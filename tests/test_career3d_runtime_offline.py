"""Offline runtime preparation uses synthetic official ZIPs and temporary trees."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import career3d_runtime_compat as compat


BASE = 'CS2 Bot Improver'
CONTROLLER = 'BotController'
API = 'BotController API'
NATIVE = 'addons/BotController/bin/win64/BotController.dll'
GAMEDATA = 'addons/BotController/gamedata.json'
MANAGED_API = 'addons/counterstrikesharp/shared/BotControllerApi/BotControllerApi.dll'
HIDER = 'addons/BotHider/bin/win64/BotHider.dll'
VISION = 'addons/BotVision/bin/win64/BotVision.dll'
HIDER_CONFIG = 'addons/BotHider/config.json'
VISION_CONFIG = 'addons/BotVision/config.json'
CUSTOM = 'addons/counterstrikesharp/plugins/CustomAim/config.json'


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def official_zip(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, blob in entries.items():
            archive.writestr(name, blob)
    return output.getvalue()


class OfflineRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='offline-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / 'career'
        self.mod = self.base / 'official-mod'
        self.game = self.base / 'game/csgo'
        for directory in (self.root, self.mod, self.game):
            directory.mkdir(parents=True)
        self.write(self.game, 'gameinfo.gi', b'fixture untouched official gameinfo')
        self.write(self.game, 'addons/Existing/Existing.dll', b'fixture existing game plugin')

        base_files = {
            'addons/metamod/bin/win64/metamod.2.cs2.dll': b'fixture official metamod',
            'addons/counterstrikesharp/bin/CounterStrikeSharp.dll': b'fixture official css',
            HIDER: b'fixture official hider',
            VISION: b'fixture official vision',
            HIDER_CONFIG: b'{"hide":true}',
            VISION_CONFIG: b'{"vision":true}',
            'overrides/scripts/ai/deathmatch.bt': b'fixture official behavior tree',
            'cfg/my_bot.cfg': b'fixture official bot cfg',
        }
        controller_files = {NATIVE: b'fixture controller 0.7.0', GAMEDATA: b'fixture gamedata 0.7.0'}
        api_files = {MANAGED_API: b'fixture controller api 0.7.0'}
        self.owned_files = {BASE: base_files, CONTROLLER: controller_files, API: api_files}
        self.source_files = {name: blob for files in self.owned_files.values() for name, blob in files.items()}
        self.manifest = {'schema_version': 1, 'revision': 'offline-fixture.1', 'components': []}
        self.archives = {}
        # Official base archives may carry older shared DLLs. The final owner
        # in the fingerprint index is the later Controller/API component.
        self.add_component(BASE, '1.4.5', {
            **base_files, NATIVE: b'fixture base controller 0.6.0',
            GAMEDATA: b'fixture base gamedata 0.6.0', MANAGED_API: b'fixture base api 0.6.0',
        }, 'ed0ard/CS2-Bot-Improver', allow_paths=[
            'addons/metamod', 'addons/counterstrikesharp/bin', 'addons/BotHider',
            'addons/BotVision', 'overrides/scripts', 'cfg', 'addons/BotController',
            'addons/counterstrikesharp/shared/BotControllerApi',
        ], replace_paths=[
            'addons/metamod', 'addons/counterstrikesharp/bin', 'addons/BotHider/bin',
            'addons/BotVision/bin', 'overrides', 'cfg',
        ], required_paths=[*base_files, NATIVE, GAMEDATA, MANAGED_API],
            preserve_paths=[HIDER_CONFIG, VISION_CONFIG])
        self.add_component(CONTROLLER, '0.7.0', controller_files, 'XBribo/CS2-Bot-Controller',
                           allow_paths=['addons/BotController'],
                           replace_paths=['addons/BotController'], required_paths=list(controller_files))
        self.add_component(API, '0.7.0', api_files, 'XBribo/CS2-Bot-Controller',
                           allow_paths=['addons/counterstrikesharp/shared/BotControllerApi'],
                           replace_paths=['addons/counterstrikesharp/shared/BotControllerApi'],
                           required_paths=list(api_files))
        self.index = {
            'schema_version': 1,
            'manifest_sha256': compat._manifest_hash(self.manifest),
            'components': [
                {'name': component['name'], 'version': component['version'],
                 'archive_sha256': component['sha256'],
                 'files': {name: digest(blob) for name, blob in self.owned_files[component['name']].items()}}
                for component in self.manifest['components']
            ],
            'approved_variants': [],
        }
        self.manifest_file = self.base / 'cs2_runtime_compat.json'
        self.index_file = self.base / 'cs2_runtime_files.json'
        self.persist_metadata()
        self.restore_source()
        self.write(self.mod, CUSTOM, b'fixture custom aim settings')
        self.start(patch('cs2career.paths.data_file', side_effect=self.fixture_data_file))
        self.download = self.start(patch.object(
            compat, '_download_archive', side_effect=AssertionError('offline installation must not download')))

    def start(self, context):
        result = context.start()
        self.addCleanup(context.stop)
        return result

    @staticmethod
    def write(root, relative, blob):
        path = root / relative
        compat.io_path(path.parent).mkdir(parents=True, exist_ok=True)
        compat.io_path(path).write_bytes(blob)
        return path

    @staticmethod
    def snapshot(root):
        return {path.relative_to(compat.io_path(root)).as_posix(): path.read_bytes()
                for path in compat.io_path(root).rglob('*') if path.is_file()}

    def fixture_data_file(self, name):
        routes = {'cs2_runtime_compat.json': self.manifest_file, 'cs2_runtime_files.json': self.index_file}
        self.assertIn(name, routes, 'tests must not read other application data')
        return routes[name]

    def add_component(self, name, version, entries, repo, **options):
        archive = official_zip(entries)
        self.archives[name] = archive
        self.manifest['components'].append({
            'name': name, 'version': version, 'sha256': digest(archive), 'size': len(archive),
            'url': f'https://github.com/{repo}/releases/download/v{version}/fixture.zip', **options,
        })

    def persist_metadata(self):
        self.manifest_file.write_text(json.dumps(self.manifest), encoding='utf-8')
        self.index_file.write_text(json.dumps(self.index), encoding='utf-8')

    def restore_source(self):
        for name, blob in self.source_files.items():
            self.write(self.mod, name, blob)

    def seed_archive(self, name, blob=None):
        component = next(row for row in self.manifest['components'] if row['name'] == name)
        return self.write(self.root, 'runtime-cache/downloads/' + component['sha256'] + '.zip',
                          self.archives[name] if blob is None else blob)

    def add_variant(self):
        files = {
            HIDER: b'fixture bundle 1.4.5 hider', VISION: b'fixture bundle 1.4.5 vision',
            NATIVE: b'fixture bundle controller 0.6.0', GAMEDATA: b'fixture bundle gamedata 0.6.0',
            MANAGED_API: b'fixture bundle controller api 0.6.0',
        }
        self.index['approved_variants'] = [{
            'id': 'fixture-official-145', 'source_archive_sha256': digest(official_zip(files)),
            'source_version': '1.4.5', 'files': {name: digest(blob) for name, blob in files.items()},
            'component_versions': {CONTROLLER: '0.6.0', API: '0.6.0'},
        }]
        self.persist_metadata()
        return files

    def read_receipt(self, result):
        runtime = Path(result['mod_dir'])
        return json.loads(compat.io_path(runtime.parent / compat.RECEIPT).read_text('utf-8'))

    def assert_offline(self):
        self.download.assert_not_called()

    def assert_no_published_runtime(self):
        cache = self.root / 'runtime-cache'
        if cache.exists():
            self.assertFalse(any(path.name.startswith('.prepare-') for path in cache.iterdir()))
            self.assertFalse(any((path / 'runtime').exists() for path in cache.iterdir()))

    def test_complete_local_official_package_reuses_every_component_without_network(self):
        source_before, game_before = self.snapshot(self.mod), self.snapshot(self.game)
        with patch.object(compat, '_artifact', side_effect=AssertionError('complete package needs no ZIP')):
            result = compat.prepare_runtime(self.root, self.mod, self.game)
        runtime = Path(result['mod_dir'])
        self.assertFalse(result['cache_hit'])
        self.assertEqual(result['reused_components'], [BASE, CONTROLLER, API])
        self.assertEqual(result['supplemented_components'], [])
        self.assertEqual(self.snapshot(runtime), source_before)
        self.assertEqual(self.snapshot(self.mod), source_before)
        self.assertEqual(self.snapshot(self.game), game_before)
        self.assertFalse((self.root / 'runtime-cache/downloads').exists())
        self.assert_offline()

    def test_edited_hider_and_vision_configs_remain_locally_reusable(self):
        changes = {HIDER_CONFIG: b'{"hide":false,"custom":true}',
                   VISION_CONFIG: b'{"vision":false,"custom":true}'}
        for name, blob in changes.items():
            self.write(self.mod, name, blob)
        before = self.snapshot(self.mod)
        result = compat.prepare_runtime(self.root, self.mod, self.game)
        runtime = Path(result['mod_dir'])
        self.assertEqual(result['reused_components'], [BASE, CONTROLLER, API])
        self.assertEqual(result['supplemented_components'], [])
        receipt = self.read_receipt(result)
        for name, blob in changes.items():
            self.assertEqual(compat.io_path(runtime / name).read_bytes(), blob)
            self.assertEqual(receipt['files'][name], digest(blob))
        self.assertEqual(self.snapshot(self.mod), before)
        self.assert_offline()

    def test_missing_dll_is_explicitly_rejected_offline_without_source_or_game_changes(self):
        (self.mod / NATIVE).unlink()
        source_before, game_before = self.snapshot(self.mod), self.snapshot(self.game)
        with self.assertRaisesRegex(ValueError, '本地发行包缺少.*BotController.*安装未联网'):
            compat.prepare_runtime(self.root, self.mod, self.game)
        self.assertEqual(self.snapshot(self.mod), source_before)
        self.assertEqual(self.snapshot(self.game), game_before)
        self.assert_no_published_runtime()
        self.assert_offline()

    def test_verified_cached_zip_supplements_only_missing_component_without_network(self):
        (self.mod / NATIVE).unlink()
        cached_zip = self.seed_archive(CONTROLLER)
        source_before, game_before = self.snapshot(self.mod), self.snapshot(self.game)
        with patch.object(compat, '_archive_plan', wraps=compat._archive_plan) as archive_plan:
            result = compat.prepare_runtime(self.root, self.mod, self.game)
        self.assertEqual(archive_plan.call_count, 1)
        self.assertEqual(archive_plan.call_args.args[1]['name'], CONTROLLER)
        self.assertEqual(result['reused_components'], [BASE, API])
        self.assertEqual(result['supplemented_components'], [CONTROLLER])
        runtime = Path(result['mod_dir'])
        for name, blob in self.source_files.items():
            self.assertEqual(compat.io_path(runtime / name).read_bytes(), blob)
        self.assertEqual(cached_zip.read_bytes(), self.archives[CONTROLLER])
        self.assertEqual(self.snapshot(self.mod), source_before)
        self.assertEqual(self.snapshot(self.game), game_before)
        self.assert_offline()

    def test_cached_base_shared_dlls_yield_to_later_local_final_owners(self):
        (self.mod / VISION).unlink()
        self.seed_archive(BASE)
        result = compat.prepare_runtime(self.root, self.mod, self.game)
        self.assertEqual(result['reused_components'], [CONTROLLER, API])
        self.assertEqual(result['supplemented_components'], [BASE])
        runtime = Path(result['mod_dir'])
        for name in (NATIVE, GAMEDATA, MANAGED_API, VISION):
            self.assertEqual(compat.io_path(runtime / name).read_bytes(), self.source_files[name])
        self.assert_offline()

    def test_corrupt_cached_zip_cannot_bypass_checksum_or_start_download(self):
        (self.mod / NATIVE).unlink()
        cached_zip = self.seed_archive(CONTROLLER, b'fixture corrupt cached archive')
        source_before, game_before = self.snapshot(self.mod), self.snapshot(self.game)
        with self.assertRaisesRegex(ValueError, '安装未联网'):
            compat.prepare_runtime(self.root, self.mod, self.game)
        self.assertEqual(cached_zip.read_bytes(), b'fixture corrupt cached archive')
        self.assertEqual(self.snapshot(self.mod), source_before)
        self.assertEqual(self.snapshot(self.game), game_before)
        self.assert_no_published_runtime()
        self.assert_offline()

    def test_coherent_approved_bundle_reuses_actual_component_source_versions(self):
        variant_files = self.add_variant()
        for name, blob in variant_files.items():
            self.write(self.mod, name, blob)
        source_before = self.snapshot(self.mod)
        result = compat.prepare_runtime(self.root, self.mod, self.game)
        self.assertEqual(result['reused_components'], [BASE, CONTROLLER, API])
        self.assertEqual(result['supplemented_components'], [])
        expected_versions = {BASE: '1.4.5', CONTROLLER: '0.6.0', API: '0.6.0'}
        receipt = self.read_receipt(result)
        self.assertEqual(receipt['components'], result['components'])
        for component in receipt['components']:
            self.assertEqual(component['source_kind'], 'official_bundle')
            self.assertEqual(component['source_version'], expected_versions[component['name']])
            self.assertEqual(component['variant'], 'fixture-official-145')
        self.assertEqual(receipt['components'][1]['version'], '0.7.0')
        self.assertEqual(self.snapshot(Path(result['mod_dir'])), source_before)
        self.assertEqual(self.snapshot(self.mod), source_before)
        self.assert_offline()

    def test_missing_or_mixed_variant_cohort_is_not_approved(self):
        variant_files = self.add_variant()
        for case in ('missing_api', 'mixed_api'):
            with self.subTest(case=case):
                self.restore_source()
                for name, blob in variant_files.items():
                    self.write(self.mod, name, blob)
                if case == 'missing_api':
                    (self.mod / MANAGED_API).unlink()
                else:
                    self.write(self.mod, MANAGED_API, self.source_files[MANAGED_API])
                source_before, game_before = self.snapshot(self.mod), self.snapshot(self.game)
                with self.assertRaisesRegex(ValueError, '安装未联网'):
                    compat.prepare_runtime(self.root, self.mod, self.game)
                self.assertEqual(self.snapshot(self.mod), source_before)
                self.assertEqual(self.snapshot(self.game), game_before)
                self.assert_no_published_runtime()
                self.assert_offline()

    def test_replaced_local_component_hashes_change_cache_identity(self):
        variant_files = self.add_variant()
        first = compat.prepare_runtime(self.root, self.mod, self.game)
        first_runtime = Path(first['mod_dir'])
        first_files = self.snapshot(first_runtime)
        for name, blob in variant_files.items():
            self.write(self.mod, name, blob)
        second = compat.prepare_runtime(self.root, self.mod, self.game)
        self.assertFalse(second['cache_hit'])
        self.assertNotEqual(second['mod_dir'], first['mod_dir'])
        self.assertEqual(self.snapshot(first_runtime), first_files)
        for name, blob in variant_files.items():
            self.assertEqual(compat.io_path(Path(second['mod_dir']) / name).read_bytes(), blob)
        self.assertEqual(second['supplemented_components'], [])
        self.assert_offline()

    def test_receipt_and_cache_are_reused_offline_from_source_and_prepared_runtime(self):
        first = compat.prepare_runtime(self.root, self.mod, self.game)
        runtime = Path(first['mod_dir'])
        receipt_file = runtime.parent / compat.RECEIPT
        receipt_before = compat.io_path(receipt_file).read_bytes()
        receipt = json.loads(receipt_before)
        self.assertEqual(receipt['schema_version'], 1)
        self.assertEqual(receipt['manifest_sha256'], compat._manifest_hash(self.manifest))
        self.assertEqual(receipt['revision'], self.manifest['revision'])
        self.assertEqual(receipt['origin_mod_dir'], str(self.mod))
        self.assertEqual(receipt['files'], {name: digest(blob) for name, blob in self.snapshot(runtime).items()})
        self.assertEqual(receipt['components'], [
            {'name': row['name'], 'version': row['version']} for row in self.manifest['components']])
        with patch.object(compat, '_artifact', side_effect=AssertionError('cache hit needs no ZIP')):
            second = compat.prepare_runtime(self.root, self.mod, self.game)
            third = compat.prepare_runtime(self.root, runtime, self.game)
        for result in (second, third):
            self.assertTrue(result['cache_hit'])
            self.assertEqual(result['mod_dir'], first['mod_dir'])
            self.assertEqual(result['reused_components'], [BASE, CONTROLLER, API])
            self.assertEqual(result['supplemented_components'], [])
        self.assertEqual(compat.io_path(receipt_file).read_bytes(), receipt_before)
        self.assert_offline()


if __name__ == '__main__':
    unittest.main()
