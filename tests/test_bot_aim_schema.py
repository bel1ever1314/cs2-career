"""Regression checks for the narrowly scoped upstream aim compatibility patch."""

import hashlib
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "BotAimImprover"


class BotAimSchemaTests(unittest.TestCase):
    def setUp(self):
        self.source = (VENDOR / "BotAimImprover.cs").read_text(encoding="utf-8")
        self.metadata = json.loads((VENDOR / "UPSTREAM.json").read_text(encoding="utf-8"))

    def test_only_documented_changes_to_upstream_aim_logic(self):
        """Reverse the complete patch and match the pinned upstream source hash."""
        upstream = self.source
        changes = (
            ('ModuleVersion => "2.1.6-career1";', 'ModuleVersion => "2.1.6";'),
            ('ts: 0x596C, en: 0x59D8, vis: 0x59DC, pbot: 0,',
             'ts: 0x596C, en: 0x59D8, vis: 0x59DC, pbot: 0x17E0,'),
            ('ts: 0x5994, en: 0x5A00, vis: 0x5A04, pbot: 0,',
             'ts: 0x5994, en: 0x5A00, vis: 0x5A04, pbot: 0x1518,'),
            ('            // This pawn schema field moved between CS2 builds 2000930 and\n'
             '            // 2000933. Resolve once before installing the native hook; never\n'
             '            // read a pawn using a stale platform-specific fallback.\n'
             '            _off = new Offsets(_off.TargetSpot, _off.Enemy, _off.IsVisible,\n'
             '                PawnBotSchema.Resolve(Schema.GetSchemaOffset), _off.Sig);\n', ''),
            ('Logger.LogInformation("[BotAimImprover] Loaded ({Plat}). PickNewAimSpot=0x{Pna:X16}; m_pBot=0x{PBot:X}",\n'
             '                win ? "Windows" : "Linux", pnaRuntime, _off.PBot);',
             'Logger.LogInformation("[BotAimImprover] Loaded ({Plat}). PickNewAimSpot=0x{Pna:X16}",\n'
             '                win ? "Windows" : "Linux", pnaRuntime);'),
        )
        for patched, original in changes:
            self.assertEqual(upstream.count(patched), 1, patched)
            upstream = upstream.replace(patched, original, 1)
        self.assertEqual(hashlib.sha256(upstream.encode()).hexdigest(),
                         self.metadata["original_source_sha256_lf"])

    def test_resolution_happens_once_before_native_hook(self):
        self.assertEqual(self.source.count("PawnBotSchema.Resolve("), 1)
        self.assertLess(self.source.index("PawnBotSchema.Resolve("),
                        self.source.index("new MemoryFunctionVoid<IntPtr>"))
        self.assertLess(self.source.index("PawnBotSchema.Resolve("),
                        self.source.index(".Hook(OnPickNewAimSpotPost"))
        self.assertNotRegex(self.source, r"pbot:\s*0x")

    def test_missing_schema_cannot_fall_back_to_a_stale_offset(self):
        resolver = (VENDOR / "PawnBotSchema.cs").read_text(encoding="utf-8")
        self.assertIn('schemaOffset("CCSPlayerPawn", "m_pBot")', resolver)
        self.assertIn("if (offset <= 0)", resolver)
        self.assertIn("throw new InvalidOperationException", resolver)
        self.assertNotIn("0x1518", resolver)
        self.assertNotIn("0x14F8", resolver)
        load = self.source[self.source.index("public override void Load("):
                           self.source.index("RegisterEventHandler<EventRoundStart>")]
        self.assertIn("catch (Exception ex)", load)
        self.assertIn("return;", load)

    def test_original_build_api_and_license_are_preserved(self):
        project = ET.parse(VENDOR / "BotAimImprover.csproj").getroot()
        self.assertEqual(project.findtext("PropertyGroup/TargetFramework"), "net10.0")
        package = project.find("ItemGroup/PackageReference")
        self.assertEqual(package.attrib, {"Include": "CounterStrikeSharp.API", "Version": "1.0.376"})
        self.assertIn("GNU AFFERO GENERAL PUBLIC LICENSE",
                      (VENDOR / "LICENSE").read_text(encoding="utf-8"))
        self.assertEqual(self.metadata["commit"], "7157ff94dee6d0a0b2701c0c44dd0f2e6c9b988d")


if __name__ == "__main__":
    unittest.main()
