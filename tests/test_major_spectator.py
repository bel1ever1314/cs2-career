"""Isolated format/reveal checks; no user season or game is advanced."""
import random
import unittest
from copy import deepcopy
from unittest.mock import patch
from types import SimpleNamespace

from cs2career.league import formats, awards
from cs2career.league.season import calendar_for, Season
from cs2career.league.spectator import reveal_series
from cs2career.engine.match import veto_maps


class MajorSpectatorTests(unittest.TestCase):
    def event(self, size=32):
        ev = next(e for e in calendar_for(2026 if size == 32 else 2024)['events'] if e['type'] == 'major')
        ev['matches'] = formats.open_event(ev, [f'Team{i}' for i in range(size)])
        return ev

    def finish(self, ev, seed):
        rng = random.Random(seed)
        for _ in range(25):
            for m in ev['matches']:
                if not m['played']:
                    m.update(played=True, winner=rng.choice([m['team_a'], m['team_b']]), series='1-0')
            if formats.is_complete(ev):
                return
            batch = formats.advance_event(ev)
            self.assertTrue(batch, 'unfinished tournament stalled')
            ev['matches'].extend(batch)
        self.fail('Major did not finish')

    def test_major_stages_advance_eight_and_reset_records(self):
        for size in (24, 32):
            for seed in range(20):
                with self.subTest(size=size, seed=seed):
                    ev = self.event(size)
                    self.assertEqual(16, len(formats.swiss_state(ev)))
                    self.assertEqual({f'Team{i}' for i in range(size-16, size)}, set(formats.swiss_state(ev)))
                    self.finish(ev, seed)
                    tables = formats.major_tables(ev)
                    self.assertEqual(2 if size == 24 else 3, len(tables))
                    for table in tables:
                        self.assertEqual(16, len(table['rows']))
                        self.assertEqual(8, sum(r['w'] == 3 for r in table['rows']))
                        self.assertEqual(8, sum(r['l'] == 3 for r in table['rows']))
                        for row in table['rows']:
                            self.assertLessEqual(row['w'] + row['l'], 5)
                            self.assertEqual(len(row['opps']), len(set(row['opps'])))
                    for i in range(1, len(tables)):
                        qualified = {r['name'] for r in tables[i-1]['rows'] if r['w'] == 3}
                        added = set(ev['major_fields'][str(i+1)]) - qualified
                        start = (len(tables)-i-1)*8
                        self.assertEqual(set(ev['field'][start:start+8]), added)
                    self.assertEqual(7, sum(m['stage'] in ('QF','SF','GF') for m in ev['matches']))
                    self.assertEqual(5, next(m['best_of'] for m in ev['matches'] if m['stage']=='GF'))
                    self.assertEqual(len(ev['matches']), len({m['id'] for m in ev['matches']}))
                    self.assertEqual(sorted(m['date'] for m in ev['matches']), [m['date'] for m in ev['matches']])
                    for m in ev['matches']:
                        if m.get('phase') == 'swiss':
                            record=m['meta']['record'].split('-')
                            self.assertEqual(3 if '2' in record else 1, m['best_of'])
                    record = awards.make_record(ev)
                    self.assertEqual(formats.major_tables(ev), formats.major_tables(record))

    def test_no_silent_major_field_truncation(self):
        ev=self.event()
        with self.assertRaises(ValueError):
            formats.open_event(ev, [f'T{i}' for i in range(31)])

    def test_final_bo5_only_t1_and_major(self):
        for kind in ('t1','major','t2','cct','qual'):
            ev={'id':'test','type':kind,'format':'single_elim','size':2,'dates':['2026-01-01']}
            self.assertEqual(5 if kind in ('t1','major') else 3, formats.open_event(ev,['A','B'])[0]['best_of'])

    def test_bo5_veto_five_unique_maps(self):
        a={'name':'A','command':70};b={'name':'B','command':70}
        with patch('cs2career.engine.match._ban_value', return_value=1), patch('cs2career.engine.match._pick_value', return_value=1):
            for size in (5,7,8):
                veto=veto_maps(a,b,[f'm{i}' for i in range(size)],5)
                self.assertEqual(5,len(set(veto['order'])))
                self.assertEqual(4,sum(s['action']=='pick' for s in veto['steps']))
                self.assertEqual(size-5,sum(s['action']=='ban' for s in veto['steps']))

    def test_real_bo5_engine_reaches_three_map_wins_and_saved_rounds(self):
        from cs2career.engine.match import play_series
        from cs2career.world import MAPS
        season = Season(2026, '2026')
        a, b = season.teams[:2]
        result = play_series(a, b, MAPS, 'GF', 5)
        self.assertEqual(3, max(map(int, result['series'].split('-'))))
        self.assertIn(len(result['maps']), (3, 4, 5))
        self.assertEqual(5, len(result['veto']['order']))
        result['id'] = 'engine-check'
        before = deepcopy(result)
        reveal = reveal_series(result)
        self.assertTrue(all(m['events_available'] for m in reveal['maps']))
        self.assertEqual(before, result)

    def test_skip_handler_persists_before_returning_reveal_and_rejects_repeat(self):
        from cs2career.web.server import Handler
        from cs2career.career import Career
        season=Season(2026,'2026'); career=Career();season.career=career
        with patch.object(career,'save'):
            career.create(dict(mode='create',era='2026',name='Viewer',org='Viewer Club',
                               origin='academy',role='rifle',region='EU'),season)
        career.story_queue=[]
        mine=career.my_team(season.teams)['name']
        opponent=next(t['name'] for t in season.teams if t['name']!=mine)
        ev=dict(id='viewer-cup',name='Viewer Cup',type='t1',format='single_elim',size=2,
                region='EU',dates=[season.date],prize=0,vrs_weight=1,status='live')
        ev['matches']=formats.open_event(ev,[mine,opponent]);season.events=[ev]
        match=ev['matches'][0];saved=[];responses=[]
        state=SimpleNamespace(season=season,persist=lambda:saved.append(deepcopy(match)),
                              payload=lambda msg:{'ok':True,'msg':msg})
        handler=SimpleNamespace(state=state,_body=lambda:{'match_id':match['id'],'reveal':True},
                                _json=lambda payload:responses.append((len(saved),payload)))
        with patch.object(career,'gate_match',return_value=''):
            Handler.post_api_series_skip(handler)
            self.assertTrue(saved[0]['played'])
            self.assertEqual(1,responses[0][0])
            self.assertTrue(responses[0][1]['reveal']['maps'])
            with self.assertRaises(ValueError):
                Handler.post_api_series_skip(handler)
        self.assertEqual(1,len(saved))

    def test_calendar_upgrade_leaves_started_events_unchanged(self):
        events=calendar_for(2026)['events']
        majors=[e for e in events if e['type']=='major']
        for i,e in enumerate(majors):
            e.update(size=16,format='swiss_playoff',status='live' if i else 'upcoming',matches=[])
        old=deepcopy(majors[1])
        season=SimpleNamespace(year=2026,events=events)
        self.assertTrue(Season.align_calendar(season))
        self.assertEqual(32,majors[0]['size'])
        self.assertEqual(old,majors[1])
        self.assertFalse(Season.align_calendar(season))

    def test_reveal_is_saved_history_and_preserves_played_maps(self):
        mp={'map':'mirage','score':'13-7','winner':'A','events':[
            {'type':'round_end','round':i+1,'winner':w} for i,w in enumerate(['a','b']*7+['a']*6)]}
        match={'id':'m','team_a':'A','team_b':'B','best_of':5,'maps':[mp,deepcopy(mp)]}
        original=deepcopy(match)
        reveal=reveal_series(match,1)
        self.assertEqual([1,0],reveal['initial'])
        self.assertEqual(1,reveal['maps'][0]['index'])
        self.assertEqual(20,len(reveal['maps'][0]['rounds']))
        self.assertEqual(original,match)
        match['maps'][1]['events'].pop()
        self.assertFalse(reveal_series(match,1)['maps'][0]['events_available'])
        self.assertEqual([],reveal_series(match,1)['maps'][0]['rounds'])


if __name__ == '__main__':
    unittest.main()
