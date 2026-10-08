extends RefCounted
## Native, read-only quotes. The server alone accepts stakes and settles money.
## One row per series: pick the winner on the row, set a stake in the panel
## that opens under it, then confirm in place. "A loses" is the same bet as
## "B wins", so the page only asks who wins and submits outcome "win".
const UI = preload("res://scripts/computer_ui.gd")
const Fmt = preload("res://scripts/ui_format.gd")
const Kit = preload("res://scripts/ui_kit.gd")
const Marks = preload("res://scripts/team_visuals.gd")
const UP := Color("2f6b52")
const DOWN := Color("ad5b52")
const QUICK := [100, 500, 1000, 5000]
var host
var linked := false
var tab := "available"
var page := 1
var loaded := ""
var pending := ""
var revision := -1
var cache: Dictionary = {}
var chosen: Dictionary = {}
var team_id := ""
var outcome := "win"
var amount := ""
var confirm: Dictionary = {}
var confirmation_button: Button
var summary_label: Label
var order_button: Button
var last_summary: Dictionary = {}
var summary_owner := ""

func observe() -> void:
	var current: Dictionary = CareerBridge.context.get("prediction_summary", {})
	var owner := str(CareerBridge.context.get("player", {}).get("id", ""))
	if summary_owner == owner and not last_summary.is_empty() and int(current.get("count", 0)) > int(last_summary.get("count", 0)):
		Computer.show_action_feedback(tr2("%d 场竞猜已结算 · 返还 %s", "%d predictions settled · Returned %s") % [int(current.count) - int(last_summary.count), Fmt.money(int(current.returned) - int(last_summary.returned))], "success", 6.0)
	last_summary = current.duplicate()
	summary_owner = owner

static func tr2(zh: String, en: String) -> String:
	return en if Locale.language == "en" else zh

static func page_title() -> String:
	return tr2("赛事竞猜", "Match predictions")

# --- small builders ---------------------------------------------------------

func text(parent: Node, value: String, size: int = 15, color: Color = UI.INK) -> Label:
	return host._label(parent, value, size, color)

## Single-line label; trimmed ones give up their minimum width, so labels that
## must stay readable inside a row pass trim = false.
func line(parent: Node, value: String, size: int = 14, color: Color = UI.INK, trim: bool = true) -> Label:
	var node := text(parent, value, size, color)
	node.autowrap_mode = TextServer.AUTOWRAP_OFF
	node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if trim: node.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	return node

func button(parent: Node, value: String, action: Callable, write: bool = false) -> Button:
	return host._button(parent, value, action, write)

func small(parent: Node, value: String, action: Callable, write: bool = false) -> Button:
	var node := UI.compact(button(parent, value, action, write))
	node.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	return node

func row(parent: Node, gap: int = 8) -> HBoxContainer:
	var node := HBoxContainer.new()
	node.add_theme_constant_override("separation", gap)
	parent.add_child(node)
	return node

func card(parent: Node, border: Color = UI.LINE, fill: Color = UI.PAPER, padding: int = 14) -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.add_theme_stylebox_override("panel", UI.style(fill, padding, 12, border))
	parent.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 8)
	panel.add_child(box)
	return box

func spacer(parent: Node) -> void:
	var gap := Control.new()
	gap.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	gap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(gap)

func money() -> int:
	return int(cache.get("money", CareerBridge.context.get("personal_money", 0)))

static func odds_text(hundredths) -> String:
	return "×%.2f" % (float(hundredths) / 100.0)

static func short_date(value: String) -> String:
	return Kit.short_date(value) if value.length() >= 10 else value

# --- page -------------------------------------------------------------------

func render(owner) -> void:
	host = owner
	host.match_center.pace.pause(false)
	if not linked:
		CareerBridge.command_finished.connect(finished)
		linked = true
	summary_label = null
	order_button = null
	confirmation_button = null
	var head := row(host.content, 10)
	head.name = "PredictionHeader"
	small(head, tr2("‹ 赛事中心", "‹ Events"), host._events_tab.bind("calendar")).name = "PredictionBack"
	var choices := [{"id":"available", "label":tr2("可参与", "Available")}, {"id":"records", "label":tr2("我的记录", "My predictions")}]
	host._tabs(head, choices, tab, switch_tab)
	var caption := line(head, tr2("个人余额", "Personal balance"), 13, UI.MUTED, false)
	caption.size_flags_horizontal = Control.SIZE_SHRINK_END
	caption.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var wallet := line(head, Fmt.money(CareerBridge.context.get("personal_money", money())), 19, UI.INK, false)
	wallet.name = "PredictionBalance"
	wallet.size_flags_horizontal = Control.SIZE_SHRINK_END
	wallet.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	line(host.content, tr2("只能猜其他队伍的正式 BO · 返还金额包含本金 · 确认后不能撤销", "Other teams' official series only · Returns include the stake · Confirmed stakes cannot be cancelled"), 12, UI.MUTED)
	var path := "/api/3d/predictions?view=%s&page=%d" % [tab, page]
	var current := int(CareerBridge.context.get("calendar", {}).get("revision", 0))
	if loaded != path or revision != current:
		if pending != path:
			pending = path
			CareerBridge._send(path, {}, false)
		text(host.content, tr2("正在读取对阵…", "Loading fixtures…"), 14, UI.MUTED)
		return
	if cache.has("error"):
		text(host.content, str(cache.error))
		small(host.content, tr2("重试", "Retry"), refresh)
		return
	if tab == "available": available()
	else: records()
	pager()

func available() -> void:
	var rows: Array = cache.get("rows", [])
	var bar := row(host.content, 10)
	line(bar, tr2("共 %d 场可竞猜", "%d series open") % int(cache.get("total", rows.size())), 13, UI.MUTED).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var advance_button := small(bar, tr2("推进到下一批对阵 ›", "Advance to next fixtures ›"), advance, true)
	advance_button.name = "PredictionAdvance"
	advance_button.tooltip_text = tr2("会推进游戏日期，停在赛前；重要事件和你的比赛仍优先。", "Advances the game date and stops before play. Important events and your matches take priority.")
	if rows.is_empty():
		Kit.empty_state(host.content, UI, "calendar", tr2("现在没有可竞猜的对阵", "No series open for predictions"), tr2("推进到下一批对阵，或等赛事开赛后再来。推进会停在赛前。", "Advance to the next fixtures, or come back once events are live. Advancing stops before play."))
		return
	var list := VBoxContainer.new()
	list.name = "PredictionFixtures"
	list.add_theme_constant_override("separation", 8)
	host.content.add_child(list)
	for item in rows: fixture(list, item)

## Lower odds means the market expects that team to win.
static func favourite(item: Dictionary) -> String:
	var a := int(item.odds_hundredths.get(str(item.team_a.id), 0))
	var b := int(item.odds_hundredths.get(str(item.team_b.id), 0))
	if a == b: return ""
	return str(item.team_a.id) if a < b else str(item.team_b.id)

func fixture(list: Node, item: Dictionary) -> void:
	var open: bool = not chosen.is_empty() and str(chosen.get("key", "")) == str(item.key)
	var box := card(list, UI.GREEN if open else UI.LINE, UI.PAPER, 12)
	box.get_parent().name = "PredictionFixture"
	var meta := row(box, 8)
	line(meta, "%s · %s · BO%d" % [str(item.event_name), short_date(str(item.date)), int(item.best_of)], 12, UI.MUTED).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var picks := row(box, 10)
	var hot := favourite(item)
	pick(picks, item, item.team_a, hot, open).name = "PredictionChoose"
	var versus := line(picks, "vs", 13, UI.MUTED, false)
	versus.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	versus.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	pick(picks, item, item.team_b, hot, open).name = "PredictionChooseB"
	if open: stake_panel(box, item)

func pick(parent: Node, item: Dictionary, team: Dictionary, hot: String, open: bool) -> Button:
	var id := str(team.id)
	var picked := open and team_id == id
	var node := Button.new()
	node.focus_mode = Control.FOCUS_ALL
	node.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	node.custom_minimum_size.y = 54
	node.tooltip_text = tr2("押 %s 胜", "Back %s to win") % str(team.name)
	var normal := UI.style(UI.MINT if picked else Color("f7f5ee"), 10, 10, UI.GREEN if picked else UI.LINE)
	if picked: normal.set_border_width_all(2)
	node.add_theme_stylebox_override("normal", normal)
	node.add_theme_stylebox_override("hover", UI.style(Color("eaf1e6"), 10, 10, Color("9eb19c")))
	node.add_theme_stylebox_override("pressed", UI.style(UI.MINT, 10, 10, UI.GREEN))
	node.add_theme_stylebox_override("hover_pressed", UI.style(UI.MINT, 10, 10, UI.GREEN))
	node.add_theme_stylebox_override("focus", UI.style(Color.TRANSPARENT, 0, 10, UI.GREEN))
	node.pressed.connect(choose_team.bind(item, id))
	parent.add_child(node)
	var inside := HBoxContainer.new()
	inside.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	inside.offset_left = 12; inside.offset_right = -14
	inside.add_theme_constant_override("separation", 10)
	inside.mouse_filter = Control.MOUSE_FILTER_IGNORE
	node.add_child(inside)
	var badge = Marks.badge(inside, str(team.name), 30)
	if badge is Control: badge.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var words := VBoxContainer.new()
	words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	words.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	words.add_theme_constant_override("separation", 0)
	inside.add_child(words)
	line(words, str(team.name), 15)
	line(words, tr2("押它胜", "To win") if not picked else tr2("已选 · 押它胜", "Selected · to win"), 11, UI.GREEN if picked else UI.MUTED)
	if id == hot: Kit.chip(inside, tr2("热门", "Favourite"), "amber", 11)
	var price := line(inside, odds_text(item.odds_hundredths[id]), 19, UI.GREEN if picked else UI.INK, false)
	price.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	price.size_flags_horizontal = Control.SIZE_SHRINK_END
	for child in node.find_children("*", "Control", true, false): child.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return node

func stake_panel(box: Node, item: Dictionary) -> void:
	var rule := ColorRect.new()
	rule.color = UI.LINE
	rule.custom_minimum_size.y = 1
	box.add_child(rule)
	var names := {str(item.team_a.id):str(item.team_a.name), str(item.team_b.id):str(item.team_b.name)}
	var head := row(box, 8)
	line(head, tr2("押 %s 胜 · 赔率 %s", "Backing %s to win · odds %s") % [str(names.get(team_id, "")), odds_text(item.odds_hundredths[team_id])], 15).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	small(head, tr2("收起", "Close"), clear_selection).name = "PredictionClose"
	var inputs := row(box, 8)
	var entry := LineEdit.new()
	entry.name = "PredictionStake"
	UI.line_edit(entry)
	entry.custom_minimum_size.x = 190
	entry.placeholder_text = tr2("投入金额（个人资金）", "Stake (personal funds)")
	entry.text = amount
	entry.text_changed.connect(stake_changed)
	entry.text_submitted.connect(func(_value: String): review())
	inputs.add_child(entry)
	var wallet := money()
	for value in QUICK:
		if value <= wallet: small(inputs, Fmt.money(value), set_amount.bind(value)).name = "PredictionQuick"
	if wallet >= 20: small(inputs, tr2("余额 10%", "10% of balance"), set_amount.bind(wallet / 10)).name = "PredictionQuick"
	spacer(inputs)
	order_button = small(inputs, tr2("下单", "Place prediction"), review)
	order_button.name = "PredictionReview"
	UI.primary(order_button)
	summary_label = line(box, "", 13, UI.MUTED, false)
	summary_label.name = "PredictionSummary"
	summary_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	refresh_summary()
	if not confirm.is_empty(): confirm_bar(box, names)

## Live outcome preview; updates labels in place so typing keeps focus.
func refresh_summary() -> void:
	if not is_instance_valid(summary_label) or chosen.is_empty(): return
	var wallet := money()
	var stake := int(amount) if amount.is_valid_int() else 0
	var valid := stake > 0 and stake <= wallet
	if is_instance_valid(order_button): order_button.disabled = not valid or not confirm.is_empty()
	if amount.strip_edges().is_empty():
		summary_label.text = tr2("输入金额或点快捷金额，这里会显示猜中能拿回多少。", "Enter a stake or pick a quick amount to see the return.")
		summary_label.add_theme_color_override("font_color", UI.MUTED)
	elif not valid:
		summary_label.text = tr2("请输入 1 到 %s 之间的整数金额。", "Enter a whole amount from 1 to %s.") % Fmt.money(wallet)
		summary_label.add_theme_color_override("font_color", DOWN)
	else:
		var total := stake * int(chosen.odds_hundredths[team_id]) / 100
		summary_label.text = tr2("猜中返还 %s（净赚 %s）· 猜错损失 %s · 买后余额 %s", "Win: return %s (profit %s) · Lose: %s · Balance after %s") % [Fmt.money(total), Fmt.money(total - stake), Fmt.money(stake), Fmt.money(wallet - stake)]
		summary_label.add_theme_color_override("font_color", UI.INK)

func stake_changed(value: String) -> void:
	amount = value.strip_edges()
	if not confirm.is_empty():
		confirm.clear()
		host._rebuild()
		return
	refresh_summary()

func set_amount(value: int) -> void:
	amount = str(value)
	confirm.clear()
	host._rebuild()

func confirm_bar(parent: Node, names: Dictionary) -> void:
	var box := card(parent, UI.AMBER, Color("fbf4e4"), 12)
	box.get_parent().name = "PredictionConfirmation"
	text(box, tr2("押 %s 胜，投入 %s。猜中返还 %s（净赚 %s），猜错损失 %s，确认后余额 %s。确认后不能撤销。", "Back %s to win with %s. Win: return %s (profit %s). Lose: %s. Balance after %s. This cannot be cancelled.") % [str(names.get(team_id, "")), Fmt.money(confirm.stake), Fmt.money(confirm.total), Fmt.money(confirm.total - confirm.stake), Fmt.money(confirm.stake), Fmt.money(money() - int(confirm.stake))], 14)
	var actions := row(box, 8)
	spacer(actions)
	small(actions, tr2("再想想", "Not yet"), func(): confirm.clear(); host._rebuild())
	confirmation_button = small(actions, tr2("确认竞猜", "Confirm prediction"), submit, true)
	confirmation_button.name = "PredictionConfirm"
	UI.primary(confirmation_button)

# --- records ----------------------------------------------------------------

## Settlement reasons are saved in Chinese by the server (also used in the
## cash-flow log); show them in the current language.
static func reason_text(reason: String) -> String:
	match reason:
		"竞猜命中": return tr2("竞猜命中", "Won")
		"竞猜未命中": return tr2("竞猜未命中", "Lost")
		"比赛取消、轮空或判罚弃权": return tr2("比赛取消、轮空或判罚弃权", "Cancelled match, bye or administrative forfeit")
		"你已加入参赛队伍": return tr2("你已加入参赛队伍", "You joined a participating team")
		"参赛队伍发生变化": return tr2("参赛队伍发生变化", "The participating teams changed")
	return reason

static func status_look(status: String) -> Array:
	match status:
		"pending": return [tr2("等待赛果", "Awaiting result"), "blue"]
		"won": return [tr2("命中", "Won"), "green"]
		"lost": return [tr2("未命中", "Lost"), "red"]
		"refunded": return [tr2("已退回", "Refunded"), "gray"]
	return [status, "gray"]

func records() -> void:
	var rows: Array = cache.get("rows", [])
	var settled: Dictionary = CareerBridge.context.get("prediction_summary", {})
	var waiting := rows.filter(func(o): return str(o.get("status", "")) == "pending")
	var tiles := row(host.content, 8)
	tiles.name = "PredictionTotals"
	Kit.stat_tile(tiles, UI, tr2("已结算", "Settled"), str(int(settled.get("count", 0))))
	Kit.stat_tile(tiles, UI, tr2("累计返还", "Total returned"), Fmt.money(settled.get("returned", 0)))
	var staked := 0
	for order in waiting: staked += int(order.get("stake", 0))
	Kit.stat_tile(tiles, UI, tr2("本页等待赛果", "Awaiting on this page"), str(waiting.size()), tr2("投入 %s", "Staked %s") % Fmt.money(staked) if not waiting.is_empty() else "")
	if rows.is_empty():
		Kit.empty_state(host.content, UI, "clipboard", tr2("还没有竞猜记录", "No predictions yet"), tr2("在「可参与」里选一场其他队伍的比赛试试。", "Pick another team's series under Available."))
		return
	var list := VBoxContainer.new()
	list.name = "PredictionRecords"
	list.add_theme_constant_override("separation", 8)
	host.content.add_child(list)
	for order in rows: record(list, order)

func record(list: Node, item: Dictionary) -> void:
	var status := str(item.get("status", ""))
	var look: Array = status_look(status)
	var box := card(list, UI.LINE, UI.PAPER, 12)
	box.get_parent().name = "PredictionRecord"
	var names := {str(item.team_a.id):str(item.team_a.name), str(item.team_b.id):str(item.team_b.name)}
	var top := row(box, 10)
	Kit.chip(top, str(look[0]), str(look[1]), 12)
	line(top, "%s vs %s" % [str(item.team_a.name), str(item.team_b.name)], 16).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var stake := int(item.get("stake", 0))
	var result := ""
	var colour := UI.INK
	match status:
		"pending": result = tr2("可返还 %s", "Returns %s") % Fmt.money(item.get("possible_return", 0))
		"won": result = Fmt.money(int(item.get("payout", 0)) - stake, true); colour = UP
		"lost": result = Fmt.money(-stake, true); colour = DOWN
		"refunded": result = tr2("退回 %s", "Refunded %s") % Fmt.money(item.get("payout", stake)); colour = UI.MUTED
	line(top, result, 18, colour, false).size_flags_horizontal = Control.SIZE_SHRINK_END
	var second := row(box, 10)
	var facts: Array[String] = [tr2("押 %s 胜", "Backed %s") % str(names.get(str(item.get("predicted_winner_id", "")), "")), tr2("投入 %s", "Stake %s") % Fmt.money(stake), odds_text(item.get("locked_odds", 0))]
	if status == "won": facts.append(tr2("返还 %s", "Returned %s") % Fmt.money(item.get("payout", 0)))
	if not str(item.get("series", "")).is_empty(): facts.append(tr2("比分 %s", "Score %s") % str(item.series))
	line(second, " · ".join(facts), 13).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	if item.get("report_available", false):
		small(second, tr2("战报 ›", "Report ›"), host._load_detail.bind("match", "%s::%s" % [item.year, item.match_id])).name = "PredictionReport"
	var where: Array[String] = [str(item.get("event_name", "")), short_date(str(item.get("date", ""))), "BO%d" % int(item.get("best_of", 3))]
	if status == "refunded" and not str(item.get("reason", "")).is_empty(): where.append(reason_text(str(item.reason)))
	line(box, " · ".join(where), 12, UI.MUTED)

# --- paging and commands ----------------------------------------------------

func pager() -> void:
	var size := maxi(1, int(cache.get("page_size", 12)))
	var pages := maxi(1, ceili(float(cache.get("total", 0)) / size))
	if pages <= 1: return
	var bar := row(host.content, 8)
	bar.alignment = BoxContainer.ALIGNMENT_CENTER
	small(bar, tr2("‹ 上一页", "‹ Previous"), move_page.bind(-1)).disabled = page <= 1
	var where := line(bar, "%d / %d" % [page, pages], 14, UI.MUTED, false)
	where.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	where.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	small(bar, tr2("下一页 ›", "Next ›"), move_page.bind(1)).disabled = page >= pages

## Kept for callers that still open the old purchase view.
func purchase() -> void:
	if chosen.is_empty(): return
	var list := VBoxContainer.new()
	host.content.add_child(list)
	fixture(list, chosen)

func review() -> void:
	if chosen.is_empty(): return
	if not amount.is_valid_int() or int(amount) <= 0 or int(amount) > money():
		host.action_feedback.show_message(tr2("请输入不超过个人余额的正整数金额。", "Enter a positive whole amount within your personal balance."), "error")
		return
	var stake := int(amount)
	confirm = {"stake":stake, "total":stake * int(chosen.odds_hundredths[team_id]) / 100}
	host._rebuild()
	call_deferred("show_confirmation")

func show_confirmation() -> void:
	await host.get_tree().process_frame
	await host.get_tree().process_frame
	await host.get_tree().process_frame
	if not is_instance_valid(confirmation_button) or not confirmation_button.is_inside_tree(): return
	# Bring the whole confirmation bar, not just its button edge, into view.
	var target: Control = confirmation_button.get_parent().get_parent().get_parent()
	var view: Rect2 = host.scroll.get_global_rect()
	var bottom: float = target.get_global_rect().end.y + 12.0
	if bottom > view.end.y: host.scroll.scroll_vertical += int(ceil(bottom - view.end.y))

func submit() -> void:
	if confirm.is_empty() or chosen.is_empty(): return
	# Backing a team to win; the server derives the predicted winner from it.
	host._command("/api/3d/predictions/buy", {"key":chosen.key, "quote_id":chosen.quote_id, "team_id":team_id, "outcome":"win", "stake":int(confirm.stake), "revision":int(CareerBridge.context.get("calendar", {}).get("revision", 0))})

func advance() -> void:
	host._command("/api/3d/predictions/advance", {"revision":int(CareerBridge.context.get("calendar", {}).get("revision", 0))})

func choose_team(item: Dictionary, id: String) -> void:
	if chosen.is_empty() or str(chosen.get("key", "")) != str(item.key):
		chosen = item.duplicate(true)
		amount = ""
	team_id = id
	outcome = "win"
	confirm.clear()
	host._rebuild()

func select(item: Dictionary) -> void:
	chosen = item.duplicate(true)
	team_id = str(item.team_a.id)
	outcome = "win"
	amount = ""
	confirm.clear()
	host._rebuild()

func clear_selection() -> void:
	chosen.clear()
	confirm.clear()
	host._rebuild()

func set_team(value: String) -> void:
	team_id = value
	confirm.clear()
	host._rebuild()

## Compatibility: "lose" on the selected team means backing the other side.
func set_outcome(value: String) -> void:
	if value == "lose" and not chosen.is_empty():
		team_id = str(chosen.team_b.id) if team_id == str(chosen.team_a.id) else str(chosen.team_a.id)
	outcome = "win"
	confirm.clear()
	host._rebuild()

func switch_tab(value: String) -> void:
	tab = value
	page = 1
	chosen.clear()
	confirm.clear()
	refresh()

func move_page(step: int) -> void:
	page = maxi(1, page + step)
	chosen.clear()
	confirm.clear()
	host.page_scroll[host.active_page] = 0
	refresh()

func refresh() -> void:
	loaded = ""
	host._rebuild()

func finished(path: String, result: Dictionary) -> void:
	if path == pending:
		pending = ""
		loaded = path
		revision = int(result.get("state_revision", CareerBridge.context.get("calendar", {}).get("revision", 0)))
		cache = result.get("predictions", {}) if result.get("ok", false) else {"error":result.get("msg", "")}
	elif path.begins_with("/api/3d/predictions/"):
		loaded = ""
		confirm.clear()
		if result.get("ok", false):
			chosen.clear()
			amount = ""
			if path.ends_with("/buy"): tab = "records"; page = 1
	else:
		return
	if is_instance_valid(host) and host.active_page == "events" and host.events_tab == "predictions": host._rebuild()
