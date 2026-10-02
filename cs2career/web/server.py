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
from .. import presentation, tactics
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
        upload_limit = tactics.MAX_BYTES if urlparse(self.path).path.startswith('/api/tactics/') else MAX_UPLOAD
        if size < 0 or size > MAX_UPLOAD or self.headers.get('Transfer-Encoding'):
            self._json({'ok': False, 'msg': '请求体过大或传输格式不支持'}, 413)
            return
        self.connection.settimeout(10)
        try:
            self._request_body = self.rfile.read(size)
        except OSError:
            self.close_connection = True
            return
        if size > upload_limit:
            # Drain only the globally bounded body before the narrower editor
            # rejection; unread bytes can erase the JSON error on Windows.
            self._json({'ok': False, 'msg': '战术数据超过 256 KiB 大小限制'}, 413)
            return
        if not self._allowed():
            self._json({"ok": False, "msg": "无效会话"}, 403)
            return
        if getattr(self.server,'game_disabled',False) and (urlparse(self.path).path.startswith('/api/cs2/') or urlparse(self.path).path in ('/api/play','/api/series/launch','/api/skins/pref','/api/train/finish','/api/scrim','/api/arena/launch','/api/arena/ingest','/api/arena/cancel')):
            self._json({'ok':False,'msg':'隔离流程测试不连接或修改 CS2，请使用模拟比赛。'},403)
            return
        if getattr(self.server, 'preview', False) and urlparse(self.path).path not in {
            '/api/skins/buy', '/api/skins/case', '/api/skins/keep', '/api/skins/cash', '/api/skins/sell', '/api/skins/equip',
            '/api/skins/craft', '/api/skins/loadout',
            '/api/tactics/save', '/api/tactics/delete', '/api/tactics/import'
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
        from ..json_bytes import encode
        data = encode(obj)
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
        if path == '/api/tactics':
            try:
                query = parse_qs(url.query, keep_blank_values=True)
                if set(query) - {'map'} or len(query.get('map', [])) > 1:
                    raise ValueError('战术查询仅允许一个 map 参数')
                self._json(tactics.public_library((query.get('map') or [tactics.MAP])[0]))
            except (ValueError, OSError) as exc:
                self._json({'ok': False, 'msg': str(exc)}, 400)
            return
        if path in ('/api/arena', '/api/arena/recommend'):
            try:
                query = parse_qs(url.query)
                mode = (query.get('mode') or ['rank'])[0]
                if mode not in ('rank', 'fpl', 'custom'):
                    raise ValueError('未知房间模式')
                arena = self.state.arena
                if path.endswith('/recommend'):
                    self._json({'ok': True, 'players': arena.recommend(self.state, mode, (query.get('human_id') or [''])[0])})
                else:
                    self._json(arena.public(self.state, mode))
            except (ValueError, OSError) as exc:
                self._json({'ok': False, 'msg': str(exc)}, 400)
            return
        if path == '/api/assist/season-board':
            from ..career.season_board import public
            self._json(public(self.state.career, self.state.season))
            return
        if (getattr(self.server, 'preview', False) or getattr(self.server,'game_disabled',False)) and (path.startswith('/api/cs2/') or path == '/api/play/result'):
            self._json({'ready': False, 'status': 'none', 'msg': '隔离预览不连接 CS2。'})
            return

        if _EQUIPPED_V5.match(path) and cs2.skins_inventory_mode() == 'external':
            self._json({'ok': False, 'msg': '外部插件配装模式不提供生涯配装，请使用原插件的数据源。'}, 409)
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
        if path == '/api/story-history':
            from ..career.arcs import history_page
            try:
                page = int((parse_qs(url.query).get('page') or ['1'])[0])
                self._json(history_page(self.state.career, page))
            except ValueError:
                self._json({'error': '页码应为正整数'}, 400)
            return
        if path == '/api/transfers':
            from ..career.transfers import candidates
            self._json({'players':candidates(self.state.career,self.state.season)})
            return
        if path == '/api/player-transfers':
            from ..career.player_transfers import public
            self._json(public(self.state.career, self.state.season))
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
            try:
                self._json(cs2.status())
            except (OSError, ValueError) as exc:
                self._json({'ok': False, 'ready': False, 'msg': str(exc),
                            'skin_integration': cs2.skin_integration()}, 400)
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
        if path.startswith('/api/tactics/'):
            # This independent editor must never persist/payload career state,
            # deploy game files, or accept arbitrary file/script paths.
            try:
                body = tactics.decode_json(self._request_body)
                if path == '/api/tactics/save':
                    if not isinstance(body, dict) or set(body) not in ({'tactic'}, {'map', 'tactic'}):
                        raise ValueError('保存请求只允许 tactic 和可选的 map')
                    result = tactics.save_tactic(body['tactic'], body.get('map', tactics.MAP))
                elif path == '/api/tactics/delete':
                    if not isinstance(body, dict) or set(body) not in ({'id'}, {'map', 'id'}):
                        raise ValueError('删除请求只允许 id 和可选的 map')
                    result = tactics.delete_tactic(body['id'], body.get('map', tactics.MAP))
                elif path == '/api/tactics/import':
                    query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
                    if set(query) - {'map'} or len(query.get('map', [])) > 1:
                        raise ValueError('战术导入仅允许一个 map 参数')
                    selected_map = (query.get('map') or [None])[0]
                    result = tactics.import_tactics(body, selected_map)
                else:
                    self._json({'ok': False, 'msg': 'unknown endpoint'}, 404)
                    return
                self._json(result)
            except (ValueError, OSError) as exc:
                self._json({'ok': False, 'msg': str(exc)}, 400)
            return
        if path.startswith('/api/arena/'):
            action = path.rsplit('/', 1)[-1]
            if action not in ('matchmake', 'create', 'pick', 'advance', 'ban', 'choose_side', 'configure', 'launch', 'ingest', 'cancel'):
                self._json({'ok': False, 'msg': 'unknown endpoint'}, 404)
                return
            # Do not call career.persist/payload even when an arena command fails.
            try:
                arena = self.state.arena
                body = self._body()
                arena.guard_rank_action(self.state, action)
                method = getattr(arena, action)
                msg = method(self.state, body) if action in ('matchmake', 'create', 'launch') else method(body)
                mode = (arena.data['lobby'] or {}).get('mode', body.get('mode', 'rank'))
                self._json({'ok': True, 'msg': msg or '', 'arena': arena.public(self.state, mode)})
            except (ValueError, OSError, RuntimeError) as exc:
                self._json({'ok': False, 'msg': str(exc)}, 400)
            except Exception as exc:
                self._json({'ok': False, 'msg': f'{type(exc).__name__}: {exc}'}, 500)
            return
        if path in ('/api/play', '/api/series/launch'):
            try:
                if getattr(self.state, 'arena', None) and self.state.arena.pending:
                    raise ValueError('对战大厅仍有比赛待回传，请先录入或放弃该场。')
            except (ValueError, OSError) as exc:
                self._json({'ok': False, 'msg': str(exc)}, 400)
                return
        try:
            if path in {
                '/api/market/buy', '/api/ops/found', '/api/logo'
            } and getattr(self.state.career, 'personal_transfers', {}).get('player_only'):
                raise ValueError('你现在是签约选手，俱乐部人事和经营由管理层负责。')
            handler_name = "post_api_assist_season_mode" if path == '/api/assist/season-mode' else "post_" + path.strip("/").replace("/", "_")
            handler = getattr(self, handler_name, None)
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
        self._json({**self.state.payload('扩展已重载。生涯事件下次触发、聊天下次准备比赛生效；赛事及年代用于新生涯。'), 'extensions':registry.public()})

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

    def post_api_assist_settings(self):
        from ..career.assistance import configure
        try:
            msg=configure(self.state.career,self.state.season,self._body())
        except ValueError as exc:
            self._json({'ok':False,'msg':str(exc)},400)
            return
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_assist_season_mode(self):
        from ..career.fast_mode import configure_season
        body=self._body()
        def reject(message):
            self._json({'ok':False,'msg':message},400)
        if type(body.get('quick_mode')) is not bool or type(body.get('year')) is not int:
            return reject('请选择本赛季的正常模式或快速模式。')
        token=body.get('token')
        if not isinstance(token,str) or not 8<=len(token)<=100:
            return reject('缺少有效的模式选择编号，请刷新。')
        c,s=self.state.career,self.state.season
        prior=c.assist.get('last_season_choice') or {}
        identity={'year':body['year'],'quick_mode':body['quick_mode']}
        if prior.get('token')==token:
            if prior.get('identity')!=identity:
                return reject('这个请求编号已用于其他选择。')
            return self._json(self.state.payload(prior.get('msg','')))
        try:
            configure_season(c,s,body['quick_mode'],body['year'])
        except ValueError as exc:
            return reject(str(exc))
        message='本赛季采用快速模式。' if body['quick_mode'] else '本赛季采用正常模式。'
        c.assist['last_season_choice']={'token':token,'identity':identity,'msg':message}
        self.state.persist()
        self._json(self.state.payload(message))

    def post_api_assist_tournament(self):
        from ..league.tournament_auto import step
        body=self._body()
        if type(body.get('revision')) is not int:
            raise ValueError('缺少模拟进度编号，请刷新赛事。')
        result=step(self.state.career,self.state.season,str(body.get('event_id') or ''),body.get('token'),body['revision'])
        self.state.persist()
        self._json({**self.state.payload(''), 'auto_step':result})

    def post_api_assist_quick(self):
        from ..career.fast_mode import step
        from ..career.story_timing import window
        body=self._body()
        def reject(message):
            # Invalid input must not reach the generic error handler's persist
            # path, which intentionally saves valid queued match decisions.
            self._json({'ok':False,'msg':message},400)
        if type(body.get('revision')) is not int:
            return reject('缺少模拟进度编号，请刷新。')
        c,s=self.state.career,self.state.season
        token=body.get('token')
        if not isinstance(token,str) or not 8<=len(token)<=100:
            return reject('缺少有效的快速模拟请求编号。')
        prior=c.assist.get('last_fast_step') or {}
        if prior.get('token')==token:
            self._json({**self.state.payload(''), 'auto_step':prior['result']})
            return
        if body['revision']!=int(c.assist.get('step_counter') or 0):
            return reject('模拟进度已变化，请刷新后继续。')
        if 'resume_break' in body and type(body['resume_break']) is not bool:
            return reject('休赛期继续标记必须为布尔值。')
        current=window(c,s)
        # A stale resume click must not acknowledge a different future break.
        if body.get('resume_break'):
            if not current or body.get('break_key')!=current['key']:
                return reject('休赛窗口已变化，请刷新后继续。')
            c.assist['quick_break_ack']=current['key']
        result=step(c,s,token,body['revision'])
        self.state.persist()
        self._json({**self.state.payload(''), 'auto_step':result})

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

    def post_api_player_transfers_apply(self):
        from ..career.player_transfers import apply
        body = self._body()
        msg = self.state.personal_command(lambda c, s: apply(c, s, str(body.get('team_id') or ''), str(body.get('role') or '')))
        self._json({**self.state.payload(msg), 'transfer':self.state.career.personal_transfers.get('attempts', [None])[-1]})

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
        story_id, choice = str(body.get('id') or ''), str(body.get('choice') or '')
        row = next((r for r in self.state.career.story_queue if r.get('id') == story_id), {})
        from ..career.arcs import changes_world
        if row.get('kind') == 'transfer' or (row.get('arc') and changes_world(row, choice)):
            self.state.personal_command(lambda c, s: c.ack_story(story_id, choice, s))
        else:
            self.state.career.ack_story(story_id, choice, self.state.season)
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
        mail_id = self._body().get('id') or ''
        row = self.state.career._mail(mail_id) or {}
        if row.get('kind') == 'contract':
            msg = self.state.personal_command(lambda c, s: c.accept_invite(s, mail_id))
        else:
            msg = self.state.career.accept_invite(self.state.season, mail_id)
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
        _, before = self.state.season.find_match(body.get("match_id") or "")
        start = len((before or {}).get("maps") or [])
        msg = self.state.season.skip_your_series(body.get("match_id") or "")
        self.state.persist()
        payload = self.state.payload(msg)
        if body.get("reveal") and before:
            from ..league.spectator import reveal_series
            payload["reveal"] = reveal_series(before, start)
        self._json(payload)

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

    def post_api_skins_craft(self):
        body = self._body()
        if set(body) - {'id', 'stickers'} or 'stickers' not in body:
            raise ValueError('贴纸编辑需要饰品 ID 和 stickers 数组。')
        msg = self.state.career.craft_skin(str(body.get('id') or ''), body['stickers'])
        self.state.persist()
        self._json(self.state.payload(msg))

    def post_api_skins_loadout(self):
        msg = self.state.career.import_loadout(str(self._body().get('id') or ''))
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
            self._json({"ok": False, "msg": str(exc)}, 400)
            return
        # Settings never advance the career or opportunistically ingest a match.
        self._json({"ok": True, "msg": "设置已保存。", "cs2": cfg,
                    "skin_integration": cs2.skin_integration(cfg)})

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
    if cs2.skins_inventory_mode() == 'external':
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
        external = bool(_EQUIPPED_V5.match(path)) and cs2.skins_inventory_mode() == 'external'
        body = None if external else _equipped_v5_response(path, self.server.state)
        data = json.dumps({'ok': False, 'msg': 'external_inventory_provider'} if external else body if body is not None else {}, ensure_ascii=False).encode("utf-8")
        self.send_response(409 if external else 200 if body is not None else 404)
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
