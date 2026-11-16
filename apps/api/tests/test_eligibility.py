import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from app.modules.recommendations.eligibility import eligible

NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)
CONTEXT = dict(available_minutes=30, venue='home', social_mode='solo', party_size=1,
               budget={'mode': 'free', 'cap_toman': 0}, owned_items=[], max_mobility='active')
ACTIVITY = dict(id='a', active=True, state='published', revision_id='r', published_revision_id='r', content=dict(
    active_minutes=20, setup_minutes=5, travel_minutes=5, venue='home', supported_social_modes=['solo', 'together'],
    min_people=1, max_people=12, cost={'kind': 'free'}, required_items=[], mobility_required='seated',
    step_free=True, quiet_compatible=True, tags=['music'], requires_async_contact=False,
    weather_requirement='any', daylight_requirement='any'))

class EligibilityTests(unittest.TestCase):
    def setUp(self):
        self.ctx, self.a = deepcopy(CONTEXT), deepcopy(ACTIVITY)
    def check(self):
        return eligible(self.ctx, self.a, NOW)
    def test_time_includes_setup_and_travel(self):
        self.assertEqual(self.check(), ('solo', 1))
        self.a['content']['travel_minutes'] = 10
        self.assertIsNone(self.check())
    def test_publication_and_exclusion(self):
        for key, value in [('active', False), ('state', 'draft'), ('published_revision_id', 'old')]:
            a = deepcopy(self.a); a[key] = value
            self.assertIsNone(eligible(self.ctx, a, NOW))
        self.assertIsNone(eligible(self.ctx, self.a, NOW, {'a'}))
    def test_social_and_group_cost(self):
        self.ctx.update(social_mode='together', party_size=3, budget={'mode': 'cap', 'cap_toman': 300000})
        cost = dict(kind='estimated', max_toman=120000, basis='per_person', verified_at=NOW-timedelta(days=1), valid_until=NOW+timedelta(days=1))
        self.a['content']['cost'] = cost
        self.assertIsNone(self.check())
        cost['max_toman'] = 80000
        self.assertEqual(self.check(), ('together', 3))
        cost['valid_until'] = NOW
        self.assertIsNone(self.check())
        cost.update(kind='unknown')
        self.assertIsNone(self.check())
    def test_either_with_one_person_cannot_select_group(self):
        self.ctx['social_mode'] = 'either'
        self.a['content'].update(supported_social_modes=['together'], min_people=2)
        self.assertIsNone(self.check())
    def test_constraints_fail_closed(self):
        cases = [({'required_items': ['phone']}, {}), ({'requires_async_contact': True}, {}),
                 ({'weather_requirement': 'fair'}, {}), ({'daylight_requirement': 'day'}, {}),
                 ({'step_free': None}, {'requires_step_free': True}),
                 ({'quiet_compatible': None}, {'requires_quiet': True}),
                 ({'tags': ['music']}, {'blocked_tags': ['music']}),
                 ({'mobility_required': 'light'}, {'max_mobility': 'seated'})]
        for changes, ctx in cases:
            with self.subTest(changes=changes, ctx=ctx):
                a, c = deepcopy(ACTIVITY), deepcopy(CONTEXT)
                a['content'].update(changes); c.update(ctx)
                self.assertIsNone(eligible(c, a, NOW))
    def test_free_and_unknown_cost(self):
        self.a['content']['cost'] = {'kind': 'unknown'}
        self.assertIsNone(self.check())
        self.ctx['budget'] = {'mode': 'flexible', 'cap_toman': None}
        self.assertEqual(self.check(), ('solo', 1))

if __name__ == '__main__':
    unittest.main()
