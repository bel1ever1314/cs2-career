extends "res://scripts/small_venue_base.gd"
## Original ceremony set, inspired by annual esports award shows. No HLTV marks.
const Audience = preload("res://scripts/arena_chicken_crowd.gd")
const Competitor = preload("res://scripts/venue_competitor.gd")
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

func _destination() -> String: return "awards"
func _data_path() -> String: return "res://data/awards_venue.json"

func _build_venue() -> void:
	_enclosure(20.0,24.0,5.7)
	env.ambient_light_energy=.29;env.ambient_light_color=Color("a9b4bf")
	_box("CeremonyCarpet",Vector3(0,.015,1.8),Vector3(3.8,.03,17.4),Color("28312f"))
	for side in [-1.0,1.0]:
		_box("AisleGoldEdge",Vector3(side*1.94,.04,1.8),Vector3(.035,.035,17.4),Color("b59354"),false,.28)
		for z in [-7.0,0.0,7.0]:
			_box("WallAcoustic",Vector3(side*9.83,2.8,z),Vector3(.10,4.4,3.5),Color("0c1821"))
			_box("WallSconce",Vector3(side*9.72,2.3,z),Vector3(.03,.8,.10),Color("dfc087"),false,.9)
			_spot("WarmWallWash",Vector3(side*9.6,4.3,z),Vector3(side*7.4,0,z),Color("ffd3a1"),1.8,42)
	_box("AwardsStage",Vector3(0,.30,-8.55),Vector3(17.4,.60,5.3),Color("1c2429"),true)
	_box("StageFrontTrim",Vector3(0,.47,-5.86),Vector3(17.4,.045,.04),Color("d7b36f"),false,.4)
	for i in range(4):
		_box("StageStep"+str(i),Vector3(0,.075*(i+1),-4.89-i*.36),Vector3(4.8,.15*(i+1),.38),Color("35403e"))
		_box("StepNosing",Vector3(0,.15*(i+1)+.008,-4.72-i*.36),Vector3(4.77,.016,.023),Color("bc9b60"),false,.2)
	# One continuous walk surface avoids capsule snagging on the decorative treads.
	var ramp:=StaticBody3D.new();ramp.name="StageAccessRamp";add_child(ramp)
	var ramp_shape:=ConvexPolygonShape3D.new();var points:=PackedVector3Array()
	for x in [-2.4,2.4]:
		points.append(Vector3(x,0,-4.7));points.append(Vector3(x,.60,-5.9));points.append(Vector3(x,-.12,-4.7));points.append(Vector3(x,-.12,-5.9))
	ramp_shape.points=points;var ramp_collision:=CollisionShape3D.new();ramp_collision.shape=ramp_shape;ramp.add_child(ramp_collision);collision_count+=1
	_box("StageBackdrop",Vector3(0,2.80,-11.33),Vector3(17.8,4.45,.13),Color("07131d"))
	# Repeating narrow light pillars give the set depth without copying a logo.
	for x in [-8.0,-6.8,-5.6,5.6,6.8,8.0]:
		_box("GoldPillar",Vector3(x,2.76,-11.18),Vector3(.085,3.9,.075),Color("cfac6a"),false,.65)
		_box("PillarShadow",Vector3(x+.18,2.76,-11.20),Vector3(.16,3.9,.04),Color("293537"))
	_sign("CAREER AWARDS",Vector3(0,4.30,-11.19),.010,0,Color("ebcb90"))
	ceremony_banner=_sign("年度选手颁奖",Vector3(0,3.63,-11.17),.004)
	ceremony_name=_sign("TOP 3  /  TOP 2  /  TOP 1",Vector3(0,2.66,-11.16),.008,0,Color("f0e4c7"))
	for rank in [3,1,2]:
		var x: float = _podium_x(rank)
		var height := .95 if rank==1 else (.66 if rank==2 else .48)
		_box("Podium"+str(rank),Vector3(x,.6+height*.5,-9.12),Vector3(1.46,height,.86),Color("203032"),true)
		_box("PodiumGoldCap",Vector3(x,.6+height,-9.12),Vector3(1.49,.032,.89),Color("b79960"))
		_sign("TOP "+str(rank),Vector3(x,.6+height*.5,-8.66),.0032)
		var trophy_holder:=Node3D.new();trophy_holder.position=Vector3(x,.6+height+.024,-9.12);add_child(trophy_holder)
		_trophy("DisplayAward"+str(rank),trophy_holder,.8)
	_box("HostLectern",Vector3(-6.5,1.08,-7.93),Vector3(.95,.94,.68),Color("33413f"),true)
	_sign("年度荣誉",Vector3(-6.5,1.13,-7.57),.0025)
	_cylinder("MicrophoneStem",Vector3(-6.28,1.78,-7.98),.018,.46,Color("111a21"))
	_box("Microphone",Vector3(-6.28,2.02,-7.95),Vector3(.035,.055,.14),Color("bcb6a4"))
	for x in [-5.8,0.0,5.8]:
		_spot("StageSpot",Vector3(x,5.47,-4.9),Vector3(x*.6,1.25,-8.9),Color("ffe0aa"),5.8,35)
		_box("StageRig",Vector3(x,5.35,-5.2),Vector3(.42,.15,.45),Color("26313b"))
	_spot("HostSpot",Vector3(-6.4,5.4,-7.0),Vector3(-6.5,1.4,-8.0),Color("ffe4b7"),3.1,28)
	for x in [-4.8,4.8]:
		_fill("StageFrontSoftKey",Vector3(x,3.3,-6.3),Color("ffe0ac"),1.35,8.0)
	for side in [-1.0,1.0]:
		for z in [-1.7,3.9,8.4]:
			_fill("GuestSeatSoftFill",Vector3(side*5.3,3.2,z),Color("d6c8ad") if side<0 else Color("aabecf"),.80,7.8)
	for z in [-3.2,2.9,9.0]:
		_fill("CentralAisleFill",Vector3(0,3.25,z),Color("a7bdc9"),.42,6.8)
	_box("RankingPanel",Vector3(7.95,2.1,-10.84),Vector3(2.60,2.28,.11),Color("16242c"))
	ranking_board=_sign("",Vector3(7.95,2.1,-10.76),.0021)
	# Upholstered benches border a wide continuous central aisle.
	for side in [-1.0,1.0]:
		for z in [-2.0,.65,3.30,5.95,8.60]:
			_box("GuestBench",Vector3(side*5.48,.415,z),Vector3(6.85,.12,.66),Color("263b40"),true)
			_box("BenchBack",Vector3(side*5.48,.755,z+.34),Vector3(6.85,.66,.075),Color("1d3039"),true)
			for x in [-2.30,2.30]:_box("BenchFoot",Vector3(side*5.48+x,.24,z),Vector3(.08,.43,.52),Color("121d26"))
	_box("WelcomePanel",Vector3(-6.8,1.71,11.80),Vector3(4.7,2.45,.10),Color("14212b"))
	_sign("选手之夜\n年度荣誉典礼",Vector3(-6.8,2.0,11.73),.0055,PI)
	_sign("中央台阶通往领奖台",Vector3(-6.8,1.12,11.72),.0029,PI,Color("b6c0b9"))
	_sign("嘉宾席 / 观礼区",Vector3(6.0,2.48,11.76),.0042,PI)
	_box("AnnualTop20Backing",Vector3(-9.72,2.48,3.0),Vector3(.06,3.58,7.30),Color("15252c"))
	var top20_wall := Node3D.new(); top20_wall.position = Vector3(-9.65,2.5,3.0); top20_wall.rotation.y = PI * .5; add_child(top20_wall)
	annual_board = _sign("",Vector3.ZERO,.00225,0,Color("ebd2a0"),top20_wall)

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
	finalized=_valid_finalized(source);preview=not finalized
	human_id=str(source.get("human_id",CareerBridge.context.get("player",{}).get("id","")))
	award_rows.clear();attendee_rows.clear();top20_rows.clear()
	if finalized:
		awards_year=str(source["year"]);ceremony_source=str(source.get("source","season.top20"))
		for row in source["top3"]:award_rows.append(row.duplicate(true))
		for row in source.get("top20", []):
			if row is Dictionary and int(row.get("rank",0)) in range(1,21): top20_rows.append(row.duplicate(true))
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
	status.text="年度排名来源：生涯年度结算" if finalized else "预览场景 · 示例嘉宾和领奖流程"
	_set_caption("走到中央通道前端，按 E 开始颁奖。" if finalized else "尚无已结算年度排名。当前为预览典礼，示例姓名不代表真实年度获奖结果。")

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
	for i in range(award_rows.size()):
		var row: Dictionary=award_rows[i];var rank:=int(row["rank"])
		var home:=Vector3(-3.3-i*1.15,.02,-3.6)
		guest_homes[rank]=home
		_box("RecipientChair",home+Vector3(0,.46,0),Vector3(.63,.10,.58),Color("314341"))
		_box("RecipientChairBack",home+Vector3(0,.80,.30),Vector3(.63,.64,.065),Color("253a3d"))
		if _is_human(row):continue
		var actor=_actor("Recipient"+str(rank),home);actor.seat_pose=true;actor.locked=true;actor.face_toward(Vector3(home.x,.02,-9))
		guest_actors[rank]=actor
		_sign(_row_name(row),Vector3(home.x,1.56,home.z+.15),.0017)
	# Use the project's shared seated chicken mesh. Display-only guests have no physics.
	var source:=Audience.new();var material:=StandardMaterial3D.new();material.vertex_color_use_as_albedo=true;material.roughness=.88
	var poses: Array[Transform3D]=[]
	var attendance:=_attendance_plan(attendee_rows,award_rows)
	var crowd_rows: Array[Dictionary]=attendance["crowd_rows"]
	recipient_attendee_ids.assign(attendance["recipient_ids"])
	for i in range(crowd_rows.size()):
		var side: float=-1 if i%2==0 else 1
		var row:=int(i/10);var slot:=int(i/2)%5
		var at:=Vector3(side*(2.85+slot*1.30),0,-2.0+row*2.65)
		poses.append(Transform3D(Basis(Vector3.UP,PI),at))
		if i<6:_sign(_row_name(crowd_rows[i]),at+Vector3(0,1.33,.22),.00165)
	static_guest_count=poses.size();audience_count=int(attendance["total_attendees"])
	for definition in [["GuestBodies",source._chicken_mesh(true)],["GuestSeatsFeet",source._seat_and_feet_mesh()]]:
		var multimesh:=MultiMesh.new();multimesh.transform_format=MultiMesh.TRANSFORM_3D;multimesh.use_colors=true;multimesh.mesh=definition[1];multimesh.instance_count=poses.size()
		for i in range(poses.size()):
			multimesh.set_instance_transform(i,poses[i]);multimesh.set_instance_color(i,Audience.PALETTE[(i*7+int(i/9))%Audience.PALETTE.size()])
		var batch:=MultiMeshInstance3D.new();batch.name=definition[0];batch.multimesh=multimesh;batch.material_override=material;add_child(batch)
	var roster_board:=Node3D.new();roster_board.name="CurrentRosterGuestList";roster_board.position=Vector3(9.72,2.56,4.55);roster_board.rotation.y=-PI*.5;add_child(roster_board)
	_box("RosterBacking",Vector3(0,0,-.035),Vector3(7.4,3.70,.06),Color("15252c"),false,0,roster_board)
	var has_current_guests: bool=not attendee_rows.is_empty() and bool(attendee_rows[0].get("current_roster",false))
	_sign("当前一线战队选手 / 嘉宾席" if has_current_guests else "预览嘉宾席" if preview else "年度嘉宾席",Vector3(0,1.50,.012),.0032,0,Color("dac18e"),roster_board)
	for col in range(3):
		var names: Array[String]=[]
		for i in range(col*17,mini((col+1)*17,attendee_rows.size())):
			var row: Dictionary=attendee_rows[i];names.append(_row_name(row)+(" · "+str(row.get("team","")) if has_current_guests else ""))
		_sign("\n".join(names),Vector3((col-1)*2.38,-.08,.012),.00165,0,Color("b9c6c4"),roster_board)
	source.free()

func _actor(id: String, at: Vector3) -> Player:
	var actor:=Competitor.new();actor.npc_id=id;actor.name=id;actor.position=at;actor.home=at;actor.test_mode=true
	actor.walk_speed=2.4;actor.run_speed=2.4;actor.step_height=.21;actor.floor_snap_length=.32;add_child(actor)
	# Dark formal jackets keep the established chicken identity visible.
	for mesh in actor.visual.find_children("*","MeshInstance3D",true,false):
		if str(mesh.name).replace("_"," ")=="Sleeveless team jersey":mesh.material_override=_material(Color("192833"))
	return actor

func _career_changed() -> void:
	# A ceremony already underway uses one immutable result snapshot.
	if ceremony_phase=="idle" and preview and _valid_finalized(CareerBridge.context.get("awards",{})):
		_set_caption("新的年度结算已就绪。重新进入颁奖厅后将使用该年度结果。")

func _nearest_target() -> String:
	if ceremony_phase=="idle" or ceremony_phase=="finished":
		if _reachable(Vector3(0,0,-3.8),1.6):return "ceremony"
	if ceremony_phase=="player_walk" and current_index>=0:
		var spot:=_podium_spot(int(award_rows[current_index]["rank"]))
		if _distance(spot)<1.05 and player.position.y>.48:return "award"
	return ""

func _hint_text() -> String:
	if target=="award":return "E 领取你的年度奖杯"
	if target=="ceremony":return "E "+("重播" if ceremony_phase=="finished" else "开始")+("年度颁奖" if finalized else "预览典礼")
	if ceremony_phase=="player_walk":return "沿中央台阶走上舞台 · 靠近你的领奖台"
	if ceremony_phase=="player_return":return "带着奖杯走回中央观礼通道 · 继续典礼"
	return "中央通道通往舞台 · P 手机可查看生涯"

func interact() -> void:
	if target=="ceremony":start_ceremony()
	elif target=="award" and ceremony_phase=="player_walk":
		var rank:=int(award_rows[current_index]["rank"]);awarded_ranks.append(rank)
		if is_instance_valid(player_trophy):player_trophy.queue_free()
		player_trophy=_trophy("YourAnnualAward",camera,.46);player_trophy.position=Vector3(.38,-.42,-.85)
		ceremony_phase="player_return";_set_caption("主持人：祝贺 %s！请回到观礼通道，典礼将继续。"%_row_name(award_rows[current_index]))

func start_ceremony() -> void:
	if not ceremony_phase in ["idle","finished"]:return
	for rank in guest_actors:
		var actor: Player=guest_actors[rank];actor.position=guest_homes[rank];actor.reset_physics_interpolation()
		actor.velocity=Vector3.ZERO;actor.locked=true;actor.seat_pose=true;actor.upper_body_action=""
	for trophy in guest_trophies.values():
		if is_instance_valid(trophy):trophy.queue_free()
	guest_trophies.clear();called_ranks.clear();awarded_ranks.clear();completed_ranks.clear()
	current_index=-1;ceremony_phase="opening";ceremony_clock=0
	_set_caption("主持人：欢迎来到 %s 年度选手颁奖。我们依次公布第三名、第二名与第一名。"%awards_year if finalized else "主持人：欢迎观看预览典礼。以下示例姓名仅用于展示领奖流程。")

func _call_next() -> void:
	current_index+=1;ceremony_clock=0
	if current_index>=award_rows.size():
		ceremony_phase="finished";active_actor=null;ceremony_name.text="荣耀属于每一位选手"
		_set_caption("年度颁奖结束。恭喜所有入选选手。" if finalized else "预览典礼结束。实际年度排名将在生涯年度结算后显示。")
		return
	var row: Dictionary=award_rows[current_index];var rank:=int(row["rank"]);called_ranks.append(rank)
	ceremony_name.text="#%d  %s"%[rank,_row_name(row)]
	_set_caption("主持人：年度%s名，%s。请上台领奖。"%[{3:"第三",2:"第二",1:"第一"}[rank],_row_name(row)] if finalized else "主持人：预览席位 #%d，%s。请上台演示领奖。"%[rank,_row_name(row)])
	ceremony_phase="announce";active_actor=null if _is_human(row) else guest_actors.get(rank)

func _set_actor_route(points: Array[Vector3]) -> void:
	actor_route=points;route_index=0
	if active_actor:active_actor.locked=false;active_actor.seat_pose=false;active_actor.test_direction=Vector3.ZERO

func _walk_actor() -> bool:
	if not active_actor:return false
	while route_index<actor_route.size() and Vector2(active_actor.position.x-actor_route[route_index].x,active_actor.position.z-actor_route[route_index].z).length()<.14:route_index+=1
	if route_index>=actor_route.size():active_actor.test_direction=Vector3.ZERO;active_actor.velocity=Vector3.ZERO;active_actor.locked=true;return true
	var direction:=actor_route[route_index]-active_actor.position;direction.y=0;active_actor.test_direction=direction.normalized();return false

func _update_venue(delta: float) -> void:
	if paused or CareerBridge.phone_open or Travel.busy:return
	ceremony_clock+=delta*ceremony_speed
	match ceremony_phase:
		"opening":
			if ceremony_clock>3.4:_call_next()
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
				var trophy:=_trophy("RecipientAward"+str(rank),active_actor.visual,.52);trophy.position=Vector3(0,.88,.39);guest_trophies[rank]=trophy;active_actor.upper_body_action="typing"
				_set_caption("主持人：祝贺 %s。"%_row_name(award_rows[current_index]))
		"award":
			if ceremony_clock>3.2:
				ceremony_phase="walk_back"
				var rank:=int(award_rows[current_index]["rank"])
				var route: Array[Vector3]=[Vector3(0,.61,-6.9),Vector3(0,0,-4.35),Vector3(0,0,-3.6),guest_homes[rank]]
				_set_actor_route(route)
		"walk_back":
			if _walk_actor():
				active_actor.seat_pose=true;active_actor.face_toward(Vector3(active_actor.position.x,0,-9));completed_ranks.append(int(award_rows[current_index]["rank"]));ceremony_phase="between";ceremony_clock=0
		"player_return":
			if _distance(audience_return_point)<1.4 and player.position.y<.2:completed_ranks.append(int(award_rows[current_index]["rank"]));ceremony_phase="between";ceremony_clock=0
		"between":
			if ceremony_clock>1.3:_call_next()

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
	return {"destination":"awards","finalized":finalized,"preview":preview,"year":awards_year,"source":ceremony_source,"top20_rows":top20_rows.size(),"attendees":audience_count,"static_guests":static_guest_count,"recipient_attendee_ids":recipient_attendee_ids.duplicate(),"species":"chicken","enclosed":has_node("ClosedCeiling"),"colliders":collision_count,"phase":ceremony_phase,"called_ranks":called_ranks.duplicate(),"awarded_ranks":awarded_ranks.duplicate(),"completed_ranks":completed_ranks.duplicate(),"host_voice":"captions only"}
