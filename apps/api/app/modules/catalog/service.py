from pydantic import ValidationError
from app.core.errors import DomainError, conflict, missing
from app.core.schemas import city_key
from app.core.values import uid, replace
from app.modules.catalog.schemas import Content


class Catalog:
    def __init__(self, store, clock):
        self.store, self.clock = store, clock

    def authorize(self, actor, admin=False):
        current = self.store.get('users', actor['id'])
        roles = ('admin',) if admin else ('admin', 'editor')
        if not current or current['status'] != 'active' or current['role'] not in roles:
            raise DomainError('FORBIDDEN', 'دسترسی این بخش رو نداری.', 403)

    def audit(self, actor_id, action, target_id, reason=None):
        self.store.insert('admin_audit', dict(id=uid(), actor_id=actor_id, action=action,
            target_id=target_id, reason=reason, created_at=self.clock()))

    def activity(self, activity_id):
        activity = self.store.get('activities', activity_id)
        if not activity:
            missing()
        return activity

    def revision(self, revision_id):
        revision = self.store.get('activity_revisions', revision_id)
        if not revision:
            missing()
        return revision

    def visible_revision(self, revision_id):
        revision = self.revision(revision_id)
        if revision['state'] not in ('published', 'superseded', 'archived'):
            missing()
        activity = self.activity(revision['activity_id'])
        if not activity['active'] or revision['state'] == 'archived':
            raise DomainError('CONTENT_WITHDRAWN', 'این پیشنهاد فعلاً در دسترس نیست.', 410)
        content = revision.get('content')
        if not isinstance(content, dict):
            raise DomainError('CONTENT_WITHDRAWN', 'این پیشنهاد فعلاً در دسترس نیست.', 410)
        # Historical content may predate the new schema. Only surface verified
        # source metadata when it passes the current contract.
        if content.get('place') or content.get('requires_venue_check'):
            parsed = self.checked_content(content, activity['primary_dimension'])
            if parsed is None:
                raise DomainError('CONTENT_WITHDRAWN', 'این پیشنهاد فعلاً در دسترس نیست.', 410)
            content = parsed.model_dump()
        return dict(id=revision['id'], activity_id=activity['id'], content=content, origin=revision['origin'])

    def candidates(self):
        result = []
        for row in self.store.published_catalog():
            content = self.checked_content(row.get('content'), row.get('primary_dimension'))
            if content is not None and row.get('revision_id') == row['published_revision_id']:
                result.append({**row, 'content': content.model_dump()})
        return result

    def cities(self):
        cities = sorted({row['content']['place']['city'] for row in self.candidates() if row['content']['place']})
        return list({city_key(city): city for city in cities}.values())

    @staticmethod
    def checked_content(raw, dimension):
        try:
            content = Content.model_validate(raw)
        except ValidationError:
            return None
        return content if content.primary_dimension == dimension else None

    def reviewable_content(self, revision, activity):
        content = self.checked_content(revision.get('content'), activity['primary_dimension'])
        if content is None:
            raise DomainError('VALIDATION_ERROR', 'محتوای نسخه کامل نیست یا با بُعد اصلی فعالیت سازگار نیست.', 422)
        return content

    def detail(self, actor, activity_id):
        self.authorize(actor)
        return {**self.activity(activity_id), 'revisions': sorted(
            [r for r in self.store.list('activity_revisions') if r['activity_id'] == activity_id],
            key=lambda r: r['revision_number'], reverse=True)}

    def clone(self, actor, activity_id, source_id):
        with self.store.atomic():
            self.authorize(actor)
            activity = self.activity(activity_id)
            source = self.revision(source_id)
            if source['activity_id'] != activity_id:
                missing()
            number = activity['next_revision_number']
            revision = self.store.insert('activity_revisions', dict(id=uid(), activity_id=activity_id,
                revision_number=number, draft_version=1, state='draft', content=source['content'], origin='human',
                created_at=self.clock(), validation_report={}))
            activity['next_revision_number'] += 1
            replace(self.store, 'activities', activity)
            self.audit(actor['id'], 'revision_cloned', revision['id'])
            return revision

    def update(self, actor, revision_id, data):
        with self.store.atomic():
            self.authorize(actor)
            revision = self.revision(revision_id)
            self.check_draft(revision, data.expected_draft_version, ('draft', 'rejected'))
            if data.content.primary_dimension != self.activity(revision['activity_id'])['primary_dimension']:
                raise DomainError('VALIDATION_ERROR', 'بُعد اصلی نسخه با فعالیت سازگار نیست.', 422)
            revision.update(content=data.content.model_dump(), draft_version=revision['draft_version'] + 1,
                            state='draft', origin='human', validation_report={})
            saved = replace(self.store, 'activity_revisions', revision)
            self.audit(actor['id'], 'draft_updated', revision_id)
            return saved

    def check_draft(self, revision, expected, states):
        if revision['draft_version'] != expected:
            conflict()
        if revision['state'] not in states:
            raise DomainError('INVALID_STATE', 'این نسخه در وضعیت مناسب این کار نیست.')

    def submit(self, actor, revision_id, expected):
        with self.store.atomic():
            self.authorize(actor)
            revision = self.revision(revision_id)
            self.check_draft(revision, expected, ('draft', 'rejected'))
            self.reviewable_content(revision, self.activity(revision['activity_id']))
            revision.update(state='review', draft_version=revision['draft_version'] + 1)
            result = replace(self.store, 'activity_revisions', revision)
            self.audit(actor['id'], 'revision_submitted', revision_id)
            return result

    def publish(self, actor, revision_id, expected):
        with self.store.atomic():
            self.authorize(actor, admin=True)
            revision = self.revision(revision_id)
            self.check_draft(revision, expected, ('review',))
            activity = self.activity(revision['activity_id'])
            content = self.reviewable_content(revision, activity)
            if content.cost.kind == 'estimated':
                # Evidence editing is deferred; never accept an unsupported estimate in this slice.
                raise DomainError('VALIDATION_ERROR', 'انتشار قیمت برآوردی به مسیر ثبت مدرک نیاز داره.', 422)
            old = self.store.get('activity_revisions', activity.get('published_revision_id', ''))
            if old and old['state'] == 'published':
                old['state'] = 'superseded'
                replace(self.store, 'activity_revisions', old)
            revision.update(state='published', draft_version=revision['draft_version'] + 1,
                reviewed_by=actor['id'], reviewed_at=self.clock(), published_at=self.clock(),
                validation_report={**revision.get('validation_report', {}), 'schema_valid': True,
                                   'human_approval': True, 'dramma_version': content.dramma.version})
            saved = replace(self.store, 'activity_revisions', revision)
            activity.update(published_revision_id=revision_id, active=not activity.get('withdrawn', False))
            replace(self.store, 'activities', activity)
            self.audit(actor['id'], 'revision_published', revision_id)
            return saved

    def withdraw(self, actor, activity_id, reason):
        with self.store.atomic():
            self.authorize(actor, admin=True)
            activity = self.activity(activity_id)
            activity.update(active=False, withdrawn=True)
            replace(self.store, 'activities', activity)
            for revision in self.store.list('activity_revisions'):
                if revision['activity_id'] == activity_id and revision['state'] in ('published', 'superseded'):
                    revision['state'] = 'archived'
                    replace(self.store, 'activity_revisions', revision)
            self.audit(actor['id'], 'activity_withdrawn', activity_id, reason)
            return {'id': activity_id, 'active': False}

    def reactivate(self, actor, activity_id, reason):
        with self.store.atomic():
            self.authorize(actor, admin=True)
            activity = self.activity(activity_id)
            revision = self.store.get('activity_revisions', activity.get('published_revision_id') or '')
            if not activity.get('withdrawn') or not revision or revision['state'] != 'published':
                raise DomainError('INVALID_STATE', 'اول نسخهٔ تازه رو بررسی و منتشر کن.')
            activity.update(active=True, withdrawn=False)
            replace(self.store, 'activities', activity)
            self.audit(actor['id'], 'activity_reactivated', activity_id, reason)
            return {'id': activity_id, 'active': True}
