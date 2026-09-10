/* JSON-only content packs: observe errors without executing pack scripts. */
(() => {
CareerUI.pages.workshop=async(_route,host,active)=>{
  const info=await get('/api/extensions');if(!active())return;
  const kinds={stories:'剧情',events:'赛事',skins:'饰品',teams:'战队',eras:'年代'};
  host.innerHTML=CareerUI.head('扩展工坊','数据驱动的剧情、赛事、饰品与世界内容')+`<div class="card"><h3>安装与制作</h3>
    <p>将扩展文件夹放入下方目录，每包包含 pack.json 和相应类型子目录。扩展只读取 JSON，不执行脚本。</p>
    <p><code>${esc(info.root)}</code></p><p class="hint">项目 extensions/_templates 提供制作示例；剧情与饰品可即时重载，赛事与年代用于新生涯。</p>
    <button class="btn" id="packs-reload" ${S.design_preview?'disabled':''}>重新扫描扩展</button></div>
    <div class="page-head"><h3>已发现 ${info.packs.length} 个扩展 · ${info.ready} 个已启用</h3></div>
    ${info.packs.length?info.packs.map(p=>`<article class="card"><h3>${esc(p.name)} <small class="hint">${esc(p.version)}</small></h3>
    <p>${esc({ready:'已启用',disabled:'已停用',rejected:'校验失败，未加载'}[p.status]||p.status)} · ${p.kinds.map(k=>esc(kinds[k]||k)).join(' / ')}</p>
    <small class="hint">${esc(p.id)}</small>${p.errors.length?`<div class="notice">${p.errors.map(esc).join('<br>')}</div>`:''}</article>`).join(''):CareerUI.empty('暂无扩展，内置内容可以直接游玩。')}`;
  $('packs-reload').onclick=async e=>{e.target.disabled=true;try{await post('/api/extensions/reload',{});}finally{CareerUI.go('workshop',{},true);}};
};
})();
