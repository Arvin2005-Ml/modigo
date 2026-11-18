"""Real ASGI integration: no HTTP mocks, network, database or model credentials."""
import asyncio
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, parse_qs
from uuid import uuid4
import httpx
from app.main import create_app
from support import MemoryTestStore
from app.core.config import Settings
from app.core.errors import DomainError
from app.core.schemas import Context, PreferencesUpdate, StartInput, TAGS
from app.core.values import replace
from app.modules.catalog.schemas import ReviewInput, DraftUpdate
from app.modules.catalog.bootstrap import seed_bank, seed_demo
from app.modules.recommendations.eligibility import eligible

ORIGIN = 'http://localhost:3000'
CONTEXT = dict(available_minutes=30, energy='low', social_mode='solo', party_size=1,
               venue='home', budget={'mode': 'free'}, mood='skip')
PASSWORD = 'a sufficiently long password'


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Restricted runners may block asyncio socketpair wakeups from worker threads.
        # A test-only timer keeps the ASGI loop moving; application code is unmodified.
        async def tick():
            while True:
                await asyncio.sleep(.01)
        self.ticker = asyncio.create_task(tick())
        self.now = datetime(2026, 11, 7, 9, 0, tzinfo=timezone.utc)
        self.app = create_app(Settings(app_origin=ORIGIN, mongodb_uri='mongodb://public.example.test/test',
            csrf_hmac_secret='test-only-stable-csrf-secret-32-characters', catalog_release='legacy'), clock=lambda: self.now,
            store_factory=lambda _: MemoryTestStore())
        self.life = self.app.router.lifespan_context(self.app)
        await self.life.__aenter__()
        self.s = self.app.state.services
        self.clients = []
        self.a, self.ua = await self.account('a@example.test')

    async def asyncTearDown(self):
        for client in self.clients:
            await client.aclose()
        await self.life.__aexit__(None, None, None)
        self.ticker.cancel()

    async def new_client(self):
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN,
                                  headers={'Origin': ORIGIN})
        self.clients.append(client)
        token = (await client.get('/api/v1/auth/csrf')).json()['csrf_token']
        client.headers['X-CSRF-Token'] = token
        return client

    async def account(self, email):
        c = await self.new_client()
        r = await c.post('/api/v1/auth/signup', json={'email': email, 'password': PASSWORD, 'adult_confirmed': True})
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual((await c.get('/api/v1/me')).status_code, 401)
        self.assertFalse(any(m['email'] == email for m in self.s.identity.mailbox))
        r = await c.post('/api/v1/auth/login', json={'email': email, 'password': PASSWORD})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse(r.json()['user']['email_verified'])
        c.headers['X-CSRF-Token'] = r.json()['csrf_token']
        return c, r.json()['user']

    async def post(self, client, path, data=None, key=None):
        return await client.post('/api/v1' + path, json=data or {}, headers={'Idempotency-Key': key or str(uuid4())})

    async def slate(self, client=None, context=None):
        client = client or self.a
        r = await self.post(client, '/check-ins', context or CONTEXT)
        self.assertEqual(r.status_code, 201, r.text)
        r = await self.post(client, '/recommendation-sessions', {'check_in_id': r.json()['id']})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    async def start(self, client=None, slate=None):
        client = client or self.a
        slate = slate or await self.slate(client)
        item = slate['items'][0]
        r = await self.post(client, '/experiences', dict(recommendation_session_id=slate['id'],
                             slot_id=item['slot_id'], revision_id=item['revision_id']))
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    async def next_suggestion(self, slate):
        current = (await self.a.get('/api/v1/recommendation-sessions/' + slate['id'])).json()
        result = await self.post(self.a, f'/recommendation-sessions/{slate["id"]}/slots/{current["items"][0]["slot_id"]}/replace',
                                 {'expected_version': current['version']})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertTrue(result.json()['replaced'])
        return (await self.a.get('/api/v1/recommendation-sessions/' + slate['id'])).json()

    async def test_full_flow_real_api(self):
        slate = await self.slate()
        self.assertEqual(slate['result_count'], 1)
        self.assertEqual(len(slate['items']), 1)
        self.assertFalse(slate['partial'])
        self.assertEqual(slate['replacements_remaining'], 6)
        self.assertNotIn('score', str(slate))
        item = slate['items'][0]
        detail = await self.a.get('/api/v1/activity-revisions/' + item['revision_id'])
        self.assertEqual(detail.status_code, 200)
        self.assertGreaterEqual(len(detail.json()['content']['steps']), 2)
        e = await self.start(slate=slate)
        completed = await self.post(self.a, f'/experiences/{e["id"]}/complete')
        self.assertEqual(completed.status_code, 200, completed.text)
        self.assertEqual(completed.json()['award']['points'], 10)
        self.assertEqual(completed.json()['award']['new_badges'], ['first_step'])
        feedback = await self.a.put(f'/api/v1/experiences/{e["id"]}/feedback', json={'rating': 'liked', 'reason': None})
        self.assertEqual(feedback.status_code, 200, feedback.text)
        self.assertEqual((await self.a.get('/api/v1/me/journey')).json()['total_points'], 10)
        self.assertIsNone((await self.a.get('/api/v1/experiences/active')).json()['experience'])

    async def test_readiness_checks_storage_and_liveness_survives_outage(self):
        from unittest.mock import patch
        from app.core.storage import StorageUnavailable
        ready = await self.a.get('/api/v1/health/ready')
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json()['data_backend'], 'mongo')
        with patch.object(self.s.store, 'ping', side_effect=StorageUnavailable('database unavailable')):
            failed = await self.a.get('/api/v1/health/ready')
            self.assertEqual(failed.status_code, 503)
            self.assertNotIn('database unavailable', failed.text)
            self.assertEqual((await self.a.get('/api/v1/health/live')).status_code, 200)

    async def test_csrf_key_survives_recreating_identity_service(self):
        from app.modules.identity.service import Identity
        raw = self.a.cookies.get('funilo_session_dev')
        new_identity = Identity(self.s.store, self.app.state.settings, lambda: self.now, self.s.limiter)
        token, preauth = new_identity.issue_csrf(raw, None)
        self.assertEqual(token, self.a.headers['X-CSRF-Token'])
        self.assertIsNone(preauth)
        new_identity.check_csrf(raw, None, token, ORIGIN)

    async def test_database_outage_during_csrf_returns_safe_503(self):
        from unittest.mock import patch
        from app.core.storage import StorageUnavailable
        with patch.object(self.s.store, 'get', side_effect=StorageUnavailable('database unavailable')):
            response = await self.post(self.a, '/check-ins', CONTEXT)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('database unavailable', response.text)

    async def test_cook_http_authorization_and_idempotency(self):
        activity = next(a for a in self.s.store.list('activities') if a['seed_key'] == 'bank:D-001')
        draft = next(r for r in self.s.store.list('activity_revisions') if r['activity_id'] == activity['id'])
        path = '/admin/activities/' + activity['id'] + '/cook'
        payload = {'target_draft_id': draft['id'], 'expected_draft_version': 1}
        self.assertEqual((await self.post(self.a, path, payload)).status_code, 403)
        self.s.identity.promote(self.ua['email'], 'editor')
        self.a.headers['X-CSRF-Token'] = (await self.a.get('/api/v1/auth/csrf')).json()['csrf_token']
        login = await self.post(self.a, '/auth/login', {'email': self.ua['email'], 'password': PASSWORD})
        self.assertEqual(login.status_code, 200, login.text)
        self.a.headers['X-CSRF-Token'] = login.json()['csrf_token']
        key = str(uuid4())
        result = await self.post(self.a, path, payload, key)
        self.assertEqual(result.status_code, 202, result.text)
        self.assertEqual((await self.post(self.a, path, payload, key)).json(), result.json())
        self.assertEqual(len(self.s.store.list('content_jobs')), 1)
        self.assertNotIn('constraints', result.json())
        self.assertEqual((await self.a.get('/api/v1/admin/jobs/' + result.json()['id'])).status_code, 200)

    async def test_csrf_missing_wrong_origin_and_cross_session(self):
        for headers in ({'X-CSRF-Token': ''}, {'Origin': 'https://attacker.test'}, {'X-CSRF-Token': 'x' * 64}):
            r = await self.a.post('/api/v1/check-ins', json=CONTEXT, headers=headers)
            self.assertEqual(r.status_code, 403)
            self.assertEqual(r.json()['error']['code'], 'CSRF_FAILED')
        other = await self.new_client()
        r = await other.post('/api/v1/auth/login', json={'email': self.ua['email'], 'password': PASSWORD},
                             headers={'X-CSRF-Token': self.a.headers['X-CSRF-Token']})
        self.assertEqual(r.status_code, 403)

    async def test_localhost_and_loopback_aliases_both_work_with_own_cookie(self):
        # Browsers scope cookies to each hostname, so obtain a token separately.
        for origin in ('http://localhost:3000', 'http://127.0.0.1:3000'):
            client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),
                                      base_url=origin, headers={'Origin': origin})
            self.clients.append(client)
            client.headers['X-CSRF-Token'] = (await client.get('/api/v1/auth/csrf')).json()['csrf_token']
            response = await self.post(client, '/auth/signup', {
                'email': 'test-' + ('localhost' if 'localhost' in origin else 'ip') + '@example.test',
                'password': PASSWORD, 'adult_confirmed': True})
            self.assertEqual(response.status_code, 202, response.text)

    async def test_wrong_origin_and_missing_cookie_are_distinguishable(self):
        wrong_origin = await self.a.post('/api/v1/auth/signup', json={}, headers={'Origin': 'https://attacker.test'})
        self.assertEqual(wrong_origin.status_code, 403)
        self.assertIn('آدرس صفحه', wrong_origin.json()['error']['message'])
        no_cookie = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN,
            headers={'Origin': ORIGIN, 'X-CSRF-Token': 'not-a-valid-token'})
        self.clients.append(no_cookie)
        result = await no_cookie.post('/api/v1/auth/signup', json={})
        self.assertEqual(result.status_code, 403)
        self.assertIn('کوکی', result.json()['error']['message'])

    async def test_cookie_flags_and_no_store(self):
        c = await self.new_client()
        r = await c.post('/api/v1/auth/login', json={'email': self.ua['email'], 'password': PASSWORD})
        cookie = r.headers['set-cookie'].lower()
        self.assertIn('httponly', cookie)
        self.assertIn('samesite=lax', cookie)
        self.assertIn('path=/', cookie)
        self.assertEqual(r.headers['cache-control'], 'no-store')

    async def test_session_expiry_and_suspended_user(self):
        session = self.s.store.list('auth_sessions')[0]
        session['expires_at'] = self.now
        replace(self.s.store, 'auth_sessions', session)
        self.assertEqual((await self.a.get('/api/v1/me')).status_code, 401)

    async def test_idle_expiry(self):
        self.now += timedelta(days=8)
        self.assertEqual((await self.a.get('/api/v1/me')).status_code, 401)

    async def test_expired_session_can_use_fresh_preauth_csrf(self):
        self.now += timedelta(days=8)
        fresh = await self.a.get('/api/v1/auth/csrf')
        self.a.headers['X-CSRF-Token'] = fresh.json()['csrf_token']
        response = await self.post(self.a, '/auth/signup', {
            'email': 'new@example.test', 'password': PASSWORD, 'adult_confirmed': True})
        self.assertEqual(response.status_code, 202, response.text)

    async def test_suspended_session_denied(self):
        u = self.s.store.get('users', self.ua['id'])
        u['status'] = 'suspended'
        replace(self.s.store, 'users', u)
        self.assertEqual((await self.a.get('/api/v1/me')).status_code, 401)

    async def test_logout_revokes_and_is_repeatable(self):
        raw = self.a.cookies.get('funilo_session_dev')
        self.assertEqual((await self.post(self.a, '/auth/logout')).status_code, 204)
        token = (await self.a.get('/api/v1/auth/csrf')).json()['csrf_token']
        self.a.headers['X-CSRF-Token'] = token
        self.assertEqual((await self.post(self.a, '/auth/logout')).status_code, 204)
        self.a.cookies.set('funilo_session_dev', raw)
        self.assertEqual((await self.a.get('/api/v1/me')).status_code, 401)

    async def test_registration_no_verification_and_role_not_public(self):
        self.assertEqual(self.s.identity.mailbox, [])
        self.assertFalse(self.s.identity.user(self.ua['id'])['email_verified'])
        self.assertEqual((await self.post(self.a, '/auth/verify-email', {'token': 'unused'})).status_code, 404)
        duplicate = await self.post(self.a, '/auth/signup', {'email': self.ua['email'], 'password': PASSWORD, 'adult_confirmed': True})
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual((await self.a.get('/api/v1/mailbox')).status_code, 404)
        self.assertEqual((await self.post(self.a, '/me/role', {'role': 'admin'})).status_code, 404)

    async def test_horizontal_access_all_resources(self):
        slate = await self.slate()
        e = await self.start(slate=slate)
        b, _ = await self.account('b@example.test')
        for path in ('/recommendation-sessions/' + slate['id'], '/experiences/' + e['id']):
            self.assertEqual((await b.get('/api/v1' + path)).status_code, 404)
        self.assertEqual((await self.post(b, '/experiences/' + e['id'] + '/complete')).status_code, 404)
        self.assertEqual((await b.put('/api/v1/experiences/' + e['id'] + '/feedback', json={'rating': 'liked'})).status_code, 404)
        self.assertEqual((await b.delete('/api/v1/experiences/' + e['id'] + '/feedback')).status_code, 404)
        self.assertIsNone((await b.get('/api/v1/experiences/active')).json()['experience'])

    async def test_idempotency_same_payload_and_conflict(self):
        key = str(uuid4())
        r = await self.post(self.a, '/check-ins', CONTEXT, key)
        again = await self.post(self.a, '/check-ins', CONTEXT, key)
        self.assertEqual(r.json(), again.json())
        different = await self.post(self.a, '/check-ins', {**CONTEXT, 'available_minutes': 15}, key)
        self.assertEqual(different.status_code, 409)
        self.assertEqual(len(self.s.store.list('check_ins')), 1)

    async def test_invalid_input_and_persian_digits(self):
        for context in ({**CONTEXT, 'party_size': True}, {**CONTEXT, 'available_minutes': 4},
                        {**CONTEXT, 'role': 'admin'}, {**CONTEXT, 'social_mode': 'together'}):
            self.assertEqual((await self.post(self.a, '/check-ins', context)).status_code, 422)
        r = await self.post(self.a, '/check-ins', {**CONTEXT, 'available_minutes': '۳۰'})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()['context']['available_minutes'], 30)

    async def test_constraints_cannot_be_weakened(self):
        p = self.s.identity.preferences(self.ua['id'])
        p['preferences'].update(blocked_tags=['imagination'], max_mobility='seated', requires_quiet=True, owned_items=['pen'])
        r = await self.a.put('/api/v1/me/preferences', json=p)
        self.assertEqual(r.status_code, 200, r.text)
        r = await self.post(self.a, '/check-ins', {**CONTEXT, 'blocked_tags': [], 'requires_quiet': False,
                                                'max_mobility': 'active', 'owned_items': []})
        c = r.json()['context']
        self.assertEqual(c['blocked_tags'], ['imagination'])
        self.assertEqual(c['owned_items'], [])
        self.assertTrue(c['requires_quiet'])
        self.assertEqual(c['max_mobility'], 'seated')

    async def test_empty_results_never_relax_constraints(self):
        slate = await self.slate(context={**CONTEXT, 'venue': 'outdoor', 'blocked_tags': sorted(TAGS)})
        self.assertEqual(slate['result_count'], 0)
        self.assertEqual(slate['empty_reason'], 'NO_MATCHES')

    async def test_short_check_in_can_offer_and_start_either_non_home_venue(self):
        body = dict(available_minutes=30, energy='low', social_mode='solo', party_size=1,
                    venue='away_from_home', budget={'mode': 'free'}, activity_intent='learn')
        # The chosen intent should win among eligible offers, even with a home match.
        unrestricted = Context.model_validate({**body, 'venue': 'any'}).model_dump()
        candidates = [a for a in self.s.catalog.candidates() if eligible(unrestricted, a, self.now)]
        picks = [next(a for a in candidates if a['content']['venue'] == venue
                      and a['content']['primary_dimension'] == dimension)
                 for venue, dimension in (('home', 'mastery'), ('outdoor', 'detachment'), ('indoor_public', 'mastery'))]
        keep = {a['id'] for a in picks}
        with self.s.store.atomic():
            for activity in self.s.store.list('activities'):
                if activity['active'] and activity['id'] not in keep:
                    activity['active'] = False
                    replace(self.s.store, 'activities', activity)
        check = await self.post(self.a, '/check-ins', body)
        self.assertEqual(check.status_code, 201, check.text)
        self.assertEqual(check.json()['context']['activity_intent'], 'learn')
        created = await self.post(self.a, '/recommendation-sessions', {'check_in_id': check.json()['id']})
        self.assertEqual(created.status_code, 201, created.text)
        slate = created.json()
        self.assertEqual(slate['context_summary']['venue'], 'away_from_home')
        self.assertEqual(slate['items'][0]['activity_id'], picks[2]['id'])
        fresh = await self.next_suggestion(slate)
        self.assertEqual(fresh['items'][0]['activity_id'], picks[1]['id'])
        self.assertFalse(fresh['replacement_available'])
        e = await self.start(slate=fresh)
        self.assertEqual(e['content_snapshot']['venue'], 'outdoor')
        self.assertEqual((await self.post(self.a, f'/experiences/{e["id"]}/complete')).status_code, 200)

    async def test_previously_empty_onboarding_choices_can_start_and_finish(self):
        for venue, size in (('outdoor', 1), ('outdoor', 12), ('indoor_public', 1), ('indoor_public', 12)):
            context = {**CONTEXT, 'venue': venue, 'available_minutes': 5, 'party_size': size,
                'social_mode': 'solo' if size == 1 else 'together', 'max_mobility': 'seated',
                'requires_step_free': True, 'requires_quiet': True}
            slate = await self.slate(context=context)
            self.assertEqual(slate['result_count'], 1)
            e = await self.start(slate=slate)
            self.assertEqual((await self.post(self.a, '/experiences/' + e['id'] + '/complete')).status_code, 200)

    async def test_two_candidate_catalog_returns_one_and_one_replacement(self):
        candidates = self.s.catalog.candidates()
        compatible = [a for a in candidates if a['content']['venue'] == 'outdoor'
                      and a['content']['supported_social_modes'] == ['solo']
                      and not a['content']['required_items']][:2]
        keep = {a['id'] for a in compatible}
        with self.s.store.atomic():
            for activity in self.s.store.list('activities'):
                if activity['active'] and activity['id'] not in keep:
                    activity['active'] = False
                    replace(self.s.store, 'activities', activity)
        slate = await self.slate(context={**CONTEXT, 'venue': 'outdoor'})
        self.assertEqual(slate['result_count'], 1)
        self.assertFalse(slate['partial'])
        self.assertIsNone(slate['empty_reason'])
        self.assertTrue(slate['replacement_available'])
        fresh = await self.next_suggestion(slate)
        self.assertFalse(fresh['replacement_available'])
        self.assertEqual(fresh['replacements_remaining'], 5)

    async def test_current_active_activity_is_excluded_from_new_recommendations(self):
        context = {**CONTEXT, 'venue': 'outdoor', 'available_minutes': 5}
        first = await self.slate(context=context)
        experience = await self.start(slate=first)
        with self.s.store.atomic():
            for activity in self.s.store.list('activities'):
                if activity['active'] and activity['id'] != experience['activity_id']:
                    activity['active'] = False
                    replace(self.s.store, 'activities', activity)
        slate = await self.slate(context=context)
        self.assertEqual(slate['result_count'], 0)
        self.assertNotIn(experience['activity_id'], [i['activity_id'] for i in slate['items']])
        self.now += timedelta(hours=25)
        self.assertEqual((await self.slate(context=context))['result_count'], 1)

    async def test_optional_tastes_and_tools_use_profile_defaults_and_explicit_empty(self):
        prefs = self.s.identity.preferences(self.ua['id'])
        prefs['preferences'].update(owned_items=['paper', 'pen'], liked_tags=['drawing'], default_goal='choose')
        self.assertEqual((await self.a.put('/api/v1/me/preferences', json=prefs)).status_code, 200)
        inherited = await self.post(self.a, '/check-ins', CONTEXT)
        self.assertEqual(inherited.json()['context']['owned_items'], ['paper', 'pen'])
        self.assertEqual(inherited.json()['context']['liked_tags'], ['drawing'])
        self.assertEqual(inherited.json()['context']['goal'], 'choose')
        explicit = await self.post(self.a, '/check-ins', {**CONTEXT, 'owned_items': [], 'liked_tags': [], 'goal': 'any'})
        self.assertEqual(explicit.json()['context']['owned_items'], [])
        self.assertEqual(explicit.json()['context']['liked_tags'], [])
        self.assertEqual(explicit.json()['context']['goal'], 'any')

    async def test_import_idempotent_raw_never_visible(self):
        seed_bank(self.s.store, self.s.clock)
        seed_demo(self.s.store, self.s.clock)
        self.assertEqual(len(self.s.store.list('activities')), 581)
        raw = [r for r in self.s.store.list('activity_revisions') if r['state'] == 'draft']
        self.assertEqual(len(raw), 450)
        self.assertEqual((await self.a.get('/api/v1/activity-revisions/' + raw[0]['id'])).status_code, 404)
        self.assertEqual((await self.a.get('/api/v1/admin/activities')).status_code, 403)

    async def test_replace_keeps_slot_and_rejects_stale_card(self):
        slate = await self.slate()
        first = slate['items'][0]
        path = f'/recommendation-sessions/{slate["id"]}/slots/{first["slot_id"]}/replace'
        result = await self.post(self.a, path, {'expected_version': slate['version']})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertTrue(result.json()['replacement_available'])
        self.assertEqual(result.json()['item']['slot_id'], first['slot_id'])
        fresh = (await self.a.get('/api/v1/recommendation-sessions/' + slate['id'])).json()
        self.assertEqual(len(fresh['items']), 1)
        self.assertNotEqual(fresh['items'][0]['activity_id'], first['activity_id'])
        self.assertEqual((await self.post(self.a, path, {'expected_version': slate['version']})).status_code, 409)
        r = await self.post(self.a, '/experiences', {'recommendation_session_id': slate['id'],
                            'slot_id': first['slot_id'], 'revision_id': first['revision_id']})
        self.assertEqual(r.status_code, 409)

    async def test_complete_race_single_ledger_and_badge(self):
        e = await self.start()
        def finish(_):
            return self.s.experiences.complete(self.ua['id'], e['id'])
        with ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(finish, range(20)))
        self.assertTrue(all(r['award'] == results[0]['award'] for r in results))
        self.assertEqual(len(self.s.store.list('reward_ledger')), 1)
        self.assertEqual(len(self.s.store.list('user_badges')), 1)
        self.assertEqual(self.s.experiences.journey(self.ua['id'])['total_points'], 10)
        self.now += timedelta(days=2)
        # Domain replay persists beyond the 24-hour receipt retention window.
        self.assertEqual(finish(0)['award'], results[0]['award'])

    async def test_start_race_only_one_active(self):
        slate = await self.slate()
        item = slate['items'][0]
        data = StartInput(recommendation_session_id=slate['id'],slot_id=item['slot_id'],revision_id=item['revision_id'])
        def start(_):
            try:
                self.s.experiences.start(self.ua['id'], data)
                return 'created'
            except DomainError as e:
                return e.code
        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(start, range(10)))
        self.assertEqual(results.count('created'), 1)
        self.assertEqual(results.count('ACTIVE_EXPERIENCE'), 9)

    async def test_daily_cap_and_recent_activity(self):
        slate = await self.slate()
        first = slate['items'][0]
        for i in range(4):
            if i:
                slate = await self.next_suggestion(slate)
            item = slate['items'][0]
            r = await self.post(self.a, '/experiences', {'recommendation_session_id': slate['id'],
                             'slot_id': item['slot_id'], 'revision_id': item['revision_id']})
            self.assertEqual(r.status_code, 201, r.text)
            result = await self.post(self.a, f'/experiences/{r.json()["id"]}/complete')
            self.assertEqual(result.json()['award']['points'], 10 if i < 3 else 0)
            if i == 3:
                self.assertEqual(result.json()['award']['reason'], 'DAILY_CAP')
        self.now += timedelta(days=1, minutes=1)
        fresh = await self.slate()
        # Find a recent activity by creating a slate from a new check-in, then choose it explicitly if shown.
        internal = self.s.store.get('recommendation_sessions', fresh['id'])
        internal['items'][0].update(activity_id=first['activity_id'], revision_id=first['revision_id'])
        replace(self.s.store, 'recommendation_sessions', internal)
        fresh = self.s.recommendations.get(self.ua['id'], fresh['id'])
        e = await self.start(slate=fresh)
        r = await self.post(self.a, f'/experiences/{e["id"]}/complete')
        self.assertEqual(r.json()['award']['reason'], 'RECENT_ACTIVITY')

    async def test_publish_permissions_pointer_and_withdrawal_receipt_redaction(self):
        slate = await self.slate()
        item = slate['items'][0]
        self.s.identity.promote(self.ua['email'], 'editor')
        actor = self.s.identity.user(self.ua['id'])
        draft = self.s.catalog.clone(actor, item['activity_id'], item['revision_id'])
        draft = self.s.catalog.submit(actor, draft['id'], draft['draft_version'])
        with self.assertRaises(DomainError) as ctx:
            self.s.catalog.publish(actor, draft['id'], draft['draft_version'])
        self.assertEqual(ctx.exception.status, 403)
        self.s.identity.promote(self.ua['email'], 'admin')
        actor = self.s.identity.user(self.ua['id'])
        self.s.catalog.publish(actor, draft['id'], draft['draft_version'])
        self.assertEqual(self.s.catalog.revision(item['revision_id'])['state'], 'superseded')
        self.assertEqual(self.s.catalog.activity(item['activity_id'])['published_revision_id'], draft['id'])
        data = StartInput(recommendation_session_id=slate['id'], slot_id=item['slot_id'], revision_id=item['revision_id'])
        with self.assertRaises(DomainError) as ctx:
            self.s.experiences.start(actor['id'], data)
        self.assertEqual(ctx.exception.code, 'VERSION_CONFLICT')
        self.s.catalog.withdraw(actor, item['activity_id'], 'بازبینی مجدد محتوا')
        from app.http.presentation import public_response
        self.assertEqual(public_response(slate, self.s.store)['items'][0], {'slot_id': item['slot_id'], 'unavailable': True})
        with self.assertRaises(DomainError) as ctx:
            self.s.catalog.visible_revision(item['revision_id'])
        self.assertEqual(ctx.exception.status, 410)

    async def test_password_reset_revokes_sessions_and_token_is_one_use(self):
        r = await self.post(self.a, '/auth/forgot-password', {'email': self.ua['email']})
        self.assertEqual(r.status_code, 202)
        link = self.s.identity.mailbox[-1]['link']
        token = parse_qs(urlsplit(link).query)['reset_password'][0]
        fresh = await self.new_client()
        new_password = ' a new password with spaces '
        r = await self.post(fresh, '/auth/reset-password', {'token': token, 'new_password': new_password})
        self.assertEqual(r.status_code, 204, r.text)
        self.assertEqual((await self.a.get('/api/v1/me')).status_code, 401)
        self.assertEqual((await self.post(fresh, '/auth/reset-password', {'token': token, 'new_password': new_password})).status_code, 400)
        r = await self.post(fresh, '/auth/login', {'email': self.ua['email'], 'password': new_password.strip()})
        self.assertEqual(r.status_code, 401)
        r = await self.post(fresh, '/auth/login', {'email': self.ua['email'], 'password': new_password})
        self.assertEqual(r.status_code, 200, r.text)

    async def test_reset_expiry_and_generic_unknown_email(self):
        known = await self.post(self.a, '/auth/forgot-password', {'email': self.ua['email']})
        unknown = await self.post(self.a, '/auth/forgot-password', {'email': 'unknown@example.test'})
        self.assertEqual(known.json(), unknown.json())
        token = parse_qs(urlsplit(self.s.identity.mailbox[-1]['link']).query)['reset_password'][0]
        self.now += timedelta(minutes=31)
        fresh = await self.new_client()
        r = await self.post(fresh, '/auth/reset-password', {'token': token, 'new_password': PASSWORD})
        self.assertEqual(r.status_code, 400)

    async def test_strict_adult_confirmation_and_role_injection(self):
        c = await self.new_client()
        for extra in ({'adult_confirmed': 1}, {'adult_confirmed': False}, {'adult_confirmed': True, 'role': 'admin'}):
            r = await self.post(c, '/auth/signup', {'email': 'bad@example.test', 'password': PASSWORD, **extra})
            self.assertEqual(r.status_code, 422, r.text)

    async def test_slate_creation_race_reuses_one_session(self):
        r = await self.post(self.a, '/check-ins', CONTEXT)
        check_id = r.json()['id']
        def create(_):
            try:
                return self.s.recommendations.create(self.ua['id'], check_id)
            except DomainError as e:
                return e.code
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(create, range(8)))
        slates = [s for s in outcomes if isinstance(s, dict)]
        self.assertEqual(len(slates), 8)
        self.assertEqual(len({s['id'] for s in slates}), 1)
        self.assertEqual(len(self.s.store.list('recommendation_sessions')), 1)
        self.assertEqual(self.s.store.get('check_ins', check_id)['created_slate_count'], 1)

    async def test_start_rechecks_latest_persistent_constraints(self):
        slate = await self.slate()
        first = slate['items'][0]
        revision = self.s.catalog.revision(first['revision_id'])
        p = self.s.identity.preferences(self.ua['id'])
        p['preferences']['blocked_tags'] = revision['content']['tags']
        await self.a.put('/api/v1/me/preferences', json=p)
        r = await self.post(self.a, '/experiences', {'recommendation_session_id': slate['id'],
                            'slot_id': first['slot_id'], 'revision_id': first['revision_id']})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['error']['code'], 'INVALID_STATE')

    async def test_replace_exhaustion_does_not_increment_version(self):
        slate = await self.slate(context={**CONTEXT, 'venue': 'outdoor', 'available_minutes': 5})
        slot = slate['items'][0]
        for _ in range(6):
            before = slate['version']
            r = await self.post(self.a, f'/recommendation-sessions/{slate["id"]}/slots/{slot["slot_id"]}/replace', {'expected_version': before})
            self.assertEqual(r.status_code, 200, r.text)
            if not r.json()['replaced']:
                self.assertEqual(r.json()['session_version'], before)
                self.assertEqual(r.json()['item'], slot)
                self.assertEqual(r.json()['replacement_count'], 5)
                break
            slate['version'] = r.json()['session_version']
            slot = r.json()['item']
        else:
            self.fail('Expected finite catalog exhaustion')

    async def test_six_replacements_are_unique_and_reload_or_new_key_cannot_reset_limit(self):
        slate = await self.slate()
        seen = {slate['items'][0]['activity_id']}
        for number in range(1, 7):
            key = str(uuid4())
            path = f'/recommendation-sessions/{slate["id"]}/slots/{slate["items"][0]["slot_id"]}/replace'
            payload = {'expected_version': slate['version']}
            result = await self.post(self.a, path, payload, key)
            self.assertEqual(result.status_code, 200, result.text)
            body = result.json()
            self.assertTrue(body['replaced'])
            self.assertEqual(body['replacement_count'], number)
            self.assertEqual(body['replacements_remaining'], 6 - number)
            self.assertNotIn(body['item']['activity_id'], seen)
            seen.add(body['item']['activity_id'])
            self.assertEqual((await self.post(self.a, path, payload, key)).json(), body)
            slate = (await self.a.get('/api/v1/recommendation-sessions/' + slate['id'])).json()
            self.assertEqual(slate['replacement_count'], number)
            duplicate = await self.post(self.a, '/recommendation-sessions', {'check_in_id': slate['check_in_id']})
            self.assertEqual(duplicate.json(), slate)
        self.assertEqual(len(seen), 7)
        self.assertFalse(slate['replacement_available'])
        seventh = await self.post(self.a, path, {'expected_version': slate['version']})
        self.assertEqual(seventh.status_code, 409)
        self.assertEqual(seventh.json()['error']['code'], 'REPLACEMENT_LIMIT')
        self.assertEqual(self.s.store.get('recommendation_sessions', slate['id'])['replacement_count'], 6)

    async def test_suggestion_history_round_trip_reload_replay_and_start(self):
        original = await self.slate()
        second = await self.next_suggestion(original)
        third = await self.next_suggestion(second)
        path = f'/recommendation-sessions/{third["id"]}/navigate'
        payload = {'direction': 'previous', 'expected_version': third['version']}
        key = str(uuid4())
        result = await self.post(self.a, path, payload, key)
        self.assertEqual(result.status_code, 200, result.text)
        back = result.json()
        self.assertEqual(back['items'], second['items'])
        self.assertEqual((back['suggestion_index'], back['suggestion_count']), (1, 3))
        self.assertEqual(back['replacement_count'], 2)
        self.assertEqual(back['replacements_remaining'], 4)
        self.assertEqual((await self.post(self.a, path, payload, key)).json(), back)
        self.assertEqual((await self.a.get('/api/v1/recommendation-sessions/' + back['id'])).json(), back)
        self.assertEqual((await self.post(self.a, '/recommendation-sessions',
            {'check_in_id': back['check_in_id']})).json(), back)
        # New generation cannot discard the unseen forward part of history.
        blocked = await self.post(self.a, f'/recommendation-sessions/{back["id"]}/slots/{back["items"][0]["slot_id"]}/replace',
            {'expected_version': back['version']})
        self.assertEqual(blocked.json()['error']['code'], 'HISTORY_NOT_AT_END')
        forward = await self.post(self.a, path, {'direction': 'next', 'expected_version': back['version']})
        self.assertEqual(forward.status_code, 200, forward.text)
        self.assertEqual(forward.json()['items'], third['items'])
        back = (await self.post(self.a, path, {'direction': 'previous',
            'expected_version': forward.json()['version']})).json()
        back = (await self.post(self.a, path, {'direction': 'previous', 'expected_version': back['version']})).json()
        self.assertEqual(back['items'], original['items'])
        self.assertEqual(back['replacement_count'], 2)
        experience = await self.start(slate=back)
        self.assertEqual(experience['revision_id'], original['items'][0]['revision_id'])

    async def test_history_remains_available_after_six_changes_without_extra_votes(self):
        slate = await self.slate()
        seen = [slate['items'][0]['activity_id']]
        for _ in range(6):
            slate = await self.next_suggestion(slate)
            seen.append(slate['items'][0]['activity_id'])
        path = f'/recommendation-sessions/{slate["id"]}/navigate'
        for expected_id in reversed(seen[:-1]):
            result = await self.post(self.a, path, {'direction': 'previous', 'expected_version': slate['version']})
            self.assertEqual(result.status_code, 200, result.text)
            slate = result.json()
            self.assertEqual(slate['items'][0]['activity_id'], expected_id)
            self.assertEqual(slate['replacement_count'], 6)
            self.assertEqual(slate['replacements_remaining'], 0)
        for expected_id in seen[1:]:
            result = await self.post(self.a, path, {'direction': 'next', 'expected_version': slate['version']})
            self.assertEqual(result.status_code, 200, result.text)
            slate = result.json()
            self.assertEqual(slate['items'][0]['activity_id'], expected_id)
        self.assertEqual(slate['suggestion_count'], 7)
        self.assertEqual(self.s.store.list('experiences'), [])

    async def test_history_navigation_ownership_validation_csrf_and_boundaries(self):
        slate = await self.slate()
        path = f'/recommendation-sessions/{slate["id"]}/navigate'
        for direction in ('previous', 'next'):
            result = await self.post(self.a, path, {'direction': direction, 'expected_version': slate['version']})
            self.assertEqual(result.status_code, 409, result.text)
            self.assertEqual(result.json()['error']['code'], 'HISTORY_BOUNDARY')
        for payload in ({'direction': 'other', 'expected_version': slate['version']},
                        {'direction': 'previous', 'expected_version': True}):
            self.assertEqual((await self.post(self.a, path, payload)).status_code, 422)
        b, _ = await self.account('history-other@example.test')
        payload = {'direction': 'previous', 'expected_version': slate['version']}
        self.assertEqual((await self.post(b, path, payload)).status_code, 404)
        self.assertEqual((await self.a.post('/api/v1' + path, json=payload,
            headers={'X-CSRF-Token': 'invalid', 'Idempotency-Key': str(uuid4())})).status_code, 403)
        fresh = (await self.a.get('/api/v1/recommendation-sessions/' + slate['id'])).json()
        self.assertEqual(fresh, slate)
        empty = await self.slate(context={**CONTEXT, 'blocked_tags': sorted(TAGS)})
        result = await self.post(self.a, f'/recommendation-sessions/{empty["id"]}/navigate',
            {'direction': 'previous', 'expected_version': empty['version']})
        self.assertEqual(result.json()['error']['code'], 'HISTORY_BOUNDARY')

    async def test_history_navigation_race_moves_once_and_stale_start_is_rejected(self):
        first = await self.slate()
        slate = await self.next_suggestion(first)
        def navigate(_):
            try:
                return self.s.recommendations.navigate(self.ua['id'], slate['id'], 'previous', slate['version'])
            except DomainError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(navigate, range(8)))
        self.assertEqual(sum(isinstance(o, dict) for o in outcomes), 1)
        self.assertEqual(outcomes.count('VERSION_CONFLICT'), 7)
        current = self.s.recommendations.get(self.ua['id'], slate['id'])
        self.assertEqual(current['items'], first['items'])
        self.assertEqual(current['replacement_count'], 1)
        item = slate['items'][0]
        result = await self.post(self.a, '/experiences', {'recommendation_session_id': slate['id'],
            'slot_id': item['slot_id'], 'revision_id': item['revision_id']})
        self.assertEqual(result.json()['error']['code'], 'VERSION_CONFLICT')

    async def test_withdrawn_history_and_replayed_navigation_remain_redacted(self):
        first = await self.slate()
        slate = await self.next_suggestion(first)
        path = f'/recommendation-sessions/{slate["id"]}/navigate'
        payload = {'direction': 'previous', 'expected_version': slate['version']}
        key = str(uuid4())
        back = await self.post(self.a, path, payload, key)
        self.assertEqual(back.status_code, 200, back.text)
        # Simulate content withdrawal without invalidating the owner's auth session.
        activity = self.s.catalog.activity(first['items'][0]['activity_id'])
        activity['active'] = False
        replace(self.s.store, 'activities', activity)
        for response in (await self.a.get('/api/v1/recommendation-sessions/' + slate['id']),
                         await self.post(self.a, path, payload, key)):
            body = response.json()
            self.assertEqual(body['items'], [{'slot_id': first['items'][0]['slot_id'], 'unavailable': True}])
            self.assertEqual(body['result_count'], 0)
            self.assertNotIn(first['items'][0]['title'], str(body))
        result = await self.post(self.a, '/experiences', {'recommendation_session_id': slate['id'],
            'slot_id': first['items'][0]['slot_id'], 'revision_id': first['items'][0]['revision_id']})
        self.assertEqual(result.json()['error']['code'], 'CONTENT_WITHDRAWN')
        forward = await self.post(self.a, path, {'direction': 'next', 'expected_version': back.json()['version']})
        self.assertEqual(forward.status_code, 200, forward.text)
        self.assertFalse(forward.json()['items'][0]['unavailable'])

    async def test_concurrent_sixth_replacement_consumes_only_one_remaining_change(self):
        slate = await self.slate()
        for _ in range(5):
            slate = await self.next_suggestion(slate)
        def change(_):
            try:
                return self.s.recommendations.replace_slot(self.ua['id'], slate['id'],
                    slate['items'][0]['slot_id'], slate['version'])
            except DomainError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(change, range(8)))
        successes = [o for o in outcomes if isinstance(o, dict)]
        self.assertEqual(len(successes), 1)
        self.assertEqual(outcomes.count('VERSION_CONFLICT'), 7)
        fresh = self.s.recommendations.get(self.ua['id'], slate['id'])
        self.assertEqual(fresh['replacement_count'], 6)
        self.assertEqual(fresh['replacements_remaining'], 0)

    async def test_need_questions_learn_from_starts_and_keep_other_users_private(self):
        b, ub = await self.account('b@example.test')
        context = Context.model_validate(CONTEXT).model_dump()
        before = self.s.recommendations._rank(ub['id'], context, [], 'fixed')[0]['activity']['id']
        slate = await self.slate(context={**CONTEXT, 'need_now': 'learn', 'desired_outcome': 'learn'})
        item = slate['items'][0]
        content = self.s.catalog.revision(item['revision_id'])['content']
        self.assertEqual(content['primary_dimension'], 'mastery')
        # Views, saves and replacements have no selection vote.
        from app.modules.recommendations.ranking import dimension_preferences
        self.assertEqual(dimension_preferences(self.s.store.list('experiences')), {})
        experience = await self.start(slate=slate)
        await self.post(self.a, '/experiences/' + experience['id'] + '/cancel')
        learned = await self.slate()
        self.assertEqual(self.s.catalog.revision(learned['items'][0]['revision_id'])['content']['primary_dimension'], 'mastery')
        fresh = await self.slate(context={**CONTEXT, 'need_now': 'unwind', 'desired_outcome': 'unwind'})
        self.assertEqual(self.s.catalog.revision(fresh['items'][0]['revision_id'])['content']['primary_dimension'], 'relaxation')
        after = self.s.recommendations._rank(ub['id'], context, [], 'fixed')[0]['activity']['id']
        self.assertEqual(before, after)
        self.assertEqual((await self.post(b, f'/recommendation-sessions/{slate["id"]}/slots/{item["slot_id"]}/replace',
            {'expected_version': slate['version']})).status_code, 404)

    async def test_new_need_answers_are_validated_by_api(self):
        for field in ('need_now', 'desired_outcome'):
            for value in ('not-a-need', True, None):
                result = await self.post(self.a, '/check-ins', {**CONTEXT, field: value})
                self.assertEqual(result.status_code, 422)

    async def test_short_check_in_rejects_invalid_intent_or_venue(self):
        for changes in ({'activity_intent': 'unrecognized'}, {'activity_intent': True},
                        {'venue': ['outdoor', 'indoor_public']}):
            result = await self.post(self.a, '/check-ins', {**CONTEXT, **changes})
            self.assertEqual(result.status_code, 422, result.text)

    async def test_rolling_reward_cap_across_local_midnight(self):
        self.now = self.now.replace(hour=20)  # 23:30 in Tehran
        slate = await self.slate()
        for i in range(3):
            if i:
                slate = await self.next_suggestion(slate)
            item = slate['items'][0]
            e = self.s.experiences.start(self.ua['id'], StartInput(recommendation_session_id=slate['id'],slot_id=item['slot_id'],revision_id=item['revision_id']))
            self.s.experiences.complete(self.ua['id'], e['id'])
        self.now += timedelta(hours=1)
        slate = await self.next_suggestion(slate)
        item = slate['items'][0]
        e = self.s.experiences.start(self.ua['id'], StartInput(recommendation_session_id=slate['id'],slot_id=item['slot_id'],revision_id=item['revision_id']))
        r = self.s.experiences.complete(self.ua['id'], e['id'])
        self.assertEqual(r['award']['reason'], 'ROLLING_CAP')
        self.assertEqual(r['award']['points'], 0)

    async def test_saved_is_private_and_withdrawal_hides_content(self):
        slate = await self.slate()
        first = slate['items'][0]
        for _ in range(2):
            self.assertEqual((await self.a.put('/api/v1/saved/'+first['activity_id'],json={})).status_code, 204)
        self.assertEqual(len((await self.a.get('/api/v1/saved')).json()['items']), 1)
        b, _ = await self.account('b@example.test')
        self.assertEqual((await b.get('/api/v1/saved')).json()['items'], [])
        self.s.identity.promote(self.ua['email'], 'admin')
        self.s.catalog.withdraw(self.s.identity.user(self.ua['id']), first['activity_id'], 'بازبینی محتوایی')
        saved = self.s.experiences.saved(self.ua['id'])
        self.assertEqual(saved[0], {'activity_id': first['activity_id'], 'unavailable': True})

    async def test_idempotency_receipt_cannot_reveal_withdrawn_snapshot(self):
        e = await self.start()
        key = str(uuid4())
        result = await self.post(self.a, '/experiences/'+e['id']+'/complete', key=key)
        self.assertIn('content_snapshot', result.json()['experience'])
        admin, ua = await self.account('admin@example.test')
        self.s.identity.promote(ua['email'], 'admin')
        self.s.catalog.withdraw(self.s.identity.user(ua['id']),e['activity_id'],'بازبینی محتوایی')
        replay = await self.post(self.a, '/experiences/'+e['id']+'/complete', key=key)
        self.assertNotIn('content_snapshot', replay.json()['experience'])
        self.assertTrue(replay.json()['experience']['unavailable'])
        self.assertEqual(result.json()['award'],replay.json()['award'])

    async def test_role_change_revokes_and_slate_expires(self):
        slate = await self.slate()
        self.now += timedelta(hours=25)
        self.assertEqual((await self.a.get('/api/v1/recommendation-sessions/'+slate['id'])).status_code, 410)
        self.s.identity.promote(self.ua['email'], 'editor')
        self.assertEqual((await self.a.get('/api/v1/me')).status_code, 401)
