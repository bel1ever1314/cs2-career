extends "res://tests/career_real_match_flow_test.gd"
## Real buttons and status responses, with every launch captured in memory.

func reject_launch(_path: String, _body: Dictionary) -> bool:
	return false

func show_online() -> Dictionary:
	var info := fixture(true)
	info.venue.merge({"destination":"club", "should_walk":false, "travel_allowed":false}, true)
	reset(info)
	CareerBridge.context.quick["unified_pace"] = true
	CareerBridge.context.nextmatch.attendance.merge({"destination":"club", "display_name":"俱乐部训练室"}, true)
	scene_file_path = "res://play.tscn"
	Travel.match_visit.clear()
	center.pace.flow.reset()
	center.show_real = true
	Computer.open_app("career_match", "club")
	Computer._finished("/api/3d/match/status?id=fixture-match", ready_status(info, true, "路径和比赛组件已就绪。"))
	return info

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(1); return
	CareerBridge.set_process(false); Computer.set_process(false); Phone.set_process(false)
	CareerBridge.connected = true; CareerBridge.busy = false; CareerBridge.clock_held = true
	Locale.set_language("zh-CN", false)
	center = Computer.match_center
	center.command_sender = send_fixture
	for side in ["ct", "t"]:
		var info := show_online()
		commands.clear()
		click(side.to_upper() + " 开场")
		check(commands.size() == 1 and commands[0].path == "/api/3d/match/launch" and commands[0].body.side == side, "online " + side + " button dispatches launch without a venue visit")
		check(center.request_pending and center.pending_action == "launch" and text_present("正在启动 CS2"), "online launch has visible request progress")
		check(Travel.match_visit.is_empty() and not Travel.busy, "online launch does not travel or create a LAN visit")
		Computer._finished("/api/3d/match/launch", {"ok":false, "reason":"测试启动失败，请重试。"})
		Computer._finished("/api/3d/match/status?id=fixture-match", ready_status(info, true, "路径和比赛组件已就绪。"))
		check(center.notice == "测试启动失败，请重试。" and text_present(center.notice), "backend launch failure survives a healthy status poll")
	# A valid LAN match must still require its physical seat. This also covers
	# a click racing with a seat becoming unavailable after buttons were built.
	var lan := fixture(true)
	reset(lan)
	CareerBridge.context.quick["unified_pace"] = true
	scene_file_path = "res://play.tscn"
	Travel.match_visit.clear()
	center.pace.flow.reset(); center.show_real = true
	Computer.open_app("career_match", "club")
	Computer._finished("/api/3d/match/status?id=fixture-match", ready_status(lan))
	check(button("CT 开场") == null and button("T 开场") == null and button("前往 小型赛场 入座") != null, "unseated LAN offers travel instead of misleading launch buttons")
	check(center.pace.plan().title == "线下比赛 · 等待入座", "dock agrees with the LAN seat requirement")
	commands.clear()
	center.command("launch", {"match_id":"fixture-match", "side":"ct"})
	check(commands.is_empty() and center.notice.begins_with("先从门口前往"), "seat guard still rejects an obsolete launch callback")
	var blocked: String = center.notice
	for i in range(3):
		Computer._finished("/api/3d/match/status?id=fixture-match", ready_status(lan, true, "路径和比赛组件已就绪。"))
	check(center.notice == blocked and text_present(blocked), "background polls cannot erase the blocked-launch explanation")
	check(not center.quick_running and center.pace.flow.phase == "paused", "a rejected launch never leaves automatic progression running")
	# Explicitly rejected sends also have feedback, rather than a fake playing state.
	var online := show_online()
	center.command_sender = reject_launch
	CareerBridge.message = ""
	click("CT 开场")
	check(not center.request_pending and not center.quick_running and center.notice.begins_with("启动请求未发出"), "unsent launch gives feedback and stays paused")
	Computer._finished("/api/3d/match/status?id=fixture-match", ready_status(online))
	check(center.notice.begins_with("启动请求未发出"), "unsent launch feedback persists through refresh")
	center.command_sender = send_fixture
	click("T 开场")
	check(center.request_pending and center.notice.is_empty() and not center.notice_sticky, "an explicit retry clears the previous failure and dispatches once")
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "tests use no real backend or CS2")
	print("ONLINE_CAREER_LAUNCH_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
