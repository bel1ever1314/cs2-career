extends RefCounted
## Device adapter for the shared, ephemeral career progression controller.
const UI = preload("res://scripts/computer_ui.gd")
const Visuals = preload("res://scripts/team_visuals.gd")
const Kit = preload("res://scripts/ui_kit.gd")
var _owner: WeakRef
var owner:
	get: return _owner.get_ref()
var flow = preload("res://scripts/career_pace_controller.gd").new()
var world = preload("res://scripts/career_world_feed.gd").new()
var timer_label: Label
var status_title: Label
var countdown: ProgressBar
var starting := false

func attach(center) -> void:
	_owner = weakref(center)

func visible() -> bool:
	return owner.host.screen.visible and owner.host.active_page in ["career_match", "quick"]

func enabled() -> bool:
	return bool(owner.quick_state().get("unified_pace", false))

func cursor() -> String:
	return str(owner.current_preflight().get("map_key", ""))

func next_cursor() -> String:
	if not owner.result.is_empty() and bool(owner.result.get("played", false)):
		return "after:" + str(owner.result.get("result_id", owner.result.get("match_id", "")))
	return cursor()

func pause(rebuild: bool = true) -> void:
	flow.pause()
	starting = false
	if rebuild and visible(): owner.host._rebuild()

func start() -> void:
	if owner.request_pending or CareerBridge.busy: return
	if owner.break_pending(owner.quick_state()) or not CareerBridge.context.get("stories", []).is_empty():
		pause(); return
	if owner.is_interrupted() or blocked_by_session(): pause(); return
	if not enabled():
		starting = true
		owner.season_command("unify", {})
		return
	flow.resume()
	if not owner.result.is_empty(): flow.arm("reveal" if owner.reveal_phase == "maps" else "waiting", next_cursor())
	elif not cursor().is_empty() and bool(owner.current_game().get("due", false)): flow.arm("prepare", cursor())
	owner.host._rebuild()

func render(parent: Node) -> void:
	var state: Dictionary = owner.quick_state()
	var heading := HBoxContainer.new()
	heading.add_theme_constant_override("separation", 10)
	parent.add_child(heading)
	UI.label(heading, "生涯推进", 25)
	var status := Kit.chip(heading, "自动推进中" if flow.running else "已暂停", "green" if flow.running else "gray", 13)
	status.name = "CareerPaceState"
	status.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	UI.label(parent, "比赛默认逐图模拟，每张图之间停 4 秒，可以接手 CS2、RTS 或暂停。暂停后可以自由活动。", 13, UI.MUTED)
	if owner.break_pending(state):
		preload("res://scripts/career_break_view.gd").mount(parent, owner)
		return
	if str(state.get("season_phase", "")) == "end":
		if not CareerBridge.context.get("stories", []).is_empty():
			UI.label(parent, str(state.get("block_reason", "")), 14, UI.AMBER)
			owner.host._button(parent, "处理待办事项", open_pending, false)
		else: owner.host._button(parent, "继续下一赛季", owner.season_command.bind("next-year", {"year":int(state.get("year", 0))}))
		return
	var game: Dictionary = owner.current_game()
	# A due fixture (or one already in hand) owns the page; otherwise show the
	# way to the next match and what happened elsewhere while advancing.
	if not owner.result.is_empty() or not game.is_empty() and (bool(game.get("due", false)) or owner.is_interrupted()
			or str(owner.current_preflight().get("phase", "")) in ["waiting", "starting", "launched"]):
		owner.render(parent)
		return
	if not str(state.get("block_reason", "")).is_empty(): UI.label(parent, str(state.block_reason), 14, UI.AMBER)
	if not CareerBridge.context.get("stories", []).is_empty(): owner.host._button(parent, "处理待办事项", owner.host._open_phone.bind("stories"), false)
	world.render(parent, owner)

## Map number (1-based) and name that the next pace action would play.
func upcoming_map() -> Dictionary:
	var info: Dictionary = owner.current_preflight()
	var rows = info.get("series_maps", [])
	for row in rows if rows is Array else []:
		if row is Dictionary and str(row.get("state", "")) in ["live", "next"]:
			return {"index":int(row.get("index", 1)), "map":str(row.get("map", ""))}
	var pending = info.get("pending_map")
	return {"index":int(info.get("maps_done", 0)) + 1, "map":str(pending) if pending is String else ""}

static func map_title(code: String) -> String:
	return code.trim_prefix("de_").capitalize()

## What the dock says and offers. The page body owns match decisions (BP,
## starting side, recording or recovering a CS2 map); the dock owns pacing.
## When the body holds the decision the dock only points at it.
func plan() -> Dictionary:
	var out := {"title":"", "detail":"", "primary":"", "cs2":"", "rts":"", "decision":false, "countdown":false}
	var info: Dictionary = owner.current_preflight()
	var game: Dictionary = owner.current_game()
	var due := bool(game.get("due", false))
	var veto: Dictionary = info.get("veto", {}) if info.get("veto", {}) is Dictionary else {}
	var turn = veto.get("turn")
	var next := upcoming_map()
	var number := int(next.get("index", 1))
	var name := map_title(str(next.get("map", "")))
	var counting: bool = flow.running and flow.phase in ["prepare", "waiting"] and flow.reservation.is_empty()
	var seconds := ceili(flow.remaining)
	if owner.request_pending:
		out.title = "正在处理……"
		out.detail = "完成后会自动继续" if flow.running else ""
		return out
	if owner.is_interrupted():
		out.merge({"title":"第 %d 图未完成 · CS2 已退出" % number, "detail":"在上方选择：重新进入、模拟本图或改用 RTS。已完成的地图会保留。", "decision":true}, true)
		return out
	if owner.result.is_empty() and blocked_by_session():
		out.merge({"title":"第 %d 图 · %s 进行中" % [number, "CS2" if CareerBridge.context.get("rts", {}).get("session", {}).is_empty() else "RTS"],
			"detail":"打完回到这里，在上方录入战绩。", "decision":true}, true)
		return out
	if not owner.result.is_empty():
		var done: bool = bool(owner.result.get("played", false))
		if owner.reveal_phase == "maps":
			out.title = "逐回合战报"
			out.detail = reservation_text() if not flow.reservation.is_empty() else "可以直接看结果，或提前预约下一图由你接手。"
			out.primary = "直接看本图结果"
			if not done:
				out.cs2 = "下一图自己打"; out.rts = "下一图 RTS"
			return out
		if owner.break_pending(owner.quick_state()) or not CareerBridge.context.get("stories", []).is_empty():
			out.merge({"title":"本图战报已就绪", "detail":"处理待办后再继续推进", "primary":"查看休赛安排" if owner.break_pending(owner.quick_state()) else "处理待办事项", "decision":true}, true)
			return out
		if done:
			out.title = "系列赛结束 · %s" % str(owner.score_text(owner.result.get("series", "")))
			out.detail = ("%d 秒后进入下一场" % seconds) if counting else ("已暂停 · 点继续进入下一场" if not flow.running else "")
			out.merge({"primary":"下一场", "cs2":"下一场自己打", "rts":"下一场 RTS", "countdown":counting}, true)
			return out
		out.title = "下一张 · 第 %d 图 %s" % [number, name] if not name.is_empty() else "下一张图"
		out.detail = reservation_text() if not flow.reservation.is_empty() else (("%d 秒后自动模拟" % seconds) if counting else "已暂停 · 可以模拟或接手")
		out.merge({"primary":"模拟第 %d 图" % number, "cs2":"第 %d 图自己打" % number, "rts":"第 %d 图 RTS" % number, "countdown":counting}, true)
		return out
	if owner.break_pending(owner.quick_state()):
		var pending: bool = not CareerBridge.context.get("stories", []).is_empty() or not str(owner.quick_state().get("block_reason", "")).is_empty()
		out.merge({"title":"Major 休赛期", "detail":"请处理上方待办事项" if pending else "待办已处理 · 属性点可以保留",
			"primary":"处理待办事项" if pending else "结束休赛停留", "decision":true}, true)
		return out
	if not CareerBridge.context.get("stories", []).is_empty():
		out.merge({"title":"有待决定的生涯事件", "detail":"处理完成后再继续推进", "primary":"处理待办事项", "decision":true}, true)
		return out
	if str(owner.quick_state().get("season_phase", "")) == "end":
		out.merge({"title":"赛季结束", "primary":"继续下一赛季", "decision":true}, true)
		return out
	if game.is_empty() or not due:
		out.title = "下一场 · %s vs %s" % [str(CareerBridge.context.get("team", {}).get("name", "")), str(game.get("opponent", ""))] if not game.is_empty() else "暂无已到期的比赛"
		out.detail = ("推进赛程中……" if flow.running else "已暂停 · 继续后推进到下一场比赛日")
		if not game.is_empty():
			out.title += " · " + str(game.get("date", ""))
			var days: int = world.days_between(str(CareerBridge.context.get("date", "")), str(game.get("date", "")))
			if days >= 0: out.title += " · " + world.countdown_text(days)
		out.primary = "继续推进"
		return out
	if not bool(veto.get("complete", false)) and turn is Dictionary:
		var mine := bool(turn.get("mine", false))
		if mine: out.title = "地图 BP · 轮到你方选图" if str(turn.get("action", "")) == "pick" else "地图 BP · 轮到你方禁图"
		else: out.title = "地图 BP · 等待 %s" % str(turn.get("team", ""))
		out.detail = "在上方点地图查看双方评价，再确认。" if mine else ""
		out.decision = true
		return out
	if owner.show_real and bool(info.get("can_launch", false)) and bool(owner.current_connection().get("can_launch", false)):
		if bool(info.get("venue", {}).get("should_walk", false)) and not owner.can_prepare_here():
			out.merge({"title":"线下比赛 · 等待入座", "detail":"在上方前往比赛场馆，到你的选手席入座。", "decision":true,
				"primary":"改为模拟本图", "rts":"改用 RTS"}, true)
			return out
		out.merge({"title":"第 %d 图 %s · 亲自上场" % [number, name], "detail":"在上方选择 CT 或 T 开场，进入 CS2。", "decision":true,
			"primary":"改为模拟本图", "rts":"改用 RTS"}, true)
		return out
	var ready := bool(veto.get("complete", false))
	out.title = ("第 %d 图 · %s" % [number, name]) if ready and not name.is_empty() else "第 %d 图 · 等待 BP" % number
	if counting: out.detail = ("%d 秒后自动模拟" if ready else "%d 秒后由队长自动 BP 并模拟") % seconds
	elif not flow.reservation.is_empty(): out.detail = reservation_text()
	else: out.detail = "已暂停 · 可以模拟、接手，或在上方手动 BP" if not ready else "已暂停 · 可以模拟或接手"
	out.merge({"primary":"模拟第 %d 图" % number, "cs2":"第 %d 图自己打" % number, "rts":"第 %d 图 RTS" % number, "countdown":counting}, true)
	return out

func reservation_text() -> String:
	return "下一图由你亲自上场" if flow.reservation == "cs2" else "下一图由你 RTS 指挥"

func footer(parent: Node) -> void:
	if not visible(): return
	var margin := MarginContainer.new()
	margin.name = "CareerPaceFooter"
	for side in ["left", "right"]: margin.add_theme_constant_override("margin_" + side, 23)
	margin.add_theme_constant_override("margin_top", 4)
	parent.add_child(margin)
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", UI.style(UI.PAPER, 10, 10, UI.LINE))
	margin.add_child(panel)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	panel.add_child(row)
	var info := VBoxContainer.new()
	info.add_theme_constant_override("separation", 1)
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	info.custom_minimum_size.x = 250
	row.add_child(info)
	var current := plan()
	status_title = UI.label_exact(info, "", 15)
	status_title.name = "PaceStatus"
	timer_label = UI.label_exact(info, "", 12, UI.MUTED)
	timer_label.name = "PaceDetail"
	for label in [status_title, timer_label]:
		label.autowrap_mode = TextServer.AUTOWRAP_OFF
		label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	countdown = ProgressBar.new()
	countdown.name = "PaceCountdown"
	countdown.show_percentage = false
	countdown.custom_minimum_size = Vector2(0, 4)
	countdown.max_value = flow.WAIT_SECONDS
	countdown.add_theme_stylebox_override("background", UI.style(UI.MINT, 0, 2))
	countdown.add_theme_stylebox_override("fill", UI.style(UI.GREEN, 0, 2))
	info.add_child(countdown)
	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", 8)
	buttons.alignment = BoxContainer.ALIGNMENT_END
	row.add_child(buttons)
	var busy: bool = owner.request_pending or CareerBridge.busy
	if not flow.reservation.is_empty():
		var cancel := UI.button(buttons, "取消预约", cancel_reservation); cancel.name = "PaceCancelReservation"
	var cs2 := UI.button(buttons, str(current.cs2) if not str(current.cs2).is_empty() else "自己打", choose.bind("cs2")); cs2.name = "PaceCS2"
	var rts := UI.button(buttons, str(current.rts) if not str(current.rts).is_empty() else "RTS", choose.bind("rts")); rts.name = "PaceRTS"
	var auto := UI.button(buttons, "暂停" if flow.running else "自动推进", toggle_auto); auto.name = "PacePause"
	var next := UI.button(buttons, str(current.primary) if not str(current.primary).is_empty() else "继续推进", primary); next.name = "PaceContinue"
	if not bool(current.decision) and not str(current.primary).is_empty(): UI.primary(next)
	for button in buttons.get_children():
		UI.compact(button)
		button.size_flags_horizontal = Control.SIZE_SHRINK_END
		button.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		button.custom_minimum_size = Vector2(96, 38)
		button.add_theme_font_size_override("font_size", 14)
	cs2.visible = not str(current.cs2).is_empty()
	rts.visible = not str(current.rts).is_empty()
	next.visible = not str(current.primary).is_empty()
	# A body-owned decision (BP, side, recording, recovery) is not paced.
	auto.visible = not bool(current.decision)
	next.disabled = busy
	cs2.disabled = busy or owner.current_game().is_empty() or (bool(owner.result.get("played", false)) and owner.reveal_phase == "maps")
	rts.disabled = cs2.disabled
	auto.disabled = busy and not flow.running
	update_label()

func toggle_auto() -> void:
	if flow.running: pause()
	else: start()

func update_label() -> void:
	if not is_instance_valid(timer_label): return
	var current := plan()
	if is_instance_valid(status_title): status_title.text = str(current.title)
	timer_label.text = str(current.detail)
	if is_instance_valid(countdown):
		countdown.visible = bool(current.countdown)
		countdown.value = flow.WAIT_SECONDS - flow.remaining

func cancel_reservation() -> void:
	flow.clear_reservation()
	owner.host._rebuild()

func primary() -> void:
	if owner.request_pending or CareerBridge.busy: return
	if not owner.result.is_empty() and owner.reveal_phase != "maps" and (owner.break_pending(owner.quick_state()) or not CareerBridge.context.get("stories", []).is_empty()):
		pause(false); owner.result.clear(); owner.reveal_phase = ""
		if owner.break_pending(owner.quick_state()): owner.host._navigate("quick")
		else: open_pending()
		return
	if owner.result.is_empty() and owner.break_pending(owner.quick_state()):
		pause(false)
		if not CareerBridge.context.get("stories", []).is_empty() or not str(owner.quick_state().get("block_reason", "")).is_empty(): open_pending()
		else: owner.resume_quick()
		return
	if owner.result.is_empty() and not CareerBridge.context.get("stories", []).is_empty():
		pause(false); open_pending(); return
	if owner.result.is_empty() and str(owner.quick_state().get("season_phase", "")) == "end":
		pause(false); owner.season_command("next-year", {"year":int(owner.quick_state().get("year", 0))}); return
	if owner.is_interrupted():
		flow.resume(); flow.arm("prepare", cursor()); dispatch("simulate")
		return
	if not owner.result.is_empty() and owner.reveal_phase == "maps":
		owner.complete_map()
		owner.reveal_phase = "stats"
		owner.continue_ready = true
		flow.completed(bool(owner.result.get("played", false)), next_cursor())
		owner.host._rebuild()
		return
	if owner.show_real and owner.result.is_empty(): owner.show_real = false
	if not flow.running:
		start()
		# The button names the map it plays: act now instead of re-arming the wait.
		var due := bool(owner.current_game().get("due", false))
		if flow.running and (not owner.result.is_empty() or (due and not cursor().is_empty())): dispatch()
		return
	dispatch()

func open_pending() -> void:
	if not CareerBridge.context.get("stories", []).is_empty(): owner.host._open_phone("stories")
	else: owner.host._navigate(str(owner.quick_state().get("pause_page", "mail")))

func choose(mode: String) -> void:
	if owner.request_pending or CareerBridge.busy or owner.current_game().is_empty(): return
	if not owner.result.is_empty() and bool(owner.result.get("played", false)):
		if owner.reveal_phase == "maps" or cursor().is_empty(): return
		# This is a NEW explicit choice for an already identified next fixture,
		# never an inherited reservation for an unneeded map of the old series.
		flow.clear_reservation()
		owner.result.clear(); owner.reveal_phase = ""
		flow.resume(); flow.arm("idle", "")
		flow.reserve(mode, cursor())
		owner.host._rebuild()
		return
	if not owner.result.is_empty() and owner.reveal_phase == "maps":
		flow.reserve(mode, next_cursor())
		owner.host._rebuild()
		return
	flow.resume()
	flow.arm("waiting", next_cursor())
	dispatch(mode)

func dispatch(mode: String = "") -> void:
	if owner.request_pending or CareerBridge.busy or CareerBridge.feedback_active: return
	if blocked_by_session(): pause(); return
	if not enabled(): start(); return
	if not CareerBridge.context.get("stories", []).is_empty() or owner.break_pending(owner.quick_state()): pause(); return
	var key := next_cursor()
	if flow.target != key: flow.arm("prepare", key)
	var selected: String = flow.take(key, mode)
	if selected.is_empty(): return
	if not owner.result.is_empty():
		var done: bool = bool(owner.result.get("played", false))
		owner.result.clear(); owner.reveal_phase = ""
		if done:
			flow.in_flight = false; flow.arm("idle", "")
			owner.host._rebuild()
			return # Awards get a frame to open before calendar commands.
	var game: Dictionary = owner.current_game()
	if game.is_empty() or not bool(game.get("due", false)):
		flow.in_flight = false
		owner.season_command("run", {"stop_at":"match_preparation"})
		return
	var id := str(game.get("id", ""))
	flow.in_flight = false
	if selected == "simulate": owner.simulate_match(id)
	else:
		flow.arm("playing", key)
		flow.next_mode = selected
		if owner.can_prepare_here():
			if selected == "rts": owner.open_rts(id)
			else: owner.show_real = true; owner.command("preflight", {"match_id":id})
		else: owner.prepare_real(id)
	owner.host._rebuild()

func finished(path: String, output: Dictionary) -> void:
	flow.in_flight = false
	if not output.get("ok", false) or output.get("result_summary", false): pause(false); return
	if path.ends_with("/unify") and starting:
		starting = false; flow.resume()
	if path.ends_with("/run"):
		if str(output.get("status", "")) in ["paused", "season_done"]: pause(false)
		else: flow.arm("idle", "")

func blocked_by_session() -> bool:
	if not owner.result.is_empty(): return false
	if not CareerBridge.context.get("rts", {}).get("session", {}).is_empty(): return true
	if owner.is_interrupted(): return false # Only explicit recovery buttons dispatch.
	var linked: Dictionary = owner.current_connection()
	return bool(owner.current_preflight().get("session_pending", false)) or str(linked.get("status", "")) in ["starting", "waiting", "launched", "running"]

func process(delta: float) -> void:
	var focused: bool = owner.host.get_window().has_focus() or DisplayServer.get_name() == "headless"
	if not CareerBridge.connected or not focused:
		if flow.running: pause(false)
		return
	if not visible():
		if flow.running and flow.phase != "playing" and not CareerBridge.feedback_active: pause(false)
		return
	if CareerBridge.feedback_active: return
	if owner.can_prepare_here() and (owner.show_real or flow.phase == "playing") and not bool(owner.current_preflight().get("venue", {}).get("entry_completed", false)) and not owner.request_pending and not CareerBridge.busy:
		owner.command("seated", {"match_id":str(owner.current_game().get("id", ""))})
		return
	if is_instance_valid(CareerBridge.feedback) and not CareerBridge.feedback.queue.is_empty() and owner.result.is_empty(): return
	if owner.is_interrupted():
		if flow.running: pause()
		return
	if blocked_by_session() and flow.phase != "playing":
		if flow.running: pause()
		return
	if flow.phase == "playing":
		if flow.next_mode == "rts" and owner.can_prepare_here() and owner.result.is_empty() and not owner.request_pending and not CareerBridge.busy:
			flow.next_mode = ""
			owner.open_rts(str(owner.current_game().get("id", "")))
		return
	if not owner.result.is_empty():
		if owner.reveal_phase == "maps": return
		if flow.phase == "reveal": flow.completed(bool(owner.result.get("played", false)), next_cursor())
	elif flow.running and flow.phase in ["idle", "dispatching"] and not owner.request_pending and not CareerBridge.busy:
		if bool(owner.current_preflight().get("session_pending", false)) or not CareerBridge.context.get("rts", {}).get("session", {}).is_empty(): pause(); return
		if not CareerBridge.context.get("stories", []).is_empty() or owner.break_pending(owner.quick_state()) or str(owner.quick_state().get("season_phase", "")) == "end": pause(); return
		if not cursor().is_empty() and bool(owner.current_game().get("due", false)): flow.arm("prepare", cursor())
		else:
			owner.quick_elapsed += delta
			if owner.quick_elapsed >= 0.8:
				owner.quick_elapsed = 0.0
				owner.season_command("run", {"stop_at":"match_preparation"})
	if flow.tick(delta, not owner.request_pending and not CareerBridge.busy): dispatch()
	update_label()
