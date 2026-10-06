"""Real HTTP + disk boundaries for preferences, creation and independent draws."""
from contextlib import ExitStack
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import test_recovery_http as http
from test_calibrated_draw import donor_pool
from cs2career.application import ApplicationState
from cs2career.career import Career, skins
from cs2career.cs2 import launch
from cs2career.storage import transaction as tx
from cs2career.storage.receipts import lookup
from tools import career3d_activities as activities
from tools import career3d_attribute_draw as draw
from tools.career3d_start import recover_creation


class PreferenceStartBoundaryTests(unittest.TestCase):
    serving = http.RecoveryHttpTests.serving
    request = http.RecoveryHttpTests.request

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.folder = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.root = self.folder / 'save'
        self.root.mkdir()
        (self.folder / '.career3d-demo.json').write_text(
            json.dumps({'kind': 'cs2career-godot-demo'}), encoding='utf-8')
        self.stack.enter_context(patch.dict(os.environ, {'CS2CAREER_SAVE_DIR': str(self.root)}))
        self.stack.enter_context(patch('cs2career.paths.save_root', return_value=self.root))
        self.stack.enter_context(patch('cs2career.league.season.STATE_PATH', self.root / 'season.json'))
        self.stack.enter_context(patch.object(Career, 'path', return_value=self.root / 'career.json'))
        self.stack.enter_context(patch.object(launch, 'SETTINGS_PATH', self.root / 'cs2.json'))
        self.stack.enter_context(patch.object(activities, '_running_cs2', return_value=False))
        self.stack.enter_context(patch.object(skins, 'sync_live', side_effect=AssertionError('No game writes')))
        self.stack.enter_context(patch.object(launch, 'install_mod', side_effect=AssertionError('No install')))
        self.stack.enter_context(patch('tools.career3d_service._pause', return_value=('', '')))
        self.state = ApplicationState()
        self.stack.enter_context(patch.object(self.state, '_reconcile', self.state.persist))
        self.stack.enter_context(patch.object(activities, 'settings_context', side_effect=lambda state:
            dict(activities.read_cs2_config(), real_skins=state.career.real_skins)))
        self.stack.enter_context(patch('tools.career3d_service.read_context', side_effect=lambda state, hour:
            {'calendar': {'revision': state.career.incident_state.get('career3d_service', {}).get('revision', 0)},
             'settings': activities.settings_context(state)}))
        self.state.persist()
        self.settings_body = dict(revision=0, settings={'difficulty': 'High'},
                                  real_skins=True, steam_id='76561198000000000')
        team = self.state.season.teams[0]
        self.create_body = dict(revision=0, request_id='create-fixture-0001', confirm_replace=True,
            career=dict(mode='join', era='2026', team_id=team['id'],
                        player_id=team['players'][0]['player_id'], role='rifle', quick_mode=True))

    def files(self):
        return {p.name: p.read_bytes() for p in self.root.glob('*.json')}

    def test_settings_context_sees_first_pending_config_and_one_commit_replays(self):
        writes = []
        with self.serving(), patch.object(tx, '_checkpoint', side_effect=writes.append):
            status, result = self.request('/api/3d/settings', self.settings_body)
            self.assertEqual(200, status, result)
            self.assertEqual('High', result['context']['settings']['difficulty'])
            self.assertTrue(result['context']['settings']['real_skins'])
            before = self.files()
            status, replay = self.request('/api/3d/settings', self.settings_body)
            self.assertTrue(replay['replayed'])
            self.assertEqual(before, self.files())
            changed = dict(self.settings_body, settings={'difficulty': 'Low'})
            self.assertEqual(400, self.request('/api/3d/settings', changed)[0])
        for filename in ('career.json', 'season.json', 'cs2.json'):
            self.assertEqual(1, writes.count('staged:' + filename))
        loaded = ApplicationState()
        self.assertTrue(loaded.career.real_skins)
        self.assertEqual(self.settings_body['steam_id'], loaded.career.steam_id)
        self.assertIsNotNone(lookup(loaded.career, 'http-request-0001'))

    def test_rejected_settings_commit_restores_all_files_and_memory(self):
        launch._write_settings(dict(launch.DEFAULTS, difficulty='Low'))
        before = self.files()
        def fail(point):
            if point == 'before_commit': raise OSError('before commit')
        with self.serving(), patch.object(tx, '_checkpoint', fail):
            status, _ = self.request('/api/3d/settings', self.settings_body)
        self.assertEqual(500, status)
        self.assertFalse(self.state.career.real_skins)
        self.assertEqual(before, self.files())
        self.assertEqual('Low', activities.read_cs2_config()['difficulty'])
        self.assertIsNone(lookup(self.state.career, 'http-request-0001'))

    def test_partial_settings_replacement_recovers_all_three_files_and_receipt(self):
        def fail(point):
            if point == 'replaced:cs2.json': raise OSError('after config replace')
        with self.serving(), patch.object(tx, '_checkpoint', fail):
            status, result = self.request('/api/3d/settings', self.settings_body)
        self.assertEqual(503, status, result)
        self.state = ApplicationState()
        self.assertTrue(self.state.career.real_skins)
        self.assertEqual('High', activities.read_cs2_config()['difficulty'])
        with self.serving():
            status, result = self.request('/api/3d/requests?id=http-request-0001')
            self.assertEqual('completed', result['status'])
            self.assertEqual('central', result['source'])

    def test_pending_config_is_visible_only_in_the_operation_thread(self):
        launch._write_settings(dict(launch.DEFAULTS, difficulty='Low'))
        seen = []
        with self.assertRaises(ValueError), self.state.operation():
            launch._write_settings(dict(launch.DEFAULTS, difficulty='High'))
            self.assertEqual('High', activities.read_cs2_config()['difficulty'])
            worker = threading.Thread(target=lambda: seen.append(activities.read_cs2_config()['difficulty']))
            worker.start()
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
            raise ValueError('abort')
        self.assertEqual(['Low'], seen)
        self.assertEqual('Low', activities.read_cs2_config()['difficulty'])

    def test_creation_rejection_does_not_retire_draft_or_replace_career(self):
        before = self.files()
        def fail(point):
            if point == 'before_commit': raise OSError('before creation commit')
        with self.serving(), patch.object(tx, '_checkpoint', fail):
            status, _ = self.request('/api/3d/start/create', self.create_body)
        self.assertEqual(500, status)
        self.assertEqual(before, self.files())
        self.assertFalse(self.state.career.exists)
        self.assertFalse(draw._metadata_path().exists())

    def test_creation_preferences_mode_and_receipt_recover_before_draft_cleanup(self):
        self.state.career.steam_id = '76561198000000000'
        self.state.career.real_skins = True
        self.state.persist()
        def fail(point):
            if point == 'replaced:career.json': raise OSError('after creation commit')
        with self.serving(), patch.object(tx, '_checkpoint', fail):
            status, result = self.request('/api/3d/start/create', self.create_body)
        self.assertEqual(503, status, result)
        self.assertFalse(draw._metadata_path().exists())
        self.state = ApplicationState()
        self.assertTrue(self.state.career.exists)
        self.assertTrue(self.state.career.assist['quick_mode'])
        self.assertTrue(self.state.career.real_skins)
        self.assertEqual('76561198000000000', self.state.career.steam_id)
        self.assertEqual(1, self.state.career.incident_state['career3d_service']['revision'])
        self.assertIsNotNone(lookup(self.state.career, self.create_body['request_id']))
        recover_creation(self.state)
        metadata = draw._metadata_path().read_bytes()
        with patch.object(draw, '_save', side_effect=AssertionError('no repeated finalization')):
            recover_creation(self.state)
        self.assertEqual(metadata, draw._metadata_path().read_bytes())
        before = self.files()
        with self.serving():
            status, replay = self.request('/api/3d/start/create', self.create_body)
        self.assertEqual(200, status, replay)
        self.assertTrue(replay['replayed'])
        self.assertEqual(before, self.files())

    def test_finalizer_failure_retains_new_career_and_is_recoverable(self):
        with self.serving(), patch.object(draw, 'finish_creation', side_effect=OSError('draft held open')):
            status, result = self.request('/api/3d/start/create', self.create_body)
        self.assertEqual(503, status, result)
        self.state = ApplicationState()
        self.assertTrue(self.state.career.exists)
        self.assertTrue(self.state.career.assist['quick_mode'])
        recover_creation(self.state)
        self.assertIn(self.create_body['request_id'], draw._load()['create_receipts'])

    def test_real_draw_is_retired_only_after_creation_and_read_confirmation_is_pure(self):
        from cs2career.world.ability import AXES
        with patch.object(draw, 'team_source_pool', return_value=donor_pool(calibrated=True)):
            draft = draw.draw_command(self.state, 'open', dict(era='2026', request_id='fixture-open'))['attribute_draw']
        ident = draft['draft_id']
        for axis in AXES:
            roll = draw.draw_command(self.state, 'roll', dict(era='2026', draft_id=ident,
                                    request_id='fixture-roll-' + axis))['draw']
            draw.draw_command(self.state, 'select', dict(era='2026', draft_id=ident,
                request_id='fixture-select-' + axis, draw_id=roll['draw_id'], axis=axis,
                player_id=roll['players'][0]['player_id']))
        body = dict(self.create_body, career=dict(mode='create', era='2026', origin='attribute_draw',
            draft_id=ident, name='Draw Fixture', org='Draw Fixture Club', role='rifle', region='AS'))
        before = draw._metadata_path().read_bytes()
        with self.serving():
            _, confirmation = self.request('/api/3d/requests?id=fixture-roll-firepower')
            self.assertEqual('completed', confirmation['status'])
            self.assertTrue(confirmation['result']['result_summary'])
            self.assertEqual(before, draw._metadata_path().read_bytes())
            status, result = self.request('/api/3d/start/create', body)
        self.assertEqual(200, status, result)
        self.assertEqual('created', draw._load()['drafts'][ident]['status'])
        self.assertNotIn('2026', draw._load()['active_team_drafts'])
        self.assertEqual(ident, self.state.career.incident_state['career3d_attribute_draw']['draft_id'])
        # A portable save does not include machine-local draft metadata.
        original = draw._metadata_path().read_bytes()
        with patch.object(draw, '_metadata_path', return_value=self.folder / 'portable-start.json'):
            recover_creation(self.state)
            self.assertIn(body['request_id'], draw._load()['create_receipts'])
            self.assertEqual({}, draw._load()['drafts'])
        self.assertEqual(original, draw._metadata_path().read_bytes())

    def test_draw_commit_failure_recovers_original_roll_and_never_consumes_another_attempt(self):
        with patch.object(draw, 'team_source_pool', return_value=donor_pool(calibrated=True)):
            draft = draw.draw_command(self.state, 'open', dict(era='2026', request_id='fixture-open'))['attribute_draw']
        body = dict(action='roll', era='2026', draft_id=draft['draft_id'], request_id='interrupted-draw')
        def fail(point):
            if point == 'replaced:' + draw.METADATA_NAME: raise OSError('draw replacement interruption')
        career_before = self.files()
        with self.serving(), patch.object(tx, '_checkpoint', fail):
            status, result = self.request('/api/3d/start/draw', body)
        self.assertEqual(503, status, result)
        tx.recover(self.folder)
        self.assertEqual(career_before, self.files())
        self.state = ApplicationState()
        career_before = self.files()  # Startup migrations are not draw effects.
        before = draw._metadata_path().read_bytes()
        with self.serving():
            _, confirmation = self.request('/api/3d/requests?id=interrupted-draw')
            self.assertEqual('completed', confirmation['status'])
            status, replay = self.request('/api/3d/start/draw', body)
            self.assertEqual(200, status, replay)
            self.assertTrue(replay['replayed'])
            self.assertEqual(1, replay['attribute_draw']['attempts_used'])
        self.assertEqual(before, draw._metadata_path().read_bytes())
        self.assertEqual(career_before, self.files())


if __name__ == '__main__':
    unittest.main()
