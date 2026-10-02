# coding=utf-8
"""Career simplified VRS: quality of recent wins, not unlimited attendance.

This is NOT Valve's complete model. Valve considers best recent results in
several factors plus head-to-head changes; it has no universal total-point cap.
Our transparent game model counts ten wins over 180 days, at most three from
one event. A decaying opening seed is a floor until real results replace it.
Source: github.com/ValveSoftware/counter-strike_regional_standings
"""

from __future__ import annotations

import math
from datetime import date, datetime

FULL_DAYS = 30
DEAD_DAYS = 365
HALF_LIFE = 150.0
RESULT_DAYS = 180
BEST_RESULTS = 10
MAX_WINS_PER_EVENT = 3
MODEL_VERSION = 'career-vrs-2'

# Displayed points = FLOOR + K * earned ** GAMMA.
#
# Retain the familiar display curve. These are game points, not a claim that
# the simplified standings reproduce today's official Valve table.
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
        return self._summaries({team_id}, as_of)[team_id]['earned']

    def _summaries(self, team_ids: set[str], as_of: str) -> dict[str, dict]:
        """One pass; never keep a cache that can become stale after a transfer."""
        today = parse_date(as_of)
        buckets = {key: [] for key in team_ids}
        seeds = {key: 0.0 for key in team_ids}
        ages = {}
        for index, row in enumerate(self.results):
            key = row.get('team')
            if key not in buckets:
                continue
            stamp = row['date']
            if stamp not in ages:
                ages[stamp] = (today - parse_date(stamp)).days
            age = ages[stamp]
            if age < 0:
                continue  # Future results never contribute to a past ranking.
            value = float(row.get('points') or 0)
            if not math.isfinite(value) or value <= 0:
                continue
            if row.get('kind') == 'seed':
                seeds[key] = max(seeds[key], value * decay(age))
                continue
            if age >= RESULT_DAYS or row.get('kind') == 'loss' or row.get('won') is False:
                continue
            event = (stamp[:4], str(row.get('event') or f'legacy-{index}'))
            buckets[key].append((value * decay(age), event, index))
        out = {}
        for key, candidates in buckets.items():
            selected = []
            event_counts = {}
            for value, event, index in sorted(candidates, key=lambda x: (-x[0], x[2])):
                if event_counts.get(event, 0) >= MAX_WINS_PER_EVENT:
                    continue
                selected.append((value, event, index))
                event_counts[event] = event_counts.get(event, 0) + 1
                if len(selected) == BEST_RESULTS:
                    break
            performance = sum(r[0] for r in selected)
            out[key] = dict(earned=max(seeds[key], performance), seed=seeds[key],
                performance=performance, counted_wins=len(selected),
                counted_events=len(event_counts),
                replacement_threshold=selected[-1][0] if len(selected) == BEST_RESULTS else 0.0,
                model=MODEL_VERSION, window_days=RESULT_DAYS,
                best_results=BEST_RESULTS, max_wins_per_event=MAX_WINS_PER_EVENT)
        return out

    def participation_value(self, team_id: str, as_of: str) -> dict:
        """Explain the counted sample and the weakest result an event can replace."""
        return self._summaries({team_id}, as_of)[team_id]

    def can_improve(self, team_id: str, weight: float, as_of: str) -> bool:
        # Use the best possible opponent share. We decline for zero ranking
        # utility only when even that upper bound cannot enter the best ten.
        summary = self.participation_value(team_id, as_of)
        return summary['counted_wins'] < BEST_RESULTS or float(weight) * 305.0 > summary['replacement_threshold']

    def live(self, team_id: str, as_of: str) -> float:
        return points_from_earned(self.earned(team_id, as_of))

    def table(self, teams: list[dict], as_of: str) -> list[dict]:
        totals = self._summaries({t['id'] for t in teams}, as_of)
        rows = [
            {
                "id": t["id"],
                "name": t["name"],
                "region": t["region"],
                "vrs": points_from_earned(totals[t['id']]['earned']),
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
                "points": 0.0,
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
