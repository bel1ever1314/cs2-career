const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let reads=0,route;
const buttons=[{dataset:{arcPage:'2'}}],host={innerHTML:'',querySelectorAll:()=>buttons};
const env=vm.createContext({CareerUI:{pages:{},head:(t)=>t,empty:String,go:(v,p)=>route={v,p}},
  esc:s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'),
  get:async url=>{assert.match(url,/^\/api\/story-history\?page=/);reads++;return {total:21,page:1,pages:2,rows:[{title:'<img onerror=alert(1)>',text:'<script>bad()</script>',date:'2026-02-01',choice:'继续职业'}]};}
});
vm.runInContext(fs.readFileSync('cs2career/web/static/desk/arcs.js','utf8'),env);
(async()=>{
 const summary=env.CareerUI.arcSummary({story_arcs:{enabled:true,na:'returned',deadline:'2028-01-01',heat:true,injury_active:{until:'2027-02-01'}}});
 assert.match(summary,/2028-01-01/);assert.match(summary,/T2/);assert.match(summary,/Major/);assert.match(summary,/伤病/);
 assert.equal(env.CareerUI.arcSummary({story_arcs:{enabled:false}}),'');
 await env.CareerUI.pages['story-history']({},host,()=>true);
 assert.match(host.innerHTML,/&lt;script&gt;/);assert.doesNotMatch(host.innerHTML,/<script>/);
 assert.match(host.innerHTML,/继续职业/);assert.equal(reads,1);
 buttons[0].onclick();assert.equal(route.v,'story-history');assert.equal(route.p.page,2);
 const original=host.innerHTML;await env.CareerUI.pages['story-history']({},host,()=>false);assert.equal(original,host.innerHTML);
 console.log('Career story UI: status, paging, escaped text, stale response guard, read-only actions passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
