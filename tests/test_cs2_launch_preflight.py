"""Incomplete Steam updates must not mutate mounts or dispatch a game."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from cs2career.cs2 import launch
from cs2career.cs2.preflight import require_installation_files


class LaunchPreflightTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cs2-launch-preflight-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.csgo = self.root / "game/csgo"
        self.csgo.mkdir(parents=True)
        (self.csgo / "gameinfo.gi").write_bytes(b"existing mounts; do not modify")
        self.required = (
            self.csgo / "steam.inf",
            self.csgo / "bin/win64/server.dll",
            self.root / "game/bin/win64/cs2.exe",
        )

    def complete_installation(self):
        for path in self.required:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture only; never executed")

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def test_reports_each_missing_file_and_action_without_writes(self):
        self.complete_installation()
        for target in self.required:
            with self.subTest(file=target.name):
                target.unlink()
                before = self.snapshot()
                with self.assertRaises(FileNotFoundError) as raised:
                    require_installation_files(self.csgo)
                message = str(raised.exception)
                for expected in (target.name, "Steam", "更新／下载", "验证游戏文件的完整性"):
                    self.assertIn(expected, message)
                self.assertEqual(before, self.snapshot())
                target.write_bytes(b"fixture only; never executed")

    def test_directory_in_place_of_binary_does_not_pass(self):
        self.complete_installation()
        self.required[-1].unlink()
        self.required[-1].mkdir()
        with self.assertRaisesRegex(FileNotFoundError, "cs2.exe"):
            require_installation_files(self.csgo)

    def test_complete_files_are_accepted_despite_stale_steam_manifest(self):
        self.complete_installation()
        (self.root / "appmanifest_730.acf").write_text(
            '"AppState" { "StateFlags" "1542" "buildid" "1" "TargetBuildID" "2" }',
            encoding="utf-8")
        before = self.snapshot()
        require_installation_files(self.csgo)
        self.assertEqual(before, self.snapshot())

    def test_incomplete_install_stops_before_any_launch_mutation(self):
        steam = self.root / "steam.exe"
        steam.write_bytes(b"fixture only; never executed")
        cfg = dict(launch.DEFAULTS, steam_exe=str(steam), csgo_path=str(self.csgo))
        request = {"nonce": "existing-unfinished-match", "map": "de_dust2"}
        original_request = deepcopy(request)
        before = self.snapshot()
        with ExitStack() as stack:
            calls = [stack.enter_context(patch.object(launch, name)) for name in (
                "build_request", "_arm_cs2_environment", "prepare_game", "launch_cs2",
                "_spawn_cs2_environment_watch", "_finish_cs2_environment",
            )]
            dispatch = stack.enter_context(patch("subprocess.Popen"))
            before_dispatch = Mock()
            with self.assertRaisesRegex(FileNotFoundError, "CS2 安装文件不完整"):
                launch.start_match({}, {}, "Player", "de_dust2", "ct", config=cfg,
                                   request_override=request, before_dispatch=before_dispatch)
            for call in calls + [dispatch, before_dispatch]:
                call.assert_not_called()
        self.assertEqual(original_request, request)
        self.assertEqual(before, self.snapshot())

    def test_supported_game_root_is_resolved_before_preflight(self):
        self.complete_installation()
        steam = self.root / "steam.exe"
        steam.write_bytes(b"fixture only; never executed")
        for supplied_path in (self.root, self.root / "game", self.csgo):
            with self.subTest(path=supplied_path):
                cfg = dict(launch.DEFAULTS, steam_exe=str(steam), csgo_path=str(supplied_path))
                with patch.object(launch, "_arm_cs2_environment", side_effect=RuntimeError("test stop")) as arm:
                    with self.assertRaisesRegex(RuntimeError, "test stop"):
                        launch.start_match({}, {}, "Player", "de_dust2", "ct", config=cfg,
                                           request_override={})
                arm.assert_called_once_with(self.csgo)


if __name__ == "__main__":
    unittest.main()
