// Deterministic timers/DOM exercise the shipped viewer, without a player save.
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
class Element {
  constructor(){this.nodes={};this.children=[];this.isConnected=true;this.inert=false;}
  set innerHTML(value){this.html=value;this.nodes={}; for(const key of value.matchAll(/\bdata-([\w-]+)(?=[\s=>])/g))this.nodes[key[1]]=new Element();}
  get innerHTML(){return this.html;}
  querySelector(s){return this.nodes[/data-([\w-]+)/.exec(s)?.[1]]||null;}
  querySelectorAll(){return Object.values(this.nodes);}
  setAttribute(){} addEventListener(){} focus(){doc.activeElement=this;}
  appendChild(el){this.children.push(el);}
  remove(){this.isConnected=false;}
}
const doc={body:new Element(),activeElement:null,createElement:()=>new Element(),querySelector:()=>shell};
const shell=new Element(), timers=new Map();let seq=0, requests=0, adopted=0, data;
const sandbox={window:{},document:doc,setTimeout:fn=>{timers.set(++seq,fn);return seq},clearTimeout:id=>timers.delete(id),
  esc:String,mapName:String,crest:()=>'',toast:msg=>{throw Error(msg)},ensureCs2AutoIngest:()=>{},
  post:async(url,body,options)=>{requests++;assert.equal(url,'/api/series/skip');assert.equal(body.reveal,true);await options.beforeApply({reveal:data});adopted++;}};
vm.runInNewContext(fs.readFileSync('cs2career/web/static/desk/spectator.js','utf8'),sandbox);
const run=sandbox.window.CareerWatch.run;
function host(){return doc.body.children.at(-1);}
function next(){host().querySelector('[data-next]').onclick();}
function tick(){assert.equal(timers.size,1);const [id,fn]=timers.entries().next().value;timers.delete(id);fn();}
function map(rounds,index=0){return {index,map:'mirage',rounds,score:`${rounds.filter(x=>x==='a').length}-${rounds.filter(x=>x==='b').length}`,winner:'A',events_available:true};}
(async()=>{
 data={teams:['A','B'],initial:[0,0],best_of:3,maps:[map(['a','b','a','b','a','b','a','b','a','b','a','b',...Array(7).fill('a')])]};
 const pending=run({id:'match'});
 assert.equal(shell.inert,true);assert.equal(adopted,0);assert.equal(timers.size,0);
 await run({id:'match'});assert.equal(requests,1,'double click submits twice');
 next();for(let i=0;i<12;i++)tick();
 assert.equal(timers.size,0,'must stop at half time');
 assert.equal(host().querySelector('[data-score]').textContent,'6 : 6');
 assert.equal(host().querySelector('[data-next]').textContent,'开始下半场');
 assert.equal(adopted,0,'final state/stories must not spoil the reveal');
 next();tick();next();assert.equal(timers.size,0,'pause must cancel timer');next();
 for(let i=0;i<6;i++)tick();
 assert.equal(host().querySelector('[data-score]').textContent,'13 : 6');
 assert.equal(host().querySelector('[data-series]').textContent,'系列赛 1 : 0');
 next();await pending;assert.equal(adopted,1);assert.equal(shell.inert,false);assert.equal(timers.size,0);
 data={teams:['A','B'],initial:[1,1],best_of:5,maps:[map(Array.from({length:24},(_,i)=>i%2?'b':'a').concat(['a','a','a','a','b','b']),2)]};
 const overtime=run({id:'overtime'});next();for(let i=0;i<12;i++)tick();next();for(let i=0;i<12;i++)tick();
 assert.match(host().querySelector('[data-status]').textContent,/进入加时/);
 next();for(let i=0;i<3;i++)tick();assert.equal(timers.size,0);assert.match(host().querySelector('[data-status]').textContent,/加时换边/);
 host().querySelector('[data-skip]').onclick();await overtime;assert.equal(adopted,2);assert.equal(requests,2);
 assert.equal(timers.size,0,'skip leaves a live timer');
 data={teams:['A','B'],initial:[0,0],best_of:3,maps:[{...map([],0),score:'13-8',events_available:false},map(['a'].fill('a'),1)]};
 const missing=run({id:'missing'});assert.match(host().querySelector('[data-status]').textContent,/缺少/);
 next();assert.equal(host().querySelector('[data-score]').textContent,'13 : 8');next();
 assert.equal(host().querySelector('[data-score]').textContent,'0 : 0');assert.equal(host().querySelector('[data-series]').textContent,'系列赛 1 : 0');
 host().querySelector('[data-skip]').onclick();await missing;
 console.log('Spectator: halftime, pause, overtime, no spoilers, next map, missing history, skip and duplicate click passed');
})().catch(e=>{console.error(e);process.exitCode=1});
