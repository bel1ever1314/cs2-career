# coding=utf-8
"""Local HTTP server. The UI is a static page that talks to this JSON API."""

from __future__ import annotations

import base64
import json
import re
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .. import cs2
from ..career import Career, skins
from ..league import Season, reset_season
from ..paths import logo_dir, static_dir
from ..world import ERA_META, apply_roles

MAX_UPLOAD = 3 * 1024 * 1024


class State:
    """One process, one career. Kept in a holder so /api/reset can swap it."""

    def __init__(self) -> None:
        self.season = Season.load_or_new()
        self.career = Career.load()
        self.season.career = self.career
        dirty = bool(getattr(self.season, "_calendar_changed", False))
        if self.career.exists:
            if self.career.fix_placeholder_mates(self.season):
                dirty = True
            if self._boot_career():
                dirty = True
        if dirty:
            self.persist()

    def _boot_career(self) -> bool:
        dirty = False
        if not self.career.exists:
            return False
        before_stories = len(self.career.story_queue)
        self.career._ensure_loan_popup()
        if len(self.career.story_queue) != before_stories:
            dirty = True
        before = len(self.career.inbox)
        if self.career.unsigned and not self.career.banned:
            self.career._dispatch_contracts(self.season)
        elif not self.career.unsigned:
            self.career.dispatch_invites(self.season)
        if len(self.career.inbox) != before:
            dirty = True
        return dirty

    def sync(self) -> None:
        apply_roles(self.season.teams)
        you = self.career.my_player(self.season.teams) if self.career.exists else None
        if you:
            self.career.role = you["role"]
        self.season.career = self.career
        if self.career.exists:
            self.career.apply_throw_flag(self.season)

    def payload(self, msg: str = "") -> dict:
        self.sync()
        return {
            "ok": True,
            "msg": msg,
            "state": self.season.public(),
            "stories": list(getattr(self.career, "story_queue", None) or []),
        }

    def persist(self) -> None:
        self.season.save()
        self.career.save()

    def reset(self) -> None:
        if self.career.path().exists():
            self.career.path().unlink()
        self.career = Career()
        self.season = reset_season()
        self.season.career = self.career


STATE = State()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(static_dir()), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        text = fmt % args if args else fmt
        if "/api/" not in text:
            return
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
        size = int(self.headers.get("Content-Length") or 0)
        if not size or size > MAX_UPLOAD:
            return {}
        try:
            return json.loads(self.rfile.read(size).decode("utf-8"))
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

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path

        equipped = _equipped_v5_response(path)
        if equipped is not None:
            self._json(equipped)
            return
        if path == "/api/state":
            self._json(STATE.payload()["state"])
            return
        if path == "/api/inspect":
            q = parse_qs(url.query)
            player = (q.get("player") or [""])[0]
            team = (q.get("team") or [""])[0]
            if player:
                row = STATE.career.inspect_player(STATE.season, player)
            elif team:
                row = STATE.career.inspect_team(STATE.season, team)
            else:
                row = None
            self._json(row or {"error": "not found"}, 200 if row else 404)
            return
        if path == "/api/match":
            mid = (parse_qs(url.query).get("id") or [""])[0]
            detail = STATE.season.match_detail(mid)
            self._json(detail or {"error": "not found"}, 200 if detail else 404)
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
            self._send_png(logo_dir() / path[len("/logo/") :].split("?")[0])
            return
        if path == "/":
            self.path = "/index.html"
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            handler = getattr(self, "post_" + path.strip("/").replace("/", "_"), None)
            if handler is None:
                self._json({"ok": False, "msg": "unknown endpoint"}, 404)
                return
            handler()
        except ValueError as exc:
            STATE.persist()
            self._json({**STATE.payload(""), "ok": False, "msg": str(exc)}, 400)
        except Exception as exc:  # surfaced in the UI instead of a dead page
            self._json({"ok": False, "msg": f"{type(exc).__name__}: {exc}"}, 500)

    # ---------------------------------------------------------------- actions

    def post_api_next(self):
        if getattr(STATE.career, "loan_default_pending", False):
            self._json({**STATE.payload(""), "ok": False, "msg": "先处理俱乐部的最后通牒。"}, 400)
            return
        msg = STATE.season.next_stage()
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_skip(self):
        if getattr(STATE.career, "loan_default_pending", False):
            self._json({**STATE.payload(""), "ok": False, "msg": "先处理俱乐部的最后通牒。"}, 400)
            return
        msg = STATE.season.skip_to_next_event()
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_reset(self):
        STATE.reset()
        self._json(STATE.payload("生涯和赛季已清空。"))

    def post_api_career_create(self):
        body = self._body()
        era = body.get("era") or "2026"
        meta = ERA_META.get(era) or ERA_META["2026"]
        STATE.season = reset_season(meta["year"], era)
        STATE.career = Career()
        STATE.season.career = STATE.career
        msg = STATE.career.create(body, STATE.season)
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_market_buy(self):
        msg = STATE.career.buy(STATE.season, (self._body().get("player") or ""))
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_scrim(self):
        msg = STATE.career.finish_training(STATE.season)
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_train_finish(self):
        msg = STATE.career.finish_training(STATE.season)
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_story_ack(self):
        body = self._body()
        STATE.career.ack_story(str(body.get("id") or ""), str(body.get("choice") or ""), STATE.season)
        STATE.persist()
        self._json(STATE.payload(""))

    def post_api_register(self):
        self._json({**STATE.payload(""), "ok": False, "msg": "赛事改为邮件邀请，请到邮箱接受或婉拒。"}, 400)

    def post_api_mail_read(self):
        msg = STATE.career.mark_read((self._body().get("id") or ""))
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_mail_read_all(self):
        msg = STATE.career.mark_read("")
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_mail_accept(self):
        msg = STATE.career.accept_invite(STATE.season, (self._body().get("id") or ""))
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_mail_decline(self):
        msg = STATE.career.decline_invite(STATE.season, (self._body().get("id") or ""))
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_mail_claim(self):
        msg = STATE.career.claim_mail(STATE.season, (self._body().get("id") or ""))
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_attr(self):
        msg = STATE.career.spend_point(STATE.season, (self._body().get("axis") or ""))
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_roles(self):
        mapping = self._body().get("roles") or {}
        msg = STATE.career.set_roles(STATE.season, mapping)
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_logo(self):
        body = self._body()
        raw = (body.get("data") or "").split(",", 1)[-1]
        team_id = body.get("team_id") or STATE.career.team_id
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
        team = next((t for t in STATE.season.teams if t["id"] == team_id), None)
        if team:
            team["logo"] = f"/logo/{team_id}.png?v={int(time.time())}"
        STATE.persist()
        self._json(STATE.payload("队标已更新。"))

    def post_api_series_launch(self):
        body = self._body()
        msg = STATE.season.launch_your_map(body.get("match_id") or "", body.get("side") or "ct")
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_series_commit(self):
        body = self._body()
        msg = STATE.season.commit_cs2_map(body.get("match_id") or "")
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_series_skip(self):
        body = self._body()
        msg = STATE.season.skip_your_series(body.get("match_id") or "")
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_play(self):
        body = self._body()
        team = STATE.career.my_team(STATE.season.teams)
        opp = next((t for t in STATE.season.teams if t["id"] == body.get("opp")), None)
        if getattr(STATE.career, "banned", False):
            self._json({"ok": False, "msg": "你已被禁赛，这份档案只能重开。"}, 400)
            return
        if getattr(STATE.career, "unsigned", False) or not STATE.career.team_id:
            self._json({"ok": False, "msg": "你现在是自由身，先在邮箱接下合同再进训练赛。"}, 400)
            return
        if not team or not opp:
            self._json({"ok": False, "msg": "先创建生涯并选好对手。"}, 400)
            return
        if opp["id"] == team["id"]:
            self._json({"ok": False, "msg": "对手不能是你自己的队，重新选一个。"}, 400)
            return
        if opp["id"] == team["id"]:
            self._json({"ok": False, "msg": "对手不能是自己的队伍，重新选一个。"}, 400)
            return
        out = cs2.start_match(
            team,
            opp,
            STATE.career.player_name,
            body.get("map") or "de_dust2",
            body.get("side") or "ct",
            STATE.season.teams,
            STATE.career,
        )
        self._json({**STATE.payload(out["msg"]), "match": out["match"]})

    def post_api_ops_donate(self):
        msg = STATE.career.donate(STATE.season, int(self._body().get("amount") or 0))
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_ops_borrow(self):
        msg = STATE.career.borrow(STATE.season, int(self._body().get("amount") or 0))
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_ops_repay(self):
        msg = STATE.career.repay(STATE.season, int(self._body().get("amount") or 0))
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_ops_found(self):
        msg = STATE.career.found_new_now(STATE.season)
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_skins_pref(self):
        body = self._body()
        msg = STATE.career.set_skin_pref(bool(body.get("real")), str(body.get("steam_id") or ""))
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_skins_buy(self):
        msg = STATE.career.buy_skin(str(self._body().get("id") or ""))
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_skins_case(self):
        msg = STATE.career.buy_case(str(self._body().get("id") or ""))
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_skins_keep(self):
        msg = STATE.career.keep_drop()
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_skins_cash(self):
        msg = STATE.career.cash_drop()
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_skins_sell(self):
        msg = STATE.career.sell_skin(str(self._body().get("id") or ""))
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_skins_equip(self):
        body = self._body()
        msg = STATE.career.equip_skin(
            str(body.get("id") or ""),
            str(body.get("side") or ""),
            bool(body.get("off")),
        )
        STATE.persist()
        self._json(STATE.payload(msg))

    def post_api_cs2_settings(self):
        cfg = cs2.save_settings(self._body())
        self._json({"ok": True, "msg": "路径已保存。", "cs2": cfg})

    def post_api_cs2_install(self):
        try:
            out = cs2.install_mod()
        except (OSError, ValueError) as exc:
            self._json({"ok": False, "msg": str(exc), "cs2": cs2.status()}, 400)
            return
        self._json({"ok": True, "msg": out["msg"], "cs2": cs2.status()})

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


_EQUIPPED_V5 = re.compile(r"^/api/equipped/v5/(\d+)\.json$")


def _equipped_v5_response(path: str) -> dict | None:
    match = _EQUIPPED_V5.match(path)
    if not match:
        return None
    career = STATE.career
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
        body = _equipped_v5_response(path)
        data = json.dumps(body if body is not None else {}, ensure_ascii=False).encode("utf-8")
        self.send_response(200 if body is not None else 404)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def start_skin_api() -> None:
    try:
        server = ThreadingHTTPServer(("127.0.0.1", skins.SKIN_API_PORT), SkinApiHandler)
    except OSError as exc:
        sys.stderr.write(f"skin api: {exc}\n")
        return
    threading.Thread(target=server.serve_forever, daemon=True).start()
    sys.stderr.write(f"skin api -> http://127.0.0.1:{skins.SKIN_API_PORT}/\n")


def free_port(preferred: int = 8768) -> int:
    for port in (preferred, 8768, 8769, 8770, 8790, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    return 8765


def serve(port: int = 8765) -> None:
    start_skin_api()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"CS2 Career  ->  http://127.0.0.1:{port}/")
    server.serve_forever()
