"""Local market, bounded price history and custody. Reads never settle a day.

Dates and item sequence numbers seed a private PRNG; none of these operations
consume the career or match random streams. Caller owns the save transaction.
"""
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import math
import random

from . import skins
from .market_balance import HISTORY_DAYS, MAX_BATCH, RUMOR_PRICE, SELL_FEES, SKILL_COSTS

KEY = 'skin_market_v1'
WEARS = (('fn', '崭新出厂', 0., .07, 1.65), ('mw', '略有磨损', .07, .15, 1.25),
         ('ft', '久经沙场', .15, .38, 1.), ('ww', '破损不堪', .38, .45, .8),
         ('bs', '战痕累累', .45, 1., .65))
SKILLS = {'analysis': '行情分析', 'judgment': '消息甄别', 'bargaining': '交易议价'}
RUMOR_KINDS = ('bullish', 'bearish')


def data(career, *, create=False):
    if create:
        return career.incident_state.setdefault(KEY, {'history': [], 'custody': [], 'skills': {}, 'rumors': []})
    return (getattr(career, 'incident_state', {}) or {}).get(KEY, {})


def rng(career, *parts):
    identity = (getattr(career, 'team_id', ''), getattr(career, 'player_name', ''))
    digest = hashlib.sha256(repr((identity, parts)).encode()).hexdigest()
    return random.Random(int(digest, 16))


def level(career, key):
    return max(0, min(3, int(data(career).get('skills', {}).get(key, 0))))


def fee(career):
    return SELL_FEES[level(career, 'bargaining')]


def variants(row):
    minimum, maximum = float(row.get('min_float', 0)), float(row.get('max_float', 1))
    out = []
    for key, name, lo, hi, multiplier in WEARS:
        low, high = max(minimum, lo), min(maximum, hi)
        if low < high or minimum == maximum and lo <= minimum < hi:
            out.append(dict(wear_id=key, wear_name=name, min_float=low, max_float=high, multiplier=multiplier))
    return out


def variant(row, wear_id):
    found = next((v for v in variants(row) if v['wear_id'] == wear_id), None)
    if not found:
        raise ValueError('这件饰品没有所选磨损。')
    return found


def wear_id(value):
    return next((key for key, _, _, hi, _ in WEARS if float(value) < hi), 'bs')


def quote(career, sid, wear, prices=None):
    row = skins.skin_map().get(sid)
    if not row:
        raise ValueError('市场上没有这件饰品。')
    v = variant(row, wear)
    base = skins.quote_of(career, sid) if prices is None else prices.get(sid)
    return max(1, round(base * v['multiplier'])) if base is not None else None


def proceeds(career, value):
    return max(0, math.floor(int(value) * (1 - fee(career))))


def item_spot(career, item):
    """Withdrawal preserves the exact wear quote; legacy stock keeps its price."""
    sid = item.get('skin_id', '')
    if item.get('market_wear_id'):
        return quote(career, sid, item['market_wear_id'])
    return skins.quote_of(career, sid) if sid else int(item.get('sell') or 0)


def _signal(career, day):
    rows = sorted(skins.skin_map())
    if not rows:
        return {}
    roll = rng(career, 'rumor', day)
    sid = roll.choice(rows)
    direction = roll.choice((-1, 1))
    honest = roll.random() < .62
    return dict(id=day, skin_id=sid, direction=direction, pressure=direction if honest else -direction,
                expires=(date.fromisoformat(day) + timedelta(days=3)).isoformat())


def _close_prices(career, day, prices):
    """The existing daily market rule, pure so informants cannot move prices."""
    pressure = {}
    for ago in range(1, 4):
        signal = _signal(career, (date.fromisoformat(day) - timedelta(days=ago)).isoformat())
        if signal:
            pressure[signal['skin_id']] = pressure.get(signal['skin_id'], 0) + signal['pressure'] * .025
    result = dict(prices)
    for row in skins.catalog()['skins']:
        sid = row['id']
        lo, hi = skins.quote_band(row)
        change = rng(career, 'close', day, sid).uniform(-.07, .07) + pressure.get(sid, 0)
        result[sid] = max(lo, min(hi, round(prices[sid] * (1 + change))))
    return result


def held_skin_ids(career):
    known = skins.skin_map()
    ids = {item.get('skin_id') for item in career.inventory if item.get('skin_id') in known}
    ids.update(lot['skin_id'] for lot in data(career).get('custody', [])
               if lot.get('items') and lot.get('skin_id') in known)
    return sorted(ids)


def _rumor_kind(row):
    # Legacy notes used one daily slot; retain their purchased direction.
    return row.get('kind') or ('bullish' if row.get('direction', 1) > 0 else 'bearish')


def _typed_signal(career, day, kind):
    candidates = sorted(skins.skin_map()) if kind == 'bullish' else held_skin_ids(career)
    if not candidates:
        raise ValueError('暂无持有饰品；买入后可购买看跌消息。' if kind == 'bearish' else '市场暂无饰品。')
    direction = 1 if kind == 'bullish' else -1
    roll = rng(career, 'typed-rumor-v1', day, kind)
    prices = {sid: skins.quote_of(career, sid) for sid in skins.skin_map()}
    projected = dict(prices)
    for offset in range(1, 4):
        # An old save without a close gets its first history sample, not a move.
        if offset == 1 and not data(career).get('history'):
            continue
        projected = _close_prices(career, (date.fromisoformat(day) + timedelta(days=offset)).isoformat(), projected)
    # Pick a fallible tip from the existing market path, never change that path
    # to make the purchased message come true. No match/career RNG is consumed.
    expected = direction if roll.random() < .62 else -direction
    pool = [sid for sid in candidates if (projected[sid] - prices[sid]) * expected > 0]
    sid = roll.choice(pool or candidates)
    return dict(id=day + ':' + kind, kind=kind, skin_id=sid, direction=direction,
                expires=(date.fromisoformat(day) + timedelta(days=3)).isoformat())


def tick(career, day):
    """One close per calendar date; migration starts today, never fabricates history."""
    store = data(career, create=True)
    history = store.setdefault('history', [])
    if history and history[-1]['date'] >= day:
        return
    skins.ensure_quotes(career)
    career.skin_quotes_prev = dict(career.skin_quotes)
    if history:
        career.skin_quotes = _close_prices(career, day, career.skin_quotes)
    history.append({'date': day, 'prices': dict(career.skin_quotes)})
    cutoff = (date.fromisoformat(day) - timedelta(days=HISTORY_DAYS - 1)).isoformat()
    store['history'] = [h for h in history if h['date'] >= cutoff][-HISTORY_DAYS:]
    store['rumors'] = [r for r in store.get('rumors', []) if r['date'] >= cutoff]


def changes(career, sid, day):
    history = data(career).get('history', [])
    spot = skins.quote_of(career, sid)
    values = {}
    for n in (1, 7, 30):
        target = (date.fromisoformat(day) - timedelta(days=n)).isoformat()
        prior = next((h['prices'].get(sid) for h in reversed(history) if h['date'] == target), None)
        values['change_' + str(n)] = round((spot / prior - 1) * 100, 2) if prior else None
    return values


def decorate(career, row, wear, day):
    from ..services.resources import cached_skin_art
    from ..skin_art import manifest
    v = variant(row, wear)
    spot = quote(career, row['id'], wear)
    return dict(row, **v, spot=spot, sell=proceeds(career, spot),
                art_path=cached_skin_art(row['id'], manifest()), **changes(career, row['id'], day))


def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{label}必须为 {low} 至 {high} 的整数。')
    return value


def page(career, day, query=None):
    query = query or {}
    minimum = float(query.get('min_price') or 0)
    maximum = float(query.get('max_price') or 1e15)
    if not all(math.isfinite(v) and v >= 0 for v in (minimum, maximum)) or minimum > maximum:
        raise ValueError('请输入有效的价格区间。')
    rows = []
    for row in skins.catalog()['skins']:
        if query.get('search') and str(query['search']).casefold() not in (row['name'] + ' ' + row['weapon']).casefold():
            continue
        if query.get('slot') and row['slot'] != query['slot']:
            continue
        if query.get('rarity') and row['rarity'] != query['rarity']:
            continue
        for v in variants(row):
            if query.get('wear') and v['wear_id'] != query['wear']:
                continue
            spot = quote(career, row['id'], v['wear_id'])
            if spot < minimum or spot > maximum:
                continue
            rows.append(dict(row, **v, spot=spot, **changes(career, row['id'], day)))
    key = query.get('sort', 'price')
    if key not in ('price', 'change_1', 'change_7', 'change_30', 'name'):
        raise ValueError('请选择价格、名称或涨跌幅排序。')
    key = 'spot' if key == 'price' else key
    present = [r for r in rows if r.get(key) is not None]
    missing = [r for r in rows if r.get(key) is None]
    present.sort(key=lambda r: (r[key], r['id'], r['wear_id']), reverse=query.get('order') == 'desc')
    rows = present + missing
    index = max(1, int(query.get('page') or 1))
    size = max(1, min(48, int(query.get('page_size') or 18)))
    selected = rows[(index-1)*size:index*size]
    from ..services.resources import cached_skin_art
    from ..skin_art import manifest
    art = manifest()
    for row in selected:
        row.update(art_path=cached_skin_art(row['id'], art), sell=proceeds(career, row['spot']))
    return dict(rows=selected, total=len(rows), page=index, page_size=size, money=career.money, fee=fee(career),
                slots=sorted({r['slot'] for r in skins.catalog()['skins']}),
                rarities=sorted({r['rarity'] for r in skins.catalog()['skins']}),
                wears=[dict(id=w[0], name=w[1]) for w in WEARS])


def detail(career, day, sid, wear):
    row = skins.skin_map().get(sid)
    if not row:
        raise ValueError('饰品不存在。')
    result = decorate(career, row, wear, day)
    history = data(career).get('history', [])
    result['history'] = [dict(date=h['date'], price=quote(career, sid, wear, h['prices']))
                         for h in history if sid in h['prices']]
    lots = [l for l in data(career).get('custody', []) if l['skin_id'] == sid and l['wear_id'] == wear]
    result['quantity'] = sum(len(l['items']) for l in lots)
    result['cost'] = sum(l['unit_cost'] * len(l['items']) for l in lots)
    result['net_value'] = proceeds(career, result['spot'] * result['quantity'])
    result['profit'] = result['net_value'] - result['cost']
    prices = [h['price'] for h in result['history']]
    analysis = level(career, 'analysis')
    result['analysis_level'] = analysis
    if analysis and prices:
        result['analysis'] = dict(low=min(prices), high=max(prices), mean=round(sum(prices)/len(prices)))
        if analysis >= 2:
            moves = [(b/a-1)*100 for a,b in zip(prices, prices[1:])]
            result['analysis']['volatility'] = round((sum(x*x for x in moves)/max(1,len(moves))) ** .5, 2)
        if analysis >= 3:
            result['analysis']['break_even'] = math.ceil(result['cost']/max(1,result['quantity'])/(1-fee(career)))
    return result


def custody(career, day):
    out = []
    for lot in data(career).get('custody', []):
        row = decorate(career, skins.skin_map()[lot['skin_id']], lot['wear_id'], day)
        count = len(lot['items'])
        out.append(dict(row, lot_id=lot['id'], quantity=count, unit_cost=lot['unit_cost'],
                        cost=lot['unit_cost']*count, net_value=proceeds(career, row['spot']*count),
                        profit=proceeds(career, row['spot']*count)-lot['unit_cost']*count))
    return out


def merchant(career, day):
    owned = data(career).get('rumors', [])
    today = next((r for r in owned if r['date'] == day), None)
    result = dict(price=RUMOR_PRICE, purchased=bool(today), skills=[dict(id=k, name=v, level=level(career,k),
        cost=SKILL_COSTS[level(career,k)] if level(career,k)<3 else None) for k,v in SKILLS.items()], rumors=[])
    held = held_skin_ids(career)
    result['offers'] = [dict(kind=kind, price=RUMOR_PRICE,
        purchased=any(r['date'] == day and _rumor_kind(r) == kind for r in owned),
        available=bool(skins.skin_map()) if kind == 'bullish' else bool(held),
        reason='暂无持有饰品；买入后可购买看跌消息。' if kind == 'bearish' and not held else '')
        for kind in RUMOR_KINDS]
    for rumor in reversed(owned):
        r = {k: v for k, v in rumor.items() if k != 'pressure'}
        r['name'] = skins.skin_map().get(r['skin_id'], {}).get('name', r['skin_id'])
        catalog_row = skins.skin_map().get(r['skin_id'])
        choices = variants(catalog_row) if catalog_row else []
        r['detail_target'] = (dict(id=r['skin_id'], wear_id=next(
            (v['wear_id'] for v in choices if v['wear_id'] == 'ft'), choices[0]['wear_id'])) if choices else None)
        r['spot'] = skins.quote_of(career, r['skin_id'])
        if day >= r['expires']:
            close = next((h['prices'].get(r['skin_id']) for h in data(career).get('history', []) if h['date']==r['expires']), None)
            r['outcome_pct'] = round((close/r['start_price']-1)*100,2) if close else None
        uncertainty = (30, 20, 10, 5)[level(career, 'judgment')]
        # An estimate of the source's base reliability, never hidden truth.
        estimate = 62 + rng(career, 'assessment', r['id']).uniform(-uncertainty, uncertainty)
        r['reliability'] = f'{max(5,round(estimate-uncertainty))}–{min(95,round(estimate+uncertainty))}%'
        result['rumors'].append(r)
    return result


def command(career, day, action, body):
    store = data(career, create=True)
    amount = 0
    if action == 'buy':
        sid, wear = body.get('id'), body.get('wear', 'ft')
        row = skins.skin_map().get(sid)
        if not row:
            raise ValueError('饰品不存在。')
        v = variant(row, wear)
        count = _integer(body.get('quantity', 1), 1, MAX_BATCH, '数量')
        spot = quote(career, sid, wear)
        amount = -spot*count
        if body.get('expected_total') != -amount:
            raise ValueError('报价已变化，请重新确认总价。')
        if career.money < -amount:
            raise ValueError('个人资金不足。')
        items = []
        for _ in range(count):
            career.skin_seq += 1
            roll = rng(career, 'item', career.skin_seq, sid, wear)
            value = min(math.nextafter(v['max_float'], v['min_float']), roll.uniform(v['min_float'],v['max_float']))
            items.append(dict(id=f'inv.{career.skin_seq}', skin_id=sid, name=row['name'], weapon=row['weapon'],
                slot=row['slot'], rarity=row['rarity'], wear=value, source='market',
                market_wear_id=wear, market_unit_cost=spot,
                seed=roll.randint(1,1000), **{'def': skins._def_of(row), 'paint': skins._paint_of(row)}))
        store.setdefault('custody', []).append(dict(id=items[0]['id'], skin_id=sid, wear_id=wear,
                                                    unit_cost=spot, date=day, items=items))
        message = f'已购买 {count} 件 {row["name"]}，保存在市场暂存。'
    elif action in ('withdraw', 'sell'):
        lot = next((l for l in store.get('custody', []) if l['id']==body.get('lot_id')), None)
        if not lot:
            raise ValueError('这批饰品已处理，请刷新。')
        count = _integer(body.get('quantity', 1), 1, min(MAX_BATCH,len(lot['items'])), '数量')
        if action == 'withdraw':
            career.inventory.extend(deepcopy(lot['items'][:count]))
            message = f'已提取 {count} 件饰品到仓库。'
        else:
            amount = proceeds(career, quote(career,lot['skin_id'],lot['wear_id'])*count)
            if body.get('expected_total') != amount:
                raise ValueError('卖出报价已变化，请重新确认。')
            message = f'已出售 {count} 件饰品，扣除手续费后到账 ${amount:,}。'
        del lot['items'][:count]
        store['custody'] = [l for l in store['custody'] if l['items']]
    elif action == 'skill':
        key = body.get('skill')
        if key not in SKILLS or level(career,key)>=3:
            raise ValueError('请选择尚未满级的交易技能。')
        amount = -SKILL_COSTS[level(career,key)]
        if career.money < -amount:
            raise ValueError('个人资金不足。')
        store.setdefault('skills', {})[key] = level(career,key)+1
        message = SKILLS[key] + '已升级。'
    elif action == 'rumor':
        kind = body.get('kind', 'bullish')
        if kind not in RUMOR_KINDS:
            raise ValueError('请选择看涨或看跌消息。')
        if any(r['date']==day and _rumor_kind(r)==kind for r in store.get('rumors', [])):
            return {'reason':'今天的这类消息已经买过了。', 'replayed':True}
        if career.money < RUMOR_PRICE:
            raise ValueError('个人资金不足。')
        signal = _typed_signal(career,day,kind)
        store.setdefault('rumors', []).append(dict(signal, date=day, start_price=skins.quote_of(career,signal['skin_id'])))
        amount = -RUMOR_PRICE
        message = '消息已记入市场笔记。'
    else:
        raise ValueError('没有这个市场操作。')
    career.money += amount
    if amount:
        career._record_cashflow(day, 'pocket', 'skin_market', message, amount, career.money)
    career.save()
    return {'reason': message}
