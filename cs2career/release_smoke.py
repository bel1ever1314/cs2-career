"""Packaged EXE smoke test; isolates before importing any application module."""
import json
import os
from pathlib import Path
import tempfile
import traceback


def run(output: Path) -> None:
    report = {'ok': False, 'scope': 'packaged imports/resources/9-bot generation; not GUI or live CS2'}
    try:
        with tempfile.TemporaryDirectory(prefix='cs2career-release-smoke-') as folder:
            root = Path(folder)
            os.environ['CS2CAREER_SAVE_DIR'] = str(root/'save')
            os.environ['CS2CAREER_EXTENSION_DIR'] = str(root/'extensions')
            os.environ['CS2CAREER_NO_GAME'] = '1'
            from .paths import save_root, vendor_root
            from .web.server import STATE
            from .cs2.launch import build_request, install_match_avatars, game_levels_ok
            from .cs2.profiles import generate_match_vpk, active_manifest
            from .world import build_teams
            assert save_root().resolve().is_relative_to(root.resolve())
            assert game_levels_ok(root/'mock-game')
            teams = build_teams('2026', 2026)
            a,b = teams[:2]
            request = build_request(a,b,a['players'][0]['name'],'de_mirage','ct')
            game = root/'mock-game'
            install_match_avatars(game,request)
            hashes = []
            for level in ('Low','Medium','High'):
                manifest = generate_match_vpk(game,request,level,root/'cache')
                assert active_manifest(game)['valid']
                assert len(manifest['bots']) == 9
                hashes.append(manifest['vpk_sha256'])
            assert len(set(hashes)) == 3
            for relative in ('CareerMatch/CareerMatch.dll','BotBuy/BotBuy.dll',
                             'InvsimCareer/InvsimCareer.dll',
                             'InventorySimulator/plugins/InventorySimulator/InventorySimulator.dll'):
                assert (vendor_root()/relative).read_bytes()[:2] == b'MZ'
            report.update(ok=True, difficulties=3, bots_per_match=9, source_model=manifest['difficulty_model'])
    except Exception:
        report['error'] = traceback.format_exc()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
