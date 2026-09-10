# coding=utf-8
"""UI-neutral application state and commands.

Tk desktop, the optional HTTP compatibility UI, and tests all use this holder.
No interface is allowed to keep a second copy of career rules.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from uuid import uuid4

from .career import Career
from .league import Season
from .world import apply_roles


class ApplicationState:
    def __init__(self) -> None:
        self.season = Season.load_or_new()
        self.career = Career.load()
        self.season.career = self.career
        from .world.ability import ensure_role_calibration, refresh_player_ability
        role_upgrade = bool(getattr(self.season, "_role_calibration_changed", False))
        for player in [*self.career.free, self.career.you_card or {}]:
            role_upgrade = ensure_role_calibration(player) or role_upgrade
            refresh_player_ability(player)
        if role_upgrade:
            self.backup()  # Back up the original pair before optional v2 fields are saved.
        dirty = bool(getattr(self.season, "_calendar_changed", False))
        dirty = dirty or role_upgrade
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
        if self.career.current_date != self.season.date:
            self.career.current_date = self.season.date
            dirty = True
        if not self.career.cashflow:
            team = self.career.my_team(self.season.teams)
            if team is not None:
                self.career._record_cashflow(
                    self.season.date, "club", "opening", "升级时俱乐部期初余额",
                    int(team.get("money") or 0), int(team.get("money") or 0),
                )
            self.career._record_cashflow(
                self.season.date, "pocket", "opening", "升级时个人期初余额",
                int(self.career.money), int(self.career.money),
            )
            dirty = True
        before_stories = len(self.career.story_queue)
        if self.career.settle_legacy_money_mail(self.season):
            dirty = True
        self.career._ensure_loan_popup()
        if len(self.career.story_queue) != before_stories:
            dirty = True
        before = len(self.career.inbox)
        if self.career.unsigned and not self.career.over():
            self.career._dispatch_contracts(self.season)
        elif not self.career.unsigned and not self.career.over():
            self.career.dispatch_invites(self.season)
        return dirty or len(self.career.inbox) != before

    def sync(self) -> None:
        apply_roles(self.season.teams, self.season.era, current_year=self.season.year)
        you = self.career.my_player(self.season.teams) if self.career.exists else None
        if you:
            self.career.role = you["role"]
        self.season.career = self.career
        if self.career.exists:
            self.career.apply_throw_flag(self.season)

    def payload(self, msg: str = "") -> dict:
        self.sync()
        ingested = ""
        try:
            ingested = self.season.try_ingest_pending_cs2()
        except Exception:
            pass
        if ingested:
            self.persist()
            msg = msg or ingested
        return {
            "ok": True,
            "msg": msg,
            "state": self.season.public(),
            "stories": list(self.career.story_queue or []),
        }

    def persist(self) -> None:
        self.season.save()
        self.career.save()

    def reset(self) -> None:
        self._replace_career(Season(), Career())

    def backup(self):
        """Preserve the current pair before replacement; never touch config/packs."""
        from .paths import save_root
        root = save_root()
        files = [root / name for name in ('season.json', 'career.json') if (root / name).is_file()]
        if not files:
            return None
        folder = root / 'backups' / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid4().hex[:8])
        folder.mkdir(parents=True)
        for path in files:
            shutil.copy2(path, folder / path.name)
        return folder

    def _replace_career(self, season, career):
        folder = self.backup()  # A failed backup must prevent replacement.
        old_season, old_career = self.season, self.career
        self.season, self.career = season, career
        self.season.career = career
        try:
            self.persist()
        except Exception:
            self.season, self.career = old_season, old_career
            if folder:
                for source in folder.iterdir():
                    target = folder.parent.parent / source.name
                    pending = target.with_suffix('.restore-tmp')
                    shutil.copy2(source, pending)
                    pending.replace(target)
            raise

    def create_career(self, payload: dict) -> str:
        from .world import ERA_META, slug, roster_names
        from .career.origins import ORIGINS, DEFAULT_ORIGIN

        payload = dict(payload)
        era = str(payload.get('era') or '2026')
        mode = payload.get('mode') or 'join'
        if era not in ERA_META or mode not in ('join', 'create'):
            raise ValueError('请选择有效的年代和生涯方式。')
        season = Season(int(ERA_META[era]['year']), era)
        if mode == 'create':
            name, org = str(payload.get('name') or '').strip(), str(payload.get('org') or '').strip()
            if not name or not org or len(name) > 32 or len(org) > 40:
                raise ValueError('请填写选手 ID（最多32字）和俱乐部名称（最多40字）。')
            if payload.get('origin', DEFAULT_ORIGIN) not in ORIGINS:
                raise ValueError('请选择路人、青训或天才开局。')
            if name.casefold() in {n.casefold() for n in roster_names(season.teams)} or not slug(org) or slug(org) in {t['id'] for t in season.teams}:
                raise ValueError('选手或俱乐部已存在，请换一个名称。')
            payload.update(name=name, org=org)
        elif not any(t['id'] == payload.get('team_id') for t in season.teams):
            raise ValueError('所选战队不属于这个年代，请重新选择。')
        career = Career()
        season.career = career
        # Build and validate off to the side. Career.create normally saves, so
        # defer this one instance's write until the old save has been backed up.
        career.save = lambda: None
        try:
            msg = career.create(payload, season)
        finally:
            del career.save
        self._replace_career(season, career)
        return msg

    def run(self, operation, *args, **kwargs) -> str:
        """Execute a domain command and save; used by desktop button handlers."""
        msg = operation(*args, **kwargs)
        self.persist()
        return str(msg or "")
