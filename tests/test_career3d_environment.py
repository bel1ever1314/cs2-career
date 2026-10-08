from application_double import ApplicationDouble
"""Purchases, decor and crash recovery run on temporary saves only."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from tools import career3d_environment as env


class Career(SimpleNamespace):
    def my_team(self, teams):
        return next((t for t in teams if t['id'] == self.team_id), None)

    def _record_cashflow(self, *args):
        self.cashflow.append(args)


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='c2c-environment-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.addCleanup(patch.stopall)
        patch.object(env, 'save_root', return_value=self.root).start()
        self.state = ApplicationDouble(
            career=Career(incident_state={'career3d_service': {'revision': 7}},
                money=10000, team_id='a', mode='join', exists=True, retired=False,
                banned=False, unsigned=False, training_session=None, cashflow=[]),
            season=SimpleNamespace(teams=[dict(id='a', name='Local Club', money=900000)],
                events=[], history=[], date='2026-10-03'), arena=SimpleNamespace(pending=None))
        self.state.persist = self.persist
        from cs2career.operations import operation
        self.state.operation = lambda: operation(self.state)
        self.persist()

    def persist(self):
        for name, obj in [('season.json', self.state.season), ('career.json', self.state.career)]:
            data = {k:v for k,v in vars(obj).items() if k != 'career'}
            from cs2career.storage.transaction import save
            save(self.root/name, lambda data=data: json.dumps(data).encode('utf-8'))

    def body(self, request_id='op', **kw):
        return dict(request_id=request_id,
            revision=self.state.career.incident_state['career3d_service']['revision'], **kw)

    def buy(self, item, request_id='buy'):
        row = next(r for r in env.catalog()['home_catalog'] if r['id'] == item)
        return env.environment_command(self.state, 'home-buy', self.body(request_id, item=item, price=row['price']))

    def test_read_is_pure_and_vitality_is_elite(self):
        before=deepcopy((vars(self.state.career), vars(self.state.season)))
        self.assertEqual('standard', env.environment_context(self.state)['club']['tier'])
        self.assertEqual(before, (vars(self.state.career), vars(self.state.season)))
        self.state.season.teams[0]['name']='Vitality'
        self.assertEqual('elite', env.environment_context(self.state)['club']['tier'])
        self.state.season.teams[0]['name']='Young Academy'
        self.assertEqual('academy', env.environment_context(self.state)['club']['tier'])

    def test_club_account_pays_once_and_stale_quote_rejected(self):
        body=self.body(team_id='a', facility='training', level=2, price=18000)
        env.environment_command(self.state, 'facility', body)
        self.assertEqual(882000, self.state.season.teams[0]['money'])
        self.assertEqual(10000, self.state.career.money)
        self.assertTrue(env.environment_command(self.state,'facility',body)['replayed'])
        self.assertEqual(882000, self.state.season.teams[0]['money'])
        self.assertEqual(2, env.environment_context(self.state)['club']['facilities']['training'])
        with self.assertRaises(ValueError):
            env.environment_command(self.state,'facility',self.body('second',team_id='a',facility='training',level=2,price=18000))
        with self.assertRaises(ValueError):
            env.environment_command(self.state,'facility',dict(body,facility='kitchen'))
        self.assertFalse((self.root/env.JOURNAL).exists())

    def test_tier_upgrade_checks_current_team_and_only_next_tier(self):
        with self.assertRaises(ValueError):
            env.environment_command(self.state,'club-tier',self.body(team_id='wrong',tier='elite',price=650000))
        env.environment_command(self.state,'club-tier',self.body(team_id='a',tier='elite',price=650000))
        self.assertEqual('elite',env.environment_context(self.state)['club']['tier'])
        self.assertEqual(250000,self.state.season.teams[0]['money'])

    def test_home_layout_stock_rotation_palette_and_paths(self):
        self.assertEqual([],env.validate_layout([], env._home(self.state)))
        self.buy('plant')
        row=dict(id='plant1',item='plant',x=2.75,z=-.5,rotation=90,color='7b9d70')
        env.environment_command(self.state,'home-layout',self.body('layout',placed=[row]))
        home=env.environment_context(self.state)['home']
        self.assertEqual([row],home['placed'])
        self.assertEqual(9650,self.state.career.money)
        self.assertEqual(900000,self.state.season.teams[0]['money'])
        for invalid in ([dict(row,x=3.5)],[dict(row,x=-2,z=-.75)],
                        [dict(row,rotation=45)],[dict(row,color='nope')],
                        [row,dict(row,id='plant2')],[dict(row,x=float('nan'))]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                env.validate_layout(invalid,home)
        self.buy('wall_sage','wall')
        env.environment_command(self.state,'home-finish',self.body('finish',item='wall_sage'))
        self.assertEqual('sage',env._home(self.state)['wallpaper'])
        self.assertEqual(9250,self.state.career.money)

    def test_current_matches_block_purchases(self):
        self.state.arena.pending={'id':'playing'}
        with self.assertRaises(ValueError): self.buy('plant')
        self.assertEqual(10000,self.state.career.money)

    def test_capsule_clearance_rejects_a_wall_across_the_workstation_route(self):
        home=env._home(self.state)
        home['owned'] += ['bookshelf']*4
        rows=[dict(id=f'barrier{i}',item='bookshelf',x=x,z=0,rotation=0,color='caa078')
              for i,x in enumerate([-.5,.5,1.5,2.5])]
        with self.assertRaisesRegex(ValueError,'挡住通路'):
            env.validate_layout(rows,home)
        self.assertEqual([],env.validate_layout([],env._home(self.state)))

    def test_removed_authored_furniture_frees_floor_without_changing_inventory(self):
        self.buy('plant')
        home=env._home(self.state)
        before=deepcopy(home)
        # Former fixed coffee table, beanbag and entry cabinet footprints.
        for x,z in [(0,1),(1.75,.75),(2.75,2.25)]:
            row=dict(id='plant',item='plant',x=x,z=z,rotation=0,color='7b9d70')
            self.assertEqual([row],env.validate_layout([row],home))
        self.assertEqual(before,home)
        self.assertEqual(4,len(env.environment_context(self.state)['home']['fixed']))

    def test_pack_away_and_restore_keep_stock_and_survive_reload(self):
        self.buy('sofa')
        row=dict(id='sofa-1',item='sofa',x=1,z=.75,rotation=90,color='bfaa95')
        env.environment_command(self.state,'home-layout',self.body('place-sofa',placed=[row]))
        owned=env._home(self.state)['owned'][:]
        balance=self.state.career.money
        body=self.body('pack-away',placed=[])
        env.environment_command(self.state,'home-layout',body)
        self.assertTrue(env.environment_command(self.state,'home-layout',body)['replayed'])
        saved=json.loads((self.root/'career.json').read_text('utf-8'))
        self.state.career.incident_state=saved['incident_state']
        self.assertEqual([],env._home(self.state)['placed'])
        self.assertEqual(owned,env._home(self.state)['owned'])
        self.assertEqual(balance,self.state.career.money)
        env.environment_command(self.state,'home-layout',self.body('restore-sofa',placed=[row]))
        self.assertEqual([row],env._home(self.state)['placed'])

    def test_facility_level_rejects_float_or_stale_revision(self):
        for body in (self.body(team_id='a',facility='training',level=2.0,price=18000),
                     dict(self.body(team_id='a',facility='training',level=2,price=18000),revision=6)):
            with self.assertRaises(ValueError): env.environment_command(self.state,'facility',body)
        self.assertEqual(900000,self.state.season.teams[0]['money'])

    def test_failed_pair_save_restores_both_files_and_memory(self):
        old_files={n:(self.root/n).read_bytes() for n in env.NAMES}
        old_money=self.state.career.money
        def fail():
            from cs2career.storage.transaction import save
            save(self.root/'season.json', lambda: b'partial write')
            raise OSError('fixture disk failure')
        self.state.persist=fail
        with self.assertRaises(OSError): self.buy('plant')
        self.assertEqual(old_money,self.state.career.money)
        self.assertNotIn(env.STORE,self.state.career.incident_state)
        self.assertEqual(old_files,{n:(self.root/n).read_bytes() for n in env.NAMES})
        self.assertFalse((self.root/env.JOURNAL).exists())

    def test_restart_rolls_back_prepared_but_keeps_committed_files(self):
        old=(self.root/'career.json').read_bytes()
        env._begin_journal(self.root)
        (self.root/'career.json').write_bytes(b'partial')
        env.recover_environment(self.root)
        self.assertEqual(old,(self.root/'career.json').read_bytes())
        env._begin_journal(self.root)
        journal=json.loads((self.root/env.JOURNAL).read_text('utf-8'))
        journal['phase']='committed'
        (self.root/env.JOURNAL).write_text(json.dumps(journal),encoding='utf-8')
        (self.root/'career.json').write_bytes(b'committed')
        env.recover_environment(self.root)
        self.assertEqual(b'committed',(self.root/'career.json').read_bytes())

    def http(self):
        from tools import career3d_service as service
        from cs2career.web.server import create_server
        def context(state, hour):
            return dict(environment=env.environment_context(state),
                calendar={'revision':state.career.incident_state['career3d_service']['revision']})
        patch.object(service,'read_context',side_effect=context).start()
        server=create_server(self.state)
        server.RequestHandlerClass=service.handler_class()
        server.display_hour=8
        worker=threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        def close():
            server.shutdown();worker.join(5);server.server_close()
        self.addCleanup(close)
        def request(path, body=None, auth=True):
            headers={'X-Career-Token':server.token} if auth else {}
            raw=None
            if body is not None:
                headers['Content-Type']='application/json'
                raw=json.dumps(body).encode()
            req=Request(f'http://127.0.0.1:{server.server_port}'+path,data=raw,headers=headers)
            try:
                with urlopen(req,timeout=5) as response:
                    return response.status,json.load(response)
            except HTTPError as response:
                return response.code,json.load(response)
        return request

    def test_authenticated_http_purchase_replay_and_english_projection(self):
        request=self.http()
        code,_=request('/api/3d/environment',auth=False)
        self.assertEqual(403,code)
        code,context=request('/api/3d/environment')
        self.assertEqual(200,code)
        self.assertEqual('standard',context['environment']['club']['tier'])
        payload=self.body(item='plant',price=350)
        code,response=request('/api/3d/environment/home-buy',payload)
        self.assertEqual(200,code,response)
        self.assertTrue(response['ok'])
        self.assertEqual(8,response['context']['calendar']['revision'])
        self.assertEqual(9650,response['context']['environment']['home']['balance'])
        self.assertIn('reason_en',response)
        code,response=request('/api/3d/environment/home-buy',payload)
        self.assertEqual(200,code,response)
        self.assertTrue(response['replayed'])
        self.assertEqual(9650,self.state.career.money)
        code,response=request('/api/3d/environment/home-buy',dict(payload,request_id='stale'))
        self.assertEqual(400,code,response)
        self.assertEqual(9650,self.state.career.money)


if __name__ == '__main__': unittest.main()
