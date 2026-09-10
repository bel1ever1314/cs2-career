/* Career creation consumes the backend origin catalogue; no UI balance constants. */
let SETUP_BUSY=false;
async function loadSetupTeams(era) {
  if (SETUP.era === era && SETUP.teams) return SETUP.teams;
  const data = await get(`/api/setup?era=${encodeURIComponent(era)}`);
  SETUP = { era, teams: data.teams || [], coverage: data.data_coverage };
  return SETUP.teams;
}

function renderSetup() {
  const origins=S.career.origins||[];
  const origin=origins.find(o=>o.id===DRAFT.origin)||origins[0];
  const eras = S.career.eras || {};
  if (SETUP.era !== DRAFT.era) {
    loadSetupTeams(DRAFT.era).then(() => { if (VIEW === "setup") renderSetup(); }).catch(() => {});
  }
  const teams = [...(SETUP.era === DRAFT.era && SETUP.teams ? SETUP.teams : [])]
    .sort((a, b) => (a.rank || 99) - (b.rank || 99));
  if (!teams.length) {
    $("view-setup").innerHTML = `<div class="page-head"><h2>开始生涯</h2></div><p class="hint">正在读取 ${esc(DRAFT.era)} 的名单…</p>`;
    return;
  }
  const picked = teams.find((t) => t.id === DRAFT.team_id) || teams[0];
  if (picked) DRAFT.team_id = picked.id;

  let h = `<div class="page-head"><h2>开始生涯</h2><span class="hint">选一个年代，加入现有队伍或自建队伍</span></div>`;
  if (S.career.legacy_save_notice) {
    h += `<div class="card" style="margin-bottom:12px;border-color:#8a5a20"><h3>旧存档已备份</h3><p class="hint">${esc(S.career.legacy_save_notice)}</p></div>`;
  }

  h += `<div class="card"><h3>年代</h3><div class="era-pick">`;
  for (const [key, meta] of Object.entries(eras)) {
    h += `<button class="era ${DRAFT.era === key ? "on" : ""}" data-era="${key}">
      <b>${key} · ${esc(meta.title)}</b><small>${esc(meta.blurb)}</small></button>`;
  }
  h += `</div></div>`;
  if(SETUP.coverage){
    const d=SETUP.coverage;
    h+=`<div class="notice compact-notice"><span>开局名单核验 ${d.verified_rosters}/${d.teams} 队 · 占位选手 ${d.placeholder_players} 人。年代数据仍在补全；有真实昵称不代表阵容与能力已核验。资料更新仅用于新生涯，旧档战绩保持原身份。</span></div>`;
  }

  if(DRAFT.mode==='create')h+=`<div class="origin-grid">${origins.map(o=>`<button class="origin-card ${o.id===DRAFT.origin?'selected':''}" data-origin="${o.id}"><small>${esc(o.tagline)}</small><h3>${esc(o.name)}</h3><b>${o.player_ability}</b><span>开局个人能力</span><p>${esc(o.description)}</p><div>俱乐部 ${money(o.club_money)} · 个人 ${money(o.pocket_money)}</div><div>队友 ${o.mate_min}–${o.mate_max} · 属性点 ${o.attr_points}</div></button>`).join('')}</div>`;
  h += `<div class="grid2" style="margin-top:12px">`;
  h += `<div class="card"><h3>方式</h3><div class="chips" style="margin-bottom:12px">
      <button data-mode="join" class="${DRAFT.mode === "join" ? "on" : ""}">加入现役队伍</button>
      <button data-mode="create" class="${DRAFT.mode === "create" ? "on" : ""}">自建队伍</button>
    </div>
    <div class="form">
      <label>位置<div class="chips" id="role-pick">${(S.career.roles || Object.keys(ROLE))
        .map((r) => `<button data-role="${r}" class="${DRAFT.role === r ? "on" : ""}">${ROLE[r] || r}</button>`)
        .join("")}</div></label>`;

  if (DRAFT.mode === "create") {
    h += `<label>选手 ID<input id="in-name" value="${esc(DRAFT.name || "")}" placeholder="你的游戏 ID" maxlength="32"></label>
      <label>队名<input id="in-org" value="${esc(DRAFT.org || "")}" placeholder="队伍名称" maxlength="40"></label>
      <label>赛区<select id="in-region">${Object.entries(REGION)
        .map(([k, v]) => `<option value="${k}" ${DRAFT.region === k ? "selected" : ""}>${v}</option>`)
        .join("")}</select></label>
      <label>队标（PNG，可选）<input type="file" id="in-logo" accept="image/png"></label>
      ${DRAFT.logo ? `<div class="row"><img class="crest" style="--sz:46px" src="${DRAFT.logo}"><span class="hint">已选好队标</span></div>` : ""}`;
  } else {
    h += `<label>队伍<select id="in-team">${teams
      .map((t) => `<option value="${esc(t.id)}" ${DRAFT.team_id === t.id ? "selected" : ""}>#${t.rank} ${esc(t.name)}</option>`)
      .join("")}</select></label>`;
    const roster = picked?.players || [];
    h += `<label>接管谁<select id="in-replace">${roster
      .map((p) => `<option value="${esc(p.name)}" ${DRAFT.replace === p.name ? "selected" : ""}>${esc(p.name)}${p.roster_status==='stand_in'?'（代打）':''} · ${esc(ROLE[p.role] || p.role)}${p.is_igl&&p.role!=='igl'?' / 兼指挥':''} · ${Math.round(p.ability)}</option>`)
      .join("")}</select></label>`;
  }
  h += `<button class="btn primary" id="btn-create">开始</button></div></div>`;

  h += `<div class="card"><h3>${DRAFT.mode === "create" ? "从零开始" : "队伍情报"}</h3>`;
  if (DRAFT.mode === "create") {
    h += `<p class="hint">${esc(origin?.name||"自建开局")}：俱乐部资金 ${money(origin?.club_money)}，个人资金 ${money(origin?.pocket_money)}。从地区邀请赛开始积累成绩；成长、阵容和赛事选择共同决定进程，不保证固定年限晋级。</p>`;
  } else if (picked) {
    h += `<div class="row" style="margin-bottom:10px">${crest(picked.name, 38)}
      <div><b style="font-size:15px">${esc(picked.name)}</b><br><small class="hint">#${picked.rank} · ${REGION[picked.region]} · 赛训 ${picked.command}</small></div></div>
      <p class="hint" style="margin:0 0 10px">${esc(picked.data_provenance?.label||DRAFT.era+' 开局名单')}<br>${esc(picked.data_provenance?.note||'')}</p>
      <table><tbody>${(picked.players || [])
        .map((p) => `<tr><td>${esc(p.name)}</td><td>${roleBadge(p.role)}</td><td class="num">${Math.round(p.ability)}</td><td class="num">${p.age}岁</td></tr>`)
        .join("")}</tbody></table>`;
  }
  h += `</div></div>`;

  if(S.career.exists)h+='<div class="notice compact-notice"><span>开始新的生涯前会自动备份当前存档；取消不会清空原档。</span><button class="btn" data-route="home">返回当前生涯</button></div>';
  $("view-setup").innerHTML = h;
  for(const id of ['in-name','in-org'])if($(id))$(id).oninput=e=>DRAFT[id==='in-name'?'name':'org']=e.target.value;
  document.querySelectorAll('[data-origin]').forEach(b=>b.onclick=()=>{DRAFT.origin=b.dataset.origin;renderSetup();});

  document.querySelectorAll("[data-era]").forEach((b) => (b.onclick = () => {
    DRAFT.era = b.dataset.era;
    DRAFT.replace = "";
    SETUP = { era: "", teams: null };
    renderSetup();
  }));
  document.querySelectorAll("[data-mode]").forEach((b) => (b.onclick = () => { DRAFT.mode = b.dataset.mode; renderSetup(); }));
  document.querySelectorAll("[data-role]").forEach((b) => (b.onclick = () => { DRAFT.role = b.dataset.role; renderSetup(); }));

  const teamSel = $("in-team");
  if (teamSel) teamSel.onchange = () => { DRAFT.team_id = teamSel.value; DRAFT.replace = ""; renderSetup(); };
  const repSel = $("in-replace");
  if (repSel) {
    if (!DRAFT.replace) DRAFT.replace = repSel.value;
    repSel.onchange = () => {
      DRAFT.replace = repSel.value;
      const row = (picked?.players || []).find((p) => p.name === DRAFT.replace);
      if (row?.role) {
        DRAFT.role = row.role;
        document.querySelectorAll("[data-role]").forEach((b) => b.classList.toggle("on", b.dataset.role === DRAFT.role));
      }
    };
  }
  const regSel = $("in-region");
  if (regSel) regSel.onchange = () => { DRAFT.region = regSel.value; };
  const logo = $("in-logo");
  if (logo) {
    logo.onchange = () => {
      const file = logo.files?.[0];
      if (!file) return;
      if (file.size > 3 * 1024 * 1024) return toast("图片要小于 3MB", true);
      const fr = new FileReader();
      fr.onload = () => { DRAFT.logo = fr.result; renderSetup(); };
      fr.readAsDataURL(file);
    };
  }

  $("btn-create").onclick = async () => {
    if(SETUP_BUSY)return;
    const body = { era: DRAFT.era, mode: DRAFT.mode, role: DRAFT.role, origin:DRAFT.origin };
    if (DRAFT.mode === "create") {
      body.name = ($("in-name")?.value || "").trim();
      body.org = ($("in-org")?.value || "").trim();
      body.region = $("in-region")?.value || "AS";
      if (!body.name || !body.org) return toast("选手 ID 和队名都要填", true);
    } else {
      body.team_id = $("in-team")?.value;
      body.replace = $("in-replace")?.value;
    }
    SETUP_BUSY=true;$("btn-create").disabled=true;
    try {
    const out = await post("/api/career/create", body);
    if (out.ok && DRAFT.mode === "create" && DRAFT.logo) {
      await post("/api/logo", { data: DRAFT.logo, team_id: S.career.team_id });
    }
    if (out.ok) show("home");
    } finally {SETUP_BUSY=false;if(VIEW==="setup")renderSetup();}
  };
}


CareerUI.pages.setup=()=>renderSetup();
