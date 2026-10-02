extends RefCounted
## Only presentation. The simulator never imports this module.
const BG := Color("10161b")
const PANEL := Color("192229")
const SURFACE := Color("222e36")
const BORDER := Color("35434c")
const TEXT := Color("ebede8")
const MUTED := Color("96a5ac")
const GOLD := Color("e1b775")
const BLUE := Color("80b9d3")
const GREEN := Color("90c9b0")
const RED := Color("e59085")

static func box(color: Color = PANEL, radius: int = 10, pad: int = 12, border: Color = Color.TRANSPARENT) -> StyleBoxFlat:
	var result := StyleBoxFlat.new()
	result.bg_color = color
	result.set_corner_radius_all(radius)
	result.content_margin_left = pad
	result.content_margin_right = pad
	result.content_margin_top = pad
	result.content_margin_bottom = pad
	if border.a > 0:
		result.border_color = border
		result.set_border_width_all(1)
	return result

static func theme() -> Theme:
	var result := Theme.new()
	var font := SystemFont.new()
	font.font_names = PackedStringArray(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "sans-serif"])
	result.default_font = font
	result.default_font_size = 14
	for kind in ["Label", "Button", "OptionButton", "CheckButton", "LineEdit", "PopupMenu"]:
		result.set_color("font_color", kind, TEXT)
	result.set_stylebox("normal", "Button", box(SURFACE, 7, 10))
	result.set_stylebox("hover", "Button", box(Color("31424c"), 7, 10))
	result.set_stylebox("pressed", "Button", box(Color("3c534f"), 7, 10))
	result.set_stylebox("disabled", "Button", box(Color("192229"), 7, 10))
	result.set_color("font_disabled_color", "Button", Color("697980"))
	result.set_stylebox("focus", "Button", box(Color.TRANSPARENT, 7, 10, GOLD))
	result.set_stylebox("normal", "OptionButton", box(SURFACE, 7, 10))
	result.set_stylebox("hover", "OptionButton", box(Color("31424c"), 7, 10))
	result.set_stylebox("pressed", "OptionButton", box(Color("31424c"), 7, 10))
	result.set_stylebox("panel", "PopupMenu", box(PANEL, 8, 10, BORDER))
	result.set_stylebox("hover", "PopupMenu", box(SURFACE, 5, 6))
	result.set_stylebox("background", "ProgressBar", box(Color("0f171c"), 3, 0))
	result.set_stylebox("fill", "ProgressBar", box(GREEN, 3, 0))
	result.set_constant("separation", "VBoxContainer", 8)
	result.set_constant("separation", "HBoxContainer", 8)
	return result

static func label(text: String, font_size: int = 14, color: Color = TEXT) -> Label:
	var result := Label.new()
	result.text = text
	result.add_theme_font_size_override("font_size", font_size)
	result.add_theme_color_override("font_color", color)
	result.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return result

static func button(text: String, action: Callable, min_size: Vector2 = Vector2(0, 38)) -> Button:
	var result := Button.new()
	result.text = text
	result.custom_minimum_size = min_size
	result.pressed.connect(action)
	return result

static func panel(color: Color = PANEL, pad: int = 12) -> PanelContainer:
	var result := PanelContainer.new()
	result.add_theme_stylebox_override("panel", box(color, 10, pad))
	return result

static func accent_button(button: Button) -> void:
	button.add_theme_stylebox_override("normal", box(GOLD, 7, 12))
	button.add_theme_stylebox_override("hover", box(Color("edcb94"), 7, 12))
	button.add_theme_stylebox_override("pressed", box(Color("c2a16c"), 7, 12))
	button.add_theme_color_override("font_color", BG)
	button.add_theme_font_size_override("font_size", 17)
