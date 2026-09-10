from copy import deepcopy
import unittest
from tools.compare_player_flows import FIELDS, compare


class FlowComparisonTests(unittest.TestCase):
    def fixture(self):
        return {**dict.fromkeys(FIELDS), 'complete':True,'errors':[],'business_hash':'full-state-hash',
                'match_checks':[{'hash':'ten-player-and-round-events'}],
                'reload':{key:True for key in ('date_equal','balance_equal','player_equal',
                    'roster_and_club_equal','loan_equal','growth_points_equal','all_match_stats_and_events_equal')}}

    def test_full_evidence_not_just_victories(self):
        a = self.fixture(); b = deepcopy(a)
        b['elapsed_seconds'] = 50
        self.assertTrue(compare(a,b)['equal'])
        b['match_checks'][0]['hash'] = 'different-damage-with-same-score'
        self.assertFalse(compare(a,b)['equal'])
        self.assertIn('match_checks',compare(a,b)['differences'])
        self.assertEqual('match_checks[0].hash',compare(a,b)['first_differences'][0]['path'])

    def test_incomplete_or_unverified_runs_cannot_pass(self):
        for change in ({'complete':False},{'business_hash':''},{'errors':['failed']},{'reload':{}}):
            a = self.fixture(); a.update(change)
            self.assertFalse(compare(a,a)['equal'])

    def test_missing_metadata_on_both_sides_is_not_evidence(self):
        a = self.fixture()
        del a['commands']
        self.assertFalse(compare(a,a)['equal'])
