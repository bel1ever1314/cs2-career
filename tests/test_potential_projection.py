"""Scouting exposes existing ceilings or labelled pure estimates, never growth edits."""
from copy import deepcopy
import random
import unittest

from cs2career.world.potential import assessment
from cs2career.world.aging import gun_year_delta
from cs2career.career.market_balance import potential_stars
from cs2career.career.transfers import candidates
import test_personal_transfers as transfer_fixture


class PotentialProjectionTests(unittest.TestCase):
    def test_known_ceiling_is_not_estimated(self):
        for value in (64, 65, 75, 80, 90, 99):
            row = dict(potential=value, ability=60, age=17)
            self.assertEqual(dict(potential=value, potential_estimated=False), assessment(row))
        self.assertEqual(5, potential_stars(assessment({'potential': 95})['potential']))

    def test_estimate_uses_existing_growth_not_invented_bonus(self):
        row = dict(ability=90, long_term_ability=74, age=17, form_delta=9)
        before = deepcopy(row)
        baseline = 74
        for age in range(18, 26): baseline = round(baseline + gun_year_delta(age, baseline), 1)
        self.assertEqual(dict(potential=baseline, potential_estimated=True), assessment(row))
        self.assertEqual(before, row)
        self.assertEqual(74, assessment(dict(row, age=30))['potential'])
        self.assertEqual(assessment(row), assessment(dict(row, role='awp', ability=99)))

    def test_reference_baseline_and_missing_data(self):
        self.assertEqual(79, assessment(dict(ability=95, stats={'role_reference_score':79}, age=28))['potential'])
        for row in ({}, {'ability':70}, {'ability':'nan', 'age':18}, {'ability':70, 'age':False}):
            self.assertIsNone(assessment(row)['potential'])

    def test_real_transfer_projection_carries_sort_value_without_stamping_players(self):
        fixture = transfer_fixture.PersonalTransferTests()
        fixture.setUp()
        fixture.s.teams[1]['players'][0]['potential'] = 95
        players = deepcopy(fixture.s.teams)
        free = deepcopy(fixture.c.free)
        state = random.getstate()
        rows = candidates(fixture.c, fixture.s)
        self.assertTrue(rows)
        self.assertTrue(all(r['potential_stars'] is not None for r in rows))
        self.assertTrue(any(r['potential_estimated'] for r in rows))
        known = next(r for r in rows if r['player_id'] == 'p1_0')
        self.assertFalse(known['potential_estimated'])
        self.assertEqual(95, known['potential'])
        self.assertEqual(players, fixture.s.teams)
        self.assertEqual(free, fixture.c.free)
        self.assertEqual(state, random.getstate())


if __name__ == '__main__': unittest.main()
