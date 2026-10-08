extends Node
## Career progression page without a due match: next-fixture card, results
## elsewhere accumulating per step, headlines, and hand-back on match day.
const DeviceProjection = preload("res://scripts/device_projection.gd")
var checks := 0
var failures: Array[String] = []
var sent: Array = []

func _ready() -> void:
	call_deferred("run")

func check(value: bool, text: String) -> void:
	checks += 1
	if not value: failures.append(text)
	print("WORLD_FEED_CHECK ", "PASS " if value else "FAIL ", text)

func capture(path: String, body: Dictionary) -> bool:
	sent.append({"path":path, "body":body.duplicate(true)})
	return true

func result(id: String, a: String, b: String, series: Array, day: String, tag: String = "") -> Dictionary:
	return {"id":id, "event_id":"e1", "event":"Cup", "stage":"GS", "date":day, "team_a":a, "team_b":b, "series":series,
		"winner":a if series[0] > series[1] else b, "rank_a":3, "rank_b":12, "upset":tag == "upset", "tag":tag}

func world(today: String, day: String, rows: Array, news: Array = []) -> Dictionary:
	return {"date":today, "results_date":day, "results":rows, "news":news}

func texts(node: Node) -> String:
	var out := PackedStringArray()
	for label in node.find_children("*", "Label", true, false):
		if alive(label): out.append(label.text)
	return " | ".join(out)

## Rebuilds free the old page at the end of the frame; count the live page only.
func alive(node: Node) -> bool:
	while node != null:
		if node.is_queued_for_deletion(): return false
		node = node.get_parent()
	return true

func live(name: String) -> Array:
	return Computer.content.find_children(name, "", true, false).filter(alive)

func buttons(container: String) -> Array:
	var found := live(container)
	return [] if found.is_empty() else found[0].get_children().filter(func(n): return n is Button)

func rows() -> Array:
	return buttons("WorldFeedResults")

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(1); return
	CareerBridge.set_process(false); Computer.set_process(false); Phone.set_process(false)
	CareerBridge.connected = true; CareerBridge.busy = false; CareerBridge.clock_held = true
	Locale.set_language("zh-CN", false)
	scene_file_path = "res://play.tscn"
	get_viewport().size = Vector2i(1280, 720)
	var day1 := [result("r1", "Spirit", "FURIA", [2, 1], "2026-07-20", "opponent"), result("r2", "Falcons", "MOUZ", [0, 2], "2026-07-20", "event"),
		result("r3", "Lynn Vision", "Natus Vincere", [2, 0], "2026-07-20", "upset"), result("r4", "G2", "Aurora", [2, 1], "2026-07-20")]
	var news := [{"id":"n1", "date":"2026-07-19", "kind":"champion", "event":"Esports World Cup", "champion":"Spirit", "mvp":"donk", "title":"x", "category":"awards"},
		{"id":"n2", "date":"2026-07-18", "kind":"news", "title":"G2 官宣新阵容", "title_en":"G2 announce a new lineup", "category":"transfer"}]
	CareerBridge.context = {"date":"2026-07-21", "calendar":{"revision":3}, "player":{"id":"p", "name":"P"}, "team":{"name":"Vitality"}, "stories":[],
		"quick":{"unified_pace":true, "year":2026, "season_phase":"running"},
		"nextmatch":{"id":"m9", "due":false, "date":"2026-07-25", "opponent":"Spirit", "event":"Cup", "stage":"QF", "best_of":3, "attendance":{"destination":"lan"}},
		"match_preflight":{}, "world":world("2026-07-21", "2026-07-20", day1, news)}
	var center = Computer.match_center
	center.command_sender = capture
	center.preflight.clear(); center.result.clear(); center.request_pending = false
	center.pace.flow.reset(); center.pace.world.reset()
	Computer.open_app("quick", "club")
	await get_tree().process_frame
	var card: Node = Computer.content.find_child("WorldFeedNext", true, false)
	check(card != null, "not-due fixture shows the next-match card instead of the match hero")
	check(card != null and texts(card).contains("还有 4 天") and texts(card).contains("Spirit"), "card names the opponent and days left")
	check(Computer.content.find_child("WorldFeedMatch", true, false) != null and Computer.content.find_child("WorldFeedAttend", true, false) != null, "card links to match details and keeps attending in person")
	print("DBG rows ", rows().size(), " heads ", buttons("WorldFeedNews").size(), " all ", Computer.content.find_children("WorldResult", "", true, false).size())
	check(rows().size() == 4, "latest result day is listed")
	check(texts(rows()[0]).contains("Spirit") and texts(rows()[0]).contains("下一个对手"), "next opponent's result comes first and is tagged")
	check(texts(Computer.content).contains("爆冷"), "upset is tagged")
	check(rows()[0].pressed.get_connections().size() > 0, "result rows open the match report")
	check(buttons("WorldFeedNews").size() == 2, "headlines listed")
	check(texts(Computer.content).contains("Spirit 夺冠 · Esports World Cup") and texts(Computer.content).contains("MVP donk"), "champion headline composed from structured fields")
	check(center.pace.plan().title.contains("还有 4 天"), "dock title shows days to the next match")
	# Rebuilding the same day does not duplicate rows.
	Computer._rebuild(); await get_tree().process_frame
	check(rows().size() == 4, "repaint keeps rows unique")
	# A season run in flight keeps the feed; it does not flip to the match hero.
	center.request_pending = true; center.pending_action = "run"
	Computer._rebuild(); await get_tree().process_frame
	check(not live("WorldFeedNext").is_empty(), "season run request keeps the feed on screen")
	center.request_pending = false; center.pending_action = ""
	# Next step: a new day prepends, older day stays below, capped.
	var before := DeviceProjection.signature("quick", CareerBridge.context)
	CareerBridge.context.date = "2026-07-22"
	CareerBridge.context.world = world("2026-07-22", "2026-07-22", [result("r5", "Vitality", "Liquid", [2, 0], "2026-07-22"), result("r6", "FaZe", "Astralis", [1, 2], "2026-07-22"), result("r1", "Spirit", "FURIA", [2, 1], "2026-07-20")], news)
	check(DeviceProjection.signature("quick", CareerBridge.context) != before, "world changes repaint the progression page")
	Computer._rebuild(); await get_tree().process_frame
	check(rows().size() == 6, "new results are added and the list is capped")
	check(texts(rows()[0]).contains("Liquid") and not texts(rows()[rows().size() - 1]).contains("Lynn Vision"), "newest day first, oldest dropped")
	check(texts(Computer.content).contains("07/20") and texts(Computer.content).contains("最新 · 07/22"), "older day is labelled under the latest")
	# Loading an earlier save starts a fresh list.
	CareerBridge.context.date = "2026-03-01"
	CareerBridge.context.world = world("2026-03-01", "", [], [])
	Computer._rebuild(); await get_tree().process_frame
	check(rows().is_empty() and texts(Computer.content).contains("其他队伍最近还没有赛果"), "earlier date resets the list and explains the empty state")
	# An older service without the field and no fixture.
	CareerBridge.context.erase("world"); CareerBridge.context.nextmatch = {}
	Computer._rebuild(); await get_tree().process_frame
	check(texts(Computer.content).contains("暂无已安排的比赛"), "no fixture shows a clear placeholder")
	# Match day hands the page back to match preparation.
	CareerBridge.context.world = world("2026-07-25", "2026-07-24", day1, news)
	CareerBridge.context.nextmatch = {"id":"m9", "due":true, "date":"2026-07-25", "opponent":"Spirit", "event":"Cup", "best_of":3, "attendance":{"destination":"club"}}
	CareerBridge.context.match_preflight = {"match_id":"m9", "map_key":"2026:cup:m9:0", "due":true, "maps_done":0, "team_a":"Vitality", "team_b":"Spirit", "phase":"ready", "venue":{"entry_completed":true}, "veto":{}, "pending_map":null}
	Computer._rebuild(); await get_tree().process_frame
	check(live("WorldFeedNext").is_empty() and rows().is_empty(), "due match replaces the feed with match preparation")
	# English
	CareerBridge.context.nextmatch.due = false; CareerBridge.context.match_preflight = {}
	CareerBridge.context.date = "2026-07-24"
	Locale.set_language("en", false)
	Computer._rebuild(); await get_tree().process_frame
	var english := Locale.english(texts(Computer.content).replace(" | ", "\n"))
	check(english.contains("Tomorrow") and english.contains("Around the scene") and english.contains("Next opponent"), "feed is translated")
	Locale.set_language("zh-CN", false)
	check(sent.is_empty(), "rendering the feed never sends commands")
	print("WORLD_FEED_RESULT checks=", checks, " failures=", failures.size())
	get_tree().quit(0 if failures.is_empty() else 1)
