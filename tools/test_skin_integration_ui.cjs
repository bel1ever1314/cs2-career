/* Settings VM fixtures only. No service, save, Steam, CS2 or external network. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const base=path.resolve(__dirname,'../cs2career/web/static/desk');
const crafts=require(path.join(base,'skin-crafts.js'));
const source=fs.readFileSync(path.join(base,'settings.js'),'utf8');
const integration={inspect_enabled:false,inventory_mode:'career',plugin_url:'https://github.com/ianlucas/cs2-css-inventory-simulator/releases',web_url:'https://github.com/ianlucas/cs2-inventory-simulator',web_app_url:'https://inventory.cstrike.app',viewer_url:'https://3d.cstrike.app/view'};
async function fixture(flags={},preview=false){
  const cfg={ready:true,mod_installed:true,levels_ok:true,skin_integration:integration,...flags},nodes=new Map(),posts=[],routes=[];
  const host={html:'',querySelectorAll:()=>[...nodes.values()]};
  const context={S:{design_preview:preview,career:{real_skins:true,steam_id:'76561198000000000',skins:{skin_integration:{inspect_enabled:true},inventory:[{id:'keep-career-item'}],equipped_ct:{ak47:'keep-career-item'}}}},PLAY:{cs2:{}},CareerSkinCrafts:crafts,
    get:async url=>{assert.equal(url,'/api/cs2/status');return cfg;},post:async(url,body)=>{posts.push({url,body:JSON.parse(JSON.stringify(body))});Object.assign(cfg,body);return {ok:true,skin_integration:{...cfg.skin_integration,inspect_enabled:cfg.skin_inspect_enabled===true,inventory_mode:cfg.skins_inventory_mode==='external'?'external':'career'}};},
    esc:value=>String(value??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])),
    $:id=>nodes.get(id),botSettingsCard:()=>'',bindBotSettings:()=>{},bindSkinPref:()=>{},
    CareerUI:{pages:{},head:()=>'',go:(...args)=>routes.push(args),paint:(target,html)=>{
      target.html=html;nodes.clear();
      for(const match of html.matchAll(/<(input|button|select)\b([^>]*\bid="([^"]+)"[^>]*)>/g)){
        const attrs=match[2],id=match[3];nodes.set(id,{disabled:/\bdisabled\b/.test(attrs),checked:/\bchecked\b/.test(attrs),value:attrs.match(/\bvalue="([^"]*)"/)?.[1]||'',isConnected:true});
      }
      for(const match of html.matchAll(/<select\b[^>]*\bid="([^"]+)"[^>]*>([\s\S]*?)<\/select>/g)){
        const options=[...match[2].matchAll(/<option\b([^>]*)>/g)],option=options.find(row=>/\bselected\b/.test(row[1]))||options[0];
        nodes.get(match[1]).value=option?.[1].match(/\bvalue="([^"]*)"/)?.[1]||'';
      }
    }}
  };
  vm.runInNewContext(source,context,{filename:'settings.js'});
  await context.CareerUI.pages.settings({},host,()=>true);
  return {cfg,nodes,posts,routes,host,context};
}
async function main(){
  let f=await fixture();
  assert.equal(f.nodes.get('skin-inventory-mode').value,'career');assert.equal(f.nodes.get('skin-inspect-enabled').checked,false,'absent persisted opt-in defaults off');
  assert.equal(f.posts.length,0,'rendering settings never enables service or mutates configuration');
  assert.equal((f.host.html.match(/target="_blank" rel="noopener noreferrer"/g)||[]).length,4);assert.match(f.host.html,/未随生涯打包/);
  assert.equal(f.nodes.get('skin-real').disabled,false);
  assert.equal(f.context.S.career.skins.skin_integration.inspect_enabled,false,'status refresh reconciles display metadata without a whole-state read');
  const toggle=f.nodes.get('skin-inspect-enabled');toggle.checked=true;await toggle.onchange({target:toggle});
  assert.deepEqual(f.posts,[{url:'/api/cs2/settings',body:{skin_inspect_enabled:true}}]);assert.equal(f.context.PLAY.cs2,null);assert.equal(f.routes[0][0],'settings');
  assert.equal(f.context.S.career.skins.skin_integration.inspect_enabled,true,'save response immediately updates opt-in display metadata');
  const mode=f.nodes.get('skin-inventory-mode');mode.value='external';await mode.onchange({target:mode});
  assert.deepEqual(f.posts[1],{url:'/api/cs2/settings',body:{skins_inventory_mode:'external'}});
  assert.equal(f.context.S.career.skins.skin_integration.inventory_mode,'external');assert.deepEqual(f.context.S.career.skins.inventory,[{id:'keep-career-item'}]);assert.deepEqual(f.context.S.career.skins.equipped_ct,{ak47:'keep-career-item'});
  f=await fixture({skins_inventory_mode:'external',skin_inspect_enabled:true});
  assert.equal(f.nodes.get('skin-inventory-mode').value,'external');assert.equal(f.nodes.get('skin-inspect-enabled').checked,true);
  for(const id of ['skin-real','skin-sid','skin-pref','p-skins','p-skins-install','p-gamedata'])assert.equal(f.nodes.get(id).disabled,true,'career skin controls are inactive in external mode');
  assert.match(f.host.html,/生涯不会写入或覆盖外部库存配置/);assert.equal(f.context.S.career.real_skins,true,'existing career preference retained');
  f=await fixture({cs2_live:true});assert.equal(f.nodes.get('skin-inventory-mode').disabled,true);
  await f.nodes.get('skin-inventory-mode').onchange({target:{value:'external'}});assert.equal(f.posts.length,0,'live-game guard does not request an inventory-mode change');
  f=await fixture({},true);for(const node of f.nodes.values())assert.equal(node.disabled,true,'isolated preview remains read-only');
  const phrases=require(path.join(base,'locales/en.js')).phrases;
  for(const key of ['配装来源','外部插件配装','外部饰品工具（可选）','在线 3D 设置','换肤插件下载','此处只编辑生涯收藏；外部 Inventory Simulator 配装由你自行管理。'])assert.ok(phrases[key]);
  console.log('PASS: settings default-off opt-in, global persistence payloads, game-closed inventory mode, external ownership, safe source/download links, preview gates and translations.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
