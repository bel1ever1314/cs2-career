"""Run isolated player careers, not world-only simulations or desktop UI tests.

Default: the agreed 3 eras x 3 starts x 5 fixed seeds, one full season each.
--until first-event is an explicitly shorter smoke test, never annual evidence.
Each subprocess creates its own temporary save/extension directories before
application imports. Resume only reuses successful, same-source evidence.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.flow_evidence import source_fingerprint

SEEDS = (17, 29, 43, 71, 101)
RELOAD_CHECKS = ('date_equal', 'balance_equal', 'player_equal', 'roster_and_club_equal',
                 'loan_equal', 'growth_points_equal', 'all_match_stats_and_events_equal')


def cases(eras, origins, seeds):
    return [{'era':era, 'origin':origin, 'seed':seed}
            for era in eras for origin in origins for seed in seeds]


def evidence_errors(report, expected, fingerprint):
    errors = []
    if not report.get('complete') or report.get('errors'):
        errors.append('run incomplete or failed')
    for key, value in expected.items():
        if report.get(key) != value:
            errors.append(f'mismatched {key}')
    if report.get('source_fingerprint') != fingerprint:
        errors.append('source/data/driver version mismatch')
    if not report.get('business_hash') or not report.get('match_checks'):
        errors.append('missing full-state or match evidence')
    if any(report.get('reload', {}).get(key) is not True for key in RELOAD_CHECKS):
        errors.append('save/reload validation missing or failed')
    return errors


def preflight(output, jobs, expected, fingerprint, resume):
    """Reject incompatible resumes before replacing any previous manifest."""
    manifest_path = output / 'matrix.json'
    if manifest_path.exists():
        if not resume:
            raise ValueError('matrix already exists; choose a new directory or --resume')
        previous = json.loads(manifest_path.read_text(encoding='utf-8'))
        for key, value in {**expected, 'source_fingerprint':fingerprint}.items():
            if previous.get(key) != value:
                raise ValueError(f'matrix {key} mismatch; choose a new output directory')
        wanted = {(r['era'],r['origin'],r['seed']) for r in jobs}
        recorded = {(r['era'],r['origin'],r['seed']) for r in previous.get('runs',[])}
        if previous.get('expected_runs') != len(jobs) or not recorded <= wanted:
            raise ValueError('matrix case selection mismatch; choose a new output directory')
    for case in jobs:
        path = output / f"{case['era']}-{case['origin']}-{case['seed']}.json"
        if not path.exists():
            continue
        if not resume:
            raise ValueError(f'{path.name} already exists; choose a new output directory')
        report = json.loads(path.read_text(encoding='utf-8'))
        errors = evidence_errors(report,{**case,**expected,'years':1},fingerprint)
        if errors:
            raise ValueError(f'{path.name}: cannot reuse: {errors}; choose a new output directory')


def execute(case, args, fingerprint):
    key = f"{case['era']}-{case['origin']}-{case['seed']}"
    path = args.output / f'{key}.json'
    expected = {**case, 'policy':'development', 'target':args.until, 'years':1, 'region':args.region}
    resumed = False
    if path.exists():
        if not args.resume:
            raise ValueError(f'{path.name} already exists; use a new directory or --resume')
        report = json.loads(path.read_text(encoding='utf-8'))
        errors = evidence_errors(report, expected, fingerprint)
        if errors:
            raise ValueError(f'{path.name}: cannot reuse: {errors}; choose a new output directory')
        resumed = True
        code = 0
    else:
        command = [sys.executable, str(ROOT / 'tools' / 'playthrough.py'),
                   '--era',case['era'],'--origin',case['origin'],'--seed',str(case['seed']),
                   '--region',args.region,'--policy','development','--until',args.until,
                   '--reload-every','50','--output',str(path)]
        with (args.output / f'{key}.log').open('w', encoding='utf-8') as log:
            process = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                     timeout=args.timeout)
        code = process.returncode
        report = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    errors = evidence_errors(report, expected, fingerprint)
    if code:
        errors.append(f'exit code {code}')
    return {**case, 'passed':not errors, 'errors':errors, 'resumed':resumed,
            'report':path.name, 'elapsed_seconds':report.get('elapsed_seconds'),
            'final_date':report.get('final_date'), 'milestones':report.get('milestones'),
            'player_series':report.get('player_series'), 'activity':report.get('activity')}


def save_manifest(args, fingerprint, results, total, started):
    data = {'schema_version':1, 'source_fingerprint':fingerprint, 'target':args.until,
            'region':args.region, 'policy':'development', 'expected_runs':total,
            'finished_runs':len(results), 'passed_runs':sum(r['passed'] for r in results),
            'complete':len(results)==total, 'passed':len(results)==total and all(r['passed'] for r in results),
            'elapsed_seconds':round(time.monotonic()-started,2),
            'limitations':['authenticated business API, not native desktop clicks',
                           'no real CS2 training; no transfers/loans in this policy',
                           'first-event runs do not validate full seasons or annual gaps'],
            'runs':sorted(results,key=lambda r:(r['era'],r['origin'],r['seed']))}
    pending = args.output / 'matrix.json.tmp'
    pending.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    pending.replace(args.output / 'matrix.json')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--eras',nargs='+',choices=['2024','2025','2026'],default=['2024','2025','2026'])
    parser.add_argument('--origins',nargs='+',choices=['street','academy','prodigy'],default=['street','academy','prodigy'])
    parser.add_argument('--seeds',nargs='+',type=int,default=list(SEEDS))
    parser.add_argument('--region',choices=['AS','EU','AM'],default='AS')
    parser.add_argument('--until',choices=['first-event','year'],default='year')
    parser.add_argument('--workers',type=int,choices=[1,2,3],default=2)
    parser.add_argument('--timeout',type=int,default=3600,help='Maximum seconds per career subprocess.')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--resume',action='store_true')
    args = parser.parse_args()
    if args.timeout < 1 or any(len(x)!=len(set(x)) for x in (args.eras,args.origins,args.seeds)):
        parser.error('timeout must be positive; duplicate cases are not allowed')
    args.output = args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=True)
    fingerprint = source_fingerprint(ROOT)
    jobs = cases(args.eras,args.origins,args.seeds)
    try:
        preflight(args.output,jobs,{'target':args.until,'region':args.region,'policy':'development'},
                  fingerprint,args.resume)
    except (ValueError,KeyError) as exc:
        parser.error(str(exc))
    results = []; started = time.monotonic()
    save_manifest(args,fingerprint,results,len(jobs),started)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(execute,case,args,fingerprint):case for case in jobs}
        for future in as_completed(futures):
            case = futures[future]
            try:
                row = future.result()
            except Exception as exc:
                row = {**case,'passed':False,'errors':[f'{type(exc).__name__}: {exc}']}
            results.append(row)
            print(json.dumps(row,ensure_ascii=False),flush=True)
            manifest = save_manifest(args,fingerprint,results,len(jobs),started)
    return 0 if manifest['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
