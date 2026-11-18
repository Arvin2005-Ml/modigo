"""Additive sourced venue release; does not alter existing content history."""
from app.modules.catalog.unified import release
import json
from functools import lru_cache
from app.modules.catalog.bootstrap import ROOT
from app.modules.catalog.cinema_expansion import import_additive
from app.modules.catalog.schemas import Content

VERSION = 'visit_expansion_v1'


@lru_cache(maxsize=1)
def visit_catalog():
    catalog = release('visit_expansion_v1')
    entries = catalog['entries']
    if catalog['version'] != VERSION or len(entries) != 43:
        raise ValueError('Invalid venue expansion version or count')
    if len({entry['key'] for entry in entries}) != len(entries):
        raise ValueError('Duplicate venue identity')
    for entry in entries:
        content = Content.model_validate(entry['content']).model_dump()
        place = content['place']
        if (not entry['key'].startswith('real:place-') or entry['category'] not in
                ('museum', 'garden', 'walk', 'park', 'view', 'heritage', 'restaurant', 'cable')
                or entry['availability_verified'] or entry['price_verified'] or len(entry['source_ids']) != 1
                or not place or not content['requires_venue_check'] or content['cost']['kind'] != 'unknown'):
            raise ValueError('Invalid venue provenance')
        source = catalog['sources'][entry['source_ids'][0]]
        if source['url'] != place['source_url'] or source['availability_verified'] or source['price_verified']:
            raise ValueError('Venue source mismatch')
        entry['content'] = content
    return catalog


def import_visits(store, clock):
    return import_additive(store, clock, visit_catalog(), version=VERSION,
        source_file='content/activities.json',
        raw_intent='معرفی مکان؛ بازبودن، قیمت، و شرایط روز تأیید نشده',
        reason='Owner request; tourism source, current availability unverified')


def main():
    import argparse
    from app.core.config import Settings
    from app.core.storage import create_store, StorageUnavailable
    from app.core.values import utcnow
    parser = argparse.ArgumentParser(description='Validate or import the additive venue release')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({'mode': 'files_only_no_database_write', 'entries': len(visit_catalog()['entries'])}))
        return 0
    store = None
    try:
        settings = Settings.load()
        store = create_store({'DATA_BACKEND': settings.data_backend, 'MONGODB_URI': settings.mongodb_uri})
        print(json.dumps({'mode': 'real_mongodb', **import_visits(store, utcnow)}, ensure_ascii=False))
        return 0
    except StorageUnavailable as exc:
        print(f'{exc}. MongoDB import not confirmed; no memory fallback was used.', file=__import__('sys').stderr)
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
