extends Node
## Real door-menu mouse routing, using only an in-memory match projection.
## The arrival scene is packed in memory; no service, CS2 or saved career is used.
var checks := 0
var failures: Array[String] = []
var commands: Array[Dictionary] = []
var accept_commands := true
var last_mouse := Vector2.ZERO
var cached_arrival: PackedScene

func _ready() -> void:
	if not "--no-service" in OS.get_cmdline_user_args() or not "--test" in OS.get_cmdline_user_args():
		push_error("Door match feedback regression requires --test --no-service.")
		get_tree().quit(1)
		return
	if get_parent() != Travel:
		var runner = get_script().new()
		Travel.add_child(runner)
	else:
		call_deferred("run")

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("DOOR_MATCH_CHECK ", "PASS " if value else "FAIL ", label)

func settle(count: int = 3) -> void:
	for _index in range(count): await get_tree().process_frame

func move_mouse(point: Vector2) -> void:
	var event := InputEventMouseMotion.new()
	event.position = point
	event.global_position = point
	event.relative = point - last_mouse
	Input.parse_input_event(event)
	Input.flush_buffered_events()
	last_mouse = point
	await settle()

func mouse_button(point: Vector2, pressed: bool) -> void:
	var event := InputEventMouseButton.new()
	event.position = point
	event.global_position = point
	event.button_index = MOUSE_BUTTON_LEFT
	event.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
	event.pressed = pressed
	Input.parse_input_event(event)
	Input.flush_buffered_events()
	await settle()

func click(control: Control) -> void:
	var point := control.get_global_rect().get_center()
	await move_mouse(point)
	await mouse_button(point, true)
	await mouse_button(point, false)

func send_fixture(path: String, body: Dictionary) -> bool:
	commands.append({"path":path, "body":body.duplicate(true)})
	return accept_commands

func fixture_context(stories: Array = []) -> Dictionary:
	var plan := {"match_id":"door-fixture", "date":"2026-10-03", "event_name":"Door Fixture Event", "opponent":"Other",
		"destination":"lan", "display_name":"Fixture LAN", "planned":true, "phase":"today", "due":true,
		"is_today":true, "can_travel":true, "can_return":false, "instruction":"到门口选择 Fixture LAN。"}
	return {"date":"2026-10-03", "calendar":{"revision":8}, "player":{"id":"own_0", "name":"Ally 0"},
		"start":{"creation_required":false}, "team":{"name":"Own"}, "stories":stories, "inbox":[],
		"feedback":{"items":[]}, "settings":{}, "nextmatch":{"id":"door-fixture", "date":"2026-10-03",
			"event":"Door Fixture Event", "opponent":"Other", "due":true, "best_of":3, "attendance":plan}, "match_preflight":{}}

func fixture_preflight() -> Dictionary:
	var own: Array = []
	var other: Array = []
	for index in range(5):
		own.append({"id":"own_" + str(index), "player_id":"own_" + str(index), "name":"Ally " + str(index), "team":"Own", "role":"rifle"})
		other.append({"id":"other_" + str(index), "player_id":"other_" + str(index), "name":"Other " + str(index), "team":"Other", "role":"rifle"})
	var venue := {"destination":"lan", "match_id":"door-fixture", "identity_source":"frozen_match_rosters", "travel_allowed":true,
		"should_walk":true, "team_a":"Own", "team_b":"Other", "own_team":"Own", "human_id":"own_0",
		"players_a":own, "players_b":other, "event_name":"Door Fixture Event", "display_name":"Fixture LAN"}
	return {"match_id":"door-fixture", "phase":"veto", "date":"2026-10-03", "due":true, "venue":venue,
		"can_launch":false, "can_simulate":true, "veto":{"complete":false, "turn":null, "steps":[], "available":[]}}

func door_status() -> Label:
	return Travel.menu.find_child("DoorTravelStatus", true, false) as Label

func resolve_button() -> Button:
	return Travel.menu.find_child("DoorTravelResolve", true, false) as Button

func text_in(root: Node, fragment: String) -> bool:
	for label in root.find_children("*", "Label", true, false):
		if fragment in label.text: return true
	return false

func destination_button(destination: String) -> Button:
	var index: int = Travel.menu.destinations.find(destination)
	return Travel.menu.buttons[index] if index >= 0 else null

func open_door() -> Button:
	Travel.close_menu()
	Travel.door_dismissed = false
	check(Travel.open_menu("bedroom"), "physical-bedroom door opens the production travel menu")
	await settle()
	return destination_button("lan")

func reset_match_request() -> void:
	var center = Computer.match_center
	center.preflight.clear()
	center.connection.clear()
	center.result.clear()
	center.request_pending = false
	center.pending_action = ""
	center.venue_after_preflight = ""
	center.notice = ""
	Travel.finish_door_request("")

func prepare_lightweight_arrival() -> void:
	var destination := Node.new()
	destination.name = "DoorFixtureArrival"
	cached_arrival = PackedScene.new()
	check(cached_arrival.pack(destination) == OK, "isolated arrival scene packs in memory")
	destination.free()
	# ResourceLoader uses this cached resource for the normal Travel.go chain.
	# Only this test process changes its cache: the shipped LAN scene is untouched.
	cached_arrival.take_over_path(Travel.SCENES["lan"])

func check_resolution_locations(origin: Node) -> void:
	for location in ["bedroom", "club", "lan", "major"]:
		Computer.close_computer()
		Phone.close_phone()
		Travel.close_menu()
		Travel.match_visit.clear()
		origin.scene_file_path = Travel.SCENES[location]
		CareerBridge._apply_context(fixture_context())
		reset_match_request()
		accept_commands = false
		CareerBridge.message = "Fixture request unavailable."
		check(Travel.open_menu(location), location + " physical doorway opens its menu")
		await settle()
		var target := destination_button("lan")
		check(target != null, location + " doorway includes this match's destination")
		if target != null: await click(target)
		var resolve := resolve_button()
		check(resolve != null and resolve.is_visible_in_tree() and not Travel.menu.notice_events, location + " non-story failure offers preparation rather than story resolution")
		if resolve != null: await click(resolve)
		check(Computer.screen.visible and Computer.active_page == "career_match" and Computer.location == location, location + " resolution preserves the actual workstation location")
		Computer._navigate("scrim")
		await settle()
		if location == "club":
			check(text_in(Computer.content, "约一场训练赛"), "club resolution retains its genuine training-workstation access")
		else:
			check(text_in(Computer.content, "请到俱乐部工作站约训练赛。") and not text_in(Computer.content, "约一场训练赛"), location + " resolution cannot grant club-only scrim access")
	Computer.close_computer()
	Phone.close_phone()
	Travel.close_menu()
	accept_commands = true
	origin.scene_file_path = Travel.SCENES["bedroom"]
	CareerBridge._apply_context(fixture_context())
	reset_match_request()

func run() -> void:
	get_window().content_scale_size = Vector2i(1280, 890)
	get_window().size = Vector2i(1280, 890)
	if DisplayServer.get_name() != "headless": await get_tree().create_timer(.15).timeout
	var origin := get_tree().current_scene
	origin.scene_file_path = Travel.SCENES["bedroom"]
	CareerBridge.set_process(false)
	Computer.set_process(false)
	Phone.set_process(false)
	CareerBridge.feedback.set_process(false)
	CareerBridge.sound_muted = true
	CareerBridge.connected = true
	CareerBridge.clock_held = true
	CareerBridge.busy = false
	CareerBridge.active_post = false
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	Computer.close_computer()
	Phone.close_phone()
	CareerBridge._apply_context(fixture_context())
	Computer.match_center.command_sender = send_fixture
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "fixture has no backend or saved career")
	var target := await open_door()
	check(target != null and not target.disabled and target.is_visible_in_tree(), "match destination is a visible enabled button")
	if target == null:
		finish()
		return
	var point := target.get_global_rect().get_center()
	var original_button_id := target.get_instance_id()
	await move_mouse(point)
	await mouse_button(point, true)
	var refreshed := fixture_context()
	refreshed["unrelated_fixture_value"] = 1
	CareerBridge._apply_context(refreshed)
	await settle()
	check(is_instance_valid(target) and destination_button("lan").get_instance_id() == original_button_id, "unrelated context update preserves the button held by the mouse")
	await mouse_button(point, false)
	check(commands.size() == 1 and commands[0].path == "/api/3d/match/preflight" and commands[0].body.match_id == "door-fixture", "real press/update/release confirms the destination exactly once")
	check(Computer.match_center.request_pending and Travel.menu.request_pending, "door and match controller share the pending preparation state")
	check(Travel.menu_open and Travel.menu.screen.visible and not Travel.busy, "waiting for preflight keeps the door menu visible without travelling")
	var pending_command_count := commands.size()
	Travel.menu.confirm()
	Travel._confirm_menu("lan")
	check(commands.size() == pending_command_count and target.disabled, "pending doorway refuses duplicate confirmation and disables its destinations")
	var status := door_status()
	check(status != null and status.is_visible_in_tree() and not status.text.is_empty(), "pending preparation is explained beside the destination")
	var paused_reason := "有新事件，请先由你作出选择，再继续模拟。"
	var stories := [{"id":"door-story", "title":"Fixture decision", "text":"请作出本场决定。", "choices":[{"id":"continue", "label":"继续"}]}]
	var blocked_context := fixture_context(stories)
	CareerBridge._apply_context(blocked_context)
	Computer._finished("/api/3d/match/preflight", {"ok":true, "status":"paused", "reason":paused_reason, "preflight":fixture_preflight(), "result":null})
	await settle()
	status = door_status()
	check(not Computer.match_center.request_pending and not Travel.menu.request_pending and not Travel.busy, "paused preflight releases pending state without entering the venue")
	check(status != null and status.is_visible_in_tree() and paused_reason in status.text, "the actual paused reason is visible in the door menu")
	check(not Computer.screen.visible and Travel.menu_open, "blocked doorway does not require opening a hidden computer")
	var resolve := resolve_button()
	check(resolve != null and resolve.is_visible_in_tree() and not resolve.disabled, "pending-story doorway offers an enabled resolution button")
	if resolve != null: await click(resolve)
	check(Phone.screen.visible and Phone.active_page == "stories" and not Travel.menu_open, "real resolution click opens the pending story and closes the door menu")
	check(commands.size() == 1, "opening the story never simulates, launches or answers it automatically")
	Phone.close_phone()
	CareerBridge._apply_context(fixture_context())
	reset_match_request()
	target = await open_door()
	if target != null: await click(target)
	check(Travel.menu.request_pending, "second door preparation is pending before walking away")
	Travel.close_menu()
	CareerBridge._apply_context(fixture_context(stories))
	Computer._finished("/api/3d/match/preflight", {"ok":true, "status":"paused", "reason":paused_reason, "preflight":fixture_preflight(), "result":null})
	await settle()
	check(not Travel.menu.request_pending and not Computer.match_center.request_pending and not Travel.menu_open and not Travel.menu.screen.visible, "a completion after walking away releases pending state without reopening the door")
	target = await open_door()
	status = door_status()
	check(status != null and status.is_visible_in_tree() and paused_reason in status.text, "returning to the door retains the pending-story explanation")
	CareerBridge._apply_context(fixture_context())
	await settle()
	status = door_status()
	resolve = resolve_button()
	check(status != null and status.text.is_empty() and not status.visible and resolve != null and not resolve.visible and not Travel.menu.notice_events, "resolving the story clears its stale door notice and action")
	reset_match_request()
	accept_commands = false
	CareerBridge.message = "操作未发出：本地后台尚未连接。"
	target = await open_door()
	if target != null: await click(target)
	await settle()
	status = door_status()
	check(not Travel.menu.request_pending and not Computer.match_center.request_pending and not Travel.busy, "request refusal cannot leave the door spinning")
	check(status != null and status.is_visible_in_tree() and not status.text.is_empty(), "request refusal has a visible door notice")
	accept_commands = true
	reset_match_request()
	target = await open_door()
	if target != null: await click(target)
	var rejected := fixture_preflight()
	rejected.venue.travel_allowed = false
	Computer._finished("/api/3d/match/preflight", {"ok":true, "status":"veto", "preflight":rejected, "result":null})
	await settle()
	status = door_status()
	check(not Travel.busy and not Travel.menu.request_pending and Travel.menu_open, "invalid physical handoff stays at the original door and releases waiting state")
	check(status != null and status.is_visible_in_tree() and not status.text.is_empty(), "rejected physical handoff explains how to view preparation")
	reset_match_request()
	await check_resolution_locations(origin)
	prepare_lightweight_arrival()
	target = await open_door()
	var prior_commands := commands.size()
	if target != null: await click(target)
	check(commands.size() == prior_commands + 1 and commands[-1].path == "/api/3d/match/preflight", "a retry prepares only the current match")
	var info := fixture_preflight()
	var accepted_context := fixture_context()
	accepted_context.match_preflight = info.duplicate(true)
	CareerBridge._apply_context(accepted_context)
	Computer._finished("/api/3d/match/preflight", {"ok":true, "status":"veto", "reason":"比赛准备已保存。", "preflight":info, "result":null})
	var deadline := Time.get_ticks_msec() + 10000
	while Travel.busy and Time.get_ticks_msec() < deadline: await get_tree().process_frame
	await settle()
	var arrived := get_tree().current_scene
	check(not Travel.busy and arrived != null and arrived.name == "DoorFixtureArrival" and arrived.scene_file_path == Travel.SCENES["lan"], "successful door preflight performs the actual in-process scene handoff")
	check(not Travel.menu_open and not Travel.menu.request_pending, "arrival clears the doorway and waiting state")
	check(Travel.match_visit.get("match_id", "") == "door-fixture" and Travel.match_visit.get("venue", {}) == info.venue, "arrival preserves this match's frozen roster")
	check(commands.all(func(command): return command.path == "/api/3d/match/preflight"), "all mouse routes avoid launch, simulation and story writes")
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service and CareerBridge.active_path.is_empty() and CareerBridge.queued_command.is_empty(), "fixture never touches a service, CS2 or real career save")
	finish()

func finish() -> void:
	print("DOOR_MATCH_RESULT ", JSON.stringify({"checks":checks, "failures":failures, "display_server":DisplayServer.get_name(), "cs2_launches":0}))
	get_tree().quit(0 if failures.is_empty() else 1)
