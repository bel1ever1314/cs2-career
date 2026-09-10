"""Isolated fixtures: new transfer prices, position awards and story packs."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import ExitStack

from cs2career.application import ApplicationState
from cs2career.career import Career, story, verse
from cs2career.career.transfers import candidates, guaranteed, buyout_price, identity
from cs2career.career.career import transfer_fee
from cs2career.content.loader import PackRegistry
from cs2career.league.awards import _event_five
from cs2career.league.season import Season


class EditorialTests(unittest.TestCase):
    def test_big_stage_milestones_ignore_small_events_even_without_pack_filter(self):
        c=Career();c.exists=True;c.team_id='a';c.player_name='Tester';c.save=lambda:None
        s=SimpleNamespace(teams=[{'id':'a','name':'A','players':[]}],year=2026)
        beats=[dict(id=when,when=when,title='Story',text='{event}') for when in ('first_lan','first_final')]
        with patch.object(story,'STORIES',beats):
            for kind in ('cct','t2','qual'):
                for when in ('first_lan','first_final'): c.watch(s,{'type':kind,'name':'Small'},when)
            self.assertEqual([],c.story_queue)
            for when in ('first_lan','first_final'): c.watch(s,{'type':'t1','name':'Big'},when)
            self.assertEqual(2,len(c.story_queue))
            for beat in list(c.story_queue):c.ack_story(beat['id'])
            c.watch(s,{'type':'major','name':'Major'},'first_final')
            self.assertEqual([],c.story_queue)

    def test_five_awards_have_unique_roles_and_do_not_relabel_stars(self):
        roles=('igl','lurk','rifle','awp','entry')
        rows=[dict(player=str(i),player_id=str(i),team='A',role=role,rating=1+i*.1,kpr=.8,maps=10) for i,role in enumerate(roles)]
        rows += [dict(player='Super AWP',player_id='star',team='B',role='awp',rating=2,kpr=1,maps=10)]
        result=_event_five(rows)
        self.assertEqual(list(roles),[r['role'] for r in result])
        self.assertEqual('Super AWP',result[3]['player'])
        self.assertEqual(5,len({r['player_id'] for r in result}))
        self.assertEqual([], _event_five([dict(player='Old',team='A',rating=2,kpr=1,maps=10)]))

    def test_role_award_uses_frozen_map_roles(self):
        season=Season.__new__(Season);store={}
        p=dict(player_id='p',name='Player',k=20,d=10,a=3,damage=2000,kast_rounds=14)
        for role in ('awp','awp','rifle'):season._add_player(store,'A',dict(p,role=role),20)
        self.assertEqual('awp',store['A|p']['role'])
        self.assertEqual({'awp':2,'rifle':1},store['A|p']['role_maps'])

    def test_three_features_have_personal_titles_evidence_and_no_fabricated_titles(self):
        features=[]
        for rank in (1,2,3):
            row=dict(rank=rank,player=f'Player{rank}',team='Test Team',rating=1.35,maps=42,mvp=0,evp=2,titles=0,majors=0)
            f=verse.decorate(row,2026,'2026')['feature'];features.append(f)
            self.assertIn(row['player'],f['title'])
            text=' '.join(s['text'] for s in f['sections'])
            self.assertIn('42 张地图',text);self.assertIn('1.35',text)
            self.assertIn('0 次赛事冠军',text);self.assertIn('缺少记录',text)
            self.assertGreater(len(text),300)
            saved=json.loads(json.dumps(dict(row,feature=f)))
            self.assertEqual(f,verse.decorate(saved,2030,'2026')['feature'])
        self.assertEqual(3,len({f['title'] for f in features}))

    def test_story_extension_load_render_ack_reload_and_disabled_pack(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);pack=root/'story-test';(pack/'stories').mkdir(parents=True)
            manifest={'id':'story-test','schema_version':1,'types':['stories']}
            (pack/'pack.json').write_text(json.dumps(manifest),encoding='utf-8')
            (pack/'stories'/'beats.json').write_text(json.dumps({'stories':[
                {'id':'pack.start','when':'start','origin':'academy','title':'{team} 开始','text':'{player} 的 {year} 年'},
                {'id':'pack.final','when':'first_final','title':'决赛','text':'{event}'}]}),encoding='utf-8')
            registry=PackRegistry(root)
            self.assertEqual('ready',registry.packs[0].status)
            with patch('cs2career.content.get_registry',return_value=registry),patch.object(story,'STORIES',story.load_stories()),patch.object(Career,'path',return_value=root/'career.json'):
                story.reload_stories()
                c=Career();c.exists=True;c.origin='academy';c.player_name='Pack Player';c.team_id='a'
                s=SimpleNamespace(teams=[{'id':'a','name':'Pack Team','players':[]}],year=2026)
                c.watch(s,when='start');beat=next(x for x in c.story_queue if x['id']=='pack.start')
                self.assertEqual('Pack Team 开始',beat['title']);self.assertEqual('Pack Player 的 2026 年',beat['text'])
                c.ack_story('pack.start');restored=Career.load();restored.watch(s,when='start')
                self.assertFalse(any(x['id']=='pack.start' for x in restored.story_queue))
            manifest['enabled']=False;(pack/'pack.json').write_text(json.dumps(manifest))
            self.assertEqual([],PackRegistry(root).payloads('stories'))


class TransferTests(unittest.TestCase):
    def setUp(self):
        stack=ExitStack();self.addCleanup(stack.close)
        root=Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch('cs2career.league.season.STATE_PATH',root/'season.json'))
        stack.enter_context(patch.object(Career,'path',return_value=root/'career.json'))
        stack.enter_context(patch('cs2career.paths.save_root',return_value=root))
        self.state=ApplicationState()
        self.state.create_career(dict(era='2026',mode='create',origin='academy',name='Buyer',org='Buyer Club',role='rifle',region='AS'))
        self.c=self.state.career;self.s=self.state.season;self.mine=self.c.my_team(self.s.teams)
        self.mine['money']=3000000  # Late-game UNIT fixture, not a flow/balance run.
        self.leaving=next(p for p in self.mine['players'] if not p.get('you'))

    def test_active_buyout_is_guaranteed_keeps_two_rosters_and_survives_reload(self):
        seller=next(t for t in self.s.teams if t['name']=='Vitality')
        target=next(p for p in seller['players'] if p['name']=='ZywOo')
        fee,mult=buyout_price(target);self.assertEqual(5,mult)
        before=self.mine['money'];before_seller=seller['money']
        reserves=[p for p in self.c.free if p['role']==target['role']]
        with patch('cs2career.career.career.random.random',side_effect=AssertionError('guaranteed must not roll')):
            guaranteed(self.c,self.s,identity(target),seller['id'],identity(self.leaving),fee)
        self.assertEqual(before-fee,self.mine['money'])
        self.assertIn(identity(target),{identity(p) for p in self.mine['players']})
        self.assertNotIn(identity(target),{identity(p) for p in seller['players']})
        self.assertEqual(5,len(seller['players']));self.assertEqual(5,len(self.mine['players']))
        self.assertTrue(any(identity(p)==identity(self.leaving) for p in self.c.free))
        replacement=next(p for p in seller['players'] if identity(p) in {identity(r) for r in reserves})
        self.assertEqual(before_seller+fee-transfer_fee(replacement['ability']),seller['money'])
        all_ids=[identity(p) for t in self.s.teams for p in t['players']]
        self.assertEqual(len(all_ids),len(set(all_ids)))
        self.state.persist();restored=ApplicationState()
        self.assertEqual(self.mine['money'],restored.career.my_team(restored.season.teams)['money'])
        with self.assertRaises(ValueError):guaranteed(self.c,self.s,identity(target),seller['id'],identity(self.leaving),fee)
        self.assertEqual(before-fee,self.mine['money'])

    def test_failed_or_stale_buyout_never_mutates_balance_or_rosters(self):
        target=self.c.free[0];fee,_=buyout_price(target)
        before=deepcopy((self.mine,self.c.free))
        for replacement,price in [(identity(self.leaving),fee+1),(identity(self.mine['players'][0]),fee)]:
            with self.assertRaises(ValueError):guaranteed(self.c,self.s,identity(target),'',replacement,price)
            self.assertEqual(before,(self.mine,self.c.free))
        self.s.events[0].update(status='live',field=[self.mine['name']])
        with self.assertRaises(ValueError):guaranteed(self.c,self.s,identity(target),'',identity(self.leaving),fee)
        self.assertEqual(before,(self.mine,self.c.free))

    def test_free_player_has_two_prices_normal_failure_only_charges_negotiation(self):
        rows=candidates(self.c,self.s);p=next(p for p in rows if not p['seller_id'] and 0<p['normal_chance']<1)
        before=self.mine['money'];roster=deepcopy(self.mine['players'])
        with patch('cs2career.career.career.random.random',return_value=1):
            self.c.buy(self.s,p['name'],identity(self.leaving),p['player_id'])
        self.assertEqual(before-p['negotiation_fee'],self.mine['money'])
        self.assertEqual(roster,self.mine['players'])
        self.assertGreater(p['guaranteed_fee'],p['normal_fee'])
        with patch('cs2career.career.career.random.random',side_effect=AssertionError('no roll')):
            guaranteed(self.c,self.s,p['player_id'],'',identity(self.leaving),p['guaranteed_fee'])
        self.assertIn(p['player_id'],{identity(x) for x in self.mine['players']})

    def test_authenticated_http_quote_and_buyout(self):
        from cs2career.web.server import create_server
        from urllib.request import Request,urlopen
        from threading import Thread
        server=create_server(self.state);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base=f'http://127.0.0.1:{server.server_port}'
            headers={'X-Career-Token':server.token,'Content-Type':'application/json'}
            with urlopen(Request(base+'/api/transfers',headers=headers)) as res: rows=json.load(res)['players']
            p=next(p for p in rows if not p['seller_id'] and not p['blocked'])
            before=self.mine['money']
            body=dict(mode='guaranteed',player_id=p['player_id'],seller_id='',replace_id=identity(self.leaving),fee=p['guaranteed_fee'])
            with urlopen(Request(base+'/api/market/buy',headers=headers,data=json.dumps(body).encode())) as res: payload=json.load(res)
            self.assertTrue(payload['ok'])
            self.assertEqual(before-p['guaranteed_fee'],payload['state']['career']['money'])
            self.assertIn(p['player_id'],{x['player_id'] for x in payload['state']['career']['roster']})
        finally:
            server.shutdown();thread.join();server.server_close()
