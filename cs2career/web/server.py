# coding=utf-8
"""Local HTTP server. The UI is a static page that talks to this JSON API."""

from __future__ import annotations

import base64
import json
import os
import re
import secrets
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .. import cs2
from ..application import ApplicationState
from .. import presentation
from ..career import skins
from ..paths import logo_dir, static_dir
from ..world import ERA_META, apply_roles, build_teams

MAX_UPLOAD = 3 * 1024 * 1024


# The browser interface is a compatibility shell.  It shares the same
# UI-neutral holder as the desktop app; no web-only game state exists.
State = ApplicationState
STATE = None  # Compatibility name only; server creation injects the one active state.


class Handler(SimpleHTTPRequestHandler):
    @property
    def state(self):
        return self.server.state

    def _allowed(self):
        token = self.headers.get("X-Career-Token", "")
        return secrets.compare_digest(token, self.server.token)

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith('/art/'):
            from ..skin_art import artwork
            from urllib.parse import unquote
            item = artwork(unquote(path[5:]))
            if item:
                self._send_png(item)
            else:
                self.send_error(404)
            return
        if urlparse(self.path).path.startswith("/api/") and not self._allowed():
            self._json({"ok": False, "msg": "会话已过期，请重新打开程序。"}, 403)
            return
        with self.server.state_lock:
            self._get()

    def do_POST(self):
        # Consume bounded request bytes even when rejecting a command. Closing a
        # Windows socket with unread POST bytes can reset it before the JSON
        # error reaches the client. Do not decode or execute untrusted data here.
        try:
            size = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            self._json({'ok': False, 'msg': '无效请求长度'}, 400)
            return
        if size < 0 or size > MAX_UPLOAD or self.headers.get('Transfer-Encoding'):
            self._json({'ok': False, 'msg': '请求体过大或传输格式不支持'}, 413)
            return
        self.connection.settimeout(10)
        try:
            self._request_body = self.rfile.read(size)
        except OSError:
            self.close_connection = True
            return
        if not self._allowed():
            self._json({"ok": False, "msg": "无效会话"}, 403)
            return
        if getattr(self.server,'game_disabled',False) and (urlparse(self.path).path.startswith('/api/cs2/') or urlparse(self.path).path in ('/api/play','/api/series/launch','/api/skins/pref','/api/train/finish','/api/scrim')):
            self._json({'ok':False,'msg':'隔离流程测试不连接或修改 CS2，请使用模拟比赛。'},403)
            return
        if getattr(self.server, 'preview', False) and urlparse(self.path).path not in {
            '/api/skins/buy', '/api/skins/case', '/api/skins/keep', '/api/skins/cash', '/api/skins/sell', '/api/skins/equip'
        }:
            self._json({'ok': False, 'msg': '这是隔离设计预览：比赛、经营和游戏文件操作未启用。'}, 403)
            return
        with self.server.state_lock:
            self._post()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(static_dir()), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        text = fmt % args if args else fmt
        if "/api/" not in text:
            return
        if sys.stderr:
            sys.stderr.write("web: " + text + "\n")

    # ---------------------------------------------------------------- helpers

    def _json(self, obj, code: int = 200) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        try:
            value = json.loads(self._request_body.decode("utf-8"))
            return value if isinstance(value, dict) else {}
        except ValueError:
            return {}

    def _send_png(self, path) -> None:
        if not path.is_file():
            self.send_error(404)
            return
        blob = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(blob)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(blob)

    # ---------------------------------------------------------------- routes

    def _get(self):
        url = urlparse(self.path)
        path = url.path
        if (getattr(self.server, 'preview', False) or getattr(self.server,'game_disabled',False)) and (path.startswith('/api/cs2/') or path == '/api/play/result'):
            self._json({'ready': False, 'status': 'none', 'msg': '隔离预览不连接 CS2。'})
            return

        equipped = _equipped_v5_response(path, self.state)
        if equipped is not None:
            self._json(equipped)
            return
        if path == "/api/state":
            payload = self.state.payload()["state"]
            payload['design_preview'] = bool(getattr(self.server, 'preview', False))
            payload['playtest'] = bool(getattr(self.server,'game_disabled',False))
            self._json(payload)
            return
        if path == "/api/setup":
            era = (parse_qs(url.query).get("era") or ["2026"])[0]
            if era not in ERA_META:
                era = "2026"
            meta = ERA_META[era]
            teams = build_teams(era, meta["year"])
            apply_roles(teams, era)
            from ..world.era_data import coverage, quality_view
            self._json(
                {
                    "era": era,
                    "year": meta["year"],
                    "data_coverage": coverage(teams),
                    "teams": [
                        {
                            "id": t["id"],
                            "name": t["name"],
                            "rank": t.get("world_rank"),
                            "region": t["region"],
                            "command": t["command"],
                            "data_provenance": quality_view(t, team=True),
                            "players": [
                                {
                                    "name": p["name"],
                                    "role": p["role"],
                                    "is_igl": bool(p.get('is_igl')),
                                    "roster_status": p.get('roster_status', 'active'),
                                    "ability": p["ability"],
                                    "age": p["age"],
                                }
                                for p in t["players"]
                            ],
                        }
                        for t in teams
                    ],
                }
            )
            return
        if path == '/api/extensions':
            from ..content import get_registry
            self._json(get_registry().public())
            return
        if path == '/api/transfers':
            from ..career.transfers import candidates
            self._json({'players':candidates(self.state.career,self.state.season)})
            return
        if path == "/api/inspect":
            q = parse_qs(url.query)
            kind = "player" if "player" in q or "player_id" in q else "team"
            key = (q.get(kind + "_id") or q.get(kind) or [""])[0]
            try:
                row = presentation.inspect(self.state, kind, key, (q.get("range") or ["season"])[0],
                                           int((q.get("page") or [1])[0]))
                self._json(row or {"error": "not found"}, 200 if row else 404)
            except ValueError:
                self._json({"error": "invalid query"}, 400)
            return
        if path in ("/api/match", "/api/event"):
            key = (parse_qs(url.query).get("id") or [""])[0]
            row = presentation.match_detail(self.state, key) if path == "/api/match" else presentation.event_detail(self.state, key)
            self._json(row or {"error": "not found"}, 200 if row else 404)
            return
        if path == "/api/events":
            self._json([{"id": e["id"], "name": e["name"], "dates": e.get("dates", []), "status": e.get("status", "done")}
                        for e in presentation.events(self.state.season)])
            return
        if path == '/api/skin-art':
            from ..skin_art import manifest
            self._json(manifest())
            return
        if path == "/api/play/result":
            self._json(cs2.read_result())
            return
        if path == "/api/cs2/status":
            self._json(cs2.status())
            return
        if path == "/api/cs2/history":
            self._json(cs2.history())
            return
        if path.startswith("/logo/"):
            name = path[len("/logo/"):]
            if "/" in name or "\\" in name or not name.endswith(".png"):
                self.send_error(404)
                return
            self._send_png(logo_dir() / name)
            return
        if path == "/":
            self.path = "/index.html"
        return SimpleHTTPRequestHandler.do_GET(self)

    def _post(self):
        path = urlparse(self.path).path
        try:
            handler = getattr(self, "post_" + path.strip("/").replace("/", "_"), None)
            if handler is None:
                self._json({"ok": False, "msg": "unknown endpoint"}, 404)
                return
            handler()
        except ValueError as exc:
            self.state.persist()
            self._json({**self.state.payload(""), "ok": False, "msg": str(exc)}, 400)
        except Exception as exc:  # surfaced in the UI instead of a dead page
            self._json({"ok": False, "msg": f"{type(exc).__name__}: {exc}"}, 500)

    # ---------------------------------------------------------------- actions

    def post_api_extensions_reload(self):
        from ..content import reload_registry
        from ..career import story
        from ..league.season import reload_calendar
        from ..world.eras import reload_era_extensions
        registry=reload_registry()
        story.reload_stories()
        skins.reload_catalog()
        reload_calendar()
        reload_era_extensions()
        self._json({**self.state.payload('扩展已重载。剧情和饰品立即生效；赛事及年代用于新生涯。'), 'extensions':registry.public()})

    def post_api_next(self):
        if getattr(self.state.career, "loan_default_pending", False):
            self._json({**self.state.payload(""), "ok": False, "msg": "先处理俱乐部的最后通牒。"}, 400)
            return
        if self.state.career.over():
            self._json({**self.state.payload(""), "ok": False, "msg": "这段生涯已经结束，只能重开。"}, 400)
            return
        msg = self.state.season.next_stage()
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_skip(self):
        if getattr(self.state.career, "loan_default_pending", False):
            self._json({**self.state.payload(""), "ok": False, "msg": "先处理俱乐部的最后通牒。"}, 400)
            return
        if self.state.career.over():
            self._json({**self.state.payload(""), "ok": False, "msg": "这段生涯已经结束，只能重开。"}, 400)
            return
        msg = self.state.season.skip_to_next_event()
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_reset(self):
        self.state.reset()
        self._json(self.state.payload("生涯和赛季已清空。"))

    def post_api_career_create(self):
        body = self._body()
        msg = self.state.create_career(body)
        self._json(self.state.payload(msg))

    def post_api_market_buy(self):
        body=self._body()
        if body.get('mode')=='guaranteed':
            from ..career.transfers import guaranteed
            msg=guaranteed(self.state.career,self.state.season,str(body.get('player_id') or ''),str(body.get('seller_id') or ''),str(body.get('replace_id') or ''),body.get('fee'))
        elif body.get('mode','normal')=='normal':
            msg = self.state.career.buy(self.state.season, (body.get("player") or ""),str(body.get('replace_id') or ''),str(body.get('player_id') or ''))
        else: raise ValueError('未知签约方式。')
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_scrim(self):
        msg = self.state.career.finish_training(self.state.season)
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_train_finish(self):
        msg = self.state.career.finish_training(self.state.season)
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_story_ack(self):
        body = self._body()
        self.state.career.ack_story(str(body.get("id") or ""), str(body.get("choice") or ""), self.state.season)
        self.state.persist()
        self._json(self.state.payload(""))

    def post_api_register(self):
        self._json({**self.state.payload(""), "ok": False, "msg": "赛事改为邮件邀请，请到邮箱接受或婉拒。"}, 400)

    def post_api_mail_read(self):
        msg = self.state.career.mark_read((self._body().get("id") or ""))
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_mail_read_all(self):
        msg = self.state.career.mark_read("")
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_mail_accept(self):
        msg = self.state.career.accept_invite(self.state.season, (self._body().get("id") or ""))
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_mail_decline(self):
        msg = self.state.career.decline_invite(self.state.season, (self._body().get("id") or ""))
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_mail_claim(self):
        msg = self.state.career.claim_mail(self.state.season, (self._body().get("id") or ""))
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_attr(self):
        msg = self.state.career.spend_point(self.state.season, (self._body().get("axis") or ""))
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_retire(self):
        msg = self.state.career.retire(self.state.season)
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_roles(self):
        body = self._body()
        mapping = body.get("roles") or {}
        clicked = str(body.get("player") or "")
        msg = self.state.career.set_roles(self.state.season, mapping, clicked)
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_logo(self):
        body = self._body()
        raw = (body.get("data") or "").split(",", 1)[-1]
        team_id = body.get("team_id") or self.state.career.team_id
        if not raw or not team_id:
            self._json({"ok": False, "msg": "没有收到图片。"}, 400)
            return
        try:
            blob = base64.b64decode(raw, validate=True)
        except Exception:
            self._json({"ok": False, "msg": "图片格式不对，请用 PNG。"}, 400)
            return
        if len(blob) > MAX_UPLOAD:
            self._json({"ok": False, "msg": "图片太大，请小于 3MB。"}, 400)
            return
        (logo_dir() / f"{team_id}.png").write_bytes(blob)
        team = next((t for t in self.state.season.teams if t["id"] == team_id), None)
        if team:
            team["logo"] = f"/logo/{team_id}.png?v={int(time.time())}"
        self.state.persist()
        self._json(self.state.payload("队标已更新。"))

    def post_api_series_launch(self):
        body = self._body()
        msg = self.state.season.launch_your_map(body.get("match_id") or "", body.get("side") or "ct")
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_series_commit(self):
        body = self._body()
        raw = body.get("result") if isinstance(body.get("result"), dict) else None
        msg = self.state.season.commit_cs2_map(body.get("match_id") or "", raw)
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_series_skip(self):
        body = self._body()
        msg = self.state.season.skip_your_series(body.get("match_id") or "")
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_play(self):
        body = self._body()
        team = self.state.career.my_team(self.state.season.teams)
        opp = next((t for t in self.state.season.teams if t["id"] == body.get("opp")), None)
        if getattr(self.state.career, "banned", False) or getattr(self.state.career, "retired", False):
            self._json({"ok": False, "msg": "这段生涯已经结束，只能重开。"}, 400)
            return
        if getattr(self.state.career, "unsigned", False) or not self.state.career.team_id:
            self._json({"ok": False, "msg": "你现在是自由身，先在邮箱接下合同再进训练赛。"}, 400)
            return
        if not team or not opp:
            self._json({"ok": False, "msg": "先创建生涯并选好对手。"}, 400)
            return
        if opp["id"] == team["id"]:
            self._json({"ok": False, "msg": "对手不能是你自己的队，重新选一个。"}, 400)
            return
        out = cs2.start_match(
            team,
            opp,
            self.state.career.player_name,
            body.get("map") or "de_dust2",
            body.get("side") or "ct",
            self.state.season.teams,
            self.state.career,
            purpose="training",
        )
        self._json({**self.state.payload(out["msg"]), "match": out["match"]})

    def post_api_ops_donate(self):
        msg = self.state.career.donate(self.state.season, int(self._body().get("amount") or 0))
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_ops_borrow(self):
        msg = self.state.career.borrow(self.state.season, int(self._body().get("amount") or 0))
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_ops_repay(self):
        msg = self.state.career.repay(self.state.season, int(self._body().get("amount") or 0))
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_ops_found(self):
        msg = self.state.career.found_new_now(self.state.season)
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_skins_pref(self):
        body = self._body()
        msg = self.state.career.set_skin_pref(bool(body.get("real")), str(body.get("steam_id") or ""))
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_skins_buy(self):
        msg = self.state.career.buy_skin(str(self._body().get("id") or ""))
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_skins_case(self):
        msg = self.state.career.buy_case(str(self._body().get("id") or ""))
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_skins_keep(self):
        msg = self.state.career.keep_drop()
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_skins_cash(self):
        msg = self.state.career.cash_drop()
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_skins_sell(self):
        msg = self.state.career.sell_skin(str(self._body().get("id") or ""))
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_skins_equip(self):
        body = self._body()
        msg = self.state.career.equip_skin(
            str(body.get("id") or ""),
            str(body.get("side") or ""),
            bool(body.get("off")),
        )
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_cs2_settings(self):
        try:
            cfg = cs2.save_settings(self._body())
        except ValueError as exc:
            self._json({"ok": False, "msg": str(exc), "cs2": cs2.status()}, 400)
            return
        self._json({"ok": True, "msg": "路径已保存。", "cs2": cfg})

    def post_api_cs2_install(self):
        try:
            out = cs2.install_mod()
        except (OSError, ValueError) as exc:
            self._json({"ok": False, "msg": str(exc), "cs2": cs2.status()}, 400)
            return
        self._json({**out, "cs2": cs2.status()}, 200 if out.get("ok") else 400)

    def post_api_cs2_sync(self):
        try:
            out = cs2.sync_live_profiles()
        except (OSError, ValueError) as exc:
            self._json({"ok": False, "msg": str(exc), "cs2": cs2.status()}, 400)
            return
        self._json({"ok": True, "msg": out["msg"], "added": out.get("added") or 0, "cs2": cs2.status()})

    def post_api_cs2_skins(self):
        try:
            out = cs2.install_skins_mod()
        except (OSError, ValueError) as exc:
            self._json({"ok": False, "msg": str(exc), "cs2": cs2.status()}, 400)
            return
        self._json({"ok": True, "msg": out["msg"], "cs2": cs2.status()})

    def post_api_cs2_gamedata(self):
        try:
            out = cs2.update_skins_gamedata()
        except (OSError, ValueError) as exc:
            self._json({"ok": False, "msg": str(exc), "cs2": cs2.status()}, 400)
            return
        self._json({**out, "cs2": cs2.status()}, 200 if out.get("ok") else 400)


_EQUIPPED_V5 = re.compile(r"^/api/equipped/v5/(\d+)\.json$")


def _equipped_v5_response(path: str, state) -> dict | None:
    match = _EQUIPPED_V5.match(path)
    if not match:
        return None
    career = state.career
    if not getattr(career, "real_skins", False):
        return None
    sid = "".join(ch for ch in str(career.steam_id or "") if ch.isdigit())
    if not sid or sid != match.group(1):
        return None
    return skins.equipped_v5_body(
        career.inventory,
        getattr(career, "equipped_ct", None) or {},
        getattr(career, "equipped_t", None) or {},
    )


class SkinApiHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def do_GET(self):
        path = urlparse(self.path).path
        body = _equipped_v5_response(path, self.server.state)
        data = json.dumps(body if body is not None else {}, ensure_ascii=False).encode("utf-8")
        self.send_response(200 if body is not None else 404)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def start_skin_api(state):
    try:
        server = ThreadingHTTPServer(("127.0.0.1", skins.SKIN_API_PORT), SkinApiHandler)
    except OSError as exc:
        if sys.stderr:
            sys.stderr.write(f"skin api: {exc}\n")
        return
    server.state = state
    threading.Thread(target=server.serve_forever, daemon=True).start()
    if sys.stderr:
        sys.stderr.write(f"skin api -> http://127.0.0.1:{skins.SKIN_API_PORT}/\n")
    return server


def free_port(preferred: int = 8768) -> int:
    for port in (preferred, 8768, 8769, 8770, 8790, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    return 8765


def create_server(state=None, port=0):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.state = state if state is not None else ApplicationState()
    server.token = secrets.token_urlsafe(32)
    server.state_lock = threading.RLock()
    server.game_disabled = os.environ.get('CS2CAREER_NO_GAME') == '1'
    return server


def serve(port: int = 8765) -> None:
    server = create_server(port=port)
    skin = start_skin_api(server.state)
    print(f"CS2 Career -> http://127.0.0.1:{server.server_port}/?token={server.token}")
    try:
        server.serve_forever()
    finally:
        if skin:
            skin.shutdown()
            skin.server_close()
        server.server_close()
