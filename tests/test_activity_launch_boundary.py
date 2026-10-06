"""Real temporary saves and fake Steam: arena/practice handoff crash points."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import unittest

import test_recovery_http as fixture
from cs2career.application import ApplicationState
from cs2career.cs2 import launch
from cs2career.services import activity_launch, matches
from cs2career.services.requests import request_result
from cs2career.storage import transaction as tx


class ActivityLaunchBoundaryTests(unittest.TestCase):
    setUp = fixture.RecoveryHttpTests.setUp
    career_fixture = fixture.RecoveryHttpTests.career_fixture
    serving = fixture.RecoveryHttpTests.serving
    request = fixture.RecoveryHttpTests.request

    def ready(self, kind='custom'):
        self.career_fixture()
        self.state.season.events.clear()
        self.state.career.training_session = None
        self.state.career.last_scrim = ''
        self.stack.enter_context(patch('tools.career3d_activities._running_cs2', return_value=False))
        self.stack.enter_context(patch('tools.career3d_activities.config_status', return_value=dict(ready=True, reason='')))
        self.stack.enter_context(patch('tools.career3d_activities.read_cs2_config', return_value=dict(launch.DEFAULTS, csgo_path='')))
        self.stack.enter_context(patch.object(launch, 'require_cs2_closed'))
        self.stack.enter_context(patch.object(launch, 'SETTINGS_PATH', self.root/'cs2.json'))
        self.stack.enter_context(patch('tools.career3d_activities._peek_ladder_result', return_value=dict(status='none')))
        if kind == 'training':
            self.path = '/api/3d/controls/training/launch'
            other = next(t for t in self.state.season.teams if t['id'] != self.state.career.team_id)
            self.body = dict(opponent_id=other['id'], map='de_dust2', side='ct', revision=0)
        else:
            arena = self.state.arena
            if kind == 'custom':
                arena.create(self.state, dict(revision=arena.data['revision'], mode='custom', players=list(arena.roster(self.state))[:10]))
            else:
                arena.matchmake(self.state, dict(revision=arena.data['revision']))
                while arena.data['lobby']['phase'] in ('draft', 'veto', 'side'):
                    lobby = arena.data['lobby']
                    body = dict(revision=arena.data['revision'])
                    if not arena.turn(lobby)['human']: arena.advance(body)
                    elif lobby['phase'] == 'draft':
                        arena.pick(dict(body, player_id=next(p for p in lobby['selection'] if p not in lobby['a'] + lobby['b'])))
                    elif lobby['phase'] == 'veto':
                        arena.ban(dict(body, map=next(m for m in lobby['map_pool'] if m not in [b['map'] for b in lobby['bans']])))
                    else: arena.choose_side(dict(body, side='ct'))
            self.path = '/api/3d/' + ('ladder' if kind == 'rank' else 'custom') + '/launch'
            self.body = dict(lobby_id=arena.data['lobby']['id'], revision=arena.data['revision'])
        self.body['request_id'] = 'activity-launch-0001'
        self.state.persist()

    def session(self, state=None):
        state = state or self.state
        return state.career.training_session if '/training/' in self.path else state.arena.data['lobby']

    def dispatch(self, cfg, args, kwargs):
        saved = self.session(ApplicationState())
        self.assertEqual(kwargs['request_override']['nonce'], saved['nonce'])
        self.assertEqual('prepared', saved['launch_state'])
        self.assertEqual('unknown', request_result(self.state, self.body['request_id'])['status'])
        self.assertFalse(self.state._operation_depth)
        kwargs['before_dispatch']()
        self.assertEqual('dispatching', self.session(ApplicationState())['launch_state'])
        return dict(match=kwargs['request_override'], msg='fake Steam accepted')

    def test_process_exit_preserves_each_activity_boundary_without_relaunch(self):
        worker = Path(__file__).parent/'fixtures/match_boundary_worker.py'
        for kind in ('custom', 'rank', 'training'):
            for point in ('intent_saved', 'dispatch_saved', 'external_finished', 'result_saved'):
                with self.subTest(kind=kind, point=point):
                    self.state.arena.data['lobby'] = None
                    self.state.arena.save()
                    self.ready(kind)
                    result = subprocess.run([sys.executable, '-B', str(worker), str(self.root),
                        'activity:' + kind, point, ''], capture_output=True, timeout=20)
                    self.assertEqual(73, result.returncode, result.stderr.decode('utf-8', errors='replace'))
                    restored = ApplicationState()
                    self.assertTrue(self.session(restored)['nonce'])
                    self.assertEqual('completed' if point == 'result_saved' else 'unknown',
                                     request_result(restored, 'process-stop-0001')['status'])
                    with patch.object(matches, '_dispatch_launch', side_effect=AssertionError('no relaunch')):
                        body = dict(self.body, request_id='process-stop-0001')
                        self.assertTrue(activity_launch.command(restored, self.path, body)['replayed'])

    def test_all_three_modes_save_before_dispatch_and_never_repeat_receipt(self):
        for kind in ('custom', 'rank', 'training'):
            with self.subTest(kind=kind):
                self.state.arena.data['lobby'] = None
                self.state.arena.save()
                self.ready(kind)
                with patch.object(matches, '_dispatch_launch', side_effect=self.dispatch) as dispatch:
                    result = activity_launch.command(self.state, self.path, self.body)
                    again = activity_launch.command(self.state, self.path, self.body)
                self.assertEqual('waiting', result['status'])
                self.assertTrue(again['replayed'])
                dispatch.assert_called_once()
                self.assertEqual('dispatched', self.session(ApplicationState())['launch_state'])

    def test_interruption_at_every_handoff_point_keeps_identity_without_auto_retry(self):
        for point in ('intent_saved', 'dispatch_saved', 'external_finished', 'result_saved'):
            with self.subTest(point=point):
                self.state.arena.data['lobby'] = None
                self.state.arena.save()
                self.ready()
                def stop(current):
                    if current == point: raise KeyboardInterrupt(point)
                with patch.object(matches, '_dispatch_launch', side_effect=self.dispatch), \
                     patch.object(activity_launch, '_checkpoint', side_effect=stop):
                    with self.assertRaises(KeyboardInterrupt):
                        activity_launch.command(self.state, self.path, self.body)
                restored = ApplicationState()
                nonce = self.session(restored)['nonce']
                with patch.object(matches, '_dispatch_launch', side_effect=AssertionError('duplicate Steam')):
                    result = activity_launch.command(restored, self.path, self.body)
                self.assertTrue(result['replayed'])
                self.assertEqual(nonce, self.session(restored)['nonce'])
                self.assertEqual('completed' if point == 'result_saved' else 'unknown', request_result(restored, self.body['request_id'])['status'])

    def test_failure_before_intent_commit_never_touches_game(self):
        self.ready()
        before = (self.root/'arena.json').read_bytes()
        def stop(point):
            if point == 'before_commit': raise OSError('disk full')
        with patch.object(tx, '_checkpoint', side_effect=stop), patch.object(matches, '_dispatch_launch') as launch:
            with self.assertRaises(OSError): activity_launch.command(self.state, self.path, self.body)
        launch.assert_not_called()
        self.assertEqual(before, (self.root/'arena.json').read_bytes())

    def test_dispatch_failure_preserves_training_for_explicit_cancel(self):
        self.ready('training')
        with patch.object(matches, '_dispatch_launch', side_effect=OSError('Steam failed')):
            result = activity_launch.command(self.state, self.path, self.body)
        self.assertEqual('failed', result['status'])
        self.assertEqual('uncertain', self.session(ApplicationState())['launch_state'])
        self.assertEqual('', self.state.career.last_scrim)

    def test_failed_custom_launch_returns_current_connection_not_preparation_success(self):
        self.ready('custom')
        with patch.object(matches, '_dispatch_launch', side_effect=OSError('Steam failed')):
            result = activity_launch.command(self.state, self.path, self.body)
        self.assertEqual('failed', result['status'])
        self.assertEqual('starting', result['connection']['phase'])
        self.assertTrue(result['connection']['can_retry'])
        self.assertEqual(self.session()['id'], result['connection']['lobby_id'])

    def test_http_routes_launch_outside_generic_transaction(self):
        self.ready()
        with self.serving(), patch.object(matches, '_dispatch_launch', side_effect=self.dispatch):
            code, result = self.request(self.path, self.body)
        self.assertEqual(200, code, result)
        self.assertEqual('waiting', result['status'])


if __name__ == '__main__': unittest.main()
