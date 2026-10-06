extends Node3D
## Shared walking/presentation for the small career venues. Career state is read only.
const Player = preload("res://scripts/chicken_player.gd")
const UI = preload("res://scripts/phone_ui.gd")
const Hud = preload("res://scripts/world_hud.gd")
const Kit = preload("res://scripts/stage_kit.gd")
var player: Player
var camera: Camera3D
var settings: Dictionary = {}
var yaw := 0.0
var pitch := 0.0
var body_y := 0.0
var focused := true
var paused := false
var booted := false
var testing := false
var capturing := false
var device_kind := ""
var camera_owned := false
var camera_tween: Tween
var target := ""
var hint: Label
var status: Label
var caption: Label
var pause_panel: PanelContainer
var cursor_dot: Label
var title_parts: Dictionary = {}
var caption_parts: Dictionary = {}
var prompt_parts: Dictionary = {}
var shown_hint := "<unset>"
var env: Environment
var collision_count := 0
var materials: Dictionary = {}

func _ready() -> void:
	testing = "--venue-test" in OS.get_cmdline_user_args()
	capturing = "--venue-capture" in OS.get_cmdline_user_args()
	settings = JSON.parse_string(FileAccess.get_file_as_string(_data_path()))
	assert(settings.get("schema_version") == 1)
	_input_map()
	_environment()
	_build_venue()
	player = Player.new(); player.name = "VenueVisitor"
	player.position = vec(settings["spawn"]); player.home = player.position
	player.walk_speed = 3.1; player.run_speed = 4.7
	player.step_height = .21; player.floor_snap_length = .3; player.test_mode = testing
	add_child(player)
	player.visual.visible = false
	player.recovered.connect(func(): _set_caption("已回到场馆入口。"))
	camera = Camera3D.new(); camera.name = "VisitorCamera"; camera.current = true
	camera.physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_OFF
	camera.fov = 75; camera.near = .05; camera.far = 80
	camera.physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_OFF; add_child(camera)
	body_y = player.position.y
	_hud(); _venue_ready(); booted = true
	if not testing and not capturing: Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if testing:
		var suite = load("res://tests/small_venue_test.gd").new()
		add_child(suite); suite.call_deferred("run", self)
	elif capturing:
		await get_tree().create_timer(2).timeout
		_capture_view()
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://renders/" + _destination() + "_venue.png")
		print("VENUE_CAPTURE ", _destination(), " draws=", Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
		get_tree().quit()

func _destination() -> String: return ""
func _data_path() -> String: return ""
func _build_venue() -> void: pass
func _venue_ready() -> void: pass
func _update_venue(_delta: float) -> void: pass
func _nearest_target() -> String: return ""
func _hint_text() -> String: return "自由走动 · 沿门口通道返回"
func interact() -> void: pass
func _capture_view() -> void: pass

func vec(values: Array) -> Vector3: return Vector3(float(values[0]), float(values[1]), float(values[2]))

func _input_map() -> void:
	var actions: Dictionary = {"club_up":[KEY_W, KEY_UP], "club_down":[KEY_S, KEY_DOWN], "club_left":[KEY_A, KEY_LEFT], "club_right":[KEY_D, KEY_RIGHT], "club_run":[KEY_SHIFT]}
	for action in actions:
		if InputMap.has_action(action): continue
		InputMap.add_action(action)
		for key in actions[action]:
			var event := InputEventKey.new(); event.physical_keycode = key; InputMap.action_add_event(action, event)

func _environment() -> void:
	var world := WorldEnvironment.new(); env = Environment.new(); world.environment = env; add_child(world)
	env.background_mode = Environment.BG_COLOR; env.background_color = Color("080d17")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR; env.ambient_light_color = Color("aabccc")
	env.ambient_light_energy = .34; env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.ssao_enabled = true; env.ssao_radius = .5; env.ssao_intensity = .7
	env.glow_enabled = true; env.glow_intensity = .25
	_polish_environment()

## Venues override this to set their own bloom/haze/reflection profile.
func _polish_environment() -> void:
	Kit.polish(env,0.0,true)

func _material(color: Color, glow: float = 0.0) -> StandardMaterial3D:
	var key := color.to_html() + ":" + str(glow)
	if materials.has(key): return materials[key]
	var mat := StandardMaterial3D.new(); mat.albedo_color = color; mat.roughness = .76
	if glow > 0:
		mat.emission_enabled = true; mat.emission = color; mat.emission_energy_multiplier = glow
	materials[key] = mat; return mat

func _box(id: String, at: Vector3, size: Vector3, color: Color, solid: bool = false, glow: float = 0.0, parent: Node3D = null) -> MeshInstance3D:
	var mesh := MeshInstance3D.new(); mesh.name = id
	# Repeated siblings receive Godot-generated names. Keep the authored ID
	# for the LAN shell adapter without renaming nodes or changing collisions.
	mesh.set_meta("venue_authored_id",id)
	var shape := BoxMesh.new(); shape.size = size; mesh.mesh = shape; mesh.position = at
	mesh.material_override = _material(color, glow)
	var owner: Node3D = self if parent == null else parent; owner.add_child(mesh)
	if solid:
		var body := StaticBody3D.new(); body.name = id + "Collision"; body.position = at; owner.add_child(body)
		body.set_meta("venue_authored_id",id)
		var collision := CollisionShape3D.new(); var box := BoxShape3D.new(); box.size = size
		collision.shape = box; body.add_child(collision); collision_count += 1
	return mesh

func _cylinder(id: String, at: Vector3, radius: float, height: float, color: Color, parent: Node3D = null) -> MeshInstance3D:
	var mesh := MeshInstance3D.new(); mesh.name = id; mesh.position = at
	var cylinder := CylinderMesh.new(); cylinder.top_radius = radius; cylinder.bottom_radius = radius
	cylinder.height = height; cylinder.radial_segments = 16; mesh.mesh = cylinder
	mesh.material_override = _material(color); (self if parent == null else parent).add_child(mesh); return mesh

func _sign(text: String, at: Vector3, pixel_size: float = .003, angle: float = 0.0, color: Color = Color("f2ddb1"), parent: Node3D = null) -> Label3D:
	var label := Label3D.new(); label.text = text; label.font = UI.font()
	label.font_size = 50; label.pixel_size = pixel_size; label.position = at; label.rotation.y = angle
	label.modulate = color; label.outline_size = 6; label.no_depth_test = false
	(self if parent == null else parent).add_child(label); return label

func _spot(id: String, at: Vector3, focus: Vector3, color: Color, energy: float, spread: float = 42.0) -> SpotLight3D:
	var light := SpotLight3D.new(); light.name = id; light.position = at
	light.light_color = color; light.light_energy = energy; light.spot_range = 14; light.spot_angle = spread; light.spot_attenuation = .5
	light.shadow_enabled = true; add_child(light); light.look_at(focus, Vector3.FORWARD if absf(at.x-focus.x)+absf(at.z-focus.z)<.01 else Vector3.UP)
	return light

func _fill(id: String, at: Vector3, color: Color, energy: float, reach: float) -> OmniLight3D:
	# Large soft pools illuminate faces and furniture outside the narrow key beams.
	var light := OmniLight3D.new(); light.name = id; light.position = at
	light.light_color = color; light.light_energy = energy; light.omni_range = reach; light.omni_attenuation = .65
	light.shadow_enabled = false; light.light_volumetric_fog_energy = 0.0; add_child(light); return light

func _enclosure(width: float, depth: float, height: float) -> void:
	_box("Floor", Vector3(0,-.12,0), Vector3(width,.24,depth), Color("18222b"), true)
	_box("BackWall", Vector3(0,height*.5,-depth*.5), Vector3(width,height,.18), Color("101923"), true)
	_box("EntryWall", Vector3(0,height*.5,depth*.5), Vector3(width,height,.18), Color("101923"), true)
	for side in [-1.0,1.0]:
		_box("SideWall", Vector3(side*width*.5,height*.5,0), Vector3(.18,height,depth), Color("1b2530"), true)
	_box("ClosedCeiling", Vector3(0,height+.09,0), Vector3(width,.18,depth), Color("0d151e"), true)
	var door := vec(settings["door"])
	_box("ExitDoor", Vector3(door.x,1.18,depth*.5-.12), Vector3(1.7,2.36,.10), Color("31414a"))
	_box("DoorWindow", Vector3(door.x,1.58,depth*.5-.18), Vector3(.85,.58,.025), Color("89aa9e"), false, .22)
	_sign("出口 / 下一站", Vector3(door.x,2.62,depth*.5-.23), .0034, PI)
	_box("DoorHandle", Vector3(door.x+.61,1.02,depth*.5-.21), Vector3(.07,.28,.08), Color("c6ad77"))

func _trophy(id: String, parent: Node3D, scale_value: float = 1.0) -> Node3D:
	var trophy := Node3D.new(); trophy.name = id; trophy.scale = Vector3.ONE*scale_value; parent.add_child(trophy)
	_box("AwardBase", Vector3(0,.04,0), Vector3(.34,.08,.25), Color("15232c"), false, 0, trophy)
	_cylinder("GoldStem", Vector3(0,.24,0), .038,.34,Color("d4af69"),trophy)
	var cup := _cylinder("GoldenCup",Vector3(0,.5,0),.13,.19,Color("ddbd7e"),trophy)
	(cup.mesh as CylinderMesh).bottom_radius = .068
	for side in [-1.0,1.0]:
		var ring := MeshInstance3D.new(); var shape := TorusMesh.new(); shape.inner_radius = .068; shape.outer_radius = .096
		ring.mesh = shape; ring.rotation.x = PI*.5; ring.position = Vector3(side*.13,.5,0); ring.material_override = _material(Color("d4af69")); trophy.add_child(ring)
	return trophy

func _hud() -> void:
	# Same glass HUD as the club and dorm: title card, subtitle-style captions,
	# a keycap prompt under the crosshair and a compact key bar.
	var layer := CanvasLayer.new(); layer.name = "WorldHud"; add_child(layer)
	var root := Control.new(); root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT); root.mouse_filter = Control.MOUSE_FILTER_IGNORE; layer.add_child(root)
	title_parts = Hud.title_card(root,str(settings["title"]))
	status = title_parts["status"]
	caption_parts = Hud.caption_pill(root)
	caption = caption_parts["label"]
	prompt_parts = Hud.prompt(root)
	# The live hint text stays on one Label for scene code; _sync_hint routes it.
	hint = Label.new(); hint.visible = false; root.add_child(hint)
	var row := Hud.hint_bar(root)
	Hud.key_hint(row,"WASD","走动")
	Hud.key_hint(row,"Shift","小跑")
	Hud.key_hint(row,"E","交互")
	Hud.key_button(row,"P","手机",func(): if not CareerBridge.phone_open and not Travel.busy: Phone.present())
	Hud.key_button(row,"Esc","菜单",func(): set_paused(not paused))
	cursor_dot = Hud.text(root,"•",14,Color(1,1,1,.8)); cursor_dot.set_anchors_and_offsets_preset(Control.PRESET_CENTER); cursor_dot.offset_left = -4; cursor_dot.offset_top = -10
	var pause := Hud.pause_menu(root,str(settings["title"]),"走到出口可选择下一站。\nP 手机可随时查看当前生涯。")
	pause_panel = pause["panel"]
	Hud.menu_button(pause["menu"],"继续走动",func(): set_paused(false),true)
	Hud.menu_button(pause["menu"],"返回俱乐部",func(): Travel.go("club"))
	pause_panel.visible = false

func _sync_hint() -> void:
	if hint.text == shown_hint: return
	shown_hint = hint.text
	var objective: Label = title_parts["objective"]
	var active := Hud.set_prompt(prompt_parts,hint.text)
	objective.text = "" if active else hint.text
	objective.visible = not objective.text.is_empty()

func _label(parent: Node, text: String, size: int) -> Label:
	var label := Label.new(); label.text = text; label.add_theme_font_override("font",UI.font()); label.add_theme_font_size_override("font_size",size)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE; parent.add_child(label); return label

func _set_caption(text: String) -> void:
	if is_instance_valid(caption):
		caption.text = text
		Hud.fit_caption(caption_parts)

func _distance(point: Vector3) -> float:
	return Vector2(player.position.x-point.x,player.position.z-point.z).length()

func _reachable(point: Vector3, radius: float) -> bool:
	if _distance(point)>radius: return false
	var eye := player.position+Vector3.UP*.85
	var query := PhysicsRayQueryParameters3D.create(eye,Vector3(point.x,eye.y,point.z),1); query.exclude = [player.get_rid()]
	return get_world_3d().direct_space_state.intersect_ray(query).is_empty()

func _physics_process(_delta: float) -> void:
	if not booted: return
	player.camera_yaw = yaw
	player.enabled = not paused and not camera_owned and not Travel.busy and not CareerBridge.phone_open and (focused or testing or capturing)
	target = _nearest_target() if player.enabled else ""
	Travel.update_door(_destination(),_distance(vec(settings["door"]))<float(settings.get("door_range",1.25)),player.enabled)

func _process(delta: float) -> void:
	if not booted: return
	var p := player.get_global_transform_interpolated().origin
	body_y = lerpf(body_y,p.y,1-exp(-16*delta))
	if not camera_owned:
		camera.position = Vector3(p.x,body_y+float(settings.get("eye_height",1.34)),p.z); camera.rotation = Vector3(pitch,yaw,0)
	hint.text = _hint_text()
	if _distance(vec(settings["door"]))<float(settings.get("door_range",1.25)): hint.text = "门口可选择下一站 · 可直接走开"
	cursor_dot.visible = not paused and not CareerBridge.phone_open
	_sync_hint()
	_update_venue(delta)

func set_paused(value: bool) -> void:
	paused = value; pause_panel.visible = value; player.velocity = Vector3.ZERO
	if value: Travel.close_menu()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if value or CareerBridge.phone_open else Input.MOUSE_MODE_CAPTURED

func before_phone() -> void:
	Travel.close_menu(); player.velocity = Vector3.ZERO

func before_computer() -> void:
	Travel.close_menu(); player.velocity = Vector3.ZERO

func set_phone_open(value: bool) -> void: set_device_open(value,"phone")

func set_device_open(value: bool, kind: String) -> void:
	var hud_layer := get_node_or_null("WorldHud") as CanvasLayer
	if hud_layer: hud_layer.visible = not value
	device_kind = kind if value else ""; player.locked = value; player.velocity = Vector3.ZERO
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if value or paused else Input.MOUSE_MODE_CAPTURED

func _unhandled_input(event: InputEvent) -> void:
	if not booted or Travel.busy or CareerBridge.phone_open: return
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED and not paused and not camera_owned:
		yaw -= event.relative.x*.0024; pitch = clampf(pitch-event.relative.y*.0024,-1.35,1.35)
	if event is InputEventKey and event.pressed and not event.echo:
		if event.physical_keycode == KEY_ESCAPE: set_paused(not paused)
		elif event.physical_keycode == KEY_E and not paused: interact()

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		focused = false
		if booted and not testing and not capturing: set_paused(true)
	elif what == NOTIFICATION_APPLICATION_FOCUS_IN: focused = true

func _exit_tree() -> void:
	if camera_tween and camera_tween.is_valid(): camera_tween.kill()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
