import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('package_public', Path(__file__).parents[1]/'tools/package_public.py')
pkg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pkg)


class PublicPackageTests(unittest.TestCase):
    def test_only_allowlisted_code_templates_and_runtime_go_into_archives(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'source';root.mkdir()
            for doc in pkg.DOCS:
                (root/doc).write_text('documentation',encoding='utf-8')
            paths=['cs2career/test.py','save/career.json','extensions/private/story.json',
                   'extensions/_templates/story.json','vendor/CareerMatch/bin/secret.dll',
                   'vendor/CareerMatch/CareerMatch.dll','tools/__pycache__/junk.pyc',
                   'release/old/save/career.json','vendor/CareerMatch/obj/personal.json']
            for name in paths:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{}')
            exe=root/'release/app.exe';exe.parent.mkdir(exist_ok=True);exe.write_bytes(b'MZfixture')
            output=Path(folder)/'published'
            result=pkg.build(root,exe,output)
            self.assertEqual(result['cs2_live_test'],'pending')
            with zipfile.ZipFile(next(output.glob('*source.zip'))) as archive:
                names='\n'.join(archive.namelist())
                self.assertIn('cs2career/test.py',names)
                self.assertIn('extensions/_templates/story.json',names)
                self.assertNotIn('/save/',names)
                self.assertNotIn('/private/',names)
                self.assertNotIn('/obj/',names)
                self.assertNotIn('secret.dll',names)
            with zipfile.ZipFile(next(output.glob('*windows-x64.zip'))) as archive:
                entries = archive.namelist()
                names = '\n'.join(entries)
                self.assertIn('/开始游玩-FAQ.txt', names)
                self.assertIn('/licenses/THIRD_PARTY_NOTICES.md', names)
                self.assertNotIn('DEVELOPER_GUIDE.zh-CN.md', names)
                self.assertNotIn('游玩说明.txt', names)
                self.assertNotIn('添加人机增强.txt', names)
                self.assertFalse(any(n.endswith('.md') and n.count('/') == 1 for n in entries))
            with self.assertRaises(FileExistsError):pkg.build(root,exe,output)

    def test_credentials_and_personal_user_paths_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config.json'
            path.write_text('C:'+'/'+ 'Users'+'/someone/private',encoding='utf-8')
            with self.assertRaises(ValueError):pkg.verify_public_text(path)

    def test_native_debug_path_is_not_exempt_from_privacy_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'plugin.dll'
            path.write_bytes(b'MZ\0C:'+b'/Users'+b'/someone/plugin.pdb\0')
            with self.assertRaises(ValueError):pkg.verify_public_text(path)
