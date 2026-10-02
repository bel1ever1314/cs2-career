"""Local optional adapter contracts, with memory-only careers and blocked I/O."""
from copy import deepcopy
import json
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs2career.career import skins
from cs2career.paths import data_file
from tools import career3d_skin_tools as adapter


CATALOG = {'stickers': [
    {'def': 100, 'name': 'A', 'name_en': 'A', 'weapon_defs': [7],
     'image': 'https://example.invalid/image.png', 'remote_account': 'catalog-private'},
    {'def': 101, 'name': 'B'}, {'def': 102, 'name': 'AWP only', 'weapon_defs': [9]}],
    'models': {'7': {'x_min': -0.4, 'x_max': 0.6456, 'y_min': -0.03, 'y_max': 0.22,
                     'schema_count': 4, 'rotation_min': -180, 'rotation_max': 180,
                     'model_variant': 'legacy'}}}


class MemoryCareer:
    def __init__(self):
        self.inventory = [
            {'id': 'inv.1', 'skin_id': 'ak-redline', 'slot': 'ak47',
             'stickers': [], 'hash': 'untrusted-cache', 'source': 'market',
             'spot': 3000, 'sell': 2700, 'provenance': {'nested': ['preserve']},
             'steam_id': '76561198000000000', 'remote_account': 'never-expose'},
            {'id': 'inv.2', 'skin_id': 'awp-asiimov', 'slot': 'awp', 'wear': .2,
             'seed': 12, 'stickers': [], 'hash': 'other-hash', 'sell': 7000}]
        self.money = 100_000
        self.skin_quotes = {'ak-redline': 3000}
        self.case_prices = {'case': {'price': 250}}
        self.skin_seq = 2
        self.incident_state = {'career3d_service': {'revision': 4}, 'other': 'preserve'}
        self.equipped_ct, self.equipped_t = {'awp': 'inv.2'}, {'ak47': 'inv.1'}
        self.real_skins, self.steam_id = True, '76561198000000000'
        self.log, self.cashflow = [], []

    def save(self):
        raise AssertionError('The optional adapter must not persist')


class SkinToolsTests(unittest.TestCase):
    def setUp(self):
        core = json.loads(data_file('skins.json').read_text(encoding='utf-8'))
        self.real_catalog_for_item = skins.sticker_catalog_for_item
        self.catalog_patch = patch.object(skins, 'catalog', return_value=deepcopy(core))
        self.catalog_patch.start()
        self.known_patch = patch.object(skins, 'sticker_catalog_for_item', return_value=deepcopy(CATALOG))
        self.known = self.known_patch.start()
        self.cfg = {'skin_tools_enabled': True, 'skins_inventory_mode': 'career',
                    'steam_exe': 'private-path', 'steam_id': '76561198000000000'}
        self.cfg_patch = patch.object(adapter, 'read_cs2_config', side_effect=lambda: deepcopy(self.cfg))
        self.cfg_patch.start()
        self.sync_patch = patch.object(skins, 'sync_live', side_effect=AssertionError('No game sync'))
        self.sync = self.sync_patch.start()
        self.net_patch = patch('urllib.request.urlopen', side_effect=AssertionError('No network'))
        self.net = self.net_patch.start()
        for active in (self.catalog_patch, self.known_patch, self.cfg_patch, self.sync_patch, self.net_patch):
            self.addCleanup(active.stop)
        self.career = MemoryCareer()
        self.state = SimpleNamespace(career=self.career,
                                     persist=lambda: self.fail('No service persistence'))

    def snapshot(self):
        return deepcopy(vars(self.career))

    def request(self, stickers=None):
        view = adapter.item_context(self.state, 'inv.1')
        return {'schema_version': 1, 'id': 'inv.1', 'expected_hash': view['expected_hash'],
                'revision': view['revision'], 'stickers': stickers if stickers is not None else
                [{'slot': 4, 'def': 100, 'schema': 0, 'x': .644, 'y': 0, 'wear': 0, 'rotation': 0}]}

    def test_disabled_discovery_and_edits_never_look_up_catalog_or_inventory(self):
        for value in (None, False, 1, 'true'):
            with self.subTest(value=value):
                self.cfg['skin_tools_enabled'] = value
                self.known.reset_mock()
                with patch.object(skins, '_item_core', side_effect=AssertionError('No item lookup')):
                    view = adapter.tools_context(SimpleNamespace())
                    self.assertFalse(view['enabled'])
                    self.assertEqual(1, view['schema_version'])
                    with self.assertRaisesRegex(ValueError, '未启用'):
                        adapter.item_context(SimpleNamespace(), 'inv.1')
                    with self.assertRaisesRegex(ValueError, '未启用'):
                        adapter.apply_stickers(SimpleNamespace(), {})
                self.known.assert_not_called()
        self.net.assert_not_called()

    def test_enabled_discovery_is_lightweight(self):
        before = self.snapshot()
        view = adapter.tools_context(SimpleNamespace())
        self.assertTrue(view['enabled'])
        self.assertFalse(view['renderer_bundled'])
        self.assertEqual(5, view['max_stickers'])
        self.known.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def test_item_read_normalizes_native_legacy_defaults_without_mutation(self):
        before = self.snapshot()
        core = skins._item_core(self.career.inventory[0])
        view = adapter.item_context(self.state, 'inv.1')
        self.assertEqual(7, view['item']['def'])
        self.assertEqual(282, view['item']['paint'])
        self.assertEqual(core['seed'], view['item']['seed'])
        self.assertEqual(.15, view['item']['wear'])
        self.assertEqual(4, view['revision'])
        self.assertEqual(64, len(view['expected_hash']))
        self.assertNotEqual('untrusted-cache', view['expected_hash'])
        self.assertEqual('legacy', view['model']['model_variant'])
        self.assertEqual(.6456, view['model']['x_max'])
        self.assertEqual([100, 101], [kit['def'] for kit in view['sticker_catalog']])
        self.assertTrue(view['editable'])
        view['model']['x_max'] = 999
        self.assertEqual(before, self.snapshot())

    def test_public_appearance_has_no_identity_money_inventory_or_external_urls(self):
        self.career.inventory[0].update(nametag='Local custom name', stattrak=0)
        read = adapter.item_context(self.state, 'inv.1')
        written = adapter.apply_stickers(self.state, self.request())
        for value in (read, written, adapter.tools_context(self.state)):
            raw = json.dumps(value)
            for private in ('76561198000000000', 'never-expose', 'catalog-private',
                            'private-path', 'inv.2', 'https://', 'skin_quotes', 'cashflow',
                            'provenance', 'equipped_ct', 'steam_id', 'remote_account'):
                self.assertNotIn(private, raw)
            self.assertNotIn('inventory', value)
            self.assertNotIn('money', value)
        self.assertEqual('Local custom name', read['item']['nametag'])
        self.assertEqual(0, read['item']['stattrak'])

    def test_success_preserves_all_metadata_and_other_state_and_native_hash(self):
        before = self.snapshot()
        core = skins._item_core(before['inventory'][0])
        body = self.request()
        response = adapter.apply_stickers(self.state, body)
        after = self.snapshot()
        self.assertEqual(4, response['revision'])  # Only the service increments it.
        self.assertEqual('next_match', response['sync'])
        self.assertEqual([], response['warnings'])
        for key, value in before.items():
            if key != 'inventory':
                self.assertEqual(value, after[key], key)
        self.assertEqual(before['inventory'][1], after['inventory'][1])
        for key, value in before['inventory'][0].items():
            if key not in ('stickers', 'hash'):
                self.assertEqual(value, after['inventory'][0][key], key)
        self.assertEqual(core['seed'], after['inventory'][0]['seed'])
        self.assertEqual(response['expected_hash'], after['inventory'][0]['hash'])
        self.assertEqual(response['expected_hash'], skins._item_payload(after['inventory'][0])['hash'])
        self.assertNotEqual(body['expected_hash'], response['expected_hash'])
        self.sync.assert_not_called()
        self.net.assert_not_called()

    def test_zero_native_parameters_remain_zero(self):
        self.career.inventory[0].update(seed=0, wear=0)
        response = adapter.apply_stickers(self.state, self.request())
        self.assertEqual(0, response['item']['seed'])
        self.assertEqual(0, response['item']['wear'])
        self.assertEqual(0, response['item']['stickers'][0]['schema'])
        self.assertEqual(.644, response['item']['stickers'][0]['x'])
        self.assertEqual(0, response['item']['stickers'][0]['y'])
        self.assertEqual(0, response['item']['stickers'][0]['wear'])
        self.assertEqual(0, response['item']['stickers'][0]['rotation'])

    def test_same_edit_and_stale_hash_are_rejected_without_other_changes(self):
        body = self.request()
        adapter.apply_stickers(self.state, body)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, '外观已变化'):
            adapter.apply_stickers(self.state, body)
        stale = self.request()
        self.career.inventory[0]['seed'] += 1
        before_seed_change = self.snapshot()
        with self.assertRaisesRegex(ValueError, '外观已变化'):
            adapter.apply_stickers(self.state, stale)
        self.assertEqual(before_seed_change, self.snapshot())
        self.assertEqual(before['money'], self.career.money)

    def test_revision_must_match_and_have_exact_integer_type(self):
        body = self.request()
        for revision in (3, 5, '4', 4.0, True, None):
            before = self.snapshot()
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                adapter.apply_stickers(self.state, {**body, 'revision': revision})
            self.assertEqual(before, self.snapshot())

    def test_body_schema_hash_and_top_level_fields_are_strict(self):
        body = self.request()
        cases = [None, [], {**body, 'schema_version': True}, {**body, 'schema_version': 2},
                 {**body, 'schema_version': '1'}, {**body, 'expected_hash': True},
                 {**body, 'expected_hash': 'not-hash'}, {**body, 'expected_hash': 'a' * 63},
                 {**body, 'catalog': CATALOG}, {**body, 'money': 1},
                 {key: value for key, value in body.items() if key != 'stickers'}]
        for invalid in cases:
            before = self.snapshot()
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                adapter.apply_stickers(self.state, invalid)
            self.assertEqual(before, self.snapshot())

    def test_invalid_sticker_payloads_are_atomic(self):
        body = self.request()
        invalid = [None, {}, [{'slot': 0, 'def': 100}] * 2,
                   [{'slot': slot, 'def': 100} for slot in range(6)],
                   [{'slot': True, 'def': 100}], [{'slot': 0, 'def': 999}],
                   [{'slot': 0, 'def': 102}], [{'slot': 0, 'def': 100, 'schema': 4}],
                   [{'slot': 0, 'def': 100, 'wear': math.nan}],
                   [{'slot': 0, 'def': 100, 'x': .646}],
                   [{'slot': 0, 'def': 100, 'y': math.inf}],
                   [{'slot': 0, 'def': 100, 'rotation': 181}],
                   [{'slot': 0, 'def': 100, 'steam_id': 'forbidden'}]]
        for stickers in invalid:
            before = self.snapshot()
            with self.subTest(stickers=stickers), self.assertRaises(ValueError):
                adapter.apply_stickers(self.state, {**body, 'stickers': stickers})
            self.assertEqual(before, self.snapshot())

    def test_typed_item_ids_missing_items_and_duplicate_inventory_fail_closed(self):
        for ident in (None, True, 1, {}, '', ' inv.1', 'inv.404'):
            with self.subTest(ident=ident), self.assertRaises(ValueError):
                adapter.item_context(self.state, ident)
        body = self.request()
        self.career.inventory.append(deepcopy(self.career.inventory[0]))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, '重复'):
            adapter.item_context(self.state, 'inv.1')
        with self.assertRaisesRegex(ValueError, '重复'):
            adapter.apply_stickers(self.state, body)
        self.assertEqual(before, self.snapshot())

    def test_duplicate_server_kits_invalid_models_fail_before_mutation(self):
        body = self.request()
        duplicate = deepcopy(CATALOG)
        duplicate['stickers'].append(deepcopy(duplicate['stickers'][0]))
        bad_schema = deepcopy(CATALOG)
        bad_schema['models']['7']['schema_count'] = True
        bad_limits = deepcopy(CATALOG)
        bad_limits['models']['7']['x_max'] = math.nan
        bad_slots = deepcopy(CATALOG)
        bad_slots['models']['7']['allowed_slots'] = [{}]
        for known in (duplicate, bad_schema, bad_limits, bad_slots):
            before = self.snapshot()
            with patch.object(skins, 'sticker_catalog_for_item', return_value=known):
                with self.assertRaises(ValueError):
                    adapter.item_context(self.state, 'inv.1')
                with self.assertRaises(ValueError):
                    adapter.apply_stickers(self.state, body)
            self.assertEqual(before, self.snapshot())

    def test_removal_and_replacement_warnings_preserve_prices(self):
        adapter.apply_stickers(self.state, self.request([{'slot': 0, 'def': 100}, {'slot': 1, 'def': 100}]))
        response = adapter.apply_stickers(self.state, self.request([{'slot': 0, 'def': 101}]))
        self.assertEqual(2, len(response['warnings']))
        self.assertEqual(2, len(self.career.inventory))
        self.assertEqual(2700, self.career.inventory[0]['sell'])

    def test_external_mode_is_explicitly_local_and_does_not_claim_sync(self):
        self.cfg['skins_inventory_mode'] = 'external'
        self.assertEqual('none', adapter.item_context(self.state, 'inv.1')['sync'])
        response = adapter.apply_stickers(self.state, self.request())
        self.assertEqual('none', response['sync'])
        self.sync.assert_not_called()

    def test_nonweapon_exposes_native_appearance_but_rejects_placing_stickers(self):
        self.career.inventory[0].update({'skin_id': '', 'slot': 'knife', 'def': 507, 'paint': 44})
        view = adapter.item_context(self.state, 'inv.1')
        self.assertFalse(view['editable'])
        self.assertIsNone(view['model'])
        self.assertEqual(507, view['item']['def'])
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, '不支持贴纸'):
            adapter.apply_stickers(self.state, self.request())
        self.assertEqual(before, self.snapshot())

    def test_actual_packaged_finish_specific_model_and_kit_export(self):
        with patch.object(skins, 'sticker_catalog_for_item', side_effect=self.real_catalog_for_item):
            view = adapter.item_context(self.state, 'inv.1')
            self.assertEqual('legacy', view['model']['model_variant'])
            self.assertEqual(.6456, view['model']['x_max'])
            self.assertGreaterEqual(len(view['sticker_catalog']), 36)
            kit = view['sticker_catalog'][0]['def']
            response = adapter.apply_stickers(self.state, self.request([
                {'slot': 4, 'def': kit, 'schema': 0, 'x': .644, 'y': 0, 'rotation': 0, 'wear': 0}]))
            exported = skins._item_payload(self.career.inventory[0])
            self.assertEqual(.644, exported['stickers'][0]['x'])
            self.assertEqual(response['expected_hash'], exported['hash'])
        self.net.assert_not_called()


if __name__ == '__main__':
    unittest.main()
