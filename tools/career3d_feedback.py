"""Read-only honours feed from frozen event/year records; explicit ack only.

GET never evaluates awards, advances dates, creates notices or marks them seen.
Participation comes from saved stable map identities, not today's club roster.
"""
from copy import deepcopy


def _human(state):
    return state.arena.career_player_id(state)


def _participation(event, human_id):
    if not human_id:
        return None
    for match in event.get('matches') or []:
        if not match.get('played') or match.get('forfeit'):
            continue
        for saved in match.get('maps') or []:
            for team, rows in (saved.get('players') or {}).items():
                for player in rows:
                    if player.get('player_id') == human_id:
                        return dict(team=team, name=player.get('name') or player.get('player') or '',
                                    player_id=human_id, source='saved_map_identity')
        frozen = match.get('career3d_identity') or {}
        if frozen.get('player_id') == human_id and match.get('maps'):
            return dict(team=frozen.get('player_team', ''), name=frozen.get('player_name', ''),
                        player_id=human_id, source='frozen_match_identity')
    return None


def _already_read(career, story_id):
    notices = [row for row in career.inbox if row.get('notification_id') == story_id]
    if notices:
        return all(row.get('read') for row in notices)
    return story_id in career.seen_stories


def _top20_payload(state, year, rows):
    human_id = _human(state)
    frozen = deepcopy(rows)
    # Do not resolve missing historic IDs using the current team/name lookup.
    for row in frozen:
        row['name'] = row.get('player', row.get('name', ''))
    rank = next((row.get('rank') for row in frozen if human_id and row.get('player_id') == human_id), None)
    return dict(ready=bool(frozen), finalized=True, year=year, years=[year],
                top3=deepcopy(frozen[:3]), top20=frozen, rows=deepcopy(frozen),
                human_id=human_id, player_rank=rank, source='season.top20',
                attendees=[], attendees_source='frozen_award_rows', attendees_current=False,
                reason='年度正式归档榜单。' if frozen else '年度已归档，本年度没有符合样本要求的选手。')


def feedback_context(state, include_acknowledged=False):
    c, s = state.career, state.season
    store = c.incident_state.get('career3d_service') or {}
    acked = set(store.get('feedback_ack') or [])
    quick = bool(c.assist.get('quick_mode'))
    human_id = _human(state)
    items = []
    for event in s.events:
        dates = event.get('dates') or []
        stamp = dates[-1] if dates else max((m.get('date', '') for m in event.get('matches') or []), default='')
        if event.get('status') != 'done' or not stamp or stamp[:4] != str(s.year) or stamp > s.date:
            continue
        awards = event.get('awards')
        if not isinstance(awards, dict) or event.get('type') == 'qual':
            continue
        who = _participation(event, human_id)
        if not who:
            continue
        story_id = 'awards.' + event['id']
        key = f'event-awards:{s.year}:{event["id"]}:{human_id}'
        if not include_acknowledged and (key in acked or _already_read(c, story_id)):
            continue
        items.append(dict(id=key, kind='event_awards', story_id=story_id,
            event_id=f'{s.year}:{event["id"]}', event_engine_id=event['id'],
            event_name=event['name'], title=event['name'] + ' · 赛事荣誉', date=stamp,
            participated=True, quick=quick, own_team=who['team'], human_id=human_id,
            human_name=who['name'], participation_source=who['source'],
            champion=event.get('champion') or '', is_champion=event.get('champion') == who['team'],
            mvp=deepcopy(awards.get('mvp')), evp=deepcopy(awards.get('evp') or []),
            five=deepcopy(awards.get('five') or []), rows=[], source='completed_event.awards'))
    # Only the current formal list, or a just-rolled year's still-unread notice,
    # can enter a new presentation queue. Historical lists remain in rankings.
    for year in sorted((int(value) for value in s.top20 if str(value).isdigit()), reverse=True):
        if year not in (s.year, s.year - 1):
            continue
        if year == s.year and (not s.events or any(event.get('status') != 'done' for event in s.events)):
            continue
        story_id = f'top20.{year}'
        active = any(row.get('id') == story_id for row in c.story_queue)
        unread = any(row.get('notification_id') == story_id and not row.get('read') for row in c.inbox)
        if year != s.year and not (active or unread):
            continue
        key = f'top20:{year}:{human_id}'
        if not include_acknowledged and (key in acked or _already_read(c, story_id)):
            continue
        rows = deepcopy(s.top20[str(year)])
        date = (getattr(s, 'top20_dates', {}) or {}).get(str(year)) or f'{year}-12-31'
        items.append(dict(id=key, kind='top20', story_id=story_id, year=year, title=f'{year} 年度 Top20',
            date=date, event_id='', event_name='', participated=True, quick=quick,
            own_team='', human_id=human_id, champion='', mvp=None, evp=[], five=[], rows=rows,
            source='season.top20', ceremony=_top20_payload(state, year, rows)))
        break
    items.sort(key=lambda row: (row['date'], row['id']))
    return dict(items=items, total=len(items), revision=int(store.get('revision', 0)),
                source='frozen_completed_event_and_final_top20', read_only=True)


def acknowledge_feedback(state, body):
    """Idempotent acknowledgement; never applies a choice or settles rewards."""
    from tools.career3d_business import guard_revision
    ids = body.get('ids') if 'ids' in body else [body.get('id')]
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 24
            or any(not isinstance(key, str) or not key for key in ids) or len(set(ids)) != len(ids)):
        raise ValueError('请提供 1 至 24 个明确的反馈 id。')
    c = state.career
    existing = set((c.incident_state.get('career3d_service') or {}).get('feedback_ack') or [])
    if all(key in existing for key in ids):
        return dict(reason='这份荣誉反馈已经确认。', acknowledged=ids, replayed=True)
    guard_revision(state, body)
    items = {item['id']: item for item in feedback_context(state, include_acknowledged=True)['items']}
    if any(key not in items and key not in existing for key in ids):
        raise ValueError('反馈不存在或不属于当前可确认的赛事/年度，请刷新。')
    # Validate the complete request before mutating. Only no-effect honour
    # notices can be dismissed together; contract/incident choices stay live.
    for key in ids:
        item = items.get(key)
        if not item:
            continue
        sid = item['story_id']
        row = next((row for row in c.story_queue if row.get('id') == sid), None)
        if (row and row.get('kind') in ('awards', 'top20') and not row.get('choices')
                and not any(row.get(field) for field in ('effects', 'arc', 'trigger'))):
            # This is an informational acknowledgement, not a story command.
            # ack_story() also drains hooks/phases and reschedules other rows;
            # avoid those unrelated choice side effects for a feedback close.
            c.story_queue = [story for story in c.story_queue if story.get('id') != sid]
            if sid not in c.seen_stories:
                c.seen_stories.append(sid)
        for notice in c.inbox:
            if notice.get('notification_id') == sid and (notice.get('notification') or {}).get('kind') in ('awards', 'top20'):
                notice['read'] = True
    store = c.incident_state.setdefault('career3d_service', {'revision': 0, 'receipts': []})
    store['feedback_ack'] = sorted(existing | set(ids))[-512:]
    return dict(reason='荣誉反馈已确认；已结算奖金与属性点没有重复发放。', acknowledged=ids,
                feedback=feedback_context(state))
