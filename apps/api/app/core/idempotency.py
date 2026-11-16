"""Caller mutations and receipts share the store's synchronous atomic block."""
import json
from datetime import timedelta
from app.core.errors import DomainError
from app.core.values import digest, uid


class Idempotency:
    def __init__(self, store, clock):
        self.store, self.clock = store, clock

    def run(self, user_id, scope, key, payload, action):
        if not isinstance(key, str) or not 16 <= len(key) <= 128 or not key.isascii():
            raise DomainError('VALIDATION_ERROR', 'شناسهٔ درخواست معتبر نیست.', 422)
        request_hash = digest(json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str))
        with self.store.atomic():
            now = self.clock()
            for r in self.store.list('idempotency_receipts'):
                if r['expires_at'] <= now:
                    self.store.delete('idempotency_receipts', r['id'])
                elif (r['user_id'], r['scope'], r['key']) == (user_id, scope, key):
                    if r['request_hash'] != request_hash:
                        raise DomainError('IDEMPOTENCY_CONFLICT', 'این شناسه برای درخواست دیگری استفاده شده.')
                    return r['response']
            response = action()
            receipt = self.store.insert('idempotency_receipts', dict(id=uid(), user_id=user_id, scope=scope,
                key=key, request_hash=request_hash, response=response, expires_at=now + timedelta(hours=24)))
            return receipt['response']
