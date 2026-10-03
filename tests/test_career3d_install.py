"""Setup tests use only synthetic E: QA files, never the player's game files."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
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
        self.runtime_prepare = self.start(patch('tools.career3d_runtime_compat.prepare_runtime',
            side_effect=lambda root, mod, game: {'mod_dir':str(mod), 'origin_mod_dir':str(mod),
                'revision':'fixture-compatible-1', 'components':{'fixture':'1'}}))
        self.original_install = launch.install_mod
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
        self.assertEqual(install.setup_context(), {'available':True, 'external_available':True, 'name':install.NAME})
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
            self.assertEqual(install.auto_prepare_config(), {'available':False, 'external_available':True, 'name':install.NAME})
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
        self.runtime_prepare.assert_not_called()
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

    def external_source(self):
        mod = self.root / '用户下载/Bot Improver 发行包'
        for relative in ('addons/metamod', 'addons/counterstrikesharp', 'overrides'):
            (mod / relative).mkdir(parents=True)
        (mod / 'addons/metamod/runtime.dll').write_bytes(b'user-selected runtime')
        self.launch._write_settings({**self.cfg, 'mod_source_path':str(mod)})
        return mod

    def test_external_available_in_ordinary_package_without_startup_discovery(self):
        with patch.dict(os.environ, {install.ENV_MOD:''}), patch.object(install.sys, 'frozen', False, create=True), \
                patch.object(self.activities, 'read_cs2_config', side_effect=AssertionError('no settings polling')):
            self.assertEqual(install.setup_context(), {'available':False, 'external_available':True, 'name':install.NAME})
        self.running.assert_not_called()
        self.mod_install.assert_not_called()

    def test_external_install_uses_only_saved_release_and_keeps_settings_and_career(self):
        mod = self.external_source()
        cfg_before = self.launch.SETTINGS_PATH.read_bytes()
        career_before = deepcopy(self.state.career.incident_state)
        with patch.object(install, 'bundle_root', return_value=self.mod.resolve()):
            result = install.install_bundle(self.state, {**self.body, 'source':'external'})
        self.mod_install.assert_called_once_with(self.game.resolve(), mod.resolve())
        self.assertEqual(result['source'], 'external')
        self.assertIn('设置中的人机增强', result['reason'])
        self.assertEqual(self.launch.SETTINGS_PATH.read_bytes(), cfg_before)
        self.assertEqual(self.state.career.incident_state, career_before)

    def test_external_install_accepts_quoted_path_with_spaces_and_chinese(self):
        mod = self.external_source()
        self.launch._write_settings({**self.cfg, 'mod_source_path':' "' + str(mod) + '" '})
        result = install.install_bundle(self.state, {**self.body, 'source':'external'})
        self.assertEqual(result['source'], 'external')
        self.mod_install.assert_called_once_with(self.game.resolve(), mod.resolve())

    def test_external_install_rejects_missing_relative_and_wrong_directory_levels(self):
        mod = self.external_source()
        for raw in ('', '.', 'relative/mod', str(self.root / 'missing'), str(mod / 'addons'), str(mod.parent)):
            with self.subTest(path=raw):
                self.launch._write_settings({**self.cfg, 'mod_source_path':raw})
                with self.assertRaises((ValueError, FileNotFoundError)):
                    install.install_bundle(self.state, {**self.body, 'source':'external'})
        self.running.assert_not_called()
        self.mod_install.assert_not_called()
        self.assertFalse((self.data / 'install-backups').exists())

    def test_external_install_does_not_fall_back_to_valid_bundled_runtime(self):
        self.launch._write_settings({**self.cfg, 'mod_source_path':str(self.root / 'missing')})
        self.assertIsNotNone(install.bundle_root())
        with self.assertRaisesRegex(FileNotFoundError, '找不到设置中的'):
            install.install_bundle(self.state, {**self.body, 'source':'external'})
        self.mod_install.assert_not_called()

    def test_install_source_must_be_recognized_and_confirmation_explicit(self):
        for body in ({'revision':7, 'source':'external'}, {**self.body, 'source':'unknown'},
                     {**self.body, 'source':None}, {**self.body, 'source':[]},
                     {'revision':6, 'confirm':True, 'source':'external'}):
            with self.subTest(body=body), self.assertRaises(ValueError):
                install.install_bundle(self.state, body)
        self.running.assert_not_called()
        self.mod_install.assert_not_called()

    def test_external_install_rejects_reparse_roots_required_folders_and_files(self):
        mod = self.external_source()
        original = install._is_reparse
        for marked in (mod, mod / 'overrides', mod / 'addons/metamod/runtime.dll'):
            with self.subTest(path=marked), \
                    patch.object(install, '_is_reparse', side_effect=lambda path: path == marked or original(path)):
                with self.assertRaisesRegex(ValueError, '目录链接'):
                    install.install_bundle(self.state, {**self.body, 'source':'external'})
        self.mod_install.assert_not_called()

    def test_external_install_rejects_source_game_overlap_before_backup(self):
        for relative in ('addons/metamod', 'addons/counterstrikesharp', 'overrides'):
            (self.game / relative).mkdir(parents=True, exist_ok=True)
        self.launch._write_settings({**self.cfg, 'mod_source_path':str(self.game)})
        with self.assertRaisesRegex(ValueError, '重叠'):
            install.install_bundle(self.state, {**self.body, 'source':'external'})
        self.running.assert_not_called()
        self.mod_install.assert_not_called()

    def test_external_install_uses_same_game_closed_and_backup_guards(self):
        self.external_source()
        self.running.return_value = True
        with self.assertRaisesRegex(ValueError, '完全退出'):
            install.install_bundle(self.state, {**self.body, 'source':'external'})
        self.mod_install.assert_not_called()
        self.runtime_prepare.assert_not_called()
        self.assertFalse((self.data / 'install-backups').exists())
        self.running.return_value = False
        self.running.side_effect = [False, True]
        with self.assertRaisesRegex(RuntimeError, '安装前备份保留在'):
            install.install_bundle(self.state, {**self.body, 'source':'external'})
        self.mod_install.assert_not_called()
        manifests = list((self.data / 'install-backups').glob('*/BACKUP_MANIFEST.json'))
        self.assertEqual(len(manifests), 1)
        self.assertEqual(json.loads(manifests[0].read_text('utf-8'))['status'], 'failed')

    def test_external_install_deploys_our_match_and_buy_components_in_mock_game(self):
        mod = self.external_source()
        (mod / 'addons/BotHider').mkdir()
        (mod / 'addons/BotHider/runtime.dll').write_bytes(b'fixture BotHider')
        vendor = self.root / 'fixture-vendor'
        for name in ('CareerMatch', 'BotBuy'):
            folder = vendor / name
            folder.mkdir(parents=True)
            (folder / (name + '.dll')).write_bytes(('fixture ' + name).encode('ascii'))
            (folder / (name + '.deps.json')).write_text('{}', 'utf-8')
        from cs2career import tactics
        self.mod_install.side_effect = self.original_install
        with patch.object(self.launch, 'vendor_root', return_value=vendor), \
                patch.object(self.launch, 'ensure_gameinfo_mounts'), \
                patch.object(tactics, 'load_library', return_value={}), \
                patch.object(self.launch, '_deploy_tactical_playbook', return_value=0):
            result = install.install_bundle(self.state, {**self.body, 'source':'external'})
        self.assertTrue(self.game.is_relative_to(QA_ROOT.resolve()))
        self.assertEqual((self.game / 'addons/metamod/runtime.dll').read_bytes(), b'user-selected runtime')
        for name in ('CareerMatch', 'BotBuy'):
            folder = self.game / 'addons/counterstrikesharp/plugins' / name
            self.assertEqual((folder / (name + '.dll')).read_bytes(), ('fixture ' + name).encode('ascii'))
            self.assertEqual((folder / (name + '.deps.json')).read_text('utf-8'), '{}')
        self.assertTrue(self.launch.mod_installed(self.game))
        self.assertEqual(json.loads((Path(result['backup_path']) / 'BACKUP_MANIFEST.json').read_text('utf-8'))['status'], 'installed')

    def test_compatible_cache_is_installed_and_persisted_without_downgrading_origin(self):
        mod = self.external_source()
        native = mod / 'addons/BotController/bin/win64/BotController.dll'
        native.parent.mkdir(parents=True)
        native.write_bytes(b'old incompatible source DLL')
        origin_files = {file.relative_to(mod).as_posix():file.read_bytes()
                        for file in mod.rglob('*') if file.is_file()}
        cache = self.data / 'runtime-cache/fixture-compatible/mod'

        def prepare(root, source, game):
            self.assertEqual(root, self.data.resolve())
            self.assertEqual(source, mod.resolve())
            self.assertEqual(game, self.game.resolve())
            self.assertFalse((self.data / 'install-backups').exists())
            self.running.assert_called_once_with()
            shutil.copytree(source, cache)
            (cache / native.relative_to(mod)).write_bytes(b'new compatible DLL')
            return {'mod_dir':str(cache), 'origin_mod_dir':str(mod),
                    'revision':'fixture-compatible-2', 'components':{'BotController':'fixture-2'}}

        def copy_compatible(game, source):
            self.assertEqual(source, cache.resolve())
            self.assertEqual(self.launch.settings()['mod_source_path'], str(cache.resolve()))
            destination = game / native.relative_to(mod)
            destination.parent.mkdir(parents=True)
            shutil.copy2(source / native.relative_to(mod), destination)
            return {'ok':True, 'files':1}

        self.runtime_prepare.side_effect = prepare
        self.mod_install.side_effect = copy_compatible
        result = install.install_bundle(self.state, {**self.body, 'source':'external'})
        self.assertEqual((self.game / native.relative_to(mod)).read_bytes(), b'new compatible DLL')
        self.assertEqual(self.activities.read_cs2_config()['mod_source_path'], str(cache.resolve()))
        self.assertEqual(origin_files, {file.relative_to(mod).as_posix():file.read_bytes()
                                      for file in mod.rglob('*') if file.is_file()})
        manifest = json.loads((Path(result['backup_path']) / 'BACKUP_MANIFEST.json').read_text('utf-8'))
        self.assertEqual(manifest['runtime'], result['runtime'])
        self.assertEqual(manifest['runtime']['origin_source'], str(mod.resolve()))
        self.assertEqual(manifest['runtime']['effective_source'], str(cache.resolve()))
        self.assertEqual(manifest['runtime']['compatibility_revision'], 'fixture-compatible-2')
        self.assertEqual(manifest['runtime']['components'], {'BotController':'fixture-2'})

    def test_compatibility_preparation_failure_never_writes_game_settings_or_origin(self):
        mod = self.external_source()
        before_config = self.launch.SETTINGS_PATH.read_bytes()
        game_files = {file.relative_to(self.game).as_posix():file.read_bytes()
                      for file in self.game.rglob('*') if file.is_file()}
        origin_files = {file.relative_to(mod).as_posix():file.read_bytes()
                        for file in mod.rglob('*') if file.is_file()}
        self.runtime_prepare.side_effect = ValueError('fixture compatible download could not be verified')
        with self.assertRaisesRegex(ValueError, 'could not be verified'):
            install.install_bundle(self.state, {**self.body, 'source':'external'})
        self.runtime_prepare.assert_called_once_with(self.data.resolve(), mod.resolve(), self.game.resolve())
        self.mod_install.assert_not_called()
        self.skin_install.assert_not_called()
        self.assertFalse((self.data / 'install-backups').exists())
        self.assertEqual(before_config, self.launch.SETTINGS_PATH.read_bytes())
        self.assertEqual(game_files, {file.relative_to(self.game).as_posix():file.read_bytes()
                                    for file in self.game.rglob('*') if file.is_file()})
        self.assertEqual(origin_files, {file.relative_to(mod).as_posix():file.read_bytes()
                                      for file in mod.rglob('*') if file.is_file()})

    def test_failed_install_never_changes_saved_source_to_unused_cache(self):
        mod = self.external_source()
        cache = self.data / 'runtime-cache/fixture-compatible/mod'
        shutil.copytree(mod, cache)
        before_config = self.launch.SETTINGS_PATH.read_bytes()
        self.runtime_prepare.return_value = {'mod_dir':str(cache), 'origin_mod_dir':str(mod),
            'revision':'fixture-compatible-2', 'components':{'fixture':'2'}}
        self.runtime_prepare.side_effect = None
        self.mod_install.return_value = {'ok':False, 'msg':'fixture installer declined before copying'}
        with self.assertRaisesRegex(RuntimeError, 'installer declined'):
            install.install_bundle(self.state, {**self.body, 'source':'external'})
        self.mod_install.assert_called_once_with(self.game.resolve(), cache.resolve())
        self.assertEqual(before_config, self.launch.SETTINGS_PATH.read_bytes())
        self.assertEqual((mod / 'addons/metamod/runtime.dll').read_bytes(), b'user-selected runtime')
        self.assertFalse((self.game / 'addons').exists())
        manifests = list((self.data / 'install-backups').glob('*/BACKUP_MANIFEST.json'))
        self.assertEqual(len(manifests), 1)
        self.assertEqual(json.loads(manifests[0].read_text('utf-8'))['status'], 'failed')


    def test_snapshot_includes_dotnet_host_but_not_desktop_apps(self):
        host = self.mod / 'addons/counterstrikesharp/dotnet/dotnet.exe'
        host.parent.mkdir(parents=True)
        host.write_bytes(b'fixture .NET host')
        (self.mod / 'Panel.exe').write_bytes(b'fixture upstream UI')
        targets = install._snapshot_targets(self.game, self.mod, self.cfg, False)
        self.assertIn(self.game / host.relative_to(self.mod), targets)
        self.assertNotIn(self.game / 'Panel.exe', targets)


if __name__ == '__main__':
    unittest.main()
