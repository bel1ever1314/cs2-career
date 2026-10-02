extends Node
## play.tscn -- --no-service --club-input-test. Input events use production routing.
var failures: Array[String] = []
var checks := 0

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("CLUB_INPUT_CHECK ", "PASS " if ok else "FAIL ", label)

func frames(count: int = 3) -> void:
	for index in range(count): await get_tree().physics_frame

func key(code: int) -> void:
	for pressed in [true, false]:
		var event := InputEventKey.new()
		event.keycode = code; event.physical_keycode = code; event.pressed = pressed
		Input.parse_input_event(event); Input.flush_buffered_events()

func run(club) -> void:
	await frames(10)
	club.focused = true
	# Fix the fixture positions, retaining every actor and dialogue object.
	for actor in club.life.roster:
		actor.process_mode = Node.PROCESS_MODE_DISABLED; actor.collision_layer = 0
	club.life.enabled = false
	var npc = club.life.roster[0]
	club.player.position = Vector3(-2.65, .23, -6.55)
	club.player.reset_physics_interpolation()
	npc.position = club.player.position + Vector3(0, 0, .40)
	npc.reset_physics_interpolation()
	await frames()
	var computer: Dictionary = club.interactions.reachable("computer")
	check(not computer.is_empty(), "computer approach is physically reachable with nearby NPC")
	check(club.life.nearest_npc() == npc, "closer NPC remains talkable")
	if computer.is_empty(): finish(); return
	var anchor: Vector3 = club.interactions.vec(computer["anchor"])
	check(npc.position.distance_to(club.player.position) < Vector2(anchor.x-club.player.position.x, anchor.z-club.player.position.z).length(), "NPC fixture is closer than computer approach")
	var target: Dictionary = club.world_target()
	check(target.get("kind") == "object" and target.get("item", {}).get("id") == "computer", "reachable computer wins E target over closer NPC")
	check(club.prompt_label.text.contains("E 使用电脑") and club.prompt_label.text.contains("F 和"), "prompt shows separate computer E and conversation F")
	var approach: Vector3 = club.player.position
	key(KEY_E)
	check(club.interactions.active.get("id") == "computer" and club.life.speaker == null, "real E begins computer and does not start NPC conversation")
	check(club.player.seat_pose and club.player.locked, "computer approach retains seated animation")
	await frames(45)
	check(Computer.screen.visible and CareerBridge.phone_open, "computer desktop opens after seated approach")
	check(club.player.seat_pose and club.player.locked, "desktop keeps actor seated")
	key(KEY_E)
	check(not Computer.screen.visible and not CareerBridge.phone_open, "computer E closes device")
	check(not club.player.seat_pose and not club.player.locked, "closing computer releases seat and actor")
	check(club.player.position.distance_to(approach) < .15, "closing computer restores original approach")
	await frames()
	key(KEY_F)
	check(club.life.speaker == npc and npc.talking, "real F starts nearby NPC conversation separately")
	check(not Computer.screen.visible and club.interactions.active.is_empty(), "F conversation does not reopen computer")
	var first_line: String = club.life.line
	key(KEY_2)
	check(club.life.topic_selected == "聊聊最近的训练" and club.life.line != first_line, "existing numbered conversation choices still work")
	key(KEY_ESCAPE)
	check(club.life.speaker == null and not npc.talking and not club.player.locked, "Escape ends conversation without losing NPC")
	check(npc in club.life.roster, "interaction arbitration retains existing NPC object")
	finish()

func finish() -> void:
	var data := {"checks":checks, "failures":failures}
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://temp"))
	var report := FileAccess.open("res://temp/club_input_test_report.json", FileAccess.WRITE)
	report.store_string(JSON.stringify(data, "  "))
	print("CLUB_INPUT_RESULT ", JSON.stringify(data))
	get_tree().quit(0 if failures.is_empty() else 1)
