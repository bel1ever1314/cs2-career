import copy
import unittest
from pathlib import Path
from cs2career.paths import data_file

from cs2career.cs2.motion_clips import motion_clip_pack, validate
from cs2career.cs2.natural_behavior import configure_match


@unittest.skipUnless(data_file('natural_behavior').is_dir(), 'Unreleased Bot Lab data intentionally omitted from 1.6 public source')
class MotionClipTests(unittest.TestCase):
    def setUp(self):
        _, self.pack, _ = motion_clip_pack()

    def test_contract_and_no_private_paths_or_full_tracks(self):
        validate(self.pack)
        self.assertLessEqual(len(self.pack['clips']), 512)
        for clip in self.pack['clips']:
            self.assertGreater(len(clip['frames']), 30)
            self.assertNotIn('steamid', clip)
            self.assertNotIn('demo_path', clip['source'])
            self.assertEqual(64, len(clip['source']['demo_sha256']))
            self.assertEqual('pending', clip['source']['geometry_review'])

    def test_request_binds_hash_and_only_dust2(self):
        info = configure_match({'map':'de_dust2'}, 'natural')
        self.assertEqual(64, len(info['clip_hash']))
        self.assertEqual(len(self.pack['clips']), info['clip_count'])
        self.assertNotIn('clip_path', configure_match({'map':'de_mirage'}, 'natural'))

    def test_runtime_does_not_filter_bothider_by_fake_client_flag(self):
        source = (Path(__file__).resolve().parents[1]/'vendor/CareerMatch/CareerMatch.Natural.cs').read_text(encoding='utf-8')
        eligibility = source.split('var careerBot=',1)[1].split(';',1)[0]
        self.assertNotIn('IsBot', eligibility)
        self.assertIn('cfg is not null', eligibility)
        self.assertIn('HasBeenControlledByPlayerThisRound', eligibility)

    def test_rejects_corruption_and_fake_jumps(self):
        base = copy.deepcopy(self.pack)
        base['clips'] = [base['clips'][0]]
        for change in (
            lambda p:p.update(map='de_mirage'),
            lambda p:p.update(execution='snap_to_demo'),
            lambda p:p['clips'][0]['frames'][0].__setitem__(1, float('nan')),
            lambda p:p['clips'][0]['frames'][2].__setitem__(0, 0),
            lambda p:p['clips'][0]['frames'][2].__setitem__(12, 1),
            lambda p:p['clips'].append(p['clips'][0]),
        ):
            broken = copy.deepcopy(base)
            change(broken)
            with self.assertRaises(ValueError):
                validate(broken)


if __name__ == '__main__':
    unittest.main()
