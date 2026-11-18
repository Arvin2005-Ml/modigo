"""Situational needs and explicit selections, without a trained model."""
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from app.core.schemas import Context, DIMENSIONS
from app.modules.catalog.bootstrap import demo_examples
from app.modules.recommendations.ranking import rank, GOALS, current_needs, dimension_preferences
from app.modules.recommendations.service import planning_alternatives

NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)


class NeedRankingTests(unittest.TestCase):
    def setUp(self):
        content = deepcopy(demo_examples()[0][1])
        content.update(active_minutes=10, setup_minutes=0, travel_minutes=0, energy_required='low',
            supported_social_modes=['solo', 'together'], min_people=1, max_people=12,
            venue='home', required_items=[], tags=['games'], secondary_dimensions=[])
        self.candidates = []
        for dimension in DIMENSIONS:
            c = {**content, 'primary_dimension': dimension}
            self.candidates.append(dict(id=dimension, revision_id=dimension, published_revision_id=dimension,
                active=True, state='published', content=c))
        self.context = Context(available_minutes=30, energy='low', social_mode='solo', party_size=1,
            venue='home', budget={'mode': 'free'}, mood='skip').model_dump()

    def choice(self, dimension, index, session=None):
        return dict(id=str(index), activity_id='old-' + str(index), recommendation_session_id=session or str(index),
            primary_dimension_snapshot=dimension, status='completed',
            content_snapshot={'tags': ['games'], 'primary_dimension': dimension},
            started_at=NOW - timedelta(days=20) + timedelta(minutes=index),
            completed_at=NOW - timedelta(days=19))

    def first(self, context=None, history=None, candidates=None):
        result = rank(candidates or self.candidates, context or self.context, NOW, set(),
                      'fixed-seed', history or [], [], [])
        self.assertEqual(len(result), 1)
        return result[0]['activity']['content']['primary_dimension']

    def test_each_new_question_independently_prioritizes_all_six_needs(self):
        for field in ('need_now', 'desired_outcome'):
            for goal, dimension in GOALS.items():
                with self.subTest(field=field, goal=goal):
                    self.assertEqual(self.first({**self.context, field: goal}), dimension)

    def test_first_answer_breaks_a_conflict_and_second_is_next(self):
        context = {**self.context, 'need_now': 'learn', 'desired_outcome': 'unwind'}
        self.assertEqual(current_needs(context), {'mastery': .6, 'relaxation': .4})
        self.assertEqual(self.first(context), 'mastery')
        remaining = [a for a in self.candidates if a['id'] != 'mastery']
        self.assertEqual(self.first(context, candidates=remaining), 'relaxation')

    def test_unknown_answers_use_the_profile_goal_then_conditions(self):
        self.assertEqual(current_needs(self.context), {})
        self.assertEqual(self.first({**self.context, 'goal': 'meaning'}), 'meaning')
        self.assertEqual(self.first(), self.first())

    def test_one_intent_replaces_legacy_answers_and_mood(self):
        legacy = {**self.context, 'need_now': 'unwind', 'desired_outcome': 'connect', 'mood': 'bored'}
        history = [self.choice('relaxation', i) for i in range(10)]
        for goal, dimension in GOALS.items():
            with self.subTest(goal=goal):
                self.assertEqual(self.first({**legacy, 'activity_intent': goal}, history), dimension)
        neutral = {**legacy, 'activity_intent': 'any'}
        self.assertEqual(current_needs(neutral), {})
        self.assertEqual(self.first(neutral, history), 'relaxation')
        self.assertEqual(self.first({**neutral, 'goal': 'meaning'}, history), 'meaning')
        scored = rank(self.candidates, neutral, NOW, set(), 'fixed', [], [], [], count=6)
        self.assertEqual(len({item['score'] for item in scored}), 1)

    def test_frequent_selections_go_first_when_current_need_is_unknown(self):
        history = [self.choice('autonomy', i) for i in range(4)] + [self.choice('mastery', 10)]
        self.assertEqual(self.first(history=history), 'autonomy')
        extended = history + [self.choice('mastery', i) for i in range(20, 25)]
        self.assertEqual(self.first(history=extended), 'mastery')

    def test_current_need_beats_a_large_history_for_another_dimension(self):
        history = [self.choice('mastery', i) for i in range(30)]
        self.assertEqual(self.first({**self.context, 'need_now': 'unwind'}, history), 'relaxation')

    def test_one_vote_per_session_uses_first_start_and_snapshot(self):
        first = self.choice('meaning', 1, session='same')
        first['status'] = 'cancelled'
        later = self.choice('mastery', 2, session='same')
        later['content_snapshot']['primary_dimension'] = 'relaxation'
        preferences = dimension_preferences([later, first, self.choice('meaning', 3)])
        self.assertEqual(preferences, {'meaning': 2 / 8})

    def test_need_and_history_never_override_hard_filters(self):
        preferred = next(a for a in self.candidates if a['id'] == 'mastery')
        preferred['content']['required_items'] = ['phone']
        context = {**self.context, 'need_now': 'learn', 'desired_outcome': 'unwind'}
        history = [self.choice('mastery', i) for i in range(10)]
        self.assertEqual(self.first(context, history), 'relaxation')
        preferred['content']['required_items'] = []
        preferred['active'] = False
        self.assertEqual(self.first(context, history), 'relaxation')

    def test_long_session_prioritizes_a_good_time_fit_over_short_familiar_games(self):
        by_dimension = {a['id']: a for a in self.candidates}
        game = by_dimension['mastery']
        walk = by_dimension['detachment']
        walk['content'].update(active_minutes=90, tags=['walking', 'nature'])
        too_long = by_dimension['meaning']
        too_long['content'].update(active_minutes=115, travel_minutes=10)
        context = {**self.context, 'available_minutes': 120, 'activity_intent': 'learn'}
        history = [self.choice('mastery', i) for i in range(10)]
        self.assertEqual(self.first(context, history, [game, walk, too_long]), 'detachment')
        self.assertEqual(self.first(context, history, [game, too_long]), 'mastery')

    def test_replacement_prefers_an_unseen_kind_of_activity_at_the_same_time_fit(self):
        first, second, different = self.candidates[:3]
        for activity in (first, second, different):
            activity['content']['active_minutes'] = 90
        different['content']['tags'] = ['music', 'listening']
        history = [self.choice(second['id'], i) for i in range(10)]
        result = rank([first, second, different], {**self.context, 'available_minutes': 120},
            NOW, {first['id']}, 'fixed-seed', history, [], [], seen=[first])
        self.assertEqual(result[0]['activity']['id'], different['id'])

    def test_four_hour_slot_prefers_full_length_over_matching_interest_and_short_swap(self):
        full, near, short, too_long = self.candidates[:4]
        for row, duration, tags in ((full, 240, ['dance']), (near, 225, ['dance']),
                                    (short, 105, ['games']), (too_long, 241, ['games'])):
            row['content'].update(active_minutes=duration, tags=tags)
        context = {**self.context, 'available_minutes': 240, 'liked_tags': ['games']}
        result = rank(self.candidates, context, NOW, set(), 'fixed', [], [], [])
        self.assertEqual(result[0]['activity']['id'], full['id'])
        result = rank(self.candidates, context, NOW, {full['id']}, 'fixed', [], [], [], seen=[full])
        self.assertEqual(result[0]['activity']['id'], near['id'])

    def test_budget_target_uses_current_group_price_and_does_not_exceed_it(self):
        expensive, closest, cheaper, stale, free = self.candidates[:5]
        for row, low, high in ((expensive, 200, 260), (closest, 235, 245), (cheaper, 60, 100), (stale, 248, 250)):
            row['content']['cost'] = {'kind':'estimated', 'min_toman':low, 'max_toman':high,
                'basis':'per_person', 'verified_at':NOW - timedelta(days=1), 'valid_until':NOW + timedelta(days=1)}
        stale['content']['cost']['valid_until'] = NOW
        context = {**self.context, 'social_mode':'together', 'party_size':2,
                   'budget':{'mode':'cap', 'cap_toman':500}}
        result = rank([free, stale, expensive, cheaper, closest], context, NOW, set(), 'fixed', [], [], [], count=5)
        self.assertEqual([item['activity']['id'] for item in result], [closest['id'], cheaper['id'], free['id']])

    def test_longer_alternative_only_relaxes_setting(self):
        at_home, public = self.candidates[:2]
        at_home['content'].update(active_minutes=120)
        public['content'].update(title='برنامهٔ چهار ساعته', venue='indoor_public', active_minutes=240)
        context = {**self.context, 'available_minutes':240}
        self.assertEqual(planning_alternatives(context, [at_home, public], NOW, set())['venue_alternative'],
                         {'title':'برنامهٔ چهار ساعته','venue':'indoor_public','total_minutes':240})
        public['content']['required_items'] = ['camera']
        self.assertIsNone(planning_alternatives(context, [at_home, public], NOW, set())['venue_alternative'])
        public['content']['required_items'] = []
        public['content']['requires_venue_check'] = True
        self.assertIsNone(planning_alternatives(context, [at_home, public], NOW, set())['venue_alternative'])

    def test_mental_game_is_fallback_unless_user_likes_it(self):
        game, movement, music = self.candidates[:3]
        movement['content']['tags'] = ['dance', 'movement']
        music['content']['tags'] = ['music']
        asked_for_game_dimension = next(goal for goal, d in GOALS.items() if d == game['id'])
        context = {**self.context, 'activity_intent': asked_for_game_dimension}
        self.assertEqual(self.first(context, candidates=[game, movement]), movement['id'])
        self.assertEqual(self.first(context, candidates=[game]), game['id'])
        self.assertEqual(self.first({**context, 'liked_tags': ['games']},
                                    candidates=[game, movement]), game['id'])
        move_goal = next(goal for goal, d in GOALS.items() if d == movement['id'])
        result = rank([game, movement, music], {**context, 'activity_intent': move_goal},
                      NOW, set(), 'fixed', [], [], [], seen=[movement])
        self.assertEqual(result[0]['activity']['id'], music['id'])


if __name__ == '__main__':
    unittest.main()
