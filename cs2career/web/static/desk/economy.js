/* Financial commands live here; cosmetic actions belong only to collection.js. */
(() => {
CareerUI.pages.locker = (_route,host) => {
  const c = S.career;
  const ops = c.ops || {};
  let h = `<div class="page-head"><h2>俱乐部经营</h2>
    <span class="hint">资金自动结算；把鼠标移到金额上可查看来源和下月明细</span></div>`;

  const finance = ops.finance || {};
  h += `<div class="finance-board ${c.unsigned ? "single" : ""}">
    ${!c.unsigned ? financeCard("俱乐部资金", finance.club || { balance: c.money }) : ""}
    ${financeCard("个人口袋", finance.pocket || { balance: c.pocket }, "personal")}
  </div>
  <p class="finance-note">${esc(finance.note || "下月预测不包含尚未发生的赛事奖金和临时交易。")}</p>`;

  if (c.crisis) {
    h += `<div class="card" style="margin-bottom:12px;border-color:#6a2a2a"><h3>经营危机</h3>
      <p class="hint">发不出工资，缺口 ${money(c.deficit)}。捐满才能续命，否则下个月解散，队友进转会市场，你留下重开新队。</p>
      <div class="row"><input id="don-amt" class="locker-input" type="number" min="1" value="${c.deficit || 1000}">
        <button class="btn primary sm" id="don-go">捐给俱乐部</button>
        <button class="btn sm" id="found-go">现在解散并重开</button></div></div>`;
  }

  if (c.unsigned) {
    h += `<div class="card" style="margin-bottom:12px"><h3>自由市场</h3>
      <p class="hint">你现在没有俱乐部，不能借款，也不能打官方赛和训练赛。去邮箱看入队合同，或继续逛皮肤市场。</p>
      <div class="row"><button class="btn primary sm" id="go-mail-fa">打开邮箱</button></div></div>`;
  }

  const loan = c.loan || {};
  if (!c.unsigned && !c.banned) {
    const ratePct = Math.round((loan.rate || 0) * 100);
    const due = (loan.principal || 0) + (loan.arrears || 0);
    h += `<div class="card" style="margin-bottom:12px"><h3>借款</h3>`;
    if (loan.active) {
      h += `<p class="hint">向${esc(loan.kind_label || "俱乐部")}借的钱。月息 ${ratePct}%，每月从口袋扣；扣不起算一个月没还。连续三个月没付上利息会发最后通牒。</p>
        <div class="grid4" style="margin-bottom:10px">
          <div class="stat"><b>${money(loan.principal)}</b><small>剩余本金</small></div>
          <div class="stat"><b>${money(loan.arrears)}</b><small>未付利息</small></div>
          <div class="stat"><b>${loan.missed || 0} / 3</b><small>连续未还</small></div>
          <div class="stat"><b>${money(loan.interest)}</b><small>下月利息</small></div>
        </div>
        <div class="row">
          <input id="repay-amt" class="locker-input" type="number" min="1" value="${due || 1}">
          <button class="btn primary sm" id="repay-go">还款</button>
        </div>`;
    } else {
      const who = loan.kind_label || (c.mode === "create" ? "银行" : "俱乐部");
      h += `<p class="hint">${c.mode === "create" ? "自建队向银行借，钱进俱乐部金库。" : "从俱乐部金库借到个人口袋，金库要留至少一个月开支。"} 同时只能欠一笔。</p>
        <div class="stat" style="margin-bottom:10px"><b>${money(loan.cap || 0)}</b><small>当前可向${esc(who)}借</small></div>
        <div class="row">
          <input id="borrow-amt" class="locker-input" type="number" min="1" value="${Math.max(1, loan.cap || 0)}">
          <button class="btn sm" id="borrow-go" ${loan.cap > 0 ? "" : "disabled"}>借款</button>
        </div>`;
    }
    h += `</div>`;
  }

  h += `<div class="grid2" style="margin-bottom:12px">`;
  if (!c.unsigned) {
    h += `<div class="card"><h3>俱乐部账本</h3>
      <div class="grid3" style="margin-bottom:10px">
        <div class="stat"><b>${money(ops.total)}</b><small>每月支出</small></div>
        <div class="stat"><b>${money(ops.salaries)}</b><small>工资</small></div>
        <div class="stat"><b>${ops.runway ?? 0} 月</b><small>还能撑</small></div>
      </div>
      <p class="hint">吃住 ${money(ops.living)} · 你的月薪 ${money(ops.your_salary)} · 奖金 12% 进个人，Major 出场费 $200,000 进俱乐部</p>
      <table><thead><tr><th>队员</th><th class="num">月薪</th></tr></thead><tbody>
        ${(ops.wages || []).map((w) => `<tr class="${w.name === c.player_name ? "me" : ""}"><td>${CareerUI.link("player",w.player_id||w.name,w.name)}</td><td class="num">${money(w.pay)}</td></tr>`).join("")}
      </tbody></table>
      ${(ops.log || []).length ? `<div style="margin-top:10px">${ops.log.map((x) => `<div class="hint">${esc(x)}</div>`).join("")}</div>` : ""}
      ${!c.crisis ? `<div class="row" style="margin-top:12px">
        <input id="don-amt" class="locker-input" type="number" min="1" value="5000">
        <button class="btn sm" id="don-go">捐给俱乐部</button>
      </div>` : ""}
    </div>`;
  }
  h += `<div class="card"><h3>个人账户</h3>
    <p class="hint">工资和赛事奖金分成自动入账。俱乐部账户用于阵容与日常运营，个人账户用于个人消费。</p>
    <p class="hint">饰品交易明细仍计入个人资金流水；物品管理、交易和开箱分别在收藏分区操作。</p>
    <div class="finance-scope"><span>赛事奖金</span><span>合同工资</span><span>借贷与还款</span></div>
  </div></div>`;
  host.innerHTML = h;
  if ($("don-go")) $("don-go").onclick = () => post("/api/ops/donate", { amount: Number($("don-amt")?.value || 0) });
  if ($("found-go")) $("found-go").onclick = () => { if (confirm("队友会进转会市场，你留下重开新队？")) post("/api/ops/found", {}); };
  if ($("go-mail-fa")) $("go-mail-fa").onclick = () => show("mail");
  if ($("borrow-go")) $("borrow-go").onclick = () => post("/api/ops/borrow", { amount: Number($("borrow-amt")?.value || 0) });
  if ($("repay-go")) $("repay-go").onclick = () => post("/api/ops/repay", { amount: Number($("repay-amt")?.value || 0) });
  if (S.design_preview) host.querySelectorAll('#don-go,#found-go,#borrow-go,#repay-go,input').forEach(e=>e.disabled=true);
};
})();
