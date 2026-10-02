extends SceneTree
## Independent input/mode boundaries; never runs or writes a Career/CS2 result.
var game
var checks := 0
var failures: Array[String] = []

func _initialize() -> void: call_deferred("run")

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("RTS_BOUNDARY_CHECK ", "PASS " if value else "FAIL ", label)

func settle() -> void:
	await process_frame
	await process_frame

func key(code: int, pressed: bool) -> void:
	var event := InputEventKey.new(); event.keycode = code; event.physical_keycode = code; event.pressed = pressed
	Input.parse_input_event(event)

func pointer(point: Vector2, button: int = 0, pressed: bool = false, additive: bool = false) -> void:
	var pixel := root.get_screen_transform() * point - Vector2(root.position)
	var event: InputEventMouse
	if button == 0:
		event = InputEventMouseMotion.new()
	else:
		event = InputEventMouseButton.new()
		event.button_index = button
		event.pressed = pressed
	event.position = pixel
	event.global_position = pixel + Vector2(root.position)
	event.shift_pressed = additive
	Input.parse_input_event(event)
	await process_frame

func map_point(world: Vector2) -> Vector2:
	game.renderer._reframe()
	return game.renderer.global_position + game.renderer.world_to_local(world)

func mouse_selection() -> void:
	# Two teammates deliberately overlap their 15px click radii. A click must
	# resolve one nearest actor; only an actual drag may select the pair.
	var own: Array = game.state.players.filter(func(p): return p.team == "t")
	for i in own.size(): own[i].pos = Vector2(700 + i * 25,700)
	own[0].pos = Vector2(500,500); own[1].pos = Vector2(520,500); own[2].pos = Vector2(620,550)
	game.renderer.rendered.clear()
	game.renderer.update_state(game.state,"command","t","")
	game._select_units([])
	var click := map_point(own[0].pos)
	await pointer(click)
	await pointer(click,MOUSE_BUTTON_LEFT,true)
	check(game.renderer.box_selecting, "real left press starts renderer selection gesture")
	await pointer(click,MOUSE_BUTTON_LEFT,false)
	check(game.selected_ids == [own[0].id], "nearby teammate click selects only the nearest single actor")
	var begin := map_point(Vector2(480,480)); var end := map_point(Vector2(540,520))
	await pointer(begin)
	await pointer(begin,MOUSE_BUTTON_LEFT,true)
	await pointer(end)
	await pointer(end,MOUSE_BUTTON_LEFT,false)
	check(game.selected_ids.size() == 2 and own[0].id in game.selected_ids and own[1].id in game.selected_ids, "actual dragged rectangle selects both own actors")
	click = map_point(own[2].pos)
	key(KEY_SHIFT,true); await process_frame
	await pointer(click,0,false,true)
	await pointer(click,MOUSE_BUTTON_LEFT,true,true)
	await pointer(click,MOUSE_BUTTON_LEFT,false,true)
	key(KEY_SHIFT,false); await process_frame
	check(game.selected_ids.size() == 3 and own[2].id in game.selected_ids, "actual Shift click adds a teammate without clearing selected group")
	click = map_point(own[0].pos)
	await pointer(click)
	await pointer(click,MOUSE_BUTTON_MIDDLE,true)
	check(game.renderer.dragging, "real middle press starts map drag")
	key(KEY_TAB,true); key(KEY_TAB,false); await settle()
	check(game.scoreboard.visible and not game.renderer.dragging and not game.renderer.box_selecting, "Tab opening scoreboard cancels in-flight map pointer gestures")
	await pointer(click,MOUSE_BUTTON_MIDDLE,false)
	game._close_scoreboard()
	await pointer(click,MOUSE_BUTTON_LEFT,true)
	check(game.renderer.box_selecting, "new selection can start after scoreboard closes")
	key(KEY_ESCAPE,true); key(KEY_ESCAPE,false); await settle()
	check(game.main_menu.visible and not game.renderer.box_selecting and not game.renderer.dragging, "Esc menu cancels in-flight selection before mouse release is swallowed")
	await pointer(click,MOUSE_BUTTON_LEFT,false)
	game._resume_match(); await settle()
	await pointer(click,MOUSE_BUTTON_MIDDLE,true)
	game.renderer.reset_camera("command")
	check(not game.renderer.dragging and not game.renderer.box_selecting, "camera reset releases stale map gesture ownership")
	await pointer(click,MOUSE_BUTTON_MIDDLE,false)

func signature() -> String:
	var result: Array = []
	for p in game.sim._players: result.append([p.id, p.goal, p.task, p.path.duplicate(), p.get("queued_goals", []).duplicate()])
	return JSON.stringify(result)

func start(mode: String = "command") -> void:
	game.start_match(mode, "t", "")
	game.set_process(false)
	game.renderer.set_process(false)
	await settle()

func run() -> void:
	root.content_scale_size = Vector2i(1280,720); root.size = Vector2i(1280,720)
	game = load("res://main.tscn").instantiate(); root.add_child(game)
	await settle()
	game.set_process(false)
	check(game._ready_ok, "standalone RTS resources initialize")
	await start()
	await mouse_selection()
	await start()
	var ids: Array = [game.rosters.t[0].id, game.rosters.t[1].id]
	game._select_units(ids)
	game.issue_order("hold")
	check(game.sim._players[game.sim._ids[ids[0]]].task == "hold" and game.sim._players[game.sim._ids[ids[1]]].task == "hold", "group tactical order reaches both chosen actors")
	var unchosen: String = str(game.rosters.t[2].id)
	check(game.sim._players[game.sim._ids[unchosen]].task != "hold", "group order leaves unselected ally task intact")
	var first: Dictionary = game.sim._players[game.sim._ids[ids[0]]]
	var target: Vector2 = game.sim._nav.nearest_walkable(first.pos + Vector2(0,-28),3.5)
	game._select_units([ids[0]])
	game._map_move(target)
	var active_goal: Vector2 = first.goal
	key(KEY_SHIFT,true); await process_frame
	check(Input.is_physical_key_pressed(KEY_SHIFT), "native Shift state is held for actual map command")
	game._map_move(game.sim._nav.nearest_walkable(first.pos + Vector2(0,-48),3.5))
	key(KEY_SHIFT,false); await process_frame
	check(first.goal == active_goal and first.get("queued_goals",[]).size() == 1, "UI Shift map command appends without replacing active movement")
	game.issue_order("hold")
	check(first.path.is_empty() and first.get("queued_goals",[]).is_empty(), "group hold releases path and queued movement")
	game.sim._round = 12; game.sim._begin_round()
	game.state = game.sim.snapshot(true); game._refresh()
	check(game.viewer_team == "t" and game.state.team_sides.t == "ct" and game.team_heading.text.contains("CT"), "half-time swaps CT/T side but keeps roster command ownership")
	game._select_units(ids); game.issue_order("hold")
	check(game.sim._players[game.sim._ids[ids[0]]].team == "t" and game.sim._players[game.sim._ids[ids[0]]].side == "ct" and game.sim._players[game.sim._ids[ids[0]]].task == "hold", "post-swap group order still controls original selected teammates")
	var prior_selection: Array = game.selected_ids.duplicate()
	game._select_units([game.rosters.ct[0].id],true)
	check(game.selected_ids == prior_selection, "half-time never makes opposing original roster selectable")
	await start("spectate")
	var before := signature()
	game.issue_order("hold")
	check(signature() == before, "spectator tactical buttons cannot alter bot orders")
	before = signature()
	var spectator: Dictionary = game.sim._players[game.sim._ids[str(game.rosters.t[0].id)]]
	game._map_move(game.sim._nav.nearest_walkable(spectator.pos + Vector2(0,-28),3.5))
	check(signature() == before, "spectator map right-click cannot change team movement")
	await start()
	game.open_scoreboard()
	before = signature()
	key(KEY_V,true); key(KEY_V,false); await settle()
	check(signature() == before, "scoreboard tactical hotkeys do not queue hidden team orders")
	game._close_scoreboard()
	game.rosters["team_names"] = {"t":"测试 A 队", "ct":"测试 B 队"}
	game.open_scoreboard()
	check(game.score_title.text.contains("测试 A 队") and game.score_title.text.contains("测试 B 队"), "scoreboard title follows supplied roster team names")
	check(Rect2(Vector2.ZERO,root.get_visible_rect().size).encloses(game.renderer.get_global_rect()), "1280x720 map stays within viewport")
	check(Rect2(Vector2.ZERO,root.get_visible_rect().size).encloses(game.pause_button.get_global_rect()), "1280x720 pause remains reachable")
	game._close_scoreboard(); await start("play")
	game._input_lock = 0
	key(KEY_W,true); await process_frame
	check(game._human_input().get("move",Vector2.ZERO).y == -1, "existing playable mode still accepts WASD")
	key(KEY_W,false); await process_frame
	check(game._human_input().get("move",Vector2.INF) == Vector2.ZERO, "released playable movement stops immediately")
	var human := str(game.sim.human_id)
	var ally := str(game.rosters.t[1].id)
	game._select_actor(ally)
	check(game.sim.human_id == ally and not game.sim._players[game.sim._ids[human]].human, "playable control switch releases previous actor back to AI")
	game._reload_request = true; game._smoke_request = true; game._flash_request = true; game._weapon_request = "pistol"
	game.open_scoreboard()
	check(not game._reload_request and not game._smoke_request and not game._flash_request and game._weapon_request.is_empty(), "scoreboard entry releases one-shot combat requests")
	game.audio.muted = true; game.queue_free(); await settle()
	print("RTS_BOUNDARY_RESULT ",JSON.stringify({"checks":checks,"failures":failures}))
	quit(0 if failures.is_empty() else 1)
