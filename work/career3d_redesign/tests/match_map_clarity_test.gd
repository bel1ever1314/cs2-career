extends Node
## Series map overview, side guidance, tactics map hint and live settings note.
## Fixtures only: commands are captured, no service, CS2 or save is touched.
const Settings = preload("res://scripts/device_settings.gd")
var failures: Array[String] = []
var checks := 0
var commands: Array = []
var center

func _ready() -> void:
	call_deferred("run")

func match_seated(id: String) -> bool:
	return id == "clarity-match"

func check(value: bool, caption: String) -> void:
	checks += 1
	if not value: failures.append(caption)
	print("MAP_CLARITY_CHECK ", "PASS " if value else "FAIL ", caption)

func send_fixture(path: String, body: Dictionary) -> bool:
	commands.append({"path":path, "body":body.duplicate(true)})
	return true

func _button(parent: Node, text: String, action: Callable, _primary: bool = true) -> Button:
	var button := Button.new()
	button.text = text
	button.pressed.connect(action)
	parent.add_child(button)
	return button

func button(fragment: String) -> Button:
	for candidate in Computer.content.find_children("*", "Button", true, false):
		if candidate.text.begins_with(fragment): return candidate
	return null

func text_present(fragment: String) -> bool:
	for node in Computer.content.find_children("*", "Label", true, false):
		if fragment in node.text: return true
	return false

func series(live: bool) -> Array:
	var second := {"index":2, "map":"train", "cs2_map":"de_train", "picked_by":"The MongolZ", "decider":false, "state":"live" if live else "next"}
	if live: second["side"] = "t"
	return [{"index":1, "map":"mirage", "cs2_map":"de_mirage", "picked_by":"Vitality", "decider":false, "state":"done", "score":"13-9", "winner":"Vitality", "won":true},
		second,
		{"index":3, "map":"nuke", "cs2_map":"de_nuke", "picked_by":"", "decider":true, "state":"upcoming"}]

func fixture(live: bool) -> Dictionary:
	return {"match_id":"clarity-match", "phase":"launched" if live else "ready", "can_simulate":true, "can_launch":not live, "due":true, "played":false,
		"team_a":"Vitality", "team_b":"The MongolZ", "best_of":3, "date":"2026-07-21", "block_reason":"", "side":"t" if live else "ct",
		"venue":{"destination":"lan", "match_id":"clarity-match", "identity_source":"frozen_match_rosters", "should_walk":true, "travel_allowed":true},
		"pending_map":"train", "maps_done":1, "series_maps":series(live),
		"veto":{"complete":true, "initialized":true, "steps":[{"team":"Vitality","action":"pick","map":"mirage","play":1}, {"team":"The MongolZ","action":"pick","map":"train","play":2}, {"team":null,"action":"decider","map":"nuke","play":3}],
			"order":["mirage", "train", "nuke"], "available":[], "turn":null},
		"config":{"ready":true,"reason":""}}

func reset(info: Dictionary) -> void:
	center.preflight.clear(); center.connection.clear(); center.result.clear()
	center.show_real = true; center.request_pending = false; center.notice = ""
	CareerBridge.context = {"date":"2026-07-21", "calendar":{"revision":18},
		"player":{"id":"fixture-player", "name":"Fixture player"}, "team":{"name":"Vitality"}, "inbox":[], "stories":[],
		"nextmatch":{"id":"clarity-match","event":"Fixture Cup","date":"2026-07-21","opponent":"The MongolZ","best_of":3,"due":true,
			"attendance":{"match_id":"clarity-match","destination":"lan","display_name":"小型赛场","is_today":true,"phase":"today","can_travel":true}},
		"match_preflight":info.duplicate(true), "settings":{"difficulty":"Medium"}, "quick":{"mode":"normal","year":2026}}
	Travel.match_visit = {"match_id":"clarity-match", "destination":"lan"}
	Computer.open_app("career_match", "lan")

func status(info: Dictionary, live: bool) -> Dictionary:
	return {"ok":true, "match_id":"clarity-match", "phase":info.phase, "status":"waiting" if live else "ready", "preflight":info.duplicate(true),
		"can_launch":not live, "cs2_running":live, "process_known":true, "can_collect":live, "result_ready":false,
		"reason":"CS2 正在进行。" if live else "", "result":null}

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args():
		push_error("match_map_clarity_test requires --no-service")
		get_tree().quit(1)
		return
	Locale.set_language("zh-CN", false)
	CareerBridge.connected = true; CareerBridge.clock_held = true
	CareerBridge.set_process(false); Computer.set_process(false); Phone.set_process(false)
	get_viewport().size = Vector2i(1280, 720)
	scene_file_path = "res://lan.tscn"
	center = Computer.match_center
	center.command_sender = send_fixture

	# Before launch: the map about to be played is "this map", never "next".
	var ready := fixture(false)
	reset(ready)
	Computer._finished("/api/3d/match/status?id=clarity-match", status(ready, false))
	await get_tree().process_frame
	check(text_present("本图 · 第2图 Train") and not text_present("下一图"), "the map to launch is named as this map")
	check(text_present("第1图 · Mirage") and text_present("胜 13-9") and text_present("第3图 · Nuke") and text_present("决胜图"), "series strip lists played, current and decider maps")
	check(button("CT 开场 · 进入 CS2 打 Train") != null and button("T 开场 · 进入 CS2 打 Train") != null, "side buttons name the map they launch")
	check(text_present("与机器人游戏 → 竞技 → 选 Train"), "launch steps name the map to pick in CS2")
	await get_tree().process_frame
	var visible_rect: Rect2 = Computer.scroll.get_global_rect()
	for caption in ["CT 开场", "T 开场"]:
		var control := button(caption)
		check(control != null and visible_rect.encloses(control.get_global_rect()), caption + " stays fully visible at 1280x720")
	button("T 开场").pressed.emit()
	check(not commands.is_empty() and commands[-1].body.get("side") == "t", "chosen side is sent with the launch")

	# While CS2 runs: the waiting map is "in progress" with the side to join.
	var live := fixture(true)
	reset(live)
	Computer._finished("/api/3d/match/status?id=clarity-match", status(live, true))
	await get_tree().process_frame
	check(text_present("正在进行 · 第2图 Train") and not text_present("下一图"), "a launched map is shown as in progress, not as the next map")
	check(text_present("CS2 里请打 Train，阵营 T（恐怖分子）"), "live guide names the map and the side to join")
	check(button("CT 开场") == null, "no second launch while the map is waiting")
	check(Locale.english("正在进行 · 第2图 Train") == "In progress · Map 2 Train", "series headline is translated")
	check(Locale.english("CS2 里请打 Train，阵营 CT（反恐精英）。地图或阵营不对，这张图的战绩不会录入。").begins_with("In CS2, play Train"), "live guide is translated")

	# Tactics room points at the match map and offers a switch.
	var editor = Computer.tactics
	editor.command_sender = func(path: String, body: Dictionary) -> bool: commands.append({"path":path, "body":body}); return true
	editor.libraries = {}
	Computer._navigate("tactics", false)
	await get_tree().process_frame
	check(editor.map_code == "de_train", "first visit on match day opens the match map")
	editor.change_map("de_nuke")
	await get_tree().process_frame
	var note: Label = editor.controls.get("match_map_note")
	var use: Button = editor.controls.get("TacticsUseMatchMap")
	check(note != null and note.visible and "Train" in note.text and "Nuke" in note.text and "进入该地图即可使用" in note.text, "other-map tactics remain usable when playing that map")
	check(use != null and use.visible and use.text == "切换到 Train", "one click returns to the match map")
	use.pressed.emit()
	await get_tree().process_frame
	check(editor.map_code == "de_train" and not use.visible and "正在编辑本场比赛地图" in note.text, "switching back confirms the match map")

	# Settings stay editable during a match and say when they apply.
	CareerBridge.busy = false; CareerBridge.active_post = false
	CareerBridge.context = {"calendar":{"revision":7}, "settings":{"difficulty":"Medium", "setup":{}, "config":{"ready":true, "path_errors":[], "component_errors":[]},
		"live_match":true, "apply_note":"比赛进行中：正在打的这张图沿用开赛时的设置，保存后从下一张图开始生效。"}}
	var settings := Settings.new()
	settings.command_sender = send_fixture
	settings.query_sender = func(_path: String): return true
	var parent := VBoxContainer.new()
	add_child(parent)
	settings.render(self, parent, false)
	var live_note := parent.find_child("DeviceSettingsLiveMatchNote", true, false) as Label
	check(live_note != null and "下一张图" in live_note.text, "settings explain changes apply from the next map")
	var save := parent.find_child("DeviceSettingsSave", true, false) as Button
	check(save != null and not save.disabled, "saving is still available during a match")

	print("MAP_CLARITY_RESULT checks=", checks, " failures=", failures.size())
	for item in failures: print("MAP_CLARITY_FAILURE ", item)
	get_tree().quit(0 if failures.is_empty() else 1)
