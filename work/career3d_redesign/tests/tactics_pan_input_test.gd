extends Node
## Real viewport input routing, including transformed parent coordinates and release capture.
var failures: Array[String] = []
var checks := 0
var last_mouse := Vector2.ZERO

func _ready() -> void:
	call_deferred("run")

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("TACTICS_PAN_INPUT_CHECK ", "PASS " if ok else "FAIL ", label)

func settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame

func send_button(point: Vector2, index: int, pressed: bool, mask: int = 0) -> void:
	var event := InputEventMouseButton.new()
	event.position = point
	event.global_position = point
	event.button_index = index
	event.button_mask = mask
	event.pressed = pressed
	Input.parse_input_event(event)
	last_mouse = point
	await settle()

func move_mouse(point: Vector2, mask: int = 0) -> void:
	var event := InputEventMouseMotion.new()
	event.position = point
	event.global_position = point
	event.relative = point - last_mouse
	event.button_mask = mask
	Input.parse_input_event(event)
	last_mouse = point
	await settle()

func send_space(pressed: bool) -> void:
	var event := InputEventKey.new()
	event.keycode = KEY_SPACE
	event.physical_keycode = KEY_SPACE
	event.pressed = pressed
	Input.parse_input_event(event)
	await settle()

func click(button: Button) -> void:
	var point := button.get_global_rect().get_center()
	await move_mouse(point)
	await send_button(point, MOUSE_BUTTON_LEFT, true, MOUSE_BUTTON_MASK_LEFT)
	await send_button(point, MOUSE_BUTTON_LEFT, false)

func run() -> void:
	get_window().content_scale_size = Vector2i(1280, 720)
	get_window().size = Vector2i(1280, 720)
	if DisplayServer.get_name() != "headless": await get_tree().create_timer(0.15).timeout
	CareerBridge.connected = true
	CareerBridge.clock_held = true
	CareerBridge.context = {"date":"2026-10-01", "calendar":{"revision":5}, "player":{"id":"fixture", "name":"平移测试"}, "inbox":[], "calendar_events":[]}
	var editor = Computer.tactics
	var value := {"id":"pan_fixture", "name":"平移测试", "side":"t", "slots":[]}
	for number in range(1, 6): value.slots.append({"slot":number, "steps":[]})
	value.slots[0].steps.append({"position":[500, 500], "level":"auto", "wait":0, "movement":"run", "look_at":null})
	editor.libraries = {"de_dust2":{"ok":true, "schema_version":1, "map":"de_dust2", "tactics":[value],
		"map_meta":{"pos_x":0, "pos_y":1000, "scale":1, "width":1000, "height":1000, "image_path":"res://tactics-radar.png"}}}
	editor.set_draft(value)
	Computer.present("club")
	Computer._navigate("tactics", false)
	await settle()
	var canvas = editor.canvas
	Computer.scroll.scroll_vertical = maxi(0, roundi((Computer.scroll.get_global_transform().affine_inverse() * editor.controls.tool_row.global_position).y - 5))
	await settle()
	check(editor.controls.TacticsEditTool.is_visible_in_tree() and editor.controls.TacticsPanTool.is_visible_in_tree(), "explicit edit and pan tools are visible beside the map")
	await click(editor.controls.TacticsPanTool)
	check(editor.map_tool == "pan" and canvas.tool_mode == "pan" and "按住左键" in editor.controls.tool_status.text, "clicking pan tool shows unambiguous left-drag state")
	canvas.zoom_at(2.0, canvas.size / 2)
	Computer.panel.scale = Vector2(0.75, 0.75)
	await settle()
	var route_before: Dictionary = editor.draft.duplicate(true)
	var pan_before: Vector2 = canvas.pan_offset
	var center: Vector2 = canvas.get_global_transform_with_canvas() * (canvas.size / 2)
	await move_mouse(center)
	await send_button(center, MOUSE_BUTTON_LEFT, true, MOUSE_BUTTON_MASK_LEFT)
	check(canvas.panning and canvas.pan_button == MOUSE_BUTTON_LEFT, "left press starts pan rather than selecting a route node")
	editor.refresh(true)
	check(canvas.panning, "same-view editor refresh preserves an active pan")
	var end := center + Vector2(30, -15)
	await move_mouse(end, MOUSE_BUTTON_MASK_LEFT)
	check(canvas.pan_offset.distance_to(pan_before + Vector2(40, -20)) < 0.02, "real input converts displacement through the 0.75 parent scale once")
	await send_button(end, MOUSE_BUTTON_LEFT, false)
	check(not canvas.panning and canvas.mouse_default_cursor_shape == Control.CURSOR_MOVE, "left release ends pan and restores its idle cursor")
	await send_button(end, MOUSE_BUTTON_RIGHT, true, MOUSE_BUTTON_MASK_RIGHT)
	await send_button(end, MOUSE_BUTTON_RIGHT, false)
	check(editor.draft == route_before and not editor.dirty, "pan mode left drag and right click never alter position or look data")
	CareerBridge.busy = true
	CareerBridge.active_post = true
	editor.refresh()
	check(not editor.controls.TacticsPanTool.disabled and not editor.controls.TacticsEditTool.disabled and not editor.controls.TacticsZoomIn.disabled and not canvas.editable, "view tools remain available during a write while route editing stays locked")
	await click(editor.controls.TacticsZoomIn)
	await click(editor.controls.TacticsEditTool)
	await click(editor.controls.TacticsPanTool)
	center = canvas.get_global_transform_with_canvas() * (canvas.size / 2)
	pan_before = canvas.pan_offset
	await move_mouse(center)
	await send_button(center, MOUSE_BUTTON_LEFT, true, MOUSE_BUTTON_MASK_LEFT)
	await move_mouse(center + Vector2(9, 6), MOUSE_BUTTON_MASK_LEFT)
	await send_button(center + Vector2(9, 6), MOUSE_BUTTON_LEFT, false)
	check(canvas.pan_offset.distance_to(pan_before + Vector2(12, 8)) < 0.02 and editor.draft == route_before and not editor.dirty, "zoom and real pan during a write change only the view")
	CareerBridge.busy = false
	editor.refresh()
	var world := [500.0, 500.0]
	var projected: Array = canvas.canvas_to_world(canvas.world_to_canvas(world))
	check(Vector2(projected[0], projected[1]).distance_to(Vector2(500, 500)) < 0.02, "coordinate roundtrip survives zoom and real transformed pan")
	if "--capture" in OS.get_cmdline_user_args() and DisplayServer.get_name() != "headless":
		Computer.panel.scale = Vector2.ONE
		await settle()
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://tactics-pan-tool-1280.png")
		Computer.panel.scale = Vector2(0.75, 0.75)
		await settle()
	center = canvas.get_global_transform_with_canvas() * (canvas.size / 2)
	await move_mouse(center)
	await send_button(center, MOUSE_BUTTON_LEFT, true, MOUSE_BUTTON_MASK_LEFT)
	var outside: Vector2 = canvas.get_global_transform_with_canvas() * Vector2(canvas.size.x + 40, canvas.size.y / 2)
	await move_mouse(outside, MOUSE_BUTTON_MASK_LEFT)
	await send_button(outside, MOUSE_BUTTON_LEFT, false)
	var released_offset: Vector2 = canvas.pan_offset
	await move_mouse(outside + Vector2(15, 10))
	check(not canvas.panning and canvas.pan_offset == released_offset, "release outside the canvas cannot leave a stuck pan")
	canvas.fit_view()
	await click(editor.controls.TacticsEditTool)
	check(editor.map_tool == "edit" and "右键设置观察方向" in editor.controls.tool_status.text, "edit tool restores clear point and look instructions")
	center = canvas.get_global_transform_with_canvas() * (canvas.size / 2)
	await move_mouse(center)
	check(Input.mouse_mode == Input.MOUSE_MODE_VISIBLE and canvas.mouse_default_cursor_shape == Control.CURSOR_ARROW, "editing keeps the visible system arrow instead of a theme-dependent cross cursor")
	check(canvas.placement_pointer_visible() and canvas.pointer_position.distance_to(canvas.size / 2) < 0.02, "a high-contrast placement pointer tracks the transformed local click coordinate")
	var pointer_outside: Vector2 = canvas.get_global_transform_with_canvas() * Vector2(canvas.size.x + 30, canvas.size.y / 2)
	await move_mouse(pointer_outside)
	check(not canvas.placement_pointer_visible(), "leaving the map removes its placement pointer")
	await move_mouse(center)
	canvas.set_editable(false)
	check(not canvas.placement_pointer_visible(), "a save lock hides the placement pointer without hiding the mouse")
	canvas.set_editable(true)
	check(canvas.placement_pointer_visible(), "unlocking restores placement feedback")
	canvas.clear_pointer()
	check(not canvas.placement_pointer_visible(), "window focus loss can clear stale placement feedback")
	await move_mouse(center)
	await send_button(center, MOUSE_BUTTON_MIDDLE, true, MOUSE_BUTTON_MASK_MIDDLE)
	await send_button(center, MOUSE_BUTTON_LEFT, true, MOUSE_BUTTON_MASK_LEFT | MOUSE_BUTTON_MASK_MIDDLE)
	await send_button(center, MOUSE_BUTTON_LEFT, false, MOUSE_BUTTON_MASK_MIDDLE)
	check(canvas.panning and canvas.pan_button == MOUSE_BUTTON_MIDDLE, "another button's release cannot cancel middle-button pan")
	pan_before = canvas.pan_offset
	await move_mouse(center + Vector2(15, 9), MOUSE_BUTTON_MASK_MIDDLE)
	await send_button(center + Vector2(15, 9), MOUSE_BUTTON_MIDDLE, false)
	check(canvas.pan_offset.distance_to(pan_before + Vector2(20, 12)) < 0.02 and editor.draft == route_before, "middle-button shortcut pans in edit mode without adding route points")
	canvas.fit_view()
	center = canvas.get_global_transform_with_canvas() * (canvas.size / 2)
	await move_mouse(center)
	await send_space(true)
	await send_button(center, MOUSE_BUTTON_LEFT, true, MOUSE_BUTTON_MASK_LEFT)
	await send_space(false)
	await move_mouse(center + Vector2(-15, 9), MOUSE_BUTTON_MASK_LEFT)
	await send_button(center + Vector2(-15, 9), MOUSE_BUTTON_LEFT, false)
	check(canvas.pan_offset.distance_to(Vector2(-20, 12)) < 0.02 and editor.draft == route_before, "Space-left shortcut finishes correctly when Space is released before the mouse")
	canvas.fit_view()
	canvas.zoom_at(1.5, canvas.size / 2)
	var node_point: Vector2 = canvas.get_global_transform_with_canvas() * canvas.world_to_canvas(editor.steps()[0].position)
	await move_mouse(node_point)
	await send_button(node_point, MOUSE_BUTTON_LEFT, true, MOUSE_BUTTON_MASK_LEFT)
	check(canvas.drag_slot == 1 and canvas.drag_step == 0, "real edit-mode press selects the node for dragging")
	editor.refresh(true)
	var drag_end := node_point + Vector2(15, 9)
	var expected: Array = canvas.canvas_to_world(canvas.get_global_transform_with_canvas().affine_inverse() * drag_end)
	await move_mouse(drag_end, MOUSE_BUTTON_MASK_LEFT)
	var moved: Array = editor.steps()[0].position
	check(Vector2(moved[0], moved[1]).distance_to(Vector2(expected[0], expected[1])) < 0.02 and editor.steps().size() == 1, "route dragging survives the synchronous selection and editor refresh")
	await send_button(drag_end, MOUSE_BUTTON_LEFT, false)
	node_point = canvas.get_global_transform_with_canvas() * canvas.world_to_canvas(editor.steps()[0].position)
	await move_mouse(node_point)
	await send_button(node_point, MOUSE_BUTTON_LEFT, true, MOUSE_BUTTON_MASK_LEFT)
	CareerBridge.busy = true
	CareerBridge.active_post = true
	editor.refresh()
	check(canvas.drag_slot == -1, "a write lock cancels a pending node drag immediately")
	CareerBridge.busy = false
	editor.refresh()
	var frozen: Array = editor.steps()[0].position.duplicate()
	await move_mouse(node_point + Vector2(15, 9), MOUSE_BUTTON_MASK_LEFT)
	await send_button(node_point + Vector2(15, 9), MOUSE_BUTTON_LEFT, false)
	check(editor.steps()[0].position == frozen, "unlocking does not revive an old node drag")
	check(editor.canvas.get_instance_id() == canvas.get_instance_id(), "all tool changes and gestures retain the same canvas")
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "input checks avoid network and career writes")
	print("TACTICS_PAN_INPUT_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
