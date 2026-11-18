"""Create a small, sourced cinema batch without changing the existing 700 release."""
from app.modules.catalog.unified import release, write_release
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('real_catalog_builder', ROOT / 'scripts/build-real-catalog.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
from app.modules.catalog.schemas import Content


def main():
    original = release('real_catalog_v1')
    existing = {(e['content']['place']['city'], e['content']['place']['name'])
                for e in original['entries'] if e['content']['place']}
    sources, entries, seen = {}, [], set()
    for line in (ROOT / 'content/cinema-expansion.txt').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        city, name, page = line.split('|')
        if (city, name) in existing or (city, name) in seen:
            raise ValueError('Duplicate place: ' + city + ' ' + name)
        seen.add((city, name))
        source_id = 'cinema-national-' + page
        url = 'https://irangaah.ir/stats/cinema' + ('?page=' + page if page != '1' else '')
        source = {'url': url, 'publisher': 'ایران‌گاه، بازنشر فهرست سینماهای کشور',
                  'researched_on': builder.DATE, 'scope': 'place_and_activity_type_only',
                  'availability_verified': False, 'price_verified': False}
        sources[source_id] = source
        content = builder.venue_content(city, name, 'cinema', 'تماشای یک فیلم از برنامهٔ روز', source)
        content['conditions_note'] = ('این سینما در فهرست منتشرشدهٔ سال ۱۴۰۴ آمده؛ بازبودن فعلی، سانس، قیمت، ظرفیت و مسیر را پیش از مراجعه از منبع معتبر بررسی کن. '
                                      'زمان رفت‌وبرگشت این برنامه حداکثر ۶۰ دقیقه فرض شده است.')
        entries.append({'key': builder.stable_key('place', city, name, 'cinema'), 'category': 'cinema',
                        'source_ids': [source_id], 'availability_verified': False, 'price_verified': False,
                        'content': Content.model_validate(content).model_dump(mode='json')})
    if len({e['key'] for e in entries}) != len(entries):
        raise ValueError('Duplicate stable key')
    data = {'version': 'cinema_expansion_v1', 'researched_on': builder.DATE,
            'publication_basis': 'owner_request_2026_11_14',
            'evidence_scope': 'historical_listing_not_live_availability_or_empirical_dramma_validation',
            'sources': sources, 'entries': entries}
    write_release(data)
    rows = ['# سینماهای افزوده‌شده', '', 'منبع این موارد فهرست تاریخی سال ۱۴۰۴ است؛ سانس، بازبودن و قیمت روز تأیید نشده‌اند.', '']
    for entry in entries:
        place = entry['content']['place']
        rows.append(f"- {place['city']} — [{place['name']}]({place['source_url']})")
    (ROOT / 'content/cinema-expansion-index.md').write_text('\n'.join(rows) + '\n')
    cities = sorted({e['content']['place']['city'] for e in original['entries'] if e['content']['place']} |
                    {e['content']['place']['city'] for e in entries})
    print(f'Validated {len(entries)} cinema records; {len(cities)} cities across both releases.')


if __name__ == '__main__':
    main()
