extends RefCounted
## Real triangle surfaces for the curved building, boxes for furniture.
## No per-frame mesh scans, pathfinding or spectator physics.
var count:=0
var audit: Array[Dictionary]=[]

func box(parent: Node,name: String,center: Vector3,size: Vector3) -> void:
	var body:=StaticBody3D.new();body.name="Solid_"+name;body.collision_layer=1;body.collision_mask=2
	var shape:=CollisionShape3D.new();var primitive:=BoxShape3D.new();primitive.size=size
	shape.shape=primitive;body.position=center;body.add_child(shape);parent.add_child(body);count+=1

func build(parent: Node3D,model: Node3D) -> void:
	for node in model.find_children("*","MeshInstance3D",true,false):
		var mesh:=node as MeshInstance3D
		var n:=str(mesh.name).replace("_"," ").to_lower()
		var structural:=false
		for token in ["plaza and arena floor","bowl dark floor","event floor","rear stage platform","performance floor","stage oak border","champions runway","centre aisle","foyer floor","terrace","circulation ring","outside rail","safety rail","walk tunnel floor","walk tunnel lining","walk tunnel ceiling","public stair","stage rear acoustic wall"]:
			if token in n:structural=true;break
		if structural:
			if mesh.mesh.get_faces().is_empty():continue
			var body:=StaticBody3D.new();body.collision_layer=1;body.collision_mask=2
			body.name="Surface_"+str(mesh.name)
			var shape:=CollisionShape3D.new();shape.shape=mesh.mesh.create_trimesh_shape()
			body.add_child(shape);parent.add_child(body);body.global_transform=mesh.global_transform
			count+=1
		elif "crowd" not in n:
			var solid:=false
			for token in ["turnstile","welcome column","concession counter","short return wall","team competition desk","team desk front","trophy stone base","backstage team block","tree planter","gate sign tower"]:
				if token in n:solid=true;break
			if solid:
				var aabb: AABB=mesh.global_transform*mesh.get_aabb()
				box(parent,str(mesh.name),aabb.get_center(),aabb.size)
	# Dense audience blocks are not corridors. One collider per bank instead
	# of thousands of capsules; the centre and side aisles stay free.
	for side in [-1,1]:
		var bounds:=AABB();var found:=false
		for node in model.find_children("Crowd*","MeshInstance3D",true,false):
			var aabb: AABB=node.global_transform*node.get_aabb()
			var p:=aabb.get_center()
			if p.y<2.7 and absf(p.x)<13 and p.z>-8 and p.z<18 and signf(p.x)==side:
				bounds=bounds.merge(aabb) if found else aabb;found=true
		if found:
			var size:=bounds.size;size.y=1.8
			var center:=bounds.get_center();center.y=1.3
			box(parent,"FloorAudience"+str(side),center,size)
			audit.append({"bank":side,"center":str(center),"size":str(size)})
	# Prevent accidental walking off the cutaway model's presentation plinth.
	box(parent,"FrontBoundary",Vector3(0,2,58.3),Vector3(107,4,.3))
	box(parent,"BackBoundary",Vector3(0,2,-34.3),Vector3(107,4,.3))
	for side in [-1,1]:box(parent,"SideBoundary"+str(side),Vector3(side*53.3,2,12),Vector3(.3,4,93))
	# Visual stair treads retain their shape. A continuous walking surface
	# avoids catching the capsule toe and bumping the first-person camera.
	ramp(parent,"StageStairs",9.0,-7.80,.44,-10.20,1.68)
	box(parent,"StageStairLanding",Vector3(0,.94,-10.61),Vector3(18,1.48,.82))
	print("ARENA_COLLIDERS ",count," ",JSON.stringify(audit))

func ramp(parent: Node,id: String,half_width: float,start_z: float,start_y: float,end_z: float,end_y: float) -> void:
	var points:=PackedVector3Array()
	for x in [-half_width,half_width]:
		points.append(Vector3(x,start_y,start_z));points.append(Vector3(x,end_y,end_z))
		points.append(Vector3(x,.2,start_z));points.append(Vector3(x,.2,end_z))
	var shape:=ConvexPolygonShape3D.new();shape.points=points
	var collision:=CollisionShape3D.new();collision.shape=shape
	var body:=StaticBody3D.new();body.name=id;body.collision_layer=1;body.collision_mask=2
	body.add_child(collision);parent.add_child(body);count+=1
