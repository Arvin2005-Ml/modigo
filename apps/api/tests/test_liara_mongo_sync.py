"""Operator credential repair preserves other runtime secrets and verifies readback."""
import importlib.util
import io
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('liara_mongo_sync', ROOT / 'scripts/sync-liara-mongo.py')
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)
URI = 'mongodb://root:test-only-password@olympus.liara.cloud:34468/my-app?authSource=admin'


class LiaraMongoSyncTests(unittest.TestCase):
    def test_file_credentials_override_stale_operator_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('MONGODB_URI=' + URI + '\n')
            with patch.dict('os.environ', {'MONGODB_URI': 'stale-runtime-value'}):
                self.assertEqual(operator.source_uri(path), URI)

    def test_rejects_private_endpoint_missing_auth_source_and_placeholder_without_disclosure(self):
        for uri in (URI.replace('olympus.liara.cloud:34468', 'shadophen:27017'),
                    URI.replace('?authSource=admin', ''), URI.replace('test-only-password', 'YOUR_PASSWORD')):
            with self.subTest(uri=uri), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / '.env'
                path.write_text('MONGODB_URI=' + uri)
                with self.assertRaises(operator.ConfigurationError) as caught:
                    operator.source_uri(path)
                self.assertNotIn(uri, str(caught.exception))
                self.assertNotIn('test-only-password', str(caught.exception))

    def test_update_retains_other_variables_and_removes_duplicate_old_uris(self):
        other = [{'key': 'CSRF_HMAC_SECRET', 'value': 'keep-the-session-secret'},
                 {'key': 'APP_ORIGIN', 'value': 'https://funilo.example.test'}]
        old = other + [{'key': 'MONGODB_URI', 'value': 'stale'}, {'key': 'MONGODB_URI', 'value': 'stale2'}]
        api, messages = Mock(), []
        api.variables.side_effect = [old, other + [{'key': 'MONGODB_URI', 'value': URI}]]
        self.assertEqual(operator.sync(api, 'shadophena', URI, write=messages.append), 0)
        api.request.assert_called_once_with('v1/projects/update-envs', {
            'project': 'shadophena', 'variables': other + [{'key': 'MONGODB_URI', 'value': URI}]})
        self.assertEqual(api.variables.call_count, 2)
        for secret in (URI, 'test-only-password', 'keep-the-session-secret'):
            self.assertNotIn(secret, '\n'.join(messages))

    def test_matching_runtime_does_not_restart_and_check_mode_does_not_mutate(self):
        for rows, check, expected in [([{'key': 'MONGODB_URI', 'value': URI}], False, 0),
                                      ([{'key': 'MONGODB_URI', 'value': 'stale'}], True, 1)]:
            api = Mock()
            api.variables.return_value = rows
            self.assertEqual(operator.sync(api, 'shadophena', URI, check=check, write=lambda _: None), expected)
            api.request.assert_not_called()

    def test_failed_readback_does_not_report_success(self):
        api = Mock()
        api.variables.return_value = []
        messages = []
        with self.assertRaises(operator.ConfigurationError):
            operator.sync(api, 'shadophena', URI, write=messages.append)
        self.assertNotIn('verified', '\n'.join(messages))

    def test_malformed_remote_variables_are_never_overwritten(self):
        api = operator.Liara('private-token')
        for response in ({}, {'project': {'envs': None}}, {'project': {'envs': [{'key': 'secret'}]}}):
            with self.subTest(response=response), patch.object(api, 'request', return_value=response):
                with self.assertRaises(operator.ConfigurationError):
                    api.variables('shadophena')

    def test_dns_and_http_errors_are_safe_and_nonzero(self):
        api = operator.Liara('private-token')
        for error in (URLError(socket.gaierror(-3, URI)),
                      HTTPError(URI, 401, 'private-token', {}, io.BytesIO(URI.encode()))):
            with self.subTest(kind=type(error).__name__), patch.object(api.opener, 'open', side_effect=error):
                with self.assertRaises(operator.ConfigurationError) as caught:
                    api.request('v1/projects/shadophena')
                for secret in (URI, 'private-token', 'test-only-password'):
                    self.assertNotIn(secret, str(caught.exception))

    def test_update_does_not_require_json_response_but_get_does(self):
        api = operator.Liara('private-token')
        response = Mock()
        response.__enter__ = Mock(return_value=io.BytesIO(b''))
        response.__exit__ = Mock(return_value=False)
        with patch.object(api.opener, 'open', return_value=response) as opened:
            self.assertIsNone(api.request('v1/projects/update-envs', {'project': 'shadophena', 'variables': []}))
            request = opened.call_args.args[0]
            self.assertEqual(request.get_method(), 'POST')
            self.assertEqual(request.full_url, 'https://api.liara.ir/v1/projects/update-envs')
        with patch.object(api.opener, 'open', return_value=response):
            with self.assertRaises(operator.ConfigurationError):
                api.variables('shadophena')

    def test_redirect_does_not_forward_operator_token(self):
        handler = operator.NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, '', {}, 'https://untrusted.example/'))
