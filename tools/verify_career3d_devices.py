"""HTTP checks for the isolated phone/PC adapters. All generated data is on E."""
import argparse
from datetime import date, timedelta
import json
from pathlib import Path
from urllib.parse import quote

from verify_career3d_service import Client


def run(folder):
    client = Client(folder)
    checks = []
    try:
        original = client.context()
        before = client.hashes()
        team = client.api('/api/3d/team?id=' + quote(original['team']['id']))['detail']
        assert len(team['players']) == 5
        player = client.api('/api/3d/player?id=' + quote(original['player']['id']))['detail']
        assert player['player_id'] == original['player']['id']
        ev = client.api('/api/3d/event?id=' + quote(original['calendar_events'][0]['id']))['detail']
        assert ev['name'] == original['calendar_events'][0]['name']
        client.api('/api/3d/team?id=missing', expected=404)
        assert client.hashes() == before
        checks.append('team/player/event ID browsing is read-only')

        def ladder(action, body=None):
            info = client.context()['ladder']
            return client.api('/api/3d/ladder/' + action, {'revision': info['revision'], **(body or {})})

        client.api('/api/3d/ladder/matchmake', {'revision': -1}, expected=400)
        ladder('matchmake')
        for _ in range(30):
            lobby = client.context()['ladder']['lobby']
            if lobby['phase'] == 'ready':
                break
            if not lobby['turn']['human']:
                ladder('advance')
            elif lobby['phase'] == 'draft':
                available = [p for p in lobby['selection'] if p not in lobby['a'] + lobby['b']]
                ladder('pick', {'player_id': available[0]})
            elif lobby['phase'] == 'veto':
                ladder('ban', {'map': lobby['map_pool'][0]})
            else:
                ladder('side', {'side': 'ct'})
        else:
            raise AssertionError('draft failed to reach a ready lobby')
        lobby = client.context()['ladder']['lobby']
        assert len(lobby['a']) == len(lobby['b']) == 5
        for side in ('a', 'b'):
            assert len({lobby['roster'][p]['role'] for p in lobby[side]}) == 5
        result = ladder('simulate', {'lobby_id': lobby['id']})['result']
        assert result['source'] == 'simulated' and result['human_id'] == original['player']['id']
        assert sum(len(p) for p in result['map']['players'].values()) == 10
        assert len(result['changes']) == 10
        settled = client.hashes()
        replay = client.api('/api/3d/ladder/simulate', {'revision': -1, 'lobby_id': lobby['id']})
        assert replay['replayed'] and replay['result'] == result and client.hashes() == settled
        now = client.context()
        for key in ('date', 'money', 'attr_points', 'team', 'player'):
            assert now[key] == original[key], key
        assert now['ladder']['player']['wins'] + now['ladder']['player']['losses'] == 1
        checks.append('real draft/veto, distinct roles, ten-player simulation, one Elo settlement, no career rewards')

        opponent = next(t for t in now['scrims']['opponents'] if t['id'] != now['team']['id'])
        client.api('/api/3d/scrim/schedule', {'opponent_id': opponent['id'], 'date': now['date'], 'map': 'dust2'})
        scrim = client.context()['scrims']['scheduled'][0]
        report = client.api('/api/3d/scrim/simulate', {'id': scrim['id']})['report']
        assert len(report['map']['players']) == 2
        assert sum(len(p) for p in report['map']['players'].values()) == 10
        settled = client.hashes()
        assert client.api('/api/3d/scrim/simulate', {'id': scrim['id']})['replayed']
        assert client.hashes() == settled
        tomorrow = (date.fromisoformat(now['date']) + timedelta(days=1)).isoformat()
        client.api('/api/3d/scrim/schedule', {'opponent_id': opponent['id'], 'date': tomorrow, 'map': 'mirage'})
        future = client.context()['scrims']['scheduled'][0]
        client.api('/api/3d/scrim/simulate', {'id': future['id']}, expected=400)
        after = client.context()
        for key in ('date', 'money', 'attr_points', 'team', 'player'):
            assert after[key] == original[key], key
        client.api('/api/3d/scrim/schedule', {}, token=False, expected=403)
        checks.append('scrim schedule/due date, ten-player report, replay safety, career unchanged')
        size = len(json.dumps(after, ensure_ascii=False).encode())
        assert size < 200_000, size
        checks.append('context omits high-volume event streams, below 200 KB after activities')
    finally:
        client.close()
    reloaded = Client(folder)
    try:
        after_reload = reloaded.context()
        assert after_reload['ladder']['player'] == after['ladder']['player']
        assert after_reload['scrims']['history'][0]['report'] == after['scrims']['history'][0]['report']
        checks.append('ladder and scrim reports survive closing and reopening')
    finally:
        reloaded.close()
    return dict(ok=True, checks=checks, context_bytes=size)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    folder = args.output_dir.resolve()
    if folder.drive.upper() != 'E:' or folder.exists():
        parser.error('Select a new isolated directory on E')
    report = run(folder)
    (folder / 'devices-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))
