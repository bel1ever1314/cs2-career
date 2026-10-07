extends RefCounted
## One unsaved form shared by phone and workstation; Python validates every write.
const UI = preload("res://scripts/computer_ui.gd")
const BOT_DEFAULTS := {"bot_aim":"mixed", "bot_nades":"normal", "bot_identity":"player", "bot_movement":"classic", "match_chat":"on", "bot_profile_mode":"career", "bot_profile_source":""}
var draft: Dictionary = {}
var dirty := false
var pending := false
var fetched := false
var message := ""
var command_sender: Callable
var saving := false
var detecting := false
var checking_updates := false
var switching_environment := false
var update_url := ""
var install_message := ""
var install_source := ""
var install_stage := ""
var pending_path := ""
var pending_read := false
var query_sender: Callable
var form_controls: Array[Control] = []
var action_buttons: Array[Button] = []
var status_labels: Array[Label] = []
var environment_labels: Array[Label] = []

func _init() -> void:
	CareerBridge.busy_changed.connect(_request_busy_changed)

func config() -> Dictionary:
	var settings: Dictionary = CareerBridge.context.get("settings", {})
	return _config_from(settings)

func _config_from(settings: Dictionary) -> Dictionary:
	# The flat settings payload also has a diagnostic "config" dictionary.
	# Keep preference fields rather than treating that diagnostic as the form.
	var raw: Dictionary = settings
	if settings.get("settings") is Dictionary:
		raw = settings.settings
	elif not _has_preferences(settings) and settings.get("config") is Dictionary:
		raw = settings.config
	var merged := raw.duplicate(true)
	for key in BOT_DEFAULTS:
		if not merged.has(key): merged[key] = BOT_DEFAULTS[key]
	# The current backend only supports the classic controller. Legacy natural
	# preferences must not silently re-enable a retired experiment on save.
	merged["bot_movement"] = "classic"
	merged["bot_identity"] = "player"
	merged["real_skins"] = settings.get("real_skins", raw.get("real_skins", false))
	merged["steam_id"] = settings.get("steam_id", raw.get("steam_id", ""))
	return merged

func _has_preferences(value: Dictionary) -> bool:
	for key in ["difficulty", "steam_exe", "csgo_path", "mod_source_path", "skins_source_path", "skins_inventory_mode", "bot_aim", "bot_nades", "bot_identity", "bot_movement", "match_chat"]:
		if value.has(key): return true
	return false

func render(host: Node, parent: Node, compact: bool = false) -> void:
	_prune_render_refs()
	var language_picker := Locale.render_picker(parent, compact)
	UI.dark_options(language_picker)
	if draft.is_empty() and not dirty:
		draft = config()
	UI.label(parent, "CS2 与人机增强", 19 if compact else 25)
	UI.label(parent, "使用你配置的 Bot Improver 发行包与难度，安装时加入本项目的兼容修复。", 12, UI.MUTED)
	var received: Dictionary = CareerBridge.context.get("settings", {})
	# Settings stay editable during a match; the backend says when they apply.
	var apply_note := str(received.get("apply_note", ""))
	if not apply_note.is_empty():
		var live_note := UI.label(parent, apply_note, 13, UI.AMBER)
		live_note.name = "DeviceSettingsLiveMatchNote"
		live_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var setup: Dictionary = received.get("setup", received.get("config", {}).get("setup", {}))
	var diagnostics: Dictionary = received.get("config", {})
	for category in [{"key":"path_errors", "title":"路径需要调整"}, {"key":"component_errors", "title":"组件需要安装或更新"}]:
		var errors: Array = diagnostics.get(str(category.key), [])
		if not errors.is_empty():
			var heading := UI.label(parent, str(category.title), 14)
			heading.name = "DeviceSettingsStatus_" + str(category.key)
			for error in errors: UI.label(parent, str(error), 12, UI.MUTED)
	if diagnostics.get("ready", false):
		var ready := UI.label(parent, "CS2 运行组件已就绪", 14, UI.GREEN)
		ready.name = "DeviceSettingsReady"
	var compatibility: Dictionary = diagnostics.get("compatibility", {})
	if compatibility.get("current", false):
		var version_text := "兼容副本：" + str(compatibility.get("revision", ""))
		var version_label := UI.label(parent, version_text, 12, UI.MUTED)
		version_label.name = "DeviceSettingsCompatibility"
	var detect_button: Button = host._button(parent, "自动检测 Steam／CS2 路径", detect_paths, false)
	detect_button.name = "DeviceSettingsDetectPaths"
	detect_button.set_meta("local_detection", true)
	action_buttons.append(detect_button)
	for field in [{"key":"steam_exe", "name":"Steam 程序"}, {"key":"csgo_path", "name":"CS2 / game / csgo 目录"}, {"key":"mod_source_path", "name":"Bot Improver 发行包目录"}, {"key":"skins_source_path", "name":"换肤插件目录（可留空）"}]:
		UI.label(parent, str(field.name), 12, UI.MUTED)
		var edit := LineEdit.new()
		edit.name = "DeviceSetting_" + str(field.key)
		UI.line_edit(edit)
		edit.text = str(draft.get(field.key, ""))
		edit.placeholder_text = "粘贴本机完整路径"
		edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		parent.add_child(edit)
		form_controls.append(edit)
		edit.text_changed.connect(func(value: String): set_value(str(field.key), value))
	UI.label(parent, "安装直接使用本地发行包，并加入我们自带的组件，不需要联网。原发行包不变，游戏文件会先备份。", 12, UI.MUTED)
	# Installation is stricter than a normal queued preference write. Keep its
	# transient busy gate out of the host's cached domain availability.
	var install_external_button: Button = host._button(parent, "安装填写目录的人机增强", install_external, false)
	install_external_button.name = "DeviceSettingsInstallExternal"
	install_external_button.set_meta("install_source", "external")
	action_buttons.append(install_external_button)
	if setup.get("available", false):
		var install_bundle_button: Button = host._button(parent, "安装随包人机增强", install_bundle, false)
		install_bundle_button.name = "DeviceSettingsInstallBundle"
		install_bundle_button.set_meta("install_source", "bundle")
		action_buttons.append(install_bundle_button)
	var check_button: Button = host._button(parent, "检查人机增强更新", check_updates, false)
	check_button.name = "DeviceSettingsCheckUpdates"
	action_buttons.append(check_button)
	UI.label(parent, "仅点击检查更新时连接 GitHub，不会自动下载或替换插件。", 12, UI.MUTED)
	if not update_url.is_empty():
		var release_button: Button = host._button(parent, "打开官方更新页面", open_update_page, false)
		release_button.name = "DeviceSettingsUpdatePage"
		action_buttons.append(release_button)
	UI.label(parent, "本地插件开关", 16)
	var environment_status := UI.label(parent, _environment_text(), 12, UI.MUTED)
	environment_status.name = "DeviceEnvironmentStatus"
	environment_labels.append(environment_status)
	UI.label(parent, "关闭 CS2 后可切换。仅调整本地插件加载，不会启动游戏或联网。退出增强对局后会自动恢复普通 CS2。", 12, UI.MUTED)
	for choice in [{"mode":"enhanced", "name":"开启本地插件"}, {"mode":"normal", "name":"关闭插件 · 恢复普通 CS2"}]:
		var environment_button: Button = host._button(parent, str(choice.name), switch_environment.bind(str(choice.mode)), false)
		environment_button.name = "DeviceEnvironment_" + str(choice.mode)
		environment_button.set_meta("environment_mode", str(choice.mode))
		action_buttons.append(environment_button)
	var environment_refresh: Button = host._button(parent, "刷新插件状态", refresh_environment, false)
	environment_refresh.name = "DeviceEnvironmentRefresh"
	environment_refresh.set_meta("environment_refresh", true)
	action_buttons.append(environment_refresh)
	UI.label(parent, "人机难度", 12, UI.MUTED)
	options(parent, "difficulty", [{"id":"Low", "name":"低"}, {"id":"Medium", "name":"中"}, {"id":"High", "name":"高"}], "Medium")
	UI.label(parent, "BotProfile 来源", 12, UI.MUTED)
	options(parent, "bot_profile_mode", [{"id":"career", "name":"生涯能力模板"}, {"id":"custom", "name":"我的 VPK 模板"}], "career")
	var profile_source := LineEdit.new()
	profile_source.name = "DeviceSetting_bot_profile_source"
	UI.line_edit(profile_source)
	profile_source.text = str(draft.get("bot_profile_source", ""))
	profile_source.placeholder_text = "自定义 botprofile.vpk 的完整路径"
	parent.add_child(profile_source)
	form_controls.append(profile_source)
	profile_source.text_changed.connect(func(value: String): set_value("bot_profile_source", value))
	UI.label(parent, "读取你的 Default 和模板参数，原 VPK 不改动；本场选手姓名与战绩仍由生涯管理。", 12, UI.MUTED)
	UI.label(parent, "瞄准预设", 12, UI.MUTED)
	options(parent, "bot_aim", [{"id":"head", "name":"头部优先"}, {"id":"mixed", "name":"混合"}, {"id":"body", "name":"身体优先"}], "mixed")
	UI.label(parent, "选择人机优先瞄准的部位；个人能力与比赛难度仍会影响枪法。", 12, UI.MUTED)
	UI.label(parent, "道具预设", 12, UI.MUTED)
	options(parent, "bot_nades", [{"id":"off", "name":"关闭"}, {"id":"less", "name":"偏少"}, {"id":"normal", "name":"正常"}, {"id":"more", "name":"偏多"}, {"id":"max", "name":"最多"}], "normal")
	UI.label(parent, "调整人机使用道具的频率。", 12, UI.MUTED)
	UI.label(parent, "队友与对手身份", 12, UI.MUTED)
	UI.label(parent, "只改变游戏内身份显示，不改变你控制的选手。", 12, UI.MUTED)
	var movement := UI.label(parent, "移动控制 · 原版增强", 12, UI.MUTED)
	movement.name = "DeviceBotMovementPreset"
	UI.label(parent, "局内队伍对话", 12, UI.MUTED)
	options(parent, "match_chat", [{"id":"on", "name":"内置＋扩展"}, {"id":"custom", "name":"仅扩展包"}, {"id":"off", "name":"关闭"}], "on")
	UI.label(parent, "仅扩展包模式使用扩展工坊安装的比赛聊天；没有扩展包时不会播放内置对话。", 12, UI.MUTED)
	UI.label(parent, "游戏内换肤", 16)
	var enable := CheckBox.new()
	enable.name = "DeviceSkinEnabled"
	enable.text = "启用游戏内换肤"
	UI.transparent(enable)
	enable.button_pressed = bool(draft.get("real_skins", false))
	parent.add_child(enable)
	form_controls.append(enable)
	enable.toggled.connect(func(value: bool): set_value("real_skins", value))
	options(parent, "skins_inventory_mode", [{"id":"career", "name":"生涯库存"}, {"id":"external", "name":"外部库存"}], "career")
	UI.label(parent, "SteamID64", 12, UI.MUTED)
	var steam := LineEdit.new()
	steam.name = "DeviceSetting_steam_id"
	UI.line_edit(steam)
	steam.text = str(draft.get("steam_id", ""))
	steam.placeholder_text = "游戏内换肤的账户 ID"
	parent.add_child(steam)
	form_controls.append(steam)
	steam.text_changed.connect(func(value: String): set_value("steam_id", value))
	UI.label(parent, "启用游戏内换肤时，需填写 17 位数字 SteamID64；暂不使用可先关闭上方开关。", 12, UI.MUTED)
	UI.label(parent, "外部库存模式保留生涯市场；进入 CS2 时使用所选库存来源。", 12, UI.MUTED)
	var loadout: Dictionary = received.get("loadout_status", {})
	if not loadout.is_empty():
		var loadout_text := str(loadout.get("reason", ""))
		if str(loadout.get("state", "")) == "ready":
			loadout_text = "已装备 CT 侧 %d 项、T 侧 %d 项；进入比赛时同步。" % [int(loadout.get("equipped_ct", 0)), int(loadout.get("equipped_t", 0))]
		var loadout_label := UI.label(parent, loadout_text, 12, UI.GREEN if str(loadout.get("state", "")) == "ready" else UI.MUTED)
		loadout_label.name = "DeviceSkinLoadoutStatus"
	UI.label(parent, "可选饰品工具", 16)
	var tools := CheckBox.new()
	tools.name = "DeviceSkinToolsEnabled"
	tools.text = "启用饰品扩展接口"
	UI.transparent(tools)
	tools.button_pressed = draft.get("skin_tools_enabled", false) == true
	parent.add_child(tools)
	form_controls.append(tools)
	tools.toggled.connect(func(value: bool): set_value("skin_tools_enabled", value))
	UI.label(parent, "供自行安装的检视／贴纸工具接入，不包含编辑器，也不会自动下载。", 12, UI.MUTED)
	var actions := HBoxContainer.new()
	parent.add_child(actions)
	var save: Button = host._button(actions, "保存 CS2 设置", submit)
	save.name = "DeviceSettingsSave"
	UI.primary(save)
	action_buttons.append(save)
	var reload: Button = host._button(actions, "重新读取", reset.bind(host), false)
	reload.name = "DeviceSettingsReload"
	action_buttons.append(reload)
	var status := UI.label(parent, message, 12, UI.MUTED)
	status.name = "DeviceSettingsOperationStatus"
	status_labels.append(status)
	_sync_form_state(false)
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
	form_controls.append(select)
	select.item_selected.connect(func(index: int): set_value(key, select.get_item_metadata(index)))

func set_value(key: String, value: Variant) -> void:
	if saving or (pending and not pending_read) or not install_stage.is_empty() or (CareerBridge.busy and CareerBridge.active_post): return
	draft[key] = value
	dirty = true
	_sync_form_state()

func submit() -> void:
	if detecting or saving or (pending and not pending_read) or not install_stage.is_empty() or (CareerBridge.busy and CareerBridge.active_post): return
	saving = true
	install_message = ""
	_set_message("正在保存 CS2 设置……")
	_send_settings()

func _send_settings() -> void:
	var settings := {}
	for key in ["steam_exe", "csgo_path", "mod_source_path", "difficulty", "skins_source_path", "skins_inventory_mode", "bot_aim", "bot_nades", "bot_identity", "match_chat", "bot_profile_mode", "bot_profile_source"]:
		var fallback := str(BOT_DEFAULTS.get(key, "Medium" if key == "difficulty" else ("career" if key == "skins_inventory_mode" else "")))
		settings[key] = str(draft.get(key, fallback)).strip_edges()
	settings["bot_movement"] = "classic"
	settings["bot_identity"] = "player"
	settings["skin_tools_enabled"] = draft.get("skin_tools_enabled", false) == true
	var body := {"revision":int(CareerBridge.context.get("calendar", {}).get("revision", 0)), "settings":settings, "real_skins":bool(draft.get("real_skins", false)), "steam_id":str(draft.get("steam_id", "")).strip_edges()}
	pending_path = "/api/3d/settings"
	var accepted := _command(pending_path, body)
	pending = accepted or pending_read
	if not accepted:
		if not pending_read: pending_path = ""
		saving = false
		install_source = ""
		install_stage = ""
		_set_message(CareerBridge.message if not CareerBridge.message.is_empty() else "设置请求没有发出，请再试一次。")
	_sync_form_state()

func _command(path: String, body: Dictionary) -> bool:
	return bool(command_sender.call(path, body.duplicate(true))) if command_sender.is_valid() else CareerBridge.command(path, body)

func detect_paths() -> void:
	if pending or saving or detecting or not install_stage.is_empty() or CareerBridge.busy: return
	pending_path = "/api/3d/settings/detect"
	detecting = true
	pending = bool(query_sender.call(pending_path)) if query_sender.is_valid() else CareerBridge._send(pending_path, {}, false)
	if not pending:
		detecting = false
		pending_path = ""
	_set_message("正在检测本机 Steam 和 CS2 路径……" if pending else "检测请求未发出，请稍后再试。")
	_sync_form_state()

func check_updates() -> void:
	if pending or saving or not install_stage.is_empty() or CareerBridge.busy: return
	pending_path = "/api/3d/settings/updates"
	checking_updates = true
	pending = bool(query_sender.call(pending_path)) if query_sender.is_valid() else CareerBridge._send(pending_path, {}, false)
	if not pending:
		checking_updates = false
		pending_path = ""
	_set_message("正在检查官方人机增强更新……" if pending else "更新检查未发出，不影响本地安装。")
	_sync_form_state()

func open_update_page() -> void:
	if update_url.begins_with("https://github.com/ed0ard/CS2-Bot-Improver/releases"):
		OS.shell_open(update_url)

func _environment() -> Dictionary:
	return CareerBridge.context.get("settings", {}).get("environment", {})

func _unsaved_paths() -> bool:
	var saved := config()
	for key in ["steam_exe", "csgo_path", "mod_source_path", "skins_source_path"]:
		if str(draft.get(key, "")).strip_edges() != str(saved.get(key, "")).strip_edges(): return true
	return false

func _environment_block_reason(mode: String) -> String:
	if _unsaved_paths(): return "请先保存路径设置，再切换本地插件。"
	var state := _environment()
	if not state.get("switch_available", false):
		var reason := str(state.get("reason", ""))
		return reason if not reason.is_empty() else "请先读取插件状态，确认 CS2 已完全关闭。"
	if str(state.get("mode", "unknown")) == mode:
		return "当前为普通 CS2。" if mode == "normal" else "本地插件已开启。"
	return ""

func _environment_text() -> String:
	var state := _environment()
	var title := "插件状态待确认"
	match str(state.get("mode", "unknown")):
		"normal": title = "当前为普通 CS2。"
		"enhanced": title = "本地插件已开启。"
		"mixed": title = "本地插件加载配置需要调整。"
	var reason := str(state.get("reason", ""))
	var text := title if reason.is_empty() or reason == title else title + "\n" + reason
	if _unsaved_paths(): text += "\n" + "请先保存路径设置，再切换本地插件。"
	return text

func _sync_environment_status() -> void:
	for label in environment_labels:
		if is_instance_valid(label): label.text = _environment_text()

func switch_environment(mode: String) -> void:
	if mode not in ["normal", "enhanced"]: return
	if pending or saving or not install_stage.is_empty() or CareerBridge.busy: return
	var blocked := _environment_block_reason(mode)
	if not blocked.is_empty():
		_set_message(blocked)
		return
	var body := {"revision":int(CareerBridge.context.get("calendar", {}).get("revision", 0)), "mode":mode}
	pending_path = "/api/3d/settings/environment"
	switching_environment = true
	pending = _command(pending_path, body)
	if not pending:
		switching_environment = false
		pending_path = ""
	_set_message(("正在开启本地插件……" if mode == "enhanced" else "正在恢复普通 CS2……") if pending else (CareerBridge.message if not CareerBridge.message.is_empty() else "插件切换请求没有发出，请再试一次。"))
	_sync_form_state()

func refresh_environment() -> void:
	if pending or saving or not install_stage.is_empty() or CareerBridge.busy: return
	pending_path = "/api/3d/settings/environment"
	pending = bool(query_sender.call(pending_path)) if query_sender.is_valid() else CareerBridge._send(pending_path, {}, false)
	if not pending: pending_path = ""
	_set_message("正在读取本地插件状态……" if pending else "插件状态读取请求没有发出，请再试一次。")
	_sync_form_state()

func install_external() -> void:
	_prepare_install("external")

func install_bundle() -> void:
	_prepare_install("bundle")

func _prepare_install(source: String) -> void:
	if pending or not install_stage.is_empty() or CareerBridge.busy: return
	if source == "external" and str(draft.get("mod_source_path", "")).strip_edges().is_empty():
		_set_message("请先填写 Bot Improver 发行包目录。")
		return
	install_source = source
	install_stage = "saving"
	saving = true
	install_message = ""
	_set_message("正在保存当前设置，随后安装人机增强……")
	_send_settings()

func _install_saved_settings() -> void:
	saving = false
	install_stage = "installing"
	var body := {"revision":int(CareerBridge.context.get("calendar", {}).get("revision", 0)), "confirm":true, "source":install_source}
	pending_path = "/api/3d/setup/install"
	pending = _command(pending_path, body)
	if pending:
		_set_message("正在检查本地组件、备份并安装人机增强，无需联网……")
	else:
		install_stage = ""
		install_source = ""
		pending_path = ""
		_set_message(CareerBridge.message if not CareerBridge.message.is_empty() else "安装请求没有发出，请再试一次。")
	_sync_form_state()

func _set_message(value: String) -> void:
	message = value
	for label in status_labels:
		if is_instance_valid(label): label.text = message

func _prune_render_refs() -> void:
	var controls: Array[Control] = []
	for control in form_controls:
		if is_instance_valid(control): controls.append(control)
	form_controls = controls
	var buttons: Array[Button] = []
	for button in action_buttons:
		if is_instance_valid(button): buttons.append(button)
	action_buttons = buttons
	var labels: Array[Label] = []
	for label in status_labels:
		if is_instance_valid(label): labels.append(label)
	status_labels = labels
	var environment_status: Array[Label] = []
	for label in environment_labels:
		if is_instance_valid(label): environment_status.append(label)
	environment_labels = environment_status

func _sync_form_state(apply_transport: bool = true) -> void:
	var locked := saving or (pending and not pending_read) or not install_stage.is_empty()
	var control_locked := locked or (CareerBridge.busy and CareerBridge.active_post)
	for control in form_controls:
		if not is_instance_valid(control): continue
		if control is LineEdit: control.editable = not control_locked
		elif control is BaseButton: control.disabled = control_locked
	for button in action_buttons:
		if not is_instance_valid(button): continue
		var unavailable: bool = locked or (button.has_meta("install_source") and pending) or (str(button.get_meta("install_source", "")) == "external" and str(draft.get("mod_source_path", "")).strip_edges().is_empty())
		if button.has_meta("environment_mode"):
			var blocked := _environment_block_reason(str(button.get_meta("environment_mode")))
			unavailable = unavailable or pending or not blocked.is_empty()
			button.tooltip_text = blocked
		if button.has_meta("environment_refresh"): unavailable = unavailable or pending
		button.set_meta("career_gate_disabled", unavailable)
		button.disabled = unavailable
		if apply_transport or button.has_meta("install_source") or button.has_meta("environment_mode") or button.has_meta("environment_refresh"):
			button.disabled = unavailable or (CareerBridge.busy and (CareerBridge.active_post or button.has_meta("install_source") or button.has_meta("environment_mode") or button.has_meta("environment_refresh")))
	_sync_environment_status()

func _request_busy_changed(_value: bool) -> void:
	_sync_form_state()

func fetch() -> void:
	if not pending and not CareerBridge.busy:
		saving = false
		pending_path = "/api/3d/settings"
		pending = bool(query_sender.call(pending_path)) if query_sender.is_valid() else CareerBridge._send(pending_path, {}, false)
		pending_read = pending
		if not pending:
			pending_path = ""
			install_stage = ""
		_sync_form_state()

func reset(host: Node) -> void:
	if detecting or saving or (pending and not pending_read) or not install_stage.is_empty(): return
	dirty = false
	draft.clear()
	fetched = false
	message = ""
	install_message = ""
	fetch()
	host._rebuild()

func finished(path: String, result: Dictionary) -> bool:
	if path == "/api/3d/settings" and result.get("result_summary", false):
		pending = false
		saving = false
		pending_read = false
		pending_path = ""
		install_stage = ""
		install_source = ""
		fetched = false
		_set_message(str(result.get("reason", result.get("msg", ""))))
		_sync_form_state()
		call_deferred("fetch") # Confirmation never authorizes a new install.
		return true
	if path == "/api/3d/settings/environment":
		if not pending or pending_path != path: return true
		pending = false
		pending_path = ""
		var was_switch := switching_environment
		switching_environment = false
		var received_settings: Dictionary = result.get("settings", {})
		if result.get("ok", false) and not received_settings.is_empty():
			CareerBridge.context["settings"] = received_settings.duplicate(true)
			if not dirty: draft = config()
		if result.get("environment") is Dictionary:
			var saved: Dictionary = CareerBridge.context.get("settings", {}).duplicate(true)
			saved["environment"] = result.environment.duplicate(true)
			CareerBridge.context["settings"] = saved
		_set_message(str(result.get("reason", result.get("msg", "插件状态已更新。" if result.get("ok", false) else ("插件切换未完成。" if was_switch else "插件状态读取未完成。")))))
		_sync_form_state()
		return true
	if path == "/api/3d/settings/updates":
		if not checking_updates or pending_path != path: return true
		checking_updates = false
		pending = false
		pending_path = ""
		update_url = str(result.get("url", ""))
		_set_message(str(result.get("reason", result.get("msg", "更新检查未完成，不影响本地安装。"))))
		_sync_form_state()
		return true
	if path == "/api/3d/settings/detect":
		if not detecting or pending_path != path: return true
		detecting = false
		pending = false
		pending_path = ""
		if result.get("ok", false):
			var paths: Dictionary = result.get("paths", {})
			for key in ["steam_exe", "csgo_path"]:
				var found := str(paths.get(key, ""))
				if not found.is_empty():
					draft[key] = found
					dirty = true
		_set_message(str(result.get("reason", result.get("msg", "路径检测未完成。"))))
		_sync_form_state()
		return true
	if path == "/api/3d/setup/install":
		if install_stage != "installing" or pending_path != path: return true
		pending = false
		pending_path = ""
		install_message = str(result.get("reason", result.get("msg", "安装已完成。" if result.get("ok", false) else "安装未完成。")))
		_set_message(install_message)
		install_source = ""
		if result.get("ok", false):
			fetched = false
			install_stage = "refreshing"
			call_deferred("fetch")
		else:
			install_stage = ""
		_sync_form_state()
		return true
	if path != "/api/3d/settings": return false
	# Phone and computer share this controller. Ignore an already consumed save
	# response after the chain has moved on to installation.
	if install_stage == "installing": return true
	var received: Dictionary = result.get("settings", {})
	if pending_read:
		pending_read = false
		fetched = true
		if result.get("ok", false) and not received.is_empty():
			CareerBridge.context["settings"] = received.duplicate(true)
		if saving:
			# A settings write can be queued behind this GET. Its own completion
			# is still pending: do not overwrite the draft or acknowledge saving.
			_sync_form_state()
			return true
	var should_install: bool = install_stage == "saving" and saving and pending_path == path
	pending = false
	pending_path = ""
	fetched = true
	_set_message(str(result.get("reason", result.get("msg", "设置已保存。" if result.get("ok", false) else "设置没有保存。"))))
	if not install_message.is_empty() and not saving and result.get("ok", false): _set_message(install_message)
	if result.get("ok", false) and not received.is_empty():
		# GET settings returns no full context; refresh the shared read projection
		# so both phone and computer show the new component diagnostics.
		CareerBridge.context["settings"] = received.duplicate(true)
	if result.get("ok", false) and (saving or not dirty):
		dirty = false
		draft = config()
		if not received.is_empty():
			draft = _config_from(received)
	saving = false
	if should_install and result.get("ok", false):
		_install_saved_settings()
	else:
		install_stage = ""
		install_source = ""
		_sync_form_state()
	return true
