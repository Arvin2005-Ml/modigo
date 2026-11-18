"""Build a source-backed batch of distinct museums, attractions and venues."""
from app.modules.catalog.unified import release, write_release
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('food_builder', ROOT / 'scripts/build-food-expansion.py')
food_builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(food_builder)
builder = food_builder.builder
from app.core.schemas import normalize_city
from app.modules.catalog.schemas import Content

VERSION = 'visit_expansion_v1'


def main():
    old = []
    for version in ('real_catalog_v1', 'cinema_expansion_v1', 'food_expansion_v1'):
        old.extend(release(version)['entries'])
    existing = {(e['content']['place']['city'], food_builder.comparable(e['content']['place']['name']))
                for e in old if e['content']['place']}
    sources, entries, seen, current = {}, [], set(), None
    for line in (ROOT / 'content/visit-expansion.txt').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        if line.startswith('@'):
            current, url, publisher = line[1:].split('|')
            sources[current] = {'url': url, 'publisher': publisher, 'researched_on': builder.DATE,
                                'scope': 'place_and_activity_type_only', 'availability_verified': False,
                                'price_verified': False}
            continue
        city, name, kind, focus = line.split('|')
        city = normalize_city(city)
        identity = (city, food_builder.comparable(name))
        if identity in existing or identity in seen:
            raise ValueError('Duplicate venue: ' + city + ' ' + name)
        if not current:
            raise ValueError('Missing source')
        seen.add(identity)
        content = builder.venue_content(city, name, kind, focus, sources[current])
        content['conditions_note'] = ('منبع معرفی، وجود محل و نوع تجربه را توضیح می‌دهد؛ بازبودن امروز، '
            'بلیت، شرایط پذیرش، قیمت و مسیر را از مسئول مجموعه بررسی کن. رفت‌وبرگشت حداکثر ۶۰ دقیقه فرض شده است.')
        if kind == 'restaurant':
            content['steps'][0] = (f'نشانی {name} را در منبع ببین؛ بازبودن، امکان صرف حضوری، '
                                   'هزینه و شرایط پذیرش را از مجموعه بررسی کن.')
            content['first_step'] = content['steps'][0]
        entries.append({'key': builder.stable_key('place', city, name, kind), 'category': kind,
                        'source_ids': [current], 'availability_verified': False, 'price_verified': False,
                        'content': Content.model_validate(content).model_dump(mode='json')})
    keys = [e['key'] for e in entries]
    if len(set(keys)) != len(keys) or set(keys) & {e['key'] for e in old}:
        raise ValueError('Duplicate stable key')
    data = {'version': VERSION, 'researched_on': builder.DATE, 'publication_basis': 'owner_request_2026_11_14',
            'evidence_scope': 'tourism_description_not_live_availability_or_empirical_dramma_validation',
            'sources': sources, 'entries': entries}
    write_release(data)
    rows = ['# بازدیدها و تجربه‌های شهری افزوده‌شده', '',
            'منابع وجود مکان و نوع آن را توضیح می‌دهند؛ شرایط روز و قیمت تأیید نشده است.', '']
    for entry in entries:
        place = entry['content']['place']
        rows.append(f"- {place['city']} — [{place['name']}]({place['source_url']})")
    (ROOT / 'content/visit-expansion-index.md').write_text('\n'.join(rows) + '\n')
    print(f'Validated {len(entries)} sourced venue experiences.')


if __name__ == '__main__':
    main()
