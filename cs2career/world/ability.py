# coding=utf-8
"""Seven-axis personal ability + eighth-axis command.

Personal ability (frags) = weighted mean of the seven gun axes.
Command is stored on every player. Only the IGL's command becomes the
team bonus (24% of map win score, veto, small frag multiplier).
"""

from __future__ import annotations

import json

from ..paths import data_file

AXES = ("entry", "trade", "nade", "clutch", "aim", "open", "move")
ALL_AXES = AXES + ("command",)
AXIS_LABEL = {
    "entry": "突破",
    "trade": "补枪",
    "nade": "道具",
    "clutch": "残局",
    "aim": "枪法",
    "open": "开战",
    "move": "身法",
    "command": "指挥",
}
WEIGHTS = {
    "awp":     {"entry": 10, "trade": 12, "nade": 12, "clutch": 16, "aim": 22, "open": 14, "move": 14},
    "entry":   {"entry": 20, "trade": 12, "nade": 10, "clutch": 12, "aim": 14, "open": 18, "move": 14},
    "rifle":   {"entry": 14, "trade": 15, "nade": 12, "clutch": 15, "aim": 16, "open": 14, "move": 14},
    "lurk":    {"entry": 12, "trade": 14, "nade": 12, "clutch": 18, "aim": 15, "open": 13, "move": 16},
    "support": {"entry": 10, "trade": 18, "nade": 20, "clutch": 12, "aim": 12, "open": 12, "move": 16},
    "igl":     {"entry": 10, "trade": 16, "nade": 20, "clutch": 14, "aim": 12, "open": 12, "move": 16},
}
SHAPE = {
    "awp":     {"entry": 0.90, "trade": 0.98, "nade": 0.96, "clutch": 1.04, "aim": 1.10, "open": 0.98, "move": 0.98},
    "entry":   {"entry": 1.08, "trade": 0.96, "nade": 0.90, "clutch": 0.96, "aim": 1.02, "open": 1.08, "move": 1.00},
    "rifle":   {"entry": 1.00, "trade": 1.00, "nade": 0.96, "clutch": 1.00, "aim": 1.04, "open": 0.98, "move": 1.00},
    "lurk":    {"entry": 0.94, "trade": 1.02, "nade": 1.00, "clutch": 1.06, "aim": 1.00, "open": 0.92, "move": 1.06},
    "support": {"entry": 0.90, "trade": 1.06, "nade": 1.10, "clutch": 0.94, "aim": 0.94, "open": 0.90, "move": 1.02},
    "igl":     {"entry": 0.88, "trade": 1.02, "nade": 1.10, "clutch": 0.96, "aim": 0.90, "open": 0.86, "move": 0.96},
}

_CACHE: dict[str, dict] | None = None


def clamp(n: float, lo: int = 40, hi: int = 100) -> int:
    return int(max(lo, min(hi, round(n))))


def ability_of(stats: dict, role: str) -> float:
    w = WEIGHTS.get(role) or WEIGHTS["rifle"]
    return round(sum(w[k] * float(stats[k]) for k in AXES) / 100.0, 1)


def command_of(role: str, stats: dict) -> int:
    return int(stats.get("command") or 0)


def refresh_team_command(team: dict) -> int:
    team["command"] = igl_command(team.get("players") or []) or int(team.get("command") or 0)
    return team["command"]


def igl_command(players: list[dict]) -> int:
    igls = [p for p in players if p.get("role") == "igl"]
    if igls:
        return max(int(round(float(p.get("command") or 0))) for p in igls)
    return 0


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
    stats = {k: clamp(target * shape[k] + _noise(name, k)) for k in AXES}
    return fit_axes(stats, role, target)


def fit_axes(stats: dict, role: str, target: float) -> dict:
    out = {k: clamp(stats[k]) for k in AXES}
    for _ in range(10):
        got = ability_of(out, role)
        if abs(got - target) < 0.15:
            break
        factor = target / max(1.0, got)
        out = {k: clamp(out[k] * factor) for k in AXES}
    return out


# Non-IGL command is usually modest. A handful of secondary callers sit higher.
RARE_VOICE = {
    "ropz": 78,
    "device": 76,
    "Jame": 76,
    "NiKo": 74,
    "s1mple": 74,
    "electronic": 72,
}


def generate_command(name: str, role: str, ability: float, preset: int | None = None) -> int:
    if preset is not None:
        return int(preset)
    if role == "igl":
        return clamp(ability - 2 + _noise(name, "cmd") * 0.4, 58, 94)
    if name in RARE_VOICE:
        return int(RARE_VOICE[name])
    base = 46 + 0.12 * ability + _noise(name, "cmd")
    return clamp(base, 40, 62)


def stored_axes(stored: dict) -> dict:
    return {k: int(stored[k]) for k in AXES}


def stats_for(name: str, role: str, target: float) -> dict:
    """Load written seven-axis stats. Do not refit a roster-table target.

    `target` is only used to generate axes for players who are not in
    player_stats.json (free agents / generated names).
    """
    stored = load_player_stats().get(name)
    if stored and all(k in stored for k in AXES):
        axes = stored_axes(stored)
        cmd = int(stored.get("command") or generate_command(name, role, target))
        out = {**axes, "command": cmd}
        if stored.get("ability") is not None:
            out["ability"] = float(stored["ability"])
        return out
    axes = generate_axes(name, role, target)
    cmd = generate_command(name, role, target)
    return {**axes, "command": cmd}
