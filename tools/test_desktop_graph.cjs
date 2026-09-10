// Exercise the actual page renderer without a browser or player save.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const matches = ['q1','q2','q3','q4','s1','s2'].map((id,i) => ({
  id, stage:i<4?'QF':'SF', team_a:'A'+i, team_b:'B'+i, played:true, series:'2-0', date:'2026-02-01'
}));
const ev = {name:'Cross-seeded test',matches,links:[
  {source:'q3',target:'s1'}, {source:'q4',target:'s1'},
  {source:'q1',target:'s2'}, {source:'q2',target:'s2'}
]};
const ui = {pages:{},head:()=>'',tabs:()=>'',link:()=>''};
const sandbox = {CareerUI:ui,get:async()=>ev,FORMAT:{},STATUS:{},money:String,esc:String,
  myTeamName:()=>'',crest:()=>'',S:{},DETAIL:null};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../cs2career/web/static/desk/competitions.js'),'utf8'),sandbox);
(async()=>{
  const host={innerHTML:'',querySelector:()=>null};
  await ui.pages.event({key:'test'},host,()=>true);
  const positions=[...host.innerHTML.matchAll(/class="graph-position" style="left:(\d+)px;top:([\d.]+)px"/g)]
    .map(m=>({x:Number(m[1]),y:Number(m[2])}));
  assert.equal(positions.length,6);
  assert.ok(positions[5].y-positions[4].y>=148,'cross-seeded semifinal cards overlap');
  console.log('Desktop graph: cross-seeded layout passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
