extends Node
## Isolated native fixtures: no service, user save, charge, or odds are changed.
const DrawReel = preload("res://scripts/draw_reel.gd")
var failures: Array[String] = []
var checks := 0
var calls: Array = []
var reveal_count := 0
var received: Dictionary = {}
const DROP := {"id":"fixture-redline", "name":"AK-47 | Redline", "weapon":"AK-47", "rarity":"classified", "wear":0.126, "sell":900, "spot":1000, "case":"轮播验证箱"}

func _ready() -> void:
	call_deferred("run")

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("CASE_REEL_CHECK ", "PASS " if value else "FAIL ", label)

func settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame

func _send(path: String, body: Dictionary) -> bool:
	calls.append({"path":path, "body":body.duplicate(true)})
	return true

func _on_revealed(result: Dictionary) -> void:
	reveal_count += 1
	received = result.duplicate(true)

func capture(name: String) -> void:
	if DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	var directory := ""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--capture-dir="): directory = argument.trim_prefix("--capture-dir=")
	if directory.is_empty(): return
	DirAccess.make_dir_recursive_absolute(directory)
	var output := directory.path_join(name + ".png")
	check(get_viewport().get_texture().get_image().save_png(output) == OK, "native screenshot saved " + name)
	print("CASE_REEL_CAPTURE ", output)

func run() -> void:
	get_viewport().size = Vector2i(1280, 890)
	CareerBridge.connected = true
	CareerBridge.connecting = false
	CareerBridge.busy = false
	CareerBridge.clock_held = true
	CareerBridge.context = {"date":"2026-10-02", "calendar":{"revision":7}, "money":5000, "skins":{
		"personal_money":5000, "pending":null, "inventory":[],
		"cases":[{"id":"fixture-case", "name":"轮播验证箱", "price":220, "key":160, "drops":["fixture-slate", "fixture-lotus", "fixture-redline"]}],
		"market":[{"id":"fixture-slate", "name":"AK-47 | Slate", "weapon":"AK-47", "rarity":"milspec"}, {"id":"fixture-lotus", "name":"M4A1-S | Black Lotus", "weapon":"M4A1-S", "rarity":"restricted"}, DROP.duplicate(true)]}}
	var solo := DrawReel.new()
	add_child(solo)
	solo.size = Vector2(820, 214)
	solo.revealed.connect(_on_revealed)
	var attribute_result := {"name":"狙击", "value":68, "rarity":"潜力", "color":"9278ae"}
	check(solo.start([{"name":"步枪", "value":74, "color":"668bb7"}, attribute_result], attribute_result), "generic dictionary reel starts")
	solo.set_process(false)
	check(not solo.start([], {"name":"wrong", "value":99}), "running reel rejects replacement")
	var previous := solo.offset
	solo.advance(1.0)
	var fast := solo.offset - previous
	previous = solo.offset
	solo.advance(1.0)
	var slower := solo.offset - previous
	check(fast > slower and slower > 0 and solo.is_running(), "horizontal movement decelerates")
	solo.advance(1.999)
	check(solo.is_running() and reveal_count == 0, "does not reveal before four seconds")
	solo.advance(0.001)
	check(not solo.is_running() and reveal_count == 1 and received == attribute_result, "four seconds reveals committed attribute unchanged")
	check(is_equal_approx(solo.result_center_x(), solo.size.x / 2.0), "committed result stops at central pointer")
	solo.skip()
	check(reveal_count == 1, "completed skip does not emit a second result")
	solo.queue_free()
	await settle()
	Computer.market_tab = "cases"
	Computer.open_app("market", "bedroom")
	Computer.case_room.command_sender = _send
	Computer._skin_command("case", {"id":"fixture-case"})
	Computer._skin_command("case", {"id":"fixture-case"})
	check(calls.size() == 1 and calls[0].body.revision == 7, "one case request while response pending")
	check(not Computer.case_room.is_running(), "animation waits for committed backend drop")
	CareerBridge.context.skins.pending = DROP.duplicate(true)
	CareerBridge.context.skins.personal_money = 4620
	Computer._finished("/api/3d/skins/case", {"ok":true, "reason":"开出 AK-47 | Redline。"})
	await settle()
	var case_reel: Control = Computer.case_room.reel
	case_reel.set_process(false)
	case_reel.advance(0.72)
	await settle()
	check(case_reel.is_running() and case_reel.size.x > 600 and case_reel.is_visible_in_tree(), "visible native reel spans the dialog")
	check(Computer.status.text == "正在开箱……", "status does not reveal the result early")
	check(not Computer.case_room.decisions.visible and Computer.case_room.skip_button.visible, "skip visible while receipt decisions wait")
	Computer._skin_command("keep", {})
	check(calls.size() == 1, "receipt cannot be collected during animation")
	var identity := case_reel.get_instance_id()
	CareerBridge.context.skins.pending.spot = 1110
	Computer._context_changed()
	Computer._rebuild()
	await settle()
	check(Computer.case_room.reel.get_instance_id() == identity and case_reel.is_running(), "poll and page rebuild preserve the playing reel")
	Computer._finished("/api/3d/skins/case", {"ok":true})
	check(Computer.case_room.reel.get_instance_id() == identity, "duplicate receipt response does not replay")
	await capture("case-reel-moving")
	Computer.case_room.skip_button.pressed.emit()
	await settle()
	check(case_reel.completed and is_equal_approx(case_reel.result_center_x(), case_reel.size.x / 2.0), "skip lands saved skin at central pointer")
	check(case_reel.result.id == DROP.id and CareerBridge.context.skins.pending.wear == DROP.wear, "skip preserves paid skin and wear")
	check(Computer.case_room.decisions.visible and not Computer.case_room.keep_button.disabled, "receipt actions unlock after reveal")
	await capture("case-reel-revealed")
	Computer._skin_command("keep", {})
	Computer._skin_command("keep", {})
	Computer._skin_command("cash", {})
	check(calls.size() == 2 and calls[1].path.ends_with("/keep"), "pending decision cannot submit twice")
	Computer._finished("/api/3d/skins/keep", {"ok":false, "reason":"测试拒绝"})
	check(not Computer.case_room.decision_pending and not Computer.case_room.keep_button.disabled, "rejected receipt decision can be retried")
	Computer._skin_command("keep", {})
	CareerBridge.context.skins.pending = null
	CareerBridge.context.skins.inventory = [DROP.duplicate(true)]
	Computer._finished("/api/3d/skins/keep", {"ok":true})
	await settle()
	check(calls.size() == 3 and not Computer.case_room.overlay.visible, "successful receipt resolution closes reveal")
	Computer._context_changed()
	check(not Computer.case_room.overlay.visible and CareerBridge.context.skins.inventory.size() == 1, "resolved receipt poll does not replay or duplicate inventory")
	Computer._skin_command("case", {"id":"fixture-case"})
	CareerBridge.context.skins.pending = DROP.duplicate(true)
	Computer._finished("/api/3d/skins/case", {"ok":true})
	await settle()
	case_reel = Computer.case_room.reel
	case_reel.set_process(false)
	check(case_reel.is_running(), "a new paid receipt animates even when its drop matches the previous one")
	identity = case_reel.get_instance_id()
	Computer.close_computer()
	case_reel.advance(0.4)
	var saved_offset: float = case_reel.offset
	Computer.present("bedroom")
	await settle()
	check(case_reel.get_instance_id() == identity and case_reel.offset == saved_offset and case_reel.is_visible_in_tree(), "closing and reopening preserve the same reel progress")
	case_reel.skip()
	Computer.case_room._later()
	Computer._context_changed()
	Computer._rebuild()
	await settle()
	check(not Computer.case_room.overlay.visible and not case_reel.is_running() and not Computer.case_room.pending().is_empty(), "saved unresolved result returns without replay after later or a poll")
	Computer.case_room.command_sender = Callable()
	print("CASE_REEL_RESULT ", JSON.stringify({"ok":failures.is_empty(), "checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
