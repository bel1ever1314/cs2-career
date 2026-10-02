extends RefCounted
## Priced, existing pro templates. Inventory and payment belong to the service.
const UI = preload("res://scripts/computer_ui.gd")
var expanded_id := ""

func render(host: Node, parent: Node, shop: Dictionary) -> void:
	UI.label(parent, "职业选手配装", 21)
	UI.label(parent, "使用游戏内个人余额购买，枪械、刀和手套一并放入库存。", 13, UI.MUTED)
	var packs: Array = shop.get("loadout_packs", [])
	for pack in packs:
		var card := UI.card(parent)
		card.name = "ProBundle_" + str(pack.get("id", ""))
		var heading := HBoxContainer.new()
		card.add_child(heading)
		var title := UI.label(heading, str(pack.get("display_name", pack.get("player", pack.get("name", "配装")))), 19)
		title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		UI.label(heading, "%d 件 · %d 游戏币" % [int(pack.get("count", pack.get("items", []).size())), int(pack.get("price", 0))], 14)
		var owned := bool(pack.get("owned", pack.get("imported", false)))
		var buy: Button = host._button(heading, "已在库存" if owned else "购买整套", purchase.bind(host, str(pack.get("id", ""))))
		buy.name = "ProBundleBuy_" + str(pack.get("id", ""))
		buy.disabled = owned or not bool(pack.get("buy_allowed", false))
		if not owned: UI.primary(buy)
		UI.label(card, str(pack.get("description", "公开配装模板；使用默认磨损和图案，入库后可装备，不可转卖。")), 12, UI.MUTED)
		var preview := HBoxContainer.new()
		card.add_child(preview)
		var items: Array = pack.get("items", [])
		var shown: Array = items if expanded_id == str(pack.get("id", "")) else featured(items)
		if expanded_id == str(pack.get("id", "")):
			for item in shown: UI.label(card, str(item.get("name", item.get("label", "饰品"))), 13)
		else:
			for item in shown:
				var tile := VBoxContainer.new()
				tile.size_flags_horizontal = Control.SIZE_EXPAND_FILL
				preview.add_child(tile)
				host._skin_art(tile, item, 90)
				UI.label(tile, str(item.get("name", item.get("label", "饰品"))), 12)
		var expand_button: Button = host._button(card, "收起清单" if expanded_id == str(pack.get("id", "")) else "查看全部配装", expand.bind(host, str(pack.get("id", ""))), false)
		expand_button.name = "ProBundleExpand_" + str(pack.get("id", ""))
		expand_button.set_meta("stable_focus", str(expand_button.name))
		if not owned and float(shop.get("personal_money", 0)) < float(pack.get("price", 0)):
			UI.label(card, "个人余额不足", 12, UI.MUTED)
	if packs.is_empty(): UI.label(parent, "配装目录还未载入。", 14, UI.MUTED)

func purchase(host: Node, ident: String) -> void:
	host._skin_command("bundle", {"id":ident, "request_id":"bundle-%d-%d" % [OS.get_process_id(), Time.get_ticks_usec()]})

func expand(host: Node, ident: String) -> void:
	expanded_id = "" if expanded_id == ident else ident
	host._rebuild()

static func featured(items: Array) -> Array:
	var result: Array = []
	for slot in ["knife", "gloves", "ak47"]:
		for item in items:
			if str(item.get("slot", "")) == slot and not result.has(item):
				result.append(item)
				break
	for item in items:
		if result.size() >= 3: break
		if not result.has(item): result.append(item)
	return result
