extends Node
## Actual button callbacks against the backend's nullable JSON contract.
## All commands are captured in memory. No service, CS2 or career save is used.
var failures: Array[String] = []
var checks := 0
var commands: Array = []
var center
var capture_dir := ""

func _ready() -> void:
	call_deferred("run")

func match_seated(id: String) -> bool:
	return id == "fixture-match"

func check(value: bool, caption: String) -> void:
	checks += 1
	if not value: failures.append(caption)
	print("CAREER_REAL_FLOW_CHECK ", "PASS " if value else "FAIL ", caption)

func send_fixture(path: String, body: Dictionary) -> bool:
	commands.append({"path":path, "body":body.duplicate(true)})
	return true

func button(fragment: String) -> Button:
	for candidate in Computer.content.find_children("*", "Button", true, false):
		if candidate.text.begins_with(fragment): return candidate
	return null

func click(fragment: String) -> void:
	var target := button(fragment)
	check(target != null and not target.disabled, "enabled button: " + fragment)
	if target != null and not target.disabled: target.pressed.emit()

func text_present(fragment: String) -> bool:
	for node in Computer.content.find_children("*", "Label", true, false):
		if fragment in node.text: return true
	return false

func check_launch_visible() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	var visible_rect: Rect2 = Computer.scroll.get_global_rect()
	for caption in ["CT 开场", "T 开场"]:
		var control := button(caption)
		check(control != null and visible_rect.encloses(control.get_global_rect()), caption + " is fully visible at 1280x720")

func capture(caption: String) -> void:
	if capture_dir.is_empty(): return
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	if image != null and not image.is_empty(): image.save_png(capture_dir.path_join(caption + ".png"))

func fixture(complete: bool) -> Dictionary:
	return {"match_id":"fixture-match", "phase":"ready" if complete else "veto", "can_simulate":true, "can_launch":complete,
		"team_a":"Vitality", "team_b":"The MongolZ", "best_of":1, "date":"2026-07-21", "block_reason":"", "side":"ct",
		"venue":{"destination":"lan", "match_id":"fixture-match", "identity_source":"frozen_match_rosters", "should_walk":true, "travel_allowed":true},
		"pending_map":"dust2" if complete else null,
		"veto":{"complete":complete, "initialized":true, "steps":[{"team":null,"action":"decider","map":"dust2","play":1}] if complete else [],
			"order":["dust2"] if complete else [], "available":[] if complete else ["dust2","mirage"],
			"turn":null if complete else {"team":"Vitality", "action":"ban", "mine":true}},
		"config":{"ready":true,"reason":""}}

func reset(info: Dictionary) -> void:
	center.preflight.clear(); center.connection.clear(); center.result.clear()
	center.show_real = false; center.request_pending = false; center.notice = ""; center.notice_sticky = false
	center.venue_after_preflight = ""
	CareerBridge.context = {"date":"2026-07-21", "calendar":{"revision":18},
		"player":{"id":"fixture-player", "name":"Fixture player"}, "team":{"name":"Vitality"}, "inbox":[], "stories":[],
		"nextmatch":{"id":"fixture-match","event":"BLAST Bounty Season2 2026","date":"2026-07-21","opponent":"The MongolZ","best_of":1,"due":true,
			"attendance":{"match_id":"fixture-match","destination":"lan","display_name":"小型赛场","is_today":true,"phase":"today","can_travel":true,
				"instruction":"比赛日到了，到门口选择「小型赛场」，前往选手席入座。"}},
		"match_preflight":info.duplicate(true), "settings":{"difficulty":"Medium"}, "quick":{"mode":"normal","year":2026}}
	Travel.match_visit = {"match_id":"fixture-match", "destination":"lan"}
	Computer.open_app("career_match", "lan")

func ready_status(info: Dictionary, allowed: bool = true, reason: String = "") -> Dictionary:
	return {"ok":true, "match_id":"fixture-match", "phase":"ready", "status":"ready", "preflight":info.duplicate(true),
		"can_launch":allowed, "cs2_running":not allowed, "process_known":true, "can_collect":false, "result_ready":false,
		"reason":reason, "result":null}

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args():
		push_error("career_real_match_flow_test requires --no-service")
		get_tree().quit(1)
		return
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "no career service started")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture-dir="): capture_dir = arg.trim_prefix("--capture-dir=")
	if not capture_dir.is_empty(): DirAccess.make_dir_recursive_absolute(capture_dir)
	Locale.set_language("zh-CN", false)
	CareerBridge.connected = true; CareerBridge.clock_held = true
	CareerBridge.set_process(false); Computer.set_process(false); Phone.set_process(false)
	get_viewport().size = Vector2i(1280, 720)
	# This fixture is already seated; travelling or a real launch is never used.
	scene_file_path = "res://lan.tscn"
	center = Computer.match_center
	center.command_sender = send_fixture
	var info := fixture(true)
	info.veto.steps = []
	for index in range(7):
		info.veto.steps.append({"team":"Vitality" if index % 2 == 0 else "The MongolZ", "action":"ban", "map":["mirage","nuke","inferno","ancient","anubis","overpass","train"][index]})
	info.veto.steps.append({"team":null,"action":"decider","map":"dust2","play":1})
	reset(info)
	click("自己去 CS2 打")
	check(commands.size() == 1 and commands[-1].path == "/api/3d/match/preflight" and commands[-1].body.match_id == "fixture-match", "actual play button requests this match's preflight")
	check(center.request_pending and center.venue_after_preflight.is_empty(), "seated preparation stays at venue and rejects duplicate requests")
	check(text_present("正在核对本场比赛、阵容与地图") and not text_present("正在读取本场结果"), "preflight progress describes preparation rather than results")
	Computer._finished("/api/3d/match/preflight", {"ok":true,"status":"ready","reason":"比赛准备已保存。","preflight":info})
	check(not center.request_pending and center.show_real, "prepare completion rebuilds the real-match view")
	check(text_present("地图 BP 已完成 · 8 项记录") and not text_present("<null>"), "completed BO1 null turn and eight history entries render correctly")
	click("查看地图 BP 记录")
	check(text_present("决胜图 · dust2") and not text_present("<null>"), "null decider team has a real map label, not a null placeholder")
	click("收起地图 BP 记录")
	check(button("CT 开场") == null, "process status must be verified before choosing a launch side")
	Computer._finished("/api/3d/match/status?id=fixture-match", ready_status(info))
	check(center.result.is_empty() and button("CT 开场") != null and button("T 开场") != null, "status result=null does not interrupt side selection")
	await check_launch_visible()
	await capture("01-bo1-ready-zh-1280x720")
	Locale.set_language("en", false)
	await check_launch_visible()
	await capture("02-bo1-ready-en-1280x720")
	Locale.set_language("zh-CN", false)
	await get_tree().process_frame
	await get_tree().process_frame
	Computer.scroll.scroll_vertical = 10
	var before_scroll: int = Computer.scroll.scroll_vertical
	var before_root: int = Computer.content.get_child(0).get_instance_id()
	Computer._finished("/api/3d/match/status?id=fixture-match", ready_status(info))
	check(Computer.scroll.scroll_vertical == before_scroll and Computer.content.get_child(0).get_instance_id() == before_root, "unchanged status neither repaints nor moves scroll")
	click("T 开场")
	check(commands[-1].path == "/api/3d/match/launch" and commands[-1].body.side == "t" and commands[-1].body.revision == 18, "T button sends the existing launch contract")
	check(text_present("正在启动 CS2"), "launch progress is visible")
	info.side = "t"
	var failed := {"ok":true,"match_id":"fixture-match","status":"failed","phase":"ready","preflight":info,
		"can_launch":true,"can_retry":true,"can_collect":false,"result":null,"reason":"现有换肤组件缺失；请关闭可选换肤后再开赛。"}
	Computer._finished("/api/3d/match/launch", {"ok":true,"status":"failed","reason":failed.reason,"connection":failed,"result":null})
	check(text_present(failed.reason) and center.notice == failed.reason, "backend failure reason remains visible")
	check(button("检查并录入") == null and button("重试进入 CS2") != null, "failed launch offers retry, not collection of a nonexistent session")
	click("重试进入 CS2")
	check(commands[-1].path == "/api/3d/match/launch" and commands[-1].body.side == "t", "retry preserves the frozen side")
	var waiting := info.duplicate(true)
	waiting.phase = "launched"
	var linked := {"ok":true,"match_id":"fixture-match","status":"waiting","phase":"launched","preflight":waiting,
		"can_launch":false,"can_retry":false,"can_collect":true,"result":null,"reason":"等待真实十人战绩。"}
	Computer._finished("/api/3d/match/launch", {"ok":true,"status":"waiting","connection":linked,"result":null})
	check(center.current_preflight().phase == "launched" and text_present(linked.reason) and button("检查并录入") != null, "launch reaches the actual waiting-for-results UI")
	click("检查并录入")
	check(commands[-1].path == "/api/3d/match/collect" and not commands[-1].body.has("result") and not str(commands[-1].body.request_id).is_empty(), "collection asks the backend to read nonce-bound results")
	Computer._finished("/api/3d/match/collect", {"ok":false,"reason":"本场真实战绩尚未完整回传。","connection":linked,"result":null})
	check(center.notice == "本场真实战绩尚未完整回传。" and text_present(center.notice) and not center.request_pending, "collect error remains visible and does not hang requests")
	# Exercise a fresh, unfinished veto, then the normal boundary to null turn.
	info = fixture(false)
	reset(info)
	click("自己去 CS2 打")
	Computer._finished("/api/3d/match/preflight", {"ok":true,"preflight":info,"result":null})
	check(not text_present("<null>") and not text_present("下一图"), "pending_map=null never appears as a fake next map")
	check(Computer.content.find_children("*", "Button", true, false).filter(func(node): return "交给队长" in node.text).size() == 1, "one automatic veto action is shown")
	click("Mirage")
	click("确认禁用")
	check(commands[-1].path == "/api/3d/match/veto" and commands[-1].body.map == "mirage", "actual map button sends the veto command")
	info = fixture(true)
	Computer._finished("/api/3d/match/veto", {"ok":true,"status":"ready","reason":"比赛准备已保存。","preflight":info,"result":null})
	check(button("Mirage") == null and not text_present("<null>"), "veto completion removes active choices without null crashes")
	Computer._finished("/api/3d/match/status?id=fixture-match", ready_status(info, false, "CS2 正在运行，请完全退出后再开下一张地图。"))
	check(button("CT 开场") == null and text_present("CS2 正在运行"), "running CS2 cannot enable a new launch and explains why")
	Computer._finished("/api/3d/match/status?id=fixture-match", ready_status(info))
	click("CT 开场")
	check(commands[-1].path == "/api/3d/match/launch" and commands[-1].body.side == "ct", "completed veto proceeds to CT launch through real callbacks")
	center.request_pending = false
	info.can_launch = false; info.config = {"ready":false,"reason":"Steam 程序未找到，请选择 steam.exe。"}
	reset(info); center.show_real = true; Computer._rebuild()
	check(text_present(info.config.reason), "preflight displays the configuration blocker before status polling")
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service and not CareerBridge.busy, "all fixtures avoid real saves, network and CS2")
	print("CAREER_REAL_FLOW_RESULT ", JSON.stringify({"checks":checks,"failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
