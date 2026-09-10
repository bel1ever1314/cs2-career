# coding=utf-8
"""Yearly gun-ability aging and IGL-only command growth.

Gun skill follows age. Command does not: it only moves with years spent as IGL.
Both curves have diminishing returns (approaching a ceiling or a floor).
"""

from __future__ import annotations

from .ability import AXES, calibrate_role, refresh_player_ability, refresh_team_command, restamp_command

GUN_LO, GUN_HI = 52.0, 99.0
CMD_LO, CMD_HI = 40, 96

# Years already spent as IGL at the start of the 2026 save.
IGL_TENURE = {
    "karrigan": 16,
    "apEX": 12,
    "FalleN": 14,
    "Aleksib": 8,
    "gla1ve": 10,
    "chopper": 8,
    "cadiaN": 7,
    "siuhy": 5,
    "MAJ3R": 8,
    "nitr0": 10,
    "Boombl4": 6,
    "arT": 8,
    "magixx": 2,
    "Snappi": 7,
    "tabseN": 9,
    "kyxsan": 4,
    "BnTeT": 8,
    "Snax": 6,
    "xelex": 3,
    "blameF": 4,
    "captainMo": 12,
    "bodyy": 4,
    "JT": 5,
    "nexa": 6,
    "advent": 8,
    "JBOEN": 1,
    "Chr1zN": 3,
    "dexter": 6,
    "MATYS": 2,
    "HooXi": 5,
    "swisher": 4,
    "DarkMeister": 2,
    "Westmelon": 3,
    "story": 3,
    "LNZ": 3,
    "Maka": 5,
    "piriajr": 3,
    "meyern": 4,
}


def starting_igl_years(name: str, role: str, age: int) -> int:
    if role != "igl":
        return 0
    if name in IGL_TENURE:
        return IGL_TENURE[name]
    return max(1, min(12, int(age) - 23))


def gun_year_delta(age: int, ability: float) -> float:
    """Age bands with a ceiling/floor so stars barely grow and wrecks barely fall."""
    a = float(ability)
    if age <= 18:
        raw = 0.80
        return raw * max(0.12, 1.0 - (a / 100.0) ** 1.35)
    if age <= 21:
        raw = 0.55
        return raw * max(0.12, 1.0 - (a / 100.0) ** 1.40)
    if age <= 25:
        raw = 0.12
        return raw * max(0.08, 1.0 - a / 105.0)
    if age <= 29:
        raw = -0.45
        return raw * (0.55 + 0.45 * (a / 100.0))
    if age <= 32:
        raw = -1.55
        return raw * (0.50 + 0.50 * (a / 100.0))
    raw = -2.35
    return raw * (0.48 + 0.52 * (a / 100.0))


def command_year_delta(igl_years: int, command: float) -> float:
    """Another year on the mic. Early tenure moves more; 90+ barely budges."""
    base = 2.30 / (1.0 + 0.40 * max(0, igl_years))
    return base * max(0.06, 1.0 - float(command) / 100.0)


def _clamp(n: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, n))


def _nudge_axes(player: dict, old: float, new: float) -> None:
    stats = player.get("stats")
    if not stats or old <= 1:
        return
    factor = new / old
    for key in AXES:
        if key in stats:
            stats[key] = int(round(_clamp(float(stats[key]) * factor, 1, 100)))


def shift_from_2026(stats: dict, ability: float, age_2026: int, age_era: int, role: str) -> tuple[float, dict]:
    """Walk ability back (or forward) along gun_year_delta using calendar ages."""
    out = dict(stats)
    a = float(ability)
    age = int(age_2026)
    era = int(age_era)
    while age > era:
        a = _clamp(a - gun_year_delta(age, a), 40.0, 98.0)
        age -= 1
    while age < era:
        age += 1
        a = _clamp(a + gun_year_delta(age, a), 40.0, 98.0)
    a = round(a, 1)
    if ability > 1 and abs(a - ability) >= 0.05:
        factor = a / ability
        for key in AXES:
            if key in out:
                out[key] = round(_clamp(float(out[key]) * factor, 1, 100), 1)
        out["ability"] = a
        out["command"] = int(round(_clamp(float(out.get("command") or 0) * factor, 8, 96)))
    else:
        out["ability"] = a
    calibrate_role(out, role, a)
    return a, out


def apply_player_year(player: dict) -> dict:
    """Age one year. Mutates the player. Returns a short log row."""
    refresh_player_ability(player)
    before = {
        "ability": float(player.get("ability") or 70),
        "command": int(player.get("command") or 0),
        "age": int(player.get("age") or 22),
        "igl_years": int(player.get("igl_years") or 0),
    }
    player["age"] = before["age"] + 1
    # Age the permanent baseline, not the selected role (otherwise changing
    # position immediately before New Year changes permanent growth).
    baseline = float(player.get("long_term_ability", before["ability"]))
    gun = _clamp(baseline + gun_year_delta(player["age"], baseline), GUN_LO, GUN_HI)
    potential = float(player.get("potential") or 0)
    if potential > gun and player["age"] <= 23:
        seed = sum(ord(ch) for ch in str(player.get("name") or "")) + int(player["age"])
        if potential >= 94:
            extra = 2.8 + (seed % 8) / 7.0 * 0.7
        else:
            extra = 1.5 + (seed % 21) / 20.0 * 2.0
        gun = _clamp(min(potential, gun + extra), GUN_LO, GUN_HI)
    player["ability"] = round(gun, 1)
    _nudge_axes(player, baseline, player["ability"])
    stats = player.get("stats")
    if stats:
        calibrate_role(stats, stats["role_reference"], player["ability"])
    player["form_delta"] = round(0.8 * float(player.get("form_delta") or 0), 2)
    player["form"] = player["ability"] + player["form_delta"]
    refresh_player_ability(player)

    if player.get("role") == "igl":
        cmd = _clamp(
            before["command"] + command_year_delta(before["igl_years"], before["command"]),
            CMD_LO,
            CMD_HI,
        )
        player["command"] = round(cmd, 1)
        player["igl_years"] = before["igl_years"] + 1
    return {
        "name": player.get("name"),
        "age": player["age"],
        "ability": player["ability"],
        "d_ability": round(player["ability"] - before["ability"], 2),
        "command": float(player.get("command") or 0),
        "d_command": round(float(player.get("command") or 0) - before["command"], 1),
        "igl_years": int(player.get("igl_years") or 0),
        "role": player.get("role"),
    }


def apply_year(teams: list[dict]) -> list[dict]:
    """Roll every rostered player forward one season."""
    rows = []
    for team in teams:
        for player in team.get("players") or []:
            rows.append(apply_player_year(player))
        refresh_team_command(team)
    return rows
