"""Isolated fixed-roster calibration, not a season/playability acceptance test.

Uses saved raw map counters and the unchanged shared Career Rating formula.
No Career is loaded, no progression commands or file writes are performed.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cs2career.world import build_teams, MAPS
from cs2career.engine import match
from cs2career.engine.rating import career_rating


def measure(curve, samples):
    teams = build_teams('2026', 2026)
    opponents = sorted(teams, key=lambda t: t['world_rank'])[:30]
    match.STAR_CURVE = curve
    results = {}
    for name in ('ZywOo', 'donk', 'ropz'):
        team = next(t for t in teams if any(p['name'].lower() == name.lower() for p in t['players']))
        pool = [t for t in opponents if t['id'] != team['id']]
        totals = dict(k=0, d=0, a=0, damage=0, kast_rounds=0, rounds=0)
        player = next(p for p in team['players'] if p['name'].lower() == name.lower())
        for seed in range(samples):
            match.RNG.seed(830000 + seed)
            mp = match.play_map(team, pool[seed % len(pool)], MAPS[seed % len(MAPS)])
            row = next(p for p in mp['players'][team['name']] if p['name'] == player['name'])
            for key in totals:
                totals[key] += mp['rounds'] if key == 'rounds' else row[key]
        results[name] = dict(ability=player['ability'], form_delta=player.get('form_delta'),
            maps=samples, rating=career_rating(totals['k'],totals['d'],totals['a'],totals['damage'],totals['kast_rounds'],totals['rounds']),
            kpr=round(totals['k']/totals['rounds'],3), adr=round(totals['damage']/totals['rounds'],1),raw=totals)
    return {'curve':curve, 'players':results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples', type=int, default=1000)
    parser.add_argument('--curves', type=float, nargs='+', default=[match.STAR_CURVE])
    args = parser.parse_args()
    print(json.dumps([measure(c,args.samples) for c in args.curves],ensure_ascii=False,indent=2))
