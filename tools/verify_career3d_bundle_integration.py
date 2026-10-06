"""Black-box market purchases in a fresh D/E fixture, never a playable save."""
import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.verify_career3d_start import LoggedClient


def verify(folder):
    client = LoggedClient(folder)
    checks = []
    try:
        ctx = client.context()
        before = client.hashes()
        packs = ctx['skins']['loadout_packs']
        assert len(packs) == 4 and sum(row['count'] for row in packs) == 33
        assert all(row['price'] > 0 and row['currency'] == 'game_coin' for row in packs)
        for _ in range(3):
            assert client.context()['skins']['loadout_packs'] == packs
        assert client.hashes() == before
        checks.append('four priced packs/33 recipes; repeated market reads do not rewrite saves')
        body = {'id': packs[0]['id'], 'request_id': uuid4().hex, 'revision': -1}
        client.api('/api/3d/skins/bundle', body, expected=400)
        client.api('/api/3d/skins/bundle', body, token=False, expected=403)
        assert client.hashes() == before
        checks.append('authentication and stale wallet rejected without writes')
        client.close()
        # Fund ONLY this test fixture via the original state writer. The client
        # has exited, so no second service can race the canonical save pair.
        from tools.career3d_service import isolate
        isolate(folder / 'data')
        from cs2career.application import ApplicationState
        state = ApplicationState()
        assert state.career.exists
        state.career.money = 5_000_000
        state.career.story_queue.append({'id': 'qa.saved-final-label', 'title': 'QA', 'text': '',
            'choices': [{'id': 'simulate', 'label': '相信队伍 · 仅模拟当前这一场'}]})
        from tools.career3d_service import read_context
        stored_story = json.dumps(state.career.story_queue, ensure_ascii=False)
        projected = read_context(state)
        assert next(row for row in projected['stories'] if row['id'] == 'qa.saved-final-label')['choices'][0]['label'] == '继续模拟'
        assert json.dumps(state.career.story_queue, ensure_ascii=False) == stored_story
        state.career.story_queue.pop()
        state.settle()
        client = LoggedClient(folder)
        ctx = client.context()
        checks.append('existing saved finals labels project Continue without changing choice or stored story')
        receipts = []
        initial_inventory = len(ctx['skins']['inventory'])
        for pack in ctx['skins']['loadout_packs']:
            wallet, size, revision = ctx['money'], len(ctx['skins']['inventory']), ctx['calendar']['revision']
            body = {'id': pack['id'], 'request_id': uuid4().hex, 'revision': revision,
                    'price': 1, 'items': []}
            result = client.api('/api/3d/skins/bundle', body)
            assert result['charged'] == pack['price'] and result['added'] == pack['count']
            ctx = result['context']
            assert ctx['money'] == wallet - pack['price']
            assert len(ctx['skins']['inventory']) == size + pack['count']
            assert ctx['calendar']['revision'] == revision + 1
            after = client.hashes()
            for repeated in (body, dict(body, request_id=uuid4().hex)):
                replay = client.api('/api/3d/skins/bundle', repeated)
                assert replay['replayed'] and replay['charged'] == 0 and replay['added'] == 0
                assert replay['context']['money'] == ctx['money']
                assert replay['context']['calendar']['revision'] == ctx['calendar']['revision']
                assert client.hashes() == after
            receipts.append(body)
        assert len(ctx['skins']['inventory']) == initial_inventory + 33
        assert len({row['id'] for row in ctx['skins']['inventory']}) == len(ctx['skins']['inventory'])
        assert all(row['owned'] and not row['buy_allowed'] for row in ctx['skins']['loadout_packs'])
        checks.append('all 33 recipes paid once and uniquely stored; client price/items cannot alter purchase')
        checks.append('same/different request retries of owned packs leave money, revision and saved bytes unchanged')
        client.close()
        client = LoggedClient(folder)
        ctx = client.context()
        after = client.hashes()
        for body in receipts:
            replay = client.api('/api/3d/skins/bundle', body)
            assert replay['replayed'] and replay['charged'] == 0
            assert replay['context']['money'] == ctx['money'] and client.hashes() == after
        checks.append('paid inventory and receipts survive service restart without duplicate debit')
        return {'ok': True, 'checks': checks, 'actual_cs2_started': False, 'official_saves_accessed': False}
    finally:
        if client.process.poll() is None:
            client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    folder = args.output_dir.resolve()
    if not args.output_dir.is_absolute() or folder.drive.upper() not in ('D:', 'E:') or folder.exists():
        parser.error('Choose a fresh absolute D/E fixture directory')
    folder.mkdir(parents=True)
    report = verify(folder)
    (folder / 'bundle-integration.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
