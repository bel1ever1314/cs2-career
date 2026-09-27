"""Build v1.6.0 on D: and prepare privacy-audited, unpublished archives.

Normal builds reuse the bundled game plugins; rebuilding game plugins is a
separate opt-in action, not a side effect of rebuilding the desktop UI.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
VERSION = '1.6.0'
DEFAULT_OUTPUT = Path('D:/CS2CareerBuilds') / ('v' + VERSION)


def build_plan(output: Path, name: str, public_output: Path, build_plugins: bool = False) -> list[list[str]]:
    commands = []
    if build_plugins:
        commands.append(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                         '-File', str(ROOT / 'tools/build_plugins.ps1'),
                         '-OutputRoot', str(output / 'plugins')])
    commands.append([sys.executable, '-B', str(ROOT / 'build_desktop_preview.py'),
                     '--integration', '--name', name, '--output-root', str(output)])
    commands.append([sys.executable, '-B', str(ROOT / 'tools/package_public.py'),
                     '--exe', str(output / 'release' / name / (name + '.exe')),
                     '--output', str(public_output), '--version', VERSION])
    return commands


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--name', default='CS2Career-160')
    parser.add_argument('--public-output', type=Path)
    parser.add_argument('--build-plugins', action='store_true', help='Explicitly rebuild CareerMatch/BotBuy; requires .NET SDK.')
    parser.add_argument('--dry-run', action='store_true', help='Show paths/commands without building or writing anything.')
    args = parser.parse_args()
    if not args.name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in args.name):
        parser.error('name must contain only ASCII letters, digits, - or _')
    output = args.output_root.resolve()
    public_output = (args.public_output or output / 'public' / datetime.now().strftime('%Y%m%d-%H%M%S')).resolve()
    commands = build_plan(output, args.name, public_output, args.build_plugins)
    if args.dry_run:
        print(json.dumps({'version': VERSION, 'output_root': str(output), 'commands': commands}, indent=2))
        return
    env = dict(os.environ)
    for key, subdir in (('TEMP', 'temp'), ('TMP', 'temp'), ('PYINSTALLER_CONFIG_DIR', 'cache/pyinstaller'),
                        ('DOTNET_CLI_HOME', 'cache/dotnet'), ('NUGET_PACKAGES', 'cache/nuget')):
        location = output / subdir
        location.mkdir(parents=True, exist_ok=True)
        env[key] = str(location)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    if public_output.exists():
        raise FileExistsError('Public output exists; choose a fresh --public-output directory.')
    for command in commands:
        subprocess.run(command, check=True, cwd=ROOT, env=env)
    print(f'Built locally, not uploaded: {public_output}')


if __name__ == '__main__':
    main()
