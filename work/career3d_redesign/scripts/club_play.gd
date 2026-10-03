extends Node3D
const Player = preload("res://scripts/chicken_player.gd")
const Interactions = preload("res://scripts/club_interactions.gd")
const CollisionBuilder = preload("res://scripts/club_collision.gd")
const ClubLife = preload("res://scripts/club_life.gd")
const Dialogue = preload("res://scripts/npc_dialogue.gd")
const ClubBoard = preload("res://scripts/club_notice_board.gd")
const TrophyDisplay = preload("res://scripts/club_trophy_display.gd")
const SceneTiers = preload("res://scripts/scene_tiers.gd")
var club_board: ClubBoard
var trophy_display: TrophyDisplay
var life: ClubLife
var dialogue: Dialogue
var player: Player
var interactions: Interactions
var model: Node3D
var camera: Camera3D
var sun: DirectionalLight3D
var environment: Environment
var camera_yaw := .28
var camera_pitch := .78
var camera_zoom := 12.6
var camera_focus := Vector3.ZERO
var overview := false
var dragging := false
var evening := false
var focused := true
var warm_lights: Array[OmniLight3D] = []
var fridge_pivot: Node3D
var fridge_tween: Tween
var prompt_panel: PanelContainer
var prompt_label: Label
var action_progress: ProgressBar
var action_label: Label
var toast_label: Label
var toast_panel: PanelContainer
var toast_seconds := 0.0
var stats_label: Label
var room_label: Label
var help_panel: PanelContainer
var controls_root: Control
var collision_builder: RefCounted
var room_previous := ""
var booted := false
var testing := false
var warm_elapsed := 0.0
var computer_display: MeshInstance3D
var overheads: Array[MeshInstance3D] = []
var device_kind := ""
var environment_tier := "academy"

func _ready() -> void:
	testing = "--test" in OS.get_cmdline_user_args()
	_input_map()
	model = (load("res://assets/chicken_club.glb") as PackedScene).instantiate() as Node3D
	add_child(model)
	_prepare_living_layout()
	collision_builder = CollisionBuilder.new()
	collision_builder.build(self,model)
	_environment()
	player = Player.new()
	player.name = "ControllableChicken"
	player.position = Vector3(-.75,.23,6.65)
	player.test_mode = testing
	add_child(player)
	player.recovered.connect(func(): _toast("已回到大厅。"))
	interactions = Interactions.new()
	interactions.name = "LocalInteractions"
	add_child(interactions)
	interactions.configure(player)
	if not Travel.club_session.is_empty():
		interactions.values=Travel.club_session["values"].duplicate()
		interactions.cooldowns=Travel.club_session["cooldowns"].duplicate()
		interactions.cooldown_clock=float(Travel.club_session["clock"])
		interactions.completed=Travel.club_session["completed"].duplicate()
	interactions.message.connect(_toast)
	interactions.stats_changed.connect(_update_stats)
	interactions.action_started.connect(_action_started)
	interactions.action_completed.connect(_action_completed)
	interactions.action_cancelled.connect(_action_cancelled)
	_prepare_props()
	_hud()
	club_board = ClubBoard.new(); club_board.name = "ClubNoticeBoard"; add_child(club_board)
	trophy_display = TrophyDisplay.new(); trophy_display.name = "ClubTrophyDisplay"; add_child(trophy_display)
	trophy_display.setup(model)
	life=ClubLife.new();life.name="ClubLife";add_child(life)
	life.setup(player,collision_builder.audit,Travel.club_session.get("npcs",{}))
	player.collision_mask=5
	dialogue=Dialogue.new();add_child(dialogue);dialogue.setup(life)
	CareerBridge.changed.connect(_career_changed)
	_career_changed()
	if testing:
		life.enabled=false;life.process_mode=Node.PROCESS_MODE_DISABLED
		for npc in life.roster:npc.collision_layer=0
	_update_stats()
	camera_focus = player.position+Vector3(0,.68,0)
	_camera_update(1.0,true)
	booted = true
	if Travel.returning:_toast("欢迎回来。",2)
	if "--travel-test" in OS.get_cmdline_user_args() and not Travel.has_meta("test_started"):
		Travel.set_meta("test_started",true)
		var suite=load("res://tests/travel_smoke_test.gd").new()
		Travel.add_child(suite);suite.call_deferred("run")
	if testing:
		var suite = load("res://tests/club_smoke_test.gd").new()
		add_child(suite)
		suite.call_deferred("run",self)
	elif "--club-honours-world-test" in OS.get_cmdline_user_args():
		var suite = load("res://tests/club_honours_world_test.gd").new(); add_child(suite); suite.call_deferred("run", self)
	elif "--club-input-test" in OS.get_cmdline_user_args():
		var suite=load("res://tests/club_input_test.gd").new();Travel.add_child(suite);suite.call_deferred("run",self)
	elif "--carry-test" in OS.get_cmdline_user_args():
		player.test_mode=true
		var suite=load("res://tests/carried_items_test.gd").new();add_child(suite);suite.call_deferred("run",self)
	elif "--carry-capture" in OS.get_cmdline_user_args():
		player.test_mode=true;life.enabled=false;camera_zoom=5.8
		player.set_carried_item("notebook");player.set_item_use(true)
		await get_tree().create_timer(.6).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://renders/carried_notebook.png")
		player.set_carried_item("phone");player.set_item_use(true)
		await get_tree().create_timer(.6).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://renders/carried_phone.png")
		player.set_carried_item("laptop");player.set_item_use(true);camera_yaw=.55;camera_pitch=.93
		await get_tree().create_timer(.6).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://renders/carried_laptop.png")
		print("CARRY_CAPTURE_DONE")
		get_tree().quit()
	elif "--npc-test" in OS.get_cmdline_user_args():
		player.test_mode=true
		var suite=load("res://tests/npc_life_test.gd").new();add_child(suite);suite.call_deferred("run",self)
	elif "--npc-capture" in OS.get_cmdline_user_args():
		await get_tree().create_timer(5).timeout
		player.position=Vector3(-5.8,.23,7.6);player.reset_physics_interpolation()
		life.begin(life.roster[5])
		await get_tree().create_timer(1).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://renders/npc_conversation.png")
		print("NPC_CAPTURE fps=",Engine.get_frames_per_second())
		get_tree().quit()
	elif "--capture" in OS.get_cmdline_user_args():
		if "--overview" in OS.get_cmdline_user_args(): overview=true
		if "--rest" in OS.get_cmdline_user_args():
			player.position=Vector3(-8.44,.23,4.08)
			await get_tree().physics_frame
			interactions.start(interactions.items[5])
		await get_tree().create_timer(3.0).timeout
		await RenderingServer.frame_post_draw
		var suffix: String="rest" if "--rest" in OS.get_cmdline_user_args() else ("overview" if overview else "entrance")
		get_viewport().get_texture().get_image().save_png("res://renders/play_"+suffix+".png")
		print("CLUB_PLAY_CAPTURE fps=",Engine.get_frames_per_second())
		get_tree().quit()

func _input_map() -> void:
	var bindings := {"club_up":[KEY_W,KEY_UP],"club_down":[KEY_S,KEY_DOWN],
		"club_left":[KEY_A,KEY_LEFT],"club_right":[KEY_D,KEY_RIGHT],"club_run":[KEY_SHIFT]}
	for action in bindings:
		if InputMap.has_action(action):continue
		InputMap.add_action(action)
		for key in bindings[action]:
			var event := InputEventKey.new()
			event.physical_keycode = key
			InputMap.action_add_event(action,event)

func _prepare_living_layout() -> void:
	# Static sculpted chickens are replaced, not duplicated. The source GLB
	# remains unchanged for the model-only viewer.
	var prefixes: Array[String]=["player01 ","player02 ","player03 ","player04 ","player05 ","chef ","receptionist ","lounge teammate ","dining teammate "]
	for node in model.find_children("*","MeshInstance3D",true,false):
		var n:=str(node.name).replace("_"," ").to_lower()
		var is_actor:=false
		for prefix in prefixes:
			if n.begins_with(prefix):node.visible=false;is_actor=true;break
		if is_actor:continue
		var p: Vector3=node.global_position
		# The old presentation desk nearly touched both walls. Compress its
		# five workstation positions slightly to create a usable side aisle.
		if p.x< -2.5 and p.z< -4.15 and p.z> -6.42:
			var furniture:=false
			for token in ["desktop","desk modesty","desk supporting","gaming monitor","monitor","mousepad","keyboard","keycap","mouse","pc case","pc cooling","chair","coffee mug","coffee surface","mug handle","player station"]:
				if token in n:furniture=true;break
			if furniture:
				p.x=-7.32+(p.x+7.12)*.90;node.global_position=p
				if "desktop" in n or "desk modesty" in n:node.scale.x*=.90

func _environment() -> void:
	var world := WorldEnvironment.new()
	environment = Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("b6c5b9")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color("f7ecd7")
	environment.ambient_light_energy = .40
	environment.tonemap_mode = Environment.TONE_MAPPER_ACES
	environment.ssao_enabled = true
	environment.ssao_radius = .60
	environment.ssao_intensity = 1.1
	world.environment = environment
	add_child(world)
	sun = DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-62,-25,0)
	sun.light_color = Color("fff0d5")
	sun.light_energy = .75
	sun.shadow_enabled = true
	sun.light_angular_distance = 2
	sun.directional_shadow_max_distance = 85
	add_child(sun)
	for pos in [Vector3(-7,3.8,-5),Vector3(1,3.8,-5),Vector3(8,3.8,-5),Vector3(-8,3.8,5),Vector3(-.5,3.8,5),Vector3(8,3.8,5)]:
		var light := OmniLight3D.new()
		light.position=pos; light.omni_range=9; light.light_color=Color("ffe5bd"); light.light_energy=.12
		add_child(light); warm_lights.append(light)
	var ground := MeshInstance3D.new()
	var plane := PlaneMesh.new(); plane.size=Vector2(250,250); ground.mesh=plane
	ground.position.y=-.47
	var mat:=StandardMaterial3D.new(); mat.albedo_color=Color("b6c5b9"); mat.roughness=1
	ground.material_override=mat; add_child(ground)
	camera=Camera3D.new(); camera.projection=Camera3D.PROJECTION_ORTHOGONAL
	camera.near=.1; camera.far=200; camera.current=true; add_child(camera)

func _prepare_props() -> void:
	for node in model.find_children("*","MeshInstance3D",true,false):
		var mesh := node as MeshInstance3D
		var normalized := str(mesh.name).replace("_"," ").to_lower()
		if normalized in ["entrance overhead sign","entry sign text"] or normalized.ends_with(" oak lintel") or normalized in ["training sign","training text","tactics sign","tactics text","kitchen sign","kitchen text","lounge sign","lounge text","dining sign","dining text"]:
			overheads.append(mesh)
		if normalized=="fridge door":
			var bounds: AABB = mesh.global_transform*mesh.get_aabb()
			fridge_pivot=Node3D.new(); fridge_pivot.name="FridgeHinge"; add_child(fridge_pivot)
			fridge_pivot.global_position=Vector3(bounds.position.x,bounds.get_center().y,bounds.get_center().z)
			mesh.reparent(fridge_pivot,true)
		if normalized.begins_with("monitor lit display"):
			if mesh.global_position.x>-4.2: computer_display=mesh

func _style(color: Color) -> StyleBoxFlat:
	var style:=StyleBoxFlat.new(); style.bg_color=color
	style.corner_radius_top_left=12; style.corner_radius_top_right=12
	style.corner_radius_bottom_left=12; style.corner_radius_bottom_right=12
	style.content_margin_left=18; style.content_margin_right=18
	style.content_margin_top=12; style.content_margin_bottom=12
	return style

func _text(parent: Node,value: String,size: int=17) -> Label:
	var label:=Label.new(); label.text=value; label.add_theme_font_size_override("font_size",size)
	parent.add_child(label); return label

func _hud() -> void:
	var canvas:=CanvasLayer.new(); add_child(canvas)
	controls_root=Control.new(); controls_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	controls_root.mouse_filter=Control.MOUSE_FILTER_IGNORE; canvas.add_child(controls_root)
	var top:=PanelContainer.new(); top.position=Vector2(24,22)
	top.add_theme_stylebox_override("panel",_style(Color(.10,.19,.19,.94))); controls_root.add_child(top)
	var col:=VBoxContainer.new(); top.add_child(col)
	room_label=_text(col,"大厅",18)
	stats_label=_text(col,"",16); stats_label.modulate=Color("e6d6a9")
	prompt_panel=PanelContainer.new(); controls_root.add_child(prompt_panel)
	prompt_panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	prompt_panel.offset_left=-185;prompt_panel.offset_right=185;prompt_panel.offset_top=-108;prompt_panel.offset_bottom=-28
	prompt_panel.mouse_filter=Control.MOUSE_FILTER_IGNORE
	prompt_panel.add_theme_stylebox_override("panel",_style(Color(.10,.19,.19,.95)))
	var stack:=VBoxContainer.new(); prompt_panel.add_child(stack)
	prompt_label=_text(stack,"",20);prompt_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	action_progress=ProgressBar.new(); action_progress.custom_minimum_size.y=7; action_progress.show_percentage=false
	action_progress.max_value=1.0; stack.add_child(action_progress); action_progress.visible=false
	action_label=_text(stack,"",15)
	var shortcuts:=PanelContainer.new();controls_root.add_child(shortcuts)
	shortcuts.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	shortcuts.offset_left=-260;shortcuts.offset_right=-24;shortcuts.offset_top=-75;shortcuts.offset_bottom=-24
	shortcuts.add_theme_stylebox_override("panel",_style(Color(.10,.19,.19,.95)))
	var row:=HBoxContainer.new(); row.add_theme_constant_override("separation",10); shortcuts.add_child(row)
	var phone_button:=Button.new(); phone_button.text="P 手机"; phone_button.pressed.connect(func():Phone.present()); row.add_child(phone_button)
	phone_button.focus_mode=Control.FOCUS_NONE
	var help_button:=Button.new(); help_button.text="F1 帮助"; help_button.focus_mode=Control.FOCUS_NONE
	help_button.pressed.connect(_toggle_help); row.add_child(help_button)
	toast_panel=PanelContainer.new(); controls_root.add_child(toast_panel)
	toast_panel.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
	toast_panel.offset_left=-455; toast_panel.offset_right=-24; toast_panel.offset_top=22; toast_panel.offset_bottom=140
	toast_panel.add_theme_stylebox_override("panel",_style(Color(.97,.92,.79,.97)))
	toast_panel.mouse_filter=Control.MOUSE_FILTER_IGNORE
	toast_label=Label.new(); toast_label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	toast_label.custom_minimum_size=Vector2(390,70); toast_label.add_theme_font_size_override("font_size",17)
	toast_label.add_theme_color_override("font_color",Color("284640")); toast_panel.add_child(toast_label)
	help_panel=PanelContainer.new(); controls_root.add_child(help_panel)
	help_panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	help_panel.offset_left=-295; help_panel.offset_right=295; help_panel.offset_top=-195; help_panel.offset_bottom=195
	help_panel.add_theme_stylebox_override("panel",_style(Color(.10,.19,.19,.98)))
	var helpcol:=VBoxContainer.new(); helpcol.add_theme_constant_override("separation",14); help_panel.add_child(helpcol)
	_text(helpcol,"先在俱乐部里逛逛",26)
	_text(helpcol,"WASD / 方向键：相对画面方向移动\nShift：小跑；E：与最近的可达物品交互\n右键拖动：旋转镜头；滚轮：缩放\nTab：全馆鸟瞰 / 角色跟随；R：镜头复位\nN：日间 / 傍晚；Esc：停止动作或关闭帮助",18)
	_text(helpcol,"靠近小鸡按 F 聊天，1—4 选择话题，Esc 告别。\n战术白板旁按 E 翻阅纸本复盘笔记。\n训练电脑在椅子后侧使用，E / Esc 可取消动作。\n走到大厅正门即可选择下一站，滚轮选择，E 出发。",17)
	var close:=Button.new(); close.text="知道了，开始走动"; close.focus_mode=Control.FOCUS_NONE
	close.pressed.connect(_toggle_help); helpcol.add_child(close); help_panel.visible=false

func _physics_process(_delta: float) -> void:
	if not booted: return
	player.camera_yaw=camera_yaw
	player.enabled=(focused or testing) and not help_panel.visible and not CareerBridge.phone_open
	if Travel.busy:player.enabled=false
	if life:
		life.held=help_panel.visible or Travel.busy or CareerBridge.phone_open
		if life.speaker:player.enabled=false
	var door_reachable: bool=not interactions.reachable("exit").is_empty()
	var door_allowed: bool=(focused or testing) and not help_panel.visible and not CareerBridge.phone_open and interactions.active.is_empty() and (life==null or life.speaker==null)
	Travel.update_door("club", door_reachable, door_allowed)

func _process(delta: float) -> void:
	if not booted:return
	warm_elapsed+=delta
	if CareerBridge.connected and int(warm_elapsed*2)!=int((warm_elapsed-delta)*2):_update_stats()
	_camera_update(delta)
	# Fade nearby lintels so doorways do not hide the small character.
	for mesh in overheads:
		var p: Vector3=(mesh.global_transform*mesh.get_aabb()).get_center()
		var near_player: bool=Vector2(p.x-player.position.x,p.z-player.position.z).length()<4.7
		mesh.transparency=move_toward(mesh.transparency,.90 if near_player and not overview else 0.0,delta*3)
	toast_seconds=maxf(0,toast_seconds-delta); toast_panel.visible=toast_seconds>0
	prompt_panel.visible=not CareerBridge.phone_open and not help_panel.visible and not Travel.busy
	if life and life.speaker:
		prompt_panel.visible=false;action_progress.visible=false
	elif interactions.active.is_empty():
		action_progress.visible=false
		action_label.visible=false
		var target:=world_target()
		if target.is_empty():
			prompt_panel.visible=false;prompt_label.text=""
		elif target["kind"]=="npc":
			prompt_label.text="F 和"+str(target["npc"].definition["name"])+"聊聊"
		else:
			prompt_label.text="" if target["item"]["id"]=="exit" else "E "+str(target["item"]["verb"])
			if target.get("npc"):
				prompt_label.text+=("  ·  " if not prompt_label.text.is_empty() else "")+"F 和"+str(target["npc"].definition["name"])+"聊聊"
			if prompt_label.text.is_empty():prompt_panel.visible=false
	else:
		action_progress.visible=true; action_progress.value=interactions.progress()
		prompt_label.text="E 取消";action_label.visible=true
		action_label.text=str(interactions.active["verb"])+"……"
		action_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	var room:=room_at(player.position)
	if room!=room_previous:
		room_label.text=room; room_previous=room

func world_target() -> Dictionary:
	var item:=interactions.reachable("computer")
	if item.is_empty():item=interactions.nearest()
	var npc=life.nearest_npc() if life else null
	if not item.is_empty():return {"kind":"object","item":item,"npc":npc}
	return {"kind":"npc","npc":npc} if npc else {}

func room_at(pos: Vector3) -> String:
	var annex_room := SceneTiers.club_room(pos,environment_tier)
	if not annex_room.is_empty(): return annex_room
	if pos.z < -1.7:
		return "训练室" if pos.x < -2.1 else ("战术会议室" if pos.x < 4.2 else "厨房")
	if pos.z < .86:return "公共走廊"
	return "休息区" if pos.x < -4.4 else ("大厅" if pos.x < 3.1 else "食堂")

func _camera_update(delta: float,instant: bool=false) -> void:
	var tier_view := SceneTiers.club_view(environment_tier)
	var desired: Vector3=tier_view.focus if overview else player.position+Vector3(0,.70,0)
	var factor:=1.0 if instant else 1-exp(-9*delta)
	camera_focus=camera_focus.lerp(desired,factor)
	camera.size=lerpf(camera.size,float(tier_view.size) if overview else camera_zoom,factor)
	camera.position=camera_focus+Vector3(sin(camera_yaw)*cos(camera_pitch),sin(camera_pitch),cos(camera_yaw)*cos(camera_pitch))*65
	camera.look_at(camera_focus,Vector3.UP)

func _unhandled_input(event: InputEvent) -> void:
	if not booted or Travel.busy or CareerBridge.phone_open:return
	if life and life.speaker:
		if event is InputEventKey and event.pressed and not event.echo:
			match event.physical_keycode:
				KEY_ESCAPE,KEY_4:life.close()
				KEY_1:dialogue.handle_choice("busy")
				KEY_2:dialogue.handle_choice("training")
				KEY_3:dialogue.handle_choice("encourage")
				KEY_E,KEY_SPACE,KEY_ENTER:dialogue.reveal()
		return
	if event is InputEventMouseButton:
		if event.button_index==MOUSE_BUTTON_RIGHT: dragging=event.pressed
		if event.pressed and not Travel.menu_open and event.button_index in [MOUSE_BUTTON_WHEEL_UP,MOUSE_BUTTON_WHEEL_DOWN]:
			camera_zoom=clampf(camera_zoom*(.90 if event.button_index==MOUSE_BUTTON_WHEEL_UP else 1.10),7,20)
	if event is InputEventMouseMotion and dragging:
		camera_yaw-=event.relative.x*.005
		camera_pitch=clampf(camera_pitch+event.relative.y*.004,.50,1.35)
	if event is InputEventKey and event.pressed and not event.echo:
		match event.physical_keycode:
			KEY_E:
				if not help_panel.visible:
					if not interactions.active.is_empty():interactions.cancel()
					else:
						var target:=world_target()
						if not target.is_empty():
							if target["kind"]=="object" and target["item"]["id"]!="exit":interactions.start(target["item"])
			KEY_F:
				if not help_panel.visible and interactions.active.is_empty() and life.begin():Travel.close_menu()
			KEY_ESCAPE:
				if help_panel.visible:_toggle_help()
				else:interactions.cancel()
			KEY_F1:_toggle_help()
			KEY_TAB:overview=not overview
			KEY_R:camera_yaw=.28;camera_pitch=.78;camera_zoom=12.6;overview=false
			KEY_N:_toggle_light()

func _notification(what: int) -> void:
	if what==NOTIFICATION_APPLICATION_FOCUS_OUT:
		focused=false;dragging=false
		if is_instance_valid(player):player.velocity=Vector3.ZERO
	elif what==NOTIFICATION_APPLICATION_FOCUS_IN:focused=true

func _toggle_help() -> void:
	help_panel.visible=not help_panel.visible
	player.velocity=Vector3.ZERO
	if help_panel.visible:Travel.close_menu()

func _toast(text: String,seconds: float=5.0) -> void:
	toast_label.text=text;toast_seconds=seconds

func _update_stats() -> void:
	stats_label.text=CareerBridge.clock_text()

func _career_changed() -> void:
	if not CareerBridge.context.is_empty():life.bind_career(CareerBridge.context)
	var club_environment: Dictionary = CareerBridge.context.get("environment",{}).get("club",{})
	environment_tier = str(club_environment.get("tier","academy"))
	SceneTiers.apply_club(self,model,environment_tier,club_environment.get("facilities",{}))
	if is_instance_valid(trophy_display): trophy_display.refresh(CareerBridge.context)
	if is_instance_valid(club_board): club_board.refresh()
	_update_stats()

func save_session() -> void:
	Travel.club_session={"values":interactions.values.duplicate(),"cooldowns":interactions.cooldowns.duplicate(),"clock":interactions.cooldown_clock,"completed":interactions.completed.duplicate(),"npcs":life.snapshot()}

func before_phone() -> void:
	if is_instance_valid(club_board): club_board.close_board(false)
	Travel.close_menu()
	dragging=false; help_panel.visible=false
	if life.speaker:life.close()
	interactions.cancel(); player.velocity=Vector3.ZERO
	player.upper_body_action=""

func before_computer() -> void:
	if is_instance_valid(club_board): club_board.close_board(false)
	Travel.close_menu()
	dragging=false;help_panel.visible=false
	if life.speaker:life.close()
	if not interactions.active.is_empty():interactions.cancel()
	player.velocity=Vector3.ZERO

func set_phone_open(opened: bool) -> void:
	set_device_open(opened,"phone")

func set_device_open(opened: bool,kind: String) -> void:
	if not is_instance_valid(player):return
	if opened:
		device_kind=kind;player.velocity=Vector3.ZERO;player.locked=true
		if kind=="computer":
			player.set_item_use(false);player.set_carried_item("");player.upper_body_action="typing"
			if not interactions.retained_device.is_empty():
				player.seat_pose=true;player.face_toward(interactions.vec(interactions.retained_device["seat_look"]))
		elif kind == "club_board":
			interactions.release_device(); player.seat_pose = false; player.upper_body_action = ""
			player.set_item_use(false); player.set_carried_item("")
		else:
			interactions.release_device();player.seat_pose=false;player.upper_body_action=""
			player.set_carried_item("phone");player.set_item_use(true)
		player.locked=true
	else:
		if device_kind=="computer":interactions.release_device()
		device_kind="";player.upper_body_action="";player.seat_pose=false
		player.set_item_use(false);player.set_carried_item("");player.locked=false;player.velocity=Vector3.ZERO

func _exit_tree() -> void:
	if is_instance_valid(club_board): club_board.close_board()
	if is_instance_valid(interactions):interactions.release_device()
	if is_instance_valid(player):player.clear_presentation();player.locked=false

func _fridge(opened: bool) -> void:
	if not fridge_pivot:return
	if fridge_tween and fridge_tween.is_valid():fridge_tween.kill()
	fridge_tween=create_tween()
	fridge_tween.tween_property(fridge_pivot,"rotation:y",-1.18 if opened else 0.0,.35).set_trans(Tween.TRANS_SINE)

func _action_started(_id: String,kind: String) -> void:
	if kind=="drink":_fridge(true)
	var held: String=str(interactions.active.get("carried_item","cup" if kind in ["drink","coffee","meal"] else ""))
	player.set_carried_item(held);player.set_item_use(not held.is_empty())
	player.upper_body_action="typing" if _id=="computer" else ""
	if kind=="train" and computer_display:
		var lit:=StandardMaterial3D.new();lit.albedo_color=Color("84e4bc");lit.emission_enabled=true;lit.emission=Color("63cba5")
		computer_display.material_overlay=lit

func _action_completed(_id: String,_effects: Dictionary) -> void:
	_cleanup_action()
	if _id=="computer":
		Computer.present("club")
	elif _id=="whiteboard":
		Computer.open_app("tactics", "club")
	elif _id in ["reception", "trophy"]:
		if not testing:
			toast_seconds = 0.0
			club_board.present(_id)
	elif not testing and CareerBridge.connected:
		var entrances: Dictionary={"sofa":"calendar"}
		if entrances.has(_id):Phone.present(entrances[_id])

func _action_cancelled(_id: String) -> void:
	_cleanup_action()

func _cleanup_action() -> void:
	_fridge(false);player.set_item_use(false);player.set_carried_item("");player.upper_body_action=""
	if computer_display:computer_display.material_overlay=null

func _toggle_light() -> void:
	evening=not evening;sun.light_energy=.2 if evening else .75
	environment.ambient_light_energy=.28 if evening else .4
	for light in warm_lights:light.light_energy=1.3 if evening else .12
