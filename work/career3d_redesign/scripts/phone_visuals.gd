extends RefCounted
## Code-drawn phone art. No icon font, web widget or downloaded bitmap is needed.
## Keep the reference's fine green lines and quiet cream/green landscape.
const GREEN := Color("3d6a55")

class Glyph extends Control:
	var kind := "mail"
	var ink := Color("3d6a55")
	var unit := Vector2.ONE
	var stroke := 1.6

	func _ready() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		resized.connect(queue_redraw)

	func line(points: Array) -> void:
		var scaled := PackedVector2Array()
		for point in points:
			scaled.append(Vector2(point[0], point[1]) * unit)
		draw_polyline(scaled, ink, stroke, true)

	func arc(center: Vector2, radius: float, start: float, end: float) -> void:
		var points := PackedVector2Array()
		for i in range(25):
			var angle := lerpf(start, end, float(i) / 24.0)
			points.append((center + Vector2(cos(angle), sin(angle)) * radius) * unit)
		draw_polyline(points, ink, stroke, true)

	func rounded(points: Rect2, radius: float) -> void:
		var box := StyleBoxFlat.new()
		box.bg_color = Color.TRANSPARENT
		box.border_color = ink
		box.set_border_width_all(maxi(1, roundi(stroke)))
		box.set_corner_radius_all(roundi(radius * unit.x))
		draw_style_box(box, Rect2(points.position * unit, points.size * unit))

	func _draw() -> void:
		unit = size / Vector2(24, 24)
		stroke = maxf(1, 1.6 * minf(unit.x, unit.y))
		match kind:
			"mail":
				rounded(Rect2(3, 5, 18, 14), 2)
				line([[3, 6], [12, 13], [21, 6]])
			"chat":
				rounded(Rect2(2, 3, 14, 11), 2)
				line([[5, 14], [5, 18], [10, 14]])
				line([[19, 8], [22, 8], [22, 21], [18, 18], [12, 18]])
			"match", "trophy":
				line([[8, 3], [16, 3], [16, 8]])
				arc(Vector2(12, 8), 4, 0, PI)
				line([[8, 8], [8, 3]])
				line([[8, 5], [3, 5], [3, 8]])
				arc(Vector2(5, 8), 2, 0, PI)
				line([[7, 8], [8, 8]])
				line([[16, 5], [21, 5], [21, 8]])
				arc(Vector2(19, 8), 2, 0, PI)
				line([[17, 8], [16, 8]])
				line([[12, 12], [12, 17], [8, 20], [16, 20]])
			"calendar":
				rounded(Rect2(3, 5, 18, 16), 2)
				line([[7, 3], [7, 7]])
				line([[17, 3], [17, 7]])
				line([[3, 10], [21, 10]])
				for y in [13, 17]:
					for x in [7, 12, 17]:
						draw_circle(Vector2(x, y) * unit, stroke * .62, ink, true, -1, true)
			"profile", "user":
				arc(Vector2(12, 7), 4, 0, TAU)
				arc(Vector2(12, 20), 7, PI, TAU)
				line([[5, 20], [5, 22]])
				line([[19, 20], [19, 22]])
			"settings":
				line([[3, 6], [9, 6]])
				line([[15, 6], [21, 6]])
				arc(Vector2(12, 6), 3, 0, TAU)
				line([[3, 17], [13, 17]])
				line([[19, 17], [21, 17]])
				arc(Vector2(16, 17), 3, 0, TAU)
			"chevron_left":
				line([[15, 5], [8, 12], [15, 19]])
			"chevron_right":
				line([[9, 5], [16, 12], [9, 19]])
			"home":
				arc(Vector2(12, 12), 8, 0, TAU)
			"clipboard":
				rounded(Rect2(5, 4, 14, 18), 2)
				rounded(Rect2(9, 2, 6, 5), 1)
				line([[9, 12], [15, 12]])
				line([[9, 17], [15, 17]])
			"news":
				rounded(Rect2(3, 4, 18, 17), 2)
				line([[7, 8], [17, 8]])
				line([[7, 12], [17, 12]])
				line([[7, 16], [12, 16]])
			"signal":
				for i in range(4):
					var x := 4.0 + i * 4.0
					line([[x, 20], [x, 16.0 - i * 4.0]])
			"wifi":
				arc(Vector2(12, 22), 16, -PI * .75, -PI * .25)
				arc(Vector2(12, 22), 10, -PI * .75, -PI * .25)
				draw_circle(Vector2(12, 20) * unit, stroke, ink, true, -1, true)
			"battery":
				rounded(Rect2(2, 6, 18, 12), 2)
				line([[22, 10], [22, 14]])
				for x in [6, 10, 14]:
					line([[x, 9], [x, 15]])

class Landscape extends Control:
	func _ready() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		clip_contents = true
		resized.connect(queue_redraw)

	func ellipse(center: Vector2, radius: Vector2, color: Color, rotation: float = 0.0) -> void:
		var polygon := PackedVector2Array()
		for i in range(96):
			var angle := TAU * float(i) / 96.0
			polygon.append(center + Vector2(cos(angle) * radius.x, sin(angle) * radius.y).rotated(rotation))
		draw_colored_polygon(polygon, color)

	func _draw() -> void:
		var w := size.x
		var h := size.y
		if w <= 0 or h <= 0:
			return
		draw_circle(Vector2(w - 64.5, 35.5), 19.5, Color("eacb7f"), true, -1, true)
		# Match the original rotated hills, including the sun peeking over the ridge.
		ellipse(Vector2(w * .30, h + 10), Vector2(w * .50, 105), Color("cee1d2"), deg_to_rad(-11))
		ellipse(Vector2(w * .75, h + 22), Vector2(w * .60, 120), Color("dae8d8"), deg_to_rad(15))
		# Let the hills settle into the page instead of ending on a hard clip line.
		var fade := minf(h * .3, 30.0)
		var ground := Color("f8f4e9")
		var clear := Color(ground, 0.0)
		draw_polygon(PackedVector2Array([Vector2(0, h - fade), Vector2(w, h - fade), Vector2(w, h), Vector2(0, h)]),
			PackedColorArray([clear, clear, ground, ground]))

static func icon(kind: String, dimensions: Vector2 = Vector2(26, 26)) -> Control:
	var glyph := Glyph.new()
	glyph.kind = kind
	glyph.custom_minimum_size = dimensions
	glyph.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return glyph

static func wallpaper(height: float = 120) -> Control:
	var landscape := Landscape.new()
	landscape.name = "HomeLandscape"
	landscape.custom_minimum_size.y = height
	landscape.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	landscape.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return landscape

static func status_icons() -> Control:
	var row := HBoxContainer.new()
	row.name = "PhoneStatusIcons"
	row.add_theme_constant_override("separation", 4)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for kind in ["signal", "wifi", "battery"]:
		row.add_child(icon(kind, Vector2(14, 14)))
	return row
