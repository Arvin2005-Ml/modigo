"""Authored paid plans must never bypass budget, venue consent or execution rules."""
import importlib.util
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError
from support import MemoryTestStore
from app.core.schemas import Context
from app.core.values import replace
from app.modules.catalog.bootstrap import iran_catalog, seed_demo
from app.modules.catalog.schemas import Content
from app.modules.catalog.service import Catalog
from app.modules.recommendations.eligibility import eligible
from app.modules.recommendations.ranking import rank

NOW = datetime(2026, 11, 13, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[3]


class IranCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = iran_catalog()
        cls.entries = cls.payload['entries']
        cls.store = MemoryTestStore()
        seed_demo(cls.store, lambda: NOW)
        cls.activities = {a['seed_key'].removeprefix('demo:'): a for a in cls.store.list('activities')}
        cls.candidates = [a for a in Catalog(cls.store, lambda: NOW).candidates()
                          if a['id'] in {cls.activities[e['key']]['id'] for e in cls.entries}]
        cls.by_key = {e['key']: next(a for a in cls.candidates if a['id'] == cls.activities[e['key']]['id'])
                      for e in cls.entries}

    def context(self, **changes):
        return Context(**(dict(available_minutes=480, energy='unknown', mood='skip',
            venue='any', social_mode='either', party_size=12, owned_items=['phone', 'towel'],
            budget={'mode': 'flexible'}, allow_venue_planning=True, weather='fair', daylight='day') | changes)).model_dump()

    def test_300_complete_unique_plans_and_reproducible_authored_source(self):
        self.assertEqual(len(self.entries), 300)
        self.assertEqual(len(self.candidates), 300)
        self.assertEqual(len({e['content']['title'] for e in self.entries}), 300)
        self.assertEqual(len({tuple(e['content']['steps']) for e in self.entries}), 300)
        self.assertEqual(len(Counter(e['category'] for e in self.entries)), 25)
        spec = importlib.util.spec_from_file_location('build_iran', ROOT / 'scripts/build-iran-catalog.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        self.assertEqual(builder.build(), self.payload)
        for entry in self.entries:
            content = Content.model_validate(entry['content'])
            self.assertEqual(content.model_dump(mode='json'), entry['content'])
            self.assertTrue(content.requires_venue_check)
            self.assertIsNone(content.step_free)
            self.assertIsNone(content.quiet_compatible)
            self.assertEqual(content.cost.kind, 'unknown')
            self.assertIsNone(content.cost.verified_at)

    def test_free_and_capped_budgets_exclude_all_unverified_prices(self):
        for budget in ({'mode': 'free'}, {'mode': 'cap', 'cap_toman': 100_000_000}):
            context = self.context(budget=budget)
            self.assertFalse(any(eligible(context, a, NOW) for a in self.candidates))

    def test_venue_plans_require_explicit_boolean_opt_in(self):
        for value in (False,):
            context = self.context(allow_venue_planning=value)
            self.assertFalse(any(eligible(context, a, NOW) for a in self.candidates))
        context = self.context()
        del context['allow_venue_planning']
        self.assertFalse(any(eligible(context, a, NOW) for a in self.candidates))
        with self.assertRaises(ValidationError):
            self.context(allow_venue_planning='yes')

    def test_every_plan_has_a_compatible_execution_context(self):
        for activity in self.candidates:
            content = activity['content']
            people = content['min_people'] if content['supported_social_modes'] == ['together'] else 1
            context = self.context(social_mode='together' if people > 1 else 'solo', party_size=people)
            with self.subTest(title=content['title']):
                self.assertIsNotNone(eligible(context, activity, NOW))

    def test_time_travel_group_weather_items_and_access_still_apply(self):
        cinema = self.by_key['iran-cinema-01']
        self.assertIsNotNone(eligible(self.context(available_minutes=210), cinema, NOW))
        self.assertIsNone(eligible(self.context(available_minutes=209), cinema, NOW))
        padel = self.by_key['iran-racket-03']
        self.assertIsNone(eligible(self.context(party_size=2, social_mode='together'), padel, NOW))
        self.assertIsNotNone(eligible(self.context(party_size=4, social_mode='together'), padel, NOW))
        self.assertIsNone(eligible(self.context(weather='unknown', party_size=4, social_mode='together'), padel, NOW))
        self.assertIsNone(eligible(self.context(requires_step_free=True), cinema, NOW))
        swimming = self.by_key['iran-water_ice-01']
        self.assertIsNone(eligible(self.context(owned_items=[]), swimming, NOW))
        self.assertIsNone(eligible(self.context(venue='home'), cinema, NOW))

    def test_ranking_and_replacement_cannot_reintroduce_seen_or_ineligible_plans(self):
        context = self.context(social_mode='solo', party_size=1, venue='indoor_public')
        shown = set()
        for _ in range(7):
            result = rank(self.candidates, context, NOW, shown, 'fixed', [], [], [])
            self.assertEqual(len(result), 1)
            item = result[0]['activity']
            self.assertNotIn(item['id'], shown)
            self.assertIsNotNone(eligible(context, item, NOW))
            shown.add(item['id'])
        self.assertEqual(rank(self.candidates, self.context(budget={'mode': 'free'}), NOW,
            set(), 'fixed', [], [], []), [])

    def test_sources_and_seed_state_survive_reimport_without_fake_approval(self):
        key = self.entries[0]['key']
        first = self.activities[key]
        revision = self.store.get('activity_revisions', first['published_revision_id'])
        self.assertEqual(revision['origin'], 'demo')
        self.assertFalse(revision['validation_report']['human_approval'])
        self.assertFalse(revision['validation_report']['availability_verified'])
        self.assertTrue(first['source_metadata']['sources'])
        ids = {a['id'] for a in self.store.list('activities')}
        store = MemoryTestStore()
        seed_demo(store, lambda: NOW)
        withdrawn = next(a for a in store.list('activities') if a['seed_key'] == first['seed_key'])
        withdrawn.update(active=False)
        replace(store, 'activities', withdrawn)
        before_ids = {a['id'] for a in store.list('activities')}
        seed_demo(store, lambda: NOW)
        self.assertEqual(before_ids, {a['id'] for a in store.list('activities')})
        self.assertFalse(store.get('activities', withdrawn['id'])['active'])
        self.assertEqual(len(ids), 431)


if __name__ == '__main__':
    unittest.main()
