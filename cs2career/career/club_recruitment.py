"""Player influence on club recruitment, separate from ownership and transfers.

Read-only quotes; one named outgoing player per approval. The HTTP transaction
owns discussion outcomes, funds, roster changes and request receipts together.
"""
from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json

from .transfers import identity, outgoing, locked

DISCUSSION_COOLDOWN_DAYS = 14
RECENT_DAYS = 30
RECENT_MAPS = 20


def _clip(value, low, high):
    return max(low, min(high, value))


def _ability(player):
    return float(player.get('long_term_ability', player.get('ability', 65)))


def _stint(career):
    from ..world.eras import ERA_META
    moves = career.personal_transfers.get('moves', [])
    joined = next((r['date'] for r in reversed(moves) if r.get('new_team_id') == career.team_id), None)
    joined = joined or ERA_META.get(str(career.start_year), {}).get('start', f'{career.start_year}-01-08')
    return f'{career.team_id}|{len(moves)}|{joined}', joined


def _state(career):
    saved = career.personal_transfers.get('recruitment') or {}
    return saved if saved.get('stint') == _stint(career)[0] else {}


def _roster(team):
    return sorted(identity(p) for p in team['players'])


def permission(career, season):
    team = career.my_team(season.teams)
    grant = _state(career).get('grant') or {}
    if (not team or career.unsigned or career.over() or grant.get('team_id') != team['id']
            or grant.get('roster') != _roster(team)):
        return None
    return deepcopy(grant)


def authorize(career, season, replace_id):
    if not career.personal_transfers.get('player_only'):
        return
    grant = permission(career, season)
    if not grant or grant['replace_id'] != replace_id:
        raise ValueError('请先与俱乐部商量，并获得替换这名队友的批准。')


def consume(career, season, replace_id):
    """Only after an actual successful signing; failed talks retain approval."""
    if career.personal_transfers.get('player_only'):
        saved = _state(career)
        grant = saved.get('grant') or {}
        if grant.get('replace_id') == replace_id:
            saved['grant'] = None
            saved['used_date'] = season.date


def recent_performance(career, season, team):
    from ..presentation import events, aggregate, measured
    cutoff = (date.fromisoformat(season.date) - timedelta(days=RECENT_DAYS)).isoformat()
    players = {identity(p): p for p in team['players']}
    names = {}
    for t in season.teams:
        for p in t['players']: names.setdefault(p['name'], set()).add(identity(p))
    rows = {pid: [] for pid in players}
    for event in events(season):
        for match in event.get('matches', []):
            stamp = match.get('date') or ''
            if not cutoff <= stamp <= season.date: continue
            if team['name'] not in (match.get('team_a'), match.get('team_b')): continue
            for index, mp in enumerate(match.get('maps', [])):
                if mp.get('winner') not in (match.get('team_a'), match.get('team_b')): continue
                rounds = mp.get('rounds', 0)
                for line in (mp.get('players') or {}).get(team['name'], []):
                    pid = line.get('player_id')
                    if not pid:
                        ids = names.get(line.get('name'), set())
                        pid = next(iter(ids)) if len(ids) == 1 else None
                    if pid in rows and measured(line, rounds):
                        rows[pid].append((stamp, str(event['id']), str(match.get('id', '')), index, line, rounds))
    result = {}
    for pid, maps in rows.items():
        maps.sort(key=lambda r: r[:4], reverse=True)
        sample = aggregate([(r[4], r[5]) for r in maps[:RECENT_MAPS]])
        result[pid] = dict(maps=sample['maps'], rating=sample['rating'])
    return result


def context(career, season):
    required = bool(career.personal_transfers.get('player_only'))
    team = career.my_team(season.teams)
    if not required or not team or career.unsigned or career.over():
        return dict(required=required, available=False, candidates=[], grant=None)
    stint, joined = _stint(career)
    tenure = max(0, (date.fromisoformat(season.date) - date.fromisoformat(joined)).days)
    saved = _state(career)
    grant = permission(career, season)
    blocked = ('赛事进行中，结束后再与俱乐部商量。' if locked(season, team) else
               '先决定当前的加盟机会，再讨论阵容调整。' if career.personal_transfers.get('pending') else
               '本次换人已获批准，请先完成这次引援。' if grant else
               '下次可商量日期：' + saved['next_date'] if saved.get('next_date', '') > season.date else '')
    you = next((p for p in team['players'] if p.get('you') or p['name'] == career.player_name), {})
    own = _ability(you)
    performance = recent_performance(career, season, team)
    rows = []
    for target in team['players']:
        if target.get('you') or target['name'] == career.player_name: continue
        pid = identity(target)
        sample = performance[pid]
        target_ability = _ability(target)
        tenure_bonus = .30 * min(tenure / 365, 1)
        influence = _clip((own - 65) * .012, -.12, .24)
        teammate = _clip((own - target_ability) * .006, -.15, .15) - _clip((target_ability - 75) * .008, -.12, .18)
        form = (_clip((1.05 - sample['rating']) * .7, -.25, .18) * min(sample['maps'] / 5, 1)
                if sample['rating'] is not None else 0)
        chance = round(_clip(.35 + tenure_bonus + influence + teammate + form, .05, .90), 4)
        row = dict(replace_id=pid, name=target['name'], ability=round(target_ability, 1),
                   recent_maps=sample['maps'], recent_rating=sample['rating'], chance=chance,
                   tenure_bonus=tenure_bonus, ability_bonus=influence, teammate_modifier=teammate, form_modifier=form)
        fingerprint = json.dumps([stint, season.date, _roster(team), row], sort_keys=True, ensure_ascii=False)
        row['quote_id'] = hashlib.sha256(fingerprint.encode()).hexdigest()[:24]
        rows.append(row)
    return dict(required=True, available=not blocked, reason=blocked, candidates=rows, grant=grant,
                tenure_days=tenure, ability=round(own, 1), next_date=saved.get('next_date', ''),
                cooldown_days=DISCUSSION_COOLDOWN_DAYS, last_attempt=deepcopy(saved.get('last_attempt')))


def discuss(career, season, replace_id, quote_id):
    data = context(career, season)
    if not data['required']: raise ValueError('你已有俱乐部引援权，无需申请换人机会。')
    if not data['available']: raise ValueError(data.get('reason') or '当前不能与俱乐部商量。')
    team = career.my_team(season.teams)
    target = outgoing(career, team, replace_id)
    row = next((r for r in data['candidates'] if r['replace_id'] == identity(target)), None)
    if not row or not replace_id or quote_id != row['quote_id']:
        raise ValueError('商量条件已变化，请刷新后重新确认。')
    from .player_transfers import draw
    # Same-day reloads/menu choices do not roll another outcome or use match RNG.
    roll = draw(career, f'club-recruitment|{_stint(career)[0]}|{season.date}', 10000)
    approved = roll <= round(row['chance'] * 10000)
    attempt = dict(date=season.date, replace_id=replace_id, name=target['name'],
                   chance=row['chance'], approved=approved)
    next_date = (date.fromisoformat(season.date) + timedelta(days=DISCUSSION_COOLDOWN_DAYS)).isoformat()
    grant = dict(team_id=team['id'], replace_id=replace_id, name=target['name'],
                 roster=_roster(team), date=season.date) if approved else None
    career.personal_transfers['recruitment'] = dict(stint=_stint(career)[0], next_date=next_date,
                                                   grant=grant, last_attempt=attempt)
    message = (f'俱乐部同意调整 {target["name"]} 的位置，你获得一次换人机会。签约成功后使用。' if approved else
               f'俱乐部暂时希望保留 {target["name"]}。可以在 {next_date} 再谈。')
    career.log.append(message)
    career.save()
    return dict(reason=message, recruitment=attempt)
