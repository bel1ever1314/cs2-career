extends Node
var checks := 0
var failures: Array[String] = []

func _ready() -> void: call_deferred("run")

func check(value: bool, caption: String) -> void:
	checks+=1
	if not value: failures.append(caption)
	print("MARKET_UI ","PASS " if value else "FAIL ",caption)

func frames() -> void:
	for i in range(5): await get_tree().process_frame

func inject(value: Dictionary) -> void:
	var market=Computer.native_market
	market.finished(market.request_path,{"ok":true,"market":value,"state_revision":0})

func snapshot(name_value: String) -> void:
	if not "--capture-market" in OS.get_cmdline_user_args(): return
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute("res://temp")
	get_viewport().get_texture().get_image().save_png("res://temp/"+name_value+".png")

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(2); return
	CareerBridge.set_process(false)
	CareerBridge.context={"calendar":{"revision":0},"start":{"creation_required":false},"skins":{"personal_money":100000,"cases":[],"inventory":[]}}
	Computer.set_process(false)
	Computer.open_app("market")
	var row={"id":"ak-redline","name":"AK-47 | Redline","weapon":"AK-47","wear_id":"ft","rarity":"classified","spot":2400,"change_1":2.2,"change_7":null,"change_30":null,"art_path":""}
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--market-art="): row.art_path=arg.trim_prefix("--market-art=")
	var fixture={"rows":[row,row,row],"total":150,"slots":["ak47","awp"],"rarities":["classified","covert"],"wears":[{"id":"ft","name":"久经沙场"}],"fee":.1}
	for language in ["zh-CN","en"]:
		Locale.set_language(language,false)
		for dimensions in [Vector2i(960,540),Vector2i(1920,1080)]:
			get_window().size=dimensions
			Computer._market_tab("market")
			inject(fixture)
			await frames()
			var grid=Computer.content.find_child("MarketListings",true,false)
			check(grid!=null,"paginated grid renders "+language+str(dimensions))
			check(Computer.content.get_global_rect().end.x<=Computer.panel.get_global_rect().end.x,"market width fits monitor "+language+str(dimensions))
			await snapshot("market-"+language+"-"+str(dimensions.x))
			Computer.native_market.advanced_filters=true
			Computer._rebuild()
			await frames()
			check(Computer.content.get_global_rect().end.x<=Computer.panel.get_global_rect().end.x,"advanced filters fit monitor")
			Computer.native_market.advanced_filters=false
			Computer.native_market.open_detail(row)
			var item=row.duplicate(true)
			item.merge({"min_float":.15,"max_float":.38,"quantity":3,"cost":7200,"profit":-720,"history":[{"date":"2026-01-08","price":2400},{"date":"2026-01-09","price":2450}]},true)
			inject({"item":item})
			await frames()
			check(Computer.content.get_global_rect().end.x<=Computer.panel.get_global_rect().end.x,"detail chart fits monitor")
			Computer.native_market.ask("buy",{"id":"ak-redline","quantity":3,"expected_total":7200},"3 · $7200")
			await frames()
			check(Computer.content.find_child("MarketConfirmation",true,false)!=null,"confirmation exists before purchase")
			await snapshot("market-detail-"+language+"-"+str(dimensions.x))
			Computer._market_tab("merchant")
			var offers := [{"kind":"bullish","price":750,"purchased":false,"available":true}, {"kind":"bearish","price":750,"purchased":false,"available":false}]
			inject({"offers":offers,"skills":[],"rumors":[]})
			await frames()
			var bull = Computer.content.find_child("MarketBuyBullish",true,false)
			var bear = Computer.content.find_child("MarketBuyBearish",true,false)
			check(bull != null and bear != null and bear.disabled,"two rumor types and empty holdings gate "+language+str(dimensions))
			bull.pressed.emit()
			await frames()
			check(Computer.native_market.confirmation.get("body",{}).get("kind","") == "bullish","bullish confirmation carries the chosen type")
			check(Computer.content.get_global_rect().end.x<=Computer.panel.get_global_rect().end.x,"rumor offers and confirmation fit monitor")
			await snapshot("market-rumor-types-"+language+"-"+str(dimensions.x))
			Computer.native_market.confirmation.clear()
			offers[0].purchased=true
			offers[1].available=true
			Computer.native_market.cache.offers=offers
			Computer._rebuild()
			await frames()
			check(Computer.content.find_child("MarketBuyBullish",true,false).disabled,"buying one type locks that slot")
			Computer.content.find_child("MarketBuyBearish",true,false).pressed.emit()
			await frames()
			check(Computer.native_market.confirmation.get("body",{}).get("kind","") == "bearish","bearish confirmation carries the chosen type")
			Computer.native_market.confirmation.clear()
			CareerBridge.context["transfers"]={"club_allowed":false,"club_browsable":true,"club_money":500000,"transfer_budget":455000,"operating_reserve":45000,"monthly_net":10000,"roster":[{"player_id":"old","name":"Existing player","role":"rifle","ability":70}],"players":[{"player_id":"new","name":"Prospect","role":"rifle","age":19,"ability":78,"potential":91,"potential_stars":5,"guaranteed_fee":175000,"normal_fee":152000,"normal_chance":.7,"negotiation_fee":3040,"monthly_salary":7230,"blocked":"赛事进行中，结束后再转会。"}]}
			Computer._navigate("transfers")
			await frames()
			var talent = Computer.content.find_child("TransferPotential",true,false)
			check(talent != null and talent.text.contains("★★★★★") and talent.tooltip_text.is_empty(),"known potential retains actual stars")
			CareerBridge.context.transfers.players[0].potential_estimated=true
			Computer._rebuild()
			await frames()
			talent = Computer.content.find_child("TransferPotential",true,false)
			check(talent != null and not talent.tooltip_text.is_empty() and talent.text.contains("estimate" if language=="en" else "估算"),"estimated potential explicitly labelled")
			check(Computer.content.get_global_rect().end.x<=Computer.panel.get_global_rect().end.x,"transfer budget and potential fit monitor "+language+str(dimensions))
			await snapshot("market-transfers-"+language+"-"+str(dimensions.x))
			Computer.open_app("market")
	Computer._market_tab("custody")
	var lot=row.duplicate(true)
	lot.merge({"lot_id":"inv.1","quantity":3,"cost":7200,"profit":-720},true)
	inject({"rows":[lot],"total":1,"fee":.1})
	await frames()
	check(Computer.content.find_child("MarketListings",true,false)!=null,"custody has withdraw and sell controls")
	Computer._market_tab("supplies")
	var market=Computer.native_market
	market.finished(market.request_path,{"ok":true,"state_revision":0,"supplies":{"catalog":[{"axis":"sniping","name":"狙击","grade":"strong","bonus":5,"price":5000,"days":7}],"stock":[],"players":[{"id":"one","name":"Test"}],"targets":[],"money":100000,"club_money":80000,"club_allowed":true}})
	await frames()
	check(Computer.content.get_child_count()>4,"supplies shop and player controls render")
	await snapshot("market-supplies")
	print("MARKET_UI_RESULT ",JSON.stringify({"checks":checks,"failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
