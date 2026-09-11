# coding=utf-8
"""UI-neutral application state and commands.

Tk desktop, the optional HTTP compatibility UI, and tests all use this holder.
No interface is allowed to keep a second copy of career rules.
"""

from __future__ import annotations

import json
from copy import deepcopy

from .career import Career
from .league import Season
from .world import apply_roles


class ApplicationState:
    def __init__(self) -> None:
        self._recover_personal_command()
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
        from .career import arcs
        if not arcs.state(self.career) and not self.career.over():
            self.backup()
            arcs.initialize(self.career, self.season)
            dirty = True
        from .career import news
        if 'world_news' not in self.career.incident_state and not self.career.over():
            self.backup()
            news.initialize(self.career,self.season)
            dirty=True
        if self.career.discard_stale_awards(self.season):
            dirty=True
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
        if self.career.personal_transfers.get('moves') and any(r.get('kind') == 'invite' and 'team_id' not in r for r in self.career.inbox):
            self.backup()  # Keep the original pair before repairing old transfer invitations.
        dirty = self.career.repair_invite_teams(self.season) or dirty
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
        from .career.assistance import process_invites, process_points
        process_invites(self.career, self.season)
        process_points(self.career, self.season)
        self.season.save()
        self.career.save()

    @staticmethod
    def _recover_personal_command():
        from .paths import save_root
        root = save_root()
        journal = root/'personal-transfer.pending.json'
        if not journal.exists():
            return
        folder = (root/'backups'/json.loads(journal.read_text('utf-8'))['backup']).resolve()
        if not folder.is_relative_to((root/'backups').resolve()):
            raise ValueError('转会恢复记录路径无效，存档未更改。')
        from .save_backups import restore
        restore(root,folder)
        journal.unlink()

    def personal_command(self, command):
        """Rollback both saves after an interrupted transfer, before loading.

        Caller holds the shared application lock. Internal Career.save calls
        are deferred so the pair is committed before sending a UI response.
        """
        from .paths import save_root
        self.persist()
        folder = self.backup()
        old_season, old_career = deepcopy((self.season, self.career))
        journal = save_root()/'personal-transfer.pending.json'
        pending = journal.with_suffix('.writing')
        pending.write_text(json.dumps({'backup': folder.name}), encoding='utf-8')
        pending.replace(journal)
        self.career.save = lambda: None
        try:
            result = command(self.career, self.season)
            del self.career.save
            self.persist()
            journal.unlink()
            return result
        except Exception:
            self.season, self.career = old_season, old_career
            self.season.career = self.career
            self._recover_personal_command()
            raise

    def reset(self) -> None:
        self._replace_career(Season(), Career())

    def backup(self):
        """Compress new snapshots; preserve all existing backups/config/packs."""
        from .paths import save_root
        from .save_backups import create
        return create(save_root())

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
                from .save_backups import restore
                restore(folder.parent.parent,folder,require_pair=False)
            raise

    def create_career(self, payload: dict) -> str:
        from .world import ERA_META, slug, roster_names
        from .career.origins import ORIGINS, DEFAULT_ORIGIN

        payload = dict(payload)
        era = str(payload.get('era') or '2026')
        mode = payload.get('mode') or 'join'
        if era not in ERA_META or mode not in ('join', 'create'):
            raise ValueError('请选择有效的年代和生涯方式。')
        scenario = payload.get('scenario', '')
        if scenario not in ('', 'na_student') or (scenario and mode != 'create'):
            raise ValueError('留学生挑战只能在自建生涯中选择。')
        if scenario == 'na_student':
            payload['region'] = 'AM'
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
