"""Small, immutable-in-the-receipt scorecard for automatic series playback.

Only saved map rows are read. No event replay, reward or simulation happens
here; per-map rates are never averaged to manufacture series statistics.
"""
from ..presentation import aggregate, measured


def series_report(match, player_id, player_team):
    maps = match.get('maps') or []
    buckets = {}
    complete = bool(maps)
    for mp in maps:
        grouped = mp.get('players') or {}
        lines = [(team, row) for team, rows in grouped.items() for row in rows]
        ids = [row.get('player_id') for _, row in lines]
        complete = complete and (len(lines) == 10 and all(ids) and len(set(ids)) == 10
            and all(len(grouped.get(team, [])) == 5 for team in (match['team_a'], match['team_b'])))
        for team, row in lines:
            pid = row.get('player_id')
            # Legacy rows without stable identity cannot safely be combined.
            if not pid:
                complete = False
                continue
            bucket = buckets.setdefault((team, pid), dict(team=team, player_id=pid,
                name=row.get('name', ''), rows=[]))
            bucket['rows'].append((row, int(mp.get('rounds') or 0)))
            complete = complete and measured(row, mp.get('rounds'))
    totals = []
    for bucket in buckets.values():
        totals.append({k: v for k, v in bucket.items() if k != 'rows'} | aggregate(bucket['rows']))
        totals[-1]['data_complete'] = totals[-1]['data_complete'] and totals[-1]['maps'] == len(maps)
    complete = bool(complete and len(totals) == 10 and all(row['maps'] == len(maps) for row in totals))
    return dict(player_id=player_id, player_team=player_team, totals=totals,
        data_complete=complete, played=bool(match.get('played')), winner=match.get('winner'))
