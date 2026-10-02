/* Hosted viewer protocol adapted from Ian Lucas's inventory-simulator (MIT).
 * Copyright (c) 2023 - present Ian Lucas.
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
 * of the Software, and to permit persons to whom the Software is furnished to
 * do so, subject to the following conditions: The above copyright notice and
 * this permission notice shall be included in all copies or substantial portions
 * of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
 * KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
 * DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
 * ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
 * DEALINGS IN THE SOFTWARE.
 *
 * No viewer/assets are bundled. Loading is opt-in. Only one appearance crosses
 * the iframe boundary; career/Steam identities and the inventory stay local. */
((root) => {
  'use strict';
  const ORIGIN='https://3d.cstrike.app', URL_VIEW=ORIGIN+'/view', SOURCE='3d.cstrike.app', VERSION=1;
  const tr=s=>root.CareerI18n?.t(s)??s;
  const field=(row,key)=>root.CareerI18n?.field(row,key)??row?.[key]??'';
  const escape=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const record=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
  const own=(o,k)=>record(o)&&Object.prototype.hasOwnProperty.call(o,k);
  const numeric=v=>typeof v==='number'&&Number.isFinite(v);
  const integer=v=>numeric(v)&&Number.isInteger(v)&&v>=0;
  const clone=v=>JSON.parse(JSON.stringify(v));
  const fail=s=>{throw new Error(tr(s));};
  const kits=shop=>Array.isArray(shop?.stickers)?shop.stickers:Array.isArray(shop?.stickers?.list)?shop.stickers.list:[];
  const enabled=shop=>shop?.skin_integration?.inspect_enabled===true;
  function checkedModel(value){
    if(!record(value))return null;
    if(!['x_min','x_max','y_min','y_max','rotation_min','rotation_max'].every(k=>numeric(value[k])))return null;
    if(value.x_min>value.x_max||value.y_min>value.y_max||value.rotation_min>value.rotation_max||!integer(value.schema_count)||value.schema_count<1||value.schema_count>32)return null;
    return {...value};
  }
  function prepare(item,shop){
    const catalog=shop?.inspect_catalog;
    if(!record(catalog)||catalog.embed_url!==URL_VIEW)fail('3D 检视目录尚未加载。');
    const key=String(item.def)+':'+String(item.paint??0), id=catalog.items?.[key];
    if(!own(catalog.items,key)||!integer(id))fail('此饰品暂不支持在线 3D 检视。');
    const reverse={};
    for(const [kit,lib]of Object.entries(catalog.stickers||{})){
      if(!integer(lib)||!/^\d+$/.test(kit)||Number(kit)<=0)continue;
      if(own(reverse,String(lib))&&reverse[lib]!==Number(kit))fail('贴纸检视目录存在重复映射。');
      reverse[lib]=Number(kit);
    }
    const appearance={id}, stickers={};
    // All other item fields are deliberately excluded, including its local id,
    // nameTag, account, equips, prices and the rest of the inventory.
    if(item.seed!=null){if(!integer(item.seed))fail('饰品外观参数无效。');appearance.seed=item.seed;}
    if(item.wear!=null){if(!numeric(item.wear)||item.wear<0||item.wear>1)fail('饰品外观参数无效。');appearance.wear=item.wear;}
    const stat=item.stattrak??item.stat_trak;
    if(stat!=null){if(stat===true)appearance.statTrak=0;else if(stat!==false){if(!integer(stat))fail('饰品外观参数无效。');appearance.statTrak=stat;}}
    const model=checkedModel(item.inspect_model)||checkedModel(catalog.models?.[String(id)]);
    const prepared={localId:item.id,expectedId:id,appearance,model,reverse,catalog,editable:!!model&&item.sticker_capable!==false&&!['knife','gloves','agents','music','graffiti'].includes(item.slot)};
    if(item.stickers!=null&&!Array.isArray(item.stickers))fail('贴纸槽位数据不完整，请重新打开饰品。');
    for(const sticker of item.stickers||[]){
      const slot=sticker.slot, lib=catalog.stickers?.[String(sticker.def)];
      if(!integer(slot)||slot>4||own(stickers,String(slot)))fail('贴纸槽位数据不完整，请重新打开饰品。');
      if(!own(catalog.stickers,String(sticker.def))||!integer(lib))fail('已有贴纸暂不支持 3D；请使用高级贴纸编辑，原贴纸不会移除。');
      const mapped={id:lib};
      for(const k of ['wear','rotation','x','y','schema'])if(sticker[k]!=null)mapped[k]=sticker[k];
      stickers[slot]=mapped;
    }
    if(Object.keys(stickers).length)appearance.stickers=stickers;
    validateState({item:appearance,schemaCount:model?.schema_count??0,activeSticker:null},prepared);
    return prepared;
  }
  function buildSrc(appearance,catalog){
    if(catalog?.embed_url!==URL_VIEW)fail('3D 检视目录尚未加载。');
    const url=new URL(URL_VIEW);url.searchParams.set('halfRotation','1');url.searchParams.set('item',JSON.stringify(appearance));return url.href;
  }
  function validateState(state,prepared){
    if(!record(state)||!record(state.item)||!integer(state.item.id)||state.item.id!==prepared.expectedId)fail('检视中的饰品已变化，请关闭后重新打开。');
    if(!integer(state.schemaCount)||state.schemaCount!==(prepared.model?.schema_count??0))fail('3D 模型与贴纸目录不一致，请使用高级贴纸编辑。');
    const value=state.item.stickers;
    if(value!=null&&!record(value))fail('3D 返回的贴纸数据无效，未保存。');
    const entries=Object.entries(value||{});
    if(entries.length>5)fail('3D 返回的贴纸数据无效，未保存。');
    for(const [key,s]of entries){
      if(!/^[0-4]$/.test(key)||!record(s)||!integer(s.id)||!own(prepared.reverse,String(s.id)))fail('3D 返回的贴纸数据无效，未保存。');
      for(const [k,min,max]of [['wear',0,1],['rotation',prepared.model?.rotation_min??-180,prepared.model?.rotation_max??180],['x',prepared.model?.x_min,prepared.model?.x_max],['y',prepared.model?.y_min,prepared.model?.y_max]]){
        if(s[k]==null)continue;
        if(!numeric(s[k])||(min!=null&&s[k]<min)||(max!=null&&s[k]>max)||((k==='x'||k==='y')&&!prepared.model))fail('3D 返回的贴纸位置超出模型范围，未保存。');
      }
      if(s.schema!=null&&(!integer(s.schema)||!prepared.model||s.schema>=prepared.model.schema_count))fail('3D 返回的贴纸锚点无效，未保存。');
    }
    if(state.activeSticker!=null&&(!integer(state.activeSticker)||state.activeSticker>4))fail('3D 返回的贴纸数据无效，未保存。');
    return state;
  }
  function toCraft(state,prepared){
    validateState(state,prepared);
    if(!prepared.editable)fail('此类饰品不支持贴纸。');
    return {id:prepared.localId,stickers:Object.entries(state.item.stickers||{}).sort(([a],[b])=>Number(a)-Number(b)).map(([slot,s])=>{
      const row={slot:Number(slot),def:prepared.reverse[s.id],wear:s.wear??0,rotation:s.rotation??0};
      for(const k of ['x','y','schema'])if(s[k]!=null)row[k]=s[k];
      return row;
    })};
  }
  // A small protocol client, not a second inventory store. Correlation ids are
  // scoped to this iframe and a state reply cannot be satisfied by a change.
  function createClient(iframe,{host=root,onEvent=()=>{}}={}){
    let destroyed=false,ready=false,serial=0;
    const pending=new Map(),timers=new Set();
    const setTimer=(fn,ms)=>{const id=host.setTimeout(()=>{timers.delete(id);fn();},ms);timers.add(id);return id;};
    const clearTimer=id=>{if(id!=null){host.clearTimeout(id);timers.delete(id);}};
    const send=(type,data,id)=>{
      if(destroyed||(!ready&&type!=='ping'))return false;
      const envelope={source:SOURCE,v:VERSION,type};if(data!==undefined)envelope.data=data;if(id!==undefined)envelope.id=id;
      iframe.contentWindow?.postMessage(envelope,ORIGIN);return !!iframe.contentWindow;
    };
    const onLoad=()=>send('ping');
    const onMessage=event=>{
      if(destroyed||event.origin!==ORIGIN||event.source!==iframe.contentWindow)return;
      const m=event.data;if(!record(m)||m.source!==SOURCE||m.v!==VERSION||typeof m.type!=='string')return;
      if(m.type==='state'&&typeof m.id==='string'&&pending.has(m.id)){
        const entry=pending.get(m.id);pending.delete(m.id);clearTimer(entry.timer);entry.resolve(m.data);return;
      }
      if(m.id!==undefined)return;
      if(m.type==='ready'){if(ready)return;ready=true;onEvent('ready',m.data);}
      else if(ready&&['change','rendered','loading','unsupported','rateLimited'].includes(m.type))onEvent(m.type,m.data);
    };
    host.addEventListener('message',onMessage);iframe.addEventListener('load',onLoad);send('ping');
    const api={
      get ready(){return ready;},get destroyed(){return destroyed;},send,
      getState(timeout=6000){
        if(destroyed||!ready)return Promise.reject(new Error(tr('3D 检视尚未就绪。')));
        const id=(host.crypto?.randomUUID?.()||'inspect')+'-'+(++serial);
        return new Promise((resolve,reject)=>{
          const timer=setTimer(()=>{pending.delete(id);reject(new Error(tr('3D 检视没有回应，未保存。')));},timeout);
          pending.set(id,{resolve,reject,timer});send('getState',undefined,id);
        });
      },
      destroy(){
        if(destroyed)return;destroyed=true;ready=false;host.removeEventListener('message',onMessage);iframe.removeEventListener('load',onLoad);
        for(const entry of pending.values()){clearTimer(entry.timer);entry.reject(new Error(tr('3D 检视已关闭。')));}pending.clear();
        for(const timer of timers)host.clearTimeout(timer);timers.clear();
      }
    };return api;
  }
  let current=null;
  function close(){current?.close();}
  function open(owner,item,shop,{command,onSaved}={}){
    close();let prepared;
    if(!enabled(shop)){
      const status=owner.querySelector('[data-inspect-entry-status]');
      if(status)status.textContent=tr('在线 3D 默认关闭，请在游戏设置中主动启用。');
      return null;
    }
    try{prepared=prepare(item,shop);}catch(error){const status=owner.querySelector('[data-inspect-entry-status]');if(status)status.textContent=error.message;return null;}
    const doc=root.document,mask=doc.createElement('div');mask.className='skin-inspect-mask';
    const supported=kits(shop).filter(s=>own(prepared.catalog.stickers,String(s.def))&&integer(prepared.catalog.stickers[s.def]));
    mask.innerHTML='<section class="skin-inspect-dialog" role="dialog" aria-modal="true" aria-label="'+escape(tr('3D 检视／直接贴纸'))+'" tabindex="-1"><header><div><h2 data-no-i18n>'+escape(field(item,'name'))+'</h2><p>'+escape(tr('在线 3D 检视 · 免费'))+'</p></div><button class="btn" data-inspect-close>'+escape(tr('返回饰品'))+'</button></header><div class="skin-inspect-body"><div class="skin-inspect-stage"><div data-inspect-frame></div><p class="skin-inspect-instructions">'+escape(tr('拖动贴纸可移动；悬停贴纸滚轮旋转。拖动空白处转枪，滚轮缩放。'))+'</p></div>'+(prepared.editable?'<aside class="skin-inspect-tools"><h3>'+escape(tr('贴纸槽位'))+'</h3><div class="skin-inspect-slots" data-inspect-slots></div><div class="skin-inspect-adjust"><button class="btn sm" data-inspect-remove>'+escape(tr('移除贴纸'))+'</button><button class="btn sm" data-inspect-preset>'+escape(tr('下个预设位置'))+'</button><label>'+escape(tr('贴纸磨损'))+' <output data-inspect-wear-value>0.00</output><input type="range" min="0" max="1" step="0.01" value="0" data-inspect-wear></label></div><h3>'+escape(tr('选择贴纸'))+'</h3><input type="search" data-inspect-search placeholder="'+escape(tr('搜索贴纸'))+'"><div class="skin-inspect-palette" data-inspect-palette></div></aside>':'')+'</div><footer><p data-inspect-status role="status" aria-live="polite">'+escape(tr('正在加载在线 3D；外网不可用时可返回高级贴纸编辑。'))+'</p>'+(prepared.editable?'<button class="btn primary" data-inspect-save disabled>'+escape(tr('保存当前贴纸'))+'</button>':'')+'</footer></section>';
    owner.append(mask);
    const frame=doc.createElement('iframe');frame.title=tr('3D 饰品检视');frame.referrerPolicy='no-referrer';frame.setAttribute('sandbox','allow-scripts allow-same-origin');frame.src=buildSrc(prepared.appearance,prepared.catalog);mask.querySelector('[data-inspect-frame]').append(frame);
    const status=mask.querySelector('[data-inspect-status]'),save=mask.querySelector('[data-inspect-save]');
    const originalFocus=doc.activeElement;
    let disposed=false,fault=false,loading=true,rendered=false,operating=false,saving=false,slot=0,state=null,expected=null,mutationTimer=null;
    const text=s=>{if(!disposed)status.textContent=tr(s);};
    const setDisabled=()=>{
      const disabled=disposed||fault||loading||!rendered||operating||saving||!client.ready;
      mask.querySelectorAll('.skin-inspect-tools button,.skin-inspect-tools input').forEach(b=>b.disabled=disabled||!!expected);
      const occupied=!!state?.item.stickers?.[slot];
      for(const name of ['remove','preset','wear']){const b=mask.querySelector('[data-inspect-'+name+']');if(b)b.disabled=disabled||!occupied||(name!=='wear'&&!!expected);}
      if(save)save.disabled=disabled||!!expected;
      frame.style.pointerEvents=operating||saving||fault?'none':'';
    };
    const updateSlots=()=>{
      const host=mask.querySelector('[data-inspect-slots]');if(!host)return;
      host.innerHTML=Array.from({length:5},(_,i)=>{
        const row=state?.item.stickers?.[i],kit=row?prepared.reverse[row.id]:null,name=row?field(supported.find(s=>Number(s.def)===kit),'name'):tr('空槽位');
        return '<button class="'+(i===slot?'active':'')+'" data-inspect-slot="'+i+'" aria-pressed="'+(i===slot)+'"><span>'+(i+1)+'</span><b data-no-i18n>'+escape(name||'#'+kit)+'</b></button>';
      }).join('');
      host.querySelectorAll('button').forEach(b=>b.onclick=()=>{slot=Number(b.dataset.inspectSlot);client.send('setActiveSticker',{index:state?.item.stickers?.[slot]?slot:null});updateSlots();});
      const wear=mask.querySelector('[data-inspect-wear]');wear.value=expected?.[slot]?.wear??state?.item.stickers?.[slot]?.wear??0;
      mask.querySelector('[data-inspect-wear-value]').textContent=Number(wear.value).toFixed(2);setDisabled();
    };
    const matches=()=>expected&&Object.keys(expected).every(key=>{
      const wanted=expected[key],got=state?.item.stickers?.[key];
      if(wanted===null)return !got;
      return got&&Object.entries(wanted).every(([k,v])=>(['wear','rotation','x','y'].includes(k)?(got[k]??0):k==='schema'?(got[k]??Number(key)%prepared.model.schema_count):got[k])===v);
    });
    const accept=value=>{
      if(disposed||fault)return;
      if((loading||!rendered)&&value?.schemaCount===0&&prepared.model)return;
      validateState(value,prepared);
      state={item:{...prepared.appearance,stickers:{}},schemaCount:value.schemaCount,activeSticker:value.activeSticker??null};
      for(const [key,s]of Object.entries(value.item.stickers||{})){const row={id:s.id};for(const k of ['wear','rotation','x','y','schema'])if(s[k]!=null)row[k]=s[k];state.item.stickers[key]=row;}
      if(matches()){expected=null;operating=false;root.clearTimeout(mutationTimer);mutationTimer=null;client.send('setActiveSticker',{index:state.item.stickers?.[slot]?slot:null});}
      updateSlots();setDisabled();
    };
    const errorOut=message=>{
      if(disposed)return;fault=true;operating=false;expected=null;root.clearTimeout(mutationTimer);text(message);setDisabled();
    };
    const client=createClient(frame,{onEvent:(type,data)=>{
      if(disposed||fault)return;
      try{
        if(type==='ready')text('3D 已连接，正在加载模型…');
        else if(type==='loading'){if(typeof data?.busy!=='boolean')return;loading=data.busy;setDisabled();}
        else if(type==='rendered'){
          if(!record(data?.item)||data.item.id!==prepared.expectedId)fail('检视中的饰品已变化，请关闭后重新打开。');
          loading=false;rendered=true;root.clearTimeout(readyTimer);text(prepared.editable?'选择贴纸后，可直接在枪身上拖动和旋转。':'此饰品支持 3D 检视，不支持贴纸。');setDisabled();
          client.getState().then(accept).catch(e=>errorOut(e.message));
        }else if(type==='change'){
          // The hosted viewer can announce its parsed item before loading the
          // model, temporarily reporting zero anchors. Do not call that a
          // corrupted model or allow it to save; rendered triggers a fresh pull.
          if(!rendered&&data?.schemaCount===0&&prepared.model)return;
          accept(data);
        }
        else if(type==='unsupported')errorOut('在线 3D 无法渲染此饰品，可返回高级贴纸编辑；未改动库存。');
        else if(type==='rateLimited')errorOut('在线 3D 请求暂受限，请稍后重新打开；未扣费、未保存。');
      }catch(error){errorOut(error.message);}
    }});
    const readyTimer=root.setTimeout(()=>{if(!rendered)errorOut('在线 3D 加载超时，可返回高级贴纸编辑；未改动库存。');},45000);
    const mutate=async(change,required)=>{
      if(disposed||fault||operating||saving||expected||!rendered)return;
      operating=true;setDisabled();
      try{
        const fresh=validateState(await client.getState(),prepared);if(disposed||fault)return;
        accept(fresh);const next={stickers:{}};
        for(const [key,s]of Object.entries(state.item.stickers||{})){next.stickers[key]={id:s.id};for(const k of ['wear','rotation','x','y','schema'])if(s[k]!=null)next.stickers[key][k]=s[k];}
        change(next);
        // Never echo viewer-added metadata back across the boundary.
        const appearance={...prepared.appearance,stickers:next.stickers};expected=required(appearance);
        client.send('setItem',{item:appearance});
        mutationTimer=root.setTimeout(()=>errorOut('3D 编辑没有确认，请重新打开；未保存。'),12000);
        client.getState().then(accept).catch(e=>errorOut(e.message));
      }catch(error){errorOut(error.message);}
    };
    const palette=()=>{
      const host=mask.querySelector('[data-inspect-palette]');if(!host)return;
      const query=mask.querySelector('[data-inspect-search]').value.toLowerCase();
      host.innerHTML=supported.filter(s=>(field(s,'name')+' '+s.name_en).toLowerCase().includes(query)).map(s=>{
        const url=prepared.catalog.images?.[s.def]||s.image;let image='';try{const u=new URL(url);if(u.protocol==='https:'&&!u.username&&!u.password)image='<img src="'+escape(u.href)+'" alt="" loading="lazy" referrerpolicy="no-referrer">';}catch(_){}
        return '<button data-inspect-kit="'+Number(s.def)+'">'+image+'<span data-no-i18n>'+escape(field(s,'name'))+'</span></button>';
      }).join('');
      host.querySelectorAll('[data-inspect-kit]').forEach(b=>b.onclick=()=>{
        const lib=prepared.catalog.stickers[b.dataset.inspectKit],target=slot,row={id:lib,wear:0,rotation:0,x:0,y:0,schema:target%prepared.model.schema_count};
        mutate(next=>{next.stickers[target]=row;},()=>({[target]:row}));
      });setDisabled();
    };
    if(prepared.editable){
      mask.querySelector('[data-inspect-search]').oninput=palette;palette();
      mask.querySelector('[data-inspect-remove]').onclick=()=>{const target=slot;mutate(next=>{delete next.stickers[target];},()=>({[target]:null}));};
      mask.querySelector('[data-inspect-preset]').onclick=async()=>{
        if(operating||saving||fault||expected)return;operating=true;setDisabled();
        try{const fresh=validateState(await client.getState(),prepared);if(disposed||fault)return;accept(fresh);const row=state.item.stickers?.[slot];if(!row){operating=false;setDisabled();return;}
          const schema=((row.schema??slot)%prepared.model.schema_count+1)%prepared.model.schema_count;expected={[slot]:{id:row.id,schema}};
          client.send('setStickerSchema',{index:slot,schema});mutationTimer=root.setTimeout(()=>errorOut('3D 编辑没有确认，请重新打开；未保存。'),12000);
          client.getState().then(accept).catch(e=>errorOut(e.message));
        }catch(error){errorOut(error.message);}
      };
      const wear=mask.querySelector('[data-inspect-wear]');wear.oninput=()=>{
        if(operating||saving||fault)return;
        const value=Number(wear.value),row=state?.item.stickers?.[slot];if(!row)return;
        expected={[slot]:{id:row.id,wear:value}};root.clearTimeout(mutationTimer);
        mutationTimer=root.setTimeout(()=>errorOut('3D 编辑没有确认，请重新打开；未保存。'),12000);
        mask.querySelector('[data-inspect-wear-value]').textContent=value.toFixed(2);client.send('setStickerWear',{index:slot,wear:value});setDisabled();
      };
      save.onclick=async()=>{
        if(save.disabled||saving)return;saving=true;setDisabled();text('正在读取当前 3D 贴纸并保存…');
        try{
          // A last change event or cached snapshot is never sufficient to save.
          const fresh=await client.getState();if(disposed||fault)return;
          if(loading||!rendered||operating)fail('3D 检视尚未就绪。');
          const body=toCraft(fresh,prepared);if(expected)fail('3D 编辑尚未确认，未保存。');
          const out=await command('/api/skins/craft',body);if(disposed)return;
          if(out&&out.ok!==false){controller.close();onSaved?.(item.id);}
          else{text(out?.msg||'保存未完成，请重试。');saving=false;setDisabled();}
        }catch(error){if(!disposed){text(error.message);saving=false;setDisabled();}}
      };
    }
    const onKey=e=>{if(e.key==='Escape'){e.preventDefault();e.stopImmediatePropagation();controller.close();}};
    const onBack=()=>controller.close();
    const observer=new root.MutationObserver(()=>{if(!owner.isConnected||!mask.isConnected)controller.close();});
    const controller={close(){
      if(disposed)return;disposed=true;client.destroy();root.clearTimeout(readyTimer);root.clearTimeout(mutationTimer);observer.disconnect();
      doc.removeEventListener('keydown',onKey,true);root.removeEventListener('popstate',onBack);root.removeEventListener('beforeunload',onBack);frame.remove();mask.remove();
      if(current===controller)current=null;if(originalFocus?.isConnected)originalFocus.focus();
    },client,frame};
    current=controller;mask.querySelector('[data-inspect-close]').onclick=()=>controller.close();mask.onclick=e=>{if(e.target===mask)controller.close();};
    doc.addEventListener('keydown',onKey,true);root.addEventListener('popstate',onBack);root.addEventListener('beforeunload',onBack);observer.observe(doc.body,{childList:true,subtree:true});
    setDisabled();mask.querySelector('section').focus();return controller;
  }
  const api={enabled,prepare,buildSrc,validateState,toCraft,createClient,open,close,ORIGIN,SOURCE,VERSION};
  root.CareerSkinInspect=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
