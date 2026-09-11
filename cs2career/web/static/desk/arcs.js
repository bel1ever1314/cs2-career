/* Story views are read-only. Decisions remain in the existing incident modal;
   pagination never advances the clock and text is always HTML-escaped. */
(() => {
  const ui=CareerUI;
  ui.arcSummary=c=>{
    const v=c.story_arcs;
    if(!v?.enabled)return '';
    const na={choose:'待选择',study:'学业与比赛',pro:'全职冲击职业',lvg_pending:'LVG邀约待定',
      invite_wait:'已获邀约资格，等待LVG结束赛事',return_pending:'等待回国组队',returned:'归国第二次挑战',achieved:'挑战达成',closed:'留学生篇结束'};
    let text=v.na?`NA 留学生 · ${na[v.na]||v.na}`:'生活与职业剧情已开启';
    if(['study','pro','returned'].includes(v.na)){
      const p=v.na_progress||{};
      const types={cct:'CCT',t2:'T2',qual:'预选赛',t1:'T1',major:'Major'};
      text+=` · 考核截至 ${v.deadline} · 个人地图 ${p.maps||0}/${p.min_maps??20}，地图均评 ${p.rating==null?'暂无':Number(p.rating).toFixed(2)}/${Number(p.min_rating??1).toFixed(2)}`;
      text+=` · 认可冠军：${(p.success_types||[]).map(x=>types[x]||x).join('／')}（${p.achievement?'已达成':'未达成'}）`;
    }
    if(v.heat)text+=' · 热恋状态波动中（至下一届Major结束）';
    if(v.injury_active?.until)text+=` · 伤病负状态至 ${v.injury_active.until}`;
    return `<div class="notice compact-notice"><span>${esc(text)}</span><button class="btn sm" data-route="story-history">故事档案</button></div>`;
  };
  ui.pages['story-history']=async(route,host,active)=>{
    const data=await get(`/api/story-history?page=${Math.max(1,Number(route.page)||1)}`);
    if(!active())return;
    host.innerHTML=ui.head('故事档案',`已保存 ${data.total} 段 · 不会重放或重复结算奖励`)+
      `<div class="filterbar"><button class="btn" data-arc-page="${data.page-1}" ${data.page<=1?'disabled':''}>上一页</button><span>${data.page} / ${data.pages}</span><button class="btn" data-arc-page="${data.page+1}" ${data.page>=data.pages?'disabled':''}>下一页</button></div>`+
      (data.rows.length?data.rows.map(r=>`<details class="card" style="margin-bottom:10px"><summary>${esc(r.date)} · ${esc(r.title)}</summary><p style="white-space:pre-wrap">${esc(r.text)}</p>${r.choice?`<p class="hint">当时的选择：${esc(r.choice)}</p>`:''}</details>`).join(''):ui.empty('还没有新的剧情记录。此前未保存文本的旧剧情不补造。'));
    host.querySelectorAll('[data-arc-page]').forEach(b=>b.onclick=()=>ui.go('story-history',{page:Number(b.dataset.arcPage)},true));
  };
})();
