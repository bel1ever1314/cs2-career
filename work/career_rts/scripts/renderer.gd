extends Control
## Draws only the observation layer supplied by the simulation. Mouse commands
## are returned in radar coordinates; no engine state is changed here.
signal move_order(point: Vector2)
signal actor_selected(id: String)
signal units_selected(ids: Array, additive: bool)
const Style = preload("res://scripts/style.gd")
var data: Dictionary = {}
var state: Dictionary = {}
var nav
var texture: Texture2D
var font: Font
var spectator := false
var viewer_team := "t"
var controlled_id := ""
var show_routes := false
var follow_player := true
var zoom := 1.0
var center := Vector2(512, 512)
var scale_factor := 1.0
var origin := Vector2.ZERO
var rendered: Dictionary = {}
var visual_events: Array[Dictionary] = []
var marker := Vector2.INF
var marker_age := 0.0
var vision := PackedVector2Array()
var vision_timer := 0.0
var dragging := false
var damage_pulse := 0.0
var label_rects: Array[Rect2] = []
var commander := false
var selected_ids: Array = []
var box_selecting := false
var box_start := Vector2.ZERO
var box_end := Vector2.ZERO

func _ready() -> void:
	font = Style.theme().default_font
	mouse_filter = Control.MOUSE_FILTER_STOP
	clip_contents = true
	resized.connect(queue_redraw)

func setup(map_data: Dictionary, model) -> void:
	data = map_data
	nav = model
	var preferred := str(data.get("radar", {}).get("image", ""))
	if not ResourceLoader.exists(preferred):
		preferred = str(data.get("radar", {}).get("original", ""))
	texture = load(preferred)
	queue_redraw()

static func vec(value) -> Vector2:
	if value is Vector2:
		return value
	if value is Array and value.size() >= 2:
		return Vector2(float(value[0]), float(value[1]))
	return Vector2.ZERO

func update_state(value: Dictionary, mode: String, team: String, human: String) -> void:
	state = value
	spectator = mode == "spectate"
	viewer_team = team
	controlled_id = human
	for p in state.get("players", []):
		var id := str(p["id"])
		if not rendered.has(id):
			rendered[id] = {"pos": vec(p["pos"]), "yaw": float(p["yaw"])}
	queue_redraw()

func push_event(event: Dictionary) -> void:
	var type := str(event.get("type", ""))
	if type == "round_start":
		rendered.clear()
		visual_events.clear()
		vision.clear()
		return
	if type in ["shot", "kill", "bomb_exploded", "utility_throw"]:
		if type == "shot" and not spectator:
			var p := _actor(str(event.get("id", "")))
			if p.get("team", "") != viewer_team and not _can_see(p):
				return
		if type == "kill" and not spectator:
			var victim := _actor(str(event.get("victim_id", event.get("victim", ""))))
			if not _can_see(victim): return
		visual_events.append({"event": event, "age": 0.0, "life": .11 if type == "shot" else 1.2})
		if type == "kill" and event.get("victim_id", event.get("victim", "")) == controlled_id:
			damage_pulse = .8
		if visual_events.size() > 64:
			visual_events.pop_front()

func _process(dt: float) -> void:
	var amount := 1.0 - exp(-35.0 * dt)
	for p in state.get("players", []):
		var id := str(p["id"])
		if rendered.has(id):
			var desired := vec(p["pos"])
			var old := vec(rendered[id]["pos"])
			rendered[id]["pos"] = desired if old.distance_to(desired) > 90 else old.lerp(desired, amount)
			rendered[id]["yaw"] = lerp_angle(float(rendered[id]["yaw"]), float(p["yaw"]), amount)
	if follow_player and not spectator:
		var actor := _actor(controlled_id)
		if not actor.is_empty() and actor.get("alive", false):
			center = center.lerp(vec(actor["pos"]), 1.0 - exp(-8.0 * dt))
	vision_timer -= dt
	if vision_timer <= 0:
		vision_timer = .15
		_update_vision()
	for v in visual_events:
		v["age"] += dt
	visual_events = visual_events.filter(func(v): return float(v["age"]) < float(v["life"]))
	marker_age = maxf(0, marker_age - dt)
	damage_pulse = maxf(0, damage_pulse - dt)
	queue_redraw()

func _reframe() -> void:
	scale_factor = maxf(.01, minf(size.x, size.y) / 1024.0 * zoom)
	var half := size / (2 * scale_factor)
	center.x = clampf(center.x, minf(512, half.x), maxf(512, 1024 - half.x))
	center.y = clampf(center.y, minf(512, half.y), maxf(512, 1024 - half.y))
	origin = size * .5 - center * scale_factor

func screen_to_world(screen_point: Vector2) -> Vector2:
	_reframe()
	return (screen_point - global_position - origin) / scale_factor

func world_to_local(point: Vector2) -> Vector2:
	return point * scale_factor + origin

func reset_camera(mode: String, actor: Dictionary = {}) -> void:
	cancel_pointer()
	follow_player = mode == "play"
	zoom = 2.6 if follow_player else 1.0
	center = vec(actor.get("pos", [512, 512])) if follow_player else Vector2(512, 512)
	rendered.clear()

func change_zoom(value: float) -> void:
	zoom = clampf(zoom * value, 1.0, 3.6)
	queue_redraw()

func fit_map() -> void:
	follow_player = false
	center = Vector2(512, 512)
	zoom = 1.0
	queue_redraw()

func cancel_pointer() -> void:
	dragging = false
	box_selecting = false
	queue_redraw()

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP and event.pressed:
			change_zoom(1.12)
			accept_event()
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN and event.pressed:
			change_zoom(1 / 1.12)
			accept_event()
		elif event.button_index == MOUSE_BUTTON_MIDDLE:
			dragging = event.pressed
		elif event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
			marker = screen_to_world(get_global_mouse_position())
			marker_age = 2.5
			move_order.emit(marker)
			accept_event()
		elif event.button_index == MOUSE_BUTTON_LEFT and commander:
			if event.pressed:
				box_selecting = true
				box_start = event.position
				box_end = box_start
			elif box_selecting:
				box_selecting = false
				var ids: Array = []
				var rectangle := Rect2(box_start, box_end - box_start).abs()
				var closest := 15.0
				var clicked := ""
				for p in state.get("players", []):
					if p.get("team", "") != viewer_team or not p.get("alive", false): continue
					var screen: Vector2 = world_to_local(vec(p["pos"]))
					if rectangle.size.length() >= 6 and rectangle.has_point(screen):
						ids.append(str(p["id"]))
					elif rectangle.size.length() < 6 and screen.distance_to(event.position) < closest:
						closest = screen.distance_to(event.position)
						clicked = str(p["id"])
				if not clicked.is_empty(): ids = [clicked]
				units_selected.emit(ids, event.shift_pressed)
			queue_redraw()
			accept_event()
		elif event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
			if not follow_player:
				var point := screen_to_world(get_global_mouse_position())
				for p in state.get("players", []):
					if p.get("team", "") == viewer_team and vec(p["pos"]).distance_to(point) < 15:
						actor_selected.emit(str(p["id"]))
						break
	elif event is InputEventMouseMotion and box_selecting:
		box_end = event.position
		queue_redraw()
		accept_event()
	elif event is InputEventMouseMotion and dragging:
		follow_player = false
		center -= event.relative / scale_factor
		accept_event()

func _actor(id: String) -> Dictionary:
	for p in state.get("players", []):
		if p["id"] == id:
			return p
	return {}

func _can_see(p: Dictionary) -> bool:
	return spectator or p.get("team", "") == viewer_team or viewer_team in p.get("spotted_by", [])

func _point_observed(point: Vector2) -> bool:
	if spectator: return true
	if nav == null: return false
	for p in state.get("players", []):
		if p.get("team", "") != viewer_team or not p.get("alive", false) or float(p.get("flash_remaining", 0)) > .15: continue
		var offset := point - vec(p["pos"])
		if offset.length_squared() > 900 * 900: continue
		var human: bool = p.get("human_control", false)
		var awareness := float(p.get("skills", {}).get("awareness", 80)) / 100.0
		if not human and absf(angle_difference(float(p.get("yaw", 0)), offset.angle())) > deg_to_rad(lerpf(65.0, 115.0, awareness)): continue
		if not nav.segment_blocked(vec(p["pos"]), point, 0): return true
	return false

func _update_vision() -> void:
	vision.clear()
	if spectator or nav == null:
		return
	var p := _actor(controlled_id)
	if p.is_empty() or not p.get("alive", false):
		return
	var at := vec(p["pos"])
	vision.append(at)
	var yaw := float(p["yaw"])
	for i in range(49):
		var direction := Vector2.from_angle(yaw - 1.0 + 2.0 * float(i) / 48.0)
		var end := at + direction * 300
		if nav.has_method("raycast_endpoint"):
			end = nav.raycast_endpoint(at, end)
		else:
			if nav.segment_blocked(at, end, 0):
				var low := 0.0
				var high := 300.0
				for _j in range(7):
					var middle := (low + high) * .5
					if nav.segment_blocked(at, at + direction * middle, 0): high = middle
					else: low = middle
					end = at + direction * low
		for utility in state.get("utilities", []):
			if utility.get("kind", "") != "smoke" or utility.get("state", "") != "active": continue
			var relative := at - vec(utility.get("pos", [0, 0]))
			var radius := float(utility.get("radius", 27))
			var c := relative.length_squared() - radius * radius
			if c <= 0:
				end = at
				break
			var b := relative.dot(direction)
			var disc := b * b - c
			if disc >= 0:
				var near := -b - sqrt(disc)
				if near > 0 and near < at.distance_to(end): end = at + direction * near
		vision.append(end)

func _draw() -> void:
	_reframe()
	label_rects.clear()
	draw_rect(Rect2(Vector2.ZERO, size), Color("10191e"))
	if texture != null:
		var tint := Color(1, 1, 1, 1) if spectator else Color(.77, .81, .84, 1)
		draw_texture_rect(texture, Rect2(origin, Vector2.ONE * 1024 * scale_factor), false, tint)
	if vision.size() >= 3:
		var points := PackedVector2Array()
		for point in vision: points.append(world_to_local(point))
		draw_colored_polygon(points, Color(.68, .82, .73, .085))
	for site in data.get("sites", {}):
		var location := world_to_local(vec(data["sites"][site]["center"]))
		var r := float(data["sites"][site].get("radius", 35)) * scale_factor
		draw_circle(location, r, Color(.85, .66, .35, .09))
		draw_arc(location, r, 0, TAU, 48, Color(.86, .72, .47, .4), 1.2, true)
		_text(location + Vector2(-7, 7), str(site), 21, Color("d9bd84"))
	for landmark in data.get("labels", []):
		_text(world_to_local(vec(landmark["position"])), str(landmark["label"]), 12, Color(.78, .79, .72, .55))
	if show_routes:
		for p in state.get("players", []):
			if p.get("team", "") != viewer_team or not p.get("alive", false): continue
			var previous := world_to_local(vec(p["pos"]))
			for point in p.get("path", []):
				var next := world_to_local(vec(point))
				draw_line(previous, next, Color(.5, .79, .72, .22), 1, true)
				previous = next
	_draw_utilities()
	_draw_bomb()
	for p in state.get("players", []):
		if _can_see(p): _draw_actor(p)
	for visual in visual_events: _draw_event(visual)
	if marker_age > 0 and marker.is_finite():
		var location := world_to_local(marker)
		draw_arc(location, 12, 0, TAU, 24, Style.GREEN, 1.5, true)
		draw_line(location - Vector2(17, 0), location + Vector2(17, 0), Style.GREEN, 1)
		draw_line(location - Vector2(0, 17), location + Vector2(0, 17), Style.GREEN, 1)
	if damage_pulse > 0:
		draw_rect(Rect2(Vector2.ZERO, size), Color(.8, .2, .12, damage_pulse * .1))
	var human := _actor(controlled_id)
	if not human.is_empty() and float(human.get("flash_remaining", 0)) > 0:
		draw_rect(Rect2(Vector2.ZERO, size), Color(.92, .95, .94, minf(.84, float(human["flash_remaining"]) * .35)))
	if follow_player and get_global_rect().has_point(get_global_mouse_position()):
		var mouse := get_local_mouse_position()
		for sign in [-1, 1]:
			draw_line(mouse + Vector2(sign * 4, 0), mouse + Vector2(sign * 11, 0), Style.TEXT, 1.3, true)
			draw_line(mouse + Vector2(0, sign * 4), mouse + Vector2(0, sign * 11), Style.TEXT, 1.3, true)
		draw_circle(mouse, 1, Style.TEXT)
	if box_selecting:
		var rectangle := Rect2(box_start, box_end - box_start).abs()
		draw_rect(rectangle, Color(.5, .8, .65, .12))
		draw_rect(rectangle, Style.GREEN, false, 1.5)

func _text(at: Vector2, text: String, fontsize: int = 12, tint: Color = Style.TEXT) -> void:
	if font == null: return
	draw_string(font, at + Vector2(0, 1), text, HORIZONTAL_ALIGNMENT_LEFT, -1, fontsize, Color(0, 0, 0, .7))
	draw_string(font, at, text, HORIZONTAL_ALIGNMENT_LEFT, -1, fontsize, tint)

func _draw_actor(p: Dictionary) -> void:
	var id := str(p["id"])
	var at := world_to_local(vec(rendered.get(id, {}).get("pos", p["pos"])))
	var side_color := Style.GOLD if p.get("side", "t") == "t" else Style.BLUE
	if not p.get("alive", false):
		draw_line(at - Vector2(3, 3), at + Vector2(3, 3), Color(.75, .7, .6, .4), 1.5)
		draw_line(at - Vector2(3, -3), at + Vector2(3, -3), Color(.75, .7, .6, .4), 1.5)
		return
	var radius := maxf(4, 3.5 * scale_factor)
	var human: bool = id == controlled_id and p.get("human_control", false)
	var yaw := float(rendered.get(id, {}).get("yaw", p["yaw"]))
	var direction := Vector2.from_angle(yaw)
	if human:
		draw_circle(at, radius + 5, Color(.91, .95, .86, .1))
		draw_arc(at, radius + 4, 0, TAU, 32, Style.TEXT, 1.5, true)
	if id in selected_ids:
		draw_arc(at, radius + 7, 0, TAU, 32, Style.GREEN, 2, true)
	draw_circle(at + Vector2(1, 2), radius + 1, Color(0, 0, 0, .6))
	draw_circle(at, radius, side_color)
	if state.get("bomb", {}).get("state", "") == "carried" and state.get("bomb", {}).get("carrier_id", "") == id and (p.get("team", "") == viewer_team or spectator):
		draw_rect(Rect2(at + Vector2(radius + 3, -3), Vector2(5, 6)), Style.GOLD)
	draw_line(at, at + direction * (radius + 7), side_color.lightened(.25), 3, true)
	draw_circle(at - direction * 1.3, radius * .45, side_color.darkened(.5))
	var name_value := str(p["name"])
	var label_width := font.get_string_size(name_value, HORIZONTAL_ALIGNMENT_LEFT, -1, 12).x
	var label_at := _name_position(at, radius, label_width)
	if label_at.distance_to(at) > 28:
		draw_line(at, label_at + Vector2(label_width * .5, -4), Color(side_color, .25), 1, true)
	_text(label_at, name_value, 12, Style.TEXT if human else side_color.lightened(.25))
	if p.get("team", "") == viewer_team or spectator:
		var width := 22.0
		draw_line(at + Vector2(-width / 2, radius + 5), at + Vector2(width / 2, radius + 5), Color("26323a"), 2)
		draw_line(at + Vector2(-width / 2, radius + 5), at + Vector2(-width / 2 + width * float(p["hp"]) / 100, radius + 5), Style.GREEN, 2)
	if p.get("interacting", false):
		draw_arc(at, radius + 8, -PI / 2, -PI / 2 + TAU * .75, 32, Style.GOLD, 2, true)

func _name_position(at: Vector2, radius: float, width: float) -> Vector2:
	var offsets := [Vector2(-width * .5, -radius - 7), Vector2(-width * .5, radius + 22),
		Vector2(radius + 11, 4), Vector2(-width - radius - 11, 4),
		Vector2(radius + 12, -22), Vector2(-width - radius - 12, -22),
		Vector2(radius + 12, 34), Vector2(-width - radius - 12, 34),
		Vector2(-width * .5, -radius - 40), Vector2(-width * .5, radius + 50)]
	for offset in offsets:
		var point: Vector2 = at + offset
		var bounds := Rect2(point + Vector2(-2, -12), Vector2(width + 4, 16))
		var free := true
		for occupied in label_rects:
			if occupied.grow(2).intersects(bounds):
				free = false
				break
		if free:
			label_rects.append(bounds)
			return point
	var point := at + Vector2(-width * .5, -radius - 7)
	label_rects.append(Rect2(point + Vector2(-2, -12), Vector2(width + 4, 16)))
	return point

func _draw_bomb() -> void:
	var bomb: Dictionary = state.get("bomb", {})
	if bomb.get("state", "") not in ["planted", "dropped"]: return
	if bomb.get("state", "") == "dropped" and not spectator and state.get("team_sides", {}).get(viewer_team, "t") != "t" and not _point_observed(vec(bomb.get("pos", [0, 0]))): return
	var at := world_to_local(vec(bomb.get("pos", [0, 0])))
	if bomb["state"] == "planted":
		var pulse := .5 + .5 * sin(float(state.get("time", 0)) * 8)
		draw_circle(at, 12 + pulse * 4, Color(.92, .43, .25, .12))
		draw_circle(at, 5, Style.RED)
	else:
		draw_rect(Rect2(at - Vector2(4, 4), Vector2(8, 8)), Style.GOLD)
	_text(at + Vector2(9, 4), "C4", 11, Style.GOLD)

func _draw_utilities() -> void:
	for utility in state.get("utilities", []):
		if not spectator and utility.get("team", "") != viewer_team and not _point_observed(vec(utility.get("pos", [0, 0]))): continue
		var at := world_to_local(vec(utility.get("pos", [0, 0])))
		if utility.get("state", "") == "flying":
			draw_circle(at, 3, Style.GREEN)
			continue
		var radius := float(utility.get("radius", 45)) * scale_factor
		draw_circle(at, radius, Color(.7, .76, .79, .18))
		draw_arc(at, radius, 0, TAU, 32, Color(.8, .86, .89, .24), 1, true)

func _draw_event(visual: Dictionary) -> void:
	var event: Dictionary = visual["event"]
	var age := float(visual["age"])
	var alpha := 1.0 - age / float(visual["life"])
	match str(event.get("type", "")):
		"shot":
			var a := world_to_local(vec(event.get("from", [0, 0])))
			var b := world_to_local(vec(event.get("to", [0, 0])))
			draw_line(a, b, Color(1, .86, .52, alpha * .65), 1.6, true)
			draw_circle(a, 5 * alpha, Color(1, .85, .5, alpha * .8))
			draw_circle(b, 2 + (1 - alpha) * 3, Color(1, .68, .38, alpha * .8))
		"kill":
			var p := _actor(str(event.get("victim_id", event.get("victim", ""))))
			if not p.is_empty():
				draw_arc(world_to_local(vec(p["pos"])), 8 + age * 12, 0, TAU, 24, Color(.85, .3, .2, alpha * .5), 1, true)
		"bomb_exploded":
			draw_circle(world_to_local(vec(event.get("pos", [0, 0]))), 30 + age * 70, Color(1, .6, .2, alpha * .3))
