/* Configuration has one home, independent of employment/training eligibility. */
(() => {
CareerUI.pages.settings = async (_route,host,active) => {
  const cfg = await get('/api/cs2/status'); if(!active())return;
  const c=S.career||{},gd=cfg.gamedata||{},live=!!cfg.cs2_live;
  const setUp=cfg.ready&&cfg.mod_installed&&cfg.levels_ok;
  const refresh=()=>{PLAY.cs2=null;CareerUI.go('settings',{},true);};
  let h=CareerUI.head('游戏设置','路径、Bot 与换肤配置集中在此处；无需加入战队即可查看。');
  h += `<div class="card" style="margin-bottom:12px"><h3>${setUp ? "游戏路径" : "首次设置（进 CS2 必做）"}</h3><div class="form">
    <label>steam.exe ${cfg.steam_ok ? "✓" : "✗"}<input id="p-steam" value="${esc(cfg.steam_exe || "")}"></label>
    <label>csgo 目录 ${cfg.csgo_ok ? "✓" : "✗"}<input id="p-csgo" value="${esc(cfg.csgo_path || "")}" placeholder="要到 game\\csgo 那一层，填游戏根目录也会自动补"></label>
    <label>人机增强目录 ${cfg.mod_ok ? "✓" : "✗"}<input id="p-mod" value="${esc(cfg.mod_source_path || "")}"></label>
    <label>换肤插件目录 ${cfg.skins_ok ? "✓" : "✗"}<input id="p-skins" value="${esc(cfg.skins_source_path || "")}" placeholder="可空，默认用生涯自带的修过读取的插件"></label>
    <div class="row"><button class="btn" id="p-save">保存路径</button>
      <button class="btn primary" id="p-install" ${cfg.ready && !live ? "" : "disabled"}>把人机增强装进游戏</button>
      <button class="btn" id="p-sync" disabled>每场自动生成 9 人</button>
      <button class="btn" id="p-skins-install" ${cfg.mod_installed && (cfg.skins_ok || cfg.skins_installed) && !live ? "" : "disabled"}>把换肤插件装进游戏</button>
      <button class="btn ghost" id="p-gamedata">更新换肤签名</button>
    </div>
    <p class="hint">${
      live
        ? "CS2 还开着：不能安装、不能同步。难度若刚改过，也必须先退游戏再进局。"
        : cfg.ready
        ? (
            !cfg.mod_installed
              ? "路径已保存。先点「把人机增强装进游戏」。装完后「把换肤插件装进游戏」才会亮。"
              : "人机增强已在游戏里。要换肤再点「把换肤插件装进游戏」，然后在本页打开换肤并填 SteamID。"
          )
        : "csgo 目录必须是 ...\\Counter-Strike Global Offensive\\game\\csgo。Steam「浏览本地文件」打开的是上一层，少了 game\\csgo。填根目录也可以，保存时会自动补上。"
    }</p>
    <p class="hint">换肤签名：内置 ${gd.bundled?.sha256?.slice(0, 8) || "—"} · 缓存 ${gd.cached?.sha256?.slice(0, 8) || "—"} · 游戏 ${gd.installed?.sha256?.slice(0, 8) || "—"}${gd.pending_install ? "（待退出 CS2 后安装）" : ""}</p>
  </div></div>`;

  h += botSettingsCard(cfg);
  h+=`<div class="card"><h3>游戏内换肤</h3>
    <p class="hint">只影响已安装换肤插件的本地 CS2 对局；生涯饰品在收藏分区管理。</p>
    <label class="row"><input id="skin-real" type="checkbox" ${c.real_skins?'checked':''}>启用游戏内换肤</label>
    <div class="row"><input id="skin-sid" class="locker-input" value="${esc(c.steam_id||'')}" placeholder="17 位 SteamID"><button id="skin-pref" class="btn">保存换肤偏好</button></div>
    ${S.design_preview?'<p class="hint">隔离预览中只展示设置，不会修改游戏或配置。</p>':''}
  </div>`;
  host.innerHTML=h;
  bindBotSettings(refresh);bindSkinPref();
  if ($("p-save")) {
    $("p-save").onclick = async () => {
      await post("/api/cs2/settings", {
        steam_exe: $("p-steam").value.trim(),
        csgo_path: $("p-csgo").value.trim(),
        mod_source_path: $("p-mod").value.trim(),
        skins_source_path: $("p-skins")?.value.trim() || "",
      });
      PLAY.cs2 = null;
      refresh();
    };
  }
  if ($("p-install")) {
    $("p-install").onclick = async (e) => {
      e.target.disabled = true;
      e.target.textContent = "复制中…";
      const out = await post("/api/cs2/install", {});
      PLAY.cs2 = null;
      refresh();
    };
  }
  if ($("p-sync")) {
    $("p-sync").onclick = async (e) => {
      e.target.disabled = true;
      e.target.textContent = "同步中…";
      await post("/api/cs2/sync", {});
      PLAY.cs2 = null;
      refresh();
    };
  }
  if ($("p-skins-install")) {
    $("p-skins-install").onclick = async (e) => {
      e.target.disabled = true;
      e.target.textContent = "复制中…";
      await post("/api/cs2/skins", {});
      PLAY.cs2 = null;
      refresh();
    };
  }
  if ($("p-gamedata")) {
    $("p-gamedata").onclick = async (e) => {
      e.target.disabled = true;
      e.target.textContent = "更新中…";
      await post("/api/cs2/gamedata", {});
      PLAY.cs2 = null;
      refresh();
    };
  }

  if(S.design_preview)host.querySelectorAll('button,input,select').forEach(e=>e.disabled=true);
};
})();
