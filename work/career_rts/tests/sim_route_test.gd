extends SceneTree
## Exact real-NAV group movement, without combat obscuring route progress.
const Sim = preload("res://scripts/match_sim.gd")
var checks := 0
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("_run")

func _check(condition: bool, label: String) -> void:
	checks += 1
	if not condition:
		failures.append(label)
		push_error(label)

func _run() -> void:
	var map_data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/dust2_game.json"))
	var rosters: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/rosters.json"))
	rosters["human_id"] = ""
	var sim = Sim.new()
	_check(sim.configure(map_data,rosters,77),"actual map route setup")
	for order in ["split_a","split_b"]:
		for p in sim._players:
			p["alive"] = p["team"] == "t"
			p["pos"] = sim._spawn(p["side"],p["index"])
			p["yield_until"] = 0.0
		sim.command("t",order)
		for frame in range(7200):
			sim._tick += 1
			sim._time = sim._tick*Sim.FIXED_DT
			for p in sim._players:
				if not p["alive"]: continue
				p["moving"] = false
				sim._follow_path(p)
			if frame % 600 == 599:
				print(JSON.stringify({"route":order,"seconds":(frame+1)*Sim.FIXED_DT,"players":sim._players.filter(func(p): return p["alive"]).map(func(p): return [p["id"],p["pos"],Vector2(p["pos"]).distance_to(p["goal"]),p["path"][0] if not p["path"].is_empty() else "done"])}))
		var actors: Array = sim._players.filter(func(p): return p["alive"])
		var events: Array = sim.pop_events()
		if order == "split_a":
			for p in actors:
				if int(p["index"]) < 3:
					for ingress in ["region_OutsideLong","region_LongDoors"]:
						_check(events.any(func(event): return event["type"] == "route_ingress_reached" and event["id"] == p["id"] and event["ingress"] == ingress),"long actor visits real entrance: "+p["id"]+" "+ingress)
		for p in actors:
			_check(Vector2(p["pos"]).distance_to(p["goal"]) < 8.0,"squad reaches real route goal: "+order+" "+p["id"])
			_check(sim.get_map_model().is_walkable(p["pos"],Sim.PLAYER_RADIUS),"squad remains walkable: "+p["id"])
			for other in actors:
				if other["id"] == p["id"]: continue
				_check(Vector2(p["pos"]).distance_to(other["pos"]) >= Sim.PLAYER_RADIUS*2.0-0.03,"squad bodies never finish overlapped")
	print(JSON.stringify({"suite":"sim_route","checks":checks,"failures":failures}))
	quit(0 if failures.is_empty() else 1)
