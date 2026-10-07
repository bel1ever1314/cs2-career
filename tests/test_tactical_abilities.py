"""Temporary duty scores remain metadata, never permanent player/profile changes."""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cs2career import arena_roles
from cs2career.cs2 import launch, profiles
from cs2career.world.ability import ability_of, ensure_role_calibration
from cs2career.world.roles import PLAYABLE_ROLES
from test_v15_core import fake_team


QA_ROOT = Path("D:/CS2CareerBuilds/v1.6.0/tactics-multimap-20261001/qa")


class TacticalAbilityTests(unittest.TestCase):
    def setUp(self):
        QA_ROOT.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="ability-slots-", dir=QA_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        environment = patch.dict(os.environ, {"CS2CAREER_SAVE_DIR": str(self.root / "save"), "CS2CAREER_NO_GAME": "1"})
        environment.start()
        self.addCleanup(environment.stop)
        self.csgo = self.root / "game" / "csgo"
        self.csgo.mkdir(parents=True)

    def specialist_team(self, name):
        team = fake_team(name, 82)
        for index, player in enumerate(team["players"]):
            player["stats"] = dict(firepower=61+index, entrying=91-index*7, trading=65+index*3,
                opening=87-index*4, clutching=41+index*8, sniping=93-index*12, utility=55)
        return team

    def test_scores_use_existing_calibration_on_copies(self):
        player = self.specialist_team("A")["players"][1]
        before = deepcopy(player)
        calibrated = deepcopy(player)
        ensure_role_calibration(calibrated)
        expected = {role: ability_of(calibrated["stats"], role) for role in PLAYABLE_ROLES}
        scores = arena_roles.tactical_abilities(player)
        self.assertEqual(expected, scores)
        self.assertGreater(len(set(scores.values())), 1)
        self.assertEqual(before, player)
        self.assertTrue(all(math.isfinite(score) and 0 <= score <= 100 for score in scores.values()))
        calibrated["role"] = "lurk"
        calibrated["stats"]["role_formula_version"] = 1
        calibrated_before = deepcopy(calibrated)
        upgraded = deepcopy(calibrated)
        ensure_role_calibration(upgraded)
        expected = {role: ability_of(upgraded["stats"], role) for role in PLAYABLE_ROLES}
        self.assertEqual(expected, arena_roles.tactical_abilities(calibrated))
        self.assertEqual(calibrated_before, calibrated)

    def test_missing_axes_keep_saved_strength_without_inventing_stats(self):
        player = {"player_id": "legacy", "role": "igl", "ability": 64.5}
        before = deepcopy(player)
        self.assertEqual({role: 64.5 for role in PLAYABLE_ROLES}, arena_roles.tactical_abilities(player))
        self.assertEqual(before, player)
        with self.assertRaises(ValueError):
            arena_roles.tactical_abilities({"ability": float("inf")})

    def test_request_builders_include_bot_and_human_scores_without_roster_changes(self):
        a, b = self.specialist_team("A"), self.specialist_team("B")
        a["players"][0]["role"] = "awp"
        before = deepcopy((a, b))
        for request in (launch.build_request(a, b, "A0", "de_nuke", "t"),
                        launch.build_lobby_request(a, b, "p_a_0", "de_nuke", "fixed")):
            self.assertEqual(arena_roles.tactical_abilities(a["players"][0]), request["human_tactical_abilities"])
            self.assertEqual("awp", request["human_role"])
            by_id = {player["player_id"]: player for team in (a, b) for player in team["players"]}
            bots = request["ct"]["players"]+request["t"]["players"]
            self.assertEqual(9, len(bots))
            for bot in bots:
                source = by_id[bot["player_id"]]
                self.assertEqual(arena_roles.tactical_abilities(source), bot["tactical_abilities"])
                self.assertEqual(source["role"], bot["role"])
                self.assertEqual(source["stats"], bot["stats"])
        observer = launch.build_lobby_request(a, b, "", "de_nuke", "observer")
        self.assertEqual({}, observer["human_tactical_abilities"])
        self.assertEqual("", observer["human_role"])
        self.assertEqual(10, len(observer["ct"]["players"]+observer["t"]["players"]))
        self.assertEqual(before, (a, b))

    def test_profile_manifest_and_request_preserve_scores_without_changing_hashes(self):
        request = launch.build_request(self.specialist_team("A"), self.specialist_team("B"), "A0", "de_dust2", "ct")
        launch.install_match_avatars(self.csgo, request)
        legacy = deepcopy(request)
        legacy.pop("human_tactical_abilities")
        for side in ("ct", "t"):
            for bot in legacy[side]["players"]:
                bot.pop("tactical_abilities")
        prepared = profiles.prepare_bots(request, "Medium")
        old_prepared = profiles.prepare_bots(legacy, "Medium")
        self.assertEqual([bot["profile_hash"] for bot in old_prepared], [bot["profile_hash"] for bot in prepared])
        self.assertTrue(all("tactical_abilities" not in bot for bot in old_prepared))
        manifest = profiles.generate_match_vpk(self.csgo, request, "Medium", self.root / "cache")
        db = (self.csgo / "overrides" / "career_botprofile.vpk").read_bytes()
        old_manifest = profiles.generate_match_vpk(self.csgo, legacy, "Medium", self.root / "cache")
        self.assertEqual(db, (self.csgo / "overrides" / "career_botprofile.vpk").read_bytes())
        for field in ("manifest_hash", "vpk_sha256", "template_hash", "preset_source_hash"):
            self.assertEqual(old_manifest[field], manifest[field])
        self.assertEqual(request["human_tactical_abilities"], manifest["human_tactical_abilities"])
        self.assertNotIn("human_tactical_abilities", old_manifest)
        for bot, original in zip(manifest["bots"], prepared):
            self.assertEqual(original["tactical_abilities"], bot["tactical_abilities"])
        for side in ("ct", "t"):
            self.assertTrue(all("tactical_abilities" in bot for bot in request[side]["players"]))
        self.assertTrue(all("tactical_abilities" in bot for bot in request["bots"]))
        profiles.generate_match_vpk(self.csgo, request, "Medium", self.root / "cache")
        self.assertTrue(profiles.active_manifest(self.csgo)["valid"])
        launch.install_match_identities(self.csgo, request)
        self.assertTrue(all("tactical_abilities" in bot and "steam_id" in bot for bot in request["bots"]))
        exported = json.loads(json.dumps(request, allow_nan=False))
        self.assertEqual(request["human_tactical_abilities"], exported["human_tactical_abilities"])

    def test_invalid_scores_are_rejected_before_artifact_writes(self):
        request = launch.build_request(fake_team("A", 82), fake_team("B", 80), "A0", "de_dust2", "ct")
        launch.install_match_avatars(self.csgo, request)
        for invalid in ({}, {"rifle": 80}, {**request["ct"]["players"][0]["tactical_abilities"], "support": 80},
                        {role: True for role in PLAYABLE_ROLES}, {role: float("nan") for role in PLAYABLE_ROLES},
                        {role: -1 for role in PLAYABLE_ROLES}, {role: 101 for role in PLAYABLE_ROLES}):
            value = deepcopy(request)
            value["ct"]["players"][0]["tactical_abilities"] = invalid
            with self.subTest(scores=invalid), self.assertRaises(ValueError):
                profiles.generate_match_vpk(self.csgo, value, "Medium", self.root / "cache")
            self.assertFalse((self.csgo / "overrides").exists())
        value = deepcopy(request)
        value["human_tactical_abilities"] = {role: float("inf") for role in PLAYABLE_ROLES}
        with self.assertRaises(ValueError):
            profiles.generate_match_vpk(self.csgo, value, "Medium", self.root / "cache")
        self.assertFalse((self.csgo / "overrides").exists())


if __name__ == "__main__":
    unittest.main()
