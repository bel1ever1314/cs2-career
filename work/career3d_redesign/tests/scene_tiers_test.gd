extends SceneTree
## Standalone isolated harness: does not autoload/start CareerBridge or a service.
const Tiers = preload("res://scripts/scene_tiers.gd")
const Builder = preload("res://scripts/scene_tier_building.gd")
const ClubCollisions = preload("res://scripts/club_collision.gd")
class Harness extends Node3D:
	var player: CharacterBody3D
var scene: Harness
var viewport: SubViewport
var camera: Camera3D
var reports: Array[Dictionary] = []
var output := ""
var failures := 0

func _initialize() -> void: call_deferred("run")

func _check(value: bool, message: String) -> void:
	if not value:
		failures += 1
		push_error("SCENE_TIERS_FAILED "+message)
		assert(value,message)

func run() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--output="): output = argument.trim_prefix("--output=")
	if not output.is_empty():
		_check(output.begins_with("E:/") or output.begins_with("E:\\"),"captures must stay on E")
		DirAccess.make_dir_recursive_absolute(output)
	viewport = SubViewport.new(); viewport.size = Vector2i(1440,980)
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS; root.add_child(viewport)
	for tier in ["academy","standard","elite"]: await _club(tier)
	for capacity in [0,100,1000,10000]: await _venue(capacity)
	await _arena_small()
	await _home()
	_check(reports.size()==9,"all fixtures reached their assertions")
	print("SCENE_TIERS_OK " if failures==0 else "SCENE_TIERS_FAILED ",JSON.stringify(reports))
	if not output.is_empty():
		var file := FileAccess.open(output.path_join("scene-tiers-report.json"),FileAccess.WRITE)
		file.store_string(JSON.stringify({"ok":failures==0,"checks":reports},"\t")); file.close()
	viewport.queue_free(); await process_frame; await process_frame
	quit(0 if failures==0 else 1)

func _new_scene() -> void:
	if scene: viewport.remove_child(scene); scene.queue_free()
	scene = Harness.new(); viewport.add_child(scene)
	var world := WorldEnvironment.new(); var env := Environment.new(); world.environment = env
	env.background_mode = Environment.BG_COLOR; env.background_color = Color("bbc9ba")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR; env.ambient_light_color = Color("ffecd0")
	env.ambient_light_energy = .40; env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.ssao_enabled = true; env.ssao_radius = .6; env.ssao_intensity = .8; scene.add_child(world)
	var sun := DirectionalLight3D.new(); sun.rotation_degrees = Vector3(-62,-28,0); sun.light_color = Color("ffe8c1")
	sun.light_energy = .68; sun.shadow_enabled = true; scene.add_child(sun)
	camera = Camera3D.new(); camera.current = true; camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.near = .1; camera.far = 500; scene.add_child(camera)

func _club(tier: String) -> void:
	_new_scene()
	var model: Node3D
	if ResourceLoader.exists("res://assets/chicken_club.glb"): model = load("res://assets/chicken_club.glb").instantiate()
	else: model = Node3D.new()
	scene.add_child(model); var original: Array[Dictionary] = []
	if model.get_child_count()>0:
		var collisions := ClubCollisions.new(); collisions.build(scene,model)
		for row in collisions.audit:
			if str(row.id)!="east_boundary": original.append(row.duplicate(true))
	else:
		var boundary := StaticBody3D.new(); boundary.name = "Solid_east_boundary"; scene.add_child(boundary)
	scene.player = CharacterBody3D.new(); scene.player.position = Vector3(-.75,.23,6.65); scene.add_child(scene.player)
	var level := 1 if tier=="academy" else 2 if tier=="standard" else 3
	var building = Tiers.apply_club(scene,model,tier,{"training":level,"meeting":level,"kitchen":level,"lounge":level})
	_check(building.tier==tier,"requested club tier")
	_check(Tiers.apply_club(scene,model,tier,building.facilities)==building,"idempotent tier application")
	if tier!="academy":
		_check(building.footprint.end.x>12.3,"annex adds usable space")
		_check(scene.get_node("Solid_east_boundary").collision_layer==0,"annex door opens old boundary")
		# Traversability at the doorway and the central annex aisle is checked
		# against the exact collision geometry, not just decoration bounds.
		_check(not Tiers._inside_solid(scene,Vector3(12.5,.23,0)),"door not blocked")
		_check(not Tiers._inside_solid(scene,Vector3(14,.23,0)),"annex centre aisle not blocked")
		for node in scene.get_children():
			if not node is StaticBody3D or node.has_meta("tier_original_layer"): continue
			_check(node.collision_layer!=0,"original collider stays active")
	var view := Tiers.club_view(tier); camera.size = float(view.size)
	camera.position = view.focus+Vector3(20,32,34); camera.look_at(view.focus)
	await _capture("club_"+tier)
	reports.append(building.diagnostics())
	if tier=="elite":
		scene.player.position = Vector3(22,.23,0)
		Tiers.apply_club(scene,model,"academy",{})
		_check(scene.player.position.x<11.8,"shrinking annex returns player safely")
		_check(scene.get_node("Solid_east_boundary").collision_layer!=0,"academy restores old boundary")

func _venue(capacity: int) -> void:
	_new_scene()
	var building = load(str(Tiers.catalog().venues[str(capacity)].scene)).instantiate()
	building.include_stations = true; scene.add_child(building)
	_check(building.audience_count==capacity,"audience count equals capacity")
	_check(building.station_count==10,"all venue tiers retain ten player stations")
	_check(building.enclosure_closed and building.roof_height>4,"venue is a closed building")
	await physics_frame; await physics_frame
	var roof_ray := PhysicsRayQueryParameters3D.create(Vector3(2,1.8,2),Vector3(2,50,2),1)
	var hit: Dictionary = scene.get_world_3d().direct_space_state.intersect_ray(roof_ray)
	_check(not hit.is_empty() and hit.position.y>=building.roof_height-.5,"physical roof encloses first-person view")
	_check(not Tiers._inside_solid(building,Vector3(0,.44 if capacity>=1000 else .04,building.footprint.end.y)),"venue central doorway is physically open")
	if capacity>=1000:
		camera.size = 93 if capacity==1000 else 185
		camera.position = Vector3(85,120,160) if capacity==10000 else Vector3(42,62,80)
		camera.look_at(Vector3(0,3,3))
	else:
		camera.size = 25 if capacity==0 else 37
		camera.position = Vector3(17,25,32); camera.look_at(Vector3(0,1,0))
	await _capture("venue_"+str(capacity)); reports.append(building.diagnostics())
	if not output.is_empty():
		building.auto_cutaway = false; building.set_cutaway(false)
		await _capture("venue_"+str(capacity)+"_closed")
		camera.projection = Camera3D.PROJECTION_PERSPECTIVE; camera.fov = 78
		camera.position = Vector3(0,2.5,14) if capacity>=1000 else Vector3(0,1.65,5.7)
		camera.look_at(Vector3(0,3,-14.5) if capacity>=1000 else Vector3(0,1.6,-3.4))
		await _capture("venue_"+str(capacity)+"_interior")

func _arena_small() -> void:
	_new_scene()
	var model := Node3D.new(); scene.add_child(model)
	var building = Tiers.apply_venue(scene,model,100,"major")
	_check(building.audience_count==100,"small arena actual audience")
	_check(building.station_count==0,"integration does not duplicate source stations")
	_check(building.roof_height>=29.5,"integration clears original arena stage arch")
	_check(building.footprint.has_point(Vector2(0,-14.5)),"small arena includes original stage")
	for z in range(-14,59):
		_check(not Tiers._inside_solid(building,Vector3(0,.52,z)),"small arena centre approach stays open")
	_check(Tiers.apply_venue(scene,model,100,"major")==building,"arena update idempotent")
	camera.size = 75; camera.position = Vector3(38,52,77); camera.look_at(Vector3(0,3,3))
	await _capture("venue_arena_100"); reports.append(building.diagnostics())

func _home() -> void:
	_new_scene()
	var model: Node3D
	if ResourceLoader.exists("res://assets/cozy_room.glb"): model = load("res://assets/cozy_room.glb").instantiate()
	else: model = Node3D.new()
	scene.add_child(model)
	var home := {"wallpaper":"peach","floor":"walnut","placed":[
		{"id":"plant-1","item":"plant","x":-2.8,"z":2.2,"rotation":0,"color":"729a7d"},
		{"id":"lamp-1","item":"lamp","x":-2.8,"z":.3,"rotation":0,"color":"e5cda7"},
		{"id":"rug-1","item":"rug","x":-.2,"z":1.2,"rotation":0,"color":"b8c5a6"}]}
	var building = Tiers.apply_home(scene,model,home)
	_check(building.get_child_count()==3,"three placed furniture objects")
	_check(Tiers.apply_home(scene,model,home)==building,"home update idempotent")
	home["balance"] = 999999
	_check(Tiers.apply_home(scene,model,home)==building,"wallet update does not rebuild decor")
	var plant: Node3D = building.get_child(0)
	_check(is_equal_approx(plant.get_node("PlantSolid").get_child(0).shape.size.x,.45),"home collider matches authoritative plant footprint")
	camera.size = 10.7; camera.position = Vector3(10,16,19); camera.look_at(Vector3(0,.6,0))
	await _capture("home_decor"); reports.append({"kind":"home","objects":3})

func _capture(name_value: String) -> void:
	await process_frame; await process_frame
	if output.is_empty(): return
	await create_timer(.15).timeout; await RenderingServer.frame_post_draw
	var path := output.path_join(name_value+".png")
	_check(viewport.get_texture().get_image().save_png(path)==OK,"save render "+name_value)
