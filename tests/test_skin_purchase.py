import unittest

from cs2career.career.career import Career
from cs2career.career import skins


class SkinPurchaseTests(unittest.TestCase):
    def test_every_catalog_skin_can_be_bought_with_exact_personal_funds(self):
        career = Career()
        career.save = lambda: None
        skins.ensure_economy(career)
        for row in skins.catalog()['skins']:
            with self.subTest(skin=row['id']):
                price = skins.quote_of(career, row['id'])
                career.money = price
                count = len(career.inventory)
                career.buy_skin(row['id'])
                self.assertEqual(0, career.money)
                self.assertEqual(count + 1, len(career.inventory))
                self.assertEqual(row['id'], career.inventory[-1]['skin_id'])

    def test_one_short_does_not_spend_or_add_item_and_can_retry(self):
        career = Career()
        career.save = lambda: None
        skins.ensure_economy(career)
        sid = 'knife-butterfly-slaughter'
        career.skin_quotes[sid] = 26451
        career.money = 26000
        before = len(career.inventory)
        career.buy_skin(sid)
        self.assertEqual(26000, career.money)
        self.assertEqual(before, len(career.inventory))
        career.money = 26451
        career.buy_skin(sid)
        self.assertEqual(0, career.money)
        self.assertEqual(before + 1, len(career.inventory))
