"""Repository contract and the only runtime backend: real MongoDB."""
import builtins
from collections.abc import Mapping
from typing import Any, ContextManager, Protocol

Document = dict[str, Any]


class DuplicateRecord(ValueError):
    """A unique document or business key already exists."""


class VersionConflict(ValueError):
    """An optimistic update used a stale version."""


class StorageUnavailable(RuntimeError):
    """Safe operational error; never contains connection strings or credentials."""


class DocumentStore(Protocol):
    def atomic(self) -> ContextManager[None]: ...
    def get(self, collection: str, record_id: str) -> Document | None: ...
    def list(self, collection: str) -> builtins.list[Document]: ...
    def published_catalog(self) -> builtins.list[Document]: ...
    def insert(self, collection: str, document: Document) -> Document: ...
    def replace(self, collection: str, document: Document, *, expected_version: int) -> Document: ...
    def delete(self, collection: str, record_id: str) -> None: ...
    def ping(self) -> None: ...
    def close(self) -> None: ...


def create_store(environment: Mapping[str, str] | None = None) -> DocumentStore:
    if environment is None:
        from app.core.config import load_environment
        environment = load_environment()
    if environment.get('DATA_BACKEND', 'mongo').strip().lower() != 'mongo':
        raise ValueError('Only DATA_BACKEND=mongo is supported; memory fallback is disabled')
    uri = environment.get('MONGODB_URI', '').strip()
    if not uri:
        raise ValueError('MONGODB_URI is required; configure the server .env')
    try:
        from app.core.mongo import MongoDocumentStore
    except ImportError:
        raise StorageUnavailable('Install the locked API dependencies, including PyMongo') from None
    return MongoDocumentStore(uri)
