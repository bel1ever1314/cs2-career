from application_double import ApplicationDouble
"""Full switch endpoint uses only synthetic game files and mocked processes."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cs2career.cs2 import launch
from cs2career.cs2.environment import read_lease, finish_watch
from cs2career.web.server import create_server
from tools import career3d_activities as activities
from tools import career3d_service as service


class EnvironmentHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='career-environment-http-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / 'game/csgo'
        (self.game / 'cfg').mkdir(parents=True)
        (self.game / 'gameinfo.gi').write_text('GameInfo { FileSystem { SearchPaths { Game csgo } } }', 'utf-8')
        (self.game / 'gameinfo_branchspecific.gi').write_bytes(b'GameInfo { FileSystem { SteamAppId 730 } }')
        (self.game / 'cfg/career_rules.cfg').write_text('bot_difficulty 3\n', 'utf-8')
        (self.game / 'cfg/gamemode_competitive.cfg').write_text('echo Valve\n', 'utf-8')
        self.save = self.root / 'save'
        self.save.mkdir()
        self.cfg = {**launch.DEFAULTS, 'csgo_path':str(self.game)}
        self.start(patch.object(launch, 'SETTINGS_PATH', self.save / 'cs2.json'))
        launch._write_settings(self.cfg)
        self.saved = 0
        self.state = ApplicationDouble(
            career=SimpleNamespace(incident_state={'career3d_service':{'revision':7, 'receipts':[]}},
                real_skins=False, steam_id='', training_session=None),
            season=SimpleNamespace(date='2026-10-04', events=[]),
            arena=SimpleNamespace(pending=None), persist=self.persist)
        self.start(patch('cs2career.paths.save_root', return_value=self.save))
        self.start(patch.object(service, '_pause', return_value=('', '')))
        self.start(patch.object(service, 'read_context', side_effect=self.context))
        self.ready = self.start(patch.object(activities, 'config_status', return_value={
            'ready':True, 'reason':'ready', 'checks':{'runtime':True, 'career_match':True, 'botbuy':True}}))
        self.live = self.start(patch('cs2career.cs2.process_state.cs2_running', return_value=False))
        self.spawn = self.start(patch('tools.career3d_cs2_watchdog.spawn_watch', return_value=object()))
        self.start(patch('subprocess.Popen', side_effect=AssertionError('never launch a real process')))
        self.server = create_server(self.state)
        self.server.RequestHandlerClass = service.handler_class()
        self.server.display_hour = 8
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.close)
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def start(self, manager):
        value = manager.start()
        self.addCleanup(manager.stop)
        return value

    def close(self):
        self.server.shutdown()
        self.worker.join(5)
        self.server.server_close()

    def persist(self):
        self.saved += 1

    def context(self, state, hour):
        return {'calendar':{'revision':service._revision(state)}, 'settings':activities.settings_context(state)}

    def request(self, body=None, *, token=None):
        request = Request(self.base+'/api/3d/settings/environment',
            data=None if body is None else json.dumps(body).encode(),
            headers={'X-Career-Token':self.server.token if token is None else token,
                     'Content-Type':'application/json'})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as response:
            return response.code, json.load(response)

    def files(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_get_and_unauthorized_post_are_read_only(self):
        before = self.files()
        self.assertEqual(403, self.request(token='wrong')[0])
        self.assertEqual(403, self.request({'revision':7, 'mode':'enhanced'}, token='wrong')[0])
        status, result = self.request()
        self.assertEqual(200, status)
        self.assertEqual('normal', result['environment']['mode'])
        self.assertEqual(before, self.files())
        self.assertEqual(0, self.saved)
        self.spawn.assert_not_called()

    def test_enable_then_disable_preserves_pending_match_and_preferences(self):
        pending = {'nonce':'unfinished', 'completed_maps':['nuke']}
        self.state.arena.pending = deepcopy(pending)
        self.state.career.training_session = {'nonce':'training'}
        self.state.season.events = [{'matches':[{'played':False, 'cs2_session':{'nonce':'career'}}]}]
        before = launch.SETTINGS_PATH.read_bytes()
        status, result = self.request({'revision':7, 'mode':'enhanced'})
        self.assertEqual(200, status, result)
        self.assertEqual('enhanced', result['environment']['mode'])
        self.assertTrue(result['environment']['watch_active'])
        self.assertEqual(8, result['context']['calendar']['revision'])
        self.spawn.assert_called_once()
        self.assertEqual('manual', self.spawn.call_args.kwargs['mode'])
        status, result = self.request({'revision':8, 'mode':'normal'})
        self.assertEqual(200, status, result)
        self.assertEqual('normal', result['environment']['mode'])
        self.assertEqual(9, result['context']['calendar']['revision'])
        self.assertEqual(pending, self.state.arena.pending)
        self.assertEqual(before, launch.SETTINGS_PATH.read_bytes())
        self.assertFalse(self.state.career.real_skins)

    def test_normal_recovery_is_available_before_character_creation_and_without_mod(self):
        self.state.career.incident_state['career3d_start'] = {'schema_version':1, 'pending':True}
        self.ready.return_value = {'ready':False, 'reason':'not installed'}
        status, result = self.request({'revision':7, 'mode':'normal'})
        self.assertEqual(200, status, result)
        self.assertEqual('normal', result['environment']['mode'])
        self.ready.assert_called()  # Projection, never an enable prerequisite.
        self.spawn.assert_not_called()

    def test_active_or_unknown_game_and_stale_revision_cannot_write(self):
        before = self.files()
        self.assertEqual(400, self.request({'revision':6, 'mode':'normal'})[0])
        for value in (True, None):
            self.live.return_value = value
            status, result = self.request({'revision':7, 'mode':'enhanced'})
            self.assertEqual(400, status, result)
        self.assertEqual(before, self.files())
        self.assertEqual(0, self.saved)
        self.spawn.assert_not_called()

    def test_spawn_failure_restores_mounts_and_does_not_accept_success(self):
        before = (self.game / 'gameinfo.gi').read_bytes()
        self.spawn.side_effect = OSError('fixture child spawn failed')
        status, result = self.request({'revision':7, 'mode':'enhanced'})
        self.assertEqual(400, status, result)
        self.assertIn('已恢复普通', result['msg'])
        after = (self.game / 'gameinfo.gi').read_text('utf-8')
        self.assertNotIn('metamod', after)
        self.assertNotIn('overrides', after)
        self.assertEqual(before.decode().split(), after.split())
        self.assertEqual('normal', read_lease(self.game)['mode'])
        self.assert_pending_effect()

    def test_old_exit_watcher_cannot_undo_a_new_enable(self):
        self.assertEqual(200, self.request({'revision':7, 'mode':'enhanced'})[0])
        old = read_lease(self.game)['generation']
        self.assertEqual(200, self.request({'revision':8, 'mode':'normal'})[0])
        self.assertEqual(200, self.request({'revision':9, 'mode':'enhanced'})[0])
        self.assertEqual({'status':'superseded'}, finish_watch(self.game, old))
        self.assertEqual('enhanced', self.request()[1]['environment']['mode'])

    def test_enable_does_not_require_the_original_download_again(self):
        self.ready.return_value = {'ready':False, 'reason':'download removed',
            'checks':{'runtime':True, 'career_match':True, 'botbuy':True, 'mod':False, 'steam':False}}
        status, result = self.request({'revision':7, 'mode':'enhanced'})
        self.assertEqual(200, status, result)
        self.assertEqual('enhanced', result['environment']['mode'])

    def test_unwritable_game_returns_actionable_error_with_current_state(self):
        before = (self.game / 'gameinfo.gi').read_bytes()
        with patch('cs2career.cs2.environment._replace', side_effect=PermissionError('fixture lock')):
            status, result = self.request({'revision':7, 'mode':'enhanced'})
        self.assertEqual(400, status, result)
        self.assertIn('游戏目录可写', result['msg'])
        self.assertEqual('normal', result['context']['settings']['environment']['mode'])
        self.assertEqual(before, (self.game / 'gameinfo.gi').read_bytes())
        self.assert_pending_effect()

    def assert_pending_effect(self):
        # The effect began, but success was never acknowledged. Reconnect may
        # inspect this intent; it must not perform another switch automatically.
        self.assertEqual(1, self.saved)
        self.assertEqual(7, service._revision(self.state))
        receipts = self.state.career.incident_state['operation_receipts']
        self.assertEqual(1, len(receipts))
        self.assertEqual('pending', receipts[0]['phase'])

    def test_old_persistent_insecure_is_reported_after_normal_switch(self):
        warning = 'Steam 的 CS2 启动选项仍含 -insecure；请在 Steam → CS2 → 属性 → 启动选项中移除后再打排位。'
        with patch('cs2career.cs2.steam_options.launch_options_status',
                   return_value={'checked':True, 'insecure':True, 'reason':warning}):
            status, result = self.request({'revision':7, 'mode':'normal'})
        self.assertEqual(200, status, result)
        self.assertEqual('normal', result['environment']['mode'])
        self.assertIn(warning, result['reason'])
        self.assertIn(warning, result['environment']['reason'])
        self.assertNotIn('可以从 Steam 正常启动', result['reason'])


if __name__ == '__main__':
    unittest.main()
