extends SceneTree
## Diagnostic only: time routing/watch separately without changing simulation.
const Sim = preload("res://scripts/match_sim.gd")

class ProfileSim extends Sim:
	var timings: Dictionary = {}
	var slow_calls: Array[Dictionary] = []

	func record(method: String, started: int) -> int:
		var elapsed := Time.get_ticks_usec() - started
		var row: Dictionary = timings.get(method, {"calls":0,"total_us":0,"max_us":0})
		row["calls"] += 1
		row["total_us"] += elapsed
		row["max_us"] = maxi(int(row["max_us"]), elapsed)
		timings[method] = row
		if elapsed > 20000:
			slow_calls.append({"method":method,"ms":elapsed/1000.0,"time":_time,"round":_round,"bomb":_bomb.get("state","")})
		return elapsed

	func _route_path(from: Vector2, to: Vector2, side: String) -> Array:
		var started := Time.get_ticks_usec()
		var result: Array = super._route_path(from,to,side)
		var elapsed := record("route_path",started)
		if elapsed > 20000:
			slow_calls[-1].merge({"from":from,"to":to,"side":side,"nodes":result.size()},true)
		return result

	func _cached_route(from: Vector2, to: Vector2) -> Array:
		var started := Time.get_ticks_usec()
		var result: Array = super._cached_route(from,to)
		record("cached_route",started)
		return result

	func _watch(p: Dictionary) -> void:
		var started := Time.get_ticks_usec()
		super._watch(p)
		record("watch",started)

func _initialize() -> void:
	call_deferred("_run")

func _run() -> void:
	var map_data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/dust2_game.json"))
	var rosters: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/rosters.json"))
	rosters["human_id"] = ""
	var sim := ProfileSim.new()
	if not sim.configure(map_data,rosters,20261001):
		quit(1)
		return
	print(JSON.stringify({"setup_profile":sim.timings}))
	sim.timings.clear()
	sim.slow_calls.clear()
	for _frame in range(1400):
		sim.step(0.25)
		sim.pop_events()
		if sim._phase == "finished": break
	print(JSON.stringify({"suite":"sim_performance","game_seconds":sim._time,"profile":sim.timings,"slow_calls":sim.slow_calls}))
	quit(0)
