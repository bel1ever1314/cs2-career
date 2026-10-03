"""RTS floor resource/provenance contracts; no live Career saves or CS2 access."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import unittest

from tools.career3d_rts import _map_rows, _map_reason

ROOT = Path(__file__).resolve().parents[1]
RTS = ROOT / 'work/career_rts'
sys.path.insert(0, str(RTS / 'tools'))
from build_layered import traversal_kind


class RTSLayerTests(unittest.TestCase):
    def test_ten_maps_are_available_in_career_and_layered_files_exist(self):
        rows = _map_rows()
        self.assertEqual(10, len(rows))
        self.assertTrue(all(row['status'] == 'playable' and row['career_ready'] for row in rows.values()))
        for map_id in ('de_nuke', 'de_vertigo'):
            row = rows[map_id]
            self.assertEqual(['upper', 'lower'], row['layers'])
            self.assertNotIn('多楼层路径', _map_reason(map_id, row))
            source = RTS / row['data_file'].removeprefix('res://')
            data = json.loads(source.read_text('utf-8'))
            self.assertEqual(map_id, data['map'])
            self.assertEqual([1024, 2048], data['world_size'])
            self.assertEqual('layered_actual_NAV', data['geometry']['kind'])
            for layer in data['layers']:
                self.assertTrue((RTS / layer['image'].removeprefix('res://')).is_file())
            grid_path = RTS / data['geometry']['grid_file'].removeprefix('res://')
            self.assertEqual(data['source']['grid_sha256'], hashlib.sha256(grid_path.read_bytes()).hexdigest())

    def test_real_floor_graph_never_joins_pages_by_adjacency(self):
        for stem in ('nuke', 'vertigo'):
            grid = json.loads((RTS / f'data/{stem}_grid.json').read_text('utf-8'))
            width, height = grid['width'], grid['height']
            edges = base64.b64decode(grid['edge_bits'])
            walk = base64.b64decode(grid['walk_bits'])
            self.assertEqual(width * height, len(edges))
            # Ordinary 8-neighbor edges never cross the upper/lower page seam.
            for x in range(width):
                self.assertFalse(edges[511 * width + x] & ((1 << 1) | (1 << 2) | (1 << 3)))
                self.assertFalse(edges[512 * width + x] & ((1 << 5) | (1 << 6) | (1 << 7)))
            links = {(row['from'], row['to']): row for row in grid['traversal_links']}
            self.assertTrue(any(a // 262144 != b // 262144 for a, b in links))
            self.assertTrue(any(row['kind'] == 'ladder' and row['evidence'] == 'NAV_ladder' for row in links.values()))
            self.assertTrue(any(row['kind'] == 'drop' and (b, a) not in links for (a, b), row in links.items()))
            for (a, b), row in links.items():
                self.assertTrue(walk[a >> 3] & 1 << (a & 7))
                self.assertTrue(walk[b >> 3] & 1 << (b & 7))
                self.assertGreater(row['seconds'], 0)
                self.assertIn(row['evidence'], ('NAV_connection', 'NAV_ladder'))
                self.assertNotEqual(row['source_area'], row['target_area'])

    def test_simplified_height_and_gap_actions(self):
        self.assertEqual('walk', traversal_kind(0, 0))
        self.assertEqual('step', traversal_kind(24, 0))
        self.assertEqual('jump', traversal_kind(48, 0))
        self.assertEqual('jump', traversal_kind(0, 40))
        self.assertEqual('drop', traversal_kind(-100, 0))
        self.assertEqual('ramp', traversal_kind(0, 0, slope=True))


if __name__ == '__main__': unittest.main()
