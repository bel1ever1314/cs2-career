extends "res://scripts/small_venue_base.gd"
## Original ceremony set, inspired by annual esports award shows. No HLTV marks.
## The hall reads the frozen annual archive only: a Top20 countdown runs on the
## LED wall, then the top three are called up one by one to the podium.
const ChickenMesh = preload("res://scripts/chicken_mesh.gd")
const Competitor = preload("res://scripts/venue_competitor.gd")
const Fmt = preload("res://scripts/ui_format.gd")
const Audio = preload("res://scripts/ceremony_audio.gd")
var finalized := false
var preview := true
var awards_year := ""
var award_rows: Array[Dictionary] = []
var attendee_rows: Array[Dictionary] = []
var human_id := ""
var guest_actors: Dictionary = {}
var guest_homes: Dictionary = {}
var guest_trophies: Dictionary = {}
var current_index := -1
var ceremony_phase := "idle"
var ceremony_clock := 0.0
var ceremony_speed := 1.0
var active_actor: Player
var actor_route: Array[Vector3] = []
var route_index := 0
var called_ranks: Array[int] = []
var awarded_ranks: Array[int] = []
var completed_ranks: Array[int] = []
# Hidden text mirrors of what the LED walls show (kept for diagnostics/tests).
var ceremony_name: Label3D
var ceremony_banner: Label3D
var ranking_board: Label3D
var player_trophy: Node3D
var audience_return_point := Vector3(0,0,.8)
var audience_count := 0
var static_guest_count := 0
var recipient_attendee_ids: Array[String] = []
var ceremony_source := "preview"
var top20_rows: Array[Dictionary] = []
var annual_board: Label3D
# Countdown through the archived Top20 (#20 … #4) before the podium calls.
var countdown_rows: Array[Dictionary] = []
var countdown_index := -1
var countdown_seen: Array[int] = []
# LED walls and show lighting.
var main_led: Control
var left_led: Control
var right_led: Control
var top20_led: Control
var roster_led: Control
var led_state := ""
var follow_spot: SpotLight3D
var follow_energy := 0.0
var confetti: CPUParticles3D
var stage_beams: Array[SpotLight3D] = []
var show_clock := 0.0
var guest_groups: Array = []
# Suspense: every name stays sealed until its own reveal; house lights dim and
# two search lights sweep the seats while the drum roll builds.
var revealed: Dictionary = {}
var display_trophies: Dictionary = {}
var house_lights: Array[Light3D] = []
var house_level := 1.0
var search_spots: Array[SpotLight3D] = []
var search_energy := 0.0
var led_flash: ColorRect
const TEASE_TOP := 3.6
const REVEAL_HOLD := 1.8

const RANK_WORDS := {1:"第一",2:"第二",3:"第三"}

func _destination() -> String: return "awards"
func _data_path() -> String: return "res://data/awards_venue.json"

func _polish_environment() -> void:
	# Faint haze lets the stage heads draw beams on Forward+; the floor and
	# stage reflect the LED wall through screen-space reflections.
	Kit.polish(env,.012,true)

func _build_venue() -> void:
	_enclosure(20.0,24.0,5.7)
	env.background_color=Color("070a12")
	env.ambient_light_energy=.42;env.ambient_light_color=Color("b4b2c6")
	_restyle_shell()
	_box("CeremonyCarpet",Vector3(0,.015,1.8),Vector3(3.8,.03,17.4),Color("5c1d29"))
	for side in [-1.0,1.0]:
		_box("AisleGoldEdge",Vector3(side*1.94,.04,1.8),Vector3(.035,.035,17.4),Color("c9a35d"),false,.55)
		for z in [-7.0,0.0,7.0]:
			_box("WallAcoustic",Vector3(side*9.83,2.8,z),Vector3(.10,4.4,3.5),Color("2c3247"))
			_box("WallSconce",Vector3(side*9.72,2.3,z),Vector3(.03,.8,.10),Color("f0cf8f"),false,1.4)
			_spot("WarmWallWash",Vector3(side*9.6,4.3,z),Vector3(side*7.4,0,z),Color("ffd3a1"),1.8,42).set_meta("house",true)
		for z in [-10.4,-3.5]:
			Kit.strip(self,"WallGoldStrip",Vector3(side*9.76,2.8,z),Vector3(.03,4.4,.05),Color("e7bf73"),1.8)
		# Ceiling cove: a warm line along each long wall outlines the room.
		Kit.strip(self,"CeilingCove",Vector3(side*9.7,5.5,0),Vector3(.05,.05,23.4),Color("f2cf8c"),1.2)
	_box("AwardsStage",Vector3(0,.30,-8.55),Vector3(17.4,.60,5.3),Color("14171e"),true)
	(get_node("AwardsStage") as MeshInstance3D).material_override=Kit.material(Color("14171e"),0.0,.22,.15)
	_box("StageFrontTrim",Vector3(0,.47,-5.86),Vector3(17.4,.045,.04),Color("e2bd72"),false,1.4)
	Kit.strip(self,"StageLipGlow",Vector3(0,.075,-5.88),Vector3(17.4,.03,.03),Color("e2bd72"),2.2)
	_box("StageFascia",Vector3(0,.28,-5.885),Vector3(17.4,.34,.015),Color("1a1d26"))
	for i in range(4):
		_box("StageStep"+str(i),Vector3(0,.075*(i+1),-4.89-i*.36),Vector3(4.8,.15*(i+1),.38),Color("262a33"))
		_box("StepNosing",Vector3(0,.15*(i+1)+.008,-4.72-i*.36),Vector3(4.77,.016,.023),Color("d8b46d"),false,.9)
	# One continuous walk surface avoids capsule snagging on the decorative treads.
	var ramp:=StaticBody3D.new();ramp.name="StageAccessRamp";add_child(ramp)
	var ramp_shape:=ConvexPolygonShape3D.new();var points:=PackedVector3Array()
	for x in [-2.4,2.4]:
		points.append(Vector3(x,0,-4.7));points.append(Vector3(x,.60,-5.9));points.append(Vector3(x,-.12,-4.7));points.append(Vector3(x,-.12,-5.9))
	ramp_shape.points=points;var ramp_collision:=CollisionShape3D.new();ramp_collision.shape=ramp_shape;ramp.add_child(ramp_collision);collision_count+=1
	_build_backdrop()
	for rank in [3,1,2]:
		var x: float = _podium_x(rank)
		var height := .95 if rank==1 else (.66 if rank==2 else .48)
		_box("Podium"+str(rank),Vector3(x,.6+height*.5,-9.12),Vector3(1.46,height,.86),Color("1c2029"),true)
		(get_node("Podium"+str(rank)) as MeshInstance3D).material_override=Kit.material(Color("1c2029"),0.0,.3,.2)
		_box("PodiumGoldCap",Vector3(x,.6+height,-9.12),Vector3(1.49,.032,.89),Color("d4b06b"),false,.35)
		Kit.strip(self,"PodiumGlow",Vector3(x,.62,-8.68),Vector3(1.46,.02,.02),Color("e2bd72"),2.0)
		var number:=_sign(str(rank),Vector3(x,.6+height*.6,-8.684),.0062,0,Color("e9c67f"))
		number.outline_size=0
		_sign("TOP "+str(rank),Vector3(x,.665,-8.684),.0016,0,Color("b9a98a")).outline_size=0
		var trophy_holder:=Node3D.new();trophy_holder.position=Vector3(x,.6+height+.024,-9.12);add_child(trophy_holder)
		display_trophies[rank]=_trophy("DisplayAward"+str(rank),trophy_holder,.8)
	_box("HostLectern",Vector3(-6.5,1.08,-7.93),Vector3(.95,.94,.68),Color("1f232d"),true)
	_box("LecternGoldEdge",Vector3(-6.5,1.56,-7.93),Vector3(.99,.03,.72),Color("d4b06b"),false,.6)
	Kit.strip(self,"LecternGlow",Vector3(-6.5,.66,-7.58),Vector3(.95,.02,.02),Color("e2bd72"),2.0)
	_sign("年度荣誉",Vector3(-6.5,1.13,-7.585),.0025,0,Color("e9c67f"))
	_cylinder("MicrophoneStem",Vector3(-6.28,1.78,-7.98),.018,.46,Color("111a21"))
	_box("Microphone",Vector3(-6.28,2.02,-7.95),Vector3(.035,.055,.14),Color("bcb6a4"))
	_build_rig()
	for x in [-4.8,4.8]:
		_fill("StageFrontSoftKey",Vector3(x,3.3,-6.3),Color("ffe0ac"),1.5,8.0)
	for side in [-1.0,1.0]:
		for z in [-1.7,3.9,8.4]:
			_fill("GuestSeatSoftFill",Vector3(side*5.3,3.2,z),Color("e2cfb0") if side<0 else Color("b6c6d6"),1.0,7.8).set_meta("house",true)
	for z in [-3.2,2.9,9.0]:
		_fill("CentralAisleFill",Vector3(0,3.25,z),Color("c9b9a6"),.62,6.8).set_meta("house",true)
	# Upholstered benches border a wide continuous central aisle.
	for side in [-1.0,1.0]:
		for z in [-2.0,.65,3.30,5.95,8.60]:
			# Low upholstered benches: seat top 0.30 m, the height a chicken sits at.
			_box("GuestBench",Vector3(side*5.48,.24,z),Vector3(6.85,.12,.66),Color("3a4466"),true)
			_box("BenchBack",Vector3(side*5.48,.58,z+.34),Vector3(6.85,.66,.075),Color("2b3352"),true)
			_box("BenchPiping",Vector3(side*5.48,.915,z+.34),Vector3(6.85,.025,.085),Color("c9a35d"),false,.25)
			for x in [-2.30,2.30]:_box("BenchFoot",Vector3(side*5.48+x,.09,z),Vector3(.08,.18,.52),Color("121520"))
	_box("WelcomePanel",Vector3(-6.8,1.71,11.80),Vector3(4.7,2.45,.10),Color("141826"))
	_box("WelcomeFrame",Vector3(-6.8,2.95,11.74),Vector3(4.7,.03,.03),Color("e2bd72"),false,1.2)
	_sign("选手之夜\n年度荣誉典礼",Vector3(-6.8,2.0,11.73),.0055,PI,Color("f0d9a8"))
	_sign("中央台阶通往领奖台",Vector3(-6.8,1.12,11.72),.0029,PI,Color("b6c0b9"))
	_sign("嘉宾席 / 观礼区",Vector3(6.0,2.48,11.76),.0042,PI)
	_box("AnnualTop20Backing",Vector3(-9.72,2.48,3.0),Vector3(.06,3.7,7.4),Color("0d1018"))
	Kit.strip(self,"Top20Frame",Vector3(-9.69,4.36,3.0),Vector3(.03,.03,7.4),Color("e2bd72"),1.6)
	Kit.strip(self,"Top20Frame",Vector3(-9.69,.62,3.0),Vector3(.03,.03,7.4),Color("e2bd72"),1.6)
	top20_led=Kit.led_screen(self,"AnnualTop20Wall",Vector3(-9.67,2.49,3.0),Vector2(7.2,3.6),Vector2i(1440,720),PI*.5,1.0)
	var top20_wall := Node3D.new(); top20_wall.name="AnnualTop20Mirror"; top20_wall.position = Vector3(-9.65,2.5,3.0); top20_wall.rotation.y = PI * .5; add_child(top20_wall)
	annual_board = _sign("",Vector3.ZERO,.00225,0,Color("ebd2a0"),top20_wall)
	annual_board.visible=false
	confetti=Kit.confetti(self,Vector3(0,5.35,-8.4),Vector3(6.5,.1,2.0))
	for light in find_children("*","Light3D",false,false):
		if light.has_meta("house"):
			light.set_meta("base_energy",light.light_energy); house_lights.append(light)

func _restyle_shell() -> void:
	# The shared enclosure is generic; the hall gets a glossy floor that picks
	# up the stage and soft plum-navy walls instead of flat blue-black.
	for child in get_children():
		if not child is MeshInstance3D: continue
		var id := str(child.get_meta("venue_authored_id",child.name))
		match id:
			"Floor": child.material_override=Kit.material(Color("1a1f2b"),0.0,.3,.08)
			"BackWall","EntryWall": child.material_override=Kit.material(Color("232838"),0.0,.85)
			"SideWall": child.material_override=Kit.material(Color("262b3c"),0.0,.85)
			"ClosedCeiling": child.material_override=Kit.material(Color("12141c"),0.0,.9)
	# Small recessed downlights across the ceiling give it scale.
	for x in [-6.0,-2.0,2.0,6.0]:
		for z in [-2.0,3.0,8.0]:
			Kit.cylinder(self,"CeilingDownlight",Vector3(x,5.69,z),.09,.02,Kit.material(Color("ffe9c4"),2.4,.3),12)

func _build_backdrop() -> void:
	_box("StageBackdrop",Vector3(0,2.80,-11.33),Vector3(17.8,4.45,.13),Color("0a0c12"))
	# Gold slats frame the LED wall; the original repeated light pillars stay.
	for x in [-8.0,-5.12,5.12,8.0]:
		_box("GoldPillar",Vector3(x,2.76,-11.18),Vector3(.085,3.9,.075),Color("d9b46b"),false,1.1)
	main_led=Kit.led_screen(self,"CeremonyLED",Vector3(0,3.12,-11.255),Vector2(9.6,3.6),Vector2i(1600,600),0.0,1.15)
	left_led=Kit.led_screen(self,"CeremonyWingLeft",Vector3(-6.56,2.82,-11.255),Vector2(2.2,3.9),Vector2i(352,624),0.0,1.0)
	right_led=Kit.led_screen(self,"CeremonyWingRight",Vector3(6.56,2.82,-11.255),Vector2(2.2,3.9),Vector2i(352,624),0.0,1.0)
	Kit.strip(self,"LedFrameTop",Vector3(0,4.95,-11.25),Vector3(9.7,.035,.03),Color("e2bd72"),1.6)
	Kit.strip(self,"LedFrameBottom",Vector3(0,1.29,-11.25),Vector3(9.7,.035,.03),Color("e2bd72"),1.6)
	# Hidden data mirrors of the LED content.
	ceremony_banner=_sign("年度选手颁奖",Vector3(0,3.63,-11.17),.004); ceremony_banner.visible=false
	ceremony_name=_sign("TOP 3  /  TOP 2  /  TOP 1",Vector3(0,2.66,-11.16),.008,0,Color("f0e4c7")); ceremony_name.visible=false
	ranking_board=_sign("",Vector3(7.95,2.1,-10.76),.0021); ranking_board.visible=false

func _build_rig() -> void:
	# Two hanging trusses carry the stage heads. Lights keep their original
	# positions and energies; the trusses only make them read as a real rig.
	Kit.truss(self,"FrontStageTruss",Vector3(0,5.25,-4.9),16.4)
	Kit.truss(self,"RearStageTruss",Vector3(0,5.25,-10.5),16.4)
	for x in [-5.8,0.0,5.8]:
		var spot:=_spot("StageSpot",Vector3(x,5.47,-4.9),Vector3(x*.6,1.25,-8.9),Color("ffe0aa"),5.8,35)
		Kit.beam(spot,1.0); stage_beams.append(spot)
		Kit.fixture(self,"StageHead",Vector3(x,5.02,-4.9),Vector3(x*.6,1.25,-8.9))
	for x in [-7.2,-2.4,2.4,7.2]:
		var back:=_spot("BackLight",Vector3(x,5.1,-10.5),Vector3(x*.8,0,-5.5),Color("e8c27c") if absf(x)>3 else Color("bcd2ff"),1.6,24)
		back.shadow_enabled=false; back.set_meta("breathes",true); Kit.beam(back,1.6); stage_beams.append(back)
		Kit.fixture(self,"BackHead",Vector3(x,5.02,-10.5),Vector3(x*.8,0,-5.5),Color("ffe4b0"))
	var host:=_spot("HostSpot",Vector3(-6.4,5.4,-7.0),Vector3(-6.5,1.4,-8.0),Color("ffe4b7"),3.1,28)
	Kit.beam(host,.6)
	follow_spot=_spot("FollowSpot",Vector3(0,5.45,-1.2),Vector3(0,1.4,-8.6),Color("fff3dc"),0.0,13)
	follow_spot.shadow_enabled=false; follow_spot.spot_range=16; Kit.beam(follow_spot,2.2)
	Kit.fixture(self,"FollowSpotHead",Vector3(0,5.3,-1.2),Vector3(0,1.4,-8.6),Color("fff6e4"))
	for x in [-3.4,3.4]:
		var search:=_spot("SearchSpot",Vector3(x,5.42,-4.6),Vector3(x,0,-1.0),Color("f6f1ff"),0.0,9)
		search.shadow_enabled=false; search.spot_range=18; search.visible=false; Kit.beam(search,2.4); search_spots.append(search)

func _ambience_file() -> String: return "crowd_awards_hall.ogg"
func _ambience_trim() -> float: return 0.85

func _venue_ready() -> void:
	_load_awards()
	_create_guests()
	if not CareerBridge.changed.is_connected(_career_changed):CareerBridge.changed.connect(_career_changed)

func _valid_finalized(source: Dictionary) -> bool:
	if not bool(source.get("finalized",false)) or not bool(source.get("ready",false)):return false
	var rows=source.get("top3",[])
	if not rows is Array or rows.size()!=3:return false
	var seen: Dictionary={}
	for row in rows:
		if not row is Dictionary:return false
		var rank:=int(row.get("rank",0));var actual_name:=str(row.get("name",row.get("player","")))
		if rank<1 or rank>3 or seen.has(rank) or actual_name.strip_edges().is_empty():return false
		seen[rank]=true
	return seen.size()==3 and source.get("year")!=null

func _load_awards(source_override: Dictionary = {}) -> void:
	var source: Dictionary = source_override
	if source.is_empty(): source = Travel.awards_visit if not Travel.awards_visit.is_empty() else CareerBridge.context.get("awards",{})
	source = Fmt.normalize(source.duplicate(true))
	finalized=_valid_finalized(source);preview=not finalized
	human_id=str(source.get("human_id",CareerBridge.context.get("player",{}).get("id","")))
	award_rows.clear();attendee_rows.clear();top20_rows.clear();countdown_rows.clear()
	if finalized:
		awards_year=str(source["year"]);ceremony_source=str(source.get("source","season.top20"))
		for row in source["top3"]:award_rows.append(row.duplicate(true))
		for row in source.get("top20", []):
			if row is Dictionary and int(row.get("rank",0)) in range(1,21): top20_rows.append(row.duplicate(true))
		top20_rows.sort_custom(func(a,b):return int(a["rank"])<int(b["rank"]))
		for row in top20_rows:
			if int(row["rank"])>3: countdown_rows.append(row)
		countdown_rows.reverse()
	else:
		awards_year="预览";ceremony_source="preview"
		for row in settings["preview_top3"]:award_rows.append(row.duplicate(true))
	for row in source.get("attendees",[]):
		if row is Dictionary:attendee_rows.append(row.duplicate(true))
	if attendee_rows.is_empty():
		for i in range(50):attendee_rows.append({"name":"预览嘉宾 %02d"%(i+1),"player_id":"preview_guest_"+str(i),"team":"一线选手嘉宾区（预览）"})
	award_rows.sort_custom(func(a,b):return int(a["rank"])>int(b["rank"]))
	ceremony_banner.text=awards_year+" 年度前三 · 已结算生涯" if finalized else "预览典礼 · 尚无已结算年度排名"
	ranking_board.text=(awards_year+" 年度前三\n\n" if finalized else "示例席位 / 预览\n\n")
	for row in award_rows:ranking_board.text += "#%d  %s\n"%[int(row["rank"]),_row_name(row)]
	if is_instance_valid(annual_board):
		annual_board.text = awards_year + " 年度正式 Top20\n\n" if finalized else "尚无年度正式 Top20\n\n预览不生成年度获奖名单"
		for row in top20_rows: annual_board.text += "#%02d  %s\n" % [int(row["rank"]),_row_name(row)]
		if finalized and top20_rows.is_empty(): annual_board.text += "完整榜单暂未提供；台上仅显示已归档前三。"
	status.text=("%s 年度颁奖礼" % awards_year) if finalized else "预览典礼"
	_set_caption("走到中央通道前端，按 E 开始颁奖。" if finalized else "还没有年度结果，这是一场用示例姓名的预览典礼。")
	if is_instance_valid(main_led): _refresh_led(true)
	if is_instance_valid(roster_led): _draw_roster()

func _row_name(row: Dictionary) -> String:return str(row.get("name",row.get("player","")))
func _podium_x(rank: int) -> float:return -3.25 if rank==3 else (3.25 if rank==2 else 0.0)
func _podium_spot(rank: int) -> Vector3:return Vector3(_podium_x(rank),.61,-7.45)
func _is_human(row: Dictionary) -> bool:return finalized and not human_id.is_empty() and str(row.get("player_id",""))==human_id

func _attendance_plan(attendees: Array, winners: Array) -> Dictionary:
	# Only a stable ID occurring once in each list can join these two projections.
	# A winner not on today's roster remains a separate invited recipient.
	var winner_counts: Dictionary={};var attendee_counts: Dictionary={}
	for row in winners:
		var id:=str(row.get("player_id",""))
		if not id.is_empty():winner_counts[id]=int(winner_counts.get(id,0))+1
	for row in attendees.slice(0,50):
		var id:=str(row.get("player_id",""))
		if not id.is_empty():attendee_counts[id]=int(attendee_counts.get(id,0))+1
	var crowd_rows: Array[Dictionary]=[];var represented_ids: Array[String]=[]
	for row in attendees.slice(0,50):
		var id:=str(row.get("player_id",""))
		if not id.is_empty() and int(winner_counts.get(id,0))==1 and int(attendee_counts.get(id,0))==1:
			represented_ids.append(id)
		else:crowd_rows.append(row)
	return {"crowd_rows":crowd_rows,"recipient_ids":represented_ids,"total_attendees":mini(50,attendees.size())}

func _create_guests() -> void:
	var host=_actor("CeremonyHost",Vector3(-6.5,.61,-8.65));host.face_toward(Vector3(0,.61,0));host.locked=true
	# The three finalists sit in name order, so the seating does not leak the
	# final ranking before it is announced.
	var seating: Array[Dictionary]=award_rows.duplicate()
	seating.sort_custom(func(a,b):return _row_name(a).naturalnocasecmp_to(_row_name(b))<0)
	for i in range(seating.size()):
		var row: Dictionary=seating[i];var rank:=int(row["rank"])
		var home:=Vector3(-3.3-i*1.15,.02,-3.6)
		guest_homes[rank]=home
		# Wide nominee armchair sized for a seated chicken: body on the
		# cushion (top 0.51 m), backrest behind the tail feathers.
		_box("RecipientChair",home+Vector3(0,.25,.04),Vector3(.82,.10,.64),Color("3b3226"))
		_box("RecipientChairBase",home+Vector3(0,.10,.04),Vector3(.74,.2,.56),Color("2c261e"))
		_box("RecipientChairBack",home+Vector3(0,.70,.52),Vector3(.82,.84,.07),Color("2c261e"))
		_box("RecipientChairGold",home+Vector3(0,1.13,.52),Vector3(.82,.025,.08),Color("d4b06b"),false,.4)
		for arm in [-1.0,1.0]:_box("RecipientChairArm",home+Vector3(arm*.44,.42,.10),Vector3(.07,.22,.56),Color("2c261e"))
		if _is_human(row):continue
		var actor=_actor("Recipient"+str(rank),home);actor.seat_pose=true;actor.locked=true;actor.face_toward(Vector3(home.x,.02,-9))
		actor.seat_lift=.30-home.y-.16
		guest_actors[rank]=actor
		_sign(_row_name(row),Vector3(home.x,2.02,home.z+.05),.0017).billboard=BaseMaterial3D.BILLBOARD_ENABLED
	# Shared seated-spectator design; guests sit on the hall's own benches, so
	# only body and dangling legs are drawn. Display-only guests have no physics.
	var material:=ChickenMesh.material()
	var poses: Array[Transform3D]=[]
	var attendance:=_attendance_plan(attendee_rows,award_rows)
	var crowd_rows: Array[Dictionary]=attendance["crowd_rows"]
	recipient_attendee_ids.assign(attendance["recipient_ids"])
	for i in range(crowd_rows.size()):
		var side: float=-1 if i%2==0 else 1
		var row:=int(i/10);var slot:=int(i/2)%5
		var at:=Vector3(side*(2.85+slot*1.30),0,-2.04+row*2.65)
		poses.append(Transform3D(Basis(Vector3.UP,PI),at))
		if i<6:_sign(_row_name(crowd_rows[i]),at+Vector3(0,1.25,.02),.00165).billboard=BaseMaterial3D.BILLBOARD_ENABLED
	static_guest_count=poses.size();audience_count=int(attendance["total_attendees"])
	for definition in [["GuestBodies",ChickenMesh.seated_chicken(2,true)],["GuestLegs",ChickenMesh.legs_mesh()]]:
		var multimesh:=MultiMesh.new();multimesh.transform_format=MultiMesh.TRANSFORM_3D;multimesh.use_custom_data=true;multimesh.use_colors=true;multimesh.mesh=definition[1];multimesh.instance_count=poses.size()
		for i in range(poses.size()):
			multimesh.set_instance_transform(i,poses[i]);multimesh.set_instance_custom_data(i,ChickenMesh.tint(i));multimesh.set_instance_color(i,Color.WHITE)
		var batch:=MultiMeshInstance3D.new();batch.name=definition[0];batch.multimesh=multimesh;batch.material_override=material;add_child(batch)
	var roster_board:=Node3D.new();roster_board.name="CurrentRosterGuestList";roster_board.position=Vector3(9.72,2.56,4.55);roster_board.rotation.y=-PI*.5;add_child(roster_board)
	_box("RosterBacking",Vector3(0,0,-.035),Vector3(7.4,3.70,.06),Color("0d1018"),false,0,roster_board)
	Kit.strip(roster_board,"RosterFrame",Vector3(0,1.86,-.01),Vector3(7.4,.03,.03),Color("e2bd72"),1.6)
	Kit.strip(roster_board,"RosterFrame",Vector3(0,-1.86,-.01),Vector3(7.4,.03,.03),Color("e2bd72"),1.6)
	roster_led=Kit.led_screen(roster_board,"GuestRosterWall",Vector3(0,0,.004),Vector2(7.2,3.6),Vector2i(1440,720),0.0,1.0)
	_draw_roster()

func _actor(id: String, at: Vector3) -> Player:
	var actor:=Competitor.new();actor.npc_id=id;actor.name=id;actor.position=at;actor.home=at;actor.test_mode=true
	actor.walk_speed=2.4;actor.run_speed=2.4;actor.step_height=.21;actor.floor_snap_length=.32;add_child(actor)
	# Dark formal jackets keep the established chicken identity visible.
	for mesh in actor.visual.find_children("*","MeshInstance3D",true,false):
		if str(mesh.name).replace("_"," ")=="Sleeveless team jersey":mesh.material_override=_material(Color("1b1f2c"))
	return actor

func _career_changed() -> void:
	# Team marks come from the media projection, which can arrive after the
	# hall was built; redraw the walls so logos replace monograms.
	if ceremony_phase in ["idle","finished"]: _refresh_led(true)
	_draw_roster()
	# A ceremony already underway uses one immutable result snapshot.
	if ceremony_phase=="idle" and preview and _valid_finalized(CareerBridge.context.get("awards",{})):
		_set_caption("新的年度结算已就绪。重新进入颁奖厅后将使用该年度结果。")

func _nearest_target() -> String:
	if ceremony_phase=="idle" or ceremony_phase=="finished":
		if _reachable(Vector3(0,0,-3.8),1.6):return "ceremony"
	if ceremony_phase in ["cd_tease","cd_reveal"]:return "skip"
	if ceremony_phase=="player_walk" and current_index>=0:
		var spot:=_podium_spot(int(award_rows[current_index]["rank"]))
		if _distance(spot)<1.05 and player.position.y>.48:return "award"
	return ""

func _hint_text() -> String:
	if target=="award":return "E 领取你的年度奖杯"
	if target=="ceremony":return "E "+("重播" if ceremony_phase=="finished" else "开始")+("年度颁奖" if finalized else "预览典礼")
	if target=="skip":return "E 跳过倒数，直接揭晓前三"
	if ceremony_phase=="player_walk":return "走上舞台，到你的领奖台前"
	if ceremony_phase=="player_return":return "带着奖杯回到观礼通道"
	return ""

func interact() -> void:
	if target=="ceremony":start_ceremony()
	elif target=="skip":_skip_countdown()
	elif target=="award" and ceremony_phase=="player_walk":
		var rank:=int(award_rows[current_index]["rank"]);awarded_ranks.append(rank)
		_take_display_trophy(rank)
		if is_instance_valid(player_trophy):player_trophy.queue_free()
		player_trophy=_trophy("YourAnnualAward",camera,.46);player_trophy.position=Vector3(.38,-.42,-.85)
		ceremony_phase="player_return";_set_caption("主持人：祝贺 %s！请回到观礼通道，典礼将继续。"%_row_name(award_rows[current_index]))
		_celebrate(rank)

func start_ceremony() -> void:
	if not ceremony_phase in ["idle","finished"]:return
	for rank in guest_actors:
		var actor: Player=guest_actors[rank];actor.position=guest_homes[rank];actor.reset_physics_interpolation()
		actor.velocity=Vector3.ZERO;actor.locked=true;actor.seat_pose=true;actor.upper_body_action=""
	for trophy in guest_trophies.values():
		if is_instance_valid(trophy):trophy.queue_free()
	for trophy in display_trophies.values():
		if is_instance_valid(trophy):trophy.visible=true;trophy.scale=Vector3.ONE*.8
	if is_instance_valid(player_trophy):player_trophy.queue_free()
	guest_trophies.clear();called_ranks.clear();awarded_ranks.clear();completed_ranks.clear();countdown_seen.clear();revealed.clear()
	current_index=-1;countdown_index=-1;ceremony_phase="opening";ceremony_clock=0;house_level=.55
	for kind in ["drumroll","drumroll_long","hit","fanfare","applause"]:Audio.sound(kind)
	if not finalized: _set_caption("主持人：欢迎观看预览典礼。以下示例姓名仅用于展示领奖流程。")
	elif countdown_rows.is_empty(): _set_caption("主持人：欢迎来到 %s 年度选手颁奖。我们依次公布第三名、第二名与第一名。" % awards_year)
	else: _set_caption("主持人：欢迎来到 %s 年度选手颁奖。先回顾年度 Top20，再依次揭晓第三名、第二名与第一名。" % awards_year)
	_refresh_led(true)

## Countdown step 1: the rank is shown, the name is not. Drum roll.
func _tease_countdown() -> void:
	countdown_index+=1;ceremony_clock=0
	if countdown_index>=countdown_rows.size():
		_begin_top_tease();return
	var rank:=int(countdown_rows[countdown_index]["rank"])
	ceremony_phase="cd_tease"
	_set_caption("主持人：年度第 %d 名……" % rank)
	Audio.play(self,"drumroll",-6.0)
	_refresh_led()

## Countdown step 2: name, team mark and numbers land with a hit.
func _reveal_countdown() -> void:
	var row: Dictionary=countdown_rows[countdown_index];var rank:=int(row["rank"])
	ceremony_phase="cd_reveal";ceremony_clock=0
	revealed[rank]=true;countdown_seen.append(rank)
	var team:=str(row.get("team",""))
	if team.is_empty(): _set_caption("主持人：年度第 %d 名 —— %s。" % [rank,_row_name(row)])
	else: _set_caption("主持人：年度第 %d 名 —— %s（%s）。" % [rank,_row_name(row),team])
	Audio.stop(self,"drumroll")
	if _is_human(row):
		Audio.play(self,"fanfare");Audio.play(self,"applause")
	else:
		Audio.play(self,"hit",-8.0);Audio.play(self,"applause",-10.0)
	_refresh_led();_flash_led()

func _skip_countdown() -> void:
	if ceremony_phase not in ["cd_tease","cd_reveal"]:return
	for row in countdown_rows:
		var rank:=int(row["rank"]);revealed[rank]=true
		if not rank in countdown_seen:countdown_seen.append(rank)
	countdown_index=countdown_rows.size()
	Audio.stop(self,"drumroll")
	_begin_top_tease()

## Podium step 1: lights down, search lights sweep the finalists, long roll.
func _begin_top_tease() -> void:
	current_index+=1;ceremony_clock=0
	if current_index>=award_rows.size():
		ceremony_phase="finished";active_actor=null;ceremony_name.text="荣耀属于每一位选手";house_level=1.0
		for row in top20_rows:revealed[int(row["rank"])]=true
		for row in award_rows:revealed[int(row["rank"])]=true
		_set_caption("年度颁奖结束。恭喜所有入选选手。" if finalized else "预览典礼结束。实际年度排名将在生涯年度结算后显示。")
		_refresh_led(true)
		return
	var rank:=int(award_rows[current_index]["rank"])
	ceremony_phase="top_tease";house_level=.22
	_set_caption("主持人：年度%s名是——" % RANK_WORDS[rank] if finalized else "主持人：预览席位 #%d 是——" % rank)
	Audio.play(self,"drumroll_long",-3.0)
	_refresh_led()

## Podium step 2: the name, a cymbal hit, fanfare and the follow spot.
func _reveal_top() -> void:
	var row: Dictionary=award_rows[current_index];var rank:=int(row["rank"]);called_ranks.append(rank);revealed[rank]=true
	ceremony_clock=0;house_level=.45
	ceremony_name.text="#%d  %s"%[rank,_row_name(row)]
	_set_caption("主持人：年度%s名，%s！请上台领奖。"%[RANK_WORDS[rank],_row_name(row)] if finalized else "主持人：预览席位 #%d，%s。请上台演示领奖。"%[rank,_row_name(row)])
	ceremony_phase="announce";active_actor=null if _is_human(row) else guest_actors.get(rank)
	Audio.stop(self,"drumroll_long")
	Audio.play(self,"hit",-2.0);Audio.play(self,"fanfare",-2.0);Audio.play(self,"applause",-4.0)
	if active_actor:active_actor.upper_body_action="clap"
	_refresh_led();_flash_led()

func _take_display_trophy(rank: int) -> void:
	# The cup on the podium is the one handed over; it leaves the podium.
	var cup: Node3D=display_trophies.get(rank)
	if is_instance_valid(cup):
		var tween:=create_tween();tween.tween_property(cup,"scale",Vector3.ONE*.05,.25).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_IN)
		tween.finished.connect(func(): if is_instance_valid(cup): cup.visible=false)

func _set_actor_route(points: Array[Vector3]) -> void:
	actor_route=points;route_index=0
	if active_actor:active_actor.locked=false;active_actor.seat_pose=false;active_actor.test_direction=Vector3.ZERO;active_actor.upper_body_action=""

func _walk_actor() -> bool:
	if not active_actor:return false
	while route_index<actor_route.size() and Vector2(active_actor.position.x-actor_route[route_index].x,active_actor.position.z-actor_route[route_index].z).length()<.14:route_index+=1
	if route_index>=actor_route.size():active_actor.test_direction=Vector3.ZERO;active_actor.velocity=Vector3.ZERO;active_actor.locked=true;return true
	var direction:=actor_route[route_index]-active_actor.position;direction.y=0;active_actor.test_direction=direction.normalized();return false

func _celebrate(rank: int) -> void:
	if rank==1 and is_instance_valid(confetti): confetti.restart()
	Audio.play(self,"applause",-3.0)

func _update_venue(delta: float) -> void:
	show_clock+=delta
	_update_show_lights(delta)
	# The hall murmurs before and after; during the show it hushes under the host.
	if ambience: ambience.set_level(1.0 if ceremony_phase in ["idle","finished"] else 0.3)
	if paused or CareerBridge.phone_open or Travel.busy:return
	ceremony_clock+=delta*ceremony_speed
	match ceremony_phase:
		"opening":
			if ceremony_clock>3.4:
				if countdown_rows.is_empty():_begin_top_tease()
				else:_tease_countdown()
		"cd_tease":
			var rank:=int(countdown_rows[countdown_index]["rank"])
			if ceremony_clock>(2.1 if rank<=10 else 1.5):_reveal_countdown()
		"cd_reveal":
			if ceremony_clock>REVEAL_HOLD:_tease_countdown()
		"top_tease":
			if ceremony_clock>TEASE_TOP:_reveal_top()
		"announce":
			if ceremony_clock>2.8:
				if _is_human(award_rows[current_index]):
					ceremony_phase="player_walk";_set_caption(caption.text+"\n沿中央台阶上台，走到 #%d 领奖台前按 E。"%int(award_rows[current_index]["rank"]))
				else:
					ceremony_phase="walk_up"
					var route: Array[Vector3]=[Vector3(0,0,-3.6),Vector3(0,0,-4.35),Vector3(0,.61,-6.9),_podium_spot(int(award_rows[current_index]["rank"]))]
					_set_actor_route(route)
		"walk_up":
			if _walk_actor():
				ceremony_phase="award";ceremony_clock=0;active_actor.face_toward(Vector3(active_actor.position.x,.61,0))
				var rank:=int(award_rows[current_index]["rank"]);awarded_ranks.append(rank)
				_take_display_trophy(rank)
				var trophy:=_trophy("RecipientAward"+str(rank),active_actor.visual,.52);trophy.position=Vector3(0,1.38,.12);guest_trophies[rank]=trophy;active_actor.upper_body_action="trophy_lift"
				trophy.scale=Vector3.ONE*.05;create_tween().tween_property(trophy,"scale",Vector3.ONE*.52,.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
				_set_caption("主持人：祝贺 %s。"%_row_name(award_rows[current_index]))
				_celebrate(rank)
		"award":
			if ceremony_clock>3.2:
				ceremony_phase="walk_back"
				var rank:=int(award_rows[current_index]["rank"])
				if guest_trophies.has(rank) and is_instance_valid(guest_trophies[rank]): guest_trophies[rank].position=Vector3(0,.88,.39)
				var route: Array[Vector3]=[Vector3(0,.61,-6.9),Vector3(0,0,-4.35),Vector3(0,0,-3.6),guest_homes[rank]]
				_set_actor_route(route)
				active_actor.upper_body_action="typing"
		"walk_back":
			if _walk_actor():
				active_actor.seat_pose=true;active_actor.face_toward(Vector3(active_actor.position.x,0,-9));completed_ranks.append(int(award_rows[current_index]["rank"]));ceremony_phase="between";ceremony_clock=0
		"player_return":
			if _distance(audience_return_point)<1.4 and player.position.y<.2:completed_ranks.append(int(award_rows[current_index]["rank"]));ceremony_phase="between";ceremony_clock=0
		"between":
			if ceremony_clock>1.3:_begin_top_tease()

func _update_show_lights(delta: float) -> void:
	if not is_instance_valid(follow_spot): return
	# House lights fade down for the drum rolls and come back afterwards.
	var level := house_level if ceremony_phase not in ["idle","finished"] else 1.0
	for light in house_lights:
		light.light_energy = lerpf(light.light_energy,float(light.get_meta("base_energy"))*level,1.0-exp(-3.0*delta))
	# The follow spot tracks whoever is walking to or standing on the podium.
	var focus := Vector3(0,1.4,-8.6)
	var wanted := 0.0
	if ceremony_phase in ["announce","walk_up","award","walk_back"] and active_actor:
		focus = active_actor.global_position+Vector3.UP*(.7+active_actor.seat_lift*active_actor.seat_blend); wanted = 7.5
	elif ceremony_phase in ["announce","player_walk","player_return"] and current_index>=0 and _is_human(award_rows[current_index]):
		focus = player.global_position+Vector3.UP*.7; wanted = 7.5
	follow_energy = lerpf(follow_energy,wanted,1.0-exp(-5.0*delta))
	follow_spot.light_energy = follow_energy
	follow_spot.visible = follow_energy > .05
	if follow_spot.visible and follow_spot.global_position.distance_to(focus) > .5:
		var current := -follow_spot.global_transform.basis.z
		var desired := (focus-follow_spot.global_position).normalized()
		var blended := current.slerp(desired,1.0-exp(-7.0*delta))
		follow_spot.look_at(follow_spot.global_position+blended,Vector3.UP)
	# Search lights sweep during the drum rolls: the whole audience for the
	# countdown, the three finalists' chairs before a podium name.
	var searching := ceremony_phase in ["cd_tease","top_tease"]
	search_energy = lerpf(search_energy,6.5 if searching else 0.0,1.0-exp(-6.0*delta))
	for i in range(search_spots.size()):
		var spot := search_spots[i]
		spot.light_energy = search_energy; spot.visible = search_energy > .05
		if not spot.visible: continue
		var t := show_clock*(2.6 if ceremony_phase=="top_tease" else 1.4)+i*2.1
		var aim := Vector3(sin(t)*6.5,.6,2.5+cos(t*.73)*5.0)
		if ceremony_phase=="top_tease":
			var seats: Array = guest_homes.values()
			if not seats.is_empty():
				var a: Vector3 = seats[int(floor(t*.5+i)) % seats.size()]
				var b: Vector3 = seats[int(floor(t*.5+i+1)) % seats.size()]
				aim = a.lerp(b,smoothstep(0.0,1.0,fposmod(t*.5,1.0)))+Vector3.UP*.9
		spot.look_at(aim,Vector3.UP)
	# Back lights breathe slowly during the show; steady when idle.
	var live := ceremony_phase not in ["idle"]
	for i in range(stage_beams.size()):
		var light := stage_beams[i]
		if light.has_meta("breathes"):
			light.light_energy = 1.6 + (sin(show_clock*1.3+i)*.6+.6 if live else 0.0)

func set_device_open(value: bool, kind: String) -> void:
	super.set_device_open(value,kind)
	# NPC directions are held during phone use so recipients do not keep walking.
	if active_actor:active_actor.locked=value or ceremony_phase not in ["walk_up","walk_back"]

func set_paused(value: bool) -> void:
	super.set_paused(value)
	if active_actor:active_actor.locked=value or CareerBridge.phone_open or ceremony_phase not in ["walk_up","walk_back"]

func _capture_view() -> void:
	player.position=Vector3(1.3,.02,1.8);player.reset_physics_interpolation();body_y=player.position.y
	yaw=.06;pitch=.03;camera.position=player.position+Vector3.UP*1.34;camera.rotation=Vector3(pitch,yaw,0)

func diagnostic_snapshot() -> Dictionary:
	return {"destination":"awards","finalized":finalized,"preview":preview,"year":awards_year,"source":ceremony_source,"top20_rows":top20_rows.size(),"countdown":countdown_seen.duplicate(),"led_state":led_state,"attendees":audience_count,"static_guests":static_guest_count,"recipient_attendee_ids":recipient_attendee_ids.duplicate(),"species":"chicken","enclosed":has_node("ClosedCeiling"),"colliders":collision_count,"phase":ceremony_phase,"called_ranks":called_ranks.duplicate(),"awarded_ranks":awarded_ranks.duplicate(),"completed_ranks":completed_ranks.duplicate(),"host_voice":"captions only"}

# ---------------------------------------------------------------- LED walls

func _stat_line(row: Dictionary) -> String:
	var parts: Array[String] = []
	if Fmt.is_number(row.get("rating")): parts.append("Rating " + Fmt.rating(row.get("rating")))
	# Each piece is localised on its own; the joined line is not a catalogue key.
	if Fmt.is_number(row.get("maps")): parts.append(Locale.text("%s 张地图" % Fmt.integer(row.get("maps"))))
	if int(row.get("titles",0))>0: parts.append(Locale.text("%d 冠" % int(row.get("titles",0))))
	if int(row.get("mvp",0))>0: parts.append(str(int(row.get("mvp",0))) + " MVP")
	if int(row.get("evp",0))>0: parts.append(str(int(row.get("evp",0))) + " EVP")
	return "  ·  ".join(parts)

func _top20_row(rank: int) -> Dictionary:
	for row in top20_rows:
		if int(row.get("rank",0))==rank: return row
	for row in award_rows:
		if int(row.get("rank",0))==rank: return row
	return {}

func _is_revealed(rank: int) -> bool:
	return ceremony_phase=="finished" or revealed.has(rank)

func _refresh_led(force: bool = false) -> void:
	if not is_instance_valid(main_led): return
	var state := ceremony_phase
	var focus_rank := 0
	if ceremony_phase in ["cd_tease","cd_reveal"] and countdown_index>=0 and countdown_index<countdown_rows.size(): focus_rank=int(countdown_rows[countdown_index]["rank"])
	elif ceremony_phase not in ["idle","opening","finished"] and current_index>=0 and current_index<award_rows.size(): focus_rank=int(award_rows[current_index]["rank"])
	var key := "%s:%d:%s:%s:%d" % [state,focus_rank,awards_year,finalized,revealed.size()]
	if key==led_state and not force: return
	led_state=key
	Kit.clear(main_led)
	Kit.gradient(main_led,Color("0c1424"),Color("05070d"))
	_led_glow(main_led)
	var teasing := ceremony_phase in ["cd_tease","top_tease"]
	if teasing and focus_rank>0: _led_tease(main_led,focus_rank)
	elif focus_rank>0: _led_rank_card(main_led,focus_rank)
	elif ceremony_phase=="finished": _led_finale(main_led)
	else: _led_title(main_led)
	led_flash=ColorRect.new(); led_flash.color=Color(1,.97,.9,0); led_flash.size=main_led.size; led_flash.mouse_filter=Control.MOUSE_FILTER_IGNORE; main_led.add_child(led_flash)
	_draw_wings(focus_rank)
	_draw_top20(focus_rank)
	var tween := create_tween()
	main_led.modulate=Color(1,1,1,0)
	tween.tween_property(main_led,"modulate",Color.WHITE,.25 if teasing else .35)
	# Teases animate (pulsing "?"), so the wall keeps rendering for the roll.
	Kit.refresh(main_led,TEASE_TOP+.6 if teasing else .7)
	for wall in [left_led,right_led,top20_led]: Kit.refresh(wall,.6)

## Rank shown, name sealed: a large pulsing question mark under the rank.
func _led_tease(root: Control, rank: int) -> void:
	var w := root.size.x
	var podium := rank<=3
	if podium:
		Kit.text_at(root,("年度%s名" % RANK_WORDS[rank]) if finalized else "预览席位 #%d" % rank,74,Rect2(0,60,w,110),Kit.GOLD)
		var mark := Kit.text_at(root,"?",230,Rect2(0,150,w,280),Kit.LED_TEXT)
		_pulse(mark)
	else:
		Kit.text_at(root,"年度 Top20 · 第 %d 名" % rank,38,Rect2(0,34,w,56),Kit.GOLD)
		Kit.text_at(root,"#%d" % rank,180,Rect2(40,86,440,300),Kit.GOLD_SOFT,HORIZONTAL_ALIGNMENT_RIGHT)
		Kit.rect(root,Rect2(520,120,4,270),Color(0.89,0.74,0.45,.6))
		var mark := Kit.text_at(root,"?",170,Rect2(570,90,600,300),Kit.LED_TEXT,HORIZONTAL_ALIGNMENT_LEFT)
		_pulse(mark)

func _pulse(label: Label) -> void:
	label.pivot_offset = label.size*.5
	var tween := create_tween().set_loops(8)
	tween.tween_property(label,"modulate:a",.35,.22)
	tween.tween_property(label,"modulate:a",1.0,.22)

## A white flash on the main wall marks the instant of a reveal.
func _flash_led() -> void:
	if not is_instance_valid(led_flash): return
	led_flash.color.a = .85
	create_tween().tween_property(led_flash,"color:a",0.0,.55)
	Kit.refresh(main_led,1.0)

func _led_glow(root: Control) -> void:
	# A soft gold horizon line and corner ticks: the hall's signature frame.
	Kit.rect(root,Rect2(0,root.size.y-6,root.size.x,6),Color(0.89,0.74,0.45,.9))
	Kit.rect(root,Rect2(0,0,root.size.x,3),Color(0.89,0.74,0.45,.55))
	for x in [24.0,root.size.x-84.0]:
		Kit.rect(root,Rect2(x,22,60,3),Color(0.89,0.74,0.45,.8))
		Kit.rect(root,Rect2(x,root.size.y-34,60,3),Color(0.89,0.74,0.45,.8))

func _led_title(root: Control) -> void:
	var w := root.size.x
	Kit.text_at(root,"CAREER  AWARDS",40,Rect2(0,40,w,60),Kit.GOLD)
	Kit.text_at(root,awards_year if finalized else "PREVIEW",150,Rect2(0,96,w,180),Kit.LED_TEXT)
	Kit.text_at(root,"年度选手颁奖典礼",52,Rect2(0,276,w,76),Kit.GOLD_SOFT)
	var line := ("年度 Top20 正式榜单 · 前三名现场领奖" if not top20_rows.is_empty() else "年度前三名现场领奖") if finalized else "预览典礼 · 示例姓名不代表真实年度结果"
	Kit.text_at(root,line,32,Rect2(0,358,w,54),Kit.LED_MUTED)
	if ceremony_phase=="opening": Kit.text_at(root,"典礼即将开始",30,Rect2(0,412,w,48),Kit.GOLD)

func _led_rank_card(root: Control, rank: int) -> void:
	# Keep everything in the upper ~70%: the #1 trophy stands in front of the
	# lower edge of the wall from the audience's eye height.
	var row := _top20_row(rank)
	var podium := rank<=3
	var w := root.size.x
	var heading := ("年度%s名" % RANK_WORDS[rank] if finalized else "预览席位 #%d" % rank) if podium else "年度 Top20 · 第 %d 名" % rank
	Kit.text_at(root,heading,38,Rect2(0,34,w,56),Kit.GOLD)
	Kit.text_at(root,"#%d" % rank,210 if podium else 180,Rect2(40,86,440,300),Kit.GOLD if podium else Kit.GOLD_SOFT,HORIZONTAL_ALIGNMENT_RIGHT)
	Kit.rect(root,Rect2(520,120,4,270),Color(0.89,0.74,0.45,.6))
	var team := str(row.get("team",""))
	Kit.text_at(root,_row_name(row),96 if podium else 84,Rect2(570,104,980,124),Kit.LED_TEXT,HORIZONTAL_ALIGNMENT_LEFT)
	var team_row := HBoxContainer.new(); team_row.position=Vector2(570,238); team_row.size=Vector2(980,84)
	team_row.add_theme_constant_override("separation",20); team_row.mouse_filter=Control.MOUSE_FILTER_IGNORE
	root.add_child(team_row)
	if not team.is_empty() and team!="示例席位":
		Kit.logo_tile(team_row,team,80)
	var team_label := Kit.text(team_row,team if not team.is_empty() else "—",44,Kit.GOLD_SOFT,HORIZONTAL_ALIGNMENT_LEFT)
	team_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var stats := _stat_line(row)
	if not stats.is_empty(): Kit.text_at(root,stats,32,Rect2(570,336,980,52),Kit.LED_MUTED,HORIZONTAL_ALIGNMENT_LEFT)
	if _is_human(row): Kit.text_at(root,"你的年度荣誉",30,Rect2(570,392,980,46),Kit.GOLD,HORIZONTAL_ALIGNMENT_LEFT)

func _led_finale(root: Control) -> void:
	var w := root.size.x
	Kit.text_at(root,"荣耀属于每一位选手",54,Rect2(0,34,w,84),Kit.GOLD_SOFT)
	var order := [2,1,3]
	for i in range(3):
		var rank: int = order[i]
		var row := _top20_row(rank)
		var x := 120.0+i*460.0
		var tall := rank==1
		var card := Kit.panel(root,Color(1,1,1,.06),22,Kit.GOLD if tall else Color(0.89,0.74,0.45,.35),20)
		card.position=Vector2(x,140 if tall else 170); card.size=Vector2(420,290 if tall else 250)
		var stack := VBoxContainer.new(); stack.alignment=BoxContainer.ALIGNMENT_CENTER; stack.mouse_filter=Control.MOUSE_FILTER_IGNORE
		stack.add_theme_constant_override("separation",8); card.add_child(stack)
		Kit.text(stack,"#%d" % rank,86 if tall else 70,Kit.GOLD)
		Kit.text(stack,_row_name(row),44 if tall else 38,Kit.LED_TEXT)
		var team := str(row.get("team",""))
		if not team.is_empty() and team!="示例席位":
			Kit.logo_tile(stack,team,64)
		Kit.text(stack,team,26,Kit.LED_MUTED)

func _draw_wings(focus_rank: int) -> void:
	for side in [left_led,right_led]:
		if not is_instance_valid(side): continue
		Kit.clear(side)
		Kit.gradient(side,Color("101a2c"),Color("06080e"))
		Kit.rect(side,Rect2(0,0,6,side.size.y),Color(0.89,0.74,0.45,.7))
		Kit.rect(side,Rect2(side.size.x-6,0,6,side.size.y),Color(0.89,0.74,0.45,.7))
	if is_instance_valid(left_led):
		var w := left_led.size.x
		Kit.text_at(left_led,"CAREER",44,Rect2(0,90,w,60),Kit.GOLD)
		Kit.text_at(left_led,"AWARDS",44,Rect2(0,148,w,60),Kit.GOLD)
		Kit.rect(left_led,Rect2(w*.3,232,w*.4,3),Color(0.89,0.74,0.45,.8))
		Kit.text_at(left_led,awards_year if finalized else "预览",58,Rect2(0,260,w,80),Kit.LED_TEXT)
		Kit.text_at(left_led,"年度选手",34,Rect2(0,350,w,50),Kit.GOLD_SOFT)
		Kit.text_at(left_led,"Top20" if not top20_rows.is_empty() else "Top3",34,Rect2(0,400,w,50),Kit.LED_MUTED)
	if is_instance_valid(right_led):
		var w := right_led.size.x
		Kit.text_at(right_led,"TOP 3",48,Rect2(0,70,w,70),Kit.GOLD)
		for i in range(3):
			var rank := 3-i
			var row := _top20_row(rank)
			var shown := _is_revealed(rank)
			var y := 170.0+i*130.0
			Kit.text_at(right_led,"#%d" % rank,40,Rect2(0,y,w,52),Kit.GOLD if rank==focus_rank else Kit.GOLD_SOFT)
			Kit.text_at(right_led,_row_name(row) if shown else "?",30,Rect2(12,y+50,w-24,46),Kit.LED_TEXT if shown else Kit.LED_MUTED)

func _draw_top20(focus_rank: int) -> void:
	if not is_instance_valid(top20_led): return
	Kit.clear(top20_led)
	var root := top20_led
	Kit.gradient(root,Color("0f1626"),Color("070a12"))
	var w := root.size.x
	Kit.rect(root,Rect2(0,0,w,4),Color(0.89,0.74,0.45,.8))
	if not finalized or top20_rows.is_empty():
		Kit.text_at(root,"年度 Top20",64,Rect2(0,180,w,90),Kit.GOLD)
		Kit.text_at(root,"尚无年度正式 Top20" if not finalized else "完整榜单暂未提供",44,Rect2(0,300,w,70),Kit.LED_TEXT)
		Kit.text_at(root,"完成全年赛事并确认进入下一赛季后，这里会显示正式归档的二十位选手。" if not finalized else "台上仅显示已归档的年度前三。",28,Rect2(80,390,w-160,90),Kit.LED_MUTED)
		return
	Kit.text_at(root,"%s 年度 Top20" % awards_year,50,Rect2(48,22,w*.6,80),Kit.GOLD,HORIZONTAL_ALIGNMENT_LEFT)
	Kit.text_at(root,"典礼现场揭晓" if ceremony_phase!="finished" else "正式归档",26,Rect2(w*.5,34,w*.5-48,60),Kit.LED_MUTED,HORIZONTAL_ALIGNMENT_RIGHT)
	var row_h := 58.0
	for row in top20_rows:
		var rank := int(row["rank"])
		var column := 0 if rank<=10 else 1
		var x := 40.0+column*(w*.5)
		var y := 118.0+((rank-1)%10)*row_h
		var hidden := not _is_revealed(rank)
		var current := rank==focus_rank
		if current: Kit.rect(root,Rect2(x-12,y-2,w*.5-56,row_h-6),Color(0.89,0.74,0.45,.22))
		elif rank<=3: Kit.rect(root,Rect2(x-12,y-2,w*.5-56,row_h-6),Color(0.89,0.74,0.45,.08))
		Kit.text_at(root,"%02d" % rank,30,Rect2(x,y,62,row_h-8),Kit.GOLD if rank<=3 or current else Kit.GOLD_SOFT,HORIZONTAL_ALIGNMENT_LEFT)
		var team := str(row.get("team",""))
		var mark := HBoxContainer.new(); mark.position=Vector2(x+66,y+4); mark.size=Vector2(44,44); mark.mouse_filter=Control.MOUSE_FILTER_IGNORE; root.add_child(mark)
		if not hidden and not team.is_empty(): Kit.logo_tile(mark,team,42)
		Kit.text_at(root,"?" if hidden else _row_name(row),30,Rect2(x+124,y,300,row_h-8),Kit.LED_TEXT if not hidden else Kit.LED_MUTED,HORIZONTAL_ALIGNMENT_LEFT)
		Kit.text_at(root,"" if hidden else team,24,Rect2(x+424,y,180,row_h-8),Kit.LED_MUTED,HORIZONTAL_ALIGNMENT_LEFT)
		Kit.text_at(root,"" if hidden else Fmt.rating(row.get("rating"),""),26,Rect2(x+w*.5-176,y,100,row_h-8),Kit.GOLD_SOFT,HORIZONTAL_ALIGNMENT_RIGHT)

func _draw_roster() -> void:
	if not is_instance_valid(roster_led): return
	var root := roster_led
	Kit.clear(root)
	Kit.gradient(root,Color("0f1626"),Color("070a12"))
	var w := root.size.x
	Kit.rect(root,Rect2(0,0,w,4),Color(0.89,0.74,0.45,.8))
	var current: bool = not attendee_rows.is_empty() and bool(attendee_rows[0].get("current_roster",false))
	Kit.text_at(root,"当前一线战队选手 · 嘉宾席" if current else ("预览嘉宾席" if preview else "年度嘉宾席"),46,Rect2(48,22,w*.62,76),Kit.GOLD,HORIZONTAL_ALIGNMENT_LEFT)
	Kit.text_at(root,"世界排名前十战队现役阵容" if current else "%d 位嘉宾" % attendee_rows.size(),26,Rect2(w*.5,34,w*.5-48,56),Kit.LED_MUTED,HORIZONTAL_ALIGNMENT_RIGHT)
	var order: Array[String] = []
	var groups: Dictionary = {}
	for row in attendee_rows.slice(0,50):
		var team := str(row.get("team",""))
		if not groups.has(team): groups[team]=[]; order.append(team)
		groups[team].append(row)
	guest_groups = order
	if current and order.size()>=2:
		# Team blocks: logo, name, world rank and the five current players.
		for i in range(mini(order.size(),10)):
			var team: String = order[i]
			var rows: Array = groups[team]
			var x := 40.0+(i%2)*(w*.5)
			var y := 112.0+int(i/2)*118.0
			Kit.rect(root,Rect2(x-10,y,w*.5-60,108),Color(1,1,1,.04))
			var mark := HBoxContainer.new(); mark.position=Vector2(x,y+12); mark.size=Vector2(56,56); mark.mouse_filter=Control.MOUSE_FILTER_IGNORE; root.add_child(mark)
			Kit.logo_tile(mark,team,54)
			var rank_text := "#%d" % int(rows[0].get("team_rank",0)) if int(rows[0].get("team_rank",0))>0 else ""
			Kit.text_at(root,team,34,Rect2(x+70,y+6,w*.5-230,46),Kit.LED_TEXT,HORIZONTAL_ALIGNMENT_LEFT)
			Kit.text_at(root,rank_text,26,Rect2(x+w*.5-180,y+8,100,44),Kit.GOLD,HORIZONTAL_ALIGNMENT_RIGHT)
			var names: Array[String] = []
			for row in rows: names.append(_row_name(row))
			Kit.text_at(root," · ".join(names),26,Rect2(x+70,y+54,w*.5-140,44),Color("c3cfdc"),HORIZONTAL_ALIGNMENT_LEFT)
	else:
		var rows: Array = attendee_rows.slice(0,50)
		for i in range(rows.size()):
			var column := i%5; var line := int(i/5)
			Kit.text_at(root,_row_name(rows[i]),24,Rect2(48+column*(w-96)/5.0,118+line*56,(w-96)/5.0-12,48),Kit.LED_TEXT,HORIZONTAL_ALIGNMENT_LEFT)
	Kit.refresh(root)
