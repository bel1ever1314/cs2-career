import contextlib
import io
import json
import shutil
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools import career3d_package_sources as source_pkg
from tools import package_career3d as pkg
from tools.package_career3d import archive, launch_cmd, seal_source_manifest, digest, VERSION


class Package3DTests(unittest.TestCase):
    def test_runtime_audio_excludes_retired_entrance_but_keeps_new_stems(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            project = base / 'source/work/career3d_redesign'
            (project / 'data').mkdir(parents=True)
            audio = project / 'assets/audio'
            audio.mkdir(parents=True)
            (project / 'assets/fixture.glb').write_bytes(b'fixture model')
            names = ('arena_entrance.ogg', 'arena_entrance_composition.json',
                     'major_final_music.ogg', 'major_final_crowd.ogg',
                     'major_final_cue.json', 'music_club_day.ogg', 'GeneralUser-GS-LICENSE.txt')
            for name in names:
                (audio / name).write_bytes(b'fixture')
            (project / 'project.godot').write_text('config_version=5', encoding='utf-8')
            with patch.object(pkg, 'MODELS', ('fixture.glb',)), patch.object(pkg.subprocess, 'run') as run:
                run.return_value.returncode = 0
                run.return_value.stdout = run.return_value.stderr = ''
                pkg.stage_game(base / 'source', base / 'game', base / 'Godot.exe', {})
            self.assertEqual({p.name for p in (base / 'game/assets/audio').iterdir()},
                             {name for name in names if not name.startswith('arena_entrance')})
            self.assertTrue((audio / 'arena_entrance.ogg').exists())

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

    def test_release_version_matches_source_stager(self):
        self.assertEqual(VERSION, '1.7.2')
        self.assertEqual(VERSION, source_pkg.VERSION)

    def legal_fixture(self, base):
        engine = base / 'Godot.exe'
        engine.write_bytes(b'MZ fixture engine')
        cache = base / 'legal-cache'
        cache.mkdir()
        for name in pkg.ENGINE_LEGAL_HASHES:
            (cache / name).write_bytes(b'Godot fixture ' + name.encode())
        hashes = {p.name: digest(p) for p in cache.iterdir()}
        pkg.write_json(cache / 'Godot-version.json', {
            'version': pkg.ENGINE_VERSION, 'executable_sha256': digest(engine)})
        return engine, cache, hashes

    def test_matching_offline_engine_licenses_are_copied_without_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            engine, cache, hashes = self.legal_fixture(base)
            target = base / 'output'
            with patch.object(pkg, 'ENGINE_LEGAL_HASHES', hashes), \
                    patch.object(pkg.urllib.request, 'urlopen') as network:
                pkg.copy_engine_legal(engine, target, cache)
            network.assert_not_called()
            self.assertEqual({p.name for p in target.iterdir()}, {*hashes, 'Godot-version.json'})
            for path in target.iterdir():
                self.assertEqual(path.read_bytes(), (cache / path.name).read_bytes())

    def test_offline_engine_license_mismatch_fails_before_writing(self):
        for invalid in ('version', 'engine', 'license', 'missing'):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                engine, cache, hashes = self.legal_fixture(base)
                if invalid == 'version':
                    pkg.write_json(cache / 'Godot-version.json', {
                        'version': 'different', 'executable_sha256': digest(engine)})
                elif invalid == 'engine':
                    engine.write_bytes(b'another engine')
                elif invalid == 'license':
                    (cache / 'Godot-LICENSE.txt').write_bytes(b'tampered')
                else:
                    (cache / 'Godot-COPYRIGHT.txt').unlink()
                with patch.object(pkg, 'ENGINE_LEGAL_HASHES', hashes), \
                        patch.object(pkg.urllib.request, 'urlopen') as network:
                    with self.assertRaises((ValueError, FileNotFoundError)):
                        pkg.copy_engine_legal(engine, base / 'output', cache)
                network.assert_not_called()
                self.assertFalse((base / 'output').exists())

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

    def fixture(self, base):
        root, assets, fonts = base / 'checkout', base / 'assets', base / 'fonts'
        files = {
            'LICENSE': 'project license\n',
            'THIRD_PARTY_NOTICES.md': 'ordinary third-party notice\n',
            'docs/3d-preview-readme.txt': 'CS2 Career 1.7.0-preview.2 ordinary release\n',
            'docs/skin-tools-interface.zh-CN.txt': 'optional skin tools\n',
            'docs/map-form-test.zh-CN.txt': 'map training and BP guide\n',
            'licenses/runtime/Python.txt': 'retained license\n',
            'cs2career/__init__.py': '# career engine\n',
            'tools/career3d_service.py': '# current backend source\n',
            'vendor/CareerMatch/CareerMatch.cs': '// 1.6.0-tactics.17\n',
            'vendor/InventorySimulator/gamedata/inventory-simulator.json': '{}\n',
            source_pkg.PROJECT + '/project.godot': 'config_version=5\n[application]\nconfig/name="CS2 Career · 俱乐部生活样板"\n',
            source_pkg.PROJECT + '/data/career_link.json': '{}\n',
            source_pkg.PROJECT + '/data/ui_style.json': '{}\n',
            source_pkg.PROJECT + '/scenes/tiers/bedroom.tscn': '[gd_scene format=3]\n',
            source_pkg.PROJECT + '/assets/branding/career_icon.svg': '<svg xmlns="http://www.w3.org/2000/svg"/>',
            source_pkg.RTS_PROJECT + '/project.godot': 'config_version=5\n',
        }
        for relative, content in files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')
        (root / 'vendor/CareerMatch/CareerMatch.dll').write_bytes(b'MZ current tactics.17')
        (root / source_pkg.PROJECT / 'assets/branding/career_boot.png').write_bytes(b'fixture boot image')
        for relative in pkg.RUNTIME_VENDOR_FILES:
            target = root / 'vendor' / relative
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'{}\n' if target.suffix == '.json' else b'MZ fixture plugin')
        # Existing private data must be excluded by the real source stager.
        private = root / source_pkg.PROJECT / 'runtime/career/save/career.json'
        private.parent.mkdir(parents=True)
        private.write_text('private save', encoding='utf-8')
        assets.mkdir()
        for name in pkg.MODELS:
            (assets / name).write_bytes(struct.pack('<4sII', b'glTF', 2, 12))
        (assets / 'audio').mkdir()
        (assets / 'audio/README.md').write_text('music provenance\n', encoding='utf-8')
        fonts.mkdir()
        for name in source_pkg.FONT_HASHES:
            (fonts / name).write_bytes(b'fixture font or license')
        engine = base / 'Godot.exe'
        engine.write_bytes(b'MZ fixture engine')
        python = base / 'python'
        python.mkdir()
        (python / 'LICENSE.txt').write_text('Python license\n', encoding='utf-8')
        args = ['--output', str(base / 'output'), '--engine', str(engine),
                '--assets', str(assets), '--fonts', str(fonts), '--media-config', str(base / 'media.json')]
        return root, fonts, python, args

    @staticmethod
    def fake_media(_config, destination):
        destination.mkdir(parents=True)
        return {'schema_version': 1, 'team_manifest': '../../media/teams/team-media.json',
                'skin_cache_roots': ['../../media/skin_art'], 'map_backgrounds': {}}, 0

    @staticmethod
    def fake_freeze(source, build):
        backend = build / 'dist/CareerBackend'
        backend.mkdir(parents=True)
        (backend / 'CareerBackend.exe').write_bytes(b'MZ newly frozen backend')
        pkg.stage_runtime_vendor(source, backend / '_internal/vendor')
        return backend

    def test_freezer_stages_exact_runtime_vendor_files_and_keeps_source_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, _, _, _ = self.fixture(base)
            extra = root / 'vendor/InventorySimulator/source/generated/long-source.cs'
            extra.parent.mkdir(parents=True)
            extra.write_text('// source only\n', encoding='utf-8')
            private = root / 'vendor/CareerMatch/match-request.json'
            private.write_text('private request must not be collected', encoding='utf-8')
            build = base / 'backend'
            with patch.object(pkg.subprocess, 'run') as run:
                pkg.freeze_backend(root, build)
            runtime = build / 'runtime-vendor'
            actual = {p.relative_to(runtime).as_posix() for p in runtime.rglob('*') if p.is_file()}
            self.assertEqual(actual, set(pkg.RUNTIME_VENDOR_FILES))
            self.assertEqual(len(actual), 12)
            for relative in actual:
                self.assertEqual(digest(runtime / relative), digest(root / 'vendor' / relative))
            self.assertTrue(extra.is_file())
            self.assertTrue(private.is_file())
            command = run.call_args.args[0]
            sep = ';' if pkg.os.name == 'nt' else ':'
            add_data = [command[i + 1] for i, argument in enumerate(command) if argument == '--add-data']
            self.assertIn(str(runtime) + sep + 'vendor', add_data)
            self.assertNotIn(str(root / 'vendor') + sep + 'vendor', add_data)

    def test_runtime_vendor_missing_input_fails_before_stage_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, _, _, _ = self.fixture(base)
            (root / 'vendor' / pkg.RUNTIME_VENDOR_FILES[-1]).unlink()
            with self.assertRaises(FileNotFoundError):
                pkg.stage_runtime_vendor(root, base / 'runtime-vendor')
            self.assertFalse((base / 'runtime-vendor').exists())

    def test_ordinary_build_uses_current_sources_and_matching_embedded_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, fonts, python, args = self.fixture(base)
            unused_bots = base / 'private-bot-stage'

            with patch.object(pkg, 'ROOT', root), \
                    patch.object(source_pkg, 'FONT_HASHES', {p.name: digest(p) for p in fonts.iterdir()}), \
                    patch.object(source_pkg, 'EXTERNAL_AUTHORING_SOURCES', {}), \
                    patch.object(source_pkg, 'stage_sources', wraps=source_pkg.stage_sources) as stage, \
                    patch.object(pkg, 'relative_media', side_effect=self.fake_media), \
                    patch.object(pkg, 'freeze_backend', side_effect=self.fake_freeze) as frozen, \
                    patch.object(pkg, 'download_legal'), \
                    patch.object(pkg, 'copy_engine_legal') as local_legal, \
                    patch.object(pkg.sys, 'base_prefix', str(python)), \
                    patch.object(pkg.subprocess, 'run', return_value=type('Result', (), {
                        'returncode': 0, 'stdout': '', 'stderr': ''})()), \
                    contextlib.redirect_stdout(io.StringIO()):
                pkg.main(args + ['--ordinary-only', '--version', '1.7.0-preview.2',
                                 '--bot-stage', str(unused_bots), '--engine-legal', str(base / 'legal-cache')])
            local_legal.assert_called_once_with(base / 'Godot.exe',
                base / 'output/release/CS2Career-1.7.0-preview.2/legal/Godot', base / 'legal-cache')
            source = base / 'output/build/source'
            frozen.assert_called_once_with(source, base / 'output/build/backend')
            self.assertEqual(stage.call_args.kwargs['version'], '1.7.0-preview.2')
            package_name = 'CS2Career-1.7.0-preview.2'
            public = base / 'output/packages'
            source_zip = public / (package_name + '-source.zip')
            windows_zip = public / (package_name + '-windows.zip')
            self.assertEqual({p.name for p in public.glob('*.zip')}, {source_zip.name, windows_zip.name})
            manifest = json.loads((public / 'BUILD_MANIFEST.json').read_text('utf-8'))
            self.assertEqual(manifest['version'], '1.7.0-preview.2')
            self.assertEqual(manifest['distribution'], 'ordinary-unbundled')
            self.assertFalse(manifest['bundled_bot_runtime'])
            readme = (source / 'docs/3d-preview-readme.txt').read_bytes()
            current_dll = (root / 'vendor/CareerMatch/CareerMatch.dll').read_bytes()
            with zipfile.ZipFile(source_zip) as archive:
                self.assertEqual(archive.read('CS2Career-source/vendor/CareerMatch/CareerMatch.dll'), current_dll)
                self.assertEqual(archive.read('CS2Career-source/3D测试版说明.txt'), readme)
                self.assertIn('CS2Career-source/' + source_pkg.PROJECT + '/scenes/tiers/bedroom.tscn', archive.namelist())
                source_manifest = json.loads(archive.read('CS2Career-source/SOURCE_STAGE_MANIFEST.json'))
                self.assertEqual(source_manifest['version'], '1.7.0-preview.2')
                self.assertFalse(source_manifest['bundled_bot_runtime'])
                for relative, checksum in source_manifest['files'].items():
                    self.assertEqual(digest(source / relative), checksum)
                self.assertFalse(any('/work/career3d_redesign/runtime/' in name or 'bot-runtime' in name or '/third_party/' in name
                                     for name in archive.namelist()))
                self.assertEqual(archive.read('CS2Career-source/licenses/runtime/Python.txt'), b'retained license\n')
            with zipfile.ZipFile(windows_zip) as archive:
                prefix = package_name + '/'
                self.assertEqual(archive.read(prefix + 'source/' + source_zip.name), source_zip.read_bytes())
                self.assertEqual(archive.read(prefix + 'backend/_internal/vendor/CareerMatch/CareerMatch.dll'), current_dll)
                self.assertEqual(archive.read(prefix + '测试版说明.txt'), readme)
                self.assertIn('CS2 Career 1.7.0-preview.2', archive.read(prefix + 'game/project.godot').decode('utf-8'))
                self.assertEqual(archive.read(prefix + 'game/scenes/tiers/bedroom.tscn'), b'[gd_scene format=3]\n')
                self.assertEqual(archive.read(prefix + 'game/assets/branding/career_boot.png'), b'fixture boot image')
                self.assertIn(prefix + 'game/assets/branding/career_icon.svg', archive.namelist())
                self.assertEqual(archive.read(prefix + 'LICENSE'), (source / 'LICENSE').read_bytes())
                self.assertFalse(any('/game/runtime/' in name or '/mod/' in name or 'bot-runtime' in name
                                     or '/third_party/' in name for name in archive.namelist()))

    def test_default_full_build_still_emits_original_three_archives(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, fonts, python, args = self.fixture(base)
            bots = base / 'audited-bots'
            for relative in ('vendor/InventorySimulator/gamedata/inventory-simulator.json',
                             'CS2BotImprover/addons/plugin.dll', 'legal/LICENSE.txt',
                             'third_party/corresponding-source.txt'):
                target = bots / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'fixture audited bot data')
            with patch.object(pkg, 'ROOT', root), \
                    patch.object(source_pkg, 'FONT_HASHES', {p.name: digest(p) for p in fonts.iterdir()}), \
                    patch.object(source_pkg, 'EXTERNAL_AUTHORING_SOURCES', {}), \
                    patch.object(pkg, 'relative_media', side_effect=self.fake_media), \
                    patch.object(pkg, 'freeze_backend', side_effect=self.fake_freeze), \
                    patch.object(pkg, 'download_legal'), \
                    patch.object(pkg.sys, 'base_prefix', str(python)), \
                    patch.object(pkg.subprocess, 'run', return_value=type('Result', (), {
                        'returncode': 0, 'stdout': '', 'stderr': ''})()), \
                    contextlib.redirect_stdout(io.StringIO()):
                pkg.main(args + ['--bot-stage', str(bots)])
            package_name = 'CS2Career-' + VERSION
            public = base / 'output/packages'
            self.assertEqual({p.name for p in public.glob('*.zip')}, {
                package_name + '-source.zip', package_name + '-windows.zip', package_name + '-all-in-one.zip'})
            manifest = json.loads((public / 'BUILD_MANIFEST.json').read_text('utf-8'))
            self.assertEqual(manifest['version'], VERSION)
            self.assertTrue(manifest['bundled_bot_runtime'])
            with zipfile.ZipFile(public / (package_name + '-windows.zip')) as archive:
                self.assertFalse(any('/mod/' in name for name in archive.namelist()))
            with zipfile.ZipFile(public / (package_name + '-all-in-one.zip')) as archive:
                prefix = package_name + '-all-in-one/'
                self.assertIn(prefix + 'mod/addons/plugin.dll', archive.namelist())
                self.assertIn(b'CS2CAREER_BUNDLED_MOD=%~dp0mod', archive.read(prefix + 'Launch-CS2Career.cmd'))

    def test_ordinary_resume_and_missing_full_bot_stage_fail_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            _, _, _, args = self.fixture(base)
            for extra in (['--ordinary-only', '--resume-prepared'], [],
                          ['--ordinary-only', '--version', '../escape']):
                with self.subTest(extra=extra), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as result:
                        pkg.main(args + extra)
                    self.assertEqual(result.exception.code, 2)
                    self.assertFalse((base / 'output').exists())


if __name__ == '__main__':
    unittest.main()
