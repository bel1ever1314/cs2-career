"""Create allowlisted public artifacts; never archive a player's release folder."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.5.0-rc.20260910.4'
DOCS = ('README.md','LICENSE','THIRD_PARTY_NOTICES.md','RECOVERED_SOURCE.md',
        'RELEASE_NOTES.md','PUBLISHING.md','DEVELOPER_GUIDE.zh-CN.md',
        'EXTENSION_ARCHITECTURE.zh-CN.md','CS2_INTEGRATION.zh-CN.md',
        'DESKTOP_REBUILD_STATUS.zh-CN.md','开始游玩-FAQ.txt')
RUNTIME_DOCS = ('开始游玩-FAQ.txt','LICENSE','THIRD_PARTY_NOTICES.md','RECOVERED_SOURCE.md')
ROOT_FILES = DOCS + ('requirements-desktop.txt','main.py','preview_main.py','playtest_main.py',
                     'build_desktop_preview.py','build_exe.py','.gitignore')
SKIP = {'bin','obj','__pycache__','.git','.agents','.codex','save','.qa','.desktop-deps'}
SUFFIXES = {'.py','.cs','.csproj','.js','.cjs','.css','.html','.json','.db','.md','.txt','.svg','.png','.ps1'}
DLLS = {'vendor/CareerMatch/CareerMatch.dll','vendor/BotBuy/BotBuy.dll',
        'vendor/InvsimCareer/InvsimCareer.dll',
        'vendor/InventorySimulator/plugins/InventorySimulator/InventorySimulator.dll'}


def source_files(root: Path) -> list[Path]:
    files = [root/name for name in ROOT_FILES if (root/name).is_file()]
    for dirname in ('cs2career','vendor','tests','tools','licenses','extensions/_templates'):
        for path in (root/dirname).rglob('*'):
            rel = path.relative_to(root)
            if not path.is_file() or set(rel.parts) & SKIP:
                continue
            if path.suffix in SUFFIXES or rel.as_posix() in DLLS:
                files.append(path)
    if (root/'extensions/README.md').is_file():
        files.append(root/'extensions/README.md')
    for path in files:
        if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
            raise ValueError(f'Outside source root or symlink: {path}')
    return sorted(set(files), key=lambda p:p.relative_to(root).as_posix())


def verify_public_text(path: Path) -> None:
    if path.suffix == '.png':
        return
    text = (path.read_bytes().decode('utf-8',errors='replace') if path.suffix in ('.dll','.exe')
            else path.read_text(encoding='utf-8-sig'))
    # Reject private Windows home paths, not public source attribution or the
    # documented SteamID64 base constant used to create synthetic bot IDs.
    if re.search(r'[A-Z]:[/\\]Users[/\\](?!Public\b|Default\b)[^/\\\s]+', text, re.I):
        raise ValueError(f'Private user path in public source: {path.name}')
    if re.search(r'(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}', text):
        raise ValueError(f'Possible credential in public source: {path.name}')


def build(root: Path, exe: Path, output: Path, version: str = VERSION) -> dict:
    if not re.fullmatch(r'[a-zA-Z0-9.-]+',version):
        raise ValueError('Invalid release version')
    if not exe.is_file() or exe.read_bytes()[:2] != b'MZ':
        raise ValueError('Expected a built Windows executable')
    verify_public_text(exe)
    for name in DOCS:
        if not (root/name).is_file():
            raise ValueError(f'Missing release document: {name}')
    if output.exists():
        raise FileExistsError('Output exists; choose a fresh --output directory')
    selected = source_files(root)
    for path in selected:
        verify_public_text(path)
    inventory = {path.relative_to(root).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in selected}
    output.mkdir(parents=True)
    prefix = f'CS2Career-{version}'
    source_zip = output/f'{prefix}-source.zip'
    runtime_zip = output/f'{prefix}-windows-x64.zip'
    with zipfile.ZipFile(source_zip,'x',zipfile.ZIP_DEFLATED) as archive:
        for path in selected:
            archive.write(path, prefix+'-source/'+path.relative_to(root).as_posix())
        archive.writestr(prefix+'-source/SOURCE_MANIFEST.json',json.dumps(inventory,indent=2,ensure_ascii=False))
    runtime = [p for p in selected if p.relative_to(root).parts[0] == 'licenses'
               or p.relative_to(root).as_posix().startswith('extensions/')
               or p.relative_to(root).as_posix() in RUNTIME_DOCS]
    with zipfile.ZipFile(runtime_zip,'x',zipfile.ZIP_DEFLATED) as archive:
        archive.write(exe,prefix+'/CS2Career.exe')
        for path in runtime:
            relative = path.relative_to(root).as_posix()
            # Ordinary players see one FAQ; legal/source provenance is retained
            # under licenses. Developer guides remain in the source archive.
            if relative in ('THIRD_PARTY_NOTICES.md','RECOVERED_SOURCE.md'):
                relative = 'licenses/'+relative
            archive.write(path,prefix+'/'+relative)
    # Audit the actual ZIP entries, not just the planned input list.
    for name in (source_zip,runtime_zip):
        with zipfile.ZipFile(name) as archive:
            if archive.testzip() is not None:
                raise ValueError(f'Archive corruption: {name.name}')
            for entry in archive.namelist():
                parts = set(Path(entry).parts)
                if parts & SKIP or entry.endswith(('.pdb','.pyc','.log')):
                    raise ValueError(f'Private/generated path leaked: {entry}')
    hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (source_zip,runtime_zip)}
    (output/'SHA256SUMS.txt').write_text(''.join(f'{sha}  {name}\n' for name,sha in hashes.items()),encoding='ascii')
    report = dict(version=version,source_files=len(selected),runtime_files=len(runtime)+1,
                  exe_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),archives=hashes,
                  cs2_live_test='pending',recovered_skin_sources='compile_checked_only')
    (output/'BUILD_MANIFEST.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'publish'/VERSION)
    args = parser.parse_args()
    print(json.dumps(build(ROOT,args.exe.resolve(),args.output.resolve()),indent=2))
