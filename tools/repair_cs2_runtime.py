"""Local, reversible deployment of the reviewed 2026-09-27 CS2 runtime.

No plugins are disabled, no saves are advanced, and nothing is uploaded.
The old mod source remains read-only. A new D: capsule prevents the launcher
from reinstalling the old BotRandomizer on the next match.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from datetime import datetime

STAGE = Path('D:/CS2CareerBuilds/v1.6.0/runtime-repair-20260927')
GAME = Path('D:/steam/steamapps/common/Counter-Strike Global Offensive/game/csgo')
SOURCE = Path('E:/1.4.1/CS2BotImprover')
SAVE = Path('D:/CS2CareerBuilds/v1.6.0/release/CS2Career-160-Matchmaking/save/cs2.json')


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inside(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    if target == root.resolve() or not target.is_relative_to(root.resolve()):
        raise ValueError(f'Path outside exact target: {relative}')
    return target


def atomic_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    handle, pending = tempfile.mkstemp(prefix='.runtime-', dir=dst.parent)
    os.close(handle)
    try:
        shutil.copy2(src, pending)
        if digest(Path(pending)) != digest(src):
            raise OSError(f'Copy checksum mismatch: {src}')
        os.replace(pending, dst)
    finally:
        Path(pending).unlink(missing_ok=True)


def active_game_pids() -> list[int]:
    command = "@(Get-Process cs2 -ErrorAction SilentlyContinue | Where-Object {$_.HandleCount -ne 0} | ForEach-Object {$_.Id}) -join ','"
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command],
                            check=True, capture_output=True, text=True)
    return [int(x) for x in result.stdout.strip().split(',') if x]


def preserved(relative: str) -> bool:
    key = relative.replace('\\', '/').lower()
    return (key.startswith('addons/counterstrikesharp/configs/')
            or key in ('addons/bothider/config.json', 'addons/bothider/bot_info.json',
                       'addons/botvision/config.json', 'addons/metamod/metaplugins.ini')
             or key.startswith('addons/counterstrikesharp/plugins/careermatch/'))


def external_inventory_file(relative: str) -> bool:
    """Match launcher's external-inventory protection without importing settings."""
    parts = relative.replace('\\', '/').casefold().split('/')
    return ('inventorysimulator' in parts or 'invsimcareer' in parts
            or parts[-1].startswith('inventory-simulator')
            or parts[-1] == 'invsim_career.cfg'
            or parts[-1] in ('inventories.json', 'inventorysimulator.dll', 'inventorysimulator.deps.json',
                            'invsimcareer.dll', 'invsimcareer.deps.json')
            or parts[-1].startswith('inventories.career'))


def build_capsule(stage: Path, source: Path) -> Path:
    capsule = stage / 'compatible-mod'
    capsule.mkdir(exist_ok=True)
    files: dict[str, Path] = {}
    for area in ('addons', 'cfg', 'backup'):
        for src in (source / area).rglob('*'):
            if not src.is_file():
                continue
            rel = src.relative_to(source).as_posix()
            # Preserve originals on E:, but never distribute its player roster,
            # logs, or duplicate auto-loaded gamedata backups in the capsule.
            if (src.suffix.lower() in ('.pdb', '.log') or '.previous.json' in rel
                    or rel == 'addons/BotHider/bot_info.json'):
                continue
            files[rel] = src
    pins = json.loads((stage / 'sources.json').read_text(encoding='utf-8-sig'))
    for pin in pins:
        if 'tag' not in pin:
            continue
        extracted = Path(pin['extracted']).resolve()
        if not extracted.is_relative_to(stage.resolve()):
            raise ValueError('Downloaded package escaped staging root')
        archive = stage / pin['url'].rsplit('/', 1)[1]
        if digest(archive) != pin['sha256']:
            raise ValueError(f'Archive changed: {archive}')
        for src in (extracted / 'addons').rglob('*'):
            if src.is_file() and src.suffix.lower() != '.pdb':
                files[src.relative_to(extracted).as_posix()] = src
    randomizer = next((stage / 'CS2-Bot-Randomizer-source').glob('*/BotRandomizer.csproj')).parent
    for name in ('BotRandomizer.dll', 'BotRandomizer.deps.json'):
        files['addons/counterstrikesharp/plugins/BotRandomizer/' + name] = stage / 'randomizer-build' / name
    for name in ('cosmetic_catalog.json', 'charm_placements.json'):
        files['addons/counterstrikesharp/plugins/BotRandomizer/' + name] = randomizer / name
    # Carry our existing match/weapon-purchase integration, not the older
    # upstream BotBuy that was only used as a base for the runtime capsule.
    vendor = Path(__file__).resolve().parents[1] / 'vendor'
    for plugin in ('CareerMatch', 'BotBuy'):
        for name in (plugin + '.dll', plugin + '.deps.json'):
            bundled = vendor / plugin / name
            if not bundled.is_file():
                raise FileNotFoundError(bundled)
            files['addons/counterstrikesharp/plugins/' + plugin + '/' + name] = bundled
    for rel, src in files.items():
        dst = inside(capsule, rel)
        if not dst.exists() or digest(dst) != digest(src):
            atomic_copy(src, dst)
    (capsule / 'overrides').mkdir(exist_ok=True)  # roster generated by Career, never copied
    manifest = {rel: digest(inside(capsule, rel)) for rel in files}
    (stage / 'capsule-files.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return capsule


def audit_signatures(stage: Path, game: Path, capsule: Path) -> dict:
    """File-pattern evidence only: not a claim that hooks/load/gameplay work."""
    server = (game / 'bin/win64/server.dll').read_bytes()
    results = []
    for relative in ('addons/counterstrikesharp/gamedata/gamedata.json',
                     'addons/BotController/gamedata.json', 'addons/BotHider/gamedata.json',
                     'addons/BotVision/gamedata.json'):
        contents = json.loads(inside(capsule, relative).read_text(encoding='utf-8-sig'))
        for name, entry in contents.items():
            sigs = entry.get('signatures', {}) if isinstance(entry, dict) else {}
            if sigs.get('library', '').lower() != 'server' or not sigs.get('windows'):
                continue
            pattern = sigs['windows']
            if not re.fullmatch(r'(?:[0-9A-Fa-f]{2}|\?\??)(?:\s+(?:[0-9A-Fa-f]{2}|\?\??))*', pattern):
                results.append({'file': relative, 'name': name, 'status': 'format_not_scanned'})
                continue
            regex = b''.join(b'.' if '?' in t else re.escape(bytes.fromhex(t)) for t in pattern.split())
            matches = list(re.finditer(regex, server, re.DOTALL))
            results.append({'file': relative, 'name': name, 'matches': len(matches),
                            'file_offsets': [m.start() for m in matches[:3]]})
    report = {'server_sha256': hashlib.sha256(server).hexdigest(), 'patterns': results,
              'runtime_tested': False}
    (stage / 'signature-audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def rollback(receipt_path: Path) -> None:
    if active_game_pids():
        raise RuntimeError('Close CS2 before rollback')
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    backup = receipt_path.parent
    game = Path(receipt['game'])
    save = Path(receipt['settings'])
    current_settings = json.loads(save.read_text(encoding='utf-8-sig')) if save.is_file() else {}
    external = current_settings.get('skins_inventory_mode') == 'external'
    for entry in reversed(receipt['changes']):
        if external and entry['kind'] == 'game' and external_inventory_file(entry['relative']):
            continue
        target = inside(game, entry['relative']) if entry['kind'] == 'game' else save
        old = inside(backup, entry['backup']) if entry.get('backup') else None
        if old is not None and old.exists():
            if digest(old) != entry['before']:
                raise ValueError('Backup hash mismatch')
            if external and entry['kind'] == 'settings':
                # This tool changes only mod_source_path. An older career-mode
                # receipt must not revert today's external mode or other prefs.
                previous = json.loads(old.read_text(encoding='utf-8-sig'))
                restored = dict(current_settings)
                if 'mod_source_path' in previous:
                    restored['mod_source_path'] = previous['mod_source_path']
                else:
                    restored.pop('mod_source_path', None)
                pending = backup / 'settings-rollback-external.json'
                pending.write_text(json.dumps(restored, ensure_ascii=False, indent=2), encoding='utf-8')
                atomic_copy(pending, target)
            else:
                atomic_copy(old, target)
        elif entry.get('before') is None and target.exists():
            # Keep newly added files recoverable outside all plugin autoload paths.
            recover = inside(backup, 'rolled-back-new/' + entry['relative'])
            recover.parent.mkdir(parents=True, exist_ok=True)
            os.replace(target, recover)
    receipt['rolled_back_at'] = datetime.now().isoformat()
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding='utf-8')


def apply(stage: Path, game: Path, capsule: Path, settings: Path) -> Path:
    if active_game_pids():
        raise RuntimeError('Close CS2 before installing')
    if not (game / 'steam.inf').is_file() or not settings.is_file():
        raise ValueError('Game/settings preflight failed')
    audit = audit_signatures(stage, game, capsule)
    ambiguous = [r for r in audit['patterns'] if r.get('matches') != 1]
    if ambiguous:
        raise ValueError(f'Official signature preflight requires review: {ambiguous}')
    settings_data = json.loads(settings.read_text(encoding='utf-8-sig'))
    external = settings_data.get('skins_inventory_mode') == 'external'
    if Path(settings_data['csgo_path']).resolve() != game.resolve():
        raise ValueError('Settings refer to a different game')
    source_manifest = json.loads((stage / 'capsule-files.json').read_text(encoding='utf-8'))
    for rel, expected in source_manifest.items():
        if digest(inside(capsule, rel)) != expected:
            raise ValueError('Capsule has changed after assembly')
    backup = stage / ('backup-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir()
    receipt_path = backup / 'installed.json'
    receipt = {'game': str(game.resolve()), 'settings': str(settings.resolve()),
               'capsule': str(capsule.resolve()), 'changes': [], 'runtime_tested': False}

    def checkpoint() -> None:
        receipt_path.write_text(json.dumps(receipt, indent=2), encoding='utf-8')

    def remember(target: Path, relative: str, kind: str) -> dict:
        entry = {'kind': kind, 'relative': relative, 'before': digest(target) if target.exists() else None}
        if target.exists():
            entry['backup'] = f'{kind}/{relative}'
            atomic_copy(target, inside(backup, entry['backup']))
        receipt['changes'].append(entry)
        checkpoint()  # durable recovery path before touching each target
        return entry

    try:
        for rel in source_manifest:
            if not rel.startswith('addons/'):
                continue
            if external and external_inventory_file(rel):
                continue
            src, target = inside(capsule, rel), inside(game, rel)
            if target.exists() and (preserved(rel) or digest(src) == digest(target)):
                continue
            entry = remember(target, rel, 'game')
            atomic_copy(src, target)
            entry['after'] = digest(target)
            checkpoint()
        # Older Career executables restore cosmetics from plugins_off before
        # consulting mod_source_path. Keep that existing recovery copy matched
        # as well; otherwise their very next launch silently downgrades the DLL.
        # We neither create/disable a plugin nor remove this user's backup.
        parked_root = inside(game, 'addons/counterstrikesharp/plugins_off/BotRandomizer')
        if parked_root.is_dir():
            prefix = 'addons/counterstrikesharp/plugins/BotRandomizer/'
            for rel in source_manifest:
                if not rel.startswith(prefix):
                    continue
                parked_rel = rel.replace('/plugins/BotRandomizer/', '/plugins_off/BotRandomizer/', 1)
                target, src = inside(game, parked_rel), inside(capsule, rel)
                if target.exists() and digest(src) == digest(target):
                    continue
                entry = remember(target, parked_rel, 'game')
                atomic_copy(src, target)
                entry['after'] = digest(target)
                checkpoint()
        # This is a data backup, not a plugin. CSS auto-loads every *.json here.
        duplicate = inside(game, 'addons/counterstrikesharp/gamedata/inventory-simulator.previous.json')
        if duplicate.exists() and not external:
            entry = remember(duplicate, duplicate.relative_to(game).as_posix(), 'game')
            retired = inside(backup, 'retired/' + duplicate.name)
            retired.parent.mkdir(parents=True, exist_ok=True)
            os.replace(duplicate, retired)
            entry['after'] = None
            checkpoint()
        entry = remember(settings, 'cs2.json', 'settings')
        settings_data['mod_source_path'] = str(capsule.resolve())
        staged_settings = stage / 'settings-next.json'
        staged_settings.write_text(json.dumps(settings_data, ensure_ascii=False, indent=2), encoding='utf-8')
        atomic_copy(staged_settings, settings)
        entry['after'] = digest(settings)
        receipt['completed_at'] = datetime.now().isoformat()
        checkpoint()
    except BaseException:
        rollback(receipt_path)
        raise
    return receipt_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('stage', 'audit', 'apply', 'rollback'))
    parser.add_argument('--stage', type=Path, default=STAGE)
    parser.add_argument('--game', type=Path, default=GAME)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--settings', type=Path, default=SAVE)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    if args.action == 'rollback':
        if args.receipt is None:
            parser.error('--receipt is required')
        rollback(args.receipt)
    elif args.action == 'stage':
        print(build_capsule(args.stage, args.source))
    elif args.action == 'audit':
        result = audit_signatures(args.stage, args.game, args.stage / 'compatible-mod')
        print(json.dumps({'count': len(result['patterns']), 'non_unique': [r for r in result['patterns'] if r.get('matches') != 1]}, indent=2))
    else:
        print(apply(args.stage, args.game, args.stage / 'compatible-mod', args.settings))


if __name__ == '__main__':
    main()
