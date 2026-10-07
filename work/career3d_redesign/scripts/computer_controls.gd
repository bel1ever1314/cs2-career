extends RefCounted
const Kit = preload("res://scripts/ui_kit.gd")
## Lazy native views of the original career controls and pure extension registry.
const UI = preload("res://scripts/computer_ui.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")
const PAGES := ["management", "training", "assistance", "rankings", "workshop"]
const LEVELS := {"major":"Major", "premier":"Premier", "t1":"T1", "t2":"T2", "cct":"CCT", "qual":"预选赛 / RMR"}
var host: Node
var cache: Dictionary = {}
var pending_path := ""
var role_draft: Dictionary = {}
var role_signature := ""
var invite_draft: Dictionary = {}
var point_draft := ""
var assistance_initialized := false
var assistance_signature := ""
var training_opponent := ""
var training_map := "dust2"
var training_side := "ct"
var cancel_training_nonce := ""
var ranking_board := "top20"
var ranking_year := 0
var ranking_page := 1
var ranking_search := ""
var mark_editor = preload("res://scripts/team_mark_editor.gd").new()

func attach(value: Node) -> void:
	host = value
	mark_editor.host = value

func _label(parent: Node, value: String, size: int = 14, color: Color = UI.INK) -> Label:
	return host._label(parent, value, size, color)

func _button(parent: Node, value: String, callback: Callable, write: bool = true) -> Button:
	return host._button(parent, value, callback, write)

func _path(page: String) -> String:
	var path := "/api/3d/controls/" + page
	if page == "rankings":
		path += "?board=%s&page=%d&search=%s" % [ranking_board, ranking_page, ranking_search.uri_encode()]
		if ranking_year > 0: path += "&year=%d" % ranking_year
	return path

func render(page: String) -> bool:
	if page not in PAGES: return false
	var path := _path(page)
	var saved: Dictionary = cache.get(path, {})
	var revision := int(CareerBridge.context.get("calendar", {}).get("revision", 0))
	if saved.is_empty() or int(saved.get("revision", -1)) != revision:
		call_deferred("_load", path)
	if saved.is_empty():
		_label(host.content, "正在读取生涯资料…", 18, UI.MUTED)
		return true
	if saved.has("error"):
		_label(host.content, str(saved["error"]), 16, UI.MUTED)
		_button(host.content, "重新读取", _retry.bind(path), false)
		return true
	var data: Dictionary = saved.get("data", {})
	match page:
		"management": _management(data)
		"training": _training(data)
		"assistance": _assistance(data)
		"rankings": _rankings(data)
		"workshop": _workshop(data)
	return true

func _load(path: String) -> void:
	if CareerBridge.busy or not CareerBridge.connected or not pending_path.is_empty(): return
	if host.active_page not in PAGES or path != _path(str(host.active_page)): return
	pending_path = path
	if not CareerBridge._send(path, {}, false): pending_path = ""

func process(_delta: float = 0.0) -> void:
	if not CareerBridge.connected:
		pending_path = ""
		return
	if CareerBridge.busy or host.active_page not in PAGES: return
	var screen = host.get("screen")
	if screen is Control and not screen.visible: return
	var path := _path(str(host.active_page))
	var saved: Dictionary = cache.get(path, {})
	if saved.is_empty() or int(saved.get("revision", -1)) != int(CareerBridge.context.get("calendar", {}).get("revision", 0)):
		_load(path)

func received(path: String, result: Dictionary) -> bool:
	if not path.begins_with("/api/3d/controls/"): return false
	if not result.has("data"):
		host.notice = str(result.get("reason", result.get("msg", "")))
	if result.has("data") and result.has("page"):
		if result.get("ok", false): cache[path] = result.duplicate(true)
		pending_path = ""
	elif path == pending_path:
		cache[path] = {"revision":int(CareerBridge.context.get("calendar", {}).get("revision", 0)), "error":str(result.get("msg", "资料暂时无法读取。"))}
		pending_path = ""
	elif result.get("ok", false):
		cache.clear()
		if path.ends_with("/roles"): role_draft.clear(); role_signature = ""
		if path.ends_with("/assistance"): assistance_initialized = false
		if path.ends_with("/cancel"): cancel_training_nonce = ""
	if host.active_page in PAGES: host._rebuild()
	return true

func _retry(path: String) -> void:
	cache.erase(path)
	host._rebuild()

func _command(action: String, body: Dictionary = {}) -> void:
	var payload := body.duplicate(true)
	payload["request_id"] = "controls-%d-%d" % [OS.get_process_id(), Time.get_ticks_usec()]
	host._device_command("/api/3d/controls/" + action, payload)

func _choice(parent: Node, name: String, choices: Array, selected: String, callback: Callable) -> OptionButton:
	var option := OptionButton.new()
	option.name = name
	UI.dark_options(option)
	option.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	option.custom_minimum_size = Vector2(130, 34)
	for entry in choices:
		option.add_item(str(entry.get("label", entry["id"])))
		option.set_item_metadata(option.item_count - 1, str(entry["id"]))
		if str(entry["id"]) == selected: option.select(option.item_count - 1)
	option.item_selected.connect(func(index: int): callback.call(str(option.get_item_metadata(index))))
	parent.add_child(option)
	return option

func _management(data: Dictionary) -> void:
	_label(host.content, "阵容与合同", 25)
	_label(host.content, str(data.get("team", "自由身")), 16, UI.MUTED)
	mark_editor.render(host.content, data)
	var roster: Array = data.get("roster", [])
	var signature := JSON.stringify(roster)
	if signature != role_signature:
		role_signature = signature
		role_draft.clear()
		for player in roster: role_draft[str(player.get("name", ""))] = str(player.get("role", "rifle"))
	var labels: Dictionary = data.get("role_labels", {})
	var choices: Array = []
	for role in data.get("roles", []): choices.append({"id":str(role), "label":str(labels.get(role, role))})
	if not roster.is_empty():
		var card := UI.card(host.content)
		_label(card, "首发位置", 19)
		for player in roster:
			var row := HBoxContainer.new()
			card.add_child(row)
			var key := str(player.get("name", ""))
			var player_id := str(player.get("player_id", ""))
			_button(row, key + (" · 你" if player.get("you", false) else ""), host._load_detail.bind("player", player_id if not player_id.is_empty() else key), false).size_flags_horizontal = Control.SIZE_EXPAND_FILL
			_label(row, "能力 %s · %s 岁" % [preload("res://scripts/ui_format.gd").score(player.get("ability")), preload("res://scripts/ui_format.gd").integer(player.get("age"))], 13, UI.MUTED)
			_choice(row, "RosterRole_" + player_id, choices, str(role_draft.get(key, "rifle")), _role_changed.bind(key, roster)).disabled = not data.get("roles_allowed", false)
		_label(card, "保留一名指挥与一名主狙。切换到已有人担任的位置时，沿用原来的位置对调。", 13, UI.MUTED)
		var apply := _button(card, "保存首发位置", _command.bind("roles", {"roles":role_draft.duplicate()}))
		apply.name = "RosterSave"
		apply.disabled = not data.get("roles_allowed", false)
		UI.primary(apply)
	if not str(data.get("reason", "")).is_empty(): _label(host.content, str(data["reason"]), 14, UI.MUTED)
	_label(host.content, "入队合同", 19)
	_label(host.content, str(data.get("contract_note", "")), 13, UI.MUTED)
	var pending: Dictionary = data.get("pending", {})
	if not pending.is_empty():
		_label(host.content, "当前加盟选择：" + str(pending.get("team", "")), 16)
		_button(host.content, "在手机中完成加盟选择", host._open_phone.bind("home"), false)
	for offer in data.get("offers", []):
		var card := UI.card(host.content)
		_label(card, str(offer.get("title", "入队邀请")), 17)
		_label(card, "%s · %s · %s" % [offer.get("date", ""), offer.get("team", ""), offer.get("status", "")], 13, UI.MUTED)
		_label(card, str(offer.get("body", "")), 14)
		if offer.get("status") == "open":
			var actions := HBoxContainer.new()
			card.add_child(actions)
			var accept := _button(actions, "查看加盟选择", _command.bind("contract/accept", {"id":offer.get("id", "")}))
			var decline := _button(actions, "婉拒合同", _command.bind("contract/decline", {"id":offer.get("id", "")}))
			accept.disabled = not data.get("contract_allowed", false)
			decline.disabled = accept.disabled
	if data.get("offers", []).is_empty(): _label(host.content, "当前没有入队合同。", 14, UI.MUTED)
	_button(host.content, "打开转会市场", host._navigate.bind("transfers"), false)
	for move in data.get("history", []):
		_label(host.content, "%s · %s → %s" % [move.get("date", ""), move.get("old_team", ""), move.get("new_team", "")], 13, UI.MUTED)

func _role_changed(value: String, player: String, roster: Array) -> void:
	var previous := str(role_draft.get(player, "rifle"))
	if value in ["awp", "igl"]:
		for member in roster:
			var key := str(member.get("name", ""))
			if key != player and role_draft.get(key) == value: role_draft[key] = previous if previous != value else "rifle"
	role_draft[player] = value
	host._rebuild()

func _training(data: Dictionary) -> void:
	_label(host.content, "训练与成长", 25)
	_label(host.content, str(data.get("rule", "")), 14, UI.MUTED)
	var focus := UI.card(host.content)
	focus.name = "MapFocusTraining"
	_label(focus, "专项练图", 19)
	_label(focus, "每天选一张，跨日结算一次。越熟练提升越慢，不增加个人属性。", 13, UI.MUTED)
	var task: Dictionary = data.get("map_practice", {})
	if not task.is_empty():
		_label(focus, "%s · %s · %s" % [task.get("date", ""), str(task.get("map", "")).capitalize(), "已完成" if task.get("settled", false) else "已安排"], 13)
	var focus_options: Array = []
	for code in data.get("maps", []): focus_options.append({"id":str(code), "label":str(code).capitalize()})
	_choice(focus, "MapFocusChoice", focus_options, training_map, func(value: String): training_map = value)
	var focus_button := _button(focus, "安排今天的专项练图", func(): _command("training/map-focus", {"map":training_map}))
	focus_button.name = "ScheduleMapFocus"
	focus_button.disabled = focus_button.disabled or bool(data.get("pending", false))
	var card := UI.card(host.content)
	_label(card, "%s · 全队心态 %s" % [data.get("date", ""), data.get("mentality", "—")], 18)
	_label(card, "今天已结算训练奖励。" if data.get("today_rewarded", false) else "今天尚未结算训练奖励。", 14)
	if data.get("pending", false):
		var session: Dictionary = data.get("session", {})
		var nonce := str(session.get("nonce", ""))
		_label(card, "待核验：%s · %s" % [session.get("date", ""), session.get("map", "")], 14)
		_button(card, "核验并结算训练", _command.bind("training/finish"))
		if cancel_training_nonce == nonce and not nonce.is_empty():
			_label(card, "退出 CS2 后可取消核验。本次训练不会获得奖励，现有战绩记录保留。", 14, UI.MUTED)
			_button(card, "确认取消核验", _command.bind("training/cancel", {"nonce":nonce, "confirmed":true}))
			_button(card, "保留待核验训练", _cancel_training_prompt, false)
		else:
			_button(card, "取消待核验训练", _ask_cancel_training.bind(nonce), false)
	else:
		var opponents: Array = []
		for opponent in data.get("opponents", []): opponents.append({"id":str(opponent.get("id", "")), "label":str(opponent.get("name", ""))})
		if training_opponent.is_empty() and not opponents.is_empty(): training_opponent = str(opponents[0]["id"])
		_choice(card, "TrainingOpponent", opponents, training_opponent, func(value: String): training_opponent = value)
		var options: Array = []
		for map_code in data.get("maps", []): options.append({"id":str(map_code), "label":str(map_code).capitalize()})
		_choice(card, "TrainingMap", options, training_map, func(value: String): training_map = value)
		_choice(card, "TrainingSide", [{"id":"ct", "label":"CT 防守方"}, {"id":"t", "label":"T 进攻方"}], training_side, func(value: String): training_side = value)
		var launch := _button(card, "进入真实 CS2 训练赛", _launch_training)
		launch.name = "TrainingLaunch"
		launch.disabled = not data.get("launch_allowed", false) or not data.get("config", {}).get("ready", false)
		UI.primary(launch)
		if not data.get("config", {}).get("ready", false):
			_label(card, str(data.get("config", {}).get("reason", "请先完成游戏设置。")), 13, UI.MUTED)
			_button(card, "打开 CS2 设置", host._navigate.bind("settings"), false)
	if not str(data.get("reason", "")).is_empty(): _label(card, str(data["reason"]), 13, UI.MUTED)
	preload("res://scripts/map_form_panel.gd").mount(host.content, data.get("map_performance", []))
	var personal: Dictionary = data.get("personal", {})
	var growth := UI.card(host.content)
	_label(growth, "属性培养 · %s 点可分配" % preload("res://scripts/ui_format.gd").score(personal.get("attr_points", 0)), 19)
	_label(growth, str(personal.get("growth_reason", "")), 14, UI.MUTED)
	var window: Dictionary = data.get("growth_window", {})
	var period = window.get("window")
	if period is Dictionary:
		_label(growth, "%s 后成长窗口：%s 至 %s" % [period.get("event", "Major"), period.get("start", ""), period.get("until", "")], 13, UI.MUTED)
	_button(growth, "手动分配属性点", _open_growth, false)
	_button(growth, "自动加点计划", host._navigate.bind("assistance"), false)
	_button(host.content, "安排模拟训练赛", host._navigate.bind("scrim"), false)

func _launch_training() -> void:
	_command("training/launch", {"opponent_id":training_opponent, "map":training_map, "side":training_side})

func _ask_cancel_training(nonce: String) -> void:
	cancel_training_nonce = nonce
	host._rebuild()

func _cancel_training_prompt() -> void:
	cancel_training_nonce = ""
	host._rebuild()

func _open_growth() -> void:
	host.profile_tab = "growth"
	host._navigate("profile")

func _assistance(data: Dictionary) -> void:
	_label(host.content, "邀请与训练计划", 25)
	_label(host.content, str(data.get("note", "")), 14, UI.MUTED)
	var signature := JSON.stringify([data.get("invites", {}), data.get("points", "off")])
	if not assistance_initialized or assistance_signature != signature:
		assistance_signature = signature
		invite_draft = data.get("invites", {}).duplicate(true)
		point_draft = str(data.get("points", "off"))
		assistance_initialized = true
	var card := UI.card(host.content)
	_label(card, "赛事邀请自动处理", 19)
	for level in data.get("levels", []):
		var key := str(level)
		var row := HBoxContainer.new()
		card.add_child(row)
		_label(row, str(LEVELS.get(key, key)), 14).custom_minimum_size.x = 140
		_choice(row, "InviteRule_" + key, [{"id":"manual", "label":"手动处理"}, {"id":"accept", "label":"自动接受"}, {"id":"decline", "label":"自动拒绝"}], str(invite_draft.get(key, "manual")), _invite_changed.bind(key))
	var save_invites := _button(card, "保存邀请规则", _save_invites)
	save_invites.name = "SaveInviteRules"
	save_invites.disabled = not data.get("allowed", false)
	card = UI.card(host.content)
	_label(card, "自动加点方向", 19)
	var options: Array = [{"id":"off", "label":"关闭 · 手动加点"}, {"id":"balanced", "label":"均衡发展 · 优先最低属性"}]
	for axis in data.get("axes", []): options.append({"id":str(axis), "label":str(data.get("axis_labels", {}).get(axis, axis))})
	_choice(card, "AutoPointDirection", options, point_draft, func(value: String): point_draft = value)
	var save_points := _button(card, "应用加点方向", _save_points)
	save_points.name = "SavePointDirection"
	save_points.disabled = not data.get("allowed", false)
	if not str(data.get("notice", "")).is_empty(): _label(card, str(data["notice"]), 14)
	if not str(data.get("reason", "")).is_empty(): _label(host.content, str(data["reason"]), 14, UI.MUTED)

func _invite_changed(value: String, key: String) -> void:
	invite_draft[key] = value

func _save_invites() -> void:
	_command("assistance", {"invites":invite_draft.duplicate(true)})

func _save_points() -> void:
	_command("assistance", {"points":point_draft})

func _rankings(data: Dictionary) -> void:
	_label(host.content, "Top20 与选手数据", 25)
	host._tabs(host.content, [{"id":"top20", "label":"年度 Top20"}, {"id":"players", "label":"选手数据榜"}], ranking_board, _ranking_board)
	var filter := HBoxContainer.new()
	host.content.add_child(filter)
	if ranking_board == "top20":
		var years: Array = []
		for year in data.get("years", []): years.append({"id":str(year), "label":str(year) + " 年"})
		_choice(filter, "RankingYear", years, str(data.get("year", "")), _ranking_year)
	var search := LineEdit.new()
	search.name = "RankingSearch"
	UI.line_edit(search)
	search.text = ranking_search
	search.placeholder_text = "搜索选手或战队"
	search.max_length = 100
	search.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	filter.add_child(search)
	search.text_changed.connect(func(value: String): ranking_search = value)
	search.text_submitted.connect(func(_value: String): _search_rankings())
	_button(filter, "搜索", _search_rankings, false)
	_label(host.content, str(data.get("note", "")), 13, UI.MUTED)
	for item in data.get("rows", []):
		var rank = item.get("rank", (ranking_page - 1) * 20 + data.get("rows", []).find(item) + 1)
		var identity := str(item.get("player_id", item.get("player", "")))
		if identity.is_empty(): identity = str(item.get("player", ""))
		var entry := _button(host.content, "%s · %s" % [item.get("player", ""), item.get("team", "")], host._load_detail.bind("player", identity), false)
		var detail := ""
		if ranking_board == "top20":
			detail = "%s · Top10 %s · Top20 %s · MVP %s · EVP %s · 总评分 %s" % [item.get("team", ""), _number(item.get("rating_top10"), 2), _number(item.get("rating_top20"), 2), item.get("mvp", 0), item.get("evp", 0), _number(item.get("score"), 4)]
		else:
			detail = "%s · K / D / A %s / %s / %s · ADR %s · KAST %s%%" % [item.get("team", ""), item.get("k", 0), item.get("d", 0), item.get("a", 0), _number(item.get("adr")), _number(float(item.get("kast", 0)) * 100)]
		var podium := int(rank) <= 3 if typeof(rank) in [TYPE_INT, TYPE_FLOAT] else false
		Kit.rich_row(entry, UI, str(item.get("player", "")), detail, "Rating %s · %s 图" % [_number(item.get("rating"), 2), item.get("maps", 0)], "#%s" % rank, "amber" if podium else "gray", "", str(item.get("team", "")), Color("c9a24a") if podium else Color.TRANSPARENT)
		entry.custom_minimum_size.y = 62
	if data.get("rows", []).is_empty(): _label(host.content, "尚无达到原榜单样本条件的选手。", 15, UI.MUTED)
	var pager := HBoxContainer.new()
	host.content.add_child(pager)
	_button(pager, "上一页", _ranking_page.bind(-1), false).disabled = ranking_page <= 1
	_label(pager, "%d / %s · %s 名选手" % [ranking_page, data.get("pages", 1), data.get("total", 0)], 14)
	_button(pager, "下一页", _ranking_page.bind(1), false).disabled = ranking_page >= int(data.get("pages", 1))

static func _number(value, digits: int = 1) -> String:
	if typeof(value) not in [TYPE_INT, TYPE_FLOAT]: return "—"
	return ("%.4f" if digits == 4 else "%.2f" if digits == 2 else "%.1f") % float(value)

func _ranking_board(value: String) -> void:
	ranking_board = value
	ranking_page = 1
	if value == "players": ranking_year = 0
	host._rebuild()

func _ranking_year(value: String) -> void:
	ranking_year = int(value)
	ranking_page = 1
	host._rebuild()

func _ranking_page(direction: int) -> void:
	ranking_page = maxi(1, ranking_page + direction)
	host._rebuild()

func _search_rankings() -> void:
	ranking_page = 1
	host._rebuild()

func _workshop(data: Dictionary) -> void:
	_label(host.content, "扩展工坊", 25)
	var card := UI.card(host.content)
	_label(card, "安装与制作", 19)
	_label(card, "将包含 pack.json 的扩展文件夹放入下方目录。原加载器只读取 JSON 数据。", 14, UI.MUTED)
	_label(card, str(data.get("root", "")), 14)
	_label(card, "重新扫描后，生涯事件在下次触发、比赛聊天在下次准备比赛时生效；赛事与年代用于新生涯。", 13, UI.MUTED)
	var reload := _button(card, "重新扫描扩展", _command.bind("workshop/reload"))
	reload.name = "ReloadWorkshop"
	reload.disabled = not str(data.get("reason", "")).is_empty()
	_label(host.content, "已发现 %s 个扩展 · %s 个已启用" % [data.get("packs", []).size(), data.get("ready", 0)], 18)
	var labels := {"stories":"剧情文字", "events":"赛事日历", "skins":"饰品", "teams":"战队", "eras":"年代", "match_chat":"比赛聊天", "incidents":"生涯事件"}
	for pack in data.get("packs", []):
		card = UI.card(host.content)
		_label(card, "%s · %s" % [pack.get("name", ""), pack.get("version", "")], 18)
		var types := PackedStringArray()
		for kind in pack.get("kinds", []): types.append(str(labels.get(kind, kind)))
		var statuses := {"ready":"已启用", "disabled":"已停用", "rejected":"校验失败，未加载"}
		_label(card, "%s · %s" % [statuses.get(pack.get("status", ""), pack.get("status", "")), " / ".join(types)], 14)
		_label(card, str(pack.get("id", "")), 12, UI.MUTED)
		for error in pack.get("errors", []): _label(card, str(error), 13, Color("a25746"))
	if data.get("packs", []).is_empty(): _label(host.content, "暂无扩展，内置内容可以直接游玩。", 14, UI.MUTED)
	if not str(data.get("reason", "")).is_empty(): _label(host.content, str(data["reason"]), 14, UI.MUTED)
