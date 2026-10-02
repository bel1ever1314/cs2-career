"""Small fixture ZIPs exercise public repackaging without real release assets."""
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

from tools import package_career3d_public as pkg


class PublicPreviewPackageTests(unittest.TestCase):
    def fixture(self, base, source_extra=(), runtime_extra=()):
        project = base / "checkout"
        for relative in pkg.OVERLAYS:
            path = project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("current " + relative + "\n", encoding="utf-8")
        # The allowlisted overlay reader must never inspect this live data.
        (project / "save").mkdir()
        (project / "save/private.json").write_text("private player data", encoding="utf-8")
        (project / "unrelated.txt").write_text("private unrelated file", encoding="utf-8")
        old_sdk = io.BytesIO()
        with zipfile.ZipFile(old_sdk, "w") as archive:
            archive.writestr("native/libraries/hl2sdk-cs2/unknown.h", "unreviewed SDK")
        source_zip, windows_zip = base / "input-source.zip", base / "input-windows.zip"
        source_files = {
            "LICENSE": b"original AGPL license\n",
            "licenses/CS2Career-MIT-legacy.txt": b"original legacy MIT\n",
            "legal/other/LICENSE.txt": b"original other license\n",
            "cs2career/core.py": b"# reviewed core\n",
            "vendor/CareerMatch/CareerMatch.cs": b"// reviewed plugin\n",
            "work/career3d_redesign/fonts/OFL.txt": b"original font OFL\n",
            "work/career3d_redesign/fonts/font.ttf": b"original font bytes",
            "media/maps/map.png": b"original reviewed image",
            "README.md": b"old readme\n",
            "SOURCE_STAGE_MANIFEST.json": b'{"files":{"old":"obsolete"}}',
            "legal/bot-runtime/NOTICE.txt": b"old full-runtime claim",
            "third_party/bot-runtime/CounterStrikeSharp-source.zip": old_sdk.getvalue(),
        }
        with zipfile.ZipFile(source_zip, "w") as archive:
            for name, content in source_files.items():
                archive.writestr("source-root/" + name, content)
            archive.writestr("source-root/save/", b"")
            for entry, content in source_extra:
                # zipfile normalizes Windows separators when constructing a
                # ZipInfo; set filename explicitly to model malformed input.
                if isinstance(entry, str) and "\\" in entry:
                    raw_entry = zipfile.ZipInfo(entry)
                    raw_entry.filename = entry
                    entry = raw_entry
                archive.writestr(entry, content)
        runtime_files = {
            "backend/CareerBackend.exe": b"MZ frozen backend",
            "backend/_internal/THIRD_PARTY_NOTICES.md": b"old runtime claim\n",
            "backend/_internal/licenses/original.txt": b"original internal license",
            "engine/Godot.exe": b"MZ unchanged official engine",
            "legal/Godot/Godot-LICENSE.txt": b"original engine license",
            "game/fonts/OFL.txt": b"original font OFL\n",
            "media/maps/map.png": b"original reviewed image",
            "licenses/runtime/Python.txt": b"original runtime license",
            "Launch-CS2Career.cmd": b"original ordinary launcher",
            "THIRD_PARTY_NOTICES.md": b"old runtime claim\n",
            "测试版说明.txt": b"old preview readme",
            "source/old-source.zip": source_zip.read_bytes(),
        }
        with zipfile.ZipFile(windows_zip, "w") as archive:
            for name, content in runtime_files.items():
                archive.writestr("runtime-root/" + name, content)
            for entry, content in runtime_extra:
                archive.writestr(entry, content)
        return project, source_zip, windows_zip, source_files, runtime_files

    def test_excludes_old_sdk_preserves_licenses_and_replaces_matching_attachment(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project, source_zip, windows_zip, source_files, runtime_files = self.fixture(base)
            output = base / "public"
            original_source, original_windows = pkg.digest(source_zip), pkg.digest(windows_zip)
            original_open = Path.open

            def guard_open(path, *args, **kwargs):
                if path.is_relative_to(project / "save"):
                    self.fail("Read live project save directory")
                return original_open(path, *args, **kwargs)

            with patch.object(Path, "open", guard_open):
                report = pkg.repack_public(source_zip, windows_zip, output, project)
            source, runtime = output / "source", output / "runtime"
            self.assertFalse((source / "third_party/bot-runtime").exists())
            self.assertFalse((source / "legal/bot-runtime").exists())
            self.assertFalse((source / "save").exists())
            self.assertFalse((source / "unrelated.txt").exists())
            for relative, content in source_files.items():
                if not pkg._source_excluded(Path(relative)) and relative not in pkg.OVERLAYS:
                    self.assertEqual((source / relative).read_bytes(), content, relative)
            for relative, content in runtime_files.items():
                if relative not in ("THIRD_PARTY_NOTICES.md", "测试版说明.txt",
                                    "backend/_internal/THIRD_PARTY_NOTICES.md", "source/old-source.zip"):
                    self.assertEqual((runtime / relative).read_bytes(), content, relative)
            readme = (source / "docs/3d-preview-readme.txt").read_bytes()
            self.assertEqual((source / "3D测试版说明.txt").read_bytes(), readme)
            self.assertEqual((runtime / "测试版说明.txt").read_bytes(), readme)
            self.assertEqual((runtime / "THIRD_PARTY_NOTICES.md").read_bytes(),
                             (project / "THIRD_PARTY_NOTICES.md").read_bytes())
            for destination in (runtime / "licenses/counter-strike-icons-LICENSE.txt",
                                runtime / "backend/_internal/licenses/counter-strike-icons-LICENSE.txt"):
                self.assertEqual(destination.read_bytes(),
                                 (project / "licenses/counter-strike-icons-LICENSE.txt").read_bytes())
            self.assertFalse((runtime / "source/old-source.zip").exists())
            self.assertEqual((runtime / "source" / pkg.SOURCE_NAME).read_bytes(),
                             (output / pkg.SOURCE_NAME).read_bytes())
            with zipfile.ZipFile(output / pkg.WINDOWS_NAME) as archive:
                self.assertEqual(archive.read(pkg.PACKAGE + "/source/" + pkg.SOURCE_NAME),
                                 (output / pkg.SOURCE_NAME).read_bytes())
            source_manifest = json.loads((source / pkg.SOURCE_MANIFEST).read_text("utf-8"))
            self.assertNotIn(pkg.SOURCE_MANIFEST, source_manifest["files"])
            self.assertEqual(source_manifest["source_files"], len(source_manifest["files"]))
            for relative, checksum in source_manifest["files"].items():
                self.assertEqual(pkg.digest(source / relative), checksum)
            self.assertEqual(report["source_manifest_sha256"], pkg.digest(source / pkg.SOURCE_MANIFEST))
            self.assertEqual(set(report["archives"]), {pkg.SOURCE_NAME, pkg.WINDOWS_NAME})
            for name, metadata in report["archives"].items():
                self.assertEqual(metadata["sha256"], pkg.digest(output / name))
            self.assertEqual(report["distribution"], "ordinary-unbundled")
            self.assertNotIn(str(base), json.dumps(report))
            self.assertNotIn(str(base), json.dumps(source_manifest))
            self.assertEqual(pkg.digest(source_zip), original_source)
            self.assertEqual(pkg.digest(windows_zip), original_windows)
            self.assertEqual(len((output / "SHA256SUMS.txt").read_text().splitlines()), 2)

    def test_unsafe_paths_are_rejected_even_inside_excluded_sdk_folder(self):
        for name in ("../escape.txt", "source-root/../escape.txt", "/absolute.txt",
                     "source-root/C:/escape.txt", "source-root/a\\b.txt",
                     "source-root/third_party/bot-runtime/../leak.txt",
                     "source-root/CON.txt", "source-root/trailing. ",
                     "source-root/a//b.txt"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                project, source_zip, windows_zip, _, _ = self.fixture(base, [(name, b"unsafe")])
                with self.assertRaises(ValueError):
                    pkg.repack_public(source_zip, windows_zip, base / "public", project)
                self.assertFalse((base / "public").exists())
                self.assertFalse(list(base.glob(".career3d-public-*")))

    def test_duplicate_paths_case_collisions_and_file_directory_collisions_fail(self):
        for entries in (
            [("source-root/LICENSE", b"duplicate")],
            [("source-root/license", b"case collision")],
            [("source-root/cs2career", b"file collides with directory")],
        ):
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    project, source_zip, windows_zip, _, _ = self.fixture(base, entries)
                with self.assertRaises(ValueError):
                    pkg.repack_public(source_zip, windows_zip, base / "public", project)
                self.assertFalse((base / "public").exists())

    def test_zip_symlinks_are_rejected_in_source_and_runtime(self):
        for location in ("source", "runtime"):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                entry = zipfile.ZipInfo(location + "-root/link")
                entry.create_system = 3
                entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                kwargs = {location + "_extra": [(entry, b"../../private")]} if location == "source" else {
                    "runtime_extra": [(entry, b"../../private")]}
                project, source_zip, windows_zip, _, _ = self.fixture(base, **kwargs)
                with self.assertRaises(ValueError):
                    pkg.repack_public(source_zip, windows_zip, base / "public", project)

    def test_runtime_mod_and_player_state_are_rejected(self):
        for name in ("runtime-root/mod/plugin.dll", "runtime-root/game/runtime/career/save.json",
                     "runtime-root/MOD/", "runtime-root/game/RUNTIME/"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                project, source_zip, windows_zip, _, _ = self.fixture(base, runtime_extra=[(name, b"")])
                with self.assertRaises(ValueError):
                    pkg.repack_public(source_zip, windows_zip, base / "public", project)
                self.assertFalse((base / "public").exists())

    def test_mismatched_source_attachment_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project, source_zip, windows_zip, _, _ = self.fixture(base)
            with zipfile.ZipFile(source_zip, "a") as archive:
                archive.writestr("source-root/later-change.txt", "different source")
            with self.assertRaisesRegex(ValueError, "does not match"):
                pkg.repack_public(source_zip, windows_zip, base / "public", project)
            self.assertFalse((base / "public").exists())

    def test_existing_output_and_missing_overlay_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project, source_zip, windows_zip, _, _ = self.fixture(base)
            output = base / "public"
            output.mkdir()
            (output / "keep.txt").write_text("user file")
            with self.assertRaises(FileExistsError):
                pkg.repack_public(source_zip, windows_zip, output, project)
            self.assertEqual((output / "keep.txt").read_text(), "user file")
            (project / "docs/external-runtime-pins.json").unlink()
            with self.assertRaises(FileNotFoundError):
                pkg.repack_public(source_zip, windows_zip, base / "another", project)
            self.assertFalse((base / "another").exists())


if __name__ == "__main__":
    unittest.main()
