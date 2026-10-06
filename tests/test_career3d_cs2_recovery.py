"""Interrupted matches recover under the server lock, never using live saves."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from tests import test_career3d_session_return as session_fixtures
from tests import test_arena as arena_fixtures
from tests.test_career3d_rts_arena import completed_report
from tools.career3d_activities import custom_command, ladder_command, _arena_status, recover_arena_cs2
from tools.career3d_cs2_lifecycle import recovery_state, utc_stamp
from tools.career3d_matches import _launch, match_command, match_status, recover_cs2_map
from tools.career3d_rts import rts_command


class RecoveryProjectionTests(unittest.TestCase):
    def test_dispatch_grace_unknown_live_closed_and_result_priorities(self):
        now = datetime(2026, 10, 4, tzinfo=timezone.utc)
        session = dict(launch_requested_at=now.isoformat(), started_at='2020-01-01T00:00:00Z')
        self.assertEqual('starting', recovery_state(session, False, now=now)['status'])
        self.assertFalse(recovery_state(session, False, now=now)['can_switch'])
        self.assertEqual('interrupted', recovery_state(session, False,
            now=now + timedelta(seconds=46))['status'])
        self.assertEqual('process_unknown', recovery_state(session, None, now=now)['status'])
        self.assertFalse(recovery_state(session, None, now=now)['can_resume'])
        self.assertEqual('waiting', recovery_state(session, True, now=now)['status'])
        self.assertEqual('result_ready', recovery_state(session, False, True, now=now)['status'])
        self.assertFalse(recovery_state(session, False, True, now=now)['can_switch'])
        self.assertEqual('interrupted', recovery_state(session, False, now=now, seen_running=True)['status'])

    def test_legacy_dispatch_and_bad_timestamp_do_not_strand_a_closed_game(self):
        for stamp in ('2020-01-01T00:00:00Z', '2020-01-01T00:00:00', 'unavailable', None):
            with self.subTest(stamp=stamp):
                self.assertTrue(recovery_state(dict(started_at=stamp), False)['can_resume'])


class CareerRecoveryTests(unittest.TestCase):
    def setUp(self):
        fixture = session_fixtures.CareerSessionReturnTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.state, self.m, self.e, self.s, self.c = fixture.state, fixture.m, fixture.e, fixture.s, fixture.c
        self.s._require_yours.return_value = (self.e, self.m)
        self.s._phase_gate = Mock(return_value=False)
        self.s.open_your_series = Mock()
        self.s._series_over = Mock(return_value=False)
        self.live = patch('tools.career3d_activities._running_cs2', return_value=False)
        self.live.start()
        self.addCleanup(self.live.stop)
        self.peek = patch('tools.career3d_matches._peek', return_value=dict(status='none'))
        self.peek_mock = self.peek.start()
        self.addCleanup(self.peek.stop)
        self.config = patch('tools.career3d_activities.read_cs2_config', return_value={})
        self.config.start()
        self.addCleanup(self.config.stop)

    def body(self, **options):
        return dict(match_id=self.m['id'], revision=0, request_id='recovery-request-1', **options)

    def keep_map(self):
        kept = dict(map='mirage', winner='Team0', source='cs2', request_nonce='earlier-map')
        self.m.update(best_of=3, maps=[kept])
        self.m['veto']['order'] = ['mirage', 'dust2', 'nuke']
        self.m['cs2_session']['map_index'] = 1
        self.m['career3d_launch']['map_index'] = 1
        return deepcopy(kept)

    def test_closed_projection_is_recoverable_and_read_only(self):
        before = deepcopy(self.m)
        view = match_status(self.state, self.m['id'])
        self.assertEqual('interrupted', view['status'])
        self.assertEqual('launched', view['phase'])
        for key in ('can_resume', 'can_simulate', 'can_rts'):
            self.assertTrue(view[key])
            self.assertTrue(view['preflight'][key])
        self.assertEqual(before, self.m)
        self.state.persist.assert_not_called()

    def test_quick_normal_exit_is_not_mistaken_for_startup_after_game_was_seen(self):
        self.m['cs2_session']['launch_requested_at'] = utc_stamp()
        with patch('tools.career3d_activities._running_cs2', return_value=True):
            self.assertEqual('waiting', match_status(self.state, self.m['id'])['status'])
        self.assertEqual('interrupted', match_status(self.state, self.m['id'])['status'])
        self.assertTrue(match_status(self.state, self.m['id'])['can_simulate'])

    def test_partial_same_nonce_dump_proves_game_started_after_service_restart(self):
        self.m['cs2_session']['launch_requested_at'] = utc_stamp()
        self.peek_mock.return_value = dict(status='in_progress', request_nonce=self.m['cs2_session']['nonce'])
        self.assertTrue(match_status(self.state, self.m['id'])['can_resume'])
        self.assertEqual('interrupted', match_status(self.state, self.m['id'])['status'])

    def test_live_unknown_and_startup_do_not_retire_original_session(self):
        original = deepcopy(self.m)
        with patch('tools.career3d_activities._running_cs2', return_value=True):
            with self.assertRaisesRegex(ValueError, 'CS2 正在运行'):
                recover_cs2_map(self.state, self.e, self.m, 'simulate')
        with patch('tools.career3d_activities._running_cs2', side_effect=RuntimeError('process probe failed')):
            with self.assertRaisesRegex(RuntimeError, 'probe failed'):
                recover_cs2_map(self.state, self.e, self.m, 'rts')
        self.m['cs2_session']['launch_requested_at'] = utc_stamp()
        with self.assertRaisesRegex(ValueError, '正在启动'):
            recover_cs2_map(self.state, self.e, self.m, 'cs2')
        self.m['cs2_session'].pop('launch_requested_at')
        self.assertEqual(original, self.m)

    def test_game_request_handoff_failure_keeps_career_session_and_saved_maps(self):
        self.keep_map()
        before = deepcopy(self.m)
        with patch('tools.career3d_activities.read_cs2_config', return_value=dict(csgo_path='X:/offline-fixture')), \
             patch('cs2career.cs2.launch.deactivate_match_request', side_effect=PermissionError('retirement denied')) as retire:
            with self.assertRaisesRegex(PermissionError, 'retirement denied'):
                recover_cs2_map(self.state, self.e, self.m, 'simulate')
        retire.assert_called_once_with(Path('X:/offline-fixture'), 'return-original-nonce')
        self.assertEqual(before, self.m)

    def test_restart_keeps_bp_side_and_prior_maps_and_never_reuses_nonce(self):
        kept = self.keep_map()
        old_nonce = self.m['cs2_session']['nonce']
        self.m['cs2_session']['side'] = 't'
        veto = deepcopy(self.m['veto'])
        def start(state, match, body):
            self.assertNotIn('cs2_session', match)
            self.assertEqual('t', body['side'])
            match['cs2_session'] = dict(nonce='new-request-nonce')
            return dict(status='waiting', reason='launched')
        with patch('tools.career3d_matches._launch', side_effect=start) as launch:
            first = match_command(self.state, 'launch', self.body())
            second = match_command(self.state, 'launch', self.body())
        self.assertTrue(first['restarted_map'])
        self.assertTrue(second['replayed'])
        launch.assert_called_once()
        self.assertEqual([kept], self.m['maps'])
        self.assertEqual(veto, self.m['veto'])
        self.assertEqual(old_nonce, self.m['career3d_retired_sessions'][0]['session']['nonce'])
        self.assertNotEqual(old_nonce, self.m['cs2_session']['nonce'])

    def test_simulate_after_exit_preserves_completed_maps_and_is_idempotent(self):
        kept = self.keep_map()
        def simulate(ident):
            self.assertNotIn('cs2_session', self.m)
            self.m['maps'].append(dict(source='sim', map='dust2', winner='Team0'))
            self.m['played'] = True
            return 'simulated remaining map'
        self.s.skip_your_series = Mock(side_effect=simulate)
        with patch('tools.career3d_matches._result_response', return_value=dict(status='finished', result={})), \
             patch('tools.career3d_matches._report', return_value=dict(maps=[])):
            first = match_command(self.state, 'simulate', self.body())
            again = match_command(self.state, 'simulate', self.body())
        self.assertEqual('finished', first['status'])
        self.assertTrue(again['replayed'])
        self.s.skip_your_series.assert_called_once_with(self.m['id'])
        self.assertEqual(kept, self.m['maps'][0])
        self.assertEqual('simulate', self.m['career3d_retired_sessions'][0]['mode'])

    def test_rts_switch_retires_cs2_nonce_and_keeps_series_results(self):
        kept = self.keep_map()
        out = rts_command(self.state, 'start', self.body(side='t'))
        self.assertEqual('rts_pending', out['status'])
        self.assertNotIn('cs2_session', self.m)
        self.assertEqual(1, out['rts_session']['map_index'])
        self.assertEqual('de_dust2', out['rts_session']['map'])
        self.assertEqual([kept], self.m['maps'])
        self.assertEqual('rts', self.m['career3d_retired_sessions'][0]['mode'])
        self.assertNotEqual('return-original-nonce', out['rts_session']['nonce'])

    def test_finished_dump_wins_mode_change_and_retry_does_not_start_next_map(self):
        kept = self.keep_map()
        session = self.m['cs2_session']
        raw = dict(schema_version=2, status='finished', complete=True, map='de_dust2',
            request_nonce=session['nonce'], ended_at='2099-10-04T10:00:00Z', ct_score=13, t_score=6,
            players=[dict(player_id=pid, name=pid, team='ct' if i < 5 else 't',
                kills=10, deaths=10, assists=3, damage=1000, kast=.7, survived_rounds=9)
                for i, pid in enumerate(session['expected_player_ids'])])
        self.peek_mock.return_value = raw
        def commit(ident, result, *, result_reader):
            self.assertEqual(result, result_reader(request_nonce=result['request_nonce']))
            self.m['maps'].append(dict(source='cs2', request_nonce=result['request_nonce']))
            self.m.pop('cs2_session')
            return 'collected old map'
        self.s.commit_cs2_map = Mock(side_effect=commit)
        with patch('tools.career3d_matches._result_response', return_value=dict(result={}, preflight={})), \
             patch('tools.career3d_matches._launch') as launch:
            first = match_command(self.state, 'launch', self.body())
            again = match_command(self.state, 'launch', self.body())
        self.assertEqual('map_collected', first['status'])
        self.assertTrue(again['replayed'])
        self.s.commit_cs2_map.assert_called_once()
        launch.assert_not_called()
        self.assertNotIn('career3d_retired_sessions', self.m)
        self.assertEqual(kept, self.m['maps'][0])

    def test_career_external_inventory_uses_ownership_handoff_not_our_dll_gate(self):
        from cs2career.cs2 import launch
        self.m.pop('cs2_session')
        self.m.pop('career3d_launch')
        self.c.real_skins = True
        def start(ident, side, *, launcher, result_reader):
            result = launcher(self.s.teams[0], self.s.teams[1], self.c.player_name,
                              'de_dust2', side, self.s.teams, self.c)
            return result['msg']
        def dispatch(*args, **kwargs):
            self.assertTrue(kwargs['existing_plugins'])
            launch.prepare_existing_skins(Path('X:/offline-fixture'), args[6], kwargs['config'])
            return dict(match=kwargs['request_override'], msg='fixture started')
        self.s.launch_your_map = Mock(side_effect=start)
        cfg = dict(launch.DEFAULTS, skins_inventory_mode='external', csgo_path='X:/offline-fixture')
        for error in (None, PermissionError('handoff denied')):
            self.m.pop('career3d_launch', None)
            with self.subTest(error=error), \
                 patch('tools.career3d_activities.read_cs2_config', return_value=cfg), \
                 patch('tools.career3d_matches.match_status', return_value={}), \
                 patch('cs2career.cs2.launch.require_cs2_closed'), \
                 patch('cs2career.cs2.launch.start_match', side_effect=dispatch), \
                 patch('cs2career.cs2.launch._prepare_external_skins', return_value=0, side_effect=error) as handoff, \
                 patch('cs2career.career.skins.plugin_installed', return_value=False) as plugin:
                result = _launch(self.state, self.m, dict(side='ct'))
            handoff.assert_called_once_with(Path('X:/offline-fixture'))
            plugin.assert_not_called()
            self.assertEqual('failed' if error else 'waiting', result['status'])
            if error:
                self.assertIn('handoff denied', result['reason'])


class ArenaRecoveryTests(unittest.TestCase):
    def setUp(self):
        fixture = arena_fixtures.ArenaTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture, self.state, self.arena = fixture, fixture.state, fixture.arena
        self.state.arena = self.arena
        self.state.career.incident_state = {'career3d_service': {'revision': 7}}
        self.state.persist = Mock()
        self.state.career.inventory = []
        self.state.career.equipped_ct, self.state.career.equipped_t = {}, {}
        self.state.career.steam_id, self.state.career.real_skins = '', False
        self.state.season.date = '2026-01-01'
        self.cfg = patch('tools.career3d_activities.read_cs2_config', return_value={})
        self.cfg.start()
        self.addCleanup(self.cfg.stop)
        self.config = patch('tools.career3d_activities.config_status', return_value=dict(ready=True, reason=''))
        self.config.start()
        self.addCleanup(self.config.stop)
        self.live = patch('tools.career3d_activities._running_cs2', return_value=False)
        self.live.start()
        self.addCleanup(self.live.stop)
        self.peek = patch('tools.career3d_activities._peek_ladder_result', return_value=dict(status='none'))
        self.peek_mock = self.peek.start()
        self.addCleanup(self.peek.stop)

    def room(self, mode='rank'):
        lobby = self.fixture.ready(mode)
        lobby.update(phase='launched', nonce='retired-game-nonce', started_at='2020-01-01T00:00:00Z')
        return lobby

    def body(self):
        lobby = self.arena.data['lobby']
        return dict(revision=self.arena.data['revision'], lobby_id=lobby['id'])

    def test_rank_and_custom_closed_status_has_actionable_flags_without_mutation(self):
        for mode in ('rank', 'custom'):
            self.arena.data['lobby'] = None
            self.room(mode)
            before = deepcopy(self.arena.data)
            view = _arena_status(self.state, mode)
            self.assertEqual('interrupted', view['status'])
            self.assertTrue(all(view[key] for key in ('can_resume', 'can_simulate', 'can_rts')))
            self.assertEqual(before, self.arena.data)

    def test_custom_and_rank_can_simulate_after_exit_once_without_career_rewards(self):
        for mode, command in (('rank', ladder_command), ('custom', custom_command)):
            self.arena.data['lobby'] = None
            lobby = self.room(mode)
            before = self.state.career.money
            first = command(self.state, 'simulate', self.body())
            changes = deepcopy(self.arena.data['ladder'])
            second = command(self.state, 'simulate', self.body())
            self.assertTrue(second['replayed'])
            self.assertEqual('simulated', first['result']['source'])
            self.assertEqual(changes, self.arena.data['ladder'])
            self.assertEqual(before, self.state.career.money)
            self.assertEqual('retired-game-nonce', lobby['career3d_retired_sessions'][0]['session']['nonce'])
            if mode == 'custom':
                self.assertEqual({}, first['result']['changes'])

    def test_result_written_on_exit_is_ingested_instead_of_simulation(self):
        lobby = self.room('custom')
        self.peek_mock.return_value = arena_fixtures.result_for(lobby)
        with patch('tools.career3d_activities._simulate') as simulate:
            out = custom_command(self.state, 'simulate', self.body())
        self.assertEqual('collected', out['status'])
        self.assertEqual('cs2', out['result']['source'])
        self.assertEqual(1, len(self.arena.data['matches']))
        self.assertNotIn('career3d_retired_sessions', self.arena.data['lobby'])
        simulate.assert_not_called()

    def test_custom_rts_is_settleable_after_exit_and_old_cs2_dump_cannot_settle_it(self):
        lobby = self.room('custom')
        body = dict(revision=7, arena_revision=self.arena.data['revision'], lobby_id=lobby['id'])
        out = rts_command(self.state, 'arena_start', body)
        session = out['rts_session']
        self.assertEqual('custom', session['mode'])
        self.assertNotEqual('retired-game-nonce', session['nonce'])
        with self.assertRaisesRegex(ValueError, '待录入'):
            self.arena.ingest(self.body(), arena_fixtures.result_for(dict(lobby, nonce='retired-game-nonce')))
        report = completed_report(session)
        body.update(arena_revision=self.arena.data['revision'], nonce=session['nonce'], report=report)
        settled = rts_command(self.state, 'arena_submit', body)
        self.assertEqual({}, settled['arena_result']['changes'])
        self.assertEqual('rts', settled['arena_result']['source'])
        self.assertTrue(rts_command(self.state, 'arena_submit', body)['replayed'])
        self.assertEqual(1, len(self.arena.data['matches']))

    def test_live_unknown_or_fresh_launch_never_changes_the_room(self):
        lobby = self.room('custom')
        before = deepcopy(lobby)
        with patch('tools.career3d_activities._running_cs2', return_value=True):
            with self.assertRaisesRegex(ValueError, 'CS2 正在运行'):
                recover_arena_cs2(self.state, self.body(), 'custom', 'simulate')
        with patch('tools.career3d_activities._running_cs2', side_effect=RuntimeError('cannot query')):
            with self.assertRaises(RuntimeError):
                recover_arena_cs2(self.state, self.body(), 'custom', 'cs2')
        self.assertEqual(before, lobby)
        lobby['launch_requested_at'] = utc_stamp()
        fresh = deepcopy(lobby)
        with self.assertRaisesRegex(ValueError, '正在启动'):
            recover_arena_cs2(self.state, self.body(), 'custom', 'rts')
        self.assertEqual(fresh, lobby)

    def test_game_request_handoff_failure_keeps_arena_pending_and_unsettled(self):
        self.room('custom')
        before = deepcopy(self.arena.data)
        with patch('tools.career3d_activities.read_cs2_config', return_value=dict(csgo_path='X:/offline-fixture')), \
             patch('cs2career.cs2.launch.deactivate_match_request', side_effect=PermissionError('retirement denied')):
            with self.assertRaisesRegex(PermissionError, 'retirement denied'):
                custom_command(self.state, 'simulate', self.body())
        self.assertEqual(before, self.arena.data)

    def test_arena_restart_prepares_frozen_room_with_new_nonce_and_external_skin_handoff(self):
        from cs2career.cs2 import launch
        lobby = self.room('custom')
        old_nonce = lobby['nonce']
        self.state.career.real_skins = True
        frozen = dict(launch.DEFAULTS, difficulty='Medium', skins_inventory_mode='external', csgo_path='X:/offline-fixture')
        lobby['3d_settings'] = frozen
        lobby['3d_cosmetics'] = {key: deepcopy(getattr(self.state.career, key)) for key in
            ('inventory', 'equipped_ct', 'equipped_t', 'steam_id', 'real_skins')}
        captured = []
        def dispatch(*args, **kwargs):
            captured.append(deepcopy(kwargs['request_override']))
            self.assertTrue(kwargs['existing_plugins'])
            launch.prepare_existing_skins(Path('X:/offline-fixture'), kwargs['career'], kwargs['config'])
            self.assertEqual('Medium', kwargs['config']['difficulty'])
            return dict(msg='fixture prepared')
        with patch('tools.career3d_activities.read_cs2_config', return_value=dict(launch.DEFAULTS, csgo_path='X:/offline-fixture')), \
             patch('cs2career.cs2.launch.require_cs2_closed'), \
             patch('cs2career.cs2.launch.start_match', side_effect=dispatch), \
             patch.object(launch, '_write_settings'), \
             patch('cs2career.cs2.launch._prepare_external_skins', return_value=0) as handoff, \
             patch('cs2career.career.skins.plugin_installed', return_value=False) as plugin:
            out = custom_command(self.state, 'launch', self.body())
        self.assertEqual('waiting', out['status'])
        self.assertTrue(out['restarted_map'])
        self.assertNotEqual(old_nonce, captured[0]['nonce'])
        bots = captured[0]['ct']['players'] + captured[0]['t']['players']
        self.assertEqual(set(lobby['roster']), {p['player_id'] for p in bots})
        self.assertEqual(10, len(bots))  # custom spectator
        handoff.assert_called_once()
        plugin.assert_not_called()
        self.assertEqual('starting', out['connection']['status'])

    def test_custom_rts_directed_side_is_respected_and_invalid_choice_keeps_cs2_request(self):
        lobby = self.room('custom')
        before = deepcopy(lobby)
        body = dict(revision=7, arena_revision=self.arena.data['revision'], lobby_id=lobby['id'])
        with self.assertRaisesRegex(ValueError, '指挥侧'):
            rts_command(self.state, 'arena_start', dict(body, commanded_side='a'))
        self.assertEqual(before, lobby)
        out = rts_command(self.state, 'arena_start', dict(body, commanded_side='t'))
        self.assertEqual('t', out['rts_session']['commanded_side'])


if __name__ == '__main__':
    unittest.main()
