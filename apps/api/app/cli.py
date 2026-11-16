"""Mongo-backed server console and trusted operator commands for a container shell.

Commands: serve | diagnose-db | check-db | role email user/editor/admin.
No arguments starts the dev console.
No role-changing HTTP route, default credentials or second application worker.
"""
import shlex
import sys
import threading
import time


def set_role(email, role):
    from app.core.config import Settings
    from app.core.storage import create_store
    from app.core.rate_limit import RateLimiter
    from app.core.values import utcnow
    from app.modules.identity.service import Identity
    settings = Settings.load()
    store = create_store({'DATA_BACKEND': settings.data_backend, 'MONGODB_URI': settings.mongodb_uri})
    try:
        Identity(store, settings, utcnow, RateLimiter(store, utcnow)).promote(email, role)
    finally:
        store.close()


def main():
    if sys.argv[1:] == ['diagnose-db']:
        from app.core.mongo_connection import diagnose_db
        raise SystemExit(diagnose_db())
    if sys.argv[1:] == ['serve']:
        print('API: importing the ASGI application', flush=True)
        import uvicorn
        from app.main import create_app
        print('API: starting one Uvicorn worker on 127.0.0.1:8000', flush=True)
        uvicorn.run(create_app, factory=True, host='127.0.0.1', port=8000,
                    workers=1, access_log=False, proxy_headers=False,
                    timeout_graceful_shutdown=15)
        return
    if len(sys.argv) == 4 and sys.argv[1] == 'role':
        from app.core.errors import DomainError
        from app.core.storage import StorageUnavailable
        try:
            set_role(sys.argv[2], sys.argv[3])
        except (DomainError, StorageUnavailable, ValueError):
            print('Role could not be changed; check settings, account and role', file=sys.stderr)
            raise SystemExit(1)
        print('Role changed; previous sessions revoked')
        return
    if sys.argv[1:] == ['check-db']:
        from app.core.config import Settings
        from app.core.storage import create_store, StorageUnavailable
        try:
            settings = Settings.load()
            store = create_store({'DATA_BACKEND': settings.data_backend, 'MONGODB_URI': settings.mongodb_uri})
            try:
                store.ping()
                print('MongoDB ready: connection, indexes and transaction commit verified')
            finally:
                store.close()
        except (StorageUnavailable, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1)
        return
    if sys.argv[1:]:
        print('Usage: python -m app.cli [serve | diagnose-db | check-db | role EMAIL user/editor/admin]', file=sys.stderr)
        raise SystemExit(2)
    import uvicorn
    from app.main import create_app
    app = create_app()
    def console():
        while not hasattr(app.state, 'services'):
            time.sleep(.05)
        print('Local operator console: mailbox EMAIL | role EMAIL user/editor/admin | resume-provider', flush=True)
        while True:
            try:
                parts = shlex.split(input())
            except EOFError:
                return
            except ValueError:
                print('Invalid command', flush=True)
                continue
            try:
                s = app.state.services
                if len(parts) == 2 and parts[0] == 'mailbox':
                    with s.store.atomic():
                        messages = [m for m in s.identity.mailbox if m['email'] == parts[1].lower()]
                        for message in messages:
                            print(message['purpose'], message['link'], flush=True)
                        if not messages:
                            print('No local messages', flush=True)
                elif len(parts) == 3 and parts[0] == 'role':
                    s.identity.promote(parts[1], parts[2])
                    print('Role changed; previous sessions revoked', flush=True)
                elif parts == ['resume-provider']:
                    s.jobs.resume()
                    print('Content provider queue resumed', flush=True)
                else:
                    print('mailbox EMAIL | role EMAIL user/editor/admin | resume-provider', flush=True)
            except Exception:
                print('Command could not be applied; check account and role', flush=True)
    threading.Thread(target=console, name='local-operator', daemon=True).start()
    uvicorn.run(app, host='127.0.0.1', port=8000, workers=1, access_log=False)


if __name__ == '__main__':
    main()
