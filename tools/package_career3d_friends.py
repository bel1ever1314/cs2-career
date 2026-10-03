"""Build a fresh friends-only all-in-one from an ordinary Windows stage.

The compatible runtime must already have the current verified receipt. This
tool never reads a live game, installs plugins, discovers saves, or publishes.
Legal notices and corresponding-source archives are explicit reviewed inputs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import zipfile

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import career3d_runtime_compat as compat
from tools.career3d_package_bots import runtime_allowed, _public_text, SOURCE_SUFFIXES, BINARY_SOURCE_SUFFIXES, PRIVATE_NAMES
from tools.package_career3d import archive, digest, launch_cmd, write_json


TEXT_TYPES = frozenset(('.json', '.txt', '.md', '.cfg', '.xml', '.nuspec', '.vdf', '.ini', '.kv3', '.vdata', '.bt'))
FORBIDDEN = frozenset(('save', 'saves', 'logs', 'reports', 'demos', 'inventories', '.git',
                      'cache', 'caches', 'backup', 'backups', 'panel', 'node_modules'))
RUSH_CFG = frozenset(('my_bot_rush_config.cfg', 'gamemode_rush.cfg', 'gamemode_rush_offline.cfg'))
BEHAVIOR_CONFIGS = frozenset(('BotAI', 'BotAimImprover', 'BotState', 'NadeSystem'))


def _root(path: Path) -> Path:
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.exists() and compat._is_link(item):
            raise ValueError('Package inputs must not contain links')
    if not path.is_dir() or path == Path(path.anchor):
        raise ValueError('Package input must be an explicit non-root directory')
    return path.resolve()


def _files(root: Path):
    for path in sorted(root.rglob('*')):
        if compat._is_link(path):
            raise ValueError('Package inputs must not contain links')
        if path.is_file():
            yield path, path.relative_to(root)


def _runtime_allowed(relative: str) -> bool:
    path = compat._relative(relative)
    if not compat.bundled_payload_allowed(path):
        return False
    parts = path.parts
    if runtime_allowed(relative):
        return True
    if len(parts) == 2 and parts[0] == 'cfg' and parts[1] in RUSH_CFG:
        return True
    if parts[:4] == ('addons', 'counterstrikesharp', 'configs', 'plugins'):
        return (len(parts) == 6 and parts[4] in BEHAVIOR_CONFIGS and path.suffix == '.json')
    return parts[:2] == ('overrides', 'scripts') and path.suffix in compat._OVERRIDE_RUNTIME_SUFFIXES


def _copy_notices(source: Path, target: Path, *, source_archives=False):
    selected = list(_files(source))
    if not selected or (source_archives and not any(p.suffix == '.zip' for p, _ in selected)):
        raise ValueError('Corresponding source must include reviewed source ZIPs')
    for path, relative in selected:
        if (any(part.casefold() in FORBIDDEN for part in relative.parts)
                or relative.name.casefold() in PRIVATE_NAMES):
            raise ValueError('Private data in legal/source input')
        if path.suffix == '.zip':
            with zipfile.ZipFile(path) as check:
                if check.testzip() is not None:
                    raise ValueError('Corrupt corresponding-source archive')
                seen, expanded = set(), 0
                for entry in check.infolist():
                    name = compat._relative(entry.filename)
                    key = name.as_posix().casefold()
                    if key in seen or stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1:
                        raise ValueError('Invalid corresponding-source archive member')
                    seen.add(key)
                    expanded += entry.file_size
                    if entry.file_size > compat.MAX_FILE_BYTES or expanded > compat.MAX_EXPANDED_BYTES:
                        raise ValueError('Corresponding source exceeds package limits')
                    if (any(p.casefold() in FORBIDDEN for p in name.parts)
                            or name.name.casefold() in PRIVATE_NAMES):
                        raise ValueError('Private data in corresponding-source archive')
                    if (not entry.is_dir() and (name.suffix.casefold() in SOURCE_SUFFIXES - BINARY_SOURCE_SUFFIXES
                            or name.name.startswith(('LICENSE', 'COPYING', 'NOTICE')))):
                        _public_text(check.read(entry), 'corresponding source', allow_id_base=True)
        elif path.suffix.casefold() in TEXT_TYPES or re.search(
                r'(^|[-_.])(?:LICENSE|COPYING|NOTICE)(?:$|[.-])', path.name, flags=re.I):
            _public_text(path.read_bytes(), 'legal/source notice', allow_id_base=True)
        else:
            raise ValueError('Unreviewed file type in legal/source input')
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def _botbuy_overlay(ordinary: Path, source_zip: Path) -> list[tuple[Path, str, str]]:
    """Only BotBuy is overlaid, using the frozen backend's matching source ZIP."""
    planned = []
    with zipfile.ZipFile(source_zip) as archive:
        manifests = [name for name in archive.namelist() if name.endswith('/SOURCE_STAGE_MANIFEST.json')]
        if len(manifests) != 1:
            raise ValueError('Ordinary source ZIP lacks its sealed source manifest')
        prefix = manifests[0].removesuffix('SOURCE_STAGE_MANIFEST.json')
        sealed = json.loads(archive.read(manifests[0]).decode('utf-8'))
        if not isinstance(sealed.get('files'), dict):
            raise ValueError('Ordinary source ZIP has an invalid source manifest')
        for source in ('vendor/BotBuy/BotBuy.cs', 'vendor/BotBuy/BotBuy.csproj'):
            if prefix + source not in archive.namelist():
                raise ValueError('Ordinary source ZIP lacks corresponding BotBuy source')
        for name in ('BotBuy.dll', 'BotBuy.deps.json'):
            relative = 'vendor/BotBuy/' + name
            path = ordinary / 'backend/_internal' / relative
            if not path.is_file():
                raise ValueError('Ordinary backend lacks its BotBuy overlay: ' + name)
            expected = sealed['files'].get(relative)
            if (not isinstance(expected, str) or not re.fullmatch(r'[a-f0-9]{64}', expected)
                    or digest(path) != expected
                    or hashlib.sha256(archive.read(prefix + relative)).hexdigest() != expected):
                raise ValueError('Ordinary BotBuy overlay does not match corresponding source: ' + name)
            planned.append((path, 'addons/counterstrikesharp/plugins/BotBuy/' + name, expected))
    return planned


def build_friends(ordinary_dir: Path, compatible_runtime: Path, legal_dir: Path,
                  corresponding_source_dir: Path, output: Path, version: str) -> dict:
    if not re.fullmatch(r'[A-Za-z0-9.-]+', version):
        raise ValueError('Invalid release version')
    ordinary, mod, legal, sources = map(_root, (ordinary_dir, compatible_runtime, legal_dir, corresponding_source_dir))
    output = Path(output).absolute()
    for parent in output.parents:
        if parent.exists() and compat._is_link(parent):
            raise ValueError('Package output must not contain links')
    if output.exists() or any(output == p or output.is_relative_to(p) or p.is_relative_to(output)
                              for p in (ordinary, mod, legal, sources)):
        raise ValueError('Choose a fresh independent package output directory')
    for name in ('backend/CareerBackend.exe', 'engine/Godot.exe', 'game/project.godot'):
        if not (ordinary / name).is_file():
            raise ValueError('Ordinary Windows stage is incomplete: ' + name)
    ordinary_files = list(_files(ordinary))
    if (ordinary / 'mod').exists() or (ordinary / 'game/runtime').exists():
        raise ValueError('Ordinary Windows stage contains a mod or player runtime')
    for _, relative in ordinary_files:
        parts = tuple(p.casefold() for p in relative.parts)
        if parts[:1] == ('mod',) or parts[:2] == ('game', 'runtime'):
            raise ValueError('Ordinary Windows stage contains a mod or player runtime')
    attachments = list((ordinary / 'source').glob('*.zip'))
    if len(attachments) != 1:
        raise ValueError('Ordinary Windows stage must carry exactly one source ZIP')
    with zipfile.ZipFile(attachments[0]) as source_zip:
        if source_zip.testzip() is not None:
            raise ValueError('Corrupt ordinary corresponding-source ZIP')
    source_hash = digest(attachments[0])
    botbuy_overlay = _botbuy_overlay(ordinary, attachments[0])
    manifest = compat.load_runtime_manifest()
    verified = compat._cached_runtime(mod, manifest)
    if verified is None:
        raise ValueError('Compatible runtime does not match its current reviewed receipt')
    # Plan against the original verified receipt, then remove private fixtures.
    selected = [(path, relative) for path, relative in compat._source_plan(mod)
                if _runtime_allowed(relative.as_posix())]
    required = {name for row in manifest['components'] for name in compat._required(row)}
    if not required.issubset({relative.as_posix() for _, relative in selected}):
        raise ValueError('Runtime packaging allowlist excludes a required component')
    for path, relative in selected:
        if path.suffix.casefold() in TEXT_TYPES:
            _public_text(compat.io_path(path).read_bytes(), relative.as_posix(), allow_id_base=True)
    # Create only after the ordinary tree and the runtime receipt are verified.
    output.mkdir(parents=True, exist_ok=False)
    package_name = 'CS2Career-' + version + '-all-in-one'
    package = output / 'stage' / package_name
    shutil.copytree(ordinary, package)
    packaged_mod = package / 'mod'
    for folder in ('addons/metamod', 'addons/counterstrikesharp', 'overrides'):
        (packaged_mod / folder).mkdir(parents=True, exist_ok=True)
    files = {}
    for path, relative in selected:
        target = packaged_mod.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(compat.io_path(path), target)
        expected = compat._hash(path)
        if digest(target) != expected:
            raise ValueError('Runtime changed during package copy')
        files[relative.as_posix()] = expected
    overlays = []
    for source, relative, expected in botbuy_overlay:
        target = packaged_mod / relative
        replaced = files.get(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if digest(source) != expected or digest(target) != expected:
            raise ValueError('Ordinary BotBuy overlay changed during package copy')
        files[relative] = expected
        overlays.append({'component': 'BotBuy', 'path': relative, 'sha256': expected,
                         'replaced_sha256': replaced,
                         'from': source.relative_to(ordinary).as_posix(),
                         'corresponding_source': 'source/' + attachments[0].name,
                         'corresponding_source_sha256': source_hash})
    # No origin_mod_dir: a tester receives only portable metadata, never E:/...
    receipt = {'schema_version': 1, 'revision': manifest['revision'],
               'manifest_sha256': compat._manifest_hash(manifest),
               'components': [{key: row[key] for key in (
                   'name', 'version', 'source_kind', 'source_version', 'variant') if key in row}
                              for row in verified['components']], 'files': files}
    write_json(package / compat.RECEIPT, receipt)
    compat.validate_bundled_runtime(packaged_mod, manifest)
    _copy_notices(legal, package / 'legal/bot-runtime')
    _copy_notices(sources, package / 'third_party/bot-runtime', source_archives=True)
    for name in ('开始游戏.cmd', 'Launch-CS2Career.cmd'):
        (package / name).write_bytes(launch_cmd(bundled=True).encode('ascii'))
    (package / '兼容显卡启动.cmd').write_bytes(launch_cmd(bundled=True, compatibility=True).encode('ascii'))
    (package / '朋友测试包说明.txt').write_text(
        'CS2 Career ' + version + ' · 朋友测试包\n\n'
        '解压整个文件夹，双击“开始游戏.cmd”。Steam 和 CS2 请使用自己的安装。\n'
        '在手机或电脑设置里核对 CS2 路径，关闭 CS2 后点击“安装随包人机增强”。\n'
        '人机增强和配套组件已放在包里，首次安装也不需要重新下载。\n'
        '每位玩家都有自己的生涯、库存和设置，本包不带开发者存档。\n'
        '第三方许可与来源源码见 legal/bot-runtime 和 third_party/bot-runtime。\n', encoding='utf-8')
    if digest(package / 'source' / attachments[0].name) != source_hash:
        raise ValueError('Ordinary corresponding source changed during copy')
    record = {'schema_version': 1, 'version': version, 'distribution': 'friends-all-in-one',
              'compatibility_revision': manifest['revision'], 'built_utc': datetime.now(timezone.utc).isoformat(),
              'ordinary_source_sha256': source_hash, 'runtime_files': len(files),
              'receipt_sha256': digest(package / compat.RECEIPT), 'includes_private_saves': False,
              'components': receipt['components'], 'overlays': overlays}
    write_json(package / 'FRIENDS_PACKAGE_MANIFEST.json', record)
    final = output / 'packages' / (package_name + '.zip')
    archive(package, final, package_name)
    with zipfile.ZipFile(final) as check:
        if check.testzip() is not None:
            raise ValueError('Corrupt friends archive')
        with tempfile.TemporaryDirectory(prefix='career-friends-archive-') as extracted:
            extraction_root = Path(extracted)
            if not extraction_root.is_absolute() or not extraction_root.name.startswith('career-friends-archive-'):
                raise ValueError('Invalid archive verification temporary directory')
            try:
                check.extractall(compat.io_path(extraction_root))
                restored = compat.validate_bundled_runtime(extraction_root / package_name / 'mod', manifest)
                if restored != receipt:
                    raise ValueError('Friends archive runtime differs from its verified stage')
            finally:
                # .NET payloads may exceed MAX_PATH after adding the package
                # prefix. Clean our verified temporary root with the same
                # extended namespace used for extraction on Windows.
                shutil.rmtree(compat.io_path(extraction_root))
    record['archive'] = {'name': final.name, 'sha256': digest(final), 'bytes': final.stat().st_size}
    write_json(output / 'packages/FRIENDS_BUILD_MANIFEST.json', record)
    (output / 'packages/SHA256SUMS.txt').write_text(record['archive']['sha256'] + '  ' + final.name + '\n', encoding='ascii')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('ordinary-dir', 'compatible-runtime', 'legal-dir', 'corresponding-source-dir', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    print(json.dumps(build_friends(args.ordinary_dir, args.compatible_runtime, args.legal_dir,
                     args.corresponding_source_dir, args.output, args.version), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
