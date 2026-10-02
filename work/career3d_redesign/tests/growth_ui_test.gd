extends Node
## Native controls use explicit fixtures, never real career files or CS2.
var failures: Array[String] = []
var checks := 0

func _ready() -> void:
	call_deferred("run")

func check(ok: bool, text: String) -> void:
	checks += 1
	if not ok:
		failures.append(text)
	print("GROWTH_UI_CHECK ", "PASS " if ok else "FAIL ", text)

func settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame

func set_device_open(_opened: bool, _kind: String) -> void:
	pass

func run() -> void:
	get_viewport().size = Vector2i(1280, 720)
	CareerBridge.connected = true
	CareerBridge.clock_held = true
	CareerBridge.context = {
		"date":"2026-03-04", "player":{"id":"fixture-you", "name":"界面测试选手", "role":"rifle", "ability":78},
		"team":{"id":"fixture-team", "name":"界面测试队", "money":12000, "roster":[]},
		"calendar":{"revision":4}, "calendar_events":[], "recent_matches":[], "inbox":[], "stories":[], "money":800,
		"personal":{"attributes":{"firepower":79, "entrying":83, "trading":76, "opening":80, "clutching":71, "sniping":69, "utility":85},
			"axes":["firepower","entrying","trading","opening","clutching","sniping","utility"],
			"axis_labels":{"firepower":"枪法","entrying":"突破","trading":"补枪","opening":"首杀","clutching":"残局","sniping":"狙击","utility":"道具"},
			"attr_points":4,"growth_allowed":true,"growth_reason":"休赛期，可以培养。","form_delta":2,
			"personal_money":800,"club_money":12000,"stats":{"maps":0,"rating":null,"adr":null,"kast":null},"recent":[]},
		"ladder":{"revision":1,"lobby":null,"player":{"elo":1800,"wins":0,"losses":0},"maps":["dust2"],"history":[]},
		"scrims":{"opponents":[],"scheduled":[],"history":[]},"news":[],"teams":[]
	}
	Phone.present("profile")
	Phone._profile_tab("growth")
	await settle()
	var plus = Phone.content.find_child("GrowthPlus_firepower", true, false)
	check(plus != null and not plus.disabled, "phone exposes a real eligible attribute control")
	if plus:
		plus.pressed.emit()
	await settle()
	check(CareerBridge.growth_draft.get("firepower") == 1 and CareerBridge.growth_remaining() == 3, "phone stages points without changing career data")
	check(CareerBridge.context["personal"]["attributes"]["firepower"] == 79, "draft never mutates stored attributes")
	Computer.present("bedroom")
	Computer._navigate("profile", false)
	await settle()
	check(not Phone.screen.visible and CareerBridge.growth_draft.get("firepower") == 1, "computer inherits shared allocation and exclusively owns device")
	check(CareerBridge.growth_adjust("entrying", 1), "second device can continue same draft")
	Phone.present("profile")
	Phone._profile_tab("growth")
	await settle()
	check(CareerBridge.growth_remaining() == 2 and CareerBridge.growth_draft.get("entrying") == 1, "phone sees second device allocation")
	check(not CareerBridge.growth_adjust("unknown", 1), "rejects unknown axis")
	CareerBridge.context["personal"]["attributes"]["sniping"] = 100
	check(not CareerBridge.growth_adjust("sniping", 1), "cannot exceed attribute cap")
	check(CareerBridge.growth_adjust("firepower", -1), "undo affects only draft")
	check(CareerBridge.growth_remaining() == 3, "undo returns available point")
	CareerBridge.context["personal"]["growth_allowed"] = false
	Phone._rebuild()
	await settle()
	plus = Phone.content.find_child("GrowthPlus_firepower", true, false)
	check(not CareerBridge.growth_adjust("firepower", 1) and plus.disabled, "career timing gate controls both logic and UI")
	Phone._busy_changed(false)
	check(plus.disabled, "HTTP completion does not unlock forbidden growth controls")
	var changed := CareerBridge.context.duplicate(true)
	changed["personal"]["attr_points"] = 2
	CareerBridge._apply_context(changed)
	check(CareerBridge.growth_draft.is_empty(), "server updates invalidate draft instead of spending stale points")
	Phone._profile_tab("stats")
	await settle()
	check(Phone.content.get_combined_minimum_size().x <= Phone.scroll.size.x + 1, "personal stats fit phone screen with missing data")
	Phone.close_phone()
	print("GROWTH_UI_RESULT ", JSON.stringify({"checks":checks,"failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
