# coding=utf-8
"""Map and series simulation.

Win/loss is driven by firepower plus command (赛训). Scoreboards respect saves,
so the winning side of a round usually takes 3-4 kills, not 5.
"""

from __future__ import annotations

import math
import random

from .morale import after_series, mentality_mult
from .rating import allocate_ints, clamp, expected_dpr, kda_rating, skill_tier

RNG = random.Random(20260905)

FIRE_SHARE = 0.76
COMMAND_SHARE = 0.24
MAP_STRONG = 1.06
MAP_WEAK = 0.95
STAR_CURVE = 1.24
STAT_COMMAND = 0.10
ROUND_LOGIT_K = 1.65


def form_roll(form: float) -> float:
    t = clamp(form, 0.0, 100.0) / 100.0
    low = 0.60 + 0.30 * t
    high = 1.05 + 0.05 * t
    if form >= 80:
        return clamp(RNG.gauss((low + high) / 2.0, 0.025), low, high)
    if form >= 50:
        return clamp(RNG.gauss((low + high) / 2.0 * 0.98, 0.045), low, high)
    return RNG.triangular(low, high, low + (high - low) * 0.28)


def map_mult(team: dict, opponent: dict, map_name: str) -> float:
    a_strong = map_name in team["strong_maps"]
    a_weak = map_name in team["weak_maps"]
    b_strong = map_name in opponent["strong_maps"]
    b_weak = map_name in opponent["weak_maps"]
    if a_strong and not b_strong:
        return MAP_STRONG
    if a_weak and not b_weak:
        return MAP_WEAK
    return 1.0


def map_impact(ability: float, form: float) -> float:
    pop = RNG.random()
    if pop < 0.10:
        return RNG.uniform(1.40, 1.85)
    if pop < 0.20:
        return RNG.uniform(0.72, 0.90)
    tier = skill_tier(ability)
    form_t = clamp(form, 0.0, 100.0) / 100.0
    carry_p = tier.carry_p * (0.70 + 0.30 * form_t)
    roll = RNG.random()
    if roll < carry_p:
        return RNG.uniform(*tier.hot)
    if roll < carry_p + tier.cold_p:
        return RNG.uniform(*tier.cold)
    return RNG.uniform(*tier.normal)


def snapshot_players(team: dict, opponent: dict, map_name: str) -> list[dict]:
    mmap = map_mult(team, opponent, map_name)
    cmd = 1.0 + STAT_COMMAND * (clamp(team["command"], 0.0, 100.0) / 100.0)
    men = mentality_mult(team.get("mentality", 70))
    rows = []
    for p in team["players"]:
        form = form_roll(p["form"])
        tier = skill_tier(p["ability"])
        impact = map_impact(p["ability"], p["form"])
        rows.append(
            {
                "name": p["name"],
                "ability": p["ability"],
                "tier": tier.name,
                "fire": (p["ability"] / 100.0) * form * mmap,
                "frag": ((p["ability"] / 70.0) ** STAR_CURVE)
                * form
                * impact
                * mmap
                * cmd
                * tier.floor
                * (0.97 + 0.03 * men),
            }
        )
    return rows


def team_score(rows: list[dict], command: float, mentality: float = 70.0) -> tuple[float, float, float]:
    fire = sum(r["fire"] for r in rows)
    cmd = clamp(command, 0.0, 100.0) / 100.0
    score = (FIRE_SHARE * fire + COMMAND_SHARE * (cmd * 5.0)) * mentality_mult(mentality)
    return score, fire, command


def round_kills() -> tuple[int, int]:
    """Kills for (round winner, round loser). Half the rounds someone saves."""
    if RNG.random() < 0.50:
        saved = RNG.randint(1, 2)
        return 5 - saved, RNG.randint(1, 2)
    return 5, RNG.randint(2, 3)


def play_rounds(p_a: float) -> tuple[int, int, int, int]:
    a = b = ka = kb = 0

    def one_round() -> None:
        nonlocal a, b, ka, kb
        win_k, lose_k = round_kills()
        if RNG.random() < p_a:
            a += 1
            ka += win_k
            kb += lose_k
        else:
            b += 1
            kb += win_k
            ka += lose_k

    while a < 13 and b < 13:
        one_round()
        if a + b >= 24:
            break
    while a == b:
        for _ in range(6):
            one_round()
    return a, b, ka, kb


def allocate_deaths(weights: list[float], total: int, rounds: int) -> list[int]:
    total = min(total, rounds * len(weights))
    deaths = allocate_ints(weights, total)
    overflow = 0
    room = []
    for i, d in enumerate(deaths):
        if d > rounds:
            overflow += d - rounds
            deaths[i] = rounds
        else:
            room.append(i)
    idx = 0
    while overflow > 0 and room:
        i = room[idx % len(room)]
        if deaths[i] < rounds:
            deaths[i] += 1
            overflow -= 1
            if deaths[i] >= rounds:
                room = [j for j in room if deaths[j] < rounds]
                idx = 0
                continue
        idx += 1
    return deaths


def box_score(rows: list[dict], kills: int, deaths: int, rounds: int) -> list[dict]:
    kill_n = allocate_ints([max(0.05, r["frag"]) for r in rows], kills)
    death_w = [max(0.35, expected_dpr(r["ability"]) * RNG.uniform(0.92, 1.08)) for r in rows]
    death_n = allocate_deaths(death_w, deaths, rounds)
    lines = []
    for r, k, d in zip(rows, kill_n, death_n):
        assists = max(0, int(round(k * RNG.uniform(0.22, 0.40) + RNG.uniform(0, 1.4))))
        lines.append(
            {
                "name": r["name"],
                "ability": r["ability"],
                "tier": r["tier"],
                "k": k,
                "d": d,
                "a": assists,
                "kpr": round(k / max(1, rounds), 3),
                "rating": kda_rating(k, d, assists, rounds),
            }
        )
    lines.sort(key=lambda x: (-x["rating"], -x["k"]))
    return lines


def play_map(team_a: dict, team_b: dict, map_name: str) -> dict:
    rows_a = snapshot_players(team_a, team_b, map_name)
    rows_b = snapshot_players(team_b, team_a, map_name)
    score_a, fire_a, cmd_a = team_score(rows_a, team_a["command"], team_a.get("mentality", 70))
    score_b, fire_b, cmd_b = team_score(rows_b, team_b["command"], team_b.get("mentality", 70))
    if team_a.get("throwing"):
        score_a *= 0.40
    if team_b.get("throwing"):
        score_b *= 0.40
    mean = max(0.5, (score_a + score_b) / 2.0)
    p_a = 1.0 / (1.0 + math.exp(-ROUND_LOGIT_K * (score_a - score_b) / mean))
    s_a, s_b, k_a, k_b = play_rounds(p_a)
    rounds = s_a + s_b
    return {
        "map": map_name,
        "score": f"{s_a}-{s_b}",
        "rounds": rounds,
        "winner": team_a["name"] if s_a > s_b else team_b["name"],
        "fire": [round(fire_a, 2), round(fire_b, 2)],
        "command": [int(cmd_a), int(cmd_b)],
        "mentality": [round(team_a.get("mentality", 70), 1), round(team_b.get("mentality", 70), 1)],
        "players": {
            team_a["name"]: box_score(rows_a, k_a, k_b, rounds),
            team_b["name"]: box_score(rows_b, k_b, k_a, rounds),
        },
    }


def map_comfort(team: dict, map_name: str) -> float:
    if map_name in team.get("strong_maps", []):
        return 1.2
    if map_name in team.get("weak_maps", []):
        return -1.1
    return 0.05


def _noise(command: float) -> float:
    chaos = max(0.08, 1.0 - clamp(command, 0.0, 100.0) / 100.0)
    return RNG.gauss(0.0, 0.28 * chaos)


def _ban_value(me: dict, opp: dict, map_name: str) -> float:
    # Ban their permanent, especially when it is not also yours.
    return map_comfort(opp, map_name) - 0.45 * map_comfort(me, map_name) + _noise(me["command"])


def _pick_value(me: dict, opp: dict, map_name: str) -> float:
    return map_comfort(me, map_name) - 0.65 * map_comfort(opp, map_name) + _noise(me["command"])


def veto_maps(team_a: dict, team_b: dict, maps: list[str], best_of: int) -> dict:
    """BO3: ban ban / pick pick / ban ban / spare bans / leftover decider.

    BO1: alternating bans down to one map. Higher seed (team_a) always starts.
    """
    pool = list(maps)
    steps: list[dict] = []
    order: list[str] = []

    if best_of <= 1:
        plan = [("ban", team_a if i % 2 == 0 else team_b) for i in range(len(pool) - 1)]
    else:
        plan = [
            ("ban", team_a),
            ("ban", team_b),
            ("pick", team_a),
            ("pick", team_b),
            ("ban", team_a),
            ("ban", team_b),
        ]
        plan += [("ban", team_a if i % 2 == 0 else team_b) for i in range(max(0, len(pool) - 7))]

    for action, team in plan:
        if len(pool) <= 1:
            break
        opp = team_b if team is team_a else team_a
        if action == "ban":
            choice = max(pool, key=lambda m: _ban_value(team, opp, m))
            pool.remove(choice)
            steps.append({"team": team["name"], "action": "ban", "map": choice})
            continue
        choice = max(pool, key=lambda m: _pick_value(team, opp, m))
        pool.remove(choice)
        order.append(choice)
        steps.append({"team": team["name"], "action": "pick", "map": choice, "play": len(order)})

    decider = pool[0]
    order.append(decider)
    steps.append({"team": None, "action": "decider", "map": decider, "play": len(order)})
    return {"steps": steps, "order": order, "best_of": best_of}


def series_ratings(played: list[dict]) -> list[dict]:
    store: dict[str, dict] = {}
    for mp in played:
        for team, lines in mp["players"].items():
            for p in lines:
                row = store.setdefault(
                    f"{team}|{p['name']}",
                    {"team": team, "player": p["name"], "k": 0, "d": 0, "a": 0, "rounds": 0},
                )
                row["k"] += p["k"]
                row["d"] += p["d"]
                row["a"] += p["a"]
                row["rounds"] += mp["rounds"]
    rows = []
    for row in store.values():
        rec = dict(row)
        rec["kpr"] = round(row["k"] / max(1, row["rounds"]), 3)
        rec["rating"] = kda_rating(row["k"], row["d"], row["a"], row["rounds"])
        rows.append(rec)
    rows.sort(key=lambda x: (-x["rating"], -x["kpr"]))
    return rows


def play_series(team_a: dict, team_b: dict, maps: list[str], stage: str, best_of: int = 3) -> dict:
    veto = veto_maps(team_a, team_b, maps, best_of)
    need = best_of // 2 + 1
    played = []
    wins = {team_a["name"]: 0, team_b["name"]: 0}
    for map_name in veto["order"]:
        result = play_map(team_a, team_b, map_name)
        played.append(result)
        wins[result["winner"]] += 1
        if max(wins.values()) >= need:
            break
    winner = team_a["name"] if wins[team_a["name"]] > wins[team_b["name"]] else team_b["name"]
    after_series(team_a, team_b, {"winner": winner, "stage": stage})
    return {
        "stage": stage,
        "best_of": best_of,
        "team_a": team_a["name"],
        "team_b": team_b["name"],
        "series": f"{wins[team_a['name']]}-{wins[team_b['name']]}",
        "winner": winner,
        "maps": played,
        "veto": veto,
        "ratings": series_ratings(played),
    }
