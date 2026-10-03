extends CanvasLayer
## Presentation only: dates and interruptions still come from the career service.
const UI = preload("res://scripts/computer_ui.gd")
var active := false
var overlay: Control
var shade: ColorRect
var caption: Label
var subtitle: Label
var text_column: VBoxContainer
var fade: Tween
var start_command: Callable
var fade_seconds := .85
var morning_seconds := .75
var outcome := ""
var previous_clock_held := false

func _ready() -> void:
	layer = 110
	process_mode = Node.PROCESS_MODE_ALWAYS
	overlay = Control.new()
	overlay.name = "SleepTransition"
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(overlay)
	shade = ColorRect.new()
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.color = Color("0b1220")
	overlay.add_child(shade)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	overlay.add_child(center)
	text_column = VBoxContainer.new()
	text_column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	text_column.add_theme_constant_override("separation", 16)
	center.add_child(text_column)
	caption = UI.label(text_column, "晚安", 36, Color("f5ecd7"))
	caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	caption.autowrap_mode = TextServer.AUTOWRAP_OFF
	subtitle = UI.label(text_column, "", 18, Color("b9c3d1"))
	subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	overlay.visible = false
	get_viewport().size_changed.connect(_layout)
	_layout()

func _layout() -> void:
	text_column.custom_minimum_size.x = minf(680, get_viewport().get_visible_rect().size.x * .8)
	caption.add_theme_font_size_override("font_size", 28 if get_viewport().get_visible_rect().size.x < 390 else 36)

func begin(target: String) -> bool:
	if active or not CareerBridge.connected or CareerBridge.busy or CareerBridge.closing or Travel.busy or CareerBridge._has_pending_match(): return false
	if target.is_empty() or target < str(CareerBridge.context.get("date", "")): return false
	active = true
	outcome = ""
	previous_clock_held = CareerBridge.clock_held
	CareerBridge.sleeping = true
	CareerBridge.clock_held = true
	Phone.close_phone()
	Computer.close_computer()
	Travel.close_menu()
	UI.device_open(self, "sleep")
	caption.text = "晚安"
	subtitle.text = "醒来：" + target + "  08:00"
	shade.color = Color("0b1220")
	overlay.modulate.a = 0
	overlay.visible = true
	_night(target)
	return true

func _night(target: String) -> void:
	fade = create_tween()
	fade.tween_property(overlay, "modulate:a", 1.0, fade_seconds).set_trans(Tween.TRANS_SINE)
	await fade.finished
	if not active: return
	var accepted := bool(start_command.call(target)) if start_command.is_valid() else CareerBridge._begin_calendar(target, true)
	if not accepted:
		CareerBridge.clock_held = previous_clock_held
		complete({"ok":false, "msg":"时间未推进，请稍后再试。"})

func complete(result: Dictionary) -> void:
	if not active or not outcome.is_empty(): return
	outcome = "reached" if result.get("ok", false) and (result.get("status", "") == "reached" or result.get("wake_at_match", false)) else "paused" if result.get("ok", false) else "failed"
	# The ordinary wake signal may already be returning from the club to bed.
	# Keep the night curtain opaque until that scene change is finished.
	while Travel.busy: await get_tree().process_frame
	caption.text = "早上好" if outcome == "reached" else "时间暂停" if outcome == "paused" else "暂时没有睡下"
	subtitle.text = CareerBridge.clock_text() if outcome == "reached" else str(result.get("reason", result.get("msg", "有比赛或事件等待你处理。")))
	if result.get("wake_at_match", false):
		var game: Dictionary = CareerBridge.context.get("nextmatch", {})
		var plan: Dictionary = game.get("attendance", {})
		subtitle.text += "\n今天对阵 %s · %s" % [game.get("opponent", ""), plan.get("display_name", "比赛场馆")]
	if subtitle.text.is_empty(): subtitle.text = "有比赛或事件等待你处理。"
	fade = create_tween()
	fade.tween_property(shade, "color", Color("514a3e"), morning_seconds).set_trans(Tween.TRANS_SINE)
	await fade.finished
	fade = create_tween()
	fade.tween_property(overlay, "modulate:a", 0.0, fade_seconds).set_trans(Tween.TRANS_SINE)
	await fade.finished
	overlay.visible = false
	active = false
	CareerBridge.sleeping = false
	UI.device_closed(self)
	if outcome == "paused": Phone.present("calendar")

func _input(event: InputEvent) -> void:
	if active and (event is InputEventKey or event is InputEventMouseButton or event is InputEventMouseMotion):
		get_viewport().set_input_as_handled()
