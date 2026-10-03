extends CanvasLayer
## A short journey reminder in the world, using the saved attendance plan.
const UI = preload("res://scripts/phone_ui.gd")
var panel: PanelContainer
var heading: Label
var detail: Label
var attendance: Dictionary = {}
var world_scene: Node

func _ready() -> void:
	layer = 8
	var screen := Control.new()
	screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	screen.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(screen)
	panel = PanelContainer.new()
	panel.name = "MatchDayGuidance"
	panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER_TOP)
	panel.offset_left = -280; panel.offset_right = 280
	panel.offset_top = 22; panel.offset_bottom = 100
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_theme_stylebox_override("panel", UI.style(UI.CREAM, 12, 14, UI.LINE))
	screen.add_child(panel)
	var lines := VBoxContainer.new(); lines.add_theme_constant_override("separation", 4); panel.add_child(lines)
	heading = UI.label(lines, "", 17, UI.GREEN)
	detail = UI.label(lines, "", 13, UI.MUTED)
	for label in [heading, detail]:
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	refresh()

func refresh() -> void:
	if not is_instance_valid(panel): return
	attendance = Travel.match_guidance()
	heading.text = "%s · 对阵 %s" % [attendance.get("event_name", attendance.get("event", "")), attendance.get("opponent", "")]
	detail.text = journey_text(attendance)
	world_scene = null

static func journey_text(attendance: Dictionary) -> String:
	var today := bool(attendance.get("is_today", false)) and bool(attendance.get("due", false))
	if attendance.is_empty() or (not bool(attendance.get("planned", false)) and not today): return ""
	var venue := str(attendance.get("display_name", attendance.get("venue_name", "比赛场馆")))
	if bool(attendance.get("is_today", false)):
		if str(attendance.get("destination", "")) == "club": return "今日比赛 · 前往俱乐部训练室，按 E 使用电脑"
		return "今日比赛 · 走到门口，选择「%s」" % venue
	if str(attendance.get("phase", "")) == "overdue": return "比赛安排已过期 · 打开手机日历查看新赛程"
	return "%s 比赛 · %s · 在手机日历睡到比赛当天" % [attendance.get("date", ""), venue]

func _process(_delta: float) -> void:
	var scene := get_tree().current_scene
	var in_home := scene != null and scene.scene_file_path in [Travel.SCENES["bedroom"], Travel.SCENES["club"]]
	panel.visible = in_home and not detail.text.is_empty() and not CareerBridge.phone_open and not Travel.busy and not Travel.menu_open
	if not panel.visible or scene == world_scene: return
	world_scene = scene
	detail.text = journey_text(attendance)
	if bool(attendance.get("is_today", false)):
		if scene.scene_file_path == Travel.SCENES["club"] and str(attendance.get("destination", "")) == "club":
			detail.text = "今日比赛 · 去训练室的电脑旁，按 E 准备比赛"
