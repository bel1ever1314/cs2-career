/* Run with node tests/test_assistance_quick.js. The real UI controller, mocked
 * DOM/network: no player save is read and no simulation endpoint is contacted. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const code=fs.readFileSync(path.join(__dirname,'..','cs2career','web','static','desk','assistance.js'),'utf8');
function harness(quick=true,results=null){
  const calls=[],timers=[],navigation=[],shell={inert:false},updates=[],delays=[],playback=[],reports=[];
  function element(){const children=new Map();return {className:'',inert:false,innerHTML:'',textContent:'',
    setAttribute(){},focus(){},remove(){this.removed=true;},querySelectorAll(){return [];},
    querySelector(key){if(!children.has(key))children.set(key,element());return children.get(key);}};}
  const row={id:'decision',when:'tournament_decision',event_id:'major-1',match_id:'final-1'},seasonHost=element();
  const context={S:{date:'2026-06-20',career:{assist:{quick_mode:quick,step_counter:4},stories:[]}},STORY_BUSY:false,PLAY_TIMER:null,
    document:{createElement:element,body:{appendChild(){}},querySelector:()=>shell,querySelectorAll:()=>[],getElementById:()=>seasonHost},crypto:{randomUUID:()=> 'test-token'},
    CareerUI:{go:(...args)=>navigation.push(args),match:id=>navigation.push(['match',id]),paint(){},drawTournamentGraph(){return '';},bindTournamentGraph:()=>({snapshot:()=>({zoom:1})})},
    CareerSeason:{status:(message,score,match)=>updates.push({message,score,match}),showReport:match=>reports.push(match),paint(){},refresh:async()=>{},playback:(_host,value)=>playback.push(value)},
    post:async(url,body,options)=>{calls.push({url,body,options});const out=results?results.shift():{ok:true,auto_step:{status:'decision',msg:'Decision required'},stories:[row]};if(!out)throw Error('advanced beyond expected season boundary');if(out.ok!==false&&options?.beforeApply)await options.beforeApply(out);context.S.career.stories=out.stories||[];return out;},
    get:async()=>({matches:[],links:[]}),toast(){},stopSeriesPoll(){},ensureCs2AutoIngest(){},myTeamName:()=> 'My Team',
    setTimeout:(fn,delay)=>{delays.push(delay);if(delay>0){fn();return 0;}timers.push({fn,delay});return timers.length;},clearTimeout(){},clearInterval(){},esc:String,render(){}};
  context.window=context;vm.runInNewContext(code,context);
  return {api:context.CareerAssist,context,calls,timers,navigation,shell,row,updates,seasonHost,delays,playback,reports};
}
(async()=>{
  const quick=harness();
  await quick.api.runQuick();
  assert.equal(quick.calls.length,1);assert.equal(quick.calls[0].url,'/api/assist/quick');
  assert.equal(quick.calls[0].body.revision,4);
  assert.equal(quick.api.isOpen(),false,'Quick decisions release the inline season runner');
  assert.equal(quick.shell.inert,false,'Main UI must be usable to choose the story');
  assert.equal(quick.navigation.at(-1)[0],'season');
  assert.equal(quick.seasonHost.removed,undefined,'Closing a run must not remove the season page');
  assert.equal(quick.calls[0].options.quiet,true,'Quick steps must not emit hundreds of toast popups');
  quick.context.S.career.stories=[];quick.api.afterStory(quick.row,'simulate');
  assert.equal(quick.timers.length,1,'After an explicit final decision, resume the same whole-season runner');
  assert.equal(quick.calls.length,1,'A future scheduled continuation has not mutated the game yet');

  const match={id:'m',team_a:'A',team_b:'B',played:true,best_of:3,start:0,winners:['A','B','A']};
  const slow=harness(true,[{ok:true,auto_step:{status:'played',match}}, {ok:true,auto_step:{status:'season_done',msg:'Done'}}]);
  await slow.api.runQuick();
  assert.deepEqual(slow.updates.filter(x=>x.score).slice(0,4).map(x=>x.score),['A 0 : 0 B','A 1 : 0 B','A 1 : 1 B','A 2 : 1 B']);
  assert.deepEqual(slow.delays.filter(x=>x>=1000),[1200,1200,1200,1800,...Array(6).fill(1000)]);
  assert.equal(slow.reports.length,1);assert.equal(slow.reports[0].series,'2 : 1');
  assert.deepEqual(slow.updates.filter(x=>x.match).map(x=>x.match.map_index),[0,1,2,3]);
  assert.deepEqual(slow.playback,[true,false]);assert.equal(slow.calls.length,2);
  const partial=harness(true,[{ok:true,auto_step:{status:'season_done',match:{...match,start:1}}}]);
  await partial.api.runQuick();
  assert.deepEqual(partial.updates.filter(x=>x.score).slice(0,3).map(x=>x.score),['A 1 : 0 B','A 1 : 1 B','A 2 : 1 B']);
  assert.deepEqual(partial.delays,[1200,1200,1800,...Array(6).fill(1000)],'A resumed series never replays already revealed maps');

  for(const action of ['skip','stop','leave']){
    const reportWait=harness(true,[{ok:true,auto_step:{status:'played',match},stories:[{id:'award'}]}]);
    let held,cleared=false;
    reportWait.context.setTimeout=(fn,delay)=>{if(delay===1000){held=fn;return 77;}fn();return 0;};
    reportWait.context.clearTimeout=id=>{if(id===77)cleared=true;};
    const run=reportWait.api.runQuick();
    for(let n=0;n<30&&!held;n++)await Promise.resolve();
    assert.equal(reportWait.reports.length,1);assert.equal(typeof held,'function');
    assert.equal(reportWait.context.S.career.stories.length,0,'Awards follow the scorecard, not cover it');
    if(action==='skip')reportWait.api.skipQuickScore();
    else if(action==='stop')reportWait.api.stopQuick();
    else reportWait.api.beforeNavigate('home');
    await run;assert.ok(cleared);assert.equal(reportWait.calls.length,1);
    assert.equal(reportWait.context.S.career.stories[0].id,'award');
  }

  for(const action of ['skip','stop','leave']){
    const replay=harness(true,[{ok:true,auto_step:{status:'played',match},stories:[{id:'award',kind:'awards'}]}]);
    let release,cleared=false;
    replay.context.setTimeout=(fn,delay)=>{assert.equal(delay,1200);release=fn;return 7;};
    replay.context.clearTimeout=id=>{assert.equal(id,7);cleared=true;};
    const running=replay.api.runQuick();
    for(let n=0;n<8&&!release;n++)await Promise.resolve();
    assert.equal(typeof release,'function');
    assert.equal(replay.context.S.career.stories.length,0,'Do not show awards before score playback');
    if(action==='skip')replay.api.skipQuickScore();
    else if(action==='stop')replay.api.stopQuick();
    else replay.api.beforeNavigate('squad');
    await running;
    assert.equal(cleared,true,'Skip/stop releases the current timer immediately');
    assert.equal(replay.calls.length,1,'Playback must never resimulate a result or auto-answer an award');
    assert.equal(replay.context.S.career.stories[0].id,'award');
    assert.equal(replay.updates.filter(x=>x.score).at(-1).score,'A 2 : 1 B');
    assert.deepEqual(replay.playback,[true,false]);assert.equal(replay.api.isActive(),false);
  }

  const offseason=harness();offseason.context.S.career.story_timing={open:true,window:{key:'major-2026-a'}};
  await offseason.api.runQuick(true);
  assert.equal(offseason.calls[0].body.resume_break,true);assert.equal(offseason.calls[0].body.break_key,'major-2026-a');
  offseason.context.S.career.stories=[];offseason.api.afterStory(offseason.row,'later');
  assert.equal(offseason.timers.length,0);

  const full=harness(true,[{ok:true,auto_step:{status:'progress',msg:'Next stage'}},{ok:true,auto_step:{status:'season_done',year:2026,msg:'Season completed'}}]);
  await full.api.runQuick();assert.equal(full.calls.length,2,'The whole-season loop must stop before rolling into another season');
  assert.equal(full.api.isActive(),false);
  assert.ok(full.updates.some(x=>x.message.includes('Season completed')));
  assert.equal(full.timers.length,0);

  const leaving=harness(true,[{ok:true,auto_step:{status:'progress',msg:'Saved current step'}}]);
  const originalPost=leaving.context.post;
  leaving.context.post=async(...args)=>{const out=await originalPost(...args);leaving.api.beforeNavigate('squad');return out;};
  await leaving.api.runQuick();
  assert.equal(leaving.calls.length,1,'Leaving the season page may finish one in-flight save, but must not advance behind another page');
  assert.equal(leaving.api.isActive(),false);assert.equal(leaving.api.isOpen(),false);
  assert.equal(leaving.timers.length,0,'Navigation cancellation must not enqueue an automatic restart');

  // A decision modal is displayed by post() before the optional board GET.
  // Hold that GET open while the user answers; the answer must not be lost.
  for(const choice of ['simulate','manual','later','simulate_then_leave']){
    const fastAnswer=harness(true,[{ok:true,auto_step:{status:'decision',msg:'Final decision'},stories:[{when:'tournament_decision',event_id:'major-1',match_id:'final-1'}]},{ok:true,auto_step:{status:'season_done',msg:'Done'}}]);
    let releaseRefresh,reads=0;
    fastAnswer.context.CareerSeason.refresh=()=>++reads===1?new Promise(resolve=>{releaseRefresh=resolve;}):Promise.resolve();
    fastAnswer.context.setTimeout=(fn,delay)=>{fastAnswer.timers.push({fn,delay});return fastAnswer.timers.length;};
    const firstRun=fastAnswer.api.runQuick();
    for(let n=0;n<8&&!releaseRefresh;n++)await Promise.resolve();
    assert.equal(typeof releaseRefresh,'function','Test must hold the actual asynchronous refresh boundary');
    fastAnswer.context.S.career.stories=[];
    fastAnswer.api.afterStory(fastAnswer.row,choice==='simulate_then_leave'?'simulate':choice);
    if(choice.startsWith('simulate')){
      assert.equal(fastAnswer.timers.length,1,'The quick final answer is retained before the GET resolves');
      fastAnswer.timers.shift().fn();
      assert.equal(fastAnswer.calls.length,1,'Do not start a second runner while the first still owns control');
      assert.equal(fastAnswer.timers.length,1,'Exactly one idle retry is scheduled');
      if(choice==='simulate_then_leave')fastAnswer.api.beforeNavigate('squad');
    }else assert.equal(fastAnswer.timers.length,0,'Manual and later must never schedule automatic continuation');
    releaseRefresh();await firstRun;
    if(choice==='simulate'){
      fastAnswer.timers.shift().fn();
      for(let n=0;n<12&&fastAnswer.api.isActive();n++)await Promise.resolve();
      assert.equal(fastAnswer.calls.length,2,'Resume the whole-season API exactly once after the decision');
      assert.equal(fastAnswer.calls[1].url,'/api/assist/quick');
      assert.equal(fastAnswer.timers.length,0);assert.equal(fastAnswer.api.isActive(),false);
    }else{
      if(choice==='simulate_then_leave')fastAnswer.timers.shift().fn();
      assert.equal(fastAnswer.calls.length,1);assert.equal(fastAnswer.timers.length,0);
      assert.equal(fastAnswer.api.isActive(),false);
    }
  }

  const explicitViewer=harness();await explicitViewer.api.run('major-1');
  assert.equal(explicitViewer.api.isOpen(),true,'A real tournament viewer stays suspended for its decision');
  explicitViewer.context.S.career.stories=[];explicitViewer.api.afterStory(explicitViewer.row,'simulate');
  assert.equal(explicitViewer.timers.length,1,'An explicitly opened matching tournament viewer may resume');

  const normal=harness(false);normal.api.afterStory(normal.row,'simulate');
  assert.equal(normal.timers.length,1,'Preserve the existing normal-mode tournament choice');

  const manual=harness();manual.api.afterStory(manual.row,'manual');
  assert.equal(manual.navigation.at(-1)[0],'match');assert.equal(manual.navigation.at(-1)[1],'final-1');
  assert.equal(manual.timers.length,0);

  const disabled=harness(false);await disabled.api.runQuick();assert.equal(disabled.calls.length,0);
  assert.equal(disabled.navigation.at(-1)[0],'season');
  assert.ok(!disabled.api.mailPanel().includes('data-quick-mode'),'Mailbox must not contain a quick-mode switch');
  const blocked=harness();blocked.context.STORY_BUSY=true;await blocked.api.runQuick();assert.equal(blocked.calls.length,0);
  console.log('PASS: inline whole-season board, season boundary, explicit final continuation, no per-step popups, no mailbox mode switch, offseason key, ordinary tournament/manual compatibility.');
})().catch(error=>{console.error(error);process.exitCode=1;});
