from copy import deepcopy
import random
import unittest
from unittest.mock import patch

import test_personal_transfers as fixture
from cs2career.career import club_recruitment as recruitment, transfers


class ClubRecruitmentTests(unittest.TestCase):
    setUp = fixture.PersonalTransferTests.setUp

    def prepare(self):
        self.c.personal_transfers['player_only'] = True
        self.s.history = []
        self.s.date = '2026-07-08'
        self.mine = self.s.teams[0]
        self.mine['money'] = 3000000
        self.c.free = [dict(player_id='free.1', name='Free One', role='awp', ability=76, age=22)]

    def proposal(self, index=0):
        return recruitment.context(self.c, self.s)['candidates'][index]

    def discuss(self, *, approved=True):
        quote = self.proposal()
        with patch('cs2career.career.player_transfers.draw', return_value=1 if approved else 10000):
            return recruitment.discuss(self.c, self.s, quote['replace_id'], quote['quote_id'])

    def records(self, kills=25, maps=6):
        target = self.mine['players'][1]
        line = dict(player_id=target['player_id'], name=target['name'], k=kills, d=12, a=5, damage=kills*90, kast_rounds=19)
        self.s.events = [dict(id='fixture', dates=[self.s.date], status='done', matches=[dict(
            id='match', date=self.s.date, played=True, team_a=self.mine['name'], team_b='Team1',
            maps=[dict(winner=self.mine['name'], rounds=24, players={self.mine['name']:[line]}) for _ in range(maps)])])]

    def test_tenure_strength_and_teammate_quality_affect_probability(self):
        self.prepare()
        self.s.date='2026-01-08'
        early=self.proposal()['chance']
        self.s.date='2027-01-08'
        veteran=self.proposal()['chance']
        self.assertGreater(veteran, early)
        self.mine['players'][0]['ability']=95
        influential=self.proposal()['chance']
        self.assertGreater(influential,veteran)
        self.mine['players'][1]['ability']=96
        protected=self.proposal()['chance']
        self.assertLess(protected,influential)
        self.assertGreaterEqual(protected,.05)
        self.assertLessEqual(influential,.90)

    def test_recent_carry_is_protected_and_small_sample_has_less_weight(self):
        self.prepare()
        no_data=self.proposal()
        self.assertIsNone(no_data['recent_rating'])
        self.assertEqual(0,no_data['form_modifier'])
        self.records(maps=1)
        one=self.proposal()
        self.records(maps=8)
        carry=self.proposal()
        self.assertLess(carry['chance'],one['chance'])
        self.assertLess(one['chance'],no_data['chance'])
        self.assertGreater(carry['recent_rating'],1.2)
        self.records(kills=6,maps=8)
        weak=self.proposal()
        self.assertGreater(weak['chance'],no_data['chance'])

    def test_recent_window_limit_missing_measurements_and_historical_identity(self):
        self.prepare()
        self.records(maps=25)
        self.assertEqual(20,self.proposal()['recent_maps'])
        event=self.s.events[0]
        self.s.history=[deepcopy(event)]
        self.assertEqual(20,self.proposal()['recent_maps'])  # no double archive count
        event['matches'][0]['date']='2025-12-31'
        self.assertEqual(0,self.proposal()['recent_maps'])
        event['matches'][0]['date']=self.s.date
        event['matches'][0]['maps'][0]['players'][self.mine['name']][0].pop('damage')
        self.assertEqual(0,self.proposal()['recent_maps'])  # shared fixture row, all incomplete

    def test_reads_do_not_mutate_or_consume_randomness(self):
        self.prepare()
        before=deepcopy((self.c.to_json(),self.s.teams))
        rng=random.getstate()
        self.assertEqual(self.proposal(),self.proposal())
        self.assertEqual(before,(self.c.to_json(),self.s.teams))
        self.assertEqual(rng,random.getstate())

    def test_declined_discussion_is_saved_has_global_cooldown_and_no_money_cost(self):
        self.prepare()
        money=(self.c.money,self.mine['money'])
        result=self.discuss(approved=False)
        self.assertFalse(result['recruitment']['approved'])
        self.assertEqual(money,(self.c.money,self.mine['money']))
        self.assertIsNone(recruitment.permission(self.c,self.s))
        self.assertFalse(recruitment.context(self.c,self.s)['available'])
        other=self.proposal(1)
        with self.assertRaises(ValueError): recruitment.discuss(self.c,self.s,other['replace_id'],other['quote_id'])
        self.s.date='2026-07-22'
        self.assertTrue(recruitment.context(self.c,self.s)['available'])

    def test_approval_is_one_outgoing_player_and_one_successful_signing(self):
        self.prepare()
        self.discuss()
        grant=recruitment.permission(self.c,self.s)
        with self.assertRaises(ValueError):
            transfers.guaranteed(self.c,self.s,'free.1','',self.mine['players'][2]['player_id'])
        money=self.c.money
        transfers.guaranteed(self.c,self.s,'free.1','',grant['replace_id'])
        self.assertEqual(money,self.c.money)
        self.assertLess(self.mine['money'],3000000)
        self.assertEqual(5,len(self.mine['players']))
        self.assertIsNone(recruitment.permission(self.c,self.s))
        self.assertTrue(self.c.personal_transfers['player_only'])

    def test_failed_free_agent_talk_retains_grant_and_success_consumes_it(self):
        self.prepare()
        self.discuss()
        grant=recruitment.permission(self.c,self.s)
        with patch('cs2career.career.career.random.random',return_value=1):
            self.c.buy(self.s,'Free One',grant['replace_id'],'free.1')
        self.assertEqual(grant,recruitment.permission(self.c,self.s))
        with patch('cs2career.career.career.random.random',return_value=0):
            self.c.buy(self.s,'Free One',grant['replace_id'],'free.1')
        self.assertIsNone(recruitment.permission(self.c,self.s))

    def test_grant_invalid_after_roster_move_or_leaving_and_returning(self):
        self.prepare()
        self.discuss()
        original=deepcopy(self.mine['players'])
        self.mine['players'][2]['player_id']='changed'
        self.assertIsNone(recruitment.permission(self.c,self.s))
        self.mine['players']=original
        self.c.personal_transfers['moves']=[dict(date='2026-07-09',new_team_id='t1'),dict(date='2026-08-01',new_team_id='t0')]
        self.s.date='2026-08-01'
        self.assertIsNone(recruitment.permission(self.c,self.s))
        self.assertEqual(0,recruitment.context(self.c,self.s)['tenure_days'])

    def test_stale_quote_self_replacement_live_matches_and_owners_rejected(self):
        self.prepare()
        quote=self.proposal()
        with self.assertRaises(ValueError): recruitment.discuss(self.c,self.s,self.mine['players'][0]['player_id'],quote['quote_id'])
        self.mine['players'][1]['ability']+=5
        with self.assertRaises(ValueError): recruitment.discuss(self.c,self.s,quote['replace_id'],quote['quote_id'])
        self.s.events=[dict(id='live',status='live',field=[self.mine['name']],matches=[])]
        self.assertFalse(recruitment.context(self.c,self.s)['available'])
        self.s.events=[]
        self.c.personal_transfers['player_only']=False
        with self.assertRaises(ValueError): recruitment.discuss(self.c,self.s,quote['replace_id'],quote['quote_id'])
        recruitment.authorize(self.c,self.s,'')

    def test_actual_discussion_roll_is_stable_across_loading_the_same_state(self):
        self.prepare()
        original=deepcopy(self.c)
        rng=random.getstate()
        q=self.proposal()
        one=recruitment.discuss(self.c,self.s,q['replace_id'],q['quote_id'])
        two=recruitment.discuss(original,self.s,q['replace_id'],q['quote_id'])
        self.assertEqual(one,two)
        self.assertEqual(rng,random.getstate())


if __name__=='__main__': unittest.main()
