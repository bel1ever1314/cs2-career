/* Team/player read models. Historical rows link to the actual stored match. */
(() => {
 const ui=CareerUI;
 function playerLink(p){return ui.link('player',p.player_id||p.name,p.name);}
 function metric(title,value){return `<div class="metric"><small>${esc(title)}</small><b>${value}</b></div>`;}
 function trend(rows){
   const values=[...rows].reverse().filter(r=>r.rating!=null);
   if(!values.length)return ui.empty('暂无比赛。完成比赛后这里会显示最近10图的 Rating 走势。');
   const x=i=>30+i*700/Math.max(1,values.length-1), y=r=>140-(Math.max(.2,Math.min(2.5,r))-.2)*110/2.3;
   return `<svg class="rating-chart" viewBox="0 0 760 165" role="img" aria-label="最近十张地图Rating走势"><line x1="20" y1="${y(1)}" x2="745" y2="${y(1)}" stroke="#4b5260" stroke-dasharray="4 5"/><text x="20" y="${y(1)-5}">1.00</text><polyline points="${values.map((r,i)=>`${x(i)},${y(r.rating)}`).join(' ')}" fill="none" stroke="#ff9559" stroke-width="3"/>${values.map((r,i)=>`<circle cx="${x(i)}" cy="${y(r.rating)}" r="4" fill="#ff9559"><title>${esc(r.map)} ${ui.num(r.rating,2)}</title></circle><text x="${x(i)}" y="${y(r.rating)-10}" text-anchor="middle">${ui.num(r.rating,2)}</text>`).join('')}</svg>`;
 }
 function history(rows,kind){
   if(!rows.length)return ui.empty('此时间范围内暂无比赛记录。');
   return `<div class="table-scroll"><table><thead><tr><th>日期 / 赛事</th><th>对阵</th><th>比分</th>${kind==='player'?'<th>地图</th><th>K / D / A</th><th>ADR</th><th>KAST</th><th>Rating</th>':''}</tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.date)}<br>${ui.link('event',r.event_id,r.event)}</td><td>${ui.link('team',r.team_a,r.team_a)}<br>${ui.link('team',r.team_b,r.team_b)}</td><td>${ui.link('match',r.match_id,r.score||r.series||(r.played?'已结束':'赛前资料'))}</td>${kind==='player'?`<td>${esc(r.map)}</td><td>${r.k} / ${r.d} / ${r.a}</td><td>${ui.num(r.adr,1)}</td><td>${r.kast==null?'—':ui.num(r.kast*100,1)+'%'}</td><td class="rating">${ui.num(r.rating,2)}</td>`:''}</tr>`).join('')}</tbody></table></div>`;
 }
 ui.pages.profile=async(r,host,active)=>{
   const row=await get(`/api/inspect?${r.kind}=${encodeURIComponent(r.key)}&range=${r.range||'season'}&page=${r.page||1}`);
   if(!active())return;
   const isTeam=r.kind==='team', title=isTeam?row.name:row.name+' · '+(ROLE[row.role]||row.role||'选手')+(row.is_igl&&row.role!=='igl'?' / 兼任指挥':'')+(row.roster_status==='stand_in'?' · 代打':'');
   let h=ui.head(title,isTeam?`${REGION[row.region]||row.region} · 世界排名 #${row.rank??'—'}`:`${row.age??'—'} 岁 · ${row.birthday||''}`);
   h+=`<div class="profile-banner">${isTeam?crest(row.name,64):'<div class="initial-mark">'+esc(row.name.slice(0,2))+'</div>'}<div><h2>${esc(row.name)}</h2>${isTeam?`<span class="hint">赛训指挥 ${row.command??'—'} · 心态 ${Math.round(row.mentality||0)}</span>`:row.historical?'<span class="hint">历史选手 · 最后记录 '+esc(row.last_team||'未知队伍')+'</span>':row.team?ui.link('team',row.team_id||row.team,row.team):'<span class="hint">自由选手</span>'}</div><div class="profile-metrics">${isTeam?metric('VRS',ui.num(row.vrs)):metric('当前位置能力',ui.num(row.ability))+metric('近期状态',row.form_delta==null?'—':(row.form_delta>=0?'+':'')+ui.num(row.form_delta,1))}</div></div>`;
   h+=ui.tabs([['overview','概览'],['matches','比赛记录'],['honours','荣誉']],r.tab||'overview');
   if(row.data_provenance?.label){
     const d=row.data_provenance;
     h+=`<details class="card"><summary>${esc(d.label)}</summary><p class="hint">${esc(d.note)}</p>${d.as_of?`<p class="hint">开局快照：${esc(d.as_of)}；不表示转会后的当前阵容仍与现实一致。</p>`:''}${(d.sources||[]).map(s=>`<p class="hint">${esc(s.title)}<br>${esc(s.url)}</p>`).join('')}</details>`;
     if(isTeam&&d.game_seed)h+=`<p class="hint">来源开局排名 ${d.source_rank?'#'+d.source_rank:'未核验'} · 收录世界开局排序 #${d.game_seed}（与当前生涯排名不同）</p>`;
   }
   h+=`<div class="filterbar"><label>统计范围 <select id="profile-range"><option value="30d">最近30天</option><option value="season">本赛季</option><option value="all">全部已保存历史</option></select></label><span class="hint">${row.total} ${isTeam?'场比赛':'张地图'} · 仅使用已保存记录</span></div>`;
   if(r.tab==='honours') h+=isTeam?`<div class="card">${row.honours?.length?row.honours.map(x=>`<p>🏆 ${esc(x.short||x.event||x.name)} · ${esc(x.date)}</p>`).join(''):ui.empty('暂无冠军荣誉')}</div>`:row.honours_notice?ui.empty(row.honours_notice):honoursMedals(row.honours)+honoursLists(row.honours);
   else if(r.tab==='matches') h+=`<div class="card pad0">${history(row.records,r.kind)}</div><div class="filterbar"><button class="btn" id="records-prev" ${row.page<=1?'disabled':''}>上一页</button><span>${row.page} / ${Math.max(1,Math.ceil(row.total/row.page_size))}</span><button class="btn" id="records-next" ${row.page*row.page_size>=row.total?'disabled':''}>下一页</button></div>`;
   else if(isTeam){
     h+=`<div class="card"><h3>当前五人配置</h3><div class="lineup-grid">${row.players.map(p=>`<article class="player-card"><small>${ROLE[p.role]||esc(p.role)}</small><h3>${playerLink(p)}</h3><strong>${ui.num(p.ability)}</strong><span>状态 ${(p.form_delta||0)>=0?'+':''}${ui.num(p.form_delta||0,1)}</span><small>${p.age}岁 · 指挥 ${ui.num(p.command)}</small></article>`).join('')}</div></div><div class="grid2"><div class="card"><h3>擅长地图</h3>${(row.strong_maps||[]).map(m=>badge('done',mapName(m))).join(' ')||'—'}</div><div class="card"><h3>地图短板</h3>${(row.weak_maps||[]).map(m=>badge('qual',mapName(m))).join(' ')||'—'}</div></div><div class="card pad0"><h3>最近比赛</h3>${history(row.recent,'team')}</div>`;
   }else{
     const a=row.summary;
     h+=`<div class="metric-grid">${metric('Rating',ui.num(a.rating,2))+metric('K / D / A',a.maps?`${a.k} / ${a.d} / ${a.a}`:'—')+metric('ADR',ui.num(a.adr,1))+metric('KAST',a.kast==null?'—':ui.num(a.kast*100,1)+'%')}</div><div class="grid2"><div class="card"><h3>最近10图 · Rating</h3>${trend(row.recent)}</div><div class="card"><h3>个人能力 · 打法维度</h3>${row.historical?ui.empty('旧战报未保存年龄、长期能力及七维档案，不补造数值。'):axisPanel(row.stats)}</div></div><div class="card pad0"><h3>近期表现</h3>${history(row.recent,'player')}</div>`;
   }
   ui.paint(host,h);
   if(isTeam&&S.career?.exists&&row.id!==S.career.team_id){
     host.insertAdjacentHTML('afterbegin','<button class="btn primary" id="profile-apply-transfer">申请加盟这支队伍</button>');
     $('profile-apply-transfer').onclick=()=>ui.go('market',{source:'personal',team_id:row.id||row.team_id||r.key});
   }
   $('profile-range').value=r.range||'season';
   $('profile-range').onchange=e=>ui.go('profile',{...r,range:e.target.value,page:1},true);
   if($('records-prev'))$('records-prev').onclick=()=>ui.go('profile',{...r,page:row.page-1},true);
   if($('records-next'))$('records-next').onclick=()=>ui.go('profile',{...r,page:row.page+1},true);
 };
 ui.pages.players=(r,host)=>{
   const tab=r.tab||'live', years=Object.keys(S.top20_history||{}).sort().reverse();
   let h=ui.head('年度 Top20','个人年度荣誉 · 与队伍排名独立')+ui.tabs([['live','当年暂定榜'],...years.map(y=>[y,y+' 最终榜'])],tab)+`<p class="hint">${tab==='live'?'赛季尚未结算，这是动态候选榜；样本不足时不会强行列满20人。':'已结算历史榜单'}</p>`+top20Table(tab==='live'?S.top20||[]:S.top20_history[tab]||[]);
   if(tab!=='live')h+=(S.top20_history[tab]||[]).filter(p=>p.rank<=3&&p.feature).map(p=>`<details class="card"><summary>Top ${p.rank} · ${esc(p.feature.title)}</summary>${ui.renderFeature(p.feature)}</details>`).join('');
   ui.paint(host,h);
   bindInspect(host);
 };
 ui.pages.data=(r,host)=>{
   const rows=(S.ratings||[]).filter(p=>(p.player||'').toLowerCase().includes((r.search||'').toLowerCase())&&(!r.team||p.team===r.team));
   rows.sort((a,b)=>(b[r.sort||'rating']||0)-(a[r.sort||'rating']||0));
   ui.paint(host,ui.head('选手数据','本赛季全对手表现 · 点击名字打开资料')+`<div class="filterbar"><input id="data-search" placeholder="搜索选手" value="${esc(r.search||'')}"><select id="data-team"><option value="">所有战队</option>${S.teams.map(t=>`<option ${t.name===r.team?'selected':''}>${esc(t.name)}</option>`).join('')}</select><select id="data-sort"><option value="rating">Rating</option><option value="maps">地图数量</option><option value="kpr">KPR</option></select><button class="btn" id="data-filter">筛选</button></div><div class="card pad0">${ratingTable(rows,{inspect:true})}</div>`);
   $('data-sort').value=r.sort||'rating';$('data-filter').onclick=()=>ui.go('data',{search:$('data-search').value,team:$('data-team').value,sort:$('data-sort').value},true);bindInspect(host);
 };
})();
