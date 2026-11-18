"""Real multi-document Mongo transactions. Nested blocks join the outer unit.

One API process and an in-process runner; no await/provider calls inside atomic.
The DB guard serializes units across operator clients too, preventing write skew.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import timezone
from threading import RLock, local
from time import monotonic, sleep

from bson.codec_options import CodecOptions
from bson import BSON
from pymongo import ASCENDING, ReadPreference
from pymongo.errors import DuplicateKeyError, PyMongoError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern
from app.core.storage import DuplicateRecord, StorageUnavailable, VersionConflict
from app.core.mongo_connection import create_mongo_client, mongo_failure

# These fields match the implemented documents, rather than the initial sketches.
INDEXES = {
    'users': [([('email', ASCENDING)], {'unique': True})],
    'profiles': [([('user_id', ASCENDING)], {'unique': True})],
    'activities': [([('seed_key', ASCENDING)], {'unique': True, 'sparse': True}),
                   ([('active', ASCENDING), ('published_revision_id', ASCENDING)], {})],
    'activity_revisions': [([('activity_id', ASCENDING), ('revision_number', ASCENDING)], {'unique': True})],
    'auth_sessions': [([('user_id', ASCENDING)], {}), ([('expires_at', ASCENDING)], {'expireAfterSeconds': 0})],
    'preauth': [([('expires_at', ASCENDING)], {'expireAfterSeconds': 0})],
    'account_tokens': [([('expires_at', ASCENDING)], {'expireAfterSeconds': 0})],
    'check_ins': [([('user_id', ASCENDING), ('created_at', ASCENDING)], {}),
                  ([('expires_at', ASCENDING)], {'expireAfterSeconds': 0})],
    'recommendation_sessions': [([('check_in_id', ASCENDING)], {'unique': True}),
        ([('user_id', ASCENDING), ('created_at', ASCENDING)], {}),
        ([('purge_at', ASCENDING)], {'expireAfterSeconds': 0})],
    'experiences': [([('user_id', ASCENDING)], {'unique': True, 'partialFilterExpression': {'status': 'active'}})],
    'feedback': [([('experience_id', ASCENDING)], {'unique': True})],
    'saved_activities': [([('user_id', ASCENDING), ('activity_id', ASCENDING)], {'unique': True})],
    'reward_ledger': [([('experience_id', ASCENDING)], {'unique': True}),
                     ([('user_id', ASCENDING), ('created_at', ASCENDING)], {})],
    'user_badges': [([('user_id', ASCENDING), ('badge_key', ASCENDING)], {'unique': True})],
    'user_progress': [([('user_id', ASCENDING)], {'unique': True})],
    'content_jobs': [([('activity_id', ASCENDING)], {'unique': True,
        'partialFilterExpression': {'state': {'$in': ['queued', 'running']}}})],
    'idempotency_receipts': [([('user_id', ASCENDING), ('scope', ASCENDING), ('key', ASCENDING)], {'unique': True}),
                             ([('expires_at', ASCENDING)], {'expireAfterSeconds': 0})],
    'rate_limit_buckets': [([('window_end', ASCENDING)], {'expireAfterSeconds': 0})],
    'admin_audit': [([('target_id', ASCENDING), ('created_at', ASCENDING)], {})],
}

PUBLISHED_CATALOG = [
    {'$match': {'active': True, 'published_revision_id': {'$type': 'string'}}},
    {'$project': {'id': 1, 'active': 1, 'primary_dimension': 1, 'published_revision_id': 1}},
    {'$lookup': {'from': 'activity_revisions', 'localField': 'published_revision_id',
                 'foreignField': '_id', 'as': 'revision'}},
    {'$unwind': '$revision'},
    {'$match': {'revision.state': 'published', '$expr': {'$eq': ['$id', '$revision.activity_id']}}},
    {'$project': {'_id': 0, 'id': 1, 'active': 1, 'primary_dimension': 1,
                  'published_revision_id': 1, 'revision_id': '$revision.id',
                  'state': '$revision.state', 'content': '$revision.content'}},
]


class MongoDocumentStore:
    def __init__(self, uri):
        self._lock, self._local = RLock(), local()
        self._client = None
        stage = 'connect'
        try:
            # Never follow private replica hostnames advertised behind Liara's
            # public proxy. The configured endpoint must be the writable primary.
            self._client = create_mongo_client(uri)
            self._db = self._client.get_default_database(codec_options=CodecOptions(tz_aware=True, tzinfo=timezone.utc),
                read_preference=ReadPreference.PRIMARY, write_concern=WriteConcern('majority', wtimeout=10000))
            if self._db.name in ('admin', 'config', 'local'):
                raise StorageUnavailable('MONGODB_URI must select an application database')
            self.ping()
            stage = 'hello'
            hello = self._client.admin.command('hello')
            if not hello.get('setName') or not hello.get('isWritablePrimary'):
                raise StorageUnavailable('MongoDB requires a writable replica-set primary for atomic application operations')
            self._initialize()
        except StorageUnavailable:
            self.close()
            raise
        except (PyMongoError, ValueError, TypeError) as exc:
            self.close()
            raise mongo_failure(exc, stage) from None

    def _initialize(self):
        try:
            for collection, definitions in INDEXES.items():
                for keys, options in definitions:
                    self._db[collection].create_index(keys, **options)
            self._db['_funilo_meta'].update_one({'_id': 'atomic_guard'}, {'$setOnInsert': {'value': 0}}, upsert=True)
        except PyMongoError as exc:
            raise mongo_failure(exc, 'indexes') from None
        # Check actual transaction/write permissions before seeding application data.
        with self.atomic():
            pass

    def ping(self):
        try:
            self._client.admin.command('ping')
        except PyMongoError as exc:
            raise mongo_failure(exc, 'ping') from None

    def close(self):
        if self._client is not None:
            self._client.close()

    @property
    def _session(self):
        return getattr(self._local, 'session', None)

    @contextmanager
    def atomic(self):
        with self._lock:
            if self._session is not None:
                yield
                return
            try:
                with self._client.start_session() as session:
                    # Bounded retries before yield cannot repeat business effects.
                    deadline = monotonic() + 5
                    while True:
                        session.start_transaction(read_concern=ReadConcern('snapshot'),
                            write_concern=WriteConcern('majority', wtimeout=10000), max_commit_time_ms=10000)
                        try:
                            self._db['_funilo_meta'].update_one({'_id': 'atomic_guard'}, {'$inc': {'value': 1}}, session=session)
                            break
                        except PyMongoError as exc:
                            if session.in_transaction:
                                session.abort_transaction()
                            if not exc.has_error_label('TransientTransactionError') or monotonic() >= deadline:
                                raise
                            sleep(.05)
                    self._local.session = session
                    try:
                        yield
                        deadline = monotonic() + 15
                        while True:
                            try:
                                session.commit_transaction()
                                break
                            except PyMongoError as exc:
                                if not exc.has_error_label('UnknownTransactionCommitResult') or monotonic() >= deadline:
                                    raise
                    except BaseException:
                        if session.in_transaction:
                            try:
                                session.abort_transaction()
                            except PyMongoError:
                                pass
                        raise
                    finally:
                        self._local.session = None
            except DuplicateKeyError:
                raise DuplicateRecord('A unique record already exists') from None
            except PyMongoError as exc:
                raise mongo_failure(exc, 'transaction') from None

    def get(self, collection, record_id):
        try:
            return self._db[collection].find_one({'_id': record_id}, {'_id': False}, session=self._session)
        except PyMongoError:
            raise StorageUnavailable('MongoDB read failed') from None

    def list(self, collection):
        try:
            return list(self._db[collection].find({}, {'_id': False}, session=self._session))
        except PyMongoError:
            raise StorageUnavailable('MongoDB read failed') from None

    def published_catalog(self):
        try:
            return list(self._db.activities.aggregate(PUBLISHED_CATALOG, session=self._session,
                                                     batchSize=2000))
        except PyMongoError:
            raise StorageUnavailable('MongoDB catalog read failed') from None

    @staticmethod
    def _candidate(document):
        candidate = deepcopy(document)
        record_id = candidate.get('id')
        if not isinstance(record_id, str) or not record_id:
            raise ValueError('document id must be a nonempty string')
        candidate['_id'] = record_id
        # BSON Date has millisecond precision. Return the persisted form so an
        # immediate response and its later idempotency replay have equal dates.
        return BSON(BSON.encode(candidate)).decode(codec_options=CodecOptions(tz_aware=True, tzinfo=timezone.utc))

    def insert(self, collection, document):
        candidate = self._candidate(document)
        version = candidate.setdefault('version', 1)
        if type(version) is not int or version != 1:
            raise ValueError('new document version must be 1')
        with self.atomic():
            try:
                self._db[collection].insert_one(candidate, session=self._session)
            except DuplicateKeyError:
                raise DuplicateRecord('A unique record already exists') from None
        candidate.pop('_id')
        return candidate

    def replace(self, collection, document, *, expected_version):
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError('expected_version must be a positive integer')
        candidate = self._candidate(document)
        candidate['version'] = expected_version + 1
        with self.atomic():
            result = self._db[collection].replace_one({'_id': candidate['_id'], 'version': expected_version},
                                                     candidate, session=self._session)
            if not result.matched_count:
                if self.get(collection, candidate['id']) is None:
                    raise KeyError(candidate['id'])
                raise VersionConflict(candidate['id'])
        candidate.pop('_id')
        return candidate

    def delete(self, collection, record_id):
        with self.atomic():
            self._db[collection].delete_one({'_id': record_id}, session=self._session)
