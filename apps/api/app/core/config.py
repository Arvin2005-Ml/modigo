from dataclasses import dataclass, field
from os import environ
from pathlib import Path
import re
import shlex
from urllib.parse import urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[4]
PRODUCTION_ORIGIN = 'https://moodigo.ir'
DEFAULT_GAPGPT_IMAGE_HOSTS = ('api.gapgpt.app', 'gapgpt.app', 'aigap.app')


def normalize_app_origin(value):
    """Canonical browser origin; never infer trust from request/proxy headers."""
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
        if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment
                or parsed.username is not None or parsed.password is not None):
            raise ValueError
        host = parsed.hostname
        if ':' in host:
            host = '[' + host + ']'
        standard_port = 443 if parsed.scheme == 'https' else 80
        suffix = f':{port}' if port is not None and port != standard_port else ''
        return f'{parsed.scheme}://{host}{suffix}'
    except (ValueError, AttributeError):
        raise ValueError('APP_ORIGIN must contain only a valid http(s) origin, without credentials, path, query or fragment') from None


def validate_mongodb_uri(uri):
    try:
        parsed = urlsplit(uri)
        # Accessing .port also validates its numeric value without echoing it.
        parsed.port
        valid = (parsed.scheme == 'mongodb' and parsed.hostname and
                 parsed.path not in ('', '/') and not parsed.fragment)
    except ValueError:
        raise ValueError('MONGODB_URI has an invalid host or port') from None
    if not valid:
        raise ValueError('MONGODB_URI must select an explicit MongoDB host and application database')
    if parsed.hostname in ('localhost', '127.0.0.1', '::1', 'shadophen'):
        raise ValueError('Use the public MongoDB endpoint, including in local development')


def load_environment(path=None, overrides=None):
    """Load the root server .env without shell execution or interpolation.

    Existing process variables always take precedence. Never load .env.example.
    """
    values = {}
    path = Path(path) if path is not None else PROJECT_ROOT / '.env'
    if path.is_file():
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            match = re.fullmatch(r'\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*', line)
            if not match:
                raise ValueError(f'Invalid server .env assignment on line {number}')
            try:
                parts = shlex.split(match[2], comments=True)
            except ValueError:
                raise ValueError(f'Invalid server .env quoting on line {number}') from None
            if len(parts) > 1:
                raise ValueError(f'Quote whitespace in server .env on line {number}')
            values[match[1]] = parts[0] if parts else ''
    values.update(environ if overrides is None else overrides)
    return values


@dataclass(frozen=True)
class Settings:
    app_origin: str = 'http://127.0.0.1:3000'
    environment: str = 'development'
    data_backend: str = 'mongo'
    mongodb_uri: str = field(default='', repr=False)
    csrf_hmac_secret: str = field(default='', repr=False)
    api_workers: str = '1'
    job_runner_mode: str = 'in_process'
    demo_content: bool = True
    catalog_release: str = 'unified'
    provider: str = 'demo'
    gapgpt_api_key: str = field(default='', repr=False)
    gapgpt_base_url: str = 'https://api.gapgpt.app/v1'
    gapgpt_model: str = 'gapgpt-deepseek-v4.1-flash'
    gapgpt_assistant_model: str = 'gdeepseek-v4.1-flash'
    gapgpt_image_model: str = 'gemini-2.5-flash-image'
    gapgpt_image_hosts: tuple[str, ...] = DEFAULT_GAPGPT_IMAGE_HOSTS

    @classmethod
    def load(cls):
        environ = load_environment()
        environment = environ.get('APP_ENV', 'development')
        default_origin = PRODUCTION_ORIGIN if environment == 'production' else 'http://127.0.0.1:3000'
        settings = cls(app_origin=normalize_app_origin(environ.get('APP_ORIGIN', default_origin)),
                       environment=environment,
                       data_backend=environ.get('DATA_BACKEND', 'mongo').strip().lower(),
                       mongodb_uri=environ.get('MONGODB_URI', '').strip(),
                       csrf_hmac_secret=environ.get('CSRF_HMAC_SECRET', ''),
                       api_workers=environ.get('API_WORKERS', environ.get('WEB_CONCURRENCY', '1')),
                       job_runner_mode=environ.get('JOB_RUNNER_MODE', 'in_process'),
                       demo_content=environ.get('DEMO_CONTENT', 'true').lower() == 'true',
                       catalog_release=environ.get('CATALOG_RELEASE', 'unified'),
                       provider=environ.get('LLM_PROVIDER', environ.get('AI_PROVIDER', 'demo')),
                       gapgpt_api_key=environ.get('GAPGPT_API_KEY', ''),
                       gapgpt_base_url=environ.get('GAPGPT_BASE_URL', 'https://api.gapgpt.app/v1'),
                       gapgpt_model=environ.get('GAPGPT_MODEL', 'gapgpt-deepseek-v4.1-flash'),
                       gapgpt_assistant_model=environ.get('GAPGPT_ASSISTANT_MODEL', 'gpt-4.1-mini').strip(),
                       gapgpt_image_model=environ.get('GAPGPT_IMAGE_MODEL', 'gemini-2.5-flash-image').strip(),
                       gapgpt_image_hosts=DEFAULT_GAPGPT_IMAGE_HOSTS + tuple(
                           host.strip().lower() for host in environ.get('GAPGPT_IMAGE_HOSTS', '').split(',') if host.strip()))
        settings.validate()
        return settings

    def validate(self):
        if self.data_backend != 'mongo':
            raise ValueError('Only DATA_BACKEND=mongo is enabled; memory fallback is disabled')
        validate_mongodb_uri(self.mongodb_uri)
        if len(self.csrf_hmac_secret) < 32:
            raise ValueError('CSRF_HMAC_SECRET must contain at least 32 characters and remain stable across restarts')
        if self.api_workers != '1' or environ.get('WEB_CONCURRENCY', '1') != '1':
            raise ValueError('The current in-process job runner requires exactly one API process')
        if self.job_runner_mode != 'in_process':
            raise ValueError('Jobs must share the application process')
        if self.catalog_release not in ('unified', 'real700', 'legacy'):
            raise ValueError('Unsupported catalog release')
        if normalize_app_origin(self.app_origin) != self.app_origin:
            raise ValueError('APP_ORIGIN must be a canonical origin; use Settings.load for environment configuration')
        parsed = urlsplit(self.app_origin)
        if self.environment not in ('development', 'production'):
            raise ValueError('APP_ENV must be development or production')
        if self.environment == 'production' and (parsed.scheme != 'https' or
                parsed.hostname in ('localhost', '127.0.0.1', '::1')):
            raise ValueError('Production APP_ORIGIN must use the public HTTPS origin')
        if self.provider not in ('demo', 'gapgpt'):
            raise ValueError('Unsupported LLM provider')
        if self.provider == 'gapgpt' and (not self.gapgpt_api_key or
                self.gapgpt_base_url != 'https://api.gapgpt.app/v1' or not self.gapgpt_model):
            raise ValueError('GapGPT requires a server-side key and the configured GapGPT endpoint')
        if not self.gapgpt_assistant_model or not self.gapgpt_image_model:
            raise ValueError('GapGPT assistant and image model identifiers must be set')
        if any(len(host) > 253 or not re.fullmatch(
                r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,62}', host)
               for host in self.gapgpt_image_hosts):
            raise ValueError('GAPGPT_IMAGE_HOSTS must contain exact DNS names without ports or wildcards')

    @property
    def allowed_origins(self):
        # Both names are local development aliases. All other origins stay exact.
        parsed = urlsplit(self.app_origin)
        origins = [self.app_origin]
        if (self.environment == 'development' and parsed.scheme == 'http'
                and parsed.hostname in ('localhost', '127.0.0.1')):
            alternate = '127.0.0.1' if parsed.hostname == 'localhost' else 'localhost'
            port = f':{parsed.port}' if parsed.port is not None else ''
            origins.append(f'http://{alternate}{port}')
        return origins

    @property
    def secure_cookies(self):
        return self.app_origin.startswith('https://')

    @property
    def session_cookie(self):
        return '__Host-funilo_session' if self.secure_cookies else 'funilo_session_dev'
