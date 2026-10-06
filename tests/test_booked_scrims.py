"""Booked practice launch/collection uses real save boundaries and fake Steam."""
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch
import unittest

import test_activity_launch_boundary as boundary
from cs2career.application import ApplicationState
from cs2career.services import activities, activity_launch, controls, matches, scrims
from cs2career.cs2.result import result_usable


class BookedScrimTests(unittest.TestCase):
    setUp = boundary.ActivityLaunchBoundaryTests.setUp
    career_fixture = boundary.ActivityLaunchBoundaryTests.career_fixture
    serving = boundary.ActivityLaunchBoundaryTests.serving
    request = boundary.ActivityLaunchBoundaryTests.request

    def ready(self):
        boundary.ActivityLaunchBoundaryTests.ready(self, 'training')
        with self.state.operation():
            activities.scrim_command(self.state, 'schedule', dict(opponent_id=self.body['opponent_id'],
                                      map='dust2', date=self.state.season.date))
            self.state.persist()
        self.booking = self.records()[0]
        self.path = '/api/3d/scrim/launch'
        self.body = dict(id=self.booking['id'], side='t', revision=0, request_id='booked-launch-0001')
        self.stack.enter_context(patch.object(scrims, '_raw', return_value={'status':'none'}))

    def records(self, state=None):
        return (state or self.state).career.incident_state['career3d_service']['scrims']

    def session(self, state=None):
        return (state or self.state).career.training_session

    def dispatch(self, cfg, args, kwargs):
        self.sent = deepcopy(kwargs['request_override'])
        self.assertEqual('launched', self.records(ApplicationState())[0]['status'])
        self.assertEqual(self.booking['id'], self.session(ApplicationState())['booking_id'])
        return boundary.ActivityLaunchBoundaryTests.dispatch(self, cfg, args, kwargs)

    def launch(self):
        with patch.object(matches, '_dispatch_launch', side_effect=self.dispatch) as call:
            out = activity_launch.command(self.state, self.path, self.body)
        return out, call

    def finish_body(self):
        return dict(id=self.booking['id'], nonce=self.session()['nonce'])

    def raw_result(self):
        request = self.sent
        players = [dict(player_id=request['human_player_id'], name=request['player'],
                        team=request['human_team'], kills=4, deaths=5, assists=1, damage=800, kast=.7)]
        for side in ('ct','t'):
            for player in request[side]['players']:
                players.append(dict(player_id=player['player_id'], name=player['display_name'], team=side,
                                    kills=4, deaths=5, assists=1, damage=800, kast=.7))
        out = dict(schema_version=2, status='finished', complete=True, request_nonce=request['nonce'],
                   map='de_dust2', ct_score=3, t_score=13, players=players,
                   ended_at=datetime.now(timezone.utc).isoformat())
        self.assertEqual('', result_usable(out, self.session()))
        return out

    def perform(self, action, body):
        with self.state.operation():
            out = activities.scrim_command(self.state, action, body)
            self.state.persist()
            return out

    def test_launch_is_durable_and_replay_never_starts_steam_twice(self):
        self.ready()
        out, call = self.launch()
        self.assertEqual('waiting', out['status'])
        call.assert_called_once()
        self.assertEqual('t', self.session()['side'])
        self.assertEqual('de_dust2', self.sent['map'])
        with patch.object(matches, '_dispatch_launch', side_effect=AssertionError('duplicate launch')):
            self.assertTrue(activity_launch.command(ApplicationState(), self.path, self.body)['replayed'])

    def test_http_launch_uses_external_commit_boundary(self):
        self.ready()
        with self.serving(), patch.object(matches, '_dispatch_launch', side_effect=self.dispatch):
            code, result = self.request(self.path, self.body)
        self.assertEqual(200, code, result)
        self.assertEqual('waiting', result['status'])
        self.assertEqual(self.booking['id'], result['context']['scrims']['pending']['booking_id'])

    def test_collect_saves_ten_player_report_without_rewards_and_replays(self):
        self.ready(); self.launch()
        body = self.finish_body()
        before = deepcopy((self.state.career.money, self.state.career.attr_points,
                           self.state.career.last_scrim, self.state.season.teams, self.state.arena.data))
        with patch.object(scrims, '_raw', return_value=self.raw_result()):
            result = self.perform('collect', body)
        report = result['report']
        self.assertEqual('cs2', report['source'])
        self.assertEqual('13-3', report['map']['score'])
        self.assertEqual(10, sum(map(len, report['map']['players'].values())))
        self.assertEqual(report['teams'][0], report['map']['winner'])
        self.assertIsNone(self.session())
        self.assertEqual(before, (self.state.career.money, self.state.career.attr_points,
                         self.state.career.last_scrim, self.state.season.teams, self.state.arena.data))
        self.assertEqual(report, self.records(ApplicationState())[0]['report'])
        self.assertTrue(self.perform('collect', body)['replayed'])

    def test_stale_or_incomplete_results_do_not_consume_booking(self):
        self.ready(); self.launch()
        valid = self.raw_result()
        for changes in ({'request_nonce':'old'}, {'status':'in_progress'}, {'map':'de_mirage'}, {'map':''}, {'ct_score':17,'t_score':13}):
            with self.subTest(changes=changes), patch.object(scrims, '_raw', return_value=dict(valid, **changes)):
                with self.assertRaises(ValueError): self.perform('collect', self.finish_body())
                self.assertIsNotNone(self.session())
                self.assertEqual('launched', self.records()[0]['status'])

    def test_cancel_requires_exact_session_and_closed_game_then_allows_simulation(self):
        self.ready(); self.launch()
        body = dict(self.finish_body(), confirmed=True)
        with self.assertRaises(ValueError): self.perform('cancel', dict(body, nonce='old'))
        with patch.object(activities, '_running_cs2', return_value=True):
            with self.assertRaises(ValueError): self.perform('cancel', body)
        self.perform('cancel', body)
        self.assertIsNone(self.session())
        self.assertEqual('scheduled', self.records()[0]['status'])
        self.assertEqual('simulated', self.perform('simulate', {'id':self.booking['id']})['report']['source'])

    def test_completed_result_wins_race_with_cancel(self):
        self.ready(); self.launch()
        with patch.object(scrims, '_raw', return_value=self.raw_result()):
            out = self.perform('cancel', dict(self.finish_body(), confirmed=True))
        self.assertEqual('cs2', out['report']['source'])

    def test_restart_changes_nonce_and_preserves_booking(self):
        self.ready(); self.launch()
        old = self.session()['nonce']
        self.body.update(nonce=old, request_id='booked-restart-0002', revision=2)
        self.launch()
        self.assertNotEqual(old, self.session()['nonce'])
        self.assertEqual(self.booking['id'], self.session()['booking_id'])

    def test_other_booking_and_future_date_never_launch(self):
        self.ready()
        self.booking['date'] = '2099-01-01'
        with patch.object(matches, '_dispatch_launch') as call:
            with self.assertRaises(ValueError): activity_launch.command(self.state, self.path, self.body)
        call.assert_not_called()
        self.booking = self.records()[0]; self.booking['date'] = self.state.season.date
        self.launch()
        with self.assertRaises(ValueError): self.perform('collect', {'id':'wrong','nonce':self.session()['nonce']})

    def test_training_controls_finish_also_preserves_booked_report(self):
        self.ready(); self.launch()
        with self.state.operation(), patch.object(scrims, '_raw', return_value=self.raw_result()):
            out = controls.controls_command(self.state, 'training/finish', {'revision':2})
            self.state.persist()
        self.assertEqual('cs2', out['report']['source'])
        self.assertEqual('finished', self.records()[0]['status'])

    def test_failed_dispatch_retains_booking_for_explicit_recovery(self):
        self.ready()
        with patch.object(matches, '_dispatch_launch', side_effect=OSError('Steam unavailable')):
            out = activity_launch.command(self.state, self.path, self.body)
        self.assertEqual('failed', out['status'])
        restored = ApplicationState()
        self.assertEqual('uncertain', self.session(restored)['launch_state'])
        self.assertEqual('launched', self.records(restored)[0]['status'])


if __name__ == '__main__': unittest.main()
