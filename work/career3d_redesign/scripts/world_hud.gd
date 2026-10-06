extends RefCounted
## Shared in-world HUD look: dark glass panels, keycap hints and light toasts.
## Used by bedroom, club and venues so every scene reads as the same game.
const Base = preload("res://scripts/phone_ui.gd")
const GLASS := Color(0.075, 0.15, 0.125, 0.86)
const GLASS_EDGE := Color(1, 1, 1, 0.10)
const KEYCAP := Color(1, 0.99, 0.96, 0.95)
const KEY_INK := Color("22342b")
const TEXT := Color("f4f1e6")
const SOFT := Color("e7d39c")

static func glass(padding_x: int = 16, padding_y: int = 10, radius: int = 14) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = GLASS
	box.set_corner_radius_all(radius)
	box.set_border_width_all(1)
	box.border_color = GLASS_EDGE
	box.content_margin_left = padding_x; box.content_margin_right = padding_x
	box.content_margin_top = padding_y; box.content_margin_bottom = padding_y
	box.shadow_color = Color(0, 0, 0, 0.18)
	box.shadow_size = 10
	box.shadow_offset = Vector2(0, 3)
	return box

static func paper(padding_x: int = 16, padding_y: int = 10) -> StyleBoxFlat:
	var box := Base.raised(Color(1, 0.992, 0.965, 0.97), padding_x, 14, Color(0, 0, 0, 0))
	box.content_margin_top = padding_y; box.content_margin_bottom = padding_y
	return box

static func text(parent: Node, value: String, size: int = 16, colour: Color = TEXT) -> Label:
	var label := Label.new()
	label.text = value
	label.add_theme_font_override("font", Base.font())
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", colour)
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(label)
	return label

static func keycap(parent: Node, key: String, size: int = 13) -> PanelContainer:
	var cap := PanelContainer.new()
	cap.name = "Keycap"
	cap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	cap.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var box := StyleBoxFlat.new()
	box.bg_color = KEYCAP
	box.set_corner_radius_all(6)
	box.border_width_bottom = 2
	box.border_color = Color(0.55, 0.6, 0.55, 0.9)
	box.content_margin_left = 7; box.content_margin_right = 7
	box.content_margin_top = 1; box.content_margin_bottom = 1
	cap.add_theme_stylebox_override("panel", box)
	parent.add_child(cap)
	text(cap, key, size, KEY_INK).horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	return cap

## A clickable hint such as [P] 手机. The Button keeps "P 手机" as its text for
## focus/tests, drawn transparent; the visible keycap row is an overlay.
static func key_button(parent: Node, key: String, caption: String, callback: Callable) -> Button:
	var button := Button.new()
	button.text = key + " " + caption
	button.focus_mode = Control.FOCUS_NONE
	button.pressed.connect(callback)
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
		button.add_theme_color_override(state, Color(0, 0, 0, 0))
	var empty := StyleBoxFlat.new()
	empty.bg_color = Color(0, 0, 0, 0)
	empty.set_corner_radius_all(8)
	var hover := empty.duplicate()
	hover.bg_color = Color(1, 1, 1, 0.08)
	button.add_theme_stylebox_override("normal", empty)
	button.add_theme_stylebox_override("hover", hover)
	button.add_theme_stylebox_override("pressed", hover)
	button.add_theme_stylebox_override("focus", empty)
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_theme_constant_override("separation", 6)
	button.add_child(row)
	keycap(row, key)
	text(row, caption, 15)
	parent.add_child(button)
	# Size the hit area to the keycap row.
	row.resized.connect(func(): button.custom_minimum_size = row.get_combined_minimum_size() + Vector2(8, 6); row.position = Vector2(4, 3))
	button.custom_minimum_size = row.get_combined_minimum_size() + Vector2(8, 6)
	row.position = Vector2(4, 3)
	return button

## A non-clickable [key] caption pair for movement hints such as WASD.
static func key_hint(parent: Node, key: String, caption: String) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_theme_constant_override("separation", 6)
	parent.add_child(row)
	keycap(row, key)
	text(row, caption, 15)
	return row

## Small glass card in the top-left corner: venue title plus a status line.
## Returns {"panel", "title", "status", "objective"} so scenes keep their labels.
static func title_card(root: Control, title_text: String, status_text: String = "") -> Dictionary:
	var card := PanelContainer.new()
	card.name = "WorldTitleCard"
	card.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_theme_stylebox_override("panel", glass(18, 12))
	card.position = Vector2(24, 22)
	root.add_child(card)
	var stack := VBoxContainer.new()
	stack.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stack.add_theme_constant_override("separation", 2)
	card.add_child(stack)
	var title := text(stack, title_text, 20)
	var status := text(stack, status_text, 14, Color(0.86, 0.9, 0.87, 0.82))
	var objective := text(stack, "", 14, SOFT)
	objective.visible = false
	objective.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	objective.custom_minimum_size = Vector2(300, 0)
	return {"panel": card, "title": title, "status": status, "objective": objective}

## Centred host-caption / notice pill near the top of the screen.
## Bottom placement reads like subtitles and stays clear of the title card.
static func caption_pill(root: Control, bottom: bool = true) -> Dictionary:
	var pill := PanelContainer.new()
	pill.name = "WorldCaption"
	pill.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pill.add_theme_stylebox_override("panel", glass(22, 12, 16))
	root.add_child(pill)
	pill.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM if bottom else Control.PRESET_CENTER_TOP)
	pill.grow_horizontal = Control.GROW_DIRECTION_BOTH
	pill.offset_left = 0; pill.offset_right = 0
	if bottom:
		pill.grow_vertical = Control.GROW_DIRECTION_BEGIN
		pill.offset_bottom = -96; pill.offset_top = -96
	else:
		pill.offset_top = 24
	var label := text(pill, "", 18)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	pill.visible = false
	return {"panel": pill, "label": label}

## Sizes a caption pill to its text (max 760 px) and hides it when empty.
static func fit_caption(pill: Dictionary, max_width: float = 640.0) -> void:
	var panel: PanelContainer = pill["panel"]
	var label: Label = pill["label"]
	panel.visible = not label.text.strip_edges().is_empty()
	if not panel.visible: return
	var font: Font = label.get_theme_font("font")
	var size: int = label.get_theme_font_size("font_size")
	var widest := 0.0
	for line in label.text.split("\n"):
		widest = maxf(widest, font.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x)
	var width := clampf(widest + 6.0, 160.0, max_width)
	# Offsets stay zero-width: the pill grows evenly around the centre anchor.
	label.custom_minimum_size = Vector2(width, 0)

## Interaction prompt under the crosshair: [E] 坐下. Hidden for passive hints.
static func prompt(root: Control) -> Dictionary:
	var pill := PanelContainer.new()
	pill.name = "WorldPrompt"
	pill.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pill.add_theme_stylebox_override("panel", glass(12, 7, 12))
	root.add_child(pill)
	pill.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	pill.grow_horizontal = Control.GROW_DIRECTION_BOTH
	pill.grow_vertical = Control.GROW_DIRECTION_END
	pill.offset_top = 64; pill.offset_bottom = 64; pill.offset_left = 0; pill.offset_right = 0
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_theme_constant_override("separation", 8)
	pill.add_child(row)
	var cap := keycap(row, "E", 14)
	var label := text(row, "", 17)
	pill.visible = false
	return {"panel": pill, "key": cap, "label": label}

## Shows "E xxx" hints as a keycap prompt; returns false for passive guidance.
static func set_prompt(prompt_parts: Dictionary, value: String) -> bool:
	var panel: PanelContainer = prompt_parts["panel"]
	var active := value.begins_with("E ") and value.length() > 2
	panel.visible = active
	if active:
		(prompt_parts["label"] as Label).text = value.substr(2)
	return active

## Bottom-right bar that sizes itself to its hints instead of a fixed width.
static func hint_bar(root: Control) -> HBoxContainer:
	var bar := PanelContainer.new()
	bar.name = "WorldHintBar"
	bar.add_theme_stylebox_override("panel", glass(10, 6))
	root.add_child(bar)
	bar.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	bar.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	bar.grow_vertical = Control.GROW_DIRECTION_BEGIN
	bar.offset_right = -24; bar.offset_bottom = -24
	bar.offset_left = -24; bar.offset_top = -24
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	bar.add_child(row)
	return row

## Glass pause menu used by every walkable scene. Returns {"panel", "menu"}.
static func pause_menu(root: Control, title_text: String, body_text: String) -> Dictionary:
	var dim := ColorRect.new()
	dim.name = "PauseDim"
	dim.color = Color(0.02, 0.04, 0.035, 0.42)
	dim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(dim)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var panel := PanelContainer.new()
	panel.name = "PauseMenu"
	panel.add_theme_stylebox_override("panel", Base.raised(Color(1, 0.992, 0.965, 0.98), 26, 18, Color(0, 0, 0, 0)))
	root.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	panel.grow_horizontal = Control.GROW_DIRECTION_BOTH
	panel.grow_vertical = Control.GROW_DIRECTION_BOTH
	panel.custom_minimum_size = Vector2(440, 0)
	var menu := VBoxContainer.new()
	menu.add_theme_constant_override("separation", 12)
	panel.add_child(menu)
	text(menu, title_text, 24, Base.INK)
	var body := text(menu, body_text, 16, Base.MUTED)
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.visibility_changed.connect(func(): dim.visible = panel.visible)
	return {"panel": panel, "menu": menu, "dim": dim}

## Paper-style menu button matching the phone/computer controls.
static func menu_button(menu: Node, caption: String, callback: Callable, primary: bool = false) -> Button:
	var button := Base.button(menu, caption, callback)
	button.custom_minimum_size = Vector2(0, 44)
	if primary:
		Base.decorate_button(button, Base.GREEN, Base.GREEN)
		button.add_theme_stylebox_override("hover", Base.style(Base.GREEN.lightened(0.1), 10, 12, Base.GREEN))
		button.add_theme_stylebox_override("pressed", Base.style(Base.GREEN.darkened(0.12), 10, 12, Base.GREEN))
		for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
			button.add_theme_color_override(state, Color.WHITE)
	return button
