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
from ..world.ability import ALL_AXES, AXIS_LABEL, AXES, ability_of, refresh_team_command, stats_for
from ..world import (
    ERA_META,
    PLAYABLE_ROLES,
    age_of,
    agent_rows,
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
    return {
        "name": cand["name"],
        "role": cand["role"],
        "ability": float(cand["ability"]),
        "command": int(cand.get("command") or stats.get("command") or 0),
        "stats": stats,
        "form": cand.get("form", float(cand["ability"]) - 8),
        "age": cand.get("age", 22),
        "igl_years": int(cand.get("igl_years") or 0),
    }


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
        obj.real_skins = bool(getattr(obj, "real_skins", False))
        obj.steam_id = str(getattr(obj, "steam_id", "") or "")
        obj.skin_seq = int(getattr(obj, "skin_seq", 0) or 0)
        obj.pending_drop = getattr(obj, "pending_drop", None)
        obj.ops_log = list(getattr(obj, "ops_log", None) or [])
        obj.fix_chance = float(getattr(obj, "fix_chance", plot.FIX_BASE) or plot.FIX_BASE)
        obj.fix_pending = bool(getattr(obj, "fix_pending", False))
        obj.throwing = bool(getattr(obj, "throwing", False))
        obj.banned = bool(getattr(obj, "banned", False))
        obj.fix_rolled = str(getattr(obj, "fix_rolled", "") or "")
        obj.coach_majors = list(getattr(obj, "coach_majors", None) or [])
        if skins.repair_items(obj.inventory):
            obj.save()
        return obj

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
        self.real_skins = False
        self.steam_id = ""
        self.skin_seq = 0
        self.pending_drop = None
        self.ops_log = []
        self.fix_chance = plot.FIX_BASE
        self.fix_pending = False
        self.throwing = False
        self.banned = False
        self.fix_rolled = ""
        self.coach_majors = []
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
            slot = next((p for p in team["players"] if p["name"] == payload.get("replace")), None)
            if slot is None:
                slot = next((p for p in team["players"] if p["role"] == self.role), team["players"][0])
            self.player_name = slot["name"]
            self.team_id = team["id"]
            self.replaced = slot["name"]
            self.hidden.append(slot["name"])
            slot["role"] = self.role
            slot["you"] = True
            self.log.append(f"加入 {team['name']}，接管 {slot['name']}（{int(slot['ability'])}）。")

        self.rebuild_free(season.teams)
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
        roles = ["entry", "support", "awp", "igl"]
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

    # ---------------------------------------------------------------- ticking

    def tick(self, season, _prev_date: str) -> None:
        if not self.exists:
            return
        month = season.date[:7]
        if month != self.last_sponsor_month:
            rank_map = {r["id"]: r["rank"] for r in season.vrs.table(season.teams, season.date)}
            for t in season.teams:
                pay = sponsor_month(rank_map.get(t["id"], 40))
                if t["id"] == self.team_id:
                    self._push_mail(
                        "sponsor",
                        season.date,
                        mail.sponsor_letter(month, rank_map.get(t["id"], 40), pay),
                        {"amount": pay, "rank": rank_map.get(t["id"], 40), "month": month},
                    )
                else:
                    t["money"] = t.get("money", 0) + pay
            self.last_sponsor_month = month
        if month != self.last_ops_month:
            if self.last_ops_month:
                self._settle_month(season, month)
            self.last_ops_month = month
        year = int(season.date[:4])
        if year > self.last_age_year:
            leftover = self.attr_points
            self.attr_points = 0
            if leftover:
                self.log.append(f"{year} 年未使用的 {leftover} 点属性已清零。")
            self._age_year(season, year)
            self.last_age_year = year
        self.dispatch_invites(season)
        self.save()

    def _age_year(self, season, year: int) -> None:
        # Roster aging (gun + IGL command) already ran in Season.roll_year.
        self.year = year
        from ..world.aging import apply_player_year

        for row in self.free:
            apply_player_year(row)
            row["fee"] = transfer_fee(row["ability"])
        self.log.append(f"{year} 转会期：年龄曲线生效。")
        self._ai_window(season)

    def _ai_window(self, season) -> None:
        table = {r["id"]: r for r in season.vrs.table(season.teams, season.date)}
        for t in season.teams:
            if t["id"] == self.team_id:
                continue
            if t.get("mentality", 70) > 66 and t.get("loss_streak", 0) < 3:
                continue
            weak = min(t["players"], key=lambda p: p["ability"])
            if weak["ability"] >= 82:
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
        if self.banned:
            return "你已被禁赛，这份档案只能重开。"
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
        if self.banned:
            return "你已被禁赛，这份档案只能重开。"
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
        self.attr_points += 1
        note = "属性点 +1"
        if spot in ("champion", "final"):
            self.attr_points += 1
            note = "属性点 +2（参赛 + 决赛）"
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

    def _dissolve_club(self, season) -> None:
        team = self.my_team(season.teams)
        if not team:
            return
        you = self.my_player(season.teams)
        leavers = [p for p in team.get("players") or [] if p.get("name") != self.player_name]
        names = [p.get("name") for p in leavers]
        team["players"] = [you] if you else []
        region = team.get("region") or "AS"
        need = ["entry", "support", "awp", "igl"]
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
        skins.sync_live(self)
        return "已记下。游戏内个人换肤还在修，先只在这页显示。" if self.real_skins else "只在生涯里显示皮肤，不写进 CS2。"

    def buy_skin(self, skin_id: str) -> str:
        row = skins.skin_map().get(skin_id)
        if not row:
            return "市场上没有这件。"
        price = int(row.get("buy") or 0)
        if self.money < price:
            return f"口袋 ${self.money:,}，买不起 ${price:,}。"
        self.money -= price
        self.skin_seq += 1
        self.inventory.append(skins.make_item(row, "market", self.skin_seq))
        msg = f"用个人口袋买下 {row['name']}。"
        self.log.append(msg)
        self.save()
        return msg

    def buy_case(self, case_id: str) -> str:
        if self.pending_drop:
            return "先处理上一个箱子的掉落。"
        cost = skins.case_cost(case_id)
        box = skins.case_map().get(case_id)
        if not box or cost <= 0:
            return "没有这个箱子。"
        if self.money < cost:
            return f"开箱需要 ${cost:,}（箱子+钥匙）。"
        drop = skins.open_case(case_id)
        self.money -= cost
        self.pending_drop = {
            **drop,
            "wear": skins._wear(),
            "source": "case",
            "case": box["name"],
            "sell": int(drop.get("sell") or 0),
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
        skin = skins.skin_map().get(drop.get("id") or "")
        pay = int((skin or {}).get("sell") or 0)
        self.money += pay
        self.pending_drop = None
        msg = f"把 {drop.get('name')} 换成了 ${pay:,}。"
        self.log.append(msg)
        self.save()
        return msg

    def sell_skin(self, inv_id: str) -> str:
        item = next((row for row in self.inventory if row.get("id") == inv_id), None)
        if not item:
            return "库存里没有这件。"
        self.inventory = [row for row in self.inventory if row.get("id") != inv_id]
        self.equipped = {k: v for k, v in self.equipped.items() if v != inv_id}
        pay = int(item.get("sell") or 0)
        self.money += pay
        msg = f"卖掉 {item['name']}，口袋 +${pay:,}。"
        self.log.append(msg)
        self.save()
        return msg

    def equip_skin(self, inv_id: str) -> str:
        item = next((row for row in self.inventory if row.get("id") == inv_id), None)
        if not item:
            return "库存里没有这件。"
        self.equipped[item["slot"]] = item["id"]
        self.save()
        skins.sync_live(self)
        return f"装备 {item['name']}。已写入换肤文件，进本地房后生效；局内可打 !ws。"

    def spend_point(self, season, axis: str) -> str:
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
        if axis == "command":
            nxt = min(99, int(round(float(stats.get("command") or you.get("command") or 50))) + 1)
            stats["command"] = nxt
            you["command"] = nxt
            refresh_team_command(team)
            label = AXIS_LABEL[axis]
            note = f"{label} {nxt - 1} → {nxt}"
        else:
            nxt = min(99, int(round(float(stats.get(axis) or 70))) + 1)
            stats[axis] = nxt
            you["ability"] = ability_of(stats, you.get("role") or self.role)
            label = AXIS_LABEL[axis]
            note = f"{label} {nxt - 1} → {nxt}，个人能力 {you['ability']:.1f}"
        self.attr_points -= 1
        msg = f"投入 1 点到{label}。{note}。剩余 {self.attr_points} 点。"
        self.log.append(msg)
        self.save()
        return msg

    def set_roles(self, season, mapping: dict) -> str:
        team = self.my_team(season.teams)
        if not team:
            return "还没有队伍。"
        names = [p["name"] for p in team["players"]]
        if set(mapping) != set(names):
            return "名单对不上，请刷新后再试。"
        roles = [mapping[n] for n in names]
        if any(r not in PLAYABLE_ROLES for r in roles):
            return "有不能用的位置。"
        if roles.count("igl") != 1:
            return "必须有且只有一名指挥。"
        if roles.count("awp") != 1:
            return "必须有且只有一名主狙。"
        for p in team["players"]:
            p["role"] = mapping[p["name"]]
            if p.get("you"):
                self.role = p["role"]
            st = p.get("stats")
            if st:
                p["ability"] = ability_of(st, p["role"])
                if "command" in st:
                    p["command"] = st["command"]
        team["custom_roles"] = True
        refresh_team_command(team)
        self.log.append("调整了首发位置。")
        self.save()
        return "位置已更新。指挥能力按新 IGL 结算。"

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

    def ack_story(self, story_id: str, choice: str = "") -> None:
        row = next((item for item in self.story_queue if item.get("id") == story_id), None)
        if row and row.get("when") == "fix_offer" and self.fix_pending:
            self.answer_fix(None, choice == "accept")
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
        if self.banned:
            return "你已被禁赛，这份档案只能重开。"
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
        self._push_plot(plot.probe_popup(), f"fix.probe.{self.mail_seq + 1}")
        self._push_plot(plot.ban_popup(self.player_name, ability), f"fix.ban.{self.mail_seq + 2}")
        self._push_mail("discipline", season.date, plot.ban_letter(self.player_name), {"status": "closed"})
        self.log.append("赛事方发了通报。你被暂时禁赛。")
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
            "skins": skins.shop_public(self.inventory, self.equipped, self.pending_drop),
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
            "fix_pending": self.fix_pending,
        }
