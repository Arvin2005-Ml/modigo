"""Additive cinema release; never changes existing identities or revisions."""
from app.modules.catalog.unified import release
import json
from functools import lru_cache
from app.core.values import uid
from app.modules.catalog.bootstrap import ROOT, content_checksum
from app.modules.catalog.schemas import Content
from app.modules.catalog.deduplication import existing_identities, identity

VERSION = 'cinema_expansion_v1'


@lru_cache(maxsize=1)
def cinema_catalog():
    catalog = release('cinema_expansion_v1')
    entries = catalog['entries']
    if catalog['version'] != VERSION or len(entries) != 77:
        raise ValueError('Invalid cinema expansion version or count')
    if len({entry['key'] for entry in entries}) != len(entries):
        raise ValueError('Duplicate cinema identity')
    for entry in entries:
        content = Content.model_validate(entry['content']).model_dump()
        place = content['place']
        if (not entry['key'].startswith('real:place-') or entry['category'] != 'cinema'
                or entry['availability_verified'] or entry['price_verified'] or len(entry['source_ids']) != 1
                or not place or not content['requires_venue_check'] or content['cost']['kind'] != 'unknown'):
            raise ValueError('Invalid cinema provenance')
        source = catalog['sources'][entry['source_ids'][0]]
        if source['url'] != place['source_url'] or source['availability_verified'] or source['price_verified']:
            raise ValueError('Cinema source mismatch')
        entry['content'] = content
    return catalog


def import_additive(store, clock, catalog, *, version, source_file, raw_intent, reason, scoped_keys=False):
    """Insert one validated release without modifying any existing identity."""
    keys = {entry['key'] for entry in catalog['entries']}
    existing = {a['seed_key'] for a in (store.activities_by_seed_keys(keys) if scoped_keys else store.list('activities'))}
    pending = [entry for entry in catalog['entries'] if entry['key'] not in existing]
    inserted = 0
    duplicate_keys = []
    for offset in range(0, len(pending), 25):
        batch = pending[offset:offset + 25]
        with store.atomic():
            # Scoped releases use a reserved, validated key namespace; old
            # importers still deduplicate by content across the whole catalog.
            rows = store.activities_by_seed_keys({e['key'] for e in batch}) if scoped_keys else store.list('activities')
            present = {a['seed_key'] for a in rows}
            identities = {} if scoped_keys else existing_identities(store)
            for entry in batch:
                if entry['key'] in present:
                    continue
                content = entry['content']
                fingerprint = identity(content)
                if fingerprint in identities:
                    duplicate_keys.append(entry['key'])
                    continue
                activity_id, revision_id = uid(), uid()
                source_metadata = {k: v for k, v in entry.items() if k != 'content'}
                source_metadata.update(catalog_version=version, researched_on=catalog['researched_on'],
                    sources={key: catalog['sources'][key] for key in entry['source_ids']})
                store.insert('activities', dict(id=activity_id, seed_key=entry['key'],
                    source_file=source_file, source_metadata=source_metadata,
                    raw_title=content['title'], raw_intent=raw_intent,
                    primary_dimension=content['primary_dimension'], active=True, published_revision_id=revision_id,
                    next_revision_number=2, start_guard_version=0, created_at=clock()))
                store.insert('activity_revisions', dict(id=revision_id, activity_id=activity_id,
                    revision_number=1, draft_version=1, state='published', content=content, origin='curated',
                    reviewed_by=None, published_at=clock(), created_at=clock(), validation_report={
                        'schema_valid': True, 'dramma_version': 'dramma_v1', 'human_approval': False,
                        'publication_basis': catalog['publication_basis'], 'catalog_version': version,
                        'import_checksum': content_checksum(content), 'source_ids': entry['source_ids'],
                        'evidence_scope': catalog['evidence_scope'], 'availability_verified': False, 'price_verified': False}))
                present.add(entry['key'])
                identities[fingerprint] = activity_id
                inserted += 1
            store.insert('admin_audit', dict(id=uid(), actor_id='system', action='curated_catalog_batch_imported',
                target_id=version, reason=reason, created_at=clock()))
    return {'catalog_version': version, 'inserted': inserted, 'release_entries': len(catalog['entries']), 'duplicate_keys': duplicate_keys}


def import_cinemas(store, clock):
    return import_additive(store, clock, cinema_catalog(), version=VERSION,
        source_file='content/activities.json', raw_intent='فهرست تاریخی سینماها؛ بازبودن و قیمت روز تأیید نشده',
        reason='Owner request; historical cinema listing; current availability unverified')


def main():
    import argparse
    from app.core.config import Settings
    from app.core.storage import create_store, StorageUnavailable
    from app.core.values import utcnow
    parser = argparse.ArgumentParser(description='Validate or import the additive cinema release')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({'mode': 'files_only_no_database_write', 'entries': len(cinema_catalog()['entries'])}))
        return 0
    store = None
    try:
        settings = Settings.load()
        store = create_store({'DATA_BACKEND': settings.data_backend, 'MONGODB_URI': settings.mongodb_uri})
        result = import_cinemas(store, utcnow)
        print(json.dumps({'mode': 'real_mongodb', **result}, ensure_ascii=False))
        return 0
    except StorageUnavailable as exc:
        print(f'{exc}. MongoDB import not confirmed; no memory fallback was used.', file=__import__('sys').stderr)
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
