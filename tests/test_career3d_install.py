"""Bundled setup tests use only synthetic E: QA files and mocked installers."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import career3d_install as install


QA_ROOT = Path('E:/CS2CareerTools/Career3DInstallerChecks-20261002/qa')


class BundledInstallTests(unittest.TestCase):
    def setUp(self):
        QA_ROOT.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='bundled-', dir=QA_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.mod = self.root / 'tester/mod'
        for name in ('addons/metamod', 'addons/counterstrikesharp', 'overrides'):
            (self.mod / name).mkdir(parents=True)
        self.source = self.mod / 'addons/metamod/runtime.dll'
        self.source.write_bytes(b'fixture new runtime')
        self.game = self.root / 'fixture-steam/game/csgo'
        self.game.mkdir(parents=True)
        (self.game / 'gameinfo.gi').write_bytes(b'fixture gameinfo before')
        (self.game / 'gameinfo_branchspecific.gi').write_bytes(b'fixture branch before')
        self.data = self.root / 'tester/game/runtime/career'
        self.save = self.data / 'save'
        self.save.mkdir(parents=True)
        (self.data / '.career3d-demo.json').write_text(json.dumps({'kind':'cs2career-godot-demo'}), 'utf-8')
        self.env = self.start(patch.dict(os.environ, {'CS2CAREER_SAVE_DIR':str(self.save),
            'CS2CAREER_EXTENSION_DIR':str(self.data / 'extensions'), install.ENV_MOD:str(self.mod)}))
        from cs2career.cs2 import launch
        from tools import career3d_activities as activities
        self.launch, self.activities = launch, activities
        self.start(patch.object(launch, 'SETTINGS_PATH', self.save / 'cs2.json'))
        self.cfg = {**launch.DEFAULTS, 'csgo_path':str(self.game), 'mod_source_path':str(self.mod)}
        launch._write_settings(self.cfg)
        self.state = SimpleNamespace(career=SimpleNamespace(
            incident_state={'career3d_service':{'revision':7}}, training_session=None, real_skins=False),
            arena=SimpleNamespace(pending=None), season=SimpleNamespace(events=[]))
        self.running = self.start(patch.object(activities, '_running_cs2', return_value=False))
        self.mod_install = self.start(patch.object(launch, 'install_mod', return_value={'ok':True, 'files':2}))
        self.skin_install = self.start(patch.object(launch, 'install_skins_mod', return_value={'ok':True, 'files':3}))
        self.start(patch.object(launch, 'find_mod_source', side_effect=AssertionError('no source search')))
        self.start(patch('subprocess.Popen', side_effect=AssertionError('no process launch')))
        self.body = {'revision':7, 'confirm':True}

    def start(self, context):
        result = context.start()
        self.addCleanup(context.stop)
        return result

    def write(self, relative, blob=b'fixture old'):
        target = self.game / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        return target

    def test_discovery_only_uses_explicit_or_frozen_sibling(self):
        self.assertEqual(install.bundle_root(), self.mod.resolve())
        self.assertEqual(install.setup_context(), {'available':True, 'name':install.NAME})
        self.running.assert_not_called()
        with patch.dict(os.environ, {install.ENV_MOD:''}), patch.object(install.sys, 'frozen', False, create=True):
            self.assertIsNone(install.bundle_root())
        with patch.dict(os.environ, {install.ENV_MOD:''}), patch.object(install.sys, 'frozen', True, create=True), \
                patch.object(install.sys, 'executable', str(self.root / 'tester/backend/CareerBackend.exe')):
            self.assertEqual(install.bundle_root(), self.mod.resolve())
        with patch.dict(os.environ, {install.ENV_MOD:'missing'}):
            self.assertIsNone(install.bundle_root())

    def test_prepare_only_fills_isolated_config_and_never_checks_processes(self):
        steam = self.root / 'fixture-steam/steam.exe'
        steam.write_bytes(b'fixture Steam')
        self.launch._write_settings({**self.cfg, 'steam_exe':'missing', 'csgo_path':'missing', 'mod_source_path':''})
        before = (self.game / 'gameinfo.gi').read_bytes()
        with patch.object(self.launch, 'find_steam_exe', return_value=str(steam)), \
                patch.object(self.launch, 'find_csgo_path', return_value=str(self.game)):
            self.assertTrue(install.auto_prepare_config()['prepared'])
        cfg = self.activities.read_cs2_config()
        self.assertEqual(cfg['steam_exe'], str(steam.resolve()))
        self.assertEqual(cfg['csgo_path'], str(self.game.resolve()))
        self.assertEqual(cfg['mod_source_path'], str(self.mod.resolve()))
        self.assertEqual((self.game / 'gameinfo.gi').read_bytes(), before)
        self.running.assert_not_called()
        self.mod_install.assert_not_called()
        self.skin_install.assert_not_called()

    def test_prepare_preserves_valid_user_paths_and_preferences(self):
        steam = self.root / 'other-steam.exe'
        steam.write_bytes(b'fixture Steam')
        cfg = {**self.cfg, 'steam_exe':str(steam), 'difficulty':'High', 'skins_inventory_mode':'external'}
        self.launch._write_settings(cfg)
        with patch.object(self.launch, 'find_steam_exe', side_effect=AssertionError('valid Steam path')), \
                patch.object(self.launch, 'find_csgo_path', side_effect=AssertionError('valid CS2 path')):
            self.assertFalse(install.auto_prepare_config()['prepared'])
        self.assertEqual(self.activities.read_cs2_config(), cfg)

    def test_prepare_requires_demo_isolation(self):
        (self.data / '.career3d-demo.json').unlink()
        with self.assertRaisesRegex(ValueError, '隔离标记'):
            install.auto_prepare_config()
        self.mod_install.assert_not_called()
        self.running.assert_not_called()

    def test_ordinary_release_does_not_discover_or_prepare_paths(self):
        with patch.dict(os.environ, {install.ENV_MOD:''}), patch.object(install.sys, 'frozen', False, create=True), \
                patch.object(self.launch, 'find_steam_exe', side_effect=AssertionError('no startup discovery')), \
                patch.object(self.launch, '_write_settings', side_effect=AssertionError('no startup writes')):
            self.assertEqual(install.auto_prepare_config(), {'available':False, 'name':install.NAME})
        self.running.assert_not_called()

    def test_install_requires_confirmation_and_current_revision(self):
        for body in ({'revision':7}, {'revision':7, 'confirm':'true'}, {'revision':6, 'confirm':True},
                     {'revision':True, 'confirm':True}):
            with self.subTest(body=body), self.assertRaises(ValueError):
                install.install_bundle(self.state, body)
        self.running.assert_not_called()
        self.mod_install.assert_not_called()
        self.assertFalse((self.data / 'install-backups').exists())

    def test_pending_training_ladder_cs2_rts_and_recovery_block_install(self):
        cases = [('training', None), ('arena', None), ('cs2', None), ('rts', None),
                 ('recovery', 'manual-load.pending.json'), ('recovery', 'personal-transfer.pending.json')]
        for kind, marker in cases:
            with self.subTest(kind=kind, marker=marker):
                self.state.career.training_session = {'nonce':'fixture'} if kind == 'training' else None
                self.state.arena.pending = {'phase':'rts'} if kind == 'arena' else None
                self.state.season.events = [{'matches':[{'played':False, 'cs2_session':{'nonce':'fixture'}}]}] if kind == 'cs2' else \
                    [{'matches':[{'played':False, 'career3d_rts':{'nonce':'fixture'}}]}] if kind == 'rts' else []
                if marker: (self.save / marker).write_text('{}', 'utf-8')
                with self.assertRaises(ValueError):
                    install.install_bundle(self.state, self.body)
                if marker: (self.save / marker).unlink()
        self.running.assert_not_called()
        self.mod_install.assert_not_called()

    def test_running_game_and_unverifiable_process_state_fail_closed(self):
        self.running.return_value = True
        with self.assertRaisesRegex(ValueError, '完全退出'):
            install.install_bundle(self.state, self.body)
        self.running.return_value = False
        self.running.side_effect = RuntimeError('fixture process query failed')
        with self.assertRaisesRegex(RuntimeError, 'process query failed'):
            install.install_bundle(self.state, self.body)
        self.mod_install.assert_not_called()
        self.assertFalse((self.data / 'install-backups').exists())

    def test_invalid_selected_game_never_calls_installer(self):
        self.launch._write_settings({**self.cfg, 'csgo_path':str(self.root)})
        with self.assertRaisesRegex(ValueError, 'CS2 目录无效'):
            install.install_bundle(self.state, self.body)
        self.mod_install.assert_not_called()
        self.running.assert_not_called()

    def test_every_existing_overwrite_is_backed_up_before_mock_install(self):
        runtime = self.write('addons/metamod/runtime.dll', b'old runtime')
        hook = self.write('cfg/gamemode_competitive.cfg', b'old hook')
        career = self.write('addons/counterstrikesharp/plugins/CareerMatch/CareerMatch.dll', b'old match')
        bothider = self.write('addons/BotHider/config.json', b'old bothider')
        branch = self.game / 'gameinfo_branchspecific.gi'
        originals = {file.relative_to(self.game).as_posix():file.read_bytes() for file in
                     (runtime, hook, career, bothider, branch, self.game / 'gameinfo.gi')}

        def mock_install(game, mod):
            self.assertEqual(game, self.game.resolve())
            self.assertEqual(mod, self.mod.resolve())
            self.assertTrue(game.is_relative_to(QA_ROOT.resolve()))
            backups = list((self.data / 'install-backups').glob('*/BACKUP_MANIFEST.json'))
            self.assertEqual(len(backups), 1)
            backup = backups[0].parent
            manifest = json.loads(backups[0].read_text('utf-8'))
            self.assertEqual(manifest['status'], 'prepared')
            for relative, blob in originals.items():
                self.assertEqual((backup / 'files' / relative).read_bytes(), blob)
            runtime.write_bytes(b'new fixture runtime')
            return {'ok':True, 'files':2}

        self.mod_install.side_effect = mock_install
        result = install.install_bundle(self.state, self.body)
        backup = Path(result['backup_path'])
        self.assertTrue(backup.is_relative_to(self.data))
        self.assertEqual(json.loads((backup / 'BACKUP_MANIFEST.json').read_text('utf-8'))['status'], 'installed')
        self.assertEqual((backup / 'files/addons/metamod/runtime.dll').read_bytes(), b'old runtime')
        self.assertEqual(self.state.career.incident_state['career3d_service']['revision'], 7)
        self.skin_install.assert_not_called()

    def test_backup_failure_never_calls_installer(self):
        self.write('addons/metamod/runtime.dll')
        with patch.object(install.shutil, 'copy2', side_effect=OSError('fixture backup failed')):
            with self.assertRaisesRegex(OSError, 'backup failed'):
                install.install_bundle(self.state, self.body)
        self.mod_install.assert_not_called()

    def test_installer_failure_retains_named_backup(self):
        self.mod_install.side_effect = OSError('fixture install failed')
        with self.assertRaisesRegex(RuntimeError, '安装前备份保留在'):
            install.install_bundle(self.state, self.body)
        manifests = list((self.data / 'install-backups').glob('*/BACKUP_MANIFEST.json'))
        self.assertEqual(len(manifests), 1)
        self.assertEqual(json.loads(manifests[0].read_text('utf-8'))['status'], 'failed')

    def test_game_started_during_backup_is_blocked_before_install(self):
        self.running.side_effect = [False, True]
        with self.assertRaisesRegex(RuntimeError, '完全退出'):
            install.install_bundle(self.state, self.body)
        self.mod_install.assert_not_called()
        manifests = list((self.data / 'install-backups').glob('*/BACKUP_MANIFEST.json'))
        self.assertEqual(len(manifests), 1)
        self.assertEqual(json.loads(manifests[0].read_text('utf-8'))['status'], 'failed')

    def test_repeated_install_creates_distinct_backups(self):
        first = install.install_bundle(self.state, self.body)
        second = install.install_bundle(self.state, self.body)
        self.assertNotEqual(first['backup_path'], second['backup_path'])

    def test_reparse_in_bundle_or_target_is_rejected_before_installer(self):
        original = install._is_reparse
        with patch.object(install, '_is_reparse', side_effect=lambda path: path == self.source or original(path)):
            with self.assertRaisesRegex(ValueError, '目录链接'):
                install.install_bundle(self.state, self.body)
        destination = self.write('addons/metamod/runtime.dll')
        with patch.object(install, '_is_reparse', side_effect=lambda path: path == destination or original(path)):
            with self.assertRaisesRegex(ValueError, '目录链接'):
                install.install_bundle(self.state, self.body)
        self.mod_install.assert_not_called()

    def test_external_inventory_keeps_user_plugin_and_never_installs_skins(self):
        self.launch._write_settings({**self.cfg, 'skins_inventory_mode':'external'})
        self.state.career.real_skins = True
        external = self.write('addons/counterstrikesharp/plugins/InventorySimulator/InventorySimulator.dll', b'external plugin')
        owner = self.write('addons/counterstrikesharp/configs/plugins/InventorySimulator/owner.txt', b'fixture owner opaque')

        def mock_install(game, mod):
            cfg = self.launch.settings()
            self.assertEqual(cfg['skins_inventory_mode'], 'external')
            self.assertEqual(cfg['mod_source_path'], str(self.mod.resolve()))
            self.assertEqual(external.read_bytes(), b'external plugin')
            self.assertEqual(owner.read_bytes(), b'fixture owner opaque')
            return {'ok':True, 'files':2}

        self.mod_install.side_effect = mock_install
        result = install.install_bundle(self.state, self.body)
        self.assertEqual(result['skin_files'], 0)
        self.skin_install.assert_not_called()

    def test_explicit_career_skins_backup_and_install_bundled_vendor(self):
        self.state.career.real_skins = True
        vendor = self.root / 'tester/backend/_internal/vendor'
        skin = vendor / 'InventorySimulator/plugins/InventorySimulator/InventorySimulator.dll'
        skin.parent.mkdir(parents=True)
        skin.write_bytes(b'fixture bundled skin')
        (vendor / 'InvsimCareer').mkdir()
        (vendor / 'InvsimCareer/InvsimCareer.dll').write_bytes(b'fixture bridge')
        self.write('addons/counterstrikesharp/gamedata/inventory-simulator.previous.json', b'old previous fixture')
        with patch.object(self.launch, 'vendor_root', return_value=vendor):
            result = install.install_bundle(self.state, self.body)
        self.skin_install.assert_called_once_with(self.game.resolve())
        self.assertEqual(result['skin_files'], 3)
        self.assertEqual(result['files'], 5)
        manifest = json.loads((Path(result['backup_path']) / 'BACKUP_MANIFEST.json').read_text('utf-8'))
        self.assertIn('addons/counterstrikesharp/plugins/InventorySimulator/InventorySimulator.dll', manifest['files'])
        self.assertTrue(manifest['files']['addons/counterstrikesharp/gamedata/inventory-simulator.previous.json']['existed'])


if __name__ == '__main__':
    unittest.main()
