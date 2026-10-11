import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cs2career.cs2 import launch


class ReviewedGamedataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'addons/RayTrace/gamedata.json'
        self.path.parent.mkdir(parents=True)
        self.server = self.root / 'bin/win64/server.dll'
        self.server.parent.mkdir(parents=True)
        self.server.write_bytes(b'reviewed fixture')
        source = Path(__file__).resolve().parents[1] / 'cs2career/data/cs2_gamedata_2000930.json'
        self.profile = json.loads(source.read_text())
        self.profile['server_sha256'] = hashlib.sha256(self.server.read_bytes()).hexdigest().upper()
        self.profile_file = self.root / 'profile.json'
        self.profile_file.write_text(json.dumps(self.profile))
        self.original = {key: {'signatures': {'library': 'server', 'windows': item['previous'],
                                             'linux': 'untouched'}, 'offsets': {'windows': 42}}
                         for key, item in self.profile['raytrace'].items()}
        self.original['custom'] = {'keep': True}
        self.path.write_text(json.dumps(self.original))
        self.addCleanup(patch.stopall)
        patch('cs2career.paths.data_file', return_value=self.profile_file).start()
        self.guard = patch.object(launch, 'require_cs2_closed').start()
        self.scanner = patch.object(launch, '_skin_signature_count', return_value=1).start()

    def test_repair_preserves_other_fields_and_backs_up_original_once(self):
        original = self.path.read_bytes()
        self.assertEqual(launch._install_reviewed_raytrace_gamedata(self.root), 1)
        patched = json.loads(self.path.read_text())
        for key, item in self.profile['raytrace'].items():
            self.assertEqual(patched[key]['signatures']['windows'], item['windows'])
            self.assertEqual(patched[key]['signatures']['linux'], 'untouched')
            self.assertEqual(patched[key]['offsets'], {'windows': 42})
        self.assertEqual(patched['custom'], {'keep': True})
        backups = list((self.path.parent / 'compat_backups').glob('*.bak'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        self.assertEqual(launch._install_reviewed_raytrace_gamedata(self.root), 0)
        self.guard.assert_called_once()

    def test_unknown_game_is_read_only(self):
        original = self.path.read_bytes()
        self.server.write_bytes(b'future unreviewed game')
        self.assertEqual(launch._install_reviewed_raytrace_gamedata(self.root), 0)
        self.assertEqual(self.path.read_bytes(), original)
        self.scanner.assert_not_called()
        self.guard.assert_not_called()

    def test_custom_signature_is_not_downgraded(self):
        data = self.original
        for key in self.profile['raytrace']:
            data[key]['signatures']['windows'] = 'custom newer signature'
        self.path.write_text(json.dumps(data))
        original = self.path.read_bytes()
        self.assertEqual(launch._install_reviewed_raytrace_gamedata(self.root), 0)
        self.assertEqual(self.path.read_bytes(), original)

    def test_nonunique_signature_and_running_game_block_all_writes(self):
        original = self.path.read_bytes()
        self.scanner.return_value = 2
        with self.assertRaises(ValueError):
            launch._install_reviewed_raytrace_gamedata(self.root)
        self.assertEqual(self.path.read_bytes(), original)
        self.scanner.return_value = 1
        self.guard.side_effect = ValueError('running')
        with self.assertRaises(ValueError):
            launch._install_reviewed_raytrace_gamedata(self.root)
        self.assertEqual(self.path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
