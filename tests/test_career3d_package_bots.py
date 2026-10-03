"""Packaging fixtures exercise privacy/integrity boundaries, never a real game."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import career3d_package_bots as package


class BotPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "project"
        self.capsule = self.base / "stage" / "compatible-mod"
        self.capsule.mkdir(parents=True)
        self.game = self.base / "game"
        self.game.mkdir()
        self.target = self.base / "output"
        self.manifest = {}
        self.required = (
            "addons/BotController/bin/win64/BotController.dll",
            "addons/counterstrikesharp/gamedata/gamedata.json",
            "addons/counterstrikesharp/configs/core.json",
        )
        for relative in self.required:
            self.item(relative, b"MZ fixture" if relative.endswith(".dll") else b"{}")
        for name in ("CareerMatch", "BotBuy"):
            for extension in ("dll", "deps.json"):
                relative = f"addons/counterstrikesharp/plugins/{name}/{name}.{extension}"
                self.item(relative, b"MZ fixture" if extension == "dll" else b"{}")
                source = self.project / f"vendor/{name}/{name}.{extension}"
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes((self.capsule / relative).read_bytes())
        for difficulty in ("Low", "Medium", "High"):
            preset = self.project / f"cs2career/data/botprofile_presets/{difficulty}.db"
            preset.parent.mkdir(parents=True, exist_ok=True)
            preset.write_bytes(b"// no upstream player list\nDefault\nEnd\nTemplate Generic\nEnd\n")
        self.skin = self.game / "addons/counterstrikesharp/gamedata/inventory-simulator.json"
        self.skin.parent.mkdir(parents=True, exist_ok=True)
        self.skin.write_bytes(b'{"ReviewedSignature":{}}')
        for name, value in (("ROOT", self.project), ("REQUIRED_FILES", self.required),
                ("REVIEWED_INVENTORY_GAMEDATA", package.digest(self.skin))):
            mock = patch.object(package, name, value)
            mock.start()
            self.addCleanup(mock.stop)
        mock = patch.object(package, "_stage_sources", side_effect=self.fake_sources)
        mock.start()
        self.addCleanup(mock.stop)
        self.pin()

    def item(self, relative, blob):
        source = self.capsule / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(blob)
        live = self.game / relative
        live.parent.mkdir(parents=True, exist_ok=True)
        live.write_bytes(blob)
        self.manifest[relative] = package.digest(source)

    def pin(self):
        file = self.capsule.parent / "capsule-files.json"
        file.write_text(json.dumps(self.manifest), encoding="utf-8")
        mock = patch.object(package, "EXPECTED_CAPSULE_MANIFEST", package.digest(file))
        mock.start()
        self.addCleanup(mock.stop)

    def fake_sources(self, pending):
        (pending / "legal").mkdir()
        (pending / "third_party").mkdir()
        return [{"component": "fixture"}]

    def snapshot(self, root):
        return {p.relative_to(root).as_posix(): package.digest(p)
                for p in root.rglob("*") if p.is_file()}

    def stage(self):
        return package.stage_bot_runtime(self.capsule, self.target, self.game)

    def test_stages_only_runtime_and_templates_leaving_game_unchanged(self):
        private = {
            "addons/BotHider/bot_info.json": b'{"private":"account"}',
            "addons/counterstrikesharp/configs/plugins/InventorySimulator/owner.txt": b"owner",
            "addons/counterstrikesharp/configs/plugins/InventorySimulator/inventories.json": b"inventory",
            "addons/counterstrikesharp/plugins/CareerMatch/match_request.json": b"request",
            "addons/counterstrikesharp/plugins/CareerMatch/match_result.json": b"result",
            "addons/counterstrikesharp/plugins/CareerMatch/report.json": b"report",
            "save/cs2.json": b"settings",
            "logs/game.log": b"private game log",
            "overrides/Medium/botprofile.db": b"named player roster",
        }
        for relative, blob in private.items():
            self.item(relative, blob)
        self.pin()
        before = self.snapshot(self.game)
        report = self.stage()
        self.assertEqual(before, self.snapshot(self.game))
        self.assertEqual(0, report["game_files_written"])
        runtime = Path(report["runtime_dir"])
        for relative in private:
            if relative.startswith("overrides/"):
                self.assertIn(b"no upstream player list", (runtime / relative).read_bytes())
            else:
                self.assertFalse((runtime / relative).exists(), relative)
        self.assertEqual(self.skin.read_bytes(), (Path(report["vendor_dir"]) / "InventorySimulator/gamedata/inventory-simulator.json").read_bytes())
        manifest = json.loads((self.target / "legal/BOT_RUNTIME_MANIFEST.json").read_text())
        self.assertNotIn(str(self.game), json.dumps(manifest))
        self.assertTrue(all(len(value) == 64 for value in manifest["runtime_files"].values()))

    def test_unknown_or_tampered_binary_is_refused_before_output(self):
        rogue = self.capsule / "addons/counterstrikesharp/api/custom.dll"
        rogue.parent.mkdir(parents=True, exist_ok=True)
        rogue.write_bytes(b"MZ unknown")
        with self.assertRaisesRegex(ValueError, "Unreviewed file"):
            self.stage()
        self.assertFalse(self.target.exists())
        rogue.unlink()
        (self.capsule / self.required[0]).write_bytes(b"MZ tampered")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.stage()
        self.assertFalse(self.target.exists())

    def test_unreviewed_manifest_or_missing_runtime_is_refused(self):
        (self.capsule.parent / "capsule-files.json").write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "manifest has not been reviewed"):
            self.stage()
        self.pin()
        (self.capsule / self.required[0]).unlink()
        with self.assertRaisesRegex(ValueError, "Missing runtime"):
            self.stage()
        self.assertFalse(self.target.exists())

    def test_identifiers_in_selected_config_and_unknown_signatures_are_refused(self):
        identifier = "7656119" + "8" * 10
        self.item(self.required[2], json.dumps({"account": identifier}).encode())
        self.pin()
        with self.assertRaisesRegex(ValueError, "Account identifier"):
            self.stage()
        self.assertFalse(self.target.exists())
        self.item(self.required[2], b"{}")
        self.pin()
        self.skin.write_bytes(b"unknown signature version")
        with self.assertRaisesRegex(ValueError, "reviewed updated skin gamedata"):
            self.stage()

    def test_game_mismatch_and_output_overlap_are_refused_without_writes(self):
        (self.game / self.required[0]).write_bytes(b"another installed version")
        before = self.snapshot(self.game)
        with self.assertRaisesRegex(ValueError, "Installed runtime differs"):
            self.stage()
        self.assertEqual(before, self.snapshot(self.game))
        with self.assertRaisesRegex(ValueError, "overlap"):
            package.stage_bot_runtime(self.capsule, self.game / "bad-output", self.game)
        self.target.mkdir()
        (self.target / "user-data").write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            self.stage()
        self.assertEqual(b"keep", (self.target / "user-data").read_bytes())

    def test_archive_path_traversal_is_rejected_and_data_panel_omitted(self):
        for relative in ("../outside", "/absolute", "C:/private", "safe\\outside"):
            with self.assertRaises(ValueError):
                package.runtime_allowed(relative)
        self.assertFalse(package._source_allowed("Panel/src/app.ts", improver=True))
        self.assertFalse(package._source_allowed("overrides/Medium/botprofile.db", improver=True))
        self.assertFalse(package._source_allowed("configs/addons/BotHider/bot_info.json"))
        self.assertTrue(package._source_allowed("src/plugin.cpp"))
        self.assertFalse(package._source_allowed("docs/manifest.json"))
        for relative in ("Harmony/Harmony.projitems", "native/version.rc", "build/AMBuildScript", "Lib/Public.snk"):
            self.assertTrue(package._source_allowed(relative), relative)

    def test_pinned_source_zip_keeps_license_code_and_recurses_submodules(self):
        parent = io.BytesIO()
        with zipfile.ZipFile(parent, "w") as archive:
            archive.writestr("repo-commit/LICENSE", "MIT fixture license")
            archive.writestr("repo-commit/src/plugin.cpp", "void Fixture() {}")
            archive.writestr("repo-commit/configs/addons/BotHider/bot_info.json", "account data")
            archive.writestr("repo-commit/.gitmodules", '[submodule "dependency"]\npath = libraries/dependency\nurl = https://github.com/example/dependency.git\n')
        child = io.BytesIO()
        with zipfile.ZipFile(child, "w") as archive:
            archive.writestr("dependency-commit/LICENSE", "MIT child license")
            archive.writestr("dependency-commit/include/library.h", "void Dependency();")
        commit, dependency_commit = "a" * 40, "b" * 40
        responses = [parent.getvalue(), json.dumps({"tree": [{"path": "libraries/dependency", "sha": dependency_commit, "mode": "160000"}]}).encode(), child.getvalue()]
        legal = self.base / "legal"
        legal.mkdir()
        output = self.base / "source.zip"
        with patch.object(package, "_download", side_effect=responses) as download:
            with zipfile.ZipFile(output, "w") as archive:
                records = package._fetch_source("example/repo", commit, archive, legal)
        self.assertEqual(3, download.call_count)
        self.assertEqual(2, len(records))
        with zipfile.ZipFile(output) as archive:
            self.assertIn("src/plugin.cpp", archive.namelist())
            self.assertIn("libraries/dependency/include/library.h", archive.namelist())
            self.assertFalse(any("bot_info.json" in name for name in archive.namelist()))
        self.assertEqual(2, len(list(legal.iterdir())))

    def test_dependency_notice_keeps_original_package_attribution_and_license(self):
        downloaded = io.BytesIO()
        with zipfile.ZipFile(downloaded, "w") as archive:
            archive.writestr("Fixture.nuspec", '<package><metadata><authors>Fixture Author</authors><copyright>Fixture Copyright</copyright><license type="expression">MIT</license></metadata></package>')
            archive.writestr("LICENSE.txt", "MIT fixture license text")
            archive.writestr("lib/net10.0/Fixture.dll", b"MZ runtime not a notice")
        notices = self.base / "notices"
        notices.mkdir()
        with patch.object(package, "_download", return_value=downloaded.getvalue()):
            record = package._nuget_notice("Fixture", "1.2.3", notices)
        self.assertEqual("Fixture Author", record["attribution"]["authors"]["text"])
        self.assertEqual("MIT", record["attribution"]["license"]["text"])
        self.assertEqual(hashlib.sha256(downloaded.getvalue()).hexdigest(), record["package_sha256"])
        folder = notices / "Fixture-1.2.3"
        self.assertEqual(b"MIT fixture license text", (folder / "1-LICENSE.txt").read_bytes())
        self.assertIn(b"Fixture Copyright", (folder / "PACKAGE_METADATA.nuspec").read_bytes())
        self.assertFalse(any(path.suffix == ".dll" for path in folder.iterdir()))

    def test_declared_gpl_and_lowercase_pinned_bsd_notices_are_preserved(self):
        legal = self.base / "legal"
        notices = legal / "nuget"
        notices.mkdir(parents=True)
        (legal / "roflmuffin_CounterStrikeSharp-LICENSE.GPL3").write_bytes(b"GPL fixture terms")
        gpl = io.BytesIO()
        with zipfile.ZipFile(gpl, "w") as archive:
            archive.writestr("Fixture.nuspec", '<package><metadata><authors>GPL Author</authors><license type="expression">GPL-3.0-only</license></metadata></package>')
        with patch.object(package, "_download", return_value=gpl.getvalue()):
            package._nuget_notice("GplFixture", "1.2.3", notices)
        self.assertEqual(b"GPL fixture terms", (notices / "GplFixture-1.2.3/DECLARED_LICENSE.txt").read_bytes())
        bsd, source = io.BytesIO(), io.BytesIO()
        with zipfile.ZipFile(bsd, "w") as archive:
            archive.writestr("Fixture.nuspec", '<package><metadata><copyright>BSD Author</copyright><license type="expression">BSD-2-Clause</license><repository url="https://github.com/example/fixture" commit="' + "a" * 40 + '" /></metadata></package>')
        with zipfile.ZipFile(source, "w") as archive:
            archive.writestr("fixture-commit/license.txt", "Copyright BSD Author\nBSD fixture terms")
            archive.writestr("fixture-commit/source.cs", "production source must not be a license notice")
        with patch.object(package, "_download", side_effect=[bsd.getvalue(), source.getvalue()]):
            record = package._nuget_notice("BsdFixture", "1.2.3", notices)
        self.assertEqual(b"Copyright BSD Author\nBSD fixture terms", (notices / "BsdFixture-1.2.3/DECLARED_LICENSE.txt").read_bytes())
        self.assertEqual(hashlib.sha256(source.getvalue()).hexdigest(), record["attribution"]["license_source"]["attributes"]["download_sha256"])
        self.assertFalse(any(path.suffix == ".cs" for path in (notices / "BsdFixture-1.2.3").iterdir()))


if __name__ == "__main__":
    unittest.main()
