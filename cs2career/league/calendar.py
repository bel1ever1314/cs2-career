"""Versioned tournament catalog: verified editions stay in their own year.

Names and event windows are sourced facts. Fields, prizes and brackets remain
the simulator's compact model; each event carries that distinction to the UI.
Future seasons use visibly fictional editions rather than relabeling history.
"""
from __future__ import annotations

import copy
import json
from datetime import date, timedelta

from ..paths import data_file

CATALOG_VERSION = "1.6.0"
VERIFIED_YEARS = (2024, 2025, 2026)
ADAPTATION = ("赛事实有；参赛名单、邀请名额、奖金分配及对阵由生涯模拟生成。"
              "比赛日压缩为游戏支持的赛制，保留真实开幕日和结束日。")


def _slots(start: str, end: str, count: int) -> list[str]:
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < first:
        raise ValueError("赛事结束日早于开幕日")
    span = (last - first).days
    return [(first + timedelta(days=(span * i) // (count - 1))).isoformat()
            for i in range(count)]


def _expand(row: dict, year: int, sources: dict) -> dict:
    ev = copy.deepcopy(row)
    window = ev.pop("window")
    start, end = [f"{year}-{value}" if len(value) == 5 else value for value in window]
    kind = ev["type"]
    if kind == "qual" and ev.get("regional_only"):
        ev.setdefault("scope", "regional")
    size = int(ev.setdefault("size", 32 if kind == "major" and year >= 2025 else
                             24 if kind == "major" else 16 if kind == "t1" else 8))
    ev.setdefault("format", "major_stages" if kind == "major" else
                  "gsl_playoff" if size == 16 and kind in ("t1", "t2") else "single_elim")
    rounds = ((size - 8) // 8 * 5 + 3 if ev["format"] == "major_stages" else
              8 if ev["format"] == "swiss_playoff" else
              6 if ev["format"] == "gsl_playoff" else max(2, size.bit_length() - 1))
    ev["dates"] = _slots(start, end, rounds)
    ev["real_event_dates"] = [start, end]
    ev["short"] = ev.get("short", ev["name"].replace(f" {year}", ""))
    ev.setdefault("vrs_weight", {"major": 1.35, "t1": 1.0, "t2": .65, "qual": .5, "cct": .4}[kind])
    ev.setdefault("prize", {"major": 1250000, "t1": 500000, "t2": 100000, "qual": 0, "cct": 25000}[kind])
    if kind in ("t2", "cct"):
        ev.setdefault("band", [13, 80])
    ev["catalog_version"] = CATALOG_VERSION
    ev["provenance"] = {"status": "verified_edition", "checked_on": "2026-09-27",
                        "sources": [sources[key] for key in ev.pop("source_ids")],
                        "verified_fields": ["name", "real_event_dates"],
                        "simulation_adaptations": ADAPTATION}
    return ev


def _builtin(year: int) -> dict:
    if year not in VERIFIED_YEARS:
        if year <= max(VERIFIED_YEARS):
            raise ValueError(f"没有核验过的 {year} 年赛事包，请添加对应年代日历。")
        return _future(year)
    raw = json.loads(data_file(f"calendars/{year}.json").read_text(encoding="utf-8"))
    sources = json.loads(data_file("calendars/sources.json").read_text(encoding="utf-8"))
    result = {"schema_version": 2, "season": year, "start": f"{year}-01-08",
              "catalog_version": CATALOG_VERSION, "note": ADAPTATION,
              "events": [_expand(row, year, sources) for row in raw["events"]]}
    validate_calendar(result)
    return result


def _future(year: int) -> dict:
    """Beyond the verified catalog, use explicit fictional circuit editions."""
    events = []
    for half, month in ((1, 6), (2, 12)):
        events.append({"id": f"major-{half}", "name": f"Future Major {year} — {half}（模拟）",
                       "short": f"Future Major {half}", "type": "major", "region": "EU" if half == 1 else "AS",
                       "size": 32, "format": "major_stages", "prize": 1250000, "vrs_weight": 1.35,
                       "dates": _slots(f"{year}-{month:02d}-01", f"{year}-{month:02d}-20", 18)})
    for month in (1, 2, 3, 4, 5, 7, 8, 9, 10, 11):
        events.append({"id": f"future-premier-{month}", "name": f"Career Premier {year} — {month:02d}（模拟）",
                       "short": f"Premier {month:02d}", "type": "t1", "region": "EU", "size": 16,
                       "format": "gsl_playoff", "prize": 500000, "vrs_weight": 1.0,
                       "dates": _slots(f"{year}-{month:02d}-16", f"{year}-{month:02d}-22", 6)})
        for region in ("EU", "AM", "AS"):
            events.append({"id": f"future-regional-{region}-{month}",
                           "name": f"Career Regional {region} {year} — {month:02d}（模拟）",
                           "short": f"Regional {region}", "type": "t2", "region": region, "regional_only": True,
                           "size": 8, "band": [13, 80], "format": "single_elim", "prize": 40000,
                           "vrs_weight": .6, "dates": _slots(f"{year}-{month:02d}-08", f"{year}-{month:02d}-10", 3)})
    for ev in events:
        ev["catalog_version"] = CATALOG_VERSION
        ev["fictional"] = True
        ev["provenance"] = {"status": "future_simulation", "sources": [],
                            "simulation_adaptations": "未来生涯赛程，赛事名称和日期为游戏虚构。"}
    return {"schema_version": 2, "season": year, "start": f"{year}-01-08",
            "catalog_version": CATALOG_VERSION, "note": "Future simulated season", "events": events}


def validate_calendar(blob: dict) -> None:
    events = blob.get("events") or []
    by_id = {ev["id"]: ev for ev in events}
    if len(by_id) != len(events):
        raise ValueError("赛事日历存在重复 ID")
    for ev in events:
        dates = ev["dates"]
        if not dates or dates != sorted(dates):
            raise ValueError(f"赛事 {ev['id']} 日期无效")
        for value in dates:
            if date.fromisoformat(value).year != blob["season"]:
                raise ValueError(f"赛事 {ev['id']} 跨用了其他年份")
        if "real_event_dates" in ev and (dates[0] < ev["real_event_dates"][0] or dates[-1] > ev["real_event_dates"][-1]):
            raise ValueError(f"赛事 {ev['id']} 超出核验过的日期")
        if ev.get("feeds"):
            dest = by_id.get(ev["feeds"])
            if dest is None or dates[-1] >= dest["dates"][0]:
                raise ValueError(f"赛事 {ev['id']} 晋级目标缺失或预选赛晚于正赛")


def calendar_for(year: int, *, include_extensions: bool = True) -> dict:
    result = _builtin(int(year))
    seen = {ev["id"] for ev in result["events"]}
    if include_extensions:
        from ..content import get_registry
        for payload in get_registry().payloads("events"):
            for raw in payload.get("events") or []:
                if not isinstance(raw, dict) or not raw.get("id") or raw["id"] in seen:
                    continue
                ev = copy.deepcopy(raw)
                if ev.get("years") and year not in ev["years"]:
                    continue
                dates = [f"{year}-{d}" if len(str(d)) == 5 else str(d) for d in ev.get("dates") or []]
                if not dates or any(date.fromisoformat(d).year != year for d in dates):
                    continue
                ev["dates"] = dates
                ev.setdefault("provenance", {"status": "user_extension", "sources": []})
                result["events"].append(ev)
                seen.add(ev["id"])
    result["events"].sort(key=lambda ev: (ev["dates"][0], ev["id"]))
    validate_calendar(result)
    return result


def load_calendar() -> dict:
    return calendar_for(max(VERIFIED_YEARS))


def reconcile_calendar(existing: list[dict], desired: list[dict], today: str) -> list[dict]:
    """Replace unstarted metadata; preserve real history and in-flight fixtures.

    No retroactive event is inserted into an existing September save just
    because January's catalog was corrected. IDs with started fixtures remain
    reserved, so a corrected catalog cannot create a second payout/history.
    """
    protected = [ev for ev in existing if ev.get("status", "upcoming") != "upcoming"
                 or ev.get("matches")]
    used = {ev["id"] for ev in protected}
    result = list(protected)
    prior = {ev["id"]: ev for ev in existing}
    for ev in desired:
        if ev["id"] in used or not ev.get("dates"):
            continue
        if ev["dates"][0] < today:
            previous = prior.get(ev["id"]) or {}
            # Reloading while an unchanged event is waiting to be activated is
            # not a migration: keep it rather than silently deleting that slot.
            if not (previous.get("catalog_version") == CATALOG_VERSION
                    and previous.get("dates") == ev["dates"]
                    and previous.get("name") == ev["name"]):
                continue
        result.append(copy.deepcopy(ev))
        used.add(ev["id"])
    result.sort(key=lambda ev: (ev.get("dates") or ["9999"])[0])
    return result
