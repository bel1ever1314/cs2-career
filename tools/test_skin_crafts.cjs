/* Pure UI fixtures only. No career service, save, CS2 or Steam access.
 * node tools/test_skin_crafts.cjs [--browser]
 * Optional browser dependencies: CAREER_PLAYWRIGHT=<installed package path>.
 * Set CAREER_BROWSER_TEMP to a D:/E: temporary directory for Chromium caches. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const base=path.resolve(__dirname,'../cs2career/web/static');
const crafts=require(path.join(base,'desk/skin-crafts.js'));
const model={x_min:-.02,x_max:.05,y_min:-.04,y_max:.04,schema_count:4,rotation_min:-180,rotation_max:180};
const item={id:'inv.1',skin_id:'ak-redline',name:'AK-47 | Redline',weapon:'AK-47',slot:'ak47',def:7,rarity:'classified',wear:.12345,seed:317,stattrak:0,nametag:'My <AK>',spot:100,sell:90,sides:['t'],stickers:[{def:99,slot:4,wear:.02,rotation:12,x:.001,y:-.002,schema:0}]};
const shop={stickers:[{def:99,name:'队伍 | 测试',name_en:'Team | Test'},{def:100,name:'安全 <贴纸>',name_en:'Safe <sticker>'}],sticker_models:{7:model},inventory:[item],market:[{...item,id:'ak-redline',wear:null}],weapons:['AK-47'],cases:[],equipped_ct:{},equipped_t:{},loadout_packs:[
  {id:'donk',player:'donk',description:'公开配装模板',source_date:'2026-09-30',source_url:'https://prosettings.net/players/donk/',count:1,quality:'public_template',items:[{name:'AK-47 | Redline',wear:.15}],imported:false},
  {id:'zywoo',player:'ZywOo',source_date:'2026-09-30',count:1,items:[{name:'AWP | Test'}],imported:false},
  {id:'monesy',player:'m0NESY',count:0,items:[],imported:false,source_url:'javascript:alert(1)'},
  {id:'niko',player:'NiKo',count:1,items:[{name:'<script>bad</script>'}],imported:true}
]};
function pure(){
  const rows=crafts.rowsFor(item);assert.equal(rows.length,5);assert.equal(rows[4].slot,4);assert.equal(rows[4].schema,0);
  const body=crafts.makeCraftPayload(item.id,rows,model);assert.deepEqual(Object.keys(body),['id','stickers']);assert.equal(body.stickers[0].slot,4);assert.equal(body.stickers[0].schema,0);
  assert.ok(!Object.hasOwn(body,'seed')&&!Object.hasOwn(body,'wear')&&!Object.hasOwn(body,'stattrak')&&!Object.hasOwn(body,'nametag'));
  rows[0]={...rows[0],def:100,wear:0,rotation:-180,x:0,y:0,schema:0};assert.equal(crafts.makeCraftPayload(item.id,rows,model).stickers.length,2,'same anchor may be reused in distinct stack slots');
  rows[4].def=0;assert.deepEqual(crafts.makeCraftPayload(item.id,rows,model).stickers.map(s=>s.slot),[0]);
  const newRows=crafts.rowsFor({stickers:[]});newRows[0].def=99;assert.ok(!Object.hasOwn(crafts.makeCraftPayload(item.id,newRows).stickers[0],'schema'),'new schema is omitted for backend automatic assignment');
  assert.ok(!Object.hasOwn(crafts.makeCraftPayload(item.id,newRows).stickers[0],'x'),'unknown model must not manufacture offset');
  const original=crafts.makeCraftPayload(item.id,crafts.rowsFor(item));assert.equal(original.stickers[0].x,.001,'existing offsets retained without model');
  for(const [key,value] of [['wear',1.1],['rotation',181],['x',.051],['y',-.041],['schema',4],['def',99.1]]){const bad=crafts.rowsFor(item);bad[4][key]=value;assert.throws(()=>crafts.makeCraftPayload(item.id,bad,model),key);}
  assert.throws(()=>crafts.makeCraftPayload(item.id,[]));
  assert.equal(crafts.offsetModel(item,shop),model);assert.equal(crafts.offsetModel({...item,def:999},shop),null);
  const html=crafts.details(item,shop);assert.equal((html.match(/data-sticker-slot=/g)||[]).length,5);assert.match(html,/My &lt;AK&gt;/);assert.match(html,/StatTrak™<\/dt><dd>0<\/dd>/);assert.match(html,/0\.12345/);assert.match(html,/step="0\.0001"/);assert.match(html,/data-sticker-field="schema"/);
  const unknown=crafts.details({...item,def:999},shop);assert.doesNotMatch(unknown,/data-sticker-field="x"/);assert.match(unknown,/保留原贴纸偏移/);
  const knife=crafts.details({...item,slot:'knife'},shop);assert.match(knife,/此类饰品不支持贴纸/);assert.match(knife,/type="submit" disabled/);
  assert.match(crafts.details({...item,bound:true},shop),/免费配装，不可出售/);
  assert.equal(crafts.packState(shop.loadout_packs[0]).disabled,false);assert.equal(crafts.packState(shop.loadout_packs[2]).available,false);assert.equal(crafts.packState(shop.loadout_packs[3]).disabled,true);
  const packs=crafts.packs(shop);assert.equal((packs.match(/data-loadout-import=/g)||[]).length,4);assert.match(packs,/data-loadout-import="monesy" disabled/);assert.match(packs,/data-loadout-import="niko" disabled/);assert.match(packs,/导入模拟外观/);assert.doesNotMatch(packs,/href="javascript/);assert.doesNotMatch(packs,/<script>/);assert.match(packs,/&lt;script&gt;bad/);
  const actual=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../cs2career/data/public_pro_loadouts.json'),'utf8'));
  const realPacks=crafts.packs({loadout_packs:actual.packs});assert.match(realPacks,/m0NESY/);assert.match(realPacks,/ZywOo/);assert.match(realPacks,/NiKo/);assert.match(realPacks,/核对日期/);
  assert.match(crafts.packs({loadout_packs:[{id:'template',player:'Test',items:[{name:'M4 | Test',defaults:{wear:.04,seed:1}}]}]}),/默认磨损 0\.04000/);
  assert.equal(crafts.safeSource('javascript:alert(1)'), '');assert.equal(crafts.safeSource('https://user:pass@example.com/'), '');assert.equal(crafts.safeSource('http://example.com/'), '');assert.ok(crafts.safeSource('https://prosettings.net/players/donk/'));
  const links=crafts.integrationLinks({plugin_url:'https://github.com/ianlucas/cs2-css-inventory-simulator/releases',web_url:'https://github.com/ianlucas/cs2-inventory-simulator',web_app_url:'https://inventory.cstrike.app',viewer_url:'https://3d.cstrike.app/view'},{viewer:true});
  assert.equal((links.match(/target="_blank" rel="noopener noreferrer"/g)||[]).length,4);assert.match(links,/换肤插件下载/);assert.match(links,/外部项目源码/);
  assert.equal(crafts.integrationLinks({plugin_url:'javascript:alert(1)',web_url:'https://user:pass@example.com',web_app_url:'http://example.com',viewer_url:'https://example.com'}),'');
  require(path.join(base,'desk/skin-inspect.js'));
  const disabled=crafts.details(item,shop);assert.match(disabled,/data-skin-inspect-settings/);assert.doesNotMatch(disabled,/data-skin-inspect>/);assert.match(disabled,/data-skin-craft-form/);
  assert.match(crafts.details(item,{...shop,skin_integration:{inspect_enabled:true}}),/data-skin-inspect>/);
  assert.match(crafts.details(item,{...shop,skin_integration:{inventory_mode:'external'}}),/此处只编辑生涯收藏/);
  const locale=require(path.join(base,'desk/locales/en.js'));assert.equal(locale.phrases['免费配装，不可出售'],'Free loadout item · Cannot be sold');assert.equal(locale.phrases['保存贴纸'],'Save stickers');
  console.log('PASS: skin crafts pure payload, 5 stack slots/4 anchors, model ranges, unedited metadata, escaping, free/imported/empty pack gates and translations.');
}
async function browser(){
  if(process.env.CAREER_BROWSER_TEMP){process.env.TEMP=process.env.CAREER_BROWSER_TEMP;process.env.TMP=process.env.CAREER_BROWSER_TEMP;}
  const {chromium}=require(process.env.CAREER_PLAYWRIGHT||'playwright');
  const browser=await chromium.launch({channel:'chrome',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1280,height:720}});
    await page.route('http://skin-crafts.test/**',route=>route.fulfill({contentType:'text/html',body:'<main id="view-inventory"></main><main id="view-skins"></main><main id="view-cases"></main>'}));
    await page.goto('http://skin-crafts.test/');
    for(const file of ['style.css','desk.css','theme.css','desk/skin-crafts.css'])await page.addStyleTag({content:fs.readFileSync(path.join(base,file),'utf8')});
    await page.addScriptTag({content:fs.readFileSync(path.join(base,'desk/dom.js'),'utf8')});
    await page.addScriptTag({content:`window.S=${JSON.stringify({career:{pocket:10,skins:shop}})};window.calls=[];window.failCraft=false;window.esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));window.money=n=>'$'+(n||0);window.$=id=>document.getElementById(id);window.rarityRank=()=>0;window.toast=()=>{};window.get=async()=>({items:{}});window.CareerUI={pages:{},head:(t,h)=>'<h2>'+esc(t)+'</h2><p>'+esc(h)+'</p>',empty:t=>'<p>'+esc(t)+'</p>',paint:CareerDOM.paint,go:()=>{}};window.render=()=>{window.repaint=CareerUI.pages.inventory({view:'inventory'},document.querySelector('#view-inventory'),()=>true);};window.post=async(path,body)=>{calls.push({path,body:structuredClone(body)});await new Promise(r=>setTimeout(r,35));if(path.endsWith('/craft')){if(failCraft)return{ok:false,msg:'fixture save failure'};S.career.skins.inventory.find(i=>i.id===body.id).stickers=structuredClone(body.stickers);}if(path.endsWith('/loadout')){const pack=S.career.skins.loadout_packs.find(p=>p.id===body.id);pack.imported=true;S.career.skins.inventory.push({...S.career.skins.inventory[0],id:'inv.free',bound:true});}render();await repaint;return{ok:true,state:S};};`});
    for(const file of ['desk/i18n.js','desk/locales/en.js','desk/skin-crafts.js','desk/collection.js'])await page.addScriptTag({content:fs.readFileSync(path.join(base,file),'utf8')});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.evaluate(async()=>{render();await repaint;});
    assert.equal(await page.locator('[data-loadout-import]').count(),4);assert.equal(await page.locator('[data-loadout-import="monesy"]').isDisabled(),true);assert.equal(await page.locator('[data-loadout-import="niko"]').isDisabled(),true);
    await page.locator('[data-skin-detail="inv.1"]').click();await page.locator('.skin-sticker-editor>summary').click();
    assert.equal(await page.locator('[data-sticker-slot]').count(),5);assert.equal(await page.locator('[data-sticker-slot="4"] [data-sticker-field="schema"]').inputValue(),'0');
    await page.locator('[data-sticker-slot="0"] [data-sticker-field="def"]').selectOption('100');
    await page.locator('[data-sticker-slot="0"] [data-sticker-field="rotation"]').fill('45.5');
    await page.locator('[data-sticker-slot="0"] [data-sticker-field="wear"]').fill('0.0335');
    await page.locator('[data-sticker-slot="0"] [data-sticker-field="x"]').fill('0.00015');
    await page.locator('[data-sticker-slot="4"] [data-sticker-remove]').click();
    await page.locator('[data-skin-craft-form] [type="submit"]').click();
    await page.waitForFunction(()=>calls.length===1&&document.querySelector('.skin-sticker-list')?.textContent.includes('安全'));
    let saved=await page.evaluate(()=>({call:calls[0],item:S.career.skins.inventory[0]}));assert.equal(saved.call.path,'/api/skins/craft');assert.equal(saved.call.body.stickers.length,1);assert.equal(saved.call.body.stickers[0].slot,0);assert.equal(saved.call.body.stickers[0].rotation,45.5);assert.equal(saved.call.body.stickers[0].wear,.0335);assert.equal(saved.call.body.stickers[0].x,.00015);assert.equal(saved.item.seed,317);assert.equal(saved.item.stattrak,0);assert.equal(saved.item.nametag,'My <AK>');assert.equal(saved.item.wear,.12345);
    await page.locator('.skin-sticker-editor>summary').click();await page.evaluate(()=>failCraft=true);await page.locator('[data-skin-craft-form] [type="submit"]').click();await page.waitForFunction(()=>document.querySelector('[data-craft-status]')?.textContent.includes('fixture save failure'));assert.equal(await page.locator('[data-skin-craft-form] [type="submit"]').isDisabled(),false);
    await page.locator('.close-detail').click();await page.locator('[data-loadout-import="donk"]').click();await page.waitForFunction(()=>S.career.skins.loadout_packs[0].imported);assert.equal(await page.locator('[data-loadout-import="donk"]').isDisabled(),true);assert.equal(await page.locator('[data-loadout-import="zywoo"]').isDisabled(),false);assert.equal(await page.evaluate(()=>S.career.pocket),10);
    await page.locator('[data-skin-detail="inv.free"]').click();assert.equal(await page.locator('#collection-sell').isDisabled(),true);assert.match(await page.locator('#collection-sell').innerText(),/不可出售/);
    await page.locator('.close-detail').click();await page.evaluate(async()=>{await CareerUI.pages.cases({view:'cases'},document.querySelector('#view-cases'),()=>true);});assert.equal(await page.locator('#view-cases [data-loadout-import]').count(),0,'cases retain their own actions');
    await page.evaluate(async()=>{CareerI18n.setLocale('en');render();await repaint;});assert.match(await page.locator('.skin-loadout-heading h3').innerText(),/Player loadouts/);await page.locator('[data-skin-detail="inv.1"]').click();assert.match(await page.locator('.skin-sticker-editor>summary').innerText(),/Edit stickers/);assert.match(await page.locator('.skin-sticker-list').innerText(),/Safe/);
    await page.setViewportSize({width:736,height:600});assert.equal(await page.locator('.collection-dialog').evaluate(el=>el.getBoundingClientRect().right<=innerWidth),true);await page.locator('.skin-sticker-editor>summary').click();assert.equal(await page.locator('[data-skin-craft-form]').evaluate(el=>el.scrollWidth<=el.clientWidth+1),true);
    assert.deepEqual(errors,[]);console.log('PASS: isolated Chromium real collection click flow, POST metadata, retry, bound sell, imported gating, case ownership, English and 736px form containment.');
  }finally{await browser.close();}
}
pure();if(process.argv.includes('--browser'))browser().catch(error=>{console.error(error);process.exitCode=1;});
