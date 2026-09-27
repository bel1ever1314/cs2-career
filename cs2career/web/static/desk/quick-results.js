/* Read-only quick-mode results. Stable player IDs, never nickname matching.
   This module cannot simulate, settle rewards or acknowledge a story. */
(() => {
  const t=value=>window.CareerI18n?.t(value)||value;
  const number=(value,digits=0)=>typeof value==='number'&&Number.isFinite(value)?value.toFixed(digits):'—';
  function outcome(winner,team){return winner&&team?(winner===team?'win':'loss'):'';}
  function mapOutcome(match,index){
    const winner=(match?.winners||[])[index-1],team=match?.player_team;
    return team&&[match.team_a,match.team_b].includes(winner)?outcome(winner,team):'';
  }
  function results(data,match){
    const rows=(data?.series_results||[]).filter(r=>r.id&&typeof r.won==='boolean');
    if(match?.report&&match.played&&match.result_id&&match.player_team&&[match.team_a,match.team_b].includes(match.winner))
      rows.push({id:match.result_id,date:match.date||'',won:match.winner===match.player_team});
    return [...new Map(rows.map(r=>[r.id,r])).values()].sort((a,b)=>String(a.date).localeCompare(String(b.date)));
  }
  function recordHTML(data,match){
    const rows=results(data,match),wins=rows.filter(r=>r.won).length;
    const count=rows.length?{wins,losses:rows.length-wins}:data.summary||{};
    return `<small>${t('本季战绩')}</small><b>${count.wins??'—'} <span>${t('胜')}</span> / ${count.losses??'—'} <span>${t('负')}</span></b>
      <div class="quick-dots" role="list" aria-label="${esc(t('本季系列赛 · 从左到右，先早后晚'))}" style="--dot-rows:${Math.max(1,Math.ceil(rows.length/20))}">${rows.map((r,i)=>{
        const label=`${i+1} · ${r.date||''} · ${t(r.won?'胜':'负')}`;
        return `<i class="result-dot ${r.won?'win':'loss'}" role="listitem" title="${esc(label)}" aria-label="${esc(label)}"></i>`;
      }).join('')}</div><span>${t('绿胜红负 · 每点一场系列赛')}</span>`;
  }
  function scorecard(match){
    const rows=match.totals||[],you=rows.filter(r=>match.player_id&&r.player_id===match.player_id&&r.team===match.player_team);
    const player=you.length===1?you[0]:null;
    const kda=p=>`${number(p.k)} / ${number(p.d)} / ${number(p.a)}`;
    const rate=(p,k,d)=>p.data_complete===false?'—':number(p[k],d);
    const teamTable=team=>`<section class="quick-team-report"><h4 data-no-i18n>${esc(team)}</h4><table><thead><tr><th>${t('选手')}</th><th>K/D/A</th><th class="quick-extra-stat">DMG</th><th>ADR</th><th class="quick-extra-stat">KAST</th><th>Rating</th></tr></thead><tbody>${rows.filter(r=>r.team===team).map(p=>`<tr class="${p===player?'quick-you':''}"><td><span data-no-i18n>${esc(p.name)}</span>${p===player?`<em>${t('你')}</em>`:''}</td><td>${kda(p)}</td><td class="quick-extra-stat">${number(p.damage)}</td><td>${rate(p,'adr',1)}</td><td class="quick-extra-stat">${p.data_complete!==false&&typeof p.kast==='number'?number(p.kast*100)+'%':'—'}</td><td>${rate(p,'rating',2)}</td></tr>`).join('')}</tbody></table></section>`;
    return `<div class="quick-report-heading"><b>${t('全场战绩')}</b><span data-no-i18n>${esc(match.team_a)} ${esc(match.series||'')} ${esc(match.team_b)}</span></div>
      ${player?`<div class="quick-player-spotlight"><strong><em>${t('你')}</em> <span data-no-i18n>${esc(player.name)}</span></strong><span>K/D/A <b>${kda(player)}</b></span><span>ADR <b>${rate(player,'adr',1)}</b></span><span>Rating <b>${rate(player,'rating',2)}</b></span></div>`:`<p class="hint">${t('未找到可确认的玩家身份，不猜测归属。')}</p>`}
      <div class="quick-team-reports">${[match.team_a,match.team_b].map(teamTable).join('')}</div>
      ${match.data_complete===false||!rows.length?`<p class="quick-report-warning">${t('部分历史数据缺失，仅显示已有记录。')}</p>`:''}`;
  }
  window.CareerQuickResults={outcome,mapOutcome,results,recordHTML,scorecard};
})();
