"""HTTP command boundary. Buffer the response until the save batch commits.

External process/install operations and manual restore retain their explicit
recovery workflows; they must not be disguised as rollback-able file writes.
"""
from .storage.receipts import lookup, record, fingerprint, request_scope
from .storage.transaction import CommitPending


def recovery_response(state):
    """Poison the holder even when an adapter owns its own transaction."""
    state._storage_failed = True
    return {'ok': False, 'error_code': 'storage_recovery_required',
            'outcome_unknown': True,
            'msg': '存档已提交，正在重新载入以完成恢复；请勿重复操作。'}


class RejectedResponse(Exception):
    pass


def transactional(path):
    if path == '/api/3d/skin-tools/stickers' or path.startswith('/api/3d/tactics/'):
        return True
    if path in ('/api/3d/match/simulate', '/api/3d/season/run'):
        return False  # The BO coordinator commits each map, not one giant batch.
    if path in ('/api/3d/settings', '/api/3d/start/create'):
        return True
    # These flows commit intent/results around external effects or own a
    # separate durable journal. Their adapters remain responsible for recovery.
    return not (any(word in path for word in ('/launch', '/install', '/shutdown'))
                or path.startswith(('/api/3d/saves/', '/api/3d/start/',
                                    '/api/3d/settings', '/api/cs2/',
                                    '/api/3d/skin-tools/', '/api/arena/', '/api/tactics/',
                                    '/api/3d/tactics/')))


def execute(handler, path):
    if not transactional(path):
        try:
            handler._post()
        except CommitPending:
            handler._json(recovery_response(handler.state), 503)
        return
    body = handler._body()
    rid = body.get('request_id') or handler.headers.get('X-Career-Request-ID')
    if rid is not None and (not isinstance(rid, str) or not 1 <= len(rid) <= 128):
        handler._json({'ok': False, 'msg': '操作编号格式不正确。'}, 400)
        return
    handler._buffer_response = True
    handler._buffered_response = None
    response = None
    try:
        with handler.state.operation():
            prior = lookup(handler.state.career, rid) if rid else None
            if prior:
                if prior['fingerprint'] != fingerprint(path, body):
                    raise ValueError('这个请求编号已经用于其他操作。')
                result = dict(prior['result'], replayed=True)
                handler._json(handler._replay_result(result))
            else:
                with request_scope(rid):
                    handler._post()
            response = handler._buffered_response
            if response is None:
                raise RuntimeError('Command did not produce a response')
            result, code = response
            if code >= 400 or result.get('ok') is False:
                raise RejectedResponse()
            if rid and not prior and not result.get('replayed'):
                record(handler.state.career, rid, path, body, result)
                handler.state.persist()
    except RejectedResponse:
        # The projection built while rejecting may reference rolled-back data.
        result, code = response
        response = ({k: v for k, v in result.items() if k not in ('context', 'state')}, code)
    except CommitPending:
        response = (recovery_response(handler.state), 503)
    except Exception as exc:
        response = ({'ok': False, 'msg': str(exc)}, 400 if isinstance(exc, ValueError) else 500)
    finally:
        handler._buffer_response = False
        handler._buffered_response = None
    if response and response[1] < 400 and not getattr(handler.state, '_storage_failed', False):
        from .services.external_effects import drain
        try:
            drain(handler.state)
        except CommitPending:
            response = (recovery_response(handler.state), 503)
    handler._json(*response)
