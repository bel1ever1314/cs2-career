"""Local signature selection and recoverable backups; no game is executed."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error

from cs2career.cs2 import launch


def gamedata(setter="AA ? CC"):
    def signature(pattern, library="server"):
        return {"signatures": {"library": library, "windows": pattern, "linux": "01 02"}}
    return {
        "CAttributeList::SetOrAddAttributeValueByName": signature(setter),
        "CCSPlayerInventory::GetItemInLoadout": signature("01 02 03"),
        "GetItemSchema": signature("05 06 07"),
        "CServerSideClientBase::ActivatePlayer": signature("09 0A 0B", "engine2"),
        "CCSPlayer_WeaponServices::DropWeapon": {"offsets": {"windows": 28, "linux": 29}},
    }


def blob(data):
    return json.dumps(data, sort_keys=True).encode()


class SkinGamedataCompatibilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="career-skin-gamedata-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.game = self.root / "game/csgo"
        self.vendor = self.root / "vendor"
        self.source = self.vendor / "InventorySimulator"
        self.bundle = self.source / "gamedata/inventory-simulator.json"
        self.cache = self.root / "save/skins_gamedata/inventory-simulator.json"
        self.installed = self.game / "addons/counterstrikesharp/gamedata/inventory-simulator.json"
        self.legacy = self.installed.with_name("inventory-simulator.previous.json")
        self.backups = self.game / "addons/counterstrikesharp/gamedata_backups/InventorySimulator"
        self.good = blob(gamedata())
        self.old = blob(gamedata("EE FF EE"))
        self.write(self.bundle, self.good)
        self.server = self.game / "bin/win64/server.dll"
        self.engine = self.game.parent / "bin/win64/engine2.dll"
        self.write(self.server, b"header\xAA\xBB\xCC\x00\x01\x02\x03\x00\x05\x06\x07\x00\xAAfooter")
        self.write(self.engine, b"header\x09\x0A\x0Bfooter")
        self.cfg = dict(launch.DEFAULTS, csgo_path=str(self.game))
        for context in (
            patch.object(launch, "settings", side_effect=lambda: dict(self.cfg)),
            patch.object(launch, "vendor_root", return_value=self.vendor),
            patch.object(launch, "skins_gamedata_override", return_value=self.cache),
            patch.object(launch, "require_cs2_closed"),
            patch.object(launch, "cs2_is_live", return_value=False),
            patch.object(launch.sys, "platform", "win32"),
        ):
            context.start()
            self.addCleanup(context.stop)
        launch._skin_signature_count.cache_clear()
        self.addCleanup(launch._skin_signature_count.cache_clear)

    def write(self, path, contents):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)

    def install(self):
        return launch._install_skin_gamedata(self.game, self.source, self.cfg)

    def backup_files(self):
        return list(self.backups.glob("*.bak"))

    def test_stale_cache_falls_back_to_bundle_offline_and_preserves_inventory(self):
        self.write(self.cache, self.old)
        self.write(self.installed, self.old)
        self.write(self.legacy, self.old)
        inventory = self.game / "addons/counterstrikesharp/configs/plugins/InventorySimulator/inventories.json"
        self.write(inventory, b"private inventory remains byte-identical")
        with patch.object(launch.urllib.request, "urlopen", side_effect=AssertionError("no download")):
            self.assertEqual(2, self.install())
        self.assertEqual(self.good, self.installed.read_bytes())
        self.assertEqual(self.old, self.cache.read_bytes())
        self.assertEqual(b"private inventory remains byte-identical", inventory.read_bytes())
        self.assertFalse(self.legacy.exists())
        self.assertEqual(2, len(self.backup_files()))
        self.assertTrue(all(path.read_bytes() == self.old for path in self.backup_files()))
        self.assertEqual([self.installed], list(self.installed.parent.glob("*.json")))

    def test_unchanged_install_and_repeat_prepare_still_retire_legacy_backup(self):
        self.write(self.installed, self.good)
        self.write(self.legacy, self.old)
        plugin = self.game / "addons/counterstrikesharp/plugins/InventorySimulator/InventorySimulator.dll"
        self.write(plugin, b"existing plugin; never run")
        career = SimpleNamespace(real_skins=True)
        self.assertEqual(1, launch.prepare_existing_skins(self.game, career, self.cfg))
        self.assertFalse(self.legacy.exists())
        self.assertEqual(self.old, self.backup_files()[0].read_bytes())
        with patch.object(launch.shutil, "copy2", side_effect=AssertionError("unchanged files")):
            self.assertEqual(0, launch.prepare_existing_skins(self.game, career, self.cfg))
        self.assertEqual(self.good, self.installed.read_bytes())
        self.assertEqual(b"existing plugin; never run", plugin.read_bytes())
        self.assertIs(career.real_skins, True)

    def test_plugin_install_retires_duplicate_even_when_main_signature_is_unchanged(self):
        plugin = self.source / "plugins/InventorySimulator/InventorySimulator.dll"
        self.write(plugin, b"fixture plugin; never run")
        self.write(self.installed, self.good)
        self.write(self.legacy, self.old)
        self.assertEqual(2, launch._copy_skins_into(self.game))
        self.assertEqual(self.good, self.installed.read_bytes())
        self.assertFalse(self.legacy.exists())
        live = self.game / "addons/counterstrikesharp/plugins/InventorySimulator/InventorySimulator.dll"
        self.assertEqual(plugin.read_bytes(), live.read_bytes())
        self.assertEqual(self.old, self.backup_files()[0].read_bytes())

    def test_cache_is_used_only_when_its_signatures_match_all_game_binaries(self):
        cache_data = gamedata()
        cache_data["CCSPlayer_WeaponServices::DropWeapon"]["offsets"]["linux"] = 30
        self.write(self.cache, blob(cache_data))
        self.assertEqual(self.cache, launch._skins_gamedata(self.source, self.game))
        cache_data["CServerSideClientBase::ActivatePlayer"]["signatures"]["windows"] = "EE EE"
        self.write(self.cache, blob(cache_data))
        self.assertEqual(self.bundle, launch._skins_gamedata(self.source, self.game))

    def test_ambiguous_signature_is_rejected_and_overlapping_matches_count(self):
        self.write(self.cache, blob(gamedata("AA")))
        self.assertEqual(self.bundle, launch._skins_gamedata(self.source, self.game))
        self.write(self.server, b"\xAA\xAA\xAA")
        info = self.server.stat()
        self.assertEqual(2, launch._skin_signature_count(str(self.server), info.st_size,
                                                       info.st_mtime_ns, "AA AA"))

    def test_changed_binary_invalidates_cached_scan_and_rejects_before_any_write(self):
        self.write(self.installed, self.old)
        self.write(self.legacy, self.old)
        self.assertEqual(self.bundle, launch._skins_gamedata(self.source, self.game))
        self.write(self.server, b"changed game; no compatible signatures")
        with self.assertRaisesRegex(ValueError, "不兼容"):
            self.install()
        self.assertEqual(self.old, self.installed.read_bytes())
        self.assertEqual(self.old, self.legacy.read_bytes())
        self.assertFalse(self.backups.exists())

    def test_repeated_selection_reuses_scans_and_missing_engine_is_not_skipped(self):
        launch._skins_gamedata(self.source, self.game)
        first = launch._skin_signature_count.cache_info()
        launch._skins_gamedata(self.source, self.game)
        second = launch._skin_signature_count.cache_info()
        self.assertEqual(first.misses, second.misses)
        self.assertGreater(second.hits, first.hits)
        self.engine.unlink()
        with self.assertRaisesRegex(ValueError, "缺少对应游戏组件"):
            self.install()

    def test_atomic_replace_failure_preserves_main_and_legacy_files(self):
        self.write(self.installed, self.old)
        self.write(self.legacy, self.old)
        with patch.object(launch.os, "replace", side_effect=PermissionError("fixture locked")):
            with self.assertRaises(PermissionError):
                self.install()
        self.assertEqual(self.old, self.installed.read_bytes())
        self.assertEqual(self.old, self.legacy.read_bytes())
        self.assertFalse(list(self.installed.parent.glob("*.tmp")))
        self.assertEqual(self.old, self.backup_files()[0].read_bytes())

    def test_retirement_failure_keeps_original_and_a_verified_recovery_copy(self):
        self.write(self.installed, self.good)
        self.write(self.legacy, self.old)
        with patch.object(launch.os, "replace", side_effect=PermissionError("fixture locked")):
            with self.assertRaises(PermissionError):
                self.install()
        self.assertEqual(self.good, self.installed.read_bytes())
        self.assertEqual(self.old, self.legacy.read_bytes())
        self.assertEqual(self.old, self.backup_files()[0].read_bytes())

    def test_external_mode_never_scans_downloads_or_moves_gamedata(self):
        self.cfg["skins_inventory_mode"] = "external"
        self.write(self.installed, self.old)
        self.write(self.legacy, self.old)
        with patch.object(launch, "_check_skin_signatures", side_effect=AssertionError("external")), \
             patch.object(launch.urllib.request, "urlopen", side_effect=AssertionError("external")):
            self.assertEqual(0, self.install())
            self.assertEqual(0, launch._copy_skins_into(self.game))
            self.assertEqual("external", launch.update_skins_gamedata()["status"])
        self.assertEqual(self.old, self.installed.read_bytes())
        self.assertEqual(self.old, self.legacy.read_bytes())
        self.assertFalse(self.cache.exists())
        self.assertFalse(self.backups.exists())

    def test_off_preparation_retires_duplicate_without_enabling_or_installing(self):
        self.write(self.installed, self.old)
        self.write(self.legacy, self.old)
        career = SimpleNamespace(real_skins=False)
        before = deepcopy(career.__dict__)
        with patch.object(launch, "_check_skin_signatures", side_effect=AssertionError("not enabled")):
            self.assertGreater(launch.prepare_existing_skins(self.game, career, self.cfg), 0)
        self.assertEqual(before, career.__dict__)
        self.assertEqual(self.old, self.installed.read_bytes())
        self.assertFalse(self.legacy.exists())

    def test_explicit_update_offline_fallback_and_unchanged_update_retire_backup(self):
        self.write(self.cache, self.old)
        self.write(self.installed, self.old)
        self.write(self.legacy, self.old)
        with patch.object(launch.urllib.request, "urlopen", side_effect=urllib.error.URLError("offline")):
            result = launch.update_skins_gamedata()
        self.assertTrue(result["ok"])
        self.assertEqual("offline_fallback", result["status"])
        self.assertEqual(self.good, self.installed.read_bytes())
        self.assertFalse(self.legacy.exists())
        self.write(self.cache, self.good)
        self.write(self.legacy, self.old)
        with patch.object(launch.urllib.request, "urlopen") as download:
            download.return_value.__enter__.return_value.read.return_value = self.good
            self.assertTrue(launch.update_skins_gamedata()["ok"])
        self.assertFalse(self.legacy.exists())
        self.assertEqual(self.good, self.installed.read_bytes())

    def test_status_reports_verified_selection_without_cold_scans(self):
        self.write(self.cache, self.old)
        self.install()
        with patch.object(launch, "_check_skin_signatures", side_effect=AssertionError("status must not scan")), \
             patch.object(launch, "_skin_signature_count", side_effect=AssertionError("status must not scan")):
            state = launch.gamedata_status(self.game)
        self.assertTrue(state["selection_verified"])
        self.assertTrue(state["cached_rejected"])
        self.assertEqual("bundled", state["selected_source"])
        self.assertFalse(state["pending_install"])
        self.assertFalse(state["cache_needs_check"])
        self.write(self.installed, self.old)
        self.assertTrue(launch.gamedata_status(self.game)["pending_install"])
        self.write(self.server, b"updated binary")
        with patch.object(launch, "_check_skin_signatures", side_effect=AssertionError("status must not scan")):
            state = launch.gamedata_status(self.game)
        self.assertFalse(state["selection_verified"])
        self.assertFalse(state["pending_install"])
        self.assertTrue(state["cache_needs_check"])

    def test_status_invalidates_receipt_on_cache_or_bundle_changes(self):
        self.write(self.cache, self.old)
        self.install()
        self.write(self.cache, self.good)
        with patch.object(launch, "_check_skin_signatures", side_effect=AssertionError("status must not scan")):
            self.assertFalse(launch.gamedata_status(self.game)["selection_verified"])
        self.write(self.cache, self.old)
        newer = gamedata()
        newer["CCSPlayer_WeaponServices::DropWeapon"]["offsets"]["linux"] += 1
        self.write(self.bundle, blob(newer))
        self.assertFalse(launch.gamedata_status(self.game)["selection_verified"])

    def test_external_status_never_reads_or_writes_selection_receipt(self):
        self.write(self.cache, self.old)
        self.write(self.installed, self.good)
        self.cfg["skins_inventory_mode"] = "external"
        with patch.object(launch, "_skin_selection_receipt", side_effect=AssertionError("external")):
            state = launch.gamedata_status(self.game)
        self.assertEqual("external", state["selected_source"])
        self.assertFalse(state["pending_install"])
        self.assertFalse(self.backups.exists())

    def test_diagnostic_hash_failure_does_not_block_a_valid_install(self):
        self.write(self.cache, self.old)
        original = launch._sha256

        def digest(path):
            if path == self.cache:
                raise PermissionError("unreadable diagnostic cache")
            return original(path)

        with patch.object(launch, "_sha256", side_effect=digest):
            self.assertEqual(1, self.install())
            state = launch.gamedata_status(self.game)
        self.assertEqual(self.good, self.installed.read_bytes())
        self.assertFalse(state["selection_verified"])
        self.assertIn("error", state["cached"])

    def install_mod_fixture(self):
        mod = self.root / "mod"
        for relative in ("addons/metamod", "addons/counterstrikesharp", "addons/BotHider", "overrides"):
            (mod / relative).mkdir(parents=True, exist_ok=True)
        self.write(self.game / "steam.inf", b"fixture")
        self.write(self.game / "gameinfo.gi", b'"GameInfo" { "FileSystem" { "SearchPaths" { Game csgo } } }')
        source_previous = mod / "addons/counterstrikesharp/gamedata/inventory-simulator.previous.json"
        self.write(source_previous, b"source legacy backup must not be copied")
        self.write(self.installed, self.good)
        self.write(self.legacy, self.old)
        with patch.object(launch, "ensure_gameinfo_mounts"), \
             patch.object(launch, "_copy_career_match", return_value=0), \
             patch.object(launch, "_deploy_tactical_playbook", return_value=0), \
             patch.object(launch, "_copy_botbuy_patch", return_value=0), \
             patch.object(launch, "apply_bothider_config"):
            self.assertTrue(launch.install_mod(self.game, mod)["ok"])
        self.assertEqual(b"source legacy backup must not be copied", source_previous.read_bytes())
        self.assertEqual(self.good, self.installed.read_bytes())

    def test_install_mod_skips_source_legacy_and_retires_installed_legacy(self):
        self.install_mod_fixture()
        self.assertFalse(self.legacy.exists())
        self.assertEqual(self.old, self.backup_files()[0].read_bytes())

    def test_install_mod_external_preserves_installed_legacy_and_source(self):
        self.cfg["skins_inventory_mode"] = "external"
        self.install_mod_fixture()
        self.assertEqual(self.old, self.legacy.read_bytes())
        self.assertFalse(self.backups.exists())


if __name__ == "__main__":
    unittest.main()
