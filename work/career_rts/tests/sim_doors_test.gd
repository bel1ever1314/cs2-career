extends SceneTree
## Exercise real simulation movement/traffic plus the WASD input handler.
## No opponent/combat, career state, filesystem writes or input automation.
const Sim = preload("res://scripts/match_sim.gd")
var checks := 0
var failures: Array[String] = []
var results: Array = []

class OneWayNav extends RefCounted:
	func nearest_walkable(point: Vector2, _radius: float) -> Vector2:return point
	func segment_blocked(from: Vector2, to: Vector2, _radius: float) -> bool:return from.x>=100.0 and to.x<100.0
	func find_path(from: Vector2, to: Vector2, radius: float, _side: String) -> Array:return [] if segment_blocked(from,to,radius) else [to]
	func constrain_motion(from: Vector2, to: Vector2, radius: float) -> Vector2:return from if segment_blocked(from,to,radius) else to

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok:
		failures.append(label)
		push_error(label)

func prepare(sim, point: Vector2, count: int, human: bool = false) -> Array:
	var chosen: Array = []
	for p in sim._players:
		p["alive"] = p["team"] == "t" and int(p["index"]) < count
		p["human"] = human and p["alive"]
		p["walking"] = false
		p["path"] = []
		p["queued_goals"] = []
		p["route_ingress"] = []
		p["route_via"] = ""
		p["yield_until"] = 0.0
		p["traffic_yield_for"] = ""
		p["traffic_yield_path"] = []
		p.erase("traffic_active_target")
		p["travel_since"] = sim._time
		if p["alive"]:
			var offset := Vector2.ZERO if count == 1 else Vector2.from_angle(int(p["index"]) * TAU / count) * 9.0
			p["pos"] = sim._nav.nearest_walkable(point + offset, Sim.PLAYER_RADIUS)
			p["travel_mark"] = p["pos"]
			p["goal"] = p["pos"]
			chosen.append(p)
	return chosen

func advance_clock(sim) -> void:
	sim._tick += 1
	sim._time = sim._tick * Sim.FIXED_DT

func test_group(sim, start: Vector2, finish: Vector2, count: int, label: String) -> void:
	var actors := prepare(sim, start, count)
	var ids: Array = actors.map(func(p): return p["id"])
	check(sim.command_move("t",finish,ids),label+" real group command accepted")
	var valid := true
	var body_safe := true
	var frames := 0
	for frame in range(3600):
		advance_clock(sim)
		for p in actors:
			var before: Vector2 = p["pos"]
			p["moving"] = false
			sim._follow_path(p)
			if not sim._nav.is_walkable(p["pos"],Sim.PLAYER_RADIUS) or sim._nav.segment_blocked(before,p["pos"],Sim.PLAYER_RADIUS):valid=false
		for p in actors:
			for other in actors:
				if p["id"]!=other["id"] and Vector2(p["pos"]).distance_to(other["pos"])<Sim.PLAYER_RADIUS*2-.03:body_safe=false
		frames=frame+1
		if actors.all(func(p): return Vector2(p["pos"]).distance_to(p["goal"])<.1):break
	check(valid,label+" every sim tick stays on directed NAV")
	check(body_safe,label+" body collisions remain enabled")
	var reached := actors.all(func(p): return Vector2(p["pos"]).distance_to(p["goal"])<.1)
	check(reached,label+" all commanded actors reach door's far side")
	if not reached:
		print("TRAFFIC_FAIL ",JSON.stringify({"label":label,"time":sim._time,"actors":actors.map(func(p): return {"id":p["id"],"pos":str(p["pos"]),"goal":str(p["goal"]),"head":str(p["path"]),"yield_for":p.get("traffic_yield_for",""),"yield_path":str(p.get("traffic_yield_path",[])),"deadline":p.get("traffic_yield_deadline",0),"best":p.get("travel_best",0),"since":p.get("travel_since",0)})}))
	results.append({"label":label,"count":count,"frames":frames,"reached":reached,"actors":actors.map(func(p): return {"id":p["id"],"left":Vector2(p["pos"]).distance_to(p["goal"]),"pos":[p["pos"].x,p["pos"].y],"goal":[p["goal"].x,p["goal"].y],"path_left":p["path"].size(),"path_head":str(p["path"][0]) if not p["path"].is_empty() else "done"})})

func test_wasd(sim, start: Vector2, finish: Vector2, label: String) -> void:
	var actors := prepare(sim,start,1,true)
	var p: Dictionary = actors[0]
	# Keep the raw adjacent NAV cells: their eight directions are exactly the
	# keyboard's cardinal/diagonal WASD vectors, not arbitrary AI steering.
	var first: int = sim._nav._nearest_cell(start,Sim.PLAYER_RADIUS)
	var last: int = sim._nav._nearest_cell(finish,Sim.PLAYER_RADIUS)
	var graph = sim._nav._graph_for(Sim.PLAYER_RADIUS)
	graph.set_side("")
	var path: PackedVector2Array = graph.get_point_path(first,last)
	check(not path.is_empty(),label+" keyboard route has connected actual NAV cells")
	if path.is_empty():return
	p["pos"] = path[0]
	var valid := true
	var stuck := false
	var frames := 0
	for goal in path:
		while Vector2(p["pos"]).distance_to(goal)>.001 and frames<10000:
			advance_clock(sim)
			var before: Vector2 = p["pos"]
			var difference: Vector2 = goal-before
			var amount := minf(.13,difference.length())
			var move := difference.normalized()*amount/(Sim.MOVE_SPEED*Sim.WALK_FACTOR*Sim.FIXED_DT)
			var interactions: Array[Dictionary] = []
			sim._human_tick(p,{"_actor_id":p["id"],"move":move,"walk":true,"aim":goal},interactions)
			frames+=1
			if not sim._nav.is_walkable(p["pos"],Sim.PLAYER_RADIUS) or sim._nav.segment_blocked(before,p["pos"],Sim.PLAYER_RADIUS):valid=false
			if before.distance_squared_to(p["pos"])<.000000001:
				stuck=true
				break
		if stuck or not valid:break
	check(valid and not stuck,label+" actual WASD handler's .13px microsteps pass without wall bypass")
	check(Vector2(p["pos"]).distance_to(path[-1])<.01,label+" human reaches far-side cell")
	results.append({"label":label,"input":"WASD_8_directions_walk","frames":frames,"stuck":stuck,"distance_left":Vector2(p["pos"]).distance_to(path[-1])})

func test_traffic_lifecycle(sim) -> void:
	var actors := prepare(sim,Vector2(220,230),1)
	var p: Dictionary = actors[0]
	p["traffic_yield_for"]="old_requester"
	p["traffic_yield_path"]=[Vector2(210,230)]
	p["traffic_active_target"]=Vector2(210,230)
	check(sim.command_move("t",Vector2(290,242),[p["id"]]),"replacement RTS move accepted during yield")
	check(not p.has("traffic_active_target") and p["traffic_yield_for"].is_empty() and p["traffic_yield_path"].is_empty(),"replacement move clears all temporary steering state")
	var real_nav = sim._nav
	sim._nav=OneWayNav.new()
	actors=prepare(sim,Vector2(90,100),2)
	p=actors[0]
	var requester: Dictionary=actors[1]
	p["pos"]=Vector2(99,100)
	p["goal"]=p["pos"]
	requester["pos"]=Vector2(99,108)
	requester["path"]=[Vector2(99,90)]
	check(sim._begin_traffic_yield(p,requester),"one-way fixture still offers a legal courtesy step")
	var return_safe := true
	var previous: Vector2=p["pos"]
	for point in p["traffic_yield_path"]:
		if sim._nav.segment_blocked(point,previous,Sim.PLAYER_RADIUS):return_safe=false
		previous=point
	check(return_safe,"temporary yield does not enter an irreversible portal")
	sim._request_traffic_clearance(p,[requester["pos"]])
	check(requester["traffic_yield_for"].is_empty(),"yielding blocker cannot ask its own requester to yield")
	p["pos"]=Vector2(99.8,100)
	requester["pos"]=Vector2(99,115)
	sim._move_player(p,Vector2.RIGHT)
	check(Vector2(p["pos"]).distance_to(Vector2(99.8,100))<.001,"actual temporary microstep cannot fall through one-way portal")
	p["pos"]=Vector2(101,100)
	p["path"]=[Vector2(98,100),Vector2(95,100)]
	p["traffic_yield_deadline"]=sim._time-1
	check(sim._follow_traffic_yield(p) and p["path"]==[Vector2(98,100),Vector2(95,100)],"failed rejoin never appends an unproven route suffix")
	sim._nav=real_nav

func run() -> void:
	var source: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/dust2_game.json"))
	var roster: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/rosters.json"))
	roster["human_id"] = ""
	var sim := Sim.new()
	var configured: bool = sim.configure(source,roster,771)
	check(configured,"real match simulator configures with repaired directed map")
	if not configured:
		quit(1)
		return
	test_traffic_lifecycle(sim)
	var probes := [
		["B doors",Vector2(220,230),Vector2(290,242)],
		["mid doors",Vector2(458,330),Vector2(462,405)],
		["long outer door",Vector2(700,690),Vector2(710,620)],
		["long inner door",Vector2(710,620),Vector2(730,540)]
	]
	for row in probes:
		for count in [1,5]:
			test_group(sim,row[1],row[2],count,str(row[0])+" "+str(count)+" actors")
			test_group(sim,row[2],row[1],count,str(row[0])+" reverse "+str(count)+" actors")
		test_wasd(sim,row[1],row[2],str(row[0])+" human forward")
		test_wasd(sim,row[2],row[1],str(row[0])+" human reverse")
	print("SIM_DOORS_RESULT ",JSON.stringify({"checks":checks,"failures":failures,"results":results}))
	quit(0 if failures.is_empty() else 1)
