/* Render real history pages with recorded API shapes and inert controls. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const ui={pages:{},head:(t,s)=>`${t} ${s}`,link:(_k,id,t)=>`${id}:${t}`,tabs:()=>'',empty:t=>`<p>${t}</p>`,num:n=>n==null?'—':String(n)};
const controls={};let response;
const ctx={CareerUI:ui,get:async url=>url==='/api/events'?[{id:'2026::cup',name:'Old Cup',dates:['2026-02-01'],status:'done'}]:response,
  $:id=>controls[id]||= {},esc:String,ROLE:{},REGION:{},FORMAT:{},STATUS:{},S:{career:{}},money:String,
  crest:()=>'',badge:()=>'',mapName:String,axisPanel:()=>{throw Error('must not fabricate historical attributes')},
  honoursMedals:()=>'',honoursLists:()=>'',myTeamName:()=>''};
for(const file of ['profiles','competitions'])vm.runInNewContext(fs.readFileSync(path.join(__dirname,`../cs2career/web/static/desk/${file}.js`),'utf8'),ctx);
(async()=>{
  response={historical:true,name:'Old Player',last_team:'Old Team',form_delta:null,summary:{maps:0},recent:[],total:0};
  const host={innerHTML:'',querySelector:()=>null};
  await ui.pages.profile({kind:'player',key:'old'},host,()=>true);
  assert.match(host.innerHTML,/历史选手/);assert.match(host.innerHTML,/不补造数值/);assert.doesNotMatch(host.innerHTML,/自由选手/);
  response={id:'2026::cup',name:'Old Cup',dates:['2026-02-01'],matches:[],awards:{mvp:{player:'Old Player'}}};
  await ui.pages.event({key:'2026::cup',tab:'awards'},host,()=>true);
  assert.match(host.innerHTML,/event-directory/);assert.match(host.innerHTML,/value="2026::cup" selected/);
  assert.match(host.innerHTML,/Old Player/);
  console.log('History UI: retired player, unknown attributes, year-qualified directory and saved MVP passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
