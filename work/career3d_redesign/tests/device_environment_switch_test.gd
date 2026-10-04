extends Node
## Environment switching is captured; no backend, plugin file or save is touched.
const Settings = preload("res://scripts/device_settings.gd")
var checks := 0
var failures: Array[String] = []
var writes: Array[Dictionary] = []
var reads: Array[String] = []

func _ready() -> void:
	call_deferred("run")

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("ENVIRONMENT_UI_CHECK ", "PASS " if value else "FAIL ", label)

func _button(parent: Node, caption: String, callback: Callable, _write: bool = true) -> Button:
	var button := Button.new()
	button.text = caption; button.pressed.connect(callback); parent.add_child(button)
	return button

func state(mode: String = "normal", available: bool = true, watched: bool = false, reason: String = "") -> Dictionary:
	return {"mode":mode, "valid":true, "switch_available":available, "reason":reason, "auto_restore":true,
		"watch_active":watched, "generation":"fixture-generation", "cs2_running":not available, "process_known":true}

func preferences() -> Dictionary:
	return {"steam_exe":"D:/Steam/steam.exe", "csgo_path":"D:/Steam/game/csgo", "mod_source_path":"D:/MyImprover",
		"skins_source_path":"D:/OptionalSkins", "difficulty":"High", "bot_aim":"mixed", "real_skins":false,
		"steam_id":"", "skin_tools_enabled":false, "config":{"ready":true}, "environment":state()}

func fixture() -> RefCounted:
	var settings := Settings.new()
	settings.command_sender = func(path: String, body: Dictionary):
		writes.append({"path":path, "body":body.duplicate(true)}); return true
	settings.query_sender = func(path: String):
		reads.append(path); return true
	return settings

func form(settings: RefCounted, compact: bool = false) -> VBoxContainer:
	var parent := VBoxContainer.new(); add_child(parent); settings.render(self, parent, compact)
	return parent

func toggle(parent: Node, mode: String) -> Button:
	return parent.find_child("DeviceEnvironment_" + mode, true, false) as Button

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(2); return
	CareerBridge.set_process(false); Computer.set_process(false); Phone.set_process(false)
	CareerBridge.busy = false; CareerBridge.active_post = false; CareerBridge.connected = true
	Locale.set_language("zh-CN", false)
	CareerBridge.context = {"calendar":{"revision":23}, "settings":preferences()}
	var settings := fixture()
	var desktop := form(settings)
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "fixture has no service or real game")
	check(not toggle(desktop, "enhanced").disabled and toggle(desktop, "normal").disabled, "normal mode offers enabling plugins, not redundant restoration")
	check((desktop.find_child("DeviceEnvironmentStatus", true, false) as Label).text.contains("普通 CS2"), "saved environment mode is visible")
	check(writes.is_empty() and reads.is_empty() and not settings.dirty, "render neither switches nor checks the network")
	settings.set_value("csgo_path", "F:/NewLibrary/game/csgo")
	check(toggle(desktop, "enhanced").disabled and toggle(desktop, "enhanced").tooltip_text.contains("先保存路径"), "unsaved paths disable switching with a save-first explanation")
	check((desktop.find_child("DeviceEnvironmentStatus", true, false) as Label).text.contains("先保存路径"), "unsaved path guidance is visible without clicking a disabled button")
	settings.switch_environment("enhanced")
	check(writes.is_empty() and settings.dirty and settings.message.contains("先保存路径"), "switching cannot secretly submit a path draft")
	settings.set_value("csgo_path", "D:/Steam/game/csgo")
	settings.set_value("bot_aim", "head")
	var phone := form(settings, true)
	CareerBridge.context.settings.environment = state("normal", true, true)
	settings._sync_form_state()
	check(not toggle(desktop, "enhanced").disabled, "registered restoration watcher alone is not a running-game gate")
	settings.switch_environment("enhanced")
	check(writes.size() == 1 and writes[-1].path == "/api/3d/settings/environment", "environment uses its own endpoint")
	check(writes[-1].body == {"revision":23, "mode":"enhanced"}, "switch payload contains only saved-config mode and revision")
	check(not writes[-1].body.has("settings") and not writes[-1].body.has("real_skins") and settings.draft.bot_aim == "head", "bot and skin preferences are not saved or enabled by switching")
	check(settings.switching_environment and settings.message == "正在开启本地插件……" and toggle(desktop, "enhanced").disabled and toggle(phone, "normal").disabled, "switch has immediate feedback and locks both devices")
	settings.set_value("real_skins", true); settings.switch_environment("normal"); settings.submit(); settings.install_external()
	check(writes.size() == 1 and not settings.draft.real_skins, "one switch excludes save, installation and late input")
	var saved := preferences(); saved.environment = state("enhanced", true, true)
	settings.finished("/api/3d/settings/environment", {"ok":true, "environment":saved.environment, "settings":saved, "reason":"fixture enabled"})
	check(not settings.pending and not settings.switching_environment and settings.message == "fixture enabled", "successful switch is acknowledged and unlocked")
	check(settings.dirty and settings.draft.bot_aim == "head" and not settings.draft.real_skins, "environment projection cannot erase unrelated unsaved choices")
	check(toggle(desktop, "enhanced").disabled and not toggle(desktop, "normal").disabled and not toggle(phone, "normal").disabled, "enhanced-but-not-running environment permits normal restoration on both devices")
	check((phone.find_child("DeviceEnvironmentStatus", true, false) as Label).text.contains("已开启"), "phone status updates even before repaint")
	settings.finished("/api/3d/settings/environment", {"ok":true, "environment":state(), "reason":"duplicate response"})
	check(CareerBridge.context.settings.environment.mode == "enhanced" and settings.message == "fixture enabled", "a duplicate completion cannot rewrite current state")
	settings.switch_environment("normal")
	check(writes.size() == 2 and writes[-1].body.mode == "normal" and settings.message == "正在恢复普通 CS2……", "restoration is an explicit local environment operation")
	settings.finished("/api/3d/settings/environment", {"ok":false, "environment":state("enhanced", false, true, "请完全退出 CS2。"), "reason":"fixture process guard"})
	check(settings.message == "fixture process guard" and not settings.pending and settings.dirty, "failed restoration preserves the draft and exposes the backend outcome")
	check(toggle(desktop, "normal").disabled and toggle(phone, "normal").disabled, "switch availability, not watcher registration, enforces the process guard")
	settings.switch_environment("normal")
	check(writes.size() == 2 and settings.message == "请完全退出 CS2。", "direct calls honor the same closed-process gate")
	settings.refresh_environment()
	check(reads == ["/api/3d/settings/environment"] and writes.size() == 2 and settings.pending, "refresh is a local read with no install, launch or preference write")
	settings.switch_environment("normal"); settings.submit()
	check(writes.size() == 2, "pending status refresh excludes switches and writes")
	settings.finished("/api/3d/settings/environment", {"ok":true, "environment":state("mixed", true, false), "reason":"fixture refreshed"})
	check(not settings.pending and not toggle(desktop, "enhanced").disabled and not toggle(desktop, "normal").disabled, "mixed mode permits explicit backend-supported repair in either direction")
	check((desktop.find_child("DeviceEnvironmentStatus", true, false) as Label).text.contains("需要调整"), "mixed loading state is explained")
	CareerBridge.busy = true; CareerBridge.active_post = false; settings._request_busy_changed(true)
	settings.switch_environment("normal"); settings.refresh_environment()
	check(writes.size() == 2 and reads.size() == 1 and toggle(desktop, "normal").disabled, "an unrelated read cannot race a local environment operation")
	CareerBridge.busy = false; settings._request_busy_changed(false)
	settings.switch_environment("invalid")
	check(writes.size() == 2, "invalid modes never leave the controller")
	desktop.free(); phone.free()
	CareerBridge.context = {"settings":preferences()}
	var before_start := fixture(); var opening := form(before_start)
	before_start.switch_environment("enhanced")
	check(writes[-1].body.revision == 0 and writes[-1].body.mode == "enhanced", "plugin controls also work before career creation using revision zero")
	before_start.finished("/api/3d/settings/environment", {"ok":true, "environment":state("enhanced", true, true), "settings":preferences(), "reason":"fixture enabled"})
	check(not before_start.dirty and not before_start.draft.real_skins and not before_start.draft.skin_tools_enabled, "a clean form stays clean without opting into skins or tools")
	opening.free()
	CareerBridge.context = {"settings":{"config":{"ready":false}}}
	var unknown := fixture(); var unknown_form := form(unknown)
	check(toggle(unknown_form, "normal").disabled and toggle(unknown_form, "enhanced").disabled, "legacy or unconfirmed environment cannot imply switch availability")
	unknown_form.free()
	CareerBridge.context = {"calendar":{"revision":25}, "settings":preferences()}
	var shared := fixture()
	Computer.device_settings = shared
	Computer.screen.visible = false
	Phone.present("settings")
	shared.switch_environment("enhanced")
	var enabled := preferences(); enabled.environment = state("enhanced", true, true)
	CareerBridge.command_finished.emit("/api/3d/settings/environment", {"ok":true, "settings":enabled, "environment":enabled.environment, "reason":"fixture phone switch"})
	await get_tree().process_frame
	await get_tree().process_frame
	check(shared.message == "fixture phone switch" and not shared.pending, "shared completion is consumed once despite both device signal listeners")
	check((Phone.content.find_child("DeviceSettingsOperationStatus", true, false) as Label).text == "fixture phone switch" and not toggle(Phone.content, "normal").disabled, "phone completion repaints the acknowledged plugin state")
	Phone.close_phone(false)
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service and not CareerBridge.busy, "all operations stayed in captured offline fixtures")
	print("ENVIRONMENT_UI_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
