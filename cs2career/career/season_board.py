"""A read-only season itinerary, not a generator of future match pairings."""
from ..league.awards import event_class


def public(c, s):
    team = c.my_team(s.teams) if c.exists else None
    name = (team or {}).get('name')
    registered = set(c.registered or [])
    invites = {row.get('event_id'): row for row in c.inbox
               if row.get('kind') == 'invite' and row.get('team_id') == c.team_id}
    rows = []
    played = []
    for event in sorted(s.events, key=lambda e: ((e.get('dates') or [''])[0], e['id'])):
        dates = event.get('dates') or []
        actual = [m for m in event.get('matches', []) if m.get('human')]
        mine = [m for m in event.get('matches', []) if m.get('human') or
                (not m.get('played') and name and name in (m.get('team_a'), m.get('team_b')))]
        invite = invites.get(event['id'], {})
        if actual or event['id'] in registered or (name and name in (event.get('field') or [])):
            participation = 'entered'
        elif invite.get('status') == 'open':
            participation = 'invited'
        elif invite.get('status') in ('declined', 'expired') or event.get('status') == 'done':
            participation = 'skipped'
        else:
            participation = 'unknown'
        played.extend(m for m in actual if m.get('played'))
        rows.append(dict(id=event['id'], name=event['name'], dates=list(dates),
            start=dates[0] if dates else '', end=dates[-1] if dates else '',
            type=event.get('type'), **{'class': event_class(event)}, status=event.get('status'),
            participation=participation, reason=invite.get('auto_reason') or invite.get('auto_blocked') or '',
            champion=event.get('champion'),
            own_matches=[{key: m.get(key) for key in ('id','date','stage','label','team_a','team_b',
                          'series','winner','played','best_of')} for m in mine]))
    # Results after a transfer stay associated with the actual played match.
    # A current club's historical world games do not become the player's games.
    series = [r for r in c.incident_state.get('arcs', {}).get('series', [])
              if str(r.get('date', '')).startswith(str(s.year) + '-')]
    results = [dict(id=r['key'], date=r['date'], won=r['win']) for r in series
               if r.get('key') and type(r.get('win')) is bool]
    results.sort(key=lambda r: r['date'])
    # These are the player's historical series, including before a transfer;
    # never substitute the new club's old wins for the player's own record.
    results = list({r['id']: r for r in results}.values())
    return dict(year=s.year, date=s.date, events=rows, series_results=results, summary=dict(
        events=len(rows), finished=sum(r['status']=='done' for r in rows),
        entered=sum(r['participation']=='entered' for r in rows), matches_played=len(played),
        wins=sum(bool(r.get('win')) for r in series), losses=sum(not r.get('win') for r in series)))
