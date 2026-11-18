"""Plans for sourced venues; times are allocations, and current operation is unverified."""
from functools import lru_cache
from urllib.parse import quote

from app.core.schemas import city_key
from app.modules.catalog.bootstrap import ROOT
from app.modules.catalog.cinema_expansion import import_additive
from app.modules.catalog.schemas import Content
from app.modules.catalog.unified import unified_catalog

VERSION = 'northern_outings_v1'
FILE = 'content/northern-outings.txt'
RESEARCHED_ON = '2026-11-18'
EVIDENCE = 'place_and_activity_type_only'

SOURCES = {
    'sari': ('ویزیت ایران؛ شهر ساری', 'https://visitiran.ir/fa/destination/' + quote('ساری')),
    'letka': ('فهرست رستوران‌های ساری؛ لتکا', 'https://res2ran.com/sari/letka'),
    'marble': ('ویزیت ایران؛ کاخ مرمر رامسر', 'https://visitiran.ir/attraction/marmar-palace-ramsar'),
    'moallem': ('ویزیت ایران؛ مسیر آستارا تا استرآباد', 'https://visitiran.ir/fa/' + quote('از آستارا تا اِسترآباد'.replace(' ', '-'))),
    'province': ('ویزیت ایران؛ مازندران', 'https://visitiran.ir/en/province/mazandaran-province'),
    'dreamland': ('ویزیت ایران؛ سرزمین رؤیاها', 'https://visitiran.ir/en/attraction/Dreamland--Amusement--Park'),
    'namak': ('ویزیت ایران؛ شهرک نمک‌آبرود', 'https://visitiran.ir/attraction/namakabrud-tourist-complex'),
    'shooka': ('هتل و رستوران شوکا', 'https://hotelshooka.ir/'),
    'chalus': ('بازنشر گزارش مهر از فرمانداری چالوس', 'https://www.cm8.ir/t/3/' + quote('فرمانداری-چالوس')),
}

# category: dimension, setting, movement, tags, what the plan is designed to provide.
PROFILES = {
    'museum': ('detachment', 'indoor_public', 'light', 'culture,discovery,indoors',
               'در بازدید کوتاه توجه به اشیای موزه جای کارهای روزمره را می‌گیرد.'),
    'heritage': ('detachment', 'outdoor', 'light', 'culture,discovery,walking',
                 'دیدن معماری در یک گردش کوتاه، توجه را از فضای روزمره دور می‌کند.'),
    'restaurant': ('relaxation', 'indoor_public', 'seated', 'food,sensory,indoors',
                   'یک وعده در محل، زمانی برای مکث و استراحت بین کارهای روزمره می‌دهد.'),
    'park': ('relaxation', 'outdoor', 'light', 'walking,outdoors,rest',
             'ریتم آرام پیاده‌روی و محدود بودن مسیر فشار یک برنامهٔ طولانی را کم می‌کند.'),
    'walk': ('relaxation', 'outdoor', 'light', 'walking,outdoors,nature',
             'قدم‌زدن در مسیر کوتاه کنار دریا فرصت یک استراحت بیرون از خانه است.'),
    'recreation': ('detachment', 'outdoor', 'light', 'play,discovery,outdoors',
                   'تمرکز روی یک تجربه در مجموعهٔ تفریحی فاصله‌ای از روال عادی می‌سازد.'),
    'cinema': ('detachment', 'indoor_public', 'seated', 'culture,storytelling,indoors',
               'تماشای یک سانس مشخص، توجه را برای مدتی از کارهای روزمره جدا می‌کند.'),
}


@lru_cache(maxsize=1)
def northern_outings_catalog():
    keys, entries = set(), []
    places = {(city_key(place['city']), city_key(place['name']))
              for release in unified_catalog()['releases'].values()
              for entry in release['entries'] if (place := entry['content'].get('place'))}
    sources = {key: dict(name=name, url=url, researched_on=RESEARCHED_ON,
                         availability_verified=False, price_verified=False)
               for key, (name, url) in SOURCES.items()}
    for row in (ROOT / FILE).read_text(encoding='utf-8').splitlines():
        if not row or row.startswith('#'):
            continue
        slug, city, category, name, title, source_id, active, setup, conditions, visit, finish = row.split('|')
        key = 'real:northern-outing-' + slug
        place_key = city_key(city), city_key(name)
        if key in keys or place_key in places:
            raise ValueError('Duplicate northern outing')
        keys.add(key)
        places.add(place_key)
        source = sources[source_id]
        dimension, venue, mobility, tags, intent = PROFILES[category]
        outside = venue == 'outdoor'
        first = 'شرایط مکان و زمان واقعی رفت‌وبرگشت را پیش از حرکت بررسی کن.'
        plan = Content.model_validate(dict(
            title=title, teaser=visit, first_step=first, steps=[first, visit, finish],
            lighter_version='اگر وقت کم است یا مکان در دسترس نیست، فعلاً حرکت نکن و برنامه را عوض کن.',
            primary_dimension=dimension, secondary_dimensions=[], tags=tags.split(','),
            active_minutes=int(active), setup_minutes=int(setup), travel_minutes=60,
            energy_required='low', mobility_required=mobility,
            supported_social_modes=['solo', 'together'], min_people=1, max_people=4, venue=venue,
            required_items=[], materials_note='از قبل ببین مکان به بلیت یا رزرو نیاز دارد یا نه.',
            accessibility_note='اگر مسیر یا امکانات خاصی لازم داری، قبل از حرکت از محل بپرس.',
            conditions_note=conditions, requires_async_contact=False, step_free=None, quiet_compatible=None,
            weather_requirement='fair' if outside else 'any', daylight_requirement='day' if outside else 'any',
            cost=dict(kind='unknown', min_toman=None, max_toman=None, basis='per_person',
                      verified_at=None, valid_until=None, note='قیمت و هزینهٔ مسیر را قبل از حرکت بررسی کن.'),
            safety_notes=['در مسیر و محوطهٔ مجاز بمان.'] if outside else [],
            place=dict(name=name, city=city, source_url=source['url'], source_name=source['name'],
                       researched_on=RESEARCHED_ON, evidence_scope=EVIDENCE),
            requires_venue_check=True, dramma=dict(version='dramma_v1',
              mechanisms=[dict(dimension=dimension, intent=intent, step_indexes=[2, 3])]))).model_dump()
        entries.append(dict(key=key, category=category, content=plan, source_ids=[source_id],
                            availability_verified=False, price_verified=False))
    return dict(version=VERSION, researched_on=RESEARCHED_ON, sources=sources, entries=entries,
                publication_basis='owner_requested_practical_venue_coverage', evidence_scope=EVIDENCE)


def import_northern_outings(store, clock):
    return import_additive(store, clock, northern_outings_catalog(), version=VERSION, source_file=FILE,
        raw_intent='گردش و تفریح در مکان مشخص؛ قیمت و باز بودن روز باید بررسی شود',
        reason='Owner request for measurable diversity of real outings')
