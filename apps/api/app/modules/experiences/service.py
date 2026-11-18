from datetime import timedelta
from zoneinfo import ZoneInfo
from app.core.errors import DomainError, conflict, missing
from app.core.schemas import merge_constraints
from app.core.values import uid, replace, owned
from app.modules.recommendations.eligibility import eligible

BADGES = [('first_step', 1), ('five_moments', 5), ('ten_moments', 10)]


class Experiences:
    def __init__(self, store, catalog, recommendations, identity, clock):
        self.store, self.catalog, self.recommendations, self.identity, self.clock = store, catalog, recommendations, identity, clock

    def _active(self, user_id):
        for e in self.store.list('experiences'):
            if e['user_id'] == user_id and e['status'] == 'active':
                if e['started_at'] + timedelta(hours=24) <= self.clock():
                    e['status'] = 'expired'
                    replace(self.store, 'experiences', e)
                else:
                    return e
        return None

    def present(self, e):
        result = {k: v for k, v in e.items() if k not in ('version', 'user_id', 'context_snapshot', 'award_result')}
        activity = self.catalog.activity(e['activity_id'])
        revision = self.catalog.revision(e['revision_id'])
        result['unavailable'] = not activity['active'] or revision['state'] == 'archived'
        if result['unavailable']:
            result.pop('content_snapshot', None)
        return result

    def active(self, user_id):
        with self.store.atomic():
            e = self._active(user_id)
            return {'experience': self.present(e) if e else None}

    def start(self, user_id, data):
        with self.store.atomic():
            user = self.identity.user(user_id)
            session = self.recommendations.load(user_id, data.recommendation_session_id)
            slot = next((s for s in session['items'] if s['slot_id'] == data.slot_id), None)
            if not slot or slot['revision_id'] != data.revision_id:
                conflict('این پیشنهاد عوض شده؛پیشنهاد تازه رو ببین.')
            activity = self.catalog.activity(slot['activity_id'])
            revision = self.catalog.revision(slot['revision_id'])
            if not activity['active'] or revision['state'] == 'archived':
                raise DomainError('CONTENT_WITHDRAWN', 'این پیشنهاد فعلاً در دسترس نیست.', 410)
            if activity['published_revision_id'] != data.revision_id:
                conflict('نسخهٔ تازه‌ای آماده شده؛دوباره پیشنهاد بگیر.')
            context = merge_constraints(session['context_snapshot'], self.identity.preferences(user_id)['preferences'])
            parsed = self.catalog.checked_content(revision.get('content'), activity['primary_dimension'])
            execution = (eligible(context, dict(id=activity['id'], active=True, state=revision['state'],
                         revision_id=revision['id'], published_revision_id=activity['published_revision_id'],
                         content=parsed.model_dump()), self.clock())
                         if parsed is not None and revision['activity_id'] == activity['id'] else None)
            if not execution:
                raise DomainError('INVALID_STATE', 'این پیشنهاد با شرایط الانت جور نیست؛یه پیشنهاد تازه بگیر.')
            active = self._active(user_id)
            if active:
                raise DomainError('ACTIVE_EXPERIENCE', 'یه تجربهٔ باز داری؛اول همون رو ببند.', fields={'experience_id': active['id']})
            # Shared synchronous lock serializes start with replace, publish, withdrawal and another start.
            activity['start_guard_version'] += 1
            replace(self.store, 'activities', activity)
            replace(self.store, 'recommendation_sessions', session)
            experience = self.store.insert('experiences', dict(id=uid(), user_id=user_id, activity_id=activity['id'],
                revision_id=revision['id'], recommendation_session_id=session['id'], slot_id=slot['slot_id'],
                content_snapshot=revision['content'], context_snapshot=context, primary_dimension_snapshot=revision['content']['primary_dimension'],
                execution_social_mode=execution[0], execution_people=execution[1], timezone_at_start=user['timezone'],
                status='active', started_at=self.clock(), completed_at=None, award_result=None))
            return self.present(experience)

    def get(self, user_id, experience_id):
        with self.store.atomic():
            self._active(user_id)
            return self.present(owned(self.store, 'experiences', experience_id, user_id))

    def history(self, user_id):
        with self.store.atomic():
            self._active(user_id)
            return sorted([self.present(e) for e in self.store.list('experiences') if e['user_id'] == user_id],
                          key=lambda e: (e['started_at'], e['id']), reverse=True)

    def journey(self, user_id):
        p = self.store.get('user_progress', user_id)
        return {k: p[k] for k in ('total_points', 'rewarded_completions', 'completed_dimensions', 'badges')} if p else dict(
            total_points=0, rewarded_completions=0, completed_dimensions=[], badges=[])

    def _award(self, e):
        now, user_id = self.clock(), e['user_id']
        local_date = now.astimezone(ZoneInfo(e['timezone_at_start'])).date().isoformat()
        # Recompute today's dates in the timezone frozen for this experience, not a mutable user profile.
        ledger = [r for r in self.store.list('reward_ledger') if r['user_id'] == user_id and r['points'] > 0]
        daily = [r for r in ledger if r['created_at'].astimezone(ZoneInfo(e['timezone_at_start'])).date().isoformat() == local_date]
        rolling = [r for r in ledger if r['created_at'] > now - timedelta(hours=24)]
        recent = [r for r in ledger if r['activity_id'] == e['activity_id'] and r['created_at'] > now - timedelta(days=7)]
        reason = 'DAILY_CAP' if len(daily) >= 3 else 'ROLLING_CAP' if sum(r['points'] for r in rolling) >= 30 else 'RECENT_ACTIVITY' if recent else 'AWARDED'
        points = 10 if reason == 'AWARDED' else 0
        self.store.insert('reward_ledger', dict(id=e['id'], experience_id=e['id'], user_id=user_id,
            activity_id=e['activity_id'], primary_dimension_snapshot=e['primary_dimension_snapshot'], points=points,
            reason=reason, award_date=local_date, rules_version='rewards_v1', created_at=now))
        progress = self.store.get('user_progress', user_id)
        if not progress:
            progress = self.store.insert('user_progress', dict(id=user_id, user_id=user_id, total_points=0,
                rewarded_completions=0, completed_dimensions=[], badges=[]))
        new_badges = []
        if points:
            progress['total_points'] += points
            progress['rewarded_completions'] += 1
            progress['completed_dimensions'] = sorted(set(progress['completed_dimensions']) | {e['primary_dimension_snapshot']})
            candidates = [key for key, threshold in BADGES if progress['rewarded_completions'] >= threshold]
            if len(progress['completed_dimensions']) >= 3:
                candidates.append('curious_three')
            if len(progress['completed_dimensions']) == 6:
                candidates.append('all_six')
            new_badges = [key for key in candidates if key not in progress['badges']]
            progress['badges'] += new_badges
            for key in new_badges:
                self.store.insert('user_badges', dict(id=uid(), user_id=user_id, badge_key=key,
                    earned_at=now, source_experience_id=e['id']))
            replace(self.store, 'user_progress', progress)
        e['completion_local_date'] = local_date
        return dict(points=points, total_points=progress['total_points'], new_badges=new_badges, reason=reason)

    def complete(self, user_id, experience_id):
        with self.store.atomic():
            self.identity.user(user_id)
            e = owned(self.store, 'experiences', experience_id, user_id)
            if e['status'] == 'completed':
                return {'experience': self.present(e), 'award': e['award_result']}
            if e['status'] != 'active' or e['started_at'] + timedelta(hours=24) <= self.clock():
                raise DomainError('INVALID_STATE', 'این تجربه دیگه برای پایان‌دادن باز نیست.')
            award = self._award(e)
            e.update(status='completed', completed_at=self.clock(), award_result=award)
            replace(self.store, 'experiences', e)
            return {'experience': self.present(e), 'award': award}

    def cancel(self, user_id, experience_id):
        with self.store.atomic():
            self.identity.user(user_id)
            e = owned(self.store, 'experiences', experience_id, user_id)
            if e['status'] == 'completed':
                raise DomainError('INVALID_STATE', 'این تجربه قبلاً تموم شده.')
            if e['status'] == 'active':
                e['status'] = 'cancelled' if e['started_at'] + timedelta(hours=24) > self.clock() else 'expired'
                replace(self.store, 'experiences', e)
            return self.present(e)

    def feedback(self, user_id, experience_id, data):
        with self.store.atomic():
            self.identity.user(user_id)
            e = owned(self.store, 'experiences', experience_id, user_id)
            if e['status'] != 'completed':
                raise DomainError('INVALID_STATE', 'بازخورد بعد از پایان تجربه ثبت می‌شه.')
            feedback = self.store.get('feedback', experience_id)
            value = dict(id=experience_id, experience_id=experience_id, user_id=user_id,
                         **data.model_dump(), updated_at=self.clock())
            if feedback:
                value['version'] = feedback['version']
                value = replace(self.store, 'feedback', value)
            else:
                value = self.store.insert('feedback', value)
            return {k: v for k, v in value.items() if k not in ('user_id', 'version')}

    def delete_feedback(self, user_id, experience_id):
        with self.store.atomic():
            owned(self.store, 'experiences', experience_id, user_id)
            self.store.delete('feedback', experience_id)

    def save(self, user_id, activity_id):
        with self.store.atomic():
            self.identity.user(user_id)
            activity = self.catalog.activity(activity_id)
            self.catalog.visible_revision(activity.get('published_revision_id') or '')
            key = user_id + ':' + activity_id
            if not self.store.get('saved_activities', key):
                self.store.insert('saved_activities', dict(id=key, user_id=user_id, activity_id=activity_id, created_at=self.clock()))

    def unsave(self, user_id, activity_id):
        with self.store.atomic():
            self.store.delete('saved_activities', user_id + ':' + activity_id)

    def saved(self, user_id):
        result = []
        for s in sorted(self.store.list('saved_activities'), key=lambda s: s['created_at'], reverse=True):
            if s['user_id'] != user_id:
                continue
            activity = self.catalog.activity(s['activity_id'])
            if not activity['active'] or not activity['published_revision_id']:
                result.append({'activity_id': activity['id'], 'unavailable': True})
            else:
                result.append({'activity_id': activity['id'], 'unavailable': False,
                    'revision_id': activity['published_revision_id'], 'content': self.catalog.visible_revision(activity['published_revision_id'])['content']})
        return result
