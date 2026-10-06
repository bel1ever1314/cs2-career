from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from cs2career.storage import receipts as r


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.career = SimpleNamespace(incident_state={})

    def test_small_results_roundtrip_without_projection_or_shared_references(self):
        result = {'ok': True, 'amount': 10, 'context': {'huge': 'x'*100000}, 'state': {}}
        r.record(self.career, 'small-1', '/api/buy', {'item': 'a'}, result, now=100)
        row = r.lookup(self.career, 'small-1')
        self.assertEqual({'ok': True, 'amount': 10}, row['result'])
        row['result']['amount'] = 0
        self.assertEqual(10, r.lookup(self.career, 'small-1')['result']['amount'])

    def test_large_match_response_keeps_confirmation_and_identity_not_report(self):
        result = {'ok': True, 'status': 'finished', 'msg': '完成'*10000,
                  'result': {'match_id': '2026:event:match', 'maps': ['x'*100000]},
                  'reveal': {'events': ['x'*100000]}, 'context': {}}
        before = deepcopy(result)
        r.record(self.career, 'large-1', '/api/3d/match/simulate', {'match_id': 'm1'}, result, now=100)
        row = r.lookup(self.career, 'large-1')
        self.assertTrue(row['result']['result_summary'])
        self.assertTrue(row['result']['ok'])
        self.assertEqual('finished', row['result']['status'])
        self.assertEqual('m1', row['result']['match_id'])
        self.assertNotIn('result', row['result'])
        self.assertNotIn('reveal', row['result'])
        self.assertLessEqual(size(row['result']), r.MAX_RESULT_BYTES)
        self.assertLessEqual(size(row), r.MAX_ROW_BYTES)
        self.assertEqual(before, result)

    def test_summary_with_many_long_fields_is_still_bounded(self):
        result = {key: '字'*9000 for key in r.SUMMARY_FIELDS}
        result['ok'] = True
        summary = r.compact_result(result)
        self.assertTrue(summary['result_summary'])
        self.assertLessEqual(size(summary), r.MAX_RESULT_BYTES)

    def test_legacy_large_rows_compact_on_write_but_lookup_is_pure(self):
        old = dict(request_id='old', fingerprint=r.fingerprint('/old', {}), path='/old',
                   created_at=100, result={'ok': True, 'report': ['x'*50000]})
        self.career.incident_state['operation_receipts'] = [old]
        before = deepcopy(self.career.incident_state)
        self.assertTrue(r.lookup(self.career, 'old')['result']['result_summary'])
        self.assertEqual(before, self.career.incident_state)
        r.record(self.career, 'next', '/next', {}, {'ok': True}, now=101)
        self.assertTrue(self.career.incident_state['operation_receipts'][0]['result']['result_summary'])

    def test_time_count_and_total_byte_limits_preserve_newest_results(self):
        # Prebuild long-lived receipts so this measures one migration/write,
        # not thousands of redundant saves.
        rows = [dict(request_id=str(i), fingerprint=r.fingerprint('/item', {'i': i}),
                     path='/item', created_at=100+i, result={'ok': True, 'msg': 'x'*4000})
                for i in range(r.MAX_RECEIPTS + 10)]
        rows.insert(0, dict(rows[0], request_id='expired', created_at=-r.RETENTION_SECONDS))
        self.career.incident_state['operation_receipts'] = rows
        r.record(self.career, 'newest', '/new', {}, {'ok': True}, now=10000)
        kept = self.career.incident_state['operation_receipts']
        self.assertLessEqual(len(kept), r.MAX_RECEIPTS)
        self.assertLessEqual(size(kept), r.MAX_TOTAL_BYTES)
        self.assertIsNotNone(r.lookup(self.career, 'newest'))
        self.assertIsNone(r.lookup(self.career, 'expired'))
        self.assertIsNone(r.lookup(self.career, '0'))  # Unknown, not "not executed".

    def test_request_fingerprint_collision_is_never_a_replay(self):
        r.record(self.career, 'request1', '/buy', {'item': 'a'}, {'ok': True}, now=100)
        with self.assertRaises(ValueError):
            r.record(self.career, 'request1', '/buy', {'item': 'b'}, {'ok': True}, now=101)
        r.record(self.career, 'request1', '/buy', {'item': 'a', 'revision': 2}, {'ok': True}, now=102)
        self.assertEqual(1, len(self.career.incident_state['operation_receipts']))

    def test_pending_can_complete_once_but_never_change_identity_or_regress(self):
        r.record(self.career, 'handoff', '/launch', {'match_id': 'a'}, {'status': 'waiting'}, pending=True)
        self.assertEqual('pending', r.lookup(self.career, 'handoff')['phase'])
        with self.assertRaises(ValueError):
            r.record(self.career, 'handoff', '/launch', {'match_id': 'b'}, {'status': 'waiting'})
        r.record(self.career, 'handoff', '/launch', {'match_id': 'a'}, {'status': 'dispatched'})
        self.assertNotIn('phase', r.lookup(self.career, 'handoff'))
        r.record(self.career, 'handoff', '/launch', {'match_id': 'a'}, {'status': 'waiting'}, pending=True)
        self.assertEqual('dispatched', r.lookup(self.career, 'handoff')['result']['status'])
        self.assertEqual(1, len(self.career.incident_state['operation_receipts']))
