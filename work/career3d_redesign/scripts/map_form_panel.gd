extends RefCounted
## Shared read-only map form presentation for computers, phones and reports.
const UI = preload("res://scripts/computer_ui.gd")
const LABELS := {"strong":"强图", "neutral":"常规", "weak":"弱图"}

static func mount(parent: Node, rows: Array) -> void:
	if rows.is_empty(): return
	var card := UI.card(parent)
	card.name = "TeamMapPerformance"
	UI.label(card, "队伍地图表现", 18)
	UI.label(card, "14 天未打或练图后逐渐生疏；比赛和专项练图可保持熟悉度。", 12, UI.MUTED)
	for item in rows:
		var recent: Array = item.get("recent", [])
		var wins := 0
		for game in recent: wins += int(bool(game.get("won", false)))
		UI.label(card, "%s · %.1f · %s" % [str(item.get("map", "")).capitalize(), float(item.get("rating", 0)), LABELS.get(str(item.get("label", "neutral")), "常规")], 15)
		UI.label(card, "长期 %.1f · 状态 %+.1f · 近 %d 图 %d 胜" % [float(item.get("strength", 0)), float(item.get("form", 0)), recent.size(), wins], 12, UI.MUTED)
		if int(item.get("inactive_days", 0)) > 14:
			UI.label(card, "已 %d 天未打或练图" % int(item["inactive_days"]), 12, UI.MUTED)
		var change = item.get("last_change")
		if change is Dictionary: change_line(card, change)

static func change_line(parent: Node, change: Dictionary) -> void:
	UI.label(parent, "%s · %s %+.2f → %.1f · %s" % [change.get("team", ""), str(change.get("map", "")).capitalize(), float(change.get("delta", 0)), float(change.get("after", 0)), change.get("reason", "")], 12, UI.GREEN if float(change.get("delta", 0)) >= 0 else UI.MUTED)

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
