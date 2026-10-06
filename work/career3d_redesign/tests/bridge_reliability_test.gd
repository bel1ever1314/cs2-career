extends Node
const Queue = preload("res://scripts/career_read_queue.gd")
var failures: Array[String] = []
var checks := 0

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("BRIDGE_CHECK ", "PASS " if value else "FAIL ", label)

func _ready() -> void:
	call_deferred("run")

func run() -> void:
	var queue := Queue.new()
	queue.enqueue("/detail"); queue.enqueue("/detail")
	check(queue.paths.size() == 1, "duplicate reads coalesce")
	queue.failed("/detail", 1000)
	check(queue.take(1999).is_empty(), "failed read waits before retry")
	check(queue.take(2000) == "/detail", "retry becomes eligible")
	queue.failed("/detail", 2000)
	check(not queue.ready("/detail", 3999), "backoff grows")
	check("/detail" in queue.paths, "failed active read is requeued")
	queue.succeeded("/detail")
	check(queue.ready("/detail", 2000), "success clears backoff")
	CareerBridge.context = {"date":"2026-12-31", "calendar":{"revision":8}}
	CareerBridge.clock_minutes = 1550
	check(CareerBridge.clock_text().ends_with("23:59"), "clock never displays 24-plus hours")
	CareerBridge.clock_boundary = true
	CareerBridge._finish_calendar({"ok":false, "status":"error"}, {})
	check(CareerBridge.clock_held, "failed day boundary pauses clock")
	CareerBridge.endpoint = "http://127.0.0.1:1"
	CareerBridge.connected = true
	CareerBridge.busy = true
	CareerBridge.active_post = false
	check(CareerBridge._send("/api/3d/player?id=p", {}, false), "detail click accepted during background poll")
	check("/api/3d/player?id=p" in CareerBridge.reads.paths, "detail remains queued")
	CareerBridge.connection_generation = 5
	CareerBridge.request_sequence = 6
	CareerBridge._response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), "{}".to_utf8_buffer(), 4, 6)
	check(CareerBridge.busy, "old connection response cannot release current request")
	CareerBridge.active_path = "/api/3d/calendar"
	CareerBridge.active_post = true
	CareerBridge.active_request_id = "lost-response-001"
	CareerBridge.queued_command = {"path":"/api/3d/attr", "body":{}}
	CareerBridge._response(HTTPRequest.RESULT_CANT_CONNECT, 0, PackedStringArray(), PackedByteArray(), 5, 6)
	check(CareerBridge.reconnecting and not CareerBridge.connected, "transport failure starts reconnect")
	check(CareerBridge.unknown_command.get("request_id") == "lost-response-001", "ambiguous write retains lookup ID")
	check(CareerBridge.queued_command.is_empty(), "unsent write is not silently replayed")
	check(CareerBridge.reads.paths.all(func(path): return not path.contains("calendar")), "writes never enter read retry queue")
	CareerBridge.active_path = "/api/3d/requests?id=lost-response-001"
	CareerBridge.active_post = false
	CareerBridge._response(HTTPRequest.RESULT_SUCCESS, 500, PackedStringArray(), '{"ok":false}'.to_utf8_buffer())
	check(not CareerBridge.unknown_command.is_empty(), "receipt query failure preserves unresolved write")
	check(CareerBridge.active_path in CareerBridge.reads.paths, "receipt query retries as a read")
	Phone.selected_player = {"id":"fixture-player"}
	CareerBridge.busy = true
	Phone._player_scope("year", 2)
	check("/api/3d/player?id=fixture-player&span=year&page=2" in CareerBridge.reads.paths, "phone player pagination queues during sync")
	Phone._load_news("awards", 2)
	check("/api/3d/news?category=awards&page=2" in CareerBridge.reads.paths, "phone news pagination queues during sync")
	CareerBridge.busy = false
	CareerBridge.reconnecting = false
	CareerBridge.feedback.entry = {"id":"old-report"}
	CareerBridge.feedback.acknowledge()
	check(CareerBridge.feedback.entry.is_empty(), "offline presentation can close locally")
	CareerBridge.active_path = "/api/3d/calendar"
	CareerBridge.active_post = true
	CareerBridge.active_request_id = "commit-recovery-001"
	CareerBridge.owns_service = true
	CareerBridge._response(HTTPRequest.RESULT_SUCCESS, 503, PackedStringArray(), '{"ok":false,"error_code":"storage_recovery_required"}'.to_utf8_buffer())
	check(CareerBridge.reconnecting and not CareerBridge.connected, "coded storage error starts restart/reconnect")
	check(CareerBridge.unknown_command.get("request_id") == "commit-recovery-001", "storage recovery looks up original request")
	check(CareerBridge.clock_held, "storage recovery stops the presentation clock")
	CareerBridge.connected = true
	check(not CareerBridge.command("/api/3d/attr", {}), "new writes wait until ambiguous outcome lookup finishes")
	Computer.match_center.quick_running = true
	Computer.match_center.request_pending = true
	Computer.match_center.finished("/api/3d/season/step", {"ok":true, "result_summary":true, "status":"saved"})
	check(not Computer.match_center.quick_running and not Computer.match_center.request_pending, "receipt summary cannot silently continue a quick season")
	Computer.custom_room.pending_action = "recommend"
	Computer.custom_room.a.clear()
	Computer.custom_room.a.append("fixture-player")
	Computer.custom_room.received("/api/3d/custom/recommend", {"ok":true, "result_summary":true})
	check(Computer.custom_room.a == ["fixture-player"] and Computer.custom_room.pending_action.is_empty(), "summary releases custom request without replacing draft from missing data")
	CareerBridge.context["ladder"] = {"lobby":{"id":"fixture-room", "phase":"draft", "turn":{}}}
	Computer.ladder_room.received("/api/3d/ladder/matchmake", {"ok":true, "result_summary":true})
	Computer.ladder_room.queue()
	check(not Computer.ladder_room.pause_reason.is_empty(), "fresh room key does not clear recovery pause before explicit continuation")
	var draw = Computer.career_start.attribute_draw
	draw.retry_body = {"action":"roll", "era":"2026", "request_id":"lost-draw"}
	draw.loaded["2026"] = true
	draw.sessions["2026"] = {"attempts_used":2}
	draw.finished("/api/3d/start/draw", {"ok":true, "result_summary":true})
	check(draw.retry_body.is_empty() and draw.loaded.is_empty(), "draw confirmation clears uncertain retry and reloads saved draft")
	check(draw.sessions.get("2026", {}).get("attempts_used") == 2 and draw.unrevealed_draw_id.is_empty(), "draw summary neither erases counts nor starts another reel")
	var settings = Computer.device_settings
	settings.pending = true
	settings.saving = true
	settings.pending_path = "/api/3d/settings"
	settings.install_stage = "saving"
	settings.finished("/api/3d/settings", {"ok":true, "result_summary":true})
	check(not settings.pending and not settings.saving and settings.install_stage.is_empty(), "saved settings summary cannot automatically continue installation")
	CareerBridge.clock_minutes = 999
	Computer.career_start.submitting = true
	Computer.career_start.uncertain_creation = {"request_id":"lost-start"}
	Computer.career_start.finished("/api/3d/start/create", {"ok":true, "result_summary":true})
	check(not Computer.career_start.submitting and Computer.career_start.uncertain_creation.is_empty(), "creation confirmation releases pending form")
	check(CareerBridge.clock_minutes == 999 and Computer.career_start.page == "welcome", "creation summary does not replay travel or reset time")
	Travel.match_visit = {"match_id":"old-career-match"}
	Computer.page_reports["match"] = {"id":"old-career-report"}
	CareerBridge.active_path = "/api/3d/requests?id=lost-load"
	CareerBridge.active_post = false
	CareerBridge.unknown_command = {"path":"/api/3d/saves/load", "request_id":"lost-load"}
	CareerBridge._response(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), '{"ok":true,"status":"completed","result":{"ok":true,"loaded":true}}'.to_utf8_buffer())
	check(Travel.match_visit.is_empty() and Computer.page_reports.is_empty(), "confirmed slot load invalidates old venue and report caches")
	check(CareerBridge.unknown_command.is_empty() and CareerBridge.queued_command.is_empty(), "slot confirmation never queues a second load")
	print("BRIDGE_RESULT checks=", checks, " failures=", failures)
	get_tree().quit(0 if failures.is_empty() else 1)
