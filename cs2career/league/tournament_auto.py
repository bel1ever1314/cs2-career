"""One bounded player command per request; no background season simulation.

Uses the ordinary gate/skip/next-stage commands. The UI must explicitly request
each step. A retry token returns the prior step, never a second settlement.
Decisive-game authorization is scoped to year/event/match/current team.
"""
from __future__ import annotations

import json
from ..paths import data_file
from ..career import incidents
from . import formats


def key(s, ev, match):
    return f"{s.year}:{ev['id']}:{match['id']}:{s.career.team_id}"


def decisive(ev, match):
    if match.get('stage') == 'GF':
        return 'final'
    if match.get('stage') in ('R16','QF','SF'):
        return 'elimination'
    if (match.get('meta') or {}).get('kind') in ('elim','decider'):
        return 'elimination'
    record = str((match.get('meta') or {}).get('record') or '').split('-')
    if len(record)==2 and record[1]=='2':
        return 'elimination'
    return ''


def blocker(c, s):
    if c.over(): return '这段生涯已经结束。'
    if c.unsigned: return '当前是自由身，请先决定新的队伍。'
    if c.loan_default_pending: return '请先处理俱乐部最后通牒。'
    if c.fix_pending: return '请先回复未署名的来信。'
    if c.personal_transfers.get('pending'): return '请先决定加盟机会。'
    if c.story_queue or incidents.pending(c): return '有新事件，请先由你作出选择，再继续模拟。'
    if incidents.competition_paused(c,s.date): return '当前暂停参赛，自动模拟不会替你弃权；请手动处理赛程。'
    if any(m.get('cs2_session') and not m.get('played') for e in s.events for m in e.get('matches',[])):
        return '有一场已连接CS2的比赛，先完成或手动处理回传，自动模拟不会覆盖它。'
    return ''


def moment(c, s, ev, match, kind):
    sid = 'tournament-moment:' + key(s,ev,match)
    if any(r.get('id')==sid for r in c.story_queue): return
    raw=json.loads(data_file('tournament_moments.json').read_text('utf-8'))
    ctx={'event':ev['name'],'stage':formats.stage_title(match),'team':s.your_team_name(),
         'player':c.player_name,'opponent':match['team_b'] if match['team_a']==s.your_team_name() else match['team_a']}
    def text(value):
        for name,val in ctx.items(): value=value.replace('{'+name+'}',str(val))
        return value
    c.story_queue.append({'id':sid,'kind':'story','when':'tournament_decision',
        'title':text(raw[kind]['title']),'text':text(raw[kind]['text']),
        'choices':[{'id':name,'label':raw['choices'][name]} for name in ('manual','simulate','later')],
        'auto_match':key(s,ev,match),'event_id':ev['id'],'match_id':match['id'],'team_id':c.team_id})


def resolve(c, s, row, choice):
    ev,match=s.find_match(row['match_id'])
    if not ev or not match or row.get('auto_match')!=key(s,ev,match) or match.get('played'):
        raise ValueError('比赛身份或状态已经变化，请重新打开赛事。')
    c.assist['tournament']={'event_id':ev['id'],'match_id':match['id'],'choice':choice,
                            'approval':key(s,ev,match) if choice=='simulate' else ''}


def step(c, s, eid, token, expected=None):
    if not isinstance(token,str) or not 8<=len(token)<=100:
        raise ValueError('缺少有效的单步请求编号。')
    if '::' in eid:
        year,eid=eid.split('::',1)
        if year!=str(s.year): raise ValueError('不能自动模拟历史赛事。')
    prior=c.assist.get('last_step') or {}
    if prior.get('token')==token:
        if prior.get('event_id')!=eid or prior.get('year')!=s.year: raise ValueError('请求编号已用于其他赛事。')
        return prior['result']
    counter=int(c.assist.get('step_counter') or 0)
    if expected is not None and expected!=counter:
        raise ValueError('模拟进度已变化，本次未执行。请刷新赛事后继续。')
    ev=next((e for e in s.events if e['id']==eid),None)
    if not ev: raise ValueError('没有找到当前赛季的赛事。')
    if not c.exists or (s.your_team_name() not in (ev.get('field') or []) and eid not in c.registered):
        raise ValueError('只能自动模拟自己参加或已接受邀请的赛事。')
    def finish(status,msg,**extra):
        result={'status':status,'msg':msg,'event_id':eid,**extra}
        c.assist['last_step']={'token':token,'event_id':eid,'year':s.year,'result':result}
        c.assist['step_counter']=counter+1
        return result
    reason=blocker(c,s)
    if reason: return finish('paused',reason)
    if ev.get('status')=='done': return finish('done','本届赛事已结束。')
    pair=s.your_series()
    if pair:
        current,match=pair
        if current['id']!=eid: return finish('paused','另一项赛事有你的待打比赛，请先处理。')
        kind=decisive(ev,match)
        approval=(c.assist.get('tournament') or {}).get('approval')
        if kind and approval!=key(s,ev,match):
            moment(c,s,ev,match,kind)
            return finish('decision','进入决赛，请选择。' if kind=='final' else '进入生死战，请选择。')
        reason=c.gate_match(s,match['id']) or blocker(c,s)
        if reason: return finish('paused',reason)
        start=len(match.get('maps') or [])
        s.skip_your_series(match['id'])
        c.assist['tournament']={'event_id':eid,'choice':'running','approval':''}
        # Only map winners, not kills or an invented intermediate round path.
        return finish('played','本场模拟完成。',match={'id':match['id'],'team_a':match['team_a'],'team_b':match['team_b'],
            'best_of':match['best_of'],'start':start,'winners':[m.get('winner') for m in match.get('maps') or []]})
    s.next_stage()
    reason=blocker(c,s)
    return finish('paused' if reason else 'done' if ev.get('status')=='done' else 'progress',
                  reason or ('赛事已结束。' if ev.get('status')=='done' else '赛程已推进。'))
