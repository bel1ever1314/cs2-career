extends Node3D
## The island the club stands on: soft grass with a soil edge, a sandy rim,
## turquoise water, round fruit trees and pines, hedges, flower patches,
## a stepping-stone path to the door, lamps, a bench and a club sign.
## Purely decorative — no collisions, no career data except the team mark.
const Kit = preload("res://scripts/stage_kit.gd")
const ChickenMesh = preload("res://scripts/chicken_mesh.gd")
const GRASS := Color("86c35a")
const GRASS_DARK := Color("6dab48")
const SOIL := Color("c58f5c")
const SAND := Color("f3e3b5")
const WATER := Color("79cfd3")
const STONE := Color("e6dfcf")
const BARK := Color("a8744a")
const LEAF := Color("5fa84e")
const PINE := Color("4f9a63")
const WOOD := Color("c79a66")
var footprint := Rect2()
var team := ""
var rng := RandomNumberGenerator.new()
var keep_out: Array[Rect2] = []

func build(area: Rect2, team_name: String = "") -> void:
	for child in get_children(): child.queue_free()
	footprint = area
	team = team_name
	rng.seed = 2207
	name = "ClubGrounds"
	var island := Rect2(area.position - Vector2(10.0, 8.0), area.size + Vector2(20.0, 26.0))
	var door := Vector2(0.0, area.end.y)
	keep_out = [area.grow(0.6), Rect2(door.x - 1.6, door.y - 0.2, 3.2, island.end.y - door.y)]
	_ground(island)
	_path(door, island)
	_trees(island)
	_hedges(area, door)
	_flowers(island)
	_props(door)

func _free(point: Vector2, margin: float = 0.0) -> bool:
	for rect in keep_out:
		if rect.grow(margin).has_point(point): return false
	return true

# ---------------------------------------------------------------- ground

func _rounded_slab(id: String, rect: Rect2, top: float, thickness: float, radius: float, mat: Material) -> void:
	var centre := Vector3(rect.get_center().x, top - thickness * 0.5, rect.get_center().y)
	Kit.box(self, id, centre, Vector3(rect.size.x - radius * 2.0, thickness, rect.size.y), mat)
	Kit.box(self, id, centre, Vector3(rect.size.x, thickness, rect.size.y - radius * 2.0), mat)
	for x in [rect.position.x + radius, rect.end.x - radius]:
		for z in [rect.position.y + radius, rect.end.y - radius]:
			Kit.cylinder(self, id + "Corner", Vector3(x, centre.y, z), radius, thickness, mat, 24)

func _ground(island: Rect2) -> void:
	var water := MeshInstance3D.new(); water.name = "Sea"
	var plane := PlaneMesh.new(); plane.size = Vector2(320, 320); water.mesh = plane
	water.position = Vector3(island.get_center().x, -0.95, island.get_center().y)
	var water_mat := StandardMaterial3D.new(); water_mat.albedo_color = WATER; water_mat.roughness = 0.15; water_mat.metallic = 0.1
	water.material_override = water_mat; add_child(water)
	_rounded_slab("Beach", island.grow(1.6), -0.62, 0.5, 4.0, Kit.material(SAND, 0.0, 0.95))
	_rounded_slab("IslandSoil", island, -0.08, 0.9, 3.2, Kit.material(SOIL, 0.0, 0.95))
	_rounded_slab("IslandGrass", island.grow(-0.05), -0.04, 0.08, 3.15, Kit.material(GRASS, 0.0, 0.92))
	# Grass tufts break up the flat green (one batch).
	var tuft := SurfaceTool.new(); tuft.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in range(3):
		var angle := i * TAU / 3.0
		ChickenMesh.ellipsoid(tuft, Vector3(cos(angle) * 0.05, 0.06, sin(angle) * 0.05), Vector3(0.035, 0.09, 0.035), Color(GRASS_DARK.r, GRASS_DARK.g, GRASS_DARK.b, 1.0), 6, 3)
	var points: Array[Transform3D] = []
	for i in range(900):
		var p := Vector2(rng.randf_range(island.position.x + 0.8, island.end.x - 0.8), rng.randf_range(island.position.y + 0.8, island.end.y - 0.8))
		if not _free(p): continue
		points.append(Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * rng.randf_range(0.7, 1.3)), Vector3(p.x, -0.04, p.y)))
	_batch("GrassTufts", tuft.commit(), points, false)

func _path(door: Vector2, island: Rect2) -> void:
	# A small stone plaza at the door, then stepping stones to the jetty edge.
	var stone := Kit.material(STONE, 0.0, 0.9)
	Kit.cylinder(self, "DoorPlaza", Vector3(door.x, -0.02, door.y + 1.3), 1.5, 0.05, stone, 28)
	var z := door.y + 3.1
	var i := 0
	while z < island.end.y - 1.0:
		var x: float = door.x + (0.28 if i % 2 == 0 else -0.28)
		var slab := Kit.cylinder(self, "SteppingStone", Vector3(x, -0.025, z), rng.randf_range(0.42, 0.5), 0.05, stone, 18)
		slab.scale = Vector3(1.0, 1.0, 0.8)
		z += 1.05; i += 1

# ---------------------------------------------------------------- planting

func _tree_mesh(pine: bool) -> ArrayMesh:
	var surface := SurfaceTool.new(); surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var bark := Color(BARK.r, BARK.g, BARK.b, 1.0)
	ChickenMesh.ellipsoid(surface, Vector3(0, 0.75, 0), Vector3(0.16, 0.8, 0.16), bark, 10, 6)
	if pine:
		# Stacked soft tiers, AC-style cedar.
		for tier in [[1.5, 1.0, 0.55], [2.15, 0.78, 0.5], [2.7, 0.52, 0.45], [3.12, 0.28, 0.32]]:
			ChickenMesh.ellipsoid(surface, Vector3(0, tier[0], 0), Vector3(tier[1], tier[2], tier[1]), Color(PINE.r, PINE.g, PINE.b, 0.0), 14, 7)
	else:
		for blob in [[0, 2.15, 0, 1.05], [-0.55, 1.85, 0.2, 0.72], [0.55, 1.9, -0.15, 0.75], [0.1, 2.75, -0.1, 0.72], [0.15, 1.8, 0.6, 0.6]]:
			ChickenMesh.ellipsoid(surface, Vector3(blob[0], blob[1], blob[2]), Vector3.ONE * blob[3], Color(LEAF.r, LEAF.g, LEAF.b, 0.0), 14, 9)
		for fruit in [[0.7, 1.75, 0.55], [-0.6, 2.2, 0.62], [0.2, 2.5, 0.92], [-0.25, 1.55, 0.78]]:
			ChickenMesh.ellipsoid(surface, Vector3(fruit[0], fruit[1], fruit[2]), Vector3.ONE * 0.11, Color(1.0, 0.55, 0.25, 1.0), 8, 5)
	return surface.commit()

func _trees(island: Rect2) -> void:
	var fruit: Array[Transform3D] = []; var pines: Array[Transform3D] = []
	var placed: Array[Vector2] = []
	for attempt in range(600):
		if fruit.size() + pines.size() >= 34: break
		var p := Vector2(rng.randf_range(island.position.x + 1.6, island.end.x - 1.6), rng.randf_range(island.position.y + 1.6, island.end.y - 1.6))
		if not _free(p, 1.8): continue
		var crowded := false
		for other in placed:
			if other.distance_to(p) < 3.0: crowded = true; break
		if crowded: continue
		placed.append(p)
		var pose := Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * rng.randf_range(0.85, 1.2)), Vector3(p.x, -0.04, p.y))
		if rng.randf() < 0.4: pines.append(pose)
		else: fruit.append(pose)
	_batch("FruitTrees", _tree_mesh(false), fruit, true)
	_batch("Pines", _tree_mesh(true), pines, true)

func _hedges(area: Rect2, door: Vector2) -> void:
	# Round hedges along the front wall, leaving the doorway clear.
	var surface := SurfaceTool.new(); surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	ChickenMesh.ellipsoid(surface, Vector3(0, 0.32, 0), Vector3(0.48, 0.38, 0.42), Color(LEAF.r, LEAF.g, LEAF.b, 0.0), 12, 7)
	var poses: Array[Transform3D] = []
	var x := area.position.x + 0.7
	while x < area.end.x - 0.5:
		if absf(x - door.x) > 2.6:
			poses.append(Transform3D(Basis.IDENTITY.scaled(Vector3.ONE * rng.randf_range(0.85, 1.1)), Vector3(x, -0.04, area.end.y + 0.95)))
		x += 0.95
	_batch("Hedges", surface.commit(), poses, true)

func _flowers(island: Rect2) -> void:
	var surface := SurfaceTool.new(); surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var stem := Color(0.42, 0.68, 0.36, 1.0)
	ChickenMesh.ellipsoid(surface, Vector3(0, 0.12, 0), Vector3(0.02, 0.12, 0.02), stem, 5, 3)
	ChickenMesh.ellipsoid(surface, Vector3(0.06, 0.06, 0), Vector3(0.06, 0.02, 0.03), stem, 5, 3)
	for i in range(5):
		var a := i * TAU / 5.0
		ChickenMesh.ellipsoid(surface, Vector3(cos(a) * 0.06, 0.25, sin(a) * 0.06), Vector3(0.05, 0.025, 0.05), Color(1, 1, 1, 0.0), 7, 4)
	ChickenMesh.ellipsoid(surface, Vector3(0, 0.26, 0), Vector3(0.035, 0.03, 0.035), Color(1.0, 0.85, 0.35, 1.0), 6, 3)
	var colours := [Color("ff7a7a"), Color("ffd45e"), Color("ffffff"), Color("c99bff"), Color("ff9ed2"), Color("ffa552")]
	var poses: Array[Transform3D] = []; var tints: Array[Color] = []
	for patch in range(16):
		var centre := Vector2(rng.randf_range(island.position.x + 1.0, island.end.x - 1.0), rng.randf_range(island.position.y + 1.0, island.end.y - 1.0))
		if not _free(centre, 0.8): continue
		var colour: Color = colours[patch % colours.size()]
		for f in range(9):
			var p := centre + Vector2(rng.randf_range(-0.8, 0.8), rng.randf_range(-0.6, 0.6))
			if not _free(p): continue
			poses.append(Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * rng.randf_range(0.9, 1.3)), Vector3(p.x, -0.04, p.y)))
			tints.append(colour)
	_batch("Flowers", surface.commit(), poses, false, Color.WHITE, tints)

# ---------------------------------------------------------------- props

func _props(door: Vector2) -> void:
	var wood := Kit.material(WOOD, 0.0, 0.85)
	var dark := Kit.material(Color("5a4636"), 0.0, 0.8)
	# Lamps either side of the path.
	for side in [-1.0, 1.0]:
		for z in [door.y + 3.0, door.y + 8.0]:
			var at: Vector3 = Vector3(door.x + side * 1.6, 0.0, z)
			Kit.cylinder(self, "LampPost", at + Vector3(0, 0.9, 0), 0.05, 1.8, dark, 10)
			Kit.cylinder(self, "LampBase", at + Vector3(0, 0.08, 0), 0.14, 0.16, dark, 12)
			var bulb := MeshInstance3D.new(); bulb.name = "LampGlobe"
			var sphere := SphereMesh.new(); sphere.radius = 0.17; sphere.height = 0.34; bulb.mesh = sphere
			bulb.position = at + Vector3(0, 1.92, 0); bulb.material_override = Kit.material(Color("ffe6ad"), 1.6, 0.4)
			add_child(bulb)
	# Bench facing the path, and a mailbox.
	var bench := Node3D.new(); bench.name = "ParkBench"; bench.position = Vector3(door.x + 3.4, 0, door.y + 5.2); bench.rotation.y = -PI * 0.5
	add_child(bench)
	Kit.box(bench, "Seat", Vector3(0, 0.42, 0), Vector3(1.4, 0.07, 0.42), wood)
	Kit.box(bench, "Back", Vector3(0, 0.7, -0.19), Vector3(1.4, 0.32, 0.06), wood)
	for x in [-0.6, 0.6]: Kit.box(bench, "Leg", Vector3(x, 0.2, 0), Vector3(0.07, 0.4, 0.36), dark)
	var mailbox := Node3D.new(); mailbox.name = "Mailbox"; mailbox.position = Vector3(door.x - 2.6, 0, door.y + 2.3); add_child(mailbox)
	Kit.box(mailbox, "Post", Vector3(0, 0.45, 0), Vector3(0.08, 0.9, 0.08), wood)
	Kit.box(mailbox, "Box", Vector3(0, 1.0, 0), Vector3(0.36, 0.26, 0.5), Kit.material(Color("e0715b"), 0.0, 0.6))
	Kit.box(mailbox, "Flag", Vector3(0.2, 1.1, -0.05), Vector3(0.02, 0.18, 0.08), Kit.material(Color("ffd45e"), 0.0, 0.6))
	# Club sign at the path entrance with the team mark.
	var sign := Node3D.new(); sign.name = "ClubSign"; sign.position = Vector3(door.x + 2.3, 0, door.y + 10.5); add_child(sign)
	for x in [-0.75, 0.75]: Kit.box(sign, "SignPost", Vector3(x, 0.55, 0), Vector3(0.09, 1.1, 0.09), wood)
	Kit.box(sign, "SignBoard", Vector3(0, 1.0, 0.02), Vector3(1.8, 0.62, 0.08), Kit.material(Color("f6ecd2"), 0.0, 0.8))
	Kit.box(sign, "SignRoof", Vector3(0, 1.38, 0.02), Vector3(1.96, 0.1, 0.22), Kit.material(Color("4f8a69"), 0.0, 0.7))
	var title := Label3D.new(); title.name = "ClubSignText"; title.text = team.to_upper() if not team.is_empty() else "CLUB"
	title.font = Kit.Base.font(); title.font_size = 64; title.pixel_size = 0.0042; title.modulate = Color("2e4a3c"); title.outline_size = 0
	title.position = Vector3(0.2, 1.0, 0.07); title.double_sided = false; sign.add_child(title)
	var mark := Kit.logo_texture(team, 160)
	if mark:
		var logo := Sprite3D.new(); logo.texture = mark; logo.pixel_size = 0.36 / float(maxi(1, mark.get_height()))
		logo.position = Vector3(-0.62, 1.0, 0.07); logo.double_sided = false; sign.add_child(logo)
	# Low wooden fence along the front of the yard.
	var fence := SurfaceTool.new(); fence.begin(Mesh.PRIMITIVE_TRIANGLES)
	var fence_colour := Color(WOOD.r, WOOD.g, WOOD.b, 1.0)
	for side in [-1.0, 1.0]:
		var start: float = door.x + side * 2.2
		for i in range(7):
			var x: float = start + side * i * 1.1
			ChickenMesh._box(fence, Vector3(x, 0.32, door.y + 11.4), Vector3(0.1, 0.64, 0.1), fence_colour)
		ChickenMesh._box(fence, Vector3(start + side * 3.3, 0.48, door.y + 11.4), Vector3(6.7, 0.07, 0.05), fence_colour)
		ChickenMesh._box(fence, Vector3(start + side * 3.3, 0.24, door.y + 11.4), Vector3(6.7, 0.07, 0.05), fence_colour)
	var fence_mesh := MeshInstance3D.new(); fence_mesh.name = "FrontFence"; fence_mesh.mesh = fence.commit()
	var fence_mat := StandardMaterial3D.new(); fence_mat.vertex_color_use_as_albedo = true; fence_mat.roughness = 0.85
	fence_mesh.material_override = fence_mat; add_child(fence_mesh)

func _batch(id: String, mesh: ArrayMesh, poses: Array[Transform3D], shadows: bool, tint: Color = Color.WHITE, tints: Array[Color] = []) -> void:
	if poses.is_empty(): return
	var instances := MultiMesh.new(); instances.transform_format = MultiMesh.TRANSFORM_3D
	instances.use_custom_data = true; instances.use_colors = true
	instances.mesh = mesh; instances.instance_count = poses.size()
	for i in range(poses.size()):
		instances.set_instance_transform(i, poses[i])
		instances.set_instance_color(i, Color.WHITE)
		var colour := tints[i] if i < tints.size() else tint
		# Gentle per-instance variation in leaf colour.
		if tints.is_empty(): colour = colour.lerp(Color(0.9, 1.0, 0.85), rng.randf() * 0.25)
		instances.set_instance_custom_data(i, colour)
	var node := MultiMeshInstance3D.new(); node.name = id; node.multimesh = instances
	node.material_override = ChickenMesh.material()
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)
