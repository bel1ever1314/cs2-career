const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes={},button={dataset:{personalApply:'0'},disabled:false};
const host={innerHTML:'',querySelectorAll:s=>s==='[data-personal-apply]'?[button]:[]};
let requests=0,complete,adopted,stories;
const quote={team_id:'test-team',team:'Test <team>',role:'rifle',replace:'Replacement',modifier:2,chance:.55,blocked:''};
const data={targets:[quote],offers_this_year:0,offer_limit:4,history:[],apply_until:'',move_until:''};
const env=vm.createContext({CareerUI:{pages:{},head:()=>'',link:(_k,_id,n)=>n,empty:String,remember(){},go(){}},
 S:{career:{exists:true,player_only:false}},ROLE:{rifle:'步枪手'},get:async()=>data,
 $:id=>nodes[id]||=( {value:''} ),esc:s=>String(s??'').replaceAll('<','&lt;').replaceAll('>','&gt;'),
 window:{confirm:()=>true,matchMedia:()=>({matches:true})},sessionStorage:{getItem:()=> 'test-token'},
 toast(){},adopt:s=>adopted=s,render(){},takeStories:s=>stories=s,
 fetch:async(url,options)=>{
   assert.equal(url,'/api/player/transfers/apply');assert.equal(options.headers['X-Career-Token'],'test-token');
   assert.deepEqual(JSON.parse(options.body),{team_id:'test-team',role:'rifle'});requests++;
   await new Promise(r=>complete=r);
   return {ok:true,json:async()=>({ok:true,state:{career:{team_id:'old-team'}},transfer:{roll:20},stories:[{id:'decision'}]})};
 }});
vm.runInContext(fs.readFileSync('cs2career/web/static/desk/personal-transfers.js','utf8'),env);
(async()=>{
 await env.CareerUI.personalTransferPage({source:'personal'},host,()=>true);
 assert.match(host.innerHTML,/55%/);assert.match(host.innerHTML,/180天/);assert.match(host.innerHTML,/0 \/ 4/);
 const first=button.onclick();await button.onclick();assert.equal(requests,1,'only one server command');
 complete();await first;assert.equal(adopted.career.team_id,'old-team','application is not immediate joining');
 assert.equal(stories[0].id,'decision');
 quote.blocked='申请冷却';data.last_attempt={team:'Test',date:'2026-01-01',roll:1,modifier:2,total:3,success:false};
 await env.CareerUI.personalTransferPage({source:'personal'},host,()=>true);
 assert.match(host.innerHTML,/未通过/);assert.match(host.innerHTML,/申请冷却/);
 await button.onclick();assert.equal(requests,1,'blocked quote never rolls');
 console.log('Personal transfer UI: exact quote, session header, one POST, deferred decision, cooldown and saved result passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
