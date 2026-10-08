"""Directional informant purchases cannot reroll, manufacture prices or use unowned stock."""
from copy import deepcopy
from datetime import date, timedelta
import random
import unittest
from unittest.mock import Mock

from cs2career.career.career import Career
from cs2career.career import skin_market as market


class RumorTypesTests(unittest.TestCase):
    def setUp(self):
        self.c = Career()
        self.c.save = Mock()
        self.c.money = 100000
        self.c.player_name = 'RumorFixture'
        self.c.team_id = 'own'
        self.day = '2026-01-08'

    def buy_item(self, sid='ak-redline'):
        market.command(self.c, self.day, 'buy', dict(id=sid, wear='ft', quantity=1,
                       expected_total=market.quote(self.c, sid, 'ft')))

    def purchase(self, kind):
        return market.command(self.c, self.day, 'rumor', {'kind': kind})

    def test_two_daily_slots_direction_and_repeat(self):
        self.buy_item()
        balance = self.c.money
        for kind, direction in (('bullish', 1), ('bearish', -1)):
            self.purchase(kind)
            self.assertTrue(self.purchase(kind)['replayed'])
            rumor = market.data(self.c)['rumors'][-1]
            self.assertEqual(direction, rumor['direction'])
            self.assertEqual(kind, rumor['kind'])
        self.assertEqual(balance - 2 * market.RUMOR_PRICE, self.c.money)
        self.assertEqual(2, len({r['id'] for r in market.data(self.c)['rumors']}))
        self.assertTrue(all(row['purchased'] for row in market.merchant(self.c, self.day)['offers']))

    def test_bearish_requires_current_custody_or_inventory(self):
        view = market.merchant(self.c, self.day)
        self.assertFalse(view['offers'][1]['available'])
        with self.assertRaises(ValueError): self.purchase('bearish')
        self.assertEqual(100000, self.c.money)
        self.buy_item()
        self.assertTrue(market.merchant(self.c, self.day)['offers'][1]['available'])
        self.purchase('bearish')
        self.assertEqual('ak-redline', market.data(self.c)['rumors'][-1]['skin_id'])
        lot = market.data(self.c)['custody'][0]
        market.command(self.c, self.day, 'withdraw', {'lot_id': lot['id'], 'quantity': 1})
        self.day = '2026-01-09'
        self.purchase('bearish')
        self.assertEqual('ak-redline', market.data(self.c)['rumors'][-1]['skin_id'])
        self.c.inventory.clear()
        self.day = '2026-01-10'
        self.assertFalse(market.merchant(self.c, self.day)['offers'][1]['available'])
        with self.assertRaises(ValueError): self.purchase('bearish')

    def test_bullish_works_without_holdings_and_is_deterministic(self):
        twin = deepcopy(self.c)
        self.purchase('bullish')
        market.command(twin, self.day, 'rumor', {'kind': 'bullish'})
        self.assertEqual(market.data(self.c)['rumors'], market.data(twin)['rumors'])
        self.assertFalse(self.c.inventory)
        self.assertFalse(market.data(self.c)['custody'])
        self.assertEqual(1, market.data(self.c)['rumors'][0]['direction'])

    def test_reads_purchase_and_forecast_leave_market_and_match_rng_alone(self):
        self.buy_item()
        market.tick(self.c, self.day)
        twin = deepcopy(self.c)
        state = random.getstate()
        self.purchase('bullish')
        self.purchase('bearish')
        before = deepcopy(market.data(self.c))
        for _ in range(3): market.merchant(self.c, self.day)
        self.assertEqual(before, market.data(self.c))
        for offset in range(1, 5):
            day = (date.fromisoformat(self.day) + timedelta(days=offset)).isoformat()
            market.tick(self.c, day)
            market.tick(twin, day)
            self.assertEqual(twin.skin_quotes, self.c.skin_quotes)
            self.assertEqual(market.data(twin)['history'], market.data(self.c)['history'])
        self.assertEqual(state, random.getstate())
        for r in market.merchant(self.c, day)['rumors']:
            self.assertNotIn('pressure', r)
            self.assertIsNotNone(r['outcome_pct'])

    def test_legacy_note_occupies_only_its_direction(self):
        market.data(self.c, create=True)['rumors'] = [dict(id=self.day, date=self.day,
            skin_id='ak-redline', direction=-1, pressure=-1, start_price=2400, expires='2026-01-11')]
        self.assertTrue(self.purchase('bearish')['replayed'])
        self.purchase('bullish')
        self.assertEqual(2, len(market.data(self.c)['rumors']))
        self.assertEqual(100000 - market.RUMOR_PRICE, self.c.money)

    def test_sold_stock_and_unknown_items_do_not_make_bearish_available(self):
        self.buy_item()
        lot = market.data(self.c)['custody'][0]
        market.command(self.c, self.day, 'sell', dict(lot_id=lot['id'], quantity=1,
            expected_total=market.proceeds(self.c, market.quote(self.c, 'ak-redline', 'ft'))))
        self.c.inventory.append({'skin_id': 'extension-not-in-market'})
        self.assertEqual([], market.held_skin_ids(self.c))
        with self.assertRaises(ValueError): self.purchase('bearish')
        for value in (None, '', 'up', [], 1, True):
            with self.assertRaises(ValueError): self.purchase(value)

    def test_bought_note_survives_holding_changes_and_old_client_default(self):
        self.buy_item()
        self.purchase('bearish')
        note = deepcopy(market.data(self.c)['rumors'][0])
        market.data(self.c)['custody'].clear()
        self.buy_item('awp-asiimov')
        self.assertTrue(self.purchase('bearish')['replayed'])
        self.assertEqual(note, market.data(self.c)['rumors'][0])
        market.command(self.c, self.day, 'rumor', {})
        self.assertEqual('bullish', market.data(self.c)['rumors'][-1]['kind'])


if __name__ == '__main__': unittest.main()
