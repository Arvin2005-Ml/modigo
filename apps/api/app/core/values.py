from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4


def utcnow():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid4())


def digest(value: str):
    return sha256(value.encode()).hexdigest()


def replace(store, collection, record):
    return store.replace(collection, record, expected_version=record['version'])


def owned(store, collection, record_id, user_id):
    from app.core.errors import missing
    record = store.get(collection, record_id)
    if not record or record.get('user_id') != user_id:
        missing()
    return record
