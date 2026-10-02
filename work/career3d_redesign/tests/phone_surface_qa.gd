extends Node
## Disposable bridge/UI fixture. Screenshots/reports go only to a new D/E folder.
const TeamVisuals = preload("res://scripts/team_visuals.gd")
var checks := 0
var failures: Array[String] = []
var output := ""
var requests: Array = []

func _ready() -> void:
	call_deferred("run")

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("PHONE_SURFACE_CHECK ", "PASS " if value else "FAIL ", label)

func settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame

func fixture_library() -> Dictionary:
	return {"map":"de_dust2", "schema_version":1, "tactics":[], "available_maps":[{"map":"de_dust2", "name":"Dust II"}],
		"map_meta":{"pos_x":0, "pos_y":1000, "scale":1, "width":1000, "height":1000, "image_path":"res://tactics-radar.png", "layers":[]}}

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(2); return
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--output-dir="): output = arg.trim_prefix("--output-dir=")
	if not output.is_absolute_path() or output.left(3).to_upper() not in ["D:/", "E:/"] or DirAccess.dir_exists_absolute(output):
		push_error("Choose a fresh explicit D/E QA folder.")
		get_tree().quit(2)
		return
	DirAccess.make_dir_recursive_absolute(output)
	var original_clipboard := DisplayServer.clipboard_get() if DisplayServer.get_name() != "headless" else ""
	CareerBridge.context = {"date":"2026-10-02", "calendar":{"revision":1}, "player":{"id":"surface-qa", "name":"界面测试"}, "stories":[], "contacts":[], "inbox":[], "calendar_events":[], "start":{"can_continue":true}}
	CareerBridge.connected = true
	CareerBridge.clock_held = true
	Computer.set_process(false)
	Phone.set_process(false)
	if not ResourceLoader.exists("res://assets/cozy_room.glb"):
		check(false, "complete isolated bedroom asset is required for rendering QA")
		get_tree().quit(1)
		return
	var bedroom := (load("res://bedroom.tscn") as PackedScene).instantiate()
	add_child(bedroom)
	await settle()
	check(is_instance_valid(bedroom.player) and is_instance_valid(bedroom.camera), "actual bedroom and camera initialized")
	if bedroom.player == null or bedroom.camera == null: get_tree().quit(1); return
	check(get_window().content_scale_aspect == Window.CONTENT_SCALE_ASPECT_EXPAND, "project uses expand aspect for its 3D window")
	for dimensions in [Vector2i(1280, 720), Vector2i(1600, 900), Vector2i(1024, 768)]:
		get_window().size = dimensions
		await settle()
		var visible := get_viewport().get_visible_rect()
		var painted: Rect2 = get_viewport().get_final_transform() * visible
		var physical := Rect2(Vector2.ZERO, Vector2(get_window().size))
		check(painted.position.distance_to(physical.position) < 1 and painted.size.distance_to(physical.size) < 2, "viewport fills the complete %s window without letterbox offsets" % dimensions)
		print("PHONE_SURFACE_VIEW ", JSON.stringify({"physical":str(physical), "logical":str(visible), "painted":str(painted)}))
		if DisplayServer.get_name() != "headless":
			await RenderingServer.frame_post_draw
			var image := get_viewport().get_texture().get_image()
			var black_edges := 0
			for step in range(1, 20):
				var x := int(image.get_width() * step / 20.0)
				var y := int(image.get_height() * step / 20.0)
				for pixel in [image.get_pixel(x, 1), image.get_pixel(x, image.get_height() - 2), image.get_pixel(1, y), image.get_pixel(image.get_width() - 2, y)]:
					if maxf(pixel.r, maxf(pixel.g, pixel.b)) < 0.012: black_edges += 1
			check(black_edges < 38, "actual bedroom render has no full black frame at %s" % dimensions)
			check(image.save_png(output.path_join("bedroom-%dx%d.png" % [dimensions.x, dimensions.y])) == OK, "captures full 3D window at %s" % dimensions)
	Computer.present("club")
	var editor = Computer.tactics
	editor.command_sender = func(path: String, body: Dictionary) -> bool: requests.append({"path":path, "body":body}); return true
	editor.libraries = {"de_dust2":fixture_library()}
	Computer._navigate("tactics", false)
	await settle()
	editor.draft["id"] = "qa_local_copy"
	editor.refresh(true)
	var saved_draft := JSON.stringify(editor.draft)
	var sent_count: int = requests.size()
	for action in ["poll", "post", "pending_save"]:
		CareerBridge.busy = true
		CareerBridge.active_post = action != "poll"
		editor.pending_action = "save" if action == "pending_save" else ""
		Computer._busy_changed(true)
		check(not editor.controls.TacticsCopyCommand.disabled, "clipboard command remains available during " + action)
		editor.controls.TacticsCopyCommand.pressed.emit()
		check(editor.notice.begins_with("已复制 play 指令"), "copy button actually runs during " + action)
		if DisplayServer.get_name() != "headless": check(DisplayServer.clipboard_get() == "play qa_local_copy", "clipboard receives the exact command during " + action)
		check(JSON.stringify(editor.draft) == saved_draft and requests.size() == sent_count, "clipboard action preserves draft and sends no service command during " + action)
	CareerBridge.busy = false
	CareerBridge.active_post = false
	editor.pending_action = ""
	editor.draft["id"] = "INVALID ID"
	editor.refresh(true)
	check(editor.controls.TacticsCopyCommand.disabled, "copy is disabled for an invalid command ID")
	var logo_path := "E:/CS2CareerTools/Career3DMedia/teams/faze.svg"
	check(FileAccess.file_exists(logo_path), "real local FaZe logo is present")
	var manifest = JSON.parse_string(FileAccess.get_file_as_string("E:/CS2CareerTools/Career3DMedia/teams/team-media.json"))
	var real_logos: Dictionary = {}
	if manifest is Dictionary:
		for club in manifest.get("team_backgrounds", {}):
			real_logos[str(club)] = str(manifest.team_backgrounds[club].get("path", ""))
	check(real_logos.size() == 48, "pinned local manifest contains all 48 exact club mappings")
	CareerBridge.context["media"] = {"team_backgrounds":real_logos}
	for club in real_logos:
		var loaded_logo: Texture2D = TeamVisuals.texture(str(club))
		check(loaded_logo != null and loaded_logo.get_width() > 0, "Godot loads the sanitized real logo for " + str(club))
	for device in [Computer, Phone]:
		for page in ["team", "player"]:
			var info := {"name":"FaZe", "region":"EU", "rank":7, "players":[], "roster":[]} if page == "team" else {"name":"karrigan", "team":"FaZe", "role":"igl", "summary":{}, "records":[]}
			if device == Computer:
				Computer.page_details[page] = info
				Computer.detail = info
				Computer.open_app(page, "club")
			else:
				if page == "team": Phone.selected_team = info
				else: Phone.selected_player = info
				Phone.present(page)
			await settle()
			var marks: Array = device.content.find_children("TeamBrandBackground", "TextureRect", true, false)
			check(marks.size() == 1 and marks[0].texture != null and marks[0].texture.get_width() > 0, "%s %s header loads the real club logo texture" % [device.name, page])
			check(device.content.get_combined_minimum_size().x <= device.scroll.size.x + 1, "%s %s branded header stays within the device width" % [device.name, page])
			if DisplayServer.get_name() != "headless":
				await RenderingServer.frame_post_draw
				get_viewport().get_texture().get_image().save_png(output.path_join("%s-%s-logo.png" % [device.name, page]))
	if DisplayServer.get_name() != "headless": DisplayServer.clipboard_set(original_clipboard)
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "QA never starts a career service or reaches CS2")
	var report := {"ok":failures.is_empty(), "checks":checks, "failures":failures}
	var file := FileAccess.open(output.path_join("phone-surface-qa.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "  "))
	print("PHONE_SURFACE_RESULT ", JSON.stringify(report))
	get_tree().quit(0 if failures.is_empty() else 1)
