# coding=utf-8
"""Player positions. Explicit per-team maps first, then name sets, then fallback.

Roster order never decides who holds the AWP.
"""

from __future__ import annotations

ROLE_LABEL = {
    "awp": "主狙",
    "igl": "指挥",
    "entry": "突破手",
    "lurk": "自由人",
    "support": "辅助",
    "rifle": "步枪手",
}

ROLE_RANK = {"awp": 0, "igl": 1, "entry": 2, "lurk": 3, "support": 4, "rifle": 5}

PLAYABLE_ROLES = ("rifle", "awp", "entry", "lurk", "support", "igl")

# Signature AWPers across all eras in this world.
AWP = {
    "ZywOo", "m0NESY", "sh1ro", "w0nderful", "device", "woxic", "torzsi", "Jee",
    "nqz", "broky", "s1mple", "degster", "sunpayus", "oSee", "hallzerk", "kaze",
    "xccurate", "DANK1NG", "saffee", "Jame", "molodoy", "EmiliaQAQ", "flayy", "zevy",
    "gr1ks", "910", "dumau", "r1nkle", "Jorko", "Neityu", "kensizor", "Lucky",
    "xKacpersky", "nilo", "Vexite", "slaxz-", "dgt", "noway", "cadiaN",
    "Krabeni", "b1st", "poiii", "beastik", "Rainwaker", "koala", "sdy",
    "fear", "MUTiRiS", "Woro2k", "Cxzi", "tomaszin", "dobu", "mizu", "controlez",
    "FL4MUS", "d1Ledez", "JW", "headtr1ck", "HEN1", "xiaosaGe",
    "Senzu", "yxngstxr", "afro", "SHOCK",
}

IGL = {
    "apEX", "karrigan", "Aleksib", "FalleN", "Boombl4", "HooXi", "gla1ve", "chopper",
    "siuhy", "Snax", "nitr0", "JT", "Zero", "captainMo", "advent", "kyxsan", "MAJ3R",
    "Snappi", "Chr1zN", "tabseN", "arT", "blameF", "swisher", "dexter", "alex", "nexa",
    "Xizt", "magixx", "xelex", "MATYS", "LNZ", "s1zzi", "Maka", "BnTeT",
    "story", "dem0n", "tO0RO", "Trash", "stressarN", "Ltz", "bnox", "AZUWU", "doc",
    "matys", "rmn", "Kvem", "luchov-", "yAmi", "n0rb3r7", "NEUZ", "saadzin", "bodyy",
    "piriajr", "DarkMeister", "tarik", "Westmelon",
}

ENTRY = {
    "YEKINDAR", "jcobbb", "XANTARES", "kyousuke", "dupreeh", "rigoN", "zont1x",
    "EliGE", "Staehr", "brnz4n", "sjuush", "MartinezSa", "INS", "C4LLM3SU3", "JBa",
    "VINI", "adamb", "xfl0ud", "Jeorge", "F0R3VER", "rain", "3gl", "MoDo",
    "dav1deus", "kraghen", "lux", "rdnzao", "CYPHER", "krazy", "jackasio", "junior",
    "zock", "AccuracyTG", "kade0", "ACCURACY", "hypex", "vsm", "xiELO", "bLitz",
    "makazze", "jL", "JamYoung", "zorte", "luchov", "18yM", "k0nfig", "Stewie2K",
    "donk", "chelo", "friberg",
}

LURK = {"ropz", "KSCERATO", "iM", "NAF", "Spinx", "jks", "electronic", "Ax1Le", "flusha", "GeT_RiGhT"}

SUPPORT = {
    "mezii", "TeSeS", "Magisk", "PR", "try", "nettik", "KRIMZ", "Lake", "Perfecto",
    "interz", "Liazz", "tN1R", "cairne", "myltsi", "Ag1l", "s-chilla", "maxxkor",
    "timpla", "Bymas", "raalz", "kisserek", "kye", "HUASOPEEK", "Sonic", "AquaRS",
    "chengking", "Efire", "MiQ", "frontales", "Gizmy", "nicx", "jambo", "podi",
    "Moseyuh", "Magisk",
}

# Explicit HLTV-style lineups. These override every set above.
TEAM_ROLES: dict[str, dict[str, str]] = {
    "Falcons": {"m0NESY": "awp", "NiKo": "rifle", "kyousuke": "entry", "TeSeS": "support", "karrigan": "igl", "degster": "awp", "dupreeh": "entry", "Magisk": "support", "Snappi": "igl"},
    "Vitality": {"ZywOo": "awp", "ropz": "lurk", "flameZ": "entry", "mezii": "support", "apEX": "igl", "Spinx": "lurk"},
    "Spirit": {"donk": "entry", "sh1ro": "awp", "zont1x": "support", "tN1R": "support", "magixx": "igl", "chopper": "igl"},
    "FURIA": {"KSCERATO": "lurk", "yuurih": "rifle", "molodoy": "awp", "YEKINDAR": "entry", "FalleN": "igl", "chelo": "entry", "skullz": "rifle"},
    "NAVI": {"w0nderful": "awp", "b1t": "rifle", "makazze": "entry", "iM": "lurk", "Aleksib": "igl", "jL": "entry"},
    "Aurora": {"XANTARES": "entry", "woxic": "awp", "Jimpphat": "rifle", "Wicadia": "rifle", "kyxsan": "igl", "MAJ3R": "igl", "jottAAA": "rifle", "soulfly": "support"},
    "BetBoom": {"Magnojez": "rifle", "zorte": "entry", "S1ren": "rifle", "d1Ledez": "awp", "Boombl4": "igl"},
    "MOUZ": {"xertioN": "entry", "Spinx": "lurk", "torzsi": "awp", "PR": "support", "xelex": "igl", "Brollan": "rifle", "Jimpphat": "rifle", "siuhy": "igl"},
    "G2": {"HeavyGod": "rifle", "huNter-": "rifle", "NertZ": "entry", "r1nkle": "awp", "MATYS": "igl", "NiKo": "rifle", "m0NESY": "awp", "nexa": "igl", "HooXi": "igl", "malbsMd": "rifle", "Snax": "igl"},
    "The MongolZ": {"910": "awp", "bLitz": "entry", "Techno": "rifle", "tikuak": "rifle", "DarkMeister": "igl"},
    "Legacy": {"latto": "rifle", "dumau": "awp", "n1ssim": "rifle", "try": "support", "arT": "igl"},
    "FaZe": {"frozen": "rifle", "Twistzz": "rifle", "jcobbb": "entry", "Neityu": "awp", "JBOEN": "igl", "broky": "awp", "ropz": "lurk", "rain": "entry", "karrigan": "igl", "s1mple": "awp"},
    "PARIVISION": {"Jame": "awp", "HObbit": "lurk", "zweih": "rifle", "xiELO": "entry", "slaxejezzz": "rifle"},
    "paiN": {"biguzera": "rifle", "saffee": "awp", "snow": "rifle", "vsm": "entry", "piriajr": "igl"},
    "GamerLegion": {"REZ": "rifle", "FL4MUS": "awp", "Tauson": "rifle", "hypex": "entry", "Snax": "igl", "volt": "support"},
    "Liquid": {"EliGE": "entry", "NAF": "lurk", "malbsMd": "rifle", "Jorko": "awp", "JT": "igl", "Twistzz": "rifle", "YEKINDAR": "entry", "oSee": "awp", "nitr0": "igl"},
    "Astralis": {"device": "awp", "jabbi": "entry", "Staehr": "rifle", "phzy": "rifle", "HooXi": "igl", "cadiaN": "awp", "br0": "support"},
    "B8": {"kensizor": "awp", "npl": "rifle", "alex666": "rifle", "esenthial": "entry", "s1zzi": "igl"},
    "3DMAX": {"Lucky": "awp", "Maka": "igl", "Graviti": "rifle", "misutaaa": "entry", "Kursy": "support"},
    "TYLOO": {"JamYoung": "entry", "Mercury": "rifle", "Moseyuh": "support", "Jee": "awp", "Zero": "igl", "AttackeR": "rifle", "captainMo": "igl"},
    "BIG": {"tabseN": "igl", "JDC": "rifle", "faveN": "rifle", "gr1ks": "awp", "blameF": "rifle"},
    "MIBR": {"insani": "rifle", "nqz": "awp", "brnz4n": "entry", "venomzera": "rifle", "LNZ": "igl"},
    "NiP": {"stavn": "rifle", "xKacpersky": "awp", "sjuush": "entry", "cairne": "support", "Snappi": "igl", "isak": "rifle", "headtr1ck": "awp", "alex": "igl"},
    "HEROIC": {"Brollan": "rifle", "nilo": "awp", "susp": "rifle", "MartinezSa": "entry", "Chr1zN": "igl", "yxngstxr": "awp"},
    "FlyQuest": {"jks": "lurk", "INS": "entry", "Vexite": "awp", "nettik": "support", "story": "igl", "dexter": "igl", "Liazz": "support"},
    "Lynn Vision": {"Westmelon": "igl", "Starry": "rifle", "EmiliaQAQ": "awp", "C4LLM3SU3": "entry", "z4KR": "rifle"},
    "M80": {"swisher": "igl", "slaxz-": "awp", "s1n": "rifle", "JBa": "entry", "Lake": "support"},
    "9z": {"dgt": "awp", "max": "rifle", "HUASOPEEK": "support", "luchov": "entry", "meyern": "igl"},
    "Imperial": {"noway": "awp", "decenty": "rifle", "VINI": "entry", "chelo": "entry", "saadzin": "igl", "HEN1": "awp"},
    "OG": {"cadiaN": "awp", "bodyy": "igl", "adamb": "entry", "arrozdoce": "rifle", "spooke": "support", "F1KU": "rifle", "NEOFRAG": "entry", "rallen": "support"},
    "FUT": {"cmtry": "rifle", "Krabeni": "awp", "dziugss": "rifle", "xfl0ud": "entry", "dem0n": "igl"},
    "NRG": {"Grim": "rifle", "hallzerk": "awp", "Sonic": "support", "Jeorge": "entry", "nitr0": "igl", "autimatic": "rifle", "RUSH": "entry"},
    "Virtus.pro": {"mir": "rifle", "b1st": "awp", "AquaRS": "support", "F0R3VER": "entry", "tO0RO": "igl"},
    "100 Thieves": {"rain": "entry", "sirah": "rifle", "poiii": "awp", "Gizmy": "support", "Magisk": "support", "floppy": "rifle", "JT": "igl"},
    "Rare Atom": {"Summer": "awp", "L1haNg": "rifle", "chengking": "support", "3gl": "entry", "Trash": "igl"},
    "SINNERS": {"SHOCK": "awp", "beastik": "rifle", "kisserek": "support", "MoDo": "entry", "stressarN": "igl"},
    "Fluxo": {"zevy": "awp", "exit": "rifle", "kye": "support", "dav1deus": "entry", "Ltz": "igl"},
    "9INE": {"flayy": "awp", "cej0t": "rifle", "raalz": "support", "kraghen": "entry", "bnox": "igl"},
    "Luminosity": {"afro": "awp", "Rainwaker": "rifle", "Bymas": "support", "lux": "entry", "AZUWU": "igl"},
    "Sharks": {"gafolo": "rifle", "koala": "awp", "maxxkor": "support", "rdnzao": "entry", "doc": "igl"},
    "ENCE": {"gla1ve": "igl", "sdy": "awp", "podi": "support", "myltsi": "rifle", "rigoN": "entry"},
    "fnatic": {"KRIMZ": "support", "fear": "awp", "jambo": "rifle", "CYPHER": "entry", "matys": "igl"},
    "SAW": {"MUTiRiS": "awp", "ewjerkz": "rifle", "Ag1l": "support", "krazy": "entry", "rmn": "igl"},
    "Passion UA": {"Woro2k": "awp", "jackasmo": "rifle", "s-chilla": "support", "jackasio": "entry", "Kvem": "igl"},
    "Complexity": {"Cxzi": "awp", "floppy": "rifle", "nicx": "support", "junior": "entry", "Grim-": "rifle", "hallzerk": "awp"},
    "BESTIA": {"tomaszin": "awp", "Noktse": "rifle", "timpla": "support", "zock": "entry", "luchov-": "igl"},
    "ATOX": {"dobu": "awp", "kabal": "rifle", "MiQ": "support", "AccuracyTG": "entry", "yAmi": "igl"},
    "HOTU": {"mizu": "awp", "finesher": "rifle", "frontales": "support", "kade0": "entry", "n0rb3r7": "igl"},
    "Chinggis Warriors": {"controlez": "awp", "cool4st": "rifle", "Efire": "support", "ACCURACY": "entry", "NEUZ": "igl"},
}


def known_role(name: str, team: str | None = None) -> str | None:
    """The role we are confident about, or None when the player is unknown."""
    if team:
        mapped = TEAM_ROLES.get(team, {}).get(name)
        if mapped:
            return mapped
    for role, names in (
        ("awp", AWP),
        ("igl", IGL),
        ("entry", ENTRY),
        ("lurk", LURK),
        ("support", SUPPORT),
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


def apply_roles(teams: list[dict]) -> None:
    """Re-derive roles from the role tables.

    The career player keeps the role they chose, and a signing whose role we do
    not know keeps whatever the transfer gave it. Every team ends up with exactly
    one AWPer, since two primary AWPs on one lineup is not a real lineup.
    """
    for t in teams:
        if t.get("custom_roles"):
            continue
        players = t.get("players") or []
        last = len(players) - 1
        for j, p in enumerate(players):
            if p.get("you"):
                continue
            role = known_role(p.get("name", ""), t.get("name"))
            if role is None:
                role = p.get("role") or ("igl" if j == last else "rifle")
            p["role"] = role

        awps = [p for p in players if p.get("role") == "awp"]
        if len(awps) > 1:
            keeper = max(awps, key=lambda p: (bool(p.get("you")), p.get("ability", 0)))
            for p in awps:
                if p is not keeper:
                    p["role"] = "rifle"
        elif not awps:
            pool = [p for p in players if not p.get("you") and p.get("role") != "igl"]
            if pool:
                max(pool, key=lambda p: p.get("ability", 0))["role"] = "awp"
