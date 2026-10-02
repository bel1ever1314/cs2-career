extends Node
## Main scene: -- --no-service --travel-menu-test. Use Windows GUI for capture checks.
## Real input traverses production handlers; Travel owns this suite across handoffs.
var failures: Array[String] = []
var checks := 0

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("TRAVEL_MENU_CHECK ", "PASS " if ok else "FAIL ", label)

func frames(count: int = 3) -> void:
	for index in range(count):
		focus_fixture()
		await get_tree().physics_frame
		focus_fixture()

func focus_fixture() -> void:
	# The Windows runner deliberately hides its GUI window. Native focus-out
	# can arrive after test startup; synthetic keyboard tests explicitly keep
	# their scene focused, without changing production focus-loss behaviour.
	var scene := get_tree().current_scene
	if scene != null: scene.set("focused", true)

func send_key(code: int, pressed: bool, echo: bool = false) -> void:
	focus_fixture()
	var event := InputEventKey.new()
	event.keycode = code; event.physical_keycode = code
	event.pressed = pressed; event.echo = echo
	Input.parse_input_event(event)
	Input.flush_buffered_events()

func key(code: int, echo: bool = false) -> void:
	send_key(code, true, echo)
	send_key(code, false)

func wheel(direction: int) -> void:
	var event := InputEventMouseButton.new()
	event.button_index = direction; event.pressed = true
	Input.parse_input_event(event)
	Input.flush_buffered_events()

func walk_until_prompt(code: int, visible: bool, maximum_frames: int = 90) -> void:
	send_key(code, true)
	for index in range(maximum_frames):
		await get_tree().physics_frame
		focus_fixture()
		if (Travel.menu_open if visible else not Travel.door_inside): break
	send_key(code, false)
	await frames()

func walk_out(code: int) -> void:
	send_key(code, true)
	for index in range(100):
		await get_tree().physics_frame
		focus_fixture()
		if not Travel.door_inside: break
	send_key(code, false)
	await frames()

func wait_for_arrival(expected_name: String) -> bool:
	var started := Time.get_ticks_msec()
	var deadline := started + 20000
	while Travel.busy and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	await frames()
	var arrived: bool = not Travel.busy and get_tree().current_scene.name == expected_name
	print("TRAVEL_MENU_ARRIVAL ", JSON.stringify({"expected":expected_name, "actual":str(get_tree().current_scene.name), "busy":Travel.busy, "elapsed_ms":Time.get_ticks_msec()-started}))
	check(arrived, "in-process arrival: " + expected_name)
	return arrived

func run() -> void:
	await frames(10)
	var bedroom = get_tree().current_scene
	bedroom.focused = true; bedroom.yaw = PI / 2
	bedroom.player.position = Vector3(1.85, .12, 1.85)
	bedroom.player.reset_physics_interpolation()
	var old_mode: int = bedroom.process_mode
	var old_clock_held: bool = CareerBridge.clock_held
	await frames(10)
	check(bedroom.target == "club", "bedroom door is physically reachable")
	check(Travel.menu_open and not Travel.busy, "walking to bedroom door automatically shows destinations without E")
	check(Travel.menu.destinations == ["club", "lan", "major", "awards"], "bedroom excludes current destination and includes new venues")
	check(bedroom.process_mode == old_mode and bedroom.player.enabled, "door prompt leaves scene and walking enabled")
	check(CareerBridge.clock_held == old_clock_held, "door prompt does not hold career clock")
	var old_connected: bool = CareerBridge.connected
	var clock_before: float = CareerBridge.clock_minutes
	CareerBridge.connected = true; CareerBridge.clock_held = false
	CareerBridge._process(.5)
	check(CareerBridge.clock_minutes > clock_before, "career clock advances beside visible door prompt")
	CareerBridge.connected = old_connected; CareerBridge.clock_held = old_clock_held
	var zoom: float = bedroom.zoom
	wheel(MOUSE_BUTTON_WHEEL_DOWN)
	check(Travel.menu.selected == 1, "wheel down selects next destination")
	wheel(MOUSE_BUTTON_WHEEL_UP)
	check(Travel.menu.selected == 0, "wheel up selects previous destination")
	check(is_equal_approx(bedroom.zoom, zoom), "door wheel does not also zoom world camera")
	key(KEY_DOWN); check(Travel.menu.selected == 0, "arrow movement is not repurposed as destination selection")
	key(KEY_UP); check(Travel.menu.selected == 0, "door prompt leaves arrow movement mapping intact")
	key(KEY_E, true)
	check(Travel.menu_open and not Travel.busy, "held E echo cannot confirm automatic prompt")
	var origin: Vector3 = bedroom.player.position
	await walk_until_prompt(KEY_W, false)
	print("TRAVEL_MENU_WALK ", JSON.stringify({"from":str(origin), "to":str(bedroom.player.position), "enabled":bedroom.player.enabled, "focused":bedroom.focused, "door_inside":Travel.door_inside, "menu_open":Travel.menu_open}))
	check(bedroom.player.position.distance_to(origin) > .4, "real W input walks away while door prompt is visible")
	check(not Travel.menu_open and not Travel.door_inside, "leaving bedroom door hides destinations")
	var distant_zoom: float = bedroom.zoom
	wheel(MOUSE_BUTTON_WHEEL_UP)
	check(bedroom.zoom < distant_zoom, "wheel resumes camera zoom away from door")
	await walk_until_prompt(KEY_S, true)
	check(Travel.menu_open, "walking back restores automatic destinations")
	key(KEY_ESCAPE)
	check(not Travel.menu_open and Travel.door_dismissed and not Travel.busy, "Escape hides prompt without travelling")
	await frames(8)
	check(not Travel.menu_open and bedroom.player.enabled, "Escape remains hidden during same visit without freezing player")
	key(KEY_E)
	check(not Travel.menu_open and not Travel.busy, "E does not reopen an Escape-dismissed visit")
	await walk_out(KEY_W)
	check(not Travel.door_inside and not Travel.door_dismissed, "walking out resets visit dismissal")
	await walk_until_prompt(KEY_S, true)
	check(Travel.menu_open, "re-entering after Escape restores choices")
	key(KEY_P)
	check(Phone.screen.visible and CareerBridge.phone_open and not Travel.menu_open, "P from door keeps phone input ownership")
	await frames()
	key(KEY_ESCAPE)
	check(not Phone.screen.visible and not Travel.busy, "phone Escape closes device without travelling")
	await frames()
	check(Travel.menu_open, "door choices resume after phone closes")
	Computer.present("bedroom")
	check(Computer.screen.visible and not Travel.menu_open, "computer hides door prompt without overlapping devices")
	await frames()
	key(KEY_E)
	check(not Computer.screen.visible and not Travel.busy, "computer E closes device without travel")
	await frames()
	check(Travel.menu_open, "door choices resume after seated computer restores approach")
	check(CareerBridge.clock_held == old_clock_held, "device and door visits preserve existing clock hold")
	key(KEY_ENTER)
	check(Travel.busy and not Travel.menu_open, "Enter confirms selected destination directly")
	if not await wait_for_arrival("PlayableChickenClub"): finish(); return
	var club = get_tree().current_scene
	club.focused = true
	club.player.position = Vector3(-.75, .23, 8.77)
	club.player.reset_physics_interpolation()
	await frames(10)
	var npc_count: int = club.life.roster.size()
	club.interactions.values["focus"] = 73
	check(Travel.menu_open and Travel.menu.destinations == ["bedroom", "lan", "major", "awards"], "club door automatically offers all other venues")
	var cooldown: float = club.interactions.cooldown_clock
	var club_zoom: float = club.camera_zoom
	await frames(10)
	check(club.interactions.cooldown_clock > cooldown, "local activity clock continues at door")
	check(club.player.enabled and not club.life.held, "club door does not hold character or NPC life")
	wheel(MOUSE_BUTTON_WHEEL_DOWN)
	wheel(MOUSE_BUTTON_WHEEL_DOWN)
	check(Travel.menu.destinations[Travel.menu.selected] == "major", "club wheel selects Major explicitly")
	check(is_equal_approx(club.camera_zoom, club_zoom), "club wheel selects without camera zoom")
	check(club.life.roster.size() == npc_count, "club NPC roster retained")
	key(KEY_E)
	check(Travel.busy, "E confirms arena from automatic prompt")
	if not await wait_for_arrival("MajorWalk"): finish(); return
	var arena = get_tree().current_scene
	arena.focused = true; arena.finish_intro()
	await frames()
	check(not arena.player.visual.visible, "arena keeps first person")
	check(arena.camera.projection == Camera3D.PROJECTION_PERSPECTIVE, "arena keeps perspective camera")
	check(Travel.menu_open and Travel.menu.destinations == ["bedroom", "club", "lan", "awards"], "arena exit automatically offers destinations")
	print("TRAVEL_MENU_POINTER ", JSON.stringify({"display_server":DisplayServer.get_name(), "actual":Input.mouse_mode, "paused":arena.paused}))
	check(Input.mouse_mode == Input.MOUSE_MODE_CAPTURED, "non-modal arena prompt keeps first person pointer captured")
	var yaw_before: float = arena.yaw
	var motion := InputEventMouseMotion.new(); motion.relative = Vector2(50, 30)
	Input.parse_input_event(motion); Input.flush_buffered_events()
	check(not is_equal_approx(arena.yaw, yaw_before), "first person camera can turn beside door prompt")
	var volume: float = arena.atmosphere.master_volume
	key(KEY_ESCAPE)
	check(not Travel.menu_open and not arena.paused, "arena Escape hides door prompt without opening pause menu")
	check(Input.mouse_mode == Input.MOUSE_MODE_CAPTURED, "arena Escape keeps first person pointer captured")
	await frames(5)
	check(not Travel.menu_open, "arena prompt stays hidden until physically leaving")
	var arena_origin: Vector3 = arena.player.position
	await walk_out(KEY_W)
	check(arena.player.position.distance_to(arena_origin) > 1.5 and not Travel.door_inside, "real first person walking leaves exit range")
	await walk_until_prompt(KEY_S, true)
	check(Travel.menu_open, "arena re-entry restores automatic choices")
	check(is_equal_approx(arena.atmosphere.master_volume, volume), "arena audio settings retained")
	wheel(MOUSE_BUTTON_WHEEL_DOWN)
	key(KEY_ENTER)
	check(Travel.busy and not Travel.menu_open, "arena Enter confirms return to club")
	if not await wait_for_arrival("PlayableChickenClub"): finish(); return
	club = get_tree().current_scene
	check(int(club.interactions.values["focus"]) == 73, "return keeps club session")
	check(club.life.roster.size() == npc_count, "return keeps NPC roster")
	check(not CareerBridge.phone_open and not Phone.screen.visible and not Computer.screen.visible, "travel leaves devices closed")
	check(not Travel.open_menu("bedroom"), "wrong current scene rejected")
	check(not Travel.open_menu("invalid"), "unknown destination rejected")
	finish()

func finish() -> void:
	var data := {"checks":checks, "failures":failures}
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://temp"))
	var report := FileAccess.open("res://temp/travel_menu_test_report.json", FileAccess.WRITE)
	report.store_string(JSON.stringify(data, "  "))
	print("TRAVEL_MENU_RESULT ", JSON.stringify(data))
	get_tree().quit(0 if failures.is_empty() else 1)
