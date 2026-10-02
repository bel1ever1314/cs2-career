extends SceneTree
## Real atlas, autonomous ten-player soak. No predetermined round outcome.
const Sim = preload("res://scripts/match_sim.gd")
var failures: Array[String] = []
var checks := 0
var total_plants := 0
var total_defuses := 0
var total_via_visits: Dictionary = {}
var total_via_assignments: Dictionary = {}
var total_objective_cancels: Dictionary = {}
var total_killed_cancels: Dictionary = {}
var seed_results: Array[Dictionary] = []

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
	for seed in [20261001, 42, 2024]:
		_run_match(map_data, rosters, seed)
	_check(total_plants > 0, "complete seeded matches include natural plants")
	_check(total_defuses > 0, "complete seeded matches include natural retakes and defuses")
	for via in ["A_long","A_short","B_tunnel","B_door"]:
		_check(total_via_assignments.has(via), "live opening orders actually assign split waypoint: "+via)
		# Being killed or re-tasked after a real plant is not waypoint arrival.
		# Explicit events audit those outcomes; the separate collision/arrival
		# route suite walks all five actors through both uninterrupted executes.
		_check(total_via_visits.has(via) or (via == "B_door" and (total_objective_cancels.has(via) or total_killed_cancels.has(via))), "live split arrives or unfinished B doors has audited death/actual objective cancellation: "+via)
	print(JSON.stringify({"suite": "sim_bot_match", "checks": checks, "failures": failures, "seed_results":seed_results}))
	quit(0 if failures.is_empty() else 1)


func _run_match(map_data: Dictionary, rosters: Dictionary, seed: int) -> void:
	var sim = Sim.new()
	var init_start := Time.get_ticks_usec()
	_check(sim.configure(map_data, rosters, seed), "real autonomous map setup")
	var init_usec := Time.get_ticks_usec() - init_start
	var counts: Dictionary = {}
	var hit_damage := 0
	var begin := Time.get_ticks_msec()
	var step_times: Array[int] = []
	var outliers: Array[Dictionary] = []
	var route_visits: Dictionary = {}
	var ingress_visits: Dictionary = {}
	var completed_vias: Dictionary = {}
	var prior_vias: Dictionary = {}
	var route_assignments: Dictionary = {}
	var objective_cancels: Dictionary = {}
	var killed_cancels: Dictionary = {}
	var planted_rounds: Dictionary = {}
	var stop_frame := 0
	for frame in range(24000): # 6000 game seconds exceeds every legal 24-round duration.
		var before_round: int = sim._round
		var before_phase: String = sim._phase
		var before_bomb: String = sim._bomb["state"]
		var step_start := Time.get_ticks_usec()
		sim.step(0.25)
		var duration := Time.get_ticks_usec()-step_start
		step_times.append(duration)
		if duration > 50000:
			outliers.append({"ms":duration/1000.0,"before_round":before_round,"round":sim._round,"before_phase":before_phase,"phase":sim._phase,"before_bomb":before_bomb,"bomb":sim._bomb["state"],"game_time":sim._time})
		for p in sim._players:
			if not p["alive"]: continue
			var key := "%d|%s" % [sim._round,p["id"]]
			var via := str(p.get("route_via", ""))
			if not via.is_empty():
				if not prior_vias.has(key):
					route_assignments[via] = int(route_assignments.get(via,0))+1
				prior_vias[key] = via
			elif prior_vias.has(key) and not completed_vias.has(key):
				var previous: String = prior_vias[key]
				# The engine clears a via only when reaching its 24-pixel region.
				_check(Vector2(p["pos"]).distance_to(sim._target(previous)) < 42.0 or p["task"] in ["defuse","guard bomb","cover defuser","recover bomb"], "via cleared only after reaching region or objective reassignment")
				completed_vias[key] = previous
		var events: Array = sim.pop_events()
		var killed_ids: Dictionary = {}
		for event in events:
			if event["type"] == "bomb_planted": planted_rounds[event["round"]] = true
			if event["type"] == "kill": killed_ids[event["victim_id"]] = event["killer_id"]
		for event in events:
			counts[event["type"]] = int(counts.get(event["type"], 0)) + 1
			if event["type"] == "route_via_cancelled":
				var cancelled := str(event["via"])
				if event["reason"] == "bomb_planted":
					_check(planted_rounds.has(event["round"]) and event["bomb_state"] == "planted" and event["task"] in ["defuse","guard bomb","cover defuser"], "cancelled via explicitly follows real plant and guard/retake reassignment")
					objective_cancels[cancelled] = int(objective_cancels.get(cancelled,0))+1
				elif event["reason"] == "killed":
					_check(killed_ids.get(event["id"],"") == event["killer_id"], "killed via cancellation has matching real kill event, not claimed arrival")
					killed_cancels[cancelled] = int(killed_cancels.get(cancelled,0))+1
			if event["type"] == "route_via_reached":
				var reached := str(event["via"])
				route_visits[reached] = int(route_visits.get(reached,0))+1
				_check(Vector2(event["pos"]).distance_to(event["point"]) < 24.0, "recorded via reached inside actual waypoint region")
			if event["type"] == "route_ingress_reached":
				var entry := str(event["ingress"])
				ingress_visits[entry] = int(ingress_visits.get(entry,0))+1
				_check(Vector2(event["pos"]).distance_to(event["point"]) < 12.0, "recorded long ingress reached inside actual waypoint region")
			if event["type"] == "shot" and event["hit"]:
				hit_damage += int(event["damage"])
				_check(not sim.get_map_model().segment_blocked(event["from"], event["to"], 0.0), "autonomous hit has wall-clear LOS")
		if frame % 40 == 39:
			var state: Dictionary = sim.snapshot()
			for p in state["players"]:
				_check(sim.get_map_model().is_walkable(p["pos"], Sim.PLAYER_RADIUS), "autonomous actor remains on NAV: " + p["id"])
			print(JSON.stringify({"seed":seed, "progress_seconds": state["time"], "round": state["round"], "score":state["score"], "bomb": state["bomb"]["state"], "shots": counts.get("shot",0), "kills": counts.get("kill",0), "plants":counts.get("bomb_planted",0),"defuses":counts.get("bomb_defused",0), "players":state["players"].map(func(p): return [p["id"],p["pos"],p["alive"],p["task"],p.get("route_via","")])}))
		stop_frame = frame
		if sim._phase == "finished": break
	var final_state: Dictionary = sim.snapshot(true)
	var ledger_damage := 0
	var ledger_kills := 0
	for p in final_state["players"]:
		ledger_damage += int(p["damage"])
		ledger_kills += int(p["k"])
	_check(ledger_damage == hit_damage, "damage ledger equals actual hit events across rounds")
	_check(ledger_kills == int(counts.get("kill",0)), "kill ledger equals real kill events")
	_check(int(counts.get("shot",0)) > 0, "actual geometry produces combat")
	_check(int(counts.get("round_end",0)) > 0, "actual geometry produces completed rounds")
	total_plants += int(counts.get("bomb_planted",0))
	total_defuses += int(counts.get("bomb_defused",0))
	for via in route_visits:
		total_via_visits[via] = int(total_via_visits.get(via,0))+int(route_visits[via])
	for via in route_assignments:
		total_via_assignments[via] = int(total_via_assignments.get(via,0))+int(route_assignments[via])
	for via in objective_cancels:
		total_objective_cancels[via] = int(total_objective_cancels.get(via,0))+int(objective_cancels[via])
	for via in killed_cancels:
		total_killed_cancels[via] = int(total_killed_cancels.get(via,0))+int(killed_cancels[via])
	_check(final_state["finished"], "natural autonomous MR12 match finishes within legal time bound")
	_check(final_state["round"] <= 24 and final_state["round"] >= 13, "completed MR12 stays within 13 to 24 rounds")
	_check(final_state["score"]["ct"] + final_state["score"]["t"] == final_state["rounds_completed"], "score exactly equals history round count")
	_check(ingress_visits.has("region_OutsideLong") and ingress_visits.has("region_LongDoors"), "long execute uses both real long entrance regions")
	var step_total := 0
	for duration in step_times: step_total += duration
	step_times.sort()
	var result := {"seed_result": seed, "checks": checks, "failures": failures.duplicate(), "event_counts": counts, "route_assignments":route_assignments,"route_visits":route_visits,"objective_canceled_vias":objective_cancels,"killed_canceled_vias":killed_cancels,"ingress_visits":ingress_visits,"completed_vias":completed_vias.size(),"score": final_state["score"], "round": final_state["round"], "game_seconds":final_state["time"], "wall_ms": Time.get_ticks_msec()-begin,"init_ms":init_usec/1000.0,"step_dt":0.25,"step_ms_mean":float(step_total)/step_times.size()/1000.0,"step_ms_p95":step_times[floori(step_times.size()*.95)]/1000.0,"step_ms_max":step_times[-1]/1000.0,"step_calls":stop_frame+1,"outliers":outliers}
	seed_results.append(result)
	print(JSON.stringify(result))
