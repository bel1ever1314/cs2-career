from application_double import ApplicationDouble
"""Opt-in cosmetic bridge over real authenticated HTTP, using memory only."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cs2career.career import skins
from cs2career.cs2 import launch
from cs2career.web.server import create_server
from tools import career3d_activities as activities
from tools import career3d_service as service
from tools import career3d_skin_tools as skin_tools


QA_ROOT = Path('E:/CS2CareerTools/SkinToolsInterface-20261002/qa')
STICKERS = {
    'stickers': [{'def': 100, 'name': 'Fixture sticker', 'weapon_defs': [7],
                  'url': 'https://private.invalid/sticker.png'}],
    'models': {'7': {'schema_count': 4, 'allowed_slots': [0, 1, 2, 3, 4],
                     'x_min': -0.4, 'x_max': 0.6,
                     'y_min': -0.03, 'y_max': 0.22,
                     'rotation_min': -180, 'rotation_max': 180,
                     'asset_path': 'PRIVATE_MODEL_PATH'}},
}
SKINS = {'ak-fixture': {'id': 'ak-fixture', 'slot': 'ak47', 'def': 7, 'paint': 282}}


def memory_state(persist=lambda: None):
    selected = {
        'id': 'fixture', 'skin_id': 'ak-fixture', 'slot': 'ak47',
        'def': 7, 'paint': 282, 'wear': 0, 'seed': 0, 'stickers': [],
        'spot': 3000, 'sell': 2700, 'private_note': 'PRIVATE_SELECTED_NOTE',
        'steam_id': 'PRIVATE_ITEM_ACCOUNT', 'source_url': 'PRIVATE_ITEM_SOURCE',
    }
    other = {**deepcopy(selected), 'id': 'other-fixture', 'private_note': 'PRIVATE_OTHER_NOTE'}
    career = SimpleNamespace(
        inventory=[selected, other], incident_state={'career3d_service': {'revision': 4, 'receipts': []}},
        real_skins=False, steam_id='76561198012345678', money=999_999,
        equipped_ct={'ak47': 'other-fixture'}, equipped_t={'ak47': 'fixture'},
        training_session=None, inbox=[{'body': 'PRIVATE_CAREER_MAIL'}],
        log=['PRIVATE_CAREER_LOG'], skin_seq=2,
    )
    return ApplicationDouble(career=career, season=SimpleNamespace(date='2026-10-02', events=[]),
                           arena=SimpleNamespace(pending=None), persist=persist)


class SkinToolsHttpTests(unittest.TestCase):
    def setUp(self):
        self.saved = 0
        self.lock_checks = []
        self.config = {**launch.DEFAULTS, 'skin_tools_enabled': False,
                       'steam_exe': 'PRIVATE_STEAM_PATH', 'csgo_path': 'PRIVATE_GAME_PATH',
                       'mod_source_path': 'PRIVATE_MOD_PATH'}
        self.state = memory_state(self.persist)
        # Only the recovery-marker lookup needs a filesystem location. Both the
        # career and settings remain in memory; any temporary path is explicit QA.
        QA_ROOT.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='http-', dir=QA_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.patches = []
        self.config_read = self.start_patch(patch.object(skin_tools, 'read_cs2_config',
                                                        side_effect=self.read_config))
        self.start_patch(patch.object(activities, 'read_cs2_config',
                                     side_effect=lambda: deepcopy(self.config)))
        self.full_context = self.start_patch(patch.object(service, 'read_context',
            side_effect=AssertionError('skin tools must never project full career context')))
        self.start_patch(patch('cs2career.paths.save_root', return_value=Path(self.tmp.name)))
        self.start_patch(patch.object(skins, 'skin_map', return_value=deepcopy(SKINS)))
        self.start_patch(patch.object(skins, 'sticker_catalog_for_item',
                                     return_value=deepcopy(STICKERS)))
        self.external_calls = [self.start_patch(context) for context in (
            patch('urllib.request.urlopen', side_effect=AssertionError('no external requests')),
            patch('urllib.request.urlretrieve', side_effect=AssertionError('no downloads')),
            patch('cs2career.skin_art.urlopen', side_effect=AssertionError('no artwork downloads')),
            patch('tools.career3d_resources.cached_skin_art',
                  side_effect=AssertionError('no artwork lookup')),
            patch.object(skins, 'sync_live', side_effect=AssertionError('no live game sync')),
            patch.object(launch, '_write_settings', side_effect=AssertionError('no settings writes')),
            patch('subprocess.Popen', side_effect=AssertionError('no process launch')),
        )]
        self.server = create_server(self.state)
        self.server.RequestHandlerClass = service.handler_class()
        self.server.display_hour = 8
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.close_server)
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def start_patch(self, context):
        result = context.start()
        self.addCleanup(context.stop)
        return result

    def close_server(self):
        self.server.shutdown()
        self.worker.join(5)
        self.server.server_close()

    def read_config(self):
        self.lock_checks.append(self.server.state_lock._is_owned())
        return deepcopy(self.config)

    def persist(self):
        self.assertTrue(self.server.state_lock._is_owned())
        self.saved += 1

    def request(self, path, body=None, token=None):
        request = Request(self.base + path,
            data=None if body is None else json.dumps(body).encode('utf-8'),
            headers={'X-Career-Token': self.server.token if token is None else token,
                     'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as response:
            return response.code, json.load(response)

    def snapshot(self):
        return deepcopy(vars(self.state.career)), deepcopy(vars(self.state.season)), self.saved

    def assert_private_data_absent(self, response):
        prohibited = {'context', 'state', 'career', 'inventory', 'steam_id', 'steam_exe',
                      'csgo_path', 'mod_source_path', 'skins_source_path', 'private_note',
                      'source_url', 'spot', 'sell', 'money', 'inbox', 'log', 'asset_path', 'url'}
        def check(value):
            if isinstance(value, dict):
                self.assertFalse(prohibited & set(value))
                for child in value.values():
                    check(child)
            elif isinstance(value, list):
                for child in value:
                    check(child)
        check(response)
        blob = json.dumps(response)
        self.assertNotIn('PRIVATE_', blob)
        self.assertNotIn(self.state.career.steam_id, blob)
        self.assertNotIn('other-fixture', blob)

    def edit_body(self, **changes):
        self.config['skin_tools_enabled'] = True
        status, selected = self.request('/api/3d/skin-tools/item?id=fixture')
        self.assertEqual(200, status)
        body = {'schema_version': 1, 'id': 'fixture', 'expected_hash': selected['expected_hash'],
                'revision': selected['revision'],
                'stickers': [{'slot': 0, 'def': 100, 'schema': 0, 'wear': 0,
                              'rotation': 0, 'x': 0, 'y': 0}]}
        return {**body, **changes}

    def test_authentication_rejects_reads_and_writes_without_touching_state(self):
        before = self.snapshot()
        for token in ('', 'not-the-session-token'):
            for path, body in (('/api/3d/skin-tools', None),
                               ('/api/3d/skin-tools/item?id=fixture', None),
                               ('/api/3d/skin-tools/stickers', {})):
                with self.subTest(token=token, path=path):
                    status, response = self.request(path, body, token)
                    self.assertEqual(403, status)
                    self.assertFalse(response['ok'])
                    self.assert_private_data_absent(response)
        self.config_read.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def test_disabled_discovery_is_available_and_item_edits_are_atomic_rejections(self):
        before = self.snapshot()
        status, metadata = self.request('/api/3d/skin-tools')
        self.assertEqual(200, status)
        self.assertTrue(metadata['ok'])
        self.assertEqual(1, metadata['schema_version'])
        self.assertFalse(metadata['enabled'])
        self.assertFalse(metadata['renderer_bundled'])
        self.assertEqual({'read_item': True, 'write_stickers': True}, metadata['capabilities'])
        self.assertEqual({'item': '/api/3d/skin-tools/item',
                          'stickers': '/api/3d/skin-tools/stickers'}, metadata['endpoints'])
        self.assert_private_data_absent(metadata)
        for path, body in (('/api/3d/skin-tools/item?id=fixture', None),
                           ('/api/3d/skin-tools/stickers', {})):
            status, response = self.request(path, body)
            self.assertEqual(400, status)
            self.assertFalse(response['ok'])
            self.assert_private_data_absent(response)
        self.assertEqual(before, self.snapshot())

    def test_enabled_item_is_selected_native_projection_and_read_only(self):
        self.config['skin_tools_enabled'] = True
        before = self.snapshot()
        for _ in range(2):
            status, response = self.request('/api/3d/skin-tools/item?id=fixture')
            self.assertEqual(200, status)
            self.assertEqual('fixture', response['id'])
            self.assertEqual(4, response['revision'])
            self.assertTrue(response['editable'])
            self.assertEqual('next_match', response['sync'])
            self.assertEqual(response['item']['hash'], response['expected_hash'])
            self.assertEqual({'def', 'paint', 'wear', 'seed', 'stickers', 'hash', 'slot'},
                             set(response['item']))
            self.assertEqual([{'def': 100, 'name': 'Fixture sticker'}], response['sticker_catalog'])
            self.assert_private_data_absent(response)
        self.assertEqual(before, self.snapshot())
        self.assertTrue(self.lock_checks and all(self.lock_checks))
        self.full_context.assert_not_called()

    def test_query_validation_and_route_whitelist_reject_other_apis(self):
        self.config['skin_tools_enabled'] = True
        before = self.snapshot()
        for query in ('', '?id=', '?id=fixture&id=other-fixture',
                      '?id=fixture&extra=yes', '?id=missing-fixture'):
            status, response = self.request('/api/3d/skin-tools/item' + query)
            self.assertEqual(400, status, query)
            self.assertFalse(response['ok'])
            self.assert_private_data_absent(response)
        for path, body in (('/api/state', None), ('/api/equipped/v5/76561198012345678.json', None),
                           ('/api/3d/skin-tools/download', None),
                           ('/api/3d/skin-tools/download', {})):
            status, response = self.request(path, body)
            self.assertEqual(404, status, path)
            self.assert_private_data_absent(response)
        self.assertEqual(before, self.snapshot())

    def test_stale_hash_revision_and_invalid_edits_never_persist(self):
        body = self.edit_body()
        cases = [
            {**body, 'expected_hash': '0' * 64}, {**body, 'expected_hash': 'bad'},
            {**body, 'revision': 3}, {**body, 'revision': True},
            {**body, 'schema_version': True}, {**body, 'schema_version': 2},
            {**body, 'id': 'missing-fixture'}, {**body, 'unexpected': 'field'},
            {**body, 'stickers': None},
            {**body, 'stickers': [{'slot': 0, 'def': 999}]},
            {**body, 'stickers': [{'slot': 0, 'def': 100, 'x': 0.61}]},
            {**body, 'stickers': [{'slot': 0, 'def': 100, 'url': 'https://invalid.test'}]},
            {**body, 'stickers': [{'slot': 0, 'def': 100}] * 2},
        ]
        for invalid in cases:
            with self.subTest(body=invalid):
                before = self.snapshot()
                status, response = self.request('/api/3d/skin-tools/stickers', invalid)
                self.assertEqual(400, status)
                self.assertFalse(response['ok'])
                self.assert_private_data_absent(response)
                self.assertEqual(before, self.snapshot())
        self.full_context.assert_not_called()

    def test_success_increments_revision_and_saves_once_with_selected_item_only(self):
        body = self.edit_body()
        before = deepcopy(vars(self.state.career))
        status, response = self.request('/api/3d/skin-tools/stickers', body)
        self.assertEqual(200, status)
        self.assertTrue(response['ok'])
        self.assertEqual('fixture', response['id'])
        self.assertEqual(5, response['revision'])
        self.assertEqual(1, self.saved)
        self.assertNotEqual(body['expected_hash'], response['expected_hash'])
        self.assertEqual(response['expected_hash'], response['item']['hash'])
        self.assertEqual(response['item']['stickers'], self.state.career.inventory[0]['stickers'])
        self.assertEqual(before['inventory'][1], self.state.career.inventory[1])
        unchanged = {key: value for key, value in before.items() if key not in ('inventory', 'incident_state')}
        self.assertEqual(unchanged, {key: value for key, value in vars(self.state.career).items()
                                     if key not in ('inventory', 'incident_state')})
        for key, value in before['inventory'][0].items():
            if key not in ('stickers', 'hash'):
                self.assertEqual(value, self.state.career.inventory[0][key])
        self.assert_private_data_absent(response)
        # A retry must be rejected before another save. A fresh read can remove
        # the sticker and increments the enclosing service revision only once.
        after = self.snapshot()
        self.assertEqual(400, self.request('/api/3d/skin-tools/stickers', body)[0])
        self.assertEqual(after, self.snapshot())
        remove = self.edit_body(stickers=[])
        status, removed = self.request('/api/3d/skin-tools/stickers', remove)
        self.assertEqual(200, status)
        self.assertEqual(6, removed['revision'])
        self.assertEqual(2, self.saved)
        self.assertEqual([], removed['item']['stickers'])
        self.assert_private_data_absent(removed)
        self.full_context.assert_not_called()

    def test_queries_and_edits_never_download_sync_launch_or_write_settings(self):
        self.config['skin_tools_enabled'] = True
        before = self.snapshot()
        self.assertEqual(200, self.request('/api/3d/skin-tools?download=1&url=https://invalid.test')[0])
        self.assertEqual(400, self.request('/api/3d/skin-tools/item?id=fixture&download=1')[0])
        self.assertEqual(before, self.snapshot())
        body = self.edit_body()
        self.assertEqual(200, self.request('/api/3d/skin-tools/stickers', body)[0])
        for call in self.external_calls:
            call.assert_not_called()


class SkinToolsSettingsTests(unittest.TestCase):
    def setUp(self):
        self.config = {**launch.DEFAULTS, 'skin_tools_enabled': False,
                       'skins_inventory_mode': 'external', 'skin_inspect_enabled': True,
                       'steam_exe': 'MEMORY_ONLY_STEAM', 'csgo_path': 'MEMORY_ONLY_GAME'}
        self.writes = 0
        self.path = MagicMock(spec=Path)
        self.path.exists.return_value = True
        self.path.is_file.return_value = True
        self.path.read_text.side_effect = lambda *args, **kwargs: json.dumps(self.config)
        self.state = memory_state()
        for context in (
            patch.object(launch, 'SETTINGS_PATH', self.path),
            patch('cs2career.storage.transaction.read_bytes',
                  side_effect=lambda path: json.dumps(self.config).encode('utf-8')),
            patch.object(launch, '_autofill', side_effect=lambda cfg: cfg),
            patch.object(launch, '_write_settings', side_effect=self.write_settings),
            patch.object(launch, 'cs2_is_live', return_value=False),
            patch.object(activities, '_running_cs2', return_value=False),
            patch.object(activities, 'config_status', return_value={'ready': False, 'fixture': True}),
        ):
            context.start()
            self.addCleanup(context.stop)

    def write_settings(self, config):
        self.config = deepcopy(config)
        self.writes += 1

    def test_missing_flag_defaults_off_and_readers_preserve_boolean_values(self):
        self.config.pop('skin_tools_enabled')
        self.assertIs(False, launch.settings()['skin_tools_enabled'])
        self.assertIs(False, activities.read_cs2_config()['skin_tools_enabled'])
        for enabled in (True, False):
            self.config['skin_tools_enabled'] = enabled
            self.assertIs(enabled, launch.settings()['skin_tools_enabled'])
            self.assertIs(enabled, activities.settings_context(self.state)['skin_tools_enabled'])
        self.assertEqual(0, self.writes)

    def test_launch_saves_flag_without_changing_other_independent_preferences(self):
        for enabled in (True, False):
            before = deepcopy(self.config)
            result = launch.save_settings({'skin_tools_enabled': enabled})
            self.assertIs(enabled, result['skin_tools_enabled'])
            self.assertIs(enabled, self.config['skin_tools_enabled'])
            self.assertEqual({key: value for key, value in before.items() if key != 'skin_tools_enabled'},
                             {key: value for key, value in self.config.items() if key != 'skin_tools_enabled'})
        self.assertEqual(2, self.writes)

    def test_3d_settings_command_round_trips_flag_and_preserves_other_preferences(self):
        before = deepcopy(vars(self.state.career))
        for enabled in (True, False):
            result = activities.settings_command(self.state,
                {'revision': 4, 'settings': {'skin_tools_enabled': enabled}})
            self.assertIs(enabled, result['settings']['skin_tools_enabled'])
            self.assertIs(enabled, self.config['skin_tools_enabled'])
            self.assertEqual('external', self.config['skins_inventory_mode'])
            self.assertIs(True, self.config['skin_inspect_enabled'])
            self.assertEqual('MEMORY_ONLY_STEAM', self.config['steam_exe'])
            self.assertEqual('MEMORY_ONLY_GAME', self.config['csgo_path'])
            self.assertEqual(before, vars(self.state.career))
        self.assertEqual(2, self.writes)

    def test_wrong_types_are_rejected_before_memory_settings_or_career_change(self):
        for value in ('true', 'false', 0, 1, None, [], {}):
            for command in (lambda body: launch.save_settings(body),
                            lambda body: activities.settings_command(self.state,
                                {'revision': 4, 'settings': body})):
                with self.subTest(value=value, command=command):
                    before = deepcopy(self.config), deepcopy(vars(self.state.career)), self.writes
                    with self.assertRaises(ValueError):
                        command({'skin_tools_enabled': value})
                    self.assertEqual(before, (self.config, vars(self.state.career), self.writes))


if __name__ == '__main__':
    unittest.main()
