from copy import deepcopy
from types import SimpleNamespace
import unittest

from cs2career import presentation
import test_presentation as fixtures


class HistoryIdentityTests(unittest.TestCase):
    def repeated_seasons(self):
        state, old_match = fixtures.PresentationTests().match_state()
        current = deepcopy(state.season.history[0])
        current['dates'] = ['2027-02-01']
        current['matches'][0]['date'] = '2027-02-01'
        current['matches'][0]['maps'][0]['score'] = '13-9'
        state.season.events = [current]
        return state, old_match

    def test_repeated_event_ids_keep_both_seasons(self):
        state, _ = self.repeated_seasons()
        rows = presentation.events(state.season)
        self.assertEqual(2, len(rows))
        self.assertEqual(2, len({r['id'] for r in rows}))

    def test_qualified_links_resolve_old_and_current_matches(self):
        state, original = self.repeated_seasons()
        before = deepcopy(original)
        old_event = presentation.event_detail(state, '2026::old-event')
        new_event = presentation.event_detail(state, '2027::old-event')
        for ev, expected in [(old_event, '13-7'), (new_event, '13-9')]:
            self.assertIsNotNone(ev)
            detail = presentation.match_detail(state, ev['matches'][0]['id'])
            self.assertEqual(expected, detail['match']['maps'][0]['score'])
            self.assertEqual(ev['id'], detail['event']['id'])
        self.assertEqual(before, original)
        # Compatibility commands still use this season's original engine ID.
        self.assertEqual('match-one', presentation.match_detail(state, '2027::match-one')['match']['id'])

    def test_current_legacy_link_wins_and_ambiguous_old_link_is_not_guessed(self):
        state, _ = self.repeated_seasons()
        self.assertEqual('13-9', presentation.match_detail(state, 'match-one')['match']['maps'][0]['score'])
        state.season.history.append(state.season.events.pop())
        self.assertIsNone(presentation.match_detail(state, 'match-one'))

    def test_ten_rows_without_damage_or_unique_ids_are_incomplete(self):
        state, match = fixtures.PresentationTests().match_state()
        del match['maps'][0]['players']['A'][0]['damage']
        self.assertFalse(presentation.match_detail(state, 'match-one')['match']['data_complete'])
        state, match = fixtures.PresentationTests().match_state()
        match['maps'][0]['players']['A'][1]['player_id'] = 'a0'
        self.assertFalse(presentation.match_detail(state, 'match-one')['match']['data_complete'])

    def test_retired_player_can_open_saved_stats_without_fabricated_attributes(self):
        state, match = fixtures.PresentationTests().match_state()
        state.season.teams = []
        state.season.date, state.season.year = '2027-01-08', 2027
        state.season.top20 = {}
        state.season.records = lambda **kwargs: []
        state.career = SimpleNamespace(free=[])
        result = presentation.inspect(state, 'player', 'a0', span='all')
        self.assertTrue(result['historical'])
        self.assertIsNone(result['ability'])
        self.assertIsNone(result['age'])
        self.assertEqual(1, result['summary']['maps'])
        self.assertEqual('2026::match-one', result['recent'][0]['match_id'])
        match['maps'][0]['players']['B'][0]['name'] = 'a0'
        # Stable ID a0 remains unambiguous; name-only alias with two other IDs does not.
        self.assertEqual(1, presentation.inspect(state, 'player', 'a0', span='all')['summary']['maps'])
        for side in ('A', 'B'):
            match['maps'][0]['players'][side][0]['name'] = 'same-alias'
        self.assertIsNone(presentation.inspect(state, 'player', 'same-alias', span='all'))

    def test_archived_awards_are_read_from_saved_summary(self):
        state, _ = self.repeated_seasons()
        state.season.history[0]['mvp'] = {'player': 'a0', 'rating': 1.4}
        old = presentation.event_detail(state, '2026::old-event')
        self.assertEqual('a0', old['awards']['mvp']['player'])
        self.assertEqual('done', old['status'])
