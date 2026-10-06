from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from cs2career.application import ApplicationState
from cs2career.career import Career
from cs2career.http_operations import execute
from cs2career.random_state import capture
from cs2career.storage import transaction as tx
from cs2career.storage.receipts import lookup


class CommandHandler:
    def __init__(self, state, request_id, action):
        self.state = state
        self.headers = {'X-Career-Request-ID': request_id}
        self.action = action
        self.responses = []

    def _body(self): return {'amount': 10}

    def _replay_result(self, result): return result

    def _post(self):
        self.action(self.state)
        self._json({'ok': True, 'amount': 10})

    def _json(self, value, code=200):
        if getattr(self, '_buffer_response', False):
            self._buffered_response = (deepcopy(value), code)
        else:
            self.responses.append((deepcopy(value), code))


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch('cs2career.league.season.STATE_PATH', self.root/'season.json'))
        self.stack.enter_context(patch.object(Career, 'path', return_value=self.root/'career.json'))
        self.stack.enter_context(patch('cs2career.paths.save_root', return_value=self.root))
        self.state = ApplicationState()
        self.state.persist()

    @staticmethod
    def spend(state):
        state.career.money += 10
        state.season.teams[0]['money'] -= 10
        # Intermediate domain saves must coalesce with the later receipt.
        for _ in range(11): state.persist()

    def test_money_and_receipt_commit_once_before_success_response(self):
        initial = self.state.career.money
        writes = []
        with patch.object(tx, '_checkpoint', side_effect=writes.append):
            first = CommandHandler(self.state, 'request-spend-0001', self.spend)
            execute(first, '/api/spend')
        self.assertEqual(200, first.responses[0][1])
        self.assertEqual(1, writes.count('staged:career.json'))
        self.assertEqual(1, writes.count('staged:season.json'))
        restarted = ApplicationState()
        second = CommandHandler(restarted, 'request-spend-0001', lambda s: self.fail('duplicate execution'))
        execute(second, '/api/spend')
        self.assertEqual(initial + 10, restarted.career.money)
        self.assertTrue(second.responses[0][0]['replayed'])
        self.assertIsNotNone(lookup(restarted.career, 'request-spend-0001'))

    def test_failure_before_commit_restores_memory_rng_and_disk(self):
        before = deepcopy((self.state.career.to_json(), self.state.season.to_json(), capture()))
        files = {p.name: p.read_bytes() for p in self.root.glob('*.json')}
        def fail(state):
            self.spend(state)
            random.random()
            raise ValueError('rejected')
        handler = CommandHandler(self.state, 'request-spend-0002', fail)
        execute(handler, '/api/spend')
        self.assertEqual(400, handler.responses[0][1])
        self.assertEqual(before, (self.state.career.to_json(), self.state.season.to_json(), capture()))
        self.assertEqual(files, {p.name: p.read_bytes() for p in self.root.glob('*.json')})

    def test_partial_replacement_recovers_receipt_and_never_repeats_money(self):
        initial = self.state.career.money
        def fail(point):
            if point == 'replaced:career.json': raise OSError('interrupted')
        with patch.object(tx, '_checkpoint', fail):
            handler = CommandHandler(self.state, 'request-spend-0003', self.spend)
            execute(handler, '/api/spend')
        self.assertEqual(503, handler.responses[0][1])
        self.assertEqual('storage_recovery_required', handler.responses[0][0]['error_code'])
        with self.assertRaises(tx.CommitPending):
            with self.state.operation(): pass
        restarted = ApplicationState()
        retry = CommandHandler(restarted, 'request-spend-0003', lambda s: self.fail('duplicate execution'))
        execute(retry, '/api/spend')
        self.assertEqual(initial + 10, restarted.career.money)
        self.assertTrue(retry.responses[0][0]['replayed'])

    def test_adapter_owned_commit_failure_also_blocks_the_holder(self):
        def fail(state):
            raise tx.CommitPending('adapter commit')
        handler = CommandHandler(self.state, 'external-request', fail)
        execute(handler, '/api/3d/settings/environment')
        self.assertEqual(503, handler.responses[0][1])
        self.assertEqual('storage_recovery_required', handler.responses[0][0]['error_code'])
        self.assertTrue(self.state._storage_failed)

    def test_explicit_rejection_rolls_back_queued_story_and_money(self):
        before = deepcopy((self.state.career.to_json(), self.state.season.to_json(), capture()))
        handler = CommandHandler(self.state, 'request-rejected', lambda s: None)
        def rejected():
            self.spend(self.state)
            self.state.career.story_queue.append({'id': 'invalid-story'})
            random.random()
            handler._json({'ok': False, 'msg': 'invalid input', 'context': {'stories': ['invalid-story']}}, 400)
        handler._post = rejected
        execute(handler, '/api/spend')
        self.assertEqual(400, handler.responses[0][1])
        self.assertNotIn('context', handler.responses[0][0])
        self.assertEqual(before, (self.state.career.to_json(), self.state.season.to_json(), capture()))
        self.assertIsNone(lookup(self.state.career, 'request-rejected'))

    def test_read_and_plain_save_never_schedule_gameplay(self):
        before = capture()
        with (patch.object(self.state.season, 'try_ingest_pending_cs2', side_effect=AssertionError('GET ingestion')),
              patch('cs2career.career.assistance.process_invites', side_effect=AssertionError('hidden invite')),
              patch('cs2career.career.assistance.process_points', side_effect=AssertionError('hidden points'))):
            self.state.payload()
            self.state.persist()
        self.assertEqual(before, capture())

    def test_live_match_query_does_not_choose_maps_or_mutate_player(self):
        self.state.create_career(dict(era='2026', mode='join', team_id=self.state.season.teams[0]['id'],
                                     replace=self.state.season.teams[0]['players'][0]['name']),
                                 story_seed='read-fixture')
        self.state.career.story_queue.clear()
        before = deepcopy((self.state.career.to_json(), self.state.season.to_json(), capture()))
        with patch.object(self.state.season, 'open_your_series', side_effect=AssertionError('query opened BP')):
            self.state.payload()
        self.assertEqual(before, (self.state.career.to_json(), self.state.season.to_json(), capture()))

    def test_post_commit_callback_failure_never_restores_old_memory(self):
        initial = self.state.career.money
        with self.assertRaises(tx.CommitPending):
            with self.state.operation():
                self.state.career.money += 10
                self.state.persist()
                tx.on_commit('failure', lambda: (_ for _ in ()).throw(ValueError('callback')))
        self.assertEqual(initial + 10, self.state.career.money)
        self.assertEqual(initial + 10, ApplicationState().career.money)

    def test_same_seed_and_story_input_reproduce_start_and_match(self):
        from cs2career.engine.match import RNG, play_map
        def run():
            random.seed(1337); RNG.seed(1337)
            self.state.create_career(dict(era='2026', mode='create', name='Replay', org='Replay Club',
                origin='academy', region='AS', role='rifle'), story_seed='fixture-story-1337')
            result = play_map(*self.state.season.teams[:2], 'dust2')
            return deepcopy((self.state.career.to_json(), self.state.season.to_json(), result))
        self.assertEqual(run(), run())
