extends RefCounted
## Paginated native market. Only the backend owns money, rolls and stock.
## Layout: compact tiles for browsing, a two-column detail with a purchase
## panel, row lists for custody, and confirmations shown where they were asked.
const UI = preload("res://scripts/computer_ui.gd")
const Fmt = preload("res://scripts/ui_format.gd")
const Kit = preload("res://scripts/ui_kit.gd")
const Visuals = preload("res://scripts/computer_visuals.gd")
const TILE := Vector2(244, 214)
const UP := Color("2f6b52")
const DOWN := Color("ad5b52")
const DEFAULTS := {"search":"", "slot":"", "rarity":"", "wear":"ft", "sort":"price", "order":"asc", "min_price":"", "max_price":""}
var host
var linked := false
var filters := {"search":"", "slot":"", "rarity":"", "wear":"ft", "sort":"price", "order":"asc", "page":1, "min_price":"", "max_price":""}
var cache: Dictionary = {}
var request_path := ""
var loaded_path := ""
var selected: Dictionary = {}
var confirmation: Dictionary = {}
var confirm_shown := false
var quantity := 1
var lot_quantity: Dictionary = {}
var loaded_revision := -1
var supply_player := ""
var supply_target := ""
var payer := "personal"
var advanced_filters := false
var source_rumor: Dictionary = {}
var detail_origin := ""
var origin_scroll := 0

static func tr2(zh: String, en: String) -> String:
	return en if Locale.language == "en" else zh

func label(parent: Node, text: String, size: int = 14, color: Color = UI.INK) -> Label:
	return host._label(parent, text, size, color)

## One-line label. Trimmed labels report no minimum width, so labels that
## must keep their text in a row (counts, fees, prices) pass trim = false.
func line(parent: Node, text: String, size: int = 14, color: Color = UI.INK, trim: bool = true) -> Label:
	var node := label(parent, text, size, color)
	node.autowrap_mode = TextServer.AUTOWRAP_OFF
	if trim: node.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return node

func button(parent: Node, text: String, callback: Callable, write: bool = false) -> Button:
	return host._button(parent, text, callback, write)

func small(parent: Node, text: String, callback: Callable, write: bool = false) -> Button:
	var node := UI.compact(button(parent, text, callback, write))
	node.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	return node

func hbox(parent: Node, gap: int = 10) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", gap)
	parent.add_child(row)
	return row

func flow(parent: Node, gap: int = 12) -> HFlowContainer:
	var box := HFlowContainer.new()
	box.add_theme_constant_override("h_separation", gap)
	box.add_theme_constant_override("v_separation", gap)
	parent.add_child(box)
	return box

func spacer(parent: Node) -> void:
	var gap := Control.new()
	gap.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	gap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(gap)

func panel(parent: Node, border: Color = UI.LINE, fill: Color = UI.PAPER, padding: int = 14) -> VBoxContainer:
	var box := PanelContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_theme_stylebox_override("panel", UI.style(fill, padding, 12, border))
	parent.add_child(box)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 8)
	box.add_child(column)
	return column

## Usable page width; the very first build happens before layout, when the
## monitor is assumed to be the usual wide one.
func page_width() -> float:
	if is_instance_valid(host.content) and host.content.size.x > 0: return host.content.size.x
	if is_instance_valid(host.scroll) and host.scroll.size.x > 0: return host.scroll.size.x - 24.0
	return 1052.0

func wide() -> bool:
	return page_width() >= 900.0

## Tiles stretch so a row fills the page edge to edge.
func tile_width() -> float:
	var width := page_width()
	var columns := maxi(1, floori((width + 12.0) / (TILE.x + 12.0)))
	return floorf((width - 12.0 * (columns - 1)) / columns)

func render(owner) -> void:
	host = owner
	if not linked:
		CareerBridge.command_finished.connect(finished)
		linked = true
	confirm_shown = false
	var query := filters.duplicate()
	query["view"] = host.market_tab
	if not selected.is_empty():
		query.merge({"view":"detail", "id":selected.id, "wear":selected.wear_id}, true)
	var path := "/api/3d/supplies" if host.market_tab == "supplies" else "/api/3d/market?"
	if host.market_tab != "supplies":
		for key in query: path += str(key) + "=" + str(query[key]).uri_encode() + "&"
	var revision := int(CareerBridge.context.get("calendar", {}).get("revision", 0))
	if loaded_path != path or loaded_revision != revision:
		if request_path != path:
			request_path = path
			CareerBridge._send(path, {}, false)
		label(host.content, tr2("正在读取市场…", "Loading market…"), 14, UI.MUTED)
		return
	if cache.has("error"):
		label(host.content, str(cache.error))
		small(host.content, tr2("重试", "Retry"), refresh)
		return
	if not selected.is_empty():
		detail()
	elif host.market_tab == "merchant":
		merchant()
	elif host.market_tab == "supplies":
		supplies()
	else:
		listing()
	# A request asked from somewhere that is not on screen any more.
	if not confirmation.is_empty() and not confirm_shown:
		var holder := VBoxContainer.new()
		host.content.add_child(holder)
		host.content.move_child(holder, 0)
		confirm_bar(holder)

func finished(path: String, result: Dictionary) -> void:
	if path == request_path:
		request_path = ""
		loaded_path = path
		loaded_revision = int(result.get("state_revision", CareerBridge.context.get("calendar", {}).get("revision", 0)))
		cache = result.get("supplies", {}) if path == "/api/3d/supplies" else result.get("market", {})
		if not result.get("ok", false): cache = {"error":result.get("msg", "")}
		if is_instance_valid(host) and host.active_page == "market": host._rebuild()
	elif path.begins_with("/api/3d/skins/market-") or path.begins_with("/api/3d/skins/supply-"):
		loaded_path = ""
		confirmation.clear()
		if result.get("ok", false): lot_quantity.clear()
		if is_instance_valid(host) and host.active_page == "market": host._rebuild()

func refresh() -> void:
	loaded_path = ""
	host._rebuild()

func reset_selection() -> void:
	source_rumor.clear()
	detail_origin = ""
	selected.clear()
	confirmation.clear()
	quantity = 1
	lot_quantity.clear()
	filters.page = 1

func option(parent: Node, names: Array, values: Array, current: String, callback: Callable) -> OptionButton:
	var control := OptionButton.new()
	UI.dark_options(control)
	control.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	control.fit_to_longest_item = false
	for name in names: control.add_item(str(name))
	var index := values.find(current)
	control.select(maxi(0,index))
	control.item_selected.connect(func(i: int): callback.call(str(values[i])))
	parent.add_child(control)
	return control

func set_filter(key: String, value) -> void:
	filters[key] = value
	filters.page = 1
	selected.clear()
	confirmation.clear()
	host.page_scroll["market"] = 0
	host._rebuild()

func set_sort(value: String) -> void:
	var parts := value.split("|")
	filters.sort = parts[0]
	filters.order = parts[1] if parts.size() > 1 else "asc"
	set_filter("page", 1)

func clear_filters() -> void:
	for key in DEFAULTS: filters[key] = DEFAULTS[key]
	set_filter("page", 1)

func active_filters() -> int:
	var count := 0
	for key in ["slot", "rarity", "wear", "min_price", "max_price"]:
		if str(filters[key]) != str(DEFAULTS[key]): count += 1
	return count

# --- shared pieces -------------------------------------------------------

func rarity_color(row: Dictionary) -> Color:
	return host._rarity_color(str(row.get("rarity", "")))

func wear_text(row: Dictionary) -> String:
	var code := str(row.get("wear_id", "")).to_upper()
	var name := str(row.get("wear_name", ""))
	if name.is_empty() and Locale.language != "en":
		for wear in cache.get("wears", []):
			if wear is Dictionary and str(wear.get("id", "")).to_upper() == code: name = str(wear.get("name", ""))
	if Locale.language == "en" or name.is_empty(): return code if not code.is_empty() else str(row.get("wear", ""))
	return name

## Day-span change as a coloured pill; "—" until the market has history.
func change_chip(parent: Node, caption: String, value) -> void:
	if value == null:
		Kit.chip(parent, caption + " —", "gray", 12)
		return
	var amount := float(value)
	Kit.chip(parent, "%s %+.1f%%" % [caption, amount], "green" if amount > 0.05 else ("red" if amount < -0.05 else "gray"), 12)

func changes(parent: Node, row: Dictionary) -> HBoxContainer:
	var chips := hbox(parent, 6)
	change_chip(chips, tr2("1天", "1d"), row.get("change_1"))
	change_chip(chips, tr2("7天", "7d"), row.get("change_7"))
	change_chip(chips, tr2("30天", "30d"), row.get("change_30"))
	return chips

func pct(value) -> String:
	return "—" if value == null else "%+.1f%%" % float(value)

func move_color(value) -> Color:
	if value == null: return UI.MUTED
	return UP if float(value) > 0.05 else (DOWN if float(value) < -0.05 else UI.MUTED)

func pl_color(value) -> Color:
	return UP if float(value) >= 0 else DOWN

## Skin picture without the "image unavailable" caption so tiles keep a fixed height.
func art(parent: Node, row: Dictionary, height: int) -> PanelContainer:
	var surface := PanelContainer.new()
	surface.name = "SkinArt"
	surface.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	surface.custom_minimum_size.y = height
	surface.mouse_filter = Control.MOUSE_FILTER_IGNORE
	surface.add_theme_stylebox_override("panel", UI.style(Color("efeee5"), 6, 10))
	parent.add_child(surface)
	var path := str(row.get("art_path", ""))
	if not path.is_empty() and FileAccess.file_exists(path):
		if not host.skin_textures.has(path):
			var image := Image.new()
			if image.load(path) == OK: host.skin_textures[path] = ImageTexture.create_from_image(image)
		if host.skin_textures.has(path):
			var picture := TextureRect.new()
			picture.texture = host.skin_textures[path]
			picture.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			picture.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			picture.mouse_filter = Control.MOUSE_FILTER_IGNORE
			surface.add_child(picture)
			return surface
	var placeholder := Visuals.SkinPlaceholder.new()
	placeholder.weapon = str(row.get("weapon", ""))
	placeholder.paint = rarity_color(row)
	surface.add_child(placeholder)
	return surface

static func tile_styles(node: Button, accent: Color = Color.TRANSPARENT) -> void:
	var normal := UI.style(UI.PAPER, 10, 12, UI.LINE)
	var hover := UI.style(Color("f1f5ec"), 10, 12, Color("9eb19c"))
	var pressed := UI.style(UI.MINT, 10, 12, UI.GREEN)
	if accent.a > 0: normal.border_color = accent
	node.add_theme_stylebox_override("normal", normal)
	node.add_theme_stylebox_override("hover", hover)
	node.add_theme_stylebox_override("pressed", pressed)
	node.add_theme_stylebox_override("hover_pressed", pressed)
	node.add_theme_stylebox_override("focus", UI.style(Color.TRANSPARENT, 0, 12, UI.GREEN))
	node.add_theme_stylebox_override("disabled", normal)

## One clickable skin tile: picture, rarity stripe, name, wear, price and today's move.
func tile(parent: Node, row: Dictionary, callback: Callable, footer: String = "", footer_color: Color = UI.MUTED) -> Button:
	var card := Button.new()
	card.name = "MarketTile"
	card.custom_minimum_size = Vector2(tile_width(), TILE.y)
	card.focus_mode = Control.FOCUS_ALL
	card.tooltip_text = str(row.get("name", ""))
	tile_styles(card)
	card.pressed.connect(callback)
	parent.add_child(card)
	var body := VBoxContainer.new()
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	body.offset_left = 10; body.offset_right = -10; body.offset_top = 10; body.offset_bottom = -10
	body.add_theme_constant_override("separation", 3)
	card.add_child(body)
	art(body, row, 92)
	var stripe := ColorRect.new()
	stripe.color = rarity_color(row)
	stripe.custom_minimum_size.y = 3
	stripe.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(stripe)
	line(body, str(row.get("name", "")), 14)
	var rarity := str(host._rarity_label(str(row.get("rarity", ""))))
	line(body, rarity + " · " + wear_text(row), 11, rarity_color(row))
	var price := hbox(body, 6)
	price.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var amount := line(price, Fmt.money(row.get("spot", row.get("buy", 0))), 17)
	amount.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	if row.has("change_1"):
		var today := line(price, tr2("今日 ", "Today ") + pct(row.get("change_1")), 12, move_color(row.get("change_1")), false)
		today.size_flags_horizontal = Control.SIZE_SHRINK_END
		today.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		if footer.is_empty():
			line(body, tr2("7天 %s · 30天 %s", "7d %s · 30d %s") % [pct(row.get("change_7")), pct(row.get("change_30"))], 11, UI.MUTED)
	if not footer.is_empty(): line(body, footer, 11, footer_color)
	quiet(body)
	return card

## Children of a clickable card must not swallow its clicks.
static func quiet(root: Node) -> void:
	if root is Control: root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	for child in root.find_children("*", "Control", true, false): child.mouse_filter = Control.MOUSE_FILTER_IGNORE

func confirm_bar(parent: Node) -> void:
	confirm_shown = true
	var box := panel(parent, UI.AMBER, Color("fbf4e4"), 12)
	box.get_parent().name = "MarketConfirmation"
	var caption := label(box, str(confirmation.caption), 15)
	caption.name = "MarketConfirmationCaption"
	var actions := hbox(box, 8)
	spacer(actions)
	small(actions, tr2("取消", "Cancel"), func(): confirmation.clear(); host._rebuild())
	var ok := small(actions, tr2("确认", "Confirm"), confirm, true)
	ok.name = "ConfirmMarketAction"
	UI.primary(ok)
	ok.call_deferred("grab_focus")

## Shows the pending confirmation here when it belongs to this spot.
func inline_confirm(parent: Node, anchor: String) -> bool:
	if confirmation.is_empty() or str(confirmation.get("anchor", "")) != anchor: return false
	confirm_bar(parent)
	return true

func ask(action: String, body: Dictionary, caption: String, anchor: String = "") -> void:
	confirmation={"action":"market-"+action,"body":body,"caption":caption,"anchor":anchor}
	if anchor.is_empty(): host.page_scroll["market"] = 0
	host._rebuild()

func confirm() -> void:
	if confirmation.is_empty(): return
	var intent := confirmation.duplicate(true)
	confirmation.clear()
	host._skin_command(intent.action,intent.body)

## − n + stepper; values live on this object so rebuilds keep them.
## − [n] + stepper. The number can also be typed: Enter or leaving the box
## applies it, clamped to 1…top. Values live on this object across rebuilds.
func stepper(parent: Node, value: int, top: int, callback: Callable) -> HBoxContainer:
	var row := hbox(parent, 4)
	row.name = "QuantityStepper"
	top = maxi(1, top)
	var minus := small(row, "−", func(): callback.call(maxi(1, value - 1)))
	minus.disabled = value <= 1
	var entry := LineEdit.new()
	entry.name = "QuantityValue"
	UI.line_edit(entry)
	entry.text = str(value)
	entry.alignment = HORIZONTAL_ALIGNMENT_CENTER
	entry.custom_minimum_size = Vector2(64, 0)
	entry.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	entry.select_all_on_focus = true
	entry.max_length = 3
	entry.tooltip_text = tr2("可直接输入数量，1–%d，回车确认", "Type a quantity from 1 to %d, then press Enter") % top
	var apply := func(raw: String):
		var digits := raw.strip_edges()
		var wanted := int(digits) if digits.is_valid_int() else value
		wanted = clampi(wanted, 1, top)
		if wanted != value: callback.call(wanted)
		else: entry.text = str(value)
	entry.text_submitted.connect(apply)
	entry.focus_exited.connect(func(): if is_instance_valid(entry): apply.call(entry.text))
	row.add_child(entry)
	var plus := small(row, "+", func(): callback.call(mini(top, value + 1)))
	plus.disabled = value >= top
	for step in [5, 10]:
		if top >= step: small(row, "×%d" % step, func(): callback.call(mini(top, step)))
	if top > 10: small(row, tr2("最多 %d", "Max %d") % top, func(): callback.call(top)).name = "QuantityMax"
	for node in [minus, plus]: node.custom_minimum_size.x = 38
	return row

func pager(parent: Node, total: int, per_page: int = 18) -> void:
	var pages := maxi(1, ceili(float(total) / per_page))
	if pages <= 1: return
	var row := hbox(parent, 8)
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	small(row, tr2("‹ 上一页", "‹ Previous"), func(): filters.page = maxi(1, int(filters.page) - 1); host.page_scroll["market"] = 0; host._rebuild()).disabled = int(filters.page) <= 1
	var where := line(row, "%d / %d" % [int(filters.page), pages], 14, UI.MUTED, false)
	where.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	where.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	small(row, tr2("下一页 ›", "Next ›"), func(): filters.page = int(filters.page) + 1; host.page_scroll["market"] = 0; host._rebuild()).disabled = int(filters.page) >= pages

# --- browse ---------------------------------------------------------------

func sorts() -> Array:
	return [["price|asc", tr2("价格从低到高", "Price: low to high")],
		["price|desc", tr2("价格从高到低", "Price: high to low")],
		["change_1|desc", tr2("今日涨幅", "Today's gainers")],
		["change_1|asc", tr2("今日跌幅", "Today's losers")],
		["change_7|desc", tr2("7 天涨幅", "7-day gainers")],
		["change_7|asc", tr2("7 天跌幅", "7-day losers")],
		["change_30|desc", tr2("30 天涨幅", "30-day gainers")],
		["change_30|asc", tr2("30 天跌幅", "30-day losers")],
		["name|asc", tr2("名称", "Name")]]

func filter_controls() -> void:
	var bar := hbox(host.content, 8)
	bar.name = "MarketToolbar"
	var search := LineEdit.new()
	UI.line_edit(search)
	search.name = "MarketSearch"
	search.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	search.text = str(filters.search)
	search.placeholder_text = tr2("搜索饰品名称，回车确认", "Search skins; press Enter")
	search.clear_button_enabled = true
	search.text_submitted.connect(func(value: String): set_filter("search", value))
	bar.add_child(search)
	var sort := option(bar, sorts().map(func(s): return s[1]), sorts().map(func(s): return s[0]), "%s|%s" % [filters.sort, filters.order], set_sort)
	sort.name = "MarketSort"
	sort.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	sort.custom_minimum_size.x = 170
	var count := active_filters()
	var toggle := small(bar, (tr2("筛选", "Filters") + (" · %d" % count if count > 0 else "")) + (" ▴" if advanced_filters else " ▾"), func(): advanced_filters = not advanced_filters; host._rebuild())
	toggle.name = "MarketFilterToggle"
	if count > 0: small(bar, tr2("清除", "Clear"), clear_filters).name = "MarketClearFilters"
	if not advanced_filters: return
	var box := panel(host.content, UI.LINE, Color("f4f2ea"), 10)
	box.get_parent().name = "MarketFilters"
	var row := hbox(box, 8)
	var slots: Array = [""] + cache.get("slots", [])
	option(row, [tr2("全部武器", "All weapons")] + cache.get("slots", []), slots, filters.slot, func(v): set_filter("slot", v))
	var rarities: Array = cache.get("rarities", [])
	var rarity_names: Array = [tr2("全部稀有度", "All rarities")]
	for rarity in rarities: rarity_names.append(host._rarity_label(str(rarity)))
	option(row, rarity_names, [""] + rarities, filters.rarity, func(v): set_filter("rarity", v))
	var wear_names: Array = [tr2("全部磨损", "All wears")]
	var wear_keys: Array = [""]
	for wear in cache.get("wears", []):
		wear_names.append(str(wear.id).to_upper() if Locale.language == "en" else wear.name)
		wear_keys.append(wear.id)
	option(row, wear_names, wear_keys, filters.wear, func(v): set_filter("wear", v))
	var prices := hbox(box, 8)
	line(prices, tr2("价格区间", "Price range"), 13, UI.MUTED, false).size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	for field in ["min_price","max_price"]:
		var entry := LineEdit.new()
		UI.line_edit(entry)
		entry.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		entry.placeholder_text = tr2("最低价", "Minimum price") if field == "min_price" else tr2("最高价", "Maximum price")
		entry.text = str(filters[field])
		entry.text_submitted.connect(func(value: String): if value.is_empty() or value.is_valid_float(): set_filter(field,value))
		prices.add_child(entry)
	line(prices, tr2("回车生效", "Enter to apply"), 12, UI.MUTED, false).size_flags_horizontal = Control.SIZE_SHRINK_END

func listing() -> void:
	var custody: bool = host.market_tab == "custody"
	if custody:
		custody_list()
		return
	filter_controls()
	var summary := hbox(host.content, 8)
	var total := int(cache.get("total", 0))
	line(summary, tr2("共 %d 件", "%d items") % total, 13, UI.MUTED).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	line(summary, tr2("出售手续费", "Selling fee") + " %.0f%%" % (float(cache.get("fee", .1))*100), 13, UI.MUTED, false).size_flags_horizontal = Control.SIZE_SHRINK_END
	var rows: Array = cache.get("rows", [])
	if rows.is_empty():
		Kit.empty_state(host.content, UI, "clipboard", tr2("没有符合条件的饰品", "No matching items"), tr2("换个关键词，或清除筛选条件。", "Try another search or clear the filters."))
		return
	var grid := flow(host.content)
	grid.name = "MarketListings"
	for row in rows: tile(grid, row, open_detail.bind(row))
	pager(host.content, total)

func open_detail(row: Dictionary) -> void:
	source_rumor.clear()
	detail_origin = host.market_tab
	origin_scroll = host.scroll.scroll_vertical
	selected=row.duplicate(true)
	quantity=1
	confirmation.clear()
	host.page_scroll["market"] = 0
	host._rebuild()

func back_to_list() -> void:
	selected.clear()
	confirmation.clear()
	source_rumor.clear()
	if not detail_origin.is_empty(): host.market_tab = detail_origin
	host.page_scroll["market"] = origin_scroll
	host._rebuild()

func open_rumor(item: Dictionary) -> void:
	var target = item.get("detail_target")
	if not target is Dictionary: return
	open_detail(target)
	source_rumor = item.duplicate(true)
	host._rebuild()

func rumor_input(event: InputEvent, item: Dictionary) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		open_rumor(item)

func pass_card_clicks(node: Node) -> void:
	for child in node.get_children():
		if child is Button: continue
		if child is Control: child.mouse_filter = Control.MOUSE_FILTER_PASS
		pass_card_clicks(child)

func set_quantity(value: int) -> void:
	quantity = value
	if str(confirmation.get("anchor", "")) == "detail": confirmation.clear()
	host._rebuild()

func detail() -> void:
	var item: Dictionary = cache.get("item",{})
	var top := hbox(host.content, 8)
	small(top, tr2("‹ 返回消息","‹ Back to rumors") if not source_rumor.is_empty() else tr2("‹ 返回列表","‹ Back to list"), back_to_list).name = "MarketBack"
	if not source_rumor.is_empty():
		label(host.content, (tr2("消息看涨", "Bullish rumor") if int(source_rumor.get("direction", 1)) > 0 else tr2("消息看跌", "Bearish rumor")) + " · " + tr2("有效至 ", "Until ") + str(source_rumor.get("expires", "")), 14, UI.GREEN)
	if item.is_empty(): return
	var columns: BoxContainer = HBoxContainer.new() if wide() else VBoxContainer.new()
	columns.name = "MarketDetail"
	columns.add_theme_constant_override("separation", 18)
	host.content.add_child(columns)
	var left := VBoxContainer.new()
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left.size_flags_stretch_ratio = 1.15
	left.add_theme_constant_override("separation", 10)
	columns.add_child(left)
	art(left, item, 172)
	var trend := panel(left)
	var head := hbox(trend, 8)
	line(head, tr2("价格走势", "Price history"), 15).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var chart := PriceChart.new()
	chart.name = "MarketPriceChart"
	chart.points = item.get("history",[])
	chart.custom_minimum_size.y = 150
	chart.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	trend.add_child(chart)
	if chart.points.size() < 2: line(trend, tr2("历史数据不足，推进日期后开始积累走势。","Not enough history yet; advance days to collect prices."), 12, UI.MUTED)
	else: line(head, Kit.short_date(str(chart.points[0].date)) + " → " + Kit.short_date(str(chart.points[-1].date)), 12, UI.MUTED, false).size_flags_horizontal = Control.SIZE_SHRINK_END
	var right := VBoxContainer.new()
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right.add_theme_constant_override("separation", 10)
	columns.add_child(right)
	var title := label(right, str(item.name), 22)
	title.name = "MarketItemName"
	line(right, str(host._rarity_label(str(item.get("rarity", "")))) + " · " + wear_text(item) + " · " + tr2("磨损 ", "Float ") + "%.2f–%.2f" % [float(item.get("min_float", 0)), float(item.get("max_float", 1))], 13, rarity_color(item))
	var price := line(right, Fmt.money(item.spot), 30)
	price.name = "MarketItemPrice"
	changes(right, item)
	purchase_panel(right, item)
	holdings(right, item)

func purchase_panel(parent: Node, item: Dictionary) -> void:
	var box := panel(parent, UI.LINE)
	box.get_parent().name = "MarketPurchase"
	line(box, tr2("购买到市场暂存", "Buy into market custody"), 15)
	var wallet := int(CareerBridge.context.get("skins",{}).get("personal_money", cache.get("money", 0)))
	var unit := int(item.spot)
	var affordable := maxi(1, mini(100, wallet / maxi(1, unit)))
	quantity = clampi(quantity, 1, 100)
	var row := hbox(box, 10)
	stepper(row, quantity, maxi(affordable, quantity) if wallet >= unit else 100, set_quantity)
	spacer(row)
	var total := unit * quantity
	var enough := wallet >= total
	var buy := small(row, tr2("购买 %d 件", "Buy %d") % quantity, func():
		ask("buy",{"id":item.id,"wear":item.wear_id,"quantity":quantity,"expected_total":total},tr2("购买 %d 件 %s · 总价 %s · 买后余额 %s","Buy %d × %s · total %s · balance after %s") % [quantity, str(item.name), Fmt.money(total), Fmt.money(wallet - total)], "detail"), true)
	buy.name = "MarketBuy"
	UI.primary(buy)
	buy.disabled = not enough
	var sums := line(box, tr2("合计 %s · 买后余额 %s", "Total %s · balance after %s") % [Fmt.money(total), Fmt.money(wallet - total)], 13, UI.MUTED if enough else DOWN)
	sums.name = "MarketTotal"
	if not enough: line(box, tr2("个人余额不够，减少数量再买。", "Not enough personal funds; lower the quantity."), 12, DOWN)
	line(box, tr2("买入不收手续费；卖出时扣 %.0f%%。", "No fee to buy; selling costs %.0f%%.") % (float(cache.get("fee", .1)) * 100), 12, UI.MUTED)
	inline_confirm(box, "detail")

func holdings(parent: Node, item: Dictionary) -> void:
	var owned := int(item.get("quantity", 0))
	if owned > 0:
		var mine := panel(parent)
		var head := hbox(mine, 8)
		line(head, tr2("我的暂存", "In custody"), 15).size_flags_horizontal = Control.SIZE_EXPAND_FILL
		small(head, tr2("去暂存出售 ›", "Sell in custody ›"), host._market_tab.bind("custody"))
		var tiles := hbox(mine, 8)
		Kit.stat_tile(tiles, UI, tr2("持有", "Held"), str(owned))
		Kit.stat_tile(tiles, UI, tr2("成本", "Cost"), Fmt.money(item.get("cost", 0)))
		Kit.stat_tile(tiles, UI, tr2("净盈亏", "Net P/L"), Fmt.money(item.get("profit", 0), true), "", "green" if float(item.get("profit", 0)) >= 0 else "red")
		var pl: Label = tiles.get_child(2).find_children("*", "Label", true, false)[1]
		pl.add_theme_color_override("font_color", pl_color(item.get("profit", 0)))
	if item.has("analysis"):
		var analysis: Dictionary = item.analysis
		var notes := panel(parent)
		notes.get_parent().name = "MarketAnalysis"
		line(notes, tr2("行情分析", "Market analysis"), 15)
		var tiles := hbox(notes, 8)
		Kit.stat_tile(tiles, UI, tr2("区间低", "Low"), Fmt.money(analysis.low))
		Kit.stat_tile(tiles, UI, tr2("区间高", "High"), Fmt.money(analysis.high))
		Kit.stat_tile(tiles, UI, tr2("均价", "Mean"), Fmt.money(analysis.mean))
		var extra: Array[String] = []
		if analysis.has("volatility"): extra.append(tr2("日波动 ", "Daily volatility ") + str(analysis.volatility) + "%")
		if analysis.has("break_even") and owned > 0: extra.append(tr2("持仓回本价 ", "Break-even ") + Fmt.money(analysis.break_even))
		if not extra.is_empty(): line(notes, " · ".join(extra), 13, UI.MUTED)

# --- custody --------------------------------------------------------------

func set_lot_quantity(lot: String, value: int) -> void:
	lot_quantity[lot] = value
	if str(confirmation.get("anchor", "")) == "lot:" + lot: confirmation.clear()
	host._rebuild()

func custody_list() -> void:
	var rows: Array = cache.get("rows", [])
	var fee := float(cache.get("fee", .1))
	var intro := hbox(host.content, 8)
	line(intro, tr2("暂存里的饰品可以直接卖出；要装备时提取到库存。", "Sell straight from custody, or withdraw to equip."), 14).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	line(intro, tr2("出售手续费", "Selling fee") + " %.0f%%" % (fee * 100), 13, UI.MUTED, false).size_flags_horizontal = Control.SIZE_SHRINK_END
	if rows.is_empty():
		Kit.empty_state(host.content, UI, "clipboard", tr2("暂存是空的", "Custody is empty"), tr2("在市场买入的饰品会先放在这里。", "Items you buy on the market land here first."))
		small(host.content, tr2("去市场看看 ›", "Browse the market ›"), host._market_tab.bind("market"))
		return
	var held := 0; var cost := 0.0; var value := 0.0; var profit := 0.0
	for row in rows:
		held += int(row.get("quantity", 0)); cost += float(row.get("cost", 0)); profit += float(row.get("profit", 0))
		value += float(row.get("spot", 0)) * int(row.get("quantity", 0))
	var tiles := hbox(host.content, 8)
	tiles.name = "CustodySummary"
	Kit.stat_tile(tiles, UI, tr2("件数", "Items"), str(held))
	Kit.stat_tile(tiles, UI, tr2("总成本", "Total cost"), Fmt.money(cost))
	Kit.stat_tile(tiles, UI, tr2("现价总值", "Market value"), Fmt.money(value))
	Kit.stat_tile(tiles, UI, tr2("净盈亏（未扣手续费）", "Net P/L (before fees)"), Fmt.money(profit, true))
	var pl: Label = tiles.get_child(3).find_children("*", "Label", true, false)[1]
	pl.add_theme_color_override("font_color", pl_color(profit))
	var list := VBoxContainer.new()
	list.name = "MarketListings"
	list.add_theme_constant_override("separation", 8)
	host.content.add_child(list)
	for row in rows: custody_row(list, row, fee)
	pager(host.content, int(cache.get("total", rows.size())))

func custody_row(list: Node, row: Dictionary, fee: float) -> void:
	var lot := str(row.get("lot_id", ""))
	var box := panel(list, UI.LINE, UI.PAPER, 10)
	box.get_parent().name = "CustodyLot"
	var line_row := hbox(box, 14)
	var thumb := Button.new()
	thumb.custom_minimum_size = Vector2(132, 70)
	thumb.tooltip_text = tr2("查看行情", "View market details")
	thumb.focus_mode = Control.FOCUS_ALL
	tile_styles(thumb)
	thumb.pressed.connect(open_detail.bind(row))
	line_row.add_child(thumb)
	var holder := MarginContainer.new()
	holder.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	holder.mouse_filter = Control.MOUSE_FILTER_IGNORE
	thumb.add_child(holder)
	art(holder, row, 60)
	quiet(holder)
	var words := VBoxContainer.new()
	words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	words.add_theme_constant_override("separation", 2)
	line_row.add_child(words)
	line(words, str(row.get("name", "")), 16)
	line(words, wear_text(row) + " · " + tr2("现价 ", "Now ") + Fmt.money(row.get("spot", 0)) + " · " + tr2("今日 ", "Today ") + pct(row.get("change_1")), 12, UI.MUTED)
	line(words, tr2("持有 %d 件 · 成本 %s", "%d held · cost %s") % [int(row.get("quantity", 0)), Fmt.money(row.get("cost", 0))], 13)
	line(words, tr2("净盈亏 ", "Net P/L ") + Fmt.money(row.get("profit", 0), true), 13, pl_color(row.get("profit", 0)))
	var owned := maxi(1, int(row.get("quantity", 1)))
	var count := clampi(int(lot_quantity.get(lot, 1)), 1, mini(100, owned))
	var actions := VBoxContainer.new()
	actions.add_theme_constant_override("separation", 6)
	actions.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	line_row.add_child(actions)
	if owned > 1:
		var step := stepper(actions, count, mini(100, owned), func(v: int): set_lot_quantity(lot, v))
		step.alignment = BoxContainer.ALIGNMENT_END
	var buttons := hbox(actions, 8)
	buttons.alignment = BoxContainer.ALIGNMENT_END
	var gross := int(row.get("spot", 0)) * count
	var net := floori(float(row.get("spot", 0)) * count * (1 - fee))
	small(buttons, tr2("提取 %d 件", "Withdraw %d") % count, func(): ask("withdraw",{"lot_id":lot,"quantity":count},tr2("提取 %d 件 %s 到库存？提取后不能在暂存里直接卖出。","Withdraw %d × %s to your inventory? It can no longer be sold from custody.") % [count, str(row.get("name", ""))], "lot:" + lot)).name = "CustodyWithdraw"
	var sell := small(buttons, tr2("出售 · 到手 %s", "Sell · net %s") % Fmt.money(net), func():
		ask("sell",{"lot_id":lot,"quantity":count,"expected_total":net},tr2("卖出 %d 件 · 总价 %s · 手续费 %s · 到手 %s · 余额 %s","Sell %d · gross %s · fee %s · net %s · balance %s") % [count, Fmt.money(gross), Fmt.money(gross - net), Fmt.money(net), Fmt.money(int(cache.get("money",0)) + net)], "lot:" + lot), true)
	sell.name = "CustodySell"
	UI.primary(sell)
	inline_confirm(box, "lot:" + lot)

# --- informant --------------------------------------------------------------

func merchant() -> void:
	var head := hbox(host.content, 10)
	var words := VBoxContainer.new()
	words.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(words)
	line(words, tr2("消息商人","Market informant"), 21)
	label(words, tr2("消息有真有假；行情也会受其他供需影响。","Rumors can be wrong; other market forces still matter."), 13, UI.MUTED)
	label(host.content, tr2("两类消息每天各买一条；已买的消息不会因读档或换持仓刷新。", "One rumor of each type per day; purchased notes stay fixed after reloading or changing holdings."), 13, UI.MUTED)
	var offers := flow(host.content)
	for offer in cache.get("offers", []):
		rumor_offer(offers, offer)
	Kit.section(host.content, UI, tr2("交易技能", "Trading skills"), "", 17)
	var skills := flow(host.content)
	var tips := {"analysis":tr2("逐级解锁区间分析、波动和回本价。", "Unlock range analysis, volatility and break-even estimates."), "judgment":tr2("缩小可靠度评估区间，不会直接揭晓真假。", "Narrow reliability estimates without revealing the truth."), "bargaining":tr2("出售手续费依次降至 9%、8%、7%。", "Reduce selling fees to 9%, 8%, then 7%.")}
	for skill in cache.get("skills",[]):
		var card := panel(skills)
		card.get_parent().custom_minimum_size.x = 330
		card.get_parent().size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var top := hbox(card, 8)
		line(top, str(skill.id).capitalize() if Locale.language=="en" else str(skill.name), 16).size_flags_horizontal = Control.SIZE_EXPAND_FILL
		Kit.chip(top, "Lv.%d" % int(skill.level), "green" if int(skill.level) > 0 else "gray", 12)
		label(card, str(tips.get(skill.id,"")), 12, UI.MUTED)
		if skill.cost != null:
			small(card, tr2("升级 · ","Upgrade · ") + Fmt.money(skill.cost), func(): ask("skill",{"skill":skill.id},tr2("升级%s，花费 %s？","Upgrade %s for %s?") % [str(skill.get("name", skill.id)), Fmt.money(skill.cost)], "skill:" + str(skill.id)), true)
		else:
			Kit.chip(card, tr2("已满级", "Maxed"), "amber", 12)
		inline_confirm(card, "skill:" + str(skill.id))
	Kit.section(host.content, UI, tr2("消息记录", "Rumor log"), "", 17)
	var rumors: Array = cache.get("rumors",[])
	if rumors.is_empty():
		label(host.content, tr2("还没有消息。买一条今日消息，它会记在这里，到期后显示实际涨跌。", "No rumors yet. Bought rumors are logged here with the real move once they expire."), 13, UI.MUTED)
	for item in rumors:
		var row := panel(host.content, UI.LINE, UI.PAPER, 10)
		row.get_parent().name = "MarketRumor"
		var top := hbox(row, 8)
		var up := int(item.direction) > 0
		Kit.chip(top, tr2("看涨","Bullish") if up else tr2("看跌","Bearish"), "green" if up else "red", 12)
		line(top, str(item.name), 15).size_flags_horizontal = Control.SIZE_EXPAND_FILL
		if item.get("outcome_pct") != null:
			var moved := float(item.outcome_pct)
			Kit.chip(top, tr2("到期 ", "At expiry ") + pct(item.outcome_pct), "green" if moved > 0 else ("red" if moved < 0 else "gray"), 12)
		line(row, tr2("%s 收到 · 有效至 %s · 可靠度估计 %s", "Received %s · until %s · estimated reliability %s") % [Kit.short_date(str(item.date)), Kit.short_date(str(item.expires)), str(item.reliability)], 12, UI.MUTED)
		if item.get("detail_target") is Dictionary:
			small(row, tr2("查看饰品", "View item"), open_rumor.bind(item)).name = "MarketRumorOpen"
			pass_card_clicks(row.get_parent())
			row.get_parent().mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
			row.get_parent().gui_input.connect(rumor_input.bind(item))

func rumor_offer(parent: Node, offer: Dictionary) -> void:
	var kind := str(offer.get("kind", "bullish"))
	var bullish := kind == "bullish"
	var box := panel(parent)
	box.get_parent().custom_minimum_size.x = 300
	box.get_parent().size_flags_horizontal = Control.SIZE_EXPAND_FILL
	line(box, tr2("看涨消息", "Bullish rumor") if bullish else tr2("持仓看跌消息", "Bearish holdings rumor"), 17)
	label(box, tr2("从整个市场随机找机会，不限于已持有饰品。", "Random opportunities across the market, not limited to your holdings.") if bullish else tr2("只针对市场暂存或装备仓库里仍持有的饰品。", "Only items currently held in market custody or your inventory."), 13, UI.MUTED)
	var bought: bool = offer.get("purchased", false)
	var price := Fmt.money(offer.get("price", 750))
	var question := tr2("花 %s 购买今天的看涨消息？", "Buy today's bullish rumor for %s?") if bullish else tr2("花 %s 购买今天的持仓看跌消息？", "Buy today's bearish holdings rumor for %s?")
	var rumor := small(box, tr2("今日已购买", "Bought today") if bought else tr2("购买 · ", "Buy · ") + price, func(): ask("rumor", {"kind":kind}, question % price, "rumor:" + kind), true)
	rumor.name = "MarketBuyBullish" if bullish else "MarketBuyBearish"
	rumor.disabled = rumor.disabled or bought or not offer.get("available", false)
	if not bought and offer.get("available", false): UI.primary(rumor)
	if not bought and not offer.get("available", false):
		label(box, tr2("暂无持有饰品；买入后可购买看跌消息。", "No items held. Buy an item before requesting a bearish rumor.") if not bullish else tr2("市场暂无饰品。", "No items are currently listed."), 13, UI.MUTED)
	inline_confirm(box, "rumor:" + kind)

# --- supplies ---------------------------------------------------------------

func axis_name(axis: String, fallback: String = "") -> String:
	var axes := {"firepower":tr2("火力","Firepower"),"entrying":tr2("突破","Entrying"),"trading":tr2("补枪","Trading"),"opening":tr2("首杀","Opening"),"clutching":tr2("残局","Clutching"),"sniping":tr2("狙击","Sniping"),"utility":tr2("道具","Utility")}
	return str(axes.get(axis, fallback if not fallback.is_empty() else axis))

func grade_name(grade: String) -> String:
	return tr2("强效","Strong") if grade == "strong" else tr2("普通","Normal")

func supplies() -> void:
	line(host.content, tr2("赛前补给","Match supplies"), 21)
	label(host.content, tr2("每位选手同一时间只能用一种药剂：普通药剂管一张图，强效药剂管整个 BO。","One effect per player at a time: normal lasts one map, strong lasts the whole BO."), 13, UI.MUTED)
	var accounts: Array = ["personal"]
	var names: Array = [tr2("个人钱包","Personal wallet")+" · "+Fmt.money(cache.get("money",0))]
	if cache.get("club_allowed",false):
		accounts.append("club")
		names.append(tr2("俱乐部经费","Club funds")+" · "+Fmt.money(cache.get("club_money",0)))
	if payer not in accounts: payer="personal"
	var head := hbox(host.content, 10)
	line(head, tr2("① 购买药剂", "1 · Buy supplies"), 17).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var pay := line(head, tr2("付款", "Pay with"), 13, UI.MUTED, false)
	pay.size_flags_horizontal = Control.SIZE_SHRINK_END
	pay.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var wallet := option(head, names, accounts, payer, func(v): payer=v; host._rebuild())
	wallet.name = "SupplyPayer"
	wallet.size_flags_horizontal = Control.SIZE_SHRINK_END
	wallet.custom_minimum_size.x = 260
	var shop := flow(host.content)
	shop.name = "SupplyShop"
	var balance := float(cache.get("club_money", 0)) if payer == "club" else float(cache.get("money", 0))
	for item in cache.get("catalog",[]):
		var card := panel(shop)
		card.get_parent().custom_minimum_size.x = 244
		var top := hbox(card, 8)
		line(top, axis_name(str(item.axis), str(item.get("name", ""))) + " +" + str(item.bonus), 17).size_flags_horizontal = Control.SIZE_EXPAND_FILL
		Kit.chip(top, grade_name(str(item.grade)), "amber" if item.grade == "strong" else "gray", 12)
		line(card, (tr2("整个 BO", "Whole BO") if item.grade == "strong" else tr2("一张图", "One map")) + " · " + tr2("用后冷却 %s 天", "%s-day cooldown") % str(item.days), 12, UI.MUTED)
		var row := hbox(card, 8)
		line(row, Fmt.money(item.price), 17).size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var anchor := "buy:%s:%s" % [item.axis, item.grade]
		var buy := small(row, tr2("购买", "Buy"), func():
			var account := str(names[accounts.find(payer)]).split(" · ")[0]
			confirmation={"action":"supply-buy","body":{"axis":item.axis,"grade":item.grade,"payer":payer},"caption":tr2("购买 %s · %s · 从%s付款？","Buy %s · %s · paid from %s?") % [axis_name(str(item.axis)) + " " + grade_name(str(item.grade)), Fmt.money(item.price), account],"anchor":anchor}
			host._rebuild(), true)
		buy.disabled = balance < float(item.price)
		inline_confirm(card, anchor)
	assign()

func assign() -> void:
	var players: Array = cache.get("players",[])
	var targets: Array = cache.get("targets",[]).filter(func(t): return not t.started)
	Kit.section(host.content, UI, tr2("② 分配给选手", "2 · Assign to a player"), "", 17)
	if players.is_empty():
		label(host.content, tr2("加入队伍后才能给选手准备药剂。", "Join a team before preparing supplies."), 13, UI.MUTED)
		return
	var ids: Array = players.map(func(p): return p.id)
	if supply_player not in ids: supply_player=str(ids[0])
	var target_ids: Array = targets.map(func(t): return t.id)
	if supply_target not in target_ids: supply_target=str(target_ids[0]) if not target_ids.is_empty() else ""
	var pick := hbox(host.content, 8)
	var who := option(pick, players.map(func(p): return p.name), ids, supply_player, func(v): supply_player=v; host._rebuild())
	who.name = "SupplyPlayer"
	if not targets.is_empty():
		var when := option(pick, targets.map(func(t): return t.label), target_ids, supply_target, func(v): supply_target=v; host._rebuild())
		when.name = "SupplyTarget"
	var status := hbox(host.content, 6)
	var prepared: Dictionary = cache.get("prepared",{})
	var active: bool = cache.get("active",{}).has(supply_player)
	var cooldown := str(cache.get("cooldowns",{}).get(supply_player,""))
	if active: Kit.chip(status, tr2("药剂效果生效中","Effect active"), "green", 12)
	if prepared.has(supply_player):
		Kit.chip(status, tr2("已准备，开赛时使用", "Prepared for the match"), "blue", 12)
		small(status, tr2("取消准备","Cancel preparation"), func(): host._skin_command("supply-cancel",{"player_id":supply_player}), true)
	if not cooldown.is_empty(): Kit.chip(status, tr2("冷却至 ","Cooldown until ") + cooldown, "amber", 12)
	if targets.is_empty(): label(host.content, tr2("先安排训练赛，或推进到下一场比赛，才能选择用在哪张图。","Book a scrim or advance to your next match to pick a map."), 13, UI.MUTED)
	var stock: Array = cache.get("stock",[])
	if stock.is_empty():
		label(host.content, tr2("库存里还没有药剂，先在上面购买。", "No supplies in stock yet; buy one above."), 13, UI.MUTED)
		return
	var counts := {}
	var first := {}
	for item in stock:
		var key := "%s:%s" % [item.axis, item.grade]
		counts[key] = int(counts.get(key, 0)) + 1
		if not first.has(key): first[key] = item
	var name_of := str(players[ids.find(supply_player)].name)
	var blocked := supply_target.is_empty() or prepared.has(supply_player) or active
	var list := VBoxContainer.new()
	list.name = "SupplyStock"
	list.add_theme_constant_override("separation", 6)
	host.content.add_child(list)
	for key in first:
		var item: Dictionary = first[key]
		var row := panel(list, UI.LINE, UI.PAPER, 10)
		var top := hbox(row, 8)
		line(top, axis_name(str(item.axis)), 15)
		Kit.chip(top, grade_name(str(item.grade)), "amber" if item.grade == "strong" else "gray", 12)
		line(top, tr2("库存 %d", "%d in stock") % int(counts[key]), 12, UI.MUTED).size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var use := small(top, tr2("给 %s 准备", "Prepare for %s") % name_of, func(): host._skin_command("supply-prepare",{"item_id":item.id,"player_id":supply_player,"target":supply_target}), true)
		use.name = "SupplyPrepare"
		use.disabled = blocked

class PriceChart extends Control:
	var points: Array=[]
	func _draw() -> void:
		draw_style_box(UI.style(Color("eef2ea"),8,8),Rect2(Vector2.ZERO,size))
		if points.size()<2: return
		var values: Array=points.map(func(p): return float(p.price))
		var low: float=values.min()
		var high: float=values.max()
		var font := get_theme_default_font()
		var left := 64.0
		for fraction in [0.0, 0.5, 1.0]:
			var y: float = 14 + (size.y - 32) * fraction
			draw_line(Vector2(left, y), Vector2(size.x - 10, y), Color(0.13, 0.2, 0.17, 0.08), 1.0)
			draw_string(font, Vector2(8, y + 4), Fmt.money(high - (high - low) * fraction), HORIZONTAL_ALIGNMENT_LEFT, left - 12, 11, Color("6c776f"))
		var coords:=PackedVector2Array()
		for i in range(values.size()): coords.append(Vector2(left+(size.x-left-12)*i/maxi(1,values.size()-1),14+(size.y-32)*(1.0-(values[i]-low)/maxf(1,high-low))))
		var fill := PackedVector2Array(coords)
		fill.append(Vector2(coords[-1].x, size.y - 18)); fill.append(Vector2(coords[0].x, size.y - 18))
		draw_colored_polygon(fill, Color(0.19, 0.43, 0.34, 0.10))
		var rising: bool = values[-1] >= values[0]
		draw_polyline(coords, Color("306e56") if rising else Color("ad5b52"), 2.5, true)
		draw_circle(coords[-1], 4.0, Color("306e56") if rising else Color("ad5b52"))
