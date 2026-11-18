"""Release integrity, safe migration and city/price/access publication boundaries."""
import asyncio
import copy
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from pydantic import ValidationError
from app.core.config import Settings
from app.core.schemas import Context, ITEMS
from app.core.values import replace, uid
from app.http.presentation import public_response
from app.main import create_app
from app.modules.catalog.bootstrap import seed_bank, seed_demo
from app.modules.catalog.curated import real_catalog, import_catalog, counts
from app.modules.catalog.schemas import Content
from app.modules.catalog.service import Catalog
from app.modules.recommendations.eligibility import eligible
from support import MemoryTestStore

NOW=datetime(2026,11,14,tzinfo=timezone.utc)
ROOT=Path(__file__).resolve().parents[3]


class RealCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=real_catalog()

    def context(self,**changes):
        return Context(**(dict(available_minutes=480,energy='unknown',mood='skip',venue='any',
            social_mode='solo',party_size=1,owned_items=sorted(ITEMS),budget={'mode':'flexible'},
            allow_venue_planning=True,city='تهران',weather='fair',daylight='day')|changes)).model_dump()

    def candidate(self,entry):
        return dict(id=entry['key'],active=True,state='published',revision_id='revision',
            published_revision_id='revision',content=entry['content'])

    def test_700_reproducible_unique_executable_entries_with_honest_sources(self):
        spec=importlib.util.spec_from_file_location('build_real',ROOT/'scripts/build-real-catalog.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        built=builder.build()
        self.assertEqual(built,self.catalog)
        self.assertEqual(len({e['key'] for e in built['entries']}),700)
        self.assertEqual(len({e['content']['title'] for e in built['entries']}),700)
        self.assertEqual(len({tuple(e['content']['steps']) for e in built['entries']}),700)
        venues=[e for e in built['entries'] if e['content']['place']]
        self.assertEqual(len(venues),400)
        self.assertEqual(len({(e['content']['place']['city'],e['content']['place']['name']) for e in venues}),400)
        self.assertEqual(len({e['content']['place']['city'] for e in venues}),62)
        for entry in built['entries']:
            content=Content.model_validate(entry['content'])
            self.assertEqual(content.model_dump(mode='json'),entry['content'])
            self.assertFalse(entry['availability_verified']);self.assertFalse(entry['price_verified'])
            self.assertEqual(content.dramma.mechanisms[0].dimension,content.primary_dimension)
            if content.place:
                source=built['sources'][entry['source_ids'][0]]
                self.assertEqual(source['url'],content.place.source_url)
                self.assertEqual(content.cost.kind,'unknown')
                self.assertIsNone(content.step_free)
            else:self.assertFalse(entry['source_ids'])

    def test_each_record_has_compatible_context_and_city_is_a_hard_filter(self):
        for entry in self.catalog['entries']:
            content=entry['content'];place=content['place'];together=content['supported_social_modes']==['together']
            context=self.context(city=place['city'] if place else None,
                social_mode='together' if together else 'solo',party_size=content['min_people'] if together else 1)
            candidate=self.candidate(entry)
            with self.subTest(title=content['title']):
                self.assertIsNotNone(eligible(context,candidate,NOW))
                if place:
                    for city in (None,'شهری خارج از فهرست'):
                        self.assertIsNone(eligible({**context,'city':city},candidate,NOW))
                    for changed in ({'allow_venue_planning':False},{'requires_step_free':True},
                            {'budget':{'mode':'free'}},{'budget':{'mode':'cap','cap_toman':100000000}}):
                        self.assertIsNone(eligible(context|changed,candidate,NOW))

    def test_location_schema_rejects_unsafe_sources_and_home_venue_mismatch(self):
        original=copy.deepcopy(self.catalog['entries'][0]['content'])
        for url in ('javascript:alert(1)','http://example.com/x','//example.com/x',
                'https://127.0.0.1/x','https://10.1.2.3/x','https://host.internal/x',
                'https://user:secret@example.com/x','https://example.com:3000/x','https://example.com/\nfoo'):
            content=copy.deepcopy(original);content['place']['source_url']=url
            with self.subTest(url=url),self.assertRaises(ValidationError):Content.model_validate(content)
        for changes in ({'venue':'home'},{'requires_venue_check':False}):
            with self.assertRaises(ValidationError):Content.model_validate(original|changes)
        content=copy.deepcopy(original);content['place']['researched_on']='2026-02-30'
        with self.assertRaises(ValidationError):Content.model_validate(content)
        self.assertEqual(self.context(city='  كيش  ')['city'],'کیش')
        self.assertIsNone(self.context(city='  ')['city'])

    def test_import_archives_only_exact_legacy_preserves_identity_history_and_raw_bank(self):
        store=MemoryTestStore();seed_bank(store,lambda:NOW);seed_demo(store,lambda:NOW,include_iran=True)
        before={a['id']:copy.deepcopy(a) for a in store.list('activities')}
        revisions={r['id']:copy.deepcopy(r) for r in store.list('activity_revisions')}
        result=import_catalog(store,lambda:NOW)
        self.assertEqual(result['inserted'],700);self.assertEqual(result['legacy_archived'],413)
        self.assertEqual(result['activities'],1581);self.assertEqual(result['activity_revisions'],1581)
        self.assertEqual(result['recommendable'],700);self.assertEqual(result['curated_recommendable'],700)
        self.assertEqual(result['raw_bank'],450)
        for aid,original in before.items():
            after=store.get('activities',aid)
            self.assertEqual(after['published_revision_id'],original['published_revision_id'])
            self.assertEqual(after['next_revision_number'],original['next_revision_number'])
        for rid,original in revisions.items():
            self.assertEqual(store.get('activity_revisions',rid)['content'],original['content'])
        snapshot=copy.deepcopy(store._collections)
        again=import_catalog(store,lambda:NOW)
        self.assertEqual(again['inserted'],0);self.assertEqual(again['legacy_archived'],0)
        self.assertEqual(snapshot,store._collections)
        for revision in store.list('activity_revisions'):
            if revision['origin']=='curated':
                self.assertFalse(revision['validation_report']['human_approval'])
                self.assertEqual(revision['validation_report']['publication_basis'],'owner_request_2026_11_14')
        # An unrelated future/imported real: key must not mask a missing member
        # of this release when the CLI verifies that all 700 are recommendable.
        member=next(a for a in store.list('activities') if a['seed_key'].startswith('real:'))
        member['active']=False;replace(store,'activities',member)
        other=copy.deepcopy(member)
        other.update(id=uid(),version=1,seed_key='real:unrelated-release',active=True)
        other_revision=copy.deepcopy(store.get('activity_revisions',member['published_revision_id']))
        other_revision.update(id=uid(),activity_id=other['id'],version=1)
        other['published_revision_id']=other_revision['id']
        store.insert('activities',other)
        store.insert('activity_revisions',other_revision)
        report=counts(store)
        self.assertEqual(report['recommendable'],700)
        self.assertEqual(report['curated_recommendable'],699)

    def test_human_edits_reviews_drafts_and_withdrawn_records_are_preserved(self):
        store=MemoryTestStore();seed_demo(store,lambda:NOW,include_iran=True)
        candidates=[a for a in store.list('activities') if a['active']][:6]
        for index,a in enumerate(candidates):
            revision=store.get('activity_revisions',a['published_revision_id'])
            if index==0:revision['content']['title']='عنوان ویرایش‌شده توسط مالک'
            if index==1:revision['origin']='human'
            if index==2:revision['validation_report']['human_approval']=True
            if index==3:revision['reviewed_by']=uid()
            if index==4:a['withdrawn']=True;a['active']=False
            if index==5:
                store.insert('activity_revisions',dict(id=uid(),activity_id=a['id'],revision_number=2,
                    state='draft',origin='human',content=copy.deepcopy(revision['content'])))
            replace(store,'activity_revisions',revision);replace(store,'activities',a)
        protected={a['id']:store.get('activities',a['id']) for a in candidates}
        import_catalog(store,lambda:NOW)
        for aid,record in protected.items():self.assertEqual(store.get('activities',aid),record)
        fresh=next(a for a in store.list('activities') if a['seed_key'].startswith('real:'))
        revision=store.get('activity_revisions',fresh['published_revision_id'])
        revision['content']['title']='نسخه اصلاح‌شده تفریح واقعی';replace(store,'activity_revisions',revision)
        fresh.update(active=False,withdrawn=True);fresh=replace(store,'activities',fresh)
        result=import_catalog(store,lambda:NOW)
        self.assertEqual(result['curated_recommendable'],699)
        self.assertEqual(store.get('activities',fresh['id']),fresh)
        self.assertEqual(store.get('activity_revisions',revision['id'])['content']['title'],'نسخه اصلاح‌شده تفریح واقعی')

    def test_failed_batch_can_resume_without_retiring_old_catalog_or_duplicate_keys(self):
        store=MemoryTestStore();seed_demo(store,lambda:NOW,include_iran=True)
        original_insert=store.insert
        def fail(collection,document):
            if collection=='activities' and document.get('seed_key')==self.catalog['entries'][30]['key']:
                raise RuntimeError('simulated interruption')
            return original_insert(collection,document)
        with patch.object(store,'insert',side_effect=fail),self.assertRaises(RuntimeError):
            import_catalog(store,lambda:NOW)
        self.assertEqual(sum(a['seed_key'].startswith('real:') for a in store.list('activities')),25)
        self.assertEqual(sum(a['active'] for a in store.list('activities')),413+25)
        result=import_catalog(store,lambda:NOW)
        self.assertEqual(result['inserted'],675);self.assertEqual(result['recommendable'],700)
        self.assertEqual(len({a['seed_key'] for a in store.list('activities')}),1131)


class RealCatalogApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_release_city_link_and_full_flow_with_ownership_and_csrf(self):
        async def tick():
            while True:await asyncio.sleep(.01)
        ticker=asyncio.create_task(tick())
        origin='http://localhost:3000'
        app=create_app(Settings(app_origin=origin,mongodb_uri='mongodb://public.example.test/test',
            csrf_hmac_secret='test-only-stable-csrf-secret-32-characters'),clock=lambda:NOW,
            store_factory=lambda _:MemoryTestStore())
        try:
            async with app.router.lifespan_context(app):
                catalog_counts = counts(app.state.services.store)
                self.assertEqual(catalog_counts['curated_recommendable'],700)
                self.assertEqual(catalog_counts['recommendable'],1003)
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=origin,
                        headers={'Origin':origin}) as client:
                    csrf=(await client.get('/api/v1/auth/csrf')).json()['csrf_token'];client.headers['X-CSRF-Token']=csrf
                    password='test password of sufficient length'
                    signup=await client.post('/api/v1/auth/signup',json=dict(email='real@example.test',password=password,adult_confirmed=True))
                    self.assertEqual(signup.status_code,202,signup.text)
                    login=await client.post('/api/v1/auth/login',json=dict(email='real@example.test',password=password))
                    self.assertEqual(login.status_code,200,login.text);client.headers['X-CSRF-Token']=login.json()['csrf_token']
                    async def post(path,data=None):
                        return await client.post('/api/v1'+path,json=data or {},headers={'Idempotency-Key':str(uuid4())})
                    payload=dict(available_minutes=240,energy='low',social_mode='solo',party_size=1,
                        venue='indoor_public',budget={'mode':'flexible'},mood='skip',city='تهران',allow_venue_planning=True)
                    blocked=await client.post('/api/v1/check-ins',json=payload,headers={'X-CSRF-Token':'wrong'})
                    self.assertEqual(blocked.status_code,403)
                    check=await post('/check-ins',payload);self.assertEqual(check.status_code,201,check.text)
                    store = app.state.services.store
                    with patch.object(store, 'published_catalog', wraps=store.published_catalog) as fetch:
                        response=await post('/recommendation-sessions',{'check_in_id':check.json()['id']})
                        self.assertEqual(fetch.call_count, 1)
                    self.assertEqual(response.status_code,201,response.text);slate=response.json();item=slate['items'][0]
                    self.assertTrue(item['requires_venue_check'])
                    self.assertEqual(item['place']['city'], 'تهران')
                    self.assertIn('رزرو', item['venue_check_message'])
                    legacy_card = {k: v for k, v in item.items() if k != 'requires_venue_check'}
                    self.assertEqual(public_response(legacy_card, store),
                                     {'slot_id': item['slot_id'], 'unavailable': True})
                    cities = await client.get('/api/v1/activity-cities')
                    self.assertIn('تهران', cities.json()['cities'])
                    detail=await client.get('/api/v1/activity-revisions/'+item['revision_id'])
                    self.assertEqual(detail.status_code,200,detail.text)
                    self.assertEqual(detail.json()['content']['place']['city'],'تهران')
                    self.assertTrue(detail.json()['content']['place']['source_url'].startswith('https://'))
                    started=await post('/experiences',dict(recommendation_session_id=slate['id'],slot_id=item['slot_id'],revision_id=item['revision_id']))
                    self.assertEqual(started.status_code,201,started.text);experience=started.json()
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url=origin) as stranger:
                        self.assertEqual((await stranger.get('/api/v1/experiences/'+experience['id'])).status_code,401)
                    completed=await post('/experiences/'+experience['id']+'/complete')
                    self.assertEqual(completed.status_code,200,completed.text)
                    feedback=await client.put('/api/v1/experiences/'+experience['id']+'/feedback',json={'rating':'liked'})
                    self.assertEqual(feedback.status_code,200,feedback.text)
                    current = (await client.get('/api/v1/recommendation-sessions/' + slate['id'])).json()
                    with patch.object(store, 'published_catalog', wraps=store.published_catalog) as fetch:
                        replacement=await post(f'/recommendation-sessions/{slate["id"]}/slots/{item["slot_id"]}/replace',
                                               {'expected_version': current['version']})
                        self.assertEqual(replacement.status_code, 200, replacement.text)
                        self.assertTrue(replacement.json()['replaced'])
                        self.assertEqual(fetch.call_count, 1)
                    for overrides in ({'city': None}, {'city': 'کیش'}, {'allow_venue_planning': False}):
                        opt = await post('/check-ins', payload | overrides)
                        result = await post('/recommendation-sessions', {'check_in_id': opt.json()['id']})
                        self.assertEqual(result.status_code, 201, result.text)
                        for card in result.json()['items']:
                            if card['place']:
                                self.assertEqual(card['place']['city'], overrides.get('city', 'تهران'))
                                self.assertIs(overrides.get('allow_venue_planning', True), True)

                    # Use an actual named activity from the shipped release. Exercise the
                    # same HTTP patch/submit/publish path an editor and admin use.
                    aid, old_id = item['activity_id'], item['revision_id']
                    no_access = await client.get('/api/v1/admin/catalog/activation')
                    self.assertEqual(no_access.status_code, 403)
                    actor = store.list('users')[0]
                    replace(store, 'users', {**actor, 'role': 'admin'})
                    cloned = await post(f'/admin/activities/{aid}/revisions', {'source_revision_id': old_id})
                    self.assertEqual(cloned.status_code, 201, cloned.text)
                    draft = cloned.json()
                    original = draft['content']
                    edited = {**original, 'lighter_version': 'فقط یکی از جزئیات همین تجربه را بررسی کن.'}
                    updated = await client.patch('/api/v1/admin/revisions/' + draft['id'], json={
                        'expected_draft_version': draft['draft_version'], 'content': edited})
                    self.assertEqual(updated.status_code, 200, updated.text)
                    submitted = await post(f'/admin/revisions/{draft["id"]}/submit',
                                           {'expected_draft_version': updated.json()['draft_version']})
                    self.assertEqual(submitted.status_code, 200, submitted.text)
                    published = await post(f'/admin/revisions/{draft["id"]}/publish',
                                           {'expected_draft_version': submitted.json()['draft_version']})
                    self.assertEqual(published.status_code, 200, published.text)
                    for field in ('place', 'requires_venue_check', 'dramma'):
                        self.assertEqual(published.json()['content'][field], original[field])
                    self.assertEqual(published.json()['reviewed_by'], actor['id'])
                    self.assertIs(published.json()['validation_report']['human_approval'], True)
                    old = store.get('activity_revisions', old_id)
                    self.assertEqual(old['state'], 'superseded')
                    self.assertEqual(old['content'], original)
                    self.assertEqual(store.get('activities', aid)['published_revision_id'], draft['id'])
                    queue = await client.get('/api/v1/admin/catalog/activation?status=raw_seed&limit=3')
                    self.assertEqual(queue.status_code, 200, queue.text)
                    self.assertEqual(queue.json()['total'], 450)
                    self.assertEqual(len(queue.json()['items']), 3)
                    self.assertEqual(queue.json()['counts']['active'], 1003)

                    # At the five-minute floor, the initial home card and all six
                    # replacements must be distinct and stay free and equipment-free.
                    check = await post('/check-ins', payload | {'available_minutes': 5, 'venue': 'home',
                                       'budget': {'mode': 'free'}, 'city': None, 'allow_venue_planning': False})
                    home = (await post('/recommendation-sessions', {'check_in_id': check.json()['id']})).json()
                    seen = {home['items'][0]['activity_id']}
                    version = home['version']
                    slot = home['items'][0]['slot_id']
                    for _ in range(6):
                        response = await post(f'/recommendation-sessions/{home["id"]}/slots/{slot}/replace',
                                              {'expected_version': version})
                        self.assertEqual(response.status_code, 200, response.text)
                        result = response.json()
                        self.assertTrue(result['replaced'])
                        self.assertFalse(result['item']['requires_venue_check'])
                        self.assertEqual(result['item']['cost_label'], 'رایگان')
                        self.assertEqual(result['item']['total_minutes'], 5)
                        seen.add(result['item']['activity_id'])
                        version = result['session_version']
                    self.assertEqual(len(seen), 7)
        finally:ticker.cancel()
