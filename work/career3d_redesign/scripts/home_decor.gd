extends CanvasLayer
## Purchases use the personal wallet; placement previews never write saves.
const UI = preload("res://scripts/computer_ui.gd")
const Buildings = preload("res://scripts/scene_tiers.gd")
var room: Node3D
var panel: PanelContainer
var content: VBoxContainer
var status: Label
var save_button: Button
var ghost: MeshInstance3D
var draft: Array = []
var baseline: Array = []
var home: Dictionary = {}
var pending: Dictionary = {}
var tab := "furniture"
var dirty := false
var awaiting := ""
var camera_before: Vector3
var closing_prompt := false
var clearing_prompt := false
var command_sender: Callable

func setup(value: Node3D) -> void:
	room = value
	layer = 12
	var root := Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	panel = PanelContainer.new()
	panel.name = "HomeDecoration"
	panel.set_anchors_and_offsets_preset(Control.PRESET_RIGHT_WIDE)
	panel.offset_left = -370; panel.offset_right = -18
	panel.offset_top = 20; panel.offset_bottom = -20
	panel.add_theme_stylebox_override("panel", UI.style(UI.CREAM, 18, 20, UI.LINE))
	root.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	panel.add_child(column)
	UI.label(column, "布置房间", 26)
	UI.label(column, "床和电脑保留，空出来的地方由你布置。", 13, UI.MUTED).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status = UI.label(column, "", 14, UI.GREEN)
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	column.add_child(scroll)
	content = VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 10)
	scroll.add_child(content)
	var controls := HBoxContainer.new()
	column.add_child(controls)
	save_button = UI.button(controls, "保存摆放", _save)
	save_button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	UI.primary(save_button)
	UI.button(controls, "完成", _close_requested)
	UI.label(column, "点击家具移动 · 点击地面摆放\nR 旋转 · Esc 取消 · 收起后可再次摆放", 13, UI.MUTED).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	ghost = MeshInstance3D.new()
	ghost.name = "FurniturePlacementPreview"
	room.add_child(ghost)
	ghost.mesh = BoxMesh.new()
	var material := StandardMaterial3D.new()
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_color = Color(.3,.65,.45,.35)
	ghost.material_override = material
	ghost.visible = false
	CareerBridge.changed.connect(_context_changed)
	CareerBridge.command_finished.connect(_finished)
	Locale.changed.connect(func(): if visible: _render())
	hide()

func present() -> void:
	if visible: return
	UI.Device.device_open(self,"decoration")
	home = CareerBridge.context.get("environment", {}).get("home", {}).duplicate(true)
	draft = home.get("placed", []).duplicate(true)
	baseline = draft.duplicate(true)
	dirty = false; closing_prompt = false; clearing_prompt = false; pending.clear()
	camera_before = Vector3(room.yaw, room.pitch, room.zoom)
	room.yaw = 0; room.pitch = 1.19; room.zoom = 8.8
	room.camera.h_offset = 1.65
	show()
	_preview(); _render()

func _render() -> void:
	for child in content.get_children():
		content.remove_child(child); child.queue_free()
	status.text = Locale.text("个人资金 %s" % preload("res://scripts/ui_format.gd").money(home.get("balance", 0)))
	var tabs := HBoxContainer.new()
	content.add_child(tabs)
	for entry in [["furniture","家具"],["wallpaper","墙面"],["floor","地板"]]:
		var button := UI.button(tabs, entry[1], _set_tab.bind(entry[0]))
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		if tab == entry[0]: button.add_theme_stylebox_override("normal", UI.style(UI.MINT, 10, 10))
	if not pending.is_empty():
		UI.label(content, "把家具放到地面上", 17)
		var controls := HBoxContainer.new()
		content.add_child(controls)
		UI.button(controls, "旋转 90°", _rotate)
		UI.button(controls, "取消移动", _cancel_move)
		var colors := HBoxContainer.new()
		content.add_child(colors)
		for color in ["7b9d70","caa078","e7cda0","97b8a8","bfaa95","d8acac"]:
			var swatch := UI.button(colors, "●", _color.bind(color))
			swatch.add_theme_color_override("font_color", Color(color))
			swatch.custom_minimum_size.x = 35
	var blocked := str(CareerBridge.context.get("environment", {}).get("blocked", ""))
	if not blocked.is_empty(): UI.label(content, blocked, 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	for item in home.get("catalog", []):
		if str(item.kind) != tab: continue
		var box := UI.card(content)
		UI.label(box, Locale.field(item, "name"), 18)
		var owned := _count(str(item.id), home.get("owned", []))
		if tab == "furniture":
			UI.label(box, "已购买 %d · 已摆放 %d" % [owned, _placed_count(str(item.id))], 13, UI.MUTED)
		var row := HBoxContainer.new()
		box.add_child(row)
		if tab == "furniture" or owned == 0:
			var buy := UI.button(row, "购买 %s" % preload("res://scripts/ui_format.gd").money(item.price), _buy.bind(item))
			buy.disabled = not awaiting.is_empty() or not blocked.is_empty() or int(home.get("balance",0)) < int(item.price)
		if owned > 0:
			var use := UI.button(row, "摆放" if tab == "furniture" else "使用", _use.bind(item))
			use.disabled = not awaiting.is_empty() or not blocked.is_empty() or (tab == "furniture" and owned <= _placed_count(str(item.id)))
	if not draft.is_empty():
		UI.label(content, "房间里的家具", 20)
		for placement in draft:
			var row := HBoxContainer.new()
			content.add_child(row)
			UI.button(row, Locale.field(_item(str(placement.item)), "name"), _move.bind(placement)).size_flags_horizontal = Control.SIZE_EXPAND_FILL
			UI.button(row, "收起", _remove.bind(str(placement.id)))
		UI.button(content, "全部收起", func(): clearing_prompt = true; _render())
	if clearing_prompt:
		UI.label(content, "收起的家具仍在库存里，不会出售。", 14).autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		UI.button(content, "确认收起全部家具", _clear_room)
		UI.button(content, "继续保留", func(): clearing_prompt = false; _render())
	if closing_prompt:
		UI.label(content, "摆放还没保存。", 16)
		UI.button(content, "不保存，离开装修", close).set_meta("decor_exit", true)
		UI.button(content, "继续布置", func(): closing_prompt=false; _render()).set_meta("decor_exit", true)
	# Freeze the complete draft while a write is in flight, including the placed
	# furniture list. Otherwise a successful save could discard edits made after it.
	if not _editable():
		for button in content.find_children("*", "Button", true, false): button.disabled = true
		# A blocked career forbids edits, not leaving the editor. Read-only exit
		# controls remain available unless an actual request is in flight.
		if awaiting.is_empty():
			for button in content.find_children("*", "Button", true, false):
				if button.get_meta("decor_exit", false): button.disabled = false
	save_button.disabled = not dirty or not _editable() or not pending.is_empty()
	save_button.tooltip_text = Locale.text("先摆放或取消正在移动的家具。") if not pending.is_empty() else ""
	if not awaiting.is_empty(): status.text = Locale.text("正在保存……")
	elif dirty: status.text += Locale.text(" · 摆放尚未保存")

func _editable() -> bool:
	return awaiting.is_empty() and str(CareerBridge.context.get("environment", {}).get("blocked", "")).is_empty()

func _count(value: String, values: Array) -> int:
	var count := 0
	for entry in values:
		if str(entry) == value: count += 1
	return count

func _placed_count(item: String) -> int:
	var count := 0
	for placement in draft:
		if str(placement.item) == item: count += 1
	return count

func _item(id: String) -> Dictionary:
	for item in home.get("catalog", []):
		if str(item.id) == id: return item
	return {}

func _set_tab(value: String) -> void:
	tab = value; _render()

func _buy(item: Dictionary) -> void:
	_submit("home-buy", {"item":item.id,"price":int(item.price)})

func _use(item: Dictionary) -> void:
	if not _editable(): return
	if item.kind != "furniture":
		_submit("home-finish", {"item":item.id})
		return
	if _placed_count(str(item.id)) >= _count(str(item.id), home.get("owned", [])): return
	pending = {"id":"furniture-%d" % Time.get_ticks_usec(), "item":item.id,"x":0.0,"z":0.0,"rotation":0,"color":item.color}
	_preview()
	_render()

func _move(placement: Dictionary) -> void:
	if not _editable(): return
	pending = placement.duplicate(true)
	_preview()
	_render()

func _remove(id: String) -> void:
	if not _editable(): return
	draft = draft.filter(func(row): return str(row.id) != id)
	if str(pending.get("id", "")) == id: _cancel_move()
	_changed()

func _clear_room() -> void:
	if not _editable(): return
	draft.clear(); pending.clear(); ghost.visible = false
	clearing_prompt = false
	_changed()

func _rotate() -> void:
	if pending.is_empty() or not _editable(): return
	pending.rotation = (int(pending.rotation)+90)%360

func _color(value: String) -> void:
	if not pending.is_empty() and _editable(): pending.color = value

func _cancel_move() -> void:
	if not awaiting.is_empty(): return
	pending.clear(); ghost.visible = false; _preview(); _render()

func _changed() -> void:
	dirty = JSON.stringify(draft) != JSON.stringify(baseline)
	_preview(); _render()

func _preview() -> void:
	var view := home.duplicate(true)
	view["placed"] = draft
	var building := Buildings.apply_home(room, room.model, view)
	for object in building.get_children():
		if object is Node3D:
			object.visible = str(object.get_meta("placement_id", "")) != str(pending.get("id", ""))

func _context_changed() -> void:
	if not visible: return
	home = CareerBridge.context.get("environment", {}).get("home", {}).duplicate(true)
	var saved: Array = home.get("placed", []).duplicate(true)
	# An idle editor follows a loaded/reconnected save; an unsaved draft survives
	# refreshes. If a disconnected save did commit, its matching draft becomes clean.
	if not dirty and pending.is_empty(): draft = saved.duplicate(true)
	baseline = saved
	dirty = JSON.stringify(draft) != JSON.stringify(baseline)
	_preview()
	_render()

func _submit(action: String, body: Dictionary) -> void:
	if not _editable(): return
	var payload := body.duplicate(true)
	payload["revision"] = int(CareerBridge.context.get("calendar", {}).get("revision",0))
	payload["request_id"] = "home-%d-%d" % [Time.get_unix_time_from_system(), Time.get_ticks_usec()]
	var path := "/api/3d/environment/" + action
	var accepted: bool = command_sender.call(path, payload) if command_sender.is_valid() else CareerBridge.command(path,payload)
	if accepted:
		awaiting = path
		_render()
		status.text = Locale.text("正在保存……")
	else: status.text = Locale.text(CareerBridge.message)

func _save() -> void:
	if not _editable() or not dirty: return
	if not pending.is_empty():
		status.text = Locale.text("先摆放或取消正在移动的家具。")
		return
	var placements: Array = []
	for row in draft:
		placements.append({"id":str(row.id),"item":str(row.item),"x":float(row.x),"z":float(row.z),"rotation":int(row.rotation),"color":str(row.color)})
	_submit("home-layout", {"placed":placements})

func _finished(path: String, result: Dictionary) -> void:
	if path != awaiting: return
	awaiting = ""
	if result.get("ok",false) and path.ends_with("home-layout"):
		draft = home.get("placed", []).duplicate(true)
		baseline = draft.duplicate(true); dirty = false
	_render()
	status.text = Locale.field(result, "reason", Locale.field(result,"msg",CareerBridge.message))

func _process(_delta: float) -> void:
	if not visible or pending.is_empty() or not _editable():
		ghost.visible = false
		return
	_update_pointer(get_viewport().get_mouse_position())

func _floor_point(mouse: Vector2) -> Variant:
	if panel.get_global_rect().has_point(mouse): return null
	var plane := Plane(Vector3.UP, .12)
	return plane.intersects_ray(room.camera.project_ray_origin(mouse), room.camera.project_ray_normal(mouse))

func _update_pointer(mouse: Vector2) -> void:
	var point: Variant = _floor_point(mouse)
	if point == null:
		ghost.visible = false
		return
	pending.x = snappedf(point.x,.25); pending.z = snappedf(point.z,.25)
	var size := _footprint(pending)
	ghost.mesh.size = Vector3(size.x,.08,size.y)
	ghost.position = Vector3(pending.x,.15,pending.z); ghost.visible = true
	ghost.material_override.albedo_color = Color(.28,.65,.44,.45) if _local_valid(pending) else Color(.8,.25,.20,.5)

func _select_at(point: Vector3) -> void:
	# Solids take precedence over rugs under them. Clicking an existing item is
	# equivalent to its catalogue Move button and never writes a save.
	for solid in [true, false]:
		for row in draft:
			if bool(_item(str(row.item)).get("solid", true)) != solid: continue
			var rect := Rect2(Vector2(row.x, row.z) - _footprint(row) / 2.0, _footprint(row))
			if rect.has_point(Vector2(point.x, point.z)):
				_move(row); return

func _place_pending() -> void:
	if not _editable() or pending.is_empty(): return
	if _local_valid(pending):
		var id := str(pending.id)
		draft = draft.filter(func(row): return str(row.id) != id)
		draft.append(pending.duplicate(true))
		pending.clear(); ghost.visible = false; _changed()
	else: status.text = Locale.text("这里放不下，换个位置试试。")

func _footprint(row: Dictionary) -> Vector2:
	var item := _item(str(row.item))
	var size := Vector2(item.get("footprint", [0.5,0.5])[0],item.get("footprint", [0.5,0.5])[1])
	return Vector2(size.y,size.x) if int(row.rotation) in [90,270] else size

func _overlap(a: Vector2, size: Vector2, b: Vector2, other: Vector2, margin: float = .04) -> bool:
	return absf(a.x-b.x) < (size.x+other.x)/2+margin and absf(a.y-b.y) < (size.y+other.y)/2+margin

func _local_valid(row: Dictionary) -> bool:
	var size := _footprint(row)
	var center := Vector2(row.x,row.z)
	if center.x-size.x/2 < -3.1 or center.x+size.x/2 > 3.1 or center.y-size.y/2 < -2.65 or center.y+size.y/2 > 2.7: return false
	if not _item(str(row.item)).get("solid",true): return true
	for fixed in home.get("fixed", []):
		if _overlap(center,size,Vector2(fixed[0],fixed[1]),Vector2(fixed[2],fixed[3]),.03): return false
	for anchor in home.get("anchors", []):
		if _overlap(center,size,Vector2(anchor[0],anchor[1]),Vector2(.55,.55),.1): return false
	for other in draft:
		if str(other.id) != str(row.id) and _item(str(other.item)).get("solid",true):
			if _overlap(center,size,Vector2(other.x,other.z),_footprint(other)): return false
	return true

func _unhandled_input(event: InputEvent) -> void:
	if not visible: return
	if event is InputEventKey and event.pressed and not event.echo and event.physical_keycode == KEY_ESCAPE:
		if not awaiting.is_empty():
			get_viewport().set_input_as_handled(); return
		if not pending.is_empty(): _cancel_move()
		else: _close_requested()
		get_viewport().set_input_as_handled()
		return
	if not _editable(): return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if pending.is_empty():
			var point: Variant = _floor_point(event.position)
			if point != null: _select_at(point)
		else:
			_update_pointer(event.position)
			if ghost.visible: _place_pending()
		get_viewport().set_input_as_handled()
	if event is InputEventKey and event.pressed and not event.echo:
		if event.physical_keycode == KEY_R: _rotate(); get_viewport().set_input_as_handled()

func _input(event: InputEvent) -> void:
	# P closes this editor first, instead of silently throwing its draft away
	# when the global phone shortcut opens a different device.
	if visible and event is InputEventKey and event.pressed and not event.echo and event.physical_keycode == KEY_P:
		_close_requested()
		UI.Device.claim_key(self)

func _close_requested() -> void:
	if not awaiting.is_empty(): return
	if dirty:
		closing_prompt = true; _render()
	else: close()

func close() -> void:
	if not visible: return
	hide(); ghost.visible = false; pending.clear()
	room.yaw = camera_before.x; room.pitch = camera_before.y; room.zoom = camera_before.z
	room.camera.h_offset = 0
	Buildings.apply_home(room,room.model,CareerBridge.context.get("environment",{}).get("home",{}))
	preload("res://scripts/home_room.gd").clear_player(room, CareerBridge.context.get("environment",{}).get("home",{}))
	UI.Device.device_closed(self)

func _exit_tree() -> void:
	if is_instance_valid(ghost): ghost.queue_free()
