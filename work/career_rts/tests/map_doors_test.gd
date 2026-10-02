extends SceneTree
## Regression for actual Dust2 NAV doors: walk every route at fixed-step speed,
## rather than accepting A* reachability as proof that a character can pass.
const MapModel = preload("res://scripts/map_model.gd")
const RADIUS := 3.5
const STEP := 1.0
var checks := 0
var failures: Array[String] = []
var route_results: Array = []

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok:
		failures.append(label)
		push_error(label)

func walk_route(nav, start: Vector2, finish: Vector2, label: String, step_size: float = STEP) -> void:
	check(nav.is_walkable(start, RADIUS), label + " start has full body clearance")
	check(nav.is_walkable(finish, RADIUS), label + " finish has full body clearance")
	var route: Array[Vector2] = nav.find_path(start, finish, RADIUS)
	check(not route.is_empty(), label + " path exists")
	var position := start
	var max_frames := 10000
	var frames := 0
	var stalls := 0
	var valid := true
	var distance := 0.0
	for goal in route:
		distance += position.distance_to(goal)
		check(not nav.segment_blocked(position, goal, RADIUS), label + " full path leg does not cross wall")
		while position.distance_to(goal) > .001 and frames < max_frames:
			var next: Vector2 = nav.constrain_motion(position, position.move_toward(goal, step_size), RADIUS)
			if not nav.is_walkable(next, RADIUS) or nav.segment_blocked(position, next, RADIUS):
				print("UNSAFE_FRAME ",JSON.stringify({"label":label,"from":[position.x,position.y],"next":[next.x,next.y],"goal":[goal.x,goal.y],"next_walkable":nav.is_walkable(next,RADIUS)}))
				valid = false
				break
			if next.distance_squared_to(position) < .00000001:
				stalls += 1
				break
			position = next
			frames += 1
		if not valid or stalls > 0 or frames >= max_frames:
			break
	check(valid, label + " every actual frame stays collision-safe")
	check(stalls == 0, label + " no door stall at fixed-step movement")
	check(position.distance_to(finish) < .01, label + " actual movement reaches far side")
	if label.begins_with("B doors") or label.begins_with("mid doors") or label.begins_with("long "):
		check(distance<180.0,label+" crosses the actual local doorway without a distant detour")
	route_results.append({"label":label,"frames":frames,"stalls":stalls,"distance_left":position.distance_to(finish),"last_position":[position.x,position.y],"path_nodes":route.size(),"distance":distance})

func run() -> void:
	var decoded = JSON.parse_string(FileAccess.get_file_as_string("res://data/dust2_game.json"))
	check(decoded is Dictionary, "actual NAV map data exists")
	if not decoded is Dictionary:
		quit(1)
		return
	var nav := MapModel.new()
	nav.setup(decoded)
	check(nav.validation_report(RADIUS)["navigation_space"]=="NAV_agent_centres","data explicitly identifies approximate NAV centre navigation")
	check(nav.validation_report(RADIUS)["cell_size"]==2.0,"dense two-pixel offline grid preserves narrow doors")
	var probes := [
		["B doors", Vector2(232,230), Vector2(284,242)],
		["mid doors", Vector2(478,350), Vector2(460,395)],
		["long outer door", Vector2(700,690), Vector2(710,620)],
		["long inner door", Vector2(710,620), Vector2(730,540)],
		["upper tunnel exit", Vector2(170,318), Vector2(174,426)],
		["upper/lower tunnel stairs", Vector2(294,482), Vector2(305,420)]
	]
	for row in probes:
		var start: Vector2 = nav.nearest_walkable(row[1],RADIUS)
		var finish: Vector2 = nav.nearest_walkable(row[2],RADIUS)
		print("DOOR_PROBE ",JSON.stringify({"label":row[0],"start":[start.x,start.y],"finish":[finish.x,finish.y],"snapped_start":start.distance_to(row[1]),"snapped_finish":finish.distance_to(row[2])}))
		check(start.distance_to(row[1])<.01 and finish.distance_to(row[2])<.01,str(row[0])+" endpoints are on both sides without a snap across the doorway")
		walk_route(nav,start,finish,str(row[0]))
		walk_route(nav,finish,start,str(row[0])+" reverse",.63)
	# Subcell clicks / actor positions must not borrow another endpoint's
	# clearance from the path cache, nor append a blocked last leg unchecked.
	var random := RandomNumberGenerator.new()
	random.seed=261001
	var subcell_valid := true
	for row in probes:
		for attempt in range(12):
			var start: Vector2 = row[1]+Vector2(random.randf_range(-.9,.9),random.randf_range(-.9,.9))
			var finish: Vector2 = row[2]+Vector2(random.randf_range(-.9,.9),random.randf_range(-.9,.9))
			if not nav.is_walkable(start,RADIUS) or not nav.is_walkable(finish,RADIUS):continue
			var path: Array[Vector2] = nav.find_path(start,finish,RADIUS)
			if path.is_empty():subcell_valid=false;continue
			var point := start
			for goal in path:
				if nav.segment_blocked(point,goal,RADIUS):subcell_valid=false
				point=goal
			if point.distance_to(finish)>.001:subcell_valid=false
	check(subcell_valid,"72 seeded non-cell-centre door endpoint probes return only legal exact paths")
	for side in ["t","ct"]:
		for spawn_value in decoded["spawns"][side]:
			for site in ["A","B"]:
				walk_route(nav,nav.vec(spawn_value),nav.vec(decoded["sites"][site]["center"]),side+str(spawn_value)+" -> "+site,.7)
	var t_spawn: Vector2 = nav.vec(decoded["spawns"]["t"][0])
	var site_a: Vector2 = nav.vec(decoded["sites"]["A"]["center"])
	var site_b: Vector2 = nav.vec(decoded["sites"]["B"]["center"])
	check(nav.segment_blocked(site_a,site_b,RADIUS),"no direct movement through solid A/B separating walls")
	check(nav.segment_blocked(t_spawn,Vector2.ZERO,RADIUS),"no movement through off-map wall")
	var stopped: Vector2 = nav.constrain_motion(t_spawn,Vector2.ZERO,RADIUS)
	check(nav.is_walkable(stopped,RADIUS) and nav.segment_blocked(stopped,Vector2.ZERO,RADIUS),"single huge frame stops at first wall")
	check(nav.is_walkable(Vector2(701,671),RADIUS) and not nav.is_walkable(Vector2(701,671),6.0),"a larger body still requires extra clearance at the narrow long door")
	var door_start := Vector2(232,230)
	var door_finish := Vector2(284,242)
	check(nav.segment_blocked(door_start,door_finish,RADIUS),"solid B door leaf still blocks a direct movement line")
	check(nav.segment_blocked(door_start,door_finish,0),"solid B door leaf still blocks a shooting ray")
	var leaf_stop: Vector2 = nav.constrain_motion(door_start,door_finish,RADIUS)
	check(leaf_stop.distance_to(door_finish)>1.0 and not nav.segment_blocked(door_start,leaf_stop,RADIUS),"huge input cannot tunnel directly through the door leaf")
	# Strip exactly ONE directed edge, not geometry. Reverse remains allowed;
	# forward movement must obey its NAV portal even with open floor pixels.
	var first: int = nav._nearest_cell(Vector2(220,230),RADIUS)
	var from_cell := Vector2i(first%nav._width,floori(float(first)/nav._width))
	var to_cell := from_cell+Vector2i.RIGHT
	var last: int = nav._cell_id(to_cell)
	var from_point: Vector2 = nav._cell_center(first)
	var to_point: Vector2 = nav._cell_center(last)
	check(not nav.segment_blocked(from_point,to_point,RADIUS) and not nav.segment_blocked(to_point,from_point,RADIUS),"portal fixture starts with two valid directed NAV edges")
	var edges: PackedByteArray = nav._edges.duplicate()
	edges[first] = edges[first] & ~(1<<0)
	nav._edges=edges
	check(nav.segment_blocked(from_point,to_point,RADIUS) and not nav.segment_blocked(to_point,from_point,RADIUS),"movement respects a missing forward portal without silently adding reverse links")
	print("DOORS_RESULT ",JSON.stringify({"checks":checks,"failures":failures,"routes":route_results}))
	quit(0 if failures.is_empty() else 1)
