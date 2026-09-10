"""Pure report helpers. No application imports, RNG draws, or save access."""
from datetime import date
import hashlib
from pathlib import Path


def source_fingerprint(root):
    """Tie long-running results to rules/data/UI and the actual driver version."""
    root = Path(root)
    files = [p for p in (root / 'cs2career').rglob('*')
             if p.is_file() and p.suffix in ('.py', '.json', '.js', '.css')]
    files += [root / 'tools' / name for name in ('playthrough.py', 'flow_evidence.py')]
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.relative_to(root).as_posix().encode('utf-8'))
        digest.update(b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def activity_evidence(commands, start, end):
    """Formal match gaps only; don't label them days without *any* gameplay.

    Rejected attempts and repeated maps/series on the same date are not extra
    match days. The unfinished trailing interval is explicitly censored.
    """
    match_days = sorted({r['date'] for r in commands
                         if r.get('path') == '/api/series/skip' and r.get('ok') is True})
    gaps = [{'from':a, 'to':b, 'days':(date.fromisoformat(b)-date.fromisoformat(a)).days}
            for a, b in zip(match_days, match_days[1:])]
    return {
        'formal_match_days':len(match_days),
        'first_match_wait_days':(date.fromisoformat(match_days[0])-date.fromisoformat(start)).days if match_days else None,
        'longest_between_matches':max(gaps, key=lambda r:r['days'], default=None),
        'gaps_30_days_or_more':[g for g in gaps if g['days'] >= 30],
        'trailing_without_match_days':(date.fromisoformat(end)-date.fromisoformat(match_days[-1] if match_days else start)).days,
        'trailing_interval_censored':True,
        'rejected_commands':sum(r.get('ok') is not True for r in commands),
    }
