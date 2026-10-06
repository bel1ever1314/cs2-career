"""Real operation/save boundaries behind both authenticated HTTP adapters."""
from contextlib import contextmanager
from copy import deepcopy
import json
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import test_operation_boundary as boundary
from cs2career.application import ApplicationState
from cs2career.career import Career
from cs2career.http_operations import transactional
from cs2career.storage import transaction as tx
from cs2career.storage.receipts import lookup
from cs2career.web.server import create_server
from tools.career3d_service import handler_class


class RecoveryHttpTests(unittest.TestCase):
    setUp = boundary.OperationTests.setUp  # Disposable save paths; no production state.

    @contextmanager
    def serving(self, *, desktop=True, restart=False):
        server = create_server(self.state)
        server.display_hour = 8
        server.game_disabled = True
        server.restart_on_storage_failure = restart
        if desktop: server.RequestHandlerClass = handler_class()
        worker = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        worker.start()
        self.server = server
        try:
            yield worker
        finally:
            server.shutdown()
            worker.join(timeout=3)
            server.server_close()
            self.assertFalse(worker.is_alive(), 'HTTP fixture did not stop')

    def request(self, path, body=None, rid='http-request-0001', authorized=True):
        req = Request(f'http://127.0.0.1:{self.server.server_port}' + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type': 'application/json', 'X-Career-Request-ID': rid,
                     'X-Career-Token': self.server.token if authorized else 'wrong'})
        try:
            with urlopen(req, timeout=10) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def career_fixture(self):
        team = self.state.season.teams[0]
        self.state.create_career(dict(era='2026', mode='join', team_id=team['id'],
                                     replace=team['players'][0]['name']), story_seed='http-fixture')
        c, s = self.state.career, self.state.season
        c.story_queue.clear()
        c.fix_pending = False
        c.fix_rolled = ''
        mine = c.my_team(s.teams)
        opponent = next(t for t in s.teams if t['id'] != mine['id'])
        event = deepcopy(s.events[0])
        event.update(id='fixture-event', status='live')
        match = dict(id='fixture-match', date=s.date, stage='QF', best_of=3, played=False, winner=None, series='',
                     team_a=mine['name'], team_b=opponent['name'], maps=[])
        event['matches'] = [match]
        s.events = [event]
        self.state.persist()
        # Keep assertions about the command boundary, not unrelated invitations
        # or passive auto-spending. The actual gate/phase/save implementations run.
        self.stack.enter_context(patch.object(self.state, '_reconcile', self.state.persist))
        self.stack.enter_context(patch('tools.career3d_start.requires_creation', return_value=False))
        self.stack.enter_context(patch('tools.career3d_attribute_draw.draw_context', return_value={}))
        return c, s, match

    def test_commit_fault_returns_code_then_stops_owned_service_and_recovers_receipt(self):
        self.career_fixture()
        money = self.state.career.money
        def spend(state, body):
            state.career.money += 10
            state.persist()
            return {'reason': 'fixture saved'}
        def crash(point):
            if point == 'replaced:career.json': raise OSError('fixture sharing error')
        with self.serving(restart=True) as worker, patch('tools.career3d_activities.spend_attributes', spend), patch.object(tx, '_checkpoint', crash):
            status, out = self.request('/api/3d/attr', {})
            self.assertEqual(503, status, out)
            self.assertEqual('storage_recovery_required', out['error_code'])
            self.assertNotIn('context', out)
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
        self.assertTrue(self.state._storage_failed)
        restarted = ApplicationState()
        self.assertEqual(money + 10, restarted.career.money)
        self.assertIsNotNone(lookup(restarted.career, 'http-request-0001'))

    def test_settings_propagates_pending_through_3d_catch_all(self):
        with self.serving(), patch('tools.career3d_activities.settings_command', side_effect=tx.CommitPending('saved')):
            status, out = self.request('/api/3d/settings', {})
            self.assertEqual(503, status)
            self.assertEqual('storage_recovery_required', out['error_code'])
            for path, body in (('/api/3d/context', None), ('/api/3d/attr', {}), ('/api/3d/requests?id=x', None)):
                code, blocked = self.request(path, body)
                self.assertEqual(503, code)
                self.assertEqual(out['error_code'], blocked['error_code'])
            self.assertEqual(403, self.request('/api/3d/attr', {}, authorized=False)[0])

    def test_outbox_acknowledgement_fault_returns_recovery_code_after_domain_commit(self):
        self.career_fixture()
        from cs2career.services import external_effects as effects
        money = self.state.career.money
        def spend(state, body):
            state.career.money += 10
            effects.enqueue(state, 'retire_match', self.root/'game', 'retired')
            state.persist()
            return {'reason': 'saved'}
        def deliver(state, item):
            self.assertEqual(money + 10, ApplicationState().career.money)
            raise tx.CommitPending('acknowledgement needs recovery')
        with self.serving(), patch('tools.career3d_activities.spend_attributes', spend), patch.object(effects, '_deliver', deliver):
            status, out = self.request('/api/3d/attr', {})
            self.assertEqual(503, status, out)
            self.assertEqual('storage_recovery_required', out['error_code'])
        self.assertEqual(money + 10, ApplicationState().career.money)

    def test_expected_story_pause_is_committed_and_replay_does_not_reroll(self):
        for desktop in (False, True):
            with self.subTest(desktop=desktop):
                c, s, match = self.career_fixture()
                endpoint = '/api/3d/match/simulate' if desktop else '/api/series/skip'
                with self.serving(desktop=desktop), patch('random.random', return_value=0):
                    code, out = self.request(endpoint, {'match_id': match['id']}, rid=f'story-gate-{desktop}')
                    self.assertEqual(200, code, out)
                    self.assertTrue(out['ok'])
                    self.assertEqual('paused', out['status'])
                    self.assertTrue(c.fix_pending)
                    self.assertTrue(c.story_queue)
                    self.assertFalse(match['maps'])
                    before = deepcopy(c.story_queue)
                    code, replay = self.request(endpoint, {'match_id': match['id']}, rid=f'story-gate-{desktop}')
                    self.assertTrue(replay['replayed'])
                    self.assertEqual(before, c.story_queue)
                loaded = ApplicationState()
                self.assertTrue(loaded.career.fix_pending)
                self.assertEqual(before, loaded.career.story_queue)
                self.assertIsNotNone(lookup(loaded.career, f'story-gate-{desktop}'))

    def test_existing_story_does_not_turn_validation_error_into_success(self):
        self.career_fixture()
        self.state.career.story_queue = [{'id': 'existing-story'}]
        self.state.persist()
        before = deepcopy(self.state.career.to_json())
        disk_before = (self.root/'career.json').read_bytes()
        def reject(state, action, body, **kwargs):
            state.career.money += 999
            state.career.story_queue.append({'id': 'invalid-new-story'})
            state.persist()
            raise ValueError('invalid match input')
        with self.serving(), patch('cs2career.services.matches.match_command', reject):
            code, out = self.request('/api/3d/match/simulate', {'match_id': 'fixture-match'})
        self.assertEqual(400, code)
        self.assertFalse(out['ok'])
        self.assertNotIn('context', out)
        self.assertEqual(before, self.state.career.to_json())
        self.assertEqual(disk_before, (self.root/'career.json').read_bytes())

    def test_map_phase_pause_saves_story_without_starting_cs2(self):
        c, s, match = self.career_fixture()
        launch = Mock(side_effect=AssertionError('A paused phase must not launch CS2'))
        def phase(season, event, current, phase_name, index=None):
            if phase_name == 'map_started':
                c.story_queue.append({'id': 'phase-incident', 'kind': 'incident',
                                      'trigger': 'map_started', 'timing': 'match'})
        with patch.object(c, 'gate_match', return_value=''), patch('cs2career.league.phases.emit', phase):
            message = self.state.run(s.launch_your_map, match['id'],
                                     result_reader=lambda **kw: None, launcher=launch)
        self.assertTrue(message)
        launch.assert_not_called()
        self.assertEqual('phase-incident', ApplicationState().career.story_queue[0]['id'])
        self.assertFalse(match.get('cs2_session'))
        self.assertFalse(match['maps'])

    def test_match_http_has_one_receipt_and_replays_without_a_second_attendance(self):
        _, _, match = self.career_fixture()
        with self.serving():
            code, out = self.request('/api/3d/match/attend', dict(match_id=match['id'], revision=0,
                                                              request_id='attend-fixture-0001'))
            self.assertEqual(200, code, out)
            self.assertFalse(match.get('career3d_receipts'))
            self.assertIsNotNone(lookup(self.state.career, 'attend-fixture-0001'))
            before = deepcopy(match['career3d_attendance'])
            code, replay = self.request('/api/3d/match/attend', dict(match_id=match['id'], revision=0,
                                                                 request_id='attend-fixture-0001'))
            self.assertEqual(200, code, replay)
            self.assertTrue(replay['replayed'])
            self.assertEqual(before, match['career3d_attendance'])

    def test_excluded_route_inventory_is_explicit(self):
        for path in ('/api/3d/settings/environment', '/api/3d/start/draw', '/api/3d/saves/load',
                     '/api/cs2/config', '/api/arena/pick',
                     '/api/tactics/save', '/api/3d/match/launch', '/api/3d/match/simulate', '/api/3d/season/run'):
            self.assertFalse(transactional(path), path)
        for path in ('/api/3d/settings', '/api/3d/start/create', '/api/3d/ladder/simulate', '/api/3d/calendar',
                     '/api/3d/story', '/api/3d/environment/facility', '/api/3d/skin-tools/stickers', '/api/3d/tactics/import'):
            self.assertTrue(transactional(path), path)
