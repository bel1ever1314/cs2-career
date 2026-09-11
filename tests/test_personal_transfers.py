"""Personal career commands; invoked only through the isolated test runner."""
import copy
import json
import os
import random
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from cs2career.application import ApplicationState
from cs2career.career import Career
from cs2career.career import player_transfers as pt, incidents
from cs2career.career.transfers import guaranteed
from cs2career.content.rules import validate_payload
from cs2career.league import Season
from cs2career.world.ability import stats_for, ability_of


def team(n, score=75):
    roles = ['rifle', 'awp', 'igl', 'entry', 'lurk']
    return dict(id=f't{n}', name=f'Team{n}', region='EU', money=100000,
        command=70, mentality=70, strong_maps=[], weak_maps=[],
        players=[dict(player_id=f'p{n}_{i}', name=f'Player{n}_{i}', role=r, ability=score,
                      stats=stats_for(f'Player{n}_{i}', r, score), form_delta=0, form=score,
                      command=70, age=22, you=False) for i, r in enumerate(roles)])


class PersonalTransferTests(unittest.TestCase):
    def test_shipped_transfer_story_template_validates(self):
        raw=json.loads((Path(__file__).resolve().parents[1]/'extensions/_templates/transfer-story-pack/incidents/example.json').read_text('utf-8'))
        validate_payload('incidents',raw)

    def setUp(self):
        self.c=Career();self.c.exists=True;self.c.team_id='t0';self.c.mode='create'
        self.c.player_name='Player0_0';self.c.role='rifle';self.c.money=1234
        self.c.inventory=[{'instance_id':'keep-item','skin_id':'test'}]
        self.c.save=Mock()
        self.s=SimpleNamespace(date='2026-01-01',year=2026,era='2026',events=[],teams=[team(i) for i in range(7)],
                              vrs=SimpleNamespace(table=lambda *a:[{'id':f't{i}','rank':i+1,'vrs':1000} for i in range(7)]))
        self.s.teams[0]['players'][0]['you']=True
        self.c._remember_you(self.s)

    def roll(self, number=20, target='t1', role='rifle'):
        with patch.object(pt, 'draw', return_value=number): return pt.apply(self.c,self.s,target,role)

    def decide(self, choice='accept'):
        row=next(r for r in self.c.story_queue if r.get('when')=='transfer_decision')
        self.c.ack_story(row['id'],choice,self.s)

    def finish_stories(self):
        while self.c.story_queue:
            row=self.c.story_queue[0]
            self.c.ack_story(row['id'],(row.get('choices') or [{'id':''}])[0]['id'],self.s)

    def test_d20_boundaries_and_exact_probabilities(self):
        self.assertTrue(pt.wins(20,-8));self.assertFalse(pt.wins(1,6))
        self.assertEqual([.45,.55,.65],[sum(pt.wins(n,m) for n in range(1,21))/20 for m in (0,2,4)])
        self.assertFalse(pt.wins(11,0));self.assertTrue(pt.wins(12,0))

    def test_quote_reads_role_without_mutating_calibration(self):
        old=copy.deepcopy(self.s.teams)
        q=pt.quote(self.c,self.s,self.s.teams[1],'awp')
        self.assertEqual(ability_of(old[0]['players'][0]['stats'],'awp'),q['ability'])
        self.assertEqual(old,self.s.teams)

    def test_failed_roll_global_and_target_cooldowns(self):
        original=copy.deepcopy(self.s.teams)
        self.roll(1)
        self.assertEqual(original,self.s.teams)
        self.assertEqual('2026-01-31',pt.state(self.c)['apply_until'])
        with self.assertRaises(ValueError):self.roll(20,'t2')
        self.s.date='2026-01-31'
        with self.assertRaises(ValueError):self.roll(20,'t1')
        self.roll(20,'t2')
        self.assertEqual(2,len(pt.state(self.c)['attempts']))

    def test_success_requires_decision_and_refusal_keeps_cooldown(self):
        original=copy.deepcopy(self.s.teams)
        self.roll();self.assertEqual(original,self.s.teams)
        self.decide('refuse');self.assertEqual(original,self.s.teams)
        self.assertEqual('create',self.c.mode)
        self.assertEqual('2026-04-01',pt.state(self.c)['apply_until'])
        with self.assertRaises(ValueError):self.roll()

    def test_founder_move_keeps_assets_and_both_five_player_teams(self):
        before=copy.deepcopy(self.s.teams);inv=copy.deepcopy(self.c.inventory)
        self.c.loan={'kind':'bank','principal':8000,'rate':.03,'arrears':100,'last_interest_month':'2026-01'}
        self.roll();self.decide()
        self.assertEqual(('join','t1',1234),(self.c.mode,self.c.team_id,self.c.money))
        self.assertEqual(inv,self.c.inventory);self.assertIsNone(self.c.loan)
        self.assertEqual(8000,self.s.teams[0]['career_bank_loan']['principal'])
        self.assertTrue(self.s.teams[0]['career_ai_managed'])
        self.assertEqual([5]*7,[len(t['players']) for t in self.s.teams])
        self.assertEqual(1,sum(p.get('you',False) for t in self.s.teams for p in t['players']))
        self.assertEqual([t['money'] for t in before],[t['money'] for t in self.s.teams])
        self.assertEqual('2026-06-30',pt.state(self.c)['move_until'])
        self.assertTrue(pt.state(self.c)['player_only'])
        self.assertIn('把队名',self.c.story_queue[0]['title'])

    def test_free_recruit_cost_is_charged_to_original_club_only(self):
        candidate=team(10,60)['players'][0]
        self.c.free=[candidate]
        from cs2career.career.career import transfer_fee
        price=transfer_fee(candidate['ability'])
        self.s.teams[0]['money']=price+10
        self.roll();self.decide()
        self.assertEqual(10,self.s.teams[0]['money'])
        self.assertEqual(100000,self.s.teams[1]['money'])
        self.assertIn(candidate['player_id'],[p['player_id'] for p in self.s.teams[0]['players']])
        self.assertIn('p1_0',[p['player_id'] for p in self.c.free])

    def test_duplicate_ack_is_noop_and_new_target_is_locked(self):
        self.roll();sid=self.c.story_queue[0]['id'];self.decide()
        before=copy.deepcopy(self.c.to_json())
        self.c.ack_story(sid,'accept',self.s)
        self.assertEqual(before,self.c.to_json())
        self.finish_stories();self.s.date='2026-06-29'
        with self.assertRaises(ValueError):self.roll(20,'t2')
        self.s.date='2026-06-30';self.roll(20,'t2')

    def test_live_event_and_training_and_pending_story_block_before_roll(self):
        for target in ['Team0','Team1']:
            self.s.events=[dict(status='live',field=[target],matches=[])]
            with self.assertRaises(ValueError):self.roll()
        self.s.events=[];self.c.training_session={'nonce':'x'}
        with self.assertRaises(ValueError):self.roll()
        self.c.training_session=None;self.c.story_queue=[dict(id='s',choices=[dict(id='x')])]
        with self.assertRaises(ValueError):self.roll()
        self.assertEqual([],pt.state(self.c)['attempts'])

    def test_changed_target_and_new_live_event_cannot_commit(self):
        self.roll();self.s.teams[1]['players'][0]['player_id']='replacement'
        before=copy.deepcopy(self.s.teams)
        with self.assertRaises(ValueError):self.decide()
        self.assertEqual(before,self.s.teams)
        self.decide('refuse')

    def test_duplicate_participant_fails_without_touching_rosters(self):
        self.roll();self.s.teams[2]['players'][0]['player_id']='p1_0'
        before=copy.deepcopy(self.s.teams)
        with self.assertRaises(ValueError):self.decide()
        self.assertEqual(before,self.s.teams)

    def test_offers_are_for_improvements_unique_and_capped_per_year(self):
        p=self.s.teams[0]['players'][0]
        p['stats']=stats_for(p['name'],'rifle',95);p['ability']=95
        with patch.object(pt,'draw',return_value=1):
            for month in range(1,13):
                self.s.date=f'2026-{month:02d}-01';pt.dispatch(self.c,self.s)
                for row in self.c.inbox:row['status']='declined'
        offers=pt.state(self.c)['offers']
        self.assertEqual(4,len(offers));self.assertEqual(4,len({r['team_id'] for r in offers}))
        self.assertTrue(all(r['ability']>=r['target_ability']+3 for r in self.c.inbox))
        self.s.date='2027-01-01'
        with patch.object(pt,'draw',return_value=1):pt.dispatch(self.c,self.s)
        self.assertEqual(5,len(pt.state(self.c)['offers']))

    def test_offer_does_not_reroll_and_expires(self):
        q=pt.quote(self.c,self.s,self.s.teams[1],'rifle')
        row=self.c._push_mail('contract',self.s.date,dict(title='offer',body='test'),dict(**q,status='open',personal_transfer=True,expires='2026-01-31'))
        with patch.object(pt,'draw',side_effect=AssertionError('must not roll')):
            self.c.accept_contract(self.s,row['id'])
        self.decide('refuse');self.assertEqual('declined',row['status'])
        row['status']='open';self.s.date='2026-02-01'
        with self.assertRaises(ValueError):pt.open_offer(self.c,self.s,row)
        self.assertEqual('expired',row['status'])

    def test_transfer_hooks_do_not_deadlock_decision_and_extend_with_flags(self):
        payload={'schema_version':1,'_pack_id':'transfer.test','incidents':[dict(id='joined',when='transfer_joined',title='欢迎 {player}',
            text='{old_team} → {new_team}',choices=[dict(id='promise',label='努力',effects=[dict(type='flag',key='promised',value=True)])])]}
        validate_payload('incidents',{k:v for k,v in payload.items() if k!='_pack_id'})
        registry=SimpleNamespace(payloads=lambda _: [payload])
        with patch('cs2career.career.incidents.get_registry',return_value=registry):
            self.roll();pt.drain_hooks(self.c,self.s)
            self.assertEqual(1,len(self.c.story_queue))
            self.decide();self.assertFalse(incidents.pending(self.c))
            farewell=self.c.story_queue[0];self.c.ack_story(farewell['id'],'thanks',self.s)
            self.assertTrue(incidents.pending(self.c))
            event=next(r for r in self.c.story_queue if r.get('kind')=='incident');self.assertEqual('Team0 → Team1',event['text'])
            self.c.ack_story(event['id'],'promise',self.s)
            self.assertTrue(incidents.state(self.c)['flags']['transfer.test:promised'])

    def test_former_opponent_hook_only_once(self):
        self.roll();self.decide();self.finish_stories()
        self.s.events=[dict(matches=[dict(id='reunion',team_a='Team0',team_b='Team1')])]
        with patch.object(pt,'drain_hooks'):
            pt.former_opponent(self.c,self.s,'reunion');pt.former_opponent(self.c,self.s,'reunion')
        self.assertEqual(1,sum(h['when']=='transfer_former_team' for h in pt.state(self.c)['hooks']))

    def test_personal_debt_repayments_go_to_original_creditor(self):
        self.c.mode='join';self.c.loan=dict(kind='club',principal=100,arrears=0,rate=.03,missed=0,last_interest_month='2026-01')
        self.roll();self.decide()
        balances=[t['money'] for t in self.s.teams]
        self.c.repay(self.s,100)
        self.assertEqual(balances[0]+100,self.s.teams[0]['money'])
        self.assertEqual(balances[1],self.s.teams[1]['money'])

    def test_old_club_finance_ticks_once_and_never_charges_player(self):
        self.c.loan=dict(kind='bank',principal=1000,arrears=0,rate=.03,last_interest_month='2026-01')
        self.roll();self.decide()
        pt.settle_ai_clubs(self.c,self.s,'2026-02');first=copy.deepcopy(self.s.teams[0])
        pt.settle_ai_clubs(self.c,self.s,'2026-02')
        self.assertEqual(first,self.s.teams[0]);self.assertEqual(1234,self.c.money)

    def test_employee_cannot_buy_change_roster_or_dissolve(self):
        self.roll();self.decide()
        for action in [lambda:self.c.buy(self.s,'x'),lambda:self.c.found_new_now(self.s),
                       lambda:guaranteed(self.c,self.s,'x','','')]:
            with self.assertRaises(ValueError):action()

    def test_fixed_seed_does_not_consume_simulation_rng(self):
        before=random.getstate();self.roll(7)
        self.assertEqual(before,random.getstate())
        self.assertEqual(pt.draw(self.c,'fixed',20),pt.draw(self.c,'fixed',20))

    def test_optional_state_survives_save_and_old_schema2_defaults(self):
        with tempfile.TemporaryDirectory() as folder, patch('cs2career.career.career.CAREER_PATH',Path(folder)/'career.json'):
            del self.c.save
            self.roll();self.c.save();loaded=Career.load()
            self.assertEqual(pt.state(self.c)['attempts'],pt.state(loaded)['attempts'])
            blob=self.c.to_json();blob.pop('personal_transfers')
            self.c.path().write_text(json.dumps(blob),encoding='utf-8')
            loaded=Career.load();self.assertEqual([],pt.state(loaded)['moves'])


class TransferTransactionTests(unittest.TestCase):
    def test_real_http_create_roll_join_reload_and_permissions(self):
        from cs2career.web.server import create_server
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,CS2CAREER_SAVE_DIR=folder), \
             patch('cs2career.career.career.CAREER_PATH',Path(folder)/'career.json'), \
             patch('cs2career.league.season.STATE_PATH',Path(folder)/'season.json'):
            app=ApplicationState()
            app.create_career(dict(mode='create',era='2026',name='TransferHttpTest',org='Transfer Test Club',origin='academy',role='rifle',region='EU'))
            # Acknowledge the opening through the normal story command.
            while app.career.story_queue:
                row=app.career.story_queue[0]
                app.career.ack_story(row['id'],(row.get('choices') or [{'id':''}])[0]['id'],app.season)
            app.persist()
            server=create_server(app);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            base=f'http://127.0.0.1:{server.server_port}'
            def request(path,body=None,token=True):
                req=Request(base+path,data=json.dumps(body).encode() if body is not None else None,
                    headers={'X-Career-Token':server.token if token else '', 'Content-Type':'application/json'})
                with urlopen(req,timeout=15) as response:return json.load(response)
            try:
                with self.assertRaises(HTTPError):request('/api/player-transfers',token=False)
                targets=request('/api/player-transfers')['targets']
                target=next(r for r in targets if not r['blocked'])
                inv=copy.deepcopy(app.career.inventory);pocket=app.career.money;old_id=app.career.team_id
                with patch.object(pt,'draw',return_value=20):
                    response=request('/api/player/transfers/apply',dict(team_id=target['team_id'],role=target['role']))
                self.assertEqual(20,response['transfer']['roll'])
                self.assertEqual(old_id,app.career.team_id)
                with self.assertRaises(HTTPError):request('/api/player/transfers/apply',dict(team_id=target['team_id'],role=target['role']))
                pending=next(r for r in app.career.story_queue if r.get('when')=='transfer_decision')
                request('/api/story/ack',dict(id=pending['id'],choice='accept'))
                self.assertEqual(target['team_id'],app.career.team_id)
                self.assertEqual(pocket,app.career.money);self.assertEqual(inv,app.career.inventory)
                self.assertTrue(request('/api/state')['career']['player_only'])
                mapping={p['name']:p['role'] for p in app.career.my_team(app.season.teams)['players']}
                mapping[app.career.player_name]='awp'
                self.assertTrue(request('/api/roles',dict(roles=mapping,player=app.career.player_name))['ok'])
                self.assertEqual('awp',app.career.role)
                with self.assertRaises(HTTPError):request('/api/market/buy',dict(mode='normal',player='x'))
                loaded=Career.load();self.assertEqual(app.career.personal_transfers,loaded.personal_transfers)
                loaded_season=Season.load_or_new()
                self.assertEqual(1,sum(p.get('you',False) for t in loaded_season.teams for p in t['players']))
                self.assertEqual(5,len(loaded.my_team(loaded_season.teams)['players']))
            finally:
                server.shutdown();worker.join();server.server_close()

    def test_pair_rollback_and_crash_recovery(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,CS2CAREER_SAVE_DIR=folder), \
             patch('cs2career.career.career.CAREER_PATH',Path(folder)/'career.json'), \
             patch('cs2career.league.season.STATE_PATH',Path(folder)/'season.json'):
            app=ApplicationState.__new__(ApplicationState)
            app.season=Season();app.career=Career();app.season.career=app.career
            app.career.money=17;app.persist()
            def fail(c,s):
                c.money=99;s.teams[0]['money']=99
                raise ValueError('test failure')
            with self.assertRaises(ValueError):app.personal_command(fail)
            self.assertEqual(17,app.career.money)
            self.assertEqual(17,json.loads((Path(folder)/'career.json').read_text('utf-8'))['money'])
            app.personal_command(lambda c,s:setattr(c,'money',31))
            self.assertEqual(31,Career.load().money)
            backup=app.backup();app.career.money=88;app.persist()
            (Path(folder)/'personal-transfer.pending.json').write_text(json.dumps({'backup':backup.name}),encoding='utf-8')
            ApplicationState._recover_personal_command()
            self.assertEqual(31,Career.load().money)
