"use strict";

let S = null;             // last /api/state payload
let VIEW = "home";
let FOCUS = null;         // focused event id
let MATCH = null;         // focused match id
let DETAIL = null;        // cached match detail
let PLAY_TIMER = null;
let SERIES_TIMER = null;
let SERIES_RESULT = null;
let SERIES_SIDE = "ct";
let SERIES_CS2 = null;
let SERIES_TRIED = "";
let DRAFT = { era: "2026", mode: "join", role: "rifle", team_id: "", replace: "", region: "AS", logo: "" };

const ROLE = { awp: "主狙", igl: "指挥", entry: "突破手", lurk: "自由人", support: "辅助", rifle: "步枪手" };
const MAPS = {
  dust2: "Dust2", mirage: "Mirage", inferno: "Inferno", nuke: "Nuke",
  ancient: "Ancient", anubis: "Anubis", overpass: "Overpass", train: "Train",
};
const CS2_MAPS = {
  de_dust2: "Dust2", de_mirage: "Mirage", de_inferno: "Inferno", de_nuke: "Nuke",
  de_ancient: "Ancient", de_anubis: "Anubis", de_overpass: "Overpass", de_train: "Train",
};
const CLS = { major: "Major", premier: "Premier", t1: "T1", t2: "T2", cct: "CCT", qual: "RMR", playin: "附加赛" };
const STATUS = { upcoming: "未开始", live: "进行中", done: "已结束" };
const FORMAT = { swiss_playoff: "瑞士轮 + 淘汰赛", gsl_playoff: "小组赛 + 淘汰赛", single_elim: "单败淘汰" };
const REGION = { EU: "欧洲", AM: "美洲", AS: "亚洲" };
const PLACE = { champion: "冠军", final: "亚军", sf: "四强", qf: "八强", stage: "小组赛" };
const MONTHS = ["一月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "十一月", "十二月"];

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const money = (n) => "$" + Math.round(n || 0).toLocaleString("en-US");
const r2 = (x) => (x == null || Number.isNaN(x) ? "—" : Number(x).toFixed(2));
const mapName = (m) => MAPS[m] || m;

let TEAMS = {};
const team = (name) => TEAMS[name] || { name, crest: { kind: "mark", color: "#333", ink: "#fff", tag: (name || "?").slice(0, 3) } };

/* ----------------------------------------------------------------- net */

async function get(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function post(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json().catch(() => ({ ok: false, msg: "服务器没有回应" }));
  if (data.state) adopt(data.state);
  if (data.ok === false) toast(data.msg || "失败", true);
  else if (data.msg) toast(data.msg, false);
  if (VIEW === "match" && MATCH) await refreshDetail();
  render();
  takeStories(data.stories || data.state?.career?.stories);
  return data;
}

async function refreshDetail() {
  if (!MATCH) return;
  try {
    DETAIL = await get(`/api/match?id=${encodeURIComponent(MATCH)}`);
  } catch {
    DETAIL = null;
  }
}

function jumpToYourMatch() {
  const ym = S?.your_match;
  if (!ym?.match?.id) return false;
  FOCUS = ym.event.id;
  openMatch(ym.match.id);
  return true;
}

let toastTimer = null;
function toast(text, bad) {
  if (!text) return;
  let el = document.querySelector(".toast");
  if (!el) {
    el = document.createElement("div");
    document.body.appendChild(el);
  }
  el.className = "toast" + (bad ? " err" : "");
  el.textContent = text;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.remove(), 4200);
}

function adopt(state) {
  S = state;
  TEAMS = {};
  for (const t of S.teams || []) TEAMS[t.name] = t;
  if (!FOCUS || !S.events.some((e) => e.id === FOCUS)) FOCUS = defaultEvent();
}

function defaultEvent() {
  const live = S.events.find((e) => e.status === "live");
  if (live) return live.id;
  const next = S.events.find((e) => e.status === "upcoming");
  if (next) return next.id;
  const done = [...S.events].reverse().find((e) => e.status === "done");
  return done ? done.id : S.events[0]?.id;
}

/* ----------------------------------------------------------------- bits */

function crest(name, size = 22) {
  const c = team(name).crest || {};
  if (c.kind === "image" && c.src) {
    return `<img class="crest" style="--sz:${size}px" src="${esc(c.src)}" alt="">`;
  }
  return `<span class="crest mark" style="--sz:${size}px;background:${esc(c.color || "#333")};color:${esc(c.ink || "#fff")}">${esc(c.tag || "?")}</span>`;
}

function tm(name, size = 22, extra = "") {
  if (!name || name === "BYE") return `<span class="tm"><span class="l">轮空</span></span>`;
  return `<span class="tm ${extra}">${crest(name, size)}<span>${esc(name)}</span></span>`;
}

const badge = (kind, text) => `<span class="badge ${kind}">${esc(text)}</span>`;
const roleBadge = (role) => badge(role || "rifle", ROLE[role] || role || "");

const AXIS = {
  entry: "突破", trade: "补枪", nade: "道具", clutch: "残局",
  aim: "枪法", open: "开战", move: "身法", command: "指挥",
};
const MAIL_KIND = { invite: "邀请", prize: "奖金", sponsor: "赞助", qualify: "出线", ops: "经营", whisper: "来信", discipline: "纪律" };
const RARITY = { milspec: "军规", restricted: "受限", classified: "保密", covert: "隐秘", extraordinary: "非凡" };
const MAIL_STATUS = {
  open: "待处理", accepted: "已接受", declined: "已婉拒",
  expired: "已过期", claimed: "已领取",
};

function axisLabels() {
  return S?.career?.axis_labels || AXIS;
}
function axisKeys() {
  return S?.career?.axes || Object.keys(AXIS);
}
function plink(name) {
  return `<button type="button" class="js-player" data-player="${esc(name)}">${esc(name)}</button>`;
}
function tlink(name, size = 20) {
  if (!name || name === "BYE") return tm(name, size);
  return `<button type="button" class="js-team" data-team="${esc(name)}">${crest(name, size)}<span>${esc(name)}</span></button>`;
}
function bindInspect(root) {
  const box = root || document;
  box.querySelectorAll(".js-player").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); openInspect("player", b.dataset.player); };
  });
  box.querySelectorAll(".js-team").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); openInspect("team", b.dataset.team); };
  });
}
function axisPanel(stats, opts = {}) {
  const labels = axisLabels();
  const spend = Boolean(opts.spend && (S.career?.attr_points || 0) > 0);
  let h = `<div class="axis-grid">`;
  for (const k of axisKeys()) {
    const v = Math.round(Number(stats?.[k] ?? 0));
    h += `<div class="axis-row"><span>${esc(labels[k] || k)}</span>
      <div class="bar"><i style="width:${Math.min(100, v)}%"></i></div>
      <b>${v || "—"}</b>
      ${spend ? `<button class="btn sm" data-axis="${k}">+</button>` : ""}</div>`;
  }
  return h + `</div>`;
}
function bindAxisSpend(root) {
  (root || document).querySelectorAll("[data-axis]").forEach((b) => {
    b.onclick = () => post("/api/attr", { axis: b.dataset.axis });
  });
}
function honoursMedals(hon) {
  const n = hon?.counts || {};
  return `<div class="medals" style="margin-bottom:14px">
    <div class="medal gold"><b>${n.titles || 0}</b><small>冠军</small></div>
    <div class="medal gold"><b>${n.majors || 0}</b><small>Major</small></div>
    <div class="medal"><b>${n.premiers || 0}</b><small>Premier</small></div>
    <div class="medal gold"><b>${n.mvp_elite || 0}</b><small>精英 MVP</small></div>
    <div class="medal"><b>${n.mvp_t1 || 0}</b><small>T1 MVP</small></div>
    <div class="medal"><b>${n.mvp_cct || 0}</b><small>CCT MVP</small></div>
    <div class="medal"><b>${n.evp || 0}</b><small>赛事 EVP</small></div>
    <div class="medal gold"><b>${n.best_top20 ? "#" + n.best_top20 : "—"}</b><small>年度最高</small></div>
  </div>`;
}
function honoursLists(hon) {
  hon = hon || { titles: [], mvp: [], evp: [], top20: [] };
  let h = `<div class="grid2">`;
  h += `<div class="card"><h3>冠军奖杯</h3>`;
  h += hon.titles.length
    ? [...hon.titles].reverse().map((t) => `<div class="trophy-row ${t.class}"><span class="ic">🏆</span>
        <div><b>${esc(t.event)}</b><br><small>${CLS[t.class] || t.class} · ${esc(t.team || "")}</small></div>
        <span class="when">${t.date}</span></div>`).join("")
    : `<p class="empty">奖杯柜是空的</p>`;
  h += `</div>`;
  h += `<div class="card"><h3>个人奖项</h3>`;
  const awardRows = [
    ...(hon.mvp || []).map((x) => ({ ...x, kind: x.title || awardTitle("mvp", x.class), ic: "⭐" })),
    ...(hon.evp || []).map((x) => ({ ...x, kind: x.title || awardTitle("evp", x.class), ic: "✦" })),
  ].sort((a, b) => (a.date < b.date ? 1 : -1));
  h += awardRows.length
    ? awardRows.map((x) => `<div class="trophy-row ${x.class}"><span class="ic">${x.ic}</span>
        <div><b>${esc(x.kind)}</b><br><small>${esc(x.event)} · Rating ${r2(x.rating)}${x.from_finalist ? " · 决赛败方" : ""}</small></div>
        <span class="when">${x.date}</span></div>`).join("")
    : `<p class="empty">还没有拿过赛事奖项</p>`;
  h += `</div></div>`;
  h += `<div class="card" style="margin-top:12px"><h3>年度 Top 20</h3>`;
  h += hon.top20.length
    ? `<table><thead><tr><th>年份</th><th class="num">名次</th><th class="num">Rating</th></tr></thead><tbody>${hon.top20
        .map((t) => `<tr><td>${t.year}</td><td class="num">#${t.rank}</td><td class="num">${r2(t.rating)}</td></tr>`)
        .join("")}</tbody></table>`
    : `<p class="empty">赛季结束时评选</p>`;
  return h + `</div>`;
}

let INSPECT = null;
async function openInspect(kind, key) {
  const q = kind === "player" ? `player=${encodeURIComponent(key)}` : `team=${encodeURIComponent(key)}`;
  try {
    INSPECT = await get(`/api/inspect?${q}`);
    if (INSPECT.error) { INSPECT = null; return toast("找不到资料", true); }
  } catch {
    INSPECT = null;
    return toast("找不到资料", true);
  }
  paintInspect();
}
function closeInspect() {
  INSPECT = null;
  const el = $("inspect-modal");
  if (el) el.remove();
}
function paintInspect() {
  let box = $("inspect-modal");
  if (!INSPECT) {
    if (box) box.remove();
    return;
  }
  if (!box) {
    box = document.createElement("div");
    box.id = "inspect-modal";
    document.body.appendChild(box);
    box.addEventListener("click", (e) => { if (e.target === box) closeInspect(); });
  }
  const row = INSPECT;
  let inner = `<button class="inspect-x" id="insp-x">×</button>`;
  if (row.kind === "team") {
    inner += `<div class="page-head" style="margin-bottom:12px">${crest(row.name, 36)}
      <div><h2>${esc(row.name)}</h2>
      <span class="hint">#${row.rank ?? "—"} ${REGION[row.region] || ""} · 赛训 ${row.command ?? "—"} · 士气 ${Math.round(row.mentality || 0)}</span></div></div>`;
    inner += `<div class="grid2">`;
    inner += `<div class="card pad0"><h3>阵容</h3><table><thead>
      <tr><th>选手</th><th>位置</th><th class="num">能力</th><th class="num">指挥</th><th class="num">年龄</th></tr></thead><tbody>`;
    for (const p of [...(row.players || [])].sort((a, b) => b.ability - a.ability)) {
      inner += `<tr class="${isMe(p.name) ? "me" : ""}"><td>${plink(p.name)}${p.you ? " ★" : ""}</td>
        <td>${roleBadge(p.role)}</td><td class="num">${Math.round(p.ability)}</td>
        <td class="num">${Math.round(p.command || 0)}</td><td class="num">${p.age}</td></tr>`;
    }
    inner += `</tbody></table></div>`;
    inner += `<div class="cards">
      <div class="card"><h3>地图</h3>
        <p><small class="hint">擅长</small><br>${(row.strong_maps || []).map((m) => badge("t1", mapName(m))).join(" ") || "—"}</p>
        <p><small class="hint">短板</small><br>${(row.weak_maps || []).map((m) => badge("qual", mapName(m))).join(" ") || "—"}</p></div>
      <div class="card"><h3>队史冠军</h3>${
        (row.honours || []).length
          ? row.honours.map((t) => `<div class="trophy-row ${t.class}"><span class="ic">🏆</span>
              <div><b>${esc(t.short)}</b></div><span class="when">${t.date}</span></div>`).join("")
          : `<p class="empty">还没有</p>`
      }</div></div></div>`;
  } else {
    inner += `<div class="page-head" style="margin-bottom:12px">
      <div><h2>${esc(row.name)}</h2>
      <span class="hint">${ROLE[row.role] || row.role || ""} · ${row.team ? esc(row.team) : "自由人"} · 能力 ${row.ability != null ? Math.round(row.ability) : "—"}</span></div></div>`;
    inner += `<div class="card" style="margin-bottom:12px"><h3>个人能力</h3>${axisPanel(row.stats)}</div>`;
    inner += honoursMedals(row.honours) + honoursLists(row.honours);
  }
  box.innerHTML = `<div class="inspect-card">${inner}</div>`;
  $("insp-x").onclick = closeInspect;
  bindInspect(box);
}

function myTeamName() {
  return S?.career?.exists ? S.career.team_name : "";
}

function isMe(playerName) {
  return S?.career?.exists && playerName === S.career.player_name;
}

function dateSpan(dates) {
  if (!dates?.length) return "";
  const a = dates[0].slice(5).replace("-", "/");
  const b = dates[dates.length - 1].slice(5).replace("-", "/");
  return a === b ? a : `${a} – ${b}`;
}

function destEvent(ev) {
  return (S.events || []).find((e) => e.id === ev.feeds) || null;
}

function eventPathHint(ev, short = false) {
  const dest = destEvent(ev);
  if (ev.type === "major") {
    return (S.year || 2026) >= 2025
      ? (short ? "VRS 前十六直邀" : "2025 起 Major 按 VRS 排名直邀，没有 RMR。")
      : (short ? "RMR 出线或世界前八" : "2024 Major：各赛区 RMR 出线 + 世界前八直邀。");
  }
  if (ev.type === "t1") {
    const n = ev.direct || (dest || ev).direct;
    const hasQ = (S.events || []).some((e) => e.feeds === ev.id);
    if (hasQ) {
      return short ? `VRS 前 ${n || 12} 直邀，其余看附加赛` : `VRS 前 ${n || 12} 直邀。剩下的名额由附加赛打出来，出线会发庆祝信。`;
    }
    return short ? "按 VRS 排名邀请" : "按当前 VRS 排名邀请，没有附加赛。";
  }
  if (ev.type === "qual") {
    if (dest?.type === "major") {
      return short ? "赛区 RMR" : "RMR 按赛区邀请。打出资格后会发庆祝信，并附上 Major 确认函。";
    }
    return short ? "大赛附加赛" : "大赛附加赛。打出资格后会发庆祝信，并附上正赛确认函。";
  }
  return short ? `奖金池 ${money(ev.prize)}` : "不再自行报名。接受邀请后才会进入签表";
}

function ratingTable(rows, opts = {}) {
  if (!rows?.length) return `<p class="empty">还没有数据</p>`;
  const vs = rows.some((r) => "rating_top5" in r);
  let h = `<table><thead><tr><th>#</th><th>选手</th><th>队伍</th><th class="num">Rating</th>`;
  if (vs) h += `<th class="num" title="对世界前5">vs T5</th><th class="num" title="对世界前10">vs T10</th><th class="num" title="对世界前20">vs T20</th>`;
  h += `<th class="num">K-D-A</th><th class="num">KPR</th><th class="num">图</th></tr></thead><tbody>`;
  rows.forEach((r, i) => {
    h += `<tr class="${isMe(r.player) ? "me" : ""}"><td>${opts.rank ? r.rank || i + 1 : i + 1}</td>
      <td>${opts.inspect ? plink(r.player) : esc(r.player)}</td>
      <td>${opts.inspect ? tlink(r.team, 18) : tm(r.team, 18)}</td><td class="num">${r2(r.rating)}</td>`;
    if (vs) h += `<td class="num">${r2(r.rating_top5)}</td><td class="num">${r2(r.rating_top10)}</td><td class="num">${r2(r.rating_top20)}</td>`;
    h += `<td class="num">${r.k}-${r.d}-${r.a}</td><td class="num">${Number(r.kpr).toFixed(2)}</td><td class="num">${r.maps ?? "—"}</td></tr>`;
  });
  return h + `</tbody></table>`;
}

function boxTable(lines) {
  const rows = [...lines].sort((a, b) => b.rating - a.rating || b.k - a.k);
  let h = `<table><thead><tr><th>选手</th><th class="num">Rating</th><th class="num">K-D-A</th><th class="num">KPR</th></tr></thead><tbody>`;
  for (const p of rows) {
    h += `<tr class="${isMe(p.name) ? "me" : ""}"><td>${esc(p.name)}</td><td class="num">${r2(p.rating)}</td>
      <td class="num">${p.k}-${p.d}-${p.a}</td><td class="num">${Number(p.kpr).toFixed(2)}</td></tr>`;
  }
  return h + `</tbody></table>`;
}

/* ----------------------------------------------------------------- shell */

function renderShell() {
  $("top-date").textContent = `${S.date}`;
  const has = S.career?.exists;
  $("nav-career").style.display = has ? "" : "none";
  document.querySelectorAll("[data-view]").forEach((b) => b.classList.toggle("on", b.dataset.view === VIEW));
  $("btn-next").disabled = !has || !!S.career?.banned;
  $("btn-skip").disabled = !has || !!S.career?.banned;
  const dot = $("mail-dot");
  if (dot) {
    const n = S.career?.unread || 0;
    dot.hidden = !has || n <= 0;
    dot.title = n ? `${n} 封未读` : "";
  }

  const foot = $("side-foot");
  if (!has) {
    foot.innerHTML = `<button class="btn primary" id="foot-new">开始生涯</button>`;
    $("foot-new").onclick = () => show("setup");
    return;
  }
  const c = S.career;
  const vrs = c.vrs || {};
  foot.innerHTML = `
    <div class="team-chip">${crest(c.team_name, 30)}
      <div><b>${esc(c.team_name)}</b><small>#${vrs.rank ?? "—"} · ${Math.round(vrs.vrs ?? 0)}</small></div>
    </div>
    <div class="team-chip you">
      <div><b>${esc(c.player_name)}</b><small>${ROLE[c.role] || c.role} · ${c.you ? Math.round(c.you.ability) : "—"}</small></div>
    </div>
    <button class="btn ghost sm" id="foot-reset">重开生涯</button>`;
  $("foot-reset").onclick = () => {
    if (confirm(c.banned ? "这份档案已经结束。清空并重开？" : "清空当前生涯和赛季？")) post("/api/reset");
  };
}

function show(name) {
  if (name === "train") name = "play";
  VIEW = name;
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("on", v.id === "view-" + name));
  if (name !== "play" && PLAY_TIMER) {
    clearInterval(PLAY_TIMER);
    PLAY_TIMER = null;
  }
  if (name !== "match") stopSeriesPoll();
  render();
}

function render() {
  if (!S) return;
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("on", v.id === "view-" + VIEW));
  renderShell();
  const fn = {
    setup: renderSetup, home: renderHome, squad: renderSquad, honours: renderHonours,
    locker: renderLocker, mail: renderMail, market: renderMarket, play: renderPlay, schedule: renderSchedule,
    event: renderEvent, match: renderMatch, ranking: renderRanking, players: renderPlayers,
  }[VIEW];
  if (fn) fn();
}

/* ----------------------------------------------------------------- setup */

function renderSetup() {
  const eras = S.career.eras || {};
  const teams = [...(S.teams || [])].sort((a, b) => (a.rank || 99) - (b.rank || 99));
  const picked = teams.find((t) => t.id === DRAFT.team_id) || teams[0];
  if (picked && !DRAFT.team_id) DRAFT.team_id = picked.id;

  let h = `<div class="page-head"><h2>开始生涯</h2><span class="hint">选一个年代，加入现有队伍或自建队伍</span></div>`;

  h += `<div class="card"><h3>年代</h3><div class="era-pick">`;
  for (const [key, meta] of Object.entries(eras)) {
    h += `<button class="era ${DRAFT.era === key ? "on" : ""}" data-era="${key}">
      <b>${key} · ${esc(meta.title)}</b><small>${esc(meta.blurb)}</small></button>`;
  }
  h += `</div></div>`;

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
    h += `<label>选手 ID<input id="in-name" value="${esc(DRAFT.name || "")}" placeholder="你的游戏 ID" maxlength="16"></label>
      <label>队名<input id="in-org" value="${esc(DRAFT.org || "")}" placeholder="队伍名称" maxlength="24"></label>
      <label>赛区<select id="in-region">${Object.entries(REGION)
        .map(([k, v]) => `<option value="${k}" ${DRAFT.region === k ? "selected" : ""}>${v}</option>`)
        .join("")}</select></label>
      <label>队标（PNG，可选）<input type="file" id="in-logo" accept="image/png,image/jpeg"></label>
      ${DRAFT.logo ? `<div class="row"><img class="crest" style="--sz:46px" src="${DRAFT.logo}"><span class="hint">已选好队标</span></div>` : ""}`;
  } else {
    h += `<label>队伍<select id="in-team">${teams
      .map((t) => `<option value="${t.id}" ${DRAFT.team_id === t.id ? "selected" : ""}>#${t.rank} ${t.name}</option>`)
      .join("")}</select></label>`;
    const roster = picked?.players || [];
    h += `<label>接管谁<select id="in-replace">${roster
      .map((p) => `<option value="${esc(p.name)}" ${DRAFT.replace === p.name ? "selected" : ""}>${p.name} · ${ROLE[p.role] || p.role} · ${Math.round(p.ability)}</option>`)
      .join("")}</select></label>`;
  }
  h += `<button class="btn primary" id="btn-create">开始</button></div></div>`;

  h += `<div class="card"><h3>${DRAFT.mode === "create" ? "从零开始" : "队伍情报"}</h3>`;
  if (DRAFT.mode === "create") {
    h += `<p class="hint">自建队伍从世界第 45 位、四名新人和 $35,000 起步。本赛区 CCT 和小比赛会发邀请。对局可按角色数值结算；自己进 CS2 打需要另装人机增强。</p>`;
  } else if (picked) {
    h += `<div class="row" style="margin-bottom:10px">${crest(picked.name, 38)}
      <div><b style="font-size:15px">${esc(picked.name)}</b><br><small class="hint">#${picked.rank} · ${REGION[picked.region]} · 赛训 ${picked.command}</small></div></div>
      <table><tbody>${(picked.players || [])
        .map((p) => `<tr><td>${esc(p.name)}</td><td>${roleBadge(p.role)}</td><td class="num">${Math.round(p.ability)}</td><td class="num">${p.age}岁</td></tr>`)
        .join("")}</tbody></table>`;
  }
  h += `</div></div>`;

  $("view-setup").innerHTML = h;

  document.querySelectorAll("[data-era]").forEach((b) => (b.onclick = () => { DRAFT.era = b.dataset.era; renderSetup(); }));
  document.querySelectorAll("[data-mode]").forEach((b) => (b.onclick = () => { DRAFT.mode = b.dataset.mode; renderSetup(); }));
  document.querySelectorAll("[data-role]").forEach((b) => (b.onclick = () => { DRAFT.role = b.dataset.role; renderSetup(); }));

  const teamSel = $("in-team");
  if (teamSel) teamSel.onchange = () => { DRAFT.team_id = teamSel.value; DRAFT.replace = ""; renderSetup(); };
  const repSel = $("in-replace");
  if (repSel) repSel.onchange = () => { DRAFT.replace = repSel.value; };
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
    const body = { era: DRAFT.era, mode: DRAFT.mode, role: DRAFT.role };
    if (DRAFT.mode === "create") {
      body.name = ($("in-name")?.value || "").trim();
      body.org = ($("in-org")?.value || "").trim();
      body.region = $("in-region")?.value || "AS";
      if (!body.name || !body.org) return toast("选手 ID 和队名都要填", true);
    } else {
      body.team_id = $("in-team")?.value;
      body.replace = $("in-replace")?.value;
    }
    const out = await post("/api/career/create", body);
    if (out.ok && DRAFT.mode === "create" && DRAFT.logo) {
      await post("/api/logo", { data: DRAFT.logo, team_id: S.career.team_id });
    }
    if (out.ok) show("home");
  };
}

/* ----------------------------------------------------------------- home */

function renderHome() {
  const c = S.career;
  if (!c.exists) { show("setup"); return; }

  const live = S.events.find((e) => e.status === "live");
  const next = S.events.find((e) => e.status === "upcoming");
  const line = c.season_line;
  const cnt = c.honours?.counts || {};
  const myTop = (S.top20 || []).find((r) => r.player === c.player_name);

  let h = `<div class="page-head"><h2>${esc(c.team_name)}</h2>
    <span class="hint">${S.year} 赛季 · ${esc(c.era)} ${esc((c.eras || {})[c.era]?.title || "")}</span></div>`;

  if (c.banned) {
    h += `<div class="card" style="margin-bottom:12px;border-color:#6a2a2a"><h3>已被禁赛</h3>
      <p class="hint">赛事方暂停了你的参赛资格。这份档案到此为止，只能重开生涯。</p></div>`;
  }

  const ym = S.your_match;
  if (ym?.match && !c.banned) {
    const pending = ym.match.pending_map;
    const n = (ym.match.maps_done || 0) + 1;
    h += `<div class="card live-up" style="margin-bottom:12px"><div class="row" style="justify-content:space-between">
      <div><h3 style="margin:0 0 6px">该你上场</h3>
        <div class="row">${tm(ym.match.team_a, 22)} <span class="hint">vs</span> ${tm(ym.match.team_b, 22)}
          <span class="hint">${esc(ym.match.label || "")} · BO${ym.match.best_of}${ym.match.series ? ` · ${ym.match.series}` : ""}</span>
        </div>
        <p class="hint" style="margin:8px 0 0">${pending ? `下一图 ${mapName(pending)}` : "按双方实力和心态结算"}</p>
      </div>
      <button class="btn primary" id="go-live">出战</button>
    </div></div>`;
  }

  if (c.crisis) {
    h += `<div class="card" style="margin-bottom:12px;border-color:#6a2a2a"><div class="row" style="justify-content:space-between">
      <div><b>俱乐部发不出工资</b><br><span class="hint">缺口 ${money(c.deficit)}。捐款续命，否则下个月解散，队友进转会市场。</span></div>
      <button class="btn primary sm" id="go-locker">去经营页</button></div></div>`;
  }

  h += `<div class="grid4">
    <div class="card"><div class="stat"><b>#${c.vrs?.rank ?? "—"}</b><small>世界排名</small></div></div>
    <div class="card"><div class="stat"><b>${Math.round(c.vrs?.vrs ?? 0)}</b><small>VRS 积分</small></div></div>
    <div class="card"><div class="stat"><b>${money(c.money)}</b><small>俱乐部资金</small></div></div>
    <div class="card"><div class="stat gold"><b>${money(c.pocket)}</b><small>个人口袋</small></div></div>
  </div>`;

  h += `<div class="grid2" style="margin-top:12px">`;

  h += `<div class="card"><h3>${live ? "正在进行" : "下一个赛事"}</h3>`;
  const ev = live || next;
  if (!ev) h += `<p class="empty">赛季日程已走完，点「下一天」进入新赛季</p>`;
  else {
    const mine = (ev.field || []).includes(c.team_name);
    h += `<div class="row" style="justify-content:space-between">
        <div><b style="font-size:15px">${esc(ev.name)}</b><br>
          <small class="hint">${dateSpan(ev.dates)} · ${REGION[ev.region]} · ${FORMAT[ev.format] || ev.format || ""}</small></div>
        ${badge(ev.class, CLS[ev.class] || ev.class)}
      </div>
      <div class="row" style="margin-top:10px">
        ${mine ? badge("done", "你在参赛名单") : ev.status === "upcoming" ? badge("upcoming", "请到邮件确认邀请") : badge("upcoming", "暂未入围")}
        <span class="hint">${eventPathHint(ev, true)}</span>
        <button class="btn sm" id="go-ev">查看</button>
        ${ev.status === "upcoming" && !mine ? `<button class="btn sm" id="go-mail">打开邮箱</button>` : ""}
      </div>`;
  }
  h += `</div>`;

  h += `<div class="card"><h3>本季个人数据</h3>`;
  if (!line) h += `<p class="empty">还没有正式比赛数据</p>`;
  else {
    h += `<div class="grid2">
      <div class="stat"><b>${r2(line.rating)}</b><small>Rating</small></div>
      <div class="stat"><b>${line.maps}</b><small>已打地图</small></div>
      <div class="stat"><b>${r2(line.rating_top10)}</b><small>对前十</small></div>
      <div class="stat"><b>${line.k}-${line.d}-${line.a}</b><small>K-D-A</small></div>
    </div>`;
    if (myTop) h += `<p class="hint" style="margin:10px 0 0">年度榜暂列第 ${myTop.rank} 位</p>`;
  }
  h += `</div></div>`;

  h += `<div class="grid2" style="margin-top:12px">`;
  const recent = [...S.events].filter((e) => e.status === "done").slice(-6).reverse();
  h += `<div class="card"><h3>最近冠军</h3>`;
  h += recent.length
    ? recent.map((e) => `<div class="trophy-row ${e.class}"><span class="ic">🏆</span>
        <div><b>${esc(e.champion || "—")}</b><br><small>${esc(e.short)}${e.awards?.mvp ? ` · MVP ${esc(e.awards.mvp.player)}` : ""}</small></div>
        <span class="when">${e.dates[e.dates.length - 1].slice(5)}</span></div>`).join("")
    : `<p class="empty">本季还没有赛事结束</p>`;
  h += `</div>`;

  h += `<div class="card"><h3>动态</h3>`;
  const log = [...(c.log || []), ...(S.log || [])].slice(-9).reverse();
  h += log.length ? `<div style="display:grid;gap:6px">${log.map((x) => `<div class="hint">${esc(x)}</div>`).join("")}</div>` : `<p class="empty">—</p>`;
  h += `</div></div>`;

  $("view-home").innerHTML = h;
  if ($("go-ev")) $("go-ev").onclick = () => { FOCUS = ev.id; show("event"); };
  if ($("go-mail")) $("go-mail").onclick = () => show("mail");
  if ($("go-locker")) $("go-locker").onclick = () => show("locker");
  if ($("go-live")) $("go-live").onclick = () => jumpToYourMatch();
}

/* ----------------------------------------------------------------- squad */

function renderSquad() {
  const c = S.career;
  const mine = S.teams.find((t) => t.id === c.team_id);
  if (!mine) { $("view-squad").innerHTML = `<p class="empty">还没有队伍</p>`; return; }
  const you = c.you || mine.players.find((p) => p.you);

  let h = `<div class="page-head"><h2>阵容</h2><span class="hint">#${mine.rank} ${REGION[mine.region]} · 赛训 ${mine.command} · 属性点 ${c.attr_points || 0}</span></div>`;

  h += `<div class="grid2"><div class="card pad0"><h3>首发五人</h3><table><thead>
    <tr><th>选手</th><th>位置</th><th class="num">能力</th><th class="num">指挥</th><th class="num">状态</th><th class="num">年龄</th></tr></thead><tbody>`;
  for (const p of [...mine.players].sort((a, b) => b.ability - a.ability)) {
    h += `<tr class="${isMe(p.name) ? "me" : ""}"><td>${plink(p.name)}${p.you ? " ★" : ""}</td>
      <td><select class="role-sel" data-role-name="${esc(p.name)}">${Object.keys(ROLE).map((k) =>
        `<option value="${k}" ${p.role === k ? "selected" : ""}>${ROLE[k]}</option>`).join("")}</select></td>
      <td class="num">${Math.round(p.ability)}</td><td class="num">${Math.round(p.command || 0)}</td>
      <td class="num">${Math.round(p.form)}</td><td class="num">${p.age}</td></tr>`;
  }
  h += `</tbody></table>
    <p class="hint" style="padding:10px 16px 14px">必须一名指挥、一名主狙。改位置会按公式重算个人能力，赛训取新 IGL 的指挥。</p></div>`;

  h += `<div class="cards">
    <div class="card"><h3>队伍</h3>
      <div class="row" style="margin-bottom:12px">${crest(mine.name, 52)}
        <div><b style="font-size:16px">${esc(mine.name)}</b><br><small class="hint">${money(mine.money)} · 士气 ${Math.round(mine.mentality || 0)}</small></div></div>
      <div class="form"><label>换队标（PNG）<input type="file" id="sq-logo" accept="image/png,image/jpeg"></label></div>
      <p class="hint">也可以把 <code>${esc(mine.id)}.png</code> 放进 save/logos 目录。</p>
    </div>
    <div class="card"><h3>地图</h3>
      <p><small class="hint">擅长</small><br>${(mine.strong_maps || []).map((m) => badge("t1", mapName(m))).join(" ")}</p>
      <p><small class="hint">短板</small><br>${(mine.weak_maps || []).map((m) => badge("qual", mapName(m))).join(" ")}</p>
    </div>
    <div class="card"><h3>队史冠军</h3>${
      (c.team_honours || []).length
        ? (c.team_honours || []).map((t) => `<div class="trophy-row ${t.class}"><span class="ic">🏆</span><div><b>${esc(t.short)}</b></div><span class="when">${t.date}</span></div>`).join("")
        : `<p class="empty">还没有</p>`
    }</div>
  </div></div>`;

  if (you) {
    const st = you.stats || {};
    h += `<div class="card" style="margin-top:12px"><h3>你的个人能力</h3>
      <p class="hint" style="margin:-4px 0 10px">七个枪维按位置权重合成个人能力；指挥单独结算。参赛 +1 点，进决赛再 +1，年底清零。</p>
      ${axisPanel(st, { spend: true })}</div>`;
  }

  $("view-squad").innerHTML = h;
  bindInspect($("view-squad"));
  bindAxisSpend($("view-squad"));
  document.querySelectorAll("[data-role-name]").forEach((sel) => {
    sel.onchange = () => {
      const roles = {};
      document.querySelectorAll("[data-role-name]").forEach((x) => { roles[x.dataset.roleName] = x.value; });
      post("/api/roles", { roles });
    };
  });
  const up = $("sq-logo");
  if (up) {
    up.onchange = () => {
      const file = up.files?.[0];
      if (!file) return;
      if (file.size > 3 * 1024 * 1024) return toast("图片要小于 3MB", true);
      const fr = new FileReader();
      fr.onload = () => post("/api/logo", { data: fr.result, team_id: mine.id });
      fr.readAsDataURL(file);
    };
  }
}

/* ----------------------------------------------------------------- honours */

function renderHonours() {
  const c = S.career;
  const hon = c.honours || { titles: [], mvp: [], evp: [], top20: [], counts: {} };
  const you = c.you || {};
  const st = you.stats || {};

  let h = `<div class="page-head"><h2>${esc(c.player_name)} 的荣誉墙</h2>
    <span class="hint">${ROLE[c.role] || c.role} · ${esc(c.team_name)} · 属性点 ${c.attr_points || 0}</span></div>`;
  h += `<div class="card" style="margin-bottom:12px"><h3>个人能力</h3>
    <p class="hint" style="margin:-4px 0 10px">七个枪维按位置权重合成个人能力；指挥单独算。没用完的点每年清零。</p>
    ${axisPanel(st, { spend: true })}</div>`;
  h += honoursMedals(hon) + honoursLists(hon);
  $("view-honours").innerHTML = h;
  bindAxisSpend($("view-honours"));
}

/* ----------------------------------------------------------------- locker */

function renderLocker() {
  const c = S.career;
  const ops = c.ops || {};
  const shop = c.skins || {};
  const inv = shop.inventory || [];
  const eq = shop.equipped || {};
  let h = `<div class="page-head"><h2>经营与库存</h2>
    <span class="hint">俱乐部发工资、管吃住；个人口袋买皮和开箱</span></div>`;

  if (c.crisis) {
    h += `<div class="card" style="margin-bottom:12px;border-color:#6a2a2a"><h3>经营危机</h3>
      <p class="hint">发不出工资，缺口 ${money(c.deficit)}。捐满才能续命，否则下个月解散，队友进转会市场，你留下重开新队。</p>
      <div class="row"><input id="don-amt" class="locker-input" type="number" min="1" value="${c.deficit || 1000}">
        <button class="btn primary sm" id="don-go">捐给俱乐部</button>
        <button class="btn sm" id="found-go">现在解散并重开</button></div></div>`;
  }

  h += `<div class="grid2" style="margin-bottom:12px">
    <div class="card"><h3>俱乐部账本</h3>
      <div class="grid4" style="margin-bottom:10px">
        <div class="stat"><b>${money(ops.cash)}</b><small>账上现金</small></div>
        <div class="stat"><b>${money(ops.total)}</b><small>每月支出</small></div>
        <div class="stat"><b>${money(ops.salaries)}</b><small>工资</small></div>
        <div class="stat"><b>${ops.runway ?? 0} 月</b><small>还能撑</small></div>
      </div>
      <p class="hint">吃住 ${money(ops.living)} · 你的月薪 ${money(ops.your_salary)} · 奖金 12% 进个人，Major 出场费 $200,000 进俱乐部</p>
      <table><thead><tr><th>队员</th><th class="num">月薪</th></tr></thead><tbody>
        ${(ops.wages || []).map((w) => `<tr class="${w.name === c.player_name ? "me" : ""}"><td>${esc(w.name)}</td><td class="num">${money(w.pay)}</td></tr>`).join("")}
      </tbody></table>
      ${(ops.log || []).length ? `<div style="margin-top:10px">${ops.log.map((x) => `<div class="hint">${esc(x)}</div>`).join("")}</div>` : ""}
      ${!c.crisis ? `<div class="row" style="margin-top:12px">
        <input id="don-amt" class="locker-input" type="number" min="1" value="5000">
        <button class="btn sm" id="don-go">捐给俱乐部</button>
      </div>` : ""}
    </div>
    <div class="card"><h3>个人口袋 ${money(c.pocket)}</h3>
      <p class="hint">来源：每月工资 + 赛事奖金 12%。转会只能用俱乐部的钱。</p>
      <p class="hint" style="margin-top:12px">游戏内换肤 · 暂未开放</p>
    </div>
  </div>`;

  if (shop.pending) {
    h += `<div class="card" style="margin-bottom:12px"><h3>刚开出 ${esc(shop.pending.name)}</h3>
      <p class="hint">${esc(shop.pending.weapon)} · ${RARITY[shop.pending.rarity] || shop.pending.rarity} · 磨损 ${Number(shop.pending.wear || 0).toFixed(3)}</p>
      <div class="row"><button class="btn primary sm" id="drop-keep">进库存</button>
        <button class="btn sm" id="drop-cash">换成 ${money(shop.pending.sell || 0)}</button></div></div>`;
  }

  h += `<div class="grid2" style="margin-bottom:12px">
    <div class="card"><h3>当前库存</h3>`;
  if (!inv.length) h += `<p class="empty">还没有皮肤</p>`;
  else {
    h += `<table><thead><tr><th>饰品</th><th>稀有度</th><th class="num">磨损</th><th></th></tr></thead><tbody>`;
    for (const it of inv) {
      const on = eq[it.slot] === it.id;
      h += `<tr><td>${esc(it.name)}${on ? " · 已装备" : ""}</td>
        <td>${badge(it.rarity, RARITY[it.rarity] || it.rarity)}</td>
        <td class="num">${Number(it.wear || 0).toFixed(3)}</td>
        <td><button class="btn sm" data-eq="${esc(it.id)}">${on ? "穿着" : "装备"}</button>
          <button class="btn sm" data-sell="${esc(it.id)}">卖 ${money(it.sell)}</button></td></tr>`;
    }
    h += `</tbody></table>`;
  }
  h += `</div><div class="card"><h3>开箱</h3>
    <p class="hint">箱子+钥匙一次付清。开出后选留下或马上换成钱。</p>`;
  for (const box of shop.cases || []) {
    const cost = (box.price || 0) + (box.key || 0);
    h += `<div class="row" style="justify-content:space-between;margin:8px 0">
      <div><b>${esc(box.name)}</b><br><small class="hint">箱子 ${money(box.price)} + 钥匙 ${money(box.key)}</small></div>
      <button class="btn sm" data-case="${esc(box.id)}">开 ${money(cost)}</button></div>`;
  }
  h += `</div></div>`;

  h += `<div class="card"><h3>皮肤市场</h3>
    <p class="hint">用个人口袋直接买进库存。</p>
    <table><thead><tr><th>饰品</th><th>枪</th><th>稀有度</th><th class="num">售价</th><th></th></tr></thead><tbody>`;
  for (const s of shop.market || []) {
    h += `<tr><td>${esc(s.name)}</td><td>${esc(s.weapon)}</td>
      <td>${badge(s.rarity, RARITY[s.rarity] || s.rarity)}</td>
      <td class="num">${money(s.buy)}</td>
      <td><button class="btn sm" data-buy="${esc(s.id)}" ${c.pocket < s.buy ? "disabled" : ""}>买入</button></td></tr>`;
  }
  h += `</tbody></table></div>`;

  $("view-locker").innerHTML = h;
  if ($("go-locker")) $("go-locker").onclick = () => show("locker");
  if ($("don-go")) $("don-go").onclick = () => post("/api/ops/donate", { amount: Number($("don-amt")?.value || 0) });
  if ($("found-go")) $("found-go").onclick = () => { if (confirm("队友会进转会市场，你留下重开新队？")) post("/api/ops/found", {}); };
  if ($("drop-keep")) $("drop-keep").onclick = () => post("/api/skins/keep", {});
  if ($("drop-cash")) $("drop-cash").onclick = () => post("/api/skins/cash", {});
  document.querySelectorAll("[data-case]").forEach((b) => (b.onclick = () => post("/api/skins/case", { id: b.dataset.case })));
  document.querySelectorAll("[data-buy]").forEach((b) => (b.onclick = () => post("/api/skins/buy", { id: b.dataset.buy })));
  document.querySelectorAll("[data-eq]").forEach((b) => (b.onclick = () => post("/api/skins/equip", { id: b.dataset.eq })));
  document.querySelectorAll("[data-sell]").forEach((b) => (b.onclick = () => post("/api/skins/sell", { id: b.dataset.sell })));
}

/* ----------------------------------------------------------------- mail */

function renderMail() {
  const c = S.career;
  const rows = [...(c.inbox || [])].reverse();
  let h = `<div class="page-head"><h2>邮件</h2>
    <span class="hint">${c.unread || 0} 封未读 · 邀请、出线、奖金和赞助都在这里</span>
    <button class="btn sm" id="mail-all">全部已读</button></div>`;
  if (!rows.length) h += `<p class="empty">信箱是空的</p>`;
  for (const m of rows) {
    const unread = !m.read;
    h += `<div class="mail-item ${unread ? "unread" : ""}">
      <div class="mh">${badge(m.kind === "invite" ? "t1" : m.kind === "prize" ? "premier" : m.kind === "qualify" ? "major" : m.kind === "whisper" ? "upcoming" : m.kind === "discipline" ? "t2" : "done", MAIL_KIND[m.kind] || m.kind)}
        <b>${esc(m.title)}</b>
        <small>${esc(m.from || "")}</small>
        <span class="when">${esc(m.date || "")}</span></div>
      <pre>${esc(m.body || "")}</pre>
      <div class="acts">`;
    if (m.kind === "invite" && m.status === "open") {
      h += `<button class="btn primary sm" data-acc="${esc(m.id)}">接受邀请</button>
        <button class="btn sm" data-dec="${esc(m.id)}">婉拒</button>`;
    } else if (m.kind === "invite") {
      h += badge(m.status === "accepted" ? "done" : "upcoming", MAIL_STATUS[m.status] || m.status);
    }
    if (m.kind === "whisper" && m.status === "open" && !c.banned) {
      h += `<button class="btn sm" data-dec="${esc(m.id)}">回绝</button>
        <button class="btn primary sm" data-acc="${esc(m.id)}">按他说的办</button>`;
    } else if (m.kind === "whisper") {
      h += badge(m.status === "accepted" ? "t2" : "done", m.status === "accepted" ? "已回复" : "已回绝");
    }
    if ((m.kind === "prize" || m.kind === "sponsor") && m.status !== "claimed") {
      h += `<button class="btn primary sm" data-claim="${esc(m.id)}">领取 ${money(m.amount)}</button>`;
    } else if (m.kind === "prize" || m.kind === "sponsor") {
      h += badge("done", "已领取");
    }
    if (unread) h += `<button class="btn ghost sm" data-read="${esc(m.id)}">标为已读</button>`;
    h += `</div></div>`;
  }
  $("view-mail").innerHTML = h;
  if ($("mail-all")) $("mail-all").onclick = () => post("/api/mail/read_all", {});
  document.querySelectorAll("[data-acc]").forEach((b) => (b.onclick = () => post("/api/mail/accept", { id: b.dataset.acc })));
  document.querySelectorAll("[data-dec]").forEach((b) => (b.onclick = () => post("/api/mail/decline", { id: b.dataset.dec })));
  document.querySelectorAll("[data-claim]").forEach((b) => (b.onclick = () => post("/api/mail/claim", { id: b.dataset.claim })));
  document.querySelectorAll("[data-read]").forEach((b) => (b.onclick = () => post("/api/mail/read", { id: b.dataset.read })));
}

/* ----------------------------------------------------------------- market */

function renderMarket() {
  const c = S.career;
  const rows = c.market || [];
  let h = `<div class="page-head"><h2>转会市场</h2><span class="hint">签人会自动送走队里能力最低的一名（你除外）</span></div>`;
  h += `<div class="card"><div class="row" style="margin-bottom:10px">
      <span class="stat"><b>${money(c.money)}</b><small>可用资金</small></span>
      <span class="stat"><b>#${c.vrs?.rank ?? "—"}</b><small>队伍排名</small></span>
    </div>`;
  if (!rows.length) h += `<p class="empty">市场上没人</p>`;
  else {
    h += `<table><thead><tr><th>选手</th><th>位置</th><th class="num">能力</th><th class="num">指挥</th><th class="num">年龄</th>
      <th>类型</th><th class="num">转会费</th><th class="num">成功率</th><th></th></tr></thead><tbody>`;
    for (const p of rows) {
      const ok = c.money >= p.fee && p.chance >= 0.18;
      h += `<tr><td>${plink(p.name)}</td><td>${roleBadge(p.role)}</td><td class="num">${Math.round(p.ability)}</td>
        <td class="num">${Math.round(p.command || 0)}</td>
        <td class="num">${p.age}</td><td><small class="hint">${esc(p.note || "")}</small></td>
        <td class="num">${money(p.fee)}</td><td class="num">${Math.round(p.chance * 100)}%</td>
        <td class="num"><button class="btn sm ${ok ? "primary" : ""}" data-buy="${esc(p.name)}" ${ok ? "" : "disabled"}>签下</button></td></tr>`;
    }
    h += `</tbody></table>`;
  }
  h += `</div>`;
  $("view-market").innerHTML = h;
  document.querySelectorAll("[data-buy]").forEach((b) => (b.onclick = () => post("/api/market/buy", { player: b.dataset.buy })));
  bindInspect($("view-market"));
}

function awardTitle(kind, evClass) {
  const mvp = { major: "Major MVP", premier: "Premier MVP", t1: "T1 MVP", t2: "T2 MVP", cct: "CCT MVP", qual: "RMR MVP" };
  const evp = { major: "Major EVP", premier: "Premier EVP", t1: "T1 EVP", t2: "T2 EVP", cct: "CCT EVP", qual: "RMR EVP" };
  return (kind === "mvp" ? mvp : evp)[evClass] || (kind === "mvp" ? "MVP" : "EVP");
}

/* ----------------------------------------------------------------- schedule */

function renderSchedule() {
  const byMonth = {};
  for (const ev of S.events) {
    const key = ev.dates[0].slice(0, 7);
    (byMonth[key] ||= []).push(ev);
  }
  let h = `<div class="page-head"><h2>${S.year} 赛季赛程</h2>
    <span class="hint">${S.events.length} 站 · ${S.events.filter((e) => e.status === "done").length} 站已结束</span></div>`;

  for (const key of Object.keys(byMonth).sort()) {
    const m = Number(key.slice(5, 7));
    h += `<div class="month"><h4>${MONTHS[m - 1]}</h4>`;
    for (const ev of byMonth[key]) {
      const mine = myTeamName() && (ev.field || []).includes(myTeamName());
      h += `<button class="ev-row ${ev.status}" data-ev="${ev.id}">
        <span class="when">${dateSpan(ev.dates)}</span>
        <span class="who"><b>${esc(ev.short)}${mine ? " ·" : ""}</b>
          <small>${REGION[ev.region]} · ${FORMAT[ev.format] || ""}</small></span>
        <span class="right">
          ${mine ? badge("done", "参赛") : ""}
          ${badge(ev.class, CLS[ev.class] || ev.class)}
          ${ev.champion ? `<span class="champ">🏆 ${crest(ev.champion, 18)} ${esc(ev.champion)}</span>` : badge(ev.status, STATUS[ev.status])}
        </span></button>`;
    }
    h += `</div>`;
  }
  $("view-schedule").innerHTML = h;
  document.querySelectorAll("[data-ev]").forEach((b) => (b.onclick = () => { FOCUS = b.dataset.ev; show("event"); }));
}

/* ----------------------------------------------------------------- event */

function stageGroups(ev) {
  const order = [];
  for (const m of ev.matches) if (!order.includes(m.stage)) order.push(m.stage);
  return order.map((stage) => ({
    stage,
    label: ev.matches.find((m) => m.stage === stage)?.label || stage,
    rows: ev.matches.filter((m) => m.stage === stage),
  }));
}

function matchCard(m) {
  const wa = m.played && m.winner === m.team_a;
  const wb = m.played && m.winner === m.team_b;
  const yours = m.yours && !m.played && m.team_b !== "BYE";
  const maps = (m.maps || []).map((x) => `${mapName(x.map)} ${x.score}`).join(" · ");
  const mid = m.played || yours;
  const sc = m.played ? m.series : yours && m.series ? m.series : `BO${m.best_of}`;
  const extra = yours && m.pending_map ? ` · 下一张 ${mapName(m.pending_map)}` : "";
  return `<button class="mt ${m.played ? "done" : yours ? "yours" : "pending"}" ${mid ? `data-mid="${esc(m.id)}"` : "disabled"}>
    ${tm(m.team_a, 22, wa ? "w" : m.played ? "l" : "")}
    <span class="sc">${esc(sc)}</span>
    <span class="tm side-b ${wb ? "w" : m.played ? "l" : ""}">${m.team_b === "BYE" ? "" : crest(m.team_b, 22)}<span>${m.team_b === "BYE" ? "轮空" : esc(m.team_b)}</span></span>
    ${m.played || m.label || yours ? `<span class="meta">${m.label ? esc(m.label) : ""}${maps ? ` · ${maps}` : ""}${m.played ? "" : ` · ${m.date.slice(5)}`}${extra}</span>` : ""}
  </button>`;
}

function renderEvent() {
  const ev = S.events.find((e) => e.id === FOCUS) || S.events[0];
  if (!ev) { $("view-event").innerHTML = `<p class="empty">没有赛事</p>`; return; }
  const mine = myTeamName();
  const registered = (S.career?.registered || []).includes(ev.id);

  let h = `<div class="page-head"><h2>${esc(ev.name)}</h2>
    ${badge(ev.class, CLS[ev.class] || ev.class)} ${badge(ev.status, STATUS[ev.status])}
    <span class="hint">${dateSpan(ev.dates)} · ${REGION[ev.region]} · ${FORMAT[ev.format] || "赛制待定"} · 奖金池 ${money(ev.prize)} · VRS ×${ev.vrs_weight}</span></div>`;

  if (ev.status === "upcoming" && S.career?.exists) {
    const pathHint = eventPathHint(ev);
    h += `<div class="card" style="margin-bottom:12px"><div class="row">
      ${registered ? badge("done", "已接受邀请") : badge("upcoming", "请到邮件确认邀请")}
      <button class="btn sm" id="ev-mail">打开邮箱</button>
      <span class="hint">${pathHint}</span></div></div>`;
  }

  if (ev.awards?.mvp) {
    const mvp = ev.awards.mvp;
    const mvpName = mvp.title || awardTitle("mvp", ev.class);
    h += `<div class="awards" style="margin-bottom:14px">
      <div class="award mvp"><span class="kind">${esc(mvpName)}</span><b>${esc(mvp.player)}</b>
        <small>${esc(mvp.team)} · Rating ${r2(mvp.rating)}${mvp.from_finalist ? " · 决赛败方" : ""}</small></div>
      ${(ev.awards.evp || []).map((r) => `<div class="award evp"><span class="kind">${esc(r.title || awardTitle("evp", ev.class))}</span><b>${esc(r.player)}</b>
        <small>${esc(r.team)} · Rating ${r2(r.rating)} · ${PLACE[r.place] || ""}</small></div>`).join("")}
    </div>`;
  }

  if (ev.champion) {
    h += `<div class="card" style="margin-bottom:12px"><div class="row" style="gap:14px">
      <span class="ic" style="font-size:26px">🏆</span>${crest(ev.champion, 44)}
      <div><b style="font-size:17px">${esc(ev.champion)}</b><br><small class="hint">冠军 · 奖金 ${money(Math.round(ev.prize * 0.34))}</small></div>
    </div></div>`;
  }

  if (ev.type === "qual" && (ev.qualified_out || []).length) {
    const dest = destEvent(ev)?.short || "正赛";
    h += `<div class="card" style="margin-bottom:12px"><h3>出线 → ${esc(dest)}</h3>
      <div class="chips">${ev.qualified_out.map((n) => `<span class="badge major">${esc(n)}</span>`).join("")}</div></div>`;
  }

  if (ev.swiss?.length) {
    h += `<div class="card pad0" style="margin-bottom:12px"><h3>瑞士轮战绩</h3><table><thead>
      <tr><th>#</th><th>队伍</th><th class="num">战绩</th><th class="num">布赫霍尔兹</th><th>状态</th></tr></thead><tbody>`;
    ev.swiss.forEach((r, i) => {
      const state = r.w >= 3 ? `<span class="rec adv">晋级</span>` : r.l >= 3 ? `<span class="rec out">淘汰</span>` : `<span class="rec">存活</span>`;
      h += `<tr class="${r.team === mine ? "me" : ""}"><td>${i + 1}</td><td>${tm(r.team, 18)}</td>
        <td class="num">${r.w}-${r.l}</td><td class="num">${r.buchholz > 0 ? "+" : ""}${r.buchholz}</td><td>${state}</td></tr>`;
    });
    h += `</tbody></table></div>`;
  }

  if (ev.groups) {
    h += `<div class="grid4" style="margin-bottom:12px">`;
    for (const [g, rows] of Object.entries(ev.groups)) {
      h += `<div class="card pad0"><h3>${g} 组</h3><table><tbody>${rows
        .map((r) => `<tr class="${r.team === mine ? "me" : ""}"><td>${tm(r.team, 18)}</td>
          <td class="num">${r.w}-${r.l}</td>
          <td class="num">${r.place === "1st" ? `<span class="rec adv">1st</span>` : r.place === "2nd" ? `<span class="rec adv">2nd</span>` : r.place === "out" ? `<span class="rec out">out</span>` : "—"}</td></tr>`)
        .join("")}</tbody></table></div>`;
    }
    h += `</div>`;
  }

  if (!ev.matches.length) {
    h += `<p class="empty">${ev.status === "upcoming" ? "赛事还没开始" : "没有对局"}</p>`;
  } else {
    for (const grp of stageGroups(ev)) {
      h += `<div class="stage-head">${esc(grp.label)}</div>`;
      h += grp.rows.map(matchCard).join("");
    }
  }

  if (!ev.matches.length && ev.field?.length) {
    h += `<div class="card" style="margin-top:12px"><h3>参赛名单</h3><div class="chips">${ev.field.map((n) => `<span class="badge">${esc(n)}</span>`).join("")}</div></div>`;
  }

  $("view-event").innerHTML = h;
  if ($("ev-mail")) $("ev-mail").onclick = () => show("mail");
  document.querySelectorAll("[data-mid]").forEach((b) => (b.onclick = () => openMatch(b.dataset.mid)));
}

/* ----------------------------------------------------------------- match */

async function openMatch(id) {
  MATCH = id;
  DETAIL = null;
  show("match");
  try {
    DETAIL = await get(`/api/match?id=${encodeURIComponent(id)}`);
  } catch {
    DETAIL = null;
  }
  renderMatch();
}

function renderMatch() {
  const el = $("view-match");
  if (!DETAIL?.match) {
    el.innerHTML = `<p class="empty">加载中…</p>`;
    return;
  }
  const m = DETAIL.match;
  const ev = DETAIL.event;
  const yours = DETAIL.yours || m.human;
  const wa = m.played && m.winner === m.team_a;
  const wb = m.played && m.winner === m.team_b;
  const live = !m.played && yours;

  let h = `<button class="btn ghost sm" id="m-back">← ${esc(ev.short || ev.name)}</button>
    <div class="page-head" style="margin-top:12px">
      <h2>${tm(m.team_a, 26, wa ? "w" : wb ? "l" : "")} <span style="margin:0 10px">${esc(m.series || "vs")}</span> ${tm(m.team_b, 26, wb ? "w" : wa ? "l" : "")}</h2>
      <span class="hint">${esc(m.label || m.stage)} · BO${m.best_of} · ${m.date}</span></div>`;

  if (!m.played && !yours) {
    h += `<p class="empty">这场还没打</p>`;
    el.innerHTML = h;
    $("m-back").onclick = () => show("event");
    return;
  }

  if (m.veto?.steps?.length) {
    h += `<div class="stage-head">BAN / PICK</div><div class="veto">`;
    for (const s of m.veto.steps) {
      h += `<span class="step ${s.action}"><span class="act">${s.action === "ban" ? "BAN" : s.action === "pick" ? "PICK" : "决胜图"}</span>
        <b>${mapName(s.map)}</b>${s.team ? `<span class="hint">${esc(s.team)}</span>` : ""}</span>`;
    }
    h += `</div>`;
    const left = (m.veto.order || []).slice((m.maps || []).length);
    if (left.length) h += `<p class="hint">未进行：${left.map(mapName).join(" · ")}</p>`;
  }

  (m.maps || []).forEach((mp, i) => {
    const src = mp.source === "cs2" ? `<span class="src">你打的</span>` : mp.source === "sim" ? `<span class="src sim">数值</span>` : "";
    h += `<div class="map-block"><div class="mh"><h4>第 ${i + 1} 图 · ${mapName(mp.map)}${src}</h4>
      <small>${mp.score} · ${esc(mp.winner)} 胜</small></div><div class="sides">`;
    for (const name of [m.team_a, m.team_b]) {
      const lines = (mp.players || {})[name] || [];
      h += `<div class="card pad0"><h3>${esc(name)}${mp.winner === name ? " ✓" : ""}</h3>${boxTable(lines)}</div>`;
    }
    h += `</div></div>`;
  });

  if (live && S.career?.banned) {
    h += `<div class="card" style="margin-top:16px"><p class="hint">你已被禁赛，无法再上场。这份档案只能重开。</p></div>`;
  } else if (live) {
    if (!SERIES_CS2) {
      get("/api/cs2/status").then((x) => { SERIES_CS2 = x; if (VIEW === "match") renderMatch(); }).catch(() => { SERIES_CS2 = { ready: false }; });
    }
    h += renderLivePanel(m);
  }

  if (m.played && m.ratings?.length) {
    h += `<div class="stage-head">全场数据</div><div class="card pad0">${ratingTable(
      m.ratings.map((r) => ({ ...r, maps: null }))
    )}</div>`;
  }

  el.innerHTML = h;
  $("m-back").onclick = () => show("event");
  bindLivePanel(m);
  if (live && m.cs2_session) startSeriesPoll(m.id);
}

function renderLivePanel(m) {
  const n = (m.maps || []).length + 1;
  const pending = m.pending_map;
  const session = m.cs2_session;
  const res = SERIES_RESULT;
  const cfg = SERIES_CS2 || {};
  let h = `<div class="card live-up play-panel" style="margin-top:16px">`;
  h += `<h3>${pending ? `第 ${n} 图 · ${mapName(pending)}` : "系列赛"}</h3>`;
  if (!cfg.ready && cfg.ready !== undefined) {
    h += `<p class="hint">自己打需要先装人机增强。到「训练赛」页填好 Steam / 游戏 / 人机增强目录，或直接按实力出战。</p>`;
  }
  h += `<div class="row">
    <label>你的阵营 <select id="s-side">
      <option value="ct" ${SERIES_SIDE === "ct" ? "selected" : ""}>CT</option>
      <option value="t" ${SERIES_SIDE === "t" ? "selected" : ""}>T</option>
    </select></label>
    <span class="hint">${esc(botLine(cfg))} · 到「训练赛」页可改</span>
  </div>`;
  const goLabel = session ? "重开这张图" : pending ? `进入第 ${n} 图` : "自己打";
  h += `<div class="row">
    <button class="btn primary" id="s-go">${goLabel}</button>
    <button class="btn" id="s-skip">${(m.maps || []).length ? "跳过剩余，按数值结算" : "跳过，按角色数值结算"}</button>
    ${session ? `<button class="btn ghost" id="s-commit">录入战绩</button>` : ""}
  </div>`;
  h += `<p class="hint">${session
    ? "闪退或中途退出后可以重开同一张图覆盖。不想打了就跳过剩余。"
    : "自己打要用 CS2 和人机增强；没装也可以按角色数值结算。"}</p>`;

  if (res && res.status && res.status !== "none") {
    const final = res.status === "finished";
    h += `<div class="scoreline"><span class="nm">${esc(res.ct_name || "CT")}</span>
      <b>${res.ct_score ?? 0} : ${res.t_score ?? 0}</b>
      <span class="nm">${esc(res.t_name || "T")}</span>
      ${badge(final ? "done" : "live", final ? "终场，正在录入" : "进行中")}</div>`;
  }
  h += `</div>`;
  return h;
}

function bindLivePanel(m) {
  if ($("s-side")) $("s-side").onchange = (e) => { SERIES_SIDE = e.target.value; };
  if ($("s-go")) {
    $("s-go").onclick = async () => {
      SERIES_TRIED = "";
      SERIES_RESULT = null;
      await post("/api/series/launch", { match_id: m.id, side: SERIES_SIDE });
      startSeriesPoll(m.id);
    };
  }
  if ($("s-skip")) {
    $("s-skip").onclick = async () => {
      if (!confirm("剩余地图按角色数值结算？已经自己打完的图会保留。")) return;
      stopSeriesPoll();
      await post("/api/series/skip", { match_id: m.id });
    };
  }
  if ($("s-commit")) {
    $("s-commit").onclick = () => post("/api/series/commit", { match_id: m.id });
  }
}

function stopSeriesPoll() {
  if (SERIES_TIMER) {
    clearInterval(SERIES_TIMER);
    SERIES_TIMER = null;
  }
}

function startSeriesPoll(matchId) {
  stopSeriesPoll();
  const tick = async () => {
    if (VIEW !== "match" || MATCH !== matchId) return;
    try {
      const res = await get("/api/play/result");
      const prev = JSON.stringify(SERIES_RESULT);
      SERIES_RESULT = res;
      if (res.status === "finished" && res.ended_at && res.ended_at !== SERIES_TRIED) {
        SERIES_TRIED = res.ended_at;
        const out = await post("/api/series/commit", { match_id: matchId });
        if (out.ok !== false) {
          SERIES_RESULT = { status: "none" };
          return;
        }
      }
      if (JSON.stringify(SERIES_RESULT) !== prev && VIEW === "match") renderMatch();
    } catch { /* game not writing yet */ }
  };
  SERIES_TIMER = setInterval(tick, 4000);
  tick();
}

/* ----------------------------------------------------------------- ranking */

function renderRanking() {
  let h = `<div class="page-head"><h2>世界排名</h2><span class="hint">Valve 积分尺度，180 天滚动衰减</span></div>`;
  h += `<div class="card pad0"><table><thead><tr><th>#</th><th>队伍</th><th>赛区</th><th class="num">VRS</th><th>阵容</th></tr></thead><tbody>`;
  for (const r of S.vrs) {
    const t = TEAMS[r.name] || {};
    const stars = (t.players || []).slice().sort((a, b) => b.ability - a.ability).slice(0, 3).map((p) => p.name).join(" · ");
    h += `<tr class="${r.name === myTeamName() ? "me" : ""}"><td>${r.rank}</td><td>${tlink(r.name, 20)}</td>
      <td><small class="hint">${REGION[r.region] || r.region}</small></td>
      <td class="num">${Math.round(r.vrs)}</td><td><small class="hint">${esc(stars)}</small></td></tr>`;
  }
  $("view-ranking").innerHTML = h + `</tbody></table></div>`;
  bindInspect($("view-ranking"));
}

/* ----------------------------------------------------------------- players */

let PLAYER_TAB = "top20";

function renderPlayers() {
  const years = Object.keys(S.top20_history || {}).sort().reverse();
  let h = `<div class="page-head"><h2>选手榜</h2>
    <span class="chips">
      <button data-tab="top20" class="${PLAYER_TAB === "top20" ? "on" : ""}">年度 Top 20</button>
      <button data-tab="rating" class="${PLAYER_TAB === "rating" ? "on" : ""}">本季 Rating</button>
      ${years.map((y) => `<button data-tab="y${y}" class="${PLAYER_TAB === "y" + y ? "on" : ""}">${y}</button>`).join("")}
    </span></div>`;

  if (PLAYER_TAB === "rating") {
    h += `<div class="card pad0">${ratingTable(S.ratings || [], { inspect: true })}</div>`;
  } else if (PLAYER_TAB.startsWith("y")) {
    h += top20Table((S.top20_history || {})[PLAYER_TAB.slice(1)] || []);
  } else {
    h += `<p class="hint" style="margin:-6px 0 12px">按 rating 打底，冠军、MVP/EVP 和对强队的表现加权。至少 20 张图才有资格。</p>`;
    h += top20Table(S.top20 || []);
  }
  $("view-players").innerHTML = h;
  document.querySelectorAll("[data-tab]").forEach((b) => (b.onclick = () => { PLAYER_TAB = b.dataset.tab; renderPlayers(); }));
  bindInspect($("view-players"));
}

function top20Table(rows) {
  if (!rows.length) return `<p class="empty">数据还不够，先打完几站赛事</p>`;
  let h = `<div class="card pad0"><table><thead><tr><th>#</th><th>选手</th><th>队伍</th>
    <th class="num">Rating</th><th class="num">对前十</th><th class="num">图</th>
    <th class="num">冠军</th><th class="num">MVP</th><th class="num">EVP</th></tr></thead><tbody>`;
  for (const r of rows) {
    h += `<tr class="${isMe(r.player) ? "me" : ""}"><td>${r.rank}</td><td><b>${plink(r.player)}</b></td><td>${tlink(r.team, 18)}</td>
      <td class="num">${r2(r.rating)}</td><td class="num">${r2(r.rating_top10)}</td><td class="num">${r.maps}</td>
      <td class="num">${r.titles || ""}</td><td class="num">${r.mvp || ""}</td><td class="num">${r.evp || ""}</td></tr>`;
  }
  return h + `</tbody></table></div>`;
}

/* ----------------------------------------------------------------- play cs2 */

let PLAY = { opp: "", map: "de_dust2", side: "ct", result: null, cs2: null, expectTrain: false, trainedAt: "" };

const DIFF_LABEL = { Low: "简单", Medium: "中等", High: "极难" };
const AIM_LABEL = { head: "爆头优先", mixed: "混合", body: "身体优先" };
const NADE_LABEL = { off: "关闭", less: "偏少", normal: "正常", more: "偏多", max: "最多" };
const ID_LABEL = { player: "真人（无 BOT 字样）", bot: "显示 BOT" };

function botLine(cfg) {
  if (!cfg) return "";
  return `难度 ${DIFF_LABEL[cfg.difficulty] || cfg.difficulty || "—"}`
    + ` · 瞄准 ${AIM_LABEL[cfg.bot_aim] || cfg.bot_aim || "—"}`
    + ` · 道具 ${NADE_LABEL[cfg.bot_nades] || cfg.bot_nades || "—"}`;
}

function pickRow(id, label, options, current, labels) {
  const opts = options.map((v) => `<option value="${esc(v)}" ${current === v ? "selected" : ""}>${esc(labels[v] || v)}</option>`).join("");
  return `<label style="flex:1">${label}<select id="${id}">${opts}</select></label>`;
}

function botSettingsCard(cfg) {
  const diffs = cfg.difficulties?.length ? cfg.difficulties : ["Low", "Medium", "High"];
  const aims = cfg.aim_modes || ["head", "mixed", "body"];
  const nades = cfg.nade_modes || ["off", "less", "normal", "more", "max"];
  const ids = cfg.identity_modes || ["player", "bot"];
  const live = cfg.installed_difficulty;
  const liveNote = live
    ? live === cfg.difficulty
      ? `游戏里现在装的是 ${DIFF_LABEL[live] || live}`
      : `游戏里现在还是 ${DIFF_LABEL[live] || live}，下一局开局时换成 ${DIFF_LABEL[cfg.difficulty] || cfg.difficulty}`
    : "";
  return `<div class="card" style="margin-bottom:12px"><h3>机器人设置</h3>
    <div class="form" style="max-width:none"><div class="row">
      ${pickRow("b-diff", "难度", diffs, cfg.difficulty, DIFF_LABEL)}
      ${pickRow("b-aim", "瞄准预设", aims, cfg.bot_aim, AIM_LABEL)}
      ${pickRow("b-nades", "道具预设", nades, cfg.bot_nades, NADE_LABEL)}
      ${pickRow("b-id", "队友对手身份", ids, cfg.bot_identity, ID_LABEL)}
    </div>
    <p class="hint">简单 / 中等 / 极难用人机加强的三份 botprofile。改难度后若 CS2 还开着，要退出重开才会换档。瞄准和道具每局重设。${esc(liveNote)}</p>
    </div></div>`;
}

function bindBotSettings(after) {
  const send = async () => {
    await post("/api/cs2/settings", {
      difficulty: $("b-diff").value,
      bot_aim: $("b-aim").value,
      bot_nades: $("b-nades").value,
      bot_identity: $("b-id").value,
    });
    if (after) after();
  };
  for (const id of ["b-diff", "b-aim", "b-nades", "b-id"]) {
    if ($(id)) $(id).onchange = send;
  }
}

function lineup(name, highlight) {
  const t = TEAMS[name];
  if (!t) return "";
  return `<div class="card pad0"><h3>${esc(name)}</h3><table><tbody>${t.players
    .map((p) => `<tr class="${highlight && isMe(p.name) ? "me" : ""}"><td>${esc(p.name)}${isMe(p.name) ? " ★" : ""}</td>
      <td>${roleBadge(p.role)}</td><td class="num">${Math.round(p.ability)}</td></tr>`)
    .join("")}</tbody></table></div>`;
}

async function renderPlay() {
  const c = S.career;
  if (!c.exists) { $("view-play").innerHTML = `<p class="empty">先创建生涯</p>`; return; }
  if (c.banned) {
    $("view-play").innerHTML = `<div class="page-head"><h2>训练赛</h2></div>
      <div class="card"><p class="hint">你已被禁赛，这份档案只能重开。</p></div>`;
    return;
  }
  if (!PLAY.cs2) {
    try { PLAY.cs2 = await get("/api/cs2/status"); } catch { PLAY.cs2 = { ready: false }; }
  }
  const opts = [...S.teams].filter((t) => t.id !== c.team_id).sort((a, b) => (a.rank || 99) - (b.rank || 99));
  // A leftover pick from an earlier career could be your own team by now.
  if (!opts.some((t) => t.id === PLAY.opp)) PLAY.opp = opts[0]?.id || "";
  const opp = S.teams.find((t) => t.id === PLAY.opp);
  const cfg = PLAY.cs2 || {};

  const you = c.you;
  const trained = c.last_scrim === S.date;
  let h = `<div class="page-head"><h2>训练赛</h2><span class="hint">进 CS2 打一场人机热身。正式赛事请从赛程点进你的场次</span></div>`;

  h += `<div class="card" style="margin-bottom:12px"><h3>你</h3>`;
  if (you) {
    h += `<div class="grid2">
        <div class="stat"><b>${Math.round(you.ability)}</b><small>能力</small></div>
        <div class="stat"><b>${Math.round(you.form)}</b><small>状态</small></div>
        <div class="stat"><b>${you.age}</b><small>年龄</small></div>
        <div class="stat"><b>${trained ? "今天已加成" : "打完加心态"}</b><small>训练</small></div>
      </div>
      <div class="bar" style="margin-top:12px"><i style="width:${Math.min(100, you.ability)}%"></i></div>
      <p class="hint" style="margin:8px 0 0">每天第一场只加队伍心态，且边际递减：心态越低加得越多，接近 94 几乎不再动。不涨个人能力和属性点。</p>`;
  } else h += `<p class="empty">—</p>`;
  h += `</div>`;

  const setUp = cfg.ready && cfg.mod_installed;
  h += `<div class="card" style="margin-bottom:12px"><h3>${setUp ? "游戏路径" : "首次设置（进 CS2 必做）"}</h3><div class="form">
    <label>steam.exe ${cfg.steam_ok ? "✓" : "✗"}<input id="p-steam" value="${esc(cfg.steam_exe || "")}"></label>
    <label>csgo 目录 ${cfg.csgo_ok ? "✓" : "✗"}<input id="p-csgo" value="${esc(cfg.csgo_path || "")}"></label>
    <label>人机增强目录 ${cfg.mod_ok ? "✓" : "✗"}<input id="p-mod" value="${esc(cfg.mod_source_path || "")}" placeholder="例如 CS2B 文件夹"></label>
    <div class="row"><button class="btn" id="p-save">保存路径</button>
      <button class="btn primary" id="p-install" ${cfg.ready ? "" : "disabled"}>把人机增强装进游戏</button>
    </div>
    <p class="hint">${
      cfg.ready
        ? "点「把人机增强装进游戏」，文件会复制进 game\\csgo。装完必须完全退出 CS2 再开。详细步骤见「添加人机增强.txt」。"
        : "自己进 CS2 打必须先装人机增强。填好 steam.exe、game\\csgo、人机增强目录后保存。只玩生涯、按实力出战则不用填。"
    }</p>
  </div></div>`;

  h += botSettingsCard(cfg);

  h += `<div class="card" style="margin-bottom:12px"><div class="form" style="max-width:none">
    <div class="row">
      <label style="flex:1">对手<select id="p-opp">${opts.map((t) => `<option value="${t.id}" ${PLAY.opp === t.id ? "selected" : ""}>#${t.rank} ${t.name}</option>`).join("")}</select></label>
      <label style="flex:1">地图<select id="p-map">${Object.entries(CS2_MAPS).map(([k, v]) => `<option value="${k}" ${PLAY.map === k ? "selected" : ""}>${v}</option>`).join("")}</select></label>
      <label style="flex:1">你的阵营<select id="p-side">
        <option value="ct" ${PLAY.side === "ct" ? "selected" : ""}>CT</option>
        <option value="t" ${PLAY.side === "t" ? "selected" : ""}>T</option></select></label>
    </div>
    <div class="row"><button class="btn primary" id="p-go" ${!setUp ? "disabled" : ""}>进入训练赛</button>
      <span class="hint">${setUp ? "进游戏后：与机器人游戏 → 竞技 → 选同一张图" : "没装人机增强就不能进 CS2，可先按实力出战"}</span></div>
  </div></div>`;

  h += `<div class="grid2" style="margin-bottom:12px">${lineup(c.team_name, true)}${opp ? lineup(opp.name) : ""}</div>`;

  const res = PLAY.result;
  if (res && res.status && res.status !== "none") {
    const final = res.status === "finished";
    h += `<div class="scoreline"><span class="nm">${esc(res.ct_name || "CT")}</span>
      <b>${res.ct_score ?? 0} : ${res.t_score ?? 0}</b>
      <span class="nm">${esc(res.t_name || "T")}</span>
      ${badge(final ? "done" : "live", final ? "终场" : "进行中")}</div>`;
    if (res.players?.length) {
      const rows = [...res.players].sort((a, b) => (b.kills || 0) - (a.kills || 0));
      h += `<div class="card pad0"><h3>${mapName((res.map || "").replace("de_", ""))} 数据</h3><table><thead>
        <tr><th>选手</th><th>阵营</th><th class="num">K</th><th class="num">D</th><th class="num">A</th><th class="num">伤害</th></tr></thead><tbody>`;
      for (const p of rows) {
        h += `<tr class="${isMe(p.name) ? "me" : ""}"><td>${esc(p.name)}${p.is_bot === false ? " ★" : ""}</td>
          <td><small class="hint">${esc(p.team || "")}</small></td><td class="num">${p.kills ?? 0}</td>
          <td class="num">${p.deaths ?? 0}</td><td class="num">${p.assists ?? 0}</td><td class="num">${p.damage ?? 0}</td></tr>`;
      }
      h += `</tbody></table></div>`;
    }
  }

  $("view-play").innerHTML = h;
  bindBotSettings(() => { PLAY.cs2 = null; renderPlay(); });
  $("p-opp").onchange = (e) => { PLAY.opp = e.target.value; renderPlay(); };
  $("p-map").onchange = (e) => { PLAY.map = e.target.value; };
  $("p-side").onchange = (e) => { PLAY.side = e.target.value; };
  if ($("p-save")) {
    $("p-save").onclick = async () => {
      await post("/api/cs2/settings", {
        steam_exe: $("p-steam").value.trim(),
        csgo_path: $("p-csgo").value.trim(),
        mod_source_path: $("p-mod").value.trim(),
      });
      PLAY.cs2 = null;
      renderPlay();
    };
  }
  if ($("p-install")) {
    $("p-install").onclick = async (e) => {
      e.target.disabled = true;
      e.target.textContent = "复制中…";
      await post("/api/cs2/install", {});
      PLAY.cs2 = null;
      renderPlay();
    };
  }
  if ($("p-go")) {
    $("p-go").onclick = async () => {
      PLAY.expectTrain = true;
      PLAY.trainedAt = "";
      await post("/api/play", { opp: PLAY.opp, map: PLAY.map, side: PLAY.side });
      startPolling();
    };
  }
  if (!PLAY_TIMER) startPolling();
}

function startPolling() {
  if (PLAY_TIMER) clearInterval(PLAY_TIMER);
  const tick = async () => {
    if (VIEW !== "play") return;
    try {
      const res = await get("/api/play/result");
      const changed = JSON.stringify(res) !== JSON.stringify(PLAY.result);
      PLAY.result = res;
      if (res.status === "finished" && PLAY.expectTrain && res.ended_at && res.ended_at !== PLAY.trainedAt) {
        PLAY.trainedAt = res.ended_at;
        PLAY.expectTrain = false;
        await post("/api/train/finish");
        return;
      }
      if (changed) renderPlay();
    } catch { /* game not running yet */ }
  };
  PLAY_TIMER = setInterval(tick, 4000);
  tick();
}

/* ----------------------------------------------------------------- stories */

let STORY_Q = [];
let STORY_BUSY = false;

function takeStories(rows) {
  if (!rows?.length) return;
  for (const row of rows) {
    if (!row?.id) continue;
    if (row.kind !== "awards" && row.kind !== "top20" && !row.text) continue;
    if (STORY_Q.some((s) => s.id === row.id)) continue;
    STORY_Q.push(row);
  }
  paintStory();
}

let REVEAL_TIMER = null;
let REVEAL_STEP = 0;
let REVEAL_NODES = [];
let revealNext = null;

function stopReveal() {
  if (REVEAL_TIMER) clearInterval(REVEAL_TIMER);
  REVEAL_TIMER = null;
}

function paintStory() {
  stopReveal();
  revealNext = null;
  let box = $("story-modal");
  const row = STORY_Q[0];
  if (!row) {
    if (box) box.remove();
    STORY_BUSY = false;
    return;
  }
  STORY_BUSY = true;
  if (!box) {
    box = document.createElement("div");
    box.id = "story-modal";
    document.body.appendChild(box);
  }
  if (row.kind === "awards") {
    paintAwards(box, row);
    return;
  }
  if (row.kind === "top20") {
    if (box.dataset.tid !== row.id) TOP20_PAGE = 0;
    box.dataset.tid = row.id;
    paintTop20(box, row);
    return;
  }
  const choices = row.choices || [];
  const paras = String(row.text || "").split("\n").filter(Boolean).map((p) => `<p>${esc(p)}</p>`).join("");
  const foot = choices.length
    ? choices.map((ch) => `<button class="btn ${ch.id === "accept" ? "" : "primary"}" type="button" data-choice="${esc(ch.id)}">${esc(ch.label)}</button>`).join("")
    : `<button class="btn primary" type="button">继续</button>`;
  box.innerHTML = `<div class="story-card">
      <button class="story-x" type="button" aria-label="关闭">×</button>
      <small>剧情</small>
      <div class="story-scroll">
        ${row.title ? `<h2>${esc(row.title)}</h2>` : ""}
        ${paras}
      </div>
      <div class="story-foot${choices.length ? " split" : ""}">${foot}</div>
    </div>`;
  box.querySelector(".story-x").onclick = () => ackStory(choices.length ? "refuse" : "");
  box.querySelectorAll(".story-foot [data-choice]").forEach((b) => {
    b.onclick = () => ackStory(b.dataset.choice);
  });
  const cont = box.querySelector(".story-foot button:not([data-choice])");
  if (cont) cont.onclick = () => ackStory("");
}

function playerFace(row) {
  if (!row?.player) return "";
  return `<span class="reveal-who">${tm(row.team, 22)}<span class="reveal-name">
    <b>${esc(row.player)}</b>
    <small>${row.role ? esc(ROLE[row.role] || row.role) : ""}${row.rating != null ? ` · ${r2(row.rating)}` : ""}</small>
  </span></span>`;
}

function paintAwards(box, row) {
  const cls = CLS[row.class] || row.class || "";
  const mvp = row.mvp;
  const evp = row.evp || [];
  const five = row.five || [];
  const slots = [];
  if (mvp) slots.push({ kind: "mvp", label: mvp.title || "MVP", row: mvp });
  evp.forEach((p, i) => slots.push({ kind: "evp", label: evp.length > 1 ? `EVP ${i + 1}` : (p.title || "EVP"), row: p }));
  five.forEach((p, i) => slots.push({ kind: "five", label: `最佳阵容 ${i + 1}`, row: p }));

  let body = `<div class="story-card awards-card">
    <button class="story-x" type="button" aria-label="关闭">×</button>
    <small>赛事荣誉</small>
    <div class="story-scroll">
    <h2>${esc(row.title || row.event || "赛事荣誉")}</h2>
    <p class="awards-lead">${cls ? `${esc(cls)} · ` : ""}冠军 ${esc(row.champion || "—")}</p>`;
  if (mvp) {
    body += `<div class="reveal-block"><div class="reveal-kicker">MVP</div>
      <div class="reveal-slot mvp" data-i="${slots.findIndex((s) => s.kind === "mvp")}"><i>?</i></div></div>`;
  }
  if (evp.length) {
    body += `<div class="reveal-block"><div class="reveal-kicker">EVP</div><div class="reveal-row">`;
    evp.forEach((p, i) => {
      const idx = slots.findIndex((s) => s.kind === "evp" && s.row === p);
      body += `<div class="reveal-slot evp" data-i="${idx}"><i>?</i></div>`;
    });
    body += `</div></div>`;
  }
  if (five.length) {
    body += `<div class="reveal-block"><div class="reveal-kicker">最佳阵容</div><div class="reveal-row five">`;
    five.forEach((p, i) => {
      const idx = slots.findIndex((s) => s.kind === "five" && s.row === p);
      body += `<div class="reveal-slot five" data-i="${idx}"><i>?</i></div>`;
    });
    body += `</div></div>`;
  }
  body += `</div><div class="story-foot"><button class="btn primary" type="button" disabled>继续</button></div></div>`;
  box.innerHTML = body;
  box.querySelector(".story-x").onclick = ackStory;

  const btn = box.querySelector(".story-foot button");
  REVEAL_STEP = 0;
  REVEAL_NODES = slots.map((slot, i) => {
    const el = box.querySelector(`[data-i="${i}"]`);
    return { el, slot };
  }).filter((x) => x.el);

  const showOne = () => {
    if (REVEAL_STEP >= REVEAL_NODES.length) {
      stopReveal();
      btn.disabled = false;
      btn.textContent = "继续";
      return true;
    }
    const { el, slot } = REVEAL_NODES[REVEAL_STEP];
    el.classList.add("show");
    el.innerHTML = `<em>${esc(slot.label)}</em>${playerFace(slot.row)}`;
    REVEAL_STEP += 1;
    if (REVEAL_STEP >= REVEAL_NODES.length) {
      stopReveal();
      btn.disabled = false;
    }
    return REVEAL_STEP >= REVEAL_NODES.length;
  };

  revealNext = () => {
    if (REVEAL_STEP < REVEAL_NODES.length) showOne();
    else ackStory();
  };
  btn.onclick = (e) => { e.stopPropagation(); revealNext(); };
  box.onclick = (e) => {
    if (e.target.closest("button")) return;
    if (REVEAL_STEP < REVEAL_NODES.length) showOne();
  };
  if (!REVEAL_NODES.length) {
    btn.disabled = false;
    return;
  }
  REVEAL_TIMER = setInterval(showOne, 850);
  setTimeout(showOne, 320);
}

let TOP20_PAGE = 0;

function top20Pages(rows) {
  const rest = [...(rows || [])].filter((r) => r.rank >= 4).sort((a, b) => b.rank - a.rank);
  const pages = [];
  for (let i = 0; i < rest.length; i += 7) pages.push({ solo: false, rows: rest.slice(i, i + 7) });
  for (const n of [3, 2, 1]) {
    const row = (rows || []).find((r) => r.rank === n);
    if (row) pages.push({ solo: true, rows: [row] });
  }
  return pages;
}

function paintTop20(box, row) {
  const pages = top20Pages(row.rows);
  if (!pages.length) {
    box.innerHTML = `<div class="story-card">
      <button class="story-x" type="button" aria-label="关闭">×</button>
      <small>${row.year} 年度</small>
      <div class="story-scroll"><p>这一年没有凑齐 Top 20。</p></div>
      <div class="story-foot"><button class="btn primary" type="button">继续</button></div>
    </div>`;
    box.querySelector(".story-x").onclick = ackStory;
    box.querySelector(".story-foot button").onclick = ackStory;
    return;
  }
  if (TOP20_PAGE >= pages.length) TOP20_PAGE = 0;
  const page = pages[TOP20_PAGE];
  const crown = { 1: "gold", 2: "silver", 3: "copper" };
  let inner = "";
  if (page.solo) {
    const p = page.rows[0];
    const me = p.player === row.you ? " me" : "";
    inner = `<div class="top-solo ${crown[p.rank] || ""}">
      <span class="crown ${crown[p.rank] || ""}">♛</span>
      <div class="top-rank">NO.${p.rank}</div>
      <h2>${esc(p.verse || "")}</h2>
      <div class="reveal-slot show${me}"><em>第 ${p.rank} 名</em>${playerFace(p)}</div>
      <div class="verse-lines">${(p.lines || []).map((t) => `<p>${esc(t)}</p>`).join("")}</div>
    </div>`;
  } else {
    inner = `<p class="awards-lead">从第 ${page.rows[0].rank} 名往上</p><div class="reveal-row">`;
    page.rows.forEach((p, i) => {
      inner += `<div class="reveal-slot${p.player === row.you ? " me" : ""}" data-i="${i}"><i>?</i></div>`;
    });
    inner += `</div>`;
  }
  box.innerHTML = `<div class="story-card awards-card">
    <button class="story-x" type="button" aria-label="关闭">×</button>
    <small>${row.year} 年度 Top 20</small>
    <div class="story-scroll">${inner}</div>
    <div class="story-foot"><button class="btn primary" type="button" ${page.solo ? "" : "disabled"}>${TOP20_PAGE < pages.length - 1 ? "下一批" : "继续"}</button></div>
  </div>`;
  box.querySelector(".story-x").onclick = () => { TOP20_PAGE = 0; ackStory(); };
  const btn = box.querySelector(".story-foot button");
  const finishPage = () => {
    if (TOP20_PAGE < pages.length - 1) {
      TOP20_PAGE += 1;
      paintTop20(box, row);
    } else {
      TOP20_PAGE = 0;
      ackStory();
    }
  };
  if (page.solo) {
    btn.onclick = finishPage;
    revealNext = finishPage;
    return;
  }
  REVEAL_STEP = 0;
  REVEAL_NODES = page.rows.map((p, i) => ({
    el: box.querySelector(`[data-i="${i}"]`),
    slot: { label: `第 ${p.rank} 名`, row: p },
  })).filter((x) => x.el);
  const showOne = () => {
    if (REVEAL_STEP >= REVEAL_NODES.length) {
      stopReveal();
      btn.disabled = false;
      return;
    }
    const { el, slot } = REVEAL_NODES[REVEAL_STEP];
    el.classList.add("show");
    el.innerHTML = `<em>${esc(slot.label)}</em>${playerFace(slot.row)}`;
    REVEAL_STEP += 1;
    if (REVEAL_STEP >= REVEAL_NODES.length) {
      stopReveal();
      btn.disabled = false;
    }
  };
  revealNext = () => {
    if (REVEAL_STEP < REVEAL_NODES.length) showOne();
    else finishPage();
  };
  btn.onclick = (e) => { e.stopPropagation(); revealNext(); };
  box.onclick = (e) => {
    if (e.target.closest("button")) return;
    if (REVEAL_STEP < REVEAL_NODES.length) showOne();
  };
  REVEAL_TIMER = setInterval(showOne, 850);
  setTimeout(showOne, 280);
}

async function ackStory(choice) {
  const row = STORY_Q.shift();
  paintStory();
  if (!row) return;
  try {
    await fetch("/api/story/ack", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: row.id, choice: choice || "" }),
    });
    const fresh = await get("/api/state");
    adopt(fresh);
    render();
    takeStories(S.career?.stories);
  } catch { /* keep going even if ack fails; it will reappear next load */ }
}

document.addEventListener("keydown", (e) => {
  if (!STORY_BUSY) return;
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    if (revealNext) revealNext();
    else if (!STORY_Q[0]?.choices) ackStory("");
  }
});

/* ----------------------------------------------------------------- boot */

document.querySelectorAll("[data-view]").forEach((b) => (b.onclick = () => show(b.dataset.view)));
$("btn-next").onclick = async () => {
  const out = await post("/api/next");
  $("top-msg").textContent = out.msg || "";
  jumpToYourMatch();
};
$("btn-skip").onclick = async () => {
  const out = await post("/api/skip");
  $("top-msg").textContent = out.msg || "";
  jumpToYourMatch();
};

document.addEventListener("keydown", (e) => {
  if (STORY_BUSY) return;
  if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
  if (e.key === "n") $("btn-next").click();
  if (e.key === "m") $("btn-skip").click();
});

(async function boot() {
  try {
    adopt(await get("/api/state"));
    VIEW = S.career?.exists ? "home" : "setup";
    render();
    takeStories(S.career?.stories);
  } catch (err) {
    document.body.innerHTML = `<div class="toast err">加载失败：${esc(String(err))}</div>`;
  }
})();
