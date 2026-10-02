"""Isolated HTTP growth/skins and original Arena CS2 handoff checks.

No game is started. Only start_match/read_result/process diagnostics are mocked;
matching, identity locking, request construction, ingestion and Elo use core rules.
"""
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
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.career3d_service import isolate, handler_class, DEMO_SEED


def run(folder):
    isolate(folder / 'data')
    # Business imports must occur after isolation, never load official saves.
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
    from cs2career import cs2
    from cs2career.career import skins
    from cs2career.engine.match import RNG
    from cs2career.world.ability import ALL_AXES
    from tools import career3d_activities as activities
    random.seed(DEMO_SEED)
    RNG.seed(DEMO_SEED)
    state = ApplicationState()
    state.create_career(dict(era='2026', mode='create', origin='academy', name='Career3D',
                             org='Morning Academy', region='AS', role='rifle'))
    # Fixture resources are empty dummy files on the isolated test directory.
    fake = folder / 'fixtures'
    csgo = fake / 'CS2' / 'game' / 'csgo'
    steam, mod = fake / 'steam.exe', fake / 'mod'
    steam.parent.mkdir(parents=True)
    steam.write_bytes(b'dummy executable, not run')
    mod.mkdir()
    for name in ('metamod', 'counterstrikesharp', 'BotHider'):
        (csgo / 'addons' / name).mkdir(parents=True)
    for name in ('CareerMatch', 'BotBuy'):
        plugin = csgo / 'addons' / 'counterstrikesharp' / 'plugins' / name
        plugin.mkdir(parents=True)
        (plugin / (name + '.dll')).write_bytes(b'dummy plugin, never loaded')
        (plugin / (name + '.deps.json')).write_text('{}', encoding='utf-8')
    cfg = {**launch.DEFAULTS, 'steam_exe': str(steam), 'csgo_path': str(csgo), 'mod_source_path': str(mod)}
    launch.SETTINGS_PATH.write_text(json.dumps(cfg), encoding='utf-8')
    server = create_server(state, port=0)
    server.RequestHandlerClass, server.game_disabled, server.display_hour = handler_class(), True, 8
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    checks, starts = [], []
    process = {'running': False, 'unknown': False}
    returned = {'raw': {'status': 'none'}}
    fail_start = {'yes': True}

    def api(path, body=None, expected=200, token=True):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['X-Career-Token'] = server.token
        req = Request(f'http://127.0.0.1:{server.server_port}' + path,
                      None if body is None else json.dumps(body).encode(), headers)
        try:
            with urlopen(req, timeout=20) as response:
                status, value = response.status, json.loads(response.read())
        except HTTPError as exc:
            status, value = exc.code, json.loads(exc.read())
        assert status == expected, (path, status, value)
        return value

    def context():
        return api('/api/3d/context')

    def hashes():
        return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in folder.rglob('*') if p.is_file()}

    def skin(action, **body):
        return api('/api/3d/skins/' + action, {'revision': context()['calendar']['revision'], **body})

    def ladder(action, **body):
        info = context()['ladder']
        return api('/api/3d/ladder/' + action, {'revision': info['revision'], **body})

    def running():
        if process['unknown']:
            raise RuntimeError('测试：无法核验 CS2 进程状态')
        return process['running']

    def closed(*_args):
        if running():
            raise ValueError('测试：CS2 正在运行')

    def mock_start(*args, **kwargs):
        starts.append(dict(request=deepcopy(kwargs['request_override']), purpose=kwargs['purpose'],
                           config=launch.settings(), inventory=deepcopy(kwargs['career'].inventory),
                           equipped_ct=deepcopy(kwargs['career'].equipped_ct)))
        # These scoped checks must never copy DLLs or park plugins.
        launch._copy_career_match(csgo, mod)
        launch._copy_botbuy_patch(csgo)
        launch.install_skins_plugin(csgo, kwargs['career'])
        if fail_start['yes']:
            raise OSError('测试 Steam 启动失败；未启动任何游戏')
        return {'msg': '测试替身启动完成；未启动任何游戏'}

    with patch.object(activities, '_running_cs2', side_effect=running), \
         patch.object(launch, 'require_cs2_closed', side_effect=closed), \
         patch.object(launch, 'start_match', side_effect=mock_start), \
         patch.object(cs2, 'read_result', side_effect=lambda nonce: deepcopy(returned['raw'])), \
         patch.object(skins, 'sync_live', side_effect=AssertionError('Unexpected game cosmetic write')):
        try:
            initial = context()
            before = hashes()
            for _ in range(3):
                context()
                api('/api/3d/ladder/status')
            assert hashes() == before
            assert initial['personal']['axes'] == list(ALL_AXES)
            assert initial['personal']['attributes'].keys() == set(ALL_AXES)
            assert initial['personal']['stats']['rating'] is None
            assert initial['money'] == initial['personal']['personal_money'] == initial['skins']['personal_money']
            assert initial['team']['money'] == initial['personal']['club_money']
            checks.append('context, market and status are read-only; original eight axes and genuine empty stats')

            # Test fixture awards available points only; every allocation uses spend_point.
            state.career.attr_points = 3
            state.persist()
            now = context()
            old_attrs = now['personal']['attributes']
            old_revision = now['calendar']['revision']
            before = hashes()
            for bad in ({'allocations': {'unknown': 1}}, {'allocations': {'firepower': 4}},
                        {'allocations': {'firepower': True}}, {'revision': -1, 'allocations': {'firepower': 1}}):
                api('/api/3d/attr', {'revision': old_revision, **bad}, expected=400)
            assert hashes() == before
            result = api('/api/3d/attr', {'revision': old_revision, 'allocations': {'firepower': 1, 'utility': 1, 'command': 1}})
            assert result['context']['personal']['attr_points'] == 0
            for axis in ('firepower', 'utility', 'command'):
                assert result['context']['personal']['attributes'][axis] == old_attrs[axis] + 1
            state.career.assist['quick_mode'] = True
            state.career.attr_points = 1
            before = hashes()
            api('/api/3d/attr', {'revision': context()['calendar']['revision'], 'allocations': {'firepower': 1}}, expected=400)
            assert hashes() == before
            state.career.assist['quick_mode'] = False
            checks.append('atomic prevalidation, stale/invalid/overbudget rejection, original spend_point and quick-window gate')

            state.career.money = 200_000
            state.persist()
            shop = context()['skins']
            market = min((r for r in shop['market'] if r['slot'] == 'ak47'), key=lambda r: r['spot'])
            pocket, club = state.career.money, context()['club_money']
            bought = skin('buy', id=market['id'])['context']['skins']
            assert state.career.money == pocket - market['spot'] and context()['club_money'] == club
            item = bought['inventory'][-1]
            skin('equip', id=item['id'], side='t')
            assert context()['skins']['equipped_t']['ak47'] == item['id']
            skin('equip', id=item['id'], side='t', off=True)
            assert 'ak47' not in context()['skins']['equipped_t']
            skin('sell', id=item['id'])
            box = min(context()['skins']['cases'], key=lambda r: r['price'] + r['key'])
            skin('case', id=box['id'])
            assert context()['skins']['pending']
            skin('keep')
            skin('case', id=box['id'])
            assert context()['skins']['pending']
            skin('cash')
            assert not context()['skins']['pending'] and context()['club_money'] == club
            assert all(not r['art_path'] for r in context()['skins']['market'])
            checks.append('original buy/equip/unequip/sell/open/keep/cash business, personal wallet only, no game writes or art downloads')

            baseline = context()
            ladder('matchmake')
            for _ in range(30):
                lobby = context()['ladder']['lobby']
                if lobby['phase'] == 'ready':
                    break
                if not lobby['turn']['human']:
                    ladder('advance')
                elif lobby['phase'] == 'draft':
                    ladder('pick', player_id=next(p for p in lobby['selection'] if p not in lobby['a'] + lobby['b']))
                elif lobby['phase'] == 'veto':
                    ladder('ban', map=next(m for m in lobby['map_pool'] if m not in [r['map'] for r in lobby['bans']]))
                else:
                    ladder('side', side='ct')
            else:
                raise AssertionError('Draft did not complete')
            lid = lobby['id']
            assert lobby['human_id'] == baseline['player']['id'] and len(lobby['roster']) == 10
            assert len(lobby['a']) == len(lobby['b']) == 5
            before = hashes()
            process['unknown'] = True
            unknown = api('/api/3d/ladder/status')
            assert unknown['cs2_running'] is None and not unknown['can_launch'] and not unknown['process_known']
            api('/api/3d/ladder/launch', dict(revision=context()['ladder']['revision'], lobby_id=lid), expected=500)
            process.update(unknown=False, running=True)
            assert not api('/api/3d/ladder/status')['can_launch']
            api('/api/3d/ladder/launch', dict(revision=context()['ladder']['revision'], lobby_id=lid), expected=400)
            assert not starts and hashes() == before
            process['running'] = False
            cfg_saved = launch.SETTINGS_PATH.read_bytes()
            launch.SETTINGS_PATH.write_text('{}', encoding='utf-8')
            missing = api('/api/3d/ladder/status')
            assert not missing['config']['ready'] and not missing['can_launch']
            launch.SETTINGS_PATH.write_bytes(cfg_saved)
            checks.append('original draft/veto and stable human identity; live, unknown and missing config block generation')

            failed = ladder('launch', lobby_id=lid, difficulty='High')
            assert failed['status'] == 'failed' and failed['context']['ladder']['lobby']['phase'] == 'starting'
            l = state.arena.data['lobby']
            nonce, snapshot = l['nonce'], deepcopy(l['roster'])
            assert starts[0]['request'].get('request_nonce') == nonce or starts[0]['request'].get('nonce') == nonce
            assert starts[0]['purpose'] == 'arena' and starts[0]['config']['difficulty'] == 'High'
            pending = context()
            assert not pending['personal']['growth_allowed']
            tomorrow = (date.fromisoformat(pending['date']) + timedelta(days=1)).isoformat()
            held = api('/api/3d/calendar', dict(target_date=tomorrow, revision=pending['calendar']['revision'], request_id=uuid4().hex))
            assert held['reason_code'] == 'ladder_match' and held['actualdate'] == pending['date'] and held['steps'] == 0
            before = hashes()
            api('/api/3d/attr', dict(revision=context()['calendar']['revision'], allocations={'firepower': 1}), expected=400)
            api('/api/3d/ladder/simulate', dict(revision=context()['ladder']['revision'], lobby_id=lid), expected=400)
            state.career.story_queue.append({'id': 'test-transfer', 'kind': 'transfer', 'choices': [{'id': 'accept'}]})
            api('/api/3d/story', dict(id='test-transfer', choice='accept'), expected=400)
            state.career.story_queue.pop()
            assert hashes() == before
            assert api('/api/3d/ladder/status')['can_retry']
            fail_start['yes'] = False
            launched = ladder('launch', lobby_id=lid, difficulty='High')
            assert launched['status'] == 'waiting' and launched['context']['ladder']['lobby']['phase'] == 'launched'
            assert state.arena.data['lobby']['nonce'] == nonce and state.arena.data['lobby']['roster'] == snapshot
            assert starts[0] == starts[1]
            checks.append('original nonce persisted on start failure; retry reuses frozen identity, ten roster, difficulty and cosmetics; pending career guards')

            l = state.arena.data['lobby']
            raw = dict(schema_version=2, status='finished', complete=True, request_nonce=nonce,
                map='de_' + l['map'], ended_at='2099-01-01T10:00:00Z', ct_score=13, t_score=6,
                identity_bindings={str(i): pid for i, pid in enumerate(l['selection'])},
                players=[dict(player_id=pid, name=p['name'], team='ct' if pid in l[l['ct']] else 't',
                    kills=10, deaths=10, assists=3, damage=1000, kast=.7, survived_rounds=9,
                    opening_kills=1, opening_deaths=1) for pid, p in l['roster'].items()])
            plugin_result = launch.plugin_dir(csgo) / 'match_result.json'
            wrong = {**raw, 'request_nonce': 'wrong'}
            returned['raw'] = wrong
            plugin_result.write_text(json.dumps(wrong), encoding='utf-8')
            assert not api('/api/3d/ladder/status')['result_ready']
            waiting = ladder('collect', lobby_id=lid)
            assert waiting['status'] == 'waiting' and state.arena.pending
            returned['raw'] = {**raw, 'players': raw['players'][:9]}
            waiting = ladder('collect', lobby_id=lid)
            assert waiting['status'] == 'waiting'
            returned['raw'] = raw
            plugin_result.write_text(json.dumps(raw), encoding='utf-8')
            before = hashes()
            assert api('/api/3d/ladder/status')['result_ready']
            assert hashes() == before and state.arena.pending
            scores = sum(r['elo'] for r in state.arena.data['ladder'].values())
            done = ladder('collect', lobby_id=lid)
            assert done['status'] == 'collected' and done['result']['map']['source'] == 'cs2'
            assert sum(len(rows) for rows in done['result']['map']['players'].values()) == 10
            assert sum(r['elo'] for r in state.arena.data['ladder'].values()) == scores
            before = hashes()
            repeated = api('/api/3d/ladder/collect', dict(revision=-1, lobby_id=lid))
            assert repeated['replayed'] and repeated['result'] == done['result'] and hashes() == before
            api('/api/3d/ladder/simulate', dict(revision=context()['ladder']['revision'], lobby_id=lid), expected=400)
            current = context()
            for key in ('date', 'money', 'attr_points', 'team', 'player'):
                assert current[key] == baseline[key], key
            checks.append('GET never settles; core ingest rejects wrong nonce/incomplete ten; real report and zero-sum Elo settle exactly once without career rewards')

            for path in ('/api/cs2/settings', '/api/play', '/api/series/launch', '/api/arena/launch'):
                api(path, {}, expected=403)
            api('/api/3d/custom/launch', {}, expected=400)
            api('/api/3d/match/launch', {}, expected=400)
            api('/api/3d/ladder/launch', {}, expected=403, token=False)
            api('/api/3d/ladder/status', expected=403, token=False)
            for name in ('CareerMatch', 'BotBuy'):
                assert (csgo / 'addons' / 'counterstrikesharp' / 'plugins' / name / (name + '.dll')).read_bytes() == b'dummy plugin, never loaded'
            checks.append('session protected; ordinary game routes and unidentified custom launch denied; career requires explicit fixture; no plugin installation or replacement')
        finally:
            server.shutdown()
            thread.join(3)
            server.server_close()
            state.persist()
    return dict(ok=True, actual_cs2_started=False, actual_plugins_modified=False, official_saves_accessed=False,
                mocked_boundaries=['CS2 start_match', 'result file provider for collect', 'process read-only diagnostic'],
                checks=checks, starts=len(starts), human_id=initial['player']['id'], axes=list(ALL_AXES))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    target = args.output_dir.resolve()
    if not target.is_absolute() or target.exists():
        parser.error('Select a new explicitly isolated directory')
    result = run(target)
    (target / 'cs2-devices-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
