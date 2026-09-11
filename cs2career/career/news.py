"""Read-only world reporting through the existing mail/story channels.

Facts are captured on business commands, never on a UI GET. Roster snapshots
use stable IDs; no invented transfer fees, rumours, interviews or future results.
The lightweight journal survives season rollover in Career.incident_state.
Text templates are data/career_news.json, overridden by arc_overrides.reports.
"""
from collections import Counter
import hashlib


def report(c, kind, occurrence, context):
    from .arcs import config, render
    node=config()['reports'][kind]
    index=int.from_bytes(hashlib.sha256((kind+'|'+occurrence).encode()).digest()[:8],'big')%len(node['text'])
    return render(node['title'],context),render(node['text'][index],context)


def publish(c,s,key,title,text,*,sender='世界赛场编辑部',popup=False):
    sent=c.incident_state.setdefault('news_publications',[])
    if key in sent:return
    sent.append(key)
    c._push_mail('news',s.date,dict(title=title,body=text,**{'from':sender}),{'status':'closed'})
    archive=c.incident_state.setdefault('arcs',{}).setdefault('history',[])
    archive.append(dict(id='news:'+key,date=s.date,title=title,text=text))
    if popup:
        c.story_queue.append(dict(id='news:'+key,kind='story',when='world_news',title=title,text=text))


def roster(s):
    rows={};duplicates=set()
    for t in s.teams:
        for p in t.get('players',[]):
            pid=p.get('player_id')
            if not pid:continue
            if pid in rows:duplicates.add(pid)
            rows[pid]=dict(team_id=t['id'],team=t['name'],player=p['name'])
    for pid in duplicates:rows.pop(pid,None)
    return rows


def standings(s):
    return {r['id']:dict(rank=r['rank'],name=r.get('name') or r.get('team') or r['id'])
            for r in s.vrs.table(s.teams,s.date)}


def initialize(c,s):
    if 'world_news' not in c.incident_state:
        c.incident_state['world_news']=dict(month=s.date[:7],started=s.date,roster=roster(s),
                                          ranking=standings(s),facts=[],events=[])
    return c.incident_state['world_news']


def capture_roster(c,s):
    v=initialize(c,s);old=v['roster'];new=roster(s)
    for pid in sorted(set(old)|set(new)):
        before=old.get(pid);after=new.get(pid)
        if before and after and before['team_id']==after['team_id']:continue
        if before and after:
            text=f"{after['player']} 从 {before['team']} 转入 {after['team']}。"
        elif after:text=f"{after['player']} 进入 {after['team']} 的现役阵容。"
        else:text=f"{before['player']} 离开 {before['team']} 的现役阵容。"
        v['facts'].append(dict(date=s.date,kind='transfer',text=text,player_id=pid))
    v['roster']=new


def event_done(c,s,ev):
    if not c.exists or c.over():return
    v=initialize(c,s);key=f"{s.year}:{ev['id']}"
    if key in v['events']:return
    v['events'].append(key)
    winner=ev.get('champion')
    if not winner:return
    mvp=(ev.get('awards') or {}).get('mvp') or {}
    text=f"{ev['name']}：{winner} 夺冠。"
    if mvp.get('player'):text+=f"本届MVP为 {mvp['player']}。"
    v['facts'].append(dict(date=s.date,kind='champion',text=text,champion=winner,
                          event_type=ev.get('type'),name=ev['name'],key=key))


def next_month(stamp):
    year,month=map(int,stamp.split('-'))
    return f'{year+1}-01' if month==12 else f'{year}-{month+1:02d}'


def tick(c,s):
    if not c.exists or c.over():return
    v=initialize(c,s)
    capture_roster(c,s)
    month=s.date[:7]
    if v['month']>=month:return
    current=standings(s)
    old=v['ranking']
    changes=sorted(((old[pid]['rank']-row['rank'],row) for pid,row in current.items() if pid in old),
                   key=lambda x:(-x[0],x[1]['rank']))
    while v['month']<month:
        stamp=v['month'];following=next_month(stamp)
        facts=[r for r in v['facts'] if r['date'][:7]==stamp]
        titles=[r for r in facts if r['kind']=='champion']
        moves=[r for r in facts if r['kind']=='transfer']
        champions='\n'.join(r['text'] for r in titles) or '本期记录中没有新产生的赛事冠军。尚未结束的比赛不提前填写结果。'
        counts=Counter(r['champion'] for r in titles)
        repeats=[f'{name}（{count}冠）' for name,count in counts.items() if count>1]
        if repeats:champions+='\n本月多冠队伍：'+'、'.join(repeats)+'。'
        transfers='\n'.join(r['text'] for r in moves) or '本期未记录到现役名单变动。没有官宣不等于存在传闻，本报不推测私下接触。'
        if following==month:
            leaders=sorted(current.values(),key=lambda r:r['rank'])[:5]
            rankings=f"截至发稿日{s.date}，VRS前五："+'、'.join(f"{r['name']}（{r['rank']}）" for r in leaders)+'。'
            risers=[(delta,row) for delta,row in changes if delta>0][:3]
            if risers:rankings+='\n相较上次记录，上升较多的队伍：'+'、'.join(f"{r['name']}上升{d}位" for d,r in risers)+'。'
            fallers=sorted(((-delta,row) for delta,row in changes if delta<0),key=lambda x:(-x[0],x[1]['rank']))[:2]
            if fallers:rankings+='\n排名回落：'+'、'.join(f"{r['name']}下降{d}位" for d,r in fallers)+'。排名变化不是某一名选手的单独责任。'
        else:rankings='这段跨月期间未保存独立月末排名快照，不用当前排名冒充当时的榜单。'
        rows=[r for r in c.incident_state.get('arcs',{}).get('series',[]) if r['date'][:7]==stamp]
        ratings=[m['rating'] for r in rows for m in r.get('maps',[]) if type(m.get('rating')) in (int,float)]
        personal=f"本期已记录你的{len(rows)}场系列赛，{sum(bool(r['win']) for r in rows)}胜{sum(not r['win'] for r in rows)}负。" if rows else '本期没有可汇总的个人正式系列赛记录；这不等同于推断你没有训练或参加活动。'
        if ratings:personal+=f"{len(ratings)}张有效地图的地图平均Career Rating为{sum(ratings)/len(ratings):.2f}。"
        calendar=sorted((e for e in s.events if e.get('status') in ('live','upcoming') and e.get('dates')),key=lambda e:e['dates'][0])[:4]
        upcoming=f"截至发稿日{s.date}的赛历：\n"+'\n'.join(f"{e['name']} · {'进行中' if e['status']=='live' else e['dates'][0]+'开始'}" for e in calendar) if calendar else '当前赛历暂无待开始赛事，已结束的赛事仍可从赛事资料页查看。'
        priority={'major':0,'t1':1,'t2':2,'qual':3,'cct':4}
        lead=min(titles,key=lambda r:priority.get(r.get('event_type'),5)) if titles else None
        headline=f"{lead['champion']}拿下{lead['name']}" if lead else '阵容有了新变化' if moves else '赛历翻页，等待下一次交锋'
        title,text=report(c,'monthly',stamp,dict(month=stamp,headline=headline,coverage=v['started'],
            champions=champions,transfers=transfers,rankings=rankings,personal=personal,upcoming=upcoming))
        # One visible summary after a multi-month jump; all months stay in mail.
        publish(c,s,'monthly:'+stamp,title,text,popup=following==month)
        v['month']=following
    v['facts']=[r for r in v['facts'] if r['date'][:7]>=month]
    v['ranking']=current
