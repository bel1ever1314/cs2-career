extends VBoxContainer
## Saved results only. Map tabs never rerun a match or invent absent stats.
const UI = preload("res://scripts/computer_ui.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")
const Scoreboard = preload("res://scripts/career_match_scoreboard.gd")
var game: Dictionary = {}
var event: Dictionary = {}
var own_id := ""
var selected: Callable
var narrow := false
var map_index := -1
var body: VBoxContainer
var tables: GridContainer
var scoreboards: Array[Control] = []

static func mount(parent: Node, match_data: Dictionary, event_data: Dictionary, player_id: String, callback: Callable, phone: bool = false) -> VBoxContainer:
	var report = load("res://scripts/career_match_report.gd").new()
	report.name = "ProfessionalMatchReport"
	report.game = match_data.duplicate(true)
	report.event = event_data.duplicate(true)
	report.own_id = player_id
	report.selected = callback
	report.narrow = phone
	report.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	report.add_theme_constant_override("separation", 12)
	parent.add_child(report)
	report.build()
	return report

static func score_text(value: Variant) -> String:
	if value is Array and value.size() >= 2: return "%s : %s" % [value[0], value[1]]
	return str(value) if value != null and not str(value).is_empty() else "—"

func build() -> void:
	TeamVisuals.match_heading(self, str(game.get("team_a", "")), str(game.get("team_b", "")), score_text(game.get("series", "")), narrow)
	UI.label(self, "%s · %s" % [event.get("name", game.get("event", "")), game.get("date", "")], 12 if narrow else 14, UI.MUTED)
	var maps: Array = game.get("maps", [])
	if maps.is_empty():
		UI.label(self, "比赛尚未结束。", 14, UI.MUTED)
		return
	var tabs := HFlowContainer.new()
	tabs.name = "MatchReportMapTabs"
	tabs.add_theme_constant_override("h_separation", 7)
	add_child(tabs)
	var series := UI.button(tabs, "全场", select_map.bind(-1))
	series.name = "MatchReportSeriesTab"
	series.custom_minimum_size.y = 32
	series.disabled = game.get("totals", []).is_empty()
	if series.disabled: series.tooltip_text = "这场比赛没有保存全场汇总。"
	for index in range(maps.size()):
		var map_row: Dictionary = maps[index]
		var button := UI.button(tabs, "%s · %s" % [str(map_row.get("map", "")).trim_prefix("de_").capitalize(), score_text(map_row.get("score", ""))], select_map.bind(index))
		button.name = "MatchReportMapTab_" + str(index)
		button.custom_minimum_size.y = 32
	body = VBoxContainer.new()
	body.add_theme_constant_override("separation", 12)
	add_child(body)
	if game.get("totals", []).is_empty(): map_index = 0
	paint()

func select_map(index: int) -> void:
	map_index = index
	paint()

func rows_for_map(map_row: Dictionary) -> Array:
	var result: Array = []
	var players: Dictionary = map_row.get("players", {})
	for team in players:
		for player in players[team]:
			var row: Dictionary = player.duplicate(true)
			row["team"] = team
			var id = row.get("resolved_player_id", row.get("player_id", ""))
			row["player_id"] = str(id) if id != null else ""
			result.append(row)
	return result

func paint() -> void:
	UI.clear(body)
	scoreboards.clear()
	var maps: Array = game.get("maps", [])
	var rows: Array = game.get("totals", []).duplicate(true)
	if map_index < 0 and rows.is_empty(): map_index = 0
	var map_row: Dictionary = maps[clampi(map_index, 0, maps.size() - 1)]
	TeamVisuals.map_banner(body, str(map_row.get("map", "")), "全场战绩" if map_index < 0 else "本图 · " + score_text(map_row.get("score", "")), 100 if narrow else 145)
	preload("res://scripts/map_form_panel.gd").changes(body, maps if map_index < 0 else [map_row])
	if map_index >= 0 or rows.is_empty(): rows = rows_for_map(map_row)
	if rows.is_empty():
		UI.label(body, "这场比赛未保存完整选手数据。", 13, UI.MUTED)
		return
	tables = GridContainer.new()
	tables.name = "MatchReportTeamTables"
	tables.columns = 1
	tables.add_theme_constant_override("h_separation", 14)
	tables.add_theme_constant_override("v_separation", 14)
	tables.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.add_child(tables)
	for team in [str(game.get("team_a", "")), str(game.get("team_b", ""))]:
		var team_rows: Array = []
		for row in rows:
			if str(row.get("team", "")) == team: team_rows.append(row)
		if team_rows.is_empty(): continue
		# Keep table minimum widths local. Otherwise two roomy scoreboards
		# expand the whole report (including its header and map) off the monitor.
		var scrolling := ScrollContainer.new()
		scrolling.name = "MatchReportStatsScroll_" + team.validate_node_name()
		scrolling.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
		scrolling.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
		scrolling.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		tables.add_child(scrolling)
		scoreboards.append(Scoreboard.mount(scrolling, team_rows, [team], own_id, selected, "选手", true))
		if team_rows.size() != 5: UI.label(body, "%s · 已保存 %s 人" % [team, team_rows.size()], 12, UI.MUTED)
	if narrow: UI.label(body, "左右滑动查看完整战绩。", 12, UI.MUTED)
	if not resized.is_connected(fit_tables): resized.connect(fit_tables)
	fit_tables()

func fit_tables() -> void:
	if not is_instance_valid(tables): return
	var required := float(tables.get_theme_constant("h_separation"))
	for board in scoreboards: required += board.get_combined_minimum_size().x
	tables.columns = 2 if not narrow and scoreboards.size() == 2 and size.x >= maxf(1000.0, required) else 1
