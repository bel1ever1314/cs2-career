/* Render real page modules with inert DOM/commands; no save or game IO. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.join(__dirname,'../cs2career/web/static');
const ui={pages:{},head:t=>`<h2>${t}</h2>`,link:(_k,_id,t)=>t,empty:t=>t};
const S={design_preview:true,career:{ops:{wages:[]},skins:{inventory:[],market:[],weapons:[],cases:[],pending:{name:'Saved drop',rarity:'covert',wear:.1,spot:100,sell:90,weapon:'AK'}},loan:{},pocket:1000}};
const host=()=>({innerHTML:'',querySelectorAll:()=>[]});
const sandbox={CareerUI:ui,S,get:async()=>({}),$:()=>null,PLAY:{},document:{addEventListener:()=>{}},
  esc:String,money:String,financeCard:t=>`<div>${t}</div>`,bindBotSettings:()=>{},bindSkinPref:()=>{},botSettingsCard:()=>'<div>Bot配置</div>',
  rarityRank:()=>0,localStorage:{getItem:()=>null}};
for(const name of ['economy','settings','collection'])vm.runInNewContext(fs.readFileSync(path.join(root,`desk/${name}.js`),'utf8'),sandbox);
(async()=>{
  const economy=host();await ui.pages.locker({},economy,()=>true);
  assert.match(economy.innerHTML,/俱乐部资金/);
  assert.doesNotMatch(economy.innerHTML,/data-open-case|pending-keep|skin-pref|data-skin-detail/);
  const settings=host();await ui.pages.settings({},settings,()=>true);
  assert.match(settings.innerHTML,/id="skin-pref"/);assert.match(settings.innerHTML,/id="p-save"/);
  for(const view of ['inventory','skins','cases']){
    const h=host();await ui.pages[view]({view},h,()=>true);
    assert.equal(h.innerHTML.includes('id="pending-keep"'),view==='cases','case results have one action owner');
    assert.doesNotMatch(h.innerHTML,/collection-nav/,'sidebar is the one collection navigation');
  }
  const app=fs.readFileSync(path.join(root,'app.js'),'utf8');
  const training=app.slice(app.indexOf('async function renderPlay()'),app.indexOf('function startPolling()'));
  assert.doesNotMatch(training,/id="p-save"|id="skin-pref"|botSettingsCard\(cfg\)/);
  assert.match(training,/data-route="settings"/);
  console.log('Desktop ownership: economy, settings, inventory, market and cases passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
