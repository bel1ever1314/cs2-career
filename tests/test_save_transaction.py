from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from cs2career.storage import transaction as tx


class TransactionTests(unittest.TestCase):
    def test_committed_state_cannot_be_caught_as_an_ordinary_io_error(self):
        self.assertFalse(issubclass(tx.CommitPending, OSError))
        with self.assertRaises(tx.CommitPending):
            try:
                raise tx.CommitPending('committed')
            except OSError:
                self.fail('A file/network fallback swallowed the commit')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('career.json', 'season.json'):
            (self.root / name).write_bytes(b'old')

    def test_repeated_nested_saves_serialize_only_final_value_once(self):
        calls = Mock(return_value=b'new')
        with tx.batch():
            for _ in range(11):
                with tx.batch():
                    tx.save(self.root/'season.json', calls)
            tx.save(self.root/'career.json', lambda: b'new')
            calls.assert_not_called()
            self.assertEqual(b'old', (self.root/'season.json').read_bytes())
        calls.assert_called_once()
        self.assertEqual(b'new', (self.root/'season.json').read_bytes())

    def test_exception_aborts_before_commit(self):
        with self.assertRaises(ValueError):
            with tx.batch():
                tx.save(self.root/'career.json', lambda: b'new')
                raise ValueError('rejected')
        self.assertEqual(b'old', (self.root/'career.json').read_bytes())

    def test_bounded_reads_apply_to_disk_and_pending_values(self):
        path = self.root/'career.json'
        self.assertEqual(b'ol', tx.read_bytes(path, max_bytes=2))
        with tx.batch():
            tx.save(path, lambda: b'new data')
            self.assertEqual(b'ne', tx.read_bytes(path, max_bytes=2))
            self.assertEqual(b'new data', tx.read_bytes(path))
        self.assertEqual(b'ne', tx.read_bytes(path, max_bytes=2))

    def test_process_death_at_every_commit_boundary(self):
        code = '''
import os, sys
from pathlib import Path
from cs2career.storage import transaction as tx
root, point = Path(sys.argv[1]), sys.argv[2]
def crash(at):
    if at == point: os._exit(71)
tx._checkpoint = crash
tx.commit({root/'career.json': b'new-career', root/'season.json': b'new-season'})
'''
        for point in ('staged:career.json', 'staged:season.json', 'before_commit',
                      'committed', 'replaced:career.json', 'replaced:season.json', 'finished'):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                for name in ('career', 'season'):
                    (root/f'{name}.json').write_bytes(b'old')
                child = subprocess.run([sys.executable, '-B', '-c', code, raw, point],
                                       timeout=20, capture_output=True)
                self.assertEqual(71, child.returncode, child.stderr.decode(errors='replace'))
                tx.recover(root)
                committed = point in ('committed', 'replaced:career.json', 'replaced:season.json', 'finished')
                for name in ('career', 'season'):
                    self.assertEqual(f'new-{name}'.encode() if committed else b'old',
                                     (root/f'{name}.json').read_bytes())
                self.assertFalse((root/tx.JOURNAL/'commit.json').exists())
                self.assertEqual([], list((root/tx.JOURNAL).glob('*.next')))
                self.assertFalse(tx.recover(root))

    def test_committed_failure_is_not_a_rollback(self):
        def fail(point):
            if point == 'replaced:career.json':
                raise OSError('occupied')
        with patch.object(tx, '_checkpoint', fail), self.assertRaises(tx.CommitPending):
            tx.commit({self.root/'career.json': b'new', self.root/'season.json': b'new'})
        self.assertTrue((self.root/tx.JOURNAL/'commit.json').exists())
        tx.recover(self.root)
        self.assertEqual(b'new', (self.root/'season.json').read_bytes())

    def test_corrupt_stage_preserves_evidence(self):
        def fail(point):
            if point == 'committed': raise OSError('crash')
        with patch.object(tx, '_checkpoint', fail), self.assertRaises(tx.CommitPending):
            tx.commit({self.root/'career.json': b'new', self.root/'season.json': b'new'})
        marker = self.root/tx.JOURNAL/'commit.json'
        record = json.loads(marker.read_text())
        (marker.parent/record['files'][0]['staged']).write_bytes(b'damaged')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            tx.recover(self.root)
        self.assertTrue(marker.exists())
        self.assertEqual(b'old', (self.root/'career.json').read_bytes())

    def test_sharing_violation_is_retried_but_disk_full_is_not(self):
        error = OSError('busy'); error.winerror = 32
        with patch.object(tx, '_replace_once', side_effect=[error, None]) as replace, patch.object(tx.time, 'sleep'):
            tx._replace(self.root/'x', self.root/'y')
            self.assertEqual(2, replace.call_count)
        with patch.object(tx, '_replace_once', side_effect=OSError('full')) as replace, self.assertRaises(OSError):
            tx._replace(self.root/'x', self.root/'y')
        self.assertEqual(1, replace.call_count)
