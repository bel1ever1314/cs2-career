import unittest
from copy import deepcopy
from cs2career.career.quick_report import series_report
from cs2career.presentation import aggregate


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
