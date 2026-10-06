import unittest

from cs2career.cs2.result import result_usable, _pick_roster


class RealResultIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.result = dict(schema_version=2, status='finished', complete=True,
            ct_score=9, t_score=13, map='de_ancient', request_nonce='test', players=[
                dict(player_id=f'p{i}', name=f'P{i}', team='ct' if i < 5 else 't',
                     kills=13, deaths=14, assists=3, damage=1500, survived_rounds=8, kast=.7)
                for i in range(10)])
        self.session = dict(nonce='test', map='ancient', expected_player_ids=[f'p{i}' for i in range(10)])

    def test_rejects_observed_26_kills_29_deaths_in_22_rounds(self):
        self.assertEqual('', result_usable(self.result, self.session))
        self.result['players'][0].update(kills=26, deaths=29)
        self.assertIn('上限', result_usable(self.result, self.session))

    def test_survival_and_finite_statistics(self):
        self.result['players'][0]['survived_rounds'] = 9
        self.assertIn('不守恒', result_usable(self.result, self.session))
        self.result['players'][0]['damage'] = float('nan')
        self.assertIn('无效', result_usable(self.result, self.session))

    def test_no_early_overtime_commit(self):
        self.result.update(status='in_progress', ct_score=13, t_score=12)
        self.assertIn('还没正常结束', result_usable(self.result, self.session))

    def test_finished_scores_must_obey_shared_rules(self):
        for a, b in [(13, 9), (16, 12), (16, 14), (19, 15), (19, 17), (22, 20)]:
            self.result.update(ct_score=a, t_score=b)
            for player in self.result['players']:
                player['survived_rounds'] = a + b - player['deaths']
            self.assertEqual('', result_usable(self.result, self.session), (a, b))
        for a, b in [(17, 13), (18, 12), (13, 12), (16, 15), (True, 9), ('13', 9), (-1, 13)]:
            self.result.update(ct_score=a, t_score=b)
            self.assertTrue(result_usable(self.result, self.session), (a, b))

    def test_session_and_rules_echo_cannot_override_saved_identity(self):
        from cs2career.engine.sessions import stamp
        stamp(self.session, 'cs2')
        # Old plugin reports remain compatible after full nonce/roster/score checks.
        self.assertEqual('', result_usable(self.result, self.session))
        self.result.update(session_id=self.session['session_id'], rules_id=self.session['rules_id'])
        self.assertEqual('', result_usable(self.result, self.session))
        self.result['rules_id'] = 'different-format'
        self.assertIn('规则', result_usable(self.result, self.session))
        self.result['rules_id'] = self.session['rules_id']
        self.result['session_id'] = 'retired-session'
        self.assertIn('会话', result_usable(self.result, self.session))

    def test_no_fallback_from_wrong_id_to_human_or_name(self):
        roster = [dict(name='KSCERATO', player_id='real')]
        self.assertIsNone(_pick_roster('KSCERATO', roster, 'KSCERATO', False, 'wrong'))
        self.assertEqual('real', _pick_roster('renamed', roster, '', True, 'real')['player_id'])

    def test_duplicate_identity_bindings_rejected(self):
        self.result['identity_bindings'] = {str(i): f'p{i}' for i in range(10)}
        self.assertEqual('', result_usable(self.result, self.session))
        self.result['identity_bindings']['1'] = 'p0'
        self.assertIn('槽位', result_usable(self.result, self.session))
