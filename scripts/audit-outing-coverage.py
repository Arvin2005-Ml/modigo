"""Measure the named outing pool with the same hard filters as recommendations."""
import argparse
from collections import Counter, defaultdict
from datetime import timezone
import sys

from app.core.schemas import Context, city_key
from app.core.values import utcnow
from app.modules.catalog.northern_outings import northern_outings_catalog
from app.modules.catalog.service import Catalog
from app.modules.catalog.unified import unified_catalog
from app.modules.recommendations.eligibility import eligible

FOOD = {'restaurant', 'fastfood', 'street_food', 'cafe'}
OUTDOORS = {'park', 'garden', 'walk', 'bridge', 'view'}
HERITAGE = {'heritage', 'bazaar', 'literature', 'cave'}
SHOWS = {'theatre', 'concert', 'gallery'}
DEFAULT_CITIES = ('تهران', 'اصفهان', 'شیراز', 'رشت', 'کیش', 'ساری', 'رامسر', 'چالوس', 'نمک‌آبرود', 'بابلسر')


def family(category):
    if category in ('museum', 'cinema'):
        return category
    for name, categories in (('food', FOOD), ('outdoors', OUTDOORS), ('heritage', HERITAGE), ('shows', SHOWS)):
        if category in categories:
            return name
    return 'other'


def from_files(baseline):
    releases = list(unified_catalog()['releases'].values())
    if not baseline:
        releases.append(northern_outings_catalog())
    for release in releases:
        for entry in release['entries']:
            content = entry['content']
            key = entry['key']
            yield dict(id=key, revision_id=key, published_revision_id=key,
                       active=True, state='published', primary_dimension=content['primary_dimension'],
                       content=content, category=entry.get('category'))


def from_mongo():
    from copy import deepcopy
    from bson.codec_options import CodecOptions
    from app.core.config import load_environment, validate_mongodb_uri
    from app.core.mongo import PUBLISHED_CATALOG
    from app.core.mongo_connection import create_mongo_client, mongo_failure

    pipeline = deepcopy(PUBLISHED_CATALOG)
    pipeline[1]['$project']['source_metadata.category'] = 1
    pipeline[-1]['$project']['category'] = '$source_metadata.category'
    try:
        uri = load_environment().get('MONGODB_URI', '').strip()
        validate_mongodb_uri(uri)
        with create_mongo_client(uri) as client:
            db = client.get_default_database(codec_options=CodecOptions(tz_aware=True, tzinfo=timezone.utc))
            return list(db.activities.aggregate(pipeline))
    except Exception as error:
        raise SystemExit(str(mongo_failure(error, 'read'))) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--baseline', action='store_true', help='Use the files before the northern outing release')
    mode.add_argument('--live', action='store_true', help='Read published records from the configured MongoDB')
    parser.add_argument('--city', action='append', help='City to show; may be repeated')
    parser.add_argument('--budget', choices=('flexible', 'free'), default='flexible')
    args = parser.parse_args()
    all_types = Counter()
    by_city = defaultdict(list)
    for row in from_mongo() if args.live else from_files(args.baseline):
        if not row['content'].get('place'):
            continue
        content = Catalog.checked_content(row['content'], row['primary_dimension'])
        if content is None:
            continue
        city = city_key(content.place.city)
        category = family(row.get('category'))
        all_types[category] += 1
        by_city[city].append(({**row, 'content': content.model_dump()}, category))
    print('named:', sum(all_types.values()), 'cities:', len(by_city), 'types:', dict(all_types))
    now = utcnow()
    for minutes, weather, daylight in ((120, 'fair', 'day'), (240, 'fair', 'day'), (240, 'unknown', 'unknown')):
        seed = Context(available_minutes=minutes, energy='low', social_mode='solo', party_size=1,
                       venue='away_from_home', budget={'mode': args.budget}, allow_venue_planning=True,
                       weather=weather, daylight=daylight).model_dump()
        snapshots = {city: Counter(category for row, category in rows
                                    if eligible({**seed, 'city':city}, row, now)) for city, rows in by_city.items()}
        covered = sum(sum(types.values()) >= 7 and len(types) >= 3 for types in snapshots.values())
        any_outing = sum(bool(types) for types in snapshots.values())
        print(f'{minutes}m {weather}: {any_outing} cities with an outing; {covered} with 7+ outings and 3+ types')
        for city in args.city or DEFAULT_CITIES:
            types = snapshots.get(city_key(city), {})
            print(f'  {city}: {sum(types.values())}', dict(types))
    return 0


if __name__ == '__main__':
    sys.exit(main())
