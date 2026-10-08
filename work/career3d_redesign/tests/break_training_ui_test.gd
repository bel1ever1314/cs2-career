extends Node
var checks := 0
var failures: Array[String] = []
var sent: Array = []

func _ready() -> void: call_deferred("run")

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("BREAK_CHECK ", "PASS " if ok else "FAIL ", label)

func capture(path: String, body: Dictionary) -> bool:
	sent.append({"path":path, "body":body.duplicate(true)})
	return true

func frames() -> void:
	for i in range(5): await get_tree().process_frame

func texts(parent: Node) -> String:
	var rows := PackedStringArray()
	for label in parent.find_children("*", "Label", true, false): rows.append(Locale.text(label.text))
	return " | ".join(rows)

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(2); return
	CareerBridge.set_process(false); Computer.set_process(false); Phone.set_process(false)
	CareerBridge.connected = true; CareerBridge.busy = false; CareerBridge.clock_held = true
	scene_file_path = "res://play.tscn"
	var center = Computer.match_center
	center.command_sender = capture
	for language in ["zh-CN", "en"]:
		Locale.set_language(language, false)
		for resolution in [Vector2i(960,640), Vector2i(1920,1080)]:
			get_window().size = resolution; get_viewport().size = resolution
			CareerBridge.context = {"date":"2026-12-13", "attr_points":37, "calendar":{"revision":8},
				"player":{"name":"P"}, "team":{"name":"9z"}, "stories":[], "nextmatch":{}, "match_preflight":{},
				"quick":{"year":2026,"unified_pace":true,"season_phase":"running", "break_key":"2026:major-2","break_ack":false,"block_reason":""}}
			center.result.clear(); center.preflight.clear(); center.connection.clear(); center.request_pending = false
			center.pace.flow.reset(); Computer.open_app("quick", "club")
			await frames()
			var agenda = Computer.content.find_child("CareerBreakAgenda", true, false)
			check(agenda != null, "break checklist rendered")
			check(texts(agenda).contains(Locale.text("没有必须处理的事项，可以结束休赛停留。")), "no hidden tasks when nothing is pending")
			check(texts(Computer.content).contains("37"), "optional saved points visible")
			check(not Computer.pace_footer.find_child("PacePause", true, false).visible, "no misleading auto advance at break")
			var finish: Button = Computer.pace_footer.find_child("PaceContinue", true, false)
			check(Locale.text(finish.text) == Locale.text("结束休赛停留") and Computer.panel.get_global_rect().encloses(finish.get_global_rect()), "bottom action fits " + language + str(resolution))
			var count := sent.size()
			center.pace.start(); center.process(60)
			check(sent.size() == count and not center.quick_running, "start cannot bypass break")
			finish.pressed.emit()
			check(sent.size() == count + 1 and sent[-1].path.ends_with("/resume") and sent[-1].body.break_key == "2026:major-2", "bottom action acknowledges correct break")
			center.request_pending = false
			CareerBridge.context.quick.block_reason = "有新事件，请先由你作出选择。"
			CareerBridge.context.stories = [{"id":"contract", "title":"续约决定", "title_en":"Contract decision", "text":"决定下赛季的安排。", "text_en":"Decide your plans for next season.", "choices":[{"id":"stay","label":"留队","label_en":"Stay"}]},
				{"id":"birthday", "title":"队友生日", "title_en":"Teammate birthday", "text":"", "choices":[]}]
			Computer._rebuild(); await frames()
			agenda = Computer.content.find_child("CareerBreakAgenda", true, false)
			check(texts(agenda).contains(Locale.field(CareerBridge.context.stories[0], "title")) and texts(agenda).contains(Locale.field(CareerBridge.context.stories[1], "title")), "pending event titles visible")
			check(agenda.find_children("*", "Button", true, false).size() == 1, "first event has inline decision")
			check(Computer.content.find_child("EndCareerBreak", true, false).disabled, "required decisions block finish")
			count = sent.size(); center.pace.start(); center.process(60)
			check(sent.size() == count, "auto cannot skip event")
			center.result = {"played":true,"series":[2,0]}; center.reveal_phase = "stats"
			check(center.pace.plan().primary == "查看休赛安排", "completed report points to break instead of another match")
			center.pace.primary(); await frames()
			check(center.result.is_empty() and Computer.content.find_child("CareerBreakAgenda", true, false) != null and sent.size() == count, "report hands back to break without simulating")
			if "--capture-market" in OS.get_cmdline_user_args():
				await RenderingServer.frame_post_draw
				DirAccess.make_dir_recursive_absolute("res://temp")
				get_viewport().get_texture().get_image().save_png("res://temp/break-" + language + "-" + str(resolution.x) + ".png")
			var focus := VBoxContainer.new(); add_child(focus)
			preload("res://scripts/map_form_panel.gd").mount(focus, [{"map":"mirage","strength":89.5,"practice_ceiling":90,"form":-1,"rating":88.5,"recent":[],"label":"strong"}])
			check(texts(focus).contains(Locale.text("专项训练可恢复至 %.1f" % 90.0)), "map recovery limit shown")
			focus.free()
	print("BREAK_TRAINING_UI_RESULT checks=", checks, " failures=", failures)
	get_tree().quit(0 if failures.is_empty() else 1)
