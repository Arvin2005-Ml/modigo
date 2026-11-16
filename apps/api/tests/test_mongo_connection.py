"""Offline diagnostics tests; injected clients do not prove a live connection."""
import io
import socket
import ssl
import sys
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from app.core.config import validate_mongodb_uri
from app.core.mongo_connection import create_mongo_client, diagnose_db, mongo_failure

URI = 'mongodb://user:private-password@public.example.test:34468/my-app?authSource=admin'


def driver_error(code=None, message=URI):
    # Only documented exception fields are needed by the safe formatter.
    error = Exception(message)
    error.code = code
    return error


class MongoConnectionTests(unittest.TestCase):
    def test_diagnostic_and_runtime_share_bounded_direct_public_connection_options(self):
        factory = Mock()
        with patch.dict(sys.modules, {'pymongo': SimpleNamespace(MongoClient=factory)}):
            create_mongo_client(URI)
        factory.assert_called_once_with(URI, appname='funilo-api', directConnection=True,
            serverSelectionTimeoutMS=5000, connectTimeoutMS=5000,
            socketTimeoutMS=10000, maxPoolSize=20, timeoutMS=15000)

    def test_error_categories_preserve_codes_without_echoing_driver_details(self):
        cases = [(driver_error(18), 'AUTHENTICATION_FAILED', 'code=18'),
                 (driver_error(13), 'PERMISSION_DENIED', 'code=13'),
                 (driver_error(20), 'TRANSACTION_UNSUPPORTED', 'code=20'),
                 (driver_error(303), 'TRANSACTION_UNSUPPORTED', 'code=303'),
                 (driver_error(40573), 'TRANSACTION_UNSUPPORTED', 'code=40573'),
                 (ssl.SSLError(URI), 'TLS_FAILED', ''),
                 (socket.gaierror(-3, URI), 'DNS_FAILED', ''),
                 (ConnectionRefusedError(URI), 'CONNECTION_REFUSED', ''),
                 (TimeoutError(URI), 'NETWORK_UNAVAILABLE', ''),
                 (ValueError(URI), 'CONFIGURATION_INVALID', ''),
                 (driver_error(999), 'OPERATION_FAILED', 'code=999')]
        for error, category, code in cases:
            with self.subTest(category=category):
                message = str(mongo_failure(error, 'ping'))
                self.assertIn(category, message)
                self.assertIn('stage=ping', message)
                self.assertIn(code, message)
                for secret in (URI, 'private-password', 'public.example.test'):
                    self.assertNotIn(secret, message)

    def test_wrapped_network_errors_and_text_signatures_are_safely_classified(self):
        for text, category in [('SSL handshake failed', 'TLS_FAILED'),
                               ('Temporary failure in name resolution', 'DNS_FAILED'),
                               ('Connection refused', 'CONNECTION_REFUSED')]:
            error = driver_error(message=text + ' ' + URI)
            with self.subTest(category=category):
                result = str(mongo_failure(error, 'connect'))
                self.assertIn(category, result)
                self.assertNotIn(URI, result)
        outer = driver_error()
        outer.errors = {'private-address': ConnectionRefusedError(URI)}
        outer.__cause__ = outer  # A cycle must terminate without leaking keys.
        self.assertIn('CONNECTION_REFUSED', str(mongo_failure(outer, URI)))
        self.assertNotIn(URI, str(mongo_failure(outer, URI)))
        self.assertNotIn('private-address', str(mongo_failure(outer, URI)))

    def client(self, *, primary=True):
        collection = SimpleNamespace(find_one=Mock(return_value=None))
        database = {'_funilo_meta': collection}
        class Database(dict):
            name = 'my-app'
        client = SimpleNamespace(admin=SimpleNamespace(command=Mock(side_effect=[
                {'ok': 1}, {'setName': 'private-replica-name', 'isWritablePrimary': primary}])),
            get_default_database=Mock(return_value=Database(database)), close=Mock())
        return client, collection

    def test_diagnostic_uses_only_read_commands_and_closes_client(self):
        client, collection = self.client()
        messages, factory = [], Mock(return_value=client)
        result = diagnose_db({'MONGODB_URI': URI}, write=messages.append, client_factory=factory)
        self.assertEqual(result, 0)
        factory.assert_called_once_with(URI)
        self.assertEqual(client.admin.command.call_args_list, [call('ping'), call('hello')])
        collection.find_one.assert_called_once_with({'_id': 'atomic_guard'}, {'_id': 1})
        client.close.assert_called_once_with()
        output = '\n'.join(messages)
        self.assertIn('Startup must still verify indexes, writes and transaction commit', output)
        self.assertNotIn('private-replica-name', output)
        self.assertNotIn('private-password', output)

    def test_auth_failure_stops_probes_and_identifies_runtime_credentials(self):
        client, collection = self.client()
        client.admin.command.side_effect = driver_error(18)
        messages = []
        self.assertEqual(diagnose_db({'MONGODB_URI': URI}, write=messages.append,
                                    client_factory=lambda uri: client), 1)
        client.admin.command.assert_called_once_with('ping')
        collection.find_one.assert_not_called()
        client.close.assert_called_once_with()
        self.assertIn('AUTHENTICATION_FAILED (stage=ping, code=18)', messages[0])
        self.assertIn('Liara runtime MONGODB_URI', messages[0])
        self.assertNotIn('private-password', messages[0])

    def test_standalone_or_secondary_is_reported_without_application_writes(self):
        for hello in ({'isWritablePrimary': True}, {'setName': 'rs', 'isWritablePrimary': False}):
            with self.subTest(hello=hello):
                client, collection = self.client()
                client.admin.command.side_effect = [{'ok': 1}, hello]
                messages = []
                self.assertEqual(diagnose_db({'MONGODB_URI': URI}, write=messages.append,
                                            client_factory=lambda uri: client), 1)
                self.assertIn('TRANSACTION_UNSUPPORTED', messages[-1])
                collection.find_one.assert_not_called()
                client.close.assert_called_once_with()

    def test_read_permission_failure_is_reported_at_the_read_stage(self):
        client, collection = self.client()
        collection.find_one.side_effect = driver_error(13)
        messages = []
        self.assertEqual(diagnose_db({'MONGODB_URI': URI}, write=messages.append,
                                    client_factory=lambda uri: client), 1)
        self.assertIn('PERMISSION_DENIED (stage=read, code=13)', messages[-1])
        client.close.assert_called_once_with()

    def test_invalid_or_private_uri_fails_before_creating_a_client(self):
        for uri in ('', 'mongodb://localhost/my-app', 'mongodb://shadophen/my-app',
                    'mongodb://user:private-password@public.example.test:private-password/my-app'):
            with self.subTest(uri=uri):
                factory, messages = Mock(), []
                self.assertEqual(diagnose_db({'MONGODB_URI': uri}, write=messages.append,
                                            client_factory=factory), 1)
                factory.assert_not_called()
                self.assertNotIn('private-password', '\n'.join(messages))
        with self.assertRaises(ValueError) as caught:
            validate_mongodb_uri('mongodb://user:private-password@public.example.test:private-password/my-app')
        self.assertNotIn('private-password', str(caught.exception))

    def test_diagnostic_cli_does_not_construct_the_application_or_require_csrf(self):
        from app import cli
        output = io.StringIO()
        with patch.object(sys, 'argv', ['app.cli', 'diagnose-db']), \
                patch('app.core.mongo_connection.load_environment', return_value={'MONGODB_URI': URI}), \
                patch('app.core.mongo_connection.create_mongo_client', side_effect=driver_error(18)), \
                patch('app.core.config.Settings.load', side_effect=AssertionError('unrelated app settings')), \
                patch('app.core.storage.create_store', side_effect=AssertionError('must not initialize or write')), \
                redirect_stdout(output), self.assertRaises(SystemExit) as caught:
            cli.main()
        self.assertEqual(caught.exception.code, 1)
        self.assertIn('AUTHENTICATION_FAILED', output.getvalue())
        self.assertNotIn('private-password', output.getvalue())
