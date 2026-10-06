from application_double import ApplicationDouble
"""Exercise authenticated quick-mode guards through a real loopback server."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cs2career.web.server import create_server
from cs2career.content.loader import PackRegistry


class QuickHttp160Tests(unittest.TestCase):
    def setUp(self):
        self.career = SimpleNamespace(assist={'step_counter': 7, 'quick_mode': True, 'quick_break_ack': 'previous'},
            incident_state={'story_timing': {'windows': [
                {'key': '2026:major-1', 'start': '2026-06-21', 'until': '2026-07-12'}]}})
        self.state = ApplicationDouble(career=self.career, season=SimpleNamespace(date='2026-06-23'),
            persist=Mock(), payload=lambda msg='': {'ok': True, 'msg': msg, 'state': {}})
        self.server = create_server(self.state)
        self.server.game_disabled = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.step_patch = patch('cs2career.career.fast_mode.step', return_value={'status': 'progress'})
        self.step = self.step_patch.start()
        self.addCleanup(self.step_patch.stop)

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def request(self, body, authenticated=True):
        request = Request(f'http://127.0.0.1:{self.server.server_port}/api/assist/quick',
            data=json.dumps(body).encode(), headers={'Content-Type': 'application/json',
            'X-Career-Token': self.server.token if authenticated else 'invalid-session'})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def body(self, **changes):
        return {'token': 'quick-test-0001', 'revision': 7, 'resume_break': True,
                'break_key': '2026:major-1', **changes}

    def test_invalid_session_and_request_fields_never_acknowledge_break(self):
        before = deepcopy(self.career.assist)
        status, _ = self.request(self.body(), authenticated=False)
        self.assertEqual(403, status)
        self.state.persist.assert_not_called()
        invalid = [self.body(token=value) for value in (None, 123, '', 'short', 'x' * 101)]
        invalid += [self.body(revision=value) for value in (None, True, '7', 6, 8)]
        invalid += [self.body(resume_break=value) for value in (None, 0, 1, 'true', [], {})]
        invalid += [self.body(break_key=value) for value in (None, '2026:major-2')]
        for body in invalid:
            with self.subTest(body=body):
                status, _ = self.request(body)
                self.assertEqual(400, status)
                self.assertEqual(before, self.career.assist)
        self.step.assert_not_called()
        self.state.persist.assert_not_called()

    def test_false_resume_runs_normal_step_without_ack(self):
        status, data = self.request(self.body(resume_break=False, break_key='irrelevant'))
        self.assertEqual(200, status)
        self.assertEqual('progress', data['auto_step']['status'])
        self.assertEqual('previous', self.career.assist['quick_break_ack'])
        self.step.assert_called_once_with(self.career, self.state.season, 'quick-test-0001', 7)
        self.state.persist.assert_called_once()

    def test_positive_ack_is_set_before_one_step_and_persist(self):
        def execute(career, season, token, revision):
            self.assertEqual('2026:major-1', career.assist['quick_break_ack'])
            return {'status': 'progress', 'msg': 'resumed'}
        self.step.side_effect = execute
        status, data = self.request(self.body())
        self.assertEqual(200, status)
        self.assertEqual('resumed', data['auto_step']['msg'])
        self.step.assert_called_once()
        self.state.persist.assert_called_once()

    def test_replayed_receipt_does_not_ack_new_window_or_advance(self):
        receipt = {'status': 'paused', 'break_key': '2026:major-1'}
        self.career.assist['last_fast_step'] = {'token': 'quick-test-0001', 'result': receipt}
        before = deepcopy(self.career.assist)
        status, data = self.request(self.body(revision=0, break_key='different-window'))
        self.assertEqual(200, status)
        self.assertEqual(receipt, data['auto_step'])
        self.assertEqual(before, self.career.assist)
        self.step.assert_not_called()
        self.state.persist.assert_not_called()

    def test_resume_outside_window_is_rejected_without_ack(self):
        self.state.season.date = '2026-08-01'
        before = deepcopy(self.career.assist)
        status, _ = self.request(self.body())
        self.assertEqual(400, status)
        self.assertEqual(before, self.career.assist)
        self.step.assert_not_called()


class PhaseTemplate160Tests(unittest.TestCase):
    def test_copied_phase_template_loads_through_real_registry(self):
        source = Path(__file__).resolve().parents[1] / 'extensions/_templates/phase-story-pack'
        with tempfile.TemporaryDirectory(prefix='career-phase-template-') as folder:
            root = Path(folder)
            shutil.copytree(source, root / 'phase-story')
            registry = PackRegistry(root)
            self.assertEqual([], registry.errors)
            self.assertEqual(1, len(registry.packs))
            self.assertEqual('ready', registry.packs[0].status, registry.packs[0].errors)
            rows = [row for payload in registry.payloads('incidents') for row in payload['incidents']]
            self.assertTrue(rows)
            self.assertTrue(any(row['when'] == 'map_started' for row in rows))


if __name__ == '__main__':
    unittest.main()
