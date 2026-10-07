extends Node
const Flow = preload("res://scripts/career_pace_controller.gd")
var checks := 0
var failures: Array[String] = []
var sent: Array = []

func _ready() -> void:
	call_deferred("run")

func check(value: bool, text: String) -> void:
	checks += 1
	if not value: failures.append(text)
	print("PACE_CHECK ", "PASS " if value else "FAIL ", text)

func capture(path: String, body: Dictionary) -> bool:
	sent.append({"path":path, "body":body.duplicate(true)})
	return true

func screenshot(name: String) -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture-output="):
			await RenderingServer.frame_post_draw
			var folder := arg.trim_prefix("--capture-output=")
			DirAccess.make_dir_recursive_absolute(folder)
			get_viewport().get_texture().get_image().save_png(folder.path_join(name + ".png"))

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(1); return
	var flow = Flow.new()
	flow.resume(); flow.arm("prepare", "bo:0")
	check(not flow.tick(3.99, true), "four second preparation is not rounded down")
	flow.reserve("cs2", "bo:0")
	check(flow.take("bo:0") == "cs2", "deadline click reserves CS2")
	check(flow.take("bo:0", "simulate").is_empty(), "same deadline cannot dispatch a second command")
	flow.in_flight = false; flow.arm("reveal", "bo:1"); flow.reserve("rts", "bo:1")
	flow.completed(false, "bo:1")
	check(flow.tick(4.0, true) and flow.take("bo:1") == "rts", "reservation applies to next map in this BO")
	flow.reserve("cs2", "bo:2"); flow.completed(true, "other:0")
	check(flow.reservation.is_empty(), "2-0 clears third-map reservation")
	flow.pause()
	check(not flow.tick(100, true), "pause never catches up missed wall time")
	flow.reset(); check(not flow.running and flow.phase == "paused", "restart starts paused")
	flow.resume(); flow.arm("waiting", "bo:1")
	check(not flow.tick(100, false) and flow.remaining == 4.0, "busy and awards do not consume countdown")
	CareerBridge.set_process(false); Computer.set_process(false); Phone.set_process(false)
	CareerBridge.connected = true; CareerBridge.busy = false; CareerBridge.clock_held = true
	Locale.set_language("zh-CN", false)
	scene_file_path = "res://play.tscn"
	CareerBridge.context = {"date":"2026-07-21", "calendar":{"revision":18}, "player":{"id":"p", "name":"P"}, "team":{"name":"Vitality"}, "stories":[], "quick":{"unified_pace":true,"year":2026,"season_phase":"running"},
		"nextmatch":{"id":"fixture", "due":true,"opponent":"Spirit","event":"Cup","best_of":3,"attendance":{"destination":"club"}},
		"match_preflight":{"match_id":"fixture","map_key":"2026:cup:fixture:0","due":true,"maps_done":0,"team_a":"Vitality","team_b":"Spirit","phase":"ready","venue":{"entry_completed":true},"veto":{},"pending_map":null}}
	Computer.active_page = "start"
	Computer.screen.visible = true
	# Exercise the real creation acknowledgement without replacing the test scene.
	Travel.busy = true
	Computer.career_start.finished("/api/3d/start/create", {"ok":true})
	Travel.busy = false
	CareerBridge.clock_held = true
	var center = Computer.match_center
	center.command_sender = capture
	check(not Computer.screen.visible and Computer.active_page == "desktop", "creation closes the computer and leaves its next opening on the desktop")
	center.process(60)
	check(not Computer.screen.visible and not center.quick_running and sent.is_empty(), "creation never opens a match or starts advancing after travel")
	Computer.present("club")
	center.process(60)
	check(Computer.active_page == "desktop" and not center.quick_running and sent.is_empty(), "opening the computer only displays the desktop")
	check(Computer.content.find_child("DesktopNextMatch", true, false) != null and Computer.content.find_child("ComputerDesktopAgenda", true, false) != null, "existing next-match card and right-hand agenda remain available")
	center.preflight.clear(); center.result.clear(); center.request_pending = false
	Computer.open_app("career_match", "club")
	center.process(60)
	check(not center.quick_running and sent.is_empty(), "viewing the upcoming match does not advance it")
	Computer.open_app("quick", "club")
	center.process(60)
	check(not center.quick_running and sent.is_empty(), "opening the progression page still waits for an explicit action")
	for resolution in [Vector2i(1280,720), Vector2i(1920,1080)]:
		get_viewport().size = resolution
		await get_tree().process_frame
		Computer._rebuild()
		await get_tree().process_frame
		for id in ["PaceContinue", "PaceCS2", "PaceRTS", "PacePause"]:
			var node: Button = Computer.pace_footer.find_child(id, true, false)
			check(node != null and get_viewport().get_visible_rect().encloses(node.get_global_rect()) and Computer.panel.get_global_rect().encloses(node.get_global_rect()), id + " visible at " + str(resolution))
		await screenshot("preparation-" + str(resolution.x))
	var advance: Button = Computer.pace_footer.find_child("PacePause", true, false)
	advance.pressed.emit()
	check(center.quick_running, "existing automatic-advance button starts progression when clicked")
	center.process(3.9)
	check(sent.is_empty(), "no simulation before preparation expires")
	center.process(0.11)
	check(sent.size() == 1 and sent[0].path.ends_with("/simulate"), "one map dispatched at deadline")
	check(sent[0].body.get("scope") == "current_map" and sent[0].body.get("map_key") == "2026:cup:fixture:0", "command carries explicit scope and map identity")
	center.pace.choose("cs2")
	check(sent.size() == 1, "takeover click cannot race in-flight simulation")
	center.request_pending = false; center.pace.flow.in_flight = false
	center.pace.flow.resume(); Computer._navigate("training")
	check(not center.quick_running, "leaving match page pauses auto advance")
	Computer.open_app("quick", "club"); center.pace.flow.resume(); CareerBridge.connected = false
	center.process(30)
	check(not center.quick_running, "disconnect pauses, reconnect does not resume")
	CareerBridge.connected = true; center.process(30)
	check(sent.size() == 1, "reconnection cannot issue a hidden command")
	center.preflight.clear(); center.connection.clear()
	CareerBridge.context.match_preflight.map_key = "2026:cup:fixture:1"
	CareerBridge.context.match_preflight.pending_map = "nuke"
	center.begin_reveal({"match_id":"fixture","result_id":"fixture-map-one","maps":[{"index":0,"map":"dust2","score":"13-8","winner":"Vitality"}], "played":false,"team_a":"Vitality","team_b":"Spirit","series":"1-0","totals":[]})
	center.pace.flow.resume()
	center.reveal_phase = "stats"
	center.process(0.01)
	check(center.pace.flow.phase == "waiting", "saved map enters the shared inter-map wait")
	center.process(3.8)
	check(sent.size() == 1, "next map remains ungenerated during report wait")
	center.process(0.3)
	check(sent.size() == 2 and sent[1].body.get("map_key") == "2026:cup:fixture:1", "after four seconds only the next map is dispatched")
	center.request_pending = false; center.pace.flow.reset()
	print("UNIFIED_PACE_RESULT checks=", checks, " failures=", failures.size())
	get_tree().quit(0 if failures.is_empty() else 1)
