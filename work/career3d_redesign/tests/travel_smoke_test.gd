extends Node
var failures: Array[String]=[]
var checks:=0
func check(ok: bool,label: String) -> void:
	checks+=1
	if not ok:failures.append(label)
	print("TRAVEL_CHECK ","PASS " if ok else "FAIL ",label)
func frames(n: int) -> void:
	for i in range(n):await get_tree().physics_frame
func run() -> void:
	await frames(10)
	var club=get_tree().current_scene
	club.interactions.values["focus"]=73
	club.interactions.cooldowns["computer"]=club.interactions.cooldown_clock+8
	club.interactions.completed["computer"]=2
	club.player.position=Vector3(-.75,.23,8.77);club.player.reset_physics_interpolation()
	await frames(10)
	check(Travel.menu_open and not Travel.busy,"walking to club door automatically offers destinations")
	var major_index: int=Travel.menu.destinations.find("major")
	Travel.menu.select_index(major_index)
	Travel.menu.confirm()
	check(Travel.busy,"transition input guarded")
	Travel.go("major") # a held/repeated request must not start a second scene change
	await Travel.arrived
	var arena=get_tree().current_scene
	check(arena.name=="MajorWalk","major scene loaded")
	arena.testing=true;arena.focused=true
	await frames(130)
	check(arena.intro_finished,"third-person to first-person intro completed")
	check(not arena.player.visual.visible,"first person hides character head")
	check(arena.camera.projection==Camera3D.PROJECTION_PERSPECTIVE,"perspective camera")
	check(arena.player.position.y>.4,"spawn floor valid")
	arena.set_paused(true)
	var origin: Vector3=arena.player.position
	Input.action_press("club_up");await frames(20);Input.action_release("club_up")
	check(arena.player.position.distance_to(origin)<.02,"menu blocks movement")
	arena.set_paused(false)
	Input.action_press("club_up");await frames(20);Input.action_release("club_up")
	check(arena.player.position.z<origin.z-.5,"W moves camera-forward")
	await frames(10)
	# Turn camera right and check right-facing W, using production input.
	arena.yaw=-PI/2
	origin=arena.player.position
	Input.action_press("club_up");await frames(20);Input.action_release("club_up")
	check(arena.player.position.x>origin.x+.5,"movement follows mouse yaw")
	Travel.go("club")
	await Travel.arrived
	club=get_tree().current_scene
	check(club.name=="PlayableChickenClub","club scene restored")
	check(int(club.interactions.values["focus"])==73,"session stats retained")
	check(int(club.interactions.completed["computer"])==2,"completion history retained")
	check(club.interactions.cooldowns.has("computer"),"cooldowns retained")
	check(Input.mouse_mode==Input.MOUSE_MODE_VISIBLE,"mouse released in club")
	check(not Travel.busy,"transition guard released")
	var data: Dictionary={"checks":checks,"failures":failures}
	var f:=FileAccess.open("res://temp/travel_test_report.json",FileAccess.WRITE);f.store_string(JSON.stringify(data,"  "))
	print("TRAVEL_RESULT ",JSON.stringify(data))
	get_tree().quit(0 if failures.is_empty() else 1)
