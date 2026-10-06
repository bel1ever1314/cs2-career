"""Bounded command results stored in the same transaction as career changes.

The receipt stores the action result, not a stale full-page projection. Missing
or expired receipts mean unknown, never proof that a command did not execute.
"""
from copy import deepcopy
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import time

MAX_RECEIPTS = 2048
RETENTION_SECONDS = 30 * 24 * 3600
MAX_RESULT_BYTES = 8 * 1024
MAX_ROW_BYTES = 12 * 1024
MAX_TOTAL_BYTES = 1024 * 1024
PROJECTION_FIELDS = frozenset(('context', 'state', 'saves', 'stories'))
SUMMARY_FIELDS = ('ok', 'status', 'reason_code', 'error_code', 'msg', 'reason',
                  'actualdate', 'date', 'year', 'revision', 'match_id', 'event_id',
                  'player_id', 'lobby_id', 'result_id', 'id', 'loaded', 'owned')
_request = ContextVar('central_receipt_request', default=None)


@contextmanager
def request_scope(request_id):
    """The HTTP boundary will commit this receipt with the operation result."""
    token = _request.set(request_id)
    try:
        yield
    finally:
        _request.reset(token)


def needs_legacy_receipt(request_id):
    """Keep direct/external callers compatible, without duplicating HTTP reports."""
    return bool(request_id) and _request.get() != request_id


def _bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8'))


def compact_result(result, body=None):
    """Keep small action responses verbatim; large views become explicit summaries.

    A summary acknowledges the saved outcome, not a replacement match report.
    Clients refresh their normal read projections instead of replaying an
    animation or continuing a quick-season command from an incomplete result.
    """
    compact = {k: v for k, v in result.items() if k not in PROJECTION_FIELDS}
    if _bytes(compact) <= MAX_RESULT_BYTES:
        return deepcopy(compact)
    summary = {'ok': result.get('ok', True), 'result_summary': True}
    for key in SUMMARY_FIELDS:
        value = compact.get(key)
        if isinstance(value, str):
            summary[key] = value.encode('utf-8')[:512].decode('utf-8', errors='ignore')
        elif value is None or type(value) in (bool, int, float):
            if key in compact: summary[key] = value
    for source in (body or {}, result.get('result'), result.get('match'), result.get('auto_step')):
        if not isinstance(source, dict): continue
        for key in ('match_id', 'event_id', 'lobby_id', 'result_id'):
            if isinstance(source.get(key), str) and key not in summary:
                summary[key] = source[key][:128]
    for key in reversed(tuple(summary)):
        if _bytes(summary) <= MAX_RESULT_BYTES: break
        if key not in ('ok', 'result_summary'): summary.pop(key)
    return summary


def compact_row(row):
    # Also migrate old unbounded receipts on the next command, without a
    # hidden write from lookup(). No body or full page lives in this store.
    return {**{k: row[k] for k in ('request_id', 'fingerprint', 'path', 'created_at')},
            **({'phase': 'pending'} if row.get('phase') == 'pending' else {}),
            'result': compact_result(row['result'])}


def fingerprint(path, body):
    body = {k: v for k, v in body.items() if k not in ('request_id', 'revision')}
    raw = json.dumps([path, body], ensure_ascii=False, sort_keys=True, allow_nan=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def lookup(career, request_id):
    for row in career.incident_state.get('operation_receipts', []):
        if row['request_id'] == request_id:
            return compact_row(row)
    return None


def record(career, request_id, path, body, result, *, now=None, pending=False):
    stamp = time.time() if now is None else now
    digest = fingerprint(path, body)
    prior = lookup(career, request_id)
    if prior:
        if prior['fingerprint'] != digest:
            raise ValueError('这个请求编号已经用于其他操作。')
        if prior.get('phase') != 'pending' or pending:
            return
    rows = [compact_row(r) for r in career.incident_state.get('operation_receipts', [])[-MAX_RECEIPTS:]
            if r['created_at'] >= stamp - RETENTION_SECONDS and r['request_id'] != request_id]
    compact = compact_result(result, body)
    rows.append(dict(request_id=request_id, fingerprint=digest, path=path,
                     created_at=stamp, result=deepcopy(compact), **({'phase': 'pending'} if pending else {})))
    kept, used = [], 2
    for row in reversed(rows[-MAX_RECEIPTS:]):
        size = _bytes(row)
        if size > MAX_ROW_BYTES:
            raise ValueError('操作回执元数据过大。')
        if used + size + 1 > MAX_TOTAL_BYTES: break
        kept.append(row)
        used += size + 1
    career.incident_state['operation_receipts'] = list(reversed(kept))
