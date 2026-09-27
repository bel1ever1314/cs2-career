import tempfile
import unittest
from pathlib import Path
from cs2career.paths import data_file

from cs2career.cs2 import launch
from cs2career.cs2.natural_behavior import CLASSIC_CVARS, behavior_pack, cfg_lines, configure_match, profile


@unittest.skipUnless(data_file('natural_behavior').is_dir(), 'Unreleased Bot Lab data intentionally omitted from 1.6 public source')
class NaturalBehaviorTests(unittest.TestCase):
    def test_pack_is_valid_and_contains_aggregate_evidence_only(self):
        data = profile()
        self.assertEqual(["de_dust2"], data["supported_maps"])
        self.assertEqual(64, len(data["sha256"]))
        self.assertEqual("aggregate_professional_demo_statistics", data["source"]["kind"])
        self.assertNotIn("demo_path", data["source"])
        path, pack, raw = behavior_pack()
        self.assertTrue(path.is_file())
        self.assertEqual(3, pack["schema_version"])
        self.assertEqual("de_dust2", pack["map"])
        self.assertGreaterEqual(pack["source"]["demo_count"], 5)
        self.assertGreater(len(pack["nodes"]), 100)
        self.assertTrue(pack["edges"])
        self.assertTrue(pack["formations"])
        self.assertTrue(any(node["peek_primitives"] for node in pack["nodes"]))
        self.assertTrue(all(node["evidence"]["position_kind"] == "observed_medoid" for node in pack["nodes"]))
        self.assertTrue(all(16 <= node["safe_radius"] <= 48 for node in pack["nodes"]))
        self.assertTrue(all(anchor["lane"] for node in pack["nodes"] for anchor in node["aim_lanes"]))
        for node in pack["nodes"]:
            lanes = {anchor["lane"] for anchor in node["aim_lanes"]}
            if node["zone"] == "a":
                self.assertTrue(lanes.isdisjoint({"b_tunnels", "b_doors", "b_hole", "b_site"}))
            if node["zone"] == "b":
                self.assertTrue(lanes.isdisjoint({"a_long", "a_short", "a_site"}))
            self.assertTrue(all(peek["lane"] in lanes for peek in node["peek_primitives"]))
        self.assertEqual(2, pack["coverage_rules"]["cross_zone_enemy_count"])
        self.assertGreaterEqual(pack["policy"]["opening_max_ms"], 10000)
        self.assertGreater(pack["policy"]["late_after_ms"], pack["policy"]["opening_max_ms"])
        self.assertGreaterEqual(pack["policy"]["strategic_alert_delay_ms"], 250)
        self.assertGreaterEqual(pack["policy"]["strategic_memory_ms"], 1000)
        self.assertGreaterEqual(pack["policy"]["task_stall_ms"], 1200)
        self.assertGreaterEqual(pack["policy"]["arrival_distance"], 8)
        self.assertGreaterEqual(pack["policy"]["arrival_speed"], 12)
        self.assertGreaterEqual(pack["policy"]["arrival_stable_ms"], 60)
        ct_lanes = {anchor["lane"] for node in pack["nodes"] if node["side"] == "ct"
                    for anchor in node["aim_lanes"]}
        self.assertTrue(set(pack["coverage_rules"]["ct_critical_lanes"]).issubset(ct_lanes))
        self.assertTrue(all("steamid" not in node for node in pack["nodes"]))
        self.assertLess(len(raw), 2 * 1024 * 1024)

    def test_natural_is_active_only_on_dust2(self):
        dust = {"map": "de_dust2"}
        info = configure_match(dust, "natural")
        self.assertEqual("natural", info["active"])
        self.assertTrue(info["profile_hash"])
        self.assertEqual(3, info["route_schema"])
        self.assertGreater(info["route_count"], 100)
        self.assertGreater(info["anchor_count"], 20)
        self.assertGreater(info["formation_count"], 10)
        self.assertEqual("natural_dust2_continuous_clips_v6", info["profile_id"])
        self.assertEqual(1, info['clip_schema'])
        self.assertGreater(info['clip_count'], 0)
        self.assertIn("阶段", info["route_scope"])
        text = "\n".join(cfg_lines(dust))
        self.assertIn("nav_smooth_spring_yaw_rotation_speed 260", text)
        self.assertIn("npcsolve_path_lookahead_dist 1800", text)

        mirage = {"map": "de_mirage"}
        info = configure_match(mirage, "natural")
        self.assertEqual("classic", info["active"])
        self.assertIn("只支持 de_dust2", info["fallback_reason"])
        text = "\n".join(cfg_lines(mirage))
        self.assertIn(f"npcsolve_path_lookahead_dist {CLASSIC_CVARS['npcsolve_path_lookahead_dist']:g}", text)

    def test_career_cfg_writes_auditable_active_style(self):
        with tempfile.TemporaryDirectory() as raw:
            csgo = Path(raw)
            match = {
                "map": "de_dust2", "quota": 9,
                "ct": {"name": "A", "logo": "aaaa", "players": []},
                "t": {"name": "B", "logo": "bbbb", "players": []},
            }
            configure_match(match, "natural")
            launch.write_career_cfg(csgo, match, dict(launch.DEFAULTS, bot_movement="natural"))
            text = (csgo / "cfg" / "career_rules.cfg").read_text(encoding="utf-8")
            self.assertIn("Career movement style: natural_dust2", text)
            self.assertIn("nav_smooth_spring_yaw_threshold 135", text)


if __name__ == "__main__":
    unittest.main()
