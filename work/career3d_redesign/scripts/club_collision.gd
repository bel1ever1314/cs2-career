extends RefCounted
## Physics is authored separately from decoration: one flat floor, solid walls,
## furniture footprints, and NPCs. Tiny keys, cups and plank seams are not floors.
## This avoids jitter on decorative bevels. Coordinates below are Godot Y-up.
var count := 0
var audit: Array[Dictionary] = []

func box(parent: Node3D,id: String,center: Vector3,size: Vector3) -> void:
	var body := StaticBody3D.new()
	body.name = "Solid_"+id.validate_node_name()
	body.collision_layer = 1
	# The presentation's walls are intentionally low. The dialogue system
	# also checks their footprint, while allowing conversation over desks.
	for token in ["wall","partition","boundary","jamb"]:
		if token in id.to_lower():body.collision_layer=9;break
	body.collision_mask = 2
	body.position = center
	var shape := BoxShape3D.new()
	shape.size = size
	var collision := CollisionShape3D.new()
	collision.shape = shape
	body.add_child(collision)
	parent.add_child(body)
	count += 1
	audit.append({"id":id,"center":[center.x,center.y,center.z],"size":[size.x,size.y,size.z]})

func build(parent: Node3D,model: Node3D) -> void:
	box(parent,"walk_floor",Vector3(0,.065,0),Vector3(24.5,.31,19.2)) # top .22
	box(parent,"south_boundary",Vector3(0,1.2,9.38),Vector3(25,.0+2.4,.20))
	box(parent,"west_boundary",Vector3(-12.29,1.3,0),Vector3(.18,2.6,18.8))
	box(parent,"east_boundary",Vector3(12.29,1.3,0),Vector3(.18,2.6,18.8))
	box(parent,"north_boundary",Vector3(0,1.3,-8.83),Vector3(24.7,2.6,.18))
	var names := ["rear wall","external wall","partition","hall wall","oak jamb","entrance timber post",
		"long five player desktop","oak tabletop","chair seat","sofa base","sofa back","sofa arm",
		"tv console","kitchen rear cabinet","side lower cabinet","fridge","prep island",
		"reception oak desk","honours cabinet side","honours cabinet dark backing","dining sideboard"]
	for node in model.find_children("*","MeshInstance3D",true,false):
		var mesh := node as MeshInstance3D
		var n := str(mesh.name).replace("_"," ").to_lower()
		var include := false
		for pattern in names:
			if n.contains(pattern): include = true; break
		if n.contains("cap") or n.contains("panel") or n.contains("note") or n.contains("handle") or n.contains("door"):
			include = false
		if n.ends_with(" pot") or n.contains(" pot "): include = true
		if not include: continue
		var bounds: AABB = mesh.global_transform * mesh.get_aabb()
		var size := bounds.size
		# Furniture has a continuous footprint down to the floor; don't walk
		# under tables, between disconnected chair legs, or through a fridge.
		var top := bounds.end.y
		size.y = maxf(.40,top-.22)
		var center := bounds.get_center()
		center.y = .22+size.y*.5
		box(parent,str(mesh.name),center,size)
	print("CLUB_COLLIDERS ",count)
