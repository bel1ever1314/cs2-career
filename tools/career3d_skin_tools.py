"""Optional, local v1 appearance adapter; no renderer, persistence or CS2 writes.

Only an explicitly requested inventory item is exposed. The enclosing service
owns its lock, revision increment and atomic save; these helpers never call the
original desktop craft command, which would save and sync the live game.
"""
from __future__ import annotations

from copy import deepcopy
import re

from tools.career3d_activities import read_cs2_config


SCHEMA_VERSION = 1
_BODY_FIELDS = {'schema_version', 'id', 'expected_hash', 'revision', 'stickers'}
_STICKER_FIELDS = {'def', 'slot', 'wear', 'rotation', 'x', 'y', 'schema'}
_NO_STICKER_SLOTS = {'knife', 'gloves', 'agents', 'music', 'graffiti'}


def _config():
    cfg = read_cs2_config()
    if cfg.get('skin_tools_enabled') is not True:
        raise ValueError('可选饰品工具接口尚未启用。')
    return cfg


def tools_context(state):
    """Cheap discovery, including when disabled; never examines the inventory."""
    return {
        'schema_version': SCHEMA_VERSION,
        'enabled': read_cs2_config().get('skin_tools_enabled') is True,
        'capabilities': {'read_item': True, 'write_stickers': True},
        'renderer_bundled': False,
        'max_stickers': 5,
        'endpoints': {'item': '/api/3d/skin-tools/item',
                      'stickers': '/api/3d/skin-tools/stickers'},
    }


def _revision(state):
    revision = state.career.incident_state.get('career3d_service', {}).get('revision', 0)
    if type(revision) is not int or revision < 0:
        raise ValueError('生涯版本数据无效。')
    return revision


def _item(state, item_id):
    from cs2career.career.skin_crafts import _inventory

    if type(item_id) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}', item_id):
        raise ValueError('饰品 ID 必须是有效的库存实例 ID。')
    inventory = state.career.inventory
    _inventory(inventory)
    row = next((row for row in inventory if row['id'] == item_id), None)
    if row is None:
        raise ValueError('库存中没有这件饰品。')
    return row


def _catalog(row):
    """Validate and project server-owned native metadata, without asset URLs."""
    from cs2career.career import skins
    from cs2career.career.skin_crafts import _catalog_index, _integer, _limits

    core = skins._item_core(row)
    known = skins.sticker_catalog_for_item(row)
    kits, models = _catalog_index(known)
    raw_model = models.get(str(core['def']), models.get(core['def']))
    model = None
    if raw_model is not None:
        if not isinstance(raw_model, dict):
            raise ValueError('武器贴纸模型数据无效。')
        for flag in ('allow_stickers', 'enabled'):
            if flag in raw_model and type(raw_model[flag]) is not bool:
                raise ValueError('武器贴纸模型开关无效。')
        if raw_model.get('allow_stickers') is not False and raw_model.get('enabled') is not False:
            count = _integer(raw_model.get('schema_count'), '模型锚点数量', 1, 32)
            slots = raw_model.get('allowed_slots', list(range(5)))
            if (not isinstance(slots, list)
                    or any(type(slot) is not int or slot not in range(5) for slot in slots)
                    or len(slots) != len(set(slots))):
                raise ValueError('模型贴纸槽位配置无效。')
            model = {'schema_count': count, 'allowed_slots': list(slots)}
            for axis in ('x', 'y', 'rotation'):
                if axis + '_min' in raw_model or axis + '_max' in raw_model:
                    lo, hi = _limits(raw_model, axis)
                elif axis == 'rotation':
                    lo, hi = -360.0, 360.0
                else:
                    continue
                if axis == 'rotation' and (lo < -360 or hi > 360):
                    raise ValueError('模型旋转限值超出允许范围。')
                model[axis + '_min'], model[axis + '_max'] = lo, hi
            if raw_model.get('model_variant') in ('legacy', 'hd'):
                model['model_variant'] = raw_model['model_variant']
    public_kits = []
    for kit, entry in kits.items():
        supported = entry.get('weapon_defs')
        if supported is not None:
            if not isinstance(supported, list) or any(type(value) is not int for value in supported):
                raise ValueError('贴纸武器限制配置无效。')
            if core['def'] not in supported:
                continue
        public = {'def': kit}
        for field in ('name', 'name_en'):
            if field in entry:
                if not isinstance(entry[field], str):
                    raise ValueError('贴纸名称数据无效。')
                public[field] = entry[field]
        public_kits.append(public)
    editable = (model is not None and bool(model['allowed_slots'])
                and row.get('sticker_capable') is not False
                and core['slot'] not in _NO_STICKER_SLOTS)
    return core, known, model, public_kits, editable


def _snapshot(row, core, known):
    from cs2career.career.skin_crafts import appearance_hash, normalize_attachments, normalize_instance

    appearance = {key: core[key] for key in ('def', 'paint', 'wear', 'seed')}
    appearance['stickers'] = normalize_attachments(row.get('stickers') or [], core['def'], known)
    # Match skins._item_payload: provenance, accounts, equips and prices never
    # cross this boundary. Optional native fields are copied explicitly.
    for field in ('nametag', 'stattrak'):
        if row.get(field) is not None:
            appearance[field] = deepcopy(row[field])
    appearance = normalize_instance(appearance, known)
    appearance['hash'] = appearance_hash(appearance, known)
    appearance['slot'] = core['slot']
    return appearance


def _sync(cfg):
    # A deferred policy, not a claim that a renderer or plugin is installed.
    return 'next_match' if cfg.get('skins_inventory_mode', 'career') == 'career' else 'none'


def item_context(state, item_id):
    """One native appearance and on-demand position/kit metadata; read-only."""
    cfg = _config()
    row = _item(state, item_id)
    core, known, model, kits, editable = _catalog(row)
    appearance = _snapshot(row, core, known)
    return {'schema_version': SCHEMA_VERSION, 'id': item_id, 'item': appearance,
            'expected_hash': appearance['hash'], 'revision': _revision(state),
            'model': model, 'sticker_catalog': kits, 'editable': editable, 'sync': _sync(cfg)}


def apply_stickers(state, body):
    """Validate a complete optimistic edit, then commit only the inventory copy."""
    cfg = _config()
    if not isinstance(body, dict) or set(body) - {'request_id'} != _BODY_FIELDS:
        raise ValueError('贴纸编辑需要 schema_version、id、expected_hash、revision 和 stickers。')
    if type(body['schema_version']) is not int or body['schema_version'] != SCHEMA_VERSION:
        raise ValueError('饰品工具只支持 schema_version 1。')
    current = _revision(state)
    if type(body['revision']) is not int or body['revision'] != current:
        raise ValueError('库存已变化，请重新读取饰品后再编辑。')
    expected = body['expected_hash']
    if type(expected) is not str or not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ValueError('expected_hash 必须是当前饰品的外观哈希。')
    row = _item(state, body['id'])
    core, known, _model, _kits, editable = _catalog(row)
    if _snapshot(row, core, known)['hash'] != expected:
        raise ValueError('饰品外观已变化，请重新读取后再编辑。')
    stickers = body['stickers']
    if not isinstance(stickers, list) or len(stickers) > 5:
        raise ValueError('贴纸必须是数组，每件武器最多 5 张。')
    if stickers and not editable:
        raise ValueError('该饰品不支持贴纸编辑。')
    if any(not isinstance(sticker, dict) or set(sticker) - _STICKER_FIELDS for sticker in stickers):
        raise ValueError('贴纸只能包含原生槽位、kit、磨损、旋转、偏移和锚点参数。')
    from cs2career.career.skin_crafts import edit_stickers

    # Legacy items resolve exactly the same defaults as the native export before
    # the pure helper hashes them. Other inventory rows remain unmodified.
    prepared = [{**item, **{key: core[key] for key in ('def', 'paint', 'wear', 'seed')}}
                if item['id'] == body['id'] else item for item in state.career.inventory]
    result = edit_stickers(prepared, body['id'], stickers, known)
    appearance = _snapshot(result['item'], core, known)
    next(row for row in result['inventory'] if row['id'] == body['id'])['hash'] = appearance['hash']
    response = {'schema_version': SCHEMA_VERSION, 'id': body['id'], 'item': appearance,
                'expected_hash': appearance['hash'], 'revision': current,
                'reason': result['message'], 'warnings': result['warnings'], 'sync': _sync(cfg)}
    state.career.inventory = result['inventory']
    return response
