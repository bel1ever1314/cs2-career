/* Run the actual page renderers: no browser, game launch or player data. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes={},posts=[];
const env=vm.createContext({CareerUI:{pages:{},head:()=>'',empty:()=>'',go:()=>{}},S:{career:{}},PLAY:{},
  get:async()=>({root:'isolated',packs:[],ready:0,match_chat:'custom'}),
  post:async(url,data)=>{posts.push([url,data]);return {};},
  esc:s=>String(s??'').replace(/[<>&"]/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;'}[c])),
  $:id=>nodes[id]??=( {value:'',disabled:false} ),botSettingsCard:()=>'',bindBotSettings:()=>{},bindSkinPref:()=>{}});
for(const page of ['settings','workshop'])vm.runInContext(fs.readFileSync(`cs2career/web/static/desk/${page}.js`,'utf8'),env);
(async()=>{
  const host={innerHTML:''};
  await env.CareerUI.pages.settings({},host,()=>true);
  assert.match(host.innerHTML,/value="custom" selected/);
  assert.match(host.innerHTML,/CS2 原生聊天框/);
  assert.match(host.innerHTML,/每回合最多教练一句、选手一句/);
  await nodes['match-chat'].onchange({target:{value:'off'}});
  assert.equal(posts[0][0],'/api/cs2/settings');assert.equal(posts[0][1].match_chat,'off');
  await env.CareerUI.pages.workshop({},host,()=>true);
  assert.match(host.innerHTML,/incidents/);assert.match(host.innerHTML,/events 是赛事日历/);
  assert.match(host.innerHTML,/教练合同数据库/);
  assert.match(host.innerHTML,/scenes/);assert.match(host.innerHTML,/sequence/);
  console.log('Content UI: chat preference persistence, native-chat scope and incident workshop explanations passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
