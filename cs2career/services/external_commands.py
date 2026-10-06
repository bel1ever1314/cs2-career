"""User-initiated plugin commands with a durable pre-effect receipt.

Adapters validate first, then call before_effect immediately before changing
the game. Their own backups/mount journals retain recovery details. Restart
and receipt queries never repeat installation or toggle a plugin implicitly.
"""
from uuid import uuid4
from ..storage.receipts import fingerprint, lookup, record
from ..storage.transaction import CommitPending
from .matches import _store

PATHS = {'/api/3d/settings/environment', '/api/3d/setup/install'}


def _checkpoint(_point):
    """Process-interruption test seam."""


def command(state, path, body):
    if path not in PATHS or getattr(state, '_operation_depth', 0):
        raise RuntimeError('External command must own its commits')
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
            return dict(status='failed', outcome_unknown=True, replayed=True,
                        reason='上次操作的结果尚待确认，请刷新安装与插件状态；不会自动再次执行。')
        return dict(prior['result'], replayed=True)
    started = False
    def before_effect(details):
        nonlocal started
        if started:
            raise RuntimeError('External intent already recorded')
        with state.operation():
            record(state.career, rid, path, body,
                   dict(ok=True, status='pending', external_intent=details), pending=True)
            state.persist()
        started = True
        _checkpoint('intent_saved')
    try:
        if path.endswith('/environment'):
            from cs2career.services.game_environment import environment_command
            out = environment_command(state, body, before_effect=before_effect)
        else:
            from cs2career.services.installation import install_bundle
            out = install_bundle(state, body, before_effect=before_effect)
    except CommitPending:
        raise
    except (OSError, ValueError, RuntimeError) as exc:
        if not started:
            if isinstance(exc, FileNotFoundError):
                raise ValueError(str(exc)) from exc
            raise
        # Game files cannot be rolled back with career memory. The adapter's
        # journal/backups remain authoritative until the user checks status.
        raise
    _checkpoint('external_finished')
    with state.operation():
        _store(state)['revision'] += 1
        state.settle()
        record(state.career, rid, path, body, dict(ok=True, **out))
        state.persist()
    _checkpoint('result_saved')
    return out
