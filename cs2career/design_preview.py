"""Isolated, seeded UI fixture; deliberately NOT a playability regression.

Uses the real tournament/match engine to create readable completed fixtures.
Server blocks non-cosmetic commands. No installed CS2 files are inspected.
"""
import json
import random
from copy import deepcopy
from .application import ApplicationState
from .career import Career
from .league import Season, formats, awards
from .engine.match import RNG, play_series
from .world import MAPS


def fixture():
    random.seed(20260910)
    RNG.seed(20260910)
    season, career = Season(2026, '2026'), Career()
    # Skip persistent writes until an isolated ApplicationState is assembled.
    career.save = lambda: None
    team = next(t for t in season.teams if t['name'] == 'Vitality')
    career.create({'era': '2026', 'mode': 'join', 'team_id': team['id'], 'replace': 'ropz', 'role': 'lurk'}, season)
    season.career = career
    season.try_ingest_pending_cs2 = lambda: ''
    season.date = career.current_date = '2026-02-28'
    selected = [team] + [t for t in season.ranked() if t is not team][:15]
    by_name = {t['name']: t for t in season.teams}
    demos = []
    for fmt in ('single_elim', 'gsl_playoff', 'swiss_playoff'):
        ev = deepcopy(season.events[0])
        ev.update(id=f'design-{fmt}', name={'single_elim':'Career Invitational · 单败邀请赛','gsl_playoff':'Career Groups · GSL 小组赛','swiss_playoff':'Career Open · 瑞士轮公开赛'}[fmt],
                  short='DESIGN CUP', format=fmt, resolved_format=fmt, status='live', matches=[], type='t1',
                  size=8 if fmt=='single_elim' else 16,
                  dates=[f'2026-02-{i:02d}' for i in range(1, 20)], prize=250000, vrs_weight=1)
        field = [t['name'] for t in selected[:8 if fmt=='single_elim' else 16]]
        ev['matches'] = formats.open_event(ev, field)
        if ev['resolved_format'] != fmt:
            raise RuntimeError(f'Preview format unexpectedly fell back: {fmt}')
        for _ in range(30):
            for match in ev['matches']:
                if match['played']:
                    continue
                a, b = by_name[match['team_a']], by_name[match['team_b']]
                match.update(play_series(a, b, MAPS, match['stage'], match['best_of']))
                match['played'] = True
                season._book_stats(ev, match, a, b)
            if formats.is_complete(ev):
                break
            ev['matches'].extend(formats.advance_event(ev))
        else:
            raise RuntimeError('Preview tournament failed to finish')
        ev['status'], ev['champion'] = 'done', formats.champion_of(ev)
        ev['champion_roster'] = [p['name'] for p in by_name[ev['champion']]['players']]
        ev['awards'] = awards.event_awards(ev, season.player_event.get(ev['id'], {}))
        demos.append(ev)
    season.events = demos + [ev for ev in season.events if ev['dates'][0] > season.date]
    career.story_queue = []
    career.real_skins = False
    career.steam_id = ''
    career.buy_skin('ak-redline')
    career.buy_skin('awp-asiimov')
    state = ApplicationState.__new__(ApplicationState)
    state.season, state.career = season, career
    # Re-enable persistence only to the save root selected BEFORE imports.
    del career.save
    return state


def run(server_only=False):
    state = fixture()
    state.persist()
    if server_only:
        from .web.server import create_server
        server = create_server(state)
        server.preview = True
        print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}/?token={server.token}'}, ensure_ascii=False), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    else:
        from .desktop.webview_app import run as open_window
        open_window(state, preview=True)
