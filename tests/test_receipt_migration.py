"""Acknowledgement of legacy receipts is read-only, bounded and unambiguous."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs2career.services.requests import request_result
from cs2career.services.controls import _receipt
from cs2career.storage import receipts
from cs2career.storage.immutable import freeze


class ReceiptMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'save'
        self.root.mkdir()
        root_patch = patch('cs2career.paths.save_root', return_value=self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        self.state = SimpleNamespace(career=SimpleNamespace(incident_state={}),
                                     season=SimpleNamespace(events=[], history=[]))

    def test_old_domain_namespaces_and_archived_match_are_readable_without_writes(self):
        result = {'reason': 'done'}
        incident = self.state.career.incident_state
        incident['career3d_service'] = {key: [dict(request_id=key, result=result)] for key in
            ('receipts', 'controls_receipts', 'tactics_import_receipts', 'season_receipts')}
        incident['career3d_service']['start_receipts'] = [dict(id='start', result=result)]
        incident['career3d_social'] = {'receipts': [dict(request_id='social', result=result)]}
        incident['career3d_environment'] = {'requests': {'environment': {'result': result}}}
        self.state.season.history = [freeze({'matches': [dict(id='m1', career3d_receipts=[
            dict(request_id='match', result={'reason': 'finished', 'report': 'x'*90000})])]})]
        before = deepcopy(incident)
        for name in ('receipts', 'controls_receipts', 'tactics_import_receipts', 'season_receipts',
                     'start', 'social', 'environment', 'match'):
            with self.subTest(namespace=name):
                response = request_result(self.state, name)
                self.assertEqual('completed', response['status'])
                self.assertTrue(response['result']['result_summary'])
                self.assertTrue(response['result']['ok'])
                self.assertLessEqual(len(json.dumps(response['result']).encode()), receipts.MAX_RESULT_BYTES)
                response['result']['reason'] = 'UI mutation'
        self.assertEqual(before, incident)
        self.assertEqual([], list(self.root.iterdir()))

    def test_namespace_collision_is_unknown_even_with_identical_success_text(self):
        row = dict(request_id='same-request', result={'reason': 'done'})
        self.state.career.incident_state['career3d_service'] = {
            'controls_receipts': [row], 'season_receipts': [deepcopy(row)]}
        result = request_result(self.state, 'same-request')
        self.assertEqual('unknown', result['status'])
        self.assertIsNone(result['result'])

    def test_missing_and_pending_manual_receipts_never_mean_safe_to_retry(self):
        with patch('cs2career.manual_saves.requests', return_value={'pending': {'status': 'pending'}}):
            for rid in ('pending', 'missing'):
                result = request_result(self.state, rid)
                self.assertEqual('unknown', result['status'])
                self.assertIsNone(result['result'])
        with patch('cs2career.manual_saves.requests', return_value={
                'done': {'status': 'done', 'result': {'loaded': True, 'id': 'slot'}}}):
            result = request_result(self.state, 'done')
            self.assertEqual('completed', result['status'])
            self.assertTrue(result['result']['loaded'])

    def test_mirrored_start_receipt_is_not_a_collision(self):
        self.state.career.incident_state['career3d_service'] = {
            'start_receipts': [dict(id='start', result={'new_career': True})]}
        mirrored = lambda rid: [('start', {'new_career': True})]
        collision = lambda rid: [('start_draw', {'new_career': True})]
        self.assertEqual('completed', request_result(self.state, 'start', independent_receipts=mirrored)['status'])
        self.assertEqual('unknown', request_result(self.state, 'start', independent_receipts=collision)['status'])

    def test_central_confirmation_does_not_open_legacy_files(self):
        receipts.record(self.state.career, 'central', '/api/example', {}, {'ok': True})
        with patch('cs2career.services.requests._legacy_results', side_effect=AssertionError('legacy read')):
            result = request_result(self.state, 'central')
        self.assertEqual('central', result['source'])

    def test_controls_keep_direct_call_receipts_but_do_not_duplicate_managed_receipts(self):
        self.state.career.incident_state['career3d_service'] = {'revision': 0}
        body = dict(request_id='direct-command', revision=0)
        expected = {'reason': 'done', 'report': 'x'*90000}
        self.assertEqual(expected, _receipt(self.state, 'example', body, lambda: deepcopy(expected)))
        replay = _receipt(self.state, 'example', body, lambda: self.fail('duplicate execution'))
        self.assertTrue(replay['replayed'])
        managed = dict(body, request_id='managed-command')
        with receipts.request_scope(managed['request_id']):
            _receipt(self.state, 'example', managed, lambda: deepcopy(expected))
        saved = self.state.career.incident_state['career3d_service']['controls_receipts']
        self.assertEqual(['direct-command'], [row['request_id'] for row in saved])
        self.assertTrue(receipts.needs_legacy_receipt(managed['request_id']))

    def test_receipt_scope_is_reset_after_failure_and_nested_scope(self):
        self.assertFalse(receipts.needs_legacy_receipt(None))
        with self.assertRaises(ValueError), receipts.request_scope('outer'):
            self.assertFalse(receipts.needs_legacy_receipt('outer'))
            self.assertTrue(receipts.needs_legacy_receipt('other'))
            with receipts.request_scope('inner'):
                self.assertFalse(receipts.needs_legacy_receipt('inner'))
            self.assertFalse(receipts.needs_legacy_receipt('outer'))
            raise ValueError('aborted')
        self.assertTrue(receipts.needs_legacy_receipt('outer'))
