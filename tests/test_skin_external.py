"""External inventory ownership, using D: mock game trees and no game/network."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs2career.cs2 import launch
from cs2career.career import skins


class ExternalInventoryTests(unittest.TestCase):
    def setUp(self):
        qa = Path('D:/CS2CareerBuilds/v1.6.0/optional-skin-compat-20261001/qa')
        qa.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='external-inventory-', dir=qa)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.game = self.root / 'game' / 'csgo'
        self.game.mkdir(parents=True)
        (self.game / 'steam.inf').write_bytes(b'fixture')
        (self.game / 'gameinfo.gi').write_text(
            '"GameInfo" { "FileSystem" { "SearchPaths" { Game csgo } } }', encoding='utf-8')
        self.mod = self.root / 'mod'
        for rel in ('addons/metamod', 'addons/counterstrikesharp', 'addons/BotHider', 'overrides'):
            (self.mod / rel).mkdir(parents=True)
            (self.game / rel).mkdir(parents=True)
        self.cfg = dict(launch.DEFAULTS, skins_inventory_mode='external', csgo_path=str(self.game),
                        mod_source_path=str(self.mod))
        self.career = SimpleNamespace(real_skins=True, steam_id='76561198000000000',
                                      inventory=[{'id': 'keep', 'stickers': [{'def': 7928, 'slot': 4}]}],
                                      equipped_ct={'ak47': 'keep'}, equipped_t={'ak47': 'keep'})
        for context in (
            patch.dict(os.environ, {'CS2CAREER_SAVE_DIR': str(self.root / 'save'),
                                    'CS2CAREER_EXTENSION_DIR': str(self.root / 'extensions')}),
            patch.object(launch, 'settings', side_effect=lambda: dict(self.cfg)),
            patch.object(launch, 'cs2_is_live', return_value=False),
        ):
            context.start()
            self.addCleanup(context.stop)
        self.external = {}
        for rel in (
            'addons/counterstrikesharp/plugins/InventorySimulator/InventorySimulator.dll',
            'addons/counterstrikesharp/plugins/InventorySimulator/custom.json',
            'addons/counterstrikesharp/gamedata/inventory-simulator.json',
            'addons/counterstrikesharp/gamedata/inventory-simulator.previous.json',
            'addons/counterstrikesharp/configs/plugins/InventorySimulator/inventories.json',
            'addons/counterstrikesharp/configs/plugins/InventorySimulator/owner.txt',
            'cfg/invsim_career.cfg', 'inventories.career.json',
        ):
            path = self.game / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            blob = ('user-owned ' + rel).encode()
            path.write_bytes(blob)
            self.external[rel] = blob

    def assert_external_untouched(self):
        for rel, expected in self.external.items():
            with self.subTest(relative=rel):
                self.assertEqual(expected, (self.game / rel).read_bytes())
        self.assertFalse(launch._plugin_parked(self.game, 'InventorySimulator').exists())

    def bridge(self):
        path = launch._plugin_live(self.game, 'InvsimCareer') / 'InvsimCareer.dll'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'our bridge')
        return path

    def test_missing_legacy_mode_defaults_to_career(self):
        self.assertEqual('career', launch.skins_inventory_mode({}))
        self.assertEqual('career', launch.skins_inventory_mode({'skins_inventory_mode': 'invalid'}))
        self.assertEqual('external', launch.skins_inventory_mode(self.cfg))

    def test_external_does_not_copy_disable_or_replace_user_plugin(self):
        bridge = self.bridge()
        with patch.object(launch, '_copy_skins_into', side_effect=AssertionError('must not copy')), \
             patch.object(launch, '_remove_plugin', side_effect=AssertionError('must not remove user plugin')), \
             patch.object(launch, 'restore_bot_randomizer', return_value=0) as bots:
            self.assertEqual(1, launch.install_skins_plugin(self.game, self.career))
            self.assertEqual(0, launch.install_skins_plugin(self.game, self.career))
        self.assertFalse(bridge.exists())
        self.assertEqual(b'our bridge', (launch._plugin_parked(self.game, 'InvsimCareer') / 'InvsimCareer.dll').read_bytes())
        self.assertEqual(2, bots.call_count)
        self.assert_external_untouched()

    def test_false_career_toggle_does_not_disable_external_plugin(self):
        self.career.real_skins = False
        with patch.object(launch, 'restore_bot_randomizer', return_value=0):
            launch.install_skins_plugin(self.game, self.career)
        self.assert_external_untouched()

    def test_existing_parked_bridge_is_not_destroyed(self):
        previous = launch._plugin_parked(self.game, 'InvsimCareer') / 'InvsimCareer.dll'
        previous.parent.mkdir(parents=True)
        previous.write_bytes(b'previous recoverable bridge')
        self.bridge()
        with patch.object(launch.time, 'time_ns', return_value=123):
            self.assertEqual(1, launch._prepare_external_skins(self.game))
        self.assertEqual(b'previous recoverable bridge', previous.read_bytes())
        self.assertEqual(b'our bridge', (previous.parent.with_name('InvsimCareer.career-external-123') / 'InvsimCareer.dll').read_bytes())

    def test_detaches_only_our_exact_exec_lines_with_byte_preserving_backups(self):
        original = b'// player config\r\ninvsim_url "https://example.test"\r\nexec invsim_career.cfg\r\nexec custom-skins.cfg\r\n'
        cfg = self.game / 'cfg/server.cfg'
        cfg.write_bytes(original)
        untouched = self.game / 'cfg/listenserver.cfg'
        other = b'// exec invsim_career.cfg\ninvsim_file "my.json"\nexec "invsim_career.cfg"\n'
        untouched.write_bytes(other)
        self.assertEqual(1, launch._prepare_external_skins(self.game))
        self.assertEqual(original.replace(b'exec invsim_career.cfg\r\n', b''), cfg.read_bytes())
        self.assertEqual(original, cfg.with_name('server.cfg.career-external-backup').read_bytes())
        self.assertEqual(other, untouched.read_bytes())
        stamp = cfg.stat().st_mtime_ns
        self.assertEqual(0, launch._prepare_external_skins(self.game))
        self.assertEqual(stamp, cfg.stat().st_mtime_ns)
        self.assert_external_untouched()

    def test_backup_failure_keeps_original_hook_and_reports_failure(self):
        cfg = self.game / 'cfg/server.cfg'
        original = b'invsim_file my.json\nexec invsim_career.cfg\n'
        cfg.write_bytes(original)
        with patch.object(launch.shutil, 'copy2', side_effect=PermissionError('backup locked')):
            with self.assertRaisesRegex(PermissionError, 'backup locked'):
                launch._prepare_external_skins(self.game)
        self.assertEqual(original, cfg.read_bytes())
        self.assertEqual([], list(cfg.parent.glob('*.tmp')))

    def test_repeated_switch_preserves_previous_and_current_config_backups(self):
        cfg = self.game / 'cfg/server.cfg'
        first = b'invsim_file first.json\nexec invsim_career.cfg\n'
        cfg.write_bytes(first)
        launch._prepare_external_skins(self.game)
        second = b'invsim_file second.json\nexec invsim_career.cfg\n'
        cfg.write_bytes(second)
        with patch.object(launch.time, 'time_ns', return_value=456):
            launch._prepare_external_skins(self.game)
        self.assertEqual(first, cfg.with_name('server.cfg.career-external-backup').read_bytes())
        self.assertEqual(second, cfg.with_name('server.cfg.career-external-backup-456').read_bytes())

    def test_running_game_refuses_bridge_and_hook_changes(self):
        bridge = self.bridge()
        cfg = self.game / 'cfg/server.cfg'
        cfg.write_bytes(b'exec invsim_career.cfg\n')
        with patch.object(launch, 'cs2_is_live', return_value=True):
            for action in (lambda: launch.install_skins_mod(self.game),
                           lambda: launch.install_skins_plugin(self.game, self.career)):
                with self.assertRaisesRegex(ValueError, '退出 CS2'):
                    action()
        self.assertTrue(bridge.exists())
        self.assertEqual(b'exec invsim_career.cfg\n', cfg.read_bytes())
        self.assert_external_untouched()

    def test_installer_only_prepares_bridge_no_source_css_or_download_needed(self):
        self.bridge()
        with patch.object(launch, 'skins_plugin_src', side_effect=AssertionError('not our plugin')), \
             patch.object(launch, 'css_installed', side_effect=AssertionError('must not install CSS')):
            result = launch.install_skins_mod(self.game)
        self.assertTrue(result['ok'])
        self.assertTrue(result['skins_installed'])
        self.assertEqual('external', result['skins_inventory_mode'])
        self.assertIn('不保证任意版本', result['msg'])
        self.assert_external_untouched()

    def test_updater_copy_and_cfg_low_level_paths_are_blocked_without_network(self):
        with patch.object(launch.urllib.request, 'urlopen', side_effect=AssertionError('no download')), \
             patch.object(launch, 'skins_gamedata_override', side_effect=AssertionError('no cache')), \
             patch.object(launch, 'skins_plugin_src', side_effect=AssertionError('no source')):
            result = launch.update_skins_gamedata()
            self.assertFalse(result['ok'])
            self.assertEqual('external', result['status'])
            self.assertEqual(0, launch._copy_skins_into(self.game))
            launch.write_invsim_cfg(self.game, self.career.steam_id)
        self.assertFalse(launch.skins_wanted(self.career))
        self.assert_external_untouched()

    def test_equipping_and_sync_preserve_both_inventory_sources(self):
        before = deepcopy(self.career.__dict__)
        with patch.object(skins, 'write_inventories', side_effect=AssertionError('no inventory write')), \
             patch.object(skins, 'write_owner_steamid', side_effect=AssertionError('no owner write')), \
             patch.object(launch, 'write_invsim_cfg', side_effect=AssertionError('no cfg write')):
            skins.sync_live(self.career)
        self.assertEqual(before, self.career.__dict__)
        self.assert_external_untouched()

    def test_career_sync_keeps_legacy_export_and_cfg_behavior(self):
        self.cfg['skins_inventory_mode'] = 'career'
        self.career.inventory = []
        self.career.equipped_ct = {}
        self.career.equipped_t = {}
        skins.sync_live(self.career)
        path = self.game / 'addons/counterstrikesharp/configs/plugins/InventorySimulator/inventories.json'
        self.assertIn(self.career.steam_id, json.loads(path.read_text()))
        self.assertIn(b'invsim_file "', (self.game / 'cfg/invsim_career.cfg').read_bytes())
        self.assertIn(b'exec invsim_career.cfg', (self.game / 'cfg/server.cfg').read_bytes())

    def test_career_install_and_disable_still_use_existing_branches(self):
        self.cfg['skins_inventory_mode'] = 'career'
        with patch.object(launch, '_copy_skins_into', return_value=7) as copy, \
             patch.object(launch, '_remove_plugin') as disable, \
             patch.object(launch, 'restore_bot_randomizer', return_value=2):
            self.assertEqual(9, launch.install_skins_plugin(self.game, self.career))
            copy.assert_called_once_with(self.game)
            disable.assert_not_called()
            self.career.real_skins = False
            self.assertEqual(2, launch.install_skins_plugin(self.game, self.career))
            self.assertEqual(['InventorySimulator', 'InvsimCareer'], [call.args[1] for call in disable.call_args_list])

    def test_install_mod_preserves_external_files_and_shared_player_cfgs(self):
        for rel in self.external:
            target = self.mod / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'template would clobber external')
        shared = self.game / 'cfg/gamemode_competitive.cfg'
        shared.write_bytes(b'invsim_url "https://player.test"\ninvsim_file "player.json"\n')
        (self.mod / 'cfg/gamemode_competitive.cfg').write_bytes(b'default template')
        new = self.mod / 'cfg/custom-skins.cfg'
        new.write_bytes(b'invsim_url "https://unwanted-template.test"\n')
        with patch.object(launch, '_copy_career_match', return_value=0), \
             patch.object(launch, '_deploy_tactical_playbook', return_value=0), \
             patch.object(launch, '_copy_botbuy_patch', return_value=0), \
             patch.object(launch, 'apply_bothider_config'):
            self.assertTrue(launch.install_mod(self.game, self.mod)['ok'])
        self.assertIn(b'invsim_url "https://player.test"', shared.read_bytes())
        self.assertIn(b'invsim_file "player.json"', shared.read_bytes())
        self.assertFalse((self.game / 'cfg/custom-skins.cfg').exists())
        self.assert_external_untouched()

    def test_prepare_external_never_syncs_and_does_not_swallow_retirement_failure(self):
        from test_v15_core import fake_team
        request = launch.build_request(fake_team('A', 85), fake_team('B', 80), 'A0', 'de_dust2', 'ct')
        self.bridge()
        contexts = (
            patch.object(launch, '_copy_career_match', return_value=0),
            patch.object(launch, '_deploy_tactical_playbook', return_value=0),
            patch.object(launch, '_copy_botbuy_patch', return_value=0),
            patch.object(launch, 'install_match_avatars'),
            patch.object(launch, 'generate_match_vpk', return_value={'manifest_hash': 'fixture', 'count': 9}),
            patch.object(launch, 'install_match_identities'),
            patch.object(launch, 'restore_bot_randomizer', return_value=0),
            patch.object(launch, 'apply_bothider_config'),
            patch.object(skins, 'sync_live', side_effect=AssertionError('must not sync')),
        )
        for context in contexts:
            context.start()
            self.addCleanup(context.stop)
        with patch.object(launch, '_prepare_external_skins', side_effect=PermissionError('bridge locked')):
            # Legacy callers may omit the new setting from opts. The actual
            # installed provider, not defaulted old opts, governs error handling.
            for opts in (self.cfg, None, {'difficulty': 'Medium'}):
                with self.subTest(opts=opts), self.assertRaisesRegex(PermissionError, 'bridge locked'):
                    launch.prepare_game(self.game, self.mod, deepcopy(request), opts, career=self.career)
        self.assertFalse((launch.plugin_dir(self.game) / 'match_request.json').exists())
        launch.prepare_game(self.game, self.mod, request, self.cfg, career=self.career)
        self.assertFalse((launch._plugin_live(self.game, 'InvsimCareer') / 'InvsimCareer.dll').exists())
        self.assert_external_untouched()

    def test_status_uses_installed_external_plugin_not_bundled_source_and_is_read_only(self):
        with patch.object(launch, 'skins_plugin_src', side_effect=AssertionError('not external source')), \
             patch.object(launch, 'game_levels_ok', return_value=True), \
             patch.object(launch, 'active_manifest', return_value={}), \
             patch.object(launch, 'live_cs2_pids', return_value=[]):
            status = launch.status()
        self.assertTrue(status['skins_ok'])
        self.assertEqual('external', status['skin_integration']['inventory_mode'])
        self.assertFalse((self.root / 'save/skins_gamedata').exists())
        self.assert_external_untouched()


if __name__ == '__main__':
    unittest.main()
