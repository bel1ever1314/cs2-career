extends Node
## UI-only settings roundtrips. Every write is captured, never sent to a backend.
const Settings = preload("res://scripts/device_settings.gd")
var checks := 0
var failures: Array[String] = []
var sent: Array[Dictionary] = []

func _ready() -> void:
	call_deferred("run")

func check(value: bool, caption: String) -> void:
	checks += 1
	if not value: failures.append(caption)
	print("BOT_OPTIONS_CHECK ", "PASS " if value else "FAIL ", caption)

func _button(parent: Node, caption: String, callback: Callable, _write: bool = true) -> Button:
	var target := Button.new()
	target.text = caption; target.pressed.connect(callback); parent.add_child(target)
	return target

func send_fixture(path: String, body: Dictionary) -> bool:
	sent.append({"path":path, "body":body.duplicate(true)})
	return true

func render_form(settings: RefCounted, compact: bool = false) -> VBoxContainer:
	var parent := VBoxContainer.new()
	add_child(parent); settings.render(self, parent, compact)
	return parent

func option(parent: Node, key: String) -> OptionButton:
	return parent.find_child("DeviceSetting_" + key, true, false) as OptionButton

func selected(parent: Node, key: String) -> String:
	var control := option(parent, key)
	return str(control.get_item_metadata(control.selected)) if control != null and control.selected >= 0 else ""

func choose(parent: Node, key: String, value: String) -> void:
	var control := option(parent, key)
	if control == null: check(false, "missing control: " + key); return
	for index in range(control.item_count):
		if str(control.get_item_metadata(index)) == value:
			control.select(index); control.item_selected.emit(index); return
	check(false, "missing choice: " + key + "/" + value)

func preferences() -> Dictionary:
	return {"steam_exe":"D:/Steam/steam.exe", "csgo_path":"D:/Steam/game/csgo", "mod_source_path":"D:/MyImprover",
		"skins_source_path":"D:/MySkins", "skins_inventory_mode":"external", "difficulty":"High", "bot_aim":"body",
		"bot_nades":"max", "bot_identity":"bot", "bot_movement":"classic", "match_chat":"custom",
		"skin_tools_enabled":true, "skin_inspect_enabled":true, "real_skins":false, "steam_id":"",
		"config":{"ready":true, "path_errors":[], "component_errors":[]}}

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(2); return
	CareerBridge.set_process(false); Computer.set_process(false); Phone.set_process(false)
	CareerBridge.connected = true; CareerBridge.busy = false; CareerBridge.active_post = false; CareerBridge.clock_held = true
	Locale.set_language("zh-CN", false)
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "no backend or real CS2 process")
	CareerBridge.context = {"calendar":{"revision":19}, "settings":preferences()}
	var settings := Settings.new(); settings.command_sender = send_fixture
	var desktop := render_form(settings)
	for key in ["bot_aim", "bot_nades", "match_chat"]:
		check(option(desktop, key) != null and selected(desktop, key) == str(preferences()[key]), "existing preference displayed: " + key)
	check(option(desktop, "bot_aim").item_count == 3 and option(desktop, "bot_nades").item_count == 5 and option(desktop, "match_chat").item_count == 3, "all supported options are selectable")
	check(option(desktop, "bot_movement") == null and desktop.find_child("DeviceBotMovementPreset", true, false) != null, "classic movement is explained without exposing retired experiments")
	check(not settings.dirty and sent.is_empty() and not (desktop.find_child("DeviceSkinEnabled", true, false) as CheckBox).button_pressed, "render neither saves nor enables skins")
	settings.set_value("steam_exe", "F:/Steam/steam.exe")
	settings.submit()
	check(sent.size() == 1 and sent[-1].path == "/api/3d/settings" and sent[-1].body.revision == 19, "normal save uses the existing revision-bound endpoint")
	check(option(desktop, "bot_identity") == null and sent[-1].body.settings.bot_identity == "player", "bot identity is fixed to named competitors")
	for key in ["bot_aim", "bot_nades", "bot_movement", "match_chat"]:
		check(sent[-1].body.settings[key] == preferences()[key], "path-only edit preserves option: " + key)
	check(sent[-1].body.settings.skins_source_path == "D:/MySkins" and sent[-1].body.settings.skins_inventory_mode == "external" and sent[-1].body.settings.skin_tools_enabled == true, "all existing skin choices remain unchanged")
	check(not sent[-1].body.settings.has("skin_inspect_enabled") and not sent[-1].body.real_skins and sent[-1].body.steam_id == "", "unexposed preferences are left to backend merge and no skin opt-in is fabricated")
	check(settings.message == "正在保存 CS2 设置……" and option(desktop, "bot_aim").disabled, "saving has immediate feedback and locks option controls")
	var before := settings.draft.duplicate(true)
	settings.set_value("bot_aim", "head"); settings.submit()
	check(settings.draft == before and sent.size() == 1, "pending save cannot be mutated or duplicated")
	var saved := preferences(); saved.steam_exe = "F:/Steam/steam.exe"
	settings.finished("/api/3d/settings", {"ok":true, "settings":saved, "reason":"fixture saved"})
	check(not settings.pending and not settings.saving and not settings.dirty and not option(desktop, "bot_aim").disabled and settings.message == "fixture saved", "save completion unlocks the form and reports the outcome")
	choose(desktop, "bot_aim", "head"); choose(desktop, "bot_nades", "off"); choose(desktop, "match_chat", "off")
	var phone := render_form(settings, true)
	check(selected(phone, "bot_aim") == "head" and selected(phone, "bot_nades") == "off" and option(phone, "bot_identity") == null and settings.draft.bot_identity == "player" and selected(phone, "match_chat") == "off", "compact phone renders the same unsaved draft")
	settings.submit()
	check(sent[-1].body.settings.bot_aim == "head" and sent[-1].body.settings.bot_nades == "off" and sent[-1].body.settings.bot_identity == "player" and sent[-1].body.settings.match_chat == "off", "actual choices are serialized without turning custom/off into defaults")
	check(option(desktop, "bot_nades").disabled and option(phone, "bot_nades").disabled, "shared write locks both device forms")
	settings.finished("/api/3d/settings", {"ok":false, "reason":"fixture rejection"})
	check(settings.dirty and settings.message == "fixture rejection" and not option(phone, "bot_nades").disabled, "rejected save retains the editable draft and reason")
	CareerBridge.busy = true; CareerBridge.active_post = true; settings._request_busy_changed(true)
	check(option(desktop, "bot_aim").disabled and option(phone, "match_chat").disabled, "unrelated backend writes also lock both forms")
	settings.set_value("bot_aim", "mixed")
	check(settings.draft.bot_aim == "head", "late input cannot race an active write")
	CareerBridge.busy = false; CareerBridge.active_post = false; settings._request_busy_changed(false)
	check(not option(desktop, "bot_aim").disabled and not option(phone, "match_chat").disabled, "transport completion restores both forms")
	desktop.free(); phone.free()
	CareerBridge.context.settings = {"config":{"ready":true}, "bot_aim":"body", "bot_nades":"less", "match_chat":"custom"}
	var legacy := Settings.new(); legacy.command_sender = send_fixture
	var legacy_form := render_form(legacy)
	check(selected(legacy_form, "bot_aim") == "body" and selected(legacy_form, "bot_nades") == "less" and selected(legacy_form, "match_chat") == "custom", "flat preferences without difficulty are not replaced by diagnostic config")
	check(option(legacy_form, "bot_identity") == null and legacy.draft.bot_identity == "player" and selected(legacy_form, "difficulty") == "Medium" and not legacy.dirty, "missing legacy fields use defaults without automatic save")
	legacy.submit()
	check(sent[-1].body.settings.bot_movement == "classic" and sent[-1].body.settings.bot_nades == "less", "legacy save fills only missing defaults and keeps configured values")
	legacy_form.free()
	CareerBridge.context.settings = {"settings":{"difficulty":"Low", "bot_aim":"head", "bot_nades":"more", "bot_identity":"player", "bot_movement":"natural", "match_chat":"off"}, "config":{"ready":true}}
	var nested := Settings.new(); nested.command_sender = send_fixture
	var nested_form := render_form(nested, true)
	check(selected(nested_form, "bot_aim") == "head" and selected(nested_form, "bot_nades") == "more" and selected(nested_form, "match_chat") == "off" and nested.draft.bot_movement == "classic", "legacy nested settings retain choices but normalize retired movement")
	Locale.set_language("en", false)
	check(Locale.text("头部优先") == "Prefer head shots" and Locale.text("局内队伍对话") == "In-match team dialogue", "new option labels have English translations")
	check(selected(nested_form, "bot_aim") == "head" and selected(nested_form, "match_chat") == "off" and not nested.dirty, "language changes never mutate option metadata or preference drafts")
	Locale.set_language("zh-CN", false)
	nested_form.free()
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service and not CareerBridge.busy, "all writes remained captured fixtures")
	print("BOT_OPTIONS_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
