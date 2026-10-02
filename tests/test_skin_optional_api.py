"""Optional skin integrations, using isolated settings and loopback fixtures."""
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cs2career.cs2 import launch
from cs2career.career import skins
from cs2career.web import server as web
from cs2career.desktop import skin_api


class OptionalSkinApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for context in (
            # These isolated HTTP fixtures intentionally exercise the settings
            # route, not the separate no-game preview gate. All paths/launch
            # detection are mocked below; no real game operation is invoked.
            patch.dict(os.environ, {'CS2CAREER_NO_GAME': '0'}),
            patch.object(launch, 'SETTINGS_PATH', Path(self.tmp.name) / 'cs2.json'),
            patch.object(launch, '_autofill', side_effect=lambda cfg: cfg),
            patch.object(launch, 'cs2_is_live', return_value=False),
        ):
            context.start()
            self.addCleanup(context.stop)
        self.career = SimpleNamespace(real_skins=True, steam_id='76561198000000000',
                                      inventory=[], equipped_ct={}, equipped_t={})
        self.state = SimpleNamespace(career=self.career,
                                     payload=lambda: {'state': {'career': {'skins': {
                                         'skin_integration': launch.skin_integration()}}}})

    def serve(self, srv):
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        def close():
            srv.shutdown()
            thread.join(5)
            srv.server_close()
        self.addCleanup(close)
        return f'http://127.0.0.1:{srv.server_port}'

    def request(self, base, path, token='', body=None):
        req = Request(base + path, headers={'X-Career-Token': token, 'Content-Type': 'application/json'},
                      data=None if body is None else json.dumps(body).encode())
        with urlopen(req, timeout=5) as reply:
            return json.load(reply)

    def test_default_and_opt_in_round_trip(self):
        self.assertEqual('career', launch.settings()['skins_inventory_mode'])
        self.assertFalse(launch.settings()['skin_inspect_enabled'])
        launch.save_settings({'skin_inspect_enabled': True})
        self.assertTrue(launch.settings()['skin_inspect_enabled'])
        launch.save_settings({'skin_inspect_enabled': False})
        self.assertFalse(launch.settings()['skin_inspect_enabled'])
        self.assertFalse(json.loads(launch.SETTINGS_PATH.read_text())['skin_inspect_enabled'])

    def test_modes_and_boolean_values_are_checked(self):
        original = launch.settings()
        for key, value in [('skins_inventory_mode', 'both'), ('skins_inventory_mode', None),
                           ('skin_inspect_enabled', 'false'), ('skin_inspect_enabled', 1)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                launch.save_settings({key: value})
            self.assertEqual(original, launch.settings())

    def test_provider_change_requires_game_closed_but_online_toggle_does_not(self):
        launch.settings()
        with patch.object(launch, 'cs2_is_live', return_value=True):
            with self.assertRaisesRegex(ValueError, '退出 CS2'):
                launch.save_settings({'skins_inventory_mode': 'external'})
            self.assertEqual('career', launch.settings()['skins_inventory_mode'])
            launch.save_settings({'skins_inventory_mode': 'career', 'skin_inspect_enabled': True})
        launch.save_settings({'skins_inventory_mode': 'external'})
        self.assertEqual('external', launch.skin_integration()['inventory_mode'])

    def test_provider_switch_detaches_bridge_before_a_direct_steam_launch(self):
        launch.save_settings({'csgo_path': str(Path(self.tmp.name) / 'game/csgo')})
        with patch.object(launch, 'is_csgo_dir', return_value=True), \
             patch.object(launch, '_prepare_external_skins', return_value=1) as detach:
            launch.save_settings({'skins_inventory_mode': 'external'})
            self.assertEqual(1, detach.call_count)
            launch.save_settings({'skin_inspect_enabled': True})
            self.assertEqual(1, detach.call_count, 'unrelated settings must not edit the game')

    def test_bridge_detach_failure_is_reported_and_keeps_external_write_guards(self):
        launch.save_settings({'csgo_path': str(Path(self.tmp.name) / 'game/csgo')})
        with patch.object(launch, 'is_csgo_dir', return_value=True), \
             patch.object(launch, '_prepare_external_skins', side_effect=OSError('locked bridge')):
            with self.assertRaisesRegex(ValueError, '请暂勿启动 CS2'):
                launch.save_settings({'skins_inventory_mode': 'external'})
        self.assertEqual('external', launch.settings()['skins_inventory_mode'])

    def test_public_integration_metadata_contains_no_player_data(self):
        data = launch.skin_integration()
        self.assertEqual({'inventory_mode', 'inspect_enabled', 'plugin_url', 'web_url',
                          'web_app_url', 'viewer_url'}, set(data))
        self.assertEqual('https://3d.cstrike.app/view', data['viewer_url'])
        self.assertNotIn(self.career.steam_id, json.dumps(data))

    def test_settings_queries_never_rewrite_provider_or_corrupt_file(self):
        launch.save_settings({'skins_inventory_mode': 'external'})
        original = launch.SETTINGS_PATH.read_bytes()
        with patch.object(launch, '_write_settings', side_effect=AssertionError('read must not write')):
            for _ in range(5):
                self.assertEqual('external', launch.settings()['skins_inventory_mode'])
        self.assertEqual(original, launch.SETTINGS_PATH.read_bytes())
        launch.SETTINGS_PATH.write_bytes(b'{"skins_inventory_mode":')
        with self.assertRaisesRegex(ValueError, '原文件未改动'):
            launch.settings()
        self.assertEqual(b'{"skins_inventory_mode":', launch.SETTINGS_PATH.read_bytes())

    def test_failed_atomic_replace_retains_original_settings(self):
        launch.save_settings({'skins_inventory_mode': 'external'})
        original = launch.SETTINGS_PATH.read_bytes()
        with patch.object(launch.os, 'replace', side_effect=OSError('fixture locked file')):
            with self.assertRaises(OSError):
                launch.save_settings({'skin_inspect_enabled': True})
        self.assertEqual(original, launch.SETTINGS_PATH.read_bytes())
        self.assertEqual([], list(launch.SETTINGS_PATH.parent.glob('.cs2-settings-*.tmp')))

    def test_broken_optional_config_does_not_hide_local_cosmetics(self):
        from cs2career.career.career import Career
        launch.SETTINGS_PATH.write_bytes(b'{')
        meta = launch.skin_integration()
        self.assertEqual('unavailable', meta['inventory_mode'])
        self.assertFalse(meta['inspect_enabled'])
        self.assertIn('configuration_error', meta)
        career = Career()
        shop = skins.shop_public(career)
        self.assertIn('inventory', shop)
        self.assertIn('market', shop)
        self.assertEqual(meta, shop['skin_integration'])
        self.assertEqual(b'{', launch.SETTINGS_PATH.read_bytes())

    def test_broken_settings_return_error_without_resetting_external_preferences(self):
        launch.SETTINGS_PATH.write_bytes(b'{"skins_inventory_mode":')
        srv = web.create_server(self.state)
        base = self.serve(srv)
        for path, body in [('/api/cs2/status', None),
                           ('/api/cs2/settings', {'skin_inspect_enabled': True})]:
            with self.subTest(path=path), self.assertRaises(HTTPError) as failure:
                self.request(base, path, srv.token, body)
            self.assertEqual(400, failure.exception.code)
            self.assertFalse(json.load(failure.exception)['ok'])
        self.assertEqual(b'{"skins_inventory_mode":', launch.SETTINGS_PATH.read_bytes())

    def test_settings_response_refreshes_shop_integration(self):
        srv = web.create_server(self.state)
        base = self.serve(srv)
        with patch.object(self.state, 'payload', side_effect=AssertionError('settings must not ingest matches')):
            result = self.request(base, '/api/cs2/settings', srv.token, {'skin_inspect_enabled': True})
            self.assertTrue(result['skin_integration']['inspect_enabled'])
            result = self.request(base, '/api/cs2/settings', srv.token, {'skin_inspect_enabled': False})
            self.assertFalse(result['skin_integration']['inspect_enabled'])
        self.assertNotIn('state', result)

    def test_main_api_and_skin_api_do_not_return_empty_success_for_external_inventory(self):
        srv = web.create_server(self.state)
        base = self.serve(srv)
        game_srv = web.ThreadingHTTPServer(('127.0.0.1', 0), web.SkinApiHandler)
        game_srv.state = self.state
        game_base = self.serve(game_srv)
        path = f'/api/equipped/v5/{self.career.steam_id}.json'
        for url, token in [(base, srv.token), (game_base, '')]:
            self.assertIn('ctWeapons', self.request(url, path, token))
        launch.save_settings({'skins_inventory_mode': 'external'})
        with patch.object(skins, 'equipped_v5_body') as export:
            self.assertIsNone(web._equipped_v5_response(path, self.state))
            for url, token in [(base, srv.token), (game_base, '')]:
                with self.subTest(url=url), self.assertRaises(HTTPError) as failure:
                    self.request(url, path, token)
                self.assertEqual(409, failure.exception.code)
                self.assertFalse(json.load(failure.exception)['ok'])
            export.assert_not_called()
        launch.save_settings({'skins_inventory_mode': 'career'})
        self.assertIn('ctWeapons', self.request(game_base, path))

    def test_legacy_desktop_endpoint_also_honors_external_provider(self):
        with patch.object(skins, 'SKIN_API_PORT', 0):
            srv = skin_api.start_skin_api(lambda: self.career)
        self.assertIsNotNone(srv)
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        base = f'http://127.0.0.1:{srv.server_port}'
        path = f'/api/equipped/v5/{self.career.steam_id}.json'
        self.assertIn('ctWeapons', self.request(base, path))
        launch.save_settings({'skins_inventory_mode': 'external'})
        with self.assertRaises(HTTPError) as failure:
            self.request(base, path)
        self.assertEqual(409, failure.exception.code)


if __name__ == '__main__':
    unittest.main()
