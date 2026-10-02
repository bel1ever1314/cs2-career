extends SceneTree
## Isolated real UI/input routes. Never opens a Career service or CS2.
## Godot --headless --path <project> --script res://tests/input_ui_test.gd

var game
var checks := 0
var failures: Array[String] = []
var details: Dictionary = {}
var held_keys: Array[int] = []


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var scene := load("res://main.tscn") as PackedScene
	_check(scene != null, "main scene loads")
	if scene == null:
		_finish()
		return
	game = scene.instantiate()
	root.add_child(game)
	await process_frame
	await process_frame
	_check(game._ready_ok, "full UI resources are ready")
	if not game._ready_ok:
		await _cleanup()
		return
	game.set_process(false)
	var start: Button = game.main_menu.find_child("StartMatchButton", true, false)
	game.menu_mode.select(0)
	game.menu_team.select(0)
	game.menu_team.emit_signal("item_selected", 0)
	var chosen_id := str(game.rosters["t"][game.menu_player.selected]["id"])
	start.emit_signal("pressed")
	await process_frame
	await process_frame
	_check(not start.disabled and start.text == "开始对局", "asynchronous button route has completed")
	_check(game.mode == "play" and game.viewer_team == "t", "menu starts selected play mode and roster side")
	_check(game.sim.human_id == chosen_id, "menu starts the actually selected human")
	_check(game.state.get("human_team", "") == "t", "human ownership is bound to the selected roster team")
	_check(game.speed_button.disabled, "human play cannot accelerate simulation")
	_check(not game.audio.muted, "fresh playable match restores normal audio preference")
	game._process(0.35) # Let the real startup input lock elapse.
	await _test_human_input()
	await _test_focus_pause_scoreboard()
	await _test_menu_and_audio()
	await _test_selection_and_command()
	_test_visibility()
	_test_report()
	await _cleanup()


func _test_human_input() -> void:
	for key in [KEY_W, KEY_D, KEY_SHIFT, KEY_E]:
		_send_key(key, true)
	await process_frame
	var input: Dictionary = game._human_input()
	_check(Input.is_physical_key_pressed(KEY_W), "actual parsed physical W is held")
	_check(input.get("move", Vector2.ZERO) == Vector2(1, -1), "W+D route preserves two-axis movement for the engine to normalize")
	_check(input.get("walk", false), "Shift routes to walking input")
	_check(input.get("interact", false), "E routes to plant/defuse input")
	for key in [KEY_W, KEY_D, KEY_SHIFT, KEY_E]:
		_send_key(key, false)
	await process_frame
	input = game._human_input()
	_check(input.get("move", Vector2.INF) == Vector2.ZERO and not input.get("walk", true), "key releases stop movement/walking input")
	for key in [KEY_R, KEY_Q, KEY_G, KEY_1]:
		_send_key(key, true)
		_send_key(key, false)
	await process_frame
	input = game._human_input()
	_check(input.get("reload", false), "R routes a reload request")
	_check(input.get("smoke", false), "Q routes a smoke request")
	_check(input.get("flash", false), "G routes a flash request")
	_check(input.get("weapon", "") == "primary", "1 routes primary weapon selection")
	_send_key(KEY_2, true)
	_send_key(KEY_2, false)
	await process_frame
	_check(game._human_input().get("weapon", "") == "pistol", "2 routes pistol selection")
	game._process(1.0 / 60.0)
	input = game._human_input()
	_check(not input.get("reload", true) and not input.get("smoke", true)
		and not input.get("flash", true) and input.get("weapon", "missing") == "", "one-shot requests are consumed once")
	_send_key(KEY_R, true, true)
	_send_key(KEY_R, false)
	await process_frame
	_check(not game._reload_request, "keyboard echo does not create a second action")
	var own: Array = game.state["players"].filter(func(p): return p["team"] == "t")
	var teammate_button := game.own_rows[1]["name"] as Button
	_check(teammate_button != null, "roster teammate is a real Button")
	if teammate_button != null:
		teammate_button.emit_signal("pressed")
	_check(game.sim.human_id == own[1]["id"], "real roster button switches to an alive own teammate")
	_check(game._human_input().is_empty(), "human switch has a short input handoff guard")
	var opponent: Dictionary = game.state["players"].filter(func(p): return p["team"] == "ct")[0]
	game._select_actor(str(opponent["id"]))
	_check(game.sim.human_id == own[1]["id"], "attempted opponent selection cannot cross human ownership")
	game._process(0.25)


func _test_focus_pause_scoreboard() -> void:
	game.pause_button.grab_focus()
	await process_frame
	_check(root.gui_get_focus_owner() == game.pause_button, "GUI button really has focus during hotkey test")
	await _tap(KEY_TAB)
	_check(game.scoreboard.visible, "Tab opens scoreboard even with button focus")
	var before := int(game.sim.snapshot()["tick"])
	game._process(0.1)
	_check(int(game.sim.snapshot()["tick"]) == before, "scoreboard pauses the simulation clock")
	for key in [KEY_R, KEY_Q, KEY_G, KEY_1, KEY_2]:
		await _tap(key)
	_check(_requests_clear(), "scoreboard ignores instant combat/utility requests")
	await _tap(KEY_TAB)
	_check(not game.scoreboard.visible, "Tab closes scoreboard without focusing another widget")
	await _tap(KEY_SPACE)
	_check(game.paused and game.pause_button.text == "继续", "focused Space pauses exactly once")
	before = int(game.sim.snapshot()["tick"])
	game._process(0.1)
	_check(int(game.sim.snapshot()["tick"]) == before, "paused game does not advance clock")
	for key in [KEY_R, KEY_Q, KEY_G, KEY_2]:
		await _tap(key)
	_check(_requests_clear(), "paused UI does not queue stale actions for resume")
	await _tap(KEY_SPACE)
	_check(not game.paused and game.pause_button.text == "暂停", "focused Space resumes exactly once")
	game.pause_button.emit_signal("pressed")
	_check(game.paused, "pause Button signal routes to pause")
	game.pause_button.emit_signal("pressed")
	_check(not game.paused, "pause Button signal routes to resume")


func _test_menu_and_audio() -> void:
	await _tap(KEY_ESCAPE)
	_check(game.main_menu.visible and not game.match_view.visible, "Esc opens menu from the real match")
	_check(game.audio.muted, "menu immediately mutes gameplay voices")
	var before := int(game.sim.snapshot()["tick"])
	game._process(0.1)
	_check(int(game.sim.snapshot()["tick"]) == before, "menu does not run the hidden match")
	await _tap(KEY_Q)
	_check(_requests_clear(), "menu ignores gameplay action keys")
	game.resume_button.emit_signal("pressed")
	_check(game.match_view.visible and not game.main_menu.visible, "real resume Button returns to the existing match")
	_check(not game.audio.muted, "resume restores unmuted preference")
	game.audio_button.emit_signal("pressed")
	_check(game.audio.muted and game.audio_button.text == "静音", "sound Button controls the real cue Node")
	game.go_menu()
	game.resume_button.emit_signal("pressed")
	_check(game.audio.muted, "menu/resume preserves deliberate mute preference")
	game.audio_button.emit_signal("pressed")
	_check(not game.audio.muted, "sound Button restores audio")


func _test_selection_and_command() -> void:
	# Audio behavior has already been exercised. Keep subsequent instant
	# observer restarts silent rather than quitting inside a new round cue.
	if not game.audio.muted:
		game.audio_button.emit_signal("pressed")
	game.start_match("command", "ct", "")
	_check(game.sim.human_id == "" and game.mode == "command", "commander mode owns no human body")
	_check(not game.speed_button.disabled, "commander can use observer speed control")
	game.speed_button.emit_signal("pressed")
	_check(game.speed == 2.0, "speed Button cycles to 2x")
	game.speed_button.emit_signal("pressed")
	_check(game.speed == 4.0, "speed Button cycles to 4x")
	game.speed_button.emit_signal("pressed")
	_check(game.speed == 1.0, "speed Button returns to 1x")
	var own: Array = game.state["players"].filter(func(p): return p["team"] == "ct")
	var teammate_button := game.own_rows[2]["name"] as Button
	teammate_button.emit_signal("pressed")
	_check(game.selected_order_id == own[2]["id"], "commander roster Button selects an order recipient")
	_check(game.sim.human_id == "" and game._human_input().is_empty(), "commander selection does not turn into WASD takeover")
	game.order_buttons["hold"].emit_signal("pressed")
	var after: Dictionary = game.sim.snapshot()
	var selected: Dictionary = after["players"].filter(func(p): return p["id"] == game.selected_order_id)[0]
	_check(selected["task"] == "hold", "tactic Button changes the actual selected actor task")
	game.renderer._reframe()
	var target: Vector2 = own[2]["pos"]
	var screen_point: Vector2 = game.renderer.global_position + game.renderer.world_to_local(target)
	var window_point: Vector2 = root.get_screen_transform() * screen_point - Vector2(root.position)
	details["mouse_test"] = {"target": str(target), "screen": str(screen_point),
		"rect": str(game.renderer.get_global_rect()), "inside": game.renderer.get_global_rect().has_point(screen_point),
		"viewport": str(root.get_visible_rect()), "tree_mouse": str(game.renderer.get_global_mouse_position()),
		"window_size": str(root.size), "screen_transform": str(root.get_screen_transform()), "window_point": str(window_point)}
	var motion := InputEventMouseMotion.new()
	motion.position = window_point
	motion.global_position = window_point + Vector2(root.position)
	# Input.parse_input_event consumes physical window pixels, not stretched
	# canvas coordinates. The explicit screen transform also works headless.
	Input.parse_input_event(motion)
	await process_frame
	var button := InputEventMouseButton.new()
	button.button_index = MOUSE_BUTTON_RIGHT
	button.position = window_point
	button.global_position = window_point + Vector2(root.position)
	button.pressed = true
	Input.parse_input_event(button)
	await process_frame
	button = button.duplicate()
	button.pressed = false
	Input.parse_input_event(button)
	await process_frame
	details["mouse_test"]["tree_mouse_after"] = str(game.renderer.get_global_mouse_position())
	details["mouse_test"]["gui_hover"] = str(root.gui_get_hovered_control())
	_check(game.renderer.marker.is_finite(), "real right-click reaches the map GUI route")
	_check(game.renderer.marker.distance_to(target) < 0.01, "real right-click preserves the intended world position")
	after = game.sim.snapshot()
	selected = after["players"].filter(func(p): return p["id"] == game.selected_order_id)[0]
	_check(selected["order"] == "move", "map right-click commands the chosen actor")
	_check(game.sim.human_id == "", "right-click order never steals a commander human slot")
	details["mouse_route"] = "Input.parse_input_event(window pixels transformed from viewport)"


func _test_visibility() -> void:
	var actor := {"id": "fixture", "team": "t", "alive": true, "pos": Vector2(400, 400), "spotted_by": []}
	_check(not game.renderer._can_see(actor), "main map rejects an unseen opposing actor")
	actor["spotted_by"] = ["ct"]
	_check(game.renderer._can_see(actor), "main map accepts a team observation")
	actor["team"] = "ct"
	actor["spotted_by"] = []
	_check(game.renderer._can_see(actor), "own teammates remain visible")
	_check(game.minimap.team == "ct" and not game.minimap.spectator, "minimap inherits the commander observation mode")
	# Minimap has the same condition inline, not an independently callable API.
	var minimap_source := FileAccess.get_file_as_string("res://scripts/minimap.gd")
	_check(minimap_source.contains('not spectator and p.get("team", "") != team and team not in p.get("spotted_by", [])'), "minimap source gates enemy markers on the same observation")
	var hidden: Dictionary = game.state["players"].filter(func(p): return p["team"] == "t")[0]
	_check(str(game.enemy_rows[0]["detail"].text).contains("未发现"), "HUD hides unseen enemy weapon and health")
	game.renderer.visual_events.clear()
	game.renderer.push_event({"type": "shot", "id": hidden["id"], "from": hidden["pos"], "to": Vector2(0, 0)})
	_check(game.renderer.visual_events.is_empty(), "unseen enemy shot never becomes a tracer")
	game.renderer.push_event({"type": "kill", "victim_id": hidden["id"], "pos": hidden["pos"]})
	_check(game.renderer.visual_events.is_empty(), "hidden death event does not leak a map location")
	game.start_match("spectate", "t", "")
	_check(game.sim.human_id == "" and game.renderer.spectator and game.minimap.spectator, "spectator mode applies consistently to all maps")
	_check(game.renderer._can_see(actor), "spectator map deliberately shows both teams")


func _test_report() -> void:
	game.open_scoreboard()
	_check(game.scoreboard.visible and game.scoreboard_rows.size() == 10, "real scoreboard owns ten actual player rows")
	var report: Dictionary = game._serializable(game.sim.report())
	_check(not _contains_vector(report), "report recursively converts map vectors for JSON")
	var parsed = JSON.parse_string(JSON.stringify(report))
	_check(parsed is Dictionary and parsed.get("players", []).size() == 10, "actual report survives JSON round trip")
	_check(parsed.get("seed", -1) == game.seed_value and parsed.has("rules"), "report carries seed and round rules")
	details["report_written"] = false
	details["checks_kind"] = "real scene, parsed keyboard/mouse, real Button signals"


func _contains_vector(value) -> bool:
	if value is Vector2:
		return true
	if value is Dictionary:
		for key in value:
			if _contains_vector(value[key]): return true
	elif value is Array:
		for item in value:
			if _contains_vector(item): return true
	return false


func _requests_clear() -> bool:
	return not game._reload_request and not game._smoke_request and not game._flash_request and game._weapon_request == ""


func _send_key(code: int, pressed: bool, echo: bool = false) -> void:
	var event := InputEventKey.new()
	event.keycode = code
	event.physical_keycode = code
	event.pressed = pressed
	event.echo = echo
	Input.parse_input_event(event)
	if pressed and code not in held_keys:
		held_keys.append(code)
	elif not pressed:
		held_keys.erase(code)


func _tap(code: int) -> void:
	_send_key(code, true)
	await process_frame
	_send_key(code, false)
	await process_frame


func _cleanup() -> void:
	for key in held_keys.duplicate():
		_send_key(key, false)
	# Dummy audio still owns playback until its next mix callback. Stop the
	# final round cue and allow that callback before destroying the scene.
	game.audio.muted = true
	await create_timer(0.06).timeout
	game.queue_free()
	await process_frame
	await process_frame
	game = null
	call_deferred("_finish")


func _check(value: bool, label: String) -> void:
	checks += 1
	if not value:
		failures.append(label)
		push_error("INPUT UI ASSERT: " + label)


func _finish() -> void:
	print("TACTICAL2D_INPUT_UI " + JSON.stringify({"ok": failures.is_empty(), "checks": checks,
		"failures": failures, "details": details, "career_files_accessed": false, "cs2_started": false}))
	quit(0 if failures.is_empty() else 1)
