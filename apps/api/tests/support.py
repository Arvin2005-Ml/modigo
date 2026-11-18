"""Isolated test double; never selectable by runtime configuration."""
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from threading import RLock
from app.core.storage import Document, DuplicateRecord, VersionConflict

class MemoryTestStore:
    """Isolated document snapshots with rollback and serialized local writes.

    Only id uniqueness is generic here. Domain repositories enforce additional
    unique keys, ownership and publication rules within a shared atomic block.
    This does not emulate Mongo queries, TTL indexes or replica-set guarantees.
    """

    def __init__(self) -> None:
        self._collections: dict[str, dict[str, Document]] = {}
        self._lock = RLock()

    @contextmanager
    def atomic(self) -> Iterator[None]:
        with self._lock:
            before = deepcopy(self._collections)
            try:
                yield
            except BaseException:
                self._collections = before
                raise

    def get(self, collection: str, record_id: str) -> Document | None:
        with self._lock:
            return deepcopy(self._collections.get(collection, {}).get(record_id))

    def list(self, collection: str) -> list[Document]:
        with self._lock:
            return deepcopy(list(self._collections.get(collection, {}).values()))

    def published_catalog(self) -> list[Document]:
        with self._lock:
            revisions = self._collections.get('activity_revisions', {})
            rows = []
            for activity in self._collections.get('activities', {}).values():
                pointer = activity.get('published_revision_id')
                revision = revisions.get(pointer)
                if (activity.get('active') is True and revision and revision.get('state') == 'published'
                        and revision.get('activity_id') == activity['id']):
                    rows.append(dict(id=activity['id'], active=True, primary_dimension=activity['primary_dimension'],
                                     published_revision_id=pointer, revision_id=revision['id'],
                                     state='published', content=revision.get('content')))
            return deepcopy(rows)
    def insert(self, collection: str, document: Document) -> Document:
        candidate = deepcopy(document)
        record_id = candidate.get('id')
        if not isinstance(record_id, str) or not record_id:
            raise ValueError('document id must be a nonempty string')
        version = candidate.setdefault('version', 1)
        if type(version) is not int or version != 1:
            raise ValueError('new document version must be 1')
        with self._lock:
            records = self._collections.setdefault(collection, {})
            if record_id in records:
                raise DuplicateRecord(record_id)
            records[record_id] = candidate
            return deepcopy(candidate)

    def replace(
        self, collection: str, document: Document, *, expected_version: int
    ) -> Document:
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError('expected_version must be a positive integer')
        candidate = deepcopy(document)
        record_id = candidate.get('id')
        if not isinstance(record_id, str) or not record_id:
            raise ValueError('document id must be a nonempty string')
        with self._lock:
            records = self._collections.get(collection, {})
            if record_id not in records:
                raise KeyError(record_id)
            if records[record_id]['version'] != expected_version:
                raise VersionConflict(record_id)
            candidate['version'] = expected_version + 1
            records[record_id] = candidate
            return deepcopy(candidate)

    def delete(self, collection: str, record_id: str) -> None:
        with self._lock:
            self._collections.get(collection, {}).pop(record_id, None)


    def ping(self):
        pass

    def close(self):
        pass
