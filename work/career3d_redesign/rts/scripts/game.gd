extends Control
## Standalone front end. Only the local simulator is imported: no Career
## service, CS2 plugin, real save, account or network connection is used.
const Sim = preload("res://rts/scripts/match_sim.gd")
const MapView = preload("res://rts/scripts/renderer.gd")
const MiniMap = preload("res://rts/scripts/minimap.gd")
const Style = preload("res://rts/scripts/style.gd")
const AudioCues = preload("res://rts/scripts/audio.gd")
const MapCatalog = preload("res://rts/scripts/map_catalog.gd")
const ROLE_NAMES := {"igl": "指挥", "entry": "突破", "awp": "主狙", "lurker": "自由人", "lurk": "自由人", "rifle": "步枪手", "support": "辅助"}
signal exit_requested
signal match_completed(report: Dictionary)
## The 3D computer passes a read-only roster. This simulation never settles Career.
var embedded := false
var initial_rosters: Dictionary = {}
var initial_team := "t"
var initial_map := "de_dust2"
var initial_overtime := false
var initial_mode := "command"
var initial_player_id := ""
var lock_player_identity := false
var mode_button: Button
var scoreboard_team_headings: Dictionary = {}
var selected_ids: Array = []
var sim
var renderer
var minimap
var audio
var map_data: Dictionary = {}
var rosters: Dictionary = {}
var state: Dictionary = {}
var _ready_ok := false
var mode := "play"
var viewer_team := "t"
var paused := false
var speed := 1.0
var selected_order_id := ""
var seed_value := 20261001
var _snapshot_clock := 0.0
var _hud_clock := 0.0
var _input_lock := 0.0
var _reload_request := false
var _smoke_request := false
var _flash_request := false
var _weapon_request := ""
var _last_round := -1
var _last_damage := 0
var _round_history: Array = []
var _finished_shown := false
var _capture_path := ""
var _capture_mode := ""
var main_menu: Control
var match_view: Control
var scoreboard: Control
var menu_mode: OptionButton
var menu_map: OptionButton
var menu_radar: TextureRect
var menu_map_name: Label
var map_heading: Label
var menu_team: OptionButton
var menu_player: OptionButton
var menu_description: Label
var resume_button: Button
var score_label: Label
var round_label: Label
var clock_label: Label
var bomb_label: Label
var status_label: Label
var score_strip: HBoxContainer
var team_heading: Label
var opponent_heading: Label
var own_rows: Dictionary = {}
var enemy_rows: Dictionary = {}
var scoreboard_rows: Dictionary = {}
var hud_name: Label
var hud_hp: Label
var hud_weapon: Label
var hud_ammo: Label
var hud_hint: Label
var health_bar: ProgressBar
var bomb_progress: ProgressBar
var feed_box: VBoxContainer
var feed_rows: Array[Label] = []
var event_history: Array[String] = []
var order_label: Label
var order_buttons: Dictionary = {}
var pause_button: Button
var speed_button: Button
var audio_button: Button
var result_banner: Control
var result_title: Label
var result_detail: Label
var score_title: Label
var score_subtitle: Label
var keyboard_hint: Label
var menu_notice: Label

func _ready() -> void:
	theme = Style.theme()
	audio = AudioCues.new()
	add_child(audio)
	map_data = MapCatalog.load_map(initial_map)
	rosters = _json("res://rts/data/rosters.json")
	if not initial_rosters.is_empty():
		rosters = initial_rosters.duplicate(true)
	_build_match()
	_build_menu()
	_build_scoreboard()
	_ready_ok = not map_data.is_empty() and not rosters.is_empty() and map_data.has("geometry")
	if not _ready_ok:
		menu_notice.text = "地图 %s 尚未完成导航验证：%s" % [initial_map, MapCatalog.entry(initial_map).get("reason", "资源尚未准备好")]
		get_node("MainMenu").find_child("StartMatchButton", true, false).disabled = true
	else:
		_update_menu_players()
	match_view.hide()
	main_menu.show()
	_parse_args()
	if not _capture_mode.is_empty() and _ready_ok:
		call_deferred("_capture_run")
	elif embedded and _ready_ok:
		call_deferred("start_match", initial_mode, initial_team, initial_player_id)

func _json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path): return {}
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed if parsed is Dictionary else {}

func _full(control: Control) -> void:
	control.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)

func _section(text: String, container: VBoxContainer) -> Label:
	var result := Style.label(text, 12, Style.MUTED)
	container.add_child(result)
	return result

func _build_menu() -> void:
	main_menu = Control.new()
	main_menu.name = "MainMenu"
	_full(main_menu)
	add_child(main_menu)
	var background := ColorRect.new()
	background.color = Style.BG
	_full(background)
	main_menu.add_child(background)
	var frame := MarginContainer.new()
	_full(frame)
	for side in ["left", "right"]: frame.add_theme_constant_override("margin_" + side, 64)
	for side in ["top", "bottom"]: frame.add_theme_constant_override("margin_" + side, 42)
	main_menu.add_child(frame)
	var content := VBoxContainer.new()
	content.add_theme_constant_override("separation", 30)
	frame.add_child(content)
	var masthead := HBoxContainer.new()
	content.add_child(masthead)
	masthead.add_child(Style.label("CS2  /  TACTICAL", 18, Style.GOLD))
	var stamp := Style.label("独立单机样本  ·  0.1", 13, Style.MUTED)
	stamp.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	stamp.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	masthead.add_child(stamp)
	var center_row := HBoxContainer.new()
	center_row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	center_row.add_theme_constant_override("separation", 38)
	content.add_child(center_row)
	var left := VBoxContainer.new()
	left.custom_minimum_size.x = 440
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.add_theme_constant_override("separation", 16)
	center_row.add_child(left)
	left.add_child(Style.label("战术地图 · 单机对抗", 36))
	var intro := Style.label("自己上场，也可以把回合交给队友。", 17, Style.MUTED)
	left.add_child(intro)
	var line := HSeparator.new()
	left.add_child(line)
	menu_map = OptionButton.new()
	menu_map.name = "MapSelector"
	menu_map.custom_minimum_size.y = 40
	for map_id in MapCatalog.available_maps():
		menu_map.add_item(str(MapCatalog.entry(map_id).get("name", map_id)))
		menu_map.set_item_metadata(menu_map.item_count - 1, map_id)
		if map_id == initial_map: menu_map.select(menu_map.item_count - 1)
	menu_map.disabled = embedded
	menu_map.item_selected.connect(func(index): select_map(str(menu_map.get_item_metadata(index))))
	left.add_child(menu_map)
	_section("游玩方式", left)
	menu_mode = OptionButton.new()
	menu_mode.custom_minimum_size.y = 44
	for item in ["亲自上场  ·  WASD + 鼠标", "战术指挥  ·  下达命令，看队友执行", "全场观战  ·  看十名选手对抗"]: menu_mode.add_item(item)
	menu_mode.item_selected.connect(func(_i): _update_menu_description())
	left.add_child(menu_mode)
	_section("我的队伍", left)
	menu_team = OptionButton.new()
	menu_team.custom_minimum_size.y = 44
	menu_team.add_item("Team Spirit  ·  进攻开局")
	menu_team.add_item("Vitality  ·  防守开局")
	menu_team.item_selected.connect(func(_i): _update_menu_players())
	left.add_child(menu_team)
	_section("控制选手", left)
	menu_player = OptionButton.new()
	menu_player.custom_minimum_size.y = 44
	menu_player.item_selected.connect(func(_i): _update_menu_description())
	left.add_child(menu_player)
	menu_description = Style.label("", 14, Style.MUTED)
	menu_description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	menu_description.custom_minimum_size.y = 48
	left.add_child(menu_description)
	var start := Style.button("开始对局", _start_from_menu, Vector2(0, 52))
	start.name = "StartMatchButton"
	Style.accent_button(start)
	left.add_child(start)
	resume_button = Style.button("继续当前对局", _resume_match, Vector2(0, 40))
	resume_button.hide()
	left.add_child(resume_button)
	menu_notice = Style.label("不会启动 CS2，不读取或修改生涯存档。", 12, Style.MUTED)
	menu_notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	left.add_child(menu_notice)
	var right := Style.panel(Color("172229"), 20)
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center_row.add_child(right)
	var art := VBoxContainer.new()
	art.add_theme_constant_override("separation", 12)
	right.add_child(art)
	var radar := TextureRect.new()
	menu_radar = radar
	if not map_data.is_empty(): radar.texture = load(str(map_data.get("radar", {}).get("image", "")))
	radar.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	radar.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	radar.size_flags_vertical = Control.SIZE_EXPAND_FILL
	radar.custom_minimum_size = Vector2(400, 420)
	art.add_child(radar)
	menu_map_name = Style.label(str(map_data.get("name", initial_map)).to_upper(), 24, Style.GOLD)
	art.add_child(menu_map_name)
	art.add_child(Style.label("5 vs 5  /  MR12  /  下包与回防", 13, Style.MUTED))
	var features := Style.label("真实雷达与现有导航资料重新投影\n独立战斗、武器与回合统计", 13, Style.MUTED)
	features.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	art.add_child(features)
	content.add_child(Style.label("WASD 移动   /   鼠标左键开火   /   E 下包、拆包   /   Tab 战绩   /   Esc 菜单", 13, Style.MUTED))

func select_map(map_id: String) -> bool:
	var loaded := MapCatalog.load_map(map_id)
	if loaded.is_empty(): return false
	initial_map = map_id
	map_data = loaded
	_ready_ok = not rosters.is_empty()
	if menu_radar != null: menu_radar.texture = load(str(map_data["radar"]["image"]))
	if menu_map_name != null: menu_map_name.text = str(map_data.get("name", map_id)).to_upper()
	if map_heading != null: map_heading.text = str(map_data.get("name", map_id)).to_upper()
	for key in order_buttons: order_buttons[key].text = _order_title(str(key))
	return true

func _order_title(order: String) -> String:
	var native: Dictionary = {"attack_a_short": "A 小推进", "attack_a_long": "A 大推进", "attack_b": "B 洞进攻", "split_b": "中路夹 B", "default": "默认分工", "hold": "原地守住"}
	var generic: Dictionary = {"attack_a_short": "A 辅路推进", "attack_a_long": "A 主路推进", "attack_b": "B 点推进", "split_b": "分路夹 B", "default": "默认分工", "hold": "原地守住"}
	return str((native if map_data.get("map", "") == "de_dust2" else generic).get(order, order))

func _update_menu_players() -> void:
	menu_player.clear()
	var team := "t" if menu_team.selected == 0 else "ct"
	for card in rosters.get(team, []):
		menu_player.add_item(str(card["name"]) + "  ·  " + ROLE_NAMES.get(card.get("role", "rifle"), "步枪手"))
	if team == "t" and menu_player.item_count > 4: menu_player.select(4)
	elif team == "ct" and menu_player.item_count > 1: menu_player.select(1)
	_update_menu_description()

func _update_menu_description() -> void:
	menu_player.disabled = menu_mode.selected != 0
	if menu_mode.selected == 1:
		menu_description.text = "战术按钮指挥全队；点选队友，再在地图上右键，可以单独安排走位。"
	elif menu_mode.selected == 2:
		menu_description.text = "双方全部可见。可以暂停、加速、查看战绩；不会影响 AI 的判断。"
	else:
		var team := "t" if menu_team.selected == 0 else "ct"
		var cards: Array = rosters.get(team, [])
		if not cards.is_empty():
			var card: Dictionary = cards[clampi(menu_player.selected, 0, cards.size() - 1)]
			menu_description.text = "%s · 能力 %d\n阵亡后可以点选一名存活队友，继续上场。" % [card["name"], int(card.get("ability", 80))]

func _build_match() -> void:
	match_view = Control.new()
	match_view.name = "MatchView"
	_full(match_view)
	add_child(match_view)
	var background := ColorRect.new()
	background.color = Style.BG
	_full(background)
	match_view.add_child(background)
	var margin := MarginContainer.new()
	_full(margin)
	for side in ["left", "right", "top", "bottom"]: margin.add_theme_constant_override("margin_" + side, 14)
	match_view.add_child(margin)
	var root_box := VBoxContainer.new()
	root_box.add_theme_constant_override("separation", 10)
	margin.add_child(root_box)
	var header := Style.panel(Style.PANEL, 12)
	root_box.add_child(header)
	var head := HBoxContainer.new()
	head.alignment = BoxContainer.ALIGNMENT_CENTER
	header.add_child(head)
	var map_title := VBoxContainer.new()
	map_title.custom_minimum_size.x = 200
	head.add_child(map_title)
	map_heading = Style.label(str(map_data.get("name", initial_map)).to_upper(), 19, Style.GOLD)
	map_title.add_child(map_heading)
	round_label = Style.label("第 1 回合 · 准备", 12, Style.MUTED)
	map_title.add_child(round_label)
	var score_box := VBoxContainer.new()
	score_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(score_box)
	score_label = Style.label("TEAM SPIRIT   0 : 0   VITALITY", 24)
	score_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	score_box.add_child(score_label)
	clock_label = Style.label("1:55", 16, Style.GOLD)
	clock_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	score_box.add_child(clock_label)
	var controls := HBoxContainer.new()
	head.add_child(controls)
	pause_button = Style.button("暂停", _toggle_pause, Vector2(66, 38))
	controls.add_child(pause_button)
	speed_button = Style.button("1×", _cycle_speed, Vector2(48, 38))
	controls.add_child(speed_button)
	audio_button = Style.button("音效", _toggle_sound, Vector2(62, 38))
	controls.add_child(audio_button)
	controls.add_child(Style.button("战绩", open_scoreboard))
	controls.add_child(Style.button("菜单", go_menu))
	if embedded:
		mode_button = Style.button("切换操控", cycle_mode, Vector2(88, 38))
		mode_button.name = "RTSModeSwitch"
		mode_button.tooltip_text = "不重开回合，在指挥、本人操控与观战之间切换。"
		controls.add_child(mode_button)
		controls.add_child(Style.button("返回电脑", func(): exit_requested.emit()))
	var center_row := HBoxContainer.new()
	center_row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	center_row.add_theme_constant_override("separation", 10)
	root_box.add_child(center_row)
	var own_panel := Style.panel(Style.PANEL, 12)
	own_panel.custom_minimum_size.x = 208
	center_row.add_child(own_panel)
	var own_box := VBoxContainer.new()
	own_panel.add_child(own_box)
	team_heading = _section("我的队伍", own_box)
	for i in range(5):
		var row := _roster_row(i, true)
		own_box.add_child(row["panel"])
		own_rows[i] = row
	var filler := Control.new()
	filler.size_flags_vertical = Control.SIZE_EXPAND_FILL
	own_box.add_child(filler)
	_section("指挥", own_box)
	var commands := GridContainer.new()
	commands.columns = 2
	commands.add_theme_constant_override("h_separation", 4)
	commands.add_theme_constant_override("v_separation", 4)
	own_box.add_child(commands)
	for pair in [["A 小推进", "attack_a_short"], ["A 大推进", "attack_a_long"], ["B 洞进攻", "attack_b"], ["中路夹 B", "split_b"], ["默认分工", "default"], ["原地守住", "hold"]]:
		var action := str(pair[1])
		var button := Style.button(_order_title(action), func(): issue_order(action), Vector2(0, 29))
		button.add_theme_font_size_override("font_size", 13)
		for state_name in ["normal", "hover", "pressed"]:
			button.add_theme_stylebox_override(state_name, Style.box(Style.SURFACE if state_name == "normal" else Color("31424c"), 7, 6))
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		commands.add_child(button)
		order_buttons[action] = button
	order_label = Style.label("全队指令", 11, Style.MUTED)
	order_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	own_box.add_child(order_label)
	var map_box := VBoxContainer.new()
	map_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	map_box.size_flags_vertical = Control.SIZE_EXPAND_FILL
	center_row.add_child(map_box)
	var toolbar := HBoxContainer.new()
	map_box.add_child(toolbar)
	status_label = Style.label("亲自上场 · 己方视野", 12, Style.MUTED)
	status_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	toolbar.add_child(status_label)
	toolbar.add_child(Style.button("−", func(): renderer.change_zoom(1 / 1.2), Vector2(32, 28)))
	toolbar.add_child(Style.button("＋", func(): renderer.change_zoom(1.2), Vector2(32, 28)))
	toolbar.add_child(Style.button("全图", func(): renderer.fit_map(), Vector2(50, 28)))
	toolbar.add_child(Style.button("跟随", _follow_camera, Vector2(50, 28)))
	toolbar.add_child(Style.button("路线", func(): renderer.show_routes = not renderer.show_routes, Vector2(50, 28)))
	renderer = MapView.new()
	renderer.name = "MapView"
	renderer.custom_minimum_size = Vector2(420, 280)
	renderer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	renderer.move_order.connect(_map_move)
	renderer.actor_selected.connect(_select_actor)
	renderer.units_selected.connect(_select_units)
	map_box.add_child(renderer)
	var strip_panel := Style.panel(Color("172027"), 9)
	map_box.add_child(strip_panel)
	var strip_box := VBoxContainer.new()
	strip_panel.add_child(strip_box)
	var strip_heading := HBoxContainer.new()
	strip_box.add_child(strip_heading)
	strip_heading.add_child(Style.label("回合轨迹", 11, Style.MUTED))
	bomb_label = Style.label("", 11, Style.GOLD)
	bomb_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bomb_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	strip_heading.add_child(bomb_label)
	score_strip = HBoxContainer.new()
	score_strip.add_theme_constant_override("separation", 4)
	strip_box.add_child(score_strip)
	for i in range(24):
		var mark := Style.label(str(i + 1), 10, Style.MUTED)
		mark.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		mark.custom_minimum_size = Vector2(18, 22)
		mark.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		score_strip.add_child(mark)
	var enemy_panel := Style.panel(Style.PANEL, 12)
	enemy_panel.custom_minimum_size.x = 230
	center_row.add_child(enemy_panel)
	var enemy_box := VBoxContainer.new()
	enemy_panel.add_child(enemy_box)
	opponent_heading = _section("对手", enemy_box)
	for i in range(5):
		var row := _roster_row(i, false)
		enemy_box.add_child(row["panel"])
		enemy_rows[i] = row
	minimap = MiniMap.new()
	minimap.custom_minimum_size = Vector2(185, 100)
	minimap.size_flags_vertical = Control.SIZE_EXPAND_FILL
	minimap.map_view = renderer
	minimap.camera_requested.connect(func(point):
		renderer.follow_player = false
		renderer.center = point
		renderer.zoom = 2.0)
	enemy_box.add_child(minimap)
	_section("对局动态", enemy_box)
	feed_box = VBoxContainer.new()
	enemy_box.add_child(feed_box)
	for i in range(3):
		var feed := Style.label("", 12, Style.MUTED)
		feed.custom_minimum_size.y = 16
		feed.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		feed_box.add_child(feed)
		feed_rows.append(feed)
	var bottom := Style.panel(Style.PANEL, 14)
	root_box.add_child(bottom)
	var hud := HBoxContainer.new()
	hud.add_theme_constant_override("separation", 26)
	bottom.add_child(hud)
	var player_box := VBoxContainer.new()
	player_box.custom_minimum_size.x = 215
	hud.add_child(player_box)
	hud_name = Style.label("donk", 19)
	player_box.add_child(hud_name)
	var hp_box := HBoxContainer.new()
	player_box.add_child(hp_box)
	hud_hp = Style.label("100 HP", 16, Style.GREEN)
	hud_hp.custom_minimum_size.x = 75
	hp_box.add_child(hud_hp)
	health_bar = ProgressBar.new()
	health_bar.show_percentage = false
	health_bar.custom_minimum_size = Vector2(120, 7)
	health_bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	hp_box.add_child(health_bar)
	var weapon_box := VBoxContainer.new()
	weapon_box.custom_minimum_size.x = 180
	hud.add_child(weapon_box)
	hud_weapon = Style.label("AK-47", 16, Style.GOLD)
	weapon_box.add_child(hud_weapon)
	hud_ammo = Style.label("30  /  90", 20)
	weapon_box.add_child(hud_ammo)
	var help_box := VBoxContainer.new()
	help_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hud.add_child(help_box)
	hud_hint = Style.label("", 13, Style.TEXT)
	help_box.add_child(hud_hint)
	bomb_progress = ProgressBar.new()
	bomb_progress.show_percentage = false
	bomb_progress.custom_minimum_size.y = 6
	bomb_progress.hide()
	help_box.add_child(bomb_progress)
	keyboard_hint = Style.label("WASD 移动  ·  Shift 静步  ·  左键开火  ·  R 换弹  ·  E 下包 / 拆包\nQ 烟雾  ·  G 闪光  ·  1 / 2 切枪  ·  地图右键指挥  ·  Tab 战绩", 11, Style.MUTED)
	help_box.add_child(keyboard_hint)
	result_banner = CenterContainer.new()
	_full(result_banner)
	result_banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	match_view.add_child(result_banner)
	var result_panel := Style.panel(Color(.07, .11, .14, .94), 22)
	result_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	result_banner.add_child(result_panel)
	var result_box := VBoxContainer.new()
	result_panel.add_child(result_box)
	result_title = Style.label("回合胜利", 28, Style.GREEN)
	result_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	result_box.add_child(result_title)
	result_detail = Style.label("", 14, Style.MUTED)
	result_detail.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	result_box.add_child(result_detail)
	result_banner.hide()

func _roster_row(index: int, own: bool) -> Dictionary:
	var panel := Style.panel(Color("1d2a32"), 4)
	var layout := VBoxContainer.new()
	layout.add_theme_constant_override("separation", 3)
	panel.add_child(layout)
	var headline := HBoxContainer.new()
	layout.add_child(headline)
	var name_value: Control = Style.button("—", func(): _roster_click(index), Vector2(0, 24)) if own else Style.label("—", 15)
	if name_value is Button:
		name_value.add_theme_stylebox_override("normal", Style.box(Color.TRANSPARENT, 3, 0))
		name_value.add_theme_stylebox_override("hover", Style.box(Color("31424c"), 3, 0))
		name_value.alignment = HORIZONTAL_ALIGNMENT_LEFT
		name_value.add_theme_font_size_override("font_size", 15)
		name_value.tooltip_text = "上场模式：切换控制；指挥模式：选中后右键安排走位。"
	name_value.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	headline.add_child(name_value)
	var stats := Style.label("0 / 0 / 0", 11, Style.MUTED)
	stats.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	headline.add_child(stats)
	var detail := Style.label("", 11, Style.MUTED)
	layout.add_child(detail)
	return {"panel": panel, "name": name_value, "detail": detail, "stats": stats, "last_style": ""}

func _build_scoreboard() -> void:
	scoreboard = Control.new()
	scoreboard.name = "ScoreboardOverlay"
	_full(scoreboard)
	add_child(scoreboard)
	var veil := ColorRect.new()
	veil.color = Color(.03, .05, .07, .87)
	_full(veil)
	scoreboard.add_child(veil)
	var center_box := CenterContainer.new()
	_full(center_box)
	scoreboard.add_child(center_box)
	var panel := Style.panel(Style.PANEL, 26)
	panel.custom_minimum_size.x = 960
	center_box.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 12)
	panel.add_child(box)
	score_title = Style.label("全场战绩", 27)
	box.add_child(score_title)
	score_subtitle = Style.label("", 13, Style.MUTED)
	box.add_child(score_subtitle)
	for team in ["t", "ct"]:
		var heading := Style.label("", 14, Style.GOLD if team == "t" else Style.BLUE)
		box.add_child(heading)
		scoreboard_team_headings[team] = heading
		var header := HBoxContainer.new()
		box.add_child(header)
		for item in [["选手 / 位置", 275], ["K", 65], ["D", 65], ["A", 65], ["伤害", 95], ["ADR", 100], ["KAST", 100], ["Rating", 95]]:
			var label := Style.label(str(item[0]), 12, Style.MUTED)
			label.custom_minimum_size.x = item[1]
			header.add_child(label)
		for i in range(5):
			var row := HBoxContainer.new()
			box.add_child(row)
			var cells: Array[Label] = []
			for width in [275, 65, 65, 65, 95, 100, 100, 95]:
				var label := Style.label("—", 14)
				label.custom_minimum_size = Vector2(width, 26)
				row.add_child(label)
				cells.append(label)
			scoreboard_rows[team + str(i)] = cells
	var actions := HBoxContainer.new()
	box.add_child(actions)
	actions.add_child(Style.button("返回对局", _close_scoreboard))
	actions.add_child(Style.button("重新选人", go_menu))
	actions.add_child(Style.button("保存本场战报", _save_report))
	scoreboard.hide()

func _start_from_menu() -> void:
	var start: Button = main_menu.find_child("StartMatchButton", true, false)
	start.disabled = true
	start.text = "准备对局…"
	await get_tree().process_frame
	var team := "t" if menu_team.selected == 0 else "ct"
	var chosen_mode: String = ["play", "command", "spectate"][menu_mode.selected]
	var cards: Array = rosters.get(team, [])
	var player := str(cards[clampi(menu_player.selected, 0, cards.size() - 1)]["id"]) if not cards.is_empty() else ""
	seed_value += 1
	start_match(chosen_mode, team, player)
	start.text = "开始对局"
	start.disabled = false

func start_match(play_mode: String = "play", team: String = "t", player_id: String = "") -> void:
	if not _ready_ok: return
	mode = play_mode
	viewer_team = team
	var cards: Dictionary = rosters.duplicate(true)
	if player_id.is_empty() and mode == "play": player_id = str(cards[viewer_team][0]["id"])
	cards["human_id"] = player_id if mode == "play" else ""
	sim = Sim.new()
	if not sim.configure(map_data, cards, seed_value, map_data.get("botlab_knowledge", {}), initial_overtime):
		menu_notice.text = "本场未能启动：请查看 runtime/godot.log。"
		return
	sim.set_human_control(mode == "play")
	paused = false
	speed = 1.0
	selected_order_id = ""
	selected_ids.clear()
	_clear_action_requests()
	_input_lock = .3
	_finished_shown = false
	_last_round = -1
	event_history.clear()
	state = sim.snapshot(true)
	_round_history = []
	audio.muted = audio_button.text == "静音"
	renderer.setup(map_data, sim.get_map_model() if sim.has_method("get_map_model") else sim._nav)
	minimap.setup(map_data)
	renderer.reset_camera(mode, _controlled())
	renderer.update_state(state, mode, viewer_team, str(state.get("human_id", "")))
	renderer.commander = mode == "command"
	renderer.selected_ids = selected_ids.duplicate()
	main_menu.hide()
	scoreboard.hide()
	match_view.show()
	speed_button.disabled = mode == "play"
	pause_button.text = "暂停"
	speed_button.text = "1×"
	resume_button.show()
	_refresh()
	_consume_events()
	if is_instance_valid(mode_button): mode_button.text = "亲自操控" if mode == "command" else "只看 / 观战" if mode == "play" else "继续指挥"

func cycle_mode() -> bool:
	if sim == null or state.get("finished", false): return false
	renderer.cancel_pointer()
	_clear_action_requests()
	if mode == "command":
		var id := initial_player_id
		if id.is_empty():
			for actor in state.get("players", []):
				if actor.get("team", "") == viewer_team and actor.get("alive", false): id = str(actor.id); break
		if not sim.select_human(id):
			# Keep the Career identity fixed after death, but do not make the
			# mode button a dead end: skip personal control and enter viewing.
			mode = "spectate"
			sim.set_human_control(false)
			order_label.text = "你的角色已阵亡，切换为观战；仍可返回指挥。"
		else:
			mode = "play"
			sim.set_human_control(true)
			speed = 1.0
	elif mode == "play":
		mode = "spectate"
		sim.set_human_control(false)
	else:
		mode = "command"
		sim.set_human_control(false)
	selected_ids.clear()
	selected_order_id = ""
	renderer.selected_ids = []
	state = sim.snapshot(true)
	renderer.commander = mode == "command"
	renderer.reset_camera(mode, _controlled())
	renderer.update_state(state, mode, viewer_team, str(state.get("human_id", "")))
	minimap.spectator = mode == "spectate"
	speed_button.disabled = mode == "play"
	_input_lock = .2
	if is_instance_valid(mode_button): mode_button.text = "亲自操控" if mode == "command" else "只看 / 观战" if mode == "play" else "继续指挥"
	_refresh()
	return true

func _process(dt: float) -> void:
	if sim == null or not match_view.visible or not _ready_ok: return
	_input_lock = maxf(0, _input_lock - dt)
	if not paused and not scoreboard.visible and not state.get("finished", false):
		sim.step(minf(dt, .1) * speed, _human_input())
		_reload_request = false
		_smoke_request = false
		_flash_request = false
		_weapon_request = ""
		_consume_events()
	_snapshot_clock += dt
	_hud_clock += dt
	if _snapshot_clock >= 1.0 / 45:
		_snapshot_clock = 0
		state = sim.snapshot()
		if int(state.get("rounds_completed", 0)) != _round_history.size():
			_round_history = sim.snapshot(true).get("round_history", [])
		state["round_history"] = _round_history
		renderer.update_state(state, mode, viewer_team, str(state.get("human_id", "")))
		minimap.state = state
		minimap.team = viewer_team
		minimap.spectator = mode == "spectate"
	if _hud_clock >= .1:
		_hud_clock = 0
		_refresh()
	if state.get("finished", false) and not _finished_shown:
		_finished_shown = true
		match_completed.emit(sim.report())
		open_scoreboard()

func _human_input() -> Dictionary:
	if mode != "play" or _input_lock > 0: return {}
	var direction := Vector2.ZERO
	if Input.is_physical_key_pressed(KEY_W): direction.y -= 1
	if Input.is_physical_key_pressed(KEY_S): direction.y += 1
	if Input.is_physical_key_pressed(KEY_A): direction.x -= 1
	if Input.is_physical_key_pressed(KEY_D): direction.x += 1
	var over_map: bool = renderer.get_global_rect().has_point(get_global_mouse_position())
	var human := _controlled()
	var aim: Vector2 = renderer.screen_to_world(get_global_mouse_position()) if over_map else MapView.vec(human.get("aim", Vector2.ZERO))
	return {"move": direction, "aim": aim, "fire": over_map and Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT),
		"reload": _reload_request, "interact": Input.is_physical_key_pressed(KEY_E),
		"walk": Input.is_physical_key_pressed(KEY_SHIFT), "smoke": _smoke_request,
		"flash": _flash_request, "weapon": _weapon_request}

func _input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo: return
	if main_menu.visible and (menu_team.get_popup().visible or menu_player.get_popup().visible or menu_mode.get_popup().visible): return
	if event.keycode == KEY_ESCAPE:
		if scoreboard.visible: _close_scoreboard()
		elif main_menu.visible and sim != null: _resume_match()
		else: go_menu()
		get_viewport().set_input_as_handled()
		return
	if not match_view.visible: return
	if (paused or scoreboard.visible or state.get("finished", false)) and event.physical_keycode in [KEY_R, KEY_Q, KEY_G, KEY_1, KEY_2]:
		get_viewport().set_input_as_handled()
		return
	match event.physical_keycode:
		KEY_SPACE: _toggle_pause()
		KEY_TAB:
			if scoreboard.visible: _close_scoreboard()
			else: open_scoreboard()
		KEY_R: _reload_request = true
		KEY_Q: _smoke_request = true
		KEY_G: _flash_request = true
		KEY_1: _weapon_request = "primary"
		KEY_2: _weapon_request = "pistol"
		KEY_F: _follow_camera()
		KEY_Z: issue_order("attack_a_short")
		KEY_X: issue_order("attack_b")
		KEY_C: issue_order("default")
		KEY_V: issue_order("hold")
	if event.physical_keycode in [KEY_SPACE, KEY_TAB, KEY_R, KEY_Q, KEY_G, KEY_1, KEY_2, KEY_F, KEY_Z, KEY_X, KEY_C, KEY_V]:
		get_viewport().set_input_as_handled()

func _consume_events() -> void:
	for event in sim.pop_events():
		renderer.push_event(event)
		audio.play_event(str(event.get("type", "")), event)
		var text := _event_text(event)
		if not text.is_empty():
			event_history.push_front(text)
			if event_history.size() > 5: event_history.pop_back()

func _event_text(event: Dictionary) -> String:
	match str(event.get("type", "")):
		"kill": return "%s  →  %s" % [_name(str(event.get("killer_id", event.get("killer", "")))), _name(str(event.get("victim_id", event.get("victim", ""))))]
		"bomb_planted": return "C4 已安放在 %s 点" % str(event.get("site", ""))
		"bomb_defused": return "炸弹已拆除"
		"bomb_pickup": return "%s 捡起 C4" % _name(str(event.get("id", "")))
		"round_end": return str(event.get("reason", "回合结束"))
		"utility_throw": return "%s 使用%s" % [_name(str(event.get("id", ""))), "烟雾" if event.get("kind", "") == "smoke" else "闪光"]
	return ""

func _name(id: String) -> String:
	for p in state.get("players", []):
		if p["id"] == id: return str(p["name"])
	return id if not id.is_empty() else "世界"

func _controlled() -> Dictionary:
	var id := str(state.get("human_id", ""))
	for p in state.get("players", []):
		if p["id"] == id: return p
	return {}

func _refresh() -> void:
	if state.is_empty(): return
	minimap.state = state
	minimap.team = viewer_team
	minimap.spectator = mode == "spectate"
	var names: Dictionary = rosters.get("team_names", {"t": "Team Spirit", "ct": "Vitality"})
	var scores: Dictionary = state.get("score", {"t": 0, "ct": 0})
	score_label.text = "%s   %d : %d   %s" % [str(names.get("t", "Team Spirit")).to_upper(), int(scores["t"]), int(scores["ct"]), str(names.get("ct", "Vitality")).to_upper()]
	var phase := str(state.get("phase", "freeze"))
	var round_number := int(state.get("round", 1))
	round_label.text = "第 %d 回合 · %s" % [round_number, "准备" if phase == "freeze" else "进行中" if phase == "live" else "结束"]
	var bomb: Dictionary = state.get("bomb", {})
	var seconds := int(ceil(float(bomb.get("remaining", 40)))) if bomb.get("state", "") == "planted" else int(ceil(float(state.get("round_time", 115))))
	clock_label.text = "C4  %d 秒" % seconds if bomb.get("state", "") == "planted" else "%d:%02d" % [seconds / 60, seconds % 60]
	clock_label.modulate = Style.RED if bomb.get("state", "") == "planted" else Style.GOLD
	bomb_label.text = "C4 已下包 · %s 点" % bomb.get("site", "") if bomb.get("state", "") == "planted" else "MR12 · 第 13 回合换边"
	status_label.text = ("亲自上场" if mode == "play" else "战术指挥" if mode == "command" else "全场观战") + (" · 已暂停" if paused else " · 全部可见" if mode == "spectate" else " · 己方视野")
	if mode == "command":
		keyboard_hint.text = "左键点选 / 框选队员 · Shift 多选 · 右键走位 · Shift + 右键追加路点\n滚轮缩放 · 中键拖图 · V 守住 · C 默认分工 · 空格暂停 · Tab 战绩"
	var sides: Dictionary = state.get("team_sides", {"t": "t", "ct": "ct"})
	if bomb.get("state", "") == "carried" and (sides.get(viewer_team, "t") == "t" or mode == "spectate"):
		bomb_label.text = "C4 · %s 携带" % _name(str(bomb.get("carrier_id", "")))
	elif bomb.get("state", "") == "dropped" and (sides.get(viewer_team, "t") == "t" or mode == "spectate" or renderer._point_observed(MapView.vec(bomb.get("pos", Vector2.ZERO)))):
		bomb_label.text = "C4 掉落 · 可以前往拾取"
	team_heading.text = str(names.get(viewer_team, "我的队伍")) + "  ·  " + ("T" if sides.get(viewer_team, "t") == "t" else "CT")
	var other := "ct" if viewer_team == "t" else "t"
	opponent_heading.text = str(names.get(other, "对手")) + "  ·  " + ("T" if sides.get(other, "ct") == "t" else "CT")
	var own_index := 0
	var enemy_index := 0
	for p in state.get("players", []):
		var own: bool = p["team"] == viewer_team
		var row: Dictionary = own_rows[own_index] if own else enemy_rows[enemy_index]
		if own: own_index += 1
		else: enemy_index += 1
		var active: bool = (p["id"] == state.get("human_id", "") and mode == "play") or p["id"] in selected_ids
		var carrying: bool = bomb.get("state", "") == "carried" and bomb.get("carrier_id", "") == p["id"] and (own or mode == "spectate")
		row["name"].text = ("▶ " if active else "") + str(p["name"]) + (" · C4" if carrying else "")
		row["name"].modulate = Style.TEXT if p["alive"] else Style.MUTED.darkened(.3)
		var visible: bool = own or mode == "spectate" or viewer_team in p.get("spotted_by", [])
		row["detail"].text = "%s · %s · %s" % [ROLE_NAMES.get(p.get("role", "rifle"), "步枪手"), str(p.get("weapon_name", p.get("weapon", "步枪"))) if visible else "未发现", "%d HP" % int(p["hp"]) if p["alive"] and visible else "阵亡" if not p["alive"] else "—"]
		row["stats"].text = "%d / %d / %d" % [int(p["k"]), int(p["d"]), int(p["a"])]
		var style_key := "selected" if active else "alive" if p["alive"] else "dead"
		if row["last_style"] != style_key:
			row["last_style"] = style_key
			row["panel"].add_theme_stylebox_override("panel", Style.box(Color("29403f") if active else Color("1d2a32") if p["alive"] else Color("161f25"), 8, 4, Style.GREEN if active else Color.TRANSPARENT))
	for i in range(feed_rows.size()): feed_rows[i].text = event_history[i] if i < event_history.size() else ""
	if _last_round != round_number or phase == "round_end" or phase == "finished":
		_last_round = round_number
		_refresh_strip()
	result_banner.visible = phase == "round_end"
	if phase == "round_end":
		var history: Array = state.get("round_history", [])
		if not history.is_empty():
			var latest: Dictionary = history.back()
			var victory: bool = latest["winner"] == viewer_team
			result_title.text = "回合胜利" if victory else "回合失利"
			result_title.modulate = Style.GREEN if victory else Style.RED
			result_detail.text = str(latest["reason"])
	_refresh_player()
	if scoreboard.visible: _refresh_scoreboard()

func _refresh_strip() -> void:
	var history: Array = state.get("round_history", [])
	for i in range(24):
		var mark: Label = score_strip.get_child(i)
		var color := Style.GREEN if i < history.size() and history[i]["winner"] == viewer_team else Style.RED if i < history.size() else Style.MUTED.darkened(.45)
		mark.add_theme_color_override("font_color", color)
		mark.text = "●" if i < history.size() else str(i + 1)
		mark.tooltip_text = "%d · %s" % [i + 1, history[i]["reason"]] if i < history.size() else "第 %d 回合" % (i + 1)

func _refresh_player() -> void:
	for button in order_buttons.values():
		button.disabled = mode == "spectate" or state.get("finished", false)
	var p := _controlled()
	if p.is_empty():
		hud_name.text = "战术指挥" if mode == "command" else "全场观战"
		var alive := {"t": 0, "ct": 0}
		for actor in state.get("players", []):
			if actor.get("alive", false): alive[actor["team"]] += 1
		hud_hp.text = "%d vs %d 存活" % [alive[viewer_team], alive["ct" if viewer_team == "t" else "t"]]
		health_bar.value = alive[viewer_team] * 20
		hud_weapon.text = "选择队友 → 右键走位" if mode == "command" else "全场观战 · 不下达指令"
		hud_ammo.text = str(map_data.get("name", initial_map)) + " / MR12"
		hud_hint.text = "暂停看局势，或用左侧按钮调整团队路线。" if mode == "command" else "空格暂停 · Tab 查看战绩 · 滚轮缩放地图"
		bomb_progress.hide()
		return
	hud_name.text = str(p["name"])
	hud_hp.text = "%d HP" % int(p["hp"])
	health_bar.value = float(p["hp"])
	hud_weapon.text = str(p.get("weapon_name", p.get("weapon", "步枪"))) + "  ·  $%d" % int(p.get("money", 0))
	hud_ammo.text = "%d  /  %d" % [int(p.get("ammo", 0)), int(p.get("reserve", 0))]
	var bomb: Dictionary = state.get("bomb", {})
	hud_hint.text = "携带 C4 · 到 A / B 点停下，按住 E 下包" if bomb.get("carrier_id", "") == p["id"] else "CT 回防 · 到 C4 附近，按住 E 拆包" if p.get("side", "t") == "ct" and bomb.get("state", "") == "planted" else "停下再开火更准 · 右键可以指挥队友走位"
	if not p["alive"]: hud_hint.text = "你已阵亡 · 点击左侧存活队友继续上场，或观看本回合。"
	if float(p.get("reloading", 0)) > 0: hud_hint.text = "正在换弹…"
	bomb_progress.visible = bomb.get("actor_id", "") == p["id"] and not str(bomb.get("action", "")).is_empty()
	if bomb_progress.visible:
		var total := 3.0 if bomb.get("action", "") == "plant" else 5.0 if p.get("has_kit", false) else 10.0
		bomb_progress.value = minf(100, float(bomb.get("progress", 0)) / total * 100)
		hud_hint.text = "正在安放 C4…" if bomb.get("action", "") == "plant" else "正在拆除 C4…"

func _roster_click(index: int) -> void:
	var ours: Array = state.get("players", []).filter(func(p): return p["team"] == viewer_team)
	if index < ours.size(): _select_actor(str(ours[index]["id"]))

func _select_actor(id: String) -> void:
	if sim == null: return
	if mode == "play":
		if lock_player_identity and id != initial_player_id:
			order_label.text = "亲自操控使用你的生涯角色；切换指挥可安排其他队员。"
			return
		if sim.select_human(id):
			_clear_action_requests()
			state = sim.snapshot(true)
			renderer.follow_player = true
			renderer.controlled_id = id
			_input_lock = .2
			_refresh()
	else:
		_select_units([id], Input.is_physical_key_pressed(KEY_SHIFT))

func _select_units(ids: Array, additive: bool = false) -> void:
	if sim == null or mode != "command": return
	if not additive: selected_ids.clear()
	for id in ids:
		var actor: Dictionary = {}
		for p in state.get("players", []):
			if p["id"] == id: actor = p; break
		if actor.get("team", "") != viewer_team or not actor.get("alive", false): continue
		if additive and id in selected_ids: selected_ids.erase(id)
		elif id not in selected_ids: selected_ids.append(id)
	selected_order_id = str(selected_ids[0]) if selected_ids.size() == 1 else ""
	renderer.selected_ids = selected_ids.duplicate()
	order_label.text = "全队指令" if selected_ids.is_empty() else "已选 %s · 右键走位，Shift 追加路点" % _selection_caption()
	_refresh()

func _selection_caption() -> String:
	var names := PackedStringArray()
	for id in selected_ids: names.append(_name(str(id)))
	return "全队" if names.is_empty() else "、".join(names)

func issue_order(order: String) -> void:
	if sim == null or mode == "spectate" or not match_view.visible or scoreboard.visible or state.get("finished", false): return
	var ids: Array = selected_ids.duplicate()
	if sim.command(viewer_team, order, ids):
		var text: String = _order_title(order)
		order_label.text = _selection_caption() + " · " + text
		state = sim.snapshot(true)

func _map_move(point: Vector2) -> void:
	if sim == null or mode == "spectate" or not match_view.visible or scoreboard.visible or state.get("finished", false): return
	var ids: Array = selected_ids.duplicate()
	var append := mode == "command" and Input.is_physical_key_pressed(KEY_SHIFT)
	if sim.command_move(viewer_team, point, ids, append):
		order_label.text = _selection_caption() + (" · 追加路点" if append else " · 前往标记位置")
	else:
		order_label.text = str(sim.command_error)

func _follow_camera() -> void:
	if mode == "play":
		renderer.follow_player = true
		renderer.zoom = maxf(1.6, renderer.zoom)
	else:
		renderer.fit_map()

func _toggle_pause() -> void:
	_clear_action_requests()
	paused = not paused
	pause_button.text = "继续" if paused else "暂停"
	_refresh()

func _cycle_speed() -> void:
	if mode == "play": return
	speed = 2.0 if speed == 1.0 else 4.0 if speed == 2.0 else 1.0
	speed_button.text = "%d×" % int(speed)

func _toggle_sound() -> void:
	var is_muted: bool = audio.toggle()
	audio_button.text = "静音" if is_muted else "音效"

func go_menu() -> void:
	renderer.cancel_pointer()
	if embedded:
		exit_requested.emit()
		return
	_clear_action_requests()
	scoreboard.hide()
	match_view.hide()
	main_menu.show()
	resume_button.visible = sim != null
	audio.muted = true

func _resume_match() -> void:
	if sim == null: return
	main_menu.hide()
	match_view.show()
	audio.muted = audio_button.text == "静音"
	_input_lock = .2

func open_scoreboard() -> void:
	renderer.cancel_pointer()
	if sim == null: return
	_clear_action_requests()
	state = sim.snapshot(true)
	_refresh_scoreboard()
	scoreboard.show()

func _close_scoreboard() -> void:
	scoreboard.hide()
	_input_lock = .2

func _clear_action_requests() -> void:
	_reload_request = false
	_smoke_request = false
	_flash_request = false
	_weapon_request = ""

func _refresh_scoreboard() -> void:
	var score: Dictionary = state.get("score", {"t": 0, "ct": 0})
	var names: Dictionary = rosters.get("team_names", {"t":"Team Spirit", "ct":"Vitality"})
	for team in scoreboard_team_headings: scoreboard_team_headings[team].text = str(names.get(team, team.to_upper()))
	score_title.text = "%s   %d : %d   %s" % [str(names.get("t","Team T")).to_upper(), score["t"], score["ct"], str(names.get("ct","Team CT")).to_upper()]
	score_subtitle.text = "比赛结束 · %d 回合 · 你的控制角色以浅绿色标出" % int(state.get("rounds_completed", 0)) if state.get("finished", false) else "第 %d 回合 · 本面板暂停对局 · Rating 按已经完成的回合计算" % int(state.get("round", 1))
	var indices := {"t": 0, "ct": 0}
	for p in state.get("players", []):
		var key := str(p["team"]) + str(indices[p["team"]])
		indices[p["team"]] += 1
		var cells: Array = scoreboard_rows[key]
		var values := [str(p["name"]) + " · " + ROLE_NAMES.get(p.get("role", "rifle"), "步枪手"), str(p["k"]), str(p["d"]), str(p["a"]), str(p["damage"]), "%.1f" % float(p.get("adr", 0)), "%d%%" % int(float(p.get("kast", 0)) * 100), "%.2f" % float(p["rating"]) if p.get("rating") != null else "—"]
		for i in range(8):
			cells[i].text = values[i]
			cells[i].modulate = Style.GREEN if p["id"] == (initial_player_id if not initial_player_id.is_empty() else state.get("human_id", "")) else Style.TEXT

func _save_report() -> void:
	if sim == null: return
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://rts/runtime/reports"))
	var filename := "res://rts/runtime/reports/match-%d.json" % Time.get_unix_time_from_system()
	var report: Dictionary = sim.report()
	var file := FileAccess.open(filename, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(_serializable(report), "\t"))
		score_subtitle.text = "战报已保存到独立样本的 runtime/reports 文件夹。"

func _serializable(value):
	if value is Vector2: return [value.x, value.y]
	if value is Dictionary:
		var result := {}
		for key in value: result[key] = _serializable(value[key])
		return result
	if value is Array:
		var result := []
		for item in value: result.append(_serializable(item))
		return result
	return value

func _parse_args() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg == "--capture-demo": _capture_mode = "match"
		elif arg == "--capture-menu": _capture_mode = "menu"
		elif arg == "--capture-play": _capture_mode = "play"
		elif arg == "--capture-stats": _capture_mode = "stats"
		elif arg.begins_with("--capture-path="): _capture_path = arg.trim_prefix("--capture-path=")
		elif arg.begins_with("--seed="): seed_value = int(arg.trim_prefix("--seed="))
		elif arg.begins_with("--map="): select_map(arg.trim_prefix("--map="))
		elif arg == "--overtime": initial_overtime = true

func _capture_run() -> void:
	if _capture_mode in ["match", "play", "stats"]:
		start_match("play" if _capture_mode == "play" else "spectate", "t", "spirit_donk" if _capture_mode == "play" else "")
		set_process(false)
		for i in range(180 if _capture_mode == "play" else 1200): sim.step(1.0 / 60.0)
		state = sim.snapshot(true)
		_consume_events()
		renderer.update_state(state, mode, viewer_team, "")
		if _capture_mode == "play":
			renderer.update_state(state, mode, viewer_team, "spirit_donk")
		_refresh()
		if _capture_mode == "stats": open_scoreboard()
	await get_tree().process_frame
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	if not _capture_path.is_empty():
		get_viewport().get_texture().get_image().save_png(_capture_path)
	get_tree().quit()
