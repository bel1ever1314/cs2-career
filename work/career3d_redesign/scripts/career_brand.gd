extends Control
## Code-native wordmark shared by the engine splash and live loading screen.
const PAPER := Color("f8f4e9")
const INK := Color("22342b")
const GREEN := Color("2f6b52")
var face := SystemFont.new()

func _init() -> void:
	face.font_names = PackedStringArray(["Arial", "Noto Sans"])
	face.font_weight = 700
	custom_minimum_size = Vector2(600, 300)
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func centered(text: String, baseline: float, font_size: int, color: Color) -> void:
	var width := face.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	draw_string(face, Vector2((600 - width) / 2, baseline), text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, color)

func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, Vector2(600, 300)), PAPER)
	draw_circle(Vector2(300, 45), 4, GREEN)
	centered("CS2", 113, 44, GREEN)
	centered("CAREER", 203, 86, INK)
	draw_line(Vector2(246, 239), Vector2(354, 239), GREEN, 3, true)
	centered("YOUR NEXT CHAPTER", 278, 13, GREEN)
