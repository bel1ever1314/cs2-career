"""Prepare an immutable compatibility runtime only for an explicit install.

The selected release and the actual game are read-only here. Fixed official
archives are checksum-verified, merged in an isolated cache, and handed to the
existing backed-up installer. Merely importing this module does no discovery,
network access, or filesystem writes.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
from urllib.parse import urlsplit
import urllib.request
from uuid import uuid4
import zipfile

from cs2career.paths import io_path


MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_EXPANDED_BYTES = 1024 * 1024 * 1024
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_FILES = 30000
MAX_RECEIPT_BYTES = 1024 * 1024
RECEIPT = 'RUNTIME_COMPAT_RECEIPT.json'
_OFFICIAL_REPOS = frozenset(('alliedmodders/metamod-source', 'roflmuffin/counterstrikesharp',
                           'xbribo/cs2-bot-controller', 'xbribo/cs2-bot-hider',
                           'xbribo/cs2-bot-vision', 'ed0ard/cs2-bot-randomizer',
                           'ed0ard/cs2-bot-improver'))
_PRIVATE_DIRS = frozenset(('inventories', 'logs', 'backup', 'backups', 'save', 'saves',
                         'plugins_off', '.git', 'demos', 'captures'))
_PRIVATE_PLUGINS = frozenset(('careermatch', 'inventorysimulator', 'invsimcareer'))
_PRIVATE_NAMES = frozenset(('bot_info.json', 'botprofile.db', 'botprofile.vpk',
                           'inventories.json', 'autoexec.cfg', 'config.cfg', 'invsim_career.cfg',
                           'match_request.json', 'match_result.json', 'match_result.best.json',
                           'tactical_playbook.json', 'console.log'))
_PRESERVABLE_CONFIGS = frozenset(('addons/bothider/config.json', 'addons/botvision/config.json'))
_OVERRIDE_RUNTIME_SUFFIXES = ('.vdata', '.vdata_c', '.kv3', '.bt', '.bt_c')


def _normal_path(path: Path | str) -> Path:
    """Keep cache identities, comparisons and receipts out of Win32's I/O namespace."""
    text = os.fspath(path)
    if os.name == 'nt':
        if text.startswith('\\\\?\\UNC\\'):
            text = '\\\\' + text[8:]
        elif text.startswith('\\\\?\\'):
            text = text[4:]
    return Path(text)


def _hash(path: Path) -> str:
    with io_path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _is_link(path: Path) -> bool:
    entry = io_path(path).lstat()
    return io_path(path).is_symlink() or bool(getattr(entry, 'st_file_attributes', 0) &
                                    getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def _relative(raw: str) -> PurePosixPath:
    """ZIP names must also be safe on case-insensitive Windows filesystems."""
    if not isinstance(raw, str) or '\x00' in raw:
        raise ValueError('兼容组件包含无效的文件名。')
    text = raw.replace('\\', '/').rstrip('/')
    parts = text.split('/')
    if not text or text.startswith('/') or any(not part or part in ('.', '..') for part in parts):
        raise ValueError('兼容组件文件超出允许目录。')
    for part in parts:
        if any(char in part for char in '<>:"|?*') or part.rstrip(' .') != part:
            raise ValueError('兼容组件包含 Windows 不支持的文件名。')
        base = part.split('.', 1)[0].upper()
        if base in ('CON', 'PRN', 'AUX', 'NUL') or re.fullmatch(r'(COM|LPT)[1-9]', base):
            raise ValueError('兼容组件包含 Windows 保留文件名。')
    return PurePosixPath(text)


def _payload_allowed(relative: PurePosixPath, *, directory: bool = False) -> bool:
    parts = tuple(part.casefold() for part in relative.parts)
    if not parts or parts[0] not in ('addons', 'cfg', 'overrides') or any(part in _PRIVATE_DIRS for part in parts):
        return False
    if any(part in _PRIVATE_PLUGINS for part in parts) or parts[-1] in _PRIVATE_NAMES:
        return False
    name = parts[-1]
    # Overrides can hold game-consumed behavior trees, but never a copied bot
    # roster, active career profile, backup, launcher, or arbitrary executable.
    if parts[0] == 'overrides':
        if len(parts) == 1:
            return directory
        if parts[1] != 'scripts':
            return False
        return directory or name.endswith(_OVERRIDE_RUNTIME_SUFFIXES)
    if parts[0] == 'cfg' and not directory and not name.endswith('.cfg'):
        return False
    if name.endswith('.exe') and parts[:3] != ('addons', 'counterstrikesharp', 'dotnet'):
        return False
    return not (name.endswith(('.pdb', '.log', '.bak', '.db', '.vpk', '.zip', '.tmp'))
                or '.previous.' in name or '.career-backup' in name
                or name.startswith(('inventories.', 'inventory-simulator', 'match_result', 'match_request')))


def _under(relative: PurePosixPath, prefixes: list[str]) -> bool:
    for raw in prefixes:
        prefix = _relative(raw.removesuffix('/**')).parts
        if tuple(part.casefold() for part in relative.parts[:len(prefix)]) == tuple(part.casefold() for part in prefix):
            return True
    return False


def _required(component: dict) -> list[str]:
    return component.get('required_paths', component.get('required_files', []))


def load_runtime_manifest() -> dict:
    from cs2career.paths import data_file
    data = json.loads(io_path(data_file('cs2_runtime_compat.json')).read_text('utf-8-sig'))
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('人机增强兼容清单格式不正确。')
    if not isinstance(data.get('revision'), str) or not data['revision']:
        raise ValueError('人机增强兼容清单缺少版本。')
    components = data.get('components')
    if not isinstance(components, list) or not components:
        raise ValueError('人机增强兼容清单缺少组件。')
    names = set()
    for component in components:
        if not isinstance(component, dict) or not isinstance(component.get('name'), str) or not component['name']:
            raise ValueError('兼容组件名称不正确。')
        if component['name'] in names:
            raise ValueError('兼容组件名称重复。')
        names.add(component['name'])
        if not isinstance(component.get('version'), str):
            raise ValueError('兼容组件缺少版本。')
        sha = component.get('sha256', '')
        if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', sha):
            raise ValueError('兼容组件缺少固定校验值。')
        if 'size' in component and (type(component['size']) is not int
                                   or not 0 < component['size'] <= MAX_ARCHIVE_BYTES):
            raise ValueError('兼容组件下载大小不正确。')
        url = urlsplit(component.get('url', ''))
        if url.scheme != 'https' or url.hostname != 'github.com' or url.username or url.password or url.query or url.fragment:
            raise ValueError('兼容组件必须使用固定的官方 GitHub 下载地址。')
        if '/releases/download/' not in url.path or not url.path.casefold().endswith('.zip'):
            raise ValueError('兼容组件下载地址不是固定的 ZIP 发行包。')
        if '/'.join(url.path.strip('/').split('/')[:2]).casefold() not in _OFFICIAL_REPOS:
            raise ValueError('兼容组件来自未知的上游项目。')
        for field in ('strip_prefix', 'target_prefix'):
            if component.get(field):
                _relative(component[field])
        for field in ('replace_paths', 'allow_paths', 'required_paths', 'required_files', 'preserve_paths'):
            if not isinstance(component.get(field, []), list) or any(not isinstance(item, str) for item in component.get(field, [])):
                raise ValueError('兼容组件路径清单格式不正确。')
            for relative in component.get(field, []):
                _relative(relative.removesuffix('/**'))
        for relative in _required(component):
            if not _payload_allowed(_relative(relative)):
                raise ValueError('兼容清单引用了非运行文件。')
        # Only reviewed user-facing settings can win over an archive default.
        # A malformed manifest must never preserve a legacy DLL/API/gamedata.
        for relative in component.get('preserve_paths', []):
            if _relative(relative).as_posix().casefold() not in _PRESERVABLE_CONFIGS:
                raise ValueError('兼容清单只能保留人机增强设置，不能保留旧运行组件。')
    return data


def _manifest_hash(manifest: dict) -> str:
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def _download_archive(url: str, destination: Path) -> None:
    """No upstream executables are started; downloads are bounded and streamed."""
    request = urllib.request.Request(url, headers={'User-Agent':'CS2Career-Compatibility-Installer'})
    with urllib.request.urlopen(request, timeout=60) as response, io_path(destination).open('xb') as stream:
        final = urlsplit(response.geturl())
        if final.scheme != 'https' or final.hostname not in ('github.com', 'release-assets.githubusercontent.com',
                                                            'objects.githubusercontent.com'):
            raise ValueError('兼容组件下载跳转到未知地址。')
        length = 0
        while block := response.read(1024 * 1024):
            length += len(block)
            if length > MAX_ARCHIVE_BYTES:
                raise ValueError('兼容组件下载大小超出范围。')
            stream.write(block)


def _artifact(cache: Path, component: dict) -> Path:
    downloads = cache / 'downloads'
    if io_path(downloads).exists() and _is_link(downloads):
        raise ValueError('兼容下载缓存含目录链接。')
    io_path(downloads).mkdir(exist_ok=True)
    expected = component['sha256'].lower()
    target = downloads / (expected + '.zip')
    if io_path(target).exists():
        if _is_link(target) or not io_path(target).is_file():
            raise ValueError('兼容下载缓存不是普通文件。')
        if (not component.get('size') or io_path(target).stat().st_size == component['size']) and _hash(target) == expected:
            return target
    pending = downloads / ('.download-' + uuid4().hex + '.zip')
    try:
        _download_archive(component['url'], pending)
        if not io_path(pending).is_file() or _is_link(pending) or io_path(pending).stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError('兼容组件下载文件不正确。')
        if _hash(pending) != expected:
            raise ValueError('兼容组件校验失败：' + component['name'] + '，没有安装。')
        if component.get('size') and io_path(pending).stat().st_size != component['size']:
            raise ValueError('兼容组件下载大小不符：' + component['name'] + '，没有安装。')
        os.replace(io_path(pending), io_path(target))
    finally:
        io_path(pending).unlink(missing_ok=True)
    return target


def _archive_plan(archive: Path, component: dict) -> list[tuple[zipfile.ZipInfo, PurePosixPath]]:
    entries, names, kinds, total = [], set(), {}, 0
    prefix = _relative(component['strip_prefix']).parts if component.get('strip_prefix') else ()
    target_prefix = _relative(component['target_prefix']) if component.get('target_prefix') else None
    with zipfile.ZipFile(io_path(archive)) as pack:
        if len(pack.infolist()) > MAX_FILES:
            raise ValueError('兼容组件包含过多文件。')
        for entry in pack.infolist():
            relative = _relative(entry.filename)
            key = relative.as_posix().casefold()
            is_dir = entry.is_dir() or entry.filename.endswith('\\')
            kind = stat.S_IFMT(entry.external_attr >> 16)
            if entry.flag_bits & 1 or kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError('兼容组件包含链接或加密文件。')
            if key in names:
                raise ValueError('兼容组件包含重复文件名。')
            names.add(key)
            kinds[key] = is_dir
            if not is_dir:
                total += entry.file_size
                if entry.file_size > MAX_FILE_BYTES or total > MAX_EXPANDED_BYTES:
                    raise ValueError('兼容组件解压大小超出范围。')
            if prefix:
                if relative.parts[:len(prefix)] != prefix or len(relative.parts) <= len(prefix):
                    continue
                relative = PurePosixPath(*relative.parts[len(prefix):])
            if target_prefix:
                relative = target_prefix / relative
            if not is_dir and _payload_allowed(relative) and (not component.get('allow_paths') or _under(relative, component['allow_paths'])):
                entries.append((entry, relative))
        for key in kinds:
            for parent in PurePosixPath(key).parents:
                if str(parent) != '.' and parent.as_posix() in kinds and not kinds[parent.as_posix()]:
                    raise ValueError('兼容组件文件与目录冲突。')
    if not entries:
        raise ValueError('兼容组件没有可安装的运行文件：' + component['name'])
    projected = [relative.as_posix().casefold() for _, relative in entries]
    if len(projected) != len(set(projected)):
        raise ValueError('兼容组件目标文件重复。')
    if any(_relative(relative).as_posix().casefold() not in projected for relative in _required(component)):
        raise ValueError('兼容发行包缺少必需文件：' + component['name'])
    return entries


def _source_plan(mod: Path) -> list[tuple[Path, PurePosixPath]]:
    mod = _normal_path(mod)
    addons = mod / 'addons'
    if not io_path(addons).is_dir() or _is_link(addons):
        raise ValueError('人机增强来源缺少普通 addons 目录。')
    entries, total = [], 0
    for area in (addons, mod / 'cfg', mod / 'overrides'):
        if not io_path(area).exists():
            continue
        if _is_link(area) or not io_path(area).is_dir():
            raise ValueError('人机增强运行文件含目录链接。')
        for directory, folders, files in os.walk(io_path(area), topdown=True, followlinks=False):
            base = _normal_path(directory)
            accepted = []
            for folder in sorted(folders):
                relative = _relative((base / folder).relative_to(mod).as_posix())
                if not _payload_allowed(relative, directory=True):
                    continue
                if _is_link(base / folder):
                    raise ValueError('人机增强运行文件含目录链接。')
                accepted.append(folder)
            folders[:] = accepted
            for name in sorted(files):
                source = base / name
                relative = _relative(source.relative_to(mod).as_posix())
                if not _payload_allowed(relative):
                    continue
                if _is_link(source) or not io_path(source).is_file():
                    raise ValueError('人机增强运行文件含链接。')
                total += io_path(source).stat().st_size
                if io_path(source).stat().st_size > MAX_FILE_BYTES or total > MAX_EXPANDED_BYTES or len(entries) >= MAX_FILES:
                    raise ValueError('人机增强运行文件大小超出范围。')
                entries.append((source, relative))
    return sorted(entries, key=lambda row: row[1].as_posix().casefold())


def _read_receipt(mod: Path) -> dict | None:
    path = mod.parent / RECEIPT
    try:
        if not io_path(path).is_file() or _is_link(path) or io_path(path).stat().st_size > MAX_RECEIPT_BYTES:
            return None
        with io_path(path).open('rb') as stream:
            raw = stream.read(MAX_RECEIPT_BYTES + 1)
        if len(raw) > MAX_RECEIPT_BYTES:
            return None
        value = json.loads(raw.decode('utf-8'))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) and value.get('schema_version') == 1 else None


def runtime_context(mod: Path) -> dict:
    """Cheap version hints, not runtime validation or a game-load claim.

    Status refreshes never enumerate payload files, hash DLLs, or download.
    The explicit installer still performs the complete checks in prepare_runtime.
    """
    result = {'source_ready':False, 'current':False, 'revision':'',
              'expected_revision':'', 'components':[]}
    try:
        mod = _normal_path(mod)
        if not mod.is_absolute() or not io_path(mod).is_dir() or _is_link(mod):
            return result
        result['source_ready'] = all(io_path(mod / name).is_dir() and not _is_link(mod / name)
                                     for name in ('addons/metamod', 'addons/counterstrikesharp', 'overrides'))
        manifest = load_runtime_manifest()
        result['expected_revision'] = manifest['revision']
        receipt = _read_receipt(mod)
        if not receipt:
            return result
        revision = receipt.get('revision')
        if isinstance(revision, str) and len(revision) <= 128:
            result['revision'] = revision
        components = receipt.get('components', [])
        if isinstance(components, list):
            result['components'] = [{'name':entry['name'], 'version':entry['version']}
                                    for entry in components[:64] if isinstance(entry, dict)
                                    and isinstance(entry.get('name'), str) and len(entry['name']) <= 128
                                    and isinstance(entry.get('version'), str) and len(entry['version']) <= 128]
        result['current'] = bool(result['source_ready'] and result['revision'] == manifest['revision']
                                 and receipt.get('manifest_sha256') == _manifest_hash(manifest))
    except (OSError, ValueError, TypeError):
        pass
    return result


def _cached_runtime(mod: Path, manifest: dict) -> dict | None:
    receipt = _read_receipt(mod)
    if not receipt or receipt.get('manifest_sha256') != _manifest_hash(manifest) or not isinstance(receipt.get('files'), dict):
        return None
    if not receipt['files']:
        return None
    try:
        for relative, sha in receipt['files'].items():
            name = _relative(relative)
            target = mod.joinpath(*name.parts)
            if not _payload_allowed(name) or not io_path(target).is_file() or _is_link(target) or _hash(target) != sha:
                return None
        actual = {relative.as_posix() for _, relative in _source_plan(mod)}
        if actual != set(receipt['files']):
            return None
        for folder in ('addons/metamod', 'addons/counterstrikesharp', 'overrides'):
            if not io_path(mod / folder).is_dir() or _is_link(mod / folder):
                return None
    except (OSError, ValueError):
        return None
    return {'mod_dir':str(mod), 'origin_mod_dir':receipt.get('origin_mod_dir', str(mod)),
            'revision':manifest['revision'], 'components':deepcopy(receipt.get('components', [])), 'cache_hit':True}


def bundled_payload_allowed(relative: PurePosixPath, *, directory: bool = False) -> bool:
    """An offline bundle never carries account/admin fixtures or a Panel."""
    parts = tuple(part.casefold() for part in relative.parts)
    excluded = {'owner.txt', 'admins.json', 'admin_groups.json', 'admin_overrides.json',
                'admins.example.json', 'admin_groups.example.json', 'admin_overrides.example.json',
                'tactical_routes.json', 'gameinfo.gi', 'gameinfo_branchspecific.gi'}
    return (_payload_allowed(relative, directory=directory)
            and not any('panel' in part for part in parts)
            and parts[-1] not in excluded)


def validate_bundled_runtime(mod: Path, manifest: dict | None = None) -> dict | None:
    """Validate a *complete* portable payload. Missing receipts mean legacy mode.

    Unlike the selected-release filter, every bundle entry must be eligible: an
    extra private file, stale receipt or altered DLL is an error, not a reason to
    silently download a replacement. No files are changed by this check.
    """
    mod = _normal_path(mod)
    receipt_path = mod.parent / RECEIPT
    if not io_path(receipt_path).exists() and not io_path(receipt_path).is_symlink():
        return None
    manifest = manifest or load_runtime_manifest()
    receipt = _read_receipt(mod)
    components = [{key: row[key] for key in ('name', 'version')} for row in manifest['components']]
    if (not receipt or receipt.get('revision') != manifest['revision']
            or receipt.get('manifest_sha256') != _manifest_hash(manifest)
            or receipt.get('components') != components
            or not isinstance(receipt.get('files'), dict) or not receipt['files']):
        raise ValueError('随包人机增强校验清单损坏或版本不匹配，未安装。')
    if not mod.is_absolute() or not io_path(mod).is_dir() or _is_link(mod):
        raise ValueError('随包人机增强目录无效或含链接，未安装。')
    actual, case_names, total = set(), set(), 0
    for directory, folders, names in os.walk(io_path(mod), topdown=True, followlinks=False):
        base = _normal_path(directory)
        for name in (*folders, *names):
            path = base / name
            relative = _relative(path.relative_to(mod).as_posix())
            if _is_link(path) or not bundled_payload_allowed(relative, directory=name in folders):
                raise ValueError('随包人机增强包含非运行文件或链接，未安装：' + relative.as_posix())
            key = relative.as_posix().casefold()
            if key in case_names:
                raise ValueError('随包人机增强文件名重复，未安装。')
            case_names.add(key)
            if name in folders:
                continue
            if not io_path(path).is_file():
                raise ValueError('随包人机增强包含非普通文件，未安装。')
            size = io_path(path).stat().st_size
            total += size
            if size > MAX_FILE_BYTES or total > MAX_EXPANDED_BYTES or len(actual) >= MAX_FILES:
                raise ValueError('随包人机增强运行文件大小超出范围，未安装。')
            relative_name = relative.as_posix()
            expected = receipt['files'].get(relative_name)
            if not isinstance(expected, str) or not re.fullmatch(r'[a-f0-9]{64}', expected) or _hash(path) != expected:
                raise ValueError('随包人机增强文件校验失败，未安装：' + relative_name)
            actual.add(relative_name)
    if actual != set(receipt['files']):
        raise ValueError('随包人机增强文件不完整，未安装。')
    required = {name for component in manifest['components'] for name in _required(component)}
    if not required.issubset(actual):
        raise ValueError('随包人机增强缺少必需组件，未安装。')
    for folder in ('addons/metamod', 'addons/counterstrikesharp', 'overrides'):
        if not io_path(mod / folder).is_dir() or _is_link(mod / folder):
            raise ValueError('随包人机增强目录不完整，未安装。')
    return {'schema_version': 1, 'revision': manifest['revision'],
            'manifest_sha256': _manifest_hash(manifest), 'components': components,
            'files': dict(sorted(receipt['files'].items()))}


def seed_bundled_runtime(root: Path, mod: Path) -> Path:
    """Explicit bundle installation seeds a verified atomic offline cache copy."""
    root, mod = _normal_path(root), _normal_path(mod)
    receipt = validate_bundled_runtime(mod)
    if receipt is None:
        return mod
    if not root.is_absolute() or not io_path(root).is_dir() or _is_link(root) or root == Path(root.anchor):
        raise ValueError('随包人机增强缓存目录无效。')
    cache = root / 'runtime-cache'
    if cache == mod or cache.is_relative_to(mod):
        raise ValueError('随包人机增强缓存不能与来源重叠。')
    if io_path(cache).exists() and _is_link(cache):
        raise ValueError('随包人机增强缓存含链接。')
    identity = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode('utf-8')).hexdigest()
    final = cache / ('bundle-' + identity)
    io_path(cache).mkdir(exist_ok=True)
    if io_path(final).exists():
        if _is_link(final):
            raise ValueError('随包人机增强缓存含链接。')
        existing = validate_bundled_runtime(final / 'runtime')
        if existing == receipt:
            return final / 'runtime'
        raise ValueError('随包人机增强已有缓存损坏，未安装。')
    staging = _normal_path(tempfile.mkdtemp(prefix='.bundle-', dir=io_path(cache)))
    try:
        runtime = staging / 'runtime'
        io_path(runtime).mkdir()
        for folder in ('addons/metamod', 'addons/counterstrikesharp', 'overrides'):
            io_path(runtime / folder).mkdir(parents=True, exist_ok=True)
        for relative, expected in receipt['files'].items():
            name = _relative(relative)
            source, target = mod.joinpath(*name.parts), runtime.joinpath(*name.parts)
            io_path(target.parent).mkdir(parents=True, exist_ok=True)
            shutil.copy2(io_path(source), io_path(target))
            if _hash(source) != expected or _hash(target) != expected:
                raise ValueError('随包人机增强在复制期间发生变化，未安装。')
        io_path(staging / RECEIPT).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), 'utf-8')
        validate_bundled_runtime(runtime)
        os.replace(io_path(staging), io_path(final))
        return final / 'runtime'
    finally:
        if io_path(staging).exists() and staging.parent == cache and staging.name.startswith('.bundle-'):
            shutil.rmtree(io_path(staging))


def prepare_runtime(root: Path, mod: Path, game: Path) -> dict:
    """Only explicit installation calls this; nothing is written to mod or game."""
    root, mod, game = _normal_path(root), _normal_path(mod), _normal_path(game)
    if not all(path.is_absolute() for path in (root, mod, game)):
        raise ValueError('兼容安装需要完整的本机目录。')
    if not io_path(root).is_dir() or not io_path(mod).is_dir() or _is_link(root) or _is_link(mod):
        raise ValueError('兼容安装目录不存在或含链接。')
    root, mod, game = (_normal_path(io_path(path).resolve()) for path in (root, mod, game))
    if root == Path(root.anchor) or mod == game or mod.is_relative_to(game) or game.is_relative_to(mod):
        raise ValueError('兼容来源不能与游戏目录重叠。')
    cache = root / 'runtime-cache'
    if cache == mod or cache.is_relative_to(mod) or cache == game or cache.is_relative_to(game) or game.is_relative_to(cache):
        raise ValueError('兼容缓存不能与来源或游戏目录重叠。')
    if io_path(cache).exists() and _is_link(cache):
        raise ValueError('兼容缓存含目录链接。')
    manifest = load_runtime_manifest()
    if mod.is_relative_to(cache) and mod.name == 'runtime':
        hit = _cached_runtime(mod, manifest)
        if hit:
            return hit
    replaced = [relative for component in manifest['components'] for relative in component.get('replace_paths', [])]
    source_plan = [(source, relative) for source, relative in _source_plan(mod) if not _under(relative, replaced)]
    source_hashes = {relative.as_posix():_hash(source) for source, relative in source_plan}
    identity = hashlib.sha256((_manifest_hash(manifest) + json.dumps(source_hashes, sort_keys=True)).encode('utf-8')).hexdigest()
    io_path(cache).mkdir(exist_ok=True)
    final = cache / identity
    if io_path(final).exists() and _is_link(final):
        raise ValueError('兼容运行缓存含目录链接。')
    hit = _cached_runtime(final / 'runtime', manifest)
    if hit:
        return hit
    archives = [(component, _artifact(cache, component)) for component in manifest['components']]
    plans = [(component, archive, _archive_plan(archive, component)) for component, archive in archives]
    staging = _normal_path(tempfile.mkdtemp(prefix='.prepare-', dir=io_path(cache)))
    runtime = staging / 'runtime'
    try:
        io_path(runtime).mkdir()
        for source, relative in source_plan:
            target = runtime.joinpath(*relative.parts)
            io_path(target.parent).mkdir(parents=True, exist_ok=True)
            shutil.copy2(io_path(source), io_path(target))
            if _hash(target) != source_hashes[relative.as_posix()] or _hash(source) != source_hashes[relative.as_posix()]:
                raise OSError('人机增强来源在准备期间发生变化，没有安装。')
        # Every official archive is applied last. The old source is never
        # copied over an updated native DLL, managed API, or gamedata.
        for component, archive, plan in plans:
            preserved = {_relative(name).as_posix().casefold() for name in component.get('preserve_paths', [])}
            with zipfile.ZipFile(io_path(archive)) as pack:
                for entry, relative in plan:
                    target = runtime.joinpath(*relative.parts)
                    if relative.as_posix().casefold() in preserved and io_path(target).is_file():
                        continue
                    io_path(target.parent).mkdir(parents=True, exist_ok=True)
                    with pack.open(entry) as source, io_path(target).open('wb') as output:
                        shutil.copyfileobj(source, output, 1024 * 1024)
                    if io_path(target).stat().st_size != entry.file_size:
                        raise ValueError('兼容组件文件长度不符，没有安装。')
            for relative in _required(component):
                if not io_path(runtime.joinpath(*_relative(relative).parts)).is_file():
                    raise ValueError('兼容组件缺少必需文件：' + component['name'])
        io_path(runtime / 'overrides').mkdir(exist_ok=True)
        for folder in ('addons/metamod', 'addons/counterstrikesharp'):
            if not io_path(runtime / folder).is_dir():
                raise ValueError('兼容运行组件不完整，没有安装。')
        files = {relative.as_posix():_hash(source) for source, relative in _source_plan(runtime)}
        components = [{key:component[key] for key in ('name', 'version')} for component in manifest['components']]
        receipt = {'schema_version':1, 'revision':manifest['revision'], 'manifest_sha256':_manifest_hash(manifest),
                   'origin_mod_dir':str(mod), 'components':components, 'files':files}
        io_path(staging / RECEIPT).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), 'utf-8')
        if io_path(final).exists():
            final = cache / (identity + '-' + uuid4().hex[:12])
        os.replace(io_path(staging), io_path(final))
        return {'mod_dir':str(final / 'runtime'), 'origin_mod_dir':str(mod), 'revision':manifest['revision'],
                'components':components, 'cache_hit':False}
    finally:
        if io_path(staging).exists() and staging.parent == cache and staging.name.startswith('.prepare-'):
            shutil.rmtree(io_path(staging))
