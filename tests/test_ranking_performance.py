"""Optimisation equivalence: no changed invite thresholds or rank formula."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from cs2career.career import Career
from cs2career.league.season import Season
from cs2career.league.vrs import VRS, parse_date


class RankingPerformanceTests(unittest.TestCase):
    def test_single_pass_matches_original_per_team_sums_and_ties(self):
        teams = [{'id':str(i),'name':f'Team {i}','region':'AS'} for i in range(60)]
        vrs = VRS()
        vrs.results = [{'team':str(i % 58),'date':f'2025-{1 + i % 12:02d}-08',
                        'points':0.1 + (i % 19) / 7} for i in range(3000)]
        # Unknown historic orgs are ignored, just as live() did before.
        vrs.results.append({'team':'deleted','date':'invalid','points':1})
        for day in ('2025-01-08','2025-09-09','2026-01-08','2028-01-08'):
            expected = [{**t,'vrs':vrs.live(t['id'],day)} for t in teams]
            expected.sort(key=lambda r:-r['vrs'])
            for rank, row in enumerate(expected,1):
                row['rank'] = rank
            with patch('cs2career.league.vrs.parse_date',wraps=parse_date) as dates:
                actual = vrs.table(teams,day)
            self.assertEqual(expected, actual)
            self.assertEqual(13, dates.call_count)  # Today plus 12 result dates.
        vrs.results.append({'team':'59','date':'2028-01-08','points':500})
        self.assertEqual('59',vrs.table(teams,'2028-01-08')[0]['id'])

    def test_invite_batch_uses_one_ranking_without_changing_eligibility(self):
        season = Season(2025,'2025')
        career = Career(); career.exists = True; career.unsigned = False
        career.team_id = season.teams[-2]['id']; career.save = Mock()
        mine = next(r for r in season.vrs.table(season.teams,season.date) if r['id']==career.team_id)
        expected = {e['id']:career.eligible_invite(season,e) for e in season.events}
        self.assertEqual(expected, {e['id']:career.eligible_invite(season,e,rank_row=mine) for e in season.events})
        with patch.object(season.vrs,'table',wraps=season.vrs.table) as table:
            career.dispatch_invites(season)
        self.assertEqual(1,table.call_count)
        self.assertTrue(career.inbox)
        self.assertTrue(all(expected[m['event_id']] for m in career.inbox if m['kind']=='invite'))
