from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_match_simulation_boundary as simulation_fixture
from cs2career.application import ApplicationState
from cs2career.league import season as season_module
from cs2career.services import matches, season_run
from cs2career.services.requests import request_result
from cs2career.storage import transaction as tx


class SeasonRunBoundaryTests(unittest.TestCase):
    setUp = simulation_fixture.MapSimulationBoundaryTests.setUp
    career_fixture = simulation_fixture.MapSimulationBoundaryTests.career_fixture
    quiet = simulation_fixture.MapSimulationBoundaryTests.quiet
    serving = simulation_fixture.MapSimulationBoundaryTests.serving
    request = simulation_fixture.MapSimulationBoundaryTests.request
    saved_match = simulation_fixture.MapSimulationBoundaryTests.saved_match

    def ready(self, size=3):
        match = simulation_fixture.MapSimulationBoundaryTests.ready(self, size)
        c, s = self.state.career, self.state.season
        c.assist.update(quick_mode=True, season_run={'year': s.year, 'status': 'running'})
        c.registered.append(s.events[0]['id'])
        s.events[0]['field'] = [match['team_a'], match['team_b']]
        self.state.persist()
        return match

    def body(self):
        return dict(request_id='quick-boundary-0001', revision=matches._revision(self.state), max_steps=1)

    def test_quick_bo3_and_bo5_save_each_map_but_return_one_complete_series(self):
        for size in (3, 5):
            with self.subTest(size=size):
                match = self.ready(size)
                played, calls = season_module.play_map, []
                def step(*args, **kwargs):
                    self.assertEqual(len(calls), len(self.saved_match()['maps']))
                    calls.append(args[2])
                    return played(*args, **kwargs)
                with patch.object(season_module, 'play_map', side_effect=step):
                    out = season_run.command(self.state, self.body())
                self.assertEqual('played', out['status'], out.get('reason'))
                self.assertEqual(1, out['steps'])
                self.assertEqual(1, len(out['results']))
                self.assertEqual(len(calls), len(out['reveal']['maps']))
                self.assertEqual(match['maps'], self.saved_match()['maps'])
                self.assertEqual('completed', request_result(ApplicationState(), self.body()['request_id'])['status'])

    def test_final_still_requires_choice_and_does_not_simulate(self):
        match = self.ready()
        match['stage'] = 'GF'
        with patch.object(season_module, 'play_map', side_effect=AssertionError('final needs a choice')):
            out = season_run.command(self.state, self.body())
        self.assertEqual('decision', out['status'])
        self.assertFalse(match['maps'])
        self.assertTrue(ApplicationState().career.story_queue)

    def test_failure_after_first_map_can_continue_with_new_request_without_reroll(self):
        self.ready()
        baseline = {p: p.read_bytes() for p in (self.root/'career.json', self.root/'season.json')}
        body = self.body()
        expected = season_run.command(self.state, body)['result']['maps']
        tx.commit(baseline)
        self.state = ApplicationState()
        self.quiet(self.state)
        def stop(point):
            if point == 'step_saved:1': raise KeyboardInterrupt('closed background process')
        with patch.object(season_run, '_checkpoint', side_effect=stop):
            with self.assertRaises(KeyboardInterrupt): season_run.command(self.state, body)
        loaded = ApplicationState()
        self.quiet(loaded)
        first = deepcopy(loaded.season.find_match(self.match_id)[1]['maps'])
        self.assertEqual(1, len(first))
        self.assertEqual('unknown', request_result(loaded, body['request_id'])['status'])
        with patch.object(season_module, 'play_map', side_effect=AssertionError('no automatic retry')):
            self.assertTrue(season_run.command(loaded, body)['replayed'])
        result = season_run.command(loaded, dict(body, request_id='quick-continue-0002', revision=matches._revision(loaded)))
        self.assertEqual('played', result['status'])
        self.assertEqual(expected, result['result']['maps'])
        self.assertEqual(first[0], loaded.season.find_match(self.match_id)[1]['maps'][0])
        self.assertEqual(1, result['reveal']['maps'][0]['index'])

    def test_real_http_fast_run_and_receipt_replay_use_separate_checkpoint_boundary(self):
        self.ready()
        with self.serving():
            body = self.body()
            code, out = self.request(season_run.PATH, body)
            self.assertEqual(200, code, out.get('msg'))
            self.assertEqual('played', out['status'])
            saved = (self.root/'season.json').read_bytes()
            code, again = self.request(season_run.PATH, body)
            self.assertEqual(200, code)
            self.assertTrue(again['replayed'])
            self.assertEqual(saved, (self.root/'season.json').read_bytes())

    def test_abrupt_quick_process_exit_only_commits_first_map(self):
        self.ready()
        worker = Path(__file__).parent/'fixtures/match_boundary_worker.py'
        result = subprocess.run([sys.executable, '-B', str(worker), str(self.root),
            'quick', 'step_saved:1', self.match_id], capture_output=True, timeout=20)
        self.assertEqual(73, result.returncode, result.stderr.decode('utf-8', errors='replace'))
        loaded = ApplicationState()
        self.assertEqual(1, len(loaded.season.find_match(self.match_id)[1]['maps']))
        self.assertEqual('unknown', request_result(loaded, 'process-stop-0001')['status'])

    def test_legacy_quick_receipt_is_checked_before_generating_child_tokens(self):
        self.ready()
        body = self.body()
        matches._store(self.state)['season_receipts'] = [
            dict(request_id=body['request_id'], action='run',
                 identity={key: body.get(key) for key in ('year', 'quick_mode', 'max_steps', 'break_key')},
                 result=dict(status='played', reason='old saved result'))]
        with patch.object(season_module, 'play_map', side_effect=AssertionError('legacy duplicate')):
            out = season_run.command(self.state, dict(body, revision=-1))
            self.assertTrue(out['replayed'])
            with self.assertRaises(ValueError):
                season_run.command(self.state, dict(body, max_steps=2))
        self.assertFalse(self.state.season.find_match(self.match_id)[1]['maps'])
