"""Prepare an isolated local recovery build using existing art and engine files.

Only an explicit empty output directory is written. Never reads saves, installs
into CS2 or uploads a release. Live native verification remains a separate step.
"""
from pathlib import Path, PurePosixPath
import argparse
import json
import shutil
import sys
import zipfile

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cs2career.cs2 import runtime_compat as compat
from tools.career3d_package_sources import stage_sources
from tools.package_career3d import freeze_backend, stage_game, archive, launch_cmd, digest, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--assets-package', required=True, type=Path)
    parser.add_argument('--official-runtime', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--resume-build', action='store_true', help='Resume this isolated, unlaunched build after staging')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    base, upstream, output = (p.resolve() for p in (args.assets_package, args.official_runtime, args.output))
    for required in ('engine/Godot.exe', 'game/fonts/ChillRoundF.ttf', 'game/data/media.json'):
        if not (base / required).is_file():
            raise FileNotFoundError(base / required)
    output.mkdir(parents=True, exist_ok=args.resume_build)
    version = 'recovered-147-20261025'
    build = output / 'build'
    source = build / 'source'
    print('Stage recovered source and existing art', flush=True)
    if not args.resume_build:
        stage_sources(root, source, root / 'work/career3d_redesign/assets', base / 'game/fonts', version=version)
    print('Freeze updated backend', flush=True)
    backend = build / 'backend/dist/CareerBackend' if args.resume_build else freeze_backend(source, build / 'backend')
    package = output / 'CS2Career-Recovered-1.4.7'
    package.mkdir(exist_ok=args.resume_build)
    if (package / 'game/runtime').exists():
        raise ValueError('Cannot resume a package that already contains player runtime data')
    shutil.copytree(backend, package / 'backend', dirs_exist_ok=args.resume_build)
    for area in ('engine', 'media', 'licenses'):
        shutil.copytree(base / area, package / area, dirs_exist_ok=args.resume_build)
    for area in ('Godot', 'Python'):
        if (base / 'legal' / area).is_dir():
            shutil.copytree(base / 'legal' / area, package / 'legal' / area, dirs_exist_ok=args.resume_build)
    shutil.copy2(root / 'LICENSE', package / 'LICENSE')
    shutil.copy2(root / 'docs/improver147-recovery.txt', package / '恢复与适配说明.txt')
    for name in ('BotAimImprover', 'BotState', 'NadeSystem'):
        (package / 'legal' / name).mkdir(parents=True, exist_ok=args.resume_build)
        shutil.copy2(root / 'vendor' / name / 'LICENSE', package / 'legal' / name / 'LICENSE')
    print('Import recovered Godot project', flush=True)
    media = json.loads((base / 'game/data/media.json').read_text('utf-8-sig'))
    if not args.resume_build:
        stage_game(source, package / 'game', package / 'engine/Godot.exe', media, version=version)
    elif not (package / 'godot-import.log').is_file():
        raise ValueError('Godot import must complete before resuming')
    print('Prepare verified offline runtime', flush=True)
    isolated = build / 'compat'
    isolated.mkdir(exist_ok=args.resume_build)
    result = compat.prepare_runtime(isolated, upstream, build / 'not-an-installed-game', allow_download=False)
    prepared = Path(result['mod_dir'])
    mod = package / 'mod'
    mod.mkdir(exist_ok=args.resume_build)
    for path, relative in compat._source_plan(prepared):
        if not compat.bundled_payload_allowed(relative):
            continue
        target = mod.joinpath(*relative.parts)
        compat.io_path(target.parent).mkdir(parents=True, exist_ok=True)
        shutil.copy2(compat.io_path(path), compat.io_path(target))
    (mod / 'overrides').mkdir(exist_ok=True)
    manifest = compat.load_runtime_manifest()
    receipt = {'schema_version': 1, 'revision': manifest['revision'],
               'manifest_sha256': compat._manifest_hash(manifest),
               'components': [{key: row[key] for key in ('name', 'version')} for row in manifest['components']],
               'files': {rel.as_posix(): digest(path) for path, rel in compat._source_plan(mod)}}
    write_json(package / compat.RECEIPT, receipt)
    compat.validate_bundled_runtime(mod)
    for name in ('开始游戏.cmd', 'Launch-CS2Career.cmd'):
        (package / name).write_bytes(launch_cmd(bundled=True).encode('ascii'))
    (package / '兼容显卡启动.cmd').write_bytes(launch_cmd(bundled=True, compatibility=True).encode('ascii'))
    print('Archive corresponding recovery source and test package', flush=True)
    (package / 'source').mkdir(exist_ok=args.resume_build)
    archive(source, package / 'source/CS2Career-recovered-source.zip', 'CS2Career-source')
    report = {'version': version, 'source_baseline': 'e04ad9763074249db20d15a5a323a7e4c9a6b304',
              'bot_improver': '1.4.7', 'cs2_news_date': '2026-10-22',
              'compiled_plugins': ['CareerMatch', 'BotBuy', 'BotAimImprover', 'BotState', 'NadeSystem'],
              'live_cs2_test': False, 'pixel_source_recovered': False,
              'save_imported': False, 'remote_server_mode': False, 'github_published': False,
              'runtime_files': len(receipt['files'])}
    write_json(package / 'BUILD_STATUS.json', report)
    zip_path = output / 'CS2Career-Recovered-1.4.7-local.zip'
    archive(package, zip_path, package.name)
    write_json(output / 'PACKAGE.json', {**report, 'zip': zip_path.name,
                                      'bytes': zip_path.stat().st_size, 'sha256': digest(zip_path)})
    print(json.dumps({'directory': str(package), 'zip': str(zip_path), 'bytes': zip_path.stat().st_size}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
