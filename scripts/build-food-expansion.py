"""Build sourced dining experiences without claiming current opening or price."""
from app.modules.catalog.unified import release, write_release
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('real_catalog_builder', ROOT / 'scripts/build-real-catalog.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
from app.core.schemas import normalize_city
from app.modules.catalog.schemas import Content

VERSION = 'food_expansion_v1'
SOURCES = {
    city: {'url': f'https://nodik.dev/places/ir/{slug}/restaurant/',
           'publisher': 'فهرست مکان‌های نودیک', 'researched_on': builder.DATE,
           'scope': 'place_and_activity_type_only', 'availability_verified': False, 'price_verified': False}
    for city, slug in [('rasht', 'rasht'), ('shiraz', 'shiraz'), ('isfahan', 'isfahan')]
}


def comparable(value):
    value = normalize_city(value).casefold()
    value = re.sub(r'(رستوران|کافه|فست فود|پردیس|سینمایی|سینما)', '', value)
    return re.sub(r'[^\w]', '', value)


def main():
    old = []
    for version in ('real_catalog_v1', 'cinema_expansion_v1'):
        old.extend(release(version)['entries'])
    existing = {(e['content']['place']['city'], comparable(e['content']['place']['name']))
                for e in old if e['content']['place']}
    entries, seen = [], set()
    for line in (ROOT / 'content/food-expansion.txt').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        city, name, kind, source_id = line.split('|')
        city = normalize_city(city)
        identity = (city, comparable(name))
        if identity in existing or identity in seen:
            raise ValueError('Duplicate venue: ' + city + ' ' + name)
        seen.add(identity)
        source = SOURCES[source_id]
        content = builder.venue_content(city, name, kind, 'انتخاب یک وعده از منوی روز', source)
        content['steps'][0] = (f'در فهرست منبع، {name} را پیدا کن و پیش از رفتن بازبودن، امکان صرف حضوری، '
                               'نشانی، قیمت و شرایط پذیرش را از خود مجموعه بررسی کن.')
        content['first_step'] = content['steps'][0]
        content['conditions_note'] = ('نام و دستهٔ محل در فهرست گردآوری‌شده آمده است. بازبودن فعلی، امکان نشستن، '
                                      'مواد غذایی، قیمت و مسیر تأیید نشده؛ قبل از رفتن از مجموعه بپرس. '
                                      'زمان رفت‌وبرگشت حداکثر ۶۰ دقیقه فرض شده است.')
        entries.append({'key': builder.stable_key('place', city, name, kind), 'category': kind,
                        'source_ids': [source_id], 'availability_verified': False, 'price_verified': False,
                        'content': Content.model_validate(content).model_dump(mode='json')})
    if len({e['key'] for e in entries}) != len(entries):
        raise ValueError('Duplicate stable key')
    data = {'version': VERSION, 'researched_on': builder.DATE, 'publication_basis': 'owner_request_2026_11_14',
            'evidence_scope': 'directory_listing_not_live_availability_or_empirical_dramma_validation',
            'sources': SOURCES, 'entries': entries}
    write_release(data)
    rows = ['# رستوران‌ها و فست‌فودهای افزوده‌شده', '',
            'پیوندها فهرست شهر را نشان می‌دهند؛ امکان صرف حضوری و فعالیت روز تأیید نشده است.', '']
    for entry in entries:
        place = entry['content']['place']
        rows.append(f"- {place['city']} — [{place['name']}]({place['source_url']})")
    (ROOT / 'content/food-expansion-index.md').write_text('\n'.join(rows) + '\n')
    print(f'Validated {len(entries)} additional dining experiences.')


if __name__ == '__main__':
    main()
