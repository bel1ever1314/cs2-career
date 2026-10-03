"""Reviewed local deployment of chat tactics; never writes saves or extensions."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess

if __package__:
    from .repair_cs2_runtime import atomic_copy, digest, GAME, STAGE
else:
    from repair_cs2_runtime import atomic_copy, digest, GAME, STAGE

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUILD = Path('D:/CS2CareerBuilds/v1.6.0/tactical-commands-20260930')
RELEASE = Path('D:/CS2CareerBuilds/v1.6.0/release/CS2Career-160-Matchmaking')
NAME = 'CS2Career-160-Matchmaking'
COMPONENT = Path('addons/counterstrikesharp/plugins/CareerMatch')


def protected_snapshot() -> dict[str, str | None]:
    """Verify player data and native plugins without changing or opening them in-app."""
    roots = [RELEASE/'save', RELEASE/'extensions', GAME/'addons/counterstrikesharp/configs']
    paths = {file for root in roots if root.is_dir() for file in root.rglob('*') if file.is_file()}
    paths.update(GAME/relative for relative in (
        'addons/BotController/bin/win64/BotController.dll',
        'addons/BotVision/bin/win64/BotVision.dll',
        'addons/BotHider/bin/win64/BotHider.dll',
        'addons/metamod/metaplugins.ini', 'overrides/botprofile.vpk',
        'addons/counterstrikesharp/plugins/CareerMatch/match_request.json',
        'addons/counterstrikesharp/plugins/CareerMatch/match_result.json',
        'addons/counterstrikesharp/plugins/CareerMatch/tactical_playbook.json',
        'addons/counterstrikesharp/plugins/CareerMatch/tactical_routes.json',
    ))
    return {str(path): digest(path) if path.is_file() else None for path in sorted(paths)}


def require_closed() -> None:
    command = "@(Get-Process cs2,CS2Career* -ErrorAction SilentlyContinue | Where-Object {$_.HandleCount -ne 0} | ForEach-Object {$_.Name}) -join ','"
    running = subprocess.run(['powershell', '-NoProfile', '-Command', command],
                             check=True, capture_output=True, text=True).stdout.strip()
    if running:
        raise RuntimeError('Close CS2 and Career before updating: ' + running)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=DEFAULT_BUILD)
    parser.add_argument('--bundle-only', action='store_true', help='Prepare bundled source plugin for the desktop build, do not install game/EXE.')
    parser.add_argument('--plugins-only', action='store_true', help='Update the source-driven 3D application plugin and recovery capsule, without replacing the packaged desktop EXE.')
    parser.add_argument('--with-botbuy', action='store_true', help='Also deploy the reviewed BotBuy build with the same backup/rollback checks.')
    args = parser.parse_args()
    if args.bundle_only and args.plugins_only:
        parser.error('Choose either --bundle-only or --plugins-only.')
    build = args.build.resolve()
    if not build.is_relative_to(Path('D:/CS2CareerBuilds').resolve()):
        raise ValueError('Keep build and backups in D:/CS2CareerBuilds')
    for name in ('CareerMatch.dll', 'CareerMatch.deps.json'):
        if not (build/'plugin'/name).is_file(): raise FileNotFoundError(name)
    json.loads((build/'plugin/CareerMatch.deps.json').read_text('utf-8-sig'))
    targets = []
    for name in ('CareerMatch.dll', 'CareerMatch.deps.json'):
        areas = [('vendor', ROOT/'vendor/CareerMatch')]
        if not args.bundle_only:
            areas += [('game', GAME/COMPONENT), ('compatible-mod', STAGE/'compatible-mod'/COMPONENT)]
        for area, destination in areas:
            targets.append((build/'plugin'/name, destination/name, Path(area)/name))
    if args.with_botbuy:
        json.loads((build/'botbuy/BotBuy.deps.json').read_text('utf-8-sig'))
        component = Path('addons/counterstrikesharp/plugins/BotBuy')
        for name in ('BotBuy.dll', 'BotBuy.deps.json'):
            areas = [('vendor/BotBuy', ROOT/'vendor/BotBuy')]
            if not args.bundle_only:
                areas += [('game/BotBuy', GAME/component), ('compatible-mod/BotBuy', STAGE/'compatible-mod'/component)]
            for area, destination in areas:
                targets.append((build/'botbuy'/name, destination/name, Path(area)/name))
    if not args.bundle_only:
        if not args.plugins_only:
            smoke = json.loads((build/'exe-smoke.json').read_text('utf-8'))
            if not smoke.get('ok'): raise RuntimeError('Updated desktop self-test has not passed')
            if smoke.get('career_plugin_sha256') != digest(build/'plugin/CareerMatch.dll').lower():
                raise RuntimeError('Desktop contains a different CareerMatch than the reviewed plugin')
            if args.with_botbuy and smoke.get('botbuy_plugin_sha256') != digest(build/'botbuy/BotBuy.dll').lower():
                raise RuntimeError('Desktop contains a different BotBuy than the reviewed plugin')
            targets.append((build/'release'/NAME/(NAME+'.exe'), RELEASE/(NAME+'.exe'), Path('desktop')/(NAME+'.exe')))
            targets.append((ROOT/'开始游玩-FAQ.txt', RELEASE/'开始游玩-FAQ.txt', Path('desktop')/'开始游玩-FAQ.txt'))
        note_targets = [('game', GAME/COMPONENT)] if args.plugins_only else [('desktop', RELEASE), ('game', GAME/COMPONENT)]
        for area, dest in note_targets:
            targets.append((ROOT/'游戏内指挥说明.txt', dest/'游戏内指挥说明.txt', Path(area)/'游戏内指挥说明.txt'))
        require_closed()
        # The recovery capsule is hash-verified on the next repair. Updating a
        # plugin without its manifest would make that verified recovery fail.
        manifest_path = STAGE/'capsule-files.json'
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text('utf-8'))
            capsule = STAGE/'compatible-mod'
            for source, destination, _ in targets:
                if destination.is_relative_to(capsule):
                    manifest[destination.relative_to(capsule).as_posix()] = digest(source)
            updated_manifest = build/'capsule-files.updated.json'
            updated_manifest.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
            targets.append((updated_manifest, manifest_path, Path('compatible-mod')/'capsule-files.json'))
    for source, destination, _ in targets:
        if not source.is_file(): raise FileNotFoundError(source)
        if destination.suffix in ('.dll', '.exe') and not destination.is_file(): raise FileNotFoundError(destination)
    protected = protected_snapshot() if not args.bundle_only else {}
    backup = build/'backup'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True, exist_ok=False)
    receipt = []
    for source, destination, relative in targets:
        old = backup/relative
        before = digest(destination) if destination.is_file() else None
        if before is not None:
            old.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, old)
            if digest(old) != before: raise OSError('Backup verification failed')
        receipt.append(dict(source=str(source), target=str(destination), backup=str(old), before=before, after=digest(source)))
    (backup/'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), 'utf-8')
    changed = []
    try:
        if not args.bundle_only: require_closed()
        for item in receipt:
            target = Path(item['target'])
            current = digest(target) if target.is_file() else None
            if current != item['before']: raise RuntimeError('Target changed during preparation: ' + str(target))
            changed.append(item)
            atomic_copy(Path(item['source']), target)
        if not args.bundle_only and protected_snapshot() != protected:
            raise RuntimeError('Protected player data or native plugins changed during deployment; updated binaries rolled back.')
    except BaseException:
        for item in reversed(changed):
            target = Path(item['target'])
            if item['before'] is not None: atomic_copy(Path(item['backup']), target)
            elif target.exists():
                # Recover a newly installed note rather than delete it.
                recover = backup/'recovered-new'/Path(item['target']).name
                recover.parent.mkdir(parents=True, exist_ok=True)
                target.replace(recover)
        raise
    report = dict(installed=len(changed), backup=str(backup), verified=all(digest(Path(i['target'])) == i['after'] for i in receipt),
                  live_navigation_tested=False, saves_and_extensions='unchanged', native_dlls='unchanged',
                  packaged_desktop_replaced=not args.bundle_only and not args.plugins_only)
    if not args.bundle_only:
        (backup/'protected-files.json').write_text(json.dumps(protected, ensure_ascii=False, indent=2), 'utf-8')
        report['protected_files_verified'] = len(protected)
    (backup/'installed.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__': main()
