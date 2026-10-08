from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs2career.world import map_form as mf
from cs2career.engine import match as engine


def team(name, ability=75):
    return dict(id=name, name=name, world_rank=10, command=75, mentality=70, map_adaptation=65,
                strong_maps=['mirage'], weak_maps=['nuke'],
                players=[dict(name=f'{name}{i}', player_id=f'{name}{i}', ability=ability, role='rifle') for i in range(5)])


def box(a, name='dust2'):
    return dict(map=name, winner=a['name'], score='13-8')


class MapFormTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b = team('A'), team('B')

    def test_projection_keeps_legacy_values_without_writes(self):
        old = deepcopy(self.a)
        self.assertEqual([90, 65, 40], [mf.rating(self.a, m) for m in ('de_mirage', 'dust2', 'nuke')])
        self.assertEqual([1.2, .05, -1.1], [round(mf.comfort(self.a, m), 2) for m in ('mirage', 'dust2', 'nuke')])
        mf.public(self.a)
        self.assertEqual(old, self.a)

    def test_peer_loss_small_decline_form_symmetric_and_once_per_box(self):
        result = box(self.a)
        changes = mf.apply_result(self.a, self.b, result, '2026-01-08')
        self.assertAlmostEqual(changes[0]['form_delta'], -changes[1]['form_delta'])
        self.assertGreater(changes[0]['strength_delta'], 0)
        self.assertLess(changes[1]['strength_delta'], 0)
        self.assertGreater(changes[1]['strength_delta'], -.45)
        self.assertGreater(changes[0]['delta'] + changes[1]['delta'], 0)
        before = deepcopy((self.a, self.b))
        self.assertEqual(changes, mf.apply_result(self.a, self.b, result, '2026-01-08'))
        self.assertEqual(before, (self.a, self.b))

    def test_losing_to_stronger_team_teaches_more_but_can_reduce_total(self):
        a1, a2 = deepcopy(self.a), deepcopy(self.a)
        weak, strong = team('weak', 45), team('strong', 99)
        low = mf.apply_result(a1, weak, box(weak), '2026-01-08')[0]
        high = mf.apply_result(a2, strong, box(strong), '2026-01-08')[0]
        self.assertGreater(high['strength_delta'], low['strength_delta'])
        self.assertLess(low['strength_delta'], 0)
        self.assertGreater(high['strength_delta'], 0)
        self.assertLess(high['form_delta'], 0)
        self.assertGreater(high['form_delta'], low['form_delta'])
        self.assertLess(high['delta'], 0)
        self.assertAlmostEqual(high['delta'], high['strength_delta'] + high['form_delta'], places=2)

    def test_learning_diminishes_with_mastery_and_is_not_free_full_rating(self):
        a, b = team('weak', 45), team('strong', 99)
        first = mf.apply_result(a, b, box(b), '2026-01-08')[0]['strength_delta']
        for _ in range(49): mf.apply_result(a, b, box(b), '2026-01-08')
        self.assertLess(mf.row(a, 'dust2')['strength'], 85)
        self.assertLess(mf.row(a, 'dust2')['last_change']['strength_delta'], first)
        mf.row(a, 'dust2')['strength'] = 100
        final = mf.apply_result(a, b, box(b), '2026-01-08')[0]
        self.assertEqual(0, final['strength_delta'])

    def test_legacy_result_is_not_recalculated_or_given_invented_components(self):
        legacy = box(self.a)
        legacy['map_form_changes'] = [dict(delta=-1, before=65, after=64)]
        before = deepcopy((self.a, self.b, legacy))
        mf.apply_result(self.a, self.b, legacy, '2026-01-08')
        self.assertEqual(before, (self.a, self.b, legacy))

    def test_practice_is_one_third_of_official_result(self):
        a, b = deepcopy(self.a), deepcopy(self.b)
        official = mf.apply_result(self.a, self.b, box(self.a), '2026-01-08')[0]
        practice = mf.apply_result(a, b, box(a), '2026-01-08', practice=True)[0]
        self.assertAlmostEqual(official['delta'] / 3, practice['delta'], places=2)
        self.assertAlmostEqual(official['strength_delta'] / 3, practice['strength_delta'], places=4)
        self.assertAlmostEqual(official['form_delta'] / 3, practice['form_delta'], places=4)

    def test_strength_of_opponent_changes_learning_not_player_attributes(self):
        weak, strong = team('weak', 45), team('strong', 99)
        a1, a2 = deepcopy(self.a), deepcopy(self.a)
        low = mf.apply_result(a1, weak, box(a1), '2026-01-08')[0]['delta']
        high = mf.apply_result(a2, strong, box(a2), '2026-01-08')[0]['delta']
        self.assertGreater(high, low)
        self.assertEqual(self.a['players'], a1['players'])
        self.assertEqual(self.a['players'], a2['players'])

    def test_existing_map_defaults_survive_first_migration(self):
        mf.apply_result(self.a, self.b, box(self.a), '2026-01-08')
        self.assertEqual(90, mf.rating(self.a, 'mirage'))
        self.assertEqual(40, mf.rating(self.a, 'nuke'))

    def test_daily_focus_settles_once_not_per_skipped_day(self):
        mf.apply_result(self.a, self.b, box(self.b, 'mirage'), '2026-01-08')
        form = mf.row(self.a, 'mirage')['form']
        strength = mf.row(self.a, 'mirage')['strength']
        mf.schedule_practice(self.a, 'de_dust2', '2026-01-08')
        mf.schedule_practice(self.a, 'mirage', '2026-01-08')
        mf.settle_practice([self.a], '2026-01-08')
        self.assertEqual(strength, mf.row(self.a, 'mirage')['strength'])
        mf.settle_practice([self.a], '2026-02-18')
        self.assertGreater(mf.row(self.a, 'mirage')['strength'], strength)
        self.assertLessEqual(mf.row(self.a, 'mirage')['strength'], 90)
        self.assertEqual(form, mf.row(self.a, 'mirage')['form'])
        self.assertEqual(0, mf.row(self.a, 'mirage')['last_change']['form_delta'])
        previous = deepcopy(self.a)
        mf.settle_practice([self.a], '2026-03-01')
        self.assertEqual(previous, self.a)
        with self.assertRaises(ValueError): mf.schedule_practice(self.a, 'dust2', '2026-01-08')
        mf.schedule_practice(self.a, 'dust2', '2026-03-01')
        mf.settle_practice([self.a], '2026-03-02')
        self.assertEqual(65, mf.rating(self.a, 'dust2'), 'practice cannot invent a new peak')

    def test_focus_recovers_to_match_peak_only_and_next_match_can_break_it(self):
        mf.apply_result(self.a, self.b, box(self.a), '2026-01-08')
        peak = mf.row(self.a, 'dust2')['practice_ceiling']
        mf.apply_result(self.a, self.b, box(self.b), '2026-01-09')
        for day in range(10, 20):
            mf.schedule_practice(self.a, 'dust2', f'2026-01-{day}')
            mf.settle_practice([self.a], f'2026-01-{day+1}')
        self.assertEqual(peak, mf.row(self.a, 'dust2')['strength'])
        self.assertEqual(peak, mf.row(self.a, 'dust2')['practice_ceiling'])
        mf.apply_result(self.a, self.b, box(self.a), '2026-01-21')
        self.assertGreater(mf.row(self.a, 'dust2')['strength'], peak)

    def test_upset_costs_more_than_peer_loss_but_single_loss_is_bounded(self):
        peer = mf.apply_result(self.a, self.b, box(self.b, 'mirage'), '2026-01-08')[0]
        a, weak = team('A'), team('weak', 45)
        upset = mf.apply_result(a, weak, box(weak, 'mirage'), '2026-01-08')[0]
        self.assertLess(upset['strength_delta'], peer['strength_delta'])
        self.assertGreaterEqual(upset['strength_delta'], -.45)
        self.assertEqual('strong', mf.row(a, 'mirage')['label'])

    def test_label_hysteresis_and_one_loss_preserve_strong_map(self):
        mf.apply_result(self.a, self.b, box(self.b, 'mirage'), '2026-01-08')
        self.assertEqual('strong', mf.row(self.a, 'mirage')['label'])
        item = self.a['map_form']['maps']['mirage']
        item.update(strength=73, form=0)
        mf._labels(self.a, 'mirage')
        self.assertEqual('strong', item['label'])
        item.update(strength=71)
        mf._labels(self.a, 'mirage')
        self.assertEqual('neutral', item['label'])
        item.update(strength=74)
        mf._labels(self.a, 'mirage')
        self.assertEqual('neutral', item['label'])

    def test_bounds_and_recent_history_are_bounded(self):
        for _ in range(150): mf.apply_result(self.a, self.b, box(self.a), '2026-01-08', practice=True)
        for t in (self.a, self.b):
            self.assertLessEqual(mf.rating(t, 'dust2'), 100)
            self.assertGreaterEqual(mf.rating(t, 'dust2'), 0)
            self.assertLessEqual(abs(mf.row(t, 'dust2')['form']), 10)
            self.assertEqual(20, len(mf.row(t, 'dust2')['recent']))

    def test_bp_prefers_trained_map_and_opponent_bans_it_more(self):
        with patch.object(engine, '_noise', return_value=0):
            pick = engine._pick_value(self.a, self.b, 'dust2')
            ban = engine._ban_value(self.b, self.a, 'dust2')
            mf.apply_result(self.a, self.b, box(self.a), '2026-01-08')
            self.assertGreater(engine._pick_value(self.a, self.b, 'dust2'), pick)
            self.assertGreater(engine._ban_value(self.b, self.a, 'dust2'), ban)
        self.assertEqual(.04, engine.MAP_SHARE)

    def test_simulation_preview_and_arena_do_not_commit_learning(self):
        before = deepcopy((self.a, self.b))
        result = engine.play_map(self.a, self.b, 'dust2')
        self.assertIn('map_expectation', result)
        self.assertNotIn('map_form_changes', result)
        self.assertEqual(before, (self.a, self.b))

    def test_ai_series_learns_each_map_without_replaying_old_history(self):
        seen = []
        def accept(result, index):
            seen.append(index)
            mf.apply_result(self.a, self.b, result, '2026-01-08')
        result = engine.play_series(self.a, self.b, ['dust2', 'nuke', 'mirage', 'inferno', 'ancient', 'anubis', 'train'], 'group', on_map=accept)
        self.assertEqual(list(range(len(result['maps']))), seen)
        self.assertTrue(all(len(r['map_form_changes']) == 2 for r in result['maps']))

    def test_rts_factor_is_bounded_and_not_a_player_stat_mutation(self):
        before = deepcopy(self.a)
        self.assertEqual(.95, mf.reaction_factor(self.a, 'mirage'))
        self.assertEqual(1.05, mf.reaction_factor(self.a, 'nuke'))
        self.assertEqual(1, mf.reaction_factor(self.a, 'dust2'))
        self.assertEqual(before, self.a)


class MapInactivityTests(unittest.TestCase):
    def test_grace_does_not_reclassify_untouched_legacy_labels(self):
        a = team('A')
        a['map_adaptation'] = 85
        mf.advance_calendar([a], '2026-01-01', '2026-01-15')
        self.assertEqual(['mirage'], a['strong_maps'])
        self.assertEqual(['nuke'], a['weak_maps'])
        self.assertEqual('neutral', mf.row(a, 'dust2')['label'])

    def test_automatic_training_maintains_all_teams_and_maps(self):
        a, b = team('A'), team('B')
        players = deepcopy(a['players'])
        mf.advance_calendar([a, b], '2026-01-01', '2026-01-15')
        self.assertEqual(90, mf.rating(a, 'mirage'))
        mf.advance_calendar([a, b], '2026-01-15', '2026-01-16')
        for t in (a, b):
            self.assertEqual(90, mf.rating(t, 'mirage'))
            self.assertEqual(40, mf.rating(t, 'nuke'))
            self.assertIsNone(mf.row(t, 'mirage')['last_change'])
            self.assertTrue(all(r['automatic_training'] for r in mf.public(t)))
        self.assertEqual(players, a['players'])
        self.assertIn('mirage', a['strong_maps'])

    def test_jumps_and_daily_steps_are_equal_and_repeated_date_is_noop(self):
        from datetime import date, timedelta
        a, b = team('A'), team('B')
        mf.apply_result(a, b, box(a), '2026-01-01')
        daily = deepcopy(a)
        mf.advance_calendar([a], '2026-01-01', '2026-04-11')
        start = date(2026, 1, 1)
        for i in range(100):
            mf.advance_calendar([daily], (start + timedelta(days=i)).isoformat(),
                                (start + timedelta(days=i + 1)).isoformat())
        for name in a['map_form']['maps']:
            self.assertEqual(mf.rating(a, name), mf.rating(daily, name))
            self.assertEqual(mf.row(a, name)['inactivity'], mf.row(daily, name)['inactivity'])
            self.assertEqual(mf.row(a, name)['label'], mf.row(daily, name)['label'])
        previous = deepcopy(a)
        mf.advance_calendar([a], '2026-01-01', '2026-04-11')
        self.assertEqual(previous, a)
        mf.advance_calendar([a], '2026-04-11', '2026-04-11')
        self.assertEqual(previous, a)

    def test_long_absence_is_bounded_and_negative_form_does_not_improve(self):
        a, b = team('A'), team('B')
        mf.apply_result(a, b, box(b), '2026-01-01')
        strength = mf.row(a, 'dust2')['strength']
        form = mf.row(a, 'dust2')['form']
        mf.advance_calendar([a], '2026-01-01', '2036-01-01')
        self.assertEqual(strength, mf.row(a, 'dust2')['strength'])
        self.assertEqual(form, mf.row(a, 'dust2')['form'])
        self.assertEqual(90, mf.rating(a, 'mirage'))
        self.assertEqual('strong', mf.row(a, 'mirage')['label'])

    def test_match_resets_only_played_map_after_result_and_does_not_restore_losses(self):
        a, b = team('A'), team('B')
        mf.advance_calendar([a, b], '2026-01-01', '2026-02-01')
        mf.apply_result(a, b, box(a), '2026-02-01', practice=True)
        before = mf.rating(a, 'dust2')
        self.assertGreater(before, 65)
        mf.advance_calendar([a, b], '2026-02-01', '2026-02-15')
        self.assertEqual(before, mf.rating(a, 'dust2'))
        self.assertEqual(14, next(r for r in mf.public(a) if r['map'] == 'dust2')['inactive_days'])
        self.assertEqual(mf.rating(a, 'mirage'), 90)

    def test_scheduled_focus_recovers_without_passive_gains_or_decay(self):
        a = team('A')
        mf.apply_result(a, team('B'), box(team('B'), 'mirage'), '2026-01-01')
        mf.advance_calendar([a], '2026-01-01', '2026-02-01')
        before = mf.rating(a, 'mirage')
        mf.schedule_practice(a, 'mirage', '2026-02-01')
        mf.advance_calendar([a], '2026-02-01', '2026-02-15')
        practiced = mf.rating(a, 'mirage')
        self.assertGreater(practiced, before)
        self.assertEqual('2026-02-01', mf.row(a, 'mirage')['inactivity']['since'])
        mf.advance_calendar([a], '2026-02-15', '2026-02-16')
        self.assertAlmostEqual(practiced, mf.rating(a, 'mirage'), places=4)
        self.assertTrue(a['map_practice']['settled'])

    def test_legacy_save_does_not_backfill_old_matches_or_mutate_on_read(self):
        a = team('A')
        value = mf._ensure(a, 'dust2')
        value['recent'] = [dict(date='2020-01-01', won=True)]
        value['last_change'] = dict(date='2020-01-01')
        before = deepcopy(a)
        mf.public(a)
        self.assertEqual(before, a)
        mf.advance_calendar([a], '2026-10-06', '2026-10-07')
        self.assertEqual(65, mf.rating(a, 'dust2'))
        self.assertEqual('2026-10-06', value['inactivity']['since'])

    def test_old_decay_is_not_refunded_and_stale_snapshot_cannot_subtract_again(self):
        a = team('A')
        value = mf._ensure(a, 'dust2')
        value.update(strength=61, practice_ceiling=61,
                     inactivity=dict(since='2026-01-01', through='2026-02-01', strength=65, form=0))
        value.pop('practice_ceiling')  # v1 legacy row
        mf.advance_calendar([a], '2026-02-01', '2026-07-01')
        self.assertEqual(61, value['strength'])
        self.assertEqual(61, value['practice_ceiling'])


import test_match_simulation_boundary as boundary
from cs2career.application import ApplicationState
from cs2career.services import match_simulation, controls


class MapFormTransactionTests(unittest.TestCase):
    setUp = boundary.MapSimulationBoundaryTests.setUp
    career_fixture = boundary.MapSimulationBoundaryTests.career_fixture
    ready = boundary.MapSimulationBoundaryTests.ready
    quiet = boundary.MapSimulationBoundaryTests.quiet
    body = boundary.MapSimulationBoundaryTests.body
    saved_match = boundary.MapSimulationBoundaryTests.saved_match

    def test_series_map_changes_survive_restart_and_request_replay(self):
        self.ready()
        body = self.body('map-form-series-1')
        result = match_simulation.command(self.state, body)
        for mp in result['result']['maps']:
            self.assertEqual(2, len(mp['map_form_changes']))
        saved = {t['id']: deepcopy(t.get('map_form')) for t in self.state.season.teams}
        loaded = ApplicationState()
        self.quiet(loaded)
        self.assertTrue(match_simulation.command(loaded, body)['replayed'])
        self.assertEqual(saved, {t['id']: t.get('map_form') for t in loaded.season.teams})

    def test_failed_operation_rolls_back_practice_selection_and_learning(self):
        self.ready()
        before = deepcopy(self.state.season.teams)
        with self.assertRaises(RuntimeError), self.state.operation():
            own = self.state.career.my_team(self.state.season.teams)
            mf.schedule_practice(own, 'dust2', self.state.season.date)
            mf.settle_practice(self.state.season.teams, '2026-12-31')
            self.state.persist()
            raise RuntimeError('fixture failure')
        self.assertEqual(before, self.state.season.teams)

    def test_training_command_is_saved_and_read_projection_is_pure(self):
        self.ready()
        with self.state.operation():
            controls.controls_command(self.state, 'training/map-focus', dict(map='dust2', revision=0))
            self.state.persist()
        loaded = ApplicationState()
        own = loaded.career.my_team(loaded.season.teams)
        self.assertEqual('dust2', own['map_practice']['map'])
        before = deepcopy(loaded.season.teams)
        self.assertEqual(own['map_practice'], controls.training_context(loaded)['map_practice'])
        self.assertEqual(before, loaded.season.teams)

    def test_calendar_crossing_settles_selected_practice(self):
        from datetime import date, timedelta
        self.ready()
        own = self.state.career.my_team(self.state.season.teams)
        today = self.state.season.date
        tomorrow = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
        target = min(mf.public(own), key=lambda r: r['rating'])['map']
        value = mf._ensure(own, target)
        value['strength'] -= 1  # previously reached level is recoverable
        before = mf.rating(own, target)
        with self.state.operation(), patch.object(self.state.season, '_calendar_pause', return_value=''):
            self.state.season.events = []
            mf.schedule_practice(own, target, today)
            self.state.season.next_stage(until=tomorrow)
            self.state.persist()
        loaded = ApplicationState()
        current = loaded.career.my_team(loaded.season.teams)
        self.assertTrue(current['map_practice']['settled'])
        self.assertGreater(mf.rating(current, target), before)

    def test_inactivity_is_transactional_and_restart_cannot_double_deduct(self):
        from datetime import date, timedelta
        self.ready()
        today = self.state.season.date
        later = (date.fromisoformat(today) + timedelta(days=30)).isoformat()
        before = deepcopy(self.state.season.teams)
        with self.assertRaises(RuntimeError), self.state.operation():
            mf.advance_calendar(self.state.season.teams, today, later)
            self.state.persist()
            raise RuntimeError('fixture failure')
        self.assertEqual(before, self.state.season.teams)
        with self.state.operation():
            mf.advance_calendar(self.state.season.teams, today, later)
            self.state.season.date = later
            self.state.persist()
        loaded = ApplicationState()
        before = deepcopy(loaded.season.teams)
        mf.advance_calendar(loaded.season.teams, today, later)
        self.assertEqual(before, loaded.season.teams)

    def test_rts_freezes_modifier_and_settles_map_once(self):
        from tools.career3d_rts import rts_command
        from test_career3d_rts_arena import completed_report
        match = self.ready()
        with self.state.operation():
            result = rts_command(self.state, 'start', dict(self.body(), side='ct'))
            self.state.persist()
        session = result['rts_session']
        frozen = deepcopy(session['rosters']['map_reaction'])
        for value in frozen.values(): self.assertTrue(.95 <= value <= 1.05)
        report = completed_report(session)
        with self.state.operation():
            result = rts_command(self.state, 'submit', dict(self.body(), nonce=session['nonce'], report=report))
            self.state.persist()
        self.assertEqual(2, len(match['maps'][0]['map_form_changes']))
        self.assertEqual(frozen, session['rosters']['map_reaction'])
        before = deepcopy(self.state.season.teams)
        replay = rts_command(self.state, 'submit', dict(self.body(), nonce=session['nonce'], report=report))
        self.assertTrue(replay['replayed'])
        self.assertEqual(before, self.state.season.teams)


import test_match_launch_boundary as launch_boundary


class MapFormCS2Tests(unittest.TestCase):
    setUp = launch_boundary.MatchLaunchBoundaryTests.setUp
    career_fixture = launch_boundary.MatchLaunchBoundaryTests.career_fixture
    ready = launch_boundary.MatchLaunchBoundaryTests.ready
    body = launch_boundary.MatchLaunchBoundaryTests.body

    def dispatch(self, cfg, arguments, kwargs):
        self.sent = deepcopy(kwargs['request_override'])
        return launch_boundary.MatchLaunchBoundaryTests.dispatch(self, cfg, arguments, kwargs)

    def test_real_cs2_map_import_learns_once_without_touching_individual_ability(self):
        from datetime import datetime, timezone
        from cs2career.services import matches, match_launch
        match = self.ready()
        before = [p['ability'] for t in self.state.season.teams for p in t['players']]
        with patch.object(matches, '_dispatch_launch', side_effect=self.dispatch):
            match_launch.command(self.state, self.body())
        session = match['cs2_session']
        self.assertIn('map_expectation', session)
        request = self.sent
        players = [dict(player_id=request['human_player_id'], name=request['player'], team=request['human_team'])]
        players += [dict(player_id=p['player_id'], name=p['display_name'], team=side)
                    for side in ('ct', 't') for p in request[side]['players']]
        result = dict(status='finished', complete=True, schema_version=2, map=request['map'],
            request_nonce=session['nonce'], ended_at=datetime.now(timezone.utc).isoformat(),
            ct_score=13, t_score=8, players=players)
        with self.state.operation():
            self.state.season.commit_cs2_map(match['id'], result, result_reader=lambda **kw: None)
            self.state.persist()
        self.assertEqual(2, len(match['maps'][0]['map_form_changes']))
        self.assertEqual(before, [p['ability'] for t in self.state.season.teams for p in t['players']])
        before_maps = deepcopy([t.get('map_form') for t in self.state.season.teams])
        with self.assertRaises(ValueError):
            self.state.season.commit_cs2_map(match['id'], result, result_reader=lambda **kw: None)
        self.assertEqual(before_maps, [t.get('map_form') for t in self.state.season.teams])


if __name__ == '__main__':
    unittest.main()
