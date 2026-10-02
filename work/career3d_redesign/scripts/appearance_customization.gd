extends RefCounted
## Cosmetic projection only. The Python service persists the avatar and remains
## the only career writer; this module never changes attributes or match rules.
const UI = preload("res://scripts/computer_ui.gd")
const DEFAULTS := {"outfit":"jersey", "body_color":"fff1d2", "belly_color":"ffe3a3", "beak_color":"efa147", "comb_color":"d65a48", "jersey_color":"2c4556", "trim_color":"70b5a5"}
const COLOR_FIELDS := [{"key":"body_color", "name":"羽毛"}, {"key":"belly_color", "name":"腹部"}, {"key":"beak_color", "name":"喙与脚"}, {"key":"comb_color", "name":"鸡冠"}, {"key":"jersey_color", "name":"队服"}, {"key":"trim_color", "name":"饰边与耳机"}]
const PRESETS := [
	{"name":"奶油新秀", "body_color":"fff1d2", "belly_color":"ffe3a3", "beak_color":"efa147", "comb_color":"d65a48", "jersey_color":"2c4556", "trim_color":"70b5a5"},
	{"name":"暖橘午后", "body_color":"e5a66b", "belly_color":"ffe7ba", "beak_color":"b77737", "comb_color":"b94c44", "jersey_color":"795d4b", "trim_color":"e4c89a"},
	{"name":"海盐蓝调", "body_color":"c7d7dd", "belly_color":"edf3e8", "beak_color":"d7a064", "comb_color":"9e536b", "jersey_color":"355366", "trim_color":"a9d2c7"}
]
var draft: Dictionary = {}
var dirty := false
var saving := false
var creation_mode := false
var message := ""
var command_sender: Callable
var host_ref: WeakRef
var preview_model: Node3D
var pickers: Dictionary = {}
var outfit_select: OptionButton
var status_label: Label
var save_button: Button

static func normalize(raw: Dictionary) -> Dictionary:
	var result := DEFAULTS.duplicate()
	result["outfit"] = str(raw.get("outfit", "jersey")) if str(raw.get("outfit", "jersey")) in ["jersey", "natural"] else "jersey"
	for field in COLOR_FIELDS:
		var key: String = str(field["key"])
		var color := Color.from_string(str(raw.get(key, DEFAULTS[key])), Color(str(DEFAULTS[key])))
		result[key] = color.to_html(false)
	return result

func config() -> Dictionary:
	var avatar: Variant = CareerBridge.context.get("avatar", {})
	var raw: Variant = avatar.get("appearance", avatar) if avatar is Dictionary else {}
	if not raw is Dictionary: raw = {}
	return normalize(raw)

func values() -> Dictionary:
	if draft.is_empty(): return DEFAULTS.duplicate() if creation_mode else config()
	return normalize(draft)

func render(host: Node, parent: Node) -> void:
	host_ref = weakref(host)
	if draft.is_empty(): draft = DEFAULTS.duplicate() if creation_mode else config()
	elif not creation_mode and not dirty and not saving: draft = config()
	pickers.clear()
	UI.label(parent, "我的小鸡", 25)
	UI.label(parent, "选择羽毛颜色、队服与饰边，右侧改动会实时显示在角色上。", 12, UI.MUTED)
	var row := HBoxContainer.new()
	row.name = "AppearanceEditor"
	row.add_theme_constant_override("separation", 18)
	parent.add_child(row)
	var preview_column := UI.card(row)
	preview_column.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	preview_model = add_preview(preview_column, values(), Vector2(240, 240) if creation_mode else Vector2(250, 285))
	UI.label(preview_column, "实时预览 · 外观不影响属性", 12, UI.MUTED).horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var form := VBoxContainer.new()
	form.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	form.add_theme_constant_override("separation", 9)
	row.add_child(form)
	UI.label(form, "穿着", 13, UI.MUTED)
	outfit_select = OptionButton.new()
	outfit_select.name = "AppearanceOutfit"
	UI.dark_options(outfit_select)
	outfit_select.add_item("队服与耳机")
	outfit_select.set_item_metadata(0, "jersey")
	outfit_select.add_item("轻装")
	outfit_select.set_item_metadata(1, "natural")
	outfit_select.select(0 if draft["outfit"] == "jersey" else 1)
	outfit_select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	form.add_child(outfit_select)
	outfit_select.item_selected.connect(func(index: int): set_value("outfit", str(outfit_select.get_item_metadata(index))))
	var colors := GridContainer.new()
	colors.columns = 2
	colors.add_theme_constant_override("h_separation", 16)
	colors.add_theme_constant_override("v_separation", 7)
	form.add_child(colors)
	for field in COLOR_FIELDS:
		var key: String = str(field["key"])
		UI.label(colors, str(field["name"]), 14).vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		var picker := ColorPickerButton.new()
		picker.name = "Appearance_" + key
		UI.Base.decorate_button(picker)
		picker.color = Color(str(draft[key]))
		picker.edit_alpha = false
		picker.text = "#" + str(draft[key]).to_upper()
		picker.custom_minimum_size = Vector2(145, 35)
		picker.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		picker.tooltip_text = "点击选择" + str(field["name"]) + "颜色"
		colors.add_child(picker)
		pickers[key] = picker
		picker.color_changed.connect(func(color: Color): set_value(key, color.to_html(false)))
	UI.label(form, "配色灵感", 13, UI.MUTED)
	var presets := HBoxContainer.new()
	presets.add_theme_constant_override("separation", 6)
	form.add_child(presets)
	for preset in PRESETS:
		UI.button(presets, str(preset["name"]), select_preset.bind(preset))
	UI.label(form, "队服款式使用现有模型；羽毛、腹部、喙脚、鸡冠和衣服均可调色。", 12, UI.MUTED)
	var actions := HBoxContainer.new()
	parent.add_child(actions)
	save_button = null
	if creation_mode:
		UI.label(actions, "随新生涯保存", 14, UI.MUTED).vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		UI.button(actions, "恢复初始配色", reset)
	else:
		save_button = UI.button(actions, "保存外观", submit)
		save_button.name = "AppearanceSave"
		UI.primary(save_button)
		UI.button(actions, "恢复已保存外观", reset)
	status_label = UI.label(parent, "", 12, UI.MUTED)
	status_label.name = "AppearanceFeedback"
	_update_feedback()
	_apply_live()

func set_value(key: String, value: Variant) -> void:
	if not DEFAULTS.has(key) or saving: return
	draft[key] = value
	draft = normalize(draft)
	dirty = true
	message = "预览已更新，创建生涯时会一并保存。" if creation_mode else "预览已更新，保存后会随生涯保留。"
	_refresh_controls()
	_apply_live()
	_update_feedback()

func select_preset(preset: Dictionary) -> void:
	if saving: return
	for field in COLOR_FIELDS:
		var key: String = str(field["key"])
		draft[key] = preset[key]
	dirty = true
	message = "已预览「%s」，%s" % [str(preset["name"]), "创建生涯时会一并保存。" if creation_mode else "保存后会随生涯保留。"]
	_refresh_controls()
	_apply_live()
	_update_feedback()

func reset() -> void:
	if saving: return
	draft = DEFAULTS.duplicate() if creation_mode else config()
	dirty = false
	message = "已恢复初始配色。" if creation_mode else "已恢复上次保存的外观。"
	_refresh_controls()
	_apply_live()
	_update_feedback()

func submit() -> void:
	if saving or creation_mode: return
	var body := {"revision":int(CareerBridge.context.get("calendar", {}).get("revision", 0)), "appearance":values()}
	saving = true
	var accepted: bool = bool(command_sender.call("/api/3d/avatar", body)) if command_sender.is_valid() else CareerBridge.command("/api/3d/avatar", body)
	if not accepted:
		saving = false
		message = "外观还没有保存。后台正在同步，请稍后点击保存。" if CareerBridge.busy else "外观还没有保存，请检查本地后台连接。"
	else:
		message = "正在保存外观……"
	_update_feedback()

func finished(path: String, result: Dictionary) -> bool:
	if path != "/api/3d/avatar": return false
	saving = false
	if result.get("ok", false):
		dirty = false
		draft = config()
		var avatar: Variant = result.get("avatar", {})
		if avatar is Dictionary and avatar.get("appearance") is Dictionary: draft = normalize(avatar["appearance"])
		elif result.get("appearance") is Dictionary: draft = normalize(result["appearance"])
		message = "外观已保存，下次进入会继续使用。"
	else:
		message = str(result.get("reason", result.get("msg", "外观没有保存，请重试。")))
	_refresh_controls()
	_apply_live()
	_update_feedback()
	return true

func _refresh_controls() -> void:
	for key in pickers:
		var picker := pickers[key] as ColorPickerButton
		if is_instance_valid(picker):
			picker.color = Color(str(draft[key]))
			picker.text = "#" + str(draft[key]).to_upper()
	if is_instance_valid(outfit_select): outfit_select.select(0 if draft["outfit"] == "jersey" else 1)

func _update_feedback() -> void:
	if is_instance_valid(status_label): status_label.text = message if not message.is_empty() else ("创建生涯时会一并保存当前外观。" if creation_mode else "当前外观已保存。")
	if is_instance_valid(save_button):
		save_button.disabled = saving
		save_button.text = "保存中……" if saving else "保存外观"
	if is_instance_valid(outfit_select): outfit_select.disabled = saving
	for picker in pickers.values():
		if is_instance_valid(picker): (picker as ColorPickerButton).disabled = saving

func _apply_live() -> void:
	if is_instance_valid(preview_model): apply_model(preview_model, values())
	if creation_mode: return
	var host: Node = host_ref.get_ref() if host_ref != null else null
	if host == null: return
	for actor in host.get_tree().get_nodes_in_group("career_personal_avatar"):
		# NPCs use the same base controller, so only the controllable actor takes
		# an unsaved personal preview. The saved projection is applied on reload.
		if actor.has_method("apply_appearance"):
			actor.apply_appearance(values())

static func add_preview(parent: Node, appearance: Dictionary = {}, dimensions: Vector2 = Vector2(250, 285)) -> Node3D:
	var container := SubViewportContainer.new()
	container.name = "AppearancePreview"
	container.custom_minimum_size = dimensions
	container.stretch = true
	container.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(container)
	var viewport := SubViewport.new()
	viewport.size = Vector2i(dimensions)
	viewport.own_world_3d = true
	viewport.render_target_update_mode = SubViewport.UPDATE_WHEN_VISIBLE
	viewport.transparent_bg = false
	container.add_child(viewport)
	var environment := WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color("f0f0e3")
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color.WHITE
	environment.environment.ambient_light_energy = .65
	viewport.add_child(environment)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-35, -30, 0)
	light.light_energy = 1.2
	viewport.add_child(light)
	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 1.8
	camera.position = Vector3(2.0, 1.6, 3.8)
	viewport.add_child(camera)
	camera.look_at(Vector3(0, .72, 0))
	var model := (load("res://assets/player_chicken.glb") as PackedScene).instantiate() as Node3D
	model.name = "AvatarPreviewModel"
	model.scale = Vector3.ONE * .62
	model.rotation.y = -.15
	viewport.add_child(model)
	var stand := model.find_child("DisplayStand", true, false) as Node3D
	if stand: stand.visible = false
	apply_model(model, appearance)
	return model

static func apply_model(model: Node3D, appearance: Dictionary) -> void:
	var values := normalize(appearance)
	var uniform: bool = values["outfit"] == "jersey"
	var kit := model.find_child("PlayerKit", true, false) as Node3D
	if kit: kit.visible = uniform
	for node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh := node as MeshInstance3D
		var name_text := str(mesh.name).replace("_", " ").to_lower()
		var key := ""
		var lighten := 0.0
		if name_text.begins_with("cream belly bib"):
			mesh.visible = not uniform
			key = "belly_color"
		elif name_text.begins_with("pear shaped body") or name_text.begins_with("round chicken head") or name_text.begins_with("short wing"):
			key = "body_color"
		elif name_text.begins_with("tail feather") or name_text.begins_with("rounded feather tip"):
			key = "body_color"; lighten = .12
		elif name_text.begins_with("small tapered beak") or name_text.begins_with("lower beak") or name_text.begins_with("short shin") or name_text.begins_with("foot pad") or name_text.begins_with("chicken toe"):
			key = "beak_color"
		elif name_text.begins_with("comb lobe") or name_text.begins_with("small chicken wattle"):
			key = "comb_color"
			if name_text.begins_with("comb lobe 1"): lighten = .15
		elif name_text.begins_with("sleeveless team jersey"):
			key = "jersey_color"
		elif name_text.begins_with("jersey teal trim") or name_text.begins_with("jersey team label") or name_text.begins_with("headphone ear shell"):
			key = "trim_color"
		if key.is_empty(): continue
		# Save an untouched copy once. Mesh resources are shared with NPCs and
		# preview models, so every recolour uses an instance material override.
		if not mesh.has_meta("avatar_base_material"):
			var source := mesh.get_active_material(0)
			mesh.set_meta("avatar_base_material", source.duplicate() if source != null else StandardMaterial3D.new())
		var material := (mesh.get_meta("avatar_base_material") as Material).duplicate() as StandardMaterial3D
		if material == null: material = StandardMaterial3D.new()
		material.albedo_color = Color(str(values[key])).lightened(lighten)
		mesh.material_override = material
