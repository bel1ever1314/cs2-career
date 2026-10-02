/* Pure protocol fixtures and optional mocked-iframe Chromium UI regression.
 * This does not prove the hosted model's visual quality or offline availability.
 * node tools/test_skin_inspect.cjs [--browser]
 * CAREER_PLAYWRIGHT=<existing package>; CAREER_BROWSER_TEMP=<D/E temp directory>.
 * No CS2, formal save, Steam login, real service or new dependency is used. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const base=path.resolve(__dirname,'../cs2career/web/static'),inspect=require(path.join(base,'desk/skin-inspect.js'));
const model={x_min:-.02,x_max:.05,y_min:-.04,y_max:.04,schema_count:4,rotation_min:-180,rotation_max:180};
const item={id:'inv.private',name:'AK-47 | 测试',name_en:'AK-47 | Test',def:7,paint:282,slot:'ak47',seed:317,wear:.12345,stattrak:0,nametag:'Private name',account:'not-for-viewer',stickers:[{def:99,slot:4,wear:.02,rotation:12,x:.001,y:-.001,schema:0}]};
const shop={skin_integration:{inspect_enabled:true,inventory_mode:'career',web_url:'https://github.com/ianlucas/cs2-inventory-simulator',web_app_url:'https://inventory.cstrike.app'},stickers:[{def:99,name:'测试贴纸',name_en:'Test sticker'},{def:100,name:'零号检视贴纸',name_en:'Viewer zero'}],inspect_catalog:{embed_url:inspect.ORIGIN+'/view',items:{'7:282':222,'507:38':0},stickers:{99:1000,100:0},models:{222:model},images:{}}};
const state=(p,stickers=p.appearance.stickers)=>({item:{...p.appearance,stickers},schemaCount:p.model?.schema_count??0,activeSticker:null});
function pure(){
  assert.equal(inspect.enabled({}),false);assert.equal(inspect.enabled({skin_integration:{inspect_enabled:'true'}}),false);assert.equal(inspect.enabled(shop),true);
  const entry={textContent:''},owner={querySelector:()=>entry};
  assert.equal(inspect.open(owner,item,{}),null,'disabled viewer never reaches document/iframe creation');assert.match(entry.textContent,/默认关闭/);
  const p=inspect.prepare(item,shop),src=new URL(inspect.buildSrc(p.appearance,shop.inspect_catalog));
  assert.equal(src.origin,inspect.ORIGIN);assert.equal(src.pathname,'/view');assert.equal(src.searchParams.get('halfRotation'),'1');
  const sent=JSON.parse(src.searchParams.get('item'));assert.deepEqual(Object.keys(sent).sort(),['id','seed','statTrak','stickers','wear']);assert.equal(sent.id,222);assert.equal(sent.statTrak,0);
  assert.doesNotMatch(src.href,/inv.private|Private|account|not-for-viewer|nameTag|nametag|steam|token/);
  assert.equal(sent.stickers[4].id,1000);assert.equal(sent.stickers[4].schema,0);assert.equal(sent.stickers[4].x,.001);
  assert.deepEqual(inspect.toCraft(state(p),p),{id:item.id,stickers:item.stickers});
  const noZero=state(p,{'0':{id:0,schema:0}}),zero=inspect.toCraft(noZero,p).stickers[0];assert.equal(zero.def,100);assert.equal(zero.wear,0);assert.equal(zero.rotation,0);assert.equal(zero.schema,0);
  const five=state(p,Object.fromEntries(Array.from({length:5},(_,i)=>[i,{id:1000,schema:0}])));assert.equal(inspect.toCraft(five,p).stickers.length,5,'5 stacks may share 1 anchor');
  const eight={...model,schema_count:8};const broad=inspect.prepare({...item,inspect_model:eight},shop);assert.equal(broad.model.schema_count,8);assert.equal(inspect.toCraft(state(broad,{'4':{id:1000,schema:7}}),broad).stickers[0].schema,7);
  const knife=inspect.prepare({...item,def:507,paint:38,slot:'knife',stickers:[]},shop);assert.equal(knife.expectedId,0);assert.equal(knife.editable,false);assert.throws(()=>inspect.toCraft(state(knife),knife));
  assert.throws(()=>inspect.prepare({...item,stickers:[{def:9999,slot:0}]},shop),/已有贴纸/);assert.throws(()=>inspect.prepare({...item,paint:999},shop),/暂不支持/);
  assert.throws(()=>inspect.prepare(item,{...shop,inspect_catalog:{...shop.inspect_catalog,embed_url:'https://evil.test/view'}}));
  assert.throws(()=>inspect.prepare(item,{...shop,inspect_catalog:{...shop.inspect_catalog,stickers:{99:1000,100:1000}}}),/重复映射/);
  for(const bad of [null,[],{}, {...state(p),item:{id:333}},{...state(p),schemaCount:0},{...state(p),schemaCount:'4'},state(p,[{id:1000}]),state(p,{'5':{id:1000}}),state(p,{'00':{id:1000}}),state(p,{'0':{id:999}}),state(p,{'0':{id:'1000'}}),state(p,{'0':{id:1000,x:.051}}),state(p,{'0':{id:1000,y:-.041}}),state(p,{'0':{id:1000,rotation:181}}),state(p,{'0':{id:1000,wear:1.01}}),state(p,{'0':{id:1000,schema:4}}),state(p,{'0':{id:1000,schema:-1}}),state(p,{'0':{id:1000,wear:NaN}})])assert.throws(()=>inspect.toCraft(bad,p),'malformed/changed/bounds');
  assert.equal(Object.keys(inspect.toCraft(state(p),p)).join(','),'id,stickers','no metadata rewritten by remote editor');
  const phrases=require(path.join(base,'desk/locales/en.js')).phrases;assert.match(phrases['保存当前贴纸'],/Save/);assert.match(phrases['3D 检视／直接贴纸'],/3D/);
  console.log('PASS: pure 3D appearance privacy, lib ID zero, old-kit preservation, 5 stacks/8 anchors, default zero, model bounds and changed-item validation.');
}
async function protocol(){
  const listeners=new Map(),timers=new Set(),sent=[],windowRef={postMessage:(m,origin)=>sent.push({m,origin})};
  const host={crypto:{randomUUID:()=> 'fixture'},addEventListener:(t,f)=>listeners.set(t,f),removeEventListener:(t,f)=>{if(listeners.get(t)===f)listeners.delete(t);},setTimeout:(f,ms)=>{const timer=setTimeout(()=>{timers.delete(timer);f();},ms);timers.add(timer);return timer;},clearTimeout:t=>{clearTimeout(t);timers.delete(t);}};
  const loads=new Set(),frame={contentWindow:windowRef,addEventListener:(_,f)=>loads.add(f),removeEventListener:(_,f)=>loads.delete(f)};
  const seen=[],client=inspect.createClient(frame,{host,onEvent:(t,d)=>seen.push([t,d])});
  const emit=(type,data,extra={})=>listeners.get('message')?.({origin:inspect.ORIGIN,source:windowRef,data:{source:inspect.SOURCE,v:1,type,data},...extra});
  assert.equal(sent[0].m.type,'ping');assert.equal(sent[0].origin,inspect.ORIGIN);
  await assert.rejects(client.getState());
  emit('ready',{v:1},{origin:'https://evil.test'});emit('ready',{v:1},{source:{}});emit('ready',{v:1},{data:{source:inspect.SOURCE,v:2,type:'ready'}});emit('ready',{v:1},{data:'ready'});assert.equal(client.ready,false);
  emit('ready',{v:1});assert.equal(client.ready,true);assert.equal(seen.length,1);
  const pending=client.getState(1000),request=sent.at(-1).m;assert.equal(request.type,'getState');
  emit('state',{}, {origin:'https://evil.test',data:{source:inspect.SOURCE,v:1,type:'state',id:request.id,data:{evil:true}}});
  emit('change',{}, {data:{source:inspect.SOURCE,v:1,type:'change',id:request.id,data:{stale:true}}});
  const value={fresh:true};emit('state',value,{data:{source:inspect.SOURCE,v:1,type:'state',id:request.id,data:value}});assert.deepEqual(await pending,value);
  const one=client.getState(1000),id1=sent.at(-1).m.id,two=client.getState(1000),id2=sent.at(-1).m.id;assert.notEqual(id1,id2);
  emit('state',{n:2},{data:{source:inspect.SOURCE,v:1,type:'state',id:id2,data:{n:2}}});emit('state',{n:1},{data:{source:inspect.SOURCE,v:1,type:'state',id:id1,data:{n:1}}});assert.deepEqual(await one,{n:1});assert.deepEqual(await two,{n:2});
  await assert.rejects(client.getState(8),/没有回应/);
  const closed=client.getState(1000),rejection=assert.rejects(closed,/已关闭/);client.destroy();await rejection;assert.equal(listeners.size,0);assert.equal(loads.size,0);assert.equal(timers.size,0);client.destroy();assert.equal(client.send('setItem',{}),false);await assert.rejects(client.getState());
  console.log('PASS: protocol strict origin/window/version, request type/id correlation, timeout, out-of-order replies and complete listener/timer disposal.');
}
const mockViewer=`<!doctype html><style>body{margin:0;background:#10242c;color:white;font:18px sans-serif}#fixture-gun{margin:90px 30px;padding:30px;background:#35545d}button{margin:20px}</style><div id="fixture-gun">Protocol test fixture — not a 3D renderer</div><script>
const params=new URLSearchParams(location.search);window.item=JSON.parse(params.get('item'));window.active=null;window.loaded=false;window.holdState=false;window.requests=[];window.incoming=[];window.skipRender=false;window.delayWear=false;
const copy=x=>JSON.parse(JSON.stringify(x));function reply(type,data,id){const m={source:'3d.cstrike.app',v:1,type,data};if(id)m.id=id;parent.postMessage(m,'http://skin-inspect.test');}
function state(){return{item:copy(window.item),schemaCount:loaded?4:0,activeSticker:active};}
function defaults(){for(const s of Object.values(item.stickers||{}))for(const k of ['wear','rotation','x','y'])if(s[k]===0)delete s[k];}
window.replyLatest=()=>{const id=requests.pop();if(id)reply('state',state(),id);};window.change=()=>reply('change',state());
window.addEventListener('message',e=>{if(e.origin!=='http://skin-inspect.test'||e.source!==parent)return;const m=e.data;if(m.source!=='3d.cstrike.app'||m.v!==1)return;incoming.push(copy(m));
if(m.type==='ping'){reply('ready',{v:1});reply('change',state());}
if(m.type==='getState'){if(holdState)requests.push(m.id);else reply('state',state(),m.id);}
if(m.type==='setItem'){if(skipRender){setTimeout(()=>{item=copy(m.data.item);defaults();change();},80);}else{loaded=false;reply('loading',{busy:true});setTimeout(()=>{item=copy(m.data.item);defaults();reply('change',state());loaded=true;reply('loading',{busy:false});reply('rendered',{item:copy(item)});reply('change',state());},50);}}
if(m.type==='setActiveSticker')active=m.data.index;
if(m.type==='setStickerWear'){const apply=()=>{const s=item.stickers?.[m.data.index];if(s){s.wear=m.data.wear;defaults();change();}};if(delayWear)setTimeout(apply,80);else apply();}
if(m.type==='setStickerSchema'){const s=item.stickers?.[m.data.index];if(s){s.schema=m.data.schema;s.x=0;s.y=0;s.rotation=0;defaults();change();}}
});setTimeout(()=>{loaded=true;defaults();reply('rendered',{item:copy(item)});reply('change',state());},150);
document.querySelector('#fixture-gun').onmousedown=()=>{const s=item.stickers?.[active];if(s){s.x=.002;s.y=.004;s.rotation=45.5;change();}};
</script>`;
async function browser(){
  if(process.env.CAREER_BROWSER_TEMP){process.env.TEMP=process.env.CAREER_BROWSER_TEMP;process.env.TMP=process.env.CAREER_BROWSER_TEMP;}
  const {chromium}=require(process.env.CAREER_PLAYWRIGHT||'playwright'),browser=await chromium.launch({channel:'chrome',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1280,height:720}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('http://skin-inspect.test/**',r=>r.fulfill({contentType:'text/html',body:'<div id="owner"><section class="collection-dialog"></section></div>'}));
    let viewerRequests=0;await page.route('https://3d.cstrike.app/view?**',r=>{viewerRequests++;return r.fulfill({contentType:'text/html',body:mockViewer});});
    await page.goto('http://skin-inspect.test');
    for(const file of ['style.css','desk.css','theme.css','desk/skin-crafts.css','desk/skin-inspect.css'])await page.addStyleTag({content:fs.readFileSync(path.join(base,file),'utf8')});
    await page.addScriptTag({content:`window.item=${JSON.stringify(item)};window.shop=${JSON.stringify(shop)};window.calls=[];window.navigation=[];window.CareerUI={go:route=>navigation.push(route)};window.saved=0;window.balance=100;window.messageBalance=0;const add=window.addEventListener.bind(window),remove=window.removeEventListener.bind(window);window.addEventListener=(type,fn,opt)=>{if(type==='message')messageBalance++;add(type,fn,opt);};window.removeEventListener=(type,fn,opt)=>{if(type==='message')messageBalance--;remove(type,fn,opt);};window.command=async(path,body)=>{calls.push({path,body:structuredClone(body)});item.stickers=structuredClone(body.stickers);return{ok:true};};`});
    for(const file of ['desk/i18n.js','desk/locales/en.js','desk/skin-inspect.js','desk/skin-crafts.js'])await page.addScriptTag({content:fs.readFileSync(path.join(base,file),'utf8')});
    await page.evaluate(()=>{shop.skin_integration.inspect_enabled=false;const owner=document.querySelector('#owner');owner.querySelector('section').innerHTML=CareerSkinCrafts.details(item,shop);CareerSkinCrafts.bindEditor(owner,item,{shop,command,onSaved:()=>saved++});});
    assert.equal(await page.locator('[data-skin-inspect]').count(),0);assert.equal(await page.locator('[data-skin-craft-form] [type="submit"]').isDisabled(),false,'free advanced editor remains available while hosted service is disabled');
    assert.equal(await page.evaluate(()=>CareerSkinInspect.open(document.querySelector('#owner'),item,shop)),null);assert.equal(viewerRequests,0);
    assert.equal(await page.locator('.skin-external-links a').count(),2);await page.locator('[data-skin-inspect-settings]').click();assert.deepEqual(await page.evaluate(()=>navigation),['settings']);assert.equal(viewerRequests,0);
    await page.evaluate(()=>{shop.skin_integration.inspect_enabled=true;const owner=document.querySelector('#owner');owner.querySelector('section').innerHTML=CareerSkinCrafts.details(item,shop);CareerSkinCrafts.bindEditor(owner,item,{shop,command,onSaved:()=>saved++});});
    assert.equal(await page.locator('iframe').count(),0,'opening detail does not connect to hosted 3D');
    async function open(){await page.locator('[data-skin-inspect]').click();await page.waitForFunction(()=>!document.querySelector('[data-inspect-save]').disabled);return page.frames().find(f=>f.url().startsWith('https://3d.cstrike.app/view'));}
    let frame=await open();assert.ok(frame);assert.equal(await page.locator('iframe').getAttribute('sandbox'),'allow-scripts allow-same-origin');assert.equal(await page.locator('iframe').getAttribute('referrerpolicy'),'no-referrer');
    assert.doesNotMatch(await page.locator('iframe').getAttribute('src'),/inv.private|Private|account|token/);
    await page.locator('[data-inspect-slot="0"]').click();await page.locator('[data-inspect-kit="99"]').click();await page.waitForFunction(()=>!document.querySelector('[data-inspect-save]').disabled);
    let remote=await frame.evaluate(()=>({item,active,incoming}));assert.equal(remote.active,0);assert.equal(remote.item.stickers[0].id,1000);assert.ok(!Object.hasOwn(remote.item.stickers[0],'wear'),'real hosted shape omits zero wear');assert.ok(!Object.hasOwn(remote.item.stickers[0],'rotation'));
    await frame.locator('#fixture-gun').click();await page.waitForFunction(()=>!document.querySelector('[data-inspect-save]').disabled);
    await frame.evaluate(()=>{holdState=true;});await page.locator('[data-inspect-save]').click();await frame.waitForFunction(()=>requests.length>0);assert.equal(await page.evaluate(()=>calls.length),0,'save waits for fresh correlated state');
    await frame.evaluate(()=>{item.stickers[0].x=.005;replyLatest();});await page.waitForFunction(()=>saved===1);
    const saved=await page.evaluate(()=>({call:calls[0],item,balance,messageBalance}));assert.equal(saved.call.path,'/api/skins/craft');assert.equal(saved.call.body.stickers[0].x,.005,'not stale last change x=.002');assert.equal(saved.call.body.stickers[0].rotation,45.5);assert.equal(saved.call.body.stickers[1].slot,4);assert.equal(saved.call.body.stickers[1].schema,0);assert.equal(saved.item.nametag,'Private name');assert.equal(saved.item.seed,317);assert.equal(saved.item.wear,.12345);assert.equal(saved.item.stattrak,0);assert.equal(saved.balance,100);assert.equal(saved.messageBalance,0);assert.deepEqual(Object.keys(saved.call.body),['id','stickers']);assert.equal(await page.locator('iframe').count(),0);
    frame=await open();await frame.evaluate(()=>{holdState=true;});await page.locator('[data-inspect-save]').click();await frame.waitForFunction(()=>requests.length>0);await page.locator('[data-inspect-close]').click();await page.waitForTimeout(30);assert.equal(await page.evaluate(()=>calls.length),1,'close cancels save before snapshot arrives');assert.equal(await page.evaluate(()=>messageBalance),0);assert.equal(await page.locator('iframe').count(),0);
    frame=await open();await frame.evaluate(()=>{skipRender=true;delayWear=true;});await page.locator('[data-inspect-slot="0"]').click();
    await page.locator('[data-inspect-wear]').evaluate(el=>{el.value='.2';el.dispatchEvent(new Event('input',{bubbles:true}));});assert.equal(await page.locator('[data-inspect-save]').isDisabled(),true,'wear awaits state commit');await page.waitForFunction(()=>!document.querySelector('[data-inspect-save]').disabled);
    await page.locator('[data-inspect-remove]').click();await page.waitForFunction(()=>!document.querySelector('[data-inspect-save]').disabled);assert.equal(await frame.evaluate(()=>item.stickers[0]),undefined,'cached deletion completes without rendered');
    await page.locator('[data-inspect-kit="99"]').click();await page.waitForFunction(()=>!document.querySelector('[data-inspect-save]').disabled);
    await frame.evaluate(()=>{item.stickers[0].x=.004;item.stickers[0].y=.003;change();});await page.locator('[data-inspect-kit="99"]').click();assert.equal(await page.locator('[data-inspect-save]').isDisabled(),true,'same kit reapply waits for x/y reset');await page.waitForFunction(()=>!document.querySelector('[data-inspect-save]').disabled);assert.equal(await frame.evaluate(()=>item.stickers[0].x??0),0);await page.locator('[data-inspect-close]').click();
    frame=await open();await frame.evaluate(()=>{item.id=333;change();});await page.waitForFunction(()=>document.querySelector('[data-inspect-status]').textContent.includes('已变化'));assert.equal(await page.locator('[data-inspect-save]').isDisabled(),true);await page.locator('[data-inspect-close]').click();assert.equal(await page.evaluate(()=>calls.length),1);
    frame=await open();await frame.evaluate(()=>{holdState=true;});await page.locator('[data-inspect-save]').click();await frame.waitForFunction(()=>requests.length>0);await frame.evaluate(()=>{reply('rateLimited',{retryAfterMs:3000});replyLatest();reply('rendered',{item});});await page.waitForFunction(()=>document.querySelector('[data-inspect-status]').textContent.includes('暂受限'));assert.equal(await page.locator('[data-inspect-save]').isDisabled(),true);assert.equal(await page.evaluate(()=>calls.length),1,'fault while waiting for fresh state blocks POST');await page.locator('[data-inspect-close]').click();assert.equal(await page.evaluate(()=>balance),100);
    frame=await open();await page.evaluate(()=>window.dispatchEvent(new PopStateEvent('popstate')));assert.equal(await page.locator('iframe').count(),0);assert.equal(await page.evaluate(()=>messageBalance),0);
    await page.evaluate(()=>CareerI18n.setLocale('en'));frame=await open();assert.match(await page.locator('[data-inspect-save]').innerText(),/Save current stickers/);
    await page.setViewportSize({width:736,height:600});assert.equal(await page.locator('.skin-inspect-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth+1&&el.getBoundingClientRect().right<=innerWidth),true);
    await page.evaluate(()=>document.querySelector('#owner').remove());await page.waitForTimeout(30);assert.equal(await page.evaluate(()=>messageBalance),0);assert.equal(await page.locator('iframe').count(),0);assert.deepEqual(errors,[]);
    console.log('PASS: opt-in gates with zero disabled viewer requests, free editor, settings route, isolated mock-iframe Chromium click flow, delayed model/omitted zero, fresh save, disposal, changed-item/rate-limit, English and 736px containment.');
  }finally{await browser.close();}
}
(async()=>{pure();await protocol();if(process.argv.includes('--browser'))await browser();})().catch(error=>{console.error(error);process.exitCode=1;});
