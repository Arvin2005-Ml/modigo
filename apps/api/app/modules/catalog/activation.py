"""Read-only editorial work queue; activation always uses the normal review path."""
from collections import Counter, defaultdict
from typing import Literal

from app.modules.catalog.bootstrap import RETIRED_DEMO_KEYS
from app.modules.catalog.deduplication import identity

ActivationStatus = Literal['active', 'raw_seed', 'retired_demo', 'duplicate_of_active',
                           'withdrawn', 'needs_content', 'needs_review', 'needs_publish', 'needs_new_revision']


def activation_queue(catalog, actor, status: ActivationStatus | None, offset, limit):
    with catalog.store.atomic():
        catalog.authorize(actor)
        activities = catalog.store.list('activities')
        revisions = defaultdict(list)
        for revision in catalog.store.list('activity_revisions'):
            revisions[revision['activity_id']].append(revision)
        candidates = {row['id']: row for row in catalog.candidates()}
    published = {identity(row['content']): row['id'] for row in candidates.values()}
    totals = Counter()
    matches = []
    for activity in sorted(activities, key=lambda row: (row.get('seed_key', ''), row['id'])):
        activity_id = activity['id']
        rows = sorted(revisions[activity_id], key=lambda row: row['revision_number'], reverse=True)
        current = candidates.get(activity_id)
        newest = next((row for row in rows if row['state'] in ('draft', 'rejected', 'review')), None)
        base = newest or (rows[0] if rows else None)
        content = catalog.checked_content(base.get('content'), activity['primary_dimension']) if base else None
        duplicate = published.get(identity(content.model_dump())) if content else None
        if current:
            state = 'active'
            revision_id = current['revision_id']
        else:
            revision_id = base['id'] if base else None
            if activity.get('withdrawn'):
                state = 'withdrawn'
            elif activity.get('seed_key') in RETIRED_DEMO_KEYS and not newest:
                state = 'retired_demo'
            elif duplicate and duplicate != activity_id:
                state = 'duplicate_of_active'
            elif newest and content:
                state = 'needs_publish' if newest['state'] == 'review' else 'needs_review'
            elif activity.get('seed_key', '').startswith('bank:') and not any(row.get('content') for row in rows):
                state = 'raw_seed'
            elif newest or content is None:
                state = 'needs_content'
            else:
                state = 'needs_new_revision'
        totals[state] += 1
        if status is None or state == status:
            matches.append(dict(activity_id=activity_id, revision_id=revision_id, seed_key=activity.get('seed_key'),
                                title=activity.get('raw_title') or (content.title if content else ''),
                                status=state, duplicate_of_activity_id=duplicate if state == 'duplicate_of_active' else None))
    return dict(counts=dict(totals), total=len(matches), items=matches[offset:offset + limit],
                next_offset=offset + limit if offset + limit < len(matches) else None)
