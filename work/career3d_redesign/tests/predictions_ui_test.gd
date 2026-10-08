extends Node
var checks := 0
var failures: Array[String] = []

func _ready() -> void: call_deferred("run")
func check(value: bool, caption: String) -> void:
	checks += 1
	if not value: failures.append(caption)
	print("PREDICTION_UI ", "PASS " if value else "FAIL ", caption)
func frames() -> void:
	for i in range(6): await get_tree().process_frame
func inject(value: Dictionary) -> void:
	var predictions = Computer.predictions
	predictions.finished(predictions.pending, {"ok":true, "state_revision":0, "predictions":value})
func snapshot(label: String) -> void:
	if not "--capture-market" in OS.get_cmdline_user_args(): return
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute("res://temp")
	get_viewport().get_texture().get_image().save_png("res://temp/" + label + ".png")
func run() -> void:
	CareerBridge.set_process(false)
	Computer.set_process(false)
	CareerBridge.context = {"calendar":{"revision":0}, "personal_money":10000, "start":{"creation_required":false}, "skins":{"personal_money":10000}}
	var offer = {"key":"2026:cup:match", "quote_id":"test", "year":2026, "event_name":"ESL Challenger League Season 51 Asia-Pacific Cup", "date":"2026-01-08", "best_of":3, "team_a":{"id":"a", "name":"Team Spirit"}, "team_b":{"id":"b", "name":"Vitality"}, "odds_hundredths":{"a":190,"b":190}}
	for language in ["zh-CN", "en"]:
		Locale.set_language(language, false)
		for dimensions in [Vector2i(960,540), Vector2i(1920,1080)]:
			get_window().size = dimensions
			Computer.open_app("events")
			Computer._events_tab("predictions")
			Computer.predictions.switch_tab("available")
			inject({"rows":[offer], "money":10000, "total":1})
			await frames()
			check(Computer.content.find_child("PredictionChoose", true, false) != null, "fixture choice exists")
			check(Computer.content.get_global_rect().end.x <= Computer.panel.get_global_rect().end.x, "fixtures fit " + language + str(dimensions))
			Computer.predictions.select(offer)
			Computer.predictions.amount = "10000"
			Computer.predictions.review()
			await frames()
			check(Computer.content.find_child("PredictionConfirm", true, false) != null, "confirmation and totals visible")
			check(Computer.predictions.confirmation_button.get_global_rect().end.y <= Computer.scroll.get_global_rect().end.y, "confirm scrolled into view")
			check(Computer.content.get_global_rect().end.x <= Computer.panel.get_global_rect().end.x, "confirmation fits")
			await snapshot("prediction-" + language + str(dimensions.x))
			Computer.open_app("market")
			Computer._market_tab("merchant")
			var market = Computer.native_market
			var rumor = {"id":"today", "name":"AK-47 | Redline", "direction":1, "date":"2026-01-08", "expires":"2026-01-11", "reliability":"50–80%", "outcome_pct":null, "detail_target":{"id":"ak-redline","wear_id":"ft"}}
			market.finished(market.request_path, {"ok":true, "market":{"purchased":true, "skills":[], "rumors":[rumor]}})
			await frames()
			check(Computer.content.find_child("MarketRumorOpen", true, false) != null, "rumor has direct link")
			market.open_rumor(rumor)
			market.finished(market.request_path, {"ok":true, "market":{"item":{"id":"ak-redline", "name":"AK-47 | Redline", "weapon":"AK-47", "wear_id":"ft", "rarity":"classified", "spot":2400, "min_float":.15, "max_float":.38, "quantity":0, "history":[]}}})
			await frames()
			check(Computer.content.find_child("MarketBack", true, false) != null, "merchant switches to item detail")
			check(not market.source_rumor.is_empty(), "detail retains rumor")
			await snapshot("rumor-detail-" + language + str(dimensions.x))
			market.back_to_list()
			check(Computer.market_tab == "merchant" and market.selected.is_empty(), "returns to rumor log")
	print("PREDICTION_UI_RESULT ", JSON.stringify({"checks":checks,"failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
