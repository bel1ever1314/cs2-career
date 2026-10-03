"""Club cabinet projection: saved titles and pre-career organisation history.

This is not an award ledger. Reading a cabinet does not import real tournaments
into the simulation, settle money, grant attributes or credit a new recruit
with the employer's previous trophies.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json

from cs2career.paths import data_file


@lru_cache(maxsize=1)
def _catalog():
    return json.loads(data_file('club_titles.json').read_text(encoding='utf-8'))


def _records(season):
    """Keep frozen map identities available without deep-copying all matches."""
    from cs2career.league.awards import event_class
    yield from getattr(season, 'history', [])
    for event in season.events:
        if event.get('status') != 'done':
            continue
        dates = event.get('dates') or []
        stamp = dates[-1] if dates else max((m.get('date', '') for m in event.get('matches', [])), default='')
        yield dict(event, date=stamp, year=int(stamp[:4]) if stamp else season.year,
                   short=event.get('short') or event.get('name', ''),
                   **{'class': event_class(event)})


def _human_id(state):
    player = state.career.my_player(state.season.teams) or state.career.you_card or {}
    return player.get('player_id') or state.arena.career_player_id(state) or ''


def _earned(state, record, human_id):
    if not human_id:
        return False
    frozen_ids = record.get('champion_roster_ids')
    if frozen_ids is not None:
        return human_id in frozen_ids
    from tools.career3d_feedback import _participation
    who = _participation(record, human_id)
    if who:
        return who['team'] == record.get('champion')
    # Old records retain the frozen winning names even when map rows were
    # pruned. Only a unique stable identity can claim that legacy name.
    name = state.career.player_name
    if not name or name not in (record.get('champion_roster') or []):
        return False
    identities = {p.get('player_id') for team in state.season.teams
                  for p in team.get('players', []) if p.get('name') == name}
    for match in record.get('matches') or []:
        for saved in match.get('maps') or []:
            for rows in (saved.get('players') or {}).values():
                identities.update(p.get('player_id') for p in rows if p.get('name') == name)
    return identities == {human_id}


def _row(record, earned):
    stamp = record['date']
    return dict(id=f"saved:{stamp[:4]}:{record.get('id') or record['name']}",
                event_id=f"{stamp[:4]}:{record.get('id', '')}",
                event=record['name'], short=record.get('short') or record['name'],
                date=stamp, year=int(stamp[:4]), team=record['champion'],
                **{'class': record.get('class') or record.get('type') or 't1'},
                source='saved_championship', historical=False, player_earned=earned,
                roster=list(record.get('champion_roster') or []), source_url='')


def trophy_context(state):
    c, s = state.career, state.season
    club = c.my_team(s.teams) or {}
    name = club.get('name', '')
    start_year = int(getattr(c, 'start_year', 0) or getattr(c, 'year', 0) or s.year)
    # Real-world results stop at the opening season, not today's save date:
    # a 2024 career that reaches 2026 must not import real 2025 winners.
    cutoff = min(f'{start_year}-01-01', s.date)
    catalog = _catalog()
    historical = [dict(deepcopy(row), id='historical:' + row['id'],
        year=int(row['date'][:4]), event_id='', source='club_history', historical=True,
        player_earned=False, roster=[], source_url=catalog['sources'][row['source_id']])
        for row in catalog['titles'] if name and row['team'] == name and row['date'] < cutoff]
    rows, personal, seen = [], [], set()
    human_id = _human_id(state)
    for record in _records(s):
        stamp = record.get('date', '')
        if (not stamp or stamp > s.date or not record.get('champion')
                or record.get('type') == 'qual' or record.get('class') == 'qual'):
            continue
        key = (stamp[:4], record.get('id') or record.get('name'), record['champion'])
        if key in seen:
            continue
        seen.add(key)
        earned = _earned(state, record, human_id)
        if earned:
            personal.append(_row(record, True))
        if name and record['champion'] == name:
            rows.append(_row(record, earned))
    # A save containing an explicitly imported historical result owns that
    # event; a seed must not place a second trophy for the same edition.
    editions = {(row['event'].casefold(), row['year']) for row in rows}
    historical = [row for row in historical if (row['event'].casefold(), row['year']) not in editions]
    rows += historical
    rows.sort(key=lambda row: (row['date'], row['id']), reverse=True)
    personal.sort(key=lambda row: (row['date'], row['id']), reverse=True)
    return dict(team_id=club.get('id', ''), team=name, title=name + ' · 冠军陈列' if name else '冠军陈列',
        rows=rows, personal_rows=personal, total=len(rows), historical_total=len(historical),
        saved_total=len(rows)-len(historical), player_total=len(personal),
        current_club_player_total=sum(row['player_earned'] for row in rows),
        historical_cutoff=cutoff, source='saved_championships_and_precareer_club_history',
        read_only=True, reason='每一座奖杯都属于夺冠时的俱乐部。' if rows else '下一座奖杯，从这里开始。')
