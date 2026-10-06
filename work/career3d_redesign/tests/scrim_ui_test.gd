extends Node
var checks := 0
var failures: Array[String] = []

func _ready() -> void: call_deferred("run")
func before_computer() -> void: pass
func set_device_open(_opened: bool, _kind: String) -> void: pass

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("SCRIM_UI ", "PASS " if ok else "FAIL ", label)

func frames(count: int = 12) -> void:
	for i in range(count): await get_tree().process_frame

func report_fixture() -> Dictionary:
	var players := {"Falcons":[], "FURIA":[]}
	for i in range(10):
		players["Falcons" if i < 5 else "FURIA"].append({"player_id":"fixture-%d" % i, "name":["kyousuke","m0NESY","TeSeS","karrigan","NiKo","molodoy","YEKINDAR","yuurih","KSCERATO","FalleN"][i], "k":14+i, "d":5+i, "a":3, "rating":1.32, "adr":96.4,"kast":.81})
	return {"id":"practice-fixture","date":"2026-01-08","teams":["Falcons","FURIA"],"human_id":"fixture-1","map":{"map":"dust2","score":"13-3","winner":"Falcons","players":players}}

func queued(button: Button) -> Dictionary:
	CareerBridge.busy = true; CareerBridge.active_post = false; CareerBridge.queued_command = {}
	button.pressed.emit()
	var result: Dictionary = CareerBridge.queued_command.duplicate(true)
	CareerBridge.busy = false; CareerBridge.queued_command = {}
	return result

func capture_media() -> void:
	# Optional local art for screenshot review; headless CI needs no media pack.
	for arg in OS.get_cmdline_user_args():
		if not arg.begins_with("--media-config="): continue
		var config: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(arg.trim_prefix("--media-config=")))
		var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(str(config.team_manifest)))
		var media := {"team_backgrounds":{}, "map_backgrounds":{}}
		for team in manifest.team_backgrounds:
			media.team_backgrounds[team] = manifest.team_backgrounds[team].path
		for map_id in config.map_backgrounds:
			media.map_backgrounds[map_id] = config.map_backgrounds[map_id].path
		CareerBridge.context.media = media

func run() -> void:
	check("--no-service" in OS.get_cmdline_user_args(), "isolated UI fixture")
	CareerBridge.connected = true; CareerBridge.clock_held = true; CareerBridge.set_process(false)
	CareerBridge.context = {"date":"2026-01-08","calendar":{"revision":7},"player":{"id":"fixture-1","name":"m0NESY"},"team":{"name":"Falcons"},"scrims":{"launch_ready":true,"pending":{},"opponents":[{"id":"furia","name":"FURIA"}],"scheduled":[{"id":"booking-fixture","date":"2026-01-08","opponent":"FURIA","map":"dust2","status":"scheduled"}],"history":[]},"ladder":{"maps":["dust2","mirage"]},"media":{},"inbox":[],"stories":[]}
	capture_media()
	Computer.set_process(false)
	Computer.open_app("scrim", "club")
	await frames()
	var launch := Computer.content.find_child("ScrimLaunch_booking-fixture", true, false) as Button
	check(launch != null and not launch.disabled, "booked scrim has an enabled CS2 launch button")
	var side := Computer.content.find_child("ScrimSide_booking-fixture", true, false) as OptionButton
	side.select(1); side.item_selected.emit(1)
	var sent := queued(launch)
	check(sent.get("path") == "/api/3d/scrim/launch" and sent.get("body", {}).get("id") == "booking-fixture" and sent.get("body", {}).get("side") == "t" and sent.get("body", {}).get("revision") == 7, "launch click keeps booking, chosen side and current revision")
	CareerBridge.context.scrims.pending = {"booking_id":"booking-fixture","nonce":"session-fixture","launch_state":"dispatched"}
	CareerBridge.context.scrims.scheduled[0].status = "launched"
	Computer._rebuild(); await frames()
	var collect := Computer.content.find_child("ScrimCollect_booking-fixture", true, false) as Button
	check(collect != null, "pending booked match offers result collection")
	sent = queued(collect)
	check(sent.get("path") == "/api/3d/scrim/collect" and sent.get("body", {}).get("nonce") == "session-fixture", "collection is bound to current match session")
	for dimensions in [Vector2i(1151,822),Vector2i(1280,720),Vector2i(1920,1080),Vector2i(800,600)]:
		get_viewport().size = dimensions
		Computer._open_report(report_fixture())
		await frames(20)
		var report := Computer.content.find_child("ProfessionalMatchReport", true, false)
		check(report != null and Computer.content.get_combined_minimum_size().x <= Computer.scroll.size.x + 1, "report minimum fits monitor %s" % dimensions)
		check(report.size.x <= Computer.scroll.size.x + 1, "actual report width fits monitor %s" % dimensions)
		check(report.tables.columns == 1 or report.scoreboards[0].get_combined_minimum_size().x + report.scoreboards[1].get_combined_minimum_size().x + 14 <= report.size.x + 1, "side-by-side stats only when both tables fit %s" % dimensions)
		check(Computer.content.find_children("CareerScorePlayer_*","Button",true,false).size() == 10, "all ten rows remain available %s" % dimensions)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture="):
			get_viewport().size = Vector2i(1280,800); await frames(20)
			await RenderingServer.frame_post_draw
			get_viewport().get_texture().get_image().save_png(arg.trim_prefix("--capture="))
	Computer.close_computer()
	print("SCRIM_UI_RESULT ", JSON.stringify({"checks":checks,"failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
