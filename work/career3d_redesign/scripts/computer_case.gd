extends RefCounted
## The service owns the paid drop. This module only presents and resolves it.
const UI = preload("res://scripts/computer_ui.gd")
const DrawReel = preload("res://scripts/draw_reel.gd")
var host: Node
var command_sender: Callable
var awaiting_case := false
var decision_pending := false
var requested_case: Dictionary = {}
var saved_drop: Dictionary = {}
var shown_key := ""
var overlay: Control
var popup: PanelContainer
var reel: Control
var phase: Label
var skip_button: Button
var decisions: HBoxContainer
var keep_button: Button
var cash_button: Button

func attach(value: Node) -> void:
	host = value

func pending() -> Dictionary:
	var value: Variant = host._skins().get("pending")
	return value if value is Dictionary else {}

func is_running() -> bool:
	return is_instance_valid(reel) and reel.is_running()

func locked() -> bool:
	return awaiting_case or decision_pending or is_running()

func _key(drop: Dictionary) -> String:
	# Quote changes during a context poll are not a new receipt.
	return JSON.stringify([drop.get("id", drop.get("skin_id", "")), drop.get("wear"), drop.get("case", "")])

func _send(action: String, data: Dictionary) -> bool:
	var body := data.duplicate(true)
	body["revision"] = int(CareerBridge.context.get("calendar", {}).get("revision", 0))
	if command_sender.is_valid(): return bool(command_sender.call("/api/3d/skins/" + action, body))
	return CareerBridge.command("/api/3d/skins/" + action, body)

func open(case_id: String) -> void:
	if locked() or not pending().is_empty(): return
	var box: Dictionary = {}
	for row in host._skins().get("cases", []):
		if str(row.get("id", "")) == case_id: box = row.duplicate(true)
	if box.is_empty(): return
	var cost := int(box.get("price", 0)) + int(box.get("key", 0))
	if float(host._skins().get("personal_money", 0)) < cost: return
	requested_case = box
	awaiting_case = true
	if not _send("case", {"id":case_id}):
		awaiting_case = false
		host.notice = CareerBridge.message
	host._busy_changed(CareerBridge.busy)

func resolve(action: String) -> void:
	if action not in ["keep", "cash"] or locked() or pending().is_empty(): return
	decision_pending = true
	if not _send(action, {}):
		decision_pending = false
		host.notice = CareerBridge.message
	refresh_buttons()
	host._busy_changed(CareerBridge.busy)

func finished(path: String, response: Dictionary) -> void:
	if path == "/api/3d/skins/case":
		var requested := awaiting_case
		awaiting_case = false
		if requested and response.get("ok", false) and not pending().is_empty():
			present_saved(requested_case, pending())
	elif path in ["/api/3d/skins/keep", "/api/3d/skins/cash"]:
		decision_pending = false
		if response.get("ok", false) and pending().is_empty():
			saved_drop.clear()
			shown_key = ""
			if is_instance_valid(overlay): overlay.hide()
	refresh_buttons()

func _card(row: Dictionary) -> Dictionary:
	var value := row.duplicate(true)
	value["label"] = str(row.get("name", "饰品"))
	value["value"] = str(row.get("weapon", "饰品"))
	value["rarity"] = host._rarity_label(str(row.get("rarity", "")))
	value["color"] = host._rarity_color(str(row.get("rarity", ""))).to_html(false)
	return value

func _pool(box: Dictionary) -> Array:
	var cards: Array = []
	var ids: Array = box.get("drops", [])
	for row in host._skins().get("market", []):
		if str(row.get("id", "")) in ids: cards.append(_card(row))
	# Optional extension cases may already carry a decorated pool.
	if cards.is_empty():
		for row in box.get("pool", []): cards.append(_card(row))
	return cards

func present_saved(box: Dictionary, drop: Dictionary) -> void:
	if drop.is_empty() or _key(drop) == shown_key or is_running(): return
	shown_key = _key(drop)
	saved_drop = drop.duplicate(true)
	# Pending drops use the same catalog artwork as their market item.
	for row in host._skins().get("market", []):
		if str(row.get("id", "")) == str(drop.get("id", drop.get("skin_id", ""))):
			saved_drop["art_path"] = row.get("art_path", "")
	_ensure_overlay()
	UI.clear(popup)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 13)
	popup.add_child(layout)
	UI.label(layout, str(box.get("name", drop.get("case", "武器箱"))), 22)
	UI.label(layout, "箱子与钥匙已扣费 · 结果已保存", 13, UI.MUTED)
	reel = DrawReel.new()
	reel.name = "CaseDrawReel"
	layout.add_child(reel)
	reel.revealed.connect(_revealed)
	phase = UI.label(layout, "正在开箱……", 17)
	phase.name = "CaseRevealPhase"
	skip_button = UI.button(layout, "跳过动画", reel.skip)
	skip_button.name = "CaseSkipAnimation"
	decisions = HBoxContainer.new()
	decisions.add_theme_constant_override("separation", 12)
	layout.add_child(decisions)
	keep_button = UI.button(decisions, "放入库存", resolve.bind("keep"))
	keep_button.name = "CaseKeepDrop"
	UI.primary(keep_button)
	cash_button = UI.button(decisions, "立即出售 · %s" % preload("res://scripts/ui_format.gd").money(drop.get("sell", 0)), resolve.bind("cash"))
	cash_button.name = "CaseCashDrop"
	UI.button(decisions, "稍后处理", _later)
	decisions.hide()
	overlay.show()
	resize()
	reel.start(_pool(box), _card(saved_drop))
	skip_button.grab_focus()
	host._update_status()

func _ensure_overlay() -> void:
	if is_instance_valid(overlay): return
	overlay = Control.new()
	overlay.name = "ComputerCaseOverlay"
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	host.screen.add_child(overlay)
	var dim := ColorRect.new()
	dim.color = Color(0.08, 0.13, 0.10, 0.48)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	overlay.add_child(dim)
	popup = PanelContainer.new()
	popup.name = "ComputerCaseDialog"
	popup.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	popup.add_theme_stylebox_override("panel", UI.style(UI.CREAM, 22, 16, UI.LINE))
	overlay.add_child(popup)

func resize() -> void:
	if not is_instance_valid(popup): return
	var viewport := host.get_viewport()
	var stretch: Vector2 = viewport.get_final_transform().get_scale().abs()
	stretch.x = maxf(stretch.x, 0.001)
	stretch.y = maxf(stretch.y, 0.001)
	var physical: Vector2 = viewport.get_visible_rect().size * stretch
	var width := minf(900, physical.x - 64)
	var height := minf(435, physical.y - 64)
	popup.pivot_offset = Vector2(width, height) / 2.0
	popup.scale = Vector2.ONE / stretch
	popup.offset_left = -width / 2.0
	popup.offset_right = width / 2.0
	popup.offset_top = -height / 2.0
	popup.offset_bottom = height / 2.0

func _revealed(_card_result: Dictionary) -> void:
	phase.text = str(saved_drop.get("name", "饰品")) + " · " + host._rarity_label(str(saved_drop.get("rarity", "")))
	skip_button.hide()
	decisions.show()
	refresh_buttons()
	host.notice = "已开出 " + str(saved_drop.get("name", "饰品")) + "。"
	host._busy_changed(CareerBridge.busy)
	keep_button.grab_focus()
	if host.screen.visible and host.active_page == "market": host._rebuild()

func refresh_buttons() -> void:
	var disabled := decision_pending or is_running() or pending().is_empty() or not CareerBridge.connected or (CareerBridge.busy and CareerBridge.active_post)
	if is_instance_valid(keep_button): keep_button.disabled = disabled
	if is_instance_valid(cash_button):
		cash_button.disabled = disabled
		if not pending().is_empty(): cash_button.text = "立即出售 · %s" % preload("res://scripts/ui_format.gd").money(pending().get("sell", 0))

func _later() -> void:
	if is_instance_valid(overlay): overlay.hide()
	if host.screen.visible and host.active_page == "market": host._rebuild()

func reset() -> void:
	awaiting_case = false
	decision_pending = false
	requested_case.clear()
	saved_drop.clear()
	shown_key = ""
	if is_instance_valid(overlay): overlay.queue_free()
	overlay = null
	popup = null
	reel = null
