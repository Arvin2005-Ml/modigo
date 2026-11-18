"""Idempotent import: owner bank stays raw. Authored examples are explicit local demos."""
import json
import re
from collections import Counter
from hashlib import sha256
from pathlib import Path
from app.core.values import uid, replace
from app.modules.catalog.schemas import Content

ROOT = Path(__file__).resolve().parents[5]
MAPPING = {'D': 'detachment', 'R': 'relaxation', 'A1': 'autonomy', 'M1': 'mastery', 'M2': 'meaning', 'A2': 'affiliation'}
# These first-pass fillers were overwhelmingly similar mental exercises. Preserve
# their keys for inspection, but keep them out of the active local catalog.
RETIRED_DEMO_KEYS = frozenset(f'demo:{i:03}' for i in range(7, 25))

def content_checksum(content):
    # Null place did not exist in the checksum format for shipped demos.
    canonical = {key: value for key, value in content.items()
                 if key not in ('place', 'outing') or value is not None}
    return sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), default=str).encode()).hexdigest()


def align_demo_content(raw):
    """Add evidence only to the repository's authored demo and provider fixtures."""
    if 'dramma' in raw:
        return raw
    labels = {
        'detachment': 'توجهت را از مشغلهٔ قبلی به این کار ببری',
        'relaxation': 'بدون عجله زمانی برای استراحت داشته باشی',
        'autonomy': 'انتخاب کنی این تجربه چطور پیش برود',
        'mastery': 'یک کار کوچک را امتحان کنی و مهارتت را تمرین کنی',
        'meaning': 'به چیزی که برایت ارزش دارد توجه کنی',
        'affiliation': 'از راه یک کار مشترک با همراهت ارتباط بگیری',
    }
    return {**raw, 'dramma': {'version': 'dramma_v1', 'mechanisms': [
        {'dimension': dimension, 'intent': f'با انجام گام دوم فرصت داری {labels[dimension]}.',
         'step_indexes': [2]}
        for dimension in (raw['primary_dimension'], *raw['secondary_dimensions'])
    ]}}


def iran_catalog():
    return json.loads((ROOT / 'content/iran-catalog.json').read_text(encoding='utf-8'))


def seed_bank(store, clock):
    bank = json.loads((ROOT / 'DRAMMA_450_activities_fa.json').read_text())
    rows = [(MAPPING[c['id']], row) for c in bank['categories'] for row in c['activities']]
    if len(rows) != 450 or any(n != 75 for n in Counter(d for d, _ in rows).values()):
        raise ValueError('Expected six dimensions with 75 raw activities each')
    if len({r['id'] for _, r in rows}) != 450:
        raise ValueError('Duplicate source keys')
    existing = {a['seed_key'] for a in store.list('activities')}
    pending = [(dimension, raw) for dimension, raw in rows if 'bank:' + raw['id'] not in existing]
    for offset in range(0, len(pending), 25):
        with store.atomic():
            for dimension, raw in pending[offset:offset + 25]:
                key = 'bank:' + raw['id']
                if key in existing:
                    continue
                activity_id = uid()
                store.insert('activities', dict(id=activity_id, seed_key=key, source_key=raw['id'],
                    source_file='DRAMMA_450_activities_fa.json', source_metadata=raw,
                    primary_dimension=dimension, raw_title=raw['title'], raw_intent='', active=False,
                    published_revision_id=None, next_revision_number=2, start_guard_version=0, created_at=clock()))
                store.insert('activity_revisions', dict(id=uid(), activity_id=activity_id, revision_number=1,
                    draft_version=1, state='draft', content=None, origin='human', validation_report={}, created_at=clock()))


def demo_examples(*, include_iran=False):
    """Load authored fixtures with stable keys; never cook or publish the raw bank."""
    text = (ROOT / 'content/cooked-examples.md').read_text()
    examples = [json.loads(block) for block in re.findall(r'```json\n(.*?)\n```', text, re.S)]
    examples += json.loads((ROOT / 'content/demo-extra.json').read_text())
    if len(examples) != 24:
        raise ValueError('Expected 24 original demo examples')
    entries = [(f'demo:{i:03}', raw) for i, raw in enumerate(examples, 1)]
    supplement = json.loads((ROOT / 'content/demo-catalog.json').read_text())
    if supplement['version'] != 'demo_catalog_v2':
        raise ValueError('Unsupported demo catalog version')
    entries += [('demo:' + entry['key'], entry['content']) for entry in supplement['entries']]
    if include_iran:
        entries += [('demo:' + entry['key'], entry['content']) for entry in iran_catalog()['entries']]
    if len({key for key, _ in entries}) != len(entries):
        raise ValueError('Duplicate demo keys')
    validated = [(key, Content.model_validate(align_demo_content(raw)).model_dump()) for key, raw in entries]
    if len({c['title'] for _, c in validated}) != len(validated):
        raise ValueError('Duplicate demo titles')
    return validated


def seed_demo(store, clock, *, include_iran=False):
    examples = demo_examples(include_iran=include_iran)
    iran = iran_catalog() if include_iran else None
    iran_entries = {'demo:' + entry['key']: entry for entry in iran['entries']} if iran else {}
    existing = {a['seed_key'] for a in store.list('activities')}
    pending = [(key, content) for key, content in examples if key not in existing]
    for offset in range(0, len(pending), 25):
        with store.atomic():
            for key, content in pending[offset:offset + 25]:
                if key in existing:
                    continue
                activity_id, revision_id = uid(), uid()
                retired = key in RETIRED_DEMO_KEYS
                provenance, validation = {}, {}
                if entry := iran_entries.get(key):
                    provenance = {'source_file': 'content/iran-catalog.json', 'source_metadata': {
                        'sources': {sid: iran['sources'][sid] for sid in entry['source_ids']}}}
                    validation.update(availability_verified=False, price_verified=False)
                store.insert('activities', dict(id=activity_id, seed_key=key, raw_title=content['title'],
                    raw_intent='نمونهٔ تألیفی برای اجرای محلی، بدون تأیید انتشار عمومی',
                    primary_dimension=content['primary_dimension'], active=not retired,
                    published_revision_id=None if retired else revision_id,
                    next_revision_number=2, start_guard_version=0, created_at=clock(), **provenance))
                store.insert('activity_revisions', dict(id=revision_id, activity_id=activity_id, revision_number=1,
                    draft_version=1, state='archived' if retired else 'published', content=content, origin='demo',
                    validation_report={'schema_valid': True, 'local_demo_only': True, 'human_approval': False,
                        'catalog_version': 'demo_catalog_v2', 'retired_demo': retired, **validation},
                    reviewed_by=None, published_at=None if retired else clock(), created_at=clock()))
    # Only pristine shipped demo revisions qualify; their immutable content stays in history.
    checksums = json.loads((ROOT / 'content/dramma-legacy-checksums.json').read_text())['checksums']
    revisions = {r['id']: r for r in store.list('activity_revisions') if r['state'] == 'published'}
    entries = dict(examples)
    for activity in store.list('activities'):
        expected = checksums.get(activity.get('seed_key'))
        fresh = entries.get(activity.get('seed_key'))
        old = revisions.get(activity.get('published_revision_id'))
        if not (fresh and expected and old and activity['active'] and not activity.get('withdrawn')
                and old['origin'] == 'demo' and not old.get('reviewed_by')
                and not old.get('validation_report', {}).get('human_approval') and old.get('content')
                and 'dramma' not in old['content']
                and content_checksum({'requires_venue_check': False, **old['content']}) == expected):
            continue
        with store.atomic():
            if store.get('activities', activity['id']) != activity or store.get('activity_revisions', old['id']) != old:
                continue
            revision_id = uid()
            store.insert('activity_revisions', dict(id=revision_id, activity_id=activity['id'],
                revision_number=activity['next_revision_number'], draft_version=1, state='published',
                content=fresh, origin='demo', reviewed_by=None, published_at=clock(), created_at=clock(),
                validation_report={**old.get('validation_report', {}), 'dramma_version': 'dramma_v1',
                                   'human_approval': False}))
            replace(store, 'activity_revisions', {**old, 'state': 'superseded'})
            replace(store, 'activities', {**activity, 'published_revision_id': revision_id,
                                         'next_revision_number': activity['next_revision_number'] + 1})
            store.insert('admin_audit', dict(id=uid(), actor_id='system', action='demo_dramma_aligned',
                target_id=revision_id, reason='Alignment of the exact shipped demo fixture', created_at=clock()))
