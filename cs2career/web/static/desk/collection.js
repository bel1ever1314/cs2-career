/* Cosmetic presentation only. The persisted pending_drop owns the result. */
(() => {
 const ui=CareerUI, colors={milspec:'#5989ff',restricted:'#9466ed',classified:'#d651d3',covert:'#ed5b5b',extraordinary:'#e8bd54'};
 let artwork=null, animationTimer=null, animationDrop=null, busy=false;
 const title={milspec:'军规级',restricted:'受限',classified:'保密',covert:'隐秘',extraordinary:'非凡'};
 const id=p=>p.skin_id||p.id;
 function photo(p){const mapped=artwork?.items?.[id(p)]?.status==='mapped';return `<div class="skin-photo">${mapped?`<img src="/art/${encodeURIComponent(id(p))}" alt="${esc(p.name)}" loading="lazy">`:''}<span class="skin-placeholder" ${mapped?'hidden':''}>${esc(p.weapon||'饰品')}<small>暂无核验图片</small></span></div>`;}
 function card(p,kind='market'){
   const shop=S.career.skins,mark=kind==='inventory'?[shop.equipped_ct?.[p.slot]===p.id?'CT':'',shop.equipped_t?.[p.slot]===p.id?'T':''].filter(Boolean).join(' / '):'';
   return `<button class="collection-card" data-skin-detail="${esc(p.id)}" data-kind="${kind}" style="--rarity:${colors[p.rarity]||'#909bac'}">${photo(p)}<div class="collection-copy"><small>${esc(p.weapon)} <span>${esc(mark)}</span></small><b>${esc(p.name.split(' | ').pop())}</b><span class="rarity-label">${title[p.rarity]||esc(p.rarity)}</span><div><strong>${money(p.spot)}</strong><small>${p.wear==null?'市场参考价':'磨损 '+Number(p.wear).toFixed(3)}</small></div></div></button>`;
 }
 async function command(path,data){if(busy)return null;busy=true;try{return await post(path,data);}finally{busy=false;}}
 function closeModal(){document.querySelector('#collection-modal')?.remove();}
 function affordability(price,balance){
   price=Number(price);balance=Number(balance);
   if(!Number.isFinite(price)||!Number.isFinite(balance)||price<0)return {allowed:false,reason:'余额或报价尚未加载，请刷新报价。'};
   const short=Math.max(0,price-balance);
   return {allowed:short===0,reason:short?`个人余额不足，还差 ${money(short)}。俱乐部资金不能购买个人饰品。`:`购买后个人余额 ${money(balance-price)}。`};
 }
 function dialog(p,kind){
   closeModal();const box=document.createElement('div');box.id='collection-modal';box.className='collection-mask';
   const inv=kind==='inventory',shop=S.career.skins;
   box.innerHTML=`<section class="collection-dialog" role="dialog" aria-modal="true" aria-label="饰品详情" style="--rarity:${colors[p.rarity]}"><button class="close-detail" aria-label="关闭">×</button>${photo(p)}<h2>${esc(p.name)}</h2><p class="rarity-label">${title[p.rarity]||esc(p.rarity)} · ${p.wear==null?'市场饰品':'磨损 '+Number(p.wear).toFixed(3)}</p><h3>${money(p.spot)}</h3><p class="hint">图片为物品标准外观，不模拟磨损、模板或 StatTrak。${artwork?.items?.[id(p)]?.source_name?'来源对应：'+esc(artwork.items[id(p)].source_name):'此物品暂未找到可靠图片对应。'}</p><div class="filterbar">${inv?(p.sides||[]).map(side=>{const on=shop['equipped_'+side]?.[p.slot]===p.id;return `<button class="btn" data-equip-side="${side}" data-off="${on?'1':''}">${on?'卸下':'装备到'} ${side.toUpperCase()}</button>`;}).join('')+`<button class="btn" id="collection-sell">出售 ${money(p.sell)}</button>`:`<button class="btn primary" id="collection-buy" ${S.career.pocket<p.spot?'disabled':''}>购买 ${money(p.spot)}</button>`}</div></section>`;
   if(!inv){
     const funds=affordability(p.spot,S.career.pocket),button=box.querySelector('#collection-buy');
     button.disabled=!funds.allowed;button.setAttribute('aria-describedby','collection-funds');
     box.querySelector('.filterbar').insertAdjacentHTML('beforebegin',`<div id="collection-funds" role="status"><p>个人余额 <strong>${money(S.career.pocket)}</strong> · 本次价格 <strong>${money(p.spot)}</strong></p><p class="hint">${funds.reason}</p></div>`);
     box.querySelector('.filterbar').insertAdjacentHTML('beforeend','<button class="btn" id="collection-refresh">刷新余额与报价</button>');
     box.querySelector('#collection-refresh').onclick=async e=>{
       e.target.disabled=true;
       try{adopt(await get('/api/state'));const current=S.career.skins.market.find(x=>x.id===p.id);if(current){dialog(current,kind);images($('collection-modal'));}else{toast('此饰品已不在市场。',true);closeModal();}}
       catch(error){toast('刷新失败：'+error.message,true);e.target.disabled=false;}
     };
   }
   document.body.append(box);box.querySelector('.close-detail').onclick=closeModal;box.onclick=e=>{if(e.target===box)closeModal();};
   box.querySelectorAll('[data-equip-side]').forEach(b=>b.onclick=async()=>{await command('/api/skins/equip',{id:p.id,side:b.dataset.equipSide,off:b.dataset.off==='1'});closeModal();});
   if($('collection-buy'))$('collection-buy').onclick=async e=>{
     if(busy)return;e.target.disabled=true;
     try{const before=S.career.skins.inventory.length;const result=await command('/api/skins/buy',{id:p.id});
       if(result?.ok!==false&&S.career.skins.inventory.length>before)closeModal();
       else{const current=S.career.skins.market.find(x=>x.id===p.id)||p;dialog(current,kind);images($('collection-modal'));}
     }catch(error){toast('购买失败：'+error.message,true);e.target.disabled=false;}
   };
   if($('collection-sell'))$('collection-sell').onclick=async()=>{if(confirm(`出售 ${p.name}，获得 ${money(p.sell)}？`)){await command('/api/skins/sell',{id:p.id});closeModal();}};
   box.querySelector('.close-detail').focus();
 }
 function images(host){host.querySelectorAll('.skin-photo img').forEach(img=>{img.onerror=()=>{img.hidden=true;img.parentElement.querySelector('.skin-placeholder').hidden=false;};if(img.complete&&!img.naturalWidth)img.onerror();});}
 function bind(host){
   images(host);
   host.querySelectorAll('[data-skin-detail]').forEach(b=>b.onclick=()=>{const list=b.dataset.kind==='inventory'?S.career.skins.inventory:S.career.skins.market;const p=list.find(x=>x.id===b.dataset.skinDetail);if(p){dialog(p,b.dataset.kind);images($('collection-modal'));}});
 }
 function pending(){const p=S.career.skins.pending;if(!p)return '';return `<div class="pending-drop" style="--rarity:${colors[p.rarity]}">${photo(p)}<div><small class="rarity-label">待处理掉落 · ${title[p.rarity]}</small><h3>${esc(p.name)}</h3><p>磨损 ${Number(p.wear).toFixed(3)} · ${money(p.spot)}</p><div class="filterbar"><button class="btn primary" id="pending-keep">放入库存</button><button class="btn" id="pending-cash">立即出售 ${money(p.sell)}</button></div><small class="hint">结果已经保存，关闭窗口不会重抽或再次扣款。</small></div></div>`;}
 function bindPending(){if($('pending-keep'))$('pending-keep').onclick=()=>command('/api/skins/keep',{});if($('pending-cash'))$('pending-cash').onclick=()=>command('/api/skins/cash',{});}
 async function paint(r,host,active){
   if(!artwork)artwork=await get('/api/skin-art');if(!active())return;
   const shop=S.career?.skins;if(!shop){host.innerHTML=ui.empty('请先创建生涯。');return;}
   const inv=r.view==='inventory',cases=r.view==='cases';
   let h=ui.head(cases?'武器箱':inv?'我的收藏':'饰品市场',`个人余额 ${money(S.career.pocket)} · ${inv?'已收藏 '+shop.inventory.length+' 件 · 装备与出售':cases?'开箱与结果处理':'购买饰品'} · 不消耗俱乐部资金`);
   if(shop.pending)h+=cases?pending():`<div class="notice compact-notice"><span>有一件已开出的饰品尚待处理。</span><button class="btn sm" data-route="cases">前往武器箱处理 →</button></div>`;
   if(cases){h+=`<div class="filterbar"><label><input type="checkbox" id="reduce-unbox" ${localStorage.getItem('reduce-unbox')==='1'?'checked':''}> 减少动画，直接显示结果</label><span class="hint">动画不影响中奖结果；箱子与钥匙一次扣费。</span></div><div class="case-grid">${shop.cases.map(b=>`<article class="case-card"><div class="case-mark">▱</div><h3>${esc(b.name)}</h3><p class="hint">${b.pool.length} 件候选饰品 · 箱子 ${money(b.price)} ＋ 钥匙 ${money(b.key)}</p><div class="case-colors">${b.pool.slice(0,12).map(p=>`<i style="background:${colors[p.rarity]}"></i>`).join('')}</div><button class="btn primary" data-open-case="${esc(b.id)}" ${shop.pending||S.career.pocket<b.price+b.key?'disabled':''}>开启 ${money(b.price+b.key)}</button><details><summary>查看可掉落饰品</summary>${b.pool.map(p=>`<p class="rarity-label" style="--rarity:${colors[p.rarity]}">${esc(p.name)}</p>`).join('')}</details></article>`).join('')}</div>`;}
   else{
     const all=inv?shop.inventory:shop.market;
     let rows=all.filter(p=>(!r.search||p.name.toLowerCase().includes(r.search.toLowerCase()))&&(!r.weapon||p.weapon===r.weapon)&&(!r.rarity||p.rarity===r.rarity));
     rows=[...rows].sort((a,b)=>r.sort==='price'?(b.spot-a.spot):rarityRank(a.rarity)-rarityRank(b.rarity)||(b.spot-a.spot));
     h+=`<div class="filterbar"><input id="skin-search" value="${esc(r.search||'')}" placeholder="搜索饰品"><select id="skin-weapon"><option value="">所有武器</option>${shop.weapons.map(w=>`<option ${r.weapon===w?'selected':''}>${esc(w)}</option>`).join('')}</select><select id="skin-rarity"><option value="">所有等级</option>${Object.entries(title).map(([k,v])=>`<option value="${k}" ${r.rarity===k?'selected':''}>${v}</option>`).join('')}</select><select id="skin-sort"><option value="rarity">稀有度优先</option><option value="price" ${r.sort==='price'?'selected':''}>价格从高到低</option></select><button class="btn" id="skin-filter">筛选</button><span class="hint">${rows.length} 件</span></div><div class="collection-grid">${rows.map(p=>card(p,inv?'inventory':'market')).join('')}</div>${rows.length?'':ui.empty('没有符合条件的饰品。')}`;
   }
   ui.paint(host,h);bind(host);bindPending();
   if($('skin-filter'))$('skin-filter').onclick=()=>ui.go(r.view,{search:$('skin-search').value,weapon:$('skin-weapon').value,rarity:$('skin-rarity').value,sort:$('skin-sort').value},true);
   if($('reduce-unbox'))$('reduce-unbox').onchange=e=>localStorage.setItem('reduce-unbox',e.target.checked?'1':'0');
   host.querySelectorAll('[data-open-case]').forEach(b=>b.onclick=async()=>{
     if(busy||S.career.skins.pending)return;b.disabled=true;
     const box=shop.cases.find(x=>x.id===b.dataset.openCase);
     await command('/api/skins/case',{id:box.id});
     const drop=S.career.skins.pending;if(drop)animate(box,drop);
   });
 }
 function animate(box,drop){
   if(animationDrop)return;animationDrop=drop;closeModal();
   const reduced=localStorage.getItem('reduce-unbox')==='1'||matchMedia('(prefers-reduced-motion: reduce)').matches;
   const mask=document.createElement('div');mask.className='collection-mask';mask.id='unbox-animation';
   const strip=Array.from({length:36},(_,i)=>box.pool[i%box.pool.length]);strip[32]=drop;
   mask.innerHTML=`<section class="unbox-dialog" role="dialog" aria-modal="true"><h2>${esc(box.name)}</h2><p class="hint">结果已保存 · 动画仅用于展示</p><div class="reel-window"><div class="reel-needle"></div><div class="reel">${strip.map(p=>`<div class="reel-card" style="--rarity:${colors[p.rarity]}">${photo(p)}<b>${esc(p.name.split(' | ').pop())}</b><small class="rarity-label">${title[p.rarity]}</small></div>`).join('')}</div></div><button class="btn" id="unbox-skip">跳过动画</button><div id="unbox-reveal"></div></section>`;
   document.body.append(mask);images(mask);
   let revealed=false;
   function reveal(){if(revealed)return;revealed=true;clearTimeout(animationTimer);mask.querySelector('.reel-window').hidden=true;$('unbox-skip').hidden=true;$('unbox-reveal').innerHTML=pending()+`<button class="btn" id="unbox-later">稍后处理</button>`;images(mask);
     for(const [btn,api] of [['pending-keep','keep'],['pending-cash','cash']]){const b=mask.querySelector('#'+btn);if(b)b.onclick=async()=>{await command('/api/skins/'+api,{});mask.remove();animationDrop=null;render();};}
     $('unbox-later').onclick=()=>{mask.remove();animationDrop=null;render();};
   }
   $('unbox-skip').onclick=reveal;
   requestAnimationFrame(()=>requestAnimationFrame(()=>{const reel=mask.querySelector('.reel'),land=reel.children[32],view=mask.querySelector('.reel-window');reel.style.transition=reduced?'none':'transform 4s cubic-bezier(.12,.7,.12,1)';reel.style.transform=`translateX(-${land.offsetLeft+land.offsetWidth/2-view.clientWidth/2}px)`;if(reduced)reveal();else animationTimer=setTimeout(reveal,4100);}));
 }
 ui.pages.inventory=ui.pages.skins=ui.pages.cases=paint;
 document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});
})();
