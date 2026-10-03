extends Node
## UI-only fixture: no service, game startup, or save is touched.
var failures: Array[String] = []
var checks := 0

func _ready() -> void:
	call_deferred("run")

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("LADDER_CS2_UI_CHECK ", "PASS " if ok else "FAIL ", label)

func settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame

func named_button(fragment: String) -> Button:
	for button in Computer.content.find_children("*", "Button", true, false):
		# The shared scoreboard spaces its player marker more generously.
		if button.is_visible_in_tree() and fragment in button.text.replace("  ", " "):
			return button
	return null

func run() -> void:
	CareerBridge.connected = true
	CareerBridge.clock_held = true
	var roster := {}
	var a := []
	var b := []
	for i in range(10):
		var pid := "fixture-%d" % i
		roster[pid] = {"player_id":pid, "name":"Player %d" % i, "role":"rifle"}
		if i < 5: a.append(pid)
		else: b.append(pid)
	CareerBridge.context = {
		"date":"2026-01-08", "player":{"id":"fixture-0", "name":"Player 0"},
		"ladder":{"revision":3, "player":{"elo":1200, "wins":0, "losses":0}, "history":[],
			"lobby":{"id":"fixture-room", "mode":"rank", "phase":"starting", "human_id":"fixture-0", "map":"dust2", "roster":roster, "a":a, "b":b}},
		"scrims":{}, "inbox":[], "calendar_events":[]
	}
	Computer.cs2_status = {"status":"waiting", "phase":"starting", "lobby_id":"fixture-room", "can_collect":true,
		"can_retry":false, "process_known":true, "cs2_running":false, "reason":"等待启动"}
	Computer.present("club")
	Computer._navigate("ladder", false)
	await settle()
	check(named_button("重试进入 CS2") == null, "a nonfailed startup has no duplicate launch")
	var failure := {"ok":true, "status":"failed", "reason":"模拟启动失败", "connection":{
		"status":"failed", "phase":"starting", "lobby_id":"fixture-room", "can_collect":true,
		"can_retry":true, "process_known":true, "cs2_running":false, "reason":"模拟启动失败"}}
	Computer._finished("/api/3d/ladder/launch", failure)
	await settle()
	check(named_button("重试进入 CS2") != null, "failed startup exposes launch retry even when collection is also possible")
	check(named_button("录入战绩") != null, "pending startup still allows reading a result")
	check(named_button("放弃本场") != null, "closed game has an explicit unscored abandonment path")
	Computer.cs2_status["cs2_running"] = true
	Computer._rebuild()
	await settle()
	check(named_button("放弃本场") == null or named_button("放弃本场").disabled, "live game cannot abandon or overwrite its room")
	Computer.cs2_status["cs2_running"] = null
	Computer.cs2_status["process_known"] = false
	Computer._rebuild()
	await settle()
	check(named_button("放弃本场") == null or named_button("放弃本场").disabled, "unknown process state cannot abandon a room")
	var players := {"Team A":[], "Team B":[]}
	for i in range(10):
		players["Team A" if i < 5 else "Team B"].append({"player_id":"fixture-%d" % i, "name":"Player %d" % i,
			"k":15, "d":10, "a":3, "rating":1.15, "adr":80.0, "kast":.75})
	var real_report := {"id":"fixture-room", "mode":"rank", "human_id":"fixture-0", "changes":{"fixture-0":16},
		"date":"2026-01-08", "map":{"source":"cs2", "map":"dust2", "score":"13 : 6", "winner":"Team A", "players":players}}
	var title: String = Computer._report_title(real_report)
	check("Team A" in title and "Team B" in title, "real result without optional teams field keeps both team names")
	Computer._open_report(real_report)
	await settle()
	check(named_button("Player 0 · 你") != null, "real ten-player report identifies the controlled career player")
	var player_buttons := 0
	for button in Computer.content.find_children("*", "Button", true, false):
		if button.text.begins_with("Player "): player_buttons += 1
	check(player_buttons == 10, "real report renders exactly ten player entries")
	check(CareerBridge.endpoint.is_empty(), "UI regressions never call a real game service")
	Computer.close_computer()
	print("LADDER_CS2_UI_RESULT ", JSON.stringify({"checks":checks,"failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
