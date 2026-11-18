"""Publish the exact repaired archive release after an explicit owner approval."""
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import sys
from urllib.error import URLError
from urllib.request import urlopen

from app.core.storage import StorageUnavailable, create_store
from app.core.values import replace, uid, utcnow
from app.modules.catalog.bootstrap import content_checksum
from app.modules.catalog.deduplication import identity
from app.modules.catalog.repair_archived import BATCH_SIZE, MIGRATION, check_plan, mongo_snapshot, plan_repairs
from app.modules.catalog.service import Catalog

PUBLICATION_BASIS = 'owner_approved_archived_release_2026_11_18'
PUBLIC_ORIGIN = 'https://moodigo.ir'
RELEASE_SIZE = 413


class PublishRefused(ValueError):
    """The release or online API no longer meets the prerequisites."""


@dataclass(frozen=True)
class Publication:
    activity: dict
    revision: dict
    archive: dict


def release_plan(activities, revisions, expected=RELEASE_SIZE):
    _, repair_stats = plan_repairs(activities, revisions)
    check_plan(repair_stats, expected)
    if repair_stats.get('pending', 0):
        raise PublishRefused('Some archived entries have no prepared revision.')
    by_id = {r['id']: r for r in revisions}
    by_activity = defaultdict(list)
    for revision in revisions:
        by_activity[revision['activity_id']].append(revision)
    identities = {}
    for activity in activities:
        current = by_id.get(activity.get('published_revision_id'))
        if not (activity.get('active') and current and current['state'] == 'published' and current.get('content')):
            continue
        identities.setdefault(identity(current['content']), set()).add(activity['id'])

    pending, counts = [], Counter()
    for activity in activities:
        repaired = [r for r in by_activity[activity['id']] if r.get('repair', {}).get('migration') == MIGRATION]
        if not repaired:
            continue
        if len(repaired) != 1:
            raise PublishRefused('Multiple repaired revisions share one activity.')
        revision = repaired[0]
        repair = revision['repair']
        archive = by_id.get(repair['source_revision_id'])
        parsed = Catalog.checked_content(revision.get('content'), activity['primary_dimension'])
        if (parsed is None or parsed.cost.kind == 'estimated' or archive is None
                or archive['activity_id'] != activity['id'] or archive['state'] != 'archived'
                or repair.get('review_checksum') != content_checksum(revision['content'])):
            raise PublishRefused('A repaired revision failed its content, provenance or cost check.')

        if revision['state'] == 'published' and activity.get('active') and not activity.get('withdrawn') and (
                activity.get('published_revision_id') == revision['id']):
            counts['already_published'] += 1
        elif (revision['state'] == 'review' and activity.get('active') is False and not activity.get('withdrawn')
                and activity.get('published_revision_id') == archive['id']
                and not revision.get('reviewed_by') and not revision.get('published_at')):
            pending.append(Publication(activity, revision, archive))
            counts['pending'] += 1
            counts['pending_venue_checks'] += parsed.requires_venue_check
        else:
            raise PublishRefused('A repaired activity is no longer in the authorized review or publication state.')

        fingerprint = identity(revision['content'])
        seen = identities.setdefault(fingerprint, set())
        if seen - {activity['id']}:
            raise PublishRefused('A repaired activity duplicates another candidate.')
        seen.add(activity['id'])
    if len(pending) + counts['already_published'] != expected:
        raise PublishRefused('The publication set does not match the authorized release size.')
    return pending, dict(counts)


def verify_online_contract():
    def fetch(path, limit):
        url = PUBLIC_ORIGIN + path
        try:
            with urlopen(url, timeout=12) as response:
                if response.geturl() != url:
                    raise PublishRefused('The online API redirected off its expected endpoint.')
                return json.loads(response.read(limit + 1))
        except (URLError, OSError, ValueError) as exc:
            raise PublishRefused('Could not verify the public API prerequisite on moodigo.ir.') from None

    health = fetch('/api/v1/health/ready', 8192)
    if not (isinstance(health, dict) and health.get('status') == 'ready' and health.get('data_backend') == 'mongo'):
        raise PublishRefused('The public API is not ready against MongoDB.')
    contract = fetch('/api/openapi.json', 2_000_000)
    try:
        props = contract['components']['schemas']['Context']['properties']
        opt_in = props['allow_venue_planning']
        checkin = contract['paths']['/api/v1/check-ins']['post']
        if opt_in['type'] == 'boolean' and opt_in['default'] is False and 'city' in props and checkin:
            return
    except (KeyError, TypeError):
        pass
    raise PublishRefused('The online API does not advertise the required city and venue opt-in contract.')


def publish_batches(store, clock, pending, verify=None):
    completed = 0
    for offset in range(0, len(pending), BATCH_SIZE):
        with store.atomic():
            for item in pending[offset:offset + BATCH_SIZE]:
                activity = store.get('activities', item.activity['id'])
                revision = store.get('activity_revisions', item.revision['id'])
                archive = store.get('activity_revisions', item.archive['id'])
                if activity != item.activity or revision != item.revision or archive != item.archive:
                    raise PublishRefused('The publication set changed; the current batch was rolled back.')
                at = clock()
                report = {**revision['validation_report'], 'publication_basis': PUBLICATION_BASIS,
                          'owner_release_approval': True, 'local_demo_only': False}
                replace(store, 'activity_revisions', {**revision, 'state': 'published',
                    'draft_version': revision['draft_version'] + 1, 'published_at': at,
                    'validation_report': report})
                replace(store, 'activities', {**activity, 'active': True, 'published_revision_id': revision['id']})
                store.insert('admin_audit', dict(id=uid(), actor_id='system',
                    action='archived_demo_published_by_owner_approval', target_id=revision['id'],
                    reason=PUBLICATION_BASIS, created_at=at))
                completed += 1
    return completed


def main(argv=None):
    from app.core.config import Settings
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Publish the owner-approved set in real MongoDB')
    args = parser.parse_args(argv)
    store = None
    try:
        settings = Settings.load()
        pending, before = release_plan(*mongo_snapshot(settings.mongodb_uri))
        print(json.dumps({'mode': 'read_only_preview', **before}), flush=True)
        if not args.apply:
            return 0
        verify_online_contract()
        if pending:
            store = create_store({'DATA_BACKEND': settings.data_backend, 'MONGODB_URI': settings.mongodb_uri})
        published = publish_batches(store, utcnow, pending)
        remaining, after = release_plan(*mongo_snapshot(settings.mongodb_uri))
        if remaining:
            raise PublishRefused('The release still contains unpublished revisions. Rerun the preview.')
        print(json.dumps({'mode': 'published_real_mongodb', 'published_now': published, **after}), flush=True)
        return 0
    except (StorageUnavailable, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
