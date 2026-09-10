/* Two transparent prices; the backend rechecks every quote and roster. */
CareerUI.pages.market=async(route,host,active)=>{
 const c=S.career,ui=CareerUI;
 if(!c.exists||c.unsigned||c.over){host.innerHTML=ui.empty('先加入或创建俱乐部，再进行引援。');return;}
 const data=await get('/api/transfers');if(!active())return;
 const source=route.source||'free',search=(route.search||'').toLowerCase();
 const isAcademy=p=>p.note==='academy'||p.note==='wonder';
 const rows=data.players.filter(p=>(source==='academy'?isAcademy(p):source==='active'?!!p.seller_id:!p.seller_id)&&(!route.role||p.role===route.role)&&(p.name+' '+p.seller).toLowerCase().includes(search));
 const development=p=>`<small class="hint">${p.age==null?'':`${ui.num(p.age)}岁`}${isAcademy(p)?` · ${p.note==='wonder'?'天才':'青训'}${p.academy_year?` · ${esc(p.academy_year)}届`:''}${p.potential==null?'':` · 潜力 ${ui.num(p.potential,1)}`}`:''}</small>`;
 host.innerHTML=ui.head('转会市场',`俱乐部资金 ${money(c.money)} · 保签不受队伍排名限制`)+ui.tabs([['free','自由球员'],['active','现役买断'],['academy','青训观察']],source)+
 (source==='academy'?'<p class="hint">这里汇集自由市场与其他战队中的青训／天才选手。届别为进入本生涯市场的年份；已被球队签下的选手遵循现役买断规则，潜力不保证兑现。</p>':'')+
 `<p class="hint">普通签约按原价与成功率谈判；失败仅扣8%谈判费。保签按长期实力报价：普通球员3倍，90分以上5倍。现役仅接受买断；双方赛事结束、卖方能补齐阵容时才能交易。</p><div class="filterbar"><input id="transfer-search" placeholder="选手或队伍" value="${esc(route.search||'')}"><select id="transfer-role"><option value="">所有位置</option>${Object.entries(ROLE).map(([id,title])=>`<option value="${id}" ${id===route.role?'selected':''}>${title}</option>`).join('')}</select><button class="btn" id="transfer-filter">筛选</button><label>替换队友 <select id="transfer-replace">${c.roster.filter(p=>!p.you&&p.name!==c.player_name).map(p=>`<option value="${esc(p.player_id)}">${esc(p.name)} · ${ROLE[p.role]}</option>`).join('')}</select></label></div><div class="card table-scroll"><table><thead><tr><th>选手 / 队伍</th><th>位置 / 能力</th><th>普通签约</th><th>100%保签</th></tr></thead><tbody>${rows.map((p,i)=>`<tr><td>${ui.link('player',p.player_id,p.name)}<small class="hint"> · ${esc(p.seller)}</small></td><td>${ROLE[p.role]||esc(p.role)} · ${ui.num(p.ability,1)}${development(p)}</td><td>${p.normal_fee==null?'现役只接受买断':`${money(p.normal_fee)} · ${Math.round(p.normal_chance*100)}%<br><small>失败扣 ${money(p.negotiation_fee)}</small><br><button class="btn sm" data-sign="${i}" data-mode="normal" ${p.blocked||!p.normal_chance||c.money<p.normal_fee?'disabled':''}>尝试签约</button>`}</td><td>${money(p.guaranteed_fee)} · ${p.multiplier}倍<br><button class="btn sm primary" data-sign="${i}" data-mode="guaranteed" ${p.blocked||c.money<p.guaranteed_fee?'disabled':''}>${p.seller_id?'买断现役':'保签入队'}</button>${p.blocked?`<small class="hint">${esc(p.blocked)}</small>`:''}</td></tr>`).join('')}</tbody></table>${rows.length?'':ui.empty('没有符合条件的选手。')}</div>`;
 // tabs ordinarily use route.tab; keep this page's source filter explicit.
 host.querySelectorAll('[data-route-tab]').forEach(b=>{const source=b.dataset.routeTab;b.removeAttribute('data-route-tab');b.onclick=()=>ui.go('market',{source},true);});
 $('transfer-filter').onclick=()=>ui.go('market',{source,search:$('transfer-search').value,role:$('transfer-role').value},true);
 host.querySelectorAll('[data-sign]').forEach(b=>b.onclick=async()=>{
   if(b.disabled)return;
   const p=rows[Number(b.dataset.sign)],mode=b.dataset.mode,replace=$('transfer-replace').value;
   const who=c.roster.find(x=>x.player_id===replace)?.name||'';
   if(!replace||!who){toast('请先选择要替换的队友。',true);return;}
   const price=mode==='normal'?p.normal_fee:p.guaranteed_fee;
   if(!window.confirm(`${mode==='normal'?'尝试签约':'100%保签'} ${p.name}，报价 ${money(price)}。成功后 ${who} 离队。${mode==='normal'?`失败会扣 ${money(p.negotiation_fee)}。`:'不会按概率拒签。'}`))return;
   host.querySelectorAll('[data-sign]').forEach(button=>button.disabled=true);
   try{await post('/api/market/buy',{player:p.name,player_id:p.player_id,seller_id:p.seller_id,replace_id:replace,mode,fee:price});}
   catch(e){toast(e.message,true);b.disabled=false;}
 });
};
