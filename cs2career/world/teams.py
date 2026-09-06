# coding=utf-8
"""Opening world: 49 teams across EU / AM / AS.

Team `command` is the IGL's eighth-axis 战术指挥. Every player has a command
stat in data/player_stats.json; only the IGL's number buffs the team.
"""

from __future__ import annotations

MAPS = ["dust2", "mirage", "inferno", "nuke", "ancient", "anubis", "overpass", "train"]

MAP_LABEL = {
    "dust2": "Dust2",
    "mirage": "Mirage",
    "inferno": "Inferno",
    "nuke": "Nuke",
    "ancient": "Ancient",
    "anubis": "Anubis",
    "overpass": "Overpass",
    "train": "Train",
}

REGION_LABEL = {"EU": "欧洲", "AM": "美洲", "AS": "亚洲"}

# name, region, world rank, command, [(player, ability), ...]
TEAMS = [
    ("Falcons", "EU", 1, 90, [("m0NESY", 93), ("NiKo", 90), ("kyousuke", 87), ("TeSeS", 81), ("karrigan", 73)]),
    ("Vitality", "EU", 2, 93, [("ZywOo", 96), ("ropz", 88), ("flameZ", 84), ("mezii", 83), ("apEX", 74)]),
    ("Spirit", "EU", 3, 91, [("donk", 95), ("sh1ro", 91), ("zont1x", 84), ("tN1R", 83), ("magixx", 80)]),
    ("FURIA", "AM", 4, 88, [("KSCERATO", 89), ("yuurih", 87), ("molodoy", 84), ("YEKINDAR", 82), ("FalleN", 76)]),
    ("NAVI", "EU", 5, 86, [("w0nderful", 88), ("b1t", 86), ("makazze", 84), ("iM", 82), ("Aleksib", 74)]),
    ("Aurora", "EU", 6, 84, [("XANTARES", 87), ("woxic", 86), ("Jimpphat", 85), ("Wicadia", 83), ("kyxsan", 75)]),
    ("BetBoom", "EU", 7, 82, [("Magnojez", 86), ("zorte", 83), ("S1ren", 82), ("d1Ledez", 80), ("Boombl4", 74)]),
    ("MOUZ", "EU", 8, 81, [("xertioN", 87), ("Spinx", 84), ("torzsi", 83), ("PR", 78), ("xelex", 72)]),
    ("G2", "EU", 9, 76, [("HeavyGod", 89), ("huNter-", 82), ("NertZ", 81), ("r1nkle", 80), ("MATYS", 72)]),
    ("The MongolZ", "AS", 10, 83, [("910", 86), ("bLitz", 84), ("Techno", 82), ("tikuak", 80), ("DarkMeister", 74)]),
    ("Legacy", "AM", 11, 71, [("latto", 86), ("dumau", 82), ("n1ssim", 80), ("try", 77), ("arT", 73)]),
    ("FaZe", "EU", 12, 80, [("frozen", 87), ("Twistzz", 85), ("jcobbb", 81), ("Neityu", 78), ("JBOEN", 72)]),
    ("PARIVISION", "EU", 13, 79, [("Jame", 84), ("HObbit", 82), ("zweih", 80), ("xiELO", 78), ("slaxejezzz", 73)]),
    ("paiN", "AM", 14, 77, [("biguzera", 84), ("saffee", 83), ("snow", 80), ("vsm", 78), ("piriajr", 72)]),
    ("GamerLegion", "EU", 15, 75, [("REZ", 85), ("FL4MUS", 82), ("Tauson", 80), ("hypex", 76), ("Snax", 72)]),
    ("Liquid", "AM", 16, 74, [("EliGE", 85), ("NAF", 83), ("malbsMd", 81), ("Jorko", 76), ("JT", 72)]),
    ("Astralis", "EU", 17, 73, [("jabbi", 83), ("device", 84), ("Staehr", 80), ("phzy", 78), ("HooXi", 71)]),
    ("B8", "EU", 18, 72, [("npl", 81), ("alex666", 80), ("esenthial", 78), ("kensizor", 76), ("s1zzi", 70)]),
    ("3DMAX", "EU", 19, 72, [("Maka", 82), ("Graviti", 80), ("Lucky", 79), ("misutaaa", 77), ("Kursy", 71)]),
    ("TYLOO", "AS", 20, 68, [("JamYoung", 88), ("Mercury", 81), ("Moseyuh", 80), ("Jee", 79), ("Zero", 71)]),
    ("BIG", "EU", 21, 60, [("tabseN", 80), ("JDC", 76), ("faveN", 75), ("gr1ks", 74), ("blameF", 74)]),
    ("MIBR", "AM", 22, 70, [("insani", 84), ("nqz", 81), ("brnz4n", 78), ("venomzera", 76), ("LNZ", 71)]),
    ("NiP", "EU", 23, 70, [("stavn", 84), ("xKacpersky", 83), ("sjuush", 80), ("cairne", 76), ("Snappi", 72)]),
    ("HEROIC", "EU", 24, 63, [("Brollan", 86), ("nilo", 75), ("susp", 74), ("MartinezSa", 73), ("Chr1zN", 70)]),
    ("FlyQuest", "AS", 25, 67, [("jks", 82), ("INS", 78), ("Vexite", 77), ("nettik", 76), ("story", 70)]),
    ("Lynn Vision", "AS", 26, 66, [("Westmelon", 79), ("Starry", 82), ("EmiliaQAQ", 77), ("C4LLM3SU3", 75), ("z4KR", 70)]),
    ("M80", "AM", 27, 65, [("swisher", 79), ("slaxz-", 78), ("s1n", 77), ("JBa", 76), ("Lake", 70)]),
    ("9z", "AM", 28, 69, [("dgt", 81), ("max", 79), ("HUASOPEEK", 77), ("luchov", 75), ("meyern", 70)]),
    ("Imperial", "AM", 29, 64, [("noway", 80), ("decenty", 78), ("VINI", 76), ("chelo", 75), ("saadzin", 70)]),
    ("OG", "EU", 30, 66, [("cadiaN", 81), ("bodyy", 78), ("adamb", 76), ("arrozdoce", 75), ("spooke", 70)]),
    ("FUT", "EU", 31, 64, [("cmtry", 80), ("Krabeni", 78), ("dziugss", 76), ("xfl0ud", 75), ("dem0n", 70)]),
    ("NRG", "AM", 32, 63, [("Grim", 80), ("hallzerk", 79), ("Sonic", 76), ("Jeorge", 75), ("nitr0", 71)]),
    ("Virtus.pro", "EU", 33, 62, [("mir", 79), ("b1st", 76), ("AquaRS", 75), ("F0R3VER", 74), ("tO0RO", 69)]),
    ("100 Thieves", "EU", 34, 68, [("rain", 83), ("sirah", 76), ("poiii", 74), ("Gizmy", 70), ("Magisk", 77)]),
    ("Rare Atom", "AS", 35, 62, [("Summer", 80), ("L1haNg", 77), ("chengking", 75), ("3gl", 74), ("Trash", 69)]),
    ("SINNERS", "EU", 36, 60, [("SHOCK", 77), ("beastik", 75), ("kisserek", 74), ("MoDo", 73), ("stressarN", 68)]),
    ("Fluxo", "AM", 37, 61, [("zevy", 78), ("exit", 76), ("kye", 74), ("dav1deus", 73), ("Ltz", 68)]),
    ("9INE", "EU", 38, 59, [("flayy", 76), ("cej0t", 75), ("raalz", 74), ("kraghen", 73), ("bnox", 68)]),
    ("Luminosity", "EU", 39, 58, [("afro", 78), ("Rainwaker", 75), ("Bymas", 74), ("lux", 73), ("AZUWU", 68)]),
    ("Sharks", "AM", 40, 56, [("gafolo", 76), ("koala", 74), ("maxxkor", 73), ("rdnzao", 72), ("doc", 67)]),
    ("ENCE", "EU", 41, 61, [("gla1ve", 74), ("sdy", 77), ("podi", 75), ("myltsi", 73), ("rigoN", 69)]),
    ("fnatic", "EU", 42, 60, [("KRIMZ", 78), ("fear", 75), ("jambo", 73), ("CYPHER", 70), ("matys", 74)]),
    ("SAW", "EU", 43, 62, [("MUTiRiS", 74), ("ewjerkz", 75), ("Ag1l", 73), ("krazy", 70), ("rmn", 72)]),
    ("Passion UA", "EU", 44, 58, [("Kvem", 74), ("jackasmo", 73), ("s-chilla", 72), ("jackasio", 71), ("Woro2k", 76)]),
    ("Complexity", "AM", 45, 64, [("floppy", 77), ("Cxzi", 76), ("nicx", 75), ("junior", 74), ("Grim-", 78)]),
    ("BESTIA", "AM", 46, 57, [("Noktse", 73), ("tomaszin", 74), ("timpla", 72), ("zock", 68), ("luchov-", 75)]),
    ("ATOX", "AS", 47, 60, [("dobu", 76), ("kabal", 75), ("MiQ", 74), ("AccuracyTG", 72), ("yAmi", 68)]),
    ("HOTU", "AS", 48, 55, [("finesher", 74), ("mizu", 73), ("frontales", 72), ("kade0", 71), ("n0rb3r7", 67)]),
    ("Chinggis Warriors", "AS", 49, 58, [("controlez", 75), ("cool4st", 73), ("Efire", 72), ("ACCURACY", 71), ("NEUZ", 68)]),
]


def tier_of(rank: int) -> str:
    if rank <= 3:
        return "t1_top"
    if rank <= 9:
        return "t1"
    if rank <= 16:
        return "t1_bottom"
    if rank <= 28:
        return "t2"
    if rank <= 40:
        return "t3"
    return "t4"


TIER_LABEL = {
    "t1_top": "顶级",
    "t1": "一线",
    "t1_bottom": "一线末",
    "t2": "二线",
    "t3": "三线",
    "t4": "四线",
}


def slug(name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")


# Map identities. Neighbouring ranks must not share the same pair.
MAP_POOLS = {
    "Falcons": (["dust2", "nuke"], ["anubis", "overpass"]),
    "Vitality": (["nuke", "inferno"], ["train", "ancient"]),
    "Spirit": (["dust2", "mirage"], ["nuke", "overpass"]),
    "FURIA": (["inferno", "mirage"], ["nuke", "train"]),
    "NAVI": (["nuke", "dust2"], ["anubis", "overpass"]),
    "Aurora": (["ancient", "inferno"], ["overpass", "train"]),
    "BetBoom": (["anubis", "mirage"], ["nuke", "dust2"]),
    "MOUZ": (["ancient", "anubis"], ["dust2", "train"]),
    "G2": (["nuke", "overpass"], ["ancient", "anubis"]),
    "The MongolZ": (["mirage", "ancient"], ["nuke", "overpass"]),
    "Lynn Vision": (["anubis", "overpass"], ["nuke", "inferno"]),
    "TYLOO": (["dust2", "ancient"], ["mirage", "train"]),
}


def maps_for(i: int, name: str) -> tuple[list[str], list[str]]:
    if name in MAP_POOLS:
        return [MAP_POOLS[name][0][:], MAP_POOLS[name][1][:]]
    a = i % 8
    b = (i * 3 + 1) % 8
    if b == a:
        b = (a + 1) % 8
    c = (i * 5 + 2) % 8
    d = (i * 5 + 3) % 8
    while c in (a, b):
        c = (c + 1) % 8
    while d in (a, b, c):
        d = (d + 1) % 8
    return [MAPS[a], MAPS[b]], [MAPS[c], MAPS[d]]


def build_teams(era: str = "2026", year: int | None = None) -> list[dict]:
    from .ability import ability_of, igl_command, stats_for
    from .aging import starting_igl_years
    from .eras import ERA_ROSTERS
    from .pool import age_of
    from .roles import role_of

    year = year or int(era)
    overrides = ERA_ROSTERS.get(era, {})
    out = []
    for i, (name, region, rank, command, roster) in enumerate(TEAMS):
        strong, weak = maps_for(i, name)
        used = overrides.get(name, roster)
        players = []
        for j, (pname, ability) in enumerate(used):
            role = role_of(pname, j, len(used) - 1, name)
            stats = stats_for(pname, role, float(ability))
            gun = float(stats["ability"]) if "ability" in stats else ability_of(stats, role)
            age = age_of(pname, year)
            players.append(
                {
                    "name": pname,
                    "role": role,
                    "ability": gun,
                    "command": int(stats["command"]),
                    "stats": stats,
                    "form": max(52, gun - 8),
                    "age": age,
                    "igl_years": starting_igl_years(pname, role, age),
                }
            )
        out.append(
            {
                "id": slug(name),
                "name": name,
                "region": region,
                "tier": tier_of(rank),
                "world_rank": rank,
                "command": igl_command(players) or command,
                "strong_maps": strong,
                "weak_maps": weak,
                "money": 220000 - rank * 2800,
                "players": players,
            }
        )
    return out


def roster_names(teams: list[dict]) -> set[str]:
    return {p["name"] for t in teams for p in t["players"]}
