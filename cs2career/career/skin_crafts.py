"""Pure, free cosmetic edits/imports. Never saves, changes money, or syncs CS2.

Unknown wear/seed stay absent. Hash the FINAL applied V5 appearance when the
caller supplies game defaults; hashing a source recipe does not invent them.
``next_id`` is the next available inv.N integer, not the last-used sequence.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit

from ..paths import data_file

MAX_STICKERS = 5
MAX_PACK_ITEMS = 64
PLAYERS = {'donk': 'donk', 'zywoo': 'ZywOo', 'monesy': 'm0NESY', 'niko': 'NiKo'}
_KEY = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$')
_WEAPON_DEFS = {'ak47': 7, 'm4a1': 60, 'm4a4': 16, 'awp': 9, 'deagle': 1, 'usp': 61, 'glock': 4}
_NAMED_DEFS = {'weapon_knife_karambit': 507, 'weapon_knife_butterfly': 515,
               'weapon_bayonet': 500, 'sport_gloves': 5030, 'specialist_gloves': 5034}


def _integer(value, label, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError(f'{label}必须是 {lo} 到 {hi} 的整数。')
    return value


def _number(value, label, lo=None, hi=None):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{label}必须是有限数字。')
    number = float(value)
    if (lo is not None and number < lo) or (hi is not None and number > hi):
        raise ValueError(f'{label}超出允许范围。')
    return 0.0 if number == 0.0 else number


def _key(value, label):
    if not isinstance(value, str) or not _KEY.fullmatch(value):
        raise ValueError(f'{label}必须是 1-96 位字母、数字、点、横线或下划线。')
    return value


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'饰品数据无法读取：{exc}') from exc


def load_sticker_catalog(path=None):
    """Read packaged data only; accepts an explicit path for isolated tests."""
    raw = _read_json(path if path is not None else data_file('stickers.json'))
    if not isinstance(raw, dict) or not isinstance(raw.get('stickers'), list) or not isinstance(raw.get('models'), dict):
        raise ValueError('贴纸目录需要 stickers 数组和 models 对象。')
    return raw


def _catalog_index(catalog):
    raw = load_sticker_catalog() if catalog is None else catalog
    if not isinstance(raw, dict) or not isinstance(raw.get('stickers'), list) or not isinstance(raw.get('models'), dict):
        raise ValueError('贴纸目录需要 stickers 数组和 models 对象。')
    kits = {}
    for row in raw['stickers']:
        if not isinstance(row, dict):
            raise ValueError('贴纸目录中的每个条目必须是对象。')
        kit = _integer(row.get('def'), '贴纸 kit ID', 1, 4294967295)
        if kit in kits:
            raise ValueError('贴纸目录存在重复 kit ID。')
        kits[kit] = row
    return kits, raw['models']


def _limits(model, axis):
    # Optional offsets require a documented model range, not a guessed UI range.
    if axis + '_min' not in model or axis + '_max' not in model:
        raise ValueError(f'该武器模型没有登记 {axis} 偏移限值。')
    lo = _number(model[axis + '_min'], axis + ' 下限')
    hi = _number(model[axis + '_max'], axis + ' 上限')
    if lo > hi:
        raise ValueError('模型限值顺序无效。')
    return lo, hi


def normalize_attachments(stickers, weapon_def, catalog=None):
    """Validate native sticker fields; return a fresh list sorted by slot.

    models keys are weapon def strings; registered models may declare
    allow_stickers/enabled, allowed_slots, x_min/x_max, y_min/y_max,
    rotation_min/rotation_max. Undocumented offsets are rejected.
    """
    weapon_def = _integer(weapon_def, '武器定义', 1, 65535)
    if not isinstance(stickers, list) or len(stickers) > MAX_STICKERS:
        raise ValueError('贴纸必须是数组，每件武器最多 5 张。')
    if not stickers:
        return []  # Removing stickers does not require an available catalog/model.
    kits, models = _catalog_index(catalog)
    model = models.get(str(weapon_def), models.get(weapon_def))
    if not isinstance(model, dict) or model.get('allow_stickers') is False or model.get('enabled') is False:
        raise ValueError('该武器模型尚未登记贴纸支持。')
    allowed_slots = model.get('allowed_slots', [0, 1, 2, 3, 4])
    if not isinstance(allowed_slots, list) or any(type(slot) is not int or slot not in range(5) for slot in allowed_slots):
        raise ValueError('模型贴纸槽位配置无效。')
    slots, result = set(), []
    for attachment in stickers:
        if not isinstance(attachment, dict):
            raise ValueError('每张贴纸必须是对象。')
        slot = _integer(attachment.get('slot'), '贴纸槽位', 0, 4)
        if slot in slots:
            raise ValueError('同一个贴纸槽位不能重复。')
        if slot not in allowed_slots:
            raise ValueError('该模型不支持所选贴纸槽位。')
        slots.add(slot)
        kit = _integer(attachment.get('def'), '贴纸 kit ID', 1, 4294967295)
        if kit not in kits:
            raise ValueError('贴纸 kit ID 不在已核验目录中。')
        supported = kits[kit].get('weapon_defs')
        if supported is not None:
            if not isinstance(supported, list) or any(type(value) is not int for value in supported):
                raise ValueError('贴纸武器限制配置无效。')
            if weapon_def not in supported:
                raise ValueError('这张贴纸不支持该武器模型。')
        row = {'slot': slot, 'def': kit}
        count = _integer(model.get('schema_count'), '模型锚点数量', 1, 32)
        row['schema'] = _integer(attachment.get('schema', slot % count), '贴纸 schema', 0, count - 1)
        if 'wear' in attachment:
            row['wear'] = _number(attachment['wear'], '贴纸磨损', 0.0, 1.0)
        if 'rotation' in attachment:
            lo = _number(model.get('rotation_min', -360), '旋转下限', -360, 360)
            hi = _number(model.get('rotation_max', 360), '旋转上限', -360, 360)
            if lo > hi:
                raise ValueError('模型旋转限值顺序无效。')
            row['rotation'] = _number(attachment['rotation'], '贴纸旋转', lo, hi)
        for axis in ('x', 'y'):
            if axis in attachment:
                lo, hi = _limits(model, axis)
                row[axis] = _number(attachment[axis], axis + ' 偏移', lo, hi)
        result.append(row)
    return sorted(result, key=lambda row: row['slot'])


def normalize_instance(row, sticker_catalog=None):
    """Copy an appearance; validate known values, preserving absent wear/seed."""
    if not isinstance(row, dict):
        raise ValueError('库存外观必须是对象。')
    result = deepcopy(row)
    result['def'] = _integer(row.get('def'), '武器定义', 1, 65535)
    result['paint'] = _integer(row.get('paint'), '涂装编号', 0, 2147483647)
    if 'wear' in row:
        result['wear'] = _number(row['wear'], '武器磨损', 0.0, 1.0)
    if 'seed' in row:
        result['seed'] = _integer(row['seed'], '武器模板', 0, 1000)
    result['stickers'] = normalize_attachments(row.get('stickers', []), result['def'], sticker_catalog)
    # Cache hashes describe appearance, never an old cached value or its provenance.
    result.pop('hash', None)
    return result


def appearance_hash(row, catalog=None):
    """Stable full weapon-appearance hash, independent of inventory ID/list order."""
    normalized = normalize_instance(row, catalog)
    fields = ('def', 'paint', 'wear', 'seed', 'stickers', 'nametag', 'stattrak', 'tint', 'keychains')
    appearance = {key: normalized[key] for key in fields if key in normalized}
    if 'nametag' in appearance and (not isinstance(appearance['nametag'], str) or len(appearance['nametag']) > 128):
        raise ValueError('名称标签必须是最多 128 字的文本。')
    if 'stattrak' in appearance:
        _integer(appearance['stattrak'], 'StatTrak', -1, 2147483647)
    if 'tint' in appearance:
        _integer(appearance['tint'], '颜色编号', 0, 2147483647)
    if 'keychains' in appearance:
        value = appearance['keychains']
        if not isinstance(value, list) or len(value) > 5 or any(not isinstance(v, dict) or type(v.get('slot')) is not int for v in value):
            raise ValueError('挂件数据必须有有效槽位。')
        appearance['keychains'] = sorted(value, key=lambda v: v['slot'])
    try:
        blob = json.dumps(appearance, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError) as exc:
        raise ValueError('外观包含非 JSON 或非有限数据。') from exc
    return hashlib.sha256(blob).hexdigest()


def _inventory(inventory):
    if not isinstance(inventory, list) or any(not isinstance(row, dict) for row in inventory):
        raise ValueError('库存必须是对象数组。')
    ids = [row.get('id') for row in inventory]
    if any(not isinstance(value, str) or not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError('库存实例 ID 缺失或重复。')


def edit_stickers(inventory, item_id, stickers, catalog=None):
    """Return edited rows and explicit free replacement/removal warnings; no mutation."""
    _inventory(inventory)
    index = next((i for i, row in enumerate(inventory) if row['id'] == item_id), None)
    if index is None:
        raise ValueError('库存中没有这件饰品。')
    old = inventory[index]
    item = normalize_instance({**old, 'stickers': stickers}, catalog)
    item['hash'] = appearance_hash(item, catalog)
    # A stale catalog must not trap an obsolete/unknown sticker on the weapon.
    # Only the replacement data is authoritative; old slots are for warnings.
    prior = old.get('stickers', [])
    previous = {row['slot']: row for row in prior
                if isinstance(row, dict) and type(row.get('slot')) is int and row['slot'] in range(5)} if isinstance(prior, list) else {}
    current = {row['slot']: row for row in item['stickers']}
    removed = sorted(set(previous) - set(current))
    replaced = sorted(slot for slot in set(previous) & set(current) if previous[slot].get('def') != current[slot]['def'])
    warnings = []
    if removed:
        warnings.append('移除槽位 ' + '、'.join(str(slot + 1) for slot in removed) + ' 的贴纸；免费编辑，不改变售价。')
    if replaced:
        warnings.append('替换槽位 ' + '、'.join(str(slot + 1) for slot in replaced) + ' 的贴纸；旧贴纸不会新增为可出售库存。')
    rows = deepcopy(inventory)
    rows[index] = item
    return {'inventory': rows, 'item': deepcopy(item), 'warnings': warnings,
            'removed_slots': removed, 'replaced_slots': replaced,
            'message': '贴纸已免费更新；个人资金和饰品售价不变。' + (' ' + ' '.join(warnings) if warnings else '')}


def _skins(catalog):
    raw = _read_json(data_file('skins.json')) if catalog is None else catalog
    if isinstance(raw, dict) and isinstance(raw.get('skins'), list):
        rows = raw['skins']
    elif isinstance(raw, dict) and all(isinstance(value, dict) for value in raw.values()):
        return raw
    else:
        raise ValueError('皮肤目录需要 skins 数组或 ID 映射。')
    if any(not isinstance(row, dict) or not isinstance(row.get('id'), str) for row in rows):
        raise ValueError('皮肤目录条目无效。')
    return {row['id']: row for row in rows}


def _skin_def(row):
    raw = row.get('def')
    if type(raw) is int:
        return raw
    if isinstance(raw, str):
        if raw.isdigit():
            return int(raw)
        if raw in _NAMED_DEFS:
            return _NAMED_DEFS[raw]
    return _WEAPON_DEFS.get(row.get('slot'), 0)


def _provenance(raw):
    source_date, source_url = raw.get('source_date'), raw.get('source_url')
    if not isinstance(source_date, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', source_date):
        raise ValueError('配装来源日期需要 YYYY-MM-DD。')
    try:
        date.fromisoformat(source_date)
    except ValueError as exc:
        raise ValueError('配装来源日期无效。') from exc
    if not isinstance(source_url, str) or len(source_url) > 2048:
        raise ValueError('配装来源 URL 无效。')
    parsed = urlsplit(source_url)
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('配装来源需要无登录凭据的 HTTP(S) URL。')
    return source_date, source_url


def validate_pack(pack, skin_catalog=None, sticker_catalog=None):
    """Validate authored recipes, not proof of a player's live/complete Steam inventory."""
    if not isinstance(pack, dict) or pack.get('schema_version', 1) != 1 or type(pack.get('schema_version', 1)) is not int:
        raise ValueError('配装包只支持 schema_version 1。')
    pack_id = _key(pack.get('id'), '配装包 ID')
    player = str(pack.get('player') or '').casefold()
    if player == 'm0nesy':
        player = 'monesy'
    if player not in PLAYERS:
        raise ValueError('免费配装包仅支持 donk、ZywOo、m0NESY、NiKo。')
    source_date, source_url = _provenance(pack)
    if 'free' in pack and type(pack['free']) is not bool:
        raise ValueError('免费配装标记必须是布尔值。')
    if pack.get('free') is False or any(key in pack and _number(pack[key], '免费配装价格') != 0 for key in ('price', 'cost')):
        raise ValueError('这些配装包必须免费。')
    recipes = pack.get('items')
    if not isinstance(recipes, list) or not 1 <= len(recipes) <= MAX_PACK_ITEMS:
        raise ValueError('配装包需要 1-64 件物品。')
    skins = _skins(skin_catalog)
    keys, items = set(), []
    for raw in recipes:
        if not isinstance(raw, dict):
            raise ValueError('配装物品必须是对象。')
        item_key = _key(raw.get('id'), '配装物品 ID')
        if item_key in keys:
            raise ValueError('配装包内物品 ID 重复。')
        keys.add(item_key)
        sid = raw.get('skin_id')
        skin = skins.get(sid) if isinstance(sid, str) else None
        if not skin:
            raise ValueError('配装引用了目录中不存在的皮肤。')
        prepared = deepcopy(raw)
        defaults = raw.get('defaults')
        if defaults is not None:
            if (pack.get('quality') != 'public_loadout_template' or pack.get('source_precision') != 'finish_only'
                    or not isinstance(defaults, dict) or not defaults or set(defaults) - {'wear', 'seed'}):
                raise ValueError('默认参数必须明确标记为 finish_only 公开配装模板。')
            source_parameters = raw.get('source_parameters')
            if not isinstance(source_parameters, dict):
                raise ValueError('默认参数需要 source_parameters 明示来源未知值。')
            origin = {}
            for parameter, value in defaults.items():
                if parameter not in source_parameters or source_parameters[parameter] is not None:
                    raise ValueError('默认参数不能冒充已核验的选手实例参数。')
                if parameter in raw and raw[parameter] != value:
                    raise ValueError('实例参数与声明的模板默认值不一致。')
                prepared[parameter] = value
                origin[parameter] = 'declared_default'
            prepared['parameter_origin'] = origin
        appearance = normalize_instance(prepared, sticker_catalog)
        if appearance['def'] != _skin_def(skin) or appearance['paint'] != int(skin.get('paint') or 0):
            raise ValueError('配装的武器／涂装与所引用皮肤目录不符。')
        if 'wear' in appearance and ('min_float' in skin or 'max_float' in skin):
            lo = _number(skin.get('min_float', 0), '涂装磨损下限', 0, 1)
            hi = _number(skin.get('max_float', 1), '涂装磨损上限', 0, 1)
            if lo > hi:
                raise ValueError('涂装磨损限值顺序无效。')
            _number(appearance['wear'], '涂装磨损', lo, hi)
        if any(key in raw and raw[key] != skin.get(key) for key in ('slot', 'weapon')):
            raise ValueError('配装的武器槽位与皮肤目录不符。')
        items.append(appearance)
    result = deepcopy(pack)
    result.update(schema_version=1, id=pack_id, player=player,
                  display_name=str(pack.get('display_name') or PLAYERS[player]), free=True,
                  source_date=source_date, source_url=source_url, items=items)
    return result


def import_pack(inventory, next_id, pack, skin_catalog=None, sticker_catalog=None):
    """Free atomic copy/import, deduped by source pack ID + recipe item ID only."""
    _inventory(inventory)
    next_id = _integer(next_id, '下一库存编号', 1, 2147483647)
    normalized = validate_pack(pack, skin_catalog, sticker_catalog)
    skins = _skins(skin_catalog)
    rows = deepcopy(inventory)
    known_ids = {row['id'] for row in rows}
    known_sources = {(row.get('source_pack_id'), row.get('source_pack_item_id')) for row in rows
                     if row.get('source_pack_id') and row.get('source_pack_item_id')}
    added, skipped = [], []
    for recipe in normalized['items']:
        key = (normalized['id'], recipe['id'])
        if key in known_sources:
            skipped.append(recipe['id'])
            continue
        while f'inv.{next_id}' in known_ids:
            next_id += 1
        skin = skins[recipe['skin_id']]
        row = {name: deepcopy(skin[name]) for name in
               ('name', 'name_en', 'weapon', 'slot', 'rarity', 'min_float', 'max_float') if name in skin}
        row.update({name: deepcopy(recipe[name]) for name in
                    ('skin_id', 'def', 'paint', 'wear', 'seed', 'stickers', 'nametag', 'stattrak', 'tint', 'keychains') if name in recipe})
        row.update(id=f'inv.{next_id}', source='pro-pack', bound=True,
                   source_pack_id=normalized['id'], source_pack_item_id=recipe['id'],
                   source_pack_key=normalized['id'] + ':' + recipe['id'], source_player=normalized['player'],
                   source_display_name=normalized['display_name'], source_date=normalized['source_date'],
                   source_url=normalized['source_url'])
        row['provenance'] = {name: deepcopy(normalized[name]) for name in ('quality', 'source_precision') if name in normalized}
        row['provenance'].update({name: deepcopy(recipe[name]) for name in
                                  ('source_parameters', 'defaults', 'parameter_origin') if name in recipe})
        row.update(deepcopy(row['provenance']))
        row['hash'] = appearance_hash(row, sticker_catalog)
        rows.append(row)
        added.append(deepcopy(row))
        known_ids.add(row['id'])
        known_sources.add(key)
        next_id += 1
    return {'inventory': rows, 'next_id': next_id, 'added': added, 'skipped': skipped,
            'pack': normalized, 'message': f'免费入库 {len(added)} 件配装；跳过 {len(skipped)} 件已导入物品。赠送外观不可出售。'}
