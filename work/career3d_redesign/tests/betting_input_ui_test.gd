extends Node
## Typed market quantities and one-step winner picks on the predictions page.
var checks := 0
var failures: Array[String] = []

func _ready() -> void: call_deferred("run")
func check(value: bool, caption: String) -> void:
	checks += 1
	if not value: failures.append(caption)
	print("BETTING_INPUT ", "PASS " if value else "FAIL ", caption)
func frames() -> void:
	for i in range(5): await get_tree().process_frame
func alive(node: Node) -> bool:
	while node != null:
		if node.is_queued_for_deletion(): return false
		node = node.get_parent()
	return true
func live(name: String) -> Node:
	for node in Computer.content.find_children(name, "", true, false):
		if alive(node): return node
	return null

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(2); return
	CareerBridge.set_process(false); Computer.set_process(false)
	Locale.set_language("zh-CN", false)
	CareerBridge.context = {"calendar":{"revision":0}, "personal_money":10000, "start":{"creation_required":false}, "skins":{"personal_money":10000}}
	# Market: typed quantity, clamped to what the wallet allows.
	Computer.open_app("market")
	Computer._market_tab("market")
	var market = Computer.native_market
	var row := {"id":"ak", "name":"AK-47 | Redline", "weapon":"AK-47", "wear_id":"ft", "rarity":"classified", "spot":400, "art_path":""}
	market.open_detail(row)
	var item := row.duplicate(true)
	item.merge({"min_float":.1, "max_float":.7, "quantity":0, "history":[]}, true)
	market.finished(market.request_path, {"ok":true, "market":{"item":item, "fee":.1}})
	await frames()
	var entry: LineEdit = live("QuantityValue")
	check(entry != null and entry.text == "1", "quantity box shows the current amount")
	entry.text_submitted.emit("7")
	await frames()
	check(market.quantity == 7, "typed quantity applies on Enter")
	entry = live("QuantityValue")
	entry.text_submitted.emit("999")
	await frames()
	check(market.quantity == 25, "typed quantity clamps to the affordable maximum")
	entry = live("QuantityValue")
	entry.text_submitted.emit("abc")
	await frames()
	check(market.quantity == 25, "non-numbers keep the previous amount")
	check(live("QuantityMax") != null, "max shortcut offered")
	var buy: Button = live("MarketBuy")
	check(buy != null and buy.text.contains("25"), "buy button names the typed quantity")
	# Predictions: picking a side opens the stake panel and submits a win.
	Computer.open_app("events")
	Computer._events_tab("predictions")
	var predictions = Computer.predictions
	predictions.switch_tab("available")
	var offer := {"key":"2026:cup:m", "quote_id":"q", "year":2026, "event_name":"Cup", "date":"2026-01-08", "best_of":3, "team_a":{"id":"a", "name":"Spirit"}, "team_b":{"id":"b", "name":"Vitality"}, "odds_hundredths":{"a":150, "b":250}}
	predictions.finished(predictions.pending, {"ok":true, "state_revision":0, "predictions":{"rows":[offer], "money":10000, "total":1, "page_size":12}})
	await frames()
	check(live("PredictionStake") == null, "stake panel closed until a side is picked")
	var side_b: Button = live("PredictionChooseB")
	side_b.pressed.emit()
	await frames()
	check(predictions.team_id == "b" and live("PredictionStake") != null, "picking a side opens the stake panel")
	var stake: LineEdit = live("PredictionStake")
	stake.text_changed.emit("2000")
	var summary: Label = live("PredictionSummary")
	check(summary.text.contains("$5,000") and summary.text.contains("$8,000"), "summary updates while typing")
	check(stake.is_inside_tree() and alive(stake), "typing does not rebuild the field")
	predictions.review()
	await frames()
	check(live("PredictionConfirm") != null, "confirmation shown in place")
	var original = predictions.confirm.duplicate()
	check(int(original.total) == 5000, "return uses the picked side's odds")
	predictions.set_outcome("lose")
	check(predictions.team_id == "a", "legacy lose on B backs A")
	print("BETTING_INPUT_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
