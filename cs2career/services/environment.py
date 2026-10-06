"""Purchased club facilities and movable home decor, on the existing wallets.

The temporary two-save journal is removed after commit: decorating does not
create an unlimited history of automatic saves. Read projections are pure.
"""
from collections import Counter, deque
from copy import deepcopy
from functools import lru_cache
import base64
import gzip
import hashlib
import json
import math
import re
from pathlib import Path

from cs2career.paths import data_file, save_root
from cs2career.manual_saves import atomic_bytes, encode

JOURNAL = 'environment.pending.json'
NAMES = ('season.json', 'career.json')
STORE = 'career3d_environment'
TIERS = ('academy', 'standard', 'elite')
DEFAULT_HOME = {'owned': ['wall_cream', 'floor_oak'], 'placed': [], 'wallpaper': 'cream', 'floor': 'oak'}
FIXED = [(-2, -.8, 1.84, 2.85), (-.65, -1.94, .65, .65),
         (1.4, -2.01, 2.5, .98), (1.35, -.94, .7, .68),
         (1.72, .83, 1.03, .96), (2.59, 2.14, .83, .72), (.05, 1.06, 1.24, 1.24)]
ANCHORS = [(-1.45, 1.35), (-1.5, 1.1), (.4, -1.2), (2.1, 2.2)]


@lru_cache(maxsize=1)
def catalog():
    return json.loads(data_file('career3d_environment.json').read_text('utf-8'))


def _saved(state):
    return state.career.incident_state.get(STORE, {})


def _default_tier(state, team):
    name = team.get('name', '')
    if name.casefold() in {n.casefold() for n in catalog()['elite_clubs']}:
        return 'elite'
    if any(word in name.casefold() for word in ('academy', 'junior', 'youth', '青训')):
        return 'academy'
    if team.get('id') == 'your-team' or getattr(state.career, 'mode', '') == 'create':
        return 'academy'
    return 'standard'


def _club(state):
    team = state.career.my_team(state.season.teams) or {}
    saved = _saved(state).get('clubs', {}).get(team.get('id', ''), {})
    initial = _default_tier(state, team)
    tier = saved.get('tier', initial)
    if tier not in TIERS:
        tier = initial
    facilities = {row['id']: max(1, min(3, int(saved.get('facilities', {}).get(row['id'], 1))))
                  for row in catalog()['facilities']}
    return team, tier, facilities


def _home(state):
    return deepcopy(_saved(state).get('home', DEFAULT_HOME))


def _blocked(state):
    from cs2career.services.matches import career_cs2_pending
    if state.career.training_session or state.arena.pending or career_cs2_pending(state):
        return '请先结束当前比赛，再装修或升级设施。'
    if not state.career.exists or state.career.retired or state.career.banned:
        return '当前生涯不能购买设施或家具。'
    return ''


def environment_context(state):
    team, tier, facilities = _club(state)
    tier_row = next(row for row in catalog()['tiers'] if row['id'] == tier)
    next_tier = catalog()['tiers'][TIERS.index(tier)+1] if tier != 'elite' else None
    upgrades = []
    for row in catalog()['facilities']:
        level = facilities[row['id']]
        upgrades.append(dict(deepcopy(row), level=level, current=deepcopy(row['levels'][level-1]),
                             next=deepcopy(row['levels'][level]) if level < 3 else None))
    home = _home(state)
    home.update(catalog=deepcopy(catalog()['home_catalog']), balance=state.career.money,
                bounds=[-3.1, 3.1, -2.65, 2.7], fixed=[list(r) for r in FIXED], anchors=ANCHORS)
    return dict(version=1, blocked=_blocked(state),
        club=dict(team_id=team.get('id', ''), tier=tier, tier_name=tier_row['name'],
                  tier_name_en=tier_row['name_en'], facilities=facilities, upgrades=upgrades,
                  next_tier=deepcopy(next_tier), balance=int(team.get('money') or 0)), home=home)


def _overlap(a, b, margin=0):
    return abs(a[0]-b[0]) < (a[2]+b[2])/2+margin and abs(a[1]-b[1]) < (a[3]+b[3])/2+margin


def validate_layout(placements, home):
    if not isinstance(placements, list) or len(placements) > 24:
        raise ValueError('房间最多摆放 24 件家具。')
    items = {row['id']: row for row in catalog()['home_catalog'] if row['kind'] == 'furniture'}
    owned, used, ids, rects, out = Counter(home['owned']), Counter(), set(), [], []
    for row in placements:
        if not isinstance(row, dict) or row.get('item') not in items:
            raise ValueError('请使用已经购买的家具。')
        item = items[row['item']]
        ident = row.get('id')
        if not isinstance(ident, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', ident) or ident in ids:
            raise ValueError('家具摆放编号无效或重复。')
        ids.add(ident); used[item['id']] += 1
        if used[item['id']] > owned[item['id']]:
            raise ValueError('摆放数量超过已购买数量。')
        x, z, rotation = row.get('x'), row.get('z'), row.get('rotation', 0)
        if (type(x) not in (int,float) or type(z) not in (int,float) or not math.isfinite(x)
                or not math.isfinite(z) or type(rotation) is not int or rotation not in (0,90,180,270)):
            raise ValueError('家具的位置或旋转角度无效。')
        if abs(x*4-round(x*4)) > .001 or abs(z*4-round(z*4)) > .001:
            raise ValueError('家具位置应对齐四分之一格。')
        width, depth = item['footprint']
        if rotation in (90,270): width, depth = depth, width
        rect = (x,z,width,depth)
        if x-width/2 < -3.1 or x+width/2 > 3.1 or z-depth/2 < -2.65 or z+depth/2 > 2.7:
            raise ValueError('家具需要摆在房间里面。')
        color = row.get('color', item['color'])
        if not isinstance(color, str) or not re.fullmatch(r'[0-9a-fA-F]{6}', color):
            raise ValueError('请选择有效的家具颜色。')
        if item['solid']:
            if any(_overlap(rect, fixed, .03) for fixed in FIXED) or any(_overlap(rect, old, .04) for old in rects):
                raise ValueError('这里已经有家具，请换个位置。')
            if any(_overlap(rect, (ax,az,.55,.55), .10) for ax,az in ANCHORS):
                raise ValueError('请给床、电脑和门口留出走动空间。')
            rects.append(rect)
        out.append(dict(id=ident, item=item['id'], x=float(x), z=float(z), rotation=rotation, color=color.lower()))
    # Check all functional stations remain connected with the chicken's body
    # clearance. This runs only on Save, never every frame or mouse movement.
    # The character is a radius-.29 capsule, not a square. The coffee table
    # is a radius-.62 cylinder: square inflation would falsely close the
    # diagonal passages of the already-working furnished bedroom.
    solids = FIXED[:-1] + rects
    def circle_box(x,z,box):
        dx=max(0,abs(x-box[0])-box[2]/2)
        dz=max(0,abs(z-box[1])-box[3]/2)
        return dx*dx+dz*dz < .293**2
    def free(x,z):
        return (-2.9 <= x <= 2.9 and -2.45 <= z <= 2.5
                and (x-.05)**2+(z-1.06)**2 >= (.62+.293)**2
                and not any(circle_box(x,z,box) for box in solids))
    cells = {(x/8,z/8) for x in range(-23,24) for z in range(-19,21) if free(x/8,z/8)}
    # Keep tight, curved passages of the existing furniture usable. Uniform
    # grid samples alone miss the capsule's narrow route around the bed's
    # rounded corner and the round table. Add exact corner/arc samples, then
    # connect only continuously collision-free short segments.
    for bx,bz,width,depth in solids:
        for sx in (-1,1):
            for sz in (-1,1):
                cx,cz=bx+sx*width/2,bz+sz*depth/2
                angles=[math.pi/2*i/24 for i in range(25)]
                for angle in angles:
                    point=(cx+sx*math.cos(angle)*.2945,cz+sz*math.sin(angle)*.2945)
                    if free(*point): cells.add(point)
                # The nearest circle-to-corner gap is sampled explicitly.
                dx,dz=.05-cx,1.06-cz
                length=math.hypot(dx,dz)
                if length and dx*sx>0 and dz*sz>0:
                    point=(cx+dx/length*.2945,cz+dz/length*.2945)
                    if free(*point): cells.add(point)
    for index in range(160):
        angle=index*math.tau/160
        point=(.05+math.cos(angle)*.9142,1.06+math.sin(angle)*.9142)
        if free(*point): cells.add(point)
    for anchor in ANCHORS:
        if free(*anchor): cells.add(anchor)
    buckets={}
    for point in cells:
        buckets.setdefault((math.floor(point[0]/.25),math.floor(point[1]/.25)),[]).append(point)
    def near(anchor):
        return min(cells, key=lambda cell:(cell[0]-anchor[0])**2+(cell[1]-anchor[1])**2) if cells else None
    source = near(ANCHORS[0]); reached = {source}; queue=deque([source])
    while queue:
        current=queue.popleft()
        if current is None: break
        bx,bz=math.floor(current[0]/.25),math.floor(current[1]/.25)
        for dx,dz in ((0,0),(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            for nxt in buckets.get((bx+dx,bz+dz),[]):
                distance=math.hypot(current[0]-nxt[0],current[1]-nxt[1])
                if nxt in reached or distance>.22: continue
                steps=max(2,math.ceil(distance/.015))
                if all(free(current[0]+(nxt[0]-current[0])*i/steps,
                            current[1]+(nxt[1]-current[1])*i/steps) for i in range(1,steps)):
                    reached.add(nxt);queue.append(nxt)
    if any(near(anchor) not in reached for anchor in ANCHORS):
        raise ValueError('这套摆放会挡住通路，请给门口和电脑留一条路。')
    return out


def _begin_journal(root):
    root=Path(root)
    if (root/JOURNAL).exists():
        recover_environment(root)
    before={}
    for name in NAMES:
        path=root/name
        if path.is_symlink(): raise ValueError('存档不能是链接。')
        raw=path.read_bytes() if path.exists() else None
        before[name]=None if raw is None else dict(size=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
            payload=base64.b64encode(gzip.compress(raw)).decode('ascii'))
    atomic_bytes(root/JOURNAL, encode(dict(version=1, phase='prepared', before=before)))


def recover_environment(root):
    root=Path(root)
    path=root/JOURNAL
    if not path.exists(): return False
    if path.is_symlink(): raise ValueError('设施事务记录不能是链接。')
    record=json.loads(path.read_text('utf-8'))
    if record.get('version') != 1 or record.get('phase') not in ('prepared','committed') or set(record.get('before', {})) != set(NAMES):
        raise ValueError('设施事务记录无效，请保留当前存档。')
    if record['phase']=='prepared':
        restored={}
        for name,row in record['before'].items():
            if row is None: restored[name]=None;continue
            if type(row.get('size')) is not int or not 0 <= row['size'] <= 512*1024*1024:
                raise ValueError('设施回滚数据大小无效。')
            raw=gzip.decompress(base64.b64decode(row['payload'], validate=True))
            if len(raw)!=row['size'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:
                raise ValueError('设施回滚数据校验失败。')
            restored[name]=raw
        for name,raw in restored.items():
            target=root/name
            if target.is_symlink(): raise ValueError('存档不能是链接。')
            if raw is None:
                if target.exists(): target.unlink()
            else: atomic_bytes(target,raw)
    path.unlink()
    return True


def environment_command(state, action, body):
    request_id=body.get('request_id')
    if not isinstance(request_id,str) or not 1 <= len(request_id) <= 128:
        raise ValueError('请提供本次操作编号。')
    if action not in ('club-tier','facility','home-buy','home-layout','home-finish'):
        raise ValueError('没有这个装修操作。')
    binding={k:v for k,v in body.items() if k not in ('revision','request_id')}
    digest=hashlib.sha256(encode(dict(action=action, body=binding))).hexdigest()
    receipt=_saved(state).get('requests',{}).get(request_id)
    if receipt:
        if receipt['hash']!=digest: raise ValueError('这个操作编号已经用于另一笔购买。')
        return dict(deepcopy(receipt['result']),replayed=True)
    from cs2career.services.business import guard_revision
    guard_revision(state,body)
    blocked=_blocked(state)
    if blocked: raise ValueError(blocked)
    team,tier,facilities=_club(state);home=_home(state)
    price=0; scope='pocket'; label='家居摆放'; target=None
    if action in ('club-tier','facility'):
        if not team or state.career.unsigned or body.get('team_id')!=team.get('id'):
            raise ValueError('当前俱乐部已经变化，请重新打开设施页面。')
        scope='club'
        if action=='club-tier':
            target=body.get('tier')
            if tier=='elite' or target!=TIERS[TIERS.index(tier)+1]:
                raise ValueError('请按当前俱乐部等级选择下一档升级。')
            quoted=next(row for row in catalog()['tiers'] if row['id']==target)
        else:
            target=next((row for row in catalog()['facilities'] if row['id']==body.get('facility')),None)
            if not target: raise ValueError('没有这项俱乐部设施。')
            level=facilities[target['id']]
            if level>=3 or type(body.get('level')) is not int or body['level']!=level+1:
                raise ValueError('这项设施已经升级或报价发生变化。')
            quoted=target['levels'][level]
        price=quoted['price'];label=quoted['name']
    elif action=='home-buy':
        target=next((row for row in catalog()['home_catalog'] if row['id']==body.get('item')),None)
        if not target: raise ValueError('没有这件家具或装饰。')
        if target['kind']!='furniture' and target['id'] in home['owned']:
            raise ValueError('这款墙面或地板已经购买。')
        if len(home['owned'])>=80: raise ValueError('家具库存已经装满。')
        price=target['price'];label=target['name']
    elif action=='home-layout':
        home['placed']=validate_layout(body.get('placed'),home)
    else:
        target=next((row for row in catalog()['home_catalog'] if row['id']==body.get('item')),None)
        if not target or target['kind'] not in ('wallpaper','floor') or target['id'] not in home['owned']:
            raise ValueError('请先购买这款墙面或地板。')
        home[target['kind']]=target['style'];label=target['name']
    balance=int(team.get('money') or 0) if scope=='club' else state.career.money
    if price and (type(body.get('price')) is not int or body['price']!=price):
        raise ValueError('价格已经变化，请刷新后购买。')
    if balance<price:
        raise ValueError('俱乐部资金不足。' if scope=='club' else '个人资金不足。')
    with state.operation():
        store=state.career.incident_state.setdefault(STORE,{'version':1,'clubs':{},'home':deepcopy(DEFAULT_HOME),'requests':{}})
        if scope=='club':
            club=store['clubs'].setdefault(team['id'],{'tier':tier,'facilities':facilities})
            if action=='club-tier':club['tier']=target
            else:club['facilities'][target['id']]=body['level']
            team['money']=balance-price
        else:
            if action=='home-buy':home['owned'].append(target['id'])
            store['home']=home
            state.career.money=balance-price
        if price:
            state.career._record_cashflow(state.season.date,scope,'facilities' if scope=='club' else 'decoration',label,-price,balance-price)
        result=dict(reason='升级完成，回到俱乐部就能看到新设施。' if scope=='club' else
                    '购买完成，可以开始布置。' if action=='home-buy' else '房间布置已保存。',
                    action=action,paid=price,scope=scope,committed=True)
        from cs2career.storage.receipts import needs_legacy_receipt
        if needs_legacy_receipt(request_id):
            store['requests'][request_id]={'hash':digest,'result':deepcopy(result)}
            store['requests']=dict(list(store['requests'].items())[-128:])
        state.career.incident_state.setdefault('career3d_service',{'receipts':[]})['revision']=body['revision']+1
        state.settle()
    return result
