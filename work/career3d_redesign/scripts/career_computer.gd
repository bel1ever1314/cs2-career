extends CanvasLayer
## Desktop workstation. CareerBridge owns all ladder and scrim state.
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
const LIGHT := UI.INK
const MUTED := UI.MUTED
const PAGES := {"desktop":"桌面", "battle":"对战中心", "career_match":"职业比赛", "quick":"快速赛季", "settings":"设置", "tactics":"战术室", "ladder":"本地天梯", "custom":"自定义对局", "rts":"战术模拟", "scrim":"训练赛", "events":"赛事中心", "team":"战队资料", "player":"选手资料", "event":"赛事资料", "match":"比赛战报", "market":"饰品市场", "profile":"我的生涯", "mail":"邮件", "calendar":"日历", "operations":"经营", "transfers":"转会", "news":"赛事新闻", "management":"阵容与合同", "training":"训练与成长", "assistance":"自动安排", "rankings":"职业榜单", "workshop":"扩展工坊", "start":"开始与继续", "appearance":"我的形象", "saves":"存档管理"}
const APPS := [{"page":"battle", "label":"对战中心", "icon":"match"}, {"page":"events", "label":"赛事中心", "icon":"trophy"}, {"page":"market", "label":"饰品市场", "icon":"clipboard"}, {"page":"operations", "label":"经营", "icon":"finance"}, {"page":"transfers", "label":"转会", "icon":"transfers"}, {"page":"news", "label":"赛事新闻", "icon":"news"}, {"page":"profile", "label":"我的生涯", "icon":"profile"}, {"page":"mail", "label":"邮件", "icon":"mail"}, {"page":"calendar", "label":"日历", "icon":"calendar"}]
var screen: Control
var panel: PanelContainer
var stand: PanelContainer
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
var pending_detail_path := ""
var rendered_context := ""
var notice := ""
var action_feedback: Control
var app_toolbar: HBoxContainer
var taskbar: HBoxContainer
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
	var place_label := _label(menubar, "俱乐部电脑", 12, MUTED)
	place_label.name = "ComputerLocation"
	place_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var close := UI.compact(UI.button(menubar, "离开电脑  [E / Esc]", close_computer))
	UI.transparent(close)
	app_toolbar = HBoxContainer.new()
	app_toolbar.name = "ComputerAppToolbar"
	app_toolbar.add_theme_constant_override("separation", 10)
	layout.add_child(app_toolbar)
	back_button = UI.compact(UI.button(app_toolbar, "‹ 返回", _back))
	UI.transparent(back_button)
	back_button.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	title = _label(app_toolbar, "桌面", 15)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	UI.transparent(UI.compact(UI.button(app_toolbar, "×", _desktop)))
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
	for item in [["management", "阵容与合同"], ["training", "训练与成长"], ["assistance", "自动安排"], ["rankings", "职业榜单"], ["workshop", "扩展工坊"], ["appearance", "我的形象"], ["start", "开局选择"], ["saves", "存档管理"]]:
		UI.compact(_button(utilities, item[1], _navigate.bind(item[0]), false))
	status = _label(layout, "", 12, MUTED)
	status.custom_minimum_size.y = 18
	status.max_lines_visible = 2
	var taskbar_surface := PanelContainer.new()
	taskbar_surface.add_theme_stylebox_override("panel", UI.style(UI.PAPER, 8, 8))
	layout.add_child(taskbar_surface)
	taskbar = HBoxContainer.new()
	taskbar.name = "ComputerTaskbar"
	taskbar.add_theme_constant_override("separation", 4)
	taskbar_surface.add_child(taskbar)
	var home := UI.compact(UI.button(taskbar, "桌面", _desktop))
	UI.transparent(home)
	home.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	for app in APPS:
		_icon_button(taskbar, str(app["icon"]), str(app["label"]), _navigate.bind(str(app["page"])), Vector2(32, 32))
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	taskbar.add_child(spacer)
	UI.transparent(UI.compact(UI.button(taskbar, "我的手机", _open_phone)))
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
	greeting.visible = not compact
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
	if is_instance_valid(rts_room.session) and not rts_room.close_session(): return
	_clear_action_feedback()
	page_scroll[active_page] = scroll.scroll_vertical
	detail_intent_serial += 1
	screen.visible = false
	if release:
		UI.device_closed(self)

func _navigate(page: String, push: bool = true) -> void:
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
	if dimensions.x < 40:
		UI.transparent(node)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	node.add_child(center)
	var icon := Visuals.icon(kind, Vector2(25, 25) if dimensions.x >= 40 else Vector2(18, 18))
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
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	parent.add_child(row)
	for choice in choices:
		var button := _button(row, str(choice["label"]), callback.bind(str(choice["id"])), false)
		UI.transparent(button)
		button.set_meta("focus_key", str(choice["id"]))
		if str(choice["id"]) == selected:
			button.add_theme_stylebox_override("normal", UI.style(UI.MINT, 7, 8))

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
	content.size_flags_vertical = Control.SIZE_EXPAND_FILL if active_page == "desktop" else Control.SIZE_FILL
	content.add_theme_constant_override("separation", 6 if active_page in ["career_match", "quick", "tactics"] or (active_page == "battle" and match_center.is_presenting()) else 12)
	action_buttons.clear()
	built_while_busy = CareerBridge.busy
	title.text = str(PAGES.get(active_page, "桌面"))
	app_toolbar.visible = active_page != "desktop"
	desktop_wallpaper.visible = active_page == "desktop"
	desktop_shortcuts.visible = active_page == "desktop"
	var location_label := panel.find_child("ComputerLocation", true, false) as Label
	if location_label:
		location_label.text = {"club":"俱乐部电脑", "lan":"LAN 选手电脑", "major":"赛事选手电脑", "bedroom":"宿舍电脑"}.get(location, "宿舍电脑")
	back_button.disabled = active_page == "desktop"
	rendered_context = PageProjection.signature(active_page, CareerBridge.context)
	_update_status()
	if CareerBridge.context.is_empty() and active_page != "desktop":
		_label(content, "生涯正在载入。连接完成后即可使用。")
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
				else: _label(content, "战术模拟模块尚未接入。", 18, MUTED)
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
	_label(card, "界面字体", 18)
	var picker := OptionButton.new()
	picker.name = "UIFontChoice"
	UI.dark_options(picker)
	picker.add_item("圆润字体 · 寒蝉全圆体")
	picker.add_item("清晰字体 · 系统黑体")
	picker.select(0 if UI.Base.font_style == "rounded" else 1)
	card.add_child(picker)
	picker.item_selected.connect(func(index: int):
		UI.Base.choose_font("rounded" if index == 0 else "system", get_tree())
	)
	_label(card, "字体随样板离线提供；仅改变显示，不影响生涯。", 12, MUTED)

func _render_desktop() -> void:
	var desktop := BoxContainer.new()
	desktop.name = "ComputerDesktop"
	desktop.size_flags_vertical = Control.SIZE_EXPAND_FILL
	desktop.add_theme_constant_override("separation", 28)
	content.add_child(desktop)
	var grid := GridContainer.new()
	grid.name = "ComputerDesktopIcons"
	grid.columns = 3
	grid.custom_minimum_size.x = 319
	grid.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	grid.add_theme_constant_override("h_separation", 20)
	grid.add_theme_constant_override("v_separation", 22)
	desktop.add_child(grid)
	for app in APPS:
		var cell := VBoxContainer.new()
		cell.custom_minimum_size.x = 93
		cell.add_theme_constant_override("separation", 7)
		grid.add_child(cell)
		_icon_button(cell, str(app["icon"]), str(app["label"]), _navigate.bind(str(app["page"])))
		var caption := _label(cell, str(app["label"]), 12)
		caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		caption.mouse_filter = Control.MOUSE_FILTER_STOP
		caption.gui_input.connect(func(event: InputEvent):
			if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
				_navigate(str(app["page"]))
		)
	var greeting := VBoxContainer.new()
	greeting.name = "ComputerDesktopGreeting"
	greeting.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	greeting.size_flags_vertical = Control.SIZE_SHRINK_END
	greeting.add_theme_constant_override("separation", 8)
	desktop.add_child(greeting)
	_label(greeting, str(CareerBridge.context.get("player", {}).get("name", "")) + "的" + ("俱乐部电脑" if location == "club" else "宿舍电脑"), 12, MUTED)
	var agenda := UI.card(desktop)
	var agenda_panel := agenda.get_parent() as PanelContainer
	agenda_panel.name = "ComputerDesktopAgenda"
	agenda_panel.size_flags_horizontal = Control.SIZE_SHRINK_END
	agenda_panel.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	agenda.custom_minimum_size.x = 250
	agenda.size_flags_horizontal = Control.SIZE_SHRINK_END
	agenda.size_flags_vertical = Control.SIZE_SHRINK_BEGIN
	_label(agenda, "今日安排", 16)
	var next_game := match_center.current_game()
	var attendance := match_center.attendance()
	if not next_game.is_empty() and (attendance.get("planned", false) or next_game.get("due", false)):
		_label(agenda, "%s · %s" % [next_game.get("event", "下一场比赛"), attendance.get("display_name", "比赛场馆")], 13)
		var arrangement := _button(agenda, "查看参赛安排", _navigate.bind("career_match"), false)
		arrangement.name = "DesktopAttendance"
		UI.primary(arrangement)
	_button(agenda, "调整与培养 · %s 点自由属性" % CareerBridge.context.get("attr_points", 0), _navigate.bind("profile"), false)
	_button(agenda, "训练与对战", _navigate.bind("battle"), false)
	_button(agenda, "%d 封邮件" % CareerBridge.context.get("inbox", []).size(), _navigate.bind("mail"), false)
	_button(agenda, "看看日历", _navigate.bind("calendar"), false)
	_button(agenda, "快速赛季", _navigate.bind("quick"), false)
	_button(agenda, "战术室", _navigate.bind("tactics"), false)
	_button(agenda, "CS2 与换肤设置", _navigate.bind("settings"), false)

func _battle() -> void:
	match_center.render(content)
	if match_center.is_presenting():
		return
	_label(content, "对战中心", 25)
	_label(content, "从一场好好打的比赛开始。", 14, MUTED)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 22)
	content.add_child(row)
	var ladder_box := UI.card(row)
	ladder_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_label(ladder_box, "本地天梯", 20)
	var player: Dictionary = _ladder_state().get("player", {})
	_label(ladder_box, "%s · Elo %s" % [CareerBridge.context.get("player", {}).get("name", ""), player.get("elo", "—")], 15)
	_label(ladder_box, "当前生涯角色 · 十人匹配 · 队长选人 · 地图 BP", 13, MUTED)
	UI.primary(_button(ladder_box, "打开天梯", _navigate.bind("ladder"), false))
	var training := UI.card(row)
	training.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_label(training, "训练赛", 20)
	_label(training, "约对手、练配合，打完一起看战报。", 13, MUTED)
	if location == "club":
		_button(training, "约一场训练赛", _navigate.bind("scrim"), false)
	else:
		_label(training, "到俱乐部电脑安排训练赛。", 14, MUTED)
	var custom := UI.card(content)
	_label(custom, "自定义对局 · 战术验证", 18)
	_label(custom, "自行选择双方各五名选手、地图与开场阵营；可控制一名选手或观察十名 BOT，不计天梯积分。", 13, MUTED)
	var custom_entry := _button(custom, "打开自定义对局", _navigate.bind("custom"), false)
	custom_entry.name = "ComputerOpenCustom"
	var rts_entry := _button(custom, "RTS 指挥对局", Callable(rts_room, "open_custom"), false)
	rts_entry.name = "ComputerOpenRTS"
	_label(content, "职业赛事", 18)
	_label(content, "比赛安排与历史战报在赛事中心；待处理的比赛也可从手机查看。", 14, MUTED)
	_button(content, "查看赛事日程", _navigate.bind("events"), false)

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
	var raw_views = data.get("position_views", [])
	var views: Array = raw_views if raw_views is Array else []
	if views.is_empty():
		return
	var selected := str(position_preview_roles.get(page, ""))
	var shown: Dictionary = {"ability":data.get("ability"), "stats":current_stats}
	var box := UI.card(parent)
	box.name = "ComputerPositionPreview_" + page
	_label(box, "位置能力", 18)
	var selector := OptionButton.new()
	UI.dark_options(selector)
	selector.name = "PositionPreviewSelector"
	selector.custom_minimum_size = Vector2(220, 36)
	selector.add_item("当前位置 · " + str(Phone.ROLES.get(current_role, current_role)))
	selector.set_item_metadata(0, "")
	box.add_child(selector)
	for view in views:
		if not view is Dictionary:
			continue
		selector.add_item(str(view.get("label", view.get("role", ""))))
		var index := selector.item_count - 1
		selector.set_item_metadata(index, str(view.get("role", "")))
		if str(view.get("role", "")) == selected:
			selector.select(index)
			shown = view
	selector.item_selected.connect(_position_preview_changed.bind(page, selector))
	_quiet_row(box, "位置适配能力", _number(shown.get("ability"), 2))
	var stats: Dictionary = shown.get("stats", {}) if shown.get("stats") is Dictionary else {}
	for axis in {"firepower":"火力", "entrying":"突破", "trading":"补枪", "opening":"首杀", "clutching":"残局", "sniping":"狙击", "utility":"道具"}:
		_quiet_row(box, str({"firepower":"火力", "entrying":"突破", "trading":"补枪", "opening":"首杀", "clutching":"残局", "sniping":"狙击", "utility":"道具"}[axis]), _number(stats.get(axis), 1))
	_label(box, "切换预览不会改变阵容。", 12, MUTED)

func _profile() -> void:
	var you: Dictionary = CareerBridge.context.get("player", {})
	var personal := _personal()
	_label(content, str(you.get("name", "我的生涯")), 25)
	var form = personal.get("form_delta")
	var form_text := "%+.1f" % float(form) if typeof(form) in [TYPE_INT, TYPE_FLOAT] else "—"
	_label(content, "%s · %s 岁 · 当前位置能力 %s · 状态 %s" % [Phone.ROLES.get(you.get("role", ""), you.get("role", "")), you.get("age", "—"), personal.get("ability", you.get("ability", "—")), form_text], 14, MUTED)
	_tabs(content, [{"id":"overview", "label":"概览"}, {"id":"growth", "label":"属性培养"}, {"id":"history", "label":"比赛数据"}], profile_tab, _profile_tab)
	if profile_tab == "growth":
		var raw_attributes = personal.get("attributes", {})
		var attributes: Dictionary = raw_attributes if raw_attributes is Dictionary else {}
		var axes: Array = personal.get("axes", attributes.keys())
		var labels: Dictionary = personal.get("axis_labels", {})
		_label(content, "自由属性点 · %d" % CareerBridge.growth_remaining(), 22)
		var allowed: bool = bool(personal.get("growth_allowed", false))
		_label(content, str(personal.get("growth_reason", "")), 13, MUTED)
		if axes.is_empty():
			_label(content, "属性资料正在载入。", 14, MUTED)
		for axis in axes:
			var key := str(axis)
			var row := HBoxContainer.new()
			row.name = "ComputerAttribute_" + key
			row.add_theme_constant_override("separation", 12)
			content.add_child(row)
			_label(row, str(labels.get(key, key)), 14).custom_minimum_size.x = 86
			var pending := int(CareerBridge.growth_draft.get(key, 0))
			var raw_value = attributes.get(key)
			var has_value: bool = typeof(raw_value) in [TYPE_INT, TYPE_FLOAT]
			var value := float(raw_value) if has_value else 0.0
			var meter := ProgressBar.new()
			meter.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			meter.custom_minimum_size = Vector2(180, 8)
			meter.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			meter.show_percentage = false
			meter.value = value + pending
			meter.add_theme_stylebox_override("background", UI.style(Color("e8eadf"), 0, 4))
			meter.add_theme_stylebox_override("fill", UI.style(Color("8daf98"), 0, 4))
			row.add_child(meter)
			var value_label := _label(row, ("%.0f%s" % [value, " +%d" % pending if pending > 0 else ""]) if has_value else "—", 14)
			value_label.name = "AttributeValue"
			value_label.custom_minimum_size.x = 66
			value_label.size_flags_horizontal = Control.SIZE_SHRINK_END
			var minus := UI.compact(_button(row, "−", CareerBridge.growth_adjust.bind(key, -1)))
			minus.name = "AttributeMinus_" + key
			minus.custom_minimum_size = Vector2(34, 30)
			minus.disabled = not allowed or not has_value or pending <= 0
			var plus := UI.compact(_button(row, "+", CareerBridge.growth_adjust.bind(key, 1)))
			plus.name = "AttributePlus_" + key
			plus.custom_minimum_size = Vector2(34, 30)
			plus.disabled = not allowed or not has_value or CareerBridge.growth_remaining() <= 0 or value + pending >= 100
		var actions := HBoxContainer.new()
		content.add_child(actions)
		var confirm := _button(actions, "确认加点", _commit_growth)
		confirm.name = "ComputerGrowthCommit"
		UI.primary(confirm)
		confirm.disabled = not allowed or CareerBridge.growth_draft.is_empty()
		_button(actions, "清空本次分配", CareerBridge.growth_clear, false)
		_label(content, "手机和电脑使用同一份属性与点数。", 12, MUTED)
		return
	if profile_tab == "overview":
		var raw_playing = personal.get("playing_attributes", personal.get("attributes", {}))
		var playing: Dictionary = raw_playing if raw_playing is Dictionary else {}
		_position_preview(content, personal, str(you.get("role", "")), playing, "profile")
	var raw_stats = personal.get("stats", {})
	var stats: Dictionary = raw_stats if raw_stats is Dictionary else {}
	var metrics := HBoxContainer.new()
	metrics.add_theme_constant_override("separation", 32)
	content.add_child(metrics)
	for stat in [{"id":"rating", "label":"Rating", "format":"%.2f"}, {"id":"adr", "label":"ADR", "format":"%.1f"}, {"id":"kast", "label":"KAST", "format":"%.1f%%"}, {"id":"maps", "label":"地图", "format":"%.0f"}]:
		var box := VBoxContainer.new()
		box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		metrics.add_child(box)
		_label(box, str(stat["label"]), 12, MUTED)
		var raw_amount = stats.get(str(stat["id"]))
		var has_amount: bool = typeof(raw_amount) in [TYPE_INT, TYPE_FLOAT]
		var amount := float(raw_amount) if has_amount else 0.0
		if stat["id"] == "kast":
			amount *= 100 if amount <= 1 else 1
		_label(box, str(stat["format"]) % amount if has_amount and int(stats.get("maps", 0)) > 0 else "—", 25)
	if stats.has("k"):
		_quiet_row(content, "K / D / A", "%s / %s / %s" % [stats.get("k", 0), stats.get("d", 0), stats.get("a", 0)])
	_quiet_row(content, "个人余额", "¥ %s" % personal.get("personal_money", CareerBridge.context.get("money", 0)))
	_quiet_row(content, "所属战队", str(CareerBridge.context.get("team", {}).get("name", "")))
	_label(content, "最近职业比赛", 18)
	for game in CareerBridge.context.get("recent_matches", []):
		_button(content, "%s · %s / %s · %s" % [game.get("date", ""), game.get("team_a", ""), game.get("team_b", ""), str(game.get("series", ""))], _load_detail.bind("match", str(game.get("id", ""))), false)
	if CareerBridge.context.get("recent_matches", []).is_empty():
		_label(content, "还没有比赛记录，第一场后会显示你的数据。", 14, MUTED)
	if profile_tab == "overview":
		_button(content, "分配自由属性点", _profile_tab.bind("growth"), false)

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
	return str({"consumer":"消费级", "industrial":"工业级", "milspec":"军规级", "restricted":"受限", "classified":"保密", "covert":"隐秘", "rare":"罕见特殊", "extraordinary":"非凡"}.get(value, value))

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
	_label(parent, "图片暂缺 · " + str(row.get("weapon", "")), 11, MUTED)

func _open_skin(row: Dictionary, inventory: bool) -> void:
	selected_skin = row.duplicate(true)
	selected_skin["_inventory"] = inventory
	_rebuild()

func _market() -> void:
	var shop := _skins()
	_label(content, "饰品市场", 25)
	var wallet = shop.get("personal_money", CareerBridge.context.get("money", 0))
	_quiet_row(content, "个人余额", "%d 游戏币" % int(wallet) if market_tab == "packs" else "¥ %s" % wallet)
	_tabs(content, [{"id":"market", "label":"市场"}, {"id":"inventory", "label":"我的库存"}, {"id":"cases", "label":"武器箱"}, {"id":"packs", "label":"职业配装"}], market_tab, _market_tab)
	if shop.is_empty():
		_label(content, "饰品资料正在载入。", 14, MUTED)
		return
	if market_tab == "packs":
		skin_bundles.render(self, content, shop)
		return
	var pending = shop.get("pending")
	if pending is Dictionary and not pending.is_empty():
		var reveal := UI.card(content)
		if case_room.is_running():
			_label(reveal, "正在开箱……", 20)
			_label(reveal, "结果已保存，轮播结束后可处理饰品。", 13, MUTED)
		else:
			_label(reveal, "开箱结果 · " + str(pending.get("name", "饰品")), 20)
			_label(reveal, "结果已保存，关闭窗口也不会重新抽取。", 13, MUTED)
			_skin_art(reveal, pending)
			var decisions := HBoxContainer.new()
			reveal.add_child(decisions)
			var keep := _button(decisions, "放入库存", _skin_command.bind("keep", {}))
			UI.primary(keep)
			keep.set_meta("case_gate", true)
			var cash := _button(decisions, "立即出售 · ¥%s" % pending.get("sell", 0), _skin_command.bind("cash", {}))
			cash.set_meta("case_gate", true)
	if not selected_skin.is_empty():
		var item := selected_skin
		var owned := bool(item.get("_inventory", false))
		_button(content, "‹ 返回列表", _market_tab.bind(market_tab), false)
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
		_label(info, str(item.get("name", "饰品")), 21)
		_label(info, _rarity_label(str(item.get("rarity", ""))), 13, _rarity_color(str(item.get("rarity", ""))))
		_quiet_row(info, "磨损", str(item.get("wear_name", item.get("wear", "—"))))
		_label(info, "¥ %s" % item.get("spot", item.get("buy", 0)), 25)
		if owned:
			for side in item.get("sides", []):
				var equipped: Dictionary = shop.get("equipped_" + str(side), {})
				var active: bool = str(equipped.get(str(item.get("slot", "")), "")) == str(item.get("id", ""))
				_button(info, ("卸下 " if active else "装备 ") + str(side).to_upper(), _skin_command.bind("equip", {"id":item.get("id", ""), "side":side, "off":active}))
			_button(info, "出售 · ¥%s" % item.get("sell", 0), _skin_command.bind("sell", {"id":item.get("id", "")}))
		else:
			var purchase := _button(info, "购买并入库", _skin_command.bind("buy", {"id":item.get("id", "")}))
			UI.primary(purchase)
			purchase.disabled = float(shop.get("personal_money", CareerBridge.context.get("money", 0))) < float(item.get("spot", item.get("buy", 0)))
		return
	if market_tab == "cases":
		for case_row in shop.get("cases", []):
			var case_box := UI.card(content)
			_label(case_box, str(case_row.get("name", "武器箱")), 18)
			var cost := int(case_row.get("price", 0)) + int(case_row.get("key", 0))
			_label(case_box, "武器箱与钥匙 · ¥%d" % cost, 14, MUTED)
			var open := _button(case_box, "开箱", _skin_command.bind("case", {"id":case_row.get("id", "")}))
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
		hit_area.tooltip_text = str(item.get("name", "饰品"))
		hit_area.gui_input.connect(_skin_card_input.bind(item, market_tab == "inventory"))
		_skin_art(card, item)
		var name_button := _button(card, str(item.get("name", "饰品")), _open_skin.bind(item, market_tab == "inventory"), false)
		UI.transparent(name_button)
		name_button.add_theme_font_size_override("font_size", 13)
		_label(card, _rarity_label(str(item.get("rarity", ""))) + " · " + str(item.get("wear_name", item.get("wear", ""))), 12, _rarity_color(str(item.get("rarity", ""))))
		_quiet_row(card, "", "¥ %s" % item.get("spot", item.get("buy", 0)))
		var stripe := ColorRect.new()
		stripe.color = _rarity_color(str(item.get("rarity", "")))
		stripe.custom_minimum_size.y = 3
		stripe.mouse_filter = Control.MOUSE_FILTER_IGNORE
		card.add_child(stripe)
	if rows.is_empty():
		_label(content, "库存还没有饰品。", 14, MUTED)

func _skin_card_input(event: InputEvent, item: Dictionary, inventory: bool) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_open_skin(item, inventory)
		get_viewport().set_input_as_handled()

func _open_mail(row: Dictionary) -> void:
	selected_mail = row.duplicate(true)
	page_scroll["mail"] = 0
	_rebuild()

func _mail() -> void:
	var inbox: Array = []
	for row in CareerBridge.context.get("inbox", []):
		if row.get("kind") not in ["news", "awards", "top20"] and not (row.get("kind") == "notification" and row.has("publication_key")):
			inbox.append(row)
	if selected_mail.is_empty():
		_label(content, "邮件", 25)
		_label(content, "收件箱", 13, MUTED)
		if inbox.is_empty():
			_label(content, "收件箱很安静。新的赛事邀请会出现在这里。", 14, MUTED)
		for row in inbox:
			var subject := Locale.field(row, "title", str(row.get("evname", "邮件")))
			var button := _button(content, subject + "\n" + str(row.get("date", "")) + " · " + Phone._mail_status(str(row.get("status", ""))), _open_mail.bind(row), false)
			button.alignment = HORIZONTAL_ALIGNMENT_LEFT
			button.name = "ComputerMail_" + str(row.get("id", "")).validate_node_name()
			UI.transparent(button)
			button.add_theme_font_size_override("font_size", 14)
		return
	var letter := selected_mail
	for row in inbox:
		if str(row.get("id", "")) == str(letter.get("id", "")):
			letter = row
			break
	_label(content, "教练的邮件" if letter.get("kind") == "invite" else "俱乐部邮件", 22)
	var paper := UI.card(content)
	_label(paper, Locale.field(letter, "title", str(letter.get("evname", "邮件"))), 20)
	_label(paper, str(letter.get("date", "")), 12, MUTED)
	_label(paper, Locale.field(letter, "body"), 15)

	if not str(letter.get("evname", "")).is_empty():
		_label(paper, str(letter.get("evname", "")) + " · " + str(letter.get("dates", [])), 14, MUTED)
	if letter.get("kind") == "invite" and letter.get("status") == "open":
		var actions := HBoxContainer.new()
		content.add_child(actions)
		UI.primary(_button(actions, "参加这场赛事", _mail_action.bind("accept", letter)))
		_button(actions, "这次先不报名", _mail_action.bind("decline", letter))
	elif letter.get("kind") == "contract" and letter.get("status") == "open":
		_label(content, "接受邀请后仍会让你确认最终去留，不会直接自动离队。", 13, MUTED)
		UI.primary(_button(content, "继续加盟决定" if letter.get("decision_pending", false) else "查看加盟机会", _mail_action.bind("accept", letter)))
		_button(content, "婉拒邀请", _mail_action.bind("decline", letter))
	elif letter.get("status") == "open" and not str(letter.get("accept_action", "")).is_empty():
		UI.primary(_button(content, "接受邀请", _mail_action.bind("accept", letter)))
		_button(content, "婉拒邀请", _mail_action.bind("decline", letter))
	elif letter.get("kind") == "contract" and not CareerBridge.context.get("stories", []).is_empty():
		_button(content, "处理当前加盟决定", _open_phone.bind("stories"), false)
	else:
		_label(content, Phone._mail_status(str(letter.get("status", ""))), 13, MUTED)

func _language_changed() -> void:
	rendered_context = ""
	call_deferred("_rebuild")

func _mail_action(action: String, letter: Dictionary) -> void:
	if action == "accept" and bool(letter.get("decision_pending", false)):
		_open_phone("stories")
		return
	var path := str(letter.get(action + "_action", "/api/3d/mail/" + action))
	if path in ["/api/3d/mail/accept", "/api/3d/mail/decline"]:
		_device_command(path, {"id":str(letter.get("id", ""))})

func _calendar_select_day(value: String) -> void:
	selected_date = value
	_rebuild()

func _shift_calendar_month(amount: int) -> void:
	var year := int(calendar_month.left(4))
	var month_number := int(calendar_month.right(2)) + amount
	if month_number < 1:
		year -= 1
		month_number = 12
	elif month_number > 12:
		year += 1
		month_number = 1
	calendar_month = "%04d-%02d" % [year, month_number]
	_rebuild()

func _calendar() -> void:
	var current := str(CareerBridge.context.get("date", ""))
	if current.is_empty():
		return
	if selected_date.is_empty() or selected_date < current:
		selected_date = CareerBridge.add_days(current, 1)
	if calendar_month.is_empty():
		calendar_month = selected_date.left(7)
	_label(content, "日历", 25)
	_label(content, "选一天，在那天的早晨醒来。", 14, MUTED)
	var header := HBoxContainer.new()
	content.add_child(header)
	UI.transparent(UI.compact(_button(header, "‹", _shift_calendar_month.bind(-1), false)))
	_label(header, calendar_month, 18).horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	UI.transparent(UI.compact(_button(header, "›", _shift_calendar_month.bind(1), false)))
	var columns := HBoxContainer.new()
	columns.add_theme_constant_override("separation", 32)
	content.add_child(columns)
	var grid := GridContainer.new()
	grid.columns = 7
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	grid.add_theme_constant_override("h_separation", 5)
	grid.add_theme_constant_override("v_separation", 5)
	columns.add_child(grid)
	for weekday in ["日", "一", "二", "三", "四", "五", "六"]:
		_label(grid, weekday, 12, MUTED).horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var first := Time.get_datetime_dict_from_datetime_string(calendar_month + "-01T00:00:00", true)
	for _blank in range(int(first.get("weekday", 0))):
		_label(grid, " ")
	for day in range(1, Phone._days_in_month(calendar_month) + 1):
		var stamp := "%s-%02d" % [calendar_month, day]
		var button := _button(grid, str(day), _calendar_select_day.bind(stamp), false)
		button.custom_minimum_size = Vector2(42, 40)
		UI.transparent(button)
		button.disabled = stamp < current or stamp.left(4) != current.left(4)
		if stamp == selected_date:
			button.add_theme_stylebox_override("normal", UI.style(UI.MINT, 5, 8))
	var day_box := VBoxContainer.new()
	day_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	day_box.add_theme_constant_override("separation", 13)
	columns.add_child(day_box)
	_label(day_box, selected_date, 19)
	_quiet_row(day_box, "醒来时间", "08:00")
	UI.primary(_button(day_box, "睡到这一天早上", CareerBridge.calendar.bind(selected_date, true)))
	_button(day_box, "睡到明早", CareerBridge.calendar.bind(CareerBridge.add_days(current, 1), true))
	_label(day_box, "比赛和待处理事件会让时间暂停。", 12, MUTED)
	if not CareerBridge.pending_target.is_empty() and CareerBridge.pending_target > current:
		_button(day_box, "继续到 " + CareerBridge.pending_target, CareerBridge.calendar.bind(CareerBridge.pending_target, true))
	var next_game := match_center.current_game()
	if not next_game.is_empty():
		var match_card := UI.card(content)
		match_card.name = "CalendarCareerMatch"
		_label(match_card, "今天的比赛" if next_game.get("due", false) else "下一场比赛", 18)
		_label(match_card, "%s · %s\n对阵 %s" % [next_game.get("date", ""), next_game.get("event", ""), next_game.get("opponent", "")], 15)
		var attendance := match_center.attendance()
		if not str(attendance.get("display_name", "")).is_empty():
			_label(match_card, "比赛地点 · " + str(attendance.display_name), 15)
			_label(match_card, str(attendance.get("instruction", "")), 13, MUTED)
		var participate := _button(match_card, "亲自参赛" if next_game.get("due", false) else "亲自参赛 · 睡到比赛日", match_center.prepare_real.bind(str(next_game.get("id", ""))))
		participate.name = "CalendarAttendMatch"
		UI.primary(participate)
	_label(content, "这个月的比赛", 18)
	for item in CareerBridge.context.get("calendar_events", []):
		if str(item.get("date", "")).begins_with(calendar_month):
			_button(content, str(item.get("date", "")) + " · " + str(item.get("name", "")), _load_detail.bind("event", str(item.get("id", ""))), false)

func _ladder_state() -> Dictionary:
	return CareerBridge.context.get("ladder", {})

func _ladder() -> void:
	if not report.is_empty():
		_render_report(report)
		return
	var ladder := _ladder_state()
	if ladder.is_empty():
		_label(content, "天梯资料还没有载入。")
		return
	var record: Dictionary = ladder.get("player", {})
	_label(content, "%s  ·  Elo %s  ·  %s 胜 / %s 负" % [CareerBridge.context.get("player", {}).get("name", ""), record.get("elo", "—"), record.get("wins", 0), record.get("losses", 0)], 19)
	_label(content, "独立天梯积分 · 可模拟比赛，也可进入 CS2 亲自打", 13, MUTED)
	var lobby = ladder.get("lobby")
	if lobby is Dictionary and lobby.get("mode", "rank") not in ["rank", "fpl"]:
		_label(content, "当前共享房间是自定义对局；天梯身份不变，先处理该房间。", 16, MUTED)
		_button(content, "打开自定义房间", _navigate.bind("custom"), false)
		if lobby.get("phase") == "finished": _button(content, "开始天梯匹配", _ladder_command.bind("matchmake", {}))
		return
	if not lobby is Dictionary or lobby.is_empty():
		abandon_lobby_id = ""
		_button(content, "开始匹配", _ladder_command.bind("matchmake", {}))
	else:
		var phase := str(lobby.get("phase", ""))
		if abandon_lobby_id != str(lobby.get("id", "")):
			abandon_lobby_id = ""
		if phase == "finished":
			var saved: Dictionary = lobby.get("result", {})
			if not saved.is_empty():
				_button(content, "打开本场战报", _open_report.bind(saved), false)
			_button(content, "开始下一场匹配", _ladder_command.bind("matchmake", {}))
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
				_label(content, str(lobby.get("map", "")).capitalize() + " · 选择开场阵营", 21)
				_button(content, "CT · 防守方", _ladder_command.bind("side", {"side":"ct"})).disabled = not human
				_button(content, "T · 进攻方", _ladder_command.bind("side", {"side":"t"})).disabled = not human
			elif phase == "ready":
				_label(content, "地图：" + str(lobby.get("map", "")).capitalize(), 21)
				var ct_team := str(lobby.get("ct", "a"))
				_label(content, "开场：%s 队 CT · %s 队 T" % [ct_team.to_upper(), "B" if ct_team == "a" else "A"], 15, MUTED)
				var ready_actions := HBoxContainer.new()
				ready_actions.add_theme_constant_override("separation", 12)
				content.add_child(ready_actions)
				_button(ready_actions, "模拟这场天梯比赛", _ladder_command.bind("simulate", {"lobby_id":lobby.get("id", "")}))
				var launch := _button(ready_actions, "进入 CS2", _ladder_command.bind("launch", {"lobby_id":lobby.get("id", "")}))
				launch.name = "ComputerLadderLaunchCS2"
				UI.primary(launch)
				launch.disabled = not bool(cs2_status.get("can_launch", false))
				var rts := _button(ready_actions, "RTS 指挥这场天梯", Callable(rts_room, "open_ladder"), false)
				rts.name = "LadderPlayRTS"
				rts.disabled = not rts_room.has_method("ladder_eligible") or not bool(rts_room.call("ladder_eligible"))
				if rts.disabled: _label(content, "本图暂不支持 RTS，可以模拟或进入 CS2。", 12, MUTED)
				var config: Dictionary = cs2_status.get("config", ladder.get("config", {}))
				if not config.get("ready", false):
					_label(content, str(config.get("reason", "正在检查 CS2 环境。")), 13, MUTED)
			elif phase == "rts":
				_label(content, "RTS 对局待完成", 20)
				var resume_rts := _button(content, "继续这场 RTS 天梯", Callable(rts_room, "open_ladder"), false)
				resume_rts.name = "LadderResumeRTS"
			elif phase in ["starting", "playing", "waiting", "started", "launched", "live"]:
				var phase_label := "正在准备 CS2 对局。" if phase == "starting" else "等待 CS2 对局战绩回传。"
				if phase == "starting" and cs2_status.get("status") == "failed":
					phase_label = "CS2 对局启动未完成。"
				elif cs2_status.get("cs2_running") == true:
					phase_label = "正在 CS2 中进行这场比赛。"
				_label(content, phase_label, 20)
			else:
				_label(content, "当前房间无法在这台电脑继续，请结束原房间后再匹配。", 16, MUTED)
			if phase in ["draft", "veto"]:
				_render_rosters(lobby)
			if phase != "draft":
				ladder_room.records(lobby)
			if phase in ["draft", "veto", "side", "ready"] and not cs2_status.get("cs2_running", false):
				_button(content, "离开当前匹配房间", _ladder_command.bind("cancel", {}))
	if not cs2_status.is_empty():
		var game_status := str(cs2_status.get("status", ""))
		if game_status in ["waiting", "failed", "blocked"]:
			_label(content, str(cs2_status.get("reason", "等待 CS2 比赛结果。")), 14, MUTED)
		if cs2_status.get("can_retry", false):
			var retry := _button(content, "重试进入 CS2", _ladder_command.bind("launch", {"lobby_id":cs2_status.get("lobby_id", "")}))
			retry.name = "ComputerLadderRetryCS2"
		if cs2_status.get("can_collect", false):
			var collect := _button(content, "录入战绩" if game_status != "failed" else "重试录入战绩", _ladder_command.bind("collect", {"lobby_id":cs2_status.get("lobby_id", "")}))
			collect.name = "ComputerLadderCollectCS2"
		if _can_abandon_ladder():
			if abandon_lobby_id == str(cs2_status.get("lobby_id", "")):
				var confirmation := UI.card(content, true)
				_label(confirmation, "放弃这场天梯？", 18)
				_label(confirmation, "关闭这个未录入房间，不计算胜负或天梯积分。之后不能再为这场录入战绩。", 14, MUTED)
				var choices := HBoxContainer.new()
				confirmation.add_child(choices)
				var abandon := _button(choices, "确认放弃，不计分", _confirm_ladder_abandon)
				abandon.name = "ComputerLadderConfirmAbandon"
				_button(choices, "继续等待", _dismiss_ladder_abandon, false)
			else:
				var abandon := _button(content, "放弃本场天梯", _request_ladder_abandon)
				abandon.name = "ComputerLadderAbandon"
	_label(content, "最近天梯比赛", 21)
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
		_label(box, "%s 队 · 队长 %s" % [str(side).to_upper(), ladder_room.player_name(lobby, captain)], 16, UI.GREEN)
		for index in range(5):
			var team: Array = lobby.get(side, [])
			if index >= team.size():
				_label(box, "%d · 等待选人" % (index + 1), 13, MUTED)
				continue
			var pid: String = team[index]
			var player: Dictionary = roster.get(pid, {})
			_label(box, "%s%s · Elo %s%s" % [player.get("name", ""), " ★ 你" if pid == lobby.get("human_id") else "",
				lobby.get("ratings", {}).get(pid, "—"), " · " + str(LadderRoom.ROLES.get(player.get("role", ""), "")) if lobby.get("role_assignment_version") else ""], 13)

func _ladder_command(action: String, extra: Dictionary) -> bool:
	var body := extra.duplicate(true)
	body["revision"] = int(_ladder_state().get("revision", 0))
	notice = ""
	# Automatic captain turns and CS2 launch already have their own visible flow.
	var accepted: bool = CareerBridge.command("/api/3d/ladder/" + action, body) if action in ["advance", "launch", "collect"] else _command("/api/3d/ladder/" + action, body)
	if not accepted:
		notice = "操作暂未发出，请等当前操作完成后重试。"
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
		notice = "请先退出 CS2，核验进程状态后再放弃本场。"
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
		_label(content, "请到俱乐部工作站约训练赛。")
		return
	if not report.is_empty():
		_render_report(report)
		return
	var scrims: Dictionary = CareerBridge.context.get("scrims", {})
	_label(content, "约一场训练赛", 26)
	_label(content, "本地模拟训练赛。比赛保存战报，不计职业赛事奖金、排名或能力奖励。", 15, MUTED)
	var opponents: Array = scrims.get("opponents", [])
	if opponents.is_empty():
		_label(content, "暂时没有可约的对手。")
	else:
		var form := UI.card(content, true)
		_label(form, "对手", 15, MUTED)
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
		_label(form, "日期", 15, MUTED)
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
		_button(dates, "今天", _set_scrim_date.bind(current), false)
		_button(dates, "明天", _set_scrim_date.bind(CareerBridge.add_days(current, 1)), false)
		_label(form, "地图", 15, MUTED)
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
		_button(form, "确认预约训练赛", _schedule_scrim).disabled = maps.is_empty()
	_label(content, "已约训练赛", 21)
	for item in scrims.get("scheduled", []):
		var card := UI.card(content, true)
		_label(card, "%s · %s · %s" % [item.get("date", ""), item.get("opponent", ""), str(item.get("map", "")).capitalize()], 19)
		if str(item.get("date", "")) <= str(CareerBridge.context.get("date", "")):
			_button(card, "开始模拟训练赛", _command.bind("/api/3d/scrim/simulate", {"id":item.get("id", "")}))
		else:
			_label(card, "到约定日期后可开赛。", 15, MUTED)
	if scrims.get("scheduled", []).is_empty():
		_label(content, "还没有约好的训练赛。", 15, MUTED)
	_label(content, "训练赛战报", 21)
	for item in scrims.get("history", []):
		var saved: Dictionary = item.get("report", {})
		_button(content, _report_title(saved), _open_report.bind(saved), false)

func _set_scrim_date(value: String) -> void:
	scrim_date = value
	page_scroll["scrim"] = scroll.scroll_vertical
	_rebuild()

func _schedule_scrim() -> void:
	_command("/api/3d/scrim/schedule", {"opponent_id":opponent_id, "date":scrim_date, "map":scrim_map})

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
	_button(content, "‹ 返回", _back, false)
	var mp: Dictionary = value.get("map", {})
	var pid := str(value.get("human_id", ""))
	var changes: Dictionary = value.get("changes", {})
	if changes.has(pid):
		_label(content, "你的天梯积分：%+d" % int(changes[pid]), 19, UI.GREEN)
	var teams := _report_teams(value)
	var game := {"team_a":teams[0] if teams.size() > 0 else "", "team_b":teams[1] if teams.size() > 1 else "", "date":value.get("date", ""), "series":mp.get("score", ""), "winner":mp.get("winner", ""), "maps":[mp]}
	MatchReport.mount(content, game, {}, pid, func(id: String): _load_detail("player", id))

func _events() -> void:
	_label(content, "赛事中心", 24)
	_tabs(content, [{"id":"calendar", "label":"赛程与战报"}, {"id":"teams", "label":"战队资料"}, {"id":"players", "label":"选手数据"}], events_tab, _events_tab)
	if events_tab == "teams":
		for team in CareerBridge.context.get("teams", []):
			TeamVisuals.button_logo(_button(content, "#%s  %s  ·  %s" % [team.get("rank", "—"), team.get("name", ""), team.get("region", "")], _load_detail.bind("team", str(team.get("id", ""))), false), str(team.get("name", "")))
	elif events_tab == "players":
		_render_player_directory()
	else:
		_label(content, "赛事日程", 19)
		for item in CareerBridge.context.get("calendar_events", []):
			_button(content, "%s  ·  %s%s" % [item.get("date", ""), item.get("name", ""), " · 已报名" if item.get("registered", false) else ""], _load_detail.bind("event", str(item.get("id", ""))), false)
		_label(content, "最近比赛", 19)
		for game in CareerBridge.context.get("recent_matches", []):
			_button(content, "%s · %s / %s · %s" % [game.get("date", ""), game.get("team_a", ""), game.get("team_b", ""), str(game.get("series", ""))], _load_detail.bind("match", str(game.get("id", ""))), false)

func _events_tab(value: String) -> void:
	events_tab = value
	page_scroll["events"] = 0
	_rebuild()

func _render_player_directory() -> void:
	_label(content, "本赛季选手数据", 21)
	_label(content, str(players_data.get("note", "本赛季对 VRS Top30 对手的已记录地图；无样本不列入。")), 13, MUTED)
	var filter_row := HBoxContainer.new()
	content.add_child(filter_row)
	var search := LineEdit.new()
	UI.line_edit(search)
	search.text = players_search
	search.placeholder_text = "选手或战队名称"
	search.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	filter_row.add_child(search)
	_button(filter_row, "搜索", func():
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
		_label(box, "Rating %s · ADR %s · KAST %s · %s 图 · %s / %s / %s" % [_number(player.get("rating"), 2), _number(player.get("adr"), 1), _percentage(player.get("kast")), player.get("maps", 0), player.get("k", "—"), player.get("d", "—"), player.get("a", "—")], 14)
	if players_data.get("rows", []).is_empty():
		_label(content, "正在读取选手数据……" if players_data.is_empty() else "没有符合条件的已记录选手。", 14, MUTED)
	var pages := HBoxContainer.new()
	content.add_child(pages)
	_button(pages, "上一页", _players_page.bind(-1), false).disabled = players_page <= 1
	_label(pages, "%s / %s" % [players_page, players_data.get("pages", 1)])
	_button(pages, "下一页", _players_page.bind(1), false).disabled = players_page >= int(players_data.get("pages", 1))
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
	TeamVisuals.banner(content, str(detail.get("name", "战队")), team_name, "战队资料")
	for field in ["region", "rank", "vrs", "money"]:
		if detail.has(field):
			_label(content, "%s：%s" % [{"region":"赛区", "rank":"排名", "vrs":"VRS", "money":"资金"}.get(field, field), str(detail[field])])
	var roster: Array = detail.get("roster", detail.get("players", []))
	for member in roster:
		if member is Dictionary:
			TeamVisuals.button_logo(_button(content, "%s · %s · 能力 %s" % [member.get("name", ""), Phone.ROLES.get(member.get("role", ""), member.get("role", "")), member.get("ability", "—")], _load_detail.bind("player", str(member.get("player_id", member.get("id", ""))))), team_name)

func _player() -> void:
	TeamVisuals.banner(content, str(detail.get("name", "选手")), str(detail.get("team", detail.get("last_team", ""))), str(detail.get("team", detail.get("last_team", ""))))
	_label(content, str(Phone.ROLES.get(detail.get("role", ""), detail.get("role", ""))) + (" · 历史资料" if detail.get("historical", false) else ""), 17, MUTED)
	if not str(detail.get("team_id", "")).is_empty():
		TeamVisuals.button_logo(_button(content, str(detail.get("team", "")), _load_detail.bind("team", str(detail["team_id"])), false), str(detail.get("team", "")))
	for field in ["age", "ability", "command", "form_delta"]:
		if detail.has(field) and detail[field] != null:
			_label(content, "%s：%s" % [{"team":"战队", "age":"年龄", "ability":"能力", "command":"指挥", "form_delta":"状态"}.get(field, field), str(detail[field])])
	_tabs(content, [{"id":"overview", "label":"概览"}, {"id":"matches", "label":"比赛记录"}, {"id":"honours", "label":"荣誉"}], player_tab, _player_tab)
	var ranges := HBoxContainer.new()
	content.add_child(ranges)
	_label(ranges, "统计范围", 13, MUTED)
	for scope in [{"id":"30d", "label":"最近30天"}, {"id":"season", "label":"本赛季"}, {"id":"all", "label":"全部历史"}]:
		var button := _button(ranges, str(scope["label"]), _player_range.bind(str(scope["id"])), false)
		if player_span == str(scope["id"]):
			UI.transparent(button)
			button.add_theme_stylebox_override("normal", UI.style(UI.MINT, 7, 8))
	_label(content, "%s 张已保存地图 · 不补造缺失数据" % detail.get("total", 0), 13, MUTED)
	if player_tab == "honours":
		_player_honours()
		return
	var summary: Dictionary = detail.get("summary", {})
	_label(content, "Rating %s · ADR %s · KAST %s · %s 图 / %s 回合" % [_number(summary.get("rating"), 2), _number(summary.get("adr"), 1), _percentage(summary.get("kast")), summary.get("maps", 0), summary.get("rounds", 0)], 19)
	_label(content, "K / D / A · %s / %s / %s" % [summary.get("k", "—"), summary.get("d", "—"), summary.get("a", "—")], 15, MUTED)
	if player_tab == "overview":
		var stats: Dictionary = detail.get("stats", {}) if detail.get("stats") is Dictionary else {}
		_position_preview(content, detail, str(detail.get("role", "")), stats, "player")
		if not detail.get("historical", false) and not stats.is_empty():
			var box := UI.card(content)
			_label(box, "实际位置属性", 18)
			for axis in {"firepower":"枪法", "entrying":"突破", "trading":"补枪", "opening":"首杀", "clutching":"残局", "sniping":"狙击", "utility":"道具", "command":"指挥"}:
				if stats.get(axis) != null:
					_quiet_row(box, str({"firepower":"枪法", "entrying":"突破", "trading":"补枪", "opening":"首杀", "clutching":"残局", "sniping":"狙击", "utility":"道具", "command":"指挥"}[axis]), _number(stats.get(axis), 1))
		_label(content, "最近10图", 19)
	_render_player_matches(detail.get("records", []) if player_tab == "matches" else detail.get("recent", []))
	if player_tab == "matches":
		var pagination := HBoxContainer.new()
		content.add_child(pagination)
		var pages := maxi(1, ceili(float(detail.get("total", 0)) / maxf(1, float(detail.get("page_size", 20)))))
		_button(pagination, "上一页", _player_page.bind(-1), false).disabled = player_page <= 1
		_label(pagination, "%s / %s" % [player_page, pages])
		_button(pagination, "下一页", _player_page.bind(1), false).disabled = player_page >= pages

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
		_label(content, "这个范围内没有已保存的地图记录。", 14, MUTED)
	for item in records:
		var box := UI.card(content)
		var row := HBoxContainer.new()
		box.add_child(row)
		_button(row, "%s · %s" % [item.get("date", ""), item.get("event", "")], _load_detail.bind("event", str(item.get("event_id", ""))), false).size_flags_horizontal = Control.SIZE_EXPAND_FILL
		_button(row, "%s · %s · %s" % [str(item.get("map", "")).capitalize(), item.get("opponent", ""), str(item.get("score", ""))], _load_detail.bind("match", str(item.get("match_id", ""))), false)
		_label(box, "%s / %s / %s · Rating %s · ADR %s · KAST %s" % [item.get("k", "—"), item.get("d", "—"), item.get("a", "—"), _number(item.get("rating"), 2), _number(item.get("adr"), 1), _percentage(item.get("kast"))], 14)

func _player_honours() -> void:
	if not str(detail.get("honours_notice", "")).is_empty():
		_label(content, str(detail["honours_notice"]), 14, MUTED)
		return
	var honours: Dictionary = detail.get("honours", {})
	for group in ["titles", "mvp", "evp", "top20"]:
		var rows: Array = honours.get(group, [])
		_label(content, str({"titles":"冠军", "mvp":"MVP", "evp":"EVP", "top20":"年度 Top20"}[group]) + " · " + str(rows.size()), 19)
		for item in rows:
			if group == "top20":
				_label(content, "%s 年 · #%s · Rating %s" % [item.get("year", ""), item.get("rank", ""), _number(item.get("rating"), 2)], 14)
			else:
				_label(content, "%s · %s%s" % [item.get("date", ""), item.get("event", item.get("short", "")), " · Rating " + _number(item.get("rating"), 2) if item.has("rating") else ""], 14)
		if rows.is_empty():
			_label(content, "暂无记录。", 13, MUTED)

static func _number(value, digits: int = 1) -> String:
	if typeof(value) not in [TYPE_INT, TYPE_FLOAT]:
		return "—"
	return "%.2f" % float(value) if digits == 2 else "%.1f" % float(value)

static func _percentage(value) -> String:
	return "%.1f%%" % (float(value) * 100) if typeof(value) in [TYPE_INT, TYPE_FLOAT] else "—"

func _event() -> void:
	_label(content, str(detail.get("name", "赛事")), 28)
	_label(content, EventFlow.dates_text(detail.get("dates", [])), 17, MUTED)
	for field in ["tier", "format", "prize", "region", "status"]:
		if detail.has(field):
			_label(content, "%s：%s" % [{"tier":"级别", "format":"赛制", "prize":"奖金", "region":"赛区", "status":"状态"}.get(field, field), EventFlow.field_text(field, detail[field])])
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
		notice = "正在开箱……" if case_room.is_running() else str(result.get("reason", result.get("msg", "")))
		if result.get("ok", false):
			selected_skin = {}
		if active_page == "market":
			_rebuild()
	elif not result.get("ok", false):
		notice = str(result.get("msg", result.get("reason", "这次操作没有完成。")))
		_update_status()

func _update_status() -> void:
	if status:
		if case_room.is_running():
			status.text = "正在开箱……"
			return
		status.text = ("正在处理……" if CareerBridge.active_post else "同步资料中……") if CareerBridge.busy else (notice if not notice.is_empty() else CareerBridge.message)

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
		if active_page == "ladder" and cs2_poll <= 0 and (cs2_status.is_empty() or str(cs2_status.get("status", "")) in ["waiting", "failed", "blocked"]):
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
