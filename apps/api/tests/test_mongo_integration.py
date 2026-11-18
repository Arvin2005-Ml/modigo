"""Opt-in integration against the public MongoDB, using disposable databases.

RUN_MONGODB_TESTS=1 enables these tests. Each test owns a UUID-named database;
no test deletes/clears the configured application database. Driver/network and
transaction failures are errors when opted in, never disguised as passes/skips.
"""
import asyncio
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from app.core.config import Settings
from app.core.storage import DuplicateRecord, VersionConflict
from app.core.values import replace as save
from app.main import create_app
import test_api as api_fixture

ENABLED = os.environ.get('RUN_MONGODB_TESTS') == '1'


def isolated_settings():
    settings = Settings.load()
    uri = os.environ.get('MONGODB_TEST_URI', settings.mongodb_uri)
    parsed = urlsplit(uri)
    database_name = 'funilo_test_' + uuid4().hex
    uri = urlunsplit(parsed._replace(path='/' + database_name))
    return replace(settings, mongodb_uri=uri, app_origin=api_fixture.ORIGIN, catalog_release='legacy'), database_name


def drop_owned_database(store, database_name):
    if not database_name.startswith('funilo_test_') or len(database_name) != 44:
        raise AssertionError('Refusing to drop a database not owned by this test')
    try:
        store._client.drop_database(database_name)
    finally:
        store.close()


@unittest.skipUnless(ENABLED, 'Requires RUN_MONGODB_TESTS=1 and the locked MongoDB driver')
class MongoStorageIntegrationTests(unittest.TestCase):
    def setUp(self):
        from app.core.mongo import MongoDocumentStore
        self.settings, self.database_name = isolated_settings()
        self.store = MongoDocumentStore(self.settings.mongodb_uri)

    def tearDown(self):
        drop_owned_database(self.store, self.database_name)

    def test_rollback_unique_indexes_versions_bson_and_new_client_persistence(self):
        from app.core.mongo import MongoDocumentStore
        now = datetime(2026, 11, 9, microsecond=123456, tzinfo=timezone.utc)
        user = self.store.insert('users', {'id': 'a', 'email': 'a@example.test', 'created_at': now})
        self.assertEqual(user['created_at'].microsecond, 123000)
        self.assertEqual(user['created_at'].utcoffset().total_seconds(), 0)
        with self.assertRaises(DuplicateRecord):
            self.store.insert('users', {'id': 'b', 'email': 'a@example.test'})
        with self.assertRaises(RuntimeError):
            with self.store.atomic():
                user['email'] = 'changed@example.test'
                save(self.store, 'users', user)
                self.store.insert('reward_ledger', {'id': 'award', 'experience_id': 'experience'})
                raise RuntimeError('rollback requested')
        self.assertEqual(self.store.get('users', 'a')['email'], 'a@example.test')
        self.assertEqual(self.store.list('reward_ledger'), [])
        user['email'] = 'updated@example.test'
        self.store.replace('users', user, expected_version=1)
        with self.assertRaises(VersionConflict):
            self.store.replace('users', user, expected_version=1)
        other = MongoDocumentStore(self.settings.mongodb_uri)
        try:
            self.assertEqual(other.get('users', 'a')['email'], 'updated@example.test')
            self.assertNotIn('_id', other.get('users', 'a'))
            indexes = other._db['auth_sessions'].index_information().values()
            self.assertTrue(any(i.get('expireAfterSeconds') == 0 for i in indexes))
        finally:
            other.close()

    def test_twenty_completions_across_two_clients_create_one_award(self):
        from app.core.mongo import MongoDocumentStore
        self.store.insert('experiences', {'id': 'exp', 'user_id': 'a', 'status': 'active'})
        other = MongoDocumentStore(self.settings.mongodb_uri)
        def finish(number):
            store = self.store if number % 2 else other
            with store.atomic():
                experience = store.get('experiences', 'exp')
                if experience['status'] == 'completed':
                    return
                experience['status'] = 'completed'
                save(store, 'experiences', experience)
                store.insert('reward_ledger', {'id': 'award', 'experience_id': 'exp', 'points': 10})
        try:
            with ThreadPoolExecutor(max_workers=8) as executor:
                list(executor.map(finish, range(20)))
            self.assertEqual(len(self.store.list('reward_ledger')), 1)
        finally:
            other.close()


@unittest.skipUnless(ENABLED, 'Requires RUN_MONGODB_TESTS=1 and the locked MongoDB driver')
class MongoApiIntegrationTests(unittest.IsolatedAsyncioTestCase):
    # Exercise the existing API acceptance scenarios with the real runtime store.
    new_client = api_fixture.ApiTests.new_client
    account = api_fixture.ApiTests.account
    post = api_fixture.ApiTests.post
    slate = api_fixture.ApiTests.slate
    start = api_fixture.ApiTests.start
    test_full_flow = api_fixture.ApiTests.test_full_flow_real_api
    test_csrf = api_fixture.ApiTests.test_csrf_missing_wrong_origin_and_cross_session
    test_horizontal_access = api_fixture.ApiTests.test_horizontal_access_all_resources
    test_publication = api_fixture.ApiTests.test_publish_permissions_pointer_and_withdrawal_receipt_redaction

    async def asyncSetUp(self):
        async def tick():
            while True:
                await asyncio.sleep(.01)
        self.ticker = asyncio.create_task(tick())
        self.settings, self.database_name = isolated_settings()
        self.now = datetime.now(timezone.utc).replace(microsecond=123456)
        self.app = create_app(self.settings, clock=lambda: self.now)
        self.life = self.app.router.lifespan_context(self.app)
        await self.life.__aenter__()
        self.s = self.app.state.services
        self.clients = []
        self.a, self.ua = await self.account('a@example.test')

    async def asyncTearDown(self):
        from app.core.mongo import MongoDocumentStore
        for client in self.clients:
            await client.aclose()
        await self.life.__aexit__(None, None, None)
        cleanup = MongoDocumentStore(self.settings.mongodb_uri)
        drop_owned_database(cleanup, self.database_name)
        self.ticker.cancel()

    async def test_session_history_csrf_and_idempotency_survive_application_restart(self):
        slate = await self.slate()
        cookies = dict(self.a.cookies)
        csrf = self.a.headers['X-CSRF-Token']
        activity_ids = {a['id'] for a in self.s.store.list('activities')}
        await self.a.aclose()
        await self.life.__aexit__(None, None, None)
        self.app = create_app(self.settings, clock=lambda: self.now)
        self.life = self.app.router.lifespan_context(self.app)
        await self.life.__aenter__()
        self.s = self.app.state.services
        import httpx
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=api_fixture.ORIGIN,
            cookies=cookies, headers={'Origin': api_fixture.ORIGIN, 'X-CSRF-Token': csrf})
        self.clients.append(client)
        self.assertEqual((await client.get('/api/v1/me')).json()['id'], self.ua['id'])
        self.assertEqual((await client.get('/api/v1/auth/csrf')).json()['csrf_token'], csrf)
        loaded = await client.get('/api/v1/recommendation-sessions/' + slate['id'])
        self.assertEqual(loaded.json(), slate)
        self.assertEqual(activity_ids, {a['id'] for a in self.s.store.list('activities')})
        key = str(uuid4())
        first = await self.post(client, '/check-ins', api_fixture.CONTEXT, key)
        replay = await self.post(client, '/check-ins', api_fixture.CONTEXT, key)
        self.assertEqual(first.json(), replay.json())
        await self.start(client, slate)
