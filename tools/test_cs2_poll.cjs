/* Real-game responses must not switch the desktop back to legacy markup. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const src=fs.readFileSync('cs2career/web/static/app.js','utf8');
const code=src.slice(src.indexOf('function stopSeriesPoll()'),src.indexOf('/* ----------------------------------------------------------------- ranking */'));
const flush=()=>new Promise(r=>setImmediate(r));
async function scenario(result){
 let commits=0,draws=0,legacy=0;
 const ctx=vm.createContext({SERIES_POLL_GENERATION:0,SERIES_TIMER:null,CS2_POLL_ID:'',
  SERIES_RESULT:null,SERIES_BEST:null,SERIES_TRIED:'',SERIES_COMMIT_ERR:'',VIEW:'match',
  S:{your_match:{match:{id:'match-1',session:true}}},
  setInterval:()=>1,clearInterval:()=>{},get:async()=>result,
  post:async()=>{commits++;return {ok:true};},render:()=>draws++,renderMatch:()=>legacy++});
 vm.runInContext(code,ctx);ctx.startSeriesPoll('match-1');await flush();
 return {ctx,commits,draws,legacy};
}
(async()=>{
 let r=await scenario({status:'live',ct_score:13,t_score:12,complete:true,map:'mirage'});
 assert.equal(r.commits,0,'13 points alone must not commit an unfinished map');
 assert.equal(r.draws,1);assert.equal(r.legacy,0);
 r=await scenario({status:'finished',ct_score:13,t_score:8,complete:false,ended_at:'end',validation_error:'missing player'});
 assert.equal(r.commits,0,'incomplete ten-player results must not auto-commit');
 r=await scenario({status:'finished',ct_score:13,t_score:8,complete:true,ended_at:'end'});
 assert.equal(r.commits,1);
 r.ctx.S.your_match=null;r.ctx.ensureCs2AutoIngest();assert.equal(r.ctx.SERIES_TIMER,null);
 const page=fs.readFileSync('cs2career/web/static/desk/competitions.js','utf8');
 assert.ok(page.includes("SERIES_CS2=await get('/api/cs2/status')"));
 console.log('CS2 desktop: actual status, terminal-only commit, complete roster, modern redraw and polling stop passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
