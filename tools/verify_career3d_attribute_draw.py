"""Isolated D/E verification of ten team draws, migration and HTTP routes."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(folder):
    from tools.career3d_service import isolate, handler_class
    data = isolate(folder / 'data')
    def audit(event, args):
        if event not in ('open', 'os.scandir') or not args or not isinstance(args[0], (str, Path)):
            return
        target = Path(args[0]).resolve()
        if any(target == base or target.is_relative_to(base) for base in (ROOT / 'save', ROOT / 'extensions')):
            raise RuntimeError('Team draw QA forbids official save/extension access')
    sys.addaudithook(audit)
    from cs2career.application import ApplicationState
    from cs2career.web.server import create_server
    from cs2career.world import build_teams, ERA_META
    from cs2career.world.ability import AXES, ability_of
    from cs2career.career.origins import origin_config, public_origins
    from cs2career.career.skins import ensure_economy
    from cs2career.league.vrs import VRS
    from tools.career3d_attribute_draw import (draw_context, draw_command, draw_options,
        source_pool, team_source_pool, selected_attributes, METADATA_NAME, _hash, _load, _save)
    from tools.career3d_start import start_command, creation_options
    state = ApplicationState()
    ensure_economy(state.career)
    state.settle()  # Explicit empty save pair, never an official/demo career.
    checks = []
    metadata = data / METADATA_NAME
    def save_hashes():
        return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (data / 'save').glob('*.json')}
    def command(action, **body):
        return draw_command(state, action, body)
    def reject(call):
        before = (save_hashes(), metadata.read_bytes() if metadata.exists() else None)
        try:
            call()
        except ValueError:
            pass
        else:
            raise AssertionError('Expected command rejection')
        assert before == (save_hashes(), metadata.read_bytes() if metadata.exists() else None)
    initial = save_hashes()
    facts = deepcopy((state.career.to_json(), state.season.date, state.season.teams))
    assert not state.career.exists and draw_context(state)['attribute_draw'] is None
    assert draw_context(state)['attribute_draw'] is None and not metadata.exists()
    assert draw_options()['max_draws'] == 10 and 'difficulties' not in draw_options()
    assert [row['id'] for row in creation_options()['origins']] == ['attribute_draw']
    assert [row['id'] for row in public_origins()] == ['street', 'academy', 'prodigy']
    checks.append('pure GET, no metadata/career writes; no difficulty; old 2D origins unchanged')

    pools, player_pools = {}, {}
    for era in ('2024', '2025', '2026'):
        world = build_teams(era)
        pool = pools[era] = team_source_pool(era, teams=world)
        player_pools[era] = source_pool(era, teams=world)
        direct = {p['source_player_id']: p for p in player_pools[era]}
        seeded = VRS()
        seeded.seed(world, ERA_META[era]['start'])
        standings = {row['id']: row for row in seeded.table(world, ERA_META[era]['start'])}
        assert pool and len(pool) == len({row['team_id'] for row in pool})
        assert abs(sum(row['team_probability'] for row in pool) - 1) < 1e-12
        assert creation_options(era)['attribute_draw']['preview_teams'] == pool
        for row in pool:
            assert len(row['players']) == len({p['player_id'] for p in row['players']}) == 5
            assert len({p['source_player'].casefold() for p in row['players']}) == 5
            assert row['source_era'] == era and row['vrs_as_of'] == ERA_META[era]['start']
            assert row['vrs_points'] == standings[row['team_id']]['vrs']
            assert row['vrs_rank'] == standings[row['team_id']]['rank']
            assert row['vrs_source'] == 'same_era_opening_game_vrs_seed'
            assert all(p['stats'] == direct[p['source_player_id']]['stats'] for p in row['players'])
        mass = {band: sum(t['team_probability'] for t in pool if t['band'] == band)
                for band in {t['band'] for t in pool}}
        assert mass['common'] > mass['legendary']
    assert save_hashes() == initial and not metadata.exists()
    checks.append('all three eras: complete five named players, exact unchanged axes, fresh opening VRS, displayed probabilities sum to one')

    # No current career VRS dependency; invalid source rows exclude the entire team.
    fixture = deepcopy(build_teams('2026')[0])
    for mutate in ('duplicate', 'placeholder', 'bool', 'nan', 'incomplete'):
        bad = deepcopy(fixture)
        if mutate == 'duplicate': bad['players'][1]['player_id'] = bad['players'][0]['player_id']
        if mutate == 'placeholder': bad['players'][1]['name'] = 'rook7'
        if mutate == 'bool': bad['players'][1]['stats']['firepower'] = True
        if mutate == 'nan': bad['players'][1]['stats']['firepower'] = float('nan')
        if mutate == 'incomplete': bad['players'].pop()
        reject(lambda bad=bad: team_source_pool('2026', teams=[bad]))
    one_team = team_source_pool('2026', teams=[fixture])
    assert len(one_team) == 1 and one_team[0]['team_probability'] == 1
    checks.append('duplicate/placeholder/invalid/incomplete rosters excluded; small pools remain drawable with replacement')

    # Preserve a genuine schema1-style draft and old receipt; GET migration is pure.
    legacy_id = 'legacy-one-axis-draft'
    legacy_draw = dict(draw_id='legacy-result', axis='firepower', value=60)
    legacy = {'draft_id': legacy_id, 'era': '2026', 'status': 'pending', 'revision': 1,
        'difficulty': 'easy', 'max_draws': 3, 'source_pool': player_pools['2026'],
        'axes': {axis: {'draws': [legacy_draw] if axis == 'firepower' else [],
                        'selected_draw_id': 'legacy-result' if axis == 'firepower' else None} for axis in AXES}}
    old_body = dict(era='2026', draft_id=legacy_id, difficulty='easy', axis='firepower', request_id='legacy-retry-roll')
    old_result = {'reason': 'legacy saved result', 'draw': legacy_draw}
    old_digest = _hash({key: old_body.get(key) for key in ('era', 'draft_id', 'difficulty', 'axis', 'draw_id')} | {'action': 'roll'})
    old_receipt = {'hash': old_digest, 'result': old_result}
    old_store = {'schema_version': 1, 'kind': 'career3d-attribute-draw', 'drafts': {legacy_id: legacy},
        'active_drafts': {'2026': legacy_id}, 'receipts': {'legacy-retry-roll': old_receipt}, 'create_receipts': {}}
    metadata.write_text(json.dumps(old_store, ensure_ascii=False), encoding='utf-8')
    legacy_bytes = metadata.read_bytes()
    assert draw_context(state) == {'attribute_draw': None, 'legacy_draft_preserved': True}
    assert metadata.read_bytes() == legacy_bytes
    assert command('roll', **old_body) == {**old_result, 'replayed': True}
    assert metadata.read_bytes() == legacy_bytes
    opened = command('open', era='2026', request_id='open-team-2026-first')
    draft = opened['attribute_draw']
    ident = draft['draft_id']
    store = _load()
    assert store['drafts'][legacy_id] == legacy and store['receipts']['legacy-retry-roll'] == old_receipt
    assert store['active_drafts']['2026'] == legacy_id and store['active_team_drafts']['2026'] == ident
    assert draft['attempts_used'] == 0 and draft['remaining'] == 10 and draft['can_roll']
    assert command('open', era='2026', request_id='open-team-2026-first')['replayed']
    assert command('open', era='2026', request_id='open-team-2026-second')['attribute_draw']['draft_id'] == ident
    checks.append('schema1 draft, selection, receipts and active mapping preserved; read-only migration/retry never rewrites old store')

    reject(lambda: command('roll', era='2025', draft_id=ident, request_id='roll-team-wrong-era'))
    reject(lambda: command('roll', era='2026', draft_id=ident, axis='firepower', request_id='roll-old-axis-invalid'))
    request = dict(era='2026', draft_id=ident, request_id='roll-team-concurrent-first')
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: command('roll', **request), range(8)))
    first = results[0]['draw']
    pending_fixture = deepcopy(results[0]['attribute_draw'])
    assert len({r['draw']['draw_id'] for r in results}) == 1
    assert sum(not r.get('replayed') for r in results) == 1
    assert draw_context(state)['attribute_draw']['attempts_used'] == 1
    reject(lambda: command('roll', era='2026', draft_id=ident, request_id='roll-pending-rejected'))
    reject(lambda: command('roll', **dict(request, era='2025')))
    reject(lambda: command('select', era='2026', draft_id=ident, draw_id=first['draw_id'],
        axis='firepower', player_id='not-in-five', request_id='select-foreign-person'))
    reject(lambda: command('select', era='2026', draft_id=ident, draw_id=first['draw_id'],
        axis='firepower', player_id=first['players'][0]['player_id'], draft_revision=-1, request_id='select-stale-revision'))
    body = dict(era='2026', draft_id=ident, draw_id=first['draw_id'], axis='firepower',
        player_id=first['players'][0]['player_id'], value=100, request_id='select-team-first')
    selected = command('select', **body)
    selected_fixture = deepcopy(selected['attribute_draw'])
    assert selected['selection']['value'] == first['players'][0]['stats']['firepower']
    assert command('select', **body)['replayed']
    reject(lambda: command('select', **dict(body, axis='entrying', request_id='select-historical-reuse')))
    assert save_hashes() == initial and facts == (state.career.to_json(), state.season.date, state.season.teams)
    reloaded = ApplicationState()
    assert draw_context(reloaded)['attribute_draw'] == selected['attribute_draw']
    assert command('roll', **request)['draw'] == first  # Retry after select/reload is exact original result.
    checks.append('eight concurrent retries spend once; pending blocks roll; each team has one immutable choice; invalid/replayed operations preserve quota/save pair')

    base = dict(mode='create', era='2026', origin='attribute_draw', draft_id=ident,
        name='TeamDrawQA', org='Team Draw QA Club', role='entry', region='AS')
    reject(lambda: start_command(state, 'create', dict(career=base, revision=0, request_id='create-incomplete-team')))
    reject(lambda: start_command(state, 'create', dict(career={**base, 'origin': 'academy'}, revision=0, request_id='create-old-origin-team')))
    reject(lambda: state.create_career({**base, '_start_attributes': {axis: 100 for axis in AXES}}))
    for attempt in range(2, 5):
        response = command('roll', era='2026', draft_id=ident, request_id=f'roll-replace-{attempt}')
        draw = response['draw']
        command('select', era='2026', draft_id=ident, draw_id=draw['draw_id'], axis='firepower',
            player_id=draw['players'][1]['player_id'], request_id=f'select-replace-{attempt}')
    blocked = command('roll', era='2026', draft_id=ident, request_id='roll-limit-protect-fifth')['draw']
    assert set(draw_context(state)['attribute_draw']['selectable_axes']) == set(AXES[1:])
    reject(lambda: command('select', era='2026', draft_id=ident, draw_id=blocked['draw_id'], axis='firepower',
        player_id=blocked['players'][0]['player_id'], request_id='select-repeat-would-deadlock'))
    for index, axis in enumerate(AXES[1:]):
        draw = blocked if index == 0 else command('roll', era='2026', draft_id=ident, request_id='roll-fill-' + axis)['draw']
        command('select', era='2026', draft_id=ident, draw_id=draw['draw_id'], axis=axis,
            player_id=draw['players'][index % 5]['player_id'], request_id='select-fill-' + axis)
    complete = draw_context(state)['attribute_draw']
    assert complete['complete'] and complete['attempts_used'] == 10 and complete['remaining'] == 0
    assert len(complete['team_draws']) == 10 and not complete['can_roll']
    assert all(draw['selection'] for draw in complete['team_draws'])
    reject(lambda: command('roll', era='2026', draft_id=ident, request_id='roll-eleventh-forbidden'))
    values, provenance = selected_attributes(ident, '2026')
    assert provenance['attempts_used'] == 10 and provenance['schema_version'] == 2
    assert provenance['value_policy'] == 'calibrated_world_axes_v1'
    reject(lambda: selected_attributes(ident, '2026', 'easy'))
    checks.append('replacements consume fresh draws; forced fill prevents deadlock; ten-draw durable cap; all seven server-selected frozen values required')
    (folder / 'backend_draw_fixture.json').write_text(json.dumps({'sessions': {
        'empty': opened['attribute_draw'], 'pending': pending_fixture,
        'selected': selected_fixture, 'complete': complete}}, ensure_ascii=False, indent=2), encoding='utf-8')

    create_body = dict(career={**base, 'attributes': {axis: 100 for axis in AXES}}, revision=0, request_id='create-exact-team-selected')
    result = start_command(state, 'create', create_body)
    assert result['new_career']
    player = state.career.my_player(state.season.teams)
    assert {axis: player['stats'][axis] for axis in AXES} == values
    from cs2career.world.calibrated import weighted_score
    assert player['ability'] == round(weighted_score(values, 'entry'), 3)
    assert state.career.incident_state['career3d_attribute_draw'] == provenance
    team = state.career.my_team(state.season.teams)
    academy = origin_config('academy')
    assert state.career.money == academy['pocket_money'] and team['money'] == academy['club_money']
    assert state.career.attr_points == academy['attr_points']
    saved = json.loads((data / 'save' / 'season.json').read_text('utf-8'))
    persisted = next(p for t in saved['teams'] if t['id'] == team['id'] for p in t['players'] if p.get('you'))
    assert {axis: persisted['stats'][axis] for axis in AXES} == values
    state.settle()
    exact = save_hashes()
    loaded = ApplicationState()
    assert start_command(loaded, 'create', {**create_body, 'revision': -1})['replayed'] and save_hashes() == exact
    reject(lambda: start_command(state, 'create', {**create_body, 'career': {**base, 'name': 'Different'}}))
    assert draw_context(state)['attribute_draw'] is None
    assert _load()['drafts'][legacy_id] == legacy
    checks.append('creation ignores forged attributes, persists exact values/provenance atomically, retains legacy records and budgets, retries survive process restart')

    # The same complete roster can repeat all ten times, including replacement of a filled axis.
    with patch('tools.career3d_attribute_draw.team_source_pool', return_value=one_team):
        small = command('open', era='2024', request_id='open-one-team-fixture')['attribute_draw']
    for index in range(10):
        draw = command('roll', era='2024', draft_id=small['draft_id'], request_id=f'roll-one-team-{index}')['draw']
        assert draw['team_id'] == one_team[0]['team_id']
        if index >= 7:
            reject(lambda: selected_attributes(small['draft_id'], '2024'))
        axis = AXES[index] if index < 7 else AXES[0]
        command('select', era='2024', draft_id=small['draft_id'], draw_id=draw['draw_id'], axis=axis,
            player_id=draw['players'][0]['player_id'], request_id=f'select-one-team-{index}')
    assert draw_context(state, '2024')['attribute_draw']['complete']
    checks.append('with-replacement sampling remains valid with one eligible roster; seven filled plus extra pending cannot bypass selection')

    # Corruption must fail closed, never reset quota or rewrite evidence.
    good_bytes = metadata.read_bytes()
    damaged = json.loads(good_bytes)
    latest = damaged['drafts'][small['draft_id']]
    latest['team_draws'][0]['selection']['value'] += .25
    metadata.write_text(json.dumps(damaged, ensure_ascii=False), encoding='utf-8')
    reject(lambda: draw_context(state, '2024'))
    metadata.write_bytes(good_bytes)
    checks.append('corrupt donor selection rejected without resetting quota or overwriting evidence')

    server = create_server(state, port=0)
    server.RequestHandlerClass, server.game_disabled, server.display_hour = handler_class(), True, 8
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def api(path, body=None, expected=200, authenticated=True):
        headers = {'Content-Type': 'application/json'}
        if authenticated: headers['X-Career-Token'] = server.token
        request = Request(f'http://127.0.0.1:{server.server_port}' + path,
            None if body is None else json.dumps(body).encode(), headers)
        try:
            with urlopen(request, timeout=20) as response:
                status, value = response.status, json.loads(response.read())
        except HTTPError as exc:
            status, value = exc.code, json.loads(exc.read())
        assert status == expected, (path, status, value)
        return value
    try:
        hashes = save_hashes()
        api('/api/3d/start/draw?era=2025', authenticated=False, expected=403)
        api('/api/3d/start/draw?era=2099', expected=400)
        normal = api('/api/3d/start/draw', dict(action='open', era='2025', request_id='http-open-2025-team'))['attribute_draw']
        body = dict(action='roll', era='2025', draft_id=normal['draft_id'], request_id='http-roll-team-once')
        rolled = api('/api/3d/start/draw', body)
        assert len(rolled['draw']['players']) == 5 and api('/api/3d/start/draw', body)['replayed']
        assert api('/api/3d/start/draw?era=2025')['attribute_draw']['attempts_used'] == 1
        api('/api/3d/start/draw', {**body, 'request_id': 'http-roll-pending-reject'}, expected=400)
        player = rolled['draw']['players'][0]
        selection = api('/api/3d/start/draw', dict(action='select', era='2025', draft_id=normal['draft_id'],
            draw_id=rolled['draw']['draw_id'], player_id=player['player_id'], axis='utility', value=100,
            request_id='http-select-team-utility'))
        assert selection['selection']['value'] == player['stats']['utility']
        assert save_hashes() == hashes
        checks.append('authenticated HTTP open/roll/select preserves current save pair; exact idempotent responses and pending rejection verified')
    finally:
        server.shutdown()
        thread.join(3)
        server.server_close()
    return dict(ok=True, checks=checks, team_pool_counts={era: len(rows) for era, rows in pools.items()},
        player_pool_counts={era: len(rows) for era, rows in player_pools.items()},
        official_saves_accessed=False, actual_cs2_started=False, date_advanced=False, metadata_path=str(metadata))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    folder = args.output_dir.resolve()
    if not args.output_dir.is_absolute() or folder.drive.upper() not in ('D:', 'E:') or folder.exists():
        parser.error('Select a new explicitly isolated absolute D/E directory')
    result = run(folder)
    (folder / 'attribute-draw-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
