"""DRAMMA contract, publication boundaries and safe shipped-demo revisioning."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
import unittest
from pydantic import ValidationError
from app.core.errors import DomainError
from app.core.values import replace, uid
from app.modules.catalog.bootstrap import demo_examples, seed_demo, seed_bank, content_checksum
from app.modules.catalog.schemas import Content
from app.modules.catalog.service import Catalog
from app.modules.content_jobs import DemoProvider, validated
from support import MemoryTestStore

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[3]


class DrammaTests(unittest.TestCase):
    def setUp(self):
        self.examples = dict(demo_examples())
        self.content = copy.deepcopy(self.examples['demo:001'])

    def test_all_cooked_content_and_cook_fixtures_have_execution_evidence(self):
        contents = list(self.examples.values()) + list(DemoProvider().fixtures.values())
        self.assertEqual(len(contents), 437)
        for content in contents:
            with self.subTest(title=content['title']):
                parsed = Content.model_validate(content)
                self.assertEqual({m.dimension for m in parsed.dramma.mechanisms},
                                 {parsed.primary_dimension, *parsed.secondary_dimensions})
                self.assertTrue(all(m.intent.strip() and m.step_indexes for m in parsed.dramma.mechanisms))

    def test_missing_duplicate_mismatched_and_invalid_step_evidence_is_rejected(self):
        mutations = [lambda c: c.pop('dramma'),
            lambda c: c['dramma'].update(version='unknown'),
            lambda c: c['dramma']['mechanisms'].pop(),
            lambda c: c['dramma']['mechanisms'].append(c['dramma']['mechanisms'][0]),
            lambda c: c['dramma']['mechanisms'][0].update(step_indexes=[0]),
            lambda c: c['dramma']['mechanisms'][0].update(step_indexes=[len(c['steps'])+1]),
            lambda c: c['dramma']['mechanisms'][0].update(step_indexes=[True]),
            lambda c: c['dramma']['mechanisms'][0].update(step_indexes=[1,1]),
            lambda c: c['dramma']['mechanisms'][0].update(intent=' ' * 20),
            lambda c: c['dramma']['mechanisms'][0].update(intent='')]
        for index, mutation in enumerate(mutations):
            content = copy.deepcopy(self.content)
            mutation(content)
            with self.subTest(case=index), self.assertRaises(ValidationError):
                Content.model_validate(content)
            with self.subTest(provider_case=index), self.assertRaises(ValueError):
                validated(json.dumps(content, ensure_ascii=False), 'detachment')

    def test_affiliation_requires_shared_execution(self):
        content = copy.deepcopy(next(c for c in self.examples.values() if c['primary_dimension']=='affiliation'))
        for modes in (['solo'], ['solo','together']):
            content.update(supported_social_modes=modes, min_people=1, max_people=1 if len(modes)==1 else 2)
            with self.subTest(modes=modes), self.assertRaisesRegex(ValidationError, 'dramma_affiliation'):
                Content.model_validate(content)

    def test_mapping_follows_execution_within_groups(self):
        cases = {'iran-cinema-01':'detachment', 'iran-theatre-11':'autonomy',
            'iran-cafe-03':'mastery', 'iran-cafe-04':'relaxation',
            'iran-textile-01':'mastery', 'iran-textile-12':'meaning',
            'iran-museum-01':'detachment', 'iran-museum-02':'meaning',
            'iran-garden-05':'mastery', 'iran-local_tour-04':'detachment',
            'iran-simulation-06':'affiliation'}
        for key, dimension in cases.items():
            self.assertEqual(self.examples['demo:'+key]['primary_dimension'], dimension)

    def test_legacy_and_activity_dimension_mismatch_cannot_be_submitted_published_or_recommended(self):
        store = MemoryTestStore()
        catalog = Catalog(store, lambda: NOW)
        actor = store.insert('users', dict(id=uid(), status='active', role='admin'))
        activity = store.insert('activities', dict(id=uid(), seed_key='manual', active=True,
            primary_dimension='detachment', published_revision_id=None))
        revision = dict(id=uid(), activity_id=activity['id'], content=self.content, draft_version=1,
            state='draft', origin='human')
        for invalid in ('legacy','wrong_dimension'):
            content = copy.deepcopy(self.content)
            if invalid == 'legacy':
                content.pop('dramma')
            else:
                activity['primary_dimension'] = 'meaning'
                activity = replace(store, 'activities', activity)
            revision['content'] = content
            for state, method in (('draft',catalog.submit),('review',catalog.publish)):
                revision['state'] = state
                if store.get('activity_revisions',revision['id']):
                    revision = replace(store, 'activity_revisions', revision)
                else:
                    revision = store.insert('activity_revisions',revision)
                with self.subTest(invalid=invalid,state=state), self.assertRaises(DomainError) as caught:
                    method(actor,revision['id'],1)
                self.assertEqual(caught.exception.status,422)
                self.assertEqual(store.get('activity_revisions',revision['id'])['state'],state)
            revision['state']='published';revision=replace(store,'activity_revisions',revision)
            activity['published_revision_id']=revision['id'];activity=replace(store,'activities',activity)
            self.assertEqual(catalog.candidates(),[])

    def test_upgrade_is_versioned_idempotent_and_preserves_editorial_and_withdrawn_content(self):
        store = MemoryTestStore()
        seed_bank(store, lambda: NOW)
        seed_demo(store, lambda: NOW)
        activities = {a['seed_key']:a for a in store.list('activities')}
        legacy = json.loads((ROOT/'content/dramma-legacy-checksums.json').read_text())['checksums']
        keys = ['demo:001','demo:iran-cinema-01','demo:iran-cinema-02','demo:iran-cinema-03','demo:iran-cinema-04','demo:iran-cinema-05']
        saved = {}
        for index,key in enumerate(keys):
            activity = activities[key]
            revision = store.get('activity_revisions',activity['published_revision_id'])
            revision['content'].pop('dramma')
            self.assertEqual(content_checksum(revision['content']),legacy[key])
            if index==1: revision['content']['title']='عنوان تغییرکردهٔ مدیر'
            if index==2: revision['origin']='human'
            if index==3: activity.update(active=False,withdrawn=True)
            if index==4: revision['validation_report']['human_approval']=True
            if index==5: revision['reviewed_by']=uid()
            revision=replace(store,'activity_revisions',revision);replace(store,'activities',activity)
            saved[key]=copy.deepcopy(revision)
        seed_demo(store, lambda: NOW)
        target=store.get('activities',activities[keys[0]]['id'])
        fresh=store.get('activity_revisions',target['published_revision_id'])
        self.assertNotEqual(fresh['id'],saved[keys[0]]['id'])
        self.assertEqual(fresh['revision_number'],2)
        self.assertFalse(fresh['validation_report']['human_approval'])
        old=store.get('activity_revisions',saved[keys[0]]['id'])
        self.assertEqual(old['state'],'superseded')
        self.assertEqual(old['content'],saved[keys[0]]['content'])
        for key in keys[1:]:
            self.assertEqual(store.get('activities',activities[key]['id'])['published_revision_id'],saved[key]['id'])
            self.assertEqual(store.get('activity_revisions',saved[key]['id']),saved[key])
        count=len(store.list('activity_revisions'))
        seed_demo(store,lambda:NOW)
        self.assertEqual(count,len(store.list('activity_revisions')))
        self.assertEqual(len([a for a in store.list('admin_audit') if a['action']=='demo_dramma_aligned']),1)
        self.assertTrue(all(not a['active'] and a['published_revision_id'] is None
                            for a in store.list('activities') if a['seed_key'].startswith('bank:')))
