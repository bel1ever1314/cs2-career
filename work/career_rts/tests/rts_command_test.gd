extends SceneTree
const Sim = preload("res://scripts/match_sim.gd")
var checks := 0
var failures: Array[String] = []

func check(value: bool, message: String) -> void:
	checks += 1
	if not value: failures.append(message)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var data = JSON.parse_string(FileAccess.get_file_as_string("res://data/dust2_game.json"))
	var rosters = JSON.parse_string(FileAccess.get_file_as_string("res://data/rosters.json"))
	rosters["human_id"] = ""
	var sim = Sim.new()
	check(sim.configure(data, rosters, 517), "ten-player initialization")
	var ids: Array = [rosters["t"][0]["id"],rosters["t"][1]["id"]]
	var first: Dictionary = sim._players[sim._ids[ids[0]]]
	var second: Dictionary = sim._players[sim._ids[ids[1]]]
	var start: Vector2 = first["pos"]
	var target: Vector2 = sim._nav.nearest_walkable(start + Vector2(0,-28),3.5)
	var ct_before = sim._players[0]["goal"]
	check(sim.command_move("t", target, ids), "multi-unit command accepted")
	check(first["task"] == "move" and second["task"] == "move", "both selected names receive movement")
	check(sim._players[0]["goal"] == ct_before, "opposing side is never redirected")
	check(first["pos"] == start, "command does not teleport")
	var old = first["goal"]
	check(not sim.command_move("t", Vector2.INF, ids), "nonfinite click refused")
	check(first["goal"] == old, "rejection preserves current task")
	check(not sim.command_move("t", Vector2(-300,-300), ids), "far blocked click is not silently snapped")
	check(not sim.command_move("t", target, [rosters["ct"][0]["id"]]), "cannot order enemy")
	var queued_target: Vector2 = sim._nav.nearest_walkable(start + Vector2(0,-48),3.5)
	check(sim.command_move("t", queued_target, [ids[0]], true), "shift command queues a second leg")
	check(first["goal"] == old and first["queued_goals"].size() == 1, "queued order does not replace active leg")
	check(sim.command("t", "hold", [ids[0]]), "selected unit can hold")
	check(first["queued_goals"].is_empty() and first["path"].is_empty(), "hold clears residual path and queue")
	check(sim.command_move("t", target, [ids[0]]), "new move after hold")
	# Isolate local movement from battles and teammate crowding; the production
	# motion and path follower still run normally, without writing positions.
	for actor in sim._players:
		if actor["id"] != ids[0]: actor["alive"] = false
	for tick in range(300): sim._follow_path(first)
	check(Vector2(first["pos"]).distance_to(first["goal"]) < .1, "ordered unit actually arrives")
	var view = load("res://main.tscn").instantiate()
	root.add_child(view)
	await process_frame
	view.set_process(false)
	view.start_match("command", "t", "")
	view.set_process(false)
	view._select_units([ids[0]], false)
	check(view.selected_ids == [ids[0]], "UI named unit selection")
	view._select_units([ids[1]], true)
	check(view.selected_ids.size() == 2, "UI shift adds teammate")
	view._select_units([ids[1]], true)
	check(view.selected_ids == [ids[0]], "UI shift toggles teammate")
	view._select_units([rosters["ct"][0]["id"]], true)
	check(view.selected_ids == [ids[0]], "UI cannot select opposing unit")
	view.queue_free()
	await process_frame
	print(JSON.stringify({"suite":"rts_commands", "checks":checks, "failures":failures}))
	quit(0 if failures.is_empty() else 1)
