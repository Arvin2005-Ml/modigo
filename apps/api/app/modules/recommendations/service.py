from datetime import timedelta
from app.core.errors import DomainError, conflict, missing
from app.core.schemas import Context, merge_constraints
from app.core.values import uid, replace, owned
from app.modules.recommendations.ranking import rank, GOALS, ALGORITHM_VERSION
from app.modules.recommendations.eligibility import eligible, total_minutes, verified_cost

REPLACEMENT_LIMIT = 6
VENUE_CHECK_MESSAGE = 'پیش از رفتن، باز بودن، هزینه، رزرو و شرایط دسترسی را از محل بررسی کن.'


def cost_label(cost, estimate):
    if cost['kind'] == 'free':
        return 'رایگان'
    if estimate is None:
        return 'هزینهٔ نامعلوم'
    low, high = (f'{amount:,}'.translate(str.maketrans('0123456789,', '۰۱۲۳۴۵۶۷۸۹٬')) for amount in estimate)
    return f'برآورد کل: {low}' + (f' تا {high}' if low != high else '') + ' تومان'


def planning_alternatives(context, candidates, now, blocked):
    """Find previews that each change just one choice and cannot start a slot."""
    available = context['available_minutes']
    wider = ({**context, 'venue': 'any'} if available >= 60 and context['venue'] != 'any' else None)
    flexible = ({**context, 'budget': {'mode': 'flexible'}} if context['budget']['mode'] == 'cap' else None)
    best, paid, different_venue, different_budget = 0, False, None, None
    for activity in candidates:
        content = activity['content']
        minutes = total_minutes(content)
        execution = eligible(context, activity, now, blocked)
        if execution:
            best = max(best, minutes)
            paid = paid or content['cost']['kind'] == 'estimated'
        elif (wider and minutes * 4 >= available * 3
                and eligible(wider, activity, now, blocked)
                and (different_venue is None or minutes > different_venue['total_minutes'])):
            different_venue = {'title': content['title'], 'venue': content['venue'], 'total_minutes': minutes}
        if (not execution and flexible and not paid and content.get('place')
                and (available < 60 or minutes * 4 >= available * 3)
                and (different_budget is None or minutes > different_budget['total_minutes'])):
            with_flexible = eligible(flexible, activity, now, blocked)
            if with_flexible and verified_cost(content['cost'], with_flexible[1], now) is None:
                different_budget = {'title': content['title'], 'total_minutes': minutes}
    if different_venue and (different_venue['total_minutes'] - best) * 10 < available:
        different_venue = None
    return {'venue_alternative': different_venue, 'budget_alternative': None if paid else different_budget}


class Recommendations:
    def __init__(self, store, catalog, identity, clock):
        self.store, self.catalog, self.identity, self.clock = store, catalog, identity, clock

    def check_in(self, user_id, data):
        with self.store.atomic():
            self.identity.user(user_id)
            preferences = self.identity.preferences(user_id)['preferences']
            context = merge_constraints(data.model_dump(), preferences, data.model_fields_set)
            record = self.store.insert('check_ins', dict(id=uid(), user_id=user_id, context=context,
                context_input=data.model_dump(exclude_unset=True),
                created_slate_count=0, recommendation_session_id=None, shown_activity_ids=[],
                created_at=self.clock(), expires_at=self.clock() + timedelta(days=90)))
            return {k: record[k] for k in ('id', 'context', 'created_at')}

    def _effective_context(self, user_id, check_in, snapshot):
        preferences = self.identity.preferences(user_id)['preferences']
        if 'context_input' in check_in:
            data = Context.model_validate(check_in['context_input'])
            return merge_constraints(data.model_dump(), preferences, data.model_fields_set)
        # Old rows cannot tell an explicit per-turn choice from an inherited
        # setting. Keep existing restrictions; don't grant removed items/contact.
        context = merge_constraints(snapshot, preferences)
        context['owned_items'] = sorted(set(context['owned_items']) & set(preferences['owned_items']))
        context['allow_async_contact'] = context['allow_async_contact'] and preferences['allow_async_contact']
        return context

    def session_context(self, session, check_in=None):
        if check_in is None:
            check_in = owned(self.store, 'check_ins', session['check_in_id'], session['user_id'])
        return self._effective_context(session['user_id'], check_in, session['context_snapshot'])

    def _rank(self, user_id, context, excluded, seed, candidates=None, seen=()):
        history = [e for e in self.store.list('experiences') if e['user_id'] == user_id]
        now = self.clock()
        active = {e['activity_id'] for e in history
                  if e['status'] == 'active' and e['started_at'] + timedelta(hours=24) > now}
        return rank(self.catalog.candidates() if candidates is None else candidates,
            context, now, set(excluded) | active, seed,
            history,
            [f for f in self.store.list('feedback') if f['user_id'] == user_id],
            [s for s in self.store.list('recommendation_sessions') if s['user_id'] == user_id],
            seen=seen)

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
            context = self._effective_context(user_id, check_in, check_in['context'])
            seed = uid()
            candidates = self.catalog.candidates()
            ranked = self._rank(user_id, context, check_in['shown_activity_ids'], seed, candidates)
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
            return self.present(session, candidates, check_in=check_in, context=context)

    def load(self, user_id, session_id):
        session = owned(self.store, 'recommendation_sessions', session_id, user_id)
        if session['expires_at'] <= self.clock():
            raise DomainError('SESSION_EXPIRED', 'این پیشنهادها قدیمی شدن؛شرایط الانت رو دوباره بگو.', 410)
        return session

    def card_execution(self, activity, revision, context):
        if revision['activity_id'] != activity['id']:
            return None, None
        parsed = self.catalog.checked_content(revision.get('content'), activity['primary_dimension'])
        if parsed is None:
            return None, None
        content = parsed.model_dump()
        execution = eligible(context, {**activity, 'state': revision['state'],
            'revision_id': revision['id'], 'content': content}, self.clock())
        return content, execution

    def present_item(self, item, context):
        unavailable = dict(slot_id=item['slot_id'], unavailable=True)
        if not item.get('revision_id') or not item.get('activity_id'):
            return unavailable
        revision = self.catalog.revision(item['revision_id'])
        activity = self.catalog.activity(item['activity_id'])
        c, execution = self.card_execution(activity, revision, context)
        if not execution:
            return unavailable
        estimate = verified_cost(c['cost'], execution[1], self.clock())
        return {**{k: v for k, v in item.items() if k != 'score_internal'},
            'title': c['title'], 'teaser': c['teaser'],
            'execution_social_mode': execution[0], 'execution_people': execution[1],
            'total_minutes': total_minutes(c),
            'cost_label': cost_label(c['cost'], estimate), 'unavailable': False,
            'cost_range_toman': None if estimate is None else {'min': estimate[0], 'max': estimate[1]},
            'requires_venue_check': c['requires_venue_check'], 'place': c['place'],
            'venue_check_message': VENUE_CHECK_MESSAGE if c['requires_venue_check'] else None}

    def present(self, session, candidates=None, *, check_in=None, context=None):
        if check_in is None:
            check_in = owned(self.store, 'check_ins', session['check_in_id'], session['user_id'])
        if context is None:
            context = self.session_context(session, check_in)
        items = [self.present_item(item, context) for item in session['items']]
        n = sum(not i.get('unavailable') for i in items)
        now = self.clock()
        alternatives = {'venue_alternative': None, 'budget_alternative': None}
        if ((context['available_minutes'] >= 60 and context['venue'] != 'any')
                or context['budget']['mode'] == 'cap'):
            if candidates is None:
                candidates = self.catalog.candidates()
            active = {e['activity_id'] for e in self.store.list('experiences')
                      if e['user_id'] == session['user_id'] and e['status'] == 'active'
                      and e['started_at'] + timedelta(hours=24) > now}
            alternatives = planning_alternatives(context, candidates, now, active)
        return dict(id=session['id'], check_in_id=session['check_in_id'], version=session['version'],
            expires_at=session['expires_at'],
            context_summary={**{k: context[k] for k in ('available_minutes','social_mode','party_size','venue','budget')},
                'city': context.get('city'), 'allow_venue_planning': context.get('allow_venue_planning', False)},
            items=items, result_count=n, partial=n == 0,
            empty_reason=None if n else 'NO_MATCHES',
            **alternatives,
            **self.replacement_state(session, check_in, context, candidates))

    def replacement_state(self, session, check_in, context, candidates=None):
        remaining = max(0, session['replacement_limit'] - session['replacement_count'])
        available = False
        if remaining and session['items'] and session['suggestion_index'] == len(session['suggestion_history']) - 1:
            excluded = set(check_in['shown_activity_ids']) | {
                e['activity_id'] for e in self.store.list('experiences')
                if e['user_id'] == session['user_id'] and e['status'] == 'active'
                and e['started_at'] + timedelta(hours=24) > self.clock()}
            now = self.clock()
            available = any(eligible(context, a, now, excluded)
                            for a in (self.catalog.candidates() if candidates is None else candidates))
        return dict(replacement_count=session['replacement_count'],
            replacement_limit=session['replacement_limit'], replacements_remaining=remaining,
            replacement_available=available, suggestion_index=session['suggestion_index'],
            suggestion_count=len(session['suggestion_history']))

    def replay(self, user_id, session_id, receipt):
        session = self.load(user_id, session_id)
        check_in = owned(self.store, 'check_ins', session['check_in_id'], user_id)
        context = self.session_context(session, check_in)
        replacement_receipt = 'session_version' in receipt
        version = receipt['session_version' if replacement_receipt else 'version']
        if version == session['version']:
            if replacement_receipt:
                return {**receipt, 'item': self.present_item(session['items'][0], context),
                        **self.replacement_state(session, check_in, context)}
            return self.present(session, check_in=check_in, context=context)
        # Keep the outcome/version of the original action. An older receipt
        # cannot authorize a new mutation or expose a card invalidated since.
        if replacement_receipt:
            return {**receipt, 'item': self.present_item(receipt['item'], context),
                    'replacement_available': False}
        items = [self.present_item(item, context) for item in receipt['items']]
        n = sum(not item['unavailable'] for item in items)
        return {**receipt, 'items': items, 'result_count': n, 'partial': n == 0,
                'venue_alternative': None, 'budget_alternative': None,
                'empty_reason': None if n else 'NO_MATCHES', 'replacement_available': False}

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
            context = self.session_context(session, check_in)
            candidates = self.catalog.candidates()
            excluded = set(check_in['shown_activity_ids'])
            seen = [a for a in candidates if a['id'] in excluded]
            ranked = self._rank(user_id, context, excluded, session['seed'], candidates, seen)
            if not ranked:
                return dict(session_version=session['version'], item=self.present_item(item, context),
                    replaced=False, **self.replacement_state(session, check_in, context, candidates))
            new_item = self._slot(ranked[0], item['rank'], context, slot_id)
            session['items'] = [new_item if s['slot_id'] == slot_id else s for s in session['items']]
            session['suggestion_history'].append(new_item)
            session['suggestion_index'] = len(session['suggestion_history']) - 1
            session['shown_activity_ids'] = sorted(set(session['shown_activity_ids']) | {new_item['activity_id']})
            session['replacement_count'] += 1
            session = replace(self.store, 'recommendation_sessions', session)
            check_in['shown_activity_ids'] = sorted(set(check_in['shown_activity_ids']) | {new_item['activity_id']})
            replace(self.store, 'check_ins', check_in)
            return dict(session_version=session['version'], item=self.present_item(new_item, context),
                replaced=True, **self.replacement_state(session, check_in, context, candidates))
