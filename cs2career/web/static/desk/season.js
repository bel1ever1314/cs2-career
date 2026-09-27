/* A whole-season board, not a second tournament popup. Route changes only read
 * data; every simulation step and mode change remains an explicit API command. */
(() => {
  let board=null, progress='', lastScore='', generation=0, playingScore=false, featured=null;
  const t=value=>window.CareerI18n?.t(value)||value;
  const field=(row,key)=>window.CareerI18n?.field(row,key)||row?.[key]||'';
  function modeCard(){
    const c=S.career||{},m=c.season_mode;
    if(!c.exists||c.over||!m?.can_choose||window.CareerAssist?.isActive?.())return '';
    if(m.phase==='start'&&m.choice_required===false)return '';
    const end=m.phase==='end';
    return `<section class="card season-mode" data-ui-key="season-mode:${S.year}"><h3>${end?'本赛季已结束 · 下一季怎么打？':'新赛季 · 选择本季节奏'}</h3><p class="hint">普通模式逐场安排；快速模式在同一屏自动播放本季比赛，无需滚动，比赛只在决赛询问。需要你选择的剧情、合同和 Major 休赛期仍会暂停。</p><div class="row"><button class="btn ${m.selected==='normal'?'primary':''}" data-season-mode="normal">${end?'下一季使用普通模式':'普通模式 · 自己安排'}</button><button class="btn ${m.selected==='quick'?'primary':''}" data-season-mode="quick">${end?'下一季使用快速模式':'快速模式 · 自动完成本季'}</button></div><p class="hint">快速模式的属性点在 Major 后统一分配；赛季中不反复询问是否切换模式。</p></section>`;
  }
  function bindMode(host){
    host.querySelectorAll('[data-season-mode]').forEach(button=>button.onclick=async()=>{
      host.querySelectorAll('[data-season-mode]').forEach(b=>b.disabled=true);
      try{
        const quick=button.dataset.seasonMode==='quick';
        const out=await post('/api/assist/season-mode',{quick_mode:quick,year:S.year,token:crypto.randomUUID()},{quiet:true});
        if(out.ok===false)return;
        reset();
        if(quick){CareerUI.go('season');await window.CareerAssist?.runQuick();}
        else CareerUI.go('home');
      }catch(error){toast(t('无法切换赛季模式：')+error.message,true);}
      finally{host.querySelectorAll('[data-season-mode]').forEach(b=>b.disabled=false);}
    });
  }
  function fallback(){
    const c=S.career||{},registered=new Set(c.registered||[]);
    return {year:S.year,date:S.date,events:(S.events||[]).map(e=>{
      const entered=(e.field||[]).includes(c.team_name)||registered.has(e.id);
      return {...e,participation:entered?'entered':e.status==='done'?'skipped':'unknown',own_matches:(e.matches||[]).filter(m=>m.team_a===c.team_name||m.team_b===c.team_name)};
    })};
  }
  function quickFocus(data){
    const events=data.events||[],mine=events.filter(e=>e.participation==='entered');
    const event=(featured&&events.find(e=>e.id===featured.event_id||(e.own_matches||[]).some(m=>m.id===featured.id)))||
      mine.find(e=>e.status==='live'&&(e.own_matches||[]).some(m=>!m.played))||
      mine.find(e=>e.status==='live')||mine.find(e=>e.status==='upcoming')||[...mine].reverse().find(e=>e.status==='done');
    const match=featured||event?.own_matches?.find(m=>!m.played)||event?.own_matches?.at(-1);
    const completed=events.flatMap(e=>(e.own_matches||[]).filter(m=>m.played).map(m=>({...m,event_name:e.name,date:m.date||e.end||e.start||''})))
      .sort((a,b)=>String(a.date).localeCompare(String(b.date)));
    const previous=[...completed].reverse().find(m=>m.id!==match?.id);
    const next=mine.find(e=>e.status==='upcoming'&&e.id!==event?.id);
    return {event,match,previous,next};
  }
  function quickHTML(data){
    const c=S.career||{},running=!!window.CareerAssist?.isActive?.(),mode=c.season_mode||{},w=c.story_timing;
    const {event,match,previous,next}=quickFocus(data),events=data.events||[];
    const finished=events.filter(e=>e.status==='done').length,percentage=events.length?Math.round(finished/events.length*100):0;
    const done=mode.phase==='end',chooser=modeCard();
    const summary=data.summary||{};
    const score=match?.series||(match?.played?'—':'VS');
    const card=(label,title,detail)=>`<section class="quick-mini"><small>${label}</small><b title="${esc(title)}">${esc(title)}</b><span>${esc(detail)}</span></section>`;
    return `<div class="quick-dashboard" data-ui-key="quick-dashboard">
      <header class="quick-header"><div><small>快速生涯</small><h2>${esc(data.year||S.year)} <span>赛季</span></h2></div><div class="quick-calendar"><b>${esc(data.date||S.date)}</b><span>${running?'自动推进中':done?'本赛季已结束':'已暂停'}</span></div><div class="quick-progress"><span>${finished} / ${events.length} <span>项赛事已结束</span></span><progress max="100" value="${percentage}">${percentage}%</progress></div></header>
      <div class="quick-body"><section class="quick-arena ${match?.report?'show-report':''} ${match?.report?window.CareerQuickResults?.outcome(match.winner,match.player_team)||'':window.CareerQuickResults?.mapOutcome(match,match?.map_index)||''}">
        ${chooser?`<div class="quick-mode-choice">${chooser}</div>`:`<div class="quick-event"><small data-quick-stage>${esc(t(match?.label||match?.stage||'本队赛程'))}</small><h2 data-quick-event title="${esc(event?.name||'')}">${esc(event?.name||'等待本队下一站')}</h2></div>
        <div class="quick-match"><strong data-quick-team-a data-no-i18n>${esc(match?.team_a||c.team_name||'—')}</strong><b data-quick-score data-no-i18n>${esc(score)}</b><strong data-quick-team-b data-no-i18n>${esc(match?.team_b||t('对手待定'))}</strong></div>
        <p class="quick-match-note">${match?.played||match?.map_index?'比分逐图揭晓 · 结果已保存':'无需逐项打开赛事，系统会自动切换到本队比赛。'}</p>
        <div data-quick-scorecard ${match?.report?'':'hidden'}>${match?.report?window.CareerQuickResults?.scorecard(match)||'':''}</div>
        ${w?.open&&!running?'<div class="quick-break"><b>Major 休赛期</b><span>处理剧情和属性点后继续</span><button class="btn sm" data-route="honours">查看个人成长</button></div>':''}`}
      </section><aside class="quick-recap">
        ${card('上一场',previous?`${previous.team_a} ${previous.series||'—'} ${previous.team_b}`:'暂无已完成比赛',previous?.event_name||'')}
        ${card('下一站',next?.name||'等待后续赛程',next?.start||next?.dates?.[0]||'')}
        <section class="quick-mini quick-record" data-quick-record>${window.CareerQuickResults?.recordHTML(data,match)||`<small>本季战绩</small><b>${summary.wins??'—'} <span>胜</span> / ${summary.losses??'—'} <span>负</span></b>`}</section>
      </aside></div>
      <footer class="quick-footer"><p data-season-status aria-live="polite">${esc(progress||'开始后自动切换比赛，无需滚动赛程。')}</p><div class="quick-controls">${running?'<button class="btn" data-stop-quick>暂停自动推进</button><button class="btn ghost" data-skip-quick-score hidden>跳过比分动画</button>':!done&&!chooser?`<button class="btn primary" data-continue-quick>${w?.open?'休赛期准备好了，继续本季':'继续模拟本季'}</button>`:''}<button class="btn ghost" data-route="home" ${running?'disabled':''}>返回生涯概览</button></div></footer>
    </div>`;
  }
  function html(data){
    if(S.career?.assist?.quick_mode)return quickHTML(data);
    const c=S.career||{},running=!!window.CareerAssist?.isActive?.(),m=c.season_mode||{},w=c.story_timing;
    const events=[...(data.events||[])].sort((a,b)=>(a.dates?.[0]||a.start||'').localeCompare(b.dates?.[0]||b.start||'')||String(a.id).localeCompare(String(b.id)));
    const finished=events.filter(e=>e.status==='done').length;
    let h=CareerUI.head('全年赛程',`${data.year||S.year} · ${data.date||S.date}`)+modeCard();
    h+=`<section class="card season-run"><div class="row"><b>${c.assist?.quick_mode?'快速模式':'普通模式'}</b><span class="hint">${finished} / ${events.length} <span>项赛事已结束</span></span>${running?'<button class="btn" data-stop-quick>暂停自动推进</button><button class="btn ghost" data-skip-quick-score hidden>跳过比分动画</button>':c.assist?.quick_mode&&m.phase!=='end'?`<button class="btn primary" data-continue-quick>${w?.open?'休赛期准备好了，继续本季':'继续模拟本季'}</button>`:''}<button class="btn ghost" data-route="home" ${running?'disabled':''}>返回生涯概览</button></div><p data-season-status aria-live="polite">${esc(progress||'全部赛事都在这里；未来参赛名单和对手只在确定后显示。')}</p>${lastScore?`<p class="season-latest-score">${esc(lastScore)}</p>`:''}<p class="hint">${c.assist?.quick_mode?'已完成结果实时保存。只在决赛、必要选择和 Major 休赛期暂停，整季结束后再选择下一季模式。':'这里可以浏览全季比赛。可在季初或季末选择快速模式。'}</p>${w?.open&&!running?`<div class="notice">Major 休赛期 · <span>积累的属性点可以使用</span> <button class="text-link" data-route="honours">查看个人成长</button></div>`:''}</section>`;
    if(!events.length)return h+'<p class="empty">本季没有已载入的赛事。</p>';
    let month='';h+='<div class="season-timeline">';
    for(const e of events){
      const dates=e.dates||[],start=e.start||dates[0]||'',end=e.end||dates[dates.length-1]||start,next=start.slice(0,7);
      if(next!==month){month=next;h+=`<h3 class="season-month" data-ui-key="month:${esc(month)}">${esc(month)}</h3>`;}
      const mine=e.participation==='entered', own=e.own_matches||[];
      const participation={entered:'本队参赛',invited:'邀请待处理',skipped:'本队未参加',unknown:'参赛待定'}[e.participation]||'参赛待定';
      h+=`<article class="card season-event ${mine?'mine':''} ${e.status==='live'?'live':''}" data-ui-key="season-event:${esc(e.id)}"><div class="season-event-head"><time>${esc(start.slice(5))}${end!==start?' — '+esc(end.slice(5)):''}</time><button class="text-link" data-open-event="${esc(e.id)}" ${running?'disabled':''}>${esc(e.name)}</button><span class="badge ${esc(e.class||'t2')}">${esc(e.class==='major'?'Major':String(e.class||'').toUpperCase())}</span><span class="badge ${esc(e.status)}">${esc(({done:'已结束',live:'进行中',upcoming:'未开始'})[e.status]||'未开始')}</span><span class="season-participation">${participation}</span></div>`;
      if(e.reason)h+=`<p class="hint">${esc(field(e,'reason'))}</p>`;
      if(e.champion)h+=`<p class="hint"><span>冠军</span> · <span data-no-i18n>${esc(e.champion)}</span></p>`;
      if(own.length)h+=`<div class="season-results">${own.map(x=>`<button class="season-match ${x.played?'played':'pending'}" data-open-match="${esc(x.id)}" ${running?'disabled':''}><small>${esc(t(x.label||x.stage||''))}</small><span data-no-i18n>${esc(x.team_a)} <b>${esc(x.series||(x.played?'—':'VS'))}</b> ${esc(x.team_b)}</span></button>`).join('')}</div>`;
      h+='</article>';
    }
    return h+'</div>';
  }
  function paint(host){
    // A board GET can finish while a saved score is being revealed. Keep its
    // data, but do not expose the final result or replace playback controls.
    if(playingScore)return;
    const data=board?.year===S.year&&board.date===S.date?board:fallback();
    CareerUI.paint(host,html(data));bindMode(host);
    const resume=host.querySelector('[data-continue-quick]'),stop=host.querySelector('[data-stop-quick]');
    if(resume)resume.onclick=()=>CareerAssist.runQuick(!!S.career?.story_timing?.open);
    if(stop)stop.onclick=()=>CareerAssist.stopQuick();
    const skip=host.querySelector('[data-skip-quick-score]');
    if(skip)skip.onclick=()=>CareerAssist.skipQuickScore();
  }
  async function refresh(host){
    const stamp=++generation;
    try{const out=await get('/api/assist/season-board');if(stamp!==generation||out.year!==S.year)return;board=out;if(host?.isConnected!==false)paint(host);}
    catch(error){if(stamp===generation&&!window.CareerAssist?.isActive?.())toast(t('赛季详情暂不可用，保留日历。'),true);}
  }
  function status(message,score,match){
    progress=message||'';if(score)lastScore=score;
    if(match!==undefined)featured=match;
    const host=document.getElementById('view-season'),line=host?.querySelector('[data-season-status]');
    if(line)line.textContent=t(progress);
    const quick=host?.querySelector('[data-quick-score]');
    if(quick){
      if(match){
        const write=(selector,value)=>{const node=host.querySelector(selector);if(node)node.textContent=value;};
        write('[data-quick-team-a]',match.team_a);write('[data-quick-team-b]',match.team_b);
        write('[data-quick-score]',match.series||'VS');
        const data=board?.year===S.year?board:fallback(),focus=quickFocus(data);
        write('[data-quick-event]',focus.event?.name||t('本队赛程'));
        write('[data-quick-stage]',match.best_of?'BO'+match.best_of:t('本队赛程'));
        resultView(host,match);
      }
      return;
    }
    if(score&&line){
      let node=host.querySelector('.season-latest-score');
      if(!node){node=document.createElement('p');node.className='season-latest-score';line.after(node);}
      node.textContent=score;
    }
  }
  function resultView(host,match){
    const results=window.CareerQuickResults;if(!results)return;
    const arena=host?.querySelector('.quick-arena'),card=host?.querySelector('[data-quick-scorecard]');
    const tone=match?.report?results.outcome(match.winner,match.player_team):results.mapOutcome(match,match?.map_index);
    const note=host?.querySelector('.quick-match-note');
    if(note&&!match?.report)note.textContent=tone?`${t(tone==='win'?'本图胜利':'本图失利')} · ${t('地图')} ${match.map_index}`:t('比分逐图揭晓 · 结果已保存');
    for(const name of ['win','loss'])arena?.classList.toggle(name,tone===name);
    arena?.classList.toggle('show-report',!!match?.report);
    if(card){card.hidden=!match?.report;card.innerHTML=match?.report?results.scorecard(match):'';}
    if(match?.report){
      const record=host.querySelector('[data-quick-record]');
      if(record)record.innerHTML=results.recordHTML(board?.year===S.year?board:fallback(),match);
    }
  }
  function showReport(match){
    featured={...match,report:true};
    const host=document.getElementById('view-season');
    resultView(host,featured);
    const skip=host?.querySelector('[data-skip-quick-score]');if(skip)skip.textContent=t('跳过战报等待');
  }
  function playback(host,value){playingScore=value;const button=host?.querySelector('[data-skip-quick-score]');if(button){button.hidden=!value;if(value)button.textContent=t('跳过比分动画');}}
  function reset(){board=null;progress='';lastScore='';generation++;playingScore=false;featured=null;}
  CareerUI.pages.season=(_route,host)=>{paint(host);return refresh(host);};
  window.CareerSeason={modeCard,bindMode,paint,refresh,status,reset,html,fallback,playback,quickFocus,showReport};
})();
