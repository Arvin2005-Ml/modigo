"""Read-only activity help; optional assets are cached per published revision."""
from datetime import timedelta
import logging
from math import ceil
from threading import BoundedSemaphore

from app.core.errors import DomainError, missing
from app.core.storage import StorageUnavailable
from app.core.values import digest, replace, uid
from app.modules.activity_assistant.provider import GapAssistantProvider, raster_type
from app.modules.activity_assistant.schemas import ChatReply, GuideText

ASSETS = 'activity_assistant_assets'
IMAGES = 'activity_assistant_images'
CACHE_VERSION = 'assistant_v1'
LEASE = timedelta(minutes=3)
COOLDOWN = timedelta(minutes=2)
RETENTION = timedelta(days=30)
logger = logging.getLogger('uvicorn.error')


def catalog_data(content):
    # Explicit projection: no account, prompts from admins, check-in, URLs,
    # personal preferences or internal scores. Price amounts can be stale.
    data = {key: content.get(key) for key in (
        'title', 'teaser', 'first_step', 'steps', 'lighter_version', 'materials_note', 'accessibility_note',
        'conditions_note', 'safety_notes', 'venue', 'active_minutes', 'setup_minutes', 'travel_minutes',
        'supported_social_modes', 'min_people', 'max_people', 'requires_venue_check',
        'required_items', 'energy_required', 'mobility_required', 'step_free', 'quiet_compatible',
        'weather_requirement', 'daylight_requirement', 'requires_async_contact',
    )}
    if content.get('place'):
        data['place'] = {key: content['place'][key] for key in ('name', 'city')}
    data['cost'] = {key: content['cost'][key] for key in ('kind', 'note')}
    return data


def catalog_guide(content):
    return dict(source='catalog', intro=content['teaser'], first_step=content['first_step'],
                steps=content['steps'], tips=[content['materials_note']], lighter_version=content['lighter_version'])


class ActivityAssistant:
    def __init__(self, store, catalog, limiter, settings, clock):
        self.store, self.catalog, self.limiter, self.clock = store, catalog, limiter, clock
        self.mode = settings.provider
        self.provider = GapAssistantProvider(settings) if self.mode == 'gapgpt' else None
        self.models = {'guide': settings.gapgpt_assistant_model, 'image': settings.gapgpt_image_model}
        self.image_hosts = ','.join(sorted(set(settings.gapgpt_image_hosts)))
        self.slots = {key: BoundedSemaphore(count) for key, count in [('guide', 2), ('image', 2), ('chat', 4)]}

    def close(self):
        if self.provider is not None:
            self.provider.close()

    def _content(self, revision_id):
        revision = self.catalog.visible_revision(revision_id)
        activity = self.catalog.activity(revision['activity_id'])
        parsed = self.catalog.checked_content(revision['content'], activity['primary_dimension'])
        if parsed is None:
            raise DomainError('CONTENT_WITHDRAWN', 'این پیشنهاد فعلاً در دسترس نیست.', 410)
        return catalog_data(parsed.model_dump())

    def _key(self, revision_id, kind):
        return digest(f'{CACHE_VERSION}:{revision_id}:{kind}:{self.models[kind]}')

    def _read(self, revision_id, kind, now):
        record = self.store.get(ASSETS, self._key(revision_id, kind))
        if record and record['expires_at'] > now:
            return record
        return None

    def _asset(self, revision_id, kind, now):
        record = self._read(revision_id, kind, now)
        if not record:
            return 'idle', None, None
        if record['state'] == 'pending' and now >= record['lease_until']:
            return 'failed', None, 0
        if record['state'] == 'failed':
            # A corrected CDN allowlist can be retried immediately after restart.
            remaining = (record['retry_at'] - now).total_seconds()
            if kind == 'image' and record.get('image_hosts') != self.image_hosts:
                remaining = 0
            return 'failed', None, max(0, ceil(remaining))
        return record['state'], record.get('guide'), None

    def _snapshot(self, revision_id, content):
        guide = catalog_guide(content)
        guide_status = 'ready'
        image_status = 'disabled'
        guide_retry = image_retry = image = None
        if self.mode == 'gapgpt':
            now = self.clock()
            guide_status, generated, guide_retry = self._asset(revision_id, 'guide', now)
            image_status, _, image_retry = self._asset(revision_id, 'image', now)
            if generated is not None:
                guide = {**generated, 'source': 'gapgpt'}
            if image_status == 'ready':
                image = dict(url=f'/api/v1/activity-revisions/{revision_id}/assistant/image',
                             alt=f'تصویرسازی برای «{content["title"]}»', source='gapgpt')
        return dict(revision_id=revision_id, mode=self.mode, guide_status=guide_status, guide=guide,
                    guide_retry_after_seconds=guide_retry, image_status=image_status, image=image,
                    image_retry_after_seconds=image_retry)

    def get(self, revision_id):
        return self._snapshot(revision_id, self._content(revision_id))

    def request(self, user_id, revision_id, kind, schedule):
        content = self._content(revision_id)
        if self.mode == 'demo':
            return 200, self._snapshot(revision_id, content)
        now = self.clock()
        state, _, retry_after = self._asset(revision_id, kind, now)
        if state in ('ready', 'pending') or retry_after:
            snapshot = self._snapshot(revision_id, content)
            return (202 if snapshot[f'{kind}_status'] == 'pending' else 200), snapshot
        slot = self.slots[kind]
        if not slot.acquire(blocking=False):
            self._busy()
        scheduled = False
        try:
            with self.store.atomic():
                content = self._content(revision_id)
                now = self.clock()
                state, _, retry_after = self._asset(revision_id, kind, now)
                if state in ('ready', 'pending') or retry_after:
                    return (202 if state == 'pending' else 200), self._snapshot(revision_id, content)
                per_user, global_limit = (20, 150) if kind == 'image' else (30, 300)
                self.limiter.take(f'assistant_{kind}', user_id, per_user, 86400)
                self.limiter.take(f'assistant_{kind}_total', 'global', global_limit, 86400)
                key = self._key(revision_id, kind)
                pending = dict(id=key, state='pending', attempt=uid(), lease_until=now + LEASE,
                               expires_at=now + LEASE + COOLDOWN)
                previous = self.store.get(ASSETS, key)
                if previous:
                    pending['version'] = previous['version']
                    replace(self.store, ASSETS, pending)
                else:
                    self.store.insert(ASSETS, pending)
                result = self._snapshot(revision_id, content)
            schedule(self._generate, revision_id, kind, pending)
            scheduled = True
            return (202 if result[f'{kind}_status'] == 'pending' else 200), result
        finally:
            if not scheduled:
                slot.release()

    @staticmethod
    def _busy():
        raise DomainError('ASSISTANT_BUSY', 'دستیار الان مشغوله؛ چند لحظه دیگه دوباره امتحان کن.', 503,
                          retry_after=5)

    def _generate(self, revision_id, kind, pending):
        try:
            try:
                if self.clock() >= pending['lease_until']:
                    return
                content = self._content(revision_id)
                if kind == 'guide':
                    result = GuideText.model_validate(self.provider.guide(content)).model_dump()
                else:
                    data, _ = self.provider.image(content)
                    result = (data, raster_type(data))
            except Exception as exc:
                # No raw provider exceptions, links, submissions or prompts in logs.
                logger.warning('Activity assistant %s generation failed (%s)', kind, type(exc).__name__)
                result = None
            try:
                self._finish(revision_id, kind, pending, result)
            except StorageUnavailable:
                # The pending lease expires; the next explicit request can retry.
                logger.warning('Activity assistant could not store %s result', kind)
        finally:
            self.slots[kind].release()

    def _finish(self, revision_id, kind, pending, result):
        key = pending['id']
        with self.store.atomic():
            current = self.store.get(ASSETS, key)
            if not current or current.get('attempt') != pending['attempt'] or current['state'] != 'pending':
                return
            now = self.clock()
            if now >= current['lease_until']:
                return
            if result is not None:
                try:
                    self._content(revision_id)
                except DomainError:
                    result = None
            if result is None:
                current.update(state='failed', retry_at=now + COOLDOWN, expires_at=now + COOLDOWN + LEASE)
                if kind == 'image':
                    current['image_hosts'] = self.image_hosts
            else:
                current.update(state='ready', expires_at=now + RETENTION)
                if kind == 'guide':
                    current['guide'] = result
                else:
                    image = dict(id=key, data=result[0], media_type=result[1], expires_at=current['expires_at'])
                    previous = self.store.get(IMAGES, key)
                    if previous:
                        image['version'] = previous['version']
                        replace(self.store, IMAGES, image)
                    else:
                        self.store.insert(IMAGES, image)
            replace(self.store, ASSETS, current)

    def image(self, revision_id):
        self._content(revision_id)
        if self.mode != 'gapgpt':
            missing()
        record = self._read(revision_id, 'image', self.clock())
        if not record or record['state'] != 'ready':
            missing()
        image = self.store.get(IMAGES, record['id'])
        if not image or image['expires_at'] <= self.clock():
            missing()
        return image['data'], image['media_type']

    def chat(self, user_id, revision_id, data):
        content = self._content(revision_id)
        if self.mode == 'demo':
            self.limiter.take('assistant_chat', user_id, 10, 60)
            question = data.messages[-1].content
            if any(word in question for word in ('وسیله', 'آماده', 'لازم', 'نیاز')):
                reply = 'این‌ها برای شروع کافیه: ' + content['materials_note']
            elif any(word in question for word in ('ساده', 'سبک', 'کوتاه', 'وقت ندار')):
                reply = content['lighter_version']
            else:
                reply = 'از همین‌جا شروع کن: ' + content['first_step']
            return ChatReply(revision_id=revision_id, source='demo', reply=reply)
        slot = self.slots['chat']
        if not slot.acquire(blocking=False):
            self._busy()
        try:
            with self.store.atomic():
                self.limiter.take('assistant_chat', user_id, 10, 60)
                self.limiter.take('assistant_chat_daily', user_id, 60, 86400)
                self.limiter.take('assistant_chat_total', 'global', 1200, 86400)
            try:
                text = self.provider.chat(content, [m.model_dump() for m in data.messages])
                answer = ChatReply(revision_id=revision_id, source='gapgpt', reply=text)
            except Exception as exc:
                logger.warning('Activity assistant chat failed (%s)', type(exc).__name__)
                raise DomainError('ASSISTANT_UNAVAILABLE', 'دستیار موقتاً در دسترس نیست؛ می‌تونی از راهنمای تفریح استفاده کنی.', 503) from None
            self._content(revision_id)
            return answer
        finally:
            slot.release()
