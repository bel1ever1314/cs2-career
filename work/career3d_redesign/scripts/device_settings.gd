extends RefCounted
## One unsaved form shared by phone and workstation; Python validates every write.
const UI = preload("res://scripts/computer_ui.gd")
var draft: Dictionary = {}
var dirty := false
var pending := false
var fetched := false
var message := ""
var command_sender: Callable
var saving := false
var install_message := ""

func config() -> Dictionary:
	var settings: Dictionary = CareerBridge.context.get("settings", {})
	var raw: Dictionary = settings.get("settings", settings.get("config", settings))
	var merged := raw.duplicate(true)
	merged["real_skins"] = settings.get("real_skins", raw.get("real_skins", false))
	merged["steam_id"] = settings.get("steam_id", raw.get("steam_id", ""))
	return merged

func render(host: Node, parent: Node, compact: bool = false) -> void:
	if draft.is_empty() and not dirty:
		draft = config()
	UI.label(parent, "CS2 与人机增强", 19 if compact else 25)
	UI.label(parent, "Bot Improver 使用你配置的发行包与难度。", 12, UI.MUTED)
	var received: Dictionary = CareerBridge.context.get("settings", {})
	var setup: Dictionary = received.get("setup", received.get("config", {}).get("setup", {}))
	if setup.get("available", false):
		UI.label(parent, "测试包已包含人机增强。确认下方 CS2 路径并退出游戏后，可在此安装；安装前会备份相关文件。", 12, UI.MUTED)
		var install: Button = host._button(parent, "安装随包人机增强", install_bundle)
		install.name = "DeviceSettingsInstallBundle"
		install.disabled = dirty or pending or CareerBridge.busy
		if dirty: UI.label(parent, "先保存下方设置，再安装到所选 CS2 目录。", 12, UI.MUTED)
	for field in [{"key":"steam_exe", "name":"Steam 程序"}, {"key":"csgo_path", "name":"CS2 / game / csgo 目录"}, {"key":"mod_source_path", "name":"Bot Improver 发行包目录"}, {"key":"skins_source_path", "name":"换肤插件目录（可留空）"}]:
		UI.label(parent, str(field.name), 12, UI.MUTED)
		var edit := LineEdit.new()
		edit.name = "DeviceSetting_" + str(field.key)
		UI.line_edit(edit)
		edit.text = str(draft.get(field.key, ""))
		edit.placeholder_text = "粘贴本机完整路径"
		edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		parent.add_child(edit)
		edit.text_changed.connect(func(value: String): set_value(str(field.key), value))
	UI.label(parent, "人机难度", 12, UI.MUTED)
	options(parent, "difficulty", [{"id":"Low", "name":"低"}, {"id":"Medium", "name":"中"}, {"id":"High", "name":"高"}], "Medium")
	UI.label(parent, "游戏内换肤", 16)
	var enable := CheckBox.new()
	enable.name = "DeviceSkinEnabled"
	enable.text = "启用游戏内换肤"
	UI.transparent(enable)
	enable.button_pressed = bool(draft.get("real_skins", false))
	parent.add_child(enable)
	enable.toggled.connect(func(value: bool): set_value("real_skins", value))
	options(parent, "skins_inventory_mode", [{"id":"career", "name":"生涯库存"}, {"id":"external", "name":"外部库存"}], "career")
	UI.label(parent, "SteamID64", 12, UI.MUTED)
	var steam := LineEdit.new()
	steam.name = "DeviceSetting_steam_id"
	UI.line_edit(steam)
	steam.text = str(draft.get("steam_id", ""))
	steam.placeholder_text = "游戏内换肤的账户 ID"
	parent.add_child(steam)
	steam.text_changed.connect(func(value: String): set_value("steam_id", value))
	UI.label(parent, "外部库存模式保留生涯市场；进入 CS2 时使用所选库存来源。", 12, UI.MUTED)
	UI.label(parent, "可选饰品工具", 16)
	var tools := CheckBox.new()
	tools.name = "DeviceSkinToolsEnabled"
	tools.text = "启用饰品扩展接口"
	UI.transparent(tools)
	tools.button_pressed = draft.get("skin_tools_enabled", false) == true
	parent.add_child(tools)
	tools.toggled.connect(func(value: bool): set_value("skin_tools_enabled", value))
	UI.label(parent, "供自行安装的检视／贴纸工具接入，不包含编辑器，也不会自动下载。", 12, UI.MUTED)
	var actions := HBoxContainer.new()
	parent.add_child(actions)
	var save: Button = host._button(actions, "保存 CS2 设置", submit)
	save.name = "DeviceSettingsSave"
	UI.primary(save)
	host._button(actions, "重新读取", reset.bind(host), false)
	if not message.is_empty(): UI.label(parent, message, 12, UI.MUTED)
	if not fetched and not pending and not CareerBridge.context.has("settings"):
		host.call_deferred("_fetch_device_settings")

func options(parent: Node, key: String, choices: Array, fallback: String) -> void:
	var select := OptionButton.new()
	select.name = "DeviceSetting_" + key
	UI.dark_options(select)
	select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	for choice in choices:
		select.add_item(str(choice.name))
		select.set_item_metadata(select.item_count - 1, str(choice.id))
		if str(choice.id) == str(draft.get(key, fallback)): select.select(select.item_count - 1)
	parent.add_child(select)
	select.item_selected.connect(func(index: int): set_value(key, select.get_item_metadata(index)))

func set_value(key: String, value: Variant) -> void:
	draft[key] = value
	dirty = true

func submit() -> void:
	saving = true
	install_message = ""
	var settings := {}
	for key in ["steam_exe", "csgo_path", "mod_source_path", "difficulty", "skins_source_path", "skins_inventory_mode"]:
		settings[key] = str(draft.get(key, "Medium" if key == "difficulty" else ("career" if key == "skins_inventory_mode" else ""))).strip_edges()
	settings["skin_tools_enabled"] = draft.get("skin_tools_enabled", false) == true
	var body := {"revision":int(CareerBridge.context.get("calendar", {}).get("revision", 0)), "settings":settings, "real_skins":bool(draft.get("real_skins", false)), "steam_id":str(draft.get("steam_id", "")).strip_edges()}
	pending = bool(command_sender.call("/api/3d/settings", body.duplicate(true))) if command_sender.is_valid() else CareerBridge.command("/api/3d/settings", body)

func install_bundle() -> void:
	if dirty or pending or CareerBridge.busy: return
	saving = false
	install_message = ""
	var body := {"revision":int(CareerBridge.context.get("calendar", {}).get("revision", 0)), "confirm":true}
	pending = bool(command_sender.call("/api/3d/setup/install", body.duplicate(true))) if command_sender.is_valid() else CareerBridge.command("/api/3d/setup/install", body)
	if pending: message = "正在备份并安装随包人机增强……"

func fetch() -> void:
	if not pending and not CareerBridge.busy:
		saving = false
		pending = CareerBridge._send("/api/3d/settings", {}, false)

func reset(host: Node) -> void:
	dirty = false
	draft.clear()
	fetched = false
	message = ""
	install_message = ""
	fetch()
	host._rebuild()

func finished(path: String, result: Dictionary) -> bool:
	if path == "/api/3d/setup/install":
		pending = false
		install_message = str(result.get("reason", result.get("msg", "安装已完成。" if result.get("ok", false) else "安装未完成。")))
		message = install_message
		if result.get("ok", false):
			fetched = false
			call_deferred("fetch")
		return true
	if path != "/api/3d/settings": return false
	pending = false
	fetched = true
	message = str(result.get("reason", result.get("msg", "设置已保存。" if result.get("ok", false) else "设置没有保存。")))
	if not install_message.is_empty() and not saving and result.get("ok", false): message = install_message
	if result.get("ok", false) and (saving or not dirty):
		dirty = false
		draft = config()
		var received: Dictionary = result.get("settings", {})
		if not received.is_empty():
			draft = received.get("settings", received.get("config", received)).duplicate(true)
			for key in ["real_skins", "steam_id"]:
				if received.has(key): draft[key] = received[key]
	saving = false
	return true
