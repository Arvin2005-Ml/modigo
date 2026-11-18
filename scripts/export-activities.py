"""Export checked-in catalog sources without connecting to application storage."""
import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/api'))

from app.modules.catalog.bootstrap import MAPPING, RETIRED_DEMO_KEYS, demo_examples
from app.modules.catalog.schemas import Content


def load_json(relative_path):
    return json.loads((ROOT / relative_path).read_text(encoding='utf-8'))


def flatten_fields(value, prefix=''):
    result = {}
    for key, item in value.items():
        name = f'{prefix}.{key}' if prefix else key
        if isinstance(item, dict) and item:
            result.update(flatten_fields(item, name))
        else:
            result[name] = item
    return result


def csv_value(value):
    if value is None:
        return ''
    if isinstance(value, (list, dict, bool)):
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    return value


def build_export():
    bank = load_json('DRAMMA_450_activities_fa.json')
    fixtures = load_json('content/demo-cook-fixtures.json')
    rows, cooked, prepared_fixtures = [], [], []
    source_keys = set()
    dimensions = Counter()
    for category in bank['categories']:
        if len(category['activities']) != 75:
            raise ValueError('Expected 75 source activities in each category')
        dimension = MAPPING[category['id']]
        for source in category['activities']:
            source_keys.add(source['id'])
            dimensions[dimension] += 1
            rows.append({
                'seed_key': 'bank:' + source['id'],
                'record_kind': 'raw_seed',
                'source_file': 'DRAMMA_450_activities_fa.json',
                'primary_dimension': dimension,
                'category': {key: value for key, value in category.items() if key != 'activities'},
                'source_metadata': source,
                'raw_title': source['title'],
                'raw_intent': '',
                'initial_state': 'draft',
                'initial_active': False,
                'has_cooked_content': False,
                'has_prepared_fixture': source['id'] in fixtures,
                'cooked_at': None,
                'human_approval': False,
            })
    if len(rows) != 450 or len(source_keys) != 450 or len(dimensions) != 6:
        raise ValueError('Expected 450 unique source activities across six dimensions')
    for key, content in demo_examples():
        retired = key in RETIRED_DEMO_KEYS
        if key in {f'demo:{number:03}' for number in range(1, 7)}:
            source_file = 'content/cooked-examples.md'
        elif retired:
            source_file = 'content/demo-extra.json'
        else:
            source_file = 'content/demo-catalog.json'
        entry = {
            'seed_key': key,
            'record_kind': 'cooked_demo',
            'source_file': source_file,
            'primary_dimension': content['primary_dimension'],
            'raw_title': content['title'],
            'raw_intent': 'نمونهٔ تألیفی برای اجرای محلی، بدون تأیید انتشار عمومی',
            'initial_state': 'archived' if retired else 'published',
            'initial_active': not retired,
            'has_cooked_content': True,
            'has_prepared_fixture': False,
            'cooked_at': None,
            'origin': 'demo',
            'catalog_version': 'demo_catalog_v2',
            'human_approval': False,
            'local_demo_only': True,
            'revision_number': 1,
            'total_minutes': sum(content[field] for field in ('active_minutes', 'setup_minutes', 'travel_minutes')),
            'content': content,
        }
        rows.append(entry)
        cooked.append(entry)
    for source_key, raw in fixtures.items():
        if source_key not in source_keys:
            raise ValueError('Cook fixture references an unknown source activity')
        content = Content.model_validate(raw).model_dump(mode='json')
        prepared_fixtures.append({
            'seed_key': 'bank:' + source_key,
            'source_file': 'content/demo-cook-fixtures.json',
            'state': 'prepared_fixture',
            'origin': 'demo',
            'human_approval': False,
            'local_demo_only': True,
            'cooked_at': None,
            'content': content,
        })
    if len({row['seed_key'] for row in rows}) != len(rows):
        raise ValueError('Duplicate export keys')
    payload = {
        'schema_version': '1.0',
        'exported_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'source': 'repository_files',
        'live_database_export': False,
        'language': 'fa',
        'counts': {
            'all_activities': len(rows),
            'raw_seeds': len(source_keys),
            'cooked_activities': len(cooked),
            'initially_active_cooked': sum(entry['initial_active'] for entry in cooked),
            'archived_cooked': sum(not entry['initial_active'] for entry in cooked),
            'prepared_fixtures': len(prepared_fixtures),
        },
        'notes': [
            'این خروجی از فایل‌های پروژه است؛ تغییرات و پخت‌های احتمالی MongoDB زنده در آن نیست.',
            'initial_state و initial_active وضعیت تعریف‌شده در ورود اولیه‌اند، نه وضعیت فعلی دیتابیس.',
            '۴۵۰ بذر خام منتشرشده یا پخته فرض نشده‌اند؛ متادیتای خام تخمینی یا نسبی است.',
            'نمونه‌های پخته تألیفی و نمایشی‌اند؛ خروجی واقعی مدل یا دارای تأیید انتشار عمومی نیستند.',
            'prepared_fixtures شش قالب آماده برای دکمهٔ پخت است؛ وجود قالب به‌معنای اجرای پخت بذر نیست.',
            'زمان واقعی پخت در فایل‌های منبع ثبت نشده و cooked_at برابر null است؛ exported_at زمان خروجی‌گرفتن است.',
        ],
        'raw_bank_metadata': {key: value for key, value in bank.items() if key != 'categories'},
        'activities': cooked,
        'prepared_fixtures': prepared_fixtures,
    }
    return rows, payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'exports')
    args = parser.parse_args()
    rows, payload = build_export()
    flattened = [flatten_fields(row) for row in rows]
    fieldnames = list(dict.fromkeys(key for row in flattened for key in row))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / 'activities.csv').open('w', encoding='utf-8-sig', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: csv_value(value) for key, value in row.items()} for row in flattened)
    (args.output_dir / 'cooked-activities.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(payload['counts'], ensure_ascii=False))


if __name__ == '__main__':
    main()
