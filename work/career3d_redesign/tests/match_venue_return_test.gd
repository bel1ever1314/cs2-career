extends Node
## Follow the real return callback without a backend, real save or CS2 launch.
var failures: Array[String] = []
var checks := 0
var commands: Array[Dictionary] = []

func _ready() -> void:
	if get_parent() != Travel:
		var runner = get_script().new()
		Travel.add_child(runner)
	else:
		call_deferred("run")

func check(value: bool, caption: String) -> void:
	checks += 1
	if not value: failures.append(caption)
	print("MATCH_VENUE_RETURN ", "PASS " if value else "FAIL ", caption)

func send_fixture(path: String, body: Dictionary) -> bool:
	commands.append({"path":path, "body":body.duplicate(true)})
	return true

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args():
		get_tree().quit(1)
		return
	CareerBridge.connected = false
	CareerBridge.set_process(false)
	CareerBridge.sound_muted = true
	Computer.set_process(false)
	Phone.set_process(false)
	var own: Array = []
	var other: Array = []
	for index in range(5):
		own.append({"id":"own_"+str(index), "player_id":"own_"+str(index), "name":"Ally "+str(index), "team":"Own", "role":"rifle"})
		other.append({"id":"opp_"+str(index), "player_id":"opp_"+str(index), "name":"Other "+str(index), "team":"Other", "role":"rifle"})
	var venue := {"destination":"lan", "match_id":"return-fixture", "identity_source":"frozen_match_rosters",
		"travel_allowed":true, "should_walk":true, "team_a":"Own", "team_b":"Other", "own_team":"Own", "human_id":"own_0",
		"players_a":own, "players_b":other, "event_name":"Return Fixture", "name":"Original venue"}
	var info := {"match_id":"return-fixture", "phase":"launched", "due":true, "can_launch":false, "can_simulate":false,
		"side":"t", "date":"2026-07-21", "venue":venue.duplicate(true), "veto":{"complete":true, "turn":null, "order":["dust2"]}}
	var attendance := {"match_id":"return-fixture", "destination":"lan", "display_name":"Original venue", "phase":"in_progress",
		"is_today":true, "due":true, "can_travel":false, "can_return":true, "instruction":"返回原场馆。"}
	CareerBridge.context = {"date":"2026-07-21", "calendar":{"revision":18}, "player":{"id":"own_0", "name":"Ally 0"},
		"team":{"name":"Own", "roster":own.duplicate(true)}, "stories":[], "inbox":[],
		"nextmatch":{"id":"return-fixture", "date":"2026-07-21", "event":"Return Fixture", "opponent":"Other", "due":true, "attendance":attendance},
		"match_preflight":info.duplicate(true), "quick":{"mode":"normal"}}
	var center = Computer.match_center
	center.preflight.clear()
	center.connection.clear()
	center.result.clear()
	center.request_pending = false
	center.venue_after_preflight = ""
	center.command_sender = send_fixture
	Computer.open_app("career_match", "bedroom")
	check(Travel.can_visit_match(venue, "return-fixture"), "pending same-day session has a valid original venue")
	Travel.menu_open = true
	Travel._confirm_menu("lan")
	check(commands.size() == 1 and commands[0].path == "/api/3d/match/preflight", "door return requests preflight only")
	check(center.venue_after_preflight == "return-fixture", "return remembers the original match ID")
	var frozen := JSON.stringify(venue)
	Computer._finished("/api/3d/match/preflight", {"ok":true, "status":"waiting", "resume_only":true, "read_only":true, "replayed":true,
		"reason":"返回原场馆。", "preflight":info.duplicate(true), "result":null})
	check(not center.request_pending and center.venue_after_preflight.is_empty(), "read-only response completes the pending return")
	check(Travel.match_visit.get("match_id", "") == "return-fixture", "waiting response enters the original venue instead of blocking")
	var until := Time.get_ticks_msec() + 30000
	while Travel.busy and Time.get_ticks_msec() < until:
		await get_tree().process_frame
	var scene := get_tree().current_scene
	check(not Travel.busy and scene != null and scene.scene_file_path == Travel.SCENES.lan, "physical LAN scene loads")
	check(JSON.stringify(Travel.match_visit.get("venue", {})) == frozen, "return preserves the frozen ten-player venue")
	check(center.current_preflight().get("phase", "") == "launched" and center.result.is_empty(), "return neither finishes the match nor resets preparation")
	check(commands.size() == 1 and commands[0].body.get("match_id") == "return-fixture", "return sends no launch, collection or simulation command")
	var before := Travel.match_visit.duplicate(true)
	center.venue_after_preflight = "return-fixture"
	Computer._finished("/api/3d/match/preflight", {"ok":true, "status":"paused", "reason":"另有比赛等待回传。", "preflight":info.duplicate(true)})
	check(not Travel.busy and Travel.match_visit == before, "a real paused preflight cannot start another venue visit")
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "test has no real service or save access")
	print("MATCH_VENUE_RETURN_RESULT ", JSON.stringify({"checks":checks, "failures":failures, "cs2_launches":0}))
	get_tree().quit(0 if failures.is_empty() else 1)
