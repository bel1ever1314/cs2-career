from application_double import ApplicationDouble
"""Skin ownership discovery is not consent to enable optional cosmetics.

All game paths are disposable fixtures; no real CS2 tree or save is inspected.
"""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from cs2career.career.career import Career
from cs2career.cs2 import launch
from tools import career3d_activities as activities
from tools import career3d_service as service


class Career3DSkinDefaultsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='career3d-skin-defaults-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.game = self.root / 'fixture-game' / 'game' / 'csgo'
        self.owner = (self.game / 'addons' / 'counterstrikesharp' / 'configs'
                      / 'plugins' / 'InventorySimulator' / 'owner.txt')
        self.owner.parent.mkdir(parents=True)
        self.owner.write_text('76561198000000000', encoding='ascii')
        self.cfg = {**launch.DEFAULTS, 'csgo_path': str(self.game)}
        self.state = ApplicationDouble(
            career=SimpleNamespace(steam_id='', real_skins=False), persist=Mock())
        self.config_reader = self._patch(patch.object(
            activities, 'read_cs2_config', side_effect=lambda: dict(self.cfg)))
        self.installed = self._patch(patch.object(
            activities, '_existing_skin_plugin', return_value=True))

    def _patch(self, context):
        value = context.start()
        self.addCleanup(context.stop)
        return value

    def test_new_career_and_optional_tools_start_disabled(self):
        career = Career()
        self.assertIs(career.real_skins, False)
        self.assertEqual(career.steam_id, '')
        self.assertIs(launch.DEFAULTS['skin_inspect_enabled'], False)
        self.assertIs(launch.DEFAULTS['skin_tools_enabled'], False)

    def test_installed_plugin_and_owner_only_fill_account_not_opt_in(self):
        service._import_skin_owner(self.state)
        self.assertEqual(self.state.career.steam_id, '76561198000000000')
        self.assertIs(self.state.career.real_skins, False)
        self.state.persist.assert_called_once_with()
        self.installed.assert_called_once_with(self.cfg)

    def test_discovery_preserves_explicit_enabled_and_disabled_preferences(self):
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                self.state.career.steam_id = ''
                self.state.career.real_skins = enabled
                self.state.persist.reset_mock()
                service._import_skin_owner(self.state)
                self.assertEqual(self.state.career.steam_id, '76561198000000000')
                self.assertIs(self.state.career.real_skins, enabled)
                self.state.persist.assert_called_once_with()

    def test_existing_account_is_not_overwritten_and_choice_is_unchanged(self):
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                self.state.career.steam_id = '76561198000000001'
                self.state.career.real_skins = enabled
                service._import_skin_owner(self.state)
                self.assertEqual(self.state.career.steam_id, '76561198000000001')
                self.assertIs(self.state.career.real_skins, enabled)
                self.state.persist.assert_not_called()
                self.installed.assert_not_called()

    def test_repeated_startup_does_not_reenable_a_disabled_preference(self):
        service._import_skin_owner(self.state)
        self.state.persist.reset_mock()
        self.state.career.real_skins = False
        service._import_skin_owner(self.state)
        self.assertIs(self.state.career.real_skins, False)
        self.state.persist.assert_not_called()

    def test_missing_owner_does_not_enable_or_persist(self):
        self.owner.unlink()
        service._import_skin_owner(self.state)
        self.assertEqual(self.state.career.steam_id, '')
        self.assertIs(self.state.career.real_skins, False)
        self.state.persist.assert_not_called()
        self.installed.assert_not_called()

    def test_invalid_owner_does_not_enable_or_persist(self):
        for invalid in ('', '7656119800000000', '765611980000000000',
                        '76561198abcdef000', '\uFF17' * 17):
            with self.subTest(owner_kind='invalid', length=len(invalid)):
                self.owner.write_text(invalid, encoding='utf-8')
                service._import_skin_owner(self.state)
                self.assertEqual(self.state.career.steam_id, '')
                self.assertIs(self.state.career.real_skins, False)
                self.state.persist.assert_not_called()
                self.installed.assert_not_called()

    def test_owner_without_installed_plugin_is_not_imported(self):
        self.installed.return_value = False
        service._import_skin_owner(self.state)
        self.assertEqual(self.state.career.steam_id, '')
        self.assertIs(self.state.career.real_skins, False)
        self.state.persist.assert_not_called()

    def test_unreadable_owner_does_not_enable_or_persist(self):
        with patch.object(Path, 'read_text', side_effect=OSError('fixture unreadable')):
            service._import_skin_owner(self.state)
        self.assertEqual(self.state.career.steam_id, '')
        self.assertIs(self.state.career.real_skins, False)
        self.state.persist.assert_not_called()
        self.installed.assert_not_called()

    def test_no_game_path_does_not_try_discovery(self):
        self.cfg['csgo_path'] = ''
        service._import_skin_owner(self.state)
        self.assertEqual(self.state.career.steam_id, '')
        self.assertIs(self.state.career.real_skins, False)
        self.state.persist.assert_not_called()
        self.installed.assert_not_called()


if __name__ == '__main__':
    unittest.main()
