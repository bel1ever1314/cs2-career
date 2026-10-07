"""Career devices reuse ordinary series, season runner and pure tactic APIs.

The HTTP owner holds ApplicationState's shared lock and persists mutations.
GET projections never open a veto, enqueue a story or collect a game result.
"""
from copy import deepcopy
import hashlib
from pathlib import Path


def _store(state):
    return state.career.incident_state.setdefault('career3d_service', {'revision': 0, 'receipts': []})


def _revision(state):
    return int(state.career.incident_state.get('career3d_service', {}).get('revision', 0))


def career_cs2_pending(state):
    return any((m.get('cs2_session') or m.get('career3d_rts')) and not m.get('played')
               for ev in state.season.events for m in ev.get('matches', []))


def _guard(state, body, optional=False):
    if optional and 'revision' not in body:
        return
    if type(body.get('revision')) is not int or body['revision'] != _revision(state):
        raise ValueError('生涯状态已变化，请刷新后再操作。')


def _pair(state, ident='', require=False):
    from cs2career.services.match_queries import player_matches as _player_matches
    pair = state.season.find_match(ident) if ident else next(iter(_player_matches(state)), None)
    if not pair or not pair[0]:
        if require:
            raise ValueError('没有找到当前赛季的这场比赛。')
        return None, None
    return pair


def _reason(state, match=None, ignore_session=False):
    from cs2career.career import incidents
    c, s = state.career, state.season
    if c.training_session:
        return '训练对局尚未完成，请先录入或取消训练。'
    if state.arena.pending:
        return '天梯比赛正在启动或等待真实回传，请先完成该场比赛。'
    if c.over():
        return '这段生涯已经结束。'
    if c.unsigned:
        return '当前是自由身，请先决定新的队伍。'
    if c.loan_default_pending or c.fix_pending or c.personal_transfers.get('pending'):
        return '请先处理待决定的生涯事务。'
    if c.story_queue or incidents.pending(c):
        return '有新事件，请先由你作出选择。'
    if incidents.competition_paused(c, s.date):
        return '当前暂停参赛，请先处理赛程。'
    for ev in s.events:
        for m in ev.get('matches', []):
            if not m.get('played') and m.get('career3d_rts'):
                return '有职业 RTS 对局尚未录入，请先完成或取消该地图。'
            if not m.get('played') and m.get('cs2_session') and (not ignore_session or m is not match):
                return '有职业比赛等待真实 CS2 回传，请先录入。'
    return ''


def _identity(state, match):
    c, s = state.career, state.season
    match.setdefault('career3d_identity', {'player_id': (c.my_player(s.teams) or {}).get('player_id', ''),
        'player_name': c.player_name, 'player_team': s.your_team_name()})
    if not match.get('career3d_venue'):
        from cs2career.services.venues import venue_for
        event, _ = s.find_match(match['id'])
        if event:
            match['career3d_venue'] = venue_for(state, event, match)


def _veto_public(state, match):
    from cs2career.world import MAPS
    veto = deepcopy(match.get('veto') or {})
    steps, order = veto.get('steps', []), veto.get('order', [])
    available = [m for m in MAPS if m not in {row['map'] for row in steps}]
    manual = match.get('career3d_veto') or {}
    plan = manual.get('plan') or []
    turn = plan[len(steps)] if len(steps) < len(plan) else None
    complete = bool(order and (not manual or manual.get('complete')))
    if turn:
        turn = {**turn, 'mine': turn.get('team') == state.season.your_team_name()}
    return {**veto, 'steps': steps, 'order': order, 'available': available,
        'turn': turn, 'complete': complete, 'initialized': bool(match.get('veto'))}


def series_maps(state, match):
    """Every map of the series in play order, so the UI never has to guess.

    state: done / live (a CS2 map is waiting for its result) / next / upcoming /
    unneeded (the series was decided before this map).
    """
    from cs2career.cs2.result import to_cs2_map
    veto = match.get('veto') or {}
    order = list(veto.get('order') or [])
    if not order or (match.get('career3d_veto') and not _veto_public(state, match)['complete']):
        return []
    steps = {row.get('map'): row for row in veto.get('steps') or [] if row.get('action') in ('pick', 'decider')}
    played = list(match.get('maps') or [])
    session = match.get('cs2_session') or {}
    need = int(match.get('best_of', 3)) // 2 + 1
    wins = {}
    for box in played:
        wins[box.get('winner')] = wins.get(box.get('winner'), 0) + 1
    decided = bool(match.get('played')) or (max(wins.values()) if wins else 0) >= need
    own = state.season.your_team_name()
    rows = []
    for index, name in enumerate(order):
        step = steps.get(name, {})
        row = {'index': index + 1, 'map': name, 'cs2_map': to_cs2_map(name),
               'picked_by': step.get('team') or '', 'decider': step.get('action') == 'decider'}
        if index < len(played):
            box = played[index]
            score = str(box.get('score', ''))
            parts = score.split('-')
            if own and own == match.get('team_b') and len(parts) == 2:
                score = parts[1] + '-' + parts[0]  # always "your rounds - their rounds"
            row.update(state='done', score=score, winner=box.get('winner', ''),
                       won=box.get('winner') == own)
        elif decided:
            row['state'] = 'unneeded'
        elif index == len(played):
            live = bool(session) and session.get('map_index') == index
            row['state'] = 'live' if live else 'next'
            if live:
                row['side'] = session.get('side', 'ct')
        else:
            row['state'] = 'upcoming'
        rows.append(row)
    return rows


def match_preflight(state, ident='', check_running=False):
    from .career_pace import map_key
    from cs2career.services.activities import config_status
    ev, match = _pair(state, ident)
    if not match:
        return {'match_id': '', 'phase': 'none', 'can_simulate': False, 'can_launch': False,
            'session_pending': career_cs2_pending(state),
            'block_reason': '目前没有到期的职业比赛。', 'config': config_status()}
    s = state.season
    yours, played = s.is_yours(match), bool(match.get('played'))
    due = bool(yours and match['date'] <= s.date and s.yours_ready(match))
    veto = _veto_public(state, match)
    reason = _reason(state, match)
    if not yours:
        reason = '这不是你当前队伍的比赛。'
    elif not due and not played:
        reason = '还没到比赛日。'
    phase = 'finished' if played else 'launched' if match.get('cs2_session') else 'scheduled' if match['date'] > s.date else \
        'ready' if veto['complete'] else 'veto' if veto['initialized'] else 'preflight'
    config = config_status()
    from cs2career.services.venues import venue_for, attendance_for
    from cs2career.world.map_form import public as map_performance
    performances = {t['name']: map_performance(t) for t in s.teams if t['name'] in (match['team_a'], match['team_b'])}
    venue = venue_for(state, ev, match)
    return {'match_id': match['id'], 'event': {'id': ev['id'], 'name': ev['name']},
        'identity': {'year': s.year, 'event_id': f'{s.year}:{ev["id"]}', 'match_id': match['id'],
                     'key': f'{s.year}:{ev["id"]}:{match["id"]}', 'human_id': venue['human_id']},
        'venue': venue, 'attendance': attendance_for(state, ev, match, venue),
        'team_a': match['team_a'], 'team_b': match['team_b'], 'date': match['date'],
        'map_performance': performances,
        'best_of': match.get('best_of', 3), 'stage': match.get('stage', ''), 'series': s._live_series(match),
        'yours': yours, 'due': due, 'played': played, 'phase': phase, 'veto': veto,
        'pending_map': match.get('pending_map'), 'maps_done': len(match.get('maps') or []),
        'map_key': map_key(state, ev, match),
        'side': (match.get('cs2_session') or match.get('career3d_launch') or {}).get('side', 'ct'),
        'series_maps': series_maps(state, match),
        'session_pending': career_cs2_pending(state),
        'revision': _revision(state), 'can_simulate': due and not reason and not played,
        'can_launch': due and not played and not reason and phase == 'ready' and config['ready'],
        'block_reason': reason, 'config': config}


def _session_return_preflight(state, event, match):
    """Read the original match seat, never prepare or restart its CS2 map."""
    session = match.get('cs2_session')
    if (not isinstance(session, dict) or not session or match.get('played')
            or match['date'] != state.season.date or not state.season.is_yours(match)
            or session.get('match_id') != match['id']
            or not isinstance(session.get('nonce'), str) or not session['nonce']
            or type(session.get('map_index')) is not int
            or session['map_index'] != len(match.get('maps') or [])):
        return None
    frozen = match.get('career3d_venue')
    if not isinstance(frozen, dict) or not frozen:
        return None
    view = match_preflight(state, match['id'])
    venue, attendance = view['venue'], view['attendance']
    key = f'{state.season.year}:{event["id"]}:{match["id"]}'
    if (not attendance['can_return'] or venue.get('identity_source') != 'frozen_match_rosters'
            or venue.get('match_id') != match['id'] or venue.get('match_identity') != key
            or venue.get('team_a') != match['team_a'] or venue.get('team_b') != match['team_b']
            or venue.get('own_team') != state.season.your_team_name()
            or venue.get('human_id') != state.arena.career_player_id(state)):
        return None
    a, b = venue.get('players_a'), venue.get('players_b')
    if not isinstance(a, list) or not isinstance(b, list) or len(a) != 5 or len(b) != 5:
        return None
    if not all(isinstance(row, dict) for row in a + b):
        return None
    ids = [row.get('id') for row in a + b]
    expected = session.get('expected_player_ids')
    if (not all(isinstance(ident, str) and ident for ident in ids) or len(set(ids)) != 10
            or any(row.get('player_id', row['id']) != row['id'] for row in a + b)
            or venue['human_id'] not in ids or not isinstance(expected, list) or len(expected) != 10
            or not all(isinstance(ident, str) and ident for ident in expected)
            or set(expected) != set(ids)):
        return None
    # Original core sessions can predate the 3D provenance fields. When those
    # fields exist, they must still identify this exact frozen fixture/roster.
    identity = session.get('career_identity')
    if identity is not None and (not isinstance(identity, dict) or any(
            identity.get(field) != value for field, value in dict(year=state.season.year,
            event_id=event['id'], match_id=match['id'], key=key, human_id=venue['human_id']).items())):
        return None
    original = session.get('venue')
    if original is not None and (not isinstance(original, dict) or any(
            original.get(field) != venue.get(field)
            for field in ('players_a', 'players_b', 'human_id', 'own_team', 'match_id', 'match_identity'))):
        return None
    return view


def _report(state, ev, match):
    from cs2career.career.quick_report import series_report
    if match.get('played') and match.get('career3d_result'):
        return deepcopy(match['career3d_result'])
    frozen = match.get('career3d_identity') or {}
    identity = {'player_id': frozen.get('player_id', (state.career.my_player(state.season.teams) or {}).get('player_id', '')),
        'player_team': frozen.get('player_team', state.season.your_team_name())}
    maps = []
    from cs2career.presentation import measured
    for index, saved in enumerate(match.get('maps') or []):
        row = deepcopy(saved)
        row.pop('events', None)
        grouped = row.get('players') or {}
        lines = [p for rows in grouped.values() for p in rows]
        row['data_complete'] = bool(len(lines) == 10 and all(p.get('player_id') for p in lines)
            and len({p.get('player_id') for p in lines}) == 10
            and all(len(grouped.get(team, [])) == 5 for team in (match['team_a'], match['team_b']))
            and all(measured(p, row.get('rounds')) for p in lines))
        maps.append({'index': index, **row})
    sources = {m.get('source') for m in maps}
    source = ('cs2' if sources == {'cs2'} else 'rts' if sources == {'rts'} else
              'mixed' if ('cs2' in sources or 'rts' in sources) else 'simulated')
    return {'id': match['id'], 'match_id': match['id'], 'result_id': f'{state.season.year}:{ev["id"]}:{match["id"]}',
        'date': match.get('date', state.season.date), 'event': ev['name'],
        'team_a': match['team_a'], 'team_b': match['team_b'], 'best_of': match.get('best_of', 3),
        'series': state.season._live_series(match), 'source': source, 'maps': maps,
        **series_report(match, **identity)}


def _result_response(state, ev, match, reason='已读取保存的战绩。', start=0):
    from cs2career.league.spectator import reveal_series
    from cs2career.career.quick_report import round_report
    reveal = reveal_series(match, start)
    for row in reveal['maps']:
        row.update(round_report(match['maps'][row['index']], reveal['teams'], row['rounds']))
    return {'reason': reason, 'status': 'finished' if match.get('played') else 'paused',
        'result': _report(state, ev, match), 'reveal': reveal,
        'preflight': match_preflight(state, match['id'])}


def _init_veto(state, ev, match):
    from cs2career.engine.match import veto_maps
    from cs2career.world import MAPS
    s = state.season
    if match.get('career3d_veto') or match.get('maps') or match.get('cs2_session'):
        return
    a = next(t for t in s.teams if t['name'] == match['team_a'])
    b = next(t for t in s.teams if t['name'] == match['team_b'])
    template = veto_maps(a, b, MAPS, match.get('best_of', 3))
    # Core opening freezes ranks/human identity; manual BP replaces only its
    # generated map choice before any map is played.
    s.open_your_series(ev, match)
    match['veto'] = {'steps': [], 'order': [], 'best_of': match.get('best_of', 3)}
    match['pending_map'] = None
    match['career3d_veto'] = {'plan': [{k: r[k] for k in ('team', 'action')} for r in template['steps']], 'complete': False}
    _advance_veto(state, match)


def _choose_veto(state, match, choice):
    row = _veto_public(state, match)
    turn = row['turn']
    if not turn or choice not in row['available']:
        raise ValueError('地图或 BP 轮次已变化，请刷新。')
    veto = match['veto']
    step = {k: turn[k] for k in ('team', 'action')}
    step['map'] = choice
    if turn['action'] in ('pick', 'decider'):
        veto['order'].append(choice)
        step['play'] = len(veto['order'])
    veto['steps'].append(step)
    if len(veto['steps']) == len(match['career3d_veto']['plan']):
        match['career3d_veto']['complete'] = True
        state.season.open_your_series(*state.season.find_match(match['id']))


def _advance_veto(state, match, all_turns=False):
    from cs2career.engine.match import _ban_value, _pick_value
    by_name = {t['name']: t for t in state.season.teams}
    while not _veto_public(state, match)['complete']:
        veto = _veto_public(state, match)
        turn = veto['turn']
        if not turn or (turn['mine'] and not all_turns):
            break
        available = veto['available']
        if turn['action'] == 'decider':
            choice = available[0]
        else:
            team = by_name[turn['team']]
            opponent = by_name[match['team_b'] if turn['team'] == match['team_a'] else match['team_a']]
            value = _ban_value if turn['action'] == 'ban' else _pick_value
            choice = max(available, key=lambda name: value(team, opponent, name))
        _choose_veto(state, match, choice)


def _peek(state, match, cfg):
    from cs2career.cs2 import launch
    from cs2career.cs2.result import pick_better_result
    from cs2career.paths import save_file
    session = match.get('cs2_session') or {}
    if not session.get('nonce'):
        return {'status': 'none'}
    paths = [save_file('cs2_last.json')]
    if cfg.get('csgo_path'):
        plugin = launch.plugin_dir(Path(cfg['csgo_path']))
        paths = [plugin / 'match_result.json', plugin / 'match_result.best.json', *paths]
    raw = [launch._load_result_file(path) for path in paths]
    return pick_better_result(*(r for r in raw if r and r.get('request_nonce') == session['nonce']))


def match_status(state, ident='', check_running=True):
    from cs2career.services.activities import read_cs2_config, _running_cs2
    from cs2career.services.match_recovery import recovery_state
    from cs2career.cs2.result import result_usable
    ev, match = _pair(state, ident)
    preflight = match_preflight(state, ident)
    live, error = getattr(state, '_3d_cs2_live', None), ''
    if check_running:
        try:
            live = _running_cs2()
        except (OSError, RuntimeError) as exc:
            live, error = None, str(exc)
        state._3d_cs2_live = live
    session = (match or {}).get('cs2_session') or {}
    raw = _peek(state, match, read_cs2_config()) if session else {'status': 'none'}
    if session and live is True:
        state._3d_cs2_seen_nonce = session.get('nonce')
    seen = bool(session and (getattr(state, '_3d_cs2_seen_nonce', None) == session.get('nonce') or
        raw.get('status') == 'in_progress' and raw.get('request_nonce') == session.get('nonce')))
    result_error = result_usable(raw, session) if session else ''
    ready = bool(session and not result_error and raw.get('ended_at')
        and raw.get('map') == session.get('cs2_map'))
    recovery = recovery_state(session, live, ready, seen_running=seen)
    resumable = bool(recovery['can_resume'] and match and _session_return_preflight(state, ev, match)
                     and not _reason(state, match, ignore_session=True))
    switchable = resumable
    failure = state.career.incident_state.get('career3d_service', {}).get('match_failure') or {}
    failure = failure if failure.get('match_id') == (match or {}).get('id') else {}
    status = 'collected' if (match or {}).get('played') else 'waiting' if session else 'failed' if failure else preflight['phase']
    reason = ('真实十人战绩已回传，请录入。' if ready else result_error) if session else \
        failure.get('reason') or preflight.get('block_reason') or preflight.get('config', {}).get('reason', '')
    can_launch = bool(preflight.get('can_launch') and live is False and not session)
    if session and recovery['status'] != 'waiting':
        status, reason = recovery['status'], recovery['reason']
    flags = dict(can_resume=resumable, can_simulate=bool(switchable), can_rts=bool(switchable),
                 launch_grace=recovery['launch_grace'])
    preflight.update(flags)
    if not session and not (match or {}).get('played') and live is not False:
        reason = error or 'CS2 正在运行，请完全退出后再开下一张地图。' if live else error or '请刷新连接状态以核验 CS2 进程。'
    return {'ok': True, 'match_id': (match or {}).get('id', ''), 'status': status, 'reason': reason,
        'phase': preflight['phase'], 'revision': _revision(state), 'preflight': preflight,
        'cs2_running': live, 'process_known': live is not None, 'process_reason': error,
        'result_ready': ready, 'can_launch': can_launch, 'can_collect': bool(session),
        'can_retry': bool(failure and can_launch),
        **flags,
        'result': _report(state, ev, match) if match and match.get('maps') else None}


def recover_cs2_map(state, event, match, mode, *, retire_request=None):
    """Explicit POST recovery, under the service's lock; GET never resets it.

    A just-finished dump wins the race against changing the execution mode.
    Retiring an unfinished request preserves the BO series and its fixed BP.
    A subsequently arriving old-nonce dump cannot settle the replacement map.
    """
    from cs2career.services.activities import _running_cs2, read_cs2_config
    from cs2career.services.match_recovery import recovery_state, retire_session
    from cs2career.cs2.result import result_usable
    session = match.get('cs2_session')
    if not session:
        return None
    if _session_return_preflight(state, event, match) is None:
        raise ValueError('原比赛身份或阵容已变化，请刷新当前比赛，不能覆盖待回传地图。')
    # Query the process before the dump: shutdown can write the final result.
    live = _running_cs2()
    state._3d_cs2_live = live
    cfg = read_cs2_config()
    raw = _peek(state, match, cfg)
    ready = not result_usable(raw, session) and raw.get('ended_at') and raw.get('map') == session.get('cs2_map')
    if ready:
        start = len(match.get('maps') or [])
        message = state.season.commit_cs2_map(match['id'], raw,
            result_reader=lambda request_nonce=None: deepcopy(raw))
        out = _result_response(state, event, match, message, start)
        out['status'] = 'finished' if match.get('played') else 'map_collected'
        if match.get('played'):
            match['career3d_result'] = deepcopy(out['result'])
        return out
    seen = getattr(state, '_3d_cs2_seen_nonce', None) == session.get('nonce') or (
        raw.get('status') == 'in_progress' and raw.get('request_nonce') == session.get('nonce'))
    recovery = recovery_state(session, live, seen_running=seen)
    if not recovery['can_resume']:
        raise ValueError(recovery['reason'])
    reason = _reason(state, match, ignore_session=True)
    if reason:
        raise ValueError(reason)
    if cfg.get('csgo_path'):
        if retire_request is None:
            from .external_effects import retire
            retire(state, Path(cfg['csgo_path']), session['nonce'])
        else:
            retire_request(Path(cfg['csgo_path']), session['nonce'])
    retire_session(match, session, mode)
    match.pop('cs2_session', None)
    _store(state).pop('match_failure', None)
    return None


def _dispatch_launch(cfg, arguments, kwargs):
    """External adapter only: no career mutation or save transaction here."""
    from cs2career.cs2 import launch
    return launch.start_match(*arguments, **kwargs, config=cfg, existing_plugins=True)


def _launch(state, match, body, *, dispatch=None):
    from cs2career.cs2 import launch
    from cs2career.services.activities import _running_cs2, config_status, read_cs2_config
    if match.get('cs2_session'):
        return {'reason': '这张图已连接 CS2，等待原场回传。', 'status': 'waiting',
            'connection': match_status(state, match['id']), 'replayed': True}
    if _running_cs2():
        raise ValueError('CS2 正在运行，请完全退出后再开下一张地图。')
    launch.require_cs2_closed('启动 3D 职业比赛')
    config = config_status()
    if not config['ready']:
        raise ValueError(config['reason'])
    cfg = read_cs2_config()
    difficulty = body.get('difficulty', cfg['difficulty'])
    if difficulty not in launch.DIFFICULTIES:
        raise ValueError('请选择原有难度 Low、Medium 或 High。')
    side = body.get('side', 'ct')
    if side not in ('ct', 't'):
        raise ValueError('请选择 CT 或 T 开局。')
    cfg['difficulty'] = difficulty
    frozen = match.get('career3d_launch')
    index = len(match.get('maps') or [])
    if frozen and frozen['map_index'] == index:
        if ('difficulty' in body and difficulty != frozen['settings']['difficulty']) or side != frozen['side']:
            raise ValueError('重试必须沿用这张图冻结的难度与选边。')
        cfg = deepcopy(frozen['settings'])
    else:
        frozen = {'map_index': index, 'side': side, 'settings': deepcopy(cfg),
            'cosmetics': {key: deepcopy(getattr(state.career, key)) for key in
                ('inventory', 'equipped_ct', 'equipped_t', 'steam_id', 'real_skins')}}
        match['career3d_launch'] = frozen
    cosmetics = deepcopy(state.career)
    for key, value in frozen['cosmetics'].items():
        setattr(cosmetics, key, deepcopy(value))
    def start(*args, **kwargs):
        arguments = list(args)
        if len(arguments) > 6:
            arguments[6] = cosmetics
        else:
            kwargs['career'] = cosmetics
        ev, _ = state.season.find_match(match['id'])
        from cs2career.services.venues import venue_for
        venue = venue_for(state, ev, match)
        actual_ids = [player.get('player_id') for team in arguments[:2] for player in team.get('players', [])]
        frozen_ids = [player['id'] for player in venue['players_a'] + venue['players_b']]
        if (len(actual_ids) != 10 or not all(actual_ids) or len(set(actual_ids)) != 10
                or set(actual_ids) != set(frozen_ids) or venue['human_id'] not in actual_ids):
            raise ValueError('冻结比赛阵容的十人身份已变化，请刷新比赛准备；不会启动错误阵容。')
        # Keep the core nonce/identity importer. Add provenance to the actual
        # request before preparation instead of inventing another game route.
        request = launch.build_request(arguments[0], arguments[1], arguments[2], arguments[3], arguments[4])
        request['career_identity'] = dict(year=state.season.year, event_id=ev['id'], match_id=match['id'],
            key=venue['match_identity'], human_id=venue['human_id'])
        request['career_venue'] = deepcopy(venue)
        kwargs['request_override'] = request
        return (dispatch or _dispatch_launch)(cfg, arguments, kwargs)
    try:
        reason = state.season.launch_your_map(match['id'], side, launcher=start,
            result_reader=lambda request_nonce=None: _peek(state, match, cfg))
    except (ValueError, OSError, RuntimeError) as exc:
        _store(state)['match_failure'] = {'match_id': match['id'], 'reason': str(exc)}
        return {'reason': str(exc), 'status': 'paused' if state.career.story_queue else 'failed',
            'connection': match_status(state, match['id'])}
    _store(state).pop('match_failure', None)
    if match.get('cs2_session'):
        from cs2career.services.match_recovery import utc_stamp
        match['cs2_session']['launch_requested_at'] = utc_stamp()
        event = state.season.find_match(match['id'])[0]
        from cs2career.services.venues import venue_for
        venue = venue_for(state, event, match)
        event_id = event['id']
        match['cs2_session']['career_identity'] = dict(year=state.season.year, event_id=event_id,
            match_id=match['id'], key=venue['match_identity'],
            human_id=venue['human_id'])
        match['cs2_session']['event_id'] = event_id
        match['cs2_session']['venue'] = deepcopy(venue)
    return {'reason': reason, 'status': 'waiting', 'connection': match_status(state, match['id'])}


def match_command(state, action, body, *, launch_handler=None, retire_request=None, simulation_limit=None):
    from cs2career.storage.receipts import needs_legacy_receipt
    from cs2career.services.activities import read_cs2_config
    if not isinstance(body.get('match_id'), str) or not body['match_id']:
        raise ValueError('请提供明确的职业比赛 match_id。')
    ev, match = _pair(state, body['match_id'], True)
    if action not in ('attend', 'seated', 'preflight', 'veto', 'autoveto', 'simulate', 'launch', 'collect'):
        raise ValueError('没有这个职业比赛操作。')
    request_id = body.get('request_id')
    if request_id is not None and (not isinstance(request_id, str) or not 8 <= len(request_id) <= 100):
        raise ValueError('request_id 必须是 8 至 100 字符的唯一编号。')
    receipts = match.get('career3d_receipts') or []
    prior = next((r for r in receipts if r['request_id'] == request_id), None) if request_id else None
    if action == 'attend' and (match.get('played') or ev.get('status') == 'done'):
        raise ValueError('这场比赛已经结束，可以查看战报。')
    if prior:
        if prior['action'] != action:
            raise ValueError('这个 request_id 已用于另一个比赛操作。')
        if action == 'attend':
            from cs2career.services.venues import attendance_for
            attendance = attendance_for(state, ev, match)
            return dict(prior['result'], attendance=attendance,
                        preflight=match_preflight(state, match['id']), replayed=True)
        return {**deepcopy(prior['result']), 'replayed': True}
    if match.get('played') and action in ('simulate', 'collect'):
        return {**_result_response(state, ev, match), 'replayed': True}
    if action == 'collect' and not match.get('cs2_session') and match.get('maps') and match['maps'][-1].get('source') == 'cs2':
        return {**_result_response(state, ev, match), 'replayed': True}
    _guard(state, body, optional=action == 'simulate')
    if action in ('launch', 'simulate', 'preflight', 'veto', 'autoveto'):
        from .career_pace import guard_map
        guard_map(state, ev, match, body)
        if action in ('launch', 'simulate') and 'map_key' in body:
            from .career_pace import enable
            enable(state)
    recovered = False
    if action in ('launch', 'simulate') and match.get('cs2_session'):
        # Repeated launch while the process is alive still means the same game,
        # not a second prepare. A closed game has an explicit restart path.
        if action == 'launch':
            connection = match_status(state, match['id'])
            if not connection.get('can_resume') and not connection.get('result_ready'):
                return {'reason': connection.get('reason', '等待原场回传。'), 'status': connection.get('status', 'waiting'),
                        'connection': connection, 'replayed': True}
            body = dict(body)
            body.setdefault('side', match['cs2_session'].get('side', 'ct'))
        out = recover_cs2_map(state, ev, match, 'cs2' if action == 'launch' else 'simulate',
                              retire_request=retire_request)
        if out:
            if needs_legacy_receipt(request_id):
                match['career3d_receipts'] = (receipts + [{'request_id': request_id,
                    'action': action, 'result': deepcopy(out)}])[-12:]
            return out
        recovered = True
    if action == 'seated':
        if match.get('played') or not state.season.is_yours(match) or not state.season.yours_ready(match) or match['date'] > state.season.date:
            raise ValueError('当前比赛尚未到入座时间。')
        _identity(state, match)
        plan = match.setdefault('career3d_attendance', {})
        plan.update(mode='personal', match_identity=f'{state.season.year}:{ev["id"]}:{match["id"]}',
                    player_id=state.arena.career_player_id(state), seated=True)
        out = dict(reason='已记住本场席位，后续地图无需重新入场。', status='ready',
                   preflight=match_preflight(state, match['id']))
    elif action == 'attend':
        if not state.season.is_yours(match):
            raise ValueError('这不是你当前队伍的比赛。')
        if ev.get('status') not in ('live', 'upcoming'):
            raise ValueError('这场比赛还没有排进当前赛程。')
        if career_cs2_pending(state) or state.arena.pending or state.career.training_session:
            raise ValueError('先完成正在进行的对局，再安排下一场。')
        from cs2career.services.venues import attendance_for
        match['career3d_attendance'] = dict(mode='personal',
            match_identity=f'{state.season.year}:{ev["id"]}:{match["id"]}',
            player_id=state.arena.career_player_id(state))
        attendance = attendance_for(state, ev, match)
        out = dict(reason=attendance['instruction'], status='planned', attendance=attendance,
                   preflight=match_preflight(state, match['id']))
    elif action == 'collect':
        if not match.get('cs2_session'):
            raise ValueError('还没有进入这场真实比赛。')
        raw = body.get('result')
        if raw is not None and not isinstance(raw, dict):
            raise ValueError('result 必须是原始战绩对象。')
        start = len(match.get('maps') or [])
        try:
            message = state.season.commit_cs2_map(match['id'], raw,
                result_reader=lambda request_nonce=None: _peek(state, match, read_cs2_config()))
        except ValueError as exc:
            return {'reason': str(exc), 'status': 'waiting', 'connection': match_status(state, match['id']), 'replayed': True}
        _store(state).pop('match_failure', None)
        out = _result_response(state, ev, match, message, start)
        out['status'] = 'finished' if match.get('played') else 'map_collected'
    else:
        if match.get('played'):
            raise ValueError('这场比赛已经结束，可以查看战报。')
        if match['date'] > state.season.date:
            raise ValueError('还没到比赛日，先睡到 ' + match['date'] + '。')
        state.season._require_yours(match['id'])
        return_view = _session_return_preflight(state, ev, match) if action == 'preflight' else None
        reason = _reason(state, match, ignore_session=return_view is not None)
        if reason:
            return {'reason': reason, 'status': 'paused', 'preflight': match_preflight(state, match['id']), 'replayed': True}
        if return_view is not None:
            # The HTTP owner treats replayed as a no-persist response. Keep the
            # original session, nonce, BP, receipts and revision untouched;
            # waiting permits the existing UI's validated venue hand-off only.
            return {'reason': return_view['attendance']['instruction'], 'status': 'waiting',
                'preflight': return_view, 'read_only': True, 'resume_only': True, 'replayed': True}
        reason = state.career.gate_match(state.season, match['id'])
        if reason or state.career.story_queue:
            return {'reason': reason or '请先处理生涯事件。', 'status': 'paused', 'preflight': match_preflight(state, match['id'])}
        _identity(state, match)
        _init_veto(state, ev, match)
        if action in ('veto', 'autoveto'):
            if match.get('maps') or match.get('cs2_session') or _veto_public(state, match)['complete']:
                raise ValueError('本场地图已冻结，不能重新 BP。')
            if action == 'veto':
                if not (_veto_public(state, match)['turn'] or {}).get('mine'):
                    raise ValueError('还没轮到你的队伍选择地图。')
                _choose_veto(state, match, body.get('map'))
            _advance_veto(state, match, all_turns=action == 'autoveto')
        elif action == 'simulate':
            _advance_veto(state, match, all_turns=True)
            start = len(match.get('maps') or [])
            message = state.season.skip_your_series(match['id'],
                **({'max_maps': simulation_limit} if simulation_limit is not None else {}))
            out = _result_response(state, ev, match, message, start)
        elif action == 'launch':
            if not _veto_public(state, match)['complete']:
                raise ValueError('请先完成地图 BP，或选择自动 BP。')
            out = (launch_handler or _launch)(state, match, body)
            if recovered:
                out['restarted_map'] = True
                out['reason'] = '已保留完成地图，重新进入当前未结束地图。' + out.get('reason', '')
        if action in ('preflight', 'veto', 'autoveto'):
            out = {'reason': '比赛准备已保存。', 'status': 'ready' if _veto_public(state, match)['complete'] else 'veto',
                'preflight': match_preflight(state, match['id'])}
    if match.get('played'):
        match['career3d_result'] = _report(state, ev, match)
    if needs_legacy_receipt(request_id):
        match['career3d_receipts'] = (receipts + [{'request_id': request_id, 'action': action, 'result': deepcopy(out)}])[-12:]
    return out


def quick_context(state):
    from cs2career.career.fast_mode import season_mode
    from cs2career.career.story_timing import window
    c, s = state.career, state.season
    current = window(c, s)
    domain = season_mode(c, s)
    reason = _reason(state)
    from cs2career.services.match_queries import due_player_match as _due_player_match
    from cs2career.services.venues import attendance_for
    personal = _due_player_match(state)
    if not reason and personal and not c.assist.get('unified_pace') and attendance_for(state, *personal)['planned']:
        reason = attendance_for(state, *personal)['instruction']
    break_ack = bool(current and c.assist.get('quick_break_ack') == current['key'])
    phase = ('story' if c.story_queue else 'blocked') if reason else 'break' if current and not break_ack else \
        'choice' if domain['choice_required'] else domain['phase']
    return {**domain, 'season_phase': domain['phase'], 'phase': phase,
        'unified_pace': bool(c.assist.get('unified_pace')),
        'mode': 'quick' if c.assist.get('quick_mode') else 'normal',
        'revision': _revision(state), 'counter': int(c.assist.get('step_counter') or 0),
        'break_key': (current or {}).get('key', ''),
        'break_ack': break_ack, 'block_reason': reason}


def season_command(state, action, body, *, simulation_limit=None):
    from cs2career.storage.receipts import needs_legacy_receipt
    from cs2career.career.fast_mode import configure_season, step
    from cs2career.career.story_timing import window
    c, s = state.career, state.season
    rid = body.get('request_id')
    receipts = _store(state).get('season_receipts') or []
    prior = next((r for r in receipts if r['request_id'] == rid), None) if rid else None
    identity = {key: body.get(key) for key in ('year', 'quick_mode', 'max_steps', 'break_key')}
    if prior:
        if prior['action'] != action or prior['identity'] != identity:
            raise ValueError('这个请求编号已用于另一个赛季操作。')
        return {**deepcopy(prior['result']), 'replayed': True}
    _guard(state, body)
    if c.training_session:
        raise ValueError('训练对局尚未完成，请先录入或取消训练。')
    if state.arena.pending:
        raise ValueError('天梯比赛尚未完成，暂时不能推进赛季。')
    if action == 'unify':
        from .career_pace import enable
        enable(state)
        out = {'reason': '统一生涯节奏已启用。', 'status': 'saved'}
    elif action == 'next-year':
        from ..career.fast_mode import season_complete
        if body.get('year') != s.year or not season_complete(s):
            raise ValueError('请在本赛季结束后继续下一赛季。')
        configure_season(c, s, True, s.year)
        from .career_pace import enable
        enable(state)
        out = {'reason': '新赛季已开始。', 'status': 'saved'}
    elif action == 'mode':
        if c.assist.get('unified_pace'):
            raise ValueError('统一生涯按地图选择玩法，不再切换赛季模式。')
        if _reason(state):
            raise ValueError(_reason(state))
        configure_season(c, s, body.get('quick_mode'), body.get('year'))
        out = {'reason': '本赛季采用快速模式。' if body['quick_mode'] else '本赛季采用正常模式。', 'status': 'saved'}
    elif action == 'resume':
        current = window(c, s)
        if not current or body.get('break_key') != current['key']:
            raise ValueError('休赛窗口已变化，请刷新后继续。')
        if _reason(state):
            raise ValueError(_reason(state))
        c.assist['quick_break_ack'] = current['key']
        out = {'reason': '休赛期准备已确认，可以继续快速模拟。', 'status': 'saved'}
    elif action == 'run':
        if not isinstance(rid, str) or not 8 <= len(rid) <= 100:
            raise ValueError('request_id 必须是 8 至 100 字符的唯一编号。')
        count = body.get('max_steps', 1)
        if type(count) is not int or not 1 <= count <= 24:
            raise ValueError('max_steps 只允许 1 至 24。')
        latest, results, steps = {}, [], 0
        for index in range(count):
            from cs2career.services.match_queries import player_matches as _player_matches
            from cs2career.services.venues import attendance_for
            pair = next(iter(_player_matches(state)), None)
            personal = attendance_for(state, *pair) if pair else {}
            if personal.get('planned') and (personal.get('due') or pair[1].get('human') or pair[1].get('veto')):
                latest = dict(status='paused', msg=personal['instruction'])
                break
            token = '3d-run:' + hashlib.sha256(f'{rid}:{index}'.encode()).hexdigest()
            result = step(c, s, token, int(c.assist.get('step_counter') or 0),
                          **({'max_maps': simulation_limit} if simulation_limit is not None else {}))
            steps += 1
            latest = result
            if result.get('match'):
                ev, match = s.find_match(result['match']['id'])
                if match:
                    _identity(state, match)
                    report = _result_response(state, ev, match, result.get('msg', ''), result['match'].get('start', 0))
                    results.append(report)
                    if match.get('played'):
                        match['career3d_result'] = _report(state, ev, match)
            # Business persistence processes earned invitations and gates after
            # each ordinary command, exactly as the core UI's step requests.
            state.settle()
            if result.get('status') not in ('progress', 'played'):
                break
        out = {'reason': latest.get('msg', ''), 'status': latest.get('status', 'paused'),
            'steps': steps, 'auto_step': latest, 'results': results}
        if results:
            out.update({key: results[-1][key] for key in ('result', 'reveal')})
    else:
        raise ValueError('没有这个赛季操作。')
    out['quick'] = quick_context(state)
    if needs_legacy_receipt(rid):
        _store(state)['season_receipts'] = (receipts + [{'request_id': rid, 'action': action,
            'identity': identity, 'result': deepcopy(out)}])[-16:]
    return out


def ceremony_context(state, year=None):
    finalized = state.season.top20
    years = sorted(int(y) for y in finalized if str(y).isdigit())
    chosen = year if year is not None else years[-1] if years else None
    rows = deepcopy(finalized.get(str(chosen)) or [])
    # Historical awards may have no stable id. Resolve only an unambiguous
    # existing roster name; never manufacture a winner or transfer history.
    by_name = {}
    for team in state.season.teams:
        for player in team.get('players', []):
            by_name.setdefault(player['name'], []).append(player.get('player_id', ''))
    for row in rows:
        row['name'] = row.get('player', '')
        ids = by_name.get(row['name'], [])
        row['player_id'] = row.get('player_id') or (ids[0] if len(ids) == 1 else '')
    human = state.arena.career_player_id(state)
    rank = next((row.get('rank') for row in rows if row['player_id'] and row['player_id'] == human), None)
    exists = chosen is not None and str(chosen) in finalized
    ranks = {r['id']: r['rank'] for r in state.season.vrs.table(state.season.teams, state.season.date)}
    frontline = sorted((t for t in state.season.teams if ranks.get(t['id'], 999) <= 10),
                       key=lambda t: ranks[t['id']])
    attendees = [{'player_id': p.get('player_id', ''), 'name': p['name'], 'player': p['name'],
                  'team': t['name'], 'team_rank': ranks[t['id']], 'current_roster': True}
                 for t in frontline for p in t.get('players', [])]
    return {'ready': bool(exists and rows), 'finalized': exists, 'year': chosen, 'years': years,
        'top3': rows[:3], 'top20': deepcopy(rows), 'attendees': attendees, 'attendees_source': 'current_top10_rosters',
        'attendees_current': True, 'human_id': human, 'player_rank': rank,
        'source': 'season.top20', 'reason': '已读取年度正式归档榜单。' if rows else
            '年度已归档，但本年度没有达到评选样本要求的选手。' if exists else '尚无年度正式归档榜单；完成赛季并确认下一赛季后揭晓。'}


def _tactical_sessions(state):
    """Read current pending identities only; never resurrect an old game request."""
    if state is None:
        return []
    sessions = []
    training = getattr(state.career, 'training_session', None)
    if training:
        sessions.append(training)
    for event in getattr(state.season, 'events', []):
        for match in event.get('matches', []):
            if not match.get('played') and match.get('cs2_session'):
                sessions.append(match['cs2_session'])
    lobby = getattr(state.arena, 'data', {}).get('lobby') or {}
    if lobby.get('phase') in ('starting', 'launched') and lobby.get('nonce'):
        sessions.append(dict(nonce=lobby['nonce'], map=lobby.get('map'),
                             expected_player_ids=list(lobby.get('roster') or {})))
    return sessions


def _tactics_publication(state, code, sync=False):
    from cs2career.cs2 import launch
    from cs2career.services.activities import read_cs2_config
    try:
        cfg = read_cs2_config() if state is not None else {}
        csgo = launch.resolve_csgo_path(cfg['csgo_path']) if cfg.get('csgo_path') else None
        if sync and csgo and getattr(state, '_operation_depth', 0):
            from .external_effects import enqueue
            enqueue(state, 'publish_tactics', csgo, code)
            return dict(status='pending', can_sync=True, synced=False, pending=True, published_ids=[],
                        reason='战术已保存，正在同步到游戏目录。')
        return launch.tactical_publication(csgo, code, _tactical_sessions(state), sync=sync)
    except (OSError, ValueError, RuntimeError) as exc:
        return dict(status='unavailable', can_sync=False, synced=False, pending=True, published_ids=[],
                    reason='战术已保存；同步状态不可用：' + str(exc))


def tactics_context(map_code='de_dust2', state=None, publication=None):
    from cs2career import tactics
    from cs2career.paths import static_dir
    value = tactics.public_library(tactics.canonical_map(map_code))
    meta = value['map_meta']
    for row in [meta, *meta.get('layers', [])]:
        resource = str(row.get('image') or '')
        candidate = (static_dir() / resource.lstrip('/')).resolve()
        row['image_path'] = str(candidate) if candidate.is_file() else ''
    return {'ok': True, **value, 'publication': publication if publication is not None else _tactics_publication(state, value['map'])}


def tactics_command(state, action, body):
    from cs2career import tactics
    _guard(state, body)
    code = tactics.canonical_map(body.get('map', tactics.MAP))
    allowed = {'revision', 'request_id', 'map'} | ({'tactic'} if action == 'save' else {'id'} if action == 'delete' else set())
    if set(body) - allowed:
        raise ValueError('战术操作包含不允许的字段。')
    if action == 'save':
        result = tactics.save_tactic(body.get('tactic'), code)
    elif action == 'delete':
        result = tactics.delete_tactic(body.get('id'), code)
    elif action == 'sync':
        result = {'msg': ''}
    else:
        raise ValueError('没有这个战术操作。')
    publication = _tactics_publication(state, code, sync=True)
    prefix = {'save': '战术已保存到独立库。', 'delete': '战术已从独立库删除。'}.get(action, '')
    message = publication['reason']
    return {**tactics_context(code, state, publication), 'reason': message, 'msg': message, 'library_message': prefix,
        'status': 'synced' if publication.get('synced') else 'saved' if action != 'sync' else 'deferred',
        **({'replayed': True} if action == 'sync' else {}),  # service: no career revision/persist for publication-only.
        **{key: result[key] for key in ('tactic', 'deleted_id', 'overwritten_ids') if key in result}}
