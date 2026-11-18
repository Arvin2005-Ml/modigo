import unittest
from datetime import datetime, timezone
from app.core.values import replace
from app.modules.catalog.cinema_expansion import cinema_catalog, import_cinemas
from app.modules.catalog.curated import real_catalog
from app.core.schemas import Context
from app.modules.recommendations.eligibility import eligible
from support import MemoryTestStore


class CinemaExpansionTests(unittest.TestCase):
    def test_sources_identities_and_dramma_are_validated(self):
        entries = cinema_catalog()['entries']
        self.assertEqual(len(entries), 77)
        self.assertFalse({e['key'] for e in entries} & {e['key'] for e in real_catalog()['entries']})
        self.assertTrue({'رشت', 'اصفهان', 'تهران', 'شیراز', 'ساری', 'نوشهر'} <=
                        {e['content']['place']['city'] for e in entries})
        self.assertTrue(all(e['content']['dramma']['version'] == 'dramma_v1' for e in entries))

    def test_city_cost_and_venue_permission_remain_hard_filters(self):
        entry = next(e for e in cinema_catalog()['entries'] if e['content']['place']['city'] == 'رشت')
        activity = {'id': entry['key'], 'active': True, 'state': 'published', 'revision_id': 'r',
                    'published_revision_id': 'r', 'content': entry['content']}
        context = Context(available_minutes=240, energy='unknown', social_mode='solo', party_size=1,
            venue='indoor_public', budget={'mode': 'flexible'}, mood='skip', city='رشت',
            allow_venue_planning=True).model_dump()
        now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.assertIsNotNone(eligible(context, activity, now))
        self.assertIsNone(eligible(context | {'city': 'تهران'}, activity, now))
        self.assertIsNone(eligible(context | {'allow_venue_planning': False}, activity, now))
        self.assertIsNone(eligible(context | {'budget': {'mode': 'free'}}, activity, now))

    def test_import_is_additive_idempotent_and_preserves_edits(self):
        store = MemoryTestStore()
        clock = lambda: datetime(2026, 11, 14, tzinfo=timezone.utc)
        store.insert('activities', {'id': 'existing', 'seed_key': 'human:existing', 'active': False})
        self.assertEqual(import_cinemas(store, clock)['inserted'], 77)
        cinema = next(a for a in store.list('activities') if a['seed_key'].startswith('real:'))
        cinema['active'] = False
        replace(store, 'activities', cinema)
        revision = store.get('activity_revisions', cinema['published_revision_id'])
        self.assertEqual(import_cinemas(store, clock)['inserted'], 0)
        self.assertFalse(store.get('activities', 'existing')['active'])
        self.assertFalse(store.get('activities', cinema['id'])['active'])
        self.assertEqual(store.get('activity_revisions', revision['id']), revision)
        self.assertEqual(len(store.list('activity_revisions')), 77)


if __name__ == '__main__':
    unittest.main()
