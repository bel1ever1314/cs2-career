"""Real Career commands, isolated by tools/run_tests.py or a temporary runner."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from cs2career.career import Career
from cs2career.league import Season, formats
from cs2career.career.assistance import configure, process_invites, process_points
from cs2career.league.tournament_auto import step, decisive, key


class AssistanceTests(unittest.TestCase):
    def setUp(self):
        self.s=Season(2026,'2026');self.c=Career();self.s.career=self.c
        with patch.object(self.c,'save'):
            self.c.create(dict(mode='create',era='2026',name='AssistTest',org='Assist Club',origin='academy',role='rifle',region='EU'),self.s)
        self.c.story_queue=[];self.c.inbox=[];self.s.events=[]
        self.mine=self.c.my_team(self.s.teams)
        self.opp=next(t for t in self.s.teams if t['id']!=self.c.team_id)
        self.save_patch=patch.object(self.c,'save');self.save_patch.start();self.addCleanup(self.save_patch.stop)

    def event(self,kind='t2',stage='GF'):
        ev=dict(id='assist-cup',name='Assist Cup',type=kind,format='single_elim',size=2,
                region='EU',dates=[self.s.date],prize=0,vrs_weight=1,status='upcoming',field=[],matches=[])
        self.s.events=[ev]
        return ev

    def open_match(self,stage='SW1',record='0-0'):
        ev=self.event()
        m=formats._mk(ev,stage,self.s.date,self.mine['name'],self.opp['name'],3,meta={'record':record})
        ev.update(status='live',matches=[m],field=[self.mine['name'],self.opp['name']])
        self.c.registered=[ev['id']]
        return ev,m

    def test_manual_default_and_auto_decline_does_not_touch_contracts(self):
        ev=self.event();row=self.c.offer_invite(self.s,ev,rank=20)
        contract={'id':'contract','kind':'contract','status':'open','team_id':self.c.team_id}
        self.c.inbox.append(contract)
        self.assertFalse(process_invites(self.c,self.s));self.assertEqual('open',row['status'])
        configure(self.c,self.s,{'invites':{'t2':'decline'}})
        self.assertTrue(process_invites(self.c,self.s))
        self.assertEqual('declined',row['status']);self.assertEqual('decline',row['auto_action'])
        self.assertEqual('open',contract['status']);self.assertFalse(process_invites(self.c,self.s))
        configure(self.c,self.s,{'invites':{'t2':'accept'}});process_invites(self.c,self.s)
        self.assertEqual('declined',row['status'],'must not overturn a past decision')

    def test_accept_and_qualifiers_and_wrong_team(self):
        ev=self.event('qual');ev['feeds']='iem';row=self.c.offer_invite(self.s,ev,rank=20)
        configure(self.c,self.s,{'invites':{'qual':'accept'}})
        row['team_id']='old-club';self.assertFalse(process_invites(self.c,self.s))
        row['team_id']=self.c.team_id;process_invites(self.c,self.s)
        self.assertEqual('accepted',row['status']);self.assertIn(ev['id'],self.c.registered)

    def test_points_cap_and_repeat_and_normal_rule_equivalence(self):
        p=self.c.my_player(self.s.teams);p['stats']['firepower']=98;self.c.attr_points=5
        configure(self.c,self.s,{'points':'firepower'});process_points(self.c,self.s)
        self.assertEqual(100,p['stats']['firepower']);self.assertEqual(3,self.c.attr_points)
        self.assertEqual('off',self.c.assist['points']);self.assertIn('已加满',self.c.assist['notice'])
        self.assertEqual(1,len(self.c.story_queue));process_points(self.c,self.s)
        self.assertEqual(1,len(self.c.story_queue));self.assertEqual(3,self.c.attr_points)

    def test_balanced_spends_only_existing_points(self):
        p=self.c.my_player(self.s.teams);old=deepcopy(p['stats']);self.c.attr_points=3
        configure(self.c,self.s,{'points':'balanced'});process_points(self.c,self.s)
        self.assertEqual(0,self.c.attr_points)
        from cs2career.world.ability import ALL_AXES
        self.assertEqual(3,sum(p['stats'].get(a,0)-old.get(a,0) for a in ALL_AXES))

    def test_decisive_rules(self):
        for stage,meta,expected in [('GF',{},'final'),('QF',{},'elimination'),('SW3',{'record':'0-2'},'elimination'),
            ('M2-SW5',{'record':'2-2'},'elimination'),('SW3',{'record':'2-0'},''),('G2',{'kind':'winners'},''),
            ('G2',{'kind':'elim'},'elimination'),('G3',{'kind':'decider'},'elimination')]:
            self.assertEqual(expected,decisive({},dict(stage=stage,meta=meta)))

    def test_final_and_elimination_require_player_choice(self):
        for stage,record,word in [('GF','0-0','奖杯'),('SW3','0-2','退路')]:
            self.c.story_queue=[];self.c.assist={};ev,m=self.open_match(stage,record)
            out=step(self.c,self.s,ev['id'],'decision-'+stage)
            self.assertEqual('decision',out['status']);self.assertFalse(m['played'])
            row=self.c.story_queue[0];self.assertIn(word,row['title'])
            self.assertEqual({'manual','simulate','later'},{ch['id'] for ch in row['choices']})
            self.assertNotIn('{player}',row['text'])
            self.c.ack_story(row['id'],'simulate',self.s)
            self.assertEqual(key(self.s,ev,m),self.c.assist['tournament']['approval'])

    def test_story_pause_and_one_series_receipt(self):
        ev,m=self.open_match()
        self.c.story_queue=[{'id':'decision','text':'choose','choices':[{'id':'yes'}]}]
        with patch.object(self.s,'skip_your_series') as skip:
            self.assertEqual('paused',step(self.c,self.s,ev['id'],'blocked1')['status']);skip.assert_not_called()
        self.c.story_queue=[]
        with patch.object(self.c,'gate_match',return_value=''),patch.object(self.s,'advance_event'):
            result=step(self.c,self.s,ev['id'],'playing1')
            self.assertEqual('played',result['status']);saved=deepcopy(m)
            self.assertEqual(result,step(self.c,self.s,ev['id'],'playing1'))
            self.assertEqual(saved,m)
        self.assertTrue(m['played']);self.assertIn(len(result['match']['winners']),(2,3))

    def test_cs2_pending_is_never_overwritten(self):
        ev,m=self.open_match();m['cs2_session']={'nonce':'pending'}
        self.assertEqual('paused',step(self.c,self.s,ev['id'],'pending1')['status'])
        self.assertFalse(m['played'])

    def test_later_reprompts_and_manual_does_not_authorize_simulation(self):
        ev,m=self.open_match('QF');step(self.c,self.s,ev['id'],'first001')
        row=self.c.story_queue[0];self.c.ack_story(row['id'],'later',self.s)
        self.assertEqual('decision',step(self.c,self.s,ev['id'],'second01')['status'])
        self.c.ack_story(row['id'],'manual',self.s)
        self.assertEqual('',self.c.assist['tournament']['approval']);self.assertFalse(m['played'])

    def test_before_match_story_stops_before_simulation(self):
        ev,m=self.open_match()
        def gate(*args):self.c.story_queue.append({'id':'surprise','text':'Choose first'});return ''
        with patch.object(self.c,'gate_match',side_effect=gate),patch.object(self.s,'skip_your_series') as skip:
            self.assertEqual('paused',step(self.c,self.s,ev['id'],'newstory')['status']);skip.assert_not_called()

    def test_settings_roundtrip(self):
        configure(self.c,self.s,{'points':'utility','invites':{'major':'accept','t2':'decline'}})
        self.assertEqual(self.c.assist,self.c.to_json()['assist'])

    def test_delayed_retry_cannot_advance_a_new_step(self):
        ev,m=self.open_match();self.c.story_queue=[{'id':'hold','text':'wait'}]
        first=step(self.c,self.s,ev['id'],'first001',0)
        self.assertEqual(first,step(self.c,self.s,ev['id'],'first001',0))
        step(self.c,self.s,ev['id'],'second01',1)
        with self.assertRaises(ValueError):step(self.c,self.s,ev['id'],'first001',0)
        self.assertEqual(2,self.c.assist['step_counter']);self.assertFalse(m['played'])

    def test_real_event_loop_finishes_without_auto_answering_stories(self):
        ev=self.event();ev['size']=4
        names=[self.mine['name']]+[t['name'] for t in self.s.teams if t['id']!=self.c.team_id][:3]
        ev['matches']=formats.open_event(ev,names);ev['status']='live';self.c.registered=[ev['id']]
        decisions=0
        for i in range(80):
            if self.c.story_queue:
                row=self.c.story_queue[0]
                choice='simulate' if row.get('when')=='tournament_decision' else (row.get('choices') or [{'id':''}])[0]['id']
                self.c.ack_story(row['id'],choice,self.s)
                decisions+=1
                continue
            result=step(self.c,self.s,ev['id'],f'whole-event-{i}')
            if result['status']=='done':break
        else:self.fail('event loop stalled')
        self.assertEqual('done',ev['status'])
        self.assertTrue(decisions>0)
        self.assertTrue(all(m['played'] for m in ev['matches']))
        self.assertEqual(3,len(ev['matches']))


if __name__=='__main__':unittest.main()
