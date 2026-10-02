extends Node
var app
var failures: Array[String] = []
var checks := 0

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("CHECK ","PASS " if ok else "FAIL ",label)

func frames(count: int) -> void:
	for i in range(count): await get_tree().physics_frame

func walk(x: float,z: float) -> bool:
	var destination:=Vector3(x,.22,z)
	for i in range(600):
		var delta: Vector3=destination-app.player.position
		delta.y=0
		if delta.length()<.12:
			app.player.test_direction=Vector3.ZERO
			await frames(12)
			check(true,"walk %.2f %.2f" %[x,z])
			return true
		app.player.test_direction=delta.normalized()
		app.player.test_run=false
		await get_tree().physics_frame
	app.player.test_direction=Vector3.ZERO
	check(false,"walk %.2f %.2f stopped %s" %[x,z,str(app.player.position)])
	return false

func route(points: Array) -> void:
	for p in points:
		if not await walk(p[0],p[1]): break

func use_item(id: String) -> void:
	var item: Dictionary={}
	for entry in app.interactions.items:
		if entry["id"]==id:item=entry
	check(app.interactions.available(item),"reachable "+id)
	var before: Dictionary=app.interactions.values.duplicate()
	check(app.interactions.start(item),"start "+id)
	if float(item["seconds"])<=0:return
	check(not app.interactions.start(item),"no double start "+id)
	app.interactions.cancel()
	check(app.interactions.values==before and not app.player.locked,"cancel without reward "+id)
	await frames(2)
	var origin: Vector3=app.player.position
	check(app.interactions.start(item),"restart "+id)
	await frames(int(float(item["seconds"])*60)+10)
	check(app.interactions.active.is_empty() and not app.player.locked,"finish "+id)
	check(int(app.interactions.completed.get(id,0))==1,"single completion "+id)
	check(not app.interactions.start(item),"cooldown "+id)
	check(app.player.position.distance_to(origin)<.15,"restore position "+id)

func run(application) -> void:
	app=application
	await frames(20)
	check(app.player.is_on_floor(),"spawn supported")
	check(app.collision_builder.count>40,"furniture and walls built")
	await route([[-1.13,3.85]])
	await use_item("reception")
	await route([[-3.6,4],[-3.6,-.2],[-6.25,-.2],[-6.25,-2.7],[-3.68,-3.67]])
	await use_item("computer")
	await route([[-6.25,-2.7],[-6.25,-.2],[1,-.2],[1,-2.7],[-1.3,-2.7],[-1.3,-7.1],[1,-7.3]])
	await use_item("whiteboard")
	await route([[-1.3,-7.1],[-1.3,-2.7],[1,-2.7],[1,-.2],[8.1,-.2],[8.1,-2.6],[10.43,-2.6],[10.43,-6.82]])
	await use_item("fridge")
	await route([[10.43,-2.6],[8.1,-2.6],[8.1,-.2],[7,-.2],[7,2.1],[5.48,2.26]])
	await use_item("meal")
	await route([[4.1,2.2],[4.1,6.5],[6.13,6.53]])
	await use_item("coffee")
	await route([[4.1,6.5],[4.1,2.2],[7,2.1],[7,-.2],[-7.6,-.2],[-7.6,1.6],[-6,1.6],[-6,4.08],[-8.44,4.08]])
	await use_item("sofa")
	await route([[-6.4,4.08],[-6.4,6.48],[-5.62,6.48]])
	await route([[-6.4,6.48],[-6.4,4.08],[-6,4.08],[-6,1.6],[-7.6,1.6],[-7.6,-.2],[-3.6,-.2],[-3.6,6.4],[1.93,6.4],[1.93,5.07]])
	await use_item("trophy")
	await route([[-.75,6.65],[-.75,8.77]])
	await use_item("exit")
	# Hold into the exterior wall: controller must stop, not walk through.
	app.player.test_direction=Vector3(0,0,1)
	await frames(100)
	app.player.test_direction=Vector3.ZERO
	check(app.player.position.z<9.3,"exterior collision")
	# Same short reach distance but across the lounge/lobby wall.
	app.player.position=Vector3(-4.05,.23,6.48)
	await frames(3)
	var probe: Dictionary={"anchor":[-5.62,.9,6.48]}
	probe["range"]=3.0
	check(not app.interactions.available(probe),"cannot interact through wall")
	for value in app.interactions.values.values():check(value>=0 and value<=100,"stat bounds")
	print("CLUB_TEST_RESULT ",JSON.stringify({"checks":checks,"failures":failures,"completed":app.interactions.completed}))
	var report:=FileAccess.open("res://temp/play_test_report.json",FileAccess.WRITE)
	report.store_string(JSON.stringify({"checks":checks,"failures":failures,"completed":app.interactions.completed},"  "))
	get_tree().quit(0 if failures.is_empty() else 1)
