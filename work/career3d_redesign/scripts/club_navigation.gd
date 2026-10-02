extends RefCounted
## Build once from the same collision footprints as the scene. A* only runs
## on task changes/recovery, not once per frame. Inflation includes NPC radius.
const CELL:=.25
const ORIGIN:=Vector2(-12.25,-9.0)
var grid:=AStarGrid2D.new()
var queries:=0
func build(audit: Array) -> void:
	grid.region=Rect2i(0,0,99,74);grid.cell_size=Vector2(CELL,CELL);grid.offset=ORIGIN
	grid.diagonal_mode=AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
	grid.default_compute_heuristic=AStarGrid2D.HEURISTIC_OCTILE
	grid.default_estimate_heuristic=AStarGrid2D.HEURISTIC_OCTILE;grid.update()
	for row in audit:
		if row["id"]=="walk_floor":continue
		var c: Array=row["center"];var s: Array=row["size"]
		var lo:=cell(Vector3(float(c[0])-float(s[0])*.5-.30,0,float(c[2])-float(s[2])*.5-.30))
		var hi:=cell(Vector3(float(c[0])+float(s[0])*.5+.30,0,float(c[2])+float(s[2])*.5+.30))
		for x in range(maxi(0,lo.x),mini(99,hi.x+1)):
			for z in range(maxi(0,lo.y),mini(74,hi.y+1)):
				var p:=world(Vector2i(x,z))
				if absf(p.x-float(c[0]))<=float(s[0])*.5+.30 and absf(p.z-float(c[2]))<=float(s[2])*.5+.30:grid.set_point_solid(Vector2i(x,z))
func cell(p: Vector3) -> Vector2i:return Vector2i(roundi((p.x-ORIGIN.x)/CELL),roundi((p.z-ORIGIN.y)/CELL))
func world(c: Vector2i) -> Vector3:return Vector3(ORIGIN.x+c.x*CELL,.223,ORIGIN.y+c.y*CELL)
func walkable(c: Vector2i) -> bool:return grid.is_in_boundsv(c) and not grid.is_point_solid(c)
func nearest(p: Vector3) -> Vector2i:
	var center:=cell(p);var best:=Vector2i(-1,-1);var distance:=INF
	for x in range(center.x-4,center.x+5):
		for z in range(center.y-4,center.y+5):
			var c:=Vector2i(x,z)
			if walkable(c):
				var d:=Vector2(world(c).x-p.x,world(c).z-p.z).length_squared()
				if d<distance:best=c;distance=d
	return best
func segment(a: Vector3,b: Vector3) -> bool:
	var steps:=maxi(1,ceili(a.distance_to(b)/.10))
	for i in range(steps+1):
		if not walkable(cell(a.lerp(b,float(i)/steps))):return false
	return true
func path(a: Vector3,b: Vector3,people: Array=[]) -> Array[Vector3]:
	queries+=1
	var start:=nearest(a);var end:=nearest(b)
	var result: Array[Vector3]=[]
	if start.x<0 or end.x<0:return result
	# Temporary bodies participate in both A* and path smoothing. Restore the
	# static grid afterwards; an occupied goal is never replaced by a nearby job.
	var temporary: Array[Vector2i]=[]
	for body in people:
		var p: Vector3=body["position"];var radius: float=float(body.get("radius",.55))
		var center:=cell(p);var reach:=ceili(radius/CELL)+1
		for x in range(center.x-reach,center.x+reach+1):
			for z in range(center.y-reach,center.y+reach+1):
				var c:=Vector2i(x,z)
				if c==start or not walkable(c):continue
				if Vector2(world(c).x-p.x,world(c).z-p.z).length()<radius:
					grid.set_point_solid(c);temporary.append(c)
	if not walkable(end):
		for c in temporary:grid.set_point_solid(c,false)
		return result
	var cells:=grid.get_id_path(start,end)
	if cells.is_empty():
		for c in temporary:grid.set_point_solid(c,false)
		return result
	var raw: Array[Vector3]=[a]
	for c in cells:raw.append(world(c))
	var index:=0
	while index<raw.size()-1:
		var next:=index+1
		for j in range(index+2,raw.size()):
			if segment(raw[index],raw[j]):next=j
			else:break
		result.append(raw[next]);index=next
	for c in temporary:grid.set_point_solid(c,false)
	return result
