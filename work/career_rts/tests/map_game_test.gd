extends SceneTree

const MapModel = preload("res://scripts/map_model.gd")
var _checks := 0
var _failures: Array[String] = []
var _route_fingerprints: Array[String] = []

func check(condition: bool, label: String) -> void:
	_checks+=1
	if not condition:_failures.append(label);push_error(label)

func test_route(nav, start: Vector2, finish: Vector2, side: String, label: String) -> void:
	var path: Array[Vector2]=nav.find_path(start,finish,3.5,side)
	_route_fingerprints.append(label+":"+str(path))
	check(not path.is_empty(),label+" reachable")
	var previous := start
	for point in path:
		check(nav.is_walkable(point,3.5),label+" waypoint has circle clearance")
		check(not nav.segment_blocked(previous,point,3.5),label+" segment cannot cross a wall or foreign NAV portal")
		previous=point
	if not path.is_empty():check(path[-1].distance_to(finish)<.1,label+" reaches exact destination")

func _initialize() -> void:
	var began := Time.get_ticks_msec()
	var decoded = JSON.parse_string(FileAccess.get_file_as_string("res://data/dust2_game.json"))
	check(decoded is Dictionary,"derived map JSON exists")
	if not decoded is Dictionary:quit(1);return
	var source: Dictionary=decoded
	var nav = MapModel.new()
	nav.setup(source)
	check(nav.bounds==Rect2(0,0,1024,1024),"real radar extent is 1024 square")
	check(source["nav_polygons"].size()==2242,"floor polygons derive from actual source NAV")
	check(source["source"]["atlas_sha256"].length()==64,"source hash preserved without source atlas")
	check(source["statistics"]["source_directed_links"]==6275,"source directional portal count retained")
	check(source["statistics"]["walk_cells"]>18000,"actual occupancy replaces rectangle schematic")
	for point in [Vector2(0,0),Vector2(512,512),Vector2(1024,1024)]:
		check(nav.world_to_pixel(nav.pixel_to_world(point)).distance_to(point)<.001,"overview world/pixel round trip")
	var report: Dictionary=nav.validation_report(3.5)
	check(report["invalid_spawns"].is_empty(),"all ten spawns have actor clearance")
	check(report["invalid_targets"].is_empty(),"all seven tactical destinations have actor clearance")
	var targets: Dictionary=source["tactical_targets"]
	for side in ["t","ct"]:
		var spawns: Array=source["spawns"][side]
		check(spawns.size()==5,side+" has five spawn-region points")
		for index in range(spawns.size()):
			var spawn := nav.vec(spawns[index])
			check(nav.region_at(spawn)==("TSpawn" if side=="t" else "CTSpawn"),side+" spawn comes from actual NAV region")
			for other in range(index+1,spawns.size()):
				check(spawn.distance_to(nav.vec(spawns[other]))>=11.99,side+" spawns are separated")
			for name in targets:
				test_route(nav,spawn,nav.vec(targets[name]),side,side+str(index)+"->"+str(name))
	var t_spawn := nav.vec(source["spawns"]["t"][0])
	var ct_spawn := nav.vec(source["spawns"]["ct"][0])
	for itinerary in [["A_long","A_site"],["A_short","A_site"],["B_tunnel","B_site"]]:
		var entrance := nav.vec(targets[itinerary[0]])
		var goal := nav.vec(targets[itinerary[1]])
		test_route(nav,t_spawn,entrance,"t","T common route entrance "+str(itinerary[0]))
		test_route(nav,entrance,goal,"t","T common route finish "+str(itinerary[1]))
	var long_previous := t_spawn
	for entrance_id in ["region_OutsideLong","region_LongDoors","A_long","A_site"]:
		var entrance: Vector2=nav.waypoint_positions[entrance_id]
		check(nav.region_at(entrance)==nav.waypoint_regions[entrance_id],"long ingress uses its actual source region "+entrance_id)
		test_route(nav,long_previous,entrance,"t","T true long ingress "+entrance_id)
		long_previous=entrance
	# Runtime actors and clicks are not restricted to four-pixel cell centres.
	for offset in [Vector2(.85,.65),Vector2(-.7,.9),Vector2(.9,-.8)]:
		var arbitrary_start: Vector2=nav.nearest_walkable(t_spawn+offset,3.5)
		var arbitrary_finish: Vector2=nav.nearest_walkable(nav.vec(targets["A_site"])-offset,3.5)
		test_route(nav,arbitrary_start,arbitrary_finish,"t","non-cell-centre endpoints "+str(offset))
	for name in ["A_site","B_site"]:test_route(nav,ct_spawn,nav.vec(targets[name]),"ct","CT retake "+name)
	check(nav.segment_blocked(nav.vec(targets["A_site"]),nav.vec(targets["B_site"])),"solid geometry blocks A/B cross-map sight")
	check(nav.segment_blocked(t_spawn,Vector2.ZERO,3.5),"swept circle cannot cross map boundary")
	var constrained: Vector2=nav.constrain_motion(t_spawn,Vector2.ZERO,3.5)
	check(nav.is_walkable(constrained,3.5),"constrained motion remains on valid floor")
	check(constrained.distance_to(Vector2.ZERO)>10,"long motion cannot tunnel through a wall")
	var snapped: Vector2=nav.nearest_walkable(Vector2.ZERO,3.5)
	check(snapped.is_finite() and nav.is_walkable(snapped,3.5),"off-floor click snaps to a valid actor location")
	var ray: Vector2=nav.ray_end(t_spawn,Vector2.ZERO)
	check(not nav.segment_blocked(t_spawn,ray),"visibility ray stops before the first blocked pixel")
	var fan: PackedVector2Array=nav.visibility_fan(t_spawn,Vector2.UP,deg_to_rad(50),240,60)
	check(fan.size()==62,"visibility fan is bounded to requested rays")
	for point in fan:check(point.is_finite(),"visibility fan coordinates finite")
	var knowledge = JSON.parse_string(FileAccess.get_file_as_string("res://data/botlab_knowledge.json"))
	if knowledge is Dictionary:nav.apply_knowledge(knowledge)
	var watch: Vector2=nav.preferred_watch(ct_spawn,"ct","awp")
	check(watch.is_finite() and not nav.segment_blocked(ct_spawn,watch),"watch preference never aims through a blocked footprint")
	check(nav.knowledge_usage()["source_regions"]>10,"Bot Lab semantic regions map to actual NAV regions")
	var cold_start_ms := Time.get_ticks_msec()
	nav.find_path(t_spawn,nav.vec(targets["A_site"]),3.5,"t")
	var cold_ms := Time.get_ticks_msec()-cold_start_ms
	var start_ms := Time.get_ticks_msec()
	for _index in range(200):nav.find_path(t_spawn,nav.vec(targets["A_site"]),3.5,"t")
	var cache_ms := Time.get_ticks_msec()-start_ms
	check(cache_ms<2500,"cached repeated paths complete within bounded test budget")
	check(nav.knowledge_usage()["cached_paths"]<=256,"route cache has a hard size bound")
	var graph = nav._graph_for(3.5)
	var regions: Array=nav.get("_regions")
	for side in ["", "t", "ct", "unknown"]:
		graph.set_side(side)
		var exact := true
		for from_index in range(regions.size()):
			for to_index in range(regions.size()):
				if graph.pair_factors[from_index*regions.size()+to_index]!=nav.route_cost_factor(str(regions[from_index]),str(regions[to_index]),side):exact=false
		check(exact,"precomputed region-pair factors are exactly equal to original knowledge weights: "+side)
	var paths: Dictionary=nav.get("_paths")
	var fifo: Array=nav.get("_path_fifo")
	var warm_key: String=fifo[-1]
	for index in range(256-paths.size()):nav._cache_path("synthetic_cache_probe_"+str(index),{"path":[],"biased":false})
	check(paths.size()==256 and fifo.size()==256,"FIFO fills to the exact bounded capacity")
	var oldest: String=fifo[0]
	nav._cache_path("synthetic_cache_overflow",{"path":[],"biased":false})
	check(paths.size()==256 and fifo.size()==256,"FIFO evicts one route without shrinking the cache")
	check(not paths.has(oldest) and paths.has(warm_key),"overflow removes only the oldest route and preserves a warmed route")
	print(JSON.stringify({"checks":_checks,"failures":_failures,"elapsed_ms":Time.get_ticks_msec()-began,"route_fingerprint":"\n".join(_route_fingerprints).sha256_text(),"first_path_after_knowledge_ms":cold_ms,"cached_200_paths_ms":cache_ms,"geometry":report,"knowledge":nav.knowledge_usage()}))
	quit(0 if _failures.is_empty() else 1)
