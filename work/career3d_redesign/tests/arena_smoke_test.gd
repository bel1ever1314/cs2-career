extends Node
var app
var checks:=0
var failures: Array[String]=[]
func check(ok: bool,label: String) -> void:
	checks+=1
	if not ok:failures.append(label)
	print("ARENA_CHECK ","PASS " if ok else "FAIL ",label)
func frames(count: int) -> void:
	for i in range(count):await get_tree().physics_frame
func walk(x: float,z: float) -> bool:
	var destination:=Vector3(x,0,z)
	for i in range(1400):
		var delta: Vector3=destination-app.player.position;delta.y=0
		if delta.length()<.18:
			app.player.test_direction=Vector3.ZERO
			await frames(15)
			check(true,"walk %.1f %.1f height %.3f" %[x,z,app.player.position.y]);return true
		app.player.test_run=true;app.player.test_direction=delta.normalized()
		await get_tree().physics_frame
	app.player.test_direction=Vector3.ZERO
	for i in range(app.player.get_slide_collision_count()):
		var impact=app.player.get_slide_collision(i)
		print("ARENA_BLOCKED_BY ",impact.get_collider().name," at ",impact.get_position()," normal ",impact.get_normal())
	check(false,"walk %.1f %.1f stopped %s" %[x,z,str(app.player.position)])
	return false
func run(application) -> void:
	app=application
	await frames(20)
	check(app.player.is_on_floor(),"spawn on hall floor")
	check(app.intro_finished and not app.player.visual.visible,"first person hides own head")
	var atmosphere=app.atmosphere
	var snapshot: Dictionary=atmosphere.diagnostic_snapshot()
	check(snapshot["closed_roof"] and snapshot["upper_walls"],"closed roof and upper enclosure")
	var redesign=load("res://tests/arena_redesign_checks.gd").new()
	for item in redesign.evaluate(app):check(bool(item["ok"]),str(item["label"]))
	var roof_ray:=PhysicsRayQueryParameters3D.create(Vector3(1.3,2,15),Vector3(1.3,40,15),1)
	var roof_hit: Dictionary=app.get_world_3d().direct_space_state.intersect_ray(roof_ray)
	var portal_ray:=PhysicsRayQueryParameters3D.create(Vector3(0,1.8,40),Vector3(0,1.8,58),1)
	check(app.get_world_3d().direct_space_state.intersect_ray(portal_ray).is_empty(),"enclosure keeps the physical public portal open")
	check(not roof_hit.is_empty() and roof_hit["position"].y>25,"interior upward ray hits enclosed roof")
	var saved_volume: float=atmosphere.master_volume
	atmosphere.set_muted(true)
	var silence:=true
	for layer in atmosphere.diagnostic_snapshot()["audio_layers"].values():
		if float(layer["volume_db"])>-79:silence=false
	check(silence,"mute silences all four layers")
	atmosphere.set_master_volume(.25);atmosphere.set_muted(false)
	check(is_equal_approx(atmosphere.master_volume,.25),"master volume is externally adjustable")
	atmosphere.set_master_volume(saved_volume)
	var passage_energy:=0.0
	for p in [[0,52],[0,45],[0,35],[0,25],[0,16],[0,4],[0,1.6]]:
		if not await walk(p[0],p[1]):break
		if p[1]==35:passage_energy=app.env.ambient_light_energy
	check(app.zone(app.player.position).begins_with("内场"),"continuous entry to bowl")
	# The redesign deliberately keeps the bowl dim; readability now comes
	# from dedicated stage/face/aisle lights, not a globally bright audience.
	check(app.env.ambient_light_energy>passage_energy+.10 and app.env.ambient_light_energy<.25,"passage opens to dim bowl with focused bright stage")
	check(atmosphere.entrance_count==1,"crossing the portal cues entrance music and cheer once")
	check(not app.current_point.is_empty() and app.current_point["id"]=="trophy","trophy prompt")
	# Stay outside the solid runway; go around the audience bank to stage steps.
	for p in [[0,2.5],[2.1,2.5],[2.1,-7.8],[8,-7.8],[8,-12.5],[-5.96,-14.8]]:
		if not await walk(p[0],p[1]):break
	check(app.player.position.y>1.55,"walk up stage steps")
	check(app.zone(app.player.position)=="选手舞台","stage reached")
	check(not app.current_point.is_empty() and app.current_point["id"]=="desk","desk prompt")
	# Return using actual movement and the same doorway, not teleportation.
	for p in [[8,-12.5],[8,-7.8],[2.1,-7.8],[2.1,2.5],[0,2.5],[0,30],[0,48],[0,56.8]]:
		if not await walk(p[0],p[1]):break
	check(not app.current_point.is_empty() and app.current_point["id"]=="exit","return door available")
	check(atmosphere.entrance_count==1,"return trip does not replay the entrance cue")
	app.player.test_direction=Vector3(0,0,1);await frames(120);app.player.test_direction=Vector3.ZERO
	check(app.player.position.z<58.25,"exterior boundary solid")
	app.player.position=Vector3(0,.50,35);app.player.velocity=Vector3.ZERO;app.player.reset_physics_interpolation()
	await frames(15);app.player.test_direction=Vector3.RIGHT;await frames(100);app.player.test_direction=Vector3.ZERO
	check(app.player.position.x<2.55,"tunnel wall solid")
	check(app.player.position.y>0,"did not fall through floor")
	var report: Dictionary={"checks":checks,"failures":failures,"colliders":app.collision_builder.count,"atmosphere":atmosphere.diagnostic_snapshot()}
	var f:=FileAccess.open("res://temp/arena_test_report.json",FileAccess.WRITE);f.store_string(JSON.stringify(report,"  "))
	print("ARENA_RESULT ",JSON.stringify(report))
	get_tree().quit(0 if failures.is_empty() else 1)
