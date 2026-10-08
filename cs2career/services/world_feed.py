"""What happened elsewhere while the career advances. Read-only projection.

Days without a player match otherwise show an empty screen. The feed lists
the latest day of finished series between other teams, most relevant first,
and the newest published headlines. Nothing is rolled, saved or generated.
"""
from datetime import date, timedelta

RESULT_LIMIT = 5
NEWS_LIMIT = 2
RESULT_WINDOW_DAYS = 7
NEWS_WINDOW_DAYS = 14


def _days_before(stamp, days):
    try:
        return (date.fromisoformat(stamp[:10]) - timedelta(days=days)).isoformat()
    except (TypeError, ValueError):
        return ''


def _next_fixture(state):
    from cs2career.services.match_queries import player_matches
    pair = next(iter(player_matches(state)), None)
    if not pair:
        return '', ''
    event, match = pair
    mine = state.season.your_team_name()
    return (match['team_b'] if match['team_a'] == mine else match['team_a']), event['id']


def _series(match):
    parts = str(match.get('series') or '').split('-')
    if len(parts) == 2 and all(p.strip().isdigit() for p in parts):
        return [int(parts[0]), int(parts[1])]
    return None


def results(state, ranks, limit=RESULT_LIMIT):
    s = state.season
    mine = s.your_team_name()
    opponent, event_id = _next_fixture(state)
    floor = _days_before(s.date, RESULT_WINDOW_DAYS)
    played = []
    for event in s.events:
        for match in event.get('matches') or []:
            teams = (match.get('team_a'), match.get('team_b'))
            if (not match.get('played') or 'BYE' in teams or mine in teams or not match.get('winner')
                    or not floor or not floor <= str(match.get('date', '')) <= s.date or _series(match) is None):
                continue
            played.append((event, match))
    if not played:
        return '', []
    latest = max(str(m['date']) for _, m in played)
    rows = []
    for event, match in played:
        if match['date'] != latest:
            continue
        a, b = match['team_a'], match['team_b']
        loser = b if match['winner'] == a else a
        rank_a, rank_b = ranks.get(a), ranks.get(b)
        winner_rank, loser_rank = ranks.get(match['winner']), ranks.get(loser)
        upset = bool(winner_rank and loser_rank and loser_rank <= 20 and winner_rank >= loser_rank + 8)
        tag = 'opponent' if opponent in (a, b) else 'event' if event['id'] == event_id else 'upset' if upset else ''
        best = min(r for r in (rank_a, rank_b, 999) if r)
        score = (100 if tag == 'opponent' else 50 if tag == 'event' else 0) + (30 if upset else 0) + max(0, 40 - best)
        rows.append(dict(id=match['id'], event_id=event['id'], event=event.get('name', ''), stage=match.get('stage', ''),
                         date=match['date'], team_a=a, team_b=b, series=_series(match), winner=match['winner'],
                         rank_a=rank_a or 0, rank_b=rank_b or 0, upset=upset, tag=tag, _score=score))
    rows.sort(key=lambda r: (-r['_score'], r['id']))
    for row in rows:
        row.pop('_score')
    return latest, rows[:limit]


def headlines(state, limit=NEWS_LIMIT):
    """Published rows only. Small-event honour records are left to the news page."""
    from cs2career.services.business import news_rows
    s = state.season
    floor = _days_before(s.date, NEWS_WINDOW_DAYS)
    tiers = {ev['id']: ev.get('type', '') for ev in list(getattr(s, 'history', []) or []) + list(s.events)}
    registered = set(getattr(state.career, 'registered', []) or [])
    out = []
    for row in news_rows(state):
        if not (floor and floor <= str(row.get('date', '')) <= s.date and row.get('title')):
            continue
        item = {k: row[k] for k in ('id', 'date', 'title', 'title_en', 'category') if k in row}
        if row.get('category') == 'awards' and row.get('champion'):
            event_id = str(row.get('event_id', '')).split('::')[-1]
            if tiers.get(event_id) not in ('major', 't1') and event_id not in registered:
                continue
            mvp = row.get('mvp') if isinstance(row.get('mvp'), dict) else {}
            item.update(kind='champion', event=row.get('event', ''), champion=row['champion'], mvp=mvp.get('player', ''))
        else:
            item['kind'] = 'news'
        out.append(item)
    out.sort(key=lambda r: (str(r.get('date', '')), str(r.get('id', ''))), reverse=True)
    return out[:limit]


def world_feed(state, table=None):
    s = state.season
    if not getattr(state.career, 'exists', False):
        return dict(date=s.date, results_date='', results=[], news=[])
    table = table if table is not None else s.vrs.table(s.teams, s.date)
    ranks = {row['name']: row['rank'] for row in table}
    day, rows = results(state, ranks)
    return dict(date=s.date, results_date=day, results=rows, news=headlines(state))
