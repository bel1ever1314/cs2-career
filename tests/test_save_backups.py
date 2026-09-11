"""Storage-only checks: generated fixtures, no real saves and no career clock."""
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from cs2career import save_backups as backups


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='c2c-backup-check-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.original={name:json.dumps({'schema_version':2,'records':[{'name':'测试选手','round':1}]*2000},ensure_ascii=False).encode()
                       for name in backups.NAMES}
        for name,data in self.original.items():(self.root/name).write_bytes(data)

    def test_new_backup_is_compressed_verified_and_exactly_restorable(self):
        folder=backups.create(self.root)
        self.assertTrue(backups.verify(folder))
        for name,data in self.original.items():
            self.assertFalse((folder/name).exists())
            self.assertLess((folder/(name+'.gz')).stat().st_size,len(data))
            self.assertEqual(data,gzip.decompress((folder/(name+'.gz')).read_bytes()))
            (self.root/name).write_bytes(b'changed')
        backups.restore(self.root,folder)
        self.assertEqual(self.original,{name:(self.root/name).read_bytes() for name in backups.NAMES})

    def test_identical_backup_reused_changed_career_retained(self):
        first=backups.create(self.root)
        self.assertEqual(first,backups.create(self.root))
        (self.root/'career.json').write_bytes(b'{"money":12}')
        second=backups.create(self.root)
        self.assertNotEqual(first,second)
        self.assertTrue(backups.verify(first))
        self.assertTrue(backups.verify(second))
        self.assertEqual(second,backups.create(self.root))

    def test_legacy_backups_unchanged_and_restore_supported(self):
        old=self.root/'backups'/'old';old.mkdir(parents=True)
        for name,data in self.original.items():(old/name).write_bytes(data)
        stamps={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in old.iterdir()}
        backups.create(self.root)
        self.assertEqual(stamps,{p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in old.iterdir()})
        backups.restore(self.root,old)
        self.assertEqual(self.original,{name:(self.root/name).read_bytes() for name in backups.NAMES})

    def test_corrupt_second_member_does_not_replace_first_live_file(self):
        folder=backups.create(self.root)
        (folder/'career.json.gz').write_bytes(b'invalid gzip')
        for name in backups.NAMES:(self.root/name).write_bytes(b'keep current')
        with self.assertRaises((OSError,ValueError,EOFError)):backups.restore(self.root,folder)
        for name in backups.NAMES:self.assertEqual(b'keep current',(self.root/name).read_bytes())

    def test_hash_mismatch_is_not_reused_or_restored(self):
        folder=backups.create(self.root)
        (folder/'career.json.gz').write_bytes(gzip.compress(b'valid gzip but wrong content'))
        with self.assertRaises(ValueError):backups.restore(self.root,folder)
        newer=backups.create(self.root)
        self.assertNotEqual(folder,newer)
        self.assertTrue(backups.verify(newer))

    def test_missing_pair_and_unsafe_restore_are_rejected(self):
        folder=backups.create(self.root)
        (folder/'career.json.gz').unlink()
        with self.assertRaises(ValueError):backups.restore(self.root,folder)
        with self.assertRaises(ValueError):backups.restore(self.root,self.root)

    def test_single_file_snapshot_for_initial_creation(self):
        (self.root/'career.json').unlink()
        folder=backups.create(self.root)
        (self.root/'season.json').write_bytes(b'new')
        backups.restore(self.root,folder,require_pair=False)
        self.assertEqual(self.original['season.json'],(self.root/'season.json').read_bytes())

    def test_uncommitted_snapshot_never_reused(self):
        folder=backups.create(self.root)
        (folder/'snapshot.json').unlink()
        self.assertNotEqual(folder,backups.create(self.root))
