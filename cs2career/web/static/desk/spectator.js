/* Presentation only: the server saves one result before this modal opens.
 * No roll/settlement endpoint is called by pause, skip, or the round timer. */
(() => {
  let active = false;
  function phase(round) {
    if (round < 12) return '上半场';
    if (round < 24) return '下半场';
    return `加时 ${Math.floor((round - 24) / 6) + 1} · ${(round - 24) % 6 < 3 ? '上' : '下'}半场`;
  }
  function boundary(round) { return round === 12 || (round >= 24 && (round - 24) % 3 === 0); }
  function show(host, data) {
    if (!data?.maps?.length) return Promise.resolve();
    return new Promise(resolve => {
      let index = 0, round = 0, score = [0, 0], series = [...data.initial];
      let timer = null, running = false, mapDone = false, speed = 1, disposed = false;
      const finish = () => { disposed = true; clearTimeout(timer); resolve(); };
      const mount = () => {
        const mp = data.maps[index];
        host.innerHTML = `<section class="watch-card"><div class="watch-top"><span>CAREER MATCHDAY · BO${Number(data.best_of)}</span><button class="btn sm" data-skip>跳过观赛 → 战报</button></div>
          <h2>第 ${Number(mp.index) + 1} 图 · ${esc(mapName(mp.map))}</h2>
          <div class="watch-series" data-series></div><div class="watch-score"><div>${crest(data.teams[0],48)}<b>${esc(data.teams[0])}</b></div><strong data-score>0 : 0</strong><div>${crest(data.teams[1],48)}<b>${esc(data.teams[1])}</b></div></div>
          <div class="watch-status" data-status aria-live="polite"></div><div class="watch-rounds" data-rounds></div>
          <div class="watch-controls"><button class="btn primary" data-next></button><label>比分速度 <select data-speed><option value="1">正常</option><option value="2">2×</option><option value="4">4×</option></select></label></div>
          <p class="hint">每回合揭晓真实模拟结果 · 半场休息时由你继续 · 赛果已保存，关闭或跳过不会重抽。</p></section>`;
        host.querySelector('[data-skip]').onclick = finish;
        host.querySelector('[data-speed]').value = String(speed);
        host.querySelector('[data-speed]').onchange = e => { speed = Number(e.target.value) || 1; };
        host.querySelector('[data-next]').onclick = () => {
          if (disposed) return;
          if (mapDone) {
            if (index === data.maps.length - 1) { finish(); return; }
            index++; round = 0; score = [0, 0]; mapDone = false; mount(); return;
          }
          if (!mp.events_available) { completeMap(); return; }
          running = !running;
          clearTimeout(timer);
          paint();
          if (running) schedule();
        };
        paint();
        host.querySelector('[data-next]').focus();
      };
      const paint = () => {
        const mp = data.maps[index];
        host.querySelector('[data-series]').textContent = `系列赛 ${series[0]} : ${series[1]}`;
        host.querySelector('[data-score]').textContent = mapDone ? mp.score.replace('-', ' : ') : `${score[0]} : ${score[1]}`;
        const status = mapDone ? `${mp.winner} 拿下本图` : !mp.events_available ? '缺少完整回合记录，仅能查看已保存的本图结果。'
          : !running && boundary(round) ? (round === 12 ? '半场休息 · 准备交换攻防' : round === 24 ? '进入加时 · 比赛还没有结束' : '加时换边 · 深呼吸，继续')
          : `${phase(round)} · ${round ? `已结束 ${round} 回合` : '等待开赛'}${Math.max(...score) === 12 && round < 24 ? ' · 图点' : ''}`;
        host.querySelector('[data-status]').textContent = status;
        host.querySelector('[data-next]').textContent = mapDone ? (index === data.maps.length - 1 ? '查看完整战报' : '准备下一张图 →')
          : !mp.events_available ? '揭晓本图结果' : running ? '暂停' : round === 0 ? '开始上半场' : round === 12 ? '开始下半场' : round >= 24 && boundary(round) ? '继续加时' : '继续比分';
      };
      const completeMap = () => {
        running = false; mapDone = true;
        const side = data.teams.indexOf(data.maps[index].winner);
        if (side >= 0) series[side]++;
        paint();
      };
      const tick = () => {
        if (disposed || !running) return;
        const mp = data.maps[index], side = mp.rounds[round] === 'a' ? 0 : 1;
        score[side]++; round++;
        const cell = document.createElement('span');
        cell.className = `watch-round side-${side}`;
        cell.textContent = `${score[0]}:${score[1]}`;
        cell.title = `R${round} · ${data.teams[side]} 获胜`;
        host.querySelector('[data-rounds]').appendChild(cell);
        if (round === mp.rounds.length) { completeMap(); return; }
        if (boundary(round)) running = false;
        paint();
        if (running) schedule();
      };
      const schedule = () => { timer = setTimeout(tick, (Math.max(...score) >= 11 ? 850 : 550) / speed); };
      mount();
    });
  }
  window.CareerWatch = {
    phase, boundary,
    async run(match) {
      if (active) return;
      active = true;
      const host = document.createElement('div'), previous = document.activeElement;
      host.className = 'watch-overlay'; host.setAttribute('role','dialog'); host.setAttribute('aria-modal','true'); host.setAttribute('aria-label','模拟比赛观赛');
      host.innerHTML = '<section class="watch-card"><h2>正在准备比赛…</h2><p>已打完的地图会保留，请稍候。</p></section>';
      document.body.appendChild(host);
      host.tabIndex = -1; host.focus();
      const shell = document.querySelector('.app');
      const wasInert = shell?.inert;
      if (shell) shell.inert = true;
      const trap = e => {
        if (e.key !== 'Tab') return;
        const nodes = [...host.querySelectorAll('button,select')].filter(n=>!n.disabled);
        if (!nodes.length) { e.preventDefault(); return; }
        const first=nodes[0], last=nodes[nodes.length-1];
        if (e.shiftKey && document.activeElement===first) {e.preventDefault();last.focus();}
        else if (!e.shiftKey && document.activeElement===last) {e.preventDefault();first.focus();}
      };
      host.addEventListener('keydown', trap);
      try {
        await post('/api/series/skip', {match_id:match.id, reveal:true}, {beforeApply:data=>show(host,data.reveal)});
      } catch (err) {
        toast(`观赛未完成：${err.message}。如网络中断，请重新打开战报确认已保存结果，不要重复结算。`, true);
      } finally {
        host.remove(); active=false;
        if (shell) shell.inert=wasInert;
        if (previous?.isConnected) previous.focus();
        ensureCs2AutoIngest();
      }
    },
  };
})();
