"""Safe domain errors; no transport or provider details in user messages."""


class DomainError(Exception):
    def __init__(self, code: str, message: str, status: int = 409, fields: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.status, self.fields = code, message, status, fields or {}


def missing():
    raise DomainError('NOT_FOUND', 'این مورد پیدا نشد.', 404)


def conflict(message='این مورد تغییر کرده؛ صفحه رو تازه کن.'):
    raise DomainError('VERSION_CONFLICT', message)
