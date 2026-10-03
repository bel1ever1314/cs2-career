extends Node
## Boundary regression only: frozen isolated HTTP session + natural Godot report.
## No network, Career save, report fabrication or autonomous match is run here.
var failures: Array[String] = []
var checks := 0
var commands: Array = []

func _ready() -> void:
	call_deferred("run")

func check(value: bool, caption: String) -> void:
	checks += 1
	if not value: failures.append(caption)
	print("CAREER_RTS_UI_CHECK ", "PASS " if value else "FAIL ", caption)

func settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame

func button(name_value: String) -> Button:
	return Computer.content.find_child(name_value, true, false) as Button

func has_label(value: String) -> bool:
	for node in Computer.content.find_children("*", "Label", true, false):
		if value in node.text: return true
	return false

func take_command() -> Dictionary:
	var value := CareerBridge.queued_command.duplicate(true)
	CareerBridge.queued_command.clear()
	if not value.is_empty(): commands.append(value)
	return value

func reply(path: String, result: Dictionary) -> void:
	CareerBridge.command_finished.emit("/api/3d/rts/" + path, result)

func key(code: Key) -> InputEventKey:
	var value := InputEventKey.new()
	value.keycode = code; value.physical_keycode = code; value.pressed = true
	return value

func close_dialogs(parent: Node) -> void:
	for child in parent.get_children():
		if child is AcceptDialog: child.hide(); child.queue_free()

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args():
		push_error("RTS UI regression requires --no-service.")
		get_tree().quit(2); return
	var session_file := ""
	var report_file := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--session-file="): session_file = arg.trim_prefix("--session-file=")
		if arg.begins_with("--report-file="): report_file = arg.trim_prefix("--report-file=")
	for path in [session_file, report_file]:
		if not path.is_absolute_path() or path.left(3).to_upper() not in ["D:/", "E:/"] or not FileAccess.file_exists(path):
			push_error("Use explicit isolated D/E JSON fixture paths.")
			get_tree().quit(2); return
	var saved = JSON.parse_string(FileAccess.get_file_as_string(session_file))
	var raw = JSON.parse_string(FileAccess.get_file_as_string(report_file))
	if not saved is Dictionary or not raw is Dictionary:
		push_error("Isolated session and report must be JSON dictionaries.")
		get_tree().quit(2); return
	check(raw.get("finished", false) and raw.get("map", "") == saved.get("map", "") and int(raw.get("seed", -1)) == int(saved.get("seed", -2)), "actual completed report matches frozen map and seed")
	check(saved.get("rosters", {}).get("ct", []).size() == 5 and saved.rosters.get("t", []).size() == 5 and raw.get("players", []).size() == 10, "fixture contains frozen ten-person identity and a measured final table")
	if not failures.is_empty(): get_tree().quit(1); return
	var saved_original := JSON.stringify(saved)
	var report_original := JSON.stringify(raw)
	CareerBridge.set_process(false)
	CareerBridge.connected = true; CareerBridge.clock_held = true
	# Existing read-poll queue accepts clicks but cannot issue HTTP with no endpoint.
	CareerBridge.busy = true; CareerBridge.active_post = false
	CareerBridge.queued_command.clear()
	CareerBridge.context = {"date":"2026-10-02", "calendar":{"revision":61}, "player":{"id":saved.player_id},
		"team":{"name":saved.rosters.team_names.t}, "stories":[], "inbox":[], "contacts":[], "calendar_events":[], "recent_matches":[],
		"rts":{"session":saved.duplicate(true), "pending":true},
		"match_preflight":{"match_id":"wrong-stale-match", "due":true, "played":false},
		"custom":{"lobby":{"mode":"custom", "phase":"ready", "map":"dust2", "ct":"a"}, "rts_rosters":saved.rosters.duplicate(true)}}
	Computer.set_process(false); Phone.set_process(false)
	Computer.open_app("rts", "club")
	await settle()
	var room: RefCounted = Computer.rts_room
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service and not CareerBridge.is_processing(), "no service started, polled or connected")
	check(room.career_match_id == str(saved.match_id) and button("CareerRTSRestart") != null, "pending frozen match overrides stale preflight and supplies restart entry")
	check(not button("CareerRTSRestart").disabled, "legacy context without career_maps remains compatible with validated map catalog")
	check(not has_label("开始自定义指挥"), "pending formal map cannot start a separate custom match")
	CareerBridge.context.rts["career_maps"] = []
	CareerBridge.context.rts["limitations"] = {str(saved.map):"fixture map is not career-ready"}
	Computer._rebuild(); await settle()
	check(button("CareerRTSRestart").disabled and has_label("fixture map is not career-ready"), "explicit restricted frozen map disables restart and explains limitation")
	CareerBridge.context.rts.erase("career_maps"); CareerBridge.context.rts.erase("limitations")
	Computer._rebuild(); await settle()
	button("CareerRTSCancel").pressed.emit()
	check(is_instance_valid(room.exit_dialog) and CareerBridge.queued_command.is_empty(), "lobby cancellation requests confirmation before any command")
	room.exit_dialog.canceled.emit(); await settle()
	check(not is_instance_valid(room.exit_dialog) and CareerBridge.queued_command.is_empty() and CareerBridge.context.rts.session == saved, "dismissed lobby confirmation preserves frozen map and sends nothing")
	button("CareerRTSCancel").pressed.emit(); room.exit_dialog.confirmed.emit()
	var canceled := take_command()
	check(canceled.get("path", "") == "/api/3d/rts/cancel" and canceled.get("body", {}).get("match_id", "") == saved.match_id and canceled.body.get("nonce", "") == saved.nonce, "confirmed lobby cancellation uses exact frozen match and nonce")
	CareerBridge.context.rts = {"session":{}, "pending":false, "career_maps":[], "limitations":{str(saved.map):"fixture map is not career-ready"}}
	reply("cancel", {"ok":true}); await settle()
	CareerBridge.context.match_preflight = {"match_id":saved.match_id, "due":true, "played":false, "pending_map":{"map":saved.map}}
	Computer._rebuild(); await settle()
	check(button("CareerRTSStart").disabled and has_label("fixture map is not career-ready"), "explicit restricted next-map dictionary disables formal start")
	CareerBridge.context.match_preflight.pending_map = str(saved.map)
	Computer._rebuild(); await settle()
	check(button("CareerRTSStart").disabled, "string next-map projection has the same restriction")
	CareerBridge.context.match_preflight.pending_map = null
	Computer._rebuild(); await settle()
	check(not button("CareerRTSStart").disabled, "unprepared BP can still request normal backend preparation")
	CareerBridge.context.rts.erase("career_maps"); CareerBridge.context.rts.erase("limitations")
	button("CareerRTSStart").pressed.emit()
	var started := take_command()
	check(started.get("path", "") == "/api/3d/rts/start" and started.get("body", {}).get("match_id", "") == saved.match_id and started.body.get("revision", 0) == 61, "formal prepare click emits one revision-bound start command")
	CareerBridge.context.rts = {"session":saved.duplicate(true), "pending":true}
	reply("start", {"ok":true, "rts_session":saved.duplicate(true)}); await settle()
	var game = room.session
	if not is_instance_valid(game) or game.sim == null:
		check(false, "frozen formal game instantiated and configured")
		print("CAREER_RTS_UI_RESULT ", JSON.stringify({"checks":checks,"failures":failures}))
		get_tree().quit(1); return
	game.set_process(false)
	check(game.embedded and game.initial_map == saved.map and int(game.seed_value) == int(saved.seed), "embedded career session uses frozen map and deterministic seed")
	check(game.initial_overtime and game.sim._allow_overtime, "career game enables real MR3 overtime in the simulator")
	check(game.initial_team == saved.commanded_side and game.viewer_team == saved.commanded_side and game.mode == "command", "commanded side remains frozen through game start")
	check(game.initial_rosters == saved.rosters and game.rosters == saved.rosters and room.frozen == saved, "complete frozen roster and skills pass to game without remapping")
	check(game.initial_player_id == saved.player_id and is_instance_valid(game.mode_button), "embedded game binds the real Career character and exposes mode switching")
	game.open_scoreboard()
	var headings_match := true
	for side in ["ct", "t"]: headings_match = headings_match and game.scoreboard_team_headings[side].text == saved.rosters.team_names[side]
	check(headings_match, "scoreboard headings use actual frozen clubs, not sample teams")
	game._close_scoreboard()
	check(game.cycle_mode() and game.mode == "play" and game.sim.human_id == saved.player_id and game.speed == 1.0, "command mode switches to real bound character without roster or result reset")
	var teammate_id := ""
	for actor in game.state.players:
		if actor.team == game.viewer_team and actor.id != saved.player_id: teammate_id = str(actor.id); break
	game._select_actor(teammate_id)
	check(game.lock_player_identity and game.sim.human_id == saved.player_id, "Career personal play cannot replace the bound character by clicking another teammate")
	check(game.cycle_mode() and game.mode == "spectate" and not game.sim._human_control, "spectate releases held character input and restores autonomous teammate")
	check(game.cycle_mode() and game.mode == "command" and not game.sim._human_control, "spectate returns to team command in the same round")
	var bound_actor: Dictionary = game.sim._players[game.sim._ids[saved.player_id]]
	bound_actor["alive"] = false
	game.state = game.sim.snapshot(true)
	check(game.cycle_mode() and game.mode == "spectate" and not game.sim._human_control and game.sim.human_id == saved.player_id, "dead bound player skips personal control without taking over a different teammate")
	check(game.cycle_mode() and game.mode == "command", "dead bound player can still return from viewing to team command")
	bound_actor["alive"] = true
	game.state = game.sim.snapshot(true)
	var expected_ids: Array = []
	for side in ["ct", "t"]:
		for player in saved.rosters[side]: expected_ids.append(str(player.id))
	var actual_ids: Array = []
	for player in game.sim.snapshot(true).players: actual_ids.append(str(player.id))
	check(actual_ids == expected_ids, "simulated ten-person stable IDs preserve backend order and identity")
	Phone.present("home")
	Phone._input(key(KEY_P)); Computer._input(key(KEY_P))
	check(not Phone.screen.visible and Computer.screen.visible and room.session == game, "phone presentation and P cannot bypass active formal RTS")
	game.scoreboard.hide(); game.main_menu.hide(); game._input(key(KEY_ESCAPE))
	check(is_instance_valid(room.exit_dialog) and room.session == game and CareerBridge.queued_command.is_empty(), "unfinished Esc asks confirmation and retains active game")
	var first_dialog: int = room.exit_dialog.get_instance_id()
	Computer.close_computer(false)
	check(Computer.screen.visible and room.exit_dialog.get_instance_id() == first_dialog, "workstation close cannot bypass or duplicate exit confirmation")
	room.exit_dialog.canceled.emit(); await settle()
	check(room.session == game and room.frozen == saved and room.last_report.is_empty() and CareerBridge.queued_command.is_empty(), "canceling exit keeps unfinished game and does not submit partial statistics")
	room.close_session(); room.exit_dialog.confirmed.emit()
	var exit_cancel := take_command()
	check(exit_cancel.get("path", "") == "/api/3d/rts/cancel" and exit_cancel.get("body", {}).get("nonce", "") == saved.nonce, "confirmed unfinished exit cancels only its nonce-bound map")
	check(not room.close_session() and CareerBridge.queued_command.is_empty() and room.session == game, "pending cancellation blocks repeat exits until receipt arrives")
	CareerBridge.context.rts = {"session":{}, "pending":false}
	reply("cancel", {"ok":true}); await settle()
	check(not is_instance_valid(room.session) and room.frozen.is_empty() and room.last_report.is_empty(), "acknowledged cancel closes game without recording unfinished result")
	CareerBridge.context.rts = {"session":saved.duplicate(true), "pending":true}
	room.begin_saved(saved); await settle()
	game = room.session; game.set_process(false)
	# Emit an actual exported completion report to isolate front-end handoff logic.
	game.match_completed.emit(raw)
	var submitted := take_command()
	check(submitted.get("path", "") == "/api/3d/rts/submit" and submitted.get("body", {}).get("nonce", "") == saved.nonce and submitted.body.get("match_id", "") == saved.match_id, "match-completed signal forwards raw report with frozen match and nonce")
	check(submitted.body.report == raw and submitted.body.revision == 61 and room.last_report == raw, "submission carries exact measured round ledger and revision, not a second simulation")
	raw["ui_mutation_probe"] = true
	check(not room.last_report.has("ui_mutation_probe") and not submitted.body.report.has("ui_mutation_probe"), "report handoff owns deep copies rather than mutable signal references")
	raw.erase("ui_mutation_probe")
	check(not room.close_session() and CareerBridge.queued_command.is_empty() and room.session == game, "pending submit cannot send another result or close game early")
	reply("submit", {"ok":false, "msg":"isolated rejected receipt"}); await settle()
	check(room.pending_action.is_empty() and room.last_report == raw and room.frozen == saved and room.session == game, "failed submission retains raw report and frozen nonce for explicit retry")
	check(game.get_children().any(func(node): return node is AcceptDialog and "原战绩仍保留" in node.dialog_text), "failed receipt visibly explains retained report and retry action")
	close_dialogs(game); await settle()
	check(not room.close_session(), "return after failure requests retry and keeps game until saved")
	var retried := take_command()
	check(retried == submitted and room.pending_action == "submit", "retry sends identical raw result and frozen nonce without resimulation")
	CareerBridge.context.rts = {"session":{}, "pending":false}
	reply("submit", {"ok":true, "status":"finished"}); await settle()
	check(room.frozen.is_empty() and room.pending_action.is_empty() and room.session == game, "successful receipt settles first and retains completion display until return")
	close_dialogs(game); await settle()
	check(room.close_session() and not is_instance_valid(room.session) and CareerBridge.queued_command.is_empty(), "settled return closes embedded game with no duplicate write")
	Phone.present("home")
	check(Phone.screen.visible and not Computer.screen.visible, "normal phone navigation resumes after settled game closes")
	Phone.close_phone()
	var arena_saved: Dictionary = saved.duplicate(true)
	arena_saved["kind"] = "arena"; arena_saved["lobby_id"] = "ladder-fixture"; arena_saved["match_id"] = ""
	CareerBridge.context.rts = {"session":{}, "arena_session":{}, "career_maps":[str(saved.map)]}
	CareerBridge.context["ladder"] = {"revision":18, "lobby":{"id":"ladder-fixture", "mode":"rank", "phase":"ready", "map":str(saved.map).trim_prefix("de_")}}
	room.open_ladder(); await settle()
	check(room.ladder_eligible() and button("LadderRTSStart") != null and not button("LadderRTSStart").disabled, "completed draft and supported BP provide a playable ladder RTS entry")
	button("LadderRTSStart").pressed.emit()
	var arena_started := take_command()
	check(arena_started.get("path", "") == "/api/3d/rts/arena_start" and arena_started.body.get("arena_revision") == 18 and arena_started.body.get("revision") == 61, "ladder start carries both independent revisions and exact lobby identity")
	CareerBridge.context.rts.arena_session = arena_saved.duplicate(true)
	reply("arena_start", {"ok":true,"rts_session":arena_saved}); await settle()
	game = room.session; game.set_process(false)
	check(room.entry_kind == "arena" and room.frozen.lobby_id == "ladder-fixture" and game.initial_player_id == saved.player_id, "ladder RTS freezes its own session while retaining the Career-bound character")
	game.match_completed.emit(raw)
	var arena_submitted := take_command()
	check(arena_submitted.get("path", "") == "/api/3d/rts/arena_submit" and arena_submitted.body.get("lobby_id") == "ladder-fixture" and arena_submitted.body.get("nonce") == arena_saved.nonce and arena_submitted.body.report == raw, "ladder completion submits measured ledger to local ladder rather than Career")
	CareerBridge.context.rts.arena_session = {}
	# A successful save may be retried without another game; display remains until return.
	reply("arena_submit", {"ok":true,"status":"finished"}); await settle()
	close_dialogs(game); await settle()
	check(room.frozen.is_empty() and room.close_session() and CareerBridge.queued_command.is_empty(), "successful ladder result returns without a repeated write")
	CareerBridge.context.rts.arena_session = arena_saved.duplicate(true)
	room.open_ladder(); await settle()
	check(button("CareerRTSRestart") != null and room.career_match_id.is_empty(), "unsettled ladder session resumes without borrowing a stale Career match")
	button("CareerRTSCancel").pressed.emit(); room.exit_dialog.confirmed.emit()
	var arena_canceled := take_command()
	check(arena_canceled.get("path", "") == "/api/3d/rts/arena_cancel" and arena_canceled.body.get("arena_revision") == 18 and arena_canceled.body.get("lobby_id") == "ladder-fixture", "ladder cancel affects only its own nonce-bound lobby")
	CareerBridge.context.rts.arena_session = {}
	reply("arena_cancel", {"ok":true}); await settle()
	check(room.frozen.is_empty() and room.pending_action.is_empty() and not is_instance_valid(room.session), "acknowledged ladder cancellation leaves neither controller nor pending input")
	CareerBridge.context.ladder.lobby = {}
	CareerBridge.context.match_preflight = {}
	var custom_roster := {}
	var custom_a: Array = []; var custom_b: Array = []
	for side in ["ct", "t"]:
		for actor in saved.rosters[side]:
			custom_roster[str(actor.id)] = actor.duplicate(true)
			if side == "ct": custom_a.append(str(actor.id))
			else: custom_b.append(str(actor.id))
	CareerBridge.context.custom = {"maps":["dust2","mirage","overpass","nuke"], "lobby":{"id":"custom-eight-map-fixture", "mode":"custom", "phase":"ready", "map":"mirage", "ct":"a", "a":custom_a, "b":custom_b, "roster":custom_roster}, "rts_rosters":saved.rosters.duplicate(true)}
	Computer.report.clear()
	Computer.open_app("custom", "club"); await settle()
	check(button("CustomRTS") != null and not button("CustomRTS").disabled, "custom setup exposes RTS for a validated map other than Dust2")
	button("CustomRTS").pressed.emit(); await settle()
	check(room.entry_kind == "custom" and room.career_match_id.is_empty() and room.eligible() and button("LadderRTSStart") == null, "custom RTS button cannot reopen a stale ladder session")
	CareerBridge.context.custom.lobby.map = "overpass"
	Computer.open_app("custom", "club"); await settle()
	check(not button("CustomRTS").disabled, "Overpass becomes available in actual custom setup after completion validation")
	CareerBridge.context.custom.lobby.map = "nuke"
	Computer.open_app("custom", "club"); await settle()
	check(not button("CustomRTS").disabled, "custom setup exposes verified layered Nuke navigation")
	button("CustomRTS").pressed.emit();await settle()
	CareerBridge.busy=false # Local custom launch needs no queued HTTP operation.
	room.start_session();await settle()
	CareerBridge.busy=true
	var layered_game=room.session
	check(is_instance_valid(layered_game) and layered_game.initial_map=="de_nuke" and layered_game.sim!=null,"embedded custom Nuke uses its actual layered resource")
	if is_instance_valid(layered_game):
		layered_game.set_process(false)
		check(layered_game.sim.get_map_model().validation_report()["layer_identity_preserved"],"embedded map preserves actual floor identities")
		layered_game.renderer.set_layer(1)
		check(layered_game.renderer.view_layer==1 and layered_game.renderer.texture!=null,"embedded lower floor has its own readable radar")
		check(layered_game.find_child("RTSFloorSwitch",true,false)!=null,"embedded RTS exposes floor switching control")
		room.close_session();await settle()
	room.entry_kind = "arena"; room.career_match_id = "stale-match"
	Computer.open_app("battle", "club"); await settle()
	button("ComputerOpenRTS").pressed.emit(); await settle()
	check(room.entry_kind == "custom" and room.career_match_id.is_empty(), "battle-center RTS entry clears stale ladder and Career selection")
	Computer.close_computer()
	check(JSON.stringify(saved) == saved_original and JSON.stringify(raw) == report_original, "UI regression leaves both isolated input fixtures unchanged")
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service and CareerBridge.process_id == -1, "entire boundary regression remains disconnected from Career saves")
	CareerBridge.busy = false; CareerBridge.queued_command.clear()
	print("CAREER_RTS_UI_RESULT ", JSON.stringify({"checks":checks,"commands":commands.size(),"failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
