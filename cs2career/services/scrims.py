"""Booked CS2 practices share the existing durable training handoff.

The booking owns its frozen roster and report; practice results do not settle
career tournament stats, prizes, ladder Elo or daily training rewards.
"""
from copy import deepcopy


def _records(state):
    return state.career.incident_state.get('career3d_service', {}).get('scrims', [])


def projection(state, records, opponents, config):
    from .controls import _busy
    session = state.career.training_session or {}
    reason = _busy(state, training=False)
    if session and not session.get('booking_id'):
        reason = '另有训练对局等待核验，请先到训练与成长页面完成或取消。'
    from .activities import _public_report
    scheduled = [{k: v for k, v in r.items() if k not in ('teams_snapshot', 'report')}
                 for r in records if r['status'] in ('scheduled', 'launched')]
    history = [{k: (_public_report(v) if k == 'report' else v) for k, v in r.items()
                if k != 'teams_snapshot'} for r in reversed(records) if r['status'] == 'finished'][:10]
    return dict(opponents=opponents, scheduled=scheduled, history=history,
                launch_ready=bool(config.get('ready')) and not reason,
                launch_reason=reason or ('' if config.get('ready') else config.get('reason', '请先完成 CS2 设置。')),
                pending={key: session.get(key, '') for key in ('booking_id', 'nonce', 'launch_state')})


def _session(state, row, body):
    session = state.career.training_session or {}
    if session.get('booking_id') != row['id'] or not session.get('nonce') or body.get('nonce') != session['nonce']:
        raise ValueError('训练赛身份已变化，请刷新后再操作。')
    return session


def _closed():
    from .activities import _running_cs2
    from ..cs2.launch import require_cs2_closed
    if _running_cs2() is not False:
        raise ValueError('请完全退出 CS2，再重开或取消这场训练赛。')
    require_cs2_closed('切换训练赛')


def _retire(state, session):
    from .activities import read_cs2_config
    from .external_effects import retire
    cfg = read_cs2_config()
    if cfg.get('csgo_path'):
        retire(state, cfg['csgo_path'], session['nonce'])


def _raw(session):
    from .matches import _peek
    from .activities import read_cs2_config
    return _peek(None, {'cs2_session': session}, read_cs2_config())


def _finish(state, row, session, raw):
    from ..cs2.result import result_usable, cs2_to_map, to_sim_map
    error = result_usable(raw, session)
    if error:
        raise ValueError('训练赛未录入：' + error)
    if to_sim_map(raw.get('map', '')) != session['map']:
        raise ValueError('训练地图不匹配，未录入战报。')
    from ..career.match_supplies import activate_training
    activate_training(state.career,state.season)
    own, other = row['teams_snapshot']
    mp = cs2_to_map(raw, session, own, other, session['player'])
    from ..world.map_form import apply_result, expectation
    mp['map_expectation'] = session.get('map_expectation') or expectation(own, other, session['map'])
    teams = {t['id']: t for t in state.season.teams}
    apply_result(teams[own['id']], teams[other['id']], mp, state.season.date, practice=True)
    report = dict(id=row['id'], date=state.season.date, source='cs2', map=mp,
                  teams=[own['name'], other['name']], human_id=row['human_id'])
    _retire(state, session)
    row.update(status='finished', report=report)
    from ..career.match_supplies import finish_series
    finish_series(state.career, 'scrim:' + row['id'])
    row.pop('teams_snapshot', None)
    state.career.training_session = None
    records = _records(state)
    old = [r['id'] for r in records if r['status'] == 'finished'][:-20]
    records[:] = [r for r in records if r['id'] not in old]
    return dict(reason='训练赛战报已录入。', report=deepcopy(report))


def command(state, action, body, *, dispatch=None):
    from .controls import _busy, _training_launch
    from ..cs2.result import result_usable
    row = next((r for r in _records(state) if r['id'] == body.get('id')), None)
    if not row:
        raise ValueError('这场训练赛不存在。')
    if row['status'] == 'finished':
        return dict(reason='训练赛已结束。', report=deepcopy(row['report']), replayed=True)
    if action in ('collect', 'cancel'):
        session = _session(state, row, body)
        if action == 'collect':
            return _finish(state, row, session, _raw(session))
        if body.get('confirmed') is not True:
            raise ValueError('请确认结束本次 CS2 训练，返回预约。')
        _closed()
        raw = _raw(session)
        if not result_usable(raw, session):
            return _finish(state, row, session, raw)
        _retire(state, session)
        state.career.training_session = None
        row.update(status='scheduled')
        row.pop('teams_snapshot', None)
        return dict(reason='已返回训练赛预约，可以重新进入 CS2 或模拟。')
    if action != 'launch':
        raise ValueError('没有这个训练赛操作。')
    if row['date'] > state.season.date:
        raise ValueError('还没到约定日期。')
    reason = _busy(state, training=False)
    if reason:
        raise ValueError(reason)
    if state.career.training_session:
        session = _session(state, row, body)
        _closed()
        raw = _raw(session)
        if not result_usable(raw, session):
            return _finish(state, row, session, raw)
        _retire(state, session)
        state.career.training_session = None
    side = body.get('side', 'ct')
    out = _training_launch(state, dict(opponent_id=row['opponent_id'], map=row['map'], side=side, supply_booking=row),
                           dispatch=dispatch, reward=False)
    career = state.career
    own = career.my_team(state.season.teams)
    other = next(t for t in state.season.teams if t['id'] == row['opponent_id'])
    career.training_session.update(booking_id=row['id'], side=side, my_team=own['name'],
                                   opp=other['name'], opponent=other['name'])
    row.update(status='launched', teams_snapshot=deepcopy([own, other]),
               human_id=state.arena.career_player_id(state))
    return out
