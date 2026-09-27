"""Major narrative choice comes from frozen ability and the personal ledger."""
from copy import deepcopy
from unittest import TestCase

from cs2career.career import major_reaction as major


class MajorReactionTests(TestCase):
    def setUp(self):
        self.teams = [dict(id=f't{i}', name=f'Team {i}', rank=33-i,
                           players=[dict(player_id=f'p{i}-{n}', name=f'Player {i}-{n}', ability=100-i)
                                    for n in range(5)]) for i in range(1, 33)]
        self.ev = dict(id='major', type='major', size=32, format='major_stages',
                       field=[t['name'] for t in self.teams], matches=[])
        major.freeze(self.ev, self.teams)
        self.key = '2026:major'

    def exit(self, rank, phase, wins=0, champion=False):
        ev=deepcopy(self.ev);team=self.teams[rank-1]
        base=dict(team_a=team['name'], team_b='Opponent', played=True, series='1-2')
        if phase.startswith('stage'):
            details=dict(stage=f'M{phase[-1]}-SW5', meta={'major_stage':int(phase[-1])})
        else:
            details=dict(stage={'quarter_final':'QF','semi_final':'SF','final':'GF'}[phase])
        for i in range(wins):
            ev['matches'].append(dict(base,id='win'+str(i),winner=team['name'],**details))
        ev['matches'].append(dict(base,id='exit',winner=team['name'] if champion else 'Opponent',**details))
        ev['champion']=team['name'] if champion else 'Other champion'
        records=[dict(key=self.key+':'+m['id'],event=self.key,team_id=team['id']) for m in ev['matches']]
        return ev,team,records

    def test_all_eighteen_exit_comparisons_have_grounded_inputs(self):
        rows=[('stage1',24,25,29),('stage2',16,17,25),('stage3',8,9,17),
              ('quarter_final',4,5,9),('semi_final',2,3,5),('final',1,2,3)]
        for phase,below,expected,above in rows:
            for comparison,rank in [('below',below),('expected',expected),('above',above)]:
                with self.subTest(phase=phase,comparison=comparison):
                    ev,team,records=self.exit(rank,phase,wins=2 if phase=='stage1' and comparison=='above' else 0)
                    out=major.assess(ev,team,records,self.key)
                    self.assertEqual(phase,out['exit'])
                    self.assertEqual(comparison,out['comparison'])
                    self.assertEqual(rank,out['rank'])

    def test_no_results_or_future_ability_in_frozen_expectation(self):
        original=deepcopy(self.ev['major_expectation'])
        self.assertEqual(1,original['teams']['t1']['rank'])
        for t in self.teams:
            t['rank']=1
            for p in t['players']:p['ability']=1
        major.freeze(self.ev,self.teams)
        self.assertEqual(original,self.ev['major_expectation'])

    def test_2024_twenty_four_team_major_has_two_stages(self):
        ev=dict(id='major24',type='major',size=24,field=[t['name'] for t in self.teams[:24]],matches=[])
        major.freeze(ev,self.teams)
        self.assertEqual(2,ev['major_expectation']['stages'])
        self.assertEqual('stage2',ev['major_expectation']['teams']['t9']['expected'])
        self.assertEqual('stage1',ev['major_expectation']['teams']['t17']['expected'])
        self.assertNotIn('stage3',{r['expected'] for r in ev['major_expectation']['teams'].values()})

    def test_champion_always_excited_including_first_seed(self):
        for rank in (1,2,16,32):
            ev,team,records=self.exit(rank,'final',champion=True)
            out=major.assess(ev,team,records,self.key)
            self.assertEqual('champion',out['exit']);self.assertEqual('激动',out['mood'])

    def test_stage_one_two_wins_do_not_claim_qualification(self):
        ev,team,records=self.exit(32,'stage1',wins=2)
        out=major.assess(ev,team,records,self.key)
        self.assertEqual('above',out['comparison']);self.assertEqual('stage1',out['exit'])
        self.assertEqual(2,out['stage_wins'])
        ev,team,records=self.exit(32,'stage1',wins=1)
        self.assertEqual('expected',major.assess(ev,team,records,self.key)['comparison'])

    def test_current_membership_cannot_replace_played_identity(self):
        ev,team,records=self.exit(2,'final')
        records[0]['team_id']='previous-club'
        self.assertIsNone(major.assess(ev,team,records,self.key))
        records[0]['team_id']=team['id'];records[0]['key']='2026:major:another-match'
        self.assertIsNone(major.assess(ev,team,records,self.key))

    def test_missing_and_invalid_match_results_do_not_create_exit_story(self):
        for change in ({'forfeit':True},{'played':False},{'winner':None},{'team_b':'BYE'},{'id':''}):
            with self.subTest(change=change):
                ev,team,records=self.exit(2,'final');ev['matches'][0].update(change)
                self.assertIsNone(major.assess(ev,team,records,self.key))
        ev,team,records=self.exit(4,'semi_final');ev['matches'][0]['winner']=team['name']
        self.assertIsNone(major.assess(ev,team,records,self.key))

    def test_missing_old_expectation_is_explicitly_ungraded(self):
        ev,team,records=self.exit(2,'final')
        ev.pop('major_expectation');ev.pop('arc_expectations')
        out=major.assess(ev,team,records,self.key)
        self.assertEqual('final',out['exit']);self.assertIsNone(out['comparison']);self.assertIsNone(out['rank'])
        ev['arc_expectations']={team['id']:2}
        self.assertEqual('expected',major.assess(ev,team,records,self.key)['comparison'])

    def test_incomplete_roster_field_does_not_promote_known_teams(self):
        ev=deepcopy(self.ev);ev.pop('major_expectation');ev.pop('arc_expectations')
        major.freeze(ev,self.teams[:10])
        self.assertFalse(ev['major_expectation']['complete'])
        self.assertTrue(all(r['rank'] is None and r['expected'] is None for r in ev['major_expectation']['teams'].values()))
