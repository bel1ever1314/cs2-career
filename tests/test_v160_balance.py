"""v1.6: attendance cannot farm ranking; role swaps cannot manufacture talent."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cs2career.league.vrs import VRS, BEST_RESULTS, MAX_WINS_PER_EVENT
from cs2career.world.ability import (calibrate_role, ability_of, gun_score,
    refresh_player_ability, ensure_role_calibration)
from cs2career.career.assistance import configure, process_invites, process_points
from cs2career.career.fast_mode import invitation_decision, step


def win(event, points=200, when='2026-06-01', team='mine'):
    return dict(team=team, date=when, points=points, kind='win', won=True,
                event=event, opp='other')


class RankingQualityTests(unittest.TestCase):
    def test_best_ten_wins_and_same_event_limit(self):
        v = VRS()
        v.results = [win('one-cup', 300) for _ in range(30)]
        self.assertEqual(900, v.earned('mine', '2026-06-01'))
        self.assertEqual(MAX_WINS_PER_EVENT, v.participation_value('mine', '2026-06-01')['counted_wins'])
        v.results += [win(f'cup-{i}', 400) for i in range(10)]
        self.assertEqual(4000, v.earned('mine', '2026-06-01'))
        before = v.live('mine', '2026-06-01')
        v.results += [win(f'cct-{i}', 90) for i in range(100)]
        self.assertEqual(before, v.live('mine', '2026-06-01'))
        self.assertFalse(v.can_improve('mine', .42, '2026-06-01'))
        self.assertTrue(v.can_improve('mine', 2, '2026-06-01'))

    def test_losses_future_and_expired_rows_do_not_inflate_ranking(self):
        v = VRS()
        v.results = [win('future', 1000, '2026-06-02'), win('expired', 1000, '2025-01-01'),
                     dict(win('loss', 1000), kind='loss', won=False), win('valid', 200)]
        self.assertEqual(200, v.earned('mine', '2026-06-01'))
        self.assertEqual(1, v.participation_value('mine', '2026-06-01')['counted_wins'])

    def test_seed_not_stacked_on_results_and_repeat_year_event_is_separate(self):
        v = VRS(); v.results = [dict(win('seed', 1000), kind='seed'), win('cup', 200)]
        self.assertEqual(1000, v.earned('mine', '2026-06-01'))
        v.results = [win('same-id', 100, '2025-12-30') for _ in range(3)] + [win('same-id', 100, '2026-01-02') for _ in range(3)]
        self.assertEqual(6, v.participation_value('mine', '2026-01-02')['counted_wins'])

    def test_awarding_loss_never_rewards_an_intentional_forfeit(self):
        v = VRS(); a = dict(id='a'); b = dict(id='b')
        v.award_series(a, b, 1, '2026-06-01', 'cup')
        self.assertEqual(0, v.earned('b', '2026-06-01'))
        self.assertGreater(v.earned('a', '2026-06-01'), 0)


class RoleScaleTests(unittest.TestCase):
    def test_equal_axes_no_free_igl_to_rifle_or_awp_bonus(self):
        stats = dict.fromkeys(('firepower','entrying','trading','opening','clutching','sniping','utility'), 90)
        calibrate_role(stats, 'igl', 83)
        for role in ('igl', 'rifle', 'awp', 'entry', 'lurk'):
            self.assertEqual(83, ability_of(stats, role))

    def test_legacy_reference_migration_preserves_growth_without_role_total_bug(self):
        axes = dict(firepower=90, entrying=70, trading=80, opening=65, clutching=90, sniping=20, utility=80)
        legacy = dict(axes, ability=84, role_reference='igl', role_reference_score=gun_score(axes, 'igl'))
        legacy['firepower'] += 3  # Earned training must survive the migration.
        p = dict(name='Legacy IGL', ability=100, stats=legacy, role='rifle', form_delta=0)
        before = ability_of(legacy, 'rifle')
        self.assertTrue(ensure_role_calibration(p))
        self.assertFalse(ensure_role_calibration(p))
        refresh_player_ability(p)
        self.assertEqual(before, p['ability'])
        self.assertLess(p['ability'], 90)
        self.assertGreater(p['long_term_ability'], 84)
        baseline = deepcopy(p['stats'])
        for _ in range(10):
            for role in ('awp','rifle','igl','lurk','entry'):
                p['role'] = role; refresh_player_ability(p)
        self.assertEqual(baseline, p['stats'])


class FastInvitationTests(unittest.TestCase):
    def setUp(self):
        self.c = SimpleNamespace(team_id='mine', registered=[], assist={}, exists=True,
            unsigned=False, over=lambda:False, inbox=[], incident_state={}, my_team=lambda teams:teams[0])
        self.s = SimpleNamespace(year=2026, date='2026-06-01', qualified={}, events=[],
            teams=[dict(id='mine',name='Mine',players=[])], vrs=VRS())
        self.s.vrs.results = []

    def event(self, kind='cct', eid='cup', start='2026-06-10'):
        return dict(id=eid,name=eid,type=kind,status='upcoming',dates=[start],vrs_weight=.42)

    def test_elite_skips_cct_developing_team_can_play(self):
        e = self.event()
        self.assertEqual('decline', invitation_decision(self.c,self.s,e,{'level_rank':8})[0])
        self.assertEqual('accept', invitation_decision(self.c,self.s,e,{'level_rank':55})[0])

    def test_cct_spacing_and_ranking_saturation(self):
        old = self.event(eid='previous', start='2026-05-20')
        old['status']='done'; self.s.events=[old]; self.c.registered=[old['id']]
        self.assertEqual('decline', invitation_decision(self.c,self.s,self.event(),{'level_rank':55})[0])
        self.s.events=[]; self.c.registered=[]
        self.s.vrs.results=[win(f'large-{i}',400) for i in range(BEST_RESULTS)]
        decision, message=invitation_decision(self.c,self.s,self.event(),{'level_rank':55})
        self.assertEqual('decline', decision); self.assertIn('最佳十场',message)

    def test_major_priority_and_collision(self):
        major = self.event('major', 'major')
        self.assertEqual('accept', invitation_decision(self.c,self.s,major,{'level_rank':55})[0])
        self.s.events=[major]; self.c.registered=['major']
        self.assertEqual('decline', invitation_decision(self.c,self.s,self.event(),{'level_rank':55})[0])

    def test_explicit_decline_setting_is_kept_and_quick_setting_validates(self):
        configure(self.c,self.s,{'quick_mode':True,'invites':{'cct':'decline'}})
        e=self.event(); self.s.events=[e]
        self.c.inbox=[dict(id='mail',kind='invite',status='open',team_id='mine',event_id=e['id'])]
        self.c.accept_invite=Mock(); self.c.decline_invite=Mock()
        with patch('cs2career.career.fast_mode.context',return_value={'level_rank':55}):
            process_invites(self.c,self.s)
        self.c.accept_invite.assert_not_called(); self.c.decline_invite.assert_called_once()
        with self.assertRaises(ValueError): configure(self.c,self.s,{'quick_mode':'yes'})

    def test_quick_mode_handles_legacy_manual_categories(self):
        configure(self.c,self.s,{'quick_mode':True,'invites':{'cct':'manual'}})
        e=self.event(); self.s.events=[e]
        row=dict(id='mail',kind='invite',status='open',team_id='mine',event_id=e['id'])
        self.c.inbox=[row]
        def accept(*args,**kwargs): row['status']='accepted'; return 'accepted'
        self.c.accept_invite=Mock(side_effect=accept)
        self.c.decline_invite=Mock()
        with patch('cs2career.career.fast_mode.context',return_value={'level_rank':55}):
            self.assertTrue(process_invites(self.c,self.s))
        self.assertEqual('accepted',row['status']); self.assertIn('CCT',row['auto_reason'])

    def test_fast_step_is_retry_safe_and_does_not_answer_plot(self):
        self.c.assist={'quick_mode':True}; self.c.dispatch_invites=Mock()
        self.s.year=2026; self.s.your_series=Mock(return_value=None)
        self.s.next_stage=Mock(return_value='advanced')
        with patch('cs2career.league.tournament_auto.blocker',return_value='请选择剧情。'):
            out=step(self.c,self.s,'request-0001',0)
            self.assertEqual('paused',out['status'])
            self.assertEqual(out,step(self.c,self.s,'request-0001',0))
            self.assertEqual(1,self.c.assist['step_counter'])
            self.s.next_stage.assert_not_called()
            with self.assertRaises(ValueError): step(self.c,self.s,'request-0002',0)

    def test_quick_auto_points_accumulate_until_major_break(self):
        self.c.assist={'quick_mode':True,'points':'firepower'}
        self.c.attr_points=4
        self.c.my_player=Mock(return_value={'stats':{'firepower':60}})
        self.c.spend_point=Mock()
        process_points(self.c,self.s)
        self.c.my_player.assert_not_called(); self.c.spend_point.assert_not_called()
        self.assertEqual(4,self.c.attr_points)

    def test_new_major_break_requires_explicit_resume(self):
        self.c.assist={'quick_mode':True}
        self.c.incident_state={'story_timing':{'windows':[{'key':'2026:major1','start':'2026-06-01','until':'2026-06-22'}]}}
        self.s.next_stage=Mock()
        result=step(self.c,self.s,'break-0001',0)
        self.assertEqual('paused',result['status']); self.assertEqual('2026:major1',result['break_key'])
        self.s.next_stage.assert_not_called()


class FastRealCommandTests(unittest.TestCase):
    def test_one_real_series_and_retry_then_decisive_game_pause(self):
        from cs2career.career import Career
        from cs2career.league import Season, formats
        s=Season(2026,'2026'); c=Career(); s.career=c
        with patch.object(c,'save'):
            c.create(dict(mode='create',era='2026',name='Fast Test',org='Fast Club',
                          origin='academy',role='rifle',region='EU'),s)
        c.story_queue=[]; c.inbox=[]; c.assist={'quick_mode':True}
        mine=c.my_team(s.teams); opp=next(t for t in s.teams if t['id']!=mine['id'])
        ev=dict(id='fast-fixture',name='Fixture',type='t2',format='swiss_playoff',size=2,
                region='EU',dates=[s.date],prize=0,vrs_weight=1,status='live',
                field=[mine['name'],opp['name']],matches=[])
        m=formats._mk(ev,'SW1',s.date,mine['name'],opp['name'],1,meta={'record':'0-0'})
        ev['matches']=[m]; s.events=[ev]; c.registered=[ev['id']]
        with patch.object(c,'save'),patch.object(c,'gate_match',return_value=''),patch.object(s,'advance_event'):
            result=step(c,s,'real-step-0001',0)
            self.assertEqual('played',result['status']); self.assertTrue(m['played'])
            saved=deepcopy(m); vrs=deepcopy(s.vrs.results)
            self.assertEqual(result,step(c,s,'real-step-0001',0))
            self.assertEqual(saved,m); self.assertEqual(vrs,s.vrs.results)
            c.story_queue=[]
            final=formats._mk(ev,'GF',s.date,mine['name'],opp['name'],3)
            ev['matches'].append(final)
            self.assertEqual('decision',step(c,s,'real-step-0002',1)['status'])
            self.assertFalse(final['played']); self.assertTrue(c.story_queue)


if __name__ == '__main__': unittest.main()
