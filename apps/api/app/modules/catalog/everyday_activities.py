"""Owner-requested authored everyday activities; additive and idempotent."""
from app.modules.catalog.unified import release
import json
from functools import lru_cache
from app.modules.catalog.bootstrap import ROOT
from app.modules.catalog.cinema_expansion import import_additive
from app.modules.catalog.schemas import Content

VERSION = 'everyday_activities_v1'

@lru_cache(maxsize=1)
def everyday_catalog():
    catalog = release('everyday_activities_v1')
    entries = catalog['entries']
    if catalog['version'] != VERSION or len(entries) != 60 or len({e['key'] for e in entries}) != len(entries):
        raise ValueError('Invalid everyday activity release')
    for entry in entries:
        c = Content.model_validate(entry['content']).model_dump()
        if (not entry['key'].startswith('real:everyday-') or entry['source_ids'] or c['place']
                or c['venue'] != 'home' or c['requires_venue_check'] or c['cost']['kind'] != 'free'
                or not 5 <= c['active_minutes'] + c['setup_minutes'] + c['travel_minutes'] <= 30):
            raise ValueError('Invalid everyday activity')
        if c['primary_dimension'] == 'affiliation' and c['supported_social_modes'] != ['together']:
            raise ValueError('Shared experience must require company')
        entry['content'] = c
    return catalog


def import_everyday(store, clock):
    return import_additive(store, clock, everyday_catalog(), version=VERSION,
        source_file='content/activities.json', raw_intent='تفریح تألیفی خانگی فردی یا گروهی با وسایل موجود',
        reason='Owner request for varied everyday activities with explicit DRAMMA mechanisms')


def main():
    import argparse
    from app.core.config import Settings
    from app.core.storage import create_store, StorageUnavailable
    from app.core.values import utcnow
    parser=argparse.ArgumentParser(description='Validate or import everyday activities')
    parser.add_argument('--apply', action='store_true')
    args=parser.parse_args()
    if not args.apply:
        print(json.dumps({'mode':'files_only_no_database_write','entries':len(everyday_catalog()['entries'])}))
        return 0
    store=None
    try:
        settings=Settings.load()
        store=create_store({'DATA_BACKEND':settings.data_backend,'MONGODB_URI':settings.mongodb_uri})
        print(json.dumps({'mode':'real_mongodb',**import_everyday(store,utcnow)},ensure_ascii=False))
        return 0
    except StorageUnavailable as exc:
        print(f'{exc}. MongoDB import not confirmed; no memory fallback was used.',file=__import__('sys').stderr)
        return 1
    finally:
        if store is not None: store.close()

if __name__ == '__main__':
    raise SystemExit(main())
