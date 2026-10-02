"""Public source staging must reject leaks and never publish partial output."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("career3d_package_sources", Path(__file__).parents[1] / "tools/career3d_package_sources.py")
pkg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pkg)


class Career3DSourcePackageTests(unittest.TestCase):
    def fixture(self, base):
        root, assets, fonts = base / "source", base / "original-assets", base / "fonts"
        paths = {
            "LICENSE": "original license\n", "cs2career/__init__.py": "__version__ = '1.6.0'\n",
            "tools/career3d_service.py": "# public backend\n", "tools/career3d_start.py": "# public start\n",
            "tools/run_tests.py": "# public test runner\n", "docs/skin-tools-interface.zh-CN.txt": "public protocol\n",
            "licenses/runtime/Python.txt": "original runtime license\n",
            "tests/test_fixture.py": "# public test\n", "extensions/_templates/story/manifest.json": "{}\n",
            pkg.PROJECT + "/project.godot": "config_version=5\n",
            pkg.PROJECT + "/scripts/example.gd": "extends Node\n",
            pkg.PROJECT + "/scripts/example.gd.uid": "uid://fixture\n",
            pkg.PROJECT + "/bedroom.tscn": '[gd_scene format=3]\n',
            pkg.PROJECT + "/source/.gdignore": "\n",
            pkg.PROJECT + "/data/career_link.json": json.dumps({"schema_version": 1, "python": "C:" + "/Users/PrivateDeveloper/python.exe", "repo_root": "C:" + "/Users/PrivateDeveloper/source", "data_dir": "runtime/career", "start_hour": 8}),
            pkg.PROJECT + "/data/ui_style.json": json.dumps({"schema_version": 1, "font_file": "res://fonts/ChillRoundF.ttf", "development_cache": "E:/private-cache/font.ttf"}),
            pkg.PROJECT + "/data/media.json": json.dumps({"schema_version": 1, "team_manifest": "E:/private-media/teams.json", "skin_cache_roots": ["D:/private/save/skin_art"], "map_backgrounds": {"de_dust2": {"kind": "loading_art", "path": "E:/private-media/de_dust2.png", "source": "installed CS2"}}}),
            pkg.PROJECT + "/启动样板.cmd": "@echo off\nrem machine launcher\n",
            pkg.PROJECT + "/rts/scripts/game.gd": "extends Control\n",
            pkg.PROJECT + "/rts/data/map_catalog.json": "{}\n",
            pkg.RTS_PROJECT + "/project.godot": "config_version=5\n",
            pkg.RTS_PROJECT + "/scripts/game.gd": "extends Control\n",
            pkg.RTS_PROJECT + "/tools/build_map.py": "# exporter\n",
            "vendor/CareerMatch/CareerMatch.cs": "// plugin source\n",
        }
        for relative, text in paths.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        assets.mkdir()
        for name in pkg.MODEL_NAMES:
            (assets / name).write_bytes(struct.pack("<4sII", b"glTF", 2, 12))
        fonts.mkdir()
        hashes = {}
        for name, content in (("ChillRoundF.ttf", b"fixture font"), ("OFL.txt", b"fixture original license")):
            (fonts / name).write_bytes(content)
            hashes[name] = hashlib.sha256(content).hexdigest()
        return root, assets, fonts, hashes

    def stage(self, root, output, assets, fonts, hashes, **kwargs):
        with patch.object(pkg, "FONT_HASHES", hashes):
            return pkg.stage_sources(root, output, assets, fonts, include_external_authoring=False, **kwargs)

    def test_current_projects_and_backend_with_private_outputs_excluded(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root, assets, fonts, hashes = self.fixture(base)
            excluded = (
                "save/career.json", "extensions/private/story.json", "tools/tests-output/report.json",
                "tools/tests-output/data/.career3d-demo.json", "tools/view_angle_lab/private.py",
                "vendor/CareerMatch/bin/generated.json", "vendor/OtherPlugin/not-allowlisted.cs",
                pkg.PROJECT + "/runtime/career/save/career.json", pkg.PROJECT + "/source-snapshots/old.py",
                pkg.PROJECT + "/.godot/editor/private.json", pkg.PROJECT + "/scripts/example.gd.import",
                pkg.PROJECT + "/temp/report.json", pkg.PROJECT + "/data/owner.txt",
                pkg.RTS_PROJECT + "/runtime/reports/real-match.json", pkg.RTS_PROJECT + "/tools/nav_export/obj/private.json",
                "cs2career/data/natural_behavior/private.json",
            )
            for relative in excluded:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("private artifact", encoding="utf-8")
            permitted_dll = root / "vendor/CareerMatch/CareerMatch.dll"
            permitted_dll.write_bytes(b"MZ public plugin")
            (permitted_dll.parent / "Unapproved.dll").write_bytes(b"MZ private plugin")
            (root / pkg.RTS_PROJECT / "assets").mkdir()
            (root / pkg.RTS_PROJECT / "assets/radar.png").write_bytes(b"PNG public radar")
            output = base / "public-stage"
            report = self.stage(root, output, assets, fonts, hashes)
            for relative in excluded:
                self.assertFalse((output / relative).exists(), relative)
            self.assertTrue((output / "tools/career3d_service.py").is_file())
            self.assertTrue((output / "docs/skin-tools-interface.zh-CN.txt").is_file())
            self.assertTrue((output / "licenses/runtime/Python.txt").is_file())
            self.assertTrue((output / pkg.PROJECT / "scripts/example.gd.uid").is_file())
            self.assertTrue((output / pkg.PROJECT / "source/.gdignore").is_file())
            self.assertTrue((output / pkg.RTS_PROJECT / "tools/build_map.py").is_file())
            self.assertTrue((output / pkg.PROJECT / "rts/scripts/game.gd").is_file())
            self.assertTrue((output / "vendor/CareerMatch/CareerMatch.dll").is_file())
            self.assertFalse((output / "vendor/CareerMatch/Unapproved.dll").exists())
            config = json.loads((output / pkg.PROJECT / "data/career_link.json").read_text("utf-8"))
            self.assertEqual((config["python"], config["repo_root"], config["data_dir"]), ("python", "../..", "runtime/career"))
            media = json.loads((output / pkg.PROJECT / "data/media.json").read_text("utf-8"))
            self.assertEqual(media["team_manifest"], "../../../media/teams/team-media.json")
            self.assertEqual(media["map_backgrounds"]["de_dust2"]["path"], "../../../media/maps/de_dust2.png")
            self.assertIn("CS2CAREER_GODOT", (output / pkg.PROJECT / "启动样板.cmd").read_text("utf-8"))
            original = (root / pkg.PROJECT / "data/career_link.json").read_text("utf-8")
            self.assertIn("PrivateDeveloper", original)
            self.assertEqual(report["source_files"], len(report["files"]))
            for relative, digest in report["files"].items():
                self.assertEqual(pkg.file_hash(output / relative), digest)
            with self.assertRaises(FileExistsError):
                self.stage(root, output, assets, fonts, hashes)

    def test_repeated_stages_have_identical_hashes_and_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root, assets, fonts, hashes = self.fixture(base)
            first, second = base / "one", base / "two"
            self.stage(root, first, assets, fonts, hashes)
            self.stage(root, second, assets, fonts, hashes)
            self.assertEqual((first / "SOURCE_STAGE_MANIFEST.json").read_bytes(), (second / "SOURCE_STAGE_MANIFEST.json").read_bytes())

    def test_private_home_text_is_scrubbed_only_in_the_stage(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root, assets, fonts, hashes = self.fixture(base)
            source = root / "docs/private-path-example.md"
            source.write_text("C:" + r"\Users\PrivateDeveloper\source and C:" + r"\\Users\\SecondDeveloper\\source", encoding="utf-8")
            original = source.read_bytes()
            output = base / "stage"
            report = self.stage(root, output, assets, fonts, hashes)
            cleaned = (output / "docs/private-path-example.md").read_text("utf-8")
            self.assertNotIn("PrivateDeveloper", cleaned)
            self.assertNotIn("SecondDeveloper", cleaned)
            self.assertIn("Public", cleaned)
            self.assertEqual(source.read_bytes(), original)
            self.assertTrue(any(row["path"] == "docs/private-path-example.md" and row["count"] == 2 for row in report["transforms"]))

    def test_credential_and_binary_private_path_fail_without_partial_stage(self):
        for mode in ("credential", "binary"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                base = Path(folder)
                root, assets, fonts, hashes = self.fixture(base)
                if mode == "credential":
                    (root / "docs/secret.md").write_text("ghp_" + "a" * 30, encoding="utf-8")
                else:
                    (root / "vendor/CareerMatch/CareerMatch.dll").write_bytes(b"MZ\0C:" + b"/Users" + b"/PrivateDeveloper/debug.pdb\0")
                output = base / "stage"
                with self.assertRaises(ValueError):
                    self.stage(root, output, assets, fonts, hashes)
                self.assertFalse(output.exists())
                self.assertFalse(list(base.glob(".sources-*")))

    def test_pinned_font_and_complete_models_are_required(self):
        for mode in ("font", "missing-model", "invalid-model"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                base = Path(folder)
                root, assets, fonts, hashes = self.fixture(base)
                if mode == "font":
                    (fonts / "ChillRoundF.ttf").write_bytes(b"unverified font")
                elif mode == "missing-model":
                    (assets / pkg.MODEL_NAMES[0]).unlink()
                else:
                    (assets / pkg.MODEL_NAMES[0]).write_bytes(b"not a model")
                with self.assertRaises(ValueError):
                    self.stage(root, base / "stage", assets, fonts, hashes)
                self.assertFalse((base / "stage").exists())

    def test_links_and_unsafe_extra_targets_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root, assets, fonts, hashes = self.fixture(base)
            external = base / "outside.py"
            external.write_text("# public external source\n", encoding="utf-8")
            for relative in ("../escape.py", "/absolute.py", "tools/tests-output/leak.py", "tools/private.dll", "save/private.py"):
                with self.subTest(target=relative), self.assertRaises(ValueError):
                    self.stage(root, base / "stage", assets, fonts, hashes, extra_sources={relative: external})
            disguised_dll = base / "not-public.dll"
            disguised_dll.write_bytes(b"MZ private DLL")
            with self.assertRaises(ValueError):
                self.stage(root, base / "stage", assets, fonts, hashes, extra_sources={"tools/looks_like_source.py": disguised_dll})
            with self.assertRaises(ValueError):
                self.stage(root, root / "public", assets, fonts, hashes)
            link = root / "docs/linked.py"
            try:
                link.symlink_to(external)
            except (OSError, NotImplementedError):
                # Windows without symlink privileges still exercises the same
                # rejection branch; platforms with privileges use a real link.
                link.write_text("# linked file fixture\n", encoding="utf-8")
                original_link_check = pkg._is_link
                with patch.object(pkg, "_is_link", side_effect=lambda p: Path(p) == link or original_link_check(Path(p))):
                    with self.assertRaises(ValueError):
                        self.stage(root, base / "stage", assets, fonts, hashes)
                return
            with self.assertRaises(ValueError):
                self.stage(root, base / "stage", assets, fonts, hashes)

    def test_explicit_external_authoring_source_is_copied_and_not_recursed(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root, assets, fonts, hashes = self.fixture(base)
            external_dir = base / "authoring"
            external_dir.mkdir()
            external = external_dir / "build_chicken.py"
            external.write_text("# original authoring\n", encoding="utf-8")
            (external_dir / "private.json").write_text("private data", encoding="utf-8")
            output = base / "stage"
            relative = pkg.PROJECT + "/source/build_chicken.py"
            self.stage(root, output, assets, fonts, hashes, extra_sources={relative: external})
            self.assertEqual((output / relative).read_text("utf-8"), external.read_text("utf-8"))
            self.assertFalse((output / pkg.PROJECT / "source/private.json").exists())

    def test_windows_long_recovered_source_paths_can_be_staged(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            root, assets, fonts, hashes = self.fixture(base)
            output = base / ("release-" + "a" * 75) / ("source-" + "b" * 75) / ("stage-" + "c" * 75)
            try:
                report = self.stage(root, output, assets, fonts, hashes)
                target = pkg._io_path(output / pkg.PROJECT / "scripts/example.gd")
                self.assertEqual(target.read_text("utf-8"), "extends Node\n")
                self.assertIn(pkg.PROJECT + "/scripts/example.gd", report["files"])
            finally:
                # tempfile's own Windows cleanup does not add the long-path
                # prefix, so clean this one generated fixture branch explicitly.
                branch = output.parents[1]
                self.assertTrue(branch.resolve().is_relative_to(base.resolve()))
                if pkg._io_path(branch).exists():
                    pkg.shutil.rmtree(pkg._io_path(branch))


if __name__ == "__main__":
    unittest.main()
