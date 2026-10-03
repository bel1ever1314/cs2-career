"""Reviewed upstream behavior scripts, without an upstream player database.

These tiny, fixed resources accompany the career's own generated match VPK.
Reading them never looks at the user's installed mod or performs a download.
"""
from functools import lru_cache
import hashlib
import json

from ..paths import data_file


LEVELS = ('Low', 'Medium', 'High')
RESOURCE_PATHS = frozenset(('scripts/ai/rush/bt_default.kv3',
                            'scripts/ai/rush/bt_config.kv3'))


@lru_cache(maxsize=3)
def _resources(level: str) -> tuple[tuple[str, bytes], ...]:
    if level not in LEVELS:
        raise ValueError('未知 Bot 行为难度：' + str(level))
    meta = json.loads(data_file('botprofile_behavior/resources.json').read_text('utf-8'))
    if meta.get('schema_version') != 1 or meta.get('upstream_version') != '1.4.5':
        raise ValueError('Bot 行为资源版本不正确。')
    rows = meta['levels'][level]
    if set(rows) != RESOURCE_PATHS:
        raise ValueError('Bot 行为资源清单不完整。')
    result = []
    expected_names = {'bt_default.kv3', 'bt_config_' + level + '.kv3'}
    for path, row in sorted(rows.items()):
        name = row['file']
        if name not in expected_names:
            raise ValueError('Bot 行为资源路径不正确。')
        payload = data_file('botprofile_behavior/' + name).read_bytes()
        if not payload or len(payload) > 64 * 1024 or hashlib.sha256(payload).hexdigest() != row['sha256']:
            raise ValueError('Bot 行为资源校验失败。')
        result.append((path, payload))
    return tuple(result)


def resources(level: str) -> dict[str, bytes]:
    # Independent dictionaries keep callers from mutating cached match assets.
    return dict(_resources(level))
