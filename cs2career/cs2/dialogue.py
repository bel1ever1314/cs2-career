"""Build a frozen cosmetic chat contract for the next CS2 process.

No career random stream is consumed: chat cannot change simulated match odds.
The plugin independently validates this optional contract and fails silent.
"""
import copy
import json

from ..content import get_registry
from ..content.rules import validate_payload
from ..paths import data_file


def build_dialogue(enabled=True, include_builtin=True):
    if not enabled:
        return {'schema_version': 2, 'enabled': False, 'rules': [], 'scenes': []}
    base = json.loads(data_file('match_chat.json').read_text(encoding='utf-8'))
    validate_payload('match_chat', base)
    rows = []
    scenes = []
    seen = set()
    for payload in ([dict(base, _pack_id='builtin')] if include_builtin else []) + get_registry().payloads('match_chat'):
        for collection, target in [('rules', rows), ('scenes', scenes)]:
            for rule in payload.get(collection, []):
                key = payload['_pack_id'] + ':' + rule['id']
                if key in seen:
                    continue
                seen.add(key)
                row = copy.deepcopy(rule)
                row['id'] = key
                target.append(row)
    if len(rows) > 200 or len(scenes) > 50:
        raise ValueError('聊天扩展合计超过 200 条普通规则或 50 个剧情，请停用部分扩展。')
    return {'schema_version': 2, 'enabled': True, 'rules': rows, 'scenes': scenes}
