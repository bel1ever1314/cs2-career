extends CanvasLayer
## Door destinations. Selection is local; confirmation reuses Travel.go.
signal confirmed(destination: String)
signal cancelled
signal resolve_requested(events: bool)
const UI = preload("res://scripts/phone_ui.gd")
const DESTINATIONS := ["bedroom", "club", "lan", "major", "awards"]
const NAMES := {"bedroom":"宿舍", "club":"俱乐部", "major":"Major 场馆", "lan":"线下赛场", "awards":"年度颁奖礼"}
const DETAILS := {"bedroom":"休息、查看电脑", "club":"训练、和队友碰面", "major":"进入场馆 · 比赛日和队友入场", "lan":"面对面 5v5 · 入座打开比赛电脑", "awards":"已结算年度前三 · 现场领奖"}
var attendance: Dictionary = {}
var screen: Control
var choices: VBoxContainer
var buttons: Array[Button] = []
var destinations: Array[String] = []
var selected := 0
var request_pending := false
var notice_events := false
var status: Label
var resolve_button: Button

func _ready() -> void:
	layer = 25
	process_mode = Node.PROCESS_MODE_ALWAYS
	screen = Control.new()
	screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	screen.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(screen)
	var panel := PanelContainer.new()
	panel.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	panel.offset_left = 24; panel.offset_right = 374
	panel.offset_top = -445; panel.offset_bottom = -24
	panel.grow_vertical = Control.GROW_DIRECTION_BEGIN
	panel.add_theme_stylebox_override("panel", UI.style(UI.CREAM, 16, 16, UI.LINE))
	screen.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	panel.add_child(column)
	UI.label(column, "选择下一站", 20)
	choices = VBoxContainer.new()
	choices.add_theme_constant_override("separation", 8)
	column.add_child(choices)
	status = UI.label(column, "", 14, UI.GREEN)
	status.name = "DoorTravelStatus"
	status.visible = false
	resolve_button = UI.button(column, "", func(): resolve_requested.emit(notice_events))
	resolve_button.name = "DoorTravelResolve"
	resolve_button.focus_mode = Control.FOCUS_NONE
	resolve_button.visible = false
	UI.label(column, "滚轮选择 · E / Enter 出发", 13, UI.MUTED)
	UI.label(column, "可直接走开 · Esc 隐藏", 12, UI.MUTED)
	screen.visible = false

func present(current_destination: String) -> void:
	attendance = Travel.match_guidance()
	var options: Array[String] = []
	var match_destination := str(attendance.get("destination", ""))
	var highlight_match := bool(attendance.get("planned", false)) or (bool(attendance.get("is_today", false)) and bool(attendance.get("due", false)))
	var can_arrive := bool(attendance.get("can_travel", false)) or bool(attendance.get("can_return", false))
	var preparing_here := can_arrive and match_destination in ["major", "lan"] and not Travel.match_visit_current(match_destination)
	if highlight_match and match_destination in DESTINATIONS and (match_destination != current_destination or preparing_here): options.append(match_destination)
	for destination in DESTINATIONS:
		if destination == current_destination or destination in options: continue
		options.append(destination)
	# Keep the same controls across unrelated career updates, including a
	# mouse press that has not yet been released.
	if options != destinations:
		UI.clear(choices)
		buttons.clear()
		destinations = options
		for index in range(destinations.size()):
			var button := UI.button(choices, "", func(): select_index(index); confirm())
			button.focus_mode = Control.FOCUS_NONE
			button.custom_minimum_size = Vector2(310, 56)
			buttons.append(button)
		selected = 0
	if notice_events and not request_pending and CareerBridge.context.get("stories", []).is_empty():
		set_notice("")
	_refresh()
	screen.visible = true

func set_notice(text: String, pending: bool = false, events: bool = false) -> void:
	request_pending = pending
	notice_events = events
	status.text = text
	status.visible = not text.is_empty()
	resolve_button.text = "查看待处理事项" if events else "查看比赛准备"
	resolve_button.visible = not pending and not text.is_empty()
	_refresh()

func dismiss() -> void:
	screen.visible = false

func select_index(index: int) -> void:
	if request_pending or destinations.is_empty(): return
	selected = wrapi(index, 0, destinations.size())
	_refresh()

func _refresh() -> void:
	for index in range(buttons.size()):
		var destination := destinations[index]
		var button := buttons[index]
		if button.disabled != request_pending: button.disabled = request_pending
		button.custom_minimum_size.y = 56
		var title := str(NAMES[destination])
		var details := str(DETAILS[destination])
		if destination == str(attendance.get("destination", "")):
			title = str(attendance.get("display_name", attendance.get("venue_name", title)))
			var event_name := str(attendance.get("event_name", attendance.get("event", "")))
			var date_label := "今日比赛" if bool(attendance.get("is_today", false)) else str(attendance.get("date", "")) + " 比赛"
			details = "%s · %s\n对阵 %s" % [date_label, event_name, attendance.get("opponent", "")]
			if bool(attendance.get("is_today", false)):
				if bool(attendance.get("can_return", false)): details += " · 返回本场席位"
				else: details += " · 到场准备" if bool(attendance.get("can_travel", false)) else " · 先处理手机中的待办"
			else:
				details += " · 比赛日再来"
			button.custom_minimum_size.y = 78
		button.text = ("›  " if index == selected else "    ") + title + "\n" + details
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.add_theme_stylebox_override("normal", UI.style(UI.MINT if index == selected else UI.PAPER, 10, 12, UI.GREEN if index == selected else UI.LINE))

func confirm() -> void:
	if not request_pending and screen.visible and not destinations.is_empty():
		confirmed.emit(destinations[selected])

func _input(event: InputEvent) -> void:
	if not screen.visible: return
	# Devices own their own controls; a device opened from another entry closes
	# this menu through the scene's before_phone / before_computer hook.
	if CareerBridge.phone_open:
		cancelled.emit()
		return
	if event is InputEventMouseButton and event.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
		if event.pressed: select_index(selected + (-1 if event.button_index == MOUSE_BUTTON_WHEEL_UP else 1))
		get_viewport().set_input_as_handled()
	elif event is InputEventKey:
		var claimed: bool = event.physical_keycode in [KEY_E, KEY_ENTER, KEY_KP_ENTER, KEY_ESCAPE]
		if not claimed: return
		if event.pressed and not event.echo:
			match event.physical_keycode:
				KEY_E, KEY_ENTER, KEY_KP_ENTER: confirm()
				KEY_ESCAPE: cancelled.emit()
		get_viewport().set_input_as_handled()
