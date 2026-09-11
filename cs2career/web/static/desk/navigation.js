/* UI routing is independent of game commands. Detail routes retain their
   filters and scroll state; no route change is allowed to advance a season. */
window.CareerUI = (() => {
  const pages = {}, stack = [];
  let cursor = -1, route = null, generation = 0;
  const labels = {home:'生涯概览',squad:'我的阵容',honours:'荣誉墙',locker:'俱乐部经营',mail:'收件箱',market:'转会市场',
    play:'训练赛',settings:'游戏设置',workshop:'扩展工坊',schedule:'赛季日历',event:'赛事中心',match:'比赛战报',ranking:'战队排名',players:'年度 Top20',data:'选手数据',
    profile:'资料中心',inventory:'饰品库存',skins:'饰品市场',cases:'武器箱',setup:'创建生涯','story-history':'故事档案'};
  function remember() {
    if (cursor < 0) return;
    stack[cursor].scroll = window.scrollY;
    stack[cursor].inputs = Object.fromEntries([...document.querySelectorAll('.view.on input[id],.view.on select[id]')].map(x=>[x.id,x.value]));
  }
  function go(view, params={}, replace=false) {
    remember();
    if(view==='train') view='play';
    if(view==='event' && !params.key) params.key=FOCUS;
    route={view,...params};
    if(replace && cursor>=0) stack[cursor]={route:{...route},scroll:0};
    else { stack.splice(cursor+1); stack.push({route:{...route},scroll:0}); cursor=stack.length-1; }
    activate();
  }
  function activate() {
    route={...stack[cursor].route}; VIEW=route.view;
    if(VIEW==='event') FOCUS=route.key;
    if(VIEW==='match') MATCH=route.key;
    if(VIEW!=='play' && PLAY_TIMER) {clearInterval(PLAY_TIMER);PLAY_TIMER=null;}
    if(VIEW!=='match') stopSeriesPoll();
    render();
  }
  function travel(delta) {
    if(cursor+delta<0 || cursor+delta>=stack.length) return;
    remember();cursor+=delta;activate();
  }
  function bar() {
    $('route-back').disabled=cursor<=0;
    $('route-forward').disabled=cursor>=stack.length-1;
    document.body.classList.toggle('is-playtest',!!S.playtest);
    $('breadcrumbs').innerHTML=`<button class="text-link" data-route="home">生涯中心</button><span>/</span><span>${esc(labels[VIEW]||VIEW)}</span>${route?.key?'<span>/</span><span class="crumb-key">'+esc(route.kind==='team'||route.kind==='player'?route.key.replace(/^p_([^_]+)_.+$/,'$1'):'详情')+'</span>':''}${S.design_preview?'<b class="preview-tag">隔离设计预览 · 不使用正式存档</b>':''}`;
  }
  function restore() {
    const entry=stack[cursor];
    for(const [id,value] of Object.entries(entry?.inputs||{})) {
      const e=$(id);if(!e)continue;
      // After a signing, the previous replacement is no longer an option.
      // Do not erase the new default by restoring an invalid select value.
      if(e.tagName==='SELECT'&&![...e.options].some(o=>o.value===value))continue;
      e.value=value;
    }
    requestAnimationFrame(()=>window.scrollTo(0,entry?.scroll||0));
  }
  function draw() {
    if(!route || route.view!==VIEW) {route={view:VIEW};stack.push({route:{...route},scroll:0});cursor=stack.length-1;}
    bar();
    if (S.design_preview && VIEW==='home') {
      queueMicrotask(()=>{const home=$('view-home');if(!home.querySelector('.preview-tour'))home.insertAdjacentHTML('afterbegin',`<div class="preview-tour"><b>第一阶段 · 交互确认</b><span>以下是模拟生成的展示赛事，不代表真实比赛结果或可玩性结论。</span><div class="filterbar"><button class="btn" data-open-team="Vitality">队伍 → 选手资料</button><button class="btn" data-open-event="design-single_elim">单败晋级图</button><button class="btn" data-open-event="design-gsl_playoff">GSL 小组路径</button><button class="btn" data-open-event="design-swiss_playoff">瑞士轮进程</button><button class="btn" data-route="cases">开箱体验</button></div></div>`);});
    }
    const stamp=++generation,painter=pages[VIEW];
    if(!painter) {queueMicrotask(()=>{if(stamp===generation)restore();});return false;}
    const host=$('view-'+VIEW);
    const routeKey=JSON.stringify(route),sameRoute=host.dataset.loadedRoute===routeKey;
    if(sameRoute)remember();
    else host.inert=true; // Old detail stays visible, but cannot act on the new route.
    // Refresh in place: do not collapse an existing page into a loading line
    // while HTTP reads are pending (polling used to flash the whole panel).
    if(!host.innerHTML.trim())host.innerHTML='<p class="empty">正在读取本地资料…</p>';
    Promise.resolve(painter({...route},host,()=>stamp===generation&&route.view===VIEW)).then(()=>{
      if(stamp!==generation)return;
      host.dataset.loadedRoute=routeKey;host.inert=false;restore();
    }).catch(err=>{if(stamp===generation){host.inert=false;if(sameRoute)toast('资料刷新失败，暂时保留原内容：'+err.message,true);else host.innerHTML=`<p class="empty">资料暂不可用：${esc(err.message)}</p>`;}});
    return true;
  }
  document.addEventListener('click',e=>{
    if(window.CareerAssist?.isOpen())return;
    const b=e.target.closest('[data-route],[data-open-player],[data-open-team],[data-open-match],[data-open-event],[data-route-tab]');
    if(!b)return;
    if(b.dataset.openPlayer!==undefined) inspect('player',b.dataset.openPlayer);
    else if(b.dataset.openTeam!==undefined) inspect('team',b.dataset.openTeam);
    else if(b.dataset.openMatch) match(b.dataset.openMatch);
    else if(b.dataset.openEvent) go('event',{key:b.dataset.openEvent});
    else if(b.dataset.routeTab) go(route.view,{...route,tab:b.dataset.routeTab},true);
    else if(b.dataset.route) go(b.dataset.route);
  });
  document.addEventListener('DOMContentLoaded',()=>{
    $('route-back').onclick=()=>travel(-1);$('route-forward').onclick=()=>travel(1);
    document.addEventListener('keydown',e=>{if(e.altKey&&['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();if(!window.CareerAssist?.isOpen())travel(e.key==='ArrowLeft'?-1:1);}});
  });
  function inspect(kind,key){go('profile',{kind,key,tab:'overview',range:'season',page:1});}
  function match(key){go('match',{key,tab:'all'});}
  return {pages,go,remember,render:draw,inspect,match,route:()=>route,
    paint:(host,html)=>window.CareerDOM?window.CareerDOM.paint(host,html):(host.innerHTML=html),
    link:(kind,key,text)=>`<button class="text-link" data-open-${kind}="${esc(key)}">${esc(text)}</button>`,
    tabs:(tabs,selected)=>`<div class="detail-tabs">${tabs.map(([id,title])=>`<button class="${id===selected?'selected':''}" data-route-tab="${esc(id)}">${esc(title)}</button>`).join('')}</div>`,
    empty:text=>`<p class="empty">${esc(text)}</p>`,
    num:(v,d=0)=>v==null?'—':Number(v).toFixed(d),
    head:(title,hint)=>`<div class="page-head"><h2>${esc(title)}</h2><span class="hint">${esc(hint||'')}</span></div>`};
})();
