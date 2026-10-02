"""Identity-bound venue metadata; physical venue facts are phase/year scoped.

Names are from organizer announcements, not inferred from tournament prestige.
Unverified venues do not become huge arenas. The game's compressed fixtures are
still simulation fixtures, never relabelled as historical real-world matches.
"""
from copy import deepcopy

# Exact edition names protect recurring event IDs and future fictional seasons.
KNOWN = {
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
        source_url='https://blast.tv/cs/tournaments/bounty-2026-season-1'),
}


def venue_for(state, event, match):
    frozen = match.get('career3d_venue')
    if frozen:
        result = deepcopy(frozen)
        result['travel_allowed'] = bool(result.get('is_lan') and result.get('roster_complete')
            and state.season.is_yours(match) and not match.get('played'))
        result['should_walk'] = bool(result['travel_allowed'] and state.season.yours_ready(match))
        result['identity_source'] = 'frozen_match_rosters'
        return result
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
    known = KNOWN.get((s.year, event['id'])) or {}
    if known.get('event_name') != event['name']:
        known = {}
    playoff = match.get('stage') in ('QF', 'SF', 'GF') or match.get('phase') == 'playoff'
    scale, name, verified, is_lan = 'unknown', '', False, False
    city, country = known.get('city', ''), known.get('country', '')
    if known:
        if known.get('online_groups') and not playoff:
            scale, is_lan = 'online', False
        elif playoff and known.get('arena'):
            scale, name, verified, is_lan = 'arena', known['arena'], True, True
        else:
            # Never assign a playoffs' 20k-seat arena to its early stages.
            scale, name, is_lan = 'studio', known.get('studio', ''), True
            verified = bool(name)
            city = known.get('studio_city', city)
            country = known.get('studio_country', country)
    elif event.get('type') in ('qual', 'cct') or 'Challenger League' in event.get('name', ''):
        scale = 'online'
    travel = bool(is_lan and complete and s.is_yours(match) and not match.get('played'))
    return dict(destination='major' if scale == 'arena' else 'lan', scale=scale,
        is_lan=is_lan, travel_allowed=travel, should_walk=bool(travel and s.yours_ready(match)),
        verified=verified, name=name, city=city, country=country,
        source_url=known.get('source_url', ''), real_venue_phase='playoffs' if playoff else 'early_stages',
        event_id=f'{s.year}:{event["id"]}', event_engine_id=event['id'], event_name=event['name'],
        match_id=match['id'], match_identity=f'{s.year}:{event["id"]}:{match["id"]}',
        team_a=match['team_a'], team_b=match['team_b'], own_team=own_team, human_id=human,
        players_a=a, players_b=b, roster_complete=bool(complete), identity_source='current_fixture_rosters',
        simulation_fixture=True, simulation_schedule=True,
        note='游戏对阵及压缩赛程来自生涯模拟；实体场馆只标注已核验赛事阶段。' if name else
             '具体实体场馆尚未核验，不显示虚构馆名或大型观众场景。')
