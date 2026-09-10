/* Render the real setup/profile modules; provenance is inert text, not HTML. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const controls={};
const info={label:'历史资料待补 · 估算占位',note:'slot 是虚构身份 <script>alert(1)</script>',sources:[{title:'公告',url:'https://example.test/<img>'}]};
const ui={pages:{},head:()=>'',link:()=>'',tabs:()=>'',num:String,empty:String};
const ctx={CareerUI:ui,esc,ROLE:{},REGION:{},get:async()=>({name:'PARIVISION 2024 slot2',historical:true,summary:{},recent:[],total:0,data_provenance:info}),
  $:id=>controls[id]||={style:{}},crest:()=>'',badge:()=>'',honoursMedals:()=>'',honoursLists:()=>'',
  DRAFT:{era:'2024',mode:'join',role:'rifle'},SETUP:{era:'2024',teams:[{id:'parivision',name:'PARIVISION',rank:41,players:[],data_provenance:info}],coverage:{verified_rosters:1,teams:49,placeholder_players:130}},
  S:{career:{eras:{'2024':{title:'魔童降世',blurb:'开局名单'}}}},
  document:{querySelectorAll:()=>[]},money:String,roleBadge:String};
vm.createContext(ctx);
for(const name of ['profiles','setup'])vm.runInContext(fs.readFileSync(`cs2career/web/static/desk/${name}.js`,'utf8'),ctx);
(async()=>{
  const host={innerHTML:''};
  await ui.pages.profile({kind:'player',key:'old'},host,()=>true);
  assert.match(host.innerHTML,/估算占位/);
  assert.match(host.innerHTML,/&lt;script&gt;/);
  assert.doesNotMatch(host.innerHTML,/<script>|<img>|href="javascript:/);
  ctx.renderSetup();
  assert.match(controls['view-setup'].innerHTML,/名单核验 1\/49/);
  assert.match(controls['view-setup'].innerHTML,/占位选手 130 人/);
  assert.match(controls['view-setup'].innerHTML,/估算占位/);
  assert.doesNotMatch(controls['view-setup'].innerHTML,/<script>/);
  console.log('Era UI: setup coverage, saved-slot notice, escaped provenance passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
