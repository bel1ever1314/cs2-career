/* Inventory customisation is pure presentation. Commands use the existing
 * career POST/adopt flow; this module owns no inventory or Steam account. */
((root) => {
  'use strict';
  const escape = value => String(value ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const tr = value => root.CareerI18n?.t(value) ?? value;
  const field = (row, name) => root.CareerI18n?.field(row, name) ?? row?.[name] ?? '';
  const number = (value, digits = 0) => value == null || value === '' || !Number.isFinite(Number(value)) ? '—' : Number(value).toFixed(digits);
  const catalog = shop => Array.isArray(shop?.stickers) ? shop.stickers : Array.isArray(shop?.stickers?.list) ? shop.stickers.list : [];
  const stickerName = (value, shop) => field(catalog(shop).find(s => Number(s.def) === Number(value)), 'name') || '#'+number(value);
  const rowsFor = item => Array.from({length:5}, (_,slot) => {
    const current = (item?.stickers || []).find(s => Number(s.slot) === slot);
    return {slot,def:current?.def ?? 0,wear:current?.wear ?? 0,rotation:current?.rotation ?? 0,x:current?.x ?? null,y:current?.y ?? null,schema:current?.schema ?? null};
  });
  const canSticker = item => item?.sticker_capable !== false && !['knife','gloves','agents','music','graffiti'].includes(item?.slot);
  function offsetModel(item,shop) {
    const model=item?.inspect_model||shop?.sticker_models?.[String(item.def)];
    return model&&['x_min','x_max','y_min','y_max'].every(key=>model[key]!=null&&Number.isFinite(Number(model[key])))&&Number(model.x_min)<=Number(model.x_max)&&Number(model.y_min)<=Number(model.y_max)?model:null;
  }
  function safeSource(value) {
    try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password ? url.href : ''; }
    catch (_) { return ''; }
  }
  function integrationLinks(integration,{plugin=true,viewer=false}={}) {
    const rows=[...(plugin?[['plugin_url','换肤插件下载']]:[]),['web_url','外部项目源码'],['web_app_url','打开 Inventory Simulator'],...(viewer?[['viewer_url','打开在线 3D 服务']]:[])];
    return rows.map(([key,label])=>{
      const url=safeSource(integration?.[key]);
      return url?'<a class="text-link" href="'+escape(url)+'" target="_blank" rel="noopener noreferrer">'+escape(tr(label))+' ↗</a>':'';
    }).join('');
  }
  function stickerSummary(item, shop) {
    const rows = [...(item?.stickers || [])].sort((a,b) => Number(a.slot)-Number(b.slot));
    return rows.length ? '<ol class="skin-sticker-list">'+rows.map(s => '<li><span>'+escape(tr('槽位'))+' '+(Number(s.slot)+1)+'</span><b data-no-i18n>'+escape(stickerName(s.def,shop))+'</b><small>'+escape(tr('贴纸磨损'))+' '+number(s.wear??0,3)+' · '+escape(tr('旋转'))+' '+number(s.rotation??0)+'°</small></li>').join('')+'</ol>' : '<p class="hint">'+escape(tr('尚未贴上贴纸。'))+'</p>';
  }
  function editorRow(row, shop, enabled, model) {
    const known = catalog(shop), found = known.some(s => Number(s.def)===Number(row.def));
    const options = '<option value="0">'+escape(tr('不贴贴纸'))+'</option>'+(!found && Number(row.def)>0 ? '<option value="'+Number(row.def)+'" selected>#'+Number(row.def)+'</option>' : '')+known.map(s=>'<option value="'+Number(s.def)+'" '+(Number(row.def)===Number(s.def)?'selected':'')+'>'+escape(field(s,'name'))+'</option>').join('');
    const n = (name,label,min,max,step) => '<label><span>'+escape(tr(label))+'</span><input type="number" data-sticker-field="'+name+'" value="'+escape(row[name]??0)+'" min="'+min+'" max="'+max+'" step="'+step+'" required '+(!enabled||!Number(row.def)?'disabled':'')+'></label>';
    const schemas=Number.isInteger(Number(model?.schema_count))&&Number(model.schema_count)>0?'<label><span>'+escape(tr('贴纸锚点'))+'</span><select data-sticker-field="schema" '+(!enabled||!Number(row.def)?'disabled':'')+'><option value="">'+escape(tr('自动锚点'))+'</option>'+Array.from({length:Number(model.schema_count)},(_,i)=>'<option value="'+i+'" '+(row.schema!=null&&Number(row.schema)===i?'selected':'')+'>'+(i+1)+'</option>').join('')+'</select></label>':'';
    return '<fieldset class="skin-sticker-row" data-sticker-slot="'+row.slot+'" data-sticker-schema="'+escape(row.schema??'')+'" data-sticker-x="'+escape(row.x??'')+'" data-sticker-y="'+escape(row.y??'')+'"><legend>'+escape(tr('槽位'))+' '+(row.slot+1)+'</legend><div class="skin-sticker-select"><label><span>'+escape(tr('贴纸'))+'</span><select data-sticker-field="def" '+(!enabled?'disabled':'')+'>'+options+'</select></label><button type="button" class="btn sm" data-sticker-remove '+(!enabled||!Number(row.def)?'disabled':'')+'>'+escape(tr('移除'))+'</button></div><div class="skin-sticker-options" '+(!Number(row.def)?'hidden':'')+'>'+n('wear','贴纸磨损',0,1,.01)+n('rotation','旋转角度',model?.rotation_min??-180,model?.rotation_max??180,.5)+(model?n('x','水平偏移',model.x_min,model.x_max,.0001)+n('y','垂直偏移',model.y_min,model.y_max,.0001):'')+schemas+'</div></fieldset>';
  }
  function details(item, shop) {
    const stat = item.stattrak ?? item.stat_trak;
    const name = item.nametag ?? item.name_tag ?? item.nameTag;
    const enabled = canSticker(item) && catalog(shop).length>0;
    const model=offsetModel(item,shop);
    const reason = !canSticker(item) ? '此类饰品不支持贴纸。' : !catalog(shop).length ? '贴纸目录尚未加载。' : '';
    const inspectEnabled=root.CareerSkinInspect?.enabled(shop)===true;
    const inspect=root.CareerSkinInspect?'<div class="skin-inspect-entry"><button class="btn '+(inspectEnabled?'primary':'')+'" type="button" '+(inspectEnabled?'data-skin-inspect':'data-skin-inspect-settings')+'>'+escape(tr(inspectEnabled?'3D 检视／直接贴纸':'在线 3D 设置'))+'</button><p class="hint">'+escape(tr(inspectEnabled?'点击加载在线 3D，仅发送当前饰品外观，不关联 Steam 账号。':'在线 3D 默认关闭，请在游戏设置中主动启用。'))+'</p><div class="skin-external-links">'+integrationLinks(shop?.skin_integration,{plugin:false})+'</div><p class="hint">'+escape(tr('在线 3D 由外部项目提供，未随生涯打包。'))+'</p><span data-inspect-entry-status role="status" aria-live="polite"></span></div>':'';
    return '<section class="skin-craft" data-ui-key="craft-'+escape(item.id)+'"><dl class="skin-item-facts"><div><dt>'+escape(tr('图案模板'))+'</dt><dd>'+number(item.seed)+'</dd></div><div><dt>'+escape(tr('精确磨损'))+'</dt><dd>'+number(item.wear,5)+'</dd></div><div><dt>StatTrak™</dt><dd>'+escape(stat==null?tr('未启用'):typeof stat==='boolean'?tr(stat?'已启用':'未启用'):number(stat))+'</dd></div><div><dt>'+escape(tr('名称标签'))+'</dt><dd data-no-i18n>'+escape(name||'—')+'</dd></div></dl>'+(item.bound?'<p class="hint skin-bound-label">'+escape(tr('免费配装，不可出售'))+'</p>':'')+inspect+'<h3>'+escape(tr('贴纸'))+'</h3>'+stickerSummary(item,shop)+'<details class="skin-sticker-editor"><summary>'+escape(tr('编辑贴纸 · 免费'))+'</summary><p class="hint">'+escape(tr('调整模拟饰品的五个贴纸槽位，不消耗余额；不是 Steam 物品。'))+'</p>'+(shop?.skin_integration?.inventory_mode==='external'?'<p class="hint">'+escape(tr('此处只编辑生涯收藏；外部 Inventory Simulator 配装由你自行管理。'))+'</p>':'')+(reason?'<p class="hint">'+escape(tr(reason))+'</p>':'')+'<form data-skin-craft-form>'+rowsFor(item).map(r=>editorRow(r,shop,enabled,model)).join('')+'<p class="hint">'+escape(tr(model?'偏移使用游戏内贴纸坐标；图片不会实时预览贴纸位置。':'此武器暂无位置范围，保留原贴纸偏移。'))+'</p><div class="skin-craft-actions"><button class="btn primary" type="submit" '+(!enabled?'disabled':'')+'>'+escape(tr('保存贴纸'))+'</button><span data-craft-status role="status" aria-live="polite"></span></div></form></details></section>';
  }
  function makeCraftPayload(id, rows, model=null) {
    if (!id || rows.length!==5) throw new Error(tr('贴纸槽位数据不完整，请重新打开饰品。'));
    const stickers = [];
    for (let slot=0;slot<5;slot++) {
      const row = rows[slot], def = Number(row.def);
      if (!Number.isInteger(def) || def<0) throw new Error(tr('请选择有效贴纸。'));
      if (!def) continue;
      const sticker = {def,slot};
      for (const [key,min,max] of [['wear',0,1],['rotation',model?.rotation_min??-360,model?.rotation_max??360]]) {
        if (row[key]==null || String(row[key]).trim()==='' || !Number.isFinite(Number(row[key])) || Number(row[key])<min || Number(row[key])>max) throw new Error(tr('请填写范围内的贴纸参数。'));
        sticker[key] = Number(row[key]);
      }
      for(const key of ['x','y'])if(row[key]!=null&&row[key]!==''){
        const value=Number(row[key]);
        if(!Number.isFinite(value)||(model&&(value<Number(model[key+'_min'])||value>Number(model[key+'_max']))))throw new Error(tr('请填写范围内的贴纸参数。'));
        sticker[key]=value;
      }
      if (row.schema != null && row.schema!=='') {
        const schema=Number(row.schema);
        if (!Number.isInteger(schema)||schema<0||(model?.schema_count!=null&&schema>=Number(model.schema_count))) throw new Error(tr('贴纸槽位数据不完整，请重新打开饰品。'));
        sticker.schema=schema;
      }
      stickers.push(sticker);
    }
    // Intentionally omit seed/wear/nametag/stattrak: unedited item metadata
    // is retained by the career service, never reconstructed from UI text.
    return {id,stickers};
  }
  function bindEditor(box,item,{command,onSaved,shop}={}) {
    const inspect=box.querySelector('[data-skin-inspect]');if(inspect)inspect.onclick=()=>root.CareerSkinInspect?.open(box,item,shop,{command,onSaved});
    const settings=box.querySelector('[data-skin-inspect-settings]');if(settings)settings.onclick=()=>{
      root.CareerSkinInspect?.close();
      box.closest?.('#collection-modal')?.remove();
      root.CareerUI?.go('settings');
    };
    const form=box.querySelector('[data-skin-craft-form]');if(!form)return;
    // Step is the arrow-key increment, not a requirement to round an existing
    // float from a saved item. makeCraftPayload validates the actual bounds.
    form.noValidate=true;
    let saving=false;
    const setRow = row => {
      const filled=Number(row.querySelector('[data-sticker-field="def"]').value)>0;
      row.querySelector('.skin-sticker-options').hidden=!filled;
      row.querySelectorAll('.skin-sticker-options input,.skin-sticker-options select').forEach(input=>input.disabled=!filled);
      row.querySelector('[data-sticker-remove]').disabled=!filled;
    };
    form.querySelectorAll('[data-sticker-slot]').forEach(row=>{
      row.querySelector('select').onchange=()=>setRow(row);
      row.querySelector('[data-sticker-remove]').onclick=()=>{row.querySelector('select').value='0';setRow(row);};
    });
    form.onsubmit=async event=>{
      event.preventDefault();if(saving||!canSticker(item))return;
      const status=form.querySelector('[data-craft-status]'), button=form.querySelector('[type="submit"]');
      try {
        const rows=[...form.querySelectorAll('[data-sticker-slot]')].map(row=>{
          const out={schema:row.dataset.stickerSchema,x:row.dataset.stickerX,y:row.dataset.stickerY};row.querySelectorAll('[data-sticker-field]').forEach(input=>out[input.dataset.stickerField]=input.value);return out;
        });
        const body=makeCraftPayload(item.id,rows,offsetModel(item,shop));saving=true;button.disabled=true;status.textContent=tr('正在保存…');
        const out=await command('/api/skins/craft',body);
        if(out && out.ok!==false){status.textContent=tr('贴纸已保存。');onSaved?.(item.id);}
        else {status.textContent=tr(out?.msg||'保存未完成，请重试。');button.disabled=false;}
      } catch(error){status.textContent=tr(error.message);button.disabled=false;}
      finally{saving=false;}
    };
  }
  function packState(pack) {
    const available=Array.isArray(pack?.items)&&pack.items.length>0;
    return {available,disabled:!!pack?.imported||!available,label:pack?.imported?'已入库':available?'免费导入':'等待配装数据'};
  }
  function packItem(item,shop) {
    const wear=item.wear??item.defaults?.wear,seed=item.seed??item.defaults?.seed;
    return '<li><b data-no-i18n>'+escape(field(item,'name')||item.skin_id||item.id||'—')+'</b>'+
      (wear==null?'':'<small>'+escape(tr(item.wear==null||item.parameter_origin?.wear==='declared_default'?'默认磨损':'磨损'))+' '+number(wear,5)+'</small>')+
      (seed==null?'':'<small>'+escape(tr(item.seed==null||item.parameter_origin?.seed==='declared_default'?'默认图案':'图案模板'))+' '+number(seed)+'</small>')+
      ((item.stickers||[]).length?'<small>'+escape(tr('贴纸'))+' '+item.stickers.map(s=>escape(stickerName(s.def,shop))).join(' / ')+'</small>':'')+'</li>';
  }
  function packs(shop) {
    const rows=Array.isArray(shop?.loadout_packs)?shop.loadout_packs:[];
    if(!rows.length)return '';
    return '<section class="skin-loadouts" aria-label="'+escape(tr('选手配装 · 免费'))+'"><div class="skin-loadout-heading"><h3>'+escape(tr('选手配装 · 免费'))+'</h3><p class="hint">'+escape(tr('导入模拟外观，不是 Steam 物品，不扣余额，也不会替换当前装备。'))+'</p></div><div class="skin-loadout-grid">'+rows.map(pack=>{
      const state=packState(pack), source=safeSource(pack.source_url), count=Number.isInteger(Number(pack.count))?Number(pack.count):(pack.items||[]).length;
      const displayName=pack.display_name||field(pack,'name')||pack.player;
      return '<article class="skin-loadout-card" data-ui-key="loadout-'+escape(pack.id)+'"><div class="skin-loadout-title"><b data-no-i18n>'+escape(displayName)+'</b><span>'+escape(tr('免费'))+'</span></div><p data-no-i18n>'+escape(field(pack,'description'))+'</p><dl><div><dt>'+escape(tr(pack.source_date_kind==='date_checked_not_match_date'?'核对日期':'资料日期'))+'</dt><dd>'+escape(pack.source_date||'—')+'</dd></div><div><dt>'+escape(tr('饰品数量'))+'</dt><dd>'+number(count)+'</dd></div></dl><details><summary>'+escape(tr('查看配装清单'))+'</summary>'+(state.available?'<ul>'+pack.items.map(item=>packItem(item,shop)).join('')+'</ul>':'<p class="hint">'+escape(tr('尚无已核对的配装物品，暂不能导入。'))+'</p>')+'</details><div class="skin-loadout-actions"><button class="btn" data-loadout-import="'+escape(pack.id)+'" '+(state.disabled?'disabled':'')+'>'+escape(tr(state.label))+'</button>'+(source?'<a class="text-link" href="'+escape(source)+'" target="_blank" rel="noopener noreferrer">'+escape(tr('查看来源'))+' ↗</a>':'')+'</div><p data-loadout-status role="status" aria-live="polite"></p></article>';
    }).join('')+'</div></section>';
  }
  function bindPacks(host,{command}={}) {
    let importing=false;
    host.querySelectorAll('[data-loadout-import]').forEach(button=>button.onclick=async()=>{
      if(importing||button.disabled)return;importing=true;
      const buttons=[...host.querySelectorAll('[data-loadout-import]')], prior=buttons.map(b=>b.disabled);
      buttons.forEach(b=>b.disabled=true);
      const status=button.closest('.skin-loadout-card').querySelector('[data-loadout-status]');status.textContent=tr('正在导入…');
      try {const out=await command('/api/skins/loadout',{id:button.dataset.loadoutImport});if(out&&out.ok!==false){button.textContent=tr('已入库');button.disabled=true;buttons.forEach((b,i)=>{if(b!==button)b.disabled=prior[i];});status.textContent=tr('已加入库存，可自行装备。');}else{status.textContent=tr(out?.msg||'导入未完成，请重试。');buttons.forEach((b,i)=>b.disabled=prior[i]);}}
      catch(error){status.textContent=tr(error.message);buttons.forEach((b,i)=>b.disabled=prior[i]);}
      finally{importing=false;}
    });
  }
  const api={details,bindEditor,packs,bindPacks,makeCraftPayload,packState,safeSource,integrationLinks,rowsFor,offsetModel};
  root.CareerSkinCrafts=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
