extends Node
## Real club geometry and production E routing; isolated in a no-service project.
var checks := 0
var failures: Array[String] = []

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("CLUB_WORLD_HONOURS ", "PASS " if ok else "FAIL ", label)

func frames(count: int = 3) -> void:
	for index in range(count): await get_tree().physics_frame

func key(code: int) -> void:
	for pressed in [true, false]:
		var event := InputEventKey.new()
		event.physical_keycode = code; event.keycode = code; event.pressed = pressed
		Input.parse_input_event(event); Input.flush_buffered_events()

func capture(name_text: String) -> void:
	if not "--capture-club-honours" in OS.get_cmdline_user_args(): return
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://temp"))
	get_viewport().get_texture().get_image().save_png("res://temp/" + name_text + ".png")

func run(club) -> void:
	check("--no-service" in OS.get_cmdline_user_args(), "test uses no career service")
	CareerBridge.set_process(false)
	club.focused = true
	club.life.enabled = false
	for npc in club.life.roster: npc.set_physics_process(false); npc.collision_layer = 0
	var rows: Array = []
	for index in range(14):
		rows.append({"id":str(index), "event":"IEM Cologne Major 2026" if index == 0 else "Club Championship " + str(index),
			"short":"Cologne Major" if index == 0 else "Club Cup " + str(index), "year":2026 if index == 0 else 2025,
			"date":"2026-06-21" if index == 0 else "2025-06-01", "team":"Vitality", "historical":index != 0})
	CareerBridge.context = {"player":{"id":"human", "name":"Player"}, "team":{"name":"Vitality"},
		"date":"2026-07-21", "nextmatch":{"event":"Test Invitational", "date":"2026-07-21", "opponent":"Spirit",
			"attendance":{"display_name":"线下赛场", "instruction":"到门口选择「线下赛场」，前往选手席入座。"}},
		"club_trophies":{"team":"Vitality", "rows":rows, "personal_rows":[rows[0]]}, "feedback":{"items":[]}}
	club.trophy_display.refresh(CareerBridge.context)
	check(club.trophy_display.trophy_nodes.size() == 6 and "14 座" in club.trophy_display.title.text, "actual club cabinet shows six physical cups and fourteen-title total")
	club.player.position = Vector3(-1.13, .23, 3.85); club.player.reset_physics_interpolation()
	await frames()
	check(not club.interactions.reachable("reception").is_empty(), "real front-desk interaction is reachable")
	key(KEY_E)
	await frames()
	check(club.club_board.is_open() and club.club_board.page == "reception" and not Phone.screen.visible, "real E opens front-desk board instead of phone")
	check(not club.player.enabled and club.player.locked and club.life.held, "front-desk panel consistently holds player and nearby activities")
	await capture("club_front_desk")
	key(KEY_ESCAPE)
	await frames()
	check(not CareerBridge.phone_open and club.player.enabled and not club.player.locked, "Escape releases real world movement")
	club.player.position = Vector3(1.93, .23, 5.07); club.player.reset_physics_interpolation()
	await frames()
	check(not club.interactions.reachable("trophy").is_empty(), "real trophy cabinet is reachable")
	key(KEY_E)
	await frames()
	check(club.club_board.is_open() and club.club_board.page == "trophy" and not Phone.screen.visible, "real E opens championship list directly")
	await capture("club_championship_list")
	key(KEY_E)
	await frames()
	check(not club.club_board.is_open() and club.player.enabled and not club.player.locked, "E closes championship list without immediately reopening it")
	club.player.position = Vector3(1.93, .23, 6.35); club.player.reset_physics_interpolation()
	club.camera_zoom = 7; club.camera_yaw = .03; club.camera_pitch = .68
	club._camera_update(1.0, true)
	await frames()
	await capture("club_trophy_shelf")
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "real scene tests never launch backend or modify player's career")
	print("CLUB_WORLD_HONOURS_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
