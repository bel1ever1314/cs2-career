extends "res://scripts/small_venue_base.gd"
const Collisions=preload("res://scripts/arena_collision.gd")
const Atmosphere=preload("res://scripts/arena_atmosphere.gd")
const ChickenCrowd=preload("res://scripts/arena_chicken_crowd.gd")
const Roster=preload("res://scripts/venue_match_roster.gd")
const Competitor=preload("res://scripts/venue_competitor.gd")
const SceneTiers=preload("res://scripts/scene_tiers.gd")
var atmosphere: Atmosphere
var crowd: ChickenCrowd
var model: Node3D
var collision_builder: RefCounted
var intro:=0.0
var intro_finished:=false
var notice: Label
var notice_time:=0.0
var main_board: Control
var wing_boards: Array[Control]=[]
var board_phase:="<unset>"
var sun: DirectionalLight3D
var showtime:=false
var lights: Array[OmniLight3D]=[]
var current_point: Dictionary={}
var roster_plan: Dictionary={}
var peers: Array[Node3D]=[]
var allies: Array[Dictionary]=[]
var competition_phase:="preview"
var player_station: Dictionary={}
var device_seated:=false
var device_approach:=Vector3.ZERO
var seat_serial:=0
var entry_door_released:=false

func _ready() -> void:
	testing="--arena-test" in OS.get_cmdline_user_args()
	capturing="--arena-capture" in OS.get_cmdline_user_args()
	settings=JSON.parse_string(FileAccess.get_file_as_string("res://data/major_walk.json"))
	roster_plan=Roster.plan(Travel.match_visit)
	assert(settings.get("schema_version")==1)
	_input_map()
	model=(load("res://assets/major_walk.glb") as PackedScene).instantiate() as Node3D;add_child(model)
	_tunnel_materials()
	_venue_display_materials()
	collision_builder=Collisions.new();collision_builder.build(self,model)
	_batch_crowd()
	SceneTiers.apply_venue(self,model,_visit_capacity(10000),"major")
	_environment()
	atmosphere=Atmosphere.new();add_child(atmosphere)
	var atmosphere_options: Dictionary=settings.get("atmosphere",{}).duplicate(true)
	atmosphere_options["competitive"]=not roster_plan.is_empty()
	atmosphere_options["capacity"]=_visit_capacity(10000)
	atmosphere.setup(env,sun,atmosphere_options)
	_stand_lights(_visit_capacity(10000))
	atmosphere.set_master_volume(CareerBridge.sound_volume); atmosphere.set_muted(CareerBridge.sound_muted)
	player=Player.new();player.name="ArenaVisitor"
	player.position=vec(settings["spawn"]);player.home=player.position
	player.test_mode=testing;player.walk_speed=float(settings["walk_speed"]);player.run_speed=float(settings["run_speed"])
	player.step_height=.27;player.floor_snap_length=.38;add_child(player)
	player.visual.rotation.y=PI;player.locked=true
	player.recovered.connect(func(): _notice("已回到场馆入口。"))
	camera=Camera3D.new();camera.current=true;camera.fov=76;camera.near=.06;camera.far=260;add_child(camera)
	camera.physics_interpolation_mode=Node.PHYSICS_INTERPOLATION_MODE_OFF
	# Camera itself updates every rendered frame, using interpolated body XY.
	camera.physics_interpolation_mode=Node.PHYSICS_INTERPOLATION_MODE_OFF
	body_y=player.position.y
	_hud();_wayfinding();_competition_roster();_stage_boards()
	if roster_plan.is_empty():
		var guidance := Travel.preview_match_hint("major")
		if not guidance.is_empty(): _notice(guidance)
	Travel.arrived.connect(_arrived)
	booted=true
	if testing:
		finish_intro()
		var suite=load("res://tests/arena_smoke_test.gd").new();add_child(suite);suite.call_deferred("run",self)
	elif capturing:
		finish_intro()
		if "--inside" in OS.get_cmdline_user_args():player.position=Vector3(0,.52,15.8)
		if "--stage" in OS.get_cmdline_user_args():player.position=Vector3(-11,1.68,-13.4);yaw=-.65;pitch=.12
		player.reset_physics_interpolation();body_y=player.position.y
		if "--showtime" in OS.get_cmdline_user_args():atmosphere.set_showtime(true)
		if "--roof" in OS.get_cmdline_user_args():pitch=.63
		await get_tree().create_timer(3).timeout
		await RenderingServer.frame_post_draw
		var suffix: String="roof" if "--roof" in OS.get_cmdline_user_args() else ("stage" if "--stage" in OS.get_cmdline_user_args() else ("inside" if "--inside" in OS.get_cmdline_user_args() else "entry"))
		get_viewport().get_texture().get_image().save_png("res://renders/major_walk_"+suffix+".png")
		print("MAJOR_CAPTURE fps=",Engine.get_frames_per_second()," draws=",Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
		print("ARENA_ATMOSPHERE ",JSON.stringify(atmosphere.diagnostic_snapshot()))
		get_tree().quit()

func _visit_capacity(fallback: int) -> int:
	var venue: Dictionary = Travel.match_visit.get("venue", {}) if Travel.match_visit.get("venue") is Dictionary else {}
	return int(venue.get("capacity", Travel.match_visit.get("capacity", fallback)))

func _stand_lights(capacity: int) -> void:
	if capacity < 1000: return
	var rings := [[24.0,7.5],[34.0,11.0]] if capacity >= 10000 else [[24.0,7.5]]
	for ring in rings:
		for angle in [-1.25,-.75,-.25,.25,.75,1.25]:
			var light:=OmniLight3D.new();light.name="StandWash"
			light.position=Vector3(sin(angle)*ring[0],ring[1]+5.0,cos(angle)*ring[0]*.75+8.0)
			light.light_color=Color("ffe2c2");light.light_energy=1.1;light.omni_range=26.0;light.omni_attenuation=1.0
			light.shadow_enabled=false;light.light_volumetric_fog_energy=0.0;add_child(light)

func _batch_crowd() -> void:
	crowd=ChickenCrowd.new();add_child(crowd);crowd.setup(model)

func _venue_display_materials() -> void:
	# Imported screen typography was part of the old static diorama. The new
	# single entrance graphic owns the visible panels, with brief honest text.
	for node in model.find_children("*", "Node3D", true, false):
		var n:=str(node.name).replace("_", " ").to_lower()
		# The old static exhibit contained ten plush human stand-ins. Competition
		# identities are now supplied by the frozen preflight, including one empty seat.
		if n.begins_with("competitor ") or n.begins_with("player arm") or n.begins_with("player headset"): node.visible=false
		if n.begins_with("main major headline") or n.begins_with("main stage subtitle") or n.begins_with("main score") or n.begins_with("event signature") or n.begins_with("wing team title") or n.begins_with("wing team star") or n.begins_with("wing final label"):
			node.visible=false
		if node is MeshInstance3D and (n=="main led screen" or n.begins_with("wing screen") and "surround" not in n):
			var backing:=StandardMaterial3D.new();backing.albedo_color=Color("07101b");backing.roughness=.82
			node.material_override=backing
	# Stage stations: chicken players are wider than the old plush stand-ins,
	# so seats move back from the desk; each monitor gets a live game frame.
	var screen_index:=0
	for node in model.find_children("*","MeshInstance3D",true,false):
		var n:=str(node.name).replace("_"," ").to_lower()
		if n.begins_with("seat cushion") or n.begins_with("seat pedestal"):node.global_position.z-=.10
		elif n.begins_with("seat rounded back"):node.global_position.z-=.41
		elif n.begins_with("player monitor back"):
			var bounds: AABB=node.global_transform*node.get_aabb()
			var centre:=bounds.position+bounds.size*.5
			var screen:=MeshInstance3D.new();screen.name="StageMonitorFrame"
			var quad:=QuadMesh.new();quad.size=Vector2(bounds.size.x*.9,bounds.size.y*.86);screen.mesh=quad
			screen.position=Vector3(centre.x,centre.y,bounds.position.z-.004);screen.rotation.y=PI
			screen.material_override=Kit.screen_material(Kit.game_frame(1009+screen_index*37,centre.x>0),.9)
			screen.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			add_child(screen);screen_index+=1

func _tunnel_materials() -> void:
	# Explicit Godot materials keep the added passage's colours consistent
	# with the original venue even when the GLB exporter omits legacy diffuse.
	for node in model.find_children("*","MeshInstance3D",true,false):
		var n:=str(node.name).replace("_"," ").to_lower()
		if not n.begins_with("walk tunnel"):continue
		var mat:=StandardMaterial3D.new();mat.roughness=.85
		mat.albedo_color=Color("3c6470") if "lining" in n else Color("172c3b")
		if "guide strip" in n:
			mat.albedo_color=Color("e9ba64");mat.emission_enabled=true;mat.emission=Color("b68d41");mat.emission_energy_multiplier=.5
		node.material_override=mat

func _environment() -> void:
	var world:=WorldEnvironment.new();env=Environment.new();world.environment=env;add_child(world)
	env.background_mode=Environment.BG_COLOR;env.background_color=Color("b7c8cf")
	env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;env.ambient_light_color=Color("e5edf4")
	env.ambient_light_energy=.65;env.tonemap_mode=Environment.TONE_MAPPER_ACES
	env.ssao_enabled=true;env.ssao_radius=.7;env.ssao_intensity=.8
	env.glow_enabled=true;env.glow_intensity=.25
	sun=DirectionalLight3D.new();sun.rotation_degrees=Vector3(-58,-30,0)
	sun.light_color=Color("fff0d9");sun.light_energy=.95;sun.shadow_enabled=true
	sun.directional_shadow_max_distance=120;sun.light_angular_distance=2;add_child(sun)

func _arena_sign(text: String,pos: Vector3,size: float=.012,face_view: bool=false) -> Label3D:
	var label:=Label3D.new();label.text=text;label.position=pos;label.font_size=58
	label.font=UI.font()
	label.pixel_size=size;label.modulate=Color("ffe2ad");label.outline_size=10
	if face_view:label.billboard=BaseMaterial3D.BILLBOARD_ENABLED
	label.double_sided=false
	add_child(label)
	return label

func _wayfinding() -> void:
	var board:=MeshInstance3D.new();var face:=BoxMesh.new();face.size=Vector3(5.4,.83,.10)
	board.mesh=face;board.position=Vector3(0,3.74,50.40)
	var ink:=StandardMaterial3D.new();ink.albedo_color=Color("172c3b");board.material_override=ink;add_child(board)
	_arena_sign("内场入口  /  ARENA",Vector3(0,3.74,50.47),.006)
	_arena_sign("↓",Vector3(0,2.8,50.47),.008)
	_arena_sign("向前进入内场",Vector3(0,3.4,19.2),.006)
	# Add visible short access stairs up to the trophy runway (the original
	# diorama had a 45 cm vertical front face, impossible to walk up).
	for i in range(2):
		var size:=Vector3(3.05,.16,.40)
		var center:=Vector3(0,.58+i*.17,.95-i*.40)
		var mesh:=MeshInstance3D.new();var cube:=BoxMesh.new();cube.size=size;mesh.mesh=cube;mesh.position=center
		var mat:=StandardMaterial3D.new();mat.albedo_color=Color("b99d69");mesh.material_override=mat;add_child(mesh)
	collision_builder.ramp(self,"RunwayAccess",1.54,1.28,.505,.28,.959)
	# Bridge the original foyer floor's rounded 7 cm lip in both directions.
	collision_builder.ramp(self,"FoyerThreshold",2.65,45.90,.474,46.90,.544)

func _panel() -> StyleBoxFlat:
	var s:=StyleBoxFlat.new();s.bg_color=Color(.045,.085,.11,.92)
	s.corner_radius_top_left=10;s.corner_radius_top_right=10;s.corner_radius_bottom_left=10;s.corner_radius_bottom_right=10
	s.content_margin_left=18;s.content_margin_right=18;s.content_margin_top=12;s.content_margin_bottom=12
	return s

func _label(parent: Node,text: String,size: int) -> Label:
	var label:=Label.new();label.text=text;label.add_theme_font_override("font",UI.font());label.add_theme_font_size_override("font_size",size);parent.add_child(label);return label

func _competition_roster() -> void:
	if roster_plan.is_empty(): return
	competition_phase="holding"
	var own: Array=roster_plan["own"];var other: Array=roster_plan["opponents"]
	player_station={"seat":Vector3(-5.96,1.56,-17.48),"approach":Vector3(-5.96,1.68,-18.48),"screen":Vector3(-5.96,2.67,-16.83)}
	var x_positions: Array[float]=[-7.72,-6.84,-5.96,-5.08,-4.20]
	var ally_index:=0
	for i in range(5):
		# Desk-front name plates face the audience; only your seat gets a marker.
		_plate(str(own[i].get("name","")),Vector3(x_positions[i],2.27,-16.205))
		if i==2:
			var marker:=_arena_sign("你的席位 ↓",Vector3(x_positions[i],3.45,-17.55),.0022,true);marker.double_sided=true
		if i!=2:
			var offset:=Vector3(-.76 if ally_index%2==0 else .76,0,-1.25-int(ally_index/2)*1.45)
			var waiting_at:=player.position+Vector3(offset.x,0,-1.2-int(ally_index/2)*1.4)
			var actor=_competitor(own[i],str(roster_plan["own_team"]),waiting_at,Color("355d72"))
			actor.locked=false;actor.walk_speed=5.0;actor.run_speed=5.0
			actor.face_toward(actor.position+Vector3(0,0,-1))
			allies.append({"actor":actor,"offset":offset,"seat":Vector3(x_positions[i],1.56,-17.48),"screen":Vector3(x_positions[i],2.67,-16.83),"route":[],"step":0})
			ally_index+=1
		var opponent_seat:=Vector3(-x_positions[4-i],1.56,-17.48)
		var opponent=_competitor(other[i],str(roster_plan["opponent_team"]),opponent_seat,Color("ad6b3d"))
		opponent.seat_pose=true;opponent.locked=true;opponent.upper_body_action="typing"
		opponent.face_toward(opponent_seat+Vector3(0,1,1))
		_plate(str(other[i].get("name","")),Vector3(opponent_seat.x,2.27,-16.205))
	# Event and team names now live on the main LED board (_stage_boards).
	_notice("和队友一起穿过中央通道入场")

func _plate(text: String, at: Vector3) -> void:
	var label:=_arena_sign(text,at,.0024)
	label.modulate=Color("24332d");label.outline_size=0

func _competitor(row: Dictionary, team: String, at: Vector3, color: Color) -> Node3D:
	var actor=Competitor.new();actor.name="Competitor_"+str(peers.size())
	# Seated on the stage chair cushion (top 2.0 m), body clear of desk and back.
	actor.seat_lift=2.0-at.y-.16;actor.seat_forward=-.06
	actor.position=at;actor.home=at;actor.test_mode=true;actor.step_height=.27;actor.floor_snap_length=.38
	add_child(actor);actor.setup_identity(row,team,color);peers.append(actor);return actor

func _update_competition() -> void:
	if roster_plan.is_empty() or paused or CareerBridge.phone_open or Travel.busy or not intro_finished: return
	# The final opener starts with the team assembled; its build holds until
	# the walk-out nears the tunnel mouth, where the drop lands.
	if competition_phase=="holding" and atmosphere.uses_cue():atmosphere.start_entrance()
	if competition_phase=="holding" and player.position.z<36.0:
		competition_phase="walkout";atmosphere.start_entrance();atmosphere.set_showtime(true)
		_notice(str(roster_plan["own_team"])+" 入场")
	if competition_phase=="walkout" and player.position.z<18.0:
		competition_phase="floor";atmosphere.portal_impact()
		_notice("走到奖杯前，从右侧通道上舞台")
	if competition_phase in ["holding","walkout"]:
		for entry in allies:
			var actor=entry["actor"];var aim: Vector3=player.position+entry["offset"]
			aim.z=minf(aim.z,57.0)
			var direction: Vector3=aim-actor.position;direction.y=0
			actor.test_direction=direction.normalized() if direction.length()>.25 else Vector3.ZERO
	elif competition_phase=="floor":
		# All four take the same walkable aisle/ramp, not a diagonal through fans.
		competition_phase="seating"
		for entry in allies:
			entry["route"]=[Vector3(0,.5,12.0),Vector3(0,.5,2.5),Vector3(2.1,.5,2.5),Vector3(2.1,.5,-7.8),Vector3(8,.5,-7.8),Vector3(8,1.68,-12.5),Vector3(9,1.68,-18.5),Vector3(entry["seat"].x,1.68,-18.5),entry["seat"]]
	elif competition_phase=="seating":
		var ready:=true
		for entry in allies:
			var actor=entry["actor"]
			if actor.seat_pose: continue
			var route: Array=entry["route"];var step:=int(entry["step"])
			while step<route.size() and Vector2(actor.position.x-route[step].x,actor.position.z-route[step].z).length()<.18: step+=1
			entry["step"]=step
			if step>=route.size():
				actor.position=entry["seat"];actor.reset_physics_interpolation();actor.test_direction=Vector3.ZERO;actor.locked=true;actor.seat_pose=true;actor.upper_body_action="typing";actor.face_toward(entry["screen"])
			else:
				ready=false;var direction: Vector3=route[step]-actor.position;direction.y=0;actor.test_direction=direction.normalized()
		if ready:
			competition_phase="ready";_notice("队友已入座 · 到你的空位按 E")

func _at_player_seat() -> bool:
	if player_station.is_empty() or player.position.y<1.5: return false
	var at: Vector3=player_station["approach"]
	return Vector2(player.position.x-at.x,player.position.z-at.z).length()<1.05

func _hud() -> void:
	# Same glass HUD as the club, dorm and small venues.
	var canvas:=CanvasLayer.new();canvas.name="WorldHud";add_child(canvas)
	var root:=Control.new();root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);root.mouse_filter=Control.MOUSE_FILTER_IGNORE;canvas.add_child(root)
	var venue_title := "职业赛事 / 大型场馆" if not roster_plan.is_empty() else "MAJOR / 场馆"
	var attendance := Travel.match_guidance()
	if str(attendance.get("destination", "")) == "major": venue_title = str(attendance.get("display_name", venue_title))
	title_parts=Hud.title_card(root,venue_title,"入场大厅");status=title_parts["status"]
	caption_parts=Hud.caption_pill(root);notice=caption_parts["label"]
	prompt_parts=Hud.prompt(root)
	hint=Label.new();hint.visible=false;root.add_child(hint)
	var row:=Hud.hint_bar(root)
	Hud.key_hint(row,"WASD","走动");Hud.key_hint(row,"E","交互")
	Hud.key_button(row,"N","舞台灯光",func(): showtime=not showtime;atmosphere.set_showtime(showtime))
	Hud.key_button(row,"P","手机",func(): if not CareerBridge.phone_open and not Travel.busy: Phone.present())
	Hud.key_button(row,"Esc","菜单",func(): set_paused(not paused))
	cursor_dot=Hud.text(root,"•",14,Color(1,1,1,.8));cursor_dot.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	cursor_dot.offset_left=-4;cursor_dot.offset_top=-10
	var pause:=Hud.pause_menu(root,"场馆漫步","穿过中央通道进入内场，沿座位旁的过道可走到舞台。\n原创入场配乐 · 场内声 · 欢呼")
	pause_panel=pause["panel"]
	Hud.menu_button(pause["menu"],"继续走动",func(): set_paused(false),true)
	Hud.menu_button(pause["menu"],"返回俱乐部",func(): Travel.go("club"))
	pause_panel.visible=false

func _sync_hint() -> void:
	if hint.text==shown_hint:return
	shown_hint=hint.text
	var objective: Label=title_parts["objective"]
	var active:=Hud.set_prompt(prompt_parts,hint.text)
	objective.text="" if active else hint.text
	objective.visible=not objective.text.is_empty()

## Transparent LED layers over the original stage screens: today's match-up
## (team marks, event, phase) on the main wall and one team per wing screen.
func _stage_boards() -> void:
	main_board=Kit.led_screen(self,"MajorMatchBoard",Vector3(0,9.4,-23.59),Vector2(23.65,10.0),Vector2i(1892,800),0.0,1.0,true)
	for spec in [[Vector3(-20,7.5,-20.70),0],[Vector3(20,7.5,-20.70),1]]:
		wing_boards.append(Kit.led_screen(self,"MajorWingBoard",spec[0],Vector2(5.5,8.6),Vector2i(440,688),0.0,1.0,true))
	for label_name in ["MajorScreenTitle"]:
		var label:=atmosphere.get_node_or_null(label_name) as Label3D
		if label:label.visible=false
	if atmosphere.stage_subtitle:atmosphere.stage_subtitle.visible=false
	if not CareerBridge.changed.is_connected(_redraw_boards):CareerBridge.changed.connect(_redraw_boards)

func _redraw_boards() -> void:board_phase="<unset>"

func _draw_boards() -> void:
	var phase:=str(atmosphere.stage_subtitle.text) if atmosphere.stage_subtitle else "入场"
	if phase==board_phase or not is_instance_valid(main_board):return
	board_phase=phase
	var root:=main_board;Kit.clear(root)
	var w:=root.size.x
	var venue: Dictionary=Travel.match_visit.get("venue",{})
	if roster_plan.is_empty():
		Kit.text_at(root,"MAJOR",230,Rect2(0,150,w,300),Color("f0dfb6"))
		Kit.text_at(root,"冠军舞台 · 自由参观",64,Rect2(0,470,w,100),Color("b8c7da"))
	else:
		var own:=str(roster_plan["own_team"]);var other:=str(roster_plan["opponent_team"])
		var event_name:=str(venue.get("event_name",venue.get("name","职业赛事")))
		Kit.text_at(root,event_name,66,Rect2(0,110,w,96),Color("e8c483"))
		var row:=HBoxContainer.new();row.alignment=BoxContainer.ALIGNMENT_CENTER;row.mouse_filter=Control.MOUSE_FILTER_IGNORE
		row.position=Vector2(0,230);row.size=Vector2(w,300);row.add_theme_constant_override("separation",56);root.add_child(row)
		Kit.logo_tile(row,own,250)
		Kit.text(row,own,132,Color("f0dfb6"),HORIZONTAL_ALIGNMENT_RIGHT)
		Kit.text(row,"VS",104,Color("e8c483"))
		Kit.text(row,other,132,Color("f0dfb6"),HORIZONTAL_ALIGNMENT_LEFT)
		Kit.logo_tile(row,other,250)
		var preflight: Dictionary=CareerBridge.context.get("match_preflight",{}) if CareerBridge.context.get("match_preflight",{}) is Dictionary else {}
		var details: Array[String]=[]
		if str(preflight.get("match_id",""))==str(roster_plan.get("match_id","")):
			if not str(preflight.get("stage","")).is_empty():details.append(str(preflight.get("stage","")))
			if int(preflight.get("best_of",0))>0:details.append("BO%d"%int(preflight.get("best_of",0)))
		details.append(Locale.text(phase))
		Kit.text_at(root," · ".join(details),56,Rect2(0,560,w,90),Color("b8c7da"))
	for i in range(wing_boards.size()):
		var wing:=wing_boards[i];Kit.clear(wing)
		var team:=""
		if not roster_plan.is_empty():team=str(roster_plan["own_team"] if i==0 else roster_plan["opponent_team"])
		if team.is_empty():
			Kit.text_at(wing,"CHAMPIONS",54,Rect2(0,250,wing.size.x,80),Color("e8c483"))
			Kit.text_at(wing,"STAGE",54,Rect2(0,330,wing.size.x,80),Color("e8c483"))
		else:
			var holder:=CenterContainer.new();holder.position=Vector2(0,150);holder.size=Vector2(wing.size.x,300);holder.mouse_filter=Control.MOUSE_FILTER_IGNORE;wing.add_child(holder)
			Kit.logo_tile(holder,team,280)
			Kit.text_at(wing,team,58,Rect2(10,480,wing.size.x-20,90),Color("f0dfb6"))
		Kit.refresh(wing)
	Kit.refresh(root)

func finish_intro() -> void:
	intro_finished=true;player.locked=false
	for child in player.get_children():
		if child is Node3D and not child is CollisionShape3D:child.visible=false
	if not testing and not capturing and focused and not paused and not CareerBridge.phone_open:Input.mouse_mode=Input.MOUSE_MODE_CAPTURED

func _arrived(destination: String) -> void:
	if destination=="major":intro=0

func _physics_process(_delta: float) -> void:
	if not booted:return
	player.camera_yaw=yaw
	player.enabled=intro_finished and not paused and not camera_owned and not Travel.busy and not CareerBridge.phone_open and (focused or testing or capturing)
	for entry in allies:
		var actor=entry["actor"];actor.enabled=not paused and not Travel.busy and not CareerBridge.phone_open
	current_point={}
	for item in settings["points"]:
		var p:=vec(item["position"])
		if Vector2(p.x-player.position.x,p.z-player.position.z).length()<float(item["range"]):current_point=item;break
	var near_exit: bool=not current_point.is_empty() and current_point["id"]=="exit"
	if roster_plan.is_empty() or player.position.z<54.0:entry_door_released=true
	Travel.update_door("major", near_exit, entry_door_released and intro_finished and not paused and (focused or testing or capturing))

func _process(delta: float) -> void:
	if not booted:return
	if not is_equal_approx(atmosphere.master_volume,CareerBridge.sound_volume):atmosphere.set_master_volume(CareerBridge.sound_volume)
	if atmosphere.muted!=CareerBridge.sound_muted:atmosphere.set_muted(CareerBridge.sound_muted)
	atmosphere.update_visitor(player.position,delta,intro_finished and not Travel.busy and roster_plan.is_empty())
	_update_competition()
	crowd.set_reaction(atmosphere.crowd_reaction(),not paused and not CareerBridge.phone_open)
	var p: Vector3=player.get_global_transform_interpolated().origin
	body_y=lerpf(body_y,p.y,1-exp(-16*delta))
	var eye:=Vector3(p.x,body_y+float(settings["eye_height"]),p.z)
	if not intro_finished:
		if not Travel.busy and not paused:intro+=delta
		var t: float=clampf(intro/float(settings["intro_seconds"]),0,1)
		var blend:=smoothstep(0,1,t)
		camera.position=eye+Vector3(0,2.0,4.6)*(1-blend)
		camera.rotation=Vector3(-.24*(1-blend),0,0)
		if t>.78:player.visual.visible=false
		if t>=1:finish_intro()
	elif not camera_owned:
		camera.position=eye;camera.rotation=Vector3(pitch,yaw,0)
	status.text=zone(player.position)
	hint.text=("门口可选择下一站 · 可直接走开" if current_point["id"]=="exit" else str(current_point["prompt"])) if not current_point.is_empty() else "沿通道往前 · 自由观察场馆" 
	if not intro_finished:hint.text="镜头正在切换至第一人称……"
	elif device_seated:hint.text="比赛电脑 · 收起后回到桌后通道"
	elif not roster_plan.is_empty() and not entry_door_released:hint.text="队伍集合完毕 · 沿中央通道和队友一起入场"
	elif _at_player_seat():hint.text="E 坐进你的空席 · 打开比赛电脑" if competition_phase=="ready" else "队友正在就位 · 稍候入座"
	elif not roster_plan.is_empty() and not current_point.is_empty() and current_point["id"]=="desk":hint.text="沿桌侧绕到后方 · 你的空席在左侧中央"
	elif roster_plan.is_empty() and (current_point.is_empty() or current_point["id"] != "exit"):
		var guidance := Travel.preview_match_hint("major")
		if not guidance.is_empty(): hint.text = guidance
	cursor_dot.visible=intro_finished and not paused and not CareerBridge.phone_open
	notice_time=maxf(0,notice_time-delta);(caption_parts["panel"] as Control).visible=notice_time>0 and not notice.text.is_empty()
	_sync_hint();_draw_boards()

func zone(p: Vector3) -> String:
	if p.z>49:return "入场大厅 / 中央入口通往内场"
	if p.z>18 and absf(p.x)<3:return "入场通道 / 前方是舞台"
	if p.z< -10 and absf(p.x)<16:return "选手舞台"
	if p.z<18 and absf(p.x)<21:return "内场 / 观众席与奖杯区"
	return "场馆公共区域"

func _notice(text: String) -> void:notice.text=text;notice_time=6;Hud.fit_caption(caption_parts)

func _pause_changed(value: bool) -> void:
	if is_instance_valid(atmosphere): atmosphere.set_paused(value)

func _look_allowed() -> bool:
	return intro_finished

func interact() -> void:
	if not intro_finished or paused or device_seated:return
	if _at_player_seat() and competition_phase=="ready":
		_seat_player();var serial:=seat_serial
		await camera_tween.finished
		if serial!=seat_serial or not device_seated or not is_inside_tree() or Travel.busy:return
		Computer.open_app("career_match","major");return
	if current_point.is_empty():return
	if current_point["id"]=="exit":return
	elif current_point["id"]=="desk" and not roster_plan.is_empty():_notice("从桌侧走到后方。只有你的空席可以打开比赛电脑。")
	elif CareerBridge.connected:Phone.present("match")
	else:_notice(str(current_point["text"]))

func _seat_player() -> void:
	Travel.close_menu();seat_serial+=1;device_approach=player.global_position;device_seated=true;camera_owned=true
	player.locked=true;player.velocity=Vector3.ZERO;player.seat_pose=true;player.upper_body_action="typing"
	player.global_position=player_station["seat"];player.reset_physics_interpolation();player.face_toward(player_station["screen"])
	var view:=Transform3D(Basis.IDENTITY,player_station["seat"]+Vector3.UP*1.17).looking_at(player_station["screen"],Vector3.UP)
	if camera_tween and camera_tween.is_valid():camera_tween.kill()
	camera_tween=create_tween();camera_tween.set_trans(Tween.TRANS_CUBIC);camera_tween.set_ease(Tween.EASE_IN_OUT);camera_tween.tween_property(camera,"global_transform",view,.72)
	atmosphere.settle_competition()

func _leave_computer() -> void:
	if not device_seated:return
	seat_serial+=1;device_seated=false
	if camera_tween and camera_tween.is_valid():camera_tween.kill()
	player.global_position=device_approach;player.reset_physics_interpolation();body_y=player.position.y
	player.seat_pose=false;player.upper_body_action="";player.locked=CareerBridge.phone_open;player.velocity=Vector3.ZERO
	var view:=Transform3D(Basis.from_euler(Vector3(pitch,yaw,0)),device_approach+Vector3.UP*float(settings["eye_height"]))
	camera_tween=create_tween();camera_tween.set_trans(Tween.TRANS_CUBIC);camera_tween.set_ease(Tween.EASE_IN_OUT);camera_tween.tween_property(camera,"global_transform",view,.38)
	camera_tween.finished.connect(func():camera_owned=false)

func match_seated(match_id: String) -> bool:
	return not roster_plan.is_empty() and str(roster_plan.get("match_id",""))==match_id and device_seated and competition_phase=="ready"

func after_computer() -> void:_leave_computer()

func set_device_open(value: bool, kind: String) -> void:
	var hud_layer:=get_node_or_null("WorldHud") as CanvasLayer
	if hud_layer: hud_layer.visible=not value
	if value and kind=="phone":_leave_computer()
	if value:Travel.close_menu()
	player.velocity=Vector3.ZERO
	player.locked=value or device_seated or not intro_finished
	atmosphere.set_paused(value or paused)
	if not value:_leave_computer()
	Input.mouse_mode=Input.MOUSE_MODE_VISIBLE if value or paused else Input.MOUSE_MODE_CAPTURED

func _unhandled_input(event: InputEvent) -> void:
	super._unhandled_input(event)
	if not booted or Travel.busy or CareerBridge.phone_open: return
	if event is InputEventKey and event.pressed and not event.echo and event.physical_keycode == KEY_N:
		showtime = not showtime
		atmosphere.set_showtime(showtime)

func before_phone() -> void:
	Travel.close_menu();_leave_computer()

func diagnostic_snapshot() -> Dictionary:
	var seated_peers:=0
	for actor in peers:
		if actor.seat_pose:seated_peers+=1
	return {"destination":"major","match_id":roster_plan.get("match_id",""),"roster_ready":not roster_plan.is_empty(),"phase":competition_phase,"peers":peers.size(),"seated_peers":seated_peers,"seated":device_seated,"human_id":roster_plan.get("human_id",""),"launches_cs2":false}
