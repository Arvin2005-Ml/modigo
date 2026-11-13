import unittest
from support import MemoryTestStore
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from app.core.storage import (
    DuplicateRecord,
    VersionConflict,
    create_store,
)


class TestStorageContract(unittest.TestCase):
    def test_runtime_rejects_memory_modes_and_missing_mongo_uri(self):
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            for settings in ({}, {'DATA_BACKEND': 'mock'}, {'DATA_BACKEND': 'memory'}, {'DATA_BACKEND': 'other'}):
                with self.subTest(settings=settings), self.assertRaises(ValueError):
                    create_store(settings)

    def test_inputs_and_results_do_not_leak_mutable_references(self):
        store = MemoryTestStore()
        source = {'id': 'activity', 'tags': ['play']}
        inserted = store.insert('activities', source)
        source['tags'].append('changed-input')
        inserted['tags'].append('changed-result')
        loaded = store.get('activities', 'activity')
        loaded['tags'].append('changed-get')
        listed = store.list('activities')
        listed[0]['tags'].append('changed-list')
        self.assertEqual(store.get('activities', 'activity')['tags'], ['play'])

    def test_atomic_failure_rolls_back_all_collections(self):
        store = MemoryTestStore()
        store.insert('experiences', {'id': 'exp', 'status': 'active'})
        with self.assertRaises(RuntimeError):
            with store.atomic():
                store.replace('experiences', {'id': 'exp', 'status': 'completed'}, expected_version=1)
                store.insert('reward_ledger', {'id': 'reward', 'points': 10})
                raise RuntimeError('failed before commit')
        self.assertEqual(store.get('experiences', 'exp')['status'], 'active')
        self.assertEqual(store.list('reward_ledger'), [])

    def test_updates_reject_stale_versions(self):
        store = MemoryTestStore()
        store.insert('sessions', {'id': 'slate', 'slot': 'old'})
        result = store.replace('sessions', {'id': 'slate', 'slot': 'new'}, expected_version=1)
        self.assertEqual(result['version'], 2)
        with self.assertRaises(VersionConflict):
            store.replace('sessions', {'id': 'slate', 'slot': 'stale'}, expected_version=1)
        self.assertEqual(store.get('sessions', 'slate')['slot'], 'new')

    def test_concurrent_completion_example_awards_once(self):
        store = MemoryTestStore()
        store.insert('experiences', {'id': 'exp', 'status': 'active'})

        def finish(_):
            with store.atomic():
                experience = store.get('experiences', 'exp')
                if experience['status'] == 'completed':
                    return
                experience['status'] = 'completed'
                store.replace('experiences', experience, expected_version=experience['version'])
                store.insert('reward_ledger', {'id': 'reward', 'experience_id': 'exp', 'points': 10})

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(finish, range(20)))
        self.assertEqual(len(store.list('reward_ledger')), 1)
        self.assertEqual(store.get('experiences', 'exp')['status'], 'completed')

    def test_duplicate_ids_and_missing_updates_are_explicit(self):
        store = MemoryTestStore()
        store.insert('users', {'id': 'user'})
        with self.assertRaises(DuplicateRecord):
            store.insert('users', {'id': 'user'})
        with self.assertRaises(KeyError):
            store.replace('users', {'id': 'missing'}, expected_version=1)
        store.delete('users', 'user')
        store.delete('users', 'user')
        self.assertIsNone(store.get('users', 'user'))

    def test_new_application_lifespan_starts_empty(self):
        original = MemoryTestStore()
        original.insert('users', {'id': 'temporary'})
        self.assertEqual(MemoryTestStore().list('users'), [])


if __name__ == '__main__':
    unittest.main()
