extends Node
## UI fixture and captured writes only; no career, native game, or tactical library is changed.
var failures: Array[String] = []
var checks := 0
var requests: Array = []

func _ready() -> void:
	call_deferred("run")

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("TACTICS_EDITOR_CHECK ", "PASS " if ok else "FAIL ", label)

func settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame

func capture(label: String) -> void:
	if "--capture" not in OS.get_cmdline_user_args() or DisplayServer.get_name() == "headless": return
	await settle()
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png("res://" + label + ".png")

func fixture_tactic(ident: String) -> Dictionary:
	var value := {"id":ident, "name":"战术 " + ident, "side":"t", "slots":[]}
	for number in range(1, 6): value.slots.append({"slot":number, "steps":[], "duty":"auto"})
	return value

func fixture_library(code: String = "de_dust2") -> Dictionary:
	return {"ok":true, "schema_version":1, "map":code, "tactics":[fixture_tactic("alpha"), fixture_tactic("beta")],
		"map_meta":{"pos_x":0, "pos_y":1000, "scale":1, "width":1000, "height":1000,
			"image_path":"res://tactics-radar.png", "layers":[{"id":"upper", "name":"上层", "image_path":"res://tactics-radar.png"}, {"id":"lower", "name":"下层", "image_path":"res://tactics-radar.png"}]}, "available_maps":[{"map":"de_dust2", "name":"Dust II"}, {"map":"de_nuke", "name":"Nuke"}]}

func mouse_button(point: Vector2, button_index: int, pressed: bool = true) -> InputEventMouseButton:
	var event := InputEventMouseButton.new()
	event.position = point
	event.button_index = button_index
	event.pressed = pressed
	return event

func run() -> void:
	get_viewport().size = Vector2i(1280, 720)
	if "--capture" in OS.get_cmdline_user_args():
		get_window().content_scale_size = Vector2i(1280, 720)
		get_window().size = Vector2i(1280, 720)
	CareerBridge.connected = true
	CareerBridge.clock_held = true
	CareerBridge.context = {"date":"2026-10-01", "calendar":{"revision":27}, "player":{"id":"fixture", "name":"测试"}, "inbox":[], "calendar_events":[]}
	var editor = Computer.tactics
	editor.command_sender = func(path: String, body: Dictionary) -> bool: requests.append({"path":path, "body":body}); return true
	editor.libraries = {"de_dust2":fixture_library(), "de_nuke":fixture_library("de_nuke")}
	Computer.present("club")
	Computer._navigate("tactics", false)
	await settle()
	check(editor.controls.TacticsId is LineEdit and editor.controls.TacticsId.max_length == 32, "chat-command ID is editable")
	check(editor.controls.TacticsDuty.is_visible_in_tree() and not editor.controls.TacticsDuty.disabled, "duties are editable under roster assignment")
	check(editor.controls.TacticsHumanSlot.disabled, "roster assignment fixes manual slot to one")
	check(Computer.content.get_combined_minimum_size().x <= Computer.scroll.size.x + 1, "detailed editor fits monitor width")
	var editor_id: int = editor.view.get_instance_id()
	var canvas_id: int = editor.canvas.get_instance_id()
	var hold_id: int = editor.controls.TacticsHold.get_instance_id()
	var name_input: LineEdit = editor.controls.TacticsName
	name_input.grab_focus()
	name_input.caret_column = 2
	editor.point_chosen([200, 800], false)
	editor.point_chosen([500, 500], false)
	editor.movement_changed("walk")
	editor.level_changed("lower")
	editor.wait_changed(2.3)
	editor.refresh(true)
	await capture("tactics-editor-1280-top")
	check(editor.steps()[1].movement == "walk" and editor.steps()[1].level == "lower" and is_equal_approx(editor.steps()[1].wait, 2.3), "run/walk, wait, and level apply to the selected step")
	check(editor.view.get_instance_id() == editor_id and editor.canvas.get_instance_id() == canvas_id and editor.controls.TacticsHold.get_instance_id() == hold_id, "editing retains editor canvas and input instances")
	check(name_input.caret_column == 2 and get_viewport().gui_get_focus_owner() == name_input, "editing a route retains text focus and caret")
	var draft_before: Dictionary = editor.draft.duplicate(true)
	editor.finished("/api/3d/tactics?map=de_dust2", fixture_library())
	check(editor.draft == draft_before and editor.view.get_instance_id() == editor_id and name_input.caret_column == 2, "library refresh retains unsaved draft and focused input")
	CareerBridge.context["money"] = 1234
	Computer._context_changed()
	check(editor.view.get_instance_id() == editor_id and get_viewport().gui_get_focus_owner() == name_input, "ordinary career polling retains tactics controls and text focus")
	var parsed_library = JSON.parse_string(JSON.stringify(fixture_library()))
	editor.finished("/api/3d/tactics?map=de_dust2", parsed_library)
	check(editor.export_value(true).tactics[0].slots[0].slot is int, "library export retains integer fields after parsing a service response")
	CareerBridge.busy = true
	CareerBridge.active_post = false
	Computer._busy_changed(true)
	check(editor.canvas.editable and editor.controls.TacticsName.editable, "read-only polling leaves local map and text editing available")
	CareerBridge.active_post = true
	Computer._busy_changed(true)
	check(not editor.canvas.editable and not editor.controls.TacticsName.editable, "write request locks map and text editing")
	CareerBridge.busy = false
	Computer._busy_changed(false)
	check(editor.canvas.editable and editor.controls.TacticsName.editable, "completing an unrelated write unlocks tactics controls without rebuilding")
	var map_canvas = editor.canvas
	if "--capture" in OS.get_cmdline_user_args():
		Computer.scroll.scroll_vertical = maxi(0, roundi((Computer.scroll.get_global_transform().affine_inverse() * map_canvas.global_position).y - 15))
		await settle()
		print("TACTICS_VIEW ", JSON.stringify({"window":str(get_window().size), "viewport":str(get_viewport().size), "canvas":str(map_canvas.get_global_rect()), "scroll":str(Computer.scroll.get_global_rect()), "offset":Computer.scroll.scroll_vertical}))
		await capture("tactics-editor-1280-map")
		var wheel_point: Vector2 = map_canvas.get_global_transform_with_canvas() * (map_canvas.size / 2)
		var hover := InputEventMouseMotion.new()
		hover.position = wheel_point
		hover.global_position = wheel_point
		Input.parse_input_event(hover)
		await settle()
		var scroll_before := Computer.scroll.scroll_vertical
		var wheel := mouse_button(wheel_point, MOUSE_BUTTON_WHEEL_UP)
		wheel.global_position = wheel_point
		Input.parse_input_event(wheel)
		await settle()
		check(is_equal_approx(map_canvas.zoom_factor, 1.25) and Computer.scroll.scroll_vertical == scroll_before, "wheel event over canvas zooms map without scrolling the page")
		await capture("tactics-editor-1280-zoom")
		map_canvas.fit_view()
	var anchor: Vector2 = map_canvas.size * Vector2(0.4, 0.6)
	var anchor_world: Array = map_canvas.canvas_to_world(anchor)
	map_canvas.zoom_at(2.0, anchor)
	var zoomed_world: Array = map_canvas.canvas_to_world(anchor)
	check(Vector2(anchor_world[0], anchor_world[1]).distance_to(Vector2(zoomed_world[0], zoomed_world[1])) < 0.01, "cursor-anchored zoom keeps the same world coordinate")
	map_canvas._gui_input(mouse_button(anchor, MOUSE_BUTTON_MIDDLE))
	var pan := InputEventMouseMotion.new()
	pan.position = anchor + Vector2(25, -14)
	pan.relative = Vector2(25, -14)
	pan.button_mask = MOUSE_BUTTON_MASK_MIDDLE
	map_canvas._gui_input(pan)
	map_canvas._gui_input(mouse_button(pan.position, MOUSE_BUTTON_MIDDLE, false))
	var world := [200.0, 800.0]
	var restored: Array = map_canvas.canvas_to_world(map_canvas.world_to_canvas(world))
	check(Vector2(world[0], world[1]).distance_to(Vector2(restored[0], restored[1])) < 0.01, "world projection roundtrip works at zoom and pan")
	check(editor.draft == draft_before, "zoom and pan never change route coordinates")
	var zoom_before: float = map_canvas.zoom_factor
	var pan_before: Vector2 = map_canvas.pan_offset
	editor.layer_changed("1")
	check(is_equal_approx(map_canvas.zoom_factor, 1.0) and map_canvas.pan_offset == Vector2.ZERO, "new radar layer starts fitted")
	editor.layer_changed("0")
	check(is_equal_approx(map_canvas.zoom_factor, zoom_before) and map_canvas.pan_offset == pan_before, "view is restored separately for each radar layer")
	map_canvas.fit_view()
	map_canvas.zoom_at(1.5, map_canvas.size / 2)
	var node_position: Vector2 = map_canvas.world_to_canvas(editor.steps()[0].position)
	map_canvas._gui_input(mouse_button(node_position, MOUSE_BUTTON_LEFT))
	check(editor.selected_step == 0 and editor.steps().size() == 2, "clicking a zoomed node selects without adding a point")
	var drag := InputEventMouseMotion.new()
	drag.position = node_position + Vector2(12, 8)
	drag.relative = Vector2(12, 8)
	drag.button_mask = MOUSE_BUTTON_MASK_LEFT
	var expected: Array = map_canvas.canvas_to_world(drag.position)
	map_canvas._gui_input(drag)
	map_canvas._gui_input(mouse_button(drag.position, MOUSE_BUTTON_LEFT, false))
	check(Vector2(editor.steps()[0].position[0], editor.steps()[0].position[1]).distance_to(Vector2(expected[0], expected[1])) < 0.01, "dragging a zoomed node writes inverse-projected world coordinates")
	editor.toggle_look()
	var look_point: Vector2 = map_canvas.size / 2
	map_canvas._gui_input(mouse_button(look_point, MOUSE_BUTTON_LEFT))
	check(editor.steps()[0].look_at != null and editor.edit_mode == "route", "look-mark mode writes a target and returns to route mode")
	editor.clear_look()
	check(editor.steps()[0].look_at == null, "look target can be cleared")
	editor.reorder_step(1)
	check(editor.selected_step == 1 and editor.steps()[1].position == expected, "reordering keeps the complete selected step together")
	editor.copy_route("2")
	check(editor.draft.slots[1].steps == editor.steps(), "copy route copies all step details")
	editor.steps()[0].wait = 7
	check(editor.draft.slots[1].steps[0].wait != 7, "copied routes are independent nested data")
	editor.copy_route("2")
	check(editor.confirmation_action.is_valid(), "copying over an existing route requires confirmation")
	editor.cancel_confirmation()
	editor.assignment_changed("ability")
	editor.human_changed("4")
	check(editor.draft.human_slot == 4 and not editor.controls.TacticsHumanSlot.disabled, "ability assignment permits selecting any manual slot")
	editor.assignment_changed("roster")
	check(editor.draft.human_slot == 1 and editor.controls.TacticsDuty.is_visible_in_tree(), "switching to roster retains duty controls and resets manual slot")
	var preserved: Dictionary = editor.draft.duplicate(true)
	editor.new_tactic()
	check(editor.confirmation_action.is_valid() and editor.draft == preserved, "new tactic waits for unsaved-change confirmation")
	editor.cancel_confirmation()
	editor.change_map("de_nuke")
	check(editor.confirmation_action.is_valid() and editor.map_code == "de_dust2", "map change waits for unsaved-change confirmation")
	editor.cancel_confirmation()
	editor.import_json(JSON.stringify({"map":"de_nuke", "tactic":fixture_tactic("incoming")}))
	check(requests.is_empty() and "地图" in editor.notice, "cross-map imports never send a mutation")
	editor.import_json(JSON.stringify({"schema_version":1, "map":"de_dust2", "tactics":[fixture_tactic("same"), fixture_tactic("same")]}))
	check(requests.is_empty() and "重复" in editor.notice, "duplicate IDs are rejected before mutation")
	check(editor.export_value().tactic == editor.draft and editor.export_value(true).tactics.size() == 2, "draft and library export use original map-specific package shapes")
	editor.draft.id = "alpha"
	editor.changed()
	editor.save_tactic()
	check(requests.is_empty() and editor.confirmation_action.is_valid(), "saving a new draft under an existing ID asks before overwrite")
	editor.confirm_pending()
	check(requests.size() == 1 and requests[0].path == "/api/3d/tactics/save" and requests[0].body.revision == 27 and requests[0].body.tactic.id == "alpha", "confirmed save uses service revision and existing pure-data body")
	check(not editor.controls.TacticsName.editable and not map_canvas.editable, "pending mutation locks editor against lost changes")
	editor.finished("/api/3d/tactics/save", {"ok":false, "reason":"fixture failure"})
	check(editor.dirty and editor.draft.id == "alpha" and editor.controls.TacticsName.editable, "failed save retains dirty draft and unlocks inputs")
	editor.set_draft(fixture_tactic("alpha"))
	editor.refresh(true)
	editor.delete_tactic()
	check(requests.size() == 1 and editor.confirmation_action.is_valid(), "delete requires explicit confirmation")
	editor.confirm_pending()
	check(requests.size() == 2 and requests[1].path == "/api/3d/tactics/delete" and requests[1].body.id == "alpha", "delete targets the loaded saved ID")
	editor.finished("/api/3d/tactics/delete", {"ok":true, "map":"de_dust2", "tactics":[fixture_tactic("beta")]})
	check(editor.original_id.is_empty() and not editor.library().get("map_meta", {}).is_empty(), "delete starts a clean draft and retains radar projection")
	editor.import_json(JSON.stringify({"map":"de_dust2", "tactic":fixture_tactic("incoming")}))
	check(requests.size() == 3 and requests[2].path == "/api/3d/tactics/import" and requests[2].body.value.tactic.id == "incoming", "JSON import forwards original package through service boundary")
	check(requests[2].body.value.tactic.slots[0].slot is int, "JSON import preserves engine-required integer slot fields")
	editor.finished("/api/3d/tactics/import", {"ok":true, "map":"de_dust2", "tactics":[fixture_tactic("beta"), fixture_tactic("incoming")]})
	check(editor.original_id == "incoming" and not editor.dirty and editor.view.get_instance_id() == editor_id, "successful import opens canonical tactic without rebuilding editor")
	for index in range(12): editor.point_chosen([100 + index * 15, 800], false)
	editor.point_chosen([500, 500], false)
	check(editor.steps().size() == 12 and "12" in editor.notice, "route remains bounded to twelve steps")
	editor.remove_step()
	check(editor.steps().size() == 11 and editor.selected_step == 10, "deleting a point preserves a valid selected step")
	if "--capture" in OS.get_cmdline_user_args():
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://tests-output"))
		editor.export_file("res://tests-output/tactics-export-draft.json")
		editor.export_file("res://tests-output/tactics-export-library.json", true)
	await capture("tactics-editor-restored")
	print("TACTICS_EDITOR_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
