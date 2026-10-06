from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_recovery_http as http_fixture
from cs2career.application import ApplicationState
from cs2career.engine.match import RNG
from cs2career.league import season as season_module
from cs2career.services import match_simulation, matches
from cs2career.services.requests import request_result
from cs2career.storage import transaction as tx
from cs2career.storage.receipts import lookup


class MapSimulationBoundaryTests(unittest.TestCase):
    setUp = http_fixture.RecoveryHttpTests.setUp
    career_fixture = http_fixture.RecoveryHttpTests.career_fixture
    serving = http_fixture.RecoveryHttpTests.serving
    request = http_fixture.RecoveryHttpTests.request

    def ready(self, best_of=3):
        c, s, match = self.career_fixture()
        match['best_of'] = best_of
        self.stack.enter_context(patch('tools.career3d_activities.config_status', return_value=dict(ready=False, reason='fixture')))
        self.stack.enter_context(patch('tools.career3d_activities._running_cs2', return_value=False))
        self.stack.enter_context(patch('cs2career.league.phases.emit'))
        self.quiet(self.state)
        matches.match_command(self.state, 'autoveto', dict(match_id=match['id'], revision=0))
        RNG.seed(819)
        self.state.persist()
        self.match_id = match['id']
        return match

    def quiet(self, state):
        self.stack.enter_context(patch.object(state.career, 'gate_match', return_value=''))
        self.stack.enter_context(patch.object(state, '_reconcile', state.persist))

    def body(self, rid='map-boundary-0001'):
        return dict(match_id=self.match_id, revision=matches._revision(self.state), request_id=rid)

    def saved_match(self):
        data = json.loads((self.root/'season.json').read_text('utf-8'))
        return next(m for e in data['events'] for m in e['matches'] if m['id'] == self.match_id)

    def test_bo3_and_bo5_commit_every_map_before_starting_next_and_reveal_whole_series(self):
        for size in (3, 5):
            with self.subTest(best_of=size):
                match = self.ready(size)
                played, finished = season_module.play_map, []
                def step(*args, **kwargs):
                    self.assertEqual(len(finished), len(self.saved_match()['maps']))
                    box = played(*args, **kwargs)
                    finished.append(box)
                    return box
                with patch.object(season_module, 'play_map', side_effect=step):
                    out = match_simulation.command(self.state, self.body())
                self.assertTrue(match['played'])
                self.assertEqual('finished', out['status'])
                self.assertGreaterEqual(len(finished), size//2+1)
                self.assertEqual(len(finished), len(out['reveal']['maps']))
                self.assertEqual(match['maps'], self.saved_match()['maps'])
                self.assertEqual(len(finished), len({row['session_id'] for row in match['maps']}))
                loaded = ApplicationState()
                self.assertEqual('completed', request_result(loaded, self.body()['request_id'])['status'])

    def test_second_map_failure_preserves_first_map_and_rng_then_new_request_continues(self):
        self.ready()
        baseline = {p: p.read_bytes() for p in (self.root/'career.json', self.root/'season.json')}
        body = self.body()
        expected = match_simulation.command(self.state, body)['result']['maps']
        tx.commit(baseline)
        self.state = ApplicationState()
        self.quiet(self.state)
        played, count = season_module.play_map, 0
        def step(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                RNG.random()  # Also prove failed simulation restores its RNG.
                raise OSError('fixture interrupted second map')
            return played(*args, **kwargs)
        with patch.object(season_module, 'play_map', side_effect=step):
            with self.assertRaises(OSError): match_simulation.command(self.state, body)
        first = deepcopy(self.saved_match()['maps'])
        self.assertEqual(1, len(first))
        self.assertEqual('unknown', request_result(self.state, body['request_id'])['status'])
        loaded = ApplicationState()
        self.quiet(loaded)
        with patch.object(season_module, 'play_map', side_effect=AssertionError('no write replay')):
            self.assertTrue(match_simulation.command(loaded, body)['replayed'])
        remaining = dict(body, request_id='map-boundary-0002', revision=matches._revision(loaded))
        result = match_simulation.command(loaded, remaining)
        self.assertEqual(expected, result['result']['maps'])
        self.assertEqual(first[0], loaded.season.find_match(self.match_id)[1]['maps'][0])
        money = loaded.career.money
        self.assertTrue(match_simulation.command(loaded, remaining)['replayed'])
        self.assertEqual(money, loaded.career.money)

    def test_first_map_story_pause_and_receipt_commit_together(self):
        match = self.ready()
        def incident(season, event, current, phase, index=None):
            if phase == 'map_finished':
                self.state.career.story_queue.append(dict(id='map-story', kind='incident',
                                                         trigger='map_finished', timing='match'))
        with patch('cs2career.league.phases.emit', side_effect=incident):
            out = match_simulation.command(self.state, self.body())
        self.assertEqual('paused', out['status'])
        self.assertEqual(1, len(match['maps']))
        loaded = ApplicationState()
        self.assertEqual('map-story', loaded.career.story_queue[0]['id'])
        self.assertEqual('completed', request_result(loaded, self.body()['request_id'])['status'])

    def test_commit_interruption_recovers_only_current_map_and_does_not_simulate_more(self):
        self.ready()
        def stop(point):
            if point == 'committed': raise OSError('fixture killed at commit')
        with patch.object(tx, '_checkpoint', side_effect=stop):
            with self.assertRaises(tx.CommitPending): match_simulation.command(self.state, self.body())
        loaded = ApplicationState()
        self.assertEqual(1, len(loaded.season.find_match(self.match_id)[1]['maps']))
        self.assertEqual('pending', lookup(loaded.career, self.body()['request_id'])['phase'])
        self.assertTrue(self.state._storage_failed)

    def test_finished_cs2_map_is_preserved_and_http_replay_does_not_settle_again(self):
        match = self.ready()
        a, b = [next(t for t in self.state.season.teams if t['name'] == match[k]) for k in ('team_a', 'team_b')]
        first = season_module.play_map(a, b, match['veto']['order'][0])
        first.update(source='cs2', request_nonce='already-collected')
        match['maps'].append(deepcopy(first))
        self.state.season.open_your_series(self.state.season.events[0], match)
        self.state.persist()
        body = self.body()
        with self.serving():
            code, out = self.request(match_simulation.PATH, body)
            self.assertEqual(200, code, out)
            self.assertEqual(1, out['reveal']['maps'][0]['index'])
            saved = (self.root/'season.json').read_bytes()
            code, replay = self.request(match_simulation.PATH, body)
            self.assertEqual(200, code, replay)
            self.assertTrue(replay['replayed'])
            self.assertEqual(saved, (self.root/'season.json').read_bytes())
        self.assertEqual(first, self.saved_match()['maps'][0])

    def test_abrupt_process_exit_after_map_keeps_score_without_running_next_map(self):
        self.ready()
        worker = Path(__file__).parent/'fixtures/match_boundary_worker.py'
        result = subprocess.run([sys.executable, '-B', str(worker), str(self.root),
            'simulate', 'map_saved:1', self.match_id], capture_output=True, timeout=20)
        self.assertEqual(73, result.returncode, result.stderr.decode('utf-8', errors='replace'))
        loaded = ApplicationState()
        self.assertEqual(1, len(loaded.season.find_match(self.match_id)[1]['maps']))
        self.assertEqual('unknown', request_result(loaded, 'process-stop-0001')['status'])
