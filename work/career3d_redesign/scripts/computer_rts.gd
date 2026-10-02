extends RefCounted
## RTS executes locally; only the shared Python service settles Career results.
const UI = preload("res://scripts/computer_ui.gd")
const Game = preload("res://rts/scripts/game.gd")
const Maps = preload("res://rts/scripts/map_catalog.gd")
var host
var session: Control
var commanded_side := "a"
var last_report: Dictionary = {}
var career_match_id := ""
var frozen: Dictionary = {}
var pending_action := ""
var notice := ""
var exit_dialog: ConfirmationDialog
var play_mode := "command"
var entry_kind := "career"
var arena_result: Dictionary = {}
var series_finished := false

func attach(owner) -> void:
	host = owner
	host.rts_render = render
	CareerBridge.command_finished.connect(received)

func lobby() -> Dictionary:
	var room = CareerBridge.context.get("custom", {}).get("lobby")
	return room if room is Dictionary and room.get("mode") == "custom" else {}

func rosters() -> Dictionary:
	var value = CareerBridge.context.get("custom", {}).get("rts_rosters", {})
	return value if value is Dictionary else {}

func eligible() -> bool:
	var room := lobby()
	return not room.is_empty() and room.get("phase") == "ready" and "de_" + str(room.get("map", "")) in Maps.available_maps() and rosters().get("ct", []).size() == 5 and rosters().get("t", []).size() == 5

func open_career(match_id: String) -> void:
	entry_kind = "career"
	career_match_id = match_id
	host._navigate("rts")

func open_ladder() -> void:
	entry_kind = "arena"
	career_match_id = ""
	host._navigate("rts")

func open_custom() -> void:
	entry_kind = "custom"
	career_match_id = ""
	host._navigate("rts")

func resume_series() -> void:
	if not host.match_center.continue_ready or host.match_center.result.get("played", false): return
	var ident := career_match_id
	if ident.is_empty(): ident = str(host.match_center.result.get("match_id", ""))
	if ident.is_empty(): return
	host.match_center.continue_result()
	open_career(ident)

func ladder_eligible() -> bool:
	var room = CareerBridge.context.get("ladder", {}).get("lobby")
	return room is Dictionary and room.get("mode", "") in ["rank", "fpl"] and room.get("phase", "") == "ready" and career_map_reason("de_" + str(room.get("map", ""))).is_empty()

func career_map_reason(map_id: String) -> String:
	if map_id.is_empty(): return ""
	var state: Dictionary = CareerBridge.context.get("rts", {})
	if map_id in state.get("career_maps", Maps.available_maps()): return ""
	return str(state.get("limitations", {}).get(map_id, "这张地图暂未通过职业 RTS 完赛验证，请使用常规模拟。"))

func render(parent: VBoxContainer) -> void:
	var card := UI.card(parent)
	UI.label(card, "RTS 指挥对局", 22)
	UI.label(card, "点选或框选队员，右键安排走位；Shift 追加路线，Tab 查看十人战绩。", 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	UI.label(card, "简化 2D 规则，不是 CS2 录像。职业比赛保存逐回合数据并正常结算；自定义对局不计积分。", 13, UI.MUTED).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var mode_picker := OptionButton.new()
	mode_picker.name = "RTSPlayMode"
	for label in ["战术指挥", "亲自操控", "只看比赛"]: mode_picker.add_item(label)
	mode_picker.select(["command", "play", "spectate"].find(play_mode))
	mode_picker.item_selected.connect(func(index): play_mode = ["command", "play", "spectate"][index])
	UI.dark_options(mode_picker)
	card.add_child(mode_picker)
	var saved: Dictionary = CareerBridge.context.get("rts", {}).get("session", {})
	var arena_saved: Dictionary = CareerBridge.context.get("rts", {}).get("arena_session", {})
	if saved.is_empty() and not arena_saved.is_empty(): saved = arena_saved
	var info: Dictionary = CareerBridge.context.get("match_preflight", {})
	var ident := career_match_id if not career_match_id.is_empty() else str(info.get("match_id", ""))
	if not saved.is_empty():
		career_match_id = str(saved.get("match_id", ""))
		UI.label(card, "未结算地图 · " + str(saved.get("map", "")), 17)
		UI.label(card, "重新开始未完赛地图，使用原名单、原地图和原种子。", 13, UI.MUTED)
		var restart := UI.button(card, "重新开始未结算地图", begin_saved.bind(saved)); UI.primary(restart)
		restart.name = "CareerRTSRestart"
		var blocked := career_map_reason(str(saved.get("map", "")))
		restart.disabled = not blocked.is_empty()
		if not blocked.is_empty(): UI.label(card, blocked, 14, UI.MUTED).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		UI.button(card, "取消未结算地图", confirm_cancel.bind(saved)).name = "CareerRTSCancel"
	elif entry_kind == "arena":
		var room: Dictionary = CareerBridge.context.get("ladder", {}).get("lobby", {})
		UI.label(card, "本地天梯 · " + str(room.get("map", "")).capitalize(), 17)
		var start := UI.button(card, "开始当前天梯 RTS", command.bind("arena_start", {"lobby_id":room.get("id", "")}))
		start.name = "LadderRTSStart"
		start.disabled = not ladder_eligible()
		UI.primary(start)
		var blocked := career_map_reason("de_" + str(room.get("map", "")))
		if not blocked.is_empty(): UI.label(card, blocked, 14, UI.MUTED)
		UI.label(card, "沿用本局队长选人、地图 BP 和选边；只结算本地天梯，不影响 VRS、奖金或培养。", 13, UI.MUTED)
		UI.button(card, "返回天梯房间", func(): host._navigate("ladder"))
	elif not ident.is_empty() and info.get("due", false) and not info.get("played", false):
		UI.label(card, "职业赛事 · %s 对阵 %s" % [info.get("team_a", ""), info.get("team_b", "")], 17)
		var start := UI.button(card, "开始当前职业地图 · 指挥我的队伍", command.bind("start", {"match_id":ident,"side":"t"})); UI.primary(start)
		start.name = "CareerRTSStart"
		var value = info.get("pending_map", "")
		var map_id := str(value.get("map", "")) if value is Dictionary else str(value) if value != null else ""
		var blocked := career_map_reason(map_id)
		start.disabled = not blocked.is_empty()
		if not blocked.is_empty(): UI.label(card, blocked, 14, UI.MUTED).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		UI.label(card, "保留已完成 BP；未完成时自动 BP。系列赛逐图进行，先到胜场才结束。", 13, UI.MUTED).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	else:
		UI.button(card, "职业比赛中心", func(): host._navigate("career_match"))
	var custom := UI.card(parent)
	UI.label(custom, "自定义指挥对局", 18)
	if eligible() and saved.is_empty():
		var row := HBoxContainer.new(); custom.add_child(row)
		var picker := OptionButton.new()
		picker.add_item("指挥 A 队", 0); picker.add_item("指挥 B 队", 1)
		picker.select(0 if commanded_side == "a" else 1)
		picker.item_selected.connect(func(index): commanded_side = "a" if index == 0 else "b")
		UI.dark_options(picker); row.add_child(picker)
		UI.primary(UI.button(row, "开始自定义指挥", start_session))
	else: UI.label(custom, "先保存十人自定义阵容，选择支持的地图。", 14, UI.MUTED)
	UI.label(custom, "支持 · " + ", ".join(Maps.available_maps()), 12, UI.MUTED).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	UI.button(custom, "配置自定义阵容 / 地图", func(): host._navigate("custom"))
	if not notice.is_empty(): UI.label(parent, notice, 14, UI.MUTED).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if not last_report.is_empty():
		var stats := UI.card(parent)
		UI.label(stats, "刚才的指挥对局", 17)
		var score: Dictionary = last_report.get("score", {})
		UI.label(stats, "开局 CT 队 %d : %d 开局 T 队 · %s" % [score.get("ct",0),score.get("t",0),"已结束" if last_report.get("finished",false) else "未结算"])
		for player in last_report.get("players", []):
			UI.label(stats, "%s   %d / %d / %d   ADR %.1f" % [player.get("name", ""),player.get("k",0),player.get("d",0),player.get("a",0),player.get("adr",0.0)], 13)

func command(action: String, payload: Dictionary) -> void:
	if not pending_action.is_empty(): return
	var body := payload.duplicate(true)
	body["revision"] = int(CareerBridge.context.get("calendar", {}).get("revision", 0))
	if action.begins_with("arena_"): body["arena_revision"] = int(CareerBridge.context.get("ladder", {}).get("revision", 0))
	if CareerBridge.command("/api/3d/rts/" + action, body): pending_action = action
	else: notice = CareerBridge.message

func received(path: String, result: Dictionary) -> void:
	if not path.begins_with("/api/3d/rts/"): return
	var action := pending_action; pending_action = ""
	notice = str(result.get("reason", result.get("msg", "")))
	if not result.get("ok", false):
		if is_instance_valid(session):
			var dialog := AcceptDialog.new(); session.add_child(dialog)
			dialog.dialog_text = notice + "\n原战绩仍保留，点击返回会重试录入。"; dialog.popup_centered(Vector2i(480, 180))
		else: host._rebuild()
		return
	if action in ["start", "arena_start"] and result.get("rts_session") is Dictionary:
		begin_saved(result.rts_session)
	elif action in ["cancel", "arena_cancel"]:
		frozen.clear(); remove_session(); host._rebuild()
	elif action in ["submit", "arena_submit"]:
		series_finished = result.get("status", "") == "finished"
		if action == "arena_submit": arena_result = result.get("arena_result", {}).duplicate(true)
		elif result.get("result") is Dictionary:
			host.match_center.begin_reveal(result.result, result.get("reveal", {}))
		frozen.clear()
		if is_instance_valid(session):
			var dialog := AcceptDialog.new(); session.add_child(dialog)
			dialog.dialog_text = "本图十人战绩已保存。" + ("系列赛结束，返回电脑可看完整战报。" if result.get("status") == "finished" else "返回电脑，可继续下一张地图。")
			dialog.popup_centered(Vector2i(520, 170))
		else: host._rebuild()
	else: host._rebuild()

func begin_saved(value: Dictionary) -> void:
	if is_instance_valid(session): return
	frozen = value.duplicate(true); last_report.clear()
	entry_kind = "arena" if value.get("kind", "") == "arena" else "career"
	series_finished = false
	arena_result.clear()
	career_match_id = str(value.get("match_id", ""))
	launch_game(value.get("rosters", {}), str(value.get("map", "")), str(value.get("commanded_side", "t")), int(value.get("seed", 0)), true)

func start_session() -> void:
	if not eligible() or CareerBridge.busy or is_instance_valid(session): return
	frozen.clear(); last_report.clear()
	entry_kind = "custom"; arena_result.clear(); series_finished = false
	var room := lobby()
	launch_game(rosters(), "de_" + str(room.map), "ct" if str(room.get("ct", "a")) == commanded_side else "t", 20261001, false)

func launch_game(roster: Dictionary, map_id: String, team: String, seed_number: int, career: bool) -> void:
	session = Game.new()
	session.embedded = true; session.initial_map = map_id
	session.initial_rosters = roster.duplicate(true)
	session.initial_team = team; session.initial_overtime = career
	session.initial_mode = play_mode
	session.initial_player_id = str(frozen.get("player_id", roster.get("human_id", "")))
	session.lock_player_identity = career
	if not career:
		var team_ids: Array = []
		for actor in roster.get(team, []): team_ids.append(str(actor.get("id", "")))
		if session.initial_player_id not in team_ids: session.initial_player_id = str(team_ids[0]) if not team_ids.is_empty() else ""
	session.seed_value = seed_number
	session.exit_requested.connect(close_session)
	session.match_completed.connect(completed)
	session.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	host.add_child(session)

func completed(report: Dictionary) -> void:
	last_report = report.duplicate(true)
	if not frozen.is_empty(): submit_report()

func submit_report() -> void:
	if frozen.get("kind", "") == "arena":
		command("arena_submit", {"lobby_id":frozen.lobby_id, "nonce":frozen.nonce, "report":last_report})
	else: command("submit", {"match_id":frozen.match_id,"nonce":frozen.nonce,"report":last_report})

func close_session() -> bool:
	if not frozen.is_empty():
		if not pending_action.is_empty(): return false
		if last_report.get("finished", false):
			submit_report(); return false
		confirm_cancel(frozen); return false
	if is_instance_valid(session) and session.sim != null: last_report = session.sim.report()
	remove_session()
	if not arena_result.is_empty():
		host._navigate("ladder")
		host._open_report(arena_result)
	elif series_finished or host.match_center.is_presenting():
		# RTS has already shown the real rounds. Return to their saved table,
		# rather than replaying those same scores as another slow simulation.
		if not host.match_center.result.is_empty(): host.match_center.open_saved(host.match_center.result)
		else: host._navigate("career_match")
	else: host._rebuild()
	return true

func confirm_cancel(value: Dictionary) -> void:
	if not pending_action.is_empty() or is_instance_valid(exit_dialog): return
	var saved := value.duplicate(true)
	exit_dialog = ConfirmationDialog.new()
	if is_instance_valid(session): session.add_child(exit_dialog)
	else: host.add_child(exit_dialog)
	exit_dialog.dialog_text = "本图尚未结算。取消后需要重新开始本图；以前保存的地图保持不变。"
	exit_dialog.confirmed.connect(func():
		exit_dialog.queue_free(); exit_dialog = null
		if saved.get("kind", "") == "arena": command("arena_cancel", {"lobby_id":saved.get("lobby_id", ""),"nonce":saved.get("nonce", "")})
		else: command("cancel", {"match_id":saved.get("match_id", ""),"nonce":saved.get("nonce", "")}))
	exit_dialog.canceled.connect(func(): exit_dialog.queue_free(); exit_dialog = null)
	exit_dialog.popup_centered(Vector2i(520, 170))

func remove_session() -> void:
	if is_instance_valid(exit_dialog): exit_dialog.queue_free()
	if is_instance_valid(session):
		session.set_process(false); session.hide(); session.queue_free()
	session = null; exit_dialog = null; host.screen.show()

func reset() -> void:
	if is_instance_valid(exit_dialog): exit_dialog.queue_free()
	if is_instance_valid(session): session.queue_free()
	session = null; exit_dialog = null; frozen.clear()
	last_report.clear(); career_match_id = ""; pending_action = ""
	arena_result.clear(); series_finished = false; entry_kind = "career"
