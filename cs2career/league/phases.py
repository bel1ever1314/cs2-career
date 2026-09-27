"""Saved, idempotent gameplay phase hooks for pure-data incident packs.

This is a command boundary, never a UI polling hook. The context describes
already reached phases; it does not manufacture a live half-time for a map
which was simulated in one operation.
"""
from copy import copy

PHASES = {'series_started', 'map_started', 'map_finished', 'series_finished', 'tournament_stage_started'}


def emit(season, event, match, phase, map_index=None):
    if phase not in PHASES:
        raise ValueError('Unsupported competition phase')
    c = getattr(season, 'career', None)
    if not c or not c.exists or not season.is_yours(match):
        return
    key = f"{phase}:{c.team_id}:{map_index if map_index is not None else ''}"
    seen = match.setdefault('phase_hooks', [])
    backlog = match.setdefault('phase_pending', [])
    if key in seen or any(item['key'] == key for item in backlog):
        return
    context = {'event_id': event['id'], 'event_name': event['name'], 'stage': match.get('stage', ''),
               'match_id': match['id'], 'player': c.player_name, 'team': season.your_team_name(),
               'map_index': str((map_index or 0) + 1)}
    # Map end and series end can occur in one command. Persist both even when
    # the first one opens a decision. The second hook waits for acknowledgement.
    backlog.append({'key': key, 'phase': phase, 'context': context, 'date': season.date,
                    'year': season.year, 'team_id': c.team_id,
                    'occurrence': f"{season.year}:{event['id']}:{match['id']}:{key}",
                    'event_type': event.get('type', '')})
    drain(season)


def drain(season):
    """Call only after gameplay commands or acknowledging a decision, never GET."""
    from ..career import incidents
    c = getattr(season, 'career', None)
    if not c or not c.exists or c.over() or incidents.pending(c):
        return
    for event in getattr(season, 'events', []):
        for match in event.get('matches', []):
            backlog = match.get('phase_pending', [])
            while backlog:
                item = backlog[0]
                seen = match.setdefault('phase_hooks', [])
                if item['key'] not in seen and item['team_id'] == c.team_id:
                    # Keep the observation date used by deterministic rolls,
                    # cooldowns and text, even if the save is resumed later.
                    observed = copy(season)
                    observed.date = item['date']
                    observed.year = item['year']
                    incidents.emit(c, observed, item['phase'], item['occurrence'],
                                   item['event_type'], item['context'])
                if item['key'] not in seen:
                    seen.append(item['key'])
                backlog.pop(0)
                if incidents.pending(c):
                    return
