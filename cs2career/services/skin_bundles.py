"""Game-currency purchases of the existing, pinned public loadout templates.

No Steam inventory, live prices, network calls or game-file writes. The service
persists the money, inventory and durable purchase receipt together after this
command returns. Existing free imports are retained without charging or filling
in missing items. Core recipe validation and its provenance remain unchanged.
"""
from __future__ import annotations

from copy import deepcopy
from statistics import median


STORE_KEY = 'career3d_skin_bundles'
CURRENCY = 'game_coin'
TEMPLATE_NOTICE = '公开配装模板；磨损和图案沿用已声明的模拟默认值。仅使用游戏币，入库后可装备，不可转卖。'


def _store(career):
    return career.incident_state.get(STORE_KEY) or {'purchases': {}, 'requests': {}}


def _price_of(career, skin, market):
    """Use existing quotes; uncatalogued finishes use a matching slot's median."""
    from cs2career.career import skins
    sid = skin['id']
    if sid in market:
        return skins.quote_of(career, sid), 'catalog_quote'
    equivalent = next((row for row in market.values()
                       if skins._def_of(row) == skins._def_of(skin)
                       and int(row.get('paint') or 0) == int(skin.get('paint') or 0)), None)
    if equivalent:
        return skins.quote_of(career, equivalent['id']), 'same_finish_quote'
    candidates = [row for row in market.values() if row.get('slot') == skin.get('slot')]
    same_rarity = [row for row in candidates if row.get('rarity') == skin.get('rarity')]
    candidates = same_rarity or candidates
    if not candidates:
        raise ValueError('配装物品没有可用的游戏币定价参照。')
    return max(1, int(round(median(skins.quote_of(career, row['id']) for row in candidates)))), 'slot_quote_median'


def _quote(career, pack, catalog, prices=None):
    from cs2career.career import skins
    market = skins.skin_map()
    entries = []
    for recipe in pack['items']:
        skin = catalog[recipe['skin_id']]
        price, basis = _price_of(career, skin, market)
        entries.append({'id': recipe['id'], 'skin_id': skin['id'], 'name': skin['name'],
                        'name_en': skin.get('name_en', ''), 'slot': skin['slot'],
                        'rarity': skin.get('rarity', ''), 'price': price, 'price_basis': basis})
    price = sum(row['price'] for row in entries)
    if prices is not None and pack['id'] in prices:
        configured = prices[pack['id']]
        if type(configured) is not int or configured < 1:
            raise ValueError('配装目录价格必须是正整数游戏币。')
        price = configured
    return price, entries


def _ownership(career, pack):
    sources = {row.get('source_pack_item_id') for row in career.inventory
               if row.get('source_pack_id') == pack['id']}
    purchased = pack['id'] in _store(career)['purchases']
    imported = all(recipe['id'] in sources for recipe in pack['items'])
    # Old free recipes were bound and imported atomically. Any surviving
    # source item establishes the old entitlement; do not sell a replacement.
    return purchased or bool(sources), imported, purchased


def bundle_context(state, prices=None):
    """Bounded, read-only rows for skins.loadout_packs; prices is server data."""
    from cs2career.career import skins
    from cs2career.skin_art import manifest
    from cs2career.services.resources import cached_skin_art
    c = state.career
    data, art = skins.pro_bundle(), manifest()
    rows = []
    for pack in data['packs']:
        price, items = _quote(c, pack, data['skins'], prices)
        for item in items:
            item['art_path'] = cached_skin_art(item['skin_id'], art)
        owned, imported, purchased = _ownership(c, pack)
        affordable = c.money >= price
        reason = ('此配装已入库，保留现有物品，不会重复扣币或补发。' if owned
                  else '个人游戏币不足。' if not affordable else '')
        rows.append({'id': pack['id'], 'player': pack['player'], 'display_name': pack['display_name'],
                     'name': pack['display_name'] + ' 配装包', 'count': len(items), 'items': items,
                     'price': price, 'currency': CURRENCY, 'free': False, 'bound': True,
                     'owned': owned, 'imported': imported, 'purchased': purchased,
                     'buy_allowed': not owned and affordable, 'reason': reason,
                     'description': TEMPLATE_NOTICE, 'source_url': pack['source_url'],
                     'source_date': pack['source_date'], 'source_precision': pack.get('source_precision', ''),
                     'price_note': '单件采用现有游戏币目录报价；无同款报价时按同槽位目录估算合计。'})
    return rows


def buy_bundle(state, body, prices=None):
    """Validate and commit one complete purchase; the enclosing service saves it."""
    from cs2career.career import skins
    from cs2career.career.skin_crafts import import_pack
    c = state.career
    if not isinstance(body, dict):
        raise ValueError('配装购买请求必须是对象。')
    pack_id, request_id = body.get('id'), body.get('request_id')
    if not isinstance(pack_id, str) or not isinstance(request_id, str) or not 8 <= len(request_id) <= 100:
        raise ValueError('配装购买需要有效 ID 与 8 至 100 字符的 request_id。')
    store = _store(c)
    previous = store['requests'].get(request_id)
    if previous:
        if previous['id'] != pack_id:
            raise ValueError('这个 request_id 已用于另一个配装包。')
        inventory_ids = {row['id'] for row in c.inventory}
        imported = all(item_id in inventory_ids for item_id in previous['inventory_ids'])
        return {**deepcopy(previous), 'replayed': True, 'owned': True, 'imported': imported,
                'original_charge': previous['charged'], 'charged': 0, 'added': 0,
                'reason': '此配装已入库，保留现有物品，不会重复扣币或补发。'}
    data = skins.pro_bundle()
    pack = next((row for row in data['packs'] if row['id'] == pack_id), None)
    if pack is None:
        raise ValueError('没有这个公开配装包。')
    owned, imported, _purchased = _ownership(c, pack)
    if owned:
        return {'id': pack_id, 'reason': '此配装已入库，保留现有物品，不会重复扣币或补发。',
                'replayed': True, 'owned': True, 'imported': imported, 'charged': 0, 'added': 0}
    current = int(c.incident_state.get('career3d_service', {}).get('revision', 0))
    if type(body.get('revision')) is not int or body['revision'] != current:
        raise ValueError('库存或游戏币已变化，请刷新后再购买配装。')
    price, _items = _quote(c, pack, data['skins'], prices)
    if type(c.money) is not int or c.money < price:
        raise ValueError('个人游戏币不足。')
    prepared = import_pack(c.inventory, c.skin_seq + 1, pack, data['skins'], skins.sticker_catalog())
    if len(prepared['added']) != len(pack['items']) or prepared['skipped']:
        raise ValueError('配装已有库存记录，请刷新后查看，不会重复扣币。')
    reason = f"已用 {price:,} 游戏币购买 {pack['display_name']} 配装，{len(prepared['added'])} 件物品已入库。"
    receipt = {'id': pack_id, 'request_id': request_id, 'reason': reason, 'replayed': False,
               'owned': True, 'imported': True, 'charged': price, 'added': len(prepared['added']),
               'currency': CURRENCY, 'inventory_ids': [row['id'] for row in prepared['added']]}
    # All recipes, funds, revision and identity checks finish before mutation.
    c.money -= price
    c.inventory = prepared['inventory']
    c.skin_seq = prepared['next_id'] - 1
    c._record_cashflow(getattr(state.season, 'date', ''), 'pocket', 'skin',
                       pack['display_name'] + ' 配装包', -price, c.money)
    c.log.append(reason)
    updated = deepcopy(store)
    updated['purchases'][pack_id] = deepcopy(receipt)
    updated['requests'][request_id] = deepcopy(receipt)
    c.incident_state[STORE_KEY] = updated
    return receipt
