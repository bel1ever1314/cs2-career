extends RefCounted
## Native line icons, landscape and explicitly labelled missing-image art.
const Phone = preload("res://scripts/phone_visuals.gd")

static func icon(kind: String, dimensions: Vector2 = Vector2(24, 24)) -> Control:
	if kind in ["finance", "transfers"]:
		var glyph := BusinessGlyph.new()
		glyph.kind = kind
		glyph.custom_minimum_size = dimensions
		return glyph
	return Phone.icon(kind, dimensions)

class BusinessGlyph extends Control:
	var kind := "finance"
	var unit := Vector2.ONE
	var stroke := 1.6
	var ink := Color("3d6a55")
	func _ready() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		resized.connect(queue_redraw)
	func line(points: Array) -> void:
		var scaled := PackedVector2Array()
		for point in points:
			scaled.append(Vector2(point[0], point[1]) * unit)
		draw_polyline(scaled, ink, stroke, true)
	func rounded(rect: Rect2, radius: float) -> void:
		var box := StyleBoxFlat.new()
		box.bg_color = Color.TRANSPARENT
		box.border_color = ink
		box.set_border_width_all(maxi(1, roundi(stroke)))
		box.set_corner_radius_all(roundi(radius * unit.x))
		draw_style_box(box, Rect2(rect.position * unit, rect.size * unit))
	func _draw() -> void:
		unit = size / Vector2(24, 24)
		stroke = maxf(1, 1.6 * minf(unit.x, unit.y))
		if kind == "finance":
			rounded(Rect2(3, 5, 18, 15), 2)
			line([[3, 8], [21, 8]])
			rounded(Rect2(14, 11, 7, 5), 1)
			draw_circle(Vector2(17, 13.5) * unit, stroke * .5, ink)
		else:
			line([[3, 8], [20, 8], [16, 4]])
			line([[20, 8], [16, 12]])
			line([[21, 17], [4, 17], [8, 13]])
			line([[4, 17], [8, 21]])

static func wallpaper() -> Control:
	var node := Phone.Landscape.new()
	node.name = "DesktopWallpaper"
	node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	node.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	return node

class SkinPlaceholder extends Control:
	var weapon := ""
	var paint := Color("8daf98")
	func _ready() -> void:
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		resized.connect(queue_redraw)
	func _draw() -> void:
		var c := size / 2.0
		var scale_factor := minf(size.x / 205.0, size.y / 100.0)
		draw_set_transform(c, -0.09, Vector2.ONE * scale_factor)
		if weapon.to_lower().contains("knife") or weapon.contains("刀"):
			draw_polygon(PackedVector2Array([Vector2(-73, 1), Vector2(-10, -15), Vector2(38, -8), Vector2(20, 11)]), PackedColorArray([paint]))
			draw_rect(Rect2(18, -6, 56, 13), Color("515b49"))
		else:
			draw_rect(Rect2(-42, -8, 85, 19), paint)
			draw_rect(Rect2(32, -10, 55, 5), Color("5c6258"))
			draw_rect(Rect2(-81, -4, 42, 15), Color("5c6258"))
			draw_rect(Rect2(-14, 10, 10, 22), paint)
			draw_rect(Rect2(16, 9, 13, 24), paint)
