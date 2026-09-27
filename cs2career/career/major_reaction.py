"""A Major reaction compares a frozen ability expectation with played results.

No VRS values, future games or post-event roster strength enter the comparison.
The six exit keys match data/major_exit_stories.json; a two-stage Major never
produces a fictitious third Swiss stage. Missing old records remain ungraded.
"""
from math import isfinite

from ..world.ability import playing_ability


EXIT_ORDER = {'stage1': 1, 'stage2': 2, 'stage3': 3,
              'quarter_final': 4, 'semi_final': 5, 'final': 6, 'champion': 7}
LABELS = {'stage1': '第一阶段', 'stage2': '第二阶段', 'stage3': '第三阶段',
          'quarter_final': '八强', 'semi_final': '四强', 'final': '决赛', 'champion': '冠军'}
LABELS_EN = {'stage1': 'Stage 1', 'stage2': 'Stage 2', 'stage3': 'Stage 3',
             'quarter_final': 'the quarterfinals', 'semi_final': 'the semifinals',
             'final': 'the final', 'champion': 'the title'}


def stage_count(ev):
    count = ev.get('major_stage_count')
    if type(count) is int and 1 <= count <= 3:
        return count
    size = ev.get('size') or len(ev.get('field', []))
    if size >= 16:
        return max(1, min(3, (size - 8) // 8))
    # Small synthetic fixtures / old records can still contain explicit stage
    # metadata. Without either, use the format's documented default.
    stages = [(m.get('meta') or {}).get('major_stage') for m in ev.get('matches', [])]
    return max([x for x in stages if type(x) is int and 1 <= x <= 3] or [3])


def expected_exit(rank, stages):
    if rank <= 1:
        return 'champion'
    if rank <= 2:
        return 'final'
    if rank <= 4:
        return 'semi_final'
    if rank <= 8:
        return 'quarter_final'
    return 'stage' + str(max(1, stages - ((rank - 9) // 8)))


def freeze(ev, teams):
    """Called after the field is selected, before the first tournament match."""
    if ev.get('type') != 'major' or ev.get('major_expectation', {}).get('schema_version') == 1:
        return
    field = set(ev.get('field', []))
    rows = []
    for team in teams:
        if team.get('name') not in field or not team.get('id'):
            continue
        players = team.get('players', [])
        if len(players) != 5:
            continue
        ability = [playing_ability(p) for p in players]
        if not all(isfinite(value) for value in ability):
            continue
        rows.append((team, sum(ability) / len(ability)))
    stages = stage_count(ev)
    # Partial fields cannot be ranked as if missing teams did not exist.
    complete = len(rows) == len(field) and bool(field)
    ordered = sorted(rows, key=lambda row: (-row[1], str(row[0]['id'])))
    snapshot = {}
    for rank, (team, ability) in enumerate(ordered, 1):
        snapshot[team['id']] = dict(team=team['name'], rank=rank if complete else None,
                                   ability=round(ability, 4),
                                   expected=expected_exit(rank, stages) if complete else None,
                                   roster=[p.get('player_id') for p in team['players']])
    ev['major_expectation'] = dict(schema_version=1, source='pre_event_playing_ability',
                                   stages=stages, field_count=len(field), complete=complete, teams=snapshot)
    if complete:
        # Preserve the older lightweight rank field used by the champion column.
        ev['arc_expectations'] = {tid: row['rank'] for tid, row in snapshot.items()}


def _stage(match, stages):
    known = {'QF': 'quarter_final', 'SF': 'semi_final', 'GF': 'final'}
    if match.get('stage') in known:
        return known[match['stage']]
    stage = (match.get('meta') or {}).get('major_stage')
    if type(stage) is int and 1 <= stage <= stages:
        return 'stage' + str(stage)
    # Older generic Swiss Majors had one Swiss stage, not three invented ones.
    if stages == 1 and str(match.get('stage', '')).startswith('SW'):
        return 'stage1'
    return None


def assess(ev, team, records, event_key):
    """Return a grounded exit and comparison, or None if identity is incomplete.

    Series IDs must join the personally played ledger to saved match records.
    A transfer to a finalist club does not grant participation in its final.
    """
    if ev.get('type') != 'major' or not team:
        return None
    own = {row.get('key') for row in records if row.get('event') == event_key
           and row.get('team_id') == team.get('id')}
    name = team['name']
    played = [m for m in ev.get('matches', []) if m.get('id')
              and event_key + ':' + m['id'] in own and m.get('played') and not m.get('forfeit')
              and name in (m.get('team_a'), m.get('team_b'))
              and m.get('team_b') != 'BYE' and m.get('team_a') != 'BYE'
              and m.get('winner') in (m.get('team_a'), m.get('team_b'))]
    if not played:
        return None
    snapshot = ev.get('major_expectation', {})
    stages = snapshot.get('stages') or stage_count(ev)
    # Tournament match lists are append-only. A deeper phase beats a later
    # date string; within one phase the final saved match is authoritative.
    recognised = [(m, _stage(m, stages)) for m in played]
    recognised = [(m, phase) for m, phase in recognised if phase]
    if not recognised:
        return None
    final, exit_key = max(enumerate(recognised), key=lambda item: (EXIT_ORDER[item[1][1]], item[0]))[1]
    if final.get('stage') == 'GF' and final['winner'] == name and ev.get('champion') == name:
        exit_key = 'champion'
    elif final['winner'] == name:
        # A last recorded win followed by unrecorded games is not an exit.
        return None
    frozen = snapshot.get('teams', {}).get(team['id'], {})
    rank = frozen.get('rank')
    expected = frozen.get('expected')
    source = snapshot.get('source')
    if not snapshot and type(ev.get('arc_expectations', {}).get(team['id'])) is int:
        rank = ev['arc_expectations'][team['id']]
        expected = expected_exit(rank, stages)
        source = 'legacy_pre_event_ability_rank'
    if expected not in EXIT_ORDER:
        expected = None
    wins = sum(m['winner'] == name for m, phase in recognised if phase == exit_key)
    if exit_key == 'champion':
        comparison = 'above'  # Every title gets the excited report.
    elif expected is None:
        comparison = None
    else:
        difference = EXIT_ORDER[exit_key] - EXIT_ORDER[expected]
        comparison = 'above' if difference > 0 else 'below' if difference < 0 else 'expected'
        # Bottom four of an expected Swiss exit band have a zero-win baseline.
        # Two actually recorded wins can exceed that baseline without pretending
        # the team qualified. Ties/one win do not invent a stronger achievement.
        if comparison == 'expected' and exit_key.startswith('stage'):
            lowest_four = 8 + (stages - int(exit_key[-1])) * 8 + 4
            if rank > lowest_four and wins >= 2:
                comparison = 'above'
    return dict(exit=exit_key, comparison=comparison, mood=('激动' if comparison == 'above' else
                '失望' if comparison == 'below' else '预料之中' if comparison else None),
                rank=rank, expected=expected, expected_label=LABELS.get(expected, '未保存赛前预期'),
                expected_en=LABELS_EN.get(expected, 'an unrecorded pre-event expectation'),
                placement=LABELS[exit_key], placement_en=LABELS_EN[exit_key],
                match_id=final['id'], opponent=final['team_b'] if final['team_a'] == name else final['team_a'],
                final_score=f"{final['team_a']} {final.get('series') or '比分未记录'} {final['team_b']}",
                stage_wins=wins, source=source)
