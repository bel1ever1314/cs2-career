extends Node3D
## Replaces the model's decorative cups with the current club's saved honours.
const UI = preload("res://scripts/phone_ui.gd")
var signature := ""
var trophy_nodes: Array[Node3D] = []
var title: Label3D

func setup(model: Node3D) -> void:
	for mesh in model.find_children("*", "MeshInstance3D", true, false):
		var normalized := str(mesh.name).replace("_", " ").to_lower()
		if normalized.begins_with("trophy foot") or normalized.begins_with("trophy stem") or normalized.begins_with("trophy cup") or normalized.begins_with("trophy handle") or normalized == "honours label":
			mesh.visible = false
	title = _label("", Vector3(1.93, 2.57, 4.56), .0027)

func refresh(ctx: Dictionary) -> void:
	var honours: Dictionary = ctx.get("club_trophies", {})
	var rows: Array = honours.get("rows", [])
	var team := str(honours.get("team", ctx.get("team", {}).get("name", "")))
	var next_signature := JSON.stringify([team, rows])
	if next_signature == signature: return
	signature = next_signature
	for child in trophy_nodes:
		remove_child(child)
		child.queue_free()
	trophy_nodes.clear()
	if is_instance_valid(title): title.text = team + " · " + str(rows.size()) + " 座冠军奖杯" if not team.is_empty() else "俱乐部荣誉"
	# Six shelf places represent the latest titles; the panel retains the full list.
	for index in mini(6, rows.size()):
		var cup := _cup("ClubChampion" + str(index))
		cup.position = Vector3(1.56 + float(index % 2) * .74, .335 + float(floori(index / 2.0)) * .73, 4.15)
		cup.set_meta("honour", rows[index].duplicate(true))
		trophy_nodes.append(cup)
		var row: Dictionary = rows[index]
		var plaque := _label(str(row.get("short", row.get("event", "冠军"))), Vector3(0, -.015, .31), .00125, cup)
		plaque.font_size = 36
		plaque.width = 270
		plaque.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		plaque.text += "\n" + str(row.get("year", ""))

func _material(color: Color) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.metallic = .65
	mat.roughness = .3
	return mat

func _mesh(shape: Mesh, at: Vector3, color: Color, parent: Node3D) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	mesh.mesh = shape
	mesh.position = at
	mesh.material_override = _material(color)
	parent.add_child(mesh)
	return mesh

func _cup(id: String) -> Node3D:
	var cup := Node3D.new()
	cup.name = id
	add_child(cup)
	var base := BoxMesh.new()
	base.size = Vector3(.25, .07, .2)
	_mesh(base, Vector3(0, .035, 0), Color("29443a"), cup)
	var stem := CylinderMesh.new()
	stem.top_radius = .036; stem.bottom_radius = .05; stem.height = .2; stem.radial_segments = 16
	_mesh(stem, Vector3(0, .16, 0), Color("d9ac48"), cup)
	var bowl := CylinderMesh.new()
	bowl.top_radius = .145; bowl.bottom_radius = .05; bowl.height = .22; bowl.radial_segments = 24
	_mesh(bowl, Vector3(0, .36, 0), Color("e0b75a"), cup)
	for side in [-1.0, 1.0]:
		var ring := TorusMesh.new()
		ring.inner_radius = .05; ring.outer_radius = .072; ring.rings = 12; ring.ring_segments = 12
		var handle := _mesh(ring, Vector3(side * .14, .35, 0), Color("d9ac48"), cup)
		handle.rotation.x = PI / 2
	return cup

func _label(text: String, at: Vector3, pixel: float, parent: Node3D = null) -> Label3D:
	var label := Label3D.new()
	label.text = text
	label.font = UI.font()
	label.font_size = 48
	label.pixel_size = pixel
	label.position = at
	label.modulate = Color("284640")
	label.outline_size = 5
	(self if parent == null else parent).add_child(label)
	return label
