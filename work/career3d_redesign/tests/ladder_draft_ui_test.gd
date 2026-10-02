extends Node
## Real workstation widgets and paced turns, with a test-only bridge transport.
const MAPS := ["dust2", "mirage", "inferno", "nuke", "ancient", "anubis", "train"]
const PICK_ORDER := ["a", "b", "b", "a", "a", "b", "b", "a"]
var failures: Array[String] = []
var checks := 0
var capture := false
var transport

func _ready() -> void:
	call_deferred("run")

func before_computer() -> void:
	pass

func before_phone() -> void:
	pass

func set_device_open(_opened: bool, _kind: String) -> void:
	pass

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("LADDER_DRAFT_UI_CHECK ", "PASS " if ok else "FAIL ", label)

func settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame

func pid(index: int) -> String:
	return "ladder-fixture-%d" % index

func room(phase: String = "draft", human_captain: bool = false, human_turn: bool = false) -> Dictionary:
	var roster := {}
	var ratings := {}
	var selection: Array[String] = []
	for i in range(10):
		var id := pid(i)
		selection.append(id)
		roster[id] = {"player_id":id, "name":"队长甲" if i == 0 else ("队长乙" if i == 1 else "候选 %d" % i), "role":"awp" if i == 3 else "rifle"}
		ratings[id] = 1800 - i * 50
	var lobby := {"id":"ladder-visible-fixture", "mode":"rank", "phase":phase, "human_id":pid(0) if human_captain else pid(2),
		"captains":[pid(0), pid(1)], "roster":roster, "ratings":ratings, "selection":selection, "a":[pid(0)], "b":[pid(1)],
		"picks":[], "bans":[], "map_pool":MAPS.duplicate(), "map":"", "ct":"a", "side_chooser":"a",
		"turn":{"side":"a", "captain_id":pid(0), "human":human_turn}, "matched_range":[1350,1800]}
	if phase != "draft":
		for i in range(8):
			var side: String = PICK_ORDER[i]
			lobby[side].append(pid(i + 2))
			lobby["picks"].append({"side":side, "player_id":pid(i + 2)})
	if phase in ["side", "ready"]:
		for i in range(6): lobby["bans"].append({"map":MAPS[i], "side":"a" if i % 2 == 0 else "b"})
		lobby["map"] = MAPS[-1]
	if phase == "ready": lobby["turn"] = null
	return lobby

func context(lobby: Dictionary, revision: int = 14) -> Dictionary:
	return {"date":"2026-10-01", "player":{"id":lobby["human_id"], "name":lobby["roster"][lobby["human_id"]]["name"]},
		"ladder":{"revision":revision, "player":{"elo":1700,"wins":4,"losses":2}, "maps":MAPS.duplicate(), "history":[], "lobby":lobby.duplicate(true)},
		"scrims":{}, "inbox":[], "calendar_events":[]}

func show(lobby: Dictionary, revision: int = 14) -> void:
	transport.fixture_reset(context(lobby, revision))
	Computer.ladder_room.reset()
	Computer.cs2_status = {"status":"idle", "can_launch":true, "config":{"ready":true}, "process_known":true, "cs2_running":false}
	Computer.report.clear()
	Computer.present("club")
	Computer._navigate("ladder", false)
	await settle()

func named(control_name: String) -> Control:
	return Computer.content.find_child(control_name, true, false) as Control

func prefixed(prefix: String, kind: String = "Button") -> Array:
	var result: Array = []
	for node in Computer.content.find_children("*", kind, true, false):
		if str(node.name).begins_with(prefix): result.append(node)
	return result

func labels_text() -> String:
	var parts: PackedStringArray = []
	for label in Computer.content.find_children("*", "Label", true, false): parts.append(label.text)
	return "\n".join(parts)

func fragment_button(fragment: String) -> Button:
	for button in Computer.content.find_children("*", "Button", true, false):
		if fragment in button.text: return button
	return null

func all_disabled(buttons: Array) -> bool:
	for button in buttons:
		if not button.disabled: return false
	return true

func first_fold_buttons(prefix: String) -> int:
	# visible_in_tree does not account for a ScrollContainer clipping its rows.
	# Require enough actual intersection for the button caption to be readable.
	var clip := Computer.scroll.get_global_rect()
	var count := 0
	for button in prefixed(prefix):
		var overlap: Rect2 = clip.intersection(button.get_global_rect())
		if button.is_visible_in_tree() and overlap.size.y >= 22 and overlap.size.x >= button.size.x * .5:
			count += 1
	return count

func advance_calls() -> int:
	var count := 0
	for call in transport.fixture_calls:
		if call["path"] == "/api/3d/ladder/advance": count += 1
	return count

func frame(delta: float) -> void:
	Computer.ladder_room.process(delta)

func capture_page(name_text: String) -> void:
	if not capture: return
	await settle()
	await RenderingServer.frame_post_draw
	var output := ProjectSettings.globalize_path("res://tests-output")
	DirAccess.make_dir_recursive_absolute(output)
	check(get_viewport().get_texture().get_image().save_png(output.path_join(name_text)) == OK, "capture " + name_text)

func capture_pool(control_name: String, filename: String) -> void:
	if not capture: return
	var control := named(control_name)
	if control == null: return
	Computer.scroll.scroll_vertical = maxi(0, int(control.get_global_rect().position.y - Computer.scroll.get_global_rect().position.y - 28))
	await capture_page(filename)
	Computer.scroll.scroll_vertical = 0
	await settle()

func run() -> void:
	transport = get_node("/root/CareerBridge")
	if not transport.has_method("fixture_reset") or not "--no-service" in OS.get_cmdline_user_args():
		push_error("Ladder draft tests require ladder_bridge_fixture.gd autoload and --no-service")
		get_tree().quit(2)
		return
	capture = "--ladder-capture" in OS.get_cmdline_user_args()
	Computer.set_process(false)
	Phone.set_process(false)
	get_window().content_scale_size = Vector2i(1280, 720)
	get_window().size = Vector2i(1280, 720)
	var lobby := room()
	await show(lobby)
	check(prefixed("LadderDraft_").size() == 8, "noncaptain sees all eight unpicked candidates")
	check(first_fold_buttons("LadderDraft_") > 0, "1280x720 first fold contains readable candidate buttons inside scroll clip")
	check(all_disabled(prefixed("LadderDraft_")), "noncaptain cannot manually choose teammates")
	check(labels_text().contains("最高") and labels_text().contains("队长甲") and labels_text().contains("队长乙") and labels_text().contains("1800") and labels_text().contains("1750"), "both highest Elo captains and ratings are explained")
	check(labels_text().contains("正在选") or labels_text().contains("轮到"), "active captain turn has readable progress")
	check(transport.fixture_calls.is_empty(), "opening draft does not immediately skip its first visible turn")
	await capture_page("ladder_draft_spectator.png")
	await capture_pool("LadderDraft_" + pid(2), "ladder_draft_candidates.png")
	var first_id: int = named("LadderDraft_" + pid(2)).get_instance_id()
	frame(.60)
	Computer._context_changed()
	Computer._finished("/api/3d/ladder/status", Computer.cs2_status.duplicate(true))
	await settle()
	check(named("LadderDraft_" + pid(2)).get_instance_id() == first_id, "unchanged context/status keeps draft widgets stable")
	frame(.64)
	check(advance_calls() == 0, "AI turn waits at least 1.25 seconds")
	frame(.02)
	check(advance_calls() == 1 and transport.busy, "AI submits exactly one turn after visible delay")
	check(transport.fixture_calls[-1]["body"].get("revision") == 14, "AI intent carries current ladder revision")
	for _i in range(8): frame(2.0)
	check(advance_calls() == 1, "pending AI turn never submits duplicates")
	transport.fixture_complete()
	await settle()
	frame(10)
	check(advance_calls() == 1, "same unchanged turn cannot replay after successful response")
	lobby["a"].append(pid(2))
	lobby["picks"].append({"side":"a", "player_id":pid(2)})
	lobby["turn"] = {"side":"b", "captain_id":pid(1), "human":false}
	transport._apply_context(context(lobby, 15))
	await settle()
	check(prefixed("LadderDraft_").size() == 7 and named("LadderDraft_" + pid(2)) == null and labels_text().contains("候选 2"), "next pick renders seven candidates and the selected player in team roster")
	check(labels_text().contains("刚刚选择") and labels_text().contains("候选 2"), "latest draft pick provides immediate readable feedback")
	frame(1.24)
	check(advance_calls() == 1, "each new AI hand receives its own full delay")
	frame(.02)
	check(advance_calls() == 2, "second AI hand advances once after its interval")
	transport.fixture_complete()
	lobby["b"].append(pid(3))
	lobby["picks"].append({"side":"b", "player_id":pid(3)})
	transport._apply_context(context(lobby, 16))
	await settle()
	Computer.close_computer()
	frame(20)
	check(advance_calls() == 2, "hidden workstation pauses AI progression")
	Computer.present("club")
	await settle()
	frame(1.24)
	check(advance_calls() == 2, "reopened turn receives a fresh viewing interval")
	frame(.02)
	check(advance_calls() == 3, "reopened room resumes one delayed AI turn")
	transport.fixture_complete()
	lobby["b"].append(pid(4))
	lobby["picks"].append({"side":"b", "player_id":pid(4)})
	lobby["turn"] = {"side":"a", "captain_id":pid(0), "human":false}
	transport._apply_context(context(lobby, 17))
	Computer._navigate("appearance", false)
	frame(20)
	check(advance_calls() == 3, "another computer page pauses AI progression")
	Computer._navigate("ladder", false)
	await settle()
	frame(1.24)
	check(advance_calls() == 3, "returning from another app starts a fresh interval")
	frame(.02)
	check(advance_calls() == 4, "returning to ladder resumes without repeated submissions")
	await show(room("draft", true, true))
	check(prefixed("LadderDraft_").size() == 8 and not all_disabled(prefixed("LadderDraft_")), "human captain gets all eight active pick controls on own turn")
	frame(20)
	check(advance_calls() == 0, "human captain turn never auto-advances")
	(named("LadderDraft_" + pid(4)) as Button).pressed.emit()
	check(transport.fixture_calls.size() == 1 and transport.fixture_calls[-1]["path"] == "/api/3d/ladder/pick" and transport.fixture_calls[-1]["body"].get("player_id") == pid(4), "manual pick sends chosen stable player id")
	check(all_disabled(prefixed("LadderDraft_")), "manual pick request locks the remaining candidates")
	await show(room("draft", true, false))
	check(all_disabled(prefixed("LadderDraft_")), "human captain waits during other captain turn")
	lobby = room("veto")
	lobby["bans"] = [{"side":"a", "map":"dust2"}, {"side":"b", "map":"mirage"}]
	await show(lobby)
	check(prefixed("LadderMap_").size() == 7, "noncaptain sees all seven maps including banned maps")
	check(first_fold_buttons("LadderMap_") > 0, "1280x720 first fold contains readable map buttons inside scroll clip")
	check(all_disabled(prefixed("LadderMap_")), "noncaptain cannot manually ban a map")
	check((named("LadderMap_dust2") as Button).text.contains("A") and (named("LadderMap_dust2") as Button).text.contains("已禁") and (named("LadderMap_mirage") as Button).text.contains("B"), "banned maps retain their team and disabled annotation")
	check(named("LadderBanRecord") != null and named("LadderBanRecord").text.contains(str(MAPS[0]).capitalize()) and named("LadderBanRecord").text.contains(str(MAPS[1]).capitalize()), "veto log shows completed bans in order")
	await capture_page("ladder_veto_spectator.png")
	await capture_pool("LadderMap_dust2", "ladder_veto_maps.png")
	lobby = room("veto", true, true)
	lobby["bans"] = [{"side":"a", "map":"dust2"}]
	await show(lobby)
	check((named("LadderMap_dust2") as Button).disabled and not (named("LadderMap_inferno") as Button).disabled, "human turn keeps banned map locked and remaining maps actionable")
	(named("LadderMap_inferno") as Button).pressed.emit()
	check(transport.fixture_calls[-1]["path"] == "/api/3d/ladder/ban" and transport.fixture_calls[-1]["body"].get("map") == "inferno", "manual ban sends correct map id")
	await show(room("side"))
	check(labels_text().contains("Train"), "side phase displays the surviving map")
	var ct := fragment_button("CT")
	var t := fragment_button("T ·")
	check((ct == null or ct.disabled) and (t == null or t.disabled), "noncaptain cannot manually choose side")
	await show(room("side", true, true))
	ct = fragment_button("CT")
	check(ct != null and not ct.disabled, "human captain can choose side on own turn")
	ct.pressed.emit()
	check(transport.fixture_calls[-1]["path"] == "/api/3d/ladder/side" and transport.fixture_calls[-1]["body"].get("side") == "ct", "manual side choice sends current phase intent")
	await show(room("ready"))
	check(prefixed("LadderPickRecord_", "Label").size() == 8 and named("LadderBanRecord") != null, "ready phase preserves all eight picks and six bans")
	check(labels_text().contains("Train") and labels_text().contains("CT"), "ready phase keeps selected map and starting side summary")
	check(fragment_button("模拟这场") != null and named("ComputerLadderLaunchCS2") != null, "ready phase keeps simulation and real CS2 actions")
	frame(20)
	check(advance_calls() == 0, "ready room never queues more captain operations")
	Computer.scroll.scroll_vertical = int(Computer.content.size.y)
	await capture_page("ladder_ready_records.png")
	# The next two phases use the same scheduler but receive new turn keys.
	# Check complete veto progression instead of testing only the first draft.
	lobby = room("veto")
	await show(lobby)
	for hand in range(6):
		frame(1.24)
		check(advance_calls() == hand, "veto hand %d waits its full interval" % (hand + 1))
		frame(.02)
		check(advance_calls() == hand + 1, "veto hand %d submits exactly once" % (hand + 1))
		var side := "a" if hand % 2 == 0 else "b"
		lobby["bans"].append({"side":side, "map":MAPS[hand]})
		lobby["turn"] = {"side":"b" if side == "a" else "a", "captain_id":pid(1) if side == "a" else pid(0), "human":false}
		if hand == 5:
			lobby["phase"] = "side"
			lobby["map"] = MAPS[-1]
			lobby["turn"] = {"side":"a", "captain_id":pid(0), "human":false}
		transport.fixture_complete(context(lobby, 15 + hand))
		await settle()
	check(prefixed("LadderMap_").is_empty() and labels_text().contains("Train"), "six paced bans transition to the surviving map and side choice")
	frame(1.24)
	check(advance_calls() == 6, "AI side choice receives a fresh full interval")
	frame(.02)
	check(advance_calls() == 7, "AI side choice submits only once")
	lobby["phase"] = "ready"
	lobby["turn"] = null
	transport.fixture_complete(context(lobby, 21))
	await settle()
	frame(20)
	check(advance_calls() == 7 and prefixed("LadderPickRecord_", "Label").size() == 8, "completed AI room preserves records and stops advancing")
	await show(room())
	transport.fixture_reject_next = true
	frame(1.26)
	check(advance_calls() == 0 and not Computer.ladder_room.pause_reason.is_empty(), "rejected dispatch stops with visible retry feedback")
	frame(20)
	check(advance_calls() == 0, "rejected dispatch never silently retries")
	Computer.ladder_room.retry()
	frame(1.24)
	check(advance_calls() == 0, "explicit retry waits a full visible interval")
	frame(.02)
	check(advance_calls() == 1, "explicit retry issues only one operation")
	transport.fixture_complete({}, {"ok":false, "msg":"隔离测试：结果未知。", "outcome_unknown":true})
	frame(20)
	check(advance_calls() == 1 and not Computer.ladder_room.pause_reason.is_empty(), "unknown write outcome pauses automatic progression")
	await show(room())
	Computer.scroll.scroll_vertical = 220
	await settle()
	var retained_scroll: int = Computer.scroll.scroll_vertical
	check(retained_scroll > 0, "scroll fixture starts below the first fold")
	var updated_status: Dictionary = Computer.cs2_status.duplicate(true)
	updated_status["reason"] = "隔离测试：连接状态更新。"
	Computer._finished("/api/3d/ladder/status", updated_status)
	await settle()
	check(Computer.scroll.scroll_vertical == retained_scroll, "same draft status refresh preserves live scroll position")
	Computer.scroll.scroll_vertical = retained_scroll
	transport._apply_context(context(room(), 15))
	await settle()
	check(Computer.scroll.scroll_vertical == retained_scroll, "same draft context refresh preserves reading position")
	transport._apply_context(context(room("veto"), 16))
	await settle()
	check(Computer.scroll.scroll_vertical == 0 and int(Computer.page_scroll.get("ladder", -1)) == 0, "draft to veto resets both live and cached scroll to top")
	check(first_fold_buttons("LadderMap_") > 0, "draft to veto brings map buttons into actual visible viewport")
	Computer.scroll.scroll_vertical = 220
	await settle()
	var next_room := room("veto")
	next_room["id"] = "ladder-visible-fixture-next-room"
	transport._apply_context(context(next_room, 17))
	await settle()
	check(Computer.scroll.scroll_vertical == 0 and first_fold_buttons("LadderMap_") > 0, "new room in the same phase also starts at visible map pool")
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "fixture never starts real service or touches save data")
	Computer.close_computer()
	print("LADDER_DRAFT_UI_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
