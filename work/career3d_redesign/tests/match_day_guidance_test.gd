extends Node
const Guidance = preload("res://scripts/world_match_guidance.gd")
var failures: Array[String] = []
var checks := 0
var requests: Array[Dictionary] = []

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("MATCH_DAY_GUIDANCE ", "PASS " if value else "FAIL ", label)

func context_for(date: String, destination: String, planned: bool = true) -> Dictionary:
	var today := date == "2026-10-04"
	var attendance := {"planned":planned, "match_id":"scheduled-test", "event_name":"Test Invitational", "date":date, "opponent":"Other", "phase":"today" if today else "scheduled", "destination":destination, "display_name":"俱乐部训练室" if destination == "club" else ("测试大场馆" if destination == "major" else "测试线下赛场"), "is_today":today, "due":today, "can_travel":today, "sleep_target":"" if today else date}
	return {"date":"2026-10-04", "nextmatch":{"id":"scheduled-test", "event":"Test Invitational", "date":date, "opponent":"Other", "due":today, "attendance":attendance}}

func _ready() -> void:
	call_deferred("run")

func run() -> void:
	CareerBridge.set_process(false); CareerBridge.connected = false
	await get_tree().process_frame
	CareerBridge.context = {"nextmatch":null, "match_preflight":null}
	Travel._career_changed(); Travel.menu.present("bedroom")
	check(Travel.current_game().is_empty() and Travel.match_guidance().is_empty(), "JSON null next match is a normal empty schedule")
	check(Travel.menu.destinations == ["club", "lan", "major", "awards"], "new career and season-end null schedule keeps ordinary travel menu")
	check(not Travel.match_visit_current() and not Travel.go_match({"destination":"major", "travel_allowed":true, "identity_source":"frozen_match_rosters"}, "missing"), "no scheduled match grants neither attendance nor seat permission")
	CareerBridge.context = context_for("2026-10-06", "major")
	Travel._career_changed()
	Travel.menu.present("bedroom")
	check(Travel.menu.destinations[0] == "major" and Travel.menu.selected == 0, "planned venue is first and selected at home door")
	var future_row := Travel.menu.buttons[0].text
	check("测试大场馆" in future_row and "Test Invitational" in future_row and "Other" in future_row, "door names actual venue, event and opponent")
	check("2026-10-06" in future_row and "比赛日再来" in future_row, "future venue gives date rather than inviting early start")
	check("手机日历睡到比赛当天" in Guidance.journey_text(Travel.match_guidance()), "world reminder explains how to reach match morning")
	var source := {"destination":"major", "match_id":"scheduled-test", "travel_allowed":true, "identity_source":"frozen_match_rosters"}
	var before := CareerBridge.context.duplicate(true)
	check(not Travel.go_match(source, "scheduled-test"), "frozen-looking visit cannot start before match date")
	check(before == CareerBridge.context and not Travel.busy and Travel.match_visit.is_empty(), "early visit leaves date, context and scene unchanged")
	Travel.match_visit = {"match_id":"scheduled-test", "destination":"major", "venue":source}
	Travel._career_changed()
	check(Travel.match_visit.is_empty(), "stale early scene snapshot does not grant a seat")
	CareerBridge.context = context_for("2026-10-04", "major")
	Travel._career_changed()
	Travel.menu.present("bedroom")
	check("今日比赛" in Travel.menu.buttons[0].text and "到场准备" in Travel.menu.buttons[0].text, "match day door clearly asks player to attend")
	check("走到门口" in Guidance.journey_text(Travel.match_guidance()) and "测试大场馆" in Guidance.journey_text(Travel.match_guidance()), "morning world reminder points to named destination")
	Travel.menu.present("major")
	check(Travel.menu.destinations[0] == "major", "already visiting venue preview can prepare current match from door")
	Travel.match_visit = {"match_id":"scheduled-test", "destination":"major", "venue":source}
	check(Travel.match_visit_current("major"), "today's frozen visit remains linked to scheduled match")
	Travel.menu.present("major")
	check("major" not in Travel.menu.destinations, "prepared venue does not offer a duplicate team entrance")
	CareerBridge.context["nextmatch"]["attendance"]["phase"] = "in_progress"
	CareerBridge.context["nextmatch"]["attendance"]["can_travel"] = false
	CareerBridge.context["nextmatch"]["attendance"]["can_return"] = true
	CareerBridge.context["match_preflight"] = {"match_id":"scheduled-test", "venue":source.duplicate(true)}
	Travel._career_changed()
	check(not Travel.match_visit.is_empty() and Travel.match_visit_current("major"), "series already underway preserves existing seat identity")
	check(Travel.can_visit_match(source, "scheduled-test"), "same-day unfinished series can return using unchanged frozen venue")
	var changed_roster := source.duplicate(true); changed_roster["players_a"] = [{"id":"replacement"}]
	check(not Travel.can_visit_match(changed_roster, "scheduled-test"), "return cannot replace frozen roster with a new selection")
	check(not Travel.can_visit_match(source, "other-id"), "return cannot attach to another match ID")
	CareerBridge.context["date"] = "2026-10-05"
	check(not Travel.can_visit_match(source, "scheduled-test"), "next-day return never opens new attendance on an old date")
	CareerBridge.context = context_for("2026-10-04", "club")
	Travel._career_changed(); Travel.menu.present("bedroom")
	check(Travel.menu.destinations[0] == "club" and "俱乐部训练室" in Travel.menu.buttons[0].text, "online match points to training room instead of fictitious arena")
	check("训练室" in Guidance.journey_text(Travel.match_guidance()), "online world reminder explains which computer to use")
	Travel.menu.present("club")
	check("club" not in Travel.menu.destinations, "online player already at club uses computer without a scene restart")
	CareerBridge.context = context_for("2026-10-04", "major", false)
	Travel._career_changed(); Travel.menu.present("bedroom")
	check(Travel.menu.destinations[0] == "major" and not Guidance.journey_text(Travel.match_guidance()).is_empty(), "today's real match is visible even without a prior personal-play plan")
	check(not bool(Travel.match_guidance().get("planned", false)), "today reminder does not silently choose personal play for the user")
	Computer.match_center.command_sender = func(path: String, body: Dictionary): requests.append({"path":path, "body":body}); return false
	Travel.menu_open = true
	Travel._confirm_menu("major")
	check(requests.size() == 1 and requests[0]["path"] == "/api/3d/match/preflight" and requests[0]["body"].get("match_id") == "scheduled-test", "door confirmation prepares the correct match without requiring a prior plan")
	check(not Travel.menu_open and not Travel.busy and CareerBridge.context["date"] == "2026-10-04", "door preparation waits for preflight instead of silently travelling or changing dates")
	Computer.match_center.command_sender = Callable()
	CareerBridge.context = context_for("2026-10-06", "major", false)
	Travel._career_changed(); Travel.menu.present("bedroom")
	check(Travel.menu.destinations == ["club", "lan", "major", "awards"], "unplanned next match does not commandeer default door selection")
	check(Guidance.journey_text(Travel.match_guidance()).is_empty(), "future attendance reminder only follows player's chosen plan")
	CareerBridge.context["nextmatch"]["attendance"]["match_id"] = "stale-id"
	check(Travel.match_guidance().is_empty(), "another match's plan cannot hijack current venue")
	Travel.menu.dismiss()
	var report := {"checks":checks, "failures":failures, "cs2_launches":0}
	print("MATCH_DAY_GUIDANCE_RESULT ", JSON.stringify(report))
	get_tree().quit(0 if failures.is_empty() else 1)
