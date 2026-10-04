extends RefCounted
## A local roster draft. Arena alone creates/configures the shared saved room.
const UI = preload("res://scripts/computer_ui.gd")
const RTSMaps = preload("res://rts/scripts/map_catalog.gd")
const PREFIX := "/api/3d/custom/"
const ROLES := {"awp":"主狙", "entry":"突破", "lurk":"自由人", "igl":"指挥", "rifle":"步枪手"}
var host
var a: Array[String] = []
var b: Array[String] = []
var players: Dictionary = {}
var map_code := "dust2"
var ct := "a"
var human_id := ""
var bound_room := ""
var bound_phase := ""
var dirty := false
var search := ""
var search_draft := ""
var page := 1
var catalog: Dictionary = {}
var catalog_path := ""
var pending_catalog := ""
var request_catalog := false
var catalog_failed := false
var pending_action := ""
var pending_status := false
var status: Dictionary = {}
var poll_timer := 0.0
var notice := ""
var refresh_needed := false
var cancel_confirm := ""
var replaced_finished_room := ""
var uncertain := false
var request_status := false
var command_sender: Callable

func attach(owner) -> void:
	host = owner

func state() -> Dictionary:
	var value = CareerBridge.context.get("custom", {})
	return value if value is Dictionary else {}

func lobby() -> Dictionary:
	var value = state().get("lobby")
	return value if value is Dictionary and value.get("mode") == "custom" else {}

func revision() -> int:
	return int(state().get("revision", CareerBridge.context.get("ladder", {}).get("revision", 0)))

func reset() -> void:
	a.clear(); b.clear(); players.clear(); catalog.clear(); status.clear()
	map_code = "dust2"; ct = "a"; human_id = ""; bound_room = ""; bound_phase = ""
	dirty = false; search = ""; search_draft = ""; page = 1
	catalog_path = ""; pending_catalog = ""; request_catalog = false; catalog_failed = false
	pending_action = ""; pending_status = false; poll_timer = 0.0
	notice = ""; refresh_needed = false; cancel_confirm = ""; replaced_finished_room = ""; uncertain = false; request_status = false

func _strings(values: Array) -> Array[String]:
	var out: Array[String] = []
	for value in values: out.append(str(value))
	return out

func _adopt(room: Dictionary) -> void:
	bound_room = str(room.get("id", ""))
	bound_phase = str(room.get("phase", ""))
	a = _strings(room.get("a", [])); b = _strings(room.get("b", []))
	players.merge(room.get("roster", {}), true)
	map_code = str(room.get("map", "dust2"))
	ct = str(room.get("ct", "a")); human_id = str(room.get("human_id", ""))
	dirty = false; cancel_confirm = ""

func context_changed() -> void:
	var room := lobby()
	if room.is_empty() and not bound_room.is_empty():
		a.clear(); b.clear(); human_id = ""; bound_room = ""; bound_phase = ""; dirty = false; status.clear(); cancel_confirm = ""
	var saved_settings_changed: bool = not room.is_empty() and (map_code != str(room.get("map", "dust2")) or ct != str(room.get("ct", "a")) or human_id != str(room.get("human_id", "")))
	if not room.is_empty() and (str(room.get("id", "")) != bound_room or str(room.get("phase", "")) != bound_phase or (not dirty and saved_settings_changed)) and not (room.get("phase") == "finished" and str(room.get("id", "")) == replaced_finished_room):
		_adopt(room)
		replaced_finished_room = ""
		status.clear()
		poll_timer = 0.0
	var connection = state().get("connection")
	if connection is Dictionary: status = connection.duplicate(true)

func foreign_room() -> Dictionary:
	var shared = state().get("shared_lobby")
	if not shared is Dictionary:
		shared = CareerBridge.context.get("ladder", {}).get("lobby")
	if shared is Dictionary and shared.get("mode") != "custom" and shared.get("phase") != "finished":
		return shared
	return {}

func _catalog_query() -> String:
	return PREFIX + "catalog?page=%d&page_size=8&search=%s" % [page, search.uri_encode()]

func _repaint(top: bool = false) -> void:
	if not host.screen.visible or host.active_page != "custom": return
	var focused = host.get_viewport().gui_get_focus_owner()
	if focused is LineEdit or focused is TextEdit:
		refresh_needed = true
		return
	host.page_scroll["custom"] = 0 if top else host.scroll.scroll_vertical
	host._rebuild()

func fetch_catalog() -> void:
	request_catalog = true
	catalog_failed = false
	catalog_path = _catalog_query()

func retry_catalog() -> void:
	fetch_catalog(); _repaint()

func search_players(_submitted: String = "") -> void:
	search = search_draft.strip_edges(); page = 1
	var focused = host.get_viewport().gui_get_focus_owner()
	if focused is LineEdit: focused.release_focus()
	fetch_catalog()
	_repaint(true)

func change_page(next_page: int) -> void:
	page = maxi(1, next_page)
	fetch_catalog()
	_repaint()

func process(delta: float) -> void:
	if not host.screen.visible or host.active_page != "custom": return
	var focused = host.get_viewport().gui_get_focus_owner()
	if refresh_needed and not focused is LineEdit and not focused is TextEdit:
		refresh_needed = false
		_repaint()
	if not CareerBridge.connected or CareerBridge.busy: return
	if request_catalog and pending_catalog.is_empty():
		pending_catalog = catalog_path
		request_catalog = false
		if not CareerBridge._send(pending_catalog, {}, false):
			pending_catalog = ""
			catalog_failed = true
			notice = "选手资料暂未读到，请重新搜索。"
			_repaint()
		return
	var room := lobby()
	poll_timer -= maxf(0, delta)
	if (request_status or (not room.is_empty() and (status.is_empty() or room.get("phase") in ["starting", "playing", "waiting", "started", "launched", "live"]) and poll_timer <= 0)) and not pending_status:
		pending_status = CareerBridge._send(PREFIX + "status", {}, false)
		request_status = false
		poll_timer = 2.5

func _player_name(id: String) -> String:
	return str(players.get(id, {}).get("name", id))

func add_player(side: String, id: String) -> void:
	if not lobby().is_empty() and lobby().get("phase") != "finished": return
	if id in a or id in b or not players.has(id): return
	var team: Array[String] = a if side == "a" else b
	if team.size() >= 5:
		notice = "%s 队已满五人。" % side.to_upper()
		_repaint(); return
	team.append(id)
	dirty = true; notice = "已把 %s 加入 %s 队。" % [_player_name(id), side.to_upper()]
	_repaint()

func remove_player(side: String, id: String) -> void:
	if not lobby().is_empty() and lobby().get("phase") != "finished": return
	var team: Array[String] = a if side == "a" else b
	team.erase(id)
	if human_id == id: human_id = ""
	dirty = true; notice = ""
	_repaint()

func _recommend(result: Dictionary) -> void:
	for row in result.get("rows", []): players[str(row.get("player_id", ""))] = row.duplicate(true)
	for value in result.get("players", []):
		var id := str(value)
		if id in a or id in b or not players.has(id): continue
		if a.size() < 5: a.append(id)
		elif b.size() < 5: b.append(id)
		else: break
	dirty = true
	if a.size() < 5 or b.size() < 5: notice = "推荐未填满空位，请再推荐或手动补齐。"

func command(action: String) -> bool:
	if uncertain:
		notice = "上一项结果未知，请先刷新房间状态。"; request_status = true; _repaint(); return false
	if not pending_action.is_empty():
		notice = "正在处理上一项操作，请稍候。"; _repaint(); return false
	var body: Dictionary = {"revision":revision()}
	var room := lobby()
	match action:
		"recommend": body = {"human_id":human_id}
		"create":
			if not foreign_room().is_empty() or a.size() != 5 or b.size() != 5:
				notice = "请先结束其他房间，并为双方各选择五名不同选手。"; _repaint(); return false
			body.merge({"players":a + b, "human_id":human_id, "map":map_code, "ct":ct})
		"configure": body.merge({"lobby_id":room.get("id", ""), "human_id":human_id, "map":map_code, "ct":ct})
		_: body["lobby_id"] = room.get("id", "")
	if action in ["simulate", "launch"] and dirty:
		notice = "地图或控制角色尚未保存，请先保存设置。"; _repaint(); return false
	pending_action = action
	notice = ""
	var accepted: bool = bool(command_sender.call(PREFIX + action, body.duplicate(true))) if command_sender.is_valid() else CareerBridge.command(PREFIX + action, body)
	if not accepted:
		pending_action = ""
		notice = "操作暂未发出，请等当前操作完成后重试。"
		_repaint(); return false
	return true

func received(path: String, result: Dictionary) -> bool:
	if not path.begins_with(PREFIX): return false
	var should_repaint := true
	if path.begins_with(PREFIX + "catalog"):
		if path == pending_catalog: pending_catalog = ""
		if path == catalog_path:
			if result.get("ok", false):
				catalog_failed = false
				catalog = result.duplicate(true)
				for row in catalog.get("rows", []): players[str(row.get("player_id", ""))] = row.duplicate(true)
			else:
				catalog_failed = true
				notice = str(result.get("reason", result.get("msg", "选手资料读取失败。")))
	elif path == PREFIX + "status":
		pending_status = false
		if result.get("ok", false):
			var next_status: Dictionary = result.get("connection", result).duplicate(true)
			should_repaint = JSON.stringify(status) != JSON.stringify(next_status) or uncertain
			status = next_status
			if uncertain: notice = "房间状态已刷新，请确认后手动继续。"
			uncertain = false
		else: notice = str(result.get("reason", result.get("msg", "房间状态读取失败。")))
	else:
		var action := path.trim_prefix(PREFIX)
		if action == pending_action: pending_action = ""
		notice = str(result.get("reason", result.get("msg", "")))
		if result.get("connection") is Dictionary: status = result["connection"].duplicate(true)
		if result.get("ok", false):
			if action == "recommend": _recommend(result)
			elif action in ["create", "configure"]: _adopt(lobby())
			elif action == "cancel":
				a.clear(); b.clear(); bound_room = ""; bound_phase = ""; human_id = ""; dirty = false; cancel_confirm = ""; status.clear()
			if result.get("result") is Dictionary and not result["result"].is_empty():
				host.report = result["result"].duplicate(true)
				host.page_reports["custom"] = host.report
				host.page_scroll["custom"] = 0
		else:
			if result.get("outcome_unknown", false):
				uncertain = true; request_status = true; status.clear()
				notice += " 结果未知，先刷新房间状态；不会自动重试。"
			if notice.is_empty(): notice = "操作未完成，请检查房间状态后重试。"
	context_changed()
	if should_repaint: _repaint(not host.report.is_empty())
	return true

func _button(parent: Node, text: String, callback: Callable, name_text: String, locked: bool = false, write: bool = true) -> Button:
	var button: Button = host._button(parent, text, callback, write)
	button.name = name_text; button.disabled = locked
	return button

func _option(parent: Node, name_text: String, entries: Array, current: String, changed: Callable, locked: bool) -> OptionButton:
	var option := OptionButton.new()
	option.name = name_text; option.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	UI.dark_options(option)
	for index in range(entries.size()):
		option.add_item(str(entries[index][1])); option.set_item_metadata(index, str(entries[index][0]))
		if str(entries[index][0]) == current: option.select(index)
	option.disabled = locked
	option.set_meta("custom_domain_locked", locked)
	parent.add_child(option)
	option.item_selected.connect(func(index: int): changed.call(str(option.get_item_metadata(index))))
	return option

func _set_map(value: String) -> void:
	map_code = value; dirty = true; _repaint()

func _set_ct(value: String) -> void:
	ct = value; dirty = true; _repaint()

func _set_human(value: String) -> void:
	human_id = value; dirty = true; _repaint()

func _settings(parent: Node, locked: bool) -> void:
	var row := HBoxContainer.new(); row.add_theme_constant_override("separation", 10); parent.add_child(row)
	var maps: Array = []
	for value in state().get("maps", catalog.get("maps", ["dust2"])): maps.append([str(value), str(value).capitalize()])
	_option(row, "CustomMap", maps, map_code, _set_map, locked)
	_option(row, "CustomCT", [["a", "A 队开场 CT"], ["b", "B 队开场 CT"]], ct, _set_ct, locked)
	var controls: Array = [["", "观察者 · 十名 BOT"]]
	for id in a + b: controls.append([id, "控制 " + _player_name(id)])
	_option(row, "CustomControl", controls, human_id, _set_human, locked)

func _teams(parent: Node, editable: bool) -> void:
	var row := HBoxContainer.new(); row.add_theme_constant_override("separation", 10); parent.add_child(row)
	for side in ["a", "b"]:
		var card := UI.card(row); card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var team: Array = a if side == "a" else b
		host._label(card, "%s 队 · %d / 5" % [str(side).to_upper(), team.size()], 16, UI.GREEN)
		for index in range(5):
			var line := HBoxContainer.new(); line.add_theme_constant_override("separation", 5); card.add_child(line)
			if index >= team.size(): host._label(line, "%d · 等待选手" % (index + 1), 12, UI.MUTED); continue
			var id: String = team[index]
			var player: Dictionary = players.get(id, {})
			var label: Label = host._label(line, _player_name(id) + (" · 你" if human_id == id else "") + " · " + str(ROLES.get(player.get("role", ""), player.get("role", ""))), 12)
			label.name = "CustomMember_" + id; label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			if editable: UI.compact(_button(line, "移除", remove_player.bind(side, id), "CustomRemove_" + id))

func _cancel_request() -> void:
	cancel_confirm = str(lobby().get("id", "")); _repaint()

func _cancel_dismiss() -> void:
	cancel_confirm = ""; _repaint()

func _cancel_confirm() -> void:
	if cancel_confirm == str(lobby().get("id", "")): command("cancel")

func refresh_status() -> void:
	request_status = true; poll_timer = 0

func _new_draft() -> void:
	replaced_finished_room = str(lobby().get("id", ""))
	a.clear(); b.clear(); bound_room = ""; bound_phase = ""; human_id = ""; dirty = false; status.clear()
	host.report.clear(); host.page_reports["custom"] = {}; _repaint(true)

func busy_changed(value: bool) -> void:
	if host.active_page != "custom": return
	var locked: bool = value and CareerBridge.active_post
	for option in host.content.find_children("*", "OptionButton", true, false):
		if option.has_meta("custom_domain_locked"): option.disabled = locked or bool(option.get_meta("custom_domain_locked"))
	var field = host.content.find_child("CustomSearch", true, false)
	if field is LineEdit: field.editable = not locked

func render(parent: Node) -> void:
	context_changed()
	if not host.report.is_empty(): host._render_report(host.report); return
	host._label(parent, "自定义对局 · 战术验证", 20)
	host._label(parent, "双方各五名选手，位置由原对局系统自动分配；不改变天梯积分或生涯身份。", 12, UI.MUTED)
	if not notice.is_empty(): host._label(parent, notice, 13, UI.GREEN)
	if not pending_action.is_empty(): host._label(parent, "正在处理操作…", 12, UI.MUTED)
	var room := lobby()
	var foreign := foreign_room()
	if not foreign.is_empty():
		host._label(parent, "另一场天梯 / FPL 房间尚未结束，自定义对局暂不可创建。", 15)
		_button(parent, "查看现有天梯房间", host._navigate.bind("ladder"), "CustomForeignRoom", false, false)
		return
	if not room.is_empty() and room.get("phase") == "finished" and not bound_room.is_empty():
		var saved: Dictionary = room.get("result", {})
		if not saved.is_empty(): _button(parent, "查看本场自定义战报", host._open_report.bind(saved), "CustomSavedReport", false, false)
		_button(parent, "重新选择十人", _new_draft, "CustomNewDraft", false, false)
		if not bound_room.is_empty(): return
	var editable: bool = room.is_empty() or (room.get("phase") == "finished" and bound_room.is_empty())
	var ready: bool = not editable and room.get("phase") == "ready"
	_settings(parent, uncertain or (not editable and not ready))
	if editable:
		var actions := HBoxContainer.new(); actions.add_theme_constant_override("separation", 10); parent.add_child(actions)
		_button(actions, "推荐补齐空位", command.bind("recommend"), "CustomRecommend", a.size() == 5 and b.size() == 5)
		UI.primary(_button(actions, "创建房间 · A %d/5 · B %d/5" % [a.size(), b.size()], command.bind("create"), "CustomCreate", uncertain or a.size() != 5 or b.size() != 5))
		host._label(parent, "搜索选手并加入 A / B 队；推荐只补空位，不覆盖已选成员。", 12, UI.MUTED)
		var filter_row := HBoxContainer.new(); filter_row.add_theme_constant_override("separation", 8); parent.add_child(filter_row)
		var field := LineEdit.new(); field.name = "CustomSearch"; field.placeholder_text = "选手姓名 / 俱乐部"; field.text = search_draft
		field.size_flags_horizontal = Control.SIZE_EXPAND_FILL; UI.line_edit(field); filter_row.add_child(field)
		field.text_changed.connect(func(value: String): search_draft = value)
		field.text_submitted.connect(search_players)
		_button(filter_row, "搜索", search_players, "CustomSearchGo", false, false)
		var rows: Array = catalog.get("rows", [])
		if catalog.is_empty() and not catalog_failed: fetch_catalog()
		if catalog_failed: _button(parent, "重新读取目录", retry_catalog, "CustomRetryCatalog", false, false)
		if not pending_catalog.is_empty() or request_catalog: host._label(parent, "正在读取选手目录…", 12, UI.MUTED)
		var grid := GridContainer.new(); grid.columns = 4; grid.add_theme_constant_override("h_separation", 8); grid.add_theme_constant_override("v_separation", 8); parent.add_child(grid)
		for player in rows:
			var id := str(player.get("player_id", "")); players[id] = player.duplicate(true)
			var card := UI.card(grid)
			host._label(card, str(player.get("name", id)), 15)
			host._label(card, "%s · %s" % [player.get("club", ""), ROLES.get(player.get("role", ""), player.get("role", ""))], 11, UI.MUTED)
			var choices := HBoxContainer.new(); choices.add_theme_constant_override("separation", 4); card.add_child(choices)
			_button(choices, "A +", add_player.bind("a", id), "CustomAddA_" + id, id in a or id in b or a.size() >= 5)
			_button(choices, "B +", add_player.bind("b", id), "CustomAddB_" + id, id in a or id in b or b.size() >= 5)
		var pagination := HBoxContainer.new(); pagination.add_theme_constant_override("separation", 10); parent.add_child(pagination)
		_button(pagination, "上一页", change_page.bind(page - 1), "CustomPreviousPage", page <= 1, false)
		host._label(pagination, "%d / %d · %d 位" % [page, maxi(1, int(catalog.get("pages", 1))), int(catalog.get("total", 0))], 12)
		_button(pagination, "下一页", change_page.bind(page + 1), "CustomNextPage", page >= int(catalog.get("pages", 1)), false)
	else:
		var actions := HBoxContainer.new(); actions.add_theme_constant_override("separation", 10); parent.add_child(actions)
		if ready:
			_button(actions, "保存地图 / 控制设置", command.bind("configure"), "CustomConfigure", uncertain or not dirty)
			_button(actions, "模拟验证", command.bind("simulate"), "CustomSimulate", uncertain or dirty)
			UI.primary(_button(actions, "进入 CS2 验证", command.bind("launch"), "CustomLaunch", uncertain or dirty or not bool(status.get("can_launch", false))))
			_button(actions, "RTS 指挥对局", host.rts_room.open_custom, "CustomRTS", uncertain or dirty or "de_" + str(room.get("map", "")) not in RTSMaps.available_maps(), false)
		elif str(status.get("status", "")) == "interrupted":
			host._label(parent, "CS2 已退出，可以继续当前房间。", 16)
			host._label(parent, "重新进入或切换 RTS 会重开当前未完成地图；模拟使用原来的十人和地图。", 12, UI.MUTED)
			if bool(status.get("can_resume", false)):
				UI.primary(_button(actions, "重新进入 CS2 · 重开当前图", command.bind("launch"), "CustomResumeCS2", uncertain))
			if bool(status.get("can_simulate", false)):
				_button(actions, "继续模拟本场", command.bind("simulate"), "CustomResumeSimulate", uncertain)
			if bool(status.get("can_rts", false)):
				_button(actions, "切换 RTS · 重开当前图", host.rts_room.open_custom, "CustomResumeRTS", uncertain, false)
		else:
			host._label(parent, "自定义对局正在启动 / 等待战绩。", 16)
		if status.get("can_retry", false) and str(status.get("status", "")) != "interrupted": _button(parent, "重试进入 CS2", command.bind("launch"), "CustomRetry", uncertain)
		if status.get("can_collect", false): _button(parent, "录入 / 重试录入战绩", command.bind("collect"), "CustomCollect", uncertain)
		_button(parent, "刷新房间状态", refresh_status, "CustomRefreshStatus", false, false)
		if not str(status.get("reason", "")).is_empty(): host._label(parent, str(status["reason"]), 12, UI.MUTED)
		if ready or (bool(status.get("process_known", false)) and status.get("cs2_running") == false):
			if cancel_confirm == str(room.get("id", "")):
				host._label(parent, "结束该自定义房间？不会计算天梯积分，未录入结果将不再接收。", 13)
				_button(parent, "确认结束房间", _cancel_confirm, "CustomCancelConfirm")
				_button(parent, "继续等待", _cancel_dismiss, "CustomCancelDismiss", false, false)
			else: _button(parent, "结束当前房间 / 重新选人", _cancel_request, "CustomCancel", false, false)
	_teams(parent, editable)
	if not editable:
		host._label(parent, "原系统自动分配五个位置；开赛前可以保存地图、开场 CT 队和控制角色。", 12, UI.MUTED)
		for item in state().get("history", []): _button(parent, host._report_title(item), host._open_report.bind(item), "CustomHistory_" + str(item.get("id", "")), false, false)
