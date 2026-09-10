from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from tools.career_matrix import SEEDS, RELOAD_CHECKS, cases, evidence_errors, preflight
from tools.flow_evidence import activity_evidence


class CareerMatrixTests(unittest.TestCase):
    def test_full_matrix_is_45_unique_preselected_cases(self):
        rows = cases(['2024','2025','2026'],['street','academy','prodigy'],SEEDS)
        self.assertEqual(45,len(rows))
        self.assertEqual(45,len({tuple(r.values()) for r in rows}))

    def test_wrong_rules_failed_runs_or_short_targets_cannot_resume_as_annual(self):
        expected = {'era':'2025','origin':'academy','seed':17,'target':'year','years':1,
                    'policy':'development','region':'AS'}
        report = {**expected,'source_fingerprint':'version-a','complete':True,'errors':[],
                  'business_hash':'full-state','match_checks':[{'hash':'all-stats'}],
                  'reload':dict.fromkeys(RELOAD_CHECKS,True)}
        self.assertEqual([],evidence_errors(report,expected,'version-a'))
        for change in ({'target':'first-event'},{'source_fingerprint':'old'},
                       {'complete':False},{'reload':{}},{'match_checks':[]},{'region':'EU'}):
            broken = deepcopy(report); broken.update(change)
            self.assertTrue(evidence_errors(broken,expected,'version-a'))

    def test_activity_ignores_rejected_and_same_day_attempts(self):
        commands = [{'path':'/api/series/skip','date':day,'ok':ok} for day,ok in
                    [('2025-02-12',True),('2025-02-12',True),('2025-03-01',False),('2025-04-20',True)]]
        commands.append({'path':'/api/story/ack','date':'2025-03-15','ok':True})
        result = activity_evidence(commands,'2025-01-08','2025-05-01')
        self.assertEqual(35,result['first_match_wait_days'])
        self.assertEqual(2,result['formal_match_days'])
        self.assertEqual(67,result['longest_between_matches']['days'])
        self.assertEqual(11,result['trailing_without_match_days'])
        self.assertTrue(result['trailing_interval_censored'])
        self.assertEqual(1,result['rejected_commands'])

    def test_no_match_yet_is_not_zero_wait_or_a_complete_gap(self):
        result = activity_evidence([],'2025-01-08','2025-02-08')
        self.assertIsNone(result['first_match_wait_days'])
        self.assertIsNone(result['longest_between_matches'])
        self.assertEqual(31,result['trailing_without_match_days'])

    def test_bad_resume_keeps_previous_manifest_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            path = output / 'matrix.json'
            old = {'target':'first-event','region':'AS','policy':'development',
                   'source_fingerprint':'old','expected_runs':1,'runs':[]}
            text = json.dumps(old)
            path.write_text(text,encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'mismatch'):
                preflight(output,cases(['2025'],['academy'],[17]),
                          {'target':'year','region':'AS','policy':'development'},'new',True)
            self.assertEqual(text,path.read_text(encoding='utf-8'))
