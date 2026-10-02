"""Isolated original Arena captain/turn/history checks, without CS2 or date steps."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.career3d_service import isolate


def run(folder):
    isolate(folder/'data')
    protected = (ROOT/'save', ROOT/'extensions', Path('E:/CS2CareerTools/Career3DRedesign/runtime/career'))
    def audit(event, args):
        if event not in ('open', 'os.scandir') or not args or not isinstance(args[0], (str, Path)):
            return
        path = Path(args[0]).resolve()
        if any(path == base or path.is_relative_to(base) for base in protected):
            raise RuntimeError('Ladder regression forbids official/runtime career data access')
    sys.addaudithook(audit)
    from cs2career.application import ApplicationState
    from cs2career.arena import Arena, PICK_ORDER, captain_key
    from tools.career3d_activities import device_context
    state = ApplicationState()
    state.create_career(dict(era='2026', mode='create', origin='academy', name='LadderFlowQA',
                            org='Ladder QA Academy', region='AS', role='rifle'))
    arena = state.arena
    human = arena.career_player_id(state)
    original = arena.roster(state)
    ids = [human, *[pid for pid in original if pid != human][:9]]
    fixture_pool = {pid: deepcopy(original[pid]) for pid in ids}
    # Explicit fixture scores exercise captain ordering independently of the
    # real professional snapshot/ability curve; production rules stay intact.
    arena.data['ladder'] = {pid: dict(elo=1000 + index*100, wins=0, losses=0, recent=[], seed={'kind':'fixture'})
                            for index, pid in enumerate(ids)}
    before = deepcopy((state.season.date, state.season.teams, state.career.money,
                       state.career.attr_points, state.career.team_id, state.career.role))
    transcript, checks = [], []
    with patch.object(arena, 'roster', return_value=fixture_pool):
        arena.matchmake(state, {'revision':arena.data['revision']})
        lobby = arena.data['lobby']
        scores = {row['player_id']:row for row in arena.catalog(state)}
        expected = sorted(lobby['selection'], key=lambda pid: captain_key(scores[pid]))[:2]
        assert lobby['captains'] == expected and human not in expected
        assert len(lobby['selection']) == 10 and len(set(lobby['selection'])) == 10
        checks.append('captains are exactly the two highest selected-player Elo scores; ordinary human is not promoted')
        while lobby['phase'] in ('draft', 'veto', 'side'):
            phase, old_picks, old_bans = lobby['phase'], deepcopy(lobby['picks']), deepcopy(lobby['bans'])
            turn = arena.turn(lobby)
            assert turn['human'] is False
            arena.advance({'revision':arena.data['revision']})
            if phase == 'draft':
                assert lobby['picks'][:-1] == old_picks and len(lobby['picks']) == len(old_picks) + 1
                action, item = 'pick', lobby['picks'][-1]['player_id']
                assert lobby['bans'] == old_bans
            elif phase == 'veto':
                assert lobby['bans'][:-1] == old_bans and len(lobby['bans']) == len(old_bans) + 1
                action, item = 'ban', lobby['bans'][-1]['map']
                assert lobby['picks'] == old_picks
            else:
                assert lobby['phase'] == 'ready' and lobby['picks'] == old_picks and lobby['bans'] == old_bans
                action, item = 'side', 'ct:' + lobby['ct']
            transcript.append(dict(step=len(transcript) + 1, phase_before=phase, side=turn['side'],
                                   captain_id=turn['captain_id'], action=action, item=item))
            public = arena.public(state)['lobby']
            assert public['picks'] == lobby['picks'] and public['bans'] == lobby['bans']
            restored = Arena(arena.path)
            assert restored.data['lobby']['picks'] == lobby['picks'] and restored.data['lobby']['bans'] == lobby['bans']
        assert [row['side'] for row in lobby['picks']] == list(PICK_ORDER)
        assert [row['side'] for row in lobby['bans']] == ['a' if index % 2 == 0 else 'b' for index in range(len(lobby['bans']))]
        assert len(lobby['picks']) == 8 and len(lobby['bans']) == len(lobby['map_pool']) - 1
        assert len(lobby['a']) == 5 and len(lobby['b']) == 5 and not set(lobby['a']).intersection(lobby['b'])
        assert [mp for mp in lobby['map_pool'] if mp not in {row['map'] for row in lobby['bans']}] == [lobby['map']]
        saved = hashlib.sha256(arena.path.read_bytes()).hexdigest()
        native_lobby = device_context(state)['ladder']['lobby']
        assert native_lobby['picks'] == lobby['picks'] and native_lobby['bans'] == lobby['bans']
        assert native_lobby['captains'] == lobby['captains'] and native_lobby['turn'] is None
        assert saved == hashlib.sha256(arena.path.read_bytes()).hexdigest()
        checks.append('each advance persists one AI action; 8 snake picks and 6 alternating bans remain available at ready and after reload/original/native read projections')
        ordinary_summary = dict(human_id=human, captain_ids=deepcopy(lobby['captains']),
                                human_is_captain=False, picks=len(lobby['picks']), bans=len(lobby['bans']),
                                map=lobby['map'], ct=lobby['ct'], steps=len(transcript))

        arena.cancel({'revision':arena.data['revision']})
        arena.data['ladder'][human]['elo'] = 3000
        arena.matchmake(state, {'revision':arena.data['revision']})
        lobby = arena.data['lobby']
        assert lobby['captains'][0] == human and arena.turn(lobby)['human']
        saved = hashlib.sha256(arena.path.read_bytes()).hexdigest()
        try:
            arena.advance({'revision':arena.data['revision']})
        except ValueError as exc:
            assert '轮到你' in str(exc)
        else:
            raise AssertionError('AI advance skipped a human captain turn')
        assert saved == hashlib.sha256(arena.path.read_bytes()).hexdigest()
        chosen = next(pid for pid in lobby['selection'] if pid not in lobby['a'] + lobby['b'])
        arena.pick({'revision':arena.data['revision'], 'player_id':chosen})
        assert lobby['picks'] == [{'side':'a', 'player_id':chosen}]
        arena.advance({'revision':arena.data['revision']})
        arena.advance({'revision':arena.data['revision']})
        assert arena.turn(lobby)['human'] and len(lobby['picks']) == 3
        checks.append('human captain receives manual turn; AI advance rejects it and stops after the two B snake turns')
    assert before == (state.season.date, state.season.teams, state.career.money,
                      state.career.attr_points, state.career.team_id, state.career.role)
    return dict(ok=True, checks=checks, ordinary_member=ordinary_summary, original_ai_transcript=transcript,
                original_pick_order=list(PICK_ORDER), current_lobby_history_preserved=True,
                fixture_note='Ten original player cards with explicit fixture Elo; no production captain/rating rules changed.',
                actual_cs2_started=False, career_date_advanced=False, deployed_runtime_accessed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    folder = args.output_dir.resolve()
    if folder.drive.upper() not in ('D:', 'E:') or folder.exists():
        parser.error('Select a new explicitly isolated D/E directory')
    result = run(folder)
    (folder/'ladder-flow-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
