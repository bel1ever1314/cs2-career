extends RefCounted
## What the career page shows while advancing without a due player match: the
## way to the next fixture, the latest results elsewhere and a few headlines.
## Results accumulate per step (newest first) so advancing adds rows instead of
## repainting an empty page. Read-only; the service builds `context.world`.
const UI = preload("res://scripts/computer_ui.gd")
const Kit = preload("res://scripts/ui_kit.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")
const KEEP := 6
const TAGS := {"opponent":["下一个对手", "amber"], "event":["同赛事", "blue"], "upset":["爆冷", "red"]}

var rows: Array = []
var seen := {}
var fresh_day := ""
var last_date := ""

func reset() -> void:
	rows.clear(); seen.clear(); fresh_day = ""; last_date = ""

## Merge the service's latest result day into the running list.
func absorb(world: Dictionary) -> void:
	var today := str(world.get("date", ""))
	# Loading an earlier save or starting a new season starts a new list.
	if today < last_date or today.left(4) != last_date.left(4): reset()
	last_date = today
	var incoming = world.get("results", [])
	var added: Array = []
	for row in incoming if incoming is Array else []:
		var id := str(row.get("id", "")) if row is Dictionary else ""
		if id.is_empty() or seen.has(id): continue
		seen[id] = true
		added.append(row)
	if added.is_empty(): return
	fresh_day = str(world.get("results_date", ""))
	rows = (added + rows).slice(0, KEEP)

static func days_between(from: String, to: String) -> int:
	if from.length() < 10 or to.length() < 10: return -1
	var a := Time.get_unix_time_from_datetime_string(from.left(10) + "T00:00:00")
	var b := Time.get_unix_time_from_datetime_string(to.left(10) + "T00:00:00")
	return int(round((b - a) / 86400.0))

static func countdown_text(days: int) -> String:
	if days <= 0: return "今天"
	if days == 1: return "明天"
	return "还有 %d 天" % days

func render(parent: Node, center) -> void:
	var world = CareerBridge.context.get("world", {})
	world = world if world is Dictionary else {}
	absorb(world)
	progress(parent, center)
	results(parent, center)
	headlines(parent, center, world)

func progress(parent: Node, center) -> void:
	var game: Dictionary = center.current_game()
	var today := str(CareerBridge.context.get("date", ""))
	var panel := PanelContainer.new()
	panel.name = "WorldFeedNext"
	panel.add_theme_stylebox_override("panel", UI.style(UI.PAPER, 14, 12, UI.LINE))
	parent.add_child(panel)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 14)
	panel.add_child(row)
	if game.is_empty():
		var words := VBoxContainer.new()
		words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(words)
		UI.label(words, "暂无已安排的比赛", 17)
		UI.label(words, "接受赛事邀请后，下一场会出现在这里。", 13, UI.MUTED)
		var events: Button = UI.compact(center.host._button(row, "赛事日程 ›", center.host._navigate.bind("events"), false))
		events.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		return
	var opponent := str(game.get("opponent", ""))
	var badge := TeamVisuals.badge(row, opponent, 40)
	if badge: badge.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var words := VBoxContainer.new()
	words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	words.add_theme_constant_override("separation", 1)
	row.add_child(words)
	var title := UI.label(words, "下一场 · %s · 对 %s" % [Kit.short_date(str(game.get("date", ""))), opponent], 17)
	title.autowrap_mode = TextServer.AUTOWRAP_OFF
	title.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	var details: Array[String] = [str(game.get("event", ""))]
	if not str(game.get("stage", "")).is_empty(): details.append(center._stage_name(str(game.get("stage", ""))))
	details.append("BO%s" % game.get("best_of", 3))
	var sub := UI.label(words, " · ".join(details), 13, UI.MUTED)
	sub.autowrap_mode = TextServer.AUTOWRAP_OFF
	sub.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	var when := VBoxContainer.new()
	when.add_theme_constant_override("separation", 0)
	when.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	row.add_child(when)
	var days := days_between(today, str(game.get("date", "")))
	var left := UI.label(when, countdown_text(days) if days >= 0 else "", 20, UI.GREEN)
	left.name = "WorldFeedDays"
	left.autowrap_mode = TextServer.AUTOWRAP_OFF
	left.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	var now := UI.label(when, "今天 %s" % Kit.short_date(today) if not today.is_empty() else "", 12, UI.MUTED)
	now.autowrap_mode = TextServer.AUTOWRAP_OFF
	now.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	# Attending in person stays one click away; the full match page has the rest.
	var attend: Button = UI.compact(center.host._button(row, "睡到比赛日", center.prepare_real.bind(str(game.get("id", "")))))
	attend.name = "WorldFeedAttend"
	attend.tooltip_text = "亲自参赛：比赛当天早上去现场"
	var open: Button = UI.compact(center.host._button(row, "比赛详情 ›", center.host._navigate.bind("career_match"), false))
	open.name = "WorldFeedMatch"
	for button in [attend, open]: button.size_flags_vertical = Control.SIZE_SHRINK_CENTER

func results(parent: Node, center) -> void:
	Kit.section(parent, UI, "其他赛场", ("最新 · %s" % Kit.short_date(fresh_day)) if not fresh_day.is_empty() else "", 17)
	if rows.is_empty():
		UI.label(parent, "其他队伍最近还没有赛果，推进后会出现在这里。", 13, UI.MUTED)
		return
	var list := VBoxContainer.new()
	list.name = "WorldFeedResults"
	list.add_theme_constant_override("separation", 4)
	parent.add_child(list)
	var shown_day := ""
	for row in rows:
		var day := str(row.get("date", ""))
		if day != fresh_day and day != shown_day:
			UI.label(list, Kit.short_date(day), 12, UI.MUTED)
		shown_day = day
		var tag: Array = TAGS.get(str(row.get("tag", "")), ["", "gray"])
		var where: Array[String] = [str(row.get("event", ""))]
		if not str(row.get("stage", "")).is_empty(): where.append(center._stage_name(str(row.get("stage", ""))))
		var ranks := ""
		if int(row.get("rank_a", 0)) > 0 and int(row.get("rank_b", 0)) > 0: ranks = "#%d vs #%d" % [int(row.rank_a), int(row.rank_b)]
		result_row(list, row, str(tag[0]), str(tag[1]), " · ".join(where), ranks, day == fresh_day, center)

## One dense line per series: winner in ink, loser muted, newest day marked.
func result_row(list: Node, row: Dictionary, tag: String, tone: String, where: String, ranks: String, fresh: bool, center) -> Button:
	var button := Button.new()
	button.name = "WorldResult"
	button.focus_mode = Control.FOCUS_ALL
	button.custom_minimum_size.y = 40
	button.add_theme_stylebox_override("normal", UI.style(UI.PAPER, 8, 10, UI.LINE))
	button.add_theme_stylebox_override("hover", UI.style(Color("f1f5ec"), 8, 10, Color("b9c9b8")))
	button.add_theme_stylebox_override("pressed", UI.style(UI.MINT, 8, 10, UI.GREEN))
	button.add_theme_stylebox_override("focus", UI.style(Color.TRANSPARENT, 0, 10, UI.GREEN))
	list.add_child(button)
	var line := HBoxContainer.new()
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	line.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	line.offset_left = 8; line.offset_right = -12
	line.add_theme_constant_override("separation", 10)
	button.add_child(line)
	var bar := ColorRect.new()
	bar.color = UI.GREEN if fresh else Color.TRANSPARENT
	bar.custom_minimum_size = Vector2(3, 22)
	bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	line.add_child(bar)
	var winner := str(row.get("winner", ""))
	var series = row.get("series", [])
	var score := "%s : %s" % [series[0], series[1]] if series is Array and series.size() == 2 else ":"
	var cells := [[str(row.get("team_a", "")), 170, HORIZONTAL_ALIGNMENT_RIGHT, 15], [score, 54, HORIZONTAL_ALIGNMENT_CENTER, 16], [str(row.get("team_b", "")), 170, HORIZONTAL_ALIGNMENT_LEFT, 15]]
	for index in range(cells.size()):
		var cell: Array = cells[index]
		var muted: bool = index != 1 and str(cell[0]) != winner
		var label := UI.label_exact(line, str(cell[0]), int(cell[3]), UI.MUTED if muted else UI.INK)
		label.custom_minimum_size.x = int(cell[1])
		label.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
		label.horizontal_alignment = cell[2]
		label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		label.autowrap_mode = TextServer.AUTOWRAP_OFF
		label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		label.clip_text = true
		label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var place := UI.label_exact(line, where, 12, UI.MUTED)
	place.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	place.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	place.autowrap_mode = TextServer.AUTOWRAP_OFF
	place.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	place.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if not tag.is_empty(): Kit.chip(line, tag, tone)
	var rank := UI.label_exact(line, ranks, 12, UI.MUTED)
	rank.custom_minimum_size.x = 84
	rank.size_flags_horizontal = Control.SIZE_SHRINK_END
	rank.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	rank.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	rank.autowrap_mode = TextServer.AUTOWRAP_OFF
	rank.mouse_filter = Control.MOUSE_FILTER_IGNORE
	button.tooltip_text = "%s 获胜" % winner
	button.pressed.connect(center.host._load_detail.bind("match", str(row.get("id", ""))))
	return button

func headlines(parent: Node, center, world: Dictionary) -> void:
	var news = world.get("news", [])
	if not news is Array or news.is_empty(): return
	Kit.section(parent, UI, "世界动态", "", 17)
	var list := VBoxContainer.new()
	list.name = "WorldFeedNews"
	list.add_theme_constant_override("separation", 4)
	parent.add_child(list)
	for item in news:
		if not item is Dictionary: continue
		var button := Button.new()
		button.name = "WorldHeadline"
		button.focus_mode = Control.FOCUS_ALL
		list.add_child(button)
		if str(item.get("kind", "")) == "champion":
			var mvp := str(item.get("mvp", ""))
			Kit.rich_row(button, UI, "%s 夺冠 · %s" % [str(item.get("champion", "")), str(item.get("event", ""))], "", Kit.short_date(str(item.get("date", ""))),
				"MVP %s" % mvp if not mvp.is_empty() else "", "amber", "trophy", str(item.get("champion", "")))
		else:
			Kit.rich_row(button, UI, Locale.field(item, "title"), "", Kit.short_date(str(item.get("date", ""))), "", "gray", "news")
		button.pressed.connect(center.host._navigate.bind("news"))
