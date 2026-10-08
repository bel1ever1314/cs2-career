extends "res://tests/match_map_clarity_test.gd"
## Disposable UI fixtures; no backend, save or CS2 writes.

func frames() -> void:
	for i in range(5): await get_tree().process_frame

func capture(name: String) -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture-output="):
			await RenderingServer.frame_post_draw
			var folder := arg.trim_prefix("--capture-output=")
			DirAccess.make_dir_recursive_absolute(folder)
			get_viewport().get_texture().get_image().save_png(folder.path_join(name + ".png"))

func performance() -> Array:
	return [{"map":"mirage", "rating":86.5, "strength":85.0, "form":1.5, "label":"strong", "played":3, "wins":2,
		"recent":[{"won":true},{"won":false},{"won":true}], "last_change":{"team":"Vitality", "map":"mirage", "delta":0.8, "after":86.5, "reason":"训练赛获胜", "strength_delta":0.12, "form_delta":0.68}},
		{"map":"nuke", "rating":43.0, "strength":45.0, "form":-2.0, "label":"weak", "played":0, "wins":0, "recent":[]}]

func bounded(root: Control, caption: String) -> void:
	var end := root.get_global_rect().end.x
	var good := true
	for item in root.find_children("*", "Control", true, false):
		if item.is_visible_in_tree() and item.get_global_rect().end.x > end + 2: good = false
	check(good, caption)

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(2); return
	Locale.set_language("zh-CN", false)
	CareerBridge.connected = true; CareerBridge.clock_held = true
	CareerBridge.set_process(false); Computer.set_process(false); Phone.set_process(false)
	scene_file_path = "res://lan.tscn"
	center = Computer.match_center
	center.command_sender = send_fixture
	for resolution in [Vector2i(1280,720), Vector2i(1920,1080)]:
		get_window().size = resolution
		get_viewport().size = resolution
		reset(fixture(false))
		CareerBridge.context["media"] = {"map_backgrounds":{"train":"E:/CS2CareerTools/Career3DMedia/maps/de_train.png", "mirage":"E:/CS2CareerTools/Career3DMedia/maps/de_mirage.png", "nuke":"E:/CS2CareerTools/Career3DMedia/maps/de_nuke.png"}}
		Computer._finished("/api/3d/match/status?id=clarity-match", status(fixture(false), false))
		await frames()
		check(Computer.content.find_child("CareerMatchMapBackground", true, false) != null, "preflight uses scenic image " + str(resolution))
		bounded(Computer.content, "preflight stays inside monitor " + str(resolution))
		await capture("preflight-" + str(resolution.x))
		var bp := fixture(false)
		bp["pending_map"] = null; bp["series_maps"] = []
		bp["veto"] = {"complete":false, "initialized":true, "steps":[], "available":["mirage", "nuke"], "turn":{"team":"Vitality", "action":"pick", "mine":true}}
		bp["map_performance"] = {"Vitality":performance(), "The MongolZ":performance()}
		center.preflight = bp
		Computer._rebuild()
		await frames()
		var before := commands.size()
		Computer.content.find_child("VetoPreview_nuke", true, false).pressed.emit()
		await frames()
		check(commands.size() == before and center.bp_preview_map == "nuke", "preview does not submit BP")
		check(text_present("43.0") and text_present("弱图"), "preview explains both teams' map form")
		bounded(Computer.content, "BP preview stays inside monitor " + str(resolution))
		check(Computer.scroll.get_global_rect().encloses(Computer.content.find_child("ConfirmVetoMap", true, false).get_global_rect()), "BP confirmation visible without scrolling " + str(resolution))
		await capture("bp-" + str(resolution.x))
		Computer.content.find_child("ConfirmVetoMap", true, false).pressed.emit()
		check(commands.size() == before + 1 and commands[-1].body.map == "nuke", "confirmation submits selected map")
		center.request_pending = false
		Computer.controls.cache["/api/3d/controls/training"] = {"revision":18,"data":{"date":"2026-07-21", "team":"Vitality", "mentality":75, "maps":["mirage","nuke"], "map_performance":performance(), "opponents":[], "config":{"ready":false}, "personal":{}}}
		Computer.open_app("training", "club")
		await frames()
		check(Computer.content.find_child("ScheduleMapFocus", true, false) != null, "training offers daily map selection")
		check(text_present("训练赛获胜"), "training displays change reason")
		check(text_present("熟练度 +0.12 · 近期状态 +0.68"), "training distinguishes learning from recent form")
		check(text_present("每天下降 0.12"), "training explains gradual inactivity decay")
		bounded(Computer.content, "training stays inside monitor " + str(resolution))
		await capture("training-" + str(resolution.x))
	# Verify the shared RTS implementation only modifies AI reaction, not skills.
	var sim = preload("res://rts/scripts/match_sim.gd").new()
	var p := {"skills":{"reaction":80}, "map_reaction":0.95}
	var fast: float = sim.reaction_seconds(p)
	p.map_reaction = 1.0
	check(is_equal_approx(fast / sim.reaction_seconds(p), 0.95), "RTS familiarity multiplier is five percent")
	print("MAP_FORM_UI_RESULT checks=", checks, " failures=", failures)
	get_tree().quit(0 if failures.is_empty() else 1)
