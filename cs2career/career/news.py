"""Read-only world reporting through the existing mail/story channels.

Facts are captured on business commands, never on a UI GET. Roster snapshots
use stable IDs; no invented transfer fees, rumours, interviews or future results.
The lightweight journal survives season rollover in Career.incident_state.
Text templates are data/career_news.json, overridden by arc_overrides.reports.
"""
from copy import deepcopy
import hashlib
import math
import re


def report(c, kind, occurrence, context, *, language='zh-CN'):
    from .arcs import config, render
    node=config()['reports'][kind]
    index=int.from_bytes(hashlib.sha256((kind+'|'+occurrence).encode()).digest()[:8],'big')%len(node['text'])
    if language=='en' and node.get('title_en') and node.get('text_en'):
        translated={**context}
        for key,value in context.items():
            if key.endswith('_en'):translated[key[:-3]]=value
        return render(node['title_en'],translated),render(node['text_en'][index%len(node['text_en'])],translated)
    return render(node['title'],context),render(node['text'][index],context)


def publish(c,s,key,title,text,*,sender='世界赛场编辑部',popup=False,
            title_en=None,text_en=None,sections=None):
    sent=c.incident_state.setdefault('news_publications',[])
    if key in sent:return
    sent.append(key)
    localized={}
    if title_en is not None:localized['title_en']=title_en
    if text_en is not None:localized['text_en']=text_en
    if sections is not None:localized['sections']=deepcopy(sections)
    mail_extra={'status':'closed','publication_key':key,**localized}
    if text_en is not None:mail_extra['body_en']=text_en
    quiet_month=key.startswith('monthly:') and c.assist.get('quick_mode')
    if not quiet_month:
        c._push_mail('news',s.date,dict(title=title,body=text,**{'from':sender}),mail_extra)
    archive=c.incident_state.setdefault('arcs',{}).setdefault('history',[])
    archive.append(dict(id='news:'+key,date=s.date,title=title,text=text,publication_key=key,**localized))
    # Quick monthly digests are archive-only: no unread badge or interruption.
    if popup and not quiet_month:
        c.story_queue.append(dict(id='news:'+key,kind='story',when='world_news',title=title,text=text,publication_key=key,**localized))


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
            text_en=f"{after['player']} joined {after['team']} from {before['team']}."
        elif after:
            text=f"{after['player']} 进入 {after['team']} 的现役阵容。"
            text_en=f"{after['player']} joined the active roster of {after['team']}."
        else:
            text=f"{before['player']} 离开 {before['team']} 的现役阵容。"
            text_en=f"{before['player']} left the active roster of {before['team']}."
        v['facts'].append(dict(date=s.date,kind='transfer',text=text,text_en=text_en,player_id=pid))
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
    text_en=f"{ev['name']}: {winner} won the title."
    if mvp.get('player'):
        text+=f"本届MVP为 {mvp['player']}。"
        text_en+=f" MVP: {mvp['player']}."
    v['facts'].append(dict(date=s.date,kind='champion',text=text,text_en=text_en,champion=winner,
                          event_type=ev.get('type'),name=ev['name'],key=key))


def next_month(stamp):
    year,month=map(int,stamp.split('-'))
    return f'{year+1}-01' if month==12 else f'{year}-{month+1:02d}'


def _fact_item(row):
    """Translate older recorded facts without inventing absent event details."""
    text=row.get('text','')
    translated=row.get('text_en')
    if translated is None:
        for pattern,template in (
            (r'^(.+) 从 (.+) 转入 (.+)。$', lambda m:f"{m[1]} joined {m[3]} from {m[2]}."),
            (r'^(.+) 进入 (.+) 的现役阵容。$', lambda m:f"{m[1]} joined the active roster of {m[2]}."),
            (r'^(.+) 离开 (.+) 的现役阵容。$', lambda m:f"{m[1]} left the active roster of {m[2]}."),
            (r'^(.+)：(.+) 夺冠。(?:本届MVP为 (.+)。)?$', lambda m:f"{m[1]}: {m[2]} won the title."+ (f" MVP: {m[3]}." if m[3] else '')),
        ):
            match=re.fullmatch(pattern,text)
            if match:
                translated=template(match);break
    return dict(text=text,text_en=translated if translated is not None else text)


def _section(key,title,title_en,items):
    return dict(id=key,title=title,title_en=title_en,items=items)


def _section_text(sections,english=False):
    field='text_en' if english else 'text'
    heading='title_en' if english else 'title'
    return '\n\n'.join('【'+section[heading]+'】\n'+
        '\n'.join('• '+row[field] for row in section['items']) for section in sections)


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
        priority={'major':0,'t1':1,'t2':2,'qual':3,'cct':4}
        titles=sorted((r for r in facts if r['kind']=='champion'),
                      key=lambda r:(priority.get(r.get('event_type'),5),r['date'],r.get('key','')))
        moves=[r for r in facts if r['kind']=='transfer']
        rows=[r for r in c.incident_state.get('arcs',{}).get('series',[]) if r['date'][:7]==stamp]
        ratings=[m['rating'] for r in rows for m in r.get('maps',[])
                 if type(m.get('rating')) in (int,float) and math.isfinite(m['rating'])]
        sections=[]
        if rows:
            wins=sum(bool(r['win']) for r in rows);losses=len(rows)-wins
            items=[dict(text=f"{len(rows)} 场系列赛 · {wins} 胜 {losses} 负",
                        text_en=f"{len(rows)} series · {wins} wins, {losses} losses")]
            if ratings:
                average=sum(ratings)/len(ratings)
                items.append(dict(text=f"个人地图平均 Career Rating {average:.2f} · {len(ratings)} 张已记录地图",
                                  text_en=f"Personal average map Career Rating {average:.2f} · {len(ratings)} recorded maps"))
            sections.append(_section('team','你的赛程','Your month',items))
        if titles:
            sections.append(_section('champions','赛场冠军','Tournament winners',[_fact_item(r) for r in titles]))
        if moves:
            sections.append(_section('transfers','转会与阵容','Transfers and rosters',[_fact_item(r) for r in moves]))
        # Only the final covered month has a contemporaneous ranking snapshot.
        # Earlier skipped months omit ranking rather than backdate today's data.
        if following==month and current:
            leaders=sorted(current.values(),key=lambda r:r['rank'])[:5]
            items=[dict(text=f"截至 {s.date} · "+'、'.join(f"#{r['rank']} {r['name']}" for r in leaders),
                        text_en=f"As of {s.date} · "+' / '.join(f"#{r['rank']} {r['name']}" for r in leaders))]
            risers=[(delta,row) for delta,row in changes if delta>0][:3]
            fallers=sorted(((-delta,row) for delta,row in changes if delta<0),key=lambda x:(-x[0],x[1]['rank']))[:2]
            for direction,rows_changed in (('up',risers),('down',fallers)):
                for delta,row in rows_changed:
                    items.append(dict(text=f"{row['name']} {'↑' if direction=='up' else '↓'} {delta} 位 → #{row['rank']}",
                                      text_en=f"{row['name']} {direction} {delta} → #{row['rank']}"))
            sections.append(_section('ranking','排名变化','Ranking changes',items))
        lead=titles[0] if titles else None
        headline=f"{lead['champion']}夺冠" if lead else '阵容更新' if moves else '本月记录'
        headline_en=f"{lead['champion']} take the title" if lead else 'Roster changes' if moves else 'The month in review'
        summary=f"{len(titles)} 项赛事收官 · {len(moves)} 次名单变动"
        summary_en=f"{len(titles)} tournaments concluded · {len(moves)} roster changes"
        # Empty months keep a short, honest record instead of five empty headings.
        body=_section_text(sections) or '本月没有新增的赛事或阵容记录。'
        body_en=_section_text(sections,True) or 'No new tournament or roster records this month.'
        context=dict(month=stamp,headline=headline,headline_en=headline_en,coverage=v['started'],
            summary=summary,summary_en=summary_en,sections=body,sections_en=body_en,
            # Keep old extension report placeholders functional.
            champions='\n'.join(r['text'] for r in titles),transfers='\n'.join(r['text'] for r in moves),
            rankings='\n'.join(r['text'] for sec in sections if sec['id']=='ranking' for r in sec['items']),
            personal='\n'.join(r['text'] for sec in sections if sec['id']=='team' for r in sec['items']),upcoming='')
        title,text=report(c,'monthly',stamp,context)
        title_en,text_en=report(c,'monthly',stamp,context,language='en')
        publish(c,s,'monthly:'+stamp,title,text,popup=following==month and not c.assist.get('quick_mode'),
                title_en=title_en,text_en=text_en,sections=sections)
        v['month']=following
    v['facts']=[r for r in v['facts'] if r['date'][:7]>=month]
    v['ranking']=current
