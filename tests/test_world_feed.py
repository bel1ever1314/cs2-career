"""World feed shown on the progression page while no player match is due."""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cs2career.services import world_feed as feed


def match(mid, a, b, series, day, played=True):
    sa, sb = (int(x) for x in series.split('-'))
    return dict(id=mid, team_a=a, team_b=b, series=series, date=day, played=played, stage='GS',
                winner=(a if sa > sb else b) if played else None)


class FakeVrs:
    def __init__(self, ranks):
        self.ranks = ranks

    def table(self, teams, date):
        return [dict(name=name, rank=rank) for name, rank in self.ranks.items()]


def state(events, ranks, today='2026-07-21', mine='Vitality', registered=()):
    season = SimpleNamespace(date=today, events=events, history=[], teams=[], vrs=FakeVrs(ranks),
                             your_team_name=lambda: mine)
    career = SimpleNamespace(exists=True, registered=list(registered))
    return SimpleNamespace(season=season, career=career)


RANKS = {'Vitality': 1, 'Spirit': 2, 'G2': 3, 'FURIA': 9, 'MOUZ': 6, 'Lynn Vision': 31,
         'Natus Vincere': 5, 'Aurora': 11, 'Falcons': 7, 'Liquid': 14}


class WorldFeedTest(unittest.TestCase):
    def setUp(self):
        self.cup = dict(id='cup', name='Cup', type='t1', matches=[
            match('c1', 'Vitality', 'Spirit', '0-0', '2026-07-25', played=False),
            match('c2', 'Falcons', 'MOUZ', '0-2', '2026-07-20'),
            match('c3', 'Vitality', 'G2', '2-1', '2026-07-20'),
        ])
        self.open = dict(id='open', name='Open', type='t2', matches=[
            match('o1', 'Spirit', 'FURIA', '2-1', '2026-07-20'),
            match('o2', 'Lynn Vision', 'Natus Vincere', '2-0', '2026-07-20'),
            match('o3', 'Aurora', 'Liquid', '2-1', '2026-07-20'),
            match('o4', 'G2', 'BYE', '1-0', '2026-07-20'),
            match('o5', 'G2', 'Aurora', '2-0', '2026-07-18'),
            match('o6', 'G2', 'Liquid', '2-0', '2026-07-01'),
        ])
        self.state = state([self.cup, self.open], RANKS)
        fixture = patch('cs2career.services.match_queries.player_matches',
                        return_value=[(self.cup, self.cup['matches'][0])])
        news = patch('cs2career.services.business.news_rows', return_value=[])
        self.addCleanup(fixture.stop)
        self.addCleanup(news.stop)
        fixture.start()
        self.news = news.start()

    def test_latest_day_other_teams_ranked_by_relevance(self):
        out = feed.world_feed(self.state)
        self.assertEqual(out['results_date'], '2026-07-20')
        ids = [row['id'] for row in out['results']]
        self.assertNotIn('c3', ids, 'player team match is not world news')
        self.assertNotIn('o4', ids, 'BYE is not a result')
        self.assertNotIn('o5', ids, 'only the latest result day is listed')
        self.assertEqual(ids[:3], ['o1', 'c2', 'o2'])
        first = out['results'][0]
        self.assertEqual((first['tag'], first['series'], first['winner'], first['rank_a'], first['rank_b']),
                         ('opponent', [2, 1], 'Spirit', 2, 9))
        self.assertEqual(out['results'][1]['tag'], 'event')
        self.assertTrue(out['results'][2]['upset'])
        self.assertEqual(out['results'][2]['tag'], 'upset')
        self.assertLessEqual(len(out['results']), feed.RESULT_LIMIT)

    def test_old_results_fall_out_of_window(self):
        self.state.season.date = '2026-08-30'
        out = feed.world_feed(self.state)
        self.assertEqual((out['results_date'], out['results']), ('', []))

    def test_headlines_keep_major_champions_and_recent_news(self):
        self.state.season.history = [dict(id='major', type='major'), dict(id='small', type='cct')]
        self.news.return_value = [
            dict(id='a1', date='2026-07-19', title='Major · 赛事荣誉记录', category='awards', event='Major',
                 event_id='2026::major', champion='Spirit', mvp=dict(player='donk')),
            dict(id='a2', date='2026-07-20', title='Small · 赛事荣誉记录', category='awards', event='Small',
                 event_id='2026::small', champion='Aurora', mvp={}),
            dict(id='n1', date='2026-07-18', title='G2 官宣新阵容', title_en='G2 announce', category='transfer'),
            dict(id='n0', date='2026-06-01', title='旧闻', category='news'),
        ]
        out = feed.world_feed(self.state)
        self.assertEqual([row['id'] for row in out['news']], ['a1', 'n1'])
        self.assertEqual((out['news'][0]['kind'], out['news'][0]['champion'], out['news'][0]['mvp']), ('champion', 'Spirit', 'donk'))
        self.assertEqual((out['news'][1]['kind'], out['news'][1]['title_en']), ('news', 'G2 announce'))

    def test_no_career_is_empty(self):
        self.state.career.exists = False
        self.assertEqual(feed.world_feed(self.state), dict(date='2026-07-21', results_date='', results=[], news=[]))


class WorldFeedSeasonTest(unittest.TestCase):
    def test_simulated_season_produces_feed_without_player_matches(self):
        from application_double import ApplicationDouble
        from cs2career.career import Career
        from cs2career.league.season import Season
        season = Season(2026, '2026')
        career = Career()
        season.career = career
        with patch.object(Career, 'save'), patch.object(Season, 'save'):
            career.create(dict(mode='create', era='2026', name='Viewer', org='Viewer Club', origin='academy',
                               role='rifle', region='EU'), season)
            career.story_queue = []
            app = ApplicationDouble(career=career, season=season)
            mine = season.your_team_name()
            seen = None
            for _ in range(40):
                season.next_stage(stop_at_season_end=True)
                career.story_queue = []
                out = feed.world_feed(app)
                if out['results']:
                    seen = out
                    break
        self.assertIsNotNone(seen, 'other teams play within the first weeks')
        for row in seen['results']:
            self.assertNotIn(mine, (row['team_a'], row['team_b']))
            self.assertEqual(row['date'], seen['results_date'])
            self.assertIn(row['winner'], (row['team_a'], row['team_b']))


if __name__ == '__main__':
    unittest.main()
