extends SceneTree
## Actual club lifecycle and input regression, without HTTP or saved careers.
## --script res://tests/dialogue_ui_test.gd -- --no-service [--capture-dialogue]
var checks := 0
var failures: Array[String] = []
var club
var bridge
var locale
var initial_language := ""
var recorded_choices: Array[String] = []

func _initialize() -> void: call_deferred("run")

func check(ok: bool, caption: String) -> void:
	checks += 1
	if not ok: failures.append(caption)
	print("DIALOGUE_UI ","PASS " if ok else "FAIL ",caption)

func frames(count: int = 3) -> void:
	for index in range(count): await physics_frame

func key(code: int) -> void:
	for pressed in [true,false]:
		var event := InputEventKey.new()
		event.keycode = code; event.physical_keycode = code; event.pressed = pressed
		Input.parse_input_event(event); Input.flush_buffered_events()

func click(control: Control) -> void:
	var point := control.get_global_rect().get_center()
	var motion := InputEventMouseMotion.new(); motion.position = point; motion.global_position = point
	Input.parse_input_event(motion); Input.flush_buffered_events()
	await process_frame
	for pressed in [true,false]:
		var event := InputEventMouseButton.new(); event.position = point; event.global_position = point
		event.button_index = MOUSE_BUTTON_LEFT; event.pressed = pressed; event.button_mask = MOUSE_BUTTON_MASK_LEFT if pressed else 0
		Input.parse_input_event(event); Input.flush_buffered_events()
		await process_frame

func language(value: String) -> void:
	locale.language = value
	TranslationServer.set_locale("en" if value=="en" else "zh_CN")
	locale.changed.emit()

func capture(name_value: String) -> void:
	if not "--capture-dialogue" in OS.get_cmdline_user_args(): return
	check(ProjectSettings.globalize_path("res://").begins_with("E:/"),"render stays on isolated E drive")
	await create_timer(.22).timeout
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://temp"))
	check(root.get_texture().get_image().save_png("res://temp/"+name_value+".png")==OK,"saved "+name_value)

func fixture(roster_id: String = "dialogue-player-1") -> Dictionary:
	return {"player":{"id":"dialogue-you","name":"Tester"},"team":{"id":"dialogue-team","name":"Test Club","roster":[
		{"id":"dialogue-you","name":"Tester","role":"rifle","you":true},
		{"id":roster_id,"name":"Aster","role":"igl"},
		{"id":"dialogue-player-2","name":"Birch","role":"awp"},
		{"id":"dialogue-player-3","name":"Cedar","role":"entry"},
		{"id":"dialogue-player-4","name":"Dawn","role":"lurker"}]},
		"environment":{"club":{"tier":"standard","facilities":{"training":2,"meeting":2,"kitchen":2,"lounge":2}}}}

func position_fixture(npc) -> void:
	club.player.test_mode = true; club.player.test_direction = Vector3.ZERO
	club.player.position = Vector3(-.75,.23,6.1); club.player.reset_physics_interpolation()
	npc.position = Vector3(-.75,.23,5.1); npc.reset_physics_interpolation()

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args():
		push_error("Dialogue QA requires --no-service"); quit(1); return
	bridge = root.get_node("CareerBridge"); bridge.set_process(false)
	locale = root.get_node("Locale"); initial_language = locale.language
	root.content_scale_size = Vector2i(1440,1000); root.size = Vector2i(1440,1000)
	language("zh-CN")
	bridge.context = fixture()
	change_scene_to_file("res://play.tscn"); await scene_changed; await frames(8)
	club = current_scene
	check(club.life.roster.size()==8,"actual career roster retains four teammates and four staff")
	club.focused = true; club.life.enabled = false
	for actor in club.life.roster:
		actor.process_mode = Node.PROCESS_MODE_DISABLED; actor.collision_layer = 0
	var npc
	for actor in club.life.roster:
		if actor.npc_id=="dialogue-player-1": npc = actor
	check(npc!=null,"fixture teammate bound to actual actor")
	if npc==null: finish(); return
	position_fixture(npc); await frames()
	var original_state: String = npc.state
	var original_action: String = npc.action
	var original_yaw: float = npc.visual.rotation.y
	club.life.conversation_choice.connect(func(_id,topic): recorded_choices.append(topic))
	key(KEY_F); await frames()
	check(club.life.speaker==npc and npc.talking,"F opens nearest actual NPC")
	check(club.player.locked and club.dialogue.panel.visible,"dialogue holds actor and shows panel")
	check(club.dialogue.heading.size.x>55 and club.dialogue.activity.size.y<40,"name and role remain a compact horizontal heading")
	check(club.dialogue.buttons[3].get_global_rect().end.y<=root.get_visible_rect().end.y,"all conversation choices stay on screen")
	check(club.dialogue.text.visible_characters>=0,"new line begins typewriter reveal")
	var first_line: String = club.life.line
	key(KEY_2)
	check(club.dialogue.text.visible_characters==-1 and recorded_choices.is_empty(),"first number key reveals only")
	check(club.life.line==first_line,"reveal leaves selected content unchanged")
	key(KEY_2)
	check(recorded_choices==["training"] and club.life.topic_selected=="聊聊最近的训练","second number key selects training")
	check(club.dialogue.text.visible_characters==0,"choice restarts typewriter")
	await click(club.dialogue.text)
	check(club.dialogue.text.visible_characters==-1 and recorded_choices.size()==1,"text click reveals without choosing")
	await frames()
	await click(club.dialogue.buttons[0])
	check(recorded_choices==["training","busy"],"actual mouse button selects revealed choice")
	await click(club.dialogue.buttons[2])
	check(club.dialogue.text.visible_characters==-1 and recorded_choices.size()==2,"first choice click reveals only")
	await click(club.dialogue.buttons[2])
	check(recorded_choices==["training","busy","encourage"] and npc.bond==1,"second choice click encourages and updates local familiarity")
	club.dialogue.reveal(); await capture("club-dialogue-zh")
	var current_line: String = club.life.line
	language("en"); await frames(); club.dialogue.reveal()
	check(club.dialogue.text.text==locale.text(current_line) and club.dialogue.text.text!=current_line,"open dialogue translates on language change")
	check(club.dialogue.relation.text.contains("Familiarity"),"English familiarity and controls caption")
	await capture("club-dialogue-en")
	key(KEY_ESCAPE); await frames()
	check(club.life.speaker==null and not npc.talking and not club.dialogue.panel.visible,"Escape closes complete dialogue")
	check(not club.player.locked and npc.state==original_state and npc.action==original_action,"close restores player and NPC activity")
	check(is_equal_approx(npc.visual.rotation.y,original_yaw),"close restores NPC facing")
	check(npc in club.life.roster,"close retains original actor")
	key(KEY_F); await frames(); key(KEY_4); await frames()
	check(club.life.speaker==null and not club.player.locked,"4 exits even while typewriter is active")
	key(KEY_F); await frames(); key(KEY_SPACE)
	check(club.dialogue.text.visible_characters==-1,"Space reveals current speech")
	club.before_phone(); await frames()
	check(club.life.speaker==null and not npc.talking and not club.dialogue.panel.visible,"device opening safely cancels dialogue")
	key(KEY_F); await frames()
	bridge.context = fixture("dialogue-replacement"); bridge.changed.emit(); await frames()
	check(club.life.speaker==null and not club.dialogue.panel.visible and not club.player.locked,"career roster replacement closes old speaker")
	check(not is_instance_valid(npc) or (npc.npc_id=="dialogue-replacement" and npc.bond==0),"replaced identity releases old relationship state")
	finish()

func finish() -> void:
	language(initial_language)
	print("DIALOGUE_UI_RESULT ",JSON.stringify({"checks":checks,"failures":failures}))
	quit(0 if failures.is_empty() else 1)
