"""Import the unified owner release using the existing audited batch importers."""
import json
from app.modules.catalog.curated import import_catalog, counts
from app.modules.catalog.cinema_expansion import import_cinemas
from app.modules.catalog.food_expansion import import_food
from app.modules.catalog.visit_expansion import import_visits
from app.modules.catalog.short_activities import import_short_activities
from app.modules.catalog.home_short import import_home_short
from app.modules.catalog.everyday_activities import import_everyday
from app.modules.catalog.unified import unified_catalog
from app.modules.catalog.deduplication import duplicate_records

IMPORTERS = (import_catalog, import_cinemas, import_food, import_visits,
             import_short_activities, import_home_short, import_everyday)


def import_unified(store, clock):
    unified_catalog()  # validate all keys before any database writes
    results = [importer(store, clock) for importer in IMPORTERS]
    return {'releases': results, 'inserted': sum(r['inserted'] for r in results),
            'duplicates_skipped': [key for r in results for key in r.get('duplicate_keys', [])],
            'preexisting_duplicate_activity_ids': duplicate_records(store),
            'counts': counts(store)}


def main():
    import argparse
    from app.core.config import Settings
    from app.core.storage import create_store, StorageUnavailable
    from app.core.values import utcnow
    parser = argparse.ArgumentParser(description='Validate or import unified activity catalog')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        data = unified_catalog()
        print(json.dumps({'mode':'files_only_no_database_write','releases':len(data['releases']),
                          'entries':sum(len(r['entries']) for r in data['releases'].values())}))
        return 0
    store = None
    try:
        settings = Settings.load()
        store = create_store({'DATA_BACKEND':settings.data_backend,'MONGODB_URI':settings.mongodb_uri})
        print(json.dumps({'mode':'real_mongodb', **import_unified(store, utcnow)},ensure_ascii=False,default=str))
        return 0
    except StorageUnavailable as exc:
        print(f'{exc}. MongoDB import not confirmed; no memory fallback was used.',file=__import__('sys').stderr)
        return 1
    finally:
        if store is not None: store.close()

if __name__ == '__main__': raise SystemExit(main())
