"""One consumable per player, per-map frozen effects without permanent stats.

prepare() is pure. activate() follows a successful launch (or starts a local
simulation) in the caller's transaction. Retired sessions retain map effects.
"""
from copy import deepcopy
from datetime import date, timedelta
from ..world.ability import AXES, AXIS_LABEL

KEY = 'match_supplies_v1'
GRADES = {'normal': dict(bonus=3, price=1500, days=3, duration='map'),
          'strong': dict(bonus=5, price=5000, days=7, duration='series')}


def data(career, create=False):
    if create:
        return career.incident_state.setdefault(KEY, {'stock': [], 'prepared': {}, 'cooldowns': {}, 'active': {}})
    return getattr(career,'incident_state',{}).get(KEY,{})


def identity(player):
    from ..world.eras import player_id
    return player.get('player_id') or player_id(player['name'])


def series_key(season, match):
    ev,_ = season.find_match(match['id'])
    return f'{season.year}:{ev["id"]}:{match["id"]}'


def prepare(career, match, key, day, index=0, *, teams=None):
    cached = match.get('supply_maps',{}).get(str(index))
    if cached is not None:
        return deepcopy(cached)
    store = data(career)
    own = career.my_team(teams) if teams is not None else None
    eligible = {identity(p) for p in own.get('players', [])} if own else None
    effects = {}
    for pid, effect in store.get('active',{}).items():
        if eligible is not None and pid not in eligible:
            continue
        if effect['series'] == key and effect['duration']=='series':
            effects[pid] = deepcopy(effect)
    for pid, entry in store.get('prepared',{}).items():
        if eligible is not None and pid not in eligible:
            continue
        if entry['series'] != key or entry['map_index'] != index:
            continue
        effects[pid] = dict(entry, **GRADES[entry['grade']], activated=day)
    return effects


def activate(career, match, key, day, effects, index=0):
    if str(index) in match.get('supply_maps',{}):
        return
    store = data(career,True)
    for pid,effect in effects.items():
        prepared = store['prepared'].get(pid)
        if not prepared or prepared['item_id'] != effect['item_id']:
            continue
        if store['cooldowns'].get(pid,'')>day or pid in store['active']:
            raise ValueError('这名选手的药剂尚未冷却。')
        item = next((r for r in store['stock'] if r['id']==effect['item_id']),None)
        if item is None:
            raise ValueError('药剂库存已变化。')
        store['stock'].remove(item)
        del store['prepared'][pid]
        store['cooldowns'][pid]=(date.fromisoformat(day)+timedelta(days=effect['days'])).isoformat()
        store['active'][pid]=deepcopy(effect)
    match.setdefault('supply_maps',{})[str(index)] = deepcopy(effects)


def teams_with_effects(teams, effects):
    out = deepcopy(teams)
    for team in out:
        command_delta = 0.
        for p in team.get('players',[]):
            effect = effects.get(identity(p))
            if effect:
                p['_match_boost'] = {effect['axis']:effect['bonus']}
                if effect['axis']=='utility':
                    from ..world.ability import playing_stats
                    raw = playing_stats(dict(p, _match_boost={}))
                    command_delta += min(effect['bonus'],100-float(raw.get('utility',p.get('ability',70))))
        if command_delta:
            team['command']=min(100,team.get('command',70)+command_delta/max(1,len(team['players'])))
    return out


def finish_map(career, match, key, index):
    store = data(career)
    for pid,effect in list(store.get('active',{}).items()):
        if effect['series']==key and effect['duration']=='map' and effect['map_index']==index:
            del store['active'][pid]


def finish_series(career, key):
    store = data(career)
    for category in ('active','prepared'):
        for pid,effect in list(store.get(category,{}).items()):
            if effect['series']==key:
                del store[category][pid]


def targets(state):
    c,s=state.career,state.season
    mine=c.my_team(s.teams) or {}
    result=[]
    for ev in s.events:
        for match in ev.get('matches',[]):
            if match.get('played') or mine.get('name') not in (match.get('team_a'),match.get('team_b')):
                continue
            index=len(match.get('maps') or [])
            result.append(dict(id=series_key(s,match), match_id=match['id'], kind='career', map_index=index,
                label=f'{ev["name"]} · {match["team_a"]} vs {match["team_b"]} · {index+1}',
                started=str(index) in match.get('supply_maps',{}) or bool(match.get('cs2_session') or match.get('career3d_rts'))))
    for row in c.incident_state.get('career3d_service',{}).get('scrims',[]):
        if row['status']!='finished':
            result.append(dict(id='scrim:'+row['id'],match_id=row['id'],kind='scrim',map_index=0,
                label=f'{row["date"]} · {row["opponent"]} · {row["map"]}',
                started='0' in row.get('supply_maps',{}) or row['status']=='launched'))
    if getattr(c,'last_scrim','')!=s.date:
        row=data(c).get('daily_training',{}).get(s.date,{})
        result.append(dict(id='training:'+s.date,match_id=s.date,kind='training',map_index=0,
                           label='今日即时训练 / Training today',started=bool(c.training_session) or '0' in row.get('supply_maps',{})))
    return result


def training_holder(career, day, booking=None):
    if booking is not None:
        return booking, 'scrim:'+booking['id']
    return data(career,True).setdefault('daily_training',{}).setdefault(day,{}), 'training:'+day


def activate_training(career, season):
    session=career.training_session or {}
    if 'supply_intent' not in session:
        return
    booking=next((r for r in career.incident_state.get('career3d_service',{}).get('scrims',[]) if r['id']==session.get('booking_id')),None)
    holder,key=training_holder(career,session.get('date',season.date),booking)
    activate(career,holder,key,season.date,session['supply_intent'])


def projection(state):
    c=state.career
    team=c.my_team(state.season.teams) or {}
    store=data(c)
    return dict(stock=deepcopy(store.get('stock',[])), prepared=deepcopy(store.get('prepared',{})),
        active=deepcopy(store.get('active',{})),cooldowns=deepcopy(store.get('cooldowns',{})),
        targets=targets(state),players=[dict(id=identity(p),name=p['name'],you=bool(p.get('you') or p['name']==c.player_name)) for p in team.get('players',[])],
        catalog=[dict(id=axis+'-'+grade,axis=axis,grade=grade,name=AXIS_LABEL[axis],**values) for axis in AXES for grade,values in GRADES.items()],
        club_allowed=bool(team and not c.personal_transfers.get('player_only')),club_money=team.get('money',0),money=c.money)


def command(state, action, body):
    from ..services.business import guard_revision
    guard_revision(state,body)
    c,s=state.career,state.season
    team=c.my_team(s.teams)
    if not c.exists or not team or c.over() or c.unsigned:
        raise ValueError('加入队伍后才能准备赛前药剂。')
    store=data(c,True)
    if action=='buy':
        axis,grade=body.get('axis'),body.get('grade')
        if axis not in AXES or grade not in GRADES:
            raise ValueError('请选择药剂种类。')
        payer=body.get('payer','personal')
        price=GRADES[grade]['price']
        if payer not in ('club','personal') or payer=='club' and c.personal_transfers.get('player_only'):
            raise ValueError('只有俱乐部管理者能使用队伍经费。')
        balance=team['money'] if payer=='club' else c.money
        if balance<price:
            raise ValueError('资金不足。')
        if payer=='club': team['money']-=price
        else: c.money-=price
        seq=store['sequence']=store.get('sequence',0)+1
        item=dict(id=f'supply.{seq}',axis=axis,grade=grade,payer=payer,team_id=team['id'],
                  owner=identity(c.my_player(s.teams)) if payer=='personal' else '')
        store['stock'].append(item)
        c._record_cashflow(s.date,'club' if payer=='club' else 'pocket','supplies','购买赛前药剂',-price,balance-price)
        message='药剂已放入补给库存。'
    elif action=='cancel':
        pid=body.get('player_id')
        if pid not in store['prepared']:
            raise ValueError('没有待取消的药剂。')
        target=next((row for row in targets(state) if row['id']==store['prepared'][pid]['series']),None)
        if target and target['started']:
            raise ValueError('本图已经开始或启动结果待确认，请先处理比赛连接状态。')
        del store['prepared'][pid]
        message='已取消准备，药剂保留在库存。'
    elif action=='prepare':
        # A future reservation must not consume a supply for a player who was
        # subsequently transferred out. Release that reservation on this write,
        # while keeping projections and match previews read-only.
        roster_ids={identity(p) for p in team['players']}
        for old_pid in list(store['prepared']):
            if old_pid not in roster_ids:
                del store['prepared'][old_pid]
        pid=body.get('player_id')
        player=next((p for p in team['players'] if identity(p)==pid),None)
        target=next((r for r in targets(state) if r['id']==body.get('target')),None)
        item=next((r for r in store['stock'] if r['id']==body.get('item_id')),None)
        if not player or not target or target['started'] or not item:
            raise ValueError('请选择本队选手、未开始的地图和库存药剂。')
        if item['payer']=='personal' and item['owner']!=pid or item['payer']=='club' and item['team_id']!=team['id']:
            raise ValueError('个人药剂仅供自己使用，队伍药剂属于购买它的俱乐部。')
        if pid in store['active'] or store['cooldowns'].get(pid,'')>s.date or pid in store['prepared']:
            raise ValueError('同一选手只能准备一种药剂，并须等待冷却结束。')
        if any(r['item_id']==item['id'] for r in store['prepared'].values()):
            raise ValueError('这支药剂已经分配给选手。')
        store['prepared'][pid]=dict(item_id=item['id'],axis=item['axis'],grade=item['grade'],
                                   series=target['id'],map_index=target['map_index'])
        message='赛前药剂已准备，开赛时使用。'
    else:
        raise ValueError('没有这个补给操作。')
    c.save()
    return dict(reason=message)
