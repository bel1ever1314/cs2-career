extends RefCounted
## Presentation never settles a match. The engine commits once before any reveal.
const UI = preload("res://scripts/computer_ui.gd")
const Scoreboard = preload("res://scripts/career_match_scoreboard.gd")
const RoundStrip = preload("res://scripts/career_match_round_strip.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")
const Kit = preload("res://scripts/ui_kit.gd")
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
var pace = preload("res://scripts/career_pace_view.gd").new()
var quick_running: bool:
	get: return pace.flow.running
	set(value): pace.flow.running = value
var quick_elapsed := 0.0
var poll_elapsed := 0.0
var notice := ""
var notice_sticky := false
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
	pace.attach(self)

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

func current_connection() -> Dictionary:
	var id := str(current_game().get("id", ""))
	if not connection.is_empty() and str(connection.get("match_id", id)) == id:
		return connection
	var linked = current_preflight().get("connection", {})
	return linked if linked is Dictionary and str(linked.get("match_id", id)) == id else {}

func is_interrupted() -> bool:
	return str(current_connection().get("status", "")) == "interrupted"

## Broadcast tables keep exact pixel sizes so a full ten-player result fits
## one monitor; ordinary pages use the larger device type scale.
func _text(parent: Node, value: String, size: int = 14, color: Color = UI.INK) -> Label:
	return UI.label_exact(parent, value, size, color) if is_presenting() else UI.label(parent, value, size, color)

func is_presenting() -> bool:
	return request_pending or not result.is_empty()

const STAGE_NAMES := {"GF":"总决赛", "SF":"半决赛", "QF":"四分之一决赛", "R16":"十六强", "LB":"败者组", "UB":"胜者组", "GS":"小组赛", "SW":"瑞士轮"}

func _stage_name(code: String) -> String:
	return str(STAGE_NAMES.get(code.to_upper(), code))

func render(parent: Node) -> void:
	if not result.is_empty():
		render_reveal(parent)
		return
	var game := current_game()
	if game.is_empty():
		Kit.empty_state(parent, UI, "match", "还没有下一场比赛", "接受赛事邀请后，赛程会出现在这里。")
		host._button(parent, "查看赛事日程", host._navigate.bind("events"), false)
		_match_footer(parent)
		return
	var own := str(CareerBridge.context.get("team", {}).get("name", ""))
	var plan := attendance()
	var details: Array[String] = [Kit.short_date(str(game.get("date", ""))) if str(game.get("date", "")).length() >= 10 else str(game.get("date", ""))]
	if not str(game.get("stage", "")).is_empty(): details.append(_stage_name(str(game.get("stage", ""))))
	details.append("BO%s" % game.get("best_of", 3))
	if not str(plan.get("display_name", "")).is_empty(): details.append(str(plan.display_name))
	var due := bool(game.get("due", false))
	var preparing := (due and pace.enabled()) or (due and show_real and can_prepare_here()) or str(current_preflight().get("phase", "")) in ["waiting", "starting", "launched"] or is_interrupted()
	if preparing:
		_text(parent, str(game.get("event", "")) + " · " + " · ".join(details), 13, UI.MUTED)
		var teams := HFlowContainer.new()
		teams.add_theme_constant_override("h_separation", 10)
		parent.add_child(teams)
		TeamVisuals.badge(teams, own, 28)
		_text(teams, own + "  /  " + str(game.get("opponent", "")), 17)
		TeamVisuals.badge(teams, str(game.get("opponent", "")), 28)
	else:
		Kit.match_hero(parent, UI, own, str(game.get("opponent", "")), str(game.get("event", "下一场比赛")), " · ".join(details), str(game.get("tier", game.get("event_type", ""))))
	# Once at the venue, BP and launch are the primary action. Keep them above
	# alternative modes so the side buttons stay visible in a 720p window.
	if preparing:
		render_preflight(parent)
	if request_pending:
		var progress := "正在读取本场结果……"
		if pending_action in ["preflight", "veto", "autoveto"]: progress = "正在核对本场比赛、阵容与地图……"
		elif pending_action == "launch": progress = "正在启动 CS2……"
		elif pending_action == "collect": progress = "正在读取 CS2 战绩……"
		_text(parent, progress, 14, UI.MUTED)
	elif due:
		if not pace.enabled():
			var actions := HBoxContainer.new()
			actions.add_theme_constant_override("separation", 12)
			parent.add_child(actions)
			var simulate: Button = host._button(actions, "模拟当前地图", simulate_match.bind(str(game.get("id", ""))))
			simulate.name = "CareerMatchSimulate"
			if current_preflight().has("can_simulate"): simulate.disabled = simulate.disabled or not bool(current_connection().get("can_simulate", current_preflight().get("can_simulate", false)))
			Kit.action_tile(simulate, UI, "模拟比赛", "直接出结果，看逐回合战报", true)
			var play: Button = host._button(actions, "自己去 CS2 打", prepare_real.bind(str(game.get("id", ""))))
			play.name = "CareerMatchPlayCS2"
			Kit.action_tile(play, UI, "亲自上场", "进入 CS2 打这场比赛")
			var rts: Button = host._button(actions, "RTS 指挥比赛", open_rts.bind(str(game.get("id", ""))))
			rts.name = "CareerMatchPlayRTS"
			if current_preflight().has("can_simulate"): rts.disabled = rts.disabled or not bool(current_connection().get("can_rts", current_preflight().get("can_simulate", false)))
			Kit.action_tile(rts, UI, "场边指挥", "俯视地图，指挥队伍打完")
	else:
		var actions := HBoxContainer.new()
		actions.add_theme_constant_override("separation", 12)
		parent.add_child(actions)
		var attend: Button = host._button(actions, "亲自参赛 · 睡到比赛日", prepare_real.bind(str(game.get("id", ""))))
		Kit.action_tile(attend, UI, "睡到比赛日", "比赛当天早上去现场", true)
		var skip: Button = host._button(actions, "只推进到比赛日", CareerBridge.calendar.bind(str(game.get("date", "")), true))
		Kit.action_tile(skip, UI, "推进到比赛日", "跳过中间的日子")
	if not notice.is_empty(): _text(parent, notice, 13, UI.MUTED)
	if not last_result.is_empty():
		host._button(parent, "查看刚才的完整战报", open_saved.bind(last_result), false)
	_match_footer(parent)

func _match_footer(parent: Node) -> void:
	var recent: Array = CareerBridge.context.get("recent_matches", [])
	if not recent.is_empty():
		Kit.section(parent, UI, "最近比赛", "", 16)
		for game_row in recent.slice(0, 5):
			var series = game_row.get("series", [])
			var score := "%s : %s" % [series[0], series[1]] if series is Array and series.size() == 2 else ""
			var row_button := Button.new()
			row_button.text = "%s %s %s" % [game_row.get("team_a", ""), score, game_row.get("team_b", "")]
			row_button.focus_mode = Control.FOCUS_ALL
			parent.add_child(row_button)
			Kit.rich_row(row_button, UI, row_button.text, "%s · %s" % [Kit.short_date(str(game_row.get("date", ""))), game_row.get("event", "")], "", "", "gray", "match")
			row_button.pressed.connect(host._load_detail.bind("match", str(game_row.get("id", ""))))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	parent.add_child(row)
	UI.compact(host._button(row, "生涯推进 ›", host._navigate.bind("quick"), false))
	UI.compact(host._button(row, "赛事日程 ›", host._navigate.bind("events"), false))

var bp_preview_map := ""

func preview_bp(map_code: String) -> void:
	bp_preview_map = map_code
	host._rebuild()

func render_preflight(parent: Node) -> void:
	var info := current_preflight()
	var card := UI.card(parent)
	card.add_theme_constant_override("separation", 6)
	if not pace.enabled(): _text(card, "进入 CS2 前的准备" if show_real else "比赛准备", 19)
	if info.is_empty():
		_text(card, "正在核对本场比赛、阵容与地图……", 13, UI.MUTED)
		return
	var blocked := str(info.get("block_reason", ""))
	if not blocked.is_empty():
		_text(card, blocked, 14, UI.MUTED)
		if not CareerBridge.context.get("stories", []).is_empty(): host._button(card, "查看赛前决定", host._open_phone.bind("stories"), false)
	var veto: Dictionary = info.get("veto", {})
	# The backend uses null for no active turn (in particular after BP completes).
	# Keep that distinct from an actual turn; do not fabricate another ban/pick.
	var turn = veto.get("turn")
	var completed_veto := bool(veto.get("complete", false))
	var steps: Array = veto.get("steps", [])
	var id := str(info.get("match_id", ""))
	if not completed_veto and turn is Dictionary:
		render_bp(card, info, turn)
	elif not bool(veto.get("initialized", false)) and not bool(info.get("session_pending", false)):
		render_before_bp(card, info)
	var map_name := ""
	if completed_veto or bool(info.get("session_pending", false)) or info.get("pending_map") is String:
		map_name = render_current_map(card, info)
	var map_title := map_label(map_name)
	var phase := str(info.get("phase", ""))
	var linked := current_connection()
	if str(linked.get("status", "")) == "interrupted":
		_text(card, str(linked.get("reason", "CS2 已退出，本场比赛尚未结束。")), 15)
		var recovery := HFlowContainer.new()
		recovery.add_theme_constant_override("h_separation", 8)
		card.add_child(recovery)
		if bool(linked.get("can_resume", false)):
			var resume: Button = host._button(recovery, "重新进入 CS2 · 重开当前图", resume_real.bind(id))
			resume.name = "CareerMatchResumeCS2"
			UI.primary(resume)
		if bool(linked.get("can_simulate", false)):
			var simulate: Button = host._button(recovery, "模拟当前未完成地图", simulate_match.bind(id))
			simulate.name = "CareerMatchResumeSimulate"
		if bool(linked.get("can_rts", false)):
			var rts: Button = host._button(recovery, "切换 RTS · 重开当前图", open_rts.bind(id), false)
			rts.name = "CareerMatchResumeRTS"
		_text(card, "重新进入会重开当前未完成地图；已完成的地图和战绩保留。", 12, UI.MUTED)
	elif phase in ["waiting", "starting", "launched"] or str(linked.get("status", "")) in ["waiting", "failed", "blocked"]:
		if not map_title.is_empty() and phase in ["waiting", "starting", "launched"]:
			var guide := _text(card, "CS2 里请打 %s，阵营 %s。地图或阵营不对，这张图的战绩不会录入。" % [map_title, side_label(str(info.get("side", "ct")))], 15)
			guide.name = "CareerMatchPlayGuide"
			guide.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		var live_actions := HFlowContainer.new()
		live_actions.add_theme_constant_override("h_separation", 8)
		card.add_child(live_actions)
		if bool(linked.get("can_collect", phase in ["waiting", "starting", "launched"])):
			UI.primary(host._button(live_actions, "检查并录入 CS2 战绩", command.bind("collect", {"match_id":id})))
		if bool(linked.get("can_retry", false)):
			host._button(live_actions, "重试进入 CS2", command.bind("launch", {"match_id":id, "side":str(info.get("side", "ct"))}))
		_text(card, str(linked.get("reason", "CS2 正在进行。赛后会读取这一图的真实结果。")), 13, UI.MUTED)
	elif bool(info.get("can_launch", false)) and bool(linked.get("can_launch", false)) and (show_real or not pace.enabled()) and bool(info.get("venue", {}).get("should_walk", false)) and not can_prepare_here():
		var destination := str(attendance().get("display_name", "比赛场馆"))
		UI.primary(host._button(card, "前往 %s 入座" % destination, travel_real.bind(id)))
		_text(card, "这是线下比赛，到你的选手席入座后再选择 CT／T 开场。", 13, UI.MUTED)
	elif bool(info.get("can_launch", false)) and bool(linked.get("can_launch", false)) and (show_real or not pace.enabled()):
		var row := HFlowContainer.new()
		row.add_theme_constant_override("h_separation", 8)
		card.add_child(row)
		var ct_text := "CT 开场 · 进入 CS2 打 %s" % map_title if not map_title.is_empty() else "CT 开场 · 进入 CS2"
		var t_text := "T 开场 · 进入 CS2 打 %s" % map_title if not map_title.is_empty() else "T 开场 · 进入 CS2"
		UI.primary(host._button(row, ct_text, command.bind("launch", {"match_id":id, "side":"ct"})))
		host._button(row, t_text, command.bind("launch", {"match_id":id, "side":"t"}))
		if not map_title.is_empty():
			var launch_steps := _text(card, "进入 CS2 后：与机器人游戏 → 竞技 → 选 %s，再加入你在这里选的开局阵营。" % map_title, 12, UI.MUTED)
			launch_steps.name = "CareerMatchLaunchSteps"
			launch_steps.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	elif bool(info.get("can_launch", false)) and (show_real or not pace.enabled()):
		_text(card, str(linked.get("reason", "正在确认 CS2 已退出……")), 13, UI.MUTED)
	elif not pace.enabled() or show_real:
		var config: Dictionary = info.get("config", {})
		var reason := str(linked.get("reason", config.get("reason", "")))
		if not reason.is_empty() and reason != blocked: _text(card, reason, 13, UI.MUTED)
	if completed_veto and not steps.is_empty() and not (info.get("series_maps", []) is Array and not info.get("series_maps", []).is_empty()):
		# Keep side/launch controls in view after a long BP. History expands only
		# on an explicit click; status polling never changes scrolling or focus.
		_text(card, "地图 BP 已完成 · %d 项记录" % steps.size(), 12, UI.MUTED)
	for step in steps if veto_history_expanded else []:
		var team_value = step.get("team")
		var team_name := str(team_value) if team_value is String else ""
		var step_label := str({"pick":"选图", "ban":"禁图", "decider":"决胜图"}.get(str(step.get("action", "")), "地图"))
		var step_text := "%s · %s" % [step_label, step.get("map", "")]
		if not team_name.is_empty(): step_text = team_name + " · " + step_text
		_text(card, step_text, 12, UI.MUTED)
	var links := HBoxContainer.new()
	links.add_theme_constant_override("separation", 8)
	card.add_child(links)
	if not steps.is_empty():
		UI.compact(host._button(links, "收起地图 BP 记录" if veto_history_expanded else "查看地图 BP 记录", toggle_veto_history, false))
	UI.compact(host._button(links, "CS2 设置 ›", host._navigate.bind("settings"), false))

## Before any BP: say what happens automatically and show both teams' maps.
func render_before_bp(card: Node, info: Dictionary) -> void:
	var intro := HBoxContainer.new()
	intro.add_theme_constant_override("separation", 10)
	card.add_child(intro)
	var note := _text(intro, "第 1 图开始前由队长自动完成地图 BP。想自己选图，可以手动 BP。", 14)
	note.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var manual: Button = host._button(intro, "手动 BP", manual_bp, false)
	manual.name = "CareerMatchManualBP"
	UI.compact(manual)
	var rows := map_matchup(info)
	if rows.is_empty(): return
	_text(card, "双方地图评价 · 你方 : 对手", 12, UI.MUTED)
	var grid := HFlowContainer.new()
	grid.name = "CareerMatchMapForm"
	grid.add_theme_constant_override("h_separation", 6)
	grid.add_theme_constant_override("v_separation", 6)
	card.add_child(grid)
	for row in rows:
		var tile := Kit.chip(grid, "%s  %s" % [map_label(str(row.map)), row.text], str(row.tone), 13)
		tile.tooltip_text = str(row.detail)

## Manual BP: compare maps on the tiles, preview one, confirm it here.
func render_bp(card: Node, info: Dictionary, turn: Dictionary) -> void:
	var available: Array = info.get("veto", {}).get("available", [])
	if bp_preview_map not in available: bp_preview_map = str(available[0]) if not available.is_empty() else ""
	var mine := bool(turn.get("mine", false))
	var picking := str(turn.get("action", "")) == "pick"
	var id := str(info.get("match_id", ""))
	var rows := {}
	for row in map_matchup(info): rows[str(row.map)] = row
	if not bp_preview_map.is_empty():
		var preview: Dictionary = rows.get(bp_preview_map.trim_prefix("de_"), {})
		TeamVisuals.map_banner(card, bp_preview_map, str(preview.get("detail", "BP 地图预览 · %s / %s" % [info.get("team_a", ""), info.get("team_b", "")])), 72)
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 8)
	card.add_child(head)
	var title := ("轮到你方选图" if picking else "轮到你方禁图") if mine else "%s · %s" % [turn.get("team", ""), "选择地图" if picking else "禁用地图"]
	var heading := _text(head, title, 17)
	heading.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var confirm: Button = host._button(head, ("确认选择 %s" if picking else "确认禁用 %s") % map_label(bp_preview_map), command.bind("veto", {"match_id":id, "map":bp_preview_map}))
	confirm.name = "ConfirmVetoMap"
	confirm.disabled = confirm.disabled or not mine or bp_preview_map.is_empty()
	UI.compact(confirm)
	if mine: UI.primary(confirm)
	UI.compact(host._button(head, "交给队长完成 BP", command.bind("autoveto", {"match_id":id}), false))
	var choices := HFlowContainer.new()
	choices.add_theme_constant_override("h_separation", 6)
	choices.add_theme_constant_override("v_separation", 6)
	card.add_child(choices)
	for map_name in available:
		var row: Dictionary = rows.get(str(map_name).trim_prefix("de_"), {})
		var caption := map_label(str(map_name)) + ("  " + str(row.text) if not row.is_empty() else "")
		var button: Button = host._button(choices, caption, preview_bp.bind(str(map_name)), false)
		button.name = "VetoPreview_" + str(map_name)
		button.tooltip_text = str(row.get("detail", ""))
		if str(map_name) == bp_preview_map: UI.primary(button)
		elif str(row.get("tone", "")) == "green": button.add_theme_color_override("font_color", UI.GREEN)
		elif str(row.get("tone", "")) == "red": button.add_theme_color_override("font_color", Color("a8594d"))
	var done := HFlowContainer.new()
	done.name = "CareerMatchVetoSoFar"
	done.add_theme_constant_override("h_separation", 14)
	for step in info.get("veto", {}).get("steps", []):
		var who := str(step.get("team")) if step.get("team") is String else ""
		var action := str(step.get("action", ""))
		var text := "决胜 %s" % map_label(str(step.get("map", "")))
		if action == "pick": text = "%s 选 %s" % [who, map_label(str(step.get("map", "")))]
		elif action == "ban": text = "%s 禁 %s" % [who, map_label(str(step.get("map", "")))]
		var entry := _text(done, text, 12, UI.MUTED)
		entry.autowrap_mode = TextServer.AUTOWRAP_OFF
		entry.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	if done.get_child_count() > 0: card.add_child(done)
	else: done.free()

## Both teams' current form for each map, own team first.
func map_matchup(info: Dictionary) -> Array:
	var performances = info.get("map_performance", {})
	if not performances is Dictionary or performances.is_empty(): return []
	var own := str(CareerBridge.context.get("team", {}).get("name", ""))
	var opponent := str(info.get("team_b", "")) if own == str(info.get("team_a", "")) else str(info.get("team_a", ""))
	if not performances.has(own): own = str(info.get("team_a", ""))
	var lookup := func(team: String) -> Dictionary:
		var by_map := {}
		for item in performances.get(team, []): by_map[str(item.get("map", ""))] = item
		return by_map
	var mine: Dictionary = lookup.call(own)
	var theirs: Dictionary = lookup.call(opponent)
	var labels := {"strong":"强图", "neutral":"常规", "weak":"弱图"}
	var out := []
	for map_name in mine:
		var a: Dictionary = mine[map_name]
		var b: Dictionary = theirs.get(map_name, {})
		var diff := float(a.get("rating", 0)) - float(b.get("rating", 0))
		out.append({"map":map_name, "text":"%.0f : %.0f" % [float(a.get("rating", 0)), float(b.get("rating", 0))],
			"tone":"green" if diff >= 3.0 else ("red" if diff <= -3.0 else "gray"),
			"detail":"%s · %.1f · %s     /     %s · %.1f · %s" % [own, float(a.get("rating", 0)), labels.get(str(a.get("label", "neutral")), "常规"),
				opponent, float(b.get("rating", 0)), labels.get(str(b.get("label", "neutral")), "常规")]})
	return out

## Scenic banner for the map in play plus the series order. Returns its code.
func render_current_map(card: Node, info: Dictionary) -> String:
	var listed = info.get("series_maps", [])
	var rows: Array = listed if listed is Array else []
	var current: Dictionary = {}
	for row in rows:
		if row is Dictionary and str(row.get("state", "")) in ["live", "next"]:
			current = row
			break
	var pending = info.get("pending_map")
	var code := str(current.get("map", "")) if not current.is_empty() else (str(pending.get("map", "")) if pending is Dictionary else str(pending) if pending is String else "")
	if code.is_empty(): return ""
	var number := int(current.get("index", int(info.get("maps_done", 0)) + 1))
	var state := str(current.get("state", "next"))
	var interrupted := str(current_connection().get("status", "")) == "interrupted"
	var subtitle := ""
	if interrupted: subtitle = "正在进行 · 第%d图 %s · CS2 已退出，本图未完成" % [number, map_label(code)]
	elif state == "live": subtitle = "正在进行 · 第%d图 %s · 你在 %s 方" % [number, map_label(code), str(current.get("side", info.get("side", "ct"))).to_upper()]
	else:
		var picked := str(current.get("picked_by", ""))
		subtitle = "本图 · 第%d图 %s" % [number, map_label(code)]
		if bool(current.get("decider", false)): subtitle = "本图 · 第%d图 %s · 决胜图" % [number, map_label(code)]
		elif not picked.is_empty(): subtitle = "本图 · 第%d图 %s · %s 选图" % [number, map_label(code), picked]
	var banner := TeamVisuals.map_banner(card, code, subtitle, 72)
	banner.get_parent().name = "CareerMatchCurrentMap"
	if not rows.is_empty(): series_strip(card, rows)
	return code

func series_strip(card: Node, rows: Array) -> void:
	var strip := HBoxContainer.new()
	strip.name = "CareerMatchSeriesMaps"
	strip.add_theme_constant_override("separation", 22)
	card.add_child(strip)
	for row in rows:
		if not row is Dictionary: continue
		var state := str(row.get("state", ""))
		var cell := HBoxContainer.new()
		cell.name = "CareerMatchSeriesMap%d" % int(row.get("index", 0))
		cell.add_theme_constant_override("separation", 6)
		strip.add_child(cell)
		var highlight := state in ["live", "next"]
		var title := _text(cell, "第%d图 · %s" % [int(row.get("index", 0)), map_label(str(row.get("map", "")))], 12, UI.INK if highlight else UI.MUTED)
		title.autowrap_mode = TextServer.AUTOWRAP_OFF
		var detail := "决胜图" if bool(row.get("decider", false)) else "待定"
		var color := UI.MUTED
		if state == "done":
			var won := bool(row.get("won", false))
			detail = ("胜 %s" if won else "负 %s") % str(row.get("score", ""))
			color = UI.GREEN if won else Color("a8594d")
		elif state == "live":
			detail = "正在进行"
			color = UI.AMBER
		elif state == "next":
			detail = "本图"
			color = UI.INK
		elif state == "unneeded":
			detail = "未进行"
		var status := _text(cell, detail, 12, color)
		status.autowrap_mode = TextServer.AUTOWRAP_OFF

static func map_label(code: String) -> String:
	return code.trim_prefix("de_").capitalize()

static func side_label(side: String) -> String:
	return "T（恐怖分子）" if side == "t" else "CT（反恐精英）"

func toggle_veto_history() -> void:
	veto_history_expanded = not veto_history_expanded
	host._rebuild()

func manual_bp() -> void:
	pace.pause(false)
	command("preflight", {"match_id":str(current_game().get("id", ""))})

func simulate_match(id: String) -> void:
	if request_pending or not result.is_empty() or id.is_empty(): return
	if pace.enabled(): pace.flow.resume()
	pending_match_id = id
	command("simulate", {"match_id":id, "request_id":request_id("match", id), "scope":"current_map", "map_key":str(current_preflight().get("map_key", ""))})

func open_rts(id: String) -> void:
	if request_pending or not result.is_empty() or id.is_empty(): return
	pace.flow.arm("playing", str(current_preflight().get("map_key", "")))
	pace.flow.next_mode = "rts"
	if not can_prepare_here():
		prepare_real(id)
		return
	pace.flow.next_mode = ""
	host.rts_room.open_career(id)

func resume_real(id: String) -> void:
	if request_pending or not bool(current_connection().get("can_resume", false)): return
	if can_prepare_here():
		command("launch", {"match_id":id, "side":str(current_preflight().get("side", "ct"))})
	else:
		travel_real(id)

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
			launch_blocked("先从门口前往 %s，再到你的选手席入座。" % attendance().get("display_name", "比赛场馆"))
			return
	var body := payload.duplicate(true)
	if action in ["simulate", "launch", "veto", "autoveto", "preflight"]:
		body["map_key"] = str(current_preflight().get("map_key", ""))
	if not body.has("request_id"): body["request_id"] = request_id(action, str(body.get("match_id", "")))
	body["revision"] = int(CareerBridge.context.get("calendar", {}).get("revision", 0))
	if action == "collect": body["request_id"] = request_id("collect", str(body.get("match_id", "")))
	notice = ""
	notice_sticky = false
	if send_command("/api/3d/match/" + action, body):
		if action == "launch":
			pace.flow.resume()
			pace.flow.arm("playing", str(current_preflight().get("map_key", "")))
		pace.flow.in_flight = true
		request_pending = true
		pending_action = action
		host._rebuild()
	elif action == "launch":
		launch_blocked(CareerBridge.message if not CareerBridge.message.is_empty() else "启动请求未发出，请稍后重试。")
	elif action == "preflight":
		venue_after_preflight = ""
		notice = CareerBridge.message if not CareerBridge.message.is_empty() else "比赛准备请求未发出，请稍后再试。"
		Travel.finish_door_request(notice)

func launch_blocked(reason: String) -> void:
	pace.pause(false)
	pace.flow.arm("paused", str(current_preflight().get("map_key", "")))
	pace.flow.next_mode = ""
	notice = reason
	notice_sticky = true
	CareerBridge.message = reason
	CareerBridge.status_changed.emit()
	host._rebuild()

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
	pace.flow.in_flight = false
	pace.flow.arm("reveal", pace.next_cursor())
	if bool(snapshot.get("played", false)): pace.flow.clear_reservation()
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
	pace.pause(false)
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
		_text(teams, "%s  /  %s" % [result.get("team_a", ""), result.get("team_b", "")], 20)
		TeamVisuals.badge(teams, str(result.get("team_b", "")), 28)
	var source_names := {"cs2":"CS2 实战", "rts":"RTS 指挥 · 简化模拟", "mixed":"系列赛 · 混合方式", "simulated":"模拟比赛"}
	_text(parent, "%s · %s · %s" % [result.get("event", ""), result.get("date", ""), source_names.get(str(result.get("source", "")), "模拟比赛")], 12, UI.MUTED)
	var maps: Array = result.get("maps", [])
	if reveal_phase == "maps":
		var revealed: Dictionary = reveal_maps[clampi(map_cursor, 0, reveal_maps.size() - 1)]
		var stage := score_stage(parent, str(revealed.get("map", "")), 96)
		var score_row := HBoxContainer.new()
		score_row.add_theme_constant_override("separation", 14)
		stage.add_child(score_row)
		# Broadcast layout: team A · score · team B, details on the right.
		var spacer := Control.new(); score_row.add_child(spacer)
		var middle := HBoxContainer.new()
		middle.alignment = BoxContainer.ALIGNMENT_CENTER
		middle.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		middle.add_theme_constant_override("separation", 14)
		score_row.add_child(middle)
		_score_team(middle, str(result.get("team_a", "")), true)
		score_label = _text(middle, "", 34)
		score_label.name = "CareerLiveScore"
		score_label.autowrap_mode = TextServer.AUTOWRAP_OFF
		score_label.custom_minimum_size.x = 110
		score_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_score_team(middle, str(result.get("team_b", "")), false)
		var stage_details := VBoxContainer.new()
		stage_details.custom_minimum_size.x = 135
		stage_details.size_flags_horizontal = Control.SIZE_SHRINK_END
		stage_details.add_theme_constant_override("separation", 1)
		score_row.add_child(stage_details)
		series_label = _text(stage_details, "", 11, UI.MUTED)
		phase_label = _text(stage_details, "", 12, UI.MUTED)
		round_label = _text(stage_details, "", 11, UI.MUTED)
		for label in [series_label, phase_label, round_label]:
			label.autowrap_mode = TextServer.AUTOWRAP_OFF
			label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		var strip_heading := _text(parent, "回合结果   蓝：你方获胜   红：你方失利   ·   12 回合换边", 11, UI.MUTED)
		strip_heading.name = "CareerRoundStripLegend"
		stats_note = strip_heading
		stats_note.autowrap_mode = TextServer.AUTOWRAP_OFF
		stats_note.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		round_strip = RoundStrip.new()
		parent.add_child(round_strip)
		event_label = _text(parent, "", 12, UI.INK)
		event_label.name = "CareerRoundEvent"
		event_label.max_lines_visible = 1
		event_label.autowrap_mode = TextServer.AUTOWRAP_OFF
		event_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		stats(parent, current_stat_rows(), "本图即时战绩" if not map_completed else "本图最终战绩")
		paint_round()
	else:
		var stage := score_stage(parent, str(maps[-1].get("map", "")) if not maps.is_empty() else "", 64)
		_text(stage, ("最终比分 · " if bool(result.get("played", true)) else "本图已录入 · 系列赛 ") + score_text(result.get("series", "")), 24, winner_color(str(result.get("winner", ""))))
		var recap: Array[String] = []
		for map_row in maps: recap.append("%s %s" % [str(map_row.get("map", "")).trim_prefix("de_").capitalize(), score_text(map_row.get("score", ""))])
		_text(stage, "  ·  ".join(recap), 12, UI.MUTED)
		if not bool(result.get("played", true)):
			# The next map sits above the long table, next to the dock that starts it.
			var info := current_preflight()
			var next_map := str(info.get("pending_map", "")) if info.get("pending_map") is String else ""
			if not next_map.is_empty():
				var next_line := _text(parent, "下一张 · 第%d图 %s · 系列赛 %s" % [maps.size() + 1, map_label(next_map), score_text(result.get("series", ""))], 15)
				next_line.name = "CareerMatchNextMap"
		preload("res://scripts/map_form_panel.gd").changes(parent, maps)
		stats(parent, result.get("totals", []))
		if not bool(result.get("data_complete", true)): _text(parent, "战绩仍有缺项；缺失的字段按原记录显示。", 12, UI.MUTED)

func _score_team(parent: Node, team: String, left: bool) -> void:
	var box := HBoxContainer.new()
	box.add_theme_constant_override("separation", 8)
	box.alignment = BoxContainer.ALIGNMENT_END if left else BoxContainer.ALIGNMENT_BEGIN
	box.custom_minimum_size.x = 130
	parent.add_child(box)
	var name_label := _text(box, team, 17)
	name_label.autowrap_mode = TextServer.AUTOWRAP_OFF
	name_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT if left else HORIZONTAL_ALIGNMENT_LEFT
	name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var mark := TeamVisuals.badge(box, team, 40)
	if mark and left: box.move_child(mark, box.get_child_count() - 1)
	elif mark: box.move_child(mark, 0)

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
			veil.color = Color(surface_color, 0.74)
			veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
			card.add_child(veil)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 2)
	card.add_child(column)
	if reveal_phase == "maps": _text(column, "第 %d 图 · %s" % [int(reveal_maps[map_cursor].get("index", map_cursor)) + 1, map_name.trim_prefix("de_").capitalize()], 13, UI.MUTED)
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
	# Saved string scores ("13-9") use the same broadcast spacing.
	var text := str(value)
	var parts := text.split("-")
	if parts.size() == 2 and parts[0].strip_edges().is_valid_int() and parts[1].strip_edges().is_valid_int():
		return "%s : %s" % [parts[0].strip_edges(), parts[1].strip_edges()]
	return text

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
	pace.primary()


func quick_state() -> Dictionary:
	var quick = CareerBridge.context.get("quick", {})
	return quick if quick is Dictionary else {}

func break_pending(state: Dictionary) -> bool:
	if str(state.get("break_key", "")).is_empty(): return false
	var ack = state.get("break_ack", false)
	return not bool(ack) if ack is bool else str(ack) != str(state.get("break_key", ""))

func render_quick(parent: Node) -> void:
	if not result.is_empty(): render_reveal(parent)
	else: pace.render(parent)


func choose_mode(_enabled: bool) -> void:
	pace.start()


func start_quick() -> void:
	pace.start()


func pause_quick() -> void:
	pace.pause()


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
	pace.process(0.0)


func finished(path: String, output: Dictionary) -> bool:
	if not path.begins_with("/api/3d/match/") and not path.begins_with("/api/3d/season/"): return false
	# Historical match detail GETs belong to the workstation's existing browser.
	if path.begins_with("/api/3d/match?"): return false
	var status_probe := path.begins_with("/api/3d/match/status")
	if status_probe and outdated_status(output): return true
	var old_view := JSON.stringify([preflight, connection, notice])
	if not status_probe:
		pace.finished(path, output)
		request_pending = false
		pending_action = ""
	if output.get("result_summary", false):
		quick_running = false
		venue_after_preflight = ""
		notice_sticky = false
		notice = str(output.get("reason", output.get("msg", "操作已保存，请查看比赛记录。")))
		if host.screen.visible: host._rebuild()
		return true
	if output.get("preflight") is Dictionary: preflight = output.preflight.duplicate(true)
	if output.get("connection") is Dictionary: connection = output.connection.duplicate(true)
	elif status_probe: connection = output.duplicate(true)
	elif output.get("ok", false) and output.get("preflight") is Dictionary:
		# A committed map/preparation owns the new cursor. A cached CS2 exit
		# belongs to the previous map, even when this is still the same BO.
		connection.clear()
	if (output.has("connection") or status_probe) and connection.get("preflight") is Dictionary: preflight = connection.preflight.duplicate(true)
	# Background status reads must not erase the explanation for a rejected
	# click. A new explicit command (or its result) owns this notice instead.
	if not status_probe:
		notice_sticky = not bool(output.get("ok", false)) or str(output.get("status", "")) in ["failed", "blocked", "paused"]
	if not status_probe or not notice_sticky:
		notice = str(output.get("reason", output.get("msg", "")))
	if output.get("ok", false):
		# Status success does not mean a match has finished: result is explicitly
		# null until a real saved report exists. Continue connection/UI handling.
		var snapshot = output.get("result")
		# Polling includes previously saved maps, not a newly settled result.
		# Replaying those would hide recovery/side controls for the live map.
		if not status_probe and snapshot is Dictionary and not snapshot.is_empty() and snapshot.get("maps", []).size() > 0:
			var timeline = output.get("reveal")
			begin_reveal(snapshot, timeline if timeline is Dictionary else {})
	else:
		quick_running = false
	if status_probe and bool(output.get("result_ready", false)) and not request_pending:
		host.call_deferred("_collect_career_result", str(output.get("match_id", current_preflight().get("match_id", ""))))
	if path.begins_with("/api/3d/season/"):
		var state: Dictionary = output.get("quick", quick_state())
		if not pace.enabled() and str(state.get("phase", "")) in ["paused", "blocked", "finished", "complete", "end", "break", "choice", "story"]: quick_running = false
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

func outdated_status(output: Dictionary) -> bool:
	var id := str(current_game().get("id", ""))
	if str(output.get("match_id", id)) != id: return true
	var incoming = output.get("preflight")
	if not incoming is Dictionary: return false
	# A status request can finish after a command/context refresh. It cannot
	# restore an older map or an older launch session on the same map.
	for known in [preflight, CareerBridge.context.get("match_preflight", {})]:
		if not known is Dictionary or str(known.get("match_id", "")) != id: continue
		if incoming.has("revision") and known.has("revision") and int(incoming.revision) < int(known.revision): return true
		if incoming.has("maps_done") and known.has("maps_done") and int(incoming.maps_done) < int(known.maps_done): return true
	return false

func process(delta: float) -> void:
	pace.process(delta)
	if CareerBridge.feedback_active: return
	if not host.screen.visible or host.active_page not in ["career_match", "quick"]: return
	if not result.is_empty():
		if reveal_phase == "maps":
			process_rounds(delta)
			return
		reveal_elapsed += delta
		if reveal_phase == "stats" and not continue_ready and reveal_elapsed >= STATS_SECONDS:
			continue_ready = true
			host._rebuild()
		return
	var info := current_preflight()
	if (show_real and str(info.get("phase", "")) == "ready") or str(info.get("phase", "")) in ["waiting", "starting", "launched"] or is_interrupted():
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
