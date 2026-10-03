"""Portable friends packages use synthetic directories, never a live game."""
import hashlib
import json
import shutil
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from tools import career3d_runtime_compat as compat
from tools import package_career3d as package_tools
from tools import package_career3d_friends as friends


NATIVE = 'addons/BotController/bin/win64/BotController.dll'


class FriendsPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='career-friends-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.ordinary = self.root / 'ordinary'
        for name in ('backend/CareerBackend.exe', 'engine/Godot.exe', 'game/project.godot'):
            self.write(self.ordinary, name, b'clean synthetic distribution')
        self.source = self.ordinary / 'source/CS2Career-fixture-source.zip'
        self.source.parent.mkdir()
        vendor_files = {'vendor/BotBuy/BotBuy.dll': b'career matching BotBuy',
                        'vendor/BotBuy/BotBuy.deps.json': b'{"runtimeTarget":"fixture"}'}
        for relative, blob in vendor_files.items():
            self.write(self.ordinary / 'backend/_internal', relative, blob)
        with zipfile.ZipFile(self.source, 'w') as source:
            source.writestr('CS2Career-source/LICENSE', 'synthetic license')
            source.writestr('CS2Career-source/vendor/BotBuy/BotBuy.cs', '// matching source')
            source.writestr('CS2Career-source/vendor/BotBuy/BotBuy.csproj', '<Project/>')
            for relative, blob in vendor_files.items():
                source.writestr('CS2Career-source/' + relative, blob)
            source.writestr('CS2Career-source/SOURCE_STAGE_MANIFEST.json', json.dumps({
                'files':{relative:hashlib.sha256(blob).hexdigest() for relative, blob in vendor_files.items()}}))
        self.runtime = self.root / 'reviewed/runtime'
        for name in ('addons/metamod', 'addons/counterstrikesharp', 'overrides'):
            (self.runtime / name).mkdir(parents=True)
        self.write(self.runtime, NATIVE, b'checked native')
        self.write(self.runtime, 'addons/counterstrikesharp/plugins/BotBuy/BotBuy.dll', b'official upstream BotBuy')
        self.write(self.runtime, 'addons/counterstrikesharp/plugins/BotBuy/BotBuy.deps.json', b'{}')
        self.write(self.runtime, 'cfg/my_bot_rush_config.cfg', b'bot_ignore_radio 0\n')
        self.write(self.runtime, 'addons/counterstrikesharp/configs/admins.example.json', b'{}')
        self.manifest = {'schema_version':1, 'revision':'fixture-compatible-current', 'components':[
            {'name':'Controller', 'version':'fixture-1', 'required_paths':[NATIVE]}]}
        self.receipt = {'schema_version':1, 'revision':self.manifest['revision'],
                        'manifest_sha256':compat._manifest_hash(self.manifest),
                        'origin_mod_dir':'E:/developer-private/source',
                        'components':[{'name':'Controller', 'version':'fixture-1'}],
                        'files':{relative.as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path, relative in compat._source_plan(self.runtime)}}
        (self.runtime.parent / compat.RECEIPT).write_text(json.dumps(self.receipt), 'utf-8')
        self.legal = self.root / 'legal'
        self.write(self.legal, 'LICENSE.txt', b'Corresponding upstream license')
        self.sources = self.root / 'sources'
        self.sources.mkdir()
        with zipfile.ZipFile(self.sources / 'upstream-source.zip', 'w') as archive:
            archive.writestr('LICENSE', 'Original terms')
            archive.writestr('plugin.cs', '// Pinned production source')
        self.manifest_patch = patch.object(compat, 'load_runtime_manifest', return_value=self.manifest)
        self.manifest_patch.start()
        self.addCleanup(self.manifest_patch.stop)

    def write(self, root, name, blob):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        return target

    def build(self, output=None):
        return friends.build_friends(self.ordinary, self.runtime, self.legal, self.sources,
                                     output or self.root / 'output', 'fixture.3')

    def unpack(self, report):
        archive_path = self.root / 'output/packages' / report['archive']['name']
        extracted = self.root / 'extracted'
        with zipfile.ZipFile(archive_path) as archive:
            self.assertIsNone(archive.testzip())
            self.assertFalse(any('/game/runtime/' in name or name.endswith('godot-import.log')
                                 or name.endswith('.gitkeep') for name in archive.namelist()))
            for folder in ('addons/metamod', 'overrides'):
                entry = archive.getinfo('CS2Career-fixture.3-all-in-one/mod/' + folder + '/')
                self.assertTrue(entry.is_dir())
            archive.extractall(extracted)
        return extracted / 'CS2Career-fixture.3-all-in-one'

    def assert_offline_install(self, package):
        user = self.root / 'new-tester'
        user.mkdir()
        game = self.root / 'synthetic-game'
        game.mkdir()
        marker = self.write(game, 'gameinfo.gi', b'untouched synthetic game')
        with patch.object(compat, '_download_archive', side_effect=AssertionError('offline')) as download, \
                patch.object(compat.urllib.request, 'urlopen', side_effect=AssertionError('offline')) as network:
            receipt = compat.validate_bundled_runtime(package / 'mod', self.manifest)
            self.assertIsNotNone(receipt)
            seeded = compat.seed_bundled_runtime(user, package / 'mod')
            prepared = compat.prepare_runtime(user, seeded, game, allow_download=False)
            self.assertTrue(prepared['cache_hit'])
            self.assertEqual(prepared['components'], receipt['components'])
            download.assert_not_called()
            network.assert_not_called()
        self.assertEqual(marker.read_bytes(), b'untouched synthetic game')
        return receipt

    def test_package_preserves_source_filters_private_fixtures_and_installs_offline(self):
        before = self.source.read_bytes()
        self.write(self.ordinary, 'godot-import.log', b'transient synthetic import log')
        report = self.build()
        package = self.unpack(report)
        self.assertEqual((package / 'source' / self.source.name).read_bytes(), before)
        receipt = json.loads((package / compat.RECEIPT).read_text('utf-8'))
        self.assertNotIn('origin_mod_dir', receipt)
        self.assertNotIn('developer-private', (package / compat.RECEIPT).read_text('utf-8'))
        self.assertFalse((package / 'mod/addons/counterstrikesharp/configs/admins.example.json').exists())
        self.assertFalse((package / 'game/runtime').exists())
        self.assertIn('CS2CAREER_BUNDLED_MOD=%~dp0mod', (package / '开始游戏.cmd').read_text('ascii'))
        self.assertTrue((package / 'legal/bot-runtime/LICENSE.txt').is_file())
        self.assertTrue((package / 'third_party/bot-runtime/upstream-source.zip').is_file())
        self.assertEqual(report['runtime_files'], 4)
        for name in ('BotBuy.dll', 'BotBuy.deps.json'):
            source = self.ordinary / 'backend/_internal/vendor/BotBuy' / name
            target = package / 'mod/addons/counterstrikesharp/plugins/BotBuy' / name
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(receipt['files']['addons/counterstrikesharp/plugins/BotBuy/' + name],
                             hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(len(report['overlays']), 2)
        self.assertEqual({row['component'] for row in report['overlays']}, {'BotBuy'})
        self.assertTrue(all(row['from'].startswith('backend/_internal/vendor/BotBuy/') for row in report['overlays']))
        self.assertEqual(self.assert_offline_install(package), receipt)

    def test_verified_controller_variant_source_version_survives_zip_and_offline_install(self):
        self.manifest['components'][0]['version'] = '0.7.0'
        variant = {'name': 'Controller', 'version': '0.7.0', 'source_kind': 'official_bundle',
                   'source_version': '0.7.1', 'variant': 'fixture-official-145'}
        self.receipt['manifest_sha256'] = compat._manifest_hash(self.manifest)
        self.receipt['components'] = [variant]
        native = self.write(self.runtime, NATIVE, b'fixture official bundle controller 0.7.1')
        self.receipt['files'][NATIVE] = hashlib.sha256(native.read_bytes()).hexdigest()
        (self.runtime.parent / compat.RECEIPT).write_text(json.dumps(self.receipt), 'utf-8')
        report = self.build()
        package = self.unpack(report)
        receipt = self.assert_offline_install(package)
        self.assertEqual(receipt['components'], [variant])
        self.assertEqual(report['components'], [variant])
        packaged_report = json.loads((package / 'FRIENDS_PACKAGE_MANIFEST.json').read_text('utf-8'))
        self.assertEqual(packaged_report['components'], [variant])
        self.assertNotIn('origin_mod_dir', receipt)

    def test_build_rejects_zip_that_loses_required_empty_directory(self):
        original_archive = friends.archive

        def drop_overrides(folder, destination, prefix):
            original_archive(folder, destination, prefix)
            with zipfile.ZipFile(destination) as archive:
                members = [(entry, archive.read(entry)) for entry in archive.infolist()
                           if entry.filename != prefix + '/mod/overrides/']
            with zipfile.ZipFile(destination, 'w') as archive:
                for entry, content in members:
                    archive.writestr(entry, content)

        with patch.object(friends, 'archive', side_effect=drop_overrides):
            with self.assertRaisesRegex(ValueError, '目录不完整'):
                self.build()
        self.assertFalse((self.root / 'output/packages/FRIENDS_BUILD_MANIFEST.json').exists())

    def test_archive_verification_extracts_and_cleans_long_windows_paths(self):
        original_archive = friends.archive
        original_extractall = zipfile.ZipFile.extractall
        deep_name = '/'.join(['backend', *['deep-fixture-' * 5] * 4, 'payload.txt'])
        extraction_roots = []

        def add_deep_payload(folder, destination, prefix):
            original_archive(folder, destination, prefix)
            with zipfile.ZipFile(destination, 'a') as archive:
                archive.writestr(prefix + '/' + deep_name, b'synthetic deep .NET payload')

        def extractall(archive, path, *args, **kwargs):
            extraction_roots.append(Path(path))
            original_extractall(archive, path, *args, **kwargs)
            payload = Path(path) / 'CS2Career-fixture.3-all-in-one' / deep_name
            self.assertGreater(len(str(compat._normal_path(payload))), 260)
            self.assertEqual(compat.io_path(payload).read_bytes(), b'synthetic deep .NET payload')

        with patch.object(friends, 'archive', side_effect=add_deep_payload), \
                patch.object(zipfile.ZipFile, 'extractall', new=extractall):
            self.build()
        self.assertEqual(len(extraction_roots), 1)
        self.assertFalse(compat.io_path(extraction_roots[0]).exists())
        if compat.os.name == 'nt':
            self.assertTrue(str(extraction_roots[0]).startswith('\\\\?\\'))

    def test_archive_preserves_empty_directories_and_filters_player_state(self):
        stage = self.root / 'archive-stage'
        for relative in ('mod/addons/metamod', 'mod/overrides'):
            (stage / relative).mkdir(parents=True)
        self.write(stage, 'game/runtime/career/save/fixture.json', b'private synthetic save')
        self.write(stage, 'godot-import.log', b'transient synthetic import log')
        self.write(stage, 'README.txt', b'portable fixture')
        result = self.root / 'fixture.zip'
        package_tools.archive(stage, result, 'fixture')
        with zipfile.ZipFile(result) as archive:
            self.assertTrue(archive.getinfo('fixture/mod/overrides/').is_dir())
            self.assertTrue(archive.getinfo('fixture/mod/addons/metamod/').is_dir())
            self.assertFalse(any('/game/runtime/' in name or name.endswith('godot-import.log')
                                 or name.endswith('.gitkeep') for name in archive.namelist()))
            archive.extractall(self.root / 'archive-extracted')
        self.assertTrue((self.root / 'archive-extracted/fixture/mod/overrides').is_dir())
        self.assertFalse((self.root / 'archive-extracted/fixture/game/runtime').exists())

    def test_archive_rejects_symlinks_and_windows_reparse_files_or_directories(self):
        stage = self.root / 'archive-stage'
        (stage / 'empty').mkdir(parents=True)
        self.write(stage, 'file.txt', b'synthetic ordinary file')
        original_symlink = Path.is_symlink
        original_lstat = Path.lstat
        for linked in (stage, stage / 'empty', stage / 'file.txt'):
            for kind in ('symlink', 'reparse'):
                with self.subTest(path=linked.name, kind=kind):
                    def is_symlink(path):
                        return path == linked or original_symlink(path)

                    def lstat(path, *args, **kwargs):
                        entry = original_lstat(path, *args, **kwargs)
                        if path == linked:
                            return SimpleNamespace(st_mode=entry.st_mode, st_file_attributes=0x400)
                        return entry

                    context = patch.object(Path, 'is_symlink', new=is_symlink) if kind == 'symlink' else \
                        patch.object(Path, 'lstat', new=lstat)
                    with context, self.assertRaisesRegex(ValueError, 'Symlink or reparse'):
                        package_tools.archive(stage, self.root / ('rejected-' + kind + '.zip'))

    def test_existing_output_and_overlapping_source_never_overwritten(self):
        output = self.root / 'exists'
        output.mkdir()
        marker = output / 'keep.txt'
        marker.write_text('keep', 'utf-8')
        with self.assertRaises(ValueError):
            self.build(output)
        self.assertEqual(marker.read_text('utf-8'), 'keep')
        with self.assertRaises(ValueError):
            self.build(self.ordinary / 'output')

    def test_prefixed_license_names_and_nuget_metadata_are_checked_and_preserved(self):
        names = ('ed0ard_CS2-BotAI-LICENSE', 'CounterStrikeSharp-LICENSE.GPL3',
                 'nuget/Lib.Harmony/1-LICENSE', 'nuget/Lib.Harmony/PACKAGE_METADATA.nuspec')
        for name in names:
            self.write(self.legal, name, b'Reviewed license and package metadata')
        self.build()
        package = self.root / 'output/stage/CS2Career-fixture.3-all-in-one'
        for name in names:
            self.assertEqual((package / 'legal/bot-runtime' / name).read_bytes(),
                             (self.legal / name).read_bytes())
        self.write(self.legal, 'unreviewed.exe', b'not a legal text')
        with self.assertRaisesRegex(ValueError, 'Unreviewed file type'):
            self.build(self.root / 'unreviewed-output')

    def test_missing_or_changed_ordinary_botbuy_overlay_rejected_before_output(self):
        overlay = self.ordinary / 'backend/_internal/vendor/BotBuy/BotBuy.dll'
        before = overlay.read_bytes()
        overlay.unlink()
        with self.assertRaisesRegex(ValueError, 'lacks its BotBuy'):
            self.build()
        self.assertFalse((self.root / 'output').exists())
        overlay.write_bytes(b'wrong DLL')
        with self.assertRaisesRegex(ValueError, 'does not match corresponding source'):
            self.build()
        self.assertFalse((self.root / 'output').exists())
        overlay.write_bytes(before)

    def test_dirty_ordinary_stage_and_corrupt_runtime_block_before_output(self):
        private = self.write(self.ordinary, 'game/runtime/career/save/career.json', b'private')
        with self.assertRaisesRegex(ValueError, 'player runtime'):
            self.build()
        self.assertFalse((self.root / 'output').exists())
        shutil.rmtree(self.ordinary / 'game/runtime')
        (self.runtime / NATIVE).write_bytes(b'changed native')
        with self.assertRaisesRegex(ValueError, 'reviewed receipt'):
            self.build()
        self.assertFalse((self.root / 'output').exists())

    def test_private_notice_rejected_and_invalid_source_archive_rejected(self):
        self.write(self.legal, 'owner.txt', b'private account owner')
        with self.assertRaises(ValueError):
            self.build()
        (self.legal / 'owner.txt').unlink()
        # Existing source archives are explicit; do not accept traversal names.
        with zipfile.ZipFile(self.sources / 'upstream-source.zip', 'w') as archive:
            archive.writestr('../outside.cs', 'invalid')
        with self.assertRaises(ValueError):
            self.build(self.root / 'other-output')

    def test_game_panel_api_sources_allowed_but_management_panel_directory_rejected(self):
        with zipfile.ZipFile(self.sources / 'upstream-source.zip', 'w') as archive:
            archive.writestr('LICENSE', 'Original terms')
            archive.writestr('Generated/EventCsWinPanelMatch.g.cs', '// game event API')
            archive.writestr('Generated/CPointClientUIWorldPanel.g.cs', '// game UI entity API')
        self.build()
        with zipfile.ZipFile(self.sources / 'upstream-source.zip', 'w') as archive:
            archive.writestr('Panel/main.cs', '// management application')
        with self.assertRaisesRegex(ValueError, 'Private data'):
            self.build(self.root / 'management-panel-output')


if __name__ == '__main__':
    unittest.main()
