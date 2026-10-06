extends Node
## Local settings fixtures only. No CS2 process or filesystem installation.
const Settings = preload("res://scripts/device_settings.gd")
var checks := 0
var failures: Array[String] = []
var sent: Array = []
var queries: Array[String] = []

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("DEVICE_INSTALL_CHECK ", "PASS " if value else "FAIL ", label)

func _button(parent: Node, text: String, action: Callable, _primary: bool = true) -> Button:
	var button := Button.new()
	button.text = text
	button.pressed.connect(action)
	parent.add_child(button)
	return button

func fixture(bundle: bool = false) -> RefCounted:
	CareerBridge.busy = false
	CareerBridge.active_post = false
	CareerBridge.context = {"calendar":{"revision":7}, "settings":{"steam_exe":"D:/steam/steam.exe", "csgo_path":"D:/steam/game/csgo", "mod_source_path":"D:/CS2BotImprover", "difficulty":"Medium", "skins_source_path":"D:/OptionalSkins", "skins_inventory_mode":"external", "real_skins":false, "steam_id":"", "setup":{"available":bundle, "external_available":true}, "config":{"ready":false, "path_errors":[], "component_errors":["比赛回传组件尚未安装。"]}}}
	var settings := Settings.new()
	settings.command_sender = func(path: String, body: Dictionary):
		sent.append({"path":path, "body":body.duplicate(true)})
		return true
	settings.query_sender = func(path: String):
		queries.append(path)
		return true
	return settings

func form(settings: RefCounted, compact: bool = false) -> VBoxContainer:
	var parent := VBoxContainer.new()
	add_child(parent)
	settings.render(self, parent, compact)
	return parent

func saved_result() -> Dictionary:
	return {"ok":true, "settings":CareerBridge.context.settings.duplicate(true)}

func _ready() -> void:
	call_deferred("run")

func run() -> void:
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "fixtures never start the service")
	var detection := fixture()
	var detection_parent := form(detection)
	var source_field := detection_parent.find_child("DeviceSetting_bot_profile_source", true, false) as LineEdit
	check(source_field != null and source_field.text.is_empty(), "custom VPK source is visible and not enabled by default")
	detection.set_value("bot_profile_mode", "custom")
	source_field.text_changed.emit("D:/MyProfiles/botprofile.vpk")
	check(detection.draft.get("bot_profile_mode") == "custom" and detection.draft.get("bot_profile_source") == "D:/MyProfiles/botprofile.vpk", "custom source and mode survive the settings draft")
	detection.set_value("bot_profile_mode", "career")
	detection.set_value("bot_profile_source", "")
	var detect_button := detection_parent.find_child("DeviceSettingsDetectPaths", true, false) as Button
	check(detect_button != null and not detect_button.disabled, "ordinary and bundled settings offer local Steam and CS2 detection")
	detection.set_value("mod_source_path", "D:/KeepMyImprover")
	detect_button.pressed.emit()
	check(detection.detecting and detection.pending and queries[-1] == "/api/3d/settings/detect" and sent.is_empty(), "path detection is a read request, not a settings write or install")
	detection.submit()
	check(sent.is_empty(), "a pending detection cannot accidentally save stale form paths")
	detection.finished("/api/3d/settings/detect", {"ok":true, "paths":{"steam_exe":"F:/Steam/steam.exe", "csgo_path":"Z:/SteamLibrary/game/csgo"}, "reason":"已检测到 Steam、CS2，路径已填入，保存后生效。"})
	check(detection.draft.steam_exe == "F:/Steam/steam.exe" and detection.draft.csgo_path == "Z:/SteamLibrary/game/csgo" and detection.dirty, "found machine paths populate the unsaved draft")
	check(detection.draft.mod_source_path == "D:/KeepMyImprover" and detection.draft.skins_source_path == "D:/OptionalSkins", "machine detection preserves the selected enhancement and skin paths")
	detection.detect_paths()
	detection.finished("/api/3d/settings/detect", {"ok":true, "paths":{"steam_exe":"", "csgo_path":""}, "reason":"未找到 Steam 或 CS2，请手动选择安装路径。"})
	check(detection.draft.steam_exe == "F:/Steam/steam.exe" and not detection.pending and not detection.detecting, "a failed search preserves existing form values and unlocks the form")
	detection_parent.free()
	queries.clear()
	var updates := fixture()
	var updates_parent := form(updates)
	var update_button := updates_parent.find_child("DeviceSettingsCheckUpdates", true, false) as Button
	check(update_button != null and queries.is_empty(), "showing settings never checks updates automatically")
	update_button.pressed.emit()
	check(queries.size() == 1 and queries[-1] == "/api/3d/settings/updates" and updates.checking_updates and sent.is_empty(), "updates require an explicit read request and never invoke installation")
	updates.finished("/api/3d/settings/updates", {"ok":true, "checked":false, "reason":"暂时无法连接 GitHub，不影响本地安装。", "url":"https://github.com/ed0ard/CS2-Bot-Improver/releases"})
	check(not updates.pending and not updates.checking_updates and updates.message.contains("不影响本地安装"), "failed network checks unlock settings and keep local installation available")
	updates_parent.free()
	updates_parent = form(updates)
	check(updates_parent.find_child("DeviceSettingsUpdatePage", true, false) != null, "a separately clicked button opens the official releases page")
	updates_parent.free()
	queries.clear()
	var settings := fixture()
	var parent := form(settings)
	var external := parent.find_child("DeviceSettingsInstallExternal", true, false) as Button
	check(external != null and not external.disabled, "ordinary public package offers external installation")
	check(parent.find_child("DeviceSettingsInstallBundle", true, false) == null, "ordinary package does not pretend to contain a bundle")
	check(parent.find_child("DeviceSettingsStatus_component_errors", true, false) != null, "component errors have their own heading")
	check(parent.find_child("DeviceSettingsStatus_path_errors", true, false) == null, "valid paths are not described as path errors")
	check(settings.draft.skins_source_path == "D:/OptionalSkins" and settings.draft.skins_inventory_mode == "external", "flat preferences are retained beside diagnostic config")
	settings.set_value("mod_source_path", "D:/NewlyEnteredImprover")
	check(not external.disabled, "an unsaved external path can be installed without a separate save click")
	external.pressed.emit()
	check(sent.size() == 1 and sent[-1].path == "/api/3d/settings", "install first saves the form")
	check(sent[-1].body.settings.mod_source_path == "D:/NewlyEnteredImprover", "save carries the latest typed path")
	check(settings.pending and external.disabled and not (parent.find_child("DeviceSetting_mod_source_path", true, false) as LineEdit).editable, "install chain locks fields and buttons")
	settings.install_external()
	settings.install_bundle()
	settings.submit()
	check(sent.size() == 1, "repeated clicks cannot enqueue a second install")
	CareerBridge.context.calendar.revision = 8
	CareerBridge.context.settings.mod_source_path = "D:/NewlyEnteredImprover"
	settings.finished("/api/3d/settings", saved_result())
	check(sent.size() == 2 and sent[-1].path == "/api/3d/setup/install", "successful save starts installation")
	check(sent[-1].body.source == "external" and sent[-1].body.confirm == true and sent[-1].body.revision == 8, "installation uses external source and the post-save revision")
	settings.finished("/api/3d/settings", saved_result())
	check(sent.size() == 2 and settings.pending and settings.install_stage == "installing", "duplicate settings response does not clear the in-flight install")
	settings.finished("/api/3d/setup/install", {"ok":true, "reason":"人机增强和比赛组件已安装。"})
	settings.finished("/api/3d/setup/install", {"ok":true, "reason":"重复回调"})
	await get_tree().process_frame
	check(queries.size() == 1 and queries[-1] == "/api/3d/settings", "successful installation refreshes status exactly once")
	CareerBridge.context.settings.config = {"ready":true, "path_errors":[], "component_errors":[]}
	settings.finished("/api/3d/settings", saved_result())
	check(not settings.pending and settings.install_stage.is_empty() and settings.message == "人机增强和比赛组件已安装。", "status refresh unlocks the form and retains the installation result")
	parent.free()
	parent = form(settings, true)
	check(parent.find_child("DeviceSettingsReady", true, false) != null, "phone settings display the refreshed ready state")
	parent.free()

	sent.clear()
	settings = fixture()
	parent = form(settings)
	settings.install_external()
	settings.finished("/api/3d/settings", {"ok":false, "msg":"请完全退出 CS2 后再修改开赛设置。"})
	check(sent.size() == 1 and settings.install_stage.is_empty() and not settings.pending, "a rejected save cannot start filesystem installation")
	check(settings.message.contains("退出 CS2"), "the save failure is shown verbatim")
	settings.install_external()
	settings.finished("/api/3d/settings", saved_result())
	settings.finished("/api/3d/setup/install", {"ok":false, "msg":"所选目录没有 addons/metamod。"})
	check(settings.install_stage.is_empty() and not settings.pending and settings.message.contains("addons/metamod"), "installation failure unlocks the form and explains the missing source content")
	parent.free()

	sent.clear()
	settings = fixture(true)
	parent = form(settings)
	check(parent.find_child("DeviceSettingsInstallBundle", true, false) != null and parent.find_child("DeviceSettingsInstallExternal", true, false) != null, "integration package keeps both installation choices")
	settings.set_value("difficulty", "High")
	settings.install_bundle()
	check(sent[-1].path == "/api/3d/settings" and sent[-1].body.settings.difficulty == "High", "bundle installation also saves unsaved preferences")
	settings.finished("/api/3d/settings", saved_result())
	check(sent[-1].body.source == "bundle", "bundle button keeps its explicit bundled source")
	parent.free()

	sent.clear()
	settings = fixture()
	settings.draft = settings.config()
	settings.set_value("mod_source_path", "")
	parent = form(settings)
	external = parent.find_child("DeviceSettingsInstallExternal", true, false) as Button
	check(external != null and external.disabled, "empty source keeps the button visible but asks for a directory first")
	settings.install_external()
	check(sent.is_empty() and settings.message.contains("发行包目录"), "empty external source performs no save or install")
	settings.set_value("mod_source_path", "D:/CS2BotImprover")
	CareerBridge.busy = true
	settings.install_external()
	check(sent.is_empty(), "busy backend blocks starting the install chain")
	CareerBridge.busy = false
	parent.free()

	sent.clear()
	settings = fixture()
	CareerBridge.busy = true
	CareerBridge.active_post = false
	parent = form(settings)
	var save_button := parent.find_child("DeviceSettingsSave", true, false) as Button
	external = parent.find_child("DeviceSettingsInstallExternal", true, false) as Button
	check(not save_button.disabled and external.disabled, "background GET keeps save available but blocks installation")
	settings.submit()
	check(sent.size() == 1 and settings.pending, "normal settings save can queue behind a read request")
	CareerBridge.busy = false
	settings.finished("/api/3d/settings", saved_result())
	check(not save_button.disabled, "normal settings completion restores the save action")
	CareerBridge.busy = true
	CareerBridge.active_post = true
	settings._request_busy_changed(true)
	check(save_button.disabled and external.disabled and not save_button.get_meta("career_gate_disabled"), "write sync uses transient lock without changing the domain gate")
	CareerBridge.busy = false
	settings._request_busy_changed(false)
	check(not save_button.disabled and not external.disabled, "write completion restores both valid actions")
	parent.free()

	sent.clear()
	settings = fixture()
	settings.fetch()
	check(settings.pending_read and settings.pending, "read request tracks its own pending phase")
	CareerBridge.busy = true
	CareerBridge.active_post = false
	parent = form(settings)
	save_button = parent.find_child("DeviceSettingsSave", true, false) as Button
	check(not save_button.disabled and not save_button.get_meta("career_gate_disabled"), "the form's own GET is not a permanent save gate")
	settings.set_value("mod_source_path", "D:/EditedDuringRead")
	settings.submit()
	check(sent.size() == 1 and settings.saving, "form can queue a settings write behind its own GET")
	settings.finished("/api/3d/settings", saved_result())
	check(settings.pending and settings.saving and not settings.pending_read and settings.draft.mod_source_path == "D:/EditedDuringRead", "GET completion cannot masquerade as queued save completion")
	CareerBridge.busy = false
	CareerBridge.context.settings.mod_source_path = "D:/EditedDuringRead"
	settings.finished("/api/3d/settings", saved_result())
	check(not settings.pending and not settings.saving and not save_button.disabled and settings.draft.mod_source_path == "D:/EditedDuringRead", "the later POST completion acknowledges and unlocks the queued save")
	parent.free()

	sent.clear()
	settings = fixture()
	settings.draft = settings.config()
	Computer.device_settings = settings
	Computer.screen.visible = false
	CareerBridge.connected = true
	Phone.present("settings")
	settings.install_external()
	CareerBridge.context.calendar.revision = 9
	CareerBridge.command_finished.emit("/api/3d/settings", saved_result())
	check(sent.size() == 2 and sent[-1].body.revision == 9 and settings.pending, "computer and phone signals start only one shared install")
	await get_tree().process_frame
	check((Phone.content.find_child("DeviceSettingsInstallExternal", true, false) as Button).disabled, "visible phone remains locked after its early signal callback")
	CareerBridge.command_finished.emit("/api/3d/setup/install", {"ok":false, "msg":"请关闭游戏后安装。"})
	await get_tree().process_frame
	check(settings.message == "请关闭游戏后安装。" and not settings.pending, "shared failure feedback is handled once for both devices")
	check((Phone.content.find_child("DeviceSettingsOperationStatus", true, false) as Label).text == "请关闭游戏后安装。", "visible phone shows the result after the computer consumes it")
	Phone.close_phone(false)

	settings = fixture()
	CareerBridge.context.settings.config = {"ready":false, "path_errors":["Steam 程序没有找到。"], "component_errors":[]}
	parent = form(settings)
	check(parent.find_child("DeviceSettingsStatus_path_errors", true, false) != null and parent.find_child("DeviceSettingsStatus_component_errors", true, false) == null, "actual path errors are separated from installation errors")
	parent.free()
	CareerBridge.context.settings.config = {"ready":true, "compatibility":{"current":true, "revision":"fixture-cohort"}}
	parent = form(settings)
	var version_label := parent.find_child("DeviceSettingsCompatibility", true, false) as Label
	check(version_label != null and version_label.text.contains("fixture-cohort"), "settings show the selected compatible runtime revision")
	parent.free()
	print("Device settings installation: %d checks; %d failures" % [checks, failures.size()])
	for failure in failures: push_error(failure)
	get_tree().quit(0 if failures.is_empty() else 1)
