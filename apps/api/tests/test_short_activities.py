"""The actual curated release must cover common restrictive contexts."""
import unittest
from datetime import datetime, timezone
from itertools import product
from app.core.schemas import Context
from app.core.values import replace
from app.modules.catalog.curated import import_catalog
from app.modules.catalog.short_activities import import_short_activities
from app.modules.catalog.service import Catalog
from app.modules.recommendations.coverage import coverage
from app.modules.recommendations.eligibility import eligible
from app.modules.recommendations.ranking import rank
from support import MemoryTestStore

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)

class ShortActivitiesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = MemoryTestStore()
        import_catalog(cls.store, lambda: NOW)
        cls.before = Catalog(cls.store, lambda: NOW).candidates()
        import_short_activities(cls.store, lambda: NOW)
        cls.after = Catalog(cls.store, lambda: NOW).candidates()

    def test_real_release_coverage_and_accessibility(self):
        before, after = coverage(self.before, NOW), coverage(self.after, NOW)
        self.assertEqual(sum(r['eligible_count'] == 0 for r in before), 648)
        self.assertEqual(len(after), 648)
        for row in after:
            with self.subTest(row=row):
                self.assertGreaterEqual(row['eligible_count'], 1)
                self.assertGreaterEqual(row['quiet_seated_count'], 1)

    def test_short_context_rank_and_hard_filters(self):
        for venue, energy, mood, social, size in product(
                ('home','outdoor','indoor_public','any'), ('low','medium','high','unknown'),
                ('tired','restless','bored','low','okay','skip'), ('solo','together'), (1, 12)):
            if social == 'solo' and size != 1 or social == 'together' and size == 1:
                continue
            context = Context(available_minutes=5,venue=venue,energy=energy,mood=mood,
                social_mode=social,party_size=size,budget={'mode':'free'},max_mobility='seated',
                requires_step_free=True,requires_quiet=True).model_dump()
            results = rank(self.after, context, NOW, set(), 'test', [], [], [], count=6)
            with self.subTest(venue=venue, energy=energy, mood=mood, social=social):
                self.assertTrue(results)
                self.assertTrue(all(eligible(context, row['activity'], NOW) for row in results))
                for row in results:
                    activity = row['activity']
                    self.assertIsNone(eligible(context | {'blocked_tags':activity['content']['tags']}, activity, NOW))
                    self.assertIsNone(eligible(context, activity, NOW, {activity['id']}))

    def test_import_is_additive_and_idempotent(self):
        store = MemoryTestStore()
        self.assertEqual(import_short_activities(store, lambda: NOW)['inserted'], 16)
        activity = store.list('activities')[0]
        activity['active'] = False
        replace(store, 'activities', activity)
        self.assertEqual(import_short_activities(store, lambda: NOW)['inserted'], 0)
        self.assertFalse(store.get('activities', activity['id'])['active'])

if __name__ == '__main__':
    unittest.main()
