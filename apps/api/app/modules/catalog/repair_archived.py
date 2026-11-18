"""Prepare current-schema review revisions from exact archived demo fixtures."""
from collections import Counter, defaultdict
from dataclasses import dataclass
import argparse
import json
import sys

from pydantic import ValidationError
from app.core.errors import DomainError
from app.core.storage import StorageUnavailable, create_store
from app.core.values import replace, uid, utcnow
from app.modules.catalog.bootstrap import ROOT, RETIRED_DEMO_KEYS, content_checksum, demo_examples
from app.modules.catalog.schemas import Content

MIGRATION = 'archived_demo_dramma_v1'
ARCHIVE_RELEASE = 'real_catalog_v1'
BATCH_SIZE = 25


class RepairRefused(ValueError):
    """The inventory no longer matches the migration's narrow scope."""


@dataclass(frozen=True)
class Repair:
    activity: dict
    archive: dict
    content: dict
    checksum: str


def plan_repairs(activities, revisions):
    checksums = json.loads((ROOT / 'content/dramma-legacy-checksums.json').read_text())['checksums']
    source = dict(demo_examples(include_iran=True))
    by_activity = defaultdict(list)
    for revision in revisions:
        by_activity[revision['activity_id']].append(revision)
    pending, statuses = [], Counter()
    for a in sorted(activities, key=lambda row: row.get('seed_key', '')):
        key = a.get('seed_key', '')
        if key in RETIRED_DEMO_KEYS:
            statuses['retired_filler_excluded'] += 1
            continue
        if key not in source or a.get('retired_by_catalog') != ARCHIVE_RELEASE:
            continue
        rows = by_activity[a['id']]
        # Keep detecting a completed migration after a later editorial publish
        # moves the activity's current pointer.
        prepared = [r for r in rows if r.get('repair', {}).get('migration') == MIGRATION]
        if len(prepared) == 1:
            fresh = prepared[0]
            old = next((r for r in rows if r['id'] == fresh['repair']['source_revision_id']), None)
            if old and old['state'] == 'archived' and old.get('content') and (
                    content_checksum({'requires_venue_check': False, **old['content']})
                    == fresh['repair']['source_checksum'] == checksums.get(key)):
                statuses['already_prepared'] += 1
                statuses['prepared_state_' + fresh['state']] += 1
                if fresh['state'] == 'review':
                    try:
                        content = Content.model_validate(fresh.get('content'))
                    except ValidationError:
                        content = None
                    if (content and content.primary_dimension == a['primary_dimension']
                            and a.get('active') is False and not a.get('withdrawn')
                            and a.get('published_revision_id') == old['id']
                            and not fresh.get('reviewed_by') and not fresh.get('published_at')
                            and not fresh.get('validation_report', {}).get('human_approval')
                            and content_checksum(fresh['content']) == fresh['repair'].get('review_checksum')):
                        statuses['prepared_verified_for_review'] += 1
                    else:
                        statuses['invalid_prepared_review'] += 1
                continue
        if a.get('active') or a.get('withdrawn') or len(rows) != 1:
            statuses['protected_activity_or_history'] += 1
            continue
        old = rows[0]
        if (old['id'] != a.get('published_revision_id') or old['state'] != 'archived'
                or old.get('origin') != 'demo' or old.get('reviewed_by') or old.get('reviewed_at')
                or old.get('validation_report', {}).get('human_approval')):
            statuses['protected_revision'] += 1
            continue
        content = old.get('content')
        checksum = content_checksum({'requires_venue_check': False, **content}) if isinstance(content, dict) else None
        if not checksum or checksum != checksums.get(key) or 'dramma' in content:
            statuses['unexpected_content'] += 1
            continue
        if type(a.get('next_revision_number')) is not int or a['next_revision_number'] <= old['revision_number']:
            statuses['invalid_next_revision_number'] += 1
            continue
        pending.append(Repair(a, old, source[key], checksum))
        statuses['pending'] += 1
        statuses['pending_changed_dimension'] += source[key]['primary_dimension'] != a['primary_dimension']
        statuses['pending_venue_plans'] += source[key]['requires_venue_check']
    return pending, dict(statuses)


def check_plan(statuses, expected):
    known = statuses.get('pending', 0) + statuses.get('already_prepared', 0)
    blockers = ('protected_activity_or_history', 'protected_revision', 'unexpected_content',
                'invalid_next_revision_number', 'invalid_prepared_review')
    if known != expected or any(statuses.get(key, 0) for key in blockers):
        raise RepairRefused('Archived inventory differs from the reviewed migration scope; no batch started.')


def apply_repairs(store, clock, pending):
    completed = 0
    for offset in range(0, len(pending), BATCH_SIZE):
        batch = pending[offset:offset + BATCH_SIZE]
        with store.atomic():
            for item in batch:
                a = store.get('activities', item.activity['id'])
                old = store.get('activity_revisions', item.archive['id'])
                if a != item.activity or old != item.archive:
                    raise RepairRefused('An archive or activity changed after preview; the current batch was rolled back.')
                timestamp, revision_id = clock(), uid()
                store.insert('activity_revisions', dict(
                    id=revision_id, activity_id=a['id'], revision_number=a['next_revision_number'],
                    draft_version=2, state='review', content=item.content, origin='demo',
                    created_at=timestamp, reviewed_by=None, reviewed_at=None, published_at=None,
                    repair={'migration': MIGRATION, 'source_revision_id': old['id'],
                            'source_checksum': item.checksum, 'source_primary_dimension': a['primary_dimension'],
                            'review_checksum': content_checksum(item.content)},
                    validation_report={'schema_valid': True, 'dramma_version': 'dramma_v1',
                                       'human_approval': False, 'availability_verified': False,
                                       'price_verified': False, 'local_demo_only': True}))
                replace(store, 'activities', {**a, 'next_revision_number': a['next_revision_number'] + 1,
                                              'primary_dimension': item.content['primary_dimension']})
                store.insert('admin_audit', dict(
                    id=uid(), actor_id='system', action='archived_demo_repaired_for_review',
                    target_id=revision_id, reason=MIGRATION, created_at=timestamp))
        completed += len(batch)
    return completed


def mongo_snapshot(uri):
    from datetime import timezone
    from bson.codec_options import CodecOptions
    from pymongo.errors import PyMongoError
    from app.core.mongo_connection import create_mongo_client, mongo_failure
    try:
        with create_mongo_client(uri) as client, client.start_session(snapshot=True) as session:
            db = client.get_default_database(codec_options=CodecOptions(tz_aware=True, tzinfo=timezone.utc))
            if db.name in ('admin', 'config', 'local'):
                raise RepairRefused('Select the application database.')
            return tuple(list(db[name].find({}, {'_id': False}, session=session))
                         for name in ('activities', 'activity_revisions'))
    except PyMongoError as exc:
        raise mongo_failure(exc, 'read') from None


def main(argv=None):
    from app.core.config import Settings
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Prepare the reviewed scope in real MongoDB')
    parser.add_argument('--expect-count', type=int, default=413)
    args = parser.parse_args(argv)
    store = None
    try:
        settings = Settings.load()
        pending, before = plan_repairs(*mongo_snapshot(settings.mongodb_uri))
        print(json.dumps({'mode': 'read_only_preview', 'migration': MIGRATION, **before}), flush=True)
        if not args.apply:
            return 0
        check_plan(before, args.expect_count)
        if pending:
            store = create_store({'DATA_BACKEND': settings.data_backend, 'MONGODB_URI': settings.mongodb_uri})
        prepared = apply_repairs(store, utcnow, pending)
        _, after = plan_repairs(*mongo_snapshot(settings.mongodb_uri))
        check_plan(after, args.expect_count)
        if after.get('pending', 0):
            raise RepairRefused('Some revisions are still pending; rerun the read-only preview.')
        print(json.dumps({'mode': 'applied_real_mongodb', 'created': prepared, **after}), flush=True)
        return 0
    except (StorageUnavailable, RepairRefused, DomainError) as exc:
        if isinstance(exc, DomainError):
            print('An activity changed during repair; rerun the read-only preview.', file=sys.stderr)
        else:
            print(str(exc), file=sys.stderr)
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
