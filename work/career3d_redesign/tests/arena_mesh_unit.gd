extends SceneTree
## Asset-independent geometry and rhythm checks; full travel uses arena-test.
var failures := 0

func check(ok: bool, label: String) -> void:
	if not ok:
		failures += 1
	print("ARENA_UNIT ", "PASS " if ok else "FAIL ", label)

func _init() -> void:
	var crowd := preload("res://scripts/arena_chicken_crowd.gd").new()
	var body: ArrayMesh = crowd._chicken_mesh(false)
	check(absf(body.get_aabb().position.y - 0.475) < 0.00001, "body geometry contacts cushion at .475 m")
	var furniture: ArrayMesh = crowd._seat_and_feet_mesh()
	var arrays: Array = furniture.surface_get_arrays(0)
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var colors: PackedColorArray = arrays[Mesh.ARRAY_COLOR]
	var feet_min := INF
	var cushion_max := -INF
	for i in range(vertices.size()):
		if colors[i].is_equal_approx(Color("efa949")):
			feet_min = minf(feet_min, vertices[i].y)
		if colors[i].is_equal_approx(Color("29435b")) and vertices[i].z > 0.0:
			cushion_max = maxf(cushion_max, vertices[i].y)
	check(absf(feet_min - 0.018) < 0.00001, "foot mesh soles stay at original row floor +18 mm")
	check(absf(cushion_max - body.get_aabb().position.y) < 0.00001, "body touches actual chair cushion geometry")
	var arena := preload("res://scripts/arena_atmosphere.gd").new()
	check(arena.beat_state(8.0 * 60.0 / 112.0)["pulse"] > 0.95, "accent reaches downbeat")
	check(arena.beat_state(8.5 * 60.0 / 112.0)["pulse"] < 0.01, "accent releases between beats")
	check(arena.beat_state(23.0)["phrase"] == 0.0, "cue settles after phrase")
	crowd.free()
	arena.free()
	quit(0 if failures == 0 else 1)
