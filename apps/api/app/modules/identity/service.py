"""Opaque sessions and locally delivered email. No public mailbox or role endpoint."""
import hmac
import secrets
from datetime import timedelta
from hashlib import sha256
from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from app.core.errors import DomainError, missing
from app.core.schemas import Preferences
from app.core.values import digest, uid, replace

PUBLIC_FIELDS = ('id', 'display_name', 'email', 'role', 'email_verified', 'timezone', 'status')
GENERIC = {'message': 'اگه این نشانی قابل استفاده باشه، ایمیل راهنما می‌رسه.'}


def password_hash(password):
    return Argon2id(salt=secrets.token_bytes(16), length=32, iterations=2,
                   lanes=1, memory_cost=19456).derive_phc_encoded(password.encode())


def verify_password(password, encoded):
    try:
        Argon2id.verify_phc_encoded(password.encode(), encoded)
        return True
    except InvalidKey:
        return False


class Identity:
    def __init__(self, store, settings, clock, limiter):
        self.store, self.settings, self.clock, self.limiter = store, settings, clock, limiter
        self._csrf_key = settings.csrf_hmac_secret.encode()
        self._dummy_hash = password_hash(secrets.token_urlsafe(32))
        # The mailbox is process-local and accessible exclusively through the local operator console.
        # Tokens are necessarily present in the delivered message, never in application logs/API.
        self.mailbox = []

    def user(self, user_id):
        user = self.store.get('users', user_id)
        if not user or user['status'] != 'active':
            raise DomainError('AUTH_REQUIRED', 'برای ادامه وارد حسابت شو.', 401)
        return user

    def public(self, user):
        return {key: user[key] for key in PUBLIC_FIELDS}

    def by_email(self, email):
        return next((u for u in self.store.list('users') if u['email'] == email.lower().strip()), None)

    def _mail(self, user, purpose):
        now = self.clock()
        for token in self.store.list('account_tokens'):
            if token['user_id'] == user['id'] and token['purpose'] == purpose and not token['consumed_at']:
                token['consumed_at'] = now
                replace(self.store, 'account_tokens', token)
        raw = secrets.token_urlsafe(32)
        self.store.insert('account_tokens', dict(id=digest(raw), user_id=user['id'], purpose=purpose,
            expires_at=now + timedelta(minutes=30),
            consumed_at=None))
        self.mailbox.append(dict(email=user['email'], purpose=purpose,
            link=f'{self.settings.app_origin}/?{purpose}={raw}', created_at=now))
        # Bounded local mailbox, no filesystem token persistence.
        self.mailbox[:] = self.mailbox[-100:]

    def signup(self, data, ip):
        self.limiter.take('signup.email', data.email, 3, 3600)
        self.limiter.take('signup.ip', ip, 10, 3600)
        encoded = password_hash(data.password)
        with self.store.atomic():
            existing = self.by_email(data.email)
            if existing:
                raise DomainError('ACCOUNT_EXISTS', 'با این ایمیل قبلاً حساب ساختی؛ وارد شو.', 409)
            user = self.store.insert('users', dict(id=uid(), email=data.email, display_name=data.display_name.strip(),
                password_hash=encoded, role='user', email_verified=False, status='active', timezone='Asia/Tehran',
                created_at=self.clock(), adult_confirmed_at=self.clock()))
            self.store.insert('profiles', dict(id=user['id'], user_id=user['id'], preferences=Preferences().model_dump()))
            return {'message': 'حسابت ساخته شد.'}

    def _csrf(self, raw):
        return hmac.new(self._csrf_key, raw.encode(), sha256).hexdigest()

    def login(self, data, ip, previous):
        self.limiter.take('login.email', data.email, 5, 900)
        self.limiter.take('login.ip', ip, 20, 900)
        user = self.by_email(data.email)
        valid = verify_password(data.password, user['password_hash'] if user else self._dummy_hash)
        if not valid or not user or user['status'] != 'active':
            raise DomainError('AUTH_REQUIRED', 'ایمیل یا رمز درست نیست.', 401)
        verified_hash = user['password_hash']
        with self.store.atomic():
            user = self.user(user['id'])
            if user['password_hash'] != verified_hash:
                raise DomainError('AUTH_REQUIRED', 'دوباره با رمز فعلی وارد شو.', 401)
            self.logout(previous)
            if not user['password_hash'].startswith('$argon2id$v=19$m=19456,t=2,p=1$'):
                user['password_hash'] = password_hash(data.password)
                replace(self.store, 'users', user)
            raw = secrets.token_urlsafe(32)
            csrf = self._csrf(raw)
            hours = 8 if user['role'] in ('editor', 'admin') else 14 * 24
            self.store.insert('auth_sessions', dict(id=digest(raw), user_id=user['id'], csrf_hash=digest(csrf),
                created_at=self.clock(), expires_at=self.clock() + timedelta(hours=hours), last_seen_at=self.clock()))
            return raw, {'user': self.public(user), 'csrf_token': csrf}

    def session(self, raw, touch=True):
        if not raw or len(raw) > 128:
            raise DomainError('AUTH_REQUIRED', 'برای ادامه وارد حسابت شو.', 401)
        with self.store.atomic():
            session = self.store.get('auth_sessions', digest(raw))
            if not session:
                raise DomainError('AUTH_REQUIRED', 'برای ادامه وارد حسابت شو.', 401)
            user = self.user(session['user_id'])
            idle = timedelta(minutes=30) if user['role'] in ('editor', 'admin') else timedelta(days=7)
            if session['expires_at'] <= self.clock() or session['last_seen_at'] + idle <= self.clock():
                self.store.delete('auth_sessions', session['id'])
                raise DomainError('AUTH_REQUIRED', 'نشستت تموم شده؛ دوباره وارد شو.', 401)
            if touch:
                session['last_seen_at'] = self.clock()
                replace(self.store, 'auth_sessions', session)
            return user

    def issue_csrf(self, session_raw, preauth_raw):
        try:
            self.session(session_raw, touch=False)
            return self._csrf(session_raw), None
        except DomainError:
            pass
        with self.store.atomic():
            if preauth_raw:
                record = self.store.get('preauth', digest(preauth_raw))
                if record and record['expires_at'] > self.clock():
                    return self._csrf(preauth_raw), preauth_raw
            raw = secrets.token_urlsafe(32)
            self.store.insert('preauth', dict(id=digest(raw), expires_at=self.clock() + timedelta(hours=1)))
            return self._csrf(raw), raw

    def check_csrf(self, session_raw, preauth_raw, header, origin):
        if origin not in self.settings.allowed_origins:
            raise DomainError('CSRF_FAILED', 'آدرس صفحه با نشانی اصلی برنامه هماهنگ نیست؛ از نشانی اصلی برنامه وارد شو.', 403)
        if not header or len(header) > 128:
            raise DomainError('CSRF_FAILED', 'درخواست معتبر نیست؛ صفحه رو تازه کن.', 403)
        with self.store.atomic():
            if session_raw:
                try:
                    self.session(session_raw, touch=False)
                except DomainError:
                    pass
                else:
                    session = self.store.get('auth_sessions', digest(session_raw))
                    if hmac.compare_digest(session['csrf_hash'], digest(header)):
                        return
                    raise DomainError('CSRF_FAILED', 'درخواست معتبر نیست؛ صفحه رو تازه کن.', 403)
            if preauth_raw:
                record = self.store.get('preauth', digest(preauth_raw))
                if record and record['expires_at'] > self.clock() and hmac.compare_digest(header, self._csrf(preauth_raw)):
                    return
        raise DomainError('CSRF_FAILED', 'نشست مرورگر معتبر نیست؛ صفحه رو تازه کن و اجازهٔ ذخیرهٔ کوکی رو بررسی کن.', 403)

    def logout(self, raw):
        if raw:
            self.store.delete('auth_sessions', digest(raw))

    def preferences(self, user_id):
        profile = self.store.get('profiles', user_id)
        return {'version': profile['version'], 'preferences': profile['preferences']}

    def update_preferences(self, user_id, data):
        from app.core.errors import conflict
        with self.store.atomic():
            self.user(user_id)
            profile = self.store.get('profiles', user_id)
            if profile['version'] != data.version:
                conflict()
            profile['preferences'] = data.preferences.model_dump()
            saved = replace(self.store, 'profiles', profile)
            return {'version': saved['version'], 'preferences': saved['preferences']}

    def account_email(self, email, ip, purpose):
        self.limiter.take(purpose + '.email', email, 3, 3600)
        self.limiter.take(purpose + '.ip', ip, 10, 3600)
        with self.store.atomic():
            user = self.by_email(email)
            if user and user['status'] == 'active' and purpose == 'reset_password':
                # Development-only operator mailbox; no claim of verified email ownership.
                self._mail(user, purpose)
            return GENERIC

    def revoke_all(self, user_id):
        for session in self.store.list('auth_sessions'):
            if session['user_id'] == user_id:
                self.store.delete('auth_sessions', session['id'])

    def logout_all(self, user_id, password):
        with self.store.atomic():
            user = self.user(user_id)
            if not verify_password(password, user['password_hash']):
                raise DomainError('AUTH_REQUIRED', 'رمز فعلی درست نیست.', 401)
            self.revoke_all(user_id)

    def reset_password(self, raw, new_password):
        encoded = password_hash(new_password)
        with self.store.atomic():
            token = self.store.get('account_tokens', digest(raw))
            if (not token or token['purpose'] != 'reset_password' or token['consumed_at']
                    or token['expires_at'] <= self.clock()):
                raise DomainError('INVALID_REQUEST', 'این لینک اعتبار نداره؛یه لینک تازه بگیر.', 400)
            user = self.user(token['user_id'])
            user['password_hash'] = encoded
            token['consumed_at'] = self.clock()
            replace(self.store, 'users', user)
            replace(self.store, 'account_tokens', token)
            self.revoke_all(user['id'])

    def change_password(self, user_id, current_password, new_password):
        encoded = password_hash(new_password)
        with self.store.atomic():
            user = self.user(user_id)
            if not verify_password(current_password, user['password_hash']):
                raise DomainError('AUTH_REQUIRED', 'رمز فعلی درست نیست.', 401)
            user['password_hash'] = encoded
            replace(self.store, 'users', user)
            self.revoke_all(user_id)

    def promote(self, email, role):
        """Local operator console only; never exposed by an HTTP route."""
        if role not in ('user', 'editor', 'admin'):
            raise ValueError('Unknown role')
        with self.store.atomic():
            user = self.by_email(email)
            if not user:
                missing()
            if user['role'] == 'admin' and role != 'admin':
                admins = [u for u in self.store.list('users') if u['role'] == 'admin' and u['status'] == 'active']
                if len(admins) <= 1:
                    raise DomainError('INVALID_STATE', 'آخرین ادمین رو نمی‌شه حذف کرد.')
            user['role'] = role
            replace(self.store, 'users', user)
            for session in self.store.list('auth_sessions'):
                if session['user_id'] == user['id']:
                    self.store.delete('auth_sessions', session['id'])
            self.store.insert('admin_audit', dict(id=uid(), actor_id='local_operator', action='role_changed',
                target_id=user['id'], role=role, created_at=self.clock()))
