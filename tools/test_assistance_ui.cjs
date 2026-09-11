// The actual runner with deterministic command replies; no browser or save.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const scoreWrites=[];
class Element {
 constructor(){this.nodes={};this.children=[];this.inert=false;}
 set innerHTML(value){this.html=value;this.nodes={};for(const m of value.matchAll(/\bdata-([\w-]+)(?=[\s=>])/g))this.nodes[m[1]]=new Element();}
 get innerHTML(){return this.html;}
 set textContent(value){this.text=value;if(/A  \d+ : \d+  B/.test(value))scoreWrites.push(value);}
 get textContent(){return this.text;}
 querySelector(s){return this.nodes[/data-([\w-]+)/.exec(s)?.[1]]||null;}
 querySelectorAll(){return Object.values(this.nodes);}
 setAttribute(){}focus(){}remove(){}appendChild(e){this.children.push(e);}
}
const body=new Element(),shell=new Element(),event={id:'2026::cup',matches:[{id:'2026::m1',team_a:'A',team_b:'B',played:false}]};
let replies=[],calls=0,concurrent=0,maxConcurrent=0,graphs=[],destinations=[],toasts=[];
const sandbox={window:{},document:{body,createElement:()=>new Element(),querySelector:()=>shell},
 S:{career:{assist:{},stories:[]}},STORY_BUSY:false,PLAY_TIMER:null,
 esc:String,myTeamName:()=> 'A',axisLabels:()=>({firepower:'火力'}),stopSeriesPoll:()=>{},ensureCs2AutoIngest:()=>{},clearInterval:()=>{},
 crypto:{randomUUID:()=>`test-token-${calls}`},setTimeout:fn=>{queueMicrotask(fn);return 1},
 toast:text=>toasts.push(text),get:async()=>JSON.parse(JSON.stringify(event)),
 CareerUI:{drawTournamentGraph:ev=>{graphs.push(JSON.parse(JSON.stringify(ev)));return ''},bindTournamentGraph:()=>{},
  paint:(host,html)=>host.innerHTML=html,
  go:(view,args)=>destinations.push([view,args]),match:id=>destinations.push(['match',id])},
 post:async(url,payload,options)=>{assert.equal(options.render,false,'simulation must not repaint the background page');calls++;concurrent++;maxConcurrent=Math.max(maxConcurrent,concurrent);const result=replies.shift();assert.ok(result,'unexpected extra automatic step');
   await options.beforeApply(result);sandbox.S.career.stories=result.stories||[];concurrent--;return result;}};
vm.runInNewContext(fs.readFileSync('cs2career/web/static/desk/assistance.js','utf8'),sandbox);
const api=sandbox.window.CareerAssist;
(async()=>{
 assert.match(api.mailPanel(),/自动拒绝/);assert.match(api.pointPanel(),/均衡发展/);
 replies=[{ok:true,auto_step:{status:'played',match:{id:'m1',team_a:'A',team_b:'B',best_of:3,start:0,winners:['B','A','A']}}},
          {ok:true,auto_step:{status:'decision',msg:'生死战'},stories:[{id:'choice',choices:[{id:'manual'}]}]}];
 await api.run(event.id);
 assert.equal(calls,2);assert.equal(maxConcurrent,1);assert.equal(shell.inert,true);
 assert.equal(api.isOpen(),true,'story pauses retain the viewer');
 assert.deepEqual(scoreWrites,['A  0 : 1  B','A  1 : 1  B','A  2 : 1  B']);
 assert.equal(graphs.length,1,'score-only updates must not recreate the graph');
 const overlay=body.children.at(-1),beforeCount=body.children.length;
 sandbox.S.career.stories=[];
 replies=[{ok:true,auto_step:{status:'decision'},stories:[{id:'choice2'}]}];
 api.afterStory({when:'tournament_decision',event_id:event.id},'simulate');
 await new Promise(setImmediate);
 assert.equal(body.children.length,beforeCount,'resume must reuse the overlay');
 assert.equal(body.children.at(-1),overlay);assert.equal(graphs.length,1);
 const oldCalls=calls;api.afterStory({when:'tournament_decision',match_id:'m2'},'manual');
 await new Promise(setImmediate);assert.equal(calls,oldCalls);assert.equal(destinations.at(-1)[0],'match');
 sandbox.S.career.stories=[];
 replies=[{ok:true,auto_step:{status:'done',msg:'结束'}}];
 api.afterStory({when:'tournament_decision',event_id:event.id},'simulate');
 await new Promise(setImmediate);assert.equal(calls,4);assert.equal(shell.inert,false);
 api.afterStory({when:'tournament_decision',event_id:event.id},'later');
 await new Promise(setImmediate);assert.equal(calls,4);
 assert.ok(!toasts.some(t=>t.includes('自动模拟已停止：')));
 console.log('Assistance UI: sequential requests, 0:1→1:1→2:1, decisive pause, manual choice, simulated resume and later-stop passed');
})().catch(e=>{console.error(e);process.exitCode=1});
