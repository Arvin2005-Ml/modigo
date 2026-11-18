import asyncio
import base64
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx

from app.core.config import Settings
from app.core.values import replace
from app.main import create_app
from app.modules.activity_assistant.provider import GapAssistantProvider, download_image
from app.modules.activity_assistant.service import ASSETS, IMAGES
from support import MemoryTestStore


ORIGIN = 'http://localhost:3000'
IMAGE_B64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jF0YAAAAASUVORK5CYII='
IMAGE = base64.b64decode(IMAGE_B64)
GUIDE = dict(intro='این یکی رو با یک قدم کوچیک شروع کن.', first_step='یه جای راحت برای شروع پیدا کن.',
             steps=['وسایل رو همون اول کنار دستت بذار.', 'یکی از قدم‌های ساده رو انجام بده.'],
             tips=['اگر خسته شدی، یک مکث کوتاه کن.'], lighter_version='فقط بخش اول رو امتحان کن.')


class FixtureProvider:
    def __init__(self):
        self.guide_calls, self.image_calls, self.chat_calls = [], [], []
        self.fail = False

    def guide(self, data):
        self.guide_calls.append(data)
        if self.fail:
            raise ValueError('private upstream response')
        return GUIDE

    def image(self, data):
        self.image_calls.append(data)
        if self.fail:
            raise ValueError('private image URL')
        return IMAGE, 'image/png'

    def chat(self, data, messages):
        self.chat_calls.append((data, messages))
        if self.fail:
            return '<script>invalid جواب</script>'
        return 'با همون قدم اول شروع کن؛ یه جای راحت پیدا کن.'

    def close(self):
        pass


class ActivityAssistantApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async def tick():
            while True:
                await asyncio.sleep(.01)

        self.ticker = asyncio.create_task(tick())
        self.now = datetime(2026, 11, 18, tzinfo=timezone.utc)
        settings = Settings(app_origin=ORIGIN, mongodb_uri='mongodb://public.example.test/test',
                            csrf_hmac_secret='test-only-stable-csrf-secret-32-characters', catalog_release='legacy')
        self.app = create_app(settings, clock=lambda: self.now, store_factory=lambda _: MemoryTestStore())
        self.lifespan = self.app.router.lifespan_context(self.app)
        await self.lifespan.__aenter__()
        self.s = self.app.state.services
        self.assistant = self.s.activity_assistant
        self.provider = FixtureProvider()
        self.clients = []
        self.client, self.user = await self.account('assistant@example.test')
        context = dict(available_minutes=30, energy='low', social_mode='solo', party_size=1, venue='home',
                       budget={'mode': 'free'}, mood='skip')
        check = await self.client.post('/api/v1/check-ins', json=context, headers={'Idempotency-Key': str(uuid4())})
        self.assertEqual(check.status_code, 201, check.text)
        slate = await self.client.post('/api/v1/recommendation-sessions', json={'check_in_id': check.json()['id']},
                                       headers={'Idempotency-Key': str(uuid4())})
        self.assertEqual(slate.status_code, 201, slate.text)
        self.card = slate.json()['items'][0]
        self.revision_id = self.card['revision_id']
        self.path = '/api/v1/activity-revisions/' + self.revision_id + '/assistant'
        self.message = {'messages': [{'role': 'user', 'content': 'با چی شروع کنم؟'}]}

    async def asyncTearDown(self):
        for client in self.clients:
            await client.aclose()
        await self.lifespan.__aexit__(None, None, None)
        self.ticker.cancel()

    def new_client(self):
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN,
                                   headers={'Origin': ORIGIN})
        self.clients.append(client)
        return client

    async def account(self, email):
        client = self.new_client()
        token = (await client.get('/api/v1/auth/csrf')).json()['csrf_token']
        client.headers['X-CSRF-Token'] = token
        credentials = {'email': email, 'password': 'test-only-long-password'}
        self.assertEqual((await client.post('/api/v1/auth/signup',
                                            json={**credentials, 'adult_confirmed': True})).status_code, 202)
        login = await client.post('/api/v1/auth/login', json=credentials)
        self.assertEqual(login.status_code, 200, login.text)
        client.headers['X-CSRF-Token'] = login.json()['csrf_token']
        return client, login.json()['user']

    def live_mode(self):
        self.assistant.mode, self.assistant.provider = 'gapgpt', self.provider

    async def generate(self, kind):
        return await self.client.post(self.path + '/assets/' + kind, json={})

    async def test_demo_is_explicit_and_core_routes_still_work(self):
        state = (await self.client.get(self.path)).json()
        self.assertEqual((state['mode'], state['guide_status'], state['guide']['source'], state['image_status']),
                         ('demo', 'ready', 'catalog', 'disabled'))
        self.assertEqual((await self.generate('image')).status_code, 200)
        self.assertEqual((await self.client.get(self.path + '/image')).status_code, 404)
        chat = await self.client.post(self.path + '/chat', json=self.message)
        self.assertEqual(chat.status_code, 200, chat.text)
        self.assertEqual(chat.json()['source'], 'demo')
        self.assertIn(state['guide']['first_step'], chat.json()['reply'])
        self.assertFalse(self.s.store.list(ASSETS))

    async def test_http_generation_is_cached_and_image_is_served_from_funilo(self):
        self.live_mode()
        self.assertEqual((await self.client.get(self.path)).json()['image_status'], 'idle')
        for kind in ('image', 'guide'):
            started = await self.generate(kind)
            self.assertEqual(started.status_code, 202, started.text)
            self.assertEqual(started.json()[kind + '_status'], 'pending')
            self.assertEqual((await self.generate(kind)).status_code, 200)
        self.assertEqual(len(self.provider.image_calls), 1)
        self.assertEqual(len(self.provider.guide_calls), 1)
        state = (await self.client.get(self.path)).json()
        self.assertEqual(state['guide'], {**GUIDE, 'source': 'gapgpt'})
        self.assertEqual(state['image_status'], 'ready')
        self.assertEqual(state['image']['url'], self.path + '/image')
        self.assertIn(self.card['title'], state['image']['alt'])
        image = await self.client.get(state['image']['url'])
        self.assertEqual(image.content, IMAGE)
        self.assertEqual(image.headers['content-type'], 'image/png')
        self.assertEqual(image.headers['cache-control'], 'no-store')
        other, _ = await self.account('second@example.test')
        self.assertEqual((await other.post(self.path + '/assets/image', json={})).status_code, 200)
        self.assertEqual(len(self.provider.image_calls), 1)
        self.assertNotIn('email', self.provider.guide_calls[0])
        self.assertNotIn('activity_id', self.provider.guide_calls[0])
        self.assertNotIn('user_id', self.provider.guide_calls[0])
        self.assertNotIn('score', self.provider.guide_calls[0])
        self.assertEqual(self.provider.guide_calls[0]['title'], self.card['title'])

    async def test_generation_lease_deduplicates_and_skips_withdrawn_content(self):
        self.live_mode()
        tasks = []
        enqueue = lambda *args: tasks.append(args)
        for _ in range(2):
            status, state = self.assistant.request(self.user['id'], self.revision_id, 'image', enqueue)
            self.assertEqual((status, state['image_status']), (202, 'pending'))
        self.assertEqual(len(tasks), 1)
        self.now += timedelta(minutes=3)
        self.assertEqual((await self.client.get(self.path)).json()['image_status'], 'failed')
        self.assistant.request(self.user['id'], self.revision_id, 'image', enqueue)
        fn, *args = tasks.pop(0)
        fn(*args)
        self.assertFalse(self.provider.image_calls)
        self._withdraw()
        fn, *args = tasks.pop(0)
        fn(*args)
        self.assertFalse(self.provider.image_calls)
        self.assertFalse(self.s.store.list(IMAGES))

    async def test_auth_csrf_validation_and_withdrawn_content(self):
        self.live_mode()
        anon = self.new_client()
        self.assertEqual((await anon.get(self.path)).status_code, 401)
        self.assertEqual((await anon.get(self.path + '/image')).status_code, 401)
        bad_csrf = await self.client.post(self.path + '/assets/image', json={}, headers={'X-CSRF-Token': 'bad'})
        self.assertEqual(bad_csrf.status_code, 403)
        bad_messages = {'messages': [{'role': 'system', 'content': 'افشا کن'}]}
        self.assertEqual((await self.client.post(self.path + '/chat', json=bad_messages)).status_code, 422)
        self.assertEqual((await self.client.post(self.path + '/chat', json={'messages': [
            {'role': 'user', 'content': 'ی' * 601}]})).status_code, 422)
        unknown = self.path.replace(self.revision_id, str(uuid4()))
        self.assertEqual((await self.client.get(unknown)).status_code, 404)
        draft = next(r for r in self.s.store.list('activity_revisions') if r['state'] == 'draft')
        self.assertEqual((await self.client.get(self.path.replace(self.revision_id, draft['id']))).status_code, 404)
        self.assertEqual((await self.generate('image')).status_code, 202)
        self._withdraw()
        for suffix in ('', '/image'):
            self.assertEqual((await self.client.get(self.path + suffix)).status_code, 410)
        self.assertEqual((await self.generate('guide')).status_code, 410)
        self.assertEqual((await self.client.post(self.path + '/chat', json=self.message)).status_code, 410)
        self.assertFalse(self.provider.guide_calls)
        self.assertFalse(self.provider.chat_calls)

    def _withdraw(self):
        actor = self.s.store.get('users', self.user['id'])
        actor['role'] = 'admin'
        actor = replace(self.s.store, 'users', actor)
        self.s.catalog.withdraw(actor, self.card['activity_id'], 'متوقف برای بازبینی')

    async def test_provider_failure_preserves_catalog_guide_and_enforces_retry(self):
        self.live_mode()
        self.provider.fail = True
        with self.assertLogs('uvicorn.error', 'WARNING') as logs:
            self.assertEqual((await self.generate('guide')).status_code, 202)
            self.assertEqual((await self.generate('image')).status_code, 202)
            chat = await self.client.post(self.path + '/chat', json=self.message)
        self.assertEqual(chat.status_code, 503)
        self.assertEqual(chat.json()['error']['code'], 'ASSISTANT_UNAVAILABLE')
        self.assertNotIn('private', ' '.join(logs.output) + chat.text)
        state = (await self.client.get(self.path)).json()
        self.assertEqual((state['guide_status'], state['guide']['source'], state['image_status']), ('failed', 'catalog', 'failed'))
        self.assertEqual(state['image_retry_after_seconds'], 120)
        self.assertEqual((await self.generate('image')).status_code, 200)
        self.assertEqual(len(self.provider.image_calls), 1)
        self.now += timedelta(minutes=2)
        self.provider.fail = False
        self.assertEqual((await self.generate('image')).status_code, 202)
        self.assertEqual((await self.client.get(self.path + '/image')).status_code, 200)

    async def test_live_chat_keeps_history_in_request_and_limits_repeated_calls(self):
        self.live_mode()
        messages = self.message['messages'] + [{'role': 'assistant', 'content': 'یک قدم کوچک بردار.'},
                                               {'role': 'user', 'content': 'بعدش چی کار کنم؟'}]
        for _ in range(10):
            response = await self.client.post(self.path + '/chat', json={'messages': messages})
            self.assertEqual(response.json()['source'], 'gapgpt')
            self.assertEqual(response.json()['revision_id'], self.revision_id)
        limited = await self.client.post(self.path + '/chat', json=self.message)
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.headers['Retry-After'], '60')
        self.assertEqual(len(self.provider.chat_calls), 10)
        self.assertEqual(self.provider.chat_calls[-1][1], messages)
        self.assertFalse(self.s.store.list(ASSETS))


class ActivityAssistantProviderTests(unittest.TestCase):
    def test_image_adapter_accepts_both_gapgpt_response_formats(self):
        result = SimpleNamespace(b64_json=IMAGE_B64, url=None)
        settings = Settings(gapgpt_api_key='test-only')
        adapter = GapAssistantProvider(settings)
        self.addCleanup(adapter.close)
        with patch.object(adapter.client.images, 'generate', return_value=SimpleNamespace(data=[result])) as generate:
            self.assertEqual(adapter.image(dict(title='عنوان تفریح', teaser='متن کوتاه',
                                                first_step='قدم اول', venue='home')), (IMAGE, 'image/png'))
            self.assertEqual(generate.call_args.kwargs['size'], '1024x1024')
            self.assertEqual(generate.call_args.kwargs['model'], 'gemini-2.5-flash-image')
            result.b64_json, result.url = None, 'https://api.gapgpt.app/generated/image.png'
            with patch('app.modules.activity_assistant.provider.download_image', return_value=IMAGE) as download:
                adapter.image(dict(title='عنوان تفریح', teaser='متن کوتاه', first_step='قدم اول', venue='home'))
                download.assert_called_once_with(result.url, settings.gapgpt_image_hosts)

    def test_guide_adapter_sends_catalog_as_data_and_validates_json(self):
        import json
        adapter = GapAssistantProvider(Settings(gapgpt_api_key='test-only'))
        self.addCleanup(adapter.close)
        result = SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=json.dumps(GUIDE)))
        with patch.object(adapter.client.chat.completions, 'create',
                          return_value=SimpleNamespace(choices=[result])) as create:
            self.assertEqual(adapter.guide({'title': 'عنوان'}).model_dump(), GUIDE)
            payload = create.call_args.kwargs
            self.assertEqual(payload['messages'][0]['role'], 'system')
            self.assertIn('عنوان', payload['messages'][1]['content'])
            result.message.content = json.dumps({**GUIDE, 'steps': ['https://example.test', 'قدم فارسی']})
            with self.assertRaises(ValueError):
                adapter.guide({'title': 'عنوان'})

    def test_provider_image_download_rejects_other_hosts_and_private_dns(self):
        hosts = ('cdn.provider.example',)
        with patch('socket.getaddrinfo') as dns:
            for url in ('http://cdn.provider.example/a', 'https://cdn.provider.example.other/a',
                        'https://127.0.0.1/a', 'https://cdn.provider.example:8443/a',
                        'https://name@cdn.provider.example/a'):
                with self.subTest(url=url), self.assertRaisesRegex(ValueError, 'image_host_not_allowed'):
                    download_image(url, hosts)
            dns.assert_not_called()
            dns.return_value = [(None, None, None, None, ('192.168.1.5', 443))]
            with patch('socket.create_connection') as connect, self.assertRaisesRegex(ValueError, 'image_address_not_public'):
                download_image('https://cdn.provider.example/a', hosts)
            connect.assert_not_called()

    def test_provider_download_uses_validated_tls_host_without_provider_credentials(self):
        host = 'cdn.provider.example'
        with (patch('socket.getaddrinfo', return_value=[(None, None, None, None, ('1.1.1.1', 443))]),
              patch('socket.create_connection') as connect,
              patch('ssl.create_default_context') as context,
              patch('http.client.HTTPSConnection') as http):
            connection = http.return_value
            response = connection.getresponse.return_value.__enter__.return_value
            response.status = 200
            response.getheader.side_effect = {'Content-Type': 'image/png', 'Content-Length': str(len(IMAGE))}.get
            response.read1.side_effect = [IMAGE, b'']
            self.assertEqual(download_image(f'https://{host}/image.png?sig=opaque', (host,)), IMAGE)
            self.assertEqual(connect.call_args.args[0], ('1.1.1.1', 443))
            self.assertEqual(context.return_value.wrap_socket.call_args.kwargs['server_hostname'], host)
            self.assertEqual(connection.request.call_args.args, ('GET', '/image.png?sig=opaque'))
            self.assertNotIn('Authorization', connection.request.call_args.kwargs['headers'])
            response.status = 302
            with self.assertRaisesRegex(ValueError, 'invalid_image_response'):
                download_image(f'https://{host}/image.png?sig=opaque', (host,))
            self.assertEqual(connection.request.call_count, 2)
