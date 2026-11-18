import unittest
from datetime import datetime, timezone
from app.core.schemas import Context
from app.core.values import replace
from app.modules.catalog.home_short import home_catalog, import_home_short
from app.modules.catalog.cinema_expansion import import_additive
from app.modules.recommendations.eligibility import eligible
from support import MemoryTestStore

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)

class HomeShortTests(unittest.TestCase):
    def test_actual_constraints_and_dramma(self):
        for entry in home_catalog()['entries']:
            c = entry['content']
            a = {'id': entry['key'], 'active': True, 'state': 'published', 'revision_id': 'r',
                 'published_revision_id': 'r', 'content': c}
            context = Context(available_minutes=20,energy='low',social_mode='solo',party_size=1,
                venue='home',budget={'mode':'free'},mood='skip',owned_items=c['required_items']).model_dump()
            with self.subTest(title=c['title']):
                self.assertEqual(c['dramma']['version'], 'dramma_v1')
                self.assertIsNotNone(eligible(context, a, NOW))
                self.assertIsNone(eligible(context | {'venue':'outdoor'}, a, NOW))
                if c['required_items']:
                    self.assertIsNone(eligible(context | {'owned_items':[]}, a, NOW))
                if not c['quiet_compatible']:
                    self.assertIsNone(eligible(context | {'requires_quiet':True}, a, NOW))

    def test_upgrade_from_previous_home_release_inserts_only_new_records(self):
        store = MemoryTestStore()
        old = {**home_catalog(), 'entries': home_catalog()['entries'][:12]}
        import_additive(store, lambda: NOW, old, version='home_short_v1',
            source_file='content/home-short-activities.json', raw_intent='old release', reason='test upgrade')
        original = store.list('activities')[0]
        revision = store.get('activity_revisions', original['published_revision_id'])
        self.assertEqual(import_home_short(store, lambda: NOW)['inserted'], 8)
        self.assertEqual(len(store.list('activities')), 20)
        self.assertEqual(store.get('activity_revisions', revision['id']), revision)

    def test_additive_import_does_not_reactivate(self):
        store = MemoryTestStore()
        self.assertEqual(import_home_short(store, lambda: NOW)['inserted'], 20)
        a = store.list('activities')[0]
        a['active'] = False
        replace(store, 'activities', a)
        self.assertEqual(import_home_short(store, lambda: NOW)['inserted'], 0)
        self.assertFalse(store.get('activities', a['id'])['active'])

if __name__ == '__main__':
    unittest.main()
