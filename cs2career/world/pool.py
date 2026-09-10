# coding=utf-8
"""Free agents: benched pros, veterans, academy talent, rank players.

These names also show up as CS2 bots when you sign them.
"""

from __future__ import annotations

# name, role, ability, birth year, region, note
FREE_AGENTS = [
    ("DANK1NG", "awp", 63, 1999, "AS", "vet"),
    ("captainMo", "igl", 62, 1989, "AS", "vet"),
    ("DD", "rifle", 59, 1994, "AS", "vet"),
    ("karSaj", "rifle", 55, 2005, "AS", "rank"),
    ("xiaosaGe", "awp", 60, 1990, "AS", "vet"),
    ("AE", "rifle", 62, 1998, "AS", "vet"),
    ("18yM", "entry", 61, 2006, "AS", "academy"),
    ("advent", "igl", 60, 1992, "AS", "vet"),
    ("somebody", "rifle", 59, 1995, "AS", "vet"),
    ("AttackeR", "rifle", 61, 1997, "AS", "vet"),
    ("Freeman", "rifle", 60, 1999, "AS", "vet"),
    ("BnTeT", "igl", 59, 1995, "AS", "vet"),
    ("xccurate", "awp", 62, 1998, "AS", "vet"),
    ("kaze", "awp", 60, 1994, "AS", "vet"),
    ("Savage", "rifle", 62, 1989, "AS", "vet"),
    ("zhokiNg", "rifle", 58, 1993, "AS", "vet"),
    ("Maxixi", "rifle", 54, 1988, "AS", "rank"),
    ("ChildKing", "rifle", 74, 2000, "AS", "academy"),
    ("lan", "rifle", 58, 2001, "AS", "academy"),
    ("Senzu", "awp", 87, 2006, "AS", "academy"),
    ("mzinho", "rifle", 59, 2007, "AS", "academy"),
    ("s1mple", "awp", 88, 1997, "EU", "vet"),
    ("electronic", "lurk", 62, 1998, "EU", "vet"),
    ("Perfecto", "rifle", 62, 1999, "EU", "vet"),
    ("broky", "awp", 72, 2001, "EU", "vet"),
    ("jL", "entry", 73, 1999, "EU", "vet"),
    ("chopper", "igl", 62, 1997, "EU", "vet"),
    ("siuhy", "igl", 60, 2002, "EU", "vet"),
    ("Ax1Le", "lurk", 59, 2002, "EU", "vet"),
    ("fame", "rifle", 63, 2003, "EU", "academy"),
    ("FL1T", "rifle", 62, 2000, "EU", "vet"),
    ("nexa", "igl", 62, 1997, "EU", "vet"),
    ("interz", "rifle", 62, 2000, "EU", "vet"),
    ("degster", "awp", 71, 2001, "EU", "vet"),
    ("sunpayus", "awp", 70, 1998, "EU", "vet"),
    ("k0nfig", "entry", 58, 1997, "EU", "vet"),
    ("soulfly", "rifle", 61, 2004, "EU", "academy"),
    ("Jerry", "rifle", 62, 1998, "EU", "vet"),
    ("oSee", "awp", 59, 1999, "AM", "vet"),
    ("autimatic", "rifle", 60, 1996, "AM", "vet"),
    ("Stewie2K", "entry", 58, 1998, "AM", "vet"),
    ("tarik", "igl", 62, 1996, "AM", "vet"),
    ("RUSH", "entry", 61, 1994, "AM", "vet"),
    ("f0rest", "rifle", 63, 1988, "EU", "legend"),
    ("GeT_RiGhT", "lurk", 66, 1990, "EU", "legend"),
    ("olofmeister", "rifle", 66, 1992, "EU", "legend"),
    ("JW", "awp", 66, 1995, "EU", "legend"),
    ("flusha", "lurk", 63, 1993, "EU", "legend"),
    ("Xizt", "igl", 66, 1991, "EU", "legend"),
    ("friberg", "entry", 66, 1991, "EU", "legend"),
]

NOTE_LABEL = {
    "vet": "老将",
    "rank": "路人王",
    "academy": "青训",
    "legend": "传奇",
}

# Known births: YYYY-MM-DD when Liquipedia has a day, otherwise YYYY.
# Names missing a month/day use a stable hash for the calendar celebration.
AGES = {
    "18yM": "2006", "3gl": "2005", "910": "2002-07-05", "AccuracyTG": "2000-06-21", "adamb": "2005-01-07",
    "advent": "1992-06-16", "AE": "1998-10-19", "afro": "1999-06-11", "Ag1l": "2003-03-02",
    "Aleksib": "1997-03-30", "alex": "1996", "alex666": "2001-08-03", "apEX": "1993-02-22",
    "AquaRS": "2006-12-28", "arrozdoce": "2002-07-02", "arT": "1996-03-27", "AttackeR": "1997-01-07",
    "autimatic": "1996-09-10", "Ax1Le": "2002-04-29", "AZUWU": "2003-11-05", "b1st": "2008-07-08",
    "b1t": "2003-01-05", "beastik": "1998-01-05", "biguzera": "1997-02-18", "blameF": "1997-06-10",
    "bLitz": "2001-06-26", "bnox": "2000-04-17", "BnTeT": "1995-08-28", "bodyy": "1997-01-08",
    "Boombl4": "1998-12-20", "br0": "2002-05-04", "brnz4n": "2003-08-26", "broky": "2001-02-14",
    "Brollan": "2002-06-17", "Bymas": "2003-08-12", "C4LLM3SU3": "2004-03-09", "cadiaN": "1995-06-26",
    "cairne": "2002-10-25", "captainMo": "1989-05-30", "cej0t": "2007-02-02", "chelo": "1998-06-08",
    "chengking": "2007-10-16", "ChildKing": "2000-02-22", "chopper": "1997-02-04", "Chr1zN": "2006-08-21",
    "cmtry": "2007-09-27", "controlez": "1997-05-23", "cool4st": "2002-06-11", "Cxzi": "2000-06-15",
    "CYPHER": "2002-12-31", "d1Ledez": "2003-07-03", "DANK1NG": "1999-09-15", "DarkMeister": "2008",
    "dav1deus": "2000-06-07", "DD": "1994-08-11", "decenty": "2004-03-01", "degster": "2001-07-21",
    "dem0n": "2007-10-02", "device": "1995-09-08", "dexter": "1994-08-15", "dgt": "2001-05-12",
    "dobu": "1999-03-13", "doc": "2002-09-20", "donk": "2007-01-25", "dumau": "2003-11-09",
    "dupreeh": "1993-03-26", "dziugss": "2008-09-12", "Efire": "2005-07-11", "electronic": "1998-09-02",
    "EliGE": "1997-07-16", "EmiliaQAQ": "2004-08-23", "esenthial": "2006-02-26", "ewjerkz": "2000-09-24",
    "exit": "1996-08-29", "F0R3VER": "2007-05-31", "f0rest": "1988-06-10", "F1KU": "2003-05-29",
    "FalleN": "1991-05-30", "fame": "2003-03-03", "faveN": "2000-02-08", "fear": "2000-11-20",
    "FL1T": "2000-12-21", "FL4MUS": "2004-08-14", "flameZ": "2003-06-22", "flayy": "2005-06-14",
    "floppy": "1999-12-31", "flusha": "1993-08-12", "Freeman": "1999-07-25", "friberg": "1991-10-19",
    "frontales": "2002-08-03", "frozen": "2002-07-18", "gafolo": "2002-04-25", "GeT_RiGhT": "1990-05-29",
    "Gizmy": "2004-02-20", "gla1ve": "1995-06-07", "gr1ks": "2005-10-24", "Graviti": "2003-11-08",
    "Grim": "2000-11-22", "Grim-": "2000-11-22", "hallzerk": "2000-07-14", "headtr1ck": "2004-06-30",
    "HeavyGod": "2002-07-24", "HEN1": "1995-07-14", "HObbit": "1994-05-18", "HooXi": "1995-05-21",
    "HUASOPEEK": "2003-04-29", "huNter-": "1996-01-03", "hypex": "2003-12-22", "iM": "1999-07-29",
    "INS": "1998-09-22", "insani": "2004-04-25", "interz": "2000-08-04", "isak": "2001-09-02",
    "jabbi": "2003-07-23", "jackasmo": "2007-05-28", "jambo": "2004-10-14", "Jame": "1998-08-23",
    "JamYoung": "2001-07-23", "JBa": "2004-06-10", "JBOEN": "2005-07-21", "jcobbb": "2004-01-27",
    "JDC": "2000-04-07", "Jee": "2004-12-21", "Jeorge": "2003-04-14", "Jerry": "1998-05-24",
    "Jimpphat": "2006-09-09", "jks": "1995-12-12", "jL": "1999-09-29", "Jorko": "2008-12-11",
    "jottAAA": "2002-07-15", "JT": "1999-04-09", "junior": "2000-12-10", "JW": "1995-02-23",
    "k0nfig": "1997-04-19", "kabal": "1995-06-01", "kade0": "2000-01-07", "karrigan": "1990-04-14",
    "kaze": "1994-07-22", "kensizor": "2006-02-02", "kisserek": "2003-04-13", "koala": "2005-02-26",
    "Krabeni": "2005-04-07", "kraghen": "2002-07-02", "krazy": "2003-12-29", "KRIMZ": "1994-04-25",
    "KSCERATO": "1999-09-12", "Kursy": "2001-08-17", "Kvem": "2001-08-29", "kye": "2004-10-15",
    "kyousuke": "2008-01-30", "kyxsan": "2000-05-26", "L1haNg": "2003-11-14", "Lake": "2004-10-19",
    "lan": "2001-09-17", "latto": "2002-12-21", "Liazz": "1997-08-30", "LNZ": "2002-10-20",
    "Ltz": "2005-07-26", "luchov": "2001-05-11", "luchov-": "2001-05-11", "Lucky": "1998-04-06",
    "lux": "2002-04-18", "m0NESY": "2005-05-01", "Magisk": "1998-03-05", "magixx": "2003-06-03",
    "Magnojez": "2004-10-14", "MAJ3R": "1991-01-25", "Maka": "1997-07-06", "makazze": "2006-12-21",
    "malbsMd": "2002-10-17", "MartinezSa": "2001-01-29", "MATYS": "2002-04-21", "matys": "2002-04-21",
    "max": "1999-06-15", "maxxkor": "2002-10-02", "Mercury": "2000-12-15", "meyern": "2002-09-10",
    "mezii": "1998-10-15", "MiQ": "2003-02-18", "mir": "1996-01-10", "misutaaa": "2003-01-15",
    "mizu": "1995-03-13", "MoDo": "2003-06-01", "molodoy": "2005-01-10", "Moseyuh": "2004-12-21",
    "MUTiRiS": "1992-12-26", "myltsi": "2004-09-29", "mzinho": "2007-06-28", "n0rb3r7": "2001-03-11",
    "n1ssim": "2001-04-27", "NAF": "1997-11-24", "Neityu": "2005-08-03", "NEOFRAG": "2001-05-19",
    "NertZ": "1999-07-12", "nettik": "2003-07-30", "NEUZ": "1999-10-12", "nexa": "1997-04-25",
    "nicx": "2004-11-29", "NiKo": "1997-02-16", "nilo": "2005-01-04", "nitr0": "1995-08-16",
    "Noktse": "1993-01-19", "noway": "2005-05-12", "npl": "2005-07-21", "nqz": "2005-01-18",
    "olofmeister": "1992-01-31", "oSee": "1999-05-31", "Perfecto": "1999-11-24", "phzy": "2002-09-24",
    "piriajr": "2002-10-01", "podi": "2004-08-05", "poiii": "2006-09-16", "PR": "2007-09-17",
    "r1nkle": "2004-10-27", "raalz": "1995-07-30", "rain": "1994-08-27", "Rainwaker": "2001-04-27",
    "rallen": "1994-06-08", "rdnzao": "2003-04-23", "REZ": "1998-01-11", "rigoN": "1999-10-07",
    "rmn": "1992-05-14", "ropz": "1999-12-22", "RUSH": "1994-05-05", "s-chilla": "2005-05-10",
    "s1mple": "1997-10-02", "s1n": "2002-03-18", "S1ren": "2002-07-16", "s1zzi": "2009-12-20",
    "saadzin": "2004-05-14", "saffee": "1994-12-19", "Savage": "1989-03-01", "sdy": "1997-03-14",
    "Senzu": "2006-08-11", "sh1ro": "2001-07-15", "SHOCK": "2000-10-29", "sirah": "2006-11-16",
    "siuhy": "2002-08-26", "sjuush": "1999-01-03", "skullz": "2002-04-20", "slaxejezzz": "2007-11-01",
    "slaxz-": "1998-11-25", "Snappi": "1990-06-09", "Snax": "1993-07-05", "snow": "2007-03-22",
    "somebody": "1995-07-03", "Sonic": "1998-12-02", "soulfly": "2004-06-16", "Spinx": "2000-09-13",
    "spooke": "2001-08-16", "Staehr": "2004-07-19", "Starry": "2005-01-03", "stavn": "2002-03-26",
    "Stewie2K": "1998-01-07", "story": "2002-04-23", "stressarN": "2002-12-13", "Summer": "1997-05-16",
    "sunpayus": "1998-11-19", "susp": "2005-01-07", "swisher": "1998-09-17", "tabseN": "1995-04-05",
    "tarik": "1996-02-18", "Tauson": "2005-08-17", "Techno": "2005-05-20", "TeSeS": "2000-12-12",
    "tikuak": "2009", "tN1R": "2001-02-14", "tO0RO": "2007-09-29", "tomaszin": "2004-02-15",
    "torzsi": "2002-05-17", "Trash": "2004-08-31", "try": "2004-09-23", "Twistzz": "1999-11-14",
    "venomzera": "2004-08-19", "Vexite": "2004-09-05", "VINI": "1999-05-20", "volt": "2001-10-18",
    "vsm": "1999-07-02", "w0nderful": "2004-12-14", "Westmelon": "2001-02-04", "Wicadia": "2005-03-04",
    "Woro2k": "2001-08-08", "woxic": "1998-09-02", "XANTARES": "1995-08-07", "xccurate": "1998-02-18",
    "xelex": "2008-06-03", "xertioN": "2004-07-22", "xfl0ud": "2002-12-23", "xiaosaGe": "1990-01-15",
    "xiELO": "2006-01-28", "Xizt": "1991-02-22", "xKacpersky": "2006-10-22", "yAmi": "2005-02-03",
    "YEKINDAR": "1999-10-04", "yuurih": "1999-12-22", "yxngstxr": "2004-10-22", "z4KR": "2002-11-14",
    "Zero": "2005-08-31", "zevy": "2001-05-30", "zhokiNg": "1993-12-07", "zock": "1997-01-25",
    "zont1x": "2005-07-20", "zorte": "1998-05-27", "zweih": "2007-09-19", "ZywOo": "2000-11-09"
}


def _birth_year(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _hash_md(name: str) -> tuple[int, int]:
    h = sum((i + 1) * ord(ch) for i, ch in enumerate(name or ""))
    return 1 + h % 12, 1 + (h // 12) % 28


def birthday_md(name: str) -> tuple[int, int]:
    """Month/day for teammate birthday popups. Hash only when the day is unknown."""
    raw = AGES.get(name)
    if isinstance(raw, str):
        parts = raw.replace("/", "-").split("-")
        if len(parts) >= 3:
            try:
                month, day = int(parts[1]), int(parts[2])
                if 1 <= month <= 12 and 1 <= day <= 31:
                    return month, day
            except ValueError:
                pass
    return _hash_md(name)


def birth_label(name: str) -> str:
    month, day = birthday_md(name)
    return f"{month}月{day}日"


def age_of(name: str, year: int) -> int:
    born = _birth_year(AGES.get(name))
    if born is None:
        born = 1998 + (sum(ord(ch) for ch in name) % 10)
    return max(16, year - born)


STARTER_CAP = 75


def starter_mates(
    region: str,
    roles: list[str],
    skip: set[str] | None = None,
    min_ability: float = 0.0,
    max_ability: float = STARTER_CAP,
    preferred_notes: tuple[str, ...] = (),
) -> list[tuple[str, float, str]]:
    """Four real free agents for a brand new org, one per role it still needs.

    Picking from the pool means your team-mates have proper names (so CS2 can
    give them a bot profile) and they leave the market once you sign them.
    """
    pool = [
        row
        for row in agent_rows()
        if float(min_ability) <= float(row["ability"]) <= float(max_ability)
    ]
    taken = {name.strip().casefold() for name in (skip or ())}
    out: list[tuple[str, float, str]] = []
    for role in roles:
        picks = [
            row
            for row in pool
            if row["name"].strip().casefold() not in taken and row["role"] == role
        ]
        # Same region reads better, then the strongest body still under the cap.
        picks.sort(
            key=lambda r: (
                bool(preferred_notes) and r.get("note") not in preferred_notes,
                r["region"] != region,
                -r["ability"],
            )
        )
        if not picks:
            picks = [row for row in pool if row["name"].strip().casefold() not in taken]
            picks.sort(
                key=lambda r: (
                    bool(preferred_notes) and r.get("note") not in preferred_notes,
                    r["region"] != region,
                    -r["ability"],
                )
            )
        if not picks:
            continue
        row = picks[0]
        taken.add(row["name"].strip().casefold())
        out.append((row["name"], row["ability"], role))
    return out


def agent_rows() -> list[dict]:
    from .ability import ability_of, stats_for
    from .eras import player_id

    rows = []
    for name, role, ability, born, region, note in FREE_AGENTS:
        AGES.setdefault(name, born)
        stats = stats_for(name, role, float(ability))
        gun = float(stats["ability"]) if "ability" in stats else ability_of(stats, role)
        from .aging import starting_igl_years

        age = age_of(name, 2026)
        rows.append(
            {
                "player_id": player_id(name),
                "name": name,
                "role": role,
                "ability": gun,
                "command": int(stats["command"]),
                "stats": stats,
                "form_delta": 0.0,
                "form": gun,
                "birth": AGES.get(name, born),
                "age": age,
                "igl_years": starting_igl_years(name, role, age),
                "region": region,
                "note": note,
                "team": None,
            }
        )
    return rows
