"""Deterministic 100-season balance report for the 1.5 simulation engine.

Run from the repository root with the bundled/system Python. ``--enforce``
returns non-zero when an acceptance band misses its target.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cs2career.engine.match import RNG, play_series
from cs2career.league.season import Season
from cs2career.world import MAPS


def _strength(team: dict) -> float:
    players = sum(float(p["ability"]) + .5 * float(p.get("form_delta") or 0) for p in team["players"]) / 5
    return .80 * players + .12 * team["command"] + .04 * team.get("mentality", 70) + .04 * 65


def _one_year(seed: int) -> dict:
    random.seed(seed)
    RNG.seed(seed)
    season = Season(2026, "2026")
    opening_rank = {t["name"]: int(t["world_rank"]) for t in season.teams}
    strengths = {t["name"]: _strength(t) for t in season.teams}
    guard = 0
    while not all(event.get("status") == "done" for event in season.events):
        season.next_stage()
        guard += 1
        if guard > 500:
            raise RuntimeError("season did not finish")
    wins = {name: 0 for name in opening_rank}
    games = {name: 0 for name in opening_rank}
    top10_upset = top10_games = top10_bo3_upset = top10_bo3_games = 0
    top30_upset = top30_games = top30_bo3_upset = top30_bo3_games = 0
    champ_top10 = top_champs = 0
    signature: list[str] = []
    for event in season.events:
        if event.get("type") in ("t1", "major") and event.get("champion"):
            top_champs += 1
            champ_top10 += opening_rank.get(event["champion"], 99) <= 10
        for match in event.get("matches") or []:
            winner = match.get("winner")
            a, b = match.get("team_a"), match.get("team_b")
            if not winner or not a or not b or b == "BYE":
                continue
            signature.append(f"{event['id']}|{match['id']}|{winner}|{match.get('series')}")
            games[a] += 1
            games[b] += 1
            wins[winner] += 1
            # Upsets are defined by the ranking that existed when the series
            # began. Opening rank is only a fallback for old fixture data.
            ra = int(match.get("rank_a_at_match") or opening_rank[a])
            rb = int(match.get("rank_b_at_match") or opening_rank[b])
            favourite = a if ra < rb else b
            lower = b if favourite == a else a
            best_of = int(match.get("best_of") or 1)
            if min(ra, rb) <= 10 < max(ra, rb):
                top10_games += 1
                top10_upset += winner != favourite
                if best_of >= 3:
                    top10_bo3_games += 1
                    top10_bo3_upset += winner != favourite
            if min(ra, rb) <= 30 < max(ra, rb):
                top30_games += 1
                top30_upset += winner != favourite
                if best_of >= 3:
                    top30_bo3_games += 1
                    top30_bo3_upset += winner != favourite
    return {
        "seed": seed,
        "signature": hashlib.sha256("\n".join(signature).encode()).hexdigest(),
        "top10_upset": top10_upset, "top10_games": top10_games,
        "top10_bo3_upset": top10_bo3_upset, "top10_bo3_games": top10_bo3_games,
        "top30_upset": top30_upset, "top30_games": top30_games,
        "top30_bo3_upset": top30_bo3_upset, "top30_bo3_games": top30_bo3_games,
        "champ_top10": champ_top10, "top_champs": top_champs,
        "wins": wins, "games": games, "strengths": strengths,
    }


def _team(name: str, ability: float) -> dict:
    return {"name": name, "world_rank": 1, "command": 70, "mentality": 70,
            "strong_maps": [], "weak_maps": [], "players": [
                {"player_id": f"p_{name}_{i}", "name": f"{name}{i}", "ability": ability,
                 "form": ability, "form_delta": 0, "role": "rifle"} for i in range(5)]}


def _pearson(xs: list[float], ys: list[float]) -> float:
    ax, ay = sum(xs) / len(xs), sum(ys) / len(ys)
    num = sum((x - ax) * (y - ay) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - ax) ** 2 for x in xs) * sum((y - ay) ** 2 for y in ys))
    return num / den if den else 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260900)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 2))
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()
    seeds = list(range(args.seed, args.seed + args.seasons))
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        years = list(pool.map(_one_year, seeds))
    repeat = _one_year(seeds[0])
    top10_u = sum(x["top10_upset"] for x in years)
    top10_n = sum(x["top10_games"] for x in years)
    top10_bo3_u = sum(x["top10_bo3_upset"] for x in years)
    top10_bo3_n = sum(x["top10_bo3_games"] for x in years)
    top30_u = sum(x["top30_upset"] for x in years)
    top30_n = sum(x["top30_games"] for x in years)
    top30_bo3_u = sum(x["top30_bo3_upset"] for x in years)
    top30_bo3_n = sum(x["top30_bo3_games"] for x in years)
    champ_u = sum(x["champ_top10"] for x in years)
    champ_n = sum(x["top_champs"] for x in years)
    names = list(years[0]["strengths"])
    strengths = [years[0]["strengths"][name] for name in names]
    rates = [sum(x["wins"][name] for x in years) / max(1, sum(x["games"][name] for x in years)) for name in names]

    gap_rates = {}
    for gap in (0, 5, 10):
        won = 0
        for seed in seeds[:100]:
            RNG.seed(seed)
            won += play_series(_team("A", 80 + gap), _team("B", 80), MAPS[:7], "regression", 3)["winner"] == "A"
        gap_rates[str(gap)] = won / min(100, len(seeds))
    report = {
        "seasons": len(years),
        "equal_bo3": gap_rates["0"], "plus5_bo3": gap_rates["5"], "plus10_bo3": gap_rates["10"],
        "top10_external_upset": top10_u / max(1, top10_n),
        "top10_external_upset_bo3_plus": top10_bo3_u / max(1, top10_bo3_n),
        "top30_external_upset": top30_u / max(1, top30_n),
        "top30_external_upset_bo3_plus": top30_bo3_u / max(1, top30_bo3_n),
        "top_event_champion_from_opening_top10": champ_u / max(1, champ_n),
        "opening_strength_year_winrate_correlation": _pearson(strengths, rates),
        "same_seed_reproduces": repeat["signature"] == years[0]["signature"],
        "samples": {
            "top10_external": top10_n, "top10_external_bo3_plus": top10_bo3_n,
            "top30_external": top30_n, "top30_external_bo3_plus": top30_bo3_n,
            "top_champions": champ_n,
        },
    }
    checks = {
        "equal_bo3": .48 <= report["equal_bo3"] <= .52,
        "plus5_bo3": .62 <= report["plus5_bo3"] <= .72,
        "plus10_bo3": .80 <= report["plus10_bo3"] <= .90,
        "top10_external_upset": .15 <= report["top10_external_upset"] <= .20,
        "top30_external_upset": .08 <= report["top30_external_upset"] <= .15,
        "top_event_champion": report["top_event_champion_from_opening_top10"] >= .75,
        "correlation": report["opening_strength_year_winrate_correlation"] >= .75,
        "reproducible": report["same_seed_reproduces"],
    }
    report["checks"] = checks
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if args.enforce and not all(checks.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
