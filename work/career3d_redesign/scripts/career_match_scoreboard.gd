extends VBoxContainer
## Shared, aligned ten-player scorecard. Updating cells never rebuilds the page.
const UI = preload("res://scripts/computer_ui.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")
const SURFACE := Color("283a33")
const HEADER := Color("20312a")
const TEXT := Color("edf3ed")
const DIM := Color("b2c3b9")
const BLUE := Color("82b7db")
const RED := Color("dc9b95")
const FIELDS := ["k", "d", "a", "adr", "kast", "rating"]
const WIDTHS := [40, 40, 40, 64, 64, 64]
var cells: Dictionary = {}
var own_id := ""
var player_selected: Callable
var roomy := false

static func mount(parent: Node, rows: Array, teams: Array, player_id: String, callback: Callable, caption: String = "十人战绩", large_report: bool = false) -> VBoxContainer:
	var board = load("res://scripts/career_match_scoreboard.gd").new()
	board.name = "CareerMatchFullStats"
	board.own_id = player_id
	board.player_selected = callback
	board.roomy = large_report
	board.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	board.add_theme_constant_override("separation", 0)
	parent.add_child(board)
	board.build(rows, teams, caption)
	return board

func build(rows: Array, teams: Array, caption: String) -> void:
	var top := panel_row(HEADER, 27 if roomy else 18)
	var title := name_cell(top, caption, 12 if roomy else 11, DIM)
	title.name = "CareerScoreboardCaption"
	for i in range(FIELDS.size()):
		numeric_cell(top, ["K", "D", "A", "ADR", "KAST", "Rating"][i], i, DIM, 12 if roomy else 11)
	var ordered := teams.duplicate()
	for row in rows:
		if str(row.get("team", "")) not in ordered: ordered.append(str(row.get("team", "")))
	for team in ordered:
		var team_rows: Array = []
		for row in rows:
			if str(row.get("team", "")) == str(team): team_rows.append(row)
		if team_rows.is_empty(): continue
		var team_panel := panel_row(HEADER.lightened(0.055), 27 if roomy else 17)
		TeamVisuals.badge(team_panel, str(team), 22 if roomy else 18)
		var is_own_team := false
		for row in team_rows:
			if not own_id.is_empty() and _player_id(row) == own_id: is_own_team = true
		name_cell(team_panel, str(team) + ("  ·  你方" if is_own_team else ""), 13 if roomy else 11, BLUE if is_own_team else RED)
		for row in team_rows: add_player(row)
	update_rows(rows)

func panel_row(color: Color, height: int) -> HBoxContainer:
	var panel := PanelContainer.new()
	panel.custom_minimum_size.y = height
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var surface := UI.style(color, 0, 0)
	# Side padding keeps names and numbers off the panel edge.
	surface.content_margin_left = 12
	surface.content_margin_right = 12
	if roomy:
		surface.content_margin_top = 3
		surface.content_margin_bottom = 3
	panel.add_theme_stylebox_override("panel", surface)
	add_child(panel)
	var line := HBoxContainer.new()
	line.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	line.add_theme_constant_override("separation", 4)
	panel.add_child(line)
	return line

func name_cell(parent: Node, value: String, font_size: int, color: Color) -> Label:
	var label := UI.label_exact(parent, value, font_size, color)
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.custom_minimum_size.x = 155 if roomy else 145
	label.autowrap_mode = TextServer.AUTOWRAP_OFF
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	return label

func numeric_cell(parent: Node, value: String, index: int, color: Color, font_size: int = 12) -> Label:
	var label := UI.label_exact(parent, value, maxi(font_size, 14) if roomy and font_size == 12 else font_size, color)
	label.size_flags_horizontal = Control.SIZE_FILL
	label.custom_minimum_size.x = WIDTHS[index] * (1.13 if roomy else 1.0)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	label.autowrap_mode = TextServer.AUTOWRAP_OFF
	return label

func add_player(row: Dictionary) -> void:
	var id := _player_id(row)
	var key := _row_key(row)
	var mine := not own_id.is_empty() and id == own_id
	var line := panel_row(UI.MINT if mine else SURFACE, 28 if roomy else 19)
	line.get_parent().name = "CareerScoreRow_" + id.validate_node_name()
	var button := UI.button(line, str(row.get("name", row.get("player", ""))) + ("  ·  你" if mine else ""), select_player.bind(id))
	button.name = "CareerScorePlayer_" + id.validate_node_name()
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.custom_minimum_size = Vector2(155 if roomy else 145, 22 if roomy else 19)
	button.autowrap_mode = TextServer.AUTOWRAP_OFF
	button.clip_text = true
	button.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	button.add_theme_font_size_override("font_size", 14 if roomy else 12)
	button.disabled = id.is_empty()
	for state in ["normal", "hover", "pressed", "disabled"]:
		button.add_theme_stylebox_override(state, UI.style(UI.MINT if mine else SURFACE.lightened(0.04 if state == "hover" else 0), 0, 0))
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_disabled_color"]:
		button.add_theme_color_override(state, UI.INK if mine else TEXT)
	button.add_theme_stylebox_override("focus", UI.style(Color.TRANSPARENT, 0, 0, BLUE))
	var row_cells := []
	for i in range(FIELDS.size()):
		var cell := numeric_cell(line, "—", i, UI.INK if mine else TEXT)
		cell.name = "CareerScore_%s_%s" % [id.validate_node_name(), FIELDS[i]]
		row_cells.append(cell)
	cells[key] = row_cells

func select_player(id: String) -> void:
	if not id.is_empty() and player_selected.is_valid(): player_selected.call(id)

func update_rows(rows: Array) -> void:
	for row in rows:
		var key := _row_key(row)
		if not cells.has(key): continue
		for i in range(FIELDS.size()):
			if is_instance_valid(cells[key][i]): cells[key][i].text = measured_text(row.get(FIELDS[i]), FIELDS[i])

static func _row_key(row: Dictionary) -> String:
	var id := _player_id(row)
	return id if not id.is_empty() else str(row.get("team", "")) + "|" + str(row.get("name", row.get("player", "")))

static func _player_id(row: Dictionary) -> String:
	var id = row.get("player_id", row.get("id", ""))
	return str(id) if id != null else ""

static func measured_text(value: Variant, field: String) -> String:
	if typeof(value) not in [TYPE_INT, TYPE_FLOAT]: return "—"
	if field == "rating": return "%.2f" % float(value)
	if field == "adr": return "%.1f" % float(value)
	if field == "kast": return "%.0f%%" % (float(value) * (100 if float(value) <= 1 else 1))
	return str(int(value))
