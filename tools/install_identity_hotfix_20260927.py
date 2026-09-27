"""Install only the reviewed CareerMatch identity repair and its packaged EXE.

Leaves saves, requests, results and every other plugin untouched. Copies the
failed match into a separate backup before a future match can replace it.
Run after building/testing the D: identity-repair-20260927 checkpoint.
"""
from __future__ import annotations

import json
import argparse
from pathlib import Path
import shutil
import subprocess

from repair_cs2_runtime import atomic_copy, digest, GAME, STAGE

BUILD = Path('D:/CS2CareerBuilds/v1.6.0/identity-repair-20260927')
RELEASE = Path('D:/CS2CareerBuilds/v1.6.0/release/CS2Career-160-Matchmaking')
COMPONENT = Path('addons/counterstrikesharp/plugins/CareerMatch')


def require_closed() -> None:
    command = "@(Get-Process cs2,CS2Career*,CS2BotLab* -ErrorAction SilentlyContinue | Where-Object {$_.HandleCount -ne 0} | ForEach-Object {$_.Name}) -join ','"
    running = subprocess.run(['powershell', '-NoProfile', '-Command', command],
                             check=True, capture_output=True, text=True).stdout.strip()
    if running:
        raise RuntimeError('Close programs before installation: ' + running)


def main() -> None:
    global BUILD
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=BUILD)
    BUILD = parser.parse_args().build.resolve()
    require_closed()
    targets = []
    for name in ('CareerMatch.dll', 'CareerMatch.deps.json'):
        for area, root in (('game', GAME), ('mod-source', STAGE / 'compatible-mod')):
            targets.append((BUILD / 'plugin' / name, root / COMPONENT / name, Path(area) / name))
    name = 'CS2Career-160-Matchmaking.exe'
    targets.append((BUILD / 'release' / 'CS2Career-160-Matchmaking' / name,
                    RELEASE / name, Path('desktop') / name))
    for src, dst, _ in targets:
        if not src.is_file() or not dst.is_file():
            raise FileNotFoundError(f'Expected existing source and target: {src} -> {dst}')
    backup = BUILD / 'backup' / 'deployed'
    backup.mkdir(exist_ok=False)
    evidence = backup / 'failed-match'
    evidence.mkdir()
    for name in ('match_request.json', 'match_result.json', 'match_result.best.json'):
        src = GAME / COMPONENT / name
        if src.is_file():
            shutil.copy2(src, evidence / name)
    if (GAME / COMPONENT / 'identity_traces').is_dir():
        shutil.copytree(GAME / COMPONENT / 'identity_traces', evidence / 'identity_traces')
    receipt = []
    for src, dst, rel in targets:
        old = backup / rel
        old.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, old)
        if digest(old) != digest(dst):
            raise OSError('Backup verification failed: ' + str(dst))
        receipt.append(dict(source=str(src), target=str(dst), backup=str(old),
                            before=digest(old), after=digest(src)))
    (backup / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    require_closed()
    changed = []
    try:
        for item in receipt:
            if digest(Path(item['target'])) != item['before']:
                raise RuntimeError('Target changed since backup: ' + item['target'])
            changed.append(item)
            atomic_copy(Path(item['source']), Path(item['target']))
    except BaseException:
        for item in reversed(changed):
            atomic_copy(Path(item['backup']), Path(item['target']))
        raise
    print(json.dumps(dict(installed=len(changed), backup=str(backup),
                          hashes_verified=all(digest(Path(r['target'])) == r['after'] for r in receipt))))


if __name__ == '__main__':
    main()
