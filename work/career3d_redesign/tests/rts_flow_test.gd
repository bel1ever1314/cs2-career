extends SceneTree
## --no-service is required: this test never creates/persists a Career.
var failures: Array[String] = []
var checks := 0

func check(value: bool, message: String) -> void:
	checks += 1
	if not value: failures.append(message)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	root.size = Vector2i(1280,720)
	root.content_scale_size = Vector2i(1280,720)
	await process_frame
	var bridge = root.get_node("CareerBridge")
	var host = root.get_node("Computer")
	bridge.connected = true
	bridge.busy = false
	var cards: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://rts/data/rosters.json"))
	var room := {"id":"test-rts", "mode":"custom", "phase":"ready", "map":"dust2", "ct":"a", "a":[], "b":[], "roster":{}}
	for side in ["ct","t"]:
		for player in cards[side]:
			room["a" if side == "ct" else "b"].append(player["id"])
			room["roster"][player["id"]] = player
	bridge.context = {"custom":{"lobby":room,"rts_rosters":cards}}
	var before = bridge.context.duplicate(true)
	for phase in ["ready", "starting", "launched", "finished"]:
		room["phase"] = phase
		check(bridge._has_pending_match() == (phase in ["starting", "launched"]), "custom CS2 clock lock: " + phase)
	room["phase"] = "ready"
	host.screen.show()
	host._navigate("rts")
	check(host.rts_render.is_valid(), "RTS page has actual module")
	check(host.rts_room.eligible(), "custom ten-player roster accepted")
	host.rts_room.start_session()
	await process_frame
	await process_frame
	var game = host.rts_room.session
	check(is_instance_valid(game), "full-screen command match opens")
	if is_instance_valid(game):
		game.set_process(false)
		check(game.mode == "command" and game.viewer_team == "ct", "correct team commanded from lobby CT assignment")
		check(game.state.get("players", []).size() == 10, "all ten custom players loaded")
		check(host.screen.visible and game.visible and host.get_child(-1) == game, "simulation covers computer without releasing device lock")
		var ids: Array = [cards["ct"][0]["id"],cards["ct"][1]["id"]]
		game._select_units(ids)
		game.issue_order("hold")
		check(game.selected_ids.size() == 2, "group selection connected to actual game")
		check(game.sim._players[game.sim._ids[ids[0]]]["task"] == "hold", "individual task executes")
		check(game.keyboard_hint.get_global_rect().end.y <= 721, "commander help fits 720px")
		check(game.renderer.get_global_rect().end.y <= 721, "map fits 720px")
		if DisplayServer.get_name() != "headless":
			await process_frame
			root.get_texture().get_image().save_png("D:/CS2CareerBuilds/rts-1280.png")
		host.rts_room.close_session()
		await process_frame
	check(host.screen.visible and host.rts_room.session == null, "return restores computer and releases simulation")
	check(bridge.context == before and not bridge.busy, "RTS never posts or changes career/lobby context")
	room["map"] = "nuke"
	check(not host.rts_room.eligible(), "unsupported map cannot impersonate Dust2")
	room["map"] = "dust2"; room["phase"] = "launched"
	check(not host.rts_room.eligible(), "pending CS2 room not reused as a fresh simulation")
	print(JSON.stringify({"suite":"3d_rts_flow", "checks":checks, "failures":failures}))
	quit(0 if failures.is_empty() else 1)
