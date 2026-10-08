"""Personal, fictional-currency series predictions. Reads never simulate/save.

The caller owns the application transaction. Quotes contain no outcome data
and consume no RNG. Orders and payouts live in the same career save as money.
"""
from copy import deepcopy
from decimal import Decimal, ROUND_FLOOR
import hashlib
import json

from ..world import MAPS
from ..world.map_form import expected, code

KEY = 'match_predictions_v1'
RETURN_FACTOR = Decimal('0.95')
MIN_PROBABILITY = .10
MAX_PROBABILITY = .90
PAGE_SIZE = 12


def data(career):
    return career.incident_state.get(KEY, {})


def identity(season, event, match):
    return f"{season.year}:{event['id']}:{match['id']}"


def teams(season, match):
    index = {t['name']: t for t in season.teams}
    return index.get(match.get('team_a')), index.get(match.get('team_b'))


def started(match):
    return bool(match.get('played') or match.get('maps') or match.get('started')
                or match.get('started_at') or match.get('cs2_session')
                or match.get('career3d_rts') or match.get('winner'))


def eligible(career, season, event, match):
    a, b = teams(season, match)
    if (not career.exists or career.over() or not a or not b or a['id'] == b['id']
            or career.team_id in (a['id'], b['id']) or started(match)
            or event.get('status') != 'live' or match.get('forfeit')
            or match.get('cancelled') or match.get('canceled')
            or match.get('best_of', 3) not in (1, 3, 5)):
        return False
    return identity(season, event, match) not in data(career).get('orders', {})


def series_probability(probabilities):
    """Exact first-to-N probability, with no generated maps or random draws."""
    need = len(probabilities) // 2 + 1
    states = {(0, 0): 1.0}
    won = 0.0
    for p in probabilities:
        following = {}
        for (a, b), weight in states.items():
            if a + 1 == need:
                won += weight * p
            else:
                following[a + 1, b] = following.get((a + 1, b), 0) + weight * p
            if b + 1 < need:
                following[a, b + 1] = following.get((a, b + 1), 0) + weight * (1 - p)
        states = following
    return max(MIN_PROBABILITY, min(MAX_PROBABILITY, won))


def quote(career, season, event, match):
    a, b = teams(season, match)
    best_of = int(match.get('best_of', 3))
    pool = list(event.get('map_pool') or MAPS)
    frozen = (match.get('veto') or {}).get('order') or []
    manual = match.get('career3d_veto') or {}
    if len(frozen) == best_of and (not manual or manual.get('complete')):
        chances = [expected(a, b, code(name)) for name in frozen]
    else:
        average = sum(expected(a, b, code(name)) for name in pool) / len(pool)
        chances = [average] * best_of
    p = series_probability(chances)
    odds = {t['id']: int((RETURN_FACTOR / Decimal(str(probability)) * 100)
                        .to_integral_value(rounding=ROUND_FLOOR))
            for t, probability in ((a, p), (b, 1 - p))}
    row = dict(key=identity(season, event, match), year=season.year,
               event_id=event['id'], event_name=event['name'], match_id=match['id'],
               date=match['date'], best_of=best_of,
               team_a=dict(id=a['id'], name=a['name']), team_b=dict(id=b['id'], name=b['name']),
               odds_hundredths=odds)
    row['quote_id'] = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
    return row


def available(career, season):
    return [(e, m) for e in season.events for m in e.get('matches', [])
            if eligible(career, season, e, m)]


def page(career, season, query=None):
    query = query or {}
    tab = query.get('view', 'available')
    if tab not in ('available', 'records'):
        raise ValueError('没有这个竞猜页面。')
    index = max(1, int(query.get('page', 1)))
    if tab == 'available':
        pairs = sorted(available(career, season), key=lambda pair: (pair[1]['date'], pair[0]['id'], pair[1]['id']))
        rows = [quote(career, season, e, m) for e, m in pairs[(index-1)*PAGE_SIZE:index*PAGE_SIZE]]
        count = len(pairs)
    else:
        records = list(reversed(list(data(career).get('orders', {}).values())))
        rows = deepcopy(records[(index-1)*PAGE_SIZE:index*PAGE_SIZE])
        count = len(records)
    return dict(rows=rows, total=count, page=index, page_size=PAGE_SIZE, money=career.money)


def summary(career):
    settled = [o for o in data(career).get('orders', {}).values() if o['status'] != 'pending']
    return dict(count=len(settled), returned=sum(o['payout'] for o in settled))


def buy(career, season, body):
    pair = next(((e, m) for e in season.events for m in e.get('matches', [])
                 if identity(season, e, m) == body.get('key')), None)
    if not pair or not eligible(career, season, *pair):
        raise ValueError('这场比赛已开赛、已购买或不符合竞猜条件，请刷新列表。')
    event, match = pair
    row = quote(career, season, event, match)
    if row['quote_id'] != body.get('quote_id'):
        raise ValueError('赔率或对阵已变化，请刷新后重新确认。')
    stake = body.get('stake')
    if type(stake) is not int or stake <= 0 or stake > career.money:
        raise ValueError('请输入不超过个人余额的正整数金额。')
    ids = [row['team_a']['id'], row['team_b']['id']]
    selection, outcome = body.get('team_id'), body.get('outcome')
    if selection not in ids or outcome not in ('win', 'lose'):
        raise ValueError('请选择这场比赛中的队伍及赢或输。')
    winner_id = selection if outcome == 'win' else next(t for t in ids if t != selection)
    rate = row['odds_hundredths'][winner_id]
    payout = stake * rate // 100
    order = dict(row, stake=stake, selected_team_id=selection, outcome=outcome,
                 predicted_winner_id=winner_id, locked_odds=rate,
                 possible_return=payout, status='pending', payout=0, placed_date=season.date)
    career.incident_state.setdefault(KEY, {'orders': {}})['orders'][row['key']] = order
    career.money -= stake
    career._record_cashflow(season.date, 'pocket', 'prediction', '赛事竞猜 · ' + event['name'], -stake, career.money)
    return dict(reason='竞猜已确认，比赛结束后自动结算。', prediction_key=row['key'])


def reconcile(career, season):
    """Called at accepted result/command boundaries, never by projections."""
    orders = data(career).get('orders', {})
    pending = [o for o in orders.values() if o['status'] == 'pending']
    if not pending:
        return []
    pairs = {identity(season, e, m): (e, m) for e in season.events for m in e.get('matches', [])}
    settled = []
    for order in pending:
        pair = pairs.get(order['key'])
        if not pair:
            continue  # Missing data is unknown, never silently a loss/refund.
        event, match = pair
        a, b = teams(season, match)
        reason = ''
        if (event.get('status') in ('cancelled', 'canceled') or match.get('cancelled')
                or match.get('canceled') or match.get('forfeit') or match.get('team_b') == 'BYE'):
            reason = '比赛取消、轮空或判罚弃权'
        elif career.team_id in (order['team_a']['id'], order['team_b']['id']):
            reason = '你已加入参赛队伍'
        elif not a or not b or {a['id'], b['id']} != {order['team_a']['id'], order['team_b']['id']}:
            reason = '参赛队伍发生变化'
        if reason:
            status, payout = 'refunded', order['stake']
        elif match.get('played') and match.get('winner') in (a['name'], b['name']):
            winner = a['id'] if match['winner'] == a['name'] else b['id']
            status = 'won' if winner == order['predicted_winner_id'] else 'lost'
            payout = order['possible_return'] if status == 'won' else 0
            reason = '竞猜命中' if status == 'won' else '竞猜未命中'
        else:
            continue
        order.update(status=status, payout=payout, settled_date=season.date, reason=reason,
                     series=match.get('series', ''), report_available=bool(match.get('played') and not match.get('forfeit')))
        career.money += payout
        career._record_cashflow(season.date, 'pocket', 'prediction', reason + ' · ' + order['event_name'], payout, career.money)
        settled.append(order['key'])
    return settled
