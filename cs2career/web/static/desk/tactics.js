/* Map-bound tactical drafts are independent of careers. Explicit commands write
 * the tactic library; ordinary state refreshes never rebuild the editor. */
((root)=>{
  'use strict';
  const COLORS=['#ffad65','#65d6bc','#82adff','#cc9aff','#f592b5'];
  const DUTIES=[['auto','自动分配'],['awp','主狙'],['entry','突破'],['lurk','自由人'],['rifle','步枪手'],['igl','指挥']];
  const MAPS=[['dust2','Dust II'],['mirage','Mirage'],['inferno','Inferno'],['nuke','Nuke'],['ancient','Ancient'],['anubis','Anubis'],['overpass','Overpass'],['train','Train'],['vertigo','Vertigo'],['cache','Cache']].map(([map,name])=>({map:'de_'+map,name}));
  const MAP_IMAGE=/^\/tactical_maps\/(de_(?:dust2|mirage|inferno|nuke|ancient|anubis|overpass|train|vertigo|cache))(?:_lower)?\.png$/;
  const clone=value=>JSON.parse(JSON.stringify(value));
  const esc=value=>String(value??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const record=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
  const finite=value=>typeof value==='number'&&Number.isFinite(value);
  const tr=value=>root.CareerI18n?.t(value)??value;
  const error=message=>{throw new Error(tr(message));};
  const entries=new WeakMap();
  root.CareerI18n?.register('en',{phrases:{
    '战术编辑器':'Tactic editor','五槽路线':'Five-slot routes','地图':'Map','雷达视图':'Radar view','实验功能，实际移动、等待和观察效果需进游戏验证。':'Experimental. Verify movement, waiting and observation in-game.',
    '路线、到点等待与箭头观察；下包后 T 守包、CT 回防。':'Routes, arrival waits and look arrows. After planting, T guards the site and CT retakes.',
    '分路、到点等待与箭头观察；交火优先原生 AI，下包后 T 守包、CT 回防。仅正式准备阶段选战术，不控制真人。':'Routes, arrival waits and look arrows; native combat takes priority. After planting, T guards and CT retakes. Select a tactic during official freeze time. The human player is never controlled.',
    '地图战术：分路、到点等待与箭头观察；交火优先原生 AI，下包后 T 守包、CT 回防。仅正式准备阶段选战术，不控制真人。':'Map tactics: routes, arrival waits and look arrows; native combat takes priority. After planting, T guards and CT retakes. Select a tactic during official freeze time. The human player is never controlled.',
    '雷达视图仅切换底图；每步层级请单独设置。':'Radar view changes the image only. Set each step’s level separately.',
    '不支持这张地图。':'This map is not supported.','地图列表无效，请重新读取。':'The map list is invalid. Refresh the library.',
    '战术包版本或地图无效。':'The tactic package version or map is invalid.','导入地图与当前地图不同，请先选择对应地图再导入。':'The import belongs to another map. Select that map before importing.',
    '读取的战术地图与所选地图不同。':'The loaded tactic map does not match the selected map.',
    '已保存战术':'Saved tactics','全部阵营':'Both sides','进攻方 T':'T side','防守方 CT':'CT side','重新读取':'Refresh library','新建':'New',
    'ID（聊天指令名）':'ID (chat command)','名称':'Name','阵营':'Side','保存战术':'Save tactic','删除战术':'Delete tactic','导入 JSON':'Import JSON','导出当前':'Export draft','导出全部':'Export library',
    '地图上点击添加步骤；拖动彩色点调整位置。':'Click the map to add a step; drag coloured points to move them.',
    '槽 1 是你（手动操作）；槽 2—5 是本场我方四名队友，按比赛请求顺序分配。':'Slot 1 is you (manual control). Slots 2–5 are your four teammates, in the match request order.',
    '路线分配':'Route assignment','名单顺序（兼容旧战术）':'Roster order (legacy tactics)','能力匹配':'Ability matching','真人手动槽位':'Your manual slot','槽位职责':'Slot duty',
    '自动分配':'Automatic duty','主狙':'AWP','突破':'Entry','自由人':'Lurk','步枪手':'Rifle','指挥':'IGL','能力匹配队友':'Teammate by ability',
    '能力模式按职责与选手能力分配 Bot；真人使用所选槽位，路线仅供参考，始终手动操作。':'Ability mode assigns bots by duty and player ability. Your selected slot is a route reference; you always retain manual control.',
    '职责可重复，可设置双狙。主狙按正常经济购买 AWP；钱不够时按正常购买流程选择武器。':'Duties may repeat, including two AWP slots. AWP duties buy an AWP through the normal economy; without enough money, normal weapon buying applies.',
    '分配模式需为 roster 或 ability。':'Assignment must be roster or ability.','真人槽位需为 1—5；名单顺序模式固定为槽 1。':'The human slot must be 1–5; roster order requires slot 1.','槽位职责无效。':'Invalid slot duty.',
    '经过点（不停留）':'Transit point (no hold)','最终到点后恢复原生决策':'Final arrival returns control to native AI','到点等待':'Arrival wait',
    '中途步骤等待为 0 时按经过点执行，不要求停稳；等待大于 0 才在点位停留。最后一步完成后恢复原生决策。':'Intermediate steps with zero wait are transit points and need no stop. Positive waits hold the position; completing the final step returns control to native AI.',
    '你 · 手动操作':'You · Manual','队友1':'Teammate 1','队友2':'Teammate 2','队友3':'Teammate 3','队友4':'Teammate 4',
    '将本槽路线复制到':'Copy this route to','全部其他槽':'All other slots','复制路线':'Copy route',
    '本槽步骤':'Steps in this slot','尚无步骤，点击地图开始。':'No steps yet. Click the map to start.',
    '选中步骤':'Selected step','等待（秒）':'Wait (seconds)','层级':'Level','自动判断':'Automatic','上层':'Upper','下层':'Lower',
    '到当前点':'Travel to this point','跑步（默认）':'Run (default)','跑步':'Run','静步':'Walk quietly','到点后等待（秒）':'Wait after arrival (seconds)',
    '移动方式只影响到当前目的地的这段路；等待秒数从到点后开始。':'Movement applies to the segment leading to this destination. The wait starts after arrival.',
    '移动方式需为 run 或 walk。':'Movement must be run or walk.',
    '设置观察方向':'Set look direction','取消观察方向':'Clear look direction','取消标记':'Cancel marking','移动位置':'Move position','观察目标':'Look target',
    '上移':'Move up','下移':'Move down','删除步骤':'Delete step','先选择或添加一个步骤。':'Select or add a step first.',
    '准备阶段聊天指令':'Freeze-time chat command','复制指令':'Copy command','旧的 rusha / rushb 指令仍可使用。':'The existing rusha / rushb commands remain available.',
    '正在读取战术…':'Loading tactics…','读取战术失败；可点重新读取。':'Could not load tactics. Click Refresh library to retry.',
    '地图图片加载失败，请先重新读取。':'The map image failed to load. Refresh the library first.',
    '地图转换信息无效，暂不能编辑。':'Map conversion metadata is invalid. Editing is unavailable.',
    '地图尚未加载。':'The map is not loaded yet.','当前草稿未保存':'Draft has unsaved changes','草稿尚未保存':'Draft not saved','已保存':'Saved',
    '在地图上点击要观察的位置；可先预瞄掩体后的方向。':'Click the map to choose a look target. Pre-aiming behind cover is allowed.',
    '每个槽最多 12 步。':'Each slot supports up to 12 steps.','战术已保存。':'Tactic saved.','正在保存战术…':'Saving tactic…',
    '保存失败，请重试。':'Could not save. Please retry.','已保存，但列表刷新失败，当前草稿保留。':'Saved, but the library refresh failed. Your draft is retained.',
    '战术已删除。':'Tactic deleted.','正在删除…':'Deleting…','删除失败，请重试。':'Could not delete. Please retry.',
    '已删除，但列表刷新失败；可点重新读取。':'Deleted, but the library refresh failed. Click Refresh library to retry.',
    '导入已完成。':'Import complete.','正在导入…':'Importing…','导入失败，请检查 JSON。':'Import failed. Check the JSON.',
    '已导入，但列表刷新失败；当前战术已保留。':'Imported, but the library refresh failed. The imported tactic is retained.',
    '导入文件过大，请拆分后导入。':'The import is too large. Split it into smaller files.','战术包含重复 ID。':'The tactic package contains duplicate IDs.',
    '导入包含同名 ID，会覆盖已有战术，继续？':'The import contains existing IDs. Replace those saved tactics?',
    '放弃当前未保存的修改？':'Discard the current unsaved changes?','此 ID 已存在，覆盖已保存战术？':'This ID already exists. Replace the saved tactic?',
    '删除这条已保存战术？不会改动生涯或比赛记录。':'Delete this saved tactic? Career and match records are unchanged.',
    '目标槽已有步骤，复制后将替换，继续？':'The target slot already has steps. Replace them with this route?',
    '路线已复制，记得保存战术。':'Route copied. Remember to save the tactic.','指令已复制。':'Command copied.','请手动复制下方指令。':'Copy the command below manually.',
    'ID 只能用 1—32 个小写字母、数字、下划线或短横线。':'Use 1–32 lowercase letters, digits, underscores or hyphens for the ID.',
    '名称需为 1—40 个字符。':'The name must contain 1–40 characters.','战术阵营需为 T 或 CT。':'The tactic side must be T or CT.',
    '战术需要 1—5 号各一个槽位。':'A tactic needs exactly one slot for each number from 1 to 5.',
    '步骤坐标需为两个有效数字。':'Step coordinates must contain two finite numbers.','等待需为 0—30 秒。':'Wait must be between 0 and 30 seconds.',
    '层级需为 auto、upper 或 lower。':'Level must be auto, upper or lower.',
    '导入内容需为一条战术或战术包。':'Import a single tactic or a tactic package.','自定义战术':'Custom tactic','已导出当前草稿。':'Draft exported.',
    '已导出全部已保存战术。':'Saved library exported.','没有已保存战术。':'No saved tactics.','没有符合筛选的战术。':'No tactics match this filter.'
  }});
  function checkMap(value){if(!MAPS.some(row=>row.map===value))error('不支持这张地图。');return value;}
  function checkMeta(value,map){
    const validImage=image=>typeof image==='string'&&MAP_IMAGE.test(image)&&(!map||MAP_IMAGE.exec(image)[1]===map);
    if(map)checkMap(map);
    if(!record(value)||!['pos_x','pos_y','scale','width','height'].every(k=>finite(value[k]))||value.scale<=0||value.width<=0||value.height<=0||!validImage(value.image))error('地图转换信息无效，暂不能编辑。');
    const inferred=MAP_IMAGE.exec(value.image)[1],layers=value.layers??[];
    if(!Array.isArray(layers)||layers.length>2)error('地图转换信息无效，暂不能编辑。');
    const ids=new Set(),cleanLayers=layers.map(layer=>{
      if(!record(layer)||!['upper','lower'].includes(layer.id)||ids.has(layer.id)||!validImage(layer.image)||MAP_IMAGE.exec(layer.image)[1]!==inferred||typeof layer.name!=='string'||!layer.name.trim())error('地图转换信息无效，暂不能编辑。');
      ids.add(layer.id);return {id:layer.id,image:layer.image,name:layer.name};
    });
    return {...value,layers:cleanLayers};
  }
  function worldToPixel(position,meta){return[(position[0]-meta.pos_x)/meta.scale,(meta.pos_y-position[1])/meta.scale];}
  function pixelToWorld(position,meta){return[meta.pos_x+position[0]*meta.scale,meta.pos_y-position[1]*meta.scale];}
  function coordinates(value){if(!Array.isArray(value)||value.length!==2||!value.every(finite))error('步骤坐标需为两个有效数字。');return [...value];}
  function normalize(value){
    if(!record(value))error('导入内容需为一条战术或战术包。');
    if(typeof value.id!=='string'||! /^[a-z0-9_-]{1,32}$/.test(value.id))error('ID 只能用 1—32 个小写字母、数字、下划线或短横线。');
    if(typeof value.name!=='string'||!value.name.trim()||value.name.trim().length>40)error('名称需为 1—40 个字符。');
    if(!['t','ct'].includes(value.side))error('战术阵营需为 T 或 CT。');
    const assignment=value.assignment===undefined?'roster':value.assignment,humanSlot=value.human_slot===undefined?1:value.human_slot;
    if(!['roster','ability'].includes(assignment))error('分配模式需为 roster 或 ability。');
    if(!Number.isInteger(humanSlot)||humanSlot<1||humanSlot>5||(assignment==='roster'&&humanSlot!==1))error('真人槽位需为 1—5；名单顺序模式固定为槽 1。');
    if(!Array.isArray(value.slots)||value.slots.length!==5)error('战术需要 1—5 号各一个槽位。');
    const found=new Set(),slots=value.slots.map(row=>{
      if(!record(row)||!Number.isInteger(row.slot)||row.slot<1||row.slot>5||found.has(row.slot)||!Array.isArray(row.steps))error('战术需要 1—5 号各一个槽位。');found.add(row.slot);
      if(row.steps.length>12)error('每个槽最多 12 步。');
      const duty=row.duty===undefined?'auto':row.duty;
      if(!DUTIES.some(([id])=>id===duty))error('槽位职责无效。');
      return {slot:row.slot,duty,steps:row.steps.map(step=>{
        if(!record(step))error('步骤坐标需为两个有效数字。');
        const position=coordinates(step.position),wait=step.wait??0,level=step.level??'auto',movement=step.movement===undefined?'run':step.movement;
        if(!finite(wait)||wait<0||wait>30)error('等待需为 0—30 秒。');
        if(!['auto','upper','lower'].includes(level))error('层级需为 auto、upper 或 lower。');
        if(!['run','walk'].includes(movement))error('移动方式需为 run 或 walk。');
        return {position,level,wait,movement,look_at:step.look_at==null?null:coordinates(step.look_at)};
      })};
    }).sort((a,b)=>a.slot-b.slot);
    return {id:value.id,name:value.name.trim(),side:value.side,assignment,human_slot:humanSlot,slots};
  }
  function parseImport(value,map='de_dust2'){
    checkMap(map);
    if(record(value)&&value.map!==undefined){checkMap(value.map);if(value.map!==map)error('导入地图与当前地图不同，请先选择对应地图再导入。');}
    if(record(value)&&value.tactic!==undefined)return {map,tactic:normalize(value.tactic)};
    if(record(value)&&value.tactics!==undefined){
      if(value.schema_version!==1||value.map!==map||!Array.isArray(value.tactics))error('战术包版本或地图无效。');
      const tactics=value.tactics.map(normalize),ids=new Set();for(const tactic of tactics){if(ids.has(tactic.id))error('战术包含重复 ID。');ids.add(tactic.id);}
      return {schema_version:1,map,tactics};
    }
    return {map,tactic:normalize(value)};
  }
  function fresh(side='t',taken=[]){let count=1,id='my_tactic';while(taken.some(row=>row.id===id))id='my_tactic_'+(++count);return{id,name:tr('自定义战术'),side,assignment:'roster',human_slot:1,slots:Array.from({length:5},(_,i)=>({slot:i+1,duty:'auto',steps:[]}))};}
  function mount(host){
    const state={map:'de_dust2',availableMaps:clone(MAPS),layer:'upper',draft:fresh(),base:null,originalId:null,slot:2,index:-1,lookMode:false,meta:null,list:[],busy:false,loaded:false,mapReady:false,drag:null,frame:null,slotLabels:['你 · 手动操作','队友1','队友2','队友3','队友4']};
    host.innerHTML='<div class="page-head"><h2>'+esc(tr('战术编辑器'))+'</h2><span class="hint">'+esc(tr('路线、到点等待与箭头观察；下包后 T 守包、CT 回防。'))+'</span></div><div class="tactics-layout"><aside class="tactics-library"><div class="tactics-library-title"><h3>'+esc(tr('已保存战术'))+'</h3><button class="btn sm" data-tactic-refresh>'+esc(tr('重新读取'))+'</button></div><label class="tactics-map-selector">'+esc(tr('地图'))+'<select data-tactic-map-select aria-label="'+esc(tr('地图'))+'">'+MAPS.map(row=>'<option value="'+row.map+'">'+esc(row.name)+'</option>').join('')+'</select></label><select data-tactic-filter aria-label="'+esc(tr('阵营'))+'"><option value="all">'+esc(tr('全部阵营'))+'</option><option value="t">'+esc(tr('进攻方 T'))+'</option><option value="ct">'+esc(tr('防守方 CT'))+'</option></select><div data-tactic-library></div></aside><section class="tactics-editor"><form data-tactic-form><div class="tactics-fields"><label>'+esc(tr('ID（聊天指令名）'))+'<input data-tactic-id required maxlength="32" pattern="[a-z0-9_-]{1,32}" spellcheck="false" autocomplete="off"></label><label>'+esc(tr('名称'))+'<input data-tactic-name required maxlength="40" autocomplete="off"></label><label>'+esc(tr('阵营'))+'<select data-tactic-side><option value="t">'+esc(tr('进攻方 T'))+'</option><option value="ct">'+esc(tr('防守方 CT'))+'</option></select></label></div><div class="tactics-toolbar"><button class="btn primary" type="submit" data-tactic-save>'+esc(tr('保存战术'))+'</button><button class="btn" type="button" data-tactic-new>'+esc(tr('新建'))+'</button><button class="btn" type="button" data-tactic-import>'+esc(tr('导入 JSON'))+'</button><button class="btn" type="button" data-tactic-export>'+esc(tr('导出当前'))+'</button><button class="btn" type="button" data-tactic-export-all>'+esc(tr('导出全部'))+'</button><button class="btn sm" type="button" data-tactic-delete>'+esc(tr('删除战术'))+'</button><input type="file" accept=".json,application/json" data-tactic-file hidden><small data-tactic-dirty></small></div><div class="tactics-slots">'+COLORS.map((color,i)=>'<button type="button" data-tactic-slot="'+(i+1)+'" style="--slot-color:'+color+'"><i></i><b>'+(i+1)+'</b><span data-tactic-count="'+(i+1)+'">0 / 12</span></button>').join('')+'</div><p class="hint tactics-slot-note">'+esc(tr('槽 1 是你（手动操作）；槽 2—5 是本场我方四名队友，按比赛请求顺序分配。'))+'</p><div class="tactics-workspace"><div class="tactics-map-panel"><div class="tactics-radar-controls" data-tactic-radar-controls hidden><label>'+esc(tr('雷达视图'))+'<select data-tactic-radar></select></label><span class="hint">'+esc(tr('雷达视图仅切换底图；每步层级请单独设置。'))+'</span></div><div class="tactics-map" data-tactic-map><img data-tactic-image alt="" draggable="false"><svg data-tactic-svg viewBox="0 0 1024 1024" role="application" aria-label="'+esc(tr('五槽路线'))+'"></svg></div><p class="hint">'+esc(tr('地图上点击添加步骤；拖动彩色点调整位置。'))+'</p><div class="tactics-copy"><label>'+esc(tr('将本槽路线复制到'))+'<select data-tactic-copy-to>'+COLORS.map((_,i)=>'<option value="'+(i+1)+'">'+(i+1)+'</option>').join('')+'<option value="all">'+esc(tr('全部其他槽'))+'</option></select></label><button class="btn sm" type="button" data-tactic-copy>'+esc(tr('复制路线'))+'</button></div></div><aside class="tactics-steps"><h3>'+esc(tr('本槽步骤'))+'</h3><div data-tactic-steps></div><div class="tactics-step-detail" data-tactic-detail hidden><h3>'+esc(tr('选中步骤'))+' <span data-tactic-step-number></span></h3><p><span>'+esc(tr('移动位置'))+'</span><code data-tactic-position></code></p><label>'+esc(tr('等待（秒）'))+'<input type="number" min="0" max="30" step="any" required data-tactic-wait></label><label>'+esc(tr('层级'))+'<select data-tactic-level><option value="auto">'+esc(tr('自动判断'))+'</option><option value="upper">'+esc(tr('上层'))+'</option><option value="lower">'+esc(tr('下层'))+'</option></select></label><p><span>'+esc(tr('观察目标'))+'</span><code data-tactic-look></code></p><div class="tactics-step-actions"><button class="btn sm" type="button" data-tactic-look-set>'+esc(tr('设置观察方向'))+'</button><button class="btn sm" type="button" data-tactic-look-clear>'+esc(tr('取消观察方向'))+'</button><button class="btn sm" type="button" data-tactic-up>'+esc(tr('上移'))+'</button><button class="btn sm" type="button" data-tactic-down>'+esc(tr('下移'))+'</button><button class="btn sm" type="button" data-tactic-step-delete>'+esc(tr('删除步骤'))+'</button></div></div><p class="hint" data-tactic-selection-note>'+esc(tr('先选择或添加一个步骤。'))+'</p></aside></div></form><div class="tactics-command"><div><span>'+esc(tr('准备阶段聊天指令'))+'</span><code data-tactic-command data-no-i18n></code></div><button class="btn sm" data-tactic-command-copy>'+esc(tr('复制指令'))+'</button><p class="hint">'+esc(tr('旧的 rusha / rushb 指令仍可使用。'))+'</p></div><p class="tactics-status" data-tactic-status role="status" aria-live="polite"></p><p class="hint tactics-runtime" data-tactic-runtime data-no-i18n></p></section></div>';
    const q=selector=>host.querySelector(selector),qa=selector=>[...host.querySelectorAll(selector)];
    const movementLabel=root.document.createElement('label');movementLabel.innerHTML=esc(tr('到当前点'))+'<select data-tactic-movement><option value="run">'+esc(tr('跑步（默认）'))+'</option><option value="walk">'+esc(tr('静步'))+'</option></select>';
    const movementNote=root.document.createElement('p');movementNote.className='hint tactics-movement-note';movementNote.textContent=tr('移动方式只影响到当前目的地的这段路；等待秒数从到点后开始。');
    const waitLabel=q('[data-tactic-wait]').closest('label');waitLabel.firstChild.textContent=tr('到点后等待（秒）');waitLabel.before(movementLabel,movementNote);
    const assignmentControls=root.document.createElement('div');assignmentControls.className='tactics-assignment';
    assignmentControls.innerHTML='<label>'+esc(tr('路线分配'))+'<select data-tactic-assignment><option value="roster">'+esc(tr('名单顺序（兼容旧战术）'))+'</option><option value="ability">'+esc(tr('能力匹配'))+'</option></select></label><label>'+esc(tr('真人手动槽位'))+'<select data-tactic-human-slot>'+COLORS.map((_,i)=>'<option value="'+(i+1)+'">'+(i+1)+'</option>').join('')+'</select></label><p class="hint" data-tactic-economy-note>'+esc(tr('职责可重复，可设置双狙。主狙按正常经济购买 AWP；钱不够时按正常购买流程选择武器。'))+'</p>';
    q('.tactics-fields').after(assignmentControls);
    qa('[data-tactic-slot]').forEach((button,i)=>{const card=root.document.createElement('div');card.className='tactic-slot-card';button.before(card);card.append(button);const dutyLabel=root.document.createElement('label');dutyLabel.className='tactic-slot-duty';dutyLabel.innerHTML=esc(tr('槽位职责'))+'<select data-tactic-duty="'+(i+1)+'" aria-label="'+(i+1)+' · '+esc(tr('槽位职责'))+'">'+DUTIES.map(([id,name])=>'<option value="'+id+'">'+esc(tr(name))+'</option>').join('')+'</select>';card.append(dutyLabel);});
    q('.tactics-slot-note').dataset.tacticAssignmentNote='';
    const transitNote=root.document.createElement('p');transitNote.className='hint tactics-transit-note';transitNote.textContent=tr('中途步骤等待为 0 时按经过点执行，不要求停稳；等待大于 0 才在点位停留。最后一步完成后恢复原生决策。');q('[data-tactic-steps]').after(transitNote);
    qa('[data-tactic-slot]').forEach((button,i)=>{const label=root.document.createElement('span');label.className='tactic-slot-label';label.dataset.tacticSlotLabel=String(i+1);label.textContent=tr(state.slotLabels[i]);button.insertBefore(label,button.querySelector('[data-tactic-count]'));});
    const row=()=>state.draft.slots[state.slot-1],step=()=>row().steps[state.index],dirty=()=>JSON.stringify(state.draft)!==state.base;
    const status=(message,bad=false)=>{q('[data-tactic-status]').textContent=tr(message);q('[data-tactic-status]').classList.toggle('bad',bad);};
    const updateDirty=()=>{q('[data-tactic-dirty]').textContent=tr(state.originalId?(dirty()?'当前草稿未保存':'已保存'):'草稿尚未保存');q('[data-tactic-command]').textContent='play '+(/^[a-z0-9_-]{1,32}$/.test(state.draft.id)?state.draft.id:'<id>');};
    const lock=()=>{
      qa('button,input,select').forEach(el=>el.disabled=state.busy);
      q('[data-tactic-delete]').disabled=state.busy||!state.originalId;
      q('[data-tactic-export-all]').disabled=state.busy||!state.list.length;
      q('[data-tactic-save]').disabled=state.busy||!state.meta;
      q('[data-tactic-copy]').disabled=state.busy||!row().steps.length;
      q('[data-tactic-human-slot]').disabled=state.busy||state.draft.assignment!=='ability';
      qa('[data-tactic-duty]').forEach(select=>select.disabled=state.busy);
      const selected=!!step();for(const key of ['wait','level','movement','look-set','look-clear','up','down','step-delete'])q('[data-tactic-'+key+']').disabled=state.busy||!selected;
      q('[data-tactic-up]').disabled=state.busy||state.index<=0;
      q('[data-tactic-down]').disabled=state.busy||state.index<0||state.index>=row().steps.length-1;
      q('[data-tactic-look-clear]').disabled=state.busy||!step()?.look_at;
      q('[data-tactic-wait]').required=selected;
      q('[data-tactic-svg]').classList.toggle('tactics-map-locked',state.busy||!state.mapReady);
    };
    const counts=()=>{qa('[data-tactic-slot]').forEach(b=>{const slot=Number(b.dataset.tacticSlot);b.classList.toggle('selected',slot===state.slot);b.setAttribute('aria-pressed',String(slot===state.slot));q('[data-tactic-count="'+slot+'"]').textContent=state.draft.slots[slot-1].steps.length+' / 12';});
      q('[data-tactic-copy-to] option[value="'+state.slot+'"]').disabled=true;qa('[data-tactic-copy-to] option').filter(o=>o.value!==String(state.slot)).forEach(o=>o.disabled=false);
      if(q('[data-tactic-copy-to]').value===String(state.slot))q('[data-tactic-copy-to]').value=String(state.slot===1?2:1);
    };
    const assignmentDetails=()=>{
      const ability=state.draft.assignment==='ability';q('[data-tactic-assignment]').value=state.draft.assignment;q('[data-tactic-human-slot]').value=String(state.draft.human_slot);
      q('[data-tactic-assignment-note]').textContent=tr(ability?'能力模式按职责与选手能力分配 Bot；真人使用所选槽位，路线仅供参考，始终手动操作。':'槽 1 是你（手动操作）；槽 2—5 是本场我方四名队友，按比赛请求顺序分配。');
      qa('[data-tactic-duty]').forEach(select=>{select.value=state.draft.slots[Number(select.dataset.tacticDuty)-1].duty;});
      qa('[data-tactic-slot-label]').forEach((label,i)=>{const manual=i+1===state.draft.human_slot;label.textContent=tr(ability?(manual?'你 · 手动操作':'能力匹配队友'):state.slotLabels[i]);label.closest('.tactic-slot-card').classList.toggle('manual',manual);});
    };
    const drawMap=()=>{
      state.frame=null;if(!state.meta)return;
      const meta=state.meta,svg=q('[data-tactic-svg]');
      svg.setAttribute('viewBox','0 0 '+meta.width+' '+meta.height);
      let h='<defs>'+COLORS.map((color,i)=>'<marker id="tactic-arrow-'+(i+1)+'" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="'+color+'"/></marker>').join('')+'</defs>';
      const slots=[...state.draft.slots].sort((a,b)=>(a.slot===state.slot?1:0)-(b.slot===state.slot?1:0));
      for(const entry of slots){
        const color=COLORS[entry.slot-1],points=entry.steps.map(s=>worldToPixel(s.position,meta));
        if(points.length>1)h+='<polyline points="'+points.map(p=>p.join(',')).join(' ')+'" fill="none" stroke="'+color+'" stroke-width="2" vector-effect="non-scaling-stroke" opacity="'+(entry.slot===state.slot?.95:.4)+'"/>';
        entry.steps.forEach((s,index)=>{
          const [x,y]=points[index],selected=entry.slot===state.slot&&index===state.index;
          if(s.look_at){const target=worldToPixel(s.look_at,meta);h+='<line x1="'+x+'" y1="'+y+'" x2="'+target[0]+'" y2="'+target[1]+'" stroke="'+color+'" stroke-width="1.5" stroke-dasharray="4 4" vector-effect="non-scaling-stroke" opacity="'+(selected?.9:.35)+'" marker-end="url(#tactic-arrow-'+entry.slot+')"/>'+(selected?'<circle cx="'+target[0]+'" cy="'+target[1]+'" r="8" fill="none" stroke="'+color+'" stroke-width="2" vector-effect="non-scaling-stroke"/>':'');}
          h+='<g data-tactic-node data-slot="'+entry.slot+'" data-step="'+index+'" class="'+(selected?'selected':'')+'"><circle cx="'+x+'" cy="'+y+'" r="26" fill="transparent"/><circle cx="'+x+'" cy="'+y+'" r="'+(selected?17:13)+'" fill="'+color+'" stroke="'+(selected?'#fff':'#15202a')+'" stroke-width="2" vector-effect="non-scaling-stroke"/><text x="'+x+'" y="'+(y+5)+'" text-anchor="middle" fill="#09131b" font-size="17" font-weight="700">'+(index+1)+'</text></g>';
        });
      }
      svg.innerHTML=h;svg.classList.toggle('mark-look',state.lookMode);
    };
    const scheduleMap=()=>{if(state.frame==null)state.frame=root.requestAnimationFrame(drawMap);};
    const listSteps=()=>{
      q('[data-tactic-steps]').innerHTML=row().steps.length?row().steps.map((s,i)=>'<button type="button" data-tactic-step="'+i+'" class="'+(i===state.index?'selected':'')+'"><b>'+(i+1)+'</b><span>'+s.position.map(v=>Math.round(v)).join(', ')+'<small>'+esc(tr(s.movement==='walk'?'静步':'跑步'))+' · '+esc(s.level==='auto'?tr('自动判断'):s.level==='upper'?tr('上层'):tr('下层'))+' · '+esc(s.wait>0?tr('到点等待')+' '+s.wait+'s':tr(i<row().steps.length-1?'经过点（不停留）':'最终到点后恢复原生决策'))+(s.look_at?' · ↗':'')+'</small></span></button>').join(''):'<p class="hint">'+esc(tr('尚无步骤，点击地图开始。'))+'</p>';
      qa('[data-tactic-step]').forEach(b=>b.onclick=()=>select(state.slot,Number(b.dataset.tacticStep)));
    };
    const details=()=>{
      const s=step();q('[data-tactic-detail]').hidden=!s;q('[data-tactic-selection-note]').hidden=!!s;
      q('[data-tactic-look-set]').textContent=tr(state.lookMode?'取消标记':'设置观察方向');
      if(s){q('[data-tactic-step-number]').textContent=state.slot+'.'+(state.index+1);q('[data-tactic-position]').textContent=s.position.map(v=>v.toFixed(1)).join(', ');q('[data-tactic-look]').textContent=s.look_at?s.look_at.map(v=>v.toFixed(1)).join(', '):'—';q('[data-tactic-wait]').value=s.wait;q('[data-tactic-wait]').setCustomValidity('');q('[data-tactic-level]').value=s.level;q('[data-tactic-movement]').value=s.movement;}lock();
    };
    const refreshEditor=()=>{counts();assignmentDetails();listSteps();details();drawMap();updateDirty();};
    function select(slot,index=-1){state.slot=slot;state.index=index;state.lookMode=false;refreshEditor();}
    const setDraft=(value,original=null)=>{const draft=normalize(value);state.drag=null;if(state.frame!=null){root.cancelAnimationFrame(state.frame);state.frame=null;}state.draft=draft;state.originalId=original;state.base=JSON.stringify(state.draft);state.slot=state.draft.slots.find(s=>s.slot!==state.draft.human_slot&&s.steps.length)?.slot||state.draft.slots.find(s=>s.slot!==state.draft.human_slot).slot;state.index=-1;state.lookMode=false;q('[data-tactic-id]').value=state.draft.id;q('[data-tactic-name]').value=state.draft.name;q('[data-tactic-side]').value=state.draft.side;refreshEditor();};
    const discard=()=>!dirty()||root.confirm(tr('放弃当前未保存的修改？'));
    const listLibrary=()=>{
      const filter=q('[data-tactic-filter]').value,rows=state.list.filter(t=>filter==='all'||t.side===filter);
      q('[data-tactic-library]').innerHTML=rows.length?rows.map(t=>'<button class="tactics-saved '+(t.id===state.originalId?'selected':'')+'" data-tactic-load="'+esc(t.id)+'"><b data-no-i18n>'+esc(t.name)+'</b><small data-no-i18n>'+t.side.toUpperCase()+' · '+esc(t.id)+' · '+t.slots.reduce((n,s)=>n+s.steps.length,0)+'</small></button>').join(''):'<p class="hint">'+esc(tr(state.list.length?'没有符合筛选的战术。':'没有已保存战术。'))+'</p>';
      qa('[data-tactic-load]').forEach(b=>b.onclick=()=>{if(state.busy||!discard())return;const found=state.list.find(t=>t.id===b.dataset.tacticLoad);if(found){setDraft(found,found.id);listLibrary();status('');}});lock();
    };
    const mapOptions=()=>{
      const select=q('[data-tactic-map-select]'),signature=JSON.stringify(state.availableMaps);
      if(select.dataset.options!==signature){select.replaceChildren(...state.availableMaps.map(row=>{const option=root.document.createElement('option');option.value=row.map;option.textContent=row.name;return option;}));select.dataset.options=signature;}
      select.value=state.map;
    };
    const radarOptions=()=>{
      const select=q('[data-tactic-radar]'),layers=state.meta?.layers??[],signature=JSON.stringify(layers);
      q('[data-tactic-radar-controls]').hidden=layers.length<2;
      if(select.dataset.options!==signature){select.replaceChildren(...layers.map(layer=>{const option=root.document.createElement('option');option.value=layer.id;option.textContent=tr(layer.name);return option;}));select.dataset.options=signature;}
      if(!layers.some(layer=>layer.id===state.layer))state.layer=layers.find(layer=>layer.id==='upper')?.id??layers[0]?.id??'upper';
      select.value=state.layer;
    };
    const showRadar=()=>{
      if(!state.meta)return;
      const image=q('[data-tactic-image]'),source=state.meta.layers.find(layer=>layer.id===state.layer)?.image??state.meta.image;
      image.alt=String(state.meta.name??state.availableMaps.find(row=>row.map===state.map)?.name??state.map);
      q('[data-tactic-map]').style.aspectRatio=state.meta.width+' / '+state.meta.height;
      if(image.dataset.mapSource!==source||(!state.mapReady&&image.complete)){const retry=image.dataset.mapSource===source;state.mapReady=false;image.style.visibility='hidden';image.dataset.mapSource=source;image.src=source+(retry?'?retry='+Date.now():'');}
      else if(image.complete&&image.naturalWidth){state.mapReady=true;image.style.visibility='';}
      lock();
    };
    const read=async(requestedMap=state.map)=>{
      checkMap(requestedMap);
      const data=await get('/api/tactics?map='+encodeURIComponent(requestedMap));
      if(!record(data)||data.schema_version!==1||!Array.isArray(data.tactics))error('战术包版本或地图无效。');
      if(data.map!==requestedMap)error('读取的战术地图与所选地图不同。');
      const meta=checkMeta(data.map_meta,requestedMap),list=data.tactics.map(normalize),availableMaps=data.available_maps===undefined?clone(MAPS):data.available_maps;
      if(!Array.isArray(availableMaps)||!availableMaps.length)error('地图列表无效，请重新读取。');
      const seen=new Set(),maps=availableMaps.map(row=>{if(!record(row)||!MAPS.some(known=>known.map===row.map)||seen.has(row.map)||typeof row.name!=='string'||!row.name.trim())error('地图列表无效，请重新读取。');seen.add(row.map);return {map:row.map,name:row.name};});
      if(!seen.has(requestedMap))error('地图列表无效，请重新读取。');
      // Prepare the entire response before committing, so failed reads retain
      // the old draft, library, coordinates and selected map as one unit.
      const changed=requestedMap!==state.map;
      state.map=requestedMap;state.meta=meta;state.list=list;state.availableMaps=maps;state.loaded=true;
      if(changed){state.layer='upper';setDraft(fresh('t',list));}
      mapOptions();radarOptions();showRadar();
      const note=String(data.runtime_note??'');if(root.CareerI18n?.bindLocalized)root.CareerI18n.bindLocalized(q('[data-tactic-runtime]'),{zh:note,en:root.CareerI18n.t(note,'en')});else q('[data-tactic-runtime]').textContent=note;
      if(Array.isArray(data.slot_labels)&&data.slot_labels.length===5&&data.slot_labels.every(v=>typeof v==='string'))state.slotLabels=[...data.slot_labels];assignmentDetails();
      listLibrary();drawMap();lock();return data;
    };
    const loading=async(requestedMap=state.map)=>{if(state.busy){mapOptions();return;}if(requestedMap!==state.map&&!discard()){mapOptions();return;}mapOptions();state.busy=true;lock();status('正在读取战术…');try{await read(requestedMap);status('');}catch(e){mapOptions();status(e.message||'读取战术失败；可点重新读取。',true);}finally{state.busy=false;lock();}};
    const send=async(path,body)=>{const result=await post(path,body,{render:false,quiet:true});if(!result||result.ok===false)throw new Error(result?.msg||tr('保存失败，请重试。'));return result;};
    q('[data-tactic-image]').onload=()=>{state.mapReady=true;q('[data-tactic-image]').style.visibility='';lock();};q('[data-tactic-image]').onerror=()=>{state.mapReady=false;q('[data-tactic-image]').style.visibility='hidden';status('地图图片加载失败，请先重新读取。',true);lock();};
    q('[data-tactic-refresh]').onclick=()=>loading();q('[data-tactic-filter]').onchange=listLibrary;
    q('[data-tactic-map-select]').onchange=e=>loading(e.target.value);
    q('[data-tactic-radar]').onchange=e=>{if(state.busy)return;state.layer=e.target.value;showRadar();};
    q('[data-tactic-new]').onclick=()=>{if(discard()){setDraft(fresh(q('[data-tactic-side]').value,state.list));listLibrary();status('');}};
    q('[data-tactic-id]').oninput=e=>{state.draft.id=e.target.value;updateDirty();};q('[data-tactic-name]').oninput=e=>{state.draft.name=e.target.value;updateDirty();};q('[data-tactic-side]').onchange=e=>{state.draft.side=e.target.value;updateDirty();};
    q('[data-tactic-assignment]').onchange=e=>{state.draft.assignment=e.target.value;if(state.draft.assignment==='roster')state.draft.human_slot=1;assignmentDetails();lock();updateDirty();};
    q('[data-tactic-human-slot]').onchange=e=>{if(state.draft.assignment!=='ability')return;state.draft.human_slot=Number(e.target.value);assignmentDetails();updateDirty();};
    qa('[data-tactic-duty]').forEach(select=>select.onchange=e=>{state.draft.slots[Number(e.target.dataset.tacticDuty)-1].duty=e.target.value;updateDirty();});
    qa('[data-tactic-slot]').forEach(b=>b.onclick=()=>select(Number(b.dataset.tacticSlot)));
    q('[data-tactic-wait]').oninput=e=>{const v=Number(e.target.value);if(e.target.value===''||!Number.isFinite(v)||v<0||v>30){e.target.setCustomValidity(tr('等待需为 0—30 秒。'));return;}e.target.setCustomValidity('');if(step()){step().wait=v;updateDirty();listSteps();lock();}};
    q('[data-tactic-level]').onchange=e=>{if(step()){step().level=e.target.value;updateDirty();listSteps();}};
    q('[data-tactic-movement]').onchange=e=>{if(step()){step().movement=e.target.value;updateDirty();listSteps();}};
    q('[data-tactic-look-set]').onclick=()=>{if(!step())return;state.lookMode=!state.lookMode;details();drawMap();status(state.lookMode?'在地图上点击要观察的位置；可先预瞄掩体后的方向。':'');};
    q('[data-tactic-look-clear]').onclick=()=>{if(step()){step().look_at=null;state.lookMode=false;refreshEditor();}};
    const reorder=delta=>{if(!step())return;const dest=state.index+delta;if(dest<0||dest>=row().steps.length)return;[row().steps[state.index],row().steps[dest]]=[row().steps[dest],row().steps[state.index]];state.index=dest;state.lookMode=false;refreshEditor();};
    q('[data-tactic-up]').onclick=()=>reorder(-1);q('[data-tactic-down]').onclick=()=>reorder(1);q('[data-tactic-step-delete]').onclick=()=>{if(step()){row().steps.splice(state.index,1);state.index=Math.min(state.index,row().steps.length-1);state.lookMode=false;refreshEditor();}};
    q('[data-tactic-copy]').onclick=()=>{
      const value=q('[data-tactic-copy-to]').value,targets=value==='all'?state.draft.slots.filter(s=>s.slot!==state.slot):[state.draft.slots[Number(value)-1]].filter(s=>s&&s.slot!==state.slot);
      if(!targets.length||!row().steps.length)return;if(targets.some(s=>s.steps.length)&&!root.confirm(tr('目标槽已有步骤，复制后将替换，继续？')))return;
      const source=clone(row().steps);targets.forEach(s=>s.steps=clone(source));refreshEditor();status('路线已复制，记得保存战术。');
    };
    const svg=q('[data-tactic-svg]');
    const pointer=event=>{const box=svg.getBoundingClientRect();return pixelToWorld([Math.max(0,Math.min(state.meta.width,(event.clientX-box.left)/box.width*state.meta.width)),Math.max(0,Math.min(state.meta.height,(event.clientY-box.top)/box.height*state.meta.height))],state.meta);};
    const finishDrag=()=>{if(!state.drag)return;state.drag=null;if(state.frame!=null){root.cancelAnimationFrame(state.frame);state.frame=null;}refreshEditor();};
    svg.onpointerdown=e=>{
      if(e.button!==0||state.busy||!state.meta||!state.mapReady)return;e.preventDefault();
      const point=pointer(e),node=e.target.closest('[data-tactic-node]');
      if(state.lookMode&&step()){step().look_at=point;state.lookMode=false;refreshEditor();status('');return;}
      if(node)select(Number(node.dataset.slot),Number(node.dataset.step));
      else{if(row().steps.length>=12){status('每个槽最多 12 步。',true);return;}row().steps.push({position:point,level:'auto',wait:0,movement:'run',look_at:null});state.index=row().steps.length-1;refreshEditor();}
      state.drag={pointer:e.pointerId,slot:state.slot,index:state.index};svg.setPointerCapture(e.pointerId);
    };
    svg.onpointermove=e=>{if(!state.drag||e.pointerId!==state.drag.pointer||state.busy)return;const s=state.draft.slots[state.drag.slot-1].steps[state.drag.index];s.position=pointer(e);q('[data-tactic-position]').textContent=s.position.map(v=>v.toFixed(1)).join(', ');updateDirty();scheduleMap();};
    svg.onpointerup=e=>{if(state.drag?.pointer!==e.pointerId)return;if(svg.hasPointerCapture(e.pointerId))svg.releasePointerCapture(e.pointerId);finishDrag();};svg.onpointercancel=finishDrag;svg.onlostpointercapture=finishDrag;
    q('[data-tactic-form]').onsubmit=async e=>{
      e.preventDefault();if(state.busy||!state.meta)return;
      try{const value=normalize(state.draft);if(state.list.some(t=>t.id===value.id)&&value.id!==state.originalId&&!root.confirm(tr('此 ID 已存在，覆盖已保存战术？')))return;
        state.busy=true;lock();status('正在保存战术…');await send('/api/tactics/save',{map:state.map,tactic:value});
        state.draft=value;state.originalId=value.id;state.base=JSON.stringify(value);updateDirty();
        try{await read();const saved=state.list.find(t=>t.id===value.id);if(saved)setDraft(saved,saved.id);listLibrary();status('战术已保存。');}catch(_){status('已保存，但列表刷新失败，当前草稿保留。',true);}
      }catch(e){status(e.message||'保存失败，请重试。',true);}finally{state.busy=false;lock();}
    };
    q('[data-tactic-delete]').onclick=async()=>{if(state.busy||!state.originalId||!root.confirm(tr('删除这条已保存战术？不会改动生涯或比赛记录。')))return;state.busy=true;lock();status('正在删除…');try{const id=state.originalId;await send('/api/tactics/delete',{map:state.map,id});state.list=state.list.filter(t=>t.id!==id);setDraft(fresh(state.draft.side,state.list));listLibrary();status('战术已删除。');try{await read();}catch(_){status('已删除，但列表刷新失败；可点重新读取。',true);}}catch(e){status(e.message||'删除失败，请重试。',true);}finally{state.busy=false;lock();}};
    q('[data-tactic-import]').onclick=()=>q('[data-tactic-file]').click();q('[data-tactic-file]').onchange=async e=>{
      const file=e.target.files?.[0];e.target.value='';if(!file||state.busy||!discard())return;
      state.busy=true;lock();status('正在导入…');
      try{if(file.size>1024*1024)error('导入文件过大，请拆分后导入。');const data=parseImport(JSON.parse(await file.text()),state.map),rows=data.tactic?[data.tactic]:data.tactics;if(rows.some(t=>state.list.some(saved=>saved.id===t.id))&&!root.confirm(tr('导入包含同名 ID，会覆盖已有战术，继续？'))){status('');return;}const result=await send('/api/tactics/import?map='+encodeURIComponent(state.map),data);state.list=Array.isArray(result.tactics)?result.tactics.map(normalize):[...state.list.filter(t=>!rows.some(incoming=>incoming.id===t.id)),...rows];const id=rows[0]?.id,saved=state.list.find(t=>t.id===id);if(saved)setDraft(saved,saved.id);listLibrary();try{await read();const canonical=state.list.find(t=>t.id===id);if(canonical)setDraft(canonical,canonical.id);listLibrary();status('导入已完成。');}catch(_){status('已导入，但列表刷新失败；当前战术已保留。',true);}}
      catch(e){status(e.message||'导入失败，请检查 JSON。',true);}finally{state.busy=false;lock();}
    };
    const download=(value,name)=>{const url=root.URL.createObjectURL(new Blob([JSON.stringify(value,null,2)+'\n'],{type:'application/json'})),a=root.document.createElement('a');a.href=url;a.download=name;root.document.body.append(a);a.click();a.remove();root.setTimeout(()=>root.URL.revokeObjectURL(url),1000);};
    q('[data-tactic-export]').onclick=()=>{try{const value=normalize(state.draft);download({map:state.map,tactic:value},state.map.replace(/^de_/,'')+'-'+value.id+'.json');status('已导出当前草稿。');}catch(e){status(e.message,true);}};
    q('[data-tactic-export-all]').onclick=()=>{download({schema_version:1,map:state.map,tactics:clone(state.list)},state.map.replace(/^de_/,'')+'-tactics.json');status('已导出全部已保存战术。');};
    q('[data-tactic-command-copy]').onclick=async()=>{try{await root.navigator.clipboard.writeText(q('[data-tactic-command]').textContent);status('指令已复制。');}catch(_){status('请手动复制下方指令。');}};
    setDraft(state.draft);listLibrary();
    const controller={state,read,load:loading,select,setDraft,destroy(){if(state.frame!=null)root.cancelAnimationFrame(state.frame);}};entries.set(host,controller);return controller;
  }
  const api={normalize,parseImport,checkMeta,worldToPixel,pixelToWorld,fresh,mount,colors:COLORS,maps:MAPS};
  root.CareerTactics=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
  if(root.CareerUI)root.CareerUI.pages.tactics=async(_route,host,active)=>{let controller=entries.get(host);if(controller)return;controller=mount(host);await controller.load();if(!active())return;};
})(typeof window!=='undefined'?window:globalThis);
