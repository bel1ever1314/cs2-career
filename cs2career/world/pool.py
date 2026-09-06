# coding=utf-8
"""Free agents: benched pros, veterans, academy talent, rank players.

These names also show up as CS2 bots when you sign them.
"""

from __future__ import annotations

# name, role, ability, birth year, region, note
FREE_AGENTS = [
    ("DANK1NG", "awp", 78, 1999, "AS", "vet"),
    ("captainMo", "igl", 74, 1989, "AS", "vet"),
    ("DD", "rifle", 72, 1998, "AS", "vet"),
    ("karSaj", "rifle", 68, 2005, "AS", "rank"),
    ("xiaosaGe", "awp", 73, 1994, "AS", "vet"),
    ("AE", "rifle", 70, 2001, "AS", "vet"),
    ("18yM", "entry", 69, 2006, "AS", "academy"),
    ("advent", "igl", 72, 1992, "AS", "vet"),
    ("somebody", "rifle", 76, 1997, "AS", "vet"),
    ("AttackeR", "rifle", 75, 1997, "AS", "vet"),
    ("Freeman", "rifle", 74, 1998, "AS", "vet"),
    ("BnTeT", "igl", 77, 1995, "AS", "vet"),
    ("xccurate", "awp", 76, 1995, "AS", "vet"),
    ("kaze", "awp", 77, 1996, "AS", "vet"),
    ("Savage", "rifle", 73, 1992, "AS", "vet"),
    ("zhokiNg", "rifle", 71, 1993, "AS", "vet"),
    ("Maxixi", "rifle", 67, 1988, "AS", "rank"),
    ("ChildKing", "rifle", 74, 2003, "AS", "academy"),
    ("lan", "rifle", 70, 2002, "AS", "academy"),
    ("Senzu", "awp", 82, 2005, "AS", "academy"),
    ("mzinho", "rifle", 80, 2005, "AS", "academy"),
    ("s1mple", "awp", 92, 1997, "EU", "vet"),
    ("electronic", "lurk", 84, 1998, "EU", "vet"),
    ("Perfecto", "support", 80, 2000, "EU", "vet"),
    ("broky", "awp", 83, 2001, "EU", "vet"),
    ("jL", "entry", 85, 2000, "EU", "vet"),
    ("chopper", "igl", 76, 1997, "EU", "vet"),
    ("siuhy", "igl", 78, 2002, "EU", "vet"),
    ("Ax1Le", "lurk", 83, 2002, "EU", "vet"),
    ("fame", "rifle", 80, 2003, "EU", "academy"),
    ("FL1T", "rifle", 81, 2000, "EU", "vet"),
    ("nexa", "igl", 75, 1997, "EU", "vet"),
    ("interz", "support", 76, 2000, "EU", "vet"),
    ("degster", "awp", 82, 2001, "EU", "vet"),
    ("sunpayus", "awp", 81, 1998, "EU", "vet"),
    ("k0nfig", "entry", 78, 1997, "EU", "vet"),
    ("soulfly", "support", 78, 2001, "EU", "academy"),
    ("Jerry", "rifle", 76, 1998, "EU", "vet"),
    ("oSee", "awp", 79, 1999, "AM", "vet"),
    ("autimatic", "rifle", 77, 1996, "AM", "vet"),
    ("Stewie2K", "entry", 76, 1998, "AM", "vet"),
    ("tarik", "igl", 74, 1996, "AM", "vet"),
    ("RUSH", "entry", 73, 1994, "AM", "vet"),
    ("f0rest", "rifle", 72, 1988, "EU", "legend"),
    ("GeT_RiGhT", "lurk", 70, 1990, "EU", "legend"),
    ("olofmeister", "rifle", 73, 1992, "EU", "legend"),
    ("JW", "awp", 71, 1995, "EU", "legend"),
    ("flusha", "lurk", 72, 1993, "EU", "legend"),
    ("Xizt", "igl", 69, 1991, "EU", "legend"),
    ("friberg", "entry", 68, 1991, "EU", "legend"),
]

NOTE_LABEL = {
    "vet": "老将",
    "rank": "路人王",
    "academy": "青训",
    "legend": "传奇",
}

# Known birth years. Everyone else gets a stable pseudo-random age.
AGES = {
    "ZywOo": 2000, "donk": 2007, "m0NESY": 2005, "NiKo": 1997, "ropz": 1999,
    "sh1ro": 2001, "device": 1995, "karrigan": 1990, "apEX": 1993, "FalleN": 1991,
    "rain": 1994, "Magisk": 1998, "EliGE": 1997, "NAF": 1997, "jks": 1995,
    "cadiaN": 1995, "gla1ve": 1995, "tabseN": 1995, "KRIMZ": 1994, "Brollan": 2002,
    "kyousuke": 2007, "JamYoung": 2002, "s1mple": 1997, "captainMo": 1989,
    "DANK1NG": 1999, "karSaj": 2005, "DD": 1998, "b1t": 2002, "iM": 1998,
    "Aleksib": 1997, "w0nderful": 2004, "zont1x": 2005, "magixx": 2003,
    "torzsi": 2003, "xertioN": 2004, "Jimpphat": 2005, "frozen": 2001,
    "Twistzz": 1999, "broky": 2001, "flameZ": 2003, "mezii": 1997,
    "KSCERATO": 1999, "yuurih": 1999, "YEKINDAR": 1999, "molodoy": 2005,
    "XANTARES": 1996, "woxic": 1999, "Jee": 2001, "Mercury": 2000,
    "Moseyuh": 2003, "Zero": 1995, "910": 2002, "bLitz": 2004, "Techno": 2003,
    "REZ": 1998, "stavn": 2002, "jabbi": 1999, "HeavyGod": 2004, "huNter-": 1998,
    "latto": 2004, "dumau": 2001, "arT": 1996, "insani": 2004, "nqz": 2003,
    "biguzera": 2001, "saffee": 1993, "Starry": 2004, "Westmelon": 2001,
    "EmiliaQAQ": 2003, "C4LLM3SU3": 2003, "tikuak": 2001, "Summer": 1998,
}


def age_of(name: str, year: int) -> int:
    born = AGES.get(name)
    if born is None:
        born = 1998 + (sum(ord(ch) for ch in name) % 10)
    return max(16, year - born)


STARTER_CAP = 75


def starter_mates(
    region: str, roles: list[str], skip: set[str] | None = None
) -> list[tuple[str, float, str]]:
    """Four real free agents for a brand new org, one per role it still needs.

    Picking from the pool means your team-mates have proper names (so CS2 can
    give them a bot profile) and they leave the market once you sign them.
    """
    pool = [row for row in agent_rows() if row["ability"] <= STARTER_CAP]
    taken: set[str] = set(skip or ())
    out: list[tuple[str, float, str]] = []
    for role in roles:
        picks = [
            row
            for row in pool
            if row["name"] not in taken and row["role"] == role
        ]
        # Same region reads better, then the strongest body still under the cap.
        picks.sort(key=lambda r: (r["region"] != region, -r["ability"]))
        if not picks:
            picks = [row for row in pool if row["name"] not in taken]
            picks.sort(key=lambda r: (r["region"] != region, -r["ability"]))
        if not picks:
            continue
        row = picks[0]
        taken.add(row["name"])
        out.append((row["name"], row["ability"], role))
    return out


def agent_rows() -> list[dict]:
    from .ability import ability_of, stats_for

    rows = []
    for name, role, ability, born, region, note in FREE_AGENTS:
        AGES.setdefault(name, born)
        stats = stats_for(name, role, float(ability))
        gun = float(stats["ability"]) if "ability" in stats else ability_of(stats, role)
        from .aging import starting_igl_years

        age = max(16, 2026 - born)
        rows.append(
            {
                "name": name,
                "role": role,
                "ability": gun,
                "command": int(stats["command"]),
                "stats": stats,
                "form": max(52, gun - 8),
                "birth": born,
                "age": age,
                "igl_years": starting_igl_years(name, role, age),
                "region": region,
                "note": note,
                "team": None,
            }
        )
    return rows
