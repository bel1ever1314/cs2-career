"""A resumable season runner built from bounded, ordinary career commands.

The client requests bounded steps and can stop at any point. Decisions,
contracts, finals and outstanding CS2 results retain their normal gates.
One run is pinned to one calendar year. An explicit season-mode confirmation,
not another automatic step, authorizes rolling into the following year.
No future match results are consulted when choosing an event.
"""
from __future__ import annotations

from datetime import date

from ..league.awards import event_class
from ..world.ability import playing_ability

PRIORITY = {'major': 0, 'premier': 1, 't1': 2, 'qual': 3, 't2': 4, 'cct': 5}


def season_complete(s):
    return bool(s.events) and all(e.get('status') == 'done' for e in s.events)


def season_mode(c, s):
    """Read-only UI contract; opening this view never chooses or rolls a year."""
    started = any(e.get('status') != 'upcoming' or any(m.get('played') or m.get('maps')
                  or m.get('cs2_session') for m in e.get('matches', [])) for e in s.events)
    phase = 'end' if season_complete(s) else 'running' if started else 'start'
    value = c.assist.get('season_mode') or {}
    return {'year': s.year, 'phase': phase, 'can_choose': phase in ('start', 'end'),
            'choice_required': phase == 'end' or (phase == 'start' and value.get('year') != s.year),
            'selected': 'quick' if c.assist.get('quick_mode') else 'normal',
            'run_year': (c.assist.get('season_run') or {}).get('year')}


def configure_season(c, s, quick_mode, expected_year):
    """Select a season mode; callers persist this with the ordinary transaction.

    The expected calendar year protects a retried end-of-season request from
    rolling two years. HTTP callers also retain their existing revision/token
    checks. Changing ancillary assistance settings does not call this method.
    """
    if type(quick_mode) is not bool or type(expected_year) is not int:
        raise ValueError('请选择有效的赛季模式和年份。')
    if expected_year != s.year:
        raise ValueError('赛季已经变化，请刷新赛程后再选择。')
    current = season_mode(c, s)
    if not current['can_choose']:
        raise ValueError('只能在赛季开始或结束时切换模式。')
    if not c.exists or c.over():
        raise ValueError('请先创建或选择一段仍在进行的生涯。')
    if current['phase'] == 'end':
        from ..league.tournament_auto import blocker
        reason = blocker(c, s)
        if reason:
            raise ValueError(reason)
        # The old season's accrual/rollover uses its old mode. Apply the new
        # mode afterwards so banked quick-mode points are never erased merely
        # because the player chooses normal mode for the following season.
        s.roll_year()
    c.assist['quick_mode'] = quick_mode
    c.assist['season_mode'] = {'year': s.year, 'mode': 'quick' if quick_mode else 'normal'}
    c.assist['season_run'] = {'year': s.year, 'status': 'ready'}
    c.assist.pop('last_fast_step', None)
    return season_mode(c, s)


def event_level(event):
    return 'qual' if event.get('type') == 'qual' else event_class(event)


def event_start(event, fallback):
    return (event.get('dates') or [fallback])[0]


def _days(first, second):
    return (date.fromisoformat(second) - date.fromisoformat(first)).days


def context(c, s):
    """Calculate standings and current roster level once per invitation batch."""
    ranking = {r['id']: r['rank'] for r in s.vrs.table(s.teams, s.date)}
    strength = sorted(s.teams, key=lambda t: (
        -sum(playing_ability(p) for p in t.get('players', [])) / max(1, len(t.get('players', []))), t['id']))
    ability_rank = next((i for i, t in enumerate(strength, 1) if t['id'] == c.team_id), 999)
    rank = ranking.get(c.team_id, 999)
    return {'rank': rank, 'level_rank': min(rank, ability_rank), 'ranking': ranking}


def invitation_decision(c, s, event, ctx=None):
    """Return accept/decline and a player-readable explanation; no mutation."""
    ctx = ctx or context(c, s)
    level = event_level(event)
    start = event_start(event, s.date)
    finish = (event.get('dates') or [start])[-1]
    committed = [e for e in s.events if e['id'] in c.registered and
                 e['id'] != event['id'] and e.get('status') != 'done']
    for other in committed:
        a = event_start(other, s.date)
        b = (other.get('dates') or [a])[-1]
        if start <= b and a <= finish:
            return 'decline', f"与已接受的 {other['name']} 赛程重叠，保留原安排。"
    if level in ('major', 'premier', 't1'):
        return 'accept', '符合直邀或出线条件，优先参加高水平赛事。'
    if level == 'qual':
        destination = next((e for e in s.events if e['id'] == event.get('feeds')), None)
        if destination and (destination['id'] in c.registered or
                c.team_id in (s.qualified.get(destination['id']) or [])):
            return 'decline', '已经获得目标正赛席位，无需重复参加预选赛。'
        return 'accept', '保留通往更高等级正赛的晋级机会。'

    higher = [e for e in committed if PRIORITY.get(event_level(e), 9) < PRIORITY.get(level, 9)
              and abs(_days(start, event_start(e, s.date))) <= 21]
    if higher:
        return 'decline', f"近期已有 {higher[0]['name']}，为主要赛事留出准备时间。"
    # A strong roster is not an invitation to a better event. In particular,
    # joining a developing club must not reject its entire available calendar.
    # Ranking saturation only justifies rest when there is an actual alternative.
    alternatives = [e for e in committed
                    if abs(_days(start, event_start(e, s.date))) <= 45]
    if alternatives and level in ('cct', 't2') and not s.vrs.can_improve(c.team_id, float(event.get('vrs_weight') or 0), start):
        return 'decline', '本赛事的最高单场积分仍不足以替换近半年最佳十场，保留休整时间。'

    if level == 'cct':
        # Developing teams need a route into the ranking, but one suitable CCT
        # in 45 days is enough for fast mode. Past manual entries also count.
        for other in s.events:
            if other['id'] == event['id'] or event_level(other) != 'cct':
                continue
            attended = other['id'] in c.registered
            if not attended:
                team = c.my_team(s.teams)
                attended = bool(team and team['name'] in (other.get('field') or []))
            if attended and abs(_days(event_start(other, s.date), start)) < 45:
                return 'decline', '45 天内已有一项 CCT，减少重复低级别赛事。'
        return 'accept', '发展中队伍选择一项适合的 CCT，积累有效胜场和经验。'
    return 'accept', '赛事层级与当前队伍匹配，可以增加有效比赛经历。'


def next_action(c, s):
    from ..league.tournament_auto import blocker
    reason = blocker(c, s)
    if reason:
        return {'action': 'paused', 'msg': reason}
    if not c.exists:
        return {'action': 'paused', 'msg': '请先创建生涯。'}
    pair = s.your_series()
    if pair:
        event, match = pair
        return {'action': 'tournament', 'event_id': event['id'], 'match_id': match['id']}
    return {'action': 'advance', 'msg': '推进到下一阶段，等待适合本队的赛事。'}


def step(c, s, token, expected=None, *, until=None, max_maps=None):
    """API command: same token returns same receipt, never a second simulation."""
    from ..league.tournament_auto import step as tournament_step, blocker
    if not isinstance(token, str) or not 8 <= len(token) <= 100:
        raise ValueError('缺少有效的快速模拟请求编号。')
    prior = c.assist.get('last_fast_step') or {}
    if prior.get('token') == token:
        return prior['result']
    counter = int(c.assist.get('step_counter') or 0)
    if expected is not None and expected != counter:
        raise ValueError('模拟进度已变化，请刷新后继续。')

    def finish(result, counted=False):
        if not counted:
            c.assist['step_counter'] = counter + 1
        c.assist['last_fast_step'] = {'token': token, 'result': result}
        return result

    if not c.assist.get('quick_mode'):
        return finish({'status': 'paused', 'msg': '快速模式已关闭。'})
    run = c.assist.setdefault('season_run', {'year': s.year, 'status': 'running'})
    if run['year'] != s.year or run.get('status') == 'done':
        return finish({'status': 'season_done', 'season_year': run['year'], 'year': s.year,
            'date': s.date, 'msg': '本次整季模拟已经结束，请在赛季页面选择下一赛季模式。'})
    from .story_timing import window
    current_break = window(c, s)
    if current_break and c.assist.get('quick_break_ack') != current_break['key']:
        return finish({'status': 'paused', 'break_key': current_break['key'],
            'msg': 'Major 休赛期到了：处理剧情、分配属性点和调整队伍后，可以继续快速模拟。'})
    action = next_action(c, s)
    if action['action'] == 'paused':
        return finish({'status': 'paused', 'msg': action['msg']})
    if season_complete(s):
        run['status'] = 'done'
        return finish({'status': 'season_done', 'season_year': run['year'], 'year': s.year,
                       'date': s.date, 'msg': '本赛季全部赛事已完成。你可以回看赛果，再选择下一赛季模式。'})
    run['status'] = 'running'
    c.dispatch_invites(s)
    if action['action'] == 'tournament':
        result = tournament_step(c, s, action['event_id'], token, counter, until=until,
                                **({'max_maps': max_maps} if max_maps is not None else {}))
        return finish(result, counted=True)
    before = (s.year, s.date, tuple((e['id'], e.get('status'), len(e.get('matches') or [])) for e in s.events))
    message = s.next_stage(stop_at_season_end=True, **({'until': until} if until is not None else {}))
    reason = blocker(c, s)
    current_break = window(c, s)
    if current_break and c.assist.get('quick_break_ack') != current_break['key']:
        return finish({'status': 'paused', 'break_key': current_break['key'],
            'msg': reason or 'Major 休赛期到了：现在可以处理剧情和分配积累的属性点。',
            'date': s.date, 'year': s.year})
    if not reason and season_complete(s):
        run['status'] = 'done'
        return finish({'status': 'season_done', 'season_year': run['year'], 'year': s.year,
                       'date': s.date, 'msg': '本赛季全部赛事已完成。你可以回看赛果，再选择下一赛季模式。'})
    after = (s.year, s.date, tuple((e['id'], e.get('status'), len(e.get('matches') or [])) for e in s.events))
    # A business-rule refusal must not spin the browser forever.
    paused = bool(reason) or (before == after and not s.your_series())
    return finish({'status': 'paused' if paused else 'progress', 'msg': reason or message,
                   'date': s.date, 'year': s.year})
