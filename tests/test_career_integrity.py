"""Isolated regression fixtures; these are not full player-playthrough claims."""
import tempfile
import unittest
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
from copy import deepcopy

from cs2career.application import ApplicationState
from cs2career.career import Career
from cs2career.world.roles import apply_roles
from cs2career.world.aging import apply_player_year
from cs2career.world.pool import age_of


class CareerIntegrityTests(unittest.TestCase):
    def setUp(self):
        stack=ExitStack();self.addCleanup(stack.close)
        self.root=Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch('cs2career.league.season.STATE_PATH',self.root/'season.json'))
        stack.enter_context(patch.object(Career,'path',return_value=self.root/'career.json'))
        stack.enter_context(patch('cs2career.paths.save_root',return_value=self.root))
        self.state=ApplicationState()

    def create(self, origin='academy'):
        self.state.create_career(dict(era='2026',mode='create',origin=origin,
            name='Integrity Tester',org='Integrity Club',region='AS',role='rifle'))
        return self.state.career, self.state.career.my_team(self.state.season.teams)

    def test_refresh_preserves_all_three_origins_age_and_annual_increment(self):
        for origin in ('street','academy','prodigy'):
            c,t=self.create(origin);p=c.my_player(self.state.season.teams)
            self.assertEqual(19,p['age'])
            for _ in range(3): self.state.sync()
            self.assertEqual(19,p['age'])
            apply_player_year(p)
            self.assertEqual(20,p['age'])
            self.state.payload();self.state.persist()
            restored=ApplicationState()
            self.assertEqual(20,restored.career.my_player(restored.season.teams)['age'])

    def test_missing_age_uses_current_year_but_custom_age_is_not_replaced(self):
        _,t=self.create();p=t['players'][1];p.pop('age')
        apply_roles([t],'2026',current_year=2029)
        self.assertEqual(age_of(p['name'],2029),p['age'])
        p['age']=17
        apply_roles([t],'2026',current_year=2029)
        self.assertEqual(17,p['age'])

    def test_oversized_repayment_never_creates_money(self):
        c,t=self.create();starting=c.money
        for _ in range(3):
            c.borrow(self.state.season,1000)
            self.assertEqual(1000,c.loan['principal'])
            before=c.money
            c.repay(self.state.season,5000)
            self.assertEqual(before-1000,c.money)
            self.assertIsNone(c.loan)
            c.repay(self.state.season,5000)
            self.assertEqual(before-1000,c.money)
        self.assertEqual(starting-3000,c.money)
        self.assertEqual(-3000,sum(r['amount'] for r in c.cashflow if r.get('scope')=='pocket' and r.get('category')=='loan'))

    def test_partial_and_exact_repayment(self):
        c,t=self.create();c.borrow(self.state.season,1000)
        before=c.money
        c.repay(self.state.season,300)
        self.assertEqual(700,c.loan['principal'])
        self.assertEqual(before-300,c.money)
        c.repay(self.state.season,700)
        self.assertEqual(before-1000,c.money)
        self.assertIsNone(c.loan)

    def training_fixture(self):
        from cs2career.cs2.launch import build_request
        c,t=self.create()
        opp=next(t2 for t2 in self.state.season.teams if t2['id']!=t['id'])
        request=build_request(t,opp,c.player_name,'de_mirage','ct')
        c.remember_training(request)
        raw=dict(schema_version=2,status='finished',complete=True,request_nonce=request['nonce'],
                 map='de_mirage',ct_score=13,t_score=8,ended_at='2099-01-01T00:00:00Z',
                 players=[{'player_id':request['human_player_id'],'team':'ct'}]+[
                     {'player_id':p['player_id'],'team':side} for side in ('ct','t') for p in request[side]['players']])
        return c,t,raw

    def test_training_requires_launched_session_and_matching_complete_result(self):
        c,t=self.create();before=deepcopy(t)
        with self.assertRaisesRegex(ValueError,'没有待核验'):
            c.finish_training(self.state.season)
        self.assertEqual(before,t)
        c,t,raw=self.training_fixture()
        for broken in (dict(raw,request_nonce='old'),dict(raw,complete=False),
                       dict(raw,map='de_nuke'),dict(raw,players=raw['players'][:-1]),
                       dict(raw,status='live',ct_score=3,t_score=2)):
            before=deepcopy(t)
            with patch('cs2career.cs2.launch.read_result',return_value=broken):
                with self.assertRaises(ValueError): c.finish_training(self.state.season)
            self.assertEqual(before,t)
            self.assertIsNotNone(c.training_session)
            self.assertEqual('',c.last_scrim)

    def test_training_reward_consumed_once_and_survives_save_reload(self):
        c,t,raw=self.training_fixture()
        c.save();restored=Career.load()
        self.assertEqual(c.training_session,restored.training_session)
        with patch('cs2career.cs2.launch.read_result',return_value=raw) as read:
            before=t.get('mentality',70)
            restored.finish_training(self.state.season)
            self.assertGreater(t['mentality'],before)
            after=t['mentality']
            read.assert_called_once_with(request_nonce=raw['request_nonce'])
            reloaded=Career.load()
            self.assertIsNone(reloaded.training_session)
            reloaded.finish_training(self.state.season)
            self.assertEqual(after,t['mentality'])
            read.assert_called_once()

    def test_training_result_selection_does_not_prefer_old_high_score(self):
        from cs2career.cs2.launch import read_result
        _,_,raw=self.training_fixture()
        old=dict(raw,request_nonce='old',ct_score=30,t_score=28)
        with patch('cs2career.cs2.launch.settings',return_value={'csgo_path':str(self.root)}), \
             patch('cs2career.cs2.launch._load_result_file',side_effect=[raw,old,old]), \
             patch('cs2career.cs2.launch._remember_result'),patch('cs2career.cs2.launch._archive'):
            self.assertEqual(raw,read_result(request_nonce=raw['request_nonce']))

    def test_official_result_ignores_unrelated_higher_scoring_argument(self):
        from cs2career.league.season import Season
        _,_,raw=self.training_fixture()
        session={'nonce':raw['request_nonce']}
        season=Season.__new__(Season)
        season._require_yours=lambda _: ({},{'cs2_session':session})
        old=dict(raw,request_nonce='old',ct_score=30,t_score=28)
        with patch('cs2career.league.season.read_result',return_value=raw) as read, \
             patch('cs2career.league.season.result_usable',return_value='validation sentinel') as validate:
            with self.assertRaisesRegex(ValueError,'validation sentinel'):
                season.commit_cs2_map('test',old)
            read.assert_called_once_with(request_nonce=raw['request_nonce'])
            validate.assert_called_once_with(raw,session)
