"""Device commands for reversible local-plugin mounts, independent of matches."""
from __future__ import annotations

import os


def environment_context(cfg=None):
    from cs2career.cs2 import launch
    from cs2career.cs2.environment import snapshot
    from cs2career.cs2.steam_options import launch_options_status
    if cfg is None:
        from cs2career.services.activities import read_cs2_config
        cfg = read_cs2_config()
    path = cfg.get('csgo_path') or ''
    try:
        status = snapshot(launch.resolve_csgo_path(path) if path else '')
    except (OSError, ValueError):
        status = snapshot('')
    steam = launch_options_status(cfg.get('steam_exe', ''))
    status['steam_launch'] = steam
    if status['mode'] == 'normal' and steam.get('insecure'):
        status['reason'] += '\n' + steam['reason']
    return status


def environment_command(state, body, *, before_effect=None):
    """A pending match is retained; only a running game blocks the switch."""
    from cs2career.cs2 import launch
    from cs2career.cs2.environment import finish_watch, switch_environment
    from cs2career.services.activities import config_status, read_cs2_config, settings_context
    from cs2career.services.business import guard_revision
    guard_revision(state, body)
    mode = body.get('mode')
    if mode not in ('normal', 'enhanced'):
        raise ValueError('请选择开启本地插件或恢复普通 CS2。')
    cfg = read_cs2_config()
    if not cfg.get('csgo_path'):
        raise ValueError('请先保存有效的 CS2 game/csgo 路径。')
    if mode == 'enhanced':
        status = config_status()
        checks = status.get('checks', {})
        # The extracted download or Steam path is not needed to mount runtime
        # already installed in this game. Full match preflight checks it later.
        if not all(checks.get(name) for name in ('runtime', 'career_match', 'botbuy')):
            raise ValueError('所选 CS2 尚未安装完整的本地比赛组件，请先安装人机增强。')
    csgo = launch.resolve_csgo_path(cfg['csgo_path'])
    def begin():
        if before_effect is not None:
            before_effect(dict(kind='plugin_environment', game_dir=str(csgo), mode=mode))
    try:
        result = switch_environment(csgo, mode, watch_mode='manual', owner_pid=os.getpid(), before_effect=begin)
    except OSError as exc:
        raise ValueError('插件切换未完成。请确认 CS2 已关闭、游戏目录可写，再刷新状态重试。') from exc
    if mode == 'enhanced':
        from cs2career.cs2.watchdog import spawn_watch
        try:
            spawn_watch(csgo, result['generation'], mode='manual', owner_pid=os.getpid())
        except (OSError, ValueError, RuntimeError) as exc:
            try:
                finish_watch(csgo, result['generation'])
            except (OSError, ValueError, RuntimeError) as restore_error:
                raise ValueError('插件恢复进程未能启动。请关闭 CS2，再点击“关闭插件”恢复普通环境。') from restore_error
            raise ValueError('本地插件恢复进程未能启动，已恢复普通 CS2。请重新打开程序后重试。') from exc
    current = environment_context(cfg)
    reason = ('本地插件已开启。退出 CS2 后自动恢复普通环境。' if mode == 'enhanced' else
              '插件已关闭，可以从 Steam 正常启动 CS2。')
    if mode == 'normal' and current['steam_launch'].get('insecure'):
        reason = '插件加载入口已关闭。\n' + current['steam_launch']['reason']
    return dict(reason=reason, environment=current, settings=settings_context(state))
