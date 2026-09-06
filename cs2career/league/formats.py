# coding=utf-8
"""Tournament formats.

single_elim   8 teams, seeded bracket, BO3 all the way (CCT / RMR / World Final)
swiss_playoff 16 teams, Valve Swiss (3 wins in, 3 losses out) then 8-team BO3
              playoff. This is the Major format, also used by IEM premiers.
gsl_playoff   16 teams, four GSL groups of four, top two advance to an 8-team
              BO3 playoff. This is the ESL Pro League / BLAST shape.

Every function here is pure: it reads the event's existing matches and returns
the next batch of fixtures. The season object owns playing them.
"""

from __future__ import annotations

from itertools import combinations

PLAYOFF_STAGES = {8: ["QF", "SF", "GF"], 4: ["SF", "GF"], 2: ["GF"], 16: ["R16", "QF", "SF", "GF"]}

STAGE_LABEL = {
    "R16": "十六强",
    "QF": "四分之一决赛",
    "SF": "半决赛",
    "GF": "决赛",
}

GSL_GROUPS = ("A", "B", "C", "D")


def stage_title(match: dict) -> str:
    stage = match.get("stage", "")
    if stage in STAGE_LABEL:
        return STAGE_LABEL[stage]
    return match.get("label") or stage


def _day(ev: dict, index: int) -> str:
    days = ev["dates"]
    return days[min(max(0, index), len(days) - 1)]


def _mk(
    ev: dict,
    stage: str,
    day: str,
    a: str,
    b: str,
    best_of: int,
    label: str = "",
    meta: dict | None = None,
) -> dict:
    seq = len([m for m in ev.get("matches", []) if m["stage"] == stage])
    return {
        "id": f"{ev['id']}-{stage}-{seq}-{a}-{b}".replace(" ", "_"),
        "stage": stage,
        "label": label or STAGE_LABEL.get(stage, stage),
        "date": day,
        "best_of": best_of,
        "team_a": a,
        "team_b": b,
        "meta": meta or {},
        "played": False,
        "winner": None,
        "series": None,
        "maps": [],
    }


def _bye(ev: dict, stage: str, day: str, team: str, label: str = "") -> dict:
    m = _mk(ev, stage, day, team, "BYE", 1, label)
    m["played"] = True
    m["winner"] = team
    m["series"] = "bye"
    return m


def _stage_done(ev: dict, stage: str) -> bool:
    slots = [m for m in ev["matches"] if m["stage"] == stage]
    return bool(slots) and all(m["played"] for m in slots)


def _has(ev: dict, stage: str) -> bool:
    return any(m["stage"] == stage for m in ev["matches"])


def _loser(m: dict) -> str:
    return m["team_a"] if m["winner"] != m["team_a"] else m["team_b"]


def field_size(available: int, want: int) -> int:
    cap = min(available, want)
    for size in (16, 8, 4, 2):
        if cap >= size:
            return size
    return 0


def resolve_format(ev: dict, available: int) -> tuple[str, int]:
    """Fall back to a smaller shape when a region cannot fill the field."""
    want = field_size(available, ev.get("size", 8))
    fmt = ev.get("format", "single_elim")
    if fmt in ("swiss_playoff", "gsl_playoff") and want < 16:
        return "single_elim", want
    return fmt, want


# --------------------------------------------------------------------------
# single elimination


def _seed_pairs(field: list[str]) -> list[tuple[str, str]]:
    n = len(field)
    return [(field[i], field[n - 1 - i]) for i in range(n // 2)]


def _open_single_elim(ev: dict, field: list[str]) -> list[dict]:
    stages = PLAYOFF_STAGES.get(len(field)) or ["GF"]
    ev["phase"] = "playoff"
    ev["playoff_stages"] = stages
    return [
        _mk(ev, stages[0], _day(ev, 0), a, b, 3)
        for a, b in _seed_pairs(field)
    ]


def _advance_playoff(ev: dict, day_offset: int) -> list[dict]:
    stages = ev.get("playoff_stages") or ["QF", "SF", "GF"]
    for i, stage in enumerate(stages):
        if not _has(ev, stage):
            continue
        if not _stage_done(ev, stage):
            return []
        if stage == "GF":
            return []
        nxt = stages[i + 1]
        if _has(ev, nxt):
            continue
        winners = [m["winner"] for m in ev["matches"] if m["stage"] == stage]
        day = _day(ev, day_offset + i + 1)
        out = []
        for j in range(0, len(winners) - 1, 2):
            out.append(_mk(ev, nxt, day, winners[j], winners[j + 1], 3))
        if len(winners) % 2 == 1:
            out.append(_bye(ev, nxt, day, winners[-1]))
        return out
    return []


# --------------------------------------------------------------------------
# Swiss


def swiss_state(ev: dict) -> dict[str, dict]:
    seeds = {name: i for i, name in enumerate(ev.get("field", []))}
    state = {
        name: {"name": name, "w": 0, "l": 0, "opps": [], "seed": seeds.get(name, 99)}
        for name in ev.get("field", [])
    }
    for m in ev["matches"]:
        if m.get("phase") != "swiss" and not m["stage"].startswith("SW"):
            continue
        if not m["played"]:
            continue
        a, b = m["team_a"], m["team_b"]
        if a not in state or b not in state:
            continue
        win, lose = (a, b) if m["winner"] == a else (b, a)
        state[win]["w"] += 1
        state[lose]["l"] += 1
        state[win]["opps"].append(lose)
        state[lose]["opps"].append(win)
    for row in state.values():
        row["diff"] = row["w"] - row["l"]
    for row in state.values():
        row["buchholz"] = sum(state[o]["diff"] for o in row["opps"] if o in state)
    return state


def _pair_no_rematch(rows: list[dict]) -> list[tuple[dict, dict]] | None:
    """Best-vs-worst inside a record group, backtracking around rematches."""
    if not rows:
        return []
    if len(rows) % 2 == 1:
        rows = rows[:-1]
    order = sorted(rows, key=lambda r: (-r["buchholz"], r["seed"]))

    def solve(pool: list[dict]) -> list[tuple[dict, dict]] | None:
        if not pool:
            return []
        top = pool[0]
        rest = pool[1:]
        for i in range(len(rest) - 1, -1, -1):
            cand = rest[i]
            if cand["name"] in top["opps"]:
                continue
            tail = solve(rest[:i] + rest[i + 1 :])
            if tail is not None:
                return [(top, cand)] + tail
        return None

    solved = solve(order)
    if solved is not None:
        return solved
    # Every option is a rematch: accept the least-bad seeded pairing.
    n = len(order)
    return [(order[i], order[n - 1 - i]) for i in range(n // 2)]


def _open_swiss(ev: dict, field: list[str]) -> list[dict]:
    ev["phase"] = "swiss"
    ev["swiss_round"] = 1
    half = len(field) // 2
    out = []
    for i in range(half):
        out.append(
            _mk(
                ev,
                "SW1",
                _day(ev, 0),
                field[i],
                field[half + i],
                1,
                label="瑞士轮 第1轮 · 0-0",
                meta={"phase": "swiss", "record": "0-0"},
            )
        )
    for m in out:
        m["phase"] = "swiss"
    return out


def _advance_swiss(ev: dict) -> list[dict]:
    rnd = ev.get("swiss_round", 1)
    if not _stage_done(ev, f"SW{rnd}"):
        return []

    state = swiss_state(ev)
    alive = [r for r in state.values() if r["w"] < 3 and r["l"] < 3]
    advanced = sorted(
        [r for r in state.values() if r["w"] >= 3],
        key=lambda r: (r["l"], -r["buchholz"], r["seed"]),
    )

    if len(advanced) >= 8 or not alive or rnd >= 5:
        return _start_playoff_from_swiss(ev, advanced, state)

    nxt = rnd + 1
    ev["swiss_round"] = nxt
    groups: dict[tuple[int, int], list[dict]] = {}
    for row in alive:
        groups.setdefault((row["w"], row["l"]), []).append(row)

    out: list[dict] = []
    leftovers: list[dict] = []
    for record in sorted(groups, key=lambda k: (-k[0], k[1])):
        rows = groups[record]
        if len(rows) % 2 == 1:
            rows = sorted(rows, key=lambda r: (-r["buchholz"], r["seed"]))
            leftovers.append(rows[-1])
            rows = rows[:-1]
        decider = record[0] == 2 or record[1] == 2
        for a, b in _pair_no_rematch(rows) or []:
            out.append(
                _mk(
                    ev,
                    f"SW{nxt}",
                    _day(ev, nxt - 1),
                    a["name"],
                    b["name"],
                    3 if decider else 1,
                    label=f"瑞士轮 第{nxt}轮 · {record[0]}-{record[1]}",
                    meta={"phase": "swiss", "record": f"{record[0]}-{record[1]}"},
                )
            )
    for a, b in _pair_no_rematch(leftovers) or []:
        out.append(
            _mk(
                ev,
                f"SW{nxt}",
                _day(ev, nxt - 1),
                a["name"],
                b["name"],
                1,
                label=f"瑞士轮 第{nxt}轮 · 跨档",
                meta={"phase": "swiss", "record": "mixed"},
            )
        )
    for m in out:
        m["phase"] = "swiss"
    if not out:
        return _start_playoff_from_swiss(ev, advanced, state)
    return out


def _start_playoff_from_swiss(ev: dict, advanced: list[dict], state: dict) -> list[dict]:
    if _has(ev, "QF") or _has(ev, "SF") or _has(ev, "GF"):
        return []
    seeded = [r["name"] for r in advanced]
    if len(seeded) < 8:
        rest = sorted(
            [r for r in state.values() if r["name"] not in seeded],
            key=lambda r: (-r["w"], r["l"], -r["buchholz"], r["seed"]),
        )
        seeded += [r["name"] for r in rest]
    seeded = seeded[: field_size(len(seeded), 8)]
    ev["phase"] = "playoff"
    ev["playoff_seeds"] = seeded
    stages = PLAYOFF_STAGES.get(len(seeded)) or ["GF"]
    ev["playoff_stages"] = stages
    ev["playoff_day0"] = len(ev["dates"]) - len(stages)
    day = _day(ev, ev["playoff_day0"])
    return [_mk(ev, stages[0], day, a, b, 3) for a, b in _seed_pairs(seeded)]


# --------------------------------------------------------------------------
# GSL groups


def _open_gsl(ev: dict, field: list[str]) -> list[dict]:
    ev["phase"] = "groups"
    ev["gsl_round"] = 1
    groups: dict[str, list[str]] = {g: [] for g in GSL_GROUPS}
    # Snake seeding: A gets 1/8/9/16, B gets 2/7/10/15, and so on.
    for i, name in enumerate(field):
        band, pos = divmod(i, 4)
        idx = pos if band % 2 == 0 else 3 - pos
        groups[GSL_GROUPS[idx]].append(name)
    ev["gsl_field"] = groups
    out = []
    for g in GSL_GROUPS:
        seeds = groups[g]
        if len(seeds) < 4:
            continue
        out.append(
            _mk(ev, "G1", _day(ev, 0), seeds[0], seeds[3], 1, f"{g}组 首轮", {"group": g, "kind": "open"})
        )
        out.append(
            _mk(ev, "G1", _day(ev, 0), seeds[1], seeds[2], 1, f"{g}组 首轮", {"group": g, "kind": "open"})
        )
    for m in out:
        m["phase"] = "groups"
    return out


def _advance_gsl(ev: dict) -> list[dict]:
    rnd = ev.get("gsl_round", 1)
    stage = f"G{rnd}"
    if not _stage_done(ev, stage):
        return []
    out: list[dict] = []

    if rnd == 1:
        ev["gsl_round"] = 2
        for g in GSL_GROUPS:
            opens = [m for m in ev["matches"] if m["stage"] == "G1" and m["meta"].get("group") == g]
            if len(opens) < 2:
                continue
            winners = [m["winner"] for m in opens]
            losers = [_loser(m) for m in opens]
            out.append(
                _mk(ev, "G2", _day(ev, 1), winners[0], winners[1], 3, f"{g}组 胜者组", {"group": g, "kind": "winners"})
            )
            out.append(
                _mk(ev, "G2", _day(ev, 1), losers[0], losers[1], 3, f"{g}组 淘汰赛", {"group": g, "kind": "elim"})
            )
    elif rnd == 2:
        ev["gsl_round"] = 3
        for g in GSL_GROUPS:
            wm = next(
                (m for m in ev["matches"] if m["stage"] == "G2" and m["meta"].get("group") == g and m["meta"].get("kind") == "winners"),
                None,
            )
            em = next(
                (m for m in ev["matches"] if m["stage"] == "G2" and m["meta"].get("group") == g and m["meta"].get("kind") == "elim"),
                None,
            )
            if not wm or not em:
                continue
            out.append(
                _mk(ev, "G3", _day(ev, 2), _loser(wm), em["winner"], 3, f"{g}组 决胜局", {"group": g, "kind": "decider"})
            )
    else:
        return _start_playoff_from_gsl(ev)

    for m in out:
        m["phase"] = "groups"
    return out or _start_playoff_from_gsl(ev)


def gsl_standings(ev: dict) -> dict[str, list[dict]]:
    """Per group: who came 1st, 2nd, and who went out."""
    table: dict[str, list[dict]] = {}
    for g in GSL_GROUPS:
        rows: dict[str, dict] = {}
        for name in (ev.get("gsl_field") or {}).get(g, []):
            rows[name] = {"team": name, "w": 0, "l": 0, "place": "—"}
        for m in ev["matches"]:
            if m["meta"].get("group") != g or not m["played"] or m["team_b"] == "BYE":
                continue
            win, lose = m["winner"], _loser(m)
            if win in rows:
                rows[win]["w"] += 1
            if lose in rows:
                rows[lose]["l"] += 1
            if m["meta"].get("kind") == "winners":
                rows.setdefault(win, {"team": win, "w": 0, "l": 0})["place"] = "1st"
            if m["meta"].get("kind") == "decider":
                rows.setdefault(win, {"team": win, "w": 0, "l": 0})["place"] = "2nd"
                rows.setdefault(lose, {"team": lose, "w": 0, "l": 0})["place"] = "out"
            if m["meta"].get("kind") == "elim":
                rows.setdefault(lose, {"team": lose, "w": 0, "l": 0})["place"] = "out"
        table[g] = sorted(rows.values(), key=lambda r: (r["place"] != "1st", r["place"] != "2nd", -r["w"]))
    return table


def _start_playoff_from_gsl(ev: dict) -> list[dict]:
    if _has(ev, "QF") or _has(ev, "SF") or _has(ev, "GF"):
        return []
    table = gsl_standings(ev)
    firsts, seconds = {}, {}
    for g, rows in table.items():
        for row in rows:
            if row["place"] == "1st":
                firsts[g] = row["team"]
            elif row["place"] == "2nd":
                seconds[g] = row["team"]
    cross = [("A", "B"), ("C", "D"), ("B", "A"), ("D", "C")]
    pairs = []
    for g1, g2 in cross:
        a, b = firsts.get(g1), seconds.get(g2)
        if a and b:
            pairs.append((a, b))
    if len(pairs) < 2:
        seeded = [t for t in (list(firsts.values()) + list(seconds.values())) if t]
        pairs = _seed_pairs(seeded[: field_size(len(seeded), 8)])
    ev["phase"] = "playoff"
    stages = PLAYOFF_STAGES.get(len(pairs) * 2) or ["GF"]
    ev["playoff_stages"] = stages
    ev["playoff_day0"] = len(ev["dates"]) - len(stages)
    day = _day(ev, ev["playoff_day0"])
    return [_mk(ev, stages[0], day, a, b, 3) for a, b in pairs]


# --------------------------------------------------------------------------
# dispatcher


def open_event(ev: dict, field: list[str]) -> list[dict]:
    fmt, size = resolve_format(ev, len(field))
    field = field[:size]
    ev["field"] = field
    ev["resolved_format"] = fmt
    ev["matches"] = []
    if fmt == "swiss_playoff":
        return _open_swiss(ev, field)
    if fmt == "gsl_playoff":
        return _open_gsl(ev, field)
    return _open_single_elim(ev, field)


def advance_event(ev: dict) -> list[dict]:
    fmt = ev.get("resolved_format") or ev.get("format", "single_elim")
    phase = ev.get("phase")
    if fmt == "swiss_playoff" and phase == "swiss":
        return _advance_swiss(ev)
    if fmt == "gsl_playoff" and phase == "groups":
        return _advance_gsl(ev)
    return _advance_playoff(ev, ev.get("playoff_day0", 0))


def is_complete(ev: dict) -> bool:
    return ev.get("phase") == "playoff" and _has(ev, "GF") and _stage_done(ev, "GF")


def champion_of(ev: dict) -> str | None:
    gf = [m for m in ev["matches"] if m["stage"] == "GF" and m["played"]]
    return gf[0]["winner"] if gf else None


def rematch_count(ev: dict) -> int:
    seen = [tuple(sorted((m["team_a"], m["team_b"]))) for m in ev["matches"] if m["played"]]
    return len(seen) - len(set(seen))


def all_pairs(field: list[str]) -> list[tuple[str, str]]:
    return list(combinations(field, 2))
