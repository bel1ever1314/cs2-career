"""Major breaks are the delivery window for long-form career stories.

Keep frozen stories in the schema-v2 incident state until the next break.
Match decisions, calendar occasions and essential business prompts remain
actionable when due. A birthday is not a long-form offseason chapter.
Opening a UI never advances dates or rolls a new story outcome.
"""
from datetime import date, timedelta

IMMEDIATE = {'fix_offer', 'fix_probe', 'fix_ban', 'loan_default', 'loan_flee_ban',
             'tournament_decision', 'transfer_decision', 'transfer_farewell',
             'transfer_reaction', 'awards', 'top20', 'major_coach', 'incident_result'}
MATCH_TRIGGERS = {'before_match', 'after_series', 'coach_absent', 'series_started',
                  'map_started', 'map_finished', 'series_finished', 'tournament_stage_started'}


def state(c):
    return c.incident_state.setdefault('story_timing', {'schema_version': 1, 'windows': [], 'deferred': []})


def open_major_break(c, s, ev):
    if ev.get('type') != 'major':
        return
    from .arcs import config
    value = state(c)
    key = f"{s.year}:{ev['id']}"
    if any(w['key'] == key for w in value['windows']):
        return
    # Use the actual completed event date, including delayed saved fixtures.
    end = max([s.date, *(ev.get('dates') or [s.date])])
    until = (date.fromisoformat(end) + timedelta(days=config()['rules'].get('offseason_days', 21))).isoformat()
    value['windows'].append({'key': key, 'event': ev['name'], 'start': end, 'until': until})
    value['windows'] = value['windows'][-6:]
    value.setdefault('first_major', key)


def window(c, s):
    value = c.incident_state.get('story_timing', {})
    return next((w for w in reversed(value.get('windows', [])) if w['start'] <= s.date <= w['until']), None)


def immediate(row):
    if row.get('timing')=='offseason':return False
    return (calendar_event(row) or row.get('timing') == 'match' or row.get('when') in IMMEDIATE
            or row.get('arc') in ('upgrade', 'na_start')
            or row.get('when') == 'start'
            or row.get('trigger') in MATCH_TRIGGERS)


def calendar_event(row):
    """Recognize old birthday payloads as well as explicitly dated notices."""
    return (row.get('timing') == 'calendar' or row.get('when') == 'teammate_birthday'
            or (row.get('when') == 'arc_reaction'
                and str(row.get('id', '')).startswith('arc-notice:')
                and ':birthday:' in str(row.get('id', ''))))


def calendar_pending(c):
    return any(calendar_event(row) and immediate(row) and row.get('choices') for row in c.story_queue)


def queued(c, sid):
    return any(r.get('id') == sid for r in c.incident_state.get('story_timing', {}).get('deferred', []))


def reconcile(c, s):
    if not c.exists or c.over():
        return False
    value = state(c)
    changed = False
    # Saves made before calendar occasions were separated may already have a
    # birthday in the deferred queue. Release it once, without rolling effects
    # or moving the simulation date backwards; retain the original event date.
    existing = set(c.seen_stories) | {r.get('id') for r in c.story_queue}
    remaining = []
    for row in value['deferred']:
        if calendar_event(row) and immediate(row):
            sid = str(row.get('id', ''))
            if row.get('when') == 'teammate_birthday' and sid.startswith('bday.'):
                row.setdefault('date', sid[5:15])
            if row.get('id') not in existing:
                c.story_queue.append(row)
                existing.add(row.get('id'))
            changed = True
        else:
            remaining.append(row)
    value['deferred'] = remaining
    if window(c, s):
        existing = set(c.seen_stories) | {r.get('id') for r in c.story_queue}
        for row in value['deferred']:
            if row.get('id') not in existing:
                c.story_queue.append(row)
                existing.add(row.get('id'))
        changed = changed or bool(value['deferred'])
        value['deferred'] = []
    else:
        keep = []
        deferred = {r.get('id') for r in value['deferred']}
        for row in c.story_queue:
            if immediate(row):
                keep.append(row)
            else:
                if row.get('id') not in deferred:
                    value['deferred'].append(row)
                    deferred.add(row.get('id'))
                changed = True
        c.story_queue = keep
    return changed


def public(c, s):
    current = window(c, s)
    from .arcs import config
    return {'open': bool(current), 'window': current,
            'deferred_count': len(c.incident_state.get('story_timing', {}).get('deferred', [])),
            'days': config()['rules']['offseason_days'],
            'rule': 'Main stories appear after a Major. Birthdays occur on their date; match incidents can interrupt a series.'}
