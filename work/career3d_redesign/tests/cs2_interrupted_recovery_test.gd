extends Node
## All button writes are captured. No career service, real save or CS2 is used.
var checks := 0
var failures: Array[String] = []
var commands: Array[Dictionary] = []

func _ready() -> void:
	call_deferred("run")

func match_seated(id: String) -> bool:
	return id == "interrupted-match"

func check(value: bool, caption: String) -> void:
	checks += 1
	if not value: failures.append(caption)
	print("CS2_RECOVERY_CHECK ", "PASS " if value else "FAIL ", caption)

func send_fixture(path: String, body: Dictionary) -> bool:
	commands.append({"path":path, "body":body.duplicate(true)})
	return true

func button(key: String) -> Button:
	return Computer.content.find_child(key, true, false) as Button

func click(key: String) -> void:
	var target := button(key)
	check(target != null and not target.disabled, "enabled recovery button: " + key)
	if target != null and not target.disabled: target.pressed.emit()

func linked(id: String, status: String = "interrupted") -> Dictionary:
	return {"status":status, "match_id":id, "lobby_id":id, "phase":"launched", "process_known":true,
		"cs2_running":false, "can_resume":status == "interrupted", "can_simulate":status == "interrupted",
		"can_rts":status == "interrupted", "can_collect":false, "can_retry":false, "can_launch":false,
		"reason":"fixture exited", "result_ready":false}

func context() -> Dictionary:
	return {"date":"2026-10-04", "calendar":{"revision":17}, "player":{"id":"own0", "name":"Fixture"},
		"team":{"name":"Own"}, "stories":[], "inbox":[], "recent_matches":[], "calendar_events":[],
		"quick":{"mode":"quick", "year":2026, "choice_required":false}, "settings":{},
		"nextmatch":{"id":"interrupted-match", "due":true, "date":"2026-10-04", "opponent":"Other", "event":"Fixture event",
			"attendance":{"match_id":"interrupted-match", "destination":"lan", "is_today":true, "due":true,
				"phase":"in_progress", "can_return":true, "can_travel":false}},
		"match_preflight":{"match_id":"interrupted-match", "due":true, "phase":"launched", "side":"t",
			"can_simulate":true, "pending_map":"dust2", "played":false,
			"venue":{"destination":"lan", "match_id":"interrupted-match", "should_walk":true,
				"identity_source":"frozen_match_rosters", "travel_allowed":true},
			"veto":{"complete":true, "steps":[], "turn":null}}, "rts":{}}

func arena_room(mode: String) -> Dictionary:
	var cards: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://rts/data/rosters.json"))
	var room := {"id":"interrupted-room", "mode":mode, "phase":"launched", "map":"dust2", "ct":"a",
		"a":[], "b":[], "roster":{}, "human_id":"", "role_assignment_version":1, "picks":[], "bans":[]}
	for side in ["ct", "t"]:
		for player in cards[side]:
			room["a" if side == "ct" else "b"].append(player.id)
			room.roster[player.id] = player.duplicate(true)
	return room

func verify_map_transition(center) -> void:
	CareerBridge.context = context()
	CareerBridge.context.quick.unified_pace = true
	var first: Dictionary = CareerBridge.context.match_preflight.duplicate(true)
	first.merge({"map_key":"2026:fixture:interrupted-match:0", "maps_done":0, "session_pending":true, "revision":17}, true)
	CareerBridge.context.match_preflight = first.duplicate(true)
	center.result.clear(); center.saved_results.clear(); center.request_pending = false
	center.preflight = first.duplicate(true); center.connection = linked("interrupted-match")
	center.pace.flow.reset()
	Computer._navigate("career_match", false)
	var exited := linked("interrupted-match")
	exited.preflight = first.duplicate(true)
	var before := commands.size()
	for index in range(3):
		center.finished("/api/3d/match/collect", {"ok":true, "status":"waiting", "connection":exited, "replayed":true})
		check(center.is_interrupted() and button("CareerMatchResumeSimulate") != null, "empty collection retains recovery options " + str(index))
	check(commands.size() == before and center.result.is_empty(), "repeated empty collection never simulates or replays a map")
	center.finished("/api/3d/match/status?id=interrupted-match", {"ok":true, "preflight":first, "status":"interrupted", "match_id":"interrupted-match", "can_simulate":true, "can_resume":true})
	center.simulate_match("interrupted-match")
	center.simulate_match("interrupted-match")
	check(commands.size() == before + 1 and commands[-1].body.scope == "current_map", "rapid recovery clicks dispatch exactly one map")
	var next := first.duplicate(true)
	next.merge({"map_key":"2026:fixture:interrupted-match:1", "maps_done":1, "phase":"ready", "pending_map":"nuke", "session_pending":false, "revision":18}, true)
	var report := {"match_id":"interrupted-match", "result_id":"transition-report", "played":false,
		"team_a":"Own", "team_b":"Other", "series":"1-0", "source":"simulated", "totals":[],
		"maps":[{"index":0, "map":"dust2", "score":"13-8", "winner":"Own", "source":"sim"}]}
	CareerBridge.context.match_preflight = next.duplicate(true)
	CareerBridge.context.calendar.revision = 18
	center.finished("/api/3d/match/simulate", {"ok":true, "status":"paused", "preflight":next, "result":report})
	check(not center.is_interrupted() and center.connection.is_empty(), "simulated map retires the cached CS2 interruption")
	center.reveal_phase = "stats"
	check(center.pace.plan().primary == "模拟第 2 图", "report offers simulation of map two")
	center.finished("/api/3d/match/status?id=interrupted-match", {"ok":true, "preflight":first, "status":"interrupted", "match_id":"interrupted-match"})
	check(center.current_preflight().map_key == next.map_key and not center.is_interrupted(), "late map-one status cannot restore an old interruption")
	center.pace.primary()
	check(commands.size() == before + 2 and commands[-1].body.map_key == next.map_key, "next-map button dispatches map two without replaying map one")
	center.request_pending = false; center.pace.flow.reset(); center.result.clear(); center.saved_results.clear()
	var second := next.duplicate(true)
	second.phase = "launched"; second.session_pending = true
	CareerBridge.context.match_preflight = second.duplicate(true)
	center.preflight = second.duplicate(true)
	var waiting := linked("interrupted-match", "waiting")
	waiting.preflight = second; waiting.result = report; waiting.ok = true
	center.finished("/api/3d/match/status?id=interrupted-match", waiting)
	check(center.result.is_empty() and center.saved_results.is_empty(), "polling map two never opens map one's saved report")
	center.result.clear(); center.connection.clear(); center.preflight.clear(); center.request_pending = false

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args():
		get_tree().quit(2); return
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "no career service or HTTP endpoint")
	CareerBridge.set_process(false); Computer.set_process(false); Phone.set_process(false)
	CareerBridge.connected = true; CareerBridge.clock_held = true; CareerBridge.sound_muted = true
	Locale.set_language("zh-CN", false)
	scene_file_path = "res://lan.tscn"
	var center = Computer.match_center
	center.command_sender = send_fixture
	Computer.custom_room.command_sender = send_fixture
	Computer.ladder_command_sender = send_fixture
	Computer.rts_room.command_sender = send_fixture
	CareerBridge.context = context()
	center.preflight.clear(); center.result.clear(); center.connection = linked("interrupted-match")
	center.request_pending = false; center.show_real = false
	Travel.match_visit = {"match_id":"interrupted-match", "destination":"lan"}
	Computer.open_app("career_match", "lan")
	check(button("CareerMatchResumeCS2") != null and button("CareerMatchResumeSimulate") != null and button("CareerMatchResumeRTS") != null,
		"reopened project exposes all three career exits even before show_real is set")
	check(Travel.can_visit_match(center.current_preflight().venue, "interrupted-match"), "interrupted same-day match can return to its original venue")
	click("CareerMatchResumeCS2")
	check(commands[-1].path == "/api/3d/match/launch" and commands[-1].body.match_id == "interrupted-match" and commands[-1].body.side == "t", "resume uses launch with frozen match and side")
	center.request_pending = false; Computer._rebuild()
	click("CareerMatchResumeSimulate")
	check(commands[-1].path == "/api/3d/match/simulate" and commands[-1].body.match_id == "interrupted-match", "simulation reuses the unfinished series")
	center.request_pending = false; Computer._rebuild()
	click("CareerMatchResumeRTS")
	check(Computer.active_page == "rts" and Computer.rts_room.career_match_id == "interrupted-match", "RTS receives the original career match ID")
	click("CareerRTSStart")
	check(commands[-1].path == "/api/3d/rts/start" and commands[-1].body.match_id == "interrupted-match", "career RTS requests recovery from the backend")
	Computer.rts_room.pending_action = ""
	Computer._navigate("quick", false)
	CareerBridge.context.quick.unified_pace = true
	center.pace.flow.reset()
	var interrupted_count := commands.size()
	center.start_quick()
	check(commands.size() == interrupted_count and not center.quick_running, "interrupted map requires an explicit recovery choice")
	center.request_pending = false; center.quick_running = false
	center.connection = linked("interrupted-match", "starting")
	Computer._navigate("career_match", false)
	check(button("CareerMatchResumeCS2") == null and button("CareerMatchResumeSimulate") == null and button("CareerMatchResumeRTS") == null, "startup grace has no premature recovery actions")
	var before := commands.size()
	center.quick_running = true; center.quick_step()
	check(commands.size() == before, "startup grace cannot be overwritten by quick mode")
	center.connection = linked("interrupted-match", "failed")
	center.preflight = center.current_preflight().duplicate(true)
	center.preflight.session_pending = true
	center.quick_step()
	check(commands.size() == before, "a failed connection with an actual pending map cannot be overwritten")
	center.preflight.session_pending = false
	center.preflight.map_key = "2026:fixture:interrupted-match:0"
	center.start_quick()
	center.process(4.01)
	check(commands.size() == before + 1 and commands[-1].path == "/api/3d/match/simulate" and commands[-1].body.scope == "current_map", "a stale failed launch does not block explicit current-map continuation")
	center.request_pending = false
	center.quick_running = false
	center.connection = linked("interrupted-match", "waiting")
	center.connection.result_ready = true; center.connection.can_collect = true
	Computer._rebuild()
	check(button("CareerMatchResumeCS2") == null and button("CareerMatchResumeSimulate") == null, "a returned valid result is not presented as restartable")
	verify_map_transition(center)
	var cards: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://rts/data/rosters.json"))
	var room := arena_room("custom")
	var state := {"revision":9, "lobby":room, "maps":["dust2"], "rts_rosters":cards, "history":[], "connection":linked(room.id)}
	CareerBridge.context.custom = state; CareerBridge.context.ladder = {"revision":9, "lobby":room, "history":[], "player":{}}
	Computer.report.clear(); Computer.page_reports.clear(); Computer.custom_room.reset()
	Computer.custom_room.status = linked(room.id)
	Computer._navigate("custom", false)
	click("CustomResumeCS2")
	check(commands[-1].path == "/api/3d/custom/launch" and commands[-1].body.lobby_id == room.id, "custom resume keeps the ten-person room")
	Computer.custom_room.pending_action = ""; Computer._rebuild()
	click("CustomResumeSimulate")
	check(commands[-1].path == "/api/3d/custom/simulate" and commands[-1].body.lobby_id == room.id, "custom skip keeps its original map and identities")
	Computer.custom_room.pending_action = ""; Computer._rebuild()
	click("CustomResumeRTS")
	check(Computer.rts_room.eligible(), "interrupted custom room is eligible, not blocked by ready-only gate")
	Computer.rts_room.start_session()
	check(commands[-1].path == "/api/3d/rts/arena_start" and commands[-1].body.lobby_id == room.id and commands[-1].body.arena_revision == 9 and commands[-1].body.commanded_side == "ct", "custom recovery starts a result-bound RTS session")
	Computer.rts_room.pending_action = ""; Computer.rts_room.commanded_side = "b"
	Computer.rts_room.start_session()
	check(commands[-1].body.commanded_side == "t", "custom RTS preserves the selected B team rather than silently controlling CT")
	Computer.custom_room.status = linked(room.id, "waiting"); Computer.custom_room.status.cs2_running = true
	CareerBridge.context.custom.connection = Computer.custom_room.status.duplicate(true)
	Computer._navigate("custom", false)
	check(button("CustomResumeCS2") == null and button("CustomResumeSimulate") == null and button("CustomResumeRTS") == null and not Computer.rts_room.eligible(), "live custom room cannot be restarted or switched to RTS")
	Computer.rts_room.pending_action = ""
	room.mode = "rank"
	CareerBridge.context.custom = {}
	CareerBridge.context.ladder = {"revision":11, "lobby":room, "history":[], "player":{"elo":1600}}
	Computer.cs2_status = linked(room.id)
	Computer._navigate("ladder", false)
	click("LadderResumeCS2")
	check(commands[-1].path == "/api/3d/ladder/launch" and commands[-1].body.lobby_id == room.id and commands[-1].body.revision == 11, "ladder resume keeps the completed draft and BP")
	click("LadderResumeSimulate")
	check(commands[-1].path == "/api/3d/ladder/simulate" and commands[-1].body.lobby_id == room.id, "ladder can finish by simulation without a new match")
	click("LadderResumeCS2RTS")
	check(Computer.rts_room.ladder_eligible(), "interrupted ladder RTS bypasses the ready-only gate")
	click("LadderRTSStart")
	check(commands[-1].path == "/api/3d/rts/arena_start" and commands[-1].body.lobby_id == room.id, "ladder RTS recovers the same room")
	Computer.cs2_status = linked(room.id, "waiting"); Computer.cs2_status.cs2_running = true
	Computer._navigate("ladder", false)
	check(button("LadderResumeCS2") == null and button("LadderResumeSimulate") == null and button("LadderResumeCS2RTS") == null and not Computer.rts_room.ladder_eligible(), "live ladder room cannot be restarted or switched to RTS")
	Locale.set_language("en", false)
	check(Locale.text("重新进入 CS2 · 重开当前图") == "Re-enter CS2 · Restart this map", "resume copy is translated")
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service and not CareerBridge.busy and not is_instance_valid(Computer.rts_room.session), "all actions stayed in captured fixtures, no real match or save")
	print("CS2_RECOVERY_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
