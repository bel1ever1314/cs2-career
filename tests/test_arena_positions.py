"""Ranked identity, local five-role optimisation and hand-off regression."""
from copy import deepcopy
from itertools import permutations
from pathlib import Path
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from cs2career.arena import Arena
from cs2career.arena_roles import assign_positions
from cs2career.cs2 import launch
from cs2career.web.server import create_server
from cs2career.world.ability import ability_of, ensure_role_calibration, playing_ability
from cs2career.world.roles import PLAYABLE_ROLES
from test_arena import fixture_state, result_for


class RankedPositionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.arena=Arena(Path(self.tmp.name)/'arena.json');self.state=fixture_state()
        self.ids=list(self.arena.roster(self.state))[:10]

    def body(self,**kw):return dict(revision=self.arena.data['revision'],**kw)

    def ready(self):
        self.arena.matchmake(self.state,self.body())
        while self.arena.data['lobby']['phase']!='ready':
            l=self.arena.data['lobby']
            if not self.arena.turn(l)['human']:self.arena.advance(self.body())
            elif l['phase']=='draft':self.arena.pick(self.body(player_id=next(p for p in l['selection'] if p not in l['a']+l['b'])))
            elif l['phase']=='veto':self.arena.ban(self.body(map=next(m for m in l['map_pool'] if m not in [b['map'] for b in l['bans']])))
            else:self.arena.choose_side(self.body(side='ct'))
        return self.arena.data['lobby']

    def test_role_assignment_optimal_stable_and_does_not_mutate_club(self):
        players=deepcopy(self.state.season.teams[0]['players'])
        for i,p in enumerate(players):
            p['role']='awp';p['name']='duplicate name'
            p['stats']=dict(firepower=50+i*4,entrying=80-i*10,trading=30+i*12,
                            opening=80-i*8,clutching=20+i*16,sniping=95-i*15,utility=50)
        before=deepcopy(players);assigned=assign_positions(players)
        self.assertEqual(before,players)
        self.assertEqual(set(PLAYABLE_ROLES),{p['role'] for p in assigned})
        self.assertEqual([p['player_id'] for p in players],[p['player_id'] for p in assigned])
        calibrated=deepcopy(players)
        for p in calibrated:ensure_role_calibration(p)
        best=max(sum(round(ability_of(p['stats'],r)*10) for p,r in zip(calibrated,roles)) for roles in permutations(PLAYABLE_ROLES))
        self.assertEqual(best,sum(round(playing_ability(p)*10) for p in assigned))
        self.assertEqual({p['player_id']:p for p in assigned},{p['player_id']:p for p in assign_positions(list(reversed(players)))})
        old_ability={p['player_id']:p['ability'] for p in before}
        for p in assigned:self.assertLessEqual(abs(p['ability']-old_ability[p['player_id']]),6)

    def test_missing_stats_not_invented_and_ties_keep_native_positions(self):
        players=deepcopy(self.state.season.teams[0]['players'])
        for p,r in zip(players,PLAYABLE_ROLES):p.pop('stats',None);p['role']=r
        assigned=assign_positions(players)
        self.assertEqual([p['role'] for p in players],[p['role'] for p in assigned])
        self.assertTrue(all('stats' not in p for p in assigned))
        for invalid in (players[:4],players[:4]+players[:1]):
            with self.assertRaises(ValueError):assign_positions(invalid)

    def test_rank_requires_exact_career_id_and_reads_do_not_mutate(self):
        before=deepcopy(self.arena.data)
        for human in ('',self.ids[1],'unknown',None):
            with self.assertRaisesRegex(ValueError,'固定使用'):
                self.arena.matchmake(self.state,self.body(human_id=human))
        public=self.arena.public(self.state)
        self.assertEqual(self.ids[0],public['rank_human_id']);self.assertTrue(public['rank_identity_locked'])
        self.assertEqual(before,self.arena.data)
        self.state.career.exists=False
        with self.assertRaisesRegex(ValueError,'创建生涯'):self.arena.matchmake(self.state,self.body())
        self.assertEqual('',self.arena.public(self.state)['rank_human_id'])
        self.arena.create(self.state,self.body(mode='custom',players=self.ids,human_id=self.ids[1]))
        self.assertEqual(self.ids[1],self.arena.data['lobby']['human_id'])
        self.arena.configure(self.body(map='dust2',ct='b',human_id=''))
        self.assertEqual('',self.arena.data['lobby']['human_id'])
        self.assertEqual(1,self.arena.data['lobby']['role_assignment_version'])
        for side in ('a','b'):
            self.assertEqual(set(PLAYABLE_ROLES),{self.arena.data['lobby']['roster'][pid]['role']
                             for pid in self.arena.data['lobby'][side]})

    def test_missing_stable_id_does_not_guess_by_name(self):
        self.state.career.you_card.pop('player_id')
        with self.assertRaisesRegex(ValueError,'创建生涯'):self.arena.matchmake(self.state,self.body())
        self.assertIsNone(self.arena.data['lobby'])

    def test_transfer_and_free_agent_keep_identity_and_points(self):
        p=self.state.season.teams[0]['players'].pop(0)
        self.state.season.teams[1]['players'].append(p)
        self.arena.data['ladder'][p['player_id']]=dict(elo=2345,recent=[],wins=1,losses=0)
        self.arena.matchmake(self.state,self.body())
        self.assertEqual(2345,self.arena.data['lobby']['ratings'][p['player_id']])
        self.arena.cancel(self.body())
        self.state.season.teams[1]['players'].remove(p)
        self.state.career.free.append(p)
        self.arena.matchmake(self.state,self.body())
        self.assertEqual(p['player_id'],self.arena.data['lobby']['human_id'])

    def test_assignments_reach_request_and_result_without_changing_career(self):
        before=deepcopy(self.state);l=self.ready()
        for side in ('a','b'):self.assertEqual(set(PLAYABLE_ROLES),{l['roster'][pid]['role'] for pid in l[side]})
        self.assertEqual(before,self.state)
        self.assertEqual(l,Arena(self.arena.path).data['lobby'])
        with patch.object(launch,'require_cs2_closed'),patch.object(launch,'start_match',return_value={'msg':'test'}):
            self.arena.launch(self.state,self.body())
        req=l['request'];bots=req['ct']['players']+req['t']['players']
        self.assertEqual(9,len(bots));self.assertEqual(self.ids[0],req['human_player_id'])
        for bot in bots:
            p=l['roster'][bot['player_id']]
            self.assertEqual(p['role'],bot['role']);self.assertAlmostEqual(playing_ability(p),bot['overall'])
        self.arena.ingest(self.body(),result_for(l))
        l=self.arena.data['lobby']
        for rows in l['result']['map']['players'].values():
            for p in rows:self.assertEqual(l['roster'][p['player_id']]['role'],p['role'])
        self.assertEqual(before,self.state)

    def test_old_pending_identity_can_import_but_not_relaunch(self):
        l=self.ready()
        with patch.object(launch,'require_cs2_closed'),patch.object(launch,'start_match',return_value={'msg':'test'}):self.arena.launch(self.state,self.body())
        l['phase']='starting';self.arena.save();before=deepcopy(self.arena.data)
        self.state.career.you_card=deepcopy(self.state.season.teams[1]['players'][0])
        self.assertIn('identity_error',self.arena.public(self.state)['lobby'])
        for action in ('pick','advance','launch'):
            with self.assertRaisesRegex(ValueError,'房间角色'):self.arena.guard_rank_action(self.state,action)
        with patch.object(launch,'start_match') as start:
            with self.assertRaisesRegex(ValueError,'房间角色'):self.arena.launch(self.state,self.body())
            start.assert_not_called()
        self.assertEqual(before,self.arena.data)
        self.arena.guard_rank_action(self.state,'ingest');self.arena.ingest(self.body(),result_for(l))
        self.assertEqual(before['lobby']['human_id'],self.arena.data['lobby']['result']['human_id'])

    def test_legacy_ready_upgraded_but_existing_nonce_roster_is_not(self):
        l=self.ready();l.pop('role_assignment_version')
        for p in l['roster'].values():p['role']='awp'
        with patch.object(launch,'require_cs2_closed'),patch.object(launch,'start_match',return_value={'msg':'test'}):self.arena.launch(self.state,self.body())
        self.assertEqual(1,l['role_assignment_version'])
        l['phase']='starting';l.pop('role_assignment_version');old=deepcopy(l['roster']);nonce=l['nonce']
        with patch.object(launch,'require_cs2_closed'),patch.object(launch,'start_match',return_value={'msg':'test'}):self.arena.launch(self.state,self.body())
        self.assertEqual(old,l['roster']);self.assertEqual(nonce,l['nonce'])
        self.assertNotIn('role_assignment_version',l)

    def test_custom_multiple_snipers_get_one_of_each_role_on_copies(self):
        for team in self.state.season.teams:
            for p in team['players']:p['role']='awp'
        before=deepcopy(self.state)
        self.arena.create(self.state,self.body(mode='custom',players=self.ids,human_id=self.ids[1]))
        l=self.arena.data['lobby']
        self.assertEqual(1,l['role_assignment_version'])
        self.assertEqual(self.ids[:5],l['a']);self.assertEqual(self.ids[5:],l['b'])
        self.assertEqual(self.ids[1],l['human_id'])
        for side in ('a','b'):
            roles=[l['roster'][pid]['role'] for pid in l[side]]
            self.assertEqual(set(PLAYABLE_ROLES),set(roles));self.assertEqual(1,roles.count('awp'))
        self.assertEqual(before,self.state)
        self.assertEqual(l,Arena(self.arena.path).data['lobby'])
        self.arena.configure(self.body(map='dust2',ct='b',human_id=''))
        assigned=deepcopy(l['roster'])
        with patch.object(launch,'require_cs2_closed'),patch.object(launch,'start_match',return_value={'msg':'test'}):
            self.arena.launch(self.state,self.body())
        self.assertTrue(l['request']['observer'])
        for side in ('ct','t'):
            bots=l['request'][side]['players']
            self.assertEqual(5,len(bots));self.assertEqual(set(PLAYABLE_ROLES),{p['role'] for p in bots})
            for bot in bots:self.assertEqual(assigned[bot['player_id']]['role'],bot['role'])
        self.assertEqual(before,self.state)

    def test_old_custom_ready_upgrades_but_starting_and_launched_snapshots_do_not(self):
        self.arena.create(self.state,self.body(mode='custom',players=self.ids,human_id=''))
        l=self.arena.data['lobby'];l.pop('role_assignment_version')
        for p in l['roster'].values():p['role']='awp'
        with patch.object(launch,'require_cs2_closed'),patch.object(launch,'start_match',return_value={'msg':'test'}):
            self.arena.launch(self.state,self.body())
        self.assertEqual(1,l['role_assignment_version'])
        for side in ('a','b'):
            self.assertEqual(set(PLAYABLE_ROLES),{l['roster'][pid]['role'] for pid in l[side]})
        # Legacy pending rooms may legitimately contain duplicate jobs. Their
        # original role/ability and nonce must survive a retry, not be upgraded.
        l['phase']='starting';l.pop('role_assignment_version')
        for p in l['roster'].values():p['role']='awp'
        old=deepcopy(l['roster']);nonce=l['nonce']
        with patch.object(launch,'require_cs2_closed'),patch.object(launch,'start_match',return_value={'msg':'test'}),\
             patch('cs2career.arena.assign_lobby_positions') as assign:
            self.arena.launch(self.state,self.body());assign.assert_not_called()
        self.assertEqual(old,l['roster']);self.assertEqual(nonce,l['nonce'])
        self.assertNotIn('role_assignment_version',l)
        self.assertTrue(all(p['role']=='awp' for side in ('ct','t') for p in l['request'][side]['players']))
        saved=deepcopy(self.arena.data)
        with patch('cs2career.arena.assign_lobby_positions') as assign:
            with self.assertRaisesRegex(ValueError,'待开赛'):self.arena.launch(self.state,self.body())
            assign.assert_not_called()
        self.assertEqual(saved,self.arena.data)

    def test_http_rejects_forged_identity_and_mismatched_room(self):
        self.state.arena=self.arena;server=create_server(self.state);server.game_disabled=True
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        def post(action,body):
            req=Request(f'http://127.0.0.1:{server.server_port}/api/arena/{action}',data=json.dumps(body).encode(),
                        headers={'Content-Type':'application/json','X-Career-Token':server.token})
            with urlopen(req,timeout=10) as r:return json.load(r)
        try:
            with self.assertRaises(HTTPError) as err:post('matchmake',self.body(human_id=self.ids[1]))
            self.assertEqual(400,err.exception.code);self.assertIsNone(self.arena.data['lobby'])
            self.assertTrue(post('matchmake',self.body())['ok'])
            before=deepcopy(self.arena.data);self.state.career.you_card['player_id']=self.ids[1]
            with self.assertRaises(HTTPError) as err:post('advance',self.body())
            self.assertEqual(400,err.exception.code);self.assertEqual(before,self.arena.data)
            # Cancel is disallowed globally in NO_GAME previews because it may
            # inspect a real process for an already-launched room. Here the
            # room is only a draft: exercise the identity exception directly.
            self.arena.guard_rank_action(self.state,'cancel');self.arena.cancel(self.body())
            self.assertIsNone(self.arena.data['lobby'])
        finally:server.shutdown();worker.join();server.server_close()
