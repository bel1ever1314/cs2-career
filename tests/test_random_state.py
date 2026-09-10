"""A reload must resume both streams, not reseed the next match or draw."""
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from cs2career.application import ApplicationState
from cs2career.career import Career
from cs2career.engine.match import RNG, play_series
from cs2career.random_state import capture, restore


class RandomCheckpointTests(unittest.TestCase):
    def setUp(self):
        checkpoint = capture()
        self.addCleanup(restore, checkpoint)

    def test_json_roundtrip_keeps_gaussian_cache_and_does_not_consume_rng(self):
        random.seed(51); RNG.seed(91)
        RNG.gauss(0, 1)
        checkpoint = capture()
        self.assertIsNotNone(checkpoint['match'][2])
        self.assertEqual(checkpoint, capture())
        expected = [random.random(), RNG.gauss(0, 1), RNG.random()]
        restore(json.loads(json.dumps(checkpoint)))
        self.assertEqual(expected, [random.random(), RNG.gauss(0, 1), RNG.random()])

    def test_bad_second_stream_does_not_partially_restore_first(self):
        original = capture()
        bad = deepcopy(original)
        bad['career'] = random.Random(89).getstate()
        bad['match'] = (3, (0,) * 625, float('nan'))
        with self.assertRaises(ValueError):
            restore(bad)
        self.assertEqual(original, capture())
        restore(None)
        self.assertEqual(original, capture())

    def test_save_reload_reproduces_full_next_series_and_career_draws(self):
        with ExitStack() as stack:
            root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
            stack.enter_context(patch('cs2career.league.season.STATE_PATH', root/'season.json'))
            stack.enter_context(patch.object(Career,'path',return_value=root/'career.json'))
            stack.enter_context(patch('cs2career.paths.save_root',return_value=root))
            state = ApplicationState()
            state.create_career(dict(era='2025',mode='create',origin='academy',
                name='Resume Tester',org='Resume Club',region='AS',role='rifle'))
            random.seed(51); RNG.seed(91)
            RNG.gauss(0, 1)
            state.persist()
            teams = deepcopy(state.season.teams[:2])
            expected = play_series(*teams, best_of=3, maps=['mirage','nuke','inferno'], stage='GF')
            decisions = [random.random() for _ in range(8)]
            # Simulate process startup with unrelated initial RNG state.
            random.seed(777); RNG.seed(999)
            restored = ApplicationState()
            actual = play_series(*deepcopy(restored.season.teams[:2]), best_of=3,
                                 maps=['mirage','nuke','inferno'], stage='GF')
            self.assertEqual(expected, actual)
            self.assertEqual(decisions, [random.random() for _ in range(8)])
