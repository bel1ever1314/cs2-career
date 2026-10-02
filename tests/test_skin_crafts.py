from copy import deepcopy
import math
import unittest
from unittest.mock import patch

from cs2career.career import skin_crafts as crafts


CATALOG = {'stickers': [
    {'id': 'verified-a', 'def': 100, 'name': 'A', 'weapon_defs': [7]},
    {'id': 'verified-b', 'def': 101, 'name': 'B'}],
    'models': {
        '7': {'x_min': -0.4, 'x_max': 0.6, 'y_min': -0.03, 'y_max': 0.22,
              'schema_count': 4, 'rotation_min': -180, 'rotation_max': 180},
        '9': {'schema_count': 4, 'rotation_min': -180, 'rotation_max': 180}}}
SKINS = {'ak-test': {'id': 'ak-test', 'name': 'AK | Test', 'slot': 'ak47', 'weapon': 'AK-47',
                     'name_en': 'AK | Test', 'def': 7, 'paint': 282, 'rarity': 'classified', 'buy': 3000, 'sell': 2000}}


def item():
    return {'id': 'inv.1', 'skin_id': 'ak-test', 'name': 'AK | Test', 'weapon': 'AK-47',
            'slot': 'ak47', 'rarity': 'classified', 'def': 7, 'paint': 282,
            'wear': 0, 'seed': 0, 'stickers': [], 'spot': 3000, 'sell': 2700}


def pack():
    return {'schema_version': 1, 'id': 'test.donk.20260930', 'player': 'donk',
            'source_date': '2026-09-30', 'source_url': 'https://example.org/public-loadout', 'free': True,
            'items': [{'id': 'rifle', 'skin_id': 'ak-test', 'def': 7, 'paint': 282,
                       'wear': 0, 'seed': 0, 'stickers': [{'def': 100, 'slot': 0, 'wear': 0}]}]}


class AttachmentTests(unittest.TestCase):
    def normalize(self, rows, weapon=7, catalog=CATALOG):
        return crafts.normalize_attachments(rows, weapon, catalog)

    def test_five_unique_slots_may_share_four_anchor_schemas(self):
        rows = [{'slot': slot, 'def': 100, 'schema': 0} for slot in reversed(range(5))]
        result = self.normalize(rows)
        self.assertEqual(list(range(5)), [row['slot'] for row in result])
        self.assertEqual([0] * 5, [row['schema'] for row in result])
        self.assertEqual(4, rows[0]['slot'])
        implicit = self.normalize([{'slot': slot, 'def': 100} for slot in range(5)])
        self.assertEqual([0, 1, 2, 3, 0], [row['schema'] for row in implicit])

    def test_invalid_slots_count_duplicate_and_integer_types(self):
        for rows in ([{'slot': -1, 'def': 100}], [{'slot': 5, 'def': 100}],
                     [{'slot': True, 'def': 100}], [{'slot': 1.0, 'def': 100}],
                     [{'slot': 0, 'def': 100}] * 2,
                     [{'slot': slot, 'def': 100} for slot in range(6)], None, {}):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.normalize(rows)

    def test_positive_cataloged_integer_kit_required(self):
        for definition in (0, -1, True, 100.0, '100', 999, 4294967296):
            with self.subTest(definition=definition), self.assertRaises(ValueError):
                self.normalize([{'slot': 0, 'def': definition}])

    def test_zero_values_and_exact_boundaries_preserved(self):
        result = self.normalize([{'slot': 0, 'def': 100, 'wear': 0, 'rotation': 0, 'x': 0, 'y': 0, 'schema': 0}])[0]
        self.assertEqual({'slot': 0, 'def': 100, 'wear': 0.0, 'rotation': 0.0, 'x': 0.0, 'y': 0.0, 'schema': 0}, result)
        for rotation in (-180, 180):
            self.assertEqual(rotation, self.normalize([{'slot': 0, 'def': 100, 'rotation': rotation}])[0]['rotation'])
        self.normalize([{'slot': 4, 'def': 100, 'x': -0.4, 'y': 0.22, 'schema': 3, 'wear': 1}])

    def test_nonfinite_out_of_range_and_invalid_schemas(self):
        cases = [('wear', -0.01), ('wear', 1.01), ('wear', math.nan), ('wear', math.inf), ('wear', True),
                 ('rotation', 181), ('rotation', -181), ('rotation', math.nan), ('x', -0.401), ('x', 0.601),
                 ('y', -0.031), ('y', 0.221), ('schema', 4), ('schema', -1), ('schema', True)]
        for key, value in cases:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.normalize([{'slot': 0, 'def': 100, key: value}])

    def test_weapon_restrictions_and_undocumented_offsets(self):
        with self.assertRaises(ValueError):
            self.normalize([{'slot': 0, 'def': 100}], 9)
        self.assertEqual(101, self.normalize([{'slot': 0, 'def': 101}], 9)[0]['def'])
        with self.assertRaises(ValueError):
            self.normalize([{'slot': 0, 'def': 101, 'x': 0}], 9)
        with self.assertRaises(ValueError):
            self.normalize([{'slot': 0, 'def': 100}], 500)
        self.assertEqual([], self.normalize([], 500))

    def test_catalog_bad_or_duplicate_kits_rejected(self):
        malformed = deepcopy(CATALOG)
        malformed['stickers'].append(deepcopy(malformed['stickers'][0]))
        with self.assertRaises(ValueError):
            self.normalize([{'slot': 0, 'def': 100}], catalog=malformed)
        with self.assertRaises(ValueError):
            self.normalize([{'slot': 0, 'def': 100}], catalog={})

    def test_actual_packaged_resource_models_and_kits(self):
        actual = crafts.load_sticker_catalog()
        self.assertGreaterEqual(len(actual['stickers']), 36)
        kit = actual['stickers'][0]['def']
        model = actual['models']['7']
        result = self.normalize([{'slot': slot, 'def': kit, 'schema': 0} for slot in range(5)], catalog=actual)
        self.assertEqual(5, len(result))
        self.normalize([{'slot': 0, 'def': kit, 'schema': model['schema_count'] - 1,
                         'x': model['x_min'], 'y': model['y_max'], 'rotation': model['rotation_min']}], catalog=actual)
        with self.assertRaises(ValueError):
            self.normalize([{'slot': 0, 'def': kit, 'schema': model['schema_count']}], catalog=actual)
        for definition, limits in actual['models'].items():
            with self.subTest(definition=definition):
                result = self.normalize([{'slot': slot, 'def': kit} for slot in range(5)], int(definition), actual)
                self.assertEqual([slot % limits['schema_count'] for slot in range(5)], [row['schema'] for row in result])


class AppearanceTests(unittest.TestCase):
    def test_instance_zero_and_unknown_parameters_not_lost_or_invented(self):
        normalized = crafts.normalize_instance(item(), CATALOG)
        self.assertEqual(0, normalized['seed'])
        self.assertEqual(0.0, normalized['wear'])
        unknown = item()
        del unknown['seed'], unknown['wear']
        normalized = crafts.normalize_instance(unknown, CATALOG)
        self.assertNotIn('seed', normalized)
        self.assertNotIn('wear', normalized)
        for key, value in (('seed', -1), ('seed', 1001), ('seed', True), ('seed', None),
                           ('wear', None), ('wear', math.nan), ('wear', -0.1), ('wear', 1.1)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                crafts.normalize_instance({**item(), key: value}, CATALOG)

    def test_hash_stable_across_dict_and_attachment_order_not_inventory_id(self):
        first = item()
        first['stickers'] = [{'slot': 4, 'def': 101, 'wear': 0.0}, {'slot': 0, 'def': 100, 'rotation': 0}]
        second = dict(reversed(list(first.items())))
        second['id'], second['source'], second['sell'] = 'inv.999', 'unrelated', 1
        second['stickers'] = list(reversed(first['stickers']))
        self.assertEqual(crafts.appearance_hash(first, CATALOG), crafts.appearance_hash(second, CATALOG))
        self.assertEqual(64, len(crafts.appearance_hash(first, CATALOG)))
        self.assertEqual(4, first['stickers'][0]['slot'])

    def test_hash_changes_for_every_appearance_parameter(self):
        original = item()
        original['stickers'] = [{'slot': 0, 'def': 100, 'wear': 0, 'rotation': 0, 'x': 0, 'y': 0, 'schema': 0}]
        expected = crafts.appearance_hash(original, CATALOG)
        for key, value in (('paint', 283), ('seed', 1), ('wear', 0.1), ('nametag', 'Name'), ('stattrak', 0), ('tint', 1)):
            self.assertNotEqual(expected, crafts.appearance_hash({**original, key: value}, CATALOG))
        for key, value in (('def', 101), ('wear', 0.1), ('rotation', 1), ('x', 0.1), ('y', 0.1), ('schema', 1)):
            changed = deepcopy(original)
            changed['stickers'][0][key] = value
            self.assertNotEqual(expected, crafts.appearance_hash(changed, CATALOG))

    def test_free_edit_preserves_money_metadata_prices_and_input_rows(self):
        original = [item()]
        before = deepcopy(original)
        result = crafts.edit_stickers(original, 'inv.1', [{'slot': 0, 'def': 100, 'wear': 0}], CATALOG)
        self.assertEqual(before, original)
        for key in ('spot', 'sell', 'wear', 'seed', 'skin_id'):
            self.assertEqual(before[0][key], result['item'][key])
        self.assertTrue(result['item']['hash'])
        result['inventory'][0]['wear'] = 0.9
        self.assertEqual(0, result['item']['wear'])

    def test_replacement_and_removal_explicit_and_atomic(self):
        original = [item()]
        original[0]['stickers'] = [{'slot': 0, 'def': 100}, {'slot': 1, 'def': 100}]
        replacement = crafts.edit_stickers(original, 'inv.1', [{'slot': 0, 'def': 101}], CATALOG)
        self.assertEqual([0], replacement['replaced_slots'])
        self.assertEqual([1], replacement['removed_slots'])
        self.assertEqual(2, len(replacement['warnings']))
        with self.assertRaises(ValueError):
            crafts.edit_stickers(original, 'inv.1', [{'slot': 0, 'def': 999}], CATALOG)
        self.assertEqual(2, len(original[0]['stickers']))
        with self.assertRaises(ValueError):
            crafts.edit_stickers(original, 'missing', [], CATALOG)
        self.assertIn('移除', replacement['message'])
        self.assertIn('替换', replacement['message'])

    def test_obsolete_catalog_sticker_can_be_removed_without_catalog_or_game_access(self):
        original = [item()]
        original[0]['stickers'] = [{'slot': 4, 'def': 999}]
        original[0]['bound'] = True
        with patch.object(crafts, '_catalog_index', side_effect=AssertionError('removal needs no catalog')):
            result = crafts.edit_stickers(original, 'inv.1', [])
        self.assertEqual([], result['item']['stickers'])
        self.assertEqual([4], result['removed_slots'])
        self.assertTrue(result['item']['bound'])


class PackTests(unittest.TestCase):
    def validate(self, value):
        return crafts.validate_pack(value, SKINS, CATALOG)

    def import_pack(self, inventory, next_id, value):
        return crafts.import_pack(inventory, next_id, value, SKINS, CATALOG)

    def test_four_players_only_and_provenance_required(self):
        for name, canonical in (('donk', 'donk'), ('ZywOo', 'zywoo'), ('monesy', 'monesy'), ('m0NESY', 'monesy'), ('NiKo', 'niko')):
            value = pack()
            value['player'] = name
            self.assertEqual(canonical, self.validate(value)['player'])
        for key, value in (('player', 's1mple'), ('source_date', '2026-02-30'), ('source_date', '20260930'),
                           ('source_url', 'javascript:alert(1)'), ('source_url', 'https://user:password@example.org/'),
                           ('free', False), ('free', 'true'), ('price', 1), ('schema_version', True)):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.validate({**pack(), key: value})

    def test_exact_fields_free_bound_items_and_id_collision(self):
        original = [item()]
        value = pack()
        before = deepcopy(value)
        result = self.import_pack(original, 1, value)
        self.assertEqual(1, len(result['added']))
        added = result['added'][0]
        self.assertEqual('inv.2', added['id'])
        self.assertEqual(3, result['next_id'])
        self.assertTrue(added['bound'])
        self.assertEqual('AK | Test', added['name_en'])
        self.assertEqual((0, 0.0), (added['seed'], added['wear']))
        self.assertEqual(value['source_date'], added['source_date'])
        self.assertEqual(value['source_url'], added['source_url'])
        self.assertEqual(('test.donk.20260930', 'rifle'), (added['source_pack_id'], added['source_pack_item_id']))
        self.assertNotIn('sell', added)
        self.assertNotIn('buy', added)
        self.assertEqual(before, value)
        self.assertEqual([item()], original)

    def test_dedup_by_pack_and_recipe_id_not_skin_id(self):
        value = pack()
        value['items'].append({**deepcopy(value['items'][0]), 'id': 'same-finish-different-craft', 'seed': 1})
        first = self.import_pack([item()], 2, value)
        self.assertEqual(2, len(first['added']))
        self.assertEqual(3, len(first['inventory']))
        again = self.import_pack(first['inventory'], first['next_id'], value)
        self.assertEqual([], again['added'])
        self.assertEqual(['rifle', 'same-finish-different-craft'], again['skipped'])
        self.assertEqual(first['next_id'], again['next_id'])
        other_source = self.import_pack(again['inventory'], again['next_id'], {**value, 'id': 'test.donk.new-source'})
        self.assertEqual(2, len(other_source['added']))

    def test_wrong_catalog_weapon_paint_slot_and_duplicate_recipe_rejected(self):
        for key, replacement in (('def', 60), ('paint', 999), ('slot', 'awp'), ('weapon', 'AWP'), ('skin_id', 'missing')):
            value = pack()
            value['items'][0][key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(value)
        value = pack()
        value['items'].append(deepcopy(value['items'][0]))
        with self.assertRaises(ValueError):
            self.validate(value)

    def test_late_invalid_recipe_leaves_inventory_and_sequence_untouched(self):
        original, value = [item()], pack()
        value['items'].append({**deepcopy(value['items'][0]), 'id': 'invalid-last', 'seed': 1001})
        before = deepcopy(original)
        with self.assertRaises(ValueError):
            self.import_pack(original, 2, value)
        self.assertEqual(before, original)

    def test_unknown_values_remain_absent_without_defaults(self):
        value = pack()
        del value['items'][0]['wear'], value['items'][0]['seed']
        result = self.import_pack([], 1, value)
        self.assertNotIn('wear', result['added'][0])
        self.assertNotIn('seed', result['added'][0])

    def test_declared_finish_only_defaults_are_not_claimed_as_player_parameters(self):
        value = pack()
        value.update(quality='public_loadout_template', source_precision='finish_only')
        recipe = value['items'][0]
        del recipe['wear'], recipe['seed']
        recipe.update(defaults={'wear': 0.15, 'seed': 1}, source_parameters={'wear': None, 'seed': None})
        result = self.import_pack([], 1, value)['added'][0]
        self.assertEqual((0.15, 1), (result['wear'], result['seed']))
        provenance = result['provenance']
        self.assertEqual('finish_only', provenance['source_precision'])
        self.assertEqual({'wear': None, 'seed': None}, provenance['source_parameters'])
        self.assertEqual({'wear': 'declared_default', 'seed': 'declared_default'}, provenance['parameter_origin'])
        self.assertEqual(provenance['source_precision'], result['source_precision'])
        self.assertEqual(provenance['source_parameters'], result['source_parameters'])
        recipe['source_parameters']['seed'] = 1
        with self.assertRaises(ValueError):
            self.validate(value)

    def test_defaults_without_honest_precision_declaration_rejected(self):
        value = pack()
        value['items'][0].update(defaults={'wear': 0, 'seed': 0}, source_parameters={'wear': None, 'seed': None})
        with self.assertRaises(ValueError):
            self.validate(value)

    def test_skin_catalog_wear_limits_honored_without_silent_clamping(self):
        limited = deepcopy(SKINS)
        limited['ak-test'].update(min_float=0.1, max_float=0.7)
        value = pack()
        with self.assertRaises(ValueError):
            crafts.validate_pack(value, limited, CATALOG)
        value['items'][0]['wear'] = 0.1
        self.assertEqual(0.1, crafts.validate_pack(value, limited, CATALOG)['items'][0]['wear'])

    def test_module_has_no_save_sync_or_financial_calls(self):
        with patch('cs2career.career.skins.sync_live', side_effect=AssertionError('no game writes')), \
             patch('cs2career.paths.save_root', side_effect=AssertionError('no save access')):
            self.import_pack([], 1, pack())
            crafts.edit_stickers([item()], 'inv.1', [], CATALOG)


if __name__ == '__main__':
    unittest.main()
