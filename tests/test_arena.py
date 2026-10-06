from application_double import ApplicationDouble
"""Local ladders and spectator hand-off: isolated data, never a live game."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from cs2career.arena import Arena, PICK_ORDER
from cs2career.arena_rules import initial_score, level
from cs2career.cs2 import launch
from cs2career.cs2.profiles import active_manifest, generate_match_vpk, expected_bot_count, read_db, PROFILE_RE
from cs2career.web.server import create_server
from test_v15_core import fake_team


def fixture_state():
    teams=[fake_team('A',80),fake_team('B',88),fake_team('C',95)]
    for i,p in enumerate(p for t in teams for p in t['players']):p['ability']=60+i*2
    return ApplicationDouble(season=SimpleNamespace(teams=teams,events=[],date='2026-01-01'),
                          career=SimpleNamespace(exists=True,you_card=deepcopy(teams[0]['players'][0]),
                                                 free=[],money=123,training_session=None))


def result_for(lobby):
    return dict(schema_version=2,status='finished',complete=True,request_nonce=lobby['nonce'],
        map='de_'+lobby['map'],ended_at='2099-01-01T10:00:00Z',ct_score=13,t_score=6,
        identity_bindings={str(i):pid for i,pid in enumerate(lobby['selection'])},
        players=[dict(player_id=pid,name=p['name'],team='ct' if pid in lobby[lobby['ct']] else 't',
            kills=10,deaths=10,assists=3,damage=1000,kast=.7,survived_rounds=9,
            opening_kills=1,opening_deaths=1) for pid,p in lobby['roster'].items()])


class ArenaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.arena=Arena(self.root/'arena.json');self.state=fixture_state()
        self.ids=list(self.arena.roster(self.state))[:10]

    def body(self,**kw):return dict(revision=self.arena.data['revision'],**kw)

    def ready(self,mode='rank'):
        if mode=='custom':self.arena.create(self.state,self.body(mode=mode,players=self.ids))
        else:self.arena.matchmake(self.state,self.body(human_id=self.ids[0]))
        self.finish_draft()
        return self.arena.data['lobby']

    def finish_draft(self):
        while self.arena.data['lobby']['phase'] in ('draft','veto','side'):
            l=self.arena.data['lobby']
            if not self.arena.turn(l)['human']:self.arena.advance(self.body())
            elif l['phase']=='draft':
                pid=next(p for p in l['selection'] if p not in l['a']+l['b'])
                self.arena.pick(self.body(player_id=pid))
            elif l['phase']=='veto':self.arena.ban(self.body(map=next(m for m in l['map_pool'] if m not in [b['map'] for b in l['bans']])))
            else:self.arena.choose_side(self.body(side='ct'))

    def launched(self,mode='rank'):
        l=self.ready(mode)
        with patch.object(launch,'require_cs2_closed'),patch.object(launch,'start_match',return_value={'msg':'launched'}) as start:
            self.arena.launch(self.state,self.body())
            self.assertEqual('arena',start.call_args.kwargs['purpose'])
            self.assertNotIn('career',start.call_args.kwargs)
        return l

    def test_ten_distinct_snapshots_and_captain_snake_picks(self):
        before=deepcopy(self.state)
        l=self.ready()
        self.assertEqual(sorted(l['selection'],key=lambda p:(-l['ratings'][p],p))[:2],l['captains'])
        self.assertEqual(list(PICK_ORDER),[p['side'] for p in l['picks']])
        self.assertEqual(5,len(l['a']));self.assertEqual(5,len(l['b']))
        self.assertFalse(set(l['a'])&set(l['b']))
        self.state.season.teams[0]['players'][0]['name']='new name'
        self.assertEqual('A0',l['roster'][self.ids[0]]['name'])
        self.assertEqual(before.career,self.state.career)
        with self.assertRaises(ValueError):self.arena.pick(self.body(player_id=self.ids[0]))

    def test_invalid_and_stale_writes_do_not_change_store(self):
        for ids in (self.ids[:9],self.ids[:9]+self.ids[:1],self.ids[:9]+['missing']):
            with self.assertRaises(ValueError):self.arena.create(self.state,self.body(mode='rank',players=ids))
        self.assertIsNone(self.arena.data['lobby'])
        self.ready('custom');before=deepcopy(self.arena.data)
        with self.assertRaises(ValueError):self.arena.configure(dict(revision=0,map='dust2',ct='a'))
        with self.assertRaises(ValueError):self.arena.configure(self.body(map='dust2',ct='b',human_id='missing'))
        self.assertEqual(before,self.arena.data)

    def test_captains_use_lobby_elo_not_rating_or_ability(self):
        row=dict(rounds=20,k=30,d=5,a=8,damage=3000,kast=.95)
        self.arena.data['ladder'][self.ids[0]]=dict(elo=1000,recent=[row]*10,wins=0,losses=0)
        l=self.ready();self.assertNotIn(self.ids[0],l['captains'])
        self.arena.cancel(self.body())
        self.arena.data['ladder'][self.ids[0]]['elo']=6000
        l=self.ready();self.assertEqual(self.ids[0],l['captains'][0])

    def test_unified_ladder_custom_unrated_reload_exactly_once(self):
        before=deepcopy(self.state)
        for mode in ('rank','fpl','custom'):
            l=self.launched(mode);raw=result_for(l)
            ladder_before=deepcopy(self.arena.data['ladder'])
            self.arena.ingest(self.body(),raw)
            scored=deepcopy(self.arena.data)
            self.arena.ingest(self.body(),raw)
            self.assertEqual(scored,self.arena.data)
            self.arena=Arena(self.arena.path)
            self.assertEqual(scored,self.arena.data)
            if mode=='custom':self.assertEqual(ladder_before,self.arena.data['ladder'])
            else:
                ladder=self.arena.data['ladder']
                self.assertEqual(sum(p['elo'] for p in ladder_before.values()),sum(p['elo'] for p in ladder.values()))
                self.assertEqual(5+sum(p['wins'] for p in ladder_before.values()),sum(p['wins'] for p in ladder.values()))
            self.arena.cancel(self.body())
        self.assertEqual(before,self.state)
        self.assertEqual(3,len(self.arena.data['matches']))

    def test_rejects_wrong_nonce_map_identity_and_team(self):
        l=self.launched();valid=result_for(l);before=deepcopy(self.arena.data)
        variants=[dict(valid,request_nonce='wrong'),dict(valid,map='de_unknown'),dict(valid,complete=False),dict(valid,players=valid['players'][:9])]
        swapped=deepcopy(valid)
        # Matchmaking shuffles IDs: rows 0 and 5 need not be opponents.
        ct=next(p for p in swapped['players'] if p['team']=='ct')
        terrorist=next(p for p in swapped['players'] if p['team']=='t')
        ct['team'],terrorist['team']='t','ct'
        variants.append(swapped)
        for raw in variants:
            with self.assertRaises(ValueError):self.arena.ingest(self.body(),raw)
            self.assertEqual(before,self.arena.data)

    def test_opening_ct_team_b_scores_b_as_winner_not_human_side(self):
        self.ready('custom');self.arena.configure(self.body(map='mirage',ct='b',human_id=self.ids[2]))
        with patch.object(launch,'require_cs2_closed'),patch.object(launch,'start_match',return_value={'msg':'ok'}) as start:
            self.arena.launch(self.state,self.body())
            request=start.call_args.kwargs['request_override']
            self.assertEqual(9,expected_bot_count(request));self.assertEqual('t',request['human_team'])
        self.arena.ingest(self.body(),result_for(self.arena.data['lobby']))
        self.assertEqual('Team B',self.arena.data['lobby']['result']['map']['winner'])
        self.assertEqual('6-13',self.arena.data['lobby']['result']['map']['score'])

    def test_launcher_failure_retains_nonce_for_recovery_without_scoring(self):
        self.ready()
        with patch.object(launch,'require_cs2_closed'),patch.object(launch,'start_match',side_effect=OSError('locked')):
            with self.assertRaises(OSError):self.arena.launch(self.state,self.body())
        self.assertEqual('starting',self.arena.data['lobby']['phase'])
        nonce=self.arena.data['lobby']['nonce']
        with patch.object(launch,'require_cs2_closed'),patch.object(launch,'start_match',return_value={'msg':'ok'}):self.arena.launch(self.state,self.body())
        self.assertEqual(nonce,self.arena.data['lobby']['nonce'])
        self.assertFalse(self.arena.data['matches'])
        with self.assertRaises(ValueError):self.arena.create(self.state,self.body(mode='custom',players=self.ids))

    def test_pending_career_or_running_game_cannot_be_overwritten(self):
        self.ready();before=deepcopy(self.arena.data)
        self.state.season.events=[{'matches':[{'cs2_session':{'nonce':'official'},'played':False}]}]
        with patch.object(launch,'start_match') as start:
            with self.assertRaises(ValueError):self.arena.launch(self.state,self.body())
            start.assert_not_called()
        self.assertEqual(before,self.arena.data)
        self.state.season.events=[]
        with patch.object(launch,'require_cs2_closed',side_effect=ValueError('退出 CS2')):
            with self.assertRaises(ValueError):self.arena.launch(self.state,self.body())
        self.assertEqual(before,self.arena.data)

    def test_save_failure_rolls_back_memory_as_well_as_disk(self):
        self.ready('custom');before=deepcopy(self.arena.data)
        with patch('cs2career.storage.transaction._durable_write',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.arena.configure(self.body(map='nuke',ct='b'))
        self.assertEqual(before,self.arena.data)
        self.assertEqual(before,Arena(self.arena.path).data)

    def test_observer_ten_profiles_identities_and_safe_avatars(self):
        a,b=self.state.season.teams[:2]
        for human in ('',a['players'][0]['player_id']):
            count=10 if not human else 9
            match=launch.build_lobby_request(a,b,human,'de_dust2','observer-test')
            csgo=self.root/str(count);csgo.mkdir()
            launch.install_match_avatars(csgo,match)
            manifest=generate_match_vpk(csgo,match,'Medium',self.root/'cache')
            launch.install_match_identities(csgo,match)
            self.assertEqual(count,manifest['count']);self.assertTrue(active_manifest(csgo)['valid'])
            self.assertEqual(count,len(PROFILE_RE.findall(read_db(csgo/'overrides/career_botprofile.vpk'))))
            bots=[p for side in ('ct','t') for p in match[side]['players']]
            self.assertEqual(count,len({p['steam_id'] for p in bots}))
            self.assertEqual('observer_match_10' if not human else 'career_match_9',manifest['type'])
        match['observer']=True
        with self.assertRaises(ValueError):expected_bot_count(match)

    def test_duplicate_names_use_ids_in_result_not_nicknames(self):
        self.state.season.teams[0]['players'][1]['name']='A0'
        l=self.launched('custom');self.arena.ingest(self.body(),result_for(l))
        rows=self.arena.data['lobby']['result']['map']['players']['Team A']
        self.assertEqual(5,len(rows));self.assertEqual(2,sum(p['name']=='A0' for p in rows))

    def test_recommendation_read_only_ten_unique(self):
        before=deepcopy(self.arena.data)
        for mode in ('rank','fpl','custom'):
            ids=self.arena.recommend(self.state,mode,self.ids[0])
            self.assertEqual(10,len(set(ids)));self.assertIn(self.ids[0],ids)
        self.assertEqual(before,self.arena.data)

    def test_elo_band_random_nine_frozen_on_read_and_reload(self):
        human=self.ids[0]
        # Thirteen nearby identities, one distant superstar. Never pair the
        # superstar while a full local lobby fits inside the initial band.
        for pid in self.arena.roster(self.state):
            self.arena.data['ladder'][pid]=dict(elo=1500,wins=0,losses=0,recent=[])
        far=list(self.arena.roster(self.state))[-1]
        self.arena.data['ladder'][far]['elo']=5000
        selections=set()
        for _ in range(12):
            self.arena.matchmake(self.state,self.body(human_id=human))
            l=deepcopy(self.arena.data['lobby']);selections.add(tuple(sorted(l['selection'])))
            self.assertEqual(10,len(set(l['selection'])));self.assertIn(human,l['selection']);self.assertNotIn(far,l['selection'])
            self.assertEqual(200,l['band'])
            self.arena.public(self.state);self.assertEqual(l,Arena(self.arena.path).data['lobby'])
            with self.assertRaises(ValueError):self.arena.matchmake(self.state,self.body(human_id=human))
            self.arena.cancel(self.body())
        self.assertGreater(len(selections),1)

    def test_band_expands_and_requires_a_human_player(self):
        with self.assertRaises(ValueError):self.arena.matchmake(self.state,self.body(human_id=''))
        self.arena.data['ladder'][self.ids[0]]=dict(elo=9000,wins=0,losses=0,recent=[])
        self.arena.matchmake(self.state,self.body(human_id=self.ids[0]))
        self.assertGreater(self.arena.data['lobby']['band'],1200)
        self.assertEqual(self.ids[0],self.arena.data['lobby']['captains'][0])

    def test_draft_and_veto_enforce_turns_and_lock_ranked_configuration(self):
        self.arena.matchmake(self.state,self.body(human_id=self.ids[0]))
        l=self.arena.data['lobby']
        available=next(p for p in l['selection'] if p not in l['a']+l['b'])
        with self.assertRaises(ValueError):self.arena.pick(self.body(player_id=available))
        stale=self.body();self.arena.advance(stale)
        with self.assertRaises(ValueError):self.arena.advance(stale)
        self.finish_draft();l=self.arena.data['lobby']
        self.assertEqual(6,len(l['bans']));self.assertEqual(6,len({b['map'] for b in l['bans']}))
        self.assertEqual(['a','b']*3,[b['side'] for b in l['bans']])
        self.assertNotIn(l['map'],[b['map'] for b in l['bans']])
        with self.assertRaises(ValueError):self.arena.configure(self.body(map='dust2',ct='b',human_id=self.ids[1]))
        with self.assertRaises(ValueError):self.arena.advance(self.body())

    def test_human_captain_not_auto_picked_and_veto_survives_reload(self):
        self.arena.data['ladder'][self.ids[0]]=dict(elo=7000,wins=0,losses=0,recent=[])
        self.arena.matchmake(self.state,self.body(human_id=self.ids[0]))
        l=self.arena.data['lobby']
        with self.assertRaises(ValueError):self.arena.advance(self.body())
        self.arena.pick(self.body(player_id=next(p for p in l['selection'] if p not in l['a']+l['b'])))
        self.arena=Arena(self.arena.path)
        self.finish_draft();l=self.arena.data['lobby']
        self.assertEqual('ready',l['phase']);self.assertEqual('a',l['ct'])

    def test_player_origin_seed_saved_once_and_identity_switch_is_rejected(self):
        for origin,expected in (('street',1400),('academy',2200),('prodigy',3000)):
            arena=Arena(self.root/(origin+'.json'))
            p=self.state.season.teams[0]['players'][0]
            self.state.career.you_card=deepcopy(p);self.state.career.origin=origin
            self.assertEqual(expected,next(r['elo'] for r in arena.catalog(self.state) if r['player_id']==p['player_id']))
            arena.matchmake(self.state,dict(revision=0,human_id=p['player_id']))
            arena.cancel(dict(revision=1))
            self.state.career.origin='prodigy';p['ability']=99
            self.assertEqual(expected,next(r['elo'] for r in arena.catalog(self.state) if r['player_id']==p['player_id']))
            with self.assertRaisesRegex(ValueError,'固定使用'):
                arena.matchmake(self.state,dict(revision=2,human_id=self.ids[1]))
            arena.matchmake(self.state,dict(revision=2))
            self.assertEqual(expected,arena.data['ladder'][self.ids[0]]['elo'])

    def test_historical_seeds_match_ids_not_duplicate_names(self):
        from cs2career.world.eras import player_id
        p=dict(player_id=player_id('donk'),name='donk',ability=95,role='entry')
        self.assertEqual(5360,initial_score(p)[0])
        p['player_id']='custom_donk'
        self.assertNotEqual(5360,initial_score(p)[0])
        self.assertEqual(1400,initial_score(p,'street')[0])
        self.assertEqual([1,2,9,10],[level(x) for x in (500,501,2000,2001)])

    def test_legacy_merge_backup_history_and_pending_nonce(self):
        p=self.ids[0]
        raw=dict(schema_version=1,revision=4,ladders={
            'rank':{p:dict(elo=1032,wins=3,losses=1,recent=[])},
            'fpl':{p:dict(elo=984,wins=0,losses=1,recent=[])}},
            matches=[],lobby=dict(mode='fpl',phase='launched',nonce='keep-me',human_id=p))
        self.arena.path.write_text(json.dumps(raw),'utf-8')
        arena=Arena(self.arena.path)
        self.assertEqual(1016,arena.data['ladder'][p]['elo']);self.assertEqual(3,arena.data['ladder'][p]['wins'])
        self.assertEqual('keep-me',arena.data['lobby']['nonce'])
        self.assertEqual(raw,json.loads(arena.path.read_text('utf-8')))
        arena.save();backups=list(self.root.glob('arena.schema1-*.json'))
        self.assertEqual(1,len(backups));self.assertEqual(raw,json.loads(backups[0].read_text('utf-8')))
        self.assertEqual(arena.data,Arena(arena.path).data)

    def test_matchmaking_save_failure_preserves_previous_ladder(self):
        self.arena.save();before=deepcopy(self.arena.data)
        with patch('cs2career.storage.transaction._durable_write',side_effect=OSError('full')):
            with self.assertRaises(OSError):self.arena.matchmake(self.state,self.body(human_id=self.ids[0]))
        self.assertEqual(before,self.arena.data);self.assertEqual(before,Arena(self.arena.path).data)


class ArenaHttpTests(unittest.TestCase):
    def test_authenticated_commands_never_settle_career_and_game_disabled_blocks_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=fixture_state();state.arena=Arena(Path(tmp)/'arena.json')
            def forbidden(*args):raise AssertionError('Arena called career settlement')
            state.persist=state.payload=forbidden
            server=create_server(state);server.game_disabled=True
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            base=f'http://127.0.0.1:{server.server_port}'
            def call(path,body=None,token=True):
                req=Request(base+path,data=json.dumps(body).encode() if body is not None else None,
                    headers={'X-Career-Token':server.token if token else '','Content-Type':'application/json'})
                with urlopen(req,timeout=10) as r:return json.load(r)
            try:
                with self.assertRaises(HTTPError):call('/api/arena',token=False)
                data=call('/api/arena');ids=[p['player_id'] for p in data['catalog'][:10]]
                reply=call('/api/arena/create',dict(revision=0,mode='custom',players=ids))
                self.assertTrue(reply['ok']);self.assertNotIn('state',reply)
                with self.assertRaises(HTTPError) as err:call('/api/arena/configure',dict(revision=0,map='dust2',ct='a'))
                self.assertEqual(400,err.exception.code)
                with self.assertRaises(HTTPError) as err:call('/api/arena/launch',dict(revision=1))
                self.assertEqual(403,err.exception.code)
                self.assertEqual('ready',state.arena.data['lobby']['phase'])
            finally:server.shutdown();worker.join();server.server_close()
