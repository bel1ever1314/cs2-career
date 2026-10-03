extends Node
## Monitor geometry only. Run with --no-service: no career or CS2 is started.
var checks := 0
var failures: Array[String] = []

func _ready() -> void:
	if not "--no-service" in OS.get_cmdline_user_args():
		push_error("Desktop layout checks require --no-service.")
		get_tree().quit(1)
		return
	call_deferred("run")

func check(value: bool, message: String) -> void:
	checks += 1
	if not value: failures.append(message)
	print("DESKTOP_LAYOUT ", "PASS " if value else "FAIL ", message)

func settle() -> void:
	for _frame in range(8): await get_tree().process_frame

func capture(name: String) -> void:
	if DisplayServer.get_name() == "headless": return
	var folder := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture-dir="): folder = arg.trim_prefix("--capture-dir=")
	if folder.is_empty(): return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(folder.path_join(name + ".png"))

func labels(node: Node) -> String:
	var text := PackedStringArray()
	for item in node.find_children("*", "Label", true, false): text.append(item.text)
	return "\n".join(text)

func run() -> void:
	CareerBridge.connected = true
	CareerBridge.context = {"date":"2026-06-21", "player":{"name":"测试选手"}, "calendar":{"revision":1, "date":"2026-06-21"}, "inbox":[], "attr_points":2}
	Computer.location = "club"
	Computer.screen.visible = true
	for dimensions in [Vector2i(1920, 1080), Vector2i(1280, 890), Vector2i(1280, 720), Vector2i(1024, 768), Vector2i(800, 600), Vector2i(640, 480)]:
		get_window().content_scale_size = dimensions
		get_window().size = dimensions
		Computer._desktop()
		await settle()
		Computer._resize()
		await settle()
		var prefix := "%dx%d " % [dimensions.x, dimensions.y]
		var dock := Computer.desktop_shortcuts as Control
		var dock_rect := dock.get_global_rect()
		var desktop := Computer.content.get_node("ComputerDesktop") as BoxContainer
		var stage := Computer.panel.find_child("ComputerStage", true, false) as Control
		var shortcuts := dock.get_node("ComputerDesktopShortcuts") as HFlowContainer
		check(not Computer.scroll.is_ancestor_of(dock), prefix + "shortcut dock is independent of page scrolling")
		check(dock_rect.end.y <= Computer.status.get_global_rect().position.y + 1, prefix + "dock is directly above footer")
		check(absf(dock_rect.end.y - Computer.status.get_global_rect().position.y) <= 1, prefix + "no unused space underneath dock")
		check(dock_rect.position.y >= stage.get_global_rect().end.y - 1, prefix + "shortcuts do not overlap main area")
		check(shortcuts.get_child_count() == 8, prefix + "all eight shortcuts remain available")
		for button in shortcuts.get_children():
			check(dock_rect.grow(1).encloses(button.get_global_rect()), prefix + button.text + " is within dock")
		check(desktop.vertical == (Computer.scroll.size.x < 720), prefix + "main area adapts to available width")
		if not desktop.vertical:
			check(desktop.size.y >= Computer.scroll.size.y - 1, prefix + "main area fills monitor instead of stopping at 395 px")
		var original_position := dock.position
		Computer.scroll.scroll_vertical = 120
		await settle()
		check(dock.position == original_position, prefix + "scrolling cannot move bottom shortcuts")
		Computer.scroll.scroll_vertical = 0
		await settle()
		await capture("desktop-%dx%d" % [dimensions.x, dimensions.y])
	Computer._navigate("event")
	await settle()
	check(not Computer.desktop_shortcuts.visible, "desktop dock is hidden in applications")
	check(Computer.content.size_flags_vertical == Control.SIZE_FILL, "applications keep their own scrolling height")
	Computer._desktop()
	await settle()
	check(Computer.desktop_shortcuts.visible, "returning home restores dock")
	CareerBridge.context["nextmatch"] = {"id":"fixture-match", "date":"2026-06-24", "event":"赛事测试", "opponent":"Fixture Team", "due":false,
		"attendance":{"planned":false, "display_name":"测试场馆", "instruction":"先睡到比赛日，早上从门口前往测试场馆。"}}
	Computer._desktop()
	await settle()
	check(Computer.content.find_child("DesktopAttendance", true, false) == null, "future unselected matches do not replace today's agenda")
	CareerBridge.context["nextmatch"]["attendance"]["planned"] = true
	Computer._desktop()
	await settle()
	var desktop_attendance := Computer.content.find_child("DesktopAttendance", true, false) as Button
	check(desktop_attendance != null and labels(Computer.content).contains("测试场馆"), "planned personal match shows event destination in desktop agenda")
	desktop_attendance.pressed.emit()
	check(Computer.active_page == "career_match", "agenda opens the personal attendance instructions")
	Computer.selected_date = "2026-06-22"
	Computer._navigate("calendar")
	await settle()
	var calendar_card := Computer.content.find_child("CalendarCareerMatch", true, false)
	var calendar_text := labels(calendar_card)
	check(calendar_text.contains("2026-06-24") and calendar_text.contains("Fixture Team"), "calendar uses scheduled match date and actual opponent")
	check(calendar_text.contains("测试场馆") and calendar_text.contains("从门口"), "calendar explains the specific destination and arrival action")
	var participate := calendar_card.find_child("CalendarAttendMatch", true, false) as Button
	check(participate.text == "亲自参赛 · 睡到比赛日", "future match offers sleep-to-match-day participation")
	var callback: Callable = participate.get_signal_connection_list("pressed")[0]["callable"]
	check(callback.get_object() == Computer.match_center and callback.get_method() == "prepare_real" and callback.get_bound_arguments() == ["fixture-match"], "calendar participation reuses the shared preparation flow")
	CareerBridge.context["nextmatch"]["due"] = true
	CareerBridge.context["nextmatch"]["attendance"]["planned"] = false
	Computer._desktop()
	await settle()
	check(Computer.content.find_child("DesktopAttendance", true, false) != null, "today's game is shown even before selecting personal attendance")
	Computer._navigate("calendar")
	await settle()
	check((Computer.content.find_child("CalendarAttendMatch", true, false) as Button).text == "亲自参赛", "due match offers same-day participation")
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "layout checks never connect a backend")
	print(JSON.stringify({"ok":failures.is_empty(), "checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
