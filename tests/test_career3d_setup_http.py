from application_double import ApplicationDouble
from unittest.mock import ANY
"""Saved-path setup over authenticated HTTP; all game files are QA fixtures."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cs2career.cs2 import launch
from cs2career.web.server import create_server
from tools import career3d_activities as activities
from tools import career3d_install as install
from tools import career3d_service as service
FIXTURE_GI = b'GameInfo { FileSystem { SearchPaths { Game csgo } } }'


class Career3DSetupHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='career3d-setup-http-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.data = self.root / 'isolated-career'
        self.save = self.data / 'save'
        self.save.mkdir(parents=True)
        (self.data / '.career3d-demo.json').write_text(
            json.dumps({'kind': 'cs2career-godot-demo'}), encoding='utf-8')
        self.steam = self.root / 'fixture-steam' / 'steam.exe'
        self.steam.parent.mkdir()
        self.steam.write_bytes(b'fixture Steam; not executable')
        self.game = self.steam.parent / 'fixture-install' / 'game' / 'csgo'
        self.game.mkdir(parents=True)
        (self.game / 'gameinfo.gi').write_bytes(FIXTURE_GI)
        (self.game / 'cfg').mkdir()
        self.mod = self.root / 'downloaded release'
        for name in ('addons/metamod', 'addons/counterstrikesharp', 'overrides'):
            (self.mod / name).mkdir(parents=True)
        (self.mod / 'addons/metamod/runtime.dll').write_bytes(b'fixture runtime')
        self.effective_mod = self.data / 'runtime-cache/fixture-compatible/mod'

        self.saved = 0
        self.state = ApplicationDouble(
            career=SimpleNamespace(
                incident_state={'career3d_service': {'revision': 7, 'receipts': []}},
                training_session=None, real_skins=False, steam_id=''),
            season=SimpleNamespace(date='2026-10-02', events=[]),
            arena=SimpleNamespace(pending=None, data={'revision': 2,
                'lobby': {'id': 'fixture-room', 'mode': 'rank', 'phase': 'ready'}}),
            persist=self.persist)
        self.start(patch.dict(os.environ, {
            'CS2CAREER_SAVE_DIR': str(self.save),
            'CS2CAREER_EXTENSION_DIR': str(self.data / 'extensions'),
            install.ENV_MOD: '',
        }))
        self.start(patch.object(install.sys, 'frozen', False, create=True))
        self.start(patch.object(launch, 'SETTINGS_PATH', self.save / 'cs2.json'))
        self.start(patch('cs2career.paths.save_root', return_value=self.save))
        self.start(patch.object(service, '_pause', return_value=('', '')))
        # Keep unrelated career projections out of this integration test. The
        # settings/config and ladder status below still use their real code.
        self.start(patch.object(service, 'read_context', side_effect=self.context))
        self.running = self.start(patch.object(activities, '_running_cs2', return_value=False))
        self.start(patch('cs2career.cs2.process_state.cs2_running', return_value=False))
        self.runtime_prepare = self.start(patch('tools.career3d_runtime_compat.prepare_runtime',
            side_effect=self.prepare_fixture))
        self.mod_install = self.start(patch.object(launch, 'install_mod', side_effect=self.install_fixture))
        self.skin_install = self.start(patch.object(launch, 'install_skins_mod',
            side_effect=AssertionError('optional skins must not install')))
        self.start(patch.object(launch, 'find_mod_source',
            side_effect=AssertionError('do not discover or install another source')))
        self.start(patch.object(launch, '_powershell',
            side_effect=AssertionError('do not inspect real processes')))
        self.start(patch('subprocess.Popen', side_effect=AssertionError('never launch a game')))

        self.server = create_server(self.state)
        self.server.RequestHandlerClass = service.handler_class()
        self.server.display_hour = 8
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.close_server)
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def start(self, context):
        result = context.start()
        self.addCleanup(context.stop)
        return result

    def close_server(self):
        self.server.shutdown()
        self.worker.join(5)
        self.server.server_close()

    def persist(self):
        self.assertTrue(self.server.state_lock._is_owned())
        self.saved += 1

    def context(self, state, display_hour):
        self.assertTrue(self.server.state_lock._is_owned())
        return {'calendar': {'revision': service._revision(state)},
                'settings': activities.settings_context(state)}

    def install_fixture(self, game, mod, *, config):
        self.assertTrue(self.server.state_lock._is_owned())
        self.assertEqual(game, self.game.resolve())
        self.assertEqual(mod, self.effective_mod.resolve())
        self.assertTrue(game.is_relative_to(self.root))
        self.assertTrue(mod.is_relative_to(self.root))
        # The real installer is intentionally not called. Create only the
        # minimal synthetic component layout checked by the real status code.
        for name in ('addons/metamod', 'addons/counterstrikesharp', 'addons/BotHider'):
            (game / name).mkdir(parents=True, exist_ok=True)
        for component in ('CareerMatch', 'BotBuy'):
            target = game / 'addons/counterstrikesharp/plugins' / component
            target.mkdir(parents=True)
            for suffix in ('.dll', '.deps.json'):
                # The status adapter verifies the bundled DLL, not just existence.
                source = Path(__file__).resolve().parents[1] / 'vendor' / component / (component + suffix)
                (target / (component + suffix)).write_bytes(source.read_bytes() if source.is_file() else b'fixture component')
        return {'ok': True, 'files': 4}

    def prepare_fixture(self, root, source, game):
        self.assertTrue(self.server.state_lock._is_owned())
        self.assertEqual(root, self.data.resolve())
        self.assertEqual(source, self.mod.resolve())
        self.assertEqual(game, self.game.resolve())
        shutil.copytree(source, self.effective_mod)
        (self.effective_mod / 'addons/metamod/runtime.dll').write_bytes(b'fixture compatible runtime')
        return {'mod_dir':str(self.effective_mod), 'origin_mod_dir':str(source),
                'revision':'fixture-compatible-1', 'components':{'fixture':'1'}}

    def request(self, path, body=None, token=None):
        request = Request(self.base + path,
            data=None if body is None else json.dumps(body).encode('utf-8'),
            headers={'X-Career-Token': self.server.token if token is None else token,
                     'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as response:
            return response.code, json.load(response)

    def save_paths(self, revision=7):
        # Explorer's Copy as path quotes and surrounding whitespace must be
        # removed for all three required paths, not just for game/csgo.
        return self.request('/api/3d/settings', {'revision': revision, 'settings': {
            'steam_exe': f'  "{self.steam}"  ',
            'csgo_path': f'"{self.game.parents[1]}"',
            'mod_source_path': f'  "{self.mod}"  ',
        }})

    def files(self):
        return {path.relative_to(self.game).as_posix(): path.read_bytes()
                for path in self.game.rglob('*') if path.is_file()}

    def test_detect_machine_paths_is_an_authenticated_read_without_install_or_save(self):
        before = self.files()
        with patch.object(launch, 'find_steam_exe', return_value=str(self.steam)) as steam, \
                patch.object(launch, 'find_csgo_path', return_value=str(self.game)) as game:
            status, rejected = self.request('/api/3d/settings/detect', token='wrong-token')
            self.assertEqual(403, status)
            steam.assert_not_called()
            game.assert_not_called()
            status, detected = self.request('/api/3d/settings/detect')
        self.assertEqual(200, status)
        self.assertEqual({'steam_exe':str(self.steam.resolve()), 'csgo_path':str(self.game.resolve())}, detected['paths'])
        self.assertEqual(before, self.files())
        self.assertFalse(launch.SETTINGS_PATH.exists())
        self.assertEqual(0, self.saved)
        self.running.assert_not_called()
        self.mod_install.assert_not_called()
        self.runtime_prepare.assert_not_called()

    def test_pending_character_cannot_start_business_actions_but_can_read_settings(self):
        self.state.career.incident_state['career3d_start'] = {'schema_version':1, 'pending':True}
        status, blocked = self.request('/api/3d/calendar', {'revision':7, 'date':'2026-10-03'})
        self.assertEqual(400, status)
        self.assertIn('创建角色', blocked['msg'])
        self.assertEqual(0, self.saved)
        self.assertEqual(7, service._revision(self.state))
        self.assertEqual(200, self.request('/api/3d/settings')[0])

    def test_updates_require_explicit_authenticated_query_and_do_not_hold_state_lock(self):
        before = self.files()
        def query():
            self.assertFalse(self.server.state_lock._is_owned())
            return {'checked':False, 'update_available':False, 'reason':'无法连接，不影响本地安装。'}
        with patch('tools.career3d_runtime_updates.check_updates', side_effect=query) as updates:
            self.assertEqual(200, self.request('/api/3d/settings')[0])
            updates.assert_not_called()
            self.assertEqual(403, self.request('/api/3d/settings/updates', token='wrong-token')[0])
            updates.assert_not_called()
            status, result = self.request('/api/3d/settings/updates')
            self.assertEqual(200, status)
            self.assertTrue(result['ok'])
            self.assertFalse(result['checked'])
            self.assertIn('不影响', result['reason'])
            updates.assert_called_once_with()
        self.assertEqual(before, self.files())
        self.assertEqual(0, self.saved)
        self.runtime_prepare.assert_not_called()
        self.mod_install.assert_not_called()

    def test_ordinary_package_save_then_external_install_unlocks_ladder(self):
        self.assertIsNone(install.bundle_root())
        before = self.files()
        status, saved = self.save_paths()
        self.assertEqual(200, status)
        self.assertTrue(saved['ok'])
        revision = saved['context']['calendar']['revision']
        self.assertEqual(8, revision)
        self.assertEqual(revision, saved['context']['settings']['revision'])
        cfg = activities.read_cs2_config()
        self.assertEqual(str(self.steam), cfg['steam_exe'])
        self.assertEqual(str(self.game), cfg['csgo_path'])
        self.assertEqual(str(self.mod), cfg['mod_source_path'])
        self.assertEqual(before, self.files())
        self.mod_install.assert_not_called()
        self.assertEqual(1, self.saved)
        self.assertFalse(saved['context']['settings']['setup']['available'])
        self.assertTrue(saved['context']['settings']['setup']['external_available'])

        status, blocked = self.request('/api/3d/ladder/status')
        self.assertEqual(200, status)
        self.assertEqual('blocked', blocked['status'])
        self.assertFalse(blocked['can_launch'])
        self.assertEqual([], blocked['config']['path_errors'])
        self.assertEqual(3, len(blocked['config']['component_errors']))

        status, result = self.request('/api/3d/setup/install',
            {'revision': revision, 'source': 'external', 'confirm': True})
        self.assertEqual(200, status, result)
        self.assertTrue(result['ok'])
        self.assertEqual('external', result['source'])
        self.assertEqual(9, result['context']['calendar']['revision'])
        self.assertTrue(result['context']['settings']['config']['ready'])
        self.mod_install.assert_called_once_with(self.game.resolve(), self.effective_mod.resolve(), config=ANY)
        self.assertEqual(str(self.effective_mod.resolve()),
                         result['context']['settings']['mod_source_path'])
        self.assertEqual(b'fixture runtime', (self.mod / 'addons/metamod/runtime.dll').read_bytes())
        self.assertEqual('fixture-compatible-1', result['runtime']['compatibility_revision'])
        self.skin_install.assert_not_called()
        self.assertEqual(4, self.saved)  # Settings, external intent, adapter state, acknowledgement.
        backup = Path(result['backup_path'])
        self.assertTrue(backup.is_relative_to(self.data))
        self.assertEqual(FIXTURE_GI,
                         (backup / 'files/gameinfo.gi').read_bytes())
        self.assertEqual('installed', json.loads(
            (backup / 'BACKUP_MANIFEST.json').read_text('utf-8'))['status'])

        status, ready = self.request('/api/3d/ladder/status')
        self.assertEqual(200, status)
        self.assertEqual('ready', ready['status'])
        self.assertTrue(ready['can_launch'])
        self.assertEqual([], ready['config']['missing'])
        self.assertEqual([], ready['config']['path_errors'])
        self.assertEqual([], ready['config']['component_errors'])

    def test_authentication_rejects_reads_save_and_install_before_any_mutation(self):
        before = self.files()
        for token in ('', 'wrong-session-token'):
            for path, body in (('/api/3d/settings', None),
                               ('/api/3d/settings', {'revision': 7, 'settings': {}}),
                               ('/api/3d/setup/install',
                                {'revision': 7, 'source': 'external', 'confirm': True})):
                with self.subTest(token=token, path=path):
                    status, response = self.request(path, body, token)
                    self.assertEqual(403, status)
                    self.assertFalse(response['ok'])
        self.assertEqual(before, self.files())
        self.assertFalse(launch.SETTINGS_PATH.exists())
        self.assertFalse((self.data / 'install-backups').exists())
        self.assertEqual(0, self.saved)
        self.running.assert_not_called()
        self.mod_install.assert_not_called()
        self.runtime_prepare.assert_not_called()

    def test_stale_save_revision_does_not_create_or_install_settings(self):
        before = self.files()
        for revision in (6, True, '7'):
            with self.subTest(revision=revision):
                status, response = self.save_paths(revision)
                self.assertEqual(400, status)
                self.assertFalse(response['ok'])
                # Rejected operations omit the pre-rollback projection. A
                # fresh read supplies the authoritative revision instead.
                self.assertNotIn('context', response)
                self.assertEqual(7, self.request('/api/3d/settings')[1]['settings']['revision'])
        self.assertFalse(launch.SETTINGS_PATH.exists())
        self.assertEqual(before, self.files())
        self.assertEqual(0, self.saved)
        self.mod_install.assert_not_called()
        self.runtime_prepare.assert_not_called()

    def test_install_requires_latest_saved_revision_and_literal_confirmation(self):
        self.assertEqual(200, self.save_paths()[0])
        before_files = self.files()
        before_config = launch.SETTINGS_PATH.read_bytes()
        before_state = deepcopy(self.state.career.incident_state)
        for body in ({'revision': 7, 'source': 'external', 'confirm': True},
                     {'revision': 8, 'source': 'external'},
                     {'revision': 8, 'source': 'external', 'confirm': 'true'},
                     {'revision': True, 'source': 'external', 'confirm': True},
                     {'revision': 8, 'source': 'unknown', 'confirm': True}):
            with self.subTest(body=body):
                status, response = self.request('/api/3d/setup/install', body)
                self.assertEqual(400, status)
                self.assertFalse(response['ok'])
                self.assertEqual(8, response['context']['calendar']['revision'])
        self.assertEqual(before_files, self.files())
        self.assertEqual(before_config, launch.SETTINGS_PATH.read_bytes())
        self.assertEqual(before_state, self.state.career.incident_state)
        self.assertFalse((self.data / 'install-backups').exists())
        self.assertEqual(1, self.saved)
        self.mod_install.assert_not_called()
        self.runtime_prepare.assert_not_called()

    def test_status_reports_bad_source_as_path_error_not_missing_game_components(self):
        status, response = self.request('/api/3d/settings', {'revision': 7, 'settings': {
            'steam_exe': str(self.steam), 'csgo_path': str(self.game),
            'mod_source_path': str(self.root / 'not-a-release')}})
        self.assertEqual(200, status)
        cfg = response['context']['settings']['config']
        self.assertFalse(cfg['checks']['mod'])
        self.assertEqual(1, len(cfg['path_errors']))
        self.assertIn('发行包', cfg['path_errors'][0])
        self.assertTrue(cfg['checks']['csgo'])
        self.assertEqual(3, len(cfg['component_errors']))
        self.mod_install.assert_not_called()

    def test_failed_compatibility_preparation_preserves_saved_paths_and_ladder_block(self):
        self.assertEqual(200, self.save_paths()[0])
        before_config = launch.SETTINGS_PATH.read_bytes()
        before_files = self.files()
        before_source = (self.mod / 'addons/metamod/runtime.dll').read_bytes()
        self.runtime_prepare.side_effect = ValueError('兼容组件准备失败，未安装。')
        status, response = self.request('/api/3d/setup/install',
            {'revision':8, 'source':'external', 'confirm':True})
        self.assertEqual(400, status)
        self.assertFalse(response['ok'])
        self.assertEqual(8, response['context']['calendar']['revision'])
        self.assertEqual(1, self.saved)
        self.assertEqual(before_config, launch.SETTINGS_PATH.read_bytes())
        self.assertEqual(before_files, self.files())
        self.assertEqual(before_source, (self.mod / 'addons/metamod/runtime.dll').read_bytes())
        self.assertFalse((self.data / 'install-backups').exists())
        self.mod_install.assert_not_called()
        status, ladder = self.request('/api/3d/ladder/status')
        self.assertEqual(200, status)
        self.assertFalse(ladder['can_launch'])
        self.assertEqual('blocked', ladder['status'])

    def test_missing_source_install_returns_actionable_400_without_writes(self):
        self.assertEqual(200, self.save_paths()[0])
        config = launch.SETTINGS_PATH.read_bytes()
        files = self.files()
        self.runtime_prepare.side_effect = FileNotFoundError('兼容组件文件未找到，请重新下载。')
        status, response = self.request('/api/3d/setup/install',
            {'revision':8, 'source':'external', 'confirm':True})
        self.assertEqual(400, status)
        self.assertFalse(response['ok'])
        self.assertIn('重新下载', response['msg'])
        self.assertEqual(config, launch.SETTINGS_PATH.read_bytes())
        self.assertEqual(files, self.files())
        self.mod_install.assert_not_called()

    def test_settings_status_refresh_is_read_only_and_does_not_install(self):
        self.assertEqual(200, self.save_paths()[0])
        before_config = launch.SETTINGS_PATH.read_bytes()
        before_files = self.files()
        for _ in range(2):
            status, response = self.request('/api/3d/settings')
            self.assertEqual(200, status)
            self.assertTrue(response['ok'])
            self.assertEqual(8, response['settings']['revision'])
            self.assertFalse(response['settings']['config']['ready'])
        self.assertEqual(before_config, launch.SETTINGS_PATH.read_bytes())
        self.assertEqual(before_files, self.files())
        self.assertEqual(1, self.saved)
        self.mod_install.assert_not_called()


if __name__ == '__main__':
    unittest.main()
