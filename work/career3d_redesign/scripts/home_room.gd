extends RefCounted
## Keep the authored shell, bed and workstation, but leave the lounge to the
## player. Do not edit the source model or touch purchased/saved placements.
const OPTIONAL_PREFIXES := ["large oval rug", "rug ", "coffee table", "round coffee table",
	"notebook", "tea cup", "tea", "cup handle", "gamepad", "beanbag", "cushion",
	"plush", "wall floating shelf", "shelf ", "trophy ", "entry cabinet", "cabinet ",
	"entry plant", "soft slippers", "slipper opening", "woven storage basket", "basket "]

static func simplify(model: Node3D) -> void:
	if not is_instance_valid(model) or model.has_meta("home_simplified"): return
	for node in model.find_children("*", "MeshInstance3D", true, false):
		var label := str(node.name).replace("_", " ").to_lower()
		for prefix in OPTIONAL_PREFIXES:
			if label.begins_with(prefix):
				node.visible = false
				break
	model.set_meta("home_simplified", true)

## A player may save a sofa where they were standing before opening the editor.
## Move only if intersecting a new solid; never teleport on ordinary refresh.
static func clear_player(room: Node3D, home: Dictionary) -> void:
	var player: Node3D = room.player
	if not is_instance_valid(player): return
	var solids: Array = home.get("fixed", []).duplicate(true)
	var items := {}
	for item in home.get("catalog", []): items[str(item.id)] = item
	for row in home.get("placed", []):
		var item: Dictionary = items.get(str(row.item), {})
		if not item.get("solid", false): continue
		var size: Array = item.get("footprint", [.5, .5])
		var turned := int(row.get("rotation", 0)) in [90, 270]
		solids.append([row.x, row.z, size[1] if turned else size[0], size[0] if turned else size[1]])
	var here := Vector2(player.position.x, player.position.z)
	if _free(here, solids): return
	var best := Vector2.INF
	var distance := INF
	for x in range(-23, 24):
		for z in range(-19, 21):
			var point := Vector2(x / 8.0, z / 8.0)
			if _free(point, solids) and point.distance_squared_to(here) < distance:
				best = point; distance = point.distance_squared_to(here)
	if best.is_finite():
		player.position = Vector3(best.x, .12, best.y)
		player.velocity = Vector3.ZERO
		player.reset_physics_interpolation()

static func _free(point: Vector2, solids: Array) -> bool:
	for box in solids:
		var delta := (point - Vector2(box[0], box[1])).abs() - Vector2(box[2], box[3]) / 2.0
		if Vector2(maxf(0, delta.x), maxf(0, delta.y)).length_squared() < .31 * .31: return false
	return true
