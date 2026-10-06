"""Quick season coordination with durable map/date steps, not a giant POST.

One UI step still means a series or a calendar advance. Intermediate maps use
their own domain tokens and commits. Result presentation joins those maps back
into one series; no client change or hidden continuation after a restart.
"""
import hashlib

from ..storage.receipts import fingerprint, lookup, record, request_scope
from ..storage.transaction import CommitPending
from . import matches, external_effects

PATH = '/api/3d/season/run'


def _checkpoint(_point):
    """Test-only seam after each durable step."""


def command(state, body):
    if getattr(state, '_operation_depth', 0):
        raise RuntimeError('Quick season checkpoints must run outside a save transaction')
    if getattr(state, '_storage_failed', False):
        raise CommitPending('存档提交等待恢复，请重启后台完成恢复后继续。')
    rid = body.get('request_id')
    if not isinstance(rid, str) or not 8 <= len(rid) <= 100:
        raise ValueError('request_id 必须是 8 至 100 字符的唯一编号。')
    prior = lookup(state.career, rid)
    if prior:
        if prior['fingerprint'] != fingerprint(PATH, body):
            raise ValueError('这个请求编号已经用于其他操作。')
        return dict(prior['result'], replayed=True, result_summary=True)
    legacy = state.career.incident_state.get('career3d_service', {}).get('season_receipts', [])
    if any(row.get('request_id') == rid for row in legacy):
        # Let the original adapter validate its identity and return its saved
        # result before translating a new request into per-map child tokens.
        return matches.season_command(state, 'run', body)
    count = body.get('max_steps', 1)
    if type(count) is not int or not 1 <= count <= 24:
        raise ValueError('max_steps 只允许 1 至 24。')
    completed, results, offsets = 0, {}, {}
    for index in range(count * 7):
        current = dict(body, max_steps=1,
                       request_id=hashlib.sha256(f'quick-map:{rid}:{index}'.encode()).hexdigest())
        if index:
            current['revision'] = matches._revision(state)
        with state.operation(), request_scope(current['request_id']):
            from ..league.outcomes import MatchPaused
            try:
                out = matches.season_command(state, 'run', current, simulation_limit=1)
            except MatchPaused as exc:
                out = dict(reason=str(exc), status='paused', steps=0, results=[],
                           quick=matches.quick_context(state))
            matches._store(state)['revision'] += 1
            state.settle()
            for report in out.get('results', []):
                ident = report['result']['match_id']
                event, match = state.season.find_match(ident)
                first = (report.get('reveal', {}).get('maps') or [{'index': 0}])[0]['index']
                offsets.setdefault(ident, first)
                results[ident] = matches._result_response(state, event, match, report['reason'], offsets[ident])
            partial = out['status'] == 'map_played'
            if not partial:
                completed += out.get('steps', 0)
            more = (out['status'] in ('progress', 'played', 'map_played')
                    and (partial or completed < count) and not state.career.story_queue
                    and index + 1 < count * 7)
            if partial:
                # Map-only checkpoints are internal; externally a stop is a
                # paused series, not a falsely completed match.
                out['status'] = 'paused'
            out.update(steps=completed, results=list(results.values()), quick=matches.quick_context(state))
            if results:
                latest = next(reversed(results.values()))
                out.update({key: latest[key] for key in ('result', 'reveal')})
            record(state.career, rid, PATH, body, dict(ok=True, **out), pending=more)
            state.persist()
        _checkpoint('step_saved:' + str(index + 1))
        external_effects.drain(state)
        if not more:
            return out
    raise AssertionError('unreachable season boundary')
