extends CanvasLayer
## World-owned reception and honours panels, not another phone application.
const UI = preload("res://scripts/phone_ui.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")
const Trophy = preload("res://scripts/career_trophy.gd")
var screen: Control
var panel: PanelContainer
var content: VBoxContainer
var heading: Label
var page := ""
var projection_signature := ""

func _ready() -> void:
	layer = 24
	screen = Control.new()
	screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(screen)
	var dim := ColorRect.new()
	dim.color = Color(.04, .08, .06, .52)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	screen.add_child(dim)
	panel = PanelContainer.new()
	panel.name = "ClubNoticePanel"
	panel.set_anchors_and_offsets_preset(Control.PRESET_CENTER)
	panel.add_theme_stylebox_override("panel", UI.style(UI.CREAM, 24, 20, UI.LINE))
	screen.add_child(panel)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 16)
	panel.add_child(layout)
	var header := HBoxContainer.new()
	layout.add_child(header)
	heading = UI.label(header, "", 25)
	var close := UI.button(header, "关闭 · E / Esc", close_board)
	UI.compact(close)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	layout.add_child(scroll)
	content = VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 12)
	scroll.add_child(content)
	get_viewport().size_changed.connect(_resize)
	_resize()
	screen.hide()

func _resize() -> void:
	var available := get_viewport().get_visible_rect().size
	var dimensions := Vector2(minf(820, available.x - 48), minf(640, available.y - 48))
	panel.offset_left = -dimensions.x / 2
	panel.offset_right = dimensions.x / 2
	panel.offset_top = -dimensions.y / 2
	panel.offset_bottom = dimensions.y / 2

func is_open() -> bool:
	return is_instance_valid(screen) and screen.visible

func present(destination: String) -> void:
	if destination not in ["reception", "trophy"]: return
	page = destination
	projection_signature = ""
	UI.device_open(self, "club_board")
	screen.show()
	refresh()

func close_board(release: bool = true) -> void:
	if not is_open(): return
	screen.hide()
	if release: UI.device_closed(self)

func refresh() -> void:
	if not is_open(): return
	var ctx := CareerBridge.context
	var relevant := [page, ctx.get("team", {}).get("name", ""), ctx.get("date", ""),
		ctx.get("nextmatch"), ctx.get("club_trophies", {})]
	var signature := JSON.stringify(relevant)
	if signature == projection_signature: return
	projection_signature = signature
	UI.clear(content)
	if page == "reception": _reception(ctx)
	else: _honours(ctx)

func _reception(ctx: Dictionary) -> void:
	heading.text = "俱乐部前台 · 今日安排"
	var club := str(ctx.get("team", {}).get("name", ""))
	if not club.is_empty(): TeamVisuals.banner(content, club, club, str(ctx.get("date", "")))
	var game: Variant = ctx.get("nextmatch")
	if game is Dictionary and not game.is_empty():
		var card := UI.card(content)
		UI.label(card, str(game.get("event", "比赛安排")), 20)
		UI.label(card, "%s · 对阵 %s" % [game.get("date", ""), game.get("opponent", "")], 16)
		var attendance: Dictionary = game.get("attendance", {})
		UI.label(card, str(attendance.get("instruction", "到比赛电脑查看本场安排。")), 17, UI.GREEN)
		var place := str(attendance.get("display_name", ""))
		if not place.is_empty(): UI.label(card, "比赛地点：" + place, 15, UI.MUTED)
	else:
		UI.label(content, "今天没有待进行的正式比赛。可以去训练室，或找队友聊聊。", 18)
	UI.label(content, "赛程与邮件可以随时用手机查看。", 14, UI.MUTED)

func _honours(ctx: Dictionary) -> void:
	heading.text = "奖杯陈列柜"
	var honours: Dictionary = ctx.get("club_trophies", {})
	var club := str(honours.get("team", ctx.get("team", {}).get("name", "")))
	TeamVisuals.banner(content, club + " · 俱乐部荣誉" if not club.is_empty() else "俱乐部荣誉", club)
	var club_rows: Array = honours.get("rows", [])
	if club_rows.is_empty(): UI.label(content, "这个赛季的奖杯位置已经留好了。", 17, UI.MUTED)
	for row in club_rows: _honour_row(row, false)
	UI.divider(content)
	UI.label(content, "我的冠军", 22, UI.GREEN)
	var personal: Array = honours.get("personal_rows", [])
	if personal.is_empty(): UI.label(content, "你的个人冠军会记录在这里。", 16, UI.MUTED)
	for row in personal: _honour_row(row, true)

func _honour_row(record: Dictionary, personal: bool) -> void:
	var card := UI.card(content)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	card.add_child(row)
	var cup := Trophy.new()
	cup.custom_minimum_size = Vector2(52, 52)
	row.add_child(cup)
	var column := VBoxContainer.new()
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(column)
	UI.label(column, str(record.get("event", "赛事冠军")), 18)
	var category := "我的冠军" if personal else "加盟前的俱乐部冠军" if record.get("historical", false) else "俱乐部冠军"
	var stamp := str(record.get("date", record.get("year", "")))
	UI.label(column, "%s · %s · %s" % [stamp, record.get("team", ""), category], 14, UI.MUTED)

func _input(event: InputEvent) -> void:
	if not is_open() or not event is InputEventKey or not event.pressed or event.echo: return
	if event.physical_keycode in [KEY_E, KEY_ESCAPE, KEY_P]:
		close_board()
		UI.claim_key(self)
