# coding=utf-8
"""Opening-world builder: legacy rows or an independent dated organisation list.

Team `command` is the five-player utility mean (赛训). The IGL's command
axis is only a stamp; it does not replace team command.
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
    ("Falcons", "EU", 1, 60, [("m0NESY", 94), ("NiKo", 86), ("kyousuke", 94), ("TeSeS", 81), ("karrigan", 76)]),
    ("Vitality", "EU", 2, 60, [("ZywOo", 98), ("ropz", 80), ("flameZ", 85), ("mezii", 78), ("apEX", 80)]),
    ("Spirit", "EU", 3, 62, [("donk", 98), ("sh1ro", 91), ("zont1x", 77), ("tN1R", 80), ("magixx", 77)]),
    ("FURIA", "AM", 4, 67, [("KSCERATO", 85), ("yuurih", 79), ("molodoy", 89), ("YEKINDAR", 82), ("FalleN", 75)]),
    ("NAVI", "EU", 5, 55, [("w0nderful", 89), ("b1t", 82), ("makazze", 82), ("iM", 83), ("Aleksib", 77)]),
    ("Aurora", "EU", 6, 42, [("XANTARES", 84), ("woxic", 85), ("Jimpphat", 82), ("Wicadia", 84), ("kyxsan", 78)]),
    ("BetBoom", "EU", 7, 44, [("Magnojez", 82), ("zorte", 80), ("S1ren", 80), ("d1Ledez", 80), ("Boombl4", 79)]),
    ("MOUZ", "EU", 8, 53, [("xertioN", 86), ("Spinx", 84), ("torzsi", 86), ("PR", 79), ("xelex", 83)]),
    ("G2", "EU", 9, 60, [("HeavyGod", 80), ("huNter-", 83), ("NertZ", 81), ("r1nkle", 81), ("MATYS", 79)]),
    ("The MongolZ", "AS", 10, 47, [("910", 85), ("bLitz", 83), ("Techno", 74), ("tikuak", 79), ("DarkMeister", 81)]),
    ("Legacy", "AM", 11, 60, [("latto", 81), ("dumau", 84), ("n1ssim", 72), ("try", 90), ("arT", 75)]),
    ("FaZe", "EU", 12, 47, [("frozen", 82), ("Twistzz", 83), ("jcobbb", 82), ("Neityu", 77), ("JBOEN", 84)]),
    ("PARIVISION", "EU", 13, 42, [("Jame", 78), ("HObbit", 78), ("zweih", 78), ("xiELO", 80), ("slaxejezzz", 81)]),
    ("paiN", "AM", 14, 45, [("biguzera", 78), ("saffee", 76), ("snow", 76), ("vsm", 76), ("piriajr", 73)]),
    ("GamerLegion", "EU", 15, 47, [("REZ", 82), ("FL4MUS", 78), ("Tauson", 79), ("hypex", 81), ("Snax", 74)]),
    ("Liquid", "AM", 16, 40, [("EliGE", 86), ("NAF", 78), ("malbsMd", 77), ("Jorko", 80), ("JT", 77)]),
    ("Astralis", "EU", 17, 62, [("jabbi", 80), ("device", 83), ("Staehr", 87), ("phzy", 80), ("HooXi", 75)]),
    ("B8", "EU", 18, 44, [("npl", 86), ("alex666", 75), ("esenthial", 80), ("kensizor", 84), ("s1zzi", 85)]),
    ("3DMAX", "EU", 19, 46, [("Maka", 77), ("Graviti", 75), ("Lucky", 76), ("misutaaa", 77), ("Kursy", 79)]),
    ("TYLOO", "AS", 20, 40, [("JamYoung", 80), ("Mercury", 78), ("Moseyuh", 76), ("Jee", 80), ("Zero", 79)]),
    ("BIG", "EU", 21, 43, [("tabseN", 76), ("JDC", 79), ("faveN", 78), ("gr1ks", 82), ("blameF", 81)]),
    ("MIBR", "AM", 22, 46, [("insani", 84), ("nqz", 81), ("brnz4n", 79), ("venomzera", 82), ("LNZ", 76)]),
    ("NiP", "EU", 23, 47, [("stavn", 82), ("xKacpersky", 81), ("sjuush", 77), ("cairne", 80), ("Snappi", 72)]),
    ("HEROIC", "EU", 24, 41, [("Brollan", 79), ("nilo", 81), ("susp", 80), ("MartinezSa", 81), ("Chr1zN", 78)]),
    ("FlyQuest", "AS", 25, 44, [("jks", 78), ("INS", 76), ("Vexite", 80), ("nettik", 76), ("story", 77)]),
    ("Lynn Vision", "AS", 26, 44, [("Westmelon", 82), ("Starry", 82), ("EmiliaQAQ", 75), ("C4LLM3SU3", 76), ("z4KR", 79)]),
    ("M80", "AM", 27, 43, [("swisher", 76), ("slaxz-", 81), ("s1n", 73), ("JBa", 77), ("Lake", 81)]),
    ("9z", "AM", 28, 51, [("dgt", 82), ("max", 75), ("HUASOPEEK", 83), ("luchov", 85), ("meyern", 79)]),
    ("Imperial", "AM", 29, 40, [("noway", 76), ("decenty", 75), ("VINI", 74), ("chelo", 75), ("saadzin", 76)]),
    ("OG", "EU", 30, 40, [("cadiaN", 75), ("bodyy", 74), ("adamb", 75), ("arrozdoce", 74), ("spooke", 74)]),
    ("FUT", "EU", 31, 53, [("cmtry", 79), ("Krabeni", 80), ("dziugss", 85), ("xfl0ud", 87), ("dem0n", 87)]),
    ("NRG", "AM", 32, 40, [("Grim", 79), ("hallzerk", 82), ("Sonic", 82), ("Jeorge", 78), ("nitr0", 77)]),
    ("Virtus.pro", "EU", 33, 40, [("mir", 75), ("b1st", 78), ("AquaRS", 74), ("F0R3VER", 74), ("tO0RO", 74)]),
    ("100 Thieves", "EU", 34, 40, [("rain", 74), ("sirah", 76), ("poiii", 79), ("Gizmy", 76), ("Magisk", 77)]),
    ("Rare Atom", "AS", 35, 40, [("Summer", 73), ("L1haNg", 76), ("chengking", 74), ("3gl", 75), ("Trash", 75)]),
    ("SINNERS", "EU", 36, 40, [("SHOCK", 73), ("beastik", 72), ("kisserek", 75), ("MoDo", 76), ("stressarN", 78)]),
    ("Fluxo", "AM", 37, 40, [("zevy", 74), ("exit", 75), ("kye", 72), ("dav1deus", 76), ("Ltz", 74)]),
    ("9INE", "EU", 38, 40, [("flayy", 78), ("cej0t", 74), ("raalz", 72), ("kraghen", 74), ("bnox", 74)]),
    ("Luminosity", "EU", 39, 40, [("afro", 76), ("Rainwaker", 72), ("Bymas", 77), ("lux", 78), ("AZUWU", 79)]),
    ("Sharks", "AM", 40, 40, [("gafolo", 73), ("koala", 73), ("maxxkor", 74), ("rdnzao", 74), ("doc", 79)]),
    ("ENCE", "EU", 41, 40, [("gla1ve", 75), ("sdy", 74), ("podi", 75), ("myltsi", 74), ("rigoN", 75)]),
    ("fnatic", "EU", 42, 40, [("KRIMZ", 77), ("fear", 73), ("jambo", 80), ("CYPHER", 77), ("fnatic 2026 slot5", 76)]),
    ("SAW", "EU", 43, 40, [("MUTiRiS", 73), ("ewjerkz", 74), ("Ag1l", 74), ("krazy", 75), ("rmn", 74)]),
    ("Passion UA", "EU", 44, 40, [("Kvem", 76), ("jackasmo", 77), ("s-chilla", 74), ("jackasio", 74), ("Woro2k", 76)]),
    ("Complexity", "AM", 45, 40, [("floppy", 74), ("Cxzi", 75), ("nicx", 76), ("junior", 77), ("Grim-", 77)]),
    ("BESTIA", "AM", 46, 40, [("Noktse", 75), ("tomaszin", 76), ("timpla", 74), ("zock", 76), ("luchov-", 77)]),
    ("ATOX", "AS", 47, 40, [("dobu", 75), ("kabal", 74), ("MiQ", 76), ("AccuracyTG", 74), ("yAmi", 72)]),
    ("HOTU", "AS", 48, 40, [("finesher", 79), ("mizu", 81), ("frontales", 81), ("kade0", 76), ("n0rb3r7", 77)]),
    ("Chinggis Warriors", "AS", 49, 40, [("controlez", 74), ("cool4st", 76), ("Efire", 74), ("ACCURACY", 74), ("NEUZ", 73)]),
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


def opening_team_context(rank: int) -> tuple[float, float, float]:
    """Opening command, mentality and map preparation estimates.

    Rank is used once as a same-era data-quality fallback, never as a live
    match multiplier and never to alter a player's permanent overall.
    """
    r = max(1, min(49, int(rank)))
    if r <= 10:
        return 100.0, 100.0, 100.0
    if r <= 30:
        return 72.0 - 1.1 * (r - 11), 60.0, 55.0
    return 1.0, 0.0, 0.0


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
    from .ability import ability_of, calibrate_role, refresh_team_command, restamp_command, stats_for
    from .aging import shift_from_2026, starting_igl_years
    from .eras import ERA_PACK_VERSION, opening_rank, player_id, roster_for, validate_era_packs
    from .pool import age_of
    from .roles import role_of
    from .era_data import correction_for, team_rows_for

    year = year or int(era)
    validate_era_packs(TEAMS)
    out = []
    for i, (name, region, roster_rank, command, roster) in enumerate(team_rows_for(era, TEAMS)):
        rank = opening_rank(era, name, roster_rank)
        command_base, opening_mentality, map_adaptation = opening_team_context(rank)
        strong, weak = maps_for(i, name)
        used, era_source, data_quality = roster_for(era, name, roster, rank)
        correction = correction_for(era, name)
        authored = {p['name']: p for p in correction.get('players', [])}
        provenance = {k: v for k, v in correction.items() if k != 'players'}
        players = []
        for j, (pname, ability) in enumerate(used):
            role = authored[pname]['role'] if pname in authored else role_of(pname, j, len(used) - 1, name)
            if correction:
                # A dated estimate must not import the global (2026) player
                # statistics or age-shift them a second time.
                from .ability import generate_axes, generate_command
                stats = {**generate_axes(pname, role, ability), 'command': generate_command(pname, role, ability)}
                calibrate_role(stats, role, ability)
            else:
                stats = stats_for(pname, role, float(ability))
            gun = float(stats["ability"]) if "ability" in stats else ability_of(stats, role)
            age = age_of(pname, year)
            if year != 2026 and not correction:
                gun, stats = shift_from_2026(stats, gun, age_of(pname, 2026), age, role)
            players.append(
                {
                    "player_id": player_id(pname),
                    "name": pname,
                    "role": role,
                    "is_igl": bool(authored.get(pname, {}).get('is_igl', False)),
                    "roster_status": authored.get(pname, {}).get('roster_status', 'active'),
                    "ability": gun,
                    "long_term_ability": gun,
                    "command": int(stats.get("command") or 0),
                    "stats": stats,
                    "form_delta": float(stats.get("form_delta") or 0),
                    "form": gun + float(stats.get("form_delta") or 0),
                    "age": age,
                    "igl_years": starting_igl_years(pname, role, age),
                    "source": era_source,
                    "data_quality": data_quality,
                    "era_provenance": provenance,
                }
            )
        team = {
            "id": correction.get('id') or slug(name),
            "org_id": correction.get('id') or slug(name),
            "era_pack_version": ERA_PACK_VERSION,
            "era": era,
            "source": era_source,
            "data_quality": data_quality,
            "era_provenance": provenance,
            "custom_roles": bool(correction),
            "allow_no_awp": bool(correction.get('allow_no_awp', False)),
            "name": name,
            "region": region,
            "tier": tier_of(rank),
            "world_rank": rank,
            "command": command,
            "command_base": command_base,
            "opening_mentality": opening_mentality,
            "mentality_floor": 0.0 if rank > 30 else 35.0,
            "map_adaptation": map_adaptation,
            "team_context_source": f"{era}-opening-rank-band-estimate",
            "strong_maps": strong,
            "weak_maps": weak,
            "money": 220000 - rank * 2800,
            "players": players,
        }
        restamp_command(team, command_base)
        out.append(team)
    # Team packs may add a new organisation or replace one by id. They use the
    # same runtime shape as built-ins, so every downstream system stays generic.
    try:
        from ..content import get_registry

        payloads = get_registry().payloads("teams")
    except (OSError, TypeError, ValueError):
        payloads = []
    by_id = {team["id"]: i for i, team in enumerate(out)}
    for payload in payloads:
        payload_era = str(payload.get("era") or "")
        if payload_era and payload_era != str(era):
            continue
        for raw in payload.get("teams") or []:
            if not isinstance(raw, dict) or not raw.get("name"):
                continue
            tid = str(raw.get("id") or slug(str(raw["name"])))
            people = raw.get("players") or []
            if len(people) != 5:
                continue
            players = []
            for j, person in enumerate(people):
                if not isinstance(person, dict) or not person.get("name"):
                    players = []
                    break
                pname = str(person["name"])
                role = str(person.get("role") or role_of(pname, j, 4, str(raw["name"])))
                ability = max(45.0, min(98.0, float(person.get("ability") or 70)))
                stats = stats_for(pname, role, ability)
                calibrate_role(stats, role, ability)
                players.append({
                    "player_id": str(person.get("player_id") or player_id(pname)),
                    "name": pname, "role": role, "ability": ability,
                    "long_term_ability": ability,
                    "command": int(stats.get("command") or 0), "stats": stats,
                    "form_delta": float(person.get("form_delta") or 0),
                    "form": ability + float(person.get("form_delta") or 0),
                    "age": int(person.get("age") or age_of(pname, year)),
                    "igl_years": int(person.get("igl_years") or 0),
                    "source": f"extension:{payload.get('_pack_id')}", "data_quality": "extension",
                })
            if len(players) != 5 or len({p["player_id"] for p in players}) != 5:
                continue
            rank = max(1, int(raw.get("rank") or 50))
            strong, weak = maps_for(len(out), str(raw["name"]))
            team = {
                "id": tid, "org_id": tid, "era_pack_version": ERA_PACK_VERSION,
                "era": str(era), "source": f"extension:{payload.get('_pack_id')}",
                "data_quality": "extension", "name": str(raw["name"]),
                "custom_roles": True,
                "region": str(raw.get("region") or "EU"), "tier": tier_of(rank),
                "world_rank": rank, "command": int(raw.get("command") or 58),
                "command_base": float(raw.get("command") or 58),
                "opening_mentality": float(raw.get("mentality") or 60),
                "mentality_floor": 0.0 if rank > 30 else 35.0,
                "map_adaptation": float(raw.get("map_adaptation") or 55),
                "team_context_source": f"extension:{payload.get('_pack_id')}",
                "strong_maps": list(raw.get("strong_maps") or strong),
                "weak_maps": list(raw.get("weak_maps") or weak),
                "money": int(raw.get("money") or 80000), "players": players,
            }
            restamp_command(team, team["command_base"])
            if tid in by_id:
                out[by_id[tid]] = team
            else:
                by_id[tid] = len(out)
                out.append(team)
    return out


def roster_names(teams: list[dict]) -> set[str]:
    return {p["name"] for t in teams for p in t["players"]}
