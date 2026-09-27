"""Local Rank/FPL and custom lobbies, independent of the career ledger.

All commands run under ApplicationState's HTTP lock. The only game hand-off
is launch(); a saved nonce and frozen roster bind exactly one result. Reads
never award Elo. Rank/FPL share one ladder; custom matches only retain stats.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import random
import shutil
import tempfile
import uuid

from .paths import save_file
from .world.ability import playing_ability
from .arena_rules import initial_score, level, map_preference, rules

MAPS = ('dust2','mirage','inferno','nuke','ancient','anubis','overpass','train')
PICK_ORDER = ('a','b','b','a','a','b','b','a')


def captain_key(row):
    # A deterministic tie-break only. Recent Rating is never a captain bonus.
    return (-row['elo'],row['player_id'])


class Arena:
    def __init__(self, path=None):
        self.path = path or save_file('arena.json')
        self.data = json.loads(self.path.read_text('utf-8')) if self.path.exists() else {
            'schema_version':2,'revision':0,'ladder':{},'lobby':None,'matches':[]}
        self._migration_backup = self.data.get('schema_version') == 1
        if self._migration_backup:
            self._migrate()
        if self.data.get('schema_version') != 2:
            raise ValueError('本地天梯文件版本不支持，未覆盖原文件')
        self._saved = deepcopy(self.data)

    def _migrate(self):
        """Combine old ladders without deleting history or a pending CS2 nonce.

        Both old ladders started at 1000. Add their earned deltas once, not
        their baselines. Established identities keep that score, not a reseed.
        Backup is deferred until the first successful write is attempted.
        """
        ladder={}
        for old in self.data.pop('ladders',{}).values():
            for pid,record in old.items():
                row=ladder.setdefault(pid,dict(elo=1000,wins=0,losses=0,recent=[],seed={'kind':'legacy'}))
                row['elo']+=record.get('elo',1000)-1000
                row['wins']+=record.get('wins',0);row['losses']+=record.get('losses',0)
                row['recent']=(row['recent']+record.get('recent',[]))[-10:]
        # Prefer chronological original stats over concatenated per-mode lists.
        recent={}
        for match in self.data.get('matches',[]):
            if match.get('mode') not in ('rank','fpl'):continue
            mp=match.get('map',{})
            for rows in mp.get('players',{}).values():
                for p in rows:
                    recent.setdefault(p['player_id'],[]).append({**p,'rounds':mp['rounds']})
        for pid,rows in recent.items():
            if pid in ladder:ladder[pid]['recent']=rows[-10:]
        lobby=self.data.get('lobby')
        if lobby:
            lobby['legacy_manual']=True
            if lobby['mode']=='fpl':lobby['mode']='rank'
        self.data.update(schema_version=2,ladder=ladder)

    @property
    def pending(self):
        return (self.data['lobby'] or {}).get('phase') in ('starting', 'launched')

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        fd,raw=tempfile.mkstemp(prefix='.arena-',suffix='.tmp',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:
                if self._migration_backup and self.path.exists():
                    backup=self.path.with_name('arena.schema1-'+uuid.uuid4().hex+'.json')
                    shutil.copy2(self.path,backup)
                    self._migration_backup=False
                json.dump(self.data,f,ensure_ascii=False,allow_nan=False)
                f.flush();os.fsync(f.fileno())
            os.replace(raw,self.path)
            self._saved = deepcopy(self.data)
        except Exception:
            self.data = deepcopy(self._saved)
            raise
        finally:
            if os.path.exists(raw):os.unlink(raw)

    def roster(self,state):
        found={}
        for team in state.season.teams:
            for p in team['players']:
                if p.get('player_id'):found[p['player_id']]={**deepcopy(p),'club':team['name']}
        for p in state.career.free:
            if p.get('player_id'):found.setdefault(p['player_id'],{**deepcopy(p),'club':''})
        you=getattr(state.career,'you_card',{}) or {}
        if you.get('player_id'):found.setdefault(you['player_id'],{**deepcopy(you),'club':''})
        return found

    def _record(self,state,p):
        pid=p['player_id']
        if pid in self.data['ladder']:return deepcopy(self.data['ladder'][pid])
        you=(getattr(state.career,'you_card',{}) or {}).get('player_id')
        origin=getattr(state.career,'origin',None) if pid==you else None
        elo,seed=initial_score(p,origin)
        return dict(elo=elo,wins=0,losses=0,recent=[],seed=seed)

    def catalog(self,state,mode='rank'):
        rows=[]
        for pid,p in self.roster(state).items():
            record=self._record(state,p)
            recent=record.get('recent') or []
            from .presentation import aggregate
            stats=aggregate([(r,r['rounds']) for r in recent])
            rating=stats.get('rating')
            ability=playing_ability(p)
            rows.append(dict(player_id=pid,name=p['name'],club=p['club'],role=p.get('role','rifle'),
                ability=round(ability,1),rating=rating,samples=len(recent),
                elo=record['elo'],level=level(record['elo']),wins=record.get('wins',0),losses=record.get('losses',0)))
        return sorted(rows,key=captain_key)

    def public(self,state,mode='rank'):
        lobby=deepcopy(self.data['lobby'])
        if lobby:
            lobby.pop('request',None)
            lobby['turn']=self.turn(lobby)
        return dict(ok=True,revision=self.data['revision'],lobby=lobby,catalog=self.catalog(state,mode),
            history=deepcopy(self.data['matches'][-20:][::-1]),maps=list(MAPS),
            default_human_id=(getattr(state.career,'you_card',{}) or {}).get('player_id',''))

    def _guard(self,revision):
        if type(revision) is not int or revision!=self.data['revision']:
            raise ValueError('房间已经变化，请刷新后再操作')

    def _commit(self):
        self.data['revision']+=1
        self.save()

    def _available(self):
        old=self.data['lobby']
        if old and old['phase']!='finished':
            raise ValueError('请先完成或关闭当前房间')

    def matchmake(self,state,body):
        self._guard(body.get('revision'));self._available()
        human=body.get('human_id')
        pool=self.roster(state)
        if not isinstance(human,str) or human not in pool:raise ValueError('请先选择你控制的选手')
        scores={p['player_id']:p for p in self.catalog(state)}
        eligible=[pid for pid in pool if pid!=human]
        if len(eligible)<9:raise ValueError('当前资料库不足十名选手')
        elo=scores[human]['elo']
        distance=lambda pid:abs(scores[pid]['elo']-elo)
        needed=sorted(distance(p) for p in eligible)[8]
        band=next((b for b in rules()['match_bands'] if b>=needed),needed)
        candidates=sorted(pid for pid in eligible if distance(pid)<=band)
        lobby_id=uuid.uuid4().hex;rng=random.Random(lobby_id)
        ids=[human]
        for _ in range(9):
            pick=rng.choices(candidates,weights=[1/(1+distance(p)/200)**2 for p in candidates],k=1)[0]
            ids.append(pick);candidates.remove(pick)
        rng.shuffle(ids)
        caps=sorted(ids,key=lambda pid:captain_key(scores[pid]))[:2]
        self.data['lobby']=dict(id=lobby_id,mode='rank',phase='draft',human_id=human,
            roster={pid:pool[pid] for pid in ids},selection=ids,a=[caps[0]],b=[caps[1]],captains=caps,
            ratings={pid:scores[pid]['elo'] for pid in ids},picks=[],bans=[],map_pool=list(rules()['veto_maps']),
            map='',ct='a',side_chooser='a',band=band,
            matched_range=[min(scores[p]['elo'] for p in ids),max(scores[p]['elo'] for p in ids)])
        for pid in ids:self.data['ladder'].setdefault(pid,self._record(state,pool[pid]))
        self._commit()

    def create(self,state,body):
        self._guard(body.get('revision'))
        self._available()
        mode=body.get('mode')
        if mode!='custom':raise ValueError('天梯请使用开始匹配，不手动挑选对手')
        ids=body.get('players')
        if not isinstance(ids,list) or len(ids)!=10 or any(not isinstance(p,str) for p in ids) or len(set(ids))!=10:
            raise ValueError('请选择十名不同的选手')
        pool=self.roster(state)
        if any(pid not in pool for pid in ids):raise ValueError('名单中的选手已不在当前资料库，请重新选择')
        human=body.get('human_id') or ''
        if human and human not in ids:raise ValueError('控制角色必须在十人名单里')
        scores={p['player_id']:p for p in self.catalog(state,mode)}
        ordered=sorted(ids,key=lambda p:captain_key(scores[p]))
        self.data['lobby']=dict(id=uuid.uuid4().hex,mode=mode,phase='ready',
            roster={pid:pool[pid] for pid in ids},selection=ids,human_id=human,map='dust2',ct='a',
            captains=ordered[:2],a=ids[:5],b=ids[5:],picks=[],ratings={pid:scores[pid]['elo'] for pid in ids})
        self._commit()

    @staticmethod
    def turn(l):
        if l['phase']=='draft':side=PICK_ORDER[len(l['picks'])]
        elif l['phase']=='veto':side='a' if len(l['bans'])%2==0 else 'b'
        elif l['phase']=='side':side=l['side_chooser']
        else:return None
        cap=l['captains'][0 if side=='a' else 1]
        return dict(side=side,captain_id=cap,human=cap==l['human_id'] or l.get('legacy_manual',False))

    def _human_turn(self,l):
        turn=self.turn(l)
        if not turn or not turn['human']:raise ValueError('当前由 AI 队长操作')

    def _pick(self,l,pid):
        if not isinstance(pid,str) or pid not in l['roster'] or pid in l['a']+l['b']:raise ValueError('该选手不在待选名单')
        side=PICK_ORDER[len(l['picks'])]
        l[side].append(pid);l['picks'].append(dict(side=side,player_id=pid))
        if len(l['picks'])==8:
            l['phase']='veto';l.setdefault('map_pool',list(rules()['veto_maps']));l.setdefault('bans',[])
            l.setdefault('side_chooser','a')

    def pick(self,body):
        self._guard(body.get('revision'));l=self.data['lobby']
        if not l or l['phase']!='draft':raise ValueError('当前不在队长选人阶段')
        self._human_turn(l);self._pick(l,body.get('player_id'))
        self._commit()

    def _ban(self,l,mp):
        if mp not in l['map_pool'] or any(b['map']==mp for b in l['bans']):raise ValueError('地图已被禁用或不在图池')
        l['bans'].append(dict(map=mp,side=self.turn(l)['side']))
        remaining=[m for m in l['map_pool'] if m not in [b['map'] for b in l['bans']]]
        if len(remaining)==1:l.update(phase='side',map=remaining[0])

    def ban(self,body):
        self._guard(body.get('revision'));l=self.data['lobby']
        if not l or l['phase']!='veto':raise ValueError('当前不在地图 BP 阶段')
        self._human_turn(l);self._ban(l,body.get('map'));self._commit()

    def choose_side(self,body):
        self._guard(body.get('revision'));l=self.data['lobby']
        if not l or l['phase']!='side':raise ValueError('当前不在选边阶段')
        self._human_turn(l)
        side=body.get('side')
        if side not in ('ct','t'):raise ValueError('请选择 CT 或 T')
        l.update(ct=l['side_chooser'] if side=='ct' else ('b' if l['side_chooser']=='a' else 'a'),phase='ready')
        self._commit()

    def advance(self,body):
        """One persisted AI turn. Reloading is safe, and cannot skip a human turn."""
        self._guard(body.get('revision'));l=self.data['lobby']
        turn=self.turn(l) if l else None
        if not turn or turn['human']:raise ValueError('现在轮到你操作')
        rng=random.Random(f"{l['id']}:{l['phase']}:{len(l['picks'])}:{len(l.get('bans',[]))}")
        if l['phase']=='draft':
            available=[p for p in l['selection'] if p not in l['a']+l['b']]
            roles=[l['roster'][p].get('role') for p in l[turn['side']]]
            def score(pid):
                role=l['roster'][pid].get('role')
                balance=100 if role not in roles else (-200 if role=='awp' else 0)
                return l['ratings'][pid]+balance+rng.uniform(-100,100)
            self._pick(l,max(available,key=score))
        elif l['phase']=='veto':
            remaining=[m for m in l['map_pool'] if m not in [b['map'] for b in l['bans']]]
            self._ban(l,min(remaining,key=lambda m:sum(map_preference(p,m) for p in l[turn['side']])))
        else:
            l.update(ct=l['side_chooser'] if rng.random()<.6 else ('b' if l['side_chooser']=='a' else 'a'),phase='ready')
        self._commit()

    def configure(self,body):
        self._guard(body.get('revision'));l=self.data['lobby']
        if not l or l['phase']!='ready':raise ValueError('先完成双方阵容')
        if l['mode']!='custom':raise ValueError('天梯阵容和地图已锁定')
        mp=body.get('map');side=body.get('ct');human=body.get('human_id') or ''
        if mp not in MAPS or side not in ('a','b') or not isinstance(human,str) or (human and human not in l['roster']):raise ValueError('地图、阵营或控制角色无效')
        l.update(map=mp,ct=side,human_id=human)
        self._commit()

    def recommend(self,state,mode,human=''):
        rows=self.catalog(state,mode)
        if human and any(p['player_id']==human for p in rows):
            score=next(p['ability'] for p in rows if p['player_id']==human)
        else:score=75
        candidates=sorted(rows,key=lambda p:abs(p['ability']-score))[:50]
        ids=[p['player_id'] for p in candidates if p['player_id']!=human]
        rng=random.Random(uuid.uuid4().hex)
        chosen=([human] if human and human in self.roster(state) else [])
        if len(ids)+len(chosen)<10:raise ValueError('当前资料库不足十名选手')
        return chosen+rng.sample(ids,10-len(chosen))

    @staticmethod
    def _career_pending(state):
        return any(m.get('cs2_session') and not m.get('played') for e in state.season.events for m in e.get('matches',[]))

    def launch(self,state,body):
        self._guard(body.get('revision'));l=self.data['lobby']
        if not l or l['phase'] not in ('ready','starting'):raise ValueError('房间不在待开赛状态')
        if self._career_pending(state):raise ValueError('请先完成或处理生涯中待回传的 CS2 比赛')
        from .cs2 import launch
        launch.require_cs2_closed('启动本地天梯或观察者比赛')
        teams={side:dict(id='arena-'+side,name='Team '+side.upper(),players=[l['roster'][p] for p in l[side]]) for side in ('a','b')}
        ct=teams[l['ct']];t=teams['b' if l['ct']=='a' else 'a']
        if l['phase']=='ready':
            l.update(phase='starting',nonce=uuid.uuid4().hex,started_at=datetime.now(timezone.utc).isoformat())
            self._commit()  # Keep a recovery token even if Steam launch fails.
        request=launch.build_lobby_request(ct,t,l['human_id'],'de_'+l['map'],l['nonce'])
        l['request']=request
        self.save()
        out=launch.start_match(ct,t,request['player'],request['map'],request['human_team'],
            teams=[ct,t],purpose='arena',request_override=request)
        l['phase']='launched';self._commit()
        return out['msg']

    def ingest(self,body,raw=None):
        self._guard(body.get('revision'));l=self.data['lobby']
        if not l or l['phase'] not in ('launched','starting','finished'):raise ValueError('当前没有待录入的天梯比赛')
        if l['phase']=='finished':return '这场已录入，不重复计分'
        from .cs2 import read_result
        from .cs2.result import result_usable, cs2_to_map
        result=raw if raw is not None else read_result(l['nonce'])
        session=dict(nonce=l['nonce'],map=l['map'],started_at=l['started_at'],expected_player_ids=list(l['roster']))
        reason=result_usable(result,session)
        if reason:raise ValueError(reason)
        if result.get('map') != 'de_'+l['map'] or not result.get('ended_at'):
            raise ValueError('回传地图或结束时间缺失，未计分')
        # IDs may not cross their opening teams even after halftime/takeover.
        for p in result['players']:
            side='ct' if p['player_id'] in l[l['ct']] else 't'
            if p.get('team')!=side:raise ValueError('回传选手与开场阵容不一致，未计分')
        teams={side:dict(id='arena-'+side,name='Team '+side.upper(),players=[l['roster'][p] for p in l[side]]) for side in ('a','b')}
        session.update(side='ct' if l['ct']=='a' else 't',my_team='Team A',opp='Team B',
            role_by_id={pid:p.get('role','rifle') for pid,p in l['roster'].items()})
        mp=cs2_to_map(result,session,teams['a'],teams['b'],'')
        won='a' if mp['winner']=='Team A' else 'b'
        updated=deepcopy(self.data)
        l=updated['lobby']
        changes={}
        if l['mode'] in ('rank','fpl'):
            ladder=updated['ladder']
            averages={side:sum(ladder.get(pid,{}).get('elo',1000) for pid in l[side])/5 for side in ('a','b')}
            expected=1/(1+10**(max(-2000,min(2000,averages['b']-averages['a']))/400))
            delta=round(32*((1 if won=='a' else 0)-expected))
            for side in ('a','b'):
                for pid in l[side]:
                    row=ladder.setdefault(pid,dict(elo=1000,wins=0,losses=0,recent=[],seed={'kind':'legacy'}))
                    change=delta if side=='a' else -delta
                    row['elo']+=change;row['wins' if side==won else 'losses']+=1
                    stats=next(p for p in mp['players'][teams[side]['name']] if p['player_id']==pid)
                    row['recent']=(row['recent']+[{**stats,'rounds':mp['rounds']}])[-10:]
                    row['name']=l['roster'][pid]['name'];changes[pid]=change
        record=dict(id=l['id'],nonce=l['nonce'],date=result.get('ended_at'),mode=l['mode'],map=mp,
            human_id=l['human_id'],winner=won,changes=changes)
        updated['matches'].append(record)
        l.update(phase='finished',result=record)
        self.data=updated
        self._commit()
        return '本场战绩已保存' if l['mode']=='custom' else '本场战绩与本地天梯积分已保存'

    def cancel(self,body):
        self._guard(body.get('revision'));l=self.data['lobby']
        if l and l['phase'] in ('starting','launched'):
            from .cs2.launch import require_cs2_closed
            require_cs2_closed('放弃当前天梯比赛')
        self.data['lobby']=None;self._commit()
