extends RefCounted
## Native money and transfers views. CareerBridge supplies every quote and mutation.
const UI = preload("res://scripts/computer_ui.gd")
var host
var transfer_source := "free"
var transfer_search := ""
var transfer_role := ""
var transfer_page := 1
var replace_id := ""
var pending_purchase: Dictionary = {}
var pending_application: Dictionary = {}
var cash_inputs: Dictionary = {}

func attach(value: CanvasLayer) -> void:
	host = value

static func money(value) -> String:
	return "$%s" % int(value) if typeof(value) in [TYPE_INT, TYPE_FLOAT] else "—"

static func numeric(value, digits: int = 1) -> String:
	if typeof(value) not in [TYPE_INT, TYPE_FLOAT]:
		return "—"
	return "%.2f" % float(value) if digits == 2 else "%.1f" % float(value)

func _label(parent: Node, text: String, size: int = 14, color: Color = UI.INK) -> Label:
	return host._label(parent, text, size, color)

func _button(parent: Node, text: String, callback: Callable, write: bool = true) -> Button:
	return host._button(parent, text, callback, write)

func render_operations() -> void:
	var ops: Dictionary = CareerBridge.context.get("operations", {})
	var finance: Dictionary = CareerBridge.context.get("finance", {})
	_label(host.content, "经营与财务", 25)
	_label(host.content, "工资与奖金自动入账。俱乐部和个人的资金各自记账。", 14, UI.MUTED)
	if ops.is_empty():
		_label(host.content, "经营资料还没有载入。")
		return
	var accounts := HBoxContainer.new()
	accounts.add_theme_constant_override("separation", 16)
	host.content.add_child(accounts)
	if not bool(ops.get("unsigned", false)):
		_account(accounts, "俱乐部账户" + (" · 仅查看" if ops.get("player_only", false) else ""), finance.get("club", {}))
	_account(accounts, "个人口袋", finance.get("pocket", {}))
	_label(host.content, str(finance.get("note", "")), 13, UI.MUTED)
	if ops.get("player_only", false):
		_label(host.content, "你是签约选手，俱乐部引援与经营由管理层负责。", 15)
	if ops.get("crisis", false):
		_label(host.content, "经营危机 · 工资缺口 " + money(ops.get("deficit")), 18, Color("a25746"))
		_label(host.content, "请先处理资金缺口或手机里的经营事件。", 14, UI.MUTED)
	var loan: Dictionary = ops.get("loan", {}) if ops.get("loan") is Dictionary else {}
	if loan.get("active", false):
		var box := UI.card(host.content)
		_label(box, "借款 · " + str(loan.get("kind_label", "")), 19)
		_label(box, "本金 %s · 欠息 %s · 月息 %s%% · 连续未还 %s 月" % [money(loan.get("principal")), money(loan.get("arrears")), numeric(float(loan.get("rate", 0)) * 100), loan.get("missed", 0)], 14)
		_cash_form(box, "repay", "偿还借款", int(loan.get("principal", 0)) + int(loan.get("arrears", 0)), true)
	elif not ops.get("unsigned", false) and not ops.get("banned", false) and not ops.get("retired", false):
		var box := UI.card(host.content)
		_label(box, "借款 · " + str(loan.get("kind_label", "")), 19)
		var cap := int(loan.get("cap", 0))
		_label(box, "可借额度 " + money(cap) + " · 月息 " + numeric(float(loan.get("rate", 0)) * 100) + "%", 14)
		_label(box, "借款进入俱乐部还是个人账户，沿用当前生涯合同规则。", 13, UI.MUTED)
		_cash_form(box, "borrow", "申请借款", cap, cap > 0)
	if not ops.get("unsigned", false):
		var ledger := UI.card(host.content)
		_label(ledger, "俱乐部账本", 19)
		_label(ledger, "每月支出 %s · 工资 %s · 生活与差旅 %s · 可维持 %s 月" % [money(ops.get("total")), money(ops.get("salaries")), money(ops.get("living")), ops.get("runway", "—")], 14)
		for wage in ops.get("wages", []):
			var row := HBoxContainer.new()
			ledger.add_child(row)
			var player_key := str(wage.get("player_id", wage.get("name", "")))
			_button(row, str(wage.get("name", "")), host._load_detail.bind("player", player_key), false).size_flags_horizontal = Control.SIZE_EXPAND_FILL
			_label(row, money(wage.get("pay")))
		for line in ops.get("log", []):
			_label(ledger, str(line), 13, UI.MUTED)
		if not ops.get("player_only", false):
			_cash_form(ledger, "donate", "从个人口袋支持俱乐部", maxi(1, int(ops.get("deficit", 5000))), true)
	if not ops.get("upgrade_supported", false):
		_label(host.content, str(ops.get("upgrade_reason", "原业务尚无设施升级功能。")), 13, UI.MUTED)

func _account(parent: Node, title: String, account: Dictionary) -> void:
	var box := UI.card(parent)
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_label(box, title, 16, UI.MUTED)
	var balance := _label(box, money(account.get("balance")), 29)
	var net := int(account.get("next_net", 0))
	_label(box, ("↑ +" if net > 0 else "↓ −" if net < 0 else "→ ") + money(absi(net)) + " 预计下月", 14, UI.GREEN if net >= 0 else Color("a25746"))
	var tooltip := "下月固定收支\n"
	for line in account.get("lines", []):
		tooltip += "%s  %s%s\n" % [line.get("label", ""), "+" if int(line.get("amount", 0)) >= 0 else "−", money(absi(int(line.get("amount", 0))))]
	tooltip += "\n近期入账与支出\n"
	for line in account.get("recent", []):
		tooltip += "%s · %s  %s%s\n" % [line.get("date", ""), line.get("label", ""), "+" if int(line.get("amount", 0)) >= 0 else "−", money(absi(int(line.get("amount", 0))))]
	balance.tooltip_text = tooltip.strip_edges()
	balance.mouse_filter = Control.MOUSE_FILTER_STOP
	_label(box, "资金来源与下月明细", 12, UI.MUTED).tooltip_text = balance.tooltip_text
	for line in account.get("lines", []):
		_label(box, "%s · %s%s" % [line.get("label", ""), "+" if int(line.get("amount", 0)) >= 0 else "−", money(absi(int(line.get("amount", 0))))], 13, UI.MUTED)

func _cash_form(parent: Node, action: String, caption: String, suggested: int, enabled: bool) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	parent.add_child(row)
	var amount := LineEdit.new()
	amount.name = "ComputerCashAmount_" + action
	amount.text = str(cash_inputs.get(action, str(maxi(1, suggested))))
	amount.placeholder_text = "金额"
	amount.custom_minimum_size = Vector2(175, 36)
	UI.line_edit(amount)
	amount.text_changed.connect(func(text: String): cash_inputs[action] = text)
	row.add_child(amount)
	var button := _button(row, caption, _cash_command.bind(action, amount))
	button.name = "ComputerCash_" + action
	button.disabled = not enabled

func _cash_command(action: String, amount: LineEdit) -> void:
	var text := amount.text.strip_edges()
	if not text.is_valid_int() or int(text) <= 0:
		host.notice = "请输入大于零的整数金额。"
		host._update_status()
		return
	host._device_command("/api/3d/ops/" + action, {"amount":int(text)})

func render_transfers() -> void:
	var data: Dictionary = CareerBridge.context.get("transfers", {})
	var personal: Dictionary = CareerBridge.context.get("player_transfers", data.get("personal", {}))
	_label(host.content, "转会", 25)
	var tabs := [{"id":"free", "label":"自由球员"}, {"id":"active", "label":"现役买断"}, {"id":"academy", "label":"青训"}, {"id":"personal", "label":"我的转会"}]
	if not data.get("club_allowed", false):
		transfer_source = "personal"
		tabs = [{"id":"personal", "label":"我的转会"}]
		_label(host.content, str(data.get("reason", "当前只能办理个人转会。")), 14, UI.MUTED)
	host._tabs(host.content, tabs, transfer_source, _set_source)
	if transfer_source == "personal":
		_render_personal(personal)
		return
	_label(host.content, "俱乐部资金 " + money(data.get("club_money")), 20)
	_label(host.content, "普通签约按成功率谈判；失败收谈判费。现役选手只能买断。报价与阵容在确认时重新核对。", 13, UI.MUTED)
	_replace_selector(data.get("roster", []))
	_filters()
	if not pending_purchase.is_empty():
		_render_purchase_confirmation(data)
	var rows: Array = []
	for value in data.get("players", []):
		var contracted := not str(value.get("seller_id", "")).is_empty()
		var academy: bool = value.get("academy_year") != null or str(value.get("note", "")).contains("青训")
		if (transfer_source == "active" and not contracted) or (transfer_source == "free" and (contracted or academy)) or (transfer_source == "academy" and (contracted or not academy)):
			continue
		if _matches_filter(str(value.get("name", "")) + " " + str(value.get("seller", "")), str(value.get("role", ""))):
			rows.append(value)
	_label(host.content, "%s 位可查看选手" % rows.size(), 13, UI.MUTED)
	for item in _paged(rows):
		var box := UI.card(host.content)
		var row := HBoxContainer.new()
		box.add_child(row)
		var player_key := str(item.get("player_id", ""))
		_button(row, str(item.get("name", "")), host._load_detail.bind("player", player_key), false).size_flags_horizontal = Control.SIZE_EXPAND_FILL
		_label(row, "%s · 能力 %s · %s 岁 · %s" % [Phone.ROLES.get(item.get("role", ""), item.get("role", "")), numeric(item.get("ability")), item.get("age", "—"), item.get("seller", "自由球员")], 14, UI.MUTED)
		var prices := HBoxContainer.new()
		prices.add_theme_constant_override("separation", 12)
		box.add_child(prices)
		var normal = item.get("normal_fee")
		if typeof(normal) in [TYPE_INT, TYPE_FLOAT]:
			var chance := float(item.get("normal_chance", 0))
			var normal_button := _button(prices, "尝试签约 %s · %.0f%%" % [money(normal), chance * 100], _ask_purchase.bind(item, "normal"))
			normal_button.disabled = not str(item.get("blocked", "")).is_empty() or chance <= 0 or int(data.get("club_money", 0)) < int(normal) or replace_id.is_empty()
			_label(box, "谈判未成仅扣 " + money(item.get("negotiation_fee")), 12, UI.MUTED)
		var guarantee := _button(prices, ("买断 " if not str(item.get("seller_id", "")).is_empty() else "100% 保签 ") + money(item.get("guaranteed_fee")), _ask_purchase.bind(item, "guaranteed"))
		guarantee.disabled = not str(item.get("blocked", "")).is_empty() or int(data.get("club_money", 0)) < int(item.get("guaranteed_fee", 0)) or replace_id.is_empty()
		if not str(item.get("blocked", "")).is_empty():
			_label(box, str(item["blocked"]), 13, UI.MUTED)
	_pager(rows.size())

func _replace_selector(roster: Array) -> void:
	_label(host.content, "新队员入队后替换谁", 14, UI.MUTED)
	var replacement := OptionButton.new()
	replacement.name = "ComputerTransferReplace"
	UI.dark_options(replacement)
	var keys: Array[String] = []
	for player in roster:
		var key := str(player.get("player_id", player.get("id", "")))
		keys.append(key)
		replacement.add_item(str(player.get("name", "")) + " · " + str(Phone.ROLES.get(player.get("role", ""), player.get("role", ""))))
	if replace_id not in keys:
		replace_id = keys[0] if not keys.is_empty() else ""
	if not keys.is_empty():
		replacement.select(keys.find(replace_id))
	replacement.disabled = keys.is_empty()
	replacement.item_selected.connect(func(index: int): replace_id = keys[index])
	host.content.add_child(replacement)

func _filters() -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	host.content.add_child(row)
	var search := LineEdit.new()
	UI.line_edit(search)
	search.text = transfer_search
	search.placeholder_text = "选手或战队名称" if transfer_source != "personal" else "战队名称"
	search.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(search)
	var roles := OptionButton.new()
	UI.dark_options(roles)
	roles.add_item("全部位置")
	var keys: Array[String] = [""]
	for key in Phone.ROLES:
		keys.append(str(key))
		roles.add_item(str(Phone.ROLES[key]))
	if transfer_role in keys:
		roles.select(keys.find(transfer_role))
	row.add_child(roles)
	var apply := func():
		transfer_search = search.text.strip_edges()
		transfer_role = keys[roles.selected]
		transfer_page = 1
		host.page_scroll["transfers"] = 0
		host._rebuild()
	_button(row, "筛选", apply, false)
	search.text_submitted.connect(func(_text: String): apply.call())

func _matches_filter(title: String, role: String) -> bool:
	return (transfer_search.is_empty() or title.to_lower().contains(transfer_search.to_lower())) and (transfer_role.is_empty() or role == transfer_role)

func _set_source(value: String) -> void:
	transfer_source = value
	transfer_page = 1
	pending_purchase = {}
	pending_application = {}
	host.page_scroll["transfers"] = 0
	host._rebuild()

func _paged(rows: Array) -> Array:
	transfer_page = clampi(transfer_page, 1, maxi(1, ceili(rows.size() / 18.0)))
	return rows.slice((transfer_page - 1) * 18, transfer_page * 18)

func _pager(count: int) -> void:
	if count == 0:
		_label(host.content, "没有符合条件的选手或位置。", 14, UI.MUTED)
		return
	var pages := maxi(1, ceili(count / 18.0))
	var row := HBoxContainer.new()
	host.content.add_child(row)
	_button(row, "上一页", _change_page.bind(-1), false).disabled = transfer_page <= 1
	_label(row, "%s / %s" % [transfer_page, pages])
	_button(row, "下一页", _change_page.bind(1), false).disabled = transfer_page >= pages

func _change_page(delta: int) -> void:
	transfer_page += delta
	host.page_scroll["transfers"] = 0
	host._rebuild()

func _ask_purchase(item: Dictionary, mode: String) -> void:
	var fee := int(item.get("normal_fee", 0)) if mode == "normal" else int(item.get("guaranteed_fee", 0))
	pending_purchase = {"player_id":item.get("player_id", ""), "seller_id":item.get("seller_id", ""), "mode":mode, "fee":fee, "replace_id":replace_id}
	pending_application = {}
	host.page_scroll["transfers"] = 0
	host._rebuild()

func _render_purchase_confirmation(data: Dictionary) -> void:
	var candidate: Dictionary = {}
	for item in data.get("players", []):
		if item.get("player_id") == pending_purchase.get("player_id") and item.get("seller_id", "") == pending_purchase.get("seller_id", ""):
			candidate = item
			break
	var box := UI.card(host.content)
	_label(box, "确认引援", 20)
	if candidate.is_empty():
		_label(box, "这位选手的报价已经变化，请重新选择。", 14)
	else:
		var replacement := ""
		for player in data.get("roster", []):
			if str(player.get("player_id", player.get("id", ""))) == str(pending_purchase.get("replace_id", "")):
				replacement = str(player.get("name", ""))
		_label(box, "%s → 入队 · %s → 离队" % [candidate.get("name", ""), replacement], 16)
		_label(box, "俱乐部支出 " + money(pending_purchase.get("fee")) + (" · 不保证谈判成功" if pending_purchase.get("mode") == "normal" else " · 100% 保证签约"), 14)
		if pending_purchase.get("mode") == "normal":
			_label(box, "本次成功率 %.0f%%，失败谈判费 %s。" % [float(candidate.get("normal_chance", 0)) * 100, money(candidate.get("negotiation_fee"))], 14, UI.MUTED)
		var current_fee = candidate.get("normal_fee") if pending_purchase.get("mode") == "normal" else candidate.get("guaranteed_fee")
		var button := _button(box, "确认签约", _confirm_purchase)
		button.name = "ComputerTransferConfirmBuy"
		button.disabled = current_fee != pending_purchase.get("fee") or replacement.is_empty() or not str(candidate.get("blocked", "")).is_empty() or not data.get("club_allowed", false) or int(data.get("club_money", 0)) < int(current_fee)
	_button(box, "取消", _dismiss_confirmation, false)

func _confirm_purchase() -> void:
	if not pending_purchase.is_empty():
		host._device_command("/api/3d/transfers/buy", pending_purchase.duplicate(true))

func _dismiss_confirmation() -> void:
	pending_purchase = {}
	pending_application = {}
	host._rebuild()

func _render_personal(data: Dictionary) -> void:
	_label(host.content, "我的职业去向", 21)
	_label(host.content, "今年收到 %s / %s 份主动邀约。试训成功后仍由你决定是否离队。" % [data.get("offers_this_year", 0), data.get("offer_limit", 4)], 14, UI.MUTED)
	_label(host.content, "申请冷却至 %s · 加盟锁定至 %s" % [_date_text(data.get("apply_until", "")), _date_text(data.get("move_until", ""))], 14)
	var last = data.get("last_attempt")
	if last is Dictionary and not last.is_empty():
		_label(host.content, "上次试训 · %s · D20 %s %+d = %s · %s" % [last.get("team", ""), last.get("roll", "—"), int(last.get("modifier", 0)), last.get("total", "—"), "通过" if last.get("success", false) else "未通过"], 15)
	var offers: Array = data.get("offers", [])
	if not offers.is_empty() or data.get("pending"):
		var box := UI.card(host.content)
		_label(box, "加盟机会", 19)
		for offer in offers:
			var mail_id := str(offer.get("id", ""))
			var offer_status := str(offer.get("status", ""))
			var offer_button := _button(box, str(offer.get("title", offer.get("team", "入队邀约"))) + " · " + str(offer.get("date", "")) + " · " + str({"":"状态未载入", "open":"待决定", "expired":"已过期", "accepted":"已接受", "declined":"已拒绝", "read":"已读"}.get(offer_status, offer_status)), host._open_phone_mail.bind(mail_id), false)
			offer_button.disabled = mail_id.is_empty()
		if data.get("pending"):
			_button(box, "处理当前加盟决定", host._open_phone.bind("stories"), false)
	_filters()
	if not pending_application.is_empty():
		var box := UI.card(host.content)
		_label(box, "确认申请试训", 20)
		_label(box, "%s · %s · 成功率 %.0f%%" % [pending_application.get("team", ""), Phone.ROLES.get(pending_application.get("role", ""), pending_application.get("role", "")), float(pending_application.get("chance", 0)) * 100], 15)
		_label(box, "只掷一次 D20。失败冷却30天，成功冷却90天；最终加盟后180天不能再次转会。", 13, UI.MUTED)
		var confirm := _button(box, "申请并掷 D20", _confirm_application)
		confirm.name = "ComputerTransferConfirmApply"
		confirm.disabled = not str(pending_application.get("blocked", "")).is_empty()
		_button(box, "取消", _dismiss_confirmation, false)
	var rows: Array = []
	for item in data.get("targets", []):
		if _matches_filter(str(item.get("team", "")), str(item.get("role", ""))):
			rows.append(item)
	for item in _paged(rows):
		var box := UI.card(host.content)
		var row := HBoxContainer.new()
		box.add_child(row)
		_button(row, str(item.get("team", "")), host._load_detail.bind("team", str(item.get("team_id", ""))), false).size_flags_horizontal = Control.SIZE_EXPAND_FILL
		_label(row, "%s · 接替 %s · 修正 %+d · %.0f%%" % [Phone.ROLES.get(item.get("role", ""), item.get("role", "")), item.get("replace", ""), int(item.get("modifier", 0)), float(item.get("chance", 0)) * 100], 14)
		var apply := _button(row, "申请试训", _ask_application.bind(item))
		apply.disabled = not str(item.get("blocked", "")).is_empty()
		if not str(item.get("blocked", "")).is_empty():
			_label(box, str(item["blocked"]), 13, UI.MUTED)
	_pager(rows.size())
	_label(host.content, "转会经历", 19)
	for record in data.get("history", []):
		_label(host.content, "%s · %s → %s · %s" % [record.get("date", ""), record.get("old_team", ""), record.get("new_team", ""), Phone.ROLES.get(record.get("transfer_role", ""), record.get("transfer_role", ""))], 14)
	if data.get("history", []).is_empty():
		_label(host.content, "还没有正式转会。", 14, UI.MUTED)

static func _date_text(value) -> String:
	return str(value) if not str(value).is_empty() else "无"

func _ask_application(item: Dictionary) -> void:
	pending_application = item.duplicate(true)
	pending_purchase = {}
	host.page_scroll["transfers"] = 0
	host._rebuild()

func _confirm_application() -> void:
	if not pending_application.is_empty():
		host._device_command("/api/3d/transfers/apply", {"team_id":pending_application.get("team_id", ""), "role":pending_application.get("role", "")})

func finished(path: String, result: Dictionary) -> void:
	if not path.begins_with("/api/3d/transfers/"):
		return
	if result.get("ok", false):
		pending_purchase = {}
		pending_application = {}
