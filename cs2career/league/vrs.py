# coding=utf-8
"""Valve-style ranking points with time decay.

Scaled to real HLTV Valve points: #1 ~2060, #10 ~1680, #20 ~1400, #50 ~1000.
A loss to a strong team still pays, so Lynn Vision taking a map off Vitality
is worth something.
"""

from __future__ import annotations

import math
from datetime import date, datetime

FULL_DAYS = 30
DEAD_DAYS = 365
HALF_LIFE = 150.0

# Displayed points = FLOOR + K * earned ** GAMMA.
#
# The floor keeps a team on the board between events, and the concave exponent
# is what reproduces the real HLTV Valve spread (#1 ~2060, #10 ~1680,
# #20 ~1400, #50 ~1000) from a 40-event season. A linear map would put #1 in
# the right place and leave everyone below 20th near zero.
FLOOR = 900.0
K = 6.8
GAMMA = 0.62


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def decay(age_days: int) -> float:
    if age_days <= FULL_DAYS:
        return 1.0
    if age_days >= DEAD_DAYS:
        return 0.0
    return math.exp(-(age_days - FULL_DAYS) / HALF_LIFE)


def target_points(rank: int) -> float:
    """The curve the table is calibrated against."""
    return round(850.0 + 1210.0 * math.exp(-(max(1, rank) - 1) / 24.0), 1)


def points_from_earned(earned: float) -> float:
    return round(FLOOR + K * max(0.0, earned) ** GAMMA, 1)


def seed_points(rank: int) -> float:
    """Pre-season form, expressed in raw earned points before the curve."""
    head = max(1.0, target_points(rank) - FLOOR)
    return round((head / K) ** (1.0 / GAMMA), 1)


class VRS:
    def __init__(self) -> None:
        self.results: list[dict] = []

    def seed(self, teams: list[dict], as_of: str) -> None:
        for t in teams:
            self.results.append(
                {
                    "team": t["id"],
                    "date": as_of,
                    "points": seed_points(int(t.get("world_rank") or 50)),
                    "kind": "seed",
                    "opp": "",
                    "won": True,
                }
            )

    def earned(self, team_id: str, as_of: str) -> float:
        today = parse_date(as_of)
        total = 0.0
        for r in self.results:
            if r["team"] != team_id:
                continue
            total += r["points"] * decay((today - parse_date(r["date"])).days)
        return total

    def live(self, team_id: str, as_of: str) -> float:
        return points_from_earned(self.earned(team_id, as_of))

    def table(self, teams: list[dict], as_of: str) -> list[dict]:
        rows = [
            {
                "id": t["id"],
                "name": t["name"],
                "region": t["region"],
                "vrs": self.live(t["id"], as_of),
            }
            for t in teams
        ]
        rows.sort(key=lambda x: -x["vrs"])
        for i, row in enumerate(rows, 1):
            row["rank"] = i
        return rows

    def rank_of(self, teams: list[dict], as_of: str) -> dict[str, int]:
        return {row["name"]: row["rank"] for row in self.table(teams, as_of)}

    def award_series(self, winner: dict, loser: dict, weight: float, as_of: str, event: str) -> None:
        vw = max(80.0, self.live(winner["id"], as_of))
        vl = max(80.0, self.live(loser["id"], as_of))
        share_w = (vl + 90.0) / (vw + vl + 180.0)
        share_l = (vw + 90.0) / (vw + vl + 180.0)
        self.results.append(
            {
                "team": winner["id"],
                "date": as_of,
                "points": round(weight * (95.0 + 210.0 * share_w), 1),
                "kind": "win",
                "opp": loser["id"],
                "event": event,
                "won": True,
            }
        )
        self.results.append(
            {
                "team": loser["id"],
                "date": as_of,
                "points": round(weight * (28.0 + 110.0 * share_l), 1),
                "kind": "loss",
                "opp": winner["id"],
                "event": event,
                "won": False,
            }
        )

    def prune(self, as_of: str) -> None:
        """Drop results that no longer contribute anything."""
        today = parse_date(as_of)
        self.results = [
            r for r in self.results if (today - parse_date(r["date"])).days < DEAD_DAYS
        ]

    def to_json(self) -> list[dict]:
        return self.results

    @classmethod
    def from_json(cls, rows: list[dict]) -> "VRS":
        obj = cls()
        obj.results = rows
        return obj
