"""Isolated custom Arena HTTP checks; no real CS2, DLL install or live saves."""
from copy import deepcopy
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
    protected = (ROOT / 'save', ROOT / 'extensions', Path('E:/CS2CareerTools/Career3DRedesign/runtime/career'))
    def audit(event, args):
        if event == 'subprocess.Popen':
            raise RuntimeError('Custom verification never starts external processes')
        if event not in ('open', 'os.scandir') or not args or not isinstance(args[0], (str, Path)):
            return
        target = Path(args[0]).resolve()
        if any(target == base or target.is_relative_to(base) for base in protected):
            raise RuntimeError('Custom verification forbids official/deployed career access')
    sys.addaudithook(audit)
    from cs2career.application import ApplicationState
    from cs2career.web.server import create_server
    from cs2career.arena import Arena
    from cs2career.engine.match import RNG
    from cs2career.cs2 import launch
    from cs2career.cs2.profiles import expected_bot_count
    from cs2career.cs2.natural_behavior import configure_match
    from cs2career.world.ability import playing_ability
    from cs2career import cs2, tactics
    from tools import career3d_activities as activities
    random.seed(DEMO_SEED)
    RNG.seed(DEMO_SEED)
    state = ApplicationState()
    state.create_career(dict(era='2026', mode='create', origin='academy', name='CustomQA',
                            org='Custom QA Academy', region='AS', role='rifle'))
    fixture = folder / 'fixtures'
    csgo, mod, steam = fixture / 'CS2' / 'game' / 'csgo', fixture / 'mod', fixture / 'steam.exe'
    fixture.mkdir()
    steam.write_bytes(b'isolated dummy executable, never run')
    mod.mkdir()
    for name in ('metamod', 'counterstrikesharp', 'BotHider'):
        (csgo / 'addons' / name).mkdir(parents=True)
    for name in ('CareerMatch', 'BotBuy'):
        plugin = csgo / 'addons' / 'counterstrikesharp' / 'plugins' / name
        plugin.mkdir(parents=True)
        (plugin / (name + '.dll')).write_bytes(b'isolated dummy plugin, never loaded')
        (plugin / (name + '.deps.json')).write_text('{}', encoding='utf-8')
    config = {**launch.DEFAULTS, 'steam_exe': str(steam), 'csgo_path': str(csgo),
              'mod_source_path': str(mod), 'bot_movement': 'natural'}
    launch.SETTINGS_PATH.write_text(json.dumps(config), encoding='utf-8')
    server = create_server(state, port=0)
    server.RequestHandlerClass, server.game_disabled, server.display_hour = handler_class(), True, 8
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    checks, preparations = [], []
    process = dict(running=False, unknown=False)
    returned = dict(raw={'status': 'none'})
    launch_failure = dict(enabled=False)

    def api(path, body=None, expected=200, token=True):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['X-Career-Token'] = server.token
        req = Request(f'http://127.0.0.1:{server.server_port}' + path,
                      None if body is None else json.dumps(body).encode(), headers)
        try:
            with urlopen(req, timeout=25) as response:
                status, value = response.status, json.loads(response.read())
        except HTTPError as exc:
            status, value = exc.code, json.loads(exc.read())
        assert status == expected, (path, status, value)
        return value

    def context():
        return api('/api/3d/context')

    def command(action, expected=200, **body):
        return api('/api/3d/custom/' + action, {'revision':state.arena.data['revision'], **body}, expected)

    def hashes():
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (folder / 'data' / 'save').glob('*.json')}

    def career_facts():
        return deepcopy((state.season.date, state.season.teams, state.career.money, state.career.attr_points,
                         state.career.team_id, state.career.role, state.career.training_session, state.career.assist,
                         state.career.inbox, state.career.story_queue))

    def running():
        if process['unknown']:
            raise RuntimeError('fixture: cannot inspect CS2 process')
        return process['running']

    def closed(*_args):
        if running():
            raise ValueError('fixture: CS2 is still running')

    def prepare(game, _mod, request, options, teams, career):
        assert game == csgo and all(len(team['players']) == 5 for team in teams)
        count = expected_bot_count(request)
        # Only process launch/file preparation are substituted. Original Arena,
        # request identities, natural settings and tactical library remain real.
        launch._copy_career_match(game, _mod)
        launch._copy_botbuy_patch(game)
        assert launch.install_skins_plugin(game, career) == 0
        configure_match(request, options.get('bot_movement', 'classic'))
        playbook = tactics.load_library(tactics.canonical_map(request['map']))
        launch._deploy_tactical_playbook(game, playbook)
        request['bot_profile'] = {'count': count, 'short_hash': 'isolated-preparation'}
        preparations.append(dict(request=deepcopy(request), difficulty=options['difficulty'],
                                 playbook=deepcopy(playbook), inventory=deepcopy(career.inventory)))

    def start_process(_exe):
        if launch_failure['enabled']:
            raise OSError('fixture: launch failed, no actual process started')
        return 'launched'

    def raw_for(lobby):
        return dict(schema_version=2, status='finished', complete=True, request_nonce=lobby['nonce'],
                    map='de_' + lobby['map'], ended_at='2099-01-01T10:00:00Z', ct_score=13, t_score=6,
                    identity_bindings={str(i): pid for i, pid in enumerate(lobby['selection'])},
                    players=[dict(player_id=pid, name=p['name'], team='ct' if pid in lobby[lobby['ct']] else 't',
                                  kills=10, deaths=10, assists=3, damage=1000, kast=.7, survived_rounds=9,
                                  opening_kills=1, opening_deaths=1) for pid, p in lobby['roster'].items()])

    with patch.object(activities, '_running_cs2', side_effect=running), \
         patch.object(launch, 'require_cs2_closed', side_effect=closed), \
         patch.object(launch, 'prepare_game', side_effect=prepare), \
         patch.object(launch, 'launch_cs2', side_effect=start_process), \
         patch.object(cs2, 'read_result', side_effect=lambda _nonce: deepcopy(returned['raw'])), \
         patch.object(launch, 'install_mod', side_effect=AssertionError('Unexpected mod installation')):
        try:
            baseline = career_facts()
            catalog = state.arena.catalog(state, 'custom')
            ids = [row['player_id'] for row in catalog[:10]]
            before, arena_before = hashes(), deepcopy(state.arena.data)
            assert api('/api/3d/custom/catalog')['rows'] == catalog[:20]
            assert api('/api/3d/custom/catalog?page=2&page_size=5')['rows'] == catalog[5:10]
            exact = api('/api/3d/custom/catalog?search=' + ids[0])
            assert exact['total'] == 1 and exact['rows'][0]['player_id'] == ids[0]
            for query in ('page=0', 'page=no', 'page_size=51', 'search=' + 'x' * 81):
                api('/api/3d/custom/catalog?' + query, expected=400)
            for human in ('', ids[9]):
                recommendation = command('recommend', human_id=human)
                assert recommendation['read_only'] and len(set(recommendation['players'])) == 10
                assert [row['player_id'] for row in recommendation['rows']] == recommendation['players']
                if human:
                    assert human in recommendation['players']
            command('recommend', human_id='missing', expected=400)
            api('/api/3d/custom/status')
            assert before == hashes() and arena_before == state.arena.data and baseline == career_facts()
            checks.append('bounded catalog/search and original recommendation/status are read-only, including career/arena memory and files')

            before = hashes()
            for patch_body in ({'players': ids[:9]}, {'players': ids[:9] + [ids[0]]},
                               {'players': ids[:9] + ['missing']}, {'map': 'unknown'},
                               {'ct': 'ct'}, {'human_id': 'missing'}, {'revision': -1}):
                command('create', expected=400, **{'players':ids, **patch_body})
            assert before == hashes() and state.arena.data['lobby'] is None
            created = command('create', players=ids, map='mirage', ct='b', human_id='')
            lobby = state.arena.data['lobby']
            lid = lobby['id']
            assert lobby['mode'] == 'custom' and lobby['phase'] == 'ready' and lobby['map'] == 'mirage' and lobby['ct'] == 'b'
            assert lobby['a'] == ids[:5] and lobby['b'] == ids[5:] and len(lobby['roster']) == 10
            assert created['context']['custom']['lobby']['observer'] is True
            readonly = created['context']['custom']['rts_rosters']
            assert readonly['read_only'] and readonly['map'] == 'de_mirage'
            assert [card['id'] for card in readonly['ct']] == ids[5:]
            assert [card['id'] for card in readonly['t']] == ids[:5]
            for side in ('ct', 't'):
                for card in readonly[side]:
                    original_card = lobby['roster'][card['id']]
                    assert card['role'] == original_card['role'] and card['ability'] == playing_ability(original_card)
                    for skill, axis in readonly['skills_source'].items():
                        assert card['skills'][skill] == original_card['stats'][axis]
            assert Arena(state.arena.path).data == state.arena.data
            before = hashes()
            api('/api/3d/ladder/matchmake', {'revision':state.arena.data['revision']}, expected=400)
            api('/api/3d/ladder/cancel', {'revision':state.arena.data['revision']}, expected=400)
            for action in ('configure', 'cancel', 'simulate', 'launch', 'collect'):
                command(action, lobby_id='wrong', map='mirage', ct='b', human_id='', expected=400)
            assert before == hashes()
            assert api('/api/3d/ladder/status')['status'] == 'blocked'
            checks.append('prevalidated ten stable IDs preserve original A/B teams; shared custom/rank room is mutually exclusive and cross-mode writes are rejected')

            launch_failure['enabled'] = True
            with patch.object(state.arena, 'require_rank_identity', side_effect=AssertionError('Rank identity applied to custom')):
                failed = command('launch', lobby_id=lid, difficulty='High')
            assert failed['status'] == 'failed' and failed['connection']['can_retry']
            lobby = state.arena.data['lobby']
            nonce, frozen_roster = lobby['nonce'], deepcopy(lobby['roster'])
            first = preparations[-1]
            assert first['request']['observer'] and first['request']['human_team'] == 'spectator'
            assert first['request']['quota'] == 10 and expected_bot_count(first['request']) == 10
            assert first['request']['human_player_id'] == '' and first['difficulty'] == 'High'
            assert first['request']['movement_style']['requested'] == launch._clean(deepcopy(config))['bot_movement']
            assert first['request']['movement_style']['active'] == 'classic'
            assert first['playbook'] == tactics.load_library('de_mirage')
            pending_before = hashes()
            command('configure', lobby_id=lid, map='nuke', ct='a', human_id=ids[0], expected=400)
            command('create', players=ids, expected=400)
            command('simulate', lobby_id=lid, expected=400)
            command('launch', lobby_id=lid, difficulty='Low', expected=400)
            process['running'] = True
            command('cancel', lobby_id=lid, expected=400)
            command('launch', lobby_id=lid, expected=400)
            process.update(running=False, unknown=True)
            command('cancel', lobby_id=lid, expected=500)
            command('launch', lobby_id=lid, expected=500)
            process['unknown'] = False
            assert pending_before == hashes()
            launch_failure['enabled'] = False
            with patch.object(state.arena, 'require_rank_identity', side_effect=AssertionError('Rank identity applied to custom')):
                started = command('launch', lobby_id=lid, difficulty='High')
            assert started['status'] == 'waiting' and state.arena.data['lobby']['phase'] == 'launched'
            assert state.arena.data['lobby']['nonce'] == nonce and state.arena.data['lobby']['roster'] == frozen_roster
            assert preparations[-1] == first
            checks.append('original observer request has ten Bot identities; launch failure/retry freezes nonce/roster/difficulty and retains original natural movement/tactical playbook without applying ranked identity or installing DLLs')

            lobby = state.arena.data['lobby']
            raw = raw_for(lobby)
            ladder_before = deepcopy(state.arena.data['ladder'])
            result_file = launch.plugin_dir(csgo) / 'match_result.json'
            for invalid in (dict(raw, request_nonce='wrong'), dict(raw, players=raw['players'][:9])):
                returned['raw'] = invalid
                result_file.write_text(json.dumps(invalid), encoding='utf-8')
                before = hashes()
                waiting = command('collect', lobby_id=lid)
                assert waiting['status'] == 'waiting' and waiting['replayed'] and state.arena.pending
                assert before == hashes()
            returned['raw'] = raw
            result_file.write_text(json.dumps(raw), encoding='utf-8')
            before = hashes()
            assert api('/api/3d/custom/status')['result_ready']
            assert hashes() == before and state.arena.pending
            done = command('collect', lobby_id=lid)
            assert done['status'] == 'collected' and done['result']['mode'] == 'custom' and done['result']['changes'] == {}
            assert done['result']['map']['source'] == 'cs2' and done['result']['map']['winner'] == 'Team B'
            assert sum(len(rows) for rows in done['result']['map']['players'].values()) == 10
            before = hashes()
            replay = command('collect', lobby_id=lid, revision=-1)
            assert replay['replayed'] and replay['result'] == done['result'] and before == hashes()
            assert state.arena.data['ladder'] == ladder_before and baseline == career_facts()
            command('simulate', lobby_id=lid, expected=400)
            checks.append('original nonce/full-ten/team-bound ingestion saves a real custom report once, without any Elo/date/growth/role/club changes; GET never settles results')

            command('cancel', lobby_id=lid)
            human = ids[9]
            command('create', players=ids, human_id=human)
            lid = state.arena.data['lobby']['id']
            command('configure', lobby_id=lid, map='nuke', ct='a', human_id=human)
            with patch.object(state.arena, 'require_rank_identity', side_effect=AssertionError('Rank identity applied to custom')):
                command('launch', lobby_id=lid)
            req = preparations[-1]['request']
            assert not req['observer'] and req['human_player_id'] == human and req['human_team'] == 't'
            assert expected_bot_count(req) == 9 and req['quota'] == 9
            assert set(req['human_tactical_abilities']) == {'awp', 'entry', 'lurk', 'igl', 'rifle'}
            process['running'] = True
            before = hashes()
            command('cancel', lobby_id=lid, expected=400)
            assert before == hashes()
            process['running'] = False
            command('cancel', lobby_id=lid)
            assert state.arena.data['lobby'] is None and baseline == career_facts()
            checks.append('an arbitrary selected non-career identity creates original nine-Bot control request; pending cancel requires confirmed closed CS2 and grants no rewards')

            command('create', players=ids, map='ancient', ct='b')
            lid = state.arena.data['lobby']['id']
            ladder_before, rng_before = deepcopy(state.arena.data['ladder']), RNG.getstate()
            simulated = command('simulate', lobby_id=lid)
            assert simulated['result']['changes'] == {} and simulated['result']['source'] == 'simulated'
            assert state.arena.data['ladder'] == ladder_before and RNG.getstate() == rng_before
            before = hashes()
            assert command('simulate', lobby_id=lid, revision=-1)['replayed'] and hashes() == before
            assert baseline == career_facts() and all(row['mode'] == 'custom' for row in context()['custom']['history'])
            command('cancel', lobby_id=lid)
            api('/api/3d/ladder/matchmake', {'revision':state.arena.data['revision']})
            before = hashes()
            command('create', players=ids, expected=400)
            command('cancel', lobby_id=state.arena.data['lobby']['id'], expected=400)
            assert context()['custom']['lobby'] is None and context()['custom']['shared_lobby']['mode'] == 'rank'
            assert not api('/api/3d/custom/status')['can_collect'] and hashes() == before
            api('/api/3d/ladder/cancel', {'revision':state.arena.data['revision']})
            checks.append('unrated simulation uses the existing engine with isolated RNG, exact-once report and custom-only history; custom page cannot cancel/replace a ranked room')

            state.career.training_session = {'nonce':'fixture-training'}
            before = hashes()
            command('create', players=ids, expected=400)
            assert before == hashes()
            state.career.training_session = None
            state.season.events.append(dict(id='fixture-pending-career', name='Fixture pending career', dates=[state.season.date],
                type='invite', status='live', matches=[dict(id='fixture-pending-match', date=state.season.date,
                team_a=state.season.teams[0]['name'], team_b=state.season.teams[1]['name'], best_of=3,
                stage='fixture', cs2_session={'nonce':'fixture-career'}, played=False, maps=[])]))
            command('create', players=ids, expected=400)
            state.season.events.pop()
            assert before == hashes()
            api('/api/3d/custom/catalog', expected=403, token=False)
            api('/api/3d/custom/launch', {}, expected=403, token=False)
            for name in ('CareerMatch', 'BotBuy'):
                assert (launch.plugin_dir(csgo) if name == 'CareerMatch' else csgo / 'addons' / 'counterstrikesharp' / 'plugins' / name).joinpath(name + '.dll').read_bytes() == b'isolated dummy plugin, never loaded'
            assert baseline == career_facts()
            checks.append('pending training/career real sessions and missing authentication block custom writes; existing DLL bytes remain unchanged')
        finally:
            server.shutdown()
            thread.join(3)
            server.server_close()
    return dict(ok=True, checks=checks, preparations=len(preparations), actual_cs2_started=False,
                actual_plugins_modified=False, official_or_deployed_saves_accessed=False,
                mocked_boundaries=['CS2 process diagnostic', 'game file preparation', 'actual Steam/CS2 process launch', 'result provider'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    folder = args.output_dir.resolve()
    if folder.drive.upper() not in ('D:', 'E:') or folder.exists():
        parser.error('Select a new explicitly isolated D/E directory')
    result = run(folder)
    (folder / 'custom-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
