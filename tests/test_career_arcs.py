"""Story branch tests: real Career queue/ack and Season callbacks; runner isolates saves."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import shutil
import json

from cs2career.career import Career, arcs, incidents, player_transfers as pt
from cs2career.league import Season
from cs2career.content.loader import PackRegistry
from cs2career.content.rules import validate_payload
from cs2career.world.ability import AXES, effective_form_delta


class CareerArcTests(TestCase):
    def setUp(self):
        self.s=Season(2026,'2026'); self.c=Career(); self.s.career=self.c
        with patch.object(self.c,'save'):
            self.c.create(dict(mode='create',era='2026',name='ArcTester',org='Arc Club',
                               origin='academy',role='rifle',region='EU'),self.s)
        self.c.story_queue=[];self.s.events=[]
        self.v=arcs.state(self.c);self.v['seed']='fixed-story-seed'
        self.mine=self.c.my_team(self.s.teams)

    def row(self,chapter):
        return next(r for r in self.c.story_queue if r.get('arc')==chapter)

    def choose(self,chapter,choice):
        row=self.row(chapter)
        with patch.object(self.c,'save'):
            self.c.ack_story(row['id'],choice,self.s)
        return row

    def queue(self,chapter,context=None):
        arcs.queue(self.c,self.s,chapter,'test-'+chapter,context)
        return self.row(chapter)

    def romance(self,kind='ordinary'):
        self.queue('romance_start');self.choose('romance_start',kind)
        self.choose(kind+'_intro','ok')

    def na(self,branch):
        self.v.update(na='choose')
        self.queue('na_start',{'na_bonus':3})
        self.choose('na_start',branch)

    def result(self,idx=1,event=None,win=True,rating=1):
        ev=event or dict(id='cup'+str(idx),name='Cup',type='t2',status='done',field=[],matches=[])
        player=self.c.my_player(self.s.teams)
        match=dict(id='m'+str(idx),played=True,team_a=self.mine['name'],team_b='Other',
            winner=self.mine['name'] if win else 'Other', maps=[dict(players={self.mine['name']:[
                dict(player_id=player['player_id'],name=player['name'],rating=rating,rounds=24)]})])
        ev.update(champion=match['winner'],matches=[match])
        arcs.on_series(self.c,self.s,ev,match)
        return ev,match

    def test_first_real_series_not_training_forfeit_and_only_once(self):
        ev,match=self.result()
        self.assertEqual(1,len([r for r in self.c.story_queue if r.get('arc')=='romance_start']))
        arcs.on_series(self.c,self.s,ev,match)
        self.assertEqual(1,len(self.v['series']))
        self.choose('romance_start','none')
        old=self.c.attr_points
        self.result(2)
        self.assertEqual(old,self.c.attr_points)
        self.assertFalse(any(r.get('arc')=='romance_start' for r in self.c.story_queue))

    def test_all_three_intro_texts_and_focus_reward_idempotence(self):
        for kind in ('ordinary','creator','celebrity'):
            c,s=deepcopy((self.c,self.s));self.queue('romance_start')
            self.choose('romance_start',kind)
            self.assertIn(arcs.PARTNERS[kind],self.row(kind+'_intro')['text'])
            self.c,self.s=c,s;self.v=arcs.state(c)
        row=self.queue('romance_start');before=self.c.attr_points
        self.choose('romance_start','none')
        self.c.ack_story(row['id'],'none',self.s)
        self.assertEqual(before+2,self.c.attr_points)

    def test_second_event_and_180_days_abroad(self):
        self.romance()
        for idx in (1,2):
            ev,_=self.result(idx);arcs.event_done(self.c,self.s,ev)
        before=self.c.attr_points
        self.choose('romance_pace','focus')
        self.assertEqual(before+2,self.c.attr_points)
        self.s.date=arcs.after(self.v['romance_started'],179);arcs.tick(self.c,self.s)
        self.assertFalse(any(r.get('arc')=='marriage' for r in self.c.story_queue))
        self.s.date=arcs.after(self.v['romance_started'],180);arcs.tick(self.c,self.s)
        self.choose('marriage','abroad')
        self.assertEqual('single',self.v['romance'])
        self.assertEqual(before+4,self.c.attr_points)

    def test_talk_two_outcomes_and_partner_support(self):
        self.romance()
        self.queue('marriage')['chance']=.1
        self.choose('marriage','talk');self.choose('stable','ok')
        arcs.opinion(self.c,self.s,'失望','bad')
        self.assertIn('林知夏',self.row('press')['text'])
        self.choose('press','endure')
        arcs.queue(self.c,self.s,'marriage','separate-branch-fixture')
        row=self.row('marriage');row['chance']=.9
        self.choose('marriage','talk')
        self.assertEqual('single',self.v['romance'])

    def test_retirement_confirm_does_not_reroll_and_preserves_history(self):
        self.romance();self.queue('marriage');self.choose('marriage','stay')
        chance=self.row('confirm_love')['chance']
        self.assertFalse(self.c.over())
        self.choose('confirm_love','back');self.choose('marriage','stay')
        self.assertEqual(chance,self.row('confirm_love')['chance'])
        self.choose('confirm_love','yes')
        self.assertTrue(self.c.retired)
        self.assertTrue(self.c.ending_text)
        self.assertGreater(len(self.v['history']),3)

    def test_both_retirement_endings(self):
        for chapter,action,prefix in [('confirm_love','yes','love'),('confirm_press','yes','press')]:
            for chance,suffix in ((.1,'home' if prefix=='love' else 'stream'),(.9,'stream' if prefix=='love' else 'other')):
                with self.subTest(chapter=chapter,chance=chance):
                    self.c.retired=False;self.c.story_queue=[];self.v['seen']=[]
                    self.queue(chapter)['chance']=chance
                    self.choose(chapter,action)
                    self.assertEqual('arc.'+prefix+'_'+suffix,self.c.ending)

    def test_major_reports_without_player_and_heat_ends(self):
        self.v['heat']=True;self.v['heat_since']=self.s.date
        champion=self.s.teams[0]
        ev=dict(id='major',name='World Major',type='major',status='done',champion=champion['name'],
                champion_roster=[p['name'] for p in champion['players']],awards={},field=[champion['name']],
                matches=[dict(id='final',team_a=champion['name'],team_b='Other',played=True,stage='GF',series='2-0')])
        arcs.event_open(self.c,self.s,ev)
        arcs.event_done(self.c,self.s,ev);arcs.event_done(self.c,self.s,ev)
        self.assertFalse(self.v['heat'])
        self.assertEqual(1,len([m for m in self.c.inbox if m.get('kind')=='news']))
        self.assertIn(champion['name'],self.c.inbox[-1]['title'])

    def test_major_final_loss_requires_own_played_final_and_only_once(self):
        for n,(kind,stage,won,forfeit,participated,expected) in enumerate([
            ('major','GF',False,False,True,1),('major','GF',True,False,True,0),
            ('major','SF',False,False,True,0),('t1','GF',False,False,True,0),
            ('major','GF',False,True,True,0),('major','GF',False,False,False,0)]):
            match=dict(id='final',stage=stage,played=True,forfeit=forfeit,
                team_a=self.mine['name'],team_b='Other',winner=self.mine['name'] if won else 'Other',series='2-0' if won else '0-2')
            ev=dict(id='final-check'+str(n),name='Final check',type=kind,status='done',
                field=[self.mine['name'],'Other'],awards={},champion=match['winner'],matches=[match])
            self.v['series']=[dict(key=arcs.key_for(self.s,ev,match) if participated else 'another-match',
                event=arcs.key_for(self.s,ev),maps=[],win=won,team_id=self.c.team_id,
                roster=sorted(p['player_id'] for p in self.mine['players']))]
            self.c.story_queue=[]
            arcs.event_done(self.c,self.s,ev);arcs.event_done(self.c,self.s,ev)
            self.assertEqual(expected,sum(r.get('arc')=='major_final_loss' for r in self.c.story_queue))

    def test_major_moods_follow_opening_expectation_champion_always_excited(self):
        for n,(rank,stage,won,mood) in enumerate([(1,'QF',False,'失望'),(2,'SF',False,'预料之中'),
                                                 (12,'QF',False,'激动'),(1,'GF',True,'激动')]):
            ev=dict(id='major-mood'+str(n),name='Mood Major',type='major',status='done',
                    field=[self.mine['name'],'Other'],awards={},champion=self.mine['name'] if won else 'Other',
                    arc_expectations={self.c.team_id:rank},matches=[dict(stage=stage,played=True,
                        team_a=self.mine['name'],team_b='Other',winner=self.mine['name'] if won else 'Other')])
            self.v['series']=[dict(event=arcs.key_for(self.s,ev),win=won,team_id=self.c.team_id,
                                  roster=sorted(p['player_id'] for p in self.mine['players']))]
            self.c.story_queue=[]
            arcs.event_done(self.c,self.s,ev)
            if mood=='失望':self.assertIn(mood,self.row('press')['text'])
            else:
                report=self.c.inbox[-1]
                self.assertGreater(len(report['body']),400)
                self.assertTrue(any(r.get('title')==report['title'] for r in self.c.story_queue))

    def test_heat_offset_is_reproducible_bounded_and_not_long_term(self):
        self.v['heat']=True;ev,match=self.result()
        player=self.c.my_player(self.s.teams);before=deepcopy(player['stats'])
        offsets=set()
        for n in range(80):
            match['id']='heat'+str(n);arcs.before_match(self.c,self.s,ev,match)
            delta=player['story_form_delta'];offsets.add(delta)
            arcs.before_match(self.c,self.s,ev,match)
            self.assertEqual(delta,player['story_form_delta'])
        self.assertEqual(set(range(-3,4)),offsets)
        self.assertEqual(before,player['stats'])
        player.update(form_delta=9,story_form_delta=3)
        self.assertEqual(10,effective_form_delta(player))

    def test_press_needs_20_maps_and_obeys_cooldown(self):
        self.v['romance']='single'
        for idx in range(19):self.result(idx,win=False,rating=.8)
        self.assertFalse(any(r.get('arc')=='press' for r in self.c.story_queue))
        self.result(20,win=False,rating=.8)
        before=self.c.attr_points
        self.choose('press','retire');self.choose('confirm_press','back')
        self.assertEqual(before+2,self.c.attr_points)
        self.result(21,win=False,rating=.8)
        self.assertFalse(any(r.get('arc')=='press' for r in self.c.story_queue))

    def test_birthday_both_have_reactions_training_plus_two(self):
        from cs2career.career.plot import birthday_popup
        before=self.c.attr_points
        for choice in ('wish','train'):
            row=birthday_popup('TestMate');row['id']='birthday-'+choice;self.c.story_queue.append(row)
            self.c.ack_story(row['id'],choice,self.s);self.c.ack_story(row['id'],choice,self.s)
            self.s.date=arcs.after(self.s.date,1)
        self.assertEqual(before+2,self.c.attr_points)
        self.assertEqual(2,len([h for h in self.v['history'] if h['title']=='TestMate的回应']))

    def test_na_is_explicit_bonus_not_every_american_career(self):
        self.c.incident_state.pop('arcs');before=self.c.attr_points
        arcs.initialize(self.c,self.s,{'scenario':'na_student'})
        self.v=arcs.state(self.c)
        self.assertEqual(before+3,self.c.attr_points)
        arcs.initialize(self.c,self.s,{'scenario':'na_student'})
        self.assertEqual(before+3,self.c.attr_points)
        self.choose('na_start','pro')
        self.assertEqual(before+5,self.c.attr_points)
        self.result()
        self.assertFalse(any(r.get('arc')=='romance_start' for r in self.c.story_queue))

    def test_na_no_data_cct_or_late_title_sends_family_not_forced_ending(self):
        self.na('study')
        self.v['events']=[dict(winner=True,type='cct',date=self.s.date,team_id=self.c.team_id,wins=1),
                          dict(winner=True,type='t2',date=arcs.after(self.v['deadline'],1),team_id=self.c.team_id,wins=1)]
        self.s.date=self.v['deadline'];arcs.tick(self.c,self.s)
        self.assertFalse(self.c.over())
        self.assertEqual('return_pending',self.v['na'])
        self.assertIsNotNone(self.row('na_return'))
        self.assertIn('家书',self.c.inbox[-1]['title'])
        self.assertFalse(any(r.get('arc')=='lvg_invite' for r in self.c.story_queue))

    def test_na_personal_data_without_title_gets_invite_and_return_letter(self):
        self.na('pro')
        for i in range(20):self.result(i,win=False,rating=1.01)
        self.c.story_queue=[]
        self.s.date=self.v['deadline'];arcs.tick(self.c,self.s)
        self.assertIsNotNone(self.row('lvg_invite'))
        self.assertFalse(self.v['na_assessment']['achievement'])
        self.assertEqual(20,self.v['na_assessment']['maps'])
        self.assertTrue(any('门一直给你留着' in r['title'] for r in self.c.inbox))
        count=len(self.c.inbox);arcs.tick(self.c,self.s)
        self.assertEqual(count,len(self.c.inbox))
        self.choose('lvg_invite','no')
        self.assertEqual('return_pending',self.v['na'])

    def test_na_major_title_qualifies_without_map_threshold(self):
        self.na('study')
        self.v['events']=[dict(winner=True,type='major',date=self.s.date,name='Test Major',key='major')]
        self.s.date=self.v['deadline'];arcs.tick(self.c,self.s)
        self.assertIsNotNone(self.row('lvg_invite'))
        self.assertTrue(self.v['na_assessment']['achievement'])
        self.assertTrue(any('支持你继续走' in r['title'] for r in self.c.inbox))
        self.choose('lvg_invite','no')
        self.assertEqual('closed',self.v['na'])

    def test_na_study_qualifier_success_lvg_really_joins(self):
        self.na('study');self.v['events']=[dict(winner=True,type='qual',date=self.s.date,team_id=self.c.team_id,wins=1)]
        self.s.date=self.v['deadline'];arcs.tick(self.c,self.s)
        self.c.story_queue=[r for r in self.c.story_queue if r.get('arc')=='lvg_invite']
        self.choose('lvg_invite','yes')
        self.assertEqual('Lynn Vision',self.c.my_team(self.s.teams)['name'])
        self.assertTrue(pt.state(self.c)['player_only'])
        self.assertEqual('closed',self.v['na'])
        self.assertEqual(1,sum(p.get('you',False) for t in self.s.teams for p in t['players']))

    def test_na_roster_decision_waits_for_live_event_not_forever(self):
        self.na('pro');self.s.date=self.v['deadline']
        ev=dict(id='live',status='live',field=[self.mine['name']],matches=[]);self.s.events=[ev]
        arcs.tick(self.c,self.s)
        self.assertFalse(any(r.get('arc')=='na_return' for r in self.c.story_queue))
        ev['status']='done';arcs.tick(self.c,self.s)
        self.assertIsNotNone(self.row('na_return'))

    def test_real_simulated_series_callback_starts_romance(self):
        ev=dict(id='arc-flow-cup',name='Arc Cup',type='cct',region='EU',size=2,
                format='single_elim',dates=[self.s.date,self.s.date],status='upcoming',
                matches=[],field=[],prize=1000,vrs_weight=1,best_of=1)
        self.s.events=[ev];self.c.inbox=[]
        letter=self.c.offer_invite(self.s,ev);self.c.accept_invite(self.s,letter['id'])
        self.s.open_event(ev)
        match=next(m for m in ev['matches'] if self.s.is_yours(m))
        with patch('cs2career.career.career.random.random',return_value=1):
            self.s.skip_your_series(match['id'])
        self.assertTrue(match['played']);self.assertEqual('done',ev['status'])
        self.assertEqual(1,len(self.v['series']));self.assertEqual(1,len(self.v['events']))
        self.assertTrue(self.v['series'][0]['maps'])
        self.assertIsNotNone(self.row('romance_start'))
        self.c.save();self.s.save()
        loaded=Career.load();self.assertTrue(arcs.state(loaded)['series'][0]['maps'])

    def test_na_return_preserves_player_not_old_club_cash_then_caster(self):
        self.na('pro');self.s.date=self.v['deadline'];arcs.tick(self.c,self.s)
        old=self.mine;old['money']=1234567;points=self.c.attr_points;money=self.c.money
        player=deepcopy(self.c.my_player(self.s.teams))
        self.choose('na_return','ok')
        new=self.c.my_team(self.s.teams)
        self.assertNotEqual(old['id'],new['id']);self.assertEqual('AS',new['region'])
        self.assertEqual(1234567,old['money']);self.assertNotEqual(old['money'],new['money'])
        self.assertEqual(player['stats'],self.c.my_player(self.s.teams)['stats'])
        self.assertEqual(player['player_id'],self.c.my_player(self.s.teams)['player_id'])
        self.assertEqual((points,money),(self.c.attr_points,self.c.money))
        self.s.date=arcs.after(self.v['returned'],30);arcs.tick(self.c,self.s)
        self.choose('dota_partner','ok')
        self.assertEqual('stable',self.v['romance'])
        self.s.date=self.v['deadline'];arcs.tick(self.c,self.s)
        self.assertEqual('arc.caster',self.c.ending)

    def test_roster_mutation_failure_rolls_back_both_saves(self):
        from cs2career.application import ApplicationState
        app=object.__new__(ApplicationState);app.career=self.c;app.season=self.s
        self.queue('na_return');old_id=self.c.team_id;old_teams=deepcopy(self.s.teams)
        row=self.row('na_return')
        with patch.object(Career,'_spawn_org',side_effect=ValueError('No starter cards')):
            with self.assertRaises(ValueError):
                app.personal_command(lambda c,s:c.ack_story(row['id'],'ok',s))
        self.assertEqual(old_id,app.career.team_id);self.assertEqual(old_teams,app.season.teams)
        self.assertEqual(old_id,Career.load().team_id)
        from cs2career.paths import save_root
        self.assertEqual(old_teams,json.loads((save_root()/'season.json').read_text('utf-8'))['teams'])
        self.assertTrue(any(r['id']==row['id'] for r in app.career.story_queue))

    def politics(self):
        roster=sorted(p['player_id'] for p in self.mine['players'])
        self.v['series']=[dict(key=str(i),team_id=self.c.team_id,roster=roster,win=False) for i in range(20)]
        self.v['events']=[dict(team_id=self.c.team_id,wins=0) for _ in range(3)]
        arcs.check_politics(self.c,self.s)
        return self.row('politics')

    def test_politics_target_stays_four_leave_player_can_apply(self):
        row=self.politics();row['chance']=.9;target=row['context']['target_id']
        pt.state(self.c).update(move_until='2099-01-01',apply_until=self.s.date)
        self.choose('politics','majority')
        self.assertTrue(self.c.unsigned);self.assertEqual('',self.c.team_id)
        self.assertIn(target,[p['player_id'] for p in self.mine['players']])
        self.assertEqual(5,len(self.mine['players']))
        self.assertEqual('',pt.blocked(self.c,self.s,applying=True))
        ids=[p['player_id'] for t in self.s.teams for p in t['players']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual('ArcTester',self.c.you_card['name'])
        self.assertTrue(self.c.you_card['player_id'])

    def test_politics_target_leaves_on_failed_counter_and_not_vrs(self):
        row=self.politics();row['chance']=.9;target=row['context']['target_id']
        self.choose('politics','defend')
        self.assertFalse(self.c.unsigned)
        self.assertNotIn(target,[p['player_id'] for p in self.mine['players']])
        self.assertIn(target,[p['player_id'] for p in self.c.free])

    def test_politics_neutral_stale_and_insufficient_roster_are_safe(self):
        row=self.politics();before=deepcopy(self.mine['players'])
        self.choose('politics','neutral');self.assertEqual(before,self.mine['players'])
        self.c.story_queue=[deepcopy(row)];self.mine['players'][0]['role']='entry'
        # Identity-based guard does not depend on role display labels.
        self.mine['players'][0]['player_id']='changed'
        before=deepcopy(self.mine['players']);self.choose('politics','majority')
        self.assertEqual(before,self.mine['players'])

    def test_injury_age_probability_loss_limits_and_recovery(self):
        cfg=deepcopy(arcs.config());p=self.c.my_player(self.s.teams)
        self.v['monthly']='';p['age']=19
        with patch.object(arcs,'roll',return_value=.01):arcs.tick(self.c,self.s)
        self.assertFalse(self.v['injuries'])
        p['age']=40;before=sum(p['stats'][a] for a in AXES);points=self.c.attr_points
        self.s.date=arcs.after(self.s.date,32)
        with patch.object(arcs,'roll',return_value=.01):arcs.tick(self.c,self.s)
        self.assertIn(before-sum(p['stats'][a] for a in AXES),(1,2))
        self.assertEqual(points,self.c.attr_points);self.assertEqual(-2,p['story_form_delta'])
        until=self.v['injury_active']['until'];self.s.date=until
        with patch.object(arcs,'roll',return_value=.99):arcs.tick(self.c,self.s)
        self.assertFalse(self.v['injury_active']);self.assertEqual(0,p['story_form_delta'])
        rates=[prob for _,prob in cfg['rules']['injury_monthly_rates']]
        self.assertEqual(sorted(rates),rates)
        self.assertGreaterEqual(len(cfg['injuries']),8)

    def test_legacy_opt_in_and_save_reload_keep_random_state(self):
        self.c.incident_state.pop('arcs');arcs.initialize(self.c,self.s)
        self.assertFalse(arcs.active(self.c));self.choose('upgrade','yes')
        self.assertTrue(arcs.active(self.c))
        self.queue('marriage');self.c.save();self.s.save()
        loaded=Career.load()
        self.assertEqual(arcs.state(self.c),arcs.state(loaded))
        self.assertEqual(self.row('marriage')['chance'],next(r for r in loaded.story_queue if r.get('arc')=='marriage')['chance'])

    def test_extension_schema_rejects_unsafe_actions_and_unresolved_refs(self):
        for raw in [dict(rules={'focus_reward':-1}),dict(rules={'injury_monthly_rates':[[20,2]]}),
                    dict(chapters={'press':{'choices':[dict(id='endure',action='finish')]}}),
                    dict(chapters={'press':{'choices':[dict(id='endure',next='missing')]}})]:
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                validate_payload('incidents',dict(schema_version=1,arc_overrides=raw))

    def test_shipped_extension_chapter_chain_reward_and_replay(self):
        template=Path(__file__).resolve().parents[1]/'extensions/_templates/career-arcs-pack'
        with TemporaryDirectory() as folder:
            shutil.copytree(template,Path(folder)/'arcs')
            registry=PackRegistry(Path(folder))
            self.assertEqual('ready',registry.packs[0].status,registry.packs[0].errors)
            with patch.object(arcs,'get_registry',return_value=registry):
                before=self.c.attr_points
                self.queue('romance_start');self.choose('romance_start','none')
                self.assertEqual(before+2,self.c.attr_points)
                row=self.row('author_focus_followup')
                next_id=next(x for x in row['choices'] if x['id']=='talk')['next']
                self.c.save();loaded=Career.load()
                saved=next(r for r in loaded.story_queue if r.get('arc')=='author_focus_followup')
                self.assertEqual(row['choices'],saved['choices'])
                self.choose('author_focus_followup','talk')
                self.assertIsNotNone(self.row(next_id))
                self.choose(next_id,'ok')
                self.c.ack_story(row['id'],'talk',self.s)
                self.assertEqual(before+2,self.c.attr_points)

    def test_pending_custom_chapter_survives_pack_removal_and_cycles_rejected(self):
        raw=dict(chapters={
            'romance_start':dict(choices=[dict(id='none',next='custom_end')]),
            'custom_end':dict(title='Saved text',text=['Original saved text'],choices=[dict(id='ok',label='OK')])})
        with TemporaryDirectory() as folder:
            registry=PackRegistry(Path(folder))
            with patch.object(registry,'payloads',return_value=[{'arc_overrides':raw}]),patch.object(arcs,'get_registry',return_value=registry):
                self.queue('romance_start')
        self.choose('romance_start','none')
        self.assertEqual('Original saved text',self.row('custom_end')['text'])
        self.choose('custom_end','ok')
        raw['chapters']['custom_end']['choices'][0]['next']='custom_end'
        with self.assertRaises(ValueError):arcs.validate_overrides(raw)

    def test_history_pagination_retirement_does_not_reconstruct(self):
        for n in range(44):arcs.notice(self.c,self.s,'Saved '+str(n),'Original '+str(n),str(n))
        self.assertEqual(30,len(arcs.public(self.c)['history']))
        first=arcs.history_page(self.c,1);last=arcs.history_page(self.c,3)
        self.assertEqual((44,3,20),(first['total'],first['pages'],len(first['rows'])))
        self.assertEqual('Saved 43',first['rows'][0]['title'])
        self.assertEqual(4,len(last['rows']))
        self.assertEqual([],arcs.history_page(self.c,4)['rows'])

    def test_world_transaction_boundary(self):
        for action in ('politics','lvg','return_home','love_retire','press_retire','finish'):
            self.assertTrue(arcs.changes_world({'choices':[dict(id='yes',action=action)]},'yes'))
        for action in ('continue','single','heat','steady','enable','endure','reunion'):
            self.assertFalse(arcs.changes_world({'choices':[dict(id='yes',action=action)]},'yes'))
