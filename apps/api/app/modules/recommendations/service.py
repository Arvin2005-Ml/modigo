from datetime import timedelta
from app.core.errors import DomainError, conflict, missing
from app.core.schemas import merge_constraints
from app.core.values import uid, replace, owned
from app.modules.recommendations.ranking import rank, GOALS, ALGORITHM_VERSION
from app.modules.recommendations.eligibility import eligible

REPLACEMENT_LIMIT = 6


class Recommendations:
    def __init__(self, store, catalog, identity, clock):
        self.store, self.catalog, self.identity, self.clock = store, catalog, identity, clock

    def check_in(self, user_id, data):
        with self.store.atomic():
            self.identity.user(user_id)
            preferences = self.identity.preferences(user_id)['preferences']
            context = merge_constraints(data.model_dump(), preferences, data.model_fields_set)
            record = self.store.insert('check_ins', dict(id=uid(), user_id=user_id, context=context,
                created_slate_count=0, recommendation_session_id=None, shown_activity_ids=[],
                created_at=self.clock(), expires_at=self.clock() + timedelta(days=90)))
            return {k: record[k] for k in ('id', 'context', 'created_at')}

    def _rank(self, user_id, context, excluded, seed, count=1, selected=None):
        history = [e for e in self.store.list('experiences') if e['user_id'] == user_id]
        active = {e['activity_id'] for e in history
                  if e['status'] == 'active' and e['started_at'] + timedelta(hours=24) > self.clock()}
        return rank(self.catalog.candidates(), context, self.clock(), set(excluded) | active, seed,
            history,
            [f for f in self.store.list('feedback') if f['user_id'] == user_id],
            [s for s in self.store.list('recommendation_sessions') if s['user_id'] == user_id], count, selected)

    def _slot(self, item, index, context, slot_id=None):
        activity = item['activity']
        content = activity['content']
        if item['need_fit'] > 0:
            explanation = 'با چیزی که الان از این وقت می‌خوای جور درمیاد.'
        elif item['dimension_preference'] > 0:
            explanation = 'از جنس تفریح‌هاییه که قبلاً انتخاب کردی.'
        elif set(content['tags']) & set(context['liked_tags']):
            explanation = 'از جنس علاقه‌هایی‌ه که انتخاب کردی.'
        elif GOALS.get(context['goal']) == content['primary_dimension']:
            explanation = {
                'unwind': 'یه انتخاب آروم برای مکثی که می‌خوای.',
                'switch_off': 'یه سرگرمی برای فاصله‌گرفتن از روزمرگی.',
                'learn': 'یه چالش کوچیک برای کشف یه چیز تازه.',
                'connect': 'یه انتخاب برای وقت مشترک با همراه‌هات.',
                'meaning': 'یه تجربه برای ساختن چیزی با سلیقهٔ خودت.',
                'choose': 'یه انتخاب که مسیرش رو خودت می‌سازی.',
            }[context['goal']]
        elif content['energy_required'] == 'low' and context['energy'] == 'low':
            explanation = 'با وقتت جور درمیاد و انرژی زیادی نمی‌خواد.'
        elif not content['required_items'] and content['cost']['kind'] == 'free':
            explanation = 'بدون خرید و وسیلهٔ خاص می‌تونی امتحانش کنی.'
        else:
            explanation = 'با وقت و شرایطی که گفتی جور درمیاد.'
        return dict(slot_id=slot_id or uid(), activity_id=activity['id'], revision_id=activity['revision_id'], rank=index,
            execution_social_mode=item['execution'][0], execution_people=item['execution'][1],
            explanation=explanation, score_internal=item['score'])

    def create(self, user_id, check_in_id):
        with self.store.atomic():
            self.identity.user(user_id)
            check_in = owned(self.store, 'check_ins', check_in_id, user_id)
            if check_in['expires_at'] <= self.clock():
                raise DomainError('SESSION_EXPIRED', 'برای شرایط الانت یه پیشنهاد تازه بگیر.', 410)
            if check_in['recommendation_session_id']:
                return self.present(self.load(user_id, check_in['recommendation_session_id']))
            preferences = self.identity.preferences(user_id)['preferences']
            context = merge_constraints(check_in['context'], preferences)
            seed = uid()
            ranked = self._rank(user_id, context, check_in['shown_activity_ids'], seed)
            items = [self._slot(item, i, context) for i, item in enumerate(ranked, 1)]
            ids = [item['activity_id'] for item in items]
            session = self.store.insert('recommendation_sessions', dict(id=uid(), user_id=user_id,
                check_in_id=check_in_id, context_snapshot=context, items=items, shown_activity_ids=ids,
                suggestion_history=items.copy(), suggestion_index=0,
                seed=seed, algorithm_version=ALGORITHM_VERSION, replacement_count=0,
                replacement_limit=REPLACEMENT_LIMIT,
                created_at=self.clock(), expires_at=self.clock() + timedelta(hours=24),
                purge_at=self.clock() + timedelta(days=90)))
            check_in['shown_activity_ids'] = sorted(set(check_in['shown_activity_ids']) | set(ids))
            check_in['created_slate_count'] += 1
            check_in['recommendation_session_id'] = session['id']
            replace(self.store, 'check_ins', check_in)
            return self.present(session)

    def load(self, user_id, session_id):
        session = owned(self.store, 'recommendation_sessions', session_id, user_id)
        if session['expires_at'] <= self.clock():
            raise DomainError('SESSION_EXPIRED', 'این پیشنهادها قدیمی شدن؛شرایط الانت رو دوباره بگو.', 410)
        return session

    def present_item(self, item):
        revision = self.catalog.revision(item['revision_id'])
        activity = self.catalog.activity(item['activity_id'])
        if not activity['active'] or revision['state'] not in ('published', 'superseded'):
            return dict(slot_id=item['slot_id'], unavailable=True)
        c = revision['content']
        return {**{k: v for k, v in item.items() if k != 'score_internal'},
            'title': c['title'], 'teaser': c['teaser'],
            'total_minutes': sum(c[k] for k in ('active_minutes', 'setup_minutes', 'travel_minutes')),
            'cost_label': 'رایگان' if c['cost']['kind'] == 'free' else 'هزینهٔ متغیر', 'unavailable': False}

    def present(self, session):
        items = [self.present_item(item) for item in session['items']]
        n = sum(not i.get('unavailable') for i in items)
        return dict(id=session['id'], check_in_id=session['check_in_id'], version=session['version'],
            expires_at=session['expires_at'],
            context_summary={k: session['context_snapshot'][k] for k in ('available_minutes','social_mode','party_size','venue','budget')},
            items=items, result_count=n, partial=n == 0,
            empty_reason=None if n else 'NO_MATCHES', **self.replacement_state(session))

    def replacement_state(self, session):
        remaining = max(0, session['replacement_limit'] - session['replacement_count'])
        available = False
        if remaining and session['items'] and session['suggestion_index'] == len(session['suggestion_history']) - 1:
            check_in = owned(self.store, 'check_ins', session['check_in_id'], session['user_id'])
            context = merge_constraints(session['context_snapshot'],
                self.identity.preferences(session['user_id'])['preferences'])
            excluded = set(check_in['shown_activity_ids']) | {
                e['activity_id'] for e in self.store.list('experiences')
                if e['user_id'] == session['user_id'] and e['status'] == 'active'
                and e['started_at'] + timedelta(hours=24) > self.clock()}
            available = any(eligible(context, a, self.clock(), excluded)
                            for a in self.catalog.candidates())
        return dict(replacement_count=session['replacement_count'],
            replacement_limit=session['replacement_limit'], replacements_remaining=remaining,
            replacement_available=available, suggestion_index=session['suggestion_index'],
            suggestion_count=len(session['suggestion_history']))

    def get(self, user_id, session_id):
        with self.store.atomic():
            return self.present(self.load(user_id, session_id))

    def navigate(self, user_id, session_id, direction, expected):
        with self.store.atomic():
            self.identity.user(user_id)
            session = self.load(user_id, session_id)
            if session['version'] != expected:
                conflict()
            if direction not in ('previous', 'next'):
                raise DomainError('INVALID_DIRECTION', 'جهت جابه‌جایی معتبر نیست.', 422)
            index = session['suggestion_index'] + (-1 if direction == 'previous' else 1)
            if not 0 <= index < len(session['suggestion_history']):
                raise DomainError('HISTORY_BOUNDARY', 'در این جهت پیشنهاد دیده‌شده‌ای نداریم.')
            session['suggestion_index'] = index
            session['items'] = [session['suggestion_history'][index]]
            session = replace(self.store, 'recommendation_sessions', session)
            return self.present(session)

    def replace_slot(self, user_id, session_id, slot_id, expected):
        with self.store.atomic():
            self.identity.user(user_id)
            session = self.load(user_id, session_id)
            if session['version'] != expected:
                conflict()
            item = next((s for s in session['items'] if s['slot_id'] == slot_id), None)
            if not item:
                missing()
            if session['suggestion_index'] != len(session['suggestion_history']) - 1:
                raise DomainError('HISTORY_NOT_AT_END', 'اول پیشنهادهای دیده‌شدهٔ بعدی رو مرور کن.')
            if session['replacement_count'] >= session['replacement_limit']:
                raise DomainError('REPLACEMENT_LIMIT',
                    'شش بار پیشنهاد رو عوض کردی؛ می‌تونی پیشنهادهای قبلی رو ببینی یا شرایط تازه‌ای بگی.')
            check_in = owned(self.store, 'check_ins', session['check_in_id'], user_id)
            context = merge_constraints(session['context_snapshot'], self.identity.preferences(user_id)['preferences'])
            candidate_map = {a['id']: a for a in self.catalog.candidates()}
            others = [candidate_map[s['activity_id']] for s in session['items']
                      if s['slot_id'] != slot_id and s['activity_id'] in candidate_map]
            ranked = self._rank(user_id, context, check_in['shown_activity_ids'], session['seed'], 1, others)
            if not ranked:
                return dict(session_version=session['version'], item=self.present_item(item),
                    replaced=False, **self.replacement_state(session))
            new_item = self._slot(ranked[0], item['rank'], context, slot_id)
            session['items'] = [new_item if s['slot_id'] == slot_id else s for s in session['items']]
            session['suggestion_history'].append(new_item)
            session['suggestion_index'] = len(session['suggestion_history']) - 1
            session['shown_activity_ids'] = sorted(set(session['shown_activity_ids']) | {new_item['activity_id']})
            session['replacement_count'] += 1
            session = replace(self.store, 'recommendation_sessions', session)
            check_in['shown_activity_ids'] = sorted(set(check_in['shown_activity_ids']) | {new_item['activity_id']})
            replace(self.store, 'check_ins', check_in)
            return dict(session_version=session['version'], item=self.present_item(new_item),
                replaced=True, **self.replacement_state(session))
