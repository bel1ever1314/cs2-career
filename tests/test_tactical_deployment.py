"""Deployment fixtures: no installed game, real EXE, or player data is used."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import install_tactical_commands as deploy


@unittest.skipUnless(Path('D:/CS2CareerBuilds').is_dir(), 'Local installer fixtures require the managed D: build tree')
class TacticalDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='D:/CS2CareerBuilds')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.build = self.root/'build'
        for key, folder in [('ROOT', 'source'), ('GAME', 'game'), ('STAGE', 'stage'), ('RELEASE', 'desktop')]:
            value = self.root/folder
            value.mkdir()
            mock = patch.object(deploy, key, value)
            mock.start(); self.addCleanup(mock.stop)
        self.sources = {}
        for component, folder in [('CareerMatch', 'plugin'), ('BotBuy', 'botbuy')]:
            for suffix in ('.dll', '.deps.json'):
                name = component+suffix
                source = self.build/folder/name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(b'{}' if suffix == '.deps.json' else b'new '+component.encode())
                self.sources[component, suffix] = source
                for destination in (deploy.ROOT/'vendor'/component,
                                    deploy.GAME/'addons/counterstrikesharp/plugins'/component,
                                    deploy.STAGE/'compatible-mod/addons/counterstrikesharp/plugins'/component):
                    destination.mkdir(parents=True, exist_ok=True)
                    (destination/name).write_bytes(b'old '+name.encode())
        source = self.build/'release'/deploy.NAME/(deploy.NAME+'.exe')
        source.parent.mkdir(parents=True); source.write_bytes(b'new exe')
        (deploy.RELEASE/(deploy.NAME+'.exe')).write_bytes(b'old exe')
        for name in ('游戏内指挥说明.txt', '开始游玩-FAQ.txt'):
            (deploy.ROOT/name).write_text('new note', 'utf-8')
            (deploy.RELEASE/name).write_text('old note', 'utf-8')
        save = deploy.RELEASE/'save'; save.mkdir()
        (save/'career.json').write_bytes(b'player career')
        (save/'arena.json').write_bytes(b'player ladder')
        native = deploy.GAME/'addons/BotController/bin/win64/BotController.dll'
        native.parent.mkdir(parents=True); native.write_bytes(b'untouched native')
        self.manifest = deploy.STAGE/'capsule-files.json'
        self.manifest.write_text(json.dumps({'unchanged-native': 'keep',
            'addons/counterstrikesharp/plugins/BotBuy/BotBuy.dll': 'old digest'}), 'utf-8')
        self.smoke = dict(ok=True, career_plugin_sha256=deploy.digest(self.sources['CareerMatch', '.dll']),
                          botbuy_plugin_sha256=deploy.digest(self.sources['BotBuy', '.dll']))
        self.write_smoke()
        self.closed = patch.object(deploy, 'require_closed')
        self.closed_mock = self.closed.start(); self.addCleanup(self.closed.stop)

    def write_smoke(self):
        (self.build/'exe-smoke.json').write_text(json.dumps(self.smoke), 'utf-8')

    def run_deploy(self, bundle=False):
        args = ['install_tactical_commands', '--build', str(self.build), '--with-botbuy']
        if bundle: args.append('--bundle-only')
        with patch('sys.argv', args), redirect_stdout(io.StringIO()):
            deploy.main()

    def test_full_install_verifies_bundle_and_preserves_native_and_player_data(self):
        before = deploy.protected_snapshot()
        self.run_deploy()
        self.assertEqual(before, deploy.protected_snapshot())
        self.assertEqual(b'new exe', (deploy.RELEASE/(deploy.NAME+'.exe')).read_bytes())
        for component in ('CareerMatch', 'BotBuy'):
            target = deploy.GAME/'addons/counterstrikesharp/plugins'/component/(component+'.dll')
            self.assertEqual(deploy.digest(self.sources[component, '.dll']), deploy.digest(target))
        manifest = json.loads(self.manifest.read_text())
        self.assertEqual('keep', manifest['unchanged-native'])
        self.assertEqual(deploy.digest(self.sources['BotBuy', '.dll']),
                         manifest['addons/counterstrikesharp/plugins/BotBuy/BotBuy.dll'])
        self.assertEqual(2, self.closed_mock.call_count)

    def test_bundle_only_does_not_touch_game_or_desktop_or_capsule_manifest(self):
        before = {str(p): p.read_bytes() for area in (deploy.GAME, deploy.RELEASE, deploy.STAGE)
                  for p in area.rglob('*') if p.is_file()}
        self.run_deploy(bundle=True)
        self.assertEqual(before, {str(p): p.read_bytes() for area in (deploy.GAME, deploy.RELEASE, deploy.STAGE)
                                 for p in area.rglob('*') if p.is_file()})
        self.closed_mock.assert_not_called()

    def test_wrong_bundled_botbuy_or_open_game_prevents_install(self):
        before = (deploy.RELEASE/(deploy.NAME+'.exe')).read_bytes()
        self.smoke['botbuy_plugin_sha256'] = 'not the reviewed plugin'; self.write_smoke()
        with self.assertRaisesRegex(RuntimeError, 'different BotBuy'): self.run_deploy()
        self.assertFalse((self.build/'backup').exists())
        self.smoke['botbuy_plugin_sha256'] = deploy.digest(self.sources['BotBuy', '.dll']); self.write_smoke()
        self.closed_mock.side_effect = RuntimeError('Close CS2')
        with self.assertRaisesRegex(RuntimeError, 'Close CS2'): self.run_deploy()
        self.assertEqual(before, (deploy.RELEASE/(deploy.NAME+'.exe')).read_bytes())
        self.assertFalse((self.build/'backup').exists())

    def test_partial_update_failure_restores_all_previous_files(self):
        before = {str(p): p.read_bytes() for area in (deploy.ROOT, deploy.GAME, deploy.RELEASE, deploy.STAGE)
                  for p in area.rglob('*') if p.is_file()}
        original_copy = deploy.atomic_copy
        def fail_botbuy(source, target):
            if source == self.sources['BotBuy', '.dll'] and target.is_relative_to(deploy.GAME):
                raise OSError('simulated locked plugin')
            original_copy(source, target)
        with patch.object(deploy, 'atomic_copy', side_effect=fail_botbuy):
            with self.assertRaisesRegex(OSError, 'locked plugin'): self.run_deploy()
        self.assertEqual(before, {str(p): p.read_bytes() for area in (deploy.ROOT, deploy.GAME, deploy.RELEASE, deploy.STAGE)
                                 for p in area.rglob('*') if p.is_file()})


if __name__ == '__main__': unittest.main()
