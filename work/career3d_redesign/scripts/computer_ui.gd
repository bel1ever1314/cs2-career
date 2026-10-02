extends RefCounted
## Computer-only chrome. Data and writes remain in CareerBridge.
const Base = preload("res://scripts/phone_ui.gd")
const Device = preload("res://scripts/career_ui.gd")
const INK := Color("293e35")
const MUTED := Color("667268")
const GREEN := Color("3d6a55")
const PAPER := Color("fffdf6")
const CREAM := Color("f8f4e9")
const MINT := Color("cee1d2")
const LINE := Color("dedfd3")

static func style(color: Color, padding: int = 12, radius: int = 12, border: Color = Color.TRANSPARENT) -> StyleBoxFlat:
	return Base.style(color, padding, radius, border)

static func label(parent: Node, value: String, size: int = 14, color: Color = INK) -> Label:
	return Base.label(parent, value, size, color)

static func button(parent: Node, value: String, callback: Callable, _dark: bool = false) -> Button:
	var node := Base.button(parent, value, callback)
	node.custom_minimum_size.y = 36
	node.add_theme_font_size_override("font_size", 14)
	# Both pointer and keyboard presses need a visible state before a request
	# starts. Disabled controls must also look different from ready controls.
	node.add_theme_stylebox_override("hover", style(Color("e5eddf"), 10, 10, Color("9eb19c")))
	node.add_theme_stylebox_override("pressed", style(Color("b6d4bb"), 10, 10, GREEN))
	node.add_theme_stylebox_override("hover_pressed", style(Color("b6d4bb"), 10, 10, GREEN))
	node.add_theme_stylebox_override("disabled", style(Color("edece4"), 10, 10, Color("deded3")))
	node.add_theme_color_override("font_disabled_color", Color("969a8f"))
	node.add_theme_stylebox_override("focus", style(Color.TRANSPARENT, 0, 10, GREEN))
	return node

static func compact(node: Button) -> Button:
	return Base.compact(node)

static func transparent(node: Button) -> void:
	Base.transparent(node)
	# Toolbar buttons still show that a pointer is over them or pressed.
	node.add_theme_stylebox_override("hover", style(Color("e5eddf"), 4, 8))
	node.add_theme_stylebox_override("pressed", style(MINT, 4, 8, Color("90ab95")))
	node.add_theme_stylebox_override("hover_pressed", style(MINT, 4, 8, Color("90ab95")))
	node.add_theme_color_override("font_disabled_color", Color("969a8f"))

static func primary(node: Button) -> void:
	node.add_theme_stylebox_override("normal", style(GREEN, 10, 10))
	node.add_theme_stylebox_override("hover", style(Color("496f57"), 10, 10))
	node.add_theme_stylebox_override("pressed", style(Color("2e5441"), 10, 10))
	node.add_theme_stylebox_override("hover_pressed", style(Color("2e5441"), 10, 10))
	node.add_theme_stylebox_override("disabled", style(Color("c7cfc2"), 10, 10))
	node.add_theme_color_override("font_disabled_color", Color("7d877a"))
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
		node.add_theme_color_override(state, PAPER)

static func card(parent: Node, _dark: bool = false) -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.add_theme_stylebox_override("panel", style(PAPER, 16, 12, LINE))
	parent.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 9)
	panel.add_child(column)
	return column

static func dark_options(node: OptionButton) -> void:
	Base.decorate_button(node)
	node.add_theme_font_override("font", Base.font())
	node.add_theme_font_size_override("font_size", 14)
	var popup := node.get_popup()
	popup.add_theme_stylebox_override("panel", style(PAPER, 8, 9, LINE))
	popup.add_theme_font_override("font", Base.font())
	popup.add_theme_font_size_override("font_size", 14)
	popup.add_theme_color_override("font_color", INK)
	popup.add_theme_color_override("font_hover_color", INK)
	popup.add_theme_stylebox_override("hover", style(MINT, 6, 5))

static func line_edit(node: LineEdit) -> void:
	node.add_theme_font_override("font", Base.font())
	node.add_theme_font_size_override("font_size", 14)
	node.add_theme_color_override("font_color", INK)
	node.add_theme_color_override("caret_color", GREEN)
	node.add_theme_stylebox_override("normal", style(PAPER, 9, 8, LINE))
	node.add_theme_stylebox_override("focus", style(PAPER, 9, 8, GREEN))
	node.add_theme_stylebox_override("read_only", style(Color("edece4"), 9, 8, LINE))
	node.add_theme_color_override("font_uneditable_color", Color("969a8f"))
	node.add_theme_color_override("selection_color", MINT)

static func clear(node: Node) -> void:
	Device.clear(node)

static func device_open(owner: Node, kind: String) -> void:
	Device.device_open(owner, kind)

static func device_closed(owner: Node) -> void:
	Device.device_closed(owner)

static func claim_key(owner: Node) -> void:
	Device.claim_key(owner)

static func key_claimed(owner: Node) -> bool:
	return Device.key_claimed(owner)
