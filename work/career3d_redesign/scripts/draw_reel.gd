extends Control
## A presentation of an already committed result. No outcome selection or writes.
signal revealed(result: Dictionary)
const UI = preload("res://scripts/computer_ui.gd")
const CARD_COUNT := 36
const LANDING_INDEX := 32
const CARD_SIZE := Vector2(164, 174)
const STRIDE := 176.0
var result: Dictionary = {}
var cards: Array[Dictionary] = []
var elapsed := 0.0
var duration := 4.0
var offset := 0.0
var running := false
var completed := false
var textures: Dictionary = {}
var badge_backgrounds: Dictionary = {}

func _init() -> void:
	custom_minimum_size = Vector2(0, 214)
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	clip_contents = true
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func start(choices: Array, saved_result: Dictionary, seconds: float = 4.0) -> bool:
	if running or saved_result.is_empty(): return false
	result = saved_result.duplicate(true)
	cards.clear()
	var pool: Array = choices if not choices.is_empty() else [saved_result]
	for index in range(CARD_COUNT):
		var card: Dictionary = pool[index % pool.size()]
		cards.append(card.duplicate(true))
	cards[LANDING_INDEX] = result.duplicate(true)
	for card in cards:
		for path in [str(card.get("art_path", "")), str(card.get("badge_path", ""))]:
			if path.is_empty() or textures.has(path): continue
			textures[path] = null
			if not FileAccess.file_exists(path): continue
			var art := Image.new()
			if art.load(path) == OK:
				textures[path] = ImageTexture.create_from_image(art)
				if path == str(card.get("badge_path", "")):
					var light := 0.0
					var coverage := 0.0
					for x in range(8):
						for y in range(8):
							var pixel := art.get_pixel(mini(art.get_width() - 1, int((x + 0.5) * art.get_width() / 8.0)), mini(art.get_height() - 1, int((y + 0.5) * art.get_height() / 8.0)))
							light += (pixel.r + pixel.g + pixel.b) / 3.0 * pixel.a
							coverage += pixel.a
					# Preserve genuine white marks while giving them readable contrast.
					badge_backgrounds[path] = Color("466151") if coverage > 0 and light / coverage > 0.78 else Color.TRANSPARENT
	duration = maxf(seconds, 0.001)
	elapsed = 0.0
	offset = 0.0
	running = true
	completed = false
	set_process(true)
	queue_redraw()
	return true

func is_running() -> bool:
	return running

func _process(delta: float) -> void:
	advance(delta)

func advance(delta: float) -> void:
	if not running: return
	elapsed = minf(duration, elapsed + maxf(0.0, delta))
	# Ease-out quart: visible movement throughout four seconds, slowing to rest.
	var progress := elapsed / duration
	offset = LANDING_INDEX * STRIDE * (1.0 - pow(1.0 - progress, 4.0))
	queue_redraw()
	if elapsed >= duration: _complete()

func skip() -> void:
	if running: _complete()

func _complete() -> void:
	if completed or not running: return
	elapsed = duration
	offset = LANDING_INDEX * STRIDE
	running = false
	completed = true
	set_process(false)
	queue_redraw()
	revealed.emit(result.duplicate(true))

func result_center_x() -> float:
	return size.x / 2.0 + LANDING_INDEX * STRIDE - offset

func _card_color(card: Dictionary) -> Color:
	var color: Variant = card.get("color", "668bb7")
	return color if color is Color else Color.from_string(str(color), Color("668bb7"))

func _text(value: String, baseline: Vector2, width: float, font_size: int, color: Color, center: bool = true) -> void:
	var font := UI.Base.font()
	var text := value
	while text.length() > 1 and font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x > width:
		text = text.left(text.length() - 2) + "…"
	var text_width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size).x
	draw_string(font, baseline + Vector2((width - text_width) / 2.0 if center else 0.0, 0), text, HORIZONTAL_ALIGNMENT_LEFT, width, font_size, color)

func _name_with_badge(label: String, path: String, rect: Rect2) -> void:
	var font := UI.Base.font()
	var text := label
	var available := rect.size.x - 18 - 30
	while text.length() > 1 and font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 15).x > available:
		text = text.left(text.length() - 2) + "…"
	var text_width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 15).x
	var left := rect.position.x + (rect.size.x - text_width - 30) / 2.0
	draw_string(font, Vector2(left, rect.position.y + 133), text, HORIZONTAL_ALIGNMENT_LEFT, available, 15, UI.INK)
	var badge: Texture2D = textures[path]
	var badge_size := badge.get_size()
	var fit := badge_size * minf(24.0 / badge_size.x, 24.0 / badge_size.y)
	var badge_position := Vector2(left + text_width + 6, rect.position.y + 114)
	var background: Color = badge_backgrounds.get(path, Color.TRANSPARENT)
	if background.a > 0: draw_style_box(UI.style(background, 0, 4), Rect2(badge_position, Vector2(24, 24)))
	draw_texture_rect(badge, Rect2(badge_position + (Vector2(24, 24) - fit) / 2.0, fit), false)

func _draw() -> void:
	draw_style_box(UI.style(Color("dce5db"), 0, 10, Color("a0b09e")), Rect2(Vector2.ZERO, size))
	for index in range(cards.size()):
		var left := size.x / 2.0 + index * STRIDE - offset - CARD_SIZE.x / 2.0
		if left + CARD_SIZE.x < 0 or left > size.x: continue
		var card: Dictionary = cards[index]
		var rect := Rect2(Vector2(left, 20), CARD_SIZE)
		var color := _card_color(card)
		draw_style_box(UI.style(UI.PAPER, 0, 8, color), rect)
		draw_rect(Rect2(rect.position + Vector2(0, CARD_SIZE.y - 5), Vector2(CARD_SIZE.x, 5)), color)
		var art_rect := Rect2(rect.position + Vector2(9, 8), Vector2(CARD_SIZE.x - 18, 91))
		var path := str(card.get("art_path", ""))
		if textures.get(path) != null:
			var texture: Texture2D = textures[path]
			var art_size := texture.get_size()
			var scale_factor := minf(art_rect.size.x / art_size.x, art_rect.size.y / art_size.y)
			var fit := art_size * scale_factor
			draw_texture_rect(texture, Rect2(art_rect.position + (art_rect.size - fit) / 2.0, fit), false)
		else:
			draw_style_box(UI.style(color.lightened(0.8), 0, 6), art_rect)
			_text(str(card.get("value", card.get("weapon", ""))), art_rect.position + Vector2(4, 58), art_rect.size.x - 8, 25, color.darkened(0.25))
		var label := str(card.get("label", card.get("name", "")))
		if " | " in label:
			_text(label.get_slice(" | ", 0), rect.position + Vector2(9, 121), CARD_SIZE.x - 18, 12, UI.MUTED)
			_text(label.get_slice(" | ", 1), rect.position + Vector2(9, 142), CARD_SIZE.x - 18, 14, UI.INK)
		else:
			var badge_path := str(card.get("badge_path", ""))
			if textures.get(badge_path) != null:
				_name_with_badge(label, badge_path, rect)
			else:
				_text(label, rect.position + Vector2(9, 133), CARD_SIZE.x - 18, 15, UI.INK)
		_text(str(card.get("rarity", "")), rect.position + Vector2(9, 161), CARD_SIZE.x - 18, 12, color.darkened(0.18))
	var center := size.x / 2.0
	draw_line(Vector2(center, 15), Vector2(center, size.y - 14), Color("a78236", 0.5), 2.0)
	draw_colored_polygon(PackedVector2Array([Vector2(center - 9, 3), Vector2(center + 9, 3), Vector2(center, 20)]), Color("a78236"))
	draw_colored_polygon(PackedVector2Array([Vector2(center - 7, size.y - 3), Vector2(center + 7, size.y - 3), Vector2(center, size.y - 16)]), Color("a78236"))
