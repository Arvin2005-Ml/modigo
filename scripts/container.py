"""Run one API with its worker and one standalone Next server in a container."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
OPENER = build_opener(ProxyHandler({}))


def public_port(environ):
    try:
        port = int(environ.get('PORT', '3000'))
    except ValueError:
        raise ValueError('PORT must be an integer') from None
    if not 1024 <= port <= 65535 or port == 8000:
        raise ValueError('PORT must be 1024..65535 and different from the internal API port 8000')
    return port


def web_environment(environ):
    # The frontend needs no database, session or model credentials, even server-side.
    allowed = ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TZ')
    result = {key: environ[key] for key in allowed if key in environ}
    result.update(NODE_ENV='production', NEXT_TELEMETRY_DISABLED='1',
                  HOSTNAME='0.0.0.0', PORT=str(public_port(environ)))
    return result


def is_ready(url):
    try:
        with OPENER.open(url, timeout=2) as response:
            payload = json.load(response)
            return response.status == 200 and isinstance(payload, dict) and payload.get('status') == 'ready'
    except (URLError, OSError, ValueError):
        return False


def stop_children(children, timeout):
    # Signal process groups as well as direct children, then reap the children.
    for _, child in children:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + timeout
    for _, child in children:
        try:
            child.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    for _, child in children:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()


def exited_child(children):
    for name, child in children:
        if child.poll() is not None:
            print(f'{name} exited (code {child.returncode}); stopping container', file=sys.stderr, flush=True)
            return True
    return False


def wait_until_ready(children, stop, check, name, deadline):
    print(f'Waiting for {name} readiness', flush=True)
    while not stop.is_set():
        if exited_child(children):
            return False
        if check():
            print(f'{name} ready', flush=True)
            return True
        if time.monotonic() >= deadline:
            print(f'{name} startup readiness timed out; check preceding API startup logs', file=sys.stderr, flush=True)
            return False
        stop.wait(.25)
    return False


def supervise(commands, stop, readiness, startup_timeout=180, shutdown_timeout=20, startup_checks=None):
    children = []
    startup_checks = startup_checks or {}
    deadline = time.monotonic() + startup_timeout
    try:
        for name, command, cwd, environ in commands:
            if stop.is_set():
                return 0
            print(f'Starting {name}', flush=True)
            children.append((name, subprocess.Popen(command, cwd=cwd, env=environ, start_new_session=True)))
            if name in startup_checks and not wait_until_ready(
                    children, stop, startup_checks[name], name, deadline):
                return 0 if stop.is_set() else 1
        if not wait_until_ready(children, stop, readiness, 'Web/API/MongoDB', deadline):
            return 0 if stop.is_set() else 1
        print('Funilo ready: web, API and MongoDB', flush=True)
        while not stop.is_set():
            if exited_child(children):
                return 1
            stop.wait(.25)
        return 0
    finally:
        stop_children(children, shutdown_timeout)


def main():
    try:
        port = public_port(os.environ)
        api_url = 'http://127.0.0.1:8000/api/v1/health/ready'
        health_url = f'http://127.0.0.1:{port}/api/v1/health/ready'
        if sys.argv[1:] == ['--healthcheck']:
            # Do not send a request through Next while its upstream is unavailable.
            return 0 if is_ready(api_url) and is_ready(health_url) else 1
        if sys.argv[1:]:
            raise ValueError('Usage: container.py [--healthcheck]')
        from app.core.config import Settings
        print('Funilo launcher: validating server configuration', flush=True)
        Settings.load()  # Fail before either server starts; never print credentials.
        stop = threading.Event()
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, lambda *_: stop.set())
        api_env = dict(os.environ, PYTHONPATH=str(ROOT / 'apps/api'), PYTHONUNBUFFERED='1')
        commands = [
            ('API', [sys.executable, '-u', '-m', 'app.cli', 'serve'], ROOT, api_env),
            ('Web', ['node', 'server.js'], ROOT / 'apps/web', web_environment(os.environ)),
        ]
        return supervise(commands, stop, lambda: is_ready(health_url),
                         startup_checks={'API': lambda: is_ready(api_url)})
    except (ValueError, OSError):
        print('Container could not start; verify APP_ORIGIN, MONGODB_URI, CSRF_HMAC_SECRET and installed files', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
