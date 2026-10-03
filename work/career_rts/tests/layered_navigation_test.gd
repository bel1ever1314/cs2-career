extends SceneTree
const Catalog = preload("res://scripts/map_catalog.gd")
const Sim = preload("res://scripts/match_sim.gd")
const View = preload("res://scripts/renderer.gd")
var checks := 0
var failures: Array[String]=[]

func _initialize() -> void:call_deferred("_run")
func check(value: bool,label: String) -> void:
	checks+=1
	if not value:failures.append(label);push_error(label)

func _run() -> void:
	var roster: Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://data/rosters.json"))
	roster["human_id"]=""
	for map_id in ["de_nuke","de_vertigo"]:
		var sim=Sim.new()
		check(sim.configure(Catalog.load_map(map_id),roster,20261003),map_id+" setup")
		var nav=sim.get_map_model()
		check(nav.validation_report()["invalid_targets"].is_empty(),map_id+" raw tactical points are walkable: "+str(nav.validation_report()["invalid_targets"]))
		check(nav.validation_report()["layer_identity_preserved"],map_id+" independent floor identity")
		var has_overlap := false
		for node in range(262144):
			if nav._cell_walkable(node,3.5) and nav._cell_walkable(node+262144,3.5):
				var top: Vector2=nav._cell_center(node)
				var bottom: Vector2=nav._cell_center(node+262144)
				check(nav.segment_blocked(top,bottom,3.5),map_id+" overlapping XY cannot walk through floor")
				check(nav.segment_blocked(top,bottom,0),map_id+" overlapping XY cannot see/shoot through floor")
				check(nav.constrain_motion(top,bottom,3.5)==top,map_id+" motion does not accidentally switch floors")
				has_overlap=true;break
		check(has_overlap,map_id+" tests actual stacked NAV XY")
		var kinds: Dictionary={}
		var one_way := false
		var crossed := false
		for row in nav._traversals.values():
			kinds[row["kind"]]=true
			var first: Vector2=nav._cell_center(int(row["from"]))
			var last: Vector2=nav._cell_center(int(row["to"]))
			if row["kind"]=="drop" and nav.traversal_between(last,first).is_empty() and nav.segment_blocked(last,first,3.5):
				check(not nav.traversal_between(first,last).is_empty(),map_id+" one-way drop allowed forwards")
				check(nav.traversal_between(last,first).is_empty(),map_id+" one-way drop cannot reverse directly")
				one_way=true
			if nav.layer_at(first)!=nav.layer_at(last) and not crossed:
				for actor in sim._players:actor["alive"]=false
				var runner: Dictionary=sim._players[5]
				runner["alive"]=true;runner["pos"]=first;runner["path"]=[last]
				sim._follow_path(runner)
				check(runner.has("traversal"),map_id+" crossing starts explicit timed traversal")
				check(runner["pos"]==first,map_id+" does not switch floors immediately")
				for tick in range(600):
					sim._follow_path(runner)
					if not runner.has("traversal"):break
				check(runner["pos"]==last and runner["path"].is_empty(),map_id+" lands at verified other-floor endpoint")
				crossed=true
			if crossed and one_way:break
		check(crossed and one_way,map_id+" has real floor gates and directed drops")
		for row in nav._traversals.values():
			if row["kind"]!="ladder":continue
			for actor in sim._players:actor["alive"]=false
			var runner: Dictionary=sim._players[5]
			var first: Vector2=nav._cell_center(int(row["from"]))
			var last: Vector2=nav._cell_center(int(row["to"]))
			runner["alive"]=true;runner["pos"]=first;runner["path"]=[]
			var direction := Vector2(last.x-first.x,fposmod(last.y,1024.0)-fposmod(first.y,1024.0)).normalized()
			if direction.is_zero_approx():direction=Vector2.UP
			var interactions: Array[Dictionary]=[]
			sim._human_tick(runner,{"move":direction,"interact":true,"_actor_id":runner["id"]},interactions)
			check(runner.get("manual_traverse",false) and runner.has("traversal"),map_id+" E plus direction starts real ladder action")
			check(runner["pos"]==first and not interactions.has(runner),map_id+" climb does not become plant/defuse or floor teleport")
			for tick in range(600):
				if runner.has("traversal"):sim._advance_traversal(runner)
				else:break
			check(runner["pos"]==last,map_id+" manual ladder lands at source-verified endpoint")
			runner.erase("manual_traverse")
			break
		# Every spawn can reach both objectives with no unclassified motion leg.
		for side in ["t","ct"]:
			for index in range(5):
				for site in ["A","B"]:
					var start: Vector2=sim._spawn(side,index)
					var route: Array=nav.find_path(start,sim._target(site+"_site"),3.5,side)
					check(not route.is_empty(),map_id+side+str(index)+" reaches "+site)
					for point in route:
						check(not nav.segment_blocked(start,point,3.5) or not nav.traversal_between(start,point).is_empty(),map_id+" every route leg is walk or verified gate")
						start=point
		var view=View.new();root.add_child(view)
		view.setup(Catalog.load_map(map_id),nav)
		view.size=Vector2(700,700)
		view.set_layer(1)
		view._reframe()
		var lower:=Vector2(512,1536)
		check(view.screen_to_world(view.world_to_local(lower)+view.global_position).distance_to(lower)<.01,map_id+" lower floor input projection roundtrip")
		check(view._can_see({"pos":Vector2(512,512),"team":"t"})==false,map_id+" main map hides other-floor actors")
		view.queue_free()
		print("LAYERED_PASS "+map_id)
	_test_timing_and_landing(roster)
	print("LAYERED_RESULT "+JSON.stringify({"checks":checks,"failures":failures}))
	quit(0 if failures.is_empty() else 1)

func _test_timing_and_landing(roster: Dictionary) -> void:
	var sim=Sim.new();sim.configure(Catalog.load_map("de_dust2"),roster,20261003)
	for actor in sim._players:actor["alive"]=false
	var runner: Dictionary=sim._players[5]
	runner["alive"]=true
	var first: Vector2=sim._spawn("t",0)
	var last: Vector2=sim._spawn("t",1)
	for kind in ["step","jump","drop","ladder","ramp"]:
		runner["pos"]=first;runner["path"]=[last]
		runner["traversal"]={"start":first,"finish":last,"elapsed":0.0,"seconds":.5,"kind":kind}
		for tick in range(15):sim._advance_traversal(runner)
		check(runner["pos"]==first and runner["motion_progress"]>0 and runner["motion_progress"]<1,kind+" has nonzero timed movement")
		if kind=="jump":check(float(runner["height_offset"])>0,"jump arc is visually elevated")
		for tick in range(18):sim._advance_traversal(runner) if runner.has("traversal") else null
		check(runner["pos"]==last and not runner.has("traversal"),kind+" timed landing completes")
	# Landing is not allowed to overlap a stationary actor.
	var blocker: Dictionary=sim._players[0];blocker["alive"]=true;blocker["pos"]=last
	runner["pos"]=first;runner["path"]=[last]
	runner["traversal"]={"start":first,"finish":last,"elapsed":0.5,"seconds":.5,"kind":"drop"}
	sim._advance_traversal(runner)
	check(runner["pos"]==first and runner.has("traversal"),"occupied gate landing cannot overlap teammate")
