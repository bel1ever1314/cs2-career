extends RefCounted
## Presentation never settles a match. The engine commits once before any reveal.
const UI = preload("res://scripts/computer_ui.gd")
const Scoreboard = preload("res://scripts/career_match_scoreboard.gd")
const RoundStrip = preload("res://scripts/career_match_round_strip.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")
const MAP_SECONDS := 2.0
const STATS_SECONDS := 4.0
const ROUND_SECONDS := 0.28
const HALFTIME_SECONDS := 1.25
const WIN_SURFACE := Color("dcebdd")
const LOSS_SURFACE := Color("f0ddd7")
var host: Node
var preflight: Dictionary = {}
var connection: Dictionary = {}
var result: Dictionary = {}
var saved_results: Dictionary = {}
var last_result: Dictionary = {}
var shown_maps := 0
var reveal_phase := ""
var reveal_elapsed := 0.0
var continue_ready := false
var request_pending := false
var pending_action := ""
var pending_match_id := ""
var show_real := false
var quick_running := false
var quick_elapsed := 0.0
var poll_elapsed := 0.0
var notice := ""
var textures: Dictionary = {}
var command_sender: Callable
var reveal: Dictionary = {}
var reveal_maps: Array = []
var map_cursor := 0
var round_cursor := 0
var live_score: Array[int] = [0, 0]
var map_completed := false
var half_pause := 0.0
var score_label: Label
var phase_label: Label
var series_label: Label
var round_label: Label
var event_label: Label
var stats_note: Label
var scoreboard: Node
var round_strip: Control
var notified_maps: Dictionary = {}
var venue_after_preflight := ""
var veto_history_expanded := false

func attach(value: Node) -> void:
	host = value

func current_game() -> Dictionary:
	var game = CareerBridge.context.get("nextmatch", {})
	return game if game is Dictionary else {}

func attendance() -> Dictionary:
	var value = current_game().get("attendance", {})
	return value if value is Dictionary else {}

func can_prepare_here() -> bool:
	var info := attendance()
	if not bool(current_game().get("due", false)): return false
	if str(info.get("destination", "")) == "club":
		var scene := host.get_tree().current_scene
		return host.location == "club" and scene != null and scene.scene_file_path == "res://play.tscn"
	var venue: Dictionary = current_preflight().get("venue", {})
	return Travel.is_match_seated(venue, str(current_game().get("id", "")))

func current_preflight() -> Dictionary:
	var current: Dictionary = CareerBridge.context.get("match_preflight", {})
	var id := str(current_game().get("id", ""))
	if str(preflight.get("match_id", "")) == id and not id.is_empty(): return preflight
	return current if str(current.get("match_id", "")) == id else {}

func is_presenting() -> bool:
	return request_pending or not result.is_empty()

func render(parent: Node) -> void:
	if not result.is_empty():
		render_reveal(parent)
		return
	var game := current_game()
	UI.label(parent, "职业比赛", 25)
	if game.is_empty():
		UI.label(parent, "还没有安排下一场比赛。", 14, UI.MUTED)
		host._button(parent, "查看赛事日程", host._navigate.bind("events"), false)
	else:
		var box := UI.card(parent)
		UI.label(box, str(game.get("event", "下一场比赛")), 20)
		UI.label(box, "%s · 对阵 %s · BO%s" % [game.get("date", ""), game.get("opponent", ""), game.get("best_of", 3)], 16)
		var plan := attendance()
		if not str(plan.get("display_name", "")).is_empty():
			UI.label(box, "比赛地点 · " + str(plan.display_name), 16)
			UI.label(box, str(plan.get("instruction", "")), 13, UI.MUTED)
		var due := bool(game.get("due", false))
		if request_pending:
			var progress := "正在读取本场结果……"
			if pending_action in ["preflight", "veto", "autoveto"]: progress = "正在核对本场比赛、阵容与地图……"
			elif pending_action == "launch": progress = "正在启动 CS2，请稍候……"
			elif pending_action == "collect": progress = "正在检查 CS2 战绩……"
			UI.label(box, progress, 14, UI.MUTED)
		elif due:
			var actions := HBoxContainer.new()
			actions.add_theme_constant_override("separation", 12)
			box.add_child(actions)
			var simulate: Button = host._button(actions, "模拟当前比赛", simulate_match.bind(str(game.get("id", ""))))
			simulate.name = "CareerMatchSimulate"
			if current_preflight().has("can_simulate"): simulate.disabled = simulate.disabled or not bool(current_preflight().get("can_simulate", false))
			UI.primary(simulate)
			var play: Button = host._button(actions, "自己去 CS2 打", prepare_real.bind(str(game.get("id", ""))))
			play.name = "CareerMatchPlayCS2"
			var rts: Button = host._button(actions, "RTS 指挥比赛", open_rts.bind(str(game.get("id", ""))))
			rts.name = "CareerMatchPlayRTS"
			if current_preflight().has("can_simulate"): rts.disabled = rts.disabled or not bool(current_preflight().get("can_simulate", false))
		else:
			UI.label(box, "可以先睡到比赛当天早上，再点“自己去 CS2 打”前往场馆；门口也能选择比赛地点。", 13, UI.MUTED)
			UI.primary(host._button(box, "亲自参赛 · 睡到比赛日", prepare_real.bind(str(game.get("id", "")))))
			host._button(box, "只推进到比赛日", CareerBridge.calendar.bind(str(game.get("date", "")), true))
		if (due and show_real and can_prepare_here()) or str(current_preflight().get("phase", "")) in ["waiting", "starting", "launched"]:
			render_preflight(parent)
	if not notice.is_empty(): UI.label(parent, notice, 13, UI.MUTED)
	if not last_result.is_empty():
		host._button(parent, "查看刚才的完整战报", open_saved.bind(last_result), false)
	UI.label(parent, "本赛季的节奏", 18)
	host._button(parent, "快速赛季 ›", host._navigate.bind("quick"), false)

func render_preflight(parent: Node) -> void:
	var info := current_preflight()
	var card := UI.card(parent)
	UI.label(card, "进入 CS2 前的准备", 19)
	if info.is_empty():
		UI.label(card, "正在核对本场比赛、阵容与地图……", 13, UI.MUTED)
		return
	var blocked := str(info.get("block_reason", ""))
	if not blocked.is_empty():
		UI.label(card, blocked, 14, UI.MUTED)
		if not CareerBridge.context.get("stories", []).is_empty(): host._button(card, "查看赛前决定", host._open_phone.bind("stories"), false)
	var veto: Dictionary = info.get("veto", {})
	# The backend uses null for no active turn (in particular after BP completes).
	# Keep that distinct from an actual turn; do not fabricate another ban/pick.
	var turn = veto.get("turn")
	var completed_veto := bool(veto.get("complete", false))
	var steps: Array = veto.get("steps", [])
	if completed_veto and not steps.is_empty():
		# Keep side/launch controls in view after a long BP. History expands only
		# on an explicit click; status polling never changes scrolling or focus.
		UI.label(card, "地图 BP 已完成 · %d 项记录" % steps.size(), 12, UI.MUTED)
	for step in steps if not completed_veto or veto_history_expanded else []:
		var team_value = step.get("team")
		var team_name := str(team_value) if team_value is String else ""
		var step_label := str({"pick":"选图", "ban":"禁图", "decider":"决胜图"}.get(str(step.get("action", "")), "地图"))
		var step_text := "%s · %s" % [step_label, step.get("map", "")]
		if not team_name.is_empty(): step_text = team_name + " · " + step_text
		UI.label(card, step_text, 12, UI.MUTED)
	var id := str(info.get("match_id", ""))
	if not veto.is_empty() and not veto.get("complete", false) and turn is Dictionary:
		UI.label(card, "%s · %s" % [turn.get("team", ""), "选择地图" if turn.get("action", "") == "pick" else "禁用地图"], 17)
		var choices := HBoxContainer.new()
		card.add_child(choices)
		for map_name in veto.get("available", []):
			var button: Button = host._button(choices, str(map_name).trim_prefix("de_").capitalize(), command.bind("veto", {"match_id":id, "map":map_name}))
			button.disabled = button.disabled or not bool(turn.get("mine", false))
		host._button(card, "交给队长完成地图 BP", command.bind("autoveto", {"match_id":id}))
	var map_value = info.get("pending_map", "")
	# null is the legitimate pre-BP state, not a map named "<null>".
	var map_name := str(map_value.get("map", "")) if map_value is Dictionary else str(map_value) if map_value is String else ""
	if not map_name.is_empty(): UI.label(card, "下一图 · " + map_name.trim_prefix("de_").capitalize(), 17)
	var phase := str(info.get("phase", ""))
	var linked_value = info.get("connection")
	var linked: Dictionary = linked_value if linked_value is Dictionary else connection
	if str(linked.get("match_id", id)) != id: linked = {}
	if phase in ["waiting", "starting", "launched"] or str(linked.get("status", "")) in ["waiting", "failed", "blocked"]:
		UI.label(card, str(linked.get("reason", "CS2 正在进行。赛后会读取这一图的真实结果。")), 14, UI.MUTED)
		if bool(linked.get("can_collect", phase in ["waiting", "starting", "launched"])):
			host._button(card, "检查并录入 CS2 战绩", command.bind("collect", {"match_id":id}))
		if bool(linked.get("can_retry", false)):
			host._button(card, "重试进入 CS2", command.bind("launch", {"match_id":id, "side":str(info.get("side", "ct"))}))
	elif bool(info.get("can_launch", false)) and bool(linked.get("can_launch", false)):
		var row := HBoxContainer.new()
		card.add_child(row)
		UI.primary(host._button(row, "CT 开场 · 进入 CS2", command.bind("launch", {"match_id":id, "side":"ct"})))
		host._button(row, "T 开场 · 进入 CS2", command.bind("launch", {"match_id":id, "side":"t"}))
	elif bool(info.get("can_launch", false)):
		UI.label(card, str(linked.get("reason", "正在确认 CS2 已退出……")), 13, UI.MUTED)
	else:
		var config: Dictionary = info.get("config", {})
		var reason := str(linked.get("reason", config.get("reason", "")))
		if not reason.is_empty() and reason != blocked: UI.label(card, reason, 13, UI.MUTED)
	if completed_veto and not steps.is_empty():
		host._button(card, "收起地图 BP 记录" if veto_history_expanded else "查看地图 BP 记录", toggle_veto_history, false)
	UI.label(card, "路径、Bot Improver 难度和换肤来源在设置中配置。", 12, UI.MUTED)
	host._button(card, "打开 CS2 设置", host._navigate.bind("settings"), false)

func toggle_veto_history() -> void:
	veto_history_expanded = not veto_history_expanded
	host._rebuild()

func simulate_match(id: String) -> void:
	if request_pending or not result.is_empty() or id.is_empty(): return
	pending_match_id = id
	command("simulate", {"match_id":id, "request_id":request_id("match", id)})

func open_rts(id: String) -> void:
	if request_pending or not result.is_empty() or id.is_empty(): return
	host.rts_room.open_career(id)

func prepare_real(id: String) -> void:
	if request_pending or id.is_empty(): return
	if bool(current_game().get("due", false)):
		travel_real(id)
		return
	show_real = false
	pending_match_id = id
	connection.clear()
	# Planning is separate from travelling and does not freeze a future roster.
	command("attend", {"match_id":id, "request_id":request_id("attend", id)})

func travel_real(id: String) -> void:
	if request_pending:
		Travel.finish_door_request("上一项操作正在处理，请稍等。")
		return
	if id.is_empty() or id != str(current_game().get("id", "")):
		Travel.finish_door_request("赛程已更新，请重新选择本场比赛。")
		return
	var plan := attendance()
	if not can_prepare_here() and not bool(plan.get("can_travel", current_game().get("due", false))) and not bool(plan.get("can_return", false)):
		notice = "比赛在 %s，先睡到比赛当天早上。" % current_game().get("date", "")
		Travel.finish_door_request(notice)
		host._rebuild()
		return
	show_real = true
	veto_history_expanded = false
	pending_match_id = id
	connection.clear()
	# The door choice freezes this match's roster before entering the venue.
	venue_after_preflight = id if Travel.menu.request_pending or not can_prepare_here() else ""
	command("preflight", {"match_id":id})

func finish_attendance(plan: Dictionary) -> void:
	var target := str(plan.get("sleep_target", ""))
	if not target.is_empty() and target > str(CareerBridge.context.get("date", "")):
		CareerBridge.calendar(target, true)
		return
	notice = str(plan.get("instruction", "到门口选择本场比赛地点。"))
	CareerBridge.message = notice
	CareerBridge.status_changed.emit()
	host.close_computer()
	Phone.close_phone()

func command(action: String, payload: Dictionary) -> void:
	if request_pending: return
	if action == "launch":
		var venue: Dictionary = current_preflight().get("venue", {})
		var id := str(payload.get("match_id", ""))
		if bool(venue.get("should_walk", false)) and str(venue.get("identity_source", "")) != "frozen_match_rosters":
			venue_after_preflight = id
			command("preflight", {"match_id":id})
			return
		if bool(venue.get("should_walk", false)) and Travel.has_method("is_match_seated") and not Travel.call("is_match_seated", venue, id):
			notice = "先从门口前往 %s，再到你的选手席入座。" % attendance().get("display_name", "比赛场馆")
			host._rebuild()
			return
	var body := payload.duplicate(true)
	body["revision"] = int(CareerBridge.context.get("calendar", {}).get("revision", 0))
	if action == "collect": body["request_id"] = request_id("collect", str(body.get("match_id", "")))
	notice = ""
	if send_command("/api/3d/match/" + action, body):
		request_pending = true
		pending_action = action
		host._rebuild()
	elif action == "preflight":
		venue_after_preflight = ""
		notice = CareerBridge.message if not CareerBridge.message.is_empty() else "比赛准备请求未发出，请稍后再试。"
		Travel.finish_door_request(notice)

func send_command(path: String, body: Dictionary) -> bool:
	if command_sender.is_valid(): return bool(command_sender.call(path, body.duplicate(true)))
	return CareerBridge.command(path, body)

static func request_id(kind: String, id: String) -> String:
	return "%s-%s-%s-%s" % [kind, id.sha256_text().left(16), OS.get_process_id(), Time.get_ticks_usec()]

func begin_reveal(snapshot: Dictionary, timeline: Dictionary = {}) -> void:
	var key := str(snapshot.get("result_id", snapshot.get("id", snapshot.get("match_id", ""))))
	if key.is_empty() or snapshot.get("maps", []).is_empty(): return
	key += "|%d|%s" % [snapshot.get("maps", []).size(), snapshot.get("played", true)]
	if saved_results.has(key):
		last_result = saved_results[key]
		return
	result = snapshot.duplicate(true)
	saved_results[key] = result.duplicate(true)
	last_result = result.duplicate(true)
	if is_instance_valid(CareerBridge.feedback): CareerBridge.feedback.remember_venue_result(snapshot, preflight)
	shown_maps = 0
	reveal_phase = "maps"
	reveal_elapsed = 0.0
	continue_ready = false
	show_real = (str(snapshot.get("source", "")) == "cs2" or str(snapshot.get("maps", [])[-1].get("source", "")) == "cs2") and not bool(snapshot.get("played", true))
	reveal = timeline.duplicate(true)
	reveal_maps = reveal.get("maps", []).duplicate(true)
	if reveal_maps.is_empty():
		for map_row in result.get("maps", []):
			reveal_maps.append({"index":map_row.get("index", reveal_maps.size()), "map":map_row.get("map", ""), "score":map_row.get("score", ""), "winner":map_row.get("winner", ""), "rounds":[], "events_available":false})
	map_cursor = 0
	reset_map_reveal()

func reset_map_reveal() -> void:
	round_cursor = 0
	live_score = [0, 0]
	map_completed = false
	half_pause = 0.0
	reveal_elapsed = 0.0

func open_saved(snapshot: Dictionary) -> void:
	result = snapshot.duplicate(true)
	shown_maps = result.get("maps", []).size()
	reveal_phase = "stats"
	continue_ready = true
	host._navigate("career_match")

func map_art(parent: Node, map_name: String) -> void:
	var paths: Dictionary = CareerBridge.context.get("media", {}).get("map_backgrounds", {})
	var path := str(paths.get(map_name, paths.get(map_name.trim_prefix("de_"), paths.get("de_" + map_name, ""))))
	if path.is_empty() or not FileAccess.file_exists(path): return
	if not textures.has(path):
		var asset := Image.new()
		if asset.load(path) == OK: textures[path] = ImageTexture.create_from_image(asset)
	if not textures.has(path): return
	var art := TextureRect.new()
	art.name = "CareerMatchMapBackground"
	art.texture = textures[path]
	art.custom_minimum_size.y = 95
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(art)

func render_reveal(parent: Node) -> void:
	var presentation := VBoxContainer.new()
	presentation.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	presentation.add_theme_constant_override("separation", 3)
	parent.add_child(presentation)
	parent = presentation
	if reveal_phase != "maps":
		var teams := HBoxContainer.new()
		teams.add_theme_constant_override("separation", 10)
		parent.add_child(teams)
		TeamVisuals.badge(teams, str(result.get("team_a", "")), 28)
		UI.label(teams, "%s  /  %s" % [result.get("team_a", ""), result.get("team_b", "")], 20)
		TeamVisuals.badge(teams, str(result.get("team_b", "")), 28)
	var source_names := {"cs2":"CS2 实战", "rts":"RTS 指挥 · 简化模拟", "mixed":"系列赛 · 混合方式", "simulated":"模拟比赛"}
	UI.label(parent, "%s · %s · %s" % [result.get("event", ""), result.get("date", ""), source_names.get(str(result.get("source", "")), "模拟比赛")], 12, UI.MUTED)
	var maps: Array = result.get("maps", [])
	if reveal_phase == "maps":
		var revealed: Dictionary = reveal_maps[clampi(map_cursor, 0, reveal_maps.size() - 1)]
		var stage := score_stage(parent, str(revealed.get("map", "")), 85)
		var score_row := HBoxContainer.new()
		stage.add_child(score_row)
		score_label = UI.label(score_row, "", 32)
		score_label.name = "CareerLiveScore"
		var stage_details := VBoxContainer.new()
		stage_details.custom_minimum_size.x = 235
		stage_details.size_flags_horizontal = Control.SIZE_SHRINK_END
		stage_details.add_theme_constant_override("separation", 1)
		score_row.add_child(stage_details)
		series_label = UI.label(stage_details, "", 11, UI.MUTED)
		phase_label = UI.label(stage_details, "", 12, UI.MUTED)
		round_label = UI.label(stage_details, "", 11, UI.MUTED)
		for label in [series_label, phase_label, round_label]:
			label.autowrap_mode = TextServer.AUTOWRAP_OFF
			label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		var strip_heading := UI.label(parent, "回合结果   蓝：你方获胜   红：你方失利   ·   12 回合换边", 11, UI.MUTED)
		strip_heading.name = "CareerRoundStripLegend"
		stats_note = strip_heading
		stats_note.autowrap_mode = TextServer.AUTOWRAP_OFF
		stats_note.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		round_strip = RoundStrip.new()
		parent.add_child(round_strip)
		event_label = UI.label(parent, "", 12, UI.INK)
		event_label.name = "CareerRoundEvent"
		event_label.max_lines_visible = 1
		event_label.autowrap_mode = TextServer.AUTOWRAP_OFF
		event_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		stats(parent, current_stat_rows(), "本图即时战绩" if not map_completed else "本图最终战绩")
		paint_round()
	else:
		var stage := score_stage(parent, str(maps[-1].get("map", "")) if not maps.is_empty() else "", 64)
		UI.label(stage, ("最终比分 · " if bool(result.get("played", true)) else "本图已录入 · 系列赛 ") + score_text(result.get("series", "")), 24, winner_color(str(result.get("winner", ""))))
		var recap: Array[String] = []
		for map_row in maps: recap.append("%s %s" % [str(map_row.get("map", "")).trim_prefix("de_").capitalize(), score_text(map_row.get("score", ""))])
		UI.label(stage, "  ·  ".join(recap), 12, UI.MUTED)
		stats(parent, result.get("totals", []))
		if not bool(result.get("data_complete", true)): UI.label(parent, "战绩仍有缺项；缺失的字段按原记录显示。", 12, UI.MUTED)
		var actions := HBoxContainer.new()
		parent.add_child(actions)
		var next: Button = host._button(actions, "下一场" if quick_running else ("准备下一张 CS2 地图" if show_real else "继续"), continue_result, false)
		next.name = "CareerMatchContinue"
		next.custom_minimum_size.y = 31
		next.disabled = false if quick_running else not continue_ready
		UI.primary(next)
		for state in ["normal", "hover", "pressed", "disabled"]: next.add_theme_stylebox_override(state, UI.style(UI.GREEN if state != "disabled" else UI.MINT, 5, 8))
		if not continue_ready and not quick_running: next.text = "先看看本场表现 · 稍后继续"
		if quick_running and not continue_ready: UI.label(actions, "%.0f 秒后自动继续" % STATS_SECONDS, 12, UI.MUTED)
		if quick_running: host._button(actions, "暂停快速赛季", pause_quick, false)
		var is_rts := str(result.get("source", "")) == "rts" or (not maps.is_empty() and str(maps[-1].get("source", "")) == "rts")
		if not bool(result.get("played", true)) and is_rts:
			var resume_rts: Button = host._button(actions, "下一张继续 RTS", Callable(host.rts_room, "resume_series"), false)
			resume_rts.name = "CareerMatchResumeRTS"
			resume_rts.disabled = not continue_ready or not host.rts_room.has_method("resume_series")

func score_stage(parent: Node, map_name: String, height: int) -> VBoxContainer:
	var winner := ""
	if reveal_phase == "maps" and map_completed:
		winner = str(reveal_maps[map_cursor].get("winner", ""))
	elif reveal_phase == "stats":
		winner = str(result.get("winner", ""))
		if not bool(result.get("played", true)) and not result.get("maps", []).is_empty(): winner = str(result.maps[-1].get("winner", ""))
	var surface_color := winner_surface(winner)
	var card := PanelContainer.new()
	card.name = "CareerScoreStage"
	card.custom_minimum_size.y = height
	card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	card.add_theme_stylebox_override("panel", UI.style(surface_color, 8, 10, UI.LINE))
	parent.add_child(card)
	var paths: Dictionary = CareerBridge.context.get("media", {}).get("map_backgrounds", {})
	var path := str(paths.get(map_name, paths.get(map_name.trim_prefix("de_"), paths.get("de_" + map_name, ""))))
	if not path.is_empty() and FileAccess.file_exists(path):
		if not textures.has(path):
			var asset := Image.new()
			if asset.load(path) == OK: textures[path] = ImageTexture.create_from_image(asset)
		if textures.has(path):
			var art := TextureRect.new()
			art.name = "CareerMatchMapBackground"
			art.texture = textures[path]
			art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
			art.mouse_filter = Control.MOUSE_FILTER_IGNORE
			card.add_child(art)
			var veil := ColorRect.new()
			veil.name = "CareerScoreTint"
			veil.color = Color(surface_color, 0.82)
			veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
			card.add_child(veil)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 2)
	card.add_child(column)
	if reveal_phase == "maps": UI.label(column, "第 %d 图 · %s" % [int(reveal_maps[map_cursor].get("index", map_cursor)) + 1, map_name.trim_prefix("de_").capitalize()], 13, UI.MUTED)
	return column

func winner_color(winner: String) -> Color:
	var outcome := winner_outcome(winner)
	return UI.GREEN if outcome == "win" else (Color("a8594d") if outcome == "loss" else UI.INK)

func winner_surface(winner: String) -> Color:
	var outcome := winner_outcome(winner)
	return WIN_SURFACE if outcome == "win" else (LOSS_SURFACE if outcome == "loss" else UI.PAPER)

func winner_outcome(winner: String) -> String:
	var own := str(result.get("player_team", CareerBridge.context.get("team", {}).get("name", "")))
	var teams: Array = [str(result.get("team_a", "")), str(result.get("team_b", ""))]
	if winner.is_empty() or own.is_empty() or winner not in teams or own not in teams: return "unknown"
	return "win" if winner == own else "loss"

func paint_round() -> void:
	if not is_instance_valid(score_label) or reveal_maps.is_empty(): return
	var map_row: Dictionary = reveal_maps[map_cursor]
	score_label.text = score_text(map_row.get("score", "")) if map_completed else "%d : %d" % [live_score[0], live_score[1]]
	score_label.add_theme_color_override("font_color", winner_color(str(map_row.get("winner", ""))) if map_completed else UI.INK)
	phase_label.text = "%s 拿下本图" % map_row.get("winner", "") if map_completed else ("半场休息 · 准备交换攻防" if half_pause > 0 else ("等待开赛" if round_cursor == 0 else ("加时赛" if round_cursor >= 24 else ("上半场" if round_cursor < 12 else "下半场"))))
	if not bool(map_row.get("events_available", false)) and not map_completed: phase_label.text = "没有完整回合记录，稍后展示已保存的比分。"
	round_label.text = "已结束 %d 回合" % round_cursor if round_cursor > 0 else ""
	var series: Array = reveal.get("initial", [0, 0]).duplicate()
	for i in range(map_cursor + (1 if map_completed else 0)):
		var winner := str(reveal_maps[i].get("winner", ""))
		if winner == str(result.get("team_a", "")): series[0] = int(series[0]) + 1
		elif winner == str(result.get("team_b", "")): series[1] = int(series[1]) + 1
	series_label.text = "系列赛 · " + score_text(series)
	if is_instance_valid(round_strip):
		var own := str(result.get("player_team", CareerBridge.context.get("team", {}).get("name", "")))
		var own_side := "a" if own == str(result.get("team_a", "")) else ("b" if own == str(result.get("team_b", "")) else "")
		round_strip.call("configure", map_row.get("rounds", []), round_cursor, own_side)
	if is_instance_valid(event_label):
		event_label.text = round_event_text(map_row)
		event_label.tooltip_text = event_label.text
	if is_instance_valid(scoreboard): scoreboard.call("update_rows", current_stat_rows())
	if is_instance_valid(stats_note):
		var reason := str(map_row.get("round_stats_reason", "回合统计记录未保存；本图结束后显示完整战绩。")) if not map_completed else ""
		stats_note.text = reason if not reason.is_empty() else "回合结果   蓝：你方获胜   红：你方失利   ·   12 回合换边"
		stats_note.tooltip_text = stats_note.text

static func score_text(value: Variant) -> String:
	if value is Array and value.size() >= 2:
		var left := str(int(value[0])) if typeof(value[0]) in [TYPE_INT, TYPE_FLOAT] else str(value[0])
		var right := str(int(value[1])) if typeof(value[1]) in [TYPE_INT, TYPE_FLOAT] else str(value[1])
		return "%s : %s" % [left, right]
	return str(value)

func stats(parent: Node, rows: Array, caption: String = "系列赛完整战绩") -> void:
	var own := str(result.get("player_id", CareerBridge.context.get("player", {}).get("id", "")))
	scoreboard = Scoreboard.mount(parent, rows, [str(result.get("team_a", "")), str(result.get("team_b", ""))], own, select_score_player, caption)

func select_score_player(id: String) -> void:
	host._load_detail("player", id)

func current_stat_rows() -> Array:
	if reveal_maps.is_empty() or result.get("maps", []).is_empty(): return []
	var current: Dictionary = reveal_maps[clampi(map_cursor, 0, reveal_maps.size() - 1)]
	var index := clampi(int(current.get("index", map_cursor)), 0, result.maps.size() - 1)
	var rows: Array = []
	if not map_completed and round_cursor > 0 and bool(current.get("round_stats_available", false)):
		var frames: Array = current.get("round_frames", [])
		if round_cursor <= frames.size(): return frames[round_cursor - 1].get("players", [])
	var players: Dictionary = result.maps[index].get("players", {})
	for team_name in players:
		for player in players[team_name]:
			var entry: Dictionary = player.duplicate(true)
			entry["team"] = team_name
			if not map_completed:
				for field in ["k", "d", "a", "adr", "kast", "rating"]:
					entry[field] = 0 if field in ["k", "d", "a"] and bool(current.get("round_stats_available", false)) else null
			rows.append(entry)
	return rows

func round_event_text(map_row: Dictionary) -> String:
	if round_cursor == 0: return "等待本图第一回合……" if bool(map_row.get("events_available", false)) else "这张地图没有保存回合事件。"
	var frames: Array = map_row.get("round_frames", [])
	if round_cursor > frames.size(): return "第 %d 回合结束 · %s 获胜" % [round_cursor, result.get("team_a", "") if str(map_row.get("rounds", [])[round_cursor - 1]) == "a" else result.get("team_b", "")]
	var frame: Dictionary = frames[round_cursor - 1]
	var parts: Array[String] = ["R%d · %s 获胜" % [round_cursor, frame.get("winner", "")]]
	for highlight in frame.get("highlights", []):
		if highlight.get("kind", "") == "opening": parts.append("%s 首杀 %s" % [highlight.get("name", ""), highlight.get("victim", "")])
		elif highlight.get("kind", "") == "multikill": parts.append("%s %s 杀" % [highlight.get("name", ""), highlight.get("kills", "")])
		elif highlight.get("kind", "") == "objective":
			var reason := str(highlight.get("reason", ""))
			parts.append("拆弹成功" if reason in ["defuse", "defused", "炸弹已拆除"] else ("炸弹爆炸" if reason in ["bomb_exploded", "exploded", "炸弹爆炸"] else "回合时间耗尽"))
	return "  ·  ".join(parts)

func continue_result() -> void:
	if result.is_empty() or (not continue_ready and not (quick_running and reveal_phase == "stats")): return
	var skipped_wait := quick_running and not continue_ready
	result.clear()
	reveal_phase = ""
	quick_elapsed = 0.0
	host._navigate("quick" if quick_running else "career_match", false)
	if skipped_wait: quick_step()

func quick_state() -> Dictionary:
	var quick = CareerBridge.context.get("quick", {})
	return quick if quick is Dictionary else {}

func break_pending(state: Dictionary) -> bool:
	if str(state.get("break_key", "")).is_empty(): return false
	var ack = state.get("break_ack", false)
	return not bool(ack) if ack is bool else str(ack) != str(state.get("break_key", ""))

func render_quick(parent: Node) -> void:
	if not result.is_empty():
		render_reveal(parent)
		return
	var state := quick_state()
	UI.label(parent, "快速赛季", 25)
	UI.label(parent, "一场场展开比赛，赛后留一点时间看完整数据。", 14, UI.MUTED)
	UI.label(parent, "%s 赛季 · %s" % [state.get("year", str(CareerBridge.context.get("date", "")).left(4)), "快速模式" if state.get("mode", "normal") == "quick" else "正常模式"], 18)
	if bool(state.get("can_choose", state.get("choice_required", false))):
		var row := HBoxContainer.new()
		parent.add_child(row)
		var season_label := "下赛季" if state.get("season_phase", "") == "end" else "本赛季"
		UI.primary(host._button(row, season_label + "使用快速模式", choose_mode.bind(true)))
		host._button(row, season_label + "正常进行", choose_mode.bind(false))
	if not str(state.get("block_reason", "")).is_empty(): UI.label(parent, str(state.block_reason), 14, UI.MUTED)
	if state.get("mode", "normal") == "quick":
		if break_pending(state):
			host._button(parent, "结束这次休赛停留，继续赛季", resume_quick)
		elif quick_running:
			UI.label(parent, "快速赛季正在进行。", 16)
			host._button(parent, "暂停快速赛季", pause_quick, false)
		elif not bool(state.get("choice_required", false)):
			UI.primary(host._button(parent, "开始 / 继续快速赛季", start_quick))
	if not CareerBridge.context.get("stories", []).is_empty(): host._button(parent, "查看待处理的队内事件", host._open_phone.bind("stories"), false)
	host._button(parent, "职业比赛中心", host._navigate.bind("career_match"), false)
	if not notice.is_empty(): UI.label(parent, notice, 13, UI.MUTED)

func choose_mode(enabled: bool) -> void:
	var state := quick_state()
	season_command("mode", {"year":int(state.get("year", str(CareerBridge.context.get("date", "2026")).left(4))), "quick_mode":enabled})

func start_quick() -> void:
	if request_pending: return
	quick_running = true
	quick_elapsed = 0.0
	quick_step()

func pause_quick() -> void:
	quick_running = false
	host._rebuild()

func resume_quick() -> void:
	season_command("resume", {"break_key":quick_state().get("break_key", "")})

func season_command(action: String, payload: Dictionary) -> void:
	if request_pending: return
	var body := payload.duplicate(true)
	body["revision"] = int(CareerBridge.context.get("calendar", {}).get("revision", 0))
	if action == "run":
		body["request_id"] = request_id("quick", str(quick_state().get("counter", 0)))
		body["max_steps"] = 1
	if send_command("/api/3d/season/" + action, body):
		request_pending = true
		pending_action = action
		host._rebuild()

func quick_step() -> void:
	if CareerBridge.feedback_active: return
	if not quick_running or request_pending or not result.is_empty() or CareerBridge.busy: return
	if not CareerBridge.context.get("stories", []).is_empty():
		quick_running = false
		host._rebuild()
		return
	season_command("run", {})

func finished(path: String, output: Dictionary) -> bool:
	if not path.begins_with("/api/3d/match/") and not path.begins_with("/api/3d/season/"): return false
	# Historical match detail GETs belong to the workstation's existing browser.
	if path.begins_with("/api/3d/match?"): return false
	var status_probe := path.begins_with("/api/3d/match/status")
	var old_view := JSON.stringify([preflight, connection, notice])
	if not status_probe:
		request_pending = false
		pending_action = ""
	if output.get("preflight") is Dictionary: preflight = output.preflight.duplicate(true)
	if output.get("connection") is Dictionary: connection = output.connection.duplicate(true)
	elif status_probe: connection = output.duplicate(true)
	if (output.has("connection") or status_probe) and connection.get("preflight") is Dictionary: preflight = connection.preflight.duplicate(true)
	if path == "/api/3d/match/collect" and output.get("ok", false): connection.clear()
	notice = str(output.get("reason", output.get("msg", "")))
	if output.get("ok", false):
		# Status success does not mean a match has finished: result is explicitly
		# null until a real saved report exists. Continue connection/UI handling.
		var snapshot = output.get("result")
		if snapshot is Dictionary and not snapshot.is_empty() and snapshot.get("maps", []).size() > 0:
			var timeline = output.get("reveal")
			begin_reveal(snapshot, timeline if timeline is Dictionary else {})
	else:
		quick_running = false
	if status_probe and bool(output.get("result_ready", false)) and not request_pending:
		host.call_deferred("_collect_career_result", str(output.get("match_id", current_preflight().get("match_id", ""))))
	if path.begins_with("/api/3d/season/"):
		var state: Dictionary = output.get("quick", quick_state())
		if str(state.get("phase", "")) in ["paused", "blocked", "finished", "complete", "end", "break", "choice", "story"]: quick_running = false
		quick_elapsed = 0.0
	if path == "/api/3d/match/attend" and output.get("ok", false):
		call_deferred("finish_attendance", output.get("attendance", attendance()).duplicate(true))
		return true
	if path == "/api/3d/match/preflight" and not venue_after_preflight.is_empty():
		var travel_id := venue_after_preflight
		venue_after_preflight = ""
		var venue: Dictionary = preflight.get("venue", {})
		var frozen := str(venue.get("identity_source", "")) == "frozen_match_rosters"
		if output.get("ok", false) and output.get("status", "") != "paused" and str(preflight.get("match_id", "")) == travel_id and frozen and bool(venue.get("travel_allowed", false)) and bool(venue.get("should_walk", false)) and Travel.has_method("go_match"):
			if Travel.call("go_match", venue, travel_id): return true
		elif output.get("ok", false) and output.get("status", "") != "paused" and str(preflight.get("match_id", "")) == travel_id and str(attendance().get("destination", "")) == "club":
			var scene := host.get_tree().current_scene
			if scene != null and scene.scene_file_path != "res://play.tscn":
				Travel.go("club")
				return true
			Travel.menu.set_notice("")
			host.open_app("career_match", "club")
			return true
		var reason := notice if not bool(output.get("ok", false)) or str(output.get("status", "")) == "paused" else "场馆准备未完成，请查看比赛准备。"
		Travel.finish_door_request(reason, not CareerBridge.context.get("stories", []).is_empty())
	if host.screen.visible and host.active_page in ["battle", "career_match", "quick"]:
		if status_probe and old_view == JSON.stringify([preflight, connection, notice]): return true
		if not result.is_empty() and host.active_page == "battle": host._navigate("career_match")
		else: host._rebuild()
	return true

func process(delta: float) -> void:
	if CareerBridge.feedback_active: return
	if not host.screen.visible or host.active_page not in ["career_match", "quick"]: return
	if not result.is_empty():
		if reveal_phase == "maps":
			process_rounds(delta)
			return
		reveal_elapsed += delta
		if reveal_phase == "stats" and not continue_ready and reveal_elapsed >= STATS_SECONDS:
			continue_ready = true
			if quick_running: continue_result()
			else: host._rebuild()
		return
	if quick_running:
		quick_elapsed += delta
		if quick_elapsed >= 0.8:
			quick_elapsed = 0.0
			quick_step()
	var info := current_preflight()
	if show_real and str(info.get("phase", "")) in ["waiting", "starting", "launched", "ready"]:
		poll_elapsed += delta
		if poll_elapsed >= 2.0 and not CareerBridge.busy and not request_pending:
			poll_elapsed = 0.0
			var id := str(info.get("match_id", ""))
			CareerBridge._send("/api/3d/match/status?id=" + id.uri_encode(), {}, false)

func process_rounds(delta: float) -> void:
	if half_pause > 0:
		half_pause = maxf(0, half_pause - delta)
		paint_round()
		return
	reveal_elapsed += delta
	if map_completed:
		if reveal_elapsed < MAP_SECONDS: return
		map_cursor += 1
		if map_cursor >= reveal_maps.size():
			map_cursor = maxi(0, reveal_maps.size() - 1)
			reveal_phase = "stats"
			reveal_elapsed = 0.0
		else: reset_map_reveal()
		host._rebuild()
		return
	var map_row: Dictionary = reveal_maps[map_cursor]
	var rounds: Array = map_row.get("rounds", [])
	if not bool(map_row.get("events_available", false)) or rounds.is_empty():
		if reveal_elapsed >= MAP_SECONDS: complete_map()
		return
	if reveal_elapsed < ROUND_SECONDS: return
	reveal_elapsed = 0.0
	var side := str(rounds[round_cursor])
	if side not in ["a", "b"]:
		map_row["events_available"] = false
		paint_round()
		return
	live_score[0 if side == "a" else 1] += 1
	round_cursor += 1
	if round_cursor >= rounds.size():
		complete_map()
		return
	if round_cursor == 12 or round_cursor == 24 or (round_cursor > 24 and (round_cursor - 24) % 3 == 0): half_pause = HALFTIME_SECONDS
	paint_round()

func complete_map() -> void:
	if map_completed: return
	map_completed = true
	shown_maps += 1
	reveal_elapsed = 0.0
	notify_map_result()
	paint_round()
	host._rebuild()

func notify_map_result() -> void:
	if reveal_maps.is_empty(): return
	var map_row: Dictionary = reveal_maps[map_cursor]
	var own := str(result.get("player_team", CareerBridge.context.get("team", {}).get("name", "")))
	var winner := str(map_row.get("winner", ""))
	if own.is_empty() or winner.is_empty() or winner not in [result.get("team_a", ""), result.get("team_b", "")]: return
	var key := "%s:map:%s:%s" % [result.get("result_id", result.get("match_id", result.get("id", ""))), map_row.get("index", map_cursor), map_row.get("map", "")]
	if notified_maps.has(key): return
	notified_maps[key] = true
	if CareerBridge.has_method("present_map_result"): CareerBridge.call("present_map_result", key, winner == own)
