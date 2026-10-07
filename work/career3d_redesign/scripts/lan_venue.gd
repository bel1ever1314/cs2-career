extends "res://scripts/small_venue_base.gd"
## Ten opposing stations; entering the computer never launches CS2 here.
const Roster = preload("res://scripts/venue_match_roster.gd")
const Competitor = preload("res://scripts/venue_competitor.gd")
const SceneTiers = preload("res://scripts/scene_tiers.gd")
var stations: Array[Dictionary] = []
var roster_plan: Dictionary = {}
var peers: Array[Node3D] = []
var device_seated := false
var device_approach := Vector3.ZERO
var selected_station: Dictionary = {}
var seat_serial := 0
var seat_marker: Label3D
var marker_clock := 0.0
var match_board: Control
var studio_board: Control

func _destination() -> String: return "lan"
func _data_path() -> String: return "res://data/lan_venue.json"

func _build_venue() -> void:
	_enclosure(13.2,13.0,4.1)
	_box("StageDeck",Vector3(0,-.02,0),Vector3(11.5,.04,7.2),Color("202d36"))
	for side in [-1.0,1.0]:
		_box("StageAccess",Vector3(side*5.97,-.02,0),Vector3(.48,.04,7.2),Color("33464f"))
		_box("TeamDesk",Vector3(0,1.0,side*1.08),Vector3(10.9,.12,.94),Color("33414a"),true)
		for x in [-4.8,0.0,4.8]: _box("DeskLeg",Vector3(x,.57,side*1.08),Vector3(.10,.80,.72),Color("16212c"))
		_box("DeskLight",Vector3(0,.93,side*1.56),Vector3(10.8,.025,.025),Color("70bcaf") if side>0 else Color("dcaa65"),false,.8)
	# A continuous glass divider sits between the facing rows, with solid posts.
	var glass := _box("GlassDivider",Vector3(0,1.55,0),Vector3(10.85,2.2,.065),Color(.33,.64,.69,.19),true)
	var mat := _material(Color(.33,.64,.69,.19)).duplicate() as StandardMaterial3D
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA; mat.roughness = .15; mat.cull_mode = BaseMaterial3D.CULL_DISABLED; glass.material_override = mat
	glass.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	for x in [-5.4,0.0,5.4]: _box("DividerPost",Vector3(x,1.4,0),Vector3(.055,2.5,.075),Color("7a8c8f"))
	_box("DividerTop",Vector3(0,2.66,0),Vector3(10.9,.06,.085),Color("7a8c8f"))
	for row in settings["stations"]:
		var entry: Dictionary = row.duplicate(true); stations.append(entry)
		_build_station(entry)
	for x in [-4.4,0.0,4.4]:
		_box("CeilingLight",Vector3(x,3.98,0),Vector3(2.0,.045,.15),Color("d5e3e0"),false,1.2)
		_spot("StationLight",Vector3(x,3.9,.15),Vector3(x,.8,0),Color("d9e6e2"),2.2,53)
	for side in [-1.0,1.0]:
		for x in [-3.7,3.7]:
			_fill("DeskRowSoftFill",Vector3(x,3.05,side*2.85),Color("c6d9e0") if side>0 else Color("edd9bb"),1.05,7.2)
	_fill("EntrySoftFill",Vector3(0,3.1,4.75),Color("d7e3da"),.58,7.0)
	_box("BackDisplay",Vector3(0,2.16,-6.36),Vector3(8.9,2.05,.10),Color("091319"))
	# Match banner on the studio's rear display; filled in _venue_ready once
	# the frozen roster (or the preview state) is known.
	match_board = Kit.led_screen(self,"LanMatchBoard",Vector3(0,2.62,-6.165),Vector2(8.4,.96),Vector2i(1680,192),0.0,1.0)
	for side in [-1.0,1.0]:
		_box("SideAcousticPanel",Vector3(side*6.43,2.18,-3.8),Vector3(.10,2.7,2.8),Color("172b34"))
		_box("WallAccent",Vector3(side*6.35,2.18,-3.8),Vector3(.025,2.4,.04),Color("a1c9c0"),false,.45)
	_box("EquipmentRack",Vector3(-5.48,.77,5.43),Vector3(.84,1.5,.72),Color("1a252f"),true)
	_sign("LAN / 选手入口",Vector3(3.2,2.05,6.32),.0042,PI)
	_sign("使用电脑选择当前生涯比赛",Vector3(3.2,1.62,6.31),.0027,PI,Color("9aafba"))
	var building := SceneTiers.apply_venue(self,null,int((Travel.match_visit.get("venue", {}) if Travel.match_visit.get("venue") is Dictionary else {}).get("capacity", Travel.match_visit.get("capacity",0))),"lan")
	# The studio's hanging sign becomes a small LED: team marks on match day.
	var title := building.get_node_or_null("StudioTitle") as Label3D if building else null
	if title:
		title.visible = false
		studio_board = Kit.led_screen(self,"StudioSignLED",title.global_position+Vector3(0,0,-.012),Vector2(5.9,.58),Vector2i(1475,145),0.0,1.0)

func _build_station(row: Dictionary) -> void:
	var seat := vec(row["seat"]); var screen := vec(row["screen"]); var side := signf(seat.z)
	var assembly := Node3D.new(); assembly.name = "Station_"+str(row["id"]); add_child(assembly)
	_box("Monitor",screen,Vector3(1.14,.71,.075),Color("111a21"),false,0,assembly)
	if row.get("player",false):
		_box("MonitorScreen",screen+Vector3(0,0,side*.041),Vector3(1.03,.60,.009),Color("142c36"),false,.38,assembly)
	else:
		# Other seats show an in-game frame (a quad, so the whole image maps
		# onto the panel); yours stays on the career app.
		var panel := MeshInstance3D.new(); panel.name = "MonitorScreen"
		var quad := QuadMesh.new(); quad.size = Vector2(1.03,.60); panel.mesh = quad
		panel.position = screen+Vector3(0,0,side*.0385); panel.rotation.y = 0.0 if side>0 else PI
		panel.material_override = Kit.screen_material(Kit.game_frame(hash(str(row["id"])),side<0),.85)
		panel.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		assembly.add_child(panel)
	_box("MonitorBezelLED",screen+Vector3(.40,-.33,side*.041),Vector3(.18,.008,.006),Color("6fc3b2") if side>0 else Color("e2a35d"),false,1.6,assembly)
	_box("MonitorStem",Vector3(screen.x,1.16,screen.z),Vector3(.06,.23,.075),Color("17212a"),false,0,assembly)
	_box("MonitorBase",Vector3(screen.x,1.075,screen.z),Vector3(.39,.025,.22),Color("101922"),false,0,assembly)
	_box("Keyboard",Vector3(seat.x,1.075,side*1.39),Vector3(.65,.035,.22),Color("121d27"),false,0,assembly)
	for n in range(3): _box("KeyRow",Vector3(seat.x,1.098,side*(1.31+n*.06)),Vector3(.59,.005,.007),Color("83b8b1"),false,.15,assembly)
	_box("Mousepad",Vector3(seat.x+.44,1.071,side*1.4),Vector3(.3,.015,.29),Color("15252d"),false,0,assembly)
	_box("Mouse",Vector3(seat.x+.44,1.094,side*1.4),Vector3(.065,.037,.10),Color("a9b4ae"),false,0,assembly)
	_box("ComputerTower",Vector3(seat.x+.69,.62,side*1.17),Vector3(.24,.77,.46),Color("101923"),false,0,assembly)
	_box("TowerLED",Vector3(seat.x+.69,.75,side*1.41),Vector3(.14,.009,.006),Color("69bba8"),false,.8,assembly)
	var accent := Kit.TEAM_A if side>0 else Kit.TEAM_B
	# Chicken-sized gaming chair: a wide low cushion the round body rests on
	# (top 0.56 m), a backrest behind the tail and low arms under the wings.
	var cz := seat.z-side*.25
	var dark := Color("1c252d")
	_box("PlayerChair",Vector3(seat.x,.52,cz),Vector3(.80,.08,.64),dark,false,0,assembly)
	_box("ChairSeatStripe",Vector3(seat.x,.562,cz),Vector3(.12,.006,.60),accent,false,.2,assembly)
	_box("ChairBack",Vector3(seat.x,.98,seat.z+side*.22),Vector3(.80,.78,.07),Color("1a222a"),false,0,assembly)
	_box("ChairHeadrest",Vector3(seat.x,1.46,seat.z+side*.23),Vector3(.46,.20,.08),Color("1a222a"),false,0,assembly)
	for bolster in [-1.0,1.0]:
		_box("ChairBolster",Vector3(seat.x+bolster*.37,1.0,seat.z+side*.21),Vector3(.07,.70,.10),accent,false,0,assembly)
		_box("ChairArm",Vector3(seat.x+bolster*.45,.68,cz),Vector3(.06,.05,.44),Color("12191f"),false,0,assembly)
		_box("ChairArmPost",Vector3(seat.x+bolster*.45,.60,cz),Vector3(.05,.12,.05),Color("12191f"),false,0,assembly)
	_cylinder("ChairStem",Vector3(seat.x,.33,cz),.055,.30,Color("14212b"),assembly)
	_box("ChairFeet",Vector3(seat.x,.20,cz),Vector3(.62,.05,.50),Color("14212b"),false,0,assembly)
	var face_angle := 0.0 if side>0 else PI
	if row.get("player",false):
		_sign("生涯比赛",screen+Vector3(0,.04,side*.052),.0022,face_angle,Color("a7d4cd"),assembly)
	_sign(str(row["id"]),screen+Vector3(-.44*side,-.326,side*.046),.0011,face_angle,Color("8fa3a6"),assembly).outline_size=0
	# Seat plates sit on the chair back, readable from the aisle behind it.
	var plate := _sign("你的席位" if row.get("player",false) else str(row["id"])+" 选手席",Vector3(seat.x,1.02,seat.z+side*.258),.0013,face_angle,Color("ffdfa0") if row.get("player",false) else Color("c9d6d6"),assembly)
	plate.outline_size=3
	if row.get("player",false):
		seat_marker = _sign("你的席位 ↓",Vector3(seat.x,1.66,seat.z+side*.1),.0021,0,Color("ffd27a"),assembly)
		seat_marker.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		seat_marker.outline_size = 8
	# ~25 small parts per seat: bake them into one mesh (one draw per material).
	Kit.merge_children(assembly)
	# The frozen preflight roster populates these seats after the room is built.

func _ambience_file() -> String: return ""

func _venue_ready() -> void:
	Music.stop_scene_music()
	if not CareerBridge.changed.is_connected(_draw_match_board): CareerBridge.changed.connect(_draw_match_board)
	roster_plan = Roster.plan(Travel.match_visit)
	if not roster_plan.is_empty():
		var own: Array = roster_plan["own"]; var other: Array = roster_plan["opponents"]
		for i in range(stations.size()):
			var row: Dictionary = stations[i]; var identity: Dictionary = own[i] if i < 5 else other[i - 5]
			row["identity"] = identity.duplicate(true)
			if bool(row.get("player", false)): continue
			var actor = Competitor.new(); actor.name = "Competitor_" + str(row["id"])
			actor.position = vec(row["seat"]) - Vector3.UP * .14; actor.home = actor.position
			actor.locked = true; actor.test_mode = true; actor.seat_pose = true
			actor.seat_lift = .56 - actor.position.y - .16; actor.seat_forward = .33
			add_child(actor)
			actor.setup_identity(identity, str(roster_plan["own_team"] if i < 5 else roster_plan["opponent_team"]), Color("355d72") if i < 5 else Color("ad6b3d"))
			actor.face_toward(vec(row["screen"])); actor.upper_body_action = "typing"; peers.append(actor)
			var name_label:=_sign(str(identity.get("name", "")), vec(row["seat"]) + Vector3(0,1.98,-.33 if i < 5 else .33), .00165, 0.0 if i < 5 else PI)
			name_label.billboard=BaseMaterial3D.BILLBOARD_ENABLED
	status.text = (str(roster_plan["own_team"]) + " 对阵 " + str(roster_plan["opponent_team"]) + " · 9 位选手已入座") if not roster_plan.is_empty() else "场地预览 · 尚未取得本场稳定阵容"
	_draw_match_board()
	var guidance := Travel.preview_match_hint("lan") if roster_plan.is_empty() else ""
	if not guidance.is_empty():
		status.text = str(Travel.match_guidance().get("display_name", "线下赛场"))
		_set_caption(guidance)
	else:
		_set_caption("找到“你的席位”，按 E 坐下")

func _polish_environment() -> void:
	# Bright studio: bloom only on emissive trims, never on cream walls.
	Kit.polish(env,0.0,true)
	env.glow_hdr_threshold = 1.3; env.glow_intensity = .4

func _update_venue(delta: float) -> void:
	if is_instance_valid(seat_marker):
		marker_clock += delta
		seat_marker.visible = not device_seated
		seat_marker.position.y = 1.66 + sin(marker_clock*2.4)*.035

func _draw_match_board() -> void:
	Kit.refresh(studio_board); Kit.refresh(match_board)
	var venue: Dictionary = Travel.match_visit.get("venue",{})
	var own := str(roster_plan.get("own_team","")); var other := str(roster_plan.get("opponent_team",""))
	if is_instance_valid(studio_board):
		var sign := studio_board
		Kit.clear(sign)
		Kit.gradient(sign,Color("2d5a52"),Color("1d3f39"))
		if roster_plan.is_empty():
			Kit.text_at(sign,"CAREER STUDIO",84,Rect2(0,0,sign.size.x,sign.size.y),Color("f6e9c9"))
		else:
			var row := HBoxContainer.new(); row.alignment = BoxContainer.ALIGNMENT_CENTER
			row.position = Vector2(0,10); row.size = Vector2(sign.size.x,sign.size.y-20); row.mouse_filter = Control.MOUSE_FILTER_IGNORE
			row.add_theme_constant_override("separation",24); sign.add_child(row)
			Kit.logo_tile(row,own,112)
			var left := Kit.text(row,own,68,Color("f6e9c9"),HORIZONTAL_ALIGNMENT_RIGHT); left.custom_minimum_size = Vector2(440,0)
			Kit.text(row,"VS",54,Kit.GOLD)
			var right := Kit.text(row,other,68,Color("f6e9c9"),HORIZONTAL_ALIGNMENT_LEFT); right.custom_minimum_size = Vector2(440,0)
			Kit.logo_tile(row,other,112)
	# Rear banner: event and format, in the band visible over the far monitors.
	if not is_instance_valid(match_board): return
	var root := match_board
	Kit.clear(root)
	Kit.gradient(root,Color("0f2a2e"),Color("071416"))
	var w := root.size.x; var h := root.size.y
	Kit.rect(root,Rect2(0,h-4,w,4),Color("6fc3b2"))
	Kit.rect(root,Rect2(0,0,w,2),Color("6fc3b2"))
	if roster_plan.is_empty():
		Kit.text_at(root,"CAREER LAN",70,Rect2(40,0,w*.42,h),Color("e8d6b1"),HORIZONTAL_ALIGNMENT_LEFT)
		Kit.text_at(root,"5 vs 5 · 小型线下比赛 · 你的席位位于前排中央",34,Rect2(w*.40,0,w*.6-40,h),Color("a9cfc8"),HORIZONTAL_ALIGNMENT_RIGHT)
		return
	var event_name := str(venue.get("event_name",""))
	var place := str(venue.get("name",""))
	if place.is_empty(): place = str(venue.get("city",""))
	Kit.text_at(root,event_name if not event_name.is_empty() else "线下比赛",62,Rect2(40,0,w*.58,h),Color("e8d6b1"),HORIZONTAL_ALIGNMENT_LEFT)
	Kit.text_at(root,Locale.text("5 vs 5 · 选手已入座") + (" · " + place if not place.is_empty() else ""),32,Rect2(w*.55,0,w*.45-40,h),Color("a9cfc8"),HORIZONTAL_ALIGNMENT_RIGHT)

func _nearest_target() -> String:
	var distance := INF; var result := ""
	for row in stations:
		var approach := vec(row["approach"]); var current := _distance(approach)
		if current<distance and _reachable(approach,.98): distance=current; result=str(row["id"])
	return result

func _station(id: String) -> Dictionary:
	for row in stations:
		if str(row["id"]) == id: return row
	return {}

func _hint_text() -> String:
	if device_seated: return "选手席 · 收起电脑后起身"
	if roster_plan.is_empty():
		var guidance := Travel.preview_match_hint("lan")
		if not guidance.is_empty(): return guidance
	if not target.is_empty() and not roster_plan.is_empty() and not _station(target).get("player", false): return "选手已入座 · 请使用前排中央你的席位"
	if not target.is_empty(): return "E 坐进"+("你的席位" if _station(target).get("player",false) else target+" 选手席")+" / 打开生涯比赛"
	return "沿桌后通道走动 · 侧边通道通往另一排"

func interact() -> void:
	if target.is_empty() or device_seated: return
	if not roster_plan.is_empty() and not _station(target).get("player", false): return
	selected_station = _station(target); seat_serial += 1
	var serial := seat_serial
	_seat(selected_station)
	await camera_tween.finished
	if serial != seat_serial or not device_seated or not is_inside_tree() or Travel.busy: return
	if Computer.has_method("open_app"): Computer.open_app("career_match","lan")
	else: Computer.present("lan")

func _seat(row: Dictionary) -> void:
	if row.is_empty() or device_seated: return
	Travel.close_menu(); device_approach = player.global_position; device_seated = true
	player.locked = true; player.velocity = Vector3.ZERO; player.seat_pose = true
	player.global_position = vec(row["seat"]); player.reset_physics_interpolation(); player.face_toward(vec(row["screen"]))
	player.upper_body_action = "typing"; camera_owned = true
	var at := vec(row["seat"])+Vector3.UP*1.17
	var view := Transform3D(Basis.IDENTITY,at).looking_at(vec(row["screen"]),Vector3.UP)
	if camera_tween and camera_tween.is_valid(): camera_tween.kill()
	camera_tween = create_tween(); camera_tween.set_trans(Tween.TRANS_CUBIC); camera_tween.set_ease(Tween.EASE_IN_OUT)
	camera_tween.tween_property(camera,"global_transform",view,.72)

func before_computer() -> void:
	super.before_computer()
	if device_seated: return
	# A device shortcut must not silently teleport a competing player into a seat.
	if not roster_plan.is_empty(): return
	if selected_station.is_empty():
		for row in stations:
			if row.get("player",false): selected_station=row; break
	_seat(selected_station)

func before_phone() -> void:
	super.before_phone(); _leave_computer()

func set_device_open(value: bool, kind: String) -> void:
	super.set_device_open(value,kind)
	if value and kind == "computer": before_computer()
	elif not value or kind == "phone": _leave_computer()

func _leave_computer() -> void:
	if not device_seated: return
	seat_serial += 1; device_seated = false
	if camera_tween and camera_tween.is_valid(): camera_tween.kill()
	player.global_position = device_approach; player.reset_physics_interpolation(); body_y = player.position.y
	player.seat_pose = false; player.upper_body_action = ""; player.velocity = Vector3.ZERO
	player.locked = CareerBridge.phone_open
	var view := Transform3D(Basis.from_euler(Vector3(pitch,yaw,0)),device_approach+Vector3.UP*float(settings["eye_height"]))
	camera_tween = create_tween(); camera_tween.set_trans(Tween.TRANS_CUBIC); camera_tween.set_ease(Tween.EASE_IN_OUT)
	camera_tween.tween_property(camera,"global_transform",view,.38)
	camera_tween.finished.connect(func(): camera_owned=false)

func after_computer() -> void: _leave_computer()

func _capture_view() -> void:
	player.position = Vector3(5.65,.11,4.6); player.reset_physics_interpolation(); body_y=player.position.y
	yaw=.72; pitch=-.10; camera.position=player.position+Vector3.UP*1.34; camera.rotation=Vector3(pitch,yaw,0)

func diagnostic_snapshot() -> Dictionary:
	return {"destination":"lan","stations":stations.size(),"teams":2,"seats_per_team":5,"glass_divider":has_node("GlassDivider"),"spectators":0,"enclosed":has_node("ClosedCeiling"),"seated":device_seated,"peers":peers.size(),"roster_ready":not roster_plan.is_empty(),"colliders":collision_count,"launches_cs2":false}

func match_seated(match_id: String) -> bool:
	return not roster_plan.is_empty() and str(roster_plan.get("match_id", "")) == match_id and device_seated and bool(selected_station.get("player", false))
