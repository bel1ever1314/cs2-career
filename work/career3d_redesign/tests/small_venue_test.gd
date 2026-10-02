extends Node
var app
var failures: Array[String]=[]
var checks:=0

func check(ok: bool,label: String) -> void:
	checks+=1
	if not ok:failures.append(label)
	print("VENUE_CHECK ","PASS " if ok else "FAIL ",label)

func frames(count: int) -> void:
	for i in range(count):await get_tree().physics_frame

func walk(point: Vector3) -> bool:
	for i in range(800):
		var delta: Vector3=point-app.player.position;delta.y=0
		if delta.length()<.17:
			app.player.test_direction=Vector3.ZERO;await frames(5);check(true,"walk "+str(point));return true
		app.player.test_direction=delta.normalized();await get_tree().physics_frame
	app.player.test_direction=Vector3.ZERO;check(false,"walk blocked at "+str(app.player.position)+" toward "+str(point));return false

func run(application) -> void:
	app=application;await frames(15)
	check(app.player.is_on_floor(),"spawn supported")
	check(not app.player.visual.visible,"first person hides own head")
	var snapshot: Dictionary=app.diagnostic_snapshot()
	check(snapshot["enclosed"],"roof closes venue")
	var roof_ray:=PhysicsRayQueryParameters3D.create(Vector3(0,1,4),Vector3(0,20,4),1)
	check(not app.get_world_3d().direct_space_state.intersect_ray(roof_ray).is_empty(),"upward ray hits ceiling")
	if snapshot["destination"]=="lan":await _lan()
	else:await _awards()
	var result: Dictionary={"checks":checks,"failures":failures,"scene":app.diagnostic_snapshot()}
	print("SMALL_VENUE_RESULT ",JSON.stringify(result))
	get_tree().quit(0 if failures.is_empty() else 1)

func _lan() -> void:
	check(app.stations.size()==10,"10 computers / 5 vs 5")
	check(app.has_node("GlassDivider") and app.diagnostic_snapshot()["spectators"]==0,"glass divider and no crowd")
	await walk(Vector3(0,0,3.2));check(app.target=="A3","player seat E prompt")
	var origin: Vector3=app.player.position
	app.selected_station=app._station("A3");app.before_computer();app.set_device_open(true,"computer")
	await frames(65)
	check(app.device_seated and app.player.locked and app.camera_owned,"computer owns seated camera")
	var station: Dictionary=app.selected_station
	check(app.camera.position.distance_to(app.vec(station["seat"])+Vector3.UP*1.17)<.03,"camera smoothly reaches monitor view")
	app.set_device_open(false,"computer");await frames(35)
	check(not app.device_seated and not app.player.locked and not app.camera_owned,"close releases seated view")
	check(app.player.position.distance_to(origin)<.04,"close restores standing approach")
	if Computer.has_method("open_app"):
		app.interact();await frames(65)
		check(Computer.screen.visible and Computer.active_page=="career_match" and Computer.location=="lan","E seat transition opens LAN career match app")
		Computer.close_computer();await frames(35)
		check(not CareerBridge.phone_open and not app.device_seated and not app.player.locked,"actual computer close releases devices and seat")
	await walk(Vector3(5.95,0,3.2));await walk(Vector3(5.95,0,-3.2));await walk(Vector3(0,0,-3.2))
	check(app.target=="B3","opposite row reachable through side aisle")
	app.player.position=Vector3(0,.21,2.5);app.player.reset_physics_interpolation();await frames(5)
	app.player.test_direction=Vector3.FORWARD;await frames(80);app.player.test_direction=Vector3.ZERO
	check(app.player.position.z>.9,"cannot walk through desks and divider")
	app.selected_station=app._station("B3");app.before_computer();await frames(65);app.before_phone();app.set_device_open(true,"phone");await frames(35)
	check(not app.device_seated and app.player.locked,"phone hands back seated view and holds movement")
	app.set_device_open(false,"phone")

func _awards() -> void:
	check(app.preview and not app.finalized,"empty career shows labeled preview")
	check("预览" in app.ceremony_banner.text and "预览" in app.caption.text,"preview never claims finalized results")
	check(app.audience_count==50,"all 50 frontline chicken guests")
	var fixture: Dictionary={"ready":true,"finalized":true,"year":2025,"top3":[{"rank":1,"name":"A","player_id":"a"},{"rank":2,"name":"B","player_id":"b"},{"rank":3,"name":"C","player_id":"c"}]}
	check(app._valid_finalized(fixture),"accepts actual finalized top3 contract")
	var roster: Array[Dictionary]=[]
	for winner in fixture["top3"]:roster.append(winner.duplicate(true))
	for i in range(47):roster.append({"name":"A" if i==0 else "Frontline "+str(i),"player_id":"roster_"+str(i)})
	var attendance: Dictionary=app._attendance_plan(roster,fixture["top3"])
	check(int(attendance["total_attendees"])==50 and attendance["crowd_rows"].size()==47 and attendance["recipient_ids"].size()==3,"winner roster IDs occupy recipient seats once with all 50 attendees present")
	var present_ids: Dictionary={}
	for row in attendance["crowd_rows"]:present_ids[str(row["player_id"])]=true
	for id in attendance["recipient_ids"]:present_ids[id]=true
	check(present_ids.size()==50,"crowd plus recipient fixture has 50 unique stable IDs")
	check(present_ids.has("roster_0"),"matching a winner name without its stable ID stays in crowd")
	var ambiguous_winners: Array=fixture["top3"].duplicate(true);ambiguous_winners[1]["player_id"]="a"
	var ambiguous: Dictionary=app._attendance_plan(roster,ambiguous_winners)
	check(not ambiguous["recipient_ids"].has("a"),"ambiguous duplicate winner IDs do not remove a crowd guest")
	fixture["finalized"]=false;check(not app._valid_finalized(fixture),"does not promote live rankings to annual result")
	fixture["finalized"]=true;fixture["top3"][2]["rank"]=2;check(not app._valid_finalized(fixture),"rejects incomplete or duplicate ranks")
	await walk(Vector3(0,0,-3.8));check(app.target=="ceremony","ceremony start reachable")
	await walk(Vector3(0,0,-6.8));check(app.player.position.y>.5,"player walks actual stage steps")
	await walk(Vector3(-3.25,0,-7.45));check(app.player.position.y>.5,"third podium reachable")
	await walk(Vector3(0,0,-6.8));await walk(Vector3(0,0,-3.8))
	app.ceremony_speed=12;app.start_ceremony()
	for i in range(12000):
		if app.ceremony_phase=="finished":break
		await get_tree().physics_frame
	check(app.ceremony_phase=="finished","sequential walk up / award / return completes")
	check(app.called_ranks==[3,2,1] and app.awarded_ranks==[3,2,1] and app.completed_ranks==[3,2,1],"host calls third second first with each recipient returning")
	check(app.player.position.y>-.1,"visitor remains on floor")
	# The player recipient waits for physical walking and an explicit trophy claim.
	fixture["top3"][2]["rank"]=3;fixture["top3"][2]["player_id"]="human_fixture";fixture["top3"][2]["name"]="Actual Career Name"
	fixture["human_id"]="human_fixture";fixture["source"]="season.top20"
	app.ceremony_phase="idle";app._load_awards(fixture)
	check(app.finalized and not app.preview and "Actual Career Name" in app.ranking_board.text,"finalized ceremony shows actual supplied career name")
	app.start_ceremony()
	for i in range(800):
		if app.ceremony_phase=="player_walk":break
		await get_tree().physics_frame
	check(app.ceremony_phase=="player_walk" and app.awarded_ranks.is_empty(),"human recipient is invited without auto awarding")
	await walk(Vector3(0,0,-6.8));await walk(Vector3(-3.25,0,-7.45))
	check(app.target=="award","human trophy claim requires reachable podium")
	app.interact();check(app.ceremony_phase=="player_return" and app.awarded_ranks==[3],"E grants presentation trophy once")
	app.interact();check(app.awarded_ranks==[3],"repeated E does not duplicate trophy")
	await walk(Vector3(0,0,-6.8));await walk(Vector3(0,0,-3.8));await walk(Vector3(0,0,.8))
	for i in range(12000):
		if app.ceremony_phase=="finished":break
		await get_tree().physics_frame
	check(app.ceremony_phase=="finished" and app.completed_ranks==[3,2,1],"human returns on foot and remaining recipients finish")
