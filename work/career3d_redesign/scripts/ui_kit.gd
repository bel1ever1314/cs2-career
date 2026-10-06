extends RefCounted
## Shared device components: status chips, section headings, stat tiles, empty
## states and information-dense list rows. Pure presentation; callers keep data
## and commands. `ui` is phone_ui.gd or computer_ui.gd so sizes follow the device.
const Base = preload("res://scripts/phone_ui.gd")
const Glyphs = preload("res://scripts/phone_visuals.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")

const TONES := {
	"green": [Color("dcebdf"), Color("2f6b52")],
	"amber": [Color("f6ead2"), Color("9a6716")],
	"red": [Color("f5ded7"), Color("a3472f")],
	"blue": [Color("dde7f3"), Color("335a8a")],
	"gray": [Color("ecebe3"), Color("5f6a62")],
	"ink": [Color("22342b"), Color("fffdf8")],
}

## Event tiers as the career service reports them.
const EVENT_TIERS := {"major":["Major", "red"], "t1":["S 级", "amber"], "t2":["A 级", "blue"], "cct":["CCT", "gray"]}

static func tone(name: String) -> Array:
	return TONES.get(name, TONES.gray)

static func chip(parent: Node, text: String, tone_name: String = "gray", size: int = 12) -> PanelContainer:
	var colors := tone(tone_name)
	var box := PanelContainer.new()
	box.name = "Chip"
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	box.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	box.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var style := Base.style(colors[0], 0, 9)
	style.content_margin_left = 8; style.content_margin_right = 8
	style.content_margin_top = 2; style.content_margin_bottom = 2
	box.add_theme_stylebox_override("panel", style)
	parent.add_child(box)
	var text_label := Label.new()
	text_label.text = text
	text_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text_label.add_theme_font_override("font", Base.font())
	text_label.add_theme_font_size_override("font_size", size)
	text_label.add_theme_color_override("font_color", colors[1])
	text_label.autowrap_mode = TextServer.AUTOWRAP_OFF
	box.add_child(text_label)
	return box

static func section(parent: Node, ui, title: String, caption: String = "", size: int = 18) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.name = "Section"
	row.add_theme_constant_override("separation", 10)
	if parent.get_meta("phone_edge", false): Base.inset(parent, row)
	else: parent.add_child(row)
	var heading: Label = ui.label(row, title, size)
	heading.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	heading.autowrap_mode = TextServer.AUTOWRAP_OFF
	heading.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	if not caption.is_empty():
		var note: Label = ui.label(row, caption, 12, ui.MUTED)
		note.size_flags_horizontal = Control.SIZE_SHRINK_END
		note.autowrap_mode = TextServer.AUTOWRAP_OFF
		note.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	return row

static func stat_tile(parent: Node, ui, caption: String, value: String, note: String = "", note_tone: String = "") -> PanelContainer:
	var box := PanelContainer.new()
	box.name = "StatTile"
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_theme_stylebox_override("panel", Base.raised(Base.PAPER, 14, 14))
	parent.add_child(box)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 2)
	box.add_child(column)
	var top: Label = ui.label(column, caption, 12, ui.MUTED)
	top.autowrap_mode = TextServer.AUTOWRAP_OFF
	var big: Label = ui.label(column, value, 24)
	big.autowrap_mode = TextServer.AUTOWRAP_OFF
	big.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	if not note.is_empty():
		var colour: Color = tone(note_tone)[1] if not note_tone.is_empty() else ui.MUTED
		var foot: Label = ui.label(column, note, 12, colour)
		foot.autowrap_mode = TextServer.AUTOWRAP_OFF
		foot.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	return box

static func empty_state(parent: Node, ui, icon_kind: String, title: String, body: String = "") -> VBoxContainer:
	var holder := PanelContainer.new()
	holder.name = "EmptyState"
	holder.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var style := Base.style(Color(1, 1, 1, 0), 22, 16, Base.LINE)
	style.set_border_width_all(1)
	style.border_color = Base.LINE
	holder.add_theme_stylebox_override("panel", style)
	if parent.get_meta("phone_edge", false): Base.inset(parent, holder)
	else: parent.add_child(holder)
	var column := VBoxContainer.new()
	column.alignment = BoxContainer.ALIGNMENT_CENTER
	column.add_theme_constant_override("separation", 6)
	holder.add_child(column)
	var circle := PanelContainer.new()
	circle.custom_minimum_size = Vector2(44, 44)
	circle.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	circle.add_theme_stylebox_override("panel", Base.style(Base.MINT, 0, 22))
	column.add_child(circle)
	var center := CenterContainer.new()
	circle.add_child(center)
	center.add_child(Glyphs.icon(icon_kind, Vector2(22, 22)))
	var heading: Label = ui.label(column, title, 16)
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	if not body.is_empty():
		var text: Label = ui.label(column, body, 13, ui.MUTED)
		text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	return column

## Turns an existing Button into a list row with a leading mark, two lines of
## copy, an optional status chip and trailing meta text. The button's own text
## stays set (focus, tooltips, tests, accessibility) but is drawn transparent.
static func rich_row(button: Button, ui, title: String, subtitle: String = "", meta: String = "", chip_text: String = "", chip_tone: String = "gray", icon_kind: String = "", team: String = "", accent: Color = Color.TRANSPARENT) -> Button:
	button.clip_text = true
	button.autowrap_mode = TextServer.AUTOWRAP_OFF
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.tooltip_text = title
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color", "font_disabled_color"]:
		button.add_theme_color_override(state, Color(0, 0, 0, 0))
	var normal := Base.style(Base.PAPER, 10, 12, Base.LINE)
	var hover := Base.style(Color("f1f5ec"), 10, 12, Color("b9c9b8"))
	var pressed := Base.style(Base.MINT, 10, 12, Base.GREEN)
	if accent.a > 0:
		for box in [normal, hover, pressed]:
			box.border_width_left = 4
			box.border_color = accent if box == normal else box.border_color
	button.add_theme_stylebox_override("normal", normal)
	button.add_theme_stylebox_override("hover", hover)
	button.add_theme_stylebox_override("pressed", pressed)
	button.add_theme_stylebox_override("hover_pressed", pressed)
	button.add_theme_stylebox_override("disabled", Base.style(Color("f1efe7"), 10, 12, Base.LINE))
	var row := HBoxContainer.new()
	row.name = "RichRow"
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	row.offset_left = 14; row.offset_right = -12; row.offset_top = 6; row.offset_bottom = -6
	row.add_theme_constant_override("separation", 12)
	button.add_child(row)
	var mark: Control = null
	if not team.is_empty(): mark = TeamVisuals.badge(row, team, 34)
	if mark == null and not icon_kind.is_empty():
		var circle := PanelContainer.new()
		circle.custom_minimum_size = Vector2(34, 34)
		circle.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		circle.mouse_filter = Control.MOUSE_FILTER_IGNORE
		circle.add_theme_stylebox_override("panel", Base.style(Base.MINT, 0, 17))
		row.add_child(circle)
		var center := CenterContainer.new()
		center.mouse_filter = Control.MOUSE_FILTER_IGNORE
		circle.add_child(center)
		center.add_child(Glyphs.icon(icon_kind, Vector2(18, 18)))
	if mark: mark.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var words := VBoxContainer.new()
	words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	words.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	words.mouse_filter = Control.MOUSE_FILTER_IGNORE
	words.add_theme_constant_override("separation", 1)
	row.add_child(words)
	var main: Label = ui.label(words, title, 15)
	main.autowrap_mode = TextServer.AUTOWRAP_OFF
	main.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	main.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if not subtitle.is_empty():
		var second: Label = ui.label(words, subtitle, 12, ui.MUTED)
		second.autowrap_mode = TextServer.AUTOWRAP_OFF
		second.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		second.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if not chip_text.is_empty():
		chip(row, chip_text, chip_tone)
	if not meta.is_empty():
		var right: Label = ui.label(row, meta, 13, ui.MUTED)
		right.autowrap_mode = TextServer.AUTOWRAP_OFF
		right.size_flags_horizontal = Control.SIZE_SHRINK_END
		right.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		right.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		right.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var arrow := Glyphs.icon("chevron_right", Vector2(16, 16))
	arrow.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(arrow)
	button.custom_minimum_size.y = 58 if not subtitle.is_empty() else 46
	return button

static func event_tier(kind: String) -> Array:
	return EVENT_TIERS.get(kind, ["赛事", "gray"])

## Short Chinese month-day ("03/18") for dense rows.
static func short_date(value: String) -> String:
	var parts := value.split("-")
	return "%s/%s" % [parts[1], parts[2]] if parts.size() == 3 else value

## A small vector chicken in the player's saved colours, for profile headers.
class ChickenBadge extends Control:
	var feather := Color("fff6e6")
	var comb := Color("d9584a")
	var beak := Color("f0a03c")
	var jersey := Color("27445a")
	var ring := Color("d3e6d7")
	func _ready() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		resized.connect(queue_redraw)
	func set_colors(values: Dictionary) -> void:
		# Same keys as appearance_customization.gd (body/comb/beak/jersey colours).
		for pair in [["feather", "body_color"], ["comb", "comb_color"], ["beak", "beak_color"], ["jersey", "jersey_color"]]:
			var raw = values.get(pair[1], "")
			if raw is String and Color.html_is_valid(raw): set(pair[0], Color(raw))
		queue_redraw()
	func _blob(center: Vector2, radius: Vector2, colour: Color) -> void:
		var points := PackedVector2Array()
		for i in range(40):
			var a := TAU * i / 40.0
			points.append(center + Vector2(cos(a) * radius.x, sin(a) * radius.y))
		draw_colored_polygon(points, colour)
	func _draw() -> void:
		var s := minf(size.x, size.y)
		var o := (size - Vector2(s, s)) / 2.0
		var u := s / 100.0
		draw_circle(o + Vector2(50, 50) * u, 50 * u, ring, true, -1, true)
		_blob(o + Vector2(50, 86) * u, Vector2(30, 18) * u, jersey)
		_blob(o + Vector2(50, 54) * u, Vector2(27, 29) * u, feather)
		for i in range(3):
			draw_circle(o + Vector2(40 + i * 10, 24 - (4 if i == 1 else 0)) * u, 7 * u, comb, true, -1, true)
		draw_circle(o + Vector2(41, 51) * u, 3.4 * u, Color("22342b"), true, -1, true)
		draw_circle(o + Vector2(59, 51) * u, 3.4 * u, Color("22342b"), true, -1, true)
		draw_colored_polygon(PackedVector2Array([o + Vector2(44, 59) * u, o + Vector2(56, 59) * u, o + Vector2(50, 67) * u]), beak)
		_blob(o + Vector2(50, 70) * u, Vector2(3.5, 4.5) * u, comb)
		draw_circle(o + Vector2(35, 60) * u, 4 * u, Color(1, .55, .55, .35), true, -1, true)
		draw_circle(o + Vector2(65, 60) * u, 4 * u, Color(1, .55, .55, .35), true, -1, true)

static func chicken_badge(parent: Node, appearance: Dictionary, diameter: float = 64.0) -> Control:
	var badge := ChickenBadge.new()
	badge.name = "ChickenBadge"
	badge.custom_minimum_size = Vector2(diameter, diameter)
	badge.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	badge.set_colors(appearance)
	parent.add_child(badge)
	return badge

## Match-day hero: dark card with both team marks, "VS", event and details.
static func match_hero(parent: Node, ui, own: String, opponent: String, event_name: String, details: String, tier_kind: String = "") -> PanelContainer:
	var card := PanelContainer.new()
	card.name = "MatchHero"
	card.add_theme_stylebox_override("panel", Base.raised(Color("22342b"), 20, 18, Color(0, 0, 0, 0)))
	if parent.get_meta("phone_edge", false): Base.inset(parent, card)
	else: parent.add_child(card)
	var stack := VBoxContainer.new()
	stack.add_theme_constant_override("separation", 10)
	card.add_child(stack)
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 8)
	stack.add_child(top)
	if not tier_kind.is_empty():
		var tier := event_tier(tier_kind)
		chip(top, tier[0], tier[1], 12)
	var event_label: Label = ui.label(top, event_name, 14, Color("cfe0d4"))
	event_label.autowrap_mode = TextServer.AUTOWRAP_OFF
	event_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	event_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 16)
	stack.add_child(row)
	for index in range(2):
		var team := own if index == 0 else opponent
		var side := VBoxContainer.new()
		side.alignment = BoxContainer.ALIGNMENT_CENTER
		side.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		side.add_theme_constant_override("separation", 6)
		row.add_child(side)
		var holder := CenterContainer.new()
		holder.custom_minimum_size = Vector2(0, 64)
		side.add_child(holder)
		var mark := TeamVisuals.badge(holder, team, 60)
		if mark == null:
			var initials := PanelContainer.new()
			initials.custom_minimum_size = Vector2(60, 60)
			initials.add_theme_stylebox_override("panel", Base.style(Color("33493e"), 0, 16))
			holder.add_child(initials)
			var text: Label = ui.label(initials, team.substr(0, 3).to_upper(), 18, Color("f4f1e6"))
			text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			text.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		var name_label: Label = ui.label(side, team, 18, Color("fffdf6"))
		name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		name_label.autowrap_mode = TextServer.AUTOWRAP_OFF
		name_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		if index == 0:
			var vs: Label = ui.label(row, "VS", 22, Color("e8c483"))
			vs.autowrap_mode = TextServer.AUTOWRAP_OFF
			vs.custom_minimum_size.x = 40
			vs.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
			vs.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var info: Label = ui.label(stack, details, 13, Color("cfe0d4"))
	info.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	return card

## A large choice tile. button.text stays for focus/tests but is drawn
## transparent; the visible title + one-line description sit on top.
static func action_tile(button: Button, ui, title: String, description: String, primary: bool = false) -> Button:
	button.clip_text = true
	button.autowrap_mode = TextServer.AUTOWRAP_OFF
	button.custom_minimum_size.y = 74
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color", "font_disabled_color"]:
		button.add_theme_color_override(state, Color(0, 0, 0, 0))
	var fill := Base.GREEN if primary else Base.PAPER
	var edge := Base.GREEN if primary else Base.LINE
	button.add_theme_stylebox_override("normal", Base.style(fill, 12, 14, edge))
	button.add_theme_stylebox_override("hover", Base.style(fill.lightened(0.08) if primary else Color("f1f5ec"), 12, 14, edge))
	button.add_theme_stylebox_override("pressed", Base.style(fill.darkened(0.1) if primary else Base.MINT, 12, 14, edge))
	button.add_theme_stylebox_override("disabled", Base.style(Color("eceae1"), 12, 14, Base.LINE))
	var stack := VBoxContainer.new()
	stack.name = "ActionTile"
	stack.mouse_filter = Control.MOUSE_FILTER_IGNORE
	stack.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	stack.offset_left = 16; stack.offset_right = -14; stack.offset_top = 10; stack.offset_bottom = -10
	stack.alignment = BoxContainer.ALIGNMENT_CENTER
	stack.add_theme_constant_override("separation", 2)
	button.add_child(stack)
	var ink := Color.WHITE if primary else Base.INK
	var muted := Color(1, 1, 1, 0.78) if primary else Base.MUTED
	var head: Label = ui.label(stack, title, 16, ink)
	head.autowrap_mode = TextServer.AUTOWRAP_OFF
	head.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var body: Label = ui.label(stack, description, 12, muted)
	body.autowrap_mode = TextServer.AUTOWRAP_OFF
	body.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	button.set_meta("tile_labels", [head, body])
	return button
