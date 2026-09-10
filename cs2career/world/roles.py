# coding=utf-8
"""Player positions. Liquipedia squad/IGL + player |roles=, then name sets.

Roster order never decides who holds the AWP. Support is not a playable role.
"""

from __future__ import annotations

ROLE_LABEL = {
    "awp": "主狙",
    "igl": "指挥",
    "entry": "突破手",
    "lurk": "自由人",
    "rifle": "步枪手",
}

ROLE_RANK = {"awp": 0, "igl": 1, "entry": 2, "lurk": 3, "rifle": 4}

PLAYABLE_ROLES = ("rifle", "awp", "entry", "lurk", "igl")

# Explicit lineups. Era extras live on the same map; apply_roles keeps one IGL/AWP.
# When two callers share a live five, pick the one who actually led that year.
ERA_CALLER = {
    "2024": {"G2": "HooXi"},
    "2025": {"G2": "Snax"},
}
TEAM_ROLES: dict[str, dict[str, str]] = {
    "Falcons": {"m0NESY": "awp", "NiKo": "entry", "kyousuke": "entry", "TeSeS": "entry", "karrigan": "igl", "degster": "awp", "dupreeh": "entry", "Magisk": "rifle", "Snappi": "igl", "kyxsan": "igl"},
    "Vitality": {"ZywOo": "awp", "ropz": "lurk", "flameZ": "entry", "mezii": "rifle", "apEX": "igl", "Spinx": "lurk"},
    "Spirit": {"donk": "entry", "sh1ro": "awp", "zont1x": "rifle", "tN1R": "rifle", "magixx": "igl", "chopper": "igl"},
    "FURIA": {"KSCERATO": "lurk", "yuurih": "rifle", "molodoy": "awp", "YEKINDAR": "entry", "FalleN": "igl", "chelo": "entry", "skullz": "rifle"},
    "NAVI": {"w0nderful": "awp", "b1t": "rifle", "makazze": "rifle", "iM": "entry", "Aleksib": "igl", "jL": "entry"},
    "Aurora": {"XANTARES": "entry", "woxic": "awp", "Jimpphat": "rifle", "Wicadia": "rifle", "kyxsan": "igl", "MAJ3R": "igl", "jottAAA": "rifle", "soulfly": "rifle"},
    "BetBoom": {"Magnojez": "rifle", "zorte": "awp", "S1ren": "rifle", "d1Ledez": "rifle", "Boombl4": "igl"},
    "MOUZ": {"xertioN": "igl", "Spinx": "lurk", "torzsi": "awp", "PR": "rifle", "xelex": "rifle", "Brollan": "rifle", "Jimpphat": "rifle", "siuhy": "igl"},
    "G2": {"HeavyGod": "rifle", "huNter-": "igl", "NertZ": "rifle", "r1nkle": "awp", "MATYS": "rifle", "NiKo": "rifle", "m0NESY": "awp", "nexa": "rifle", "HooXi": "igl", "malbsMd": "rifle", "Snax": "igl"},
    "The MongolZ": {"910": "awp", "bLitz": "igl", "Techno": "rifle", "tikuak": "rifle", "DarkMeister": "rifle"},
    "Legacy": {"latto": "rifle", "dumau": "rifle", "n1ssim": "rifle", "try": "awp", "arT": "igl"},
    "FaZe": {"frozen": "rifle", "Twistzz": "igl", "jcobbb": "rifle", "Neityu": "rifle", "JBOEN": "awp", "broky": "awp", "ropz": "lurk", "rain": "entry", "karrigan": "igl", "s1mple": "awp"},
    "PARIVISION": {"Jame": "igl", "HObbit": "rifle", "zweih": "rifle", "xiELO": "rifle", "slaxejezzz": "rifle"},
    "paiN": {"biguzera": "igl", "saffee": "awp", "snow": "rifle", "vsm": "rifle", "piriajr": "entry"},
    "GamerLegion": {"REZ": "rifle", "FL4MUS": "entry", "Tauson": "rifle", "hypex": "awp", "Snax": "igl", "volt": "rifle"},
    "Liquid": {"EliGE": "entry", "NAF": "rifle", "malbsMd": "entry", "Jorko": "awp", "JT": "igl", "Twistzz": "rifle", "YEKINDAR": "entry", "oSee": "awp", "nitr0": "igl"},
    "Astralis": {"device": "awp", "jabbi": "rifle", "Staehr": "rifle", "phzy": "awp", "HooXi": "igl", "cadiaN": "igl", "br0": "rifle"},
    "B8": {"kensizor": "rifle", "npl": "rifle", "alex666": "igl", "esenthial": "rifle", "s1zzi": "awp"},
    "3DMAX": {"Lucky": "rifle", "Maka": "igl", "Graviti": "rifle", "misutaaa": "rifle", "Kursy": "awp"},
    "TYLOO": {"JamYoung": "rifle", "Mercury": "igl", "Moseyuh": "rifle", "Jee": "awp", "Zero": "rifle", "AttackeR": "rifle", "captainMo": "igl"},
    "BIG": {"tabseN": "rifle", "JDC": "rifle", "faveN": "rifle", "gr1ks": "awp", "blameF": "igl"},
    "MIBR": {"insani": "rifle", "nqz": "awp", "brnz4n": "entry", "venomzera": "rifle", "LNZ": "igl"},
    "NiP": {"stavn": "awp", "xKacpersky": "rifle", "sjuush": "rifle", "cairne": "rifle", "Snappi": "igl", "isak": "rifle", "headtr1ck": "awp", "alex": "igl"},
    "HEROIC": {"Brollan": "rifle", "nilo": "rifle", "susp": "rifle", "MartinezSa": "awp", "Chr1zN": "igl", "yxngstxr": "awp"},
    "FlyQuest": {"jks": "rifle", "INS": "igl", "Vexite": "rifle", "nettik": "rifle", "story": "awp", "dexter": "igl", "Liazz": "rifle"},
    "Lynn Vision": {"Westmelon": "igl", "Starry": "rifle", "EmiliaQAQ": "rifle", "C4LLM3SU3": "rifle", "z4KR": "awp"},
    "M80": {"swisher": "entry", "slaxz-": "awp", "s1n": "igl", "JBa": "rifle", "Lake": "rifle"},
    "9z": {"dgt": "lurk", "max": "igl", "HUASOPEEK": "entry", "luchov": "entry", "meyern": "awp"},
    "Imperial": {"noway": "rifle", "decenty": "lurk", "VINI": "igl", "chelo": "entry", "saadzin": "awp", "HEN1": "awp"},
    "OG": {"cadiaN": "igl", "bodyy": "rifle", "adamb": "rifle", "arrozdoce": "rifle", "spooke": "rifle", "F1KU": "rifle", "NEOFRAG": "entry", "rallen": "rifle"},
    "FUT": {"cmtry": "awp", "Krabeni": "igl", "dziugss": "rifle", "xfl0ud": "rifle", "dem0n": "rifle"},
    "NRG": {"Grim": "entry", "hallzerk": "awp", "Sonic": "rifle", "Jeorge": "rifle", "nitr0": "igl", "autimatic": "rifle", "RUSH": "entry"},
    "Virtus.pro": {"mir": "igl", "b1st": "awp", "AquaRS": "rifle", "F0R3VER": "rifle", "tO0RO": "rifle"},
    "100 Thieves": {"rain": "entry", "sirah": "rifle", "poiii": "rifle", "Gizmy": "igl", "Magisk": "rifle", "floppy": "rifle", "JT": "igl"},
    "Rare Atom": {"Summer": "igl", "L1haNg": "rifle", "chengking": "rifle", "3gl": "awp", "Trash": "rifle"},
    "SINNERS": {"SHOCK": "rifle", "beastik": "igl", "kisserek": "rifle", "MoDo": "awp", "stressarN": "rifle"},
    "Fluxo": {"zevy": "awp", "exit": "igl", "kye": "rifle", "dav1deus": "entry", "Ltz": "rifle"},
    "9INE": {"flayy": "awp", "cej0t": "rifle", "raalz": "igl", "kraghen": "rifle", "bnox": "rifle"},
    "Luminosity": {"afro": "awp", "Rainwaker": "lurk", "Bymas": "lurk", "lux": "igl", "AZUWU": "rifle"},
    "Sharks": {"gafolo": "igl", "koala": "rifle", "maxxkor": "awp", "rdnzao": "rifle", "doc": "rifle"},
    "ENCE": {"gla1ve": "igl", "sdy": "rifle", "podi": "awp", "myltsi": "rifle", "rigoN": "entry"},
    "fnatic": {"KRIMZ": "rifle", "fear": "igl", "jambo": "awp", "CYPHER": "entry", "matys": "rifle"},
    "SAW": {"MUTiRiS": "igl", "ewjerkz": "rifle", "Ag1l": "rifle", "krazy": "rifle", "rmn": "rifle"},
    "Passion UA": {"Woro2k": "awp", "jackasmo": "rifle", "s-chilla": "rifle", "jackasio": "rifle", "Kvem": "rifle"},
    "Complexity": {"Cxzi": "rifle", "floppy": "rifle", "nicx": "rifle", "junior": "awp", "Grim-": "igl", "hallzerk": "awp"},
    "BESTIA": {"tomaszin": "lurk", "Noktse": "igl", "timpla": "rifle", "zock": "lurk", "luchov-": "rifle"},
    "ATOX": {"dobu": "igl", "kabal": "rifle", "MiQ": "rifle", "AccuracyTG": "awp", "yAmi": "rifle"},
    "HOTU": {"mizu": "rifle", "finesher": "rifle", "frontales": "awp", "kade0": "igl", "n0rb3r7": "rifle"},
    "Chinggis Warriors": {"controlez": "rifle", "cool4st": "igl", "Efire": "rifle", "ACCURACY": "rifle", "NEUZ": "rifle"},
}


def _names(role: str) -> set[str]:
    return {n for players in TEAM_ROLES.values() for n, r in players.items() if r == role}


AWP = _names("awp") | {"sunpayus", "kaze", "xccurate", "DANK1NG", "JW", "xiaosaGe", "Senzu"}
IGL = _names("igl") | {"tabseN", "swisher", "advent", "Xizt", "BnTeT", "tarik", "nexa"}
ENTRY = _names("entry") | {"dupreeh", "18yM", "k0nfig", "Stewie2K", "friberg"}
LURK = _names("lurk") | {"electronic", "Ax1Le", "flusha", "GeT_RiGhT"}
# Dual IGL/AWP or backup AWPer when the live five has no dedicated sniper.
BACKUP_AWP = {"FalleN", "Jame", "cadiaN", "cool4st", "NAF", "Maka"}


def known_role(name: str, team: str | None = None) -> str | None:
    """The role we are confident about, or None when the player is unknown."""
    if team:
        mapped = TEAM_ROLES.get(team, {}).get(name)
        if mapped:
            return mapped if mapped != "support" else "rifle"
    for role, names in (
        ("awp", AWP),
        ("igl", IGL),
        ("entry", ENTRY),
        ("lurk", LURK),
    ):
        if name in names:
            return role
    return None


def role_of(name: str, index: int = 0, last: int = 4, team: str | None = None) -> str:
    role = known_role(name, team)
    if role:
        return role
    if index == last:
        return "igl"
    return "rifle"


def apply_roles(teams: list[dict], era: str | None = None, *, current_year: int | None = None) -> bool:
    """Re-derive roles from the role tables.

    The career player keeps the role they chose, except leftover 辅助 is folded
    into 步枪手. Every team ends up with one IGL (or a 指挥狙) and one AWPer.
    """
    from .ability import ensure_role_calibration, refresh_player_ability
    calibrated = False
    for t in teams:
        players = t.get("players") or []
        for p in players:
            calibrated = ensure_role_calibration(p) or calibrated
        year = current_year or (int(era) if era and str(era).isdigit() else None)
        if year:
            from .pool import age_of

            for p in players:
                # Age is persistent career state. Only repair missing values;
                # browsing must not undo aging or a scenario's authored age.
                if p.get("name") and p.get("age") is None:
                    p["age"] = age_of(p["name"], year)
        for p in players:
            if p.get("role") == "support":
                p["role"] = "rifle"
        if t.get("custom_roles"):
            _ensure_igl_awp(players, allow_no_awp=bool(t.get('allow_no_awp')))
            for p in players:
                refresh_player_ability(p)
            continue
        last = len(players) - 1
        for j, p in enumerate(players):
            if p.get("you"):
                continue
            role = known_role(p.get("name", ""), t.get("name"))
            if role is None:
                role = p.get("role") or ("igl" if j == last else "rifle")
            if role == "support":
                role = "rifle"
            p["role"] = role
        _ensure_igl_awp(players)
        _force_era_caller(players, era, t.get("name"))
        for p in players:
            refresh_player_ability(p)
        try:
            from .ability import refresh_team_command, restamp_command

            restamp_command(t)
            refresh_team_command(t)
        except Exception:
            pass
    return calibrated


def _ensure_igl_awp(players: list[dict], *, allow_no_awp: bool = False) -> None:
    _keep_one(players, "awp", key=lambda p: (bool(p.get("you")), float(p.get("ability") or 0)))
    igls = [p for p in players if p.get("role") == "igl"]
    if not igls and not any(p.get('is_igl') for p in players):
        if not any(p.get("role") == "awp" and p.get("name") in IGL for p in players):
            pool = [p for p in players if not p.get("you") and p.get("role") != "awp"]
            if not pool:
                pool = [p for p in players if not p.get("you")]
            if pool:
                max(
                    pool,
                    key=lambda p: (
                        p.get("name") in IGL,
                        int(p.get("command") or 0),
                        float(p.get("ability") or 0),
                    ),
                )["role"] = "igl"
    _keep_one(players, "igl", key=lambda p: (bool(p.get("you")), int(p.get("command") or 0), float(p.get("ability") or 0)))
    if not allow_no_awp and not any(p.get("role") == "awp" for p in players):
        backup = [p for p in players if not p.get("you") and p.get("name") in BACKUP_AWP]
        if backup:
            max(backup, key=lambda p: float(p.get("ability") or 0))["role"] = "awp"
        else:
            pool = [p for p in players if not p.get("you") and p.get("role") != "igl"]
            if not pool:
                pool = [p for p in players if not p.get("you")]
            if pool:
                max(pool, key=lambda p: float(p.get("ability") or 0))["role"] = "awp"


def _force_era_caller(players: list[dict], era: str | None, team: str | None) -> None:
    want = ERA_CALLER.get(str(era) or "", {}).get(team or "")
    if not want:
        return
    target = next((p for p in players if p.get("name") == want), None)
    if not target or target.get("you"):
        return
    for p in players:
        if p is not target and p.get("role") == "igl" and not p.get("you"):
            p["role"] = "rifle"
    if target.get("role") != "awp":
        target["role"] = "igl"


def _keep_one(players: list[dict], role: str, key) -> None:
    holders = [p for p in players if p.get("role") == role]
    if len(holders) <= 1:
        return
    keeper = max(holders, key=key)
    for p in holders:
        if p is not keeper:
            p["role"] = "rifle"
