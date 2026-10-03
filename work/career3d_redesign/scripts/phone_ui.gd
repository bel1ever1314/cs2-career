extends RefCounted
## Phone-only rendering. Desktop and device business stay in their existing owners.
const Device = preload("res://scripts/career_ui.gd")
const INK := Color("293e35")
const MUTED := Color("667268")
const GREEN := Color("3d6a55")
const PAPER := Color("fffdf6")
const CREAM := Color("f8f4e9")
const MINT := Color("cee1d2")
const LINE := Color("dedfd3")
const BADGE := Color("a04e38")
static var body_font: Font
static var font_style := "rounded"
static var font_loaded := false
static var control_icons: Dictionary = {}

static func font() -> Font:
	if body_font == null:
		if not font_loaded:
			font_loaded = true
			font_style = str(Locale.preference("font", "rounded"))
		var fallback := SystemFont.new()
		fallback.font_names = PackedStringArray(["Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC"])
		fallback.font_weight = 400
		fallback.oversampling = 2.0
		body_font = fallback
		if font_style == "rounded":
			var config = JSON.parse_string(FileAccess.get_file_as_string("res://data/ui_style.json"))
			if config is Dictionary:
				for path in [str(config.get("font_file", "")), str(config.get("development_cache", ""))]:
					if FileAccess.file_exists(path):
						var rounded := FontFile.new()
						if rounded.load_dynamic_font(path) == OK:
							rounded.fallbacks = [fallback]
							body_font = rounded
							break
	return body_font

static func choose_font(value: String, tree: SceneTree) -> void:
	if value not in ["rounded", "system"]: return
	font_style = value
	body_font = null
	font_loaded = true
	var replacement := font()
	ThemeDB.fallback_font = replacement
	_replace_font(tree.root, replacement)
	Locale.set_preference("font", value)

static func _replace_font(node: Node, replacement: Font) -> void:
	if node is Control:
		node.add_theme_font_override("font", replacement)
		if node.theme: node.theme.default_font = replacement
	if node is Label3D: node.font = replacement
	for child in node.get_children(): _replace_font(child, replacement)

static func style(color: Color, padding: int = 12, radius: int = 12, border: Color = Color.TRANSPARENT) -> StyleBoxFlat:
	return Device.style(color, padding, radius, border)

static func control_icon(kind: String) -> Texture2D:
	if control_icons.has(kind):
		return control_icons[kind]
	var drawing := ""
	if kind == "slider":
		drawing = '<circle cx="9" cy="9" r="7" fill="#3d6a55"/>'
	else:
		drawing = '<rect x="2" y="2" width="14" height="14" rx="4" fill="#fffdf6" stroke="#78907f" stroke-width="1.3"/>'
		if kind == "checked":
			drawing += '<path d="M5.5 9L8 11.5L12.5 6.5" fill="none" stroke="#3d6a55" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
	var image := Image.new()
	image.load_svg_from_string('<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18">' + drawing + '</svg>')
	var texture := ImageTexture.create_from_image(image)
	control_icons[kind] = texture
	return texture

static func inset(parent: Node, child: Control) -> void:
	if parent.get_meta("phone_edge", false):
		var margins := MarginContainer.new()
		margins.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		margins.add_theme_constant_override("margin_left", 19)
		margins.add_theme_constant_override("margin_right", 19)
		parent.add_child(margins)
		margins.add_child(child)
	else:
		parent.add_child(child)

static func label(parent: Node, value: String, size: int = 14, color: Color = INK) -> Label:
	var node := Label.new()
	node.text = value
	node.add_theme_font_override("font", font())
	node.add_theme_font_size_override("font_size", size)
	node.add_theme_color_override("font_color", color)
	node.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	node.custom_minimum_size.y = ceilf(size * 1.4)
	node.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	inset(parent, node)
	return node

static func decorate_button(node: Button, color: Color = PAPER, border: Color = LINE) -> void:
	node.focus_mode = Control.FOCUS_ALL
	node.add_theme_font_override("font", font())
	node.add_theme_font_size_override("font_size", 14)
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
		node.add_theme_color_override(state, INK)
	node.add_theme_color_override("font_disabled_color", MUTED)
	node.add_theme_stylebox_override("normal", style(color, 10, 12, border))
	node.add_theme_stylebox_override("hover", style(Color("edf0e5"), 10, 12, border))
	node.add_theme_stylebox_override("pressed", style(MINT, 10, 12, border))
	node.add_theme_stylebox_override("disabled", style(Color("e8e8df"), 10, 12, border))
	node.add_theme_stylebox_override("focus", style(Color.TRANSPARENT, 0, 12, Color("90ab95")))

static func button(parent: Node, value: String, callback: Callable, _dark: bool = false) -> Button:
	var node := Button.new()
	node.text = value
	node.custom_minimum_size = Vector2(60, 41)
	node.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	node.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	decorate_button(node)
	node.pressed.connect(callback)
	inset(parent, node)
	return node

static func compact(node: Button) -> Button:
	node.autowrap_mode = TextServer.AUTOWRAP_OFF
	node.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	return node

static func transparent(node: Button) -> void:
	node.add_theme_stylebox_override("normal", style(Color.TRANSPARENT, 4, 8))
	node.add_theme_stylebox_override("hover", style(Color("e9efdf"), 4, 8))
	node.add_theme_stylebox_override("pressed", style(MINT, 4, 8))
	node.add_theme_stylebox_override("disabled", style(Color.TRANSPARENT, 4, 8))
	node.add_theme_font_size_override("font_size", 12)
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color"]:
		node.add_theme_color_override(state, MUTED)
	node.add_theme_stylebox_override("focus", style(Color.TRANSPARENT, 0, 8, Color("90ab95")))

static func card(parent: Node, _dark: bool = false) -> VBoxContainer:
	var box := PanelContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_theme_stylebox_override("panel", style(PAPER, 16, 18))
	inset(parent, box)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 8)
	box.add_child(column)
	return column

static func divider(parent: Node) -> void:
	var line := ColorRect.new()
	line.color = LINE
	line.custom_minimum_size.y = 1
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	inset(parent, line)

static func space(parent: Node, height: int) -> void:
	var gap := Control.new()
	gap.custom_minimum_size.y = height
	parent.add_child(gap)

static func clear(parent: Node) -> void:
	Device.clear(parent)

static func device_open(owner: Node, kind: String) -> void:
	Device.device_open(owner, kind)

static func device_closed(owner: Node) -> void:
	Device.device_closed(owner)

static func claim_key(owner: Node) -> void:
	Device.claim_key(owner)

static func key_claimed(owner: Node) -> bool:
	return Device.key_claimed(owner)
