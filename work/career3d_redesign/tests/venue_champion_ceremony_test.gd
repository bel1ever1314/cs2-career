extends Node
## Frozen result/UI fixtures only. No match, save, service or CS2 is started.
const Ceremony = preload("res://scripts/venue_champion_ceremony.gd")
var checks := 0
var failures: Array[String] = []
var commands: Array = []

class VenueFixture:
	extends Node3D
	var roster_plan: Dictionary = {}
	var seated := true
	var before_phone_calls := 0
	var attendance_captured_before_leave := false
	func match_seated(id: String) -> bool:
		return seated and str(roster_plan.get("match_id", "")) == id
	func before_phone() -> void:
		before_phone_calls += 1
		attendance_captured_before_leave = CareerBridge.feedback.venue_results.has("2026:fixture-event")
		seated = false

func _ready() -> void:
	call_deferred("run")

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("CHAMPION_CEREMONY_CHECK ", "PASS " if value else "FAIL ", label)

func frames() -> void:
	for _index in range(4): await get_tree().process_frame

func result(source: String = "cs2") -> Dictionary:
	return {"id":"final-1", "match_id":"final-1", "result_id":"2026:fixture-event:final-1", "played":true,
		"date":"2026-10-03", "event":"Fixture LAN Final", "team_a":"Our Team", "team_b":"Other Team",
		"player_team":"Our Team", "player_id":"human", "winner":"Our Team", "series":[2,0], "source":source,
		"maps":[{"map":"de_dust2", "score":[13,5], "winner":"Our Team", "players":{}, "source":source}], "totals":[]}

func roster() -> Dictionary:
	var rows: Array = []
	for index in range(5): rows.append({"id":"human" if index == 0 else "ally-" + str(index), "name":"The Player" if index == 0 else "Teammate " + str(index)})
	return {"match_id":"final-1", "own_team":"Our Team", "human_id":"human", "own":rows}

func award() -> Dictionary:
	return {"id":"event-awards:2026:fixture-event:human", "kind":"event_awards", "source":"completed_event.awards",
		"event_id":"2026:fixture-event", "event_engine_id":"fixture-event", "event_name":"Fixture LAN Final",
		"date":"2026-10-03", "participated":true, "quick":false, "own_team":"Our Team", "champion":"Our Team",
		"human_id":"human", "human_name":"The Player", "title":"Fixture LAN Final · 赛事荣誉",
		"mvp":{"player_id":"human", "name":"The Player", "team":"Our Team"}, "evp":[], "five":[]}

func participation(destination: String = "lan", source: String = "cs2") -> Dictionary:
	return {"personal":true, "destination":destination, "stage":"GF", "event_id":"2026:fixture-event",
		"roster":roster(), "result":result(source), "appearance":{}}

func run() -> void:
	get_window().content_scale_size = Vector2i(1280, 720)
	get_window().size = Vector2i(1280, 720)
	check("--no-service" in OS.get_cmdline_user_args(), "isolated no-service test flag is present")
	CareerBridge.connected = false
	CareerBridge.set_process(false)
	CareerBridge.sound_muted = true
	CareerBridge.clock_held = true
	CareerBridge.context = {"player":{"id":"human", "name":"The Player"}, "team":{"name":"Our Team"}, "calendar":{"revision":12}, "avatar":{"appearance":{}}, "stories":[], "feedback":{"items":[]}}
	var feed = CareerBridge.feedback
	feed.set_process(false)
	feed.command_sender = func(path: String, body: Dictionary) -> bool: commands.append({"path":path, "body":body}); return true
	var official := award()
	var original_award := JSON.stringify(official)
	var original_attendance := participation()
	var attendance_text := JSON.stringify(original_attendance)
	var planned := Ceremony.plan(official, original_attendance)
	check(planned.players.size() == 5 and planned.players[2].id == "human", "winning personal final reserves centre for player plus four frozen teammates")
	check(JSON.stringify(official) == original_award and JSON.stringify(original_attendance) == attendance_text, "planning leaves awards results and roster untouched")
	check(not Ceremony.plan(official, participation("major")).is_empty(), "large arena final uses the same ceremony contract")
	check(not Ceremony.plan(official, participation("lan", "simulated")).is_empty(), "simulating from the player's LAN seat also celebrates an official title")
	var automatic := participation()
	automatic.personal = false
	var quick_award := official.duplicate(true)
	quick_award.quick = true
	check(Ceremony.plan(quick_award, automatic).is_empty(), "automatic quick mode does not acquire a physical trophy ceremony")
	check(not Ceremony.plan(quick_award, participation()).is_empty(), "quick-season final personally played from a seat can still lift its trophy")
	var changed := official.duplicate(true)
	changed.champion = "Other Team"
	check(Ceremony.plan(changed, participation()).is_empty(), "losing finalist never lifts the winner's cup")
	changed = official.duplicate(true)
	changed.source = "live_standings"
	check(Ceremony.plan(changed, participation()).is_empty(), "live ranking or nonofficial feedback cannot manufacture a title")
	changed = official.duplicate(true)
	changed.kind = "top20"
	check(Ceremony.plan(changed, participation()).is_empty(), "Top20 awards keep their separate annual ceremony")
	changed = official.duplicate(true)
	changed.event_id = "2026:another-event"
	check(Ceremony.plan(changed, participation()).is_empty(), "another event cannot reuse a physical final's roster")
	var incomplete := participation()
	incomplete.result.played = false
	check(Ceremony.plan(official, incomplete).is_empty(), "winning one map in an incomplete series is not a championship ceremony")
	incomplete = participation()
	incomplete.stage = "SF"
	check(Ceremony.plan(official, incomplete).is_empty(), "a semifinal result cannot trigger the trophy lift")
	incomplete = participation("club")
	check(Ceremony.plan(official, incomplete).is_empty(), "online club match has no physical LAN/arena ceremony")
	incomplete = participation()
	incomplete.roster.own[1].id = "human"
	check(Ceremony.plan(official, incomplete).is_empty(), "duplicate teammate identity cannot populate the champion lineup")
	incomplete = participation()
	incomplete.roster.own.pop_back()
	check(Ceremony.plan(official, incomplete).is_empty(), "incomplete roster is not replaced by invented winners")
	incomplete = participation()
	incomplete.result.player_id = "someone-else"
	check(Ceremony.plan(official, incomplete).is_empty(), "saved participation is bound to this player's actual final")
	var venue := VenueFixture.new()
	venue.name = "ReadOnlyLanFinalFixture"
	venue.scene_file_path = "res://lan.tscn"
	venue.roster_plan = roster()
	get_tree().root.add_child(venue)
	get_tree().current_scene = venue
	var preflight := {"match_id":"final-1", "identity":{"event_id":"2026:fixture-event"}, "stage":"GF", "venue":{"event_id":"2026:fixture-event", "destination":"lan"}}
	Computer.match_center.preflight = preflight.duplicate(true)
	Computer.match_center.last_result = result()
	Computer.match_center.quick_running = false
	var context_before := JSON.stringify(CareerBridge.context)
	feed.present(official)
	var celebration = feed.champion_ceremony
	check(venue.before_phone_calls == 1 and not venue.seated and venue.attendance_captured_before_leave, "real device_open invokes before_phone only after old-final attendance is frozen")
	check(is_instance_valid(celebration) and celebration.active, "already-in-progress frozen seated final triggers without a new local completion marker")
	if not is_instance_valid(celebration): finish(); return
	celebration.set_process(false)
	await frames()
	check(CareerBridge.feedback_active and CareerBridge.phone_open and not feed.entry.is_empty(), "ceremony retains modal world lock until honours are read")
	check(not is_instance_valid(feed.sheet), "trophy lift appears before the MVP/EVP newspaper")
	check(celebration.actors.size() == 5 and celebration.actors[2].npc_id == "human", "actual ceremony creates exactly player and four named teammates")
	check(celebration.actors[2].display_name == "The Player" and celebration.actors[0].display_name == "Teammate 1", "winner cutscene uses frozen player names not anonymous substitutes")
	check(celebration.viewport.own_world_3d and celebration.actors[0].get_world_3d() != venue.get_world_3d(), "ceremony world is separate and cannot displace actual venue actors")
	check(is_instance_valid(celebration.cup) and celebration.cup.name == "ChampionCup" and celebration.cup.find_children("TrophyHandle*", "MeshInstance3D", true, false).size() == 2, "visible cup has bowl stem base and two handles")
	var start_height: float = celebration.cup.position.y
	var sounds_before: int = feed.sound_count
	feed.acknowledge()
	check(commands.is_empty(), "no reward/save/ack mutation is sent while the team is lifting its cup")
	celebration._process(1.7)
	check(not celebration.raised and celebration.continue_button.disabled, "first beat brings teammates to the podium before the trophy lift")
	celebration._process(.35)
	check(celebration.raised and feed.last_sound == "champion" and feed.sound_count == sounds_before + 1, "lifting the cup emits one distinct victory cue")
	celebration._process(1.6)
	if "--champion-capture" in OS.get_cmdline_user_args() and DisplayServer.get_name() != "headless":
		await frames()
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://champion-lift.png")
	check(celebration.cup.position.y > start_height + .4 and celebration.actors[2].left_wing.rotation.x < -2.5, "player visibly raises both wings and its held trophy")
	var grips: Vector3 = celebration.actors[2].left_grip.global_position.lerp(celebration.actors[2].right_grip.global_position, .5)
	check(celebration.cup.global_position.distance_to(grips + Vector3(0, .15, .18)) < .001, "trophy follows real hand grips instead of floating at an imagined human height")
	check(celebration.confetti.visible and celebration.confetti.multimesh.instance_count == 88, "bounded golden confetti starts after the completed lift")
	check(not celebration.continue_button.disabled and celebration.actors[0].left_wing.rotation.x < -1.4, "four teammates cheer and continue becomes available after the lift")
	var viewport_reference: WeakRef = weakref(celebration.viewport)
	var actor_reference: WeakRef = weakref(celebration.actors[2])
	celebration._process(4.5)
	await frames()
	check(not is_instance_valid(feed.champion_ceremony) and is_instance_valid(feed.sheet) and feed.sheet.visible, "ceremony completes automatically into the original honours newspaper")
	check(viewport_reference.get_ref() == null and actor_reference.get_ref() == null, "completed cutscene releases temporary viewport models and actors")
	check(feed.sound_count == sounds_before + 1, "handoff to the newspaper does not double-play the championship sound")
	check(commands.is_empty() and JSON.stringify(CareerBridge.context) == context_before and venue.roster_plan == roster(), "celebration and handoff do not change career evidence real teammates or results")
	feed._release()
	await frames()
	feed.present(official)
	check(not is_instance_valid(feed.champion_ceremony) and is_instance_valid(feed.sheet), "reopening the same title cannot replay its physical trophy lift")
	feed._release()
	await frames()
	feed.reset_for_loaded_career()
	check(feed.venue_results.is_empty() and feed.champion_seen.is_empty() and not CareerBridge.feedback_active, "loading/resetting career clears old title attendance and modal state")
	Computer.match_center.quick_running = true
	feed.present(quick_award)
	check(not is_instance_valid(feed.champion_ceremony) and is_instance_valid(feed.sheet) and feed.last_sound == "champion", "pure quick mode retains readable championship feedback and sound without travelling")
	feed._release()
	Computer.match_center.quick_running = false
	await frames()
	venue.seated = false
	feed.remember_venue_result(result(), preflight)
	check(feed.venue_results.is_empty(), "nonseated scene preview cannot claim personal final attendance")
	venue.seated = true
	Computer.match_center.saved_results.clear()
	Computer.match_center.begin_reveal(result("simulated"))
	check(feed.venue_results.has("2026:fixture-event") and feed.venue_results["2026:fixture-event"].result.source == "simulated", "existing result-reveal hook records a seat-simulated complete final")
	Computer.match_center.result.clear()
	feed.present(official)
	check(is_instance_valid(feed.champion_ceremony) and feed.champion_ceremony.active, "seat-simulated final uses the same physical celebration as the actual-play result")
	var cancelled_viewport: WeakRef = weakref(feed.champion_ceremony.viewport)
	feed.reset_for_loaded_career()
	await frames()
	check(cancelled_viewport.get_ref() == null and not CareerBridge.feedback_active and feed.entry.is_empty(), "career unload during a lift releases temporary models and all modal ownership")
	check(not CareerBridge.owns_service and CareerBridge.endpoint.is_empty() and CareerBridge.runtime_dir.is_empty(), "whole fixture never launches a backend or opens a user save")
	get_tree().current_scene = self
	venue.queue_free()
	finish()

func finish() -> void:
	print("CHAMPION_CEREMONY_RESULT ", JSON.stringify({"checks":checks, "failures":failures, "commands":commands.size()}))
	get_tree().quit(0 if failures.is_empty() else 1)
