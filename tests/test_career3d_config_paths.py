from application_double import ApplicationDouble
"""Settings/status fixtures do not search for or install into a real CS2 tree."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs2career.cs2 import launch
from tools import career3d_activities as activities


class Career3DConfigPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='career3d-config-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.settings = self.root / 'save/cs2.json'
        self.settings.parent.mkdir()
        self.steam = self.root / 'Steam 中文/steam.exe'
        self.steam.parent.mkdir()
        self.steam.write_bytes(b'fixture executable, not runnable')
        self.game_root = self.root / 'Steam 中文/steamapps/common/Counter-Strike Global Offensive'
        self.game = self.game_root / 'game/csgo'
        self.game.mkdir(parents=True)
        (self.game / 'gameinfo.gi').write_text('fixture', encoding='utf-8')
        self.mod = self.root / 'CS2 Bot Improver 中文'
        for relative in ('addons/metamod', 'addons/counterstrikesharp', 'overrides'):
            (self.mod / relative).mkdir(parents=True)
        self.cfg = {**launch.DEFAULTS, 'steam_exe': str(self.steam),
                    'csgo_path': str(self.game), 'mod_source_path': str(self.mod)}
        self.start(patch.object(launch, 'SETTINGS_PATH', self.settings))
        self.start(patch.object(launch, 'find_mod_source', side_effect=AssertionError('no discovery')))
        self.start(patch.object(launch, 'find_csgo_path', side_effect=AssertionError('no discovery')))
        self.start(patch.object(launch, 'install_mod', side_effect=AssertionError('no implicit install')))
        self.start(patch.object(launch, 'career_match_current', return_value=True))
        self.process = self.start(patch.object(activities, '_running_cs2', return_value=False))
        self.state = ApplicationDouble(career=SimpleNamespace(
            incident_state={'career3d_service': {'revision': 7}},
            training_session=None, real_skins=False, steam_id=''),
            arena=SimpleNamespace(pending=None), season=SimpleNamespace(events=[]))
        launch._write_settings(self.cfg)

    def start(self, context):
        value = context.start()
        self.addCleanup(context.stop)
        return value

    def installed(self):
        for relative in ('addons/metamod', 'addons/counterstrikesharp', 'addons/BotHider'):
            (self.game / relative).mkdir(parents=True, exist_ok=True)
        for name in ('CareerMatch', 'BotBuy'):
            folder = self.game / 'addons/counterstrikesharp/plugins' / name
            folder.mkdir(parents=True)
            (folder / (name + '.dll')).write_bytes(b'fixture')
            (folder / (name + '.deps.json')).write_text('{}', encoding='utf-8')

    def test_valid_paths_without_components_report_install_not_path_error(self):
        before = self.settings.read_bytes()
        value = activities.config_status()
        self.assertFalse(value['ready'])
        self.assertEqual(value['path_errors'], [])
        self.assertEqual(value['missing'], ['runtime', 'career_match', 'botbuy'])
        self.assertEqual(len(value['component_errors']), 3)
        self.assertIn('安装填写目录的人机增强', value['reason'])
        self.assertNotIn('核对路径', value['reason'])
        self.assertTrue(value['plugins_install_enabled'])
        self.assertEqual(self.settings.read_bytes(), before)
        self.process.assert_not_called()

    def test_ready_requires_components_in_the_selected_game(self):
        self.installed()
        value = activities.config_status()
        self.assertTrue(value['ready'])
        self.assertEqual(value['path_errors'], [])
        self.assertEqual(value['component_errors'], [])
        self.assertEqual(value['missing'], [])

    def test_old_match_plugin_is_an_update_hint_not_a_path_error(self):
        self.installed()
        with patch.object(launch, 'career_match_current', return_value=False):
            value = activities.config_status()
        self.assertFalse(value['ready'])
        self.assertEqual([], value['path_errors'])
        self.assertIn('career_match_update', value['missing'])
        self.assertIn('无需重新下载', value['reason'])

    def test_custom_vpk_settings_validate_locally_without_touching_source(self):
        from cs2career.cs2.profiles import write_vpk
        source = self.root / 'my bots.vpk'
        write_vpk(source, 'Default\n Skill = 77\nEnd\n')
        before = source.read_bytes()
        activities.settings_command(self.state, {'revision': 7, 'settings': {
            'bot_profile_mode': 'custom', 'bot_profile_source': f'"{source}"'}})
        saved = json.loads(self.settings.read_text('utf-8'))
        self.assertEqual('custom', saved['bot_profile_mode'])
        self.assertEqual(str(source), saved['bot_profile_source'])
        self.assertEqual(before, source.read_bytes())
        snapshot = self.settings.read_bytes()
        with self.assertRaises(ValueError):
            activities.settings_command(self.state, {'revision': 7, 'settings': {'bot_profile_source': str(self.root / 'missing.vpk')}})
        self.assertEqual(snapshot, self.settings.read_bytes())
        activities.settings_command(self.state, {'revision': 7, 'settings': {'bot_profile_mode': 'career', 'bot_profile_source': ''}})
        self.assertEqual('', json.loads(self.settings.read_text('utf-8'))['bot_profile_source'])

    def test_status_includes_cheap_compatibility_context_without_downloads(self):
        self.installed()
        hint = {'current':True, 'revision':'fixture-cohort', 'components':[]}
        with patch('tools.career3d_runtime_compat.runtime_context', return_value=hint) as context, \
             patch('tools.career3d_runtime_compat._download_archive', side_effect=AssertionError('no status download')):
            value = activities.config_status()
        self.assertEqual(hint, value['compatibility'])
        self.assertTrue(value['ready'])
        context.assert_called_once_with(self.mod)

    def test_missing_game_reports_path_instead_of_guessing_component_state(self):
        launch._write_settings({**self.cfg, 'csgo_path': str(self.root / 'missing/game/csgo')})
        value = activities.config_status()
        self.assertEqual(len(value['path_errors']), 1)
        self.assertIn('CS2 目录', value['path_errors'][0])
        self.assertEqual(value['component_errors'], [])
        self.assertNotIn('安装填写目录', value['reason'])

    def test_csgo_directory_without_gameinfo_is_not_ready(self):
        self.installed()
        (self.game / 'gameinfo.gi').unlink()
        value = activities.config_status()
        self.assertFalse(value['checks']['csgo'])
        self.assertIn('gameinfo.gi', value['reason'])

    def test_addons_subfolder_is_not_a_complete_source(self):
        self.installed()
        launch._write_settings({**self.cfg, 'mod_source_path': str(self.mod / 'addons')})
        value = activities.config_status()
        self.assertFalse(value['checks']['mod'])
        self.assertEqual(value['missing'], ['mod'])
        self.assertIn('overrides', value['path_errors'][0])
        self.assertEqual(value['component_errors'], [])

    def test_quoted_existing_paths_are_read_without_rewriting_preferences(self):
        quoted = {**self.cfg, 'steam_exe': f' "{self.steam}" ',
                  'csgo_path': f' "{self.game}" ', 'mod_source_path': f' "{self.mod}" '}
        launch._write_settings(quoted)
        before = self.settings.read_bytes()
        value = activities.config_status()
        self.assertEqual(value['path_errors'], [])
        self.assertEqual(value['steam_exe'], str(self.steam))
        self.assertEqual(value['mod_source_path'], str(self.mod))
        self.assertEqual(before, self.settings.read_bytes())

    def test_saving_strips_quotes_and_resolves_game_root_without_installing(self):
        before = deepcopy(self.state.career.incident_state)
        value = activities.settings_command(self.state, {'revision': 7, 'settings': {
            'steam_exe': f' "{self.steam}" ', 'csgo_path': f' "{self.game_root}" ',
            'mod_source_path': f' "{self.mod}" ', 'skins_source_path': ' "" '}})
        saved = json.loads(self.settings.read_text('utf-8'))
        self.assertEqual(saved['steam_exe'], str(self.steam))
        self.assertEqual(Path(saved['csgo_path']), self.game)
        self.assertEqual(saved['mod_source_path'], str(self.mod))
        self.assertEqual(saved['skins_source_path'], '')
        self.assertEqual(value['settings']['config']['path_errors'], [])
        self.assertEqual(self.state.career.incident_state, before)
        self.assertFalse((self.game / 'addons').exists())

    def test_empty_and_whitespace_paths_stay_empty_not_current_directory(self):
        activities.settings_command(self.state, {'revision': 7, 'settings': {
            key: ' "  " ' for key in activities._CS2_PATH_FIELDS}})
        saved = json.loads(self.settings.read_text('utf-8'))
        for key in activities._CS2_PATH_FIELDS:
            self.assertEqual(saved[key], '')
        value = activities.config_status()
        self.assertEqual(value['csgo_path'], '')
        self.assertEqual(len(value['path_errors']), 3)
        self.assertEqual(value['component_errors'], [])

    def test_saving_still_rejects_stale_revision_or_running_game(self):
        original = self.settings.read_bytes()
        with self.assertRaises(ValueError):
            activities.settings_command(self.state, {'revision': 6, 'settings': self.cfg})
        self.process.return_value = True
        with self.assertRaisesRegex(ValueError, '完全退出 CS2'):
            activities.settings_command(self.state, {'revision': 7, 'settings': {'csgo_path': str(self.root)}})
        self.assertEqual(original, self.settings.read_bytes())

    def test_running_game_or_waiting_map_still_saves_preferences_for_the_next_map(self):
        # Each launched map freezes its own settings; saving only writes cs2.json.
        self.process.return_value = True
        result = activities.settings_command(self.state, {'revision': 7, 'settings': {**self.cfg, 'difficulty': 'High'}})
        self.assertEqual('High', json.loads(self.settings.read_text('utf-8'))['difficulty'])
        self.assertEqual('', result['settings']['apply_note'])
        self.process.return_value = False
        match = {'id': 'm1', 'played': False, 'cs2_session': {'nonce': 'n1', 'map_index': 1}}
        self.state.season.events.append({'matches': [match]})
        result = activities.settings_command(self.state, {'revision': 7, 'settings': {**self.cfg, 'bot_aim': 'head'}})
        self.assertEqual('head', json.loads(self.settings.read_text('utf-8'))['bot_aim'])
        self.assertIn('下一张图', result['reason'])
        self.assertTrue(result['settings']['live_match'])
        self.assertIn('下一张图', result['settings']['apply_note'])
        # Unchanged paths in the full form are not a change of game folder.
        before = self.settings.read_bytes()
        with self.assertRaisesRegex(ValueError, 'CS2 目录'):
            activities.settings_command(self.state, {'revision': 7, 'settings': {**self.cfg, 'csgo_path': str(self.root)}})
        self.assertEqual(before, self.settings.read_bytes())

    def test_optional_skin_account_error_is_not_reported_as_a_path_error(self):
        original = self.settings.read_bytes()
        with self.assertRaisesRegex(ValueError, 'SteamID64.*关闭游戏内换肤'):
            activities.settings_command(self.state, {'revision': 7, 'settings': {},
                                                    'real_skins': True, 'steam_id': ''})
        self.assertEqual(original, self.settings.read_bytes())


if __name__ == '__main__':
    unittest.main()
