"""Isolated loopback adapter for the optional Godot career demo.

Only the bootstrap imports standard-library modules. Select the demo save and
extension roots before importing ApplicationState or the existing HTTP server.
The adapter owns one state and uses its existing rules and shared server lock.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import random
import signal
import sys
import threading
from urllib.parse import parse_qs, urlparse
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_VERSION = 1
DEMO_SEED = 20260930
MAX_CALENDAR_STEPS = 24
MARKER = ".career3d-demo.json"


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".writing")
    pending.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    pending.replace(path)


def isolate(data_dir: Path) -> Path:
    """Refuse regular game folders and unmarked existing saves, without loading them."""
    root = data_dir.expanduser().resolve()
    if not data_dir.is_absolute():
        raise ValueError("--data-dir must be an explicit absolute demo directory")
    protected = ((ROOT / "save").resolve(), (ROOT / "extensions").resolve())
    if root == ROOT or any(root == p or root.is_relative_to(p) for p in protected):
        raise ValueError("The regular save/extension folders cannot be used for the 3D demo")
    if root == Path(root.anchor):
        raise ValueError("A drive root cannot be used as the demo data directory")
    marker = root / MARKER
    expected = {"kind": "cs2career-godot-demo", "protocol_version": PROTOCOL_VERSION,
                "seed": DEMO_SEED, "origin": "academy"}
    if marker.exists():
        if json.loads(marker.read_text("utf-8")) != expected:
            raise ValueError("This directory belongs to an incompatible demo")
    elif any((folder / name).exists() for folder in (root, root / "save")
             for name in ("season.json", "career.json")):
        raise ValueError("Refusing existing unmarked saves; select a new demo directory")
    root.mkdir(parents=True, exist_ok=True)
    _write_json(marker, expected)
    os.environ["CS2CAREER_SAVE_DIR"] = str(root / "save")
    os.environ["CS2CAREER_EXTENSION_DIR"] = str(root / "extensions")
    os.environ["CS2CAREER_NO_GAME"] = "1"
    (root / "save").mkdir(exist_ok=True)
    (root / "extensions").mkdir(exist_ok=True)
    return root


def _lock_directory(data_dir: Path):
    """Keep a second demo process from loading and writing the same save pair."""
    handle = (data_dir / ".service.lock").open("a+b")
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise ValueError("A 3D demo service is already using this data directory") from None
    return handle


def _player(row: dict) -> dict:
    from cs2career.world.ability import playing_ability
    return {"id": row.get("player_id", ""), "name": row.get("name", ""),
            "role": row.get("role", ""), "ability": round(playing_ability(row), 1) if row else 0,
            "age": row.get("age", 0)}


def _player_matches(state):
    """Read fixtures without your_series(), which opens a veto and mutates state."""
    s = state.season
    return sorted(((ev, match) for ev in s.events if ev.get("status") == "live"
                   for match in ev.get("matches", [])
                   if not match.get("played") and s.is_yours(match)),
                  key=lambda pair: (pair[1]["date"], pair[1]["id"]))


def _due_player_match(state):
    return next(((ev, m) for ev, m in _player_matches(state)
                 if m["date"] <= state.season.date or m.get("human") or m.get("veto")
                 or m.get("maps") or m.get("cs2_session")), None)


def _store(state) -> dict:
    return state.career.incident_state.setdefault("career3d_service", {"revision": 0, "receipts": []})


def _revision(state) -> int:
    return int(state.career.incident_state.get("career3d_service", {}).get("revision", 0))


def read_context(state, display_hour=8) -> dict:
    """Small read-only projection. Opening the phone cannot roll or save outcomes."""
    from cs2career.career.fast_mode import season_mode
    c, s = state.career, state.season
    mine = c.my_team(s.teams) or {}
    you = c.my_player(s.teams) or c.you_card or {}
    ranking = next((r["rank"] for r in s.vrs.table(s.teams, s.date) if r["id"] == c.team_id), None)
    pairs = _player_matches(state)
    nextmatch = None
    if pairs:
        ev, m = pairs[0]
        nextmatch = {"id": m["id"], "event_id": ev["id"], "event": ev["name"],
                     "date": m["date"], "opponent": m["team_b"] if m["team_a"] == mine.get("name") else m["team_a"],
                     "best_of": m.get("best_of", 3), "due": bool(_due_player_match(state)),
                     "stage": m.get("stage", ""), "series": m.get("series", "")}
    stories = [{"id": r["id"], "title": r.get("title", "生涯事件"),
                "text": r.get("text", ""), "required": True,
                "choices": [{"id": ch["id"], "label": {"相信队伍 · 仅模拟当前这一场": "继续模拟",
                            "Trust the team · Simulate this final": "Continue simulation"}.get(
                            ch.get("label", ch["id"]), ch.get("label", ch["id"]))}
                            for ch in r.get("choices", [])]}
               for r in c.story_queue if r.get("id")]
    event_lookup = {e["id"]: e for e in s.events}
    from tools.career3d_business import inbox_rows, mail_actions
    inbox = [{"id": r["id"], "kind": r.get("kind", ""), "title": r.get("title", ""),
              "body": r.get("body", ""), "date": r.get("date", ""), "status": r.get("status", ""),
              "event_id": r.get("event_id", ""), "read": bool(r.get("read")),
              "evname": event_lookup.get(r.get("event_id"), {}).get("name", r.get("evname", "")),
              **{key: r[key] for key in ('team_id', 'team', 'role', 'replace_id', 'expires', 'personal_transfer') if key in r},
              "dates": list(event_lookup.get(r.get("event_id"), {}).get("dates") or r.get("dates") or [])}
             for r in inbox_rows(state)]
    inbox = [dict(row, **mail_actions(state, c._mail(row['id']) or row)) for row in inbox]
    events = [{"date": (ev.get("dates") or [s.date])[0], "end_date": (ev.get("dates") or [s.date])[-1],
               "id": ev["id"], "name": ev["name"], "type": ev.get("type", ""),
               "registered": ev["id"] in c.registered, "played": ev.get("status") == "done"}
              for ev in s.events]
    recent = []
    for ev in s.events:
        for m in ev.get("matches", []):
            if m.get("played") and s.is_yours(m):
                recent.append({"id": m["id"], "date": m["date"], "event": ev["name"],
                               "team_a": m["team_a"], "team_b": m["team_b"],
                               "series": m.get("series", ""), "winner": m.get("winner", "")})
    recent.sort(key=lambda r: (r["date"], r["id"]), reverse=True)
    mode = season_mode(c, s)
    from tools.career3d_activities import device_context
    from tools.career3d_activities import settings_context
    from tools.career3d_matches import match_preflight, quick_context, ceremony_context
    from tools.career3d_resources import resource_context
    from tools.career3d_start import startup_context
    from tools.career3d_rts import rts_context
    from tools.career3d_social import social_context
    awards = ceremony_context(state)
    from tools.career3d_feedback import feedback_context
    return {"ok": True, "protocol_version": PROTOCOL_VERSION, "isolated": True,
            "player": _player(you), "team": {"id": mine.get("id", ""), "name": mine.get("name", ""),
              "region": mine.get("region", ""), "rank": ranking, "money": mine.get("money", 0),
              "roster": [_player(p) for p in mine.get("players", [])]},
            "date": s.date, "nextmatch": nextmatch, "stories": stories,
            "mode": "quick" if c.assist.get("quick_mode") else "normal",
            "season": {"year": s.year, "era": s.era, "phase": mode["phase"],
                       "choice_required": mode["choice_required"]},
            "clock": {"hour": display_hour, "minute": 0, "display_only": True,
                      "hourly_absence_implemented": False},
            "calendar": {"revision": _revision(state), "max_steps": MAX_CALENDAR_STEPS},
            "calendar_events": events, "inbox": inbox, "recent_matches": recent[:5],
            "training_pending": bool(c.training_session),
            "money": c.money, "attr_points": c.attr_points, "origin": c.origin,
            "personal_money": c.money, "club_money": mine.get("money", 0),
            'match_preflight': match_preflight(state), 'quick': quick_context(state),
            'settings': settings_context(state),
            'ceremony': {k: v for k, v in awards.items() if k != 'attendees'}, 'awards': awards,
            'feedback': feedback_context(state),
            **resource_context(), **device_context(state), **startup_context(state), **rts_context(state), **social_context(state)}


def _pause(state):
    """Commands use ordinary business gates; no event choices are answered here."""
    if state.arena.pending:
        return "ladder_match", "天梯比赛正在启动或等待真实回传；日期与阵容已暂停，请先录入战绩或关闭房间。"
    if state.career.training_session:
        return "training_match", "CS2 训练赛正在等待核验；日期与阵容已暂停，请先在训练页完成本次训练。"
    from cs2career.league.tournament_auto import blocker
    reason = blocker(state.career, state.season)
    if reason:
        return "story" if state.career.story_queue else "business", reason
    if _due_player_match(state):
        return "player_match", "轮到你上场：请打开职业比赛，选择模拟或进入 CS2。"
    return "", ""


@contextmanager
def _bounded_calendar(season, target: str):
    """Adapt the next-stage command's busy-day query under the shared lock.

    next_stage remains responsible for all date changes, ticks, finances,
    birthdays and match scheduling. The method is restored before releasing
    the lock, including after exceptions. No copied calendar rules or date
    assignment is introduced into the demo service.
    """
    original = season._next_busy_day
    had_override = "_next_busy_day" in season.__dict__
    def capped_day():
        real = original()
        candidate = min(real, target) if real else target
        # Also retain roster birthdays when no world fixture exists before the cap.
        occasion = season.career.next_calendar_day(season, candidate) if season.career else None
        return min(candidate, occasion) if occasion else candidate
    season._next_busy_day = capped_day
    try:
        yield
    finally:
        if had_override:
            season._next_busy_day = original
        else:
            del season._next_busy_day


def advance_calendar(state, body: dict) -> dict:
    """One bounded request, never a player simulation or automatic year roll."""
    from cs2career.career.fast_mode import season_complete, step
    target = body.get("target_date")
    if not isinstance(target, str):
        raise ValueError("target_date 必须是 YYYY-MM-DD 日期")
    try:
        target_day = date.fromisoformat(target)
    except ValueError:
        raise ValueError("target_date 必须是 YYYY-MM-DD 日期") from None
    s, c = state.season, state.career
    request_id = body.get("request_id")
    if not isinstance(request_id, str) or not 8 <= len(request_id) <= 100:
        raise ValueError("request_id 必须是 8 至 100 字符的唯一编号")
    if type(body.get("revision")) is not int:
        raise ValueError("请提供 context.calendar.revision")
    store = _store(state)
    prior = next((r for r in store["receipts"] if r["request_id"] == request_id), None)
    if prior:
        if prior["target_date"] != target:
            raise ValueError("这个 request_id 已用于另一个目标日期")
        return dict(prior["result"], replayed=True)
    if target_day.isoformat() != target or target < s.date or target_day.year != s.year:
        raise ValueError("目标日期必须在当前赛季内，且不能早于当前日期")
    if body["revision"] != store["revision"]:
        raise ValueError("生涯状态已变化，请刷新手机后继续")
    steps, status, reason, reason_code = 0, "progress", "", "step_limit"
    while steps < MAX_CALENDAR_STEPS:
        reason_code, reason = _pause(state)
        if reason:
            status = "paused"
            break
        if s.date == target:
            status, reason, reason_code = "reached", "已到达目标日期。", "target_reached"
            break
        if season_complete(s):
            status, reason, reason_code = "season_done", "本赛季已结束，请明确选择下一赛季模式。", "season_complete"
            break
        before = (s.date, sum(bool(m.get("played")) for e in s.events for m in e.get("matches", [])))
        with _bounded_calendar(s, target):
            if c.assist.get("quick_mode"):
                token = "3d:" + hashlib.sha256(f"{request_id}:{steps}".encode()).hexdigest()
                result = step(c, s, token, int(c.assist.get("step_counter") or 0))
                reason = result.get("msg", "")
            else:
                result = None
                reason = s.next_stage(stop_at_season_end=True)
        steps += 1
        state.persist()
        if s.date > target or s.year != target_day.year:
            raise RuntimeError("The bounded domain calendar crossed its target")
        reason_code, pause_reason = _pause(state)
        if pause_reason:
            status, reason = "paused", pause_reason
            break
        if result and result.get("status") == "paused":
            status, reason_code = "paused", "quick_break"
            reason = result.get("msg", "快速模式已暂停。")
            break
        if s.date == target:
            status, reason, reason_code = "reached", "已到达目标日期。", "target_reached"
            break
        after = (s.date, sum(bool(m.get("played")) for e in s.events for m in e.get("matches", [])))
        if before == after:
            status, reason_code = "paused", "no_progress"
            break
    else:
        reason = "本次有界推进已完成；可以继续请求同一目标日期。"
        reason_code = "step_limit"
    store["revision"] += 1
    receipt = {"ok": True, "actualdate": s.date, "status": status, "reason": reason,
               "reason_code": reason_code, "steps": steps, "revision": store["revision"]}
    store["receipts"].append({"request_id": request_id, "target_date": target, "result": receipt})
    store["receipts"] = store["receipts"][-32:]
    state.persist()
    return receipt


def handler_class():
    from cs2career.web.server import Handler
    class Career3DHandler(Handler):
        def do_GET(self):
            if urlparse(self.path).path not in ("/api/3d/context", "/api/3d/match", "/api/3d/team", "/api/3d/player", "/api/3d/players", "/api/3d/event", "/api/3d/news", "/api/3d/mail", "/api/3d/ladder/status",
                "/api/3d/custom/catalog", "/api/3d/custom/status",
                "/api/3d/match/preflight", "/api/3d/match/status", "/api/3d/settings", "/api/3d/tactics", "/api/3d/ceremony",
                "/api/3d/start/options", "/api/3d/start/draw", "/api/3d/saves", "/api/3d/skin-tools", "/api/3d/skin-tools/item", "/api/3d/controls/management", "/api/3d/controls/training",
                "/api/3d/controls/assistance", "/api/3d/controls/rankings", "/api/3d/controls/workshop"):
                self._json({"ok": False, "msg": "3D demo endpoint not found"}, 404)
                return
            super().do_GET()

        def _get(self):
            url = urlparse(self.path)
            if url.path == "/api/3d/context":
                self._json(read_context(self.state, self.server.display_hour))
            elif url.path in ('/api/3d/skin-tools', '/api/3d/skin-tools/item'):
                from tools.career3d_skin_tools import tools_context, item_context
                try:
                    if url.path.endswith('/item'):
                        query = parse_qs(url.query, keep_blank_values=True)
                        ids = query.get('id', [])
                        if len(ids) != 1 or set(query) != {'id'}:
                            raise ValueError('请提供一个库存饰品 ID。')
                        result = item_context(self.state, ids[0])
                    else:
                        result = tools_context(self.state)
                    self._json({'ok': True, **result})
                except (ValueError, OSError) as exc:
                    self._json({'ok': False, 'msg': str(exc)}, 400)
            elif url.path == '/api/3d/saves':
                from tools.career3d_saves import saves_context
                try:
                    self._json(saves_context(self.state))
                except (ValueError, OSError) as exc:
                    self._json({'ok': False, 'msg': str(exc)}, 400)
            elif url.path == '/api/3d/start/options':
                from tools.career3d_start import creation_options
                try:
                    self._json(creation_options((parse_qs(url.query).get('era') or ['2026'])[0]))
                except ValueError as exc:
                    self._json({'ok': False, 'msg': str(exc)}, 400)
            elif url.path == '/api/3d/start/draw':
                from tools.career3d_attribute_draw import draw_context
                try:
                    self._json({'ok': True, **draw_context(self.state,
                        (parse_qs(url.query).get('era') or ['2026'])[0])})
                except ValueError as exc:
                    self._json({'ok': False, 'msg': str(exc)}, 400)
            elif url.path.startswith('/api/3d/controls/'):
                from tools.career3d_controls import controls_context
                query = parse_qs(url.query)
                try:
                    options = {}
                    if url.path.endswith('/rankings'):
                        year = (query.get('year') or [''])[0]
                        options = dict(board=(query.get('board') or ['top20'])[0],
                            year=int(year) if year else None, page=int((query.get('page') or ['1'])[0]),
                            search=(query.get('search') or [''])[0])
                    self._json(controls_context(self.state, url.path.rsplit('/', 1)[1], **options))
                except ValueError as exc:
                    self._json({'ok': False, 'msg': str(exc)}, 400)
            elif url.path in ('/api/3d/match/preflight', '/api/3d/match/status'):
                from tools.career3d_matches import match_preflight, match_status
                ident = (parse_qs(url.query).get('id') or [''])[0]
                if url.path.endswith('/status'):
                    self._json(match_status(self.state, ident))
                else:
                    self._json({'ok': True, 'preflight': match_preflight(self.state, ident)})
            elif url.path == '/api/3d/settings':
                from tools.career3d_activities import settings_context
                self._json({'ok': True, 'settings': settings_context(self.state)})
            elif url.path in ('/api/3d/tactics', '/api/3d/ceremony'):
                from tools.career3d_matches import tactics_context, ceremony_context
                query = parse_qs(url.query)
                try:
                    if url.path.endswith('/tactics'):
                        self._json(tactics_context((query.get('map') or ['de_dust2'])[0]))
                    else:
                        value = (query.get('year') or [''])[0]
                        if value and (not value.isdigit() or not 2000 <= int(value) <= 3000):
                            raise ValueError('年度必须是有效的年份。')
                        self._json({'ok': True, 'awards': ceremony_context(self.state, int(value) if value else None)})
                except ValueError as exc:
                    self._json({'ok': False, 'msg': str(exc)}, 400)
            elif url.path == "/api/3d/ladder/status":
                from tools.career3d_activities import ladder_status
                self._json(ladder_status(self.state))
            elif url.path == '/api/3d/custom/status':
                from tools.career3d_activities import custom_status
                self._json(custom_status(self.state))
            elif url.path == '/api/3d/custom/catalog':
                from tools.career3d_activities import custom_catalog
                query = parse_qs(url.query)
                try:
                    self._json(custom_catalog(self.state, page=int((query.get('page') or ['1'])[0]),
                        search=(query.get('search') or [''])[0], page_size=int((query.get('page_size') or ['20'])[0])))
                except ValueError as exc:
                    self._json({'ok': False, 'msg': str(exc)}, 400)
            elif url.path == "/api/3d/news":
                from tools.career3d_business import news_detail, news_page
                query = parse_qs(url.query)
                key = (query.get('id') or [''])[0]
                try:
                    if key:
                        detail = news_detail(self.state, key)
                        self._json({'ok': True, 'detail': detail} if detail else {'ok': False, 'msg': '没有找到这篇已发布报道。'},
                                   200 if detail else 404)
                    else:
                        self._json(news_page(self.state, int((query.get('page') or ['1'])[0]),
                            (query.get('category') or ['all'])[0], (query.get('month') or [''])[0]))
                except ValueError as exc:
                    self._json({'ok': False, 'msg': str(exc)}, 400)
            elif url.path == '/api/3d/mail':
                from tools.career3d_business import mail_detail
                query = parse_qs(url.query)
                detail = mail_detail(self.state, (query.get('id') or [''])[0])
                self._json({'ok': True, 'detail': detail} if detail else {'ok': False, 'msg': '没有找到这封邮件。'},
                           200 if detail else 404)
            elif url.path == '/api/3d/players':
                from tools.career3d_business import players_page
                query = parse_qs(url.query)
                try:
                    self._json(players_page(self.state, (query.get('span') or ['season'])[0],
                        int((query.get('page') or ['1'])[0]), (query.get('search') or [''])[0]))
                except ValueError as exc:
                    self._json({'ok': False, 'msg': str(exc)}, 400)
            elif url.path == "/api/3d/match":
                from cs2career.presentation import match_detail
                match_id = (parse_qs(url.query).get("id") or [""])[0]
                detail = match_detail(self.state, match_id)
                self._json({"ok": True, **detail} if detail else {"ok": False, "msg": "没有找到这场比赛"},
                           200 if detail else 404)
            elif url.path in ("/api/3d/team", "/api/3d/player", "/api/3d/event"):
                from cs2career.presentation import inspect, event_detail
                query = parse_qs(url.query)
                key = (query.get("id") or [""])[0]
                kind = url.path.rsplit("/", 1)[1]
                try:
                    span = (query.get('span') or query.get('range') or ['season'])[0]
                    page = int((query.get('page') or ['1'])[0])
                    if span not in ('season', 'all', '30d') or page < 1:
                        raise ValueError('资料范围应为 season、all 或 30d，页码必须是正整数。')
                    detail = event_detail(self.state, key) if kind == "event" else inspect(self.state, kind, key, span=span, page=page)
                    if kind == 'player':
                        from tools.career3d_business import player_detail_projection
                        detail = player_detail_projection(self.state, detail)
                except ValueError as exc:
                    self._json({'ok': False, 'msg': str(exc)}, 400)
                    return
                self._json({"ok": True, "detail": detail} if detail else {"ok": False, "msg": "暂时没有这份资料"},
                           200 if detail else 404)
            else:
                self._json({"ok": False, "msg": "3D demo endpoint not found"}, 404)

        def _post(self):
            path = urlparse(self.path).path
            body = self._body()
            c, s = self.state.career, self.state.season
            try:
                if path == "/api/3d/shutdown":
                    self._json({"ok": True, "status": "stopping"})
                    self.wfile.flush()
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                from cs2career.paths import save_root
                if (save_root() / 'manual-load.pending.json').exists():
                    raise ValueError('存档恢复事务尚未完成，请重新启动完成恢复后再操作。')
                if path == "/api/3d/calendar":
                    hour = body.get("display_hour", 8)
                    if type(hour) is not int or not 0 <= hour <= 23:
                        raise ValueError("display_hour 只允许 0 至 23 的展示小时")
                    receipt = advance_calendar(self.state, body)
                    self.server.display_hour = hour
                    self._json({**receipt, "context": read_context(self.state, hour)})
                    return
                if path == '/api/3d/start/draw':
                    from tools.career3d_attribute_draw import draw_command
                    # Attribute drafts have their own durable receipts. Drawing
                    # cannot advance or rewrite the existing career pair.
                    self._json({'ok': True, **draw_command(self.state, body.get('action'), body)})
                    return
                if path.startswith('/api/3d/saves/'):
                    from tools.career3d_saves import saves_command, saves_context
                    activity = saves_command(self.state, path.rsplit('/', 1)[1], body)
                    # The slot adapter owns commit/recovery and guard counters.
                    # Do not persist again through the old c/s local references.
                    c, s = self.state.career, self.state.season
                    if activity.get('loaded'):
                        self.server.display_hour = 8
                    self._json({'ok': True, **activity, 'actualdate': s.date,
                                'saves': saves_context(self.state),
                                'context': read_context(self.state, self.server.display_hour)})
                    return
                if path == '/api/3d/skin-tools/stickers':
                    from tools.career3d_skin_tools import apply_stickers
                    activity = apply_stickers(self.state, body)
                    # This adapter exchanges cosmetic data only. Do not return
                    # the full career context or run a renderer/game sync here.
                    _store(self.state)['revision'] += 1
                    self.state.persist()
                    self._json({'ok': True, **activity, 'revision': _store(self.state)['revision']})
                    return
                activity = {}
                if path in ('/api/3d/start/create', '/api/3d/avatar'):
                    from tools.career3d_start import start_command
                    activity = start_command(self.state, 'avatar' if path.endswith('/avatar') else 'create', body)
                    message = activity['reason']
                    c, s = self.state.career, self.state.season
                elif path == '/api/3d/feedback/ack':
                    from tools.career3d_feedback import acknowledge_feedback
                    activity = acknowledge_feedback(self.state, body)
                    message = activity['reason']
                elif path.startswith('/api/3d/controls/'):
                    from tools.career3d_controls import controls_command
                    activity = controls_command(self.state, path.removeprefix('/api/3d/controls/'), body)
                    message = activity['reason']
                elif path.startswith('/api/3d/match/'):
                    from tools.career3d_matches import match_command
                    activity = match_command(self.state, path.rsplit('/', 1)[1], body)
                    message = activity['reason']
                elif path.startswith('/api/3d/rts/'):
                    from tools.career3d_rts import rts_command
                    activity = rts_command(self.state, path.rsplit('/', 1)[1], body)
                    message = activity['reason']
                elif path == '/api/3d/social/send':
                    from tools.career3d_social import social_command
                    activity = social_command(self.state, body)
                    message = activity['reason']
                elif path.startswith('/api/3d/season/'):
                    from tools.career3d_matches import season_command
                    activity = season_command(self.state, path.rsplit('/', 1)[1], body)
                    message = activity['reason']
                elif path == '/api/3d/settings':
                    from tools.career3d_activities import settings_command
                    activity = settings_command(self.state, body)
                    message = activity['reason']
                elif path == '/api/3d/setup/install':
                    from tools.career3d_install import install_bundle
                    activity = install_bundle(self.state, body)
                    message = activity['reason']
                elif path.startswith('/api/3d/tactics/'):
                    if path == '/api/3d/tactics/import':
                        from tools.career3d_controls import tactics_import
                        activity = tactics_import(self.state, body)
                    else:
                        from tools.career3d_matches import tactics_command
                        activity = tactics_command(self.state, path.rsplit('/', 1)[1], body)
                    message = activity['reason']
                elif path.startswith('/api/3d/ops/') or path.startswith('/api/3d/transfers/'):
                    from tools.career3d_matches import career_cs2_pending
                    if career_cs2_pending(self.state):
                        raise ValueError('职业比赛等待真实回传，请先录入后再改变生涯事务。')
                    from tools.career3d_business import operations_command, transfer_command
                    command = operations_command if path.startswith('/api/3d/ops/') else transfer_command
                    activity = command(self.state, path.rsplit('/', 1)[1], body)
                    message = activity['reason']
                elif path == "/api/3d/attr":
                    from tools.career3d_activities import spend_attributes
                    activity = spend_attributes(self.state, body)
                    message = activity['reason']
                elif path.startswith("/api/3d/skins/"):
                    if path.endswith('/bundle'):
                        from tools.career3d_skin_bundles import buy_bundle
                        activity = buy_bundle(self.state, body)
                    else:
                        from tools.career3d_activities import skin_command
                        activity = skin_command(self.state, path.rsplit('/', 1)[1], body)
                    message = activity['reason']
                elif path.startswith('/api/3d/custom/'):
                    from tools.career3d_activities import custom_command
                    activity = custom_command(self.state, path.rsplit('/', 1)[1], body)
                    message = activity['reason']
                    if activity.get('read_only'):
                        self._json({'ok': True, **activity, 'context': read_context(self.state, self.server.display_hour)})
                        return
                elif path.startswith("/api/3d/ladder/") or path.startswith("/api/3d/scrim/"):
                    from tools.career3d_activities import ladder_command, scrim_command
                    command = ladder_command if path.startswith("/api/3d/ladder/") else scrim_command
                    activity = command(self.state, path.rsplit("/", 1)[1], body)
                    message = activity["reason"]
                    # A retried report read must not increment revision or write again.
                    if activity.get("replayed"):
                        self._json({"ok": True, **activity, "context": read_context(self.state, self.server.display_hour)})
                        return
                elif path == "/api/3d/story":
                    from tools.career3d_matches import career_cs2_pending
                    if career_cs2_pending(self.state):
                        raise ValueError('职业比赛等待真实回传，请先录入后再作生涯选择。')
                    from tools.career3d_business import guard_roster
                    guard_roster(self.state)
                    story_id, choice = str(body.get("id") or ""), str(body.get("choice") or "")
                    row = next((r for r in c.story_queue if r.get("id") == story_id), None)
                    if not row:
                        raise ValueError("剧情已处理或不存在，请刷新手机")
                    if row.get("choices") and choice not in {r["id"] for r in row["choices"]}:
                        raise ValueError("请选择这段剧情提供的有效选项")
                    from cs2career.career.arcs import changes_world
                    from tools.career3d_social import before_story_choice, after_story_choice
                    social_capture = before_story_choice(self.state, row, choice)
                    if row.get("kind") == "transfer" or (row.get("arc") and changes_world(row, choice)):
                        if self.state.arena.pending:
                            raise ValueError("天梯比赛正在启动或等待真实回传，暂时不能改变选手身份或阵容。")
                        self.state.personal_command(lambda career, season: career.ack_story(story_id, choice, season))
                    else:
                        c.ack_story(story_id, choice, s)
                    activity.update(after_story_choice(self.state, social_capture))
                    message = "剧情选择已保存。"
                elif path in ("/api/3d/mail/accept", "/api/3d/mail/decline"):
                    from tools.career3d_business import mail_command
                    activity = mail_command(self.state, path.rsplit('/', 1)[1], body)
                    message = activity['reason']
                else:
                    self._json({"ok": False, "msg": "3D demo endpoint not found"}, 404)
                    return
                if activity.get('replayed'):
                    self._json({'ok': True, **activity, 'context': read_context(self.state, self.server.display_hour)})
                    return
                _store(self.state)["revision"] += 1
                self.state.persist()
                reason_code, reason = _pause(self.state)
                self._json({"ok": True, "actualdate": s.date, "status": "paused" if reason else "saved",
                            "reason": reason or message, "reason_code": reason_code,
                            **activity,
                            "context": read_context(self.state, self.server.display_hour)})
            except ValueError as exc:
                c, s = self.state.career, self.state.season
                if path.startswith('/api/3d/skin-tools/'):
                    self._json({'ok': False, 'msg': str(exc)}, 400)
                    return
                # A match gate can legitimately queue a decision before refusing.
                if path == "/api/3d/match/simulate" and c.story_queue:
                    _store(self.state)["revision"] += 1
                    self.state.persist()
                    self._json({"ok": True, "actualdate": s.date, "status": "paused",
                                "reason": str(exc), "reason_code": "story",
                                "context": read_context(self.state, self.server.display_hour)})
                    return
                self._json({"ok": False, "msg": str(exc), "actualdate": s.date,
                            "context": read_context(self.state, self.server.display_hour)}, 400)
            except Exception as exc:
                error = {"ok": False, "msg": f"{type(exc).__name__}: {exc}"}
                if path.startswith('/api/3d/saves/'):
                    try:
                        error['context'] = read_context(self.state, self.server.display_hour)
                    except Exception:
                        pass  # Keep the original storage error if projection also fails.
                self._json(error, 500)
    return Career3DHandler


def _port(value: str) -> int:
    if ":" in value:
        host, value = value.rsplit(":", 1)
        if host != "127.0.0.1":
            raise argparse.ArgumentTypeError("Only 127.0.0.1 is allowed")
    try:
        result = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Use a port number or 127.0.0.1:PORT") from None
    if not 0 <= result <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 0 and 65535")
    return result


def _parent_pid(value: str) -> int:
    try:
        result = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Parent PID must be a positive integer") from None
    if result <= 0:
        raise argparse.ArgumentTypeError("Parent PID must be a positive integer")
    return result


class ParentProcessMonitor:
    """Observe a parent process; a Windows handle also avoids PID reuse races."""
    def __init__(self, pid: int):
        self.pid, self.handle = pid, None
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
            self.kernel.OpenProcess.restype = wintypes.HANDLE
            self.kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            self.kernel.WaitForSingleObject.restype = wintypes.DWORD
            self.kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
            self.kernel.CloseHandle.restype = wintypes.BOOL
            # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, both read-only.
            self.handle = self.kernel.OpenProcess(0x00101000, False, pid)
            if not self.handle:
                error = ctypes.get_last_error()
                if error not in (87, 1168):  # Parent already exited vs permission failure.
                    raise OSError(error, "Cannot monitor the parent process")

    def wait_for_exit(self, stopped: threading.Event) -> bool:
        while not stopped.is_set():
            if os.name == "nt":
                if not self.handle:
                    return True
                result = self.kernel.WaitForSingleObject(self.handle, 250)
                if result == 0:
                    return True
                if result != 258:  # WAIT_TIMEOUT
                    raise OSError("Parent process monitoring failed")
            else:
                try:
                    os.kill(self.pid, 0)  # Existence query; no signal is sent.
                except ProcessLookupError:
                    return True
                except PermissionError:
                    pass
                stopped.wait(0.25)
        return False

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--port", type=_port, default=0, help="0 chooses a free loopback port")
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--parent-pid", type=_parent_pid, help="Gracefully stop when the owning Godot process exits")
    parser.add_argument("--cs2-config", type=Path, default=ROOT / 'save' / 'cs2.json',
                        help="Read only this existing path/options configuration, never a career save")
    parser.add_argument("--no-cs2-config", action='store_true', help="Skip the optional configuration import for isolated testing")
    parser.add_argument('--media-config', type=Path, help='Read-only project media/cache manifest')
    parser.add_argument("--mode", choices=("normal", "quick"), default="normal", help="New-demo initial season mode")
    args = parser.parse_args(argv)
    try:
        data_dir = isolate(args.data_dir)
        if args.media_config:
            os.environ['CS2CAREER3D_MEDIA_CONFIG'] = str(args.media_config.expanduser().resolve())
        if args.ready_file:
            ready_file = args.ready_file.resolve()
            forbidden = (ROOT / "save", ROOT / "extensions", data_dir / "save", data_dir / "extensions")
            if any(ready_file == p.resolve() or ready_file.is_relative_to(p.resolve()) for p in forbidden):
                raise ValueError("The temporary ready file must be outside all save/extension directories")
            if ready_file in (data_dir / MARKER, data_dir / ".service.lock"):
                raise ValueError("The ready file cannot overwrite demo metadata")
        directory_lock = _lock_directory(data_dir)
        parent_monitor = ParentProcessMonitor(args.parent_pid) if args.parent_pid else None
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    sys.path.insert(0, str(ROOT))
    from cs2career.application import ApplicationState
    from cs2career.career import arcs
    from cs2career.career.fast_mode import configure_season
    from cs2career.engine.match import RNG
    from cs2career.web.server import create_server
    from cs2career.paths import save_root, extension_root
    from cs2career.league.season import STATE_PATH
    from cs2career.career.career import CAREER_PATH
    if (save_root() != data_dir / "save" or extension_root() != data_dir / "extensions"
            or STATE_PATH != data_dir / "save" / "season.json"
            or CAREER_PATH != data_dir / "save" / "career.json"):
        raise RuntimeError("Business modules were imported before demo isolation")
    if not args.no_cs2_config and args.cs2_config.is_file():
        from cs2career.cs2 import launch
        try:
            imported = json.loads(args.cs2_config.read_text('utf-8-sig'))
            if not isinstance(imported, dict):
                raise ValueError('CS2 path configuration must be a JSON object')
            cfg = {key: value for key, value in imported.items() if key in launch.DEFAULTS and
                   (isinstance(value, str) or key in ('skin_inspect_enabled', 'skin_tools_enabled') and type(value) is bool)}
            if launch.SETTINGS_PATH.is_file():
                own = json.loads(launch.SETTINGS_PATH.read_text('utf-8-sig'))
                if isinstance(own, dict):
                    cfg.update({key: value for key, value in own.items() if key in launch.DEFAULTS and
                               (isinstance(value, str) and value or key in ('skin_inspect_enabled', 'skin_tools_enabled') and type(value) is bool)})
            _write_json(launch.SETTINGS_PATH, launch._clean({**launch.DEFAULTS, **cfg}))
        except (OSError, ValueError) as exc:
            print(f'CS2 configuration unavailable: {exc}', file=sys.stderr)
    if not args.no_cs2_config:
        from tools.career3d_install import auto_prepare_config
        auto_prepare_config()
    random.seed(DEMO_SEED)
    RNG.seed(DEMO_SEED)
    from cs2career.manual_saves import recover as recover_manual_load
    recover_manual_load(save_root())
    state = ApplicationState()
    if not state.career.exists:
        original_uuid = arcs.uuid4
        arcs.uuid4 = lambda: UUID(int=DEMO_SEED)
        try:
            state.create_career({"era": "2026", "mode": "create", "origin": "academy",
                                 "name": "Career3D", "org": "Morning Academy", "region": "AS", "role": "rifle"})
        finally:
            arcs.uuid4 = original_uuid
        configure_season(state.career, state.season, args.mode == "quick", state.season.year)
        state.persist()
    # Reuse only the installed skin owner's configuration, never original career
    # inventory/preferences. Missing ownership remains an explicit UI empty state.
    if not args.no_cs2_config:
        from tools.career3d_activities import read_cs2_config, _existing_skin_plugin
        cfg = read_cs2_config()
        owner_file = Path(cfg.get('csgo_path') or '') / 'addons' / 'counterstrikesharp' / 'configs' / 'plugins' / 'InventorySimulator' / 'owner.txt'
        if cfg.get('csgo_path') and not state.career.steam_id and owner_file.is_file():
            try:
                owner = owner_file.read_text('ascii').strip()
                if len(owner) == 17 and owner.isdigit() and _existing_skin_plugin(cfg):
                    state.career.steam_id, state.career.real_skins = owner, True
                    state.persist()
            except (OSError, ValueError):
                pass
    server = create_server(state, port=args.port)
    server.RequestHandlerClass = handler_class()
    server.game_disabled = True
    server.display_hour = 8
    ready = {"ready": True, "protocol_version": PROTOCOL_VERSION, "host": "127.0.0.1",
             "port": server.server_port, "token": server.token, "pid": os.getpid(),
             "base_url": f"http://127.0.0.1:{server.server_port}", "data_dir": str(data_dir)}
    if args.parent_pid:
        ready["parent_pid"] = args.parent_pid
    watchdog_stop = threading.Event()
    watchdog = None
    def watch_parent():
        try:
            if parent_monitor.wait_for_exit(watchdog_stop):
                server.shutdown()
        except OSError as exc:
            if sys.stderr:
                print(f"parent watchdog: {exc}", file=sys.stderr)
            server.shutdown()
        finally:
            parent_monitor.close()
    def stop(_signal, _frame):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    try:
        if args.ready_file:
            _write_json(args.ready_file.resolve(), ready)
        print(json.dumps(ready, ensure_ascii=False), flush=True)
        if parent_monitor:
            watchdog = threading.Thread(target=watch_parent, name="career3d-parent-watchdog", daemon=True)
            watchdog.start()
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        watchdog_stop.set()
        if watchdog:
            watchdog.join(timeout=1)
        elif parent_monitor:
            parent_monitor.close()
        try:
            server.server_close()
            with server.state_lock:
                state.persist()
        finally:
            if args.ready_file and args.ready_file.exists():
                try:
                    if json.loads(args.ready_file.read_text("utf-8")).get("pid") == os.getpid():
                        args.ready_file.unlink()
                except (OSError, ValueError):
                    pass
            directory_lock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
