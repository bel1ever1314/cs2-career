# coding=utf-8
"""HLTV seven-axis personal ability + eighth-axis command stamp.

Gun ability uses the six frag axes (utility is team command only).
Team command is the mean of the five utilities. The command axis is a
stamp: IGL 50%, the other four split 50%.
"""

from __future__ import annotations

import json

from ..paths import data_file

GUN_AXES = ("firepower", "entrying", "trading", "opening", "clutching", "sniping")
AXES = GUN_AXES + ("utility",)
ALL_AXES = AXES + ("command",)
AXIS_LABEL = {
    "firepower": "火力",
    "entrying": "突破",
    "trading": "补枪",
    "opening": "首杀",
    "clutching": "残局",
    "sniping": "狙击",
    "utility": "道具",
    "command": "指挥",
}
RIFLE_W = {
    "firepower": 28,
    "entrying": 18,
    "trading": 22,
    "opening": 16,
    "clutching": 12,
    "sniping": 4,
}
ENTRY_W = {
    "firepower": 24,
    "entrying": 24,
    "opening": 20,
    "trading": 18,
    "clutching": 10,
    "sniping": 4,
}
IGL_W = {
    "firepower": 18,
    "entrying": 10,
    "opening": 10,
    "trading": 28,
    "clutching": 18,
    "sniping": 4,
}
# Free-roamer: finishing isolated rounds and trading matter more than entry.
# Keep the legacy rifle/entry/IGL formulas and AWP bonus unchanged.
LURK_W = dict(firepower=24, entrying=8, trading=26, opening=10, clutching=28, sniping=4)
AWP_SNIPE_BONUS = 0.06
STRETCH_MIN = 16.56
STRETCH_MAX = 79.08
COMMAND_STAMP_MULT = 2.2
SHAPE = {
    "awp":     {"firepower": 1.02, "entrying": 0.88, "trading": 0.96, "opening": 1.00, "clutching": 1.04, "sniping": 1.12, "utility": 0.94},
    "entry":   {"firepower": 1.04, "entrying": 1.10, "trading": 0.96, "opening": 1.08, "clutching": 0.94, "sniping": 0.70, "utility": 0.90},
    "rifle":   {"firepower": 1.02, "entrying": 0.98, "trading": 1.02, "opening": 0.98, "clutching": 1.00, "sniping": 0.74, "utility": 0.96},
    "lurk":    {"firepower": 0.98, "entrying": 0.90, "trading": 1.04, "opening": 0.92, "clutching": 1.06, "sniping": 0.72, "utility": 1.00},
    "support": {"firepower": 0.92, "entrying": 0.88, "trading": 1.08, "opening": 0.90, "clutching": 0.96, "sniping": 0.68, "utility": 1.10},
    "igl":     {"firepower": 0.90, "entrying": 0.86, "trading": 1.04, "opening": 0.88, "clutching": 1.00, "sniping": 0.66, "utility": 1.08},
}

_CACHE: dict[str, dict] | None = None


def clamp(n: float, lo: float = 1, hi: float = 100) -> int:
    return int(max(lo, min(hi, round(n))))


def _weights(role: str) -> dict[str, float]:
    if role == "igl":
        return IGL_W
    if role == "entry":
        return ENTRY_W
    if role == "lurk":
        return LURK_W
    return RIFLE_W


def gun_score(stats: dict, role: str) -> float:
    w = _weights(role)
    s = sum((w[k] / 100.0) * float(stats.get(k) or 0) for k in GUN_AXES)
    if role == "awp":
        s += AWP_SNIPE_BONUS * float(stats.get("sniping") or 0)
    return s


def stretch_gun(score: float) -> float:
    span = STRETCH_MAX - STRETCH_MIN
    if span <= 0:
        return 69.0
    raw = 40.0 + 58.0 * (score - STRETCH_MIN) / span
    return round(max(40.0, min(98.0, raw)), 1)


def unstretch(ability: float) -> float:
    t = (max(40.0, min(98.0, float(ability))) - 40.0) / 58.0
    return STRETCH_MIN + t * (STRETCH_MAX - STRETCH_MIN)


def ability_of(stats: dict, role: str) -> float:
    """Current-position ability, calibrated to the player's original strength.

    Compare UNCLIPPED weighted scores: clipping each role first would make
    high-axis stars identical in every role. The anchor never moves on a role
    switch, so switching back is lossless and cannot farm permanent ability.
    Bare legacy axes still support generation/fit_axes without a calibration.
    """
    if stats.get("role_reference_score") is not None and stats.get("ability") is not None:
        delta = (gun_score(stats, role) - float(stats["role_reference_score"])) * 58 / (STRETCH_MAX - STRETCH_MIN)
        return round(max(40.0, min(100.0, float(stats["ability"]) + delta)), 1)
    return stretch_gun(gun_score(stats, role))


def calibrate_role(stats: dict, role: str, baseline: float) -> None:
    """Stamp a new/aged baseline. Never call this merely to change positions."""
    stats["ability"] = round(float(baseline), 1)
    stats["role_reference"] = role
    stats["role_reference_score"] = gun_score(stats, role)


def ensure_role_calibration(player: dict) -> bool:
    """Upgrade live v2 rows in memory, preserving their CURRENT saved ability.

    Old saves may contain stale stats.ability after aging; the live row wins.
    Historical match snapshots are never passed here or recalculated.
    """
    stats = player.get("stats")
    if not stats or stats.get("role_reference_score") is not None:
        return False
    role = player.get("role") or "rifle"
    calibrate_role(stats, role, float(player.get("ability", stats.get("ability", 70))))
    if player.get("form_delta") is None:
        player["form_delta"] = max(-10.0, min(10.0,
            float(player.get("form", player["ability"])) - float(player["ability"])))
    return True


def refresh_player_ability(player: dict) -> None:
    ensure_role_calibration(player)
    stats = player.get("stats")
    if not stats:
        return
    player["ability"] = ability_of(stats, player.get("role") or "rifle")
    player["long_term_ability"] = ability_of(stats, stats["role_reference"])
    player["form"] = player["ability"] + float(player.get("form_delta") or 0)


def playing_ability(player: dict) -> float:
    """Read-only boundary for simulation/CS2; uncalibrated snapshots stay intact."""
    stats = player.get("stats") or {}
    if stats.get("role_reference_score") is not None:
        return ability_of(stats, player.get("role") or "rifle")
    return float(player.get("ability") or 70)


RATING_SCALE = (
    (0.85, 60.0), (0.95, 70.0), (1.00, 76.0), (1.05, 82.0),
    (1.10, 89.0), (1.15, 93.0), (1.20, 96.0), (1.30, 98.0),
)


def overall_from_rating(rating: float) -> float:
    """Piecewise historical-rating scale used by all era packs."""
    value = float(rating)
    if value <= RATING_SCALE[0][0]:
        return round(max(45.0, 60.0 + (value - .85) * 100.0), 1)
    for (r0, o0), (r1, o1) in zip(RATING_SCALE, RATING_SCALE[1:]):
        if value <= r1:
            return round(o0 + (value - r0) / (r1 - r0) * (o1 - o0), 1)
    return round(min(100.0, 98.0 + (value - 1.30) * 10.0), 1)


def initial_form_delta(recent_90_rating: float, long_rating: float) -> float:
    return round(max(-10.0, min(10.0, 200.0 * (recent_90_rating - long_rating))), 2)


def long_term_rating(
    top30_365: float,
    all_365: float,
    previous_365: float,
    maps: int,
    peer_rating: float,
) -> float:
    """Date-node rating with low-sample shrinkage to same-era/role peers."""
    raw = 0.60 * float(top30_365) + 0.25 * float(all_365) + 0.15 * float(previous_365)
    confidence = min(1.0, max(0.0, int(maps) / 20.0))
    return round(confidence * raw + (1.0 - confidence) * float(peer_rating), 4)


def long_term_overall(
    top30_365: float,
    all_365: float,
    previous_365: float,
    maps: int,
    peer_rating: float,
) -> float:
    return overall_from_rating(long_term_rating(top30_365, all_365, previous_365, maps, peer_rating))


def command_of(role: str, stats: dict) -> int:
    return int(stats.get("command") or 0)


def team_command_from_utility(players: list[dict]) -> int:
    vals = []
    for p in players:
        st = p.get("stats") or {}
        vals.append(float(st.get("utility") or 0))
    if not vals:
        return 40
    return int(round(max(40.0, min(96.0, sum(vals) / len(vals)))))


def caller_of(players: list[dict]) -> dict | None:
    igl = next((p for p in players if p.get("role") == "igl"), None)
    if igl:
        return igl
    from .roles import IGL

    return next((p for p in players if p.get("role") == "awp" and p.get("name") in IGL), None)


def _stamp(raw: float) -> float:
    return max(1.0, min(100.0, round(raw * COMMAND_STAMP_MULT, 2)))


def _team_command_value(team: dict, players: list[dict]) -> int:
    utility = team_command_from_utility(players)
    base = team.get("command_base")
    if base is None:
        return utility
    # Opening tactical preparation persists as club knowledge; roster utility
    # moves it gradually instead of making one transfer erase the team context.
    return int(round(max(1.0, min(100.0, .85 * float(base) + .15 * utility))))


def restamp_command(team: dict, opening_base: float | None = None) -> int:
    """Rewrite player command stamps and initialise/refresh team preparation."""
    players = team.get("players") or []
    if opening_base is not None:
        team["command_base"] = round(max(1.0, min(100.0, float(opening_base))), 2)
        cmd = int(round(team["command_base"]))
    else:
        cmd = _team_command_value(team, players)
    team["command"] = cmd
    lead = caller_of(players)
    others = [p for p in players if p is not lead]
    share_raw = (cmd * 0.50 / max(1, len(others))) if others else 0.0
    igl_raw = cmd - share_raw * len(others)
    for p in players:
        stamp = _stamp(igl_raw if (lead is not None and p is lead) else share_raw)
        p["command"] = stamp
        st = p.get("stats")
        if st is not None:
            st["command"] = int(round(stamp))
    return cmd


def refresh_team_command(team: dict) -> int:
    """Refresh team 赛训 from opening preparation plus current utility."""
    players = team.get("players") or []
    cmd = _team_command_value(team, players)
    team["command"] = cmd
    return cmd


def igl_command(players: list[dict]) -> int:
    return team_command_from_utility(players)


def load_player_stats() -> dict[str, dict]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    path = data_file("player_stats.json")
    if not path.is_file():
        _CACHE = {}
        return _CACHE
    _CACHE = json.loads(path.read_text(encoding="utf-8"))
    return _CACHE


def reload_player_stats() -> dict[str, dict]:
    global _CACHE
    _CACHE = None
    return load_player_stats()


def _noise(name: str, key: str) -> int:
    return (sum(ord(ch) for ch in name + key) % 7) - 3


def generate_axes(name: str, role: str, target: float) -> dict:
    shape = SHAPE.get(role) or SHAPE["rifle"]
    stats = {k: clamp(target * shape[k] + _noise(name, k), 1, 100) for k in AXES}
    return fit_axes(stats, role, target)


def fit_axes(stats: dict, role: str, target: float) -> dict:
    out = {k: clamp(stats.get(k, 50), 1, 100) for k in AXES}
    for _ in range(12):
        got = ability_of(out, role)
        if abs(got - target) < 0.15:
            break
        factor = target / max(1.0, got)
        for k in GUN_AXES:
            out[k] = clamp(out[k] * factor, 1, 100)
    return out


def generate_command(name: str, role: str, ability: float, preset: int | None = None) -> int:
    if preset is not None:
        return int(max(1, min(100, preset)))
    if role == "igl":
        return clamp(ability * 1.10 + _noise(name, "cmd") * 0.3, 20, 100)
    base = (8 + 0.12 * ability + _noise(name, "cmd")) * COMMAND_STAMP_MULT
    return clamp(base, 8, 100)


def stored_axes(stored: dict) -> dict:
    return {k: float(stored[k]) for k in AXES}


def stats_for(name: str, role: str, target: float) -> dict:
    """Load axes and calibrate position ability to the era's long-term baseline.

    The legacy ``ability`` field in player_stats was derived from axes and, in
    older data builds, team-rank discounting. It is intentionally ignored.
    A v2 ``long_rating`` is authoritative; otherwise the era-pack target is.
    """
    stored = load_player_stats().get(name)
    if stored and all(k in stored for k in AXES):
        axes = stored_axes(stored)
        cmd = int(stored.get("command") or generate_command(name, role, target))
        out = {**axes, "command": cmd}
        out["ability"] = (
            overall_from_rating(float(stored["long_rating"]))
            if stored.get("long_rating") is not None
            else round(float(target), 1)
        )
        if stored.get("form_delta") is not None:
            out["form_delta"] = float(stored["form_delta"])
        calibrate_role(out, role, out["ability"])
        return out
    axes = generate_axes(name, role, target)
    cmd = generate_command(name, role, target)
    out = {**axes, "command": cmd, "ability": ability_of(axes, role)}
    calibrate_role(out, role, out["ability"])
    return out
