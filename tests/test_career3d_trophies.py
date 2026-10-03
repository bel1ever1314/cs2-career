from copy import deepcopy
from datetime import date
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from cs2career.career import Career
from cs2career.league import awards
from tools.career3d_trophies import _catalog, trophy_context


class ClubTrophyTests(unittest.TestCase):
    def setUp(self):
        self.c = Career()
        self.c.exists, self.c.team_id, self.c.player_name = True, 'vitality', 'You'
        self.c.you_card = dict(name='You', player_id='human')
        self.c.save = Mock()
        teams = [dict(id='vitality', name='Vitality', players=[dict(name='You', player_id='human', you=True)]),
                 dict(id='other', name='Other', players=[dict(name='OtherPerson', player_id='other')])]
        self.s = SimpleNamespace(date='2026-08-01', year=2026, events=[], history=[], teams=teams)
        self.state = SimpleNamespace(career=self.c, season=self.s,
            arena=SimpleNamespace(career_player_id=lambda state: 'human'))

    def event(self, **changes):
        event = dict(id='title', name='IEM Example 2026', short='IEM Example',
                     dates=['2026-07-20', '2026-07-25'], status='done', champion='Vitality',
                     champion_roster=['You'], type='t1', matches=[], awards={})
        event.update(changes)
        self.s.events.append(event)
        return event

    def test_current_club_has_precareer_history_without_mutating_save(self):
        before = deepcopy((self.c.to_json(), self.s.__dict__))
        row = trophy_context(self.state)
        self.assertGreater(row['historical_total'], 2)
        self.assertEqual('2026-01-01', row['historical_cutoff'])
        self.assertTrue(any(title['event'] == 'BLAST.tv Paris Major 2023' for title in row['rows']))
        self.assertTrue(all(title['historical'] and not title['player_earned'] for title in row['rows']))
        self.assertEqual([], row['personal_rows'])
        row['rows'][0]['event'] = 'Changed'
        self.assertEqual(before, (self.c.to_json(), self.s.__dict__))
        self.c.save.assert_not_called()

    def test_historical_titles_never_import_real_future_of_earlier_start(self):
        self.c.start_year = 2024
        row = trophy_context(self.state)
        self.assertTrue(row['rows'])
        self.assertTrue(all(title['date'] < '2024-01-01' for title in row['rows']))
        self.assertFalse(any('Cologne 2024' in title['event'] or '2025' in title['event'] for title in row['rows']))
        self.c.start_year = 2025
        self.assertTrue(any('Cologne 2024' in title['event'] for title in trophy_context(self.state)['rows']))
        self.assertFalse(any('2025' in title['event'] for title in trophy_context(self.state)['rows']))

    def test_player_title_added_to_current_club_and_personal_rows(self):
        self.event(champion_roster_ids=['human'])
        row = trophy_context(self.state)
        self.assertEqual(1, row['saved_total'])
        self.assertEqual(1, row['player_total'])
        self.assertEqual(1, row['current_club_player_total'])
        self.assertTrue(row['rows'][0]['player_earned'])

    def test_previous_employers_title_stays_personal_after_transfer(self):
        self.event(champion='Other', champion_roster_ids=['human'])
        row = trophy_context(self.state)
        self.assertEqual(0, row['saved_total'])
        self.assertEqual('Other', row['personal_rows'][0]['team'])
        self.assertEqual(0, row['current_club_player_total'])

    def test_new_employers_old_saved_titles_are_not_personal(self):
        self.event(champion_roster=['FormerPlayer'], champion_roster_ids=['former'])
        self.c.personal_transfers['moves'] = [dict(date='2026-07-30', to_team_id='vitality')]
        row = trophy_context(self.state)
        self.assertEqual(1, row['saved_total'])
        self.assertEqual(0, row['player_total'])
        self.assertFalse(row['rows'][0]['player_earned'])

    def test_frozen_map_identity_confirms_legacy_participation(self):
        self.event(champion_roster=[], matches=[dict(played=True, maps=[dict(players={'Vitality': [
            dict(name='Renamed', player_id='human')], 'Other': [dict(name='OtherPerson', player_id='other')]})])])
        row = trophy_context(self.state)
        self.assertEqual(1, row['player_total'])
        self.s.events[0]['champion'] = 'Other'
        self.assertEqual(0, trophy_context(self.state)['player_total'])

    def test_frozen_ids_override_conflicting_names_or_current_roster(self):
        self.event(champion_roster_ids=['impostor'])
        self.assertEqual(0, trophy_context(self.state)['player_total'])

    def test_legacy_frozen_winning_names_supported_only_for_unique_identity(self):
        self.event()
        self.assertEqual(1, trophy_context(self.state)['player_total'])
        self.s.teams[1]['players'].append(dict(name='You', player_id='namesake'))
        self.assertEqual(0, trophy_context(self.state)['player_total'])

    def test_qualification_future_unfinished_and_duplicate_records_not_trophies(self):
        self.event(id='qual', type='qual')
        self.event(id='notdone', status='live')
        self.event(id='future', dates=['2026-09-01', '2026-09-05'])
        event = self.event(champion_roster_ids=['human'])
        self.s.history.append(awards.make_record(event, include_matches=False))
        row = trophy_context(self.state)
        self.assertEqual(1, row['saved_total'])
        self.assertEqual(1, row['player_total'])

    def test_history_survives_rollover_without_current_roster_guess(self):
        record = awards.make_record(self.event(champion_roster_ids=['human']), include_matches=False)
        self.s.events, self.s.history, self.s.year, self.s.date = [], [record], 2027, '2027-01-08'
        self.c.team_id = 'other'
        self.assertEqual(1, trophy_context(self.state)['player_total'])
        self.assertEqual('Vitality', trophy_context(self.state)['personal_rows'][0]['team'])

    def test_frozen_record_copies_ids_and_keeps_old_format_compatible(self):
        event = self.event(champion_roster_ids=['human'])
        record = awards.make_record(event, include_matches=False)
        record['champion_roster_ids'].append('changed')
        self.assertEqual(['human'], event['champion_roster_ids'])
        del event['champion_roster_ids']
        self.assertNotIn('champion_roster_ids', awards.make_record(event, include_matches=False))

    def test_saved_import_owns_same_real_edition_instead_of_duplicate_seed(self):
        event = self.event(id='paris', name='BLAST.tv Paris Major 2023', dates=['2023-05-08', '2023-05-21'],
                           champion_roster_ids=['old'], champion_roster=['OldPlayer'], type='major')
        row = trophy_context(self.state)
        matches = [title for title in row['rows'] if title['event'] == event['name']]
        self.assertEqual(1, len(matches))
        self.assertFalse(matches[0]['historical'])

    def test_no_current_club_has_no_physical_club_titles_but_keeps_personal_titles(self):
        self.event(champion_roster_ids=['human'])
        self.c.team_id = ''
        row = trophy_context(self.state)
        self.assertEqual([], row['rows'])
        self.assertEqual(1, row['player_total'])

    def test_own_custom_club_has_no_manufactured_history(self):
        self.s.teams[0]['name'] = 'My club'
        row = trophy_context(self.state)
        self.assertEqual([], row['rows'])
        self.assertEqual(0, row['historical_total'])

    def test_common_club_historical_titles_use_actual_game_team_names(self):
        expected = {
            'Astralis': 'astralis-berlin-2019',
            'Liquid': 'liquid-cologne-2019',
            'MOUZ': 'mouz-epl19-2024',
            'fnatic': 'fnatic-cologne-2015',
            'NiP': 'nip-cologne-2014',
            'Virtus.pro': 'vp-katowice-2014',
            'Spirit': 'spirit-shanghai-2024',
            'FaZe': 'faze-epl17-2023',
        }
        for name, title_id in expected.items():
            with self.subTest(team=name):
                self.s.teams[0]['name'] = name
                row = trophy_context(self.state)
                self.assertIn('historical:' + title_id, {title['id'] for title in row['rows']})
                self.assertTrue(all(title['historical'] and not title['player_earned'] for title in row['rows']))
                self.assertEqual(0, row['player_total'])

    def test_new_history_uses_career_cutoff_not_current_save_year(self):
        for name, title_id in [('Spirit', 'spirit-shanghai-2024'), ('MOUZ', 'mouz-epl19-2024')]:
            with self.subTest(team=name):
                self.s.teams[0]['name'] = name
                self.c.start_year = 2024
                row = trophy_context(self.state)
                self.assertNotIn('historical:' + title_id, {title['id'] for title in row['rows']})
                self.c.start_year = 2025
                row = trophy_context(self.state)
                self.assertIn('historical:' + title_id, {title['id'] for title in row['rows']})

    def test_copenhagen_major_is_navi_title_not_faze(self):
        title = next(title for title in _catalog()['titles'] if title['id'] == 'navi-copenhagen-2024')
        self.assertEqual('NAVI', title['team'])
        self.s.teams[0]['name'] = 'FaZe'
        self.assertFalse(any('Copenhagen' in row['event'] for row in trophy_context(self.state)['rows']))

    def test_catalog_dates_unique_ids_and_sources_are_auditable(self):
        catalog = _catalog()
        ids = [title['id'] for title in catalog['titles']]
        self.assertEqual(len(ids), len(set(ids)))
        for title in catalog['titles']:
            date.fromisoformat(title['date'])
            self.assertIn(title['class'], ('major', 'premier', 't1', 't2'))
            self.assertTrue(catalog['sources'][title['source_id']].startswith('https://'))


if __name__ == '__main__':
    unittest.main()
