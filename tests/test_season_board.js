/* Pure presentation checks. No saves or HTTP endpoints are accessed. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const code=fs.readFileSync(path.join(__dirname,'..','cs2career','web','static','desk','season.js'),'utf8');
const ctx={S:{year:2026,date:'2026-06-21',career:{exists:true,team_name:'A',registered:['future'],assist:{quick_mode:true},season_mode:{phase:'running',can_choose:false}},events:[]},CareerUI:{pages:{},head:(title,hint)=>`<h2>${title}</h2><span>${hint}</span>`},CareerAssist:{isActive:()=>false},esc:s=>String(s??'').replace(/[<>&"]/g,x=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[x]))};
ctx.window=ctx;vm.runInNewContext(code,ctx);const api=ctx.CareerSeason;
assert.equal(api.modeCard(),'','Running seasons must not repeatedly offer switching');
ctx.S.career.season_mode={phase:'start',can_choose:true,selected:'normal'};
assert.ok(api.modeCard().includes('data-season-mode="quick"'));
ctx.S.career.season_mode.choice_required=false;
assert.equal(api.modeCard(),'','Confirming a mode must not immediately ask the same question again');
ctx.S.career.season_mode={phase:'end',can_choose:true,selected:'quick'};
assert.ok(api.modeCard().includes('下一季使用普通模式'));
ctx.S.career.season_mode={phase:'running',can_choose:false,selected:'quick'};
const board={year:2026,date:'2026-06-21',events:[
  {id:'future',name:'Future Event',dates:['2026-11-01','2026-11-20'],class:'major',status:'upcoming',participation:'entered',own_matches:[]},
  {id:'past',name:'Past Event',dates:['2026-01-01'],class:'t2',status:'done',participation:'skipped',champion:'<script>x</script>'},
  {id:'current',name:'Current Event',dates:['2026-06-01','2026-06-28'],class:'major',status:'live',participation:'entered',own_matches:[{id:'m1',team_a:'A',team_b:'B',series:'2 : 1',played:true,stage:'QF'}]},
]};
const quick=api.html(board);
assert.ok(quick.includes('quick-dashboard')&&!quick.includes('season-timeline'));
assert.ok(!quick.includes('data-open-event=')&&!quick.includes('data-open-match='),'Quick playback never requires browsing event cards');
assert.equal((quick.match(/class="quick-mini/g)||[]).length,3,'The recap is bounded, regardless of calendar length');
assert.ok(quick.includes('Current Event')&&quick.includes('Future Event'));
assert.equal(api.quickFocus(board).event.id,'current');
ctx.S.career.assist.quick_mode=false;
const html=api.html(board);
assert.ok(html.indexOf('Past Event')<html.indexOf('Current Event')&&html.indexOf('Current Event')<html.indexOf('Future Event'),'Sort the full calendar chronologically');
for(const label of ['本队未参加','本队参赛','进行中','未开始','已结束','2 : 1'])assert.ok(html.includes(label),label);
assert.equal((html.match(/data-open-match=/g)||[]).length,1,'Only saved/generated matches may appear; never fabricate future pairings');
assert.ok(!html.includes('<script>')&&html.includes('&lt;script&gt;'),'All names remain escaped data');
ctx.S.career.assist.quick_mode=true;
assert.ok(api.html({...board,events:[...board.events,...Array.from({length:100},(_,i)=>({...board.events[0],id:'extra'+i,name:'Extra'+i}))]}).length<8000,'Adding a hundred events cannot turn quick mode into a long page');
ctx.S.events=board.events.map(x=>({...x,field:x.id==='current'?['A']:[]}));
const fallback=api.fallback();
assert.equal(fallback.events.find(x=>x.id==='future').participation,'entered');
assert.equal(fallback.events.find(x=>x.id==='past').participation,'skipped');
// Score changes touch text nodes only; asynchronous board reads must not
// replace controls or reveal the saved final score during playback.
let paints=0,scoreNode=null;const skip={hidden:true},statusNode={textContent:'',after:node=>{scoreNode=node;}};
const host={querySelector:key=>key==='[data-season-status]'?statusNode:key==='.season-latest-score'?scoreNode:key==='[data-skip-quick-score]'?skip:null,querySelectorAll:()=>[]};
ctx.document={getElementById:()=>host,createElement:()=>({textContent:'',className:''})};
ctx.CareerUI.paint=()=>{paints++;};
api.playback(host,true);api.status('BO3 · 1 / 3','A 1 : 0 B');api.paint(host);
assert.equal(skip.hidden,false);assert.equal(paints,0);assert.equal(scoreNode.textContent,'A 1 : 0 B');
const stable=scoreNode;api.status('BO3 · 2 / 3','A 1 : 1 B');assert.equal(scoreNode,stable);
api.playback(host,false);api.paint(host);assert.equal(skip.hidden,true);assert.equal(paints,1);
api.status('BO3','A 1 : 0 B',{id:'m1',event_id:'current',team_a:'A',team_b:'B',series:'1 : 0',best_of:3});
assert.equal(api.quickFocus(board).match.series,'1 : 0','Playback uses its current score, not the saved final score');
assert.ok(api.html(board).includes('1 : 0'));
api.status('Next stage','',null);assert.equal(api.quickFocus(board).match.series,'2 : 1');
console.log('PASS: season mode boundaries, complete chronological board, participant distinctions, saved match links, escaping, read-only fallback.');
