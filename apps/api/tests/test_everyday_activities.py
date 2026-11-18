import unittest
from datetime import datetime, timezone
from app.core.schemas import Context
from app.core.values import replace
from app.modules.catalog.everyday_activities import everyday_catalog, import_everyday
from app.modules.recommendations.eligibility import eligible
from support import MemoryTestStore

NOW=datetime(2026,11,14,tzinfo=timezone.utc)

class EverydayActivitiesTests(unittest.TestCase):
    def test_constraints_and_meaningful_dramma_mapping(self):
        entries=everyday_catalog()['entries']
        self.assertEqual(len(entries),60)
        self.assertEqual(sum(e['content']['primary_dimension']=='affiliation' for e in entries),30)
        self.assertEqual(len({e['content']['title'] for e in entries}),60)
        for e in entries:
            c=e['content']; group=e['category']=='shared'
            activity={'id':e['key'],'active':True,'state':'published','revision_id':'r','published_revision_id':'r','content':c}
            context=Context(available_minutes=30,energy='low',social_mode='together' if group else 'solo',
                party_size=2 if group else 1,venue='home',budget={'mode':'free'},mood='skip',owned_items=c['required_items']).model_dump()
            with self.subTest(title=c['title']):
                self.assertEqual(c['dramma']['mechanisms'][0]['dimension'],c['primary_dimension'])
                self.assertIsNotNone(eligible(context,activity,NOW))
                self.assertIsNone(eligible(context|{'venue':'outdoor'},activity,NOW))
                self.assertIsNone(eligible(context|{'social_mode':'solo' if group else 'together', 'party_size':1 if group else 2},activity,NOW))
                if c['required_items']:
                    self.assertIsNone(eligible(context|{'owned_items':[]},activity,NOW))
                if not c['quiet_compatible']:
                    self.assertIsNone(eligible(context|{'requires_quiet':True},activity,NOW))
                if c['max_people']==2:
                    self.assertIsNone(eligible(context|{'party_size':3},activity,NOW))

    def test_idempotent_import_preserves_withdrawal(self):
        s=MemoryTestStore()
        self.assertEqual(import_everyday(s,lambda:NOW)['inserted'],60)
        a=s.list('activities')[0]; a['active']=False; replace(s,'activities',a)
        revision=s.get('activity_revisions',a['published_revision_id'])
        self.assertEqual(import_everyday(s,lambda:NOW)['inserted'],0)
        self.assertFalse(s.get('activities',a['id'])['active'])
        self.assertEqual(s.get('activity_revisions',revision['id']),revision)

if __name__=='__main__': unittest.main()
