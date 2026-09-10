# coding=utf-8
"""Map and series simulation.

Win/loss is driven by firepower plus command (赛训). Scoreboards respect saves,
so the winning side of a round usually takes 3-4 kills, not 5.
"""

from __future__ import annotations

import math
import random

from .morale import after_series, mentality_mult
from .rating import career_rating, clamp, expected_dpr, expected_rating, skill_tier
from ..world.ability import playing_ability

RNG = random.Random(20260905)

FIRE_SHARE = 0.80
COMMAND_SHARE = 0.12
MENTALITY_SHARE = 0.04
MAP_SHARE = 0.04
MAP_STRONG = 1.06
MAP_WEAK = 0.95
# Approved top-player calibration: continuous ability-based frag share, never
# a name bonus or a displayed Rating multiplier. Team victory odds are unchanged.
STAR_CURVE = 2.20
STAT_COMMAND = 0.10
ROUND_LOGIT_K = 1.65


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
    """Small reproducible match noise; 1.4's fixed 10% 1.40-1.85 spike is gone."""
    delta = clamp(float(form) - float(ability), -10.0, 10.0)
    return clamp(RNG.gauss(1.0 + delta / 200.0, 0.025), 0.92, 1.08)


def snapshot_players(team: dict, opponent: dict, map_name: str) -> list[dict]:
    mmap = map_mult(team, opponent, map_name)
    cmd = 1.0 + STAT_COMMAND * (clamp(team["command"], 0.0, 100.0) / 100.0)
    men = mentality_mult(team.get("mentality", 70))
    rows = []
    for p in team["players"]:
        p = dict(p, ability=playing_ability(p))
        form_value = float(p.get("form_delta", float(p.get("form", p["ability"])) - p["ability"]))
        p["form"] = p["ability"] + form_value
        tier = skill_tier(p["ability"])
        impact = map_impact(p["ability"], p.get("form", p["ability"] + form_value))
        effective = clamp(p["ability"] + 0.5 * form_value, 45, 100)
        rows.append(
            {
                "player_id": p.get("player_id", ""),
                "name": p["name"],
                "role": p.get("role") or "rifle",
                "ability": p["ability"],
                "tier": tier.name,
                "effective": effective,
                "fire": effective,
                "frag": ((effective / 70.0) ** STAR_CURVE)
                * impact
                * mmap
                * cmd
                * tier.floor
                * (0.97 + 0.03 * men),
            }
        )
    return rows


def team_score(rows: list[dict], command: float, mentality: float = 70.0, map_fit: float = 65.0) -> tuple[float, float, float]:
    fire = sum(r["fire"] for r in rows) / max(1, len(rows))
    score = (FIRE_SHARE * fire + COMMAND_SHARE * clamp(command, 0, 100)
             + MENTALITY_SHARE * clamp(mentality, 0, 100) + MAP_SHARE * clamp(map_fit, 0, 100))
    return score, fire, command


def round_kills() -> tuple[int, int]:
    """Kills for (round winner, round loser). Half the rounds someone saves."""
    if RNG.random() < 0.50:
        saved = RNG.randint(1, 2)
        return 5 - saved, RNG.randint(1, 2)
    return 5, RNG.randint(2, 3)


def _weighted_sample(rows: list[dict], count: int, key) -> list[dict]:
    pool, out = list(rows), []
    for _ in range(min(count, len(pool))):
        weights = [max(0.01, float(key(row))) for row in pool]
        picked = RNG.choices(pool, weights=weights, k=1)[0]
        pool.remove(picked)
        out.append(picked)
    return out


def play_round_event_stream(rows_a: list[dict], rows_b: list[dict], p_a: float) -> tuple[int, int, list[dict], dict[str, dict]]:
    """Simulate coherent per-round events, then derive the box score from them."""
    all_rows = rows_a + rows_b
    stats = {
        r["name"]: {
            "k": 0, "d": 0, "a": 0, "damage": 0, "kast_rounds": 0,
            "survived_rounds": 0, "traded_deaths": 0,
            "opening_kills": 0, "opening_deaths": 0,
        }
        for r in all_rows
    }
    events: list[dict] = []
    score_a = score_b = 0

    def one_round(number: int) -> None:
        nonlocal score_a, score_b
        a_wins = RNG.random() < p_a
        score_a += int(a_wins)
        score_b += int(not a_wins)
        win_k, lose_k = round_kills()
        deaths_a, deaths_b = (lose_k, win_k) if a_wins else (win_k, lose_k)
        dead_a = _weighted_sample(rows_a, deaths_a, lambda r: expected_dpr(r["ability"]))
        dead_b = _weighted_sample(rows_b, deaths_b, lambda r: expected_dpr(r["ability"]))
        raw: list[tuple[dict, dict, str, str]] = []
        for victim in dead_b:
            raw.append((RNG.choices(rows_a, weights=[r["frag"] for r in rows_a], k=1)[0], victim, "a", "b"))
        for victim in dead_a:
            raw.append((RNG.choices(rows_b, weights=[r["frag"] for r in rows_b], k=1)[0], victim, "b", "a"))
        RNG.shuffle(raw)
        flags = {r["name"]: {"kill": False, "assist": False, "dead": False, "traded": False} for r in all_rows}
        pending: list[tuple[str, str, str, int]] = []
        for order, (killer, victim, killer_side, victim_side) in enumerate(raw):
            # A teammate can trade a death when that death's killer dies within
            # the next two simulated engagements (the event clock is <=5 sec).
            for original_victim, original_killer, original_side, at in pending:
                if victim["name"] == original_killer and killer_side == original_side and order - at <= 2:
                    flags[original_victim]["traded"] = True
                    stats[original_victim]["traded_deaths"] += 1
            assister = None
            teammates = [r for r in (rows_a if killer_side == "a" else rows_b) if r is not killer]
            if teammates and RNG.random() < 0.42:
                assister = RNG.choice(teammates)
            damage = RNG.randint(96, 125)
            stats[killer["name"]]["k"] += 1
            stats[killer["name"]]["damage"] += damage
            stats[victim["name"]]["d"] += 1
            flags[killer["name"]]["kill"] = True
            flags[victim["name"]]["dead"] = True
            if assister:
                stats[assister["name"]]["a"] += 1
                stats[assister["name"]]["damage"] += RNG.randint(15, 45)
                flags[assister["name"]]["assist"] = True
            if order == 0:
                stats[killer["name"]]["opening_kills"] += 1
                stats[victim["name"]]["opening_deaths"] += 1
            pending.append((victim["name"], killer["name"], victim_side, order))
            events.append({"round": number, "type": "kill", "killer": killer["name"], "victim": victim["name"], "assister": assister["name"] if assister else "", "damage": damage})
        # Non-lethal damage is part of the same ledger, not reverse-engineered ADR.
        for _ in range(RNG.randint(3, 8)):
            side = RNG.choice(("a", "b"))
            attacker = RNG.choice(rows_a if side == "a" else rows_b)
            victim = RNG.choice(rows_b if side == "a" else rows_a)
            damage = RNG.randint(5, 45)
            stats[attacker["name"]]["damage"] += damage
            events.append({"round": number, "type": "hurt", "attacker": attacker["name"], "victim": victim["name"], "damage": damage})
        for row in all_rows:
            flag = flags[row["name"]]
            if not flag["dead"]:
                stats[row["name"]]["survived_rounds"] += 1
            if flag["kill"] or flag["assist"] or not flag["dead"] or flag["traded"]:
                stats[row["name"]]["kast_rounds"] += 1
        events.append({"round": number, "type": "round_end", "winner": "a" if a_wins else "b"})

    while score_a < 13 and score_b < 13:
        one_round(score_a + score_b + 1)
        if score_a + score_b >= 24:
            break
    while score_a == score_b:
        for _ in range(6):
            one_round(score_a + score_b + 1)
    return score_a, score_b, events, stats


def event_box_score(rows: list[dict], stats: dict[str, dict], rounds: int) -> list[dict]:
    lines = []
    for row in rows:
        st = stats[row["name"]]
        lines.append({
            "player_id": row.get("player_id", ""), "name": row["name"],
            "role": row.get("role") or "",
            "ability": row["ability"], "tier": row["tier"],
            **st,
            "kpr": round(st["k"] / max(1, rounds), 3),
            "adr": round(st["damage"] / max(1, rounds), 2),
            "kast": round(st["kast_rounds"] / max(1, rounds), 4),
            "rating": career_rating(st["k"], st["d"], st["a"], st["damage"], st["kast_rounds"], rounds),
        })
    return sorted(lines, key=lambda x: (-x["rating"], -x["k"]))


def validate_rosters(team_a: dict, team_b: dict) -> None:
    """Reject identity collisions before drawing RNG or writing a box score.

    The legacy simulation ledger still keys names. Distinct IDs with the same
    nickname are therefore also rejected, rather than merging their numbers.
    Missing IDs remain compatible with old engine-only fixtures.
    """
    groups = [team.get('players') or [] for team in (team_a, team_b)]
    if any(len(group) != 5 for group in groups):
        raise ValueError("比赛需要双方各五名选手，请检查阵容。")
    names, ids = set(), set()
    for player in groups[0] + groups[1]:
        name = str(player.get('name') or '').strip().casefold()
        pid = player.get('player_id')
        if not name or name in names or (pid and pid in ids):
            raise ValueError(f"比赛阵容存在重复或无效选手：{player.get('name') or '未命名'}，请检查双方名单。")
        names.add(name)
        if pid:
            ids.add(pid)


def play_map(team_a: dict, team_b: dict, map_name: str) -> dict:
    validate_rosters(team_a, team_b)
    rows_a = snapshot_players(team_a, team_b, map_name)
    rows_b = snapshot_players(team_b, team_a, map_name)
    def fit(team: dict) -> float:
        base = float(team.get("map_adaptation", 65))
        if map_name in team.get("strong_maps", []):
            base += 25
        elif map_name in team.get("weak_maps", []):
            base -= 25
        return clamp(base, 0, 100)

    fit_a, fit_b = fit(team_a), fit(team_b)
    score_a, fire_a, cmd_a = team_score(rows_a, team_a["command"], team_a.get("mentality", 70), fit_a)
    score_b, fire_b, cmd_b = team_score(rows_b, team_b["command"], team_b.get("mentality", 70), fit_b)
    if team_a.get("throwing"):
        score_a *= 0.40
    if team_b.get("throwing"):
        score_b *= 0.40
    p_a = 1.0 / (1.0 + math.exp(-(score_a - score_b) / 32.0))
    s_a, s_b, events, ledger = play_round_event_stream(rows_a, rows_b, p_a)
    rounds = s_a + s_b
    return {
        "source": "sim",
        "map": map_name,
        "score": f"{s_a}-{s_b}",
        "rounds": rounds,
        "winner": team_a["name"] if s_a > s_b else team_b["name"],
        "fire": [round(fire_a, 2), round(fire_b, 2)],
        "command": [int(cmd_a), int(cmd_b)],
        "mentality": [round(team_a.get("mentality", 70), 1), round(team_b.get("mentality", 70), 1)],
        "schema_version": 2,
        "events": events,
        "players": {
            team_a["name"]: event_box_score(rows_a, ledger, rounds),
            team_b["name"]: event_box_score(rows_b, ledger, rounds),
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
                    f"{team}|{p.get('player_id') or p['name']}",
                    {"team": team, "player_id": p.get("player_id", ""), "player": p["name"], "k": 0, "d": 0, "a": 0, "damage": 0, "kast_rounds": 0, "rounds": 0},
                )
                row["k"] += p["k"]
                row["d"] += p["d"]
                row["a"] += p["a"]
                row["damage"] += p.get("damage", 0)
                row["kast_rounds"] += p.get("kast_rounds", p.get("kast", 0) * mp["rounds"])
                row["rounds"] += mp["rounds"]
    rows = []
    for row in store.values():
        rec = dict(row)
        rec["kpr"] = round(row["k"] / max(1, row["rounds"]), 3)
        rec["adr"] = round(row["damage"] / max(1, row["rounds"]), 2)
        rec["kast"] = round(row["kast_rounds"] / max(1, row["rounds"]), 4)
        rec["rating"] = career_rating(row["k"], row["d"], row["a"], row["damage"], row["kast_rounds"], row["rounds"])
        rows.append(rec)
    rows.sort(key=lambda x: (-x["rating"], -x["kpr"]))
    return rows


def update_player_forms(teams: list[dict], ratings: list[dict]) -> None:
    by_id = {row.get("player_id") or row["player"]: float(row["rating"]) for row in ratings}
    for team in teams:
        for player in team.get("players") or []:
            identity = player.get("player_id") or player["name"]
            if identity not in by_id:
                continue
            old = float(player.get("form_delta") or 0)
            signal = clamp(25.0 * (by_id[identity] - expected_rating(player["ability"])), -10, 10)
            player["form_delta"] = round(0.8 * old + 0.2 * signal, 2)
            player["form"] = round(float(player["ability"]) + player["form_delta"], 2)


def play_series(team_a: dict, team_b: dict, maps: list[str], stage: str, best_of: int = 3) -> dict:
    validate_rosters(team_a, team_b)
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
    ratings = series_ratings(played)
    update_player_forms([team_a, team_b], ratings)
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
        "ratings": ratings,
    }
