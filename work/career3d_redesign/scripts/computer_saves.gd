extends RefCounted
## A manual-slot client only. CareerBridge owns transport and loaded contexts.
const UI = preload("res://scripts/computer_ui.gd")
const INDEX_PATH := "/api/3d/saves"
const ACTIONS := ["save", "load", "delete"]
var host: Node
var data: Dictionary = {}
var draft := ""
var notice := ""
var read_notice := false
var pending_path := ""
var requested_once := false
var needs_refresh := true
var uncertain_write := false
var confirmation: Dictionary = {}
var command_sender: Callable
var controls: Dictionary = {}
var focus_after_render := false
var saved_caret := 0
var saved_selection := Vector2i(-1, -1)

func attach(value: Node) -> void:
	host = value

func _active() -> bool:
	return is_instance_valid(host) and is_instance_valid(host.screen) and host.screen.visible and host.active_page == "saves"

func is_editing() -> bool:
	return is_instance_valid(controls.get("name")) and controls.name.has_focus()

func render(parent: Node) -> void:
	controls.clear()
	var view := VBoxContainer.new()
	view.name = "ComputerSaveManager"
	view.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	view.add_theme_constant_override("separation", 12)
	parent.add_child(view)
	UI.label(view, "存档", 25)
	var current := UI.card(view)
	UI.label(current, "当前进度 · 自动保存", 18)
	var state: Dictionary = data.get("current", {})
	UI.label(current, _summary(state), 15)
	UI.label(current, "保存时间：%s  ·  %s" % [_stamp(state.get("saved_at", "")), _mb(state.get("size_bytes", 0))], 12, UI.MUTED)
	var form := UI.card(view)
	UI.label(form, "另存一份", 18)
	var name_field := LineEdit.new()
	name_field.name = "ComputerSaveName"
	name_field.text = draft
	name_field.placeholder_text = "存档名称"
	name_field.max_length = 64
	name_field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	UI.line_edit(name_field)
	form.add_child(name_field)
	controls.name = name_field
	name_field.text_changed.connect(func(value: String): draft = value; _update_controls())
	name_field.text_submitted.connect(func(_value: String): save())
	var form_actions := HFlowContainer.new()
	form_actions.add_theme_constant_override("h_separation", 10)
	form.add_child(form_actions)
	controls.save = _button(form_actions, "保存", save, "ComputerSaveCreate")
	UI.primary(controls.save)
	controls.refresh = _button(form_actions, "重新读取", fetch.bind(true), "ComputerSaveRefresh", false)
	controls.status = UI.label(view, _status_text(), 13, UI.MUTED)
	if bool(data.get("blocked", false)):
		UI.label(view, "当前不能保存或读档：" + str(data.get("reason", "请先完成当前操作。")), 13, UI.MUTED)
	UI.label(view, "手动存档 · %d" % data.get("slots", []).size(), 18)
	var slot_controls := []
	for slot in data.get("slots", []):
		var card := UI.card(view)
		var id := str(slot.get("id", ""))
		card.name = "ComputerSaveSlot_" + id.validate_node_name()
		UI.label(card, str(slot.get("label", "未命名存档")), 17)
		UI.label(card, _summary(slot), 14)
		UI.label(card, "保存时间：%s  ·  %s" % [_stamp(slot.get("created_at", "")), _mb(slot.get("size_bytes", 0))], 12, UI.MUTED)
		if not confirmation.is_empty() and str(confirmation.id) == id:
			_render_confirmation(card)
			continue
		var actions := HFlowContainer.new()
		actions.add_theme_constant_override("h_separation", 10)
		card.add_child(actions)
		var load_button := _button(actions, "读档", begin_confirmation.bind("load", id), "ComputerSaveLoad_" + id.validate_node_name())
		var delete_button := _button(actions, "删除", begin_confirmation.bind("delete", id), "ComputerSaveDelete_" + id.validate_node_name())
		slot_controls.append({"kind":"load", "node":load_button})
		slot_controls.append({"kind":"delete", "node":delete_button})
	controls.slots = slot_controls
	if data.has("slots") and data.slots.is_empty(): UI.label(view, "还没有手动存档。", 14, UI.MUTED)
	_update_controls()
	if focus_after_render:
		focus_after_render = false
		_restore_input.call_deferred()

func _render_confirmation(parent: Node) -> void:
	# Confirm beside the chosen slot, not offscreen above a long list.
	var box := VBoxContainer.new()
	box.name = "ComputerSaveConfirmation"
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_theme_constant_override("separation", 8)
	parent.add_child(box)
	var loading: bool = confirmation.kind == "load"
	UI.label(box, ("读取「%s」？" if loading else "删除「%s」？") % confirmation.label, 17)
	UI.label(box, "当前进度会切换到这份存档。" if loading else "只删除这份手动存档。", 13, UI.MUTED)
	var choices := HFlowContainer.new()
	choices.add_theme_constant_override("h_separation", 10)
	box.add_child(choices)
	controls.confirm = _button(choices, "确认读取" if loading else "确认删除", confirm_action, "ComputerSaveConfirm")
	controls.cancel = _button(choices, "取消", cancel_confirmation, "ComputerSaveCancel", false)

func _button(parent: Node, text: String, callback: Callable, name: String, write: bool = true) -> Button:
	var button: Button = host._button(parent, text, callback, write)
	button.name = name
	return button

func _name(value: Variant, fallback: String) -> String:
	var text := str(value.get("name", "")) if value is Dictionary else str(value) if value != null else ""
	return fallback if text.is_empty() else text

func _summary(value: Dictionary) -> String:
	return "%s  ·  %s\n%s  ·  %s 开局" % [_name(value.get("player", ""), "暂无生涯"), _name(value.get("team", ""), "暂无队伍"), str(value.get("date", "—")), str(value.get("era", "—"))]

func _stamp(value: Variant) -> String:
	return "—" if str(value).is_empty() else str(value).replace("T", " ")

func _mb(value: Variant) -> String:
	return "%.2f MB" % (maxf(0, float(value)) / 1048576.0)

func _status_text() -> String:
	if not notice.is_empty(): return notice
	return "正在读取存档……" if pending_path == INDEX_PATH else ""

func _gate(kind: String) -> bool:
	if not _active() or not pending_path.is_empty() or needs_refresh or uncertain_write or data.is_empty() or not CareerBridge.connected or CareerBridge.busy: return false
	return kind == "delete" or not bool(data.get("blocked", false))

func _disabled(button: Button, value: bool) -> void:
	button.disabled = value
	button.set_meta("career_gate_disabled", value)

func _update_controls() -> void:
	if not is_instance_valid(controls.get("name")): return
	controls.name.editable = pending_path.is_empty() or pending_path == INDEX_PATH
	_disabled(controls.save, not _gate("save") or draft.strip_edges().is_empty())
	controls.refresh.disabled = not pending_path.is_empty() or CareerBridge.busy
	controls.status.text = _status_text()
	for slot in controls.get("slots", []): _disabled(slot.node, not _gate(str(slot.kind)))
	if is_instance_valid(controls.get("confirm")):
		_disabled(controls.confirm, not _gate(str(confirmation.get("kind", ""))))
		controls.cancel.disabled = not pending_path.is_empty()

func _redraw() -> void:
	if not _active(): return
	if is_editing():
		focus_after_render = true
		saved_caret = controls.name.caret_column
		saved_selection = Vector2i(controls.name.get_selection_from_column(), controls.name.get_selection_to_column()) if controls.name.has_selection() else Vector2i(-1, -1)
	host._rebuild()

func _restore_input() -> void:
	if not _active() or not is_instance_valid(controls.get("name")): return
	controls.name.grab_focus()
	controls.name.caret_column = mini(saved_caret, draft.length())
	if saved_selection.x >= 0: controls.name.select(saved_selection.x, saved_selection.y)

func fetch(force: bool = false) -> void:
	if not _active() or not pending_path.is_empty() or (requested_once and not needs_refresh and not force): return
	if not CareerBridge.connected or CareerBridge.busy:
		if notice.is_empty():
			notice = "后台暂未连接。" if not CareerBridge.connected else "正在同步，请稍后重新读取。"
			read_notice = true
		_update_controls()
		return
	pending_path = INDEX_PATH
	if _send(INDEX_PATH, {}, false): requested_once = true
	else:
		pending_path = ""
		needs_refresh = true
		notice = CareerBridge.message if not CareerBridge.message.is_empty() else "存档列表未读取，请稍后重试。"
		read_notice = true
	_update_controls()

func _send(path: String, payload: Dictionary, post: bool) -> bool:
	if command_sender.is_valid(): return bool(command_sender.call(path, payload, post))
	return CareerBridge.command(path, payload) if post else CareerBridge._send(path, payload, false)

func _slot(id: String) -> Dictionary:
	for slot in data.get("slots", []):
		if str(slot.get("id", "")) == id: return slot
	return {}

func save() -> void:
	var label := draft.strip_edges()
	if not _gate("save") or label.is_empty() or label.length() > 64: return
	_request("save", {"label":label})

func begin_confirmation(kind: String, id: String) -> void:
	if kind not in ["load", "delete"] or not _gate(kind): return
	var slot := _slot(id)
	if slot.is_empty(): return
	confirmation = {"kind":kind, "id":id, "label":str(slot.get("label", "未命名存档"))}
	_redraw()

func cancel_confirmation() -> void:
	if not pending_path.is_empty(): return
	confirmation.clear()
	_redraw()

func confirm_action() -> void:
	if confirmation.is_empty(): return
	var kind := str(confirmation.kind)
	if not _gate(kind) or _slot(str(confirmation.id)).is_empty(): return
	_request(kind, {"id":str(confirmation.id), "confirm":true})

func _request(kind: String, payload: Dictionary) -> void:
	if kind not in ACTIONS or not _gate(kind): return
	payload = payload.duplicate(true)
	payload["revision"] = int(CareerBridge.context.get("calendar", {}).get("revision", 0))
	payload["request_id"] = "saveui-" + Crypto.new().generate_random_bytes(16).hex_encode()
	pending_path = INDEX_PATH + "/" + kind
	if _send(pending_path, payload, true): confirmation.clear()
	else:
		pending_path = ""
		notice = CareerBridge.message if not CareerBridge.message.is_empty() else "操作未发出，请稍后重试。"
		read_notice = false
	_redraw()

func received(path: String, result: Dictionary) -> bool:
	if pending_path.is_empty() or path != pending_path: return false
	pending_path = ""
	if path == INDEX_PATH:
		if result.get("ok", false):
			if uncertain_write: notice = "存档列表已更新。"
			elif read_notice: notice = ""
			read_notice = false
			data = {"revision":result.get("revision", 0), "current":result.get("current", {}).duplicate(true), "slots":[], "blocked":bool(result.get("blocked", false)), "reason":str(result.get("reason", ""))}
			for slot in result.get("slots", []):
				if slot is Dictionary and not str(slot.get("id", "")).is_empty(): data.slots.append(slot.duplicate(true))
			needs_refresh = false
			uncertain_write = false
			if not confirmation.is_empty() and _slot(str(confirmation.id)).is_empty(): confirmation.clear()
		else:
			needs_refresh = true
			notice = str(result.get("reason", result.get("msg", "存档列表未读取，请重新读取。")))
			read_notice = true
		_redraw()
		return true
	var action := path.get_file()
	read_notice = false
	var succeeded: bool = bool(result.get("ok", false)) and (action != "load" or bool(result.get("loaded", false)))
	if succeeded:
		if action == "save": draft = ""
		notice = {"save":"已保存。", "load":"已读档。", "delete":"已删除。"}.get(action, "操作完成。")
	else:
		notice = str(result.get("reason", result.get("msg", "操作没有完成，请重试。")))
		if action == "load" and result.get("ok", false): notice = "读档没有完成，请重新读取。"
		if bool(result.get("outcome_unknown", false)):
			uncertain_write = true
			notice = "连接中断，结果尚未确认。请重新读取存档列表。"
	confirmation.clear()
	needs_refresh = true
	_redraw()
	fetch(true) # Read saved state only; never resend an uncertain write.
	return true
