from __future__ import annotations

import math
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cs2career.career.career import Career, sponsor_month
from cs2career.career import economy
from cs2career.cs2.launch import (
    STEAM_ID64_BASE,
    build_request,
    install_match_avatars,
    install_match_identities,
)
from cs2career.cs2.result import result_usable
from cs2career.cs2.profiles import (
    PROFILE_RE,
    active_manifest,
    bot_parameters,
    classify_tier,
    generate_match_vpk,
    read_db,
)
from cs2career.engine.match import RNG, play_map, play_series
from cs2career.engine.rating import career_rating
from cs2career.world import MAPS, build_teams
from cs2career.world.ability import long_term_rating, overall_from_rating
from cs2career.world.eras import roster_for
from cs2career.cs2.launch import _validate_gamedata
from cs2career.paths import vendor_root


def fake_team(name: str, ability: float) -> dict:
    return {
        "id": name.lower(), "name": name, "world_rank": 1, "command": 70,
        "mentality": 70, "strong_maps": [], "weak_maps": [],
        "players": [{
            "player_id": f"p_{name.lower()}_{i}", "name": f"{name}{i}",
            "ability": ability, "form": ability, "form_delta": 0,
            "role": ("awp", "entry", "lurk", "igl", "rifle")[i],
            "stats": {"firepower": ability, "entrying": ability, "opening": ability, "clutching": ability},
        } for i in range(5)],
    }


class BotProfileTests(unittest.TestCase):
    def test_boundaries(self):
        expected = {64: "RankRifler", 65: "ProSlow", 74: "ProSlow", 75: "ProSteady", 84: "ProSteady", 85: "ProFast", 89: "ProFast", 90: "ProTop", 95: "ProTop", 98: "ProTop"}
        fast = {"entrying": 90, "opening": 90, "firepower": 70, "clutching": 70}
        for overall, tier in expected.items():
            self.assertEqual(classify_tier(overall, "rifle", fast), tier)

    def test_upstream_tiers_are_finite_bounded_without_custom_star_bonus(self):
        # User replaced the continuous offset model with original base + tiers.
        # Original Fast/Precise styles are not a monotonic reaction-time curve.
        for difficulty in ("Low", "Medium", "High"):
            from cs2career.cs2 import improver_presets
            token = improver_presets.preset('High')['raw_acceleration']
            rows = [bot_parameters(n, n, difficulty) for n in range(45, 101)]
            for row in rows:
                for key, value in row.items():
                    if isinstance(value, str):
                        self.assertIn(key, ('LookAngleMaxAccelNormal','LookAngleMaxAccelAttacking'))
                        self.assertEqual(value, token)
                    else:
                        self.assertTrue(math.isfinite(value) and value >= 0)
                self.assertLessEqual(row["LookAngleStiffnessNormal"], 3000)
            self.assertEqual([x["Skill"] for x in rows], sorted(x["Skill"] for x in rows))
            if difficulty != 'Medium':
                self.assertEqual(bot_parameters(95, 95, difficulty), bot_parameters(94, 94, difficulty))

    def test_vpk_contains_exactly_nine_profiles(self):
        match = build_request(fake_team("A", 80), fake_team("B", 82), "A0", "de_mirage", "ct")
        with tempfile.TemporaryDirectory() as raw:
            csgo = Path(raw) / "game" / "csgo"
            csgo.mkdir(parents=True)
            install_match_avatars(csgo, match)
            manifest = generate_match_vpk(csgo, match, "High", Path(raw) / "cache")
            text = read_db(csgo / "overrides" / "botprofile.vpk")
            self.assertEqual(manifest["count"], 9)
            self.assertEqual(len(PROFILE_RE.findall(text)), 9)
            self.assertEqual(len({b["player_id"] for b in manifest["bots"]}), 9)
            self.assertTrue(active_manifest(csgo)["valid"])
            self.assertTrue(all(bot["avatar_kind"] in ("team", "default") for bot in manifest["bots"]))
            self.assertTrue(all(Path(bot["avatar_path"]).is_file() for bot in manifest["bots"]))
            manifest_path = csgo / "overrides" / "botprofile.manifest.json"
            tampered = json.loads(manifest_path.read_text(encoding="utf-8"))
            tampered["difficulty"] = "Low"
            manifest_path.write_text(json.dumps(tampered), encoding="utf-8")
            self.assertFalse(active_manifest(csgo)["valid"])

    def test_unknown_team_uses_bundled_default_avatar(self):
        match = build_request(fake_team("Unknown A", 80), fake_team("Unknown B", 82), "Unknown A0", "de_mirage", "ct")
        with tempfile.TemporaryDirectory() as raw:
            csgo = Path(raw) / "game" / "csgo"
            csgo.mkdir(parents=True)
            install_match_avatars(csgo, match)
            manifest = generate_match_vpk(csgo, match, "Medium", Path(raw) / "cache")
            self.assertEqual({bot["avatar_kind"] for bot in manifest["bots"]}, {"default"})
            self.assertEqual(len({bot["avatar_hash"] for bot in manifest["bots"]}), 1)
            Path(manifest["bots"][0]["avatar_path"]).write_bytes(b"\x89PNG\r\n\x1a\nchanged")
            self.assertFalse(active_manifest(csgo)["valid"])

    def test_known_team_uses_curated_team_crest(self):
        match = build_request(fake_team("Vitality", 90), fake_team("Unknown", 80), "Vitality0", "de_nuke", "ct")
        with tempfile.TemporaryDirectory() as raw:
            csgo = Path(raw) / "game" / "csgo"
            csgo.mkdir(parents=True)
            install_match_avatars(csgo, match)
            manifest = generate_match_vpk(csgo, match, "Medium", Path(raw) / "cache")
            self.assertEqual({bot["avatar_kind"] for bot in manifest["bots"] if bot["side"] == "ct"}, {"team"})

    def test_match_uses_exactly_nine_unique_synthetic_identities(self):
        match = build_request(fake_team("A", 80), fake_team("B", 82), "A0", "de_mirage", "ct")
        with tempfile.TemporaryDirectory() as raw:
            csgo = Path(raw) / "game" / "csgo"
            csgo.mkdir(parents=True)
            install_match_avatars(csgo, match)
            generate_match_vpk(csgo, match, "Medium", Path(raw) / "cache")
            payload = install_match_identities(csgo, match)
            written = json.loads(
                (csgo / "addons" / "BotHider" / "bot_info.json").read_text(encoding="ascii")
            )
            steam_ids = [bot["steam_id"] for bot in match["bots"]]
            self.assertEqual(payload, written)
            self.assertEqual(len(payload["players"]), 9)
            self.assertEqual(len(set(steam_ids)), 9)
            self.assertTrue(all(sid > STEAM_ID64_BASE for sid in steam_ids))
            self.assertEqual(
                {row["player_name"] for row in payload["players"].values()},
                {bot["profile_name"] for bot in match["bots"]},
            )


class ResultTests(unittest.TestCase):
    def test_real_result_requires_exact_request_roster_and_five_per_side(self):
        ids = [f"p_{i}" for i in range(10)]
        session = {
            "nonce": "nonce-1", "map": "mirage", "started_at": "",
            "expected_player_ids": ids,
        }
        result = {
            "schema_version": 2, "status": "finished", "complete": True,
            "request_nonce": "nonce-1", "map": "de_mirage",
            "ct_score": 13, "t_score": 8,
            "players": [
                {"player_id": pid, "team": "ct" if i < 5 else "t"}
                for i, pid in enumerate(ids)
            ],
        }
        self.assertEqual(result_usable(result, session), "")
        result["players"][-1]["team"] = "ct"
        self.assertIn("各 5 人", result_usable(result, session))
        result["players"][-1]["team"] = "t"
        result["players"][-1]["player_id"] = "p_intruder"
        self.assertIn("身份", result_usable(result, session))

    def test_event_stream_conserves_kills_and_deaths(self):
        RNG.seed(77)
        a, b = fake_team("A", 85), fake_team("B", 80)
        result = play_map(a, b, "mirage")
        aa, bb = result["players"]["A"], result["players"]["B"]
        self.assertEqual(sum(p["k"] for p in aa), sum(p["d"] for p in bb))
        self.assertEqual(sum(p["k"] for p in bb), sum(p["d"] for p in aa))
        for line in aa + bb:
            self.assertEqual(line["rating"], career_rating(line["k"], line["d"], line["a"], line["damage"], line["kast_rounds"], result["rounds"]))

    def test_fixed_seed_balance(self):
        wins = {}
        for gap in (0, 5, 10):
            count = 0
            for seed in range(20260900, 20261000):
                RNG.seed(seed)
                if play_series(fake_team("A", 80 + gap), fake_team("B", 80), MAPS[:7], "test", 3)["winner"] == "A":
                    count += 1
            wins[gap] = count
        self.assertTrue(48 <= wins[0] <= 52, wins)
        self.assertTrue(62 <= wins[5] <= 72, wins)
        self.assertTrue(80 <= wins[10] <= 90, wins)


class FinanceTests(unittest.TestCase):
    @staticmethod
    def career_and_season():
        team = fake_team("Mine", 80)
        team["id"] = "mine"
        team["name"] = "Mine"
        team["money"] = 100000

        class Vrs:
            @staticmethod
            def table(_teams, _date):
                return [{"id": "mine", "name": "Mine", "rank": 10, "vrs": 1500}]

        season = SimpleNamespace(teams=[team], date="2026-03-01", vrs=Vrs(), events=[])
        career = Career()
        career.exists = True
        career.team_id = "mine"
        career.player_name = "Mine0"
        career.current_date = season.date
        # Finance methods normally persist; unit tests must never touch the
        # real save file beside the application.
        career.save = lambda: None
        return career, season, team

    def test_sponsor_is_automatic_and_forecast_is_explained(self):
        career, season, team = self.career_and_season()
        career._pay_sponsors(season, "2026-03")
        self.assertEqual(team["money"], 100000 + sponsor_month(10))
        self.assertFalse(career.inbox)
        self.assertEqual(career.cashflow[-1]["category"], "sponsor")
        ops = career._ops_public(season, team, {"mine": {"rank": 10}})
        forecast = ops["finance"]["club"]
        self.assertEqual(forecast["next_net"], sponsor_month(10) - ops["total"])
        self.assertEqual(sum(row["amount"] for row in forecast["lines"]), forecast["next_net"])

    def test_event_prize_auto_splits_without_mail(self):
        career, season, team = self.career_and_season()
        event = {
            "id": "event-1", "name": "Test Cup", "status": "done", "type": "t2",
            "prize": 100000, "matches": [{"played": True, "team_a": "Mine", "team_b": "Other"}],
            "awards": {}, "champion": "Mine",
        }
        career.watch = lambda *_args, **_kwargs: None
        with patch("cs2career.career.career.awards.placements", return_value={"Mine": "champion"}):
            career.award_event(season, event)
        club, pocket = economy.split_prize(34000)
        self.assertEqual(team["money"], 100000 + club)
        self.assertEqual(career.money, pocket)
        self.assertFalse(career.inbox)
        self.assertEqual([row["scope"] for row in career.cashflow[-2:]], ["club", "pocket"])

    def test_legacy_money_mail_is_credited_only_once_then_removed(self):
        career, season, team = self.career_and_season()
        career.inbox = [
            {"kind": "prize", "status": "open", "amount": 10000, "date": "2026-02-20", "title": "旧奖金"},
            {"kind": "sponsor", "status": "open", "amount": 5000, "date": "2026-02-01", "title": "旧赞助"},
        ]
        club, pocket = economy.split_prize(10000)
        self.assertTrue(career.settle_legacy_money_mail(season))
        self.assertEqual(team["money"], 100000 + club + 5000)
        self.assertEqual(career.money, pocket)
        self.assertFalse(career.inbox)
        self.assertFalse(career.settle_legacy_money_mail(season))
        self.assertEqual(team["money"], 100000 + club + 5000)


class EraPackTests(unittest.TestCase):
    def test_all_runtime_rosters_have_five_unique_players_not_historical_verification(self):
        for era in ("2024", "2025", "2026"):
            teams = build_teams(era)
            self.assertEqual(len(teams), {'2024': 54, '2025': 59, '2026': 49}[era])
            players = [p for team in teams for p in team["players"]]
            self.assertEqual(len(players), len(teams) * 5)
            self.assertEqual(len({p["player_id"] for p in players}), len(players))
            self.assertTrue(all(team["era_pack_version"] == 2 for team in teams))

    def test_estimated_historical_rosters_do_not_read_future_strength(self):
        low = [(f"future{i}", 45) for i in range(5)]
        high = [(f"future{i}", 100) for i in range(5)]
        a, source, quality = roster_for("2024", "Unlisted Test Club", low, 32)
        b, _, _ = roster_for("2024", "Unlisted Test Club", high, 32)
        self.assertEqual(a, b)
        self.assertEqual(source, "same-era-role-template-2024")
        self.assertEqual(quality, "estimated")

    def test_long_term_weighting_and_sample_shrinkage(self):
        self.assertEqual(long_term_rating(1.20, 1.10, 1.00, 20, 1.00), 1.145)
        self.assertEqual(long_term_rating(1.20, 1.10, 1.00, 0, 1.02), 1.02)
        self.assertEqual(overall_from_rating(1.10), 89.0)

    def test_ropz_long_term_overall_is_not_team_discounted(self):
        vitality = next(team for team in build_teams("2026") if team["name"] == "Vitality")
        ropz = next(player for player in vitality["players"] if player["name"] == "ropz")
        self.assertGreaterEqual(ropz["ability"], 89)
        self.assertLessEqual(ropz["ability"], 91)
        self.assertLess(ropz["form_delta"], 0)

    def test_bundled_gamedata_contract(self):
        path = vendor_root() / "InventorySimulator" / "gamedata" / "inventory-simulator.json"
        self.assertGreater(len(_validate_gamedata(path.read_bytes())), 10)
        with self.assertRaises(ValueError):
            _validate_gamedata(b'{"bad": {"offsets": {"windows": "x"}}}')


if __name__ == "__main__":
    unittest.main()
