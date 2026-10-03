extends SceneTree
## Run only in the isolated QA tree, with --no-service. Never writes user://.
var failures: Array[String] = []
var checks := 0
var locale

func _initialize() -> void:
	call_deferred("run")

func check(value: bool, caption: String) -> void:
	checks += 1
	if not value: failures.append(caption)

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args():
		push_error("locale_native_test requires --no-service and an isolated QA tree")
		quit(1)
		return
	locale = root.get_node("Locale")
	if "--locale-restart-check" in OS.get_cmdline_user_args():
		check(locale.language == "en", "language loaded after process restart")
		check(locale.preference("font") == "system", "merged font preference loaded after restart")
		print("LOCALE_RESTART_RESULT checks=", checks, " failures=", JSON.stringify(failures))
		quit(0 if failures.is_empty() else 1)
		return
	var preferences_path: String = locale._preferences_path()
	check(preferences_path == "res://runtime/ui_preferences_test.json", "test preference path isolated from user preferences")
	var existed := FileAccess.file_exists(preferences_path)
	var stored := FileAccess.get_file_as_string(preferences_path) if existed else ""
	var before_preferences: Dictionary = locale._preferences.duplicate(true)
	var old_language: String = locale.language
	locale.set_language("zh-CN", false)
	locale.set_language("en", false)
	check(locale.text("界面语言") == "Language", "English service")
	check(TranslationServer.translate("界面语言") == "Language", "native TranslationServer")
	check(locale.text("用户自己的未知内容") == "用户自己的未知内容", "unknown authored/user content unchanged")
	check(locale.text("已购买 12 · 已摆放 3") == "Owned 12 · Placed 3", "numeric template unchanged")
	var label := Label.new()
	label.text = "界面语言"
	root.add_child(label)
	var world := Label3D.new()
	world.text = "界面语言"
	root.add_child(world)
	await process_frame
	var english_width: float = label.get_minimum_size().x
	var english_aabb: AABB = world.get_aabb()
	locale.set_language("zh-CN", false)
	await process_frame
	check(TranslationServer.translate("界面语言") == "界面语言", "Chinese native locale restored")
	check(label.text == "界面语言" and world.text == "界面语言", "source label text preserved")
	check(label.get_minimum_size().x != english_width, "native Label refreshed without node scan")
	check(world.get_aabb().size.x != english_aabb.size.x, "native Label3D refreshed without node scan")
	locale.protect_records({"player":{"name":"冠军","ability":80},"team":{"name":"青训","roster":[]}})
	locale.set_language("en")
	check(locale.text("冠军") == "冠军" and locale.text("青训") == "青训", "name collisions protected")
	locale.register_projection({"title":"测试自定义内容","title_en":"Authored custom content"})
	check(locale.text("测试自定义内容") == "Authored custom content", "authored backend fields registered")
	locale.set_preference("font", "system")
	var saved = JSON.parse_string(FileAccess.get_file_as_string(preferences_path))
	check(saved is Dictionary and saved.language == "en" and saved.font == "system", "font merge preserves language preference")
	var output: Array = []
	var status := OS.execute(OS.get_executable_path(), ["--headless", "--path", ProjectSettings.globalize_path("res://"), "--script", "res://tests/locale_native_test.gd", "--", "--no-service", "--locale-restart-check"], output, true)
	check(status == 0 and str(output).contains("LOCALE_RESTART_RESULT"), "separate process persistence check")
	print(str(output))
	# Restore the fixture file and memory; no real preference, career or service touched.
	locale._preferences = before_preferences
	locale.set_language(old_language, false)
	if existed:
		var file := FileAccess.open(preferences_path, FileAccess.WRITE)
		if file: file.store_string(stored)
	else:
		DirAccess.remove_absolute(ProjectSettings.globalize_path(preferences_path))
	print("LOCALE_NATIVE_RESULT checks=", checks, " failures=", JSON.stringify(failures))
	quit(0 if failures.is_empty() else 1)
