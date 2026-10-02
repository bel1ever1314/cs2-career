extends SceneTree
## Deterministic gameplay regressions; fixtures are memory-only. Production
## navigation is used for the integration portion, never a displayed fake map.
const Sim = preload("res://scripts/match_sim.gd")
var checks := 0
var failures: Array[String] = []
var baseline

class OpenNav extends RefCounted:
	func nearest_walkable(point: Vector2, _radius: float) -> Vector2: return point
	func find_path(_from: Vector2, point: Vector2, _radius: float, _side: String) -> Array: return [point]
	func segment_blocked(_from: Vector2, _to: Vector2, _radius: float) -> bool: return false
	func constrain_motion(_from: Vector2, to: Vector2, _radius: float) -> Vector2: return to
	func knowledge_usage() -> Dictionary: return {}

class WallNav extends OpenNav:
	func segment_blocked(from: Vector2, to: Vector2, _radius: float) -> bool:
		return (from.x < 150.0 and to.x >= 150.0) or (from.x >= 150.0 and to.x < 150.0)

class TrackNav extends RefCounted:
	var inner
	var searches: Array[Dictionary] = []
	func nearest_walkable(point: Vector2, radius: float) -> Vector2:
		return inner.nearest_walkable(point,radius)
	func find_path(from: Vector2, to: Vector2, radius: float, side: String) -> Array:
		searches.append({"from":from,"to":to})
		return inner.find_path(from,to,radius,side)
	func segment_blocked(from: Vector2, to: Vector2, radius: float) -> bool:
		return inner.segment_blocked(from,to,radius)


func _initialize() -> void:
	call_deferred("_run")


func _check(condition: bool, label: String) -> void:
	checks += 1
	if not condition:
		failures.append(label)
		push_error(label)


func _run() -> void:
	var map_data = JSON.parse_string(FileAccess.get_file_as_string("res://data/dust2_game.json"))
	var rosters = JSON.parse_string(FileAccess.get_file_as_string("res://data/rosters.json"))
	if not map_data is Dictionary or not rosters is Dictionary:
		_check(false, "actual map and static roster JSON are present")
		_finish()
		return
	baseline = Sim.new()
	_check(baseline.configure(map_data, rosters, 77), "actual atlas map configures")
	_check(baseline.snapshot()["players"].size() == 10, "ten unique players")
	_check(baseline.human_id == "spirit_donk", "public human identity")
	_check(baseline.get_map_model() != null, "renderer shares the map model")
	for p in baseline.snapshot()["players"]:
		_check(baseline.get_map_model().is_walkable(p["pos"], Sim.PLAYER_RADIUS), "real spawn is walkable: " + p["id"])
		_check(p["weapon"] in Sim.WEAPONS and p["money"] >= 0, "affordable role loadout: " + p["id"])
	_test_controls()
	_test_weapons()
	_test_input_time()
	_test_commands_takeover()
	_test_utilities()
	_test_objectives()
	_test_ledger_match()
	_test_cached_routes()
	_test_actual_map()
	_finish()


func _fixture(seed: int = 77):
	var sim = Sim.new()
	sim._map = baseline._map.duplicate(true)
	sim._nav = OpenNav.new()
	sim._players = baseline._players.duplicate(true)
	sim._ids = baseline._ids.duplicate(true)
	sim._human_id = baseline.human_id
	sim._human_team = "t"
	sim._bomb = baseline._bomb.duplicate(true)
	sim._phase = "live"
	sim._round = 1
	sim._rng.seed = seed
	for index in range(sim._players.size()):
		var p: Dictionary = sim._players[index]
		p["pos"] = Vector2(5000.0 + index * 1200.0, 5000.0)
		p["goal"] = p["pos"]
		p["aim"] = Vector2(p["pos"]) + Vector2.RIGHT * 20.0
		p["path"] = []
		p["task"] = "hold"
		p["order"] = "hold"
		p["smokes"] = 0
		p["flashes"] = 0
	var human: Dictionary = sim._players[sim._ids[sim.human_id]]
	human["pos"] = Vector2(100, 100)
	human["goal"] = human["pos"]
	human["aim"] = Vector2(200, 100)
	return sim


func _human(sim) -> Dictionary:
	return sim._players[sim._ids[sim.human_id]]


func _equip(p: Dictionary, weapon: String) -> void:
	p["weapon"] = weapon
	p["primary_weapon"] = weapon if weapon != "pistol" else "ak"
	p["ammo"] = int(Sim.WEAPONS[weapon]["magazine"])
	p["reserve"] = int(Sim.WEAPONS[weapon]["reserve"])
	p["inventory"] = {weapon: {"ammo": p["ammo"], "reserve": p["reserve"]}, "pistol": {"ammo": 20, "reserve": 60}}
	p["cooldown"] = 0.0
	p["reloading"] = 0.0
	p["reload_pending"] = false


func _test_controls() -> void:
	var run = _fixture()
	run.step(1.0, {"move": Vector2.RIGHT, "aim": Vector2(300, 100)})
	_check(absf(_human(run)["pos"].x - 154.0) < 0.001, "run speed is 54 radar pixels per second")
	_check(absf(_human(run)["yaw"]) < 0.001, "mouse controls yaw")
	var walk = _fixture()
	walk.step(1.0, {"move": Vector2.RIGHT, "walk": true})
	_check(absf(_human(walk)["pos"].x - 128.08) < 0.001, "shift walk is slower")
	_check(_human(walk)["walking"], "walking exposed in snapshot")
	var diagonal = _fixture()
	diagonal.step(1.0, {"move": Vector2(1, 1)})
	_check(absf(Vector2(_human(diagonal)["pos"]).distance_to(Vector2(100,100)) - 54.0) < 0.001, "diagonal does not exceed run speed")
	var invalid = _fixture()
	invalid.step(NAN, {"fire": true})
	invalid.step(-1.0, {"fire": true})
	_check(invalid.snapshot()["tick"] == 0, "invalid delta never advances simulation")
	invalid.step(Sim.FIXED_DT, {"move": Vector2.INF, "aim": Vector2.INF})
	_check(_human(invalid)["pos"].is_finite() and is_finite(float(_human(invalid)["yaw"])), "invalid input cannot poison actor coordinates")
	var freeze = _fixture()
	freeze._phase = "freeze"
	freeze._phase_time = 2.0
	freeze.step(0.1,{"weapon":"pistol","move":Vector2.RIGHT,"fire":true})
	_check(_human(freeze)["weapon"] == "pistol" and _human(freeze)["pos"] == Vector2(100,100) and _human(freeze)["shots"] == 0,"freeze accepts equipment choice but no movement or fire")
	var traffic = _fixture()
	var walker := _human(traffic)
	var blocker: Dictionary = traffic._players[5]
	blocker["pos"] = Vector2(110,100)
	traffic.step(1.0, {"move":Vector2.RIGHT})
	_check(Vector2(walker["pos"]).distance_to(blocker["pos"]) >= Sim.PLAYER_RADIUS*2.0-0.03, "body steering never overlaps a blocking teammate")
	_check(Vector2(walker["pos"]).distance_to(Vector2(100,100)) <= Sim.MOVE_SPEED+0.01, "body steering never increases movement budget")


func _test_weapons() -> void:
	for weapon in ["ak", "m4", "awp", "pistol"]:
		var sim = _fixture(5)
		var p := _human(sim)
		_equip(p, weapon)
		sim.step(1.0, {"fire": true, "aim": Vector2(300,100)})
		_check(p["shots"] >= floori(float(Sim.WEAPONS[weapon]["rate"])) and p["shots"] <= ceili(float(Sim.WEAPONS[weapon]["rate"])) + 1, "weapon-specific rate: " + weapon)
		_check(p["ammo"] == int(Sim.WEAPONS[weapon]["magazine"]) - int(p["shots"]), "one bullet per recorded shot: " + weapon)
		var shots := sim.pop_events().filter(func(event): return event["type"] == "shot")
		_check(not shots.is_empty() and shots[0]["weapon"] == weapon, "weapon in shot event: " + weapon)
		p["ammo"] = 0
		p["reserve"] = 3
		sim.step(float(Sim.WEAPONS[weapon]["reload"]) + 0.1, {"reload": true})
		_check(p["ammo"] == 3 and p["reserve"] == 0, "reload transfers only finite reserve: " + weapon)
		sim._reload(p)
		_check(not p["reload_pending"], "empty reserve cannot create ammo: " + weapon)
	var wall = _fixture()
	wall._nav = WallNav.new()
	var victim: Dictionary = wall._players[0]
	victim["pos"] = Vector2(200,100)
	victim["goal"] = victim["pos"]
	wall.step(1.0, {"fire": true, "aim": victim["pos"]})
	_check(victim["hp"] == 100 and _human(wall)["damage"] == 0, "wall shots cannot damage or inflate ledger")
	for event in wall.pop_events():
		if event["type"] == "shot" and event["id"] == wall.human_id:
			_check(event["to"].x <= 150.01, "bullet ray terminates before wall")
	var switcher = _fixture()
	var actor := _human(switcher)
	actor["ammo"] = 5
	switcher.step(0.4, {"weapon": "pistol"})
	_check(actor["weapon"] == "pistol" and actor["ammo"] == 20, "secondary pistol is available")
	switcher.step(0.4, {"weapon": "primary"})
	_check(actor["weapon"] == "ak" and actor["ammo"] == 5, "switch does not refill primary")
	var low := actor.duplicate(true)
	low["skills"]["reaction"] = 0.0
	var high := actor.duplicate(true)
	high["skills"]["reaction"] = 100.0
	_check(switcher.reaction_seconds(high) < switcher.reaction_seconds(low), "reaction property changes first-shot latency")
	var reaction = _fixture()
	var shooter: Dictionary = reaction._players[0]
	shooter["pos"] = Vector2(130,100)
	shooter["yaw"] = PI
	shooter["flashes"] = 0
	reaction.step(0.1)
	_check(shooter["shots"] == 0, "AI does not instant-fire on acquiring a target")
	reaction.step(0.7)
	_check(shooter["shots"] > 0, "AI fires after reaction and aim alignment")


func _test_input_time() -> void:
	var late = _fixture()
	late.step(11.0, {}) # one second remains behind the bounded 600-tick call
	_check(late.snapshot()["tick"] == 600, "catch-up per call is bounded")
	late.step(0.0, {"fire": true, "aim": Vector2(200,100)})
	_check(_human(late)["shots"] == 0, "late zero-time click never reshoots old backlog")
	late.step(Sim.FIXED_DT, {"fire": true, "aim": Vector2(200,100)})
	_check(_human(late)["shots"] == 1, "new click applies only to its own time interval")
	var edge = _fixture()
	_human(edge)["smokes"] = 3
	edge.step(4.0, {"smoke": true, "aim": Vector2(150,100)})
	_check(_human(edge)["smokes"] == 2, "one-shot grenade input is not replayed across catch-up ticks")
	var fine = _fixture()
	var coarse = _fixture()
	for _index in range(120): fine.step(1.0/120.0, {"fire": true})
	for _index in range(4): coarse.step(0.25, {"fire": true})
	_check(fine.snapshot()["tick"] == coarse.snapshot()["tick"] and _human(fine)["shots"] == _human(coarse)["shots"], "fixed ticks are frame-rate independent")


func _test_commands_takeover() -> void:
	var sim = _fixture()
	var target: Dictionary = sim._players[sim._ids["spirit_zont1x"]]
	_check(sim.command_move("t", Vector2(250,250), [target["id"]]), "right-click selected teammate command")
	_check(target["task"] == "move" and target["goal"] == Vector2(250,250), "selected actor receives exact move goal")
	_check(not sim.command_move("t", Vector2.INF), "nonfinite command rejected")
	_check(not sim.command("t", "unknown"), "unknown tactical command rejected")
	_check(sim.command("t", "attack_b", [target["id"]]), "legacy command is preserved")
	_check(not sim.select_human("vitality_zywoo"), "takeover cannot steal enemy")
	target["alive"] = false
	_check(not sim.select_human(target["id"]), "takeover cannot control dead teammate")
	target["alive"] = true
	_check(sim.select_human(target["id"]) and sim.human_id == target["id"], "alive teammate takeover succeeds")
	_check(sim._players.filter(func(p): return p["human"]).size() == 1, "exactly one controlled actor")
	var human_goal: Vector2 = target["goal"]
	_check(sim.command_move("t", Vector2(350,350)), "empty move selection commands AI team")
	_check(target["goal"] == human_goal, "empty move selection excludes human WASD actor")
	var stale = _fixture()
	stale.step(11.0, {"move": Vector2.RIGHT})
	stale.select_human("spirit_zont1x")
	var start: Vector2 = _human(stale)["pos"]
	stale.step(0.0)
	_check(_human(stale)["pos"] == start, "queued previous actor's movement does not apply after takeover")
	var partial = _fixture()
	_human(partial)["ammo"] = 5
	partial.step(Sim.FIXED_DT/2.0,{"reload":true})
	partial.select_human("spirit_zont1x")
	_human(partial)["ammo"] = 5
	partial.step(Sim.FIXED_DT/2.0,{})
	_check(not _human(partial)["reload_pending"],"partial old-actor input edge cannot reload new actor")


func _test_utilities() -> void:
	var smoke = _fixture()
	_human(smoke)["smokes"] = 1
	smoke.step(0.7, {"smoke": true, "aim": Vector2(150,100)})
	_check(smoke.snapshot()["utilities"].size() == 1, "smoke appears in public snapshot")
	_check(smoke.vision_blocked(Vector2(100,100), Vector2(200,100)), "deployed smoke blocks vision")
	var utility: Dictionary = smoke.snapshot()["utilities"][0]
	_check(utility["state"] == "active" and utility["radius"] == Sim.SMOKE_RADIUS and utility["pos"].is_finite(), "renderer utility position/radius/state contract")
	smoke.step(10.0)
	smoke.step(9.0)
	_check(smoke.snapshot()["utilities"].is_empty(), "smoke has a finite lifetime")
	var flash = _fixture()
	_human(flash)["flashes"] = 1
	var opponent: Dictionary = flash._players[0]
	opponent["pos"] = Vector2(140,100)
	opponent["goal"] = opponent["pos"]
	opponent["yaw"] = PI
	opponent["ammo"] = 0
	opponent["reserve"] = 0
	flash.step(0.7, {"flash": true, "aim": Vector2(130,100)})
	_check(float(opponent["flash_remaining"]) > 0.0, "facing flash blinds a visible actor")
	_check(not flash.pop_events().filter(func(event): return event["type"] == "flash").is_empty(), "flash event is public")
	var wall = _fixture()
	wall._nav = WallNav.new()
	var hidden: Dictionary = wall._players[0]
	hidden["pos"] = Vector2(200,100)
	wall._detonate_flash({"pos": Vector2(140,100), "owner_id": wall.human_id})
	_check(hidden["flash_remaining"] == 0.0, "wall blocks flash effect")


func _test_objectives() -> void:
	var plant = _fixture()
	var actor := _human(plant)
	actor["pos"] = plant._vector(plant._map["sites"]["A"]["center"])
	plant._bomb["carrier_id"] = actor["id"]
	plant.step(3.0, {"interact": true})
	_check(plant._bomb["state"] == "planted" and absf(float(plant._bomb["remaining"]) - 40.0) < 0.001, "E plants after three seconds, full 40-second timer")
	_check(actor["plants"] == 1, "actual plant recorded once")
	var cancel = _fixture()
	_human(cancel)["pos"] = cancel._vector(cancel._map["sites"]["A"]["center"])
	cancel.step(1.0, {"interact": true})
	cancel.step(Sim.FIXED_DT, {"move": Vector2.RIGHT, "interact": true})
	_check(cancel._bomb["progress"] == 0.0 and cancel._bomb["state"] == "carried", "movement cancels plant instead of completing off-site")
	var post = _fixture()
	post._bomb.merge({"state": "planted", "site": "A", "pos": Vector2(300,300)}, true)
	var kit: Dictionary = post._players[0]
	var cover: Dictionary = post._players[2]
	kit["task"] = "default"
	kit["pos"] = Vector2(330,300)
	cover["task"] = "default"
	cover["pos"] = Vector2(325,300)
	var guard: Dictionary = post._players[5]
	guard["task"] = "default"
	guard["route_via"] = "B_door"
	guard["route_via_pos"] = post._target("B_door")
	var interactions: Array[Dictionary] = []
	post._postplant(kit, interactions)
	post._postplant(cover, interactions)
	post._postplant(guard, interactions)
	_check(kit["task"] == "defuse" and kit["goal"] == Vector2(300,300), "designated kit CT moves to bomb")
	_check(cover["task"] == "cover defuser" and cover["goal"].distance_to(Vector2(300,300)) > 8.0, "other CT covers rather than stacking on bomb")
	_check(guard["task"] == "guard bomb" and guard["goal"].distance_to(Vector2(300,300)) > 8.0, "T adopts purposeful postplant guard")
	var cancels := post.pop_events().filter(func(event): return event["type"] == "route_via_cancelled" and event["id"] == guard["id"])
	_check(cancels.size() == 1 and cancels[0]["via"] == "B_door" and cancels[0]["reason"] == "bomb_planted" and cancels[0]["bomb_state"] == "planted" and cancels[0]["task"] == "guard bomb", "real planted state explicitly audits unfinished via cancellation rather than arrival")
	kit["pos"] = Vector2(320,300)
	interactions.clear()
	post._postplant(kit, interactions)
	_check(interactions.has(kit) and kit["interacting"], "AI defuses within actual 23-pixel interaction range without stacking at C4")
	kit["pos"] = Vector2(323,300)
	kit["interacting"] = false
	interactions.clear()
	post._postplant(kit, interactions)
	_check(interactions.is_empty(), "23-pixel boundary uses same strict interaction test as actual bomb action")
	kit["alive"] = false
	_check(post._designated_defuser() == cover["id"], "dead defuser is replaced by alive retake teammate")
	var defuse = _fixture()
	defuse._human_id = "vitality_apex"
	defuse._human_team = "ct"
	for p in defuse._players: p["human"] = p["id"] == defuse.human_id
	_human(defuse)["pos"] = Vector2(100,100)
	defuse._bomb.merge({"state": "planted", "site": "A", "pos": Vector2(100,100)}, true)
	defuse.step(1.0)
	_check(defuse._bomb["progress"] == 0.0 and defuse._bomb["state"] == "planted", "controlled human still requires E to defuse")
	defuse.step(5.0, {"interact": true})
	_check(defuse._bomb["state"] == "defused" and _human(defuse)["defuses"] == 1, "E with CT kit defuses in five seconds")
	var explosion = _fixture()
	for p in explosion._players:
		if p["side"] == "t": p["alive"] = false
	explosion._bomb.merge({"state": "planted", "site": "B", "pos": Vector2(100,100), "remaining": 0.5}, true)
	explosion.step(0.6)
	_check(explosion._score["t"] == 1 and explosion._bomb["state"] == "exploded", "dead T team can win by planted bomb, not instant CT elimination win")


func _test_ledger_match() -> void:
	var sim = _fixture()
	var killer := _human(sim)
	var assister: Dictionary = sim._players[5]
	var victim: Dictionary = sim._players[0]
	victim["damagers"] = {killer["id"]: 60, assister["id"]: 40}
	killer["damage"] = 60
	killer["round_damage"] = 60
	assister["damage"] = 40
	assister["round_damage"] = 40
	sim._kill(killer, victim)
	sim._kill(killer, victim)
	_check(killer["k"] == 1 and victim["d"] == 1 and assister["a"] == 1, "kill death assist ledger does not duplicate a dead victim")
	sim._end_round("t", "ledger fixture")
	var snapshot: Dictionary = sim.snapshot(true)
	_check(snapshot["round_history"].size() == 1 and snapshot["score"]["t"] == 1, "one round result is stored once")
	_check(snapshot["players"][sim._ids[killer["id"]]]["adr"] == 60.0, "ADR uses actual damage and completed rounds")
	_check(snapshot["round_history"][0]["players"].size() == 10, "history preserves all roster statistics")
	for p in snapshot["players"]: _check(p["money"] >= 0 and p["money"] <= 16000, "economy remains within bounds")
	var half = _fixture()
	half._round = 12
	half._score = {"ct": 6, "t": 5}
	half._end_round("t", "half fixture")
	half.step(2.0)
	_check(half._round == 13 and half._team_sides == {"ct": "t", "t": "ct"}, "MR12 swaps sides at round thirteen")
	_check(_human(half)["team"] == "t" and _human(half)["side"] == "ct", "takeover identity remains permanent team after halftime")
	var finish = _fixture()
	finish._round = 24
	finish._score = {"ct": 11, "t": 12}
	finish._end_round("ct", "draw fixture")
	finish.step(2.0)
	_check(finish.snapshot()["finished"] and finish.report()["winner"] == "draw", "24 rounds can finish 12:12 without hidden overtime")
	var win = _fixture()
	win._score = {"ct": 12, "t": 2}
	win._end_round("ct", "win fixture")
	win.step(2.0)
	_check(win.snapshot()["finished"] and win.report()["winner"] == "ct", "first thirteen round wins ends MR12 match")


func _test_actual_map() -> void:
	baseline.set_human_control(false)
	baseline.pop_events()
	baseline.step(10.0)
	baseline.step(10.0)
	var state: Dictionary = baseline.snapshot()
	_check(state["tick"] == 1200, "real atlas simulation advances twenty seconds")
	var damage := 0
	for p in state["players"]:
		_check(p["pos"].is_finite() and baseline.get_map_model().is_walkable(p["pos"], Sim.PLAYER_RADIUS), "real-path actor stays walkable: " + p["id"])
		_check(p["ammo"] >= 0 and p["reserve"] >= 0, "real-path ammunition is finite: " + p["id"])
		damage += int(p["damage"])
	for event in baseline.pop_events():
		if event["type"] == "shot" and event["hit"]:
			_check(not baseline.get_map_model().segment_blocked(event["from"], event["to"], 0.0), "real hit has clear wall LOS")
	_check(damage >= 0, "actual map ledger is nonnegative")


func _test_cached_routes() -> void:
	var key := "t|split_a|4"
	var plan_size: int = baseline._opening_plans[key]["path"].size()
	var actor := _human(baseline)
	var original: Array = actor["path"].duplicate(true)
	actor["path"].clear()
	_check(baseline._opening_plans[key]["path"].size() == plan_size,"live path consumption cannot mutate immutable opening template")
	actor["path"] = original
	for start_key in ["CT_connector","A_site","B_site","A_short","B_tunnel","A_long"]:
		var start: Vector2 = baseline._target(start_key)
		for goal_key in ["A_site","B_site"]:
			var goal: Vector2 = baseline._target(goal_key)
			var path: Array = baseline._route_path(start,goal,"ct")
			_check(not path.is_empty(),"cached objective corridor exists: "+start_key+" "+goal_key)
			var previous := start
			for point in path:
				_check(not baseline.get_map_model().segment_blocked(previous,point,Sim.PLAYER_RADIUS),"reused corridor preserves radius and directed portal")
				previous = point
			_check(previous.distance_to(goal) < 0.1,"cached corridor ends at requested objective, not stale goal")
	var original_nav = baseline._nav
	var tracking := TrackNav.new()
	tracking.inner = original_nav
	baseline._nav = tracking
	var start := Vector2(838.0,134.0)
	var goal := Vector2(204.0345,135.6019)
	var retake: Array = baseline._route_path(start,goal,"ct")
	_check(not retake.is_empty(),"dynamic B guard uses known static approach plus final site path")
	for search in tracking.searches:
		_check(Vector2(search["from"]).distance_to(baseline._target("B_site")) < 0.1,"dynamic B tail search starts at local static site, not far A actor")
	var previous := start
	for point in retake:
		_check(not original_nav.segment_blocked(previous,point,Sim.PLAYER_RADIUS),"dynamic B retake tail preserves wall radius and directed portals")
		previous = point
	_check(previous.distance_to(goal)<0.1,"dynamic B retake ends at actual guard point")
	baseline._nav = original_nav


func _finish() -> void:
	print(JSON.stringify({"suite": "sim_game", "checks": checks, "failures": failures}))
	quit(0 if failures.is_empty() else 1)
