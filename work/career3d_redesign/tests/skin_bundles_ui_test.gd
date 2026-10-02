extends Node
## Run only in a disposable D/E project with the matching in-memory bridge.
var checks := 0
var failures: Array[String] = []
var fixture: Dictionary = {}
var output := ""

func _ready() -> void:
	if not CareerBridge.get_script().resource_path.ends_with("skin_bundles_bridge_fixture.gd"):
		push_error("Skin bundle UI QA requires the in-memory bridge; no live backend is allowed.")
		get_tree().quit(2)
		return
	var root := ProjectSettings.globalize_path("res://")
	if root.left(3).to_upper() not in ["D:/", "E:/"]:
		push_error("Run this UI QA in a disposable D/E project.")
		get_tree().quit(2)
		return
	output = root.path_join("skin-bundles-ui-output")
	DirAccess.make_dir_recursive_absolute(output)
	var loaded = JSON.parse_string(FileAccess.get_file_as_string("res://tests/skin_bundles_fixture.json"))
	if not loaded is Dictionary or not loaded.get("fixture", false):
		push_error("Generate the actual-catalog skin_bundles_fixture.json first.")
		get_tree().quit(2)
		return
	fixture = loaded
	Computer.set_process(false)
	Phone.set_process(false)
	get_window().size = Vector2i(1280, 720)
	call_deferred("run")

func check(value: bool, caption: String) -> void:
	checks += 1
	if not value: failures.append(caption)
	print("SKIN_BUNDLES_UI_CHECK ", "PASS " if value else "FAIL ", caption)

func settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame

func capture(caption: String) -> void:
	if DisplayServer.get_name() == "headless": return
	await RenderingServer.frame_post_draw
	check(get_viewport().get_texture().get_image().save_png(output.path_join(caption + ".png")) == OK, "native screenshot " + caption)

func labels(node: Node) -> Array[String]:
	var result: Array[String] = []
	for child in node.get_children():
		if child is Label: result.append(child.text)
		result.append_array(labels(child))
	return result

func find_button(node: Node, caption: String) -> Button:
	for child in node.get_children():
		if child is Button and child.text == caption: return child
		var found := find_button(child, caption)
		if found != null: return found
	return null

func fit(caption: String) -> void:
	var physical: Rect2 = get_viewport().get_final_transform() * Computer.panel.get_global_rect()
	check(Rect2(Vector2.ZERO, Vector2(get_window().size)).encloses(physical), caption + " monitor fits physical 1280x720 window")
	check(Computer.content.get_combined_minimum_size().x <= Computer.scroll.size.x + 1, caption + " has no horizontal overflow")
	check(Computer.scroll.size.y >= 250, caption + " keeps usable scroll height")
	for pack in fixture["shop"]["loadout_packs"]:
		var card = Computer.content.find_child("ProBundle_" + str(pack["id"]), true, false)
		if card != null:
			check(card.get_child(0).size.y <= 90, caption + " compact purchase row " + str(pack["display_name"]))

func page(shop: Dictionary) -> void:
	CareerBridge.context = {"date":"2026-10-02", "calendar":{"revision":17},
		"player":{"id":"ui-fixture", "name":"界面测试"}, "stories":[], "inbox":[], "contacts":[],
		"start":{"can_continue":true}, "skins":shop.duplicate(true)}
	CareerBridge.busy = false
	CareerBridge.requests.clear()
	Computer.selected_skin = {}
	Computer.market_tab = "packs"
	Computer.open_app("market", "club")
	await settle()

func run() -> void:
	var shop: Dictionary = fixture["shop"]
	var packs: Array = shop["loadout_packs"]
	check(packs.size() == 4, "actual backend catalog contains four player bundles")
	var item_count := 0
	for pack in packs: item_count += int(pack["count"])
	check(item_count == 33, "actual backend catalog contains all 33 recipe items")
	await page(shop)
	check(Computer.content.find_children("ProBundle_*", "VBoxContainer", true, false).size() == 4, "renders four distinct bundle cards")
	fit("available bundles")
	var all_words := "\n".join(labels(Computer.content))
	check(not all_words.contains("¥") and not all_words.contains("人民币"), "bundle page consistently displays game currency")
	for pack in packs:
		var ident := str(pack["id"])
		var card = Computer.content.find_child("ProBundle_" + ident, true, false)
		var buy: Button = card.find_child("ProBundleBuy_" + ident, true, false)
		check(buy != null and not buy.disabled, str(pack["display_name"]) + " affordable purchase is enabled")
		check(buy.focus_mode == Control.FOCUS_ALL and buy.get_theme_stylebox("focus") != null, str(pack["display_name"]) + " purchase has keyboard focus styling")
		buy.grab_focus()
		await settle()
		check(buy.has_focus(), str(pack["display_name"]) + " purchase accepts keyboard focus")
		check(buy.get_theme_color("font_focus_color") == buy.get_theme_color("font_color"), str(pack["display_name"]) + " focus preserves button text contrast")
		check(labels(card).has("%d 件 · %d 游戏币" % [int(pack["count"]), int(pack["price"])]), str(pack["display_name"]) + " shows its actual integer item count and quote")
		check(labels(card).has(str(pack["description"])), str(pack["display_name"]) + " explains declared template defaults and bound items")
		buy.pressed.emit()
		var request: Dictionary = CareerBridge.requests[-1]
		check(request["path"] == "/api/3d/skins/bundle" and request["post"], str(pack["display_name"]) + " purchase uses bundle endpoint")
		check(request["body"]["id"] == ident and int(request["body"]["revision"]) == 17, str(pack["display_name"]) + " purchase carries exact ID and context revision")
		check(str(request["body"]["request_id"]).begins_with("bundle-") and str(request["body"]["request_id"]).length() >= 8, str(pack["display_name"]) + " purchase carries a unique request ID")
	check(CareerBridge.requests.size() == 4 and CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "purchase checks capture memory requests without a network or service")
	var request_ids: Dictionary = {}
	for request in CareerBridge.requests: request_ids[str(request["body"]["request_id"])] = true
	check(request_ids.size() == 4, "each bundle button generates a distinct purchase request ID")
	Computer.scroll.scroll_vertical = 0
	await settle()
	await capture("bundles-available-1280x720")
	var request_total: int = CareerBridge.requests.size()
	for pack in packs:
		var ident := str(pack["id"])
		var card = Computer.content.find_child("ProBundle_" + ident, true, false)
		var expand_button := find_button(card, "查看全部配装")
		expand_button.grab_focus()
		await settle()
		expand_button.pressed.emit()
		await settle()
		card = Computer.content.find_child("ProBundle_" + ident, true, false)
		check(Computer.skin_bundles.expanded_id == ident and find_button(card, "收起清单") != null, str(pack["display_name"]) + " expands its full item list")
		check(find_button(card, "收起清单").has_focus(), str(pack["display_name"]) + " expansion keeps focus on the same bundle")
		for item in pack["items"]:
			check(labels(card).has(str(item["name"])), str(pack["display_name"]) + " expanded item " + str(item["skin_id"]))
		fit("expanded " + str(pack["display_name"]))
		if pack["player"] == "donk":
			Computer.scroll.scroll_vertical = 0
			await settle()
			await capture("bundles-donk-expanded-1280x720")
		var collapse := find_button(card, "收起清单")
		check(collapse.focus_mode == Control.FOCUS_ALL and not collapse.disabled, str(pack["display_name"]) + " collapse remains focusable")
		collapse.grab_focus()
		collapse.pressed.emit()
		await settle()
		card = Computer.content.find_child("ProBundle_" + ident, true, false)
		check(Computer.skin_bundles.expanded_id.is_empty() and find_button(card, "查看全部配装") != null, str(pack["display_name"]) + " collapses to its featured preview")
		check(find_button(card, "查看全部配装").has_focus(), str(pack["display_name"]) + " collapse keeps focus on the same bundle")
	check(CareerBridge.requests.size() == request_total, "expansion and collapse send no purchase or service request")
	var insufficient := shop.duplicate(true)
	insufficient["personal_money"] = 0
	for pack in insufficient["loadout_packs"]: pack["buy_allowed"] = false
	await page(insufficient)
	for pack in packs:
		var card = Computer.content.find_child("ProBundle_" + str(pack["id"]), true, false)
		check(card.find_child("ProBundleBuy_" + str(pack["id"]), true, false).disabled, str(pack["display_name"]) + " insufficient wallet disables purchase")
		check(labels(card).has("个人余额不足"), str(pack["display_name"]) + " insufficient wallet has an explanation")
	fit("insufficient wallet")
	await capture("bundles-insufficient-1280x720")
	var owned := shop.duplicate(true)
	for pack in owned["loadout_packs"]:
		pack["owned"] = true
		pack["imported"] = true
		pack["buy_allowed"] = false
	await page(owned)
	for pack in packs:
		var buy: Button = Computer.content.find_child("ProBundleBuy_" + str(pack["id"]), true, false)
		check(buy.disabled and buy.text == "已在库存", str(pack["display_name"]) + " existing inventory prevents repeated purchase")
	fit("already owned")
	await capture("bundles-owned-1280x720")
	check(CareerBridge.requests.is_empty() and CareerBridge.endpoint.is_empty(), "owned and wallet states cause no external request")
	var result := {"ok":failures.is_empty(), "checks":checks, "failures":failures,
		"backend":"memory only", "physical_window":"1280x720", "catalog":"four real pinned templates, 33 items"}
	var file := FileAccess.open(output.path_join("skin-bundles-ui-qa.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify(result, "  "))
	print("SKIN_BUNDLES_UI_RESULT ", JSON.stringify(result))
	get_tree().quit(0 if failures.is_empty() else 1)
