extends Control
## Official overview projection only; the same canvas survives selection and dragging.
signal point_chosen(world: Array, look: bool)
signal node_selected(slot: int, step: int)
signal node_moved(slot: int, step: int, world: Array)
signal view_changed(zoom: float)
var metadata: Dictionary = {}
var slots: Array = []
var selected_slot := 1
var selected_step := -1
var texture: Texture2D
var editable := true
var look_mode := false
var drag_slot := -1
var drag_step := -1
var zoom_factor := 1.0
var pan_offset := Vector2.ZERO
var panning := false
var tool_mode := "edit"
var pan_button := 0
var pan_last_position := Vector2.ZERO
var space_down := false
var pointer_inside := false
var pointer_position := Vector2.ZERO
var view_states: Dictionary = {}
var view_key := ""
const COLORS := [Color("2c7854"), Color("537ab0"), Color("b08339"), Color("985e97"), Color("ac6259")]

func _ready() -> void:
	update_cursor()
	resized.connect(queue_redraw)
	focus_mode = Control.FOCUS_ALL
	clip_contents = true
	get_window().focus_exited.connect(stop_gesture)
	get_window().focus_exited.connect(clear_pointer)
	mouse_entered.connect(track_pointer)
	mouse_exited.connect(clear_pointer)

func set_tool_mode(value: String) -> void:
	# Refreshing selection or polling must not terminate an unchanged gesture.
	if value == tool_mode: return
	tool_mode = value
	stop_gesture()

func set_editable(value: bool) -> void:
	editable = value
	if not editable: stop_drag()
	queue_redraw()

func update_cursor() -> void:
	# Keep a recognizable system arrow. The placement reticle below is drawn
	# against the map itself, independent of Windows cursor themes.
	mouse_default_cursor_shape = Control.CURSOR_DRAG if panning or drag_slot >= 1 else (Control.CURSOR_MOVE if tool_mode == "pan" else Control.CURSOR_ARROW)
	queue_redraw()

func track_pointer() -> void:
	pointer_inside = true
	pointer_position = get_local_mouse_position()
	queue_redraw()

func clear_pointer() -> void:
	pointer_inside = false
	queue_redraw()

func placement_pointer_visible() -> bool:
	return pointer_inside and editable and tool_mode == "edit" and not panning and image_rect().has_point(pointer_position)

func start_pan(event: InputEventMouseButton) -> void:
	panning = true
	pan_button = event.button_index
	pan_last_position = event.position
	stop_drag()
	grab_focus()
	accept_event()

func stop_pan() -> void:
	panning = false
	pan_button = 0
	update_cursor()

func stop_gesture() -> void:
	stop_pan()
	stop_drag()
	space_down = false

func _notification(what: int) -> void:
	if what == NOTIFICATION_VISIBILITY_CHANGED and is_inside_tree() and not is_visible_in_tree():
		stop_gesture()
		clear_pointer()

func use_view(key: String) -> void:
	if key == view_key: return
	remember_view()
	view_key = key
	var saved: Dictionary = view_states.get(key, {})
	zoom_factor = float(saved.get("zoom", 1.0))
	pan_offset = saved.get("pan", Vector2.ZERO)
	stop_gesture()
	view_changed.emit(zoom_factor)
	queue_redraw()

func remember_view() -> void:
	if not view_key.is_empty(): view_states[view_key] = {"zoom":zoom_factor, "pan":pan_offset}

func zoom_at(multiplier: float, anchor: Vector2) -> void:
	var before := image_rect()
	if before.size.x <= 0 or before.size.y <= 0: return
	var uv := (anchor - before.position) / before.size
	zoom_factor = clampf(zoom_factor * multiplier, 0.75, 8.0)
	var after := image_rect()
	pan_offset += anchor - (after.position + uv * after.size)
	remember_view()
	view_changed.emit(zoom_factor)
	queue_redraw()

func zoom_in() -> void:
	zoom_at(1.25, size / 2.0)

func zoom_out() -> void:
	zoom_at(0.8, size / 2.0)

func fit_view() -> void:
	zoom_factor = 1.0
	pan_offset = Vector2.ZERO
	remember_view()
	view_changed.emit(zoom_factor)
	queue_redraw()

func image_rect() -> Rect2:
	var width := maxf(1.0, float(metadata.get("width", 1024)))
	var height := maxf(1.0, float(metadata.get("height", 1024)))
	var fit := minf(size.x / width, size.y / height)
	var drawn := Vector2(width, height) * fit * zoom_factor
	return Rect2((size - drawn) / 2.0 + pan_offset, drawn)

func world_to_canvas(world: Array) -> Vector2:
	var rect := image_rect()
	var scale := maxf(0.001, float(metadata.get("scale", 4.4)))
	var x := (float(world[0]) - float(metadata.get("pos_x", -2476))) / scale
	var y := (float(metadata.get("pos_y", 3239)) - float(world[1])) / scale
	return rect.position + Vector2(x / float(metadata.get("width", 1024)), y / float(metadata.get("height", 1024))) * rect.size

func canvas_to_world(point: Vector2) -> Array:
	var rect := image_rect()
	if rect.size.x <= 0 or rect.size.y <= 0: return [0, 0]
	var uv := (point - rect.position) / rect.size
	uv = uv.clamp(Vector2.ZERO, Vector2.ONE)
	var scale := float(metadata.get("scale", 4.4))
	return [float(metadata.get("pos_x", -2476)) + uv.x * float(metadata.get("width", 1024)) * scale, float(metadata.get("pos_y", 3239)) - uv.y * float(metadata.get("height", 1024)) * scale]

func ordered_slots() -> Array:
	var ordered := slots.duplicate()
	ordered.sort_custom(func(a, b): return int(a.get("slot", 1)) != selected_slot and int(b.get("slot", 1)) == selected_slot)
	return ordered

func hit_node(point: Vector2) -> Vector2i:
	var closest := Vector2i(-1, -1)
	var distance := 13.0
	for row in ordered_slots():
		var route: Array = row.get("steps", [])
		for index in range(route.size()):
			var measured := point.distance_to(world_to_canvas(route[index].get("position", [0, 0])))
			if measured <= distance:
				distance = measured
				closest = Vector2i(int(row.get("slot", 1)), index)
	return closest

func stop_drag() -> void:
	drag_slot = -1
	drag_step = -1
	update_cursor()

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		pointer_inside = Rect2(Vector2.ZERO, size).has_point(event.position)
		pointer_position = event.position
		queue_redraw()
	# View operations never change world coordinates and stay available while saving.
	if event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
		zoom_at(1.25 if event.button_index == MOUSE_BUTTON_WHEEL_UP else 0.8, event.position)
		accept_event()
		return
	if event is InputEventMouseButton and panning:
		# Additional buttons cannot steal or end the gesture's initiating button.
		if not event.pressed and event.button_index == pan_button: stop_pan()
		accept_event()
		return
	if event is InputEventKey and (event.keycode == KEY_SPACE or event.physical_keycode == KEY_SPACE):
		space_down = event.pressed
		accept_event()
		return
	if event is InputEventMouseButton and event.pressed and (event.button_index == MOUSE_BUTTON_MIDDLE or (event.button_index == MOUSE_BUTTON_LEFT and (tool_mode == "pan" or space_down or Input.is_physical_key_pressed(KEY_SPACE) or Input.is_key_pressed(KEY_SPACE)))):
		start_pan(event)
		return
	if event is InputEventMouseMotion and panning:
		var mask := MOUSE_BUTTON_MASK_MIDDLE if pan_button == MOUSE_BUTTON_MIDDLE else MOUSE_BUTTON_MASK_LEFT
		if not event.button_mask & mask:
			stop_pan()
			return
		# GUI position has already been transformed into this canvas's local space.
		pan_offset += event.position - pan_last_position
		pan_last_position = event.position
		remember_view()
		queue_redraw()
		accept_event()
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode in [KEY_PLUS, KEY_EQUAL, KEY_KP_ADD]: zoom_in(); accept_event(); return
		if event.keycode in [KEY_MINUS, KEY_KP_SUBTRACT]: zoom_out(); accept_event(); return
		if event.keycode in [KEY_0, KEY_KP_0]: fit_view(); accept_event(); return
	if tool_mode == "pan":
		if event is InputEventMouseButton: accept_event()
		return
	if not editable: stop_drag(); return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and not event.pressed:
		stop_drag()
		accept_event()
		return
	if event is InputEventMouseMotion and drag_slot >= 1:
		if not event.button_mask & MOUSE_BUTTON_MASK_LEFT: stop_drag(); return
		node_moved.emit(drag_slot, drag_step, canvas_to_world(event.position))
		queue_redraw()
		accept_event()
		return
	if not event is InputEventMouseButton or not event.pressed or event.button_index not in [MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT] or not image_rect().has_point(event.position): return
	grab_focus()
	if event.button_index == MOUSE_BUTTON_RIGHT or look_mode: point_chosen.emit(canvas_to_world(event.position), true)
	else:
		var hit := hit_node(event.position)
		if hit.x >= 1:
			drag_slot = hit.x
			drag_step = hit.y
			node_selected.emit(hit.x, hit.y)
			update_cursor()
		else: point_chosen.emit(canvas_to_world(event.position), false)
	queue_redraw()
	accept_event()

func _draw() -> void:
	var rect := image_rect()
	draw_style_box(preload("res://scripts/computer_ui.gd").style(Color("e8ede3"), 0, 8), Rect2(Vector2.ZERO, size))
	if texture: draw_texture_rect(texture, rect, false)
	else:
		draw_rect(rect, Color("dae4d9"))
		for index in range(1, 8):
			draw_line(rect.position + Vector2(rect.size.x * index / 8.0, 0), rect.position + Vector2(rect.size.x * index / 8.0, rect.size.y), Color("c3cfc0"))
			draw_line(rect.position + Vector2(0, rect.size.y * index / 8.0), rect.position + Vector2(rect.size.x, rect.size.y * index / 8.0), Color("c3cfc0"))
	for row in ordered_slots():
		var number := int(row.get("slot", 1))
		var color: Color = COLORS[clampi(number - 1, 0, 4)]
		if number != selected_slot: color.a = 0.42
		var previous := Vector2.ZERO
		var route: Array = row.get("steps", [])
		for index in range(route.size()):
			var step: Dictionary = route[index]
			var position := world_to_canvas(step.get("position", [0, 0]))
			if index > 0: draw_line(previous, position, color, 3.0 if number == selected_slot else 1.5, true)
			var radius := 8.0 if number == selected_slot and index == selected_step else 6.0
			draw_circle(position, radius + 2, Color("fffdf6"))
			draw_circle(position, radius, color)
			draw_string(preload("res://scripts/phone_ui.gd").font(), position + Vector2(-3, 4), str(index + 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color("fffdf6"))
			if step.get("look_at") is Array:
				var look := world_to_canvas(step.look_at)
				draw_dashed_line(position, look, color, 1.5, 5.0, true)
				var direction := (look - position).normalized()
				var perpendicular := Vector2(-direction.y, direction.x)
				draw_line(look, look - direction * 9 + perpendicular * 4, color, 1.5, true)
				draw_line(look, look - direction * 9 - perpendicular * 4, color, 1.5, true)
				if number == selected_slot and index == selected_step: draw_circle(look, 4.5, color, false, 1.5)
			previous = position
	if placement_pointer_visible():
		# The center is exactly the click coordinate, including zoom and pan.
		for direction in [Vector2.LEFT, Vector2.RIGHT, Vector2.UP, Vector2.DOWN]:
			var start: Vector2 = pointer_position + direction * 4.0
			var end: Vector2 = pointer_position + direction * 12.0
			draw_line(start, end, Color("172b24"), 5.0, true)
			draw_line(start, end, Color("fffdf6"), 2.0, true)
		draw_circle(pointer_position, 2.5, Color("172b24"))
		draw_circle(pointer_position, 1.0, Color("fffdf6"))
