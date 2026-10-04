"""Returning to a frozen match seat is not permission to restart its CS2 map."""
from copy import deepcopy
from http.server import ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.request import Request, urlopen

from tests import test_career3d_match_attendance as attendance_fixtures
from tools.career3d_matches import _identity, match_command, match_preflight
from tools.career3d_service import handler_class
from tools.career3d_venues import venue_for


class CareerSessionReturnTests(unittest.TestCase):
    def setUp(self):
        fixture = attendance_fixtures.CareerMatchAttendanceTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.c, self.s, self.m, self.e, self.state = (
            fixture.c, fixture.s, fixture.m, fixture.e, fixture.state)
        self.s.date = self.m['date']
        self.c.incident_state.update(seen={}, flags={})
        self.c.gate_match = Mock(return_value='')
        self.m.update(stage='G1', best_of=1, maps=[], pending_map='dust2', human=True,
            veto=dict(steps=[dict(team='Team0' if index % 2 == 0 else 'Team1',
                action='ban', map=name) for index, name in enumerate(
                ('ancient', 'nuke', 'mirage', 'inferno', 'train', 'overpass', 'anubis'))]
                + [dict(team=None, action='decider', map='dust2', play=1)],
                order=['dust2'], best_of=1), career3d_veto=dict(complete=True))
        _identity(self.state, self.m)
        venue = venue_for(self.state, self.e, self.m)
        self.m['cs2_session'] = dict(match_id=self.m['id'], map='dust2', cs2_map='de_dust2',
            side='ct', nonce='return-original-nonce', started_at='2026-10-03T03:53:05Z',
            map_index=0, expected_player_ids=[p['id'] for p in venue['players_a'] + venue['players_b']],
            venue=deepcopy(venue), career_identity=dict(year=self.s.year,
                event_id=self.e['id'], match_id=self.m['id'], key=venue['match_identity'],
                human_id=venue['human_id']))
        self.m['career3d_launch'] = dict(map_index=0, side='ct', settings=dict(difficulty='Low'))
        self.m['career3d_receipts'] = [dict(request_id='original-launch-request', action='launch',
            result=dict(status='waiting'))]

    def command(self, action='preflight', **values):
        return match_command(self.state, action, dict(match_id=self.m['id'], revision=0,
            request_id='return-seat-request', **values))

    def test_same_day_original_session_returns_waiting_without_any_write_or_launch(self):
        before = deepcopy(self.m)
        incident_before = deepcopy(self.c.incident_state)
        with patch('tools.career3d_matches._identity') as identity, \
             patch('tools.career3d_matches._init_veto') as veto, \
             patch('tools.career3d_matches._launch') as launch, \
             patch('cs2career.cs2.launch.build_request') as request, \
             patch('cs2career.cs2.launch.start_match') as start:
            view = match_preflight(self.state, self.m['id'])
            self.assertTrue(view['attendance']['can_return'])
            self.assertFalse(view['attendance']['can_travel'])
            self.assertEqual('launched', view['phase'])
            out = self.command()
            again = self.command()
        self.assertEqual(out, again)
        self.assertEqual('waiting', out['status'])
        for key in ('read_only', 'resume_only', 'replayed'):
            self.assertTrue(out[key])
        self.assertEqual('这场比赛正在进行，回到比赛电脑接续。', out['reason'])
        self.assertEqual('lan', out['preflight']['attendance']['return_destination'])
        self.assertEqual('frozen_match_rosters', out['preflight']['venue']['identity_source'])
        self.assertTrue(out['preflight']['venue']['travel_allowed'])
        self.assertTrue(out['preflight']['venue']['should_walk'])
        self.assertFalse(out['preflight']['can_launch'])
        # Waiting for a result still blocks launching; only the seat hand-off
        # is allowed. The legitimate completed-BP null turn is also retained.
        self.assertIn('等待真实 CS2 回传', out['preflight']['block_reason'])
        self.assertIsNone(out['preflight']['veto']['turn'])
        self.assertIsNone(out['preflight']['veto']['steps'][-1]['team'])
        self.assertEqual(before, self.m)
        self.assertEqual(incident_before, self.c.incident_state)
        for call in (identity, veto, launch, request, start, self.c.gate_match, self.state.persist):
            call.assert_not_called()

    def test_original_core_session_without_optional_3d_provenance_can_return(self):
        self.m['cs2_session'].pop('career_identity')
        self.m['cs2_session'].pop('venue')
        before = deepcopy(self.m)
        self.assertTrue(self.command()['resume_only'])
        self.assertEqual(before, self.m)

    def test_legacy_venue_presentation_refresh_preserves_frozen_roster_and_session(self):
        self.e.update(id='blast-bounty-2', name='BLAST Bounty Season 2 2026', type='premier')
        self.m.pop('career3d_venue')
        _identity(self.state, self.m)
        venue = venue_for(self.state, self.e, self.m)
        self.m['career3d_venue'].update(scale='unknown', is_lan=False,
            travel_allowed=False, visit_destination='club', should_walk=False)
        self.m['cs2_session'].update(venue=deepcopy(venue), career_identity=dict(
            year=self.s.year, event_id=self.e['id'], match_id=self.m['id'],
            key=venue['match_identity'], human_id=venue['human_id']))
        before = deepcopy(self.m)
        out = self.command()
        self.assertTrue(out['resume_only'])
        self.assertEqual('lan', out['preflight']['attendance']['destination'])
        self.assertEqual(before, self.m)

    def test_online_original_session_can_return_to_its_club_without_lan_permission(self):
        self.e.update(type='cct', name='CCT Europe Series')
        venue = venue_for(self.state, self.e, self.m)
        self.m['cs2_session']['venue'] = deepcopy(venue)
        before = deepcopy(self.m)
        out = self.command()
        self.assertTrue(out['resume_only'])
        self.assertEqual('club', out['preflight']['attendance']['return_destination'])
        self.assertFalse(out['preflight']['venue']['travel_allowed'])
        self.assertEqual(before, self.m)

    def test_partial_bo3_can_return_to_the_original_arena_without_restarting_its_next_map(self):
        self.m.update(stage='GF', best_of=3, maps=[dict(source='cs2', winner='Team0')])
        venue = venue_for(self.state, self.e, self.m)
        self.m['cs2_session'].update(map_index=1, venue=deepcopy(venue))
        self.m['career3d_launch']['map_index'] = 1
        before = deepcopy(self.m)
        out = self.command()
        self.assertTrue(out['resume_only'])
        self.assertEqual('major', out['preflight']['attendance']['return_destination'])
        self.assertEqual(1, out['preflight']['maps_done'])
        self.assertFalse(out['preflight']['can_launch'])
        self.assertEqual(before, self.m)

    def test_unsafe_session_or_frozen_identity_remains_paused_without_repreparing(self):
        original = deepcopy(self.m)
        changes = {
            'session_match': lambda: self.m['cs2_session'].update(match_id='different-match'),
            'missing_nonce': lambda: self.m['cs2_session'].pop('nonce'),
            'wrong_map_index': lambda: self.m['cs2_session'].update(map_index=1),
            'non_integer_map_index': lambda: self.m['cs2_session'].update(map_index=False),
            'missing_expected_ids': lambda: self.m['cs2_session'].pop('expected_player_ids'),
            'duplicate_expected_id': lambda: self.m['cs2_session']['expected_player_ids'].__setitem__(0, 'p0_1'),
            'changed_expected_id': lambda: self.m['cs2_session']['expected_player_ids'].__setitem__(0, 'replacement'),
            'missing_freeze': lambda: self.m.pop('career3d_venue'),
            'frozen_wrong_match': lambda: self.m['career3d_venue'].update(match_id='different-match'),
            'frozen_wrong_fixture_key': lambda: self.m['career3d_venue'].update(match_identity='2025:old:match-1'),
            'frozen_wrong_human': lambda: self.m['career3d_venue'].update(human_id='p0_1'),
            'frozen_wrong_team': lambda: self.m['career3d_venue'].update(own_team='Team1'),
            'frozen_wrong_team_a': lambda: self.m['career3d_venue'].update(team_a='Team1'),
            'short_roster': lambda: self.m['career3d_venue']['players_a'].pop(),
            'duplicate_frozen_id': lambda: self.m['career3d_venue']['players_a'][0].update(id='p0_1', player_id='p0_1'),
            'conflicting_frozen_id_fields': lambda: self.m['career3d_venue']['players_a'][0].update(id='replacement'),
            'missing_frozen_id': lambda: self.m['career3d_venue']['players_a'][0].pop('id'),
            'wrong_session_provenance': lambda: self.m['cs2_session']['career_identity'].update(key='wrong-fixture'),
            'wrong_session_venue': lambda: self.m['cs2_session']['venue']['players_a'][0].update(name='Wrong identity'),
        }
        with patch('tools.career3d_matches._identity') as identity, \
             patch('tools.career3d_matches._init_veto') as veto, \
             patch('tools.career3d_matches._launch') as launch:
            for name, change in changes.items():
                with self.subTest(guard=name):
                    self.m.clear()
                    self.m.update(deepcopy(original))
                    change()
                    before = deepcopy(self.m)
                    out = self.command()
                    self.assertEqual('paused', out['status'])
                    self.assertFalse(out.get('resume_only', False))
                    self.assertEqual(before, self.m)
        for call in (identity, veto, launch, self.c.gate_match, self.state.persist):
            call.assert_not_called()

    def test_genuine_career_blockers_still_pause_an_otherwise_valid_return(self):
        changes = {
            'training': lambda: setattr(self.c, 'training_session', {'pending': True}),
            'ladder': lambda: setattr(self.state.arena, 'pending', True),
            'story': lambda: self.c.story_queue.append(dict(id='must-decide')),
            'unsigned': lambda: setattr(self.c, 'unsigned', True),
            'loan': lambda: setattr(self.c, 'loan_default_pending', True),
            'fix': lambda: setattr(self.c, 'fix_pending', True),
            'transfer': lambda: self.c.personal_transfers.update(pending={'id': 'pending-transfer'}),
            'competition_pause': lambda: self.c.incident_state.update(competition_pause=dict(until='2026-06-22')),
            'ended_career': lambda: setattr(self.c, 'banned', True),
        }
        career_before = deepcopy(self.c.__dict__)
        for name, change in changes.items():
            with self.subTest(blocker=name):
                self.c.__dict__.clear()
                self.c.__dict__.update(deepcopy(career_before))
                self.state.arena.pending = False
                change()
                before = deepcopy(self.m)
                out = self.command()
                self.assertEqual('paused', out['status'])
                self.assertFalse(out.get('resume_only', False))
                self.assertTrue(out['reason'])
                self.assertEqual(before, self.m)
        self.state.persist.assert_not_called()

    def test_other_pending_session_cannot_be_ignored(self):
        other = dict(id='other-match', date=self.s.date, team_a='Team0', team_b='Team1',
                     played=False, cs2_session=dict(nonce='different-session'))
        self.e['matches'].append(other)
        before = deepcopy(self.e)
        out = self.command()
        self.assertEqual('paused', out['status'])
        self.assertIn('等待真实 CS2 回传', out['reason'])
        self.assertFalse(out.get('resume_only', False))
        self.assertEqual(before, self.e)

    def test_date_change_foreign_or_completed_match_cannot_return(self):
        original = deepcopy(self.m)
        self.s.date = '2026-06-22'
        self.assertEqual('paused', self.command()['status'])
        self.assertEqual(original, self.m)
        self.s.date = '2026-06-20'
        with self.assertRaisesRegex(ValueError, '还没到比赛日'):
            self.command()
        self.assertEqual(original, self.m)
        self.s.date = self.m['date']
        self.c.team_id = 'foreign-team'
        out = self.command()
        self.assertEqual('paused', out['status'])
        self.assertEqual('这不是你当前队伍的比赛。', out['preflight']['block_reason'])
        self.assertEqual(original, self.m)
        self.c.team_id = 't0'
        self.m['played'] = True
        with self.assertRaisesRegex(ValueError, '这场比赛已经结束'):
            self.command()

    def test_other_actions_keep_their_existing_session_gate(self):
        before = deepcopy(self.m)
        for action in ('veto', 'autoveto'):
            with self.subTest(action=action):
                out = self.command(action)
                self.assertEqual('paused', out['status'])
                self.assertFalse(out.get('resume_only', False))
                self.assertEqual(before, self.m)
        # Exiting now permits an explicit switch, but a live game never does.
        with patch('tools.career3d_activities._running_cs2', return_value=True), \
             patch('tools.career3d_matches._peek', return_value={'status': 'none'}):
            with self.assertRaisesRegex(ValueError, 'CS2 正在运行'):
                self.command('simulate')
        self.assertEqual(before, self.m)
        with patch('tools.career3d_matches.match_status', return_value=dict(status='waiting')) as status, \
             patch('tools.career3d_matches._launch') as launch:
            out = self.command('launch')
        self.assertEqual('waiting', out['status'])
        self.assertFalse(out.get('resume_only', False))
        self.assertEqual(before, self.m)
        status.assert_called_once_with(self.state, self.m['id'])
        launch.assert_not_called()

    def test_new_match_preflight_still_uses_the_original_prepare_and_career_gate(self):
        self.m.pop('cs2_session')
        self.m.pop('career3d_venue')
        with patch('tools.career3d_matches._identity', wraps=_identity) as identity, \
             patch('tools.career3d_matches._init_veto') as veto:
            out = self.command()
        self.assertEqual('ready', out['status'])
        self.assertFalse(out.get('read_only', False))
        self.assertFalse(out.get('resume_only', False))
        self.c.gate_match.assert_called_once_with(self.s, self.m['id'])
        identity.assert_called_once_with(self.state, self.m)
        veto.assert_called_once_with(self.state, self.e, self.m)
        self.assertEqual('return-seat-request', self.m['career3d_receipts'][-1]['request_id'])

    def test_return_still_checks_revision(self):
        before = deepcopy(self.m)
        with self.assertRaisesRegex(ValueError, '生涯状态已变化'):
            match_command(self.state, 'preflight', dict(match_id=self.m['id'], revision=99))
        self.assertEqual(before, self.m)

    def test_http_return_does_not_persist_increment_revision_or_record_receipt(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_class())
        server.state, server.token, server.state_lock = self.state, 'return-fixture-token', threading.RLock()
        server.game_disabled, server.display_hour = True, 8
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        before = deepcopy(self.m)
        incident_before = deepcopy(self.c.incident_state)
        try:
            with patch('tools.career3d_service.read_context', return_value=dict(date=self.s.date)), \
                 patch('tools.career3d_service._pause') as pause:
                for _ in range(2):
                    request = Request(f'http://127.0.0.1:{server.server_port}/api/3d/match/preflight',
                        data=json.dumps(dict(match_id=self.m['id'], revision=0,
                            request_id='http-return-request')).encode(),
                        headers={'Content-Type': 'application/json', 'X-Career-Token': server.token})
                    with urlopen(request, timeout=5) as response:
                        self.assertEqual(200, response.status)
                        out = json.load(response)
                    self.assertTrue(out['ok'])
                    self.assertTrue(out['read_only'])
                    self.assertTrue(out['resume_only'])
                    self.assertEqual('waiting', out['status'])
                pause.assert_not_called()
        finally:
            server.shutdown()
            worker.join()
            server.server_close()
        self.assertEqual(before, self.m)
        self.assertEqual(incident_before, self.c.incident_state)
        self.state.persist.assert_not_called()


if __name__ == '__main__':
    unittest.main()
