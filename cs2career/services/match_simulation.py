"""Bounded BO simulation with one durable map per operation.

The response still presents the whole newly simulated series. A stop between
maps preserves scores, RNG and events; an explicit new request continues from
the last committed map. Retrying an old request only confirms its progress.
"""
from uuid import uuid4

from ..storage.receipts import fingerprint, lookup, record, request_scope
from ..storage.transaction import CommitPending
from . import matches, external_effects

PATH = '/api/3d/match/simulate'


def _checkpoint(_point):
    """Fault-injection seam; never resumes a write from a read/reconnect."""


def command(state, body):
    if getattr(state, '_operation_depth', 0):
        raise RuntimeError('Per-map simulation must run outside a save transaction')
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
        return dict(prior['result'], replayed=True, result_summary=True)
    event, match = matches._pair(state, body.get('match_id', ''), True)
    scope = body.get('scope', 'remaining_series')
    if scope not in ('current_map', 'remaining_series'):
        raise ValueError('请选择模拟当前图或剩余系列赛。')
    if scope == 'current_map' and 'map_key' not in body:
        raise ValueError('缺少当前地图编号，请刷新比赛。')
    if scope == 'current_map':
        matches._guard(state, body)
    from .career_pace import guard_map
    guard_map(state, event, match, body)
    start = len(match.get('maps') or [])
    current = dict(body)
    # At most seven maps in a supported BO7; the series itself stops at
    # its winning score. A malformed series must not spin indefinitely.
    for step in range(7):
        before = len(match.get('maps') or [])
        with state.operation(), request_scope(rid):
            from ..league.outcomes import MatchPaused
            try:
                out = matches.match_command(state, 'simulate', current, simulation_limit=1)
            except MatchPaused as exc:
                out = dict(reason=str(exc), status='paused')
            if out.get('replayed'):
                if step:
                    # An ordinary gate after a committed map is a confirmed
                    # partial outcome, not an indefinitely pending request.
                    out = matches._result_response(state, event, match, out['reason'], start)
                    record(state.career, rid, PATH, body, dict(ok=True, **out))
                    state.persist()
                return out
            matches._store(state)['revision'] += 1
            state.settle()
            from ..career.incidents import pending
            collected = out.get('status') == 'map_collected'
            more = (scope != 'current_map' and not collected and not match.get('played') and len(match.get('maps') or []) > before
                    and bool(match.get('pending_map')) and not state.career.story_queue
                    and not pending(state.career) and step < 6)
            if match.get('maps'):
                out = matches._result_response(state, event, match, out['reason'], start)
                if collected:
                    out['status'] = 'map_collected'
            record(state.career, rid, PATH, body, dict(ok=True, **out), pending=more)
            state.persist()
        _checkpoint('map_saved:' + str(len(match.get('maps') or [])))
        # Any prior CS2 nonce has already been retired in the saved series.
        # A file handoff error cannot erase the map we just completed.
        external_effects.drain(state)
        if not more:
            return out
        current['revision'] = matches._revision(state)
    raise AssertionError('unreachable simulation boundary')
