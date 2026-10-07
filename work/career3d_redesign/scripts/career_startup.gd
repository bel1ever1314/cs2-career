extends CanvasLayer
## Presentation only: no career creation, scheduling, retries or save writes.
const UI = preload("res://scripts/computer_ui.gd")
const Brand = preload("res://scripts/career_brand.gd")
var screen: ColorRect
var status: Label
var actions: HBoxContainer
var bar: ProgressBar
var finished := false

func _ready() -> void:
	layer = 110
	name = "CareerStartup"
	screen = ColorRect.new()
	screen.color = Brand.PAPER
	screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(screen)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	screen.add_child(center)
	var stack := VBoxContainer.new()
	stack.add_theme_constant_override("separation", 15)
	center.add_child(stack)
	stack.add_child(Brand.new())
	var subtitle := UI.label(stack, "CS2 生涯模拟器", 20, UI.GREEN)
	subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	status = UI.label(stack, "正在载入生涯……", 14, UI.MUTED)
	status.name = "StartupStatus"
	status.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status.custom_minimum_size = Vector2(600, 42)
	bar = ProgressBar.new()
	bar.show_percentage = false
	bar.indeterminate = true
	bar.custom_minimum_size.y = 3
	bar.add_theme_stylebox_override("background", UI.style(UI.MINT, 0, 2))
	bar.add_theme_stylebox_override("fill", UI.style(UI.GREEN, 0, 2))
	stack.add_child(bar)
	actions = HBoxContainer.new()
	actions.alignment = BoxContainer.ALIGNMENT_CENTER
	stack.add_child(actions)
	UI.button(actions, "查看界面", dismiss)
	UI.button(actions, "退出游戏", CareerBridge.quit)
	_refresh()

func _process(_delta: float) -> void:
	_refresh()

func _refresh() -> void:
	if finished: return
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	if CareerBridge.connected and not CareerBridge.context.is_empty() and get_tree().current_scene != null:
		dismiss()
		return
	var failed := not CareerBridge.connecting and not CareerBridge.busy and not CareerBridge.reconnecting
	status.text = CareerBridge.message if failed or CareerBridge.reconnecting else (
		"正在准备生涯数据……" if not CareerBridge.connecting else "正在启动生涯后台……")
	actions.visible = failed
	bar.visible = not failed

func dismiss() -> void:
	if finished: return
	finished = true
	set_process(false)
	screen.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var fade := create_tween()
	fade.tween_property(screen, "modulate:a", 0.0, .2)
	fade.tween_callback(queue_free)
