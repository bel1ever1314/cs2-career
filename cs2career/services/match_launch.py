"""Durable career CS2 handoff: intent -> external work -> acknowledgement.

The HTTP adapter holds the application lock for the entire command. No game
files or processes are part of a save rollback. An interrupted attempt is
observed/recovered by its nonce; neither restart nor receipt lookup dispatches
Steam again. Arena/training use the companion activity_launch coordinator.
"""
from copy import deepcopy
from uuid import uuid4

from ..storage.receipts import fingerprint, lookup, record, request_scope
from ..storage.transaction import CommitPending
from . import matches, external_effects

PATH = '/api/3d/match/launch'


def _checkpoint(_point):
    """Fault-injection seam; no production scheduling or automatic replay."""


def command(state, body):
    if getattr(state, '_operation_depth', 0):
        raise RuntimeError('CS2 handoff must run outside a save transaction')
    if getattr(state, '_storage_failed', False):
        raise CommitPending('存档提交等待恢复，请重启后台完成恢复后继续。')
    body = dict(body)
    rid = body.setdefault('request_id', uuid4().hex)
    if not isinstance(rid, str) or not 8 <= len(rid) <= 100:
        raise ValueError('request_id 必须是 8 至 100 字符的唯一编号。')
    prior = lookup(state.career, rid)
    if prior:
        if prior['fingerprint'] != fingerprint(PATH, body):
            raise ValueError('这个请求编号已经用于其他操作。')
        if prior.get('phase') == 'pending':
            return dict(reason='这次启动的结果尚待确认，请刷新比赛连接状态。',
                        status='waiting', replayed=True, outcome_unknown=True,
                        connection=matches.match_status(state, body['match_id']))
        return dict(prior['result'], replayed=True)

    prepared, retired = [], []
    def retire(path, nonce):
        external_effects.enqueue(state, 'retire_match', path, nonce)
        retired.append(nonce)

    def capture(cfg, arguments, kwargs):
        prepared.append((deepcopy(cfg), deepcopy(arguments), deepcopy(kwargs)))
        # The core builds the same session/roster as a live dispatch. This
        # return acknowledges preparation only; it does not claim Steam ran.
        return {'match': kwargs['request_override'], 'msg': '', 'supply_deferred': True}

    def prepare(current, match, data):
        return matches._launch(current, match, data, dispatch=capture)

    from ..league.outcomes import MatchPaused
    with state.operation(), request_scope(rid):
        try:
            out = matches.match_command(state, 'launch', body, launch_handler=prepare,
                                        retire_request=retire)
        except MatchPaused as exc:
            out = dict(reason=str(exc), status='paused')
        if out.get('replayed'):
            return out
        if prepared:
            _, match = state.season.find_match(body['match_id'])
            match['cs2_session'].update(launch_state='prepared', launch_request_id=rid)
        matches._store(state)['revision'] += 1
        state.settle()
        record(state.career, rid, PATH, body, dict(ok=True, **out), pending=bool(prepared or retired))
        state.persist()

    if not prepared and not retired:
        return out
    _checkpoint('intent_saved')
    from cs2career.services.match_recovery import utc_stamp

    def before_dispatch():
        # Preparation can take longer than Steam's grace window. Timestamp
        # immediately before dispatch, not before copying/generating files.
        with state.operation():
            _, match = state.season.find_match(body['match_id'])
            match['cs2_session'].update(launch_state='dispatching', launch_requested_at=utc_stamp())
            matches._store(state)['revision'] += 1
            state.persist()
        _checkpoint('dispatch_saved')

    dispatched, error = None, None
    try:
        external_effects.drain(state)
        if prepared:
            cfg, arguments, kwargs = prepared[0]
            nonce = kwargs['request_override']['nonce']
            kwargs['before_dispatch'] = before_dispatch
            dispatched = matches._dispatch_launch(cfg, arguments, kwargs)
            if dispatched['match']['nonce'] != nonce:
                raise ValueError('启动返回的比赛编号与已保存请求不一致。')
    except CommitPending:
        raise
    except Exception as exc:
        # Steam could have started even if a later handoff step raised. Keep
        # the persisted session and its identity; never pretend to roll back.
        error = f'{type(exc).__name__}: {exc}'
    _checkpoint('external_finished')

    with state.operation():
        _, match = state.season.find_match(body['match_id'])
        session = match.get('cs2_session')
        if session:
            session.update(launch_state='uncertain' if error else 'dispatched', launch_requested_at=utc_stamp())
            if dispatched:
                session['environment_generation'] = dispatched['match'].get('environment_generation', '')
        if error:
            matches._store(state)['match_failure'] = {'match_id': match['id'], 'reason': error}
            out = dict(reason=error, status='failed')
        elif dispatched:
            from ..career.match_supplies import activate, series_key
            activate(state.career, match, series_key(state.season,match), state.season.date,
                     session.get('supply_intent',{}), session['map_index'])
            matches._store(state).pop('match_failure', None)
            out['reason'] = f"第 {session['map_index'] + 1} 图 {session['map']}。{dispatched['msg']}"
        out['connection'] = matches.match_status(state, match['id'])
        matches._store(state)['revision'] += 1
        record(state.career, rid, PATH, body, dict(ok=True, **out))
        state.persist()
    _checkpoint('result_saved')
    return out
