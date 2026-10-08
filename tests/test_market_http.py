"""New commands cross the real authenticated HTTP/save/receipt boundary."""
from copy import deepcopy
import unittest
from cs2career.application import ApplicationState
from cs2career.career import skin_market as market
from cs2career.services import matches
import test_recovery_http as fixture


class MarketHttpTests(unittest.TestCase):
    setUp=fixture.RecoveryHttpTests.setUp
    career_fixture=fixture.RecoveryHttpTests.career_fixture
    serving=fixture.RecoveryHttpTests.serving
    request=fixture.RecoveryHttpTests.request

    def test_typed_rumor_receipts_and_slots_survive_restart(self):
        c,s,_=self.career_fixture()
        c.money=100000
        c.inventory=[{'skin_id':'ak-redline','id':'owned.1'}]
        self.state.persist()
        with self.serving():
            for kind in ('bullish','bearish'):
                body=dict(kind=kind,revision=matches._revision(self.state))
                code,result=self.request('/api/3d/skins/market-rumor',body,rid='rumor-'+kind+'-0001')
                self.assertEqual(200,code,result)
                balance=c.money
                code,replay=self.request('/api/3d/skins/market-rumor',body,rid='rumor-'+kind+'-0001')
                self.assertEqual(200,code,replay)
                self.assertTrue(replay['replayed'])
                self.assertEqual(balance,c.money)
            notes=deepcopy(market.data(c)['rumors'])
        self.state=ApplicationState()
        with self.serving():
            code,result=self.request('/api/3d/skins/market-rumor',body,rid='rumor-bearish-0001')
            self.assertEqual(200,code,result)
            self.assertTrue(result['replayed'])
            code,page=self.request('/api/3d/market?view=merchant')
            self.assertEqual(200,code,page)
            self.assertTrue(all(r['purchased'] for r in page['market']['offers']))
        self.assertEqual(balance,self.state.career.money)
        self.assertEqual(notes,market.data(self.state.career)['rumors'])

    def test_buy_and_partial_withdraw_receipts_survive_restart(self):
        c,s,_=self.career_fixture()
        c.money=100000
        self.state.persist()
        price=market.quote(c,'ak-redline','bs')
        body=dict(id='ak-redline',wear='bs',quantity=4,expected_total=price*4,revision=matches._revision(self.state))
        with self.serving():
            code,result=self.request('/api/3d/skins/market-buy',body,rid='custody-buy-0001')
            self.assertEqual(200,code,result)
            money=c.money
            _,again=self.request('/api/3d/skins/market-buy',body,rid='custody-buy-0001')
            self.assertTrue(again['replayed'])
            self.assertEqual(money,c.money)
            self.assertFalse(c.inventory)
            lot=market.data(c)['custody'][0]
            item_snapshot=deepcopy(lot['items'])
            before=(self.root/'career.json').read_bytes()
            for view in ('market','custody','merchant'):
                code,result=self.request('/api/3d/market?view='+view)
                self.assertEqual(200,code,result)
            self.assertEqual(before,(self.root/'career.json').read_bytes())
            body=dict(lot_id=lot['id'],quantity=2,revision=matches._revision(self.state))
            code,result=self.request('/api/3d/skins/market-withdraw',body,rid='custody-withdraw-0001')
            self.assertEqual(200,code,result)
        self.state=ApplicationState()
        with self.serving():
            code,result=self.request('/api/3d/skins/market-withdraw',body,rid='custody-withdraw-0001')
            self.assertEqual(200,code,result)
            self.assertTrue(result['replayed'])
        self.assertEqual(item_snapshot[:2],self.state.career.inventory)
        self.assertEqual(item_snapshot[2:],market.data(self.state.career)['custody'][0]['items'])
        self.assertEqual(money,self.state.career.money)


if __name__=='__main__': unittest.main()
