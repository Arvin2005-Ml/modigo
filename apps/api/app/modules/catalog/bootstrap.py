"""Idempotent import: owner bank stays raw. Authored examples are explicit local demos."""
import json
import hashlib
import re
from collections import Counter
from pathlib import Path
from app.core.values import uid, replace
from app.modules.catalog.schemas import Content

ROOT = Path(__file__).resolve().parents[5]
MAPPING = {'D': 'detachment', 'R': 'relaxation', 'A1': 'autonomy', 'M1': 'mastery', 'M2': 'meaning', 'A2': 'affiliation'}
# These first-pass fillers were overwhelmingly similar mental exercises. Preserve
# their keys for inspection, but keep them out of the active local catalog.
RETIRED_DEMO_KEYS = frozenset(f'demo:{i:03}' for i in range(7, 25))


def iran_catalog():
    """Authored conditional plans, never a claim of live venue availability."""
    catalog = json.loads((ROOT / 'content/iran-catalog.json').read_text(encoding='utf-8'))
    if catalog['version'] != 'iran_catalog_v1' or len(catalog['entries']) != 300:
        raise ValueError('Expected the versioned catalog of 300 Iran plans')
    entries = catalog['entries']
    if len({entry['key'] for entry in entries}) != len(entries):
        raise ValueError('Duplicate Iran catalog keys')
    for entry in entries:
        if (not entry['content'].get('requires_venue_check')
                or entry['content']['cost']['kind'] != 'unknown'
                or entry['availability_verified'] or entry['price_verified']
                or not entry['source_ids']
                or any(source not in catalog['sources'] for source in entry['source_ids'])):
            raise ValueError('Invalid availability or evidence metadata')
    return catalog


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


def demo_examples():
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
    entries += [('demo:' + entry['key'], entry['content']) for entry in iran_catalog()['entries']]
    if len({key for key, _ in entries}) != len(entries):
        raise ValueError('Duplicate demo keys')
    validated = [(key, Content.model_validate(raw).model_dump()) for key, raw in entries]
    if len({c['title'] for _, c in validated}) != len(validated):
        raise ValueError('Duplicate demo titles')
    return validated


def seed_demo(store, clock):
    examples = demo_examples()
    iran = iran_catalog()
    metadata = {'demo:' + entry['key']: {k: v for k, v in entry.items() if k != 'content'}
                for entry in iran['entries']}
    existing = {a['seed_key'] for a in store.list('activities')}
    pending = [(key, content) for key, content in examples if key not in existing]
    for offset in range(0, len(pending), 25):
        with store.atomic():
            for key, content in pending[offset:offset + 25]:
                if key in existing:
                    continue
                activity_id, revision_id = uid(), uid()
                retired = key in RETIRED_DEMO_KEYS
                extra = metadata.get(key)
                provenance = dict(source_file='content/iran-catalog.json', source_metadata={
                    **extra, 'sources': {name: iran['sources'][name] for name in extra['source_ids']}}) if extra else {}
                store.insert('activities', dict(id=activity_id, seed_key=key, raw_title=content['title'],
                    raw_intent='نمونهٔ تألیفی برای اجرای محلی، بدون تأیید انتشار عمومی',
                    primary_dimension=content['primary_dimension'], active=not retired,
                    published_revision_id=None if retired else revision_id,
                    next_revision_number=2, start_guard_version=0, created_at=clock(), **provenance))
                store.insert('activity_revisions', dict(id=revision_id, activity_id=activity_id, revision_number=1,
                    draft_version=1, state='archived' if retired else 'published', content=content, origin='demo',
                    validation_report={'schema_valid': True, 'local_demo_only': True, 'human_approval': False,
                        'dramma_version': 'dramma_v1',
                        'catalog_version': 'iran_catalog_v1' if extra else 'demo_catalog_v2',
                        'retired_demo': retired, **({'availability_verified': False,
                            'price_verified': False, 'evidence_scope': extra['evidence_scope'],
                            'source_ids': extra['source_ids']} if extra else {})},
                    reviewed_by=None, published_at=None if retired else clock(), created_at=clock()))
    upgrade_demo_alignment(store, clock, examples)


def content_checksum(content):
    # Old validated Content included this default even when its source omitted it.
    normalized = {'requires_venue_check': False, **content}
    if normalized.get('place') is None:
        normalized.pop('place', None)
    return hashlib.sha256(json.dumps(normalized, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), default=str).encode()).hexdigest()


def upgrade_demo_alignment(store, clock, examples):
    """New revisions only for exact shipped demos; never overwrite editorial work."""
    legacy = json.loads((ROOT / 'content/dramma-legacy-checksums.json').read_text())['checksums']
    updated = dict(examples)
    revisions = {r['id']: r for r in store.list('activity_revisions')}
    for candidate in store.list('activities'):
        key = candidate.get('seed_key')
        old = revisions.get(candidate.get('published_revision_id'))
        if (key not in updated or not candidate['active'] or candidate.get('withdrawn')
                or not old or old.get('origin') != 'demo' or old['state'] != 'published'
                or old.get('reviewed_by') or old.get('validation_report', {}).get('human_approval')
                or not old.get('content') or content_checksum(old['content']) != legacy.get(key)):
            continue
        with store.atomic():
            activity = store.get('activities', candidate['id'])
            current = store.get('activity_revisions', activity.get('published_revision_id') or '')
            # Recheck inside the transaction against concurrent edit/withdraw/publish.
            if (not activity['active'] or activity.get('withdrawn') or not current
                    or current != old):
                continue
            content = updated[key]
            revision_id = uid()
            store.insert('activity_revisions', dict(id=revision_id, activity_id=activity['id'],
                revision_number=activity['next_revision_number'], draft_version=1, state='published',
                content=content, origin='demo', reviewed_by=None, published_at=clock(), created_at=clock(),
                validation_report={**old.get('validation_report', {}), 'schema_valid': True,
                    'dramma_version': 'dramma_v1', 'alignment_migration': 'dramma_v1',
                    'previous_revision_id': old['id'], 'human_approval': False, 'local_demo_only': True}))
            current['state'] = 'superseded'
            replace(store, 'activity_revisions', current)
            activity.update(published_revision_id=revision_id,
                primary_dimension=content['primary_dimension'],
                next_revision_number=activity['next_revision_number'] + 1)
            replace(store, 'activities', activity)
            store.insert('admin_audit', dict(id=uid(), actor_id='system', action='demo_dramma_aligned',
                target_id=revision_id, reason='dramma_v1: exact shipped demo only', created_at=clock()))
