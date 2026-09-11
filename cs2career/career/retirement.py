"""Voluntary retirement: authored copy plus evidenced career longevity.

No large match deepcopy; count retained official maps by stable player ID.
Titles determine achievement, not whether somebody is an ageing veteran.
Missing history is not invented. Forced storyline endings remain in arcs.
"""
from datetime import date
from functools import lru_cache
import json
from ..paths import data_file


@lru_cache(maxsize=1)
def config():
    raw=json.loads(data_file('career_retirement.json').read_text('utf-8'))
    limits={'legend_min_majors':100,'legend_min_titles':1000,'legend_min_top20':100,
            'veteran_min_age':100,'veteran_min_years':100,'veteran_min_active_seasons':100,
            'veteran_min_maps':100000}
    if raw.get('schema_version')!=1:raise ValueError('退役文案schema_version须为1')
    rules=raw.get('rules',{})
    for key,maximum in limits.items():
        if type(rules.get(key)) is not int or not 1<=rules[key]<=maximum:
            raise ValueError('退役判定须为范围内的正整数：'+key)
    for key in ('legend','veteran','early_success','plain'):
        row=raw.get('endings',{}).get(key,{})
        for field,maximum in (('title',160),('text',5000)):
            if not isinstance(row.get(field),str) or not row[field].strip() or len(row[field])>maximum:
                raise ValueError('退役文案缺失或过长：'+key+'.'+field)
    return raw


def career_context(c,s):
    player=c.my_player(s.teams) or c.you_card or {}
    pid=player.get('player_id');days=[];seen=set()
    for ev in [*s.history,*s.events]:
        for match in ev.get('matches',[]):
            if not match.get('played') or match.get('forfeit') or 'BYE' in (match.get('team_a'),match.get('team_b')):continue
            day=match.get('date') or ev.get('date') or (ev.get('dates') or [''])[0]
            if not day or day[:4]<str(c.start_year) or day>s.date:continue
            try:stamp=date.fromisoformat(day)
            except ValueError:continue
            for index,mp in enumerate(match.get('maps',[])):
                rows=[p for group in (mp.get('players') or {}).values() for p in group]
                matches=[p for p in rows if pid and p.get('player_id')==pid]
                # Legacy name-only maps may contain aliases; count only an
                # unambiguous name if the saved map has no conflicting ID.
                if not matches:
                    named=[p for p in rows if p.get('name')==c.player_name]
                    matches=named if len(named)==1 and not named[0].get('player_id') else []
                if len(matches)!=1:continue
                key=(day[:4],ev.get('id'),match.get('id'),index)
                if key not in seen:seen.add(key);days.append(stamp)
    today=date.fromisoformat(s.date)
    first=min(days) if days else today
    years=today.year-first.year-((today.month,today.day)<(first.month,first.day))
    return dict(age=int(player.get('age') or 0),years=max(0,years),active_seasons=len({d.year for d in days}),maps=len(days))


def choose(honours,context=None):
    cfg=config();r=cfg['rules'];counts=(honours or {}).get('counts') or {};ctx=context or {}
    if all(int(counts.get(key) or 0)>=r['legend_min_'+key] for key in ('majors','titles','top20')):
        key='legend'
    elif all(int(ctx.get(key) or 0)>=r['veteran_min_'+key] for key in ('age','years','active_seasons','maps')):
        key='veteran'
    elif any(int(counts.get(key) or 0)>0 for key in ('titles','premiers','top20','mvp','evp')):
        key='early_success'
    else:key='plain'
    return {'id':key,**cfg['endings'][key]}
