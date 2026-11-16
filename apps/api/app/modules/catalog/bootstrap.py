"""Idempotent import: owner bank stays raw. Authored examples are explicit local demos."""
import json
import re
from collections import Counter
from pathlib import Path
from app.core.values import uid
from app.modules.catalog.schemas import Content

ROOT = Path(__file__).resolve().parents[5]
MAPPING = {'D': 'detachment', 'R': 'relaxation', 'A1': 'autonomy', 'M1': 'mastery', 'M2': 'meaning', 'A2': 'affiliation'}
# These first-pass fillers were overwhelmingly similar mental exercises. Preserve
# their keys for inspection, but keep them out of the active local catalog.
RETIRED_DEMO_KEYS = frozenset(f'demo:{i:03}' for i in range(7, 25))


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
    if len({key for key, _ in entries}) != len(entries):
        raise ValueError('Duplicate demo keys')
    validated = [(key, Content.model_validate(raw).model_dump()) for key, raw in entries]
    if len({c['title'] for _, c in validated}) != len(validated):
        raise ValueError('Duplicate demo titles')
    return validated


def seed_demo(store, clock):
    examples = demo_examples()
    existing = {a['seed_key'] for a in store.list('activities')}
    pending = [(key, content) for key, content in examples if key not in existing]
    for offset in range(0, len(pending), 25):
        with store.atomic():
            for key, content in pending[offset:offset + 25]:
                if key in existing:
                    continue
                activity_id, revision_id = uid(), uid()
                retired = key in RETIRED_DEMO_KEYS
                store.insert('activities', dict(id=activity_id, seed_key=key, raw_title=content['title'],
                    raw_intent='نمونهٔ تألیفی برای اجرای محلی، بدون تأیید انتشار عمومی',
                    primary_dimension=content['primary_dimension'], active=not retired,
                    published_revision_id=None if retired else revision_id,
                    next_revision_number=2, start_guard_version=0, created_at=clock()))
                store.insert('activity_revisions', dict(id=revision_id, activity_id=activity_id, revision_number=1,
                    draft_version=1, state='archived' if retired else 'published', content=content, origin='demo',
                    validation_report={'schema_valid': True, 'local_demo_only': True, 'human_approval': False,
                        'catalog_version': 'demo_catalog_v2', 'retired_demo': retired},
                    reviewed_by=None, published_at=None if retired else clock(), created_at=clock()))
