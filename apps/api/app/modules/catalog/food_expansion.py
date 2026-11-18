"""Additive sourced dining release; does not alter existing catalog history."""
from app.modules.catalog.unified import release
import json
from functools import lru_cache
from app.modules.catalog.bootstrap import ROOT
from app.modules.catalog.cinema_expansion import import_additive
from app.modules.catalog.schemas import Content

VERSION = 'food_expansion_v1'


@lru_cache(maxsize=1)
def food_catalog():
    catalog = release('food_expansion_v1')
    entries = catalog['entries']
    if catalog['version'] != VERSION or len(entries) != 70:
        raise ValueError('Invalid dining expansion version or count')
    if len({entry['key'] for entry in entries}) != len(entries):
        raise ValueError('Duplicate dining identity')
    city_for_source = {'rasht': 'رشت', 'shiraz': 'شیراز', 'isfahan': 'اصفهان'}
    for entry in entries:
        content = Content.model_validate(entry['content']).model_dump()
        place = content['place']
        if (not entry['key'].startswith('real:place-') or entry['category'] not in ('restaurant', 'fastfood')
                or entry['availability_verified'] or entry['price_verified'] or len(entry['source_ids']) != 1
                or not place or not content['requires_venue_check'] or content['cost']['kind'] != 'unknown'):
            raise ValueError('Invalid dining provenance')
        source_id = entry['source_ids'][0]
        source = catalog['sources'][source_id]
        if (source['url'] != place['source_url'] or source['availability_verified'] or source['price_verified']
                or city_for_source.get(source_id) != place['city']):
            raise ValueError('Dining source mismatch')
        entry['content'] = content
    return catalog


def import_food(store, clock):
    return import_additive(store, clock, food_catalog(), version=VERSION,
        source_file='content/activities.json',
        raw_intent='فهرست کسب‌وکارها؛ امکان صرف حضوری، بازبودن و قیمت روز تأیید نشده',
        reason='Owner request; sourced dining directory; current availability unverified')


def main():
    import argparse
    from app.core.config import Settings
    from app.core.storage import create_store, StorageUnavailable
    from app.core.values import utcnow
    parser = argparse.ArgumentParser(description='Validate or import the additive dining release')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({'mode': 'files_only_no_database_write', 'entries': len(food_catalog()['entries'])}))
        return 0
    store = None
    try:
        settings = Settings.load()
        store = create_store({'DATA_BACKEND': settings.data_backend, 'MONGODB_URI': settings.mongodb_uri})
        print(json.dumps({'mode': 'real_mongodb', **import_food(store, utcnow)}, ensure_ascii=False))
        return 0
    except StorageUnavailable as exc:
        print(f'{exc}. MongoDB import not confirmed; no memory fallback was used.', file=__import__('sys').stderr)
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
