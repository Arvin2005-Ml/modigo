from datetime import timedelta
from app.core.errors import DomainError
from app.core.values import digest, replace


class RateLimiter:
    def __init__(self, store, clock):
        self.store, self.clock = store, clock

    def take(self, scope, subject, limit, seconds):
        with self.store.atomic():
            now = self.clock()
            key = digest(f'{scope}:{subject}')
            record = self.store.get('rate_limit_buckets', key)
            if record and record['window_end'] > now:
                if record['count'] >= limit:
                    raise DomainError('RATE_LIMITED', 'یه کم مکث کن و دوباره امتحان کن.', 429)
                record['count'] += 1
                replace(self.store, 'rate_limit_buckets', record)
            else:
                if record:
                    self.store.delete('rate_limit_buckets', key)
                self.store.insert('rate_limit_buckets', dict(id=key, count=1, window_end=now + timedelta(seconds=seconds)))
