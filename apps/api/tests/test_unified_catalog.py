import unittest
from datetime import datetime, timezone
from app.core.values import replace
from app.modules.catalog.import_unified import import_unified
from app.modules.catalog.unified import unified_catalog
from app.modules.catalog.deduplication import identity, duplicate_records
from app.modules.catalog.cinema_expansion import import_additive
from app.modules.catalog.everyday_activities import everyday_catalog
from app.modules.catalog.curated import real_catalog
from support import MemoryTestStore

NOW=datetime(2026,11,14,tzinfo=timezone.utc)

class UnifiedCatalogTests(unittest.TestCase):
    def test_combined_import_is_idempotent_and_skips_reviewed_duplicates(self):
        data=unified_catalog();self.assertEqual(len(data['releases']),7)
        s=MemoryTestStore();first=import_unified(s,lambda:NOW)
        self.assertEqual(first['inserted'],1015)
        self.assertEqual(set(first['duplicates_skipped']), {'real:everyday-group-'+i for i in ('005','007','012','015','016','019')})
        self.assertEqual(len(s.list('activities')),1015)
        second=import_unified(s,lambda:NOW)
        self.assertEqual(second['inserted'],0)
        self.assertEqual(set(second['duplicates_skipped']), {'real:everyday-group-'+i for i in ('005','007','012','015','016','019')})
        self.assertEqual(len(s.list('activities')),1015)

    def test_reverse_import_order_preserves_existing_and_reuses_identity(self):
        existing=next(e for e in everyday_catalog()['entries'] if e['key']=='real:everyday-group-007')
        canonical=next(e for e in real_catalog()['entries'] if e['content']['title']=='اسم‌فامیل کلاسیک')
        self.assertEqual(identity(existing['content']),identity(canonical['content']))
        s=MemoryTestStore()
        catalog={**everyday_catalog(), 'entries':[existing]}
        import_additive(s,lambda:NOW,catalog,version='old',source_file='old',raw_intent='test',reason='test')
        item=s.list('activities')[0];item['active']=False;replace(s,'activities',item)
        from app.modules.catalog.curated import import_catalog
        result=import_catalog(s,lambda:NOW)
        self.assertIn(canonical['key'],result['duplicate_keys'])
        self.assertFalse(s.get('activities',item['id'])['active'])
        self.assertFalse(any(a.get('seed_key')==canonical['key'] for a in s.list('activities')))

    def test_existing_duplicates_are_reported_without_deletion(self):
        s=MemoryTestStore()
        original=next(e for e in everyday_catalog()['entries'] if e['key']=='real:everyday-group-007')
        import_additive(s,lambda:NOW,{**everyday_catalog(), 'entries':[original]},
            version='test',source_file='old',raw_intent='test',reason='test')
        a=s.list('activities')[0];r=s.get('activity_revisions',a['published_revision_id'])
        second={**a,'id':'duplicate-activity','seed_key':'human:existing','published_revision_id':'duplicate-revision'}
        second_revision={**r,'id':'duplicate-revision','activity_id':second['id']}
        s.insert('activities',second);s.insert('activity_revisions',second_revision)
        self.assertEqual(duplicate_records(s),[sorted([a['id'],second['id']])])
        self.assertEqual(len(s.list('activities')),2)

    def test_location_and_distinct_titles_are_not_collapsed(self):
        c={'title':'تجربه بازی','venue':'home','place':None}
        self.assertNotEqual(identity(c),identity({**c,'title':'تجربه سفال'}))
        a={**c,'venue':'indoor_public','place':{'city':'رشت','name':'سینما'}}
        self.assertNotEqual(identity(a),identity({**a,'place':{'city':'تهران','name':'سینما'}}))

if __name__=='__main__':unittest.main()
