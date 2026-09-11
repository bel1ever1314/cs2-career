// Isolated Chromium DOM regression. Never starts the career backend or opens a save.
const {chromium}=require('playwright');
const fs=require('node:fs'),assert=require('node:assert/strict');
const read=p=>fs.readFileSync('cs2career/web/static/'+p,'utf8');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1280,height:720}});
  await page.setContent('<main id="root"></main><div id="graph"></div><div id="story-modal"></div>');
  await page.addScriptTag({content:read('desk/dom.js')});
  const basic=await page.evaluate(()=>{
   const host=document.querySelector('#root'),paint=CareerDOM.paint;
   const content=(score,order=['a','b'])=>`<h2>生涯资料</h2><p id="score">${score}</p><input id="filter" value=""><button id="action">操作</button><details id="history"><summary>历史</summary><p>比赛记录</p></details><section>${order.map(id=>`<article data-ui-key="${id}"><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="><b>${id}</b></article>`).join('')}</section>`;
   paint(host,content(0));
   const a=host.querySelector('article'),img=a.querySelector('img'),score=host.querySelector('#score');
   const field=host.querySelector('#filter');field.focus();field.value='正在输入';field.setSelectionRange(2,2);
   host.querySelector('details').open=true;
   let clicks=0;host.querySelector('button').onclick=()=>clicks++;
   for(let i=1;i<=20;i++){paint(host,content(i));host.querySelector('button').onclick=()=>clicks++;}
   host.querySelector('button').click();
   const retained=a===host.querySelector('article')&&img===host.querySelector('img')&&score===host.querySelector('#score');
   const typing=document.activeElement===field&&field.value==='正在输入'&&field.selectionStart===2;
   paint(host,content(21,['b','a','c']));
   const reordered=host.querySelectorAll('article')[1]===a&&a.querySelector('img')===img;
   const open=host.querySelector('details').open;
   paint(host,'<input id="check" type="checkbox" checked><button id="disabled" disabled>操作</button><script>window.unexpectedScript=true</script>');
   paint(host,'<input id="check" type="checkbox"><button id="disabled">操作</button>');
   return {retained,typing,reordered,open,clicks,controls:!host.querySelector('input').checked&&!host.querySelector('button').disabled,safe:!window.unexpectedScript};
  });
  assert.deepEqual(basic,{retained:true,typing:true,reordered:true,open:true,clicks:1,controls:true,safe:true});
  await page.addScriptTag({content:`window.CareerUI={pages:{},paint:CareerDOM.paint,link:(k,id,t)=>'<button>'+t+'</button>'};window.myTeamName=()=> 'Mine';window.esc=String;window.crest=()=>'<img width="20" height="20" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==">';window.toast=()=>{};`});
  await page.addScriptTag({content:read('desk/competitions.js')});
  await page.addScriptTag({content:read('desk/assistance.js')});
  await page.addStyleTag({content:'.graph-viewport{width:700px;height:300px;overflow:auto}.graph-board{position:relative}.graph-position,.graph-stage,.bracket-lines{position:absolute}.graph-position{width:280px}'});
  const graph=await page.evaluate(()=>{
   const host=document.querySelector('#graph'),update=CareerAssist.pathView(host,'Mine');
   const match=(id,stage)=>({id,stage,team_a:'Mine',team_b:'Other',best_of:3,played:false});
   const ev={matches:[match('m1','QF'),match('m2','SF')],links:[{source:'m1',target:'m2',team:'Mine'}]};
   update(ev,'');const node=host.querySelector('[data-node="m1"]'),img=node.querySelector('img'),viewport=host.querySelector('.graph-viewport');
   host.querySelector('[data-zoom="+"]').click();viewport.scrollLeft=30;
   ev.matches[0].played=true;ev.matches[0].series='2 : 1';ev.matches[0].winner='Mine';update(ev,'');
   const score=node.querySelector('.node-title span').textContent;
   ev.matches.push(match('m3','GF'));ev.links.push({source:'m2',target:'m3',team:'Mine'});update(ev,'');
   return {same:host.querySelector('[data-node="m1"]')===node&&node.querySelector('img')===img,viewport:host.querySelector('.graph-viewport')===viewport,score,zoom:host.querySelector('.graph-board').style.transform,left:viewport.scrollLeft,count:host.querySelectorAll('[data-node]').length};
  });
  assert.deepEqual(graph,{same:true,viewport:true,score:'2 : 1',zoom:'scale(1.15)',left:30,count:3});
  const source=read('app.js'),story=source.slice(source.indexOf('function paintStory()'),source.indexOf('function playerFace('));
  await page.addScriptTag({content:`window.$=id=>document.getElementById(id);window.STORY_Q=[{id:'one',text:'教练正在等你做决定。',choices:[{id:'yes',label:'继续比赛'}]}];window.STORY_BUSY=false;window.stopCount=0;window.stopReveal=()=>stopCount++;window.revealNext=null;window.ackStory=()=>{};${story}`});
  const modal=await page.evaluate(()=>{
   paintStory();const button=document.querySelector('#story-modal button');
   paintStory();paintStory();const stable=button===document.querySelector('#story-modal button')&&stopCount===1;
   STORY_Q=[{id:'two',text:'接下来的一场比赛。',choices:[]}];paintStory();
   const changed=document.querySelector('#story-modal').textContent.includes('接下来');
   STORY_Q=[];paintStory();return {stable,changed,closed:!document.querySelector('#story-modal')&&!STORY_BUSY};
  });
  assert.deepEqual(modal,{stable:true,changed:true,closed:true});
  await page.addStyleTag({content:read('desk/spectator.css')+'#story-modal{position:fixed;inset:0;z-index:80;background:#0008}'});
  await page.addScriptTag({content:`window.S={career:{assist:{},stories:[]}};window.PLAY_TIMER=null;window.stopSeriesPoll=()=>{};window.ensureCs2AutoIngest=()=>{};window.calls=0;window.CareerUI.go=()=>{};window.get=async()=>({matches:[{id:'m1',stage:'QF',team_a:'Mine',team_b:'Other',best_of:3}],links:[]});window.post=async()=>{calls++;const row={id:'pause'+calls,text:'赛前选择',when:'tournament_decision',choices:[{id:'simulate',label:'继续模拟'}]};S.career.stories=calls<3?[row]:[];STORY_Q=S.career.stories;paintStory();return {ok:true,auto_step:{status:calls<3?'decision':'done'},stories:S.career.stories};};`});
  // about:blank may not expose randomUUID in some Chromium configurations.
  await page.evaluate(()=>{if(!crypto.randomUUID)crypto.randomUUID=()=>String(Math.random());});
  await page.evaluate(async()=>{
   await CareerAssist.run('cup');window.heldOverlay=document.querySelector('.event-auto-overlay');
   window.heldGraph=heldOverlay.querySelector('.graph-viewport');
  });
  assert.equal(await page.evaluate(()=>Number(getComputedStyle(document.querySelector('#story-modal')).zIndex)>Number(getComputedStyle(heldOverlay).zIndex)),true,'story must be above the retained viewer');
  await page.evaluate(()=>{S.career.stories=[];STORY_Q=[];paintStory();CareerAssist.afterStory({when:'tournament_decision',event_id:'cup'},'simulate');});
  await page.waitForFunction(()=>calls===2&&!!document.querySelector('.awaiting-story'));
  assert.equal(await page.evaluate(()=>heldOverlay===document.querySelector('.event-auto-overlay')&&heldGraph===heldOverlay.querySelector('.graph-viewport')),true);
  await page.evaluate(()=>{S.career.stories=[];STORY_Q=[];paintStory();CareerAssist.afterStory({when:'tournament_decision',event_id:'cup'},'simulate');});
  await page.waitForFunction(()=>calls===3&&!document.querySelector('.event-auto-overlay'));
  console.log('Chromium: 20 in-place refreshes, image/node identity, focus/caret, keyed reorder, controls, script exclusion, appended round with preserved camera, and stable story modal passed.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
