"""Pinned viewer mappings and engine-space positions, without network or CS2."""
from copy import deepcopy
import unittest

from cs2career.career import skins
from cs2career.career.skin_crafts import edit_stickers
from tools.build_inspect_catalog import build


class InspectContractTests(unittest.TestCase):
    def test_valve_ids_are_not_viewer_ids(self):
        manifest = skins.inspect_catalog()
        self.assertEqual(222, manifest['items']['7:282'])
        self.assertEqual(12459, manifest['stickers']['7928'])
        self.assertNotEqual(7, manifest['items']['7:282'])
        self.assertTrue(all(str(row['def']) in manifest['stickers'] for row in skins.sticker_catalog()['stickers']))

    def test_all_pro_guns_knives_gloves_have_exact_viewer_mapping(self):
        manifest = skins.inspect_catalog()
        bundle = skins.pro_bundle()
        for pack in bundle['packs']:
            slots = {bundle['skins'][item['skin_id']]['slot'] for item in pack['items']}
            self.assertTrue({'knife', 'gloves'}.issubset(slots))
            for item in pack['items']:
                key = f"{item['def']}:{item['paint']}"
                self.assertIn(key, manifest['items'], key)

    def test_legacy_range_is_not_incorrectly_restricted_to_hd_intersection(self):
        item = {'id': 'test', 'def': 7, 'paint': 282, 'wear': .15, 'seed': 1,
                'slot': 'ak47', 'stickers': [], 'source_pack_id': 'fixture'}
        known = skins.sticker_catalog_for_item(item)
        model = known['models']['7']
        self.assertEqual('legacy', model['model_variant'])
        self.assertEqual(.6456, model['x_max'])
        stickers = [{'def': 7928, 'slot': 4, 'schema': 0, 'x': .644, 'y': 0,
                     'wear': 0, 'rotation': 0}]
        result = edit_stickers([item], 'test', stickers, known)
        exported = skins._item_payload(result['item'])
        self.assertEqual(.644, exported['stickers'][0]['x'])
        self.assertEqual(4, exported['stickers'][0]['slot'])
        self.assertEqual(0, exported['stickers'][0]['schema'])
        self.assertEqual(result['item']['hash'], exported['hash'])
        self.assertEqual([], item['stickers'])

    def test_builder_selects_finish_specific_native_ranges(self):
        base = {'id': 4, 'definitionIndex': 7, 'type': 'weapon',
                'stickerSchemaCount': 4, 'legacyStickerSchemaCount': 3}
        for prefix, limit in [('sticker', 1), ('legacySticker', 2)]:
            base.update({prefix+'OffsetXMin': -limit, prefix+'OffsetXMax': limit,
                         prefix+'OffsetYMin': -limit, prefix+'OffsetYMax': limit})
        rows = [base, {'id': 222, 'definitionIndex': 7, 'variantIndex': 282,
                       'parentId': 4, 'type': 'weapon', 'isLegacyModel': True},
                {'id': 333, 'definitionIndex': 7, 'variantIndex': 444,
                 'parentId': 4, 'type': 'weapon'},
                {'id': 12459, 'type': 'sticker', 'variantIndex': 7928, 'imagePath': '/images/g2.webp'}]
        output = build(rows, {7}, {7928})
        self.assertEqual(2, output['models']['222']['x_max'])
        self.assertEqual(1, output['models']['333']['x_max'])
        self.assertEqual(3, output['models']['222']['schema_count'])
        self.assertEqual(4, output['models']['333']['schema_count'])
        with self.assertRaises(ValueError):
            build(rows, {7}, {999999})
        duplicate = deepcopy(rows[1])
        duplicate['id'] = 999
        with self.assertRaises(ValueError):
            build(rows+[duplicate], {7}, {7928})


if __name__ == '__main__':
    unittest.main()
