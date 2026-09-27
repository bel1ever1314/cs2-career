"""Build the isolated design checkpoint without replacing the player's EXE."""
import os
import sys
import argparse
import shutil
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'.desktop-deps'))


def main():
    import PyInstaller.__main__ as pyi
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--playtest', action='store_true')
    mode.add_argument('--integration', action='store_true', help='Real CS2 entry; bundle plugins, keep saves beside this separate EXE.')
    parser.add_argument('--name', help='Optional separate checkpoint name; never replaces an open EXE.')
    parser.add_argument('--output-root', help='Put PyInstaller build and release output here (for example D:\\CS2CareerBuilds).')
    parser.add_argument('--natural-routes', type=Path, help='Optional private Dust2 motion pack, copied beside the test EXE, never embedded.')
    args = parser.parse_args()
    playtest = args.playtest
    name = args.name or ('CS2Career-CS2Test' if args.integration else 'CS2Career-Playtest' if playtest else 'CS2Career-Preview')
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in name):
        parser.error('name must contain only ASCII letters, digits, - or _')
    build = name.lower() if args.name else ('desktop-playtest' if playtest else 'desktop-preview')
    output_root = Path(args.output_root).resolve() if args.output_root else ROOT
    release_root = output_root / 'release' / name
    build_root = output_root / 'build' / build
    if args.natural_routes:
        route_pack = json.loads(args.natural_routes.read_text(encoding='utf-8'))
        if route_pack.get('schema_version') != 3 or route_pack.get('map') != 'de_dust2' or not route_pack.get('nodes'):
            parser.error('invalid Dust2 motion pack')
    # A public EXE must not embed this developer's absolute D: path. With the
    # launcher's working directory set beside the EXE, extraction stays local.
    runtime_args = ['--runtime-tmpdir', 'runtime-temp'] if args.output_root else []
    if runtime_args:
        (output_root / 'runtime-temp').mkdir(parents=True, exist_ok=True)
    sep = ';' if os.name == 'nt' else ':'
    plugin_args = []
    data_args=[]
    for item in (ROOT/'cs2career/data').iterdir():
        if item.name=='natural_behavior' and not args.natural_routes:continue
        destination='data/'+item.name if item.is_dir() else 'data'
        data_args += ['--add-data',f'{item}{sep}{destination}']
    if args.integration:
        required = ['CareerMatch/CareerMatch.dll','CareerMatch/CareerMatch.deps.json',
                    'BotBuy/BotBuy.dll','BotBuy/BotBuy.deps.json',
                    'InvsimCareer/InvsimCareer.dll','InvsimCareer/InvsimCareer.deps.json',
                    'InventorySimulator/plugins/InventorySimulator/InventorySimulator.dll',
                    'InventorySimulator/plugins/InventorySimulator/InventorySimulator.deps.json',
                    'InventorySimulator/gamedata/inventory-simulator.json']
        for rel in required:
            src = ROOT/'vendor'/rel
            if not src.is_file():
                raise FileNotFoundError(f'Missing bundled plugin: {src}')
            plugin_args += ['--add-data',f'{src}{sep}vendor/{Path(rel).parent.as_posix()}']
        plugin_args += ['--add-data',f'{ROOT/"vendor/InventorySimulator/plugins/InventorySimulator/lang"}{sep}vendor/InventorySimulator/plugins/InventorySimulator/lang']
    pyi.run([
        str(ROOT/('main.py' if args.integration else 'playtest_main.py' if playtest else 'preview_main.py')), '--name', name, '--onefile', '--windowed', '--noconfirm',
        '--distpath', str(release_root), '--workpath', str(build_root),
        '--specpath', str(build_root), '--paths', str(ROOT/'.desktop-deps'),
        '--collect-all', 'webview', '--collect-all', 'clr_loader', '--collect-all', 'pythonnet',
        '--collect-all', 'orjson',
        '--add-data', f'{ROOT / "cs2career/web/static"}{sep}web/static',
        '--add-data', f'{ROOT / "licenses"}{sep}licenses',
        '--add-data', f'{ROOT / "LICENSE"}{sep}.',
        '--exclude-module', 'PyQt5', '--exclude-module', 'PyQt6', '--exclude-module', 'PySide2', '--exclude-module', 'PySide6',
        '--exclude-module', 'pytest',
    ] + data_args + plugin_args + runtime_args)
    if args.integration:
        shutil.copy2(ROOT / '开始游玩-FAQ.txt', release_root / '开始游玩-FAQ.txt')
    if args.natural_routes:
        destination = release_root / 'natural_routes'
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.natural_routes, destination / 'de_dust2.json')
        shutil.copy2(ROOT / '自然中门试验说明.txt', release_root / '自然中门试验说明.txt')


if __name__ == '__main__':
    main()
