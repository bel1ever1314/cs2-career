extends Control
## A known terrain map, not a reveal-all radar. Enemy markers require the
## same spotted_by observation as the main map.
signal camera_requested(point: Vector2)
const Style = preload("res://scripts/style.gd")
var state: Dictionary = {}
var team := "t"
var spectator := false
var map_view
var texture: Texture2D
var origin := Vector2.ZERO
var map_scale := 1.0

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	tooltip_text = "点击小地图查看位置；全场观战可看到双方。"

func setup(map_data: Dictionary) -> void:
	texture = load(str(map_data.get("radar", {}).get("image", "")))
	queue_redraw()

func _process(_dt: float) -> void:
	queue_redraw()

func _draw() -> void:
	map_scale = minf(size.x, size.y) / 1024.0
	origin = (size - Vector2.ONE * 1024 * map_scale) / 2
	draw_rect(Rect2(Vector2.ZERO, size), Color("10191e"))
	if texture == null: return
	draw_texture_rect(texture, Rect2(origin, Vector2.ONE * 1024 * map_scale), false, Color(.85, .88, .89))
	for p in state.get("players", []):
		if not p.get("alive", false): continue
		if not spectator and p.get("team", "") != team and team not in p.get("spotted_by", []): continue
		var at: Vector2 = p.get("pos", Vector2.ZERO)
		var tint := Style.GOLD if p.get("side", "t") == "t" else Style.BLUE
		draw_circle(origin + at * map_scale, 2.6, tint)
	if map_view != null:
		var extent: Vector2 = map_view.size / maxf(.01, map_view.scale_factor)
		var rect := Rect2(origin + (map_view.center - extent / 2) * map_scale, extent * map_scale)
		draw_rect(rect.intersection(Rect2(origin, Vector2.ONE * 1024 * map_scale)), Color(.9, .95, .88, .5), false, 1)

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		camera_requested.emit((get_local_mouse_position() - origin) / maxf(.001, map_scale))
		accept_event()
