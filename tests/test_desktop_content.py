# coding=utf-8
import json
import tempfile
import unittest
from pathlib import Path

from cs2career.career.career import Career
from cs2career.career.origins import ORIGINS
from cs2career.content.loader import PackRegistry
from cs2career.league.season import Season


class OriginTests(unittest.TestCase):
    def test_three_origins_make_complete_distinct_starts(self):
        seen = set()
        for key, cfg in ORIGINS.items():
            season = Season()
            career = Career()
            career.save = lambda: None
            career.create({
                "era": "2026", "mode": "create", "role": "rifle",
                "name": f"Tester {key}", "org": f"Test {key}",
                "region": "AS", "origin": key,
            }, season)
            team = career.my_team(season.teams)
            self.assertEqual(5, len(team["players"]))
            self.assertEqual(5, len({p["player_id"] for p in team["players"]}))
            self.assertEqual(cfg["player_ability"], team["players"][0]["ability"])
            self.assertEqual(cfg["club_money"], team["money"])
            self.assertEqual(cfg["pocket_money"], career.money)
            self.assertEqual(cfg["attr_points"], career.attr_points)
            seen.add((career.money, team["money"], team["players"][0]["ability"]))
        self.assertEqual(3, len(seen))


class PackTests(unittest.TestCase):
    def test_valid_pack_loads_and_bad_pack_is_isolated(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            good = root / "good"
            (good / "stories").mkdir(parents=True)
            (good / "pack.json").write_text(json.dumps({
                "schema_version": 1, "id": "test.good", "name": "Good",
                "version": "1", "types": ["stories"],
            }), encoding="utf-8")
            (good / "stories" / "a.json").write_text(json.dumps({
                "stories": [{"id": "test.story", "when": "start", "text": "ok"}],
            }), encoding="utf-8")
            bad = root / "bad"
            bad.mkdir()
            (bad / "pack.json").write_text("{broken", encoding="utf-8")
            registry = PackRegistry(root)
            self.assertEqual(1, len(registry.payloads("stories")))
            self.assertEqual({"ready", "rejected"}, {p.status for p in registry.packs})


if __name__ == "__main__":
    unittest.main()
