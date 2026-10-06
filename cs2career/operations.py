"""Application operation boundary, shared by HTTP, desktop and CLI callers.

Adapters own the state lock. Nested domain calls join one save batch; failures
before commit restore both memory and gameplay RNG. A durable commit failure
instead blocks further commands until recovery, never pretends to roll back.
"""
from contextlib import contextmanager
from copy import deepcopy

from .random_state import capture, restore
from .storage.transaction import CommitPending, batch
from .storage.immutable import snapshot_memo


@contextmanager
def operation(state):
    if getattr(state, '_storage_failed', False):
        raise CommitPending('存档提交等待恢复，请重启后台完成恢复后继续。')
    if getattr(state, '_operation_depth', 0):
        yield
        return
    previous = deepcopy((state.season, state.career, getattr(state, '_arena', None)), snapshot_memo(state.season))
    rng = capture()
    state._operation_depth = 1
    try:
        with batch():
            yield
    except CommitPending:
        state._storage_failed = True
        raise
    except BaseException:
        state.season, state.career, arena = previous
        state.season.career = state.career
        if arena is None:
            state.__dict__.pop('_arena', None)
        else:
            state._arena = arena
        restore(rng)
        raise
    finally:
        state._operation_depth = 0
