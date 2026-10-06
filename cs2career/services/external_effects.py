"""Durable outbox for rebuildable game files, not Steam/process commands.

Items are saved with the domain change. Delivery runs only after commit and
may repeat: retirement checks the exact nonce; tactics regenerate the latest
saved library under the existing game/session guards. Failures stay pending.
"""
from hashlib import sha256
from pathlib import Path

KEY = 'external_effects_v1'


def enqueue(state, kind, path, value):
    if kind not in ('retire_match', 'publish_tactics'):
        raise ValueError('Unknown external effect')
    path = str(Path(path).absolute())
    ident = sha256(f'{kind}\0{path}\0{value}'.encode()).hexdigest()
    state.career.incident_state.setdefault(KEY, {})[ident] = dict(kind=kind, path=path, value=value)
    state.career.save()


def retire(state, path, nonce):
    if getattr(state, '_operation_depth', 0):
        enqueue(state, 'retire_match', path, nonce)
    else:
        from ..cs2.launch import deactivate_match_request
        deactivate_match_request(Path(path), nonce)


def _deliver(state, item):
    from ..cs2 import launch
    if item['kind'] == 'retire_match':
        launch.deactivate_match_request(Path(item['path']), item['value'])
    elif item['kind'] == 'publish_tactics':
        from .matches import _tactical_sessions
        result = launch.tactical_publication(Path(item['path']), item['value'], _tactical_sessions(state), sync=True)
        if not result.get('synced'):
            raise ValueError(result['reason'])
    else:
        raise ValueError('Unknown saved external effect')


def drain(state):
    if getattr(state, '_operation_depth', 0):
        raise RuntimeError('External delivery cannot run before commit')
    if getattr(state, '_storage_failed', False):
        return
    for ident, item in list(state.career.incident_state.get(KEY, {}).items()):
        try:
            _deliver(state, item)
        except (OSError, ValueError, RuntimeError) as exc:
            error = str(exc)[:500]
            if item.get('last_error') != error:
                with state.operation():
                    state.career.incident_state[KEY][ident]['last_error'] = error
                    state.persist()
            continue
        with state.operation():
            state.career.incident_state[KEY].pop(ident, None)
            state.persist()
