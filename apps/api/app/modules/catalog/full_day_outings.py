"""Source-backed one- and two-day outings. Explicit, additive release."""
import argparse
from collections import Counter
from functools import lru_cache
import json
import re
import sys
from urllib.parse import quote

from app.core.outing import OUTING_ORIGINS, MINUTES_PER_DAY
from app.core.schemas import Context
from app.modules.catalog.bootstrap import ROOT
from app.modules.catalog.cinema_expansion import import_additive
from app.modules.catalog.deduplication import identity
from app.modules.catalog.schemas import Content
from app.modules.catalog.service import Catalog
from app.modules.recommendations.eligibility import eligible

VERSION = 'full_day_outings_v1'
FILE = 'content/full-day-outings.txt'
RESEARCHED_ON = '2026-11-18'
EVIDENCE = 'place_and_activity_type_only'
EXPECTED = {(city, days): 10 for city in OUTING_ORIGINS.values() for days in (1, 2)}

SOURCES = {
    'golestan': ('یونسکو؛ کاخ گلستان', 'https://whc.unesco.org/en/list/1422/'),
    'tabiat': ('ویزیت ایران؛ پل طبیعت', 'https://visitiran.ir/attraction/tabiat-bridge'),
    'saadabad': ('ویزیت ایران؛ سعدآباد', 'https://visitiran.ir/en/attraction/saadabad-palace-complex'),
    'niavaran': ('ویزیت ایران؛ نیاوران', 'https://visitiran.ir/attraction/niavaran-palace'),
    'chitgar': ('ویزیت ایران؛ چیتگر', 'https://visitiran.ir/attraction/chitgar-lake-and-park'),
    'rey': ('ویزیت ایران؛ شهرری', 'https://visitiran.ir/destination/shahr-e-rey'),
    'varamin': ('ویزیت ایران؛ ورامین', 'https://visitiran.ir/fa/destination/' + quote('ورامین')),
    'lavasan': ('ویزیت ایران؛ لواسان', 'https://visitiran.ir/index.php/fa/destination/' + quote('لواسان')),
    'alborz': ('ویزیت ایران؛ البرز', 'https://visitiran.ir/province/Alborz-Province'),
    'qazvin': ('ویزیت ایران؛ قزوین', 'https://visitiran.ir/en/province/qazvin-province'),
    'khorasan': ('ویزیت ایران؛ خراسان رضوی', 'https://visitiran.ir/en/province/Razavi-Khorasan-province'),
    'torqabeh': ('ویزیت ایران؛ طرقبه', 'https://visitiran.ir/index.php/en/attraction/torqabeh'),
    'chenaran': ('ویزیت ایران؛ چناران', 'https://visitiran.ir/destination/chenaran'),
    'neyshabur': ('ویزیت ایران؛ نیشابور', 'https://visitiran.ir/destination/neyshabur'),
    'isfahan': ('ویزیت ایران؛ اصفهان', 'https://visitiran.ir/province/Isfahan-Province'),
    'naqsh': ('یونسکو؛ میدان نقش جهان', 'https://whc.unesco.org/en/list/115/'),
    'jameh': ('یونسکو؛ مسجد جامع اصفهان', 'https://whc.unesco.org/en/list/1397/'),
    'gardens': ('یونسکو؛ باغ ایرانی', 'https://whc.unesco.org/en/list/1372/'),
    'nazhvan': ('ویزیت ایران؛ ناژوان', 'https://visitiran.ir/fa/attraction/' + quote('ناژوان')),
    'natanz': ('ویزیت ایران؛ نطنز و ابیانه', 'https://visitiran.ir/destination/natanz'),
    'kashan': ('ویزیت ایران؛ کاشان', 'https://visitiran.ir/en/destination/kashan'),
    'niasar': ('ویزیت ایران؛ چهارتاقی نیاسر', 'https://visitiran.ir/attraction/chahartaq-niasar-fire-temple'),
    'shiraz': ('ویزیت ایران؛ جاذبه‌های شیراز', 'https://visitiran.ir/index.php/en/destination/shiraz'),
    'fars': ('ویزیت ایران؛ فارس', 'https://visitiran.ir/en/province/fars-province'),
    'persepolis': ('یونسکو؛ تخت جمشید', 'https://whc.unesco.org/en/list/114/'),
    'pasargadae': ('یونسکو؛ پاسارگاد', 'https://whc.unesco.org/en/list/1106/'),
    'sassanid': ('یونسکو؛ آثار ساسانی فارس', 'https://whc.unesco.org/en/list/1568/'),
    'maharloo': ('ویزیت ایران؛ مهارلو', 'https://visitiran.ir/attraction/maharloo-lake'),
    'azarbaijan': ('ویزیت ایران؛ آذربایجان شرقی', 'https://visitiran.ir/en/province/East-Azerbaijan-Province'),
    'tabriz': ('یونسکو؛ بازار تاریخی تبریز', 'https://whc.unesco.org/en/list/1346/'),
    'osku': ('ویزیت ایران؛ اسکو و کندوان', 'https://visitiran.ir/destination/osku'),
    'marand': ('ویزیت ایران؛ مرند', 'https://visitiran.ir/fa/destination/' + quote('مرند')),
    'maragheh': ('ویزیت ایران؛ مراغه', 'https://visitiran.ir/destination/maragheh'),
    'ahar': ('رایزنی فرهنگی ایران؛ اهر', 'https://en.irancultura.it/tourism/attractions/attractions-tabriz/ahar/'),
    'kordasht': ('ویزیت ایران؛ مجموعهٔ کردشت', 'https://visitiran.ir/attraction/complex-bath-and-castle-kurdasht'),
    'stepanos': ('ویزیت ایران؛ سنت استپانوس', 'https://visitiran.ir/en/attraction/saint-stepanos-monastery'),
}

# Each row authors the stops and activities; these profiles only give them a
# consistent planning buffer and tags. The times are not routing measurements.
PROFILES = {
    'rest': ('relaxation', ['outdoors', 'walking', 'nature', 'rest'], 510, 105,
             'مکث و حرکت با سرعت دلخواه در فضای عمومی فرصت استراحت می‌دهد.'),
    'heritage': ('detachment', ['outdoors', 'culture', 'discovery'], 540, 90,
                 'دیدن جزئیات یک مکان تاریخی توجه را از روال روزمره دور می‌کند.'),
    'design': ('mastery', ['outdoors', 'culture', 'design', 'observation'], 540, 85,
               'مقایسهٔ جزئیات معماری تمرین کوچکی برای دیدن دقیق‌تر است.'),
    'photo': ('autonomy', ['outdoors', 'observation', 'photography', 'walking'], 520, 95,
              'انتخاب سوژه و مسیر کوتاه، برنامه را به سلیقهٔ شخصی نزدیک می‌کند.'),
    'memory': ('meaning', ['outdoors', 'culture', 'memory', 'reflection'], 530, 90,
                'ثبت یک مشاهده از مکان، یادگاری کوچک و شخصی از گردش می‌سازد.'),
}


def _day(morning, afternoon, total, setup, travel):
    return dict(morning=morning, afternoon=afternoon, active_minutes=total - setup - travel,
                setup_minutes=setup, travel_minutes=travel)


@lru_cache(maxsize=1)
def full_day_catalog():
    entries, keys, titles, routes = [], set(), set(), set()
    distribution = Counter()
    sources = {key: dict(name=name, url=url, researched_on=RESEARCHED_ON,
                         availability_verified=False, price_verified=False)
               for key, (name, url) in SOURCES.items()}
    for line, row in enumerate((ROOT / FILE).read_text(encoding='utf-8').splitlines(), 1):
        if not row or row.startswith('#'):
            continue
        try:
            origin, duration, slug, city, name, evidence, travel, theme, title, am, pm, night, am2, pm2 = (
                value.strip() for value in row.split('|'))
            days, one_way = int(duration), int(travel)
            city_from, source = OUTING_ORIGINS[origin], sources[evidence]
            dimension, tags, total, setup, intent = PROFILES[theme]
            if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', slug):
                raise ValueError('invalid stable slug')
            if days == 1 and (night or am2 or pm2):
                raise ValueError('one-day plan has a second day')
            key = f'real:full-day-{origin}-{days}-{slug}'
            first = (f'از {city_from} زمان رفت‌وبرگشت، وضعیت مسیر و باز بودن توقف‌ها را بررسی کن.'
                     if days == 1 else
                     f'از {city_from} مسیر رفت و برگشت را بررسی کن و قبل از حرکت اقامت مجاز در {night} را هماهنگ کن.')
            itinerary = ([_day(am, pm, total, setup, 2 * one_way + 20)] if days == 1 else
                         [_day(am, pm, total, setup, one_way + 40),
                          _day(am2, pm2, total - 30, setup, one_way + 50)])
            steps = [am, pm] if days == 1 else [am, pm, am2, pm2]
            content = Content.model_validate(dict(
                title=title, teaser=f'گردش {"یک‌روزه" if days == 1 else "دوروزه"} از {city_from} با محور «{name}».',
                first_step=first, steps=steps,
                lighter_version='اگر انرژی یا وقت کم شد، توقف دوم هر روز را حذف کن و برای برگشت وقت کافی بگذار.',
                materials_note='آب، کفش مناسب و مسیر برگشت را آماده کن؛ وسیله، بلیت یا رزرو را از قبل بررسی کن.',
                accessibility_note='پله، شیب یا مسیر ناهموار ممکن است وجود داشته باشد. برای دسترسی و سرویس بهداشتی از محل بپرس.',
                conditions_note=('برای بازدیدها روشنایی روز، هوای مناسب و باز بودن توقف‌ها را بررسی کن.'
                                 + (' رزرو و شرایط اقامت یک شب را هم جداگانه بررسی کن.' if days == 2 else '')),
                primary_dimension=dimension, secondary_dimensions=[], tags=tags,
                **{field: sum(day[field] for day in itinerary)
                   for field in ('active_minutes', 'setup_minutes', 'travel_minutes')},
                energy_required='low' if theme == 'rest' else 'medium', mobility_required='light',
                supported_social_modes=['solo', 'together'], min_people=1, max_people=12,
                venue='outdoor', required_items=[], requires_async_contact=False,
                step_free=None, quiet_compatible=None, weather_requirement='fair', daylight_requirement='day',
                cost=dict(kind='unknown', min_toman=None, max_toman=None, basis='per_group', verified_at=None,
                          valid_until=None, note='هزینهٔ کل مسیر، ورودی، خوردوخوراک و در برنامهٔ دوروزه اقامت را پیش از حرکت بررسی کن.'),
                safety_notes=['در جاهای عمومی و مجاز بمان؛ اگر راه یا هوا نامناسب بود حرکت نکن.'],
                place=dict(name=name, city=city, source_url=source['url'], source_name=source['name'],
                           researched_on=RESEARCHED_ON, evidence_scope=EVIDENCE),
                outing=dict(days=days, origin_city=city_from, country_code='IR', one_way_travel_minutes=one_way,
                            overnight_city=night or None, itinerary=itinerary),
                requires_venue_check=True, dramma=dict(version='dramma_v1', mechanisms=[
                    dict(dimension=dimension, intent=intent, step_indexes=[1, 2])])),
            ).model_dump()
            fingerprint = identity(content)
            if key in keys or fingerprint in titles or tuple(steps) in routes:
                raise ValueError('duplicate identity or itinerary')
            keys.add(key)
            titles.add(fingerprint)
            routes.add(tuple(steps))
            distribution[city_from, days] += 1
            entries.append(dict(key=key, category=theme, content=content, source_ids=[evidence],
                                availability_verified=False, price_verified=False))
        except (ValueError, KeyError) as exc:
            raise ValueError(f'{FILE}:{line}: {exc}') from exc
    if distribution != EXPECTED:
        raise ValueError('Expected ten different outings per origin and duration')
    return dict(version=VERSION, researched_on=RESEARCHED_ON, sources=sources, entries=entries,
                publication_basis='owner_requested_full_day_outings', evidence_scope=EVIDENCE)


def import_full_day_outings(store, clock):
    return import_additive(store, clock, full_day_catalog(), version=VERSION, source_file=FILE,
        raw_intent='گردش یک‌روزه و دوروزه از شهر مبدأ مشخص؛ قیمت، راه و بازبودن روز نیاز به بررسی دارند',
        reason='Owner request: 100 domestic one- and two-day outings with reviewed origins and sources',
        scoped_keys=True)


@lru_cache(maxsize=10)
def outing_seed_keys(city, days):
    return frozenset(entry['key'] for entry in full_day_catalog()['entries']
                     if (entry['content']['outing']['origin_city'], entry['content']['outing']['days']) == (city, days))


def coverage_report(store, clock):
    expected_keys = {row['key'] for row in full_day_catalog()['entries']}
    ids = {a['id'] for a in store.activities_by_seed_keys(expected_keys)}
    candidates = Catalog(store, clock).candidates(ids)
    groups = {}
    for origin, name in OUTING_ORIGINS.items():
        groups[origin] = {}
        for days in (1, 2):
            context = Context(available_minutes=days * MINUTES_PER_DAY, outing_days=days, energy='unknown',
                social_mode='solo', party_size=1, venue='away_from_home', budget={'mode': 'flexible'},
                city=name, allow_venue_planning=True, weather='fair', daylight='day').model_dump()
            group = Catalog(store, clock).recommendation_candidates(context)
            now = clock()
            groups[origin][days] = sum(eligible(context, row, now) is not None for row in group)
    return dict(expected=len(expected_keys), present=len(ids), published=len(candidates),
                eligible=sum(sum(group.values()) for group in groups.values()), by_origin_and_days=groups)


def main(argv=None):
    from app.core.config import Settings
    from app.core.storage import create_store, StorageUnavailable
    from app.core.values import utcnow

    parser = argparse.ArgumentParser(description='Validate, import or verify the full-day outing release')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--apply', action='store_true')
    action.add_argument('--verify', action='store_true')
    args = parser.parse_args(argv)
    catalog = full_day_catalog()
    if not (args.apply or args.verify):
        print(json.dumps({'mode': 'files_only', 'version': VERSION, 'entries': len(catalog['entries'])}))
        return 0
    store = None
    try:
        settings = Settings.load()
        store = create_store({'DATA_BACKEND': settings.data_backend, 'MONGODB_URI': settings.mongodb_uri})
        imported = import_full_day_outings(store, utcnow) if args.apply else {}
        report = coverage_report(store, utcnow)
        print(json.dumps({'mode': 'real_mongodb', 'version': VERSION, **imported, **report}, ensure_ascii=False))
        return 0 if report['present'] == report['published'] == report['eligible'] == report['expected'] else 2
    except StorageUnavailable as exc:
        print(f'{exc}. MongoDB operation not confirmed; no fallback used.', file=sys.stderr)
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
