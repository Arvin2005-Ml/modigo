"""Authored home activities, imported additively with immutable history."""
from app.modules.catalog.unified import release
import json
from functools import lru_cache
from app.modules.catalog.bootstrap import ROOT
from app.modules.catalog.cinema_expansion import import_additive
from app.modules.catalog.schemas import Content

VERSION = 'home_short_v1'

@lru_cache(maxsize=1)
def home_catalog():
    data = release('home_short_v1')
    entries = data['entries']
    if data['version'] != VERSION or len(entries) != 20 or len({e['key'] for e in entries}) != len(entries):
        raise ValueError('Invalid home short release')
    for entry in entries:
        c = Content.model_validate(entry['content']).model_dump()
        if (not entry['key'].startswith('real:home-short-') or entry['source_ids'] or c['place']
                or c['venue'] != 'home' or c['requires_venue_check'] or c['cost']['kind'] != 'free'
                or not 10 <= c['active_minutes'] + c['setup_minutes'] + c['travel_minutes'] <= 20):
            raise ValueError('Invalid home activity')
        entry['content'] = c
    return data


def import_home_short(store, clock):
    return import_additive(store, clock, home_catalog(), version=VERSION,
        source_file='content/activities.json', raw_intent='تفریح خانگی کوتاه تألیفی با وسایل موجود',
        reason='Owner request for more short and low-energy home activities')


def main():
    import argparse
    from app.core.config import Settings
    from app.core.storage import create_store, StorageUnavailable
    from app.core.values import utcnow
    parser = argparse.ArgumentParser(description='Validate or import short home activities')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({'mode': 'files_only_no_database_write', 'entries': len(home_catalog()['entries'])}))
        return 0
    store = None
    try:
        settings = Settings.load()
        store = create_store({'DATA_BACKEND': settings.data_backend, 'MONGODB_URI': settings.mongodb_uri})
        print(json.dumps({'mode': 'real_mongodb', **import_home_short(store, utcnow)}, ensure_ascii=False))
        return 0
    except StorageUnavailable as exc:
        print(f'{exc}. MongoDB import not confirmed; no memory fallback was used.', file=__import__('sys').stderr)
        return 1
    finally:
        if store is not None:
            store.close()

if __name__ == '__main__':
    raise SystemExit(main())
