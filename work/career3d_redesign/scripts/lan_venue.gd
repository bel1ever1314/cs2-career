extends "res://scripts/small_venue_base.gd"
## Ten opposing stations; entering the computer never launches CS2 here.
const Roster = preload("res://scripts/venue_match_roster.gd")
const Competitor = preload("res://scripts/venue_competitor.gd")
var stations: Array[Dictionary] = []
var roster_plan: Dictionary = {}
var peers: Array[Node3D] = []
var device_seated := false
var device_approach := Vector3.ZERO
var selected_station: Dictionary = {}
var seat_serial := 0

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
	_sign("CAREER LAN",Vector3(0,2.62,-6.28),.009,0,Color("e8d6b1"))
	_sign("5 vs 5  /  小型线下比赛",Vector3(0,1.83,-6.27),.0044)
	_sign("你的席位位于前排中央",Vector3(0,1.42,-6.27),.003,0,Color("8db8b2"))
	for side in [-1.0,1.0]:
		_box("SideAcousticPanel",Vector3(side*6.43,2.18,-3.8),Vector3(.10,2.7,2.8),Color("172b34"))
		_box("WallAccent",Vector3(side*6.35,2.18,-3.8),Vector3(.025,2.4,.04),Color("a1c9c0"),false,.45)
	_box("EquipmentRack",Vector3(-5.48,.77,5.43),Vector3(.84,1.5,.72),Color("1a252f"),true)
	_sign("LAN / 选手入口",Vector3(3.2,2.05,6.32),.0042,PI)
	_sign("使用电脑选择当前生涯比赛",Vector3(3.2,1.62,6.31),.0027,PI,Color("9aafba"))

func _build_station(row: Dictionary) -> void:
	var seat := vec(row["seat"]); var screen := vec(row["screen"]); var side := signf(seat.z)
	var assembly := Node3D.new(); assembly.name = "Station_"+str(row["id"]); add_child(assembly)
	_box("Monitor",screen,Vector3(1.14,.71,.075),Color("111a21"),false,0,assembly)
	_box("MonitorScreen",screen+Vector3(0,0,side*.041),Vector3(1.03,.60,.009),Color("142c36") if side>0 else Color("342b21"),false,.38,assembly)
	_box("MonitorStem",Vector3(screen.x,1.16,screen.z),Vector3(.06,.23,.075),Color("17212a"),false,0,assembly)
	_box("MonitorBase",Vector3(screen.x,1.075,screen.z),Vector3(.39,.025,.22),Color("101922"),false,0,assembly)
	_box("Keyboard",Vector3(seat.x,1.075,side*1.39),Vector3(.65,.035,.22),Color("121d27"),false,0,assembly)
	for n in range(3): _box("KeyRow",Vector3(seat.x,1.098,side*(1.31+n*.06)),Vector3(.59,.005,.007),Color("83b8b1"),false,.15,assembly)
	_box("Mousepad",Vector3(seat.x+.44,1.071,side*1.4),Vector3(.3,.015,.29),Color("15252d"),false,0,assembly)
	_box("Mouse",Vector3(seat.x+.44,1.094,side*1.4),Vector3(.065,.037,.10),Color("a9b4ae"),false,0,assembly)
	_box("ComputerTower",Vector3(seat.x+.69,.62,side*1.17),Vector3(.24,.77,.46),Color("101923"),false,0,assembly)
	_box("TowerLED",Vector3(seat.x+.69,.75,side*1.41),Vector3(.14,.009,.006),Color("69bba8"),false,.8,assembly)
	_box("PlayerChair",Vector3(seat.x,.6,seat.z),Vector3(.64,.11,.66),Color("263e48"),false,0,assembly)
	_box("ChairBack",Vector3(seat.x,.96,seat.z+side*.29),Vector3(.64,.65,.075),Color("22343e"),false,0,assembly)
	_cylinder("ChairStem",Vector3(seat.x,.39,seat.z),.055,.30,Color("14212b"),assembly)
	_box("ChairFeet",Vector3(seat.x,.26,seat.z),Vector3(.58,.06,.45),Color("14212b"),false,0,assembly)
	var face_angle := 0.0 if side>0 else PI
	_sign("生涯比赛" if row.get("player",false) else str(row["id"])+" / LAN",screen+Vector3(0,.10,side*.052),.00165,face_angle,Color("a7d4cd"),assembly)
	_sign("你的席位" if row.get("player",false) else str(row["id"])+" 选手席",Vector3(seat.x,1.36,seat.z+side*.32),.00175,face_angle,Color("ffdfa0") if row.get("player",false) else Color("b7c8c9"),assembly)
	# The frozen preflight roster populates these seats after the room is built.

func _venue_ready() -> void:
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
			add_child(actor)
			actor.setup_identity(identity, str(roster_plan["own_team"] if i < 5 else roster_plan["opponent_team"]), Color("355d72") if i < 5 else Color("ad6b3d"))
			actor.face_toward(vec(row["screen"])); actor.upper_body_action = "typing"; peers.append(actor)
			var name_label:=_sign(str(identity.get("name", "")), vec(row["seat"]) + Vector3(0,1.52,.36 if i < 5 else -.36), .00165, 0.0 if i < 5 else PI)
			name_label.billboard=BaseMaterial3D.BILLBOARD_ENABLED
	status.text = (str(roster_plan["own_team"]) + " 对阵 " + str(roster_plan["opponent_team"]) + " · 9 位选手已入座") if not roster_plan.is_empty() else "场地预览 · 尚未取得本场稳定阵容"
	_set_caption("走到前排中央的“你的席位”，按 E 坐下使用电脑。")

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
