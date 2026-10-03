extends RefCounted
## News is read-only saved publication data, separate from invitation mail.
const UI = preload("res://scripts/computer_ui.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")
const CATEGORY := {"all":"全部", "news":"赛场新闻", "awards":"赛事荣誉", "top20":"年度 Top20", "transfer":"转会动态"}
var host
var category := "all"
var month := ""
var page := 1
var data: Dictionary = {}
var article: Dictionary = {}
var pending_path := ""
var pending_intent := -1
var pending_id := ""
var requested_query := ""
var error := ""

func attach(value: CanvasLayer) -> void:
	host = value

func _label(parent: Node, text: String, size: int = 14, color: Color = UI.INK) -> Label:
	return host._label(parent, text, size, color)

func _button(parent: Node, text: String, callback: Callable) -> Button:
	return host._button(parent, text, callback, false)

func render() -> void:
	if not article.is_empty():
		_render_article()
		return
	_label(host.content, "赛事新闻", 25)
	_label(host.content, "看见赛场、荣誉与转会发生了什么。这里只呈现已经保存的消息。", 14, UI.MUTED)
	var tabs: Array = []
	for key in CATEGORY:
		tabs.append({"id":key, "label":CATEGORY[key]})
	host._tabs(host.content, tabs, category, _set_category)
	var summary = CareerBridge.context.get("news", {})
	var fallback: Dictionary = summary if summary is Dictionary else {"rows":summary if summary is Array else []}
	var shown: Dictionary = data if not data.is_empty() else fallback
	var months: Array = data.get("months", fallback.get("months", []))
	var tools := HBoxContainer.new()
	tools.add_theme_constant_override("separation", 12)
	host.content.add_child(tools)
	var month_choice := OptionButton.new()
	month_choice.name = "ComputerNewsMonth"
	UI.dark_options(month_choice)
	month_choice.add_item("所有月份")
	var keys: Array[String] = [""]
	for stamp in months:
		keys.append(str(stamp))
		month_choice.add_item(str(stamp))
	if month in keys:
		month_choice.select(keys.find(month))
	month_choice.item_selected.connect(func(index: int): _set_month(keys[index]))
	tools.add_child(month_choice)
	_button(tools, "刷新新闻", _refresh)
	_label(tools, "%s 篇" % shown.get("total", shown.get("rows", []).size()), 13, UI.MUTED)
	if not error.is_empty():
		_label(host.content, error, 14, Color("a25746"))
	if data.is_empty() and category != "all" or data.is_empty() and not month.is_empty():
		_label(host.content, "正在读取新闻……", 14, UI.MUTED)
	else:
		for record in shown.get("rows", []):
			var box := UI.card(host.content)
			_label(box, str(record.get("date", "")) + " · " + str(CATEGORY.get(record.get("category", "news"), "赛场新闻")), 12, UI.MUTED)
			var title := _button(box, Locale.field(record, "title", "赛场动态"), _open.bind(str(record.get("id", ""))))
			TeamVisuals.button_logo(title, str(record.get("team", "")), 26)
			title.name = "ComputerNewsArticle_" + str(record.get("id", "")).validate_node_name()
			var intro := Locale.field(record, "summary", Locale.field(record, "preview"))
			if not intro.is_empty():
				_label(box, intro, 14, UI.MUTED)
		if shown.get("rows", []).is_empty() and pending_path.is_empty():
			_label(host.content, "这个范围内还没有已发表的消息。", 14, UI.MUTED)
	var pagination := HBoxContainer.new()
	host.content.add_child(pagination)
	_button(pagination, "上一页", _change_page.bind(-1)).disabled = page <= 1
	_label(pagination, "%s / %s" % [page, shown.get("pages", 1)])
	_button(pagination, "下一页", _change_page.bind(1)).disabled = page >= int(shown.get("pages", 1))
	if requested_query != _query() and pending_path.is_empty():
		call_deferred("_fetch", "")

func _query() -> String:
	return "/api/3d/news?category=%s&month=%s&page=%s" % [category.uri_encode(), month.uri_encode(), page]

func _fetch(id: String = "") -> void:
	if not host.screen.visible or host.active_page != "news" or not pending_path.is_empty():
		return
	var path := "/api/3d/news?id=" + id.uri_encode() if not id.is_empty() else _query()
	if CareerBridge._send(path, {}, false):
		pending_path = path
		pending_id = id
		pending_intent = host.detail_intent_serial
		if id.is_empty():
			requested_query = path

func _refresh() -> void:
	if not pending_path.is_empty():
		return
	requested_query = ""
	error = ""
	_fetch()

func _set_category(value: String) -> void:
	category = value
	_reset_list()

func _set_month(value: String) -> void:
	month = value
	_reset_list()

func _reset_list() -> void:
	page = 1
	data = {}
	article = {}
	error = ""
	requested_query = ""
	host.detail_intent_serial += 1
	host.page_scroll["news"] = 0
	host._rebuild()

func _change_page(delta: int) -> void:
	page = maxi(1, page + delta)
	data = {}
	article = {}
	requested_query = ""
	host.detail_intent_serial += 1
	host.page_scroll["news"] = 0
	host._rebuild()

func _open(id: String) -> void:
	if id.is_empty() or CareerBridge.busy:
		return
	error = ""
	_fetch(id)

func back() -> bool:
	if article.is_empty():
		return false
	article = {}
	host._rebuild()
	return true

func finished(path: String, result: Dictionary) -> bool:
	if path != pending_path or pending_path.is_empty():
		return false
	var may_show: bool = host.screen.visible and host.active_page == "news" and pending_intent == host.detail_intent_serial
	var detail_requested := not pending_id.is_empty()
	pending_path = ""
	pending_id = ""
	pending_intent = -1
	if may_show:
		if result.get("ok", false):
			if detail_requested:
				article = result.get("detail", {})
				host.page_scroll["news"] = 0
			else:
				data = result.duplicate(true)
			error = ""
		else:
			error = str(result.get("reason", result.get("msg", "新闻暂时没有读取完成。")))
		host._rebuild()
	return true

func _render_article() -> void:
	_button(host.content, "‹ 返回新闻列表", _back_to_list)
	_label(host.content, Locale.field(article, "title", "赛场动态"), 25)
	_label(host.content, str(article.get("date", "")) + " · " + str(CATEGORY.get(article.get("category", "news"), "赛场新闻")), 13, UI.MUTED)
	var body := Locale.field(article, "text", Locale.field(article, "body")).strip_edges()
	if not body.is_empty():
		for paragraph in body.split("\n\n", false):
			_label(host.content, paragraph, 15)
	var sections = article.get("sections", [])
	if body.is_empty() and sections is Array:
		for section in sections:
			if not section is Dictionary:
				continue
			_label(host.content, Locale.field(section, "heading", Locale.field(section, "title")), 19)
			_label(host.content, Locale.field(section, "text"), 15)
			for item in section.get("items", []):
				_label(host.content, Locale.field(item, "text"), 15)
	var awards: Dictionary = article.get("awards", article) if article.get("awards", article) is Dictionary else article
	var mvp = awards.get("mvp")
	if mvp is Dictionary and not mvp.is_empty():
		_label(host.content, "MVP", 21, UI.GREEN)
		_award_row(mvp)
	for group in ["evp", "five"]:
		var records: Array = awards.get(group, [])
		if not records.is_empty():
			_label(host.content, "EVP" if group == "evp" else "五位置最佳阵容", 21)
			for record in records:
				_award_row(record)
	var top20: Array = article.get("rows", [])
	if article.get("category") == "top20" or article.get("kind") == "top20":
		for record in top20:
			var box := UI.card(host.content)
			var player_key := str(record.get("player_id", record.get("player", "")))
			TeamVisuals.button_logo(_button(box, "#%s · %s · %s" % [record.get("rank", "—"), record.get("player", ""), record.get("team", "")], host._load_detail.bind("player", player_key)), str(record.get("team", "")))
			_label(box, "Rating " + _number(record.get("rating")), 14, UI.MUTED)
			var feature = record.get("feature")
			if feature is Dictionary:
				_label(box, Locale.field(feature, "title"), 19)
				if not str(feature.get("subtitle", "")).is_empty():
					_label(box, str(feature["subtitle"]), 13, UI.MUTED)
				for section in feature.get("sections", []):
					_label(box, Locale.field(section, "heading"), 17)
					_label(box, Locale.field(section, "text"), 15)
	if not str(article.get("event_id", "")).is_empty():
		_button(host.content, "打开赛事资料", host._load_detail.bind("event", str(article["event_id"])))

func _award_row(record: Dictionary) -> void:
	var box := UI.card(host.content)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	box.add_child(row)
	TeamVisuals.badge(row, str(record.get("team", "")), 30)
	var player_key := str(record.get("player_id", record.get("player", "")))
	_button(row, str(record.get("player", record.get("name", ""))), host._load_detail.bind("player", player_key)).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_label(row, str(record.get("team", "")) + " · " + str(Phone.ROLES.get(record.get("role", ""), record.get("role", ""))) + " · Rating " + _number(record.get("rating")), 14)
	if not str(record.get("title", "")).is_empty():
		_label(box, str(record["title"]), 13, UI.MUTED)

static func _number(value) -> String:
	return "%.2f" % float(value) if typeof(value) in [TYPE_INT, TYPE_FLOAT] else "—"

func _back_to_list() -> void:
	article = {}
	host.page_scroll["news"] = 0
	host._rebuild()
