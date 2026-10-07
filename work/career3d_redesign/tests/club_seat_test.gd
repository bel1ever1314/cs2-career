extends Node
## Local geometry/roster fixtures. No backend or player saves are opened.
var checks := 0
var failures: Array[String] = []

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("CLUB_SEAT_CHECK ", "PASS " if value else "FAIL ", label)

func frames() -> void:
	for i in range(5): await get_tree().physics_frame

func _ready() -> void:
	call_deferred("run")

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(2); return
	CareerBridge.set_process(false); CareerBridge.clock_held = true
	Travel.club_session = {}
	var club = load("res://play.tscn").instantiate()
	add_child(club)
	club.player.test_mode = true; club.life.enabled = false
	var life = club.life
	var computer: Dictionary = {}
	for item in club.interactions.items:
		if item["id"] == "computer": computer = item
	check(computer["seat"] == life.data["sites"]["pc5"]["seat"], "reserved NPC site matches actual player interaction seat")
	check(life.roster.size() == 8 and not life.reservations.has("pc5"), "four teammate stations and four staff leave player station empty at spawn")
	var context := {"player":{"id":"human"}, "team":{"id":"club", "roster":[]}}
	var roles := ["igl", "awp", "entry", "lurker", "rifle"]
	for human_role in range(5):
		context["team"]["roster"] = [{"id":"human", "name":"Human", "role":roles[human_role], "you":true}]
		for i in range(5):
			if i != human_role: context["team"]["roster"].append({"id":"mate%d" % i, "name":"Mate%d" % i, "role":roles[i]})
		life.bind_career(context)
		await frames()
		var valid: bool = life.roster.size() == 8 and not life.reservations.has("pc5")
		for npc in life.roster:
			valid = valid and npc.site_id != "pc5"
			for job in npc.definition["schedule"]: valid = valid and not life._player_site(job[0])
		check(valid, "all five player roles keep pc5 reserved: " + roles[human_role])
	# Old cached scene state may still say a real teammate was in pc5.
	var snapshot: Dictionary = life.snapshot()
	var mate = life.roster[0]
	snapshot["npcs"][mate.npc_id]["site"] = "pc5"
	snapshot["npcs"][mate.npc_id]["position"] = life.data["sites"]["pc5"]["seat"].duplicate()
	snapshot["npcs"][mate.npc_id]["bond"] = 3
	life.restore(snapshot)
	await frames()
	check(mate.site_id != "pc5" and mate.bond == 3 and not life.reservations.has("pc5"), "legacy occupied-seat snapshot relocates teammate but preserves relationship")
	var sites := {}
	var unique := true
	for npc in life.roster:
		if sites.has(npc.site_id): unique = false
		sites[npc.site_id] = true
	check(unique, "legacy fallback does not steal another saved destination")
	# Even an injected/older schedule is not allowed to request the human seat.
	mate.definition["schedule"].insert(mate.schedule_index + 1, ["pc5", 40])
	life._next(mate)
	check(mate.site_id != "pc5" and not life.reservations.has("pc5"), "schedule transition rejects the reserved player station")
	life.bind_career({"player":{"id":"human"}, "team":null})
	await frames()
	life.bind_career(context)
	await frames()
	check(life.roster.size() == 8 and not life.reservations.has("pc5"), "leaving and joining a club regenerates only teammate stations")
	club.player.position = club.interactions.vec(computer["anchor"]); club.player.position.y = .23
	club.player.reset_physics_interpolation()
	await frames()
	check(club.interactions.available(computer), "player can reach and use their computer after roster changes")
	print("CLUB_SEAT_RESULT checks=", checks, " failures=", failures)
	get_tree().quit(0 if failures.is_empty() else 1)
