extends Node
const Images = preload("res://scripts/team_mark_image.gd")
const Editor = preload("res://scripts/team_mark_editor.gd")
const Startup = preload("res://scripts/career_startup.gd")
const UI = preload("res://scripts/computer_ui.gd")
var checks := 0
var failures: Array[String] = []
var commands: Array = []
var notice := ""

func _ready() -> void:
	call_deferred("run")

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("TEAM_MARK_STARTUP_CHECK ", "PASS " if ok else "FAIL ", label)

func _button(parent: Node, text: String, callback: Callable, _write: bool = false) -> Button:
	return UI.button(parent, text, callback)

func _device_command(path: String, body: Dictionary) -> void:
	commands.append({"path":path, "body":body})

func _rebuild() -> void:
	pass

func settle() -> void:
	for _i in range(5): await get_tree().process_frame

func capture(label: String, viewport: Viewport = null) -> void:
	if DisplayServer.get_name() == "headless": return
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture-dir="):
			var directory := arg.trim_prefix("--capture-dir=")
			DirAccess.make_dir_recursive_absolute(directory)
			await RenderingServer.frame_post_draw
			var target := viewport if viewport != null else get_viewport()
			check(target.get_texture().get_image().save_png(directory.path_join(label + ".png")) == OK, "capture " + label)

func run() -> void:
	if "--no-service" not in OS.get_cmdline_user_args(): get_tree().quit(2); return
	CareerBridge.set_process(false)
	CareerBridge.connected = false
	CareerBridge.connecting = true
	CareerBridge.context = {}
	var splash := Startup.new()
	add_child(splash)
	await settle()
	check(not splash.finished and splash.bar.visible and not splash.actions.visible, "startup shows live load state instead of engine logo")
	for dimensions in [Vector2i(1024, 720), Vector2i(1920, 1080)]:
		get_window().content_scale_size = dimensions
		get_window().size = dimensions
		await settle()
		check(Rect2(Vector2.ZERO, Vector2(dimensions)).encloses(splash.status.get_global_rect()), "startup fits " + str(dimensions))
		await capture("startup_" + str(dimensions.x))
	CareerBridge.connecting = false
	CareerBridge.message = "fixture: backend unavailable"
	await settle()
	check(splash.actions.visible and not splash.bar.visible and splash.status.text == CareerBridge.message, "startup failure remains readable with exit and fallback controls")
	CareerBridge.connected = true
	CareerBridge.context = {"calendar":{"revision":4}}
	await settle()
	check(splash.finished, "ready context dismisses startup without creating a save or simulating")
	await get_tree().create_timer(.3).timeout
	var source := Image.create(1024, 256, false, Image.FORMAT_RGBA8)
	source.fill(Color.TRANSPARENT)
	source.fill_rect(Rect2i(10, 10, 900, 200), Color("17191c"))
	var panel := Images.panel(source)
	var avatar := Images.avatar(source)
	check(panel.get_width() == 512 and panel.get_height() < 512, "panel preserves rectangular aspect and caps longest edge")
	check(avatar.get_size() == Vector2i(64, 64) and avatar.get_pixel(0, 0).to_html() == "202428b3", "CS2 uses square translucent graphite tile")
	check(avatar.save_png_to_buffer().size() < 16384, "generated avatar fits BotHider size limit")
	source.fill(Color.TRANSPARENT)
	check(Images.panel(source) == null and Images.avatar(source) == null, "fully transparent images rejected")
	var editor := Editor.new()
	editor.host = self
	var box := VBoxContainer.new()
	add_child(box)
	editor.render(box, {"marks":{"allowed":false}})
	check(box.get_child_count() == 0, "joined clubs do not expose a custom owner upload")
	editor.render(box, {"team":"Fixture Club", "team_id":"fixture", "marks":{"allowed":true}})
	check(box.find_child("UploadClubMark", true, false) != null and box.find_child("UploadCS2Mark", true, false) != null, "owner has separate panel and in-game upload actions")
	box.hide()
	var payload := {"team_id":"fixture", "kind":"club", "panel_png":Marshalls.raw_to_base64(panel.save_png_to_buffer()), "avatar_png":Marshalls.raw_to_base64(avatar.save_png_to_buffer())}
	editor.show_preview(panel, avatar, payload)
	await settle()
	check(commands.is_empty(), "preview does not save before confirmation")
	await capture("custom_mark_preview", editor.preview.get_viewport())
	(editor.preview.find_child("ConfirmTeamMark", true, false) as Button).pressed.emit()
	check(commands.size() == 1 and commands[0].path == "/api/3d/controls/team-logo" and commands[0].body.has("request_id"), "confirmation sends bounded images with team identity and request id")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture-dir="):
			var directory := arg.trim_prefix("--capture-dir=")
			panel.save_png(directory.path_join("generated_panel.png"))
			avatar.save_png(directory.path_join("generated_avatar.png"))
	await settle()
	print("TEAM_MARK_STARTUP_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
