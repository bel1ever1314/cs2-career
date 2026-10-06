from copy import deepcopy
from unittest.mock import patch
import unittest
import test_operation_boundary as fixture
from cs2career.application import ApplicationState
from cs2career.services import external_effects as effects
from cs2career.services import external_commands
from cs2career.services.requests import request_result
from cs2career import tactics


class ExternalEffectBoundaryTests(unittest.TestCase):
    setUp = fixture.OperationTests.setUp

    def test_library_and_outbox_rollback_together_before_game_sync(self):
        self.stack.enter_context(patch.object(tactics, 'library_path', return_value=self.root/'tactics.json'))
        value = tactics.empty_library()
        with patch.object(effects, '_deliver') as deliver:
            with self.assertRaises(ValueError), self.state.operation():
                tactics.write_library(self.root/'tactics.json', value)
                self.assertEqual(value, tactics.load_library())
                effects.enqueue(self.state, 'publish_tactics', self.root/'game', 'de_dust2')
                raise ValueError('reject command')
        deliver.assert_not_called()
        self.assertFalse((self.root/'tactics.json').exists())
        self.assertFalse(self.state.career.incident_state.get(effects.KEY))

    def test_delivery_can_be_retried_after_acknowledgement_interruption(self):
        with self.state.operation():
            effects.enqueue(self.state, 'retire_match', self.root/'game', 'old-nonce')
            self.state.persist()
        loaded = ApplicationState()
        with patch.object(effects, '_deliver', side_effect=OSError('sharing violation')):
            effects.drain(loaded)
        self.assertEqual(1, len(ApplicationState().career.incident_state[effects.KEY]))
        with patch.object(effects, '_deliver') as deliver:
            effects.drain(loaded)
            effects.drain(loaded)
        deliver.assert_called_once()
        self.assertFalse(ApplicationState().career.incident_state[effects.KEY])

    def test_rejected_command_does_not_publish_or_retire(self):
        with patch.object(effects, '_deliver') as deliver:
            with self.assertRaises(ValueError), self.state.operation():
                effects.retire(self.state, self.root/'game', 'old-nonce')
                raise ValueError('invalid switch')
            effects.drain(self.state)
        deliver.assert_not_called()

    def test_plugin_intent_is_durable_and_query_never_installs_again(self):
        path = '/api/3d/setup/install'
        body = dict(request_id='install-boundary-0001')
        def install(state, body, *, before_effect):
            before_effect(dict(game_dir=str(self.root/'game')))
            self.assertEqual('unknown', request_result(ApplicationState(), body['request_id'])['status'])
            raise KeyboardInterrupt('killed after game writes')
        with patch('tools.career3d_install.install_bundle', side_effect=install):
            with self.assertRaises(KeyboardInterrupt): external_commands.command(self.state, path, body)
        restored = ApplicationState()
        with patch('tools.career3d_install.install_bundle', side_effect=AssertionError('must not reinstall')):
            result = external_commands.command(restored, path, body)
        self.assertTrue(result['outcome_unknown'])
        self.assertTrue(result['replayed'])

    def test_invalid_install_does_not_create_a_pending_intent(self):
        body = dict(request_id='invalid-install-0001')
        before = deepcopy(self.state.career.to_json())
        with patch('tools.career3d_install.install_bundle', side_effect=ValueError('invalid path')):
            with self.assertRaises(ValueError): external_commands.command(self.state, '/api/3d/setup/install', body)
        self.assertEqual(before, self.state.career.to_json())


if __name__ == '__main__': unittest.main()
