"""Unified career boundaries; real saves and fake game I/O, no live CS2."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import test_match_simulation_boundary as fixture
from cs2career.application import ApplicationState
from cs2career.engine.match import RNG
from cs2career.services import career_pace, match_simulation, matches, season_run, match_launch
from cs2career.cs2 import launch
from tools.career3d_rts import rts_command
from test_career3d_rts_arena import completed_report


class UnifiedPaceTests(unittest.TestCase):
    setUp = fixture.MapSimulationBoundaryTests.setUp
    career_fixture = fixture.MapSimulationBoundaryTests.career_fixture
    quiet = fixture.MapSimulationBoundaryTests.quiet
    ready = fixture.MapSimulationBoundaryTests.ready
    body = fixture.MapSimulationBoundaryTests.body
    serving = fixture.MapSimulationBoundaryTests.serving
    request = fixture.MapSimulationBoundaryTests.request

    def current(self, token):
        return dict(self.body(token), scope='current_map',
                    map_key=matches.match_preflight(self.state, self.match_id)['map_key'])

    def test_single_map_stops_without_consuming_next_map_and_replays_after_restart(self):
        match = self.ready()
        body = self.current('unified-first-map')
        from cs2career.league.season import play_map
        with patch('cs2career.league.season.play_map', wraps=play_map) as simulate:
            out = match_simulation.command(self.state, body)
        self.assertEqual(1, simulate.call_count)
        self.assertEqual(1, len(match['maps']))
        self.assertEqual(1, len(out['reveal']['maps']))
        rng = RNG.getstate()
        before = deepcopy(self.state.season.teams)
        loaded = ApplicationState()
        self.assertTrue(match_simulation.command(loaded, body)['replayed'])
        self.assertEqual(before, loaded.season.teams)
        self.assertEqual(rng, RNG.getstate())
        with self.assertRaisesRegex(ValueError, '地图进度'):
            match_simulation.command(loaded, dict(body, request_id='late-deadline-click', revision=matches._revision(loaded)))

    def test_preparation_boundary_does_not_pick_maps_or_simulate_player(self):
        match = self.ready()
        for key in ('veto', 'career3d_veto', 'pending_map'): match.pop(key, None)
        career_pace.enable(self.state)
        with patch('cs2career.league.season.play_map', side_effect=AssertionError('no speculative map')):
            out = season_run.command(self.state, dict(request_id='unified-calendar', revision=0, stop_at='match_preparation'))
        self.assertEqual('ready', out['status'])
        self.assertEqual(self.match_id, out['next_match']['match_id'])
        self.assertFalse(match['maps'])
        self.assertNotIn('veto', match)

    def test_policy_preserves_points_preferences_and_does_not_save_running_state(self):
        self.ready()
        c = self.state.career
        c.attr_points = 37
        c.assist.update(invites={'major':'accept', 'cct':'decline'}, points='off')
        original = deepcopy(self.state.season.events)
        with self.state.operation():
            matches.season_command(self.state, 'unify', dict(revision=0))
            self.state.persist()
        loaded = ApplicationState()
        self.assertEqual(37, loaded.career.attr_points)
        self.assertEqual({'major':'accept', 'cct':'decline'}, loaded.career.assist['invites'])
        self.assertTrue(loaded.career.assist['unified_pace'])
        self.assertEqual(original, self.state.season.events)
        self.assertEqual(original[0]['matches'], loaded.season.find_match(self.match_id)[0]['matches'])
        self.assertNotIn('running', loaded.career.assist)

    def test_seat_is_series_scoped_and_survives_restart(self):
        match = self.ready()
        with self.state.operation():
            out = matches.match_command(self.state, 'seated', dict(self.body('seated-series')))
            self.state.persist()
        self.assertTrue(out['preflight']['venue']['entry_completed'])
        loaded = ApplicationState()
        self.assertTrue(matches.match_preflight(loaded, self.match_id)['venue']['entry_completed'])
        match['career3d_attendance']['match_identity'] = 'other-series'
        self.assertFalse(matches.match_preflight(self.state, self.match_id)['venue']['entry_completed'])

    def test_sim_cs2_rts_maps_keep_bp_and_settle_each_map_once(self):
        match = self.ready()
        self.stack.enter_context(patch.object(self.state.season, '_phase_gate', return_value=False))
        self.stack.enter_context(patch('tools.career3d_activities.config_status', return_value=dict(ready=True, reason='')))
        self.stack.enter_context(patch('tools.career3d_activities.read_cs2_config', return_value=dict(launch.DEFAULTS, csgo_path='')))
        self.stack.enter_context(patch.object(launch, 'require_cs2_closed'))
        self.stack.enter_context(patch.object(matches, '_peek', return_value={'status':'none'}))
        career_pace.enable(self.state)
        match_simulation.command(self.state, self.current('mixed-sim-first'))
        first = deepcopy(match['maps'][0])
        order = list(match['veto']['order'])
        sent = {}
        def dispatch(cfg, args, kwargs):
            sent.update(kwargs['request_override'])
            return dict(match=sent, msg='fixture only')
        with patch.object(matches, '_dispatch_launch', side_effect=dispatch):
            match_launch.command(self.state, self.current('mixed-cs2-second'))
        session = deepcopy(match['cs2_session'])
        players = [dict(player_id=sent['human_player_id'], name=sent['player'], team=sent['human_team'])]
        players += [dict(player_id=p['player_id'], name=p['display_name'], team=side)
                    for side in ('ct','t') for p in sent[side]['players']]
        # Opposite winner to map one guarantees a real third-map transition.
        ct_team = session['my_team'] if session['side'] == 'ct' else session['opp']
        ct_win = ct_team != first['winner']
        raw = dict(schema_version=2, status='finished', complete=True, map=session['cs2_map'],
                   request_nonce=session['nonce'], ended_at='2099-10-06T12:00:00Z',
                   ct_score=13 if ct_win else 8, t_score=8 if ct_win else 13, players=players)
        with patch.object(matches, '_peek', return_value=raw):
            match_simulation.command(self.state, self.current('mixed-collect-second'))
        self.assertEqual(2, len(match['maps']))
        self.assertFalse(match['played'])
        with self.state.operation():
            out = rts_command(self.state, 'start', dict(self.current('mixed-start-third'), side='ct'))
            self.state.persist()
        rts = out['rts_session']
        report = completed_report(rts)
        body = dict(self.current('mixed-submit-third'), nonce=rts['nonce'], report=report)
        with self.state.operation():
            out = rts_command(self.state, 'submit', body)
            self.state.persist()
        self.assertTrue(match['played'])
        self.assertEqual(order, match['veto']['order'])
        self.assertEqual(first, match['maps'][0])
        self.assertEqual(['sim', 'cs2', 'rts'], [m.get('source', 'sim') for m in match['maps']])
        self.assertTrue(all(len(m['map_form_changes']) == 2 for m in match['maps']))
        before = deepcopy(self.state.season.teams)
        self.assertTrue(rts_command(self.state, 'submit', body)['replayed'])
        self.assertEqual(before, self.state.season.teams)
        with self.assertRaises(ValueError):
            self.state.season.commit_cs2_map(self.match_id, raw, result_reader=lambda **kwargs:raw)
        self.assertEqual(3, len(ApplicationState().season.find_match(self.match_id)[1]['maps']))

    def test_old_bot_identity_preference_is_always_normalized_to_player(self):
        for old in ('bot', 'player', None):
            cfg = launch._clean(dict(launch.DEFAULTS, bot_identity=old))
            self.assertEqual('player', cfg['bot_identity'])

    def test_repeated_exit_collection_then_simulation_can_continue_next_map(self):
        match = self.ready()
        self.stack.enter_context(patch.object(self.state.season, '_phase_gate', return_value=False))
        self.stack.enter_context(patch('tools.career3d_activities.config_status', return_value=dict(ready=True, reason='')))
        self.stack.enter_context(patch('tools.career3d_activities.read_cs2_config', return_value=dict(launch.DEFAULTS, csgo_path='')))
        self.stack.enter_context(patch.object(launch, 'require_cs2_closed'))
        self.stack.enter_context(patch.object(matches, '_peek', return_value={'status':'none'}))
        career_pace.enable(self.state)
        def dispatch(cfg, args, kwargs):
            return dict(match=kwargs['request_override'], msg='fixture only')
        with patch.object(matches, '_dispatch_launch', side_effect=dispatch):
            match_launch.command(self.state, self.current('recovery-launch-first'))
            for cycle in range(2):
                # The process has been seen and then exited; each relaunch has
                # a distinct nonce, but the same uncompleted map identity.
                self.state._3d_cs2_seen_nonce = match['cs2_session']['nonce']
                before, rng = deepcopy(match), RNG.getstate()
                for index in range(3):
                    out = matches.match_command(self.state, 'collect', self.current(f'recovery-read-{cycle}-{index}'))
                    self.assertEqual('waiting', out['status'])
                    self.assertTrue(out['connection']['can_resume'])
                    self.assertEqual(before, match)
                    self.assertEqual(rng, RNG.getstate())
                match_launch.command(self.state, self.current(f'recovery-relaunch-{cycle}'))
        self.state._3d_cs2_seen_nonce = match['cs2_session']['nonce']
        nonce = match['cs2_session']['nonce']
        body = self.current('recovery-simulate-first')
        first = match_simulation.command(self.state, body)
        self.assertEqual(1, len(match['maps']))
        self.assertFalse(match['played'])
        self.assertNotIn('cs2_session', match)
        self.assertFalse(first['preflight']['session_pending'])
        self.assertEqual(nonce, match['career3d_retired_sessions'][-1]['session']['nonce'])
        saved, teams, rng = deepcopy(match['maps']), deepcopy(self.state.season.teams), RNG.getstate()
        self.assertTrue(match_simulation.command(self.state, body)['replayed'])
        for _ in range(3):
            view = matches.match_status(self.state, self.match_id)
            self.assertEqual('ready', view['status'])
            self.assertFalse(view['can_collect'])
        self.assertEqual(saved, match['maps'])
        self.assertEqual(teams, self.state.season.teams)
        self.assertEqual(rng, RNG.getstate())
        second = match_simulation.command(self.state, self.current('recovery-simulate-second'))
        self.assertEqual(2, len(match['maps']))
        self.assertEqual(saved[0], match['maps'][0])
        self.assertEqual(1, second['reveal']['maps'][0]['index'])
        self.assertEqual(2, len(ApplicationState().season.find_match(self.match_id)[1]['maps']))

    def test_two_zero_stops_without_third_map_or_rng_consumption(self):
        match = self.ready()
        from cs2career.league.season import play_map
        def home_win(a, b, name, *args, **kwargs):
            box = play_map(a, b, name, *args, **kwargs)
            box.update(winner=a['name'], score='13-6')
            return box
        with patch('cs2career.league.season.play_map', side_effect=home_win) as simulate:
            match_simulation.command(self.state, self.current('two-zero-first'))
            match_simulation.command(self.state, self.current('two-zero-second'))
            before = RNG.getstate()
            match_simulation.command(self.state, self.current('two-zero-late'))
        self.assertEqual(2, simulate.call_count)
        self.assertEqual(2, len(match['maps']))
        self.assertTrue(match['played'])
        self.assertEqual(before, RNG.getstate())

    def test_active_rts_stops_calendar_and_does_not_cancel_session(self):
        match = self.ready()
        career_pace.enable(self.state)
        match['career3d_rts'] = {'nonce':'active-test', 'map_index':0}
        out = season_run.command(self.state, dict(request_id='rts-calendar-hold', revision=0, stop_at='match_preparation'))
        self.assertEqual('paused', out['status'])
        self.assertEqual('active-test', match['career3d_rts']['nonce'])
        self.assertFalse(match['maps'])

    def test_break_points_optional_required_story_blocks_ack_and_reads_are_pure(self):
        self.ready()
        c, s = self.state.career, self.state.season
        career_pace.enable(self.state)
        c.attr_points = 37
        c.incident_state['story_timing'] = {'deferred':[], 'windows':[{'key':'test-major', 'start':s.date, 'until':s.date}]}
        c.story_queue = [{'id':'decision', 'text':'choose', 'choices':[{'id':'stay'}]}]
        before = deepcopy(c.to_json())
        view = matches.quick_context(self.state)
        self.assertEqual('test-major', view['break_key'])
        self.assertFalse(view['break_ack'])
        self.assertTrue(view['block_reason'])
        self.assertEqual(before, c.to_json())
        with self.assertRaises(ValueError), self.state.operation():
            matches.season_command(self.state, 'resume', dict(revision=matches._revision(self.state), break_key='test-major'))
        c = self.state.career
        self.assertNotEqual('test-major', c.assist.get('quick_break_ack'))
        c.story_queue = []
        with self.state.operation():
            matches.season_command(self.state, 'resume', dict(revision=matches._revision(self.state), break_key='test-major'))
            self.state.persist()
        loaded = ApplicationState()
        self.assertEqual(37, loaded.career.attr_points)
        self.assertEqual('test-major', loaded.career.assist['quick_break_ack'])
