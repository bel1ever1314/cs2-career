extends Node3D
## One shared seated chicken design. Seats/feet remain planted; only a small
## near-floor group breathes and moves wings. Far terraces are fully static.

const MAX_ANIMATED := 56
const CUSHION_TOP := 0.475
const BODY_BOTTOM := 0.475
const FOOT_SOLE := 0.018
const PALETTE := [Color("ffffff"),Color("c99b71"),Color("91adb9"),Color("c47e60"),Color("657c80"),Color("d1ad62"),Color("a390b5"),Color("abb99b")]
var spectator_count := 0
var animated_count := 0
var removed_legacy_count := 0
var batch_count := 0
var grounded_count := 0
var max_floor_error := 0.0
var elapsed := 0.0
var cheer_mix := 0.0
var active := true
var near_transforms: Array[Transform3D] = []
var breathing_batch: MultiMesh
var left_wing_batch: MultiMesh
var right_wing_batch: MultiMesh

func setup(venue: Node3D) -> void:
	name = "SeatedChickenAudience"
	# Spectators are display-only, updated every rendered frame. Keep this
	# branch out of the arena's inherited physics interpolation path.
	physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_OFF
	var seated: Array[Transform3D] = []
	var near: Array[Transform3D] = []
	var far: Array[Transform3D] = []
	var floor_levels: Array[float] = []
	for surface_node in venue.find_children("*", "MeshInstance3D", true, false):
		var surface_name := str(surface_node.name).replace("_", " ").to_lower()
		if "terrace" in surface_name or surface_name == "event floor":
			var bounds: AABB = surface_node.global_transform * surface_node.get_aabb()
			floor_levels.append(bounds.end.y)
	for legacy in venue.find_children("Crowd*", "MeshInstance3D", true, false):
		var pose: Transform3D = legacy.global_transform
		# The GLB Crowd origins were 25 mm above terraces / 50 mm above the
		# event floor. Resolve the actual row surface, then plant the foot soles.
		# Keep the original X/Z, facing and row assignment; no AABB-centre seat.
		var row_floor := -INF
		for level in floor_levels:
			if level <= pose.origin.y + 0.001 and pose.origin.y - level <= 0.10:
				row_floor = maxf(row_floor, level)
		if is_finite(row_floor):
			pose.origin.y = row_floor - FOOT_SOLE
			grounded_count += 1
			max_floor_error = maxf(max_floor_error, absf((pose * Vector3(0, FOOT_SOLE, 0)).y - row_floor))
		seated.append(pose)
		var at := pose.origin
		if near.size() < MAX_ANIMATED and at.y < 3.4 and absf(at.x) < 13.0 and at.z > -8.0 and at.z < 18.0:
			near.append(pose)
		else:
			far.append(pose)
		legacy.visible = false
		legacy.queue_free()
		removed_legacy_count += 1
	spectator_count = seated.size()
	animated_count = near.size()
	near_transforms = near
	var material := StandardMaterial3D.new()
	material.vertex_color_use_as_albedo = true
	material.roughness = 0.88
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	_batch("AllSharedSeatsAndPlantedFeet", _seat_and_feet_mesh(), material, seated)
	_batch("StaticTerraceChickens", _chicken_mesh(true), material, far)
	breathing_batch = _batch("NearSeatedBodies", _chicken_mesh(false), material, near)
	left_wing_batch = _batch("NearLeftWings", _wing_mesh(-1.0), material, near)
	right_wing_batch = _batch("NearRightWings", _wing_mesh(1.0), material, near)
	_update_near(0.0)
	print("ARENA_CHICKEN_AUDIENCE seated=", spectator_count, " animated=", animated_count, " batches=", batch_count)

func _batch(label: String, mesh: ArrayMesh, material: Material, transforms: Array[Transform3D]) -> MultiMesh:
	var instances := MultiMesh.new()
	instances.transform_format = MultiMesh.TRANSFORM_3D
	instances.use_colors = true
	instances.mesh = mesh
	instances.instance_count = transforms.size()
	for i in range(transforms.size()):
		instances.set_instance_transform(i, transforms[i])
		instances.set_instance_color(i, PALETTE[(i * 7 + int(i / 9)) % PALETTE.size()])
	var batch := MultiMeshInstance3D.new()
	batch.name = label
	batch.physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_OFF
	batch.multimesh = instances
	batch.material_override = material
	batch.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(batch)
	batch_count += 1
	return instances

func _vertex(surface: SurfaceTool, at: Vector3, normal: Vector3, color: Color) -> void:
	surface.set_color(color)
	surface.set_normal(normal)
	surface.add_vertex(at)

func _triangle(surface: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, color: Color) -> void:
	var normal := (b - a).cross(c - a).normalized()
	_vertex(surface, a, normal, color)
	_vertex(surface, b, normal, color)
	_vertex(surface, c, normal, color)

func _box(surface: SurfaceTool, center: Vector3, size: Vector3, color: Color) -> void:
	var corners: Array[Vector3] = []
	for x in [-1.0, 1.0]:
		for y in [-1.0, 1.0]:
			for z in [-1.0, 1.0]:
				corners.append(center + size * Vector3(x, y, z) * 0.5)
	for face in [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]:
		_triangle(surface, corners[face[0]], corners[face[1]], corners[face[2]], color)
		_triangle(surface, corners[face[0]], corners[face[2]], corners[face[3]], color)

func _ellipsoid(surface: SurfaceTool, center: Vector3, radii: Vector3, color: Color, sides: int = 10, rings: int = 6) -> void:
	for row in range(rings):
		for side in range(sides):
			var directions: Array[Vector3] = []
			for ij in [[row, side], [row + 1, side], [row + 1, side + 1], [row, side + 1]]:
				var latitude := PI * float(ij[0]) / rings
				var longitude := TAU * float(ij[1]) / sides
				directions.append(Vector3(sin(latitude) * cos(longitude), cos(latitude), sin(latitude) * sin(longitude)))
			for tri in ([[0, 1, 2]] if row == 0 else ([[0, 2, 3]] if row == rings - 1 else [[0, 1, 2], [0, 2, 3]])):
				for index in tri:
					var direction: Vector3 = directions[index]
					_vertex(surface, center + direction * radii, (direction / radii).normalized(), color)

func _seat_and_feet_mesh() -> ArrayMesh:
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var frame := Color("172431")
	var upholstery := Color("29435b")
	_box(surface, Vector3(0, 0.435, -0.035), Vector3(0.50, 0.08, 0.46), upholstery)
	_box(surface, Vector3(0, 0.71, -0.265), Vector3(0.50, 0.58, 0.055), upholstery)
	for side in [-1.0, 1.0]:
		_box(surface, Vector3(side * 0.20, 0.207, -0.06), Vector3(0.045, 0.394, 0.35), frame)
		# Bent legs: belly supported by the cushion, soles on that row's floor.
		_box(surface, Vector3(side * 0.13, 0.235, 0.21), Vector3(0.047, 0.386, 0.055), Color("d7882e"))
		_ellipsoid(surface, Vector3(side * 0.13, 0.041, 0.29), Vector3(0.082, 0.023, 0.125), Color("efa949"), 8, 4)
	return surface.commit()

func _body_parts(surface: SurfaceTool) -> void:
	var feathers := Color("eedab1")
	_ellipsoid(surface, Vector3(0, 0.675, -0.015), Vector3(0.225, 0.20, 0.205), feathers)
	_ellipsoid(surface, Vector3(0, 0.985, 0.025), Vector3(0.178, 0.183, 0.172), Color("f4e8cd"))
	_ellipsoid(surface, Vector3(0, 0.65, -0.22), Vector3(0.10, 0.105, 0.105), feathers, 8, 4)
	# A red comb, orange pointed beak and front-facing eyes identify chickens.
	for z in [-0.055, 0.025, 0.10]:
		_ellipsoid(surface, Vector3(0, 1.162, z), Vector3(0.041, 0.086, 0.055), Color("cd4b39"), 8, 4)
	var beak_tip := Vector3(0, 0.969, 0.287)
	var beak_color := Color("eba84a")
	for tri in [[Vector3(-0.063, 1.005, 0.177), Vector3(0.063, 1.005, 0.177), beak_tip],
		[Vector3(0.063, 1.005, 0.177), Vector3(0, 0.935, 0.179), beak_tip],
		[Vector3(0, 0.935, 0.179), Vector3(-0.063, 1.005, 0.177), beak_tip]]:
		_triangle(surface, tri[0], tri[1], tri[2], beak_color)
	for side in [-1.0, 1.0]:
		_ellipsoid(surface, Vector3(side * 0.076, 1.035, 0.177), Vector3(0.036, 0.041, 0.017), Color("fffaf0"), 8, 4)
		_ellipsoid(surface, Vector3(side * 0.076, 1.034, 0.192), Vector3(0.018, 0.025, 0.008), Color("172533"), 6, 4)
		_ellipsoid(surface, Vector3(side * 0.065, 1.047, 0.198), Vector3(0.006, 0.008, 0.004), Color.WHITE, 6, 3)

func _chicken_mesh(include_wings: bool) -> ArrayMesh:
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	_body_parts(surface)
	if include_wings:
		for side in [-1.0, 1.0]:
			_ellipsoid(surface, Vector3(side * 0.231, 0.661, 0.03), Vector3(0.064, 0.154, 0.107), Color("dec899"), 8, 5)
	return surface.commit()

func _wing_mesh(side: float) -> ArrayMesh:
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	_ellipsoid(surface, Vector3(side * 0.032, -0.079, 0.03), Vector3(0.064, 0.154, 0.107), Color("dec899"), 8, 5)
	return surface.commit()

func set_reaction(value: float, is_active: bool = true) -> void:
	cheer_mix = clampf(value, 0.0, 1.0)
	active = is_active

func _process(delta: float) -> void:
	if active:
		elapsed += delta
		_update_near(elapsed)

func _update_near(at_time: float) -> void:
	if not breathing_batch:
		return
	for i in range(near_transforms.size()):
		var pose := near_transforms[i]
		var phase := i * 1.713
		var breathe := sin(at_time * 1.6 + phase) * 0.006
		var body_pose := pose
		body_pose.origin.y += breathe
		breathing_batch.set_instance_transform(i, body_pose)
		for side in [-1.0, 1.0]:
			var gesture := 0.0
			# Infrequent low-amplitude wing/shoulder movement keeps near fans alive
			# between walk-ins; feet and all far terraces remain fully static.
			var idle_gesture := maxf(0.0,sin(at_time * .62 + phase)) * .10 if i % 4 == 0 else .0
			if i % 3 == 0:
				gesture = cheer_mix * (1.40 + 0.15 * sin(at_time * 3.4 + phase))
			elif i % 3 == 1:
				gesture = cheer_mix * (0.45 + 0.18 * sin(at_time * 4.8 + phase))
			gesture += idle_gesture
			var wing_pose := Transform3D(Basis(Vector3.FORWARD, -side * gesture), Vector3(side * 0.199, 0.74 + breathe, 0.0))
			(left_wing_batch if side < 0.0 else right_wing_batch).set_instance_transform(i, pose * wing_pose)

func diagnostic_snapshot() -> Dictionary:
	return {"species": "chicken", "seated": spectator_count, "legacy_removed": removed_legacy_count,
		"animated": animated_count, "batches": batch_count, "body_bottom_m": BODY_BOTTOM,
		"cushion_top_m": CUSHION_TOP, "foot_sole_m": FOOT_SOLE,
		"grounded": grounded_count, "max_floor_error_m": max_floor_error,
		"far_static": spectator_count - animated_count, "spectator_physics": 0,"palette_variants":PALETTE.size()}
