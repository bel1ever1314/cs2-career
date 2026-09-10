# coding=utf-8
"""Legacy era adapters; independent dated worlds live in data/eras/<year>.json."""

from __future__ import annotations

import hashlib
import re

ERA_PACK_VERSION = 2

ERA_META = {
    "2024": {
        "year": 2024,
        "title": "魔童降世",
        "blurb": "donk 横空出世，Copenhagen / Shanghai 双 Major 周期。",
        "start": "2024-01-08",
    },
    "2025": {
        "year": 2025,
        "title": "新秩序",
        "blurb": "上海 Major 落幕，转会窗口仍在继续。新赛季的王座，等待你来争夺。",
        "start": "2025-01-08",
    },
    "2026": {
        "year": 2026,
        "title": "现代",
        "blurb": "FURIA / Vitality / Falcons 开年领跑。",
        "start": "2026-01-08",
    },
}

# Legacy opening table among the original 49 orgs. The 2024/2025 manifests override
# both this ranking and the organisation list; these tables remain for eras
# which have not yet been reconstructed (currently 2026).
# 2024-01-01 HLTV, 2025-01-06 HLTV, 2026-01-05 Valve ranking.
# Skipped orgs (Monte, Cloud9, …) drop out; Eternal Fire → Aurora,
# Grayhound → FlyQuest. Unlisted orgs go to the tail in TEAMS order.
ERA_RANK_ORDER = {
    "2024": [
        "Vitality", "FaZe", "MOUZ", "NAVI", "Virtus.pro", "G2", "Complexity",
        "Falcons", "FURIA", "Spirit", "Aurora", "MIBR", "BIG", "BetBoom",
        "GamerLegion", "Astralis", "The MongolZ", "NiP", "9z", "Lynn Vision",
        "3DMAX", "TYLOO", "M80", "SAW", "BESTIA", "ENCE", "paiN", "OG",
        "SINNERS", "fnatic", "FlyQuest", "B8", "Imperial", "Sharks", "Legacy",
        "NRG", "Fluxo", "ATOX", "Passion UA", "Rare Atom",
        "PARIVISION", "Liquid", "HEROIC", "FUT", "100 Thieves", "9INE",
        "Luminosity", "HOTU", "Chinggis Warriors",
    ],
    "2025": [
        "Spirit", "G2", "NAVI", "Vitality", "MOUZ", "FaZe", "The MongolZ",
        "Liquid", "FURIA", "Falcons", "Astralis", "MIBR", "Aurora", "paiN",
        "3DMAX", "Complexity", "Virtus.pro", "GamerLegion", "SAW", "BIG",
        "FlyQuest", "M80", "Imperial", "B8", "BetBoom", "fnatic", "Passion UA",
        "9z", "NiP", "Rare Atom", "ENCE", "BESTIA", "TYLOO", "Lynn Vision",
        "OG", "ATOX", "NRG", "Legacy", "SINNERS", "9INE", "Sharks", "Fluxo",
        "PARIVISION", "HOTU", "Chinggis Warriors",
        "HEROIC", "FUT", "100 Thieves", "Luminosity",
    ],
    "2026": [
        "FURIA", "Vitality", "Falcons", "Spirit", "NAVI", "MOUZ", "FaZe",
        "The MongolZ", "Aurora", "B8", "Legacy", "G2", "Liquid", "3DMAX",
        "Astralis", "PARIVISION", "HEROIC", "paiN", "FUT", "NiP", "Passion UA",
        "SAW", "NRG", "GamerLegion", "Imperial", "BetBoom", "HOTU", "M80",
        "fnatic", "FlyQuest", "9INE", "BIG", "Fluxo", "ENCE", "SINNERS",
        "BESTIA", "Lynn Vision", "Sharks", "OG", "Virtus.pro", "MIBR",
        "Rare Atom", "TYLOO", "9z", "Chinggis Warriors",
        "100 Thieves", "Luminosity", "Complexity", "ATOX",
    ],
}


def opening_rank(era: str, name: str, fallback: int = 50) -> int:
    from .era_data import world_manifest
    world = world_manifest(str(era))
    if world:
        return next((t['seed'] for t in world['teams'] if t['name'] == name), fallback)
    order = ERA_RANK_ORDER.get(str(era)) or ERA_RANK_ORDER["2026"]
    try:
        return order.index(name) + 1
    except ValueError:
        return fallback


# Legacy partial lists, NOT fully verified historical snapshots. Missing teams
# use explicitly fictional estimates; dated JSON corrections take precedence.
ERA_ROSTERS = {
    "2024": {
        "Spirit": [("donk", 94), ("sh1ro", 90), ("zont1x", 83), ("magixx", 81), ("chopper", 76)],
        "Vitality": [("ZywOo", 95), ("Spinx", 86), ("flameZ", 83), ("mezii", 82), ("apEX", 75)],
        "NAVI": [("jL", 88), ("b1t", 86), ("w0nderful", 85), ("iM", 81), ("Aleksib", 74)],
        "FaZe": [("ropz", 89), ("frozen", 86), ("broky", 84), ("rain", 82), ("karrigan", 74)],
        "G2": [("NiKo", 92), ("m0NESY", 91), ("huNter-", 83), ("nexa", 76), ("HooXi", 71)],
        "MOUZ": [("xertioN", 86), ("Jimpphat", 84), ("torzsi", 83), ("Brollan", 85), ("siuhy", 77)],
        "Falcons": [("TeSeS", 81), ("dupreeh", 78), ("Magisk", 80), ("degster", 81), ("Snappi", 72)],
        "TYLOO": [("JamYoung", 86), ("Mercury", 80), ("Moseyuh", 79), ("Jee", 78), ("AttackeR", 75)],
        "NiP": [("stavn", 84), ("xKacpersky", 82), ("isak", 76), ("headtr1ck", 78), ("alex", 71)],
        "FlyQuest": [("INS", 78), ("Vexite", 77), ("nettik", 76), ("dexter", 74), ("Liazz", 73)],
        "OG": [("F1KU", 75), ("bodyy", 78), ("NEOFRAG", 74), ("rallen", 70), ("spooke", 70)],
        "GamerLegion": [("REZ", 85), ("FL4MUS", 82), ("Tauson", 80), ("hypex", 76), ("volt", 72)],
        "HEROIC": [("nilo", 75), ("susp", 74), ("MartinezSa", 73), ("yxngstxr", 74), ("Chr1zN", 70)],
        "Astralis": [("device", 84), ("jabbi", 83), ("Staehr", 80), ("phzy", 78), ("br0", 72)],
        "Aurora": [("XANTARES", 87), ("woxic", 86), ("Wicadia", 83), ("soulfly", 78), ("MAJ3R", 74)],
        "100 Thieves": [("floppy", 75), ("sirah", 76), ("poiii", 74), ("Gizmy", 70), ("JT", 72)],
        "Liquid": [("EliGE", 85), ("NAF", 83), ("YEKINDAR", 82), ("oSee", 79), ("nitr0", 71)],
        "Complexity": [("hallzerk", 78), ("Cxzi", 76), ("nicx", 75), ("junior", 74), ("Grim-", 77)],
        "fnatic": [("KRIMZ", 78), ("fear", 75), ("jambo", 73), ("CYPHER", 70), ("matys", 74)],
        "FURIA": [("KSCERATO", 88), ("yuurih", 86), ("chelo", 78), ("skullz", 76), ("FalleN", 77)],
        "NRG": [("Grim", 80), ("autimatic", 77), ("Sonic", 76), ("Jeorge", 75), ("RUSH", 73)],
        "Imperial": [("noway", 80), ("decenty", 78), ("VINI", 76), ("HEN1", 75), ("saadzin", 70)],
    },
    "2025": {
        "Vitality": [("ZywOo", 96), ("ropz", 88), ("flameZ", 85), ("mezii", 84), ("apEX", 74)],
        "Spirit": [("donk", 95), ("sh1ro", 91), ("zont1x", 84), ("magixx", 80), ("chopper", 76)],
        "Falcons": [("m0NESY", 93), ("NiKo", 90), ("TeSeS", 81), ("Magisk", 80), ("kyxsan", 75)],
        "G2": [("HeavyGod", 87), ("huNter-", 82), ("malbsMd", 81), ("Snax", 74), ("HooXi", 70)],
        "MOUZ": [("xertioN", 87), ("Brollan", 86), ("Jimpphat", 85), ("torzsi", 83), ("siuhy", 78)],
        "NAVI": [("w0nderful", 87), ("b1t", 86), ("jL", 84), ("iM", 81), ("Aleksib", 74)],
        "FaZe": [("s1mple", 90), ("frozen", 87), ("rain", 82), ("broky", 82), ("karrigan", 73)],
        "Liquid": [("EliGE", 85), ("Twistzz", 85), ("NAF", 83), ("YEKINDAR", 81), ("nitr0", 72)],
        "FURIA": [("KSCERATO", 89), ("yuurih", 87), ("chelo", 78), ("skullz", 77), ("FalleN", 76)],
        "NRG": [("Grim", 80), ("hallzerk", 79), ("autimatic", 77), ("Sonic", 76), ("Jeorge", 75)],
        "Astralis": [("device", 84), ("jabbi", 83), ("Staehr", 80), ("phzy", 78), ("cadiaN", 76)],
        "Imperial": [("noway", 80), ("decenty", 78), ("VINI", 76), ("HEN1", 75), ("saadzin", 70)],
        "Aurora": [("XANTARES", 87), ("woxic", 86), ("Wicadia", 83), ("jottAAA", 76), ("MAJ3R", 74)],
        "HEROIC": [("nilo", 75), ("susp", 74), ("yxngstxr", 74), ("MartinezSa", 73), ("Chr1zN", 70)],
        "GamerLegion": [("REZ", 85), ("FL4MUS", 82), ("Tauson", 80), ("hypex", 76), ("volt", 72)],
        "OG": [("F1KU", 75), ("bodyy", 78), ("NEOFRAG", 74), ("rallen", 70), ("spooke", 70)],
        "100 Thieves": [("floppy", 75), ("sirah", 76), ("poiii", 74), ("Gizmy", 70), ("JT", 72)],
        "Complexity": [("Grim-", 77), ("Cxzi", 76), ("nicx", 75), ("junior", 74), ("Complexity 2025 slot5", 74)],
        "FUT": [("cmtry", 80), ("Krabeni", 78), ("dziugss", 76), ("xfl0ud", 75), ("dem0n", 70)],
    },
    "2026": {},
}


def player_id(name: str) -> str:
    folded = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")[:18]
    digest = hashlib.sha256(name.strip().casefold().encode()).hexdigest()[:10]
    return f"p_{folded or 'player'}_{digest}"


def _estimated_roster(era: str, team_name: str, rank: int) -> list[tuple[str, float]]:
    """Same-era/rank/role-slot fallback; never reads a future lineup's values."""
    if rank <= 3:
        centre = 84.0
    elif rank <= 10:
        centre = 81.0
    elif rank <= 16:
        centre = 78.0
    elif rank <= 28:
        centre = 75.0
    elif rank <= 40:
        centre = 71.0
    else:
        centre = 68.0
    # Star, secondary, rifle, support and caller slots. The generated names are
    # identities in that historical snapshot, not disguised 2026 players.
    offsets = (5.0, 2.0, 0.0, -2.0, -5.0)
    return [
        (f"{team_name} {era} slot{i + 1}", max(45.0, min(98.0, centre + delta)))
        for i, delta in enumerate(offsets)
    ]


def roster_for(
    era: str,
    team_name: str,
    current: list[tuple[str, float]],
    rank: int | None = None,
) -> tuple[list[tuple[str, float]], str, str]:
    """Return a complete snapshot without borrowing future player identities.

    Unsourced historical slots use explicit same-era estimates as allowed by the
    v2 pack contract. They are deliberately not disguised 2026 lineups.
    """
    from .era_data import correction_for
    corrected = correction_for(era, team_name)
    if corrected:
        return [(p['name'], p['ability']) for p in corrected['players']], f"dated-roster-{era}", "mixed"
    if era == "2026":
        return list(current), "opening-world-2026", "curated"
    known = ERA_ROSTERS.get(era, {}).get(team_name)
    if known:
        return list(known), f"historical-roster-{era}", "curated"
    estimated = _estimated_roster(era, team_name, int(rank or opening_rank(era, team_name)))
    return estimated, f"same-era-role-template-{era}", "estimated"


def validate_era_packs(team_rows: list[tuple]) -> None:
    from .era_data import roster_corrections, team_rows_for, world_manifest
    for era, team in roster_corrections():
        if era not in ERA_META or team not in [r[0] for r in team_rows_for(era, team_rows)]:
            raise ValueError(f'{era}/{team} 阵容补丁存在未解析引用')
    for era in ERA_META:
        selected = team_rows_for(era, team_rows)
        names = [row[0] for row in selected]
        order = names if world_manifest(era) else ERA_RANK_ORDER.get(era) or []
        if len(order) != len(set(order)) or set(order) != set(names):
            raise ValueError(f"{era} 年代包队伍引用不完整或重复")
        seen: set[str] = set()
        for team_name, *_rest, current in selected:
            roster, _source, _quality = roster_for(
                era, team_name, current, opening_rank(era, team_name)
            )
            if len(roster) != 5:
                raise ValueError(f"{era}/{team_name} 不是五人阵容")
            ids = [player_id(name) for name, _ in roster]
            if len(set(ids)) != 5:
                raise ValueError(f"{era}/{team_name} 存在重复选手 ID")
            # One player cannot occupy two organisations at the same snapshot.
            if seen.intersection(ids):
                raise ValueError(f"{era} 年代包存在跨队重复选手 ID")
            seen.update(ids)


def _load_era_extensions() -> None:
    """Add data-only eras. Missing rank/roster fields inherit the 2026 shell."""
    try:
        from ..content import get_registry

        payloads = get_registry().payloads("eras")
    except (OSError, TypeError, ValueError):
        return
    for payload in payloads:
        for row in payload.get("eras") or []:
            if not isinstance(row, dict):
                continue
            era_id = str(row.get("id") or "")
            try:
                year = int(row.get("year") or era_id)
            except ValueError:
                continue
            if not era_id or era_id in ERA_META:
                continue
            ERA_META[era_id] = {
                "year": year,
                "title": str(row.get("title") or era_id),
                "blurb": str(row.get("blurb") or "玩家扩展年代"),
                "start": str(row.get("start") or f"{year}-01-08"),
                "pack_id": payload.get("_pack_id"),
            }
            order = row.get("rank_order")
            ERA_RANK_ORDER[era_id] = list(order) if isinstance(order, list) else list(ERA_RANK_ORDER["2026"])
            rosters: dict[str, list[tuple[str, float]]] = {}
            for team_name, players in (row.get("rosters") or {}).items():
                cooked = []
                for player in players or []:
                    if isinstance(player, dict) and player.get("name"):
                        cooked.append((str(player["name"]), float(player.get("ability") or 70)))
                    elif isinstance(player, (list, tuple)) and len(player) >= 2:
                        cooked.append((str(player[0]), float(player[1])))
                if len(cooked) == 5:
                    rosters[str(team_name)] = cooked
            ERA_ROSTERS[era_id] = rosters


_load_era_extensions()


def reload_era_extensions() -> dict:
    _load_era_extensions()
    return ERA_META
