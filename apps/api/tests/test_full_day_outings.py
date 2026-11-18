from copy import deepcopy
from datetime import datetime, timezone
import unittest

from pydantic import ValidationError

from app.core.schemas import Context
from app.core.values import replace
from app.modules.catalog.full_day_outings import coverage_report, full_day_catalog, import_full_day_outings
from app.modules.catalog.schemas import Content
from support import MemoryTestStore

NOW = datetime(2026, 11, 18, tzinfo=timezone.utc)
BASE = dict(available_minutes=1440, outing_days=1, energy='unknown', social_mode='solo',
            party_size=1, venue='away_from_home', budget={'mode': 'flexible'}, city='تهران',
            allow_venue_planning=True, weather='fair', daylight='day')


class FullDayOutingTests(unittest.TestCase):
    def test_only_explicit_supported_full_day_contexts_are_valid(self):
        self.assertEqual(Context(**BASE).outing_days, 1)
        self.assertEqual(Context(**{**BASE, 'available_minutes': 2880, 'outing_days': 2}).outing_days, 2)
        for bad in ({'venue': 'home'}, {'venue': 'any'}, {'venue': 'outdoor'}, {'city': None},
                    {'city': 'رشت'}, {'city': 'New York'}, {'allow_venue_planning': False},
                    {'available_minutes': 2880}, {'available_minutes': 480}, {'outing_days': True},
                    {'outing_days': None}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                Context(**{**BASE, **bad})
        self.assertIsNone(Context(**{**BASE, 'outing_days': None, 'available_minutes': 480, 'city': 'رشت'}).outing_days)

    def test_catalog_guards_scope_schedules_and_unknown_cost(self):
        rows = full_day_catalog()['entries']
        self.assertEqual(len(rows), 100)
        self.assertEqual(len({r['content']['title'] for r in rows}), 100)
        self.assertTrue(all(r['content']['venue'] == 'outdoor' and r['content']['cost']['kind'] == 'unknown' for r in rows))
        base = next(r['content'] for r in rows if r['content']['outing']['days'] == 2)
        for change in (
            lambda c: c['outing'].update(country_code='TR'),
            lambda c: c['place'].update(city='اهواز'),
            lambda c: c['outing'].update(overnight_city=None),
            lambda c: c['outing'].update(one_way_travel_minutes=181),
            lambda c: c['outing']['itinerary'].pop(),
            lambda c: c.update(travel_minutes=c['travel_minutes'] - 1),
            lambda c: c.update(venue='indoor_public'),
        ):
            content = deepcopy(base)
            change(content)
            with self.assertRaises(ValidationError):
                Content.model_validate(content)

    def test_import_publishes_ten_per_origin_and_duration_and_preserves_withdrawal(self):
        store = MemoryTestStore()
        clock = lambda: NOW
        self.assertEqual(import_full_day_outings(store, clock)['inserted'], 100)
        report = coverage_report(store, clock)
        self.assertEqual((report['present'], report['published'], report['eligible']), (100, 100, 100))
        self.assertEqual(report['by_origin_and_days'],
                         {slug: {1: 10, 2: 10} for slug in ('tehran', 'mashhad', 'isfahan', 'shiraz', 'tabriz')})
        activity = next(iter(store.list('activities')))
        self.assertEqual(activity['source_metadata']['catalog_version'], 'full_day_outings_v1')
        revision = store.get('activity_revisions', activity['published_revision_id'])
        self.assertEqual(revision['state'], 'published')
        self.assertFalse(revision['validation_report']['human_approval'])
        activity['active'] = False
        replace(store, 'activities', activity)
        self.assertEqual(import_full_day_outings(store, clock)['inserted'], 0)
        self.assertEqual(coverage_report(store, clock)['published'], 99)
        self.assertEqual(len(store.list('activity_revisions')), 100)
