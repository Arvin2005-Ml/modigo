"""Shared connection settings and credential-free operator diagnostics.

Never emit driver exception text: it can contain URIs or server documents.
Diagnostics issue only ping, hello and a projected read; no indexes or writes.
"""
import socket
import ssl

from app.core.config import load_environment, validate_mongodb_uri
from app.core.storage import StorageUnavailable


def create_mongo_client(uri):
    from pymongo import MongoClient
    return MongoClient(uri, appname='funilo-api', directConnection=True,
        serverSelectionTimeoutMS=5000, connectTimeoutMS=5000,
        socketTimeoutMS=10000, maxPoolSize=20, timeoutMS=15000)


def mongo_failure(exc, stage):
    """Map codes/types and fixed driver phrases to a finite, safe message.

Some network causes are retained only in PyMongo's message. That text is
examined for fixed signatures locally, never interpolated into the output.
"""
    stage = stage if stage in ('configuration', 'connect', 'ping', 'hello', 'indexes', 'transaction', 'read') else 'operation'
    pending, seen, errors = [exc], set(), []
    while pending and len(seen) < 32:
        error = pending.pop()
        if not isinstance(error, BaseException) or id(error) in seen:
            continue
        seen.add(id(error))
        errors.append(error)
        pending.extend((error.__cause__, error.__context__))
        nested = getattr(error, 'errors', None)
        if isinstance(nested, dict):
            pending.extend(list(nested.values())[:32])
        elif isinstance(nested, (list, tuple)):
            pending.extend(nested[:32])
    codes = [code for error in errors if type(code := getattr(error, 'code', None)) is int]
    names = {base.__name__ for error in errors for base in type(error).__mro__}
    text = ' '.join(str(error).lower() for error in errors)
    code = next((value for value in codes if value in (18, 13, 20, 303, 40573)), codes[0] if codes else None)
    if code == 18:
        category, hint = 'AUTHENTICATION_FAILED', 'Verify the username, password and authSource in the Liara runtime MONGODB_URI (the supplied account uses authSource=admin).'
    elif code == 13:
        category, hint = 'PERMISSION_DENIED', 'The MongoDB account lacks permission for this operation; check its application database roles.'
    elif code in (20, 303, 40573):
        category, hint = 'TRANSACTION_UNSUPPORTED', 'Use a writable replica-set primary with transaction support.'
    elif any(isinstance(error, ssl.SSLError) for error in errors) or any(token in text for token in ('ssl handshake', 'certificate_verify_failed', 'certificate verify failed', 'tls handshake')):
        category, hint = 'TLS_FAILED', 'Check the endpoint TLS requirements and trusted CA certificates; keep certificate validation enabled.'
    elif any(isinstance(error, socket.gaierror) for error in errors) or any(token in text for token in ('name or service not known', 'temporary failure in name resolution', 'getaddrinfo failed', 'nodename nor servname')):
        category, hint = 'DNS_FAILED', 'The runtime cannot resolve the configured public MongoDB hostname; check DNS and database availability.'
    elif any(isinstance(error, ConnectionRefusedError) for error in errors) or 'connection refused' in text:
        category, hint = 'CONNECTION_REFUSED', 'The configured public host/port refused TCP; check the database is running and its public port is enabled.'
    elif 'ConfigurationError' in names or 'InvalidURI' in names or isinstance(exc, (ValueError, TypeError)):
        category, hint = 'CONFIGURATION_INVALID', 'Check the MongoDB URI options, explicit application database and driver/server compatibility.'
    elif any(isinstance(error, TimeoutError) for error in errors) or names.intersection(('ServerSelectionTimeoutError', 'NetworkTimeout', 'ConnectionFailure')):
        category, hint = 'NETWORK_UNAVAILABLE', 'No usable MongoDB connection; check the public host/port, network access and database status.'
    else:
        category, hint = 'OPERATION_FAILED', 'Check database status and permissions for this startup stage.'
    suffix = f', code={code}' if code is not None else ''
    return StorageUnavailable(f'MongoDB {category} (stage={stage}{suffix}): {hint}')


def diagnose_db(environment=None, *, write=print, client_factory=None):
    """Return exit status; never create application services or a job runner."""
    client, stage = None, 'configuration'
    try:
        environment = load_environment() if environment is None else environment
        uri = environment.get('MONGODB_URI', '').strip()
        validate_mongodb_uri(uri)
        stage = 'connect'
        client = (client_factory or create_mongo_client)(uri)
        database = client.get_default_database()
        if database.name in ('admin', 'config', 'local'):
            raise ValueError('An application database is required')
        stage = 'ping'
        client.admin.command('ping')
        write('MongoDB ping: OK (configured public endpoint; direct connection)')
        stage = 'hello'
        hello = client.admin.command('hello')
        if not hello.get('setName') or not hello.get('isWritablePrimary'):
            write('MongoDB TRANSACTION_UNSUPPORTED (stage=hello): a writable replica-set primary is required.')
            return 1
        write('MongoDB replica-set primary: OK')
        stage = 'read'
        database['_funilo_meta'].find_one({'_id': 'atomic_guard'}, {'_id': 1})
        write('MongoDB read: OK; no data changed. Startup must still verify indexes, writes and transaction commit.')
        return 0
    except ImportError:
        write('Install the locked API dependencies, including PyMongo')
        return 1
    except Exception as exc:
        write(str(mongo_failure(exc, stage)))
        return 1
    finally:
        if client is not None:
            client.close()
