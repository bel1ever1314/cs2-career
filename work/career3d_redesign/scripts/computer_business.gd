extends RefCounted
const Kit = preload("res://scripts/ui_kit.gd")
const Fmt = preload("res://scripts/ui_format.gd")
## Native money and transfers views. CareerBridge supplies every quote and mutation.
const UI = preload("res://scripts/computer_ui.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")
var host
var transfer_source := "free"
var transfer_search := ""
var transfer_role := ""
var transfer_page := 1
var transfer_sort := "ability"
var affordable_only := false
var replace_id := ""
var pending_purchase: Dictionary = {}
var pending_application: Dictionary = {}
var cash_inputs: Dictionary = {}
var pending_facility: Dictionary = {}
var recruitment := preload("res://scripts/club_recruitment_view.gd").new()

func attach(value: CanvasLayer) -> void:
	host = value
	recruitment.attach(value, self)

static func money(value) -> String:
	return preload("res://scripts/ui_format.gd").money(value)

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
	if ops.is_empty():
		_label(host.content, "经营资料还没有载入。")
		return
	var accounts := HBoxContainer.new()
	accounts.add_theme_constant_override("separation", 16)
	host.content.add_child(accounts)
	if not bool(ops.get("unsigned", false)):
		_account(accounts, "俱乐部账户", finance.get("club", {}))
	_account(accounts, "个人口袋", finance.get("pocket", {}))
	_label(host.content, str(finance.get("note", "")), 13, UI.MUTED)
	if ops.get("player_only", false):
		_label(host.content, "可以在转会市场与俱乐部商量换人；设施可在下方升级。", 15)
	_render_facilities()
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

func _render_facilities() -> void:
	var environment: Dictionary = CareerBridge.context.get("environment", {})
	var club: Dictionary = environment.get("club", {})
	if str(club.get("team_id", "")).is_empty(): return
	var box := UI.card(host.content)
	box.name = "ClubFacilities"
	_label(box, "俱乐部设施", 23)
	_label(box, Locale.field(club, "tier_name") + " · " + money(club.get("balance", 0)), 18)
	_label(box, "设施用俱乐部资金 · 家具用个人资金", 14, UI.MUTED)
	var blocked := str(environment.get("blocked", ""))
	if not blocked.is_empty(): _label(box, blocked, 14, Color("a25746"))
	var next_tier: Variant = club.get("next_tier")
	if next_tier is Dictionary:
		var tier := _button(box, "扩建为 %s · %s" % [Locale.field(next_tier, "name"), money(next_tier.price)], _ask_facility.bind("club-tier", {"team_id":club.team_id,"tier":next_tier.id,"price":int(next_tier.price)}, Locale.field(next_tier, "name")))
		tier.name = "ClubTierUpgrade"
		tier.disabled = not blocked.is_empty() or int(club.balance) < int(next_tier.price)
	for facility in club.get("upgrades", []):
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 12)
		box.add_child(row)
		var detail := VBoxContainer.new()
		detail.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(detail)
		_label(detail, "%s · Lv.%d" % [Locale.field(facility, "name"), int(facility.level)], 17)
		_label(detail, Locale.field(facility.current, "name"), 13, UI.MUTED)
		if facility.get("next") is Dictionary:
			var target: Dictionary = facility.next
			var button := _button(row, "升级 %s" % money(target.price), _ask_facility.bind("facility", {"team_id":club.team_id,"facility":facility.id,"level":int(facility.level)+1,"price":int(target.price)}, Locale.field(target, "name")))
			button.name = "FacilityUpgrade_" + str(facility.id)
			button.tooltip_text = Locale.field(target, "name")
			button.disabled = not blocked.is_empty() or int(club.balance) < int(target.price)
		else: _label(row, "已完成", 14, UI.GREEN)
	if not pending_facility.is_empty():
		_label(box, "购买 %s？从俱乐部账户支付 %s。" % [pending_facility.label, money(pending_facility.body.price)], 17)
		var choices := HBoxContainer.new()
		box.add_child(choices)
		_button(choices, "确认升级", _confirm_facility).name = "ConfirmFacilityUpgrade"
		_button(choices, "取消", _cancel_facility, false)

func _ask_facility(action: String, body: Dictionary, caption: String) -> void:
	pending_facility = {"action":action, "body":body.duplicate(true), "label":caption}
	host._rebuild()

func _cancel_facility() -> void:
	pending_facility.clear()
	host._rebuild()

func _confirm_facility() -> void:
	if pending_facility.is_empty(): return
	var payload: Dictionary = pending_facility.body.duplicate(true)
	payload["request_id"] = "club-%d-%d" % [Time.get_unix_time_from_system(), Time.get_ticks_usec()]
	var action := str(pending_facility.action)
	pending_facility.clear()
	host._device_command("/api/3d/environment/" + action, payload)

func _account(parent: Node, title: String, account: Dictionary) -> void:
	var box := UI.card(parent)
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_label(box, title, 16, UI.MUTED)
	var balance := _label(box, money(account.get("balance")), 29)
	var net := int(account.get("next_net", 0))
	if account.has("operating_reserve"):
		_label(box, "预留月度运营 " + money(account.operating_reserve), 14, UI.MUTED)
		_label(box, "可用引援预算 " + money(account.get("transfer_budget", 0)), 16, UI.GREEN)
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
	if not data.get("club_browsable", data.get("club_allowed", false)):
		transfer_source = "personal"
		tabs = [{"id":"personal", "label":"我的转会"}]
		_label(host.content, str(data.get("reason", "当前只能办理个人转会。")), 14, UI.MUTED)
	host._tabs(host.content, tabs, transfer_source, _set_source)
	if transfer_source == "personal":
		_render_personal(personal)
		return
	_label(host.content, "俱乐部资金 " + money(data.get("club_money")), 20)
	_label(host.content, "预留月度运营 " + money(data.get("operating_reserve", 0)) + " · 可用引援预算 " + money(data.get("transfer_budget", 0)), 14, UI.MUTED)
	_label(host.content, "普通签约按成功率谈判；失败收谈判费。现役选手只能买断。报价与阵容在确认时重新核对。", 13, UI.MUTED)
	_replace_selector(data.get("roster", []))
	recruitment.render(data)
	var signing_allowed: bool = recruitment.allowed(data, replace_id)
	if not str(data.get("reason", "")).is_empty(): _label(host.content, str(data.reason), 13, UI.MUTED)
	_button(host.content, "查看财务 / 个人注资", host._navigate.bind("operations"), false)
	_filters()
	if not pending_purchase.is_empty():
		_render_purchase_confirmation(data)
	var rows: Array = []
	for value in data.get("players", []):
		var contracted := not str(value.get("seller_id", "")).is_empty()
		var academy: bool = value.get("academy_year") != null or str(value.get("note", "")) in ["academy", "wonder"] or str(value.get("note", "")).contains("青训")
		if (transfer_source == "active" and not contracted) or (transfer_source == "free" and (contracted or academy)) or (transfer_source == "academy" and (contracted or not academy)):
			continue
		if affordable_only and int(value.get("guaranteed_fee", 0)) > int(data.get("transfer_budget", 0)): continue
		if _matches_filter(str(value.get("name", "")) + " " + str(value.get("seller", "")), str(value.get("role", ""))):
			rows.append(value)
	rows.sort_custom(func(a,b):
		var av: float = float(a.get(transfer_sort) if a.get(transfer_sort) != null else -1)
		var bv: float = float(b.get(transfer_sort) if b.get(transfer_sort) != null else -1)
		return av < bv if transfer_sort in ["age","guaranteed_fee"] else av > bv)
	_label(host.content, "%s 位可查看选手" % rows.size(), 13, UI.MUTED)
	for item in _paged(rows):
		var box := UI.card(host.content)
		var row := HBoxContainer.new()
		box.add_child(row)
		row.add_theme_constant_override("separation", 10)
		var player_key := str(item.get("player_id", ""))
		var seller := str(item.get("seller", "自由球员"))
		TeamVisuals.badge(row, seller if not str(item.get("seller_id", "")).is_empty() else "", 30)
		var name_button := _button(row, str(item.get("name", "")), host._load_detail.bind("player", player_key), false)
		UI.transparent(name_button)
		UI.compact(name_button)
		name_button.add_theme_font_size_override("font_size", 18)
		for state in ["font_color", "font_hover_color", "font_focus_color"]: name_button.add_theme_color_override(state, UI.INK)
		Kit.chip(row, str(Phone.ROLES.get(item.get("role", ""), item.get("role", ""))), "green")
		Kit.chip(row, "能力 " + Fmt.score(item.get("ability")), "blue")
		var stars = item.get("potential_stars")
		var potential_label := _label(box, Locale.message("market.predicted_potential_salary" if item.get("potential_estimated", false) else "market.potential_salary", {"stars":"★".repeat(int(stars)) if stars != null else Locale.message("market.unscouted"), "salary":money(item.get("monthly_salary", 0))}), 14, UI.MUTED)
		potential_label.name = "TransferPotential"
		if item.get("potential_estimated", false): potential_label.tooltip_text = Locale.message("market.potential_estimate_help")
		var facts := _label(row, "%s 岁 · %s" % [Fmt.integer(item.get("age")), seller], 14, UI.MUTED)
		facts.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		facts.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		facts.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		facts.autowrap_mode = TextServer.AUTOWRAP_OFF
		var prices := HBoxContainer.new()
		prices.add_theme_constant_override("separation", 12)
		box.add_child(prices)
		var normal = item.get("normal_fee")
		if typeof(normal) in [TYPE_INT, TYPE_FLOAT]:
			var chance := float(item.get("normal_chance", 0))
			var normal_button := _button(prices, "尝试签约 %s · %.0f%%" % [money(normal), chance * 100], _ask_purchase.bind(item, "normal"))
			normal_button.name = "TransferNormal_" + player_key
			normal_button.disabled = not signing_allowed or not str(item.get("blocked", "")).is_empty() or chance <= 0 or int(data.get("club_money", 0)) < int(normal) or replace_id.is_empty()
			_label(box, "谈判未成仅扣 " + money(item.get("negotiation_fee")), 12, UI.MUTED)
		var guarantee := _button(prices, ("买断 " if not str(item.get("seller_id", "")).is_empty() else "100% 保签 ") + money(item.get("guaranteed_fee")), _ask_purchase.bind(item, "guaranteed"))
		guarantee.name = "TransferGuaranteed_" + player_key
		guarantee.disabled = not signing_allowed or not str(item.get("blocked", "")).is_empty() or int(data.get("club_money", 0)) < int(item.get("guaranteed_fee", 0)) or replace_id.is_empty()
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
	replacement.item_selected.connect(func(index: int):
		replace_id = keys[index]
		pending_purchase.clear()
		recruitment.pending.clear()
		host._rebuild())
	host.content.add_child(replacement)

func _filters() -> void:
	if transfer_source != "personal":
		var sorting := HBoxContainer.new()
		host.content.add_child(sorting)
		var order := OptionButton.new()
		UI.dark_options(order)
		var fields := ["ability", "potential", "guaranteed_fee", "age"]
		for caption in ["当前实力优先", "未来潜力优先", "价格从低到高", "年龄从小到大"]: order.add_item(caption)
		order.select(fields.find(transfer_sort))
		order.item_selected.connect(func(i: int): transfer_sort=fields[i]; transfer_page=1; host._rebuild())
		sorting.add_child(order)
		var budget := CheckButton.new()
		budget.text="仅看预算内"
		budget.add_theme_color_override("font_color", UI.INK)
		budget.add_theme_color_override("font_hover_color", UI.GREEN)
		budget.button_pressed=affordable_only
		budget.toggled.connect(func(value: bool): affordable_only=value; transfer_page=1; host._rebuild())
		sorting.add_child(budget)
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
				var salary := int(600 + float(player.get("ability",70))*85)
				_label(box,"能力变化 %+.1f · 签约后预计月结余 %s" % [float(candidate.get("ability",0))-float(player.get("ability",0)),money(int(data.get("monthly_net",0))+salary-int(candidate.get("monthly_salary",0)))],14)
		_label(box, "%s → 入队 · %s → 离队" % [candidate.get("name", ""), replacement], 16)
		_label(box, "俱乐部支出 " + money(pending_purchase.get("fee")) + (" · 不保证谈判成功" if pending_purchase.get("mode") == "normal" else " · 100% 保证签约"), 14)
		if pending_purchase.get("mode") == "normal":
			_label(box, "本次成功率 %.0f%%，失败谈判费 %s。" % [float(candidate.get("normal_chance", 0)) * 100, money(candidate.get("negotiation_fee"))], 14, UI.MUTED)
		var current_fee = candidate.get("normal_fee") if pending_purchase.get("mode") == "normal" else candidate.get("guaranteed_fee")
		var button := _button(box, "确认签约", _confirm_purchase)
		button.name = "ComputerTransferConfirmBuy"
		button.disabled = current_fee != pending_purchase.get("fee") or replacement.is_empty() or not str(candidate.get("blocked", "")).is_empty() or not recruitment.allowed(data, str(pending_purchase.get("replace_id", ""))) or int(data.get("club_money", 0)) < int(current_fee)
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
			var status_text := str({"":"状态未载入", "open":"待决定", "expired":"已过期", "accepted":"已接受", "declined":"已拒绝", "read":"已读"}.get(offer_status, offer_status))
			var offer_button := _button(box, str(offer.get("title", offer.get("team", "入队邀约"))) + " · " + str(offer.get("date", "")) + " · " + status_text, host._open_phone_mail.bind(mail_id), false)
			offer_button.disabled = mail_id.is_empty()
			Kit.rich_row(offer_button, UI, str(offer.get("title", offer.get("team", "入队邀约"))), str(offer.get("date", "")), "", status_text, "amber" if offer_status == "open" else "gray", "mail", str(offer.get("team", "")))
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
		row.add_theme_constant_override("separation", 10)
		box.add_child(row)
		TeamVisuals.badge(row, str(item.get("team", "")), 30)
		var team_button := _button(row, str(item.get("team", "")), host._load_detail.bind("team", str(item.get("team_id", ""))), false)
		UI.transparent(team_button)
		UI.compact(team_button)
		team_button.add_theme_font_size_override("font_size", 18)
		for state in ["font_color", "font_hover_color", "font_focus_color"]: team_button.add_theme_color_override(state, UI.INK)
		Kit.chip(row, str(Phone.ROLES.get(item.get("role", ""), item.get("role", ""))), "green")
		var chance := float(item.get("chance", 0))
		Kit.chip(row, "成功率 %.0f%%" % (chance * 100), "green" if chance >= .5 else ("amber" if chance >= .2 else "red"))
		var terms := _label(row, "接替 %s · 修正 %+d" % [item.get("replace", ""), int(item.get("modifier", 0))], 14, UI.MUTED)
		terms.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		terms.autowrap_mode = TextServer.AUTOWRAP_OFF
		terms.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		var apply := UI.compact(_button(row, "申请试训", _ask_application.bind(item)))
		apply.disabled = not str(item.get("blocked", "")).is_empty()
		if not str(item.get("blocked", "")).is_empty():
			_label(box, str(item["blocked"]), 13, UI.MUTED)
	_pager(rows.size())
	Kit.section(host.content, UI, "转会经历", "", 19)
	for record in data.get("history", []):
		_label(host.content, "%s · %s → %s · %s" % [record.get("date", ""), record.get("old_team", ""), record.get("new_team", ""), Phone.ROLES.get(record.get("transfer_role", ""), record.get("transfer_role", ""))], 14)
	if data.get("history", []).is_empty():
		Kit.empty_state(host.content, UI, "profile", "还没有正式转会", "试训通过并确认加盟后，记录会保存在这里。")

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
	recruitment.finished(path, result)
	if not path.begins_with("/api/3d/transfers/"):
		return
	if result.get("ok", false):
		pending_purchase = {}
		pending_application = {}
