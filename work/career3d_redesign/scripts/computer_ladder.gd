extends RefCounted
## Room presentation and paced AI turns. Arena remains the only draft/veto owner.
const UI = preload("res://scripts/computer_ui.gd")
const AI_TURN_DELAY := 1.25
const ROLES := {"awp":"主狙", "entry":"突破", "lurk":"自由人", "igl":"指挥", "rifle":"步枪手"}
var host
var turn_key := ""
var remaining := AI_TURN_DELAY
var sent_key := ""
var pause_reason := ""
var visible_phase := ""

func attach(owner) -> void:
	host = owner

func reset() -> void:
	turn_key = ""
	sent_key = ""
	remaining = AI_TURN_DELAY
	pause_reason = ""
	visible_phase = ""

func _key(lobby: Dictionary) -> String:
	return JSON.stringify([lobby.get("id", ""), lobby.get("phase", ""), lobby.get("picks", []).size(),
		lobby.get("bans", []).size(), lobby.get("turn", {})])

func queue() -> void:
	var lobby = host._ladder_state().get("lobby")
	if not lobby is Dictionary or lobby.get("phase") not in ["draft", "veto", "side"]:
		turn_key = ""
		return
	var next_key := _key(lobby)
	if next_key != turn_key:
		turn_key = next_key
		remaining = AI_TURN_DELAY
		sent_key = ""
		pause_reason = ""

func process(delta: float) -> void:
	# Leaving the room pauses its choices. On return, the visible turn gets its
	# full viewing interval; GET refreshes/rebuilds do not reset that interval.
	if not host.screen.visible or host.active_page != "ladder" or not host.report.is_empty():
		remaining = AI_TURN_DELAY
		return
	queue()
	var lobby = host._ladder_state().get("lobby")
	if not lobby is Dictionary or lobby.get("identity_error") or lobby.get("phase") not in ["draft", "veto", "side"]:
		return
	var turn = lobby.get("turn")
	if not turn is Dictionary or bool(turn.get("human", false)) or not pause_reason.is_empty() or sent_key == turn_key:
		return
	if CareerBridge.busy or not CareerBridge.connected:
		return
	remaining -= maxf(0.0, delta)
	if remaining <= 0:
		sent_key = turn_key
		if not host._ladder_command("advance", {}):
			pause_reason = "队长操作暂未发出，请重试。"
			host._rebuild()

func received(path: String, result: Dictionary) -> void:
	if path.begins_with("/api/3d/ladder/") and result.get("result_summary", false):
		var current = host._ladder_state().get("lobby")
		if current is Dictionary: turn_key = _key(current)
		pause_reason = "操作已保存，请确认当前阵容后继续选人 / BP。"
		return
	if path == "/api/3d/ladder/advance" and not result.get("ok", false):
		# A transport error may have committed the write. Never replay the same
		# turn automatically; explicit retry still uses Arena's revision guard.
		pause_reason = str(result.get("reason", result.get("msg", "队长操作暂未完成。")))
	elif path == "/api/3d/ladder/matchmake" and result.get("ok", false):
		reset()
	elif path == "/api/3d/ladder/cancel" and result.get("ok", false):
		reset()

func retry() -> void:
	reset()
	host._rebuild()

func player_name(lobby: Dictionary, pid: String) -> String:
	return str(lobby.get("roster", {}).get(pid, {}).get("name", pid))

func heading(lobby: Dictionary) -> void:
	var phase := str(lobby.get("phase", ""))
	var phase_key := str(lobby.get("id", "")) + ":" + phase
	if phase_key != visible_phase:
		visible_phase = phase_key
		host.page_scroll["ladder"] = 0
	var stage := HBoxContainer.new()
	stage.add_theme_constant_override("separation", 15)
	host.content.add_child(stage)
	var current: int = {"draft":0, "veto":1, "side":2}.get(phase, 3)
	for i in range(4):
		var text: String = ["队长选人", "地图 BP", "选择阵营", "准备开赛"][i]
		host._label(stage, ("✓ " if i < current else "%d · " % (i + 1)) + text, 15, UI.GREEN if i <= current else UI.MUTED)
	if phase not in ["draft", "veto", "side"]:
		return
	var turn: Dictionary = lobby.get("turn", {})
	var human := bool(turn.get("human", false))
	var actor := player_name(lobby, str(turn.get("captain_id", "")))
	var verb: String = {"draft":"选队友", "veto":"禁地图", "side":"选阵营"}.get(phase, "操作")
	var caption := "轮到你%s" % verb if human else "%s 队 · %s 正在%s" % [str(turn.get("side", "")).to_upper(), actor, verb]
	host._label(host.content, caption, 19, UI.GREEN)
	if not human:
		host._label(host.content, "由本局两位最高分队长选人和 BP，你可以观看完整过程。", 13, UI.MUTED)
	var picks: Array = lobby.get("picks", [])
	if phase == "draft" and not picks.is_empty():
		var previous: Dictionary = picks.back()
		host._label(host.content, "刚刚选择：%s 队 → %s" % [str(previous.get("side", "")).to_upper(), player_name(lobby, str(previous.get("player_id", "")))], 14)
	if not pause_reason.is_empty():
		host._label(host.content, pause_reason, 14)
		host._button(host.content, "继续队长选人 / BP", retry, false)

func draft(lobby: Dictionary, human: bool) -> void:
	host._label(host.content, "待选队员 · 选人顺序 A → B → B → A → A → B → B → A", 14, UI.MUTED)
	var grid := GridContainer.new()
	grid.columns = 4
	grid.add_theme_constant_override("h_separation", 9)
	grid.add_theme_constant_override("v_separation", 9)
	host.content.add_child(grid)
	var roster: Dictionary = lobby.get("roster", {})
	var selected: Array = lobby.get("a", []) + lobby.get("b", [])
	for pid in lobby.get("selection", roster.keys()):
		if pid in selected: continue
		var player: Dictionary = roster.get(pid, {})
		var card := UI.card(grid)
		var button: Button = host._button(card, str(player.get("name", pid)), host._ladder_command.bind("pick", {"player_id":pid}))
		button.name = "LadderDraft_" + str(pid)
		button.disabled = not human
		button.tooltip_text = "点击选入你的队伍" if human else "等待本局队长选择"
		host._label(card, "%s · Elo %s" % [ROLES.get(player.get("role", ""), player.get("role", "")), lobby.get("ratings", {}).get(pid, "—")], 12, UI.MUTED)

func veto(lobby: Dictionary, human: bool) -> void:
	host._label(host.content, "双方轮流禁图，剩下一张开赛。", 14, UI.MUTED)
	var banned := {}
	for ban in lobby.get("bans", []):
		banned[str(ban.get("map", ""))] = str(ban.get("side", "")).to_upper()
	var grid := GridContainer.new()
	grid.columns = 4
	grid.add_theme_constant_override("h_separation", 9)
	grid.add_theme_constant_override("v_separation", 9)
	host.content.add_child(grid)
	for map_name in lobby.get("map_pool", []):
		var card := UI.card(grid)
		host._label(card, str(map_name).capitalize(), 17)
		var is_banned: bool = banned.has(str(map_name))
		var text := "%s 队已禁用" % banned[str(map_name)] if is_banned else "禁用地图"
		var button: Button = host._button(card, text, host._ladder_command.bind("ban", {"map":map_name}))
		button.name = "LadderMap_" + str(map_name)
		button.disabled = is_banned or not human
		button.tooltip_text = "已经禁用" if is_banned else ("点击禁用这张地图" if human else "等待本局队长禁图")

func records(lobby: Dictionary) -> void:
	var picks: Array = lobby.get("picks", [])
	var bans: Array = lobby.get("bans", [])
	if picks.is_empty() and bans.is_empty(): return
	var card := UI.card(host.content)
	host._label(card, "本局选人与地图 BP 记录", 16)
	if not picks.is_empty():
		var grid := GridContainer.new()
		grid.columns = 2
		grid.add_theme_constant_override("h_separation", 25)
		card.add_child(grid)
		for i in range(picks.size()):
			var pick: Dictionary = picks[i]
			var label: Label = host._label(grid, "%d · %s 队 → %s" % [i + 1, str(pick.get("side", "")).to_upper(), player_name(lobby, str(pick.get("player_id", "")))], 13)
			label.name = "LadderPickRecord_%d" % i
	if not bans.is_empty():
		var parts: PackedStringArray = []
		for ban in bans:
			parts.append("%s 队禁用 %s" % [str(ban.get("side", "")).to_upper(), str(ban.get("map", "")).capitalize()])
		var label: Label = host._label(card, "  →  ".join(parts), 13, UI.MUTED)
		label.name = "LadderBanRecord"
	if not str(lobby.get("map", "")).is_empty():
		host._label(card, "决胜地图：" + str(lobby.get("map", "")).capitalize(), 15, UI.GREEN)
