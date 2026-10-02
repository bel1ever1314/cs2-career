extends Node
## Uses an actual isolated command receipt, then drives only in-memory GUI state.
var failures: Array[String] = []
var checks := 0
var commands: Array = []
var capture_dir := ""

func _ready() -> void:
	call_deferred("run")

func check(value: bool, caption: String) -> void:
	checks += 1
	if not value: failures.append(caption)
	print("QUICK_REPLAY_CHECK ", "PASS " if value else "FAIL ", caption)

func send_fixture(path: String, body: Dictionary) -> bool:
	commands.append({"path":path, "body":body.duplicate(true)})
	return true

func settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame

func capture(caption: String) -> void:
	if capture_dir.is_empty(): return
	await RenderingServer.frame_post_draw
	var picture := get_viewport().get_texture().get_image()
	if picture and not picture.is_empty(): picture.save_png(capture_dir.path_join(caption + ".png"))

func cell(id: String, field: String) -> Label:
	return Computer.content.find_child("CareerScore_%s_%s" % [id.validate_node_name(), field], true, false) as Label

func button() -> Button:
	return Computer.content.find_child("CareerMatchContinue", true, false) as Button

func drive_rounds(center: RefCounted) -> void:
	var guard := 0
	while center.reveal_phase == "maps" and guard < 300:
		if center.half_pause > 0: center.process(1.26)
		elif center.map_completed: center.process(2.01)
		else: center.process(0.29)
		guard += 1

func run() -> void:
	check("--no-service" in OS.get_cmdline_user_args(), "requires no-service and never connects to a career save")
	var fixture_file := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--fixture-file="): fixture_file = arg.trim_prefix("--fixture-file=")
		if arg.begins_with("--capture-dir="): capture_dir = arg.trim_prefix("--capture-dir=")
	if not capture_dir.is_empty(): DirAccess.make_dir_recursive_absolute(capture_dir)
	var response = JSON.parse_string(FileAccess.get_file_as_string(fixture_file))
	if not response is Dictionary:
		check(false, "fixture contains an actual command receipt")
		get_tree().quit(1)
		return
	var snapshot: Dictionary = response.result.duplicate(true)
	var timeline: Dictionary = response.reveal.duplicate(true)
	var unchanged := JSON.stringify(response)
	get_viewport().size = Vector2i(1280, 720)
	CareerBridge.connected = true
	CareerBridge.clock_held = true
	CareerBridge.context = {"calendar":{"revision":18}, "date":snapshot.get("date", ""), "player":{"id":snapshot.player_id}, "team":{"name":snapshot.player_team}, "inbox":[], "stories":[], "recent_matches":[], "calendar_events":[], "quick":{"year":2026, "mode":"quick", "phase":"running", "choice_required":false, "counter":1, "break_key":"", "break_ack":false}}
	Computer.set_process(false)
	var center: RefCounted = Computer.match_center
	center.command_sender = send_fixture
	center.quick_running = true
	Computer.open_app("quick", "club")
	center.begin_reveal(snapshot, timeline)
	Computer._rebuild()
	await settle()
	var own := str(snapshot.player_id)
	check(center.live_score == [0, 0] and center.round_cursor == 0, "saved final score is concealed at replay start")
	check(cell(own, "k").text == "0" and cell(own, "adr").text == "—", "first-frame player row starts at zero with unmeasured rates")
	check(Computer.content.find_children("CareerScorePlayer_*", "Button", true, false).size() == 10, "all ten actual players appear while rounds replay")
	var first_board: int = center.scoreboard.get_instance_id()
	center.process(0.29)
	var first: Dictionary = timeline.maps[0].round_frames[0]
	var own_first: Dictionary = {}
	for player in first.players:
		if str(player.player_id) == own: own_first = player
	check(cell(own, "k").text == str(int(own_first.k)) and cell(own, "rating").text == "%.2f" % own_first.rating, "first round updates measured player cells from actual receipt")
	check(center.scoreboard.get_instance_id() == first_board, "per-round stats repaint in place without resetting page or clicks")
	check("首杀" in center.event_label.text, "raw opening-kill event is visible")
	check(center.round_strip.completed == 1 and center.round_strip.own_side in ["a", "b"], "round strip reveals only completed outcomes relative to own team")
	check(center.round_strip.WIN == Color("478bc5") and center.round_strip.LOSS == Color("c96560"), "own wins are blue and own losses red")
	for i in range(11): center.process(0.29)
	check(center.round_cursor == 12 and center.half_pause > 0, "twelve-round boundary has a visible halftime pause")
	await settle()
	check(Computer.content.get_combined_minimum_size().x <= Computer.scroll.size.x + 1, "aligned scoreboard and strip fit the workstation width")
	print("QUICK_REPLAY_LAYOUT live ", Computer.content.size, " available ", Computer.scroll.size, " board ", center.scoreboard.size)
	check(Computer.content.size.y <= Computer.scroll.size.y + 1, "live replay fits workstation height without hiding the table")
	var first_adr := cell(own, "adr")
	var other_id := str(first.players[-1].player_id)
	check(absf(first_adr.global_position.x - cell(other_id, "adr").global_position.x) < 0.1, "numeric columns align across both teams")
	await capture("01-halftime")
	drive_rounds(center)
	await settle()
	check(center.reveal_phase == "stats" and not center.continue_ready, "final full-series table preserves automatic four-second wait")
	check(button() != null and button().text == "下一场" and not button().disabled, "next-match button is immediately usable during final table wait")
	print("QUICK_REPLAY_LAYOUT final ", Computer.content.size, " available ", Computer.scroll.size, " board ", center.scoreboard.size)
	check(Computer.content.size.y <= Computer.scroll.size.y + 1, "full-series ten-player table fits workstation height")
	await capture("02-final-scoreboard")
	button().pressed.emit()
	check(center.result.is_empty() and center.quick_running and commands.size() == 1 and commands[0].path == "/api/3d/season/run", "manual next skips remaining wait and sends one bounded next step")
	center.continue_result()
	center.process(10.0)
	check(commands.size() == 1, "repeat next and timer cannot send another command while pending")
	center.request_pending = false
	Computer._finished("/api/3d/season/run", {"ok":true, "quick":CareerBridge.context.quick, "result":snapshot, "reveal":timeline})
	check(center.result.is_empty() and commands.size() == 1, "replayed receipt never presents or settles completed match again")
	var automatic := snapshot.duplicate(true)
	automatic["result_id"] = str(snapshot.result_id) + "-automatic-ui"
	center.begin_reveal(automatic, timeline)
	Computer._rebuild()
	drive_rounds(center)
	center.process(3.95)
	check(not center.result.is_empty() and commands.size() == 1, "automatic continuation still waits for full statistic interval")
	center.process(0.06)
	check(center.result.is_empty() and commands.size() == 1, "automatic expiry closes presentation without resimulating it")
	center.process(0.81)
	check(commands.size() == 2 and commands[-1].path == "/api/3d/season/run", "automatic path schedules one next step after its normal interval")
	center.request_pending = false
	center.quick_running = false
	var legacy := snapshot.duplicate(true)
	legacy["result_id"] = str(snapshot.result_id) + "-legacy-ui"
	legacy["maps"] = [legacy.maps[0]]
	center.begin_reveal(legacy)
	Computer._rebuild()
	center.process(0.29)
	check(center.round_cursor == 0 and cell(own, "k").text == "—" and not center.round_strip.rounds.size(), "legacy missing history shows no invented rounds or evolving stats")
	center.process(1.72)
	await settle()
	check(center.map_completed and cell(own, "k").text != "—", "legacy map displays saved final scoreboard when its reveal completes")
	check(JSON.stringify(response) == unchanged and CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "all UI presentation leaves actual command receipt unchanged and service stopped")
	print("QUICK_REPLAY_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
