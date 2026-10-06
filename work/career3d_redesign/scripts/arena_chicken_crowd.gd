extends Node3D
## One shared seated chicken design. Seats/feet remain planted; only a small
## near-floor group breathes and moves wings. Far terraces are fully static.

const ChickenMesh = preload("res://scripts/chicken_mesh.gd")
const MAX_ANIMATED := 56
const CUSHION_TOP := 0.30
const BODY_BOTTOM := 0.30
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
	# The entrance tunnel cuts through the lowest rows: nobody sits on its roof.
	var tunnels: Array[AABB] = []
	for surface_node in venue.find_children("*", "MeshInstance3D", true, false):
		if "walk tunnel" in str(surface_node.name).replace("_", " ").to_lower():
			tunnels.append(surface_node.global_transform * surface_node.get_aabb())
	for legacy in venue.find_children("Crowd*", "MeshInstance3D", true, false):
		var pose: Transform3D = legacy.global_transform
		# The GLB Crowd origins were 25 mm above terraces / 50 mm above the
		# event floor. Resolve the actual row surface, then plant the foot soles.
		# Keep the original X/Z, facing and row assignment; no AABB-centre seat.
		var row_floor := -INF
		for level in floor_levels:
			if level <= pose.origin.y + 0.001 and pose.origin.y - level <= 0.10:
				row_floor = maxf(row_floor, level)
		legacy.visible = false
		legacy.queue_free()
		removed_legacy_count += 1
		# A spectator with no terrace or floor under it would float: skip it.
		if not is_finite(row_floor) or _over_tunnel(pose.origin, tunnels): continue
		pose.origin.y = row_floor - FOOT_SOLE
		grounded_count += 1
		max_floor_error = maxf(max_floor_error, absf((pose * Vector3(0, FOOT_SOLE, 0)).y - row_floor))
		seated.append(pose)
		var at := pose.origin
		if near.size() < MAX_ANIMATED and at.y < 3.4 and absf(at.x) < 13.0 and at.z > -8.0 and at.z < 18.0:
			near.append(pose)
		else:
			far.append(pose)
	all_seated = seated; all_near = near; all_far = far
	_build_batches(seated, near, far)
	print("ARENA_CHICKEN_AUDIENCE seated=", spectator_count, " animated=", animated_count, " batches=", batch_count)

func _over_tunnel(at: Vector3, tunnels: Array[AABB]) -> bool:
	for box in tunnels:
		if at.x > box.position.x - 0.3 and at.x < box.end.x + 0.3 and at.z > box.position.z - 0.3 and at.z < box.end.z + 0.3 and at.y < box.end.y + 1.6:
			return true
	return false

var all_seated: Array[Transform3D] = []
var all_near: Array[Transform3D] = []
var all_far: Array[Transform3D] = []

func _build_batches(seated: Array[Transform3D], near: Array[Transform3D], far: Array[Transform3D]) -> void:
	for child in get_children():
		if child is MultiMeshInstance3D: remove_child(child); child.queue_free()
	batch_count = 0
	spectator_count = seated.size()
	animated_count = near.size()
	near_transforms = near
	var material := ChickenMesh.material()
	_batch("AllSharedSeatsAndPlantedFeet", _seat_and_feet_mesh(), material, seated)
	_batch("StaticTerraceChickens", ChickenMesh.seated_chicken(0, true), material, far)
	breathing_batch = _batch("NearSeatedBodies", _chicken_mesh(false), material, near)
	left_wing_batch = _batch("NearLeftWings", _wing_mesh(-1.0), material, near)
	right_wing_batch = _batch("NearRightWings", _wing_mesh(1.0), material, near)
	_update_near(elapsed)

## A smaller event only fills the lower tiers: drop spectators seated above.
func limit_height(max_y: float) -> void:
	_build_batches(_below(all_seated, max_y), _below(all_near, max_y), _below(all_far, max_y))

func _below(list: Array[Transform3D], max_y: float) -> Array[Transform3D]:
	var out: Array[Transform3D] = []
	for pose in list:
		if pose.origin.y <= max_y: out.append(pose)
	return out

func _batch(label: String, mesh: ArrayMesh, material: Material, transforms: Array[Transform3D]) -> MultiMesh:
	var instances := MultiMesh.new()
	instances.transform_format = MultiMesh.TRANSFORM_3D
	# Per-spectator feather tint travels in custom data, so eyes, beaks and
	# combs keep their colours (instance colour would tint everything).
	instances.use_custom_data = true
	# White instance colour: some renderers multiply vertex colour by it.
	instances.use_colors = true
	instances.mesh = mesh
	instances.instance_count = transforms.size()
	for i in range(transforms.size()):
		instances.set_instance_transform(i, transforms[i])
		instances.set_instance_custom_data(i, ChickenMesh.tint(i))
		instances.set_instance_color(i, Color.WHITE)
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
	var frame := Color("3b4350")
	var upholstery := Color("b5473f")
	_box(surface, Vector3(0, CUSHION_TOP - 0.04, -0.035), Vector3(0.50, 0.08, 0.46), upholstery)
	# Backrest sits behind the tail feathers (tail reaches z = -0.285).
	_box(surface, Vector3(0, CUSHION_TOP + 0.25, -0.32), Vector3(0.50, 0.58, 0.055), upholstery)
	for side in [-1.0, 1.0]:
		_box(surface, Vector3(side * 0.20, (CUSHION_TOP - 0.08) * 0.5, -0.06), Vector3(0.045, CUSHION_TOP - 0.08, 0.35), frame)
	# Seated legs: knees over the cushion edge, soles on that row's floor.
	ChickenMesh.legs(surface, Vector3.ZERO, FOOT_SOLE)
	return surface.commit()

func _body_parts(surface: SurfaceTool) -> void:
	ChickenMesh.add_seated_chicken(surface, Vector3.ZERO, 2, false)

func _chicken_mesh(include_wings: bool) -> ArrayMesh:
	return ChickenMesh.seated_chicken(2, include_wings)

func _wing_mesh(side: float) -> ArrayMesh:
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	ChickenMesh.ellipsoid(surface, Vector3(side * 0.036, -0.065, 0.01), Vector3(0.06, 0.14, 0.11), Color(0.93, 0.9, 0.85, 0.0), 10, 6)
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
			var wing_pose := Transform3D(Basis(Vector3.FORWARD, -side * gesture), Vector3(side * 0.199, 0.74 - (0.475 - BODY_BOTTOM) + breathe, 0.0))
			(left_wing_batch if side < 0.0 else right_wing_batch).set_instance_transform(i, pose * wing_pose)

func diagnostic_snapshot() -> Dictionary:
	return {"species": "chicken", "seated": spectator_count, "legacy_removed": removed_legacy_count,
		"animated": animated_count, "batches": batch_count, "body_bottom_m": BODY_BOTTOM,
		"cushion_top_m": CUSHION_TOP, "foot_sole_m": FOOT_SOLE,
		"grounded": grounded_count, "max_floor_error_m": max_floor_error,
		"far_static": spectator_count - animated_count, "spectator_physics": 0,"palette_variants":PALETTE.size()}

