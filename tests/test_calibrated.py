"""Candidate lookup/position semantics; no application state or career writes."""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlparse

from cs2career.world import calibrated
from tools import promote_calibration_pack


class CalibratedPackTests(unittest.TestCase):
    def candidate(self, name="donk", role="entry", era="2026", team="Spirit"):
        stats = calibrated.stats_for_candidate(name, role, era, team)
        self.assertIsNotNone(stats)
        return stats

    def test_pack_is_cached_and_recursively_immutable(self):
        pack = calibrated.load_calibrated_pack()
        self.assertIs(pack, calibrated.load_calibrated_pack())
        self.assertEqual(1141, len(pack["records"]))
        with self.assertRaises(TypeError):
            pack["model_version"] = "changed"
        with self.assertRaises(TypeError):
            pack["records"][0]["axes"]["firepower"] = 1
        with self.assertRaises(TypeError):
            pack["records"][0]["uncertainty"]["overall"][0] = 1

    def test_world_lookup_is_exact_era_team_and_name(self):
        row = calibrated.lookup("donk", "2026", "Spirit")
        self.assertIs(row, calibrated.lookup("donk", "2026", "spirit"))
        self.assertEqual("2026", row["era"])
        self.assertIsNone(calibrated.lookup("donk", "2026"))
        for name, era, team in (("Donk", "2026", "Spirit"),
                                ("donk", "2026", "SPIRIT"),
                                ("donk", "2026", "Vitality"),
                                ("donk", "2027", "Spirit")):
            self.assertIsNone(calibrated.lookup(name, era, team))
        self.assertEqual("2024", calibrated.lookup("donk", "2024", "Spirit")["era"])

    def test_missing_world_candidate_never_falls_back_to_library(self):
        library = next(row for row in calibrated.load_calibrated_pack()["records"] if row["kind"] == "library")
        self.assertIsNone(calibrated.lookup(library["name"], "2026", "nonexistent-team"))
        self.assertIsNotNone(calibrated.lookup(library["name"], kind="library"))
        self.assertIs(calibrated.lookup(library["name"], kind="library"),
                      calibrated.lookup(library["name"], kind="current_library"))

    def test_free_agents_only_have_a_2026_candidate(self):
        row = next(row for row in calibrated.load_calibrated_pack()["records"] if row["kind"] == "free_agent")
        self.assertIsNotNone(calibrated.lookup(row["name"], "2026", kind="free_agent"))
        self.assertIsNone(calibrated.lookup(row["name"], "2025", kind="free_agent"))
        self.assertIsNone(calibrated.lookup(row["name"], "2024", kind="free_agent"))
        self.assertIsNone(calibrated.lookup(row["name"], kind="not-a-kind"))

    def test_candidate_role_argument_never_rebases_or_expresses_axes(self):
        row = calibrated.lookup("donk", "2026", "Spirit")
        one = self.candidate(role="entry")
        other = self.candidate(role="awp")
        self.assertEqual(one, other)
        self.assertEqual(row["reference_role"], other["position_model"]["reference_role"])
        self.assertEqual(dict(row["axes"]), {axis: other[axis] for axis in calibrated.AXES})
        self.assertEqual(row["overall"], other["ability"])
        self.assertNotEqual(dict(row["axes"]), calibrated.express_axes(other, "awp"))

    def test_getter_returns_owned_stats_and_metadata(self):
        one = self.candidate()
        expected = self.candidate()
        one["firepower"] = 1
        one["position_model"]["reference_role"] = "awp"
        one["calibration_provenance"]["uncertainty"]["overall"][0] = 1
        self.assertEqual(expected, self.candidate())

    def test_marker_for_blended_drafts_has_no_real_player_identity(self):
        marker = calibrated.model_marker("lurk", "draft-receipt:42")
        self.assertEqual("draft-receipt:42", marker["seed_id"])
        self.assertEqual(.3, marker["expression_weight"])
        self.assertEqual(3, marker["expression_cap"])
        self.assertEqual(3, marker["fit_cap"])
        self.assertNotIn("baseline_axes", marker)
        self.assertNotIn("reference_score", marker)

    def test_native_scale_and_igl_utility_weight(self):
        stats = {axis: 70 for axis in calibrated.AXES}
        for role in calibrated.ROLE_WEIGHTS:
            self.assertEqual(70, calibrated.weighted_score(stats, role))
        stats["utility"] = 100
        self.assertEqual(73.6, calibrated.weighted_score(stats, "igl"))
        self.assertEqual(70, calibrated.weighted_score(stats, "rifle"))
        self.assertEqual(77.2, calibrated.weighted_score(stats, "support"))

    def test_neutral_axes_do_not_get_an_awp_ability_bonus(self):
        stats = {axis: 70 for axis in calibrated.AXES}
        stats["position_model"] = calibrated.model_marker("rifle")
        for role in calibrated.POSITIONS:
            self.assertEqual(0, calibrated.role_fit(stats, role))

    def test_reference_restores_current_base_and_fit_uses_base(self):
        stats = self.candidate()
        reference = stats["position_model"]["reference_role"]
        stats["firepower"] = 97.123456
        self.assertEqual({axis: stats[axis] for axis in calibrated.AXES},
                         calibrated.express_axes(stats, reference))
        self.assertEqual(0, calibrated.role_fit(stats, reference))
        fit = calibrated.role_fit(stats, "awp")
        preview = calibrated.express_axes(stats, "awp")
        preview["sniping"] = 100
        self.assertEqual(fit, calibrated.role_fit(stats, "awp"))

    def test_switching_never_accumulates_or_changes_overall(self):
        stats = self.candidate()
        before = deepcopy(stats)
        expected = {role: calibrated.express_axes(stats, role) for role in calibrated.POSITIONS}
        for _ in range(50):
            for role in calibrated.POSITIONS:
                self.assertEqual(expected[role], calibrated.express_axes(stats, role))
                self.assertLessEqual(abs(calibrated.role_fit(stats, role)), 3)
        self.assertEqual(before, stats)

    def test_expressions_are_bounded_with_softened_headroom(self):
        for base in (1, 1.5, 3, 70, 97, 99.5, 100):
            for reference in calibrated.ROLE_WEIGHTS:
                stats = {axis: base for axis in calibrated.AXES}
                stats["position_model"] = calibrated.model_marker(reference)
                for role in calibrated.ROLE_WEIGHTS:
                    axes = calibrated.express_axes(stats, role)
                    self.assertEqual(set(calibrated.AXES), set(axes))
                    self.assertTrue(all(math.isfinite(value) and 1 <= value <= 100 for value in axes.values()))
                    self.assertTrue(all(abs(value - base) <= 3.000001 for value in axes.values()))
        stats = {axis: 99.5 for axis in calibrated.AXES}
        stats["position_model"] = calibrated.model_marker("rifle")
        self.assertEqual(99.875, calibrated.express_axes(stats, "awp")["sniping"])

    def test_invalid_skills_markers_and_parameters_are_rejected(self):
        for bad in (True, None, float("nan"), float("inf"), 0, 101, "70"):
            stats = self.candidate()
            stats["firepower"] = bad
            with self.assertRaises(ValueError):
                calibrated.express_axes(stats, "awp")
            with self.assertRaises(ValueError):
                calibrated.role_fit(stats, "awp")
        for key, bad in (("fit_cap", 6), ("expression_cap", 6),
                         ("expression_weight", -1), ("headroom_softening", 1),
                         ("reference_role", "coach"), ("model_version", "unknown")):
            stats = self.candidate()
            stats["position_model"][key] = bad
            with self.assertRaises(ValueError):
                calibrated.express_axes(stats, "awp")
        with self.assertRaises(ValueError):
            calibrated.express_axes({axis: 70 for axis in calibrated.AXES}, "awp")
        with self.assertRaises(ValueError):
            calibrated.model_marker("coach")

    def test_all_records_base_and_five_views_have_finite_bounds(self):
        pack = calibrated.load_calibrated_pack()
        for row in pack["records"]:
            stats = calibrated.stats_for_candidate(row["name"], row["reference_role"], row["era"], row["team_id"], row["kind"])
            self.assertEqual(row["overall"], stats["ability"])
            self.assertEqual(dict(row["axes"]), {axis: stats[axis] for axis in calibrated.AXES})
            for role in calibrated.POSITIONS:
                axes = calibrated.express_axes(stats, role)
                self.assertTrue(all(math.isfinite(value) and 1 <= value <= 100 for value in axes.values()))
                self.assertLessEqual(abs(calibrated.role_fit(stats, role)), 3)

    def test_only_five_people_have_annual_evidence_with_no_future_windows(self):
        anchors = [row for row in calibrated.load_calibrated_pack()["records"] if row["evidence"]["level"] == "annual_top30"]
        self.assertEqual(14, len(anchors))
        self.assertEqual({"MiQ", "donk", "NiKo", "ZywOo", "m0NESY"}, {row["canonical_name"] for row in anchors})
        self.assertEqual(5, len({row["hltv_id"] for row in anchors}))
        for row in anchors:
            if row["era"] == "library":
                year = 2025
            else:
                self.assertIn(row["era"], ("2025", "2026"))
                year = int(row["era"]) - 1
            for source in row["evidence"]["sources"]:
                parsed = urlparse(source["url"])
                query = parse_qs(parsed.query)
                self.assertEqual([f"{year}-01-01"], query["startDate"])
                self.assertEqual([f"{year}-12-31"], query["endDate"])
                self.assertIn(f"/players/{row['hltv_id']}/", parsed.path)

    def test_artifact_hash_and_no_raw_traces(self):
        path = promote_calibration_pack.DEFAULT_OUTPUT
        raw = json.loads(path.read_text(encoding="utf-8"))
        pack_id = raw.pop("pack_id")
        self.assertEqual(pack_id, promote_calibration_pack._digest(raw))
        self.assertLess(path.stat().st_size, 1_500_000)
        for row in raw["records"]:
            self.assertNotIn("raw", row)
            self.assertNotIn("old", row)
            self.assertNotIn("positions", row)
            self.assertNotIn("components", row)
            self.assertNotIn("rating", row["axes"])
            self.assertNotIn("adr", row["axes"])

    @unittest.skipUnless(promote_calibration_pack.DEFAULT_LAB.is_dir(), "isolated source lab unavailable")
    def test_full_pack_and_all_views_match_fresh_lab_without_source_writes(self):
        lab = promote_calibration_pack.DEFAULT_LAB
        paths = [lab / "snapshot.json", lab / "parameters.json", lab / "calibration.py", lab / "report.json"]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        pack = promote_calibration_pack.build_pack(lab)
        actual = json.loads(promote_calibration_pack.DEFAULT_OUTPUT.read_text(encoding="utf-8"))
        self.assertEqual(actual, pack)
        self.assertEqual(5705, pack["coverage"]["position_views_checked"])
        self.assertEqual(before, {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths})


if __name__ == "__main__":
    unittest.main()
