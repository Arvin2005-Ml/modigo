"""Content coverage regressions, checked against real eligibility and ranking."""
import unittest
from datetime import datetime, timezone
from itertools import product

from app.core.schemas import Context
from support import MemoryTestStore
from app.core.values import replace
from app.modules.catalog.bootstrap import demo_examples, seed_demo
from app.modules.catalog.service import Catalog
from app.modules.recommendations.coverage import coverage
from app.modules.recommendations.eligibility import eligible
from app.modules.recommendations.ranking import rank

NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)


class CatalogCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = MemoryTestStore()
        seed_demo(cls.store, lambda: NOW)
        cls.candidates = Catalog(cls.store, lambda: NOW).candidates()

    def ranked(self, context, excluded=None):
        return rank(self.candidates, context, NOW, excluded or set(), 'coverage-test', [], [], [], count=6)

    def test_648_onboarding_combinations_have_six_without_items(self):
        rows = coverage(self.candidates, NOW)
        self.assertEqual(len(rows), 648)
        for row in rows:
            with self.subTest(row=row):
                self.assertGreaterEqual(row['eligible_count'], 6)
                self.assertGreaterEqual(row['quiet_seated_count'], 6)

    def test_shortest_slates_stay_full_for_every_energy_and_mood(self):
        # Mood and energy must not accidentally become hard filters.
        for venue, (mode, size), energy, mood in product(
            ('home', 'outdoor', 'indoor_public', 'any'),
            (('solo', 1), ('together', 2), ('together', 12), ('either', 1), ('either', 12)),
            ('low', 'medium', 'high', 'unknown'), ('tired', 'restless', 'bored', 'low', 'okay', 'skip')):
            context = Context(available_minutes=5, venue=venue, social_mode=mode, party_size=size,
                energy=energy, mood=mood, budget={'mode': 'free'}, requires_quiet=True,
                requires_step_free=True, max_mobility='seated').model_dump()
            result = self.ranked(context)
            with self.subTest(venue=venue, mode=mode, size=size, energy=energy, mood=mood):
                self.assertEqual(len(result), 6)
                self.assertEqual(len({r['activity']['id'] for r in result}), 6)
                self.assertTrue(all(eligible(context, r['activity'], NOW) for r in result))

    def test_equipment_and_longer_sessions_add_real_choices_in_each_setting(self):
        for venue, mode in product(('home', 'outdoor', 'indoor_public'), ('solo', 'together')):
            context = Context(available_minutes=120, venue=venue, social_mode=mode,
                party_size=12 if mode == 'together' else 1, energy='medium', mood='skip',
                budget={'mode': 'free'}, owned_items=['paper', 'pen', 'phone', 'book'],
                weather='fair', daylight='day').model_dump()
            longer = [a for a in self.candidates if eligible(context, a, NOW) and
                      sum(a['content'][k] for k in ('active_minutes', 'setup_minutes', 'travel_minutes')) >= 30]
            with self.subTest(venue=venue, mode=mode):
                self.assertGreaterEqual(len(longer), 4)
                self.assertTrue(any(a['content']['required_items'] for a in longer))

    def test_interests_change_the_selection_with_available_tools(self):
        base = Context(available_minutes=60, venue='home', social_mode='solo', party_size=1,
            energy='unknown', mood='skip', budget={'mode': 'free'}, owned_items=['paper', 'pen', 'phone']).model_dump()
        def first(tag):
            return rank(self.candidates, {**base, 'liked_tags': [tag]}, NOW,
                        set(), 'coverage-test', [], [], [])[0]
        drawing, music = first('drawing'), first('music')
        self.assertIn('drawing', drawing['activity']['content']['tags'])
        self.assertIn('music', music['activity']['content']['tags'])
        self.assertNotEqual(drawing['activity']['id'], music['activity']['id'])
        self.assertEqual(drawing, first('drawing'))

    def test_short_context_exhaustion_stays_empty_instead_of_repeating(self):
        context = Context(available_minutes=5, venue='outdoor', social_mode='together', party_size=12,
            energy='low', mood='skip', budget={'mode': 'free'}).model_dump()
        first = self.ranked(context)
        excluded = {r['activity']['id'] for r in first}
        self.assertEqual(len(first), 6)
        self.assertEqual(self.ranked(context, excluded), [])

    def test_supplement_has_stable_keys_and_stays_explicit_demo(self):
        self.assertEqual(len(demo_examples()), 131)
        self.assertEqual(len(self.candidates), 113)
        store = MemoryTestStore()
        seed_demo(store, lambda: NOW)
        before = store.list('activities')
        withdrawn = before[0]
        withdrawn['active'] = False
        replace(store, 'activities', withdrawn)
        seed_demo(store, lambda: NOW)
        self.assertEqual({a['id'] for a in before}, {a['id'] for a in store.list('activities')})
        self.assertFalse(store.get('activities', withdrawn['id'])['active'])
        for r in store.list('activity_revisions'):
            self.assertEqual(r['origin'], 'demo')
            self.assertTrue(r['validation_report']['local_demo_only'])
            self.assertFalse(r['validation_report']['human_approval'])
            self.assertIsNone(r['reviewed_by'])


if __name__ == '__main__':
    unittest.main()
