"""Reversible local Bot mounts; no Career imports, network or game launches."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

from . import gameinfo

STATE_FILE = '.career-environment.json'
_MODE_CFGS = ('gamemode_competitive.cfg', 'gamemode_competitive_offline.cfg',
              'gamemode_casual.cfg', 'gamemode_custom.cfg')
_HOOK = re.compile(r'(?im)^(?P<indent>[ \t]*)exec[ \t]+'
                   r'(?:"career_(?:rules|quick)\.cfg"|career_(?:rules|quick)\.cfg)'
                   r'[ \t]*(?P<comment>//[^\r\n]*)?(?P<newline>\r?\n|$)')


def _without_hooks(text):
    return _HOOK.sub(lambda hit: (hit['indent'] + hit['comment'] + hit['newline'])
                     if hit['comment'] else '', text)


def _root(csgo):
    root = Path(csgo).resolve()
    if not root.is_dir() or root.name.casefold() != 'csgo' or root.parent.name.casefold() != 'game':
        raise ValueError('请先保存有效的 CS2 game/csgo 路径。')
    if not (root / 'gameinfo.gi').is_file() or not (root / 'cfg').is_dir():
        raise ValueError('CS2 游戏配置不完整，请先在 Steam 验证游戏文件。')
    return root


def _state_path(csgo):
    return _root(csgo) / 'cfg' / STATE_FILE


def read_lease(csgo):
    """Only read the small game-specific lease, never initialize save data."""
    path = _state_path(csgo)
    if not path.is_file():
        return {}
    if path.stat().st_size > 64 * 1024:
        raise ValueError('本地插件状态文件无效，请重新检查游戏设置。')
    state = json.loads(path.read_text('utf-8'))
    if (not isinstance(state, dict) or state.get('schema_version') != 1
            or not re.fullmatch(r'[a-f0-9]{32}', str(state.get('generation', '')))
            or state.get('mode') not in ('normal', 'enhanced') or not isinstance(state.get('watch'), dict)):
        raise ValueError('本地插件状态文件无效，请重新检查游戏设置。')
    return state


def _closed():
    from .process_state import cs2_running
    running = cs2_running()
    if running is not False:
        raise ValueError('请完全退出 CS2 后再开启或关闭本地插件。' if running else
                         '暂时无法确认 CS2 是否已退出，请刷新连接状态后重试。')


def _bytes(path):
    content = path.read_bytes()
    if len(content) > 1024 * 1024:
        raise ValueError('游戏配置文件大小异常，未修改。')
    return content


def _encoded(before, text):
    return (b'\xef\xbb\xbf' if before.startswith(b'\xef\xbb\xbf') else b'') + text.encode('utf-8')


@contextmanager
def _lock(csgo):
    """Coordinate the UI process and the detached exit watcher for this game."""
    path = _root(csgo) / 'cfg' / '.career-environment.lock'
    with path.open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _replace(path, before, after):
    """Back up the observed bytes and compare before each atomic replacement."""
    if before == after:
        return False
    if before is not None and path.name != STATE_FILE:
        backup = path.with_name(path.name + '.career-backup.' + hashlib.sha256(before).hexdigest()[:12])
        if not backup.exists():
            with backup.open('xb') as stream:
                stream.write(before)
                stream.flush()
                os.fsync(stream.fileno())
        if backup.read_bytes() != before:
            raise OSError('游戏配置备份核对失败，原文件未替换。')
    handle, pending = tempfile.mkstemp(prefix='.career-environment-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(after)
            stream.flush()
            os.fsync(stream.fileno())
        _closed()
        current = path.read_bytes() if path.exists() else None
        if current != before:
            raise OSError('游戏配置在切换过程中发生变化，请刷新后重试。')
        os.replace(pending, path)
    finally:
        Path(pending).unlink(missing_ok=True)
    return True


def _plan(csgo, mode):
    root = _root(csgo)
    rows = []
    for name in ('gameinfo.gi', 'gameinfo_branchspecific.gi'):
        path = root / name
        if not path.exists():
            continue
        before = _bytes(path)
        text = before.decode('utf-8-sig')
        _, _, layers = gameinfo._structure(text, allow_missing=name != 'gameinfo.gi')
        for layer in layers:
            if not re.fullmatch(r'[a-zA-Z0-9_-]+', layer) or not (root.parent / layer / 'gameinfo.gi').is_file():
                raise ValueError('CS2 配置引用了已移除的继承目录，请先在 Steam 验证游戏文件。')
        after = (gameinfo.patched_gameinfo(text) if mode == 'enhanced' and name == 'gameinfo.gi'
                 else gameinfo.without_career_mounts(text, optional=name != 'gameinfo.gi') if mode == 'normal'
                 else text)
        rows.append((path, before, _encoded(before, after)))
    for name in _MODE_CFGS:
        path = root / 'cfg' / name
        if not path.exists():
            continue
        before = _bytes(path)
        text = before.decode('utf-8-sig')
        after = _without_hooks(text)
        if mode == 'enhanced' and (root / 'cfg' / 'career_rules.cfg').is_file():
            newline = '\r\n' if '\r\n' in text else '\n'
            after = after.rstrip('\r\n') + newline + 'exec career_rules.cfg' + newline
        rows.append((path, before, _encoded(before, after)))
    return rows


def _write_mode(csgo, mode, *, watch_mode='manual', owner_pid=None):
    _closed()
    root = _root(csgo)
    plan = _plan(root, mode)
    state_path = _state_path(root)
    before = state_path.read_bytes() if state_path.exists() else None
    state = dict(schema_version=1, generation=uuid.uuid4().hex, mode=mode,
                 watch=dict(active=mode == 'enhanced', mode=watch_mode,
                            started_at=datetime.now(timezone.utc).isoformat(), owner_pid=owner_pid))
    plan.append((state_path, before, (json.dumps(state, ensure_ascii=False, indent=2)+'\n').encode('utf-8')))
    applied = []
    try:
        for path, old, new in plan:
            if _replace(path, old, new):
                applied.append((path, old, new))
    except BaseException:
        # Restore only our own replacements. Never roll back over a Valve update
        # or another app's edit, and never modify a now-running game.
        for path, old, new in reversed(applied):
            try:
                if old is not None and path.read_bytes() == new:
                    _replace(path, new, old)
            except (OSError, ValueError):
                pass
        raise
    return state


def switch_environment(csgo, mode, *, watch_mode='manual', owner_pid=None):
    if mode not in ('normal', 'enhanced') or watch_mode not in ('manual', 'dispatch'):
        raise ValueError('请选择开启本地插件或恢复普通 CS2。')
    if owner_pid is not None and (type(owner_pid) is not int or owner_pid <= 0):
        raise ValueError('本地插件恢复进程身份无效。')
    _closed()  # A refused switch must not even create its coordination file.
    with _lock(csgo):
        state = _write_mode(csgo, mode, watch_mode=watch_mode, owner_pid=owner_pid)
    return {**snapshot(csgo), 'lease': state}


def finish_watch(csgo, generation):
    with _lock(csgo):
        lease = read_lease(csgo)
        if lease.get('generation') != generation or lease.get('mode') != 'enhanced' or not lease.get('watch', {}).get('active'):
            return dict(status='superseded')
        _write_mode(csgo, 'normal')
    return dict(status='restored', environment=snapshot(csgo))


def snapshot(csgo):
    """UI status is determined from the files, not just a remembered checkbox."""
    try:
        root = _root(csgo)
        lease = read_lease(root)
        normal_plan = _plan(root, 'normal')
        mounts = any(path.name.startswith('gameinfo') and before != after for path, before, after in normal_plan)
        hooks = any(path.parent.name == 'cfg' and before != after for path, before, after in normal_plan)
        base = (root / 'gameinfo.gi').read_text('utf-8-sig')
        patched = gameinfo.patched_gameinfo(base)
        mode = 'enhanced' if mounts and patched == base else 'mixed' if mounts or hooks else 'normal'
        from .process_state import cs2_running
        live = cs2_running()
        armed = lease.get('mode') == 'enhanced' and bool(lease.get('watch', {}).get('active'))
        reason = ('本地插件已开启。退出 CS2 后会自动恢复普通环境。' if mode == 'enhanced' and armed else
                  '本地插件已开启。请从本项目进入比赛，或一键恢复普通 CS2。' if mode == 'enhanced' else
                  '本地插件加载入口已关闭，普通 CS2 环境已恢复。' if mode == 'normal' else
                  '检测到部分本地加载入口，可以一键恢复普通 CS2。')
        if live is not False:
            reason = ('CS2 正在运行，请完全退出后再切换插件。' if live else
                      '暂时无法确认 CS2 进程，请刷新后再切换插件。')
        return dict(mode=mode, valid=True, switch_available=live is False, reason=reason,
                    auto_restore=True, watch_active=bool(lease.get('watch', {}).get('active')),
                    generation=lease.get('generation', ''), watch=deepcopy(lease.get('watch', {})),
                    cs2_running=live, process_known=live is not None)
    except (OSError, ValueError, UnicodeError) as exc:
        return dict(mode='unknown', valid=False, switch_available=False, reason=str(exc),
                    auto_restore=True, watch_active=False, generation='', watch={},
                    cs2_running=None, process_known=False)
