extends SceneTree
## Real device input around embedded RTS, using test-only bridge/no service.
var checks := 0
var failures: Array[String] = []

func _initialize() -> void: call_deferred("run")

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("RTS_MODAL_CHECK ", "PASS " if value else "FAIL ", label)

func settle() -> void:
	await process_frame
	await process_frame

func key(code: int, pressed: bool) -> void:
	var event := InputEventKey.new(); event.keycode=code; event.physical_keycode=code; event.pressed=pressed
	Input.parse_input_event(event)

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): quit(2); return
	var transport = root.get_node("CareerBridge")
	var computer = root.get_node("Computer")
	var phone = root.get_node("Phone")
	computer.set_process(false); phone.set_process(false)
	var roster: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://rts/data/rosters.json"))
	roster["team_names"]={"ct":"自定义 A 队","t":"自定义 B 队"}
	var a: Array = []; var b: Array = []; var pool := {}
	for side in ["ct","t"]:
		for card in roster[side]:
			pool[card.id]=card.duplicate(true)
			if side == "ct": a.append(card.id)
			else: b.append(card.id)
	var room := {"id":"rts-modal-isolated","mode":"custom","phase":"ready","map":"dust2","ct":"a","human_id":"","a":a,"b":b,"roster":pool}
	transport.fixture_reset({"player":{"id":"unchanged-career-id","name":"既有角色"},"custom":{"revision":31,"lobby":room,"rts_rosters":roster,"history":[],"maps":["dust2"]},"ladder":{"revision":31,"player":{"elo":1700}},"inbox":[]})
	var before: String = JSON.stringify(transport.context)
	computer.open_app("rts","club"); await settle()
	computer.rts_room.start_session(); await settle()
	var game = computer.rts_room.session
	check(is_instance_valid(game) and game.visible and computer.screen.visible and not phone.screen.visible and computer.get_child(-1) == game, "embedded RTS covers the registered visible computer as its topmost controls")
	if not is_instance_valid(game): quit(1); return
	game.set_process(false)
	check(game.mode == "command" and transport.phone_open, "embedded session keeps career device/actor lock")
	key(KEY_P,true); key(KEY_P,false); await settle()
	check(not phone.screen.visible and computer.screen.visible and is_instance_valid(computer.rts_room.session), "P inside embedded RTS never opens phone or closes its registered computer")
	if phone.screen.visible: phone.close_phone()
	check(transport.phone_open, "embedded session retains actor and clock lock after device hotkey")
	key(KEY_E,true); key(KEY_E,false); await settle()
	check(computer.screen.visible and is_instance_valid(computer.rts_room.session) and transport.phone_open, "E gameplay key cannot close the covered registered computer")
	if not is_instance_valid(game):
		print("RTS_MODAL_RESULT ",JSON.stringify({"checks":checks,"failures":failures}))
		quit(1)
		return
	game.open_scoreboard()
	check(game.score_title.text.contains("自定义 A 队") and game.score_title.text.contains("自定义 B 队"), "embedded scoreboard preserves custom A B names")
	key(KEY_ESCAPE,true); key(KEY_ESCAPE,false); await settle()
	check(is_instance_valid(computer.rts_room.session) and not game.scoreboard.visible and computer.screen.visible and transport.phone_open, "first Esc closes scoreboard without releasing active RTS device lock")
	key(KEY_ESCAPE,true); key(KEY_ESCAPE,false); await settle()
	check(computer.rts_room.session == null and computer.screen.visible and not phone.screen.visible, "return to computer releases only RTS session controls")
	check(transport.phone_open, "return to visible computer retains original device lock")
	check(JSON.stringify(transport.context) == before and transport.fixture_calls.is_empty(), "session control never mutates saved room career identity or Elo")
	computer.close_computer(); await settle()
	check(not transport.phone_open, "closing computer after RTS releases device lock normally")
	check(transport.endpoint.is_empty() and not transport.owns_service, "embedded boundaries remain isolated from service CS2 and save writer")
	print("RTS_MODAL_RESULT ",JSON.stringify({"checks":checks,"failures":failures}))
	quit(0 if failures.is_empty() else 1)
