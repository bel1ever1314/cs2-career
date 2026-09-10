"""Frag distribution changes, not rating arithmetic or predetermined match odds."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from cs2career.world import build_teams
from cs2career.engine import match


class StarCurveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        teams = build_teams('2026', 2026)
        cls.a = next(t for t in teams if t['name'] == 'Vitality')
        cls.b = next(t for t in teams if t['name'] == 'Spirit')

    def play(self, seed, curve, a=None):
        match.RNG.seed(seed)
        with patch.object(match, 'STAR_CURVE', curve):
            return match.play_map(a or self.a, self.b, 'mirage')

    def test_fixed_seed_reproduces_every_stat_and_event(self):
        self.assertEqual(self.play(41, 2.2), self.play(41, 2.2))

    def test_new_curve_keeps_score_and_team_kill_totals(self):
        for seed in range(100):
            old, new = self.play(seed,1.24), self.play(seed,2.2)
            self.assertEqual((old['winner'],old['score']), (new['winner'],new['score']))
            for team in (self.a['name'],self.b['name']):
                for key in ('k','d','damage'):
                    self.assertEqual(sum(p[key] for p in old['players'][team]),sum(p[key] for p in new['players'][team]))
            rows = sum(new['players'].values(),[])
            self.assertEqual(sum(p['k'] for p in rows),sum(p['d'] for p in rows))

    def test_names_do_not_grant_star_bonus(self):
        team=deepcopy(self.a)
        for i,p in enumerate(team['players']):
            p['name']='Generic_'+str(i)
        old,new=self.play(99,2.2),self.play(99,2.2,team)
        def normalized(mp):
            return sorted([{k:v for k,v in p.items() if k!='name'} for p in mp['players'][team['name']]],key=lambda p:p['player_id'])
        self.assertEqual(normalized(old),normalized(new))


if __name__=='__main__':
    unittest.main()
