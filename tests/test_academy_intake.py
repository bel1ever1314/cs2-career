"""Focused intake/rollover fixtures, not a full-season playability verdict."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cs2career.application import ApplicationState
from cs2career.career import Career
from cs2career.career.career import _signed
from cs2career.career.transfers import candidates
from cs2career.world.academy import intake, load_names
from cs2career.world.aging import apply_player_year


class AcademyGeneratorTests(unittest.TestCase):
    def test_two_each_year_plus_wonder_in_career_year_three_seven_eleven(self):
        used = []
        for year in range(2027, 2037):
            rows = intake(year, 2026, used, set())
            wonder = year in (2028, 2032, 2036)
            self.assertEqual(3 if wonder else 2, len(rows))
            self.assertEqual(int(wonder), sum(p['note'] == 'wonder' for p in rows))
            self.assertTrue(all(16 <= p['age'] <= 18 for p in rows))
            self.assertTrue(all(p['academy_year'] == year for p in rows))
            self.assertEqual(rows, intake(year, 2026, used, set()))
            used.extend(p['name'] for p in rows)
        self.assertEqual(len(used), len(set(used)))

    def test_aliases_used_hidden_or_rostered_cannot_spawn_a_duplicate_id(self):
        with patch('cs2career.world.academy.load_names', return_value=['KYRO','Kyro','vael','VAEL','nexu','krynn']):
            rows = intake(2028, 2026, [' kyro '], {' VAEL '})
        self.assertEqual(['nexu','krynn'], [p['name'] for p in rows])

    def test_fixed_pool_exhaustion_is_finite_and_does_not_recycle(self):
        self.assertEqual([], intake(2066, 2026, load_names(), set()))

    def test_signing_preserves_intake_and_potential_actually_affects_growth(self):
        talent = intake(2028, 2026, [], set())[0]
        signed = _signed(deepcopy(talent))
        for field in ('player_id','note','academy_year','potential','age','region'):
            self.assertEqual(talent[field], signed[field])
        ordinary = deepcopy(signed)
        ordinary.pop('potential')
        apply_player_year(signed)
        apply_player_year(ordinary)
        self.assertGreater(signed['ability'], ordinary['ability'])


class AcademyRolloverTests(unittest.TestCase):
    def test_rollover_market_ai_ownership_and_reload_do_not_duplicate_intake(self):
        with ExitStack() as stack:
            root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
            stack.enter_context(patch('cs2career.league.season.STATE_PATH', root/'season.json'))
            stack.enter_context(patch.object(Career,'path',return_value=root/'career.json'))
            stack.enter_context(patch('cs2career.paths.save_root',return_value=root))
            state = ApplicationState()
            state.create_career(dict(era='2026',mode='create',origin='academy',
                name='Academy Tester',org='Academy Club',region='AS',role='rifle'))
            # End-of-season fixture: exercise the actual rollover/tick and AI
            # window, without claiming all preceding matches have been played.
            state.season.events = []
            state.season.roll_year()
            self.assertEqual(2, len(state.career.academy_used))
            self.assertEqual(2027, state.career.last_age_year)
            quotes = [p for p in candidates(state.career,state.season) if p.get('academy_year') == 2027]
            self.assertEqual(2, len(quotes))  # Includes any recruits signed by AI.
            self.assertTrue(all(p['note']=='academy' and p['potential'] for p in quotes))
            state.persist()
            restored = ApplicationState()
            before = deepcopy(restored.career.academy_used)
            restored.career.tick(restored.season, restored.season.date)
            restored.sync()
            self.assertEqual(before, restored.career.academy_used)
            restored.season.events = []
            restored.season.roll_year()
            all_people = restored.career.free + [p for t in restored.season.teams for p in t['players']]
            third = [p for p in all_people if p.get('academy_year') == 2028]
            self.assertEqual(3, len(third))
            self.assertEqual(1, sum(p['note']=='wonder' for p in third))
            self.assertEqual(5, len(restored.career.academy_used))
            ids = [p['player_id'] for p in all_people if p.get('academy_year')]
            self.assertEqual(len(ids), len(set(ids)))
