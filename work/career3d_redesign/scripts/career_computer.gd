extends CanvasLayer
## Desktop workstation. CareerBridge owns all ladder and scrim state.
const SharedPages = preload("res://scripts/device_pages.gd")
const SharedData = preload("res://scripts/device_page_data.gd")
const UI = preload("res://scripts/computer_ui.gd")
const Visuals = preload("res://scripts/computer_visuals.gd")
const Business = preload("res://scripts/computer_business.gd")
const News = preload("res://scripts/computer_news.gd")
const PageProjection = preload("res://scripts/device_projection.gd")
const CareerMatch = preload("res://scripts/computer_career_match.gd")
const DeviceSettings = preload("res://scripts/device_settings.gd")
const Tactics = preload("res://scripts/computer_tactics.gd")
const Controls = preload("res://scripts/computer_controls.gd")
const CareerStart = preload("res://scripts/computer_start.gd")
const SaveManager = preload("res://scripts/computer_saves.gd")
const Appearance = preload("res://scripts/appearance_customization.gd")
const LadderRoom = preload("res://scripts/computer_ladder.gd")
const CustomRoom = preload("res://scripts/computer_custom.gd")
const RTSRoom = preload("res://scripts/computer_rts.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")
const MatchReport = preload("res://scripts/career_match_report.gd")
const EventFlow = preload("res://scripts/career_event_flow.gd")
const CaseRoom = preload("res://scripts/computer_case.gd")
const SkinBundles = preload("res://scripts/computer_skin_bundles.gd")
const ActionFeedback = preload("res://scripts/device_action_feedback.gd")
const Fmt = preload("res://scripts/ui_format.gd")
const Kit = preload("res://scripts/ui_kit.gd")
const LIGHT := UI.INK
const MUTED := UI.MUTED
var PAGES: Dictionary:
	get: return SharedData.page_titles(false)
var APPS: Array:
	get: return SharedData.apps(false)
var screen: Control
var panel: PanelContainer
var stand: PanelContainer
var pace_footer: VBoxContainer
var content: VBoxContainer
var scroll: ScrollContainer
var title: Label
var status: Label
var clock: Label
var back_button: Button
var active_page := "desktop"
var location := "bedroom"
var detail: Dictionary = {}
var page_details: Dictionary = {}
var report: Dictionary = {}
var page_reports: Dictionary = {}
var history: Array[String] = []
var page_scroll: Dictionary = {}
var action_buttons: Array[Button] = []
var opponent_id := ""
var scrim_date := ""
var scrim_map := ""
var scrim_side := "ct"
var pending_detail_path := ""
var rendered_context := ""
var notice := ""
var action_feedback: Control
var app_toolbar: HBoxContainer
var taskbar: HBoxContainer
var taskbar_buttons: Dictionary = {}
var desktop_wallpaper: Control
var desktop_shortcuts: MarginContainer
var market_tab := "market"
var selected_skin: Dictionary = {}
var selected_mail: Dictionary = {}
var profile_tab := "overview"
var position_preview_roles: Dictionary = {}
var market_search := ""
var market_weapon := ""
var market_rarity := ""
var selected_date := ""
var calendar_month := ""
var cs2_status: Dictionary = {}
var cs2_poll := 0.0
var ladder_command_sender: Callable
var skin_textures: Dictionary = {}
var detail_intent_serial := 0
var pending_detail_intent := -1
var built_while_busy := false
var abandon_lobby_id := ""
var business = Business.new()
var news = News.new()
var player_tab := "overview"
var player_span := "season"
var player_page := 1
var events_tab := "calendar"
var players_data: Dictionary = {}
var players_search := ""
var players_page := 1
var pending_players_path := ""
var players_query := ""
var match_center = CareerMatch.new()
var device_settings = DeviceSettings.new()
var tactics = Tactics.new()
var controls = Controls.new()
var career_start = CareerStart.new()
var save_manager = SaveManager.new()
var appearance = Appearance.new()
var ladder_room = LadderRoom.new()
var custom_room = CustomRoom.new()
var rts_room = RTSRoom.new()
var case_room = CaseRoom.new()
var skin_bundles = SkinBundles.new()
## Optional local RTS renderer supplied by its module; no career write fallback.
var rts_render: Callable
var repaint_pending := false

func _ready() -> void:
	Locale.changed.connect(_language_changed)
	business.attach(self)
	news.attach(self)
	match_center.attach(self)
	tactics.attach(self)
	controls.attach(self)
	career_start.attach(self)
	save_manager.attach(self)
	ladder_room.attach(self)
	custom_room.attach(self)
	rts_room.attach(self)
	case_room.attach(self)
	layer = 31
	process_mode = Node.PROCESS_MODE_ALWAYS
	screen = Control.new()
	screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(screen)
	var dim := ColorRect.new()
	dim.color = Color(0.08, 0.13, 0.10, 0.55)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	screen.add_child(dim)
	stand = PanelContainer.new()
	stand.name = "MonitorStand"
	stand.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	stand.add_theme_stylebox_override("panel", UI.style(Color("bdc6b8"), 0, 8, Color("9cae9f")))
	screen.add_child(stand)
	panel = PanelContainer.new()
	panel.name = "ComputerMonitor"
	panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	panel.add_theme_stylebox_override("panel", UI.style(Color("e3e7db"), 10, 18, Color("bdc6b8")))
	screen.add_child(panel)
	var display := PanelContainer.new()
	display.add_theme_stylebox_override("panel", UI.style(UI.CREAM, 0, 12))
	panel.add_child(display)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 0)
	display.add_child(layout)
	var menu := PanelContainer.new()
	menu.add_theme_stylebox_override("panel", UI.style(UI.PAPER, 10, 8))
	layout.add_child(menu)
	var menubar := HBoxContainer.new()
	menubar.add_theme_constant_override("separation", 12)
	menu.add_child(menubar)
	UI.transparent(UI.compact(UI.button(menubar, "Career", _desktop)))
	var place_label := _label(menubar, Locale.source("device.club_workstation"), 12, MUTED)
	place_label.name = "ComputerLocation"
	place_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var close := UI.compact(UI.button(menubar, Locale.source("device.leave_computer_e_esc"), close_computer))
	UI.transparent(close)
	app_toolbar = HBoxContainer.new()
	app_toolbar.name = "ComputerAppToolbar"
	app_toolbar.add_theme_constant_override("separation", 10)
	layout.add_child(app_toolbar)
	back_button = UI.compact(UI.button(app_toolbar, Locale.source("device.back_2"), _back))
	UI.transparent(back_button)
	back_button.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	title = _label(app_toolbar, Locale.source("page.desktop"), 16)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	var close_app := UI.compact(UI.button(app_toolbar, "×", _desktop))
	UI.transparent(close_app)
	# Chrome rows stay slim so pages keep their full working height.
	for chrome in [back_button, close_app]: chrome.custom_minimum_size.y = 30
	var stage := Control.new()
	stage.name = "ComputerStage"
	stage.size_flags_vertical = Control.SIZE_EXPAND_FILL
	stage.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	layout.add_child(stage)
	desktop_wallpaper = Visuals.wallpaper()
	stage.add_child(desktop_wallpaper)
	scroll = ScrollContainer.new()
	scroll.name = "ComputerScroll"
	scroll.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	scroll.offset_left = 23
	scroll.offset_right = -23
	scroll.offset_top = 20
	scroll.offset_bottom = -18
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	stage.add_child(scroll)
	content = VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 12)
	scroll.add_child(content)
	scroll.resized.connect(_layout_desktop)
	pace_footer = VBoxContainer.new()
	layout.add_child(pace_footer)
	# Desktop shortcuts belong to the monitor chrome, not the scrolling page.
	# The stage takes spare height; this dock stays just above the taskbar.
	desktop_shortcuts = MarginContainer.new()
	desktop_shortcuts.name = "ComputerDesktopDock"
	desktop_shortcuts.add_theme_constant_override("margin_left", 23)
	desktop_shortcuts.add_theme_constant_override("margin_right", 23)
	desktop_shortcuts.add_theme_constant_override("margin_top", 8)
	desktop_shortcuts.add_theme_constant_override("margin_bottom", 12)
	layout.add_child(desktop_shortcuts)
	var utilities := HFlowContainer.new()
	utilities.name = "ComputerDesktopShortcuts"
	utilities.add_theme_constant_override("h_separation", 8)
	utilities.add_theme_constant_override("v_separation", 8)
	desktop_shortcuts.add_child(utilities)
	for item in [["management", Locale.source("page.management")], ["training", Locale.source("page.training")], ["assistance", Locale.source("page.assistance")], ["rankings", Locale.source("page.rankings")], ["workshop", Locale.source("page.workshop")], ["appearance", Locale.source("page.appearance")], ["start", Locale.source("device.career_setup")], ["saves", Locale.source("page.saves")]]:
		var shortcut := UI.compact(_button(utilities, item[1], _navigate.bind(item[0]), false))
		shortcut.add_theme_stylebox_override("normal", UI.raised(Color(1, 0.996, 0.973, 0.92), 12, 10))
	var status_margin := MarginContainer.new()
	status_margin.add_theme_constant_override("margin_left", 23)
	status_margin.add_theme_constant_override("margin_right", 23)
	status_margin.add_theme_constant_override("margin_top", 0)
	status_margin.add_theme_constant_override("margin_bottom", 0)
	layout.add_child(status_margin)
	status = _label(status_margin, "", 12, MUTED)
	status.custom_minimum_size.y = 18
	status.max_lines_visible = 2
	var taskbar_surface := PanelContainer.new()
	taskbar_surface.add_theme_stylebox_override("panel", UI.style(UI.PAPER, 8, 8))
	layout.add_child(taskbar_surface)
	taskbar = HBoxContainer.new()
	taskbar.name = "ComputerTaskbar"
	taskbar.add_theme_constant_override("separation", 4)
	taskbar_surface.add_child(taskbar)
	var home := UI.compact(UI.button(taskbar, Locale.source("page.desktop"), _desktop))
	UI.transparent(home)
	home.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	for app in APPS:
		taskbar_buttons[str(app["page"])] = _icon_button(taskbar, str(app["icon"]), str(app["label"]), _navigate.bind(str(app["page"])), Vector2(36, 36))
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	taskbar.add_child(spacer)
	UI.transparent(UI.compact(UI.button(taskbar, Locale.source("device.my_phone"), _open_phone)))
	clock = _label(taskbar, "", 12, MUTED)
	clock.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	clock.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	clock.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	clock.autowrap_mode = TextServer.AUTOWRAP_OFF
	action_feedback = ActionFeedback.new()
	action_feedback.top_inset = 82.0
	panel.add_child(action_feedback)
	CareerBridge.changed.connect(_context_changed)
	CareerBridge.busy_changed.connect(_busy_changed)
	CareerBridge.status_changed.connect(_update_status)
	CareerBridge.command_finished.connect(_finished)
	CareerBridge.wake_requested.connect(_wake)
	CareerBridge.growth_changed.connect(_growth_changed)
	get_viewport().size_changed.connect(_resize)
	_resize()
	screen.visible = false

func _resize() -> void:
	var size := get_viewport().get_visible_rect().size
	var stretch := get_viewport().get_final_transform().get_scale().abs()
	stretch.x = maxf(stretch.x, 0.001)
	stretch.y = maxf(stretch.y, 0.001)
	var physical := size * stretch
	var width := maxf(320, minf(physical.x * .88, physical.x - 36))
	var height := maxf(260, minf(physical.y * .88, physical.y - 62))
	panel.pivot_offset = Vector2(width, height) / 2.0
	panel.scale = Vector2.ONE / stretch
	panel.offset_left = -width / 2
	panel.offset_right = width / 2
	panel.offset_top = -height / 2 - 14
	panel.offset_bottom = height / 2 - 14
	stand.offset_left = -110
	stand.offset_right = 110
	stand.offset_top = height / stretch.y / 2 - 22
	stand.offset_bottom = height / stretch.y / 2 + 22
	stand.pivot_offset = Vector2(110, 22)
	stand.scale = Vector2.ONE / stretch
	case_room.resize()
	_layout_desktop()

func _layout_desktop() -> void:
	if not is_instance_valid(content) or not is_instance_valid(scroll): return
	var desktop := content.get_node_or_null("ComputerDesktop") as BoxContainer
	if desktop == null: return
	var compact := scroll.size.x < 720
	desktop.vertical = compact
	var greeting := desktop.get_node("ComputerDesktopGreeting") as Control
	greeting.visible = true
	var agenda := desktop.get_node("ComputerDesktopAgenda") as Control
	agenda.size_flags_horizontal = Control.SIZE_EXPAND_FILL if compact else Control.SIZE_SHRINK_END

func present(place: String = "bedroom") -> void:
	if Travel.busy or CareerBridge.sleeping:
		return
	Travel.close_menu()
	location = place if place in ["bedroom", "club", "lan", "major"] else "bedroom"
	var phone := get_node_or_null("/root/Phone")
	if phone and phone.screen.visible:
		phone.close_phone(false)
	screen.visible = true
	UI.device_open(self, "computer")
	if StartGate.requires_creation() and active_page not in ["start", "saves"]:
		active_page = "start"
	if location != "club" and active_page == "scrim":
		active_page = "desktop"
	if active_page == "saves":
		save_manager.needs_refresh = true
		save_manager.requested_once = false
	_rebuild()
	call_deferred("_focus_first")
	call_deferred("_advance_ai")

func open_app(page: String, place: String = "club") -> void:
	if Travel.busy:
		return
	active_page = page if PAGES.has(page) else "desktop"
	present(place)

func _fetch_device_settings() -> void:
	device_settings.fetch()

func _fetch_tactics() -> void:
	tactics.fetch()

func _fetch_start_options() -> void:
	career_start.fetch()

func reset_career_views() -> void:
	match_center.pace.flow.reset()
	_clear_action_feedback()
	detail_intent_serial += 1
	pending_detail_path = ""
	pending_players_path = ""
	players_query = ""
	selected_date = ""
	calendar_month = ""
	opponent_id = ""
	scrim_date = ""
	notice = ""
	rendered_context = ""
	page_details.clear()
	page_reports.clear()
	detail.clear()
	report.clear()
	selected_mail.clear()
	selected_skin.clear()
	case_room.reset()
	players_data.clear()
	cs2_status.clear()
	ladder_room.reset()
	custom_room.reset()
	rts_room.reset()
	page_scroll.clear()
	position_preview_roles.clear()
	history.clear()
	match_center = CareerMatch.new()
	match_center.attach(self)
	business = Business.new()
	business.attach(self)
	news = News.new()
	news.attach(self)
	controls = Controls.new()
	controls.attach(self)
	appearance.draft.clear()
	CareerBridge.growth_clear()

func _collect_career_result(id: String) -> void:
	match_center.command("collect", {"match_id":id})

func close_computer(release: bool = true) -> void:
	if screen == null:
		return
	if StartGate.requires_creation():
		StartGate.remind()
		return
	if is_instance_valid(rts_room.session) and not rts_room.close_session(): return
	_clear_action_feedback()
	page_scroll[active_page] = scroll.scroll_vertical
	detail_intent_serial += 1
	match_center.pace.pause(false)
	screen.visible = false
	if release:
		UI.device_closed(self)

func _navigate(page: String, push: bool = true) -> void:
	if page not in ["career_match", "quick", "rts"]: match_center.pace.pause(false)
	if StartGate.requires_creation() and page not in ["start", "saves"]:
		StartGate.remind()
		return
	if active_page != page and is_instance_valid(action_feedback): action_feedback.clear_notice()
	detail_intent_serial += 1
	page_scroll[active_page] = scroll.scroll_vertical
	if active_page in ["ladder", "scrim", "custom"]:
		page_reports[active_page] = report
	if active_page != page and push:
		history.append(active_page)
	active_page = page
	if page == "saves":
		save_manager.needs_refresh = true
		save_manager.requested_once = false
	report = page_reports.get(page, {}) if page in ["ladder", "scrim", "custom"] else {}
	if page in ["team", "player", "event", "match"]:
		detail = page_details.get(page, {})
	notice = ""
	_rebuild()
	call_deferred("_focus_first")
	if page == "ladder":
		call_deferred("_advance_ai")
		call_deferred("_poll_cs2_status")
	elif page == "custom":
		custom_room.context_changed()
		if custom_room.catalog.is_empty(): custom_room.fetch_catalog()
	elif page == "saves":
		save_manager.fetch(true)

func _desktop() -> void:
	history.clear()
	_navigate("desktop", false)

func _back() -> void:
	if active_page == "news" and news.back():
		return
	if not report.is_empty() and active_page in ["ladder", "scrim", "custom"]:
		report = {}
		page_reports[active_page] = {}
		_rebuild()
	elif active_page == "market" and not selected_skin.is_empty():
		selected_skin = {}
		_rebuild()
	elif active_page == "mail" and not selected_mail.is_empty():
		selected_mail = {}
		_rebuild()
	elif not history.is_empty():
		_navigate(history.pop_back(), false)
	else:
		_desktop()

func _label(parent: Node, value: String, size: int = 17, color: Color = LIGHT) -> Label:
	# The live match presentation is a dense broadcast table sized to fit one
	# monitor without scrolling; it keeps its exact type sizes.
	if active_page in ["career_match", "quick", "battle"] and match_center.is_presenting():
		return UI.label_exact(parent, value, size, color)
	return UI.label(parent, value, size, color)

func _button(parent: Node, value: String, callback: Callable, write: bool = true) -> Button:
	var button := UI.button(parent, value, callback, true)
	if write:
		action_buttons.append(button)
		# Form rendering describes domain availability, not a transient poll.
		# _seal_actions stores it after each page has applied its own gates.
		button.set_meta("career_gate_disabled", false)
	return button

func _icon_button(parent: Node, kind: String, caption: String, callback: Callable, dimensions: Vector2 = Vector2(64, 64)) -> Button:
	var node := UI.button(parent, "", callback)
	node.custom_minimum_size = dimensions
	node.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	node.tooltip_text = caption
	node.set_meta("focus_key", caption)
	if dimensions.x <= 40:
		UI.transparent(node)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	node.add_child(center)
	var icon := Visuals.icon(kind, Vector2(28, 28) if dimensions.x >= 56 else (Vector2(25, 25) if dimensions.x >= 40 else Vector2(20, 20)))
	icon.mouse_filter = Control.MOUSE_FILTER_IGNORE
	center.add_child(icon)
	return node

func _open_phone(page: String = "home") -> void:
	close_computer(false)
	Phone.present(page)

func _open_phone_mail(id: String) -> void:
	_open_phone("mail")
	Phone._open_mail(id)

func _device_command(path: String, body: Dictionary) -> void:
	var payload := body.duplicate(true)
	payload["revision"] = int(CareerBridge.context.get("calendar", {}).get("revision", 0))
	notice = ""
	if not _command(path, payload):
		notice = CareerBridge.message
	_update_status()

func show_action_feedback(message: String, kind: String = "success", duration: float = 4.0, operation: String = "") -> void:
	if is_instance_valid(action_feedback) and screen.visible:
		action_feedback.show_message(message, kind, duration, operation)

func _clear_action_feedback() -> void:
	if is_instance_valid(action_feedback): action_feedback.clear_notice(true)

func _command(path: String, body: Dictionary = {}) -> bool:
	var accepted := CareerBridge.command(path, body)
	if is_instance_valid(action_feedback) and screen.visible:
		action_feedback.track_request(path, accepted, CareerBridge.message)
	return accepted

func _commit_growth() -> bool:
	var accepted := CareerBridge.growth_commit()
	if is_instance_valid(action_feedback) and screen.visible:
		action_feedback.track_request("/api/3d/attr", accepted, CareerBridge.message)
	return accepted

func _tabs(parent: Node, choices: Array, selected: String, callback: Callable) -> void:
	# Segmented control: one tinted track, the selected segment lifts out of it.
	var track := PanelContainer.new()
	track.name = "SegmentedTabs"
	track.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	track.add_theme_stylebox_override("panel", UI.style(Color("ebe7da"), 4, 12))
	parent.add_child(track)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 4)
	track.add_child(row)
	for choice in choices:
		var button := _button(row, str(choice["label"]), callback.bind(str(choice["id"])), false)
		UI.transparent(button)
		button.add_theme_font_size_override("font_size", 15)
		button.custom_minimum_size.y = 36
		button.set_meta("focus_key", str(choice["id"]))
		for state in ["font_color", "font_hover_color", "font_focus_color"]:
			button.add_theme_color_override(state, UI.MUTED)
		if str(choice["id"]) == selected:
			button.add_theme_stylebox_override("normal", UI.raised(UI.PAPER, 7, 9, Color(0, 0, 0, 0)))
			for state in ["font_color", "font_hover_color", "font_focus_color"]:
				button.add_theme_color_override(state, UI.INK)

func _quiet_row(parent: Node, left: String, right: String) -> void:
	var row := HBoxContainer.new()
	parent.add_child(row)
	_label(row, left, 14, MUTED)
	_label(row, right, 14).horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT

func _context_changed() -> void:
	custom_room.context_changed()
	if active_page == "market" and case_room.locked(): return
	if active_page in ["battle", "career_match", "quick"] and match_center.is_presenting():
		return
	if active_page == "settings" and device_settings.dirty:
		return
	if active_page in ["start", "appearance", "tactics", "management", "assistance", "training", "saves"]:
		return
	var focused := get_viewport().gui_get_focus_owner()
	if Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT) or focused is LineEdit or focused is TextEdit:
		repaint_pending = true
		return
	if screen.visible and rendered_context != PageProjection.signature(active_page, CareerBridge.context):
		page_scroll[active_page] = scroll.scroll_vertical
		_rebuild()

func _rebuild() -> void:
	var focused := get_viewport().gui_get_focus_owner()
	var focus_text := str(focused.text) if focused is Button and content.is_ancestor_of(focused) else ""
	var focus_key := str(focused.get_meta("stable_focus", "")) if focused is Button and content.is_ancestor_of(focused) else ""
	UI.clear(content)
	UI.clear(pace_footer)
	match_center.pace.footer(pace_footer)
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL if active_page == "desktop" else Control.SIZE_FILL
	content.add_theme_constant_override("separation", 6 if active_page in ["career_match", "quick", "tactics"] or (active_page == "battle" and match_center.is_presenting()) else 12)
	action_buttons.clear()
	built_while_busy = CareerBridge.busy
	title.text = str(PAGES.get(active_page, Locale.source("page.desktop")))
	app_toolbar.visible = active_page != "desktop"
	desktop_wallpaper.visible = active_page == "desktop"
	desktop_shortcuts.visible = active_page == "desktop"
	var location_label := panel.find_child("ComputerLocation", true, false) as Label
	if location_label:
		location_label.text = {"club":Locale.source("device.club_workstation"), "lan":Locale.source("device.lan_player_computer"), "major":Locale.source("device.tournament_player_computer"), "bedroom":Locale.source("device.home_computer")}.get(location, Locale.source("device.home_computer"))
	back_button.disabled = active_page == "desktop"
	for page in taskbar_buttons:
		var task: Button = taskbar_buttons[page]
		if not is_instance_valid(task): continue
		# The running app is marked in the taskbar, like a real desktop.
		task.add_theme_stylebox_override("normal", UI.style(UI.MINT, 4, 9) if page == active_page else UI.style(Color.TRANSPARENT, 4, 9))
	rendered_context = PageProjection.signature(active_page, CareerBridge.context)
	_update_status()
	if CareerBridge.context.is_empty() and active_page != "desktop":
		_label(content, Locale.source("device.loading_your_career_this_page_will_be_available_once_connected"))
	else:
		match active_page:
			"desktop": _render_desktop()
			"battle": _battle()
			"career_match": match_center.render(content)
			"quick": match_center.render_quick(content)
			"settings":
				device_settings.render(self, content)
				_font_settings()
			"tactics": tactics.render(content)
			"start": career_start.render(content)
			"saves": save_manager.render(content)
			"appearance": appearance.render(self, content)
			"management", "training", "assistance", "rankings", "workshop": controls.render(active_page)
			"ladder": _ladder()
			"custom": custom_room.render(content)
			"rts":
				if rts_render.is_valid(): rts_render.call(content)
				else: _label(content, Locale.source("device.tactical_simulation_is_not_available_yet"), 18, MUTED)
			"scrim": _scrim()
			"events": _events()
			"team": _team()
			"player": _player()
			"event": _event()
			"match": _match()
			"market": _market()
			"profile": _profile()
			"mail": _mail()
			"calendar": _calendar()
			"operations": business.render_operations()
			"transfers": business.render_transfers()
			"news": news.render()
	_seal_actions()
	_layout_desktop()
	scroll.set_deferred("scroll_vertical", int(page_scroll.get(active_page, 0)))
	if not focus_key.is_empty():
		call_deferred("_restore_keyed_focus", focus_key)
	elif not focus_text.is_empty():
		call_deferred("_restore_focus", content, focus_text)

func _seal_actions() -> void:
	for button in action_buttons:
		if is_instance_valid(button):
			button.set_meta("career_gate_disabled", button.disabled)
	_busy_changed(CareerBridge.busy)

func _font_settings() -> void:
	var card := UI.card(content)
	_label(card, Locale.source("device.interface_font"), 18)
	var picker := OptionButton.new()
	picker.name = "UIFontChoice"
	UI.dark_options(picker)
	picker.add_item(Locale.source("device.rounded_font_2"))
	picker.add_item(Locale.source("device.system_sans_serif_2"))
	picker.select(0 if UI.Base.font_style == "rounded" else 1)
	card.add_child(picker)
	picker.item_selected.connect(func(index: int):
		UI.Base.choose_font("rounded" if index == 0 else "system", get_tree())
	)
	_label(card, Locale.source("device.fonts_are_provided_offline_changing_the_font_only_affects_display"), 12, MUTED)

func _render_desktop() -> void:
	var c := CareerBridge.context
	var desktop := BoxContainer.new()
	desktop.name = "ComputerDesktop"
	desktop.size_flags_vertical = Control.SIZE_EXPAND_FILL
	desktop.add_theme_constant_override("separation", 26)
	content.add_child(desktop)
	# 1. Applications: large labelled tiles, the same nine apps as the taskbar.
	var grid := GridContainer.new()
	grid.name = "ComputerDesktopIcons"
	grid.columns = 3
	grid.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	grid.add_theme_constant_override("h_separation", 14)
	grid.add_theme_constant_override("v_separation", 14)
	desktop.add_child(grid)
	var open_mail := 0
	for item in c.get("inbox", []):
		if item.get("status") == "open": open_mail += 1
	for app in APPS:
		var cell := VBoxContainer.new()
		cell.custom_minimum_size.x = 86
		cell.add_theme_constant_override("separation", 6)
		grid.add_child(cell)
		var tile := _icon_button(cell, str(app["icon"]), str(app["label"]), _navigate.bind(str(app["page"])), Vector2(64, 64))
		tile.add_theme_stylebox_override("normal", UI.raised(UI.PAPER, 0, 18))
		tile.add_theme_stylebox_override("hover", UI.style(Color("eef4ea"), 0, 18, Color("b9c9b8")))
		if str(app["page"]) == "mail" and open_mail > 0:
			var badge := PanelContainer.new()
			badge.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
			badge.offset_left = -14; badge.offset_right = 6; badge.offset_top = -6; badge.offset_bottom = 14
			badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
			badge.add_theme_stylebox_override("panel", UI.style(UI.BADGE, 0, 10))
			tile.add_child(badge)
			var number := _label(badge, str(open_mail), 11, UI.PAPER)
			number.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			number.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var caption := _label(cell, str(app["label"]), 13)
		caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		caption.autowrap_mode = TextServer.AUTOWRAP_OFF
		caption.mouse_filter = Control.MOUSE_FILTER_STOP
		caption.gui_input.connect(func(event: InputEvent):
			if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
				_navigate(str(app["page"]))
		)
	# 2. Today: who you are, the next match and the numbers that change daily.
	var greeting := VBoxContainer.new()
	greeting.name = "ComputerDesktopGreeting"
	greeting.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	greeting.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	greeting.add_theme_constant_override("separation", 12)
	desktop.add_child(greeting)
	var player: Dictionary = c.get("player", {}) if c.get("player") is Dictionary else {}
	var team: Dictionary = c.get("team", {}) if c.get("team") is Dictionary else {}
	var hour := floori(CareerBridge.clock_minutes / 60)
	var salutation := Locale.source("device.good_morning") if hour < 12 else (Locale.source("device.good_afternoon") if hour < 18 else Locale.source("device.good_evening"))
	var hello := _label(greeting, salutation + ("，" + str(player.get("name", "")) if not str(player.get("name", "")).is_empty() else ""), 28)
	hello.autowrap_mode = TextServer.AUTOWRAP_OFF
	hello.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	var who := HBoxContainer.new()
	who.add_theme_constant_override("separation", 8)
	greeting.add_child(who)
	if not str(team.get("name", "")).is_empty():
		TeamVisuals.badge(who, str(team.get("name", "")), 24)
		var team_line := _label(who, "%s · %s" % [team.get("name", ""), Phone.ROLES.get(str(player.get("role", "")), str(player.get("role", "")))], 14, MUTED)
		team_line.autowrap_mode = TextServer.AUTOWRAP_OFF
		team_line.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
		if team.has("rank"): Kit.chip(who, Locale.source("device.world_rank_value") % Fmt.integer(team.get("rank")), "green")
	var next_game := match_center.current_game()
	var next_card := PanelContainer.new()
	next_card.name = "DesktopNextMatch"
	next_card.add_theme_stylebox_override("panel", UI.raised(Color("24402f") if not next_game.is_empty() else UI.PAPER, 18, 16, Color("24402f") if not next_game.is_empty() else UI.LINE))
	greeting.add_child(next_card)
	var next_row := HBoxContainer.new()
	next_row.add_theme_constant_override("separation", 16)
	next_card.add_child(next_row)
	var next_words := VBoxContainer.new()
	next_words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	next_words.add_theme_constant_override("separation", 3)
	next_row.add_child(next_words)
	if next_game.is_empty():
		_label(next_words, Locale.source("device.next_match"), 12, MUTED)
		_label(next_words, Locale.source("device.no_matches_scheduled"), 19)
		_label(next_words, Locale.source("device.accept_event_invitations_in_your_mail_and_the_schedule_appears_here"), 13, MUTED)
		var invites := UI.compact(_button(next_row, Locale.source("device.view_invitations"), _navigate.bind("mail"), false))
		invites.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	else:
		var label_colour := Color("b8d4c2")
		_label(next_words, Locale.source("device.next_match_valuevalue") % [next_game.get("date", ""), Locale.source("device.today") if next_game.get("due", false) else ""], 12, label_colour)
		var versus := HBoxContainer.new()
		versus.add_theme_constant_override("separation", 10)
		next_words.add_child(versus)
		var vs_mark := _label(versus, "VS", 19, Color("e9c46a"))
		vs_mark.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
		vs_mark.autowrap_mode = TextServer.AUTOWRAP_OFF
		TeamVisuals.badge(versus, str(next_game.get("opponent", "")), 28)
		var opponent := _label(versus, str(next_game.get("opponent", Locale.source("device.tbd"))), 21, UI.PAPER)
		opponent.autowrap_mode = TextServer.AUTOWRAP_OFF
		var detail_line := "%s · BO%s" % [next_game.get("event", ""), Fmt.integer(next_game.get("best_of", 3))]
		var event_line := _label(next_words, detail_line, 13, label_colour)
		event_line.autowrap_mode = TextServer.AUTOWRAP_OFF
		event_line.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		var stage := str(next_game.get("stage", ""))
		if not stage.is_empty():
			_label(next_words, {"QF":Locale.source("device.quarterfinal"), "SF":Locale.source("device.semifinal"), "GF":Locale.source("device.final"), "R16":Locale.source("device.round_of_16")}.get(stage, stage), 12, label_colour)
		var go := _button(next_row, Locale.source("device.event_schedule"), _navigate.bind("career_match"), false)
		UI.compact(go)
		UI.primary(go)
		go.add_theme_stylebox_override("normal", UI.style(Color("e9c46a"), 12, 10))
		go.add_theme_stylebox_override("hover", UI.style(Color("f0d388"), 12, 10))
		for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
			go.add_theme_color_override(state, Color("24402f"))
		go.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var stats := HBoxContainer.new()
	stats.name = "DesktopStats"
	stats.add_theme_constant_override("separation", 12)
	greeting.add_child(stats)
	var personal := _personal()
	var finance: Dictionary = c.get("finance", {}) if c.get("finance") is Dictionary else {}
	var pocket: Dictionary = finance.get("pocket", {}) if finance.get("pocket") is Dictionary else {}
	var club: Dictionary = finance.get("club", {}) if finance.get("club") is Dictionary else {}
	var pocket_next = pocket.get("next_net")
	Kit.stat_tile(stats, UI, Locale.source("device.personal_balance"), Fmt.money_short(personal.get("personal_money", c.get("personal_money", c.get("money")))), (Locale.source("device.next_month") + Fmt.money(pocket_next, true)) if Fmt.is_number(pocket_next) else "", "green" if Fmt.is_number(pocket_next) and float(pocket_next) >= 0 else "red")
	var club_next = club.get("next_net")
	Kit.stat_tile(stats, UI, Locale.source("device.club_funds_2"), Fmt.money_short(personal.get("club_money", c.get("club_money", team.get("money")))), (Locale.source("device.next_month") + Fmt.money(club_next, true)) if Fmt.is_number(club_next) else "", "green" if Fmt.is_number(club_next) and float(club_next) >= 0 else "red")
	var points := int(c.get("attr_points", personal.get("attr_points", 0)))
	Kit.stat_tile(stats, UI, Locale.source("device.current_ability"), Fmt.score(personal.get("ability", player.get("ability"))), (Locale.source("device.value_points_to_assign") % points) if points > 0 else Locale.source("device.form_value") % ("%+.1f" % float(personal.get("form_delta")) if Fmt.is_number(personal.get("form_delta")) else "—"), "amber" if points > 0 else "")
	Kit.stat_tile(stats, UI, Locale.source("device.mail_awaiting_reply"), str(open_mail), Locale.source("device.value_in_total") % c.get("inbox", []).size(), "amber" if open_mail > 0 else "")
	var news_rows: Array = c.get("news", {}).get("rows", []) if c.get("news") is Dictionary else []
	if not news_rows.is_empty():
		var headline: Dictionary = news_rows[0]
		var news_button := _button(greeting, Locale.source("device.event_news") + str(headline.get("title", "")), _navigate.bind("news"), false)
		news_button.name = "DesktopHeadline"
		Kit.rich_row(news_button, UI, Locale.field(headline, "title"), Locale.source("device.latest") + str(headline.get("date", "")), "", Locale.source("device.news"), "blue", "news")
	# 3. Agenda: today's actionable shortcuts.
	var agenda := UI.card(desktop)
	var agenda_panel := agenda.get_parent() as PanelContainer
	agenda_panel.name = "ComputerDesktopAgenda"
	agenda_panel.size_flags_horizontal = Control.SIZE_SHRINK_END
	agenda_panel.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	agenda.custom_minimum_size.x = 262
	agenda.size_flags_horizontal = Control.SIZE_SHRINK_END
	agenda.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	agenda.add_theme_constant_override("separation", 6)
	Kit.section(agenda, UI, Locale.source("device.today_s_agenda"), str(c.get("date", "")), 17)
	var attendance := match_center.attendance()
	if not next_game.is_empty() and (attendance.get("planned", false) or next_game.get("due", false)):
		_label(agenda, "%s · %s" % [next_game.get("event", Locale.source("device.next_match")), attendance.get("display_name", Locale.source("device.match_venue_2"))], 13)
		var arrangement := _button(agenda, Locale.source("device.view_match_arrangements"), _navigate.bind("career_match"), false)
		arrangement.name = "DesktopAttendance"
		UI.primary(arrangement)
	for entry in [
		[Locale.source("device.training_and_setup_value_available_attribute_points") % Fmt.integer(c.get("attr_points", 0), "0"), "profile", "profile"],
		[Locale.source("device.training_and_matches"), "battle", "match"],
		[Locale.source("device.value_messages") % c.get("inbox", []).size(), "mail", "mail"],
		[Locale.source("device.open_calendar"), "calendar", "calendar"],
		[Locale.source("page.quick"), "quick", "trophy"],
		[Locale.source("page.tactics"), "tactics", "clipboard"],
		[Locale.source("device.cs2_and_skin_settings"), "settings", "settings"]]:
		var item := _button(agenda, str(entry[0]), _navigate.bind(str(entry[1])), false)
		Kit.rich_row(item, UI, str(entry[0]), "", "", "", "gray", str(entry[2]))
		item.custom_minimum_size.y = 42

func _battle() -> void:
	match_center.render(content)
	if match_center.is_presenting():
		return
	_label(content, Locale.source("page.battle"), 25)
	_label(content, Locale.source("device.start_with_a_good_match"), 14, MUTED)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 22)
	content.add_child(row)
	var ladder_box := UI.card(row)
	ladder_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_label(ladder_box, Locale.source("page.ladder"), 20)
	var player: Dictionary = _ladder_state().get("player", {})
	_label(ladder_box, "%s · Elo %s" % [CareerBridge.context.get("player", {}).get("name", ""), Fmt.integer(player.get("elo"))], 15)
	_label(ladder_box, Locale.source("device.career_character_ten_players_captain_picks_map_veto"), 13, MUTED)
	UI.primary(_button(ladder_box, Locale.source("device.open_ladder"), _navigate.bind("ladder"), false))
	var training := UI.card(row)
	training.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_label(training, Locale.source("page.scrim"), 20)
	_label(training, Locale.source("device.arrange_a_scrim_practise_teamwork_and_review_the_match_together"), 13, MUTED)
	if location == "club":
		_button(training, Locale.source("device.arrange_a_scrim"), _navigate.bind("scrim"), false)
	else:
		_label(training, Locale.source("device.arrange_a_scrim_at_the_club_workstation"), 14, MUTED)
	var custom := UI.card(content)
	_label(custom, Locale.source("device.custom_match_test_tactics"), 18)
	_label(custom, Locale.source("device.choose_both_five_player_squads_map_and_starting_side_play_as_one_player_or_obser"), 13, MUTED)
	var custom_entry := _button(custom, Locale.source("device.open_custom_match"), _navigate.bind("custom"), false)
	custom_entry.name = "ComputerOpenCustom"
	var rts_entry := _button(custom, Locale.source("device.rts_command_match"), Callable(rts_room, "open_custom"), false)
	rts_entry.name = "ComputerOpenRTS"
	_label(content, Locale.source("device.career_tournaments"), 18)
	_button(content, Locale.source("device.view_tournament_schedule"), _navigate.bind("events"), false)

func _personal() -> Dictionary:
	var value = CareerBridge.context.get("personal", {})
	return value if value is Dictionary else {}

func _profile_tab(value: String) -> void:
	profile_tab = value
	_rebuild()

func _growth_changed() -> void:
	if screen.visible and active_page == "profile":
		_rebuild()

func _position_preview_changed(index: int, page: String, selector: OptionButton) -> void:
	position_preview_roles[page] = str(selector.get_item_metadata(index))
	page_scroll[active_page] = scroll.scroll_vertical
	_rebuild()

func _position_preview(parent: Node, data: Dictionary, current_role: String, current_stats: Dictionary, page: String) -> void:
	var preview := preload("res://scripts/position_preview.gd").new()
	preview.role_selected.connect(func(role: String):
		position_preview_roles[page] = role
		page_scroll[active_page] = scroll.scroll_vertical
		_rebuild())
	var widget := preview.render(parent, data, current_role, current_stats, str(position_preview_roles.get(page, "")), Phone.ROLES, page, false)
	if widget != null: widget.set_meta("page_fragment", preview)

func _profile() -> void:
	var you: Dictionary = CareerBridge.context.get("player", {})
	var personal := _personal()
	var header := HBoxContainer.new()
	header.name = "ProfileHeader"
	header.add_theme_constant_override("separation", 16)
	content.add_child(header)
	var saved_avatar: Variant = CareerBridge.context.get("avatar", {})
	var look: Variant = saved_avatar.get("appearance", {}) if saved_avatar is Dictionary else {}
	Kit.chicken_badge(header, look if look is Dictionary else {}, 72)
	var heading := VBoxContainer.new()
	heading.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	heading.alignment = BoxContainer.ALIGNMENT_CENTER
	heading.add_theme_constant_override("separation", 2)
	header.add_child(heading)
	_label(heading, str(you.get("name", Locale.source("page.career"))), 25)
	var form = personal.get("form_delta")
	var form_text := Fmt.signed(form)
	_label(heading, Locale.source("device.value_age_value_role_ability_value_form_value") % [Phone.ROLES.get(you.get("role", ""), you.get("role", "")), Fmt.integer(you.get("age")), Fmt.score(personal.get("ability", you.get("ability"))), form_text], 14, MUTED)
	var club_name := str(CareerBridge.context.get("team", {}).get("name", ""))
	if not club_name.is_empty(): TeamVisuals.badge(header, club_name, 48)
	_tabs(content, [{"id":"overview", "label":Locale.source("device.overview")}, {"id":"growth", "label":Locale.source("device.attribute_training")}, {"id":"history", "label":Locale.source("device.match_statistics")}], profile_tab, _profile_tab)
	if profile_tab == "growth":
		var fragment := SharedPages.new()
		fragment.growth_adjusted.connect(CareerBridge.growth_adjust)
		fragment.growth_confirmed.connect(_commit_growth)
		fragment.growth_cleared.connect(CareerBridge.growth_clear)
		fragment.growth(content, personal, CareerBridge.growth_draft, CareerBridge.growth_remaining(), false, _button, CareerBridge.busy)
		return
	if profile_tab == "overview":
		var raw_playing = personal.get("playing_attributes", personal.get("attributes", {}))
		var playing: Dictionary = raw_playing if raw_playing is Dictionary else {}
		_position_preview(content, personal, str(you.get("role", "")), playing, "profile")
	var raw_stats = personal.get("stats", {})
	var stats: Dictionary = raw_stats if raw_stats is Dictionary else {}
	var metrics := HBoxContainer.new()
	metrics.name = "ProfileMetrics"
	metrics.add_theme_constant_override("separation", 12)
	content.add_child(metrics)
	for stat in [{"id":"rating", "label":"Rating", "format":"%.2f"}, {"id":"adr", "label":"ADR", "format":"%.1f"}, {"id":"kast", "label":"KAST", "format":"%.1f%%"}, {"id":"maps", "label":Locale.source("device.map"), "format":"%.0f"}]:
		var raw_amount = stats.get(str(stat["id"]))
		var has_amount: bool = typeof(raw_amount) in [TYPE_INT, TYPE_FLOAT]
		var amount := float(raw_amount) if has_amount else 0.0
		if stat["id"] == "kast":
			amount *= 100 if amount <= 1 else 1
		Kit.stat_tile(metrics, UI, str(stat["label"]), str(stat["format"]) % amount if has_amount and int(stats.get("maps", 0)) > 0 else "—")
	if stats.has("k"):
		_quiet_row(content, "K / D / A", Fmt.kda(stats))
	_quiet_row(content, Locale.source("device.personal_balance"), Fmt.money(personal.get("personal_money", CareerBridge.context.get("money", 0))))
	_quiet_row(content, Locale.source("device.current_team"), str(CareerBridge.context.get("team", {}).get("name", "")))
	_label(content, Locale.source("device.recent_career_matches"), 18)
	var recent := SharedPages.new()
	recent.match_selected.connect(func(id: String): _load_detail("match", id))
	recent.recent_matches(content, CareerBridge.context.get("recent_matches", []), false, _button)
	if profile_tab == "overview":
		_button(content, Locale.source("device.allocate_attribute_points"), _profile_tab.bind("growth"), false)

func _skins() -> Dictionary:
	var value = CareerBridge.context.get("skins", {})
	return value if value is Dictionary else {}

func _market_tab(value: String) -> void:
	market_tab = value
	selected_skin = {}
	page_scroll["market"] = 0
	_rebuild()

func _skin_command(action: String, data: Dictionary = {}) -> void:
	if action == "case":
		case_room.open(str(data.get("id", "")))
		return
	if action in ["keep", "cash"]:
		case_room.resolve(action)
		return
	var body := data.duplicate(true)
	body["revision"] = int(CareerBridge.context.get("calendar", {}).get("revision", 0))
	_command("/api/3d/skins/" + action, body)

func _rarity_color(value: String) -> Color:
	return {"consumer":Color("8a98a6"), "industrial":Color("668bb7"), "milspec":Color("668bb7"), "restricted":Color("9278ae"), "classified":Color("b46f91"), "covert":Color("ae5d55"), "rare":Color("a78236"), "extraordinary":Color("a78236")}.get(value, Color("668bb7"))

func _rarity_label(value: String) -> String:
	return str({"consumer":Locale.source("device.consumer_grade"), "industrial":Locale.source("device.industrial_grade"), "milspec":Locale.source("device.mil_spec"), "restricted":Locale.source("device.restricted"), "classified":Locale.source("device.classified"), "covert":Locale.source("device.covert"), "rare":Locale.source("device.rare_special_item"), "extraordinary":Locale.source("device.extraordinary")}.get(value, value))

func _skin_art(parent: Node, row: Dictionary, height: int = 112) -> void:
	var surface := PanelContainer.new()
	surface.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	surface.custom_minimum_size.y = height
	surface.mouse_filter = Control.MOUSE_FILTER_PASS
	surface.add_theme_stylebox_override("panel", UI.style(Color("efeee5"), 6, 10))
	parent.add_child(surface)
	var path := str(row.get("art_path", ""))
	if not path.is_empty() and FileAccess.file_exists(path):
		if not skin_textures.has(path):
			var image := Image.new()
			if image.load(path) == OK:
				skin_textures[path] = ImageTexture.create_from_image(image)
		if skin_textures.has(path):
			var art := TextureRect.new()
			art.texture = skin_textures[path]
			art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			art.mouse_filter = Control.MOUSE_FILTER_IGNORE
			surface.add_child(art)
			return
	var placeholder := Visuals.SkinPlaceholder.new()
	placeholder.weapon = str(row.get("weapon", ""))
	placeholder.paint = _rarity_color(str(row.get("rarity", "")))
	surface.add_child(placeholder)
	_label(parent, Locale.source("device.image_unavailable") + str(row.get("weapon", "")), 11, MUTED)

func _open_skin(row: Dictionary, inventory: bool) -> void:
	selected_skin = row.duplicate(true)
	selected_skin["_inventory"] = inventory
	_rebuild()

func _market() -> void:
	var shop := _skins()
	_label(content, Locale.source("page.market"), 25)
	var wallet = shop.get("personal_money", CareerBridge.context.get("money", 0))
	_quiet_row(content, Locale.source("device.personal_balance"), Locale.source("device.value_game_coins") % int(wallet) if market_tab == "packs" else Fmt.money(wallet))
	_tabs(content, [{"id":"market", "label":Locale.source("device.market")}, {"id":"inventory", "label":Locale.source("device.my_inventory")}, {"id":"cases", "label":Locale.source("device.cases")}, {"id":"packs", "label":Locale.source("device.pro_loadouts")}], market_tab, _market_tab)
	if shop.is_empty():
		_label(content, Locale.source("device.loading_item_details"), 14, MUTED)
		return
	if market_tab == "packs":
		skin_bundles.render(self, content, shop)
		return
	var pending = shop.get("pending")
	if pending is Dictionary and not pending.is_empty():
		var reveal := UI.card(content)
		if case_room.is_running():
			_label(reveal, Locale.source("device.opening_case"), 20)
			_label(reveal, Locale.source("device.the_result_is_saved_manage_the_item_after_the_animation"), 13, MUTED)
		else:
			_label(reveal, Locale.source("device.case_result") + str(pending.get("name", Locale.source("device.skin"))), 20)
			_label(reveal, Locale.source("device.the_result_is_saved_closing_this_window_will_not_reroll_it"), 13, MUTED)
			_skin_art(reveal, pending)
			var decisions := HBoxContainer.new()
			reveal.add_child(decisions)
			var keep := _button(decisions, Locale.source("device.keep_in_inventory"), _skin_command.bind("keep", {}))
			UI.primary(keep)
			keep.set_meta("case_gate", true)
			var cash := _button(decisions, Locale.source("device.sell_now_value") % Fmt.money(pending.get("sell", 0)), _skin_command.bind("cash", {}))
			cash.set_meta("case_gate", true)
	if not selected_skin.is_empty():
		var item := selected_skin
		var owned := bool(item.get("_inventory", false))
		_button(content, Locale.source("device.back_to_list"), _market_tab.bind(market_tab), false)
		var columns := HBoxContainer.new()
		columns.add_theme_constant_override("separation", 25)
		content.add_child(columns)
		var art_column := VBoxContainer.new()
		art_column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		columns.add_child(art_column)
		_skin_art(art_column, item, 235)
		var info := VBoxContainer.new()
		info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		info.add_theme_constant_override("separation", 12)
		columns.add_child(info)
		_label(info, str(item.get("name", Locale.source("device.skin"))), 21)
		_label(info, _rarity_label(str(item.get("rarity", ""))), 13, _rarity_color(str(item.get("rarity", ""))))
		_quiet_row(info, Locale.source("device.wear"), str(item.get("wear_name", item.get("wear", "—"))))
		_label(info, Fmt.money(item.get("spot", item.get("buy", 0))), 25)
		if owned:
			for side in item.get("sides", []):
				var equipped: Dictionary = shop.get("equipped_" + str(side), {})
				var active: bool = str(equipped.get(str(item.get("slot", "")), "")) == str(item.get("id", ""))
				_button(info, (Locale.source("device.unequip") if active else Locale.source("device.equip")) + str(side).to_upper(), _skin_command.bind("equip", {"id":item.get("id", ""), "side":side, "off":active}))
			_button(info, Locale.source("device.sell_value") % Fmt.money(item.get("sell", 0)), _skin_command.bind("sell", {"id":item.get("id", "")}))
		else:
			var purchase := _button(info, Locale.source("device.buy_and_add_to_inventory"), _skin_command.bind("buy", {"id":item.get("id", "")}))
			UI.primary(purchase)
			purchase.disabled = float(shop.get("personal_money", CareerBridge.context.get("money", 0))) < float(item.get("spot", item.get("buy", 0)))
		return
	if market_tab == "cases":
		for case_row in shop.get("cases", []):
			var case_box := UI.card(content)
			_label(case_box, str(case_row.get("name", Locale.source("device.cases"))), 18)
			var cost := int(case_row.get("price", 0)) + int(case_row.get("key", 0))
			_label(case_box, Locale.source("device.case_and_key_value") % Fmt.money(cost), 14, MUTED)
			var open := _button(case_box, Locale.source("device.open_case"), _skin_command.bind("case", {"id":case_row.get("id", "")}))
			open.set_meta("case_gate", true)
			open.disabled = (pending is Dictionary and not pending.is_empty()) or float(shop.get("personal_money", CareerBridge.context.get("money", 0))) < cost
		return
	var grid := GridContainer.new()
	grid.name = "ComputerSkinGrid"
	grid.columns = 3
	grid.add_theme_constant_override("h_separation", 14)
	grid.add_theme_constant_override("v_separation", 14)
	content.add_child(grid)
	var rows: Array = shop.get("inventory" if market_tab == "inventory" else "market", [])
	for item in rows:
		var card := UI.card(grid)
		card.custom_minimum_size.x = 260
		card.mouse_filter = Control.MOUSE_FILTER_PASS
		var hit_area := card.get_parent() as PanelContainer
		hit_area.tooltip_text = str(item.get("name", Locale.source("device.skin")))
		hit_area.gui_input.connect(_skin_card_input.bind(item, market_tab == "inventory"))
		_skin_art(card, item)
		var name_button := _button(card, str(item.get("name", Locale.source("device.skin"))), _open_skin.bind(item, market_tab == "inventory"), false)
		UI.transparent(name_button)
		name_button.add_theme_font_size_override("font_size", 13)
		_label(card, _rarity_label(str(item.get("rarity", ""))) + " · " + str(item.get("wear_name", item.get("wear", ""))), 12, _rarity_color(str(item.get("rarity", ""))))
		_quiet_row(card, "", Fmt.money(item.get("spot", item.get("buy", 0))))
		var stripe := ColorRect.new()
		stripe.color = _rarity_color(str(item.get("rarity", "")))
		stripe.custom_minimum_size.y = 3
		stripe.mouse_filter = Control.MOUSE_FILTER_IGNORE
		card.add_child(stripe)
	if rows.is_empty():
		_label(content, Locale.source("device.your_inventory_is_empty"), 14, MUTED)

func _skin_card_input(event: InputEvent, item: Dictionary, inventory: bool) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_open_skin(item, inventory)
		get_viewport().set_input_as_handled()

func _open_mail(row: Dictionary) -> void:
	selected_mail = row.duplicate(true)
	page_scroll["mail"] = 0
	_rebuild()

func _mail() -> void:
	var inbox: Array = SharedData.inbox(CareerBridge.context)
	var fragment := SharedPages.new()
	if selected_mail.is_empty():
		fragment.mail_selected.connect(_open_mail)
		fragment.mail_list(content, inbox, false, _button)
		return
	var letter := SharedData.current_mail(inbox, selected_mail)
	fragment.mail_action.connect(_mail_action)
	fragment.mail_content(content, letter, false, _button)
	if letter.get("status") != "open" and letter.get("kind") == "contract" and not CareerBridge.context.get("stories", []).is_empty():
		_button(content, Locale.source("device.resolve_current_transfer_decision"), _open_phone.bind("stories"), false)

func _language_changed() -> void:
	rendered_context = ""
	call_deferred("_rebuild")

func _mail_action(action: String, letter: Dictionary) -> void:
	var intent := SharedData.mail_intent(action, letter)
	if intent.has("page"):
		_open_phone(intent.page)
	elif intent.has("path"):
		_device_command(intent.path, intent.body)

func _calendar_select_day(value: String) -> void:
	selected_date = value
	_rebuild()

func _shift_calendar_month(amount: int) -> void:
	calendar_month = SharedData.shift_month(calendar_month, amount, str(CareerBridge.context.get("date", "")))
	_rebuild()

func _calendar() -> void:
	var current := str(CareerBridge.context.get("date", ""))
	if current.is_empty():
		return
	if selected_date.is_empty() or selected_date < current:
		selected_date = CareerBridge.add_days(current, 1)
	if calendar_month.is_empty():
		calendar_month = selected_date.left(7)
	var fragment := SharedPages.new()
	fragment.day_selected.connect(_calendar_select_day)
	fragment.month_shifted.connect(_shift_calendar_month)
	fragment.sleep_requested.connect(func(day: String): CareerBridge.calendar(day, true))
	fragment.event_selected.connect(func(id: String): _load_detail("event", id))
	fragment.calendar_controls(content, current, selected_date, calendar_month, CareerBridge.pending_target, false, _button)
	var next_game := match_center.current_game()
	if not next_game.is_empty():
		var match_card := UI.card(content)
		match_card.name = "CalendarCareerMatch"
		_label(match_card, Locale.source("device.today_s_match") if next_game.get("due", false) else Locale.source("device.next_match"), 18)
		_label(match_card, Locale.source("device.value_value_vs_value") % [next_game.get("date", ""), next_game.get("event", ""), next_game.get("opponent", "")], 15)
		var attendance := match_center.attendance()
		if not str(attendance.get("display_name", "")).is_empty():
			_label(match_card, Locale.source("device.match_venue") + str(attendance.display_name), 15)
			_label(match_card, str(attendance.get("instruction", "")), 13, MUTED)
		var participate := _button(match_card, Locale.source("device.play_in_person") if next_game.get("due", false) else Locale.source("device.play_in_person_sleep_until_match_day"), match_center.prepare_real.bind(str(next_game.get("id", ""))))
		participate.name = "CalendarAttendMatch"
		UI.primary(participate)
	fragment.calendar_events(content, CareerBridge.context.get("calendar_events", []), calendar_month, false, _button)

func _ladder_state() -> Dictionary:
	return CareerBridge.context.get("ladder", {})

func _ladder() -> void:
	if not report.is_empty():
		_render_report(report)
		return
	var ladder := _ladder_state()
	if ladder.is_empty():
		_label(content, Locale.source("device.ladder_data_has_not_loaded_yet"))
		return
	var record: Dictionary = ladder.get("player", {})
	_label(content, Locale.source("device.value_elo_value_value_w_value_l") % [CareerBridge.context.get("player", {}).get("name", ""), Fmt.integer(record.get("elo")), Fmt.integer(record.get("wins"), "0"), Fmt.integer(record.get("losses"), "0")], 19)
	_label(content, Locale.source("device.separate_ladder_rating_simulate_or_play_in_cs2"), 13, MUTED)
	var ladder_tiles := HBoxContainer.new()
	ladder_tiles.add_theme_constant_override("separation", 12)
	content.add_child(ladder_tiles)
	var wins := int(record.get("wins", 0)) if Fmt.is_number(record.get("wins")) else 0
	var losses := int(record.get("losses", 0)) if Fmt.is_number(record.get("losses")) else 0
	Kit.stat_tile(ladder_tiles, UI, "Elo", Fmt.integer(record.get("elo")))
	Kit.stat_tile(ladder_tiles, UI, Locale.source("device.w_l"), "%d / %d" % [wins, losses])
	Kit.stat_tile(ladder_tiles, UI, Locale.source("device.win_rate"), ("%d%%" % roundi(100.0 * wins / (wins + losses))) if wins + losses > 0 else "—")
	var lobby = ladder.get("lobby")
	if lobby is Dictionary and lobby.get("mode", "rank") not in ["rank", "fpl"]:
		_label(content, Locale.source("device.a_custom_match_room_is_active_finish_or_close_it_before_playing_ladder"), 16, MUTED)
		_button(content, Locale.source("device.open_custom_room"), _navigate.bind("custom"), false)
		if lobby.get("phase") == "finished": _button(content, Locale.source("device.find_ladder_match"), _ladder_command.bind("matchmake", {}))
		return
	if not lobby is Dictionary or lobby.is_empty():
		abandon_lobby_id = ""
		UI.primary(_button(content, Locale.source("device.find_match"), _ladder_command.bind("matchmake", {})))
	else:
		var phase := str(lobby.get("phase", ""))
		if abandon_lobby_id != str(lobby.get("id", "")):
			abandon_lobby_id = ""
		if phase == "finished":
			var saved: Dictionary = lobby.get("result", {})
			if not saved.is_empty():
				_button(content, Locale.source("device.open_match_report"), _open_report.bind(saved), false)
			_button(content, Locale.source("device.find_next_match"), _ladder_command.bind("matchmake", {}))
		else:
			ladder_room.heading(lobby)
			# Keep the active pool above the full rosters: on a 720p monitor the
			# old five-slot cards pushed every draft/veto control below the fold.
			if phase not in ["draft", "veto"]:
				_render_rosters(lobby)
			var turn = lobby.get("turn")
			var human: bool = turn is Dictionary and bool(turn.get("human", false))
			if phase == "draft":
				ladder_room.draft(lobby, human)
			elif phase == "veto":
				ladder_room.veto(lobby, human)
			elif phase == "side":
				_label(content, str(lobby.get("map", "")).capitalize() + Locale.source("device.choose_starting_side"), 21)
				_button(content, Locale.source("device.ct_defenders"), _ladder_command.bind("side", {"side":"ct"})).disabled = not human
				_button(content, Locale.source("device.t_attackers"), _ladder_command.bind("side", {"side":"t"})).disabled = not human
			elif phase == "ready":
				_label(content, Locale.source("device.map_2") + str(lobby.get("map", "")).capitalize(), 21)
				var ct_team := str(lobby.get("ct", "a"))
				_label(content, Locale.source("device.starting_sides_team_value_ct_team_value_t") % [ct_team.to_upper(), "B" if ct_team == "a" else "A"], 15, MUTED)
				var ready_actions := HBoxContainer.new()
				ready_actions.add_theme_constant_override("separation", 12)
				content.add_child(ready_actions)
				_button(ready_actions, Locale.source("device.simulate_ladder_match"), _ladder_command.bind("simulate", {"lobby_id":lobby.get("id", "")}))
				var launch := _button(ready_actions, Locale.source("device.play_in_cs2_2"), _ladder_command.bind("launch", {"lobby_id":lobby.get("id", "")}))
				launch.name = "ComputerLadderLaunchCS2"
				UI.primary(launch)
				launch.disabled = not bool(cs2_status.get("can_launch", false))
				var rts := _button(ready_actions, Locale.source("device.command_ladder_match_in_rts"), Callable(rts_room, "open_ladder"), false)
				rts.name = "LadderPlayRTS"
				rts.disabled = not rts_room.has_method("ladder_eligible") or not bool(rts_room.call("ladder_eligible"))
				if rts.disabled: _label(content, Locale.source("device.rts_is_unavailable_for_this_map_simulate_or_play_in_cs2"), 12, MUTED)
				var config: Dictionary = cs2_status.get("config", ladder.get("config", {}))
				if not config.get("ready", false):
					_label(content, str(config.get("reason", Locale.source("device.checking_cs2_setup"))), 13, MUTED)
			elif phase == "rts":
				_label(content, Locale.source("device.rts_match_pending"), 20)
				var resume_rts := _button(content, Locale.source("device.resume_rts_ladder_match"), Callable(rts_room, "open_ladder"), false)
				resume_rts.name = "LadderResumeRTS"
			elif phase in ["starting", "playing", "waiting", "started", "launched", "live"]:
				var phase_label := Locale.source("device.preparing_cs2_match") if phase == "starting" else Locale.source("device.waiting_for_cs2_match_results")
				if phase == "starting" and cs2_status.get("status") == "failed":
					phase_label = Locale.source("device.cs2_match_launch_did_not_finish")
				elif cs2_status.get("cs2_running") == true:
					phase_label = Locale.source("device.this_match_is_being_played_in_cs2")
				_label(content, phase_label, 20)
			else:
				_label(content, Locale.source("device.this_room_cannot_resume_on_this_computer_close_it_before_matching_again"), 16, MUTED)
			if phase in ["draft", "veto"]:
				_render_rosters(lobby)
			if phase != "draft":
				ladder_room.records(lobby)
			if phase in ["draft", "veto", "side", "ready"] and not cs2_status.get("cs2_running", false):
				_button(content, Locale.source("device.leave_current_room"), _ladder_command.bind("cancel", {}))
	if not cs2_status.is_empty():
		var game_status := str(cs2_status.get("status", ""))
		if game_status in ["waiting", "failed", "blocked", "interrupted", "starting"]:
			_label(content, str(cs2_status.get("reason", Locale.source("device.waiting_for_cs2_results"))), 14, MUTED)
		if game_status == "interrupted":
			_label(content, Locale.source("device.re_entering_or_switching_to_rts_restarts_the_unfinished_map_your_roster_map_veto"), 13, MUTED)
			if cs2_status.get("can_resume", false):
				var resume := _button(content, Locale.source("device.re_enter_cs2_restart_this_map"), _ladder_command.bind("launch", {"lobby_id":cs2_status.get("lobby_id", "")}))
				resume.name = "LadderResumeCS2"
			if cs2_status.get("can_simulate", false):
				var simulate := _button(content, Locale.source("device.simulate_this_ladder_match"), _ladder_command.bind("simulate", {"lobby_id":cs2_status.get("lobby_id", "")}))
				simulate.name = "LadderResumeSimulate"
			if cs2_status.get("can_rts", false):
				var rts := _button(content, Locale.source("device.switch_to_rts_restart_this_map"), Callable(rts_room, "open_ladder"), false)
				rts.name = "LadderResumeCS2RTS"
		if cs2_status.get("can_retry", false) and game_status != "interrupted":
			var retry := _button(content, Locale.source("device.retry_cs2_launch"), _ladder_command.bind("launch", {"lobby_id":cs2_status.get("lobby_id", "")}))
			retry.name = "ComputerLadderRetryCS2"
		if cs2_status.get("can_collect", false):
			var collect := _button(content, Locale.source("device.import_result") if game_status != "failed" else Locale.source("device.retry_result_import"), _ladder_command.bind("collect", {"lobby_id":cs2_status.get("lobby_id", "")}))
			collect.name = "ComputerLadderCollectCS2"
		if _can_abandon_ladder():
			if abandon_lobby_id == str(cs2_status.get("lobby_id", "")):
				var confirmation := UI.card(content, true)
				_label(confirmation, Locale.source("device.abandon_this_ladder_match"), 18)
				_label(confirmation, Locale.source("device.close_this_room_without_recording_a_win_loss_or_rating_change_results_cannot_be"), 14, MUTED)
				var choices := HBoxContainer.new()
				confirmation.add_child(choices)
				var abandon := _button(choices, Locale.source("device.confirm_abandon_no_rating_change"), _confirm_ladder_abandon)
				abandon.name = "ComputerLadderConfirmAbandon"
				_button(choices, Locale.source("device.keep_waiting"), _dismiss_ladder_abandon, false)
			else:
				var abandon := _button(content, Locale.source("device.abandon_ladder_match"), _request_ladder_abandon)
				abandon.name = "ComputerLadderAbandon"
	Kit.section(content, UI, Locale.source("device.recent_ladder_matches"), "", 21)
	if ladder.get("history", []).is_empty():
		Kit.empty_state(content, UI, "match", Locale.source("device.no_ladder_record_yet"), Locale.source("device.start_matchmaking_and_every_finished_match_will_be_kept_here"))
	for item in ladder.get("history", []):
		_button(content, _report_title(item), _open_report.bind(item), false)

func _render_rosters(lobby: Dictionary) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	content.add_child(row)
	var roster: Dictionary = lobby.get("roster", {})
	for side in ["a", "b"]:
		var box := UI.card(row, true)
		box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var captains: Array = lobby.get("captains", [])
		var captain := str(captains[0 if side == "a" else 1]) if captains.size() == 2 else ""
		_label(box, Locale.source("device.team_value_captain_value") % [str(side).to_upper(), ladder_room.player_name(lobby, captain)], 16, UI.GREEN)
		for index in range(5):
			var team: Array = lobby.get(side, [])
			if index >= team.size():
				_label(box, Locale.source("device.value_awaiting_draft") % (index + 1), 13, MUTED)
				continue
			var pid: String = team[index]
			var player: Dictionary = roster.get(pid, {})
			_label(box, "%s%s · Elo %s%s" % [player.get("name", ""), Locale.source("device.you_2") if pid == lobby.get("human_id") else "",
				lobby.get("ratings", {}).get(pid, "—"), " · " + str(LadderRoom.ROLES.get(player.get("role", ""), "")) if lobby.get("role_assignment_version") else ""], 13)

func _ladder_command(action: String, extra: Dictionary) -> bool:
	var body := extra.duplicate(true)
	body["revision"] = int(_ladder_state().get("revision", 0))
	notice = ""
	# Automatic captain turns and CS2 launch already have their own visible flow.
	var accepted: bool
	if ladder_command_sender.is_valid(): accepted = bool(ladder_command_sender.call("/api/3d/ladder/" + action, body.duplicate(true)))
	else: accepted = CareerBridge.command("/api/3d/ladder/" + action, body) if action in ["advance", "launch", "collect"] else _command("/api/3d/ladder/" + action, body)
	if not accepted:
		notice = Locale.source("device.request_not_sent_wait_for_the_current_operation_then_retry")
		_update_status()
	return accepted

func _can_abandon_ladder() -> bool:
	var lobby = _ladder_state().get("lobby")
	return lobby is Dictionary and str(lobby.get("phase", "")) in ["starting", "launched"] and str(lobby.get("id", "")) == str(cs2_status.get("lobby_id", "")) and bool(cs2_status.get("process_known", false)) and cs2_status.get("cs2_running") == false

func _request_ladder_abandon() -> void:
	if not _can_abandon_ladder():
		return
	abandon_lobby_id = str(cs2_status.get("lobby_id", ""))
	_rebuild()

func _dismiss_ladder_abandon() -> void:
	abandon_lobby_id = ""
	_rebuild()

func _confirm_ladder_abandon() -> void:
	if not _can_abandon_ladder() or abandon_lobby_id != str(cs2_status.get("lobby_id", "")):
		abandon_lobby_id = ""
		notice = Locale.source("device.close_cs2_and_verify_its_process_has_stopped_before_abandoning")
		_rebuild()
		return
	abandon_lobby_id = ""
	_ladder_command("cancel", {})

func _poll_cs2_status() -> void:
	if screen.visible and active_page == "ladder" and CareerBridge.connected and not CareerBridge.busy:
		CareerBridge._send("/api/3d/ladder/status", {}, false)
		cs2_poll = 1.5

func _advance_ai() -> void:
	ladder_room.queue()

func _scrim() -> void:
	if location != "club":
		_label(content, Locale.source("device.arrange_scrims_at_the_club_workstation"))
		return
	if not report.is_empty():
		_render_report(report)
		return
	var scrims: Dictionary = CareerBridge.context.get("scrims", {})
	_label(content, Locale.source("device.arrange_a_scrim"), 26)
	_label(content, Locale.source("scrim.play_options"), 15, MUTED)
	if not str(scrims.get("launch_reason", "")).is_empty():
		_label(content, str(scrims["launch_reason"]), 14, MUTED)
		_button(content, Locale.source("scrim.open_settings"), _navigate.bind("settings"), false)
	var opponents: Array = scrims.get("opponents", [])
	if opponents.is_empty():
		_label(content, Locale.source("device.no_scrim_opponents_available"))
	else:
		var form := UI.card(content, true)
		_label(form, Locale.source("device.opponent"), 15, MUTED)
		var opponent := OptionButton.new()
		UI.dark_options(opponent)
		opponent.custom_minimum_size.y = 42
		opponent.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		for i in range(opponents.size()):
			opponent.add_item(str(opponents[i].get("name", "")))
			if str(opponents[i].get("id", "")) == opponent_id:
				opponent.select(i)
		if opponent_id.is_empty():
			opponent_id = str(opponents[0].get("id", ""))
		opponent.item_selected.connect(func(index: int): opponent_id = str(opponents[index].get("id", "")))
		form.add_child(opponent)
		_label(form, Locale.source("device.date"), 15, MUTED)
		var current := str(CareerBridge.context.get("date", ""))
		if scrim_date.is_empty() or scrim_date < current:
			scrim_date = current
		var date_entry := LineEdit.new()
		date_entry.text = scrim_date
		date_entry.placeholder_text = "YYYY-MM-DD"
		UI.line_edit(date_entry)
		date_entry.custom_minimum_size.y = 40
		date_entry.text_changed.connect(func(value: String): scrim_date = value)
		form.add_child(date_entry)
		var dates := HBoxContainer.new()
		form.add_child(dates)
		_button(dates, Locale.source("device.today_2"), _set_scrim_date.bind(current), false)
		_button(dates, Locale.source("device.tomorrow"), _set_scrim_date.bind(CareerBridge.add_days(current, 1)), false)
		_label(form, Locale.source("device.map"), 15, MUTED)
		var maps: Array = _ladder_state().get("maps", [])
		var map_choice := OptionButton.new()
		UI.dark_options(map_choice)
		map_choice.custom_minimum_size.y = 42
		for i in range(maps.size()):
			map_choice.add_item(str(maps[i]).capitalize())
			if str(maps[i]) == scrim_map:
				map_choice.select(i)
		if scrim_map.is_empty() and not maps.is_empty():
			scrim_map = str(maps[0])
		map_choice.item_selected.connect(func(index: int): scrim_map = str(maps[index]))
		form.add_child(map_choice)
		_button(form, Locale.source("device.confirm_scrim_booking"), _schedule_scrim).disabled = maps.is_empty()
	_label(content, Locale.source("device.booked_scrims"), 21)
	for item in scrims.get("scheduled", []):
		var card := UI.card(content, true)
		_label(card, "%s · %s · %s" % [item.get("date", ""), item.get("opponent", ""), str(item.get("map", "")).capitalize()], 19)
		if str(item.get("date", "")) <= str(CareerBridge.context.get("date", "")):
			var ident := str(item.get("id", ""))
			var pending: Dictionary = scrims.get("pending", {})
			var waiting := str(pending.get("booking_id", "")) == ident and not str(pending.get("nonce", "")).is_empty()
			if waiting:
				_label(card, Locale.source("scrim.waiting"), 14, MUTED)
				var collect := _button(card, Locale.source("scrim.collect"), _command.bind("/api/3d/scrim/collect", {"id":ident,"nonce":pending.get("nonce", "")}))
				collect.name = "ScrimCollect_" + ident.validate_node_name()
			else:
				var side_choice := OptionButton.new()
				side_choice.name = "ScrimSide_" + ident.validate_node_name()
				UI.dark_options(side_choice)
				side_choice.add_item(Locale.text(Locale.source("scrim.start_ct")))
				side_choice.add_item(Locale.text(Locale.source("scrim.start_t")))
				side_choice.select(1 if scrim_side == "t" else 0)
				side_choice.item_selected.connect(func(index: int): scrim_side = "t" if index == 1 else "ct")
				card.add_child(side_choice)
			var launch := _button(card, Locale.source("scrim.restart" if waiting else "scrim.launch"), _launch_scrim.bind(ident, str(pending.get("nonce", "")) if waiting else ""))
			launch.name = "ScrimLaunch_" + ident.validate_node_name()
			launch.disabled = not scrims.get("launch_ready", false) or (not waiting and not str(pending.get("nonce", "")).is_empty())
			if waiting:
				_button(card, Locale.source("scrim.cancel"), _command.bind("/api/3d/scrim/cancel", {"id":ident,"nonce":pending.get("nonce", ""),"confirmed":true}))
			else:
				_button(card, Locale.source("device.simulate_scrim"), _command.bind("/api/3d/scrim/simulate", {"id":ident})).disabled = not str(pending.get("nonce", "")).is_empty()
		else:
			_label(card, Locale.source("device.the_match_starts_on_the_booked_date"), 15, MUTED)
	if scrims.get("scheduled", []).is_empty():
		_label(content, Locale.source("device.no_scrims_booked_yet"), 15, MUTED)
	_label(content, Locale.source("device.scrim_reports"), 21)
	for item in scrims.get("history", []):
		var saved: Dictionary = item.get("report", {})
		_button(content, _report_title(saved), _open_report.bind(saved), false)

func _set_scrim_date(value: String) -> void:
	scrim_date = value
	page_scroll["scrim"] = scroll.scroll_vertical
	_rebuild()

func _schedule_scrim() -> void:
	_command("/api/3d/scrim/schedule", {"opponent_id":opponent_id, "date":scrim_date, "map":scrim_map})

func _launch_scrim(ident: String, nonce: String) -> void:
	_device_command("/api/3d/scrim/launch", {"id":ident,"nonce":nonce,"side":scrim_side})

func _report_title(value: Dictionary) -> String:
	var map_result: Dictionary = value.get("map", {})
	return "%s  ·  %s  ·  %s  ·  %s" % [value.get("date", ""), str(map_result.get("map", "")).capitalize(), " / ".join(_report_teams(value)), str(map_result.get("score", ""))]

func _report_teams(value: Dictionary) -> Array:
	var teams = value.get("teams")
	if teams is Array and not teams.is_empty():
		return teams
	var players = value.get("map", {}).get("players")
	return players.keys() if players is Dictionary else []

func _open_report(value: Dictionary) -> void:
	report = value.duplicate(true)
	if active_page in ["ladder", "scrim", "custom"]:
		page_reports[active_page] = report
	page_scroll[active_page] = 0
	_rebuild()

func _render_report(value: Dictionary) -> void:
	_button(content, Locale.source("device.back_2"), _back, false)
	var mp: Dictionary = value.get("map", {})
	var pid := str(value.get("human_id", ""))
	var changes: Dictionary = value.get("changes", {})
	if changes.has(pid):
		_label(content, Locale.source("device.your_ladder_rating_value") % int(changes[pid]), 19, UI.GREEN)
	var teams := _report_teams(value)
	var game := {"team_a":teams[0] if teams.size() > 0 else "", "team_b":teams[1] if teams.size() > 1 else "", "date":value.get("date", ""), "series":mp.get("score", ""), "winner":mp.get("winner", ""), "maps":[mp]}
	MatchReport.mount(content, game, {}, pid, func(id: String): _load_detail("player", id))

func _events() -> void:
	_label(content, Locale.source("page.events"), 24)
	_tabs(content, [{"id":"calendar", "label":Locale.source("device.schedule_and_reports")}, {"id":"teams", "label":Locale.source("page.team_details")}, {"id":"players", "label":Locale.source("device.player_stats")}], events_tab, _events_tab)
	if events_tab == "teams":
		var regions := {"EU":Locale.source("device.europe"), "AM":Locale.source("device.americas"), "AS":Locale.source("device.asia")}
		for team in CareerBridge.context.get("teams", []):
			var team_row := _button(content, "#%s  %s  ·  %s" % [Fmt.integer(team.get("rank")), team.get("name", ""), team.get("region", "")], _load_detail.bind("team", str(team.get("id", ""))), false)
			Kit.rich_row(team_row, UI, str(team.get("name", "")), str(regions.get(str(team.get("region", "")), team.get("region", ""))) + Locale.source("device.region"), Fmt.rank(team.get("rank")), "", "gray", "", str(team.get("name", "")))
	elif events_tab == "players":
		_render_player_directory()
	else:
		var events: Array = CareerBridge.context.get("calendar_events", [])
		var today := str(CareerBridge.context.get("date", ""))
		var upcoming: Array = []
		var finished: Array = []
		for item in events:
			if str(item.get("end_date", item.get("date", ""))) < today: finished.append(item)
			else: upcoming.append(item)
		finished.reverse()
		Kit.section(content, UI, Locale.source("device.tournament_schedule"), Locale.source("device.value_live_or_upcoming_value_finished") % [upcoming.size(), finished.size()], 19)
		if events.is_empty():
			Kit.empty_state(content, UI, "calendar", Locale.source("device.no_events_yet"), Locale.source("device.events_you_register_for_appear_here_after_accepting_invitations"))
		for item in upcoming + finished:
			if item == (finished[0] if not finished.is_empty() else null):
				_label(content, Locale.source("device.finished_2"), 13, MUTED)
			var tier := Kit.event_tier(str(item.get("type", "")))
			var span := Kit.short_date(str(item.get("date", "")))
			if not str(item.get("end_date", "")).is_empty() and item.get("end_date") != item.get("date"):
				span += " – " + Kit.short_date(str(item.get("end_date", "")))
			var ended := str(item.get("end_date", item.get("date", ""))) < today
			var running := not ended and str(item.get("date", "")) <= today
			var state := [Locale.source("calendar.registered"), "green"] if item.get("registered", false) and not ended else ([Locale.source("device.finished_2"), "gray"] if ended else ([Locale.source("device.live"), "gray"] if running else ["", "gray"]))
			var event_row := _button(content, "%s  ·  %s%s" % [item.get("date", ""), item.get("name", ""), Locale.source("device.registered") if item.get("registered", false) else ""], _load_detail.bind("event", str(item.get("id", ""))), false)
			Kit.rich_row(event_row, UI, str(item.get("name", "")), "%s · %s" % [span, tier[0]], str(state[0]), str(tier[0]), str(tier[1]), "trophy", "", Color("2f6b52") if item.get("registered", false) else Color.TRANSPARENT)
		Kit.section(content, UI, Locale.source("device.recent_matches"), "", 19)
		var recent: Array = CareerBridge.context.get("recent_matches", [])
		if recent.is_empty():
			Kit.empty_state(content, UI, "match", Locale.source("device.no_match_records_yet"), Locale.source("device.match_reports_appear_here_after_your_first_pro_match"))
		for game in recent:
			var match_row := _button(content, "%s · %s / %s · %s" % [game.get("date", ""), game.get("team_a", ""), game.get("team_b", ""), str(game.get("series", ""))], _load_detail.bind("match", str(game.get("id", ""))), false)
			Kit.rich_row(match_row, UI, "%s  vs  %s" % [game.get("team_a", ""), game.get("team_b", "")], str(game.get("date", "")), str(game.get("series", "")), "", "gray", "", str(game.get("team_a", "")))

func _events_tab(value: String) -> void:
	events_tab = value
	page_scroll["events"] = 0
	_rebuild()

func _render_player_directory() -> void:
	_label(content, Locale.source("device.season_player_statistics"), 21)
	_label(content, str(players_data.get("note", Locale.source("device.this_season_vs_vrs_top30"))), 13, MUTED)
	var filter_row := HBoxContainer.new()
	content.add_child(filter_row)
	var search := LineEdit.new()
	UI.line_edit(search)
	search.text = players_search
	search.placeholder_text = Locale.source("device.player_or_team_name")
	search.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	filter_row.add_child(search)
	_button(filter_row, Locale.source("device.search"), func():
		players_search = search.text.strip_edges()
		players_page = 1
		players_data = {}
		players_query = ""
		_rebuild()
	, false)
	for player in players_data.get("rows", []):
		var box := UI.card(content)
		var row := HBoxContainer.new()
		box.add_child(row)
		var pid := str(player.get("player_id", ""))
		if not pid.is_empty():
			TeamVisuals.button_logo(_button(row, str(player.get("player", "")), _load_detail.bind("player", pid), false), str(player.get("team", ""))).size_flags_horizontal = Control.SIZE_EXPAND_FILL
		else:
			TeamVisuals.badge(row, str(player.get("team", "")), 32)
			_label(row, str(player.get("player", "")), 16).size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var team_label := _label(row, str(player.get("team", "")), 14, MUTED)
		team_label.size_flags_horizontal = Control.SIZE_SHRINK_END
		team_label.autowrap_mode = TextServer.AUTOWRAP_OFF
		team_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		_label(box, Locale.source("device.rating_value_adr_value_kast_value_value_maps_value_value_value") % [_number(player.get("rating"), 2), _number(player.get("adr"), 1), _percentage(player.get("kast")), player.get("maps", 0), player.get("k", "—"), player.get("d", "—"), player.get("a", "—")], 14)
	if players_data.get("rows", []).is_empty():
		_label(content, Locale.source("device.loading_player_statistics") if players_data.is_empty() else Locale.source("device.no_recorded_players_match_these_filters"), 14, MUTED)
	var pages := HBoxContainer.new()
	content.add_child(pages)
	_button(pages, Locale.source("device.previous"), _players_page.bind(-1), false).disabled = players_page <= 1
	_label(pages, "%s / %s" % [players_page, players_data.get("pages", 1)])
	_button(pages, Locale.source("device.next"), _players_page.bind(1), false).disabled = players_page >= int(players_data.get("pages", 1))
	var query := "/api/3d/players?span=season&page=%s&search=%s" % [players_page, players_search.uri_encode()]
	if players_query != query and pending_players_path.is_empty():
		call_deferred("_fetch_players", query)

func _fetch_players(query: String) -> void:
	if screen.visible and active_page == "events" and events_tab == "players" and CareerBridge._send(query, {}, false):
		pending_players_path = query
		players_query = query

func _players_page(delta: int) -> void:
	players_page = maxi(1, players_page + delta)
	players_data = {}
	players_query = ""
	page_scroll["events"] = 0
	_rebuild()

func _load_detail(kind: String, id: String, span: String = "", page: int = 1) -> void:
	pending_detail_intent = detail_intent_serial
	pending_detail_path = "/api/3d/" + kind + "?id=" + id.uri_encode()
	if kind == "player":
		if span.is_empty():
			player_tab = "overview"
			span = "season"
		pending_detail_path += "&span=" + span.uri_encode() + "&page=" + str(page)
	if not CareerBridge._send(pending_detail_path, {}, false):
		pending_detail_path = ""

func _team() -> void:
	var team_name := str(detail.get("name", ""))
	TeamVisuals.banner(content, str(detail.get("name", Locale.source("page.team"))), team_name, Locale.source("page.team_details"))
	SharedPages.new().roster_date(content, detail, false)
	for field in ["region", "rank", "vrs", "money"]:
		if detail.has(field):
			_label(content, "%s：%s" % [{"region":Locale.source("device.region"), "rank":Locale.source("device.rank"), "vrs":"VRS", "money":Locale.source("device.funds")}.get(field, field), str(detail[field])])
	preload("res://scripts/map_form_panel.gd").mount(content, detail.get("map_performance", []))
	var roster: Array = detail.get("roster", detail.get("players", []))
	for member in roster:
		if member is Dictionary:
			TeamVisuals.button_logo(_button(content, Locale.source("device.value_value_ability_value") % [member.get("name", ""), Phone.ROLES.get(member.get("role", ""), member.get("role", "")), Fmt.score(member.get("ability"))], _load_detail.bind("player", str(member.get("player_id", member.get("id", ""))))), team_name)

func _player() -> void:
	TeamVisuals.banner(content, str(detail.get("name", Locale.source("page.player"))), str(detail.get("team", detail.get("last_team", ""))), str(detail.get("team", detail.get("last_team", ""))))
	SharedPages.new().roster_date(content, detail, false)
	_label(content, str(Phone.ROLES.get(detail.get("role", ""), detail.get("role", ""))) + (Locale.source("device.historical_profile") if detail.get("historical", false) else ""), 17, MUTED)
	if not str(detail.get("team_id", "")).is_empty():
		TeamVisuals.button_logo(_button(content, str(detail.get("team", "")), _load_detail.bind("team", str(detail["team_id"])), false), str(detail.get("team", "")))
	for field in ["age", "ability", "command", "form_delta"]:
		if detail.has(field) and detail[field] != null:
			_label(content, "%s：%s" % [{"team":Locale.source("page.team"), "age":Locale.source("device.age"), "ability":Locale.source("device.ability"), "command":Locale.source("role.igl"), "form_delta":Locale.source("device.form")}.get(field, field), str(detail[field])])
	_tabs(content, [{"id":"overview", "label":Locale.source("device.overview")}, {"id":"matches", "label":Locale.source("device.match_history")}, {"id":"honours", "label":Locale.source("profile.honours")}], player_tab, _player_tab)
	var ranges := HBoxContainer.new()
	content.add_child(ranges)
	_label(ranges, Locale.source("device.statistics_range"), 13, MUTED)
	for scope in [{"id":"30d", "label":Locale.source("device.last_30_days")}, {"id":"season", "label":Locale.source("device.this_season")}, {"id":"all", "label":Locale.source("device.all_saved_history")}]:
		var button := _button(ranges, str(scope["label"]), _player_range.bind(str(scope["id"])), false)
		if player_span == str(scope["id"]):
			UI.transparent(button)
			button.add_theme_stylebox_override("normal", UI.style(UI.MINT, 7, 8))
	_label(content, Locale.source("device.value_saved_maps_missing_data_is_not_reconstructed") % detail.get("total", 0), 13, MUTED)
	if player_tab == "honours":
		_player_honours()
		return
	SharedPages.new().player_summary(content, detail.get("summary", {}), false)
	if player_tab == "overview":
		var stats: Dictionary = detail.get("stats", {}) if detail.get("stats") is Dictionary else {}
		_position_preview(content, detail, str(detail.get("role", "")), stats, "player")
		if not detail.get("historical", false) and not stats.is_empty():
			var box := UI.card(content)
			_label(box, Locale.source("device.attributes_for_current_role"), 18)
			for axis in {"firepower":Locale.source("device.aim"), "entrying":Locale.source("device.entry"), "trading":Locale.source("device.trading"), "opening":Locale.source("device.opening"), "clutching":Locale.source("device.clutching"), "sniping":Locale.source("device.sniping"), "utility":Locale.source("device.utility"), "command":Locale.source("role.igl")}:
				if stats.get(axis) != null:
					_quiet_row(box, str({"firepower":Locale.source("device.aim"), "entrying":Locale.source("device.entry"), "trading":Locale.source("device.trading"), "opening":Locale.source("device.opening"), "clutching":Locale.source("device.clutching"), "sniping":Locale.source("device.sniping"), "utility":Locale.source("device.utility"), "command":Locale.source("role.igl")}[axis]), _number(stats.get(axis), 1))
		_label(content, Locale.source("device.last_10_maps"), 19)
	_render_player_matches(detail.get("records", []) if player_tab == "matches" else detail.get("recent", []))
	if player_tab == "matches":
		var pagination := HBoxContainer.new()
		content.add_child(pagination)
		var pages := maxi(1, ceili(float(detail.get("total", 0)) / maxf(1, float(detail.get("page_size", 20)))))
		_button(pagination, Locale.source("device.previous"), _player_page.bind(-1), false).disabled = player_page <= 1
		_label(pagination, "%s / %s" % [player_page, pages])
		_button(pagination, Locale.source("device.next"), _player_page.bind(1), false).disabled = player_page >= pages

func _player_tab(value: String) -> void:
	player_tab = value
	page_scroll["player"] = 0
	_rebuild()

func _player_range(value: String) -> void:
	_load_detail("player", str(detail.get("player_id", detail.get("name", ""))), value, 1)

func _player_page(delta: int) -> void:
	_load_detail("player", str(detail.get("player_id", detail.get("name", ""))), player_span, maxi(1, player_page + delta))

func _render_player_matches(records: Array) -> void:
	if records.is_empty():
		_label(content, Locale.source("device.no_saved_maps_in_this_range"), 14, MUTED)
	for item in records:
		var box := UI.card(content)
		var row := HBoxContainer.new()
		box.add_child(row)
		_button(row, "%s · %s" % [item.get("date", ""), item.get("event", "")], _load_detail.bind("event", str(item.get("event_id", ""))), false).size_flags_horizontal = Control.SIZE_EXPAND_FILL
		_button(row, "%s · %s · %s" % [str(item.get("map", "")).capitalize(), item.get("opponent", ""), str(item.get("score", ""))], _load_detail.bind("match", str(item.get("match_id", ""))), false)
		_label(box, "%s / %s / %s · Rating %s · ADR %s · KAST %s" % [item.get("k", "—"), item.get("d", "—"), item.get("a", "—"), _number(item.get("rating"), 2), _number(item.get("adr"), 1), _percentage(item.get("kast"))], 14)

func _player_honours() -> void:
	SharedPages.new().player_honours(content, detail, false)

static func _number(value, digits: int = 1) -> String:
	return Fmt.num(value, digits)

static func _percentage(value) -> String:
	return Fmt.percent_fixed(value)

func _event() -> void:
	_label(content, str(detail.get("name", Locale.source("page.match"))), 28)
	_label(content, EventFlow.dates_text(detail.get("dates", [])), 17, MUTED)
	for field in ["tier", "format", "prize", "region", "status"]:
		if detail.has(field):
			_label(content, "%s：%s" % [{"tier":Locale.source("device.tier"), "format":Locale.source("device.format"), "prize":Locale.source("device.prize_money"), "region":Locale.source("device.region"), "status":Locale.source("device.form")}.get(field, field), EventFlow.field_text(field, detail[field])])
	EventFlow.mount(content, detail, func(id: String): _load_detail("match", id))

func _match() -> void:
	var game: Dictionary = detail.get("match", {})
	MatchReport.mount(content, game, detail.get("event", {}), str(CareerBridge.context.get("player", {}).get("id", "")), func(id: String): _load_detail("player", id))

func _busy_changed(value: bool) -> void:
	for button in action_buttons:
		if is_instance_valid(button):
			button.disabled = (value and CareerBridge.active_post) or not CareerBridge.connected or bool(button.get_meta("career_gate_disabled", false)) or (bool(button.get_meta("case_gate", false)) and case_room.locked())
	case_room.refresh_buttons()
	if active_page == "tactics": tactics.refresh()
	custom_room.busy_changed(value)
	save_manager._update_controls()
	_update_status()

func _finished(path: String, result: Dictionary) -> void:
	# Queue our own result before a leaf returns, then show it after that leaf's
	# navigation/repaint. Background reads and the other device remain silent.
	if is_instance_valid(action_feedback): action_feedback.call_deferred("finish_request", path, result)
	if save_manager.received(path, result): return
	case_room.finished(path, result)
	ladder_room.received(path, result)
	if custom_room.received(path, result): return
	if career_start.finished(path, result): return
	if appearance.finished(path, result): return
	if controls.received(path, result): return
	if match_center.finished(path, result):
		return
	if tactics.finished(path, result):
		return
	if device_settings.finished(path, result):
		if screen.visible and active_page == "settings":
			_rebuild()
		return
	if news.finished(path, result):
		return
	if path == pending_players_path and not pending_players_path.is_empty():
		pending_players_path = ""
		if path == players_query:
			players_data = result.duplicate(true)
			if screen.visible and active_page == "events" and events_tab == "players":
				_rebuild()
		return
	if path == "/api/3d/ladder/status":
		var changed: bool = JSON.stringify(cs2_status) != JSON.stringify(result)
		cs2_status = result.duplicate(true)
		if screen.visible and active_page == "ladder" and changed:
			page_scroll[active_page] = scroll.scroll_vertical
			_rebuild()
		return
	if path == pending_detail_path and not pending_detail_path.is_empty():
		var may_navigate: bool = screen.visible and pending_detail_intent == detail_intent_serial
		pending_detail_path = ""
		pending_detail_intent = -1
		if result.get("ok", false):
			detail = result if path.begins_with("/api/3d/match?") else result.get("detail", {})
			var page := path.get_slice("/", 3).get_slice("?", 0)
			page_details[page] = detail
			if page == "player":
				player_span = str(detail.get("range", "season"))
				player_page = int(detail.get("page", 1))
			if may_navigate:
				_navigate(page)
	if not screen.visible:
		return
	if path.begins_with("/api/3d/ladder/") or path.begins_with("/api/3d/scrim/"):
		var connection_changed := false
		if result.get("connection") is Dictionary:
			connection_changed = JSON.stringify(cs2_status) != JSON.stringify(result["connection"])
			cs2_status = result["connection"].duplicate(true)
		notice = str(result.get("reason", result.get("msg", "")))
		if result.get("ok", false):
			var report_changed := false
			var report_page := "ladder" if path.begins_with("/api/3d/ladder/") else "scrim"
			var received_report: Dictionary = {}
			if result.get("result") is Dictionary:
				received_report = result["result"]
			elif result.get("report") is Dictionary:
				received_report = result["report"]
			if not received_report.is_empty():
				page_reports[report_page] = received_report
			if report_page == active_page and not received_report.is_empty():
				report = received_report
				report_changed = true
			if report_changed or connection_changed or rendered_context != PageProjection.signature(active_page, CareerBridge.context):
				page_scroll[active_page] = 0 if report_changed else scroll.scroll_vertical
				_rebuild()
			else:
				_update_status()
			call_deferred("_advance_ai")
			if path.begins_with("/api/3d/ladder/"):
				call_deferred("_poll_cs2_status")
		else:
			if active_page == "ladder" and (connection_changed or path == "/api/3d/ladder/advance"):
				page_scroll[active_page] = scroll.scroll_vertical
				_rebuild()
			else:
				_update_status()
	elif path.begins_with("/api/3d/ops/") or path.begins_with("/api/3d/transfers/") or path.begins_with("/api/3d/mail/"):
		business.finished(path, result)
		notice = str(result.get("reason", result.get("msg", "")))
		if path == "/api/3d/mail/accept" and result.get("ok", false) and result.get("decision_pending", false):
			_open_phone("stories")
			return
		if active_page in ["operations", "transfers", "mail"]:
			_rebuild()
	elif path.begins_with("/api/3d/skins/"):
		notice = Locale.source("device.opening_case") if case_room.is_running() else str(result.get("reason", result.get("msg", "")))
		if result.get("ok", false):
			selected_skin = {}
		if active_page == "market":
			_rebuild()
	elif not result.get("ok", false):
		notice = str(result.get("msg", result.get("reason", Locale.source("device.this_operation_did_not_complete"))))
		_update_status()

func _update_status() -> void:
	if status:
		if case_room.is_running():
			status.text = Locale.source("device.opening_case")
			return
		# While a match result is being revealed the service message would spoil
		# the score ("Vitality 2-0 ..."), so the footer stays quiet until the end.
		if match_center.is_presenting() and match_center.reveal_phase == "maps":
			status.text = ""
			return
		status.text = (Locale.source("device.processing") if CareerBridge.active_post else Locale.source("device.synchronizing_2")) if CareerBridge.busy else (notice if not notice.is_empty() else CareerBridge.message)

func _wake() -> void:
	close_computer()

func _focus_first() -> void:
	if screen.visible:
		_focus_in(content)

func _focus_in(node: Node) -> bool:
	for child in node.get_children():
		if child is Button and not child.disabled:
			child.grab_focus()
			return true
		if _focus_in(child):
			return true
	return false

func _restore_keyed_focus(key: String) -> void:
	var target := content.find_child(key, true, false) as Button
	if target != null and not target.disabled and target.is_visible_in_tree(): target.grab_focus()

func _restore_focus(node: Node, text: String) -> bool:
	for child in node.get_children():
		if child is Button and child.text == text and not child.disabled:
			child.grab_focus()
			return true
		if _restore_focus(child, text):
			return true
	return false

func _process(delta: float) -> void:
	match_center.process(delta)
	controls.process(delta)
	ladder_room.process(delta)
	custom_room.process(delta)
	if screen.visible:
		var focused := get_viewport().gui_get_focus_owner()
		if repaint_pending and not Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT) and not focused is LineEdit and not focused is TextEdit:
			repaint_pending = false
			_context_changed()
		if active_page == "start" and career_start.options.is_empty() and career_start.page == "create": career_start.fetch()
		if active_page == "saves" and not save_manager.requested_once and CareerBridge.connected and not CareerBridge.busy:
			save_manager.fetch()
		if active_page == "tactics" and not tactics.libraries.has(tactics.map_code) and tactics.pending_path.is_empty() and CareerBridge.connected and not CareerBridge.busy and not CareerBridge.endpoint.is_empty():
			tactics.fetch()
		clock.text = CareerBridge.clock_text()
		cs2_poll -= delta
		if active_page == "ladder" and cs2_poll <= 0 and (cs2_status.is_empty() or str(cs2_status.get("status", "")) in ["waiting", "failed", "blocked", "interrupted", "starting"]):
			_poll_cs2_status()

func _input(event: InputEvent) -> void:
	if is_instance_valid(rts_room.session): return
	if not screen.visible or not event is InputEventKey or not event.pressed or event.echo or UI.key_claimed(self):
		return
	var typing := get_viewport().gui_get_focus_owner()
	if typing is LineEdit or typing is TextEdit:
		return
	if event.physical_keycode in [KEY_ESCAPE, KEY_P, KEY_E]:
		close_computer()
		UI.claim_key(self)
	elif event.physical_keycode == KEY_HOME:
		_desktop()
		UI.claim_key(self)
	elif event.physical_keycode == KEY_BACKSPACE:
		var focused := get_viewport().gui_get_focus_owner()
		if not focused is LineEdit:
			_back()
			UI.claim_key(self)
