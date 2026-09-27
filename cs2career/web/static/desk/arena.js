/* Server-authoritative local matchmaking. Keyed paints keep selectors stable. */
(() => {
  const words = {
    '对战大厅':'Match lobby','独立本地天梯':'Independent local ladder','自定义':'Custom',
    '挑选十人':'Select ten players','搜索选手或俱乐部':'Search players or clubs','推荐十人':'Suggest ten players',
    '清空名单':'Clear selection','建立房间':'Create lobby','移除':'Remove','加入 A':'Add to A','加入 B':'Add to B','加入名单':'Add player',
    '前五人是 A 队，后五人是 B 队；移除后可重新分配。':'The first five slots are Team A, the last five Team B. Remove a player to reassign.',
    '队长选人':'Captain draft','本轮选人':'Current pick','点选一名待选选手，代当前队长完成选择。':'Choose an available player for the current captain.',
    '地图与身份':'Map & participation','地图':'Map','开局 CT':'Starting CT','控制角色':'Play as',
    '观察者 · 十名 Bot':'Spectator · ten Bots','进入 CS2':'Launch CS2','保存设置':'Save settings',
    '请先完全退出 CS2；进入对应地图的竞技人机模式。观察者场由插件自动安排旁观。':'Fully exit CS2 first, then open Competitive vs Bots on the selected map. The plugin assigns you to spectators in observer matches.',
    '比赛待回传':'Waiting for the result','录入本场战绩':'Import match result','重试启动':'Retry launch',
    '完成比赛后回到这里录入；未收到正式终场与完整十人数据不会计分。':'Return here after the match to import. No rating changes until the official end and complete ten-player stats arrive.',
    '关闭房间':'Close lobby','放弃待回传比赛需要先退出 CS2；已保存战绩不删除。确定关闭？':'Exit CS2 before abandoning a pending match. Saved results will be retained. Close this lobby?',
    '本地积分榜':'Local standings','最近对局':'Recent matches','查看战报':'View report','返回房间':'Back to lobby',
    '尚无已保存的对局':'No saved matches yet','能力':'Ability','胜':'W','负':'L','选手':'Player','队长':'Captain',
    '你控制的选手':'Your player','房间已更新':'Lobby updated','无人符合筛选条件':'No matching players',
    '最近 Rating':'Recent Rating','样本':'Maps','积分变化':'Elo change','下一场':'Next match',
    '暂无已计分选手':'No rated players yet','请先在游戏设置中配置 CS2 和人机增强。':'Configure CS2 and Bot Improver in Game Settings first.',
    '房间已经变化，请刷新后再操作':'The lobby has changed. Refresh before continuing.',
    '请选择十名不同的选手':'Select ten distinct players.',
    '本场战绩与本地天梯积分已保存':'Match stats and local ladder ratings saved.',
    '本场战绩已保存':'Match stats saved.','这场已录入，不重复计分':'This match has already been scored.',
    '还没有读到比分':'No result received yet.',
    '按模式自动生成 9／10 人':'Generate 9 or 10 Bots per mode',
    '请在 CS2 进入选定地图的竞技人机模式。':'In CS2, open Competitive vs Bots on the selected map.',
    '十人战绩不完整，已阻止录入':'Incomplete ten-player stats; result rejected.',
    '未知房间模式':'Unknown lobby mode.',
    '上一场仍待回传，请先录入或退出 CS2 后放弃该场':'A match is pending. Import it, or exit CS2 and close that lobby first.',
    '名单中的选手已不在当前资料库，请重新选择':'A selected player is no longer in the current database. Select again.',
    '控制角色必须在十人名单里':'Your controlled player must belong to the selected ten.',
    '当前不在队长选人阶段':'The lobby is not in its draft phase.',
    '该选手不在待选名单':'That player is not available to pick.',
    '先完成双方阵容':'Complete both rosters first.',
    '地图、阵营或控制角色无效':'Invalid map, starting side or controlled player.',
    '当前资料库不足十名选手':'There are fewer than ten players in this database.',
    '房间不在待开赛状态':'The lobby is not ready to launch.',
    '请先完成或处理生涯中待回传的 CS2 比赛':'Resolve the pending career CS2 match first.',
    '当前没有待录入的天梯比赛':'There is no pending local match to import.',
    '回传地图或结束时间缺失，未计分':'The result map or end time is missing. No points awarded.',
    '回传选手与开场阵容不一致，未计分':'Result identities do not match the opening rosters. No points awarded.',
    '对战大厅仍有比赛待回传，请先录入或放弃该场。':'A lobby match is still pending. Import it or abandon it first.',
    '比赛还没正常结束，等待 CareerMatch 确认终场；加时中不会提前录入。':'Waiting for CareerMatch to confirm the final result; overtime is not imported early.',
  };

  Object.assign(words,{
    '本地天梯':'Local ladder','一个天梯，一场属于你的比赛。':'One ladder. Your next match.',
    '按分段匹配九名选手，队长选人后进入地图 BP。':'Match nine players at your Elo, draft teams, then veto maps.',
    '本地单机匹配，不连接线上服务；不影响生涯 VRS、资金或属性。':'Offline local matches. No online service, career VRS, cash or attribute changes.',
    '开始匹配':'Find match','更换选手':'Change player','收起选手库':'Close player pool',
    '天梯分':'Ladder Elo','胜率':'Win rate','对局':'Matches','先选择一名选手':'Choose your player','使用此选手':'Play as',
    '匹配完成':'Match found','地图 BP':'Map veto','选边':'Starting side','准备开赛':'Ready to play',
    '本局分段':'Lobby Elo','匹配范围已扩大':'Search range expanded','两位最高分选手担任队长':'The two highest-Elo players are captains',
    '轮到你选人':'Your pick','队长正在选人':'Captain is picking','选择队员':'Pick player',
    '你不是本局队长，选人和禁图会自动进行。':'You are not a captain. Draft and veto will run automatically.',
    '选人顺序':'Pick order','平均分':'Average Elo','等待选人':'Awaiting pick','你':'YOU',
    '轮到你禁图':'Your map ban','队长正在禁图':'Captain is banning a map','禁用地图':'Ban map','已禁用':'BANNED',
    '决胜地图':'DECIDER','双方交替禁掉六张图，剩余地图开赛；A 队选择开局阵营。':'Alternate six bans. Play the remaining map; Team A chooses the starting side.',
    '选择你的开局阵营':'Choose your starting side','队长正在选边':'Captain is choosing a side',
    '先打 CT':'Start CT','先打 T':'Start T','本局阵容和地图已确定':'Teams and map are locked',
    '请先退出 CS2，再从这里启动本场比赛。':'Exit CS2 first, then launch this match here.',
    '全队选人记录':'Draft log','刷新房间':'Refresh lobby','自动流程已暂停，请刷新重试。':'Automatic steps paused. Refresh to retry.',
    '关闭当前房间？已保存战绩不会删除。':'Close this lobby? Saved match history is retained.',
    '前五人是 A 队，后五人是 B 队。可以亲自参赛，也可以旁观十名 Bot。':'First five: Team A; next five: Team B. Play or spectate ten Bots.',
    '请先完成或关闭当前房间':'Finish or close the current lobby first.',
    '请先选择你控制的选手':'Select your controlled player first.',
    '当前由 AI 队长操作':'It is an AI captain’s turn.','现在轮到你操作':'It is your turn.',
    '天梯阵容和地图已锁定':'Ranked rosters and map are locked.',
    '地图已被禁用或不在图池':'That map is already banned or not in the pool.',
    '当前不在地图 BP 阶段':'The lobby is not in map veto.','当前不在选边阶段':'The lobby is not in side selection.',
    '请选择 CT 或 T':'Select CT or T.',
    '天梯请使用开始匹配，不手动挑选对手':'Use Find match for ranked games; opponents are not chosen manually.',
    '绑定当前生涯角色':'Bound to your career player',
    '天梯固定使用当前生涯角色，不能更换选手':'Ranked matches use your current career player. You cannot switch players.',
    '请先创建生涯角色，再开始天梯匹配':'Create a career player before entering the local ladder.',
    '当前生涯角色资料缺失，无法开始天梯匹配':'Your career player data is missing. Ranked matchmaking is unavailable.',
    '当前房间角色与生涯不一致，请录入已有战绩或关闭房间后重新匹配':'This lobby belongs to a different career player. Import its existing result or close it and queue again.',
    '本场位置':'Match role',
    '选人完成后，按五位置能力自动分工；不改变生涯位置。':'After the draft, positions are assigned by role ability without changing career positions.',
    '双方已按位置适性分配五个不同位置。':'Both teams have five distinct positions assigned by role ability.',
    '分配位置需要五名不同的选手':'Role assignment requires five distinct players.'
  });
  CareerI18n.register('en',{phrases:words});
  const tr=s=>CareerI18n.t(s), txt=s=>esc(tr(s));
  let data=null, mode='rank', chosen=[], human='', query='', page=0;
  let busy=false, host=null, report=null, timer=null, autoError=false, active=()=>false, customConfig=null;
  const card=pid=>data.catalog.find(p=>p.player_id===pid);
  const careerHuman=()=>data?.rank_human_id||'';
  const name=pid=>data?.lobby?.roster?.[pid]?.name||card(pid)?.name||pid;
  const elo=pid=>data.lobby?.ratings?.[pid]??card(pid)?.elo??1000;
  const person=pid=>'<b translate="no">'+esc(name(pid))+'</b>';
  const num=(v,n=0)=>v==null?'—':Number(v).toFixed(n);
  const button=(act,label,extra='',disabled=false,style='')=>'<button class="btn '+style+'" data-arena="'+act+'" '+extra+' '+(disabled||busy?'disabled':'')+'>'+txt(label)+'</button>';
  const role=p=>txt(({awp:'主狙',entry:'突破',lurk:'自由人',igl:'指挥',rifle:'步枪手'})[p.role]||p.role);
  const paint=(node,html)=>CareerUI.paint?CareerUI.paint(node,html):(node.innerHTML=html);
  function boxScore(r) {
    const mp=r.map;
    return `<article class="card arena-result"><h2 translate="no">Team A ${esc(mp.score)} Team B · ${esc(mp.map)}</h2><p>${esc(r.mode.toUpperCase())} · ${esc(r.date||'')}</p><div class="arena-score-scroll"><table><thead><tr><th>${txt('选手')}</th><th>K / D / A</th><th>Damage</th><th>ADR</th><th>KAST</th><th>FK / FD</th><th>Rating</th><th>${txt('积分变化')}</th></tr></thead><tbody>${Object.entries(mp.players).map(([team,rows])=>`<tr class="arena-team"><th colspan="8" translate="no">${esc(team)}</th></tr>${rows.map(p=>`<tr class="${p.player_id===r.human_id?'arena-you':''}"><td translate="no">${esc(p.name)} ${p.player_id===r.human_id?'★':''}</td><td>${p.k} / ${p.d} / ${p.a}</td><td>${p.damage}</td><td>${num(p.adr,1)}</td><td>${num(p.kast*100,1)}%</td><td>${p.opening_kills} / ${p.opening_deaths}</td><td><b>${num(p.rating,2)}</b></td><td>${r.mode==='custom'?'—':((r.changes[p.player_id]>=0?'+':'')+r.changes[p.player_id])}</td></tr>`).join('')}`).join('')}</tbody></table></div>${r.human_id?`<p class="arena-you-label">★ ${txt('你控制的选手')}</p>`:''}</article>`;
  }

  function teams(l) {
    return '<div class="arena-teams">'+['a','b'].map(s=>'<article class="arena-squad side-'+s+'" data-ui-key="team-'+s+'"><header><div><small>TEAM '+s.toUpperCase()+'</small><h3 translate="no">'+(l.mode==='custom'?'Team '+s.toUpperCase():esc(name(l.captains[s==='a'?0:1])))+'</h3></div><span>'+txt('平均分')+'<b>'+Math.round(l[s].reduce((sum,p)=>sum+elo(p),0)/Math.max(1,l[s].length))+'</b></span></header>'+
      Array.from({length:5},(_,i)=>{const pid=l[s][i];return pid?'<div class="arena-slot '+(pid===l.human_id?'is-you':'')+'" data-ui-key="slot-'+esc(pid)+'"><span class="arena-slot-no">'+(i+1)+'</span><div>'+person(pid)+'<small translate="no">'+esc(l.roster[pid].club||'—')+'</small>'+(l.role_assignment_version?'<small class="arena-assigned-role" data-match-role="'+esc(l.roster[pid].role)+'">'+txt('本场位置')+' · '+role(l.roster[pid])+'</small>':'')+'</div><span class="arena-slot-tags">'+(l.mode!=='custom'&&l.captains.includes(pid)?'<em>'+txt('队长')+'</em>':'')+(pid===l.human_id?'<em>★ '+txt('你')+'</em>':'')+'<b>'+elo(pid)+'</b></span></div>':'<div class="arena-slot vacant" data-ui-key="empty-'+s+'-'+i+'"><span class="arena-slot-no">'+(i+1)+'</span><span>'+txt('等待选人')+'</span></div>';}).join('')+'</article>').join('')+'</div>';
  }
  function pool() {
    const node=host.querySelector('[data-arena-pool]');if(!node||mode!=='custom')return;
    const rows=data.catalog.filter(p=>(p.name+' '+p.club).toLowerCase().includes(query.toLowerCase()));
    page=Math.min(page,Math.max(0,Math.ceil(rows.length/18)-1));
    paint(node,'<div class="arena-grid">'+rows.slice(page*18,page*18+18).map(p=>'<article class="arena-player-card '+(p.player_id===human?'selected':'')+'" data-ui-key="player-'+esc(p.player_id)+'"><div><span class="arena-avatar" translate="no">'+esc(p.name.slice(0,2).toUpperCase())+'</span><span><b translate="no">'+esc(p.name)+'</b><small translate="no">'+esc(p.club||'—')+'</small></span><strong>'+p.elo+'</strong></div><p>'+role(p)+' · '+txt('最近 Rating')+' '+num(p.rating,2)+'</p>'+
      '<div class="arena-actions">'+button('add','加入 A','data-id="'+esc(p.player_id)+'" data-side="a"',chosen.includes(p.player_id)||chosen.slice(0,5).filter(Boolean).length>=5)+button('add','加入 B','data-id="'+esc(p.player_id)+'" data-side="b"',chosen.includes(p.player_id)||chosen.slice(5).filter(Boolean).length>=5)+'</div></article>').join('')+'</div><div class="arena-pager">'+button('prev','←','',page===0)+'<span>'+(page+1)+' / '+Math.max(1,Math.ceil(rows.length/18))+'</span>'+button('next','→','',(page+1)*18>=rows.length)+'</div>');
  }
  const playerPool=()=>'<section class="card arena-library" data-ui-key="library"><input data-arena-search aria-label="'+txt('搜索选手或俱乐部')+'" placeholder="'+txt('搜索选手或俱乐部')+'" value="'+esc(query)+'"><div data-arena-pool></div></section>';
  function home() {
    const p=card(careerHuman()),n=p?p.wins+p.losses:0;
    return '<div class="arena-queue" data-ui-key="queue"><article class="arena-identity"><span class="arena-eyebrow">'+txt('你控制的选手')+'</span><div class="arena-identity-name"><span class="arena-level">'+(p?.level||'—')+'<small>LVL</small></span><div><h2 translate="no">'+esc(p?.name||'—')+'</h2><p translate="no">'+esc(p?.club||'—')+'</p></div></div><div class="arena-elo"><strong>'+(p?.elo??'—')+'</strong><span>'+txt('天梯分')+'</span></div><div class="arena-metrics"><div><b>'+n+'</b><small>'+txt('对局')+'</small></div><div><b>'+(n?Math.round(p.wins/n*100)+'%':'—')+'</b><small>'+txt('胜率')+'</small></div><div><b>'+num(p?.rating,2)+'</b><small>'+txt('最近 Rating')+'</small></div></div><p class="arena-bound-player" data-bound-player="'+esc(careerHuman())+'">'+txt(p?'绑定当前生涯角色':'请先创建生涯角色，再开始天梯匹配')+'</p></article>'+
      '<article class="arena-match-intro"><div class="arena-eyebrow">RANK / FPL <span>5 VS 5</span></div><h2>'+txt('本地天梯')+'</h2><p>'+txt('按分段匹配九名选手，队长选人后进入地图 BP。')+'</p><div class="arena-flow">'+['匹配完成','队长选人','地图 BP'].map((t,i)=>'<span>0'+(i+1)+' <b>'+txt(t)+'</b></span>').join('')+'</div>'+button('matchmake','开始匹配','',!p,'arena-find')+'<small>'+txt('选人完成后，按五位置能力自动分工；不改变生涯位置。')+'</small><small>'+txt('本地单机匹配，不连接线上服务；不影响生涯 VRS、资金或属性。')+'</small></article></div>';
  }
  function customHome() {
    return '<article class="card"><h3>'+txt('挑选十人')+' · '+chosen.filter(Boolean).length+'/10</h3><p class="hint">'+txt('前五人是 A 队，后五人是 B 队。可以亲自参赛，也可以旁观十名 Bot。')+'</p><div class="arena-custom-slots">'+Array.from({length:10},(_,i)=>'<span>'+(i<5?'A':'B')+(i%5+1)+' '+(chosen[i]?person(chosen[i])+button('remove','×','data-id="'+esc(chosen[i])+'" aria-label="'+txt('移除')+'"'):'—')+'</span>').join('')+'</div><div class="arena-toolbar">'+button('recommend','推荐十人')+button('clear','清空名单')+button('create','建立房间','',chosen.filter(Boolean).length!==10,'primary')+'</div></article>'+playerPool();
  }
  function phasePanel(l) {
    const turn=l.turn,humanTurn=turn?.human;
    let h='';
    if(l.identity_error){
      h+='<p class="arena-error" role="status">'+txt(l.identity_error)+'</p>';
      if(['draft','veto','side','ready'].includes(l.phase))return h+teams(l);
    }
    if(l.mode==='rank'){
      const stages=['匹配完成','队长选人','地图 BP','选边','准备开赛'];
      const current=({draft:1,veto:2,side:3,ready:4,starting:4,launched:4,finished:4})[l.phase];
      h+='<div class="arena-steps">'+stages.map((label,i)=>'<span class="'+(i<current?'done':i===current?'current':'')+'"><b>'+(i<current?'✓':i+1)+'</b>'+txt(label)+'</span>').join('')+'</div>';
      h+='<div class="arena-match-meta"><span>'+txt('本局分段')+' <b>'+(l.matched_range||[Math.min(...l.selection.map(elo)),Math.max(...l.selection.map(elo))]).join(' – ')+'</b></span><span>'+txt('两位最高分选手担任队长')+'</span>'+(l.band>200?'<span>'+txt('匹配范围已扩大')+' ±'+l.band+'</span>':'')+'</div>';
    }
    h+=teams(l);
    if(l.role_assignment_version)h+='<p class="hint arena-role-summary">'+txt('双方已按位置适性分配五个不同位置。')+'</p>';
    if(['draft','veto','side'].includes(l.phase)){
      h+='<section class="card arena-stage" data-ui-key="stage-'+l.phase+'"><div class="arena-stage-title"><div><span class="arena-eyebrow">'+(humanTurn?'YOUR TURN':'CAPTAIN TURN')+'</span><h3>'+txt(l.phase==='draft'?(humanTurn?'轮到你选人':'队长正在选人'):l.phase==='veto'?(humanTurn?'轮到你禁图':'队长正在禁图'):(humanTurn?'选择你的开局阵营':'队长正在选边'))+'</h3></div><span translate="no">Team '+turn.side.toUpperCase()+' · '+esc(name(turn.captain_id))+'</span></div>';
      if(!l.captains.includes(l.human_id)&&!l.legacy_manual)h+='<p class="hint">'+txt('你不是本局队长，选人和禁图会自动进行。')+'</p>';
      if(l.phase==='draft')h+='<p class="hint">'+txt('选人顺序')+' A · B · B · A · A · B · B · A</p><div class="arena-grid">'+l.selection.filter(p=>!l.a.concat(l.b).includes(p)).map(pid=>'<article class="arena-player-card" data-ui-key="draft-'+esc(pid)+'"><div><span>'+person(pid)+'<small translate="no">'+esc(l.roster[pid].club)+'</small></span><strong>'+elo(pid)+'</strong></div><p>'+role(l.roster[pid])+'</p>'+button('pick','选择队员','data-id="'+esc(pid)+'"',!humanTurn,'arena-full')+'</article>').join('')+'</div>';
      else if(l.phase==='veto')h+='<p class="hint">'+txt('双方交替禁掉六张图，剩余地图开赛；A 队选择开局阵营。')+'</p><div class="arena-map-grid">'+l.map_pool.map((m,i)=>{const ban=l.bans.find(b=>b.map===m);return '<article class="arena-map map-'+i+' '+(ban?'banned':'')+'" data-ui-key="map-'+m+'"><span class="arena-map-code">'+String(i+1).padStart(2,'0')+'</span><h4 translate="no">'+m.toUpperCase()+'</h4>'+(ban?'<span>'+txt('已禁用')+' · Team '+ban.side.toUpperCase()+'</span>':button('ban','禁用地图','data-map="'+m+'"',!humanTurn))+'</article>';}).join('')+'</div>';
      else h+='<div class="arena-decider"><small>'+txt('决胜地图')+'</small><h2 translate="no">'+esc(l.map.toUpperCase())+'</h2><div class="arena-toolbar">'+button('side','先打 CT','data-side="ct"',!humanTurn)+button('side','先打 T','data-side="t"',!humanTurn)+'</div></div>';
      if(autoError)h+='<p class="arena-error">'+txt('自动流程已暂停，请刷新重试。')+'</p>'+button('refresh','刷新房间');
      h+='</section>';
    } else if(l.phase==='ready'){
      if(l.mode==='custom'){
        const cfg=customConfig||l;
        h+='<section class="card" data-ui-key="custom-config"><h3>'+txt('地图与身份')+'</h3><div class="arena-config"><label>'+txt('地图')+'<select data-arena-map>'+data.maps.map(m=>'<option value="'+m+'" '+(cfg.map===m?'selected':'')+'>'+m+'</option>').join('')+'</select></label><label>'+txt('开局 CT')+'<select data-arena-ct>'+['a','b'].map(s=>'<option value="'+s+'" '+(cfg.ct===s?'selected':'')+'>Team '+s.toUpperCase()+'</option>').join('')+'</select></label><label>'+txt('控制角色')+'<select data-arena-human><option value="">'+txt('观察者 · 十名 Bot')+'</option>'+l.selection.map(pid=>'<option value="'+esc(pid)+'" '+(cfg.human_id===pid?'selected':'')+' translate="no">'+esc(name(pid))+'</option>').join('')+'</select></label></div>'+button('configure','保存设置')+'</section>';
      }
      h+='<section class="card arena-ready"><div><span class="arena-eyebrow">BO1 · '+txt('本局阵容和地图已确定')+'</span><h2 translate="no">'+esc(l.map.toUpperCase())+'</h2><p>CT · Team '+l.ct.toUpperCase()+' / T · Team '+(l.ct==='a'?'B':'A')+'</p><small>'+txt('请先退出 CS2，再从这里启动本场比赛。')+'</small></div>'+button('launch','进入 CS2','',!!S.playtest||!!S.design_preview,'arena-find')+'</section>';
    } else if(l.phase==='finished')h+=boxScore(l.result);
    else h+='<section class="card"><h3>'+txt('比赛待回传')+'</h3><p translate="no">'+esc(l.map)+' · '+esc(l.nonce?.slice(0,12)||'')+'</p><p>'+txt('完成比赛后回到这里录入；未收到正式终场与完整十人数据不会计分。')+'</p>'+button('ingest','录入本场战绩','',!!S.playtest)+(l.phase==='starting'?button('retry','重试启动','',!!S.playtest||!!l.identity_error):'')+'</section>';
    if(l.picks?.length)h+='<details class="card"><summary>'+txt('全队选人记录')+'</summary><div class="arena-pick-log">'+l.picks.map((p,i)=>'<span>'+(i+1)+' · Team '+p.side.toUpperCase()+' → '+person(p.player_id)+'</span>').join('')+'</div></details>';
    return h;
  }
  function draw(){
    if(!host||!data)return;
    const l=data.lobby;
    let h='<header class="arena-heading"><div><span class="arena-eyebrow">CS2 CAREER · PLAY</span><h2>'+txt('对战大厅')+'</h2></div><div class="arena-toolbar">'+['rank','custom'].map(m=>button('mode',m==='rank'?'本地天梯':'自定义','data-mode="'+m+'"',!!l,m===mode?'primary':'')).join('')+'<button class="btn ghost" data-route="settings">'+txt('游戏设置')+'</button></div></header>';
    if(report)h+=button('back','返回房间')+boxScore(report);
    else{
      if(l)h+='<div class="arena-toolbar arena-room-tools"><span translate="no">'+(l.mode==='custom'?'CUSTOM':'RANK / FPL')+' · #'+esc(l.id.slice(0,8))+'</span>'+button('cancel',l.phase==='finished'?'下一场':'关闭房间')+'</div>'+phasePanel(l);
      else h+=mode==='rank'?home():customHome();
      h+='<div class="arena-bottom"><details class="card"><summary>'+txt('本地积分榜')+'</summary><div class="arena-standings">'+data.catalog.slice(0,20).map((p,i)=>'<div><span>'+String(i+1).padStart(2,'0')+'</span><b translate="no">'+esc(p.name)+'</b><strong>'+p.elo+'</strong><small>'+p.wins+txt('胜')+' / '+p.losses+txt('负')+'</small></div>').join('')+'</div></details><details class="card"><summary>'+txt('最近对局')+'</summary>'+data.history.map(r=>'<div class="arena-history"><span translate="no">'+esc(r.map.map)+' · '+esc(r.map.score)+'<small>'+esc(r.date?.slice(0,10)||'')+'</small></span>'+button('report','查看战报','data-id="'+esc(r.id)+'"')+'</div>').join('')+'</details></div>';
    }
    paint(host,h);host.dataset.arenaRevision=String(data.revision);host.dataset.arenaPhase=l?.phase||'idle';pool();schedule();
  }
  async function command(action,body={}){
    const out=await post('/api/arena/'+action,{...body,revision:data.revision},{render:false,quiet:true});
    if(out.ok){data=out.arena;if(out.msg)toast(tr(action==='launch'?'请在 CS2 进入选定地图的竞技人机模式。':out.msg));return true;}
    if(action==='advance')autoError=true;
    data=await get('/api/arena');return false;
  }
  function schedule(){
    if(timer||busy||report||autoError||data.lobby?.identity_error||!data.lobby?.turn||data.lobby.turn.human||!active())return;
    timer=setTimeout(async()=>{
      timer=null;if(!active()||busy||report||data.lobby?.identity_error||!data.lobby?.turn||data.lobby.turn.human)return;
      busy=true;
      try{await command('advance');}catch(e){autoError=true;toast(e.message,true);}
      finally{busy=false;if(active())draw();}
    },850);
  }
  function config(){return {map:host.querySelector('[data-arena-map]').value,ct:host.querySelector('[data-arena-ct]').value,human_id:host.querySelector('[data-arena-human]').value};}
  async function click(e){
    const b=e.target.closest('[data-arena]');if(!b||busy||b.disabled)return;
    const action=b.dataset.arena,id=b.dataset.id;
    const cfg=mode==='custom'&&['configure','launch'].includes(action)?config():null;
    if(timer){clearTimeout(timer);timer=null;}
    busy=true;host.querySelectorAll('[data-arena]').forEach(el=>el.disabled=true);
    try{
      if(action==='mode'){mode=b.dataset.mode;chosen=[];query='';page=0;}
      else if(action==='matchmake'){autoError=false;await command('matchmake');}
      else if(action==='add'){if(!chosen.includes(id)){const start=b.dataset.side==='a'?0:5;for(let i=start;i<start+5;i++)if(!chosen[i]){chosen[i]=id;break;}}}
      else if(action==='remove')chosen[chosen.indexOf(id)]=null;
      else if(action==='clear')chosen=[];
      else if(action==='recommend')chosen=(await get('/api/arena/recommend?mode=custom')).players;
      else if(action==='prev')page--;
      else if(action==='next')page++;
      else if(action==='create'){customConfig=null;await command('create',{mode:'custom',players:chosen,human_id:''});}
      else if(action==='pick')await command('pick',{player_id:id});
      else if(action==='ban')await command('ban',{map:b.dataset.map});
      else if(action==='side')await command('choose_side',{side:b.dataset.side});
      else if(action==='configure'){await command('configure',cfg);customConfig=null;}
      else if(action==='launch'){if(mode!=='custom'||await command('configure',cfg))await command('launch');}
      else if(action==='retry')await command('launch');
      else if(action==='ingest')await command('ingest');
      else if(action==='cancel'){if(data.lobby?.phase==='finished'||confirm(tr('关闭当前房间？已保存战绩不会删除。')))await command('cancel');}
      else if(action==='refresh'){data=await get('/api/arena');autoError=false;}
      else if(action==='report')report=data.history.find(r=>r.id===id);
      else if(action==='back')report=null;
    }catch(err){toast(err.message,true);}
    finally{busy=false;draw();}
  }
  CareerUI.pages.arena=async(_route,node,isActive)=>{
    active=isActive;host=node;
    const next=await get('/api/arena');if(!isActive()||busy)return;
    if(data&&next.revision<data.revision)return;
    data=next;if(data.lobby){mode=data.lobby.mode==='custom'?'custom':'rank';if(data.lobby.human_id)human=data.lobby.human_id;}
    if(!data.lobby)human=careerHuman();
    host.onclick=click;
    host.oninput=e=>{if(e.target.matches('[data-arena-search]')){query=e.target.value;page=0;pool();}};
    host.onchange=e=>{if(e.target.matches('[data-arena-map],[data-arena-ct],[data-arena-human]'))customConfig=config();};
    draw();
  };
})();
