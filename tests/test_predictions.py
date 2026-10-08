from copy import deepcopy
import unittest
from unittest.mock import patch

import test_recovery_http as fixture
from cs2career.application import ApplicationState
from cs2career.career import predictions as p, skin_market
from cs2career.engine.match import RNG
from cs2career.services import predictions as service, matches
from cs2career.storage import transaction as tx


class PredictionTests(unittest.TestCase):
    setUp = fixture.RecoveryHttpTests.setUp
    career_fixture = fixture.RecoveryHttpTests.career_fixture
    serving = fixture.RecoveryHttpTests.serving
    request = fixture.RecoveryHttpTests.request

    def ready(self):
        c, s, m = self.career_fixture()
        a, b = [t for t in s.teams if t['id'] != c.team_id][:2]
        m.update(team_a=a['name'], team_b=b['name'])
        c.money = 10000
        self.state.persist()
        return c, s, s.events[0], m

    def body(self, c, s, e, m, **changes):
        q = p.quote(c, s, e, m)
        return dict(key=q['key'], quote_id=q['quote_id'], team_id=q['team_a']['id'],
                    outcome='win', stake=1000, revision=matches._revision(self.state), **changes)

    def test_series_chance_symmetry_and_strength(self):
        for n in (1, 3, 5):
            self.assertAlmostEqual(.5, p.series_probability([.5]*n))
            self.assertGreater(p.series_probability([.6]*n), .5)
            self.assertAlmostEqual(1, p.series_probability([.6]*n) + p.series_probability([.4]*n))

    def test_quotes_reads_and_buy_leave_rng_unchanged(self):
        c, s, e, m = self.ready()
        seed = RNG.getstate()
        before = deepcopy((c.to_dict() if hasattr(c, 'to_dict') else c.incident_state, s.events))
        first = p.page(c, s)
        self.assertEqual(first, p.page(c, s))
        self.assertEqual(before, (c.to_dict() if hasattr(c, 'to_dict') else c.incident_state, s.events))
        p.buy(c, s, self.body(c, s, e, m))
        self.assertEqual(seed, RNG.getstate())

    def test_loss_selection_normalized_and_full_wallet(self):
        c, s, e, m = self.ready()
        body = self.body(c, s, e, m)
        body.update(outcome='lose', stake=c.money)
        p.buy(c, s, body)
        order = p.data(c)['orders'][body['key']]
        self.assertEqual(order['team_b']['id'], order['predicted_winner_id'])
        self.assertEqual(0, c.money)
        m.update(played=True, winner=m['team_b'], series='0-2')
        p.reconcile(c, s)
        self.assertEqual(order['possible_return'], c.money)
        p.reconcile(c, s)
        self.assertEqual(order['possible_return'], c.money)

    def test_invalid_stakes_quotes_and_matches_reject_without_deduction(self):
        c, s, e, m = self.ready()
        body = self.body(c, s, e, m)
        for amount in (0, -1, True, 1.5, '100', 10001):
            with self.assertRaises(ValueError): p.buy(c, s, dict(body, stake=amount))
        with self.assertRaises(ValueError): p.buy(c, s, dict(body, quote_id='stale'))
        for change in ({'played': True}, {'maps':[{}]}, {'cs2_session':{'nonce':'old'}}, {'career3d_rts':{'id':'live'}}, {'team_b':'BYE'}):
            modified = dict(m, **change)
            self.assertFalse(p.eligible(c, s, e, modified))
        self.assertFalse(p.eligible(c, s, e, dict(m, team_a=c.my_team(s.teams)['name'])))
        self.assertEqual(10000, c.money)

    def test_cancel_forfeit_join_refund_and_postponement(self):
        for reason in ('cancelled', 'forfeit', 'join', 'postponed'):
            with self.subTest(reason=reason):
                c, s, e, m = self.ready()
                p.buy(c, s, self.body(c, s, e, m))
                order = next(iter(p.data(c)['orders'].values()))
                if reason == 'join': c.team_id = order['team_a']['id']
                else: m[reason] = True
                p.reconcile(c, s)
                self.assertEqual(9000 if reason == 'postponed' else 10000, c.money)
                self.assertEqual('pending' if reason == 'postponed' else 'refunded', order['status'])

    def test_http_receipt_read_only_and_restart(self):
        c, s, e, m = self.ready()
        body = self.body(c, s, e, m)
        with self.serving():
            before = (self.root/'career.json').read_bytes()
            self.assertEqual(200, self.request('/api/3d/predictions')[0])
            self.assertEqual(before, (self.root/'career.json').read_bytes())
            code, result = self.request('/api/3d/predictions/buy', body, rid='prediction-buy-one')
            self.assertEqual(200, code, result)
            self.assertTrue(self.request('/api/3d/predictions/buy', body, rid='prediction-buy-one')[1]['replayed'])
            self.assertEqual(9000, c.money)
        self.state = ApplicationState()
        with self.serving():
            self.assertTrue(self.request('/api/3d/predictions/buy', body, rid='prediction-buy-one')[1]['replayed'])
        self.assertEqual(9000, self.state.career.money)

    def test_commit_recovery_never_doubles_stake(self):
        c, s, e, m = self.ready()
        body = self.body(c, s, e, m)
        def crash(point):
            if point == 'replaced:career.json': raise OSError('fixture interruption')
        with self.serving(), patch.object(tx, '_checkpoint', crash):
            code, result = self.request('/api/3d/predictions/buy', body, rid='prediction-crash-one')
            self.assertEqual(503, code, result)
        self.state = ApplicationState()
        self.assertEqual(9000, self.state.career.money)
        with self.serving():
            self.assertTrue(self.request('/api/3d/predictions/buy', body, rid='prediction-crash-one')[1]['replayed'])

    def test_ai_result_settles_in_same_commit(self):
        c, s, e, m = self.ready()
        p.buy(c, s, self.body(c, s, e, m))
        with self.state.operation():
            s.play_match(e, m)
            self.state.persist()
        order = next(iter(p.data(c)['orders'].values()))
        self.assertIn(order['status'], ('won', 'lost'))
        reloaded = ApplicationState()
        self.assertEqual(c.money, reloaded.career.money)
        self.assertEqual(order, p.data(reloaded.career)['orders'][order['key']])

    def test_payout_commit_recovers_once(self):
        c, s, e, m = self.ready()
        p.buy(c, s, self.body(c, s, e, m))
        self.state.persist()
        order = next(iter(p.data(c)['orders'].values()))
        expected = c.money + order['possible_return']
        def crash(point):
            if point == 'replaced:career.json': raise OSError('payout interruption')
        with patch.object(tx, '_checkpoint', crash), self.assertRaises(tx.CommitPending):
            with self.state.operation():
                m.update(played=True, winner=m['team_a'], series='2-0')
                p.reconcile(c, s)
                self.state.persist()
        loaded = ApplicationState()
        self.assertEqual(expected, loaded.career.money)
        p.reconcile(loaded.career, loaded.season)
        self.assertEqual(expected, loaded.career.money)
        self.assertTrue(loaded.season.find_match(m['id'])[1]['played'])

    def test_identical_match_results_with_and_without_prediction(self):
        c, s, e, m = self.ready()
        a, b = p.teams(s, m)
        from cs2career.engine.match import play_series
        seed = RNG.getstate()
        control = play_series(deepcopy(a), deepcopy(b), ['dust2','mirage','nuke','ancient','inferno','anubis','train'], 'QF', 3)
        RNG.setstate(seed)
        p.page(c, s)
        p.buy(c, s, self.body(c, s, e, m))
        actual = play_series(deepcopy(a), deepcopy(b), ['dust2','mirage','nuke','ancient','inferno','anubis','train'], 'QF', 3)
        self.assertEqual(control, actual)

    def test_newly_created_fixtures_stop_before_play(self):
        c, s, e, m = self.ready()
        e['matches'] = []
        e['status'] = 'upcoming'
        def create():
            e.update(status='live', matches=[m])
        with patch.object(s, '_calendar_pause', return_value=''), patch.object(s, 'advance_event'), patch.object(s, 'ensure_live', side_effect=create), patch.object(s, 'play_match', side_effect=AssertionError('must stop before new fixtures play')), patch.object(c, 'tick'), patch.object(c, 'watch'), patch.object(c, 'dispatch_invites'):
            s.next_stage(stop_at_season_end=True, prepare_only=True, prediction_stop=True)
        self.assertTrue(p.available(c,s))
        self.assertFalse(m['played'])

    def test_important_choice_and_own_match_block_advance(self):
        c, s, e, m = self.ready()
        c.story_queue = [dict(id='choice', choices=[dict(id='yes')])]
        with patch.object(s, 'next_stage', side_effect=AssertionError('choice may not be skipped')):
            self.assertEqual('paused', service.command(self.state, 'advance', {'revision':0})['prediction_status'])
        c.story_queue.clear()
        m['team_a'] = c.my_team(s.teams)['name']
        with patch.object(s, 'next_stage', side_effect=AssertionError('own match may not be skipped')):
            self.assertEqual('paused', service.command(self.state, 'advance', {'revision':0})['prediction_status'])

    def test_advance_existing_fixtures_is_noop(self):
        c, s, e, m = self.ready()
        with patch.object(service, 'stop_reason', return_value=''), patch.object(s, 'next_stage', side_effect=AssertionError('must not advance')):
            out = service.command(self.state, 'advance', {'revision':0})
        self.assertEqual('ready', out['prediction_status'])
        self.assertFalse(m['played'])

    def test_prediction_boundary_does_not_roll_maps(self):
        c, s, e, m = self.ready()
        with patch.object(s, '_calendar_pause', return_value=''), patch.object(s, 'advance_event'), patch.object(s, 'ensure_live'), patch.object(s, 'play_match', side_effect=AssertionError('no map yet')), patch.object(c, 'tick'), patch.object(c, 'watch'), patch.object(c, 'dispatch_invites'):
            s.next_stage(stop_at_season_end=True, prepare_only=True, prediction_stop=True)
        self.assertFalse(m['played'])

    def test_rumor_target_supported_and_projection_pure(self):
        c, s, e, m = self.ready()
        skin_market.command(c, s.date, 'rumor', {})
        before = deepcopy(c.incident_state)
        for day in (s.date, '2099-01-01'):
            rumor = skin_market.merchant(c, day)['rumors'][0]
            item = skin_market.detail(c, day, rumor['detail_target']['id'], rumor['detail_target']['wear_id'])
            self.assertEqual(rumor['skin_id'], item['id'])
        self.assertEqual(before, c.incident_state)


if __name__ == '__main__': unittest.main()
