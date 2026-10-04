"""Device diagnostics must reflect effective equipment, not just a toggle."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs2career.cs2 import launch
from tools import career3d_activities as activities


class Career3DSkinStatusTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {**launch.DEFAULTS, 'csgo_path': 'fixture-game/game/csgo'}
        self.career = SimpleNamespace(
            real_skins=True, steam_id='76561198000000000', money=100,
            inventory=[{'id': 'owned-rifle', 'skin_id': 'fixture-skin'}],
            equipped_ct={}, equipped_t={'ak47': 'owned-rifle'}, incident_state={})
        self.state = SimpleNamespace(career=self.career)
        self._patch(patch.object(activities, 'read_cs2_config', return_value=self.cfg))
        self.installed = self._patch(patch.object(activities, '_existing_skin_plugin', return_value=True))

    def _patch(self, context):
        value = context.start()
        self.addCleanup(context.stop)
        return value

    def test_ready_requires_effective_equipment(self):
        status = activities._skin_loadout_context(self.career, self.cfg)
        self.assertEqual(status['state'], 'ready')
        self.assertEqual((status['equipped_ct'], status['equipped_t']), (0, 1))
        self.assertNotIn('steam_id', status)
        self.career.equipped_t = {'ak47': 'removed-item'}
        status = activities._skin_loadout_context(self.career, self.cfg)
        self.assertEqual(status['state'], 'not_equipped')
        self.assertEqual(self.career.equipped_t, {'ak47': 'removed-item'})

    def test_missing_plugin_is_not_ready_even_with_equipment(self):
        self.installed.return_value = False
        status = activities._skin_loadout_context(self.career, self.cfg)
        self.assertEqual(status['state'], 'unavailable')
        self.assertFalse(status['plugin_installed'])

    def test_disabled_and_external_do_not_equip_or_enable(self):
        before = deepcopy(self.career.__dict__)
        self.career.real_skins = False
        self.assertEqual(activities._skin_loadout_context(self.career, self.cfg)['state'], 'disabled')
        self.cfg['skins_inventory_mode'] = 'external'
        self.assertEqual(activities._skin_loadout_context(self.career, self.cfg)['state'], 'external')
        self.assertFalse(self.career.real_skins)
        self.assertEqual(self.career.inventory, before['inventory'])
        self.assertEqual(self.career.equipped_t, before['equipped_t'])

    def test_settings_expose_reason_without_mutating_career(self):
        self.career.equipped_t = {}
        before = deepcopy(self.career.__dict__)
        with patch.object(activities, 'config_status', return_value={}), \
                patch('tools.career3d_install.setup_context', return_value={}):
            result = activities.settings_context(self.state)
        self.assertEqual(result['loadout_status']['state'], 'not_equipped')
        self.assertIn('配装为空', result['loadout_status']['reason'])
        self.assertEqual(self.career.__dict__, before)

    def test_market_no_longer_claims_empty_loadout_is_ready(self):
        self.career.equipped_t = {}
        with patch('cs2career.career.skins.shop_public', return_value={'cases': [], 'market': [], 'inventory': []}), \
                patch('cs2career.skin_art.manifest', return_value={}), \
                patch('tools.career3d_skin_bundles.bundle_context', return_value={}):
            result = activities.skin_context(self.state)
        self.assertFalse(result['integration_ready'])
        self.assertEqual(result['loadout_status']['state'], 'not_equipped')
        self.assertEqual(result['integration_reason'], result['loadout_status']['reason'])


if __name__ == '__main__':
    unittest.main()
