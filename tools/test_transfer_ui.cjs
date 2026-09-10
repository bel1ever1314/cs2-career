const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const controls={'transfer-search':{value:''},'transfer-role':{value:''},'transfer-replace':{value:'mate'}};
const normal={dataset:{sign:'0',mode:'normal'},disabled:false},guaranteed={dataset:{sign:'0',mode:'guaranteed'},disabled:false};
const host={innerHTML:'',querySelectorAll:s=>s==='[data-sign]'?[normal,guaranteed]:[]};let sent;
const quote={player_id:'target',name:'Target',role:'awp',ability:88,seller_id:'',seller:'自由球员',normal_fee:100,normal_chance:.45,negotiation_fee:8,guaranteed_fee:300,multiplier:3,blocked:''};
const ctx=vm.createContext({CareerUI:{pages:{},head:()=>'',tabs:()=>'',link:(_k,_id,t)=>t,num:String,empty:String,go(){}},
 S:{career:{exists:true,money:10000,player_name:'You',roster:[{player_id:'mate',name:'Mate',role:'rifle'}]}},
 ROLE:{awp:'主狙',rifle:'步枪手'},get:async()=>({players:[quote]}),$:id=>controls[id]||=( {}),esc:String,money:n=>'$'+n,
 window:{confirm:()=>true},post:async(url,body)=>{sent={url,body};},toast(){}});
vm.runInContext(fs.readFileSync('cs2career/web/static/desk/transfers.js','utf8'),ctx);
(async()=>{
 await ctx.CareerUI.pages.market({},host,()=>true);
 assert.match(host.innerHTML,/45%/);assert.match(host.innerHTML,/100%保签/);assert.match(host.innerHTML,/失败扣 \$8/);
 await guaranteed.onclick();assert.equal(sent.body.mode,'guaranteed');assert.equal(sent.body.replace_id,'mate');assert.equal(sent.body.player_id,'target');assert.equal(sent.body.fee,300);
 assert.ok(normal.disabled&&guaranteed.disabled,'both choices lock while request is sent');
 Object.assign(quote,{note:'wonder',academy_year:2028,age:17,potential:96});
 await ctx.CareerUI.pages.market({source:'academy'},host,()=>true);
 assert.match(host.innerHTML,/2028届/);assert.match(host.innerHTML,/17岁/);assert.match(host.innerHTML,/潜力 96/);
 assert.match(host.innerHTML,/天才/);assert.match(host.innerHTML,/潜力不保证兑现/);
 Object.assign(quote,{seller_id:'rival',seller:'Rival',normal_fee:null});
 await ctx.CareerUI.pages.market({source:'academy'},host,()=>true);
 assert.match(host.innerHTML,/现役只接受买断/);assert.match(host.innerHTML,/Target/);
 quote.note='vet';
 await ctx.CareerUI.pages.market({source:'academy'},host,()=>true);
 assert.match(host.innerHTML,/没有符合条件/);
 console.log('Transfer UI: both prices, chance, failure fee, replacement and guaranteed command passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
