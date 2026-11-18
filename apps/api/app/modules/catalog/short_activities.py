"""Additive, authored short activities for constrained everyday contexts."""
from app.modules.catalog.unified import release
import json
from functools import lru_cache
from app.modules.catalog.bootstrap import ROOT
from app.modules.catalog.cinema_expansion import import_additive
from app.modules.catalog.schemas import Content

VERSION = 'short_activities_v1'

@lru_cache(maxsize=1)
def short_catalog():
    catalog = release('short_activities_v1')
    entries = catalog['entries']
    if catalog['version'] != VERSION or len(entries) != 16 or len({e['key'] for e in entries}) != len(entries):
        raise ValueError('Invalid short activities release')
    for entry in entries:
        content = Content.model_validate(entry['content']).model_dump()
        if (not entry['key'].startswith('real:short-') or entry['source_ids'] or content['place']
                or content['requires_venue_check'] or content['required_items'] or content['cost']['kind'] != 'free'
                or content['active_minutes'] + content['setup_minutes'] + content['travel_minutes'] != 5):
            raise ValueError('Invalid short activity')
        entry['content'] = content
    return catalog


def import_short_activities(store, clock):
    return import_additive(store, clock, short_catalog(), version=VERSION,
        source_file='content/activities.json', raw_intent='تجربه کوتاه تألیفی بدون نیاز به وسیله یا خرید',
        reason='Owner request for coverage of short low-energy situations')


def main():
    import argparse
    from app.core.config import Settings
    from app.core.storage import create_store, StorageUnavailable
    from app.core.values import utcnow
    parser = argparse.ArgumentParser(description='Validate or import short activities')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({'mode':'files_only_no_database_write', 'entries':len(short_catalog()['entries'])}))
        return 0
    store = None
    try:
        settings = Settings.load()
        store = create_store({'DATA_BACKEND': settings.data_backend, 'MONGODB_URI': settings.mongodb_uri})
        print(json.dumps({'mode':'real_mongodb', **import_short_activities(store, utcnow)}, ensure_ascii=False))
        return 0
    except StorageUnavailable as exc:
        print(f'{exc}. MongoDB import not confirmed; no memory fallback was used.', file=__import__('sys').stderr)
        return 1
    finally:
        if store is not None:
            store.close()

if __name__ == '__main__':
    raise SystemExit(main())
