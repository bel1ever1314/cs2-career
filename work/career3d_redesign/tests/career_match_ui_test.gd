extends Node
## Fixture-only UI contracts. It never starts the career service or CS2.
var failures: Array[String] = []
var checks := 0
var commands: Array = []
var capture_dir := ""

class SeatedFixture extends Node:
	func match_seated(id: String) -> bool:
		return id == "fixture-match"

func _ready() -> void:
	call_deferred("run")

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("CAREER_MATCH_UI_CHECK ", "PASS " if value else "FAIL ", label)

func send_fixture(path: String, body: Dictionary) -> bool:
	commands.append({"path":path, "body":body.duplicate(true)})
	return true

func settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame

func capture(label: String) -> void:
	if capture_dir.is_empty(): return
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	if image and not image.is_empty(): image.save_png(capture_dir.path_join(label + ".png"))

func button(fragment: String, device: Node = Computer) -> Button:
	for candidate in device.content.find_children("*", "Button", true, false):
		if fragment in candidate.text: return candidate
	return null

func fixture_result() -> Dictionary:
	var players := {"Green Team":[], "Orange Team":[]}
	var totals := []
	for i in range(10):
		var team := "Green Team" if i < 5 else "Orange Team"
		var row := {"player_id":"fixture-%d" % i, "name":"Player %d" % i, "team":team, "k":20 - i, "d":12, "a":4, "rating":1.30 - i * 0.03, "adr":90.0 - i, "kast":0.80}
		players[team].append(row.duplicate(true))
		totals.append(row.duplicate(true))
	return {"id":"fixture-match", "result_id":"fixture-series-receipt", "match_id":"fixture-match", "date":"2026-03-04", "event":"Fixture Championship", "team_a":"Green Team", "team_b":"Orange Team", "best_of":3, "series":[2, 0], "winner":"Green Team", "source":"simulated", "played":true, "player_id":"fixture-0", "player_team":"Green Team", "data_complete":true,
		"maps":[{"index":0, "map":"dust2", "score":"13-4", "winner":"Green Team", "source":"simulated", "rounds":17, "players":players}, {"index":1, "map":"mirage", "score":"13-2", "winner":"Green Team", "source":"simulated", "rounds":15, "players":players}], "totals":totals}

func fixture_reveal() -> Dictionary:
	return {"match_id":"fixture-match", "teams":["Green Team", "Orange Team"], "initial":[0, 0], "maps":[{"index":0, "map":"dust2", "score":"13-4", "winner":"Green Team", "rounds":["a", "a", "b", "a", "a", "b", "a", "a", "a", "b", "a", "a", "a", "b", "a", "a", "a"], "events_available":true}, {"index":1, "map":"mirage", "score":"13-2", "winner":"Green Team", "rounds":["a", "a", "a", "a", "b", "a", "a", "a", "a", "a", "a", "a", "b", "a", "a"], "events_available":true}]}

func drive_rounds(center: RefCounted) -> void:
	var guard := 0
	while center.reveal_phase == "maps" and guard < 100:
		if center.half_pause > 0: center.process(1.26)
		elif center.map_completed: center.process(2.01)
		else: center.process(0.29)
		guard += 1

func run() -> void:
	check("--test" in OS.get_cmdline_user_args() or "--no-service" in OS.get_cmdline_user_args(), "fixture requires a no-service flag")
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "no career service is started")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture-dir="): capture_dir = arg.trim_prefix("--capture-dir=")
	if not capture_dir.is_empty(): DirAccess.make_dir_recursive_absolute(capture_dir)
	get_viewport().size = Vector2i(1280, 720)
	CareerBridge.connected = true
	CareerBridge.clock_held = true
	CareerBridge.context = {"date":"2026-03-04", "calendar":{"revision":18}, "player":{"id":"fixture-0", "name":"Player 0"}, "team":{"name":"Green Team"}, "nextmatch":{"id":"fixture-match", "event":"Fixture Championship", "date":"2026-03-04", "opponent":"Orange Team", "best_of":3, "due":true}, "inbox":[], "stories":[], "recent_matches":[], "calendar_events":[], "quick":{"year":2026, "mode":"normal", "phase":"choice", "can_choose":true, "choice_required":true, "counter":0, "break_key":"", "break_ack":false}, "settings":{"steam_exe":"D:/Steam/steam.exe", "csgo_path":"E:/SteamLibrary/game/csgo", "mod_source_path":"D:/BotImprover", "difficulty":"Medium", "skins_inventory_mode":"career", "real_skins":false, "steam_id":""}}
	Computer.match_center.command_sender = send_fixture
	Computer.device_settings.command_sender = send_fixture
	Computer.tactics.command_sender = send_fixture
	Computer.set_process(false)
	Computer.open_app("career_match", "lan")
	await settle()
	check(Computer.location == "lan", "LAN workstation location is preserved")
	check(button("模拟当前比赛") != null and button("自己去 CS2 打") != null, "pending career game keeps simulation and direct CS2 actions")
	await capture("01-career-match")
	var root_id: int = Computer.content.get_child(0).get_instance_id()
	CareerBridge.context["clock"] = {"hour":9, "minute":21}
	Computer._context_changed()
	check(Computer.content.get_child(0).get_instance_id() == root_id, "clock projection does not repaint match page")
	Computer._busy_changed(true)
	Computer._busy_changed(false)
	await settle()
	check(Computer.content.get_child(0).get_instance_id() == root_id, "background GET busy transition does not repaint workstation")
	Computer.match_center.simulate_match("fixture-match")
	Computer.match_center.simulate_match("fixture-match")
	check(commands.size() == 1 and commands[-1].path == "/api/3d/match/simulate", "repeat click sends one engine simulation")
	check(commands[-1].body.revision == 18 and not str(commands[-1].body.request_id).is_empty(), "simulation carries revision and unique request id")
	var snapshot := fixture_result()
	var timeline := fixture_reveal()
	var untouched := JSON.stringify(snapshot)
	Computer._finished("/api/3d/match/simulate", {"ok":true, "result":snapshot, "reveal":timeline})
	var center: RefCounted = Computer.match_center
	check(center.shown_maps == 0 and center.round_cursor == 0 and center.live_score == [0, 0], "saved match begins with unrevealed zero score")
	root_id = Computer.content.get_child(0).get_instance_id()
	center.process(0.20)
	check(center.round_cursor == 0, "saved rounds wait for the pacing interval")
	center.process(0.09)
	check(center.round_cursor == 1 and center.live_score == [1, 0], "first score comes from saved first round winner")
	check(Computer.content.get_child(0).get_instance_id() == root_id, "round score updates labels in place")
	for i in range(11): center.process(0.29)
	check(center.round_cursor == 12 and center.half_pause > 0, "round twelve pauses at halftime")
	var half_score: Array = center.live_score.duplicate()
	center.process(0.50)
	check(center.round_cursor == 12 and center.live_score == half_score, "halftime retains the exact saved score")
	await settle()
	await capture("02-halftime")
	center.process(0.76)
	for i in range(5): center.process(0.29)
	check(center.map_completed and center.shown_maps == 1 and center.live_score == [13, 4], "first map ends at its saved score")
	var stage := Computer.content.find_child("CareerScoreStage", true, false) as PanelContainer
	check(stage.get_theme_stylebox("panel").bg_color == center.WIN_SURFACE, "completed own-team map uses a muted green background")
	check(Computer.content.find_children("CareerScorePlayer_*", "Button", true, false).size() == 10, "per-map scoreboard appears after map end")
	center.process(1.95)
	check(center.map_cursor == 0, "map result holds for two seconds")
	center.process(0.06)
	check(center.map_cursor == 1 and center.live_score == [0, 0], "next map starts without revealing its final score")
	Computer.close_computer()
	var before_round: int = center.round_cursor
	center.process(10)
	check(center.round_cursor == before_round, "closing pauses presentation without rerunning simulation")
	Computer.open_app("career_match", "lan")
	check(commands.size() == 1 and center.map_cursor == 1, "reopening resumes the saved match")
	drive_rounds(center)
	check(center.reveal_phase == "stats" and not center.continue_ready, "final statistics remain before continue becomes available")
	await settle()
	var own := Computer.content.find_child("CareerScorePlayer_fixture-0", true, false) as Button
	check(own != null and "你" in own.text and own.get_theme_stylebox("normal").bg_color == preload("res://scripts/computer_ui.gd").MINT, "controlled career player is highlighted in full ten-player statistics")
	check(Computer.content.find_children("CareerScorePlayer_*", "Button", true, false).size() == 10, "final scoreboard contains exactly ten actual players")
	check(Computer.content.get_combined_minimum_size().x <= Computer.scroll.size.x + 1, "scoreboard fits workstation width")
	check(Computer.content.size.y <= Computer.scroll.size.y + 1, "final ten-player statistics fit without scrolling")
	stage = Computer.content.find_child("CareerScoreStage", true, false) as PanelContainer
	check(stage.get_theme_stylebox("panel").bg_color == center.WIN_SURFACE, "final own-team victory retains muted green stage background")
	center.result["winner"] = "Orange Team"
	Computer._rebuild()
	stage = Computer.content.find_child("CareerScoreStage", true, false) as PanelContainer
	check(stage.get_theme_stylebox("panel").bg_color == center.LOSS_SURFACE, "saved defeat uses a muted rose stage background")
	center.result["winner"] = "Unknown Team"
	Computer._rebuild()
	stage = Computer.content.find_child("CareerScoreStage", true, false) as PanelContainer
	check(stage.get_theme_stylebox("panel").bg_color == preload("res://scripts/computer_ui.gd").PAPER, "unknown winner keeps a neutral stage background")
	center.result["winner"] = "Green Team"
	Computer._rebuild()
	if Computer.content.size.y > Computer.scroll.size.y + 1:
		print("SCORE_LAYOUT ", Computer.content.size, " available ", Computer.scroll.size)
		for child in Computer.content.get_children(): print("SCORE_LAYOUT_CHILD ", child.name, " ", child.size)
	await capture("03-full-statistics")
	center.process(3.95)
	check(not center.continue_ready, "full stats hold for four seconds")
	center.process(0.06)
	check(center.continue_ready and not center.result.is_empty(), "normal mode requires an explicit continue")
	check(JSON.stringify(snapshot) == untouched, "presentation never mutates backend snapshot")
	center.continue_result()
	Computer._finished("/api/3d/match/simulate", {"ok":true, "replayed":true, "result":snapshot, "reveal":timeline})
	check(center.result.is_empty() and commands.size() == 1, "replayed receipt never restarts settlement or animation")
	var missing := snapshot.duplicate(true)
	missing["result_id"] = "missing-round-events"
	missing["maps"] = [missing.maps[0]]
	center.begin_reveal(missing)
	Computer._rebuild()
	center.process(0.29)
	check(center.round_cursor == 0 and center.live_score == [0, 0], "missing round events never invent a score path")
	center.process(1.72)
	check(center.map_completed and center.round_cursor == 0, "missing event map reveals only its saved final result")
	center.result.clear()
	center.reveal_phase = ""
	var original_scene := get_tree().current_scene
	var seated_fixture := SeatedFixture.new()
	seated_fixture.scene_file_path = "res://lan.tscn"
	get_tree().root.add_child(seated_fixture)
	get_tree().current_scene = seated_fixture
	Travel.match_visit = {"match_id":"fixture-match", "destination":"lan"}
	var info := {"match_id":"fixture-match", "phase":"veto", "can_launch":false, "can_simulate":true, "venue":{"destination":"lan", "match_id":"fixture-match"}, "veto":{"complete":false, "steps":[], "available":["dust2", "mirage"], "turn":{"team":"Green Team", "action":"ban", "mine":true}}}
	center.show_real = true
	Computer._finished("/api/3d/match/preflight", {"ok":true, "preflight":info})
	check(button("Dust") != null and button("交给队长") != null, "career CS2 preflight exposes map BP")
	info["phase"] = "ready"
	info["can_launch"] = true
	info["pending_map"] = "dust2"
	info["veto"]["complete"] = true
	Computer._finished("/api/3d/match/status?id=fixture-match", {"ok":true, "match_id":"fixture-match", "status":"ready", "preflight":info, "can_launch":false, "cs2_running":true})
	check(button("CT 开场") == null, "live CS2 process prevents a new map launch")
	Computer._finished("/api/3d/match/status?id=fixture-match", {"ok":true, "match_id":"fixture-match", "status":"ready", "preflight":info, "can_launch":true, "cs2_running":false})
	check(button("CT 开场") != null and button("T 开场") != null, "closed CS2 process offers both starting sides")
	var waiting := info.duplicate(true)
	waiting["phase"] = "waiting"
	Computer._finished("/api/3d/match/launch", {"ok":true, "connection":{"ok":true, "match_id":"fixture-match", "phase":"waiting", "status":"waiting", "preflight":waiting, "can_launch":false, "reason":"等待真实战绩"}})
	check(center.current_preflight().phase == "waiting" and button("检查并录入") != null, "launch connection updates the actual preflight phase")
	var connection := {"ok":true, "match_id":"fixture-match", "phase":"waiting", "status":"waiting", "preflight":waiting, "can_launch":false, "result_ready":false, "reason":"等待真实战绩"}
	Computer._finished("/api/3d/match/status?id=fixture-match", connection)
	root_id = Computer.content.get_child(0).get_instance_id()
	Computer._finished("/api/3d/match/status?id=fixture-match", connection)
	check(Computer.content.get_child(0).get_instance_id() == root_id, "unchanged CS2 polling leaves the page untouched")
	connection["result_ready"] = true
	Computer._finished("/api/3d/match/status?id=fixture-match", connection)
	await settle()
	check(commands[-1].path == "/api/3d/match/collect" and commands[-1].body.match_id == "fixture-match" and not commands[-1].body.has("result"), "ready CS2 result automatically requests nonce-bound backend ingestion")
	center.request_pending = false
	var partial := snapshot.duplicate(true)
	partial["result_id"] = "fixture-real-partial"
	partial["played"] = false
	partial["source"] = "cs2"
	partial["maps"] = [partial.maps[0]]
	partial["series"] = [1, 0]
	Computer._finished("/api/3d/match/collect", {"ok":true, "result":partial, "preflight":info})
	check(center.current_preflight().phase == "ready" and center.connection.is_empty(), "real map collection clears stale waiting connection and retains next-map preflight")
	drive_rounds(center)
	center.process(4.01)
	center.continue_result()
	check(center.show_real and center.result.is_empty() and button("CT 开场") == null, "partial CS2 result returns to next-map process check before launch")
	center.connection = {"match_id":"fixture-match", "can_retry":true, "status":"failed"}
	center.preflight = waiting.duplicate(true)
	center.preflight["side"] = "t"
	Computer._rebuild()
	button("重试进入 CS2").pressed.emit()
	check(commands[-1].path == "/api/3d/match/launch" and commands[-1].body.side == "t", "launch retry retains the map's frozen starting side")
	center.request_pending = false
	get_tree().current_scene = original_scene
	Travel.match_visit.clear()
	seated_fixture.queue_free()
	Computer.open_app("quick", "club")
	check(button("本赛季使用快速模式") != null, "PC quick season has a direct mode selection outside mail")
	Phone.present("match")
	check(button("快速赛季", Phone) != null, "phone赛事 has a direct quick-season entry outside mail")
	Phone.present("quick")
	check(button("本赛季使用快速模式", Phone) != null, "phone quick mode uses shared season controls")
	center.choose_mode(true)
	check(commands[-1].path == "/api/3d/season/mode" and commands[-1].body.quick_mode is bool and commands[-1].body.quick_mode, "quick mode sends the backend boolean contract")
	center.request_pending = false
	CareerBridge.context.quick = {"year":2026, "mode":"quick", "phase":"running", "can_choose":false, "choice_required":false, "counter":1, "break_key":"", "break_ack":false}
	Computer.open_app("quick", "club")
	CareerBridge.context.quick["break_key"] = "fixture-break"
	CareerBridge.context.quick["break_ack"] = true
	Computer._rebuild()
	check(button("结束这次休赛停留") == null and button("开始 / 继续快速赛季") != null, "acknowledged boolean break remains runnable without repeated resume")
	CareerBridge.context.quick["break_ack"] = false
	Computer._rebuild()
	check(button("结束这次休赛停留") != null, "unacknowledged break requires an explicit keyed resume")
	CareerBridge.context.quick["break_key"] = ""
	Computer._rebuild()
	center.start_quick()
	check(commands[-1].path == "/api/3d/season/run" and commands[-1].body.max_steps == 1, "quick season advances one bounded step at a time")
	var quick_snapshot := snapshot.duplicate(true)
	quick_snapshot["result_id"] = "quick-fixture-receipt"
	Computer._finished("/api/3d/season/run", {"ok":true, "quick":CareerBridge.context.quick, "result":quick_snapshot, "reveal":timeline})
	drive_rounds(center)
	var before_commands := commands.size()
	center.process(4.01)
	check(center.result.is_empty() and center.quick_running and commands.size() == before_commands, "quick mode waits through full statistics before scheduling the next step")
	center.process(0.81)
	check(commands.size() == before_commands + 1 and commands[-1].path == "/api/3d/season/run", "next quick step begins after presentation completes")
	center.request_pending = false
	center.quick_running = false
	Computer.open_app("settings", "club")
	check(Computer.content.find_child("DeviceSetting_mod_source_path", true, false) != null and Computer.content.find_child("DeviceSetting_difficulty", true, false) != null, "PC settings include Bot Improver path and original difficulty presets")
	Computer.device_settings.set_value("mod_source_path", "D:/FixtureImprover")
	Computer.device_settings.set_value("difficulty", "High")
	Computer.device_settings.set_value("skins_inventory_mode", "external")
	Computer.device_settings.set_value("real_skins", true)
	Computer.device_settings.set_value("steam_id", "76561198000000000")
	Phone.present("settings")
	var form := Phone.content.find_child("DeviceSetting_mod_source_path", true, false) as LineEdit
	check(form != null and form.text == "D:/FixtureImprover", "phone and PC retain one shared unsaved configuration form")
	Computer.device_settings.submit()
	check(commands[-1].path == "/api/3d/settings" and commands[-1].body.settings.mod_source_path == "D:/FixtureImprover" and commands[-1].body.settings.difficulty == "High", "settings submit the configured external Bot Improver path and difficulty")
	check(commands[-1].body.settings.skins_inventory_mode == "external" and commands[-1].body.real_skins and commands[-1].body.steam_id == "76561198000000000", "optional skin source and account use backend settings fields")
	Computer.device_settings.saving = false
	Computer.device_settings.set_value("mod_source_path", "D:/UnsavedDraft")
	Computer.device_settings.finished("/api/3d/settings", {"ok":true, "settings":CareerBridge.context.settings})
	check(Computer.device_settings.dirty and Computer.device_settings.draft.mod_source_path == "D:/UnsavedDraft", "late read-only settings response preserves the user's unsaved draft")
	await settle()
	await capture("04-phone-settings")
	Computer.open_app("tactics", "club")
	Computer.tactics.libraries["de_dust2"] = {"map":"de_dust2", "tactics":[], "map_meta":{"pos_x":-2476, "pos_y":3239, "scale":4.4, "width":1024, "height":1024}, "available_maps":[{"map":"de_dust2", "name":"Dust II"}, {"map":"de_mirage", "name":"Mirage"}]}
	Computer._rebuild()
	check(Computer.active_page == "tactics" and Computer.content.find_child("TacticsMapCanvas", true, false) != null, "meeting-room hook opens a desktop map editor")
	var editor: RefCounted = Computer.tactics
	editor.draft["name"] = "Fixture route"
	editor.point_chosen([-1000, 2000], false)
	editor.point_chosen([-900, 2000], true)
	check(editor.steps()[0].position == [-1000, 2000] and editor.steps()[0].look_at == [-900, 2000], "waypoint and look target preserve world coordinate data")
	editor.steps()[0]["wait"] = 12.5
	editor.steps()[0]["movement"] = "walk"
	editor.select_slot(2)
	editor.point_chosen([-900, 1800], false)
	check(editor.draft.slots.size() == 5 and editor.steps().size() == 1, "editor keeps five independent route slots")
	var canvas := Computer.content.find_child("TacticsMapCanvas", true, false)
	await settle()
	var world: Array = [-1000.0, 2000.0]
	var restored: Array = canvas.canvas_to_world(canvas.world_to_canvas(world))
	check(absf(float(restored[0]) - world[0]) < 0.01 and absf(float(restored[1]) - world[1]) < 0.01, "canvas projection roundtrips the backend overview metadata")
	editor.change_map("de_mirage")
	editor.confirm_pending()
	check(editor.map_code == "de_mirage", "confirmed map switch opens the selected map")
	editor.change_map("de_dust2")
	check(editor.draft.name == "Fixture route" and editor.draft.slots[0].steps[0].movement == "walk", "switching maps retains each map's unsaved draft")
	editor.assignment_changed("ability")
	editor.set_human()
	editor.save_tactic()
	check(commands[-1].path == "/api/3d/tactics/save" and commands[-1].body.map == "de_dust2" and commands[-1].body.tactic.slots.size() == 5, "tactics use the existing multimap save contract")
	check(commands[-1].body.tactic.slots[0].steps[0].wait == 12.5 and commands[-1].body.tactic.slots[0].steps[0].movement == "walk", "hold time and movement are saved as original data fields")
	check(commands[-1].body.tactic.assignment == "ability" and commands[-1].body.tactic.human_slot == 2, "ability assignment retains the chosen human slot")
	var saved_tactic: Dictionary = commands[-1].body.tactic.duplicate(true)
	editor.finished("/api/3d/tactics/save", {"ok":true, "map":"de_dust2", "tactic":saved_tactic, "tactics":[saved_tactic]})
	editor.selected_slot = 1
	editor.selected_step = 0
	editor.clear_look()
	check(editor.steps()[0].has("look_at") and editor.steps()[0].look_at == null, "clear-look preserves required nullable contract field")
	await settle()
	check(Computer.content.get_combined_minimum_size().x <= Computer.scroll.size.x + 1, "tactics controls fit workstation width")
	await capture("05-tactics")
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service and not CareerBridge.busy, "all fixture actions avoid network, real saves and CS2 launch")
	print("CAREER_MATCH_UI_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
