from application_double import ApplicationDouble
"""Career venue scenes, sourced names and read-only legacy projections."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from tools.career3d_venues import VENUE_POLICY_VERSION, attendance_for, venue_for


class CareerVenuePolicyTests(unittest.TestCase):
    def setUp(self):
        self.teams = [dict(name=f'Team{team}', players=[
            dict(name=f'Player {team}-{slot}', player_id=f'p{team}_{slot}', role='rifle')
            for slot in range(5)]) for team in range(2)]
        self.match = dict(id='fixture-1', date='2026-06-21', stage='G1',
                          team_a='Team0', team_b='Team1', played=False)
        self.event = dict(id='ordinary-event', name='Ordinary Cup 2026', type='t1')
        self.season = SimpleNamespace(year=2026, date='2026-06-21', teams=self.teams,
            is_yours=lambda match: 'Team0' in (match['team_a'], match['team_b']),
            yours_ready=lambda match: not match.get('played'),
            your_team_name=lambda: 'Team0')
        self.state = ApplicationDouble(season=self.season,
            career=SimpleNamespace(my_team=lambda teams: teams[0]),
            arena=SimpleNamespace(career_player_id=lambda state: 'p0_0'))

    def venue(self):
        return venue_for(self.state, self.event, self.match)

    def test_other_events_have_ten_computer_early_stage_rooms(self):
        for kind in ('t1', 't2', 'major'):
            for stage, phase in (('G1', 'groups'), ('G2', 'groups'),
                                 ('SW5', 'swiss'), ('M3-SW4', 'swiss')):
                with self.subTest(kind=kind, stage=stage):
                    self.event['type'] = kind
                    self.match.update(stage=stage, phase=phase)
                    venue = self.venue()
                    self.assertEqual(('studio', 'lan', True),
                        (venue['scale'], venue['visit_destination'], venue['travel_allowed']))
                    self.assertEqual('小型赛场', venue['display_name'])
                    self.assertEqual(10, len(venue['players_a']) + len(venue['players_b']))
                    self.assertEqual('', venue['name'])
                    self.assertFalse(venue['verified'])
                    self.assertEqual(VENUE_POLICY_VERSION, venue['venue_policy_version'])

    def test_all_elimination_rounds_route_to_large_arenas(self):
        for stage in ('R16', 'QF', 'SF', 'GF'):
            with self.subTest(stage=stage):
                self.match['stage'] = stage
                venue = self.venue()
                self.assertEqual(('arena', 'major', True),
                    (venue['scale'], venue['visit_destination'], venue['travel_allowed']))
                self.assertEqual('大型场馆', venue['display_name'])
                self.assertEqual('playoffs', venue['real_venue_phase'])
                self.assertEqual('playoff_arena', venue['venue_policy'])
        self.match.update(stage='custom-knockout', phase='playoff')
        self.assertEqual('arena', self.venue()['scale'])

    def test_qualifier_and_cct_level_events_stay_online_even_for_finals(self):
        for kind, name in (('qual', 'Open Qualifier'), ('cct', 'CCT Europe Series'),
                           ('t2', 'ESL Challenger League Season 51')):
            for stage in ('G1', 'QF', 'SF', 'GF'):
                with self.subTest(kind=kind, stage=stage):
                    self.event.update(type=kind, name=name)
                    self.match['stage'] = stage
                    venue = self.venue()
                    self.assertEqual(('online', 'club', False),
                        (venue['scale'], venue['visit_destination'], venue['travel_allowed']))
                    self.assertEqual('俱乐部训练室', venue['display_name'])
                    self.assertTrue(attendance_for(self.state, self.event, self.match)['can_travel'])

    def test_event_advancing_to_playoffs_does_not_relabel_its_previous_groups(self):
        self.event['phase'] = 'playoff'
        self.match.update(stage='G2', phase='groups', meta=dict(kind='elim'))
        self.assertEqual('studio', self.venue()['scale'])

    def test_real_names_keep_exact_year_and_phase_while_scene_policy_is_independent(self):
        self.event.update(id='blast-open-1', name='BLAST Premier Open Rotterdam 2026')
        early = self.venue()
        self.assertEqual('BLAST Copenhagen studios', early['name'])
        self.assertEqual(('Copenhagen', 'Denmark'), (early['city'], early['country']))
        self.match['stage'] = 'GF'
        final = self.venue()
        self.assertEqual('Ahoy Arena', final['name'])
        self.assertEqual('arena', final['real_venue_scale'])
        self.event.update(id='blast-bounty', name='BLAST Premier Bounty Season 1 2026')
        self.match['stage'] = 'G1'
        early = self.venue()
        self.assertEqual(('online', 'online'), (early['scale'], early['real_venue_scale']))
        self.match['stage'] = 'GF'
        final = self.venue()
        self.assertEqual(('arena', 'studio'), (final['scale'], final['real_venue_scale']))
        self.assertEqual('BLAST Studio, Malta', final['real_venue_name'])
        self.assertTrue(final['source_url'])
        self.season.year = 2027
        self.assertEqual('', self.venue()['name'])
        self.assertFalse(self.venue()['verified'])

    def test_bounty_online_phases_override_generic_stage_policy(self):
        for year in (2025, 2026):
            self.season.year = year
            self.event.update(id='blast-bounty', name=f'BLAST Premier Bounty Season 1 {year}')
            for stage in ('G1', 'G2', 'R32', 'RO32', 'R16', 'RO16'):
                with self.subTest(year=year, stage=stage):
                    self.match.update(stage=stage, phase='playoff' if stage.startswith('R') else 'groups')
                    venue = self.venue()
                    self.assertEqual(('online', 'club', False, False),
                        (venue['scale'], venue['destination'], venue['should_walk'], venue['travel_allowed']))
                    self.assertEqual('verified_online_phase', venue['venue_policy'])
                    self.assertEqual('俱乐部训练室', venue['display_name'])
            for stage in ('QF', 'SF', 'GF'):
                self.match.update(stage=stage, phase='playoff')
                self.assertEqual(('arena', 'major', True),
                    tuple(self.venue()[key] for key in ('scale', 'destination', 'should_walk')))
        self.match.update(stage='G1', phase='groups')
        self.event['name'] = 'Different Cup 2026'
        self.assertEqual('lan', self.venue()['destination'])
        self.season.year = 2027
        self.event['name'] = 'BLAST Premier Bounty Season 1 2027'
        self.assertEqual('lan', self.venue()['destination'])

    def test_frozen_bounty_lan_becomes_online_without_changing_progress(self):
        saved = self.venue()
        self.season.year = 2025
        self.event.update(id='blast-bounty', name='BLAST Premier Bounty Season 1 2025')
        self.match.update(career3d_venue=saved, veto={'order':['dust2', 'nuke', 'mirage']},
                          maps=[{'map':'dust2', 'score':[13, 8]}])
        before = deepcopy(self.match)
        venue = self.venue()
        self.assertEqual(('club', False, False),
            (venue['destination'], venue['is_lan'], venue['should_walk']))
        self.assertEqual('club', attendance_for(self.state, self.event, self.match)['destination'])
        for key in ('players_a', 'players_b', 'human_id', 'match_identity'):
            self.assertEqual(saved[key], venue[key])
        self.assertEqual(before, self.match)

    def test_legacy_unknown_online_projection_keeps_frozen_ids_after_transfer_changes(self):
        original = self.venue()
        original.update(scale='unknown', is_lan=False, destination='lan',
                        travel_allowed=False, visit_destination='club', should_walk=False)
        for key in ('venue_policy_version', 'venue_policy', 'real_venue_scale', 'real_venue_name'):
            original.pop(key, None)
        self.match['career3d_venue'] = deepcopy(original)
        saved_before = deepcopy(self.match)
        self.teams[0]['players'][1].update(name='Later replacement', player_id='new-person')
        venue = self.venue()
        self.assertEqual('studio', venue['scale'])
        self.assertTrue(venue['travel_allowed'])
        for key in ('players_a', 'players_b', 'human_id', 'own_team', 'team_a', 'team_b',
                    'match_id', 'match_identity', 'event_id'):
            self.assertEqual(original[key], venue[key])
        self.assertEqual('frozen_match_rosters', venue['identity_source'])
        self.assertEqual(saved_before, self.match)
        self.match['stage'] = 'GF'
        self.assertEqual('arena', self.venue()['scale'])
        self.assertEqual(original['players_a'], self.venue()['players_a'])

    def test_legacy_lan_qualifier_corrects_to_online_without_modifying_saved_record(self):
        self.event['type'] = 'qual'
        self.match['stage'] = 'GF'
        saved = self.venue()
        saved.update(scale='arena', is_lan=True, destination='major',
                     visit_destination='major', venue_policy_version='old-version')
        self.match['career3d_venue'] = saved
        before = deepcopy(self.match)
        projected = self.venue()
        self.assertEqual(('online', 'club', False),
            (projected['scale'], projected['visit_destination'], projected['should_walk']))
        self.assertEqual(before, self.match)

    def test_scene_policy_does_not_bypass_missing_rosters_or_completed_match(self):
        self.match['stage'] = 'GF'
        self.teams[1]['players'][0]['player_id'] = 'p0_0'
        invalid = self.venue()
        self.assertEqual('arena', invalid['scale'])
        self.assertFalse(invalid['roster_complete'])
        self.assertFalse(invalid['travel_allowed'])
        self.teams[1]['players'][0]['player_id'] = 'p1_0'
        self.match['played'] = True
        completed = self.venue()
        self.assertFalse(completed['should_walk'])
        self.assertFalse(attendance_for(self.state, self.event, self.match)['can_travel'])


if __name__ == '__main__':
    unittest.main()
