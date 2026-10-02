extends SceneTree
const Catalog = preload("res://scripts/map_catalog.gd")
const Sim = preload("res://scripts/match_sim.gd")
var checks := 0
var failures: Array[String] = []
var results: Array[Dictionary] = []

class WallBombNav extends RefCounted:
	func segment_blocked(from: Vector2, to: Vector2, _radius: float) -> bool:
		return (from.x < 150 and to.x >= 150) or (from.x >= 150 and to.x < 150)

func _initialize() -> void:
	call_deferred("_run")

func check(value: bool, label: String) -> void:
	checks += 1
	if not value:
		failures.append(label)
		push_error(label)

func _run() -> void:
	var rosters: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/rosters.json"))
	rosters["human_id"] = ""
	check(Catalog.catalog().get("schema_version", 0) == 2, "versioned catalog")
	check(Catalog.available_maps().size() == 8, "eight maps have verified runtime data")
	for map_id in ["de_nuke", "de_vertigo", "unknown_map"]:
		check(Catalog.load_map(map_id).is_empty(), map_id + " cannot silently alias or use false floor connections")
	for map_id in Catalog.available_maps():
		var map_data := Catalog.load_map(map_id)
		check(map_data.get("map", "") == map_id, map_id + " catalog identity")
		var sim = Sim.new()
		check(sim.configure(map_data, rosters, 20261002), map_id + " simulation starts")
		var nav = sim.get_map_model()
		check(nav.validation_report()["invalid_spawns"].is_empty(), map_id + " ten real-NAV projected spawns")
		check(nav.validation_report()["invalid_targets"].is_empty(), map_id + " NAV tactical targets")
		check(map_data["source"]["nav_sha256"].length() == 64, map_id + " actual NAV hash")
		if map_id != "de_dust2": check(sim._knowledge.is_empty(), map_id + " does not use Dust2 knowledge")
		for side in ["t", "ct"]:
			for index in range(5):
				var spawn: Vector2 = sim._spawn(side, index)
				for site in ["A", "B"]:
					var goal: Vector2 = sim._target(site + "_site")
					var path: Array = nav.find_path(spawn, goal, Sim.PLAYER_RADIUS, side)
					check(not path.is_empty(), map_id + side + str(index) + " reaches " + site)
					var previous := spawn
					for point in path:
						check(not nav.segment_blocked(previous, point, Sim.PLAYER_RADIUS), map_id + " continuous legal directed NAV segment")
						previous = point
		for site in ["A", "B"]:
			var posts: Array = sim.postplant_positions(site)
			check(posts.size() == 5, map_id + site + " five guard positions")
			var watched: Dictionary = {}
			for post in posts: watched[post["watch"]] = true
			check(watched.size() >= 2, map_id + site + " guards watch different actual entrance lanes")
			for index in range(posts.size()):
				var point: Vector2 = posts[index]["position"]
				check(point.distance_to(sim._target(site + "_site")) >= 60, map_id + site + " guard outside cramped bomb circle")
				check(nav.is_walkable(point, Sim.PLAYER_RADIUS), map_id + site + " legal guard point")
				for other in range(index + 1, posts.size()):
					check(point.distance_to(posts[other]["position"]) >= 40, map_id + site + " crossfire spacing")
			var actor: Dictionary = sim._players[5]
			actor["pos"] = sim._target(site + "_site")
			actor["task"] = "default"
			sim._bomb.merge({"state": "planted", "site": site, "pos": actor["pos"]}, true)
			var interactions: Array[Dictionary] = []
			sim._postplant(actor, interactions)
			check(actor["task"] == "guard bomb" and Vector2(actor["goal"]).distance_to(sim._bomb["pos"]) >= 60, map_id + site + " T actually receives distant guard post")
			var kit: Dictionary = sim._players[0]
			kit["pos"] = sim._bomb["pos"]
			kit["task"] = "default"
			sim._postplant(kit, interactions)
			var cover: Dictionary = sim._players[2]
			cover["task"] = "default"
			sim._postplant(cover, interactions)
			check(cover["task"] == "cover defuser" and Vector2(cover["goal"]).distance_to(sim._bomb["pos"]) >= 60, map_id + site + " CT cover watches an entrance")
			check(sim._site_at(sim._target(site + "_site")) == site, map_id + " actual site identity " + site)
		# A single actor physically traverses the full map, then performs a real
		# plant interaction. Navigation legality is checked on every microstep.
		for p in sim._players: p["alive"] = false
		var runner: Dictionary = sim._players[5]
		runner["alive"] = true
		runner["side"] = "t"
		runner["pos"] = sim._spawn("t", 0)
		sim._set_goal(runner, sim._target("A_site"), "move")
		for tick in range(3600):
			var previous: Vector2 = runner["pos"]
			sim._tick += 1; sim._time += Sim.FIXED_DT
			sim._follow_path(runner)
			check(not nav.segment_blocked(previous, runner["pos"], Sim.PLAYER_RADIUS), map_id + " actor transit stays legal")
			if Vector2(runner["pos"]).distance_to(runner["goal"]) < 1: break
		check(Vector2(runner["pos"]).distance_to(runner["goal"]) < 1, map_id + " actual transit arrives at A")
		sim._phase = "live"
		sim._bomb.merge({"state": "carried", "carrier_id": runner["id"], "progress": 0.0, "actor_id": "", "action": "", "pos": runner["pos"]}, true)
		runner["moving"] = false
		for tick in range(180): sim._update_bomb([runner])
		check(sim._bomb["state"] == "planted" and runner["plants"] == 1, map_id + " actual NAV point accepts plant")
		# Record a real simulated round and validate the strict report interface.
		sim._end_round("t", "test actual planted objective")
		var report: Dictionary = sim.report()
		check(report["schema_version"] == 2 and report["map"] == map_id and report["seed"] == 20261002, map_id + " versioned raw report")
		check(report["round_history"].size() == 1 and report["round_history"][0]["players"].size() == 10, map_id + " raw round contains ten players")
		results.append({"map": map_id, "source_areas": map_data["statistics"]["source_nav_areas"], "guard_positions": sim.postplant_positions("A").size() + sim.postplant_positions("B").size()})
		print("MULTIMAP_PASS " + map_id)
	_test_defuse_wall(rosters)
	_test_overtime(rosters)
	print("MULTIMAP_RESULT " + JSON.stringify({"checks": checks, "failures": failures, "maps": results}))
	quit(0 if failures.is_empty() else 1)

func _test_defuse_wall(rosters: Dictionary) -> void:
	# Memory-only boundary fixture; actual per-map transit is tested above.
	var sim = Sim.new()
	sim.configure(Catalog.load_map("de_dust2"), rosters, 38)
	sim._nav = WallBombNav.new()
	var kit: Dictionary = sim._players[0]
	kit["pos"] = Vector2(140, 100)
	kit["task"] = "defuse"
	kit["moving"] = false
	sim._bomb.merge({"state": "planted", "site": "A", "pos": Vector2(160, 100), "progress": 0.0}, true)
	var interactions: Array[Dictionary] = []
	sim._postplant(kit, interactions)
	check(not interactions.has(kit), "AI cannot defuse through a wall despite 23px proximity")
	sim._update_bomb([kit])
	check(sim._bomb["progress"] == 0, "E cannot defuse through the same wall")

func _test_overtime(rosters: Dictionary) -> void:
	var sim = Sim.new()
	sim.configure(Catalog.load_map("de_dust2"), rosters, 37, {}, true)
	sim._round = 24; sim._score = {"ct": 12, "t": 12}
	check(not sim._match_decided(), "formal 12:12 begins MR3")
	sim._begin_round()
	check(sim._round == 25 and sim.snapshot()["rules"]["overtime"], "first overtime round")
	var sides: Dictionary = sim._team_sides.duplicate()
	sim._round = 27; sim._begin_round()
	check(sim._team_sides["ct"] != sides["ct"], "MR3 side swap after three rounds")
	sim._round = 30; sim._score = {"ct": 15, "t": 15}
	check(not sim._match_decided(), "15:15 begins another MR3 block")
	sim._score = {"ct": 16, "t": 14}
	check(sim._match_decided(), "16:14 settles first MR3 block")
	sim._round = 35; sim._score = {"ct": 18, "t": 17}
	check(not sim._match_decided(), "second block requires nineteen")
	sim._score = {"ct": 19, "t": 16}
	check(sim._match_decided(), "19:16 settles second MR3 block")
