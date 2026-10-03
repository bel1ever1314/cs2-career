"""Compatibility preparation uses synthetic ZIPs and game directories on E:."""
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import career3d_runtime_compat as compat


QA_ROOT = Path('E:/CS2CareerTools/Career3DRuntimeChecks-20261002/qa')
NATIVE = 'addons/BotController/bin/win64/BotController.dll'
GAMEDATA = 'addons/BotController/gamedata.json'


def archive_bytes(entries):
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in entries:
            archive.writestr(name, value)
    return data.getvalue()


def prepare_with_downloads(root, mod, game):
    # Archive upgrade tests explicitly opt into the developer preparation path.
    # Player installation uses prepare_runtime's offline default.
    return compat.prepare_runtime(root, mod, game, allow_download=True)


class CompatibilityRuntimeTests(unittest.TestCase):
    def setUp(self):
        QA_ROOT.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='runtime-', dir=QA_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.root = self.base / 'career'
        self.root.mkdir()
        self.mod = self.base / '原始发行包 Bot Improver'
        self.mod.mkdir()
        self.game = self.base / 'game/csgo'
        self.game.mkdir(parents=True)
        self.write(self.game, 'gameinfo.gi', b'official untouched game')
        for name in ('addons/metamod', 'addons/counterstrikesharp', 'overrides'):
            (self.mod / name).mkdir(parents=True)
        for name, value in ((NATIVE, b'old native'), (GAMEDATA, b'old gamedata'),
                            ('addons/BotController/gamedata/obsolete.json', b'old obsolete'),
                            ('addons/metamod/bin/win64/metamod.2.cs2.dll', b'keep metamod'),
                            ('addons/counterstrikesharp/plugins/CustomAim/CustomAim.dll', b'keep aim'),
                            ('addons/counterstrikesharp/configs/plugins/CustomAim/config.json', b'keep aim settings'),
                            ('cfg/gamemode_custom.cfg', b'keep game cfg'),
                            ('cfg/autoexec.cfg', b'private bindings'),
                            ('addons/BotHider/bot_info.json', b'private player identities'),
                            ('addons/counterstrikesharp/plugins/InventorySimulator/inventories.json', b'private inventory'),
                            ('addons/counterstrikesharp/plugins/CareerMatch/match_request.json', b'private request'),
                            ('addons/CustomAim/run.log', b'private log'),
                            ('overrides/Medium/botprofile.db', b'private roster')):
            self.write(self.mod, name, value)
        self.manifest_file = self.base / 'manifest.json'
        self.urls = {}
        self.manifest = {'schema_version':1, 'revision':'windows-fixture.1', 'components':[]}
        self.add_component('Controller', [(NATIVE, b'new native'), (GAMEDATA, b'new gamedata'),
                                         ('addons/BotHider/bot_info.json', b'upstream identities'),
                                         ('addons/Evil/Other.dll', b'not approved')],
                           replace_paths=['addons/BotController/bin', 'addons/BotController/gamedata.json',
                                          'addons/BotController/gamedata'],
                           allow_paths=['addons/BotController'], required_paths=[NATIVE, GAMEDATA])
        self.persist_manifest()
        self.start(patch('cs2career.paths.data_file', return_value=self.manifest_file))
        self.download = self.start(patch.object(compat, '_download_archive', side_effect=self.fake_download))
        self.start(patch('subprocess.Popen', side_effect=AssertionError('no executable startup')))

    def start(self, context):
        mock = context.start()
        self.addCleanup(context.stop)
        return mock

    def write(self, root, name, value):
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(value)
        return file

    def add_component(self, name, entries, **options):
        data = archive_bytes(entries)
        url = 'https://github.com/XBribo/CS2-Bot-Controller/releases/download/v0.7.1/' + name + '.zip'
        self.urls[url] = data
        self.manifest['components'].append({'name':name, 'version':'fixture-1', 'url':url,
                                           'sha256':hashlib.sha256(data).hexdigest(), **options})

    def persist_manifest(self):
        self.manifest_file.write_text(json.dumps(self.manifest), 'utf-8')

    def add_improver_base(self, extra=()):
        production = Path(__file__).resolve().parents[1] / 'cs2career/data/cs2_runtime_compat.json'
        component = deepcopy(json.loads(production.read_text('utf-8'))['components'][0])
        self.assertEqual(component['name'], 'CS2 Bot Improver')
        entries = [(name, ('official 1.4.5: ' + name).encode('utf-8'))
                   for name in component['required_paths']]
        entries += [('addons/BotHider/config.json', b'{"official":"hider"}'),
                    ('addons/BotVision/config.json', b'{"official":"vision"}'),
                    ('addons/counterstrikesharp/shared/BotControllerApi/BotControllerApi.dll', b'base api'),
                    ('Panel v1.4.5.exe', b'never launch panel'),
                    ('addons/BotHider/bot_info.json', b'never copy player identities'),
                    ('overrides/Medium/botprofile.vpk', b'never copy roster'),
                    ('addons/counterstrikesharp/plugins/CareerMatch/CareerMatch.dll', b'never copy career'),
                    ('addons/counterstrikesharp/plugins/InventorySimulator/inventories.json', b'private inventory'),
                    ('backup/WithBots/gameinfo.gi', b'never use upstream gameinfo')]
        entries.extend(extra)
        payload = archive_bytes(entries)
        self.urls[component['url']] = payload
        component['sha256'] = hashlib.sha256(payload).hexdigest()
        component['size'] = len(payload)
        self.manifest['components'].insert(0, component)
        self.manifest['revision'] = 'windows-fixture.2-improver145'
        self.persist_manifest()
        return component

    def fake_download(self, url, destination):
        compat.io_path(destination).write_bytes(self.urls[url])

    def use_long_roots(self):
        """Long fixture paths work without changing Windows machine policy."""
        parent = self.base / ('long-career-folder-' * 3) / ('long-install-folder-' * 3)
        parent = parent / ('long-local-fixture-' * 3) / ('long-component-cache-' * 3)
        self.assertGreater(len(str(parent)), 260)
        compat.io_path(parent).mkdir(parents=True)
        original_mod = self.mod
        self.root = parent / 'career'
        compat.io_path(self.root).mkdir()
        self.mod = parent / 'original-mod'
        shutil.copytree(compat.io_path(original_mod), compat.io_path(self.mod))
        # TemporaryDirectory itself may not be long-path-aware on older Windows.
        # The explicit extended path cleanup runs first, only on our own fixture.
        self.addCleanup(shutil.rmtree, compat.io_path(self.base / ('long-career-folder-' * 3)))
        custom = ('addons/counterstrikesharp/plugins/CustomAim/' +
                  'source-file-with-long-name-' * 3 + '.json')
        self.write_long(self.mod, custom, b'custom long source')
        return custom

    def write_long(self, root, name, value):
        file = root / name
        compat.io_path(file.parent).mkdir(parents=True, exist_ok=True)
        compat.io_path(file).write_bytes(value)
        return file

    def original_files(self):
        return {p.relative_to(self.mod).as_posix():p.read_bytes() for p in self.mod.rglob('*') if p.is_file()}

    def portable_bundle(self):
        prepared = Path(prepare_with_downloads(self.root, self.mod, self.game)['mod_dir'])
        package = self.base / 'friends-package'
        bundle = package / 'mod'
        shutil.copytree(prepared, bundle)
        shutil.copy2(prepared.parent / compat.RECEIPT, package / compat.RECEIPT)
        receipt = json.loads((package / compat.RECEIPT).read_text('utf-8'))
        receipt.pop('origin_mod_dir', None)
        (package / compat.RECEIPT).write_text(json.dumps(receipt), 'utf-8')
        return bundle

    def test_explicit_bundle_seeds_fresh_cache_offline_and_preserves_source_game(self):
        bundle = self.portable_bundle()
        before = {p.relative_to(bundle).as_posix(): p.read_bytes() for p in bundle.rglob('*') if p.is_file()}
        user = self.base / 'fresh-player-career'
        user.mkdir()
        self.download.side_effect = AssertionError('offline bundle must not download')
        self.download.reset_mock()
        seeded = compat.seed_bundled_runtime(user, bundle)
        self.assertTrue(seeded.is_relative_to(user / 'runtime-cache'))
        result = prepare_with_downloads(user, seeded, self.game)
        self.assertTrue(result['cache_hit'])
        self.assertEqual(compat.seed_bundled_runtime(user, bundle), seeded)
        self.download.assert_not_called()
        self.assertNotIn('origin_mod_dir', json.loads((seeded.parent / compat.RECEIPT).read_text('utf-8')))
        self.assertEqual(before, {p.relative_to(bundle).as_posix(): p.read_bytes() for p in bundle.rglob('*') if p.is_file()})
        self.assertEqual((self.game / 'gameinfo.gi').read_bytes(), b'official untouched game')

    def test_legacy_bundle_without_receipt_uses_existing_preparation(self):
        self.assertIsNone(compat.validate_bundled_runtime(self.mod))
        self.assertEqual(compat.seed_bundled_runtime(self.root, self.mod), self.mod)
        self.assertFalse((self.root / 'runtime-cache').exists())

    def test_bundle_corrupt_receipt_never_falls_back_or_writes_cache(self):
        bundle = self.portable_bundle()
        receipt_path = bundle.parent / compat.RECEIPT
        original = receipt_path.read_bytes()
        cases = [b'{', b'{}']
        receipt = json.loads(original)
        for key, value in (('revision', 'old'), ('manifest_sha256', '0' * 64), ('components', [])):
            changed = {**receipt, key: value}
            cases.append(json.dumps(changed).encode())
        for i, blob in enumerate(cases):
            with self.subTest(i=i):
                user = self.base / ('broken-user-' + str(i))
                user.mkdir()
                receipt_path.write_bytes(blob)
                with self.assertRaises(ValueError):
                    compat.seed_bundled_runtime(user, bundle)
                self.assertFalse((user / 'runtime-cache').exists())
        receipt_path.write_bytes(original)

    def test_bundle_altered_missing_extra_private_and_panel_files_rejected(self):
        bundle = self.portable_bundle()
        native = bundle / NATIVE
        original = native.read_bytes()
        native.write_bytes(b'altered')
        with self.assertRaisesRegex(ValueError, '校验失败'):
            compat.validate_bundled_runtime(bundle)
        native.unlink()
        with self.assertRaisesRegex(ValueError, '不完整'):
            compat.validate_bundled_runtime(bundle)
        native.write_bytes(original)
        for relative in ('addons/BotHider/bot_info.json', 'Panel.exe',
                         'addons/counterstrikesharp/configs/admins.example.json',
                         'addons/extra.dll'):
            with self.subTest(relative=relative):
                path = self.write(bundle, relative, b'not packaged')
                with self.assertRaises(ValueError):
                    compat.validate_bundled_runtime(bundle)
                path.unlink()

    def test_bundle_missing_required_component_rejected_even_with_resealed_receipt(self):
        bundle = self.portable_bundle()
        (bundle / NATIVE).unlink()
        receipt_path = bundle.parent / compat.RECEIPT
        receipt = json.loads(receipt_path.read_text('utf-8'))
        receipt['files'].pop(NATIVE)
        receipt_path.write_text(json.dumps(receipt), 'utf-8')
        with self.assertRaisesRegex(ValueError, '必需组件'):
            compat.validate_bundled_runtime(bundle)

    def test_corrupt_seed_copy_is_not_published(self):
        bundle = self.portable_bundle()
        user = self.base / 'failed-copy-user'
        user.mkdir()
        with patch.object(compat.shutil, 'copy2', side_effect=OSError('fixture copy failure')):
            with self.assertRaisesRegex(OSError, 'fixture copy failure'):
                compat.seed_bundled_runtime(user, bundle)
        self.assertEqual(list((user / 'runtime-cache').iterdir()), [])

    def test_overlay_preserves_source_game_settings_and_excludes_private_payload(self):
        before = self.original_files()
        result = prepare_with_downloads(self.root, self.mod, self.game)
        runtime = Path(result['mod_dir'])
        self.assertTrue(runtime.is_relative_to(self.root / 'runtime-cache'))
        self.assertEqual(result['origin_mod_dir'], str(self.mod))
        self.assertEqual(result['revision'], self.manifest['revision'])
        self.assertFalse(result['cache_hit'])
        self.assertEqual((runtime / NATIVE).read_bytes(), b'new native')
        self.assertEqual((runtime / GAMEDATA).read_bytes(), b'new gamedata')
        self.assertFalse((runtime / 'addons/BotController/gamedata/obsolete.json').exists())
        for relative in ('cfg/gamemode_custom.cfg', 'addons/counterstrikesharp/configs/plugins/CustomAim/config.json'):
            self.assertEqual((runtime / relative).read_bytes(), before[relative])
        for relative in ('cfg/autoexec.cfg', 'addons/BotHider/bot_info.json',
                         'addons/counterstrikesharp/plugins/InventorySimulator/inventories.json',
                         'addons/counterstrikesharp/plugins/CareerMatch/match_request.json',
                         'addons/CustomAim/run.log', 'overrides/Medium/botprofile.db', 'addons/Evil/Other.dll'):
            self.assertFalse((runtime / relative).exists(), relative)
        self.assertEqual(self.original_files(), before)
        self.assertEqual((self.game / 'gameinfo.gi').read_bytes(), b'official untouched game')
        self.assertTrue((runtime / 'overrides').is_dir())
        receipt = json.loads((runtime.parent / compat.RECEIPT).read_text('utf-8'))
        self.assertIn(NATIVE, receipt['files'])
        self.assertEqual(receipt['files'][NATIVE], hashlib.sha256(b'new native').hexdigest())

    def test_cache_reused_for_same_release_and_already_prepared_source_without_network(self):
        first = prepare_with_downloads(self.root, self.mod, self.game)
        self.download.reset_mock()
        second = prepare_with_downloads(self.root, self.mod, self.game)
        third = prepare_with_downloads(self.root, Path(first['mod_dir']), self.game)
        self.assertEqual(first['mod_dir'], second['mod_dir'])
        self.assertEqual(first['mod_dir'], third['mod_dir'])
        self.assertTrue(second['cache_hit'] and third['cache_hit'])
        self.download.assert_not_called()

    def test_manifest_revision_rebuilds_prepared_source_preserving_custom_plugins_and_settings(self):
        hider_config = 'addons/BotHider/config.json'
        self.write(self.mod, hider_config, b'{"custom": "hider setting"}')
        self.add_component('Hider settings', [(hider_config, b'{"upstream": "hider default"}')],
                           allow_paths=['addons/BotHider'], preserve_paths=[hider_config],
                           required_paths=[hider_config])
        self.persist_manifest()
        original = self.original_files()
        first = prepare_with_downloads(self.root, self.mod, self.game)
        previous = Path(first['mod_dir'])
        previous_files = {p.relative_to(previous).as_posix():p.read_bytes()
                          for p in previous.rglob('*') if p.is_file()}

        self.manifest['revision'] = 'windows-fixture.2'
        self.persist_manifest()
        self.download.reset_mock()
        self.assertFalse(compat.runtime_context(previous)['current'])
        rebuilt = prepare_with_downloads(self.root, previous, self.game)
        runtime = Path(rebuilt['mod_dir'])

        self.assertFalse(rebuilt['cache_hit'])
        self.assertNotEqual(rebuilt['mod_dir'], first['mod_dir'])
        self.assertEqual(rebuilt['revision'], 'windows-fixture.2')
        self.assertTrue(compat.runtime_context(runtime)['current'])
        self.assertEqual((runtime / NATIVE).read_bytes(), b'new native')
        self.assertEqual((runtime / GAMEDATA).read_bytes(), b'new gamedata')
        self.assertFalse((runtime / 'addons/BotController/gamedata/obsolete.json').exists())
        for relative in ('addons/counterstrikesharp/plugins/CustomAim/CustomAim.dll',
                         'addons/counterstrikesharp/configs/plugins/CustomAim/config.json',
                         hider_config, 'cfg/gamemode_custom.cfg'):
            self.assertEqual((runtime / relative).read_bytes(), original[relative], relative)
        self.assertEqual({p.relative_to(previous).as_posix():p.read_bytes()
                          for p in previous.rglob('*') if p.is_file()}, previous_files)
        self.assertEqual(self.original_files(), original)
        self.assertEqual((self.game / 'gameinfo.gi').read_bytes(), b'official untouched game')
        self.download.assert_not_called()

    def test_old_release_gets_complete_improver_behavior_upgrade_not_only_controller(self):
        old_behavior = ('BotAI', 'BotAimImprover', 'BotState', 'NadeSystem')
        for plugin in old_behavior:
            self.write(self.mod, f'addons/counterstrikesharp/plugins/{plugin}/{plugin}.dll', b'old behavior')
            self.write(self.mod, f'addons/counterstrikesharp/plugins/{plugin}/obsolete.json', b'old data')
            self.write(self.mod, f'addons/counterstrikesharp/configs/plugins/{plugin}/config.json', b'old settings')
        self.write(self.mod, 'addons/BotHider/config.json', b'{"custom":"hider"}')
        self.write(self.mod, 'addons/BotVision/config.json', b'{"custom":"vision"}')
        self.write(self.mod, 'cfg/my_bot_normal_config.cfg', b'old normal config')
        original = self.original_files()
        base = self.add_improver_base()
        result = prepare_with_downloads(self.root, self.mod, self.game)
        runtime = Path(result['mod_dir'])
        for name in base['required_paths']:
            self.assertEqual((runtime / name).read_bytes(), ('official 1.4.5: ' + name).encode('utf-8'))
        for plugin in old_behavior:
            self.assertFalse((runtime / f'addons/counterstrikesharp/plugins/{plugin}/obsolete.json').exists())
            self.assertFalse((runtime / f'addons/counterstrikesharp/configs/plugins/{plugin}/config.json').exists())
        self.assertEqual((runtime / NATIVE).read_bytes(), b'new native')
        for folder in ('BotHider', 'BotVision'):
            name = f'addons/{folder}/config.json'
            self.assertEqual((runtime / name).read_bytes(), original[name])
        self.assertFalse((runtime / 'cfg/gamemode_custom.cfg').exists())
        self.assertEqual((runtime / 'addons/counterstrikesharp/plugins/CustomAim/CustomAim.dll').read_bytes(), b'keep aim')
        self.assertEqual(self.original_files(), original)
        self.assertEqual((self.game / 'gameinfo.gi').read_bytes(), b'official untouched game')

    def test_prepared_earlier_revision_rebuilt_with_new_behavior_and_dependency_order(self):
        first = Path(prepare_with_downloads(self.root, self.mod, self.game)['mod_dir'])
        before = {p.relative_to(first).as_posix():p.read_bytes() for p in first.rglob('*') if p.is_file()}
        self.add_improver_base()
        api = 'addons/counterstrikesharp/shared/BotControllerApi/BotControllerApi.dll'
        self.add_component('Managed API', [(api, b'audited 0.7.0 api')],
                           allow_paths=[api], replace_paths=[api], required_paths=[api])
        self.persist_manifest()
        self.assertFalse(compat.runtime_context(first)['current'])
        result = prepare_with_downloads(self.root, first, self.game)
        runtime = Path(result['mod_dir'])
        self.assertFalse(result['cache_hit'])
        self.assertNotEqual(runtime, first)
        self.assertEqual((runtime / api).read_bytes(), b'audited 0.7.0 api')
        self.assertEqual((runtime / NATIVE).read_bytes(), b'new native')
        self.assertTrue((runtime / 'addons/counterstrikesharp/plugins/BotAI/BotAI.dll').is_file())
        self.assertEqual({p.relative_to(first).as_posix():p.read_bytes() for p in first.rglob('*') if p.is_file()}, before)
        self.download.reset_mock()
        self.assertTrue(prepare_with_downloads(self.root, runtime, self.game)['cache_hit'])
        self.download.assert_not_called()

    def test_fixed_base_never_copies_panel_private_roster_or_career_plugin(self):
        self.add_improver_base()
        runtime = Path(prepare_with_downloads(self.root, self.mod, self.game)['mod_dir'])
        receipt = json.loads((runtime.parent / compat.RECEIPT).read_text('utf-8'))
        for name in ('Panel v1.4.5.exe', 'addons/BotHider/bot_info.json',
                     'overrides/Medium/botprofile.vpk', 'overrides/botprofile.vpk',
                     'addons/counterstrikesharp/plugins/CareerMatch/CareerMatch.dll',
                     'addons/counterstrikesharp/plugins/InventorySimulator/inventories.json',
                     'backup/WithBots/gameinfo.gi'):
            self.assertFalse((runtime / name).exists(), name)
            self.assertNotIn(name, receipt['files'])
        self.assertTrue((runtime / 'overrides').is_dir())

    def test_override_behavior_resources_are_copied_hashed_and_cache_checked(self):
        behavior = 'overrides/scripts/ai/bt_bots.vdata'
        self.write(self.mod, behavior, b'game behavior source')
        self.write(self.mod, 'overrides/scripts/ai/player_roster.db', b'private roster')
        self.write(self.mod, 'overrides/scripts/ai/runner.exe', b'launcher')
        self.write(self.mod, 'overrides/sounds/anthem.vsnd_c', b'not behavior')
        self.write(self.mod, 'overrides/backup/scripts/ai/old.vdata', b'backup')
        runtime = Path(prepare_with_downloads(self.root, self.mod, self.game)['mod_dir'])
        self.assertEqual((runtime / behavior).read_bytes(), b'game behavior source')
        receipt = json.loads((runtime.parent / compat.RECEIPT).read_text('utf-8'))
        self.assertEqual(receipt['files'][behavior], hashlib.sha256(b'game behavior source').hexdigest())
        for name in ('overrides/scripts/ai/player_roster.db', 'overrides/scripts/ai/runner.exe',
                     'overrides/sounds/anthem.vsnd_c', 'overrides/backup/scripts/ai/old.vdata'):
            self.assertFalse((runtime / name).exists())
        (runtime / behavior).write_bytes(b'changed behavior')
        self.assertIsNone(compat._cached_runtime(runtime, self.manifest))

    def test_base_official_override_behavior_supersedes_old_resource(self):
        behavior = 'overrides/scripts/ai/bt_bots.vdata_c'
        self.write(self.mod, behavior, b'old behavior')
        self.add_improver_base([(behavior, b'official new behavior')])
        runtime = Path(prepare_with_downloads(self.root, self.mod, self.game)['mod_dir'])
        self.assertEqual((runtime / behavior).read_bytes(), b'official new behavior')

    def test_base_checksum_failure_stops_before_publishing_new_runtime(self):
        original = self.original_files()
        base = self.add_improver_base()
        self.urls[base['url']] = b'changed official artifact'
        with self.assertRaisesRegex(ValueError, '校验失败'):
            prepare_with_downloads(self.root, self.mod, self.game)
        self.assertFalse(list((self.root / 'runtime-cache').glob('*/runtime')))
        self.assertEqual(self.original_files(), original)
        self.assertEqual((self.game / 'gameinfo.gi').read_bytes(), b'official untouched game')

    def test_optional_fixed_size_is_validated_and_checked(self):
        for size in (True, '123', 0, -1, compat.MAX_ARCHIVE_BYTES + 1):
            invalid = deepcopy(self.manifest)
            invalid['components'][0]['size'] = size
            self.manifest_file.write_text(json.dumps(invalid), 'utf-8')
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, '大小不正确'):
                compat.load_runtime_manifest()
        self.persist_manifest()
        self.manifest['components'][0]['size'] = 1
        self.persist_manifest()
        with self.assertRaisesRegex(ValueError, '大小不符'):
            prepare_with_downloads(self.root, self.mod, self.game)
        self.assertFalse(list((self.root / 'runtime-cache').glob('*/runtime')))

    def test_changed_legacy_cohort_file_cannot_overwrite_official_runtime_or_invalidate_cache(self):
        first = prepare_with_downloads(self.root, self.mod, self.game)
        (self.mod / NATIVE).write_bytes(b'changed old native')
        self.download.reset_mock()
        second = prepare_with_downloads(self.root, self.mod, self.game)
        self.assertEqual(first['mod_dir'], second['mod_dir'])
        self.assertEqual((Path(second['mod_dir']) / NATIVE).read_bytes(), b'new native')
        self.download.assert_not_called()

    def test_changed_custom_plugin_creates_new_runtime_without_redownloading_pinned_archive(self):
        first = prepare_with_downloads(self.root, self.mod, self.game)
        self.write(self.mod, 'addons/counterstrikesharp/plugins/CustomAim/CustomAim.dll', b'new aim')
        self.download.reset_mock()
        second = prepare_with_downloads(self.root, self.mod, self.game)
        self.assertNotEqual(first['mod_dir'], second['mod_dir'])
        self.download.assert_not_called()

    def test_root_mapped_randomizer_and_prefix_stripped_component(self):
        self.add_component('Randomizer', [('BotRandomizer.dll', b'new randomizer'),
                                         ('BotRandomizer.deps.json', b'{}'), ('BotRandomizer.pdb', b'debug')],
                           target_prefix='addons/counterstrikesharp/plugins/BotRandomizer',
                           allow_paths=['addons/counterstrikesharp/plugins/BotRandomizer'],
                           required_paths=['addons/counterstrikesharp/plugins/BotRandomizer/BotRandomizer.dll'])
        self.add_component('Nested', [('package/addons/Nested/Test.dll', b'nested'),
                                     ('package/readme.txt', b'not runtime')], strip_prefix='package',
                           allow_paths=['addons/Nested'], required_paths=['addons/Nested/Test.dll'])
        self.persist_manifest()
        result = prepare_with_downloads(self.root, self.mod, self.game)
        runtime = Path(result['mod_dir'])
        self.assertEqual((runtime / 'addons/counterstrikesharp/plugins/BotRandomizer/BotRandomizer.dll').read_bytes(), b'new randomizer')
        self.assertFalse((runtime / 'addons/counterstrikesharp/plugins/BotRandomizer/BotRandomizer.pdb').exists())
        self.assertEqual((runtime / 'addons/Nested/Test.dll').read_bytes(), b'nested')

    def test_dotnet_host_executable_is_preserved_but_never_started_and_other_exes_excluded(self):
        self.add_component('Dotnet', [('addons/counterstrikesharp/dotnet/dotnet.exe', b'dotnet host'),
                                     ('addons/panel.exe', b'upstream panel')],
                           allow_paths=['addons/counterstrikesharp/dotnet'],
                           required_paths=['addons/counterstrikesharp/dotnet/dotnet.exe'])
        self.persist_manifest()
        runtime = Path(prepare_with_downloads(self.root, self.mod, self.game)['mod_dir'])
        self.assertEqual((runtime / 'addons/counterstrikesharp/dotnet/dotnet.exe').read_bytes(), b'dotnet host')
        self.assertFalse((runtime / 'addons/panel.exe').exists())

    def test_existing_native_plugin_settings_preserved_and_missing_settings_use_archive_default(self):
        hider_config = 'addons/BotHider/config.json'
        vision_config = 'addons/BotVision/config.json'
        self.write(self.mod, hider_config, b'{"custom": "hider setting"}')
        self.add_component('Hider settings', [(hider_config, b'{"upstream": "hider default"}')],
                           allow_paths=['addons/BotHider'], preserve_paths=[hider_config],
                           required_paths=[hider_config])
        self.add_component('Vision settings', [(vision_config, b'{"upstream": "vision default"}')],
                           allow_paths=['addons/BotVision'], preserve_paths=[vision_config],
                           required_paths=[vision_config])
        self.persist_manifest()
        first = prepare_with_downloads(self.root, self.mod, self.game)
        runtime = Path(first['mod_dir'])
        self.assertEqual((runtime / hider_config).read_bytes(), b'{"custom": "hider setting"}')
        self.assertEqual((runtime / vision_config).read_bytes(), b'{"upstream": "vision default"}')
        self.write(self.mod, vision_config, b'{"custom": "vision setting"}')
        second = Path(prepare_with_downloads(self.root, self.mod, self.game)['mod_dir'])
        self.assertEqual((second / vision_config).read_bytes(), b'{"custom": "vision setting"}')
        self.assertEqual((self.mod / hider_config).read_bytes(), b'{"custom": "hider setting"}')

    def test_manifest_cannot_preserve_old_native_api_or_gamedata_components(self):
        for name in (NATIVE, GAMEDATA, 'addons/counterstrikesharp/api/CounterStrikeSharp.API.dll',
                     'addons/counterstrikesharp/configs/other-config.json'):
            invalid = deepcopy(self.manifest)
            invalid['components'][0]['preserve_paths'] = [name]
            self.manifest_file.write_text(json.dumps(invalid), 'utf-8')
            with self.subTest(path=name), self.assertRaisesRegex(ValueError, '不能保留旧运行组件'):
                compat.load_runtime_manifest()
        self.download.assert_not_called()

    def test_checksum_failure_never_publishes_runtime_or_changes_source_game(self):
        before = self.original_files()
        self.urls[self.manifest['components'][0]['url']] = b'wrong artifact'
        with self.assertRaisesRegex(ValueError, '校验失败'):
            prepare_with_downloads(self.root, self.mod, self.game)
        self.assertEqual(self.original_files(), before)
        self.assertFalse(list((self.root / 'runtime-cache').glob('*/runtime')))
        self.assertEqual((self.game / 'gameinfo.gi').read_bytes(), b'official untouched game')

    def test_unsafe_zip_paths_duplicate_windows_names_and_symlinks_rejected(self):
        component = self.manifest['components'][0]
        unsafe = [('../escape.dll', b'x'), ('C:/escape.dll', b'x'), ('/escape.dll', b'x'),
                  ('addons/CON.dll', b'x'), ('addons/trailing .dll ', b'x')]
        for entry in unsafe:
            with self.subTest(path=entry[0]):
                path = self.write(self.base, 'unsafe.zip', archive_bytes([(NATIVE, b'ok'), entry]))
                with self.assertRaises(ValueError):
                    compat._archive_plan(path, component)
        path = self.write(self.base, 'unsafe.zip', archive_bytes([('addons/x.dll', b'a'), ('addons/X.dll', b'b')]))
        with self.assertRaisesRegex(ValueError, '重复'):
            compat._archive_plan(path, component)
        link = zipfile.ZipInfo('addons/link.dll')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        path = self.write(self.base, 'unsafe.zip', archive_bytes([(link, b'../target')]))
        with self.assertRaisesRegex(ValueError, '链接'):
            compat._archive_plan(path, component)

    def test_zip_file_directory_conflict_rejected_even_in_excluded_area(self):
        path = self.write(self.base, 'unsafe.zip', archive_bytes([('docs/readme', b'file'), ('docs/readme/nested.txt', b'child')]))
        with self.assertRaisesRegex(ValueError, '冲突'):
            compat._archive_plan(path, self.manifest['components'][0])

    def test_required_files_must_come_from_official_archive_not_old_source(self):
        component = deepcopy(self.manifest['components'][0])
        path = self.write(self.base, 'missing.zip', archive_bytes([(GAMEDATA, b'new gamedata')]))
        with self.assertRaisesRegex(ValueError, '缺少必需'):
            compat._archive_plan(path, component)

    def test_manifest_loading_is_pure_and_rejects_unpinned_or_foreign_inputs(self):
        self.assertEqual(compat.load_runtime_manifest()['revision'], self.manifest['revision'])
        self.download.assert_not_called()
        self.assertFalse((self.root / 'runtime-cache').exists())
        for key, value in (('sha256', 'not a hash'), ('url', 'http://github.com/example.zip'),
                           ('url', 'https://example.com/release.zip'),
                           ('url', 'https://github.com/other/repo/releases/download/v1/release.zip'),
                           ('allow_paths', ['../escape'])):
            with self.subTest(field=key, value=value):
                invalid = deepcopy(self.manifest)
                invalid['components'][0][key] = value
                self.manifest_file.write_text(json.dumps(invalid), 'utf-8')
                with self.assertRaises(ValueError):
                    compat.load_runtime_manifest()
        self.download.assert_not_called()

    def test_invalid_overlapping_roots_fail_without_download_or_game_writes(self):
        for root, mod, game in ((self.root, self.mod, self.mod),
                                (self.mod, self.mod, self.game), (Path('relative'), self.mod, self.game)):
            with self.subTest(root=root, mod=mod, game=game), self.assertRaises(ValueError):
                prepare_with_downloads(root, mod, game)
        self.download.assert_not_called()
        self.assertFalse((self.root / 'runtime-cache').exists())

    def test_tampered_prepared_runtime_is_rebuilt_without_touching_old_tree(self):
        first = prepare_with_downloads(self.root, self.mod, self.game)
        runtime = Path(first['mod_dir'])
        (runtime / NATIVE).write_bytes(b'tampered')
        result = prepare_with_downloads(self.root, runtime, self.game)
        self.assertNotEqual(result['mod_dir'], str(runtime))
        self.assertEqual((Path(result['mod_dir']) / NATIVE).read_bytes(), b'new native')
        self.assertEqual((runtime / NATIVE).read_bytes(), b'tampered')

    def test_version_context_is_cheap_read_only_and_not_full_game_validation(self):
        prepared = prepare_with_downloads(self.root, self.mod, self.game)
        runtime = Path(prepared['mod_dir'])
        self.download.reset_mock()
        with patch.object(compat, '_hash', side_effect=AssertionError('status must not hash files')), \
                patch.object(compat, '_source_plan', side_effect=AssertionError('status must not walk files')), \
                patch.object(compat, '_cached_runtime', side_effect=AssertionError('status must not validate entire cache')):
            result = compat.runtime_context(runtime)
            self.assertTrue(result['source_ready'] and result['current'])
            self.assertEqual(result['revision'], self.manifest['revision'])
            self.assertEqual(result['expected_revision'], self.manifest['revision'])
            self.assertEqual(result['components'], [{'name':'Controller', 'version':'fixture-1'}])
            # A status hint must not claim that the game loaded the DLL, nor
            # pretend a cheap receipt check replaces install-time verification.
            (runtime / NATIVE).write_bytes(b'tampered after prepare')
            self.assertTrue(compat.runtime_context(runtime)['current'])
            self.assertNotIn('loaded', result)
            legacy = compat.runtime_context(self.mod)
            self.assertTrue(legacy['source_ready'])
            self.assertFalse(legacy['current'])
            self.assertEqual(legacy['revision'], '')
        self.download.assert_not_called()

    def test_version_context_rejects_stale_oversized_and_invalid_receipts_without_network(self):
        runtime = Path(prepare_with_downloads(self.root, self.mod, self.game)['mod_dir'])
        path = runtime.parent / compat.RECEIPT
        receipt = json.loads(path.read_text('utf-8'))
        self.download.reset_mock()
        for field, value in (('revision', 'old'), ('manifest_sha256', 'stale')):
            stale = deepcopy(receipt)
            stale[field] = value
            path.write_text(json.dumps(stale), 'utf-8')
            self.assertFalse(compat.runtime_context(runtime)['current'])
        for raw in ('{broken', 'x' * (compat.MAX_RECEIPT_BYTES + 1)):
            path.write_text(raw, 'utf-8')
            context = compat.runtime_context(runtime)
            self.assertFalse(context['current'])
            self.assertEqual(context['components'], [])
        self.assertFalse(compat.runtime_context(self.base / 'missing')['source_ready'])
        self.assertFalse(compat.runtime_context(Path('relative'))['source_ready'])
        self.download.assert_not_called()

    def test_long_roots_zip_members_source_copy_and_cache_reuse_keep_normal_receipts(self):
        custom = self.use_long_roots()
        long_member = ('addons/counterstrikesharp/dotnet/shared/Microsoft.AspNetCore.App/10.0.3/' +
                       'Microsoft.Extensions.Diagnostics.HealthChecks.Abstractions.dll')
        self.add_component('LongDotnet', [(long_member, b'long framework dll')],
                           allow_paths=['addons/counterstrikesharp/dotnet'],
                           required_paths=[long_member])
        self.persist_manifest()
        first = prepare_with_downloads(self.root, self.mod, self.game)
        runtime = Path(first['mod_dir'])
        self.assertGreater(len(str(runtime / long_member)), 400)
        self.assertEqual(compat.io_path(runtime / long_member).read_bytes(), b'long framework dll')
        self.assertEqual(compat.io_path(runtime / custom).read_bytes(), b'custom long source')
        self.assertEqual(first['origin_mod_dir'], str(self.mod))
        self.assertFalse(first['mod_dir'].startswith('\\\\?\\'))
        receipt = json.loads(compat.io_path(runtime.parent / compat.RECEIPT).read_text('utf-8'))
        self.assertEqual(receipt['origin_mod_dir'], str(self.mod))
        self.assertIn(long_member, receipt['files'])
        self.assertIn(custom, receipt['files'])
        self.assertTrue(all(not name.startswith('\\\\?\\') for name in receipt['files']))
        self.download.reset_mock()
        same_source = prepare_with_downloads(self.root, self.mod, self.game)
        same_runtime = prepare_with_downloads(self.root, runtime, self.game)
        self.assertTrue(same_source['cache_hit'] and same_runtime['cache_hit'])
        self.assertEqual(same_source['mod_dir'], first['mod_dir'])
        self.assertEqual(same_runtime['mod_dir'], first['mod_dir'])
        self.assertTrue(compat.runtime_context(runtime)['current'])
        self.download.assert_not_called()

    def test_long_cache_invalidated_payload_rebuilds_to_new_normal_path(self):
        self.use_long_roots()
        first = prepare_with_downloads(self.root, self.mod, self.game)
        runtime = Path(first['mod_dir'])
        compat.io_path(runtime / NATIVE).write_bytes(b'changed cached DLL')
        self.download.reset_mock()
        rebuilt = prepare_with_downloads(self.root, self.mod, self.game)
        self.assertNotEqual(rebuilt['mod_dir'], first['mod_dir'])
        self.assertFalse(rebuilt['mod_dir'].startswith('\\\\?\\'))
        self.assertEqual(compat.io_path(Path(rebuilt['mod_dir']) / NATIVE).read_bytes(), b'new native')
        self.assertEqual(compat.io_path(runtime / NATIVE).read_bytes(), b'changed cached DLL')
        self.assertEqual(compat.io_path(self.mod / NATIVE).read_bytes(), b'old native')
        self.download.assert_not_called()

    def test_long_staging_tree_removed_after_copy_failure(self):
        custom = self.use_long_roots()
        copy = shutil.copy2

        def interrupted_copy(source, target):
            result = copy(source, target)
            if compat._normal_path(source).relative_to(self.mod).as_posix() == custom:
                raise OSError('fixture copy interruption')
            return result

        with patch.object(compat.shutil, 'copy2', side_effect=interrupted_copy):
            with self.assertRaisesRegex(OSError, 'fixture copy interruption'):
                prepare_with_downloads(self.root, self.mod, self.game)
        directories = list(compat.io_path(self.root / 'runtime-cache').iterdir())
        self.assertFalse(any(path.name.startswith('.prepare-') for path in directories))
        self.assertFalse(any(compat.io_path(path / 'runtime').exists() for path in directories))
        self.assertEqual(compat.io_path(self.mod / custom).read_bytes(), b'custom long source')
        self.assertEqual((self.game / 'gameinfo.gi').read_bytes(), b'official untouched game')

    def test_long_download_partial_cleaned_after_bad_checksum(self):
        self.use_long_roots()
        self.urls[self.manifest['components'][0]['url']] = b'bad checksum'
        with self.assertRaisesRegex(ValueError, '校验失败'):
            prepare_with_downloads(self.root, self.mod, self.game)
        downloads = compat.io_path(self.root / 'runtime-cache/downloads')
        self.assertEqual(list(downloads.iterdir()), [])
        self.assertEqual(compat.io_path(self.mod / NATIVE).read_bytes(), b'old native')

    @unittest.skipUnless(os.name == 'nt', 'Windows I/O namespaces')
    def test_windows_io_namespace_converts_back_to_normal_drive_and_unc_paths(self):
        self.assertEqual(str(compat._normal_path('\\\\?\\E:\\career\\runtime')),
                         'E:\\career\\runtime')
        self.assertEqual(str(compat._normal_path('\\\\?\\UNC\\server\\share\\career')),
                         '\\\\server\\share\\career')


class BundledCompatibilityCohortTests(unittest.TestCase):
    """The Windows controller is pinned to the ABI our tactical leases audited."""

    def test_bundled_native_and_managed_controller_pin_the_same_audited_release(self):
        root = Path(__file__).resolve().parents[1]
        with patch('cs2career.paths.data_file', return_value=root / 'cs2career/data/cs2_runtime_compat.json'):
            manifest = compat.load_runtime_manifest()
        components = {component['name']:component for component in manifest['components']}
        for name, filename, sha256 in (
                ('BotController', 'BotController-MM-windows-0.7.0.zip',
                 '75d5885fe8dbbf55773bc044740b08ce269afdd57007175c71f28204579ec743'),
                ('BotController API', 'BotController-CSS-API-0.7.0.zip',
                 '5aa0ad73afa617e5c6b61f124d4af0719a972acf642c9dbe34ddaae2ae21ea35')):
            with self.subTest(component=name):
                component = components[name]
                self.assertEqual(component['version'], '0.7.0')
                self.assertEqual(component['url'],
                                 'https://github.com/XBribo/CS2-Bot-Controller/releases/download/v0.7.0/' + filename)
                self.assertEqual(component['sha256'].lower(), sha256)
        self.assertIn(NATIVE, components['BotController']['required_paths'])
        self.assertIn('addons/counterstrikesharp/shared/BotControllerApi/BotControllerApi.dll',
                      components['BotController API']['required_paths'])

    def test_improver145_is_pinned_first_and_replaces_complete_old_behavior_cohort(self):
        root = Path(__file__).resolve().parents[1]
        with patch('cs2career.paths.data_file', return_value=root / 'cs2career/data/cs2_runtime_compat.json'):
            manifest = compat.load_runtime_manifest()
        self.assertEqual(manifest['revision'], 'windows-20261003.2-improver145')
        base = manifest['components'][0]
        self.assertEqual(base['name'], 'CS2 Bot Improver')
        self.assertEqual(base['version'], '1.4.5')
        self.assertEqual(base['url'], 'https://github.com/ed0ard/CS2-Bot-Improver/releases/download/v1.4.5/CS2BotImprover.zip')
        self.assertEqual(base['sha256'], 'ae37b86533abfe0547c5ad4346d478cd846727509fc092842a81240eb0130140')
        self.assertEqual(base['size'], 73129728)
        for plugin in ('BotAI', 'BotAimImprover', 'BotState', 'NadeSystem'):
            self.assertIn('addons/counterstrikesharp/plugins/' + plugin, base['replace_paths'])
            self.assertIn('addons/counterstrikesharp/plugins/' + plugin, base['allow_paths'])
        self.assertIn('cfg', base['replace_paths'])
        self.assertIn('overrides', base['replace_paths'])
        self.assertNotIn('addons', base['allow_paths'])
        self.assertNotIn('overrides', base['allow_paths'])
        self.assertEqual(set(base['preserve_paths']),
                         {'addons/BotHider/config.json', 'addons/BotVision/config.json'})

    def test_tactical_hold_binding_keeps_the_audited_windows_controller_hash_and_abi(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / 'vendor/CareerMatch/TacticalHoldControls.cs').read_text('utf-8-sig')
        audited_hashes = dict(re.findall(r'\["([0-9A-F]{64})"\]\s*=\s*(\d+)', source))
        self.assertEqual(audited_hashes.get(
            '8645168D4BB6A55CE8A8AC4246BCE394496E4EECF4F56C2F2A7932A98EB75D61'), '22')
        self.assertIn('AuditedAbiForHash(hash);', source)
        self.assertIn('ValidateAbi(hash, Export<VersionFn>("GetVersion")())', source)


if __name__ == '__main__':
    unittest.main()
