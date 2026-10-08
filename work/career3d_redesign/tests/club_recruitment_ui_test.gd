extends "res://tests/market_supplies_ui_test.gd"

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(2); return
	CareerBridge.set_process(false); Computer.set_process(false)
	CareerBridge.connected = true; CareerBridge.busy = false
	CareerBridge.context = {"calendar":{"revision":0}, "start":{"creation_required":false}, "personal_money":3000000}
	var player := {"player_id":"new", "name":"Prospect", "role":"rifle", "age":19, "ability":78, "potential":91, "potential_stars":5, "guaranteed_fee":175000, "normal_fee":152000, "normal_chance":.7, "negotiation_fee":3040, "monthly_salary":7230, "blocked":""}
	var candidate := {"replace_id":"old", "name":"Existing player", "ability":90, "recent_rating":1.30, "recent_maps":15, "chance":.43,
		"tenure_bonus":.20, "ability_bonus":.24, "teammate_modifier":-.12, "form_modifier":-.24, "quote_id":"fixture"}
	for language in ["zh-CN", "en"]:
		Locale.set_language(language, false)
		for dimensions in [Vector2i(960,540), Vector2i(1920,1080)]:
			get_window().size = dimensions
			CareerBridge.context.transfers = {"club_browsable":true, "club_allowed":false, "club_money":3000000, "transfer_budget":2940000, "operating_reserve":60000,
				"roster":[{"player_id":"old", "name":"Existing player", "role":"rifle", "ability":90},{"player_id":"other", "name":"Other player", "role":"awp", "ability":80}], "players":[player],
				"recruitment":{"required":true, "available":true, "tenure_days":200, "ability":95, "candidates":[candidate], "grant":null}}
			Computer.business.replace_id = "old"
			Computer.business.transfer_source = "free"
			Computer.business.recruitment.pending.clear()
			Computer.open_app("transfers")
			await frames()
			var panel = Computer.content.find_child("ClubRecruitmentPanel", true, false)
			check(panel != null, "employee can browse and discuss recruitment " + language + str(dimensions))
			check(Computer.content.find_child("TransferGuaranteed_new", true, false).disabled, "approval required before buying")
			check(Computer.content.get_global_rect().end.x <= Computer.panel.get_global_rect().end.x, "discussion fits monitor")
			Computer.content.find_child("RecruitmentPropose", true, false).pressed.emit()
			await frames()
			check(Computer.content.find_child("RecruitmentConfirm", true, false) != null, "discussion has confirmation")
			check(Computer.business.recruitment.pending == {"replace_id":"old","quote_id":"fixture"}, "confirmation binds outgoing player and quote")
			Computer.scroll.ensure_control_visible(Computer.content.find_child("RecruitmentConfirm", true, false))
			await frames()
			await snapshot("recruitment-" + language + "-" + str(dimensions.x))
			CareerBridge.context.transfers.club_allowed = true
			CareerBridge.context.transfers.recruitment.grant = {"replace_id":"old", "name":"Existing player"}
			Computer._rebuild()
			await frames()
			check(not Computer.content.find_child("TransferGuaranteed_new", true, false).disabled, "approved teammate enables signing")
			Computer.content.find_child("ComputerTransferReplace", true, false).item_selected.emit(1)
			await frames()
			check(Computer.content.find_child("TransferGuaranteed_new", true, false).disabled, "cannot use approval for another teammate")
			Computer.content.find_child("RecruitmentUseGrant", true, false).pressed.emit()
			await frames()
			check(Computer.business.replace_id == "old", "return to approved teammate")
			CareerBridge.context.transfers.recruitment.grant = null
			CareerBridge.context.transfers.recruitment.available = false
			CareerBridge.context.transfers.recruitment.reason = "下次可商量日期：2026-07-22"
			Computer.business.recruitment.pending.clear()
			Computer._rebuild()
			await frames()
			check(Computer.content.find_child("RecruitmentPropose", true, false).disabled, "discussion cooldown is visible and blocks resubmission")
	print("RECRUITMENT_UI_RESULT checks=", checks, " failures=", failures)
	get_tree().quit(0 if failures.is_empty() else 1)
