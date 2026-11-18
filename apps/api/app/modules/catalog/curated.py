"""Owner-authorized release importer. Stable identities, immutable content history.

Only the exact shipped, unreviewed legacy demos are archived. Existing curated
records (including withdrawn and editor-modified records) are never overwritten.
Runtime storage always comes from the real MongoDB store factory.
"""
from app.modules.catalog.unified import release
import json
from functools import lru_cache
from collections import Counter
from app.core.values import uid, replace
from app.modules.catalog.bootstrap import ROOT, content_checksum, demo_examples
from app.modules.catalog.schemas import Content
from app.modules.catalog.deduplication import existing_identities, identity

VERSION = 'real_catalog_v1'


@lru_cache(maxsize=1)
def real_catalog():
    catalog=release('real_catalog_v1')
    entries=catalog['entries']
    if catalog['version']!=VERSION or len(entries)!=700:
        raise ValueError('Expected the versioned release of 700 researched activities')
    if len({e['key'] for e in entries})!=700 or len({e['content']['title'] for e in entries})!=700:
        raise ValueError('Duplicate curated identity or title')
    venues=0
    for entry in entries:
        if not entry['key'].startswith('real:') or entry['availability_verified'] or entry['price_verified']:
            raise ValueError('Invalid curated provenance')
        content=Content.model_validate(entry['content']).model_dump()
        if content['place']:
            venues+=1
            if len(entry['source_ids'])!=1:raise ValueError('A researched place needs its source')
            source=catalog['sources'][entry['source_ids'][0]]
            if content['place']['source_url']!=source['url'] or content['cost']['kind']!='unknown':
                raise ValueError('Source or cost evidence mismatch')
        elif entry['source_ids'] or content['requires_venue_check']:
            raise ValueError('Home recipes must not promise a venue')
        entry['content']=content
    if venues!=400:raise ValueError('Expected 400 researched place experiences')
    return catalog


def counts(store):
    """Report distinct identities and actual recommendable revisions separately."""
    from app.modules.catalog.service import Catalog
    from app.core.values import utcnow
    activities=store.list('activities');revisions=store.list('activity_revisions')
    candidates=Catalog(store,utcnow).candidates()
    release_keys={entry['key'] for entry in real_catalog()['entries']}
    curated_ids={a['id'] for a in activities if a.get('seed_key') in release_keys}
    return dict(activities=len(activities),activity_revisions=len(revisions),
        active_flags=sum(bool(a['active']) for a in activities),
        recommendable=len(candidates),curated_recommendable=sum(a['id'] in curated_ids for a in candidates),
        raw_bank=sum(a.get('seed_key','').startswith('bank:') for a in activities),
        revision_states=dict(Counter(r['state'] for r in revisions)))


def _safe_legacy(activity, revision, expected, history):
    return bool(activity and activity['active'] and not activity.get('withdrawn')
        and revision and revision['state']=='published' and revision.get('origin')=='demo'
        and not revision.get('reviewed_by') and not revision.get('validation_report',{}).get('human_approval')
        and revision.get('content') and content_checksum(revision['content']) in expected.get(activity['seed_key'],set())
        and not any(r.get('origin')=='human' and r.get('content') for r in history))


def import_catalog(store,clock):
    catalog=real_catalog()
    existing={a['seed_key']:a for a in store.list('activities')}
    pending=[e for e in catalog['entries'] if e['key'] not in existing]
    inserted=0
    duplicate_keys=[]
    for offset in range(0,len(pending),25):
        with store.atomic():
            # Recheck stable unique keys under the transaction guard. A restart or
            # concurrent operator may already have committed the previous batch.
            present={a['seed_key'] for a in store.list('activities')}
            identities=existing_identities(store)
            for entry in pending[offset:offset+25]:
                if entry['key'] in present:continue
                content=entry['content'];fingerprint=identity(content)
                if fingerprint in identities:
                    duplicate_keys.append(entry['key']);continue
                activity_id,revision_id=uid(),uid()
                source_metadata={k:v for k,v in entry.items() if k!='content'}
                source_metadata.update(catalog_version=VERSION,researched_on=catalog['researched_on'],
                    sources={key:catalog['sources'][key] for key in entry['source_ids']})
                store.insert('activities',dict(id=activity_id,seed_key=entry['key'],
                    source_file='content/activities.json',source_metadata=source_metadata,
                    raw_title=content['title'],raw_intent='محتوای تألیفی و گردآوری‌شده طبق درخواست مالک در ۲۳ آبان ۱۴۰۵؛ بدون ادعای قیمت یا ظرفیت زنده',
                    primary_dimension=content['primary_dimension'],active=True,published_revision_id=revision_id,
                    next_revision_number=2,start_guard_version=0,created_at=clock()))
                store.insert('activity_revisions',dict(id=revision_id,activity_id=activity_id,
                    revision_number=1,draft_version=1,state='published',content=content,origin='curated',
                    reviewed_by=None,published_at=clock(),created_at=clock(),validation_report={
                        'schema_valid':True,'dramma_version':'dramma_v1','human_approval':False,
                        'publication_basis':catalog['publication_basis'],'catalog_version':VERSION,
                        'import_checksum':content_checksum(content),'source_ids':entry['source_ids'],
                        'evidence_scope':catalog['evidence_scope'],'availability_verified':False,'price_verified':False}))
                present.add(entry['key']);identities[fingerprint]=activity_id;inserted+=1
            store.insert('admin_audit',dict(id=uid(),actor_id='system',action='curated_catalog_batch_imported',
                target_id=VERSION,reason='Owner request 2026-11-14; source references retained; no live availability claim',created_at=clock()))
    # Do not retire the previous catalog until all release identities exist.
    release_keys={e['key'] for e in catalog['entries']}
    present_keys={a['seed_key'] for a in store.list('activities')}
    identities=existing_identities(store)
    if any(e['key'] not in present_keys and identity(e['content']) not in identities for e in catalog['entries']):
        raise ValueError('Incomplete curated release; legacy catalog preserved')
    # Accept both the pre-alignment and current shipped payload, never an editor's
    # arbitrary changes. Adding optional fields must not alter old checksums.
    expected={key:{content_checksum(content)} for key,content in demo_examples(include_iran=True)}
    legacy=json.loads((ROOT/'content/dramma-legacy-checksums.json').read_text())['checksums']
    for key,checksum in legacy.items():expected.setdefault(key,set()).add(checksum)
    revisions=store.list('activity_revisions');by_id={r['id']:r for r in revisions}
    by_activity={}
    for r in revisions:by_activity.setdefault(r['activity_id'],[]).append(r)
    retirement=[a for a in store.list('activities') if _safe_legacy(a,by_id.get(a.get('published_revision_id')),expected,by_activity.get(a['id'],[]))]
    archived=0
    for offset in range(0,len(retirement),25):
        with store.atomic():
            history=store.list('activity_revisions')
            for candidate in retirement[offset:offset+25]:
                activity=store.get('activities',candidate['id'])
                revision=store.get('activity_revisions',activity.get('published_revision_id') or '')
                if not _safe_legacy(activity,revision,expected,[r for r in history if r['activity_id']==activity['id']]):continue
                # Content and published pointer remain for saves/history; active
                # flag and state exclude this record from fresh recommendations.
                activity.update(active=False,retired_by_catalog=VERSION)
                replace(store,'activities',activity)
                revision['state']='archived';replace(store,'activity_revisions',revision)
                store.insert('admin_audit',dict(id=uid(),actor_id='system',action='legacy_demo_archived',
                    target_id=activity['id'],reason=VERSION+': exact shipped unreviewed demo; content/history preserved',created_at=clock()))
                archived+=1
    return {'catalog_version':VERSION,'inserted':inserted,'legacy_archived':archived,'duplicate_keys':duplicate_keys,**counts(store)}


def offline_report():
    catalog=real_catalog()
    venues=[e for e in catalog['entries'] if e['content']['place']]
    return dict(mode='files_only_no_database_write',catalog_version=VERSION,entries=len(catalog['entries']),
        venue_entries=len(venues),home_entries=len(catalog['entries'])-len(venues),sources=len(catalog['sources']),
        cities=len({e['content']['place']['city'] for e in venues}),
        dimensions=dict(Counter(e['content']['primary_dimension'] for e in catalog['entries'])))


def main(argv=None):
    import argparse
    from app.core.config import Settings
    from app.core.storage import create_store,StorageUnavailable
    from app.core.values import utcnow
    parser=argparse.ArgumentParser(description='Validate files or apply the owner-authorized release to real public MongoDB')
    parser.add_argument('--apply',action='store_true',help='Commit 700 curated records and safely archive exact legacy demos')
    args=parser.parse_args(argv)
    if not args.apply:
        print(json.dumps(offline_report(),ensure_ascii=False));return 0
    store=None
    try:
        settings=Settings.load()
        store=create_store({'DATA_BACKEND':settings.data_backend,'MONGODB_URI':settings.mongodb_uri})
        before=counts(store)
        result=import_catalog(store,utcnow)
        print(json.dumps({'mode':'real_mongodb','before':before,'after':result},ensure_ascii=False))
        # Withdrawn and edited records are preserved; never report full activation
        # merely because a batch inserted without error.
        return 0 if result['curated_recommendable']==700 else 2
    except StorageUnavailable as exc:
        # The storage contract guarantees credential-free operational messages.
        print(f'{exc}. MongoDB import not confirmed; no memory fallback was used.',file=__import__('sys').stderr)
        return 1
    except ValueError:
        print('MongoDB import not confirmed. Check locked dependencies, public endpoint connectivity and release validation. No memory fallback was used.',file=__import__('sys').stderr)
        return 1
    finally:
        if store is not None:store.close()


if __name__=='__main__':
    raise SystemExit(main())
