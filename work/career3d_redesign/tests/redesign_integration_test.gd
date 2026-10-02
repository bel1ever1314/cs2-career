extends Node
## Real loopback service + new device scenes. Reports only in this E project.
var failures: Array[String] = []
var checks := 0
var serial := 0
var reply: Dictionary = {}

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("REDESIGN_CHECK ", "PASS " if ok else "FAIL ", label)

func idle() -> bool:
	var deadline := Time.get_ticks_msec() + 70000
	while (not CareerBridge.connected or CareerBridge.busy) and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	return CareerBridge.connected and not CareerBridge.busy

func send(path: String, body: Dictionary) -> Dictionary:
	await idle()
	var previous := serial
	check(CareerBridge.command(path, body), "accepted " + path)
	var deadline := Time.get_ticks_msec() + 70000
	while serial == previous and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	return reply.duplicate(true)

func capture(filename: String) -> void:
	await get_tree().create_timer(.3).timeout
	if DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png("res://renders/" + filename + ".png")

func run() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	reparent(CareerBridge)
	CareerBridge.command_finished.connect(func(_path, result): reply = result; serial += 1)
	check(await idle(), "Godot starts authenticated isolated service")
	if not CareerBridge.connected: finish(); return
	check(CareerBridge.context.get("isolated", false), "independent sample state")
	CareerBridge.clock_held = true
	print("PHONE_VIEWPORT ", JSON.stringify({"logical":str(get_viewport().get_visible_rect().size), "window":str(get_window().size), "final_scale":str(get_viewport().get_final_transform().get_scale()), "phone_scale":str(Phone.panel.scale)}))
	await capture("redesign_bedroom")
	for page in ["home", "mail", "chat", "match", "calendar", "profile", "settings", "news"]:
		Phone.present(page)
		await get_tree().process_frame
		check(Phone.screen.visible and CareerBridge.phone_open and Phone.active_page == page, "phone page " + page)
		await capture("redesign_phone_" + page)
	Phone.close_phone()
	check(not CareerBridge.phone_open, "phone closes and returns control")
	Computer.present("bedroom")
	await get_tree().process_frame
	check(Computer.screen.visible and CareerBridge.phone_open, "bedroom computer desktop")
	await capture("redesign_computer_bedroom")
	for app in ["battle", "events", "market", "profile", "mail", "calendar", "operations", "transfers", "news", "career_match", "quick", "settings", "tactics"]:
		Computer._navigate(app, false)
		await get_tree().process_frame
		await idle()
		await get_tree().process_frame
		check(Computer.active_page == app and Computer.content.get_combined_minimum_size().x <= Computer.scroll.size.x + 1, "real computer application fits: " + app)
		await capture("redesign_computer_" + app)
	check(not Computer.tactics.library().get("map_meta", {}).get("image_path", "").is_empty(), "meeting room editor resolves real local radar artwork")
	check(not CareerBridge.context.get("media", {}).get("map_backgrounds", {}).get("de_dust2", "").is_empty(), "match map backgrounds resolve separate local loading artwork")
	check(not CareerBridge.context.get("finance", {}).is_empty(), "management reads real original wallets")
	check(not CareerBridge.context.get("transfers", {}).is_empty(), "transfer market reads original career candidates")
	check(CareerBridge.context.get("news") is Dictionary, "published news has independent paginated read model")
	var own_id := str(CareerBridge.context.get("player", {}).get("id", ""))
	Computer._load_detail("player", own_id)
	await idle()
	await get_tree().process_frame
	check(Computer.detail.get("player_id", "") == own_id and Computer.detail.has("summary") and Computer.detail.has("honours"), "player data follows stable identity and original aggregate")
	await capture("redesign_computer_player")
	var personal: Dictionary = CareerBridge.context.get("personal", {})
	check(not personal.is_empty() and not personal.get("attributes", {}).is_empty(), "native personal controls read real career attributes")
	if personal.get("growth_allowed", false) and int(personal.get("attr_points", 0)) > 0:
		var chosen_axis := ""
		for axis in personal.get("axes", []):
			var value = personal.get("attributes", {}).get(axis)
			if value != null and float(value) < 100:
				chosen_axis = axis
				break
		if not chosen_axis.is_empty():
			var old_value := float(personal["attributes"][chosen_axis])
			var old_points := int(personal["attr_points"])
			Phone.present("profile")
			Phone._profile_tab("growth")
			check(CareerBridge.growth_adjust(chosen_axis, 1), "phone stages one real career point")
			Computer.present("bedroom")
			Computer._navigate("profile", false)
			Computer._profile_tab("growth")
			check(CareerBridge.growth_draft.get(chosen_axis, 0) == 1, "computer reads phone draft without duplicating it")
			var growth: Dictionary = await send("/api/3d/attr", {"allocations":CareerBridge.growth_draft.duplicate(), "revision":int(CareerBridge.context["calendar"]["revision"])})
			check(growth.get("ok", false) and float(CareerBridge.context["personal"]["attributes"][chosen_axis]) == old_value + 1, "real service applies ordinary career point rule")
			check(int(CareerBridge.context["personal"]["attr_points"]) == old_points - 1 and CareerBridge.growth_draft.is_empty(), "shared allocation commits once and clears both device drafts")
			await capture("redesign_computer_personal_growth")
	Computer.close_computer()
	check(not CareerBridge.phone_open, "computer closes and returns control")
	Travel.go("club")
	await Travel.arrived
	var club = get_tree().current_scene
	check(club.life.roster.size() == 8, "four real teammates plus staff")
	await capture("redesign_club")
	Computer.present("club")
	await get_tree().process_frame
	check(Computer.screen.visible, "club computer desktop")
	await capture("redesign_computer_club")
	Phone.present("home")
	check(Phone.screen.visible and not Computer.screen.visible, "phone replaces computer without two modals")
	Phone.close_phone()
	var context: Dictionary = CareerBridge.context
	var result: Dictionary = await send("/api/3d/ladder/matchmake", {"revision": int(context["ladder"]["revision"])})
	check(result.get("ok", false), "real ladder lobby")
	for index in range(30):
		var ladder: Dictionary = CareerBridge.context["ladder"]
		var lobby: Dictionary = ladder["lobby"]
		if lobby["phase"] == "ready": break
		var body: Dictionary = {"revision": int(ladder["revision"])}
		var action := "advance"
		if lobby["turn"].get("human", false):
			if lobby["phase"] == "draft":
				action = "pick"
				for pid in lobby["selection"]:
					if pid not in lobby["a"] and pid not in lobby["b"]: body["player_id"] = pid; break
			elif lobby["phase"] == "veto": action = "ban"; body["map"] = lobby["map_pool"][0]
			else: action = "side"; body["side"] = "ct"
		await send("/api/3d/ladder/" + action, body)
	var ladder: Dictionary = CareerBridge.context["ladder"]
	var lobby: Dictionary = ladder["lobby"]
	check(lobby["phase"] == "ready", "captains complete draft and veto")
	if lobby["phase"] == "ready":
		result = await send("/api/3d/ladder/simulate", {"revision": int(ladder["revision"]), "lobby_id": lobby["id"]})
		check(result.get("result", {}).get("source") == "simulated", "ten-player simulated ladder report")
	Computer.present("club")
	Computer._navigate("ladder", false)
	if result.get("result") is Dictionary: Computer._open_report(result["result"])
	await get_tree().process_frame
	await capture("redesign_computer_ladder_result")
	Computer.close_computer()
	Travel.go("major")
	await Travel.arrived
	var arena = get_tree().current_scene
	arena.finish_intro()
	check(arena.atmosphere != null, "dark arena with entrance audio")
	await capture("redesign_arena_entry")
	Travel.go("bedroom")
	await Travel.arrived
	check(get_tree().current_scene.scene_file_path == "res://bedroom.tscn", "scene travel returns to bedroom")
	finish()

func finish() -> void:
	var report := {"ok": failures.is_empty(), "checks": checks, "failures": failures}
	var output := FileAccess.open("res://temp/redesign_integration_report.json", FileAccess.WRITE)
	output.store_string(JSON.stringify(report, "  "))
	print("REDESIGN_RESULT ", JSON.stringify(report))
	CareerBridge.quit()
