from app.core.errors import DomainError, conflict, missing
from app.core.values import uid, replace
from app.modules.catalog.schemas import Content
from pydantic import ValidationError


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
        return dict(id=revision['id'], activity_id=activity['id'], content=revision['content'], origin=revision['origin'])

    def candidates(self):
        result = []
        # The expanded catalog must not make one public Mongo round trip per
        # activity (including raw seeds). Resolve published pointers in one read.
        revisions = {revision['id']: revision for revision in self.store.list('activity_revisions')}
        for activity in self.store.list('activities'):
            revision = revisions.get(activity.get('published_revision_id'))
            if not activity['active'] or not revision or revision['state'] != 'published':
                continue
            try:
                self.validated_content(revision, activity)
            except DomainError:
                continue
            result.append(dict(id=activity['id'], active=True, published_revision_id=revision['id'],
                revision_id=revision['id'], state=revision['state'], content=revision['content']))
        return result

    def validated_content(self, revision, activity=None):
        """Legacy content stays inspectable; a fresh execution requires alignment."""
        activity = activity or self.activity(revision['activity_id'])
        try:
            content = Content.model_validate(revision.get('content'))
        except ValidationError:
            raise DomainError('VALIDATION_ERROR', 'هدف تجربه و قدم‌های مرتبط با آن را در محتوای کامل بررسی کن.', 422) from None
        if content.primary_dimension != activity['primary_dimension']:
            raise DomainError('VALIDATION_ERROR', 'بُعد اصلی نسخه با فعالیت سازگار نیست.', 422)
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
            if not revision.get('content'):
                raise DomainError('VALIDATION_ERROR', 'اول محتوای کامل این پیش‌نویس رو آماده کن.', 422)
            self.validated_content(revision)
            revision.update(state='review', draft_version=revision['draft_version'] + 1)
            result = replace(self.store, 'activity_revisions', revision)
            self.audit(actor['id'], 'revision_submitted', revision_id)
            return result

    def publish(self, actor, revision_id, expected):
        with self.store.atomic():
            self.authorize(actor, admin=True)
            revision = self.revision(revision_id)
            self.check_draft(revision, expected, ('review',))
            content = self.validated_content(revision)
            if content.cost.kind == 'estimated':
                # Evidence editing is deferred; never accept an unsupported estimate in this slice.
                raise DomainError('VALIDATION_ERROR', 'انتشار قیمت برآوردی به مسیر ثبت مدرک نیاز داره.', 422)
            activity = self.activity(revision['activity_id'])
            old = self.store.get('activity_revisions', activity.get('published_revision_id', ''))
            if old and old['state'] == 'published':
                old['state'] = 'superseded'
                replace(self.store, 'activity_revisions', old)
            revision.update(state='published', draft_version=revision['draft_version'] + 1,
                reviewed_by=actor['id'], reviewed_at=self.clock(), published_at=self.clock())
            revision['validation_report'] = {**revision.get('validation_report', {}),
                'schema_valid': True, 'dramma_version': content.dramma.version,
                'human_approval': True}
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
