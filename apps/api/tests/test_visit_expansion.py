import unittest
from datetime import datetime, timezone
from app.core.schemas import Context
from app.core.values import replace
from app.modules.catalog.cinema_expansion import cinema_catalog
from app.modules.catalog.curated import real_catalog
from app.modules.catalog.food_expansion import food_catalog
from app.modules.catalog.visit_expansion import visit_catalog, import_visits
from app.modules.recommendations.eligibility import eligible
from support import MemoryTestStore


class VisitExpansionTests(unittest.TestCase):
    def test_sources_city_dramma_and_hard_filters(self):
        entries = visit_catalog()['entries']
        self.assertEqual(len(entries), 43)
        old = set()
        for release in (real_catalog(), cinema_catalog(), food_catalog()):
            old |= {e['key'] for e in release['entries']}
        self.assertFalse(old & {e['key'] for e in entries})
        self.assertTrue({'تهران', 'رشت', 'لاهیجان', 'اصفهان', 'کیش'} <=
                        {e['content']['place']['city'] for e in entries})
        now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        for entry in entries:
            content = entry['content']
            self.assertEqual(content['dramma']['version'], 'dramma_v1')
            self.assertFalse(entry['availability_verified'])
            self.assertFalse(entry['price_verified'])
            activity = {'id': entry['key'], 'active': True, 'state': 'published', 'revision_id': 'r',
                        'published_revision_id': 'r', 'content': content}
            context = Context(available_minutes=240, energy='unknown', social_mode='solo', party_size=1,
                venue=content['venue'], budget={'mode': 'flexible'}, mood='skip', city=content['place']['city'],
                weather='fair', allow_venue_planning=True).model_dump()
            with self.subTest(place=content['place']['name']):
                self.assertIsNotNone(eligible(context, activity, now))
                self.assertIsNone(eligible(context | {'city': 'شهر دیگر'}, activity, now))
                self.assertIsNone(eligible(context | {'allow_venue_planning': False}, activity, now))
                self.assertIsNone(eligible(context | {'budget': {'mode': 'free'}}, activity, now))

    def test_idempotent_import_preserves_existing_and_inactive_revision(self):
        store = MemoryTestStore()
        clock = lambda: datetime(2026, 11, 14, tzinfo=timezone.utc)
        store.insert('activities', {'id': 'old', 'seed_key': 'human:old', 'active': False})
        self.assertEqual(import_visits(store, clock)['inserted'], 43)
        item = next(a for a in store.list('activities') if a['id'] != 'old')
        item['active'] = False
        replace(store, 'activities', item)
        revision = store.get('activity_revisions', item['published_revision_id'])
        self.assertEqual(import_visits(store, clock)['inserted'], 0)
        self.assertFalse(store.get('activities', 'old')['active'])
        self.assertFalse(store.get('activities', item['id'])['active'])
        self.assertEqual(store.get('activity_revisions', revision['id']), revision)


if __name__ == '__main__':
    unittest.main()
