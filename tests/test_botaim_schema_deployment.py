"""Deploy the schema-aware aim adapter into disposable trees only."""
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cs2career.cs2 import launch


class AimSchemaDeploymentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="aim-schema-deployment-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.csgo = self.root / "game/csgo"
        self.csgo.mkdir(parents=True)
        (self.csgo / "gameinfo.gi").write_text(
            '"GameInfo" { "FileSystem" { "SearchPaths" { Game csgo } } }', encoding="utf-8")
        self.vendor = self.root / "vendor"
        self.source = self.vendor / "BotAimImprover"
        self.source.mkdir(parents=True)
        (self.source / "BotAimImprover.dll").write_bytes(b"MZ schema-aware fixture; never executed")
        (self.source / "BotAimImprover.deps.json").write_text("{}", encoding="utf-8")
        self.target = launch._plugin_live(self.csgo, "BotAimImprover")
        for context in (patch.object(launch, "vendor_root", return_value=self.vendor),
                        patch.object(launch, "cs2_is_live", return_value=False)):
            context.start()
            self.addCleanup(context.stop)

    def test_install_and_refresh_preserve_config_backup_and_unchanged_files(self):
        self.target.mkdir(parents=True)
        old = self.target / "BotAimImprover.dll"
        old.write_bytes(b"old fixed-offset adapter")
        config = self.csgo / "addons/counterstrikesharp/configs/plugins/BotAimImprover/config.json"
        config.parent.mkdir(parents=True)
        config.write_bytes(b'{"custom aim":"keep"}')
        self.assertEqual(2, launch._copy_aim_schema_patch(self.csgo))
        self.assertEqual(b"old fixed-offset adapter", old.with_name(old.name + ".career-backup").read_bytes())
        timestamps = [path.stat().st_mtime_ns for path in self.target.iterdir()]
        self.assertEqual(0, launch._copy_aim_schema_patch(self.csgo))
        self.assertEqual(timestamps, [path.stat().st_mtime_ns for path in self.target.iterdir()])
        self.assertEqual(b'{"custom aim":"keep"}', config.read_bytes())
        self.assertEqual((self.source / old.name).read_bytes(), old.read_bytes())

    def test_missing_binary_or_deps_is_an_error_before_destination_creation(self):
        for name in ("BotAimImprover.dll", "BotAimImprover.deps.json"):
            with self.subTest(file=name):
                path = self.source / name
                original = path.read_bytes()
                path.unlink()
                with self.assertRaisesRegex(FileNotFoundError, "BotAimImprover 插件缺少"):
                    launch._copy_aim_schema_patch(self.csgo)
                self.assertFalse(self.target.exists())
                path.write_bytes(original)

    def test_locked_copy_is_not_reported_as_success(self):
        with patch.object(launch.os, "replace", side_effect=PermissionError("locked aim")):
            with self.assertRaisesRegex(PermissionError, "locked aim"):
                launch._copy_aim_schema_patch(self.csgo)
        self.assertFalse((self.target / "BotAimImprover.dll").exists())
        self.assertFalse(list(self.target.glob("*.tmp")))

    def test_running_game_never_copies(self):
        with patch.object(launch, "cs2_is_live", return_value=True):
            with self.assertRaisesRegex(ValueError, "退出 CS2"):
                launch._copy_aim_schema_patch(self.csgo)
        self.assertFalse(self.target.exists())

    def test_full_installer_overlays_schema_patch_after_old_upstream_copy(self):
        mod = self.root / "mod"
        for relative in ("addons/metamod", "addons/counterstrikesharp", "overrides"):
            (mod / relative).mkdir(parents=True)
        upstream = mod / "addons/counterstrikesharp/plugins/BotAimImprover"
        upstream.mkdir(parents=True)
        (upstream / "BotAimImprover.dll").write_bytes(b"upstream old constant")
        (upstream / "BotAimImprover.deps.json").write_text("{}", encoding="utf-8")
        with ExitStack() as stack:
            for name in ("_copy_career_match", "_deploy_tactical_playbook", "_copy_botbuy_patch"):
                stack.enter_context(patch.object(launch, name, return_value=0))
            stack.enter_context(patch.object(launch, "hook_competitive_cfg"))
            stack.enter_context(patch.object(launch, "apply_bothider_config"))
            out = launch.install_mod(self.csgo, mod, config=dict(launch.DEFAULTS))
        self.assertTrue(out["ok"])
        self.assertEqual((self.source / "BotAimImprover.dll").read_bytes(),
                         (self.target / "BotAimImprover.dll").read_bytes())
        self.assertEqual(b"upstream old constant",
                         (self.target / "BotAimImprover.dll.career-backup").read_bytes())

    def test_career_cfg_pins_previous_botstate_fov_without_changing_aim_preference(self):
        match = {"ct": {"name": "A", "logo": "", "players": [1] * 4},
                 "t": {"name": "B", "logo": "", "players": [1] * 5}}
        for aim in ("head", "mixed", "body"):
            with self.subTest(aim=aim):
                launch.write_career_cfg(self.csgo, match, dict(launch.DEFAULTS, bot_aim=aim))
                for name in ("career_rules.cfg", "career_quick.cfg"):
                    lines = (self.csgo / "cfg" / name).read_text("utf-8").splitlines()
                    self.assertEqual(1, lines.count("css_bot_fov 120 180"))
                    self.assertIn("bot_aim " + aim, lines)
                    self.assertIn("bot_nades normal", lines)


if __name__ == "__main__":
    unittest.main()
