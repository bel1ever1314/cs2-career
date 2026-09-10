/* Tournament graph and box scores consume saved engine data, not UI forecasts. */
(() => {
 const ui=CareerUI;
 function stats(lines){
   if(!lines?.length)return ui.empty('没有保存这支队伍的选手战绩。');
   return `<div class="table-scroll"><table class="box-score"><thead><tr><th>选手</th><th>K</th><th>D</th><th>A</th><th>伤害</th><th>ADR</th><th>KAST</th><th>首杀/首死</th><th>Rating</th></tr></thead><tbody>${[...lines].sort((a,b)=>(b.rating||0)-(a.rating||0)).map(p=>`<tr class="${p.name===S.career?.player_name?'me':''}"><td>${ui.link('player',p.resolved_player_id||p.player_id||p.name,p.name)}</td><td>${ui.num(p.k)}</td><td>${ui.num(p.d)}</td><td>${ui.num(p.a)}</td><td>${ui.num(p.damage)}</td><td>${ui.num(p.adr,1)}</td><td>${p.kast==null?'—':ui.num(p.kast*100,1)+'%'}</td><td>${ui.num(p.opening_kills)} / ${ui.num(p.opening_deaths)}</td><td class="rating">${ui.num(p.rating,2)}</td></tr>`).join('')}</tbody></table></div>`;
 }
 function rounds(mp){
   if(!mp.events_available)return ui.empty('这张地图没有保存逐回合事件；不会根据比分伪造回合过程。');
   let a=0,b=0;const m=DETAIL.match;
   return `<div class="round-strip">${mp.round_history.map(r=>{
     if(r.winner===m.team_a)a++;else if(r.winner===m.team_b)b++;
     return `<details class="round ${r.winner===m.team_a?'side-a':'side-b'}"><summary title="${esc(r.winner||'胜者未知')}"><small>R${r.number}</small><b>${a}:${b}</b></summary><div class="round-pop"><b>第${r.number}回合 · ${esc(r.winner||'未知')} 获胜</b>${r.events.length?r.events.map(e=>`<p>${esc(e.type==='kill'?`${e.killer||e.killer_name||'世界'} → ${e.victim||e.victim_name||'未知'}${e.assister?' · 助攻 '+e.assister:''}`:e.type==='hurt'?`${e.attacker||'世界'} → ${e.victim||'未知'} · ${e.damage||0}伤害`:e.type)}</p>`).join(''):'<p>此回合未保存详细事件。</p>'}</div></details>`;
   }).join('')}</div><p class="hint">橙色：${esc(m.team_a)} · 蓝色：${esc(m.team_b)}。点击回合展开已保存事件。</p>`;
 }
 ui.pages.match=async(r,host,active)=>{
   const detail=await get('/api/match?id='+encodeURIComponent(r.key));if(!active())return;
   DETAIL=detail;MATCH=r.key;const m=detail.match,ev=detail.event,maps=m.maps||[], tab=r.tab||'all';
   if(!m.played&&detail.yours&&!S.design_preview&&!S.playtest){
     try {SERIES_CS2=await get('/api/cs2/status');} catch {SERIES_CS2={ready:false};}
     if(!active())return;
   }
   let h=ui.head(ev.name,`${m.label||m.stage} · BO${m.best_of} · ${m.date||''}`)+`<div class="match-banner"><div>${crest(m.team_a,50)}${ui.link('team',m.team_a,m.team_a)}</div><strong>${esc(m.series||'VS')}</strong><div>${ui.link('team',m.team_b,m.team_b)}${crest(m.team_b,50)}</div></div><div class="filterbar">${ui.link('event',ev.id,'查看赛事晋级路径 →')}<span class="hint">${m.played?'比赛已结束':maps.length?'系列赛进行中':'赛前资料'}</span></div>`;
   if(m.veto?.steps?.length)h+=`<div class="veto">${m.veto.steps.map(v=>`<span class="step ${esc(v.action)}"><small>${esc(v.action.toUpperCase())}</small><b>${mapName(v.map)}</b><span>${esc(v.team||'决胜图')}</span></span>`).join('')}</div>`;
   h+=ui.tabs([['all','全场'],...maps.map((mp,i)=>[String(i),'第'+(i+1)+'图 · '+mapName(mp.map)+' '+mp.score])],tab);
   if(!maps.length)h+=`<div class="notice">${m.team_b==='BYE'?'本场轮空，没有十人战绩。':'本场尚未保存地图战绩。未开赛或回传不完整时，不能把缺失统计补成0。'}</div>`;
   else if(tab==='all'){
     if(!m.data_complete)h+='<div class="notice">部分地图缺少完整十人战绩，以下仅汇总已保存的数据。</div>';
     for(const tm of [m.team_a,m.team_b])h+=`<div class="card pad0"><h3>${ui.link('team',tm,tm)} <small class="hint">全场汇总</small></h3>${stats(m.totals.filter(p=>p.team===tm))}</div>`;
   }else{
     const mp=maps[Number(tab)];
     if(mp){h+=`<div class="filterbar"><h3>${mapName(mp.map)} · ${esc(mp.score)}</h3><span class="badge">${mp.source==='cs2'?'CS2 实战':'模拟比赛'}</span></div>`;
       if(!mp.data_complete)h+='<div class="notice">历史记录不完整。保留原数据，不自动补人。</div>';
       for(const tm of [m.team_a,m.team_b])h+=`<div class="card pad0"><h3>${ui.link('team',tm,tm)}</h3>${stats((mp.players||{})[tm])}</div>`;
       h+=`<div class="card"><h3>逐回合比分与事件</h3>${rounds(mp)}</div>`;}
   }
   if(!m.played&&detail.yours&&!S.design_preview)h+=renderLivePanel(m);
   host.innerHTML=h;
   host.querySelectorAll('.round').forEach(rd=>rd.ontoggle=()=>{
     if(!rd.open)return;
     const p=rd.querySelector('.round-pop'),rect=rd.getBoundingClientRect();
     p.style.position='fixed';p.style.left=Math.max(8,Math.min(innerWidth-330,rect.left))+'px';
     p.style.top=Math.max(90,rect.top-310)+'px';
   });
   if(!m.played&&detail.yours&&!S.design_preview)bindLivePanel(m);
 };
 function node(m){return `<article class="bracket-node ${m.team_a===myTeamName()||m.team_b===myTeamName()?'mine':''}" data-node="${esc(m.id)}"><button class="node-title" data-open-match="${esc(m.id)}">${esc(m.label||m.stage)} <span>${m.played?esc(m.series||'已结束'):'BO'+m.best_of}</span></button>${[m.team_a,m.team_b].map(tm=>`<div class="node-team ${tm===m.winner?'winner':''}">${tm==='BYE'?'轮空':crest(tm,20)+ui.link('team',tm,tm)}<span>${tm===m.winner?'✓':''}</span></div>`).join('')}<small>${esc(m.date||'')} ${m.meta?.record?'· '+esc(m.meta.record):''}</small></article>`;}
 function drawGraph(ev){
   const stages=[...new Set(ev.matches.map(m=>m.stage))], positions={},counts={};
   stages.forEach((s,i)=>{const rows=ev.matches.filter(m=>m.stage===s);counts[s]=rows.length;let previousY=-98;rows.forEach((m,j)=>{
     const incoming=(ev.links||[]).filter(l=>l.target===m.id&&positions[l.source]);
     const playoff=['R16','QF','SF','GF'].includes(s);
     const center=incoming.length?incoming.reduce((n,l)=>n+positions[l.source].y,0)/incoming.length:0;
     const desiredY=playoff&&incoming.length?Math.max(50+j*148,center):50+j*148;
     // Cross-seeded playoffs can have reversed parent centres. Always reserve
     // one full card row so adjacent matches never overlap after scaling.
     const y=Math.max(previousY+148,desiredY);previousY=y;
     positions[m.id]={x:20+i*320,y};
   });});
   const width=Math.max(600,stages.length*320+20),height=Math.max(340,...Object.values(positions).map(p=>p.y+165));
   let h=`<div class="graph-tools"><button class="btn sm" data-zoom="-">−</button><button class="btn sm" data-zoom="+">＋</button><button class="btn sm" data-zoom="fit">适应窗口</button><button class="btn sm" id="graph-mine">定位我的战队</button><span class="hint">拖动空白平移 · 点击比赛标题看战报 · 虚线为败者去向</span></div><div class="graph-viewport"><div class="graph-space" style="width:${width}px;height:${height}px"><div class="graph-board" style="width:${width}px;height:${height}px"><svg class="bracket-lines" width="${width}" height="${height}" aria-hidden="true">`;
   for(const link of ev.links||[]){const a=positions[link.source],b=positions[link.target];if(!a||!b)continue;const x=a.x+280,y=a.y+70,x2=b.x,y2=b.y+70;h+=`<path d="M${x} ${y} H${(x+x2)/2} V${y2} H${x2}" fill="none" stroke="${link.outcome==='loser'?'#686f80':'#c68458'}" stroke-width="2" ${link.outcome==='loser'?'stroke-dasharray="5 5"':''}/>`;}
   h+='</svg>'+stages.map((s,i)=>`<h3 class="graph-stage" style="left:${20+i*320}px">${esc({QF:'四分之一决赛',SF:'半决赛',GF:'决赛',G1:'小组首轮',G2:'胜者 / 淘汰赛',G3:'小组决胜局'}[s]||s)}</h3>`).join('');
   for(const m of ev.matches){const p=positions[m.id];h+=`<div class="graph-position" style="left:${p.x}px;top:${p.y}px">${node(m)}</div>`;}
   return h+'</div></div></div><p class="hint">只展示已生成对阵；尚未确定的下一阶段将在引擎配对后出现。瑞士轮连线表示实际参赛路径，不预设未来对手。</p>';
 }
 function graphControls(host){
   const viewport=host.querySelector('.graph-viewport'),board=host.querySelector('.graph-board'),space=host.querySelector('.graph-space');if(!board)return;
   let zoom=1,drag=null;const w=board.offsetWidth,h=board.offsetHeight;
   const apply=()=>{board.style.transform=`scale(${zoom})`;space.style.width=w*zoom+'px';space.style.height=h*zoom+'px';};
   host.querySelectorAll('[data-zoom]').forEach(b=>b.onclick=()=>{zoom=b.dataset.zoom==='fit'?Math.min(1,viewport.clientWidth/w,viewport.clientHeight/h):Math.max(.35,Math.min(1.6,zoom+(b.dataset.zoom==='+'?.15:-.15)));apply();});
   $('graph-mine').onclick=()=>{const m=board.querySelector('.mine');if(m){const p=m.parentElement;viewport.scrollTo({left:p.offsetLeft*zoom-20,top:p.offsetTop*zoom-40,behavior:'smooth'});}else toast('你没有参加这个赛事。',false);};
   viewport.onpointerdown=e=>{if(e.target.closest('button'))return;drag={x:e.clientX,y:e.clientY,left:viewport.scrollLeft,top:viewport.scrollTop};viewport.setPointerCapture(e.pointerId);};
   viewport.onpointermove=e=>{if(drag){viewport.scrollLeft=drag.left-(e.clientX-drag.x);viewport.scrollTop=drag.top-(e.clientY-drag.y);}};
   viewport.onpointerup=viewport.onpointercancel=()=>drag=null;
 }
 ui.pages.event=async(r,host,active)=>{
   const ev=await get('/api/event?id='+encodeURIComponent(r.key||FOCUS));if(!active())return;
   const directory=await get('/api/events');if(!active())return;
   const tab=r.tab||'graph';
   let h=ui.head(ev.name,`${(ev.dates||[]).join(' / ')} · ${FORMAT[ev.resolved_format||ev.format]||ev.format||'历史赛事'} · ${STATUS[ev.status]||'已结束'} · 奖金 ${money(ev.prize||0)}`);
   if(Array.isArray(directory))h+=`<div class="filterbar"><label>本季与历史赛事 <select id="event-directory">${[...directory].sort((a,b)=>(b.dates?.[0]||'').localeCompare(a.dates?.[0]||'')).map(e=>`<option value="${esc(e.id)}" ${e.id===ev.id?'selected':''}>${esc(e.dates?.[0]||'日期未知')} · ${esc(e.name)} · ${esc(STATUS[e.status]||'已结束')}</option>`).join('')}</select></label></div>`;
   h+=ui.tabs([['graph','赛制进程'],['list','比赛列表'],['field','参赛队伍'],['awards','赛事荣誉']],tab);
   if(tab==='field')h+=`<div class="team-grid">${(ev.field||[...new Set(ev.matches.flatMap(m=>[m.team_a,m.team_b]))]).filter(t=>t!=='BYE').map(t=>`<div class="card">${crest(t,36)} ${ui.link('team',t,t)}</div>`).join('')}</div>`;
   else if(tab==='awards')h+=`<div class="card"><h3>冠军</h3>${ev.champion?ui.link('team',ev.champion,ev.champion):'尚未产生'}<h3>MVP</h3>${ev.awards?.mvp?ui.link('player',ev.awards.mvp.player,ev.awards.mvp.player):'尚未产生'}<h3>EVP</h3>${(ev.awards?.evp||[]).map(p=>ui.link('player',p.player,p.player)).join(' · ')||'尚未产生'}<h3>最佳阵容</h3><p class="hint">按本届赛事已记录的主要位置分别评选。旧战报缺少位置时不猜测补位。</p>${(ev.awards?.five||[]).map(p=>`<p>${esc(ROLE[p.role]||'旧记录未注明位置')} · ${ui.link('player',p.player_id||p.player,p.player)} · Rating ${ui.num(p.rating,2)}</p>`).join('')||'尚未产生'}</div>`;
   else if(!ev.matches?.length)h+=ui.empty('对阵尚未生成。接受邀请并推进至开赛后显示；未确定的对手不会被虚构。');
   else if(tab==='list')h+=`<div class="match-list">${ev.matches.map(node).join('')}</div>`;
   else{
     if(ev.swiss_table?.length)h+=`<div class="card"><h3>瑞士轮状态</h3><div class="swiss-groups">${ev.swiss_table.map(t=>`<span>${ui.link('team',t.team||t.name,t.team||t.name)} ${t.w||0}–${t.l||0} ${t.w>=3?'晋级':t.l>=3?'淘汰':''}</span>`).join('')}</div></div>`;
     h+=drawGraph(ev);
   }
   host.innerHTML=h;graphControls(host);
   const chooser=host.querySelector('#event-directory');
   if(chooser)chooser.onchange=e=>ui.go('event',{key:e.target.value,tab:'graph'});
 };
})();
