import json
import unittest

from cs2career.engine.rules import COMPETITIVE
from cs2career.engine.match import RNG, play_round_event_stream
from cs2career.paths import data_file


class MatchRulesTests(unittest.TestCase):
    def test_simulation_identity_is_stable_distinct_and_does_not_consume_rng(self):
        from cs2career.engine.sessions import stamp_simulation
        before = RNG.getstate()
        first = stamp_simulation({}, 'career', 2026, 'event', 'match', 0)
        self.assertEqual(first, stamp_simulation({}, 'career', 2026, 'event', 'match', 0))
        self.assertNotEqual(first['session_id'], stamp_simulation({}, 'career', 2026, 'event', 'match', 1)['session_id'])
        self.assertEqual(COMPETITIVE.id, first['rules_id'])
        self.assertEqual(before, RNG.getstate())

    def test_shared_examples(self):
        fixtures = json.loads(data_file('match_rules.json').read_text('utf-8'))
        for a, b in fixtures['final_scores']:
            self.assertTrue(COMPETITIVE.final_score(a, b), (a, b))
            self.assertTrue(COMPETITIVE.final_score(b, a), (b, a))
        for a, b in fixtures['nonfinal_scores']:
            self.assertFalse(COMPETITIVE.final_score(a, b), (a, b))

    def test_overtime_stops_at_clinching_round_including_known_seed_33(self):
        checkpoint = RNG.getstate()
        self.addCleanup(RNG.setstate, checkpoint)
        rows = lambda side: [dict(name=f'{side}{n}', ability=80, frag=1) for n in range(5)]
        for seed in range(80):
            RNG.seed(seed)
            a, b, events, stats = play_round_event_stream(rows('A'), rows('B'), .5)
            self.assertTrue(COMPETITIVE.final_score(a, b), (seed, a, b))
            score = [0, 0]
            ends = [event for event in events if event['type'] == 'round_end']
            self.assertEqual(a + b, len(ends))
            for i, event in enumerate(ends):
                score[event['winner'] == 'b'] += 1
                self.assertEqual(i == len(ends) - 1, COMPETITIVE.decided(*score))
            for row in stats.values():
                self.assertEqual(a + b, row['d'] + row['survived_rounds'])

    def test_cs2_config_uses_same_format(self):
        self.assertIn('mp_maxrounds 24', COMPETITIVE.cs2_commands())
        self.assertIn('mp_overtime_maxrounds 6', COMPETITIVE.cs2_commands())
