"""Focused isolated career match/settings/tactics/quick HTTP verification.

All output is in an explicitly new D/E folder. No actual CS2 process starts;
only process discovery, start_match and the result-file provider are mocked.
Calendar, manual veto preferences, conversion, stats and rewards use core code.
"""
from copy import copy, deepcopy
from datetime import datetime, timezone, timedelta
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import threading
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.career3d_service import isolate, handler_class, DEMO_SEED


def run(folder):
    isolate(folder / 'data')
    def audit(event, args):
        if event not in ('open', 'os.scandir') or not args or not isinstance(args[0], (str, Path)):
            return
        target = Path(args[0]).resolve()
        if any(target == base or target.is_relative_to(base) for base in (ROOT / 'save', ROOT / 'extensions')):
            raise RuntimeError('Test forbids official save/extension access')
    sys.addaudithook(audit)
    from cs2career.application import ApplicationState
    from cs2career.web.server import create_server
    from cs2career.cs2 import launch
    from cs2career.league import season as season_module
    from cs2career.engine.match import RNG
    from cs2career.career import skins
    from tools import career3d_activities as activities, career3d_matches as matches
    random.seed(DEMO_SEED)
    RNG.seed(DEMO_SEED)
    state = ApplicationState()
    payload = dict(era='2026', mode='create', origin='academy', name='Career3D',
                   org='Morning Academy', region='AS', role='rifle')
    state.create_career(payload)
    fake = folder / 'fixtures'
    csgo, steam, mod = fake / 'CS2' / 'game' / 'csgo', fake / 'steam.exe', fake / 'mod'
    steam.parent.mkdir(parents=True)
    steam.write_bytes(b'test executable, never run')
    mod.mkdir()
    for name in ('metamod', 'counterstrikesharp', 'BotHider'):
        (csgo / 'addons' / name).mkdir(parents=True)
    for name in ('CareerMatch', 'BotBuy'):
        plugin = csgo / 'addons' / 'counterstrikesharp' / 'plugins' / name
        plugin.mkdir(parents=True)
        (plugin / (name + '.dll')).write_bytes(b'test plugin, never loaded')
        (plugin / (name + '.deps.json')).write_text('{}', encoding='utf-8')
    server = create_server(state, port=0)
    server.RequestHandlerClass, server.game_disabled, server.display_hour = handler_class(), True, 8
    server.RequestHandlerClass.log_message = lambda *_args: None
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    returned = {'raw': {'status': 'none'}}
    process = {'running': False}
    starts, checks = [], []
    def api(path, body=None, expected=200):
        req = Request(f'http://127.0.0.1:{server.server_port}' + path,
                      None if body is None else json.dumps(body).encode(),
                      {'X-Career-Token': server.token, 'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=30) as response:
                code, result = response.status, json.loads(response.read())
        except HTTPError as exc:
            code, result = exc.code, json.loads(exc.read())
        assert code == expected, (path, code, result)
        return result
    def context():
        return api('/api/3d/context')
    def command(path, **body):
        return api('/api/3d/' + path, {'revision': context()['calendar']['revision'], **body})
    def hashes(base=None):
        base = base or folder
        return {str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in base.rglob('*') if p.is_file()}
    def ack():
        for _ in range(50):
            stories = context()['stories']
            if not stories:
                return
            row = stories[0]
            command('story', id=row['id'], choice=(row['choices'][0]['id'] if row['choices'] else ''))
        raise AssertionError('Story chain did not end')
    def due():
        for _ in range(35):
            ack()
            ctx = context()
            if ctx.get('nextmatch') and ctx['nextmatch']['due']:
                return ctx['nextmatch']['id']
            events = {e['id']: e for e in ctx['calendar_events']}
            if not ctx.get('nextmatch'):
                invitations = [r for r in ctx['inbox'] if r['kind'] == 'invite' and r['status'] == 'open'
                               and r.get('event_id') in events]
                if invitations:
                    selected = min(invitations, key=lambda r: events[r['event_id']]['date'])
                    command('mail/accept', id=selected['id'])
                    target = events[selected['event_id']]['end_date']
                else:
                    registered = [e for e in ctx['calendar_events'] if e['registered'] and not e['played']]
                    assert registered, 'No normal career invitations or registrations available'
                    target = min(registered, key=lambda e: e['date'])['end_date']
            else:
                target = events[ctx['nextmatch']['event_id']]['end_date']
            command('calendar', target_date=target, request_id=uuid4().hex)
        raise AssertionError('Normal calendar never reached player fixture')
    def prepare(ident):
        for _ in range(20):
            response = command('match/preflight', match_id=ident)
            if response['context']['stories']:
                ack()
            else:
                return response['preflight']
        raise AssertionError('Match preflight stayed gated')
    def start(*args, **kwargs):
        cfg = launch.settings()
        launch._copy_career_match(csgo, mod)
        launch._copy_botbuy_patch(csgo)
        launch.install_skins_plugin(csgo, args[6] if len(args) > 6 else kwargs.get('career'))
        request = launch.build_request(*args[:5])
        # prepare_game's normal profile generation publishes these same nine
        # identities; the start boundary replacement performs no VPK writes.
        request['bots'] = deepcopy(request['ct']['players'] + request['t']['players'])
        starts.append({'request': deepcopy(request), 'settings': deepcopy(cfg)})
        return {'msg': 'Mock CS2 start; no game launched.', 'match': request}
    def closed(*_args):
        if process['running']:
            raise ValueError('Mock CS2 running')
    with patch.object(activities, '_running_cs2', side_effect=lambda: process['running']), \
         patch.object(launch, 'require_cs2_closed', side_effect=closed), \
         patch.object(launch, 'start_match', side_effect=start), \
         patch.object(matches, '_peek', side_effect=lambda *_args: deepcopy(returned['raw'])), \
         patch.object(skins, 'sync_live', side_effect=AssertionError('Unexpected cosmetic game write')):
        try:
            initial = context()
            before = hashes()
            assert not initial['awards']['ready'] and initial['awards']['top3'] == []
            assert len(initial['awards']['attendees']) == 50
            for _ in range(3):
                context()
                api('/api/3d/settings')
                api('/api/3d/ceremony')
                api('/api/3d/tactics?map=de_nuke')
                api('/api/3d/match/preflight')
                api('/api/3d/match/status')
            assert hashes() == before
            checks.append('GETs are pure; no awards before finalized year; audience uses 50 current top10 players')

            revision = initial['calendar']['revision']
            cfg = {'steam_exe': str(steam), 'csgo_path': str(csgo), 'mod_source_path': str(mod),
                   'difficulty': 'Low', 'skin_inspect_enabled': True}
            response = command('settings', settings=cfg, real_skins=False, steam_id='')
            assert api('/api/3d/settings')['settings']['skin_inspect_enabled'] is True
            assert response['settings']['difficulty'] == 'Low'
            fixtures = hashes(fake)
            api('/api/3d/settings', {'revision': revision, 'settings': {'difficulty': 'High'}}, expected=400)
            command('settings', settings={'difficulty': 'High'})
            assert hashes(fake) == fixtures
            library = api('/api/3d/tactics?map=de_nuke')
            assert Path(library['map_meta']['image_path']).is_file()
            assert len(library['map_meta']['layers']) >= 2
            tactic = {'id': 'career3d-probe', 'name': 'Verification route', 'side': 'ct',
                      'slots': [{'slot': n, 'steps': []} for n in range(1, 6)]}
            command('tactics/save', map='de_nuke', tactic=tactic)
            assert api('/api/3d/tactics?map=de_nuke')['tactics'][-1] == tactic
            bad = deepcopy(tactic)
            bad['slots'][1]['slot'] = 1
            before = hashes()
            api('/api/3d/tactics/save', {'revision': context()['calendar']['revision'], 'map': 'de_nuke', 'tactic': bad}, expected=400)
            assert hashes() == before and hashes(fake) == fixtures
            checks.append('independent atomic settings retain boolean options; pure original tactics validation/layers; no game files changed')

            ident = due()
            before = hashes()
            api('/api/3d/match/preflight?id=' + quote(ident))
            assert hashes() == before
            preflight = prepare(ident)
            assert preflight['phase'] == 'veto' and not preflight['veto']['complete']
            turn = preflight['veto']['turn']
            assert turn['mine']
            chosen = preflight['veto']['available'][-1]
            preflight = command('match/veto', match_id=ident, map=chosen)['preflight']
            assert any(row['map'] == chosen and row['team'] == turn['team'] for row in preflight['veto']['steps'])
            preflight = command('match/autoveto', match_id=ident)['preflight']
            assert preflight['veto']['complete'] and len(preflight['veto']['order']) == preflight['best_of']
            assert len({r['map'] for r in preflight['veto']['steps']}) == len(preflight['veto']['steps'])
            for _ in range(20):
                response = command('match/simulate', match_id=ident, request_id=uuid4().hex)
                if response.get('result', {}).get('played'):
                    break
                ack()
            else:
                raise AssertionError('Simulation never completed')
            report = response['result']
            assert report['data_complete'] and len(report['totals']) == 10
            assert all(row['data_complete'] and sum(len(lines) for lines in row['players'].values()) == 10 for row in report['maps'])
            assert len(response['reveal']['maps']) <= len(report['maps'])
            for revealed in response['reveal']['maps']:
                assert revealed['round_stats_available'] and revealed['round_damage_available']
                assert len(revealed['round_frames']) == len(revealed['rounds'])
                assert all(len(frame['players']) == 10 for frame in revealed['round_frames'])
                final = {row['player_id']: row for row in revealed['round_frames'][-1]['players']}
                saved = report['maps'][revealed['index']]
                for row in [p for team in saved['players'].values() for p in team]:
                    assert all(row[key] == final[row['player_id']][key] for key in ('k', 'd', 'a', 'damage', 'kast_rounds', 'adr', 'kast', 'rating'))
            (folder / 'match-projection.json').write_text(json.dumps(response, ensure_ascii=False), encoding='utf-8')
            checks.append('actual simulated command projects exact evolving ten-person K/D/A/ADR/KAST/Rating without changing saved ledgers')
            before = hashes()
            replay = api('/api/3d/match/simulate', {'match_id': ident, 'revision': -1})
            assert replay['replayed'] and replay['result'] == report and hashes() == before
            checks.append('manual BP preserves chosen map/opponent preferences; saved ten-player maps/totals and repeat simulation never resettle')

            ident = due()
            prepare(ident)
            command('match/autoveto', match_id=ident)
            process['running'] = True
            api('/api/3d/match/launch', {'match_id': ident, 'revision': context()['calendar']['revision']}, expected=400)
            process['running'] = False
            for map_index in range(5):
                returned['raw'] = {'status': 'none'}
                for _ in range(20):
                    launched = command('match/launch', match_id=ident, side='ct')
                    if launched.get('status') == 'waiting':
                        break
                    ack()
                else:
                    raise AssertionError('Real launch remained gated')
                ev, match = state.season.find_match(ident)
                session = deepcopy(match['cs2_session'])
                assert session and launched['connection']['phase'] == 'launched'
                before = hashes()
                status = api('/api/3d/match/status?id=' + quote(ident))
                assert status['can_collect'] and not status['result_ready'] and hashes() == before
                assert context()['match_preflight']['session_pending']
                pending_date = context()['date']
                assert command('calendar', target_date=pending_date, request_id=uuid4().hex)['status'] == 'paused'
                api('/api/3d/ladder/matchmake', {'revision': context()['ladder']['revision']}, expected=400)
                api('/api/3d/attr', {'revision': context()['calendar']['revision'], 'key': 'firepower'}, expected=400)
                api('/api/3d/settings', {'revision': context()['calendar']['revision'], 'settings': {'difficulty': 'Low'}}, expected=400)
                roster_rejection = api('/api/3d/transfers/release', {'revision': context()['calendar']['revision'],
                    'player_id': context()['team']['roster'][1]['id']}, expected=400)
                assert '回传' in roster_rejection['msg']
                replay_launch = command('match/launch', match_id=ident, side='ct')
                assert replay_launch['status'] == 'waiting' and replay_launch['replayed']
                teams = [state.career.my_team(state.season.teams), next(t for t in state.season.teams if t['name'] == session['opp'])]
                players = [{'player_id': p['player_id'], 'name': p['name'], 'team': 'ct' if n == 0 else 't',
                            'kills': 10, 'deaths': 10, 'assists': 2, 'damage': 1300, 'kast': .65,
                            'survived_rounds': 10, 'opening_kills': 1, 'opening_deaths': 1, 'traded_deaths': 1}
                           for n, team in enumerate(teams) for p in team['players']]
                raw = dict(schema_version=2, status='finished', complete=True, map=session['cs2_map'],
                           request_nonce=session['nonce'], ct_name=teams[0]['name'], t_name=teams[1]['name'],
                           ct_score=13, t_score=7, winner='ct', players=players,
                           ended_at=(datetime.now(timezone.utc) + timedelta(seconds=map_index)).strftime('%Y-%m-%dT%H:%M:%SZ'))
                wrong = {**raw, 'request_nonce': 'wrong'}
                assert command('match/collect', match_id=ident, result=wrong)['status'] == 'waiting'
                assert len(match['maps']) == map_index
                incomplete = {**raw, 'players': players[:-1]}
                assert command('match/collect', match_id=ident, result=incomplete)['status'] == 'waiting'
                returned['raw'] = raw
                before = hashes()
                ready_status = api('/api/3d/match/status?id=' + quote(ident))
                assert ready_status['result_ready'] and hashes() == before, ready_status
                rid = uuid4().hex
                collected = command('match/collect', match_id=ident, request_id=rid)
                assert collected['result']['data_complete'] and len(match['maps']) == map_index + 1
                assert all(row['source'] == 'cs2' for row in collected['result']['maps'])
                before = hashes()
                replay = api('/api/3d/match/collect', {'match_id': ident, 'request_id': rid, 'revision': -1})
                assert replay['replayed'] and replay['result'] == collected['result'] and hashes() == before
                recovered = api('/api/3d/match/collect', {'match_id': ident, 'revision': -1})
                assert recovered['replayed'] and recovered['result'] == collected['result'] and hashes() == before
                if match.get('played'):
                    break
                ack()
            assert match['played'] and hashes(fake) == fixtures
            assert not context()['match_preflight']['session_pending']
            checks.append('core career start/session/result conversion reused; nonce/incomplete rejected; game pending freezes career/ladder; map/series settle once without DLL copies')

            ack()
            with server.state_lock:
                state.create_career(payload)
            ack()
            command('season/mode', year=state.season.year, quick_mode=True)
            initial_year = state.season.year
            played = False
            for _ in range(70):
                rid = uuid4().hex
                result = command('season/run', request_id=rid, max_steps=1)
                before = hashes()
                replay = api('/api/3d/season/run', {'revision': -1, 'request_id': rid, 'max_steps': 1})
                assert replay['replayed'] and replay.get('auto_step') == result.get('auto_step') and hashes() == before
                assert state.season.year == initial_year
                if result.get('result', {}).get('played'):
                    assert result['result']['data_complete'] and result['reveal']['match_id'] == result['result']['match_id']
                    assert all(row['round_stats_available'] and row['round_damage_available'] for row in result['reveal']['maps'])
                    played = True
                    break
                ack()
            assert played
            ack()
            with server.state_lock:
                # An explicit window fixture verifies the resume adapter only;
                # no Major results, dates, awards or choices are invented.
                key = 'verification-break:' + str(initial_year)
                state.career.incident_state.setdefault('story_timing', {})['windows'] = [
                    {'key': key, 'event': 'Resume verification', 'start': state.season.date, 'until': state.season.date}]
                state.persist()
            ack()
            held_date = state.season.date
            held = command('season/run', request_id=uuid4().hex, max_steps=24)
            assert held['status'] == 'paused' and held['quick']['phase'] == 'break' and state.season.date == held_date
            before = hashes()
            api('/api/3d/season/resume', {'revision': context()['calendar']['revision'], 'break_key': 'stale'}, expected=400)
            assert hashes() == before
            rid = uuid4().hex
            resumed = command('season/resume', break_key=key, request_id=rid)
            assert resumed['quick']['break_ack']
            before = hashes()
            repeated = api('/api/3d/season/resume', {'revision': -1, 'break_key': key, 'request_id': rid})
            assert repeated['replayed'] and hashes() == before
            checks.append('quick pause retains date; stale break rejected; explicit matching break resume replays without another write')
            # A legitimate due fixture is promoted to a final solely as a gate
            # fixture. No result is injected: ordinary runner must stop first.
            ident = due()
            with server.state_lock:
                ev, match = state.season.find_match(ident)
                match['stage'] = 'GF'
                state.career.assist['tournament'] = {}
                state.persist()
            ack()
            decision = command('season/run', request_id=uuid4().hex, max_steps=24)
            assert decision['status'] == 'decision' and not match.get('played') and not match.get('maps')
            assert decision['quick']['phase'] == 'story' and context()['stories']
            api('/api/3d/season/mode', {'revision': context()['calendar']['revision'], 'year': initial_year - 1, 'quick_mode': False}, expected=400)
            checks.append('bounded ordinary quick runner includes complete played result/reveal; receipts prevent retries; stops before finals/story; never rolls year automatically')

            with server.state_lock:
                state.career.story_queue.clear()
                state.season.roll_year()
                state.persist()
            annual = api('/api/3d/ceremony?year=' + str(initial_year))['awards']
            assert annual['finalized'] and annual['top3'] == [{**row, 'name': row.get('player', ''),
                'player_id': row.get('player_id') or next((p['player_id'] for t in state.season.teams for p in t['players'] if p['name'] == row['player']), '')}
                for row in state.season.top20[str(initial_year)][:3]]
            assert annual['ready'] == bool(state.season.top20[str(initial_year)])
            checks.append('ceremony is a projection of actual roll_year table, including truthful insufficient-sample empty state')
            probe = copy(state)
            probe.season = copy(state.season)
            probe.season.top20 = {'2000': [{'rank': 1, 'player': state.career.player_name,
                'player_id': 'different-player-with-same-name', 'team': 'Identity fixture'}]}
            before = hashes()
            assert matches.ceremony_context(probe, 2000)['player_rank'] is None and hashes() == before
            checks.append('private award identity fixture cannot assign a same-name different-ID winner to the human')
        finally:
            server.shutdown()
            thread.join(3)
            server.server_close()
            state.persist()
    return {'ok': True, 'actual_cs2_started': False, 'actual_plugins_modified': False,
            'official_saves_accessed': False, 'mocked_boundaries': ['CS2 process discovery', 'start_match', 'result-file provider'],
            'fixtures': ['promoted due fixture stage to GF to verify final gate', 'synthetic ten-player raw CS2 return',
                         'explicit offseason window to verify keyed resume'],
            'checks': checks, 'real_handoff_mock_starts': len(starts), 'simulated_match_id': report['match_id']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    target = args.output_dir.expanduser().resolve()
    if not args.output_dir.is_absolute() or target.exists() or target.drive.upper() not in ('D:', 'E:'):
        parser.error('Select a new explicit D:/ or E:/ verification directory')
    result = run(target)
    (target / 'career-matches-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
