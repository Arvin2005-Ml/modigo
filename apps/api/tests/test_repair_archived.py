"""Checksummed archive repair only creates reviewed-queue revisions."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import unittest

from app.core.errors import DomainError
from app.core.values import replace, uid
from app.modules.catalog.activation import activation_queue
from app.modules.catalog.bootstrap import ROOT, demo_examples
from app.modules.catalog.repair_archived import RepairRefused, check_plan, plan_repairs, apply_repairs
from app.modules.catalog.service import Catalog
from support import MemoryTestStore

NOW = datetime(2026, 11, 18, tzinfo=timezone.utc)


class RepairArchivedTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryTestStore()
        self.catalog = Catalog(self.store, lambda: NOW)
        self.editor = self.store.insert('users', dict(id=uid(), role='editor', status='active'))
        self.admin = self.store.insert('users', dict(id=uid(), role='admin', status='active'))
        self.source = dict(demo_examples(include_iran=True))

    def archive(self, key, **activity_changes):
        activity_id, revision_id = uid(), uid()
        old = deepcopy(self.source[key])
        old.pop('dramma', None)
        old.pop('place', None)
        if not old['requires_venue_check']:
            old.pop('requires_venue_check')
        activity = self.store.insert('activities', dict(id=activity_id, seed_key=key, active=False,
            retired_by_catalog='real_catalog_v1', published_revision_id=revision_id,
            next_revision_number=2, primary_dimension=old['primary_dimension'], **activity_changes))
        revision = self.store.insert('activity_revisions', dict(id=revision_id, activity_id=activity_id,
            state='archived', origin='demo', content=old, revision_number=1, draft_version=1,
            validation_report={'human_approval': False}, reviewed_by=None))
        return activity, revision

    def plan(self):
        return plan_repairs(self.store.list('activities'), self.store.list('activity_revisions'))

    def test_repairs_actual_fixture_contents_for_review_and_keeps_originals(self):
        home, original_home = self.archive('demo:001')
        venue, original_venue = self.archive('demo:iran-cinema-01')
        pending, before = self.plan()
        check_plan(before, 2)
        self.assertEqual(before['pending_venue_plans'], 1)
        self.assertEqual(apply_repairs(self.store, lambda: NOW, pending), 2)

        queue = activation_queue(self.catalog, self.editor, 'needs_publish', 0, 10)
        self.assertEqual(queue['total'], 2)
        self.assertEqual(self.catalog.candidates(), [])
        for activity, original in ((home, original_home), (venue, original_venue)):
            updated = self.store.get('activities', activity['id'])
            self.assertFalse(updated['active'])
            self.assertEqual(updated['published_revision_id'], original['id'])
            self.assertEqual(updated['next_revision_number'], 3)
            self.assertEqual(self.store.get('activity_revisions', original['id']), original)
            item = next(row for row in queue['items'] if row['activity_id'] == activity['id'])
            revision = self.store.get('activity_revisions', item['revision_id'])
            self.assertEqual(revision['content'], self.source[activity['seed_key']])
            self.assertEqual(revision['repair']['source_revision_id'], original['id'])
            self.assertFalse(revision['validation_report']['human_approval'])
            self.assertIsNone(revision['reviewed_by'])
        venue_revision = next(row for row in queue['items'] if row['activity_id'] == venue['id'])['revision_id']
        with self.assertRaises(DomainError):
            self.catalog.publish(self.editor, venue_revision, 2)
        posted = self.catalog.publish(self.admin, venue_revision, 2)
        self.assertTrue(posted['content']['requires_venue_check'])
        self.assertTrue(posted['validation_report']['human_approval'])
        self.assertEqual(self.store.get('activity_revisions', original_venue['id']), original_venue)
        pending, result = self.plan()
        check_plan(result, 2)
        self.assertEqual(pending, [])
        self.assertEqual(result['already_prepared'], 2)
        self.assertEqual(result['prepared_verified_for_review'], 1)
        self.assertEqual(result['prepared_state_published'], 1)
        self.assertEqual(len([row for row in self.store.list('admin_audit')
                             if row['action'] == 'archived_demo_repaired_for_review']), 2)

    def test_refuses_changed_archives_and_does_not_include_retired_or_raw(self):
        _, changed = self.archive('demo:001')
        self.archive('demo:007')
        self.store.insert('activities', dict(id=uid(), seed_key='bank:D-001', active=False))
        changed['content']['title'] = 'عنوان ویرایش شده در بایگانی'
        replace(self.store, 'activity_revisions', changed)
        pending, result = self.plan()
        self.assertFalse(pending)
        self.assertEqual(result, {'unexpected_content': 1, 'retired_filler_excluded': 1})
        with self.assertRaises(RepairRefused):
            check_plan(result, 1)

    def test_concurrent_change_rolls_back_the_entire_current_batch(self):
        one, _ = self.archive('demo:001')
        two, _ = self.archive('demo:002')
        pending, result = self.plan()
        check_plan(result, 2)
        replace(self.store, 'activities', {**two, 'withdrawn': True})
        with self.assertRaises(RepairRefused):
            apply_repairs(self.store, lambda: NOW, pending)
        self.assertEqual(self.store.get('activities', one['id']), one)
        self.assertEqual(len(self.store.list('activity_revisions')), 2)
        self.assertEqual(self.store.list('admin_audit'), [])

    def test_every_nonretired_source_already_has_valid_repaired_content(self):
        # Loading requires the current schema, including matching evidence/steps.
        self.assertEqual(len(self.source), 431)
        self.assertEqual(sum(key.startswith('demo:iran-') for key in self.source), 300)
        checksums = json.loads((ROOT / 'content/dramma-legacy-checksums.json').read_text())['checksums']
        self.assertEqual(set(checksums), set(self.source))
