"""Voluntary ending conditions; no user-save reads or writes."""
from types import SimpleNamespace
from unittest import TestCase
from cs2career.career.retirement import choose,career_context


class RetirementTests(TestCase):
    def test_one_year_with_trophy_is_not_veteran(self):
        for age in (20,35):
            self.assertEqual('early_success',choose({'counts':{'titles':1}},
                dict(age=age,years=1,active_seasons=2,maps=300))['id'])

    def test_veteran_requires_all_four_conditions_not_honours(self):
        context=dict(age=28,years=5,active_seasons=5,maps=200)
        self.assertEqual('veteran',choose({'counts':{}},context)['id'])
        for field,value in context.items():
            self.assertEqual('plain',choose({'counts':{}},{**context,field:value-1})['id'])

    def test_legend_priority_and_empty_history(self):
        self.assertEqual('legend',choose({'counts':dict(majors=2,titles=6,top20=3)})['id'])
        self.assertEqual('plain',choose({'counts':{}},dict(age=50))['id'])

    def test_context_uses_identity_and_full_anniversaries(self):
        player=dict(player_id='me',name='Tester',age=28)
        career=SimpleNamespace(my_player=lambda teams:player,you_card={},start_year=2026,player_name='Tester')
        mp=dict(players={'Team':[player]})
        match=dict(id='f',date='2026-12-31',played=True,team_a='Team',team_b='Other',maps=[mp])
        ev=dict(id='cup',matches=[match])
        season=SimpleNamespace(teams=[],history=[ev],events=[ev],date='2031-01-01')
        self.assertEqual(dict(age=28,years=4,active_seasons=1,maps=1),career_context(career,season))
        match['forfeit']=True
        self.assertEqual(0,career_context(career,season)['maps'])
