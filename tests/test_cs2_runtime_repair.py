"""Runtime deployment fixtures only; never write to a real game or save."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import repair_cs2_runtime as repair


class RuntimeRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stage = self.root / 'stage'; self.stage.mkdir()
        self.game = self.root / 'game'; self.game.mkdir()
        self.capsule = self.stage / 'compatible-mod'; self.capsule.mkdir()
        self.settings = self.root / 'save' / 'cs2.json'; self.settings.parent.mkdir()
        self.settings.write_text(json.dumps({'csgo_path': str(self.game), 'mod_source_path': 'old', 'difficulty': 'High'}), encoding='utf-8')
        (self.game / 'steam.inf').write_text('test')
        self.manifest = {}
        for name, value in [('active_game_pids', []), ('audit_signatures', {'patterns': []})]:
            m = patch.object(repair, name, return_value=value); m.start(); self.addCleanup(m.stop)

    def item(self, rel, new, old=None):
        src = self.capsule / rel; src.parent.mkdir(parents=True, exist_ok=True); src.write_bytes(new)
        self.manifest[rel] = repair.digest(src)
        (self.stage / 'capsule-files.json').write_text(json.dumps(self.manifest))
        target = self.game / rel
        if old is not None:
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(old)
        return target

    def deploy(self):
        return repair.apply(self.stage, self.game, self.capsule, self.settings)

    def test_updates_dll_settings_but_preserves_plugins_and_player_state(self):
        dll = self.item('addons/BotController/bin/win64/BotController.dll', b'new', b'old')
        lab = self.game / 'addons/counterstrikesharp/plugins/BotLab/BotLab.dll'
        lab.parent.mkdir(parents=True); lab.write_bytes(b'keep lab')
        career = self.settings.parent / 'career.json'; career.write_bytes(b'untouched')
        old_settings = self.settings.read_bytes()
        receipt = self.deploy()
        self.assertEqual(b'new', dll.read_bytes())
        self.assertEqual(b'keep lab', lab.read_bytes())
        self.assertEqual(b'untouched', career.read_bytes())
        result = json.loads(self.settings.read_text()); self.assertEqual('High', result['difficulty'])
        self.assertEqual(str(self.capsule.resolve()), result['mod_source_path'])
        repair.rollback(receipt)
        self.assertEqual(b'old', dll.read_bytes())
        self.assertEqual(old_settings, self.settings.read_bytes())

    def test_never_overwrites_config_identity_or_match_request(self):
        for rel in ('addons/BotHider/config.json','addons/BotHider/bot_info.json',
                    'addons/counterstrikesharp/configs/core.json',
                    'addons/counterstrikesharp/plugins/CareerMatch/match_request.json'):
            self.item(rel, b'default', b'personal')
        self.deploy()
        for rel in self.manifest:
            self.assertEqual(b'personal', (self.game / rel).read_bytes())

    def test_retires_only_duplicate_gamedata_and_restores_on_rollback(self):
        self.item('addons/safe.dll', b'new')
        duplicate = self.game / 'addons/counterstrikesharp/gamedata/inventory-simulator.previous.json'
        duplicate.parent.mkdir(parents=True); duplicate.write_bytes(b'old signatures')
        receipt = self.deploy()
        self.assertFalse(duplicate.exists())
        self.assertEqual(b'old signatures', (receipt.parent / 'retired' / duplicate.name).read_bytes())
        repair.rollback(receipt)
        self.assertEqual(b'old signatures', duplicate.read_bytes())
        self.assertFalse((self.game / 'addons/safe.dll').exists())
        self.assertTrue((receipt.parent / 'rolled-back-new/addons/safe.dll').exists())

    def test_running_game_blocks_before_any_write(self):
        dll = self.item('addons/safe.dll', b'new', b'old')
        with patch.object(repair, 'active_game_pids', return_value=[42]):
            with self.assertRaisesRegex(RuntimeError, 'Close CS2'): self.deploy()
        self.assertEqual(b'old', dll.read_bytes())
        self.assertFalse(list(self.stage.glob('backup-*')))

    def test_changed_capsule_or_ambiguous_signatures_block(self):
        dll = self.item('addons/safe.dll', b'new', b'old')
        (self.capsule / 'addons/safe.dll').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'changed'): self.deploy()
        self.assertEqual(b'old', dll.read_bytes())
        with patch.object(repair, 'audit_signatures', return_value={'patterns': [{'matches': 2}]}):
            with self.assertRaisesRegex(ValueError, 'preflight'): self.deploy()

    def test_partial_failure_restores_already_written_files(self):
        first = self.item('addons/first.dll', b'new', b'old')
        second = self.item('addons/second.dll', b'new2', b'old2')
        real_copy = repair.atomic_copy
        def fail_second(src, dst):
            if src == self.capsule / 'addons/second.dll': raise OSError('simulated locked DLL')
            real_copy(src, dst)
        with patch.object(repair, 'atomic_copy', side_effect=fail_second):
            with self.assertRaisesRegex(OSError, 'locked'): self.deploy()
        self.assertEqual(b'old', first.read_bytes()); self.assertEqual(b'old2', second.read_bytes())
        self.assertEqual('old', json.loads(self.settings.read_text())['mod_source_path'])

    def test_paths_cannot_escape_target(self):
        for path in ('../outside', '.', str(self.root / 'other')):
            with self.assertRaises(ValueError): repair.inside(self.game, path)

    def test_legacy_launcher_recovery_source_cannot_downgrade_cosmetics(self):
        self.item('addons/counterstrikesharp/plugins/BotRandomizer/BotRandomizer.dll', b'new', b'old')
        parked = self.game / 'addons/counterstrikesharp/plugins_off/BotRandomizer/BotRandomizer.dll'
        parked.parent.mkdir(parents=True); parked.write_bytes(b'old recovery')
        receipt = self.deploy()
        self.assertEqual(b'new', parked.read_bytes())
        repair.rollback(receipt)
        self.assertEqual(b'old recovery', parked.read_bytes())

    def test_external_apply_preserves_plugin_inventory_signatures_and_duplicate_backup(self):
        data = json.loads(self.settings.read_text())
        data['skins_inventory_mode'] = 'external'
        self.settings.write_text(json.dumps(data))
        external_paths = (
            'addons/counterstrikesharp/plugins/InventorySimulator/InventorySimulator.dll',
            'addons/counterstrikesharp/plugins/InventorySimulator/lang/en.json',
            'addons/counterstrikesharp/plugins/InvsimCareer/InvsimCareer.dll',
            'addons/counterstrikesharp/gamedata/inventory-simulator.json',
            'addons/counterstrikesharp/gamedata/inventory-simulator.previous.json',
            'addons/counterstrikesharp/configs/plugins/InventorySimulator/inventories.json',
        )
        for rel in external_paths:
            self.item(rel, b'template', b'user owned')
        absent = 'addons/counterstrikesharp/configs/plugins/InventorySimulator/missing-owner.txt'
        self.item(absent, b'must not create')
        dll = self.item('addons/BotController/bin/win64/BotController.dll', b'new safe', b'old safe')
        receipt = self.deploy()
        self.assertEqual(b'new safe', dll.read_bytes())
        for rel in external_paths:
            self.assertEqual(b'user owned', (self.game / rel).read_bytes())
        self.assertFalse((self.game / absent).exists())
        changes = json.loads(receipt.read_text())['changes']
        self.assertFalse(any(repair.external_inventory_file(row['relative']) for row in changes))
        repair.rollback(receipt)
        self.assertEqual(b'old safe', dll.read_bytes())
        self.assertEqual('external', json.loads(self.settings.read_text())['skins_inventory_mode'])

    def test_old_career_receipt_cannot_rollback_current_external_inventory_or_mode(self):
        skin = self.item('addons/counterstrikesharp/plugins/InventorySimulator/InventorySimulator.dll',
                         b'career template', b'old career plugin')
        gamedata = self.item('addons/counterstrikesharp/gamedata/inventory-simulator.json',
                            b'career signatures', b'old career signatures')
        safe = self.item('addons/safe.dll', b'new safe', b'old safe')
        receipt = self.deploy()
        data = json.loads(self.settings.read_text())
        data.update(skins_inventory_mode='external', skin_inspect_enabled=True, custom_preference='keep')
        self.settings.write_text(json.dumps(data))
        skin.write_bytes(b'new user plugin')
        gamedata.write_bytes(b'new user signatures')
        repair.rollback(receipt)
        self.assertEqual(b'new user plugin', skin.read_bytes())
        self.assertEqual(b'new user signatures', gamedata.read_bytes())
        self.assertEqual(b'old safe', safe.read_bytes())
        restored = json.loads(self.settings.read_text())
        self.assertEqual('external', restored['skins_inventory_mode'])
        self.assertTrue(restored['skin_inspect_enabled'])
        self.assertEqual('keep', restored['custom_preference'])
        self.assertEqual('old', restored['mod_source_path'])

    def test_launcher_and_standalone_repair_use_the_same_external_file_boundaries(self):
        from cs2career.cs2 import launch
        for rel in (
            'addons/counterstrikesharp/plugins/InventorySimulator/InventorySimulator.dll',
            'ADDONS/COUNTERSTRIKESHARP/PLUGINS/InvsimCareer/InvsimCareer.dll',
            'addons/counterstrikesharp/gamedata/inventory-simulator.previous.json',
            'cfg/invsim_career.cfg', 'inventories.json', 'inventories.career.json',
            'addons/BotRandomizer/BotRandomizer.dll', 'cfg/server.cfg', 'addons/safe.dll',
        ):
            with self.subTest(relative=rel):
                self.assertEqual(launch.external_inventory_file(rel), repair.external_inventory_file(rel))


if __name__ == '__main__': unittest.main()
