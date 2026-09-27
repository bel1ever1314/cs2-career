"""Packaged EXE smoke test; isolates before importing any application module."""
import json
import os
from pathlib import Path
import tempfile
import traceback


def run(output: Path) -> None:
    report = {'ok': False, 'scope': '1.6 packaged resources/calendar/offseason/local ladders/9 and 10 Bot generation; not GUI or live CS2'}
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
            from .career.story_timing import open_major_break
            open_major_break(app.career,app.season,dict(id='smoke-major',name='Smoke fixture',type='major',dates=[app.season.date]))
            arcs.queue(app.career,app.season,'romance_start','packaged-test')
            row=next(r for r in app.career.story_queue if r.get('arc')=='romance_start')
            app.personal_command(lambda c,s:c.ack_story(row['id'],'none',s))
            assert app.career.attr_points==before+2
            assert arcs.state(Career.load())['romance']=='single'
            assert len(arcs.config()['injuries'])>=8
            from .career.localization import present
            from .career.notifications import informational
            assert all(n.get('title_en') and n.get('text_en') and all(c.get('label_en') for c in n['choices'])
                       for n in arcs.config()['chapters'].values())
            assert present({'text':'这是生涯世界的伤病设定，不代表现实诊断。'})['text_en'].startswith('This is a fictional')
            assert not informational({'kind':'awards','class':'major'})
            assert informational({'kind':'awards','class':'t1'})
            report['narrative_revision']='English chapters/choices/messages bundled; Major ceremonies remain interactive'
            report['story_arcs']='bundled JSON/choice/reward/paired save/reload passed'
            dialogue = build_dialogue()
            assert dialogue['enabled'] and len(dialogue['rules']) >= 11
            assert dialogue['schema_version'] == 2 and isinstance(dialogue['scenes'], list)
            from .cs2.launch import MOVEMENT_MODES
            from .league.calendar import calendar_for
            from . import __version__
            assert __version__=='1.6.0' and MOVEMENT_MODES==('classic',)
            assert len([k for k in arcs.config()['chapters'] if k.startswith('major_exit_')])==18
            for year in (2024,2025,2026):
                assert len([e for e in calendar_for(year)['events'] if e['type']=='major'])==2
            from .paths import static_dir
            assert (static_dir()/'desk/locales/en.js').is_file()
            assert (static_dir()/'desk/season.js').is_file()
            assert (static_dir()/'desk/quick-results.js').is_file()
            assert (static_dir()/'desk/quick-stage.css').is_file()
            assert (static_dir()/'desk/arena.js').is_file()
            assert (static_dir()/'desk/arena.css').is_file()
            arena = app.arena
            selection = [p['player_id'] for p in arena.catalog(app)[:10]]
            arena.matchmake(app,dict(revision=0,human_id=selection[-1]))
            while arena.data['lobby']['phase'] in ('draft','veto','side'):
                lobby=arena.data['lobby']
                body=dict(revision=arena.data['revision'])
                if not arena.turn(lobby)['human']:arena.advance(body)
                elif lobby['phase']=='draft':
                    pid=next(p for p in lobby['selection'] if p not in lobby['a']+lobby['b'])
                    arena.pick(dict(body,player_id=pid))
                elif lobby['phase']=='veto':
                    arena.ban(dict(body,map=next(m for m in lobby['map_pool'] if m not in [b['map'] for b in lobby['bans']])))
                else:arena.choose_side(dict(body,side='ct'))
            assert len(arena.data['lobby']['a'])==len(arena.data['lobby']['b'])==5
            assert len(arena.data['lobby']['bans'])==6
            report['matchmaking']='unified Elo matchmaking / captain draft / map veto passed'
            from .career.quick_report import series_report
            assert not series_report({'maps':[]},None,None)['data_complete']
            report['quick_results']='scorecard module and styles bundled; missing stats remain incomplete'
            from .career.fast_mode import configure_season, season_mode
            from .career.season_board import public as season_board
            configure_season(app.career,app.season,True,app.season.year)
            app.persist()
            assert Career.load().assist['quick_mode'] is True
            assert season_mode(app.career,app.season)['selected']=='quick'
            board=season_board(app.career,app.season)
            assert len(board['events'])==len(app.season.events)
            from .career.news import publish
            publish(app.career,app.season,'monthly:smoke','月报','测试',popup=True,
                    title_en='Monthly report',text_en='Test')
            app.persist()
            assert not any(row.get('publication_key')=='monthly:smoke' for row in app.career.story_queue)
            assert not any(row.get('publication_key')=='monthly:smoke' for row in app.career.inbox)
            assert any(row.get('publication_key')=='monthly:smoke' for row in app.career.incident_state['arcs']['history'])
            report['season_revision']='season mode / itinerary / quiet monthly report / saved mode passed'
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
            from .cs2.launch import build_lobby_request, install_match_identities
            observer_request=build_lobby_request(a,b,'','de_mirage','observer-smoke')
            install_match_avatars(game,observer_request)
            observer_manifest=generate_match_vpk(game,observer_request,'Medium',root/'cache')
            install_match_identities(game,observer_request)
            assert active_manifest(game)['valid'] and observer_manifest['count']==10
            assert observer_request['observer'] and not observer_request['human_player_id']
            report['arena']='local draft saved; observer ten-profile VPK and identities passed (not live game)'
            for relative in ('CareerMatch/CareerMatch.dll','BotBuy/BotBuy.dll',
                             'InvsimCareer/InvsimCareer.dll',
                             'InventorySimulator/plugins/InventorySimulator/InventorySimulator.dll'):
                assert (vendor_root()/relative).read_bytes()[:2] == b'MZ'
            report.update(ok=True, version=__version__, difficulties=3, bots_per_match=9, source_model=manifest['difficulty_model'], dialogue_rules=len(dialogue['rules']), dialogue_schema=dialogue['schema_version'], natural_dust2='excluded', major_exit_chapters=18, personal_transfer='create/apply/persist/reload passed')
    except Exception:
        report['error'] = traceback.format_exc()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
