extends Node3D
const Actor=preload("res://scripts/club_npc.gd")
const Navigation=preload("res://scripts/club_navigation.gd")
signal dialogue_changed
signal dialogue_closed
signal conversation_choice(npc_id: String,topic: String)
var roster: Array[Actor]=[]
var data: Dictionary
var navigation: RefCounted
var player
var nearest: Actor
var speaker: Actor
var line: String=""
var topic_selected: String=""
var clock:=0.0
var reservations: Dictionary={}
var enabled:=true
var held:=false
var scan_time:=0.0
var waits:=0
var replans:=0
var invalid_sites: Array[String]=[]
var career_context: Dictionary={}
var bound_team_id: String=""
const STAFF: Array[String]=["coach","manager","chef","analyst"]
const ROLE_KEYS: Dictionary={"igl":"igl","指挥":"igl","awp":"awp","awper":"awp","主狙":"awp","entry":"entry","突破手":"entry","lurker":"lurker","lurk":"lurker","自由人":"lurker","support":"rifle","rifle":"rifle","步枪手":"rifle"}

func setup(actor,audit: Array,saved: Dictionary={}) -> void:
	player=actor;data=JSON.parse_string(FileAccess.get_file_as_string("res://data/club_life.json"))
	assert(data.get("schema_version")==1)
	navigation=Navigation.new();navigation.build(audit)
	for id in data["sites"]:
		var p:=vec(data["sites"][id]["position"])
		var c: Vector2i=navigation.nearest(p)
		if c.x<0 or navigation.world(c).distance_to(p)>.85:invalid_sites.append(id)
		else:data["sites"][id]["target"]=navigation.world(c)
	assert(invalid_sites.is_empty(),"Some NPC sites are inaccessible: "+str(invalid_sites))
	for row in data["npcs"]:
		if _player_site(str(row["schedule"][0][0])):continue
		var npc:=Actor.new();npc.definition=row.duplicate(true);npc.manager=self;npc.name="NPC_"+str(row["id"])
		var site_id: String=row["schedule"][0][0];var site: Dictionary=data["sites"][site_id]
		npc.position=site["target"];add_child(npc);roster.append(npc)
		npc.arrived.connect(_arrived.bind(npc))
		reservations[site_id]=npc.npc_id
		npc.start_job(site_id,site,float(row["start_remaining"]))
	if saved.has("career"):bind_career(saved["career"])
	if not saved.is_empty():restore(saved)
	print("CLUB_LIFE_READY npcs=",roster.size()," invalid_sites=",invalid_sites)

func bind_career(context: Dictionary) -> void:
	if data.is_empty() or not context.has("player") or not context.has("team"):return
	var player_value=context.get("player")
	if not player_value is Dictionary:return
	var player_row: Dictionary=player_value
	var player_id: String=str(player_row.get("id",""))
	if player_id.is_empty():return
	var team_value=context.get("team")
	var team_row: Dictionary=team_value if team_value is Dictionary else {}
	var roster_value=team_row.get("roster",[])
	var rows: Array=roster_value if roster_value is Array else []
	var teammates: Array[Dictionary]=[];var wanted: Dictionary={}
	for raw in rows:
		if not raw is Dictionary:continue
		var id: String=str(raw.get("id",""))
		if id.is_empty() or id==player_id or raw.get("you",false) or wanted.has(id):continue
		if teammates.size()>=4:break
		wanted[id]=true;teammates.append(raw.duplicate(true))
	var pool: Array[Actor]=[];var retained: Dictionary={}
	for npc in roster:
		if npc.template_id in STAFF:continue
		if wanted.has(npc.npc_id):retained[npc.npc_id]=npc
		else:pool.append(npc)
	for row in teammates:
		var key: String=ROLE_KEYS.get(str(row.get("role","rifle")).to_lower(),"rifle")
		var npc: Actor=retained.get(str(row["id"]))
		if npc==null:
			if not pool.is_empty():
				for candidate in pool:
					var candidate_key: String=ROLE_KEYS.get(str(candidate.definition.get("career_role",candidate.definition["role"])).to_lower(),"rifle")
					if candidate_key==key:npc=candidate;break
				if npc==null:npc=pool[0]
				pool.erase(npc)
			else:
				var used: Array[String]=[]
				for other in roster:used.append(other.template_id)
				var definition: Dictionary={}
				for candidate in data["npcs"]:
					if str(candidate["id"]) in STAFF or str(candidate["id"]) in used:continue
					if _player_site(str(candidate["schedule"][0][0])):continue
					if reservations.has(str(candidate["schedule"][0][0])):continue
					if definition.is_empty():definition=candidate.duplicate(true)
					if ROLE_KEYS.get(str(candidate["role"]).to_lower(),"rifle")==key:
						definition=candidate.duplicate(true);break
				if definition.is_empty():continue
				npc=Actor.new();npc.definition=definition;npc.manager=self
				var first: String=definition["schedule"][0][0]
				npc.position=data["sites"][first]["target"];add_child(npc);roster.append(npc)
				npc.arrived.connect(_arrived.bind(npc))
				npc.start_job(first,data["sites"][first],float(definition["start_remaining"]))
			# Release the previous identity before adopting the actual player ID.
			if reservations.get(npc.site_id)==npc.npc_id:reservations.erase(npc.site_id)
			reservations[npc.site_id]=str(row["id"])
			if speaker==npc:close()
			npc.bond=0;npc.topics.clear();npc.encourage_at=-1000
		npc.bind_identity(row,data["role_templates"][key])
	for npc in pool:
		if speaker==npc:close()
		if nearest==npc:nearest=null
		if reservations.get(npc.site_id)==npc.npc_id:reservations.erase(npc.site_id)
		roster.erase(npc);npc.queue_free()
	bound_team_id=str(team_row.get("id",""))
	career_context={"player":{"id":player_id},"team":{"id":bound_team_id,"roster":teammates.duplicate(true)}}

func vec(a: Array) -> Vector3:return Vector3(a[0],a[1],a[2])

func _player_site(id: String) -> bool:
	return bool(data["sites"].get(id,{}).get("player_only",false))

func _physics_process(delta: float) -> void:
	if player==null or not enabled or held:return
	clock+=delta
	for npc in roster:
		if npc.talking:continue
		if npc.state=="doing":
			npc.remaining-=delta
			if npc.remaining<=0:_next(npc)
		elif npc.state=="waiting":
			npc.remaining-=delta
			if npc.remaining<=0:_next(npc)
		elif npc.state=="walking" and npc.progress_time>=2:
			var stalled: bool=Vector2(npc.position.x-npc.progress_anchor.x,npc.position.z-npc.progress_anchor.z).length()<.65
			npc.progress_time=0;npc.progress_anchor=npc.position
			if stalled:
				var points: Array[Vector3]=navigation.path(npc.position,npc.destination,_people(npc))
				replans+=1
				if not points.is_empty():npc.route=points;npc.route_index=0;npc.sidestep_time=0
	scan_time-=delta
	if scan_time<=0:
		scan_time=.12;nearest=nearest_npc()
		for npc in roster:npc.nameplate.visible=npc==nearest or npc==speaker

func _people(npc: Actor) -> Array:
	var bodies: Array=[{"position":player.position,"radius":.60}]
	for other in roster:
		if other!=npc:bodies.append({"position":other.position,"radius":.55})
	return bodies

func _next(npc: Actor) -> void:
	# Shared stations may be occupied. Pick another activity from THIS
	# character's schedule instead of forming a circular hold-and-wait chain.
	var schedule: Array=npc.definition["schedule"]
	var next_index: int=-1
	var requested: String=""
	for offset in range(1,schedule.size()+1):
		var candidate: int=(npc.schedule_index+offset)%schedule.size()
		var site: String=schedule[candidate][0]
		if _player_site(site):continue
		if site==npc.site_id:continue
		if not reservations.has(site) or reservations[site]==npc.npc_id:
			next_index=candidate;requested=site;break
	if next_index<0:npc.remaining=3;waits+=1;return
	# Do not snap out of a seat into someone standing in the aisle.
	if npc.seat_pose and not clear_of_people(npc.approach,npc,.60):npc.remaining=2;return
	var target: Vector3=data["sites"][requested]["target"]
	var start: Vector3=npc.approach if npc.seat_pose else npc.position
	var points: Array[Vector3]=navigation.path(start,target,_people(npc))
	if points.is_empty():npc.remaining=4;waits+=1;return
	if reservations.get(npc.site_id)==npc.npc_id:reservations.erase(npc.site_id)
	reservations[requested]=npc.npc_id
	npc.leave_seat();npc.schedule_index=next_index;npc.site_id=requested
	npc.activity_label="去"+str(data["sites"][requested]["label"])
	npc.finished_jobs+=1;npc.start_route(points,target)

func _arrived(npc: Actor) -> void:
	if _player_site(npc.site_id):
		_next(npc);return
	var site: Dictionary=data["sites"][npc.site_id]
	if npc.position.distance_to(site["target"])>.30 or not clear_of_people(npc.position,npc,.46):
		npc.test_direction=Vector3.ZERO;return
	npc.start_job(npc.site_id,site,float(npc.definition["schedule"][npc.schedule_index][1]))

func clear_of_people(p: Vector3,npc: Actor,range_value: float) -> bool:
	if Vector2(p.x-player.position.x,p.z-player.position.z).length()<range_value:return false
	for other in roster:
		if other==npc:continue
		if Vector2(p.x-other.position.x,p.z-other.position.z).length()<range_value:return false
	return true

func steer(npc: Actor,direction: Vector3,delta: float) -> Vector3:
	if not enabled or held:return Vector3.ZERO
	if npc.sidestep_time>0:
		npc.sidestep_time-=delta
		var ahead: Vector3=npc.position+npc.sidestep*.30
		if navigation.segment(npc.position,ahead) and clear_of_people(ahead,npc,.50):return npc.sidestep*.65
		npc.sidestep_time=0
	var blocker: Node3D=null
	var bodies: Array[Node3D]=[player]
	for other in roster:
		if other!=npc:bodies.append(other)
	for other in bodies:
		var offset: Vector3=other.position-npc.position;offset.y=0
		if offset.length()<.70 and offset.normalized().dot(direction)>.55:blocker=other;break
	if blocker:
		# Try a short clear side step, never push the player or teleport through
		# a doorway. Keeping the chosen side briefly prevents left/right jitter.
		var right:=Vector3(-direction.z,0,direction.x)
		for side in [right,-right]:
			var p: Vector3=npc.position+side*.60
			if navigation.segment(npc.position,p) and clear_of_people(p,npc,.62):
				npc.sidestep=side;npc.sidestep_time=.38;return side*.65
		# Deterministic right of way in a narrow doorway. The yielding chicken
		# physically backs out until a wider patch allows the dynamic path to pass.
		if blocker is Actor and npc.npc_id>blocker.npc_id:
			var behind: Vector3=npc.position-direction*.65
			if navigation.segment(npc.position,behind) and clear_of_people(behind,npc,.53):
				npc.sidestep=-direction;npc.sidestep_time=.55;return -direction*.65
		return Vector3.ZERO
	return direction

func can_talk(npc: Actor) -> bool:
	var delta: Vector3=npc.position-player.position
	if Vector2(delta.x,delta.z).length()>2.55:return false
	var origin: Vector3=player.position+Vector3(0,1.35,0)
	var target: Vector3=npc.position+Vector3(0,1.2,0)
	var query:=PhysicsRayQueryParameters3D.create(origin,target,1)
	var space:PhysicsDirectSpaceState3D=player.get_world_3d().direct_space_state
	if not space.intersect_ray(query).is_empty():return false
	var wall_ray:=PhysicsRayQueryParameters3D.create(Vector3(origin.x,.85,origin.z),Vector3(target.x,.85,target.z),8)
	return space.intersect_ray(wall_ray).is_empty()

func nearest_npc() -> Actor:
	var result: Actor=null;var distance:=INF
	for npc in roster:
		if not can_talk(npc):continue
		var d: float=player.position.distance_squared_to(npc.position)
		if d<distance:result=npc;distance=d
	return result

func begin(npc: Actor=null) -> bool:
	if speaker:return false
	if npc==null:npc=nearest_npc()
	if npc==null or not can_talk(npc):return false
	speaker=npc;player.locked=true;player.velocity=Vector3.ZERO;player.face_toward(npc.position)
	npc.begin_talk(player.position)
	line=_pick(data["activity_lines"].get(npc.talk_action,["我在这儿，你说。"]),"activity:"+npc.talk_action)
	topic_selected="正在"+npc.activity_label;dialogue_changed.emit();return true

func _pick(lines: Array,key: String) -> String:
	var index: int=int(speaker.topics.get(key,0))%lines.size()
	speaker.topics[key]=int(speaker.topics.get(key,0))+1
	return str(lines[index])

func choose(topic: String) -> void:
	if speaker==null:return
	match topic:
		"busy":
			topic_selected="你在忙什么？"
			line=_pick(data["activity_lines"].get(speaker.talk_action,["休息一会儿。"]),"activity:"+speaker.talk_action)
		"training":
			topic_selected="聊聊最近的训练"
			line=_pick(speaker.definition["training"],"training")
		"encourage":
			topic_selected="一起加油。"
			line=_pick(speaker.definition["encourage"],"encourage")
			if clock-speaker.encourage_at>=60:
				speaker.bond=mini(5,speaker.bond+1);speaker.encourage_at=clock
		"leave":close();return
	conversation_choice.emit(speaker.npc_id,topic);dialogue_changed.emit()

func close() -> void:
	if speaker==null:return
	speaker.end_talk();speaker=null;player.locked=false;player.velocity=Vector3.ZERO
	dialogue_closed.emit()

func snapshot() -> Dictionary:
	var states: Dictionary={}
	for npc in roster:
		states[npc.npc_id]={"index":npc.schedule_index,"site":npc.site_id,"state":npc.state,"remaining":npc.remaining,"position":[npc.position.x,npc.position.y,npc.position.z],"approach":[npc.approach.x,npc.approach.y,npc.approach.z],"bond":npc.bond,"topics":npc.topics.duplicate(),"encourage_at":npc.encourage_at}
	return {"clock":clock,"npcs":states,"career":career_context.duplicate(true)}

func restore(saved: Dictionary) -> void:
	if saved.has("career") and not saved["career"].is_empty() and saved["career"]!=career_context:bind_career(saved["career"])
	clock=float(saved.get("clock",0));reservations.clear()
	# Claim valid saved destinations before relocating an obsolete player-seat
	# occupant, so its fallback cannot steal another teammate's saved station.
	for npc in roster:
		var site_id: String=str(saved.get("npcs",{}).get(npc.npc_id,{}).get("site",npc.site_id))
		if not _player_site(site_id):reservations[site_id]=npc.npc_id
	for npc in roster:
		var row: Dictionary=saved.get("npcs",{}).get(npc.npc_id,{})
		if row.is_empty():reservations[npc.site_id]=npc.npc_id;continue
		npc.bond=int(row["bond"]);npc.topics=row["topics"].duplicate();npc.encourage_at=float(row["encourage_at"])
		# Old scene snapshots may place a teammate in the player's seat. Keep
		# their identity/bond, but start an allowed activity when re-entering.
		if _player_site(str(row["site"])):
			for i in range(npc.definition["schedule"].size()):
				var fallback: String=npc.definition["schedule"][i][0]
				if _player_site(fallback) or reservations.has(fallback):continue
				npc.schedule_index=i;reservations[fallback]=npc.npc_id
				npc.position=data["sites"][fallback]["target"];npc.reset_physics_interpolation()
				npc.start_job(fallback,data["sites"][fallback],float(npc.definition["schedule"][i][1]))
				break
			continue
		npc.schedule_index=int(row["index"]);npc.site_id=str(row["site"]);reservations[npc.site_id]=npc.npc_id
		var site: Dictionary=data["sites"][npc.site_id]
		npc.position=vec(row["approach"] if row["state"]=="doing" and site.has("seat") else row["position"])
		npc.reset_physics_interpolation()
		if row["state"]=="walking":npc.start_route(navigation.path(npc.position,site["target"]),site["target"])
		else:npc.start_job(npc.site_id,site,float(row["remaining"]))
