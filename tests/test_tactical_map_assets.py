"""Bundled radar metadata is shared with the editor and plugin at build time."""
import hashlib
import json
import struct
import unittest

from cs2career import tactics
from cs2career.paths import data_file, static_dir


class TacticalMapAssetsTests(unittest.TestCase):
    def test_registry_covers_ten_maps_and_has_pinned_source(self):
        registry = json.loads(data_file('tactical_maps.json').read_text('utf-8'))
        self.assertEqual(registry['schema_version'], 1)
        self.assertEqual(set(registry['maps']), set(tactics.SUPPORTED_MAPS))
        self.assertEqual(len(registry['source']['revision']), 40)
        self.assertEqual(registry['source']['rights_holder'], 'Valve Corporation')

    def test_local_radars_have_matching_hash_and_dimensions(self):
        images = set()
        for entry in tactics.available_maps():
            code = entry['map']
            meta = tactics.map_metadata(code)
            self.assertEqual(meta['image'], f'/tactical_maps/{code}.png')
            self.assertEqual(meta['image_sha256'], meta['layers'][0]['image_sha256'])
            for layer in meta['layers']:
                with self.subTest(map=code, layer=layer['id']):
                    self.assertIn(layer['image'], (f'/tactical_maps/{code}.png', f'/tactical_maps/{code}_lower.png'))
                    blob = (static_dir()/layer['image'].lstrip('/')).read_bytes()
                    self.assertEqual(blob[:8], b'\x89PNG\r\n\x1a\n')
                    self.assertEqual(blob[12:16], b'IHDR')
                    self.assertEqual(struct.unpack('>II', blob[16:24]), (meta['width'], meta['height']))
                    self.assertEqual(hashlib.sha256(blob).hexdigest(), layer['image_sha256'])
                    images.add(layer['image'])
        self.assertEqual(len(images), 13)

    def test_layers_are_explicit_but_do_not_invent_extra_floors(self):
        for code in tactics.SUPPORTED_MAPS:
            layers = tactics.map_metadata(code)['layers']
            expected = ['upper', 'lower'] if code in ('de_nuke', 'de_train', 'de_vertigo') else ['upper']
            self.assertEqual([row['id'] for row in layers], expected)

    def test_world_projection_roundtrips_all_maps(self):
        for code in tactics.SUPPORTED_MAPS:
            for pixel in ([0, 0], [512, 512], [1024, 1024], [151.7, 901.2]):
                with self.subTest(map=code, pixel=pixel):
                    projected = tactics.world_to_pixel(tactics.pixel_to_world(pixel, code), code)
                    for actual, wanted in zip(projected, pixel):
                        self.assertAlmostEqual(actual, wanted, places=8)


if __name__ == '__main__':
    unittest.main()
