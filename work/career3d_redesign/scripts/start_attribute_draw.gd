extends RefCounted
## Saved team draws. A team draw contributes exactly one chosen ability.
const UI = preload("res://scripts/computer_ui.gd")
const Reel = preload("res://scripts/draw_reel.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")
const PATH := "/api/3d/start/draw"
var owner_ref: WeakRef
var start: RefCounted:
	get: return owner_ref.get_ref() if owner_ref != null else null
var host: Node
var sessions: Dictionary = {}
var loaded: Dictionary = {}
var pending_path := ""
var pending_body: Dictionary = {}
var pending_era := ""
var retry_body: Dictionary = {}
var notice := ""
var proposal: Dictionary = {}
var popup: Window
var reel: Control
var card_root: Node
var counter: Label
var status: Label
var finish_hint: Label
var roll_button: Button
var commit_button: Button
var retry_button: Button
var team_state: Label
var axis_labels: Dictionary = {}
var candidates: Array[Dictionary] = []
var history: Label
## Save first, reveal second. The new outcome must not appear behind the reel.
var unrevealed_draw_id := ""

func attach(owner: RefCounted, device: Node) -> void:
	owner_ref = weakref(owner)
	host = device
	CareerBridge.busy_changed.connect(_busy_changed)

func current() -> Dictionary:
	return sessions.get(str(start.draft.era), {})

func complete() -> bool:
	return unrevealed_draw_id.is_empty() and bool(current().get("complete", false))

static func field_id(value: Variant) -> String:
	return "" if value == null else str(value)

func has_pending_draw() -> bool:
	return not field_id(current().get("pending_draw_id")).is_empty()

func current_draw() -> Dictionary:
	var session := current()
	var pending := field_id(session.get("pending_draw_id"))
	var draws: Array = session.get("team_draws", [])
	for draw in draws:
		if str(draw.draw_id) == pending:
			return {} if pending == unrevealed_draw_id else draw
	return draws.back() if not draws.is_empty() else {}

func render(parent: Node, meta: Dictionary) -> void:
	card_root = UI.card(parent)
	card_root.name = "CareerAttributeDraw"
	axis_labels.clear()
	candidates.clear()
	commit_button = null
	team_state = null
	retry_button = null
	UI.label(card_root, "抽队伍，选择你的能力", 20)
	UI.label(card_root, "最多抽 10 支队伍。每次从这支队伍的一名选手身上选一项能力；七项选齐，再进入形象设置。", 12, UI.MUTED)
	counter = UI.label(card_root, "", 13, UI.GREEN)
	var session := current()
	if not loaded.has(str(start.draft.era)):
		UI.label(card_root, "正在读取抽取记录……", 13, UI.MUTED)
		call_deferred("fetch")
	var actions := HBoxContainer.new()
	card_root.add_child(actions)
	roll_button = host._button(actions, "抽取第一支队伍", roll_current, false)
	roll_button.name = "CareerTeamDrawRoll"
	UI.primary(roll_button)
	var summary := GridContainer.new()
	summary.columns = 4
	summary.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	summary.add_theme_constant_override("h_separation", 12)
	summary.add_theme_constant_override("v_separation", 7)
	card_root.add_child(summary)
	for axis in session.get("axes", meta.get("axes", [])):
		var label := UI.label(summary, "", 13)
		label.name = "CareerCollected_" + str(axis.id)
		label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		axis_labels[str(axis.id)] = label
	var draw := current_draw()
	if not unrevealed_draw_id.is_empty():
		UI.label(card_root, "正在抽取队伍……", 18, UI.GREEN)
	elif not draw.is_empty(): render_team(card_root, draw)
	history = UI.label(card_root, "", 12, UI.MUTED)
	history.name = "CareerTeamDrawHistory"
	finish_hint = UI.label(card_root, "", 12, UI.MUTED)
	status = UI.label(card_root, "", 12, UI.MUTED)
	status.name = "CareerTeamDrawFeedback"
	retry_button = host._button(card_root, "重新确认上次操作", retry, false)
	refresh_controls()

func render_team(parent: Node, draw: Dictionary) -> void:
	var title_row := HBoxContainer.new()
	parent.add_child(title_row)
	TeamVisuals.badge(title_row, str(draw.get("source_team", "")), 38)
	var color := Color.from_string(str(draw.get("band_color", "63a8f2")), UI.GREEN)
	UI.label(title_row, "%s · %s" % [str(draw.get("source_team", "")), str(draw.get("band_label", ""))], 18, color.darkened(0.35))
	UI.label(title_row, "VRS %s · #%d" % [number(draw.get("vrs_points", 0)), int(draw.get("vrs_rank", 0))], 13, UI.MUTED)
	team_state = UI.label(parent, "", 12, UI.MUTED)
	team_state.name = "CareerTeamDrawState"
	var table := GridContainer.new()
	table.name = "CareerTeamAbilities"
	table.columns = 6
	table.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	table.add_theme_constant_override("h_separation", 7)
	table.add_theme_constant_override("v_separation", 5)
	parent.add_child(table)
	UI.label(table, "能力", 13, UI.MUTED)
	var players: Array = draw.get("players", [])
	for player in players:
		var caption := VBoxContainer.new()
		caption.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		table.add_child(caption)
		var name_row := HBoxContainer.new()
		caption.add_child(name_row)
		UI.label(name_row, str(player.get("source_player", player.get("name", ""))), 13)
		TeamVisuals.badge(name_row, str(draw.get("source_team", "")), 18)
	for axis in current().get("axes", []):
		UI.label(table, str(axis.name), 14).vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		for player in players:
			var axis_id := str(axis.id)
			var player_id := str(player.get("player_id", player.get("source_player_id", "")))
			var value: float = float(player.get("stats", {}).get(axis_id, 0))
			var choice := {"axis":axis_id, "axis_name":str(axis.name), "player_id":player_id,
				"draw_id":str(draw.draw_id), "value":value, "source_player":str(player.get("source_player", ""))}
			choice["band_color"] = ability_color(value)
			var button: Button = host._button(table, number(value), propose.bind(choice), false)
			button.name = "CareerTeamValue_" + axis_id + "_" + player_id.validate_node_name()
			button.custom_minimum_size = Vector2(85, 34)
			button.tooltip_text = "%s · %s %s" % [choice.source_player, choice.axis_name, number(value)]
			candidates.append({"button":button, "choice":choice})
	commit_button = host._button(parent, "先点击一个想要的数值", commit, false)
	commit_button.name = "CareerTeamDrawCommit"
	UI.primary(commit_button)

func propose(choice: Dictionary) -> void:
	if not unrevealed_draw_id.is_empty() or not pending_path.is_empty() or not retry_body.is_empty(): return
	if field_id(current().get("pending_draw_id")) != str(choice.draw_id): return
	if not str(choice.axis) in current().get("selectable_axes", []): return
	proposal = choice.duplicate(true)
	notice = "已选中 %s 的%s；点击下方收下后，再抽下一支队伍。" % [str(choice.source_player), str(choice.axis_name)]
	for axis in current().get("axes", []):
		if str(axis.id) == str(choice.axis) and not field_id(axis.get("selected_player_id")).is_empty():
			notice = "将用 %s 的%s %s 替换原来的 %s；本次仍消耗一支队伍的选择。" % [str(choice.source_player), str(choice.axis_name), number(choice.value), number(axis.get("selected_value", 0))]
	refresh_controls()

func commit() -> void:
	if proposal.is_empty(): return
	send("select", str(proposal.axis), str(proposal.draw_id), str(proposal.player_id))

func roll_current() -> void:
	send("open" if current().is_empty() else "roll")

static func number(value: Variant) -> String:
	return str(int(value)) if is_equal_approx(float(value), float(int(value))) else "%.1f" % float(value)

func ability_color(value: float) -> Color:
	var bands: Array = start.options.get("attribute_draw", {}).get("bands", [])
	var color := Color("63a8f2")
	for band in bands:
		if value >= float(band.get("min_value", 1)): color = Color.from_string(str(band.get("color", "63a8f2")), color)
	if bands.is_empty():
		color = Color("e5b85b") if value >= 90 else Color("9b75d1") if value >= 80 else Color("63a8f2") if value >= 65 else Color("6caa79") if value >= 50 else Color("8b96a3")
	return color

func _busy_changed(_value: bool) -> void:
	refresh_controls()
	if not _value and start != null and not loaded.has(str(start.draft.era)) and pending_path.is_empty() and host.screen.visible and host.active_page == "start" and start.page == "create" and start.draft.mode == "create": call_deferred("fetch")

func refresh_controls() -> void:
	if not is_instance_valid(card_root) or card_root.is_queued_for_deletion(): return
	var session := current()
	var locked := not unrevealed_draw_id.is_empty() or not pending_path.is_empty() or not retry_body.is_empty() or not CareerBridge.connected
	if is_instance_valid(counter):
		counter.text = "已抽 %d / %d 次 · 剩余 %d 次" % [int(session.get("attempts_used", 0)), int(session.get("max_draws", 10)), int(session.get("remaining", 10))]
	if is_instance_valid(roll_button):
		var used := int(session.get("attempts_used", 0))
		roll_button.text = "抽取第一支队伍" if used == 0 else "继续抽队伍 · 剩余 %d 次" % int(session.get("remaining", 0))
		roll_button.disabled = locked or not loaded.has(str(start.draft.era)) or (not session.is_empty() and not session.get("can_roll", false))
	for axis in session.get("axes", []):
		var label: Label = axis_labels.get(str(axis.id))
		if not is_instance_valid(label): continue
		var selection: Variant = axis.get("selection", {})
		if not selection is Dictionary: selection = {}
		var filled := not field_id(axis.get("selected_player_id")).is_empty()
		label.text = "%s  %s\n%s" % [str(axis.name), number(axis.get("selected_value", 0)) if filled else "—", str(selection.get("source_player", "待选择"))]
		label.modulate = UI.INK if filled else UI.MUTED
	var pending := field_id(session.get("pending_draw_id"))
	var allowed: Array = session.get("selectable_axes", [])
	for entry in candidates:
		var button: Button = entry.button
		if not is_instance_valid(button): continue
		var choice: Dictionary = entry.choice
		var chosen: bool = proposal.get("axis", "") == choice.axis and proposal.get("player_id", "") == choice.player_id and proposal.get("draw_id", "") == choice.draw_id
		button.disabled = locked or pending != str(choice.draw_id) or not str(choice.axis) in allowed
		var rarity: Color = choice.band_color
		button.add_theme_stylebox_override("normal", UI.style(UI.MINT if chosen else rarity.lightened(0.93), 5, 7, UI.GREEN if chosen else rarity.lightened(0.45)))
		button.add_theme_color_override("font_color", UI.GREEN if chosen else rarity.darkened(0.38))
	if is_instance_valid(commit_button):
		commit_button.disabled = locked or proposal.is_empty() or pending != str(proposal.get("draw_id", ""))
		commit_button.text = "收下 %s 的%s · %s" % [str(proposal.source_player), str(proposal.axis_name), number(proposal.value)] if not proposal.is_empty() else "先点击一个想要的数值" if not pending.is_empty() else "这次已收下数值"
	if is_instance_valid(team_state):
		team_state.text = "从这支队伍选一项能力。" if not pending.is_empty() else "已保存本次选择，可继续抽下一支队伍。"
		if not pending.is_empty() and allowed.size() < 7: team_state.text = "剩余次数刚好够补齐能力，本次请选择尚未填写的一项。"
	if is_instance_valid(finish_hint):
		finish_hint.text = "七项能力已选齐，可以进入下一步。剩余抽取机会也可用来替换一项能力。" if complete() else "还需选择 %d 项能力。已填能力可替换，每次仍只收下一项。" % session.get("unfilled_axes", [0, 1, 2, 3, 4, 5, 6]).size()
	if is_instance_valid(status): status.text = notice
	if is_instance_valid(retry_button): retry_button.visible = not retry_body.is_empty(); retry_button.disabled = not pending_path.is_empty()
	if is_instance_valid(history): history.text = history_text(session)
	if start != null: start.refresh_next_button()

func history_text(session: Dictionary) -> String:
	var lines: PackedStringArray = []
	for draw in session.get("team_draws", []):
		var selection: Variant = draw.get("selection")
		if not selection is Dictionary or selection.is_empty(): continue
		var axis_name := str(selection.get("axis_name", selection.get("axis", "")))
		for axis in session.get("axes", []):
			if str(axis.id) == str(selection.get("axis", "")): axis_name = str(axis.name)
		lines.append("%d. %s → %s · %s %s" % [int(draw.get("attempt", lines.size() + 1)), str(draw.get("source_team", "")), str(selection.get("source_player", "")), axis_name, number(selection.get("value", 0))])
	return "本次抽取记录\n" + "\n".join(lines) if not lines.is_empty() else ""

func fetch() -> void:
	if start == null: return # The owning form may have been replaced by a slot load.
	var era := str(start.draft.era)
	if loaded.has(era) or not pending_path.is_empty() or CareerBridge.busy: return
	var path := PATH + "?era=" + era.uri_encode()
	if CareerBridge._send(path, {}, false):
		pending_path = path
		pending_era = era
		pending_body.clear()

func send(action: String, axis: String = "", draw_id: String = "", player_id: String = "") -> void:
	if not pending_path.is_empty() or not retry_body.is_empty(): return
	var body := {"action":action, "era":str(start.draft.era), "request_id":"team-draw-%d-%d" % [OS.get_process_id(), Time.get_ticks_usec()]}
	if action != "open": body.merge({"draft_id":current().get("draft_id", ""), "draft_revision":int(current().get("revision", 0))})
	if action == "select": body.merge({"axis":axis, "draw_id":draw_id, "player_id":player_id})
	issue(body)

func issue(body: Dictionary) -> void:
	pending_path = PATH
	pending_body = body.duplicate(true)
	pending_era = str(body.era)
	if not CareerBridge.command(PATH, body):
		pending_path = ""
		pending_body.clear()
		notice = CareerBridge.message
	else: notice = "正在抽取队伍……" if body.action in ["open", "roll"] else "正在收下这个数值……"
	refresh_controls()

func retry() -> void:
	if not retry_body.is_empty() and pending_path.is_empty(): issue(retry_body)

func rebuild_preserving_scroll() -> void:
	if not host.screen.visible or host.active_page != "start": return
	host.page_scroll["start"] = host.scroll.scroll_vertical
	host.get_viewport().gui_release_focus()
	host._rebuild()

func finished(path: String, result: Dictionary) -> bool:
	if path == PATH and result.get("result_summary", false):
		# A lookup confirms the saved draw, not another spin. Reload its current
		# projection even if the transport error already released pending_path.
		pending_path = ""
		pending_body.clear()
		retry_body.clear()
		proposal.clear()
		unrevealed_draw_id = ""
		loaded.clear()
		if is_instance_valid(popup): popup.queue_free()
		notice = str(result.get("reason", result.get("msg", "")))
		call_deferred("fetch")
		refresh_controls()
		return true
	if path != pending_path or pending_path.is_empty(): return false
	var body := pending_body.duplicate(true)
	var era := pending_era
	pending_path = ""
	pending_body.clear()
	notice = str(result.get("reason", result.get("msg", "")))
	if result.get("ok", false):
		loaded[era] = true
		var saved: Variant = result.get("attribute_draw")
		sessions[era] = saved.duplicate(true) if saved is Dictionary else {}
		retry_body.clear()
		if str(body.get("action", "")) == "select":
			proposal.clear()
			notice = "已收下这个数值。"
			refresh_controls() # Keep the selected row and scrollbar in place.
		else:
			proposal.clear()
			var animate: bool = body.get("action", "") == "roll" and result.get("draw") is Dictionary and era == str(start.draft.era) and start.page == "create" and start.draft.mode == "create"
			if animate: unrevealed_draw_id = str(result.draw.get("draw_id", ""))
			rebuild_preserving_scroll()
			if era == str(start.draft.era) and start.page == "create" and start.draft.mode == "create":
				if animate: show_reel(result.draw)
				if body.get("action", "") == "open" and int(current().get("attempts_used", 0)) == 0 and current().get("can_roll", false): call_deferred("send", "roll")
	else:
		if not body.is_empty() and result.get("outcome_unknown", false): retry_body = body
		if not result.get("transport_failure", false):
			if body.is_empty(): loaded[era] = true
			else:
				loaded.erase(era)
				call_deferred("fetch")
		refresh_controls()
	return true

func show_reel(draw: Dictionary) -> void:
	if is_instance_valid(popup): popup.queue_free()
	popup = Window.new()
	popup.name = "CareerAttributeReel"
	popup.title = "队伍抽取"
	popup.transient = true
	popup.exclusive = true
	popup.unresizable = true
	popup.size = Vector2i(680, 350)
	host.add_child(popup)
	var background := ColorRect.new()
	background.color = UI.CREAM
	background.mouse_filter = Control.MOUSE_FILTER_IGNORE
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	popup.add_child(background)
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]: margin.add_theme_constant_override("margin_" + side, 16)
	popup.add_child(margin)
	var column := VBoxContainer.new()
	margin.add_child(column)
	var label := UI.label(column, "看看这次会抽到哪支队伍。", 14)
	reel = Reel.new()
	column.add_child(reel)
	var skip := UI.button(column, "跳过动画", func():
		if reel.is_running(): reel.skip()
		else: popup.hide()
	)
	var choices: Array = []
	for source in start.options.get("attribute_draw", {}).get("preview_teams", []): choices.append(reel_card(source))
	reel.revealed.connect(func(saved: Dictionary):
		label.text = "%s · VRS %s · %s" % [str(saved.name), str(saved.value), str(saved.rarity)]
		skip.text = "查看这支队伍的能力"
		unrevealed_draw_id = ""
		rebuild_preserving_scroll()
	)
	popup.close_requested.connect(func(): reel.skip(); popup.hide())
	popup.popup_centered()
	reel.start(choices, reel_card(draw), 4.0)

static func reel_card(draw: Dictionary) -> Dictionary:
	var team := str(draw.get("source_team", draw.get("name", "")))
	return {"name":team, "value":number(draw.get("vrs_points", 0)), "rarity":str(draw.get("band_label", "")), "color":str(draw.get("band_color", "63a8f2")), "badge_path":str(CareerBridge.context.get("media", {}).get("team_backgrounds", {}).get(team, ""))}

func reset_after_create() -> void:
	unrevealed_draw_id = ""
	sessions.clear()
	loaded.clear()
	retry_body.clear()
	proposal.clear()
	if is_instance_valid(popup): popup.queue_free()
