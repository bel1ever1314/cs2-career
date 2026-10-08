extends Node
## Real device trees; all replies are fixtures. No backend or user-save writes.
var checks := 0
var failures: Array[String] = []

func _ready() -> void: call_deferred("run")
func set_device_open(_opened: bool, _kind: String) -> void: pass
func frames() -> void:
	for i in range(6): await get_tree().process_frame
func check(value: bool, caption: String) -> void:
	checks += 1
	if not value: failures.append(caption)
	print("SCROLL_MEMORY ", "PASS " if value else "FAIL ", caption)

func management() -> Dictionary:
	var roster: Array = []
	for i in range(5):
		roster.append({"player_id":"p%d" % i, "name":"Player %d" % i, "ability":80, "age":21, "role":["igl","awp","rifle","entry","lurker"][i]})
	var offers: Array = []
	for i in range(12): offers.append({"title":"Contract %d" % i, "team":"Fixture", "status":"closed", "body":"Fixture contract history"})
	return {"team":"Fixture", "roster":roster, "roles_allowed":true, "marks":{"allowed":true}, "offers":offers,
		"roles":["igl","awp","rifle","entry","lurker"], "role_labels":{}}

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(2); return
	CareerBridge.set_process(false); Computer.set_process(false); Phone.set_process(false)
	CareerBridge.clock_held = true; CareerBridge.connected = true
	CareerBridge.context = {"date":"2026-03-04", "calendar":{"revision":4}, "start":{"creation_required":false},
		"player":{"id":"p0", "name":"Player 0"}, "team":{}, "inbox":[], "stories":[], "nextmatch":{}}
	var path := "/api/3d/controls/management"
	for language in ["zh-CN", "en"]:
		Locale.set_language(language, false)
		for dimensions in [Vector2i(960,540), Vector2i(1920,1080)]:
			get_window().size = dimensions
			CareerBridge.busy = true; CareerBridge.active_post = false
			var data := management()
			Computer.controls.role_signature = ""
			Computer.controls.pending_path = ""
			Computer.controls.cache[path] = {"revision":4, "data":data}
			Computer.open_app("management", "club")
			await frames()
			Computer.scroll.scroll_vertical = 180
			await frames()
			var position: int = Computer.scroll.scroll_vertical
			check(position > 0, "fixture can scroll " + language + str(dimensions))
			Computer.controls._role_changed("awp", "Player 0", data.roster)
			await frames()
			check(Computer.scroll.scroll_vertical == position, "changing position preserves viewport")
			check(Computer.controls.role_draft["Player 0"] == "awp" and Computer.controls.role_draft["Player 1"] == "igl", "role swap remains intact")
			Computer.content.find_child("RosterSave", true, false).grab_focus()
			await frames()
			position = Computer.scroll.scroll_vertical
			Computer.controls._command("roles", {"roles":Computer.controls.role_draft.duplicate()})
			check(CareerBridge.queued_command.get("body", {}).get("roles", {}).get("Player 0") == "awp", "save sends the selected role")
			CareerBridge.queued_command.clear()
			Computer._finished("/api/3d/controls/roles", {"ok":true, "msg":"已保存"})
			await frames()
			check(Computer.content.find_child("RosterSave", true, false) != null and Computer.controls.role_draft["Player 0"] == "awp", "save keeps page and draft while refreshing")
			check(Computer.scroll.scroll_vertical == position, "save response preserves viewport")
			data.roster[0].role = "awp"; data.roster[1].role = "igl"
			Computer._finished(path, {"ok":true, "page":"management", "revision":4, "data":data})
			await frames()
			check(Computer.scroll.scroll_vertical == position, "fresh data and focus restoration preserve viewport")
			Computer._finished("/api/3d/controls/roles", {"ok":false, "msg":"请稍后再试"})
			await frames()
			check(Computer.scroll.scroll_vertical == position, "rejected save preserves viewport")
			Computer._navigate("desktop")
			await frames()
			Computer._navigate("management")
			await frames()
			check(Computer.scroll.scroll_vertical == position, "back navigation restores page position")
			Computer.page_scroll.management = 0
			Computer._rebuild()
			await frames()
			check(Computer.scroll.scroll_vertical == 0, "explicit new-content reset still works")
			Computer.scroll.scroll_vertical = 220
			Computer._rebuild(); Computer._rebuild()
			await frames()
			check(Computer.scroll.scroll_vertical == 220, "same-frame rebuilds ignore old restoration")
			Computer._rebuild()
			Computer._navigate("desktop")
			await frames()
			check(Computer.scroll.scroll_vertical == 0, "late restore cannot move another page")
			Computer.close_computer()
			Phone.selected_team = {"name":"Fixture", "roster":data.roster + data.roster + data.roster}
			Phone.present("team")
			await frames()
			Phone.scroll.scroll_vertical = 170
			await frames()
			var phone_position: int = Phone.scroll.scroll_vertical
			Phone._rebuild()
			await frames()
			check(phone_position > 0 and Phone.scroll.scroll_vertical == phone_position, "phone refresh preserves viewport")
			Phone.close_phone()
	print("SCROLL_MEMORY_RESULT checks=", checks, " failures=", failures)
	get_tree().quit(0 if failures.is_empty() else 1)
