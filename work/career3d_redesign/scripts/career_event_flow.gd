extends RefCounted
## Connect only saved source/target links. Unresolved Swiss pairings stay blank.
const UI = preload("res://scripts/computer_ui.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")

static func dates_text(dates: Array) -> String:
	if dates.is_empty(): return ""
	return str(dates[0]) if dates.size() == 1 else str(dates[0]) + " — " + str(dates[-1])

static func field_text(field: String, value: Variant) -> String:
	if field == "format":
		return str({"single_elim":"单败淘汰", "double_elim":"双败淘汰", "swiss":"瑞士轮", "groups":"分组赛", "major":"Major 多阶段"}.get(str(value), value))
	if field == "status":
		return str({"live":"进行中", "scheduled":"待开赛", "finished":"已结束", "complete":"已结束", "pending":"待开赛"}.get(str(value), value))
	return str(value)

static func mount(parent: Node, event: Dictionary, callback: Callable, narrow: bool = false) -> void:
	var matches: Array = event.get("matches", [])
	UI.label(parent, "赛事进程", 17 if narrow else 22)
	if matches.is_empty():
		UI.label(parent, "赛程尚未发布。", 13, UI.MUTED)
		return
	var scroll := ScrollContainer.new()
	scroll.name = "EventFlowScroll"
	scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	parent.add_child(scroll)
	var graph := FlowGraph.new()
	graph.name = "EventFlowGraph"
	graph.mouse_filter = Control.MOUSE_FILTER_PASS
	graph.matches = matches.duplicate(true)
	graph.links = event.get("links", []).duplicate(true)
	graph.callback = callback
	scroll.add_child(graph)
	graph.build()
	UI.label(parent, "绿色：胜者路线 · 红色：败者路线", 12, UI.MUTED)
	var major: Array = event.get("major_tables", [])
	if not major.is_empty():
		for stage in major:
			standings(parent, "第 %s 阶段 · 瑞士轮" % stage.get("stage", ""), stage.get("rows", []), narrow)
	elif not event.get("swiss_table", []).is_empty():
		standings(parent, "瑞士轮积分", event.get("swiss_table", []), narrow)
	var groups: Dictionary = event.get("groups_table", {})
	for group in groups: standings(parent, "%s 组" % group, groups[group], narrow)

static func standings(parent: Node, title: String, rows: Array, narrow: bool) -> void:
	var card := UI.card(parent)
	UI.label(card, title, 15 if narrow else 18)
	for item in rows:
		var row := HBoxContainer.new()
		card.add_child(row)
		var team := str(item.get("name", item.get("team", "")))
		TeamVisuals.badge(row, team, 22)
		UI.label(row, team, 13).size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var record := "%s 胜 · %s 负" % [item.get("w", 0), item.get("l", 0)]
		if item.get("place", "—") != "—": record += " · " + str({"1st":"第一晋级","2nd":"第二晋级","out":"淘汰"}.get(item.get("place"), item.get("place")))
		UI.label(row, record, 12, UI.MUTED)

class FlowGraph extends Control:
	const CARD_WIDTH := 244
	const CARD_HEIGHT := 110
	const COLUMN_GAP := 60
	const ROW_GAP := 18
	var matches: Array = []
	var links: Array = []
	var callback: Callable
	var boxes: Dictionary = {}
	var stages: Array[String] = []
	var grouped: Dictionary = {}

	func build() -> void:
		for game in matches:
			var stage := str(game.get("stage", game.get("phase", "赛程")))
			if stage.is_empty(): stage = "赛程"
			if stage not in stages:
				stages.append(stage)
				grouped[stage] = []
			grouped[stage].append(game)
		var maximum := 1
		for stage in stages: maximum = maxi(maximum, grouped[stage].size())
		custom_minimum_size = Vector2(stages.size() * (CARD_WIDTH + COLUMN_GAP) - COLUMN_GAP, maximum * (CARD_HEIGHT + ROW_GAP) + 36)
		for column in range(stages.size()):
			var occupied_y: Array[float] = []
			var heading := UI.label(self, str({"R16":"十六强", "QF":"四分之一决赛", "SF":"半决赛", "GF":"决赛"}.get(stages[column], stages[column])), 15, UI.GREEN)
			heading.position = Vector2(column * (CARD_WIDTH + COLUMN_GAP), 0)
			heading.size = Vector2(CARD_WIDTH, 28)
			for index in range(grouped[stages[column]].size()):
				var game: Dictionary = grouped[stages[column]][index]
				var panel := PanelContainer.new()
				panel.name = "EventFlowMatch_" + str(game.get("id", "")).validate_node_name()
				panel.position = Vector2(column * (CARD_WIDTH + COLUMN_GAP), 34 + index * (CARD_HEIGHT + ROW_GAP))
				var parents: Array[float] = []
				for link in links:
					if str(link.get("target", "")) == str(game.get("id", "")) and boxes.has(str(link.get("source", ""))):
						parents.append(boxes[str(link.get("source"))].position.y)
				if parents.size() > 1:
					var total := 0.0
					for y in parents: total += y
					panel.position.y = total / parents.size()
				# GSL winner and elimination matches can share the same sources.
				# Preserve both cards and their actual links instead of overlapping.
				for y in occupied_y:
					if absf(panel.position.y - y) < CARD_HEIGHT + ROW_GAP:
						panel.position.y = y + CARD_HEIGHT + ROW_GAP
				occupied_y.append(panel.position.y)
				custom_minimum_size.y = maxf(custom_minimum_size.y, panel.position.y + CARD_HEIGHT + 12)
				panel.size = Vector2(CARD_WIDTH, CARD_HEIGHT)
				panel.add_theme_stylebox_override("panel", UI.style(UI.PAPER, 8, 9, UI.LINE))
				add_child(panel)
				boxes[str(game.get("id", ""))] = Rect2(panel.position, Vector2(CARD_WIDTH, CARD_HEIGHT))
				var content := VBoxContainer.new()
				content.add_theme_constant_override("separation", 3)
				panel.add_child(content)
				for slot in ["team_a", "team_b"]:
					var row := HBoxContainer.new()
					content.add_child(row)
					var team := str(game.get(slot, "待定"))
					TeamVisuals.badge(row, team, 20)
					var name := UI.label(row, team, 13, UI.GREEN if game.get("winner") == team else UI.INK)
					name.size_flags_horizontal = Control.SIZE_EXPAND_FILL
					name.autowrap_mode = TextServer.AUTOWRAP_OFF
					name.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
				var series = game.get("series", [])
				var score := "%s : %s" % [series[0], series[1]] if series is Array and series.size() >= 2 else str(series)
				var button := UI.button(content, (score if game.get("played", false) else "待开赛") + " · " + str(game.get("date", "")), open_match.bind(str(game.get("id", ""))))
				button.name = "EventFlowOpen_" + str(game.get("id", "")).validate_node_name()
				button.custom_minimum_size.y = 27
				button.add_theme_font_size_override("font_size", 11)
		queue_redraw()

	func open_match(id: String) -> void:
		if callback.is_valid() and not id.is_empty(): callback.call(id)

	func _draw() -> void:
		for link in links:
			var source := str(link.get("source", ""))
			var target := str(link.get("target", ""))
			if not boxes.has(source) or not boxes.has(target): continue
			var start: Vector2 = boxes[source].position + Vector2(CARD_WIDTH, CARD_HEIGHT / 2.0)
			var finish: Vector2 = boxes[target].position + Vector2(0, CARD_HEIGHT / 2.0)
			if start.x >= finish.x: continue
			var midpoint := (start.x + finish.x) / 2.0
			var points := PackedVector2Array([start, Vector2(midpoint, start.y), Vector2(midpoint, finish.y), finish])
			var color := Color("93b39e") if link.get("outcome", "") == "winner" else Color("cb9f98")
			draw_polyline(points, color, 2.0, true)
			draw_circle(finish, 3, color)
