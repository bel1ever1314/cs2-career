# coding=utf-8
"""Individual awards: event MVP / EVP and the year-end Top 20.

MVP is usually the best player on the winning team. If a player on the
losing finalist is at least 0.10 event rating above that, they take the MVP
instead. EVPs fill out the rest. A Major gives MVP + 4 EVP, a premier
MVP + 3, a normal tier-1 MVP + 2, a CCT or RMR only an MVP.

MVP titles are classed: Major / Premier / T1 / T2 / CCT / RMR.

Everything past `event_awards` works on normalized *records* rather than live
event dicts, so honours survive a season rollover.
"""

from __future__ import annotations

from ..engine.rating import kda_rating

PLACE_LABEL = {
    "champion": "冠军",
    "final": "亚军",
    "sf": "四强",
    "qf": "八强",
    "stage": "小组赛",
}

PLACE_BONUS = {"champion": 0.30, "final": 0.18, "sf": 0.10, "qf": 0.04, "stage": 0.0}

CLASS_LABEL = {
    "major": "Major",
    "premier": "Premier",
    "t1": "T1",
    "t2": "T2",
    "cct": "CCT",
    "qual": "RMR",
}

EVP_SLOTS = {"major": 4, "premier": 3, "t1": 2, "t2": 1, "cct": 0, "qual": 0}

MVP_TITLE = {
    "major": "Major MVP",
    "premier": "Premier MVP",
    "t1": "T1 MVP",
    "t2": "T2 MVP",
    "cct": "CCT MVP",
    "qual": "RMR MVP",
}
EVP_TITLE = {
    "major": "Major EVP",
    "premier": "Premier EVP",
    "t1": "T1 EVP",
    "t2": "T2 EVP",
    "cct": "CCT EVP",
    "qual": "RMR EVP",
}
ELITE_CLASSES = ("major", "premier")
RUNNER_MVP_GAP = 0.10

TROPHY_WEIGHT = {"major": 0.050, "premier": 0.025, "t1": 0.012, "t2": 0.007, "cct": 0.004, "qual": 0.003}
MVP_WEIGHT = {"major": 0.050, "premier": 0.035, "t1": 0.020, "t2": 0.012, "cct": 0.008, "qual": 0.006}

# Year-end Top 20: 60% (MVP + vs Top10) / 40% (EVP + vs Top20).
# Games against teams outside the Top 30 do not count.
HIGH_SHARE = 0.60
MID_SHARE = 0.40
MVP_PTS = {"major": 1.15, "premier": 0.75, "t1": 0.48, "t2": 0.06, "cct": 0.06, "qual": 0.06}
EVP_PTS = {"major": 0.38, "premier": 0.24, "t1": 0.14, "t2": 0.06, "cct": 0.00, "qual": 0.00}
HONOR_DECAY = 0.70
MIN_MAPS_TOP30 = 12
MIN_MAPS_TOP10 = 12
MIN_MAPS_TOP20 = 6


def _honor_points(classes: list[str], table: dict[str, float]) -> float:
    pts = sorted((table.get(c, 0.0) for c in classes), reverse=True)
    return sum(p * (HONOR_DECAY ** i) for i, p in enumerate(pts))


def _band_rating(rec: dict, band: str, min_maps: int) -> float:
    maps = rec.get(f"maps_{band}")
    if maps is None:
        maps = rec.get("maps", 0) if band == "top30" else 0
    rating = rec.get(f"rating_{band}")
    if band == "top30" and rating is None:
        rating = rec.get("rating")
        maps = rec.get("maps", 0)
    if rating is None or maps < min_maps:
        return 0.0
    return float(rating)


def event_class(ev: dict) -> str:
    if ev.get("type") == "major":
        return "major"
    if ev.get("prestige") == "premier":
        return "premier"
    if ev.get("type") == "qual":
        feeds = ev.get("feeds") or ""
        if str(feeds).startswith("major"):
            return "qual"
        return "playin"
    return ev.get("type", "t1")


PRIZE_SPLIT = {"champion": 0.34, "final": 0.18, "sf": 0.09, "qf": 0.05, "stage": 0.0}


def placements(ev: dict) -> dict[str, str]:
    """team name -> champion / final / sf / qf / stage."""
    out: dict[str, str] = {name: "stage" for name in (ev.get("field") or [])}
    for m in ev.get("matches") or []:
        for name in (m.get("team_a"), m.get("team_b")):
            if name and name != "BYE":
                out.setdefault(name, "stage")

    def beaten(m: dict) -> str | None:
        if not m.get("played") or m.get("team_b") == "BYE" or not m.get("winner"):
            return None
        return m["team_a"] if m["winner"] != m["team_a"] else m["team_b"]

    for m in ev.get("matches") or []:
        stage = m.get("stage")
        if stage == "QF" and beaten(m):
            out[beaten(m)] = "qf"
        elif stage == "SF" and beaten(m):
            out[beaten(m)] = "sf"
        elif stage == "GF":
            if beaten(m):
                out[beaten(m)] = "final"
            if m.get("winner"):
                out[m["winner"]] = "champion"
    return out


def award_title(kind: str, ev_class: str) -> str:
    table = MVP_TITLE if kind == "mvp" else EVP_TITLE
    return table.get(ev_class, kind.upper())


def _best_on(rows: list[dict], team: str | None, min_maps: int = 3) -> dict | None:
    if not team:
        return None
    pool = [r for r in rows if r["team"] == team]
    solid = [r for r in pool if r["maps"] >= min_maps] or pool
    if not solid:
        return None
    return max(solid, key=lambda r: (r["rating"], r["kpr"], r["maps"]))


def _runner_up(ev: dict) -> str | None:
    for m in ev.get("matches") or []:
        if m.get("stage") == "GF" and m.get("played") and m.get("winner"):
            if m["winner"] == m.get("team_a"):
                return m.get("team_b")
            return m.get("team_a")
    place = placements(ev)
    return next((name for name, spot in place.items() if spot == "final"), None)


def event_awards(ev: dict, store: dict) -> dict:
    """store: {"team|player": {team, player, maps, rounds, k, d, a}}."""
    place = placements(ev)
    klass = event_class(ev)
    rows = []
    for row in store.values():
        rec = dict(row)
        rec["rating"] = kda_rating(row["k"], row["d"], row["a"], row["rounds"])
        rec["kpr"] = round(row["k"] / max(1, row["rounds"]), 3)
        rec["place"] = place.get(row["team"], "stage")
        rec["score"] = round(rec["rating"] + PLACE_BONUS.get(rec["place"], 0.0), 4)
        rows.append(rec)
    if not rows:
        return {"mvp": None, "evp": [], "five": []}

    rows.sort(key=lambda r: (-r["score"], -r["rating"], -r["kpr"]))
    champion = ev.get("champion")
    champ_best = _best_on(rows, champion)
    runner_best = _best_on(rows, _runner_up(ev))

    pick = champ_best or rows[0]
    stolen = False
    if champ_best and runner_best and runner_best["rating"] >= champ_best["rating"] + RUNNER_MVP_GAP:
        pick = runner_best
        stolen = True

    mvp = {
        **pick,
        "kind": "mvp",
        "title": award_title("mvp", klass),
        "class": klass,
        "from_finalist": stolen,
    }

    want = EVP_SLOTS.get(klass, 1)
    evp = []
    if want:
        allowed = {"champion", "final", "sf", "qf"}
        for r in rows:
            if len(evp) >= want:
                break
            if r["player"] == mvp["player"] and r["team"] == mvp["team"]:
                continue
            if r["place"] not in allowed or r["maps"] < 2:
                continue
            evp.append({**r, "kind": "evp", "title": award_title("evp", klass), "class": klass})
    return {"mvp": mvp, "evp": evp, "five": _event_five(rows)}


def _event_five(rows: list[dict]) -> list[dict]:
    """Best five by event rating — the all-star five, not just the winners."""
    out: list[dict] = []
    used: set[tuple[str, str]] = set()
    for row in sorted(rows, key=lambda r: (-r["rating"], -r["kpr"], -r["maps"])):
        key = (row["player"], row["team"])
        if key in used:
            continue
        used.add(key)
        out.append(
            {
                "player": row["player"],
                "team": row["team"],
                "rating": row["rating"],
                "maps": row["maps"],
                "place": row.get("place") or "stage",
            }
        )
        if len(out) >= 5:
            break
    return out


def make_record(ev: dict) -> dict:
    """Freeze a finished event into something honours can read forever."""
    award = ev.get("awards") or {}
    mvp = award.get("mvp")
    return {
        "id": ev["id"],
        "name": ev["name"],
        "short": ev.get("short") or ev["name"],
        "class": event_class(ev),
        "type": ev.get("type"),
        "region": ev.get("region"),
        "date": ev["dates"][-1],
        "year": int(ev["dates"][-1][:4]),
        "champion": ev.get("champion"),
        "runner_up": next(
            (
                m["team_a"] if m["winner"] != m["team_a"] else m["team_b"]
                for m in ev.get("matches") or []
                if m.get("stage") == "GF" and m.get("played")
            ),
            None,
        ),
        "champion_roster": ev.get("champion_roster") or [],
        "teams": list(ev.get("field") or []),
        "format": ev.get("resolved_format") or ev.get("format"),
        "prize": ev.get("prize", 0),
        "mvp": (
            {
                "player": mvp["player"],
                "team": mvp["team"],
                "rating": mvp["rating"],
                "title": mvp.get("title") or award_title("mvp", event_class(ev)),
                "class": mvp.get("class") or event_class(ev),
                "from_finalist": bool(mvp.get("from_finalist")),
            }
            if mvp
            else None
        ),
        "evp": [
            {
                "player": r["player"],
                "team": r["team"],
                "rating": r["rating"],
                "title": r.get("title") or award_title("evp", event_class(ev)),
                "class": r.get("class") or event_class(ev),
            }
            for r in award.get("evp") or []
        ],
        "five": [
            {
                "player": r["player"],
                "team": r["team"],
                "rating": r["rating"],
                "maps": r.get("maps") or 0,
                "place": r.get("place") or "stage",
            }
            for r in award.get("five") or []
        ],
    }


def top20(rating_rows: list[dict], records: list[dict]) -> list[dict]:
    """Year-end Top 20.

    60% MVP + rating vs Top10. 40% EVP + rating vs Top20.
    Only maps against Top 30 teams count. Weaker opposition is ignored.
    """
    if not rating_rows:
        return []

    titles: dict[str, list[str]] = {}
    mvps: dict[str, list[str]] = {}
    evps: dict[str, list[str]] = {}
    for rec in records:
        if rec.get("mvp"):
            klass = rec["mvp"].get("class") or rec.get("class")
            mvps.setdefault(rec["mvp"]["player"], []).append(klass)
        for row in rec.get("evp") or []:
            evps.setdefault(row["player"], []).append(row.get("class") or rec.get("class"))
        for name in rec.get("champion_roster") or []:
            titles.setdefault(name, []).append(rec["class"])

    rows = []
    for rec in rating_rows:
        maps30 = rec.get("maps_top30", rec.get("maps", 0))
        if maps30 < MIN_MAPS_TOP30:
            continue
        name = rec["player"]
        mvp_pts = _honor_points(mvps.get(name, []), MVP_PTS)
        evp_pts = _honor_points(evps.get(name, []), EVP_PTS)
        vs10 = _band_rating(rec, "top10", MIN_MAPS_TOP10)
        vs20 = _band_rating(rec, "top20", MIN_MAPS_TOP20)
        high = 0.5 * mvp_pts + 0.5 * vs10
        mid = 0.5 * evp_pts + 0.5 * vs20
        score = HIGH_SHARE * high + MID_SHARE * mid
        rows.append(
            {
                "player": name,
                "team": rec["team"],
                "rating": rec.get("rating_top30", rec.get("rating")),
                "rating_top10": rec.get("rating_top10"),
                "rating_top5": rec.get("rating_top5"),
                "rating_top20": rec.get("rating_top20"),
                "maps": maps30,
                "maps_top10": rec.get("maps_top10", 0),
                "maps_top20": rec.get("maps_top20", 0),
                "kpr": rec["kpr"],
                "k": rec["k"],
                "d": rec["d"],
                "a": rec["a"],
                "mvp": len(mvps.get(name, [])),
                "evp": len(evps.get(name, [])),
                "titles": len(titles.get(name, [])),
                "majors": len([c for c in titles.get(name, []) if c == "major"]),
                "mvp_pts": round(mvp_pts, 3),
                "evp_pts": round(evp_pts, 3),
                "score": round(score, 4),
            }
        )
    rows.sort(key=lambda r: (-r["score"], -(r.get("rating_top10") or 0), -r["maps"]))
    top = rows[:20]
    for i, row in enumerate(top, 1):
        row["rank"] = i
    return top


def honours_for(records: list[dict], top20_history: dict, player_name: str) -> dict:
    """Everything one player has won, across every season played so far."""
    titles, mvp, evp = [], [], []
    for rec in records:
        entry = {
            "event": rec["name"],
            "short": rec["short"],
            "class": rec["class"],
            "type": rec["type"],
            "date": rec["date"],
            "year": rec["year"],
        }
        if (rec.get("mvp") or {}).get("player") == player_name:
            mvp.append(
                {
                    **entry,
                    "rating": rec["mvp"]["rating"],
                    "title": rec["mvp"].get("title") or award_title("mvp", rec["class"]),
                    "from_finalist": bool(rec["mvp"].get("from_finalist")),
                }
            )
        for row in rec.get("evp") or []:
            if row["player"] == player_name:
                evp.append(
                    {
                        **entry,
                        "rating": row["rating"],
                        "title": row.get("title") or award_title("evp", rec["class"]),
                    }
                )
        # Winning an RMR gets you to the Major, it is not a trophy.
        if rec["type"] != "qual" and player_name in (rec.get("champion_roster") or []):
            titles.append({**entry, "team": rec.get("champion")})

    top = []
    for year, rows in sorted(top20_history.items(), key=lambda kv: str(kv[0])):
        for row in rows or []:
            if row["player"] == player_name:
                top.append({"year": int(year), "rank": row["rank"], "rating": row["rating"]})

    titles.sort(key=lambda x: x["date"])
    mvp.sort(key=lambda x: x["date"])
    evp.sort(key=lambda x: x["date"])
    return {
        "titles": titles,
        "mvp": mvp,
        "evp": evp,
        "top20": top,
        "counts": {
            "titles": len(titles),
            "majors": len([t for t in titles if t["class"] == "major"]),
            "premiers": len([t for t in titles if t["class"] == "premier"]),
            "mvp": len(mvp),
            "mvp_elite": len([x for x in mvp if x["class"] in ELITE_CLASSES]),
            "mvp_major": len([x for x in mvp if x["class"] == "major"]),
            "mvp_premier": len([x for x in mvp if x["class"] == "premier"]),
            "mvp_t1": len([x for x in mvp if x["class"] == "t1"]),
            "mvp_t2": len([x for x in mvp if x["class"] == "t2"]),
            "mvp_cct": len([x for x in mvp if x["class"] == "cct"]),
            "mvp_qual": len([x for x in mvp if x["class"] == "qual"]),
            "evp": len(evp),
            "evp_elite": len([x for x in evp if x["class"] in ELITE_CLASSES]),
            "top20": len(top),
            "best_top20": min([t["rank"] for t in top], default=None),
            "number_one": len([t for t in top if t["rank"] == 1]),
        },
    }


def team_honours(records: list[dict], team_name: str) -> list[dict]:
    return [
        {"event": r["name"], "short": r["short"], "class": r["class"], "date": r["date"]}
        for r in records
        if r.get("champion") == team_name
    ]
