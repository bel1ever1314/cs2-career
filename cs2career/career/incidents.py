"""Career incident extension boundary, separate from tournament `events`.

Queue a frozen decision, then apply only validated, whitelisted effects when
the player chooses. Save the consumed decision with its effects in the normal
ApplicationState transaction. Pack removal never strands a pending choice.
"""
import copy
import hashlib
import re
from datetime import date, timedelta

from ..content import get_registry
from ..content.rules import validate_effects


def state(career):
    if not isinstance(getattr(career, 'incident_state', None), dict):
        career.incident_state = {}
    value = career.incident_state
    for key in ('seen', 'flags'):
        value.setdefault(key, {})
    return value


def decorate(beat):
    """Override built-in copy/labels, never its action IDs, odds or consequences."""
    result = copy.deepcopy(beat)
    for payload in get_registry().payloads('incidents'):
        for row in payload.get('overrides', []):
            if row['when'] != beat.get('when'):
                continue
            for key in ('title', 'text'):
                if key in row:
                    result[key] = row[key]
            for choice in result.get('choices', []):
                choice['label'] = row.get('labels', {}).get(choice['id'], choice['label'])
    return result


def pending(career):
    return any(row.get('kind') == 'incident' for row in career.story_queue)


def competition_status(career, day):
    pause = state(career).get('competition_pause', {})
    return {**pause, 'active': bool(pause.get('until', '') > day)}


def competition_paused(career, day):
    return bool(career and competition_status(career, day)['active'])


def emit(career, season, when, occurrence='', event_type='', context=None):
    """At most one outstanding incident, no gameplay RNG consumption.

    Stable date/occurrence rolls prevent re-opening menus to reroll a choice.
    max_per_career + cooldown are stored in schema-v2 optional fields.
    """
    if not career.exists or career.over() or season is None or pending(career):
        return
    team = career.my_team(season.teams)
    transfer_hook = when.startswith('transfer_')
    if not team and not transfer_hook:
        return
    extra = context or {}
    today = date.fromisoformat(season.date).toordinal()
    values = state(career)
    for payload in get_registry().payloads('incidents'):
        for row in payload.get('incidents', []):
            if row['when'] != when:
                continue
            key = payload['_pack_id'] + ':' + row['id']
            conditions = row.get('conditions', {})
            values_context = {'mode': career.mode, 'origin': career.origin, 'event_type': event_type, **extra}
            if any(values_context.get(k) != v for k, v in conditions.items() if k != 'flags'):
                continue
            if any(values['flags'].get(payload['_pack_id'] + ':' + k, False) != v
                   for k, v in conditions.get('flags', {}).items()):
                continue
            record = values['seen'].get(key, {})
            if record.get('count', 0) >= row.get('max_per_career', 1):
                continue
            if today - record.get('day', -100000) < row.get('cooldown_days', 30):
                continue
            # Include the career starting identity, not a global random stream.
            seed = f'{career.start_year}|{career.player_name}|{key}|{when}|{season.date}|{occurrence}'
            roll = int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], 'big') / 2**64
            if roll >= row.get('probability', 1):
                continue
            count = record.get('count', 0) + 1
            values['seen'][key] = {'count': count, 'day': today}
            def render(line):
                # Flat, explicit transfer tokens only; substituted text is not parsed again.
                tokens = {k: str(extra.get(k, '')) for k in ('player', 'old_team', 'new_team', 'transfer_role')}
                return re.sub(r'\{(player|old_team|new_team|transfer_role)\}', lambda m: tokens[m[1]], line) if transfer_hook else line
            choices = copy.deepcopy(row['choices'])
            for choice in choices:
                choice['label'] = render(choice['label'])
            career.story_queue.append({
                'id': f'incident:{key}:{count}', 'kind': 'incident', 'when': 'incident',
                'title': render(row['title']), 'text': render(row['text']),
                'choices': choices, 'pack_id': payload['_pack_id'],
                'team_id': (team or {}).get('id', ''), 'trigger': when, 'date': season.date,
            })
            return


def resolve(career, season, row, choice_id):
    """Validate the ENTIRE transaction and affordability before any mutation."""
    choice = next((c for c in row.get('choices', []) if c.get('id') == choice_id), None)
    if choice is None or season is None:
        raise ValueError('请选择有效事件选项，且需要已加载生涯。')
    if row.get('arc'):
        from . import arcs
        return arcs.resolve(career, season, row, choice_id)
    effects = choice.get('effects', [])
    validate_effects(effects)
    team = career.my_team(season.teams)
    if (team or {}).get('id', '') != row.get('team_id'):
        # Never charge a newly joined club for a former club's unresolved event.
        career.log.append(f"事件已失效（所属战队变更）：{row.get('title', '')}")
        return
    pocket_delta = sum(e['amount'] for e in effects if e['type'] == 'pocket_money')
    club_delta = sum(e['amount'] for e in effects if e['type'] == 'club_money')
    mentality_delta = sum(e['amount'] for e in effects if e['type'] == 'mentality')
    if not team and (club_delta or mentality_delta):
        raise ValueError('自由身状态没有俱乐部，请选择不影响俱乐部资金或心态的选项。')
    if career.money + pocket_delta < 0 or int((team or {}).get('money', 0)) + club_delta < 0:
        raise ValueError('资金不足，事件尚未结算；请选择其他选项。')
    pause = next((e for e in effects if e['type'] == 'competition_pause'), None)
    if pause and pause['amount']:
        for event in season.events:
            for match in event.get('matches', []):
                if not match.get('played') and team and team['name'] in (match.get('team_a'), match.get('team_b')) and (match.get('cs2_session') or match.get('maps')):
                    raise ValueError('这场系列赛已有实战或地图记录，请打完后再暂停参赛，或选择继续比赛。')
    points = sum(e['amount'] for e in effects if e['type'] == 'skill_points')
    flags = state(career)['flags']
    for effect in effects:
        if effect['type'] == 'flag':
            flags[row['pack_id'] + ':' + effect['key']] = effect['value']
    if mentality_delta:
        from ..engine.morale import shift_mentality
        shift_mentality(team, max(-20, min(20, mentality_delta)))
    for account, delta in (('pocket', pocket_delta), ('club', club_delta)):
        if not delta:
            continue
        if account == 'pocket':
            career.money += delta
            balance = career.money
        else:
            team['money'] = int(team.get('money', 0)) + delta
            balance = team['money']
        career._record_cashflow(season.date, account, 'incident', row['title'], delta, balance)
    notes = []
    if points:
        career.attr_points += points
        notes.append(f'技能点 +{points}（已到账）')
    if pause:
        until = (date.fromisoformat(season.date) + timedelta(days=pause['amount'])).isoformat()
        if pause['amount']:
            until = max(until, state(career).get('competition_pause', {}).get('until', ''))
        state(career)['competition_pause'] = dict(until=until, reason=row['title'])
        notes.append(f'暂停参赛至 {until}；期间的已排比赛将弃权，不生成虚假战绩。仍可推进日期，到期自动恢复。' if pause['amount'] else '已恢复参赛；错过的比赛不会重打。')
    if notes:
        career.story_queue.append(dict(id=row['id']+':effects', kind='story', when='incident_result',
                                       title='决定之后', text='\n'.join(notes)))
    career.log.append(f"{row['title']}：{choice['label']}" + ('；'+'；'.join(notes) if notes else ''))
