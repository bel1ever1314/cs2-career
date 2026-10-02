extends SceneTree
## Real scene integration, not a synthetic screenshot or an alternate UI.
## Run: Godot --headless --path <project> --script res://tests/smoke_scene.gd
## Optional rendered run: append -- --capture=<absolute PNG path>.

const AudioCues := preload("res://scripts/audio.gd")
var failures: Array[String] = []
var checks := 0
var details: Dictionary = {}


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	details["godot"] = Engine.get_version_info().get("string", "")
	details["display"] = DisplayServer.get_name()
	await _test_audio()
	if not ResourceLoader.exists("res://main.tscn"):
		_check(false, "main scene exists")
		_finish()
		return
	var scene := load("res://main.tscn") as PackedScene
	_check(scene != null, "main scene loads")
	if scene == null:
		_finish()
		return
	var game := scene.instantiate() as Control
	_check(game != null, "main root is a Control")
	if game == null:
		_finish()
		return
	root.add_child(game)
	await process_frame
	await process_frame
	_check(game.name == "TacticalGame", "main scene has the expected root")
	_check(game.get("_ready_ok") == true, "main scene resources and UI are ready")
	var menu := game.find_child("MainMenu", true, false) as Control
	var match_view := game.find_child("MatchView", true, false) as Control
	var start := game.find_child("StartMatchButton", true, false) as Button
	_check(menu != null and menu.visible, "initial scene opens the menu")
	_check(match_view != null and not match_view.visible, "match is not silently running under menu")
	_check(start != null and not start.get_signal_connection_list("pressed").is_empty(), "start button has a real route")
	_check(game.find_child("MapView", true, false) != null, "map renderer is in the real UI")
	for method in ["start_match", "open_scoreboard", "issue_order", "go_menu"]:
		_check(game.has_method(method), "game API: " + method)
	if not game.has_method("start_match") or game.get("_ready_ok") != true:
		game.queue_free()
		await process_frame
		_finish()
		return
	game.call("start_match", "spectate", "t", "")
	await process_frame
	var simulation = game.get("sim")
	_check(simulation != null and simulation.has_method("snapshot"), "spectator match creates the shared engine")
	_check(match_view != null and match_view.visible and menu != null and not menu.visible, "match and menu visibility handoff")
	if simulation != null and simulation.has_method("snapshot"):
		var before: Dictionary = simulation.snapshot()
		_check(before.get("players", []).size() == 10, "match contains ten roster players")
		_check(str(before.get("human_id", "")).is_empty(), "spectator does not steal a human slot")
		var ids: Dictionary = {}
		for player: Dictionary in before.get("players", []):
			ids[str(player.get("id", ""))] = true
			_check(not str(player.get("name", "")).is_empty(), "roster player name is present")
			var point = player.get("pos", Vector2.INF)
			_check(point is Vector2 and point.is_finite(), "player has a finite map position")
		_check(ids.size() == 10 and not ids.has(""), "all ten player identities are distinct")
		game.set_process(false)
		game.set_physics_process(false)
		for tick in range(180):
			simulation.step(1.0 / 60.0)
		var after: Dictionary = simulation.snapshot()
		_check(int(after.get("tick", 0)) >= int(before.get("tick", 0)) + 180, "real fixed-tick engine advances after startup")
		_check(str(after.get("phase", "")) == "live", "freeze transitions into a playable live round")
		details["round"] = after.get("round", 0)
		details["tick"] = after.get("tick", 0)
		game.call("issue_order", "attack_b")
		_check(simulation.snapshot().get("players", []).size() == 10, "tactic route keeps the same match roster")
	game.call("open_scoreboard")
	await process_frame
	var scoreboard := game.find_child("ScoreboardOverlay", true, false) as Control
	_check(scoreboard != null and scoreboard.visible, "scoreboard opens through the real game API")
	await _capture_if_requested()
	game.call("go_menu")
	await process_frame
	_check(menu != null and menu.visible, "return-to-menu route works")
	_check(match_view != null and not match_view.visible, "return-to-menu hides gameplay")
	# Exercise the actual Button signal, not merely its direct public method.
	if start != null:
		start.emit_signal("pressed")
		await process_frame
		await process_frame
		_check(match_view != null and match_view.visible, "start button signal starts a playable match")
		_check(not start.disabled and start.text == "开始对局", "asynchronous start finishes before scene teardown")
	game.audio.muted = true
	await create_timer(0.06).timeout
	game.queue_free()
	await process_frame
	await process_frame
	_finish()


func _test_audio() -> void:
	var cues := AudioCues.new()
	root.add_child(cues)
	await process_frame
	_check(cues.get_child_count() == 8, "audio has a bounded eight-voice pool")
	var sounds: Dictionary = cues.get("_sounds")
	_check(sounds.size() == 8, "all synthesized cue resources are built")
	for kind: String in sounds:
		var stream := sounds[kind] as AudioStreamWAV
		_check(stream != null and stream.format == AudioStreamWAV.FORMAT_16_BITS
			and stream.mix_rate == 22050 and not stream.stereo
			and stream.data.size() > 100, "valid self-contained PCM cue: " + kind)
	_check(not cues.play_event("unsupported"), "unsupported event is harmless")
	_check(cues.play_event("shot", {"weapon": "ak"}), "gunshot event reaches an audio voice")
	_check(not cues.play_event("shot"), "dense gunfire is throttled")
	_check(cues.toggle(), "mute toggle enables mute")
	var before: int = cues.events_played
	_check(not cues.play_event("round_start") and cues.events_played == before, "mute blocks new playback")
	for voice: AudioStreamPlayer in cues.get_children():
		_check(not voice.playing, "mute stops an existing voice")
	_check(not cues.toggle() and cues.play_event("round_end"), "unmute restores round cues")
	cues.muted = true
	await create_timer(0.06).timeout
	cues.queue_free()
	await process_frame


func _capture_if_requested() -> void:
	var capture_path := ""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--capture="):
			capture_path = argument.trim_prefix("--capture=")
	if capture_path.is_empty():
		return
	if DisplayServer.get_name() == "headless":
		details["capture"] = "skipped: headless has no rendered framebuffer"
		return
	await process_frame
	await RenderingServer.frame_post_draw
	var picture := root.get_texture().get_image()
	_check(picture != null and picture.get_width() > 0, "rendered screenshot has a framebuffer")
	if picture != null:
		_check(picture.save_png(capture_path) == OK, "rendered screenshot saved")
		details["capture"] = capture_path


func _check(value: bool, label: String) -> void:
	checks += 1
	if not value:
		failures.append(label)
		push_error("SMOKE ASSERT: " + label)


func _finish() -> void:
	print("TACTICAL2D_SMOKE " + JSON.stringify({"ok": failures.is_empty(), "checks": checks,
		"failures": failures, "details": details, "career_files_accessed": false,
		"cs2_started": false}))
	quit(0 if failures.is_empty() else 1)
