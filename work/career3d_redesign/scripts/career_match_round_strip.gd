extends Control
## Repaint only completed winners. Future slots do not disclose saved outcomes.
const WIN := Color("478bc5")
const LOSS := Color("c96560")
const EMPTY := Color("d9dfda")
const TEXT := Color("667268")
var rounds: Array = []
var completed := 0
var own_side := ""

func _init() -> void:
	name = "CareerMatchRoundStrip"
	custom_minimum_size.y = 28
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	resized.connect(queue_redraw)

func configure(winners: Array, shown: int, side: String) -> void:
	rounds = winners.duplicate()
	completed = clampi(shown, 0, rounds.size())
	own_side = side
	queue_redraw()

func _draw() -> void:
	if rounds.is_empty(): return
	var slots := maxi(24, completed)
	var groups := 1 + maxi(0, ceili(float(slots - 24) / 3.0))
	var gap := 3.0
	var split_gap := 9.0
	var cell_width := maxf(3.0, (size.x - gap * (slots - 1) - split_gap * groups) / slots)
	var x := 0.0
	var font := get_theme_default_font()
	for i in range(slots):
		if i == 12 or i == 24 or (i > 24 and (i - 24) % 3 == 0): x += split_gap
		var color := EMPTY
		if i < completed:
			color = WIN if str(rounds[i]) == own_side else (LOSS if own_side in ["a", "b"] else Color("91aaa0"))
		draw_style_box(style_box(color), Rect2(x, 1, cell_width, 14))
		if i == 0 or i == 11 or i == 12 or i == 23 or i == slots - 1:
			draw_string(font, Vector2(x, 26), str(i + 1), HORIZONTAL_ALIGNMENT_CENTER, cell_width, 10, TEXT)
		x += cell_width + gap

func style_box(color: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(2)
	return style
