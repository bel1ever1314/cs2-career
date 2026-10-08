extends Node3D
const Hud = preload("res://scripts/world_hud.gd")
const Player=preload("res://scripts/chicken_player.gd")
const Buildings = preload("res://scripts/scene_tiers.gd")
const Decor = preload("res://scripts/home_decor.gd")
const HomeRoom = preload("res://scripts/home_room.gd")
var decoration: Decor
var player: Player
var camera: Camera3D
var yaw:=.57
var pitch:=.72
var zoom:=9.8
var dragging:=false
var focused:=true
var prompt: Label
var time_label: Label
var model: Node3D
var target := ""
var sun: DirectionalLight3D
var env: Environment
var prompt_panel: PanelContainer
var help_panel: PanelContainer
var device_kind := ""
var device_seated := false
var device_approach := Vector3.ZERO
const COMPUTER_SEAT := Vector3(1.35,.52,-.91)
const COMPUTER_SCREEN := Vector3(1.41,1.58,-2.09)

func _ready() -> void:
	for action in {"club_up":KEY_W,"club_down":KEY_S,"club_left":KEY_A,"club_right":KEY_D,"club_run":KEY_SHIFT}:
		if InputMap.has_action(action):continue
		InputMap.add_action(action)
		var key:=InputEventKey.new(); key.physical_keycode={"club_up":KEY_W,"club_down":KEY_S,"club_left":KEY_A,"club_right":KEY_D,"club_run":KEY_SHIFT}[action]
		InputMap.action_add_event(action,key)
	model=(load("res://assets/cozy_room.glb") as PackedScene).instantiate(); add_child(model)
	HomeRoom.simplify(model)
	_box("Floor",Vector3(0,-.03,0),Vector3(6.7,.27,6.0))
	_box("BackWall",Vector3(0,1.3,-2.92),Vector3(6.7,2.6,.12))
	_box("LeftWall",Vector3(-3.3,1.3,0),Vector3(.12,2.6,6.0))
	_box("RightBoundary",Vector3(3.3,1,0),Vector3(.12,2,6.0))
	_box("FrontBoundary",Vector3(0,1,2.96),Vector3(6.7,2,.12))
	_box("Bed",Vector3(-2,.67,-.8),Vector3(1.84,1.1,2.85))
	_box("Nightstand",Vector3(-.65,.5,-1.94),Vector3(.65,.8,.65))
	_box("Desk",Vector3(1.4,.57,-2.01),Vector3(2.5,.92,.98))
	_box("Chair",Vector3(1.35,.60,-.94),Vector3(.7,.98,.68))
	var world:=WorldEnvironment.new(); env=Environment.new(); world.environment=env; add_child(world)
	env.background_mode=Environment.BG_COLOR; env.background_color=Color("bbc9b9")
	env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR; env.ambient_light_color=Color("fce7c5"); env.ambient_light_energy=.55
	env.tonemap_mode=Environment.TONE_MAPPER_ACES; env.ssao_enabled=true; env.ssao_radius=.5
	sun=DirectionalLight3D.new(); sun.rotation_degrees=Vector3(-58,-30,0); sun.light_color=Color("ffe8be"); sun.light_energy=.8; sun.shadow_enabled=true; add_child(sun)
	player=Player.new(); player.position=Vector3(-1.45,.12,1.35); player.home=player.position; add_child(player)
	camera=Camera3D.new(); camera.current=true; camera.projection=Camera3D.PROJECTION_ORTHOGONAL; camera.near=.1; camera.far=100; add_child(camera)
	camera.physics_interpolation_mode=Node.PHYSICS_INTERPOLATION_MODE_OFF
	_hud(); _camera()
	decoration=Decor.new(); add_child(decoration); decoration.setup(self)
	CareerBridge.changed.connect(_career_changed); _career_changed()
	if "--integration-test" in OS.get_cmdline_user_args() and not CareerBridge.has_meta("integration_started"):
		CareerBridge.set_meta("integration_started",true)
		var test=load("res://tests/career_integration_test.gd").new(); add_child(test); test.call_deferred("run")
	if "--redesign-integration-test" in OS.get_cmdline_user_args() and not CareerBridge.has_meta("redesign_test_started"):
		CareerBridge.set_meta("redesign_test_started",true)
		var test=load("res://tests/redesign_integration_test.gd").new();add_child(test);test.call_deferred("run")
	if "--travel-menu-test" in OS.get_cmdline_user_args() and not Travel.has_meta("menu_test_started"):
		Travel.set_meta("menu_test_started",true)
		var test=load("res://tests/travel_menu_test.gd").new();Travel.add_child(test);test.call_deferred("run")
	if "--capture-bedroom" in OS.get_cmdline_user_args():
		await get_tree().create_timer(3).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://renders/career_bedroom.png")
		Phone.present("calendar")
		await get_tree().create_timer(1).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://renders/career_phone.png")
		CareerBridge.quit()

func _box(id: String,pos: Vector3,size: Vector3) -> void:
	var body:=StaticBody3D.new(); body.name=id; body.position=pos; add_child(body)
	var collision:=CollisionShape3D.new(); var box:=BoxShape3D.new(); box.size=size; collision.shape=box; body.add_child(collision)

func _hud() -> void:
	var layer:=CanvasLayer.new(); layer.name="WorldHud"; add_child(layer)
	var root:=Control.new(); root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT); root.mouse_filter=Control.MOUSE_FILTER_IGNORE; layer.add_child(root)
	var top:=PanelContainer.new(); top.position=Vector2(25,24); root.add_child(top)
	var style:=Hud.glass(18,12)
	top.add_theme_stylebox_override("panel",style)
	var col:=VBoxContainer.new(); top.add_child(col)
	var label:=Label.new(); label.text="宿舍"; label.add_theme_font_size_override("font_size",18); col.add_child(label)
	time_label=Label.new(); time_label.add_theme_font_size_override("font_size",18); col.add_child(time_label)
	prompt_panel=PanelContainer.new();prompt_panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	prompt_panel.offset_left=-180;prompt_panel.offset_right=180;prompt_panel.offset_top=-88;prompt_panel.offset_bottom=-28
	prompt_panel.add_theme_stylebox_override("panel",style);prompt_panel.mouse_filter=Control.MOUSE_FILTER_IGNORE;root.add_child(prompt_panel)
	var stack:=VBoxContainer.new(); prompt_panel.add_child(stack)
	prompt=Label.new(); prompt.add_theme_font_size_override("font_size",21); stack.add_child(prompt)
	prompt.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	var row:=Hud.hint_bar(root)
	Hud.key_button(row,"P","手机",func():Phone.present())
	Hud.key_button(row,"F1","帮助",_toggle_help)
	Hud.key_button(row,"B","布置房间",func(): if not CareerBridge.phone_open and not Travel.busy: decoration.present())
	help_panel=PanelContainer.new();help_panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	help_panel.offset_left=-275;help_panel.offset_right=275;help_panel.offset_top=-165;help_panel.offset_bottom=165
	help_panel.add_theme_stylebox_override("panel",style);root.add_child(help_panel)
	var help_col:=VBoxContainer.new();help_col.add_theme_constant_override("separation",14);help_panel.add_child(help_col)
	var instructions:=Label.new();instructions.text="WASD / 方向键：走动\nShift：小跑；E：使用身边的物品\nP：打开手机；Esc：关闭\n右键拖动：旋转镜头；滚轮：缩放\n走到门口即可选择下一站，滚轮选择，E 出发。\n桌旁使用电脑，床边选择醒来的日期。";instructions.add_theme_font_size_override("font_size",18);help_col.add_child(instructions)
	var close:=Button.new();close.text="继续走动";close.focus_mode=Control.FOCUS_NONE;close.pressed.connect(_toggle_help);help_col.add_child(close)
	help_panel.visible=false

func _career_changed() -> void:
	if is_instance_valid(time_label):time_label.text=CareerBridge.clock_text()
	if is_instance_valid(model) and (not is_instance_valid(decoration) or not decoration.visible):
		var home: Dictionary = CareerBridge.context.get("environment",{}).get("home",{})
		Buildings.apply_home(self,model,home)
		if not device_seated: HomeRoom.clear_player(self,home)

func _camera() -> void:
	var focus:=Vector3(0,.65,0)
	camera.size=zoom; camera.position=focus+Vector3(sin(yaw)*cos(pitch),sin(pitch),cos(yaw)*cos(pitch))*30
	camera.look_at(focus,Vector3.UP)

func _physics_process(_delta: float) -> void:
	player.camera_yaw=yaw; player.enabled=focused and not CareerBridge.phone_open and not Travel.busy and not help_panel.visible
	target=""
	Travel.update_door("bedroom", _can_reach(Vector3(2.1,.12,2.2),1.3), focused and not CareerBridge.phone_open and not Travel.busy and not help_panel.visible)
	if CareerBridge.phone_open or Travel.busy or help_panel.visible:return
	var closest:=INF
	var targets: Dictionary={"club":{"anchor":Vector3(2.1,.12,2.2),"range":1.3},"sleep":{"anchor":Vector3(-1.5,.12,1.1),"range":1.2},"desk":{"anchor":Vector3(.4,.12,-1.2),"range":1.1}}
	for id in targets:
		var row: Dictionary=targets[id]
		var anchor: Vector3=row["anchor"]
		var distance:=Vector2(player.position.x-anchor.x,player.position.z-anchor.z).length()
		if distance>float(row["range"]) or distance>=closest:continue
		if not _can_reach(anchor,float(row["range"])):continue
		target=str(id);closest=distance

func _can_reach(anchor: Vector3, reach: float) -> bool:
	if Vector2(player.position.x-anchor.x,player.position.z-anchor.z).length()>reach:return false
	var origin:=player.position+Vector3(0,.65,0)
	var query:=PhysicsRayQueryParameters3D.create(origin,Vector3(anchor.x,origin.y,anchor.z),1)
	query.exclude=[player.get_rid()]
	return player.get_world_3d().direct_space_state.intersect_ray(query).is_empty()

func _process(_delta: float) -> void:
	time_label.text=CareerBridge.clock_text()
	prompt.text={"sleep":"E 睡觉","desk":"E 使用电脑"}.get(target,"")
	prompt_panel.visible=not prompt.text.is_empty() and not CareerBridge.phone_open and not Travel.busy and not help_panel.visible
	_camera()
	sun.light_energy=.8 if CareerBridge.clock_minutes<1080 else .25

func _unhandled_input(event: InputEvent) -> void:
	if CareerBridge.phone_open or Travel.busy:return
	if event is InputEventMouseButton:
		if event.button_index==MOUSE_BUTTON_RIGHT:dragging=event.pressed
		if event.pressed and not Travel.menu_open and event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN]:zoom=clampf(zoom*(.9 if event.button_index==MOUSE_BUTTON_WHEEL_UP else 1.1),7,14)
	if event is InputEventMouseMotion and dragging:yaw-=event.relative.x*.005; pitch=clampf(pitch+event.relative.y*.004,.45,1.2)
	if event is InputEventKey and event.pressed and not event.echo and event.physical_keycode==KEY_E:
		if help_panel.visible:return
		if target=="sleep":Phone.present("calendar")
		elif target=="desk":Computer.present("bedroom")
	if event is InputEventKey and event.pressed and not event.echo:
		if event.physical_keycode==KEY_F1:_toggle_help()
		elif event.physical_keycode==KEY_ESCAPE and help_panel.visible:_toggle_help()
		elif event.physical_keycode==KEY_B and not help_panel.visible and is_instance_valid(decoration) and not decoration.visible:decoration.present()

func before_phone() -> void:
	if is_instance_valid(decoration) and decoration.visible: decoration.close()
	Travel.close_menu()
	dragging=false;help_panel.visible=false;_leave_computer();player.velocity=Vector3.ZERO

func before_computer() -> void:
	if is_instance_valid(decoration) and decoration.visible: decoration.close()
	Travel.close_menu()
	dragging=false;help_panel.visible=false;player.velocity=Vector3.ZERO
	if not device_seated:
		device_approach=player.global_position;device_seated=true
		player.global_position=COMPUTER_SEAT;player.reset_physics_interpolation()
	player.seat_pose=true;player.face_toward(COMPUTER_SCREEN)

func set_phone_open(opened: bool) -> void:
	set_device_open(opened,"phone")

func set_device_open(opened: bool,kind: String) -> void:
	if not is_instance_valid(player):return
	var hud_layer:=get_node_or_null("WorldHud") as CanvasLayer
	# The editor owns P/Esc and its unsaved-draft prompt; HUD phone buttons must
	# not bypass that prompt by opening a different device underneath it.
	if hud_layer: hud_layer.visible=not opened
	if opened:
		device_kind=kind;player.locked=true;player.velocity=Vector3.ZERO
		if kind=="computer":
			before_computer();player.set_item_use(false);player.set_carried_item("");player.upper_body_action="typing"
		elif kind in ["sleep","decoration"]:
			_leave_computer();player.upper_body_action="";player.set_carried_item("");player.set_item_use(false)
		else:
			_leave_computer();player.upper_body_action="";player.set_carried_item("phone");player.set_item_use(true)
	else:
		_leave_computer();device_kind="";player.upper_body_action=""
		player.set_item_use(false);player.set_carried_item("");player.locked=false;player.velocity=Vector3.ZERO

func _leave_computer() -> void:
	if device_seated:
		player.global_position=device_approach;player.reset_physics_interpolation();device_seated=false
	player.seat_pose=false

func _toggle_help() -> void:
	help_panel.visible=not help_panel.visible;dragging=false;player.velocity=Vector3.ZERO
	if help_panel.visible:Travel.close_menu()

func _exit_tree() -> void:
	if is_instance_valid(player):_leave_computer();player.clear_presentation();player.locked=false

func _notification(what: int) -> void:
	if what==NOTIFICATION_APPLICATION_FOCUS_OUT:focused=false; dragging=false
	elif what==NOTIFICATION_APPLICATION_FOCUS_IN:focused=true
