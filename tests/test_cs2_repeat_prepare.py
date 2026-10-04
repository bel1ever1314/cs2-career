"""Repeat local preparation and skin export in disposable game/save trees."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from cs2career.career import skins
from cs2career.cs2 import launch


class RepeatPreparationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cs2-repeat-prepare-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.game = self.root / "game" / "csgo"
        for relative in ("cfg", "addons/metamod", "addons/counterstrikesharp", "addons/BotHider"):
            (self.game / relative).mkdir(parents=True, exist_ok=True)
        (self.game / "gameinfo.gi").write_text(
            '"GameInfo" { "FileSystem" { "SearchPaths" { Game csgo } } }', encoding="utf-8")
        self.mod = self.root / "mod"
        self.mod.mkdir()
        self.save = self.root / "save"
        self.save.mkdir()
        self.cfg = dict(launch.DEFAULTS, csgo_path=str(self.game), mod_source_path=str(self.mod))
        self.career = SimpleNamespace(
            real_skins=True, steam_id="76561198000000000",
            inventory=[dict(id="ak-one", slot="ak47", def_=7, paint=302, wear=.15, seed=1),
                       dict(id="ak-two", slot="ak47", def_=7, paint=282, wear=.12, seed=2)],
            equipped_ct={}, equipped_t={"ak47": "ak-one"})
        for item in self.career.inventory:
            item["def"] = item.pop("def_")
        target = launch._plugin_live(self.game, "InventorySimulator") / "InventorySimulator.dll"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"fixture DLL; never run")
        for name in ("gamemode_competitive.cfg", "gamemode_competitive_offline.cfg",
                     "gamemode_casual.cfg", "gamemode_custom.cfg"):
            (self.game / "cfg" / name).write_text("bot_quota 10\nbot_quota_mode fill\n", encoding="utf-8")
        for context in (
            patch.object(launch, "settings", side_effect=lambda: dict(self.cfg)),
            patch.object(launch, "save_file", side_effect=lambda name: self.save / name),
            patch.object(launch, "cs2_is_live", return_value=False),
            patch.object(launch, "install_skins_plugin", return_value=0),
            patch.object(launch, "_copy_career_match", return_value=0),
            patch.object(launch, "_copy_botbuy_patch", return_value=0),
            patch.object(launch, "launch_cs2", side_effect=AssertionError("never launch CS2")),
        ):
            context.start()
            self.addCleanup(context.stop)

    def request(self):
        from test_v15_core import fake_team
        return launch.build_request(fake_team("A", 88), fake_team("B", 84), "A0", "de_dust2", "ct")

    def test_reentry_exports_current_equipment_without_copying_any_plugin(self):
        first = self.request()
        launch.prepare_game(self.game, self.mod, first, self.cfg, career=self.career)
        self.assertEqual("ready", first["skin_status"]["state"])
        path = (self.game / "addons/counterstrikesharp/configs/plugins/InventorySimulator/inventories.json")
        exported_first = json.loads(path.read_text("utf-8"))
        self.assertEqual(302, exported_first[self.career.steam_id]["tWeapons"]["7"]["paint"])
        self.career.equipped_t["ak47"] = "ak-two"
        second = self.request()
        launch.prepare_game(self.game, self.mod, second, self.cfg, career=self.career)
        exported_second = json.loads(path.read_text("utf-8"))
        self.assertEqual(282, exported_second[self.career.steam_id]["tWeapons"]["7"]["paint"])
        self.assertNotEqual(first["nonce"], second["nonce"])
        saved = json.loads((launch.plugin_dir(self.game) / "match_request.json").read_text("utf-8"))
        self.assertEqual(second["nonce"], saved["nonce"])
        self.assertEqual(9, len(saved["bots"]))
        for name in ("career_rules.cfg", "career_quick.cfg"):
            self.assertIn("bot_quota 9", (self.game / "cfg" / name).read_text("utf-8"))
        for name in ("gamemode_competitive.cfg", "gamemode_competitive_offline.cfg"):
            text = (self.game / "cfg" / name).read_text("utf-8")
            self.assertEqual(1, text.count("exec career_rules.cfg"))
        self.assertIs(self.career.real_skins, True)

    def test_repeat_preparation_repairs_a_valve_replaced_game_mode_cfg(self):
        launch.prepare_game(self.game, self.mod, self.request(), self.cfg, career=self.career)
        target = self.game / "cfg/gamemode_competitive_offline.cfg"
        target.write_text("bot_quota 10\nbot_quota_mode fill\n", encoding="utf-8")
        launch.prepare_game(self.game, self.mod, self.request(), self.cfg, career=self.career)
        self.assertEqual("bot_quota 0\nbot_quota_mode normal\nexec career_rules.cfg\n", target.read_text("utf-8"))

    def test_off_switch_is_preserved_and_never_exports_old_owned_items(self):
        self.career.real_skins = False
        before = deepcopy(self.career.__dict__)
        with patch.object(skins, "sync_live", side_effect=AssertionError("not consented")):
            state = launch._prepare_match_skins(self.game, self.career)
        self.assertEqual("disabled", state["state"])
        self.assertEqual(before, self.career.__dict__)

    def test_empty_or_stale_equipment_is_explained_not_filled_automatically(self):
        self.career.equipped_t = {"ak47": "no-longer-owned"}
        before = deepcopy(self.career.__dict__)
        state = launch._prepare_match_skins(self.game, self.career)
        self.assertEqual("not_equipped", state["state"])
        self.assertEqual(0, state["equipped_t"])
        self.assertIn("装备", state["reason"])
        self.assertEqual(before, self.career.__dict__)

    def test_diagnostics_do_not_disclose_account_id(self):
        state = launch.career_loadout_status(self.career, self.cfg)
        self.assertEqual(1, state["equipped_t"])
        self.assertNotIn(self.career.steam_id, json.dumps(state))
        self.career.steam_id = ""
        self.assertEqual("missing_account", launch.career_loadout_status(self.career, self.cfg)["state"])

    def test_external_source_does_not_export_or_inspect_career_inventory(self):
        self.cfg["skins_inventory_mode"] = "external"
        with patch.object(skins, "sync_live", side_effect=AssertionError("external is user owned")):
            self.assertEqual("external", launch._prepare_match_skins(self.game, self.career)["state"])

    def test_export_error_is_reported_not_silently_declared_ready(self):
        with patch.object(skins, "sync_live", return_value=None):
            state = launch._prepare_match_skins(self.game, self.career)
        self.assertEqual("unavailable", state["state"])
        self.assertIn("未同步", state["reason"])

    def test_partially_written_inventory_does_not_hide_a_wrong_owner(self):
        launch._prepare_match_skins(self.game, self.career)
        path = self.game / "addons/counterstrikesharp/configs/plugins/InventorySimulator/owner.txt"
        path.write_text("76561198000000001", encoding="ascii")
        with patch.object(skins, "sync_live", return_value=None):
            self.assertEqual("unavailable", launch._prepare_match_skins(self.game, self.career)["state"])

    def test_non_ascii_game_library_path_can_export_its_skin_cfg(self):
        alternate = self.root / "游戏库" / "game" / "csgo"
        target = launch._plugin_live(alternate, "InventorySimulator") / "InventorySimulator.dll"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"fixture DLL; never run")
        self.cfg["csgo_path"] = str(alternate)
        self.assertEqual("ready", launch._prepare_match_skins(alternate, self.career)["state"])
        self.assertIn("游戏库", (alternate / "cfg/invsim_career.cfg").read_text("utf-8"))

    def test_bot_compatibility_failure_remains_a_blocker(self):
        with patch.object(launch, "install_skins_plugin", side_effect=ValueError("BotRandomizer cohort changed")):
            with self.assertRaisesRegex(ValueError, "cohort changed"):
                launch._prepare_match_skins(self.game, self.career)


class DeactivateRequestTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cs2-retire-request-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.game = self.root / "game/csgo"
        self.target = launch.plugin_dir(self.game) / "match_request.json"
        self.target.parent.mkdir(parents=True)
        self.original = json.dumps(dict(active=True, nonce="fixture-old-nonce", map="de_dust2",
                                        bots=[dict(player_id="bot-1")])).encode()
        self.target.write_bytes(self.original)
        self.results = {}
        for relative in ("match_result.json", "match_result.best.json"):
            path = self.target.parent / relative
            path.write_bytes(b"preserve existing score")
            self.results[path] = path.read_bytes()
        inventory = self.game / "addons/counterstrikesharp/configs/plugins/InventorySimulator/inventories.json"
        inventory.parent.mkdir(parents=True)
        inventory.write_bytes(b"preserve user inventory")
        self.results[inventory] = inventory.read_bytes()
        closed = patch.object(launch, "cs2_is_live_strict", return_value=False)
        closed.start()
        self.addCleanup(closed.stop)

    def test_retires_only_active_matching_request_atomically_and_preserves_scores(self):
        self.assertTrue(launch.deactivate_match_request(self.game, "fixture-old-nonce"))
        result = json.loads(self.target.read_text("utf-8"))
        self.assertIs(result["active"], False)
        self.assertEqual("fixture-old-nonce", result["nonce"])
        self.assertEqual([dict(player_id="bot-1")], result["bots"])
        backups = list(self.target.parent.glob("match_request.retired-*.json"))
        self.assertEqual(1, len(backups))
        self.assertEqual(self.original, backups[0].read_bytes())
        self.assertFalse(list(self.target.parent.glob(".match-request-retire-*.tmp")))
        for path, expected in self.results.items():
            self.assertEqual(expected, path.read_bytes())
        self.assertFalse(launch.deactivate_match_request(self.game, "fixture-old-nonce"))
        self.assertEqual(1, len(list(self.target.parent.glob("match_request.retired-*.json"))))

    def test_missing_request_and_newer_nonce_are_noops(self):
        with patch.object(launch, "cs2_is_live_strict", side_effect=AssertionError("no writes needed")):
            self.assertFalse(launch.deactivate_match_request(self.game, "other-nonce"))
            self.assertEqual(self.original, self.target.read_bytes())
            self.target.unlink()
            self.assertFalse(launch.deactivate_match_request(self.game, "fixture-old-nonce"))

    def test_running_or_unknown_process_never_changes_request(self):
        for query in (True, None):
            with self.subTest(query=query), patch.object(launch, "cs2_is_live_strict", return_value=query):
                with self.assertRaises(ValueError):
                    launch.deactivate_match_request(self.game, "fixture-old-nonce")
            self.assertEqual(self.original, self.target.read_bytes())
        with patch.object(launch, "cs2_is_live_strict", side_effect=RuntimeError("cannot query")):
            with self.assertRaisesRegex(RuntimeError, "cannot query"):
                launch.deactivate_match_request(self.game, "fixture-old-nonce")

    def test_permission_error_keeps_active_request_and_cleans_temporary(self):
        with patch.object(launch.os, "replace", side_effect=PermissionError("fixture locked")):
            with self.assertRaisesRegex(PermissionError, "locked"):
                launch.deactivate_match_request(self.game, "fixture-old-nonce")
        self.assertEqual(self.original, self.target.read_bytes())
        self.assertFalse(list(self.target.parent.glob(".match-request-retire-*.tmp")))

    def test_process_starting_during_write_is_rechecked(self):
        with patch.object(launch, "cs2_is_live_strict", side_effect=[False, True]):
            with self.assertRaises(ValueError):
                launch.deactivate_match_request(self.game, "fixture-old-nonce")
        self.assertEqual(self.original, self.target.read_bytes())
        self.assertFalse(list(self.target.parent.glob(".match-request-retire-*.tmp")))


class ExistingSkinsOwnershipTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cs2-existing-skins-")
        self.addCleanup(temporary.cleanup)
        self.game = Path(temporary.name) / "game/csgo"
        self.cfg = dict(launch.DEFAULTS)
        self.career = SimpleNamespace(real_skins=True)
        self.dll = launch._plugin_live(self.game, "InventorySimulator") / "InventorySimulator.dll"
        self.dll.parent.mkdir(parents=True)
        self.dll.write_bytes(b"player plugin; never run")
        self.bridge = launch._plugin_live(self.game, "InvsimCareer") / "InvsimCareer.dll"
        self.bridge.parent.mkdir(parents=True)
        self.bridge.write_bytes(b"career bridge; never run")
        (self.game / "cfg").mkdir()
        self.cfg_file = self.game / "cfg/listenserver.cfg"
        self.cfg_file.write_text("exec invsim_career.cfg\nexec custom-user.cfg\n", encoding="utf-8")
        self.inventory = self.game / "addons/counterstrikesharp/configs/plugins/InventorySimulator/inventories.json"
        self.inventory.parent.mkdir(parents=True)
        self.inventory.write_bytes(b"owned inventory")
        gamedata = self.game / "addons/counterstrikesharp/gamedata/inventory-simulator.json"
        gamedata.parent.mkdir(parents=True)
        gamedata.write_bytes((launch.vendor_root() / "InventorySimulator/gamedata/inventory-simulator.json").read_bytes())
        for context in (patch.object(launch, "cs2_is_live", return_value=False),
                        patch.object(launch, "skins_gamedata_override", return_value=self.game.parent / "fixture-cache.json"),
                        patch.object(launch, "_copy_skins_into", side_effect=AssertionError("never install DLLs")),
                        patch.object(launch.urllib.request, "urlopen", side_effect=AssertionError("never download"))):
            context.start()
            self.addCleanup(context.stop)

    def test_enabled_reuses_plugin_without_copy_or_write(self):
        self.assertEqual(0, launch.prepare_existing_skins(self.game, self.career, self.cfg))
        self.assertEqual(b"player plugin; never run", self.dll.read_bytes())
        self.assertEqual(b"owned inventory", self.inventory.read_bytes())
        self.assertTrue(self.bridge.is_file())

    def test_off_parks_both_plugins_and_removes_only_our_hook(self):
        self.career.real_skins = False
        self.assertGreater(launch.prepare_existing_skins(self.game, self.career, self.cfg), 0)
        self.assertFalse(self.dll.exists())
        self.assertFalse(self.bridge.exists())
        self.assertEqual(b"player plugin; never run",
                         (launch._plugin_parked(self.game, "InventorySimulator") / self.dll.name).read_bytes())
        self.assertEqual("exec custom-user.cfg\n", self.cfg_file.read_text("utf-8"))
        self.assertEqual(b"owned inventory", self.inventory.read_bytes())
        self.assertIs(self.career.real_skins, False)

    def test_external_never_disables_user_plugin_for_either_career_toggle(self):
        self.cfg["skins_inventory_mode"] = "external"
        for enabled in (True, False):
            self.career.real_skins = enabled
            launch.prepare_existing_skins(self.game, self.career, self.cfg)
            self.assertEqual(b"player plugin; never run", self.dll.read_bytes())
            self.assertEqual(b"owned inventory", self.inventory.read_bytes())
        self.assertFalse(self.bridge.exists())
        self.assertEqual("exec custom-user.cfg\n", self.cfg_file.read_text("utf-8"))

    def test_external_does_not_require_or_download_optional_plugin(self):
        self.dll.unlink()
        self.cfg["skins_inventory_mode"] = "external"
        launch.prepare_existing_skins(self.game, self.career, self.cfg)
        self.assertFalse(self.dll.exists())
        self.assertEqual(b"owned inventory", self.inventory.read_bytes())

    def test_on_off_on_restores_local_copies_with_no_package_or_download(self):
        self.career.real_skins = False
        launch.prepare_existing_skins(self.game, self.career, self.cfg)
        self.career.real_skins = True
        self.assertGreater(launch.prepare_existing_skins(self.game, self.career, self.cfg), 0)
        self.assertEqual(b"player plugin; never run", self.dll.read_bytes())
        self.assertEqual(b"career bridge; never run", self.bridge.read_bytes())
        self.assertEqual(b"owned inventory", self.inventory.read_bytes())
        self.assertEqual(b"player plugin; never run",
                         (launch._plugin_parked(self.game, "InventorySimulator") / self.dll.name).read_bytes())

    def test_external_does_not_restore_a_disabled_career_plugin(self):
        self.career.real_skins = False
        launch.prepare_existing_skins(self.game, self.career, self.cfg)
        self.cfg["skins_inventory_mode"] = "external"
        self.career.real_skins = True
        launch.prepare_existing_skins(self.game, self.career, self.cfg)
        self.assertFalse(self.dll.exists())
        self.assertFalse(self.bridge.exists())
        self.assertEqual(b"owned inventory", self.inventory.read_bytes())

    def test_unmarked_modified_or_existing_live_plugin_is_not_overwritten(self):
        self.career.real_skins = False
        launch.prepare_existing_skins(self.game, self.career, self.cfg)
        parked = launch._plugin_parked(self.game, "InventorySimulator")
        (parked / self.dll.name).write_bytes(b"modified after retirement")
        self.career.real_skins = True
        with self.assertRaisesRegex(ValueError, "组件缺失"):
            launch.prepare_existing_skins(self.game, self.career, self.cfg)
        self.assertFalse(self.dll.exists())
        (parked / launch._SKIN_DISABLED_RECEIPT).unlink()
        with self.assertRaisesRegex(ValueError, "组件缺失"):
            launch.prepare_existing_skins(self.game, self.career, self.cfg)
        self.dll.parent.mkdir()
        self.dll.write_bytes(b"user newer live plugin")
        launch.prepare_existing_skins(self.game, self.career, self.cfg)
        self.assertEqual(b"user newer live plugin", self.dll.read_bytes())

    def test_newest_valid_local_retirement_wins_when_multiple_backups_exist(self):
        self.career.real_skins = False
        with patch.object(launch.time, "time_ns", return_value=100):
            launch.prepare_existing_skins(self.game, self.career, self.cfg)
        self.career.real_skins = True
        launch.prepare_existing_skins(self.game, self.career, self.cfg)
        self.dll.write_bytes(b"newer installed local DLL")
        self.career.real_skins = False
        with patch.object(launch.time, "time_ns", return_value=200):
            launch.prepare_existing_skins(self.game, self.career, self.cfg)
        self.career.real_skins = True
        launch.prepare_existing_skins(self.game, self.career, self.cfg)
        self.assertEqual(b"newer installed local DLL", self.dll.read_bytes())
        self.assertEqual(b"player plugin; never run",
                         (launch._plugin_parked(self.game, "InventorySimulator") / self.dll.name).read_bytes())

    def test_running_game_refuses_opt_out_without_touching_files(self):
        self.career.real_skins = False
        with patch.object(launch, "cs2_is_live", return_value=True):
            with self.assertRaises(ValueError):
                launch.prepare_existing_skins(self.game, self.career, self.cfg)
        self.assertTrue(self.dll.exists())
        self.assertTrue(self.bridge.exists())

    def test_existing_parked_plugin_is_preserved_and_failure_is_not_hidden(self):
        parked = launch._plugin_parked(self.game, "InventorySimulator") / self.dll.name
        parked.parent.mkdir(parents=True)
        parked.write_bytes(b"previous recoverable plugin")
        self.career.real_skins = False
        launch.prepare_existing_skins(self.game, self.career, self.cfg)
        self.assertEqual(b"previous recoverable plugin", parked.read_bytes())
        latest = list(parked.parent.parent.glob("InventorySimulator.career-disabled-*"))
        self.assertEqual(1, len(latest))
        self.assertEqual(b"player plugin; never run", (latest[0] / self.dll.name).read_bytes())
        self.dll.parent.mkdir(parents=True)
        self.dll.write_bytes(b"current plugin")
        with patch.object(launch.shutil, "move", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                launch.prepare_existing_skins(self.game, self.career, self.cfg)
        self.assertEqual(b"current plugin", self.dll.read_bytes())


if __name__ == "__main__":
    unittest.main()
