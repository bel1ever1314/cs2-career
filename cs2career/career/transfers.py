"""Player-controlled signings. Quotes and mutations share server-side rules."""
from copy import deepcopy
from ..world.ability import ability_of, refresh_team_command
from ..world.eras import player_id


def identity(p):
    return p.get('player_id') or player_id(p['name'])


def locked(season, team):
    name=team['name']
    return any((e.get('status')=='live' and (name in e.get('field',[]) or any(
        name in (m.get('team_a'),m.get('team_b')) for m in e.get('matches',[])))) or any(
        m.get('cs2_session') and name in (m.get('team_a'),m.get('team_b')) for m in e.get('matches',[]))
        for e in season.events)


def buyout_price(p):
    from .career import transfer_fee
    st=p.get('stats') or {}
    overall=ability_of(st,st['role_reference']) if st.get('role_reference_score') is not None else float(p.get('long_term_ability',p['ability']))
    multiplier=5 if overall>=90 else 3
    return transfer_fee(overall)*multiplier, multiplier


def outgoing(career, team, key=''):
    pool=[p for p in team['players'] if not p.get('you') and p['name']!=career.player_name]
    if key:
        found=[p for p in pool if identity(p)==key]
        if len(found)!=1: raise ValueError('请选择当前队内的一名队友作为替换对象，不能替换自己。')
        return found[0]
    if not pool: raise ValueError('没有可替换的队友。')
    return min(pool,key=lambda p:p['ability'])  # Old clients remain compatible.


def candidates(career, season):
    mine=career.my_team(season.teams)
    if not mine or career.unsigned or career.over(): return []
    from .career import transfer_fee, buy_chance
    rank=next((r for r in season.vrs.table(season.teams,season.date) if r['id']==mine['id']),{})
    rows=[]; own_locked=locked(season,mine)
    occupied={identity(p) for t in season.teams for p in t['players']}
    for seller, pool in [(None,career.free)]+[(t,t['players']) for t in season.teams if t['id']!=mine['id']]:
        for p in pool:
            price,mult=buyout_price(p); fee=transfer_fee(p['ability'])
            chance=buy_chance(rank.get('vrs',900),p['ability'],mine.get('money',0),fee)
            reason='赛事进行中，结束后再转会。' if own_locked or (seller and locked(season,seller)) else ''
            if seller and not reason and not any(identity(r) not in occupied and r.get('role')==p['role'] and
                    transfer_fee(r['ability'])<=seller.get('money',0)+price for r in career.free):
                reason='卖方暂无可签的同位置替补，暂不能买断。'
            rows.append(dict(player_id=identity(p),name=p['name'],role=p['role'],ability=p['ability'],
                age=p.get('age'),potential=p.get('potential'),note=p.get('note',''),academy_year=p.get('academy_year'),
                seller_id=seller['id'] if seller else '',seller=seller['name'] if seller else '自由球员',
                normal_fee=fee if not seller else None,normal_chance=(max(.2,chance) if chance>=.18 else 0) if not seller else None,
                negotiation_fee=int(fee*.08),guaranteed_fee=price,multiplier=mult,blocked=reason))
    return sorted(rows,key=lambda p:(-p['ability'],p['player_id']))


def guaranteed(career, season, target_id, seller_id, replace_id, expected_fee=None):
    from .career import _signed, transfer_fee
    from ..world.roles import apply_roles
    mine=career.my_team(season.teams)
    if not mine or career.unsigned or career.over(): raise ValueError('当前生涯不能签约。')
    seller=next((t for t in season.teams if t['id']==seller_id and t is not mine),None) if seller_id else None
    if seller_id and seller is None: raise ValueError('卖方队伍不存在，或选手已经在你的队里。')
    if locked(season,mine) or (seller and locked(season,seller)):
        raise ValueError('双方参赛期间不能变更阵容，请等赛事结束。')
    pool=seller['players'] if seller else career.free
    found=[p for p in pool if identity(p)==target_id]
    if len(found)!=1: raise ValueError('选手已转会或身份不唯一，请刷新报价。')
    target=found[0]; price,_=buyout_price(target)
    if not seller and any(identity(p)==target_id for t in season.teams for p in t['players']):
        raise ValueError('这名选手已有现役合同，请刷新并使用现役买断。')
    if expected_fee is not None and int(expected_fee)!=price: raise ValueError('报价已变化，请刷新后确认。')
    if mine.get('money',0)<price: raise ValueError(f'保签需要 ${price:,}，俱乐部资金不足。')
    if not replace_id: raise ValueError('保签前请选择要替换的队友。')
    leaving=outgoing(career,mine,replace_id)
    if len(mine['players'])!=5 or (seller and len(seller['players'])!=5): raise ValueError('阵容不是五人，不能执行转会。')
    replacement=None; replacement_fee=0
    if seller:
        occupied={identity(p) for t in season.teams for p in t['players']}
        reserves=[p for p in career.free if identity(p) not in occupied and p.get('role')==target['role']
                  and transfer_fee(p['ability'])<=seller.get('money',0)+price]
        if not reserves: raise ValueError('卖方暂时没有可签的同位置自由球员，不能留下空缺阵容。')
        replacement=max(reserves,key=lambda p:(p['ability'],identity(p)))
        replacement_fee=transfer_fee(replacement['ability'])
    # Everything that can be rejected is checked before money or rosters move.
    incoming=_signed(deepcopy(target)); departing=deepcopy(leaving)
    reserve=_signed(deepcopy(replacement)) if replacement else None
    mine['players']=[p for p in mine['players'] if p is not leaving]+[incoming]
    mine['money']-=price; mine['custom_roles']=True
    removed={identity(replacement)} if replacement else {target_id}
    career.free=[p for p in career.free if identity(p) not in removed]
    departing.update(team=None,fee=transfer_fee(departing['ability']))
    if departing['name'] not in career.hidden: career.free.append(departing)
    if seller:
        seller['players']=[p for p in seller['players'] if p is not target]+[reserve]
        seller['money']=seller.get('money',0)+price-replacement_fee
        seller['custom_roles']=True
        refresh_team_command(seller)
    apply_roles([mine]+([seller] if seller else []))
    refresh_team_command(mine)
    career._record_cashflow(season.date,'club','transfer',f'保签 {target["name"]}',-price,mine['money'])
    msg=f'花费 ${price:,} 保签 {target["name"]}，{leaving["name"]} 离队。'
    if seller: msg+=f' {seller["name"]} 收到买断费，并签下 {replacement["name"]} 补位。'
    career.log.append(msg);career.save()
    return msg
