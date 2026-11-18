"""Exercise production cookies, container lifecycle and the source upload boundary."""
import asyncio
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

import httpx
from app.core.config import Settings
from app.core.values import utcnow
from app.main import create_app
from support import MemoryTestStore

ROOT = Path(__file__).resolve().parents[3]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f'scripts/{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


container = script('container')
packager = script('package-deploy')


class ContainerTests(unittest.TestCase):
    def test_web_waits_for_api_readiness_before_it_is_started(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api_marker, web_marker = root / 'api-ready', root / 'web-started'
            api_code = ('import pathlib,sys,time; time.sleep(.15); '
                        'pathlib.Path(sys.argv[1]).touch(); time.sleep(60)')
            web_code = ('import pathlib,sys,time; '
                        'assert pathlib.Path(sys.argv[1]).exists(); '
                        'pathlib.Path(sys.argv[2]).touch(); time.sleep(60)')
            commands = [('API', [sys.executable, '-c', api_code, str(api_marker)], ROOT, os.environ),
                        ('Web', [sys.executable, '-c', web_code, str(api_marker), str(web_marker)], ROOT, os.environ)]
            stop = threading.Event()
            def web_ready():
                if not web_marker.exists():
                    return False
                stop.set()
                return True
            result = container.supervise(commands, stop, web_ready, startup_timeout=3, shutdown_timeout=1,
                                         startup_checks={'API': api_marker.exists})
            self.assertEqual(result, 0)
            self.assertTrue(web_marker.exists())

    def test_api_failure_or_timeout_never_launches_web_and_reaps_the_api(self):
        for fails in (False, True):
            with self.subTest(fails=fails):
                spawn, children = subprocess.Popen, []
                def tracked_spawn(*args, **kwargs):
                    child = spawn(*args, **kwargs)
                    children.append(child)
                    return child
                code = 'raise SystemExit(2)' if fails else 'import time; time.sleep(60)'
                commands = [('API', [sys.executable, '-c', code], ROOT, os.environ),
                            ('Web', [sys.executable, '-c', 'raise AssertionError("must not start")'], ROOT, os.environ)]
                with patch.object(container.subprocess, 'Popen', side_effect=tracked_spawn), \
                        patch('builtins.print') as output:
                    result = container.supervise(commands, threading.Event(), lambda: self.fail('web probed before API ready'),
                        startup_timeout=.1, shutdown_timeout=1, startup_checks={'API': lambda: False})
                self.assertEqual(result, 1)
                self.assertEqual(len(children), 1)
                self.assertIsNotNone(children[0].poll())
                messages = ' '.join(str(call.args[0]) for call in output.call_args_list)
                self.assertIn('API exited' if fails else 'API startup readiness timed out', messages)

    def test_stop_during_api_startup_does_not_start_web(self):
        stop = threading.Event()
        timer = threading.Timer(.15, stop.set)
        spawn, children = subprocess.Popen, []
        def tracked_spawn(*args, **kwargs):
            child = spawn(*args, **kwargs)
            children.append(child)
            return child
        commands = [('API', [sys.executable, '-c', 'import time; time.sleep(60)'], ROOT, os.environ),
                    ('Web', [sys.executable, '-c', 'raise AssertionError("must not start")'], ROOT, os.environ)]
        timer.start()
        try:
            with patch.object(container.subprocess, 'Popen', side_effect=tracked_spawn):
                result = container.supervise(commands, stop, lambda: False, shutdown_timeout=1,
                    startup_checks={'API': lambda: False})
        finally:
            timer.cancel()
        self.assertEqual(result, 0)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())

    def test_healthcheck_does_not_proxy_through_web_until_api_is_ready(self):
        api = 'http://127.0.0.1:8000/api/v1/health/ready'
        public = 'http://127.0.0.1:3000/api/v1/health/ready'
        with patch.object(sys, 'argv', ['container.py', '--healthcheck']), \
                patch.dict(os.environ, {'PORT': '3000'}), \
                patch.object(container, 'is_ready', return_value=False) as check:
            self.assertEqual(container.main(), 1)
        check.assert_called_once_with(api)
        with patch.object(sys, 'argv', ['container.py', '--healthcheck']), \
                patch.dict(os.environ, {'PORT': '3000'}), \
                patch.object(container, 'is_ready', side_effect=[True, False]):
            self.assertEqual(container.main(), 1)
        with patch.object(sys, 'argv', ['container.py', '--healthcheck']), \
                patch.dict(os.environ, {'PORT': '3000'}), \
                patch.object(container, 'is_ready', side_effect=[True, True]) as check:
            self.assertEqual(container.main(), 0)
        self.assertEqual([call.args[0] for call in check.call_args_list], [api, public])

    def test_frontend_does_not_inherit_server_credentials(self):
        env = container.web_environment(dict(PATH='/usr/bin', PORT='4000', HOSTNAME='private',
            MONGODB_URI='secret', CSRF_HMAC_SECRET='secret', GAPGPT_API_KEY='secret',
            NEXT_PUBLIC_ACCIDENTAL_SECRET='secret', LIARA_TOKEN='secret'))
        self.assertEqual(env['PORT'], '4000')
        self.assertEqual(env['HOSTNAME'], '0.0.0.0')
        self.assertNotIn('secret', env.values())

    def test_unexpected_child_exit_stops_other_child_and_fails(self):
        sleeper = subprocess.Popen
        children = []
        def spawn(*args, **kwargs):
            child = sleeper(*args, **kwargs)
            children.append(child)
            return child
        commands = [('API', [sys.executable, '-c', 'import time; time.sleep(60)'], ROOT, os.environ),
                    ('Web', [sys.executable, '-c', 'raise SystemExit(0)'], ROOT, os.environ)]
        with patch.object(container.subprocess, 'Popen', side_effect=spawn):
            result = container.supervise(commands, threading.Event(), lambda: True, shutdown_timeout=1)
        self.assertEqual(result, 1)
        self.assertTrue(all(child.poll() is not None for child in children))

    def test_termination_and_readiness_timeout_reap_children(self):
        for terminate in (False, True):
            with self.subTest(terminate=terminate):
                stop = threading.Event()
                timer = threading.Timer(.15, stop.set) if terminate else None
                if timer:
                    timer.start()
                command = [('API', [sys.executable, '-c', 'import time; time.sleep(60)'], ROOT, os.environ)]
                spawn = subprocess.Popen
                children = []
                def tracked_spawn(*args, **kwargs):
                    child = spawn(*args, **kwargs)
                    children.append(child)
                    return child
                try:
                    with patch.object(container.subprocess, 'Popen', side_effect=tracked_spawn):
                        result = container.supervise(command, stop, lambda: False,
                            startup_timeout=.1, shutdown_timeout=1)
                finally:
                    if timer:
                        timer.cancel()
                self.assertEqual(result, 0 if terminate else 1)
                self.assertTrue(all(child.poll() is not None for child in children))

    def test_upload_contains_sources_and_excludes_secrets_and_builds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in packager.FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('source')
            forbidden = ('.env', 'apps/web/.env.production', 'apps/api/app/.env',
                         'apps/api/app/__pycache__/config.pyc', 'apps/api/app/secret.key',
                         'apps/web/node_modules/dependency.js', 'apps/web/.next/server.js')
            for name in forbidden:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('never upload')
            (root / 'apps/api/app/main.py').write_text('source')
            destination, _ = packager.package(root)
            with zipfile.ZipFile(destination) as archive:
                self.assertIn('Dockerfile', archive.namelist())
                self.assertIn('apps/api/app/main.py', archive.namelist())
                self.assertTrue(all(name not in archive.namelist() for name in forbidden))
                self.assertNotIn(b'never upload', b''.join(archive.read(n) for n in archive.namelist()))

    def test_checkout_package_includes_frontend_type_contracts(self):
        sources = {name for _, name in packager.deploy_files(ROOT)}
        self.assertTrue({
            'apps/web/types/index.ts',
            'apps/web/types/domain.ts',
            'apps/web/types/api.ts',
            'apps/web/types/admin.ts',
        }.issubset(sources))

    def test_operator_role_command_revokes_sessions_and_writes_audit_without_seeding(self):
        from app.cli import set_role
        from app.core.rate_limit import RateLimiter
        from app.core.schemas import Signup, Credentials
        from app.modules.identity.service import Identity
        settings = Settings(mongodb_uri='mongodb://public.example.test/app',
                            csrf_hmac_secret='test-only-secret-at-least-32-characters')
        store = MemoryTestStore()
        identity = Identity(store, settings, utcnow, RateLimiter(store, utcnow))
        identity.signup(Signup(email='operator@example.test', password='a sufficiently long password',
                              adult_confirmed=True), '127.0.0.1')
        identity.login(Credentials(email='operator@example.test', password='a sufficiently long password'),
                       '127.0.0.1', None)
        self.assertEqual(len(store.list('auth_sessions')), 1)
        with patch('app.core.config.Settings.load', return_value=settings), \
                patch('app.core.storage.create_store', return_value=store), patch.object(store, 'close') as close:
            set_role('operator@example.test', 'admin')
        close.assert_called_once()
        self.assertEqual(identity.by_email('operator@example.test')['role'], 'admin')
        self.assertEqual(store.list('auth_sessions'), [])
        self.assertEqual(store.list('admin_audit')[0]['action'], 'role_changed')
        self.assertEqual(store.list('activities'), [])


class ProductionApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_https_session_csrf_and_exact_origin(self):
        # Keep restricted ASGI runners responsive while sync routes run in threads.
        async def tick():
            while True:
                await asyncio.sleep(.01)
        ticker = asyncio.create_task(tick())
        origin = 'https://moodigo.ir'
        with patch('app.core.config.load_environment', return_value={
                'APP_ENV': 'production', 'APP_ORIGIN': origin + '/', 'DEMO_CONTENT': 'false',
                'MONGODB_URI': 'mongodb://public.example.test/app',
                'CSRF_HMAC_SECRET': 'production-test-secret-at-least-32-characters'}):
            settings = Settings.load()
        app = create_app(settings, store_factory=lambda _: MemoryTestStore())
        try:
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                             base_url=origin, headers={'Origin': origin}) as client:
                    response = await client.get('/api/v1/auth/csrf')
                    self.assertIn('Secure', response.headers['set-cookie'])
                    client.headers['X-CSRF-Token'] = response.json()['csrf_token']
                    account = dict(email='production@example.test', password='a sufficiently long password',
                                   adult_confirmed=True)
                    self.assertEqual((await client.post('/api/v1/auth/signup', json=account)).status_code, 202)
                    response = await client.post('/api/v1/auth/login', json={k: account[k] for k in ('email', 'password')})
                    self.assertEqual(response.status_code, 200)
                    cookie = next(c for c in response.headers.get_list('set-cookie') if c.startswith('__Host-'))
                    for flag in ('Secure', 'HttpOnly', 'SameSite=lax', 'Path=/'):
                        self.assertIn(flag, cookie)
                    self.assertNotIn('Domain=', cookie)
                    client.headers['X-CSRF-Token'] = response.json()['csrf_token']
                    self.assertEqual((await client.get('/api/v1/me')).status_code, 200)
                    for bad_origin in ('https://attacker.test', 'http://127.0.0.1:3000',
                                       'https://shadophena.liara.run', 'http://moodigo.ir',
                                       'https://moodigo.ir.attacker.test', 'https://moodigo.ir:444', 'null', ''):
                        denied = await client.post('/api/v1/auth/logout', json={}, headers={
                            'Origin': bad_origin, 'X-Forwarded-Host': 'moodigo.ir',
                            'X-Forwarded-Proto': 'https'})
                        self.assertEqual(denied.status_code, 403)
                        self.assertNotIn('آدرس محلی', denied.json()['error']['message'])
                    # A valid page origin still requires the session-bound CSRF token.
                    denied = await client.post('/api/v1/auth/logout', json={}, headers={'X-CSRF-Token': 'wrong'})
                    self.assertEqual(denied.status_code, 403)
                    self.assertEqual((await client.post('/api/v1/auth/logout', json={})).status_code, 204)
                    self.assertEqual((await client.get('/api/v1/me')).status_code, 401)
        finally:
            ticker.cancel()
