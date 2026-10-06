"""Real paired saves around a fake external CS2 dispatch; never starts a game."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_recovery_http as http_fixture
from cs2career.application import ApplicationState
from cs2career.cs2 import launch
from cs2career.services import match_launch, matches
from cs2career.services import match_simulation
from cs2career.services.requests import request_result
from cs2career.storage import transaction as tx
from cs2career.storage.receipts import lookup


class MatchLaunchBoundaryTests(unittest.TestCase):
    setUp = http_fixture.RecoveryHttpTests.setUp
    career_fixture = http_fixture.RecoveryHttpTests.career_fixture
    serving = http_fixture.RecoveryHttpTests.serving
    request = http_fixture.RecoveryHttpTests.request

    def ready(self):
        c, s, match = self.career_fixture()
        self.stack.enter_context(patch.object(c, 'gate_match', return_value=''))
        self.stack.enter_context(patch.object(s, '_phase_gate', return_value=False))
        self.stack.enter_context(patch('tools.career3d_activities._running_cs2', return_value=False))
        self.stack.enter_context(patch('tools.career3d_activities.config_status', return_value=dict(ready=True, reason='')))
        self.stack.enter_context(patch('tools.career3d_activities.read_cs2_config', return_value=dict(launch.DEFAULTS, csgo_path='')))
        self.stack.enter_context(patch.object(launch, 'require_cs2_closed'))
        self.stack.enter_context(patch.object(matches, '_peek', return_value={'status': 'none'}))
        matches.match_command(self.state, 'autoveto', dict(match_id=match['id'], revision=0))
        self.state.persist()
        self.match_id = match['id']
        return match

    def body(self, rid='launch-boundary-0001'):
        return dict(match_id=self.match_id, revision=matches._revision(self.state), request_id=rid)

    def dispatch(self, cfg, arguments, kwargs):
        # Independent disk reads prove the intent is durable before effects.
        season = json.loads((self.root/'season.json').read_text('utf-8'))
        stored = next(m for ev in season['events'] for m in ev['matches'] if m['id'] == self.match_id)
        request = kwargs['request_override']
        self.assertEqual(request['nonce'], stored['cs2_session']['nonce'])
        self.assertEqual(10, len(set(stored['cs2_session']['expected_player_ids'])))
        self.assertEqual('prepared', stored['cs2_session']['launch_state'])
        self.assertEqual('pending', lookup(self.state.career, self.body()['request_id'])['phase'])
        self.assertEqual('unknown', request_result(self.state, self.body()['request_id'])['status'])
        self.assertEqual(0, self.state._operation_depth)
        kwargs['before_dispatch']()
        self.assertEqual('dispatching', self.state.season.find_match(self.match_id)[1]['cs2_session']['launch_state'])
        return dict(match=request, msg='fake Steam accepted')

    def test_intent_precedes_external_work_and_completion_replays_without_dispatch(self):
        self.ready()
        body = self.body()
        with patch.object(matches, '_dispatch_launch', side_effect=self.dispatch) as dispatch:
            result = match_launch.command(self.state, body)
            again = match_launch.command(self.state, body)
        self.assertEqual('waiting', result['status'])
        self.assertTrue(again['replayed'])
        dispatch.assert_called_once()
        loaded = ApplicationState()
        session = loaded.season.find_match(self.match_id)[1]['cs2_session']
        self.assertEqual('dispatched', session['launch_state'])
        self.assertEqual('completed', request_result(loaded, body['request_id'])['status'])
        self.assertFalse(loaded.season.find_match(self.match_id)[1].get('career3d_receipts'))

    def test_interruption_after_intent_or_dispatch_never_automatically_launches_again(self):
        self.ready()
        for point in ('intent_saved', 'dispatch_saved', 'external_finished', 'result_saved'):
            with self.subTest(point=point):
                # A new isolated career for each stop, not a mutated live save.
                self.ready()
                body = self.body()
                def stop(current):
                    if current == point:
                        raise KeyboardInterrupt('simulated process stop')
                with patch.object(match_launch, '_checkpoint', side_effect=stop), \
                     patch.object(matches, '_dispatch_launch', side_effect=self.dispatch) as dispatch:
                    with self.assertRaises(KeyboardInterrupt):
                        match_launch.command(self.state, body)
                expected = 0 if point == 'intent_saved' else 1
                self.assertEqual(expected, dispatch.call_count)
                loaded = ApplicationState()
                original = deepcopy(loaded.season.find_match(self.match_id)[1]['cs2_session'])
                with patch.object(matches, '_dispatch_launch', side_effect=AssertionError('must not re-dispatch')):
                    replay = match_launch.command(loaded, body)
                self.assertTrue(replay['replayed'])
                self.assertEqual(original, loaded.season.find_match(self.match_id)[1]['cs2_session'])
                self.assertEqual('completed' if point == 'result_saved' else 'unknown',
                                 request_result(loaded, body['request_id'])['status'])

    def test_intent_disk_failure_never_dispatches_and_rolls_back(self):
        self.ready()
        before = (self.root/'season.json').read_bytes()
        def fail(point):
            if point == 'before_commit': raise OSError('no disk space')
        with patch.object(tx, '_checkpoint', side_effect=fail), patch.object(matches, '_dispatch_launch') as dispatch:
            with self.assertRaises(OSError): match_launch.command(self.state, self.body())
        dispatch.assert_not_called()
        self.assertEqual(before, (self.root/'season.json').read_bytes())
        self.assertFalse(self.state.season.find_match(self.match_id)[1].get('cs2_session'))

    def test_failed_external_handoff_keeps_nonce_then_explicit_new_attempt_retires_it(self):
        self.ready()
        with patch.object(matches, '_dispatch_launch', side_effect=OSError('watcher failed')) as dispatch:
            result = match_launch.command(self.state, self.body())
        dispatch.assert_called_once()
        self.assertEqual('failed', result['status'])
        match = self.state.season.find_match(self.match_id)[1]
        old = match['cs2_session']['nonce']
        self.assertEqual('uncertain', match['cs2_session']['launch_state'])
        self.assertEqual(old, ApplicationState().season.find_match(self.match_id)[1]['cs2_session']['nonce'])
        match['cs2_session']['launch_requested_at'] = '2020-01-01T00:00:00Z'
        def restart(cfg, args, kwargs):
            self.assertNotEqual(old, kwargs['request_override']['nonce'])
            return dict(match=kwargs['request_override'], msg='new explicit attempt')
        with patch.object(matches, '_dispatch_launch', side_effect=restart):
            out = match_launch.command(self.state, self.body('launch-boundary-0002'))
        self.assertTrue(out['restarted_map'])
        self.assertEqual(old, match['career3d_retired_sessions'][-1]['session']['nonce'])

    def test_result_commit_failure_recovers_receipt_without_launching_again(self):
        self.ready()
        body = self.body()
        def dispatch(cfg, arguments, kwargs):
            def fail(point):
                if point == 'committed': raise OSError('replacement interrupted')
            self.stack.enter_context(patch.object(tx, '_checkpoint', side_effect=fail))
            return dict(match=kwargs['request_override'], msg='fake game launched')
        with patch.object(matches, '_dispatch_launch', side_effect=dispatch) as called:
            with self.assertRaises(tx.CommitPending): match_launch.command(self.state, body)
        called.assert_called_once()
        self.stack.enter_context(patch.object(tx, '_checkpoint'))
        loaded = ApplicationState()
        self.assertEqual('dispatched', loaded.season.find_match(self.match_id)[1]['cs2_session']['launch_state'])
        with patch.object(matches, '_dispatch_launch') as again:
            self.assertTrue(match_launch.command(loaded, body)['replayed'])
        again.assert_not_called()

    def test_real_http_adapter_and_header_receipt_do_not_commit_twice(self):
        self.ready()
        with self.serving(), patch.object(matches, '_dispatch_launch', side_effect=self.dispatch) as dispatch:
            body = dict(match_id=self.match_id, revision=0)
            code, result = self.request(match_launch.PATH, body, rid='launch-boundary-0001')
            self.assertEqual(200, code, result)
            code, replay = self.request(match_launch.PATH, body, rid='launch-boundary-0001')
            self.assertTrue(replay['replayed'])
            code, rejected = self.request(match_launch.PATH, dict(body, side='t'), rid='launch-boundary-0001')
            self.assertEqual(400, code, rejected)
        dispatch.assert_called_once()
        self.assertEqual(3, matches._revision(self.state))

    def test_nested_transaction_is_rejected_before_external_work(self):
        self.ready()
        with self.state.operation(), patch.object(matches, '_dispatch_launch') as dispatch:
            with self.assertRaisesRegex(RuntimeError, 'outside'):
                match_launch.command(self.state, self.body())
        dispatch.assert_not_called()

    def test_finished_cs2_dump_wins_simulation_request_without_playing_next_map(self):
        self.ready()
        with patch.object(matches, '_dispatch_launch', side_effect=self.dispatch):
            match_launch.command(self.state, self.body())
        match = self.state.season.find_match(self.match_id)[1]
        session = deepcopy(match['cs2_session'])
        raw = dict(schema_version=2, status='finished', complete=True, map=session['cs2_map'],
            request_nonce=session['nonce'], ended_at='2099-10-04T10:00:00Z', ct_score=13, t_score=6,
            players=[dict(player_id=pid, name=pid, team='ct' if i < 5 else 't',
                kills=10, deaths=10, assists=3, damage=1000, kast=.7, survived_rounds=9)
                for i, pid in enumerate(session['expected_player_ids'])])
        body = self.body('switch-simulate-0001')
        with patch.object(matches, '_peek', return_value=raw), \
             patch('cs2career.league.season.play_map', side_effect=AssertionError('collect only')):
            out = match_simulation.command(self.state, body)
            self.assertEqual('map_collected', out['status'])
            self.assertTrue(match_simulation.command(self.state, body)['replayed'])
        self.assertEqual(1, len(match['maps']))
        self.assertEqual('cs2', match['maps'][0]['source'])
        first = deepcopy(match['maps'][0])
        def dispatch(cfg, args, kwargs):
            return dict(match=kwargs['request_override'], msg='new explicit map')
        with patch.object(matches, '_peek', return_value=raw), patch.object(matches, '_dispatch_launch', side_effect=dispatch):
            match_launch.command(self.state, self.body('launch-second-map'))
        self.assertNotEqual(session['nonce'], match['cs2_session']['nonce'])
        with self.assertRaises(ValueError):
            self.state.season.commit_cs2_map(self.match_id, raw, result_reader=lambda **kwargs: raw)
        self.assertEqual([first], match['maps'])

    def test_abrupt_child_process_exit_preserves_each_external_handoff_boundary(self):
        worker = Path(__file__).parent/'fixtures/match_boundary_worker.py'
        for point in ('intent_saved', 'dispatch_saved', 'external_finished', 'result_saved'):
            with self.subTest(point=point):
                self.ready()
                result = subprocess.run([sys.executable, '-B', str(worker), str(self.root),
                    'launch', point, self.match_id], capture_output=True, timeout=20)
                self.assertEqual(73, result.returncode, result.stderr.decode('utf-8', errors='replace'))
                loaded = ApplicationState()
                session = loaded.season.find_match(self.match_id)[1]['cs2_session']
                self.assertTrue(session['nonce'])
                self.assertEqual(10, len(set(session['expected_player_ids'])))
                self.assertEqual('completed' if point == 'result_saved' else 'unknown',
                                 request_result(loaded, 'process-stop-0001')['status'])
                with patch.object(matches, '_dispatch_launch', side_effect=AssertionError('no implicit restart')):
                    self.assertTrue(match_launch.command(loaded, dict(match_id=self.match_id, revision=0,
                                    request_id='process-stop-0001'))['replayed'])
