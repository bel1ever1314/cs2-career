extends SceneTree
## Isolated LAN visual regression: no service, career writes or user settings.
## --script res://tests/lan_lighting_test.gd -- --no-service [--capture-lan-lighting] [--lan-lighting-baseline]
var checks := 0
var failures: Array[String] = []
var scene
var baseline := false
var capture_enabled := false

func _initialize() -> void: call_deferred("run")

func check(ok: bool, caption: String) -> void:
	checks += 1
	if not ok: failures.append(caption)
	print("LAN_LIGHTING ","PASS " if ok else "FAIL ",caption)

func frames(count: int) -> void:
	for index in range(count): await process_frame

func light_snapshot() -> Dictionary:
	var result := {}
	for light in scene.find_children("*","Light3D",true,false):
		result[str(light.get_path())] = [light.light_energy,light.position,light.rotation,light.visible,light.shadow_enabled]
	return result

func floor_surfaces() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for mesh in scene.find_children("*","MeshInstance3D",true,false):
		if not mesh.is_visible_in_tree() or not mesh.mesh is BoxMesh: continue
		var bounds: AABB = mesh.global_transform*mesh.get_aabb()
		if bounds.size.y>.26 or absf(bounds.end.y)>.0001 or bounds.size.x*bounds.size.z<1: continue
		var material := mesh.material_override as StandardMaterial3D
		if material==null: continue
		result.append({"node":str(mesh.get_path()),"top":bounds.end.y,"rect":Rect2(bounds.position.x,bounds.position.z,bounds.size.x,bounds.size.z),"color":material.albedo_color.to_html()})
	return result

func conflicts(surfaces: Array[Dictionary]) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for index in range(surfaces.size()):
		for other in range(index+1,surfaces.size()):
			var a := surfaces[index]; var b := surfaces[other]
			if a.color==b.color: continue
			var overlap: Rect2 = a.rect.intersection(b.rect)
			if overlap.get_area()>.1: result.append({"a":a.node,"b":b.node,"top":a.top,"area":overlap.get_area(),"colors":[a.color,b.color]})
	return result

func legacy_wall_meshes() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for child in scene.get_children():
		if not child is MeshInstance3D or not child.mesh is BoxMesh: continue
		var size: Vector3 = child.mesh.size
		if is_equal_approx(size.x,.18) and is_equal_approx(size.y,4.1) and is_equal_approx(size.z,13):
			result.append({"node":str(child.name),"visible":child.visible})
	return result

func screenshot(name_value: String) -> void:
	await RenderingServer.frame_post_draw
	check(root.get_texture().get_image().save_png("res://temp/"+name_value+".png")==OK,"save "+name_value)

func visual_samples(prefix: String) -> Dictionary:
	var samples: Array[float] = []
	for index in range(24):
		# A tiny real camera turn changes depth rasterization but neither light
		# nor floor material. Sample the same unobstructed floor world position.
		scene.camera.rotation.y = -.006+index*.0005
		await frames(2); await RenderingServer.frame_post_draw
		var picture := root.get_texture().get_image()
		var point: Vector2 = scene.camera.unproject_position(Vector3(1.5,.001,3.15))
		var pixel := picture.get_pixel(clampi(roundi(point.x),0,picture.get_width()-1),clampi(roundi(point.y),0,picture.get_height()-1))
		samples.append((pixel.r+pixel.g+pixel.b)/3.0)
		if index in [0,12,23]: check(picture.save_png("res://temp/"+prefix+"-%02d.png" % index)==OK,"save sweep frame")
	var minimum := 1.0; var maximum := 0.0
	for value in samples: minimum=minf(minimum,value); maximum=maxf(maximum,value)
	return {"samples":samples,"minimum":minimum,"maximum":maximum,"range":maximum-minimum}

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args():
		push_error("LAN lighting QA requires --no-service"); quit(1); return
	baseline = "--lan-lighting-baseline" in OS.get_cmdline_user_args()
	capture_enabled = "--capture-lan-lighting" in OS.get_cmdline_user_args()
	root.get_node("CareerBridge").set_process(false)
	root.get_node("Travel").match_visit = {}
	root.content_scale_size = Vector2i(1440,1000); root.size = Vector2i(1440,1000)
	change_scene_to_file("res://lan.tscn"); await scene_changed; await frames(8)
	scene = current_scene; scene.testing = true; scene.focused = true; scene.camera_owned = true
	scene.player.set_physics_process(false); scene.set_process(false); Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	scene.camera.position = Vector3(0,1.65,5.7); scene.camera.rotation = Vector3(-.14,0,0)
	var tier: Node3D = scene.get_node("VenueTierBuilding")
	var initial := light_snapshot(); await frames(32)
	check(initial==light_snapshot(),"all original and tier light energies/positions stay constant")
	check(tier.roof_group.visible and tier.upper_wall_group.visible,"first-person roof does not toggle")
	check(scene.stations.size()==10,"ten original stations preserved")
	var rows := floor_surfaces(); var overlaps := conflicts(rows); var walls := legacy_wall_meshes()
	print("LAN_LIGHTING_SURFACES ",JSON.stringify(rows)); print("LAN_LIGHTING_CONFLICTS ",JSON.stringify(overlaps)); print("LAN_LIGHTING_OLD_WALLS ",JSON.stringify(walls))
	if baseline: check(not overlaps.is_empty(),"baseline reproduces unlike-material coplanar floor")
	else:
		check(overlaps.is_empty(),"no unlike-material coplanar floor surfaces")
		check(walls.size()==2,"both original side walls remain identifiable")
		for wall in walls: check(not wall.visible,"old wall visual hidden: "+wall.node)
	var samples := {}
	if capture_enabled:
		check(ProjectSettings.globalize_path("res://").begins_with("E:/"),"captures stay on E drive")
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://temp"))
		await screenshot("lan-lighting-before" if baseline else "lan-lighting-after")
		samples = await visual_samples("lan-lighting-before" if baseline else "lan-lighting-after")
		if not baseline: check(float(samples.range)<.05,"same world-floor sample has no dark/bright flicker while turning")
	print("LAN_LIGHTING_RESULT ",JSON.stringify({"checks":checks,"failures":failures,"conflicts":overlaps,"old_walls":walls,"floor_luminance":samples}))
	quit(0 if failures.is_empty() else 1)
