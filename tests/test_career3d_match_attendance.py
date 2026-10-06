from application_double import ApplicationDouble
"""Fixture-date attendance plans, morning stops and read-only venue guidance."""
from copy import deepcopy
from http.server import ThreadingHTTPServer
import json
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cs2career.career import Career
from tools.career3d_matches import _identity, match_command, match_preflight, season_command
from tools.career3d_service import _due_player_match, advance_calendar, handler_class
from tools.career3d_venues import attendance_for, venue_for


def roster(index):
    return dict(id=f't{index}', name=f'Team{index}', players=[
        dict(player_id=f'p{index}_{slot}', name=f'Player {index}-{slot}', role=role)
        for slot, role in enumerate(('rifle', 'entry', 'awp', 'lurk', 'igl'))])


class CareerMatchAttendanceTests(unittest.TestCase):
    def setUp(self):
        self.c = Career()
        self.c.exists, self.c.team_id, self.c.player_name = True, 't0', 'Player 0-0'
        self.c.save = Mock()
        self.m = dict(id='match-1', date='2026-06-21', stage='GF', best_of=3,
                      team_a='Team0', team_b='Team1', played=False)
        self.e = dict(id='major-1', name='IEM Cologne Major 2026', type='major',
                      dates=['2026-06-21'], status='live', matches=[self.m])
        self.s = SimpleNamespace(date='2026-06-19', year=2026, era='2026',
                                 teams=[roster(0), roster(1)], events=[self.e])
        self.s.your_team_name = lambda: (self.c.my_team(self.s.teams) or {}).get('name', '')
        self.s.is_yours = lambda m: self.s.your_team_name() in (m['team_a'], m['team_b'])
        # Deliberately retain the core's open-veto readiness exception. The 3D
        # adapter must enforce the fixture date even on legacy opened series.
        self.s.yours_ready = lambda m: bool(self.s.is_yours(m) and not m.get('played') and
            (m['date'] <= self.s.date or m.get('human') or m.get('veto') or m.get('maps')))
        self.s.find_match = lambda ident: next(((e, m) for e in self.s.events for m in e['matches']
                                               if m['id'] == ident), (None, None))
        self.s._live_series = lambda m: None
        self.s._require_yours = Mock()
        self.s._next_busy_day = lambda: self.m['date']
        self.s.career = self.c
        self.state = ApplicationDouble(career=self.c, season=self.s,
            arena=SimpleNamespace(pending=False, career_player_id=lambda state: 'p0_0'), persist=Mock())
        self.config = patch('tools.career3d_activities.config_status', return_value=dict(ready=True, reason=''))
        self.config.start()
        self.addCleanup(self.config.stop)

    def attend(self, request='attend-request-1'):
        return match_command(self.state, 'attend', dict(match_id=self.m['id'], revision=0,
                                                      request_id=request))

    def test_future_context_has_actual_date_and_named_destination_without_mutation(self):
        before = deepcopy(self.e)
        view = match_preflight(self.state)
        self.assertEqual(self.m['id'], view['match_id'])
        self.assertEqual('scheduled', view['phase'])
        self.assertFalse(view['due'])
        self.assertFalse(view['can_launch'])
        self.assertEqual('2026-06-21', view['attendance']['sleep_target'])
        self.assertEqual('LANXESS arena', view['attendance']['display_name'])
        self.assertEqual('major', view['attendance']['destination'])
        self.assertEqual(before, self.e)

    def test_attend_only_records_personal_intent_without_veto_date_or_roster_freeze(self):
        before = deepcopy(self.e)
        result = self.attend()
        self.assertEqual('planned', result['status'])
        self.assertTrue(result['attendance']['planned'])
        self.assertIn('2026-06-21', result['reason'])
        self.assertEqual('2026-06-19', self.s.date)
        for key in ('human', 'veto', 'career3d_identity', 'career3d_venue', 'cs2_session'):
            self.assertNotIn(key, self.m)
        after = deepcopy(self.e)
        after['matches'][0].pop('career3d_attendance')
        after['matches'][0].pop('career3d_receipts')
        self.assertEqual(before, after)
        self.s._require_yours.assert_not_called()
        self.state.persist.assert_not_called()

    def test_plan_survives_save_roundtrip_and_old_saves_need_no_migration(self):
        self.assertFalse(attendance_for(self.state, self.e, self.m)['planned'])
        self.attend()
        self.m.update(json.loads(json.dumps(self.m)))
        self.assertTrue(attendance_for(self.state, self.e, self.m)['planned'])
        self.s.teams[0]['players'][1]['name'] = 'New teammate'
        self.assertEqual('New teammate', venue_for(self.state, self.e, self.m)['players_a'][1]['name'])

    def test_attend_retry_refreshes_day_state_without_recording_second_plan(self):
        first = self.attend()
        self.s.date = self.m['date']
        self.c.incident_state.setdefault('career3d_service', dict(receipts=[], revision=0))['revision'] = 2
        result = self.attend()
        self.assertTrue(result['replayed'])
        self.assertEqual('scheduled', first['attendance']['phase'])
        self.assertEqual('today', result['attendance']['phase'])
        self.assertTrue(result['attendance']['can_travel'])
        self.assertEqual(1, len(self.m['career3d_receipts']))

    def test_finished_or_foreign_match_cannot_start_an_attendance_plan(self):
        self.m['played'] = True
        with self.assertRaisesRegex(ValueError, '已经结束'):
            self.attend()
        self.m['played'] = False
        self.m['team_a'] = 'Other team'
        with self.assertRaisesRegex(ValueError, '不是你当前队伍'):
            self.attend()
        self.assertNotIn('career3d_attendance', self.m)

    def test_finished_attend_receipt_does_not_resurrect_a_completed_match(self):
        self.attend()
        self.m['played'] = True
        with self.assertRaisesRegex(ValueError, '已经结束'):
            self.attend()
        done = match_preflight(self.state, self.m['id'])
        self.assertEqual('finished', done['attendance']['phase'])
        self.assertFalse(done['attendance']['planned'])
        self.assertFalse(done['attendance']['can_travel'])

    def test_revision_and_running_match_guard_personal_intent(self):
        with self.assertRaises(ValueError):
            match_command(self.state, 'attend', dict(match_id=self.m['id'], revision=9))
        self.state.arena.pending = True
        with self.assertRaisesRegex(ValueError, '正在进行'):
            self.attend()
        self.assertNotIn('career3d_attendance', self.m)

    def test_early_open_veto_cannot_launch_freeze_or_mark_match_due(self):
        self.m.update(human=True, veto=dict(order=['Dust2'], steps=[]))
        self.assertTrue(self.s.yours_ready(self.m))
        self.assertIsNone(_due_player_match(self.state))
        info = match_preflight(self.state)
        self.assertFalse(info['due'])
        self.assertFalse(info['can_launch'])
        self.assertFalse(info['venue']['should_walk'])
        for action in ('preflight', 'autoveto', 'launch'):
            with self.assertRaisesRegex(ValueError, '还没到比赛日'):
                match_command(self.state, action, dict(match_id=self.m['id'], revision=0))
        self.assertNotIn('career3d_venue', self.m)

    def test_frozen_venue_recomputes_actual_day_and_preserves_rosters(self):
        _identity(self.state, self.m)
        frozen = deepcopy(self.m['career3d_venue']['players_a'])
        self.assertFalse(venue_for(self.state, self.e, self.m)['should_walk'])
        self.s.date = self.m['date']
        self.s.teams[0]['players'][1]['name'] = 'Later name'
        current = venue_for(self.state, self.e, self.m)
        self.assertTrue(current['should_walk'])
        self.assertEqual(frozen, current['players_a'])

    def test_small_online_and_unknown_games_have_concrete_place_labels(self):
        self.m['stage'] = 'M1-SW1'
        studio = attendance_for(self.state, self.e, self.m)
        self.assertEqual(('lan', '小型赛场'), (studio['destination'], studio['display_name']))
        self.e.update(id='cct-test', name='CCT Europe Series', type='cct')
        online = attendance_for(self.state, self.e, self.m)
        self.assertEqual(('club', '俱乐部训练室'), (online['destination'], online['display_name']))
        self.e.update(id='other', name='Scheduled tournament', type='t1')
        self.assertEqual('lan', attendance_for(self.state, self.e, self.m)['destination'])
        self.assertFalse(venue_for(self.state, self.e, self.m)['verified'])

    def test_plan_is_not_reused_after_transfer_or_player_identity_change(self):
        self.attend()
        self.state.arena.career_player_id = lambda state: 'p0_2'
        self.assertFalse(attendance_for(self.state, self.e, self.m)['planned'])
        self.state.arena.career_player_id = lambda state: 'p0_0'
        self.c.team_id = 'foreign-team'
        self.assertFalse(attendance_for(self.state, self.e, self.m)['planned'])

    def test_qualifier_and_cct_due_games_can_prepare_at_club_without_lan_permissions(self):
        self.m['stage'] = 'R16'
        for ident, name, kind in (('qual-test', 'Open qualifier', 'qual'),
                                  ('cct-test', 'CCT Europe Series', 'cct')):
            with self.subTest(event=ident):
                self.e.update(id=ident, name=name, type=kind)
                self.s.date = '2026-06-19'
                self.assertFalse(attendance_for(self.state, self.e, self.m)['can_travel'])
                self.s.date = self.m['date']
                view = match_preflight(self.state, self.m['id'])
                self.assertEqual('club', view['attendance']['destination'])
                self.assertTrue(view['attendance']['due'])
                self.assertTrue(view['attendance']['can_travel'])
                self.assertFalse(view['venue']['travel_allowed'])
                self.assertFalse(view['venue']['should_walk'])
                self.assertEqual('', view['block_reason'])

    def test_in_progress_keeps_identity_but_does_not_offer_a_second_arrival(self):
        self.attend()
        self.s.date = self.m['date']
        self.m['maps'] = [dict(source='cs2')]
        view = attendance_for(self.state, self.e, self.m)
        self.assertTrue(view['is_today'])
        self.assertTrue(view['due'])
        self.assertTrue(view['planned'])
        self.assertEqual('in_progress', view['phase'])
        self.assertFalse(view['can_travel'])
        self.assertTrue(view['can_resume'])
        self.assertTrue(view['can_return'])
        self.assertEqual('major', view['return_destination'])

    def test_partial_frozen_series_can_return_to_same_club_or_lan_without_refreeze(self):
        self.s.date = self.m['date']
        for ident, name, kind, destination in (('major-1', 'IEM Cologne Major 2026', 'major', 'major'),
                                             ('cct-test', 'CCT Europe Series', 'cct', 'club')):
            with self.subTest(event=ident):
                self.m.pop('career3d_venue', None)
                self.e.update(id=ident, name=name, type=kind)
                self.m['stage'] = 'R16' if destination == 'club' else 'GF'
                _identity(self.state, self.m)
                self.m['maps'] = [dict(source='cs2')]
                frozen = deepcopy(self.m['career3d_venue'])
                view = match_preflight(self.state, self.m['id'])
                self.assertTrue(view['attendance']['can_resume'])
                self.assertTrue(view['attendance']['can_return'])
                self.assertEqual(destination, view['attendance']['return_destination'])
                self.assertFalse(view['attendance']['can_travel'])
                self.assertEqual('frozen_match_rosters', view['venue']['identity_source'])
                self.assertEqual(frozen, self.m['career3d_venue'])

    def test_series_return_does_not_trigger_new_arrival_after_day_change_or_completion(self):
        self.s.date = self.m['date']
        _identity(self.state, self.m)
        self.m['maps'] = [dict(source='cs2')]
        self.assertTrue(attendance_for(self.state, self.e, self.m)['can_return'])
        self.s.date = '2026-06-22'
        old = attendance_for(self.state, self.e, self.m)
        self.assertFalse(old['can_return'])
        self.assertEqual('', old['return_destination'])
        self.m['played'] = True
        done = attendance_for(self.state, self.e, self.m)
        self.assertFalse(done['can_resume'])
        self.assertFalse(done['can_return'])

    def calendar(self, quick=False, birthday=''):
        self.attend()
        self.c.assist['quick_mode'] = quick
        self.c.next_calendar_day = lambda season, target: birthday if birthday and season.date < birthday <= target else None
        def next_stage(**kwargs):
            target = min(self.s._next_busy_day(), kwargs['until'])
            self.s.date = self.c.next_calendar_day(self.s, target) or target
            if self.s.date == birthday:
                self.c.story_queue.append(dict(id='birthday-choice'))
            return self.s.date
        self.s.next_stage = Mock(side_effect=next_stage)
        with patch('cs2career.league.tournament_auto.blocker',
                   side_effect=lambda c, s: '请先祝贺生日。' if c.story_queue else ''), \
             patch('cs2career.career.fast_mode.step') as fast:
            result = advance_calendar(self.state, dict(target_date=self.m['date'],
                revision=0, request_id='sleep-request-1'))
        fast.assert_not_called()
        return result

    def test_sleep_stops_on_match_morning_without_simulating_personal_game(self):
        result = self.calendar()
        self.assertEqual('2026-06-21', result['actualdate'])
        self.assertEqual('player_match', result['reason_code'])
        self.assertEqual('paused', result['status'])
        self.assertIn('LANXESS arena', result['reason'])
        self.assertFalse(self.m['played'])

    def test_quick_mode_sleep_stops_at_personally_planned_match_morning(self):
        result = self.calendar(quick=True)
        self.assertEqual('2026-06-21', result['actualdate'])
        self.assertEqual('player_match', result['reason_code'])
        self.assertFalse(self.m['played'])

    def test_sleep_stops_for_earlier_birthday_and_does_not_jump_to_target(self):
        result = self.calendar(quick=True, birthday='2026-06-20')
        self.assertEqual('2026-06-20', result['actualdate'])
        self.assertEqual('story', result['reason_code'])
        self.assertEqual('paused', result['status'])
        self.assertFalse(self.m['played'])
        self.assertEqual('2026-06-21', attendance_for(self.state, self.e, self.m)['sleep_target'])

    def test_quick_run_does_not_automatically_play_a_personally_planned_due_match(self):
        self.attend()
        self.s.date = self.m['date']
        self.c.assist['quick_mode'] = True
        with patch('cs2career.career.fast_mode.step') as fast:
            out = season_command(self.state, 'run', dict(revision=0, request_id='run-request-1'))
        fast.assert_not_called()
        self.assertEqual('paused', out['status'])
        self.assertEqual(0, out['steps'])
        self.assertIn('LANXESS arena', out['reason'])
        self.assertEqual([], out['results'])

    def test_attend_http_persists_once_and_returns_plan_without_venue_freeze(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_class())
        server.state, server.token, server.state_lock = self.state, 'match-attendance-test', threading.RLock()
        server.game_disabled, server.display_hour = True, 8
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        def post(token, revision):
            req = Request(f'http://127.0.0.1:{server.server_port}/api/3d/match/attend',
                data=json.dumps(dict(match_id=self.m['id'], revision=revision,
                                     request_id='http-attend-request')).encode(),
                headers={'Content-Type': 'application/json', 'X-Career-Token': token})
            try:
                with urlopen(req, timeout=5) as response:
                    return response.status, json.load(response)
            except HTTPError as error:
                return error.code, json.load(error)
        try:
            with patch('tools.career3d_service.read_context', return_value=dict(date=self.s.date)), \
                 patch('tools.career3d_service._pause', return_value=('', '')):
                self.assertEqual(403, post('invalid', 0)[0])
                self.state.persist.assert_not_called()
                code, out = post(server.token, 0)
                self.assertEqual(200, code)
                self.assertEqual('planned', out['status'])
                self.assertTrue(out['attendance']['planned'])
                self.assertEqual('2026-06-21', out['attendance']['sleep_target'])
                # Handler-only double: reconciliation plus the shared receipt.
                # Real disk-write coalescing is checked in test_operation_boundary.
                self.assertEqual(2, self.state.persist.call_count)
                self.assertNotIn('career3d_venue', self.m)
                self.state.persist.reset_mock()
                code, retry = post(server.token, 0)
                self.assertEqual(200, code)
                self.assertTrue(retry['replayed'])
                self.state.persist.assert_not_called()
        finally:
            server.shutdown()
            worker.join()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
