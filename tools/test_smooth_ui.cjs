// Stable score DOM and async refresh checks against the actual UI modules.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const read=p=>fs.readFileSync('cs2career/web/static/'+p,'utf8');
const ev={matches:[
 {id:'m1',team_a:'Mine',team_b:'Other',stage:'SW1',played:false,best_of:3},
 {id:'unrelated',team_a:'Other',team_b:'Third',stage:'SW2'},
 {id:'m2',team_a:'Fourth',team_b:'Mine',stage:'SW2',played:false,best_of:3}
],links:[{source:'m1',target:'m2',team:'Mine',outcome:'winner'},
 {source:'m1',target:'unrelated',team:'Other',outcome:'loser'}]};
let rebuilds=0,nodes=[],snapshot={zoom:.8,left:70,top:20},restored;
const host={querySelectorAll:()=>nodes,querySelector:()=>null,
 set innerHTML(value){rebuilds++;nodes=[];}};
const sandbox={window:{},CareerUI:{paint:(host,html)=>host.innerHTML=html,drawTournamentGraph:ev=>ev,
 bindTournamentGraph:(_host,saved)=>{restored=saved;nodes=ev.matches.filter(m=>m.team_a==='Mine'||m.team_b==='Mine').map(m=>{
   const score={textContent:'BO3'},marks=[{textContent:''},{textContent:''}];
   return {dataset:{node:m.id},score,querySelector:()=>score,querySelectorAll:()=>marks.map(mark=>({classList:{toggle(){}},querySelector:selector=>{assert.equal(selector,':scope > span:last-child','must not overwrite a fallback crest');return mark;}}))};
 });return {snapshot:()=>snapshot};}}};
vm.runInNewContext(read('desk/assistance.js'),sandbox);
const api=sandbox.window.CareerAssist,path=api.teamPath(ev,'Mine');
assert.deepEqual(Array.from(path.matches,m=>m.id),['m1','m2']);assert.equal(path.links.length,1);
assert.equal(ev.matches.length,3,'filter must not mutate saved event');
const update=api.pathView(host,'Mine');update(ev,'');const first=nodes[0];
ev.matches[0].played=true;ev.matches[0].series='1 : 0';update(ev,'');
assert.equal(rebuilds,1);assert.equal(nodes[0],first);assert.equal(first.score.textContent,'1 : 0');
ev.matches[0].series='2 : 0';ev.matches[0].winner='Mine';update(ev,'');
assert.equal(rebuilds,1);assert.equal(first.score.textContent,'2 : 0');
ev.matches[1].series='2-1';update(ev,'');assert.equal(rebuilds,1,'unrelated match must not refresh own path');
ev.matches.push({id:'m3',team_a:'Mine',team_b:'New',stage:'SW3',played:false,best_of:1});update(ev,'');
assert.equal(rebuilds,2);assert.equal(restored,snapshot,'new round must retain graph camera');

// Keep the painted page while the next read is unresolved, and do not restore
// an old scroll offset on same-route polling refreshes.
let resolvePage,pagesWritten=0;
const page={dataset:{},inert:false,html:'',get innerHTML(){return this.html},set innerHTML(v){pagesWritten++;this.html=v;}};
const ids={'view-event':page,'route-back':{},'route-forward':{},breadcrumbs:{}};
const nav={window:{scrollY:120,scrollTo(){}},VIEW:'event',FOCUS:'cup',S:{design_preview:false},
 document:{body:{classList:{toggle(){}}},addEventListener(){},querySelectorAll:()=>[]},
 $:id=>ids[id],esc:String,toast(){},queueMicrotask,requestAnimationFrame:fn=>fn(),Promise};
vm.runInNewContext(read('desk/navigation.js'),nav);
nav.window.CareerUI.pages.event=()=>new Promise(resolve=>{resolvePage=()=>{page.innerHTML='finished content';resolve();};});
(async()=>{
 nav.window.CareerUI.render();assert.match(page.innerHTML,/正在读取/);resolvePage();await new Promise(setImmediate);
 const before=pagesWritten;nav.window.CareerUI.render();assert.equal(pagesWritten,before);assert.equal(page.innerHTML,'finished content');
 resolvePage();await new Promise(setImmediate);assert.equal(page.inert,false);
 console.log('Smooth UI: own-team path only, stable score nodes, saved camera, no repeated loading blank and background render suppression passed');
})().catch(e=>{console.error(e);process.exitCode=1});
