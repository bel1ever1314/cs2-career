# coding=utf-8
"""Starting-world snapshots. 2026 uses world.teams.TEAMS as-is."""

from __future__ import annotations

ERA_META = {
    "2024": {
        "year": 2024,
        "title": "魔童降世",
        "blurb": "donk 横空出世，Copenhagen / Shanghai 双 Major 周期。",
        "start": "2024-01-08",
    },
    "2025": {
        "year": 2025,
        "title": "蜜蜂王朝",
        "blurb": "Vitality 五人统治全年，ZywOo 回到世界第一。",
        "start": "2025-01-08",
    },
    "2026": {
        "year": 2026,
        "title": "现代",
        "blurb": "Falcons / Vitality / Spirit 三分天下。",
        "start": "2026-01-08",
    },
}

# team -> [(player, ability), ...]. Teams left out keep their 2026 lineup.
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
        "Complexity": [("Grim-", 77), ("Cxzi", 76), ("nicx", 75), ("junior", 74), ("hallzerk", 74)],
        "FUT": [("cmtry", 80), ("Krabeni", 78), ("dziugss", 76), ("xfl0ud", 75), ("dem0n", 70)],
    },
    "2026": {},
}
