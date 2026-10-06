from application_double import ApplicationDouble
"""Season board reads and mode choices must not advance on refresh/retry."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cs2career.career.season_board import public
from cs2career.web.server import create_server


class SeasonBoardTests(TestCase):
    def test_quick_unread_badge_excludes_retained_monthly_mail_without_mutating_it(self):
        from cs2career.career.career import Career
        c=SimpleNamespace(assist={'quick_mode': True}, inbox=[
            {'id':'monthly', 'publication_key':'monthly:2026-01', 'read':False},
            {'id':'champion', 'publication_key':'champion:2026-major', 'read':False},
            {'id':'invite', 'read':False}])
        before=deepcopy(c.inbox)
        self.assertEqual(2,Career.unread_count(c))
        self.assertEqual(before,c.inbox)
        c.assist['quick_mode']=False
        self.assertEqual(3,Career.unread_count(c))

    def test_calendar_includes_unentered_events_but_no_invented_fixtures(self):
        career=SimpleNamespace(exists=True, team_id='mine', registered=['future'], inbox=[],
            incident_state={}, my_team=lambda _: {'name':'New club'})
        match=dict(id='past1', date='2026-02-01', stage='QF', team_a='New club', team_b='Other',
                   played=True, human=False, winner='New club', series='2-0')
        season=SimpleNamespace(year=2026, date='2026-03-01', teams=[], events=[
            dict(id='past',name='Past Cup',type='t2',status='done',dates=['2026-02-01'],matches=[match]),
            dict(id='future',name='Future Cup',type='t1',status='upcoming',dates=['2026-08-01'],matches=[]),
            dict(id='not-ours',name='Another Cup',type='t1',status='upcoming',dates=['2026-09-01'],matches=[])])
        before=deepcopy(season.events)
        result=public(career,season)
        self.assertEqual(['past','future','not-ours'],[r['id'] for r in result['events']])
        self.assertEqual('entered',result['events'][1]['participation'])
        self.assertEqual('unknown',result['events'][2]['participation'])
        self.assertEqual([],result['events'][0]['own_matches'])
        self.assertEqual([],result['events'][1]['own_matches'])
        self.assertEqual(0,result['summary']['matches_played'])
        self.assertEqual(before,season.events)
        career.incident_state={'arcs':{'series':[
            {'key':'older','date':'2025-12-31','win':True,'team_id':'old'},
            {'key':'first','date':'2026-02-01','win':False,'team_id':'old'},
            {'key':'second','date':'2026-03-01','win':True,'team_id':'new'}]}}
        result=public(career,season)
        self.assertEqual([False,True],[r['won'] for r in result['series_results']])
        self.assertEqual(['first','second'],[r['id'] for r in result['series_results']])


class SeasonModeHttpTests(TestCase):
    def setUp(self):
        self.career=SimpleNamespace(assist={})
        self.state=ApplicationDouble(career=self.career,season=SimpleNamespace(year=2026),
            persist=Mock(),payload=lambda msg='':{'ok':True,'msg':msg,'state':{}})
        self.server=create_server(self.state)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.configure_patch=patch('cs2career.career.fast_mode.configure_season',return_value={'year':2027})
        self.configure=self.configure_patch.start()
        self.addCleanup(self.configure_patch.stop)

    def tearDown(self):
        self.server.shutdown();self.thread.join();self.server.server_close()

    def request(self,body,authenticated=True):
        req=Request(f'http://127.0.0.1:{self.server.server_port}/api/assist/season-mode',
            data=json.dumps(body).encode(),headers={'Content-Type':'application/json',
            'X-Career-Token':self.server.token if authenticated else 'wrong'})
        try:
            with urlopen(req,timeout=5) as response:return response.status,json.load(response)
        except HTTPError as error:return error.code,json.load(error)

    def test_replayed_year_end_choice_is_idempotent(self):
        body={'quick_mode':True,'year':2026,'token':'season-choice-0001'}
        status,result=self.request(body)
        self.assertEqual(200,status);self.assertIsInstance(result['msg'],str)
        self.assertEqual(200,self.request(body)[0])
        self.configure.assert_called_once_with(self.career,self.state.season,True,2026)
        self.state.persist.assert_called_once()
        self.assertEqual(400,self.request({**body,'quick_mode':False})[0])
        self.state.persist.assert_called_once()

    def test_bad_or_rejected_inputs_have_no_automatic_side_effect(self):
        valid={'quick_mode':True,'year':2026,'token':'season-choice-0002'}
        self.assertEqual(403,self.request(valid,False)[0])
        for body in ({**valid,'quick_mode':'true'},{**valid,'year':True},{**valid,'token':''}):
            self.assertEqual(400,self.request(body)[0])
        self.configure.assert_not_called();self.state.persist.assert_not_called()
        self.configure.side_effect=ValueError('只能在赛季开始或结束时切换模式。')
        self.assertEqual(400,self.request(valid)[0])
        self.state.persist.assert_not_called()
        self.assertNotIn('last_season_choice',self.career.assist)
