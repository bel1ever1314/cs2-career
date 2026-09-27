"""Opt-in player conveniences. All actions reuse the manual business commands.

Stored in Career.assist (optional schema-v2 field). Never accept contracts or
story choices, never increase point budgets, never change match odds.
"""
from __future__ import annotations

from ..world.ability import ALL_AXES, AXIS_LABEL
from ..league.awards import event_class

LEVELS = ('major', 'premier', 't1', 't2', 'cct', 'qual')


def configure(c, s, body):
    rules = body.get('invites', c.assist.get('invites') or {})
    points = body.get('points', c.assist.get('points') or 'off')
    quick_mode = body.get('quick_mode', bool(c.assist.get('quick_mode')))
    if type(quick_mode) is not bool:
        raise ValueError('快速模式开关必须为是或否。')
    if not isinstance(rules, dict) or any(k not in LEVELS or v not in ('manual','accept','decline') for k,v in rules.items()):
        raise ValueError('邀请规则只支持各级赛事的手动、自动接受、自动拒绝。')
    if points not in ('off','balanced',*ALL_AXES):
        raise ValueError('未知自动加点方向。')
    if quick_mode != bool(c.assist.get('quick_mode')):
        from .fast_mode import configure_season
        configure_season(c, s, quick_mode, s.year)
    c.assist.update(invites=dict(rules), points=points, notice='')
    return '辅助设置已保存，现有待处理邀请和可用属性点会按新规则处理；已接受/拒绝的邀请不追改。'


def process_invites(c, s):
    rules = getattr(c, 'assist', {}).get('invites') or {}
    quick_mode = bool(getattr(c, 'assist', {}).get('quick_mode'))
    if (not rules and not quick_mode) or not c.exists or c.over() or c.unsigned:
        return False
    changed = False
    events = {e['id']:e for e in s.events}
    rows = [row for row in c.inbox if row.get('kind') == 'invite' and row.get('status') == 'open'
            and row.get('team_id') == c.team_id
            and events.get(row.get('event_id'), {}).get('status') == 'upcoming']
    if not rows:
        return False
    from .fast_mode import context, invitation_decision, event_level, event_start, PRIORITY
    ctx = context(c, s) if quick_mode else None
    if quick_mode:
        rows.sort(key=lambda row: (PRIORITY.get(event_level(events.get(row.get('event_id'), {})), 9),
                                  event_start(events.get(row.get('event_id'), {}), s.date)))
    for row in rows:
        if row.get('kind') != 'invite' or row.get('status') != 'open' or row.get('team_id') != c.team_id:
            continue
        ev = events.get(row.get('event_id'))
        if not ev or ev.get('status') != 'upcoming':
            continue
        level = 'qual' if ev.get('type')=='qual' else event_class(ev)
        rule = rules.get(level, 'manual')
        reason = ''
        if quick_mode and rule == 'manual':
            rule, reason = invitation_decision(c, s, ev, ctx)
        if rule not in ('accept','decline'):
            continue
        action = c.accept_invite if rule == 'accept' else c.decline_invite
        message = action(s, row['id'], persist=False)
        if row.get('status') in ('accepted','declined'):
            row['auto_action'] = rule
            if reason:
                row['auto_reason'] = reason
            row.pop('auto_blocked',None)
            changed = True
        elif row.get('auto_blocked') != message:
            row['auto_blocked'] = message
            changed = True
    return changed


def process_points(c, s):
    mode = getattr(c,'assist',{}).get('points') or 'off'
    if mode == 'off' or not c.exists or c.over() or c.unsigned:
        return
    if c.assist.get('quick_mode'):
        from .story_timing import window
        if not window(c, s):
            return  # Accumulate points until the post-Major development window.
    you = c.my_player(s.teams)
    if not you or mode not in ('balanced',*ALL_AXES):
        return
    axes = list(ALL_AXES) if mode == 'balanced' else [mode]
    def value(axis):
        stats = you.get('stats') or {}
        return int(round(float(stats.get(axis) or (you.get('command') or 50 if axis=='command' else 70))))
    # A point is spent by the same capped method as '+'. Batch disk writes at
    # ApplicationState.persist, instead of saving a whole season per point.
    for _ in range(len(ALL_AXES)*100):
        available = [a for a in axes if value(a)<100]
        if not available:
            label = '全部维度' if mode=='balanced' else AXIS_LABEL[mode]
            c.assist.update(points='off', notice=f'{label}已加满，自动加点已暂停。剩余 {c.attr_points} 点保留，请选择其他方向。')
            c._push_plot({'kind':'story','title':'训练计划完成','text':c.assist['notice']},
                         f'auto-points:{s.date}:{mode}:{c.attr_points}')
            break
        if c.attr_points<1:
            break
        axis = min(available,key=value) if mode=='balanced' else available[0]
        before = c.attr_points
        c.spend_point(s, axis, persist=False)
        if c.attr_points>=before:
            break
