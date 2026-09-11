"""Read models for desktop/web. Never mutate a match or invent missing stats.

Historical records contain roster snapshots; current team membership is only
used to resolve a uniquely identifiable legacy name, never to rewrite history.
"""
from copy import deepcopy
from datetime import date, timedelta
from math import isfinite
from .engine.rating import career_rating
from .league import formats
from .league import awards
from .world.era_data import quality_view


def events(season):
    # Calendar IDs repeat annually. Qualify read-only routes, NOT engine IDs
    # used by invitations, qualification, pending CS2 sessions, or old saves.
    by_id = {}
    for archived, rows in ((True, season.history), (False, season.events)):
        for ev in rows:
            year = str(ev.get('year') or (ev.get('dates') or [ev.get('date', '')])[0])[:4]
            key = route_key(year, ev['id'])
            by_id[key] = {**ev, 'id': key, 'legacy_id': ev['id'], 'route_year': year, 'archived': archived}
    return list(by_id.values())


def route_key(year, key):
    return f'{year}::{key}' if len(str(year)) == 4 and str(year).isdigit() else key


def resolve_legacy(candidates):
    """Raw IDs mean current season; ambiguous historical IDs must not guess."""
    current = [pair for pair in candidates if not pair[0]['archived']]
    rows = current or candidates
    return rows[0] if len(rows) == 1 else None


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def measured(row, rounds):
    return (numeric(rounds) and rounds > 0 and all(numeric(row.get(k)) and row[k] >= 0 for k in ('k', 'd', 'a', 'damage'))
            and (numeric(row.get('kast_rounds')) and 0 <= row['kast_rounds'] <= rounds
                 or numeric(row.get('kast')) and 0 <= row['kast'] <= 1))


def current_players(state):
    return [(p, t) for t in state.season.teams for p in t['players']] + [(p, None) for p in state.career.free]


def identity(state, name):
    ids = {p.get('player_id') for p, _ in current_players(state) if p['name'] == name and p.get('player_id')}
    return next(iter(ids)) if len(ids) == 1 else None


def saved_players(state):
    """Observed identities only: never manufacture a retired player's ability."""
    for ev in events(state.season):
        for match in ev.get('matches') or []:
            for mp in match.get('maps') or []:
                for team, rows in (mp.get('players') or {}).items():
                    for player in rows:
                        yield player, team, match.get('date') or ev.get('date') or ''


def empty_honours():
    return {'titles': [], 'mvp': [], 'evp': [], 'top20': [], 'counts': {}}


def aggregate(rows):
    """Each input has a player row + its map's rounds. Missing is not zero."""
    if not rows:
        return {'maps': 0, 'rounds': 0, 'rating': None, 'adr': None, 'kast': None}
    totals = {k: 0 for k in ('k', 'd', 'a', 'damage', 'kast_rounds', 'opening_kills', 'opening_deaths', 'survived_rounds')}
    complete = all(measured(p, n) for p, n in rows)
    rounds = sum(n for _, n in rows)
    for p, n in rows:
        for k in totals:
            if k == 'kast_rounds':
                value = p.get(k, (p.get('kast') or 0) * n)
                totals[k] += value if numeric(value) else 0
            else:
                value = p.get(k)
                totals[k] += value if numeric(value) else 0
    out = {**totals, 'maps': len(rows), 'rounds': rounds, 'data_complete': complete}
    out.update(rating=career_rating(totals['k'], totals['d'], totals['a'], totals['damage'], totals['kast_rounds'], rounds) if complete else None,
               adr=round(totals['damage'] / max(1, rounds), 1) if complete else None,
               kast=totals['kast_rounds'] / max(1, rounds) if complete else None,
               kpr=round(totals['k'] / max(1, rounds), 3))
    return out


def in_range(day, season, span):
    if not day:
        return span == 'all'
    if span == '30d':
        return (date.fromisoformat(season.date) - timedelta(days=30)).isoformat() <= day <= season.date
    return span == 'all' or str(day).startswith(str(season.year))


def inspect(state, kind, key, span='season', page=1, page_size=20):
    season, career = state.season, state.career
    target_id = None
    if kind == 'team':
        row = career.inspect_team(season, key)
        if not row:
            return None
        name = row['name']
        team = next((t for t in season.teams if t['name'] == name), None)
        if team:
            row['data_provenance'] = quality_view(team, team=True)
    else:
        candidates = [(p, t) for p, t in current_players(state) if p.get('player_id') == key]
        if not candidates:
            candidates = [(p, t) for p, t in current_players(state) if p['name'] == key]
        if candidates:
            unique = {(p.get('player_id') or p['name']) for p, _ in candidates}
            if len(unique) != 1:
                return None
            player, team = candidates[0]
            name = player['name']
            target_id = player.get('player_id') or identity(state, name)
            row = career.inspect_player(season, name)
            if not row:
                return None
            # Name-based compatibility lookup must not supply another person's
            # attributes when the caller supplied a stable ID.
            row.update({k: player.get(k) for k in ('name', 'role', 'ability', 'command', 'age', 'form', 'stats', 'is_igl', 'roster_status')})
            row.update(team=team['name'] if team else None, team_id=team['id'] if team else None,
                       player_id=target_id, form_delta=player.get('form_delta', 0), historical=False)
            row['data_provenance'] = quality_view(player)
        else:
            snapshots = list(saved_players(state))
            matches = [item for item in snapshots if item[0].get('player_id') == key]
            if not matches:
                matches = [item for item in snapshots if item[0].get('name') == key]
            ids = {p.get('player_id') for p, _, _ in matches}
            if len(ids) != 1 or not all(ids):
                return None
            player, last_team, last_seen = max(matches, key=lambda item: item[2])
            name, target_id = player['name'], player['player_id']
            row = dict(kind='player', name=name, player_id=target_id, historical=True, last_seen=last_seen,
                       last_team=last_team, team=None, role=None, age=None, ability=None, command=None,
                       form_delta=None, stats={}, honours=empty_honours())
            row['data_provenance'] = quality_view(player)
        name_ids = {p.get('player_id') for p, _ in current_players(state) if p['name'] == name}
        name_ids.update(p.get('player_id') for p, _, _ in saved_players(state) if p.get('name') == name)
        if name_ids == {target_id}:
            row['honours'] = awards.honours_for(season.records(include_matches=False), season.top20, name)
        else:
            row['honours'] = empty_honours()
            row['honours_notice'] = '同名历史身份无法唯一关联，未猜测荣誉归属。'
    records, stat_rows = [], []
    for ev in events(season):
        for m in ev.get('matches') or []:
            if not in_range(m.get('date') or (ev.get('dates') or [None])[0], season, span):
                continue
            base = dict(event_id=ev['id'], event=ev['name'], match_id=route_key(ev['route_year'], m['id']), date=m.get('date', ''),
                        team_a=m['team_a'], team_b=m['team_b'], series=m.get('series'), played=m.get('played', False))
            if kind == 'team':
                if name in (m['team_a'], m['team_b']):
                    records.append({**base, 'won': m.get('winner') == name})
                continue
            for index, mp in enumerate(m.get('maps') or []):
                for team_name, players in (mp.get('players') or {}).items():
                    for p in players:
                        match_id = p.get('player_id')
                        hit = bool(target_id and match_id == target_id) if match_id else p.get('name') == name and name_ids == {target_id}
                        if not hit:
                            continue
                        n = int(mp.get('rounds') or 0)
                        rec = {**base, 'map': mp['map'], 'map_index': index, 'score': mp.get('score'), 'team': team_name,
                               'opponent': m['team_b'] if team_name == m['team_a'] else m['team_a'], 'rounds': n, **deepcopy(p)}
                        records.append(rec)
                        stat_rows.append((rec, n))
    records.sort(key=lambda x: (x['date'], x['match_id'], x.get('map_index', 0)), reverse=True)
    page, page_size = max(1, int(page)), max(1, min(100, int(page_size)))
    row.update(range=span, page=page, page_size=page_size, total=len(records), recent=records[:10],
               records=records[(page-1)*page_size:page*page_size])
    if kind == 'player':
        row['summary'] = aggregate(stat_rows)
    return row


def match_detail(state, mid):
    pairs = [(ev, m) for ev in events(state.season) for m in ev.get('matches', [])]
    exact = [(ev, m) for ev, m in pairs if route_key(ev['route_year'], m['id']) == mid]
    found = resolve_legacy(exact or [(ev, m) for ev, m in pairs if m['id'] == mid])
    if not found:
        return None
    ev, original = found
    m = deepcopy(original)
    totals = {}
    for mp in m.get('maps') or []:
        grouped = mp.get('players') or {}
        lines = [(tm, p) for tm, players in grouped.items() for p in players]
        ids = [p.get('player_id') or identity(state, p['name']) for _, p in lines]
        mp['data_complete'] = (len(lines) == 10 and all(len(grouped.get(tm, [])) == 5 for tm in (m['team_a'], m['team_b']))
                               and all(ids) and len(set(ids)) == 10
                               and all(measured(p, mp.get('rounds')) for _, p in lines))
        for tm, p in lines:
            pid = p.get('player_id') or identity(state, p['name'])
            p['resolved_player_id'] = pid
            key = (tm, pid or p['name'])
            bucket = totals.setdefault(key, {'name': p['name'], 'player_id': pid, 'team': tm, 'rows': []})
            bucket['rows'].append((p, int(mp.get('rounds') or 0)))
        round_groups = {}
        for event in mp.get('events') or []:
            number = int(event.get('round') or 0)
            if number <= 0:
                continue
            rd = round_groups.setdefault(number, {'number': number, 'winner': None, 'events': []})
            if event.get('type') == 'round_end':
                win = event.get('winner')
                rd['winner'] = m['team_a'] if win == 'a' else m['team_b'] if win == 'b' else win
            else:
                rd['events'].append(event)
        mp['round_history'] = sorted(round_groups.values(), key=lambda r: r['number'])
        mp['events_available'] = bool(round_groups)
    m['totals'] = [{k: v for k, v in b.items() if k != 'rows'} | aggregate(b['rows']) for b in totals.values()]
    m['data_complete'] = bool(m.get('maps')) and all(mp['data_complete'] for mp in m['maps'])
    m['route_id'] = route_key(ev['route_year'], m['id'])
    return {'event': {'id': ev['id'], 'name': ev['name'], 'short': ev.get('short')}, 'match': m,
            'yours': not ev['archived'] and state.season.is_yours(original)}


def event_detail(state, eid):
    rows = events(state.season)
    found = resolve_legacy([(e, None) for e in rows if e['id'] == eid] or [(e, None) for e in rows if e['legacy_id'] == eid])
    if not found:
        return None
    ev = found[0]
    out = deepcopy(ev)
    if ev['archived']:
        out.setdefault('status', 'done')
        out['awards'] = out.get('awards') or {k: deepcopy(ev.get(k)) for k in ('mvp', 'evp', 'five')}
    for m in out.get('matches') or []:
        m['id'] = route_key(ev['route_year'], m['id'])
    # Only connect participants actually resolved by the engine. Future Swiss
    # pairing is deliberately not inferred; pending matches remain unknown.
    links = []
    seen = []
    for m in out.get('matches', []):
        for slot in ('team_a', 'team_b'):
            tm = m[slot]
            prior = next((p for p in reversed(seen) if p.get('played') and tm in (p['team_a'], p['team_b']) and tm != 'BYE'), None)
            if prior:
                links.append({'source': prior['id'], 'target': m['id'], 'team': tm,
                              'outcome': 'winner' if prior.get('winner') == tm else 'loser'})
        seen.append(m)
    out['links'] = links
    out['swiss_table'] = list(formats.swiss_state(ev).values()) if ev.get('swiss_round') else []
    out['major_tables'] = formats.major_tables(ev)
    out['groups_table'] = formats.gsl_standings(ev) if ev.get('gsl_field') else {}
    return out
