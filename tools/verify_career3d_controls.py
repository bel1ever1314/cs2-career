"""Isolated HTTP verification of original controls; no game or official saves."""
from copy import deepcopy
from datetime import date, timedelta
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

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
            raise RuntimeError('Controls verification forbids official save/extension access')
    sys.addaudithook(audit)
    from cs2career.application import ApplicationState
    from cs2career.web.server import create_server
    from cs2career.engine.match import RNG
    from cs2career.cs2 import launch
    from cs2career import tactics
    from tools import career3d_activities
    random.seed(DEMO_SEED)
    RNG.seed(DEMO_SEED)
    state = ApplicationState()
    state.create_career(dict(era='2026', mode='create', origin='academy', name='ControlsQA',
                            org='Controls Academy', region='AS', role='rifle'))
    server = create_server(state, port=0)
    server.RequestHandlerClass, server.game_disabled, server.display_hour = handler_class(), True, 8
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    checks = []
    def api(path, body=None, expected=200):
        req = Request(f'http://127.0.0.1:{server.server_port}' + path,
                      None if body is None else json.dumps(body).encode(),
                      {'Content-Type': 'application/json', 'X-Career-Token': server.token})
        try:
            with urlopen(req, timeout=25) as response:
                status, value = response.status, json.loads(response.read())
        except HTTPError as exc:
            status, value = exc.code, json.loads(exc.read())
        assert status == expected, (path, status, value)
        return value
    def revision():
        return api('/api/3d/context')['calendar']['revision']
    def command(action, rid, **body):
        return api('/api/3d/controls/' + action, dict(revision=revision(), request_id=rid, **body))
    def hashes():
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (folder/'data'/'save').glob('*.json')}
    try:
        before = hashes()
        stamp = state.season.date
        facts = deepcopy((state.career.inbox, state.career.story_queue, state.career.assist,
                          state.career.attr_points, state.career.incident_state))
        for page in ('management', 'training', 'assistance', 'workshop'):
            assert api('/api/3d/controls/' + page)['page'] == page
        top = api('/api/3d/controls/rankings')['data']
        assert top['rows'] == state.season.top20_live()
        stats = api('/api/3d/controls/rankings?board=players')['data']
        assert len(stats['rows']) <= 20 and stats['scope'] == 'top30'
        api('/api/3d/controls/rankings?year=nonsense', expected=400)
        api('/api/3d/controls/rankings?board=invalid', expected=400)
        assert before == hashes() and stamp == state.season.date
        assert facts == (state.career.inbox, state.career.story_queue, state.career.assist,
                         state.career.attr_points, state.career.incident_state)
        checks.append('all controls GETs are bounded and leave saved and in-memory career facts unchanged')

        roster = state.career.my_team(state.season.teams)['players']
        mapping = {p['name']: p['role'] for p in roster}
        body = dict(revision=revision(), request_id='roles-request-001', roles=mapping)
        saved = api('/api/3d/controls/roles', body)
        after = hashes()
        replay = api('/api/3d/controls/roles', body)
        assert replay['replayed'] and replay['context']['calendar']['revision'] == saved['context']['calendar']['revision']
        assert after == hashes()
        api('/api/3d/controls/roles', dict(body, roles={'wrong':'awp'}), expected=400)
        api('/api/3d/controls/roles', dict(body, request_id='roles-stale-001'), expected=400)
        command('assistance', 'assist-request-001', invites={'major':'decline', 'qual':'manual'}, points='off')
        assert state.career.assist['invites'] == {'major':'decline', 'qual':'manual'}
        checks.append('original role command and invite rules persist with revision guards and receipt-safe retries')

        state.career.attr_points = 2
        state.persist()
        you = state.career.my_player(state.season.teams)
        old = float(you['stats']['firepower'])
        command('assistance', 'points-request-001', points='firepower')
        assert state.career.attr_points == 0 and float(you['stats']['firepower']) == old + 2
        command('assistance', 'points-off-request-001', points='off')
        checks.append('automatic attributes spend exactly the existing two-point budget through original spend_point')

        state.arena.data['lobby'] = {'phase':'launched'}
        frozen = hashes()
        for action, payload in [('roles', {'roles':mapping}), ('assistance', {'points':'balanced'}),
                                ('workshop/reload', {}), ('training/launch', {'opponent_id':'missing'})]:
            api('/api/3d/controls/' + action, dict(revision=revision(), **payload), expected=400)
        assert frozen == hashes()
        state.arena.data['lobby'] = None
        with patch('tools.career3d_matches.career_cs2_pending', return_value=True):
            api('/api/3d/controls/assistance', dict(revision=revision(), points='balanced'), expected=400)
        assert frozen == hashes()
        checks.append('active real ladder and career matches freeze roster, assistance, training launch and registry reload')

        # Original nonce-bound training request + complete ten-player result.
        team = state.career.my_team(state.season.teams)
        opponent = next(t for t in state.season.teams if t['id'] != team['id'])
        started, installed = [], []
        original_copy = launch._copy_career_match
        def launch_fixture(mine, target, name, code, side, teams, career, *, purpose):
            assert purpose == 'training' and mine['id'] == team['id'] and target['id'] == opponent['id']
            launch._copy_career_match(folder/'fixture_game')
            launch._copy_botbuy_patch(folder/'fixture_game')
            request = launch.build_request(mine, target, name, code, side)
            career.remember_training(request)
            started.append(request)
            return {'msg':'Isolated launch fixture', 'match':request}
        with patch.object(career3d_activities, 'config_status', return_value={'ready':True}), \
             patch.object(career3d_activities, '_running_cs2', return_value=False), \
             patch.object(career3d_activities, '_require_existing_plugin', side_effect=lambda path, name: installed.append(name) or 0), \
             patch.object(launch, 'require_cs2_closed'), patch.object(launch, 'start_match', side_effect=launch_fixture):
            command('training/launch', 'training-launch-001', opponent_id=opponent['id'], map='mirage', side='ct')
        request = started[0]
        assert installed == ['CareerMatch', 'BotBuy'] and launch._copy_career_match is original_copy
        # Pending real training is a global identity/date freeze, including
        # legacy device routes outside the new controls namespace. Supply a
        # due own-match fixture only to reach the original match adapter gate;
        # remove it before any permitted calendar persistence occurs.
        original_events = state.season.events
        fixture_match = dict(id='pending-training-career-match', date=stamp, team_a=team['name'],
                             team_b=opponent['name'], best_of=3, stage='fixture', played=False, maps=[])
        fixture_event = dict(id='pending-training-event', name='Pending training guard fixture',
                             dates=[stamp], status='live', type='invite', matches=[fixture_match])
        state.season.events = [*original_events, fixture_event]
        frozen_files = hashes()
        frozen_facts = deepcopy((state.season.date, state.season.teams, state.career.attr_points,
                                state.career.role, state.career.team_id, state.career.training_session,
                                state.career.incident_state, state.career.assist))
        try:
            context = api('/api/3d/context')
            assert context['training_pending'] and not context['personal']['growth_allowed']
            assert '训练' in context['personal']['growth_reason'] and context['quick']['block_reason']
            assert not context['transfers']['club_allowed']
            for path, payload in [
                ('settings', {'settings':{'difficulty':'High'}}),
                ('attr', {'allocations':{'firepower':1}}),
                ('season/mode', {'year':state.season.year, 'quick_mode':True}),
                ('season/run', {'max_steps':1, 'request_id':'training-guard-run-001'}),
                ('season/resume', {'break_key':'fixture-break'}),
                ('ladder/matchmake', {'mode':'rank'}),
                ('ladder/launch', {'lobby_id':'fixture-room'}),
                ('ladder/simulate', {'lobby_id':'fixture-room'}),
                ('scrim/schedule', {'opponent_id':opponent['id'], 'date':stamp, 'map':'mirage'}),
                ('scrim/simulate', {'id':'fixture-practice'}),
                ('transfers/apply', {'team_id':opponent['id'], 'role':'rifle'}),
                ('transfers/buy', {'player_id':opponent['players'][0]['player_id'], 'seller_id':opponent['id']}),
                ('controls/roles', {'roles':mapping}),
                ('controls/assistance', {'points':'balanced'}),
            ]:
                denied = api('/api/3d/' + path, dict(revision=revision(), **payload), expected=400)
                assert '训练' in denied['msg'] or path == 'settings' and '真实比赛' in denied['msg'], (path, denied['msg'])
            for action in ('preflight', 'veto', 'autoveto', 'simulate', 'launch'):
                blocked = api('/api/3d/match/' + action, dict(match_id=fixture_match['id'], map='mirage', revision=revision()))
                assert blocked['status'] == 'paused' and blocked['replayed'] and '训练' in blocked['reason']
                assert not blocked['preflight']['can_simulate'] and not blocked['preflight']['can_launch']
            assert hashes() == frozen_files
            assert frozen_facts == (state.season.date, state.season.teams, state.career.attr_points,
                                    state.career.role, state.career.team_id, state.career.training_session,
                                    state.career.incident_state, state.career.assist)
            assert not fixture_match.get('veto') and not fixture_match.get('cs2_session') and not fixture_match['maps']
        finally:
            state.season.events = original_events
        checks.append('pending real training freezes settings, attributes, season mode/run/resume, ladder, scrims, transfers and career preparation without changing date/ability/roster/files')
        paused = api('/api/3d/calendar', dict(target_date=(date.fromisoformat(stamp) + timedelta(days=1)).isoformat(),
                     revision=revision(), request_id='training-calendar-001'))
        assert paused['status'] == 'paused' and paused['reason_code'] == 'training_match' and state.season.date == stamp
        raw = dict(schema_version=2, status='finished', complete=True, request_nonce=request['nonce'],
                   map='de_mirage', ct_score=13, t_score=8, ended_at='2099-01-01T00:00:00Z',
                   players=[{'player_id':request['human_player_id'], 'team':'ct'}] +
                   [{'player_id':p['player_id'], 'team':side} for side in ('ct', 't') for p in request[side]['players']])
        with patch.object(launch, 'read_result', return_value=dict(raw, request_nonce='wrong')):
            command_body = dict(revision=revision(), request_id='training-result-001')
            api('/api/3d/controls/training/finish', command_body, expected=400)
        before_mentality = team.get('mentality', 70)
        with patch.object(launch, 'read_result', return_value=raw):
            value = api('/api/3d/controls/training/finish', command_body)
            after_mentality = team['mentality']
            assert after_mentality >= before_mentality and state.career.last_scrim == stamp and state.career.training_session is None
            again = api('/api/3d/controls/training/finish', command_body)
            assert again['replayed'] and team['mentality'] == after_mentality
        checks.append('original training rejects wrong nonce and settles one complete result once; retry does not reward twice')
        api('/api/3d/controls/training/launch', dict(revision=revision(), opponent_id=opponent['id'], map='mirage'), expected=400)
        assert not api('/api/3d/controls/training')['data']['launch_allowed']
        # A legacy/aborted pending connection can be dismissed explicitly only
        # after a positive process check says CS2 is closed.
        state.career.training_session = dict(nonce='aborted-training-001', date=stamp, map='mirage')
        old_facts = deepcopy((state.career.attr_points, state.career.last_scrim, team['mentality'], state.career.log,
                              state.season.events))
        cancel = dict(revision=revision(), request_id='training-cancel-001', nonce='aborted-training-001', confirmed=True)
        api('/api/3d/controls/training/cancel', dict(cancel, confirmed=False), expected=400)
        with patch.object(career3d_activities, '_running_cs2', return_value=True):
            api('/api/3d/controls/training/cancel', cancel, expected=400)
        with patch.object(career3d_activities, '_running_cs2', side_effect=RuntimeError('Cannot verify process')):
            api('/api/3d/controls/training/cancel', cancel, expected=400)
        assert state.career.training_session is not None
        with patch.object(career3d_activities, '_running_cs2', return_value=False):
            api('/api/3d/controls/training/cancel', cancel)
        assert state.career.training_session is None
        assert old_facts == (state.career.attr_points, state.career.last_scrim, team['mentality'], state.career.log, state.season.events)
        assert api('/api/3d/controls/training/cancel', cancel)['replayed']
        checks.append('same-day relaunch is refused; explicit cancellation requires known closed CS2 and only clears connection marker')

        command('workshop/reload', 'workshop-request-001')
        assert api('/api/3d/controls/workshop')['data']['root'] == str(folder/'data'/'extensions')
        sample = {'id':'controls_qa', 'name':'QA', 'side':'t',
                  'slots':[{'slot':i, 'steps':[]} for i in range(1, 6)]}
        tactic_body = dict(value={'map':'de_mirage', 'tactic':sample}, revision=revision(), request_id='tactics-import-001')
        imported = api('/api/3d/tactics/import', tactic_body)
        assert imported['map'] == 'de_mirage' and imported['imported_count'] == 1
        assert imported['map_meta']['image_path'] and imported['available_maps']
        replay = api('/api/3d/tactics/import', tactic_body)
        assert replay['replayed'] and tactics.load_library('de_mirage')['tactics'][-1]['id'] == 'controls_qa'
        bad = dict(tactic_body, request_id='tactics-invalid-001', revision=revision(), map='de_nuke')
        api('/api/3d/tactics/import', bad, expected=400)
        checks.append('original extension reload is isolated; tactic imports preserve multimap validation, public metadata and retry receipts')
        assert state.season.date == stamp
    finally:
        server.shutdown()
        thread.join(3)
        server.server_close()
    return dict(ok=True, checks=checks, official_saves_accessed=False, actual_cs2_started=False,
                actual_plugins_modified=False, date_advanced=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    folder = args.output_dir.resolve()
    if folder.drive.upper() not in ('D:', 'E:') or folder.exists():
        parser.error('Select a new explicitly isolated D/E directory')
    result = run(folder)
    (folder/'controls-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
