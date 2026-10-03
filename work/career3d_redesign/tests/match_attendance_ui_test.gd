extends Node
## Local UI fixtures only: no real date writer, venue transition or CS2 launch.
var checks := 0
var failures: Array[String] = []
var commands: Array = []
var targets: Array[String] = []
var wakes := 0

func _ready() -> void:
	call_deferred("run")

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("ATTENDANCE_UI_CHECK ", "PASS " if ok else "FAIL ", label)

func send(path: String, body: Dictionary) -> bool:
	commands.append({"path":path, "body":body.duplicate(true)})
	return true

func sleep_send(target: String) -> bool:
	targets.append(target)
	return true

func woke() -> void:
	wakes += 1

func settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame

func wait_sleep() -> void:
	var limit := Time.get_ticks_msec() + 1500
	while CareerBridge.sleep_transition.active and Time.get_ticks_msec() < limit:
		await get_tree().process_frame
	check(not CareerBridge.sleep_transition.active, "night curtain completes")

func labels(root: Node) -> String:
	var values: Array[String] = []
	for node in root.find_children("*", "Label", true, false): values.append(node.text)
	return "\n".join(values)

func button(root: Node, fragment: String) -> Button:
	for node in root.find_children("*", "Button", true, false):
		if fragment in node.text: return node
	return null

func run() -> void:
	check("--no-service" in OS.get_cmdline_user_args(), "isolated no-service fixture")
	CareerBridge.set_process(false)
	Computer.set_process(false)
	CareerBridge.connected = true
	CareerBridge.sound_muted = true
	CareerBridge.feedback.set_process(false)
	CareerBridge.wake_requested.disconnect(Phone._wake)
	CareerBridge.wake_requested.connect(woke)
	var sleep = CareerBridge.sleep_transition
	sleep.fade_seconds = .03
	sleep.morning_seconds = .03
	sleep.start_command = sleep_send
	var plan := {"match_id":"planned-match", "date":"2026-10-05", "event":"IEM Fixture", "opponent":"Orange Team", "destination":"major", "display_name":"LANXESS arena", "phase":"scheduled", "due":false, "can_travel":false, "sleep_target":"2026-10-05", "planned":false, "instruction":"10 月 5 日早上，从宿舍门口选择 LANXESS arena。"}
	CareerBridge.context = {"date":"2026-10-02", "calendar":{"revision":4}, "player":{"id":"human", "name":"Player"}, "team":{"name":"Green Team"}, "stories":[], "inbox":[], "calendar_events":[], "recent_matches":[], "nextmatch":{"id":"planned-match", "date":"2026-10-05", "event":"IEM Fixture", "opponent":"Orange Team", "due":false, "attendance":plan}, "match_preflight":{}, "feedback":{"items":[]}}
	Computer.match_center.command_sender = send
	Computer.open_app("career_match", "bedroom")
	await settle()
	check("LANXESS arena" in labels(Computer.content), "computer names the actual destination before match day")
	check(button(Computer.content, "亲自参赛 · 睡到比赛日") != null, "future match offers attendance and morning sleep")
	check(button(Computer.content, "CT 开场") == null, "future match has no launch button")
	Phone.present("match")
	check("LANXESS arena" in labels(Phone.content), "phone match page gives the same destination")
	Phone.present("calendar")
	check("LANXESS arena" in labels(Phone.content) and "Orange Team" in labels(Phone.content), "calendar contains the fixture and destination")
	Computer.match_center.prepare_real("planned-match")
	check(commands.size() == 1 and commands[0].path == "/api/3d/match/attend", "attendance choice plans instead of freezing or launching")
	check(commands[0].body.match_id == "planned-match" and commands[0].body.revision == 4, "plan binds the current match and calendar revision")
	plan.planned = true
	Computer.match_center.finished("/api/3d/match/attend", {"ok":true, "attendance":plan})
	await get_tree().create_timer(.10).timeout
	check(targets == ["2026-10-05"], "one sleep targets the real fixture date")
	check(not Computer.screen.visible and not Phone.screen.visible, "night closes both devices")
	check(Travel.match_visit.is_empty() and commands.size() == 1, "planning has not travelled or prepared a CS2 session")
	CareerBridge.context.date = "2026-10-05"
	CareerBridge.context.nextmatch.due = true
	plan.phase = "today"
	plan.due = true
	plan.can_travel = true
	plan.sleep_target = ""
	CareerBridge.context.nextmatch.attendance = plan
	CareerBridge.clock_minutes = 1300
	CareerBridge._finish_calendar({"ok":true, "status":"paused", "reason_code":"player_match", "actualdate":"2026-10-05"}, {"display_hour":8, "wake":true})
	check(CareerBridge.clock_minutes == 480 and not CareerBridge.clock_held and wakes == 1, "match gate wakes at eight without simulating the match")
	check(sleep.caption.text == "早上好" and "LANXESS arena" in sleep.subtitle.text, "morning says where to play today")
	await wait_sleep()
	check(not Phone.screen.visible, "match morning returns to the room rather than a blocking calendar")
	Computer.match_center.finish_attendance(plan)
	check(not Travel.busy and "LANXESS arena" in CareerBridge.message, "today's attendance tells player to go to the door instead of teleporting")
	Computer.match_center.prepare_real("planned-match")
	check(commands.size() == 2 and commands[-1].path == "/api/3d/match/preflight", "match-day direct play still prepares without requiring another door choice")
	Computer.match_center.request_pending = false
	Computer.match_center.venue_after_preflight = ""
	CareerBridge.context.nextmatch.due = false
	check(sleep.begin("2026-10-07"), "later sleep accepts a real date")
	await get_tree().create_timer(.10).timeout
	CareerBridge.context.date = "2026-10-06"
	CareerBridge._finish_calendar({"ok":true, "status":"paused", "reason_code":"story", "actualdate":"2026-10-06", "reason":"生日消息等你回复。"}, {"display_hour":8, "wake":true})
	check(wakes == 1 and CareerBridge.clock_held and sleep.caption.text == "时间暂停", "earlier story is not mistaken for match morning")
	await wait_sleep()
	check(Phone.screen.visible and Phone.active_page == "calendar", "earlier date event remains available to answer")
	check(CareerBridge.context.date == "2026-10-06", "presentation never invents the requested future day")
	Phone.close_phone()
	print("ATTENDANCE_UI_RESULT ", JSON.stringify({"checks":checks, "failures":failures, "cs2_launches":0}))
	get_tree().quit(0 if failures.is_empty() else 1)
