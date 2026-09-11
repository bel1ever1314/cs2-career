/* Convenience controls and a cancellable, one-command-at-a-time event viewer.
 * No unattended timer ever answers a story. Server guards are authoritative. */
(() => {
 const levels={major:'Major',premier:'Premier 顶级大赛',t1:'T1',t2:'T2',cct:'CCT',qual:'预选赛 / RMR'};
 let active=false, pausedEvent=null, session=null;
 const settings=()=>S?.career?.assist||{};
 function mailPanel(){
   const rules=settings().invites||{};
   return `<details class="card assist-mail"><summary>邀请自动处理 · 按赛事等级设置</summary><p class="hint">只处理本队赛事邀请，不处理转会合同或剧情。保存后立即应用于当前未处理邀请；已有决定不追改。</p><div class="assist-rules">${Object.entries(levels).map(([key,label])=>`<label>${esc(label)}<select data-invite-rule="${key}">${[['manual','手动处理'],['accept','自动接受'],['decline','自动拒绝']].map(([value,text])=>`<option value="${value}" ${(rules[key]||'manual')===value?'selected':''}>${text}</option>`).join('')}</select></label>`).join('')}</div><button class="btn" data-save-invites>保存邀请规则</button></details>`;
 }
 function bindMail(root){
   const b=root.querySelector('[data-save-invites]');if(!b)return;
   b.onclick=async()=>{b.disabled=true;try{await post('/api/assist/settings',{invites:Object.fromEntries([...root.querySelectorAll('[data-invite-rule]')].map(s=>[s.dataset.inviteRule,s.value]))});}finally{b.disabled=false;}};
 }
 function pointPanel(){
   const mode=settings().points||'off';
   return `<div class="assist-points"><label>自动加点 <select data-point-direction>${[['off','关闭 · 手动加点'],['balanced','均衡发展 · 优先最低维度'],...Object.entries(axisLabels())].map(([value,text])=>`<option value="${esc(value)}" ${mode===value?'selected':''}>${esc(text)}</option>`).join('')}</select></label><button class="btn sm" data-save-points>应用方向</button><p class="hint">应用后立即投入现有点数，此后新获得的点数也自动投入。加满即停止，剩余点数保留。</p>${settings().notice?`<p class="notice">${esc(settings().notice)}</p>`:''}</div>`;
 }
 function bindPoints(root){root.querySelectorAll('[data-save-points]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await post('/api/assist/settings',{points:b.closest('.assist-points').querySelector('select').value});}finally{b.disabled=false;}});}
 const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
 function teamPath(ev,name){
   const matches=(ev.matches||[]).filter(m=>m.team_a===name||m.team_b===name);
   const ids=new Set(matches.map(m=>m.id));
   return {...ev,matches,links:(ev.links||[]).filter(l=>l.team===name&&ids.has(l.source)&&ids.has(l.target))};
 }
 function pathView(host,name){
   let layout='',controls=null,lastFocus='';
   const write=(node,text)=>{if(node&&node.textContent!==text)node.textContent=text;};
   return (event,focus)=>{
     const ev=teamPath(event,name);
     // Results are not structural: keep DOM nodes, image resources, zoom and
     // scroll position intact when only a saved score/winner has changed.
     const signature=JSON.stringify([ev.matches.map(m=>[m.id,m.stage,m.team_a,m.team_b,m.label,m.date,m.best_of,m.meta]),ev.links]);
     if(signature!==layout){
       const saved=controls?.snapshot();
       CareerUI.paint(host,ev.matches.length?CareerUI.drawTournamentGraph(ev):'<p class="empty">本队对阵尚未生成，正在等待当前阶段结束。这里只显示本队赛程。</p>');
       controls=CareerUI.bindTournamentGraph(host,saved);layout=signature;
     }
     const nodes=[...host.querySelectorAll('[data-node]')];
     for(const m of ev.matches){
       const node=nodes.find(n=>n.dataset.node===m.id);if(!node)continue;
       write(node.querySelector('.node-title span'),m.played?(m.series||'已结束'):'BO'+m.best_of);
       node.querySelectorAll('.node-team').forEach((row,i)=>{
         const won=[m.team_a,m.team_b][i]===m.winner;
         row.classList.toggle('winner',won);write(row.querySelector(':scope > span:last-child'),won?'✓':'');
       });
     }
     if(focus&&focus!==lastFocus){
       const node=nodes.find(n=>n.dataset.node===focus||n.dataset.node.endsWith('::'+focus)),viewport=host.querySelector('.graph-viewport');
       if(node&&viewport){viewport.scrollLeft=Math.max(0,node.parentElement.offsetLeft*(controls?.snapshot()?.zoom||1)-100);lastFocus=focus;}
     }
   };
 }
 function closeSession(navigate=true){
   if(!session)return;
   const {host,shell,oldInert,eid}=session;
   host.remove();if(shell)shell.inert=oldInert;session=null;pausedEvent=null;
   if(navigate)CareerUI.go('event',{key:eid,tab:'graph'});
   ensureCs2AutoIngest();
 }
 async function run(eid){
   if(active||!eid)return;
   if(STORY_BUSY){pausedEvent=eid;toast('先处理当前事件，处理完后继续模拟。',false);return;}
   active=true;pausedEvent=null;stopSeriesPoll();
   if(PLAY_TIMER){clearInterval(PLAY_TIMER);PLAY_TIMER=null;}
   if(session&&session.eid!==eid)closeSession(false);
   if(!session){
   const host=document.createElement('div');host.className='watch-overlay event-auto-overlay';host.setAttribute('role','dialog');host.setAttribute('aria-modal','true');host.tabIndex=-1;
   host.innerHTML='<section class="event-auto-card"><div class="watch-top"><h2>本队赛事之路</h2><button class="btn" data-stop-auto>停止自动模拟</button></div><p data-auto-status>正在读取赛事…</p><div class="event-auto-score" data-auto-score></div><div data-auto-graph></div><p class="hint">只显示本队比赛与直接对手 · 每图揭晓大比分 · 已保存结果不会重抽</p></section>';
   document.body.appendChild(host);host.focus();const shell=document.querySelector('.app'), oldInert=shell?.inert;if(shell)shell.inert=true;
   session={eid,host,shell,oldInert,updatePath:pathView(host.querySelector('[data-auto-graph]'),myTeamName())};
   }
   const {host,updatePath}=session;host.className='watch-overlay event-auto-overlay';host.inert=false;
   let stopped=false,ev=null,focusMatch='';
   host.querySelector('[data-stop-auto]').onclick=()=>{stopped=true;pausedEvent=null;if(!active){closeSession();return;}host.querySelector('[data-auto-status]').textContent='将在当前处理完成后停止，已完成结果会保留。';};
   const draw=()=>updatePath(ev,focusMatch);
   try{
     ev=await get('/api/event?id='+encodeURIComponent(eid));draw();
     while(!stopped){
       const token=crypto.randomUUID();
       const out=await post('/api/assist/tournament',{event_id:eid,token,revision:settings().step_counter||0},{render:false,beforeApply:async data=>{
         const m=data.auto_step?.match;if(!m)return;
         focusMatch=m.id;
         let a=0,b=0;
         const node=ev.matches.find(x=>x.id===m.id||x.id.endsWith('::'+m.id));
         for(let i=0;i<m.winners.length;i++){
           if(m.winners[i]===m.team_a)a++;else if(m.winners[i]===m.team_b)b++;
           if(i<m.start)continue;
           host.querySelector('[data-auto-score]').textContent=`${m.team_a}  ${a} : ${b}  ${m.team_b}`;
           host.querySelector('[data-auto-status]').textContent=`第${i+1}图结束 · BO${m.best_of}`;
           if(node){node.series=`${a} : ${b}`;node.played=true;node.winner=null;draw();}
           if(!stopped)await wait(850);
         }
       }});
       if(out.ok===false){stopped=true;break;}
       const result=out.auto_step;
       if(!result)throw Error('缺少自动模拟状态');
       if(['paused','decision','done'].includes(result.status)||(out.stories||out.state?.career?.stories||[]).length){
         const stories=out.stories||out.state?.career?.stories||[];
         // Only keep a suspended viewer when an actual decision can resume it.
         // Non-story blockers must return to the page where they can be fixed.
         pausedEvent=!stopped&&result.status!=='done'&&stories.length?eid:null;
         host.querySelector('[data-auto-status]').textContent=result.msg||'有新事件，模拟已暂停。';
         toast(result.msg||'有新事件，模拟已暂停。',false);break;
       }
       ev=await get('/api/event?id='+encodeURIComponent(eid));draw();
       host.querySelector('[data-auto-status]').textContent=result.msg||'准备下一轮…';
       if(!stopped)await wait(300);
     }
   }catch(err){toast('自动模拟已停止：'+err.message+'。已保存比赛不重算，可重新打开赛事确认。',true);pausedEvent=null;}
   finally{
     active=false;
     if(pausedEvent){host.className='watch-overlay event-auto-overlay awaiting-story';host.inert=true;}
     else closeSession();
   }
 }
 function afterStory(row,choice){
   if(row.when==='tournament_decision'){
     if(choice==='manual'){pausedEvent=null;closeSession(false);CareerUI.match(row.match_id);return;}
     if(choice==='later'){pausedEvent=null;closeSession();return;}
     if(choice==='simulate')pausedEvent=row.event_id;
   }
   if(pausedEvent && !(S.career?.stories||[]).length){const eid=pausedEvent;pausedEvent=null;setTimeout(()=>run(eid),0);}
 }
 window.CareerAssist={mailPanel,bindMail,pointPanel,bindPoints,run,afterStory,teamPath,pathView,isOpen:()=>!!session};
})();
