/* Opt-in live viewer QA. No Career, Steam login, saves, or game files. */
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
async function main(){
  if(!process.argv.includes('--live')){console.log('Use --live to test the anonymous hosted 3D viewer. No game/save access.');return;}
  process.env.TEMP=process.env.CAREER_BROWSER_TEMP||'D:/CS2CareerBuilds/runtime-temp';process.env.TMP=process.env.TEMP;
  const {chromium}=require(process.env.CAREER_PLAYWRIGHT||'playwright');
  const manifest=JSON.parse(fs.readFileSync(path.join(root,'cs2career/data/inspect_catalog.json'),'utf8'));
  const stickers=JSON.parse(fs.readFileSync(path.join(root,'cs2career/data/stickers.json'),'utf8')).stickers;
  const fixture={item:{id:'isolated-test',name:'AK-47 | Redline',def:7,paint:282,slot:'ak47',wear:.15,seed:1,stickers:[],sticker_capable:true},shop:{skin_integration:{inspect_enabled:true},inspect_catalog:manifest,stickers}};
  const server=http.createServer((req,res)=>{
    if(req.url==='/skin-inspect.js'||req.url==='/skin-inspect.css'){
      res.setHeader('Content-Type',req.url.endsWith('js')?'application/javascript':'text/css');
      res.end(fs.readFileSync(path.join(root,'cs2career/web/static/desk',req.url.slice(1))));return;
    }
    res.setHeader('Content-Type','text/html; charset=utf-8');res.end(`<!doctype html><link rel="stylesheet" href="/skin-inspect.css"><body><div id="owner"><button id="start">打开3D</button></div><script src="/skin-inspect.js"></script><script>const f=${JSON.stringify(fixture)};window.commands=[];window.saved=false;document.querySelector('#start').onclick=()=>{window.controller=CareerSkinInspect.open(document.querySelector('#owner'),f.item,f.shop,{command:async(route,body)=>{commands.push({route,body});return {ok:true}},onSaved:()=>saved=true})};</script>`);
  });
  let browser;
  try{
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    browser=await chromium.launchPersistentContext(path.join(process.env.TEMP,'skin-inspect-profile'),{channel:'chrome',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
    const page=await browser.newPage({viewport:{width:1280,height:800}});
    await page.setViewportSize({width:1280,height:800});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(()=>{window.inspectMessages=[];addEventListener('message',event=>{if(event.origin==='https://3d.cstrike.app')inspectMessages.push(event.data);});});
    await page.goto(`http://127.0.0.1:${server.address().port}`);await page.click('#start');
    await page.locator('[data-inspect-save]').waitFor();
    try{await page.waitForFunction(()=>!document.querySelector('[data-inspect-save]').disabled,null,{timeout:45000});}
    catch(error){console.error('Viewer diagnostics:',JSON.stringify({errors,frames:page.frames().map(f=>f.url()),snapshot:await page.evaluate(()=>({status:document.querySelector('[data-inspect-status]')?.textContent,ready:controller?.client.ready,messages:inspectMessages}))}));await page.screenshot({path:path.join(process.env.TEMP,'skin-inspect-live-failure.png')});throw error;}
    const kit=stickers[0].def;
    await page.click(`[data-inspect-kit="${kit}"]`);
    await page.waitForFunction(()=>!document.querySelector('[data-inspect-save]').disabled,null,{timeout:20000});
    const state=await page.evaluate(()=>controller.client.getState());
    assert.equal(state.item.id,222);assert.equal(state.item.stickers[0].id,manifest.stickers[kit]);
    assert.equal(state.activeSticker,0);
    const bounds=await page.locator('iframe').boundingBox();
    const sx=bounds.x+bounds.width*.64,sy=bounds.y+bounds.height*.345;
    await page.mouse.move(sx,sy);await page.mouse.down();await page.mouse.move(sx-30,sy+8,{steps:12});await page.mouse.up();
    async function waitSticker(predicate){for(let i=0;i<80;i++){const snapshot=await page.evaluate(()=>controller.client.getState());if(predicate(snapshot.item.stickers[0]))return snapshot;await page.waitForTimeout(100);}throw Error('Real pointer operation was not confirmed by committed viewer state');}
    const dragged=await waitSticker(s=>Math.abs(s.x??0)+Math.abs(s.y??0)>0.00001);
    console.log('Actual drag snapshot:',JSON.stringify(dragged));
    if(!Math.abs(dragged.item.stickers[0].x??0)&&!Math.abs(dragged.item.stickers[0].y??0))console.error('Drag message history:',JSON.stringify(await page.evaluate(()=>inspectMessages.slice(-20))));
    await page.screenshot({path:path.join(process.env.TEMP,'skin-inspect-drag.png')});
    assert.ok(Math.abs(dragged.item.stickers[0].x??0)+Math.abs(dragged.item.stickers[0].y??0)>0);
    await page.mouse.wheel(0,120);
    await waitSticker(s=>Math.abs(s.rotation??0)>0);
    await page.screenshot({path:path.join(process.env.TEMP,'skin-inspect-live.png')});
    // Exercise actual native anchor cycling, then save a fresh viewer snapshot.
    await page.click('[data-inspect-preset]');
    await page.waitForFunction(()=>!document.querySelector('[data-inspect-save]').disabled,null,{timeout:20000});
    await page.click('[data-inspect-save]');
    await page.waitForFunction(()=>saved,null,{timeout:10000});
    const calls=await page.evaluate(()=>commands);
    assert.equal(calls.length,1);assert.equal(calls[0].route,'/api/skins/craft');
    assert.equal(calls[0].body.id,'isolated-test');assert.equal(calls[0].body.stickers[0].def,kit);
    assert.equal(calls[0].body.stickers[0].schema,1);
    assert.equal(await page.locator('iframe').count(),0);
    console.log('PASS: live anonymous localhost iframe rendered real AK, added/selected sticker, dragged decal, rotated by wheel, changed native anchor, fetched fresh state, saved mapped sticker and disposed iframe. This is not a live CS2 alignment test.');
  }finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
