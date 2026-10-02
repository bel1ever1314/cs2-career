"""Packaged EXE smoke test; isolates before importing any application module."""
import json
import hashlib
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
            assert (static_dir()/'desk/skin-crafts.js').is_file()
            assert (static_dir()/'desk/skin-crafts.css').is_file()
            assert (static_dir()/'desk/skin-inspect.js').is_file()
            assert (static_dir()/'desk/skin-inspect.css').is_file()
            assert (static_dir()/'desk/tactics.js').is_file()
            assert (static_dir()/'desk/tactics.css').is_file()
            report['tactical_editor_assets'] = {name: hashlib.sha256((static_dir()/'desk'/name).read_bytes()).hexdigest()
                                               for name in ('tactics.js', 'tactics.css')}
            from . import tactics
            from .paths import data_file
            radar_meta = json.loads(data_file('tactical_map_dust2.json').read_text('utf-8'))
            radar = static_dir()/'tactical_maps/de_dust2.png'
            assert hashlib.sha256(radar.read_bytes()).hexdigest() == radar_meta['image_sha256']
            playbook = tactics.public_library()
            assert {t['side'] for t in playbook['tactics']} == {'t', 'ct'}
            assert playbook['slot_labels'][0] == '你 · 手动操作'
            point = tactics.pixel_to_world([512, 512])
            assert tactics.world_to_pixel(point) == [512, 512]
            sample = playbook['tactics'][0]
            result = tactics.save_tactic(sample)
            assert result['ok'] and tactics.library_path().resolve().is_relative_to(root.resolve())
            assert tactics.load_library()['tactics'] == result['tactics']
            dust2_snapshot = tactics.library_path().read_bytes()
            images = 0
            for entry in tactics.available_maps():
                code = entry['map']
                meta = tactics.map_metadata(code)
                for layer in meta['layers']:
                    image = static_dir()/layer['image'].lstrip('/')
                    assert image.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'
                    assert hashlib.sha256(image.read_bytes()).hexdigest() == layer['image_sha256']
                    images += 1
                for pixel in ([0, 0], [512, 512], [1024, 1024]):
                    actual = tactics.world_to_pixel(tactics.pixel_to_world(pixel, code), code)
                    assert all(abs(a-b) < 1e-8 for a, b in zip(actual, pixel))
                if code == tactics.MAP:
                    continue
                # The same ID is deliberately saved in every isolated map file.
                row = json.loads(json.dumps(sample))
                for slot in row['slots']:
                    for step in slot['steps']:
                        step['position'] = tactics.pixel_to_world([512, 512], code)
                        step['look_at'] = tactics.pixel_to_world([550, 512], code)
                saved = tactics.save_tactic(row, code)
                assert tactics.load_library(code)['tactics'] == saved['tactics']
                assert tactics.library_path(code).resolve().is_relative_to(root.resolve())
                assert tactics.library_path().read_bytes() == dust2_snapshot
            assert len(tactics.available_maps()) == 10 and images == 13
            duty_sample = json.loads(json.dumps(sample))
            duty_sample.update(id='smoke_double_awp', assignment='ability', human_slot=4)
            for slot in duty_sample['slots']:
                slot['duty'] = 'awp' if slot['slot'] in (1, 2) else 'rifle'
            saved = tactics.save_tactic(duty_sample)
            reloaded = next(t for t in tactics.load_library()['tactics'] if t['id'] == 'smoke_double_awp')
            assert reloaded == duty_sample and saved['ok']
            assert sum(s['duty'] == 'awp' for s in reloaded['slots']) == 2
            report['tactical_duties'] = 'ability assignment / manual human slot4 / repeated AWP duties saved and reloaded in isolated test save'
            gait_sample = json.loads(json.dumps(duty_sample))
            gait_sample['id'] = 'smoke_segment_gaits'
            for slot in gait_sample['slots']:
                for i, step in enumerate(slot['steps']):
                    step['movement'] = 'run' if i % 2 == 0 else 'walk'
            saved = tactics.save_tactic(gait_sample)
            gait_reload = next(t for t in tactics.load_library()['tactics'] if t['id'] == gait_sample['id'])
            assert saved['ok'] and gait_reload == gait_sample
            assert all(step['movement'] in ('run', 'walk') for slot in gait_reload['slots'] for step in slot['steps'])
            report['tactical_travel_gaits'] = 'per-segment run/walk saved and reloaded; legacy absent field means run; live movement untested'
            report['tactical_maps'] = [row['map'] for row in tactics.available_maps()]
            report['tactical_editor'] = ('10 map metadata / 13 local radar hashes / five slots / T and CT examples / '
                                         'coordinate roundtrip / independent same-ID map save and reload passed; '
                                         'look arrows, repeated duties and post-plant tasks bundled; live waypoint continuity and buying untested')
            from .career import skins
            packs = skins.pro_bundle()['packs']
            assert {p['player'] for p in packs} == {'donk', 'zywoo', 'monesy', 'niko'}
            for pack in packs:
                source = skins.pro_bundle()['skins']
                assert {'knife', 'gloves'} <= {source[r['skin_id']]['slot'] for r in pack['items']}
                assert all(f"{r['def']}:{r['paint']}" in skins.inspect_catalog()['items'] for r in pack['items'])
            old_money = app.career.money
            app.career.import_loadout(packs[0]['id'])
            item = next(r for r in app.career.inventory if r['slot']=='ak47')
            kit = skins.sticker_catalog()['stickers'][0]['def']
            app.career.craft_skin(item['id'], [{'def':kit,'slot':0,'schema':0,'wear':0}])
            sides = skins.sides_for(item['slot'])
            app.career.equip_skin(item['id'], sides[0])
            body = skins.equipped_v5_body(app.career.inventory, app.career.equipped_ct, app.career.equipped_t)
            weapon = body['ctWeapons' if sides[0]=='ct' else 'tWeapons'][str(item['def'])]
            assert weapon['stickers'][0]['def'] == kit and weapon['hash']
            assert app.career.money == old_money
            count = len(app.career.inventory)
            app.career.import_loadout(packs[0]['id'])
            assert len(app.career.inventory)==count
            assert Career.load().inventory==app.career.inventory
            report['cosmetics']='four expanded free templates with knives/gloves / pinned online 3D bridge / model-specific sticker craft / V5 hash / duplicate import / save reload passed; no live CS2 or viewer render in this self-test'
            arena = app.arena
            selection = [p['player_id'] for p in arena.catalog(app)[:10]]
            arena.matchmake(app,dict(revision=0))
            assert arena.data['lobby']['human_id']==app.career.you_card['player_id']
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
            for side in ('a','b'):
                assert {arena.data['lobby']['roster'][pid]['role'] for pid in arena.data['lobby'][side]}=={'awp','entry','lurk','rifle','igl'}
            report['matchmaking']='career-bound identity / five distinct match positions / captain draft / map veto passed'
            from .arena import Arena
            custom = Arena(root/'custom-arena.json')
            custom.create(app, dict(revision=0, mode='custom', players=selection, human_id=''))
            for side in ('a','b'):
                assert {custom.data['lobby']['roster'][pid]['role'] for pid in custom.data['lobby'][side]} == {'awp','entry','lurk','rifle','igl'}
            assert custom.data['lobby']['role_assignment_version'] == 1
            report['custom_positions'] = 'each side has five assigned positions on match snapshots; observer selection preserved'
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
            game.mkdir(parents=True, exist_ok=True)
            (game/'gameinfo.gi').write_text(
                '"GameInfo"\n{\n\t"FileSystem"\n\t{\n\t\t"SearchPaths"\n\t\t{\n'
                '\t\t\tGame csgo\n\t\t}\n\t}\n}\n', encoding='utf-8')
            from .cs2.gameinfo import ensure_gameinfo_mounts
            assert ensure_gameinfo_mounts(game)
            gi_before = (game/'gameinfo.gi').read_bytes()
            assert not ensure_gameinfo_mounts(game)
            assert gi_before == (game/'gameinfo.gi').read_bytes()
            assert b'LayeredOnMod' not in gi_before
            report['gameinfo'] = 'current Valve config preserved / two mounts / idempotent isolated replacement passed'
            install_match_avatars(game,request)
            hashes = []
            for level in ('Low','Medium','High'):
                manifest = generate_match_vpk(game,request,level,root/'cache')
                assert active_manifest(game)['valid']
                assert len(manifest['bots']) == 9
                from .cs2.profiles import read_db
                import re
                assert not re.search(r'(?mi)WeaponPreference\s*=\s*(aug|scar20|g3sg1)\b', read_db(game/'overrides/botprofile.vpk'))
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
            # Deployment compares this to the reviewed plugin, so rebuilding
            # cannot silently bundle an earlier CareerMatch than the game copy.
            report['career_plugin_sha256'] = hashlib.sha256(
                (vendor_root()/'CareerMatch/CareerMatch.dll').read_bytes()).hexdigest()
            report['botbuy_plugin_sha256'] = hashlib.sha256(
                (vendor_root()/'BotBuy/BotBuy.dll').read_bytes()).hexdigest()
            # Exercise the bundled calendar classifier and persisted birthday
            # snapshot outside any Major window, not the developer's saves.
            from .career import story_timing
            birthday = app.career.next_calendar_day(app.season, f'{app.season.year}-12-31')
            assert birthday is not None
            app.season.date = birthday
            app.career.last_birthday = ''
            app.career.story_queue = []
            app.career.incident_state['story_timing'] = {'schema_version': 1, 'windows': [], 'deferred': []}
            app.career._birthday_tick(app.season)
            story_timing.reconcile(app.career, app.season)
            rows = [r for r in app.career.story_queue if r.get('when') == 'teammate_birthday']
            assert rows and all(r['date'] == birthday and r['timing'] == 'calendar' for r in rows)
            app.persist()
            assert any(r.get('id') == rows[0]['id'] for r in Career.load().story_queue)
            report['calendar_occasions'] = 'birthday dated outside Major window; saved/reloaded without deferral'
            report.update(ok=True, version=__version__, difficulties=3, bots_per_match=9, source_model=manifest['difficulty_model'], dialogue_rules=len(dialogue['rules']), dialogue_schema=dialogue['schema_version'], natural_dust2='excluded', major_exit_chapters=18, personal_transfer='create/apply/persist/reload passed')
    except Exception:
        report['error'] = traceback.format_exc()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
