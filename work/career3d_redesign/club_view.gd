extends Node3D
## Independent visual prototype: no career save access and no gameplay writes.
## Model coordinates converted by GLB: Blender Z-up -> Godot Y-up.
var camera: Camera3D
var environment: Environment
var sun: DirectionalLight3D
var warm_lights: Array[OmniLight3D] = []
var yaw := 0.52
var elevation := 0.77
var zoom := 33.5
var focus := Vector3(0, 0.8, 0)
var dragging := false
var rotating := false
var evening := false
var preset := 0
var status: Label
var buttons: Array[Button] = []
var light_button: Button

const VIEWS = [
	{"title": "全馆", "focus": Vector3(0, 0.8, 0), "zoom": 33.5, "yaw": .52, "elevation": .77,
	 "note": "前排：休息区 / 大厅 / 食堂；后排：训练室 / 会议室 / 厨房"},
	{"title": "大厅", "focus": Vector3(-.6, 1.2, 4.6), "zoom": 10.8, "yaw": .25, "elevation": .67,
	 "note": "接待台、奖杯陈列和入场门厅；走廊连接六个区域"},
	{"title": "训练室", "focus": Vector3(-7.12, 1.25, -5.2), "zoom": 11.8, "yaw": .24, "elevation": .64,
	 "note": "五套训练设备、队友席位、教练工作台与训练日程"},
	{"title": "会议室", "focus": Vector3(1, 1.2, -5.0), "zoom": 8.5, "yaw": .25, "elevation": .70,
	 "note": "六人复盘桌和战术白板，独立于日常训练区"},
	{"title": "厨房", "focus": Vector3(8.0, 1.25, -5.4), "zoom": 10.3, "yaw": .28, "elevation": .78,
	 "note": "备餐岛台、水槽、灶台、冰箱和储物柜"},
	{"title": "食堂", "focus": Vector3(7.5, 1.0, 4.6), "zoom": 11.0, "yaw": .25, "elevation": .77,
	 "note": "八人餐桌、咖啡机与饮水区，厨房经走廊可达"},
	{"title": "休息区", "focus": Vector3(-8.25, 1.05, 4.8), "zoom": 10.0, "yaw": -.40, "elevation": .73,
	 "note": "沙发、电视和茶几：训练结束后休息聊天的地方"}
]

func _ready() -> void:
	var packed := load("res://assets/chicken_club.glb") as PackedScene
	if packed == null:
		push_error("俱乐部模型缺失，请先运行建模脚本。")
		return
	add_child(packed.instantiate())
	var world := WorldEnvironment.new()
	environment = Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("b6c5b9")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color("f7ecd7")
	environment.ambient_light_energy = .40
	environment.tonemap_mode = Environment.TONE_MAPPER_ACES
	environment.ssao_enabled = true
	environment.ssao_radius = .70
	environment.ssao_intensity = 1.15
	environment.ssao_power = 1.3
	environment.glow_enabled = true
	environment.glow_intensity = .18
	world.environment = environment
	add_child(world)
	sun = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-62, -25, 0)
	sun.light_color = Color("fff0d5")
	sun.light_energy = .75
	sun.shadow_enabled = true
	sun.light_angular_distance = 2.0
	sun.directional_shadow_max_distance = 75.0
	add_child(sun)
	for pos in [Vector3(-7,3.8,-5),Vector3(1,3.8,-5),Vector3(8,3.8,-5),Vector3(-8,3.8,5),Vector3(-.5,3.8,5),Vector3(8,3.8,5)]:
		var light := OmniLight3D.new()
		light.position = pos
		light.omni_range = 9.0
		light.light_color = Color("ffe5bd")
		light.light_energy = .12
		add_child(light)
		warm_lights.append(light)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(250,250)
	ground.mesh = plane
	ground.position.y = -.47
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color("b6c5b9")
	mat.roughness = 1
	ground.material_override = mat
	add_child(ground)
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.near = .1
	camera.far = 220
	camera.current = true
	add_child(camera)
	_ui()
	_set_view(0)
	var args := OS.get_cmdline_user_args()
	if "--training" in args:
		_set_view(2)
	if "--kitchen" in args:
		_set_view(4)
	if "--evening" in args:
		_toggle_light()
	if "--capture" in args:
		await get_tree().create_timer(4).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://renders/godot_" + str(preset) + ("_evening" if evening else "") + ".png")
		print("CLUB_RUNTIME_OK preset=",preset," fps=",Engine.get_frames_per_second()," draws=",Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
		get_tree().quit()

func _ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var root := Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(root)
	var panel := PanelContainer.new()
	panel.position = Vector2(25,22)
	root.add_child(panel)
	var style := StyleBoxFlat.new()
	style.bg_color = Color(.10,.19,.19,.93)
	style.corner_radius_top_left = 14
	style.corner_radius_top_right = 14
	style.corner_radius_bottom_left = 14
	style.corner_radius_bottom_right = 14
	style.content_margin_left = 19
	style.content_margin_right = 19
	style.content_margin_top = 13
	style.content_margin_bottom = 13
	panel.add_theme_stylebox_override("panel",style)
	var col := VBoxContainer.new()
	panel.add_child(col)
	var title := Label.new()
	title.text = "ROOKIE CLUB / 小鸡电竞俱乐部"
	title.add_theme_font_size_override("font_size",25)
	col.add_child(title)
	status = Label.new()
	status.add_theme_font_size_override("font_size",15)
	status.modulate = Color("d4dcc6")
	col.add_child(status)
	var disclaimer := Label.new()
	disclaimer.text = "可旋转空间原型 · 暂未接入角色行走及生涯交互"
	disclaimer.add_theme_font_size_override("font_size",13)
	disclaimer.modulate = Color("aabfb3")
	col.add_child(disclaimer)
	var footer := Panel.new()
	root.add_child(footer)
	footer.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	footer.offset_top = -104
	footer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var footer_style := StyleBoxFlat.new()
	footer_style.bg_color = Color(.10,.19,.19,.93)
	footer.add_theme_stylebox_override("panel",footer_style)
	var row := HBoxContainer.new()
	root.add_child(row)
	row.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	row.offset_left = 26
	row.offset_top = -62
	row.offset_bottom = -17
	row.add_theme_constant_override("separation",8)
	for i in range(VIEWS.size()):
		var button := Button.new()
		button.text = str(i+1) + " " + str(VIEWS[i]["title"])
		button.custom_minimum_size = Vector2(118,44)
		button.focus_mode = Control.FOCUS_NONE
		button.toggle_mode = true
		button.pressed.connect(_set_view.bind(i))
		row.add_child(button)
		buttons.append(button)
	light_button = Button.new()
	light_button.text = "N 傍晚灯光"
	light_button.custom_minimum_size = Vector2(140,44)
	light_button.focus_mode = Control.FOCUS_NONE
	light_button.pressed.connect(_toggle_light)
	row.add_child(light_button)
	var hint := Label.new()
	root.add_child(hint)
	hint.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	hint.offset_left = 28
	hint.offset_top = -94
	hint.text = "左键旋转 · 右键平移 · 滚轮缩放 · 1—7 查看房间 · R 重置 · 空格自动环绕"
	hint.add_theme_font_size_override("font_size",16)
	hint.modulate = Color("d4dcc6")

func _set_view(index: int) -> void:
	preset = index
	rotating = false
	focus = VIEWS[index]["focus"]
	zoom = VIEWS[index]["zoom"]
	yaw = VIEWS[index]["yaw"]
	elevation = VIEWS[index]["elevation"]
	status.text = VIEWS[index]["note"]
	for i in range(buttons.size()):
		buttons[i].set_pressed_no_signal(i==index)
	_update_camera()

func _update_camera() -> void:
	camera.size = zoom
	camera.position = focus + Vector3(sin(yaw)*cos(elevation),sin(elevation),cos(yaw)*cos(elevation))*65
	camera.look_at(focus,Vector3.UP)

func _process(delta: float) -> void:
	if rotating:
		yaw += delta*.16
		_update_camera()

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index==MOUSE_BUTTON_LEFT:
			dragging=event.pressed
		if event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN]:
			zoom=clampf(zoom*(.9 if event.button_index==MOUSE_BUTTON_WHEEL_UP else 1.1),4,48)
			_update_camera()
	if event is InputEventMouseMotion:
		if dragging:
			yaw-=event.relative.x*.005
			elevation=clampf(elevation+event.relative.y*.004,.16,1.47)
			_update_camera()
		elif Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
			focus+=(-camera.global_basis.x*event.relative.x+camera.global_basis.y*event.relative.y)*zoom*.001
			_update_camera()
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode>=KEY_1 and event.keycode<=KEY_7:
			_set_view(event.keycode-KEY_1)
		elif event.keycode==KEY_R:
			_set_view(preset)
		elif event.keycode==KEY_SPACE:
			rotating=not rotating
		elif event.keycode==KEY_N:
			_toggle_light()

func _toggle_light() -> void:
	evening=not evening
	sun.light_energy=.20 if evening else .75
	environment.ambient_light_energy=.28 if evening else .40
	for light in warm_lights:
		light.light_energy=1.30 if evening else .12
	light_button.text="N 日间灯光" if evening else "N 傍晚灯光"
