import json
import threading
import unittest
from datetime import datetime, timezone
from app.core.config import Settings
from app.core.errors import DomainError
from support import MemoryTestStore
from app.core.values import uid, replace
from app.modules.catalog.schemas import CookInput, DraftUpdate
from app.modules.catalog.service import Catalog
from app.modules.content_jobs import ContentJobs, DemoProvider, ProviderFailure, validated


class JobsTests(unittest.TestCase):
    def setUp(self):
        self.clock = lambda: datetime(2026, 11, 7, tzinfo=timezone.utc)
        self.store = MemoryTestStore()
        self.actor = self.store.insert('users', {'id': uid(), 'status': 'active', 'role': 'editor'})
        self.activity = self.store.insert('activities', {'id': uid(), 'source_key': 'D-001', 'seed_key': 'bank:D-001',
            'raw_title': 'تماشای ابرها', 'raw_intent': '', 'primary_dimension': 'detachment',
            'active': False, 'published_revision_id': None, 'next_revision_number': 2})
        self.revision = self.store.insert('activity_revisions', {'id': uid(), 'activity_id': self.activity['id'],
            'revision_number': 1, 'draft_version': 1, 'state': 'draft', 'content': None, 'origin': 'human'})
        self.catalog = Catalog(self.store, self.clock)
        self.jobs = ContentJobs(self.store, self.catalog, Settings(), self.clock)
        self.data = CookInput(target_draft_id=self.revision['id'], expected_draft_version=1)

    def enqueue(self):
        return self.jobs.enqueue(self.actor, self.activity['id'], self.data)

    def test_demo_creates_only_unreviewed_draft(self):
        job = self.enqueue()
        self.assertTrue(self.jobs.process_one())
        self.assertEqual(self.jobs.get(self.actor, job['id'])['state'], 'succeeded')
        revision = self.catalog.revision(self.revision['id'])
        self.assertEqual((revision['state'], revision['origin'], revision['draft_version']), ('draft', 'demo', 2))
        self.assertFalse(revision['validation_report']['human_approval'])
        self.assertFalse(self.catalog.activity(self.activity['id'])['active'])

    def test_restart_fails_interrupted_jobs_without_repeating_provider_calls(self):
        job = self.enqueue()
        running = self.store.get('content_jobs', job['id'])
        running['state'] = 'running'
        replace(self.store, 'content_jobs', running)
        self.jobs.recover_interrupted()
        recovered = self.jobs.get(self.actor, job['id'])
        self.assertEqual(recovered['state'], 'failed')
        self.assertEqual(recovered['error_code'], 'WORKER_INTERRUPTED')
        self.assertFalse(self.jobs.process_one())
        self.assertIsNone(self.catalog.revision(self.revision['id'])['content'])
        self.jobs.recover_interrupted()
        self.assertEqual(len([a for a in self.store.list('admin_audit')
                             if a['action'] == 'content_job_interrupted']), 1)

    def test_unavailable_demo_and_permission(self):
        activity = self.catalog.activity(self.activity['id'])
        activity['source_key'] = 'D-002'
        replace(self.store, 'activities', activity)
        job = self.enqueue()
        self.jobs.process_one()
        self.assertEqual(self.jobs.get(self.actor, job['id'])['error_code'], 'DEMO_FIXTURE_UNAVAILABLE')
        user = self.store.insert('users', {'id': uid(), 'status':'active', 'role':'user'})
        with self.assertRaises(DomainError):
            self.jobs.list(user)

    def test_concurrent_edit_or_cancel_never_overwrites(self):
        for action in ('edit', 'cancel'):
            with self.subTest(action=action):
                self.setUp()
                started, release = threading.Event(), threading.Event()
                demo = DemoProvider()
                class Slow:
                    def generate(self, activity, constraints, previous=None):
                        started.set()
                        release.wait(3)
                        return demo.generate(activity, constraints, previous)
                self.jobs.provider = Slow()
                job = self.enqueue()
                thread = threading.Thread(target=self.jobs.process_one)
                thread.start()
                self.assertTrue(started.wait(3))
                if action == 'edit':
                    content = validated(demo.generate(self.activity, ''), 'detachment')
                    content['title'] = 'عنوان ویرایش شده انسان'
                    self.catalog.update(self.actor, self.revision['id'], DraftUpdate(expected_draft_version=1, content=content))
                else:
                    self.jobs.cancel(self.actor, job['id'])
                release.set()
                thread.join(3)
                self.assertFalse(thread.is_alive())
                result = self.jobs.get(self.actor, job['id'])
                self.assertEqual(result['state'], 'failed' if action == 'edit' else 'cancelled')
                if action == 'edit':
                    self.assertEqual(result['error_code'], 'STALE_DRAFT')
                    self.assertEqual(self.catalog.revision(self.revision['id'])['content']['title'], 'عنوان ویرایش شده انسان')
                else:
                    self.assertIsNone(self.catalog.revision(self.revision['id'])['content'])

    def test_single_active_job_and_auth_pause(self):
        class Broken:
            def generate(self, activity, constraints, previous=None):
                raise ProviderFailure('PROVIDER_AUTH')
        self.jobs.provider = Broken()
        self.enqueue()
        with self.assertRaises(DomainError):
            self.enqueue()
        self.jobs.process_one()
        self.assertTrue(self.jobs.paused)
        with self.assertRaises(DomainError):
            self.enqueue()
        self.jobs.resume()
        self.enqueue()

    def test_strict_parse_and_dimension(self):
        text = DemoProvider().generate(self.activity, '')
        self.assertEqual(validated('```json\n'+text+'\n```', 'detachment')['primary_dimension'], 'detachment')
        for invalid in (text + text, 'extra ' + text, text.replace('ابرها', 'https://example.test')):
            with self.assertRaises(ValueError):
                validated(invalid, 'detachment')
        with self.assertRaises(ValueError):
            validated(text, 'mastery')

    def test_single_repair_and_bounded_transport_retries(self):
        demo = DemoProvider()
        class Provider:
            calls = 0
            def generate(inner, activity, constraints, previous=None):
                inner.calls += 1
                if inner.calls == 1:
                    raise ProviderFailure('PROVIDER_UNAVAILABLE', True, 0)
                if inner.calls == 2:
                    return 'invalid JSON'
                self.assertEqual(previous, 'invalid JSON')
                return demo.generate(activity, constraints)
        provider = Provider()
        self.jobs = ContentJobs(self.store, self.catalog, Settings(provider='gapgpt'), self.clock, provider)
        job = self.enqueue()
        self.jobs.process_one()
        self.assertEqual(provider.calls, 3)
        self.assertEqual(self.jobs.get(self.actor, job['id'])['state'], 'succeeded')

        self.setUp()
        class AlwaysUnavailable:
            calls = 0
            def generate(inner, activity, constraints, previous=None):
                inner.calls += 1
                raise ProviderFailure('PROVIDER_UNAVAILABLE', True, 0)
        provider2 = AlwaysUnavailable()
        self.jobs.provider = provider2
        job = self.enqueue()
        self.jobs.process_one()
        self.assertEqual(provider2.calls, 3)
        self.assertEqual(self.jobs.get(self.actor, job['id'])['state'], 'failed')

    def test_withdraw_requires_fresh_published_revision_before_reactivation(self):
        admin = self.store.insert('users', {'id':uid(), 'role':'admin', 'status':'active'})
        self.enqueue(); self.jobs.process_one()
        r = self.catalog.revision(self.revision['id'])
        r = self.catalog.submit(self.actor, r['id'], r['draft_version'])
        self.catalog.publish(admin, r['id'], r['draft_version'])
        self.catalog.withdraw(admin, self.activity['id'], 'نیاز به بررسی بیشتر')
        with self.assertRaises(DomainError):
            self.catalog.reactivate(admin, self.activity['id'], 'بازبینی انجام شده')
        fresh = self.catalog.clone(self.actor, self.activity['id'], r['id'])
        fresh = self.catalog.submit(self.actor, fresh['id'], fresh['draft_version'])
        self.catalog.publish(admin, fresh['id'], fresh['draft_version'])
        self.assertFalse(self.catalog.activity(self.activity['id'])['active'])
        self.catalog.reactivate(admin, self.activity['id'], 'بازبینی انجام شده')
        self.assertTrue(self.catalog.activity(self.activity['id'])['active'])


if __name__ == '__main__':
    unittest.main()
