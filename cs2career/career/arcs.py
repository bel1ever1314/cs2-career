"""Career story adapter, not a second application state.

All persistent state lives in Career.incident_state['arcs']; decisions use the
existing incident queue/ack transaction. Text, rewards, thresholds and endings
are data. Only whitelisted actions below can alter teams or end a career.
No UI polling, eval, name-based character unlocks, or gameplay RNG consumption.
"""
from copy import deepcopy
from datetime import date, timedelta
from functools import lru_cache
import hashlib
import json
import math
import re
from uuid import uuid4

from ..paths import data_file
from ..content import get_registry
from ..world.ability import AXIS_LABEL, refresh_player_ability, refresh_team_command, playing_ability


PARTNERS = {'ordinary': '她', 'creator': '她', 'celebrity': '她', 'dota': '她'}
LIMITS = {'focus_reward': (0,100), 'na_bonus': (0,100), 'marriage_days': (1,3650),
          'heat_amplitude': (0,10), 'split_chance': (0,1), 'injury_cooldown_days': (1,365),
          'injury_duration_days': (1,365), 'injury_form_penalty': (-10,0), 'injury_year_limit': (0,12),
          'politics_min_series': (5,100), 'politics_window': (5,100), 'politics_win_rate': (0,1),
          'politics_empty_events': (1,10), 'politics_cooldown_days': (1,3650),
          'press_min_maps': (5,200), 'press_days': (1,365), 'press_cooldown_days': (1,3650),
          'press_bad_rating': (.2,2.5), 'press_good_rating': (.2,2.5), 'return_partner_days': (1,365),
          'na_first_year_days': (1,3650), 'na_return_days': (1,3650),
          'na_min_maps': (1,5000), 'na_min_rating': (.2,2.5),
          'major_favourite_rank': (1,64), 'major_contender_rank': (1,64)}


@lru_cache(maxsize=1)
def base_config():
    cfg=json.loads(data_file('career_arcs.json').read_text('utf-8'))
    cfg['reports']=json.loads(data_file('career_news.json').read_text('utf-8'))
    return cfg


def validate_overrides(raw):
    """Authoring boundary: override copy/rewards, or attach safe custom chapters."""
    from ..content.rules import keys, number, text, identifier
    keys(raw, {'rules','chapters','endings','reports'})
    reports=raw.get('reports',{})
    keys(reports,set(base_config()['reports']))
    for item in reports.values():
        keys(item,{'title','text'})
        if 'title' in item:text(item['title'],160)
        if 'text' in item:
            if not isinstance(item['text'],list) or not 1<=len(item['text'])<=30:
                raise ValueError('报道text需要1—30套文案')
            for line in item['text']:text(line,5000)
    rules = raw.get('rules', {})
    keys(rules, set(LIMITS) | {'injury_monthly_rates','lvg_team_name','na_success_types'})
    for key, value in rules.items():
        if key in LIMITS:
            if not number(value, *LIMITS[key]): raise ValueError('剧情规则数值超限：'+key)
            if key not in {'split_chance','politics_win_rate','press_bad_rating','press_good_rating','na_min_rating'} and type(value) is not int:
                raise ValueError('剧情规则需要整数：'+key)
        elif key == 'lvg_team_name': text(value, 80)
        elif key == 'na_success_types':
            if not isinstance(value,list) or not value or len(value)!=len(set(value)) or any(x not in ('cct','t2','qual','t1','major') for x in value):
                raise ValueError('na_success_types须为不重复的赛事类型列表')
        else:
            if not isinstance(value,list) or not 1 <= len(value) <= 12: raise ValueError('伤病年龄段格式错误')
            previous = -1
            for band in value:
                if not isinstance(band,list) or len(band)!=2 or type(band[0]) is not int or not previous < band[0] <= 150 or not number(band[1],0,1):
                    raise ValueError('伤病年龄上界须递增，概率须在0—1')
                previous = band[0]
    chapters = raw.get('chapters', {})
    if not isinstance(chapters,dict) or len(chapters)>200: raise ValueError('chapters须为至多200项对象')
    for key, chapter in chapters.items():
        identifier(key); keys(chapter, {'title','text','choices'})
        if 'title' in chapter: text(chapter['title'],100)
        if 'text' in chapter:
            if not isinstance(chapter['text'],list) or not 1<=len(chapter['text'])<=30: raise ValueError('text需要1—30套完整文案')
            for line in chapter['text']: text(line,5000)
        if key not in base_config()['chapters'] and not {'title','text','choices'} <= set(chapter):
            raise ValueError('自定义章节需要title/text/choices')
        if 'choices' in chapter:
            if not isinstance(chapter['choices'],list) or not 1<=len(chapter['choices'])<=4: raise ValueError('章节需要1—4个选项')
            known = {r['id']:r for r in base_config()['chapters'].get(key,{}).get('choices',[])}
            ids = set()
            for choice in chapter['choices']:
                keys(choice, {'id','label','reward','next','action','ending','branches'})
                identifier(choice.get('id'))
                if choice['id'] in ids: raise ValueError('章节选项id重复')
                ids.add(choice['id'])
                if 'label' in choice: text(choice['label'],120)
                if 'reward' in choice and (type(choice['reward']) is not int or not 0<=choice['reward']<=100): raise ValueError('reward需要0—100整数')
                if known:
                    if choice['id'] not in known or any(k in choice for k in ('action','ending','branches')): raise ValueError('内置选项只能改文字、奖励和追加next章节')
                elif choice.get('action','continue') not in ('continue','finish') or not choice.get('label'):
                    raise ValueError('新章节只允许continue或finish动作，并需要label')
                if 'next' in choice: identifier(choice['next'])
                if 'ending' in choice: identifier(choice['ending'])
                if 'branches' in choice:
                    branches=choice['branches']
                    if not isinstance(branches,list) or not 1<=len(branches)<=4: raise ValueError('branches需要1—4项')
                    for branch in branches:
                        keys(branch,{'weight','next'});identifier(branch.get('next'))
                        if not number(branch.get('weight'),.001,100): raise ValueError('分支weight须大于0')
    endings = raw.get('endings',{})
    if not isinstance(endings,dict) or len(endings)>100: raise ValueError('endings格式错误')
    for key, item in endings.items():
        identifier(key);keys(item,{'title','text'});text(item.get('title'),100);text(item.get('text'),5000)
    merged_keys = set(base_config()['chapters']) | set(chapters)
    ending_keys = set(base_config()['endings']) | set(endings)
    for chapter in chapters.values():
        for choice in chapter.get('choices',[]):
            refs = [choice['next']] if choice.get('next') else []
            refs += [b['next'] for b in choice.get('branches',[])]
            if any(ref not in merged_keys for ref in refs): raise ValueError('章节next引用未解析；相关自定义章节应放在同一文件')
            if choice.get('action')=='finish' and choice.get('ending') not in ending_keys: raise ValueError('结局引用未解析')
    # Reject newly introduced cycles: an accidental reward loop must not turn
    # a text-only expansion into unlimited points. Built-in confirmation-back
    # edges remain legal; authors can append chapters, not loop into them.
    graph={key:set() for key in merged_keys}
    new_edges=[]
    for key in merged_keys:
        choices={c['id']:c for c in base_config()['chapters'].get(key,{}).get('choices',[])}
        for item in chapters.get(key,{}).get('choices',[]):
            choices[item['id']]={**choices.get(item['id'],{}),**item}
            new_edges.extend((key,ref) for ref in ([item['next']] if item.get('next') else [])+[b['next'] for b in item.get('branches',[])])
        for choice in choices.values():
            graph[key].update(([choice['next']] if choice.get('next') else [])+[b['next'] for b in choice.get('branches',[])])
    for source,target in new_edges:
        todo=[target];visited=set()
        while todo:
            key=todo.pop()
            if key==source:raise ValueError('扩展章节存在循环引用，请用不重复的章节结束选择链')
            if key not in visited:visited.add(key);todo.extend(graph.get(key,()))


@lru_cache(maxsize=4)
def _config(registry):
    cfg = deepcopy(base_config())
    for payload in registry.payloads('incidents'):
        extra = payload.get('arc_overrides',{})
        cfg['rules'].update(extra.get('rules',{}))
        cfg['endings'].update(extra.get('endings',{}))
        for key,item in extra.get('reports',{}).items():
            cfg['reports'][key].update(deepcopy(item))
        for key, chapter in extra.get('chapters',{}).items():
            old = cfg['chapters'].setdefault(key,{})
            for field in ('title','text'):
                if field in chapter: old[field] = deepcopy(chapter[field])
            if 'choices' in chapter:
                if key not in base_config()['chapters']: old['choices'] = deepcopy(chapter['choices'])
                else:
                    byid = {c['id']:c for c in chapter['choices']}
                    old['choices'] = [{**c, **byid.get(c['id'],{})} for c in old['choices']]
    return cfg


def config(): return _config(get_registry())
def state(c): return c.incident_state.get('arcs', {})
def active(c): return bool(c and c.exists and state(c).get('enabled') and not c.over())
def after(day, n): return (date.fromisoformat(day)+timedelta(days=int(n))).isoformat()
def key_for(s, ev, match=None): return f'{s.year}:{ev["id"]}' + (':'+match['id'] if match else '')
def roll(c, key):
    return int.from_bytes(hashlib.sha256((state(c).get('seed','')+'|'+key).encode()).digest()[:8],'big')/2**64


def render(text, context):
    return re.sub(r'\{([a-z_]+)\}', lambda m: str(context.get(m[1], '{'+m[1]+'}')), text)


def initialize(c,s,payload=None):
    if state(c): return False
    c.incident_state['arcs'] = dict(enabled=payload is not None, seed=uuid4().hex, started=s.date,
        series=[], events=[], seen=[], history=[], monthly='', injuries=[], news=[], last_press='',
        last_politics='', romance='waiting', partner='', na='', heat=False)
    if payload is None:
        queue(c,s,'upgrade','upgrade')
    elif payload.get('scenario') == 'na_student':
        state(c)['na']='choose'
        c.attr_points += config()['rules']['na_bonus']
        queue(c,s,'na_start','na-start',{'na_bonus':config()['rules']['na_bonus']})
    return True


def queue(c,s,chapter,occurrence,context=None,frozen=None):
    v=state(c); sid='arc:'+chapter+':'+hashlib.sha256(str(occurrence).encode()).hexdigest()[:20]
    if not v or sid in v['seen'] or any(r.get('id')==sid for r in c.story_queue): return
    cfg=deepcopy(config())
    if frozen:
        cfg['chapters'].update(frozen.get('chapters',{}));cfg['endings'].update(frozen.get('endings',{}))
    node=deepcopy(cfg['chapters'][chapter]); ctx={'player':c.player_name,
        'na_min_maps':cfg['rules']['na_min_maps'],'na_min_rating':f"{cfg['rules']['na_min_rating']:.2f}",
        'na_first_year_days':cfg['rules']['na_first_year_days'],'na_return_days':cfg['rules']['na_return_days'],
        'partner':PARTNERS.get(v.get('partner'), '伴侣'), **(context or {})}
    choices=node['choices']
    for choice in choices:
        choice['reward']=int(choice.get('reward', cfg['rules']['focus_reward'] if choice.get('focus') else 0))
        choice['label']=render(choice['label'],ctx) + (f"（属性点+{choice['reward']}）" if choice['reward'] else '')
        choice['action']=choice.get('action','continue')
        if choice.get('action')=='finish':
            choice['ending_content']=deepcopy(cfg['endings'][choice['ending']])
        if choice.get('branches'):
            total=sum(b['weight'] for b in choice['branches']); value=roll(c,sid+choice['id'])*total
            for branch in choice['branches']:
                value-=branch['weight']
                if value<=0:
                    choice['next']=branch['next'];break
    # Returning from a confirmation must not grant a new roll of a 50/50 ending.
    chance_key = ('love-ending:'+v.get('romance_started','') if chapter=='confirm_love' else
                  'press-ending:'+ctx.get('reward_key',occurrence) if chapter=='confirm_press' else
                  'marriage-talk:'+v.get('romance_started','') if chapter=='marriage' else sid+'outcome')
    # Persist only reachable custom chapters, so removing a pack cannot strand
    # its already accepted choice chain. Normal built-in choices carry no graph.
    custom={}; endings={};todo=[x.get('next') for x in choices if x.get('next')]
    while todo:
        key=todo.pop()
        if key in base_config()['chapters'] or key in custom:continue
        custom[key]=deepcopy(cfg['chapters'][key])
        for item in custom[key]['choices']:
            if item.get('ending'):endings[item['ending']]=deepcopy(cfg['endings'][item['ending']])
            todo.extend(([item['next']] if item.get('next') else [])+[b['next'] for b in item.get('branches',[])])
    c.story_queue.append(dict(id=sid,kind='incident',when='incident',arc=chapter,pack_id='builtin.arcs',
        title=render(node['title'],ctx),text=render(node['text'][int(roll(c,sid+'text')*len(node['text']))],ctx),
        choices=choices,context=ctx,date=s.date,team_id=c.team_id,
        arc_rules=deepcopy(cfg['rules']), arc_followups=dict(chapters=custom,endings=endings),chance=roll(c,chance_key)))


def notice(c,s,title,text,occurrence):
    sid='arc-notice:'+occurrence
    if c._queued(sid): return
    c.story_queue.append(dict(id=sid,kind='story',title=title,text=text,when='arc_reaction'))
    state(c).setdefault('history',[]).append(dict(id=sid,date=s.date,title=title,text=text))


def finish(c,s,ending,item=None):
    item=deepcopy(item or config()['endings'][ending])
    c.retired=True;c.ending='arc.'+ending;c.ending_title=item['title'];c.ending_text=item['text']
    c.story_queue=[];c.fix_pending=False;c.throwing=False;c._sync_throw(s)
    for mail in c.inbox:
        if mail.get('status')=='open' and mail.get('kind') in ('invite','contract'): mail['status']='expired'
    state(c)['heat']=False
    notice(c,s,item['title'],item['text'],'ending:'+ending)
    c.log.append('生涯结局：'+item['title'])


def free_club(c,s,team,departures):
    """Freeze outgoing cards, fill ALL vacancies before committing. No fake IDs."""
    from . import player_transfers as pt
    from ..world.ability import ensure_role_calibration
    occupied={p.get('player_id') or p['name'] for t in s.teams for p in t['players']}
    candidates=[p for p in c.free if (p.get('player_id') or p['name']) not in occupied and p['name'] not in c.hidden]
    chosen=[]
    for gone in departures:
        pool=[p for p in candidates if p not in chosen]
        if not pool: raise ValueError('自由市场不足以补齐阵容；名单未变，请补充选手包后重试。')
        chosen.append(max(pool,key=lambda p:(p.get('role')==gone.get('role'),p.get('ability',0),p['name'])))
    replacements=[]
    for incoming,gone in zip(chosen,departures):
        p=deepcopy(incoming);p.update(role=gone['role'],you=False,is_igl=gone['role']=='igl')
        ensure_role_calibration(p);refresh_player_ability(p);replacements.append(p)
    leaving_player=any(p.get('you') for p in departures)
    if leaving_player: c._remember_you(s)
    ids={p.get('player_id') or p['name'] for p in departures}
    team['players']=[p for p in team['players'] if (p.get('player_id') or p['name']) not in ids]+replacements
    chosenids={p.get('player_id') or p['name'] for p in chosen}
    c.free=[p for p in c.free if (p.get('player_id') or p['name']) not in chosenids]
    for p in departures:
        if not p.get('you'): c._player_to_free(s,p,team.get('region','EU'))
    team['custom_roles']=True;refresh_team_command(team)
    if leaving_player:
        if c.loan and c.loan.get('kind')=='bank': team['career_bank_loan']=deepcopy(c.loan);c.loan=None
        elif c.loan: c.loan.setdefault('creditor_team_id',team['id'])
        team.update(career_ai_managed=True,career_ops_month=s.date[:7])
        c.repair_invite_teams(s)
        old=team['id']; c.team_id='';c.unsigned=True;c.registered=[];c.crisis=False;c.deficit=0;c.throwing=False
        for mail in c.inbox:
            if mail.get('kind') in ('invite','contract') and mail.get('status')=='open':mail['status']='expired'
        value=pt.state(c);value.update(pending=None,move_until='',checked_month='')
        value['moves'].append(dict(date=s.date,old_team_id=old,old_team=team['name'],new_team_id='',new_team='',source='story_release'))


def safe_roster(c,s):
    from .transfers import locked
    team=c.my_team(s.teams)
    if c.training_session or (team and locked(s,team)):
        raise ValueError('当前赛事或CS2对局尚未结束，暂不能改变名单。可先继续赛程，结束后再办理。')


def return_home(c,s):
    safe_roster(c,s)
    from .origins import origin_config
    from . import player_transfers as pt
    from ..world import slug
    old=c.my_team(s.teams); you=deepcopy(c._you_stats(s))
    you['you']=True
    if old: free_club(c,s,old,[c.my_player(s.teams)])
    cfg=origin_config(c.origin)
    org=c.player_name+' 归国俱乐部'; sid=slug(org)
    n=1
    while any(t['id']==sid for t in s.teams): n+=1;sid=slug(org)+f'-{n}'
    c.team_id=sid;c.mode='create';c.unsigned=False;c.crisis=False;c.deficit=0;c.registered=[]
    c._spawn_org(s,org,{'region':'AS'})
    new=c.my_team(s.teams)
    new['players']=[you if p.get('you') else p for p in new['players']]
    new['custom_roles']=True;refresh_team_command(new)
    occupied={p.get('player_id') or p['name'] for t in s.teams for p in t['players']}
    c.free=[p for p in c.free if (p.get('player_id') or p['name']) not in occupied]
    pt.state(c)['player_only']=False
    c._record_cashflow(s.date,'club','restart','归国自建队启动资金',cfg['club_money'],new['money'])
    c.dispatch_invites(s);c._remember_you(s)
    state(c).update(na='returned',returned=s.date,deadline=after(s.date,config()['rules']['na_return_days']))


def lvg_join(c,s):
    from . import player_transfers as pt
    safe_roster(c,s)
    target=next((t for t in s.teams if t['name']==config()['rules']['lvg_team_name']),None)
    if not target: raise ValueError('当前年代包找不到Lynn Vision，请检查战队包；也可婉拒，不会卡住存档。')
    if target['id']==c.team_id: state(c)['na']='closed';return
    role=c.role if any(p['role']==c.role for p in target['players']) else 'rifle'
    offer=pt.quote(c,s,target,role)
    if not offer: raise ValueError('LVG暂时没有合适位置，可稍后重试或婉拒。')
    offer.update(id='arc-lvg',source='story_offer',date=s.date)
    value=pt.state(c);value['move_until']=''  # Scripted once-only invitation overrides personal lock, not live roster locks.
    pt.decision(c,s,offer)
    row=next(r for r in c.story_queue if r['id']=='transfer-decision:arc-lvg')
    # Transfer validation must not see the current storyline's own decision as a blocker.
    removed=[r for r in c.story_queue if r.get('choices') and r is not row]
    c.story_queue=[r for r in c.story_queue if r not in removed]
    try: pt.resolve(c,s,row,'accept')
    finally: c.story_queue.extend(removed)
    c.story_queue=[r for r in c.story_queue if r['id']!=row['id']]
    state(c)['na']='closed'


def resolve(c,s,row,choice_id):
    v=state(c); choice=next(x for x in row['choices'] if x['id']==choice_id)
    action=choice.get('action','continue'); rules=row['arc_rules'];ctx=row['context']; sid=row['id']
    # Ownership-changing actions execute inside ApplicationState.personal_command.
    if action=='return_home': return_home(c,s)
    elif action=='lvg': lvg_join(c,s)
    elif action=='politics':
        safe_roster(c,s);team=c.my_team(s.teams)
        current=sorted((p.get('player_id') or p['name']) for p in (team or {}).get('players',[]))
        if not team or team['id']!=row['team_id'] or current!=ctx['roster_ids']:
            notice(c,s,'这次争执已经过去','阵容已经变化，旧的宫斗决定失效，不对新队友执行旧决定。',sid+':stale')
        else:
            target=next(p for p in team['players'] if (p.get('player_id') or p['name'])==ctx['target_id'])
            succeeds=row['chance']<rules['split_chance']
            target_stays = succeeds if choice['side']=='defend' else not succeeds
            departures=[p for p in team['players'] if p is not target] if target_stays else [target]
            free_club(c,s,team,departures)
            notice(c,s,'名单之外的代价',
                f"{target['name']}的反击得到了管理层支持，留下了。其他四人离开阵容。"+
                ('\n你也成为自由身，可以主动申请其他队伍，试训概率与申请冷却仍然有效；也可以等待offer。' if c.unsigned else '')
                if target_stays else f"管理层最终选择更换{target['name']}。他收好设备离开，临走只说：‘希望你们下一次能把问题解决在服务器里。’\n新队员已经补入，但换掉一个名字并不保证成绩自动好转。",sid)
    elif action=='enable':v['enabled']=True;v['started']=s.date
    elif action=='disable':v['enabled']=False;v['declined']=True
    elif action=='romance':
        v.update(romance='dating',partner=choice_id,romance_started=s.date)
        queue(c,s,choice_id+'_intro',sid)
    elif action=='single':v['romance']='single';notice(c,s,'先把这一条路走好','你把想法说清楚，没有吊着谁等待。眼下你想把有限的时间交给训练，未来则不急着替自己作答。',sid)
    elif action in ('heat','steady'):
        v['pace']=action;v['heat']=action=='heat';v['heat_since']=s.date
        notice(c,s,'选择之后', '接下来直到下一届Major结束，每场系列赛的短期状态会额外正负波动；长期能力不变。' if action=='heat' else '你和她约好训练时专心、见面时也专心。这不是把感情放在职业的对立面，而是努力让两件重要的事都走得更长。',sid)
    elif action=='confirm_love':queue(c,s,'confirm_love',sid)
    elif action=='love_retire':finish(c,s,'love_home' if row['chance']<rules['split_chance'] else 'love_stream')
    elif action=='breakup':v['romance']='single';v['heat']=False;queue(c,s,'breakup_reply',sid)
    elif action=='talk':
        success=row['chance']<rules['split_chance'];v['romance']='stable' if success else 'single';v['heat']=False
        queue(c,s,'stable' if success else 'breakup_reply',sid)
    elif action=='confirm_press':queue(c,s,'confirm_press',sid,ctx)
    elif action=='press_retire':finish(c,s,'press_stream' if row['chance']<rules['split_chance'] else 'press_other')
    elif action=='endure':queue(c,s,'endure_reply',sid)
    elif action=='neutral':queue(c,s,'neutral_reply',sid)
    elif action in ('na_study','na_pro'):
        v.update(na='study' if action=='na_study' else 'pro',deadline=after(v['started'],rules.get('na_first_year_days',config()['rules']['na_first_year_days'])))
    elif action=='na_close':
        has_title=v.get('na_assessment',{}).get('achievement',False)
        v['na']='closed' if has_title else 'return_pending'
        notice(c,s,'谢谢你们认真看过我的比赛','你给赛训组回信表达感谢，对方尊重了你的决定。'+
               ('家里支持你继续职业，这条留学生邀约线结束，生涯照常继续。' if has_title else '没有冠军成绩，也没有接受这份邀请，你决定按家书里的商量回国，从自己的队伍重新开始。'),sid)
        if not has_title:queue(c,s,'na_return','invite-refused')
    elif action=='dota_stable':v.update(romance='stable',partner='dota')
    elif action=='reunion':
        replies={'bold':'对面很快回话：“狠话收到了。我们也没打算送你一场胜利。”采访席笑了一阵，熟悉的队友如今真成了对手。',
                 'respect':'旧队长回应：“一起打过的比赛是真的，今天想赢你也是真的。场上见。”你们点头，各自回到准备区。',
                 'quiet':'对方没有替你的沉默编故事：“他一直这样，开打就知道了。”镜头移开，你终于可以只看眼前的比赛。'}
        notice(c,s,'旧队的回应',replies[choice_id],sid)
        v.setdefault('reunion_choices',{})[ctx['match_key']]=choice_id
    elif action=='finish':finish(c,s,choice['ending'],choice.get('ending_content'))
    elif action!='continue':raise ValueError('未知剧情动作，未结算')
    reward=choice.get('reward',0)
    reward_key=ctx.get('reward_key',sid)
    if reward and not c.over() and reward_key not in v.setdefault('rewarded',[]):
        c.attr_points+=reward;v['rewarded'].append(reward_key)
        c.log.append(f"{row['title']}：属性点 +{reward}")
    v['seen'].append(sid)
    v['history'].append(dict(id=sid,date=s.date,title=row['title'],text=row['text'],choice=choice['label']))
    if choice.get('next') and not c.over():queue(c,s,choice['next'],sid,ctx,row.get('arc_followups'))


def changes_world(row, choice_id):
    """Only roster/retirement choices need the expensive two-save transaction.

    Text, flags and free points live wholly in the atomic career save. Never
    copy years of match events just to acknowledge the next story paragraph.
    """
    choice=next((x for x in row.get('choices',[]) if x['id']==choice_id),{})
    return choice.get('action') in {'return_home','lvg','politics','love_retire','press_retire','finish'}


def opinion(c,s,text,occurrence):
    v=state(c)
    support = (f"{PARTNERS.get(v['partner'],'她')}发来消息：‘我看见了那些话。你可以跟我说难过，不用在我面前也装作无所谓。’" if v.get('romance')=='stable' else '队友说，今晚先一起复盘，不必独自承受所有声音。')
    queue(c,s,'press',occurrence,{'opinion':text,'support':support,'reward_key':'press:'+occurrence})
    v['last_press']=s.date


def on_series(c,s,ev,match):
    if not active(c) or not match.get('played') or match.get('forfeit') or not match.get('maps'):return
    v=state(c);key=key_for(s,ev,match)
    if any(r['key']==key for r in v['series']):return
    you=c.my_player(s.teams);team=c.my_team(s.teams)
    if not you or not team or team['name'] not in (match['team_a'],match['team_b']):return
    maps=[]
    for mp in match['maps']:
        for p in (mp.get('players') or {}).get(team['name'],[]):
            if p.get('player_id')==you.get('player_id') or (not p.get('player_id') and p.get('name')==c.player_name):
                maps.append({'rating':p.get('rating'), 'rounds':p.get('rounds') or mp.get('rounds',0)})
    roster=sorted(p.get('player_id') or p['name'] for p in team['players'])
    v['series'].append(dict(key=key,event=key_for(s,ev),date=s.date,team_id=team['id'],roster=roster,
                            win=match.get('winner')==team['name'],maps=maps,role=c.role))
    na_progress(c,commit=True)
    v['series']=v['series'][-300:]
    if v['romance']=='waiting' and not v['na']:queue(c,s,'romance_start','first-series')
    if key in v.get('reunion_choices',{}):
        line='对面赛后主动过来握手：“今天你们打得好。下一次我们会准备得更充分。”' if match.get('winner')==team['name'] else '旧队赢下了比赛，但握手时没有再追着赛前的话不放：“下次见，继续加油。”'
        notice(c,s,'握手的时候',line,key+':reunion-result')
    you['story_form_delta']=0
    # Major reaction takes precedence on its closing series; avoid two bad
    # press choices and two focus rewards for the same sporting result.
    from ..league import formats
    if ev.get('type')!='major' or not formats.is_complete(ev):check_press(c,s)


def check_press(c,s):
    v=state(c);r=config()['rules']
    if v['last_press'] and after(v['last_press'],r['press_cooldown_days'])>s.date:return
    rows=[x for x in v['series'] if x['team_id']==c.team_id and x['date']>=after(s.date,-r['press_days']) and x['role']==c.role]
    maps=[m for x in rows for m in x['maps'] if isinstance(m.get('rating'),(int,float))]
    if len(maps)<r['press_min_maps']:return
    rating=sum(m['rating'] for m in maps)/len(maps);win=sum(x['win'] for x in rows)/len(rows)
    text=''
    if c.role=='igl' and win<.35:text=f'最近{len(rows)}场只赢了{sum(x["win"] for x in rows)}场，讨论开始集中在指挥的组织与临场方向，而不是你的击杀数。'
    elif c.role!='igl' and rating<r['press_bad_rating']:
        text=f'最近{len(maps)}图平均Rating约{rating:.2f}。'+('虽然队伍一直在赢，仍有人质疑你的贡献；也有人提醒，你的分工不能只用击杀解释。' if win>=.6 else '持续低迷的数据让外界开始质疑这个位置，要求更换选手的声音越来越多。')
    elif c.role!='igl' and rating>r['press_good_rating'] and win<.4:
        text=f'最近{len(maps)}图平均Rating约{rating:.2f}，胜利却没有随之到来。有人替你惋惜，也有人追问漂亮的数据为何没能转化成成绩。'
    if text:opinion(c,s,text,'personal:'+s.date)


def event_open(c,s,ev):
    if not active(c):return
    field=set(ev.get('field',[])); teams=[t for t in s.teams if t['name'] in field]
    ordered=sorted(teams,key=lambda t:(-sum(playing_ability(p) for p in t['players'])/5,t['id']))
    ev['arc_expectations']={t['id']:i+1 for i,t in enumerate(ordered)}


def event_done(c,s,ev):
    if not active(c):return
    from ..league.awards import placements
    v=state(c);key=key_for(s,ev)
    if key in v.setdefault('finished_events',[]):return
    v['finished_events'].append(key)
    mine=c.my_team(s.teams); participated=[r for r in v['series'] if r['event']==key]
    if participated:
        winner=ev.get('champion')==(mine or {}).get('name')
        v['events'].append(dict(key=key,date=s.date,type=ev.get('type'),winner=winner,name=ev.get('name','赛事'),
                               wins=sum(r['win'] for r in participated),team_id=c.team_id))
        if v['romance']=='dating' and len(v['events'])>=2 and not v.get('pace'):queue(c,s,'romance_pace','second-event')
    if ev.get('type')=='major':
        champion=ev.get('champion') or '未知队伍'; mvp=(ev.get('awards') or {}).get('mvp') or {}
        champ_team=next((t for t in s.teams if t['name']==champion),{})
        rank=ev.get('arc_expectations',{}).get(champ_team.get('id'),99)
        final=next((m for m in ev['matches'] if m.get('stage')=='GF' and m.get('played')), {})
        from .news import report
        context=dict(champion=champion,event=ev['name'],mvp=mvp.get('player') or '未公布',
                     roster='、'.join(ev.get('champion_roster',[])) or '历史阵容未记录',
                     final=f"{final.get('team_a','')} {final.get('series','')} {final.get('team_b','')}" if final else '决赛详情未记录')
        title,text=report(c,'champion_favourite' if rank<=config()['rules']['major_favourite_rank'] else 'champion_surprise',key,context)
        notice(c,s,title,text,key+':champion')
        c._push_mail('news',s.date,{'title':title,'from':'Major赛事专栏','body':text},{'status':'closed','event_id':ev['id']})
        if v.get('heat') and s.date>=v.get('heat_since',''):
            v['heat']=False;notice(c,s,'热恋回到生活的节奏','这届Major已经结束，热恋带来的额外状态波动停止。接下来如何相处，仍取决于两个人的沟通。',key+':heat-end')
        if participated and mine:
            spot=placements(ev).get(mine['name'],'stage');actual={'champion':0,'final':1,'sf':2,'qf':3}.get(spot,4)
            # An actual personally played final loss, not merely belonging to
            # a finalist club (nor a forfeit, bye or another team's final).
            if (final.get('id') and not final.get('forfeit') and
                mine['name'] in (final.get('team_a'),final.get('team_b')) and
                final.get('winner') in (final.get('team_a'),final.get('team_b')) and
                final['winner']!=mine['name'] and final['winner']!='BYE' and
                any(row.get('key')==key_for(s,ev,final) for row in participated)):
                queue(c,s,'major_final_loss',key,dict(event=ev['name'],team=mine['name'],
                    opponent=final['winner'],final_score=f"{final['team_a']} {final.get('series') or '比分未记录'} {final['team_b']}"))
            r=config()['rules']
            rank=ev.get('arc_expectations',{}).get(mine['id'],99);expected=2 if rank<=r['major_favourite_rank'] else 3 if rank<=r['major_contender_rank'] else 4
            mood='激动' if actual==0 or actual<expected else '失望' if actual>expected else '预料之中'
            maps=[m['rating'] for row in participated for m in row.get('maps',[]) if isinstance(m.get('rating'),(int,float)) and math.isfinite(m['rating'])]
            context.update(team=mine['name'],player=c.player_name,rank=rank,
                placement={'champion':'冠军','final':'亚军','sf':'四强','qf':'八强'}.get(spot,'未进八强'),
                expected={2:'至少四强',3:'至少八强',4:'争取突破小组阶段'}[expected],
                performance=f"{c.player_name}在已记录的{len(maps)}张地图中，地图平均Career Rating为{sum(maps)/len(maps):.2f}。" if maps else '本次未保存完整个人数据，本文不推测个人发挥。')
            title,text=report(c,{'激动':'major_excited','失望':'major_disappointed','预料之中':'major_expected'}[mood],key,context)
            c._push_mail('news',s.date,{'title':title,'from':'Major赛后观察','body':text},{'status':'closed','event_id':ev['id']})
            if mood=='失望':opinion(c,s,text,key+':major')
            else:notice(c,s,title,text,key+':opinion')
            if mood=='失望':
                v.setdefault('history',[]).append(dict(id='major-report:'+key,date=s.date,title=title,text=text))
    check_politics(c,s)


def check_politics(c,s):
    from .transfers import locked
    v=state(c);r=config()['rules'];team=c.my_team(s.teams)
    if not team or locked(s,team) or len(team['players'])!=5:return
    if v['last_politics'] and after(v['last_politics'],r['politics_cooldown_days'])>s.date:return
    roster=sorted(p.get('player_id') or p['name'] for p in team['players'])
    rows=[]
    for x in reversed(v['series']):
        if x['team_id']!=team['id'] or x['roster']!=roster:break
        rows.append(x)
        if len(rows)>=r['politics_window']:break
    events=[e for e in v['events'] if e['team_id']==team['id']][-r['politics_empty_events']:]
    if len(rows)<r['politics_min_series'] or sum(x['win'] for x in rows)/len(rows)>r['politics_win_rate'] or len(events)<r['politics_empty_events'] or any(e['wins'] for e in events):return
    others=sorted((p for p in team['players'] if not p.get('you')),key=lambda p:p.get('player_id') or p['name'])
    target=others[int(roll(c,'politics-target:'+s.date)*len(others))]
    ctx=dict(series_count=len(rows),wins=sum(x['win'] for x in rows),target=target['name'],
             target_id=target.get('player_id') or target['name'],roster_ids=roster,
             allies='、'.join(p['name'] for p in others if p is not target))
    queue(c,s,'politics',s.date,ctx);v['last_politics']=s.date


def before_match(c,s,ev,match):
    if not active(c):return
    from . import player_transfers as pt
    v=state(c);key=key_for(s,ev,match)
    moves=[m for m in pt.state(c)['moves'] if m.get('old_team')]
    if moves and moves[-1]['old_team']!=(c.my_team(s.teams) or {}).get('name') and moves[-1]['old_team'] in (match['team_a'],match['team_b']):
        queue(c,s,'reunion',key,{'old_team':moves[-1]['old_team'],'match_key':key})
    player=c.my_player(s.teams)
    if player:
        offset=0
        if v.get('heat'):
            amplitude=config()['rules']['heat_amplitude'];offset=(int(roll(c,key+':heat')*(2*amplitude+1))-amplitude)
        injury=v.get('injury_active',{})
        player['story_form_delta']=offset+(injury.get('penalty',0) if injury.get('until','')>s.date else 0)


def birthday(c,s,name,choice):
    cfg=config();pool=cfg['birthday']['train' if choice=='train' else 'wish']
    index=int(roll(c,s.date+name+choice)*len(pool))
    notice(c,s,name+'的回应',render(pool[index],{'teammate':name}),s.date+':birthday:'+name)


def na_progress(c, *, commit=False):
    """Personal map samples, not team trophies. Keep totals past series pruning.

    Old saves are seeded only from retained, identified personal map records;
    missing maps never become zero-rated samples. Public GETs do not mutate.
    """
    v=state(c);r=config()['rules'];start=v.get('returned') if v.get('na')=='returned' else v.get('started')
    deadline=v.get('deadline','')
    tally=deepcopy(v.get('na_stats',{}))
    if tally.get('start')!=start or tally.get('deadline')!=deadline:
        tally=dict(start=start,deadline=deadline,keys=[],maps=0,total=0.0)
    seen=set(tally['keys'])
    if start and deadline and v.get('na') in ('study','pro','returned'):
        for row in v.get('series',[]):
            if row['key'] in seen or not start<=row['date']<=deadline:continue
            for mp in row.get('maps',[]):
                rating=mp.get('rating')
                if type(rating) in (float,int) and math.isfinite(rating) and .2<=rating<=2.5:
                    tally['maps']+=1;tally['total']+=rating
            tally['keys'].append(row['key']);seen.add(row['key'])
        if commit:v['na_stats']=tally
    avg=tally['total']/tally['maps'] if tally['maps'] else None
    return dict(maps=tally['maps'],rating=avg,min_maps=r['na_min_maps'],min_rating=r['na_min_rating'],
                passed=tally['maps']>=r['na_min_maps'] and avg is not None and avg>=r['na_min_rating'])


def na_achievements(c):
    v=state(c);start=v.get('returned',v['started']) if v.get('na')=='returned' else v['started']
    return [e for e in v['events'] if e.get('winner') and e.get('type') in config()['rules']['na_success_types']
            and start<=e['date']<=v.get('deadline','')]


def na_first_assessment(c,s,progress):
    """Freeze both independent qualifications before either letter is shown."""
    from .news import report, publish
    v=state(c);titles=na_achievements(c)
    v['na_assessment']=dict(date=s.date,deadline=v['deadline'],achievement=bool(titles),**progress)
    rating=f"{progress['rating']:.2f}" if progress['rating'] is not None else '尚无有效样本'
    ctx=dict(player=c.player_name,achievement='、'.join(e.get('name') or e.get('key') or e['type']+'赛事' for e in titles)+'夺冠',
        assessment=f"你的正式比赛记录是{progress['maps']}张地图，地图平均Career Rating {rating}。"+
        ('个人表现已经达到了职业邀约的数据标准。我们看见了你的努力，也知道一个人打得好不一定立刻有冠军。' if progress['passed'] else '目前的样本量或个人表现，还没有达到约定的数据标准。这不是给你的天赋下结论，却是我们需要一起面对的现状。'))
    key='na-family:'+v['deadline']
    title,text=report(c,'family_support' if titles else 'family_return',key,ctx)
    publish(c,s,key,title,text,sender='家里',popup=True)
    if titles or progress['passed']:
        v['na']='invite_wait'
    else:
        v['na']='return_pending';queue(c,s,'na_return','first-deadline')


def tick(c,s):
    if not active(c):return
    v=state(c);r=config()['rules']
    from .transfers import locked
    team=c.my_team(s.teams)
    # Do not present a blocking roster decision which can only be resolved
    # after finishing the very tournament the decision would prevent playing.
    roster_busy=bool(c.training_session or (team and locked(s,team)))
    if not roster_busy:check_politics(c,s)
    if v['romance']=='dating' and v.get('pace') and after(v['romance_started'],r['marriage_days'])<=s.date:
        queue(c,s,'marriage','six-months')
    na=v.get('na','')
    if na in ('study','pro','returned') and s.date>=v['deadline'] and not roster_busy and not any(x.get('choices') for x in c.story_queue):
        progress=na_progress(c,commit=True)
        if na in ('study','pro'):na_first_assessment(c,s,progress)
        else:
            won=progress['passed'] or bool(na_achievements(c))
            v['na_assessment']=dict(date=s.date,deadline=v['deadline'],achievement=bool(na_achievements(c)),**progress)
            if not won:finish(c,s,'caster');return
            v['na']='achieved';queue(c,s,'dota_partner','return-success')
    # Never let an invitation lock the player out of advancing the tournament
    # the target club must first finish. The family letter is already readable.
    if v.get('na')=='invite_wait' and not roster_busy and not any(x.get('choices') for x in c.story_queue):
        target=next((t for t in s.teams if t['name']==r['lvg_team_name']),None)
        if not target or not locked(s,target):
            queue(c,s,'lvg_invite','anniversary');v['na']='lvg_pending'
            row=next((x for x in c.story_queue if x.get('arc')=='lvg_invite'),None)
            if row:
                from .news import publish
                publish(c,s,'na-invite:'+v['deadline'],row['title'],row['text'],sender=r['lvg_team_name'])
    if v.get('na')=='returned' and s.date>=after(v['returned'],r['return_partner_days']) and v.get('partner')!='dota':
        queue(c,s,'dota_partner','home-meeting')
    injury=v.get('injury_active',{})
    if injury and s.date>=injury['until']:
        notice(c,s,'逐渐回到熟悉的节奏','这一段负状态影响结束了。队友把训练安排发来：“不急着证明今天全好了，先把能做好的做稳。”\n暂时的状态惩罚已解除；此前下降的能力不会自动补回。',injury['id']+':recovery')
        v['injury_active']={}
        p=c.my_player(s.teams)
        if p:p['story_form_delta']=0
    if v['monthly']==s.date[:7]:return
    v['monthly']=s.date[:7]
    p=c.my_player(s.teams) or c.you_card
    if not p or v.get('injury_active'):return
    if any(not m.get('played') and (m.get('cs2_session') or m.get('maps')) for e in s.events for m in e.get('matches',[]) if (c.my_team(s.teams) or {}).get('name') in (m.get('team_a'),m.get('team_b'))):return
    injuries=v['injuries']
    if sum(x['date'][:4]==s.date[:4] for x in injuries)>=r['injury_year_limit']:return
    if injuries and after(injuries[-1]['date'],r['injury_cooldown_days'])>s.date:return
    rate=next((prob for age,prob in r['injury_monthly_rates'] if int(p.get('age',19))<=age),0)
    if roll(c,'injury:'+s.date[:7])>=rate:return
    pool=[i for i in config()['injuries'] if i['id'] not in [x['type'] for x in injuries[-3:]] and (i['id']!='recurrence' or injuries)]
    item=pool[int(roll(c,'injury-kind:'+s.date[:7])*len(pool))]
    loss=1+int(roll(c,'injury-loss:'+s.date[:7])*2);stats=p['stats'];changes=[]
    for n in range(loss):
        axis=item['axes'][int(roll(c,f'injury-axis:{s.date[:7]}:{n}')*len(item['axes']))]
        before=float(stats.get(axis,50));stats[axis]=max(1,before-1);changes.append(f'{AXIS_LABEL[axis]} {before:g}→{stats[axis]:g}')
    refresh_player_ability(p)
    record=dict(id='injury:'+s.date[:7],type=item['id'],date=s.date,loss=loss,changes=changes)
    injuries.append(record);v['injury_active']=dict(id=record['id'],until=after(s.date,r['injury_duration_days']),penalty=r['injury_form_penalty'])
    p['story_form_delta']=r['injury_form_penalty']
    text=item['texts'][int(roll(c,'injury-text:'+s.date[:7])*len(item['texts']))]
    text+='\n\n游戏效果：'+ '，'.join(changes)+f"。状态暂时{r['injury_form_penalty']:+d}，到{v['injury_active']['until']}解除。\n这是生涯世界的伤病设定，不代表现实诊断。"
    if v.get('romance')=='stable':text+=f"\n{PARTNERS.get(v['partner'],'她')}告诉你：‘今天不需要再逞强，我陪你把这段时间过完。’"
    notice(c,s,item['name'],text,record['id']);c._remember_you(s)


def public(c):
    v=state(c)
    out={k:deepcopy(v.get(k)) for k in ('enabled','na','deadline','romance','partner','heat','injury_active')}
    out['history']=deepcopy(v.get('history',[])[-30:])
    out['na_bonus']=config()['rules']['na_bonus']
    if v.get('na') in ('study','pro','returned'):
        out['na_progress']=na_progress(c)
        out['na_progress']['achievement']=bool(na_achievements(c))
        out['na_progress']['success_types']=config()['rules']['na_success_types']
    return out


def history_page(c, page=1):
    """Paginate saved text, not reconstructed/re-simulated historical scenes."""
    if page<1:raise ValueError('页码应为正整数')
    rows=state(c).get('history',[]);end=max(0,len(rows)-(page-1)*20)
    return dict(rows=deepcopy(list(reversed(rows[max(0,end-20):end]))),page=page,
                pages=max(1,(len(rows)+19)//20),total=len(rows))
