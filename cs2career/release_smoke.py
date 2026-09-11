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
            from .cs2.dialogue import build_dialogue
            from .career import incidents
            from .career import arcs
            from .career import player_transfers
            assert player_transfers.wins(20, -8) and not player_transfers.wins(1, 6)
            from .application import ApplicationState
            from .json_bytes import orjson, encode
            assert orjson is not None, 'Packaged native JSON encoder is missing'
            assert json.loads(encode({'test': '完整中文', 'rounds': [1, 2]}))['test'] == '完整中文'
            app = ApplicationState()
            app.create_career(dict(mode='create', era='2026', name='PackagedTransferTest', org='Packaged Test Club', origin='academy', role='rifle', region='EU'))
            while app.career.story_queue:
                row = app.career.story_queue[0]
                app.career.ack_story(row['id'], (row.get('choices') or [{'id':''}])[0]['id'], app.season)
            target = next(r for r in player_transfers.public(app.career, app.season)['targets'] if not r['blocked'])
            app.personal_command(lambda c,s: player_transfers.apply(c,s,target['team_id'],target['role']))
            assert len(app.career.personal_transfers['attempts']) == 1
            from .career import Career
            assert Career.load().personal_transfers['attempts'] == app.career.personal_transfers['attempts']
            before=app.career.attr_points
            arcs.queue(app.career,app.season,'romance_start','packaged-test')
            row=next(r for r in app.career.story_queue if r.get('arc')=='romance_start')
            app.personal_command(lambda c,s:c.ack_story(row['id'],'none',s))
            assert app.career.attr_points==before+2
            assert arcs.state(Career.load())['romance']=='single'
            assert len(arcs.config()['injuries'])>=8
            report['story_arcs']='bundled JSON/choice/reward/paired save/reload passed'
            dialogue = build_dialogue()
            assert dialogue['enabled'] and len(dialogue['rules']) == 5
            assert dialogue['schema_version'] == 2 and isinstance(dialogue['scenes'], list)
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
            report.update(ok=True, difficulties=3, bots_per_match=9, source_model=manifest['difficulty_model'], dialogue_rules=len(dialogue['rules']), dialogue_schema=dialogue['schema_version'], personal_transfer='create/apply/persist/reload passed')
    except Exception:
        report['error'] = traceback.format_exc()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
