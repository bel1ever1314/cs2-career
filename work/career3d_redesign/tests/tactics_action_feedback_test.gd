extends Node
## Isolated UI fixture: clipboard and service writes are captured, never sent.
var checks := 0
var failures: Array[String] = []
var requests: Array = []
var clipboard_value := ""
var clipboard_writes: Array[String] = []
var allow_clipboard := true
var allow_requests := true

func _ready() -> void:
	call_deferred("run")

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("TACTICS_ACTION_FEEDBACK_CHECK ", "PASS " if ok else "FAIL ", label)

func settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame

func fixture_tactic(ident: String) -> Dictionary:
	var value := {"id":ident, "name":"战术 " + ident, "side":"t", "slots":[]}
	for number in range(1, 6): value.slots.append({"slot":number, "steps":[], "duty":"auto"})
	return value

func fixture_library() -> Dictionary:
	return {"ok":true, "schema_version":1, "map":"de_dust2", "tactics":[fixture_tactic("alpha"), fixture_tactic("beta")],
		"map_meta":{"pos_x":0, "pos_y":1000, "scale":1, "width":1000, "height":1000, "image_path":"res://tactics-radar.png"},
		"available_maps":[{"map":"de_dust2", "name":"Dust II"}]}

func write_clipboard(value: String) -> bool:
	clipboard_writes.append(value)
	if allow_clipboard: clipboard_value = value
	return allow_clipboard

func send_command(path: String, body: Dictionary) -> bool:
	requests.append({"path":path, "body":body.duplicate(true)})
	return allow_requests

func feedback_is(kind: String, words: String) -> bool:
	return Computer.action_feedback.visible and Computer.action_feedback.current_kind == kind and words in Computer.action_feedback.current_message

func click_copy(editor) -> void:
	editor.controls.TacticsCopyCommand.pressed.emit()

func run() -> void:
	get_viewport().size = Vector2i(1280, 720)
	CareerBridge.connected = true
	CareerBridge.clock_held = true
	CareerBridge.context = {"date":"2026-10-03", "calendar":{"revision":27}, "player":{"id":"fixture", "name":"测试"}, "inbox":[], "calendar_events":[]}
	var editor = Computer.tactics
	editor.command_sender = send_command
	editor.clipboard_writer = write_clipboard
	editor.clipboard_reader = func() -> String: return clipboard_value
	editor.libraries = {"de_dust2":fixture_library()}
	Computer.present("club")
	Computer._navigate("tactics", false)
	await settle()
	var feedback = Computer.action_feedback
	check(is_instance_valid(feedback) and feedback.is_inside_tree(), "computer owns a fixed action-feedback panel")
	check(not Computer.scroll.is_ancestor_of(feedback), "result panel is outside the scrolling editor")
	check(feedback.mouse_filter == Control.MOUSE_FILTER_IGNORE and feedback.surface.mouse_filter == Control.MOUSE_FILTER_IGNORE and feedback.text_label.mouse_filter == Control.MOUSE_FILTER_IGNORE, "feedback overlay never intercepts a second click")
	editor.draft.id = "unsaved_route"
	editor.draft.name = "草稿路线"
	editor.changed()
	var view_id: int = editor.view.get_instance_id()
	var canvas_id: int = editor.canvas.get_instance_id()
	var name_input: LineEdit = editor.controls.TacticsName
	var button: Button = editor.controls.TacticsCopyCommand
	var button_id := button.get_instance_id()
	var draft_before: Dictionary = editor.draft.duplicate(true)
	Computer.scroll.scroll_vertical = 380
	await settle()
	var scroll_before: int = Computer.scroll.scroll_vertical
	name_input.grab_focus()
	name_input.caret_column = 2
	click_copy(editor)
	check(clipboard_value == "play unsaved_route" and clipboard_writes == ["play unsaved_route"], "pressed signal copies the actual editable play ID")
	check(button.text == "已复制 ✓" and editor.copied_command == clipboard_value, "copy button acknowledges the verified clipboard value")
	check(editor.copy_feedback_deadline_msec > Time.get_ticks_msec(), "button acknowledgement has a temporary expiry")
	check(feedback_is("success", "play unsaved_route") and "草稿还没保存" in feedback.current_message, "fixed notice confirms copy but warns that the draft is unsaved")
	check(editor.controls.notice.text == editor.notice and "已复制" in editor.notice, "existing editor notice also shows the copy result")
	check(requests.is_empty() and editor.pending_action.is_empty() and editor.pending_path.is_empty(), "copy never starts a backend request")
	check(editor.draft == draft_before and editor.dirty and editor.original_id.is_empty(), "copy never saves or modifies the unsaved draft")
	check(editor.view.get_instance_id() == view_id and editor.canvas.get_instance_id() == canvas_id and button.get_instance_id() == button_id, "copy retains view canvas and button instances")
	check(Computer.scroll.scroll_vertical == scroll_before, "copy does not jump the page scroll")
	check(get_viewport().gui_get_focus_owner() == name_input and name_input.caret_column == 2, "copy feedback preserves focused input and caret")
	await settle()
	check(feedback.surface.get_global_rect().intersects(Computer.panel.get_global_rect()) and feedback.text_label.is_visible_in_tree(), "copy result remains visible while the editor is scrolled")
	editor.set_draft(fixture_tactic("alpha"))
	editor.refresh(true)
	check(button.text == "复制指令", "loading a different ID clears the old copied caption")
	click_copy(editor)
	check(clipboard_value == "play alpha" and feedback_is("success", "准备阶段"), "saved tactic copies its own command and gives paste instructions")
	check("草稿还没保存" not in feedback.current_message and not editor.dirty, "saved tactic is not falsely labelled unsaved")
	editor.draft.name = "修改了的 alpha"
	editor.changed()
	click_copy(editor)
	check(feedback_is("success", "草稿还没保存") and clipboard_value == "play alpha", "dirty saved tactic warns that changed content still needs saving")
	var first_deadline: int = editor.copy_feedback_deadline_msec
	await settle()
	click_copy(editor)
	check(editor.copy_feedback_deadline_msec >= first_deadline and button.text == "已复制 ✓", "repeated copy refreshes the acknowledgement lifetime")
	editor.copy_feedback_deadline_msec = Time.get_ticks_msec() - 1
	editor.refresh_copy_caption()
	check(button.text == "复制指令", "expired acknowledgement restores the original caption")
	click_copy(editor)
	await get_tree().create_timer(2.75).timeout
	check(button.text == "复制指令", "scheduled timer expires the copy caption without rebuilding the view")
	editor.set_draft(fixture_tactic("beta"))
	editor.refresh(true)
	click_copy(editor)
	await get_tree().create_timer(2.35).timeout
	editor.draft.id = "gamma"
	editor.changed()
	check(button.text == "复制指令", "editing the ID cannot retain acknowledgement for the previous command")
	click_copy(editor)
	await get_tree().create_timer(0.35).timeout
	check(clipboard_value == "play gamma" and button.text == "已复制 ✓", "new ID receives its own acknowledgement even after an older copy timer")
	var count_before := clipboard_writes.size()
	allow_clipboard = false
	click_copy(editor)
	check(feedback_is("error", "没有复制成功") and button.text == "复制指令" and editor.copied_command.is_empty(), "failed clipboard write cannot show a false copied state")
	check(clipboard_writes.size() == count_before + 1, "clipboard failure still records the attempted command")
	allow_clipboard = true
	editor.clipboard_reader = func() -> String: return "unrelated clipboard text"
	click_copy(editor)
	check(feedback_is("error", "没有复制成功") and button.text == "复制指令", "mismatched clipboard readback is reported as an error")
	editor.clipboard_reader = func() -> String: return clipboard_value
	editor.draft.id = "Invalid ID"
	editor.changed()
	count_before = clipboard_writes.size()
	editor.copy_command()
	check(button.disabled and clipboard_writes.size() == count_before and feedback_is("error", "有效的战术 ID"), "invalid IDs never reach the clipboard or report success")
	editor.set_draft(fixture_tactic("alpha"))
	editor.refresh(true)
	CareerBridge.busy = true
	CareerBridge.active_post = true
	editor.refresh()
	check(not button.disabled, "pending service write does not lock a local copy")
	click_copy(editor)
	check(clipboard_value == "play alpha" and requests.is_empty(), "copy works during a pending unrelated service write")
	CareerBridge.busy = false
	CareerBridge.active_post = false
	editor.refresh()
	var notices_before: int = feedback.shown_count
	var message_before: String = feedback.current_message
	editor.finished("/api/3d/tactics?map=de_dust2", fixture_library())
	check(feedback.shown_count == notices_before and feedback.current_message == message_before, "ordinary GET polling never manufactures a result toast")
	editor.finished("/api/3d/tactics/save", {"ok":true, "map":"de_dust2", "tactic":fixture_tactic("alpha"), "tactics":[fixture_tactic("alpha")]})
	check(feedback.shown_count == notices_before, "unsolicited save response never claims an initiated save succeeded")
	editor.draft.name = "收到旧结果以后仍要保留的草稿"
	editor.changed()
	var protected_draft: Dictionary = editor.draft.duplicate(true)
	var protected_library: Dictionary = editor.library().duplicate(true)
	for action in ["save", "delete", "import"]:
		editor.finished("/api/3d/tactics/" + action, {"ok":true, "map":"de_dust2", "tactic":fixture_tactic("beta"), "tactics":[fixture_tactic("beta")]})
		check(editor.draft == protected_draft and editor.library() == protected_library and editor.dirty and feedback.shown_count == notices_before, "duplicate or foreign %s response never overwrites a newer dirty draft or library" % action)
	editor.pending_path = "/api/3d/tactics?map=de_dust2"
	editor.pending_map = "de_dust2"
	editor.pending_read_feedback = true
	editor.finished(editor.pending_path, fixture_library())
	check(feedback_is("success", "战术列表已更新") and not editor.pending_read_feedback, "explicit reread owns its success result unlike ordinary polling")
	editor.pending_path = "/api/3d/tactics?map=de_dust2"
	editor.pending_map = "de_dust2"
	editor.pending_read_feedback = true
	editor.finished(editor.pending_path, {"ok":false, "map":"de_dust2", "reason":"fixture reread failure"})
	check(feedback_is("error", "fixture reread failure") and not editor.pending_read_feedback, "explicit reread failure produces an owned error result")
	editor.draft.name = "待保存名称"
	editor.changed()
	editor.controls.TacticsSave.pressed.emit()
	check(requests.size() == 1 and requests[-1].path == "/api/3d/tactics/save" and requests[-1].body.revision == 27, "save button still submits only its original service contract")
	check(feedback_is("progress", "正在保存") and editor.pending_action == "save", "accepted save displays progress rather than premature success")
	click_copy(editor)
	check(feedback_is("success", "已复制") and editor.pending_action == "save", "copy briefly acknowledges locally without completing the pending save")
	feedback._process(5.0)
	check(feedback_is("progress", "正在保存"), "copy toast expiry restores the still-pending save progress")
	editor.finished("/api/3d/tactics/save", {"ok":false, "reason":"fixture save failure", "map":"de_dust2"})
	check(feedback_is("error", "fixture save failure") and editor.dirty and editor.pending_action.is_empty(), "save failure is visible and retains the unsaved draft")
	feedback._process(8.0)
	check(not feedback.visible, "failed save result removes pending progress permanently after error toast expires")
	editor.controls.TacticsSave.pressed.emit()
	click_copy(editor)
	feedback._process(5.0)
	check(feedback_is("progress", "正在保存"), "a new pending save also survives an intervening copy toast")
	editor.finished("/api/3d/tactics/save", {"ok":true, "map":"de_dust2", "tactic":editor.draft.duplicate(true), "tactics":[editor.draft.duplicate(true)], "msg":"战术已保存。"})
	check(feedback_is("success", "战术已保存") and not editor.dirty, "matching save response shows verified success")
	feedback._process(8.0)
	check(not feedback.visible, "successful save result removes pending progress permanently after success toast expires")
	allow_requests = false
	editor.controls.TacticsSave.pressed.emit()
	check(feedback_is("error", "请求未发送") and editor.pending_action.is_empty(), "unaccepted service request is an error not progress or success")
	allow_requests = true
	var requests_before := requests.size()
	editor.import_json("not JSON")
	check(feedback_is("error", "JSON 无效") and requests.size() == requests_before, "invalid import is immediately visible without a write")
	editor.import_file("res://tests-output/no-such-tactic.json")
	check(feedback_is("error", "无法读取"), "missing import file gives visible failure")
	editor.import_json(JSON.stringify({"map":"de_dust2", "tactic":fixture_tactic("incoming")}))
	check(feedback_is("progress", "正在导入") and editor.pending_action == "import", "accepted import displays progress until its own response")
	editor.finished("/api/3d/tactics/import", {"ok":false, "map":"de_dust2", "reason":"fixture import failure"})
	check(feedback_is("error", "fixture import failure"), "failed import receives a visible error result")
	editor.import_json(JSON.stringify({"map":"de_dust2", "tactic":fixture_tactic("incoming")}))
	editor.finished("/api/3d/tactics/import", {"ok":true, "map":"de_dust2", "tactics":[fixture_tactic("incoming")], "msg":"导入已完成。"})
	check(feedback_is("success", "导入已完成") and editor.original_id == "incoming", "successful import gives feedback and selects the canonical saved tactic")
	var output_folder := ProjectSettings.globalize_path("res://tests-output")
	DirAccess.make_dir_recursive_absolute(output_folder)
	var export_path := output_folder.path_join("action-feedback-tactic.json")
	editor.export_file(export_path)
	var exported = JSON.parse_string(FileAccess.get_file_as_string(export_path))
	check(feedback_is("success", "已导出草稿") and exported is Dictionary and exported.tactic.id == "incoming", "export success is shown only after the actual fixture file is written")
	editor.export_file(output_folder.path_join("not-created/export.json"))
	check(feedback_is("error", "无法写入"), "unwritable export destination cannot report success")
	check(editor.view.get_instance_id() == view_id and editor.canvas.get_instance_id() == canvas_id, "all action feedback preserves the existing editor and canvas")
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service and CareerBridge.runtime_dir.is_empty(), "fixture never starts a service or opens a live save")
	print("TACTICS_ACTION_FEEDBACK_RESULT ", JSON.stringify({"checks":checks, "failures":failures, "requests":requests.size()}))
	get_tree().quit(0 if failures.is_empty() else 1)
