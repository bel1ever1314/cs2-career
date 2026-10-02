"""Explicit installation of the tester's bundled Bot Improver runtime.

Discovery and startup preparation never modify game files or inspect processes.
Only install_bundle, under the service lock and an explicit confirmation, calls
the existing installer after copying every possible overwrite into a local backup.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
from uuid import uuid4


NAME = '随包人机增强 / Bot Improver'
ENV_MOD = 'CS2CAREER_BUNDLED_MOD'
_HOOKS = ('gamemode_competitive.cfg', 'gamemode_competitive_offline.cfg',
          'gamemode_casual.cfg', 'gamemode_custom.cfg', 'listenserver.cfg', 'server.cfg')


def _is_reparse(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, 'st_file_attributes', 0) &
                                    getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def bundle_root() -> Path | None:
    """Only the launcher-selected source or frozen backend's sibling mod is used."""
    explicit = os.environ.get(ENV_MOD, '').strip()
    if explicit:
        candidate = Path(explicit)
        if not candidate.is_absolute():
            base = Path(sys.executable).resolve().parent.parent if getattr(sys, 'frozen', False) else Path.cwd()
            candidate = base / candidate
    elif getattr(sys, 'frozen', False):
        candidate = Path(sys.executable).resolve().parent.parent / 'mod'
    else:
        return None
    try:
        if not candidate.is_dir() or _is_reparse(candidate):
            return None
        root = candidate.resolve()
        if root == Path(root.anchor):
            return None
        for relative in ('addons', 'addons/metamod', 'addons/counterstrikesharp', 'overrides'):
            folder = root / relative
            if not folder.is_dir() or _is_reparse(folder):
                return None
        return root
    except OSError:
        return None


def setup_context() -> dict:
    """Cheap read-only availability. Polling never starts process discovery."""
    return {'available': bundle_root() is not None, 'name': NAME}


def _isolated_root() -> Path:
    raw = os.environ.get('CS2CAREER_SAVE_DIR', '')
    save = Path(raw)
    if not raw or not save.is_absolute() or save.name != 'save':
        raise ValueError('安装只允许使用已隔离的 3D 生涯设置。')
    root = save.resolve().parent
    if root == Path(root.anchor):
        raise ValueError('安装备份不能使用磁盘根目录。')
    marker = root / '.career3d-demo.json'
    if not marker.is_file() or _is_reparse(marker):
        raise ValueError('当前目录缺少 3D 生涯隔离标记。')
    data = json.loads(marker.read_text('utf-8'))
    if not isinstance(data, dict) or data.get('kind') != 'cs2career-godot-demo':
        raise ValueError('当前目录的 3D 生涯隔离标记无效。')
    from cs2career.cs2 import launch
    if launch.SETTINGS_PATH.resolve() != save.resolve() / 'cs2.json':
        raise ValueError('CS2 设置未隔离，不能继续安装。')
    return root


def auto_prepare_config() -> dict:
    """Fill missing machine paths in isolated preferences; never install anything."""
    mod = bundle_root()
    if mod is None:
        return setup_context()
    _isolated_root()
    from cs2career.cs2 import launch
    from tools.career3d_activities import read_cs2_config
    with launch._SETTINGS_LOCK:
        cfg = read_cs2_config()
        before = deepcopy(cfg)
        if not cfg.get('steam_exe') or not Path(cfg['steam_exe']).is_file():
            detected = launch.find_steam_exe()
            if detected and Path(detected).is_file():
                cfg['steam_exe'] = str(Path(detected).resolve())
        csgo = launch.resolve_csgo_path(cfg.get('csgo_path') or '')
        if launch.is_csgo_dir(csgo):
            cfg['csgo_path'] = str(csgo.resolve())
        else:
            detected = launch.find_csgo_path()
            found = launch.resolve_csgo_path(detected) if detected else Path()
            if detected and launch.is_csgo_dir(found):
                cfg['csgo_path'] = str(found.resolve())
        if not cfg.get('mod_source_path') or not launch._improver_here(Path(cfg['mod_source_path'])):
            cfg['mod_source_path'] = str(mod)
        if cfg != before:
            launch._write_settings(launch._clean(cfg))
    return {**setup_context(), 'prepared': cfg != before}


def _bundle_files(mod: Path) -> list[Path]:
    files = []
    for source in sorted(mod.rglob('*')):
        if _is_reparse(source) or not source.resolve().is_relative_to(mod):
            raise ValueError('随包人机增强包含目录链接，未安装。')
        if source.is_file() and source.suffix.casefold() != '.exe':
            files.append(source)
    return files


def _under_game(game: Path, relative: Path) -> Path:
    target = game / relative
    if relative.is_absolute() or '..' in relative.parts or not target.resolve().is_relative_to(game):
        raise ValueError('安装目标超出所选 CS2 目录，未安装。')
    for candidate in (target, *target.parents):
        if candidate.exists() and _is_reparse(candidate):
            raise ValueError('CS2 安装目标含目录链接，未安装。')
        if candidate == game:
            break
    return target


def _snapshot_targets(game: Path, mod: Path, cfg: dict, real_skins: bool) -> list[Path]:
    from cs2career.cs2 import launch
    targets = {source.relative_to(mod) for source in _bundle_files(mod)}
    targets.update(Path(name) for name in ('gameinfo.gi', 'gameinfo_branchspecific.gi'))
    targets.update(Path('cfg') / name for name in _HOOKS)
    targets.add(Path('addons/BotHider/config.json'))
    css = Path('addons/counterstrikesharp')
    for name in ('CareerMatch', 'BotBuy'):
        targets.update(css / 'plugins' / name / (name + suffix) for suffix in ('.dll', '.deps.json'))
    targets.add(css / 'plugins/CareerMatch/tactical_playbook.json')
    bridge = game / css / 'plugins/InvsimCareer'
    if bridge.exists():
        _under_game(game, bridge.relative_to(game))
        for source in bridge.rglob('*'):
            _under_game(game, source.relative_to(game))
            if source.is_file():
                targets.add(source.relative_to(game))
    if real_skins and launch.skins_inventory_mode(cfg) != 'external':
        vendor = launch.vendor_root()
        skin = launch._skins_plugin_dir(vendor / 'InventorySimulator')
        if skin is None:
            raise FileNotFoundError('随包换肤组件缺失，未安装。')
        if _is_reparse(skin):
            raise ValueError('随包换肤组件包含目录链接，未安装。')
        for source in skin.rglob('*'):
            if _is_reparse(source):
                raise ValueError('随包换肤组件包含目录链接，未安装。')
            if source.is_file() and source.suffix.casefold() != '.pdb':
                targets.add(css / 'plugins/InventorySimulator' / source.relative_to(skin))
        targets.update(css / 'gamedata' / name for name in
                       ('inventory-simulator.json', 'inventory-simulator.previous.json'))
        helper = vendor / 'InvsimCareer'
        if helper.exists() and _is_reparse(helper):
            raise ValueError('随包换肤桥包含目录链接，未安装。')
        for source in helper.rglob('*'):
            if _is_reparse(source):
                raise ValueError('随包换肤桥包含目录链接，未安装。')
            if source.is_file() and source.suffix.casefold() != '.pdb':
                targets.add(css / 'plugins/InvsimCareer' / source.relative_to(vendor / 'InvsimCareer'))
    return [_under_game(game, relative) for relative in sorted(targets)]


def _snapshot(root: Path, game: Path, targets: list[Path]) -> tuple[Path, dict]:
    parent = root / 'install-backups'
    if parent.exists() and _is_reparse(parent):
        raise ValueError('安装备份目录含目录链接，未安装。')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    backup = parent / (stamp + '-' + uuid4().hex[:12])
    backup.mkdir(parents=True)
    records = {}
    for target in targets:
        relative = target.relative_to(game)
        if target.exists() and not target.is_file():
            raise ValueError('安装文件目标被目录占用，未安装：' + relative.as_posix())
        if not target.exists():
            records[relative.as_posix()] = {'existed': False}
            continue
        before = hashlib.sha256(target.read_bytes()).hexdigest()
        saved = backup / 'files' / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, saved)
        if hashlib.sha256(saved.read_bytes()).hexdigest() != before or hashlib.sha256(target.read_bytes()).hexdigest() != before:
            raise OSError('安装前备份核对失败，未安装：' + relative.as_posix())
        records[relative.as_posix()] = {'existed': True, 'sha256': before, 'bytes': saved.stat().st_size}
    manifest = {'schema_version': 1, 'kind': 'cs2career3d-install-backup',
                'game_dir': str(game), 'status': 'prepared', 'files': records}
    (backup / 'BACKUP_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf-8')
    return backup, manifest


def install_bundle(state, body: dict) -> dict:
    """Caller owns revision advancement/persistence; this installs only on demand."""
    from cs2career.cs2 import launch
    from tools.career3d_activities import _running_cs2, _scoped_calls, read_cs2_config
    from tools.career3d_business import guard_revision
    from tools.career3d_matches import career_cs2_pending
    guard_revision(state, body)
    if body.get('confirm') is not True:
        raise ValueError('请明确确认安装随包人机增强。')
    root = _isolated_root()
    if state.career.training_session or state.arena.pending or career_cs2_pending(state):
        raise ValueError('CS2、训练或 RTS 对局尚未结束，请完成或取消后再安装。')
    if any((root / 'save' / name).exists() for name in ('manual-load.pending.json', 'personal-transfer.pending.json')):
        raise ValueError('生涯或存档恢复尚未完成，请重启恢复后再安装。')
    mod = bundle_root()
    if mod is None:
        raise FileNotFoundError('此测试包未提供完整的随包人机增强。')
    cfg = read_cs2_config()
    chosen = cfg.get('csgo_path') or ''
    if not chosen or not Path(chosen).is_absolute():
        raise ValueError('请先在设置中保存本机 CS2 / game / csgo 完整路径。')
    game = launch.resolve_csgo_path(chosen).resolve()
    if not launch.is_csgo_dir(game) or not (game / 'gameinfo.gi').is_file():
        raise ValueError('所选 CS2 目录无效或缺少 gameinfo.gi，请核对后再安装。')
    if game == mod or game.is_relative_to(mod) or mod.is_relative_to(game):
        raise ValueError('人机增强来源不能与 CS2 安装目录重叠。')

    def closed(action='安装随包人机增强'):
        if _running_cs2():
            raise ValueError('请完全退出 CS2 后再' + action + '。')

    closed()
    real_skins = bool(state.career.real_skins)
    targets = _snapshot_targets(game, mod, cfg, real_skins)
    backup, manifest = _snapshot(root, game, targets)
    # Pin settings to this isolated snapshot. The desktop's autofill must not
    # switch sources or inspect a different game's configuration while installing.
    install_cfg = {**cfg, 'csgo_path': str(game), 'mod_source_path': str(mod), 'skins_source_path': ''}
    skin_files = 0
    try:
        with _scoped_calls([(launch, 'settings', lambda: deepcopy(install_cfg)),
                            (launch, 'require_cs2_closed', closed)]):
            # Recheck after the backup; a game started while copying is blocked.
            closed()
            result = launch.install_mod(game, mod)
            if not result.get('ok', False):
                raise RuntimeError(str(result.get('msg', '人机增强安装未完成。')))
            if real_skins and launch.skins_inventory_mode(install_cfg) != 'external':
                skins = launch.install_skins_mod(game)
                if not skins.get('ok', False):
                    raise RuntimeError(str(skins.get('msg', '可选换肤组件安装未完成。')))
                skin_files = int(skins.get('files', 0))
        manifest['status'] = 'installed'
    except (OSError, ValueError, RuntimeError) as exc:
        manifest['status'] = 'failed'
        (backup / 'BACKUP_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf-8')
        raise RuntimeError(f'安装未完成；安装前备份保留在 {backup}。{exc}') from exc
    (backup / 'BACKUP_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), 'utf-8')
    total = int(result.get('files', 0)) + skin_files
    return {'reason': f'已安装随包人机增强（{total} 个文件）。安装前备份：{backup}',
            'backup_path': str(backup), 'files': total, 'skin_files': skin_files,
            'setup': setup_context()}
