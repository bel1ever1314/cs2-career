"""Major delivery windows and interruption-safe series phase extension hooks."""
import json
import re
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cs2career.career import Career, arcs, incidents, story_timing
from cs2career.career.assistance import process_points
from cs2career.league import Season, formats, phases
from cs2career.paths import data_file


class TimingFixture(unittest.TestCase):
    def setUp(self):
        self.s=Season(2026,'2026'); self.c=Career(); self.s.career=self.c
        with patch.object(self.c,'save'):
            self.c.create(dict(mode='create',era='2026',name='Timing Test',org='Timing Club',
                          origin='academy',role='rifle',region='EU'),self.s)
        self.c.story_queue=[]; self.c.inbox=[]; self.s.events=[]
        self.c.incident_state.pop('story_timing',None)
        self.mine=self.c.my_team(self.s.teams)
        self.opp=next(t for t in self.s.teams if t['id'] != self.c.team_id)
        self.saved=patch.object(self.c,'save'); self.saved.start(); self.addCleanup(self.saved.stop)

    def major(self):
        return dict(id='timing-major',name='Test Major',type='major',status='done',
                    dates=[self.s.date],matches=[],field=[],awards={},champion=self.opp['name'])


class MajorWindowTests(TimingFixture):
    def test_window_only_after_major_once_and_expires(self):
        event=self.major()
        story_timing.open_major_break(self.c,self.s,dict(event,type='t1'))
        self.assertIsNone(story_timing.window(self.c,self.s))
        story_timing.open_major_break(self.c,self.s,event)
        before=deepcopy(story_timing.state(self.c))
        story_timing.open_major_break(self.c,self.s,event)
        self.assertEqual(before,story_timing.state(self.c))
        current=story_timing.window(self.c,self.s)
        self.assertEqual(arcs.after(self.s.date,arcs.config()['rules']['offseason_days']),current['until'])
        self.s.date=arcs.after(current['until'],1)
        self.assertIsNone(story_timing.window(self.c,self.s))

    def test_long_stories_defer_with_payload_intact_and_required_decision_stays(self):
        row={'id':'chapter','kind':'story','when':'birthday','text':'A frozen story',
             'choices':[{'id':'train','label':'Train'}],'chance':.172}
        self.c.story_queue=[deepcopy(row),{'id':'fix','kind':'story','when':'fix_offer','text':'Choose'}]
        story_timing.reconcile(self.c,self.s)
        self.assertEqual(['fix'],[r['id'] for r in self.c.story_queue])
        self.assertEqual([row],story_timing.state(self.c)['deferred'])
        story_timing.reconcile(self.c,self.s)
        story_timing.open_major_break(self.c,self.s,self.major())
        story_timing.reconcile(self.c,self.s); story_timing.reconcile(self.c,self.s)
        self.assertEqual(1,sum(r['id']=='chapter' for r in self.c.story_queue))
        self.assertEqual(row,next(r for r in self.c.story_queue if r['id']=='chapter'))
        self.assertFalse(story_timing.state(self.c)['deferred'])

    def test_explicit_offseason_overrides_immediate_trigger(self):
        self.c.story_queue=[dict(id='forced-offseason',kind='story',when='before_match',
                                trigger='map_started',timing='offseason')]
        story_timing.reconcile(self.c,self.s)
        self.assertFalse(self.c.story_queue)
        self.assertEqual('forced-offseason',story_timing.state(self.c)['deferred'][0]['id'])

    def test_first_series_never_starts_romance_first_completed_major_does(self):
        v=arcs.state(self.c); you=self.c.my_player(self.s.teams)
        event=dict(id='normal',name='Normal',type='t2',status='live')
        match=dict(id='first',played=True,team_a=self.mine['name'],team_b=self.opp['name'],
                   winner=self.mine['name'],maps=[dict(rounds=20,players={self.mine['name']:[
                       dict(player_id=you['player_id'],name=you['name'],rating=1.1,rounds=20)]})])
        arcs.on_series(self.c,self.s,event,match)
        self.assertEqual('waiting',v['romance'])
        self.assertFalse(any(r.get('arc')=='romance_start' for r in self.c.story_queue))
        event=self.major()
        arcs.event_done(self.c,self.s,event); arcs.event_done(self.c,self.s,event)
        rows=[r for r in self.c.story_queue if r.get('arc')=='romance_start']
        self.assertEqual(1,len(rows))
        self.assertTrue(story_timing.window(self.c,self.s))

    def test_quick_manual_and_auto_points_block_then_spend_in_window(self):
        self.c.assist={'quick_mode':True,'points':'firepower'}; self.c.attr_points=3
        you=self.c.my_player(self.s.teams); before=deepcopy(you['stats'])
        self.assertIn('休赛期',self.c.spend_point(self.s,'firepower'))
        process_points(self.c,self.s)
        self.assertEqual(3,self.c.attr_points); self.assertEqual(before,you['stats'])
        story_timing.open_major_break(self.c,self.s,self.major())
        self.c.spend_point(self.s,'firepower'); self.assertEqual(2,self.c.attr_points)
        process_points(self.c,self.s)
        self.assertEqual(0,self.c.attr_points)
        self.assertEqual(before['firepower']+3,you['stats']['firepower'])

    def test_year_roll_retains_quick_points_and_normal_mode_clears(self):
        for quick in (True,False):
            with self.subTest(quick=quick):
                self.c.attr_points=7; self.c.assist={'quick_mode':quick}
                self.c.last_age_year=2026
                self.c.last_sponsor_month=self.c.last_ops_month='2027-01'
                self.s.date='2027-01-01'; self.s.year=2027
                with patch.object(self.c,'_age_year'),patch.object(self.c,'dispatch_invites'), \
                     patch.object(self.c,'_birthday_tick'),patch.object(self.c,'emit_incidents'), \
                     patch('cs2career.career.arcs.tick'),patch('cs2career.career.news.tick'), \
                     patch('cs2career.career.player_transfers.tick'),patch('cs2career.career.career.skins.advance_day'):
                    self.c.tick(self.s,'2026-12-31')
                self.assertEqual(7 if quick else 0,self.c.attr_points)

    def test_daily_incident_is_not_consumed_outside_break(self):
        rule=dict(id='daily',when='day',title='Daily',text='Offseason decision',
                  choices=[dict(id='ok',label='Continue',effects=[])])
        registry=SimpleNamespace(payloads=lambda kind:[{'_pack_id':'timing','incidents':[rule]}])
        with patch.object(incidents,'get_registry',return_value=registry):
            incidents.emit(self.c,self.s,'day','first-day')
            self.assertFalse(incidents.pending(self.c))
            self.assertNotIn('timing:daily',incidents.state(self.c)['seen'])
            story_timing.open_major_break(self.c,self.s,self.major())
            incidents.emit(self.c,self.s,'day','break-day')
            self.assertTrue(incidents.pending(self.c))

    def test_eighteen_exit_stories_have_complete_bilingual_variants(self):
        rows=json.loads(data_file('major_exit_stories.json').read_text('utf-8'))['stories']
        expected={stage+'_'+mood for stage in ('stage1','stage2','stage3','quarter_final','semi_final','final')
                  for mood in ('below','expected','above')}
        self.assertEqual(expected,set(rows)); self.assertEqual(18,len(rows))
        self.assertEqual(18,len({r['title'] for r in rows.values()}))
        for key,row in rows.items():
            with self.subTest(chapter=key):
                self.assertTrue(row['title_en'])
                self.assertTrue(row['text']); self.assertTrue(row['text_en'])
                self.assertGreater(len(row['text'][0]),160)
                self.assertGreater(len(row['text_en'][0]),200)
                tokens=set(re.findall(r'\{([^}]+)\}', '\n'.join(row['text']+row['text_en'])))
                self.assertLessEqual(tokens,{'event','expected','player','team'})


class CompetitionPhaseTests(TimingFixture):
    def fixture(self, phases_wanted, best_of=3):
        event=dict(id='phase-fixture',name='Phase Fixture',type='t2',format='swiss_playoff',size=2,
                   region='EU',dates=[self.s.date],prize=0,vrs_weight=1,status='live',
                   field=[self.mine['name'],self.opp['name']],matches=[])
        match=formats._mk(event,'SW1',self.s.date,self.mine['name'],self.opp['name'],best_of,meta={'record':'0-0'})
        event['matches']=[match];self.s.events=[event];self.c.registered=[event['id']]
        rules=[dict(id=p,when=p,title=p,text='{event_name}: {map_index}',max_per_career=20,cooldown_days=0,
                    choices=[dict(id='ok',label='Continue',effects=[])]) for p in phases_wanted]
        registry=SimpleNamespace(payloads=lambda kind:[{'_pack_id':'phase-test','incidents':rules}]
                                 if kind=='incidents' else [])
        self.registry=patch.object(incidents,'get_registry',return_value=registry)
        self.registry.start(); self.addCleanup(self.registry.stop)
        self.gate=patch.object(self.c,'gate_match',return_value='')
        self.gate.start(); self.addCleanup(self.gate.stop)
        self.advance=patch.object(self.s,'advance_event')
        self.advance.start(); self.addCleanup(self.advance.stop)
        return event,match

    def ack(self):
        row=next(r for r in self.c.story_queue if r.get('kind')=='incident')
        self.c.ack_story(row['id'],'ok',self.s)
        phases.drain(self.s)

    def test_map_start_pauses_before_simulation_and_is_not_duplicated(self):
        _,match=self.fixture(['map_started'])
        with patch('cs2career.league.season.play_map') as simulate:
            message=self.s.skip_your_series(match['id'])
            self.assertIn('暂停',message);simulate.assert_not_called()
        self.assertEqual([],match['maps']);self.assertFalse(match['played'])
        seen=list(match['phase_hooks'])
        phases.emit(self.s,self.s.events[0],match,'map_started',0)
        self.assertEqual(seen,match['phase_hooks']); self.assertEqual(1,len(self.c.story_queue))
        self.ack()
        self.s.skip_your_series(match['id'])
        self.assertEqual(1,len(match['maps']))
        self.assertEqual('map_started',self.c.story_queue[0]['trigger'])
        self.assertIn('2',self.c.story_queue[0]['text'])

    def test_map_end_retains_result_and_does_not_reroll_after_ack(self):
        _,match=self.fixture(['map_finished'])
        self.s.skip_your_series(match['id'])
        self.assertEqual(1,len(match['maps'])); self.assertFalse(match['played'])
        first=deepcopy(match['maps'][0]); self.ack()
        self.s.skip_your_series(match['id'])
        self.assertGreaterEqual(len(match['maps']),2)
        self.assertEqual(first,match['maps'][0])
        self.assertEqual(1,sum(key.endswith(':0') and key.startswith('map_finished:') for key in match['phase_hooks']))

    def test_final_map_and_series_end_decisions_are_delivered_in_order(self):
        _,match=self.fixture(['map_finished','series_finished'],best_of=1)
        self.s.skip_your_series(match['id'])
        self.assertTrue(match['played']); self.assertEqual(1,len(match['maps']))
        self.assertEqual('map_finished',self.c.story_queue[0]['trigger'])
        self.assertEqual(['series_finished'],[r['phase'] for r in match['phase_pending']])
        before=deepcopy(match['maps']); self.ack()
        self.assertEqual('series_finished',self.c.story_queue[0]['trigger'])
        self.ack(); phases.drain(self.s)
        self.assertFalse(match['phase_pending']);self.assertEqual(before,match['maps'])
        self.assertEqual(1,sum(key.startswith('series_finished:') for key in match['phase_hooks']))

    def test_backlog_context_date_and_team_are_frozen(self):
        event,match=self.fixture(['map_finished'])
        self.c.story_queue=[{'id':'existing','kind':'incident'}]
        phases.emit(self.s,event,match,'map_finished',0)
        original=self.s.date
        self.s.date=arcs.after(original,5);self.c.story_queue=[]
        phases.drain(self.s)
        self.assertEqual(original,self.c.story_queue[0]['date'])
        self.c.story_queue=[]
        phases.emit(self.s,event,match,'map_finished',1)
        self.c.story_queue=[{'id':'existing','kind':'incident'}]
        phases.emit(self.s,event,match,'series_finished')
        self.c.story_queue=[];self.c.team_id='another-team'
        phases.drain(self.s)
        self.assertFalse(match['phase_pending']);self.assertFalse(self.c.story_queue)


if __name__=='__main__':unittest.main()
