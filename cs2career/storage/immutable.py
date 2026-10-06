"""Read-only JSON history records; an explicit deepcopy creates an editable view.

Operation snapshots can share sealed records, while presentation code that
deepcopies a historical match still receives ordinary mutable dicts/lists.
"""
from copy import deepcopy


def _readonly(*_args, **_kwargs):
    raise TypeError('Archived match records are read-only; copy before editing')


class FrozenDict(dict):
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _readonly

    def __copy__(self):
        return dict(self)

    def __reduce_ex__(self, protocol):
        # Pickle is an inter-process transport here, never a save-file format.
        # Do not ask the unpickler to mutate a read-only subclass.
        return dict, (dict(self),)

    def __deepcopy__(self, memo):
        result = {}
        memo[id(self)] = result
        result.update((key, deepcopy(value, memo)) for key, value in self.items())
        return result


class FrozenList(list):
    __setitem__ = __delitem__ = append = extend = insert = pop = remove = clear = sort = reverse = __iadd__ = __imul__ = _readonly

    def __copy__(self):
        return list(self)

    def __reduce_ex__(self, protocol):
        return list, (list(self),)

    def __deepcopy__(self, memo):
        result = []
        memo[id(self)] = result
        result.extend(deepcopy(value, memo) for value in self)
        return result


def freeze(value):
    if isinstance(value, (FrozenDict, FrozenList)):
        return value
    if isinstance(value, dict):
        return FrozenDict((key, freeze(item)) for key, item in value.items())
    if isinstance(value, list):
        return FrozenList(freeze(item) for item in value)
    return value


def snapshot_memo(season):
    """Copy the appendable index, share only recursively sealed records."""
    history = season.history
    if history and all(isinstance(row, FrozenDict) for row in history):
        return {id(history): list(history)}
    return {}
