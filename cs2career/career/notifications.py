"""Non-blocking notices, shared by both career modes.

Only acknowledgement-only records are archived. Choices, incident effects,
contracts and operational gates are never answered here. The original payload
is retained with the mail so award details and translations remain available.
"""
from copy import deepcopy


PROTECTED = {'fix_offer', 'fix_probe', 'fix_ban', 'loan_default', 'loan_flee_ban',
             'tournament_decision', 'transfer_decision', 'transfer_farewell',
             'teammate_birthday'}


def informational(row):
    if row.get('kind') == 'awards' and row.get('class') == 'major':
        return False
    return (not row.get('choices') and row.get('kind', 'story') in ('story', 'awards', 'top20')
            and row.get('when') not in PROTECTED and not row.get('effects')
            and not row.get('arc') and not row.get('trigger'))


def obsolete_elimination_prompt(row, c, s):
    """Recognize only our old, identity-bound, no-effect tournament modal.

    This expires an obsolete confirmation, not a player choice. Unknown packs,
    transferred-team records, historical matches and current finals stay live.
    """
    if (row.get('kind') != 'story' or row.get('when') != 'tournament_decision'
            or not str(row.get('id', '')).startswith('tournament-moment:')
            or row.get('team_id') != c.team_id or row.get('effects')
            or row.get('arc') or row.get('trigger')):
        return False
    choices = row.get('choices') or []
    if ({choice.get('id') for choice in choices} != {'manual', 'simulate', 'later'}
            or any(choice.get('effects') for choice in choices)):
        return False
    event = next((e for e in s.events if e['id'] == row.get('event_id')), None)
    if event is None:
        return False
    match = next((m for m in event.get('matches', []) if m['id'] == row.get('match_id')), None)
    if not match or not match.get('stage') or match['stage'] == 'GF':
        return False
    identity = f"{s.year}:{event['id']}:{match['id']}:{c.team_id}"
    return row.get('auto_match') == identity and row['id'] == 'tournament-moment:' + identity


def _body(row, english=False):
    key = 'text_en' if english else 'text'
    if row.get(key):
        return row[key]
    if row.get('kind') == 'awards':
        mvp = (row.get('mvp') or {}).get('player') or '—'
        evp = ', '.join(p.get('player', '') for p in row.get('evp', [])) or '—'
        return (f"Champion: {row.get('champion') or '—'}\nMVP: {mvp}\nEVP: {evp}\n"
                'Full awards are available on the tournament page.' if english else
                f"冠军：{row.get('champion') or '—'}\nMVP：{mvp}\nEVP：{evp}\n"
                '完整最佳阵容与战绩可在赛事资料页查看。')
    if row.get('kind') == 'top20':
        return '\n'.join(f"{i}. {p.get('player') or p.get('name') or '—'}"
                         for i, p in enumerate(row.get('rows', []), 1))
    return row.get('text') or ''


def reconcile(c, s):
    """Archive pure notices once without invoking any choice/reward handler."""
    existing = {r.get('notification_id') for r in c.inbox}
    # News publication already files both a mail and an immutable history row.
    # Removing its popup must not create a second copy of the same newsletter.
    existing.update(r.get('id') for r in c.incident_state.get('arcs', {}).get('history', []))
    changed = False

    def keep(rows):
        nonlocal changed
        remaining = []
        for row in rows:
            sid = row.get('id')
            obsolete = obsolete_elimination_prompt(row, c, s)
            if not sid or (not informational(row) and not obsolete):
                remaining.append(row)
                continue
            if sid not in existing:
                title = row.get('title') or ('年度 Top20' if row.get('kind') == 'top20' else '生涯动态')
                localized = {}
                if row.get('title_en'):
                    localized['title_en'] = row['title_en']
                elif row.get('kind') == 'top20':
                    localized['title_en'] = 'Annual Top 20'
                if row.get('text_en') or row.get('kind') in ('awards', 'top20'):
                    localized['body_en'] = _body(row, True)
                if obsolete:
                    localized['notification_superseded'] = 'nonfinal_confirmation_removed'
                c.inbox.append({'id': 'notice:' + sid, 'kind': 'notification',
                    'date': row.get('date') or s.date, 'title': title,
                    'from': '生涯动态', 'from_en': 'Career updates',
                    'body': _body(row), **localized,
                    'status': 'filed', 'read': False, 'notification_id': sid,
                    'notification': deepcopy(row)})
                existing.add(sid)
            if sid not in c.seen_stories:
                c.seen_stories.append(sid)
            changed = True
        return remaining

    c.story_queue = keep(c.story_queue)
    timing = c.incident_state.get('story_timing', {})
    if timing.get('deferred'):
        timing['deferred'] = keep(timing['deferred'])
    return changed
