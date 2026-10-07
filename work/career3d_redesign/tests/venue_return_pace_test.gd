extends Node
func _ready() -> void:
	call_deferred("run")

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(1); return
	CareerBridge.set_process(false); Computer.set_process(false); Phone.set_process(false)
	var builder = load("res://tests/venue_match_flow_test.gd").new()
	var venue: Dictionary = builder.venue("major")
	builder.free()
	venue.merge({"match_id":"return-bo", "entry_completed":true, "capacity":100}, true)
	Travel.match_visit = {"match_id":"return-bo", "destination":"major", "venue":venue}
	var scene = load("res://major_walk.tscn").instantiate()
	add_child(scene)
	await get_tree().process_frame
	scene.set_process(false); scene.set_physics_process(false)
	var ready: bool = scene.competition_phase == "ready" and scene.intro_finished
	var seated := 0
	for actor in scene.peers:
		if actor.seat_pose: seated += 1
	var valid: bool = ready and seated == 9 and scene.atmosphere.entrance_count == 0 and scene.player.position.distance_to(scene.player_station.approach) < 0.2
	print("VENUE_RETURN_PACE_RESULT ready=", ready, " seated=", seated, " entrances=", scene.atmosphere.entrance_count, " passed=", valid)
	get_tree().quit(0 if valid else 1)
