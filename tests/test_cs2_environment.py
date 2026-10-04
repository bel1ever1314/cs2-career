"""Local-environment transforms in disposable CS2 trees; never launch a game."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cs2career.cs2 import environment, gameinfo


VALVE_GI = ('"GameInfo"\r\n{\r\n'
            '\tgame "Current Valve title"\r\n'
            '\tFileSystem\r\n\t{\r\n'
            '\t\tSteamAppId 710\r\n'
            '\t\tSearchPaths\r\n\t\t{\r\n'
            '\t\t\tGame_LowViolence csgo_lv\r\n'
            '\t\t\tGame csgo\r\n'
            '\t\t\tGame core\r\n'
            '\t\t\tGame csgo/another-user-mod\r\n'
            '\t\t\tMod csgo\r\n'
            '\t\t}\r\n\t}\r\n'
            '\tConVars { fps_max 400 } // Valve setting\r\n'
            '}\r\n')
BRANCH_GI = ('"GameInfo"\r\n{\r\n'
             '\t// Current branch, not a template from a Bot package.\r\n'
             '\tFileSystem { ForceFixedAppIds 1 SteamAppId 730 BreakpadAppId 2347771 }\r\n'
             '\tPanorama { PreprocessResources 1 }\r\n'
             '}\r\n')
BOM = b'\xef\xbb\xbf'


class CareerMountTransformTests(unittest.TestCase):
    def test_remove_only_exact_game_mounts_and_preserve_other_keys(self):
        text = ('GameInfo { FileSystem { SearchPaths { '
                'Game csgo Game core '
                'Game "CSGO\\addons\\metamod" '
                'Game csgo/overrides/botprofile.vpk '
                'Game csgo/overrides/ '
                'Game csgo/addons/metamod-other '
                'Game csgo/overrides/botprofile.vpk-other '
                'Game csgo/overrides2 '
                'Mod csgo/addons/metamod '
                'Game_LowViolence csgo/overrides '
                '} } ConVars { fps_max 400 } }')
        result = gameinfo.without_career_mounts(text)
        self.assertNotIn('"CSGO\\addons\\metamod"', result)
        self.assertNotIn('Game csgo/overrides/botprofile.vpk ', result)
        self.assertNotIn('Game csgo/overrides ', result)
        for preserved in ('Game core', 'Game csgo/addons/metamod-other',
                          'Game csgo/overrides/botprofile.vpk-other',
                          'Game csgo/overrides2', 'Mod csgo/addons/metamod',
                          'Game_LowViolence csgo/overrides', 'fps_max 400'):
            self.assertIn(preserved, result)

    def test_inline_comments_and_inline_unrelated_pairs_are_preserved(self):
        text = ('GameInfo { FileSystem { SearchPaths {\r\n'
                '  Game "csgo/addons/metamod" // do not erase this comment\r\n'
                '  Game csgo/overrides/botprofile.vpk Game csgo/user-vpk // preserve pair\r\n'
                '  Game csgo\r\n'
                '} } }\r\n')
        result = gameinfo.without_career_mounts(text)
        self.assertIn('// do not erase this comment\r\n', result)
        self.assertIn('Game csgo/user-vpk // preserve pair\r\n', result)
        self.assertNotIn('Game "csgo/addons/metamod"', result)
        self.assertNotIn('Game csgo/overrides/botprofile.vpk', result)
        self.assertNotIn('\n', result.replace('\r\n', ''))
        self.assertEqual(result, gameinfo.without_career_mounts(result))

    def test_comment_only_mounts_do_not_count_as_loading_entries(self):
        text = VALVE_GI.replace('Game core', 'Game core // Game csgo/addons/metamod')
        text = text.replace('Game core //', '/* Game csgo/overrides/botprofile.vpk */ Game core //')
        self.assertEqual(text, gameinfo.without_career_mounts(text))

    def test_whole_career_lines_removed_without_extra_blank_lines(self):
        patched = gameinfo.patched_gameinfo(VALVE_GI)
        self.assertEqual(VALVE_GI, gameinfo.without_career_mounts(patched))
        self.assertEqual(patched, gameinfo.patched_gameinfo(patched))

    def test_optional_branch_without_searchpaths_is_byte_equivalent_text(self):
        self.assertEqual(BRANCH_GI, gameinfo.without_career_mounts(BRANCH_GI, optional=True))
        with self.assertRaises(ValueError):
            gameinfo.without_career_mounts(BRANCH_GI)

    def test_duplicate_career_entries_are_all_removed(self):
        duplicated = gameinfo.patched_gameinfo(VALVE_GI).replace(
            'Game core', 'Game csgo/addons/metamod\r\n\t\t\tGame core')
        self.assertEqual(VALVE_GI, gameinfo.without_career_mounts(duplicated))

    def test_malformed_and_ambiguous_searchpaths_are_rejected(self):
        for text in ('GameInfo { FileSystem { SearchPaths { Game csgo } }',
                     'GameInfo { FileSystem { SearchPaths { Game } } }',
                     'GameInfo { FileSystem { SearchPaths { Game { csgo 1 } } } }',
                     'GameInfo { FileSystem { SearchPaths { Game csgo } SearchPaths { Game core } } }'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                gameinfo.without_career_mounts(text)


class EnvironmentLeaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='cs2-environment-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.csgo = self.root / 'game' / 'csgo'
        (self.csgo / 'cfg').mkdir(parents=True)
        (self.csgo / 'gameinfo.gi').write_bytes(BOM + VALVE_GI.encode('utf-8'))
        (self.csgo / 'gameinfo_branchspecific.gi').write_bytes(BOM + BRANCH_GI.encode('utf-8'))
        self.cfg_names = ('gamemode_competitive.cfg', 'gamemode_competitive_offline.cfg',
                          'gamemode_casual.cfg', 'gamemode_custom.cfg')
        for name in self.cfg_names:
            (self.csgo / 'cfg' / name).write_bytes(BOM + b'// Valve cfg\r\nbot_quota 10\r\n')
        (self.csgo / 'cfg' / 'career_rules.cfg').write_bytes(b'// isolated fixture\nbot_quota 9\n')
        self.plugins = {
            'addons/metamod/bin/win64/server.dll': b'never loaded fixture',
            'addons/metamod/BotController.vdf': b'"Plugin" { "file" "BotController" }',
            'addons/BotHider/config.json': b'{"identity_mode":"player"}',
            'addons/counterstrikesharp/plugins/InventorySimulator/InventorySimulator.dll': b'external fixture',
            'overrides/botprofile.vpk': b'fake VPK',
        }
        for relative, payload in self.plugins.items():
            path = self.csgo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        context = patch('cs2career.cs2.process_state.cs2_running', return_value=False)
        self.process = context.start()
        self.addCleanup(context.stop)

    def bytes_for(self, relative):
        return (self.csgo / relative).read_bytes()

    def assert_plugins_untouched(self):
        for relative, payload in self.plugins.items():
            self.assertEqual(payload, self.bytes_for(relative))

    def test_enhanced_normal_roundtrip_preserves_bom_crlf_branch_and_plugins(self):
        gi = self.bytes_for('gameinfo.gi')
        branch = self.bytes_for('gameinfo_branchspecific.gi')
        cfgs = {name: self.bytes_for('cfg/' + name) for name in self.cfg_names}
        enhanced = environment.switch_environment(self.csgo, 'enhanced', owner_pid=1234)
        self.assertEqual('enhanced', enhanced['mode'])
        self.assertTrue(enhanced['watch_active'])
        self.assertEqual('manual', enhanced['lease']['watch']['mode'])
        self.assertEqual(1234, enhanced['lease']['watch']['owner_pid'])
        for relative in ('gameinfo.gi',) + tuple('cfg/' + name for name in self.cfg_names):
            data = self.bytes_for(relative)
            self.assertTrue(data.startswith(BOM))
            self.assertNotIn(b'\n', data.replace(b'\r\n', b''))
        self.assertEqual(branch, self.bytes_for('gameinfo_branchspecific.gi'))
        normal = environment.switch_environment(self.csgo, 'normal')
        self.assertEqual('normal', normal['mode'])
        self.assertFalse(normal['watch_active'])
        self.assertEqual(gi, self.bytes_for('gameinfo.gi'))
        self.assertEqual(branch, self.bytes_for('gameinfo_branchspecific.gi'))
        for name, data in cfgs.items():
            self.assertEqual(data, self.bytes_for('cfg/' + name))
        self.assert_plugins_untouched()

    def test_exit_restore_keeps_personal_settings_changed_during_play(self):
        user_file = self.root / 'userdata/fixture/730/local/cfg/cs2_user_convars_0_slot0.vcfg'
        user_file.parent.mkdir(parents=True)
        before = b'"config" { "convars" { "cl_crosshairstyle" "4" } }'
        after = b'"config" { "convars" { "cl_crosshairstyle" "6" "cl_crosshair_thickness" "2" } }'
        user_file.write_bytes(before)
        autoexec = self.csgo / 'cfg/autoexec.cfg'
        autoexec.write_bytes(b'// personal settings\ncl_crosshair_gap -2\n')
        enabled = environment.switch_environment(self.csgo, 'enhanced')
        self.assertEqual(user_file.read_bytes(), before)
        user_file.write_bytes(after)  # The player changed their crosshair in CS2.
        environment.finish_watch(self.csgo, enabled['generation'])
        self.assertEqual(user_file.read_bytes(), after)
        self.assertEqual(autoexec.read_bytes(), b'// personal settings\ncl_crosshair_gap -2\n')

    def test_repeated_switch_keeps_same_game_bytes_and_no_duplicate_hook(self):
        first = environment.switch_environment(self.csgo, 'enhanced')
        first_gi = self.bytes_for('gameinfo.gi')
        first_cfg = self.bytes_for('cfg/gamemode_competitive.cfg')
        second = environment.switch_environment(self.csgo, 'enhanced')
        self.assertEqual(first_gi, self.bytes_for('gameinfo.gi'))
        self.assertEqual(first_cfg, self.bytes_for('cfg/gamemode_competitive.cfg'))
        self.assertEqual(1, first_cfg.count(b'exec career_rules.cfg'))
        self.assertNotEqual(first['generation'], second['generation'])
        environment.switch_environment(self.csgo, 'normal')
        normal_gi = self.bytes_for('gameinfo.gi')
        normal_cfg = self.bytes_for('cfg/gamemode_competitive.cfg')
        environment.switch_environment(self.csgo, 'normal')
        self.assertEqual(normal_gi, self.bytes_for('gameinfo.gi'))
        self.assertEqual(normal_cfg, self.bytes_for('cfg/gamemode_competitive.cfg'))

    def test_normal_removes_branch_mounts_but_preserves_current_branch_settings(self):
        branch = BRANCH_GI.replace('ForceFixedAppIds 1',
                                  'SearchPaths { Game csgo/addons/metamod Game core } ForceFixedAppIds 1')
        (self.csgo / 'gameinfo_branchspecific.gi').write_bytes(BOM + branch.encode())
        environment.switch_environment(self.csgo, 'normal')
        after = self.bytes_for('gameinfo_branchspecific.gi')
        self.assertTrue(after.startswith(BOM))
        self.assertNotIn(b'csgo/addons/metamod', after)
        self.assertIn(b'Game core', after)
        self.assertIn(b'ForceFixedAppIds 1 SteamAppId 730 BreakpadAppId 2347771', after)

    def test_normal_removes_only_our_cfg_hooks(self):
        target = self.csgo / 'cfg/gamemode_competitive.cfg'
        target.write_bytes(BOM + b'exec career_rules.cfg\r\nexec "career_quick.cfg"\r\n'
                           b'exec career_rules.cfg-extra\r\nexec user.cfg\r\n// exec career_rules.cfg\r\n')
        environment.switch_environment(self.csgo, 'normal')
        self.assertEqual(BOM + b'exec career_rules.cfg-extra\r\nexec user.cfg\r\n// exec career_rules.cfg\r\n',
                         target.read_bytes())

    def test_normal_removes_active_cfg_hooks_with_inline_comments(self):
        target = self.csgo / 'cfg/gamemode_competitive.cfg'
        target.write_bytes(BOM + b'exec career_rules.cfg // installed local hook\r\n'
                           b'exec "career_quick.cfg" // legacy quick hook\r\nexec user.cfg\r\n')
        environment.switch_environment(self.csgo, 'normal')
        self.assertNotIn(b'exec career_rules.cfg', target.read_bytes())
        self.assertNotIn(b'exec "career_quick.cfg"', target.read_bytes())
        self.assertIn(b'exec user.cfg', target.read_bytes())

    def test_snapshot_reads_actual_mounts_not_only_lease_checkbox(self):
        self.assertEqual('normal', environment.snapshot(self.csgo)['mode'])
        lease = environment.switch_environment(self.csgo, 'enhanced')['lease']
        (self.csgo / 'gameinfo.gi').write_bytes(BOM + VALVE_GI.encode())
        current = environment.snapshot(self.csgo)
        self.assertEqual('mixed', current['mode'])  # Valve restored GI, but owned cfg hooks remain.
        self.assertEqual(lease['generation'], current['generation'])
        environment.switch_environment(self.csgo, 'normal')
        self.assertEqual('normal', environment.snapshot(self.csgo)['mode'])
        (self.csgo / 'gameinfo.gi').write_bytes(BOM + VALVE_GI.replace(
            'Game core', 'Game csgo/addons/metamod\r\n\t\t\tGame core').encode())
        self.assertEqual('mixed', environment.snapshot(self.csgo)['mode'])

    def test_watch_generation_prevents_old_watcher_from_disabling_new_match(self):
        first = environment.switch_environment(self.csgo, 'enhanced')
        second = environment.switch_environment(self.csgo, 'enhanced', watch_mode='dispatch')
        before = self.bytes_for('gameinfo.gi')
        self.assertEqual({'status': 'superseded'}, environment.finish_watch(self.csgo, first['generation']))
        self.assertEqual(before, self.bytes_for('gameinfo.gi'))
        self.assertEqual(second['generation'], environment.read_lease(self.csgo)['generation'])
        result = environment.finish_watch(self.csgo, second['generation'])
        self.assertEqual('restored', result['status'])
        self.assertEqual('normal', environment.snapshot(self.csgo)['mode'])
        self.assertEqual({'status': 'superseded'}, environment.finish_watch(self.csgo, second['generation']))

    def test_running_and_unknown_process_refuse_switch_and_watch_finish(self):
        active = environment.switch_environment(self.csgo, 'enhanced')
        before = {relative: self.bytes_for(relative)
                  for relative in ('gameinfo.gi', 'cfg/' + environment.STATE_FILE)}
        for running in (True, None):
            self.process.return_value = running
            with self.subTest(running=running):
                with self.assertRaises(ValueError):
                    environment.switch_environment(self.csgo, 'normal')
                with self.assertRaises(ValueError):
                    environment.finish_watch(self.csgo, active['generation'])
                current = environment.snapshot(self.csgo)
                self.assertFalse(current['switch_available'])
                self.assertIs(current['process_known'], running is not None)
                for relative, data in before.items():
                    self.assertEqual(data, self.bytes_for(relative))

    def test_running_stale_watcher_is_noop_without_trying_to_switch(self):
        active = environment.switch_environment(self.csgo, 'enhanced')
        self.process.return_value = True
        self.assertEqual({'status': 'superseded'}, environment.finish_watch(self.csgo, '0' * 32))
        self.assertEqual(active['generation'], environment.read_lease(self.csgo)['generation'])

    def test_partial_write_error_rolls_back_files_and_does_not_commit_lease(self):
        originals = {name: self.bytes_for(name) for name in
                     ('gameinfo.gi', 'gameinfo_branchspecific.gi') + tuple('cfg/' + n for n in self.cfg_names)}
        real_replace = environment._replace

        def fail_on_second_cfg(path, before, after):
            if path.name == 'gamemode_competitive_offline.cfg' and b'exec career_rules.cfg' in after:
                raise PermissionError('isolated locked config')
            return real_replace(path, before, after)

        with patch.object(environment, '_replace', side_effect=fail_on_second_cfg):
            with self.assertRaises(PermissionError):
                environment.switch_environment(self.csgo, 'enhanced')
        for name, data in originals.items():
            self.assertEqual(data, self.bytes_for(name))
        self.assertEqual({}, environment.read_lease(self.csgo))
        self.assertFalse(list(self.csgo.rglob('.career-environment-*.tmp')))
        self.assert_plugins_untouched()

    def test_lease_write_failure_rolls_back_all_config_files_and_old_lease(self):
        first = environment.switch_environment(self.csgo, 'enhanced')
        originals = {name: self.bytes_for(name) for name in
                     ('gameinfo.gi', 'cfg/' + environment.STATE_FILE) + tuple('cfg/' + n for n in self.cfg_names)}
        real_replace = environment._replace

        def fail_lease(path, before, after):
            if path.name == environment.STATE_FILE:
                raise PermissionError('isolated lease failure')
            return real_replace(path, before, after)

        with patch.object(environment, '_replace', side_effect=fail_lease):
            with self.assertRaises(PermissionError):
                environment.switch_environment(self.csgo, 'normal')
        for name, data in originals.items():
            self.assertEqual(data, self.bytes_for(name))
        self.assertEqual(first['generation'], environment.read_lease(self.csgo)['generation'])

    def test_rollback_never_overwrites_a_concurrent_external_edit(self):
        gi = self.csgo / 'gameinfo.gi'
        original_cfg = self.bytes_for('cfg/gamemode_competitive.cfg')
        external = BOM + VALVE_GI.replace('Current Valve title', 'Updated by Steam').encode()
        real_replace = environment._replace

        def fail_after_external_update(path, before, after):
            if path.name == 'gamemode_competitive_offline.cfg':
                gi.write_bytes(external)
                raise PermissionError('isolated concurrent updater')
            return real_replace(path, before, after)

        with patch.object(environment, '_replace', side_effect=fail_after_external_update):
            with self.assertRaises(PermissionError):
                environment.switch_environment(self.csgo, 'enhanced')
        self.assertEqual(external, gi.read_bytes())
        self.assertEqual(original_cfg, self.bytes_for('cfg/gamemode_competitive.cfg'))
        self.assertEqual({}, environment.read_lease(self.csgo))

    def test_replace_detects_changed_bytes_and_leaves_external_edit(self):
        path = self.csgo / 'cfg/gamemode_competitive.cfg'
        before = path.read_bytes()
        external = b'// another app changed the cfg\r\n'
        original_closed = environment._closed

        def change_during_replace():
            original_closed()
            path.write_bytes(external)

        with patch.object(environment, '_closed', side_effect=change_during_replace):
            with self.assertRaises(OSError):
                environment._replace(path, before, before + b'exec career_rules.cfg\r\n')
        self.assertEqual(external, path.read_bytes())
        self.assertFalse(list(path.parent.glob('.career-environment-*.tmp')))

    def test_invalid_branch_is_rejected_before_any_game_mutation(self):
        before = self.bytes_for('gameinfo.gi')
        (self.csgo / 'gameinfo_branchspecific.gi').write_bytes(b'GameInfo { FileSystem {')
        with self.assertRaises(ValueError):
            environment.switch_environment(self.csgo, 'enhanced')
        self.assertEqual(before, self.bytes_for('gameinfo.gi'))
        self.assertEqual({}, environment.read_lease(self.csgo))

    def test_retired_layer_reference_refuses_old_package_config(self):
        gi = self.csgo / 'gameinfo.gi'
        before = BOM + VALVE_GI.replace('game "Current Valve title"',
                                       'LayeredOnMod csgo_imported').encode()
        gi.write_bytes(before)
        with self.assertRaises(ValueError):
            environment.switch_environment(self.csgo, 'enhanced')
        self.assertEqual(before, gi.read_bytes())

    def test_existing_valid_layer_is_preserved(self):
        layer = self.root / 'game' / 'user_layer'
        layer.mkdir()
        (layer / 'gameinfo.gi').write_bytes(b'GameInfo {}')
        gi = self.csgo / 'gameinfo.gi'
        before = BOM + VALVE_GI.replace('game "Current Valve title"',
                                       'LayeredOnMod user_layer').encode()
        gi.write_bytes(before)
        environment.switch_environment(self.csgo, 'enhanced')
        environment.switch_environment(self.csgo, 'normal')
        self.assertEqual(before, gi.read_bytes())

    def test_malformed_lease_snapshot_is_invalid_without_overwriting_it(self):
        path = self.csgo / 'cfg' / environment.STATE_FILE
        invalid = b'{"schema_version":1,"generation":"not-valid","mode":"enhanced","watch":{}}'
        path.write_bytes(invalid)
        current = environment.snapshot(self.csgo)
        self.assertFalse(current['valid'])
        self.assertEqual('unknown', current['mode'])
        self.assertFalse(current['switch_available'])
        self.assertEqual(invalid, path.read_bytes())

    def test_invalid_switch_parameters_do_not_change_files(self):
        original = self.bytes_for('gameinfo.gi')
        for args in ({'mode': 'unsupported'}, {'mode': 'enhanced', 'watch_mode': 'unsupported'},
                     {'mode': 'enhanced', 'owner_pid': True}, {'mode': 'enhanced', 'owner_pid': 0}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                environment.switch_environment(self.csgo, **args)
        self.assertEqual(original, self.bytes_for('gameinfo.gi'))
        self.assertEqual({}, environment.read_lease(self.csgo))


if __name__ == '__main__':
    unittest.main()
