extends RefCounted
## Shared read-only map form presentation for computers, phones and reports.
const UI = preload("res://scripts/computer_ui.gd")
const LABELS := {"strong":"强图", "neutral":"常规", "weak":"弱图"}

static func mount(parent: Node, rows: Array) -> void:
	if rows.is_empty(): return
	var card := UI.card(parent)
	card.name = "TeamMapPerformance"
	UI.label(card, "队伍地图表现", 18)
	UI.label(card, "综合评价 = 熟练度 + 近期状态。获胜提升熟练度，输给明显强队仍有少量学习收益；输给同档或较弱队伍时小幅下降。", 12, UI.MUTED)
	UI.label(card, "日常自动训练已开启：所有队伍维持地图熟练度，不因闲置衰退。专项训练可恢复已达到的水平，比赛才能突破。", 12, UI.MUTED)
	for item in rows:
		var recent: Array = item.get("recent", [])
		var wins := 0
		for game in recent: wins += int(bool(game.get("won", false)))
		UI.label(card, "%s · %.1f · %s" % [str(item.get("map", "")).capitalize(), float(item.get("rating", 0)), LABELS.get(str(item.get("label", "neutral")), "常规")], 15)
		UI.label(card, "熟练度 %.1f · 近期状态 %+.1f · 近 %d 图 %d 胜" % [float(item.get("strength", 0)), float(item.get("form", 0)), recent.size(), wins], 12, UI.MUTED)
		UI.label(card, "专项训练可恢复至 %.1f" % float(item.get("practice_ceiling", item.get("strength", 0))), 12, UI.MUTED)
		var change = item.get("last_change")
		if change is Dictionary: change_line(card, change)

static func change_line(parent: Node, change: Dictionary) -> void:
	UI.label(parent, "%s · %s %+.2f → %.1f · %s" % [change.get("team", ""), str(change.get("map", "")).capitalize(), float(change.get("delta", 0)), float(change.get("after", 0)), change.get("reason", "")], 12, UI.GREEN if float(change.get("delta", 0)) >= 0 else UI.MUTED)
	# Old reports keep their original totals; never invent historical components.
	if change.has("strength_delta") and change.has("form_delta"):
		UI.label(parent, "熟练度 %+.2f · 近期状态 %+.2f" % [float(change.strength_delta), float(change.form_delta)], 12, UI.MUTED)

static func changes(parent: Node, maps: Array) -> void:
	for item in maps:
		for change in item.get("map_form_changes", []): change_line(parent, change)

static func comparison(parent: Node, performances: Dictionary, map_code: String) -> void:
	var card := UI.card(parent)
	card.name = "VetoMapComparison"
	var summaries: Array[String] = []
	for team in performances:
		for item in performances[team]:
			if str(item.get("map", "")) == map_code.trim_prefix("de_"):
				summaries.append("%s · %.1f · %s" % [team, float(item.get("rating", 0)), LABELS.get(str(item.get("label", "neutral")), "常规")])
	UI.label(card, "     /     ".join(summaries), 14)
