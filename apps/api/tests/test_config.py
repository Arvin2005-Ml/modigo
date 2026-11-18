import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from app.core.config import Settings, load_environment

URI = 'mongodb://user:private-password@public.example.test:34468/my-app?authSource=admin'
SECRET = 'private-csrf-secret-with-at-least-32-characters'


class ConfigurationTests(unittest.TestCase):
    def settings(self, **changes):
        return replace(Settings(mongodb_uri=URI, csrf_hmac_secret=SECRET), **changes)

    def test_mongo_is_the_only_runtime_backend(self):
        self.settings().validate()
        for backend in ('mock', 'memory', ''):
            with self.subTest(backend=backend), self.assertRaises(ValueError):
                self.settings(data_backend=backend).validate()

    def test_database_and_stable_csrf_secret_are_required(self):
        for changes in ({'mongodb_uri': ''}, {'mongodb_uri': 'mongodb://public.example.test/'},
                        {'csrf_hmac_secret': ''}, {'csrf_hmac_secret': 'short'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.settings(**changes).validate()

    def test_local_or_private_db_hosts_are_rejected(self):
        for host in ('localhost', '127.0.0.1', '[::1]', 'shadophen'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                self.settings(mongodb_uri=f'mongodb://{host}:27017/my-app').validate()

    def test_settings_repr_does_not_expose_secrets(self):
        for secret in (URI, 'private-password', SECRET):
            self.assertNotIn(secret, repr(self.settings()))

    def test_production_requires_https_and_an_exact_public_origin(self):
        settings = self.settings(environment='production', app_origin='https://funilo.example.test')
        settings.validate()
        self.assertTrue(settings.secure_cookies)
        self.assertEqual(settings.session_cookie, '__Host-funilo_session')
        self.assertEqual(settings.allowed_origins, ['https://funilo.example.test'])
        for origin in ('http://funilo.example.test', 'https://localhost', 'https://127.0.0.1',
                       'https://funilo.example.test/', 'https://funilo.example.test/path'):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                self.settings(environment='production', app_origin=origin).validate()
        with self.assertRaises(ValueError):
            self.settings(environment='prodution').validate()

    def test_production_environment_defaults_to_the_owner_domain(self):
        environment = {'APP_ENV': 'production', 'MONGODB_URI': URI, 'CSRF_HMAC_SECRET': SECRET}
        with patch('app.core.config.load_environment', return_value=environment):
            settings = Settings.load()
        self.assertEqual(settings.app_origin, 'https://moodigo.ir')
        self.assertEqual(settings.allowed_origins, ['https://moodigo.ir'])
        self.assertTrue(settings.secure_cookies)
        environment['APP_ENV'] = 'development'
        with patch('app.core.config.load_environment', return_value=environment):
            self.assertEqual(Settings.load().app_origin, 'http://127.0.0.1:3000')

    def test_environment_origin_is_canonicalized_to_the_browser_origin(self):
        for value in ('https://shadophena.liara.run/', '  https://shadophena.liara.run  ',
                      'https://SHADOPHENA.liara.run:443/'):
            with self.subTest(value=value), patch('app.core.config.load_environment', return_value={
                    'APP_ENV': 'production', 'APP_ORIGIN': value,
                    'MONGODB_URI': URI, 'CSRF_HMAC_SECRET': SECRET}):
                settings = Settings.load()
                self.assertEqual(settings.app_origin, 'https://shadophena.liara.run')
                self.assertEqual(settings.allowed_origins, ['https://shadophena.liara.run'])

    def test_origin_normalization_rejects_paths_credentials_and_invalid_ports(self):
        for value in ('https://shadophena.liara.run/path', 'https://shadophena.liara.run//',
                      'https://shadophena.liara.run?x=1', 'https://shadophena.liara.run#fragment',
                      'https://:private-password@shadophena.liara.run',
                      'https://shadophena.liara.run:private-password'):
            with self.subTest(value=value), patch('app.core.config.load_environment', return_value={
                    'APP_ENV': 'production', 'APP_ORIGIN': value,
                    'MONGODB_URI': URI, 'CSRF_HMAC_SECRET': SECRET}):
                with self.assertRaises(ValueError) as caught:
                    Settings.load()
                self.assertNotIn('private-password', str(caught.exception))

    def test_dotenv_is_not_executed_and_environment_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('MONGODB_URI="' + URI + '"\nAPP_ORIGIN=http://localhost:3000\n'
                            'EMPTY=\nLITERAL=\'$(never-execute)\'\n')
            loaded = load_environment(path, {'APP_ORIGIN': 'http://127.0.0.1:3000'})
            self.assertEqual(loaded['MONGODB_URI'], URI)
            self.assertEqual(loaded['APP_ORIGIN'], 'http://127.0.0.1:3000')
            self.assertEqual(loaded['LITERAL'], '$(never-execute)')
            self.assertEqual(loaded['EMPTY'], '')

    def test_invalid_dotenv_error_does_not_echo_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('MONGODB_URI="private-password\n')
            with self.assertRaises(ValueError) as caught:
                load_environment(path, {})
            self.assertNotIn('private-password', str(caught.exception))

    def test_main_import_does_not_load_credentials_or_connect(self):
        import importlib
        import app.main
        with patch('app.core.config.Settings.load', side_effect=AssertionError('startup only')):
            importlib.reload(app.main)
