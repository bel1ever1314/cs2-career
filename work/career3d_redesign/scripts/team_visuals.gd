extends RefCounted
## Genuine local club marks. No URLs or executable media content.
const UI = preload("res://scripts/computer_ui.gd")
static var textures: Dictionary = {}

static func texture(team: String) -> Texture2D:
	var paths: Dictionary = CareerBridge.context.get("media", {}).get("team_backgrounds", {})
	var path := str(paths.get(team, ""))
	if path.is_empty():
		for known in paths:
			if str(known).to_lower() == team.to_lower():
				path = str(paths[known])
				break
	if path.is_empty(): return null
	if textures.has(path): return textures[path]
	# Cache failed local loads too: rebuilding a long list must not repeatedly
	# parse the same SVG or revisit an unavailable file.
	textures[path] = null
	if not FileAccess.file_exists(path): return null
	var source := Image.new()
	if source.load(path) != OK: return null
	var needs_backdrop := _needs_backdrop(source)
	var mark := ImageTexture.create_from_image(_with_backdrop(source) if needs_backdrop else source)
	mark.set_meta("club_backdrop", needs_backdrop)
	textures[path] = mark
	return textures[path]

static func _needs_backdrop(source: Image) -> bool:
	# Ignore transparent pixels when measuring a mark's visible brightness.
	# Sampling bounds one-time SVG analysis even for large local images.
	var sample := source.duplicate() as Image
	if sample.get_width() > 64 or sample.get_height() > 64:
		sample.resize(64, 64, Image.INTERPOLATE_BILINEAR)
	var light := 0.0
	var coverage := 0.0
	for y in sample.get_height():
		for x in sample.get_width():
			var pixel := sample.get_pixel(x, y)
			light += (pixel.r * .2126 + pixel.g * .7152 + pixel.b * .0722) * pixel.a
			coverage += pixel.a
	return coverage > 0.0 and light / coverage > .78

static func _with_backdrop(source: Image) -> Image:
	var padding := maxi(2, ceili(maxi(source.get_width(), source.get_height()) * .12))
	var width := source.get_width() + padding * 2
	var height := source.get_height() + padding * 2
	var radius := maxf(3.0, minf(width, height) * .18)
	var badge_image := Image.create(width, height, false, Image.FORMAT_RGBA8)
	badge_image.fill(Color.TRANSPARENT)
	for y in height:
		for x in width:
			var nearest := Vector2(clampf(x + .5, radius, width - radius), clampf(y + .5, radius, height - radius))
			var edge := Vector2(x + .5, y + .5).distance_to(nearest)
			if edge <= radius:
				var fill := UI.GREEN
				fill.a = clampf(radius - edge, 0.0, 1.0)
				badge_image.set_pixel(x, y, fill)
	var original := source.duplicate() as Image
	original.convert(Image.FORMAT_RGBA8)
	badge_image.blend_rect(original, Rect2i(Vector2i.ZERO, original.get_size()), Vector2i(padding, padding))
	return badge_image

static func button_logo(button: Button, team: String, size: int = 32) -> Button:
	var mark := texture(team)
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	if mark == null: return button
	button.icon = mark
	button.expand_icon = true
	button.icon_alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.add_theme_constant_override("icon_max_width", size)
	button.add_theme_constant_override("h_separation", 12)
	button.custom_minimum_size.y = maxf(button.custom_minimum_size.y, size + 16)
	button.set_meta("team_logo", team)
	return button

static func badge(parent: Node, team: String, size: int = 36) -> TextureRect:
	var mark := texture(team)
	if mark == null: return null
	var art := TextureRect.new()
	art.name = "TeamListLogo"
	art.texture = mark
	art.custom_minimum_size = Vector2(size, size)
	art.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	art.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	art.mouse_filter = Control.MOUSE_FILTER_IGNORE
	art.set_meta("team_logo", team)
	parent.add_child(art)
	return art

static func banner(parent: Node, title: String, team: String, subtitle: String = "") -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.name = "TeamBrandBanner"
	panel.custom_minimum_size.y = 108
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.add_theme_stylebox_override("panel", UI.style(Color("edf1e5"), 18, 12, UI.LINE))
	parent.add_child(panel)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	panel.add_child(row)
	var column := VBoxContainer.new()
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	column.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	column.add_theme_constant_override("separation", 8)
	row.add_child(column)
	UI.label(column, title, 26)
	if not subtitle.is_empty(): UI.label(column, subtitle, 14, UI.MUTED)
	var mark := texture(team)
	if mark != null:
		var art := TextureRect.new()
		art.name = "TeamBrandBackground"
		art.texture = mark
		art.custom_minimum_size = Vector2(88, 82)
		art.size_flags_horizontal = Control.SIZE_SHRINK_END
		art.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		art.mouse_filter = Control.MOUSE_FILTER_IGNORE
		art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		art.modulate = Color(1, 1, 1, .72 if mark.get_meta("club_backdrop", false) else .48)
		row.add_child(art)
	return column

static func match_heading(parent: Node, team_a: String, team_b: String, score: String, narrow: bool = false) -> void:
	var box := UI.card(parent)
	var row := HBoxContainer.new()
	row.name = "MatchTeamHeader"
	row.add_theme_constant_override("separation", 10)
	box.add_child(row)
	for index in range(2):
		if index == 1:
			var score_label := UI.label(row, score, 22 if narrow else 34)
			score_label.name = "MatchSeriesScore"
			score_label.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
			score_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			score_label.autowrap_mode = TextServer.AUTOWRAP_OFF
		var team := team_a if index == 0 else team_b
		var column := VBoxContainer.new()
		column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		column.alignment = BoxContainer.ALIGNMENT_CENTER
		row.add_child(column)
		badge(column, team, 38 if narrow else 52)
		var caption := UI.label(column, team, 13 if narrow else 20)
		caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		caption.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		caption.max_lines_visible = 2

static func map_texture(map_name: String) -> Texture2D:
	var paths: Dictionary = CareerBridge.context.get("media", {}).get("map_backgrounds", {})
	var path := str(paths.get(map_name, paths.get(map_name.trim_prefix("de_"), paths.get("de_" + map_name, ""))))
	if path.is_empty(): return null
	if textures.has(path): return textures[path]
	textures[path] = null
	if not FileAccess.file_exists(path): return null
	var source := Image.new()
	if source.load(path) == OK: textures[path] = ImageTexture.create_from_image(source)
	return textures[path]

static func map_banner(parent: Node, map_name: String, subtitle: String = "", height: int = 120) -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.name = "MatchMapPhoto"
	panel.custom_minimum_size.y = height
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.add_theme_stylebox_override("panel", UI.style(UI.GREEN, 14, 10))
	parent.add_child(panel)
	var image := map_texture(map_name)
	if image:
		var art := TextureRect.new()
		art.name = "CareerMatchMapBackground"
		art.texture = image
		art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		art.mouse_filter = Control.MOUSE_FILTER_IGNORE
		panel.add_child(art)
		var veil := ColorRect.new()
		veil.color = Color(0.08, 0.16, 0.13, .62)
		veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
		panel.add_child(veil)
	var column := VBoxContainer.new()
	column.alignment = BoxContainer.ALIGNMENT_CENTER
	panel.add_child(column)
	UI.label(column, map_name.trim_prefix("de_").capitalize(), 24, UI.PAPER)
	if not subtitle.is_empty(): UI.label(column, subtitle, 15, Color("dbe8dd"))
	return column
