const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let reads=0,route,rendered=0,language='zh-CN',currentRoute={view:'home'};
const listeners=new Map();
const buttons=[{dataset:{arcPage:'2'}}],host={innerHTML:'',querySelectorAll:()=>buttons};
const env=vm.createContext({CareerUI:{pages:{},head:(t)=>t,empty:String,go:(v,p)=>route={v,p},
  route:()=>currentRoute,render:()=>rendered++},
  document:{addEventListener:(name,callback)=>listeners.set(name,callback)},
  window:{CareerI18n:{field:(row,key)=>language==='en'?(row[key+'_en']??row[key]):row[key]}},
  esc:s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'),
  get:async url=>{assert.match(url,/^\/api\/story-history\?page=/);reads++;return {total:21,page:1,pages:2,rows:[{title:'<img onerror=alert(1)>',title_en:'English <img>',text:'<script>bad()</script>',text_en:'English <script>bad()</script>',date:'2026-02-01',choice:'继续职业',choice_en:'Continue career'}]};}
});
vm.runInContext(fs.readFileSync('cs2career/web/static/desk/arcs.js','utf8'),env);
(async()=>{
 const summary=env.CareerUI.arcSummary({story_arcs:{enabled:true,na:'returned',deadline:'2028-01-01',na_progress:{success_types:['t2']},heat:true,injury_active:{until:'2027-02-01'}}});
 assert.match(summary,/2028-01-01/);assert.match(summary,/T2/);assert.match(summary,/Major/);assert.match(summary,/伤病/);
 assert.equal(env.CareerUI.arcSummary({story_arcs:{enabled:false}}),'');
 await env.CareerUI.pages['story-history']({},host,()=>true);
 assert.match(host.innerHTML,/&lt;script&gt;/);assert.doesNotMatch(host.innerHTML,/<script>/);
 assert.match(host.innerHTML,/继续职业/);assert.equal(reads,1);
 buttons[0].onclick();assert.equal(route.v,'story-history');assert.equal(route.p.page,2);
 const original=host.innerHTML;await env.CareerUI.pages['story-history']({},host,()=>false);assert.equal(original,host.innerHTML);
 assert.equal(typeof listeners.get('career:language'),'function');
 listeners.get('career:language')();assert.equal(rendered,0,'language changes do not redraw an unrelated route');
 currentRoute={view:'story-history'};language='en';listeners.get('career:language')();assert.equal(rendered,1);
 await env.CareerUI.pages['story-history']({},host,()=>true);
 assert.match(host.innerHTML,/English &lt;img&gt;/);assert.match(host.innerHTML,/English &lt;script&gt;/);
 assert.match(host.innerHTML,/Continue career/);assert.doesNotMatch(host.innerHTML,/<script>|<img>/);
 console.log('Career story UI: status, paging, escaped translations, language listener, stale response guard, read-only actions passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
