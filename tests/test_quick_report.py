import unittest
from copy import deepcopy
from cs2career.career.quick_report import series_report, round_report
from cs2career.presentation import aggregate
from cs2career.engine.match import RNG, play_round_event_stream, event_box_score


class QuickReportTests(unittest.TestCase):
    def fixture(self):
        def mp(rounds, kills):
            return dict(rounds=rounds, players={team:[dict(player_id=f'{team}{i}',name='same-name',
                k=kills,d=9,a=3,damage=kills*80,kast_rounds=rounds-2) for i in range(5)] for team in ('A','B')})
        return dict(team_a='A',team_b='B',played=True,winner='B',maps=[mp(20,10),mp(30,24)])

    def test_unequal_maps_are_aggregated_not_averaged_and_player_is_stable(self):
        match=self.fixture();before=deepcopy(match)
        result=series_report(match,'B2','B')
        self.assertEqual(before,match)
        self.assertTrue(result['data_complete']);self.assertEqual(10,len(result['totals']))
        player=next(p for p in result['totals'] if p['player_id']=='B2')
        expected=aggregate([(mp['players']['B'][2],mp['rounds']) for mp in match['maps']])
        self.assertEqual(34,player['k']);self.assertEqual(50,player['rounds'])
        for key in ('adr','kast','rating'):self.assertEqual(expected[key],player[key])
        self.assertEqual('B2',result['player_id']);self.assertEqual('B',result['player_team'])

    def test_missing_map_identity_is_not_guessed_from_same_names(self):
        match=self.fixture();match['maps'][1]['players']['B'][2].pop('player_id')
        result=series_report(match,'B2','B')
        self.assertFalse(result['data_complete'])
        self.assertEqual(10,next(p for p in result['totals'] if p['player_id']=='B2')['k'])
        match['maps']=[]
        result=series_report(match,'B2','B')
        self.assertFalse(result['data_complete']);self.assertEqual([],result['totals'])

    def round_fixture(self):
        teams = ('A', 'B')
        rosters = [[dict(player_id=f'{team}{i}', name=f'{team} player {i}',
            ability=80, frag=1, tier='主力') for i in range(5)] for team in teams]
        RNG.seed(3106)
        a, b, events, ledger = play_round_event_stream(*rosters, .55)
        mp = dict(rounds=a+b, score=f'{a}-{b}', events=events,
            players={team: event_box_score(rows, ledger, a+b) for team, rows in zip(teams, rosters)})
        rounds = [e['winner'] for e in events if e['type'] == 'round_end']
        return mp, teams, rounds

    def test_round_projection_matches_saved_ten_person_measurements(self):
        mp, teams, rounds = self.round_fixture()
        before = deepcopy(mp); rng_before = RNG.getstate()
        report = round_report(mp, teams, rounds)
        self.assertEqual(before, mp); self.assertEqual(rng_before, RNG.getstate())
        self.assertTrue(report['round_stats_available']); self.assertTrue(report['round_damage_available'])
        self.assertEqual(len(rounds), len(report['round_frames']))
        for frame in report['round_frames']:
            self.assertEqual(10, len(frame['players']))
            self.assertTrue(frame['highlights'])
        final = {p['player_id']: p for p in report['round_frames'][-1]['players']}
        for row in [p for rows in mp['players'].values() for p in rows]:
            for field in ('k', 'd', 'a', 'damage', 'kast_rounds', 'adr', 'kast', 'rating'):
                self.assertEqual(row[field], final[row['player_id']][field], field)
        report['round_frames'][0]['events'][0]['killer'] = 'changed only in projection'
        self.assertEqual(before, mp)

    def test_old_assist_damage_is_never_guessed_for_live_rates(self):
        mp, teams, rounds = self.round_fixture()
        for event in mp['events']:
            event.pop('assist_damage', None)
        report = round_report(mp, teams, rounds)
        self.assertTrue(report['round_stats_available']); self.assertFalse(report['round_damage_available'])
        self.assertIn('助攻伤害', report['round_stats_reason'])
        for frame in report['round_frames']:
            for row in frame['players']:
                self.assertIsNone(row['adr']); self.assertIsNone(row['rating']); self.assertIsNone(row['damage'])
                self.assertIsInstance(row['k'], int); self.assertIsInstance(row['kast'], float)

    def test_partial_or_ambiguous_events_do_not_establish_live_stats(self):
        mp, teams, rounds = self.round_fixture()
        mp['events'] = [e for e in mp['events'] if e['type'] == 'round_end']
        report = round_report(mp, teams, rounds)
        self.assertFalse(report['round_stats_available'])
        self.assertTrue(all(not frame['players'] and not frame['highlights'] for frame in report['round_frames']))
        mp, teams, rounds = self.round_fixture()
        mp['players']['B'][0]['name'] = mp['players']['A'][0]['name']
        self.assertFalse(round_report(mp, teams, rounds)['round_stats_available'])
        self.assertEqual([], round_report(mp, teams, [])['round_frames'])

    def test_rts_round_deltas_use_stable_ids_even_with_shared_nicknames(self):
        teams = ('A', 'B')
        roster = {team: [dict(player_id=f'{team}{i}', name='shared nickname', k=26 if team == 'A' and i == 0 else 0,
            d=13 if team == 'B' and i in (0, 1) else 0, a=0, damage=2600 if team == 'A' and i == 0 else 0,
            kast_rounds=0 if team == 'B' and i in (0, 1) else 13) for i in range(5)] for team in teams}
        history = [dict(round=n, winner='A', reason='elimination', players=[dict(id=f'{team}{i}',
            team='ct' if team == 'A' else 't', k=2 if team == 'A' and i == 0 else 0,
            d=1 if team == 'B' and i in (0, 1) else 0, a=0, damage=200 if team == 'A' and i == 0 else 0,
            opening_kills=1 if team == 'A' and i == 0 else 0, opening_deaths=1 if team == 'B' and i == 0 else 0,
            survived=not(team == 'B' and i in (0, 1)), kast=not(team == 'B' and i in (0, 1)), traded=False)
            for team in teams for i in range(5)]) for n in range(1, 14)]
        mp = dict(players=roster, rts_round_history=history, events=[])
        original = deepcopy(mp)
        report = round_report(mp, teams, ['a'] * 13)
        self.assertTrue(report['round_stats_available']); self.assertTrue(report['round_damage_available'])
        first = next(p for p in report['round_frames'][0]['players'] if p['player_id'] == 'A0')
        final = next(p for p in report['round_frames'][-1]['players'] if p['player_id'] == 'A0')
        self.assertEqual((2, 200, 200.0, 1.0), (first['k'], first['damage'], first['adr'], first['kast']))
        self.assertEqual((26, 2600), (final['k'], final['damage']))
        self.assertEqual(original, mp)
        for rd in mp['rts_round_history']:
            for player in rd['players']:
                for field in ('k', 'd', 'a', 'damage', 'opening_kills', 'opening_deaths'):
                    player[field] = float(player[field])
        self.assertTrue(round_report(mp, teams, ['a'] * 13)['round_stats_available'])
        mp['rts_round_history'][0]['players'][0]['id'] = 'unknown'
        self.assertFalse(round_report(mp, teams, ['a'] * 13)['round_stats_available'])
