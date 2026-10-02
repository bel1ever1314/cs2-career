extends Node
## Fake transport and manual slots only: no filesystem or live service access.
const Saves = preload("res://scripts/computer_saves.gd")
const UI = preload("res://scripts/computer_ui.gd")
const FIRST := "0123456789abcdef0123456789abcdef"
const SECOND := "abcdef0123456789abcdef0123456789"
var checks := 0
var failures: Array[String] = []
var host: FakeHost
var manager
var requests: Array = []
var allow_send := true

class FakeHost extends CanvasLayer:
	var screen: Control
	var content: VBoxContainer
	var active_page := "saves"
	var manager
	var redraws := 0
	func _ready() -> void:
		screen = PanelContainer.new()
		screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		screen.add_theme_stylebox_override("panel", UI.style(UI.CREAM, 24))
		add_child(screen)
		var scroll := ScrollContainer.new()
		scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
		screen.add_child(scroll)
		content = VBoxContainer.new()
		content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		scroll.add_child(content)
	func _button(parent: Node, text: String, callback: Callable, _write: bool = true) -> Button:
		return UI.button(parent, text, callback)
	func _rebuild() -> void:
		redraws += 1
		UI.clear(content)
		manager.render(content)

func _ready() -> void: call_deferred("run")

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("SAVES_CHECK ", "PASS " if value else "FAIL ", label)

func settle() -> void:
	for _index in range(4): await get_tree().process_frame

func send(path: String, body: Dictionary, post: bool) -> bool:
	requests.append({"path":path, "body":body.duplicate(true), "post":post})
	return allow_send

func fixture(blocked: bool = false) -> Dictionary:
	return {"ok":true, "revision":11, "current":{"player":"存档测试选手", "team":"FlyQuest", "date":"2026-10-02", "era":"2026", "size_bytes":1572864, "saved_at":"2026-10-02T12:00:00+08:00"},
		"slots":[{"id":FIRST,"label":"大赛前","player":"存档测试选手","team":"FlyQuest","date":"2026-09-28","era":"2026","created_at":"2026-10-01T21:00:00+08:00","size_bytes":2097152}, {"id":SECOND,"label":"2024 年开始的职业生涯","player":"另一位选手","team":"很长的测试俱乐部联合竞技青训队","date":"2024-01-03","era":"2024","created_at":"2026-09-30T09:00:00+08:00","size_bytes":524288}],
		"backups":[{"id":"legacy-safety-backup","label":"不应显示的自动安全备份"}],"blocked":blocked,"reason":"比赛尚未完成。" if blocked else ""}

func named(value: String) -> Control:
	return host.content.find_child(value, true, false) as Control

func labels() -> String:
	var values: PackedStringArray = []
	for label in host.content.find_children("*", "Label", true, false): values.append(label.text)
	return "\n".join(values)

func reply_index(blocked: bool = false) -> void:
	check(manager.received("/api/3d/saves", fixture(blocked)), "index reply is consumed")
	await settle()

func capture(name: String) -> void:
	if DisplayServer.get_name() == "headless": return
	var directory := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture-dir="): directory = arg.trim_prefix("--capture-dir=")
	if directory.is_empty(): return
	await RenderingServer.frame_post_draw
	check(get_viewport().get_texture().get_image().save_png(directory.path_join(name + ".png")) == OK, "native screenshot " + name)

func run() -> void:
	if "--no-service" not in OS.get_cmdline_user_args(): get_tree().quit(2); return
	CareerBridge.connected = true
	CareerBridge.busy = false
	CareerBridge.clock_held = true
	CareerBridge.context = {"player":{"id":"save-test"}, "calendar":{"revision":37}}
	var career_before := JSON.stringify(CareerBridge.context)
	get_window().content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	get_window().content_scale_size = Vector2i(1280,720)
	get_window().size = Vector2i(1280,720)
	host = FakeHost.new()
	add_child(host)
	manager = Saves.new()
	manager.attach(host)
	manager.command_sender = send
	host.manager = manager
	host._rebuild()
	check(named("ComputerSaveCreate").disabled, "save requires a read index and a nonempty name")
	CareerBridge.busy = true
	manager.fetch()
	check(requests.is_empty() and manager.read_notice, "navigation colliding with a poll waits without sending")
	CareerBridge.busy = false
	manager.fetch(); manager.fetch()
	check(requests.size() == 1 and requests[0].path == "/api/3d/saves" and not requests[0].post, "first fetch is read-only and duplicate navigation does not poll")
	await reply_index()
	check(manager.notice.is_empty(), "successful first read clears transient busy notice")
	check(labels().contains("FlyQuest") and labels().contains("2026 开局") and labels().contains("2026-09-28") and labels().contains("2026-10-01 21:00:00") and labels().contains("1.50 MB") and labels().contains("2.00 MB"), "identity date era timestamp and MB are rendered")
	check(not labels().contains("不应显示") and named("ComputerSaveSlot_legacy-safety-backup") == null, "legacy safety backups never enter manual-slot list")
	manager.fetch()
	check(requests.size() == 1, "cached navigation does not refetch automatically")
	var field := named("ComputerSaveName") as LineEdit
	check(field.max_length == 64, "name editor follows backend 64-character limit")
	field.text = "  决赛前的进度  "
	field.text_changed.emit(field.text)
	field.grab_focus()
	field.caret_column = 3
	CareerBridge.busy = true
	manager._update_controls()
	check(named("ComputerSaveCreate").disabled and named("ComputerSaveRefresh").disabled, "global bridge busy update visibly locks actions")
	CareerBridge.busy = false
	manager._update_controls()
	check(not named("ComputerSaveCreate").disabled and not named("ComputerSaveRefresh").disabled, "global bridge completion restores current domain gates")
	manager.fetch(true)
	await reply_index()
	field = named("ComputerSaveName") as LineEdit
	check(field.text == "  决赛前的进度  " and field.has_focus() and field.caret_column == 3, "read refresh preserves typed name focus and caret")
	manager.save(); manager.save()
	var saved: Dictionary = requests[-1]
	check(saved.path == "/api/3d/saves/save" and saved.post and saved.body.label == "决赛前的进度" and saved.body.revision == 37, "save uses trimmed label and current calendar revision not index revision")
	check(str(saved.body.request_id).length() >= 8 and requests.filter(func(row): return row.path == "/api/3d/saves/save").size() == 1, "stable pending write prevents double clicks")
	check(not field.editable or not (named("ComputerSaveName") as LineEdit).editable, "submitted save name is held while write is pending")
	manager.received("/api/3d/saves/save", {"ok":false,"reason":"测试保存失败"})
	check(manager.draft == "  决赛前的进度  " and requests[-1].path == "/api/3d/saves" and not requests[-1].post, "failed save preserves name and refreshes with GET only")
	await reply_index()
	check(manager.notice == "测试保存失败", "read reconciliation does not hide a failed save notice")
	manager.save()
	check(requests[-1].body.request_id != saved.body.request_id and str(requests[-1].body.request_id).length() <= 100, "new explicit actions use independent bounded request ids")
	manager.received("/api/3d/saves/save", {"ok":true,"context":{"calendar":{"revision":38}}})
	check(manager.draft.is_empty() and manager.notice == "已保存。", "successful save clears only submitted local draft")
	await reply_index()
	var before := requests.size()
	manager.begin_confirmation("load", FIRST)
	await settle()
	check(requests.size() == before and named("ComputerSaveConfirmation") != null, "read slot requires a separate confirmation before POST")
	manager.cancel_confirmation()
	await settle()
	check(requests.size() == before and named("ComputerSaveConfirmation") == null, "cancelled read changes no career state")
	manager.begin_confirmation("load", FIRST)
	manager.confirm_action(); manager.confirm_action()
	check(requests[-1].path == "/api/3d/saves/load" and requests[-1].body.id == FIRST and requests[-1].body.confirm and requests[-1].body.revision == 37, "confirmed read sends exact opaque slot id and explicit consent")
	check(requests.filter(func(row): return row.path == "/api/3d/saves/load").size() == 1, "read confirmation cannot send a duplicate load")
	manager.received("/api/3d/saves/load", {"ok":true,"loaded":true,"context":{"player":{"id":"loaded"}}})
	check(JSON.stringify(CareerBridge.context) == career_before, "module leaves loaded contexts and travel reset to bridge owner")
	await reply_index(true)
	check(named("ComputerSaveLoad_" + FIRST).disabled and not named("ComputerSaveDelete_" + FIRST).disabled, "match gate blocks save/load while manual-slot deletion remains available")
	before = requests.size()
	manager.begin_confirmation("delete", FIRST)
	await settle()
	check(requests.size() == before and (named("ComputerSaveConfirm") as Button).text == "确认删除", "delete requires a second explicit confirmation")
	check(named("ComputerSaveConfirmation").get_parent() == named("ComputerSaveSlot_" + FIRST), "confirmation stays beside selected slot in long lists")
	(host.screen.get_child(0) as ScrollContainer).scroll_vertical = 220
	await settle()
	await capture("computer-saves-delete-confirmation")
	manager.confirm_action(); manager.confirm_action()
	check(requests[-1].path == "/api/3d/saves/delete" and requests[-1].body.id == FIRST and requests[-1].body.confirm, "delete sends no directory or backup path")
	check(requests.filter(func(row): return row.path == "/api/3d/saves/delete").size() == 1, "pending deletion cannot be duplicated")
	manager.received("/api/3d/saves/delete", {"ok":true})
	await reply_index()
	manager.draft = "未知结果保留输入"
	host._rebuild()
	manager.save()
	CareerBridge.connected = false
	manager.received("/api/3d/saves/save", {"ok":false,"transport_failure":true,"outcome_unknown":true})
	var write_count := requests.filter(func(row): return row.post).size()
	manager.save(); manager.fetch(); manager.confirm_action()
	check(manager.uncertain_write and manager.draft == "未知结果保留输入" and requests.filter(func(row): return row.post).size() == write_count, "unknown write result is never automatically retried")
	CareerBridge.connected = true
	manager.fetch(true)
	await reply_index()
	check(not manager.uncertain_write and not named("ComputerSaveCreate").disabled, "successful explicit read reconciles unknown write before unlocking actions")
	allow_send = false
	before = requests.size()
	manager.save()
	check(manager.pending_path.is_empty() and manager.draft == "未知结果保留输入" and requests.size() == before + 1, "not-sent write releases pending form without erasing input")
	allow_send = true
	check(not manager.received("/api/3d/unrelated", {"ok":true}), "unrelated bridge replies are not consumed")
	manager.begin_confirmation("load", FIRST)
	manager.confirm_action()
	manager.received("/api/3d/saves/load", {"ok":true,"loaded":false})
	check(manager.notice.contains("读档没有完成"), "load is not claimed successful without explicit loaded marker")
	await reply_index()
	manager.fetch(true)
	before = requests.size()
	manager.received("/api/3d/saves", {"ok":false,"reason":"测试读取失败"})
	check(manager.needs_refresh and named("ComputerSaveCreate").disabled and requests.size() == before, "failed index read gates writes without automatic retry")
	manager.fetch(true)
	await reply_index(true)
	before = requests.size()
	manager.save(); manager.begin_confirmation("load", SECOND)
	check(requests.size() == before and manager.confirmation.is_empty(), "blocked gates are enforced by callbacks as well as disabled buttons")
	manager.fetch(true)
	await reply_index()
	manager.begin_confirmation("delete", SECOND)
	manager.fetch(true)
	var missing := fixture()
	missing.slots = []
	manager.received("/api/3d/saves", missing)
	await settle()
	before = requests.size()
	manager.confirm_action()
	check(manager.confirmation.is_empty() and requests.size() == before and labels().contains("还没有手动存档"), "missing slots clear stale confirmations and render honest empty state")
	manager.fetch(true)
	var redraws := host.redraws
	host.active_page = "profile"
	manager.received("/api/3d/saves", fixture())
	check(host.redraws == redraws and manager.data.slots.size() == 2, "late read updates cache but never redraws a different page")
	before = requests.size()
	manager.fetch(true)
	check(requests.size() == before, "hidden save page never polls")
	host.active_page = "saves"
	manager.notice = ""
	manager.draft = "我的手动存档"
	host._rebuild()
	(host.screen.get_child(0) as ScrollContainer).scroll_vertical = 0
	await settle()
	await capture("computer-saves-1280")
	get_window().content_scale_size = Vector2i(640,720)
	get_window().size = Vector2i(640,720)
	await settle()
	check(host.content.get_combined_minimum_size().x <= 640 - 48, "manual-slot cards and actions fit a narrow workstation")
	await capture("computer-saves-640")
	check(JSON.stringify(CareerBridge.context) == career_before, "all fake actions leave original career projection unchanged")
	print("SAVES_RESULT ", JSON.stringify({"checks":checks,"failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
