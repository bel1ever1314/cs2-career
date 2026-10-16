"""Synthetic games only: offline, post-intent auto deployment and UI status."""
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import json
import shutil
import unittest

from cs2career.cs2 import launch, runtime_compat
from cs2career.services import activities, bundled_launch, installation, matches


class BundledLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix='career-auto-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / 'game/csgo'
        self.game.mkdir(parents=True)
        (self.game / 'gameinfo.gi').write_text('fixture', encoding='utf-8')
        self.mod = self.root / 'mod'
        self.mod.mkdir()
        self.vendor = self.root / 'vendor'
        for name in ('CareerMatch', 'BotBuy', 'BotAimImprover'):
            target = self.vendor / name
            target.mkdir(parents=True)
            (target / (name + '.dll')).write_bytes(('new ' + name).encode())
            (target / (name + '.deps.json')).write_text('{}')
        self.relative = 'addons/metamod/runtime.dll'
        file = self.mod / self.relative
        file.parent.mkdir(parents=True)
        file.write_bytes(b'runtime')
        self.receipt = {'files': {self.relative: hashlib.sha256(b'runtime').hexdigest()}}
        self.cfg = dict(launch.DEFAULTS, csgo_path=str(self.game), steam_exe=str(self.root / 'steam.exe'))
        (self.root / 'steam.exe').write_bytes(b'steam')
        self.stack = self.enterContext(ExitStack())
        self.stack.enter_context(patch.object(installation, 'bundle_root', return_value=self.mod))
        self.stack.enter_context(patch.object(launch, 'vendor_root', return_value=self.vendor))
        self.stack.enter_context(patch.object(launch, 'require_installation_files'))
        self.closed = self.stack.enter_context(patch.object(launch, 'require_cs2_closed'))
        self.stack.enter_context(patch.object(runtime_compat, 'validate_bundled_runtime', return_value=self.receipt))
        self.stack.enter_context(patch.object(installation, '_isolated_root', return_value=self.root))
        self.seed = self.stack.enter_context(patch.object(runtime_compat, 'seed_bundled_runtime', return_value=self.mod))
        self.prepare = self.stack.enter_context(patch.object(runtime_compat, 'prepare_runtime',
            return_value={'mod_dir': str(self.mod), 'revision': 'test', 'components': []}))
        self.backup = self.root / 'backup'
        self.backup.mkdir()
        self.stack.enter_context(patch.object(installation, '_snapshot_targets', return_value=[]))
        self.snapshot = self.stack.enter_context(patch.object(installation, '_snapshot',
            return_value=(self.backup, {'status': 'prepared'})))
        self.switch = self.stack.enter_context(patch('cs2career.cs2.environment.switch_environment'))
        self.installer = self.stack.enter_context(patch.object(launch, 'install_mod', side_effect=self.install))

    def install(self, game, mod, config):
        dest = game / self.relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mod / self.relative, dest)
        for name in ('CareerMatch', 'BotBuy', 'BotAimImprover'):
            shutil.copytree(self.vendor / name, game / 'addons/counterstrikesharp/plugins' / name, dirs_exist_ok=True)
        return {'ok': True}

    def test_first_launch_prepares_offline_then_reuses_files(self):
        cfg = bundled_launch.prepare(self.cfg)
        self.assertEqual(str(self.mod), cfg['mod_source_path'])
        self.prepare.assert_called_once_with(self.root, self.mod, self.game, allow_download=False)
        self.assertEqual('installed', json.loads((self.backup / 'BACKUP_MANIFEST.json').read_text())['status'])
        bundled_launch.prepare(self.cfg)
        self.assertEqual(1, self.installer.call_count)
        self.assertEqual(1, self.snapshot.call_count)

    def test_running_cs2_and_broken_bundle_never_install(self):
        self.closed.side_effect = ValueError('running')
        with self.assertRaisesRegex(ValueError, 'running'):
            bundled_launch.prepare(self.cfg)
        self.installer.assert_not_called()
        self.closed.side_effect = None
        with patch.object(runtime_compat, 'validate_bundled_runtime', return_value=None):
            with self.assertRaisesRegex(ValueError, '校验清单'):
                bundled_launch.prepare(self.cfg)
        self.installer.assert_not_called()

    def test_failed_install_is_not_reported_as_ready_and_keeps_backup(self):
        self.installer.side_effect = RuntimeError('locked file')
        with self.assertRaisesRegex(RuntimeError, 'locked file'):
            bundled_launch.prepare(self.cfg)
        self.assertEqual('failed', json.loads((self.backup / 'BACKUP_MANIFEST.json').read_text())['status'])

    def test_status_can_offer_launch_but_never_installs(self):
        with patch.object(activities, 'read_cs2_config', return_value=self.cfg):
            status = activities.config_status()
        self.assertTrue(status['ready'])
        self.assertTrue(status['auto_prepare'])
        self.assertFalse(status['installed_ready'])
        self.assertNotIn('点击“安装', status['reason'])
        self.assertTrue(all('点击“安装' not in error for error in status['component_errors']))
        self.installer.assert_not_called()
        self.closed.assert_not_called()

    def test_dispatch_prepares_before_starting_game(self):
        with patch.object(launch, 'start_match', return_value='started') as start:
            self.assertEqual('started', matches._dispatch_launch(self.cfg, [], {}))
        self.installer.assert_called_once()
        self.assertEqual(str(self.mod), start.call_args.kwargs['config']['mod_source_path'])

    def test_normal_edition_does_not_change_install_workflow(self):
        with patch.object(installation, 'bundle_root', return_value=None):
            self.assertIs(self.cfg, bundled_launch.prepare(self.cfg))
        self.installer.assert_not_called()

    def test_plugin_copy_invalidates_preinstall_result(self):
        with patch.object(launch._matching_plugin_bytes, 'cache_clear') as clear:
            launch._copy_verified_plugin(self.vendor / 'CareerMatch', self.root / 'fake-plugin', 'CareerMatch')
        clear.assert_called_once()


if __name__ == '__main__':
    unittest.main()
