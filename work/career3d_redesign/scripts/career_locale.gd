extends Node
## Display preferences only. Career context, IDs and command payloads stay original.
signal changed
const NativeTranslation = preload("res://scripts/career_locale_translation.gd")
const CATALOGUE := "res://data/locale_en.json"
var language := "zh-CN"
var _preferences: Dictionary = {}
var _messages: Dictionary = {}
var _templates: Array[Dictionary] = []
var _identity_names: Dictionary = {}
var _cache: Dictionary = {}
var _translation: Translation

func _ready() -> void:
	var saved = JSON.parse_string(FileAccess.get_file_as_string(_preferences_path())) if FileAccess.file_exists(_preferences_path()) else null
	if saved is Dictionary: _preferences = saved
	if _preferences.is_empty() and FileAccess.file_exists("res://runtime/ui_preferences.json"):
		var legacy = JSON.parse_string(FileAccess.get_file_as_string("res://runtime/ui_preferences.json"))
		if legacy is Dictionary: _preferences = legacy
	var data = JSON.parse_string(FileAccess.get_file_as_string(CATALOGUE))
	if data is Dictionary:
		_messages = data.get("phrases", {})
		for row in data.get("templates", []):
			var matcher := RegEx.new()
			if matcher.compile(str(row.get("pattern", ""))) == OK:
				_templates.append({"matcher":matcher, "replacement":row.replacement, "keys":row.get("keys", []), "prefix":row.get("prefix", "")})
	_translation = NativeTranslation.new()
	_translation.locale = "en"
	_translation.owner = self
	TranslationServer.add_translation(_translation)
	language = "en" if _preferences.get("language", "zh-CN") == "en" else "zh-CN"
	TranslationServer.set_locale("en" if language == "en" else "zh_CN")
	set_process(false)
	call_deferred("_connect_identities")

func _connect_identities() -> void:
	var bridge := get_node_or_null("/root/CareerBridge")
	if bridge != null:
		bridge.changed.connect(_update_identities)
		_update_identities()

func _exit_tree() -> void:
	if _translation != null:
		_translation.set("owner", null)
		TranslationServer.remove_translation(_translation)

func _update_identities() -> void:
	_identity_names.clear()
	_cache.clear()
	var bridge := get_node_or_null("/root/CareerBridge")
	if bridge != null: protect_records(bridge.context)

func protect_records(value: Variant) -> void:
	# Semantic identity fields are retained even when the player chooses a name
	# which happens to match a UI message (e.g. "冠军"). Never alter these fields.
	if value is Dictionary:
		if value.has("name") and (value.has("player_id") or value.has("ability") or value.has("roster") or value.has("players")):
			_identity_names[str(value.name)] = true
		for key in ["player", "player_name", "team_a", "team_b", "opponent", "champion", "winner"]:
			if value.get(key) is String and not str(value[key]).is_empty(): _identity_names[str(value[key])] = true
		for item in value.values(): protect_records(item)
	elif value is Array:
		for item in value: protect_records(item)

func register_projection(value: Variant) -> void:
	# Register exact authored siblings from the HTTP response, retaining source
	# strings in every control so native locale changes can restore Chinese.
	protect_records(value)
	_register_pairs(value)
	_cache.clear()

func _register_pairs(value: Variant) -> void:
	if value is Dictionary:
		for key in value:
			if str(key).ends_with("_en") and value[key] is String:
				var source = value.get(str(key).trim_suffix("_en"))
				if source is String and not source.is_empty(): _messages[source] = value[key]
			_register_pairs(value[key])
	elif value is Array:
		for item in value: _register_pairs(item)

func english(value: String) -> String:
	if value.is_empty() or _identity_names.has(value): return value
	if _cache.has(value): return _cache[value]
	var translated := _english(value)
	if _cache.size() > 4096: _cache.clear()
	_cache[value] = translated
	return translated

func _english(value: String) -> String:
	if _messages.has(value): return str(_messages[value])
	for row in _templates:
		if not str(row.prefix).is_empty() and not value.begins_with(str(row.prefix)): continue
		var matched: RegExMatch = row.matcher.search(value)
		if matched == null: continue
		var result := str(row.replacement)
		for index in range(row.keys.size()):
			var capture := matched.get_string(index + 1)
			# Only complete known semantic labels in template slots are localized;
			# captured names and arbitrary user content are never word-replaced.
			if not _identity_names.has(capture) and capture != value: capture = english(capture)
			result = result.replace("{" + str(row.keys[index]) + "}", capture)
		return result
	if value.contains("\n"):
		var lines := PackedStringArray()
		for line in value.split("\n"): lines.append(english(line))
		return "\n".join(lines)
	# UI layout separators join whole labels. Translate only complete catalogued
	# chunks, preserving unknown prose, player names and values verbatim.
	for separator in ["   ·   ", "  ·  ", " · ", " / "]:
		if value.contains(separator):
			var chunks := PackedStringArray()
			for chunk in value.split(separator): chunks.append(english(chunk))
			return separator.join(chunks)
	return value

func text(value: Variant) -> String:
	if value is Dictionary:
		return str(value.get("en", value.get("zh", value.get("zh-CN", "")))) if language == "en" else str(value.get("zh", value.get("zh-CN", value.get("en", ""))))
	return english(str(value)) if language == "en" else str(value)

func field(record: Dictionary, key: String, fallback: String = "") -> String:
	protect_records(record)
	return text(record.get(key + "_en", record.get(key, fallback))) if language == "en" else text(record.get(key, fallback))

func set_language(value: String, persist: bool = true) -> void:
	var next := "en" if value == "en" else "zh-CN"
	if next == language: return
	language = next
	if persist: set_preference("language", language)
	TranslationServer.set_locale("en" if language == "en" else "zh_CN")
	changed.emit()

func preference(key: String, fallback: Variant = null) -> Variant:
	return _preferences.get(key, fallback)

func set_preference(key: String, value: Variant) -> void:
	_preferences[key] = value
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(_preferences_path().get_base_dir()))
	var file := FileAccess.open(_preferences_path(), FileAccess.WRITE)
	if file: file.store_string(JSON.stringify(_preferences))

func _preferences_path() -> String:
	# user:// is writable in installed/exported games; preferences are not saves.
	# QA explicitly opts out of services and must never overwrite real preferences.
	if "--no-service" in OS.get_cmdline_user_args(): return "res://runtime/ui_preferences_test.json"
	return "user://ui_preferences.json"

func render_picker(parent: Node, compact: bool = false) -> OptionButton:
	var label := Label.new()
	label.text = "界面语言"
	label.add_theme_font_size_override("font_size", 14 if compact else 16)
	parent.add_child(label)
	var picker := OptionButton.new()
	picker.name = "CareerLanguageChoice"
	picker.add_item("简体中文")
	picker.add_item("English")
	picker.set_item_metadata(0, "zh-CN")
	picker.set_item_metadata(1, "en")
	picker.select(1 if language == "en" else 0)
	picker.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(picker)
	picker.item_selected.connect(func(index: int): set_language(str(picker.get_item_metadata(index))))
	return picker
