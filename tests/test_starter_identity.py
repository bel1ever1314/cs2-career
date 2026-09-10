"""No cloned active players in a new organisation, across independent eras."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from cs2career.career import Career
from cs2career.engine.match import RNG, play_map, play_series
from cs2career.league.season import Season
from cs2career.world.pool import starter_mates


class StarterIdentityTests(unittest.TestCase):
    def create(self, era, origin, name='Identity Rookie'):
        season = Season(int(era),era)
        career = Career(); career.save = lambda: None
        career.create({'era':era,'mode':'create','origin':origin,'role':'rifle',
                       'region':'AS','name':name,'org':'Identity Org'},season)
        return season, career

    def test_all_eras_and_origins_do_not_clone_active_ids(self):
        for era in ('2024','2025','2026'):
            for origin in ('street','academy','prodigy'):
                with self.subTest(era=era,origin=origin):
                    season, career = self.create(era,origin)
                    players = [p for t in season.teams for p in t['players']]
                    ids = [p['player_id'] for p in players]
                    names = [p['name'].strip().casefold() for p in players]
                    self.assertEqual(len(ids),len(set(ids)))
                    self.assertEqual(len(names),len(set(names)))
                    self.assertEqual(5,len(career.my_team(season.teams)['players']))

    def test_custom_name_also_excluded_from_starter_pool(self):
        with patch('cs2career.career.career.starter_mates',wraps=starter_mates) as picker:
            season, career = self.create('2025','prodigy','captainMo')
        self.assertIn('captainMo',picker.call_args.kwargs['skip'])
        names = [p['name'].casefold() for p in career.my_team(season.teams)['players']]
        self.assertEqual(1,names.count('captainmo'))

    def test_insufficient_available_candidates_are_not_silently_four_players(self):
        with patch('cs2career.career.career.starter_mates',return_value=[]):
            with self.assertRaisesRegex(ValueError,'不足'):
                self.create('2025','prodigy')

    def test_original_mongolz_match_has_ten_distinct_conserved_lines(self):
        season, career = self.create('2025','prodigy')
        mine = career.my_team(season.teams)
        other = next(t for t in season.teams if t['name']=='The MongolZ')
        result = play_map(mine,other,'mirage')
        lines = [p for rows in result['players'].values() for p in rows]
        self.assertEqual(10,len({p['player_id'] for p in lines}))
        self.assertEqual(sum(p['k'] for p in lines),sum(p['d'] for p in lines))
        self.assertTrue(all(p['kast_rounds'] <= result['rounds'] for p in lines))

    def test_invalid_roster_rejected_before_rng_or_team_mutation(self):
        season = Season(2025,'2025')
        a,b = deepcopy(season.teams[:2])
        for kind in ('id','name','short'):
            left,right = deepcopy(a),deepcopy(b)
            if kind == 'id':
                right['players'][0]['player_id'] = left['players'][0]['player_id']
            elif kind == 'name':
                right['players'][0]['name'] = ' '+left['players'][0]['name'].upper()+' '
            else:
                right['players'].pop()
            before = deepcopy((left,right)); rng = RNG.getstate()
            with self.assertRaises(ValueError):
                play_series(left,right,['mirage','nuke','inferno'],'GF')
            self.assertEqual(before,(left,right))
            self.assertEqual(rng,RNG.getstate())
