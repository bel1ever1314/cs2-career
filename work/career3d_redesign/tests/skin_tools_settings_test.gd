extends Node
const Settings = preload("res://scripts/device_settings.gd")
var checks := 0
var failures: Array[String] = []
var sent: Array = []

func check(value: bool, message: String) -> void:
	checks += 1
	if not value: failures.append(message)

func _button(parent: Node, text: String, action: Callable, _primary: bool = true) -> Button:
	var button := Button.new()
	button.text = text
	button.pressed.connect(action)
	parent.add_child(button)
	return button

func _ready() -> void:
	CareerBridge.context = {"calendar":{"revision":7}, "settings":{"difficulty":"Medium", "skins_inventory_mode":"career"}}
	var settings = Settings.new()
	settings.command_sender = func(path: String, body: Dictionary):
		sent.append({"path":path, "body":body.duplicate(true)})
		return true
	var parent := VBoxContainer.new()
	add_child(parent)
	settings.render(self, parent)
	var toggle = parent.find_child("DeviceSkinToolsEnabled", true, false)
	check(toggle is CheckBox, "neutral interface toggle exists")
	check(not toggle.button_pressed, "default disabled")
	check(not settings.dirty, "render does not enable interface")
	toggle.button_pressed = true
	check(settings.dirty and settings.draft.skin_tools_enabled == true, "explicit opt-in stored in draft")
	settings.submit()
	check(sent.size() == 1 and sent[0].path == "/api/3d/settings", "existing settings route")
	check(sent[0].body.settings.skin_tools_enabled == true, "boolean true submitted")
	check(sent[0].body.revision == 7, "revision retained")
	check(not sent[0].body.settings.has("skin_inspect_enabled"), "does not enable old hosted viewer")
	check(not sent[0].body.settings.has("viewer_url"), "no preselected third-party renderer")
	settings.finished("/api/3d/settings", {"ok":true, "settings":{"difficulty":"Medium", "skin_tools_enabled":true}})
	settings.set_value("skin_tools_enabled", false)
	settings.submit()
	check(sent[1].body.settings.skin_tools_enabled == false, "explicit disable remains boolean false")
	parent.free()
	CareerBridge.context.settings.skin_tools_enabled = true
	settings = Settings.new()
	parent = VBoxContainer.new()
	add_child(parent)
	settings.render(self, parent, true)
	toggle = parent.find_child("DeviceSkinToolsEnabled", true, false)
	check(toggle.button_pressed, "phone compact form reads configured opt-in")
	check(not settings.dirty, "existing opt-in does not dirty form")
	parent.free()
	print("Skin tools settings: %d checks; %d failures" % [checks, failures.size()])
	for failure in failures: push_error(failure)
	get_tree().quit(0 if failures.is_empty() else 1)
