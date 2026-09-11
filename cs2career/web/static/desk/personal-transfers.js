/* Personal career commands. A dice animation reveals a saved server result;
   it neither rolls a die nor performs another POST when skipped or closed. */
(() => {
 const ui=CareerUI;
 let busy=false;
 ui.personalTransferPage=async(route,host,active)=>{
   const data=await get('/api/player-transfers');if(!active())return;
   const c=S.career,search=(route.search||'').toLowerCase();
   const rows=data.targets.filter(p=>(!route.team_id||p.team_id===route.team_id)&&(!route.role||p.role===route.role)&&p.team.toLowerCase().includes(search));
   const last=data.last_attempt;
   host.innerHTML=ui.head('我的转会','你是这段生涯的主角：申请试训，或等待球队主动邀约')+
     (!c.player_only&&!c.unsigned?'<button class="btn" id="club-market">返回俱乐部引援</button>':'')+
     `<div class="card"><p>本年主动邀约 ${data.offers_this_year} / ${data.offer_limit}（不是保证发满）。收到的合同在邮箱确认，无需再掷骰。</p>
     <p>申请失败：全队通用冷却30天，同队90天；成功：申请冷却90天；正式加盟后180天不能再次转会。</p>
     <p class="hint">申请冷却至 ${esc(data.apply_until||'无')} · 加盟锁定至 ${esc(data.move_until||'无')}。拒绝已通过的申请也不返还机会。</p>
     <p class="hint">D20 + 位置能力差修正 ≥ 12 通过；每完整3分差修正1点，范围 −8～+6。天然20通过、天然1失败。不同位置只显示本次试训的加成。</p></div>`+
     (last?`<div class="card"><h3>上次试训 · ${esc(last.team)} · ${esc(last.date)}</h3><p>D20 <b>${last.roll}</b> ${last.modifier>=0?'+':''}${last.modifier} = ${last.total} · ${last.success?'已通过，最终去留以你的选择为准':'未通过'}</p></div>`:'')+
     (data.pending?'<p class="hint">有待决定的加盟机会，请先处理剧情弹窗。</p>':'')+
     `<div class="filterbar"><input id="personal-search" placeholder="战队名称" value="${esc(route.search||'')}"><select id="personal-role"><option value="">全部位置</option>${Object.entries(ROLE).map(([id,name])=>`<option value="${id}" ${route.role===id?'selected':''}>${esc(name)}</option>`).join('')}</select><button class="btn" id="personal-filter">筛选</button>${route.team_id?'<button class="btn" id="personal-all">查看所有战队</button>':''}<button class="btn" data-route="mail">查看邀约邮箱</button></div>`+
     `<div class="card table-scroll"><table><thead><tr><th>战队</th><th>试训位置</th><th>能力修正 / 成功率</th><th>申请</th></tr></thead><tbody>${rows.map((r,i)=>`<tr><td>${ui.link('team',r.team_id,r.team)}</td><td>${esc(ROLE[r.role]||r.role)}<small class="hint"> · 接替 ${esc(r.replace)}</small></td><td>${r.modifier>=0?'+':''}${r.modifier} · ${Math.round(r.chance*100)}%</td><td><button class="btn primary" data-personal-apply="${i}" ${r.blocked||busy?'disabled':''}>申请并掷 D20</button>${r.blocked?`<p class="hint">${esc(r.blocked)}</p>`:''}</td></tr>`).join('')}</tbody></table>${rows.length?'':ui.empty('没有符合条件的战队位置。')}</div>`+
     `<div class="card"><h3>生涯转会记录</h3>${data.history.length?data.history.map(r=>`<p>${esc(r.date)} · ${esc(r.old_team)} → ${esc(r.new_team)} · ${esc(ROLE[r.transfer_role]||r.transfer_role)}</p>`).join(''):ui.empty('还没有正式转会。')}</div>`;
   if($('club-market'))$('club-market').onclick=()=>ui.go('market',{source:'free'},true);
   $('personal-filter').onclick=()=>ui.go('market',{source:'personal',team_id:route.team_id,search:$('personal-search').value,role:$('personal-role').value},true);
   if($('personal-all'))$('personal-all').onclick=()=>ui.go('market',{source:'personal'},true);
   host.querySelectorAll('[data-personal-apply]').forEach(b=>b.onclick=()=>apply(rows[Number(b.dataset.personalApply)],host));
 };
 async function reveal(result){
   if(!result||window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)return;
   const box=document.createElement('div');box.className='personal-dice-overlay';
   box.innerHTML='<div class="card"><h3>试训 · D20</h3><strong class="personal-dice">…</strong><p>结果已经保存，动画不会改变骰点。</p><button class="btn">直接查看结果</button></div>';
   document.body.appendChild(box);
   await new Promise(resolve=>{
     let n=0,ended=false;
     const finish=()=>{if(ended)return;ended=true;clearInterval(timer);box.remove();resolve();};
     const timer=setInterval(()=>{box.querySelector('strong').textContent=String(++n%20+1);if(n>=18)finish();},60);
     box.querySelector('button').onclick=finish;
   });
 }
 async function apply(row,host){
   if(busy||row.blocked)return;
   if(!window.confirm(`申请 ${row.team} 的${ROLE[row.role]||row.role}位置？成功率 ${Math.round(row.chance*100)}%。本次只投一次，失败冷却30天，成功冷却90天；成功后仍可选择留下。`))return;
   busy=true;host.querySelectorAll('[data-personal-apply]').forEach(b=>b.disabled=true);
   try{
     const response=await fetch('/api/player/transfers/apply',{method:'POST',headers:{'Content-Type':'application/json','X-Career-Token':sessionStorage.getItem('career-token')||''},body:JSON.stringify({team_id:row.team_id,role:row.role})});
     const data=await response.json();
     if(response.ok&&data.ok!==false)await reveal(data.transfer);
     if(data.state)adopt(data.state);
     toast(data.msg||'试训已处理',!response.ok||data.ok===false);
     busy=false;ui.remember();render();takeStories(data.stories||data.state?.career?.stories);
   }catch(e){toast('未能确认回传，请刷新查看已保存的上次试训；不要反复点击。'+e.message,true);}
   finally{busy=false;}
 }
})();
