"""Build local, privacy-filtered Windows 3D preview distributions.

Run on the build computer; the resulting runtime needs neither Python nor Godot
installed. Steam and a legitimate CS2 installation remain player prerequisites.
Never installs anything into a game or publishes a GitHub release.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.7.0-preview.1'
MODELS = ('cozy_room.glb', 'chicken_club.glb', 'player_chicken.glb', 'major_walk.glb')
ENGINE_VERSION = '4.7.2-stable'
ENGINE_LEGAL_HASHES = {
    'Godot-LICENSE.txt': 'b0435e3b3e4e55238f05f4b306f30524a1b2e20147810d436eaa554fa6855c80',
    'Godot-COPYRIGHT.txt': 'cb1980c88089573bcacd7221d777c689bb8bbd778799f24c27fca0fe5f774d6d',
}
RUNTIME_VENDOR_FILES = (
    'CareerMatch/CareerMatch.dll', 'CareerMatch/CareerMatch.deps.json',
    'BotBuy/BotBuy.dll', 'BotBuy/BotBuy.deps.json',
    'InvsimCareer/InvsimCareer.dll', 'InvsimCareer/InvsimCareer.deps.json',
    'InventorySimulator/gamedata/inventory-simulator.json',
    'InventorySimulator/plugins/InventorySimulator/InventorySimulator.dll',
    'InventorySimulator/plugins/InventorySimulator/InventorySimulator.deps.json',
    'InventorySimulator/plugins/InventorySimulator/lang/zh-Hans.json',
    'InventorySimulator/plugins/InventorySimulator/lang/pt-BR.json',
    'InventorySimulator/plugins/InventorySimulator/lang/en.json',
)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def seal_source_manifest(source, report, *, ordinary_only=False):
    """Seal after resource/legal overlays, not before the final public tree exists."""
    files = {p.relative_to(source).as_posix(): digest(p) for p in sorted(source.rglob('*'))
             if p.is_file() and p.name != 'SOURCE_STAGE_MANIFEST.json'}
    overlays = ['portable-public-media', 'preview-notice'] if ordinary_only else [
        'reviewed-inventory-gamedata', 'portable-public-media',
        'dependency-corresponding-source', 'preview-notice']
    report = {**report, 'source_files': len(files), 'files': files,
              'post_stage_overlays': overlays}
    if ordinary_only:
        report.update(distribution='ordinary-unbundled', bundled_bot_runtime=False)
    write_json(source / 'SOURCE_STAGE_MANIFEST.json', report)
    return report


def relative_media(source, media):
    """Copy only manifest-selected public artwork, never an entire save/cache."""
    cfg = json.loads(Path(source).read_text('utf-8-sig'))
    media = Path(media)
    media.mkdir(parents=True, exist_ok=False)
    maps = {}
    for name, row in cfg['map_backgrounds'].items():
        original = Path(row['path'])
        target = media / 'maps' / (name + original.suffix)
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(original, target)
        maps[name] = {**row, 'path': '../../media/maps/' + target.name}
    original_manifest = Path(cfg['team_manifest'])
    teams = json.loads(original_manifest.read_text('utf-8-sig'))
    for row in teams['team_backgrounds'].values():
        for key in ('path', 'original_path'):
            if not row.get(key):
                continue
            original = Path(row[key])
            target = media / 'teams' / ('source' if key == 'original_path' else '') / original.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
            row[key] = target.relative_to(media / 'teams').as_posix()
    write_json(media / 'teams' / 'team-media.json', teams)
    art = json.loads((ROOT / 'cs2career/data/skin_art.json').read_text('utf-8-sig'))
    count = 0
    for row in art['items'].values():
        if row.get('status') != 'mapped' or not row.get('url'):
            continue
        name = hashlib.sha256(row['url'].encode()).hexdigest() + '.png'
        original = next((Path(folder) / name for folder in cfg['skin_cache_roots']
                         if (Path(folder) / name).is_file()), None)
        target = media / 'skin_art' / name
        if original and not target.exists():
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(original, target)
            count += 1
    return {'schema_version': 1, 'team_manifest': '../../media/teams/team-media.json',
            'skin_cache_roots': ['../../media/skin_art'], 'map_backgrounds': maps}, count


def download_legal(engine, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('LICENSE.txt', 'COPYRIGHT.txt'):
        url = f'https://raw.githubusercontent.com/godotengine/godot/{ENGINE_VERSION}/{name}'
        with urllib.request.urlopen(url, timeout=90) as response:
            content = response.read()
        if not content or b'Godot' not in content:
            raise ValueError('Invalid Godot license response')
        (destination / ('Godot-' + name)).write_bytes(content)
    write_json(destination / 'Godot-version.json', {
        'version': ENGINE_VERSION, 'executable_sha256': digest(engine),
        'source': f'https://github.com/godotengine/godot/tree/{ENGINE_VERSION}',
        'distribution': 'official Windows editor binary used as portable project runner'})


def copy_engine_legal(engine, destination, cache):
    """Reuse verified license texts for the exact engine, without networking."""
    cache, destination = Path(cache), Path(destination)
    metadata = json.loads((cache / 'Godot-version.json').read_text('utf-8-sig'))
    if metadata.get('version') != ENGINE_VERSION or metadata.get('executable_sha256') != digest(engine):
        raise ValueError('Cached Godot licenses do not match the selected engine')
    for name, expected in ENGINE_LEGAL_HASHES.items():
        if digest(cache / name) != expected:
            raise ValueError('Cached Godot license checksum mismatch: ' + name)
    # Validate the complete cache before creating any output.
    destination.mkdir(parents=True, exist_ok=False)
    for name in (*ENGINE_LEGAL_HASHES, 'Godot-version.json'):
        shutil.copy2(cache / name, destination / name)


def stage_runtime_vendor(source, destination):
    """Copy only installable plugin payloads; full vendor sources stay in the source ZIP."""
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise FileExistsError('Choose a fresh runtime vendor stage')
    files = []
    for relative in RUNTIME_VENDOR_FILES:
        path = source / 'vendor' / relative
        for candidate in (path, *path.parents):
            if candidate.is_symlink() or getattr(candidate, 'is_junction', lambda: False)():
                raise ValueError('Linked vendor runtime input: ' + relative)
            if candidate == source:
                break
        if not path.is_file():
            raise FileNotFoundError('Missing required vendor runtime: ' + relative)
        files.append((relative, path, digest(path)))
    destination.mkdir(parents=True, exist_ok=False)
    for relative, path, expected in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        if digest(target) != expected:
            raise ValueError('Vendor runtime copy checksum mismatch: ' + relative)
    return destination


def freeze_backend(source, build):
    """Build from sanitized sources, not from the developer's personal path."""
    build.mkdir(parents=True, exist_ok=True)
    runtime_vendor = stage_runtime_vendor(source, build / 'runtime-vendor')
    sep = ';' if os.name == 'nt' else ':'
    args = [sys.executable, '-m', 'PyInstaller', str(source / 'tools/career3d_backend_main.py'),
            '--name', 'CareerBackend', '--onedir', '--console', '--noconfirm', '--clean',
            '--distpath', str(build / 'dist'), '--workpath', str(build / 'work'),
            '--specpath', str(build), '--paths', str(source), '--collect-all', 'orjson']
    for module in source.joinpath('tools').glob('career3d_*.py'):
        args += ['--hidden-import', 'tools.' + module.stem]
    args += ['--add-data', str(runtime_vendor) + sep + 'vendor']
    for relative, dest in (
        ('cs2career/data', 'data'), ('cs2career/web/static', 'web/static'),
        ('licenses', 'licenses'), ('LICENSE', '.'),
        ('work/career_rts/data', 'work/career_rts/data'),
        ('work/career3d_redesign/data/locale_en.json', 'work/career3d_redesign/data'),
        ('work/career3d_redesign/data/phone_social.json', 'work/career3d_redesign/data')):
        args += ['--add-data', str(source / relative) + sep + dest]
    for module in ('pytest', 'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
                   'numpy', 'pandas', 'matplotlib', 'webview', 'pythonnet', 'clr_loader'):
        args += ['--exclude-module', module]
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['TEMP'] = env['TMP'] = str(build / 'temp')
    (build / 'temp').mkdir(exist_ok=True)
    with (build / 'freeze.log').open('w', encoding='utf-8') as log:
        subprocess.run(args, cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    return build / 'dist/CareerBackend'


def stage_game(source, target, engine, media_config, *, version=VERSION):
    project = source / 'work/career3d_redesign'
    target.mkdir(parents=True, exist_ok=False)
    for item in project.iterdir():
        if item.is_dir() and item.name in ('scripts', 'data', 'rts', 'fonts', 'scenes'):
            shutil.copytree(item, target / item.name)
        elif item.is_file() and item.suffix in ('.godot', '.tscn', '.gd', '.txt', '.uid'):
            shutil.copy2(item, target / item.name)
    for name in MODELS:
        target.joinpath('assets').mkdir(exist_ok=True)
        shutil.copy2(project / 'assets' / name, target / 'assets' / name)
    for item in (project / 'assets/audio').iterdir():
        if item.suffix in ('.ogg', '.json', '.txt', '.md'):
            target.joinpath('assets/audio').mkdir(exist_ok=True)
            shutil.copy2(item, target / 'assets/audio' / item.name)
    write_json(target / 'data/career_link.json', {
        'schema_version': 1, 'backend_exe': '../backend/CareerBackend.exe',
        'repo_root': '', 'python': '', 'data_dir': 'runtime/career',
        'real_seconds_per_game_minute': 1.0, 'start_hour': 8})
    write_json(target / 'data/media.json', media_config)
    project_file = target / 'project.godot'
    text = project_file.read_text('utf-8').replace(
        'config/name="CS2 Career · 俱乐部生活样板"',
        f'config/name="CS2 Career {version} · 3D 测试版"')
    project_file.write_text(text, encoding='utf-8')
    # Import in the distributed location; .godot editor metadata is never shipped.
    result = subprocess.run([str(engine), '--headless', '--path', str(target), '--import'],
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=420)
    if result.returncode or 'SCRIPT ERROR:' in result.stdout + result.stderr:
        raise RuntimeError('Godot project import failed:\n' + result.stdout + result.stderr)
    (target.parent / 'godot-import.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    cache = target / '.godot'
    if cache.is_dir():
        for child in cache.iterdir():
            if child.is_dir() and child.name != 'imported':
                shutil.rmtree(child)
    return result


def launch_cmd(bundled=False, compatibility=False):
    # Written as UTF-8 ASCII, no developer machine paths. All arguments are quoted.
    render = ' --rendering-method gl_compatibility' if compatibility else ''
    return ('@echo off\r\nsetlocal\r\ncd /d "%~dp0"\r\n'
            'set "CS2CAREER_BUNDLED_MOD=' + ('%~dp0mod' if bundled else '') + '"\r\n'
            'if not exist "%~dp0game\\runtime" mkdir "%~dp0game\\runtime"\r\n'
            'start "CS2 Career" /wait "%~dp0engine\\Godot.exe" --path "%~dp0game"'
            ' --log-file "%~dp0game\\runtime\\game.log"' + render + '\r\n'
            'if errorlevel 1 (echo Startup failed. See game\\runtime\\game.log & pause)\r\n')


def archive(folder, destination, prefix=None):
    """Exclude only regenerated user state; folder itself must be a clean stage."""
    folder, destination = Path(folder), Path(destination)
    def reject_link(path):
        if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
            raise ValueError('Symlink or reparse point in package')

    for path in (folder, *folder.parents):
        reject_link(path)
    if not folder.is_dir():
        raise ValueError('Package stage must be a directory')
    entries = []
    for directory, folders, names in os.walk(folder, topdown=True, followlinks=False):
        base = Path(directory)
        accepted = []
        for name in sorted(folders):
            path = base / name
            reject_link(path)
            relative = path.relative_to(folder)
            if relative.parts[:2] != ('game', 'runtime') and name != 'godot-import.log':
                accepted.append(name)
        folders[:] = accepted
        file_count = 0
        for name in sorted(names):
            path = base / name
            reject_link(path)
            relative = path.relative_to(folder)
            if relative.parts[:2] == ('game', 'runtime') or name == 'godot-import.log':
                continue
            if path.is_file():
                entries.append((path, relative.as_posix()))
                file_count += 1
        # Files imply their parents, but an empty directory needs its own ZIP
        # member or extraction drops required roots such as mod/overrides.
        if base != folder and not accepted and not file_count:
            entries.append((base, base.relative_to(folder).as_posix() + '/'))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for path, name in sorted(entries, key=lambda row: row[1]):
            output.write(path, (prefix + '/' if prefix else '') + name)


PREVIEW_README = '''CS2 Career 1.7.0-preview.1 · 本地 3D 测试版

解压整个文件夹，不要在压缩包里直接打开。双击“开始游戏.cmd”。
不需要安装 Python 或 Godot。显卡兼容问题可试“兼容显卡启动.cmd”。
这是首次 3D 测试版，不替换 1.6.0 正式版，也不包含开发者存档。

可以测试房间／俱乐部／场馆、手机和电脑、开局抽属性及外观、
生涯、快速模拟、天梯、自定义、战术设计、RTS、手动存档与读档。
界面和细节仍在迭代；RTS 多层地图不代表已完整支持所有楼层。

进入真实 CS2：仍需自己安装 Steam 和 CS2，并登录自己的账号。
整合包：在手机或电脑“设置”中核对游戏路径，关闭 CS2 后，点击
“安装随包人机增强”。它会备份受影响文件，再安装当前配套组件。
普通运行包：不含完整人机增强；使用你已有的兼容组件与来源路径。
不要把开发者配置／身份文件复制到其他玩家电脑。
游戏更新可能破坏底层插件兼容性，不能保证未来 CS2 更新后仍可用。
这些插件只用于程序启动的 -insecure 本地人机对局，不用于官方匹配。
恢复普通游戏前需退出程序和 CS2，按 MOD 说明停用／移除相关插件并
核对 Steam 启动项；仅删除 -insecure 不代表插件已完全移除。

存档：game/runtime/career/save；手动存档在其 manual 目录。
安装备份：game/runtime/career/install-backups。运行包不含任何历史存档。
请放在可写的普通目录。移动整个文件夹可以保留自己的测试进度。
出现错误请提供 game/runtime/game.log 和发生错误时的操作。

饰品 3D 检视／直接贴纸编辑：仅提供可选接口，默认关闭。
不内置或自动下载外部检视器，玩家自行安装工具及对应适配器。

来源与许可见 legal、licenses 和随包源码。Valve 游戏素材、队伍标志
与第三方组件仍归各自权利人；本项目许可不覆盖这些素材。
本包是未签名的测试构建。请核对 SHA256；遇到系统提示不要关闭安全防护。

English: Unzip the whole folder and run Launch-CS2Career.cmd. Python and Godot
are bundled. Steam and CS2 are not. Optional bot installation is explicit in
Settings, requires CS2 to be closed, and keeps backups. No private saves or
account IDs are included. This preview has not been verified on every PC.
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--engine-legal', type=Path, help='Reuse verified local Godot license files instead of downloading them')
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--fonts', type=Path, required=True)
    parser.add_argument('--media-config', type=Path, required=True)
    parser.add_argument('--version', default=VERSION)
    parser.add_argument('--ordinary-only', action='store_true', help='Build only fresh ordinary Windows and source archives; do not bundle a bot runtime')
    parser.add_argument('--bot-stage', type=Path, help='Audited staged capsule, required unless --ordinary-only is used')
    parser.add_argument('--resume-prepared', action='store_true', help='Reuse this build folder after offline backend preparation')
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9.-]+', args.version):
        parser.error('--version must contain only letters, digits, periods or hyphens')
    if args.ordinary_only and args.resume_prepared:
        parser.error('--ordinary-only requires a fresh backend build and forbids --resume-prepared')
    if not args.ordinary_only and args.bot_stage is None:
        parser.error('--bot-stage is required unless --ordinary-only is used')
    output = args.output.resolve()
    if args.resume_prepared:
        proof = json.loads((output / 'PREPARED_BUILD.json').read_text('utf-8'))
        if proof.get('version') != args.version or (output / 'packages').exists():
            raise ValueError('Not an unfinished prepared preview build')
    else:
        output.mkdir(parents=True, exist_ok=False)
    from tools.career3d_package_sources import stage_sources
    source = output / 'build/source'
    report = json.loads((source / 'SOURCE_STAGE_MANIFEST.json').read_text('utf-8')) if args.resume_prepared else \
        stage_sources(ROOT, source, args.assets, args.fonts, version=args.version)
    bots = None if args.ordinary_only else args.bot_stage.resolve()
    if bots is not None:
        for item in (bots / 'vendor').rglob('*'):
            if item.is_file():
                target = source / 'vendor' / item.relative_to(bots / 'vendor')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
        write_json(source / 'SOURCE_STAGE_MANIFEST.json', {**report, 'post_stage_overlay': {
            'vendor/InventorySimulator/gamedata/inventory-simulator.json': digest(
                source / 'vendor/InventorySimulator/gamedata/inventory-simulator.json')}})
    media, skin_count = relative_media(args.media_config, source / 'media')
    source_media = {**media, 'team_manifest': '../../../media/teams/team-media.json',
                    'skin_cache_roots': ['../../../media/skin_art'], 'map_backgrounds': {
                        name: {**row, 'path': row['path'].replace('../../media/', '../../../media/')}
                        for name, row in media['map_backgrounds'].items()}}
    write_json(source / 'work/career3d_redesign/data/media.json', source_media)
    if bots is not None:
        shutil.copytree(bots / 'legal', source / 'legal/bot-runtime')
        shutil.copytree(bots / 'third_party', source / 'third_party/bot-runtime')
        notice = source / 'THIRD_PARTY_NOTICES.md'
        notice.write_text(f'# {args.version} distribution note\n\n'
            'This preview all-in-one distribution includes the audited Bot Improver runtime and '
            'its accompanying source archives and licenses in legal/bot-runtime and '
            'third_party/bot-runtime. Statements below about an unbundled full runtime refer '
            'to the earlier 1.6.0 release, not this explicitly labeled preview. The third-party '
            'management panel and external 3D sticker editor are not bundled.\n\n' +
            notice.read_text('utf-8'), encoding='utf-8')
    preview_readme = (source / 'docs/3d-preview-readme.txt').read_text('utf-8') if args.ordinary_only else \
        PREVIEW_README.replace(VERSION, args.version)
    (source / '3D测试版说明.txt').write_text(preview_readme, encoding='utf-8', newline='\n')
    report = seal_source_manifest(source, report, ordinary_only=args.ordinary_only)
    backend = output / 'build/backend/dist/CareerBackend' if args.resume_prepared else \
        freeze_backend(source, output / 'build/backend')
    if not (backend / 'CareerBackend.exe').is_file():
        raise ValueError('Prepared frozen backend is missing')
    package = output / 'release' / ('CS2Career-' + args.version)
    package.mkdir(parents=True)
    shutil.copytree(backend, package / 'backend')
    package.joinpath('engine').mkdir()
    shutil.copy2(args.engine, package / 'engine/Godot.exe')
    if args.engine_legal:
        copy_engine_legal(args.engine, package / 'legal/Godot', args.engine_legal)
    else:
        download_legal(args.engine, package / 'legal/Godot')
    shutil.copytree(source / 'licenses', package / 'licenses')
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.is_file():
        raise FileNotFoundError('The distributed Python license is missing')
    package.joinpath('legal/Python').mkdir(parents=True)
    shutil.copy2(python_license, package / 'legal/Python/LICENSE.txt')
    shutil.copy2(source / 'THIRD_PARTY_NOTICES.md', package / 'THIRD_PARTY_NOTICES.md')
    soundfont_license = source / 'work/career3d_redesign/assets/audio/GeneralUser-GS-LICENSE.txt'
    if soundfont_license.is_file():
        shutil.copy2(soundfont_license, package / 'licenses/GeneralUser-GS-LICENSE.txt')
    shutil.copytree(source / 'media', package / 'media')
    stage_game(source, package / 'game', args.engine, media, version=args.version)
    shutil.copy2(source / 'LICENSE', package / 'LICENSE')
    shutil.copy2(source / 'docs/skin-tools-interface.zh-CN.txt', package / '饰品工具接口说明.txt')
    (package / '测试版说明.txt').write_text(preview_readme, encoding='utf-8', newline='\n')
    for name in ('开始游戏.cmd', 'Launch-CS2Career.cmd'):
        (package / name).write_bytes(launch_cmd().encode('ascii'))
    (package / '兼容显卡启动.cmd').write_bytes(launch_cmd(compatibility=True).encode('ascii'))
    public = output / 'packages'
    source_zip = public / ('CS2Career-' + args.version + '-source.zip')
    archive(source, source_zip, 'CS2Career-source')
    package.joinpath('source').mkdir()
    shutil.copy2(source_zip, package / 'source' / source_zip.name)
    runtime_zip = public / ('CS2Career-' + args.version + '-windows.zip')
    archive(package, runtime_zip, package.name)
    built_archives = [source_zip, runtime_zip]
    if bots is not None:
        # Mutate only this clean staging folder after the ordinary archive is sealed.
        shutil.copytree(bots / 'CS2BotImprover', package / 'mod')
        shutil.copytree(bots / 'legal', package / 'legal/bot-runtime')
        shutil.copytree(bots / 'third_party', package / 'third_party/bot-runtime')
        for name in ('开始游戏.cmd', 'Launch-CS2Career.cmd'):
            (package / name).write_bytes(launch_cmd(bundled=True).encode('ascii'))
        (package / '兼容显卡启动.cmd').write_bytes(launch_cmd(bundled=True, compatibility=True).encode('ascii'))
        full_zip = public / ('CS2Career-' + args.version + '-all-in-one.zip')
        archive(package, full_zip, package.name + '-all-in-one')
        built_archives.append(full_zip)
    archives = {p.name: {'sha256': digest(p), 'bytes': p.stat().st_size}
                for p in built_archives}
    write_json(public / 'BUILD_MANIFEST.json', {
        'schema_version': 1, 'version': args.version, 'base_core_version': '1.6.0',
        'built_utc': datetime.now(timezone.utc).isoformat(), 'archives': archives,
        'distribution': 'ordinary-unbundled' if args.ordinary_only else 'preview-with-all-in-one',
        'bundled_bot_runtime': not args.ordinary_only,
        'godot_version': ENGINE_VERSION, 'skin_images': skin_count,
        'included_private_saves': False, 'published_to_github': False,
        'live_cs2_test': False, 'install_requires_steam_and_cs2': True})
    (public / 'SHA256SUMS.txt').write_text(''.join(
        row['sha256'] + '  ' + name + '\n' for name, row in archives.items()), encoding='ascii')
    print(json.dumps({'packages': str(public), 'archives': archives}, indent=2))


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    main()
