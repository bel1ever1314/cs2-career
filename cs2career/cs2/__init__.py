# coding=utf-8
"""CS2 adapters, with business APIs loaded only when they are requested.

The standalone environment watchdog can import its pure filesystem/process
helpers without initializing settings or creating a Career save directory.
"""
from importlib import import_module

_LAUNCH_EXPORTS = {
    'AIM_MODES', 'DIFFICULTIES', 'IDENTITY_MODES', 'NADE_MODES', 'install_mod',
    'install_skins_mod', 'update_skins_gamedata', 'sync_live_profiles', 'history',
    'read_result', 'save_settings', 'settings', 'skins_inventory_mode',
    'skin_integration', 'start_match', 'status',
}
_RESULT_EXPORTS = {'cs2_to_map', 'pick_better_result', 'result_usable', 'to_cs2_map', 'to_sim_map'}

__all__ = [
    "AIM_MODES",
    "DIFFICULTIES",
    "IDENTITY_MODES",
    "NADE_MODES",
    "install_mod",
    "install_skins_mod",
    "update_skins_gamedata",
    "sync_live_profiles",
    "cs2_to_map",
    "history",
    "pick_better_result",
    "read_result",
    "result_usable",
    "save_settings",
    "settings",
    "skins_inventory_mode",
    "skin_integration",
    "start_match",
    "status",
    "to_cs2_map",
    "to_sim_map",
]


def __getattr__(name):
    module = 'launch' if name in _LAUNCH_EXPORTS else 'result' if name in _RESULT_EXPORTS else None
    if module is None:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    value = getattr(import_module('.' + module, __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
