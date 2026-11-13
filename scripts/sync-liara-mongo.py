"""Apply the server .env Mongo URI to Liara runtime; never print credentials.

Uses the same HTTPS endpoints as the installed official Liara CLI. Only the
MONGODB_URI key is changed; the complete set of other runtime keys is retained.
An environment update can restart the app. No build or deployment is needed.
"""
import argparse
import hmac
import json
import os
from pathlib import Path
import re
import socket
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/api'))
from app.core.config import load_environment, validate_mongodb_uri


class ConfigurationError(RuntimeError):
    """Fixed operator-facing text without remote bodies or credentials."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def source_uri(path):
    # Explicitly choose the file: a stale shell MONGODB_URI must not override it.
    try:
        uri = load_environment(path, overrides={}).get('MONGODB_URI', '').strip()
        validate_mongodb_uri(uri)
        parsed = urlsplit(uri)
        password = unquote(parsed.password or '')
        valid = (parsed.hostname == 'olympus.liara.cloud' and parsed.port == 34468
                 and parsed.path == '/my-app' and unquote(parsed.username or '') == 'root'
                 and parse_qs(parsed.query).get('authSource') == ['admin']
                 and password and password == password.strip()
                 and password.upper() not in ('YOUR_PASSWORD', 'PASSWORD', 'REPLACE_ME'))
        if valid:
            return uri
    except (OSError, ValueError):
        pass
    raise ConfigurationError('The server .env must contain the supplied public MongoDB URI with root, the real password and authSource=admin.')


def api_token():
    token = os.environ.get('LIARA_API_TOKEN', '').strip()
    if token:
        return token
    try:
        config = json.loads((Path.home() / '.liara-auth.json').read_text())
        for account in config['accounts'].values():
            if account.get('current') and account.get('api_token'):
                return account['api_token']
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    raise ConfigurationError('Log in with liara login, or set LIARA_API_TOKEN in the operator environment.')


class Liara:
    def __init__(self, token, team_id=None):
        self.token = token
        self.query = '?' + urlencode({'teamID': team_id}) if team_id else ''
        self.opener = build_opener(NoRedirect())

    def request(self, path, payload=None):
        request = Request('https://api.liara.ir/' + path + self.query,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'},
            method='POST' if payload is not None else 'GET')
        try:
            with self.opener.open(request, timeout=15) as response:
                # Update responses need not have a JSON body; the readback is authoritative.
                return None if payload is not None else json.load(response)
        except HTTPError as exc:
            raise ConfigurationError(f'Liara API rejected the request (HTTP {exc.code}); runtime credentials were not verified.') from None
        except URLError as exc:
            if isinstance(exc.reason, socket.gaierror):
                raise ConfigurationError('Liara API DNS unavailable in this environment; runtime credentials were not verified.') from None
            raise ConfigurationError('Liara API network connection failed; runtime credentials were not verified.') from None
        except (OSError, ValueError):
            raise ConfigurationError('Liara API returned an unreadable response or the request timed out; runtime credentials were not verified.') from None

    def variables(self, app):
        payload = self.request('v1/projects/' + app)
        try:
            rows = payload['project']['envs']
            if not isinstance(rows, list) or any(
                    not isinstance(row, dict) or not isinstance(row.get('key'), str)
                    or not isinstance(row.get('value'), str) for row in rows):
                raise ValueError
            return [{'key': row['key'], 'value': row['value']} for row in rows]
        except (KeyError, TypeError, ValueError):
            raise ConfigurationError('Liara runtime variables could not be read; refusing to replace them.') from None


def matches(rows, uri):
    values = [row['value'] for row in rows if row['key'] == 'MONGODB_URI']
    return len(values) == 1 and hmac.compare_digest(values[0].encode(), uri.encode())


def sync(api, app, uri, *, check=False, write=print):
    rows = api.variables(app)
    if matches(rows, uri):
        write('Liara runtime MONGODB_URI already matches the server .env; no restart requested.')
        return 0
    if check:
        write('Liara runtime MONGODB_URI differs from the server .env; no changes requested.')
        return 1
    variables = [row for row in rows if row['key'] != 'MONGODB_URI']
    variables.append({'key': 'MONGODB_URI', 'value': uri})
    write('Updating only Liara runtime MONGODB_URI from the server .env; Liara may restart the app.')
    api.request('v1/projects/update-envs', {'project': app, 'variables': variables})
    if not matches(api.variables(app), uri):
        raise ConfigurationError('Liara runtime MONGODB_URI did not match after the update; do not assume the fix succeeded.')
    write('Liara runtime MONGODB_URI verified. MongoDB authentication and readiness still require a live check.')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=ROOT / '.env')
    parser.add_argument('--app', default=None)
    parser.add_argument('--team-id')
    parser.add_argument('--check', action='store_true', help='Compare runtime credentials without updating or restarting')
    args = parser.parse_args(argv)
    try:
        app = args.app or json.loads((ROOT / 'liara.json').read_text())['app']
        if not isinstance(app, str) or not re.fullmatch(r'[a-zA-Z0-9_-]+', app):
            raise ConfigurationError('Invalid Liara app name.')
        uri = source_uri(args.env_file)
        api = Liara(api_token(), args.team_id)
        print('MongoDB target: olympus.liara.cloud:34468/my-app; authSource=admin; credentials hidden.', flush=True)
        return sync(api, app, uri, check=args.check)
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        print('Could not read operator configuration; credentials hidden.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
