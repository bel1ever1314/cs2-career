"""Compare two completed isolated playthrough reports, not just their scores.

No application imports or save loading. Timing, paths, and presentation-only
run names are excluded; persistent gameplay hash and each major evidence set
must agree. A failed/incomplete run can never establish reproducibility.
"""
import argparse
import json
from pathlib import Path
import sys

FIELDS = ('era','origin','seed','policy','target','years','commands','milestones',
          'monthly','match_checks','reload_checkpoints','academy_intakes',
          'participation','business_hash','final_date','final_player')


def first_difference(a, b, path):
    """Keep one precise counterexample per field; don't dump entire match ledgers."""
    if type(a) is not type(b):
        return {'path':path,'before':a,'after':b}
    if isinstance(a, dict):
        for key in sorted(a.keys() | b.keys()):
            if key not in a or key not in b:
                return {'path':f'{path}.{key}','missing_from':'before' if key not in a else 'after'}
            if a[key] != b[key]:
                return first_difference(a[key], b[key], f'{path}.{key}')
    elif isinstance(a, list):
        if len(a) != len(b):
            return {'path':f'{path}.length','before':len(a),'after':len(b)}
        for index, (left, right) in enumerate(zip(a,b)):
            if left != right:
                return first_difference(left, right, f'{path}[{index}]')
    return {'path':path,'before':a,'after':b}


def compare(a, b):
    problems = []
    for label, report in (('before',a),('after',b)):
        missing = [key for key in FIELDS if key not in report]
        if missing:
            problems.append(f'{label}: missing fields: {", ".join(missing)}')
        if not report.get('complete') or report.get('errors'):
            problems.append(f'{label}: incomplete or failed run')
        if not report.get('business_hash') or not report.get('match_checks'):
            problems.append(f'{label}: missing persistent-state or match evidence')
        required = ('date_equal','balance_equal','player_equal','roster_and_club_equal',
                    'loan_equal','growth_points_equal','all_match_stats_and_events_equal')
        if any(report.get('reload',{}).get(key) is not True for key in required):
            problems.append(f'{label}: reload validation missing or failed')
    differences = [key for key in FIELDS if a.get(key) != b.get(key)]
    return {'equal':not problems and not differences,'problems':problems,'differences':differences,
            'first_differences':[first_difference(a.get(key),b.get(key),key) for key in differences],
            'before_seconds':a.get('elapsed_seconds'),'after_seconds':b.get('elapsed_seconds'),
            'compared_fields':list(FIELDS)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before',type=Path)
    parser.add_argument('after',type=Path)
    args = parser.parse_args()
    result = compare(json.loads(args.before.read_text(encoding='utf-8')),
                     json.loads(args.after.read_text(encoding='utf-8')))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    sys.exit(0 if result['equal'] else 1)
