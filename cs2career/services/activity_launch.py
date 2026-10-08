"""Arena and practice handoffs. A saved intent always precedes game IO.

Receipts are observations, never an instruction to launch again. Interrupted
handoffs retain the room/training nonce for collection or explicit cancellation.
"""
from copy import deepcopy
from uuid import uuid4

from ..storage.receipts import fingerprint, lookup, record, request_scope
from ..storage.transaction import CommitPending
from . import matches

PATHS = {'/api/3d/ladder/launch', '/api/3d/custom/launch', '/api/3d/controls/training/launch', '/api/3d/scrim/launch'}


def _checkpoint(_point):
    """Test-only process interruption seam."""


def command(state, path, body):
    if path not in PATHS or getattr(state, '_operation_depth', 0):
        raise RuntimeError('Activity handoff must own its commit boundary')
    if getattr(state, '_storage_failed', False):
        raise CommitPending('存档提交等待恢复，请重新启动后台。')
    body = dict(body)
    rid = body.setdefault('request_id', uuid4().hex)
    if not isinstance(rid, str) or not 8 <= len(rid) <= 100:
        raise ValueError('request_id 必须是 8 至 100 字符的唯一编号。')
    prior = lookup(state.career, rid)
    if prior:
        if prior['fingerprint'] != fingerprint(path, body):
            raise ValueError('这个请求编号已经用于其他操作。')
        if prior.get('phase') == 'pending':
            return dict(status='waiting', reason='这次启动的结果尚待确认，请刷新比赛连接状态。',
                        outcome_unknown=True, replayed=True)
        return dict(prior['result'], replayed=True)
    booked = path == '/api/3d/scrim/launch'
    training = path.endswith('/training/launch') or booked
    prepared = []
    def capture(cfg, args, kwargs):
        prepared.append((deepcopy(cfg), deepcopy(args), deepcopy(kwargs)))
        return dict(match=kwargs['request_override'], msg='', supply_deferred=True)
    def session():
        return state.career.training_session if training else state.arena.data['lobby']
    with state.operation(), request_scope(rid):
        if booked:
            from .activities import scrim_command
            from .business import guard_revision
            guard_revision(state, body)
            out = scrim_command(state, 'launch', body, dispatch=capture)
        elif training:
            from .controls import controls_command
            out = controls_command(state, 'training/launch', body, dispatch=capture)
        else:
            from cs2career.services.activities import custom_command, ladder_command
            perform = custom_command if '/custom/' in path else ladder_command
            out = perform(state, 'launch', body, dispatch=capture)
        if prepared:
            session().update(launch_state='prepared', launch_request_id=rid)
            if not training:
                session()['phase'] = 'starting'
        matches._store(state)['revision'] += 1
        state.settle()
        record(state.career, rid, path, body, dict(ok=True, **out), pending=bool(prepared))
        state.persist()
    if not prepared:
        return out
    _checkpoint('intent_saved')
    from .external_effects import drain
    drain(state)
    from cs2career.services.match_recovery import utc_stamp
    def before_dispatch():
        with state.operation():
            session().update(launch_state='dispatching', launch_requested_at=utc_stamp())
            state.arena.save() if not training else None
            state.persist()
        _checkpoint('dispatch_saved')
    cfg, args, kwargs = prepared[0]
    kwargs['before_dispatch'] = before_dispatch
    dispatched, error = None, None
    try:
        dispatched = matches._dispatch_launch(cfg, args, kwargs)
        if dispatched['match']['nonce'] != session()['nonce']:
            raise ValueError('启动返回的比赛编号与已保存请求不一致。')
    except CommitPending:
        raise
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    _checkpoint('external_finished')
    with state.operation():
        session().update(launch_state='uncertain' if error else 'dispatched', launch_requested_at=utc_stamp())
        if dispatched:
            session()['environment_generation'] = dispatched['match'].get('environment_generation', '')
        failure = 'training_failure' if training else ('custom_failure' if '/custom/' in path else 'ladder_failure')
        if error:
            matches._store(state)[failure] = dict(lobby_id=session().get('id'), reason=error)
        else:
            if training:
                from ..career.match_supplies import activate_training
                activate_training(state.career,state.season)
            matches._store(state).pop(failure, None)
            if not training:
                session()['phase'] = 'launched'
        if not training:
            state.arena.save()
            from cs2career.services.activities import _arena_status
            out['connection'] = _arena_status(state, 'custom' if '/custom/' in path else 'rank', check_running=False)
        out.update(status='failed' if error else 'waiting', reason=error or dispatched['msg'])
        matches._store(state)['revision'] += 1
        record(state.career, rid, path, body, dict(ok=True, **out))
        state.persist()
    _checkpoint('result_saved')
    return out
