import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.package_career3d import archive, launch_cmd, seal_source_manifest, digest, VERSION


class Package3DTests(unittest.TestCase):
    def test_launchers_are_relative_and_quote_paths(self):
        plain = launch_cmd()
        bundle = launch_cmd(bundled=True)
        self.assertIn('"%~dp0game"', plain)
        self.assertIn('"%~dp0engine\\Godot.exe"', plain)
        self.assertNotIn('C:/Users/', plain)
        self.assertIn('CS2CAREER_BUNDLED_MOD="', plain)
        self.assertIn('CS2CAREER_BUNDLED_MOD=%~dp0mod', bundle)
        self.assertIn('--rendering-method gl_compatibility', launch_cmd(compatibility=True))

    def test_archive_excludes_user_state_but_keeps_runtime_licenses(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'stage'
            for name in ('game/runtime/career/save/career.json',
                         'licenses/runtime/LICENSE.txt', 'game/data/career_link.json'):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('test')
            result = Path(temporary) / 'package.zip'
            archive(root, result, 'preview')
            with zipfile.ZipFile(result) as output:
                self.assertEqual(set(output.namelist()), {
                    'preview/licenses/runtime/LICENSE.txt', 'preview/game/data/career_link.json'})

    def test_preview_version_not_stable_release(self):
        self.assertEqual(VERSION, '1.7.0-preview.1')

    def test_final_source_manifest_records_overlays_and_added_license(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'NOTICE.txt').write_text('final notice')
            (root / 'legal').mkdir()
            (root / 'legal/LICENSE.txt').write_text('dependency license')
            result = seal_source_manifest(root, {'files': {'NOTICE.txt': 'old hash'}})
            self.assertEqual(result['files']['NOTICE.txt'], digest(root / 'NOTICE.txt'))
            self.assertIn('legal/LICENSE.txt', result['files'])
            self.assertNotIn('SOURCE_STAGE_MANIFEST.json', result['files'])
            self.assertEqual(result['source_files'], 2)


if __name__ == '__main__':
    unittest.main()
