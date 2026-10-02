extends Control
## Small original vector trophy; no external image or downloaded brand artwork.
var gold := Color("d9ac48")

func _init() -> void:
	custom_minimum_size = Vector2(92, 92)
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _draw() -> void:
	var scale_size := minf(size.x, size.y) / 92.0
	draw_set_transform((size - Vector2(92, 92) * scale_size) / 2.0, 0, Vector2.ONE * scale_size)
	draw_circle(Vector2(46, 44), 41, Color("dfbd60", .12))
	draw_arc(Vector2(29, 32), 15, PI * .48, PI * 1.6, 20, gold, 5, true)
	draw_arc(Vector2(63, 32), 15, -PI * .6, PI * .52, 20, gold, 5, true)
	draw_colored_polygon(PackedVector2Array([Vector2(26, 14), Vector2(66, 14), Vector2(62, 42), Vector2(53, 53), Vector2(39, 53), Vector2(30, 42)]), gold)
	draw_line(Vector2(35, 18), Vector2(32, 36), Color("fff0b1"), 3, true)
	draw_rect(Rect2(42, 51, 8, 17), gold)
	draw_style_box(_base(), Rect2(29, 69, 34, 9))
	draw_rect(Rect2(22, 80, 48, 5), Color("b58b35"))

func _base() -> StyleBoxFlat:
	var base := StyleBoxFlat.new()
	base.bg_color = gold
	base.set_corner_radius_all(3)
	return base
