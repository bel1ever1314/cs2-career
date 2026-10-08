"""Team map learning. Pure projections; changes only at accepted result/day boundaries."""
from copy import deepcopy
from datetime import date
import math

from .ability import playing_ability

VERSION = 2
MATCH_LEARNING_RATE = .8
UNDERDOG_LEARNING_SHARE = .35
PEER_EXPECTATION = .45
LOSS_BASE = .08
LOSS_SLOPE = .8
LOSS_CAP = .45
FOCUS_RECOVERY_RATE = .8


def code(value):
    return str(value).lower().removeprefix('de_')


def _clip(value, low=0.0, high=100.0):
    return max(low, min(high, value))


def _initial(team, name):
    name = code(name)
    strong = name in {code(m) for m in team.get('strong_maps', [])}
    weak = name in {code(m) for m in team.get('weak_maps', [])}
    return dict(strength=_clip(float(team.get('map_adaptation', 65)) + (25 if strong else -25 if weak else 0)),
                form=0.0, label='strong' if strong else 'weak' if weak else 'neutral',
                played=0, wins=0, recent=[], last_change=None)


def row(team, name):
    """Never migrate/write a team during a GET or an engine preview."""
    return (team.get('map_form') or {}).get('maps', {}).get(code(name)) or _initial(team, name)


def rating(team, name):
    value = row(team, name)
    return _clip(value['strength'] + value['form'])


def comfort(team, name):
    # Preserve legacy BP landmarks: 40 -> -1.1, 65 -> .05, 90 -> 1.2.
    return (rating(team, name) - 65.0) * .046 + .05


def reaction_factor(team, name):
    return 1.0 - .05 * _clip((rating(team, name) - 65.0) / 25.0, -1, 1)


def expected(team, opponent, name):
    def power(t):
        players = t.get('players') or []
        fire = sum(playing_ability(p) for p in players) / len(players) if players else 65
        return .80 * fire + .12 * float(t.get('command', 65)) + .04 * float(t.get('mentality', 70)) + .04 * rating(t, name)
    return _clip(1 / (1 + math.exp(-(power(team) - power(opponent)) / 16.0)), .1, .9)


def expectation(a, b, name):
    p = expected(a, b, name)
    return {a['name']: p, b['name']: 1 - p}


def _ensure(team, name):
    if 'map_form' not in team:
        from cs2career.arena import MAPS
        names = {code(m) for m in [*MAPS, *team.get('strong_maps', []), *team.get('weak_maps', []), name]}
        # Freeze all legacy defaults before projecting the changing labels.
        team['map_form'] = dict(version=VERSION, maps={m: _initial(team, m) for m in sorted(names)})
    maps = team['map_form']['maps']
    if name not in maps:
        maps[name] = _initial(team, name)
    team['map_form']['version'] = VERSION
    # Migration starts at the current saved level, never guesses old peaks or
    # refunds historic decay. A GET continues to use the pure row() fallback.
    for value in maps.values():
        value.setdefault('practice_ceiling', value['strength'])
    return maps[name]


def _labels(team, name):
    value = team['map_form']['maps'][name]
    score = rating(team, name)
    old = value['label']
    value['label'] = ('strong' if score >= (72 if old == 'strong' else 78) else
                      'weak' if score <= (53 if old == 'weak' else 47) else 'neutral')
    for field, label in [('strong_maps', 'strong'), ('weak_maps', 'weak')]:
        team[field] = sorted(m for m, r in team['map_form']['maps'].items() if r['label'] == label)


def _mark_active(value, day):
    # Older pending training may finish during migration. Never rewind an
    # already observed calendar; legacy saves begin tracking now, not in history.
    day = max(day, value.get('inactivity', {}).get('through', day))
    value['inactivity'] = dict(since=day, through=day,
                               strength=value['strength'], form=value['form'])


def _change(team, name, previous, reason, day):
    """Keep familiarity, recent form and their clipped total distinguishable."""
    value = row(team, name)
    before = _clip(previous['strength'] + previous['form'])
    after = rating(team, name)
    change = dict(team_id=team.get('id', ''), team=team['name'], map=name,
                  before=round(before, 2), after=round(after, 2),
                  delta=round(after - before, 2), reason=reason, date=day)
    for field in ('strength', 'form'):
        change[field + '_before'] = round(previous[field], 4)
        change[field + '_after'] = round(value[field], 4)
        change[field + '_delta'] = round(value[field] - previous[field], 4)
    return change


def advance_calendar(teams, old_day, new_day):
    """All clubs train routinely: maintain, never inflate or decay their maps.

    Only an explicitly selected focus can recover lost familiarity. Calendar
    jumps do not invent scrims, consume match RNG or modify player attributes.
    """
    old_stamp, new_stamp = date.fromisoformat(old_day), date.fromisoformat(new_day)
    if new_stamp <= old_stamp:
        return
    for team in teams:
        _ensure(team, 'dust2')
        for value in team['map_form']['maps'].values():
            if 'inactivity' not in value:
                _mark_active(value, old_day)
    settle_practice(teams, new_day)
    for team in teams:
        for name, value in team['map_form']['maps'].items():
            idle = value['inactivity']
            if new_day <= idle['through']:
                continue
            idle['through'] = new_day


def apply_result(a, b, box, day, *, practice=False):
    """Called with the authoritative mutable box in the same transaction as its append.

    The result owns its receipt, so retention follows existing match/report storage
    rather than an ever-growing second ledger. Existing import/session guards reject
    duplicate result files before they can create another box.
    """
    if 'map_form_changes' in box:
        return box['map_form_changes']
    if box.get('winner') not in (a['name'], b['name']):
        raise ValueError('地图结果缺少有效胜方。')
    name = code(box['map'])
    chances = box.get('map_expectation') or expectation(a, b, name)
    weight = 1 / 3 if practice else 1.0
    changes = []
    for team in (a, b):
        value = _ensure(team, name)
        previous = dict(strength=value['strength'], form=value['form'])
        won = box['winner'] == team['name']
        chance = _clip(float(chances[team['name']]), .1, .9)
        residual = int(won) - chance
        # Results reveal mastery: an upset loss costs a small bounded amount;
        # an underdog can still learn from losing to a clearly stronger side.
        # No extra random draws, player-stat changes or historical replay.
        learning = MATCH_LEARNING_RATE * (1 - value['strength'] / 100) * (1.5 - chance)
        if not won:
            learning = (learning * UNDERDOG_LEARNING_SHARE if chance < PEER_EXPECTATION else
                        -min(LOSS_CAP, LOSS_BASE + LOSS_SLOPE * (chance - PEER_EXPECTATION)) * value['strength'] / 100)
        value['strength'] = round(_clip(value['strength'] + weight * learning), 4)
        value['practice_ceiling'] = max(value['practice_ceiling'], value['strength'])
        value['form'] = round(_clip((1 - .15 * weight) * value['form'] + 4 * weight * residual, -10, 10), 4)
        value['played'] += 1
        value['wins'] += int(won)
        value['recent'] = (value['recent'] + [dict(date=day, won=won, practice=practice)])[-20:]
        _mark_active(value, day)
        _labels(team, name)
        change = _change(team, name, previous,
                         ('训练赛' if practice else '正式比赛') + ('获胜' if won else '失利'), day)
        value['last_change'] = deepcopy(change)
        changes.append(change)
    box['map_form_changes'] = changes
    return changes


def settle_map(season, match, index):
    if getattr(season, 'career', None):
        from cs2career.career.match_supplies import finish_map, series_key
        finish_map(season.career, match, series_key(season, match), index)
    teams = {t['name']: t for t in season.teams}
    box = match['maps'][index]
    return apply_result(teams[match['team_a']], teams[match['team_b']], box, season.date)


def schedule_practice(team, name, day):
    from cs2career.arena import MAPS
    name = code(name)
    if name not in MAPS:
        raise ValueError('请选择有效的训练地图。')
    if (team.get('map_practice') or {}).get('date') == day and team['map_practice'].get('settled'):
        raise ValueError('今天的专项训练已经完成。')
    team['map_practice'] = dict(map=name, date=day, settled=False)


def settle_practice(teams, new_day):
    """One selected training day, not a reward for every skipped day."""
    for team in teams:
        task = team.get('map_practice') or {}
        if not task or task.get('settled') or task['date'] >= new_day:
            continue
        name = task['map']
        value = _ensure(team, name)
        previous = dict(strength=value['strength'], form=value['form'])
        value['strength'] = round(min(value['practice_ceiling'],
                                     value['strength'] + FOCUS_RECOVERY_RATE * (1 - value['strength'] / 100)), 4)
        _mark_active(value, task['date'])
        _labels(team, name)
        task['settled'] = True
        value['last_change'] = _change(team, name, previous, '专项练图', task['date'])


def public(team, maps=None):
    if maps is None:
        from cs2career.arena import MAPS
        maps = MAPS
    out = []
    for name in maps:
        name = code(name)
        value = row(team, name)
        idle = value.get('inactivity', {})
        inactive_days = (date.fromisoformat(idle['through']) - date.fromisoformat(idle['since'])).days if idle else 0
        out.append(dict(map=name, rating=round(rating(team, name), 1),
                        strength=round(value['strength'], 1), form=round(value['form'], 1),
                        label=value['label'], played=value['played'], wins=value['wins'],
                        recent=deepcopy(value['recent']), last_change=deepcopy(value['last_change']),
                        inactive_days=inactive_days, automatic_training=True,
                        practice_ceiling=round(value.get('practice_ceiling', value['strength']), 1)))
    return out
