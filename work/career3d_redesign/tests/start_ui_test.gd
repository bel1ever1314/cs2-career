extends Node
## The actual device autoloads and world-derived option rows, with no service.
## Queued request tests inspect intent only and never flush it to a server.
const UI = preload("res://scripts/computer_ui.gd")
const PhoneUI = preload("res://scripts/phone_ui.gd")
const Avatar = preload("res://scripts/appearance_customization.gd")
const TeamDrawFixture = preload("res://tests/team_draw_fixture.gd")
var checks := 0
var failures: Array[String] = []
var actor
var fixture: Dictionary = {}
var capture := false
const DRAW_AXES := [{"id":"firepower", "name":"火力"}, {"id":"entrying", "name":"突破"}, {"id":"trading", "name":"补枪"}, {"id":"opening", "name":"首杀"}, {"id":"clutching", "name":"残局"}, {"id":"sniping", "name":"狙击"}, {"id":"utility", "name":"道具"}]

func completed_draw_fixture(era: String) -> Dictionary:
	return TeamDrawFixture.completed(era)

func _ready() -> void:
	call_deferred("run")

func before_computer() -> void:
	pass

func before_phone() -> void:
	pass

func set_device_open(_opened: bool, _kind: String) -> void:
	pass

func check(ok: bool, text: String) -> void:
	checks += 1
	if not ok: failures.append(text)
	print("START_UI_CHECK ", "PASS " if ok else "FAIL ", text)

func settle(count: int = 3) -> void:
	for _i in range(count): await get_tree().process_frame

func named(control_name: String) -> Control:
	return Computer.content.find_child(control_name, true, false) as Control

func choice_ids(option: OptionButton) -> Array[String]:
	var ids: Array[String] = []
	for i in range(option.item_count): ids.append(str(option.get_item_metadata(i)))
	return ids

func press(option: OptionButton, id: String) -> void:
	for i in range(option.item_count):
		if str(option.get_item_metadata(i)) == id:
			option.select(i)
			option.item_selected.emit(i)
			return

func visible_button(node: Node, text: String) -> Button:
	for child in node.get_children():
		if child is Button and child.text == text and child.is_visible_in_tree(): return child
		var nested := visible_button(child, text)
		if nested != null: return nested
	return null

func busy(value: bool, post: bool = false) -> void:
	CareerBridge.active_post = post
	CareerBridge.busy = value
	CareerBridge.busy_changed.emit(value)

func inspect_layout(label: String) -> void:
	var visible := get_viewport().get_visible_rect()
	check(visible.encloses(Computer.panel.get_global_rect()), label + " monitor stays inside viewport")
	check(Computer.content.get_combined_minimum_size().x <= Computer.scroll.size.x + 1, label + " no horizontal overflow")
	check(Computer.scroll.size.y >= 250, label + " body has usable scroll height")
	check(Computer.taskbar.get_parent().get_global_rect().end.y <= visible.end.y, label + " taskbar remains reachable")
	var start_button := visible_button(Computer.content, "开始这段生涯")
	if start_button:
		Computer.scroll.scroll_vertical = int(Computer.content.size.y)
		await settle()
		check(Computer.scroll.get_global_rect().encloses(start_button.get_global_rect()), label + " creation action reachable by scrolling")
		Computer.scroll.scroll_vertical = 0
		await settle()

func capture_page(filename: String) -> void:
	if not capture: return
	await settle(8)
	await RenderingServer.frame_post_draw
	var output := ProjectSettings.globalize_path("res://tests-output")
	DirAccess.make_dir_recursive_absolute(output)
	var result := get_viewport().get_texture().get_image().save_png(output.path_join(filename))
	check(result == OK, "capture " + filename)

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args():
		push_error("Start UI checks require --no-service to keep saves isolated")
		get_tree().quit(2)
		return
	capture = "--start-capture" in OS.get_cmdline_user_args()
	var fixture_path := "res://tests/start_options_fixture.json"
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--options-fixture="): fixture_path = argument.trim_prefix("--options-fixture=")
	fixture = JSON.parse_string(FileAccess.get_file_as_string(fixture_path))
	for era in fixture: fixture[era] = TeamDrawFixture.upgrade_options(fixture[era])
	CareerBridge.context = {
		"date":"2026-10-01", "player":{"id":"existing-fixture-player", "name":"Existing EP", "role":"rifle"},
		"team":{"id":"existing-fixture-team", "name":"既有生涯战队", "players":[], "roster":[]},
		"start":{"player":"Existing EP", "date":"2026-10-01", "can_continue":true},
		"calendar":{"revision":71}, "avatar":{"appearance":Avatar.DEFAULTS.duplicate()},
		"settings":{"settings":{}}, "personal":{"attributes":{"aim":65}, "attr_points":1, "growth_allowed":true},
		"ladder":{"maps":["dust2", "mirage"], "lobby":null, "history":[]}, "inbox":[], "stories":[]
	}
	CareerBridge.connected = true
	CareerBridge.endpoint = ""
	CareerBridge.clock_held = true
	actor = preload("res://scripts/chicken_player.gd").new()
	add_child(actor)
	actor.set_physics_process(false)
	actor.enabled = false
	var original_context := JSON.stringify(CareerBridge.context)
	var original_actor: Dictionary = actor.appearance.duplicate(true)
	get_window().content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	get_window().content_scale_aspect = Window.CONTENT_SCALE_ASPECT_IGNORE
	get_window().content_scale_size = Vector2i(1280, 720)
	get_window().size = Vector2i(1280, 720)
	await settle()
	Computer.open_app("start", "bedroom")
	await settle()
	check(Computer.screen.visible and not Phone.screen.visible and Computer.career_start.page == "welcome", "welcome exclusively opens workstation")
	check(visible_button(Computer.content, "继续这段生涯") != null and visible_button(Computer.content, "开始新生涯") != null, "welcome offers continue and new career")
	await inspect_layout("welcome 1280x720")
	await capture_page("start_welcome_1280.png")
	visible_button(Computer.content, "开始新生涯").pressed.emit()
	check(Computer.career_start.page == "create", "new career button opens creation wizard")
	for era in fixture: Computer.career_start.options_by_era[era] = fixture[era].duplicate(true)
	Computer.career_start.options = fixture["2026"].duplicate(true)
	Computer.career_start.attribute_draw.loaded["2026"] = true
	Computer.career_start.attribute_draw.sessions["2026"] = completed_draw_fixture("2026")
	Computer._rebuild()
	await settle()
	for id in ["street", "academy", "prodigy"]:
		var origin := named("CareerOrigin_" + id) as Button
		check(origin == null, "removed origin is absent: " + id)
	check(Computer.career_start.draft.origin == "attribute_draw", "self-created career uses attribute draw origin")
	check(named("CareerDrawDifficulty") == null, "three difficulties removed from team draw opening")
	for axis in DRAW_AXES: check(named("CareerCollected_" + str(axis.id)) != null, "seven collected-ability controls present: " + str(axis.id))
	check(JSON.stringify(CareerBridge.context) == original_context, "attribute and new-career drafts never mutate server projection")
	check(Computer.career_start.avatar.creation_mode and named("AppearanceEditor") == null and named("CareerStartCreate") == null, "ability page cannot edit appearance or create directly")
	Computer.career_start.avatar.set_value("body_color", "eeccdd")
	check(actor.appearance == original_actor, "embedded appearance leaves existing actor unchanged")
	var name_field := named("CareerStartName") as LineEdit
	name_field.grab_focus()
	for keycode in [KEY_E, KEY_P]:
		var event := InputEventKey.new()
		event.physical_keycode = keycode
		event.keycode = keycode
		event.unicode = 101 if keycode == KEY_E else 112
		event.pressed = true
		Phone._input(event)
		Computer._input(event)
		get_viewport().push_input(event)
		event = event.duplicate()
		event.pressed = false
		get_viewport().push_input(event)
		await settle()
		check(Computer.screen.visible and not Phone.screen.visible, "typing letter does not close or open device: " + char(keycode))
	check(name_field.text.ends_with("ep") and Computer.career_start.draft.name.ends_with("ep"), "native text input reaches new-career draft")
	var preserved_name := name_field.get_instance_id()
	Computer._context_changed()
	check(named("CareerStartName").get_instance_id() == preserved_name, "context poll keeps focused creation controls alive")
	get_viewport().gui_release_focus()
	var club_field := named("CareerStartClub") as LineEdit
	club_field.text = "EP Fixture Club"
	club_field.text_changed.emit(club_field.text)
	check(Computer.career_start.draft.org == "EP Fixture Club", "club text reaches draft")
	var name_font: Font = name_field.get_theme_font("font")
	Computer.career_start.next_step()
	await settle()
	check(Computer.career_start.page == "appearance" and named("AppearanceEditor") != null, "completed opening requires next step for appearance")
	Computer.career_start.ask_create()
	check(is_instance_valid(Computer.career_start.confirmation) and Computer.career_start.confirmation.visible, "complete draft opens review confirmation before replacement")
	if is_instance_valid(Computer.career_start.confirmation): Computer.career_start.confirmation.hide()
	check(not Computer.career_start.submitting and CareerBridge.queued_command.is_empty(), "canceling confirmation does not submit a career")
	var rounded := PhoneUI.font()
	print("START_FONT ", JSON.stringify({"class":rounded.get_class(), "family":rounded.get_font_name(), "style":rounded.get_font_style_name(), "bytes":rounded.data.size() if rounded is FontFile else 0}))
	check(rounded is FontFile and rounded.data.size() > 1000000, "bundled rounded FontFile actually loads")
	var chinese_covered := true
	for character in "你的职业生涯小鸡羽毛俱乐部圆润字体":
		chinese_covered = chinese_covered and rounded.has_char(character.unicode_at(0))
	check(chinese_covered, "rounded font covers visible Chinese labels")
	check(name_font == rounded, "new career text input uses rounded font")
	await inspect_layout("create 1280x720")
	await capture_page("start_create_1280.png")
	if capture:
		Computer.scroll.scroll_vertical = int(Computer.content.size.y)
		await capture_page("start_avatar_1280.png")
		Computer.scroll.scroll_vertical = 0
		await settle()
	Computer.career_start.edit_selection()
	await settle()
	for era in ["2024", "2025", "2026"]:
		press(named("CareerStartEra") as OptionButton, era)
		Computer.career_start.change_mode("join")
		await settle()
		var teams: Array = fixture[era]["teams"]
		var team_option := named("CareerStartTeam") as OptionButton
		var expected_ids: Array[String] = []
		for team in teams: expected_ids.append(str(team["id"]))
		check(choice_ids(team_option) == expected_ids, "professional teams belong to chosen era " + era)
		check(Computer.career_start.team_id == expected_ids[0] and not Computer.career_start.player_id.is_empty(), "cached era automatically selects first professional roster " + era)
		press(team_option, str(teams[1]["id"]))
		await settle()
		var player_option := named("CareerStartPlayer") as OptionButton
		var expected_players: Array[String] = []
		for player in teams[1]["players"]: expected_players.append(str(player["player_id"]))
		check(choice_ids(player_option) == expected_players, "professional roster belongs to selected team and era " + era)
		press(player_option, expected_players[-1])
		check(Computer.career_start.team_id == str(teams[1]["id"]) and Computer.career_start.player_id == expected_players[-1], "stable team/player ids reach draft " + era)
		check(Computer.career_start.draft.role == str(teams[1]["players"][-1]["role"]), "selected professional player's original role reaches draft " + era)
	check(Computer.career_start.avatar.values()["body_color"] == "eeccdd", "era and mode rerenders preserve embedded avatar draft")
	check(JSON.stringify(CareerBridge.context) == original_context, "era and professional choices never modify existing career")
	Computer.career_start.change_mode("create")
	Computer.career_start.next_step()
	busy(true, false)
	Computer._rebuild()
	await settle()
	var create_button := visible_button(Computer.content, "开始这段生涯")
	check(create_button != null and not create_button.disabled, "creation action built during GET remains actionable")
	busy(false, false)
	check(not create_button.disabled, "GET completion does not leave new control disabled")
	busy(true, true)
	Computer._rebuild()
	create_button = visible_button(Computer.content, "开始这段生涯")
	check(create_button != null and create_button.disabled, "creation action built during POST is locked")
	busy(false, true)
	check(not create_button.disabled, "POST completion restores action built while busy")
	var gate := Computer._button(Computer.content, "Domain gate fixture", func(): pass)
	gate.disabled = true
	Computer._seal_actions()
	busy(true, false)
	busy(false, false)
	check(gate.disabled, "domain disabled gate survives request completion")
	Computer._rebuild()
	busy(true, false)
	Computer.career_start.create()
	var queued: Dictionary = CareerBridge.queued_command.duplicate(true)
	check(queued.get("path") == "/api/3d/start/create" and Computer.career_start.submitting, "create click queues once behind read-only sync")
	check(queued.get("body", {}).get("revision") == 71 and queued.get("body", {}).get("appearance", {}).get("body_color") == "eeccdd", "queued creation retains reviewable draft and revision")
	check(queued.get("body", {}).get("career", {}).get("draft_id") == "fixture-complete-2026" and not queued.get("body", {}).get("career", {}).has("difficulty"), "queued creation references completed team draw without difficulty")
	check(JSON.stringify(CareerBridge.context) == original_context, "queued creation intent has not modified existing career")
	check(not CareerBridge.command("/api/3d/avatar", {"appearance":Avatar.DEFAULTS}), "second concurrent intent is rejected with feedback")
	check(not CareerBridge.message.is_empty(), "rejected concurrent intent leaves visible message")
	CareerBridge.queued_command.clear()
	busy(false, false)
	Computer.career_start.finished("/api/3d/start/create", {"ok":false, "reason":"隔离测试没有发送到后台"})
	await settle()
	check(not Computer.career_start.submitting and Computer.career_start.notice.contains("隔离测试"), "rejected creation restores editable wizard with feedback")
	for scenario in [{"physical":Vector2i(1920,1080), "logical":Vector2i(1920,1080), "name":"create 1920x1080"}, {"physical":Vector2i(1920,1080), "logical":Vector2i(1280,720), "name":"create 150 percent scale"}]:
		get_window().content_scale_size = scenario.logical
		get_window().size = scenario.physical
		await settle(5)
		Computer._resize()
		Computer._rebuild()
		await settle()
		print("START_LAYOUT ", JSON.stringify({"name":scenario.name, "logical":str(get_viewport().get_visible_rect().size), "physical":str(get_window().size), "scale":str(get_viewport().get_final_transform().get_scale()), "content_min":str(Computer.content.get_combined_minimum_size()), "scroll":str(Computer.scroll.size)}))
		await inspect_layout(scenario.name)
	await capture_page("start_create_scale150.png")
	check(get_viewport().get_final_transform().get_scale().is_equal_approx(Vector2.ONE * 1.5), "150 percent scenario uses actual viewport stretch")
	Computer._navigate("appearance")
	await settle()
	Computer.appearance.set_value("body_color", "aaccee")
	check(actor.appearance["body_color"] == "aaccee", "existing-career avatar applies live outside creation wizard")
	var appearance_model_id: int = Computer.appearance.preview_model.get_instance_id()
	Computer._context_changed()
	check(Computer.appearance.preview_model.get_instance_id() == appearance_model_id, "appearance context poll preserves live editor")
	await inspect_layout("appearance 150 percent scale")
	await capture_page("appearance_scale150.png")
	Computer.appearance.reset()
	Phone.present("settings")
	await settle()
	var phone_edit: LineEdit = Phone.content.find_child("DeviceSetting_steam_exe", true, false)
	check(phone_edit != null, "phone settings exposes native editable field")
	if phone_edit != null:
		phone_edit.grab_focus()
		var event := InputEventKey.new()
		event.physical_keycode = KEY_P
		event.pressed = true
		Phone._input(event)
		Computer._input(event)
		check(Phone.screen.visible and not Computer.screen.visible, "typing P in phone setting does not close or swap device")
	get_viewport().gui_release_focus()
	busy(true, false)
	Phone._rebuild()
	var phone_read := Phone.content.find_child("DeviceSettingsSave", true, false) as Button
	check(not phone_read.disabled, "phone action created during read sync remains available")
	busy(false, false)
	check(not phone_read.disabled, "phone read completion leaves control available")
	busy(true, true)
	Phone._rebuild()
	var phone_write := Phone.content.find_child("DeviceSettingsSave", true, false) as Button
	check(phone_write.disabled, "phone action created during write sync is locked")
	busy(false, true)
	check(not phone_write.disabled, "phone write completion restores newly created action")
	Phone.close_phone()
	Computer.close_computer()
	Phone.selected_mail = "old-career-mail"
	Phone.selected_mail_detail = {"body":"old career mail"}
	Phone.selected_player = {"player_id":"old-career-player"}
	Phone.selected_event = {"id":"old-career-event"}
	Phone.selected_contact = "old-career-player"
	Phone.news_article = {"title":"old career article"}
	Phone.detail = {"id":"old-career-event"}
	Phone.history = ["mail", "player"]
	Phone.page_scroll = {"mail":60}
	Phone.pending_detail_path = "/api/3d/player?id=old-career-player"
	Phone.reset_career_views()
	check(Phone.selected_mail.is_empty() and Phone.selected_mail_detail.is_empty() and Phone.selected_player.is_empty() and Phone.selected_event.is_empty(), "career reset clears phone cached detail selections")
	check(Phone.selected_contact.is_empty() and Phone.news_article.is_empty() and Phone.detail.is_empty() and Phone.history.is_empty() and Phone.page_scroll.is_empty(), "career reset clears old phone conversation selection navigation and article caches")
	check(Phone.pending_detail_path.is_empty(), "career reset invalidates old phone request intent")
	CareerBridge.queued_command.clear()
	var completions: Array = []
	CareerBridge.command_finished.connect(func(path: String, result: Dictionary): completions.append({"path":path, "result":result.duplicate(true)}))
	CareerBridge.active_path = "/api/3d/context"
	CareerBridge.active_body = {}
	busy(true, false)
	Computer.career_start.create()
	check(Computer.career_start.submitting and not CareerBridge.queued_command.is_empty(), "transport fixture queues creation behind GET")
	CareerBridge._response(HTTPRequest.RESULT_TIMEOUT, 0, PackedStringArray(), "{}".to_utf8_buffer())
	check(not Computer.career_start.submitting and CareerBridge.queued_command.is_empty(), "GET timeout completes discarded creation and clears pending UI")
	check(completions.size() == 2 and completions[-1]["path"] == "/api/3d/start/create" and completions[-1]["result"].get("not_sent", false), "queued timeout reports operation was not sent")
	check(JSON.stringify(CareerBridge.context) == original_context, "timeout cannot mutate existing career projection")
	completions.clear()
	Computer.appearance.saving = true
	Computer.appearance.dirty = true
	Computer.appearance.draft = Avatar.DEFAULTS.duplicate()
	Computer.appearance.draft["body_color"] = "abbccd"
	CareerBridge.connected = true
	CareerBridge.active_path = "/api/3d/avatar"
	CareerBridge.active_body = {"appearance":Computer.appearance.values()}
	busy(true, true)
	CareerBridge._response(HTTPRequest.RESULT_TIMEOUT, 0, PackedStringArray(), "{}".to_utf8_buffer())
	check(not Computer.appearance.saving and Computer.appearance.dirty and Computer.appearance.values()["body_color"] == "abbccd", "POST timeout releases avatar pending state and retains draft")
	check(completions.size() == 1 and completions[0]["result"].get("outcome_unknown", false) and completions[0]["result"].get("transport_failure", false), "write timeout reports uncertain outcome without retry")
	check(CareerBridge.queued_command.is_empty() and not CareerBridge.connected and not CareerBridge.busy, "write timeout leaves no silent retries or stuck busy state")
	completions.clear()
	Computer.appearance.saving = true
	CareerBridge.queued_command = {"path":"/api/3d/avatar", "body":{"appearance":Avatar.DEFAULTS.duplicate()}}
	CareerBridge._flush_queued()
	check(not Computer.appearance.saving and completions.size() == 1 and completions[0]["result"].get("not_sent", false), "disconnected queued flush completes unsent avatar and releases pending state")
	print("START_UI_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
