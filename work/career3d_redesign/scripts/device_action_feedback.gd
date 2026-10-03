extends Control
## A device-local result notice. It never grabs focus or claims a click.
const UI = preload("res://scripts/phone_ui.gd")
const COLORS := {
	"success": [Color("e5f1e4"), Color("31624c"), "✓"],
	"error": [Color("f7e4dd"), Color("994c37"), "!"],
	"progress": [Color("e8eef2"), Color("496476"), "…"]
}
var surface: PanelContainer
var text_label: Label
var current_message := ""
var current_kind := "success"
var current_operation := ""
var shown_count := 0
var remaining := 0.0
var top_inset := 72.0
var pending_requests: Dictionary = {}
var pending_operations: Dictionary = {}

func _ready() -> void:
	name = "DeviceActionFeedback"
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	z_index = 200
	process_mode = Node.PROCESS_MODE_ALWAYS
	surface = PanelContainer.new()
	surface.name = "ActionFeedbackSurface"
	surface.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(surface)
	text_label = Label.new()
	text_label.name = "ActionFeedbackText"
	text_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text_label.add_theme_font_override("font", UI.font())
	text_label.add_theme_font_size_override("font_size", 14)
	text_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	text_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	surface.add_child(text_label)
	resized.connect(_layout)
	_layout()
	visible = false

func _layout() -> void:
	if not is_instance_valid(surface): return
	var width := maxf(1.0, minf(560.0, size.x - 28.0))
	surface.position = Vector2((size.x - width) / 2.0, top_inset)
	surface.size = Vector2(width, maxf(48.0, surface.get_combined_minimum_size().y))

func show_message(message: String, kind: String = "success", duration: float = 4.0, operation: String = "") -> void:
	var normalized_kind := "progress" if kind == "pending" else kind if COLORS.has(kind) else "success"
	if not operation.is_empty():
		pending_operations.erase(operation)
		if normalized_kind == "progress" and not message.strip_edges().is_empty(): pending_operations[operation] = message.strip_edges()
	if message.strip_edges().is_empty():
		if not operation.is_empty() and current_operation == operation and current_kind == "progress" and normalized_kind != "progress":
			_restore_pending_notice()
		return
	current_message = message.strip_edges()
	current_kind = normalized_kind
	current_operation = operation
	var theme: Array = COLORS[current_kind]
	text_label.text = str(theme[2]) + "  " + current_message
	text_label.add_theme_color_override("font_color", theme[1])
	surface.add_theme_stylebox_override("panel", UI.style(theme[0], 12, 12, theme[1]))
	remaining = -1.0 if duration <= 0.0 else maxf(0.25, duration)
	modulate.a = 1.0
	visible = true
	shown_count += 1
	_layout()

func clear_notice(clear_pending: bool = false) -> void:
	visible = false
	remaining = 0.0
	current_message = ""
	current_operation = ""
	modulate.a = 1.0
	if clear_pending:
		pending_requests.clear()
		pending_operations.clear()

func _process(delta: float) -> void:
	if not visible or remaining < 0.0: return
	remaining -= delta
	if remaining <= 0.0:
		_restore_pending_notice()
	elif remaining < 0.3:
		modulate.a = remaining / 0.3

func _restore_pending_notice() -> void:
	if not pending_operations.is_empty():
		var latest: String = str(pending_operations.keys()[-1])
		show_message(str(pending_operations[latest]), "progress", 0.0, latest)
	elif not pending_requests.is_empty():
		show_message("正在处理……", "progress", 0.0)
	else:
		clear_notice()

func track_request(path: String, accepted: bool, failure: String = "") -> void:
	if accepted:
		pending_requests[path] = success_text(path)
		show_message("正在处理……", "progress", 0.0)
	else:
		show_message(failure if not failure.is_empty() else "操作还没有发出，请稍后再试。", "error", 5.0)

func finish_request(path: String, result: Dictionary) -> bool:
	if not pending_requests.has(path): return false
	var fallback := str(pending_requests[path])
	pending_requests.erase(path)
	if result.get("ok", false):
		var message := str(result.get("msg", "")).strip_edges()
		if message.is_empty(): message = str(result.get("reason", "")).strip_edges()
		show_message(fallback if message.is_empty() else message, "success", 4.5)
	else:
		var message := str(result.get("msg", "")).strip_edges()
		if message.is_empty(): message = str(result.get("reason", "")).strip_edges()
		if result.get("outcome_unknown", false):
			message = "连接中断，结果尚未确认。请刷新后查看。"
		show_message("操作没有完成，请重试。" if message.is_empty() else message, "error", 6.0)
	return true

static func success_text(path: String) -> String:
	var specific := {
		"/api/3d/attr": "属性点已分配。",
		"/api/3d/mail/accept": "邀请已接受。",
		"/api/3d/mail/decline": "已婉拒这次邀请。",
		"/api/3d/social/send": "消息已发送。",
		"/api/3d/story": "选择已记录。",
		"/api/3d/scrim/schedule": "训练赛已安排。",
		"/api/3d/scrim/simulate": "训练赛已结束，战报已保存。",
		"/api/3d/controls/roles": "首发位置已保存。",
		"/api/3d/controls/assistance": "自动安排已保存。",
		"/api/3d/controls/workshop/reload": "扩展已重新扫描。",
		"/api/3d/controls/training/finish": "训练已核验并结算。",
		"/api/3d/controls/training/cancel": "已取消本次训练核验。",
		"/api/3d/ladder/pick": "队友已选入阵容。",
		"/api/3d/ladder/ban": "地图已禁用。"
	}
	if specific.has(path): return str(specific[path])
	if path.begins_with("/api/3d/ops/"): return "经营操作已完成。"
	if path.begins_with("/api/3d/transfers/"): return "转会操作已完成。"
	if path.begins_with("/api/3d/skins/"): return "饰品操作已完成。"
	return "操作已完成。"
