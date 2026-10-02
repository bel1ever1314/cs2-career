extends CanvasLayer
## Door destinations. Selection is local; confirmation reuses Travel.go.
signal confirmed(destination: String)
signal cancelled
const UI = preload("res://scripts/phone_ui.gd")
const DESTINATIONS := ["bedroom", "club", "lan", "major", "awards"]
const NAMES := {"bedroom":"宿舍", "club":"俱乐部", "major":"Major 场馆", "lan":"线下赛场", "awards":"年度颁奖礼"}
const DETAILS := {"bedroom":"休息、查看电脑", "club":"训练、和队友碰面", "major":"进入场馆 · 比赛日和队友入场", "lan":"面对面 5v5 · 入座打开比赛电脑", "awards":"已结算年度前三 · 现场领奖"}
var screen: Control
var choices: VBoxContainer
var buttons: Array[Button] = []
var destinations: Array[String] = []
var selected := 0

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
	panel.add_theme_stylebox_override("panel", UI.style(UI.CREAM, 16, 16, UI.LINE))
	screen.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	panel.add_child(column)
	UI.label(column, "选择下一站", 20)
	choices = VBoxContainer.new()
	choices.add_theme_constant_override("separation", 8)
	column.add_child(choices)
	UI.label(column, "滚轮选择 · E / Enter 出发", 13, UI.MUTED)
	UI.label(column, "可直接走开 · Esc 隐藏", 12, UI.MUTED)
	screen.visible = false

func present(current_destination: String) -> void:
	UI.clear(choices)
	buttons.clear()
	destinations.clear()
	for destination in DESTINATIONS:
		if destination == current_destination: continue
		destinations.append(destination)
		var index := destinations.size() - 1
		var button := UI.button(choices, "", func(): select_index(index); confirm())
		button.focus_mode = Control.FOCUS_NONE
		button.custom_minimum_size = Vector2(310, 56)
		# A stationary pointer must not change a wheel selection when this
		# automatic prompt appears beneath it. Clicking still picks this row.
		buttons.append(button)
	selected = 0
	_refresh()
	screen.visible = true

func dismiss() -> void:
	screen.visible = false

func select_index(index: int) -> void:
	if destinations.is_empty(): return
	selected = wrapi(index, 0, destinations.size())
	_refresh()

func _refresh() -> void:
	for index in range(buttons.size()):
		var destination := destinations[index]
		var button := buttons[index]
		button.text = ("›  " if index == selected else "    ") + NAMES[destination] + "\n" + DETAILS[destination]
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.add_theme_stylebox_override("normal", UI.style(UI.MINT if index == selected else UI.PAPER, 10, 12, UI.GREEN if index == selected else UI.LINE))

func confirm() -> void:
	if screen.visible and not destinations.is_empty():
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
