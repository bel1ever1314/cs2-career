"""Render the real quick-mode CSS/JS with isolated data, never a player save.

Usage: python -B tools/check_quick_stage_layout.py --output D:/.../layout
Requires Playwright and installed Microsoft Edge. No downloads or game launch.
"""
import argparse
import json
from pathlib import Path
import re
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
STATIC=ROOT/'cs2career/web/static'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    html=(STATIC/'index.html').read_text('utf-8')
    html=re.sub(r'<script\b[^>]*>.*?</script>','',html,flags=re.S)
    html=re.sub(r'<link\b[^>]*>','',html)
    cases=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=True)
        for width,height in ((1280,720),(1920,1080),(1024,576),(853,480),(1536,864)):
            for language in ('zh-CN','en'):
                page=browser.new_page(viewport=dict(width=width,height=height))
                page.set_content(html)
                for css in ('style.css','desk.css','theme.css','desk/spectator.css','desk/i18n.css','desk/quick-stage.css'):
                    page.add_style_tag(content=(STATIC/css).read_text('utf-8'))
                page.evaluate("""() => {
                  window.S={year:2026,date:'2026-06-20',career:{exists:true,team_name:'Test Club',assist:{quick_mode:true},season_mode:{phase:'running',can_choose:false}}};
                  window.esc=value=>String(value??'').replace(/[<>&\"]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','\"':'&quot;'}[c]));
                  window.running=true;
                  window.CareerUI={pages:{},head:()=>'',paint:(host,text)=>host.innerHTML=text,route:()=>({view:'season'})};
                  window.CareerAssist={isActive:()=>window.running};
                  window.data={year:2026,date:S.date,summary:{wins:12,losses:7},events:Array.from({length:100},(_,i)=>({id:'event'+i,
                    name:i===30?'BLAST.tv Austin Major 2026':'Sample Tournament '+i,participation:'entered',status:i<30?'done':i===30?'live':'upcoming',
                    start:'2026-06-20',end:'2026-06-25',own_matches:i===30?[{id:'m30',team_a:'Test Club',team_b:'Counter-Strike International',stage:'Quarter-final',best_of:3}]:[]}))};
                  S.events=data.events;
                  data.series_results=Array.from({length:120},(_,i)=>({id:'result'+i,date:'2026-06-01',won:i%3!==0}));
                  window.get=async()=>data;
                  window.reportMatch={id:'m30',event_id:'event30',result_id:'result119',date:'2026-06-20',team_a:'Test Club',team_b:'Counter-Strike International',
                    player_team:'Test Club',player_id:'p2',series:'2 : 1',best_of:3,played:true,winner:'Test Club',winners:['Test Club','Counter-Strike International','Test Club'],data_complete:true,
                    totals:Array.from({length:10},(_,i)=>({player_id:'p'+i,name:i===2?'My Player':'Player '+i,team:i<5?'Test Club':'Counter-Strike International',
                      k:46,d:38,a:12,damage:4567,adr:82.5,kast:.76,rating:i===2?1.35:1.12,data_complete:true}))};
                }""")
                for js in ('desk/locales/en.js','desk/i18n.js','desk/quick-results.js','desk/season.js'):
                    page.add_script_tag(content=(STATIC/js).read_text('utf-8'))
                page.evaluate("""locale=>{CareerI18n.setLocale(locale);document.getElementById('view-season').classList.add('on');document.getElementById('top-date').textContent=S.date;}""",language)
                for state in ('running','loss','report','paused','break','end','start'):
                    page.evaluate("""async state=>{
                      CareerSeason.reset();
                      window.running=['running','loss','report'].includes(state);
                      S.career.season_mode={phase:state==='end'?'end':state==='start'?'start':'running',can_choose:['end','start'].includes(state),selected:'quick'};
                      S.career.story_timing={open:state==='break'};
                      const host=document.getElementById('view-season');await CareerSeason.refresh(host);
                      CareerI18n.apply(host);
                      if(window.running){CareerSeason.playback(host,true);CareerSeason.status('BO3 · 1 / 3','Test Club 1 : 0 Counter-Strike International',
                        {...reportMatch,series:'1 : 0',map_index:state==='loss'?2:1});
                        if(state==='report'){CareerSeason.showReport(reportMatch);CareerSeason.status('Series stats · 6s');}}
                      else CareerSeason.playback(host,false);
                    }""",state)
                    page.wait_for_timeout(30)
                    result=page.evaluate("""() => {
                      const host=document.querySelector('.quick-dashboard'),rect=host.getBoundingClientRect();
                      const failures=[...host.querySelectorAll('.quick-arena,.quick-footer,.quick-controls,.quick-match,.quick-mode-choice,[data-quick-scorecard],.quick-team-reports,.quick-player-spotlight,.quick-record,.quick-dots')]
                        .filter(e=>e.scrollHeight>e.clientHeight+2||e.scrollWidth>e.clientWidth+2).map(e=>({name:e.className,width:e.clientWidth,scrollWidth:e.scrollWidth,height:e.clientHeight,scrollHeight:e.scrollHeight}));
                      const outside=[...host.querySelectorAll('button')].filter(e=>!e.hidden&&e.getClientRects().length)
                        .filter(e=>{const r=e.getBoundingClientRect();return r.bottom>innerHeight+1||r.right>innerWidth+1||r.top<0;}).map(e=>e.textContent);
                      return {viewport:[innerWidth,innerHeight],bottom:rect.bottom,scroll:document.documentElement.scrollHeight>innerHeight+1,
                        nested_overflow:failures,offscreen_controls:outside,timeline:!!host.querySelector('.season-timeline'),
                        win:!!host.querySelector('.quick-arena.win'),loss:!!host.querySelector('.quick-arena.loss'),
                        report_rows:host.querySelectorAll('.quick-team-report tbody tr').length,player_rows:host.querySelectorAll('.quick-you').length,
                        dots:host.querySelectorAll('.result-dot').length};
                    }""")
                    result.update(language=language,state=state);cases.append(result)
                    if state in ('running','end','report','loss') and width in (1280,853):
                        page.screenshot(path=str(args.output/f'{width}x{height}-{language}-{state}.png'))
                page.close()
        browser.close()
    failed=[c for c in cases if c['scroll'] or c['nested_overflow'] or c['offscreen_controls'] or c['timeline'] or c['bottom']>c['viewport'][1]+1
            or c['dots']!=120 or (c['state']=='loss' and not c['loss'])
            or (c['state'] in ('running','report') and not c['win'])
            or (c['state']=='report' and (c['report_rows']!=10 or c['player_rows']!=1))]
    (args.output/'report.json').write_text(json.dumps(dict(cases=cases,failed=failed),ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(dict(cases=len(cases),failed=failed),ensure_ascii=False,indent=2))
    if failed:raise SystemExit(1)


if __name__=='__main__':main()
