# coding=utf-8
"""The season: calendar, invites, brackets, ranking points, awards, rollover."""

from __future__ import annotations

import json
from datetime import date, datetime

from ..cs2 import cs2_to_map, read_result, result_usable, start_match, to_cs2_map
from ..engine import (
    after_event,
    after_series,
    init_mentality,
    play_map,
    play_series,
    rest_delta,
    series_ratings,
    shift_mentality,
    travel_delta,
    veto_maps,
)
from ..engine.rating import kda_rating
from ..paths import data_file, save_file
from ..world import MAPS, apply_roles, build_teams, crest
from . import awards, formats
from .vrs import VRS

STATE_PATH = save_file("season.json")

PRIZE_SPLIT = awards.PRIZE_SPLIT


def load_calendar() -> dict:
    return json.loads(data_file("calendar.json").read_text(encoding="utf-8"))


CAL_RAW = load_calendar()


MAJOR_TITLES = {
    2024: {
        "major-1": ("Copenhagen Major 2024", "Copenhagen"),
        "major-2": ("Shanghai Major 2024", "Shanghai"),
    }
}


def calendar_for(year: int) -> dict:
    blob = json.loads(json.dumps(CAL_RAW))
    base = str(blob.get("season", 2026))
    blob["season"] = year
    blob["start"] = f"{year}-01-08"
    kept = []
    for ev in blob["events"]:
        if ev.get("gate") == "rmr" and year >= 2025:
            continue
        ev["dates"] = [d.replace(base, str(year), 1) for d in ev["dates"]]
        ev["name"] = ev["name"].replace(base, str(year))
        title = (MAJOR_TITLES.get(year) or {}).get(ev["id"])
        if title:
            ev["name"], ev["short"] = title
        kept.append(ev)
    blob["events"] = kept
    return blob


def _d(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _find(teams: list[dict], name_or_id: str) -> dict:
    for t in teams:
        if t["id"] == name_or_id or t["name"] == name_or_id:
            return t
    raise KeyError(name_or_id)


def _blank_event(ev: dict) -> dict:
    ev.setdefault("status", "upcoming")
    ev.setdefault("matches", [])
    ev.setdefault("champion", None)
    ev.setdefault("field", [])
    ev.setdefault("phase", None)
    ev.setdefault("qualified_out", [])
    ev.setdefault("awards", None)
    return ev


class Season:
    def __init__(self, year: int = 2026, era: str = "2026") -> None:
        cal = calendar_for(year)
        self.year = year
        self.era = era
        self.career = None
        self.teams = build_teams(era, year)
        init_mentality(self.teams)
        self.date = cal["start"]
        self.vrs = VRS()
        self.vrs.seed(self.teams, self.date)
        self.events = [_blank_event(e) for e in json.loads(json.dumps(cal["events"]))]
        self.qualified: dict[str, list[str]] = {}
        self.player_all: dict[str, dict] = {}
        self.player_event: dict[str, dict] = {}
        self.history: list[dict] = []
        self.top20: dict[str, list[dict]] = {}
        self.log: list[str] = [f"{year} 赛季开始。"]

    # ---------------------------------------------------------------- tables

    def team_map(self) -> dict[str, dict]:
        return {t["id"]: t for t in self.teams}

    def ranked(self) -> list[dict]:
        tm = self.team_map()
        return [tm[row["id"]] for row in self.vrs.table(self.teams, self.date)]

    def records(self) -> list[dict]:
        done = [awards.make_record(ev) for ev in self.events if ev.get("status") == "done"]
        return self.history + done

    # ---------------------------------------------------------------- invites

    def major_uses_rmr(self) -> bool:
        return self.year < 2025

    def dest_direct(self, ev: dict) -> int:
        if ev.get("direct"):
            return int(ev["direct"])
        if ev["type"] == "major":
            return 8 if self.major_uses_rmr() else int(ev.get("size", 16))
        return int(ev.get("size", 16))

    def has_qualifier(self, ev: dict) -> bool:
        if ev.get("type") == "major" and not self.major_uses_rmr():
            return False
        return any(e.get("feeds") == ev["id"] for e in self.events)

    def field_for(self, ev: dict) -> list[dict]:
        ranked = self.ranked()
        kind = ev["type"]
        size = ev.get("size", 8)
        region = ev.get("region")

        if kind in ("major", "t1"):
            return self._field_invited(ev)

        lo, hi = ev.get("band") or (1, len(ranked))
        in_band = [t for i, t in enumerate(ranked, 1) if lo <= i <= hi]
        rest = [t for t in ranked if t not in in_band]
        dest = next((e for e in self.events if e["id"] == ev.get("feeds")), None)
        skip = set()
        if dest:
            skip = {t["id"] for t in ranked[: self.dest_direct(dest)]}

        if kind == "qual":
            global_pi = ev.get("scope") == "global" or (dest and dest.get("type") == "t1")
            if global_pi:
                pool = [t for t in ranked if t["id"] not in skip]
            else:
                pool = [t for t in ranked if t["region"] == region and t["id"] not in skip]
        elif kind == "cct":
            pool = [t for t in in_band if t["region"] == region]
            pool += [t for t in rest if t["region"] == region]
        else:  # t2 and anything else: global, but skip the very top
            pool = list(in_band) + rest

        if len(pool) < size:
            have = {t["id"] for t in pool}
            pool += [t for t in ranked if t["id"] not in have]
        return self._inject_career(ev, pool[:size])

    def _field_invited(self, ev: dict) -> list[dict]:
        ranked = self.ranked()
        size = ev.get("size", 8)
        if not self.has_qualifier(ev):
            return self._inject_career(ev, ranked[:size])
        picked: list[dict] = []
        seen: set[str] = set()
        for tid in self.qualified.get(ev["id"], []):
            team = self.team_map().get(tid)
            if team and tid not in seen:
                picked.append(team)
                seen.add(tid)
        for t in ranked[: self.dest_direct(ev)]:
            if len(picked) >= size:
                break
            if t["id"] not in seen:
                picked.append(t)
                seen.add(t["id"])
        for t in ranked:
            if len(picked) >= size:
                break
            if t["id"] not in seen:
                picked.append(t)
                seen.add(t["id"])
        order = {t["id"]: i for i, t in enumerate(ranked)}
        picked.sort(key=lambda t: order.get(t["id"], 99))
        return self._inject_career(ev, picked[:size])

    def _inject_career(self, ev: dict, picked: list[dict]) -> list[dict]:
        """Player team plays only after accepting the invite mail."""
        career = getattr(self, "career", None)
        size = ev.get("size", 8)
        if not career or not career.exists:
            return picked[:size]
        mine = self.team_map().get(career.team_id)
        if not mine:
            return picked[:size]
        accepted = ev["id"] in (career.registered or [])
        if ev.get("type") in ("major", "t1") and not self._earned_slot(ev, mine):
            accepted = False
        picked = [t for t in picked if t["id"] != mine["id"]]
        if accepted:
            ranked = self.ranked()
            order = {t["id"]: i for i, t in enumerate(ranked)}
            picked.append(mine)
            picked.sort(key=lambda t: order.get(t["id"], 99))
        if len(picked) < size:
            have = {t["id"] for t in picked} | ({mine["id"]} if not accepted else set())
            for t in self.ranked():
                if t["id"] not in have:
                    picked.append(t)
                    have.add(t["id"])
                if len(picked) >= size:
                    break
        picked = picked[:size]
        if accepted and picked and not any(t["id"] == mine["id"] for t in picked):
            picked[-1] = mine
        elif accepted and not picked:
            picked = [mine]
        return picked

    def _earned_slot(self, ev: dict, team: dict) -> bool:
        if team["id"] in (self.qualified.get(ev["id"]) or []):
            return True
        return any(t["id"] == team["id"] for t in self.ranked()[: self.dest_direct(ev)])

    # ---------------------------------------------------------------- events

    def _schedule(self, ev: dict, matches: list[dict]) -> None:
        for m in matches:
            if _d(m["date"]) < _d(self.date):
                m["date"] = self.date
            ev["matches"].append(m)

    def open_event(self, ev: dict) -> None:
        if ev["status"] != "upcoming":
            return
        field = self.field_for(ev)
        if len(field) < 2:
            ev["status"] = "done"
            self.log.append(f"{ev['name']} 人数不足，取消。")
            return

        start = ev["dates"][0]
        rest_days = max(1, (_d(start) - _d(self.date)).days) if _d(self.date) < _d(start) else 8
        for t in field:
            before = t["mentality"]
            rd, rtag = rest_delta(rest_days)
            td, ttag = travel_delta(t.get("last_region", t["region"]), ev["region"])
            shift_mentality(t, rd + td)
            t["last_region"] = ev["region"]
            t.setdefault("mentality_log", []).append(
                {
                    "event": ev["id"],
                    "when": "arrive",
                    "before": before,
                    "after": t["mentality"],
                    "rest": rtag,
                    "travel": ttag,
                }
            )

        opening = formats.open_event(ev, [t["name"] for t in field])
        ev["status"] = "live"
        ev["matches"] = []
        self._schedule(ev, opening)
        self.log.append(f"{ev['name']} 开赛，{len(ev['field'])} 支队伍。")
        if self.career:
            self.career.maybe_major_coach(self, ev)
            self.career.watch(self, ev)

    def advance_event(self, ev: dict) -> None:
        guard = 0
        while guard < 12:
            guard += 1
            if formats.is_complete(ev):
                self.finish_event(ev)
                return
            fresh = formats.advance_event(ev)
            if not fresh:
                return
            self._schedule(ev, fresh)
            if any(not m["played"] for m in fresh):
                return

    def finish_event(self, ev: dict) -> None:
        if ev["status"] == "done":
            return
        ev["champion"] = formats.champion_of(ev)
        ev["status"] = "done"
        place = awards.placements(ev)

        champ_team = next((t for t in self.teams if t["name"] == ev["champion"]), None)
        ev["champion_roster"] = [p["name"] for p in champ_team["players"]] if champ_team else []

        store = self.player_event.get(ev["id"]) or {}
        ev["awards"] = awards.event_awards(ev, store)

        pool = ev.get("prize", 0)
        player_id = getattr(getattr(self, "career", None), "team_id", "")
        if pool:
            for name, spot in place.items():
                team = next((t for t in self.teams if t["name"] == name), None)
                if not team:
                    continue
                if player_id and team["id"] == player_id:
                    continue
                team["money"] = team.get("money", 0) + int(pool * PRIZE_SPLIT.get(spot, 0.0))

        after_event(self.teams, {"event": ev["id"], "champion": ev["champion"], "matches": ev["matches"]})
        if ev["type"] == "qual":
            self._collect_qualifiers(ev)

        mvp = (ev["awards"] or {}).get("mvp")
        tail = f"，MVP {mvp['player']}" if mvp else ""
        self.log.append(f"{ev['name']} 冠军：{ev['champion']}{tail}")
        if self.career:
            self.career.award_event(self, ev)
            if not any(e.get("status") in ("upcoming", "live") for e in self.events):
                self.career.on_top20_eve(self)

    def _collect_qualifiers(self, ev: dict) -> None:
        feeds = ev.get("feeds")
        if not feeds:
            return
        gf = next((m for m in ev["matches"] if m["stage"] == "GF" and m["played"]), None)
        if not gf:
            return
        names = [gf["winner"], gf["team_a"] if gf["winner"] != gf["team_a"] else gf["team_b"]]
        need = ev.get("qualify", 2)
        if need >= 3:
            losers = []
            for m in ev["matches"]:
                if m["stage"] == "SF" and m["played"] and m["team_b"] != "BYE":
                    losers.append(m["team_a"] if m["winner"] != m["team_a"] else m["team_b"])
            losers.sort(key=lambda n: -self.vrs.live(_find(self.teams, n)["id"], self.date))
            names += losers[: need - 2]
        ids = []
        for name in names[:need]:
            try:
                ids.append(_find(self.teams, name)["id"])
            except KeyError:
                continue
        ev["qualified_out"] = ids
        bucket = self.qualified.setdefault(feeds, [])
        for tid in ids:
            if tid not in bucket:
                bucket.append(tid)

    # ---------------------------------------------------------------- playing

    def _add_player(self, store: dict, team: str, p: dict, rounds: int) -> None:
        row = store.setdefault(
            f"{team}|{p['name']}",
            {"team": team, "player": p["name"], "maps": 0, "rounds": 0, "k": 0, "d": 0, "a": 0},
        )
        row["maps"] += 1
        row["rounds"] += rounds
        row["k"] += p["k"]
        row["d"] += p["d"]
        row["a"] += p["a"]

    def _book_stats(self, ev: dict, match: dict, team_a: dict, team_b: dict) -> None:
        win, lose = (team_a, team_b) if match["winner"] == team_a["name"] else (team_b, team_a)
        best_of = match.get("best_of", 3)
        weight = ev["vrs_weight"] * (0.75 if best_of == 1 else 1.0)
        self.vrs.award_series(win, lose, weight, match["date"], ev["id"])
        store = self.player_event.setdefault(ev["id"], {})
        for mp in match.get("maps") or []:
            for team, lines in mp["players"].items():
                for p in lines:
                    self._add_player(self.player_all, team, p, mp["rounds"])
                    self._add_player(store, team, p, mp["rounds"])

    def your_team_name(self) -> str:
        career = self.career
        if not career or not getattr(career, "exists", False):
            return ""
        team = career.my_team(self.teams)
        return team["name"] if team else ""

    def is_yours(self, match: dict) -> bool:
        name = self.your_team_name()
        if not name or match.get("team_b") == "BYE":
            return False
        return match.get("team_a") == name or match.get("team_b") == name

    def find_match(self, match_id: str) -> tuple[dict, dict] | tuple[None, None]:
        for ev in self.events:
            for m in ev["matches"]:
                if m["id"] == match_id:
                    return ev, m
        return None, None

    def _map_wins(self, match: dict) -> tuple[int, int]:
        wa = wb = 0
        for mp in match.get("maps") or []:
            if mp.get("winner") == match["team_a"]:
                wa += 1
            elif mp.get("winner") == match["team_b"]:
                wb += 1
        return wa, wb

    def _series_over(self, match: dict) -> bool:
        need = match.get("best_of", 3) // 2 + 1
        return max(self._map_wins(match)) >= need

    def _live_series(self, match: dict) -> str | None:
        if match.get("played") and match.get("series"):
            return match["series"]
        wa, wb = self._map_wins(match)
        if wa or wb or match.get("maps"):
            return f"{wa}-{wb}"
        return None

    def your_series(self) -> tuple[dict, dict] | None:
        open_ones: list[tuple[dict, dict]] = []
        due_ones: list[tuple[dict, dict]] = []
        today = _d(self.date)
        for ev in self.events:
            if ev["status"] != "live":
                continue
            for m in ev["matches"]:
                if m.get("played") or not self.is_yours(m):
                    continue
                if m.get("human") or m.get("veto") or m.get("maps") or m.get("cs2_session"):
                    open_ones.append((ev, m))
                elif _d(m["date"]) <= today:
                    due_ones.append((ev, m))
        rows = open_ones or due_ones
        if not rows:
            return None
        rows.sort(key=lambda item: (item[1]["date"], item[1]["id"]))
        ev, match = rows[0]
        self.open_your_series(ev, match)
        return ev, match

    def yours_ready(self, match: dict) -> bool:
        if match.get("played") or not self.is_yours(match):
            return False
        if match.get("human") or match.get("veto") or match.get("maps") or match.get("cs2_session"):
            return True
        return _d(match["date"]) <= _d(self.date)

    def _require_yours(self, match_id: str) -> tuple[dict, dict]:
        ev, match = self.find_match(match_id)
        if not ev or not match:
            raise ValueError("找不到这场比赛")
        if not self.is_yours(match):
            raise ValueError("这不是你的比赛")
        if not self.yours_ready(match):
            raise ValueError("还没到比赛日")
        return ev, match

    def open_your_series(self, ev: dict, match: dict) -> None:
        if match.get("played") or match.get("team_b") == "BYE":
            return
        match["human"] = True
        if not match.get("veto"):
            a = _find(self.teams, match["team_a"])
            b = _find(self.teams, match["team_b"])
            match["veto"] = veto_maps(a, b, MAPS, match.get("best_of", 3))
            match.setdefault("maps", [])
        if self._series_over(match):
            match["pending_map"] = None
            return
        done = len(match.get("maps") or [])
        order = (match.get("veto") or {}).get("order") or []
        match["pending_map"] = order[done] if done < len(order) else None

    def _finalize_human(self, ev: dict, match: dict) -> None:
        a = _find(self.teams, match["team_a"])
        b = _find(self.teams, match["team_b"])
        wa, wb = self._map_wins(match)
        winner = a["name"] if wa > wb else b["name"]
        match["played"] = True
        match["winner"] = winner
        match["series"] = f"{wa}-{wb}"
        match["ratings"] = series_ratings(match.get("maps") or [])
        match["pending_map"] = None
        match["cs2_session"] = None
        after_series(a, b, {"winner": winner, "stage": match["stage"]})
        self._book_stats(ev, match, a, b)
        self.advance_event(ev)
        if self.career:
            self.career.on_series_done(self)
            self.career.watch(self)

    def launch_your_map(self, match_id: str, side: str = "ct") -> str:
        if self.career:
            block = self.career.gate_match(self, match_id)
            if block:
                raise ValueError(block)
        ev, match = self._require_yours(match_id)
        self.open_your_series(ev, match)
        if match.get("played"):
            raise ValueError("这场已经打完了")
        session = match.get("cs2_session")
        raw = read_result()
        if session and result_usable(raw, session) == "":
            msg = self.commit_cs2_map(match_id, raw)
            if match.get("played"):
                return msg
        pending = match.get("pending_map")
        if not pending:
            raise ValueError("没有待打的地图")
        mine = self.career.my_team(self.teams) if self.career else None
        if not mine:
            raise ValueError("先创建生涯")
        opp_name = match["team_b"] if match["team_a"] == mine["name"] else match["team_a"]
        opp = _find(self.teams, opp_name)
        side = "t" if side == "t" else "ct"
        match["cs2_session"] = {
            "match_id": match_id,
            "map": pending,
            "cs2_map": to_cs2_map(pending),
            "side": side,
            "started_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "my_team": mine["name"],
            "opp": opp["name"],
            "map_index": len(match.get("maps") or []),
        }
        out = start_match(
            mine, opp, self.career.player_name, to_cs2_map(pending), side, self.teams, self.career
        )
        n = match["cs2_session"]["map_index"] + 1
        return f"第 {n} 图 {pending}。{out['msg']}"

    def commit_cs2_map(self, match_id: str, raw: dict | None = None) -> str:
        ev, match = self._require_yours(match_id)
        if match.get("played"):
            raise ValueError("这场已经打完了")
        session = match.get("cs2_session")
        if not session:
            raise ValueError("还没有进入当场比赛")
        result = raw if raw is not None else read_result()
        err = result_usable(result, session)
        if err:
            raise ValueError(err)
        if match.get("last_ended_at") and match["last_ended_at"] == result.get("ended_at"):
            return "这张图的战绩已经录入了"
        a = _find(self.teams, match["team_a"])
        b = _find(self.teams, match["team_b"])
        box = cs2_to_map(result, session, a, b, self.career.player_name)
        maps = match.setdefault("maps", [])
        idx = session.get("map_index")
        if idx is None:
            idx = len(maps)
        idx = int(idx)
        if idx < len(maps):
            maps[idx] = box
            del maps[idx + 1 :]
        else:
            maps.append(box)
        match["last_ended_at"] = result.get("ended_at")
        match["cs2_session"] = None
        n = idx + 1
        if self._series_over(match):
            self._finalize_human(ev, match)
            return f"第 {n} 图 {box['score']}，系列赛结束 {match['series']}。"
        self.open_your_series(ev, match)
        nxt = match.get("pending_map")
        return f"第 {n} 图结束 {box['score']}。下一张：{nxt}。"

    def skip_your_series(self, match_id: str) -> str:
        if self.career:
            block = self.career.gate_match(self, match_id)
            if block:
                raise ValueError(block)
        ev, match = self._require_yours(match_id)
        if match.get("played"):
            raise ValueError("这场已经打完了")
        self.open_your_series(ev, match)
        a = _find(self.teams, match["team_a"])
        b = _find(self.teams, match["team_b"])
        need = match.get("best_of", 3) // 2 + 1
        maps = match.setdefault("maps", [])
        kept = sum(1 for mp in maps if mp.get("source") == "cs2")
        wa, wb = self._map_wins(match)
        wins = {a["name"]: wa, b["name"]: wb}
        order = (match.get("veto") or {}).get("order") or []
        for map_name in order[len(maps) :]:
            if max(wins.values()) >= need:
                break
            box = play_map(a, b, map_name)
            box["source"] = "sim"
            maps.append(box)
            wins[box["winner"]] = wins.get(box["winner"], 0) + 1
        self._finalize_human(ev, match)
        if kept:
            return f"前 {kept} 图保留你打的战绩，剩余按数值结算：{match['series']}。"
        return f"已按角色数值结算：{a['name']} {match['series']} {b['name']}。"

    def _forfeit_yours(self, ev: dict, match: dict) -> None:
        mine = self.career.my_team(self.teams) if self.career else None
        if not mine:
            return
        opp = match["team_b"] if match["team_a"] == mine["name"] else match["team_a"]
        need = match.get("best_of", 3) // 2 + 1
        wa, wb = (0, need) if match["team_a"] == mine["name"] else (need, 0)
        match["played"] = True
        match["winner"] = opp
        match["series"] = f"{wa}-{wb}"
        match["maps"] = match.get("maps") or []
        match["forfeit"] = True
        match["pending_map"] = None
        match["cs2_session"] = None
        a = _find(self.teams, match["team_a"])
        b = _find(self.teams, match["team_b"])
        after_series(a, b, {"winner": opp, "stage": match["stage"]})
        self._book_stats(ev, match, a, b)
        self.advance_event(ev)

    def play_match(self, ev: dict, match: dict) -> None:
        if match["played"] or match["team_b"] == "BYE":
            return
        if self.is_yours(match):
            if self.career and getattr(self.career, "banned", False):
                self._forfeit_yours(ev, match)
            return
        a = _find(self.teams, match["team_a"])
        b = _find(self.teams, match["team_b"])
        best_of = match.get("best_of", 3)
        series = play_series(a, b, MAPS, match["stage"], best_of)

        match["played"] = True
        match["winner"] = series["winner"]
        match["series"] = series["series"]
        match["maps"] = series["maps"]
        match["veto"] = series["veto"]
        match["ratings"] = series["ratings"]
        self._book_stats(ev, match, a, b)

    def due_matches(self) -> list[tuple[dict, dict]]:
        """Everything unplayed that today has caught up with.

        Anything already overdue counts too: skipping ahead must never leave a
        fixture stranded in the past, or its event would stay live forever.
        """
        today = _d(self.date)
        out = []
        for ev in self.events:
            if ev["status"] != "live":
                continue
            for m in ev["matches"]:
                if not m["played"] and _d(m["date"]) <= today:
                    out.append((ev, m))
        return out

    def matches_on(self, day: str) -> list[tuple[dict, dict]]:
        return [
            (ev, m)
            for ev in self.events
            if ev["status"] == "live"
            for m in ev["matches"]
            if m["date"] == day and not m["played"]
        ]

    def ensure_live(self) -> None:
        today = _d(self.date)
        for ev in self.events:
            if ev["status"] == "upcoming" and _d(ev["dates"][0]) <= today:
                self.open_event(ev)

    def _next_busy_day(self) -> str | None:
        today = _d(self.date)
        days = []
        for ev in self.events:
            if ev["status"] == "done":
                continue
            if ev["status"] == "upcoming" and _d(ev["dates"][0]) > today:
                days.append(ev["dates"][0])
            for m in ev["matches"]:
                if not m["played"] and _d(m["date"]) > today:
                    days.append(m["date"])
        return min(days) if days else None

    def next_stage(self) -> str:
        if self.career:
            self.career.dispatch_invites(self)
        self.ensure_live()
        for ev in self.events:
            if ev["status"] == "live":
                self.advance_event(ev)

        jumped = False
        if not self.due_matches():
            nxt = self._next_busy_day()
            if not nxt:
                return self.roll_year()
            self.date = nxt
            self.ensure_live()
            jumped = True

        played = 0
        guard = 0
        while guard < 60:
            guard += 1
            pending = [(e, m) for e, m in self.due_matches() if not self.is_yours(m)]
            if not pending:
                break
            for ev, m in pending:
                self.play_match(ev, m)
                played += 1
            for ev in {id(p[0]): p[0] for p in pending}.values():
                self.advance_event(ev)

        yours = self.your_series()
        if yours:
            ev, match = yours
            self.open_your_series(ev, match)

        self.vrs.prune(self.date)
        head = f"推进到 {self.date}" if jumped else self.date
        if yours:
            _ev, match = yours
            extra = f"{head}，进行了 {played} 场比赛。" if played else head
            msg = (
                f"{extra} 轮到你上场：{match['team_a']} vs {match['team_b']}，"
                f"BO{match.get('best_of', 3)}。"
            )
        else:
            msg = f"{head}，进行了 {played} 场比赛。"
        self.log.append(msg)
        if self.career:
            self.career.tick(self, self.date)
            self.career.watch(self)
        return msg

    def skip_to_next_event(self) -> str:
        """Finish every running event, then land on the next one's opening day."""
        if self.career:
            self.career.dispatch_invites(self)
        yours = self.your_series()
        if yours:
            ev, match = yours
            self.open_your_series(ev, match)
            return f"先打完或跳过你的比赛：{match['team_a']} vs {match['team_b']}"
        guard = 0
        while any(e["status"] == "live" for e in self.events) and guard < 200:
            guard += 1
            before = (self.date, sum(1 for e in self.events if e["status"] == "live"))
            self.next_stage()
            yours = self.your_series()
            if yours:
                ev, match = yours
                return f"先打完或跳过你的比赛：{match['team_a']} vs {match['team_b']}"
            if (self.date, sum(1 for e in self.events if e["status"] == "live")) == before:
                break
        nxt = next((e for e in self.events if e["status"] == "upcoming"), None)
        if not nxt:
            return self.roll_year()
        self.date = nxt["dates"][0]
        self.ensure_live()
        for ev in self.events:
            if ev["status"] == "live":
                self.advance_event(ev)
        msg = f"来到 {nxt['name']}（{self.date}）。"
        self.log.append(msg)
        if self.career:
            self.career.tick(self, self.date)
            self.career.watch(self)
        return msg

    # ---------------------------------------------------------------- rollover

    def roll_year(self) -> str:
        finished = [awards.make_record(ev) for ev in self.events if ev.get("status") == "done"]
        table = awards.top20(self.ratings_vs_field(), finished)
        self.top20[str(self.year)] = table
        self.history += finished

        best = table[0]["player"] if table else "—"
        old = self.year
        if self.career:
            self.career.on_year_end(self, old, table)
        self.year += 1
        cal = calendar_for(self.year)
        self.events = [_blank_event(e) for e in json.loads(json.dumps(cal["events"]))]
        self.qualified = {}
        self.player_all = {}
        self.player_event = {}
        self.date = cal["start"]
        for t in self.teams:
            t["series_streak"] = 0
            t["loss_streak"] = 0
            t["mentality_log"] = []
        from ..world.aging import apply_year

        apply_year(self.teams)
        msg = f"{old} 赛季结束。年度第一：{best}。{self.year} 赛季开始。"
        self.log.append(msg)
        if self.career:
            self.career.tick(self, self.date)
            self.career.dispatch_invites(self)
        return msg

    # ---------------------------------------------------------------- ratings

    def ratings(self, store: dict) -> list[dict]:
        rows = []
        for row in store.values():
            rec = dict(row)
            rec["kd"] = round(row["k"] / max(1, row["d"]), 2)
            rec["kpr"] = round(row["k"] / max(1, row["rounds"]), 3)
            rec["rating"] = kda_rating(row["k"], row["d"], row["a"], row["rounds"])
            rows.append(rec)
        rows.sort(key=lambda x: (-x["rating"], -x["kpr"]))
        return rows

    def ratings_vs_field(self) -> list[dict]:
        """Season rating vs VRS bands. Maps against teams outside the Top 30 are ignored."""
        rank = self.vrs.rank_of(self.teams, self.date)

        def blank() -> dict:
            return {"maps": 0, "rounds": 0, "k": 0, "d": 0, "a": 0}

        def add(bucket: dict, p: dict, rounds: int) -> None:
            bucket["maps"] += 1
            bucket["rounds"] += rounds
            bucket["k"] += p.get("k", 0)
            bucket["d"] += p.get("d", 0)
            bucket["a"] += p.get("a", 0)

        acc: dict[str, dict] = {}
        for ev in self.events:
            for m in ev.get("matches") or []:
                if not m.get("played"):
                    continue
                for mp in m.get("maps") or []:
                    for team, lines in (mp.get("players") or {}).items():
                        opp = m["team_b"] if team == m["team_a"] else m["team_a"]
                        opp_rank = rank.get(opp, 99)
                        if opp_rank > 30:
                            continue
                        for p in lines:
                            row = acc.setdefault(
                                f"{team}|{p['name']}",
                                {
                                    "team": team,
                                    "player": p["name"],
                                    "top30": blank(),
                                    "top5": blank(),
                                    "top10": blank(),
                                    "top20": blank(),
                                },
                            )
                            rounds = mp.get("rounds", 0)
                            add(row["top30"], p, rounds)
                            if opp_rank <= 5:
                                add(row["top5"], p, rounds)
                            if opp_rank <= 10:
                                add(row["top10"], p, rounds)
                            if opp_rank <= 20:
                                add(row["top20"], p, rounds)

        rows = []
        for row in acc.values():
            box = row["top30"]
            rec = {
                "team": row["team"],
                "player": row["player"],
                "k": box["k"],
                "d": box["d"],
                "a": box["a"],
                "rounds": box["rounds"],
                "maps": box["maps"],
                "maps_top30": box["maps"],
                "kpr": round(box["k"] / max(1, box["rounds"]), 3),
                "rating": kda_rating(box["k"], box["d"], box["a"], box["rounds"]),
                "rating_top30": kda_rating(box["k"], box["d"], box["a"], box["rounds"]),
            }
            for band in ("top5", "top10", "top20"):
                b = row[band]
                rec[f"maps_{band}"] = b["maps"]
                rec[f"rating_{band}"] = (
                    kda_rating(b["k"], b["d"], b["a"], b["rounds"]) if b["rounds"] else None
                )
            rows.append(rec)
        rows.sort(key=lambda x: (-x["rating"], -x["kpr"]))
        return rows

    def top20_live(self) -> list[dict]:
        finished = [awards.make_record(ev) for ev in self.events if ev.get("status") == "done"]
        return awards.top20(self.ratings_vs_field(), finished)

    # ---------------------------------------------------------------- payload

    def _your_match_public(self) -> dict | None:
        pair = self.your_series()
        if not pair:
            return None
        ev, m = pair
        return {
            "event": {"id": ev["id"], "name": ev["name"], "short": ev.get("short")},
            "match": {
                "id": m["id"],
                "team_a": m["team_a"],
                "team_b": m["team_b"],
                "best_of": m.get("best_of", 3),
                "series": self._live_series(m),
                "pending_map": m.get("pending_map"),
                "maps_done": len(m.get("maps") or []),
                "session": bool(m.get("cs2_session")),
                "label": m.get("label") or m.get("stage"),
            },
        }

    def match_detail(self, match_id: str) -> dict | None:
        ev, m = self.find_match(match_id)
        if not ev:
            return None
        return {
            "event": {"id": ev["id"], "name": ev["name"], "short": ev.get("short")},
            "match": m,
            "yours": self.is_yours(m),
        }

    def _event_public(self, ev: dict) -> dict:
        slim = []
        for m in ev["matches"]:
            slim.append(
                {
                    "id": m["id"],
                    "stage": m["stage"],
                    "label": m.get("label"),
                    "phase": m.get("phase"),
                    "group": (m.get("meta") or {}).get("group"),
                    "record": (m.get("meta") or {}).get("record"),
                    "kind": (m.get("meta") or {}).get("kind"),
                    "date": m["date"],
                    "best_of": m.get("best_of", 3),
                    "team_a": m["team_a"],
                    "team_b": m["team_b"],
                    "played": m["played"],
                    "winner": m["winner"],
                    "series": m.get("series") or self._live_series(m),
                    "yours": self.yours_ready(m),
                    "human": bool(m.get("human")),
                    "pending_map": m.get("pending_map"),
                    "maps": [
                        {"map": x["map"], "score": x["score"], "source": x.get("source")}
                        for x in (m.get("maps") or [])
                    ],
                }
            )
        out = {
            "id": ev["id"],
            "name": ev["name"],
            "short": ev.get("short") or ev["name"],
            "type": ev["type"],
            "class": awards.event_class(ev),
            "format": ev.get("resolved_format") or ev.get("format"),
            "region": ev["region"],
            "dates": ev["dates"],
            "status": ev["status"],
            "phase": ev.get("phase"),
            "champion": ev.get("champion"),
            "field": ev.get("field") or [],
            "prize": ev.get("prize", 0),
            "vrs_weight": ev.get("vrs_weight"),
            "direct": ev.get("direct"),
            "scope": ev.get("scope"),
            "feeds": ev.get("feeds"),
            "qualify": ev.get("qualify"),
            "qualified_out": [
                (self.team_map().get(tid) or {}).get("name") or tid
                for tid in (ev.get("qualified_out") or [])
            ],
            "awards": ev.get("awards"),
            "matches": slim,
        }
        fmt = out["format"]
        if fmt == "swiss_playoff" and ev.get("field"):
            state = formats.swiss_state(ev)
            out["swiss"] = sorted(
                (
                    {
                        "team": r["name"],
                        "w": r["w"],
                        "l": r["l"],
                        "buchholz": r["buchholz"],
                        "seed": r["seed"] + 1,
                    }
                    for r in state.values()
                ),
                key=lambda r: (-r["w"], r["l"], -r["buchholz"], r["seed"]),
            )
        if fmt == "gsl_playoff" and ev.get("gsl_field"):
            out["groups"] = formats.gsl_standings(ev)
        return out

    def public(self) -> dict:
        vrs = self.vrs.table(self.teams, self.date)
        rank = {row["name"]: row["rank"] for row in vrs}
        teams = []
        for t in self.teams:
            teams.append(
                {
                    "id": t["id"],
                    "name": t["name"],
                    "region": t["region"],
                    "tier": t["tier"],
                    "command": t["command"],
                    "money": t.get("money", 0),
                    "mentality": t.get("mentality"),
                    "strong_maps": t.get("strong_maps", []),
                    "weak_maps": t.get("weak_maps", []),
                    "crest": crest(t),
                    "rank": rank.get(t["name"]),
                    "players": t["players"],
                }
            )
        blob = {
            "date": self.date,
            "year": self.year,
            "era": self.era,
            "vrs": vrs,
            "teams": teams,
            "events": [self._event_public(ev) for ev in self.events],
            "ratings": self.ratings_vs_field()[:60],
            "top20": self.top20_live(),
            "top20_history": self.top20,
            "records": self.records(),
            "log": self.log[-10:],
            "your_match": self._your_match_public(),
        }
        if self.career:
            blob["career"] = self.career.public(self)
        else:
            from ..world import ERA_META

            blob["career"] = {"exists": False, "eras": ERA_META}
        return blob

    # ---------------------------------------------------------------- storage

    def save(self) -> None:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        blob = {
            "date": self.date,
            "year": self.year,
            "era": self.era,
            "teams": self.teams,
            "vrs": self.vrs.to_json(),
            "events": self.events,
            "qualified": self.qualified,
            "player_all": self.player_all,
            "player_event": self.player_event,
            "history": self.history,
            "top20": self.top20,
            "log": self.log,
        }
        STATE_PATH.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load_or_new(cls) -> "Season":
        if not STATE_PATH.exists():
            s = cls()
            s.save()
            return s
        try:
            blob = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            s = cls.__new__(cls)
            s.teams = blob["teams"]
            s.date = blob["date"]
            s.year = blob.get("year", int(s.date[:4]))
            s.era = blob.get("era", "2026")
            s.career = None
            s.vrs = VRS.from_json(blob["vrs"])
            s.events = [_blank_event(e) for e in blob["events"]]
            s.qualified = blob.get("qualified", {})
            s.player_all = blob.get("player_all", {})
            s.player_event = blob.get("player_event", {})
            s.history = blob.get("history", [])
            s.top20 = blob.get("top20", {})
            s.log = blob.get("log", [])
            apply_roles(s.teams)
            s._calendar_changed = s.align_calendar()
            return s
        except (KeyError, ValueError, TypeError):
            return reset_season()

    def align_calendar(self) -> bool:
        """Drop leftover 2025+ RMRs and insert missing T1 play-ins on old saves."""
        want = [_blank_event(json.loads(json.dumps(e))) for e in calendar_for(self.year)["events"]]
        want_ids = {e["id"] for e in want}
        before = [e["id"] for e in self.events]
        kept = []
        for ev in self.events:
            if ev["id"] in want_ids:
                src = next(e for e in want if e["id"] == ev["id"])
                for key in ("direct", "scope", "feeds", "qualify", "gate"):
                    if key in src:
                        ev[key] = src[key]
                kept.append(ev)
            elif ev.get("status") == "done":
                kept.append(ev)
        have = {e["id"] for e in kept}
        for ev in want:
            if ev["id"] not in have:
                kept.append(ev)
        kept.sort(key=lambda e: (e.get("dates") or [""])[0])
        self.events = kept
        return [e["id"] for e in kept] != before


def reset_season(year: int = 2026, era: str = "2026") -> Season:
    if STATE_PATH.exists():
        STATE_PATH.unlink()
    s = Season(year, era)
    s.save()
    return s
