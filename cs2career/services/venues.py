"""Identity-bound venue facts and stage-based career presentation.

The playable scene follows the career's policy: qualifiers/CCT-level events
and verified online phases are online, other early stages use ten-player LAN
rooms, and their playoffs use arenas. Physical venue facts remain edition/phase
scoped, and reading a legacy fixture never replaces its frozen roster.
"""
from copy import deepcopy

VENUE_POLICY_VERSION = '20261007.1'
PLAYOFF_STAGES = frozenset(('R16', 'QF', 'SF', 'GF'))

# Exact edition names protect recurring event IDs and future fictional seasons.
KNOWN = {
    (2025, 'blast-bounty'): dict(event_name='BLAST Premier Bounty Season 1 2025',
        studio='BLAST Studios Copenhagen', city='Copenhagen', country='Denmark',
        online_groups=True, online_stages=('R32', 'RO32', 'R16', 'RO16'),
        source_url='https://blast.tv/cs/news/bounty-season-1-quarterfinal-schedule'),
    (2024, 'major-2'): dict(event_name='Perfect World Shanghai Major 2024',
        arena='浦发银行东方体育中心', studio='上海世博中心', city='上海', country='中国',
        source_url='https://www.csgo.com.cn/article/details/20240906/225749.html'),
    (2025, 'major-1'): dict(event_name='BLAST.tv Austin Major 2025',
        arena='Moody Center', city='Austin', country='United States',
        source_url='https://blast.tv/cs/news/everything-you-need-to-know-about-blasttv-austin-major-playoffs'),
    (2025, 'major-2'): dict(event_name='StarLadder Budapest Major 2025',
        arena='MVM Dome', studio='MTK Sportpark', city='Budapest', country='Hungary',
        source_url='https://major.starladder.com/'),
    (2026, 'major-1'): dict(event_name='IEM Cologne Major 2026',
        arena='LANXESS arena', city='Cologne', country='Germany',
        source_url='https://pro.eslgaming.com/tour/2025/08/iem-cologne-major-announcement/'),
    (2026, 'major-2'): dict(event_name='PGL Major Singapore 2026',
        arena='Singapore Indoor Stadium', city='Singapore', country='Singapore',
        source_url='https://www.pglesports.com/cs2/pgl-major-singapore-2026/'),
    (2026, 'iem-krakow'): dict(event_name='IEM Kraków 2026',
        arena='TAURON Arena Kraków', city='Kraków', country='Poland',
        source_url='https://pro.eslgaming.com/tour/2026/02/annual-club-inventive-iem-krakow-update/'),
    (2026, 'blast-open-1'): dict(event_name='BLAST Premier Open Rotterdam 2026',
        arena='Ahoy Arena', studio='BLAST Copenhagen studios', city='Rotterdam', country='Netherlands',
        studio_city='Copenhagen', studio_country='Denmark',
        source_url='https://blast.tv/cs/news/blast-premier-open-rotterdam-coming-in-march-2026'),
    (2026, 'blast-bounty'): dict(event_name='BLAST Premier Bounty Season 1 2026',
        studio='BLAST Studio, Malta', city='Malta', country='Malta', online_groups=True,
        online_stages=('R32', 'RO32', 'R16', 'RO16'),
        source_url='https://blast.tv/cs/tournaments/bounty-2026-season-1'),
}


def _venue_details(year, event, match):
    """Separate the game's venue scene from sourced, real-world venue facts."""
    # A group elimination match is still a group-stage fixture. Do not use the
    # event's current phase: it may already have advanced beyond an older match.
    playoff = (str(match.get('stage', '')).upper() in PLAYOFF_STAGES
               or str(match.get('phase', '')).lower() == 'playoff')
    kind = str(event.get('type', '')).lower()
    known = KNOWN.get((year, event['id'])) or {}
    if known.get('event_name') != event['name']:
        known = {}
    # Bounty's opening elimination rounds are online too. A generic R16
    # playoff label must not force an edition's online phase into a venue.
    online_phase = bool(known.get('online_groups') and
                        (not playoff or str(match.get('stage', '')).upper() in known.get('online_stages', ())))
    online = online_phase or kind in ('qual', 'cct') or 'challenger league' in event.get('name', '').lower()
    scale = 'online' if online else 'arena' if playoff else 'studio'

    real_scale, name = 'unknown', ''
    city, country = known.get('city', ''), known.get('country', '')
    if known:
        if online_phase:
            real_scale = 'online'
        elif playoff and known.get('arena'):
            real_scale, name = 'arena', known['arena']
        else:
            real_scale, name = 'studio', known.get('studio', '')
            city = known.get('studio_city', city)
            country = known.get('studio_country', country)
    capacity = (0 if scale != 'arena' else 10000 if kind in ('major','premier') else
                1000 if kind in ('t1',) else 100)
    return dict(destination='club' if online else 'major' if playoff else 'lan', capacity=capacity,
        scale=scale, is_lan=not online, name=name, verified=bool(name),
        city=city, country=country, source_url=known.get('source_url', ''),
        real_venue_phase='playoffs' if playoff and not online_phase else 'early_stages',
        real_venue_scale=real_scale, real_venue_name=name,
        venue_policy_version=VENUE_POLICY_VERSION,
        venue_policy='verified_online_phase' if online_phase else 'online_qualifier_or_cct' if online else
                     'playoff_arena' if playoff else 'early_stage_ten_player_lan',
        note='比赛场景按赛制分阶段呈现；对阵及赛程来自生涯模拟。')


def _arrival_details(state, match, venue):
    """Refresh visit timing without changing a frozen roster or fixture."""
    today = state.season.date
    due = bool(not match.get('played') and match['date'] <= today
               and state.season.yours_ready(match))
    destination = 'major' if venue.get('scale') == 'arena' else 'lan' if venue.get('is_lan') else 'club'
    label = venue.get('name') or ('小型赛场' if destination == 'lan' else
                                '大型场馆' if destination == 'major' else '俱乐部训练室')
    venue.update(display_name=label, visit_destination=destination, due=due,
                 match_date=match['date'], should_walk=bool(venue['travel_allowed'] and due))
    plan = match.get('career3d_attendance') or {}
    venue['entry_completed'] = bool(plan.get('seated') and
        plan.get('match_identity') == venue.get('match_identity') and
        plan.get('player_id') == state.arena.career_player_id(state))
    return venue


def attendance_for(state, event, match, venue=None):
    """Player-facing match-day plan. Reading it never opens a series."""
    venue = venue if venue is not None else venue_for(state, event, match)
    s = state.season
    yours = s.is_yours(match)
    done = bool(match.get('played'))
    due = bool(yours and not done and match['date'] <= s.date and s.yours_ready(match))
    progress = bool(match.get('cs2_session') or match.get('career3d_rts') or match.get('maps') or venue.get('entry_completed'))
    phase = ('finished' if done else 'in_progress' if progress else
             'scheduled' if match['date'] > s.date else 'today' if match['date'] == s.date else 'overdue')
    plan = match.get('career3d_attendance') or {}
    key = f'{s.year}:{event["id"]}:{match["id"]}'
    planned = bool(yours and not done and plan.get('mode') == 'personal'
                   and plan.get('match_identity') == key
                   and plan.get('player_id') == state.arena.career_player_id(state))
    destination = venue.get('visit_destination', 'club')
    label = venue.get('display_name', '俱乐部训练室')
    if done:
        instruction = '这场比赛已经结束，可以查看战报。'
    elif progress:
        instruction = '返回本场席位，继续当前比赛；已完成地图保留。'
    elif match['date'] > s.date:
        instruction = f'先睡到 {match["date"]}，早上前往「{label}」。'
    elif destination == 'club':
        instruction = '比赛日到了，到俱乐部训练室的比赛电脑准备。'
    else:
        instruction = f'比赛日到了，到门口选择「{label}」，前往选手席入座。'
    own = s.your_team_name()
    opponent = match['team_b'] if match['team_a'] == own else match['team_a']
    place_ready = bool(destination == 'club' or venue.get('travel_allowed'))
    can_resume = bool(due and progress and place_ready)
    can_return = bool(can_resume and match['date'] == s.date)
    return dict(planned=planned, mode='personal' if planned else '', match_id=match['id'],
        match_identity=key, event_id=event['id'], event_name=event['name'],
        date=match['date'], opponent=opponent, phase=phase,
        destination=destination, display_name=label, venue_name=label,
        instruction=instruction, is_today=match['date'] == s.date, due=due,
        can_travel=bool(due and not progress and place_ready),
        can_resume=can_resume, can_return=can_return,
        return_destination=destination if can_return else '',
        sleep_target=match['date'] if yours and not done and match['date'] > s.date else '')


def venue_for(state, event, match):
    frozen = match.get('career3d_venue')
    if frozen:
        result = deepcopy(frozen)
        # Legacy saves froze the old unknown/online fallback. Refresh only
        # presentation facts in the returned view; fixture IDs, team identity,
        # ten player IDs and the original saved record are not modified.
        result.update(_venue_details(state.season.year, event, match))
        result['travel_allowed'] = bool(result.get('is_lan') and result.get('roster_complete')
            and state.season.is_yours(match) and not match.get('played'))
        result['identity_source'] = 'frozen_match_rosters'
        return _arrival_details(state, match, result)
    s, c = state.season, state.career
    human = state.arena.career_player_id(state)
    current = c.my_team(s.teams) or {}
    old_identity = match.get('career3d_identity') or {}
    human = old_identity.get('player_id') or human
    own_team = old_identity.get('player_team') or current.get('name', '')
    by_name = {team['name']: team for team in s.teams}
    def roster(name):
        return [dict(id=player.get('player_id') or '', player_id=player.get('player_id') or '',
                     name=player['name'], role=player.get('role', ''), team=name)
                for player in by_name.get(name, {}).get('players', [])]
    a, b = roster(match['team_a']), roster(match['team_b'])
    ids = [player['id'] for player in a + b]
    complete = len(a) == len(b) == 5 and all(ids) and len(set(ids)) == 10 and human in ids
    details = _venue_details(s.year, event, match)
    travel = bool(details['is_lan'] and complete and s.is_yours(match) and not match.get('played'))
    return _arrival_details(state, match, dict(**details,
        travel_allowed=travel, should_walk=bool(travel and s.yours_ready(match)),
        event_id=f'{s.year}:{event["id"]}', event_engine_id=event['id'], event_name=event['name'],
        match_id=match['id'], match_identity=f'{s.year}:{event["id"]}:{match["id"]}',
        team_a=match['team_a'], team_b=match['team_b'], own_team=own_team, human_id=human,
        players_a=a, players_b=b, roster_complete=bool(complete), identity_source='current_fixture_rosters',
        simulation_fixture=True, simulation_schedule=True))
