extends CanvasLayer
## A portrait phone. Career decisions always go to CareerBridge.
const UI = preload("res://scripts/phone_ui.gd")
const Visuals = preload("res://scripts/phone_visuals.gd")
const News = preload("res://scripts/phone_news.gd")
const Social = preload("res://scripts/phone_social.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")
const MatchReport = preload("res://scripts/career_match_report.gd")
const EventFlow = preload("res://scripts/career_event_flow.gd")
const PageProjection = preload("res://scripts/device_projection.gd")
const ActionFeedback = preload("res://scripts/device_action_feedback.gd")
const Fmt = preload("res://scripts/ui_format.gd")
const Kit = preload("res://scripts/ui_kit.gd")
const PAGES := {"home":"主屏", "mail":"邮件", "chat":"聊天", "match":"赛事", "quick":"快速赛季", "calendar":"日历", "profile":"我的", "settings":"设置", "team":"战队", "stories":"队内事件", "player":"选手", "event":"赛事资料", "news":"赛事新闻"}
const APPS := [
	{"id":"mail", "name":"邮件"},
	{"id":"chat", "name":"聊天"},
	{"id":"match", "name":"赛事"},
	{"id":"calendar", "name":"日历"},
	{"id":"profile", "name":"我的"},
	{"id":"settings", "name":"设置"}
]
const ROLES := {"rifle":"步枪手", "awp":"主狙", "entry":"突破手", "lurk":"自由人", "lurker":"自由人", "igl":"指挥", "support":"辅助"}
var screen: Control
var panel: PanelContainer
var content: VBoxContainer
var scroll: ScrollContainer
var title: Label
var status: Label
var clock: Label
var back_button: Button
var home_clock: Label
var heading: MarginContainer
var heading_icon: CenterContainer
var active_page := "home"
var selected_date := ""
var month := ""
var detail: Dictionary = {}
var action_buttons: Array[Button] = []
var nav_buttons: Dictionary = {}
var history: Array[String] = []
var page_scroll: Dictionary = {}
var selected_mail := ""
var selected_mail_detail: Dictionary = {}
var selected_player: Dictionary = {}
var player_range := "season"
var player_page := 1
var news_data: Dictionary = {}
var news_article: Dictionary = {}
var news_category := "all"
var news_page := 1
var selected_event: Dictionary = {}
var selected_team: Dictionary = {}
var selected_contact := ""
var profile_tab := "overview"
var position_preview_roles: Dictionary = {}
var rendered_context := ""
var pending_detail_path := ""
var pending_detail_open := false
var detail_intent_serial := 0
var pending_detail_intent := -1
var _toast_text := ""
var action_feedback: Control

func reset_career_views() -> void:
	_clear_action_feedback()
	detail_intent_serial += 1
	pending_detail_path = ""
	pending_detail_open = false
	selected_date = ""
	month = ""
	detail.clear()
	history.clear()
	page_scroll.clear()
	position_preview_roles.clear()
	selected_mail = ""
	selected_mail_detail.clear()
	selected_player.clear()
	player_range = "season"
	player_page = 1
	news_data.clear()
	news_article.clear()
	news_category = "all"
	news_page = 1
	selected_event.clear()
	selected_team.clear()
	selected_contact = ""
	profile_tab = "overview"
	rendered_context = ""
	_toast_text = ""
	active_page = "home"

func _ready() -> void:
	Locale.changed.connect(_language_changed)
	layer = 30
	process_mode = Node.PROCESS_MODE_ALWAYS
	screen = Control.new()
	screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var phone_theme := Theme.new()
	phone_theme.default_font = UI.font()
	phone_theme.default_font_size = 14
	screen.theme = phone_theme
	add_child(screen)
	var dim := ColorRect.new()
	dim.color = Color(0.015, 0.025, 0.05, 0.72)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	screen.add_child(dim)
	panel = PanelContainer.new()
	panel.name = "PhoneShell"
	panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	var shell_style := UI.style(Color("e3e7db"), 10, 40, Color("bdc6b8"))
	shell_style.set_border_width_all(3)
	shell_style.content_margin_top = 13
	shell_style.content_margin_bottom = 10
	panel.add_theme_stylebox_override("panel", shell_style)
	screen.add_child(panel)
	var shell_layout := VBoxContainer.new()
	shell_layout.add_theme_constant_override("separation", 9)
	panel.add_child(shell_layout)
	var camera_row := HBoxContainer.new()
	camera_row.alignment = BoxContainer.ALIGNMENT_CENTER
	shell_layout.add_child(camera_row)
	var camera := PanelContainer.new()
	camera.custom_minimum_size = Vector2(44, 5)
	camera.add_theme_stylebox_override("panel", UI.style(Color("78907f"), 0, 5))
	camera_row.add_child(camera)
	var glass := PanelContainer.new()
	glass.name = "PhoneScreen"
	glass.size_flags_vertical = Control.SIZE_EXPAND_FILL
	glass.add_theme_stylebox_override("panel", UI.style(UI.CREAM, 0, 29))
	shell_layout.add_child(glass)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 0)
	glass.add_child(layout)
	var status_margin := MarginContainer.new()
	status_margin.add_theme_constant_override("margin_left", 21)
	status_margin.add_theme_constant_override("margin_right", 21)
	status_margin.add_theme_constant_override("margin_top", 13)
	status_margin.add_theme_constant_override("margin_bottom", 8)
	layout.add_child(status_margin)
	var bar := HBoxContainer.new()
	status_margin.add_child(bar)
	clock = UI.label(bar, "", 12, UI.INK)
	clock.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	clock.autowrap_mode = TextServer.AUTOWRAP_OFF
	var status_art := Visuals.status_icons()
	status_art.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	bar.add_child(status_art)
	heading = MarginContainer.new()
	heading.add_theme_constant_override("margin_left", 19)
	heading.add_theme_constant_override("margin_right", 19)
	heading.add_theme_constant_override("margin_top", 10)
	heading.add_theme_constant_override("margin_bottom", 19)
	layout.add_child(heading)
	var header := HBoxContainer.new()
	heading.add_child(header)
	title = UI.label(header, "", 21)
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	title.autowrap_mode = TextServer.AUTOWRAP_OFF
	heading_icon = CenterContainer.new()
	heading_icon.custom_minimum_size = Vector2(26, 26)
	header.add_child(heading_icon)
	scroll = ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	layout.add_child(scroll)
	content = VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 10)
	content.set_meta("phone_edge", true)
	scroll.add_child(content)
	var message_margin := MarginContainer.new()
	message_margin.add_theme_constant_override("margin_left", 19)
	message_margin.add_theme_constant_override("margin_right", 19)
	layout.add_child(message_margin)
	status = UI.label(message_margin, "", 12, UI.MUTED)
	status.max_lines_visible = 2
	var footer := PanelContainer.new()
	var footer_style := UI.style(UI.CREAM, 14, 0)
	footer_style.border_color = UI.LINE
	footer_style.border_width_top = 1
	footer_style.corner_radius_bottom_left = 29
	footer_style.corner_radius_bottom_right = 29
	footer_style.content_margin_top = 9
	footer_style.content_margin_bottom = 12
	footer.add_theme_stylebox_override("panel", footer_style)
	layout.add_child(footer)
	var navigation := HBoxContainer.new()
	navigation.name = "PhoneNavigation"
	navigation.alignment = BoxContainer.ALIGNMENT_CENTER
	navigation.add_theme_constant_override("separation", 38)
	footer.add_child(navigation)
	back_button = _navigation_button(navigation, "返回", "chevron_left", _back)
	_navigation_button(navigation, "主屏", "home", _home)
	action_feedback = ActionFeedback.new()
	action_feedback.top_inset = 60.0
	panel.add_child(action_feedback)
	CareerBridge.changed.connect(_context_changed)
	CareerBridge.status_changed.connect(_update_status)
	CareerBridge.busy_changed.connect(_busy_changed)
	CareerBridge.command_finished.connect(_finished)
	CareerBridge.wake_requested.connect(_wake)
	CareerBridge.growth_changed.connect(_growth_changed)
	get_viewport().size_changed.connect(_resize)
	_resize()
	screen.visible = false

func _resize() -> void:
	# Canvas-items stretch scales the world down in a 720p window. Keep only
	# the phone at its reference pixel size, centred and uniformly fitted.
	var viewport_size := get_viewport().get_visible_rect().size
	var stretch := get_viewport().get_final_transform().get_scale().abs()
	stretch.x = maxf(stretch.x, 0.001)
	stretch.y = maxf(stretch.y, 0.001)
	var available := viewport_size * stretch - Vector2(24, 24)
	# A larger handset: more room for the home widgets and fewer wrapped rows.
	var width := 384.0
	var height := 748.0
	var fit := maxf(0.1, minf(1.0, minf(available.x / width, available.y / height)))
	panel.offset_left = -width / 2
	panel.offset_right = width / 2
	panel.offset_top = -height / 2
	panel.offset_bottom = height / 2
	panel.pivot_offset = Vector2(width, height) / 2
	panel.scale = Vector2(fit / stretch.x, fit / stretch.y)

func present(page: String = "today") -> void:
	if StartGate.requires_creation():
		StartGate.remind()
		Computer.open_app("start", "bedroom")
		return
	if Travel.busy or CareerBridge.sleeping:
		return
	Travel.close_menu()
	detail_intent_serial += 1
	var computer := get_node_or_null("/root/Computer")
	if computer and computer.screen.visible:
		if is_instance_valid(computer.rts_room.session):
			return
		computer.close_computer(false)
	var destination := "home" if page == "today" else page
	if not PAGES.has(destination):
		destination = "home"
	screen.visible = true
	UI.device_open(self, "phone")
	_navigate(destination, false)

func close_phone(release: bool = true) -> void:
	if screen == null:
		return
	_clear_action_feedback()
	detail_intent_serial += 1
	pending_detail_open = false
	page_scroll[active_page] = scroll.scroll_vertical
	screen.visible = false
	if release:
		UI.device_closed(self)

func _navigate(page: String, push: bool = true) -> void:
	if active_page != page and is_instance_valid(action_feedback): action_feedback.clear_notice()
	page_scroll[active_page] = scroll.scroll_vertical
	if active_page != page and push:
		history.append(active_page)
	active_page = page
	_toast_text = ""
	_rebuild()

func _home() -> void:
	history.clear()
	_navigate("home", false)

func _back() -> void:
	if active_page == "home":
		close_phone()
	else:
		_home()

func _context_changed() -> void:
	if active_page == "settings" and Computer.device_settings.dirty:
		return
	if screen.visible and rendered_context != PageProjection.signature(active_page, CareerBridge.context):
		page_scroll[active_page] = scroll.scroll_vertical
		_rebuild()

func _rebuild() -> void:
	var focused := get_viewport().gui_get_focus_owner()
	var focus_text := str(focused.get_meta("focus_key", focused.text)) if focused is Button and content.is_ancestor_of(focused) else ""
	UI.clear(content)
	action_buttons.clear()
	content.add_theme_constant_override("separation", 0 if active_page in ["home", "mail", "chat"] else 10)
	heading.visible = active_page != "home"
	title.text = PAGES.get(active_page, "主屏")
	UI.clear(heading_icon)
	var heading_kind: String = str({"team":"profile", "player":"profile", "event":"match", "stories":"chat", "news":"mail"}.get(active_page, active_page))
	var glyph := Visuals.icon(str(heading_kind), Vector2(16, 16))
	glyph.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	glyph.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	heading_icon.add_child(glyph)
	back_button.disabled = false
	back_button.tooltip_text = "放下手机" if active_page == "home" else "返回主屏"
	scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED if active_page == "home" else ScrollContainer.SCROLL_MODE_AUTO
	rendered_context = PageProjection.signature(active_page, CareerBridge.context)
	_update_status()
	if CareerBridge.context.is_empty() and active_page not in ["home", "settings"]:
		UI.label(content, "生涯正在载入。稍后再打开这个 App。")
	else:
		match active_page:
			"home": _today()
			"mail": _mail()
			"chat": _chat()
			"match": _matches()
			"quick": _quick()
			"calendar": _calendar()
			"profile": _profile()
			"team": _team()
			"player": _player()
			"event": _event()
			"news": _news()
			"stories": _stories()
			"settings": _settings()
	for button in action_buttons:
		if is_instance_valid(button): button.set_meta("career_gate_disabled", button.disabled)
	_busy_changed(CareerBridge.busy)
	scroll.set_deferred("scroll_vertical", int(page_scroll.get(active_page, 0)))
	if not focus_text.is_empty():
		call_deferred("_restore_focus", focus_text)

func _button(parent: Node, text: String, callback: Callable, write: bool = true) -> Button:
	var button := UI.button(parent, text, callback)
	if write:
		action_buttons.append(button)
		button.set_meta("career_gate_disabled", false)
	return button

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

func _route(page: String) -> void:
	_navigate(page)
	if page == "news":
		_load_news(news_category, news_page)

func _navigation_button(parent: Node, caption: String, kind: String, callback: Callable) -> Button:
	var button := UI.button(parent, "", callback)
	UI.transparent(button)
	button.custom_minimum_size = Vector2(78, 36)
	button.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	button.tooltip_text = caption
	button.set_meta("focus_key", "nav:" + kind)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	center.mouse_filter = Control.MOUSE_FILTER_IGNORE
	button.add_child(center)
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_theme_constant_override("separation", 5)
	center.add_child(row)
	var icon := Visuals.icon(kind, Vector2(17, 17))
	icon.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	icon.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(icon)
	var caption_label := UI.label(row, caption, 12, UI.MUTED)
	caption_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caption_label.autowrap_mode = TextServer.AUTOWRAP_OFF
	return button

func _list_row(parent: Node, value: String, subtitle: String, callback: Callable, avatar: String = "", icon_kind: String = "", pending: bool = false, write: bool = false, team: String = "") -> Button:
	var button := _button(parent, "", callback, write)
	UI.transparent(button)
	button.custom_minimum_size.y = 70
	button.tooltip_text = value
	button.set_meta("focus_key", "row:" + value)
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	row.offset_top = 15
	row.offset_bottom = -15
	row.add_theme_constant_override("separation", 11)
	button.add_child(row)
	var club_mark := TeamVisuals.badge(row, team)
	if club_mark == null and (not avatar.is_empty() or not icon_kind.is_empty()):
		var face := PanelContainer.new()
		face.custom_minimum_size = Vector2(36, 36)
		face.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		face.mouse_filter = Control.MOUSE_FILTER_IGNORE
		face.add_theme_stylebox_override("panel", UI.style(UI.MINT, 0, 13))
		row.add_child(face)
		var center := CenterContainer.new()
		center.mouse_filter = Control.MOUSE_FILTER_IGNORE
		face.add_child(center)
		if not icon_kind.is_empty():
			var glyph := Visuals.icon(icon_kind, Vector2(19, 19))
			glyph.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
			glyph.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			center.add_child(glyph)
		else:
			var initial := UI.label(center, avatar, 14, UI.GREEN)
			initial.mouse_filter = Control.MOUSE_FILTER_IGNORE
			initial.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var words := VBoxContainer.new()
	words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	words.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	words.mouse_filter = Control.MOUSE_FILTER_IGNORE
	words.add_theme_constant_override("separation", 3)
	row.add_child(words)
	var main_label := UI.label(words, value, 14)
	main_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	main_label.max_lines_visible = 2
	main_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	var secondary := UI.label(words, subtitle, 12, UI.MUTED)
	secondary.mouse_filter = Control.MOUSE_FILTER_IGNORE
	secondary.max_lines_visible = 1
	secondary.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	var right: Control
	if pending:
		var dot := PanelContainer.new()
		dot.custom_minimum_size = Vector2(7, 7)
		dot.add_theme_stylebox_override("panel", UI.style(UI.BADGE, 0, 4))
		right = dot
	else:
		right = Visuals.icon("chevron_right", Vector2(17, 17))
	right.mouse_filter = Control.MOUSE_FILTER_IGNORE
	right.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	right.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(right)
	words.minimum_size_changed.connect(func(): button.custom_minimum_size.y = maxf(70, words.get_combined_minimum_size().y + 30))
	UI.divider(parent)
	return button

func _today() -> void:
	var c := CareerBridge.context
	home_clock = null
	UI.space(content, 17)
	var greeting := VBoxContainer.new()
	greeting.add_theme_constant_override("separation", 5)
	UI.inset(content, greeting)
	var player: Dictionary = c.get("player", {})
	var hour := floori(CareerBridge.clock_minutes / 60)
	var salutation := "早上好" if hour < 12 else ("下午好" if hour < 18 else "晚上好")
	var name := str(player.get("name", ""))
	var welcome := UI.label(greeting, salutation + ("，" + name if not name.is_empty() else ""), 25)
	welcome.max_lines_visible = 1
	welcome.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	var date := str(c.get("date", ""))
	var weekday := ""
	if not date.is_empty():
		var stamp := Time.get_datetime_dict_from_datetime_string(date + "T00:00:00", true)
		weekday = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"][int(stamp.get("weekday", 0))]
	UI.label(greeting, weekday + (" · 上午" if hour < 12 else (" · 下午" if hour < 18 else " · 晚上")), 12, UI.MUTED)
	UI.space(content, 6)
	content.add_child(Visuals.wallpaper(100))
	UI.space(content, 12)
	var grid := GridContainer.new()
	grid.columns = 3
	grid.add_theme_constant_override("h_separation", 10)
	grid.add_theme_constant_override("v_separation", 19)
	UI.inset(content, grid)
	nav_buttons.clear()
	for app in APPS:
		var column := VBoxContainer.new()
		column.custom_minimum_size.x = 88
		column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		column.add_theme_constant_override("separation", 8)
		grid.add_child(column)
		var tile := _button(column, "", _route.bind(str(app["id"])), false)
		tile.custom_minimum_size = Vector2(60, 60)
		tile.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		tile.tooltip_text = str(app["name"])
		tile.set_meta("app_id", app["id"])
		tile.set_meta("focus_key", "app:" + str(app["id"]))
		var tile_style := UI.style(UI.PAPER, 0, 19)
		tile_style.shadow_color = Color(0.21, 0.35, 0.26, 0.06)
		tile_style.shadow_size = 2
		tile_style.shadow_offset = Vector2(0, 2)
		tile.add_theme_stylebox_override("normal", tile_style)
		tile.add_theme_stylebox_override("hover", UI.style(Color("f2f5eb"), 0, 19))
		tile.add_theme_stylebox_override("pressed", UI.style(UI.MINT, 0, 19))
		tile.add_theme_stylebox_override("focus", UI.style(Color.TRANSPARENT, 0, 19, Color("90ab95")))
		var center := CenterContainer.new()
		center.mouse_filter = Control.MOUSE_FILTER_IGNORE
		center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		tile.add_child(center)
		var icon := Visuals.icon(str(app["id"]), Vector2(24, 24))
		icon.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
		icon.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		center.add_child(icon)
		var caption := UI.label(column, str(app["name"]), 12)
		caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		caption.mouse_filter = Control.MOUSE_FILTER_STOP
		caption.set_meta("app_caption", app["id"])
		caption.gui_input.connect(_app_caption_input.bind(str(app["id"])))
		nav_buttons[app["id"]] = tile
	# Widgets sit under the apps so Tab still starts at the first app.
	UI.space(content, 14)
	_home_widgets(c)
	var open_mail := 0
	for item in c.get("inbox", []):
		if item.get("status") == "open":
			open_mail += 1
	if open_mail > 0:
		var badge := PanelContainer.new()
		badge.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
		badge.offset_left = -17
		badge.offset_right = 3
		badge.offset_top = -3
		badge.offset_bottom = 17
		badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
		badge.add_theme_stylebox_override("panel", UI.style(UI.BADGE, 0, 10))
		nav_buttons["mail"].add_child(badge)
		var number := UI.label(badge, str(open_mail), 11, UI.PAPER)
		number.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		number.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		number.mouse_filter = Control.MOUSE_FILTER_IGNORE

func _home_widgets(c: Dictionary) -> void:
	# Glanceable cards: the next match and today's numbers, tappable into apps.
	var holder := VBoxContainer.new()
	holder.name = "PhoneHomeWidgets"
	holder.add_theme_constant_override("separation", 8)
	UI.inset(content, holder)
	var game: Variant = c.get("nextmatch")
	var next_button := _button(holder, "", _route.bind("match"), false)
	next_button.name = "PhoneNextMatchWidget"
	next_button.custom_minimum_size.y = 64
	var dark := game is Dictionary and not (game as Dictionary).is_empty()
	next_button.add_theme_stylebox_override("normal", UI.raised(Color("24402f") if dark else UI.PAPER, 0, 16, Color(0, 0, 0, 0)))
	next_button.add_theme_stylebox_override("hover", UI.style(Color("2c4c39") if dark else Color("eef3e8"), 0, 16))
	next_button.add_theme_stylebox_override("pressed", UI.style(Color("1d3326") if dark else UI.MINT, 0, 16))
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	row.offset_left = 14; row.offset_right = -12; row.offset_top = 8; row.offset_bottom = -8
	row.add_theme_constant_override("separation", 10)
	next_button.add_child(row)
	var words := VBoxContainer.new()
	words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	words.mouse_filter = Control.MOUSE_FILTER_IGNORE
	words.add_theme_constant_override("separation", 0)
	row.add_child(words)
	if dark:
		var info: Dictionary = game
		var top := UI.label(words, "下一场 · %s%s" % [info.get("date", ""), " · 今天" if info.get("due", false) else ""], 11, Color("b8d4c2"))
		top.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var versus := UI.label(words, "VS  " + str(info.get("opponent", "待定")), 17, UI.PAPER)
		versus.autowrap_mode = TextServer.AUTOWRAP_OFF
		versus.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		versus.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var mark := TeamVisuals.badge(row, str(info.get("opponent", "")), 34)
		if mark: row.move_child(mark, 0)
	else:
		UI.label(words, "下一场比赛", 11, UI.MUTED).mouse_filter = Control.MOUSE_FILTER_IGNORE
		var none := UI.label(words, "还没有排定的比赛", 15)
		none.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var arrow := Visuals.icon("chevron_right", Vector2(16, 16))
	arrow.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	if dark: arrow.ink = UI.PAPER
	row.add_child(arrow)
	var personal: Dictionary = c.get("personal", {}) if c.get("personal") is Dictionary else {}
	var waiting := 0
	for item in c.get("inbox", []):
		if item.get("status") == "open": waiting += 1
	var tiles := HBoxContainer.new()
	tiles.add_theme_constant_override("separation", 8)
	holder.add_child(tiles)
	for spec in [["个人余额", Fmt.money_short(personal.get("personal_money", c.get("money"))), "profile"], ["待回复", "%d 封" % waiting, "mail"], ["能力", Fmt.score(personal.get("ability", c.get("player", {}).get("ability"))), "profile"]]:
		var tile := _button(tiles, "", _route.bind(str(spec[2])), false)
		tile.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		tile.custom_minimum_size.y = 50
		tile.add_theme_stylebox_override("normal", UI.raised(UI.PAPER, 0, 13, Color(0, 0, 0, 0)))
		tile.add_theme_stylebox_override("hover", UI.style(Color("eef3e8"), 0, 13))
		var column := VBoxContainer.new()
		column.mouse_filter = Control.MOUSE_FILTER_IGNORE
		column.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		column.offset_left = 10; column.offset_top = 6; column.offset_right = -6
		column.add_theme_constant_override("separation", 0)
		tile.add_child(column)
		UI.label(column, str(spec[0]), 11, UI.MUTED).mouse_filter = Control.MOUSE_FILTER_IGNORE
		var value := UI.label(column, str(spec[1]), 15)
		value.autowrap_mode = TextServer.AUTOWRAP_OFF
		value.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		value.mouse_filter = Control.MOUSE_FILTER_IGNORE

func _app_caption_input(event: InputEvent, page: String) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_route(page)
		get_viewport().set_input_as_handled()

func _mail() -> void:
	var inbox: Array = CareerBridge.context.get("inbox", [])
	if not selected_mail.is_empty() and not selected_mail_detail.is_empty():
		var current_letter := selected_mail_detail.duplicate(true)
		for fresh in inbox:
			if str(fresh.get("id", "")) == selected_mail: current_letter.merge(fresh, true)
		inbox = [current_letter]
	UI.label(content, "收件箱" if selected_mail.is_empty() else "邮件", 12, UI.MUTED)
	UI.space(content, 4 if selected_mail.is_empty() else 14)
	if inbox.is_empty():
		UI.label(content, "收件箱很安静。新的赛事邀请会出现在这里。")
		return
	for mail in inbox:
		if not selected_mail.is_empty() and str(mail.get("id", "")) != selected_mail:
			continue
		var invite: bool = mail.get("kind") == "invite"
		var contract: bool = mail.get("kind") == "contract"
		var subject := Locale.field(mail, "title")
		if subject.is_empty():
			subject = (str(mail.get("team", "战队")) + " · 加盟邀请") if contract else str(mail.get("evname", "邮件"))
		var sender := "教练" if invite else str(mail.get("sender", mail.get("team", "俱乐部")))
		var meta := "%s · %s · %s" % [sender, mail.get("date", ""), _mail_status(str(mail.get("status", "")))]
		if selected_mail.is_empty():
			var row := _list_row(content, subject, meta, _open_mail.bind(str(mail.get("id", ""))), "教" if invite else "", "" if invite else "clipboard", mail.get("status") == "open")
			row.name = "MailRow_" + str(mail.get("id", "")).validate_node_name()
			row.set_meta("focus_key", "mail:" + str(mail.get("id", "")))
			row.add_to_group("phone_mail_row")
			continue
		title.text = sender
		var box := UI.card(content)
		UI.label(box, subject, 16)
		UI.label(box, "%s · %s" % [mail.get("date", ""), _mail_status(str(mail.get("status", "")))], 12, UI.MUTED)
		UI.space(box, 4)
		if invite:
			UI.label(box, "这场赛事的邀请到了。看一下赛程，咱们要不要报名？", 14)
		if not str(mail.get("body", "")).is_empty():
			UI.label(box, Locale.field(mail, "body"), 14)
		if not str(mail.get("evname", "")).is_empty():
			UI.label(box, str(mail["evname"]) + "\n" + str(mail.get("dates", "")), 14)
		UI.space(box, 4)
		UI.label(box, "—— " + sender, 12, UI.MUTED).horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		UI.space(content, 14)
		if invite and mail.get("status") == "open":
			_primary(_button(content, "参加这场赛事", _mail_action.bind("accept", mail)))
			UI.space(content, 8)
			_button(content, "这次先不报名", _mail_action.bind("decline", mail))
		elif contract and mail.get("status") == "open":
			UI.label(box, "接受后进入加盟决定，最终是否转会仍由你确认。", 12, UI.MUTED)
			_primary(_button(content, "继续加盟决定" if mail.get("decision_pending", false) else "查看加盟机会", _mail_action.bind("accept", mail)))
			UI.space(content, 8)
			_button(content, "婉拒这份邀请", _mail_action.bind("decline", mail))
		elif mail.get("status") == "open" and not str(mail.get("accept_action", "")).is_empty():
			_primary(_button(content, "接受邀请", _mail_action.bind("accept", mail)))
			_button(content, "婉拒邀请", _mail_action.bind("decline", mail))
		return

func _contract_command(action: String, id: String) -> void:
	for mail in CareerBridge.context.get("inbox", []):
		if str(mail.get("id", "")) == id:
			_mail_action(action, mail)
			return
	_mail_action(action, {"id":id})

func _mail_action(action: String, mail: Dictionary) -> void:
	if action == "accept" and bool(mail.get("decision_pending", false)):
		_navigate("stories")
		return
	var path := str(mail.get(action + "_action", "/api/3d/mail/" + action))
	if path not in ["/api/3d/mail/accept", "/api/3d/mail/decline"]: return
	_command(path, {"id":str(mail.get("id", "")), "revision":int(CareerBridge.context.get("calendar", {}).get("revision", 0))})

func _primary(button: Button) -> Button:
	for state in ["normal", "hover", "pressed"]:
		button.add_theme_stylebox_override(state, UI.style(UI.GREEN if state == "normal" else Color("315842"), 10, 12))
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color", "font_hover_pressed_color"]:
		button.add_theme_color_override(state, UI.PAPER)
	return button

func _mail_status(value: String) -> String:
	return {"open":"待回复", "accepted":"已接受", "declined":"已婉拒", "read":"已读", "filed":"已收阅", "expired":"已过期"}.get(value, value)

func _open_mail(id: String) -> void:
	selected_mail = id
	selected_mail_detail.clear()
	page_scroll["mail"] = 0
	_rebuild()
	_request_detail("mail", id)

func _contacts() -> Array[Dictionary]:
	return Social.contacts(CareerBridge.context)

func _chat() -> void:
	Social.render(self)

func _open_chat(id: String) -> void:
	selected_contact = id
	page_scroll["chat"] = 0
	_rebuild()

func _reply(contact: Dictionary, reply: Dictionary) -> void:
	_command("/api/3d/social/send", {"contact_id":str(contact.get("id", "")), "reply_id":str(reply.get("id", "")), "request_id":"phone:%d:%d" % [Time.get_unix_time_from_system() * 1000, Time.get_ticks_usec()], "revision":int(CareerBridge.context.get("calendar", {}).get("revision", 0))})

func _reveal_social_message(id: String) -> void:
	await get_tree().process_frame
	if screen.visible and active_page == "chat":
		Social.focus_message(self, id)

func _calendar() -> void:
	var current := str(CareerBridge.context.get("date", ""))
	if current.is_empty():
		return
	if selected_date.is_empty() or selected_date < current:
		selected_date = CareerBridge.add_days(current, 1)
		month = selected_date.left(7)
	if month.is_empty():
		month = selected_date.left(7)
	var top := HBoxContainer.new()
	UI.inset(content, top)
	UI.transparent(UI.compact(_button(top, "‹", _shift_month.bind(-1), false)))
	top.get_child(0).custom_minimum_size = Vector2(34, 34)
	var month_label := UI.label(top, month, 18)
	month_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	month_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	month_label.autowrap_mode = TextServer.AUTOWRAP_OFF
	var next_month := UI.compact(_button(top, "›", _shift_month.bind(1), false))
	UI.transparent(next_month)
	next_month.custom_minimum_size = Vector2(34, 34)
	var grid := GridContainer.new()
	grid.columns = 7
	grid.add_theme_constant_override("h_separation", 3)
	grid.add_theme_constant_override("v_separation", 3)
	UI.inset(content, grid)
	for weekday in ["日", "一", "二", "三", "四", "五", "六"]:
		UI.label(grid, weekday, 12).horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var first := Time.get_datetime_dict_from_datetime_string(month + "-01T00:00:00", true)
	for _i in range(int(first["weekday"])):
		UI.label(grid, " ")
	for day in range(1, _days_in_month(month) + 1):
		var stamp := "%s-%02d" % [month, day]
		var button := _button(grid, str(day), _select_day.bind(stamp), false)
		UI.transparent(button)
		button.custom_minimum_size = Vector2(34, 34)
		button.add_theme_font_size_override("font_size", 12)
		button.disabled = stamp < current or stamp.left(4) != current.left(4)
		if stamp == selected_date:
			button.add_theme_stylebox_override("normal", UI.style(UI.MINT, 4, 8))
	UI.label(content, "醒来：" + selected_date + " 08:00", 14)
	_primary(_button(content, "睡到这一天早上", CareerBridge.calendar.bind(selected_date, true)))
	_button(content, "睡到明早", CareerBridge.calendar.bind(CareerBridge.add_days(current, 1), true))
	if not CareerBridge.pending_target.is_empty() and CareerBridge.pending_target > current:
		_button(content, "继续到 " + CareerBridge.pending_target, CareerBridge.calendar.bind(CareerBridge.pending_target, true))
	UI.label(content, "比赛和待处理事件会让日历暂停。", 12, UI.MUTED)
	var next_game = CareerBridge.context.get("nextmatch")
	if next_game is Dictionary and not next_game.is_empty():
		var match_card := UI.card(content)
		UI.label(match_card, "今天的比赛" if next_game.get("due", false) else "下一场比赛", 15)
		UI.label(match_card, "%s · %s\n对阵 %s" % [next_game.get("date", ""), next_game.get("event", ""), next_game.get("opponent", "")], 13)
		_render_match_destination(match_card, next_game)
		_primary(_button(match_card, "亲自参赛" if next_game.get("due", false) else "亲自参赛 · 睡到比赛日", Computer.match_center.prepare_real.bind(str(next_game.get("id", "")))))
	for event in CareerBridge.context.get("calendar_events", []):
		if str(event.get("date", "")).begins_with(month):
			_list_row(content, str(event.get("name", "")), str(event.get("date", "")) + (" · 已报名" if event.get("registered", false) else ""), _load_event.bind(str(event.get("id", ""))), "", "calendar", false, true)

func _days_in_month(value: String) -> int:
	var year := int(value.left(4))
	var m := int(value.right(2))
	if m == 2:
		return 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
	return 30 if m in [4, 6, 9, 11] else 31

func _shift_month(amount: int) -> void:
	var year := int(month.left(4))
	var m := int(month.right(2)) + amount
	if m == 0:
		year -= 1
		m = 12
	if m == 13:
		year += 1
		m = 1
	if year != int(str(CareerBridge.context.get("date", "")).left(4)):
		return
	month = "%04d-%02d" % [year, m]
	_rebuild()

func _select_day(day: String) -> void:
	selected_date = day
	_rebuild()

func _profile() -> void:
	var links := HBoxContainer.new()
	UI.inset(content, links)
	_button(links, "小鸡形象", _computer_page.bind("appearance"), false)
	_button(links, "阵容与合同", _computer_page.bind("management"), false)
	var player: Dictionary = CareerBridge.context.get("player", {})
	var personal: Dictionary = CareerBridge.context.get("personal", {})
	# The profile shows your own chicken in its saved colours, not a generic icon.
	var avatar_row := CenterContainer.new()
	UI.inset(content, avatar_row)
	var saved: Variant = CareerBridge.context.get("avatar", {})
	var look: Variant = saved.get("appearance", {}) if saved is Dictionary else {}
	Kit.chicken_badge(avatar_row, look if look is Dictionary else {}, 76)
	UI.label(content, str(player.get("name", "选手")), 20).horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	UI.label(content, "%s · 能力 %s" % [ROLES.get(player.get("role", ""), player.get("role", "")), Fmt.score(player.get("ability"))], 12, UI.MUTED).horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	UI.space(content, 12)
	var tabs := HBoxContainer.new()
	tabs.add_theme_constant_override("separation", 6)
	UI.inset(content, tabs)
	for item in [["overview", "概览"], ["stats", "比赛数据"], ["growth", "属性培养"]]:
		var tab := _button(tabs, item[1], _profile_tab.bind(item[0]), false)
		tab.custom_minimum_size = Vector2(60, 35)
		tab.add_theme_font_size_override("font_size", 12)
		if profile_tab == item[0]:
			tab.add_theme_stylebox_override("normal", UI.style(UI.MINT, 7, 10))
	UI.space(content, 12)
	if profile_tab == "growth":
		_profile_growth(personal)
		return
	if profile_tab == "overview":
		var raw_playing = personal.get("playing_attributes", personal.get("attributes", {}))
		var playing: Dictionary = raw_playing if raw_playing is Dictionary else {}
		_position_preview(personal, str(player.get("role", "")), playing, "profile")
	var stats: Dictionary = personal.get("stats", {})
	var sample := UI.card(content)
	UI.label(sample, "本赛季 · %s 张地图" % stats.get("maps", 0), 12, UI.MUTED)
	UI.label(sample, "Rating %s   ·   ADR %s" % [_stat(stats.get("rating"), 2), _stat(stats.get("adr"), 1)], 16)
	UI.label(sample, "K / D / A   %s / %s / %s" % [_stat(stats.get("k"), 0), _stat(stats.get("d"), 0), _stat(stats.get("a"), 0)], 13)
	UI.label(sample, "KAST %s   ·   状态 %+d" % [_percentage(stats.get("kast")), int(personal.get("form_delta", player.get("form_delta", 0)))], 12, UI.MUTED)
	UI.space(content, 12)
	if profile_tab == "stats":
		var recent: Array = personal.get("recent", [])
		if recent.is_empty():
			UI.label(content, "还没有比赛数据", 13, UI.MUTED)
		for game in recent:
			_list_row(content, "%s · %s" % [game.get("map", ""), game.get("opponent", "")], "%s · Rating %s" % [game.get("date", ""), _stat(game.get("rating"), 2)], _load_detail.bind(str(game.get("match_id", ""))), "", "match", false, true)
		var ladder: Dictionary = CareerBridge.context.get("ladder", {}).get("player", {})
		UI.label(content, "天梯 Elo %s · %s 胜 / %s 负" % [Fmt.integer(ladder.get("elo")), Fmt.integer(ladder.get("wins"), "0"), Fmt.integer(ladder.get("losses"), "0")], 13)
		return
	_list_row(content, str(CareerBridge.context.get("team", {}).get("name", "我的战队")), "战队阵容", _own_team, "", "profile", false, false, str(CareerBridge.context.get("team", {}).get("name", "")))
	_list_row(content, "最近比赛与战报", "查看职业赛事记录", _route.bind("match"), "", "match")
	UI.label(content, "个人余额 " + Fmt.money(personal.get("personal_money", CareerBridge.context.get("money", 0))), 14)
	UI.label(content, "俱乐部资金 " + Fmt.money(personal.get("club_money", CareerBridge.context.get("team", {}).get("money", 0))), 12, UI.MUTED)

func _stat(value: Variant, digits: int) -> String:
	if value == null:
		return "—"
	if digits == 2:
		return "%.2f" % float(value)
	if digits == 1:
		return "%.1f" % float(value)
	return str(roundi(float(value)))

func _percentage(value: Variant) -> String:
	return "—" if value == null else "%d%%" % roundi(float(value) * 100)

func _profile_tab(tab: String) -> void:
	profile_tab = tab
	page_scroll["profile"] = 0
	_rebuild()

func _position_preview_changed(index: int, page: String, selector: OptionButton) -> void:
	position_preview_roles[page] = str(selector.get_item_metadata(index))
	page_scroll[active_page] = scroll.scroll_vertical
	_rebuild()

func _position_preview(data: Dictionary, current_role: String, current_stats: Dictionary, page: String) -> void:
	var raw_views = data.get("position_views", [])
	var views: Array = raw_views if raw_views is Array else []
	if views.is_empty():
		return
	var selected := str(position_preview_roles.get(page, ""))
	var shown: Dictionary = {"ability":data.get("ability"), "stats":current_stats}
	var box := UI.card(content)
	box.name = "PhonePositionPreview_" + page
	UI.label(box, "位置能力", 15)
	var selector := OptionButton.new()
	UI.decorate_button(selector)
	var popup := selector.get_popup()
	popup.add_theme_stylebox_override("panel", UI.style(UI.PAPER, 8, 9, UI.LINE))
	popup.add_theme_font_override("font", UI.font())
	popup.add_theme_font_size_override("font_size", 14)
	popup.add_theme_color_override("font_color", UI.INK)
	popup.add_theme_color_override("font_hover_color", UI.INK)
	popup.add_theme_stylebox_override("hover", UI.style(UI.MINT, 6, 5))
	selector.name = "PositionPreviewSelector"
	selector.custom_minimum_size.y = 36
	selector.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	selector.add_item("当前位置 · " + str(ROLES.get(current_role, current_role)))
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
	UI.label(box, "位置适配能力 " + _stat_value(shown.get("ability"), 2), 16)
	var stats: Dictionary = shown.get("stats", {}) if shown.get("stats") is Dictionary else {}
	for axis in {"firepower":"火力", "entrying":"突破", "trading":"补枪", "opening":"首杀", "clutching":"残局", "sniping":"狙击", "utility":"道具"}:
		var row := HBoxContainer.new()
		box.add_child(row)
		UI.label(row, str({"firepower":"火力", "entrying":"突破", "trading":"补枪", "opening":"首杀", "clutching":"残局", "sniping":"狙击", "utility":"道具"}[axis]), 13, UI.MUTED).size_flags_horizontal = Control.SIZE_EXPAND_FILL
		UI.label(row, _stat_value(stats.get(axis), 1), 13)
	UI.label(box, "切换预览不会改变阵容。", 12, UI.MUTED)

func _profile_growth(personal: Dictionary) -> void:
	UI.label(content, "自由属性点 %d" % CareerBridge.growth_remaining(), 17, UI.GREEN)
	var reason := str(personal.get("growth_reason", "个人属性正在载入。"))
	if not reason.is_empty():
		UI.label(content, reason, 12, UI.MUTED)
	UI.space(content, 8)
	var attributes: Dictionary = personal.get("attributes", {})
	var labels: Dictionary = personal.get("axis_labels", {})
	for axis in personal.get("axes", []):
		if not attributes.has(axis):
			continue
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 5)
		UI.inset(content, row)
		var caption := UI.label(row, str(labels.get(axis, axis)), 13)
		caption.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var measured: bool = typeof(attributes[axis]) in [TYPE_INT, TYPE_FLOAT]
		var attribute: float = float(attributes[axis]) if measured else 0.0
		var value := UI.label(row, str(roundi(attribute + int(CareerBridge.growth_draft.get(axis, 0)))) if measured else "—", 14)
		value.custom_minimum_size.x = 32
		value.size_flags_horizontal = Control.SIZE_SHRINK_END
		value.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		for delta in [-1, 1]:
			var adjust := _button(row, "−" if delta == -1 else "+", CareerBridge.growth_adjust.bind(str(axis), delta))
			adjust.name = ("GrowthMinus_" if delta == -1 else "GrowthPlus_") + str(axis)
			adjust.custom_minimum_size = Vector2(34, 34)
			adjust.size_flags_horizontal = Control.SIZE_SHRINK_END
			var blocked: bool = not personal.get("growth_allowed", false) or not measured
			if delta == -1:
				blocked = blocked or int(CareerBridge.growth_draft.get(axis, 0)) == 0
			else:
				blocked = blocked or CareerBridge.growth_remaining() == 0 or attribute + int(CareerBridge.growth_draft.get(axis, 0)) >= 100
			adjust.set_meta("career_gate_disabled", blocked)
			adjust.disabled = adjust.disabled or blocked
		UI.space(content, 5)
	UI.space(content, 10)
	var commit := _primary(_button(content, "确认加点", _commit_growth))
	commit.name = "GrowthCommit"
	commit.set_meta("career_gate_disabled", CareerBridge.growth_draft.is_empty() or not personal.get("growth_allowed", false))
	commit.disabled = commit.disabled or bool(commit.get_meta("career_gate_disabled"))
	UI.space(content, 6)
	_button(content, "撤销本次分配", CareerBridge.growth_clear, false).disabled = CareerBridge.growth_draft.is_empty() or CareerBridge.busy
	UI.space(content, 8)
	UI.label(content, "手机与电脑共用同一份属性点。确认前可以调整。", 12, UI.MUTED)

func _growth_changed() -> void:
	if screen.visible and active_page == "profile":
		page_scroll["profile"] = scroll.scroll_vertical
		_rebuild()

func _own_team() -> void:
	selected_team = {}
	_route("team")

func _team() -> void:
	var team: Dictionary = selected_team if not selected_team.is_empty() else CareerBridge.context.get("team", {})
	TeamVisuals.banner(content, str(team.get("name", "战队")), str(team.get("name", "")), "赛区 %s · 排名 %s" % [team.get("region", ""), team.get("rank", "—")])
	var player_id := str(CareerBridge.context.get("player", {}).get("id", ""))
	for member in team.get("roster", team.get("players", [])):
		_list_row(content, str(member.get("name", "")) + (" · 你" if str(member.get("player_id", member.get("id", ""))) == player_id else ""), "%s · 能力 %s" % [ROLES.get(member.get("role", ""), member.get("role", "")), Fmt.score(member.get("ability"))], _load_player.bind(str(member.get("player_id", member.get("id", "")))), str(member.get("name", "")).left(1), "", false, true, str(team.get("name", "")))

func _open_player(player: Dictionary) -> void:
	selected_player = player.duplicate(true)
	_route("player")

func _load_player(id: String) -> void:
	player_range = "season"
	player_page = 1
	_request_detail("player", id)

func _load_team(id: String) -> void:
	_request_detail("team", id)

func _load_event(id: String) -> void:
	_request_detail("event", id)

func _request_detail(kind: String, id: String) -> void:
	# A hidden compatibility call explicitly requests an open. A subsequent
	# close/switch invalidates that intent while the response may still be cached.
	pending_detail_open = not screen.visible
	pending_detail_intent = detail_intent_serial
	pending_detail_path = "/api/3d/" + kind + "?id=" + id.uri_encode()
	if not CareerBridge._send(pending_detail_path, {}, false):
		pending_detail_path = ""
		pending_detail_open = false
		pending_detail_intent = -1

func _player() -> void:
	var team_name := str(selected_player.get("team", selected_player.get("last_team", "")))
	TeamVisuals.banner(content, str(selected_player.get("name", "选手")), team_name, str(ROLES.get(selected_player.get("role", ""), selected_player.get("role", ""))))
	if not team_name.is_empty() and team_name != "<null>":
		if not str(selected_player.get("team_id", "")).is_empty():
			TeamVisuals.button_logo(_button(content, team_name, _load_team.bind(str(selected_player["team_id"])), false), team_name)
		else:
			UI.label(content, team_name, 14, UI.MUTED)
	for field in [{"id":"ability", "label":"能力"}, {"id":"age", "label":"年龄"}, {"id":"nationality", "label":"国籍"}, {"id":"potential", "label":"潜力"}, {"id":"elo", "label":"天梯积分"}]:
		if selected_player.get(field["id"]) != null:
			UI.label(content, str(field["label"]) + "：" + str(selected_player[field["id"]]))
	if selected_player.get("form_delta") != null:
		UI.label(content, "近期状态 %+.1f" % float(selected_player["form_delta"]), 14, UI.MUTED)
	var raw_attributes = selected_player.get("stats", {})
	var attributes: Dictionary = raw_attributes if raw_attributes is Dictionary else {}
	_position_preview(selected_player, str(selected_player.get("role", "")), attributes, "player")
	var range_row := HBoxContainer.new()
	UI.inset(content, range_row)
	for item in [["30d", "30 天"], ["season", "本赛季"], ["all", "全部"]]:
		var range_button := _button(range_row, item[1], _player_scope.bind(item[0], 1), false)
		range_button.set_meta("player_range", item[0])
		if str(selected_player.get("range", player_range)) == item[0]:
			_primary(range_button)
	var summary: Dictionary = selected_player.get("summary", {})
	var stats := UI.card(content)
	UI.label(stats, "比赛数据 · %d 张地图" % int(summary.get("maps", 0)), 15)
	UI.label(stats, "Rating %s · ADR %s\nKAST %s · %d 个回合" % [_stat_value(summary.get("rating"), 2), _stat_value(summary.get("adr"), 1), _stat_value(summary.get("kast"), 0, true), int(summary.get("rounds", 0))], 14)
	if int(summary.get("maps", 0)) > 0:
		UI.label(stats, "击杀 %s / 死亡 %s / 助攻 %s" % [summary.get("k", "—"), summary.get("d", "—"), summary.get("a", "—")], 14)
		if not summary.get("data_complete", false):
			UI.label(stats, "部分历史数据不完整，缺失统计不补零。", 12, UI.MUTED)
	else:
		UI.label(stats, "这个范围还没有已保存的职业比赛数据。", 12, UI.MUTED)
	UI.label(content, "比赛记录", 16)
	var rows: Array = selected_player.get("records", selected_player.get("recent", []))
	for game in rows:
		_list_row(content, "%s · %s" % [game.get("map", "比赛"), _stat_value(game.get("rating"), 2)], "%s · 对阵 %s\n%s" % [game.get("date", ""), game.get("opponent", ""), game.get("event", "")], _load_detail.bind(str(game.get("match_id", ""))), "", "match", false, true)
	var total := int(selected_player.get("total", rows.size()))
	var current := int(selected_player.get("page", 1))
	var page_size := maxi(1, int(selected_player.get("page_size", 20)))
	if total > page_size:
		var paging := HBoxContainer.new()
		UI.inset(content, paging)
		var previous := _button(paging, "上一页", _player_scope.bind(player_range, current - 1), false)
		previous.disabled = current <= 1
		var next := _button(paging, "下一页", _player_scope.bind(player_range, current + 1), false)
		next.disabled = current * page_size >= total
		UI.label(content, "第 %d 页 · 共 %d 张地图" % [current, total], 12, UI.MUTED)
	var honours: Dictionary = selected_player.get("honours", {})
	UI.label(content, "荣誉", 16)
	var counts: Dictionary = honours.get("counts", {})
	for item in [["titles", "冠军"], ["mvp", "MVP"], ["evp", "EVP"], ["top20", "Top20"]]:
		var saved: Array = honours.get(item[0], [])
		UI.label(content, "%s · %d" % [item[1], int(counts.get(item[0], saved.size()))], 14)
		for honour in saved:
			if honour is Dictionary:
				UI.label(content, str(honour.get("event", honour.get("name", honour.get("year", "")))) + (" · #" + str(honour["rank"]) if honour.has("rank") else ""), 12, UI.MUTED)
	if not str(selected_player.get("honours_notice", "")).is_empty():
		UI.label(content, str(selected_player["honours_notice"]), 12, UI.MUTED)

func _stat_value(value: Variant, digits: int = 1, percent: bool = false) -> String:
	if value == null or not (value is float or value is int):
		return "—"
	return (("%." + str(digits) + "f") % (float(value) * (100.0 if percent else 1.0))) + ("%" if percent else "")

func _player_scope(span: String, page: int) -> void:
	var id := str(selected_player.get("player_id", selected_player.get("id", "")))
	if id.is_empty() or CareerBridge.busy:
		return
	player_range = span
	player_page = maxi(1, page)
	pending_detail_open = not screen.visible
	pending_detail_intent = detail_intent_serial
	pending_detail_path = "/api/3d/player?id=" + id.uri_encode() + "&span=" + span.uri_encode() + "&page=" + str(player_page)
	if not CareerBridge._send(pending_detail_path, {}, false):
		pending_detail_path = ""
		pending_detail_intent = -1

func _event() -> void:
	UI.label(content, str(selected_event.get("name", "赛事资料")), 20)
	UI.label(content, EventFlow.dates_text(selected_event.get("dates", [])), 12, UI.MUTED)
	for field in ["date", "start", "end", "tier", "format", "prize", "region"]:
		if selected_event.has(field):
			UI.label(content, "%s：%s" % [{"date":"日期", "start":"开始", "end":"结束", "tier":"级别", "format":"赛制", "prize":"奖金", "region":"赛区"}.get(field, field), EventFlow.field_text(field, selected_event[field])])
	for team in selected_event.get("teams", []):
		if team is Dictionary:
			_list_row(content, str(team.get("name", "战队")), "战队资料", _load_team.bind(str(team.get("id", ""))), "", "profile", false, true, str(team.get("name", "")))
	EventFlow.mount(content, selected_event, _load_detail, true)

func _stories() -> void:
	var queue: Array = CareerBridge.context.get("stories", [])
	if queue.is_empty():
		UI.label(content, "事情都处理好了。继续你的一天吧。")
		return
	var story: Dictionary = queue[0]
	UI.label(content, Locale.field(story, "title", "队内事件"), 20)
	UI.label(content, Locale.field(story, "text"), 14)
	for choice in story.get("choices", []):
		_button(content, Locale.field(choice, "label", "选择"), _command.bind("/api/3d/story", {"id":story["id"], "choice":choice["id"]}))

	if story.get("choices", []).is_empty():
		_button(content, "我知道了", _command.bind("/api/3d/story", {"id":story["id"], "choice":""}))
	UI.label(content, "还有 %d 件待处理" % queue.size(), 12, UI.MUTED)

func _language_changed() -> void:
	rendered_context = ""
	call_deferred("_rebuild")

func _matches() -> void:
	if not detail.is_empty():
		_render_detail()
		return
	var shortcuts := HBoxContainer.new()
	shortcuts.add_theme_constant_override("separation", 8)
	UI.inset(content, shortcuts)
	_button(shortcuts, "赛事新闻 ›", _route.bind("news"), false)
	_button(shortcuts, "快速赛季 ›", _route.bind("quick"), false)
	var game = CareerBridge.context.get("nextmatch")
	if game is Dictionary and not game.is_empty():
		var plan: Dictionary = game.get("attendance", {})
		var details: Array[String] = [Kit.short_date(str(game.get("date", "")))]
		details.append("BO%d" % int(game.get("best_of", 3)))
		if not str(plan.get("display_name", "")).is_empty(): details.append(str(plan.display_name))
		Kit.match_hero(content, UI, str(CareerBridge.context.get("team", {}).get("name", "")), str(game.get("opponent", "")), str(game.get("event", "下一场")), " · ".join(details))
		var box := VBoxContainer.new()
		box.add_theme_constant_override("separation", 8)
		UI.inset(content, box)
		if game.get("due", false):
			_primary(_button(box, "去比赛电脑 · 模拟或上场", _open_computer.bind("career_match"), false))
			_button(box, "自己去 CS2 打", Computer.match_center.prepare_real.bind(str(game.get("id", ""))))
		else:
			_primary(_button(box, "亲自参赛 · 睡到比赛日", Computer.match_center.prepare_real.bind(str(game.get("id", "")))))
			_button(box, "只推进到比赛日", CareerBridge.calendar.bind(str(game["date"]), true))
	else:
		Kit.empty_state(content, UI, "match", "还没有排定的比赛", "确认赛事邀请后，赛程会出现在这里。")
		_button(content, "查看赛事邀请", _route.bind("mail"), false)
	Kit.section(content, UI, "最近比赛", "", 16)
	for game_row in CareerBridge.context.get("recent_matches", []):
		var series = game_row.get("series", [])
		var score := str(series)
		if series is Array and series.size() == 2:
			score = "%s : %s" % [series[0], series[1]]
		_list_row(content, "%s  %s  %s" % [game_row.get("team_a", ""), score, game_row.get("team_b", "")], "%s · %s" % [game_row.get("date", ""), game_row.get("event", "")], _load_detail.bind(str(game_row["id"])), "", "match", false, true)
	if CareerBridge.context.get("recent_matches", []).is_empty():
		UI.label(content, "暂无", 12, UI.MUTED)
	var today := str(CareerBridge.context.get("date", ""))
	var upcoming: Array = []
	var finished: Array = []
	for event in CareerBridge.context.get("calendar_events", []):
		if str(event.get("end_date", event.get("date", ""))) < today: finished.append(event)
		else: upcoming.append(event)
	finished.reverse()
	Kit.section(content, UI, "赛事日程", "%d 项进行中或即将开始" % upcoming.size(), 16)
	for event in upcoming + finished:
		var tier := Kit.event_tier(str(event.get("type", "")))
		var state := "已结束" if event in finished else ("已报名" if event.get("registered", false) else "")
		var subtitle := "%s · %s%s" % [Kit.short_date(str(event.get("date", ""))), tier[0], (" · " + state) if not state.is_empty() else ""]
		_list_row(content, str(event.get("name", "")), subtitle, _load_event.bind(str(event.get("id", ""))), "", "calendar", false, true)

func _render_match_destination(parent: Node, game: Dictionary) -> void:
	var plan: Dictionary = game.get("attendance", {})
	if str(plan.get("display_name", "")).is_empty(): return
	UI.label(parent, "比赛地点 · " + str(plan.display_name), 14)

func _news() -> void:
	News.render(self)

func _load_news(category: String = "all", page: int = 1, id: String = "") -> void:
	if CareerBridge.busy:
		return
	news_category = category
	news_page = maxi(1, page)
	pending_detail_open = not screen.visible
	pending_detail_intent = detail_intent_serial
	pending_detail_path = "/api/3d/news?id=" + id.uri_encode() if not id.is_empty() else "/api/3d/news?category=" + category.uri_encode() + "&page=" + str(news_page)
	if not CareerBridge._send(pending_detail_path, {}, false):
		pending_detail_path = ""
		pending_detail_intent = -1

func _news_list() -> void:
	news_article.clear()
	_rebuild()

func _load_detail(id: String) -> void:
	_request_detail("match", id)

func _render_detail() -> void:
	var back_to_list := _button(content, "‹ 比赛列表", _clear_detail, false)
	UI.transparent(back_to_list)
	var game: Dictionary = detail.get("match", {})
	var own_id := str(CareerBridge.context.get("player", {}).get("id", ""))
	MatchReport.mount(content, game, detail.get("event", {}), own_id, _load_player, true)

func _clear_detail() -> void:
	detail = {}
	page_scroll["match"] = 0
	_rebuild()

func _open_computer(page: String) -> void:
	Computer.open_app(page, Computer.location)

func _quick() -> void:
	var state: Dictionary = CareerBridge.context.get("quick", {})
	UI.label(content, "快速赛季", 20)
	UI.label(content, "%s 赛季 · %s" % [state.get("year", str(CareerBridge.context.get("date", "")).left(4)), "快速模式" if state.get("mode", "normal") == "quick" else "正常模式"], 14)
	if bool(state.get("can_choose", state.get("choice_required", false))):
		var season_label := "下赛季" if state.get("season_phase", "") == "end" else "本赛季"
		_primary(_button(content, season_label + "使用快速模式", Computer.match_center.choose_mode.bind(true)))
		_button(content, season_label + "正常进行", Computer.match_center.choose_mode.bind(false))
	if not str(state.get("block_reason", "")).is_empty(): UI.label(content, str(state.block_reason), 13, UI.MUTED)

	_primary(_button(content, "打开快速赛季与逐场战报", _open_computer.bind("quick"), false))
	if not CareerBridge.context.get("stories", []).is_empty(): _button(content, "处理队内事件", _route.bind("stories"), false)

func _fetch_device_settings() -> void:
	Computer.device_settings.fetch()

func _settings() -> void:
	var links := HBoxContainer.new()
	UI.inset(content, links)
	_button(links, "开局选择", _computer_page.bind("start"), false)
	_button(links, "自动安排", _computer_page.bind("assistance"), false)
	_button(content, "扩展工坊", _computer_page.bind("workshop"), false)
	var font_choice := OptionButton.new()
	UI.decorate_button(font_choice)
	font_choice.name = "PhoneFontChoice"
	font_choice.add_item("圆润字体")
	font_choice.add_item("系统黑体")
	font_choice.select(0 if UI.font_style == "rounded" else 1)
	UI.inset(content, font_choice)
	font_choice.item_selected.connect(func(index: int): UI.choose_font("rounded" if index == 0 else "system", get_tree()))
	Computer.device_settings.render(self, content, true)
	UI.space(content, 16)
	UI.label(content, "声音", 16)
	var volume := HSlider.new()
	volume.min_value = 0
	volume.max_value = 1
	volume.step = 0.05
	volume.value = CareerBridge.sound_volume
	volume.custom_minimum_size.y = 35
	volume.add_theme_stylebox_override("slider", UI.style(UI.LINE, 0, 3))
	volume.add_theme_stylebox_override("grabber_area", UI.style(UI.MINT, 0, 3))
	volume.add_theme_stylebox_override("grabber_area_highlight", UI.style(UI.MINT, 0, 3))
	volume.add_theme_icon_override("grabber", UI.control_icon("slider"))
	volume.add_theme_icon_override("grabber_highlight", UI.control_icon("slider"))
	volume.value_changed.connect(func(value: float): CareerBridge.sound_volume = value; _audio())
	UI.inset(content, volume)
	var mute := CheckBox.new()
	mute.text = "静音"
	mute.button_pressed = CareerBridge.sound_muted
	UI.transparent(mute)
	mute.add_theme_color_override("font_color", UI.INK)
	mute.add_theme_color_override("font_focus_color", UI.INK)
	mute.add_theme_color_override("font_hover_color", UI.INK)
	mute.add_theme_color_override("font_pressed_color", UI.INK)
	mute.add_theme_font_size_override("font_size", 14)
	for icon_kind in ["checked", "unchecked", "checked_disabled", "unchecked_disabled"]:
		mute.add_theme_icon_override(icon_kind, UI.control_icon("checked" if icon_kind.begins_with("checked") else "unchecked"))
	mute.toggled.connect(func(value: bool): CareerBridge.sound_muted = value; _audio())
	UI.inset(content, mute)
	UI.label(content, "Tab 切换，Enter 确认。\nP / Esc 收起，Home 回到主屏。", 12, UI.MUTED)
	_button(content, "保存并退出", CareerBridge.quit, false)

func _audio() -> void:
	var scene := get_tree().current_scene
	if scene and scene.get("atmosphere") != null:
		scene.atmosphere.set_master_volume(CareerBridge.sound_volume)
		scene.atmosphere.set_muted(CareerBridge.sound_muted)

func _travel(destination: String) -> void:
	close_phone()
	Travel.go(destination)

func _wake() -> void:
	close_phone()
	Travel.go("bedroom")

func _busy_changed(value: bool) -> void:
	for button in action_buttons:
		if is_instance_valid(button):
			button.disabled = (value and CareerBridge.active_post) or not CareerBridge.connected or bool(button.get_meta("career_gate_disabled", false))
	_update_status()

func _refresh_settings_after_command() -> void:
	if screen.visible and active_page == "settings":
		_rebuild()

func _finished(path: String, result: Dictionary) -> void:
	if is_instance_valid(action_feedback): action_feedback.call_deferred("finish_request", path, result)
	if path in ["/api/3d/story", "/api/3d/social/send"] and result.get("ok", false) and not str(result.get("social_contact_id", "")).is_empty() and screen.visible:
		selected_contact = str(result.social_contact_id)
		page_scroll["chat"] = 0
		_navigate("chat")
		call_deferred("_reveal_social_message", str(result.get("social_focus_message_id", "")))
		if not str(result.get("social_page", "")).is_empty():
			_route(str(result.social_page))
		return
	if path in ["/api/3d/settings", "/api/3d/settings/detect", "/api/3d/settings/updates", "/api/3d/settings/environment", "/api/3d/setup/install"]:
		# Computer owns the shared settings controller and handles this signal
		# even while hidden. Phone is earlier in autoload order, so wait until
		# the shared controller has consumed the result before drawing it.
		if screen.visible and active_page == "settings":
			call_deferred("_refresh_settings_after_command")
		return
	if path.begins_with("/api/3d/season/"):
		if screen.visible and active_page == "quick":
			_rebuild()
		return
	if path == pending_detail_path and not pending_detail_path.is_empty():
		var current_intent := pending_detail_intent == detail_intent_serial
		var should_open := current_intent and pending_detail_open
		pending_detail_path = ""
		pending_detail_open = false
		pending_detail_intent = -1
		if result.get("ok", false):
			var page := path.get_slice("/", 3).get_slice("?", 0)
			match page:
				"match": detail = result
				"player": selected_player = result.get("detail", {})
				"team": selected_team = result.get("detail", {})
				"event": selected_event = result.get("detail", {})
				"mail": selected_mail_detail = result.get("detail", {})
				"news":
					if result.has("detail"):
						news_article = result["detail"]
					else:
						news_data = result.duplicate(true)
						news_article.clear()
			if screen.visible and current_intent:
				_navigate(page)
			elif should_open and not CareerBridge.phone_open:
				present(page)
	if path == "/api/3d/match/simulate" and result.get("ok", false) and screen.visible and active_page == "match":
		detail = {}
		_navigate("stories" if not CareerBridge.context.get("stories", []).is_empty() else "match")
	elif path == "/api/3d/mail/accept" and result.get("ok", false) and screen.visible and not CareerBridge.context.get("stories", []).is_empty():
		_navigate("stories")
	elif path == "/api/3d/calendar" and result.get("status") == "paused" and screen.visible:
		_navigate("stories" if not CareerBridge.context.get("stories", []).is_empty() else "match")
	elif screen.visible:
		_busy_changed(CareerBridge.busy)
	if not result.get("ok", false) and screen.visible:
		_toast_text = str(result.get("msg", result.get("reason", "这次操作没有完成。")))
		_update_status()

func _update_status() -> void:
	if status:
		status.text = _toast_text if not _toast_text.is_empty() else ("同步中……" if CareerBridge.busy else (CareerBridge.message if not CareerBridge.connected else ""))
		status.visible = not status.text.is_empty()

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

func _restore_focus(value: String) -> void:
	_restore_in(content, value)

func _restore_in(node: Node, value: String) -> bool:
	for child in node.get_children():
		if child is Button and str(child.get_meta("focus_key", child.text)) == value and not child.disabled:
			child.grab_focus()
			return true
		if _restore_in(child, value):
			return true
	return false

func _process(_delta: float) -> void:
	if screen.visible:
		clock.text = "%02d:%02d" % [floori(CareerBridge.clock_minutes / 60), int(CareerBridge.clock_minutes) % 60]
		if active_page == "home" and is_instance_valid(home_clock):
			home_clock.text = "%02d:%02d" % [floori(CareerBridge.clock_minutes / 60), int(CareerBridge.clock_minutes) % 60]

func _input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo or UI.key_claimed(self):
		return
	var typing := get_viewport().gui_get_focus_owner()
	if typing is LineEdit or typing is TextEdit: return
	var computer := get_node_or_null("/root/Computer")
	if computer and computer.screen.visible:
		# The embedded match owns Esc; opening the phone must not unlock the
		# club or dismiss the workstation underneath an active RTS session.
		if is_instance_valid(computer.rts_room.session):
			if event.physical_keycode == KEY_P:
				UI.claim_key(self)
			return
		if event.physical_keycode in [KEY_P, KEY_ESCAPE]:
			computer.close_computer()
			UI.claim_key(self)
		return
	# Opening a phone should not look like a preselected app. Tab explicitly
	# starts keyboard navigation; subsequent focus traversal stays native.
	if screen.visible and event.physical_keycode == KEY_TAB and get_viewport().gui_get_focus_owner() == null:
		_focus_first()
		UI.claim_key(self)
		return
	if event.physical_keycode == KEY_P:
		if screen.visible:
			close_phone()
		else:
			present()
		UI.claim_key(self)
	elif screen.visible and event.physical_keycode == KEY_ESCAPE:
		close_phone()
		UI.claim_key(self)
	elif screen.visible and event.physical_keycode == KEY_HOME:
		_home()
		UI.claim_key(self)
	elif screen.visible and event.physical_keycode == KEY_BACKSPACE:
		_back()
		UI.claim_key(self)

func _computer_page(page: String) -> void:
	close_phone(false)
	Computer.open_app(page, "club" if get_tree().current_scene.scene_file_path == "res://play.tscn" else "bedroom")
