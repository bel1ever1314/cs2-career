/* Run the actual acknowledgement handler with controlled network outcomes. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('cs2career/web/static/app.js','utf8');
const handler=source.slice(source.indexOf('let STORY_ACK_BUSY ='),source.indexOf('document.addEventListener("keydown"',source.indexOf('let STORY_ACK_BUSY =')));
let requests=0,release;
const context=vm.createContext({STORY_Q:[{id:'decision'}],S:{career:{}},sessionStorage:{getItem:()=> 'session-test'},
  paintStory:()=>{},render:()=>{},adopt:()=>{},takeStories:()=>{},toast:()=>{},
  fetch:async(_url,opts)=>{assert.equal(opts.headers['X-Career-Token'],'session-test');requests++;await new Promise(r=>release=r);return {ok:false,json:async()=>({ok:false,msg:'retry'})};}});
vm.runInContext(handler,context);
(async()=>{
  const first=context.ackStory('refuse');
  await context.ackStory('refuse');assert.equal(requests,1,'double click is blocked');
  release();await first;assert.equal(context.STORY_Q.length,1,'failure retains the pending decision');
  context.fetch=async()=>({ok:true,json:async()=>({ok:true,state:{career:{}},stories:[]})});
  await context.ackStory('refuse');assert.equal(context.STORY_Q.length,0,'success removes the decision');
  console.log('Story acknowledgement: session header, retry and duplicate-click checks passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
