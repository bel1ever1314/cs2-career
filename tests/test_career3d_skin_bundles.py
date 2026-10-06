from application_double import ApplicationDouble
"""Pure in-memory purchases with actual pinned recipes; no service/save/game."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs2career.career import skins
from cs2career.career.skin_crafts import import_pack
from cs2career.paths import data_file
from tools.career3d_skin_bundles import STORE_KEY, bundle_context, buy_bundle


class MemoryCareer:
    def __init__(self):
        self.money = 1_000_000
        self.inventory = []
        self.skin_seq = 0
        self.skin_quotes = {}
        self.incident_state = {'career3d_service': {'revision': 4}}
        self.log = []
        self.cashflow = []
        self.equipped_ct, self.equipped_t = {}, {}

    def _record_cashflow(self, date, scope, category, label, amount, balance):
        self.cashflow.append(dict(date=date, scope=scope, category=category,
                                 label=label, amount=amount, balance=balance))

    def save(self):
        raise AssertionError('Pure bundle commands must leave persistence to the service')


class SkinBundlesTests(unittest.TestCase):
    def setUp(self):
        self.core = json.loads(data_file('skins.json').read_text(encoding='utf-8'))
        self.catalog_patch = patch.object(skins, 'catalog', return_value=deepcopy(self.core))
        self.catalog_patch.start()
        self.art_patch = patch('tools.career3d_resources.cached_skin_art', return_value='')
        self.art_patch.start()
        skins.pro_bundle.cache_clear()
        self.career = MemoryCareer()
        self.state = ApplicationDouble(career=self.career, season=SimpleNamespace(date='2026-10-02'))
        self.addCleanup(self.catalog_patch.stop)
        self.addCleanup(self.art_patch.stop)
        self.addCleanup(skins.pro_bundle.cache_clear)

    def request(self, pack='pro-donk-public', request='bundle-request-0001', revision=4, **extra):
        return dict(id=pack, request_id=request, revision=revision, **extra)

    def snapshot(self):
        return deepcopy(vars(self.career))

    def test_four_original_templates_have_item_prices_and_read_only_context(self):
        before = self.snapshot()
        rows = bundle_context(self.state)
        self.assertEqual(['donk', 'zywoo', 'monesy', 'niko'], [row['player'] for row in rows])
        self.assertEqual([8, 8, 8, 9], [row['count'] for row in rows])
        for row in rows:
            self.assertEqual(sum(item['price'] for item in row['items']), row['price'])
            self.assertGreater(row['price'], 10_000)
            self.assertEqual('game_coin', row['currency'])
            self.assertTrue(row['buy_allowed'])
            self.assertFalse(row['owned'])
            self.assertTrue(row['bound'])
            for item in row['items']:
                self.assertTrue(item['name'] and item['slot'])
                self.assertEqual('', item['art_path'])
                self.assertGreater(item['price'], 1)
        self.assertEqual(before, self.snapshot())

    def test_single_purchase_uses_quotes_and_keeps_original_provenance(self):
        self.career.skin_quotes['ak-redline'] = 9999
        preview = bundle_context(self.state)[0]
        self.assertEqual(9999, next(row['price'] for row in preview['items'] if row['skin_id'] == 'ak-redline'))
        money = self.career.money
        receipt = buy_bundle(self.state, self.request(price=1, items=[{'skin_id': 'invented'}]))
        self.assertEqual(preview['price'], receipt['charged'])
        self.assertEqual(money - preview['price'], self.career.money)
        self.assertEqual(8, len(self.career.inventory))
        self.assertEqual(8, self.career.skin_seq)
        self.assertEqual(-preview['price'], self.career.cashflow[0]['amount'])
        self.assertEqual('pocket', self.career.cashflow[0]['scope'])
        self.assertEqual(1, len(self.career.log))
        self.assertIn('pro-donk-public', self.career.incident_state[STORE_KEY]['purchases'])
        for row in self.career.inventory:
            self.assertTrue(row['bound'])
            self.assertEqual('pro-donk-public', row['source_pack_id'])
            self.assertEqual('finish_only', row['source_precision'])
            self.assertEqual({'wear': None, 'seed': None}, row['source_parameters'])
            self.assertEqual(1, row['seed'])
            self.assertTrue(row['hash'])

    def test_same_request_and_fresh_request_do_not_charge_or_add_again(self):
        buy_bundle(self.state, self.request())
        self.career.incident_state['career3d_service']['revision'] = 5
        before = self.snapshot()
        for body in (self.request(), self.request(request='bundle-request-0002', revision=5)):
            receipt = buy_bundle(self.state, body)
            self.assertTrue(receipt['replayed'])
            self.assertEqual(0, receipt['charged'])
            self.assertEqual(0, receipt['added'])
            self.assertEqual(before, self.snapshot())

    def test_receipt_survives_reload_and_missing_inventory_is_not_recreated(self):
        buy_bundle(self.state, self.request())
        restored = MemoryCareer()
        restored.__dict__.update(deepcopy(self.career.__dict__))
        restored.inventory.pop()
        self.state.career = restored
        before = deepcopy(restored.__dict__)
        result = buy_bundle(self.state, self.request())
        self.assertTrue(result['replayed'] and result['owned'])
        self.assertFalse(result['imported'])
        self.assertEqual(0, result['charged'])
        self.assertEqual(before, restored.__dict__)

    def test_old_free_imports_are_retained_without_charge_or_top_up(self):
        data = skins.pro_bundle()
        imported = import_pack([], 1, data['packs'][0], data['skins'], skins.sticker_catalog())
        for inventory in (imported['inventory'], imported['inventory'][:1]):
            self.career.inventory = deepcopy(inventory)
            self.career.skin_seq = 8
            before = self.snapshot()
            preview = bundle_context(self.state)[0]
            self.assertTrue(preview['owned'])
            self.assertFalse(preview['buy_allowed'])
            response = buy_bundle(self.state, self.request())
            self.assertTrue(response['replayed'])
            self.assertEqual(0, response['charged'])
            self.assertEqual(before, self.snapshot())

    def test_invalid_revision_funds_identity_and_token_are_atomic(self):
        cases = [self.request(revision=3), self.request(revision=True), self.request(pack='not-a-pack'),
                 self.request(request='short'), self.request(request=123)]
        for body in cases:
            before = self.snapshot()
            with self.subTest(body=body), self.assertRaises(ValueError):
                buy_bundle(self.state, body)
            self.assertEqual(before, self.snapshot())
        self.career.money = 0
        before = self.snapshot()
        with self.assertRaises(ValueError): buy_bundle(self.state, self.request())
        self.assertEqual(before, self.snapshot())

    def test_request_id_cannot_be_reused_for_another_pack(self):
        buy_bundle(self.state, self.request())
        before = self.snapshot()
        with self.assertRaises(ValueError):
            buy_bundle(self.state, self.request(pack='pro-zywoo-public'))
        self.assertEqual(before, self.snapshot())

    def test_server_owned_data_price_override_and_invalid_prices(self):
        configured = {'pro-donk-public': 60_000}
        self.assertEqual(60_000, bundle_context(self.state, configured)[0]['price'])
        self.assertEqual(60_000, buy_bundle(self.state, self.request(), configured)['charged'])
        for invalid in (0, -1, True, 1.2, '1000'):
            with self.subTest(price=invalid), self.assertRaises(ValueError):
                bundle_context(self.state, {'pro-donk-public': invalid})

    def test_all_four_bundles_use_distinct_inventory_ids_and_export(self):
        for index, pack in enumerate(skins.pro_bundle()['packs']):
            buy_bundle(self.state, self.request(pack=pack['id'], request='purchase-request-%d' % index))
        self.assertEqual(33, len(self.career.inventory))
        self.assertEqual(33, len({row['id'] for row in self.career.inventory}))
        self.assertEqual(4, len(self.career.cashflow))
        self.assertTrue(all(row['owned'] and row['imported'] and not row['buy_allowed']
                            for row in bundle_context(self.state)))
        ak = next(row for row in self.career.inventory if row['slot'] == 'ak47')
        exported = skins.equipped_v5_body(self.career.inventory, {}, {'ak47': ak['id']})
        self.assertEqual(ak['paint'], exported['tWeapons']['7']['paint'])
        self.assertEqual(ak['seed'], exported['tWeapons']['7']['seed'])


if __name__ == '__main__':
    unittest.main()
