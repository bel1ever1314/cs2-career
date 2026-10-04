"""Device adapters for the isolated Godot sample.

Use existing Arena captain/draft/veto, CS2 handoff and nonce-bound ingestion.
Ranked lobbies and career series use existing CS2 adapters. Scrims simulate.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
from uuid import uuid4


def _public_report(record):
    out = deepcopy(record)
    if isinstance(out.get('map'), dict):
        out['map'].pop('events', None)
    return out


def team_directory(state):
    ranks = {r['id']: r['rank'] for r in state.season.vrs.table(state.season.teams, state.season.date)}
    return sorted([dict(id=t['id'], name=t['name'], region=t.get('region', ''), rank=ranks.get(t['id']))
                   for t in state.season.teams], key=lambda t: (t['rank'] or 9999, t['name']))


def device_context(state):
    from cs2career.arena import MAPS
    arena = state.arena
    human = arena.career_player_id(state)
    player = arena.roster(state).get(human)
    record = arena._record(state, player) if player else dict(elo=0, wins=0, losses=0)
    lobby = deepcopy(arena.data.get('lobby'))
    if lobby:
        lobby.pop('request', None)
        lobby.pop('career3d_retired_sessions', None)
        lobby['turn'] = arena.turn(lobby)
        if lobby.get('result'):
            lobby['result'] = _public_report(lobby['result'])
    store = state.career.incident_state.get('career3d_service', {})
    scrims = deepcopy(store.get('scrims', []))
    directory = team_directory(state)
    connection = ladder_status(state, check_running=False)
    # The current report is already in lobby/history; status polling has its
    # own full result response when the connection page needs it.
    connection.pop('result', None)
    from tools.career3d_business import business_context
    return dict(teams=directory, **business_context(state), personal=personal_context(state), skins=skin_context(state),
                ladder=dict(revision=arena.data['revision'], lobby=lobby, rank_human_id=human,
                            player={k: record.get(k, 0) for k in ('elo', 'wins', 'losses')},
                            history=[_public_report(r) for r in arena.data['matches'][-10:][::-1]],
                            maps=list(MAPS), connection=connection, shared_lobby=_shared_lobby(arena)),
                custom=custom_context(state),
                scrims=dict(opponents=[t for t in directory if t['id'] != state.career.team_id],
                            scheduled=[r for r in scrims if r['status'] == 'scheduled'],
                            history=[{**r, 'report': _public_report(r['report'])}
                                     for r in reversed(scrims) if r['status'] == 'finished'][:10]))


def _shared_lobby(arena):
    lobby = arena.data.get('lobby')
    return {key: lobby.get(key, '') for key in ('id', 'mode', 'phase')} if lobby else None


def custom_context(state):
    """The original single Arena room, projected only to its custom page."""
    from cs2career.arena import MAPS
    arena = state.arena
    lobby = deepcopy(arena.data.get('lobby'))
    if lobby and lobby.get('mode') == 'custom':
        lobby.pop('request', None)
        lobby.pop('career3d_retired_sessions', None)
        lobby['turn'] = arena.turn(lobby)
        lobby['observer'] = not bool(lobby.get('human_id'))
        if lobby.get('result'):
            lobby['result'] = _public_report(lobby['result'])
    else:
        lobby = None
    return dict(revision=arena.data['revision'], lobby=lobby, shared_lobby=_shared_lobby(arena),
                history=[_public_report(row) for row in reversed(arena.data['matches'])
                         if row.get('mode') == 'custom'][:10], maps=list(MAPS),
                rts_rosters=_custom_rts_rosters(lobby) if lobby else None)


def _custom_rts_rosters(lobby):
    """Read-only RTS visualization aliases, never CS2 or career simulation input."""
    from cs2career.world.ability import ALL_AXES, playing_ability, playing_stats
    aliases = dict(aim='firepower', reaction='opening', recoil='trading', awareness='clutching', utility='utility')
    out = dict(team_names={}, map='de_' + lobby['map'], human_id=lobby.get('human_id', ''),
               skills_source=aliases, read_only=True)
    for side, arena_side in (('ct', lobby['ct']), ('t', 'b' if lobby['ct'] == 'a' else 'a')):
        cards = []
        for pid in lobby[arena_side]:
            player = lobby['roster'][pid]
            ability = playing_ability(player)
            expressed = playing_stats(player)
            stats = {key: expressed.get(key) for key in ALL_AXES}
            skills = {key: stats[axis] if type(stats.get(axis)) in (int, float) else ability
                      for key, axis in aliases.items()}
            cards.append(dict(id=pid, player_id=pid, name=player['name'], role=player.get('role', 'rifle'),
                              ability=ability, skills=skills, stats=stats))
        out[side] = cards
        out['team_names'][side] = 'Team ' + arena_side.upper()
    return out


def custom_catalog(state, page=1, search='', page_size=20):
    from cs2career.arena import MAPS
    if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 50:
        raise ValueError('页码必须为正整数，每页应为 1 至 50 人。')
    if not isinstance(search, str) or len(search) > 80:
        raise ValueError('选手搜索应为 80 字以内的文字。')
    search = search.strip()
    rows = state.arena.catalog(state, 'custom')
    needle = search.casefold()
    if needle:
        rows = [row for row in rows if needle in ' '.join(str(row.get(key, ''))
                for key in ('player_id', 'name', 'club', 'role')).casefold()]
    total, start = len(rows), (page - 1) * page_size
    return dict(ok=True, revision=state.arena.data['revision'], rows=rows[start:start + page_size],
                page=page, page_size=page_size, total=total, pages=max(1, (total + page_size - 1) // page_size),
                search=search, maps=list(MAPS))


def _custom_room(state, body):
    lobby = state.arena.data.get('lobby')
    if not lobby or lobby.get('mode') != 'custom' or lobby['id'] != body.get('lobby_id'):
        raise ValueError('当前自定义房间身份已变化，请刷新；不能操作天梯房间。')
    return lobby


def _custom_options(body, ids):
    from cs2career.arena import MAPS
    human, map_name, ct = body.get('human_id', ''), body.get('map', 'dust2'), body.get('ct', 'a')
    if not isinstance(human, str) or human and human not in ids:
        raise ValueError('控制的选手必须在本场十人中；空值表示十 Bot 观察者。')
    if map_name not in MAPS or ct not in ('a', 'b'):
        raise ValueError('请选择原有地图和开场 CT 队伍 A 或 B。')
    return dict(map=map_name, ct=ct, human_id=human)


def custom_command(state, action, body):
    """Thin original Arena adapters; custom reports never settle ladder Elo."""
    arena = state.arena
    if action == 'recommend':
        human = body.get('human_id', '')
        if not isinstance(human, str) or human and human not in arena.roster(state):
            raise ValueError('请选择资料库中的稳定选手身份，或空值观察者。')
        ids = arena.recommend(state, 'custom', human)
        catalog = {row['player_id']: row for row in arena.catalog(state, 'custom')}
        return dict(reason='原有推荐名单已生成；尚未创建或修改房间。', players=ids,
                    rows=[catalog[pid] for pid in ids], read_only=True)
    if action not in ('create', 'configure', 'simulate', 'launch', 'collect', 'cancel'):
        raise ValueError('没有这个自定义对局操作。')
    if action not in ('collect', 'cancel'):
        if state.career.training_session:
            raise ValueError('训练对局尚未完成，请先录入或取消训练。')
        if arena._career_pending(state):
            raise ValueError('职业比赛正在等待 CS2 回传，请先录入后再进入自定义对局。')
    if action == 'create':
        ids = body.get('players')
        if not isinstance(ids, list) or len(ids) != 10 or any(not isinstance(pid, str) for pid in ids) or len(set(ids)) != 10:
            raise ValueError('请选择十名不同的稳定选手身份，前五名 A 队、后五名 B 队。')
        options = _custom_options(body, ids)
        # Validate every requested option before the original creator commits.
        arena.create(state, dict(revision=body.get('revision'), mode='custom', players=ids,
                                 human_id=options['human_id']))
        if options['map'] != 'dust2' or options['ct'] != 'a':
            arena.configure(dict(revision=arena.data['revision'], **options))
        return {'reason': '自定义十人房间已创建，不计算天梯积分或生涯奖励。'}
    lobby = _custom_room(state, body)
    if action in ('launch', 'collect'):
        return _arena_cs2_command(state, action, body, 'custom')
    if action == 'simulate':
        if lobby['phase'] == 'finished':
            if (lobby.get('result') or {}).get('source') != 'simulated':
                raise ValueError('这场真实 CS2 战绩已录入，不能用模拟覆盖。')
            return {'reason': '自定义对局已结束。', 'result': _public_report(lobby['result']), 'replayed': True}
        arena._guard(body.get('revision'))
        if lobby['phase'] in ('starting', 'launched'):
            recovered = recover_arena_cs2(state, body, 'custom', 'simulate')
            if recovered:
                return recovered
        if lobby['phase'] != 'ready':
            raise ValueError('自定义房间尚未准备好；待回传的真实比赛不能模拟。')
        a, b = _mix_team(lobby, 'a'), _mix_team(lobby, 'b')
        a['name'], b['name'] = 'Team A', 'Team B'
        mp = _simulate(a, b, lobby['map'], lobby['id'])
        record = dict(id=lobby['id'], date=state.season.date, source='simulated', mode='custom',
                      map=mp, human_id=lobby['human_id'], winner='a' if mp['winner'] == a['name'] else 'b',
                      teams=[a['name'], b['name']], changes={})
        before = deepcopy(arena.data)
        try:
            lobby.update(phase='finished', result=record)
            arena.data['matches'] = (arena.data['matches'] + [record])[-100:]
            arena._commit()
        except Exception:
            arena.data = before
            raise
        return {'reason': '自定义模拟战报已保存，不计积分或生涯奖励。', 'result': _public_report(record)}
    arena._guard(body.get('revision'))
    if action == 'configure':
        options = _custom_options(body, lobby['selection'])
        arena.configure(dict(revision=body.get('revision'), **options))
        return {'reason': '自定义地图、开场阵营与控制身份已保存。'}
    if lobby['phase'] in ('starting', 'launched') and _running_cs2() is not False:
        raise ValueError('请完全退出 CS2，核验进程后再放弃本场自定义对局。')
    arena.cancel(body)
    return {'reason': '自定义房间已关闭；没有计算积分或生涯奖励。'}


def _simulate(team_a, team_b, map_name, seed):
    from cs2career.engine.match import RNG, play_map
    before = RNG.getstate()
    try:
        # Device activity must not consume the world's next tournament RNG.
        RNG.seed(int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], 'big'))
        return play_map(deepcopy(team_a), deepcopy(team_b), map_name)
    finally:
        RNG.setstate(before)


def _mix_team(lobby, side):
    players = [deepcopy(lobby['roster'][pid]) for pid in lobby[side]]
    return dict(id='device-' + side, name='蓝队' if side == 'a' else '橙队', players=players,
                command=sum(p.get('command', 50) for p in players) / 5,
                mentality=70, map_adaptation=65, strong_maps=[], weak_maps=[])


def _simulate_rank(state, body):
    arena, lobby = state.arena, state.arena.data.get('lobby')
    if not lobby or lobby.get('mode') != 'rank' or lobby['id'] != body.get('lobby_id'):
        raise ValueError('当前天梯房间身份已变化，请刷新。')
    if lobby['phase'] == 'finished':
        if (lobby.get('result') or {}).get('source') != 'simulated':
            raise ValueError('这场真实 CS2 战绩已录入，不能用模拟覆盖。')
        return {'reason': '比赛已结束。', 'result': deepcopy(lobby['result']), 'replayed': True}
    arena._guard(body.get('revision'))
    arena.require_rank_identity(state)
    if lobby['phase'] in ('starting', 'launched'):
        recovered = recover_arena_cs2(state, body, 'rank', 'simulate')
        if recovered:
            return recovered
    if lobby['phase'] != 'ready':
        raise ValueError('请先完成房间；正在启动或等待真实回传的比赛不能模拟。')
    a, b = _mix_team(lobby, 'a'), _mix_team(lobby, 'b')
    mp = _simulate(a, b, lobby['map'], lobby['id'])
    won_a = mp['winner'] == a['name']
    averages = {side: sum(lobby['ratings'][pid] for pid in lobby[side]) / 5 for side in ('a', 'b')}
    expected = 1 / (1 + 10 ** (max(-2000, min(2000, averages['b'] - averages['a'])) / 400))
    delta = round(32 * (int(won_a) - expected))
    before = deepcopy(arena.data)
    try:
        changes = {}
        for side, team in (('a', a), ('b', b)):
            for line in mp['players'][team['name']]:
                pid, change = line['player_id'], delta if side == 'a' else -delta
                row = arena.data['ladder'][pid]
                row['elo'] += change
                row['wins' if (side == 'a') == won_a else 'losses'] += 1
                row['recent'] = (row['recent'] + [{**line, 'rounds': mp['rounds']}])[-10:]
                row['name'] = lobby['roster'][pid]['name']
                changes[pid] = change
        record = dict(id=lobby['id'], date=state.season.date, source='simulated', mode='rank', map=mp,
                      human_id=lobby['human_id'], winner='a' if won_a else 'b', teams=[a['name'], b['name']], changes=changes)
        lobby.update(phase='finished', result=record)
        arena.data['matches'] = (arena.data['matches'] + [record])[-100:]
        arena._commit()
    except Exception:
        arena.data = before
        raise
    return {'reason': '比赛已结束。', 'result': deepcopy(record)}


def ladder_command(state, action, body):
    arena = state.arena
    lobby = arena.data.get('lobby')
    if action != 'matchmake' and lobby and lobby.get('mode') != 'rank':
        raise ValueError('共享房间属于自定义对局，不能从天梯入口修改或关闭。')
    if action not in ('cancel', 'collect') and state.career.training_session:
        raise ValueError('训练对局尚未完成，请先录入或取消训练。')
    if action not in ('cancel', 'collect') and any(m.get('cs2_session') and not m.get('played')
            for ev in state.season.events for m in ev.get('matches', [])):
        raise ValueError('职业比赛正在等待 CS2 回传，请先录入后再进入天梯。')
    if action in ('launch', 'collect'):
        return ladder_cs2_command(state, action, body)
    if action == 'simulate':
        return _simulate_rank(state, body)
    methods = {'matchmake': arena.matchmake, 'pick': arena.pick, 'advance': arena.advance,
               'ban': arena.ban, 'side': arena.choose_side, 'cancel': arena.cancel}
    if action not in methods:
        raise ValueError('没有这个天梯操作')
    if action == 'matchmake':
        methods[action](state, body)
    else:
        arena.guard_rank_action(state, action)
        methods[action](body)
    return {'reason': '匹配成功。' if action == 'matchmake' else '房间已更新。'}


@contextmanager
def _scoped_calls(overrides):
    originals = []
    try:
        for module, name, replacement in overrides:
            originals.append((module, name, getattr(module, name)))
            setattr(module, name, replacement)
        yield
    finally:
        for module, name, original in reversed(originals):
            setattr(module, name, original)


_CS2_PATH_FIELDS = ('steam_exe', 'csgo_path', 'mod_source_path', 'skins_source_path')


def _clean_config_path(value):
    """Explorer's Copy as path quotes are not part of the filesystem path."""
    text = str(value or '').strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        text = text[1:-1].strip()
    return text


def read_cs2_config():
    """settings()/status() save and autofill paths; polling must use this pure read."""
    from cs2career.cs2 import launch
    cfg = dict(launch.DEFAULTS)
    if launch.SETTINGS_PATH.is_file():
        try:
            saved = json.loads(launch.SETTINGS_PATH.read_text('utf-8-sig'))
            if isinstance(saved, dict):
                cfg.update({k: v for k, v in saved.items() if k in cfg and
                            (isinstance(v, str) or k in ('skin_inspect_enabled', 'skin_tools_enabled') and type(v) is bool)})
        except (OSError, ValueError):
            pass
    for key in _CS2_PATH_FIELDS:
        cfg[key] = _clean_config_path(cfg.get(key))
    return launch._clean(cfg)


def config_status():
    from cs2career.cs2 import launch
    from tools.career3d_runtime_compat import runtime_context
    cfg = read_cs2_config()
    csgo = launch.resolve_csgo_path(cfg.get('csgo_path') or '')
    checks = {'steam': bool(cfg.get('steam_exe')) and Path(cfg['steam_exe']).is_file(),
              'csgo': bool(cfg.get('csgo_path')) and launch.is_csgo_dir(csgo)
                      and (csgo / 'gameinfo.gi').is_file(),
              'mod': bool(cfg.get('mod_source_path')) and launch._improver_here(Path(cfg['mod_source_path']))}
    checks['runtime'] = checks['csgo'] and launch.mod_installed(csgo)
    checks['career_match'] = checks['csgo'] and all((launch.plugin_dir(csgo) / name).is_file()
        for name in ('CareerMatch.dll', 'CareerMatch.deps.json'))
    checks['botbuy'] = checks['csgo'] and all((csgo / 'addons' / 'counterstrikesharp' / 'plugins' / 'BotBuy' / name).is_file()
        for name in ('BotBuy.dll', 'BotBuy.deps.json'))
    missing = [key for key, okay in checks.items() if not okay]
    path_errors = []
    if not checks['steam']:
        path_errors.append('Steam 程序未找到，请选择 steam.exe。')
    if not checks['csgo']:
        path_errors.append('CS2 目录未找到或缺少 gameinfo.gi，请选择游戏根目录或 game/csgo。')
    if not checks['mod']:
        path_errors.append('人机增强发行包目录不完整，请选择包含 addons/metamod、addons/counterstrikesharp 和 overrides 的目录。')
    component_labels = {'runtime': '人机增强', 'career_match': '比赛回传组件', 'botbuy': '买枪组件'}
    # A missing game path is a path problem, not evidence that its plugins
    # need installing. Only inspect the selected, valid game's components.
    component_errors = [label + '尚未安装到所选 CS2 目录。'
                        for key, label in component_labels.items() if checks['csgo'] and not checks[key]]
    if not missing:
        reason = '路径和比赛组件已就绪。'
    else:
        reason = ' '.join(path_errors + component_errors)
        if component_errors:
            reason += ' 请在设置中点击“安装填写目录的人机增强”。'
    return {'ready': not missing, 'reason': reason, 'missing': missing, 'checks': checks,
            'path_errors': path_errors, 'component_errors': component_errors,
            'compatibility': runtime_context(Path(cfg.get('mod_source_path') or '')),
            'difficulty': cfg['difficulty'], 'difficulties': list(launch.DIFFICULTIES),
            'csgo_path': str(csgo) if cfg.get('csgo_path') else '', 'steam_exe': cfg.get('steam_exe', ''),
            'mod_source_path': cfg.get('mod_source_path', ''), 'plugins_install_enabled': True}


def settings_context(state):
    from tools.career3d_install import setup_context
    from tools.career3d_cs2_environment import environment_context
    cfg = read_cs2_config()
    return {**cfg, 'revision': int(state.career.incident_state.get('career3d_service', {}).get('revision', 0)),
            'real_skins': bool(state.career.real_skins), 'steam_id': state.career.steam_id,
            'config': config_status(), 'setup': setup_context(), 'environment': environment_context(cfg),
            'loadout_status': _skin_loadout_context(state.career, cfg), 'isolated': True}


def settings_command(state, body):
    """Persist independent preferences; never rebuild staged game files here."""
    from cs2career.cs2 import launch
    from cs2career.career import skins
    from tools.career3d_business import guard_revision
    guard_revision(state, body)
    patch = body.get('settings', {})
    if not isinstance(patch, dict) or any(key not in launch.DEFAULTS for key in patch):
        raise ValueError('请选择现有 CS2 设置字段。')
    cfg = read_cs2_config()
    options = {'difficulty': launch.DIFFICULTIES, 'bot_aim': launch.AIM_MODES,
               'bot_nades': launch.NADE_MODES, 'bot_identity': launch.IDENTITY_MODES,
               'bot_movement': launch.MOVEMENT_MODES, 'match_chat': ('on', 'custom', 'off'),
               'skins_inventory_mode': launch.SKINS_INVENTORY_MODES}
    for key, value in patch.items():
        if key in ('skin_inspect_enabled', 'skin_tools_enabled'):
            if type(value) is not bool:
                raise ValueError('饰品接口开关必须是布尔值。')
        elif not isinstance(value, str) or len(value) > 2048 or '\x00' in value or '\n' in value or '\r' in value:
            raise ValueError('CS2 设置必须是有效的单行文本。')
        if key in options and value not in options[key]:
            raise ValueError('未知 CS2 设置选项：' + key)
    if state.career.training_session or state.arena.pending or any(m.get('cs2_session') and not m.get('played')
            for ev in state.season.events for m in ev.get('matches', [])):
        raise ValueError('真实比赛正在启动或等待回传，请先完成比赛再修改设置。')
    if patch and _running_cs2():
        raise ValueError('请完全退出 CS2 后再修改开赛设置。')
    real = body.get('real_skins', bool(state.career.real_skins))
    steam = body.get('steam_id', state.career.steam_id)
    if type(real) is not bool or not isinstance(steam, str):
        raise ValueError('游戏内换肤设置格式不正确，请重新选择。')
    if real and (len(steam) != 17 or not steam.isdigit()):
        raise ValueError('启用游戏内换肤时，请填写 17 位数字 SteamID64；暂不使用可先关闭游戏内换肤。')
    for key, value in patch.items():
        if key in _CS2_PATH_FIELDS:
            value = _clean_config_path(value)
        cfg[key] = str(launch.resolve_csgo_path(value)) if key == 'csgo_path' and value else value
    # save_settings also modifies a staged CS2 request and skin ownership.
    # The low-level atomic writer is scoped to the independent save root.
    with launch._SETTINGS_LOCK:
        launch._write_settings(launch._clean(cfg))
    if 'real_skins' in body or 'steam_id' in body:
        with _scoped_calls([(skins, 'sync_live', lambda _career: None),
                            (skins, 'plugin_installed', lambda _csgo=None: False)]):
            state.career.set_skin_pref(real, steam)
    return {'reason': '游戏路径、难度和可选换肤已保存在独立生涯。', 'settings': settings_context(state)}


def _existing_skin_plugin(cfg):
    from cs2career.career import skins
    return bool(cfg.get('csgo_path')) and skins.plugin_installed(Path(cfg['csgo_path']))


def _skin_loadout_context(career, cfg):
    from cs2career.cs2 import launch
    status = launch.career_loadout_status(career, cfg)
    installed = _existing_skin_plugin(cfg)
    if status['state'] == 'ready' and not installed:
        status = dict(status, state='unavailable', reason='换肤已开启，但游戏内换肤组件尚未安装。')
    return dict(status, plugin_installed=installed)


def _cached_art(skin_id, manifest):
    from tools.career3d_resources import cached_skin_art
    return cached_skin_art(skin_id, manifest)


def skin_context(state):
    from cs2career.career import skins
    from cs2career.skin_art import manifest
    cfg = read_cs2_config()
    loadout = _skin_loadout_context(state.career, cfg)
    installed = loadout['plugin_installed']
    with _scoped_calls([(skins, 'plugin_installed', lambda _csgo=None: installed)]):
        shop = skins.shop_public(deepcopy(state.career))
    # These original desktop catalogs are separate products, not items exposed
    # by the 3D market. Keep device polling small; the core catalog is unchanged.
    for key in ('inspect_catalog', 'stickers', 'sticker_models', 'loadout_packs'):
        shop.pop(key, None)
    from tools.career3d_skin_bundles import bundle_context
    shop['loadout_packs'] = bundle_context(state)
    for box in shop['cases']:
        box.pop('pool', None)  # Market already carries every decorated skin.
    art = manifest()
    for row in shop['market'] + shop['inventory']:
        row['art_path'] = _cached_art(row.get('skin_id') or row['id'], art)
    shop.update(personal_money=state.career.money, real_skins=bool(state.career.real_skins),
                steam_id=state.career.steam_id, live_sync_deferred=True,
                loadout_status=loadout,
                integration_ready=bool(installed and loadout['state'] in ('ready', 'external')),
                integration_reason=loadout['reason'])
    return shop


def personal_context(state):
    from cs2career.world.ability import (ALL_AXES, AXIS_LABEL, effective_form_delta,
                                       playing_ability, playing_stats, position_views)
    from cs2career.career.story_timing import window
    from cs2career.presentation import inspect
    c, s = state.career, state.season
    you, team = c.my_player(s.teams) or c.you_card or {}, c.my_team(s.teams) or {}
    attributes = {key: (you.get('stats') or {}).get(key) for key in ALL_AXES}
    if attributes['command'] is None:
        attributes['command'] = you.get('command')
    playing = playing_stats(you)
    reason = ''
    if c.training_session:
        reason = '训练对局尚未完成，请先录入或取消训练再加点。'
    elif state.arena.pending:
        reason = '天梯比赛正在启动或等待真实回传，请先录入或关闭房间后再加点。'
    elif any(m.get('cs2_session') and not m.get('played') for ev in s.events for m in ev.get('matches', [])):
        reason = '职业比赛正在等待真实回传，请先录入后再加点。'
    elif c.over():
        reason = '这段生涯已经结束。'
    elif c.assist.get('quick_mode') and not window(c, s):
        reason = '快速模式的属性点已保留，请在 Major 结束后的休赛期统一分配。'
    elif c.attr_points < 1:
        reason = '没有可用属性点。'
    elif not c.my_player(s.teams) or not team:
        reason = '找不到你的选手数据。'
    elif all(value is not None and int(round(float(value))) >= 100 for value in attributes.values()):
        reason = '全部属性已满。'
    detail = inspect(state, 'player', you.get('player_id') or '', span='season') if you.get('player_id') else None
    summary = deepcopy((detail or {}).get('summary') or {})
    summary = {**{key: summary.get(key) for key in ('rating', 'k', 'd', 'a', 'adr', 'kast', 'maps', 'rounds')}, **summary}
    return {'player_id': you.get('player_id', ''), 'name': you.get('name', c.player_name),
            'attributes': attributes, 'axes': list(ALL_AXES), 'axis_labels': dict(AXIS_LABEL),
            'attr_points': c.attr_points, 'ability': playing_ability(you), 'form_delta': effective_form_delta(you),
            'playing_attributes': {key: playing.get(key) for key in ALL_AXES},
            'position_views': position_views(you),
            'growth_allowed': not reason, 'growth_reason': reason,
            'stats': summary, 'stats_source': 'career_season',
            'personal_money': c.money, 'club_money': team.get('money', 0),
            'state': {'retired': bool(c.retired), 'banned': bool(c.banned), 'unsigned': bool(c.unsigned),
                      'over': bool(c.over()), 'origin': c.origin, 'role': c.role}}


def spend_attributes(state, body):
    from cs2career.world.ability import ALL_AXES
    c, s = state.career, state.season
    current = int(c.incident_state.get('career3d_service', {}).get('revision', 0))
    if type(body.get('revision')) is not int or body['revision'] != current:
        raise ValueError('个人资料已变化，请刷新后再确认加点。')
    allocations = body.get('allocations')
    if allocations is None and body.get('key'):
        allocations = {body['key']: 1}
    if not isinstance(allocations, dict) or not allocations or any(k not in ALL_AXES for k in allocations):
        raise ValueError('请选择原有属性维度。')
    if any(type(v) is not int or v < 0 or v > 100 for v in allocations.values()) or not sum(allocations.values()):
        raise ValueError('属性分配必须是非负整数，且至少投入一点。')
    personal = personal_context(state)
    if not personal['growth_allowed']:
        raise ValueError(personal['growth_reason'])
    if sum(allocations.values()) > c.attr_points:
        raise ValueError('分配点数超过当前可用属性点。')
    for key, count in allocations.items():
        value = personal['attributes'].get(key)
        value = int(round(float(value or (50 if key == 'command' else 70))))
        if value + count > 100:
            raise ValueError('属性分配超过 100 上限。')
    for key in ALL_AXES:
        for _ in range(allocations.get(key, 0)):
            c.spend_point(s, key, persist=False)
    return {'reason': '属性分配已按现有成长规则保存。'}


def skin_command(state, action, body):
    from cs2career.career import skins
    c = state.career
    current = int(c.incident_state.get('career3d_service', {}).get('revision', 0))
    if type(body.get('revision')) is not int or body['revision'] != current:
        raise ValueError('库存或资金已变化，请刷新后再操作。')
    if action not in ('buy', 'case', 'keep', 'cash', 'sell', 'equip', 'preferences'):
        raise ValueError('没有这个饰品操作。')
    # Equip/sell normally sync game files immediately; defer that to the one
    # authorized CS2 match launch so live games retain frozen cosmetics.
    with _scoped_calls([(skins, 'sync_live', lambda _career: None),
                        (skins, 'plugin_installed', lambda _csgo=None: False)]):
        if action == 'buy':
            sid = str(body.get('id') or '')
            if sid not in skins.skin_map() or c.money < skins.quote_of(c, sid):
                raise ValueError('饰品不存在或个人资金不足。')
            message = c.buy_skin(sid)
        elif action == 'case':
            cid = str(body.get('id') or '')
            if cid not in skins.case_map() or c.pending_drop or c.money < skins.case_cost(cid, c):
                raise ValueError('箱子不存在、个人资金不足，或上个掉落还未处理。')
            message = c.buy_case(cid)
        elif action in ('keep', 'cash'):
            if not c.pending_drop:
                raise ValueError('没有待处理的掉落。')
            message = c.keep_drop() if action == 'keep' else c.cash_drop()
        elif action in ('sell', 'equip'):
            item_id = str(body.get('id') or '')
            item = next((r for r in c.inventory if r['id'] == item_id), None)
            if not item:
                raise ValueError('库存中没有这件饰品。')
            if action == 'sell':
                message = c.sell_skin(item_id)
            else:
                side = body.get('side')
                if side not in ('ct', 't') or side not in skins.sides_for(item.get('slot', '')):
                    raise ValueError('请选择这件饰品支持的 CT 或 T 阵营。')
                if 'off' in body and type(body['off']) is not bool:
                    raise ValueError('off 必须是布尔值。')
                c.equip_skin(item_id, side, bool(body.get('off')))
                message = '本地装备已保存，进入 CS2 比赛时使用这份装备。'
        else:
            if type(body.get('real')) is not bool:
                raise ValueError('real 必须是布尔值。')
            steam_id = str(body.get('steam_id') or c.steam_id)
            if body['real'] and (len(steam_id) != 17 or not steam_id.isdigit()):
                raise ValueError('游戏内换肤需要 17 位数字 SteamID。')
            c.set_skin_pref(body['real'], steam_id)
            message = '换肤偏好已保存在独立生涯，进入 CS2 比赛时应用。'
    return {'reason': message}


def _peek_ladder_result(state, cfg):
    from cs2career.cs2 import launch
    from cs2career.cs2.result import pick_better_result
    from cs2career.paths import save_file
    lobby = state.arena.data.get('lobby') or {}
    if not lobby.get('nonce'):
        return {'status': 'none'}
    paths = [save_file('cs2_last.json')]
    if cfg.get('csgo_path'):
        plugin = launch.plugin_dir(Path(cfg['csgo_path']))
        paths = [plugin / 'match_result.json', plugin / 'match_result.best.json', *paths]
    candidates = [launch._load_result_file(p) for p in paths]
    return pick_better_result(*(r for r in candidates if r and r.get('request_nonce') == lobby['nonce']))


def _running_cs2():
    """Read-only sentinel: the original helper conflates failure and no process."""
    from cs2career.cs2 import launch
    result = launch._powershell("$career3dProcesses = @(Get-Process -Name cs2 -ErrorAction SilentlyContinue | Where-Object { $_.HandleCount -ne 0 }); 'ok:' + (($career3dProcesses | Select-Object -ExpandProperty Id) -join ',')")
    if not result.strip().startswith('ok:'):
        raise RuntimeError('无法核验 CS2 进程状态；请检查系统权限后重试，不会生成或覆盖开赛配置。')
    return bool(result.strip()[3:])


def ladder_status(state, check_running=True):
    return _arena_status(state, 'rank', check_running)


def custom_status(state, check_running=True):
    return {**_arena_status(state, 'custom', check_running), 'custom': custom_context(state)}


def _arena_status(state, mode, check_running=True):
    from cs2career.cs2.result import result_usable
    from tools.career3d_cs2_lifecycle import recovery_state
    arena, cfg = state.arena, read_cs2_config()
    config = config_status()
    lobby = arena.data.get('lobby') or {}
    live, process_error = getattr(state, '_3d_cs2_live', None), ''
    if check_running:
        try:
            live = _running_cs2()
        except (OSError, RuntimeError) as exc:
            live, process_error = None, str(exc)
        state._3d_cs2_live = live
    phase, lid = lobby.get('phase', ''), lobby.get('id', '')
    failure = state.career.incident_state.get('career3d_service', {}).get('custom_failure' if mode == 'custom' else 'ladder_failure') or {}
    failure = failure if failure.get('lobby_id') == lid else {}
    reason, status, result_ready = '', 'idle', False
    recovery = recovery_state(None, live)
    if not lobby:
        reason = '尚未开始匹配。'
    elif lobby.get('mode') != mode:
        status, reason = 'blocked', '另一个模式占用了共享对战房间，请先完成或关闭原房间。'
    elif phase == 'finished':
        status, reason = 'collected', '本场真实战绩已录入。' if (lobby.get('result') or {}).get('map', {}).get('source') == 'cs2' else '这是以前保存的模拟报告。'
    elif phase in ('starting', 'launched'):
        raw = _peek_ladder_result(state, cfg) if check_running else {'status': 'none'}
        if live is True:
            state._3d_cs2_seen_nonce = lobby.get('nonce')
        seen = bool(lobby.get('nonce') and (getattr(state, '_3d_cs2_seen_nonce', None) == lobby.get('nonce') or
                raw.get('status') == 'in_progress' and raw.get('request_nonce') == lobby.get('nonce')))
        error = result_usable(raw, {'nonce': lobby.get('nonce'), 'map': lobby.get('map'),
            'started_at': lobby.get('started_at'), 'expected_player_ids': list(lobby.get('roster', {}))})
        result_ready = not error and raw.get('map') == 'de_' + lobby.get('map', '') and bool(raw.get('ended_at'))
        status = 'failed' if failure else 'waiting'
        reason = failure.get('reason') or ('真实十人战绩已回传，请录入。' if result_ready else error or '等待当前天梯比赛回传。')
        recovery = recovery_state({k: v for k, v in lobby.items()
            if not failure or k not in ('started_at', 'launch_requested_at')}, live, result_ready, seen_running=seen)
        if recovery['status'] != 'waiting':
            status, reason = recovery['status'], recovery['reason']
    elif live:
        status, reason = 'blocked', 'CS2 正在运行；请完全退出后再开新天梯，当前配置不会覆盖。'
    elif live is None and phase == 'ready':
        status, reason = 'blocked', process_error or '尚未核验 CS2 进程状态，请刷新天梯连接状态。'
    elif phase == 'ready':
        status, reason = ('ready', '阵容与地图已锁定，可以进入 CS2。') if config['ready'] else ('blocked', config['reason'])
    else:
        status, reason = phase, '请先完成选人、地图 BP 与选边。'
    return {'ok': True, 'status': status, 'reason': reason, 'lobby_id': lid, 'revision': arena.data['revision'],
            'phase': phase, 'cs2_running': live, 'process_known': live is not None, 'process_reason': process_error,
            'config': config, 'result_ready': result_ready,
            'can_launch': phase == 'ready' and lobby.get('mode') == mode and config['ready'] and live is False,
            'can_collect': phase in ('starting', 'launched') and lobby.get('mode') == mode,
            'can_retry': phase == 'starting' and lobby.get('mode') == mode and bool(failure) and config['ready'] and live is False,
            'can_resume': lobby.get('mode') == mode and bool(lobby.get('nonce')) and recovery['can_resume'] and config['ready'],
            'can_simulate': lobby.get('mode') == mode and bool(lobby.get('nonce')) and recovery['can_switch'],
            'can_rts': lobby.get('mode') == mode and bool(lobby.get('nonce')) and recovery['can_switch'],
            'launch_grace': recovery['launch_grace'],
            'can_cancel': bool(lobby) and lobby.get('mode') == mode and (phase not in ('starting', 'launched') or live is False),
            'result': _public_report(lobby['result']) if lobby.get('result') else None}


def recover_arena_cs2(state, body, mode, execution):
    """Return to the frozen room after exit, or ingest a winning result race."""
    from cs2career.cs2.result import result_usable
    from tools.career3d_cs2_lifecycle import recovery_state, retire_session
    arena = state.arena
    lobby = arena.data.get('lobby') or {}
    if lobby.get('mode') != mode or lobby.get('id') != body.get('lobby_id'):
        raise ValueError('当前对局房间身份已变化，请刷新。')
    if lobby.get('phase') not in ('starting', 'launched'):
        return None
    arena._guard(body.get('revision'))
    if not lobby.get('nonce') or len(lobby.get('roster') or {}) != 10:
        raise ValueError('原房间请求身份不完整，不能覆盖待回传比赛。')
    live = _running_cs2()
    state._3d_cs2_live = live
    cfg = read_cs2_config()
    raw = _peek_ladder_result(state, cfg)
    expected = dict(nonce=lobby['nonce'], map=lobby['map'], started_at=lobby.get('started_at'),
                    expected_player_ids=list(lobby['roster']))
    ready = not result_usable(raw, expected) and raw.get('ended_at') and raw.get('map') == 'de_' + lobby['map']
    if ready:
        message = arena.ingest(body, raw)
        return dict(status='collected', reason=message,
                    result=_public_report(arena.data['lobby']['result']))
    failure_key = 'custom_failure' if mode == 'custom' else 'ladder_failure'
    failure = state.career.incident_state.get('career3d_service', {}).get(failure_key) or {}
    failed = failure.get('lobby_id') == lobby['id']
    seen = (getattr(state, '_3d_cs2_seen_nonce', None) == lobby.get('nonce') or
            raw.get('status') == 'in_progress' and raw.get('request_nonce') == lobby.get('nonce'))
    recovery = recovery_state({k: v for k, v in lobby.items()
        if not failed or k not in ('started_at', 'launch_requested_at')}, live, seen_running=seen)
    if not recovery['can_resume']:
        raise ValueError(recovery['reason'])
    if cfg.get('csgo_path'):
        from cs2career.cs2 import launch
        launch.deactivate_match_request(Path(cfg['csgo_path']), lobby['nonce'])
    retire_session(lobby, {key: deepcopy(lobby[key]) for key in
        ('nonce', 'started_at', 'launch_requested_at', 'request') if key in lobby}, execution)
    for key in ('nonce', 'started_at', 'launch_requested_at', 'request'):
        lobby.pop(key, None)
    lobby['phase'] = 'ready'
    lobby['career3d_recovering'] = True
    # The subsequent launch/simulation/RTS operation commits once. Do not bump
    # its revision here or it would invalidate the user's very same request.
    return None


def _require_existing_plugin(csgo, name):
    from cs2career.cs2 import launch
    root = launch.plugin_dir(Path(csgo)) if name == 'CareerMatch' else Path(csgo) / 'addons' / 'counterstrikesharp' / 'plugins' / name
    if not all((root / file).is_file() for file in (name + '.dll', name + '.deps.json')):
        raise ValueError('现有 ' + name + ' 组件缺失；3D 样板不安装或替换插件。')
    return 0


def ladder_cs2_command(state, action, body):
    return _arena_cs2_command(state, action, body, 'rank')


def _arena_cs2_command(state, action, body, mode):
    from cs2career.cs2 import launch
    from cs2career.career import skins
    arena, c = state.arena, state.career
    lobby = arena.data.get('lobby')
    if not lobby or lobby.get('mode') != mode or lobby['id'] != body.get('lobby_id'):
        raise ValueError('当前对局房间身份已变化，请刷新。')
    if mode == 'rank':
        arena.require_rank_identity(state)
    failure_key = 'custom_failure' if mode == 'custom' else 'ladder_failure'
    def connection(current):
        return _arena_status(current, mode)
    store = c.incident_state.setdefault('career3d_service', {'revision': 0, 'receipts': []})
    if action == 'collect':
        if lobby['phase'] == 'finished':
            return {'reason': '这场已录入，不重复保存或计分。', 'status': 'collected', 'result': _public_report(lobby['result']), 'replayed': True}
        arena._guard(body.get('revision'))
        try:
            message = arena.ingest(body)
        except ValueError as exc:
            return {'reason': str(exc), 'status': 'waiting', 'connection': connection(state), 'replayed': True}
        store.pop(failure_key, None)
        return {'reason': message, 'status': 'collected', 'result': _public_report(arena.data['lobby']['result'])}
    arena._guard(body.get('revision'))
    if action != 'launch' or lobby['phase'] not in ('ready', 'starting', 'launched'):
        raise ValueError('房间尚未准备好，或已有比赛等待回传。')
    if lobby['phase'] in ('starting', 'launched'):
        recovered = recover_arena_cs2(state, body, mode, 'cs2')
        if recovered:
            return recovered
    if _running_cs2() is not False:
        raise ValueError('CS2 正在运行；请完全退出后再开新对局，当前配置不会覆盖。')
    launch.require_cs2_closed('启动新的 3D 自定义对局' if mode == 'custom' else '启动新的 3D 天梯比赛')
    config = config_status()
    if not config['ready']:
        raise ValueError(config['reason'])
    cfg = read_cs2_config()
    wanted = body.get('difficulty', cfg['difficulty'])
    if wanted not in launch.DIFFICULTIES:
        raise ValueError('请选择原有难度 Low、Medium 或 High。')
    if (lobby['phase'] == 'starting' or lobby.get('career3d_recovering')) and lobby.get('3d_settings'):
        cfg = deepcopy(lobby['3d_settings'])
        if 'difficulty' in body and wanted != cfg['difficulty']:
            raise ValueError('重试必须沿用这场已冻结的难度。')
    else:
        cfg['difficulty'] = wanted
        lobby['3d_settings'] = deepcopy(cfg)
        lobby['3d_cosmetics'] = {key: deepcopy(getattr(c, key)) for key in
            ('inventory', 'equipped_ct', 'equipped_t', 'steam_id', 'real_skins')}
    cosmetics = deepcopy(c)
    for key, value in lobby['3d_cosmetics'].items():
        setattr(cosmetics, key, deepcopy(value))
    start = launch.start_match
    def start_with_cosmetics(*args, **kwargs):
        kwargs['career'] = cosmetics
        return start(*args, **kwargs)
    def installed_skins(csgo, career=None):
        return launch.prepare_existing_skins(Path(csgo), career, cfg)
    # Keep the original game preparation, request, profiles and result importer.
    # Only plugin installation is disabled and the isolated cosmetics supplied.
    try:
        with _scoped_calls([(launch, 'settings', lambda: deepcopy(cfg)),
            (launch, 'start_match', start_with_cosmetics),
            (launch, '_copy_career_match', lambda csgo, _mod=None: _require_existing_plugin(csgo, 'CareerMatch')),
            (launch, '_copy_botbuy_patch', lambda csgo: _require_existing_plugin(csgo, 'BotBuy')),
            (launch, 'install_skins_plugin', installed_skins)]):
            message = arena.launch(state, body)
    except (ValueError, OSError, RuntimeError) as exc:
        store[failure_key] = {'lobby_id': lobby['id'], 'reason': str(exc)}
        state.persist()
        return {'reason': str(exc), 'status': 'failed', 'connection': connection(state)}
    store.pop(failure_key, None)
    from tools.career3d_cs2_lifecycle import utc_stamp
    lobby['launch_requested_at'] = utc_stamp()
    restarted = bool(lobby.pop('career3d_recovering', False))
    # Only the independent preferences are updated; never write original cs2.json.
    launch.SETTINGS_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'reason': message, 'status': 'waiting', 'connection': connection(state), 'restarted_map': restarted}


def scrim_command(state, action, body):
    from cs2career.arena import MAPS
    career, season = state.career, state.season
    if career.training_session:
        raise ValueError('训练对局尚未完成，请先录入或取消训练。')
    team = career.my_team(season.teams)
    if not team or len(team.get('players', [])) != 5 or career.over():
        raise ValueError('有完整阵容后才能约训练赛')
    store = career.incident_state.setdefault('career3d_service', {'revision': 0, 'receipts': []})
    records = store.setdefault('scrims', [])
    if action == 'schedule':
        opponent = next((t for t in season.teams if t['id'] == body.get('opponent_id')), None)
        if not opponent or opponent['id'] == team['id'] or len(opponent.get('players', [])) != 5:
            raise ValueError('请选择另一支完整队伍')
        day = str(body.get('date', ''))
        try:
            day = date.fromisoformat(day).isoformat()
        except ValueError:
            raise ValueError('请选择训练赛日期') from None
        if day < season.date:
            raise ValueError('这个日期已经过去了')
        if any(r['date'] == day for r in records):
            raise ValueError('当天已经约了一场训练赛')
        map_name = body.get('map', 'dust2')
        if map_name not in MAPS:
            raise ValueError('请选择地图')
        row = dict(id=uuid4().hex, opponent_id=opponent['id'], opponent=opponent['name'],
                   date=day, map=map_name, status='scheduled')
        records.append(row)
        return {'reason': '训练赛约好了。'}
    if action != 'simulate':
        raise ValueError('没有这个训练赛操作')
    row = next((r for r in records if r['id'] == body.get('id')), None)
    if not row:
        raise ValueError('这场训练赛不存在')
    if row['status'] == 'finished':
        return {'reason': '训练赛已结束。', 'report': deepcopy(row['report']), 'replayed': True}
    if row['date'] > season.date:
        raise ValueError('还没到约定日期')
    opponent = next((t for t in season.teams if t['id'] == row['opponent_id']), None)
    if not opponent or opponent['id'] == team['id']:
        raise ValueError('对手阵容已变化，请重新约赛')
    mp = _simulate(team, opponent, row['map'], row['id'])
    report = dict(id=row['id'], date=season.date, source='simulated', map=mp,
                  teams=[team['name'], opponent['name']], human_id=state.arena.career_player_id(state))
    row.update(status='finished', report=report)
    # Bounded report history; pending agreements remain intact.
    done = [r['id'] for r in records if r['status'] == 'finished'][:-20]
    records[:] = [r for r in records if r['id'] not in done]
    return {'reason': '训练赛已结束。', 'report': deepcopy(report)}
