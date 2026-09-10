"""Isolated player-career flow probe using the desktop's authenticated HTTP API.

This is a workflow test, NOT proof of fun or the full agreed balance matrix.
No direct stat/date/money edits, game launch, fixtures, or user extensions.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from urllib.parse import quote
from datetime import date as calendar_date

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.flow_evidence import activity_evidence, source_fingerprint


def run(args):
    # These must be established before importing any application module.
    with tempfile.TemporaryDirectory(prefix='c2c-player-flow-') as folder:
        os.environ['CS2CAREER_SAVE_DIR'] = str(Path(folder) / 'save')
        os.environ['CS2CAREER_EXTENSION_DIR'] = str(Path(folder) / 'extensions')
        os.environ['CS2CAREER_NO_GAME'] = '1'
        from cs2career.application import ApplicationState
        from cs2career.web.server import Handler, create_server
        from cs2career.engine.match import RNG
        random.seed(args.seed)
        RNG.seed(args.seed)
        Handler.log_message = lambda *a: None
        server = create_server(ApplicationState())
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f'http://127.0.0.1:{server.server_port}'
        report = {'era': args.era, 'origin': args.origin, 'seed': args.seed,
                  'policy': args.policy,
                  'policy_rules': 'accept available invitations; simulate own series; refuse match fixing; ' +
                      ('spend earned points on firepower/trading/entrying/opening/clutching/sniping; choose offered birthday training; donate affordable crisis deficit' if args.policy == 'development' else 'free birthday response; no growth spending') +
                      '; no transfers or loans; real CS2 training remains untested (never claim rewards without a match)',
                  'random_streams': {'career': args.seed, 'match': args.seed},
                  'commands': [], 'milestones': {}, 'monthly': [], 'errors': [], 'complete': False,
                  'match_checks': [], 'target': args.until, 'years': args.years,
                  'reload_checkpoints': [], 'academy_intakes': []}
        report['source_fingerprint'] = source_fingerprint(ROOT)
        report['region'] = args.region
        state = None

        def check_match(key):
            data = request('/api/match?id=' + quote(key))
            match = data.get('match') or {}
            if not match.get('played') or not match.get('data_complete') or len(match.get('totals') or []) != 10:
                report['failure_match'] = data
                raise AssertionError(f'{key}: missing completed ten-player box score')
            for mp in match['maps']:
                lines = [p for players in mp['players'].values() for p in players]
                if sum(p['k'] for p in lines) != sum(p['d'] for p in lines):
                    raise AssertionError(f'{key}: kills/deaths not conserved')
                history = mp.get('round_history') or []
                if len(history) != mp['rounds'] or not all(r['winner'] in (match['team_a'], match['team_b']) for r in history):
                    raise AssertionError(f'{key}: missing round history')
            payload = {k: match[k] for k in ('team_a', 'team_b', 'series', 'maps', 'totals')}
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            return {'route_id': match['route_id'], 'hash': digest, 'maps': len(match['maps']),
                    'rounds': sum(mp['rounds'] for mp in match['maps'])}

        def request(path, body=None):
            nonlocal state
            req = Request(base + path, data=None if body is None else json.dumps(body).encode(),
                          headers={'Content-Type': 'application/json', 'X-Career-Token': server.token})
            try:
                with urlopen(req, timeout=180) as response:
                    data = json.load(response)
            except HTTPError as exc:
                data = json.load(exc)
            if 'state' in data:
                state = data['state']
            if body is not None:
                report['commands'].append({'path': path, 'body': body, 'date': state.get('date'), 'ok': data.get('ok'), 'msg': data.get('msg')})
            return data

        try:
            data = request('/api/career/create', {'era': args.era, 'mode': 'create', 'origin': args.origin,
                          'name': 'Flow Tester', 'org': 'Flow Club', 'role': 'rifle', 'region': args.region})
            if not data.get('ok'):
                raise RuntimeError(data)
            start_date = state['date']
            report['opening_roster'] = [{k:p.get(k) for k in ('player_id','name','role','ability')}
                                        for p in state['career']['roster']]
            last_month = ''
            last_year = int(args.era)
            for step in range(args.max_steps):
                if args.reload_every and step and step % args.reload_every == 0:
                    # Restart fixture: overwrite process RNGs, then verify that
                    # loading a real saved career restores both exact streams.
                    from cs2career.random_state import capture
                    with server.state_lock:
                        server.state.persist()
                        expected_rng = capture()
                        random.seed(args.seed + step)
                        RNG.seed(args.seed + step + 1)
                        server.state = ApplicationState()
                        if capture() != expected_rng:
                            raise AssertionError('reload changed the saved random sequence')
                    request('/api/state')
                    report['reload_checkpoints'].append({'date':state['date'],'step':step,'random_state_equal':True})
                career = state['career']
                date = state['date']
                current_year = int(date[:4])
                if current_year != last_year:
                    last_year = current_year
                    all_people = server.state.career.free + [p for t in server.state.season.teams for p in t['players']]
                    report['academy_intakes'].append({'year':current_year,'players':[
                        {k:p.get(k) for k in ('player_id','name','age','ability','potential','note','academy_year')}
                        for p in all_people if p.get('academy_year') == current_year]})
                if date[:7] != last_month:
                    last_month = date[:7]
                    report['monthly'].append({'date': date, 'club': career['money'], 'pocket': career['pocket'],
                                              'ability': (career.get('you') or {}).get('ability'),
                                              'rank': (career.get('vrs') or {}).get('rank'), 'unsigned': career['unsigned'],
                                              'age': (career.get('you') or {}).get('age'),
                                              'attr_points': career.get('attr_points'), 'loan': career.get('loan')})
                    print(json.dumps(report['monthly'][-1]), flush=True)
                if date[:7] != start_date[:7]:
                    report['milestones'].setdefault('first_month', date)
                if any(e.get('status') == 'done' and career['team_name'] in (e.get('field') or []) for e in state['events']):
                    report['milestones'].setdefault('first_event', date)
                if args.until == 'first-event' and 'first_event' in report['milestones']:
                    report['complete'] = True
                    break
                if current_year > int(args.era):
                    report['milestones'].setdefault('first_year', date)
                target_year = int(args.era) + args.years
                if current_year >= target_year:
                    target_event_done = any(e.get('status') == 'done' and career['team_name'] in (e.get('field') or []) for e in state['events'])
                    if args.until == 'year' or (args.until == 'next-season-event' and target_event_done):
                        if target_event_done:
                            report['milestones']['next_season_event'] = date
                        report['complete'] = True
                        break
                if career.get('over'):
                    report['errors'].append({'kind': 'career_ended', 'date': date, 'ending': career.get('ending')})
                    break
                stories = career.get('stories') or []
                if stories:
                    row = stories[0]
                    choices = row.get('choices') or []
                    ids = [c['id'] for c in choices]
                    # Only choose explicitly offered outcomes; never invent a choice.
                    preferred = ('refuse','train','free','message','ignore') if args.policy == 'development' else ('refuse','free','message','ignore')
                    choice = next((c for c in preferred if c in ids), ids[0] if ids else '')
                    data = request('/api/story/ack', {'id': row['id'], 'choice': choice})
                else:
                    invitation = next((m for m in career['inbox'] if m.get('status') == 'open' and m.get('kind') in ('invite', 'contract')), None)
                    match = (state.get('your_match') or {}).get('match')
                    axes = (career.get('you') or {}).get('stats') or {}
                    axis = next((a for a in ('firepower','trading','entrying','opening','clutching','sniping') if axes.get(a,100) < 100), None)
                    if args.policy == 'development' and career.get('attr_points',0) > 0 and axis and not career['unsigned']:
                        points = career['attr_points']
                        previous = float(axes[axis])
                        data = request('/api/attr', {'axis': axis})
                        updated = state['career']
                        if updated['attr_points'] != points-1 or float(updated['you']['stats'][axis]) <= previous:
                            raise AssertionError('growth command reported success without spending a point and increasing its axis')
                    elif args.policy == 'development' and career.get('crisis') and 0 < career.get('deficit',0) <= career['pocket']:
                        data = request('/api/ops/donate', {'amount': career['deficit']})
                    elif invitation:
                        data = request('/api/mail/accept', {'id': invitation['id']})
                    elif match:
                        data = request('/api/series/skip', {'match_id': match['id']})
                        if data.get('ok'):
                            report['milestones'].setdefault('first_match', state['date'])
                            report['match_checks'].append(check_match(match['id']))
                    else:
                        data = request('/api/next', {})
                if not data.get('ok') and not (state['career'].get('stories') or []):
                    report['errors'].append({'kind': 'command_rejected', 'last': report['commands'][-1]})
                    break
                if step and step % 25 == 0:
                    print(f'progress: {step} commands, {state["date"]}', flush=True)
            else:
                report['errors'].append({'kind': 'step_limit', 'date': state['date']})
            # A real reload, not a fresh fixture. Compare persisted business state.
            server.state.persist()
            before = (Path(folder) / 'save' / 'career.json').read_bytes()
            restored = ApplicationState()
            report['reload'] = {'date_equal': restored.season.date == server.state.season.date,
                                'balance_equal': restored.career.money == server.state.career.money,
                                'player_equal': restored.career.player_name == server.state.career.player_name,
                                'career_hash': hashlib.sha256(before).hexdigest()}
            team_before=server.state.career.my_team(server.state.season.teams)
            team_after=restored.career.my_team(restored.season.teams)
            report['reload']['roster_and_club_equal'] = team_before == team_after
            report['reload']['loan_equal'] = restored.career.loan == server.state.career.loan
            report['reload']['growth_points_equal'] = restored.career.attr_points == server.state.career.attr_points
            if not all(value for key,value in report['reload'].items() if key.endswith('_equal')):
                raise AssertionError('business state changed during save/reload')
            with server.state_lock:
                server.state = restored
            for checked in report['match_checks']:
                reloaded = check_match(checked['route_id'])
                if checked != reloaded:
                    raise AssertionError(f'{checked["route_id"]}: saved stats/events changed after reload or rollover')
            report['reload']['all_match_stats_and_events_equal'] = True
            report['final_date'] = state['date']
            if report['milestones'].get('first_match'):
                report['first_match_wait_days'] = (calendar_date.fromisoformat(report['milestones']['first_match']) - calendar_date.fromisoformat(start_date)).days
            report['player_series'] = len(report['match_checks'])
            report['activity'] = activity_evidence(report['commands'], start_date, state['date'])
            report['participation'] = []
            for year in range(int(args.era), int(state['date'][:4]) + 1):
                records = [r for r in server.state.season.records() if str(r.get('date','')).startswith(str(year))]
                for team in server.state.season.teams:
                    entered = [r for r in records if team['name'] in (r.get('field') or [])]
                    report['participation'].append({'year':year,'team_id':team['id'],'team':team['name'],
                        'events':len(entered),'completed_year':year<int(state['date'][:4])})
            # Business fingerprint deliberately excludes wall time, file paths,
            # and HTTP tokens. Includes all persistent gameplay/financial state.
            canonical = {'career': json.loads((Path(folder)/'save'/'career.json').read_text(encoding='utf-8')),
                         'season': json.loads((Path(folder)/'save'/'season.json').read_text(encoding='utf-8'))}
            report['business_hash'] = hashlib.sha256(json.dumps(canonical,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            report['final_player'] = {k: (state['career'].get('you') or {}).get(k) for k in ('age','ability','long_term_ability','role','stats')}
            report['elapsed_seconds'] = round(time.monotonic() - args.started, 2)
        except Exception as exc:
            report['complete'] = False
            report['errors'].append({'kind': type(exc).__name__, 'message': str(exc)})
        finally:
            server.shutdown()
            worker.join()
            server.server_close()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--era', choices=['2024', '2025', '2026'], default='2026')
    parser.add_argument('--origin', choices=['street', 'academy', 'prodigy'], default='academy')
    parser.add_argument('--seed', type=int, default=17)
    parser.add_argument('--region', choices=['AS','EU','AM'], default='AS')
    parser.add_argument('--policy', choices=['baseline','development'], default='baseline')
    parser.add_argument('--max-steps', type=int, default=1500)
    parser.add_argument('--until', choices=['first-event', 'year', 'next-season-event'], default='year')
    parser.add_argument('--years', type=int, default=1, help='Completed seasons before the year/next-season-event stopping point.')
    parser.add_argument('--reload-every', type=int, default=0, help='Reload actual saved state every N commands; 0 disables mid-run restarts.')
    parser.add_argument('--output', type=Path, default=ROOT / '.qa' / 'reports' / 'player-flow.json')
    args = parser.parse_args()
    if args.years < 1 or args.reload_every < 0:
        parser.error('years must be positive and reload-every must be nonnegative')
    args.started = time.monotonic()
    result = run(args)
    print(json.dumps({k: result.get(k) for k in ('complete', 'milestones', 'errors', 'reload', 'elapsed_seconds')}, ensure_ascii=False))
    sys.exit(0 if result['complete'] and not result['errors'] else 1)
