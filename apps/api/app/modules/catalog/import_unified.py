"""Import the unified owner release using the existing audited batch importers."""
import json
from app.modules.catalog.curated import import_catalog, counts
from app.modules.catalog.cinema_expansion import import_cinemas
from app.modules.catalog.food_expansion import import_food
from app.modules.catalog.visit_expansion import import_visits
from app.modules.catalog.short_activities import import_short_activities
from app.modules.catalog.home_short import import_home_short
from app.modules.catalog.everyday_activities import import_everyday
from app.modules.catalog.short_now import import_short_now, short_now_catalog
from app.modules.catalog.long_now import import_long_now, long_now_catalog
from app.modules.catalog.practical_now import import_practical_now, practical_now_catalog
from app.modules.catalog.northern_outings import import_northern_outings, northern_outings_catalog
from app.modules.catalog.full_day_outings import import_full_day_outings, full_day_catalog
from app.modules.catalog.unified import unified_catalog
from app.modules.catalog.deduplication import duplicate_records

IMPORTERS = (import_catalog, import_cinemas, import_food, import_visits,
             import_short_activities, import_home_short, import_everyday, import_short_now, import_long_now,
             import_practical_now, import_northern_outings, import_full_day_outings)


def import_unified(store, clock):
    unified_catalog()  # validate all keys before any database writes
    short_now_catalog()
    long_now_catalog()
    practical_now_catalog()
    northern_outings_catalog()
    full_day_catalog()
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
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--short-now-only', action='store_true', help='Validate or import only the short same-place release')
    scope.add_argument('--long-now-only', action='store_true', help='Validate or import only the longer same-place release')
    scope.add_argument('--practical-now-only', action='store_true', help='Validate or import only the practical recreation release')
    scope.add_argument('--northern-outings-only', action='store_true', help='Validate or import only the northern outing release')
    args = parser.parse_args()
    selected = next(((loader, importer) for enabled, loader, importer in (
        (args.short_now_only, short_now_catalog, import_short_now),
        (args.long_now_only, long_now_catalog, import_long_now),
        (args.practical_now_only, practical_now_catalog, import_practical_now),
        (args.northern_outings_only, northern_outings_catalog, import_northern_outings),
    ) if enabled), None)
    if not args.apply:
        releases = ([selected[0]()] if selected else [*unified_catalog()['releases'].values(),
                     short_now_catalog(), long_now_catalog(), practical_now_catalog(), northern_outings_catalog(),
                     full_day_catalog()])
        from app.modules.catalog.schemas import Content
        for release in releases:
            for entry in release['entries']:
                Content.model_validate(entry['content'])
        print(json.dumps({'mode':'files_only_no_database_write','releases':len(releases),
                          'entries':sum(len(r['entries']) for r in releases)}))
        return 0
    store = None
    try:
        settings = Settings.load()
        store = create_store({'DATA_BACKEND':settings.data_backend,'MONGODB_URI':settings.mongodb_uri})
        importer = selected[1] if selected else import_unified
        result = importer(store, utcnow)
        print(json.dumps({'mode':'real_mongodb', **result},ensure_ascii=False,default=str))
        return 0
    except StorageUnavailable as exc:
        print(f'{exc}. MongoDB import not confirmed; no memory fallback was used.',file=__import__('sys').stderr)
        return 1
    finally:
        if store is not None: store.close()

if __name__ == '__main__': raise SystemExit(main())
