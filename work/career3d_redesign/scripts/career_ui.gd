extends RefCounted
## Shared native widgets. Only CareerBridge writes career state.
const INK := Color("243044")
const MUTED := Color("6a768b")
const ACCENT := Color("3d6bd9")
const PAPER := Color("f5f7fb")

static func style(color: Color, padding: int = 12, radius: int = 12, border: Color = Color.TRANSPARENT) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = color
	box.set_corner_radius_all(radius)
	box.content_margin_left = padding
	box.content_margin_right = padding
	box.content_margin_top = padding
	box.content_margin_bottom = padding
	if border.a > 0:
		box.set_border_width_all(1)
		box.border_color = border
	return box

static func label(parent: Node, value: String, size: int = 17, color: Color = INK) -> Label:
	var node := Label.new()
	node.text = value
	node.add_theme_font_size_override("font_size", size)
	node.add_theme_color_override("font_color", color)
	node.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	node.custom_minimum_size.y = ceilf(size * 1.35)
	node.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(node)
	return node

static func button(parent: Node, value: String, callback: Callable, dark: bool = false) -> Button:
	var node := Button.new()
	node.text = value
	node.focus_mode = Control.FOCUS_ALL
	node.custom_minimum_size = Vector2(80, 40)
	node.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	node.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	node.add_theme_font_size_override("font_size", 16)
	var foreground := Color("edf3ff") if dark else INK
	node.add_theme_color_override("font_color", foreground)
	node.add_theme_color_override("font_hover_color", foreground)
	node.add_theme_color_override("font_pressed_color", foreground)
	node.add_theme_color_override("font_focus_color", foreground)
	node.add_theme_color_override("font_hover_pressed_color", foreground)
	node.add_theme_color_override("font_disabled_color", Color("8793a6"))
	node.add_theme_stylebox_override("normal", style(Color("28354b") if dark else Color("e7edf8"), 9, 9))
	node.add_theme_stylebox_override("hover", style(Color("374a68") if dark else Color("d9e5fa"), 9, 9))
	node.add_theme_stylebox_override("pressed", style(Color("3e64a1") if dark else Color("bacef4"), 9, 9))
	node.add_theme_stylebox_override("disabled", style(Color("202936") if dark else Color("eef0f4"), 9, 9))
	node.add_theme_stylebox_override("focus", style(Color.TRANSPARENT, 0, 9, Color("699afa")))
	node.pressed.connect(callback)
	parent.add_child(node)
	return node

static func compact(button: Button) -> Button:
	# A single-line toolbar control must reserve its measured text width.
	button.autowrap_mode = TextServer.AUTOWRAP_OFF
	button.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	return button

static func dark_options(button: OptionButton) -> void:
	var foreground := Color("edf3ff")
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
		button.add_theme_color_override(state, foreground)
	button.add_theme_font_size_override("font_size", 16)
	button.add_theme_stylebox_override("normal", style(Color("28354b"), 9, 9))
	button.add_theme_stylebox_override("hover", style(Color("374a68"), 9, 9))
	button.add_theme_stylebox_override("pressed", style(Color("3e64a1"), 9, 9))
	button.add_theme_stylebox_override("focus", style(Color.TRANSPARENT, 0, 9, Color("699afa")))
	var popup := button.get_popup()
	popup.add_theme_stylebox_override("panel", style(Color("1c293d"), 9, 9))
	popup.add_theme_color_override("font_color", foreground)
	popup.add_theme_color_override("font_hover_color", foreground)
	popup.add_theme_font_size_override("font_size", 16)

static func card(parent: Node, dark: bool = false) -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.add_theme_stylebox_override("panel", style(Color("1c293d") if dark else Color.WHITE, 12, 12))
	parent.add_child(panel)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 8)
	panel.add_child(column)
	return column

static func clear(parent: Node) -> void:
	for child in parent.get_children():
		parent.remove_child(child)
		child.queue_free()

static func device_open(owner: Node, kind: String) -> void:
	CareerBridge.phone_open = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	var scene := owner.get_tree().current_scene
	if scene and kind == "computer" and scene.has_method("before_computer"):
		scene.before_computer()
	elif scene and scene.has_method("before_phone"):
		scene.before_phone()
	if scene and scene.has_method("set_device_open"):
		scene.set_device_open(true, kind)
	elif scene and scene.has_method("set_phone_open"):
		scene.set_phone_open(true)

static func device_closed(owner: Node) -> void:
	var phone := owner.get_node_or_null("/root/Phone")
	var computer := owner.get_node_or_null("/root/Computer")
	var opened: bool = CareerBridge.sleeping or CareerBridge.feedback_active or (phone != null and phone.screen.visible) or (computer != null and computer.screen.visible)
	CareerBridge.phone_open = opened
	var scene := owner.get_tree().current_scene
	if scene and scene.has_method("set_device_open"):
		scene.set_device_open(opened, "sleep" if CareerBridge.sleeping else "phone" if phone != null and phone.screen.visible else ("phone" if owner.name == "Phone" else "computer"))
	elif scene and scene.has_method("set_phone_open"):
		scene.set_phone_open(opened)

static func claim_key(owner: Node) -> void:
	owner.get_tree().set_meta("career_device_input_frame", Engine.get_process_frames())
	owner.get_viewport().set_input_as_handled()

static func key_claimed(owner: Node) -> bool:
	return int(owner.get_tree().get_meta("career_device_input_frame", -1)) == Engine.get_process_frames()
