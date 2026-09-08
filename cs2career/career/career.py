# coding=utf-8
"""The player career: join or found a team, money, transfers, scrims, honours."""

from __future__ import annotations

import json
import random
import re
from datetime import datetime
from pathlib import Path

from ..engine import shift_mentality
from ..engine.morale import scrim_mentality_gain
from ..league import awards
from ..paths import save_file
from ..world.ability import ALL_AXES, AXIS_LABEL, AXES, ability_of, refresh_team_command, restamp_command, stats_for
from ..world.roles import ROLE_LABEL
from ..world import (
    ERA_META,
    PLAYABLE_ROLES,
    age_of,
    agent_rows,
    birth_label,
    birthday_md,
    crest,
    maps_for,
    roster_names,
    slug,
    starter_mates,
    tier_of,
)
from . import economy, mail, plot, skins, story, verse

CAREER_PATH = save_file("career.json")

PLACEHOLDER_RE = re.compile(r"^rook\d+$", re.IGNORECASE)

START_POCKET = 40000
ORG_START_ABILITY = 74.0


def _signed(cand: dict, year: int | None = None) -> dict:
    stats = cand.get("stats") or stats_for(cand["name"], cand["role"], float(cand["ability"]))
    out = {
        "name": cand["name"],
        "role": cand["role"],
        "ability": float(cand["ability"]),
        "command": int(cand.get("command") or stats.get("command") or 0),
        "stats": stats,
        "form": cand.get("form", float(cand["ability"]) - 8),
        "age": cand.get("age", 22),
        "igl_years": int(cand.get("igl_years") or 0),
    }
    if cand.get("potential"):
        out["potential"] = float(cand["potential"])
    return out


def transfer_fee(ability: float) -> int:
    return int(max(8000, (ability**3) * 0.32))


def sponsor_month(rank: int) -> int:
    return int(175000 / max(1, rank) ** 0.52)


def buy_chance(buyer_vrs: float, ability: float, money: int, fee: int) -> float:
    if money < fee:
        return 0.0
    if ability >= 92:
        return min(0.12, (buyer_vrs / 2100.0) ** 2.4 * 0.35)
    if ability >= 88:
        return min(0.28, (buyer_vrs / 1900.0) ** 1.8 * 0.55)
    prestige = min(1.0, buyer_vrs / max(900.0, ability * 18.0))
    cash = min(1.2, money / max(fee, 1))
    return min(0.85, 0.25 + 0.5 * prestige * cash)


def year_delta(age: int, ability: float = 80.0) -> float:
    from ..world.aging import gun_year_delta

    return gun_year_delta(age, ability)


def scrim_gain(ability: float) -> float:
    if ability >= 90:
        return 0.0
    if ability >= 85:
        return 0.30
    if ability >= 80:
        return 0.55
    return 1.0


class Career:
    def __init__(self) -> None:
        self.exists = False
        self.era = "2026"
        self.year = 2026
        self.player_name = ""
        self.role = "rifle"
        self.team_id = ""
        self.mode = "join"
        self.replaced = ""
        self.money = 0
        self.last_scrim = ""
        self.last_sponsor_month = ""
        self.last_age_year = 2026
        self.registered: list[str] = []
        self.free: list[dict] = []
        self.hidden: list[str] = []
        self.log: list[str] = []
        self.seen_stories: list[str] = []
        self.story_queue: list[dict] = []
        self.inbox: list[dict] = []
        self.mail_seq = 0
        self.attr_points = 0
        self.last_ops_month = ""
        self.crisis = False
        self.deficit = 0
        self.inventory: list[dict] = []
        self.equipped: dict = {}
        self.equipped_ct: dict = {}
        self.equipped_t: dict = {}
        self.skin_quotes: dict = {}
        self.skin_quotes_prev: dict = {}
        self.case_prices: dict = {}
        self.real_skins = False
        self.steam_id = ""
        self.skin_seq = 0
        self.pending_drop = None
        self.ops_log: list[str] = []
        self.fix_chance = plot.FIX_BASE
        self.fix_pending = False
        self.throwing = False
        self.banned = False
        self.fix_rolled = ""
        self.coach_majors: list[str] = []
        self.loan: dict | None = None
        self.unsigned = False
        self.you_card: dict = {}
        self.loan_default_pending = False
        self.last_offer_month = ""
        self.retired = False
        self.ending = ""
        self.ending_title = ""
        self.ending_text = ""
        self.academy_used: list[str] = []
        self.last_birthday = ""
        self.start_year = 2026

    # ---------------------------------------------------------------- storage

    def path(self):
        return CAREER_PATH

    def to_json(self) -> dict:
        return {
            "exists": self.exists,
            "era": self.era,
            "year": self.year,
            "player_name": self.player_name,
            "role": self.role,
            "team_id": self.team_id,
            "mode": self.mode,
            "replaced": self.replaced,
            "money": self.money,
            "last_scrim": self.last_scrim,
            "last_sponsor_month": self.last_sponsor_month,
            "last_age_year": self.last_age_year,
            "registered": self.registered,
            "free": self.free,
            "hidden": self.hidden,
            "log": self.log[-40:],
            "seen_stories": self.seen_stories,
            "story_queue": self.story_queue,
            "inbox": self.inbox,
            "mail_seq": self.mail_seq,
            "attr_points": self.attr_points,
            "last_ops_month": self.last_ops_month,
            "crisis": self.crisis,
            "deficit": self.deficit,
            "inventory": self.inventory,
            "equipped": self.equipped,
            "equipped_ct": self.equipped_ct,
            "equipped_t": self.equipped_t,
            "skin_quotes": self.skin_quotes,
            "skin_quotes_prev": self.skin_quotes_prev,
            "case_prices": self.case_prices,
            "real_skins": self.real_skins,
            "steam_id": self.steam_id,
            "skin_seq": self.skin_seq,
            "pending_drop": self.pending_drop,
            "ops_log": self.ops_log[-20:],
            "fix_chance": self.fix_chance,
            "fix_pending": self.fix_pending,
            "throwing": self.throwing,
            "banned": self.banned,
            "fix_rolled": self.fix_rolled,
            "coach_majors": self.coach_majors,
            "loan": self.loan,
            "unsigned": self.unsigned,
            "you_card": self.you_card,
            "loan_default_pending": self.loan_default_pending,
            "last_offer_month": self.last_offer_month,
            "retired": self.retired,
            "ending": self.ending,
            "ending_title": self.ending_title,
            "ending_text": self.ending_text,
            "academy_used": self.academy_used,
            "last_birthday": self.last_birthday,
            "start_year": self.start_year,
        }

    def save(self) -> None:
        CAREER_PATH.parent.mkdir(parents=True, exist_ok=True)
        CAREER_PATH.write_text(json.dumps(self.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> "Career":
        obj = cls()
        if not CAREER_PATH.exists():
            return obj
        try:
            blob = json.loads(CAREER_PATH.read_text(encoding="utf-8"))
        except ValueError:
            return obj
        for k, v in blob.items():
            setattr(obj, k, v)
        obj.seen_stories = list(getattr(obj, "seen_stories", None) or [])
        obj.story_queue = list(getattr(obj, "story_queue", None) or [])
        obj.inbox = list(getattr(obj, "inbox", None) or [])
        obj.mail_seq = int(getattr(obj, "mail_seq", 0) or 0)
        obj.attr_points = int(getattr(obj, "attr_points", 0) or 0)
        obj.last_ops_month = getattr(obj, "last_ops_month", "") or ""
        obj.crisis = bool(getattr(obj, "crisis", False))
        obj.deficit = int(getattr(obj, "deficit", 0) or 0)
        obj.inventory = list(getattr(obj, "inventory", None) or [])
        obj.equipped = dict(getattr(obj, "equipped", None) or {})
        obj.equipped_ct = dict(getattr(obj, "equipped_ct", None) or {})
        obj.equipped_t = dict(getattr(obj, "equipped_t", None) or {})
        obj.skin_quotes = dict(getattr(obj, "skin_quotes", None) or {})
        obj.skin_quotes_prev = dict(getattr(obj, "skin_quotes_prev", None) or {})
        obj.case_prices = dict(getattr(obj, "case_prices", None) or {})
        obj.real_skins = bool(getattr(obj, "real_skins", False))
        obj.steam_id = str(getattr(obj, "steam_id", "") or "")
        obj.skin_seq = int(getattr(obj, "skin_seq", 0) or 0)
        obj.pending_drop = getattr(obj, "pending_drop", None)
        skins.migrate_equipped(obj)
        dirty = skins.ensure_economy(obj)
        obj.ops_log = list(getattr(obj, "ops_log", None) or [])
        obj.fix_chance = float(getattr(obj, "fix_chance", plot.FIX_BASE) or plot.FIX_BASE)
        obj.fix_pending = bool(getattr(obj, "fix_pending", False))
        obj.throwing = bool(getattr(obj, "throwing", False))
        obj.banned = bool(getattr(obj, "banned", False))
        obj.fix_rolled = str(getattr(obj, "fix_rolled", "") or "")
        obj.coach_majors = list(getattr(obj, "coach_majors", None) or [])
        obj.loan = getattr(obj, "loan", None) or None
        if obj.loan and not isinstance(obj.loan, dict):
            obj.loan = None
        obj.unsigned = bool(getattr(obj, "unsigned", False))
        if obj.exists and not str(getattr(obj, "team_id", "") or ""):
            obj.unsigned = True
        obj.you_card = dict(getattr(obj, "you_card", None) or {})
        obj.loan_default_pending = bool(getattr(obj, "loan_default_pending", False))
        obj.last_offer_month = str(getattr(obj, "last_offer_month", "") or "")
        obj.retired = bool(getattr(obj, "retired", False))
        obj.ending = str(getattr(obj, "ending", "") or "")
        obj.ending_title = str(getattr(obj, "ending_title", "") or "")
        obj.ending_text = str(getattr(obj, "ending_text", "") or "")
        obj.academy_used = list(getattr(obj, "academy_used", None) or [])
        obj.last_birthday = str(getattr(obj, "last_birthday", "") or "")
        obj.start_year = int(getattr(obj, "start_year", 0) or getattr(obj, "year", 2026) or 2026)
        if obj.role == "support":
            obj.role = "rifle"
            dirty = True
        if (obj.you_card or {}).get("role") == "support":
            obj.you_card["role"] = "rifle"
            dirty = True
        for row in obj.free or []:
            if isinstance(row, dict) and row.get("role") == "support":
                row["role"] = "rifle"
                dirty = True
        if skins.repair_items(obj.inventory) or dirty:
            obj.save()
        return obj

    def over(self) -> bool:
        return bool(self.banned or self.retired)

    def _apply_ending(self, key: str) -> dict:
        ending = plot.ENDINGS[key]
        self.ending = ending["id"]
        self.ending_title = ending["title"]
        self.ending_text = ending["text"]
        return ending

    # ---------------------------------------------------------------- lookups

    def my_team(self, teams: list[dict]) -> dict | None:
        return next((t for t in teams if t["id"] == self.team_id), None)

    def my_player(self, teams: list[dict]) -> dict | None:
        team = self.my_team(teams)
        if not team:
            return None
        return next((p for p in team["players"] if p["name"] == self.player_name), None)

    def fix_placeholder_mates(self, season) -> bool:
        """Swap the old rook1..rook4 stand-ins for real free agents.

        Careers made before this existed still carry the placeholders, and CS2
        gives a nameless bot a random pro name, so the roster never matched.
        """
        team = self.my_team(season.teams)
        if not team:
            return False
        slots = [p for p in team["players"] if PLACEHOLDER_RE.match(p.get("name") or "")]
        if not slots:
            return False
        picks = starter_mates(
            team.get("region") or "AS",
            [p.get("role") or "rifle" for p in slots],
            skip=roster_names(season.teams) | set(self.hidden),
        )
        for slot, (name, ability, _role) in zip(slots, picks):
            self.log.append(f"{slot['name']} 换成 {name}（{int(ability)}）。")
            slot["name"] = name
            slot["ability"] = float(ability)
            slot["form"] = max(52.0, float(ability) - 6)
            slot["age"] = age_of(name, season.year)
        self.rebuild_free(season.teams)
        return True

    def rebuild_free(self, teams: list[dict]) -> None:
        taken = roster_names(teams) | set(self.hidden)
        rows = []
        for row in agent_rows():
            if row["name"] in taken:
                continue
            row["age"] = age_of(row["name"], self.year)
            row["fee"] = transfer_fee(row["ability"])
            rows.append(row)
        self.free = rows

    # ---------------------------------------------------------------- create

    def create(self, payload: dict, season) -> str:
        era = payload.get("era") or "2026"
        meta = ERA_META[era]
        mode = payload.get("mode") or "join"
        role = payload.get("role") or "rifle"

        self.exists = True
        self.era = era
        self.year = meta["year"]
        self.role = role if role in PLAYABLE_ROLES else "rifle"
        self.mode = mode
        self.money = START_POCKET
        self.last_scrim = ""
        self.last_sponsor_month = meta["start"][:7]
        self.last_age_year = self.year
        self.registered = []
        self.hidden = []
        self.seen_stories = []
        self.story_queue = []
        self.inbox = []
        self.mail_seq = 0
        self.attr_points = 0
        self.last_ops_month = meta["start"][:7]
        self.crisis = False
        self.deficit = 0
        self.inventory = []
        self.equipped = {}
        self.equipped_ct = {}
        self.equipped_t = {}
        self.skin_quotes = {}
        self.skin_quotes_prev = {}
        self.case_prices = {}
        self.real_skins = False
        self.steam_id = ""
        self.skin_seq = 0
        self.pending_drop = None
        skins.ensure_economy(self)
        self.ops_log = []
        self.fix_chance = plot.FIX_BASE
        self.fix_pending = False
        self.throwing = False
        self.banned = False
        self.fix_rolled = ""
        self.coach_majors = []
        self.loan = None
        self.unsigned = False
        self.you_card = {}
        self.loan_default_pending = False
        self.last_offer_month = ""
        self.retired = False
        self.ending = ""
        self.ending_title = ""
        self.ending_text = ""
        self.academy_used = []
        self.last_birthday = ""
        self.start_year = self.year
        self.log = [f"生涯开始：{era} {meta['title']}"]

        if mode == "create":
            self.player_name = (payload.get("name") or "Player").strip() or "Player"
            org = (payload.get("org") or f"{self.player_name} Club").strip()
            self.team_id = slug(org)
            self.replaced = ""
            self._spawn_org(season, org, payload)
            self.log.append(f"创建 {org}，你是 {self.player_name}。")
        else:
            team = next(t for t in season.teams if t["id"] == payload.get("team_id"))
            wanted = (payload.get("replace") or "").strip()
            slot = next((p for p in team["players"] if p["name"] == wanted), None)
            if slot is None:
                names = "、".join(p["name"] for p in team["players"])
                raise ValueError(
                    f"{team['name']} 在 {era} 的名单是 {names}，没有 {wanted or '这个人'}。"
                    "换年代后请重新选要接管的选手。"
                )
            self.player_name = slot["name"]
            self.team_id = team["id"]
            self.replaced = slot["name"]
            self.hidden.append(slot["name"])
            slot["role"] = self.role
            slot["you"] = True
            self.log.append(f"加入 {team['name']}，接管 {slot['name']}（{int(slot['ability'])}）。")

        self.rebuild_free(season.teams)
        self._remember_you(season)
        self.watch(season, when="start")
        self.dispatch_invites(season)
        try:
            from ..cs2.launch import settings
            from ..cs2.profiles import seed_mod_profiles

            added = seed_mod_profiles(Path(settings()["mod_source_path"]), season.teams)
            if added:
                self.log.append(f"人机库补录 {added} 个新名字。")
        except Exception:
            pass
        self.save()
        return self.log[-1]

    def _spawn_org(self, season, org: str, payload: dict) -> None:
        region = payload.get("region") if payload.get("region") in ("EU", "AM", "AS") else "AS"
        roles = ["entry", "rifle", "awp", "igl"]
        if self.role == "awp":
            roles[2] = "rifle"
        if self.role == "igl":
            roles[3] = "rifle"
        mates = starter_mates(region, roles)
        you_stats = stats_for(self.player_name, self.role, ORG_START_ABILITY)
        players = [
            {
                "name": self.player_name,
                "role": self.role,
                "ability": ORG_START_ABILITY,
                "command": int(you_stats["command"]),
                "stats": you_stats,
                "form": 66,
                "age": 19,
                "you": True,
            }
        ]
        for name, ability, role in mates:
            row = _signed({"name": name, "role": role, "ability": ability})
            row["form"] = ability - 6
            row["age"] = age_of(name, season.year)
            players.append(row)
        strong, weak = maps_for(len(season.teams), org)
        team = {
            "id": self.team_id,
            "name": org,
            "region": region,
            "tier": tier_of(45),
            "world_rank": 45,
            "command": 58,
            "strong_maps": strong,
            "weak_maps": weak,
            "money": 35000,
            "mentality": 62,
            "series_streak": 0,
            "loss_streak": 0,
            "last_region": region,
            "mentality_log": [],
            "color": payload.get("color") or "#6ea8ff",
            "players": players,
        }
        refresh_team_command(team)
        if payload.get("logo"):
            team["logo"] = payload["logo"]
        season.teams.append(team)
        season.vrs.seed([team], season.date)

    def set_logo(self, season, src: str) -> str:
        team = self.my_team(season.teams)
        if not team:
            return "还没有队伍。"
        team["logo"] = src
        self.log.append("更新了队标。")
        return "队标已更新。"

    def _remember_you(self, season) -> None:
        you = self.my_player(season.teams) if season is not None else None
        if not you:
            return
        self.you_card = {
            "name": you.get("name") or self.player_name,
            "role": you.get("role") or self.role,
            "ability": float(you.get("ability") or 74),
            "command": int(you.get("command") or 0),
            "stats": you.get("stats") or stats_for(self.player_name, self.role, float(you.get("ability") or 74)),
            "form": you.get("form", max(52.0, float(you.get("ability") or 74) - 8)),
            "age": you.get("age") or 19,
            "igl_years": int(you.get("igl_years") or 0),
            "you": True,
        }
        self.role = you.get("role") or self.role

    def _you_stats(self, season=None) -> dict:
        if season is not None:
            you = self.my_player(season.teams)
            if you:
                return you
        return dict(self.you_card or {})

    # ---------------------------------------------------------------- ticking

    def tick(self, season, _prev_date: str) -> None:
        if not self.exists:
            return
        self._remember_you(season)
        if self.over():
            self.save()
            return
        month = season.date[:7]
        if month != self.last_sponsor_month:
            for stamp in economy.months_after(self.last_sponsor_month, month):
                self._pay_sponsors(season, stamp)
            self.last_sponsor_month = month
        if month != self.last_ops_month:
            for stamp in economy.months_after(self.last_ops_month, month):
                self._settle_month(season, stamp)
                if self.loan_default_pending:
                    break
                self._charge_loan_interest(season, stamp)
                if self.loan_default_pending:
                    break
            if not self.loan_default_pending:
                self.last_ops_month = month
        year = int(season.date[:4])
        if year > self.last_age_year:
            leftover = self.attr_points
            self.attr_points = 0
            if leftover:
                self.log.append(f"{year} 年未使用的 {leftover} 点属性已清零。")
            self._age_year(season, year)
            self.last_age_year = year
        if self.unsigned and not self.over() and not self.loan_default_pending:
            self._dispatch_contracts(season)
        elif not self.unsigned and not self.over():
            self.dispatch_invites(season)
        skins.advance_day(self)
        self._birthday_tick(season)
        self.save()

    def _pay_sponsors(self, season, month: str) -> None:
        rank_map = {r["id"]: r["rank"] for r in season.vrs.table(season.teams, season.date)}
        for t in season.teams:
            pay = sponsor_month(rank_map.get(t["id"], 40))
            if t["id"] == self.team_id and not self.unsigned:
                self._push_mail(
                    "sponsor",
                    season.date,
                    mail.sponsor_letter(month, rank_map.get(t["id"], 40), pay),
                    {"amount": pay, "rank": rank_map.get(t["id"], 40), "month": month},
                )
            else:
                t["money"] = t.get("money", 0) + pay

    def _age_year(self, season, year: int) -> None:
        # Roster aging (gun + IGL command) already ran in Season.roll_year.
        self.year = year
        from ..world.aging import apply_player_year

        for row in self.free:
            apply_player_year(row)
            row["fee"] = transfer_fee(row["ability"])
        self.log.append(f"{year} 转会期：年龄曲线生效。")
        self._academy_intake(season, year)
        self._ai_window(season)

    def _academy_intake(self, season, year: int) -> None:
        from ..world.academy import intake

        taken = roster_names(season.teams) | {r.get("name") for r in self.free} | set(self.hidden)
        start = int(self.start_year or year)
        rows = intake(year, start, self.academy_used, taken)
        for row in rows:
            row["fee"] = transfer_fee(row["ability"])
            self.free.append(row)
            self.academy_used.append(row["name"])
            kind = "天才" if row.get("note") == "wonder" else "青训"
            self.log.append(
                f"{year} 青训营：{kind} {row['name']}（{int(row['ability'])}，潜力 {int(row.get('potential') or 0)}）进入转会市场。"
            )

    def _birthday_tick(self, season) -> None:
        if self.over() or self.unsigned or not self.team_id:
            return
        date = season.date or ""
        if len(date) < 10 or self.last_birthday == date:
            return
        self.last_birthday = date
        try:
            month, day = int(date[5:7]), int(date[8:10])
        except ValueError:
            return
        team = self.my_team(season.teams)
        if not team:
            return
        for player in team.get("players") or []:
            name = player.get("name") or ""
            if not name or name == self.player_name or player.get("you"):
                continue
            if birthday_md(name) == (month, day):
                self._push_plot(plot.birthday_popup(name), f"bday.{date}.{name}")

    def _ai_window(self, season) -> None:
        table = {r["id"]: r for r in season.vrs.table(season.teams, season.date)}
        for t in season.teams:
            if t["id"] == self.team_id:
                continue
            aging_out = any(int(p.get("age") or 0) >= 31 for p in t.get("players") or [])
            weak = min(t["players"], key=lambda p: p["ability"])
            if weak["ability"] >= 84 and not aging_out:
                continue
            if t.get("mentality", 70) > 66 and t.get("loss_streak", 0) < 3 and not aging_out:
                continue
            row = table.get(t["id"], {})
            for cand in sorted(self.free, key=lambda x: -x["ability"])[:12]:
                fee = transfer_fee(cand["ability"])
                if t.get("money", 0) < fee:
                    continue
                if buy_chance(row.get("vrs", 1000), cand["ability"], t["money"], fee) < 0.35:
                    continue
                t["money"] -= fee
                outgoing = dict(weak)
                outgoing["team"] = None
                outgoing["fee"] = transfer_fee(outgoing["ability"])
                t["players"] = [p for p in t["players"] if p["name"] != weak["name"]]
                t["players"].append(_signed(cand))
                refresh_team_command(t)
                self.free = [x for x in self.free if x["name"] != cand["name"]]
                if outgoing["name"] not in self.hidden:
                    self.free.append(outgoing)
                self.log.append(f"{t['name']} 签下 {cand['name']}，放走 {weak['name']}。")
                break

    # ---------------------------------------------------------------- actions

    def buy(self, season, player_name: str) -> str:
        if self.unsigned or not self.team_id:
            return "你现在是自由身，先在邮箱接下合同。"
        team = self.my_team(season.teams)
        if not team:
            return "没有自己的队伍。"
        cand = next((x for x in self.free if x["name"] == player_name), None)
        if not cand:
            return "自由市场没有这个人。"
        fee = transfer_fee(cand["ability"])
        row = {r["id"]: r for r in season.vrs.table(season.teams, season.date)}.get(
            team["id"], {"vrs": 900}
        )
        chance = buy_chance(row["vrs"], cand["ability"], team.get("money", 0), fee)
        if team.get("money", 0) < fee:
            return f"转会费 ${fee:,} 不够。"
        if chance < 0.18:
            return f"{cand['name']} 看不上现在的队伍，成功率只有 {chance:.0%}。"
        if random.random() > max(0.2, chance):
            team["money"] -= int(fee * 0.08)
            return f"{cand['name']} 拒签，谈判费打了水漂。"
        weak = min(team["players"], key=lambda p: (p.get("you") is True, p["ability"]))
        if weak.get("you"):
            return "不能把自己卖掉。"
        outgoing = dict(weak)
        outgoing["fee"] = transfer_fee(outgoing["ability"])
        team["players"] = [p for p in team["players"] if p["name"] != weak["name"]]
        team["players"].append(_signed(cand))
        refresh_team_command(team)
        team["money"] -= fee
        self.free = [x for x in self.free if x["name"] != cand["name"]]
        if outgoing["name"] not in self.hidden:
            self.free.append(outgoing)
        msg = f"签下 {cand['name']}，{weak['name']} 离队，花费 ${fee:,}。"
        self.log.append(msg)
        self.save()
        return msg

    def finish_training(self, season) -> str:
        """Mentality bump after a real CS2 training match. Once per calendar day."""
        if self.over():
            return "这段生涯已经结束，只能重开。"
        if self.unsigned or not self.team_id:
            return "你现在是自由身，先在邮箱接下合同再进训练赛。"
        if self.last_scrim == season.date:
            return "今天的训练加成已经给过了，这局只当热身。"
        team = self.my_team(season.teams)
        if not team:
            return "没有找到你的队伍。"
        before = float(team.get("mentality") or 70)
        gain = scrim_mentality_gain(before)
        self.last_scrim = season.date
        if gain <= 0:
            msg = "训练赛打完。心态已经很高，热身几乎带不动了。"
        else:
            after = shift_mentality(team, gain)
            msg = f"训练赛打完。心态 +{gain:.2f} → {after:.1f}（边际递减，不涨个人能力）。"
        self.log.append(msg)
        self.save()
        return msg

    def scrim(self, season, opp_id: str) -> str:
        """Kept for old clients; training now happens in CS2 via finish_training."""
        return self.finish_training(season)

    def register(self, season, event_id: str) -> str:
        ev = next((e for e in season.events if e["id"] == event_id), None)
        if not ev:
            return "没有这个赛事。"
        if ev["status"] != "upcoming":
            return "已经开打或结束，报不了名。"
        table = season.vrs.table(season.teams, season.date)
        mine = next((r for r in table if r["id"] == self.team_id), None)
        if not mine:
            return "找不到你的队伍。"
        if self.over():
            return "这段生涯已经结束，只能重开。"
        if ev["type"] in ("major", "t1"):
            return "大赛不能自行报名。直邀或附加赛出线才会收到邀请。"
        if ev["type"] in ("cct", "qual") and mine["region"] != ev["region"]:
            return f"{ev['name']} 只收 {ev['region']} 赛区的队伍。"
        need = mail.INVITE_NEED.get(ev["type"], 30)
        if mine["rank"] > need:
            return f"VRS 第 {mine['rank']}，{ev['type'].upper()} 需要前 {need}。"
        if event_id not in self.registered:
            self.registered.append(event_id)
        self.log.append(f"报名 {ev['name']}")
        self.save()
        return f"已报名 {ev['name']}"

    def award_event(self, season, ev: dict) -> None:
        team = self.my_team(season.teams)
        if not team or ev.get("status") != "done" or ev.get("career_paid"):
            return
        played = any(team["name"] in (m.get("team_a"), m.get("team_b")) for m in ev.get("matches", []))
        if not played:
            return
        ev["career_paid"] = True

        place = awards.placements(ev)
        spot = place.get(team["name"], "stage")
        series = [
            m
            for m in ev.get("matches") or []
            if m.get("played")
            and m.get("team_b") != "BYE"
            and team["name"] in (m.get("team_a"), m.get("team_b"))
        ]
        n = len(series)
        extra = 1 if spot == "champion" else 0
        gained = n + extra
        self.attr_points += gained
        bits = [f"系列赛 {n}"]
        if extra:
            bits.append("冠军 +1")
        note = f"属性点 +{gained}（{'，'.join(bits)}）"
        self.log.append(f"{ev['name']} 结束，{note}。今年剩余 {self.attr_points} 点。")

        pool = int(ev.get("prize") or 0)
        pay = int(pool * awards.PRIZE_SPLIT.get(spot, 0.0))
        if pay:
            self._push_mail(
                "prize",
                season.date,
                mail.prize_letter(ev, team["name"], spot, pay),
                {"amount": pay, "event_id": ev["id"], "spot": spot},
            )

        champ = ev.get("champion") == team["name"]
        award = ev.get("awards") or {}
        mvp = (award.get("mvp") or {}).get("player") == self.player_name
        evp = any(r["player"] == self.player_name for r in award.get("evp") or [])
        if champ:
            self.log.append(f"🏆 {ev['name']} 夺冠！")
        if mvp:
            title = (award.get("mvp") or {}).get("title") or "MVP"
            self.log.append(f"⭐ {ev['name']} {title}！")
        elif evp:
            title = ((award.get("evp") or [{}])[0]).get("title") or "EVP"
            self.log.append(f"✦ {ev['name']} {title}。")
        if ev.get("type") == "qual" and team["id"] in (ev.get("qualified_out") or []):
            dest = next((e for e in season.events if e["id"] == ev.get("feeds")), None)
            self._push_mail(
                "qualify",
                season.date,
                mail.qualify_letter(ev, dest, team["name"]),
                {"event_id": ev["id"], "dest_id": ev.get("feeds"), "major_id": ev.get("feeds"), "status": "open"},
            )
            self.log.append(f"出线 {ev['name']} → {(dest or {}).get('name') or '正赛'}。")
            if dest:
                self.offer_invite(season, dest, earned=True)
        if ev.get("type") == "major":
            team["money"] = team.get("money", 0) + economy.MAJOR_APPEARANCE
            self.ops_log.append(f"{ev['name']} 出场费 ${economy.MAJOR_APPEARANCE:,} 进俱乐部。")
            self.log.append(f"打入 {ev['name']}，俱乐部收到出场费 ${economy.MAJOR_APPEARANCE:,}。")
        self.watch(season, ev)
        self.save()

    # ---------------------------------------------------------------- mail / points / roles

    def _mail(self, mail_id: str) -> dict | None:
        return next((row for row in self.inbox if row.get("id") == mail_id), None)

    def _push_mail(self, kind: str, date: str, payload: dict, extra: dict | None = None) -> dict:
        self.mail_seq += 1
        row = mail.new_mail(kind, date, payload, extra)
        row["id"] = f"{kind}.{self.mail_seq}"
        self.inbox.append(row)
        return row

    def unread_count(self) -> int:
        return sum(1 for row in self.inbox if not row.get("read"))

    def eligible_invite(self, season, ev: dict) -> bool:
        if ev.get("status") != "upcoming":
            return False
        table = season.vrs.table(season.teams, season.date)
        mine = next((r for r in table if r["id"] == self.team_id), None)
        if not mine:
            return False
        if ev["type"] == "major":
            if season.year >= 2025:
                return mine["rank"] <= ev.get("size", mail.MAJOR_VRS_RANK)
            if self.team_id in (season.qualified.get(ev["id"]) or []):
                return True
            return mine["rank"] <= mail.LEGEND_RANK
        if ev["type"] == "t1":
            if self.team_id in (season.qualified.get(ev["id"]) or []):
                return True
            return mine["rank"] <= season.dest_direct(ev)
        if ev["type"] == "qual":
            dest = next((e for e in season.events if e["id"] == ev.get("feeds")), None)
            if dest and dest.get("type") == "t1":
                if mine["rank"] <= season.dest_direct(dest):
                    return False
                return mine["rank"] <= mail.PLAYIN_RANK
            if dest and dest.get("type") == "major" and season.year >= 2025:
                return False
            if mine["region"] != ev["region"]:
                return False
            return mine["rank"] <= mail.INVITE_NEED.get("qual", 40)
        if ev["type"] == "cct":
            return mine["region"] == ev["region"]
        if ev["type"] == "t2":
            return True
        need = mail.INVITE_NEED.get(ev["type"], 30)
        if mine["rank"] > need:
            return False
        return True

    def dispatch_invites(self, season) -> None:
        if self.unsigned or not self.team_id or self.banned:
            return
        if not self.exists:
            return
        for row in self.inbox:
            if row.get("kind") != "invite" or row.get("status") != "open":
                continue
            ev = next((e for e in season.events if e["id"] == row.get("event_id")), None)
            if ev and ev.get("status") != "upcoming":
                row["status"] = "expired"
        upcoming = [e for e in season.events if e.get("status") == "upcoming"]
        upcoming.sort(key=lambda e: (e.get("dates") or [""])[0])
        today = season.date

        def days_until(ev: dict) -> int:
            start = (ev.get("dates") or [today])[0]
            try:
                a = datetime.strptime(today, "%Y-%m-%d").date()
                b = datetime.strptime(start, "%Y-%m-%d").date()
                return (b - a).days
            except ValueError:
                return 99

        eligible = [e for e in upcoming if self.eligible_invite(season, e)]
        near = [e for e in eligible if days_until(e) <= 28]
        small = [e for e in eligible if e.get("type") in ("cct", "t2") and days_until(e) <= 50]
        chosen = []
        for ev in near + small + eligible[:3]:
            if ev not in chosen:
                chosen.append(ev)
        table = {r["id"]: r for r in season.vrs.table(season.teams, season.date)}
        rank = (table.get(self.team_id) or {}).get("rank", 40)
        for ev in chosen:
            earned = self.team_id in (season.qualified.get(ev["id"]) or [])
            self.offer_invite(season, ev, earned=earned, rank=rank)

    def offer_invite(self, season, ev: dict, earned: bool = False, rank: int | None = None) -> dict | None:
        if any(row.get("kind") == "invite" and row.get("event_id") == ev["id"] for row in self.inbox):
            return None
        if ev.get("status") != "upcoming":
            return None
        team = self.my_team(season.teams)
        if rank is None:
            table = {r["id"]: r for r in season.vrs.table(season.teams, season.date)}
            rank = (table.get(self.team_id) or {}).get("rank", 40)
        letter = mail.invite_letter(ev, team["name"] if team else "", rank, earned=earned)
        return self._push_mail(
            "invite",
            season.date,
            letter,
            {"event_id": ev["id"], "event": ev.get("name"), "short": ev.get("short") or ev.get("name")},
        )

    def mark_read(self, mail_id: str = "") -> str:
        if mail_id:
            row = self._mail(mail_id)
            if not row:
                return "没有这封邮件。"
            row["read"] = True
            return "已读。"
        for row in self.inbox:
            row["read"] = True
        return "全部标为已读。"

    def accept_invite(self, season, mail_id: str) -> str:
        if self.banned:
            return "你已被禁赛，这份档案只能重开。"
        row = self._mail(mail_id)
        if row and row.get("kind") == "whisper":
            return self.answer_fix(season, True, mail_id)
        if row and row.get("kind") == "contract":
            return self.accept_contract(season, mail_id)
        if not row or row.get("kind") != "invite":
            return "这不是邀请函。"
        if row.get("status") != "open":
            return "这封邀请已经失效。"
        ev = next((e for e in season.events if e["id"] == row.get("event_id")), None)
        if not ev or ev.get("status") != "upcoming":
            row["status"] = "expired"
            row["read"] = True
            return "赛事已经开打或结束，来不及接受了。"
        if ev["id"] not in self.registered:
            self.registered.append(ev["id"])
        row["status"] = "accepted"
        row["read"] = True
        self.log.append(f"接受邀请：{ev['name']}")
        self.save()
        return f"已接受 {ev['name']} 的邀请。"

    def decline_invite(self, season, mail_id: str) -> str:
        row = self._mail(mail_id)
        if row and row.get("kind") == "whisper":
            return self.answer_fix(season, False, mail_id)
        if row and row.get("kind") == "contract":
            return self.decline_contract(mail_id)
        if not row or row.get("kind") != "invite":
            return "这不是邀请函。"
        if row.get("status") != "open":
            return "这封邀请已经失效。"
        ev_id = row.get("event_id")
        if ev_id in self.registered:
            self.registered = [x for x in self.registered if x != ev_id]
        row["status"] = "declined"
        row["read"] = True
        name = row.get("event") or ev_id
        self.log.append(f"婉拒邀请：{name}")
        self.save()
        return f"已婉拒 {name}。"

    def claim_mail(self, season, mail_id: str) -> str:
        row = self._mail(mail_id)
        if not row or row.get("kind") not in ("prize", "sponsor"):
            return "这封邮件没有可领取的款项。"
        if row.get("status") == "claimed":
            return "已经领过了。"
        amount = int(row.get("amount") or 0)
        team = self.my_team(season.teams)
        if not team:
            return "还没有队伍。"
        if row.get("kind") == "prize":
            club, pocket = economy.split_prize(amount)
            team["money"] = team.get("money", 0) + club
            self.money += pocket
            note = f"领取赛事分成：俱乐部队 ${club:,}，个人 ${pocket:,}。"
        else:
            team["money"] = team.get("money", 0) + amount
            note = f"领取赞助 ${amount:,}，全部进俱乐部。"
        row["status"] = "claimed"
        row["read"] = True
        self.log.append(note)
        self.save()
        return note

    def _settle_month(self, season, month: str) -> None:
        team = self.my_team(season.teams)
        if not team:
            return
        if self.crisis:
            if self.loan and self.loan.get("kind") == "club":
                self._begin_loan_default(season)
                return
            self._dissolve_club(season)
            return
        table = {r["id"]: r["rank"] for r in season.vrs.table(season.teams, season.date)}
        rank = table.get(self.team_id, 40)
        burn = economy.month_burn(team.get("players") or [], rank)
        cash = int(team.get("money") or 0)
        you_pay = next((w["pay"] for w in burn["wages"] if w["name"] == self.player_name), 0)
        if cash < burn["total"]:
            team["money"] = 0
            self.crisis = True
            self.deficit = burn["total"] - cash
            self.ops_log.append(f"{month} 发不出工资。缺口 ${self.deficit:,}。")
            self.log.append(f"俱乐部没钱了。缺口 ${self.deficit:,}。捐款续命，否则下月解散。")
            self._push_mail(
                "ops",
                season.date,
                {
                    "title": f"{month} 经营危机",
                    "from": "俱乐部财务",
                    "body": (
                        f"本月工资 ${burn['salaries']:,}，吃住 ${burn['living']:,}，一共 ${burn['total']:,}。\n"
                        f"账上只有 ${cash:,}。请用个人口袋捐给俱乐部，否则下个月队伍解散。"
                    ),
                },
                {"status": "open", "deficit": self.deficit},
            )
            return
        team["money"] = cash - burn["total"]
        self.money += you_pay
        self.crisis = False
        self.deficit = 0
        self.ops_log.append(
            f"{month} 工资 ${burn['salaries']:,}，吃住 ${burn['living']:,}，你到手 ${you_pay:,}，账上 ${team['money']:,}。"
        )
        self.log.append(f"{month} 发薪：个人 ${you_pay:,}，俱乐部剩余 ${team['money']:,}。")

    def donate(self, season, amount: int) -> str:
        team = self.my_team(season.teams)
        pay = max(0, int(amount or 0))
        if not team:
            return "还没有队伍。"
        if pay <= 0:
            return "捐款金额不对。"
        if self.money < pay:
            return "口袋里不够。"
        self.money -= pay
        team["money"] = team.get("money", 0) + pay
        if self.crisis:
            if team["money"] >= self.deficit:
                self.crisis = False
                self.deficit = 0
                msg = f"你捐了 ${pay:,}。俱乐部缓过来了。"
            else:
                self.deficit = max(0, self.deficit - pay)
                msg = f"你捐了 ${pay:,}。还差 ${self.deficit:,}。"
        else:
            msg = f"你捐了 ${pay:,}。俱乐部账上 ${team['money']:,}。"
        self.ops_log.append(msg)
        self.log.append(msg)
        self.save()
        return msg

    def _loan_rank(self, season) -> int:
        if not self.team_id:
            return 40
        table = {r["id"]: r["rank"] for r in season.vrs.table(season.teams, season.date)}
        return int(table.get(self.team_id, 40) or 40)

    def _loan_cap(self, season) -> int:
        team = self.my_team(season.teams)
        if not team or self.unsigned:
            return 0
        rank = self._loan_rank(season)
        kind = economy.loan_kind_for_mode(self.mode)
        if kind == "bank":
            return economy.bank_borrow_cap(rank)
        burn = economy.month_burn(team.get("players") or [], rank)
        return economy.club_borrow_cap(int(team.get("money") or 0), burn["total"])

    def _loan_public(self, season, team: dict | None, table: dict) -> dict:
        loan = self.loan if isinstance(self.loan, dict) else None
        kind = (loan or {}).get("kind") or economy.loan_kind_for_mode(self.mode)
        rate = float((loan or {}).get("rate") or economy.rate_for_kind(kind))
        principal = int((loan or {}).get("principal") or 0)
        arrears = int((loan or {}).get("arrears") or 0)
        cap = self._loan_cap(season) if not (loan and principal > 0) else 0
        return {
            "kind": kind,
            "kind_label": "银行" if kind == "bank" else "俱乐部",
            "principal": principal,
            "arrears": arrears,
            "missed": int((loan or {}).get("missed") or 0),
            "rate": rate,
            "interest": economy.interest_due(principal, rate) if principal else 0,
            "cap": cap,
            "active": bool(loan and principal > 0),
            "pending": self.loan_default_pending,
        }

    def borrow(self, season, amount: int) -> str:
        if self.banned:
            return "你已被禁赛，这份档案只能重开。"
        if self.unsigned or not self.team_id:
            return "你现在是自由身，不能借款。"
        if self.loan_default_pending:
            return "先处理俱乐部的最后通牒。"
        if self.loan and int(self.loan.get("principal") or 0) > 0:
            return "先还清这一笔，才能再借。"
        team = self.my_team(season.teams)
        if not team:
            return "还没有队伍。"
        pay = max(0, int(amount or 0))
        if pay <= 0:
            return "借款金额不对。"
        cap = self._loan_cap(season)
        if cap <= 0:
            return "现在借不了。俱乐部要留至少一个月的工资和吃住。"
        if pay > cap:
            return f"最多能借 ${cap:,}。"
        kind = economy.loan_kind_for_mode(self.mode)
        rate = economy.rate_for_kind(kind)
        if kind == "club":
            if int(team.get("money") or 0) < pay:
                return "俱乐部账上不够。"
            team["money"] = int(team.get("money") or 0) - pay
            self.money += pay
            note = f"从俱乐部借了 ${pay:,}，进个人口袋。月息 {int(rate * 100)}%。"
        else:
            team["money"] = int(team.get("money") or 0) + pay
            note = f"向银行借了 ${pay:,}，进俱乐部金库。月息 {int(rate * 100)}%。"
        self.loan = {
            "kind": kind,
            "principal": pay,
            "rate": rate,
            "missed": 0,
            "arrears": 0,
            "last_interest_month": season.date[:7],
        }
        self.ops_log.append(note)
        self.log.append(note)
        self.save()
        return note

    def repay(self, season, amount: int) -> str:
        if self.unsigned or not self.team_id:
            return "你现在是自由身，这笔账已经勾销。"
        if self.loan_default_pending:
            return "先处理俱乐部的最后通牒。"
        loan = self.loan if isinstance(self.loan, dict) else None
        if not loan or int(loan.get("principal") or 0) <= 0:
            return "没有欠款。"
        pay = max(0, int(amount or 0))
        if pay <= 0:
            return "还款金额不对。"
        if self.money < pay:
            return "口袋里不够。"
        team = self.my_team(season.teams)
        arrears = int(loan.get("arrears") or 0)
        principal = int(loan.get("principal") or 0)
        kind = loan.get("kind") or "club"
        take = pay
        paid_interest = 0
        paid_principal = 0
        if arrears and take:
            bit = min(take, arrears)
            self.money -= bit
            take -= bit
            loan["arrears"] = arrears - bit
            paid_interest = bit
            if kind == "club" and team is not None:
                team["money"] = int(team.get("money") or 0) + bit
            if loan["arrears"] <= 0:
                loan["missed"] = 0
                loan["arrears"] = 0
        if take and principal:
            bit = min(take, principal)
            self.money -= bit
            take -= bit
            loan["principal"] = principal - bit
            paid_principal = bit
            if kind == "club" and team is not None:
                team["money"] = int(team.get("money") or 0) + bit
        if take:
            self.money += take
        if int(loan.get("principal") or 0) <= 0 and int(loan.get("arrears") or 0) <= 0:
            self.loan = None
            note = f"还清了。利息 ${paid_interest:,}，本金 ${paid_principal:,}。"
        else:
            parts = []
            if paid_interest:
                parts.append(f"利息 ${paid_interest:,}")
            if paid_principal:
                parts.append(f"本金 ${paid_principal:,}")
            left = int((self.loan or {}).get("principal") or 0)
            miss = int((self.loan or {}).get("missed") or 0)
            note = f"还了{'、'.join(parts) or '一笔'}。还欠本金 ${left:,}，连续未付息 {miss} 个月。"
        self.ops_log.append(note)
        self.log.append(note)
        self.save()
        return note

    def _charge_loan_interest(self, season, month: str) -> None:
        loan = self.loan if isinstance(self.loan, dict) else None
        if not loan or self.loan_default_pending:
            return
        if str(loan.get("last_interest_month") or "") == month:
            return
        principal = int(loan.get("principal") or 0)
        if principal <= 0:
            self.loan = None
            return
        rate = float(loan.get("rate") or economy.rate_for_kind(loan.get("kind") or "club"))
        due = economy.interest_due(principal, rate)
        team = self.my_team(season.teams)
        loan["last_interest_month"] = month
        if self.money >= due:
            self.money -= due
            loan["arrears"] = 0
            loan["missed"] = 0
            if loan.get("kind") == "club" and team is not None:
                team["money"] = int(team.get("money") or 0) + due
            self.ops_log.append(f"{month} 利息 ${due:,} 已从口袋扣除。")
            return
        loan["arrears"] = int(loan.get("arrears") or 0) + due
        loan["missed"] = int(loan.get("missed") or 0) + 1
        self.ops_log.append(f"{month} 口袋不够付利息 ${due:,}。连续未付 {loan['missed']} 个月。")
        self.log.append(f"{month} 没付上利息。连续 {loan['missed']} 个月。")
        if loan["missed"] >= economy.LOAN_MISS_LIMIT:
            self._begin_loan_default(season)

    def _begin_loan_default(self, season) -> None:
        if self.loan_default_pending:
            self._ensure_loan_popup()
            return
        self.loan_default_pending = True
        self._ensure_loan_popup()
        self.log.append("俱乐部发来最后通牒。")

    def _ensure_loan_popup(self) -> None:
        if not self.loan_default_pending:
            return
        if any(item.get("when") == "loan_default" for item in self.story_queue):
            return
        self._push_plot(plot.loan_default_popup(), f"loan.default.{self.mail_seq + 1}")

    def answer_loan_default(self, season, choice: str) -> str:
        if not self.loan_default_pending:
            return "这封通牒已经处理过了。"
        flee = choice == "flee"
        kept = False
        banned = False
        if flee:
            if random.random() < plot.FLEE_P:
                kept = True
            else:
                banned = True
                kept = True
        self._release_from_club(season, wipe=not kept, banned=banned)
        self.loan_default_pending = False
        self.last_ops_month = season.date[:7] if season is not None else self.last_ops_month
        self.story_queue = [item for item in self.story_queue if item.get("when") != "loan_default"]
        if flee:
            you = self._you_stats(season)
            ability = float(you.get("ability") or 74)
            ending = self._apply_ending("flee")
            self.retired = True
            self._push_plot(plot.loan_flee_news(self.player_name, ability), f"loan.news.{self.mail_seq + 1}")
            if banned:
                self._push_mail(
                    "discipline",
                    season.date if season is not None else "",
                    plot.loan_flee_ban_letter(self.player_name),
                    {"status": "closed"},
                )
                self.log.append("出逃被发现。" + ending["title"] + "。")
            else:
                self.log.append("你带着东西离开了。" + ending["title"] + "。")
            self.save()
            return ending["title"]
        if kept:
            self.log.append("你离开了俱乐部，钱和皮肤还在。现在是自由身。")
            self._dispatch_contracts(season)
            self.save()
            return "你离开了。钱和皮肤还在，等邮箱里的合同。"
        self.log.append("你被移出名单。个人账户和皮肤已清零。现在是自由身。")
        self._dispatch_contracts(season)
        self.save()
        return "你被移出名单。资产已清零，等邮箱里的合同。"

    def _wipe_assets(self) -> None:
        self.money = 0
        self.inventory = []
        self.equipped = {}
        self.equipped_ct = {}
        self.equipped_t = {}
        self.pending_drop = None
        if self.real_skins:
            try:
                skins.sync_live(self)
            except Exception:
                pass

    def _player_to_free(self, season, player: dict, region: str) -> None:
        name = player.get("name") or ""
        if not name or name == self.player_name or name in self.hidden:
            return
        taken = {r.get("name") for r in self.free} | (roster_names(season.teams) - {name})
        if name in taken:
            return
        ability = float(player.get("ability") or 70)
        self.free.append(
            {
                "name": name,
                "role": player.get("role") or "rifle",
                "ability": ability,
                "command": int(player.get("command") or 0),
                "stats": player.get("stats") or stats_for(name, player.get("role") or "rifle", ability),
                "form": player.get("form", max(52.0, ability - 8)),
                "age": player.get("age") or age_of(name, season.year),
                "igl_years": int(player.get("igl_years") or 0),
                "region": region,
                "note": "vet",
                "team": None,
                "fee": transfer_fee(ability),
            }
        )

    def _fill_one_from_free(self, season, team: dict, prefer_role: str) -> None:
        skip = {p.get("name") for p in team.get("players") or []} | set(self.hidden) | {self.player_name}
        cands = [row for row in self.free if row.get("name") not in skip]
        same = [row for row in cands if (row.get("role") or "rifle") == prefer_role]
        pool = same or cands
        if pool:
            pick = max(pool, key=lambda r: float(r.get("ability") or 0))
            team.setdefault("players", []).append(_signed(pick))
            self.free = [row for row in self.free if row.get("name") != pick.get("name")]
            refresh_team_command(team)
            return
        region = team.get("region") or "AS"
        mates = starter_mates(
            region,
            [prefer_role or "rifle"],
            skip=roster_names(season.teams) | set(self.hidden) | {self.player_name},
        )
        if not mates:
            return
        name, ability, role = mates[0]
        st = stats_for(name, role, float(ability))
        team.setdefault("players", []).append(
            {
                "name": name,
                "role": role,
                "ability": float(ability),
                "command": int(st["command"]),
                "stats": st,
                "form": max(52.0, float(ability) - 6),
                "age": age_of(name, season.year),
                "you": False,
            }
        )
        refresh_team_command(team)

    def _release_from_club(self, season, wipe: bool, banned: bool) -> None:
        team = self.my_team(season.teams) if season is not None else None
        self._remember_you(season)
        old_name = team.get("name") if team else "俱乐部"
        prefer = self.role or "rifle"
        if team:
            team["players"] = [p for p in (team.get("players") or []) if p.get("name") != self.player_name]
            team["throwing"] = False
            if len(team.get("players") or []) < 5:
                self._fill_one_from_free(season, team, prefer)
            refresh_team_command(team)
        self.team_id = ""
        self.unsigned = True
        self.loan = None
        self.crisis = False
        self.deficit = 0
        self.registered = []
        self.throwing = False
        self.last_offer_month = ""
        if wipe:
            self._wipe_assets()
        if banned:
            self.banned = True
        letter = plot.loan_release_letter(self.player_name, old_name, wipe)
        self._push_mail("ops", season.date if season is not None else "", letter, {"status": "closed"})
        for row in self.inbox:
            if row.get("kind") == "invite" and row.get("status") == "open":
                row["status"] = "expired"

    def _dispatch_contracts(self, season) -> None:
        if not self.unsigned or self.banned or self.loan_default_pending:
            return
        month = season.date[:7]
        if self.last_offer_month == month:
            return
        open_ids = {
            row.get("team_id")
            for row in self.inbox
            if row.get("kind") == "contract" and row.get("status") == "open"
        }
        if len(open_ids) >= 4:
            self.last_offer_month = month
            return
        targets = self._contract_targets(season, skip=open_ids)
        if not targets:
            self.last_offer_month = month
            return
        n = 2 if len(targets) >= 2 else 1
        if len(targets) > 1 and random.random() < 0.35:
            n = 1
        for team, replace, role in targets[:n]:
            letter = mail.contract_letter(
                team.get("name") or "",
                ROLE_LABEL.get(role, role),
                replace.get("name") or "",
                self.player_name,
            )
            self._push_mail(
                "contract",
                season.date,
                letter,
                {
                    "team_id": team["id"],
                    "team": team.get("name"),
                    "replace": replace.get("name"),
                    "role": role,
                    "status": "open",
                },
            )
        self.last_offer_month = month

    def _contract_targets(self, season, skip: set | None = None) -> list[tuple]:
        skip = set(skip or ())
        you = self._you_stats(season)
        if not you:
            return []
        role = you.get("role") or self.role or "rifle"
        ability = float(you.get("ability") or 74)
        command = int(you.get("command") or 0)
        table = {r["id"]: r for r in season.vrs.table(season.teams, season.date)}
        scored: list[tuple] = []
        fallback: list[tuple] = []
        for team in season.teams:
            tid = team.get("id")
            if not tid or tid in skip or tid == self.team_id:
                continue
            players = list(team.get("players") or [])
            if not players or any(p.get("name") == self.player_name for p in players):
                continue
            rank = int((table.get(tid) or {}).get("rank") or 40)
            if rank <= 9 and ability < 80:
                continue
            if rank <= 16 and ability < 76:
                continue
            replace = None
            offer_role = role
            score = 0.0
            if role == "igl":
                igl = next((p for p in players if p.get("role") == "igl"), None)
                if igl and command >= int(igl.get("command") or 0) + 4:
                    replace = igl
                    offer_role = "igl"
                    score = float(command - int(igl.get("command") or 0) + 24)
            if replace is None:
                same = [p for p in players if (p.get("role") or "rifle") == role]
                if same:
                    weak = min(same, key=lambda p: float(p.get("ability") or 0))
                    if ability + 1 >= float(weak.get("ability") or 0):
                        replace = weak
                        offer_role = role
                        score = ability - float(weak.get("ability") or 0)
            if replace is None:
                weak = min(players, key=lambda p: float(p.get("ability") or 0))
                if ability >= float(weak.get("ability") or 0) + 2:
                    replace = weak
                    offer_role = you.get("role") or role
                    score = ability - float(weak.get("ability") or 0)
            if replace is None:
                weak = min(players, key=lambda p: float(p.get("ability") or 0))
                fallback.append((float(rank) + (ability - float(weak.get("ability") or 0)), team, weak, role))
                continue
            score += rank / 8.0
            scored.append((score, team, replace, offer_role))
        scored.sort(key=lambda x: -x[0])
        out = [(t, r, role) for _, t, r, role in scored]
        if len(out) < 2:
            fallback.sort(key=lambda x: -x[0])
            for _, team, weak, role in fallback:
                if any(team is row[0] for row in out):
                    continue
                out.append((team, weak, role))
                if len(out) >= 2:
                    break
        return out[:2]

    def accept_contract(self, season, mail_id: str) -> str:
        if self.banned:
            return "你已被禁赛，这份档案只能重开。"
        row = self._mail(mail_id)
        if not row or row.get("kind") != "contract":
            return "这不是入队合同。"
        if row.get("status") != "open":
            return "这封合同已经失效。"
        if not self.unsigned:
            return "你已经有队伍了。"
        team = next((t for t in season.teams if t["id"] == row.get("team_id")), None)
        if not team:
            row["status"] = "expired"
            return "这支队伍已经不在了。"
        replace_name = row.get("replace") or ""
        replace = next((p for p in team.get("players") or [] if p.get("name") == replace_name), None)
        if replace is None:
            plist = team.get("players") or []
            if not plist:
                row["status"] = "expired"
                return "这支队伍名单空了。"
            replace = min(plist, key=lambda p: float(p.get("ability") or 0))
            replace_name = replace.get("name") or ""
        offer_role = row.get("role") or self.role or "rifle"
        region = team.get("region") or "AS"
        self._player_to_free(season, replace, region)
        team["players"] = [p for p in (team.get("players") or []) if p.get("name") != replace_name]
        card = dict(self.you_card or {})
        card["name"] = self.player_name
        card["role"] = offer_role
        card["you"] = True
        if not card.get("ability"):
            card["ability"] = 74.0
        if not card.get("stats"):
            card["stats"] = stats_for(self.player_name, offer_role, float(card["ability"]))
        card["ability"] = ability_of(card["stats"], offer_role)
        incoming = _signed(card)
        incoming["you"] = True
        incoming["role"] = offer_role
        team["players"].append(incoming)
        refresh_team_command(team)
        self.team_id = team["id"]
        self.unsigned = False
        self.mode = "join"
        self.role = offer_role
        self.replaced = replace_name
        self._remember_you(season)
        row["status"] = "accepted"
        row["read"] = True
        for other in self.inbox:
            if other.get("kind") == "contract" and other.get("status") == "open" and other.get("id") != row.get("id"):
                other["status"] = "expired"
        msg = f"加盟 {team.get('name')}，{replace_name} 回到自由市场。"
        self.log.append(msg)
        self.save()
        return msg

    def decline_contract(self, mail_id: str) -> str:
        row = self._mail(mail_id)
        if not row or row.get("kind") != "contract":
            return "这不是入队合同。"
        if row.get("status") != "open":
            return "这封合同已经失效。"
        row["status"] = "declined"
        row["read"] = True
        name = row.get("team") or row.get("team_id")
        self.log.append(f"婉拒 {name} 的合同。")
        self.save()
        return f"已婉拒 {name} 的合同。"

    def _dissolve_club(self, season) -> None:
        team = self.my_team(season.teams)
        if not team:
            return
        you = self.my_player(season.teams)
        leavers = [p for p in team.get("players") or [] if p.get("name") != self.player_name]
        names = [p.get("name") for p in leavers]
        team["players"] = [you] if you else []
        region = team.get("region") or "AS"
        need = ["entry", "rifle", "awp", "igl"]
        if self.role == "awp":
            need[2] = "rifle"
        if self.role == "igl":
            need[3] = "rifle"
        mates = starter_mates(region, need, skip=roster_names(season.teams) | set(self.hidden))
        for name, ability, role in mates:
            st = stats_for(name, role, float(ability))
            team["players"].append(
                {
                    "name": name,
                    "role": role,
                    "ability": float(ability),
                    "command": int(st["command"]),
                    "stats": st,
                    "form": max(52.0, float(ability) - 6),
                    "age": age_of(name, season.year),
                    "you": False,
                }
            )
        refresh_team_command(team)
        team["money"] = 18000
        team["tier"] = "t4"
        self.mode = "create"
        self.crisis = False
        self.deficit = 0
        self.rebuild_free(season.teams)
        taken = {r["name"] for r in self.free}
        for p in leavers:
            name = p.get("name") or ""
            if not name or name in taken:
                continue
            ability = float(p.get("ability") or 70)
            outgoing = {
                "name": name,
                "role": p.get("role") or "rifle",
                "ability": ability,
                "command": int(p.get("command") or 0),
                "stats": p.get("stats") or stats_for(name, p.get("role") or "rifle", ability),
                "form": p.get("form", max(52.0, ability - 8)),
                "age": p.get("age") or age_of(name, season.year),
                "igl_years": int(p.get("igl_years") or 0),
                "region": region,
                "note": "vet",
                "team": None,
                "fee": transfer_fee(ability),
            }
            self.free.append(outgoing)
            taken.add(name)
        left = "、".join(names) if names else "队友"
        msg = f"俱乐部解散。{left} 进了转会市场。你留下重开一间新队，账上 $18,000。"
        self.ops_log.append(msg)
        self.log.append(msg)
        self._push_mail(
            "ops",
            season.date,
            {
                "title": "俱乐部解散，新队成立",
                "from": "俱乐部秘书",
                "body": msg + "\n这和自建队伍一样：从底层重新攒 VRS，先打 CCT。",
            },
            {"status": "open"},
        )

    def found_new_now(self, season) -> str:
        if self.unsigned:
            return "你现在是自由身，不能重开一队。"
        if not self.crisis:
            return "队伍还能运转，不用现在解散。"
        self._dissolve_club(season)
        self.save()
        return self.log[-1]

    def set_skin_pref(self, real: bool, steam_id: str = "") -> str:
        self.real_skins = bool(real)
        if steam_id:
            self.steam_id = "".join(ch for ch in steam_id if ch.isdigit())[:20]
        self.save()
        if not self.real_skins:
            return "只在生涯里显示皮肤，不写进 CS2。"
        if not self.steam_id:
            return "已打开换肤，但还没填 SteamID。填 17 位数字后再装备一次。"
        if not skins.plugin_installed():
            return "已打开换肤。请到训练赛页把换肤插件装进游戏，然后完全退出 CS2 再进。"
        skins.sync_live(self)
        return "已打开游戏内换肤。进本地房后武器会换成你装备的饰品；局内可打 !ws 刷新，对着枪按检视键看外观。"

    def buy_skin(self, skin_id: str) -> str:
        skins.ensure_economy(self)
        row = skins.skin_map().get(skin_id)
        if not row:
            return "市场上没有这件。"
        price = skins.quote_of(self, skin_id)
        if self.money < price:
            return f"口袋 ${self.money:,}，买不起 ${price:,}。"
        self.money -= price
        self.skin_seq += 1
        self.inventory.append(skins.make_item(row, "market", self.skin_seq))
        msg = f"用个人口袋 {price:,} 买下 {row['name']}。"
        self.log.append(msg)
        self.save()
        return msg

    def buy_case(self, case_id: str) -> str:
        skins.ensure_economy(self)
        if self.pending_drop:
            return "先处理上一个箱子的掉落。"
        cost = skins.case_cost(case_id, self)
        box = skins.case_map().get(case_id)
        if not box or cost <= 0:
            return "没有这个箱子。"
        if self.money < cost:
            return f"开箱需要 ${cost:,}（箱子+钥匙）。"
        drop = skins.open_case(case_id)
        self.money -= cost
        spot = skins.quote_of(self, drop["id"])
        self.pending_drop = {
            **drop,
            "wear": skins._wear(),
            "source": "case",
            "case": box["name"],
            "spot": spot,
            "sell": skins.sell_proceeds(spot),
        }
        self.log.append(f"打开 {box['name']}，开出 {drop['name']}。")
        self.save()
        return f"开出 {drop['name']}。留下进库存，或立刻换成钱。"

    def keep_drop(self) -> str:
        drop = self.pending_drop
        if not drop:
            return "没有待处理的掉落。"
        skin = skins.skin_map().get(drop.get("id") or "")
        if not skin:
            self.pending_drop = None
            return "这件皮肤找不到了。"
        self.skin_seq += 1
        item = skins.make_item(skin, "case", self.skin_seq)
        item["wear"] = drop.get("wear") or item["wear"]
        self.inventory.append(item)
        self.pending_drop = None
        msg = f"{item['name']} 进了库存。"
        self.log.append(msg)
        self.save()
        return msg

    def cash_drop(self) -> str:
        drop = self.pending_drop
        if not drop:
            return "没有待处理的掉落。"
        sid = drop.get("id") or drop.get("skin_id") or ""
        pay = skins.sell_proceeds(skins.quote_of(self, sid)) if sid else int(drop.get("sell") or 0)
        self.money += pay
        self.pending_drop = None
        msg = f"把 {drop.get('name')} 换成了 ${pay:,}（市价扣 10%）。"
        self.log.append(msg)
        self.save()
        return msg

    def _unequip_id(self, inv_id: str) -> None:
        self.equipped_ct = {k: v for k, v in (self.equipped_ct or {}).items() if v != inv_id}
        self.equipped_t = {k: v for k, v in (self.equipped_t or {}).items() if v != inv_id}
        self.equipped = {**self.equipped_ct, **self.equipped_t}

    def sell_skin(self, inv_id: str) -> str:
        item = next((row for row in self.inventory if row.get("id") == inv_id), None)
        if not item:
            return "库存里没有这件。"
        self.inventory = [row for row in self.inventory if row.get("id") != inv_id]
        self._unequip_id(inv_id)
        pay = skins.sell_proceeds(skins.quote_of(self, item.get("skin_id") or ""))
        self.money += pay
        msg = f"卖掉 {item['name']}，口袋 +${pay:,}（市价扣 10%）。"
        self.log.append(msg)
        self.save()
        skins.sync_live(self)
        return msg

    def equip_skin(self, inv_id: str, side: str = "", off: bool = False) -> str:
        skins.migrate_equipped(self)
        side = (side or "").lower()
        if side not in ("ct", "t"):
            return "请选择装到 CT 还是 T。"
        loadout = self.equipped_ct if side == "ct" else self.equipped_t
        if off:
            item = next((row for row in self.inventory if row.get("id") == inv_id), None)
            slot = (item or {}).get("slot") or ""
            if slot and loadout.get(slot) == inv_id:
                loadout.pop(slot, None)
            else:
                for key, val in list(loadout.items()):
                    if val == inv_id:
                        loadout.pop(key, None)
            self.equipped = {**self.equipped_ct, **self.equipped_t}
            self.save()
            skins.sync_live(self)
            return f"已从 {side.upper()} 卸下。"
        item = next((row for row in self.inventory if row.get("id") == inv_id), None)
        if not item:
            return "库存里没有这件。"
        slot = item.get("slot") or ""
        if side not in skins.sides_for(slot):
            return f"{item['name']} 不能装到 {side.upper()}。"
        loadout[slot] = item["id"]
        self.equipped = {**self.equipped_ct, **self.equipped_t}
        self.save()
        skins.sync_live(self)
        if self.real_skins and skins.plugin_installed() and self.steam_id:
            return f"已给 {side.upper()} 装备 {item['name']}，并写入换肤文件。"
        if self.real_skins:
            return f"已给 {side.upper()} 装备 {item['name']}。游戏内换肤还差插件或 SteamID。"
        return f"已给 {side.upper()} 装备 {item['name']}。"

    def spend_point(self, season, axis: str) -> str:
        if self.over():
            return "这段生涯已经结束。"
        if self.attr_points < 1:
            return "没有可用属性点。"
        if axis not in ALL_AXES:
            return "没有这个维度。"
        you = self.my_player(season.teams)
        team = self.my_team(season.teams)
        if not you or not team:
            return "找不到你的选手数据。"
        stats = you.get("stats") or stats_for(you["name"], you.get("role") or self.role, float(you.get("ability") or 74))
        you["stats"] = stats
        label = AXIS_LABEL[axis]
        if axis == "command":
            cur = int(round(float(stats.get("command") or you.get("command") or 50)))
            if cur >= 100:
                return f"{label} 已满，不能再点。"
            nxt = min(100, cur + 1)
            stats["command"] = nxt
            you["command"] = nxt
            note = f"{label} {cur} → {nxt}"
        elif axis == "utility":
            cur = int(round(float(stats.get(axis) or 70)))
            if cur >= 100:
                return f"{label} 已满，不能再点。"
            nxt = min(100, cur + 1)
            stats[axis] = nxt
            refresh_team_command(team)
            note = f"{label} {cur} → {nxt}，队指挥 {team.get('command')}"
        else:
            cur = int(round(float(stats.get(axis) or 70)))
            if cur >= 100:
                return f"{label} 已满，不能再点。"
            nxt = min(100, cur + 1)
            stats[axis] = nxt
            you["ability"] = ability_of(stats, you.get("role") or self.role)
            note = f"{label} {cur} → {nxt}，个人能力 {you['ability']:.1f}"
        self.attr_points -= 1
        msg = f"投入 1 点到{label}。{note}。剩余 {self.attr_points} 点。"
        self.log.append(msg)
        self.save()
        return msg

    def answer_birthday(self, season, name: str, choice: str) -> str:
        team = self.my_team(season.teams) if season is not None else None
        if choice == "train":
            self.attr_points += 1
            if team is not None:
                shift_mentality(team, -1)
            msg = f"{name} 生日你去训练了。属性点 +1，队心态 -1。"
        else:
            if team is not None:
                shift_mentality(team, 2)
            msg = f"你祝贺了 {name} 的生日。队心态 +2。"
        self.log.append(msg)
        self.save()
        return msg

    def retire(self, season) -> str:
        if not self.exists:
            return "还没有生涯。"
        if self.over():
            return "这段生涯已经结束。"
        honours = awards.honours_for(season.records(), season.top20, self.player_name)
        ending = plot.honour_ending(honours)
        self.retired = True
        self._apply_ending(ending["id"])
        self._push_plot(
            {
                "when": "retire",
                "kind": "plot",
                "title": ending["title"],
                "text": ending["text"],
                "ending": ending["id"],
            },
            f"retire.{self.mail_seq + 1}",
        )
        self.log.append(f"你选择退役。{ending['title']}。")
        self.save()
        return ending["title"]

    def set_roles(self, season, mapping: dict, clicked: str = "") -> str:
        team = self.my_team(season.teams)
        if not team:
            return "还没有队伍。"
        names = [p["name"] for p in team["players"]]
        if set(mapping) != set(names):
            return "名单对不上，请刷新后再试。"
        roles = [mapping[n] for n in names]
        if any(r not in PLAYABLE_ROLES for r in roles):
            return "有不能用的位置。"
        if clicked and clicked in mapping:
            want = mapping[clicked]
            if want in ("awp", "igl"):
                old = next((p.get("role") or "rifle" for p in team["players"] if p["name"] == clicked), "rifle")
                for n in names:
                    if n != clicked and mapping.get(n) == want:
                        mapping[n] = old if old != want else "rifle"
                roles = [mapping[n] for n in names]
        if roles.count("igl") != 1:
            raise ValueError("必须有且只有一名指挥。点指挥会和原来的指挥对调。")
        if roles.count("awp") != 1:
            raise ValueError("必须有且只有一名主狙。点主狙会和原来的主狙对调。")
        for p in team["players"]:
            p["role"] = mapping[p["name"]]
            if p.get("you"):
                self.role = p["role"]
            st = p.get("stats")
            if st:
                p["ability"] = ability_of(st, p["role"])
        restamp_command(team)
        refresh_team_command(team)
        team["custom_roles"] = True
        self.log.append("调整了首发位置。")
        self.save()
        return "位置已更新。个人能力按新位置重算，队指挥仍按道具。"

    def inspect_player(self, season, name: str) -> dict | None:
        found = None
        team = None
        for t in season.teams:
            for p in t.get("players") or []:
                if p.get("name") == name:
                    found, team = p, t
                    break
            if found:
                break
        if not found:
            found = next((x for x in self.free if x.get("name") == name), None)
        if not found:
            return None
        stats = found.get("stats") or stats_for(name, found.get("role") or "rifle", float(found.get("ability") or 70))
        honours = awards.honours_for(season.records(), season.top20, name)
        return {
            "kind": "player",
            "name": name,
            "role": found.get("role"),
            "ability": found.get("ability"),
            "command": found.get("command") or stats.get("command"),
            "age": found.get("age"),
            "birthday": birth_label(name),
            "form": found.get("form"),
            "you": bool(found.get("you")),
            "team": team["name"] if team else None,
            "team_id": team["id"] if team else None,
            "stats": {k: stats.get(k) for k in ALL_AXES},
            "honours": honours,
        }

    def inspect_team(self, season, name: str) -> dict | None:
        team = next((t for t in season.teams if t["name"] == name or t["id"] == name), None)
        if not team:
            return None
        table = {r["name"]: r for r in season.vrs.table(season.teams, season.date)}
        row = table.get(team["name"]) or {}
        return {
            "kind": "team",
            "id": team["id"],
            "name": team["name"],
            "region": team["region"],
            "command": team.get("command"),
            "mentality": team.get("mentality"),
            "money": team.get("money", 0),
            "rank": row.get("rank"),
            "vrs": row.get("vrs"),
            "strong_maps": team.get("strong_maps") or [],
            "weak_maps": team.get("weak_maps") or [],
            "crest": crest(team),
            "players": team["players"],
            "honours": awards.team_honours(season.records(), team["name"]),
        }

    # ---------------------------------------------------------------- stories

    def _context(self, season, ev: dict | None = None) -> dict:
        team = self.my_team(season.teams)
        return {
            "era": self.era,
            "year": getattr(season, "year", self.year),
            "player": self.player_name,
            "team": team["name"] if team else "",
            "role": self.role,
            "mode": self.mode,
            "class": awards.event_class(ev) if ev else "",
            "class_label": awards.CLASS_LABEL.get(awards.event_class(ev), "") if ev else "",
            "type": ev.get("type") if ev else "",
            "event": (ev.get("name") if ev else "") or "",
            "short": (ev.get("short") if ev else "") or (ev.get("name") if ev else "") or "",
            "event_id": (ev.get("id") if ev else "") or "",
            "champion": (ev.get("champion") if ev else "") or "",
        }

    def _enqueue(self, when: str, season, ev: dict | None = None) -> None:
        ctx = self._context(season, ev)
        ctx["when"] = when
        seen = set(self.seen_stories)
        queued = {row["id"] for row in self.story_queue}
        for beat in story.collect(ctx, seen, queued):
            self.story_queue.append(beat)

    def watch(self, season, ev: dict | None = None, when: str | None = None) -> None:
        """Scan the season for story beats that should fire now."""
        if not self.exists:
            return
        if when:
            self._enqueue(when, season, ev)
            return

        team = self.my_team(season.teams)
        if not team:
            return
        name = team["name"]
        events = [ev] if ev else season.events
        for event in events:
            if event.get("status") not in ("live", "done"):
                continue
            involved = name in (event.get("field") or []) or any(
                name in (m.get("team_a"), m.get("team_b")) for m in event.get("matches") or []
            )
            if not involved:
                continue
            self._enqueue("first_lan", season, event)
            if event.get("type") == "major" or awards.event_class(event) == "major":
                self._enqueue("first_major", season, event)
            if any(
                m.get("stage") == "GF" and name in (m.get("team_a"), m.get("team_b"))
                for m in event.get("matches") or []
            ):
                self._enqueue("first_final", season, event)
            if event.get("champion") == name:
                self._enqueue("first_title", season, event)
                self._enqueue_title(season, event)
            award = event.get("awards") or {}
            if (award.get("mvp") or {}).get("player") == self.player_name:
                self._enqueue("first_mvp", season, event)
            if any(r.get("player") == self.player_name for r in award.get("evp") or []):
                self._enqueue("first_evp", season, event)

    def _queued(self, story_id: str) -> bool:
        return story_id in self.seen_stories or any(row.get("id") == story_id for row in self.story_queue)

    def _enqueue_title(self, season, ev: dict) -> None:
        """Every title gets a celebration beat, then the awards reveal."""
        if ev.get("type") == "qual":
            return
        ctx = self._context(season, ev)
        sid = f"title.{ev['id']}"
        if not self._queued(sid):
            beat = story.pick(ctx, "title") or {
                "id": sid,
                "when": "title",
                "title": "冠军",
                "text": f"{ctx['team']} 拿下了 {ctx['event']}。",
            }
            beat["id"] = sid
            if (
                self.era == "2026"
                and self.player_name == "NiKo"
                and awards.event_class(ev) == "major"
            ):
                beat["title"] = verse.NIKO_MAJOR
            self.story_queue.append(beat)
        aid = f"awards.{ev['id']}"
        if not self._queued(aid):
            self.story_queue.append(self._awards_reveal(season, ev))

    def _awards_reveal(self, season, ev: dict) -> dict:
        award = ev.get("awards") or {}
        roles: dict[str, str] = {}
        for team in season.teams:
            for player in team.get("players") or []:
                roles[player["name"]] = player.get("role") or ""

        def slim(row: dict | None) -> dict | None:
            if not row:
                return None
            return {
                "player": row.get("player") or "",
                "team": row.get("team") or "",
                "rating": row.get("rating"),
                "title": row.get("title") or "",
                "role": roles.get(row.get("player") or "", ""),
                "from_finalist": bool(row.get("from_finalist")),
            }

        return {
            "id": f"awards.{ev['id']}",
            "kind": "awards",
            "when": "awards",
            "title": ev.get("short") or ev.get("name") or "",
            "event": ev.get("name") or "",
            "short": ev.get("short") or ev.get("name") or "",
            "class": awards.event_class(ev),
            "champion": ev.get("champion") or "",
            "mvp": slim(award.get("mvp")),
            "evp": [slim(row) for row in award.get("evp") or [] if slim(row)],
            "five": [slim(row) for row in award.get("five") or [] if slim(row)],
        }

    def on_top20_eve(self, season) -> None:
        sid = f"top20.eve.{season.year}"
        if self._queued(sid):
            return
        table = season.top20_live()
        you = next((row for row in table if row["player"] == self.player_name), None)
        maps = (self.season_line(season) or {}).get("maps") or 0
        if you and you["rank"] <= 16:
            band = "lock"
        elif you and you["rank"] <= 24:
            band = "edge"
        elif maps >= 16 and not you:
            band = "edge"
        else:
            band = "miss"
        ctx = self._context(season)
        ctx["band"] = band
        beat = story.pick(ctx, "top20_eve")
        if not beat:
            return
        beat["id"] = sid
        self.story_queue.append(beat)
        self.save()

    def on_year_end(self, season, year: int, table: list[dict]) -> None:
        self.on_top20_eve(season)
        rid = f"top20.{year}"
        if self._queued(rid):
            return
        self.story_queue.append(
            {
                "id": rid,
                "kind": "top20",
                "when": "top20",
                "year": year,
                "you": self.player_name,
                "rows": [verse.decorate(row, year, self.era) for row in table],
            }
        )
        self.save()

    def ack_story(self, story_id: str, choice: str = "", season=None) -> None:
        row = next((item for item in self.story_queue if item.get("id") == story_id), None)
        if row and row.get("when") == "fix_offer" and self.fix_pending:
            self.answer_fix(season, choice == "accept")
        if row and row.get("when") == "loan_default" and self.loan_default_pending:
            self.answer_loan_default(season, choice)
        if row and row.get("when") == "teammate_birthday":
            self.answer_birthday(season, row.get("player") or "", choice)
        self.story_queue = [item for item in self.story_queue if item.get("id") != story_id]
        if story_id and story_id not in self.seen_stories:
            self.seen_stories.append(story_id)
        self.save()

    def _push_plot(self, beat: dict, sid: str) -> None:
        beat = dict(beat)
        beat["id"] = sid
        if any(item.get("id") == sid for item in self.story_queue):
            return
        self.story_queue.append(beat)

    def maybe_major_coach(self, season, ev: dict) -> None:
        if self.banned or not ev or ev.get("type") != "major":
            return
        eid = ev.get("id") or ""
        if not eid or eid in self.coach_majors:
            return
        team = self.my_team(season.teams)
        if not team or team["name"] not in (ev.get("field") or []):
            return
        self.coach_majors.append(eid)
        if random.random() >= plot.COACH_P:
            return
        shift_mentality(team, -5)
        team.setdefault("mentality_log", []).append(
            {"event": eid, "when": "coach_absent", "delta": -5, "after": team.get("mentality")}
        )
        self._push_plot(plot.coach_popup(ev.get("name") or "Major"), f"coach.{eid}")
        self.log.append(f"教练缺席 {ev.get('name')}，全队心态 -5。")

    def gate_match(self, season, match_id: str = "") -> str:
        """Block a live series, or interrupt it with a quiet offer."""
        self._sync_throw(season)
        if self.over():
            return "这段生涯已经结束，只能重开。"
        if self.unsigned:
            return "你现在是自由身，先在邮箱接下合同。"
        if self.fix_pending:
            return "先回那封没有署名的信。"
        if self.throwing:
            return ""
        key = str(match_id or "")
        if key and key == self.fix_rolled:
            return ""
        if random.random() >= max(plot.FIX_MIN, min(plot.FIX_MAX, float(self.fix_chance or plot.FIX_BASE))):
            self.fix_rolled = key
            return ""
        self.fix_rolled = key
        self.fix_pending = True
        letter = self._push_mail(
            "whisper",
            season.date,
            plot.whisper_letter(self.player_name),
            {"status": "open"},
        )
        beat = plot.whisper_popup()
        beat["mail_id"] = letter["id"]
        self._push_plot(beat, f"fix.offer.{self.mail_seq}")
        return "邮箱里来了一封不署名的信。"

    def answer_fix(self, season, accept: bool, mail_id: str = "") -> str:
        if self.banned:
            return "你已被禁赛，这份档案只能重开。"
        row = self._mail(mail_id) if mail_id else next(
            (item for item in self.inbox if item.get("kind") == "whisper" and item.get("status") == "open"),
            None,
        )
        if not self.fix_pending and not (row and row.get("status") == "open"):
            return "这封信已经处理过了。"
        if row:
            row["status"] = "accepted" if accept else "declined"
            row["read"] = True
        self.fix_pending = False
        self.story_queue = [item for item in self.story_queue if item.get("when") != "fix_offer"]
        if accept:
            self.fix_chance = min(plot.FIX_MAX, float(self.fix_chance or plot.FIX_BASE) + plot.FIX_ACCEPT)
            self.throwing = True
            self.money += plot.PAYOUT
            if season is not None:
                self._sync_throw(season)
            self.log.append("你回了一封含糊的信。账上多了一笔说不清的钱。")
            self.save()
            return "你回了一句含糊的话。账上多了一笔说不清来路的钱。"
        self.fix_chance = max(plot.FIX_MIN, float(self.fix_chance or plot.FIX_BASE) * plot.FIX_REFUSE)
        self.throwing = False
        if season is not None:
            self._sync_throw(season)
        self.log.append("你把那封信关了。")
        self.save()
        return "你把那封信关了。对方不会再急着找你——至少一段时间里。"

    def _sync_throw(self, season) -> None:
        team = self.my_team(season.teams) if season is not None else None
        if team is not None:
            team["throwing"] = bool(self.throwing and not self.banned)

    def on_series_done(self, season) -> None:
        if not self.throwing or self.banned:
            self.throwing = False
            self._sync_throw(season)
            self.save()
            return
        self.throwing = False
        self._sync_throw(season)
        if random.random() >= plot.CATCH_P:
            self.log.append("那场对局没有再被人提起。")
            self.save()
            return
        you = self.my_player(season.teams) if season is not None else None
        ability = float((you or {}).get("ability") or 74)
        self.banned = True
        self.fix_pending = False
        ending = self._apply_ending("fix")
        self._push_plot(plot.probe_popup(), f"fix.probe.{self.mail_seq + 1}")
        self._push_plot(plot.ban_popup(self.player_name, ability), f"fix.ban.{self.mail_seq + 2}")
        self._push_mail("discipline", season.date, plot.ban_letter(self.player_name), {"status": "closed"})
        self.log.append(f"赛事方发了通报。{ending['title']}。")
        self.save()

    def apply_throw_flag(self, season) -> None:
        self._sync_throw(season)

    # ---------------------------------------------------------------- payload

    def season_line(self, season) -> dict | None:
        for row in season.ratings_vs_field():
            if row["player"] == self.player_name:
                return row
        return None

    def _ops_public(self, season, team: dict | None, table: dict) -> dict:
        rank = (table.get(self.team_id) or {}).get("rank", 40) if self.team_id else 40
        burn = economy.month_burn((team or {}).get("players") or [], rank)
        you_pay = next((w["pay"] for w in burn["wages"] if w["name"] == self.player_name), 0)
        return {
            "rank": rank,
            "salaries": burn["salaries"],
            "living": burn["living"],
            "total": burn["total"],
            "wages": burn["wages"],
            "your_salary": you_pay,
            "cash": (team or {}).get("money", 0) if team else 0,
            "runway": int(((team or {}).get("money", 0) or 0) / burn["total"]) if burn["total"] else 0,
            "log": self.ops_log[-8:],
        }

    def public(self, season) -> dict:
        team = self.my_team(season.teams) if self.exists else None
        you = self.my_player(season.teams) if self.exists else None
        if not you and self.you_card:
            you = dict(self.you_card)
            you["you"] = True
        table = {r["id"]: r for r in season.vrs.table(season.teams, season.date)} if self.exists else {}

        market = []
        if self.exists and team:
            mine = table.get(team["id"], {"vrs": 900, "rank": 40})
            for row in sorted(self.free, key=lambda x: -x["ability"]):
                fee = transfer_fee(row["ability"])
                market.append(
                    {
                        **row,
                        "fee": fee,
                        "chance": round(
                            buy_chance(mine["vrs"], row["ability"], team.get("money", 0), fee), 3
                        ),
                    }
                )

        if you and not you.get("stats"):
            you["stats"] = stats_for(
                you["name"], you.get("role") or self.role, float(you.get("ability") or 74)
            )
        if you:
            you["birthday"] = birth_label(you.get("name") or self.player_name)
        honours = (
            awards.honours_for(season.records(), season.top20, self.player_name)
            if self.exists
            else {"titles": [], "mvp": [], "evp": [], "top20": [], "counts": {}}
        )
        return {
            "exists": self.exists,
            "era": self.era,
            "year": self.year,
            "eras": ERA_META,
            "roles": list(PLAYABLE_ROLES),
            "player_name": self.player_name,
            "role": self.role,
            "mode": self.mode,
            "team_id": self.team_id,
            "team_name": team["name"] if team else "",
            "money": team.get("money", 0) if team else 0,
            "pocket": self.money,
            "crisis": self.crisis,
            "deficit": self.deficit,
            "ops": self._ops_public(season, team, table),
            "skins": skins.shop_public(self),
            "real_skins": self.real_skins,
            "steam_id": self.steam_id,
            "you": you,
            "roster": team["players"] if team else [],
            "last_scrim": self.last_scrim,
            "registered": self.registered,
            "market": market[:60],
            "honours": honours,
            "team_honours": awards.team_honours(season.records(), team["name"]) if team else [],
            "season_line": self.season_line(season) if self.exists else None,
            "vrs": table.get(self.team_id) if self.team_id else None,
            "log": self.log[-12:],
            "stories": list(self.story_queue),
            "inbox": list(self.inbox),
            "unread": self.unread_count(),
            "attr_points": self.attr_points,
            "axes": list(ALL_AXES),
            "axis_labels": AXIS_LABEL,
            "banned": self.banned,
            "retired": self.retired,
            "over": self.over(),
            "ending": (
                {
                    "id": self.ending,
                    "title": self.ending_title,
                    "text": self.ending_text,
                }
                if self.over() and self.ending_text
                else None
            ),
            "fix_pending": self.fix_pending,
            "unsigned": self.unsigned,
            "loan": self._loan_public(season, team, table) if self.exists else None,
            "loan_default_pending": self.loan_default_pending,
        }
