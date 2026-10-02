extends RefCounted
## Independent fixed-tick top-down singleplayer, not a CS2 replay/controller.
## No career state, files, networking, predetermined winner or hidden shots.

const MapModel = preload("res://scripts/map_model.gd")
const FIXED_DT := 1.0 / 60.0
const MOVE_SPEED := 54.0
const WALK_FACTOR := 0.52
const PLAYER_RADIUS := 3.5
const FIRE_RANGE := 900.0
const WEAPONS := {
	"ak": {"name": "AK-47", "magazine": 30, "reserve": 90, "rate": 10.0, "reload": 2.5, "damage": 36, "range": 700.0, "accuracy": 0.94, "moving_accuracy": 0.42, "price": 2700, "kill_reward": 300},
	"m4": {"name": "M4A4", "magazine": 30, "reserve": 90, "rate": 11.0, "reload": 2.6, "damage": 32, "range": 650.0, "accuracy": 0.96, "moving_accuracy": 0.48, "price": 3100, "kill_reward": 300},
	"awp": {"name": "AWP", "magazine": 5, "reserve": 30, "rate": 0.67, "reload": 3.2, "damage": 115, "range": 900.0, "accuracy": 0.99, "moving_accuracy": 0.08, "price": 4750, "kill_reward": 100},
	"pistol": {"name": "Pistol", "magazine": 20, "reserve": 60, "rate": 4.5, "reload": 1.8, "damage": 24, "range": 420.0, "accuracy": 0.90, "moving_accuracy": 0.70, "price": 0, "kill_reward": 300}}
const SMOKE_RADIUS := 27.0
const SMOKE_SECONDS := 18.0
const FLASH_RADIUS := 105.0
const UTILITY_RANGE := 120.0
const ROUND_SECONDS := 115.0
const BOMB_SECONDS := 40.0
const PLANT_SECONDS := 3.0
const DEFUSE_SECONDS := 10.0
const KIT_SECONDS := 5.0
const FREEZE_SECONDS := 2.0
const RESULT_SECONDS := 2.0
const ORDERS := ["attack_a", "attack_a_long", "attack_a_short", "attack_b", "split_a", "split_b", "hold", "retake_a", "retake_b", "save", "default"]

var _map: Dictionary = {}
var _nav = null
var _players: Array[Dictionary] = []
var _ids: Dictionary = {}
var _rng := RandomNumberGenerator.new()
var _accumulator := 0.0
var _input_segments: Array[Dictionary] = []
var _tick := 0
var _time := 0.0
var _phase := "unconfigured"
var _phase_time := 0.0
var _round_time := ROUND_SECONDS
var _round := 0
var _score: Dictionary = {"ct": 0, "t": 0}
var _team_sides: Dictionary = {"ct": "ct", "t": "t"}
var _bomb: Dictionary = {}
var _events: Array[Dictionary] = []
var _round_events: Array[Dictionary] = []
var _history: Array[Dictionary] = []
var _intel: Dictionary = {"ct": {}, "t": {}}
var _human_id := ""
var _human_team := ""
var human_id: String:
	get:
		return _human_id
var _human_control := true
var _winner := ""
var _message := ""
var _opening_recorded := false
var _seed := 0
var _knowledge: Dictionary = {}
var _watch_uses := 0
var command_error := ""
var _utilities: Array[Dictionary] = []
var _utility_serial := 0
var _loss_streak: Dictionary = {"ct": 0, "t": 0}
var _opening_plans: Dictionary = {}
var _route_bank: Array[Dictionary] = []
var _guard_plans: Dictionary = {}
var _guard_candidates: Dictionary = {}
var _plant_guard_key := ""
var _plant_guard_posts: Array[Dictionary] = []
var _t_guard_key := ""
var _t_guard_assignments: Dictionary = {}
var _allow_overtime := false


func configure(map: Dictionary, rosters: Dictionary, seed: int, knowledge: Dictionary = {}, allow_overtime: bool = false) -> bool:
	if map.is_empty() or rosters.get("ct", []).size() != 5 or rosters.get("t", []).size() != 5:
		return false
	_map = map.duplicate(true)
	_allow_overtime = allow_overtime
	_nav = MapModel.new()
	_nav.setup(_map)
	_knowledge = knowledge.duplicate(true) if not knowledge.is_empty() else _map.get("botlab_knowledge", {}).duplicate(true)
	if _knowledge.is_empty() and _map.get("map", "") == "de_dust2" and FileAccess.file_exists("res://data/botlab_knowledge.json"):
		var decoded = JSON.parse_string(FileAccess.get_file_as_string("res://data/botlab_knowledge.json"))
		if decoded is Dictionary:
			_knowledge = decoded
	if _nav.has_method("apply_knowledge"):
		_nav.apply_knowledge(_knowledge)
	_watch_uses = 0
	_rng.seed = seed
	_seed = seed
	_players.clear()
	_ids.clear()
	_human_id = str(rosters.get("human_id", ""))
	for team in ["ct", "t"]:
		var roster: Array = rosters[team]
		for index in range(5):
			var card: Dictionary = roster[index]
			var pid := str(card.get("id", card.get("player_id", team + str(index + 1))))
			if pid.is_empty() or _ids.has(pid):
				_phase = "unconfigured"
				return false
			var ability := clampf(float(card.get("ability", 75)), 0.0, 100.0)
			if not is_finite(ability):
				return false
			var skills: Dictionary = card.get("skills", {}).duplicate(true)
			for key in ["aim", "reaction", "recoil", "awareness", "utility"]:
				skills[key] = clampf(float(skills.get(key, ability)), 0.0, 100.0)
				if not is_finite(float(skills[key])):
					return false
			var p: Dictionary = {"id": pid, "name": str(card.get("name", pid)), "team": team, "side": team,
				"index": index, "role": str(card.get("role", "rifle")), "ability": ability, "skills": skills,
				"has_kit": bool(card.get("kit", index < 2)), "human": pid == _human_id,
				"weapon": "pistol", "primary_weapon": "", "inventory": {}, "reserve": 60, "money": 6000,
				"smokes": 1, "flashes": 1, "utility_cooldown": 0.0, "flash_remaining": 0.0,
				"walking": false, "reaction_target": "", "reaction_remaining": 0.0, "burst": 0,
				"k": 0, "d": 0, "a": 0, "damage": 0, "shots": 0, "hits": 0,
				"plants": 0, "defuses": 0, "survived_rounds": 0, "kast_rounds": 0,
				"opening_kills": 0, "opening_deaths": 0, "round_k": 0, "round_a": 0,
				"round_damage": 0, "round_traded": false, "last_death": {}, "damagers": {},
				"pos": Vector2.ZERO, "aim": Vector2.RIGHT, "yaw": 0.0, "path": [], "goal": Vector2.ZERO,
				"task": "", "alive": true, "hp": 100, "ammo": 30, "reloading": 0.0, "cooldown": 0.0,
				"moving": false, "interacting": false, "visible": true, "visible_enemy_ids": [], "seen_target": ""}
			_ids[pid] = _players.size()
			_players.append(p)
	if not _human_id.is_empty() and not _ids.has(_human_id):
		_phase = "unconfigured"
		return false
	_human_team = str(_players[_ids[_human_id]]["team"]) if not _human_id.is_empty() else ""
	_accumulator = 0.0
	_input_segments.clear()
	_utilities.clear()
	_utility_serial = 0
	_loss_streak = {"ct": 0, "t": 0}
	_tick = 0
	_time = 0.0
	_round = 0
	_score = {"ct": 0, "t": 0}
	_team_sides = {"ct": "ct", "t": "t"}
	_events.clear()
	_history.clear()
	_winner = ""
	_warm_opening_plans()
	_warm_guard_plans()
	_begin_round()
	return true


func setup(map: Dictionary, rosters: Dictionary, seed: int = 1) -> bool:
	return configure(map, rosters, seed)


func get_map_model():
	return _nav


func set_human_control(enabled: bool) -> void:
	_human_control = enabled
	if _ids.has(_human_id):
		var p: Dictionary = _players[_ids[_human_id]]
		_set_goal(p, p["goal"], str(p["task"]), str(p.get("route_via", "")), true)


func select_human(id: String) -> bool:
	if not _ids.has(id) or _phase in ["unconfigured", "finished"]:
		return false
	var next: Dictionary = _players[_ids[id]]
	if not next["alive"] or (not _human_team.is_empty() and next["team"] != _human_team):
		return false
	var previous := _human_id
	_human_id = id
	_human_team = str(next["team"])
	for p in _players:
		p["human"] = p["id"] == id
		if p["id"] == previous and p["alive"]:
			_set_goal(p, p["goal"], str(p["task"]), str(p.get("route_via", "")), true)
	_emit("human_selected", {"id": id, "previous_id": previous, "team": _human_team})
	return true


func command_move(team: String, point: Vector2, ids: Array = [], append: bool = false) -> bool:
	command_error = "此处不可到达，请点击可行走区域。"
	if not point.is_finite() or not _score.has(team) or _phase in ["unconfigured", "finished"]:
		return false
	var selected: Array = []
	for p in _players:
		if p["team"] == team and p["alive"] and (ids.is_empty() or p["id"] in ids):
			# An empty selection commands AI teammates, not the WASD-controlled actor.
			if ids.is_empty() and p["human"] and _human_control:
				continue
			selected.append(p)
	if selected.is_empty():
		command_error = "没有可执行指令的存活队员。"
		return false
	# Plan every selected unit first: a bad click must not partly redirect a group.
	var plans: Array = []
	var group_start := Vector2.ZERO
	for p in selected:group_start+=Vector2(p["pos"])
	group_start/=selected.size()
	var group_direction := (point-group_start).normalized()
	for index in range(selected.size()):
		var p: Dictionary = selected[index]
		var offset := Vector2.ZERO if selected.size() == 1 else Vector2.from_angle(float(index) * TAU / selected.size()) * 8.0
		var goal: Vector2 = _nav.nearest_walkable(point + offset, PLAYER_RADIUS)
		if goal.distance_to(point + offset) > 12.0: return false
		var queued: Array = p.get("queued_goals", [])
		if append and queued.size() >= 16:
			command_error = "最多追加 16 个路点，完成后可继续安排。"
			return false
		var start: Vector2 = p["goal"] if append and not p["path"].is_empty() else p["pos"]
		if append and not queued.is_empty(): start = queued[-1]
		var route: Array = _nav.find_path(start, goal, PLAYER_RADIUS, p["side"])
		if route.is_empty() and start.distance_to(goal) > .1: return false
		plans.append({"p":p, "goal":goal, "path":route})
	for plan in plans:
		var p: Dictionary = plan["p"]
		p["order"] = "move"
		if append and not p["path"].is_empty():
			p["queued_goals"].append(plan["goal"])
			var queued_traffic: Array = p.get("queued_traffic",[])
			queued_traffic.append({"center":point,"direction":group_direction})
			p["queued_traffic"]=queued_traffic
		else:
			p["queued_goals"] = []
			p["queued_traffic"] = []
			p["goal"] = plan["goal"]
			p["path"] = plan["path"]
			p["task"] = "move"
			p["route_via"] = ""
			p["route_ingress"] = []
			p["travel_mark"] = p["pos"]
			p["travel_since"] = _time
			p["passed_route"] = [p["pos"]]
			p["traffic_center"]=point
			p["traffic_direction"]=group_direction
			p["travel_best"]=INF
			p["traffic_yield_path"]=[]
			p["traffic_yield_for"]=""
			p.erase("traffic_active_target")
	command_error = ""
	_emit("command", {"team": team, "order": "move", "point": point, "append":append, "ids": selected.map(func(p): return p["id"])})
	return true


func command(team: String, order: String, ids: Array = []) -> bool:
	if not _score.has(team) or order not in ORDERS or _phase in ["unconfigured", "finished"]:
		return false
	var selected: Array[Dictionary] = []
	for p in _players:
		if p["team"] == team and p["alive"] and (ids.is_empty() or p["id"] in ids):
			selected.append(p)
	if selected.is_empty():
		return false
	for index in range(selected.size()):
		_order_player(selected[index], order, index)
	_emit("command", {"team": team, "order": order, "ids": selected.map(func(p): return p["id"])})
	return true


func step(dt: float, input: Dictionary = {}) -> void:
	if _phase in ["unconfigured", "finished"] or not is_finite(dt) or dt < 0.0:
		return
	_accumulator += dt
	if dt > 0.0:
		_input_segments.append({"remaining": dt, "input": input.duplicate(true), "actor_id": _human_id})
	# Bound one UI call's work, retaining (not dropping) any extra fixed ticks.
	var count := 0
	while _accumulator + 0.000000001 >= FIXED_DT and count < 600 and _phase != "finished":
		_accumulator -= FIXED_DT
		_fixed_tick(_tick_input())
		count += 1


func _tick_input() -> Dictionary:
	# Each state belongs to its own real-time interval. A new mouse click must
	# never be replayed over an older catch-up backlog (including step(0)).
	var left := FIXED_DT
	var result: Dictionary = {}
	var edges: Dictionary = {}
	var edge_actor := ""
	while left > 0.000000001 and not _input_segments.is_empty():
		var segment: Dictionary = _input_segments[0]
		var state: Dictionary = segment["input"]
		if edge_actor != str(segment["actor_id"]):
			edges.clear()
			edge_actor = str(segment["actor_id"])
		result = state.duplicate(true)
		result["_actor_id"] = segment["actor_id"]
		for key in ["reload", "smoke", "flash", "weapon"]:
			if state.get(key, false):
				edges[key] = state[key]
				state.erase(key)
		var consumed := minf(left, float(segment["remaining"]))
		left -= consumed
		segment["remaining"] -= consumed
		if float(segment["remaining"]) < 0.000000001:
			_input_segments.pop_front()
	result.merge(edges, true)
	return result


func snapshot(include_history: bool = false) -> Dictionary:
	var rows: Array[Dictionary] = []
	var visibility: Dictionary = {"ct": [], "t": []}
	for p in _players:
		if p["alive"]:
			for pid in p["visible_enemy_ids"]:
				if not visibility[p["team"]].has(pid):
					visibility[p["team"]].append(pid)
	var rounds_done := _history.size()
	var denominator := maxi(1, rounds_done + (1 if _phase == "live" else 0))
	for original in _players:
		var p: Dictionary = original.duplicate(true)
		p["position"] = p["pos"]
		p["human_control"] = p["human"] and _human_control
		p["ammo"] = int(p["ammo"])
		p["weapon_name"] = WEAPONS[p["weapon"]]["name"]
		p["magazine"] = WEAPONS[p["weapon"]]["magazine"]
		p["adr"] = snappedf(float(p["damage"]) / denominator, 0.1)
		p["kast"] = float(p["kast_rounds"]) / maxi(1, rounds_done) if rounds_done > 0 else 0.0
		p["rating"] = _rating(p, rounds_done) if rounds_done > 0 else null
		p["rounds"] = rounds_done
		p["spotted_by"] = []
		for team in ["ct", "t"]:
			if p["id"] in visibility[team]:
				p["spotted_by"].append(team)
		p.erase("damagers")
		rows.append(p)
	var bomb: Dictionary = _bomb.duplicate(true)
	var knowledge_usage: Dictionary = _nav.knowledge_usage() if _nav.has_method("knowledge_usage") else {}
	knowledge_usage["source"] = _knowledge.get("source", {}).duplicate(true)
	knowledge_usage["sim_watch_uses"] = _watch_uses
	bomb["position"] = bomb.get("pos", Vector2.ZERO)
	bomb["timer"] = bomb.get("remaining", 0.0)
	return {"schema_version": 2, "map": _map.get("map", ""), "map_name": _map.get("name", ""), "phase": _phase, "phase_time": _phase_time, "time": _time, "tick": _tick, "seed": _seed,
		"round": _round, "round_time": _round_time, "score": _score.duplicate(), "team_sides": _team_sides.duplicate(),
		"players": rows, "bomb": bomb, "utilities": _utilities.duplicate(true), "events": _events.slice(maxi(0, _events.size() - 40)).duplicate(true),
		"rounds_completed": rounds_done,
		"round_history": _history.duplicate(true) if include_history else [],
		"winner": _winner, "message": _message, "finished": _phase == "finished", "human_id": _human_id, "human_team": _human_team,
		"visible_enemy_ids": visibility, "knowledge": knowledge_usage,
		"rules": {"fixed_tick": FIXED_DT, "round_seconds": ROUND_SECONDS, "bomb_seconds": BOMB_SECONDS,
			"mr12": true, "overtime": _allow_overtime, "overtime_format": "MR3; swap sides every 3 rounds; $10000 per half" if _allow_overtime else "none", "friendly_fire": false, "ammo_economy": true,
			"economy": "practice start $6000; automatic affordable loadouts, retained survivor guns; round rewards",
			"move_speed": MOVE_SPEED, "walk_factor": WALK_FACTOR, "actor_radius": PLAYER_RADIUS,
			"assist_damage": 40, "trade_window": 5.0, "explosion_environment_damage": false,
			"visibility": "AI only engages live line-of-sight targets; spectator renders all positions",
			"rating": "Career Rating v2, sample gameplay metrics; not official HLTV Rating"}}


func pop_events() -> Array[Dictionary]:
	var out: Array[Dictionary] = _events.duplicate(true)
	_events.clear()
	return out


func report() -> Dictionary:
	var state := snapshot(true)
	return {"schema_version": 2, "map": _map.get("map", ""), "map_schema_version": _map.get("schema_version", 1),
		"map_source": _map.get("source", {}).duplicate(true), "map_limitations": _map.get("limitations", []).duplicate(),
		"finished": state["finished"], "winner": state["winner"], "score": state["score"],
		"players": state["players"], "round_history": state["round_history"], "seed": _seed,
		"rules": state["rules"], "knowledge": state["knowledge"]}


func _warm_guard_plans() -> void:
	# Every post is a legal, reachable NAV point. Wide positions protect site
	# approaches and let several teammates form a crossfire around the bomb.
	_guard_plans.clear()
	_guard_candidates.clear()
	_plant_guard_key = ""
	for site in ["A", "B"]:
		var center := _target(site + "_site")
		var keys: Array = _map.get("site_entrances", {}).get(site, ["A_long", "A_short", "CT_connector"] if site == "A" else ["B_tunnel", "B_door", "CT_connector"])
		var entrances: Array[Vector2] = []
		for key in keys: entrances.append(_target(str(key)))
		var posts: Array[Dictionary] = []
		for row in _map.get("postplant_posts", {}).get(site, []):
			var point := _vector(row["position"])
			if _nav.is_walkable(point, PLAYER_RADIUS) and not _nav.find_path(center, point, PLAYER_RADIUS).is_empty():
				posts.append({"position": point, "watch": _vector(row.get("watch", row["position"]))})
		if posts.size() < 5:
			var candidates: Array[Dictionary] = []
			for radius in [78.0, 116.0, 158.0]:
				for degrees in range(0, 360, 20):
					var point: Vector2 = _nav.nearest_walkable(center + Vector2.RIGHT.rotated(deg_to_rad(degrees)) * radius, PLAYER_RADIUS)
					var distance := center.distance_to(point)
					if distance < 60.0 or distance > 184.0: continue
					if candidates.any(func(row): return Vector2(row["position"]).distance_to(point) < 18.0): continue
					var watch: Vector2 = entrances[0] if not entrances.is_empty() else center
					var visible := false
					var nearest := INF
					for entry in entrances:
						var can_see: bool = not _nav.segment_blocked(point, entry)
						var value := point.distance_to(entry)
						if (can_see and not visible) or (can_see == visible and value < nearest):
							visible = can_see; nearest = value; watch = entry
					candidates.append({"position": point, "watch": watch, "visible": visible, "bomb_visible": not _nav.segment_blocked(center, point), "distance": distance})
			_guard_candidates[site] = candidates.duplicate(true)
			while posts.size() < 5 and not candidates.is_empty():
				var best := -1
				var best_score := -INF
				for index in range(candidates.size()):
					var row: Dictionary = candidates[index]
					var separation := 150.0
					for post in posts: separation = minf(separation, Vector2(row["position"]).distance_to(post["position"]))
					if separation < 40.0: continue
					var score := separation + (35.0 if row["visible"] else 0.0) + (95.0 if row["bomb_visible"] and posts.size() < 3 else 0.0) - absf(float(row["distance"]) - 105.0) * .2
					if score > best_score: best_score = score; best = index
				if best < 0: break
				var selected: Dictionary = candidates.pop_at(best)
				if _nav.find_path(center, selected["position"], PLAYER_RADIUS).is_empty(): continue
				posts.append(selected)
		# Assign several entry lanes; an unseen lane remains a direction to
		# watch, never knowledge of an enemy beyond the visibility mask.
		var watched: Dictionary = {}
		for post in posts:
			var best_watch: Vector2 = post["watch"]
			var best_value := -INF
			for entry in entrances:
				var value: float = (120.0 if not _nav.segment_blocked(post["position"], entry) else 0.0) - float(watched.get(entry, 0)) * 180.0 - Vector2(post["position"]).distance_to(entry) * .1
				if value > best_value: best_value = value; best_watch = entry
			post["watch"] = best_watch
			watched[best_watch] = int(watched.get(best_watch, 0)) + 1
		_guard_plans[site] = posts


func postplant_positions(site: String) -> Array:
	return _guard_plans.get(site, []).duplicate(true)


func _posts_for_current_bomb() -> Array:
	var site: String = _bomb["site"]
	var bomb_pos: Vector2 = _bomb["pos"]
	var key := site + ":" + str(bomb_pos)
	if key == _plant_guard_key: return _plant_guard_posts
	_plant_guard_key = key
	_plant_guard_posts.clear()
	var pool: Array = _guard_candidates.get(site, []).duplicate(true)
	# A legal plant can lie near the edge of the site. A post that sees the
	# nominal centre may have a wall between it and that actual C4 position.
	for row in _guard_plans.get(site, []):
		var shifted: Vector2 = _nav.nearest_walkable(Vector2(row["position"]) + bomb_pos - _target(site + "_site"), PLAYER_RADIUS)
		pool.append({"position": shifted, "watch": row["watch"], "visible": row.get("visible", false)})
	for row in pool:
		var point: Vector2 = row["position"]
		row["bomb_visible"] = point.is_finite() and (not _nav.has_method("is_walkable") or _nav.is_walkable(point, PLAYER_RADIUS)) and not _nav.segment_blocked(point, bomb_pos, 0.0)
	var cover_slots := 2
	while _plant_guard_posts.size() < 5 and not pool.is_empty():
		var best := -1
		var best_value := -INF
		for index in range(pool.size()):
			var row: Dictionary = pool[index]
			if _plant_guard_posts.size() < cover_slots and not row["bomb_visible"]: continue
			var distance: float = bomb_pos.distance_to(row["position"])
			if distance < 60 or distance > 184: continue
			var separation := 150.0
			for other in _plant_guard_posts: separation = minf(separation, Vector2(row["position"]).distance_to(other["position"]))
			if separation < 40: continue
			var value := separation + (150.0 if row["bomb_visible"] and _plant_guard_posts.size() < 3 else 0.0) + (25.0 if row.get("visible", false) else 0.0) - absf(distance - 105.0) * .2
			if value > best_value: best_value = value; best = index
		if best < 0:
			if _plant_guard_posts.size() < cover_slots:
				cover_slots = _plant_guard_posts.size()
				continue # No further legal bomb sightline; keep real entrance cover.
			break
		var selected: Dictionary = pool.pop_at(best)
		if _nav.find_path(bomb_pos, selected["position"], PLAYER_RADIUS, "t").is_empty(): continue
		selected["covers_bomb"] = bool(selected["bomb_visible"]) and _plant_guard_posts.size() < 2
		_plant_guard_posts.append(selected)
	if _plant_guard_posts.is_empty(): _plant_guard_posts.assign(_guard_plans.get(site, []))
	var watched: Dictionary = {}
	for post in _plant_guard_posts:
		var best_watch: Vector2 = post["watch"]
		var best_value := -INF
		for entrance in _map.get("site_entrances", {}).get(site, ["A_long", "A_short", "CT_connector"] if site == "A" else ["B_tunnel", "B_door", "CT_connector"]):
			var entry := _target(str(entrance))
			var value: float = (120.0 if not _nav.segment_blocked(post["position"], entry) else 0.0) - float(watched.get(entry, 0)) * 180.0 - Vector2(post["position"]).distance_to(entry) * .1
			if value > best_value: best_value = value; best_watch = entry
		post["watch"] = best_watch
		watched[best_watch] = int(watched.get(best_watch, 0)) + 1
	return _plant_guard_posts


func _t_postplant_assignments(posts: Array) -> Dictionary:
	# Responsibilities belong to living teammates, not dead roster slots.
	# Only the known C4 and friendly positions are used; no hidden CT state.
	var guards: Array[Dictionary] = []
	var ids: Array[String] = []
	for friend in _players:
		if friend["alive"] and friend["side"] == "t" and friend["task"] not in ["save", "hold"] and not (friend["human"] and _human_control):
			guards.append(friend)
			ids.append(str(friend["id"]))
	var key := "%s|%s|%s|%s" % [_round, _bomb["site"], _bomb["pos"], ",".join(ids)]
	if key == _t_guard_key: return _t_guard_assignments
	_t_guard_key = key
	var previous_assignments := _t_guard_assignments.duplicate(true)
	_t_guard_assignments.clear()
	var remaining := guards.duplicate()
	# A surviving bomb watcher keeps that responsibility; replace only the
	# empty critical slots before redistributing entrance cover.
	for post in posts:
		if not bool(post.get("covers_bomb", false)): continue
		for index in range(remaining.size()):
			var friend: Dictionary = remaining[index]
			var previous: Dictionary = previous_assignments.get(str(friend["id"]), {})
			if previous.is_empty() or Vector2(previous["position"]).distance_to(post["position"]) > .1 or friend["task"] != "guard bomb": continue
			if _route_path(friend["pos"], post["position"], "t").is_empty(): continue
			_t_guard_assignments[str(friend["id"])] = post.duplicate(true)
			remaining.remove_at(index)
			break
	for post in posts:
		if _t_guard_assignments.values().any(func(row): return Vector2(row["position"]).distance_to(post["position"]) < .1): continue
		var chosen := -1
		var best_cost := INF
		for index in range(remaining.size()):
			var friend: Dictionary = remaining[index]
			var route: Array = _route_path(friend["pos"], post["position"], "t")
			if route.is_empty(): continue
			var cost := 0.0
			var previous: Vector2 = friend["pos"]
			for point in route:
				cost += previous.distance_to(point)
				previous = point
			if cost < best_cost: best_cost = cost; chosen = index
		if chosen < 0: continue
		var friend: Dictionary = remaining.pop_at(chosen)
		_t_guard_assignments[str(friend["id"])] = post.duplicate(true)
		if remaining.is_empty(): break
	return _t_guard_assignments


func _warm_opening_plans() -> void:
	# Static spawn/formation plans are prepared once while loading a match.
	# The map's bounded dynamic cache may evict a route during live play; that
	# must not turn the next round's ten orders into a one-second UI freeze.
	_opening_plans.clear()
	_route_bank.clear()
	for side in ["ct", "t"]:
		var orders: Array = ["default"] if side == "ct" else ["split_a", "split_b"]
		for order in orders:
			for index in range(5):
				var template: Dictionary = _players[index].duplicate(true)
				template["side"] = side
				template["pos"] = _spawn(side, index)
				_order_player(template, order, index)
				var plan: Dictionary = {}
				for key in ["goal","path","task","order","route_via","route_via_pos","route_ingress"]:
					plan[key] = template[key]
				_opening_plans["%s|%s|%d" % [side,order,index]] = plan.duplicate(true)
	for key in _opening_plans:
		var plan: Dictionary = _opening_plans[key]
		var parts: PackedStringArray = str(key).split("|")
		var nodes: Array = [_spawn(parts[0], int(parts[2]))]
		nodes.append_array(plan["path"])
		_bank_bidirectional(nodes)
	# The opening routes can contain a one-way drop, so an A-to-B retake
	# cannot assume it may reverse them. Warm explicit static objective links.
	for first in ["A_site","B_site","CT_connector"]:
		for last in ["A_site","B_site","CT_connector"]:
			if first == last:
				continue
			var start := _target(first)
			var nodes: Array = [start]
			nodes.append_array(_nav.find_path(start,_target(last),PLAYER_RADIUS,"ct"))
			_bank_bidirectional(nodes)


func _bank_bidirectional(nodes: Array) -> void:
	_bank_route(nodes)
	# Reverse only portions whose directed portals permit it. A jump-down
	# edge is never silently turned into a jump-up edge.
	var backwards := nodes.duplicate()
	backwards.reverse()
	var run: Array = []
	for point in backwards:
		if not run.is_empty() and _nav.segment_blocked(run[-1],point,PLAYER_RADIUS):
			_bank_route(run)
			run = []
		run.append(point)
	_bank_route(run)


func _bank_route(nodes: Array) -> void:
	if nodes.size() < 2:
		return
	var prefix: Array[float] = [0.0]
	for index in range(1, nodes.size()):
		prefix.append(prefix[-1] + Vector2(nodes[index-1]).distance_to(nodes[index]))
	_route_bank.append({"nodes": nodes.duplicate(), "prefix": prefix})


func _cached_route(from: Vector2, to: Vector2) -> Array:
	var best := INF
	var found: Array = []
	var connections: Dictionary = {}
	for chain in _route_bank:
		var nodes: Array = chain["nodes"]
		var prefix: Array = chain["prefix"]
		var entries: Array = []
		var exits: Array = []
		for index in range(nodes.size()):
			var node: Vector2 = nodes[index]
			var start_distance := from.distance_to(node)
			var end_distance := to.distance_to(node)
			if start_distance <= 96.0:
				var start_key := "start|" + str(node)
				if not connections.has(start_key):
					connections[start_key] = not _nav.segment_blocked(from, node, PLAYER_RADIUS)
				if connections[start_key]:
					entries.append({"index":index,"distance":start_distance})
			if end_distance <= 96.0:
				var end_key := "end|" + str(node)
				if not connections.has(end_key):
					connections[end_key] = not _nav.segment_blocked(node, to, PLAYER_RADIUS)
				if connections[end_key]:
					exits.append({"index":index,"distance":end_distance})
		for entry in entries:
			for exit in exits:
				var first: int = entry["index"]
				var last: int = exit["index"]
				if last < first:
					continue
				var cost: float = entry["distance"] + prefix[last] - prefix[first] + exit["distance"]
				if cost < best:
					best = cost
					found = nodes.slice(first,last+1)
					found.append(to)
	return found


func _route_path(from: Vector2, to: Vector2, side: String) -> Array:
	if not _nav.segment_blocked(from, to, PLAYER_RADIUS):
		return [to]
	if not _route_bank.is_empty():
		var reused := _cached_route(from, to)
		if not reused.is_empty():
			return reused
		# A planted C4 and its guard offsets are dynamic, and can be separated
		# from a nearby route node by an actual NAV portal/wall. Reuse the known
		# static site approach, then ask for only the short final site path.
		# Never substitute straight-line movement for the radius/portal checks.
		for key in ["A_site", "B_site"]:
			var entrance := _target(key)
			# Wider postplant positions still join the prewarmed site corridor.
			if entrance.distance_to(to) > 220.0:
				continue
			var approach: Array = [entrance] if not _nav.segment_blocked(from,entrance,PLAYER_RADIUS) else _cached_route(from,entrance)
			if approach.is_empty():
				continue
			var tail: Array = _nav.find_path(entrance,to,PLAYER_RADIUS,side)
			if not tail.is_empty():
				approach.append_array(tail)
				return approach
		# A-to-B retakes commonly join two known corridors at CT spawn. These
		# joins are checked at the same radius and preserve every directed edge.
		for key in ["CT_connector","A_short","B_tunnel","B_door"]:
			var anchor := _target(key)
			var first: Array = [anchor] if not _nav.segment_blocked(from,anchor,PLAYER_RADIUS) else _cached_route(from,anchor)
			if first.is_empty():
				continue
			var second: Array = [to] if not _nav.segment_blocked(anchor,to,PLAYER_RADIUS) else _cached_route(anchor,to)
			if not second.is_empty():
				first.append_array(second)
				return first
	return _nav.find_path(from, to, PLAYER_RADIUS, side)


func _begin_round() -> void:
	_round += 1
	if _round == 13:
		_team_sides = {"ct": "t", "t": "ct"}
	if _allow_overtime and _round >= 25:
		if _round > 25 and (_round - 25) % 3 == 0:
			_team_sides = {"ct": "t" if _team_sides["ct"] == "ct" else "ct", "t": "t" if _team_sides["t"] == "ct" else "ct"}
		if (_round - 25) % 3 == 0:
			_loss_streak = {"ct": 0, "t": 0}
			for p in _players:
				p["money"] = 10000
				p["primary_weapon"] = ""
				p["inventory"] = {}
	_round_events.clear()
	_plant_guard_key = ""
	_t_guard_key = ""
	_t_guard_assignments.clear()
	_utilities.clear()
	_intel = {"ct": {}, "t": {}}
	_opening_recorded = false
	_round_time = ROUND_SECONDS
	_phase = "freeze"
	_phase_time = FREEZE_SECONDS
	_message = "第 %d 回合 · %s" % [_round, "MR3 加时" if _round >= 25 else "MR12 半场换边" if _round == 13 else "准备阶段"]
	for p in _players:
		var retained := _round > 1 and bool(p["alive"])
		p["side"] = _team_sides[p["team"]]
		_buy_loadout(p, retained)
		var spawn := _spawn(str(p["side"]), int(p["index"]))
		p.merge({"pos": spawn, "goal": spawn, "path": [], "aim": spawn + Vector2.RIGHT * 80.0,
			"yaw": 0.0, "alive": true, "hp": 100, "reloading": 0.0, "cooldown": 0.0,
			"round_k": 0, "round_a": 0, "round_damage": 0, "round_traded": false,
			"round_opening_kills": 0, "round_opening_deaths": 0,
			"moving": false, "interacting": false, "damagers": {}, "last_death": {},
			"reload_pending": false, "visible_enemy_ids": [], "seen_target": "", "walking": false,
			"reaction_target": "", "reaction_remaining": 0.0, "flash_remaining": 0.0,
			"utility_cooldown": 0.0, "burst": 0, "travel_mark": spawn, "travel_since": _time,
			"yield_until": 0.0, "yield_direction": Vector2.ZERO}, true)
		p["queued_goals"] = []
		p["queued_traffic"] = []
		p["passed_route"] = [spawn]
		p["traffic_yield_for"]=""
		p["traffic_yield_path"]=[]
		p.erase("traffic_active_target")
		p.erase("guard_watch")
		p["travel_best"]=INF
		p["traffic_center"]=spawn
		p["traffic_direction"]=Vector2.ZERO
	var carrier: Dictionary = {}
	for p in _players:
		if p["side"] == "t" and (carrier.is_empty() or (p["human"] and _human_control)):
			carrier = p
			if p["human"] and _human_control:
				break
	_bomb = {"state": "carried", "carrier_id": carrier["id"], "pos": carrier["pos"], "site": "",
		"remaining": BOMB_SECONDS, "progress": 0.0, "actor_id": "", "action": "", "planter_id": ""}
	for p in _players:
		var opening := "default" if p["side"] == "ct" else "split_a" if _round % 3 != 0 else "split_b"
		var key := "%s|%s|%d" % [p["side"],opening,p["index"]]
		if _opening_plans.has(key):
			p.merge(_opening_plans[key].duplicate(true), true)
		else:
			_order_player(p, "default", int(p["index"]))
	_emit("round_start", {"round": _round, "team_sides": _team_sides.duplicate(), "carrier_id": carrier["id"]})


func _fixed_tick(input: Dictionary) -> void:
	_tick += 1
	_time = float(_tick) * FIXED_DT
	if _phase in ["freeze", "round_end"]:
		if _phase == "freeze" and _human_control and _ids.has(_human_id) and str(input.get("_actor_id", _human_id)) == _human_id:
			var human: Dictionary = _players[_ids[_human_id]]
			if input.has("weapon"):
				_switch_weapon(human, str(input["weapon"]))
			var aim: Vector2 = input.get("aim", human["aim"])
			if aim.is_finite() and aim.distance_squared_to(human["pos"]) > 0.01:
				human["aim"] = aim
				human["yaw"] = (aim - Vector2(human["pos"])).angle()
		_phase_time = maxf(0.0, _phase_time - FIXED_DT)
		if _phase_time <= 0.000001:
			if _phase == "round_end":
				if _match_decided():
					_finish_match()
				else:
					_begin_round()
			else:
				_phase = "live"
				_message = "回合进行中"
				_emit("round_live", {})
		return
	if _phase != "live":
		return
	_round_time = maxf(0.0, _round_time - FIXED_DT)
	_update_utilities()
	var interactions: Array[Dictionary] = []
	for p in _players:
		if not p["alive"]:
			continue
		# Keep a single tick of fractional overshoot so rates such as 11 shots/s
		# do not silently round down to 10 on a 60 Hz simulation.
		p["cooldown"] = maxf(-FIXED_DT, float(p["cooldown"]) - FIXED_DT)
		p["reloading"] = maxf(0.0, float(p["reloading"]) - FIXED_DT)
		p["reaction_remaining"] = maxf(0.0, float(p["reaction_remaining"]) - FIXED_DT)
		p["flash_remaining"] = maxf(0.0, float(p["flash_remaining"]) - FIXED_DT)
		p["utility_cooldown"] = maxf(0.0, float(p["utility_cooldown"]) - FIXED_DT)
		if float(p["cooldown"]) <= 0.0 and _tick % 12 == 0:
			p["burst"] = maxi(0, int(p["burst"]) - 1)
		if p.get("reload_pending", false) and float(p["reloading"]) <= 0.0:
			var transfer := mini(int(WEAPONS[p["weapon"]]["magazine"]) - int(p["ammo"]), int(p["reserve"]))
			p["ammo"] += transfer
			p["reserve"] -= transfer
			p["reload_pending"] = false
			_sync_weapon(p)
			_emit("reload_complete", {"id": p["id"]})
		p["moving"] = false
		p["interacting"] = false
		if p["human"] and _human_control:
			_human_tick(p, input, interactions)
		else:
			_ai_tick(p, interactions)
		if _phase != "live":
			return
	_update_bomb(interactions)
	if _phase != "live":
		return
	var alive_t := _alive_side("t")
	var alive_ct := _alive_side("ct")
	if alive_ct == 0:
		_end_round("t", "CT 全员被消灭")
	elif alive_t == 0 and _bomb["state"] != "planted":
		_end_round("ct", "T 全员被消灭，且炸弹尚未下包")
	elif _round_time <= 0.000001 and _bomb["state"] != "planted":
		_end_round("ct", "回合时间耗尽，炸弹未下包")


func _human_tick(p: Dictionary, input: Dictionary, interactions: Array[Dictionary]) -> void:
	if str(input.get("_actor_id", _human_id)) != str(p["id"]):
		input = {}
	_visible_enemy(p) # Perception only: never use this target to aim or fire.
	if input.has("weapon"):
		_switch_weapon(p, str(input["weapon"]))
	var move: Vector2 = input.get("move", Vector2.ZERO)
	if not move.is_finite():
		move = Vector2.ZERO
	if move.length_squared() > 1.0:
		move = move.normalized()
	p["walking"] = bool(input.get("walk", false))
	_move_player(p, move * MOVE_SPEED * (WALK_FACTOR if p["walking"] else 1.0) * FIXED_DT)
	var target: Vector2 = input.get("aim", p["aim"])
	if target.is_finite() and target.distance_squared_to(p["pos"]) > 0.01:
		p["aim"] = target
		p["yaw"] = (target - Vector2(p["pos"])).angle()
	if input.get("smoke", false):
		_throw_utility(p, "smoke", p["aim"])
	elif input.get("flash", false):
		_throw_utility(p, "flash", p["aim"])
	if input.get("reload", false):
		_reload(p)
	if input.get("interact", false) and not p["moving"] and not input.get("fire", false) and float(p["reloading"]) <= 0.0:
		interactions.append(p)
		p["interacting"] = true
	elif input.get("fire", false):
		_fire(p)


func _ai_tick(p: Dictionary, interactions: Array[Dictionary]) -> void:
	p["walking"] = false
	var enemy := _visible_enemy(p)
	if not enemy.is_empty():
		var target: Vector2 = enemy["pos"]
		_intel[p["team"]][enemy["id"]] = {"pos": target, "seen_at": _time}
		var desired := (target - Vector2(p["pos"])).angle()
		if p["reaction_target"] != enemy["id"]:
			p["reaction_target"] = enemy["id"]
			p["reaction_remaining"] = reaction_seconds(p)
		var turn_speed := lerpf(2.8, 7.0, float(p["skills"]["aim"]) / 100.0)
		p["yaw"] = rotate_toward(float(p["yaw"]), desired, turn_speed * FIXED_DT)
		p["aim"] = Vector2(p["pos"]) + Vector2.from_angle(float(p["yaw"])) * FIRE_RANGE
		if Vector2(p["pos"]).distance_to(target) > float(WEAPONS[p["weapon"]]["range"]):
			_follow_path(p)
			return
		if float(p["reaction_remaining"]) <= 0.0 and int(p["flashes"]) > 0 and float(p["utility_cooldown"]) <= 0.0 and p["role"] == "igl" and Vector2(p["pos"]).distance_to(target) < FLASH_RADIUS:
			_throw_utility(p, "flash", target)
		if p["ammo"] <= 0:
			if int(p["reserve"]) > 0:
				_reload(p)
			elif p["weapon"] != "pistol":
				_switch_weapon(p, "pistol")
		elif float(p["reaction_remaining"]) <= 0.0 and absf(angle_difference(float(p["yaw"]), desired)) < 0.015:
			_fire(p)
		return
	p["reaction_target"] = ""
	if _bomb["state"] == "planted" and p["task"] not in ["save", "hold"]:
		_postplant(p, interactions)
	elif _bomb["state"] == "dropped" and p["side"] == "t" and _closest_side_to_bomb("t") == p["id"]:
		if Vector2(p["goal"]).distance_to(_bomb["pos"]) > 4.0:
			_set_goal(p, _bomb["pos"], "recover bomb")
	if _bomb["state"] == "carried" and _bomb["carrier_id"] == p["id"] and p["task"] not in ["save", "hold"]:
		var site := _site_at(p["pos"])
		if not site.is_empty() and float(p["reloading"]) <= 0.0:
			interactions.append(p)
			p["interacting"] = true
			return
	if int(p["smokes"]) > 0 and p["role"] == "igl" and float(p["utility_cooldown"]) <= 0.0:
		var smoke_target: Vector2 = _bomb["pos"] if _bomb["state"] == "planted" and p["side"] == "ct" else p["goal"]
		if p["side"] == "ct" and _bomb["state"] == "planted" and Vector2(p["pos"]).distance_to(smoke_target) < UTILITY_RANGE:
			_throw_utility(p, "smoke", smoke_target)
		elif p["side"] == "t" and _bomb["state"] == "carried" and Vector2(p["pos"]).distance_to(smoke_target) < 95.0:
			_throw_utility(p, "smoke", smoke_target)
	if p["interacting"]:
		return
	var low_mag := 1 if p["weapon"] == "awp" else 7
	if p["ammo"] < low_mag and int(p["reserve"]) > 0:
		_reload(p)
	_follow_path(p)
	if not p["moving"]:
		_watch(p)


func reaction_seconds(p: Dictionary) -> float:
	return lerpf(0.48, 0.13, float(p["skills"]["reaction"]) / 100.0)


func _postplant(p: Dictionary, interactions: Array[Dictionary]) -> void:
	var bomb_pos: Vector2 = _bomb["pos"]
	var defuser := _designated_defuser()
	if p["side"] == "ct" and p["id"] == defuser:
		if Vector2(p["pos"]).distance_to(bomb_pos) < 23.0 and not _nav.segment_blocked(p["pos"], bomb_pos, 0.0):
			if float(p["reloading"]) <= 0.0:
				interactions.append(p)
				p["interacting"] = true
			return
		if p["task"] != "defuse":
			_set_goal(p, bomb_pos, "defuse")
	else:
		var task := "cover defuser" if p["side"] == "ct" else "guard bomb"
		var posts: Array = _posts_for_current_bomb()
		var assigned: Dictionary = _t_postplant_assignments(posts).get(str(p["id"]), {}) if p["side"] == "t" else {}
		if p["side"] == "t" and not posts.is_empty() and assigned.is_empty(): return
		var changed: bool = p["side"] == "t" and not assigned.is_empty() and Vector2(p["goal"]).distance_to(assigned["position"]) > .1
		if p["task"] != task or changed:
			if not posts.is_empty():
				var post: Dictionary = assigned if not assigned.is_empty() else posts[int(p["index"]) % posts.size()]
				_set_goal(p, post["position"], task)
				p["guard_watch"] = bomb_pos if p["side"] == "t" and bool(post.get("covers_bomb", false)) else post["watch"]
			else:
				var approach := _target("CT_connector" if _bomb["site"] == "A" else "B_door")
				var angle := (approach - bomb_pos).angle() + float(int(p["index"])) * TAU / 5.0
				_set_goal(p, bomb_pos + Vector2.from_angle(angle) * 88.0, task)
				p["guard_watch"] = approach
		p["walking"] = p["side"] == "t" and Vector2(p["pos"]).distance_to(p["goal"]) < 24.0


func _designated_defuser() -> String:
	var found := ""
	var best := INF
	for p in _players:
		if not p["alive"] or p["side"] != "ct" or p["task"] in ["save", "hold"] or (p["human"] and _human_control):
			continue
		if _bomb.get("actor_id", "") == p["id"]:
			return str(p["id"])
		var cost := Vector2(p["pos"]).distance_to(_bomb["pos"]) / MOVE_SPEED + (KIT_SECONDS if p["has_kit"] else DEFUSE_SECONDS)
		if cost < best:
			best = cost
			found = str(p["id"])
	return found


func _watch(p: Dictionary) -> void:
	if (_tick + int(p["index"]) * 7) % 60 != 0:
		return
	var target: Vector2 = p["goal"]
	if p["task"] in ["guard bomb", "cover defuser"]:
		target = p.get("guard_watch", _target("CT_connector" if _bomb["site"] == "A" else "B_door"))
	elif _nav.has_method("preferred_watch"):
		target = _nav.preferred_watch(p["pos"], p["side"], p["role"])
		if target.is_finite() and target.distance_to(p["pos"]) > 5.0:
			_watch_uses += 1
	else:
		var path: Array = p["path"]
		if not path.is_empty():
			target = path[0]
	if target.is_finite() and target.distance_to(p["pos"]) > 5.0:
		p["yaw"] = (target - Vector2(p["pos"])).angle()
		p["aim"] = target


func _visible_enemy(p: Dictionary) -> Dictionary:
	# Per-actor 10Hz sensing on fixed ticks. A cached opponent still needs a
	# current clear LOS before tracking/fire; render visibility is never input.
	if float(p["flash_remaining"]) > 0.15:
		p["visible_enemy_ids"] = []
		p["seen_target"] = ""
		return {}
	if (_tick + int(p["index"])) % 6 != 0:
		var pid := str(p["seen_target"])
		if _ids.has(pid):
			var cached: Dictionary = _players[_ids[pid]]
			if cached["alive"] and _can_see(p, cached):
				return cached
		p["visible_enemy_ids"] = []
		return {}
	var found: Dictionary = {}
	var closest := FIRE_RANGE * FIRE_RANGE
	p["visible_enemy_ids"] = []
	for enemy in _players:
		if not enemy["alive"] or enemy["team"] == p["team"]:
			continue
		var distance := Vector2(p["pos"]).distance_squared_to(enemy["pos"])
		if not _can_see(p, enemy):
			continue
		p["visible_enemy_ids"].append(enemy["id"])
		if distance <= closest:
			closest = distance
			found = enemy
	p["seen_target"] = found.get("id", "")
	return found


func _can_see(p: Dictionary, enemy: Dictionary) -> bool:
	var offset: Vector2 = Vector2(enemy["pos"]) - Vector2(p["pos"])
	if offset.length_squared() > FIRE_RANGE * FIRE_RANGE:
		return false
	if p["human"] and _human_control:
		return not vision_blocked(p["pos"], enemy["pos"])
	var awareness := float(p["skills"]["awareness"]) / 100.0
	var half_fov := deg_to_rad(lerpf(65.0, 115.0, awareness))
	# Nearby running footsteps cause a turn only through a current clear LOS;
	# neither hearing nor last-known intelligence ever authorizes a wall shot.
	var in_fov: bool = absf(angle_difference(float(p["yaw"]), offset.angle())) <= half_fov or (offset.length() < 45.0 and enemy["moving"] and not enemy["walking"])
	return in_fov and not vision_blocked(p["pos"], enemy["pos"])


func vision_blocked(from: Vector2, to: Vector2) -> bool:
	if _nav.segment_blocked(from, to, 0.0):
		return true
	for utility in _utilities:
		if utility["kind"] == "smoke" and utility["state"] == "active":
			var nearest := Geometry2D.get_closest_point_to_segment(utility["pos"], from, to)
			if nearest.distance_to(utility["pos"]) <= float(utility["radius"]):
				return true
	return false


func _move_player(p: Dictionary, delta: Vector2) -> void:
	if delta.is_zero_approx():
		return
	var start: Vector2 = p["pos"]
	var goal: Vector2 = _nav.constrain_motion(start, start + delta, PLAYER_RADIUS)
	var yielding := not str(p.get("traffic_yield_for","")).is_empty()
	# A temporary courtesy move must not drop through a one-way NAV portal.
	# Every actual microstep, including collision steering, must be reversible.
	if yielding and _nav.segment_blocked(goal,start,PLAYER_RADIUS):goal=start
	p["traffic_blocker"]=""
	if not _actors_clear(p, start, goal):
		goal = start
		# Bounded tangential steering, never an unbounded push/teleport. Every
		# candidate is checked against every actor, not only the last collision.
		var handedness := 1.0 if int(p["index"]) % 2 == 0 else -1.0
		var target: Vector2 = p.get("traffic_active_target",p["path"][0] if not p["path"].is_empty() else start+delta)
		for angle in [PI/4.0, -PI/4.0, PI/2.0, -PI/2.0]:
			var candidate: Vector2 = _nav.constrain_motion(start, start + delta.rotated(angle * handedness), PLAYER_RADIUS)
			if yielding and _nav.segment_blocked(candidate,start,PLAYER_RADIUS):continue
			# A quarter-turn needs a brief sideways step to round a parked
			# teammate. Allow only a fraction of this frame's step away from
			# the target; the progress timer below still detects orbiting.
			if _actors_clear(p, start, candidate) and candidate.distance_squared_to(start) > 0.00001 and candidate.distance_to(target)<=start.distance_to(target)+delta.length()*.25:
				goal = candidate
				break
	p["pos"] = goal
	p["moving"] = goal.distance_squared_to(start) > 0.00001
	if p["moving"]:_remember_passage(p)


func _actors_clear(p: Dictionary, start: Vector2, goal: Vector2) -> bool:
	var minimum := PLAYER_RADIUS * 2.0 - 0.02
	for other in _players:
		if other["id"] == p["id"] or not other["alive"]:
			continue
		var old_distance := start.distance_to(other["pos"])
		var distance := goal.distance_to(other["pos"])
		var swept_distance := Geometry2D.get_closest_point_to_segment(other["pos"],start,goal).distance_to(other["pos"])
		if distance < minimum or (old_distance>=minimum and swept_distance<minimum):
			# A legacy/configured overlap may only separate, never grow closer.
			if old_distance >= minimum or distance <= old_distance + 0.00001:
				return false
	return true


func _follow_path(p: Dictionary) -> void:
	# A teammate who has already arrived must still make room for an actor
	# whose legal route passes its parking spot. A yield is a bounded normal
	# walk, not a push, teleport, disabled body or changed permanent order.
	if _follow_traffic_yield(p):return
	var ingress: Array = p.get("route_ingress", [])
	while not ingress.is_empty() and Vector2(p["pos"]).distance_to(ingress[0]["pos"]) < 12.0:
		_emit("route_ingress_reached", {"id": p["id"], "ingress": ingress[0]["id"], "pos": p["pos"], "point": ingress[0]["pos"]})
		ingress.pop_front()
	var via := str(p.get("route_via", ""))
	if not via.is_empty() and ingress.is_empty() and Vector2(p["pos"]).distance_to(p["route_via_pos"]) < 24.0:
		_emit("route_via_reached", {"id": p["id"], "via": via, "pos": p["pos"], "point": p["route_via_pos"]})
		p["route_via"] = ""
		via = ""
	var path: Array = p["path"]
	# A projected NAV portal may be only one actor wide. Do not cut a turn by
	# dropping its exact center two pixels early: that offset can block every
	# subsequent segment even though the original A* path is legal.
	while not path.is_empty():
		var near := Vector2(p["pos"]).distance_to(path[0])
		if near < 0.05:
			_remember_passage(p)
			path.pop_front()
		elif near < 8.0 and path.size() > 1 and not _nav.segment_blocked(p["pos"], path[1], PLAYER_RADIUS):
			# A teammate may occupy this node. Skip it only if the following
			# segment is legal from the actual position, never by cutting a wall.
			_remember_passage(p)
			path.pop_front()
		else:
			break
	if path.is_empty():
		var queued: Array = p.get("queued_goals", [])
		if queued.is_empty(): return
		var next: Vector2 = queued.pop_front()
		var traffic_queue: Array = p.get("queued_traffic",[])
		var traffic: Dictionary = traffic_queue.pop_front() if not traffic_queue.is_empty() else {}
		_set_goal(p, next, "move")
		if not traffic.is_empty():
			p["traffic_center"]=traffic["center"]
			p["traffic_direction"]=traffic["direction"]
		path = p["path"]
		if path.is_empty(): return
	var progress := _traffic_remaining(p)
	if progress<float(p.get("travel_best",INF))-.5:
		p["travel_best"]=progress
		p["travel_since"]=_time
	elif _time-float(p.get("travel_since",_time))>.5:
		_request_traffic_clearance(p,path)
		p["travel_since"]=_time
	var difference: Vector2 = Vector2(path[0]) - Vector2(p["pos"])
	var movement := difference.normalized() * minf(difference.length(), MOVE_SPEED * (WALK_FACTOR if p["walking"] else 1.0) * FIXED_DT)
	_move_player(p, movement)
	if not p["moving"]:
		if (_tick + int(p["index"])) % 30 == 0:
			_set_goal(p, p["goal"], str(p["task"]), via, true)
	elif difference.length_squared() > 0.01:
		p["yaw"] = rotate_toward(float(p["yaw"]), difference.angle(), 3.0 * FIXED_DT)
		p["aim"] = Vector2(p["pos"]) + Vector2.from_angle(float(p["yaw"])) * 80.0


func _traffic_remaining(p: Dictionary) -> float:
	var path: Array = p["path"]
	if path.is_empty():return 0.0
	var distance := Vector2(p["pos"]).distance_to(path[0])
	for index in range(1,path.size()):distance+=Vector2(path[index-1]).distance_to(path[index])
	var center: Vector2 = p.get("traffic_center",p["goal"])
	var forward: Vector2 = p.get("traffic_direction",Vector2.ZERO)
	# Correct the different spread goals back to their common destination:
	# a rear unit with a nearer parking spot must not outrank the front unit.
	return distance+(center-Vector2(p["goal"])).dot(forward)

func _traffic_precedes(p: Dictionary, other: Dictionary) -> bool:
	if other["path"].is_empty():return true
	var own := _traffic_remaining(p)
	var theirs := _traffic_remaining(other)
	if absf(own-theirs)>.5:return own<theirs
	return "%s|%d" % [p["team"],p["index"]]<"%s|%d" % [other["team"],other["index"]]

func _blocks_traffic(point: Vector2, start: Vector2, route: Array, clearance: float = PLAYER_RADIUS*2+.35) -> bool:
	var previous := start
	var walked := 0.0
	for node in route:
		var next: Vector2 = node
		if Geometry2D.get_closest_point_to_segment(point,previous,next).distance_to(point)<clearance:return true
		walked+=previous.distance_to(next)
		if walked>40.0:break
		previous=next
	return false

func _request_traffic_clearance(p: Dictionary, route: Array) -> void:
	for other in _players:
		if not other["alive"] or other["id"]==p["id"] or other["team"]!=p["team"] or (other["human"] and _human_control):continue
		# The requester has right of way. Asking it to retreat for its own
		# yielding blocker creates a mutual wait instead of a passage.
		if other["id"]==str(p.get("traffic_yield_for","")):continue
		if Vector2(p["pos"]).distance_to(other["pos"])>19.0:continue
		if not _blocks_traffic(other["pos"],p["pos"],route):continue
		if not str(other.get("traffic_yield_for","")).is_empty():continue
		if not _traffic_precedes(p,other):continue
		_begin_traffic_yield(other,p)

func _begin_traffic_yield(blocker: Dictionary, requester: Dictionary) -> bool:
	var start: Vector2 = blocker["pos"]
	var candidates: Array[Vector2] = []
	for point in blocker.get("passed_route",[]):
		if start.distance_to(point)>=8.0 and start.distance_to(point)<=20.0:candidates.append(point)
	for distance in [8.0,12.0,18.0]:
		for index in range(16):candidates.append(start+Vector2.from_angle(index*TAU/16)*distance)
	var best := -INF
	var best_path: Array = []
	for point in candidates:
		# Keep the existing navigation interface usable by simple/test maps.
		if _nav.nearest_walkable(point,PLAYER_RADIUS).distance_to(point)>.001:continue
		var end_clear := true
		for actor in _players:
			if actor["alive"] and actor["id"]!=blocker["id"] and point.distance_to(actor["pos"])<PLAYER_RADIUS*2+.2:end_clear=false;break
		if not end_clear:continue
		var path: Array = [point] if not _nav.segment_blocked(start,point,PLAYER_RADIUS) else _nav.find_path(start,point,PLAYER_RADIUS,blocker["side"])
		if path.is_empty():continue
		var reversible := true
		var previous := start
		for node in path:
			if _nav.segment_blocked(node,previous,PLAYER_RADIUS):reversible=false;break
			previous=node
		if not reversible:continue
		var length := start.distance_to(path[0])
		for index in range(1,path.size()):length+=Vector2(path[index-1]).distance_to(path[index])
		if length>28.0:continue
		var score := point.distance_to(requester["pos"])-length*.3
		if not _blocks_traffic(point,requester["pos"],requester["path"]):score+=40.0
		if _actors_clear(blocker,start,path[0]):score+=15.0
		if score>best:best=score;best_path=path
	if best_path.is_empty():return false
	blocker["traffic_yield_path"]=best_path
	blocker["traffic_yield_for"]=requester["id"]
	blocker["traffic_yield_start"]=start
	blocker["traffic_yield_deadline"]=_time+3.0
	blocker["traffic_yield_check"]=_time
	return true

func _follow_traffic_yield(p: Dictionary) -> bool:
	var requester_id := str(p.get("traffic_yield_for",""))
	if requester_id.is_empty():return false
	var requester: Dictionary = _players[_ids[requester_id]] if _ids.has(requester_id) else {}
	var original: Vector2 = p.get("traffic_yield_start",p["pos"])
	var cleared: bool = requester.is_empty() or not requester["alive"]
	if not cleared:
		var spacing := Vector2(requester["pos"]).distance_to(original)
		cleared=(requester["path"].is_empty() and spacing>PLAYER_RADIUS*2+.3) or (spacing>PLAYER_RADIUS*2+5 and not _blocks_traffic(original,requester["pos"],requester["path"]))
	if cleared or _time>float(p.get("traffic_yield_deadline",0.0)):
		# Rejoin the still-pending route, not a distant opening-route bank.
		# This preserves tactical ingress/queued orders and avoids reversing
		# traffic just because a short local yield moved off its cached chain.
		var remaining: Array = p["path"].duplicate()
		var next: Vector2 = remaining[0] if not remaining.is_empty() else p["goal"]
		var rejoin: Array = _nav.find_path(p["pos"],next,PLAYER_RADIUS,p["side"])
		# Never append an unproven suffix after a failed directed rejoin.
		if rejoin.is_empty() and Vector2(p["pos"]).distance_to(next)>.05:return true
		p["traffic_yield_for"]=""
		p["traffic_yield_path"]=[]
		p.erase("traffic_active_target")
		if not remaining.is_empty():rejoin.append_array(remaining.slice(1))
		p["path"]=rejoin
		p["travel_best"]=INF
		p["travel_since"]=_time
		return false
	var path: Array = p.get("traffic_yield_path",[])
	while not path.is_empty() and Vector2(p["pos"]).distance_to(path[0])<.05:path.pop_front()
	if path.is_empty():return true
	var goal: Vector2 = path[0]
	p["traffic_active_target"]=goal
	var direction := goal-Vector2(p["pos"])
	_move_player(p,direction.normalized()*minf(direction.length(),MOVE_SPEED*FIXED_DT))
	if not p["moving"] and _time-float(p.get("traffic_yield_check",_time))>.3:
		_request_traffic_clearance(p,path)
		p["traffic_yield_check"]=_time
	return true

func _remember_passage(p: Dictionary) -> void:
	var history: Array = p.get("passed_route", [])
	if history.is_empty() or Vector2(history[-1]).distance_to(p["pos"]) > 3.0:
		history.append(p["pos"])
		if history.size() > 20: history.pop_front()
	p["passed_route"] = history


func _fire(p: Dictionary) -> void:
	if not p["alive"] or float(p["cooldown"]) > 0.000001 or float(p["reloading"]) > 0.0 or float(p["utility_cooldown"]) > 0.8:
		return
	if p["ammo"] <= 0:
		_reload(p)
		return
	p["ammo"] -= 1
	p["shots"] += 1
	p["burst"] += 1
	var weapon: Dictionary = WEAPONS[p["weapon"]]
	p["cooldown"] = maxf(0.0, float(p["cooldown"]) + 1.0 / float(weapon["rate"]))
	_sync_weapon(p)
	var origin: Vector2 = p["pos"]
	var direction := Vector2.from_angle(float(p["yaw"]))
	var end := _ray_end(origin, direction, float(weapon["range"]))
	var found: Dictionary = {}
	var nearest := origin.distance_to(end)
	for enemy in _players:
		if not enemy["alive"] or enemy["team"] == p["team"]:
			continue
		var offset: Vector2 = Vector2(enemy["pos"]) - origin
		var along := offset.dot(direction)
		var cross_distance := absf(offset.cross(direction))
		if cross_distance > PLAYER_RADIUS: continue
		# Hit the actor's near circular surface, not its centre. At a NAV/pixel
		# corner the visible centre can coincide with the ray's wall boundary;
		# comparing only centres made every shot miss one direction forever.
		var half_chord := sqrt(maxf(0.0, PLAYER_RADIUS * PLAYER_RADIUS - cross_distance * cross_distance))
		var entry := maxf(0.0, along - half_chord)
		if along > 0.0 and entry <= nearest and not _nav.segment_blocked(origin, enemy["pos"], 0.0):
			nearest = entry
			found = enemy
	var hit := false
	var damage := 0
	if not found.is_empty():
		var aim_skill := 90.0 if p["human"] and _human_control else float(p["skills"]["aim"])
		var recoil_skill := float(p["skills"]["recoil"])
		var chance := clampf(float(weapon["accuracy"]) - (100.0 - aim_skill) * 0.002 - nearest / 6000.0 - maxi(0, int(p["burst"]) - 3) * (100.0 - recoil_skill) * 0.0005, 0.20, 0.99)
		if p["moving"]:
			chance *= lerpf(float(weapon["moving_accuracy"]), 0.82, 0.55) if p["walking"] else float(weapon["moving_accuracy"])
		if float(p["flash_remaining"]) > 0.15:
			chance *= 0.15
		hit = _rng.randf() < chance
		if hit:
			damage = mini(int(found["hp"]), int(weapon["damage"]))
			p["hits"] += 1
			p["damage"] += damage
			p["round_damage"] += damage
			found["hp"] -= damage
			found["damagers"][p["id"]] = int(found["damagers"].get(p["id"], 0)) + damage
			end = found["pos"]
	_emit("shot", {"id": p["id"], "from": origin, "to": end, "hit": hit,
		"target_id": found.get("id", "") if hit else "", "damage": damage, "weapon": p["weapon"]})
	if hit and found["hp"] <= 0:
		_kill(p, found)


func _ray_end(origin: Vector2, direction: Vector2, distance: float = FIRE_RANGE) -> Vector2:
	var endpoint := origin + direction * distance
	if _nav.has_method("raycast_endpoint"):
		return _nav.raycast_endpoint(origin, endpoint, 0.0)
	if not _nav.segment_blocked(origin, endpoint, 0.0):
		return endpoint
	var low := 0.0
	var high := distance
	for _iteration in range(14):
		var middle := (low + high) * 0.5
		if _nav.segment_blocked(origin, origin + direction * middle, 0.0):
			high = middle
		else:
			low = middle
	return origin + direction * low


func _kill(killer: Dictionary, victim: Dictionary) -> void:
	if not victim["alive"] or killer["team"] == victim["team"]:
		return
	if not str(victim.get("route_via", "")).is_empty():
		_emit("route_via_cancelled", {"id":victim["id"],"via":victim["route_via"],
			"reason":"killed","killer_id":killer["id"],"task":victim["task"],
			"bomb_state":_bomb["state"],"pos":victim["pos"],"point":victim["route_via_pos"]})
	victim["alive"] = false
	victim["hp"] = 0
	victim["d"] += 1
	victim["last_death"] = {"killer_id": killer["id"], "at": _time}
	killer["k"] += 1
	killer["round_k"] += 1
	killer["money"] = mini(16000, int(killer["money"]) + int(WEAPONS[killer["weapon"]]["kill_reward"]))
	for pid in victim["damagers"]:
		if pid != killer["id"] and int(victim["damagers"][pid]) >= 40 and _ids.has(pid):
			var assister: Dictionary = _players[_ids[pid]]
			assister["a"] += 1
			assister["round_a"] += 1
	# A dead teammate is traded only when their actual killer dies within 5s.
	for teammate in _players:
		var death: Dictionary = teammate["last_death"]
		if teammate["team"] == killer["team"] and not death.is_empty() and death.get("killer_id") == victim["id"] and _time - float(death["at"]) <= 5.0:
			teammate["round_traded"] = true
	if not _opening_recorded:
		_opening_recorded = true
		killer["opening_kills"] += 1
		victim["opening_deaths"] += 1
		killer["round_opening_kills"] = 1
		victim["round_opening_deaths"] = 1
	if _bomb["state"] == "carried" and _bomb["carrier_id"] == victim["id"]:
		_bomb.merge({"state": "dropped", "carrier_id": "", "pos": victim["pos"], "actor_id": "", "progress": 0.0}, true)
		_emit("bomb_drop", {"id": victim["id"], "pos": victim["pos"]})
	_emit("kill", {"killer_id": killer["id"], "victim_id": victim["id"], "pos": victim["pos"], "weapon": killer["weapon"]})


func _reload(p: Dictionary) -> void:
	if p["ammo"] >= int(WEAPONS[p["weapon"]]["magazine"]) or int(p["reserve"]) <= 0 or float(p["reloading"]) > 0.0:
		return
	p["reloading"] = float(WEAPONS[p["weapon"]]["reload"])
	p["reload_pending"] = true
	_emit("reload", {"id": p["id"], "weapon": p["weapon"]})


func _sync_weapon(p: Dictionary) -> void:
	p["inventory"][p["weapon"]] = {"ammo": int(p["ammo"]), "reserve": int(p["reserve"])}


func _switch_weapon(p: Dictionary, selection: String) -> bool:
	var weapon := str(p["primary_weapon"]) if selection == "primary" else "pistol" if selection == "pistol" else ""
	if weapon.is_empty() or not p["inventory"].has(weapon) or weapon == p["weapon"]:
		return false
	_sync_weapon(p)
	p["weapon"] = weapon
	p["ammo"] = int(p["inventory"][weapon]["ammo"])
	p["reserve"] = int(p["inventory"][weapon]["reserve"])
	p["reloading"] = 0.0
	p["reload_pending"] = false
	p["cooldown"] = maxf(float(p["cooldown"]), 0.25)
	p["burst"] = 0
	_emit("weapon_switch", {"id": p["id"], "weapon": weapon})
	return true


func _buy_loadout(p: Dictionary, retained: bool) -> void:
	var desired := "awp" if p["role"] == "awp" else "m4" if p["side"] == "ct" else "ak"
	var primary := str(p["primary_weapon"]) if retained else ""
	var spent := 0
	if primary.is_empty() and int(p["money"]) >= int(WEAPONS[desired]["price"]):
		primary = desired
		spent += int(WEAPONS[desired]["price"])
	elif not primary.is_empty():
		spent += mini(200, int(p["money"])) # Surviving guns are kept; fresh ammo is paid for.
	p["money"] -= spent
	p["inventory"] = {"pistol": {"ammo": 20, "reserve": 60}}
	if not primary.is_empty():
		p["inventory"][primary] = {"ammo": WEAPONS[primary]["magazine"], "reserve": WEAPONS[primary]["reserve"]}
	p["primary_weapon"] = primary
	p["weapon"] = primary if not primary.is_empty() else "pistol"
	p["ammo"] = int(p["inventory"][p["weapon"]]["ammo"])
	p["reserve"] = int(p["inventory"][p["weapon"]]["reserve"])
	p["has_kit"] = p["side"] == "ct" and int(p["index"]) < 2 and int(p["money"]) >= 400
	if p["has_kit"]:
		p["money"] -= 400
	p["smokes"] = 1 if int(p["money"]) >= 300 else 0
	p["money"] -= int(p["smokes"]) * 300
	p["flashes"] = 1 if int(p["money"]) >= 200 else 0
	p["money"] -= int(p["flashes"]) * 200


func _throw_utility(p: Dictionary, kind: String, target: Vector2) -> bool:
	var stock := "smokes" if kind == "smoke" else "flashes" if kind == "flash" else ""
	if stock.is_empty() or not target.is_finite() or not p["alive"] or int(p[stock]) <= 0 or float(p["utility_cooldown"]) > 0.0 or float(p["reloading"]) > 0.0:
		return false
	var origin: Vector2 = p["pos"]
	var offset := target - origin
	if not (p["human"] and _human_control):
		var error := (100.0 - float(p["skills"]["utility"])) * 0.08
		offset += Vector2(_rng.randf_range(-error, error), _rng.randf_range(-error, error))
	if offset.length_squared() < 0.1:
		offset = Vector2.from_angle(float(p["yaw"])) * 10.0
	var endpoint := _ray_end(origin, offset.normalized(), minf(offset.length(), UTILITY_RANGE))
	p[stock] -= 1
	p["utility_cooldown"] = 1.0
	_utility_serial += 1
	var row := {"id": _utility_serial, "owner_id": p["id"], "team": p["team"], "kind": kind,
		"state": "flying", "from": origin, "to": endpoint, "pos": origin,
		"age": 0.0, "flight_seconds": 0.55, "remaining": SMOKE_SECONDS if kind == "smoke" else 0.12,
		"radius": SMOKE_RADIUS if kind == "smoke" else FLASH_RADIUS}
	_utilities.append(row)
	_emit("utility_throw", {"id": p["id"], "utility_id": _utility_serial, "kind": kind, "from": origin, "to": endpoint, "pos": origin})
	return true


func _update_utilities() -> void:
	for index in range(_utilities.size() - 1, -1, -1):
		var row: Dictionary = _utilities[index]
		if row["state"] == "flying":
			row["age"] += FIXED_DT
			row["pos"] = Vector2(row["from"]).lerp(row["to"], minf(1.0, float(row["age"]) / float(row["flight_seconds"])))
			if float(row["age"]) + 0.000001 >= float(row["flight_seconds"]):
				row["state"] = "active"
				row["pos"] = row["to"]
				_emit("utility_deployed", {"kind": row["kind"], "utility_id": row["id"], "pos": row["pos"], "radius": row["radius"]})
				if row["kind"] == "flash":
					_detonate_flash(row)
		else:
			row["remaining"] -= FIXED_DT
			if float(row["remaining"]) <= 0.000001:
				_emit("utility_expire", {"utility_id": row["id"], "kind": row["kind"], "pos": row["pos"]})
				_utilities.remove_at(index)


func _detonate_flash(row: Dictionary) -> void:
	for p in _players:
		if not p["alive"]:
			continue
		var to_flash: Vector2 = Vector2(row["pos"]) - Vector2(p["pos"])
		if to_flash.length() > FLASH_RADIUS or vision_blocked(p["pos"], row["pos"]):
			continue
		var facing := maxf(0.0, Vector2.from_angle(float(p["yaw"])).dot(to_flash.normalized()))
		var duration := lerpf(0.45, 2.8, facing) * (1.0 - 0.6 * to_flash.length() / FLASH_RADIUS)
		p["flash_remaining"] = maxf(float(p["flash_remaining"]), duration)
		p["seen_target"] = ""
		p["visible_enemy_ids"] = []
		_emit("flash", {"id": p["id"], "owner_id": row["owner_id"], "duration": duration, "pos": row["pos"]})


func _update_bomb(interactions: Array[Dictionary]) -> void:
	if _bomb["state"] == "carried" and _ids.has(_bomb["carrier_id"]):
		_bomb["pos"] = _players[_ids[_bomb["carrier_id"]]]["pos"]
	elif _bomb["state"] == "dropped":
		for p in _players:
			if p["alive"] and p["side"] == "t" and Vector2(p["pos"]).distance_to(_bomb["pos"]) < 20.0:
				_bomb.merge({"state": "carried", "carrier_id": p["id"], "pos": p["pos"]}, true)
				if not (p["human"] and _human_control) and p["task"] not in ["save", "hold"]:
					_order_player(p, str(p.get("order", "attack_a")), int(p["index"]))
				_emit("bomb_pickup", {"id": p["id"]})
				break
	var acting: Dictionary = {}
	var action := ""
	for p in interactions:
		if not p["alive"] or p["moving"]:
			continue
		if _bomb["state"] == "carried" and _bomb["carrier_id"] == p["id"] and not _site_at(p["pos"]).is_empty():
			acting = p
			action = "plant"
			break
		if _bomb["state"] == "planted" and p["side"] == "ct" and Vector2(p["pos"]).distance_to(_bomb["pos"]) < 23.0 and not _nav.segment_blocked(p["pos"], _bomb["pos"], 0.0):
			if acting.is_empty() or p["id"] == _bomb["actor_id"]:
				acting = p
				action = "defuse"
	if acting.is_empty():
		if not str(_bomb["actor_id"]).is_empty():
			_emit("interaction_cancel", {"id": _bomb["actor_id"], "action": _bomb["action"]})
		_bomb.merge({"actor_id": "", "progress": 0.0, "action": ""}, true)
	else:
		if _bomb["actor_id"] != acting["id"] or _bomb["action"] != action:
			_bomb.merge({"actor_id": acting["id"], "action": action, "progress": 0.0}, true)
			_emit("interaction_start", {"id": acting["id"], "action": action})
		_bomb["progress"] += FIXED_DT
		var required := PLANT_SECONDS if action == "plant" else KIT_SECONDS if acting["has_kit"] else DEFUSE_SECONDS
		if float(_bomb["progress"]) + 0.000001 >= required:
			if action == "plant":
				acting["plants"] += 1
				acting["money"] = mini(16000, int(acting["money"]) + 300)
				_bomb.merge({"state": "planted", "carrier_id": "", "planter_id": acting["id"],
					"site": _site_at(acting["pos"]), "pos": acting["pos"], "remaining": BOMB_SECONDS,
					"progress": 0.0, "actor_id": "", "action": ""}, true)
				_emit("bomb_planted", {"id": acting["id"], "site": _bomb["site"], "pos": _bomb["pos"]})
				return # A newly planted bomb starts with the full 40 seconds.
			else:
				acting["defuses"] += 1
				_bomb["state"] = "defused"
				_emit("bomb_defused", {"id": acting["id"]})
				_end_round("ct", "炸弹已拆除")
				return
	if _bomb["state"] == "planted":
		_bomb["remaining"] = maxf(0.0, float(_bomb["remaining"]) - FIXED_DT)
		if float(_bomb["remaining"]) <= 0.000001:
			_bomb["state"] = "exploded"
			_emit("bomb_exploded", {"pos": _bomb["pos"]})
			_end_round("t", "炸弹爆炸")


func _end_round(side: String, reason: String) -> void:
	if _phase != "live":
		return
	var team := "ct" if _team_sides["ct"] == side else "t"
	_score[team] += 1
	var loser := "t" if team == "ct" else "ct"
	_loss_streak[team] = 0
	_loss_streak[loser] = mini(5, int(_loss_streak[loser]) + 1)
	var statistics: Array[Dictionary] = []
	for p in _players:
		var reward := 3250 if p["team"] == team else mini(3400, 1400 + maxi(0, int(_loss_streak[loser]) - 1) * 500)
		p["money"] = mini(16000, int(p["money"]) + reward)
		var survived: bool = p["alive"]
		if survived:
			p["survived_rounds"] += 1
		var kast: bool = p["round_k"] > 0 or p["round_a"] > 0 or survived or p["round_traded"]
		if kast:
			p["kast_rounds"] += 1
		statistics.append({"id": p["id"], "name": p["name"], "team": p["team"], "side": p["side"],
			"k": p["round_k"], "d": 0 if survived else 1, "a": p["round_a"], "damage": p["round_damage"],
			"opening_kills": p.get("round_opening_kills", 0), "opening_deaths": p.get("round_opening_deaths", 0),
			"survived": survived, "kast": kast, "traded": p["round_traded"], "weapon": p["weapon"], "money": p["money"]})
	_emit("round_end", {"winner": team, "winner_side": side, "reason": reason, "score": _score.duplicate()})
	_history.append({"round": _round, "winner": team, "winner_side": side, "reason": reason,
		"score": _score.duplicate(), "duration": ROUND_SECONDS - _round_time,
		"bomb": _bomb.duplicate(true), "players": statistics, "events": _round_events.duplicate(true)})
	_phase = "round_end"
	_phase_time = RESULT_SECONDS
	_message = "%s 赢得第 %d 回合：%s" % [team.to_upper(), _round, reason]


func _match_decided() -> bool:
	if _round < 24: return _score["ct"] >= 13 or _score["t"] >= 13
	if not _allow_overtime: return true
	if _round == 24: return _score["ct"] != _score["t"]
	var overtime_block := floori(float(_round - 25) / 6.0)
	var needed := 16 + overtime_block * 3
	return _score["ct"] >= needed or _score["t"] >= needed


func _finish_match() -> void:
	_phase = "finished"
	_winner = "draw" if _score["ct"] == _score["t"] else "ct" if _score["ct"] > _score["t"] else "t"
	_message = "比赛结束 · %d:%d · %s%s" % [_score["ct"], _score["t"], "平局" if _winner == "draw" else _winner.to_upper() + " 获胜", "" if _allow_overtime else "（样本无加时）"]
	_emit("match_end", {"winner": _winner, "score": _score.duplicate()})


func _emit(kind: String, data: Dictionary) -> void:
	var event: Dictionary = {"type": kind, "tick": _tick, "time": _time, "round": _round}
	event.merge(data, true)
	_events.append(event)
	_round_events.append(event)
	if _events.size() > 2048:
		_events.pop_front()


func _alive_side(side: String) -> int:
	var count := 0
	for p in _players:
		if p["side"] == side and p["alive"]:
			count += 1
	return count


func _closest_side_to_bomb(side: String) -> String:
	var found := ""
	var closest := INF
	for p in _players:
		if p["alive"] and p["side"] == side:
			if p["task"] in ["save", "hold"]:
				continue
			var distance := Vector2(p["pos"]).distance_squared_to(_bomb["pos"])
			if distance < closest:
				closest = distance
				found = p["id"]
	return found


func _spawn(side: String, index: int) -> Vector2:
	var points: Array = _map.get("spawns", {}).get(side, [])
	var point := _vector(points[index % points.size()]) if not points.is_empty() else Vector2(100, 100)
	return _nav.nearest_walkable(point, PLAYER_RADIUS)


func _vector(value) -> Vector2:
	if value is Vector2:
		return value
	return Vector2(float(value[0]), float(value[1]))


func _target(key: String) -> Vector2:
	if _map.get("tactical_targets", {}).has(key):
		return _nav.nearest_walkable(_vector(_map["tactical_targets"][key]), PLAYER_RADIUS)
	for row in _map.get("waypoints", []):
		if str(row["id"]) == key:
			return _nav.nearest_walkable(_vector(row["position"]), PLAYER_RADIUS)
	var site := key.trim_suffix("_site")
	if _map.get("sites", {}).has(site):
		return _nav.nearest_walkable(_vector(_map["sites"][site]["center"]), PLAYER_RADIUS)
	return _spawn("ct", 0)


func _site_at(point: Vector2) -> String:
	for key in ["A", "B"]:
		var row: Dictionary = _map.get("sites", {}).get(key, {})
		if not row.is_empty() and point.distance_to(_vector(row["center"])) <= float(row.get("radius", 50)):
			return key
	return ""


func _set_goal(p: Dictionary, point: Vector2, task: String, via: String = "", repath: bool = false) -> void:
	var previous_via := str(p.get("route_via", ""))
	if not previous_via.is_empty() and previous_via != via:
		var reason := "reassigned"
		if _bomb.get("state", "") == "planted" and task in ["defuse","guard bomb","cover defuser"]:
			reason = "bomb_planted"
		elif _bomb.get("state", "") == "dropped" and task == "recover bomb":
			reason = "bomb_dropped"
		_emit("route_via_cancelled", {"id":p["id"],"via":previous_via,"reason":reason,
			"task":task,"bomb_state":_bomb.get("state", ""),"site":_bomb.get("site", ""),
			"pos":p["pos"],"point":p["route_via_pos"]})
	var goal: Vector2 = _nav.nearest_walkable(point, PLAYER_RADIUS)
	var path: Array = []
	var intermediate := goal
	var ingress: Array = []
	if not via.is_empty():
		if repath:
			ingress = p.get("route_ingress", []).duplicate(true)
		elif via == "A_long":
			# A long execute must actually enter long doors, not take the
			# shortest path up short and walk backward into the long region.
			for key in ["region_OutsideLong", "region_LongDoors"]:
				if _map.get("waypoints", []).any(func(row): return str(row.get("id", "")) == key):
					ingress.append({"id": key, "pos": _target(key)})
		var leg_start: Vector2 = p["pos"]
		for entry in ingress:
			path.append_array(_route_path(leg_start, entry["pos"], p["side"]))
			leg_start = entry["pos"]
		intermediate = _target(via)
		path.append_array(_route_path(leg_start, intermediate, p["side"]))
		path.append_array(_route_path(intermediate, goal, p["side"]))
	else:
		# RTS point moves/repaths must stay local. Opening-route templates
		# belong to tactical orders and can otherwise reverse a door queue.
		path = _nav.find_path(p["pos"], goal, PLAYER_RADIUS, p["side"]) if task == "move" else _route_path(p["pos"], goal, p["side"])
	p["goal"] = goal
	p["path"] = path
	p["task"] = task
	p["route_via"] = via
	p["route_via_pos"] = intermediate
	p["route_ingress"] = ingress
	if not repath:
		p["travel_mark"] = p["pos"]
		p["travel_since"] = _time
		p["passed_route"] = [p["pos"]]
		p["travel_best"]=INF
		p["traffic_center"]=point
		p["traffic_direction"]=(point-Vector2(p["pos"])).normalized()
		p["traffic_yield_for"]=""
		p["traffic_yield_path"]=[]
		p.erase("traffic_active_target")


func _order_player(p: Dictionary, order: String, index: int) -> void:
	p["queued_goals"] = []
	p["queued_traffic"] = []
	p["traffic_yield_for"]=""
	p["traffic_yield_path"]=[]
	p.erase("traffic_active_target")
	p["order"] = order
	if order == "hold":
		p["path"] = []
		p["goal"] = p["pos"]
		p["task"] = "hold"
		p["route_via"] = ""
		p["route_ingress"] = []
		return
	var via := ""
	var target: Vector2 = p["pos"]
	var task := order
	match order:
		"default":
			if p["side"] == "t":
				_order_player(p, "split_a" if _round % 3 != 0 else "split_b", index)
				return
			else:
				var post := "A_site" if index < 2 else "B_site" if index < 4 else "CT_connector"
				target = _target(post)
				task = "defend " + post
		"attack_a", "attack_a_long":
			target = _target("A_site")
			via = "A_long"
		"attack_a_short":
			target = _target("A_site")
			via = "A_short"
		"attack_b":
			target = _target("B_site")
			via = "B_tunnel"
		"split_a":
			target = _target("A_site")
			via = "A_long" if index < 3 else "A_short"
			task += " " + via
		"split_b":
			target = _target("B_site")
			via = "B_tunnel" if index < 3 else "B_door"
			task += " " + via
		"retake_a":
			target = _target("A_site")
			via = "CT_connector"
		"retake_b":
			target = _target("B_site")
			via = "B_door"
		"save":
			target = _spawn(str(p["side"]), int(p["index"]))
	if order not in ["hold", "save"]:
		var offset := Vector2.from_angle(float(index) * TAU / 5.0) * 24.0
		target = _nav.nearest_walkable(target + offset, PLAYER_RADIUS)
	_set_goal(p, target, task, via)


func _rating(p: Dictionary, rounds: int) -> float:
	var n := float(maxi(1, rounds))
	var kpr := float(p["k"]) / n
	var survival := 1.0 - minf(float(p["d"]) / n, 1.0)
	var apr := float(p["a"]) / n
	var adr := float(p["damage"]) / n
	var kast := clampf(float(p["kast_rounds"]) / n, 0.0, 1.0)
	var raw := 0.35 * kpr / 0.67 + 0.15 * survival / 0.33 + 0.10 * apr / 0.20 + 0.20 * adr / 74.0 + 0.20 * kast / 0.72
	return snappedf(clampf(raw, 0.20, 2.50), 0.01)
