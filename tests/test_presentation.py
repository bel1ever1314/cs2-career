"""Regression tests for the read-only desktop detail contract."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from cs2career import presentation
from cs2career.league import awards
from cs2career.engine.rating import career_rating


class PresentationTests(unittest.TestCase):
    def match_state(self):
        p = lambda n: {'player_id': n, 'name': n, 'k': 10, 'd': 8, 'a': 2, 'damage': 1100, 'kast_rounds': 12, 'rating': 9.99}
        match = {'id': 'match-one', 'team_a': 'A', 'team_b': 'B', 'played': True, 'winner': 'A', 'series': '2-0', 'date': '2026-02-01',
                 'maps': [{'map': 'mirage', 'rounds': 20, 'score': '13-7', 'players': {'A': [p('a'+str(i)) for i in range(5)], 'B': [p('b'+str(i)) for i in range(5)]},
                           'events': [{'round': 1, 'type': 'kill', 'killer': 'a0', 'victim': 'b0'}, {'round': 1, 'type': 'round_end', 'winner': 'a'}]}]}
        event = {'id': 'old-event', 'name': 'Old Cup', 'matches': [match], 'dates': ['2026-02-01'], 'type': 't1'}
        season = SimpleNamespace(events=[], history=[event], is_yours=lambda m: False)
        state = SimpleNamespace(season=season)
        return state, match

    def test_archived_match_is_readable_and_never_mutated(self):
        state, match = self.match_state()
        before = deepcopy(match)
        result = presentation.match_detail(state, match['id'])['match']
        self.assertEqual(match, before)
        self.assertTrue(result['data_complete'])
        self.assertEqual(10, len(result['totals']))
        self.assertEqual(career_rating(10, 8, 2, 1100, 12, 20), result['totals'][0]['rating'])
        self.assertEqual('A', result['maps'][0]['round_history'][0]['winner'])

    def test_missing_rows_are_not_filled(self):
        state, match = self.match_state()
        match['maps'][0]['players']['B'].pop()
        result = presentation.match_detail(state, match['id'])['match']
        self.assertFalse(result['data_complete'])
        self.assertEqual(9, len(result['totals']))

    def test_missing_damage_is_not_presented_as_measured_rating(self):
        row = {'k': 3, 'd': 4, 'a': 1}
        result = presentation.aggregate([(row, 20)])
        self.assertIsNone(result['rating'])
        self.assertIsNone(result['adr'])

    def test_unequal_maps_aggregate_raw_rounds(self):
        a = {'k': 20, 'd': 10, 'a': 4, 'damage': 1900, 'kast_rounds': 15}
        b = {'k': 5, 'd': 12, 'a': 1, 'damage': 450, 'kast_rounds': 5}
        result = presentation.aggregate([(a, 25), (b, 13)])
        self.assertEqual(career_rating(25,22,5,2350,20,38), result['rating'])
        self.assertEqual(38, result['rounds'])

    def test_archive_keeps_independent_match_snapshot(self):
        state, match = self.match_state()
        ev = state.season.history[0]
        record = awards.make_record(ev)
        match['maps'][0]['score'] = 'changed'
        self.assertEqual('13-7', record['matches'][0]['maps'][0]['score'])

    def test_graph_only_connects_saved_progression(self):
        state, match = self.match_state()
        match.update(stage='QF')
        later = {**deepcopy(match), 'id': 'final', 'stage': 'GF', 'team_b': 'C', 'played': False, 'winner': None}
        state.season.history[0]['matches'].append(later)
        event = presentation.event_detail(state, 'old-event')
        self.assertEqual([{'source':'2026::match-one','target':'2026::final','team':'A','outcome':'winner'}], event['links'])

    def test_design_fixture_really_contains_all_three_formats(self):
        from cs2career.design_preview import fixture
        from cs2career.career import Career
        # This fixture creates no files; prevent writes if its implementation changes.
        with patch.object(Career, 'save'):
            state = fixture()
        for ev in state.season.events[:3]:
            self.assertEqual(ev['format'], ev['resolved_format'])
            stages = {m['stage'] for m in ev['matches']}
            self.assertIn('GF', stages)
            if ev['format'] == 'gsl_playoff':
                self.assertTrue({'G1','G2','G3'} <= stages)
                self.assertEqual(16, len(ev['field']))
            elif ev['format'] == 'swiss_playoff':
                self.assertTrue({'SW1','SW2','SW3','SW4','SW5'} <= stages)
                self.assertEqual(16, len(ev['field']))


if __name__ == '__main__':
    unittest.main()
