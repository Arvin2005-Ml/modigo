import unittest
from datetime import datetime, timezone
from app.core.schemas import Context
from app.core.values import replace
from app.modules.catalog.cinema_expansion import cinema_catalog
from app.modules.catalog.curated import real_catalog
from app.modules.catalog.food_expansion import food_catalog, import_food
from app.modules.recommendations.eligibility import eligible
from support import MemoryTestStore


class FoodExpansionTests(unittest.TestCase):
    def test_release_has_distinct_sourced_executable_dining(self):
        entries = food_catalog()['entries']
        self.assertEqual(len(entries), 70)
        existing = {e['key'] for e in real_catalog()['entries']} | {e['key'] for e in cinema_catalog()['entries']}
        self.assertFalse(existing & {e['key'] for e in entries})
        self.assertEqual({e['content']['place']['city'] for e in entries}, {'رشت', 'شیراز', 'اصفهان'})
        now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        for entry in entries:
            content = entry['content']
            self.assertEqual(content['dramma']['version'], 'dramma_v1')
            self.assertFalse(entry['availability_verified'])
            self.assertFalse(entry['price_verified'])
            self.assertIn('صرف حضوری', content['first_step'])
            activity = {'id': entry['key'], 'active': True, 'state': 'published', 'revision_id': 'r',
                        'published_revision_id': 'r', 'content': content}
            context = Context(available_minutes=240, energy='unknown', social_mode='solo', party_size=1,
                venue='indoor_public', budget={'mode': 'flexible'}, mood='skip', city=content['place']['city'],
                allow_venue_planning=True).model_dump()
            with self.subTest(place=content['place']['name']):
                self.assertIsNotNone(eligible(context, activity, now))
                self.assertIsNone(eligible(context | {'city': 'شهری دیگر'}, activity, now))
                self.assertIsNone(eligible(context | {'allow_venue_planning': False}, activity, now))
                self.assertIsNone(eligible(context | {'budget': {'mode': 'free'}}, activity, now))

    def test_import_preserves_existing_and_does_not_restore_withdrawn(self):
        store = MemoryTestStore()
        clock = lambda: datetime(2026, 11, 14, tzinfo=timezone.utc)
        store.insert('activities', {'id': 'old', 'seed_key': 'human:old', 'active': False})
        self.assertEqual(import_food(store, clock)['inserted'], 70)
        item = next(a for a in store.list('activities') if a['id'] != 'old')
        item['active'] = False
        replace(store, 'activities', item)
        revision = store.get('activity_revisions', item['published_revision_id'])
        self.assertEqual(import_food(store, clock)['inserted'], 0)
        self.assertFalse(store.get('activities', 'old')['active'])
        self.assertFalse(store.get('activities', item['id'])['active'])
        self.assertEqual(store.get('activity_revisions', revision['id']), revision)
        self.assertEqual(len(store.list('activity_revisions')), 70)


if __name__ == '__main__':
    unittest.main()
