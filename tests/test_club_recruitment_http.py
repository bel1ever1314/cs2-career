from copy import deepcopy
import unittest
from unittest.mock import patch

import test_recovery_http as fixture
from cs2career.application import ApplicationState
from cs2career.career import club_recruitment as recruitment, transfers
from cs2career.services import matches, business
from cs2career.storage import transaction as tx


class RecruitmentHttpTests(unittest.TestCase):
    setUp = fixture.RecoveryHttpTests.setUp
    career_fixture = fixture.RecoveryHttpTests.career_fixture
    serving = fixture.RecoveryHttpTests.serving
    request = fixture.RecoveryHttpTests.request

    def prepare(self):
        c,s,_=self.career_fixture()
        s.events=[]
        c.personal_transfers['player_only']=True
        c.my_team(s.teams)['money']=3000000
        self.state.persist()
        return c,s

    def discuss_body(self):
        row=recruitment.context(self.state.career,self.state.season)['candidates'][0]
        return dict(replace_id=row['replace_id'],quote_id=row['quote_id'],revision=matches._revision(self.state))

    def test_grant_and_purchase_survive_restart_and_duplicate_requests(self):
        c,s=self.prepare()
        before=deepcopy(c.to_json())
        view=business.business_context(self.state)['transfers']
        self.assertTrue(view['club_browsable'])
        self.assertFalse(view['club_allowed'])
        self.assertEqual(before,c.to_json())
        body=self.discuss_body()
        with self.serving(), patch('cs2career.career.player_transfers.draw', return_value=1):
            code,out=self.request('/api/3d/transfers/discuss',body,rid='recruitment-ask-001')
            self.assertEqual(200,code,out)
            saved=deepcopy(c.personal_transfers)
            code,replay=self.request('/api/3d/transfers/discuss',body,rid='recruitment-ask-001')
            self.assertTrue(replay['replayed'],replay)
            self.assertEqual(saved,c.personal_transfers)
        self.state=ApplicationState()
        c,s=self.state.career,self.state.season
        self.assertEqual(saved,c.personal_transfers)
        grant=recruitment.permission(c,s)
        self.assertIsNotNone(grant)
        row=min((r for r in transfers.candidates(c,s) if not r['seller_id'] and not r['blocked']),key=lambda r:r['guaranteed_fee'])
        buy=dict(player_id=row['player_id'],seller_id='',replace_id=grant['replace_id'],
                 fee=row['guaranteed_fee'],mode='guaranteed',revision=matches._revision(self.state))
        money=c.my_team(s.teams)['money']; pocket=c.money
        with self.serving():
            code,out=self.request('/api/3d/transfers/buy',buy,rid='recruitment-buy-001')
            self.assertEqual(200,code,out)
            code,replay=self.request('/api/3d/transfers/buy',buy,rid='recruitment-buy-001')
            self.assertTrue(replay['replayed'],replay)
        loaded=ApplicationState()
        self.assertIsNone(recruitment.permission(loaded.career,loaded.season))
        self.assertEqual(money-row['guaranteed_fee'],loaded.career.my_team(loaded.season.teams)['money'])
        self.assertEqual(pocket,loaded.career.money)
        self.assertTrue(loaded.career.personal_transfers['player_only'])

    def test_interrupted_committed_discussion_recovers_grant_and_receipt(self):
        self.prepare()
        body=self.discuss_body()
        def fault(point):
            if point == 'replaced:career.json': raise OSError('fixture interrupted commit')
        with self.serving(), patch('cs2career.career.player_transfers.draw', return_value=1), patch.object(tx,'_checkpoint',fault):
            code,out=self.request('/api/3d/transfers/discuss',body,rid='recruitment-crash-001')
            self.assertEqual(503,code,out)
            self.assertEqual('storage_recovery_required',out['error_code'])
        self.state=ApplicationState()
        self.assertIsNotNone(recruitment.permission(self.state.career,self.state.season))
        with self.serving():
            code,replay=self.request('/api/3d/transfers/discuss',body,rid='recruitment-crash-001')
            self.assertEqual(200,code,replay)
            self.assertTrue(replay['replayed'])

    def test_interrupted_purchase_recovers_roster_money_and_consumed_grant(self):
        c,s=self.prepare()
        with self.state.operation(), patch('cs2career.career.player_transfers.draw', return_value=1):
            business.transfer_command(self.state,'discuss',self.discuss_body())
            self.state.persist()
        grant=recruitment.permission(c,s)
        row=min((r for r in transfers.candidates(c,s) if not r['seller_id'] and not r['blocked']),key=lambda r:r['guaranteed_fee'])
        body=dict(player_id=row['player_id'],seller_id='',replace_id=grant['replace_id'],
                  fee=row['guaranteed_fee'],mode='guaranteed',revision=matches._revision(self.state))
        money=c.my_team(s.teams)['money']
        def fault(point):
            if point == 'replaced:season.json': raise OSError('fixture interrupted commit')
        with self.serving(), patch.object(tx,'_checkpoint',fault):
            code,out=self.request('/api/3d/transfers/buy',body,rid='recruitment-buy-crash-001')
            self.assertEqual(503,code,out)
        self.state=ApplicationState()
        c,s=self.state.career,self.state.season
        self.assertIsNone(recruitment.permission(c,s))
        self.assertEqual(money-row['guaranteed_fee'],c.my_team(s.teams)['money'])
        self.assertIn(row['player_id'],[transfers.identity(p) for p in c.my_team(s.teams)['players']])
        with self.serving():
            code,out=self.request('/api/3d/transfers/buy',body,rid='recruitment-buy-crash-001')
            self.assertEqual(200,code,out)
            self.assertTrue(out['replayed'])


if __name__=='__main__': unittest.main()
