"""Build the isolated design checkpoint without replacing the player's EXE."""
import os
import sys
import argparse
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
    args = parser.parse_args()
    playtest = args.playtest
    name = args.name or ('CS2Career-CS2Test' if args.integration else 'CS2Career-Playtest' if playtest else 'CS2Career-Preview')
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in name):
        parser.error('name must contain only ASCII letters, digits, - or _')
    build = name.lower() if args.name else ('desktop-playtest' if playtest else 'desktop-preview')
    sep = ';' if os.name == 'nt' else ':'
    plugin_args = []
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
        '--distpath', str(ROOT/'release'/name), '--workpath', str(ROOT/'build'/build),
        '--specpath', str(ROOT/'build'/build), '--paths', str(ROOT/'.desktop-deps'),
        '--collect-all', 'webview', '--collect-all', 'clr_loader', '--collect-all', 'pythonnet',
        '--collect-all', 'orjson',
        '--add-data', f'{ROOT / "cs2career/data"}{sep}data',
        '--add-data', f'{ROOT / "cs2career/web/static"}{sep}web/static',
        '--add-data', f'{ROOT / "licenses"}{sep}licenses',
        '--add-data', f'{ROOT / "LICENSE"}{sep}.',
        '--exclude-module', 'PyQt5', '--exclude-module', 'PyQt6', '--exclude-module', 'PySide2', '--exclude-module', 'PySide6',
        '--exclude-module', 'pytest',
    ] + plugin_args)


if __name__ == '__main__':
    main()
