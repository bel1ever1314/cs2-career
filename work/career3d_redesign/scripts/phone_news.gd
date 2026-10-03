extends RefCounted
## Published career articles only. The phone never creates awards or live rankings.
const UI = preload("res://scripts/phone_ui.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")
const CATEGORY := {"all":"全部", "news":"赛场", "awards":"荣誉", "top20":"Top20", "transfer":"转会"}

static func render(phone: Node) -> void:
	var parent: VBoxContainer = phone.content
	var article: Dictionary = phone.news_article
	if not article.is_empty():
		phone._button(parent, "‹ 新闻列表", phone._news_list, false)
		UI.label(parent, Locale.field(article, "title", "赛事新闻"), 19)
		UI.label(parent, "%s · %s" % [article.get("date", ""), CATEGORY.get(article.get("category", "news"), "赛场")], 12, UI.MUTED)
		UI.label(parent, Locale.field(article, "text"), 14)
		var mvp = article.get("mvp")
		if mvp != null:
			if mvp is Dictionary: TeamVisuals.badge(parent, str(mvp.get("team", "")), 34)
			UI.label(parent, "MVP · " + _name(mvp), 16)
		for item in [["evp", "EVP"], ["five", "最佳阵容"]]:
			var players = article.get(item[0], [])
			if players is Array and not players.is_empty():
				UI.label(parent, item[1], 16)
				for player in players:
					if player is Dictionary: TeamVisuals.badge(parent, str(player.get("team", "")), 26)
					UI.label(parent, _name(player), 14)
		for feature in article.get("rows", []):
			if not feature is Dictionary:
				continue
			TeamVisuals.badge(parent, str(feature.get("team", "")), 28)
			UI.label(parent, "#%s · %s" % [feature.get("rank", ""), feature.get("player", feature.get("name", ""))], 16)
			var report = feature.get("feature", {})
			if report is Dictionary:
				UI.label(parent, Locale.field(report, "title"), 15)
				UI.label(parent, Locale.field(report, "text", Locale.field(report, "body")), 14)
				for section in report.get("sections", []):
					UI.label(parent, Locale.field(section, "heading"), 15)
					UI.label(parent, Locale.field(section, "text"), 14)
			elif report is String:
				UI.label(parent, report, 14)
		return
	var filters := GridContainer.new()
	filters.columns = 3
	UI.inset(parent, filters)
	for category in CATEGORY:
		var button: Button = phone._button(filters, CATEGORY[category], phone._load_news.bind(category, 1, ""), false)
		button.set_meta("news_category", category)
		if phone.news_category == category:
			phone._primary(button)
	var projection = CareerBridge.context.get("news", {})
	var data: Dictionary = phone.news_data
	if data.is_empty():
		data = projection if projection is Dictionary else {"rows":projection, "page":1, "pages":1, "total":projection.size() if projection is Array else 0}
	var rows: Array = data.get("rows", [])
	UI.label(parent, "已发布 · %d 篇" % int(data.get("total", rows.size())), 12, UI.MUTED)
	if rows.is_empty():
		UI.label(parent, "还没有这个分类的新闻。赛事荣誉、转会报道和年度 Top20 发布后会出现在这里。", 14)
	for row in rows:
		phone._list_row(parent, Locale.field(row, "title", "赛事新闻"), "%s · %s" % [row.get("date", ""), CATEGORY.get(row.get("category", "news"), "赛场")], phone._load_news.bind(phone.news_category, phone.news_page, str(row.get("id", ""))), "", "mail", false, true, str(row.get("team", "")))
	if phone.news_data.is_empty() and int(data.get("total", 0)) > rows.size():
		phone._button(parent, "阅读全部新闻", phone._load_news.bind(phone.news_category, 1, ""), false)
		return
	var pages := int(data.get("pages", 1))
	if pages > 1:
		var paging := HBoxContainer.new()
		UI.inset(parent, paging)
		var previous: Button = phone._button(paging, "上一页", phone._load_news.bind(phone.news_category, phone.news_page - 1, ""), false)
		previous.disabled = phone.news_page <= 1
		var next: Button = phone._button(paging, "下一页", phone._load_news.bind(phone.news_category, phone.news_page + 1, ""), false)
		next.disabled = phone.news_page >= pages
		UI.label(parent, "%d / %d" % [phone.news_page, pages], 12, UI.MUTED)

static func _name(value: Variant) -> String:
	if value is Dictionary:
		return str(value.get("name", value.get("player", "")))
	return str(value)
