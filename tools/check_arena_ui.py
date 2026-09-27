"""Real lobby HTTP commands + headless Edge; fake roster, no game or career save.

python -B tools/check_arena_ui.py --output D:/CS2CareerBuilds/v1.6.0/arena/ui
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='arena-ui-') as tmp:
        os.environ.update(CS2CAREER_SAVE_DIR=str(Path(tmp)/'save'),CS2CAREER_EXTENSION_DIR=str(Path(tmp)/'extensions'),CS2CAREER_NO_GAME='1')
        from test_arena import fixture_state,result_for
        from cs2career.arena import Arena
        from cs2career.web.server import create_server
        from playwright.sync_api import sync_playwright
        state=fixture_state();state.arena=Arena(Path(tmp)/'arena.json')
        static=ROOT/'cs2career/web/static'
        html=re.sub(r'<script\b[^>]*>.*?</script>|<link\b[^>]*>','',(static/'index.html').read_text('utf-8'),flags=re.S)
        server=create_server(state);server.game_disabled=True
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        base=f'http://127.0.0.1:{server.server_port}'
        checks=[];errors=[]
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True)
                for lang in ('zh-CN','en'):
                    page=browser.new_page(viewport={'width':1280,'height':720})
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    page.route(base+'/',lambda route:route.fulfill(status=200,content_type='text/html',body=html))
                    page.goto(base+'/')
                    for css in ('style.css','desk.css','theme.css','desk/i18n.css','desk/arena.css'):page.add_style_tag(content=(static/css).read_text('utf-8'))
                    page.evaluate("""token=>{
                      sessionStorage.setItem('career-token',token);
                      window.S={playtest:true,career:{}}; window.ROLE={awp:'AWP',entry:'Entry',lurk:'Lurk',igl:'IGL',rifle:'Rifle'};
                      window.esc=v=>String(v??'').replace(/[<>&\"]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','\"':'&quot;'}[c]));
                      window.get=async url=>{const r=await fetch(url,{headers:{'X-Career-Token':token}});return r.json();};
                      window.post=async(url,body)=>{const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-Career-Token':token},body:JSON.stringify(body)});return r.json();};
                      window.toast=()=>{};window.confirm=()=>true;
                      window.CareerUI={pages:{},head:(title,hint)=>`<h2>${esc(title)}</h2><p>${esc(hint)}</p>`};
                      document.getElementById('view-arena').classList.add('on');
                    }""",server.token)
                    for js in ('desk/locales/en.js','desk/i18n.js','desk/dom.js','desk/arena.js'):page.add_script_tag(content=(static/js).read_text('utf-8'))
                    page.evaluate('CareerUI.paint=CareerDOM.paint; window.arenaActive=true')
                    page.evaluate('lang=>CareerI18n.setLocale(lang)',lang)
                    for scenario in ('captain','member','custom'):
                        mode='custom' if scenario=='custom' else 'rank'
                        state.arena.data['lobby']=None;state.arena.save()
                        catalog=state.arena.catalog(state)
                        human=(catalog[0] if scenario=='captain' else catalog[-1])['player_id']
                        state.career.you_card=deepcopy(state.arena.roster(state)[human])
                        page.evaluate("""async()=>{await CareerUI.pages.arena({},document.getElementById('view-arena'),()=>window.arenaActive);} """)
                        page.locator(f'[data-arena="mode"][data-mode="{mode}"]').click()
                        def inspect(phase):
                            for width,height in ((1280,720),(1920,1080),(1024,576),(853,480)):
                                page.set_viewport_size({'width':width,'height':height})
                                page.evaluate("CareerI18n.apply(document.getElementById('view-arena'))")
                                overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth+1')
                                assert not overflow,(width,lang,scenario,phase)
                                if lang=='en':
                                    chinese=page.locator('#view-arena').inner_text()
                                    assert not re.search(r'[\u4e00-\u9fff]',chinese),(phase,chinese)
                                checks.append(dict(language=lang,scenario=scenario,phase=phase,viewport=[width,height],overflow=overflow))
                                if width==1280:page.screenshot(path=str(args.output/f'{lang}-{scenario}-{phase}.png'),full_page=True)
                            page.set_viewport_size({'width':1280,'height':720})
                        if mode=='rank':
                            assert page.locator('[data-arena=choose],[data-arena=select],[data-arena-pool]').count()==0
                            assert page.locator('[data-bound-player]').get_attribute('data-bound-player')==human
                            inspect('queue')
                            page.locator('[data-arena=matchmake]').click()
                            page.locator('.arena-stage').wait_for()
                            if scenario=='member':
                                page.evaluate('window.arenaActive=false')
                                revision=state.arena.data['revision']
                                page.wait_for_timeout(1100)
                                assert revision==state.arena.data['revision'],'Navigation must pause AI turns'
                                page.evaluate("""async()=>{window.arenaActive=true;await CareerUI.pages.arena({},document.getElementById('view-arena'),()=>window.arenaActive);} """)
                            seen=set()
                            import time
                            deadline=time.monotonic()+45
                            while state.arena.data['lobby']['phase']!='ready':
                                assert time.monotonic()<deadline,'Draft/veto failed to progress'
                                l=state.arena.data['lobby'];turn=state.arena.turn(l)
                                if turn['human']:
                                    if l['phase'] not in seen:inspect(l['phase']);seen.add(l['phase'])
                                    action={'draft':'pick','veto':'ban','side':'side'}[l['phase']]
                                    revision=state.arena.data['revision']
                                    page.locator(f'[data-arena={action}]:enabled').first.click()
                                    page.wait_for_function("r=>Number(document.getElementById('view-arena').dataset.arenaRevision)>r",arg=revision)
                                else:
                                    assert page.locator('[data-arena=pick]:enabled,[data-arena=ban]:enabled,[data-arena=side]:enabled').count()==0
                                    page.wait_for_timeout(100)
                            page.locator('.arena-ready').wait_for()
                            assert len(state.arena.data['lobby']['bans'])==6
                            assert state.arena.data['lobby']['human_id']==human
                            assert page.locator('[data-arena-map]').count()==0
                            assert page.locator('.arena-assigned-role').count()==10
                            for side in ('a','b'):
                                assert set(page.locator('.side-'+side+' [data-match-role]').evaluate_all('(els)=>els.map(e=>e.dataset.matchRole)'))=={'awp','rifle','entry','lurk','igl'}
                        else:
                            human=''
                            page.locator('[data-arena=recommend]').click()
                            page.locator('[data-arena=create]:enabled').click()
                            page.locator('[data-arena-map]').select_option('mirage')
                            page.locator('[data-arena-ct]').select_option('b')
                            # A server refresh must preserve unsaved controls and
                            # the actual select node (no flashing/replacement).
                            page.evaluate('window.savedSelector=document.querySelector("[data-arena-map]")')
                            page.evaluate("""async()=>{await CareerUI.pages.arena({},document.getElementById('view-arena'),()=>window.arenaActive);} """)
                            assert page.evaluate('window.savedSelector===document.querySelector("[data-arena-map]")')
                            assert page.locator('[data-arena-map]').input_value()=='mirage'
                            page.locator('[data-arena=configure]').click()
                            page.wait_for_function("document.querySelector('[data-arena=configure]')?.disabled===false")
                        l=state.arena.data['lobby']
                        assert len(l['a'])==len(l['b'])==5
                        assert l['human_id']==human
                        inspect('ready')
                        # Full result read/display, without invoking the game launcher.
                        l.update(phase='launched',nonce=f'qa-{lang}-{scenario}',started_at='2026-01-01T00:00:00Z')
                        state.arena.ingest({'revision':state.arena.data['revision']},result_for(l))
                        page.evaluate("""async()=>{await CareerUI.pages.arena({},document.getElementById('view-arena'),()=>window.arenaActive);} """)
                        assert page.locator('.arena-result tbody tr:not(.arena-team)').count()==10
                        assert page.locator('.arena-you').count()==(1 if mode=='rank' else 0)
                        inspect('result')
                    # No career: ranked must not silently select the first pro.
                    state.arena.data['lobby']=None;state.arena.save();state.career.exists=False
                    page.evaluate("async()=>{await CareerUI.pages.arena({},document.getElementById('view-arena'),()=>window.arenaActive);}")
                    page.locator('[data-arena=mode][data-mode=rank]').click()
                    assert page.locator('[data-arena=matchmake]').is_disabled()
                    assert page.locator('[data-bound-player]').get_attribute('data-bound-player')==''
                    page.locator('[data-arena=mode][data-mode=custom]').click()
                    assert page.locator('[data-arena=recommend]').is_enabled()
                    state.career.exists=True
                    page.close()
                browser.close()
        finally:server.shutdown();worker.join();server.server_close()
        report=dict(ok=not errors,cases=checks,errors=errors)
        (args.output/'checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        if errors:raise AssertionError(errors)
        print(json.dumps(dict(ok=True,cases=len(checks),errors=errors)))


if __name__=='__main__':main()
