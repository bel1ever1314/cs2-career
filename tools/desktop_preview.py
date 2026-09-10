"""A disposable UI fixture. Never loads or writes the player's saves.

Run with --smoke for every page and the creation form; otherwise opens the
same fixture for visual inspection and clicking. Uses the actual domain state.
"""
import sys
from contextlib import ExitStack
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cs2career.desktop.bootstrap import prepare_tk_runtime
prepare_tk_runtime()
from cs2career.application import ApplicationState
from cs2career.career import Career
from cs2career.league import Season
from cs2career.desktop.app import DesktopApp


def fixture():
    season = Season()
    career = Career()
    career.save = lambda:None
    team = next(t for t in season.teams if t['name']=='Vitality')
    career.create({'era':'2026','mode':'join','team_id':team['id'],'replace':'ropz','role':'lurk'},season)
    season.career = career
    season.save = lambda:None
    state = ApplicationState.__new__(ApplicationState)
    state.season, state.career = season, career
    state.persist = lambda:None
    season.try_ingest_pending_cs2 = lambda:''
    def create(payload):
        new_season = Season(int(payload['era']),payload['era'])
        new_season.save = lambda:None
        new_career = Career()
        new_career.save = lambda:None
        new_season.career = new_career
        new_season.try_ingest_pending_cs2 = lambda:''
        msg = new_career.create(payload,new_season)
        state.season,state.career = new_season,new_career
        return msg
    state.create_career = create
    return state


def main():
    state = fixture()
    with ExitStack() as stack:
        stack.enter_context(patch('cs2career.cs2.launch.settings',return_value={}))
        stack.enter_context(patch('cs2career.cs2.launch.cs2_is_live',return_value=False))
        for name in ('start_match','save_settings','install_mod','install_skins_mod','update_skins_gamedata'):
            stack.enter_context(patch('cs2career.cs2.'+name,return_value={'msg':'隔离预览：没有修改游戏文件。'}))
        app = DesktopApp(state,testing=True)
        app.title('CS2 Career · Design Preview [isolated]')
        if '--compact' in sys.argv:
            app.geometry('1060x680')
        if '--smoke' in sys.argv:
            for width,height in ((1440,900),(1060,680)):
                app.geometry(f'{width}x{height}')
                for key,_,_ in app.NAV:
                    app.go(key)
                    app.update()
                    if app.callback_errors:
                        raise AssertionError('\n'.join(app.callback_errors))
                    for nav in app.nav_buttons.values():
                        assert nav.winfo_y()+nav.winfo_height()<=app.sidebar.winfo_height(), 'Sidebar item clipped'
                    if key=='dashboard':
                        cta = next(w for w in descendants(app.page_host) if isinstance(w,tk.Button) and w.cget('text')=='查看赛事邀请  →')
                        assert cta.winfo_width()>=cta.winfo_reqwidth(), 'Match hero CTA clipped'
                    print(f'PASS {width}x{height} {key}',flush=True)
                app.show_setup()
                app.update()
                setup = app.page_host.winfo_children()[0]
                for origin in ('street','academy','prodigy'):
                    setup.select(origin)
                    app.update()
                setup.set_mode('join')
                app.update()
                if app.callback_errors:
                    raise AssertionError('\n'.join(app.callback_errors))
                print(f'PASS {width}x{height} setup variants',flush=True)
            exercise_commands(app)
            app.close()
        else:
            app.mainloop()


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def exercise_commands(app):
    """Verify the UI passes the nested match id and current inventory IDs."""
    state = app.state
    pair = {'event':{'id':'test-event','name':'Preview Cup'},'match':{
        'id':'test-match-42','team_a':'Vitality','team_b':'FaZe',
        'best_of':3,'series':'0-0','pending_map':'mirage','label':'Final'}}
    with patch.object(state.season,'_your_match_public',return_value=pair):
        for page in ('dashboard','schedule'):
            app.go(page)
            app.update()
        with patch.object(app,'background',side_effect=lambda f:f()), patch.object(state.season,'launch_your_map') as launch:
            next(w for w in descendants(app.page_host) if isinstance(w,tk.Button) and w.cget('text')=='亲自上场  →').invoke()
            launch.assert_called_once_with('test-match-42','ct')
    app.go('skins')
    app.update()
    tables = [w for w in descendants(app.page_host) if isinstance(w,ttk.Treeview)]
    market = tables[1]
    market.selection_set(market.get_children()[0])
    before = len(state.career.inventory)
    next(w for w in descendants(app.page_host) if isinstance(w,tk.Button) and w.cget('text')=='购买所选饰品').invoke()
    app.update()
    assert len(state.career.inventory)==before+1
    inventory = next(w for w in descendants(app.page_host) if isinstance(w,ttk.Treeview))
    inv_id = state.career.inventory[-1]['id']
    inventory.selection_set(inv_id)
    with patch('cs2career.career.skins.sync_live'):
        next(w for w in descendants(app.page_host) if isinstance(w,tk.Button) and w.cget('text')=='装备到 T').invoke()
        app.update()
        assert inv_id in state.career.equipped_t.values()
        inventory = next(w for w in descendants(app.page_host) if isinstance(w,ttk.Treeview))
        inventory.selection_set(inv_id)
        next(w for w in descendants(app.page_host) if isinstance(w,tk.Button) and w.cget('text')=='卸下装备').invoke()
        app.update()
        assert inv_id not in state.career.equipped_t.values()
    app.show_setup()
    app.update()
    setup = app.page_host.winfo_children()[0]
    setup.name.set('DesktopTester')
    setup.org.set('Desktop Fixture')
    setup.select('prodigy')
    setup.submit()
    app.update()
    assert app.state.career.origin=='prodigy'
    assert app.state.career.player_name=='DesktopTester'
    assert app.page=='dashboard'
    if app.callback_errors:
        raise AssertionError('\n'.join(app.callback_errors))
    print('PASS live match contract, skin purchase/equip/unequip, new-career submit',flush=True)


if __name__=='__main__':
    main()
