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
    @property
    def arena(self):
        """One local ladder store; never included in career settlement/saves."""
        if not hasattr(self, '_arena'):
            from .arena import Arena
            self._arena = Arena()
        return self._arena

    def __init__(self) -> None:
        from .paths import save_root
        from .storage.transaction import recover
        recover(save_root())
        self._recover_personal_command()
        self.season = Season.load_or_new()
        self.career = Career.load()
        self.season.career = self.career
        from .world.ability import ensure_role_calibration, refresh_player_ability
        role_upgrade = bool(getattr(self.season, "_role_calibration_changed", False))
        for player in [*self.career.free, self.career.you_card or {}]:
            role_upgrade = ensure_role_calibration(player) or role_upgrade
            refresh_player_ability(player)
        if role_upgrade or getattr(self.season, '_calendar_changed', False):
            self.backup()  # Back up the original pair before optional v2 fields are saved.
        dirty = bool(getattr(self.season, "_calendar_changed", False))
        dirty = dirty or role_upgrade
        obsolete=set(getattr(self.season, '_calendar_removed_ids', ())) | set(getattr(self.season, '_calendar_replaced_ids', ()))
        if obsolete:
            self.career.registered=[eid for eid in self.career.registered if eid not in obsolete]
            for row in self.career.inbox:
                if row.get('kind')=='invite' and row.get('event_id') in obsolete:
                    row.update(kind='calendar_notice', status='expired', calendar_legacy=True)
            for eid in obsolete:self.season.qualified.pop(eid,None)
        if self.career.exists:
            if self.career.fix_placeholder_mates(self.season):
                dirty = True
            if self._boot_career():
                dirty = True
        if dirty:
            self.settle()

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
        from .career.story_timing import reconcile
        from .career.notifications import reconcile as file_notices
        dirty = file_notices(self.career, self.season) or dirty
        dirty = reconcile(self.career, self.season) or dirty
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
        from .career.localization import present
        return {
            "ok": True,
            "msg": msg,
            "state": self.season.public(),
            "stories": [present(r) for r in self.career.story_queue or []],
        }

    def persist(self) -> None:
        """Save current values only. No invitations, stories or automatic points."""
        from .storage.transaction import batch, CommitPending
        if getattr(self, '_storage_failed', False):
            raise CommitPending('存档提交等待恢复，请重启后台后继续。')
        with batch():
            self.season.save()
            self.career.save()

    def operation(self):
        from .operations import operation
        return operation(self)

    def settle(self) -> None:
        """Explicit command-side reconciliation, separate from persistence."""
        with self.operation():
            self._reconcile()

    def _reconcile(self) -> None:
        self.sync()
        from .career.assistance import process_invites, process_points
        from .career.story_timing import reconcile
        from .career.notifications import reconcile as file_notices
        file_notices(self.career, self.season)
        reconcile(self.career, self.season)
        process_invites(self.career, self.season)
        process_points(self.career, self.season)
        reconcile(self.career, self.season)
        file_notices(self.career, self.season)
        self.persist()

    def poll_results(self) -> str:
        """Explicit background command; never called while projecting a page."""
        if not any(m.get('cs2_session') and not m.get('played')
                   for ev in self.season.events for m in ev.get('matches', [])):
            return ''
        with self.operation():
            message = self.season.try_ingest_pending_cs2()
            if message:
                self.settle()
            return message

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
        """One recoverable operation; keep the old journal reader for upgrades."""
        if not getattr(self, '_operation_depth', 0):
            self.persist()  # Preserve a direct caller's already accepted edits.
        with self.operation():
            result = command(self.career, self.season)
            self.settle()
            return result

    def reset(self) -> None:
        self._replace_career(Season(), Career())

    def backup(self):
        """Compress new snapshots; preserve all existing backups/config/packs."""
        from .paths import save_root
        from .save_backups import create
        return create(save_root())

    def _replace_career(self, season, career):
        self.backup()  # A failed backup must prevent replacement.
        with self.operation():
            self.season, self.career = season, career
            self.season.career = career
            self.settle()

    def create_career(self, payload: dict, *, start_attributes=None, start_metadata=None,
                      story_seed=None, inherit_preferences=False, quick_mode=None) -> str:
        from .world import ERA_META, slug, roster_names
        from .career.origins import ORIGINS, DEFAULT_ORIGIN

        payload = dict(payload)
        # HTTP/client bodies cannot supply the internal creation attributes or
        # receipts. The 3D adapter resolves its durable draft and passes these
        # separate arguments only after server validation.
        payload.pop('_start_attributes', None)
        payload.pop('_start_metadata', None)
        if start_attributes is not None:
            payload['_start_attributes'] = deepcopy(start_attributes)
        if start_metadata is not None:
            payload['_start_metadata'] = deepcopy(start_metadata)
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
                raise ValueError('请选择有效的开局方式。')
            if payload.get('origin') == 'attribute_draw' and start_attributes is None:
                raise ValueError('七维抽取开局必须使用服务器已保存的属性草稿。')
            if name.casefold() in {n.casefold() for n in roster_names(season.teams)} or not slug(org) or slug(org) in {t['id'] for t in season.teams}:
                raise ValueError('选手或俱乐部已存在，请换一个名称。')
            payload.update(name=name, org=org)
        elif not any(t['id'] == payload.get('team_id') for t in season.teams):
            raise ValueError('所选战队不属于这个年代，请重新选择。')
        career = Career()
        season.career = career
        # Build and validate off to the side. Career.create normally saves, so
        # defer this one instance's write until the old save has been backed up.
        from .storage.transaction import discard_writes
        with discard_writes():
            msg = career.create(payload, season, story_seed=story_seed)
            if inherit_preferences:
                career.steam_id = self.career.steam_id
                career.real_skins = self.career.real_skins
            if quick_mode is not None:
                from .career.fast_mode import configure_season
                configure_season(career, season, quick_mode, season.year)
        self._replace_career(season, career)
        return msg

    def run(self, operation, *args, **kwargs) -> str:
        """Execute a domain command and save; used by desktop button handlers."""
        from .league.outcomes import MatchPaused
        with self.operation():
            try:
                msg = operation(*args, **kwargs)
            except MatchPaused as exc:
                msg = str(exc)
            self.settle()
            return str(msg or "")
