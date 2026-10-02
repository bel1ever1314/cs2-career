extends Node
## No service: calendar outcomes are fixtures and never mutate real save files.
var checks := 0
var failures: Array[String] = []
var sends: Array[String] = []
var accepted := true
var save_reads := 0

func _ready() -> void:
	call_deferred("run")

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("SLEEP_CHECK ", "PASS " if value else "FAIL ", label)

func send(target: String) -> bool:
	sends.append(target)
	return accepted

func save_transport(path: String, _payload: Dictionary, post: bool) -> bool:
	check(path == "/api/3d/saves" and not post, "desktop navigation only reads manual slots")
	save_reads += 1
	return true

func wait_sleep(sleep) -> void:
	var deadline := Time.get_ticks_msec() + 3000
	while sleep.active and Time.get_ticks_msec() < deadline: await get_tree().process_frame
	check(not sleep.active, "transition completes within fixture deadline")

func capture(name: String) -> void:
	if DisplayServer.get_name() == "headless": return
	var directory := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture-dir="): directory = arg.trim_prefix("--capture-dir=")
	if directory.is_empty(): return
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(directory)
	check(get_viewport().get_texture().get_image().save_png(directory.path_join(name + ".png")) == OK, "native screenshot " + name)

func run() -> void:
	check("--no-service" in OS.get_cmdline_user_args(), "isolated fixtures")
	CareerBridge.context = {"date":"2026-10-02", "player":{"id":"human"}, "calendar":{"revision":42}, "stories":[], "feedback":{"items":[]}}
	CareerBridge.connected = true
	CareerBridge.clock_held = false
	CareerBridge.sound_muted = true
	CareerBridge.feedback.set_process(false)
	var sleep = CareerBridge.sleep_transition
	sleep.fade_seconds = .08
	sleep.morning_seconds = .08
	sleep.start_command = send
	Phone.present("calendar")
	check(Phone.screen.visible, "calendar is visible before sleep")
	check(CareerBridge.calendar("2026-10-03", true), "sleep accepts calendar target")
	check(sleep.active and CareerBridge.sleeping and CareerBridge.phone_open, "night transition locks walking and time")
	check(not Phone.screen.visible and not Computer.screen.visible, "sleep puts devices away")
	check(sends.is_empty() and sleep.overlay.modulate.a == 0, "calendar not sent before fade to night")
	check(not sleep.begin("2026-10-04"), "repeated click cannot start second sleep")
	Phone.present(); Computer.present()
	check(not Phone.screen.visible and not Computer.screen.visible, "device shortcuts cannot open over sleep")
	check(not CareerBridge.command("/api/3d/attr", {}), "unrelated write not queued during sleep")
	await get_tree().create_timer(.15).timeout
	check(sends == ["2026-10-03"] and sleep.overlay.modulate.a > .99, "one calendar command only after opaque night")
	check(sleep.caption.get_line_count() == 1 and sleep.subtitle.get_line_count() == 1 and sleep.text_column.size.x > 300, "night captions are horizontal with a full text column")
	check(CareerBridge.context.date == "2026-10-02", "presentation never invents a date")
	await capture("sleep-night")
	CareerBridge.context.date = "2026-10-03"
	CareerBridge.clock_minutes = 480
	CareerBridge.clock_held = false
	sleep.complete({"ok":true, "status":"reached"})
	check(sleep.caption.text == "早上好" and sleep.subtitle.text.contains("2026-10-03"), "morning displays actual server date")
	await capture("sleep-morning")
	await wait_sleep(sleep)
	check(not CareerBridge.sleeping and not CareerBridge.phone_open and not sleep.overlay.visible, "morning releases input and curtain")
	check(not CareerBridge.clock_held, "successful sleep resumes clock")
	check(sleep.begin("2026-10-04"), "next sleep may begin")
	await get_tree().create_timer(.15).timeout
	CareerBridge.clock_held = true
	sleep.complete({"ok":true, "status":"paused", "reason":"比赛等待你决定。"})
	check(sleep.caption.text == "时间暂停" and sleep.subtitle.text == "比赛等待你决定。", "event pause not advertised as target date reached")
	await wait_sleep(sleep)
	check(CareerBridge.clock_held and Phone.screen.visible and Phone.active_page == "calendar", "paused calendar returns to player without auto answer")
	Phone.close_phone()
	accepted = false
	CareerBridge.clock_held = false
	check(sleep.begin("2026-10-04"), "can fade before rejected send")
	await wait_sleep(sleep)
	check(sleep.outcome == "failed" and not CareerBridge.clock_held, "unsent request restores prior time hold")
	accepted = true
	check(sleep.begin("2026-10-04"), "can test failed transport")
	await get_tree().create_timer(.15).timeout
	CareerBridge.clock_held = true
	sleep.complete({"ok":false, "msg":"后台连接中断。"})
	await wait_sleep(sleep)
	check(not CareerBridge.sleeping and CareerBridge.clock_held, "unknown server outcome releases curtain but keeps time paused")
	CareerBridge.busy = true
	check(not sleep.begin("2026-10-04"), "busy service rejects sleep before animation")
	CareerBridge.busy = false
	CareerBridge.context["training_pending"] = true
	check(not sleep.begin("2026-10-04"), "unfinished match blocks sleep")
	CareerBridge.context.erase("training_pending")
	check(not sleep.begin("2026-10-01"), "past target cannot start sleep")
	check(sleep.begin("2026-10-04"), "continuation failure fixture starts sleep")
	await get_tree().create_timer(.15).timeout
	CareerBridge.calendar_running = true
	CareerBridge.busy = true
	check(not CareerBridge._calendar_step() and not CareerBridge.calendar_running, "synchronous continuation failure stops calendar chain")
	CareerBridge.busy = false
	await wait_sleep(sleep)
	check(not CareerBridge.sleeping and CareerBridge.clock_held, "continuation failure cannot leave a permanent black screen")
	var feed = CareerBridge.feedback
	feed.seen["future-award"] = true
	feed.map_sounds["future-map"] = true
	feed.queue.append({"id":"future-award"})
	Phone.selected_contact = "old-contact"
	Computer.page_reports["ladder"] = {"match":"old-match"}
	CareerBridge.pending_target = "2026-12-31"
	CareerBridge.queued_command = {"path":"old-action"}
	CareerBridge.growth_draft = {"firepower":2}
	Travel.match_visit = {"match_id":"old-match"}
	CareerBridge._reset_for_loaded_career()
	check(feed.seen.is_empty() and feed.queue.is_empty() and feed.map_sounds.is_empty(), "same-player restore clears future feedback dedup")
	check(Computer.page_reports.is_empty() and Phone.selected_contact.is_empty(), "restore clears stale views")
	check(CareerBridge.queued_command.is_empty() and CareerBridge.pending_target.is_empty() and CareerBridge.growth_draft.is_empty(), "restore discards transient commands and allocation draft")
	check(Travel.match_visit.is_empty() and CareerBridge.clock_minutes == 480, "restore resets scene visit and wakes at eight")
	CareerBridge.context.feedback.items = [{"id":"same-context-award", "kind":"event_awards"}]
	feed.ingest()
	var original_scene := get_tree().current_scene
	get_tree().current_scene = null # No travel or real scene is part of this response fixture.
	CareerBridge.active_path = "/api/3d/saves/load"
	CareerBridge.active_post = true
	CareerBridge.active_body = {}
	CareerBridge._response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), JSON.stringify({"ok":true, "loaded":true, "context":CareerBridge.context.duplicate(true)}).to_utf8_buffer())
	check(feed.queue.size() == 1 and feed.queue[0].id == "same-context-award", "identical-context load re-ingests unacknowledged honours exactly once")
	await get_tree().process_frame
	get_tree().current_scene = original_scene
	feed.queue.clear()
	var manager = Computer.save_manager
	manager.command_sender = save_transport
	Computer.present()
	Computer._navigate("saves")
	check(manager.pending_path == "/api/3d/saves" and save_reads == 1, "desktop enters save manager and reads once")
	manager.received("/api/3d/saves", {"ok":true, "revision":42, "current":{"player":"Fixture", "team":"Fixture Team", "date":"2026-10-03", "era":"2026", "size_bytes":4096, "saved_at":"2026-10-02T08:00:00"}, "slots":[], "blocked":false})
	manager.draft = "大赛之前"
	Computer._rebuild()
	var field: LineEdit = manager.controls.name
	check(not manager.controls.save.disabled, "ready desktop enables manual save")
	CareerBridge.active_post = false
	CareerBridge.busy = true
	Computer._busy_changed(true)
	check(manager.controls.save.disabled and manager.controls.refresh.disabled, "background synchronization has visible save gates")
	CareerBridge.busy = false
	Computer._busy_changed(false)
	check(not manager.controls.save.disabled and not manager.controls.refresh.disabled, "busy release restores save controls without rebuild")
	CareerBridge.context.date = "2026-10-04"
	Computer._context_changed()
	check(manager.controls.name == field and field.text == "大赛之前", "context refresh does not replace name input")
	Computer._navigate("desktop")
	CareerBridge.busy = true
	Computer._navigate("saves")
	check(not manager.requested_once and save_reads == 1, "navigation during poll leaves initial fetch pending")
	CareerBridge.busy = false
	Computer._process(0)
	check(manager.requested_once and save_reads == 2, "save page fetch resumes when poll ends")
	manager.received("/api/3d/saves", {"ok":true, "revision":42, "current":{}, "slots":[], "blocked":false})
	Computer.close_computer()
	print("SLEEP_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
