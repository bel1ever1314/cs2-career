extends Node
## No backend, game launch or career writes. Explicit requests stay in a fake
## in-flight read queue and completions are delivered by this fixture only.
var checks := 0
var failures: Array[String] = []

func _ready() -> void:
	if not "--no-service" in OS.get_cmdline_user_args():
		push_error("Device action feedback requires --no-service.")
		get_tree().quit(1)
		return
	call_deferred("run")

func check(ok: bool, description: String) -> void:
	checks += 1
	if not ok: failures.append(description)
	print("ACTION_FEEDBACK_CHECK ", "PASS " if ok else "FAIL ", description)

func settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame

func set_device_open(_opened: bool, _kind: String) -> void:
	pass

func queue_read() -> void:
	CareerBridge.connected = true
	CareerBridge.busy = true
	CareerBridge.active_post = false
	CareerBridge.queued_command.clear()
	CareerBridge.message = ""

func ignore_mouse(node: Node) -> bool:
	if node is Control and node.mouse_filter != Control.MOUSE_FILTER_IGNORE: return false
	for child in node.get_children():
		if not ignore_mouse(child): return false
	return true

func run() -> void:
	get_viewport().size = Vector2i(1280, 720)
	CareerBridge.connected = true
	CareerBridge.clock_held = true
	CareerBridge.context = {"date":"2026-03-04", "calendar":{"revision":4}, "player":{"id":"fixture", "name":"Fixture"}, "team":{}, "personal":{"growth_allowed":true}, "ladder":{"revision":1}, "inbox":[], "stories":[], "nextmatch":{}, "calendar_events":[], "recent_matches":[]}
	Computer.present("bedroom")
	await settle()
	var feedback = Computer.action_feedback
	check(feedback != null and not feedback.visible, "opening device does not invent an action result")
	check(ignore_mouse(feedback), "entire feedback tree ignores mouse and cannot block controls")
	check(not Computer.scroll.is_ancestor_of(feedback) and Computer.panel.is_ancestor_of(feedback), "result lives in fixed monitor overlay, outside scrolling page")
	Computer.show_action_feedback("已复制 play fixture。")
	await settle()
	var before_position: Vector2 = feedback.global_position
	Computer.scroll.scroll_vertical = 200
	await settle()
	check(feedback.current_message == "已复制 play fixture。" and feedback.global_position == before_position, "local operation result stays visible without scrolling to footer")
	Computer.show_action_feedback("正在保存……", "progress", 0.0)
	check(feedback.current_kind == "progress" and feedback.remaining < 0.0, "progress has distinct state and waits for completion")
	Computer.show_action_feedback("已保存。", "success", .25)
	check(feedback.current_message == "已保存。" and feedback.current_kind == "success", "new result replaces previous progress")
	feedback._process(.1)
	check(feedback.visible and feedback.modulate.a < 1.0, "result visibly fades without blocking a timer")
	feedback._process(.2)
	check(not feedback.visible and feedback.current_message.is_empty(), "expired notice leaves no stale result")
	Computer.show_action_feedback("正在保存战术…", "progress", 0.0, "tactics:save:de_dust2")
	Computer.show_action_feedback("已复制指令。", "success", .25)
	feedback._process(.3)
	check(feedback.current_kind == "progress" and feedback.current_message == "正在保存战术…", "short clipboard success restores unfinished operation progress")
	Computer.show_action_feedback("战术已保存。", "success", .25, "tactics:save:de_dust2")
	feedback._process(.3)
	check(not feedback.visible and feedback.pending_operations.is_empty(), "completed keyed operation never resurrects its old progress")
	Computer.show_action_feedback("正在读取其他地图…", "progress", 0.0, "tactics:read:de_nuke")
	shown_count_check(feedback)
	feedback.track_request("/api/3d/attr", true)
	Computer.show_action_feedback("已复制指令。", "success", .25)
	feedback._process(.3)
	check(feedback.current_kind == "progress" and feedback.current_message == "正在处理……", "short local result also restores an unfinished owned backend request")
	feedback.clear_notice(true)

	queue_read()
	check(Computer._command("/api/3d/controls/assistance"), "explicit write queued behind read is owned by requesting device")
	check(feedback.current_kind == "progress" and feedback.pending_requests.has("/api/3d/controls/assistance"), "request acceptance shows progress, never premature success")
	CareerBridge.queued_command.clear()
	Computer._finished("/api/3d/controls/assistance", {"ok":true})
	await settle()
	check(feedback.current_message == "自动安排已保存。" and feedback.current_kind == "success", "successful write without message gets meaningful completion")
	var shown: int = feedback.shown_count
	Computer._finished("/api/3d/controls/assistance", {"ok":true})
	Phone._finished("/api/3d/controls/assistance", {"ok":true})
	Computer._finished("/api/3d/ladder/status", {"ok":true})
	await settle()
	check(feedback.shown_count == shown and not Phone.action_feedback.visible, "duplicate completion, other device and background GET never repeat result")
	queue_read()
	Computer._device_command("/api/3d/ops/donate", {"amount":100})
	CareerBridge.queued_command.clear()
	Computer._finished("/api/3d/ops/donate", {"ok":false, "msg":"余额不足。"})
	await settle()
	check(feedback.current_kind == "error" and feedback.current_message == "余额不足。", "backend rejection is shown as failure with actual reason")
	queue_read()
	Computer._command("/api/3d/attr")
	CareerBridge.queued_command.clear()
	Computer._finished("/api/3d/attr", {"ok":false, "outcome_unknown":true})
	await settle()
	check(feedback.current_kind == "error" and "尚未确认" in feedback.current_message, "lost write response is not falsely reported as success or safe retry")
	Computer.show_action_feedback("旧页面结果")
	Computer._navigate("events")
	await settle()
	check(not feedback.visible, "navigation clears old page notice")
	queue_read()
	Computer._command("/api/3d/controls/assistance")
	CareerBridge.queued_command.clear()
	Computer.close_computer()
	shown = feedback.shown_count
	Computer._finished("/api/3d/controls/assistance", {"ok":true})
	await settle()
	check(not feedback.visible and feedback.shown_count == shown and feedback.pending_requests.is_empty(), "closing discards pending display ownership and late result stays silent")

	CareerBridge.busy = false
	Phone.present("home")
	await settle()
	queue_read()
	check(Phone._command("/api/3d/mail/decline"), "phone owns only its own explicit write")
	CareerBridge.queued_command.clear()
	Phone._finished("/api/3d/mail/decline", {"ok":true})
	await settle()
	check(Phone.action_feedback.current_message == "已婉拒这次邀请。" and not feedback.visible, "phone gets meaningful own result without waking computer notice")
	check(not Phone.scroll.is_ancestor_of(Phone.action_feedback) and ignore_mouse(Phone.action_feedback), "phone notification also stays outside content and never intercepts input")
	queue_read()
	Phone._command("/api/3d/social/send")
	CareerBridge.queued_command.clear()
	Phone._finished("/api/3d/social/send", {"ok":true, "social_contact_id":"fixture-contact"})
	await settle()
	check(Phone.active_page == "chat" and Phone.action_feedback.current_message == "消息已发送。", "own completion survives automatic destination navigation")
	shown = Phone.action_feedback.shown_count
	Phone._rebuild()
	await settle()
	check(Phone.action_feedback.current_message == "消息已发送。" and Phone.action_feedback.shown_count == shown, "context/page refresh keeps notice without duplicate display")
	Phone.close_phone()
	CareerBridge.busy = false
	print("ACTION_FEEDBACK_RESULT ", JSON.stringify({"checks":checks,"failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)

func shown_count_check(feedback: Control) -> void:
	var count_before: int = feedback.shown_count
	Computer.show_action_feedback("", "success", 4.0, "tactics:read:de_nuke")
	check(not feedback.visible and feedback.pending_operations.is_empty() and feedback.shown_count == count_before, "empty completion quietly removes its operation and stale progress")
