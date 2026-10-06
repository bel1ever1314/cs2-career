"""GameInfo regression tests operate only on temporary mock CS2 directories."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cs2career.cs2 import gameinfo


MERGED_GAMEINFO = '''"GameInfo"
{
    game "Counter-Strike 2"
    title "COUNTER-STRIKE 2"
    SupportsDX8 0
    SupportsDX9 0
    SupportsVR 0
    PanoramaUIClientFromClient 1
    MaterialSystem2 1
    LegacyEntitySystem 0
    "FileSystem"
    {
        SteamAppId 730
        ToolsAppId 211
        "SearchPaths"
        {
            Game_LowViolence csgo_lv
            Game csgo
            Game core
            Mod csgo
            Write csgo
            AddonRoot csgo_addons
        }
    }
    "ConVars"
    {
        sv_cheats 0
        custom_owner_setting "keep this value"
    }
}
'''

MINIMAL_GAMEINFO = '"GameInfo"\n{\n    "FileSystem"\n    {\n        "SearchPaths"\n        {\n            Game csgo\n        }\n    }\n}\n'


class PatchedGameInfoTests(unittest.TestCase):
    def test_merged_official_settings_are_preserved_with_only_two_mounts(self):
        after = gameinfo.patched_gameinfo(MERGED_GAMEINFO)
        expected = MERGED_GAMEINFO.replace(
            '            Game csgo\n',
            '            Game\tcsgo/overrides/career_botprofile.vpk\n'
            '            Game\tcsgo/addons/metamod\n'
            '            Game csgo\n', 1)
        self.assertEqual(expected, after)
        self.assertNotIn('LayeredOnMod', after)
        self.assertEqual(after, gameinfo.patched_gameinfo(after))

    def test_existing_mounts_are_idempotent_with_quoted_keys_and_path_variants(self):
        text = MINIMAL_GAMEINFO.replace(
            '            Game csgo\n',
            '            "gAmE" "CSGO\\OVERRIDES\\CAREER_BOTPROFILE.VPK/"\n'
            '            "GAME" "CSGO/addons/METAMOD/"\n'
            '            Game csgo\n')
        self.assertEqual(text, gameinfo.patched_gameinfo(text))

    def test_one_existing_mount_is_not_duplicated(self):
        for mounted, missing in (
            ('csgo/overrides/career_botprofile.vpk', 'csgo/addons/metamod'),
            ('csgo/addons/metamod', 'csgo/overrides/career_botprofile.vpk'),
        ):
            with self.subTest(mounted=mounted):
                text = MINIMAL_GAMEINFO.replace(
                    '            Game csgo\n',
                    f'            Game {mounted}\n            Game csgo\n')
                after = gameinfo.patched_gameinfo(text)
                self.assertEqual(1, after.count(mounted))
                self.assertEqual(1, after.count(missing))
                self.assertLess(after.index(missing), after.index(mounted))
                self.assertEqual(after, gameinfo.patched_gameinfo(after))

    def test_comments_quoted_keys_and_crlf_are_preserved(self):
        text = '''// Game csgo/overrides/botprofile.vpk { "FileSystem" }
"gAmEiNfO"
{
    /* fake SearchPaths { Game csgo/addons/metamod } */
    "FileSystem"
    {
        "SearchPaths"
        {
            // Keep this comment and the priority of the low violence path.
            "Game_LowViolence" "csgo_lv"
            "Game" "csgo" // official merged game folder
            "Game" "core"
        }
    }
    "Description" "a quoted { brace } and escaped \\"word\\""
}
'''.replace('\n', '\r\n')
        expected = text.replace(
            '            "Game" "csgo"',
            '            Game\tcsgo/overrides/career_botprofile.vpk\r\n'
            '            Game\tcsgo/addons/metamod\r\n'
            '            "Game" "csgo"', 1)
        after = gameinfo.patched_gameinfo(text)
        self.assertEqual(expected, after)
        self.assertNotIn('\n', after.replace('\r\n', ''))

    def test_invalid_searchpaths_are_rejected(self):
        invalid = {
            'missing': 'GameInfo { FileSystem { SteamAppId 730 } }',
            'duplicate': 'GameInfo { FileSystem { SearchPaths { Game csgo } SearchPaths { Game core } } }',
            'duplicate filesystem': 'GameInfo { FileSystem { SearchPaths { Game csgo } } FileSystem { SearchPaths { Game core } } }',
            'odd entries': 'GameInfo { FileSystem { SearchPaths { Game } } }',
            'nested entries': 'GameInfo { FileSystem { SearchPaths { Game { Value csgo } } } }',
            'no game': 'GameInfo { FileSystem { SearchPaths { Mod csgo } } }',
            'unclosed': 'GameInfo { FileSystem { SearchPaths { Game csgo } }',
        }
        for case, text in invalid.items():
            with self.subTest(case=case), self.assertRaises(ValueError):
                gameinfo.patched_gameinfo(text)


class EnsureGameInfoMountsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cs2career-gameinfo-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.csgo = self.root / 'game' / 'csgo'
        self.csgo.mkdir(parents=True)
        self.path = self.csgo / 'gameinfo.gi'

    def write_gameinfo(self, text=MERGED_GAMEINFO, *, bom=False):
        before = (b'\xef\xbb\xbf' if bom else b'') + text.encode('utf-8')
        self.path.write_bytes(before)
        return before

    def assert_original_untouched(self, before):
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual([], list(self.csgo.glob('.career-gameinfo-*.tmp')))

    def test_atomic_replacement_keeps_verified_original_backup_and_bom(self):
        before = self.write_gameinfo(MERGED_GAMEINFO.replace('\n', '\r\n'), bom=True)
        backup = self.csgo / ('gameinfo.gi.career-backup.' + hashlib.sha256(before).hexdigest()[:12])
        real_replace = os.replace

        def checked_replace(source, target):
            self.assertEqual(self.csgo, Path(source).parent)
            self.assertEqual(self.path, Path(target))
            self.assertEqual(before, self.path.read_bytes())
            self.assertEqual(before, backup.read_bytes())
            real_replace(source, target)

        with patch.object(gameinfo.os, 'replace', side_effect=checked_replace) as replace:
            self.assertTrue(gameinfo.ensure_gameinfo_mounts(self.csgo))
            replace.assert_called_once()
        self.assertEqual(before, backup.read_bytes())
        expected = b'\xef\xbb\xbf' + gameinfo.patched_gameinfo(before.decode('utf-8-sig')).encode('utf-8')
        self.assertEqual(expected, self.path.read_bytes())
        self.assertEqual([], list(self.csgo.glob('.career-gameinfo-*.tmp')))

    def test_unchanged_file_is_not_rewritten_and_does_not_create_another_backup(self):
        self.write_gameinfo()
        self.assertTrue(gameinfo.ensure_gameinfo_mounts(self.csgo))
        os.utime(self.path, ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))
        stamp = self.path.stat().st_mtime_ns
        before = self.path.read_bytes()
        with patch.object(gameinfo.shutil, 'copy2') as copy, patch.object(gameinfo.os, 'replace') as replace:
            self.assertFalse(gameinfo.ensure_gameinfo_mounts(self.csgo))
            copy.assert_not_called()
            replace.assert_not_called()
        self.assertEqual(stamp, self.path.stat().st_mtime_ns)
        self.assert_original_untouched(before)
        self.assertEqual(1, len(list(self.csgo.glob('gameinfo.gi.career-backup.*'))))

    def test_missing_gameinfo_is_rejected_without_creating_files(self):
        with self.assertRaises(FileNotFoundError):
            gameinfo.ensure_gameinfo_mounts(self.csgo)
        self.assertEqual([], list(self.csgo.iterdir()))

    def test_missing_or_duplicate_searchpaths_never_changes_the_file(self):
        for text in (
            'GameInfo { FileSystem { SteamAppId 730 } }',
            'GameInfo { FileSystem { SearchPaths { Game csgo } SearchPaths { Game core } } }',
        ):
            with self.subTest(text=text):
                before = self.write_gameinfo(text)
                with self.assertRaises(ValueError):
                    gameinfo.ensure_gameinfo_mounts(self.csgo)
                self.assert_original_untouched(before)
                self.assertEqual([self.path], list(self.csgo.iterdir()))

    def test_removed_layered_base_is_rejected_without_backup_or_replacement(self):
        before = self.write_gameinfo(MINIMAL_GAMEINFO.replace('{\n', '{\n    LayeredOnMod csgo_core\n', 1))
        with self.assertRaisesRegex(ValueError, 'csgo_core'):
            gameinfo.ensure_gameinfo_mounts(self.csgo)
        self.assert_original_untouched(before)
        self.assertEqual([self.path], list(self.csgo.iterdir()))

    def test_existing_old_layered_base_is_allowed_and_preserved(self):
        base = self.csgo.parent / 'csgo_core' / 'gameinfo.gi'
        base.parent.mkdir()
        base.write_bytes(MERGED_GAMEINFO.encode('utf-8'))
        before = self.write_gameinfo(MINIMAL_GAMEINFO.replace('{\n', '{\n    "LayeredOnMod" "csgo_core"\n', 1))
        self.assertTrue(gameinfo.ensure_gameinfo_mounts(self.csgo))
        self.assertEqual(gameinfo.patched_gameinfo(before.decode('utf-8')), self.path.read_text('utf-8'))
        self.assertIn('"LayeredOnMod" "csgo_core"', self.path.read_text('utf-8'))
        self.assertEqual(MERGED_GAMEINFO.encode('utf-8'), base.read_bytes())

    def test_backup_failure_preserves_original_and_never_stages_a_replacement(self):
        before = self.write_gameinfo()
        with patch.object(gameinfo.shutil, 'copy2', side_effect=PermissionError('backup locked')):
            with self.assertRaises(PermissionError):
                gameinfo.ensure_gameinfo_mounts(self.csgo)
        self.assert_original_untouched(before)
        self.assertEqual([self.path], list(self.csgo.iterdir()))

    def test_conflicting_backup_is_not_overwritten_and_blocks_replacement(self):
        before = self.write_gameinfo()
        backup = self.csgo / ('gameinfo.gi.career-backup.' + hashlib.sha256(before).hexdigest()[:12])
        backup.write_bytes(b'keep existing backup')
        with self.assertRaises(OSError):
            gameinfo.ensure_gameinfo_mounts(self.csgo)
        self.assert_original_untouched(before)
        self.assertEqual(b'keep existing backup', backup.read_bytes())

    def test_replace_failure_keeps_original_backup_and_cleans_staging_file(self):
        before = self.write_gameinfo()
        with patch.object(gameinfo.os, 'replace', side_effect=PermissionError('gameinfo locked')):
            with self.assertRaises(PermissionError):
                gameinfo.ensure_gameinfo_mounts(self.csgo)
        self.assert_original_untouched(before)
        backups = list(self.csgo.glob('gameinfo.gi.career-backup.*'))
        self.assertEqual(1, len(backups))
        self.assertEqual(before, backups[0].read_bytes())

    def test_flush_failure_keeps_original_and_cleans_staging_file(self):
        before = self.write_gameinfo()
        with patch.object(gameinfo.os, 'fsync', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                gameinfo.ensure_gameinfo_mounts(self.csgo)
        self.assert_original_untouched(before)


if __name__ == '__main__':
    unittest.main()
