"""Isolated invitations, frozen venues/honours and completed-season feedback."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from cs2career.career import Career, player_transfers
from cs2career.league import Season, awards
from cs2career.world import build_teams
from tools.career3d_business import mail_command, mail_detail
from tools.career3d_feedback import feedback_context, acknowledge_feedback
from tools.career3d_matches import _identity, _launch, match_preflight
from tools.career3d_venues import venue_for


def team(index):
    roles = ('rifle', 'entry', 'awp', 'lurk', 'igl')
    return dict(id=f't{index}', name=f'Team{index}', region='EU', money=100000,
        command=70, mentality=70, strong_maps=[], weak_maps=[],
        players=[dict(player_id=f'p{index}_{slot}', name=f'P{index}_{slot}', role=role,
                      ability=75, stats=dict(firepower=70, entrying=70, trading=70,
                      opening=70, clutching=70, sniping=70, utility=70), form=75, age=22)
                 for slot, role in enumerate(roles)])


class Career3DExperienceTests(unittest.TestCase):
    def setUp(self):
        self.c = Career()
        self.c.exists, self.c.team_id, self.c.player_name, self.c.role = True, 't0', 'P0_0', 'rifle'
        self.c.save = Mock()
        self.s = SimpleNamespace(date='2026-06-21', year=2026, era='2026',
            teams=[team(0), team(1), team(2)], events=[], top20={}, top20_dates={},
            vrs=SimpleNamespace(table=lambda *args: [dict(id=f't{i}', rank=i+1, vrs=1000) for i in range(3)]))
        self.s.teams[0]['players'][0]['you'] = True
        self.s.your_team_name = lambda: (self.c.my_team(self.s.teams) or {}).get('name', '')
        self.s.is_yours = lambda match: self.s.your_team_name() in (match['team_a'], match['team_b'])
        self.s.yours_ready = lambda match: not match.get('played') and self.s.is_yours(match) and match['date'] <= self.s.date
        self.s.find_match = lambda ident: next(((ev, match) for ev in self.s.events for match in ev.get('matches', [])
                                               if match['id'] == ident), (None, None))
        self.s._live_series = lambda match: match.get('series')
        self.c._remember_you(self.s)
        self.state = SimpleNamespace(career=self.c, season=self.s,
            arena=SimpleNamespace(pending=False, career_player_id=lambda state: 'p0_0'), persist=Mock())
        self.state.personal_command = Mock(side_effect=lambda fn: fn(self.c, self.s))

    def contract(self, ident='contract.1', target=1):
        quote = player_transfers.quote(self.c, self.s, self.s.teams[target], 'rifle')
        row = dict(id=ident, kind='contract', status='open', date=self.s.date,
                   expires='2026-07-21', personal_transfer=True, **quote)
        self.c.inbox.append(row)
        return row

    def completed(self):
        match = dict(id='fixture-1', date=self.s.date, stage='GF', played=True, best_of=3,
            team_a='Team0', team_b='Team1', winner='Team0', series='2-0',
            maps=[dict(players={'Team0': deepcopy(self.s.teams[0]['players']),
                                'Team1': deepcopy(self.s.teams[1]['players'])})])
        award = dict(mvp=dict(player='P0_0', player_id='p0_0', team='Team0', role='rifle', rating=1.2),
                     evp=[dict(player='P1_2', player_id='p1_2', team='Team1', role='awp', rating=1.1)],
                     five=[dict(player=f'P0_{i}', player_id=f'p0_{i}', team='Team0', role=role, rating=1.1)
                           for i, role in enumerate(('rifle', 'entry', 'awp', 'lurk', 'igl'))])
        event = dict(id='event-1', name='Original LAN 2026', dates=['2026-06-19', self.s.date],
                     type='t1', status='done', champion='Team0', matches=[match], awards=award)
        self.s.events = [event]
        return event

    def honour_story(self):
        row = dict(id='awards.event-1', kind='awards', when='awards', title='Honours')
        self.c.story_queue.append(row)
        return row

    def test_reopening_same_contract_resumes_one_decision_without_transfer(self):
        row = self.contract()
        before = deepcopy(self.s.teams)
        player_transfers.open_offer(self.c, self.s, row)
        pending = deepcopy(self.c.personal_transfers['pending'])
        message = player_transfers.open_offer(self.c, self.s, row)
        self.assertIn('已打开', message)
        self.assertEqual(pending, self.c.personal_transfers['pending'])
        self.assertEqual(1, len(self.c.story_queue))
        self.assertEqual(before, self.s.teams)

    def test_different_contract_is_still_blocked(self):
        player_transfers.open_offer(self.c, self.s, self.contract())
        with self.assertRaisesRegex(ValueError, '不能同时申请多队'):
            player_transfers.open_offer(self.c, self.s, self.contract('contract.2', 2))

    def test_mail_same_contract_is_replayed_and_has_exact_story_route(self):
        self.contract()
        first = mail_command(self.state, 'accept', dict(id='contract.1', revision=0))
        self.assertTrue(first['decision_pending'])
        self.assertEqual('transfer-decision:contract.1', first['decision_id'])
        calls = self.state.personal_command.call_count
        result = mail_command(self.state, 'accept', dict(id='contract.1', revision=0))
        self.assertTrue(result['replayed'])
        self.assertEqual(calls, self.state.personal_command.call_count)
        self.assertEqual('transfer_decision', mail_detail(self.state, 'contract.1')['action_kind'])

    def test_event_invitation_routes_to_registration_even_with_pending_employer(self):
        player_transfers.open_offer(self.c, self.s, self.contract())
        ev = dict(id='event-invite', name='Invited event', status='upcoming', dates=['2026-07-01'])
        self.s.events = [ev]
        self.c.inbox.append(dict(id='invite.1', kind='invite', status='open', team_id='t0', event_id=ev['id']))
        out = mail_command(self.state, 'accept', dict(id='invite.1', revision=0))
        self.assertEqual('event_registration', out['action_kind'])
        self.assertIn(ev['id'], self.c.registered)
        self.state.personal_command.assert_not_called()
        self.assertEqual('contract.1', self.c.personal_transfers['pending']['mail_id'])
        self.assertTrue(mail_command(self.state, 'accept', dict(id='invite.1', revision=0))['replayed'])

    def test_mail_revision_and_real_roster_sessions_are_guarded(self):
        self.contract()
        with self.assertRaises(ValueError):
            mail_command(self.state, 'accept', dict(id='contract.1', revision=9))
        self.c.training_session = dict(nonce='real-training')
        with self.assertRaises(ValueError):
            mail_command(self.state, 'accept', dict(id='contract.1', revision=0))
        self.assertIsNone(self.c.personal_transfers.get('pending'))

    def test_feedback_reads_frozen_awards_without_mutation(self):
        event = self.completed()
        self.honour_story()
        before = deepcopy((event, self.c.to_json()))
        item = feedback_context(self.state)['items'][0]
        self.assertEqual('event_awards', item['kind'])
        self.assertTrue(item['is_champion'])
        self.assertEqual('Team0', item['own_team'])
        self.assertEqual(event['awards']['five'], item['five'])
        item['mvp']['player'] = 'not-real'
        self.assertEqual(before, (event, self.c.to_json()))
        self.c.save.assert_not_called()

    def test_feedback_participation_survives_transfer_and_ignores_current_club(self):
        self.completed()
        self.c.team_id = 't2'
        item = feedback_context(self.state)['items'][0]
        self.assertEqual('Team0', item['own_team'])
        self.assertTrue(item['is_champion'])
        self.s.events[0]['matches'][0]['maps'][0]['players']['Team0'][0]['player_id'] = 'other-person'
        self.assertEqual([], feedback_context(self.state)['items'])

    def test_nonparticipants_and_old_seasons_do_not_enter_presentation_feed(self):
        self.completed()
        self.state.arena.career_player_id = lambda state: 'observer-not-in-map'
        self.assertEqual([], feedback_context(self.state)['items'])
        self.state.arena.career_player_id = lambda state: 'p0_0'
        self.s.events[0]['dates'] = ['2025-06-19', '2025-06-21']
        self.assertEqual([], feedback_context(self.state)['items'])
        self.s.top20 = {'2024': [dict(rank=1, player='P0_0', player_id='p0_0', team='Team0')]}
        self.assertEqual([], feedback_context(self.state)['items'])

    def test_normal_and_quick_feedback_use_same_frozen_honours(self):
        self.completed()
        normal = feedback_context(self.state)['items'][0]
        self.c.assist['quick_mode'] = True
        quick = feedback_context(self.state)['items'][0]
        self.assertFalse(normal.pop('quick'))
        self.assertTrue(quick.pop('quick'))
        self.assertEqual(normal, quick)

    def test_ack_dismisses_only_matching_no_choice_honour_story(self):
        self.completed()
        self.honour_story()
        choice = dict(id='important', kind='incident', choices=[dict(id='choose')])
        self.c.story_queue.append(choice)
        key = feedback_context(self.state)['items'][0]['id']
        before = (self.c.money, self.c.attr_points)
        acknowledge_feedback(self.state, dict(id=key, revision=0))
        self.assertNotIn('awards.event-1', [row['id'] for row in self.c.story_queue])
        self.assertIn(choice, self.c.story_queue)
        self.assertEqual(before, (self.c.money, self.c.attr_points))
        self.assertEqual([], feedback_context(self.state)['items'])
        self.c.save.reset_mock()
        self.assertTrue(acknowledge_feedback(self.state, dict(ids=[key], revision=-1))['replayed'])
        self.c.save.assert_not_called()

    def test_ack_never_answers_choice_awards_or_unknown_ids(self):
        self.completed()
        row = self.honour_story()
        row['choices'] = [dict(id='protected')]
        key = feedback_context(self.state)['items'][0]['id']
        with self.assertRaises(ValueError):
            acknowledge_feedback(self.state, dict(ids=[key, 'foreign-id'], revision=0))
        self.assertIn(row, self.c.story_queue)
        acknowledge_feedback(self.state, dict(id=key, revision=0))
        self.assertIn(row, self.c.story_queue)

    def test_final_top20_uses_formal_saved_rows_not_live_ranking(self):
        self.completed()
        rows = [dict(rank=1, player='P0_0', player_id='p0_0', team='OriginalTeam', score=5.4)]
        self.s.top20 = {'2026': deepcopy(rows)}
        self.s.top20_dates = {'2026': self.s.date}
        item = next(row for row in feedback_context(self.state)['items'] if row['kind'] == 'top20')
        self.assertEqual(rows, item['rows'])
        self.assertEqual(1, item['ceremony']['player_rank'])
        self.assertEqual('OriginalTeam', item['ceremony']['top20'][0]['team'])
        self.s.events[0]['status'] = 'live'
        self.assertFalse(any(row['kind'] == 'top20' for row in feedback_context(self.state)['items']))

    def test_just_rolled_top20_requires_unread_notice_and_only_one_year(self):
        self.s.top20 = {'2025': [dict(rank=1, player='P0_0', player_id='p0_0', team='Team0')], '2024': []}
        self.assertEqual([], feedback_context(self.state)['items'])
        self.c.inbox.append(dict(id='notice:top20.2025', kind='notification', read=False,
            notification_id='top20.2025', notification=dict(kind='top20', year=2025)))
        feed = feedback_context(self.state)
        self.assertEqual(1, feed['total'])
        self.assertEqual(2025, feed['items'][0]['year'])

    def test_venue_phase_and_edition_are_never_faked(self):
        event = self.completed()
        event.update(id='major-1', name='IEM Cologne Major 2026', type='major')
        match = event['matches'][0]
        match['played'] = False
        self.assertEqual(('major', 'LANXESS arena'),
                         tuple(venue_for(self.state, event, match)[key] for key in ('destination', 'name')))
        match['stage'] = 'M1-SW1'
        early = venue_for(self.state, event, match)
        self.assertEqual('lan', early['destination'])
        self.assertEqual('studio', early['scale'])
        self.assertNotEqual('LANXESS arena', early['name'])
        event['name'] = 'Future Major 2026 (fictional)'
        unknown = venue_for(self.state, event, match)
        self.assertFalse(unknown['verified'])
        self.assertFalse(unknown['travel_allowed'])
        self.assertEqual('', unknown['name'])

    def test_online_bounty_groups_do_not_travel_to_a_large_arena(self):
        event = self.completed()
        event.update(id='blast-bounty', name='BLAST Premier Bounty Season 1 2026')
        match = event['matches'][0]
        match.update(stage='R16', played=False)
        self.assertEqual('online', venue_for(self.state, event, match)['scale'])
        self.assertFalse(venue_for(self.state, event, match)['travel_allowed'])
        match['stage'] = 'GF'
        final = venue_for(self.state, event, match)
        self.assertEqual('studio', final['scale'])
        self.assertEqual('lan', final['destination'])
        self.assertEqual('BLAST Studio, Malta', final['name'])

    def test_preflight_get_is_read_only_and_business_freezes_exact_ten_ids(self):
        event = self.completed()
        event.update(id='major-1', name='IEM Cologne Major 2026', type='major')
        match = event['matches'][0]
        match['played'] = False
        match.pop('maps')
        before = deepcopy(event)
        config = dict(ready=False, reason='No game in tests')
        with patch('tools.career3d_activities.config_status', return_value=config):
            view = match_preflight(self.state, match['id'])
        self.assertEqual(before, event)
        self.assertEqual(5, len(view['venue']['players_a']))
        self.assertEqual(10, len({row['id'] for row in view['venue']['players_a'] + view['venue']['players_b']}))
        _identity(self.state, match)
        frozen = deepcopy(match['career3d_venue'])
        self.s.teams[0]['players'][1]['name'] = 'RenamedLater'
        self.assertEqual(frozen['players_a'], venue_for(self.state, event, match)['players_a'])
        match['played'] = True
        self.assertFalse(venue_for(self.state, event, match)['travel_allowed'])

    def test_venue_rejects_missing_or_duplicate_player_identity(self):
        event = self.completed()
        event.update(id='major-1', name='IEM Cologne Major 2026', type='major')
        match = event['matches'][0]
        match['played'] = False
        self.s.teams[1]['players'][0]['player_id'] = 'p0_0'
        venue = venue_for(self.state, event, match)
        self.assertFalse(venue['roster_complete'])
        self.assertFalse(venue['travel_allowed'])

    def test_cs2_launch_request_and_session_keep_fixture_identity_without_game(self):
        from cs2career.league import season as season_module
        event = self.completed()
        event.update(id='major-1', name='IEM Cologne Major 2026', type='major')
        match = event['matches'][0]
        match.update(played=False, pending_map='Dust2', maps=[])
        _identity(self.state, match)
        captured = []
        def start(*args, **kwargs):
            captured.append(deepcopy(kwargs['request_override']))
            return dict(match=kwargs['request_override'], msg='Mock game not started')
        def launch_map(ident, side):
            value = season_module.start_match(self.s.teams[0], self.s.teams[1], self.c.player_name,
                'de_dust2', side, self.s.teams, self.c)
            match['cs2_session'] = dict(nonce=value['match']['nonce'], cs2_map='de_dust2')
            return value['msg']
        self.s.launch_your_map = launch_map
        request = dict(nonce='mock-request-nonce', human_player_id='p0_0', bots=[])
        with patch('tools.career3d_activities._running_cs2', return_value=False), \
             patch('tools.career3d_activities.config_status', return_value=dict(ready=True)), \
             patch('tools.career3d_activities.read_cs2_config', return_value=dict(difficulty='Medium')), \
             patch('cs2career.cs2.launch.require_cs2_closed'), \
             patch('cs2career.cs2.launch.build_request', return_value=request), \
             patch('cs2career.cs2.launch.start_match', side_effect=start), \
             patch('tools.career3d_matches.match_status', return_value={}):
            result = _launch(self.state, match, dict(side='ct'))
        self.assertEqual('waiting', result['status'])
        self.assertEqual(1, len(captured))
        self.assertEqual(match['id'], captured[0]['career_identity']['match_id'])
        self.assertEqual('2026:major-1:' + match['id'], captured[0]['career_identity']['key'])
        self.assertEqual('p0_0', captured[0]['career_identity']['human_id'])
        self.assertEqual('LANXESS arena', captured[0]['career_venue']['name'])
        self.assertEqual(captured[0]['career_identity'], match['cs2_session']['career_identity'])

    def test_http_feedback_ack_is_authenticated_persisted_and_replay_safe(self):
        from tools import career3d_service
        self.completed()
        self.honour_story()
        key = feedback_context(self.state)['items'][0]['id']
        server = ThreadingHTTPServer(('127.0.0.1', 0), career3d_service.handler_class())
        server.state, server.token, server.state_lock = self.state, 'experience-test-token', threading.RLock()
        server.game_disabled, server.display_hour = True, 8
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(token, revision):
            req = Request(f'http://127.0.0.1:{server.server_port}/api/3d/feedback/ack',
                data=json.dumps(dict(ids=[key], revision=revision)).encode(),
                headers={'Content-Type': 'application/json', 'X-Career-Token': token})
            try:
                with urlopen(req, timeout=5) as response:
                    return response.status, json.load(response)
            except HTTPError as error:
                return error.code, json.load(error)
        try:
            with patch.object(career3d_service, 'read_context', side_effect=lambda state, hour: dict(feedback=feedback_context(state))), \
                 patch.object(career3d_service, '_pause', return_value=('', '')):
                self.assertEqual(403, request('invalid-token', 0)[0])
                self.state.persist.assert_not_called()
                code, out = request(server.token, 0)
                self.assertEqual(200, code)
                self.assertEqual([key], out['acknowledged'])
                self.state.persist.assert_called_once()
                self.assertEqual(1, self.c.incident_state['career3d_service']['revision'])
                persisted = json.loads(json.dumps(self.c.to_json()))
                self.c.incident_state = persisted['incident_state']
                self.state.persist.reset_mock()
                code, out = request(server.token, 0)
                self.assertEqual(200, code)
                self.assertTrue(out['replayed'])
                self.state.persist.assert_not_called()
                self.assertEqual([], out['context']['feedback']['items'])
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def test_end_of_season_finalization_is_once_and_preserves_final_formula(self):
        season = Season.__new__(Season)
        season.year, season.date = 2026, '2026-12-18'
        season.top20, season.top20_dates = {}, {}
        season.events = [dict(id='e', name='Ended', dates=['2026-12-18'], status='done', matches=[], type='t1')]
        season.career = SimpleNamespace(on_year_end=Mock())
        season.ratings_vs_field = Mock(return_value=[])
        with patch('cs2career.league.awards.top20', return_value=[dict(player='ActualWinner', player_id='actual-id', rank=1)]) as ranker, \
             patch('cs2career.career.verse.feature_report', return_value='Frozen report'):
            first = season.finalize_top20()
            second = season.finalize_top20()
        self.assertIs(first, second)
        ranker.assert_called_once()
        season.career.on_year_end.assert_called_once()
        self.assertEqual('Frozen report', first[0]['feature'])
        self.assertEqual('2026-12-18', season.top20_dates['2026'])
        season.top20 = {}
        season.events[0]['status'] = 'upcoming'
        with self.assertRaises(ValueError):
            season.finalize_top20()

    def test_2024_2025_rosters_have_calibrated_candidates_not_2026_aliases(self):
        for era, expected in (('2024', 270), ('2025', 295)):
            teams = build_teams(era, int(era))
            players = [player for row in teams for player in row['players']]
            self.assertEqual(expected, len(players))
            calibrated = [player for player in players if player.get('stats', {}).get('position_model')]
            self.assertEqual(expected, len(calibrated))
            self.assertEqual({era}, {player['stats']['calibration_provenance']['era'] for player in calibrated})
            self.assertTrue(all(player['stats']['position_model']['seed_id'].startswith(era + ':') for player in calibrated))


if __name__ == '__main__':
    unittest.main()
