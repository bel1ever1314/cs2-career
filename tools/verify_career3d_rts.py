"""Isolated formal RTS workflow using natural Godot reports and actual HTTP commands.

Requires a fresh D:/ or E:/ output directory. No formal saves, CS2 processes,
plugins or deployed build are accessed. The GF gate fixture changes a test
stage only; all submitted map scores and player ledgers come from Godot.
"""
from copy import deepcopy
from datetime import date, timedelta
import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.career3d_service import isolate, handler_class, DEMO_SEED


def run(folder, godot):
    isolate(folder / 'data')
    def audit(event, args):
        if event not in ('open', 'os.scandir') or not args or not isinstance(args[0], (str, Path)):
            return
        target = Path(args[0]).resolve()
        if any(target == base or target.is_relative_to(base) for base in (ROOT / 'save', ROOT / 'extensions')):
            raise RuntimeError('RTS test forbids official save/extension access')
    sys.addaudithook(audit)
    from cs2career.application import ApplicationState
    from cs2career.web.server import create_server
    from cs2career.engine.match import RNG
    random.seed(DEMO_SEED)
    RNG.seed(DEMO_SEED)
    state = ApplicationState()
    state.create_career(dict(era='2026', mode='create', origin='academy', name='RTS Verification',
                            org='Morning Academy', region='AS', role='rifle'))
    source = ROOT / 'work/career_rts'
    project = folder / 'godot'
    project.mkdir(parents=True)
    for name in ('scripts', 'data', 'assets'):
        shutil.copytree(source / name, project / name)
    shutil.copy2(source / 'project.godot', project / 'project.godot')
    (project / 'tests').mkdir()
    shutil.copy2(source / 'tests/career_report_export.gd', project / 'tests/career_report_export.gd')
    checks, natural_maps = [], []
    server = create_server(state, port=0)
    server.RequestHandlerClass, server.game_disabled, server.display_hour = handler_class(), True, 8
    server.RequestHandlerClass.log_message = lambda *_args: None
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def api(path, body=None, expected=200):
        request = Request(f'http://127.0.0.1:{server.server_port}' + path,
            None if body is None else json.dumps(body).encode(),
            {'X-Career-Token': server.token, 'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=90) as response:
                code, value = response.status, json.loads(response.read())
        except HTTPError as exc:
            code, value = exc.code, json.loads(exc.read())
        assert code == expected, (path, code, value.get('msg', value.get('reason')), value.get('status'))
        return value
    def context():
        return api('/api/3d/context')
    def command(path, **body):
        return api('/api/3d/' + path, {'revision': context()['calendar']['revision'], **body})
    def hashes():
        return {str(p.relative_to(folder / 'data')): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (folder / 'data').rglob('*') if p.is_file()}
    def ack():
        for _ in range(50):
            stories = context()['stories']
            if not stories: return
            row = stories[0]
            command('story', id=row['id'], choice=(row['choices'][0]['id'] if row['choices'] else ''))
        raise AssertionError('Story chain did not end')
    def due():
        for _ in range(35):
            ack()
            current = context()
            if current.get('nextmatch') and current['nextmatch']['due']:
                return current['nextmatch']['id']
            events = {event['id']: event for event in current['calendar_events']}
            if current.get('nextmatch'):
                target = events[current['nextmatch']['event_id']]['end_date']
            else:
                invites = [row for row in current['inbox'] if row['kind'] == 'invite' and row['status'] == 'open'
                           and row.get('event_id') in events]
                if invites:
                    chosen = min(invites, key=lambda row: events[row['event_id']]['date'])
                    command('mail/accept', id=chosen['id'])
                    target = events[chosen['event_id']]['end_date']
                else:
                    registered = [event for event in current['calendar_events'] if event['registered'] and not event['played']]
                    assert registered, 'Normal career did not provide a registered event'
                    target = min(registered, key=lambda event: event['date'])['end_date']
            command('calendar', target_date=target, request_id=uuid4().hex)
        raise AssertionError('Normal calendar did not reach a due career match')
    def prepare(ident):
        for _ in range(20):
            value = command('match/preflight', match_id=ident)
            if value['context']['stories']:
                ack(); continue
            veto = value['preflight']['veto']
            if veto['complete']: return
            turn = veto['turn']
            assert turn and turn['mine']
            available = veto['available']
            if turn['action'] == 'ban':
                choice = 'nuke' if 'nuke' in available else available[-1]
            else:
                choice = 'dust2' if 'dust2' in available else next(name for name in available if name != 'nuke')
            command('match/veto', match_id=ident, map=choice)
        raise AssertionError('Manual original BP did not complete')
    def start(ident):
        for _ in range(20):
            result = command('rts/start', match_id=ident, side='t')
            if result.get('rts_session'): return result['rts_session']
            assert result['status'] == 'paused'
            ack()
        raise AssertionError('RTS start remained gated')
    def natural_report(session):
        prefix = folder / ('map-' + str(session['map_index']))
        session_file, report_file = prefix.with_suffix('.session.json'), prefix.with_suffix('.report.json')
        session_file.write_text(json.dumps(session, ensure_ascii=False), encoding='utf-8')
        process = subprocess.run([str(godot), '--headless', '--path', str(project), '--script',
            'res://tests/career_report_export.gd', '--', '--session-file=' + session_file.as_posix(),
            '--report-file=' + report_file.as_posix()], capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=300)
        prefix.with_suffix('.godot.log').write_text(process.stdout + process.stderr, encoding='utf-8')
        assert process.returncode == 0 and report_file.is_file(), process.stdout + process.stderr
        report = json.loads(report_file.read_text('utf-8'))
        assert report['finished'] and report['rules']['overtime'] is True
        natural_maps.append(dict(map=report['map'], score=report['score'], rounds=len(report['round_history']),
                                 seed=report['seed'], file=str(report_file)))
        print('NATURAL_CAREER_RTS_MAP ' + json.dumps(natural_maps[-1]), flush=True)
        return report
    try:
        ident = due()
        prepare(ident)
        before = hashes()
        for _ in range(3):
            assert not context()['rts']['pending']
        assert hashes() == before
        checks.append('read-only RTS context creates no session and changes no isolated save')
        revision = context()['calendar']['revision']
        api('/api/3d/rts/start', dict(match_id=ident, side='bad', revision=revision), expected=400)
        assert hashes() == before
        # This explicit stage-only fixture tests the ordinary career gate. No
        # fixture scores or player statistics are submitted to the engine.
        with server.state_lock:
            from cs2career.league.tournament_auto import moment
            ev, match = state.season.find_match(ident)
            original_stage = match['stage']
            match['stage'] = 'GF'
            moment(state.career, state.season, ev, match, 'final')
            state.persist()
        gated = command('rts/start', match_id=ident, side='t')
        assert gated['status'] == 'paused' and not match.get('career3d_rts') and not match.get('maps')
        assert context()['stories']
        with server.state_lock:
            match['stage'] = original_stage
            state.persist()
        ack()
        checks.append('ordinary pending tournament final decision pauses RTS before freezing any map or recording statistics')
        session = start(ident)
        repeated = command('rts/start', match_id=ident, side='t')
        assert repeated['replayed'] and repeated['rts_session'] == session
        before = hashes()
        tomorrow = (date.fromisoformat(state.season.date) + timedelta(days=1)).isoformat()
        calendar = api('/api/3d/calendar', dict(revision=context()['calendar']['revision'], target_date=tomorrow,
            request_id=uuid4().hex))
        assert calendar['status'] == 'paused' and state.season.date < tomorrow and not match.get('maps')
        before = hashes()
        blocked = command('match/simulate', match_id=ident, request_id=uuid4().hex)
        assert blocked['status'] == 'paused' and not match.get('maps') and hashes() == before
        command('rts/cancel', match_id=ident, nonce=session['nonce'])
        assert not match.get('career3d_rts') and not match.get('maps')
        checks.append('one frozen nonce/roster/map session blocks calendar and other simulation; cancel adds no result')
        for index in range(5):
            session = start(ident)
            report = natural_report(session)
            before = hashes()
            revision = context()['calendar']['revision']
            for label, change in (
                ('negative counter', lambda value: value['round_history'][0]['players'][0].update(k=-1)),
                ('missing counter', lambda value: value['round_history'][0]['players'][0].pop('damage')),
                ('boolean counter', lambda value: value['round_history'][0]['players'][0].update(k=True)),
                ('fractional counter', lambda value: value['round_history'][0]['players'][0].update(k=.5)),
                ('wrong final ledger', lambda value: value['players'][0].update(d=value['players'][0]['d'] + 1)),
                ('wrong identity', lambda value: value['round_history'][0]['players'][0].update(id='unrelated-player')),
                ('extra post-final round', lambda value: value['round_history'].append(deepcopy(value['round_history'][-1])))):
                invalid = deepcopy(report)
                change(invalid)
                api('/api/3d/rts/submit', dict(match_id=ident, nonce=session['nonce'], revision=revision, report=invalid), expected=400)
                assert hashes() == before and len(match.get('maps') or []) == index, label
            api('/api/3d/rts/submit', dict(match_id=ident, nonce='wrong-nonce', revision=revision, report=report), expected=400)
            assert hashes() == before
            # Godot JSON emits integral numeric values that other clients may
            # parse as floats. Preserve boolean state, but exercise all counters.
            numeric = deepcopy(report)
            for row in numeric['players']:
                for key in ('k', 'd', 'a', 'damage', 'kast_rounds', 'survived_rounds', 'opening_kills', 'opening_deaths'):
                    row[key] = float(row[key])
            for rd in numeric['round_history']:
                for row in rd['players']:
                    for key in ('k', 'd', 'a', 'damage', 'opening_kills', 'opening_deaths'):
                        row[key] = float(row[key])
            committed = command('rts/submit', match_id=ident, nonce=session['nonce'], report=numeric)
            assert len(match['maps']) == index + 1 and not match.get('career3d_rts')
            saved = match['maps'][-1]
            assert saved['source'] == 'rts' and len(saved['rts_round_history']) == len(report['round_history'])
            assert saved['score'] == f"{sum(r['winner'] == 'a' for r in saved['events'] if r['type'] == 'round_end')}-{sum(r['winner'] == 'b' for r in saved['events'] if r['type'] == 'round_end')}"
            assert any(event['type'] == 'kill' and event.get('killer_id') and event.get('victim_id') for event in saved['events'])
            assert any(event['type'] == 'hurt' and event.get('attacker_id') and event.get('victim_id') for event in saved['events'])
            revealed = committed['reveal']['maps'][0]
            assert revealed['events_available'] and revealed['round_stats_available'] and revealed['round_damage_available']
            final = {p['player_id']: p for p in revealed['round_frames'][-1]['players']}
            for p in [p for rows in saved['players'].values() for p in rows]:
                assert all(final[p['player_id']][key] == p[key] for key in ('k', 'd', 'a', 'damage', 'kast_rounds', 'adr', 'kast', 'rating'))
            before = hashes()
            replayed = api('/api/3d/rts/submit', dict(match_id=ident, nonce=session['nonce'], revision=-1, report=numeric))
            assert replayed['replayed'] and hashes() == before and len(match['maps']) == index + 1
            if match.get('played'):
                break
            ack()
        assert match['played'] and match['series'] and match['ratings']
        assert committed['result']['source'] == 'rts' and committed['result']['data_complete']
        assert len(committed['result']['totals']) == 10
        assert all(row['maps'] == len(match['maps']) for row in committed['result']['totals'])
        (folder / 'rts-match-projection.json').write_text(json.dumps(committed, ensure_ascii=False), encoding='utf-8')
        checks.append('natural Godot formal overtime-enabled reports preserve exact IDs/events and all ten round/final statistics')
        checks.append('malformed/partial/counterfeit/wrong-nonce reports do not write; integral Godot float counters are accepted')
        checks.append('each map and completed ordinary series settle once; stale submit receipts replay without any write or repeat rewards')
    finally:
        server.shutdown(); thread.join(3); server.server_close()
        state.persist()
    return dict(ok=True, official_saves_accessed=False, actual_cs2_started=False, actual_plugins_modified=False,
                actual_natural_godot_reports=True, gate_fixture='only isolated stage changed to GF; no fabricated map reports',
                checks=checks, maps=natural_maps)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--godot', type=Path, default=Path('E:/CS2CareerTools/Installers/Godot_v4.7.2-stable_win64.exe/Godot_v4.7.2-stable_win64_console.exe'))
    args = parser.parse_args()
    folder = args.output_dir.resolve()
    if not args.output_dir.is_absolute() or folder.exists() or folder.drive.upper() not in ('D:', 'E:'):
        parser.error('Choose a new explicit D:/ or E:/ verification directory')
    result = run(folder, args.godot)
    (folder / 'career-rts-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
