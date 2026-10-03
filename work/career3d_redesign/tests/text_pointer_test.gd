extends Node
## Real GUI routing with an in-memory career projection; no backend or saved career.
const UI = preload("res://scripts/computer_ui.gd")
const Major = preload("res://scripts/major_walk.gd")
const Chicken = preload("res://scripts/chicken_player.gd")
var checks := 0
var failures: Array[String] = []
var last_mouse := Vector2.ZERO

func _ready() -> void:
	if not "--no-service" in OS.get_cmdline_user_args() or not "--test" in OS.get_cmdline_user_args():
		push_error("Text pointer regression requires --test --no-service.")
		get_tree().quit(1)
		return
	call_deferred("run")

func check(value: bool, message: String) -> void:
	checks += 1
	if not value: failures.append(message)
	print("TEXT_POINTER_CHECK ", "PASS " if value else "FAIL ", message)

func settle() -> void:
	for _frame in range(3): await get_tree().process_frame

func move_mouse(point: Vector2, mask: int = 0) -> void:
	var event := InputEventMouseMotion.new()
	event.position = point
	event.global_position = point
	event.relative = point - last_mouse
	event.button_mask = mask
	Input.parse_input_event(event)
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
	await settle()

func click(field: Control) -> void:
	var point := field.get_global_rect().get_center()
	await move_mouse(point)
	await mouse_button(point, true)
	await mouse_button(point, false)

func key(code: Key, unicode: int = 0, control: bool = false) -> void:
	for pressed in [true, false]:
		var event := InputEventKey.new()
		event.keycode = code
		event.physical_keycode = code
		event.unicode = unicode if pressed else 0
		event.ctrl_pressed = control
		event.pressed = pressed
		Input.parse_input_event(event)
		await settle()

func pointer(field: LineEdit, description: String) -> void:
	check(field.mouse_default_cursor_shape == Control.CURSOR_ARROW, description + " uses a stable arrow instead of the platform I-beam")
	check(field.get_cursor_shape(field.size / 2) == Control.CURSOR_ARROW, description + " actually resolves an arrow in its text area")

func ensure_field_visible(scroll: ScrollContainer, field: Control) -> void:
	scroll.ensure_control_visible(field)
	await settle()

func settings_fields(surface: Control, description: String) -> void:
	for name in ["steam_exe", "csgo_path", "mod_source_path", "skins_source_path", "steam_id"]:
		var field := surface.find_child("DeviceSetting_" + name, true, false) as LineEdit
		check(field != null, description + " renders " + name)
		if field != null: pointer(field, description + " " + name)

func late_intro_ownership() -> void:
	# Never enter the tree: this isolates pointer ownership without loading an
	# arena, roster, audio or a real player session.
	var arena := Major.new()
	arena.player = Chicken.new()
	arena.add_child(arena.player)
	arena.pause_panel = PanelContainer.new()
	arena.add_child(arena.pause_panel)
	arena.testing = false
	arena.capturing = false
	arena.focused = true
	CareerBridge.phone_open = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	arena.finish_intro()
	check(Input.mouse_mode == Input.MOUSE_MODE_VISIBLE, "late arena intro cannot recapture the pointer from an open device")
	arena.paused = true
	arena.set_paused(false)
	check(Input.mouse_mode == Input.MOUSE_MODE_VISIBLE, "resuming arena movement cannot recapture the pointer from an open device")
	CareerBridge.phone_open = false
	arena.finish_intro()
	if DisplayServer.get_name() == "headless":
		print("TEXT_POINTER_SKIP headless display cannot report a native captured pointer; first-person capture must also be checked with a windowed test")
	else:
		check(Input.mouse_mode == Input.MOUSE_MODE_CAPTURED, "an arena intro without a device still enables first-person mouse look")
	arena.free()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func run() -> void:
	get_window().content_scale_size = Vector2i(1280, 890)
	get_window().size = Vector2i(1280, 890)
	if DisplayServer.get_name() != "headless": await get_tree().create_timer(0.15).timeout
	CareerBridge.connected = true
	CareerBridge.clock_held = true
	CareerBridge.busy = false
	CareerBridge.active_post = false
	CareerBridge.context = {"date":"2026-10-03", "calendar":{"revision":1}, "player":{"id":"pointer_fixture", "name":"Pointer fixture"}, "start":{"creation_required":false}, "inbox":[], "calendar_events":[], "settings":{"steam_exe":"D:/Steam/steam.exe", "csgo_path":"D:/Steam/game/csgo", "mod_source_path":"D:/BotImprover", "skins_source_path":"", "difficulty":"Medium", "real_skins":false, "steam_id":"", "setup":{"available":false}, "config":{"ready":true, "path_errors":[], "component_errors":[]}}}
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "test starts without a service or saved career")
	var native := LineEdit.new()
	check(native.mouse_default_cursor_shape == Control.CURSOR_IBEAM, "native text inputs would otherwise switch to the system I-beam")
	native.free()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	var form := VBoxContainer.new()
	form.position = Vector2(40, 40)
	form.size = Vector2(650, 240)
	add_child(form)
	var editable := LineEdit.new()
	editable.text = "Original"
	UI.line_edit(editable)
	form.add_child(editable)
	var readonly := LineEdit.new()
	readonly.text = "Read only"
	readonly.editable = false
	UI.line_edit(readonly)
	form.add_child(readonly)
	var secret := LineEdit.new()
	secret.secret = true
	secret.text = "password"
	UI.line_edit(secret)
	form.add_child(secret)
	var spin := SpinBox.new()
	spin.min_value = 0
	spin.max_value = 90
	spin.value = 15
	UI.line_edit(spin.get_line_edit())
	form.add_child(spin)
	await settle()
	pointer(editable, "editable field")
	pointer(readonly, "read-only field")
	pointer(secret, "password field")
	pointer(spin.get_line_edit(), "SpinBox internal text field")
	await click(editable)
	check(editable.has_focus(), "real mouse click still focuses editable text")
	check(Input.mouse_mode == Input.MOUSE_MODE_VISIBLE, "hover and focus never hide or capture the mouse")
	await key(KEY_A, 0, true)
	check(editable.get_selected_text() == "Original", "keyboard selection remains functional")
	await key(KEY_Z, 122)
	check(editable.text == "z", "typing replaces the real selection")
	check(editable.get_theme_color("caret_color") == UI.GREEN, "text insertion caret remains distinct from the mouse pointer")
	await click(readonly)
	await key(KEY_A, 0, true)
	await key(KEY_Z, 122)
	check(readonly.text == "Read only" and not readonly.editable, "pointer styling cannot unlock a read-only field")
	await click(secret)
	await key(KEY_A, 0, true)
	await key(KEY_Z, 122)
	check(secret.text == "z" and secret.secret, "password editing remains functional and masked")
	await click(spin.get_line_edit())
	await key(KEY_A, 0, true)
	await key(KEY_3, 51)
	await key(KEY_7, 55)
	await key(KEY_ENTER)
	check(is_equal_approx(spin.value, 37), "SpinBox still commits a typed numeric value")
	form.queue_free()
	await settle()
	Computer.device_settings.query_sender = func(_path: String): return true
	Computer.open_app("settings", "bedroom")
	await settle()
	settings_fields(Computer.content, "computer settings")
	check(Computer.screen.visible and not Phone.screen.visible and CareerBridge.phone_open and Input.mouse_mode == Input.MOUSE_MODE_VISIBLE, "computer modal owns input and releases the first-person mouse")
	var computer_field := Computer.content.find_child("DeviceSetting_steam_exe", true, false) as LineEdit
	if computer_field != null:
		await ensure_field_visible(Computer.scroll, computer_field)
		await click(computer_field)
		check(computer_field.has_focus() and Input.mouse_mode == Input.MOUSE_MODE_VISIBLE, "actual computer settings accept a visible-pointer focus click")
	Phone.present("settings")
	await settle()
	settings_fields(Phone.content, "phone settings")
	check(Phone.screen.visible and not Computer.screen.visible and CareerBridge.phone_open and Input.mouse_mode == Input.MOUSE_MODE_VISIBLE, "computer-to-phone handoff keeps one visible-pointer modal")
	var phone_field := Phone.content.find_child("DeviceSetting_steam_exe", true, false) as LineEdit
	if phone_field != null:
		await ensure_field_visible(Phone.scroll, phone_field)
		await click(phone_field)
		check(phone_field.has_focus() and Input.mouse_mode == Input.MOUSE_MODE_VISIBLE, "actual phone settings accept a visible-pointer focus click")
	Phone.close_phone()
	await settle()
	check(not Phone.screen.visible and not Computer.screen.visible and not CareerBridge.phone_open, "closing the last device releases its input ownership")
	late_intro_ownership()
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service and CareerBridge.active_path.is_empty() and CareerBridge.queued_command.is_empty(), "all input checks leave backend, CS2 and saved careers untouched")
	print("TEXT_POINTER_RESULT ", JSON.stringify({"checks":checks, "failures":failures, "display_server":DisplayServer.get_name()}))
	get_tree().quit(0 if failures.is_empty() else 1)
