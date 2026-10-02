"""Black-box start/avatar checks on a newly created D/E fixture only."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import subprocess
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.verify_career3d_service import Client


class LoggedClient(Client):
    """Many draw requests must not fill an unread Windows stderr pipe."""
    def __init__(self, folder, mode='normal'):
        suffix = uuid4().hex[:8]
        self.logs = [(folder / f'start-service-{suffix}.{name}.log').open('w', encoding='utf-8')
                     for name in ('stdout', 'stderr')]
        original = subprocess.Popen
        def launch(*args, **kwargs):
            kwargs.update(stdout=self.logs[0], stderr=self.logs[1])
            return original(*args, **kwargs)
        try:
            with patch('tools.verify_career3d_service.subprocess.Popen', side_effect=launch):
                super().__init__(folder, mode)
        except Exception:
            for log in self.logs: log.close()
            raise

    def close(self):
        try:
            super().close()
        finally:
            for log in self.logs: log.close()


def verify(folder):
    client = LoggedClient(folder)
    checks = []
    try:
        for era in ('2024', '2025', '2026'):
            before = client.hashes()
            options = client.api('/api/3d/start/options?era=' + era)
            assert options['era'] == era and [row['id'] for row in options['origins']] == ['attribute_draw']
            assert options['attribute_draw']['max_draws'] == 10
            assert 'difficulties' not in options['attribute_draw']
            assert all(len(t['players']) == 5 for t in options['teams'])
            previews = options['attribute_draw']['preview_teams']
            assert previews and all(row['source_era'] == era and len(row['players']) == 5 for row in previews)
            assert abs(sum(row['team_probability'] for row in previews) - 1) < 1e-12
            assert client.hashes() == before
            checks.append('read-only dated options ' + era)
        before = client.hashes()
        ctx = client.context()
        client.api('/api/3d/avatar', {'revision': ctx['calendar']['revision'],
                                    'appearance': {'body_color': 'zzzzzz'}}, expected=400)
        assert client.hashes() == before
        checks.append('invalid appearance rejected without write')
        colors = {'body_color': '#acbdee', 'jersey_color': '334477', 'outfit': 'natural'}
        out = client.api('/api/3d/avatar', {'revision': ctx['calendar']['revision'], 'appearance': colors})
        assert out['context']['avatar']['appearance']['body_color'] == 'acbdee'
        assert out['context']['avatar']['appearance']['outfit'] == 'natural'
        checks.append('appearance canonical, saved in original incident state')
        for era in ('2024', '2025', '2026'):
            before = client.hashes()
            opened = client.api('/api/3d/start/draw', {'action': 'open', 'era': era, 'request_id': uuid4().hex})
            draft = opened['attribute_draw']
            assert draft['max_draws'] == 10 and draft['attempts_used'] == 0 and 'difficulty' not in draft
            selected = {}
            for axis in [row['id'] for row in draft['axes']]:
                draw_body = {'action': 'roll', 'era': era, 'draft_id': draft['draft_id'], 'request_id': uuid4().hex}
                response = client.api('/api/3d/start/draw', draw_body)
                draft, drawn = response['attribute_draw'], response['draw']
                assert drawn['source_era'] == era and drawn['band'] and drawn['band_color']
                assert len(drawn['players']) == 5 and all(len(p['stats']) == 7 for p in drawn['players'])
                assert client.api('/api/3d/start/draw', draw_body)['replayed']
                client.api('/api/3d/start/draw', {**draw_body, 'request_id': uuid4().hex}, expected=400)
                if era == '2026' and not selected:
                    # A real process restart with a revealed, not-yet-selected roster.
                    assert client.hashes() == before
                    client.close()
                    client = LoggedClient(folder)
                    # Normal shutdown intentionally persists the original save;
                    # draw endpoints themselves must not do so on either side.
                    before = client.hashes()
                    assert client.api('/api/3d/start/draw?era=' + era)['attribute_draw'] == draft
                    assert client.api('/api/3d/start/draw', draw_body)['draw'] == drawn
                    checks.append('pending team and its idempotent receipt survive an actual service restart')
                donor = drawn['players'][len(selected) % 5]
                selected[axis] = donor['stats'][axis]
                select_body = {'action': 'select', 'era': era, 'draft_id': draft['draft_id'],
                    'axis': axis, 'draw_id': drawn['draw_id'], 'player_id': donor['player_id'],
                    'request_id': uuid4().hex, 'value': 100}
                response = client.api('/api/3d/start/draw', select_body)
                draft = response['attribute_draw']
                assert client.api('/api/3d/start/draw', select_body)['replayed']
                client.api('/api/3d/start/draw', {**select_body, 'axis': 'utility' if axis != 'utility' else 'firepower',
                    'request_id': uuid4().hex}, expected=400)
            assert draft['complete'] and draft['attempts_used'] == 7 and client.hashes() == before
            ctx = client.context()
            body = {'revision': ctx['calendar']['revision'], 'request_id': uuid4().hex,
                    'confirm_replace': True, 'appearance': colors,
                    'career': {'era': era, 'mode': 'create', 'origin': 'attribute_draw',
                               'draft_id': draft['draft_id'], 'attributes': {axis: 100 for axis in selected},
                               'name': 'StartQA_' + era, 'org': 'StartQA ' + era,
                               'role': 'rifle', 'region': 'AS', 'quick_mode': era == '2026'}}
            rejection = dict(body, confirm_replace=False)
            before = client.hashes()
            client.api('/api/3d/start/create', rejection, expected=400)
            assert client.hashes() == before
            result = client.api('/api/3d/start/create', body)
            assert result['new_career'] and result['context']['origin'] == 'attribute_draw'
            assert result['context']['player']['name'] == body['career']['name']
            assert result['context']['calendar']['revision'] == ctx['calendar']['revision'] + 1
            assert len(result['context']['team']['roster']) == 5
            assert result['context']['avatar']['appearance']['body_color'] == 'acbdee'
            saved = json.loads((folder / 'data' / 'save' / 'season.json').read_text('utf-8'))
            player_card = next(p for t in saved['teams'] for p in t['players'] if p.get('you'))
            assert {axis: player_card['stats'][axis] for axis in selected} == selected
            after = client.hashes()
            replay = client.api('/api/3d/start/create', body)
            assert replay['replayed'] and client.hashes() == after
            checks.append(era + ' seven-team start, one attribute per draw, exact frozen axes, forged-value/duplicate-receipt protection')
        options = client.api('/api/3d/start/options?era=2024')
        team = next(t for t in options['teams'] if t['name'] == 'Vitality')
        player = next(p for p in team['players'] if p['name'].lower() == 'zywoo')
        ctx = client.context()
        body = {'revision': ctx['calendar']['revision'], 'request_id': uuid4().hex, 'confirm_replace': True,
                'career': {'mode': 'join', 'era': '2024', 'team_id': team['id'],
                           'player_id': player['player_id'], 'role': 'awp'}, 'appearance': colors}
        result = client.api('/api/3d/start/create', body)
        assert result['context']['player']['id'] == player['player_id']
        assert result['context']['player']['name'] == player['name']
        assert result['context']['season']['era'] == '2024'
        assert result['context']['date'].startswith('2024-')
        assert result['context']['team']['id'] == team['id']
        checks.append('professional start resolves dated stable IDs')
        backups = list((folder / 'data' / 'save' / 'backups').iterdir())
        assert len(backups) >= 4
        checks.append('replacement backup retained')
        client.close()
        resumed = LoggedClient(folder)
        client = resumed
        ctx = client.context()
        assert ctx['player']['id'] == player['player_id']
        assert ctx['avatar']['appearance']['body_color'] == 'acbdee'
        checks.append('career and cosmetics recover after service restart')
        return {'passed': True, 'checks': checks, 'count': len(checks)}
    finally:
        if client.process.poll() is None: client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    folder = args.output_dir.resolve()
    if not args.output_dir.is_absolute() or folder.drive.upper() not in ('D:', 'E:') or folder.exists():
        parser.error('Use a fresh absolute D/E directory')
    folder.mkdir(parents=True)
    report = verify(folder)
    (folder / 'start-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
