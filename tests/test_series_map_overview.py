"""The match page names every map of a series and which one is being played."""
from types import SimpleNamespace
import unittest

from cs2career.services.matches import series_maps


def state(own='Alpha'):
    return SimpleNamespace(season=SimpleNamespace(your_team_name=lambda: own))


def bo3(**extra):
    veto = {'best_of': 3, 'order': ['mirage', 'train', 'nuke'], 'steps': [
        {'team': 'Alpha', 'action': 'ban', 'map': 'inferno'},
        {'team': 'Beta', 'action': 'ban', 'map': 'dust2'},
        {'team': 'Alpha', 'action': 'pick', 'map': 'mirage', 'play': 1},
        {'team': 'Beta', 'action': 'pick', 'map': 'train', 'play': 2},
        {'team': None, 'action': 'decider', 'map': 'nuke', 'play': 3}]}
    return {'id': 'm1', 'team_a': 'Alpha', 'team_b': 'Beta', 'best_of': 3, 'veto': veto, 'maps': [], **extra}


class SeriesMapOverviewTests(unittest.TestCase):
    def test_waiting_map_is_live_not_next(self):
        match = bo3(maps=[{'map': 'mirage', 'score': '13-9', 'winner': 'Alpha'}],
                    cs2_session={'map_index': 1, 'side': 't', 'cs2_map': 'de_train'})
        rows = series_maps(state(), match)
        self.assertEqual(['done', 'live', 'upcoming'], [row['state'] for row in rows])
        self.assertEqual(('de_train', 't', 'Beta'), (rows[1]['cs2_map'], rows[1]['side'], rows[1]['picked_by']))
        self.assertTrue(rows[0]['won'])
        self.assertTrue(rows[2]['decider'])

    def test_before_launch_the_current_map_is_next(self):
        rows = series_maps(state(), bo3())
        self.assertEqual(['next', 'upcoming', 'upcoming'], [row['state'] for row in rows])
        self.assertEqual([1, 2, 3], [row['index'] for row in rows])

    def test_scores_read_from_the_players_side_and_decided_series_skips_the_rest(self):
        match = bo3(maps=[{'map': 'mirage', 'score': '13-9', 'winner': 'Alpha'},
                          {'map': 'train', 'score': '13-5', 'winner': 'Alpha'}])
        rows = series_maps(state('Beta'), match)
        self.assertEqual(('9-13', False), (rows[0]['score'], rows[0]['won']))
        self.assertEqual('unneeded', rows[2]['state'])

    def test_unfinished_manual_veto_shows_no_order(self):
        match = bo3(career3d_veto={'plan': [{}] * 7, 'complete': False})
        match['veto']['steps'] = match['veto']['steps'][:2]
        self.assertEqual([], series_maps(state(), match))


if __name__ == '__main__':
    unittest.main()
