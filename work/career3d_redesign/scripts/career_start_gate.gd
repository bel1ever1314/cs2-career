extends Node
## A one-time welcome screen; loading resources or running tests never creates a save.
const UI = preload("res://scripts/phone_ui.gd")
var welcomed := false

func requires_creation() -> bool:
	return bool(CareerBridge.context.get("start", {}).get("creation_required", false))

func remind() -> void:
	CareerBridge.message = "请先创建角色，或读取已有生涯存档。"
	CareerBridge.status_changed.emit()

func _ready() -> void:
	ThemeDB.fallback_font = UI.font()
	if Engine.is_editor_hint(): return
	for flag in OS.get_cmdline_user_args():
		if "test" in flag or "capture" in flag or flag == "--no-service": return
	add_child(preload("res://scripts/career_startup.gd").new())
	CareerBridge.changed.connect(_welcome)
	if CareerBridge.connected: call_deferred("_welcome")

func _welcome() -> void:
	if welcomed or CareerBridge.context.is_empty(): return
	welcomed = true
	Computer.call_deferred("open_app", "start", "bedroom")
