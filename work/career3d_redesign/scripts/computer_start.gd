extends RefCounted
## Start selection calls the original career creator; a draft never edits a save.
const UI = preload("res://scripts/computer_ui.gd")
const Appearance = preload("res://scripts/appearance_customization.gd")
const AttributeDraw = preload("res://scripts/start_attribute_draw.gd")
var host: Node
var options: Dictionary = {}
var options_by_era: Dictionary = {}
var draft := {"mode":"create", "era":"2026", "origin":"attribute_draw", "name":"", "org":"", "region":"AS", "role":"rifle", "quick_mode":false}
var team_id := ""
var player_id := ""
var page := "welcome"
var pending_path := ""
var pending_era := ""
var submitting := false
var uncertain_creation: Dictionary = {}
var notice := ""
var confirmation: ConfirmationDialog
var avatar = Appearance.new()
var attribute_draw = AttributeDraw.new()
var next_button: Button

func attach(value: Node) -> void:
	host = value
	avatar.creation_mode = true
	attribute_draw.attach(self, host)

func render(parent: Node) -> void:
	next_button = null
	UI.label(parent, "你的职业生涯", 26)
	if page == "welcome":
		var columns := HBoxContainer.new()
		columns.add_theme_constant_override("separation", 28)
		parent.add_child(columns)
		Appearance.add_preview(columns, CareerBridge.context.get("avatar", {}).get("appearance", {}), Vector2(240, 320))
		var content := UI.card(columns)
		content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var start: Dictionary = CareerBridge.context.get("start", {})
		UI.label(content, str(start.get("player", CareerBridge.context.get("player", {}).get("name", ""))), 24)
		UI.label(content, str(start.get("date", CareerBridge.context.get("date", ""))) + " · " + str(CareerBridge.context.get("team", {}).get("name", "")), 14, UI.MUTED)
		UI.primary(host._button(content, "继续这段生涯", host.close_computer, false))
		host._button(content, "开始新生涯", begin_new, false)
		host._button(content, "换个形象", host._navigate.bind("appearance"), false)
		host._button(content, "存档与读档", host._navigate.bind("saves"), false)
		UI.label(content, "新开局会先备份当前生涯，不会动旧桌面版的存档。", 12, UI.MUTED)
		return
	if options.is_empty():
		UI.label(parent, "正在读取年代与阵容……", 15, UI.MUTED)
		host.call_deferred("_fetch_start_options")
		return
	if page == "appearance":
		render_appearance(parent)
		return
	UI.label(parent, "第一步 · 选择开局与能力", 15, UI.MUTED)
	var row := HBoxContainer.new()
	parent.add_child(row)
	select(row, "CareerStartEra", options.get("eras", []), str(draft.era), change_era, "year")
	select(row, "CareerStartMode", [{"id":"create", "name":"自建开局"}, {"id":"join", "name":"接管职业选手"}], str(draft.mode), change_mode)
	select(row, "CareerStartRole", options.get("roles", []), str(draft.role), func(value: String): draft.role = value)
	if draft.mode == "create":
		var names := HBoxContainer.new()
		parent.add_child(names)
		input(names, "选手 ID", "CareerStartName", str(draft.name), 32, func(value: String): draft.name = value)
		input(names, "俱乐部名称", "CareerStartClub", str(draft.org), 40, func(value: String): draft.org = value)
		select(names, "CareerStartRegion", options.get("regions", []), str(draft.region), func(value: String): draft.region = value)
		attribute_draw.render(parent, options.get("attribute_draw", {}))
	else:
		var team := current_team()
		var roster := HBoxContainer.new()
		parent.add_child(roster)
		select(roster, "CareerStartTeam", options.get("teams", []), team_id, choose_team)
		var players: Array = []
		for player in team.get("players", []):
			players.append({"id":player.player_id, "name":"%s · %s" % [player.name, player.role]})
		select(roster, "CareerStartPlayer", players, player_id, choose_player)
		UI.label(parent, "接管所选年代的真实名单；形象只改变你的 3D 小鸡。", 12, UI.MUTED)
	var actions := HBoxContainer.new()
	parent.add_child(actions)
	next_button = host._button(actions, "进入下一步 · 设置形象", next_step, false)
	next_button.name = "CareerStartNext"
	UI.primary(next_button)
	host._button(actions, "返回", welcome, false)
	refresh_next_button()
	if not notice.is_empty(): UI.label(parent, notice, 13, UI.MUTED)

func render_appearance(parent: Node) -> void:
	UI.label(parent, "第二步 · 设置你的形象", 15, UI.MUTED)
	var player_name := player_id
	for player in current_team().get("players", []):
		if str(player.player_id) == player_id: player_name = str(player.name)
	var identity := "%s · %s" % [str(draft.name), str(draft.org)] if draft.mode == "create" else "%s · %s" % [player_name, str(current_team().get("name", ""))]
	UI.label(parent, identity, 14, UI.GREEN)
	var pace := CheckButton.new()
	pace.name = "CareerStartQuick"
	pace.text = "快速赛季开局"
	UI.transparent(pace)
	pace.button_pressed = bool(draft.quick_mode)
	pace.toggled.connect(func(value: bool): draft.quick_mode = value)
	parent.add_child(pace)
	avatar.render(host, parent)
	var actions := HBoxContainer.new()
	parent.add_child(actions)
	var create_button: Button = host._button(actions, "正在建立生涯……" if submitting else "确认上次开局结果" if not uncertain_creation.is_empty() else "开始这段生涯", ask_create)
	create_button.name = "CareerStartCreate"
	create_button.disabled = submitting
	UI.primary(create_button)
	var back: Button = host._button(actions, "返回选择能力" if draft.mode == "create" else "返回选择选手", edit_selection, false)
	back.name = "CareerStartBackToSelection"
	back.disabled = submitting or not uncertain_creation.is_empty()
	if not notice.is_empty(): UI.label(parent, notice, 13, UI.MUTED)

func refresh_next_button() -> void:
	if not is_instance_valid(next_button): return
	next_button.disabled = submitting or not attribute_draw.pending_path.is_empty() or not attribute_draw.retry_body.is_empty() or (draft.mode == "create" and (not attribute_draw.complete() or attribute_draw.has_pending_draw())) or (draft.mode == "join" and player_id.is_empty())

func next_step() -> void:
	if draft.mode == "create" and (not attribute_draw.complete() or attribute_draw.has_pending_draw()):
		notice = "先选齐七项能力，并收下这次抽到队伍的一项数值。"
		return
	if draft.mode == "create" and (str(draft.name).strip_edges().is_empty() or str(draft.org).strip_edges().is_empty()):
		notice = "先填写选手 ID 和俱乐部名称。"
		rebuild_preserving_scroll()
		return
	page = "appearance"
	notice = ""
	host.page_scroll["start"] = 0
	host._rebuild()

func edit_selection() -> void:
	if submitting or not uncertain_creation.is_empty(): return
	page = "create"
	notice = ""
	host.page_scroll["start"] = 0
	host._rebuild()

func rebuild_preserving_scroll() -> void:
	host.page_scroll["start"] = host.scroll.scroll_vertical
	host._rebuild()

func select(parent: Node, control_name: String, rows: Array, selected: String, callback: Callable, caption_key: String = "name") -> void:
	var field := OptionButton.new()
	field.name = control_name
	field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	UI.dark_options(field)
	for entry in rows:
		var caption: String = str(int(entry.year)) if caption_key == "year" else str(entry.get(caption_key, entry.get("id", "")))
		field.add_item(caption)
		field.set_item_metadata(field.item_count - 1, str(entry.id))
		if str(entry.id) == selected: field.select(field.item_count - 1)
	parent.add_child(field)
	field.item_selected.connect(func(index: int): callback.call(str(field.get_item_metadata(index))))

func input(parent: Node, caption: String, control_name: String, text: String, limit: int, callback: Callable) -> void:
	var field := LineEdit.new()
	field.name = control_name
	field.placeholder_text = caption
	field.text = text
	field.max_length = limit
	field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	UI.line_edit(field)
	parent.add_child(field)
	field.text_changed.connect(callback)

func current_team() -> Dictionary:
	for team in options.get("teams", []):
		if str(team.id) == team_id: return team
	return {}

func choose_team(value: String) -> void:
	team_id = value
	var players: Array = current_team().get("players", [])
	player_id = str(players[0].player_id) if not players.is_empty() else ""
	if not players.is_empty(): draft.role = str(players[0].role)
	rebuild_preserving_scroll()

func choose_player(value: String) -> void:
	player_id = value
	for player in current_team().get("players", []):
		if str(player.player_id) == value: draft.role = str(player.role)
	rebuild_preserving_scroll()

func begin_new() -> void:
	page = "create"
	avatar.draft = Appearance.normalize(CareerBridge.context.get("avatar", {}).get("appearance", {}))
	avatar.dirty = false
	host.page_scroll["start"] = 0
	fetch()
	host._rebuild()

func welcome() -> void:
	page = "welcome"
	host._rebuild()

func change_mode(value: String) -> void:
	draft.mode = value
	ensure_roster_defaults()
	rebuild_preserving_scroll()

func change_era(value: String) -> void:
	draft.era = value
	attribute_draw.proposal.clear()
	options = options_by_era.get(value, {})
	team_id = ""
	player_id = ""
	ensure_roster_defaults()
	fetch()
	rebuild_preserving_scroll()

func fetch() -> void:
	if not options.is_empty() or not pending_path.is_empty() or CareerBridge.busy: return
	var path := "/api/3d/start/options?era=" + str(draft.era).uri_encode()
	if CareerBridge._send(path, {}, false):
		pending_path = path
		pending_era = str(draft.era)

func ensure_roster_defaults() -> void:
	var teams: Array = options.get("teams", [])
	if teams.is_empty(): return
	if current_team().is_empty(): team_id = str(teams[0].id)
	var players: Array = current_team().get("players", [])
	if players.is_empty():
		player_id = ""
		return
	var selected: Dictionary = {}
	for player in players:
		if str(player.player_id) == player_id: selected = player
	if selected.is_empty():
		selected = players[0]
		player_id = str(selected.player_id)
	if draft.mode == "join": draft.role = str(selected.role)

func finished(path: String, result: Dictionary) -> bool:
	if attribute_draw.finished(path, result): return true
	if path == "/api/3d/start/create":
		submitting = false
		notice = str(result.get("reason", result.get("msg", "")))
		if not result.get("outcome_unknown", false): uncertain_creation.clear()
		if result.get("ok", false):
			attribute_draw.reset_after_create()
			page = "welcome"
			host.reset_career_views()
			Phone.reset_career_views()
			host.close_computer()
			CareerBridge.clock_minutes = 480
			CareerBridge.clock_held = false
			Travel.go("bedroom", false)
		elif host.screen.visible and host.active_page == "start": host._rebuild()
		return true
	if path != pending_path or pending_path.is_empty(): return false
	pending_path = ""
	if result.get("ok", false):
		options_by_era[pending_era] = result.duplicate(true)
		if str(draft.era) == pending_era:
			options = result.duplicate(true)
			ensure_roster_defaults()
	else: notice = str(result.get("msg", "开局资料没有读取成功。"))
	if host.screen.visible and host.active_page == "start": host._rebuild()
	return true

func ask_create() -> void:
	if submitting: return
	if page != "appearance": return
	if uncertain_creation.is_empty() and draft.mode == "create" and (str(draft.name).strip_edges().is_empty() or str(draft.org).strip_edges().is_empty()):
		notice = "先填写选手 ID 和俱乐部名称。"
		host._rebuild()
		return
	if uncertain_creation.is_empty() and draft.mode == "create" and not attribute_draw.complete():
		notice = "先选齐七项能力。"
		host._rebuild()
		return
	if is_instance_valid(confirmation): confirmation.queue_free()
	confirmation = ConfirmationDialog.new()
	confirmation.title = "开始新生涯"
	confirmation.dialog_text = "当前生涯会先备份，再开始新的生涯。确定你的开局和形象了吗？"
	confirmation.ok_button_text = "开始"
	confirmation.cancel_button_text = "再看看"
	confirmation.confirmed.connect(create)
	host.add_child(confirmation)
	confirmation.popup_centered(Vector2i(420, 180))

func create() -> void:
	if submitting: return
	var payload := draft.duplicate(true)
	if payload.mode == "join": payload.merge({"team_id":team_id, "player_id":player_id})
	else:
		payload["draft_id"] = attribute_draw.current().get("draft_id", "")
	var body := {"career":payload, "appearance":avatar.values(), "confirm_replace":true,
		"revision":int(CareerBridge.context.get("calendar", {}).get("revision", 0)),
		"request_id":"start-%d-%d" % [OS.get_process_id(), Time.get_ticks_usec()]}
	if not uncertain_creation.is_empty(): body = uncertain_creation.duplicate(true)
	submitting = CareerBridge.command("/api/3d/start/create", body)
	if submitting: uncertain_creation = body.duplicate(true)
	if not submitting: notice = "操作未发出，请等待当前操作结束后再试。"
	host._rebuild()
