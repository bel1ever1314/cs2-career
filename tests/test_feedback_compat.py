"""Tester feedback regressions. All VPKs and requests are temporary fixtures."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

from cs2career.cs2 import custom_profiles, profiles, launch
from cs2career.cs2.gameinfo import patched_gameinfo, without_career_mounts
from cs2career.cs2.launch import build_request
from cs2career.cs2.result import pick_better_result, result_usable
from cs2career.engine.rating import career_rating
from tests.test_v15_core import fake_team
from tests.test_cs2_result_integrity import RealResultIntegrityTests


class FeedbackTests(unittest.TestCase):
    def test_rating_over_250_keeps_exceptional_maps_distinct(self):
        thirty = career_rating(30, 4, 6, 3400, 18, 19)
        fifty = career_rating(50, 4, 6, 5400, 18, 19)
        self.assertGreater(fifty, 2.5)
        self.assertGreater(fifty, thirty)
        self.assertEqual(.2, career_rating(0, 19, 0, 0, 0, 19))

    def fixture_result(self):
        fixture = RealResultIntegrityTests()
        fixture.setUp()
        return fixture.result, fixture.session

    def test_complete_backup_beats_incomplete_final_dump(self):
        good, session = self.fixture_result()
        good['ended_at'] = '2026-10-05T12:00:00Z'
        bad = deepcopy(good)
        bad.update(complete=False, validation_error='identity slots lost after exit')
        bad['players'][0]['kills'] += 1
        self.assertIs(good, pick_better_result(bad, good))
        self.assertEqual('', result_usable(pick_better_result(bad, good), session))
        later = deepcopy(bad)
        later['ct_score'] += 1
        self.assertIs(later, pick_better_result(later, good))
        other = deepcopy(good)
        other['request_nonce'] = 'other'
        self.assertIs(bad, pick_better_result(bad, other))

    def test_timestamps_compare_instants_not_timezone_strings(self):
        row, session = self.fixture_result()
        session['started_at'] = '2026-10-05T18:00:00+08:00'
        row['ended_at'] = '2026-10-05T10:15:00Z'
        self.assertEqual('', result_usable(row, session))
        row['ended_at'] = '2026-10-05T09:59:00Z'
        self.assertIn('残留战绩', result_usable(row, session))

    def test_custom_vpk_preserves_source_and_match_identity(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / 'overrides' / 'botprofile.vpk'
            source.parent.mkdir()
            text = ('Default\n Skill = 77\n ReactionTime = 0.314\nEnd\n'
                    'Template RiflePro\n WeaponPreference = ak47\n WeaponPreference = m4a1\nEnd\n'
                    'RiflePro "OriginalPlayer"\n Skill = 91\nEnd\n')
            profiles.write_vpk(source, text)
            original = source.read_bytes()
            req = build_request(fake_team('A', 80), fake_team('B', 82), 'A0', 'de_mirage', 'ct')
            launch.install_match_avatars(root, req)
            ids = {r['player_id'] for side in ('ct', 't') for r in req[side]['players']}
            for _ in range(2):
                manifest = profiles.generate_match_vpk(root, req, 'High', root / 'cache', custom_source=str(source))
                self.assertEqual(original, source.read_bytes())
                db = profiles.read_db(root / 'overrides' / profiles.MATCH_VPK)
                self.assertIn('ReactionTime = 0.314', db)
                self.assertNotIn('OriginalPlayer', db)
                self.assertEqual(9, len(profiles.PROFILE_RE.findall(db)))
                self.assertEqual(ids, {b['player_id'] for b in manifest['bots']})
                self.assertTrue(profiles.active_manifest(root)['valid'])
                self.assertEqual(custom_profiles.MODEL, manifest['difficulty_model'])
                self.assertEqual(hashlib.sha256(original).hexdigest(), manifest['preset_source_hash'])
            profiles.generate_match_vpk(root, req, 'Medium', root / 'cache')
            self.assertEqual(original, source.read_bytes())
            self.assertNotEqual(custom_profiles.MODEL, profiles.active_manifest(root)['difficulty_model'])

    def test_custom_vpk_bad_crc_and_missing_default_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / 'custom.vpk'
            profiles.write_vpk(path, 'Template RiflePro\n Skill = 80\nEnd\n')
            with self.assertRaisesRegex(ValueError, 'Default'):
                custom_profiles.load(path)
            blob = bytearray(profiles.vpk_bytes('Default\n Skill = 77\nEnd\n'))
            index = blob.index(b'Skill = 77')
            blob[index + 8] = ord('6')
            path.write_bytes(blob)
            with self.assertRaisesRegex(ValueError, '校验失败'):
                custom_profiles.load(path)

    def test_own_vpk_mount_is_below_career_mount_and_exit_unmounts_both(self):
        original = 'GameInfo { FileSystem { SearchPaths { Game csgo/overrides/botprofile.vpk Game csgo Game core } } }'
        patched = patched_gameinfo(original)
        self.assertLess(patched.index('career_botprofile.vpk'), patched.index('Game csgo/overrides/botprofile.vpk'))
        self.assertEqual(patched, patched_gameinfo(patched))
        normal = without_career_mounts(patched)
        self.assertNotIn('botprofile.vpk', normal)
        self.assertIn('Game csgo Game core', normal)


if __name__ == '__main__':
    unittest.main()
