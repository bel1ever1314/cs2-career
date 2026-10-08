"""Market and boosts are pure on reads, independent of gameplay RNG and durable."""
from copy import deepcopy
from datetime import date,timedelta
import random
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from cs2career.career.career import Career, sponsor_month, transfer_fee
from cs2career.career import skins, skin_market as market, match_supplies as supplies
from cs2career.career.transfers import buyout_price
from cs2career.career.market_balance import potential_stars
from cs2career.world.ability import playing_stats, playing_ability


class MarketTests(unittest.TestCase):
    def setUp(self):
        self.c=Career(); self.c.save=Mock(); self.c.money=1000000
        self.c.player_name='test'; self.c.team_id='test-club'
        self.day='2026-01-08'

    def buy(self,quantity=3,sid='ak-redline',wear='ft'):
        return market.command(self.c,self.day,'buy',dict(id=sid,wear=wear,quantity=quantity,
                              expected_total=market.quote(self.c,sid,wear)*quantity))

    def test_reads_pure_and_no_fabricated_history(self):
        before=deepcopy(self.c.incident_state); seed=random.getstate()
        for _ in range(2):
            page=market.page(self.c,self.day)
            item=market.detail(self.c,self.day,'ak-redline','ft')
            market.custody(self.c,self.day); market.merchant(self.c,self.day)
        self.assertTrue(page['rows']); self.assertEqual([],item['history'])
        self.assertIsNone(item['change_30']); self.assertEqual(before,self.c.incident_state)
        self.assertEqual(seed,random.getstate())

    def test_custody_partial_extract_fixed_items_and_rng(self):
        seed=random.getstate(); self.buy()
        self.assertEqual([],self.c.inventory)
        lot=market.data(self.c)['custody'][0]; original=deepcopy(lot['items'])
        market.command(self.c,self.day,'withdraw',dict(lot_id=lot['id'],quantity=2))
        self.assertEqual(original[:2],self.c.inventory)
        self.assertEqual(original[2:],lot['items'])
        self.assertEqual(seed,random.getstate())
        price=market.proceeds(self.c,market.quote(self.c,'ak-redline','ft'))
        market.command(self.c,self.day,'sell',dict(lot_id=lot['id'],quantity=1,expected_total=price))
        self.assertFalse(market.data(self.c)['custody'])
        with self.assertRaises(ValueError): market.command(self.c,self.day,'withdraw',dict(lot_id=lot['id'],quantity=1))

    def test_invalid_quantities_quotes_and_wear(self):
        for count in (True,0,-1,101,1.2):
            with self.assertRaises(ValueError): self.buy(count)
        with self.assertRaises(ValueError): market.command(self.c,self.day,'buy',dict(id='ak-redline',wear='ft',quantity=1,expected_total=1))
        with self.assertRaises(ValueError): market.quote(self.c,'ak-redline','invalid')
        self.assertEqual(1000000,self.c.money)

    def test_withdrawn_item_keeps_wear_price_and_bargaining_fee(self):
        self.buy(1,wear='bs')
        lot=market.data(self.c)['custody'][0]
        price=market.quote(self.c,'ak-redline','bs')
        market.command(self.c,self.day,'withdraw',dict(lot_id=lot['id'],quantity=1))
        item=self.c.inventory[0]
        self.assertEqual(price,skins._decorate_item(self.c,item)['spot'])
        for _ in range(3): market.command(self.c,self.day,'skill',dict(skill='bargaining'))
        before=self.c.money
        self.c.sell_skin(item['id'],sync=False)
        self.assertEqual(market.proceeds(self.c,price),self.c.money-before)
        self.assertFalse(self.c.inventory)

    def test_price_filters_reject_nan_and_inverted_ranges(self):
        for query in ({'min_price':'nan'},{'max_price':'inf'},{'min_price':50,'max_price':10}):
            with self.assertRaises(ValueError): market.page(self.c,self.day,query)

    def test_six_month_budget_multiple_seeds_without_trading_or_stat_edits(self):
        from cs2career.career.economy import month_burn
        for seed in (12,87,430,617,909):
            roll=random.Random(seed)
            starter=[dict(ability=roll.uniform(63,67)) for _ in range(5)]
            original=deepcopy(starter)
            costs=month_burn(starter,100)['total']
            fee=buyout_price(dict(ability=75),free=True)[0]
            funds=90000
            months=0
            while funds-costs<fee and months<12:
                funds+=sponsor_month(100)-costs
                months+=1
            self.assertLessEqual(months,7,(seed,costs,months))
            self.assertGreaterEqual(months,4)
            self.assertGreater(75-max(p['ability'] for p in starter),8)
            self.assertEqual(original,starter)

    def test_daily_history_bounded_and_duplicate_day_noop(self):
        seed=random.getstate()
        for index in range(95):
            day=(date.fromisoformat(self.day)+timedelta(days=index)).isoformat()
            market.tick(self.c,day)
        self.assertEqual(90,len(market.data(self.c)['history']))
        before=deepcopy(market.data(self.c)); quotes=deepcopy(self.c.skin_quotes)
        market.tick(self.c,day)
        self.assertEqual(before,market.data(self.c)); self.assertEqual(quotes,self.c.skin_quotes)
        self.assertEqual(seed,random.getstate())
        values=market.page(self.c,day,dict(wear='ft',slot='ak47',sort='change_7',order='desc'))['rows']
        self.assertEqual(sorted([r['change_7'] for r in values],reverse=True),[r['change_7'] for r in values])

    def test_skills_and_rumor_cannot_reroll(self):
        market.command(self.c,self.day,'rumor',{})
        before=self.c.money
        self.assertTrue(market.command(self.c,self.day,'rumor',{})['replayed'])
        self.assertEqual(before,self.c.money)
        public=market.merchant(self.c,self.day)
        self.assertNotIn('pressure',public['rumors'][0])
        for _ in range(3): market.command(self.c,self.day,'skill',dict(skill='bargaining'))
        self.assertEqual(.07,market.fee(self.c))
        with self.assertRaises(ValueError): market.command(self.c,self.day,'skill',dict(skill='bargaining'))

    def test_finance_and_potential_defaults(self):
        self.assertEqual(55000,sponsor_month(100))
        self.assertEqual(175000,sponsor_month(1))
        p=dict(ability=75)
        self.assertEqual(round(transfer_fee(75)*1.15),buyout_price(p,free=True)[0])
        self.assertEqual(transfer_fee(75)*3,buyout_price(p)[0])
        self.assertEqual([None,1,2,3,4,5],[potential_stars(v) for v in (None,64,65,75,80,90)])

    def test_catalog_images_wear_and_exact_mapping(self):
        from cs2career.services.resources import cached_skin_art
        from cs2career.skin_art import manifest
        catalog=skins.catalog()['skins']
        self.assertGreaterEqual(len(catalog),150)
        for row in catalog:
            self.assertTrue(cached_skin_art(row['id'],manifest()),row['id'])
            self.assertTrue(market.variants(row),row['id'])
        self.assertEqual(16,skins.skin_map()['m4-temukau']['def'])


class SupplyTests(unittest.TestCase):
    def setUp(self):
        self.c=Career(); self.c.save=Mock(); self.c.exists=True; self.c.money=50000
        self.c.player_name='human'; self.c.team_id='own'; self.c.personal_transfers={}
        players=[dict(player_id=str(i),name='human' if i==0 else 'bot'+str(i),role='rifle',ability=75,
            stats={axis:75. for axis in supplies.AXES}) for i in range(5)]
        self.team=dict(id='own',name='Own',money=100000,players=players,command=75)
        self.match=dict(id='match',team_a='Own',team_b='Away',maps=[],played=False)
        self.ev=dict(id='event',name='Event',matches=[self.match])
        self.s=SimpleNamespace(date='2026-01-08',year=2026,teams=[self.team],events=[self.ev],find_match=lambda _: (self.ev,self.match))
        self.state=SimpleNamespace(career=self.c,season=self.s)
        self.key=supplies.series_key(self.s,self.match)

    def command(self,action,**body):
        return supplies.command(self.state,action,dict(revision=0,**body))

    def prepared(self,grade='normal'):
        self.command('buy',axis='firepower',grade=grade,payer='club')
        item=supplies.data(self.c)['stock'][-1]
        self.command('prepare',player_id='1',target=self.key,item_id=item['id'])
        return supplies.prepare(self.c,self.match,self.key,self.s.date)

    def test_preview_failure_does_not_consume_and_repeat_start_once(self):
        effects=self.prepared(); before=deepcopy(self.team)
        boosted=supplies.teams_with_effects([self.team],effects)[0]
        self.assertEqual(78,playing_stats(boosted['players'][1])['firepower'])
        self.assertGreater(playing_ability(boosted['players'][1]),playing_ability(self.team['players'][1]))
        self.assertEqual(before,self.team); self.assertEqual(1,len(supplies.data(self.c)['stock']))
        supplies.activate(self.c,self.match,self.key,self.s.date,effects)
        supplies.activate(self.c,self.match,self.key,self.s.date,effects)
        self.assertEqual(0,len(supplies.data(self.c)['stock']))
        self.assertEqual('2026-01-11',supplies.data(self.c)['cooldowns']['1'])
        supplies.finish_map(self.c,self.match,self.key,0)
        self.assertFalse(supplies.data(self.c)['active'])
        self.assertEqual(effects,supplies.prepare(self.c,self.match,self.key,self.s.date))

    def test_strong_survives_maps_not_series_and_never_stacks(self):
        effects=self.prepared('strong')
        with self.assertRaises(ValueError): self.command('prepare',player_id='1',target=self.key,item_id='supply.1')
        supplies.activate(self.c,self.match,self.key,self.s.date,effects)
        supplies.finish_map(self.c,self.match,self.key,0)
        later=supplies.prepare(self.c,self.match,self.key,self.s.date,1)
        self.assertEqual(5,later['1']['bonus'])
        self.assertEqual('2026-01-15',supplies.data(self.c)['cooldowns']['1'])
        supplies.finish_series(self.c,self.key)
        self.assertFalse(supplies.prepare(self.c,self.match,self.key,self.s.date,2))

    def test_cancel_refunds_reservation_not_purchase_and_wallet_permissions(self):
        self.prepared(); self.command('cancel',player_id='1')
        self.assertEqual(1,len(supplies.data(self.c)['stock']))
        self.assertEqual(98500,self.team['money']); self.assertEqual(50000,self.c.money)
        self.command('buy',axis='sniping',grade='strong',payer='personal')
        with self.assertRaises(ValueError): self.command('prepare',player_id='1',target=self.key,item_id='supply.2')
        self.c.personal_transfers['player_only']=True
        with self.assertRaises(ValueError): self.command('buy',axis='sniping',grade='normal',payer='club')

    def test_uncertain_launch_cannot_cancel_reserved_supply(self):
        self.prepared()
        self.match['cs2_session']={'nonce':'pending','launch_state':'uncertain'}
        with self.assertRaisesRegex(ValueError,'启动结果待确认'):
            self.command('cancel',player_id='1')
        self.assertIn('1',supplies.data(self.c)['prepared'])
        self.assertEqual(1,len(supplies.data(self.c)['stock']))

    def test_departed_player_does_not_consume_boost_or_buff_opponent(self):
        self.prepared()
        departed=self.team['players'].pop(1)
        effects=supplies.prepare(self.c,self.match,self.key,self.s.date,teams=[self.team])
        self.assertFalse(effects)
        before=deepcopy(departed)
        self.assertEqual(before,supplies.teams_with_effects([dict(players=[departed])],effects)[0]['players'][0])
        supplies.activate(self.c,self.match,self.key,self.s.date,effects)
        self.assertEqual(1,len(supplies.data(self.c)['stock']))


if __name__=='__main__': unittest.main()
