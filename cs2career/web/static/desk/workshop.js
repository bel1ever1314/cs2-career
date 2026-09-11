/* JSON-only content packs: observe errors without executing pack scripts. */
(() => {
CareerUI.pages.workshop=async(_route,host,active)=>{
  const info=await get('/api/extensions');if(!active())return;
  const kinds={stories:'剧情',events:'赛事日历',skins:'饰品',teams:'战队',eras:'年代',match_chat:'比赛聊天',incidents:'生涯事件（选择与后果）'};
  host.innerHTML=CareerUI.head('扩展工坊','数据驱动的剧情、赛事、饰品与世界内容')+`<div class="card"><h3>安装与制作</h3>
    <p>将扩展文件夹放入下方目录，每包包含 pack.json 和相应类型子目录。扩展只读取 JSON，不执行脚本。</p>
    <p><code>${esc(info.root)}</code></p><p class="hint">项目 extensions/_templates 提供制作示例。stories 是叙事文字；events 是赛事日历；incidents 才是教练变动等选择事件；match_chat 是 CS2 比赛文字。</p>
    <p class="hint">重新扫描后，生涯事件从下一次触发生效，已弹出的选择保持原内容；比赛聊天从下一次准备 CS2 比赛生效。赛事与年代用于新生涯。</p>
    <button class="btn" id="packs-reload" ${S.design_preview?'disabled':''}>重新扫描扩展</button></div>
    <details class="card"><summary>可以扩展哪些生涯事件？</summary>
      <p>已有业务：假赛邀请（接受／拒绝）、调查与处罚、Major 前教练缺席、生日和债务事件。incidents.overrides 可修改弹窗文字及选项标签，不改变原概率与后果。</p>
      <p>新增事件触发点：日期推进、自己的正式比赛开始前、系列赛结束后、参赛赛事开赛、教练缺席后。</p>
      <p>允许效果：个人资金、俱乐部资金、全队心态、自定义布尔标记、技能点奖励、暂停正式参赛；用标记连接后续事件。至少保留一个免费且不要求暂停的选项。</p>
      <p>skill_points 的 amount 为奖励点数（0—100）；competition_pause 的 amount 为天数（1—365），写0可提前恢复。暂停会让期间已排比赛弃权，到期自动恢复。示例见 choice-effects-pack/怎么验证.txt。</p>
      <p>转会触发点：收到邀约、申请成功或失败、决定留队、离队、入队、对阵旧队。可以用 farewell_choice 区分三种告别，继续写外界或队友的回应。</p>
      <p class="hint">示例包自带中文 README.txt。教练离队目前用标记与心态表达，不是教练合同数据库；扩展不能执行脚本。严重负面情节请用虚构人物并标注虚构。</p></details>
    <details class="card"><summary>比赛内剧情与普通聊天有什么区别？</summary>
      <p>match_chat 文件中 rules 是普通聊天：教练和选手每回合各一句；text 数组随机选一句。scenes 是场内剧情：sequence 数组按顺序逐句播放，教练、队友、对手可以交替说话。</p>
      <p>剧情优先于所有普通聊天。一个回合只选一个剧情；同级按扩展加载顺序、文件名、数组顺序选择。每个剧情最多六句，支持逐句设置间隔。</p>
      <p class="hint">示例见 match-scene-pack。剧情只显示文字，不改变赛果、暂停或操控 CS2；换图、重启或下一回合冻结结束会取消未说完的内容。</p></details>
    <div class="page-head"><h3>已发现 ${info.packs.length} 个扩展 · ${info.ready} 个已启用</h3></div>
    ${info.packs.length?info.packs.map(p=>`<article class="card"><h3>${esc(p.name)} <small class="hint">${esc(p.version)}</small></h3>
    <p>${esc({ready:'已启用',disabled:'已停用',rejected:'校验失败，未加载'}[p.status]||p.status)} · ${p.kinds.map(k=>esc(kinds[k]||k)).join(' / ')}</p>
    <small class="hint">${esc(p.id)}</small>${p.errors.length?`<div class="notice">${p.errors.map(esc).join('<br>')}</div>`:''}</article>`).join(''):CareerUI.empty('暂无扩展，内置内容可以直接游玩。')}`;
  $('packs-reload').onclick=async e=>{e.target.disabled=true;try{await post('/api/extensions/reload',{});}finally{CareerUI.go('workshop',{},true);}};
};
})();
