extends RefCounted
## Actual map NAV projected into radar pixels. This is a conservative 2D
## approximation, NOT the CS2 collision/visibility engine or a replay.
## Offline masks and directed portal edges make every runtime query bounded.
## Source NAV qualifies nominal agent centres; it is not a physical wall BSP.

const DEFAULT_RADIUS := 3.5
const MAX_PATH_CACHE := 256
const DIRECTIONS := [Vector2i(1,0),Vector2i(1,1),Vector2i(0,1),Vector2i(-1,1),Vector2i(-1,0),Vector2i(-1,-1),Vector2i(0,-1),Vector2i(1,-1)]

class PortalGraph extends AStar2D:
	var region_ids := PackedByteArray()
	var positions := PackedVector2Array()
	var region_count := 0
	var factors_by_side: Dictionary = {}
	var pair_factors := PackedFloat64Array()
	var layered := false
	var traversal_costs: Dictionary = {}
	func set_side(side: String) -> void:
		pair_factors=factors_by_side.get(side,factors_by_side[""])
	func _compute_cost(from_id: int, to_id: int) -> float:
		var key := str(from_id)+":"+str(to_id)
		if traversal_costs.has(key):return float(traversal_costs[key])
		var distance := positions[from_id].distance_to(positions[to_id])
		if region_ids[from_id]==region_ids[to_id]:return distance
		return distance*pair_factors[int(region_ids[from_id])*region_count+int(region_ids[to_id])]
	func _estimate_cost(from_id: int, to_id: int) -> float:
		if layered:
			var from := Vector2(positions[from_id].x,fposmod(positions[from_id].y,1024.0))
			var to := Vector2(positions[to_id].x,fposmod(positions[to_id].y,1024.0))
			return from.distance_to(to)*.82
		return positions[from_id].distance_to(positions[to_id])*.82

var data: Dictionary = {}
var bounds := Rect2(Vector2.ZERO, Vector2(1024,1024))
var waypoint_positions: Dictionary = {}
var waypoint_regions: Dictionary = {}
var knowledge: Dictionary = {}
var path_bias_uses := 0
var watch_bias_uses := 0
var watch_fallback_uses := 0
var _width := 256
var _height := 256
var _cell_size := 4.0
var _image_width := 1024
var _image_height := 1024
var _walk_bits := PackedByteArray()
var _edges := PackedByteArray()
var _regions: Array = []
var _region_ids := PackedByteArray()
var _positions := PackedVector2Array()
var _collision := PackedByteArray()
var _clearance := PackedByteArray()
var _sight := PackedByteArray()
var _graphs: Dictionary = {}
var _paths: Dictionary = {}
var _path_fifo: Array[String] = []
var _route_factors: Dictionary = {}
var _region_pair_factors: Dictionary = {}
var _region_points: Dictionary = {}
var _watch_anchors: Array = []
var _centre_navigation := false
var _nav_agent_radius := DEFAULT_RADIUS
var _layered := false
var _traversals: Dictionary = {}

func setup(source: Dictionary) -> void:
	data = source.duplicate(true)
	var size: Array = data.get("world_size",[1024,1024])
	_image_width = int(size[0]); _image_height = int(size[1])
	bounds = Rect2(Vector2.ZERO,Vector2(_image_width,_image_height))
	var geometry: Dictionary = data.get("geometry",{})
	var decoded = JSON.parse_string(FileAccess.get_file_as_string(str(geometry.get("grid_file",""))))
	assert(decoded is Dictionary,"Map grid data missing: " + str(data.get("map", "")))
	var grid: Dictionary = decoded
	_layered = str(geometry.get("kind","")) == "layered_actual_NAV"
	_traversals.clear()
	for row in grid.get("traversal_links",[]):
		_traversals[str(int(row["from"]))+":"+str(int(row["to"]))]=row
	_centre_navigation = str(grid.get("navigation_space",geometry.get("navigation_space",""))) == "NAV_agent_centres"
	_nav_agent_radius = float(grid.get("actor_clearance",geometry.get("actor_clearance",DEFAULT_RADIUS)))
	_width=int(grid["width"]); _height=int(grid["height"]); _cell_size=float(grid["cell_size"])
	_walk_bits=Marshalls.base64_to_raw(str(grid["walk_bits"]))
	_edges=Marshalls.base64_to_raw(str(grid["edge_bits"]))
	_region_ids=Marshalls.base64_to_raw(str(grid["region_indices"]))
	_regions=grid["regions"]
	assert(_edges.size()==_width*_height and _region_ids.size()==_edges.size(),"Map grid size mismatch")
	_positions.resize(_width*_height)
	for id in range(_positions.size()):
		_positions[id]=Vector2((id%_width+.5)*_cell_size,(floori(float(id)/_width)+.5)*_cell_size)
	_collision=_mask(str(geometry["collision_mask"]))
	_clearance=_mask(str(geometry["clearance_mask"]))
	_sight=_mask(str(geometry["sight_mask"]))
	waypoint_positions.clear(); waypoint_regions.clear(); _region_points.clear()
	for row in data.get("waypoints",[]):
		var id := str(row["id"])
		var point := vec(row["position"])
		var region := str(row.get("source_region",""))
		waypoint_positions[id]=point; waypoint_regions[id]=region
		if not _region_points.has(region): _region_points[region]=[]
		_region_points[region].append(point)
	_watch_anchors=data.get("watch_anchors",[])
	_graphs.clear(); _paths.clear()
	var supplied = data.get("botlab_knowledge",{})
	apply_knowledge(supplied if supplied is Dictionary else {})

func _mask(path: String) -> PackedByteArray:
	var image: Image
	# Imported resources survive a packed export. Source-byte fallback also
	# supports clean headless QA, without triggering a missing-loader warning.
	if not FileAccess.file_exists(path) and ResourceLoader.exists(path,"Texture2D"):
		var texture = load(path)
		if texture is Texture2D:image=texture.get_image()
	if image == null and FileAccess.file_exists(path):
		var source_bytes := FileAccess.get_file_as_bytes(path)
		image=Image.new()
		if image.load_png_from_buffer(source_bytes)!=OK:image=null
	assert(image != null and image.get_width()==_image_width and image.get_height()==_image_height,"Map mask missing: "+path)
	image.convert(Image.FORMAT_L8)
	return image.get_data()

func vec(value: Array) -> Vector2:
	return Vector2(float(value[0]),float(value[1]))

func world_to_pixel(point: Vector2) -> Vector2:
	var overview: Dictionary=data["radar"]["overview"]
	return Vector2((point.x-float(overview["pos_x"]))/float(overview["scale"]),(float(overview["pos_y"])-point.y)/float(overview["scale"]))

func pixel_to_world(point: Vector2) -> Vector2:
	var overview: Dictionary=data["radar"]["overview"]
	return Vector2(float(overview["pos_x"])+point.x*float(overview["scale"]),float(overview["pos_y"])-point.y*float(overview["scale"]))

func _pixel_id(point: Vector2) -> int:
	if not point.is_finite() or point.x<0 or point.y<0 or point.x>=_image_width or point.y>=_image_height:return -1
	return floori(point.y)*_image_width+floori(point.x)

func _cell(point: Vector2) -> Vector2i:
	return Vector2i(floori(point.x/_cell_size),floori(point.y/_cell_size))

func _cell_id(cell: Vector2i) -> int:
	if cell.x<0 or cell.y<0 or cell.x>=_width or cell.y>=_height:return -1
	return cell.y*_width+cell.x

func _cell_center(id: int) -> Vector2:
	return _positions[id]

func _cell_walkable(id: int, radius: float) -> bool:
	if id<0 or id>=_width*_height or (_walk_bits[id>>3] & (1<<(id&7)))==0:return false
	return is_walkable(_cell_center(id),radius)

func is_walkable(point: Vector2, radius: float = 0.0) -> bool:
	var pixel := _pixel_id(point)
	if pixel<0 or _collision[pixel]!=0:return false
	if radius<=0:return true
	var cell_id := _cell_id(_cell(point))
	if cell_id<0 or (_walk_bits[cell_id>>3] & (1<<(cell_id&7)))==0:return false
	return float(_clearance[pixel])*.25 >= _required_clearance(radius)

func _required_clearance(radius: float) -> float:
	# Source NAV already qualifies the nominal agent centre. Re-eroding that
	# centre space by the whole body radius closes real narrow door portals.
	# Larger agents still need their excess body radius plus pixel uncertainty.
	var extra := maxf(0.0,radius-_nav_agent_radius) if _centre_navigation else radius
	return extra+.75 if extra>0 else 0.0

func _pixel_clear(pixel: Vector2i, radius: float, movement: bool) -> bool:
	if pixel.x<0 or pixel.y<0 or pixel.x>=_image_width or pixel.y>=_image_height:return false
	var id := pixel.y*_image_width+pixel.x
	if not movement:return _sight[id]==0
	if _collision[id]!=0:return false
	var cell_id := _cell_id(Vector2i(floori(pixel.x/_cell_size),floori(pixel.y/_cell_size)))
	if cell_id<0 or (_walk_bits[cell_id>>3] & (1<<(cell_id&7)))==0:return false
	return float(_clearance[id])*.25>=_required_clearance(radius)

func _edge_allowed(from_cell: Vector2i, to_cell: Vector2i) -> bool:
	if from_cell==to_cell:return true
	var difference := to_cell-from_cell
	var direction := DIRECTIONS.find(difference)
	var id := _cell_id(from_cell)
	return id>=0 and direction>=0 and (_edges[id] & (1<<direction))!=0

func segment_blocked(start: Vector2, finish: Vector2, radius: float = 0.0) -> bool:
	if radius<=0:
		return _trace_fraction(start,finish,0.0,false)<1.0
	return _trace_fraction(start,finish,radius,true)<1.0

func _trace_fraction(start: Vector2, finish: Vector2, radius: float, movement: bool) -> float:
	if not start.is_finite() or not finish.is_finite():return 0.0
	# Floor pages are distinct terrain. Even aligned XY cannot give movement
	# or visibility between floors without an explicit traversal action.
	if _layered and layer_at(start)!=layer_at(finish):return 0.0
	if movement and not is_walkable(start,radius):return 0.0
	var pixel := Vector2i(floori(start.x),floori(start.y))
	if not _pixel_clear(pixel,radius,movement):return 0.0
	var direction := finish-start
	var length := direction.length()
	if length<.000001:return 1.0
	var step := Vector2i(int(signf(direction.x)),int(signf(direction.y)))
	var next_x := ((pixel.x+(1 if step.x>0 else 0))-start.x)/direction.x if step.x!=0 else INF
	var next_y := ((pixel.y+(1 if step.y>0 else 0))-start.y)/direction.y if step.y!=0 else INF
	var delta_x := absf(1.0/direction.x) if step.x!=0 else INF
	var delta_y := absf(1.0/direction.y) if step.y!=0 else INF
	var previous_cell := _cell(start)
	# Visit every crossed pixel and directed NAV cell boundary exactly once.
	# The result is independent of path length, frame speed or sampling phase.
	while minf(next_x,next_y)<1.0-1e-10:
		var fraction := minf(next_x,next_y)
		var blocked := false
		if absf(next_x-next_y)<1e-10:
			blocked=not _pixel_clear(pixel+Vector2i(step.x,0),radius,movement) or not _pixel_clear(pixel+Vector2i(0,step.y),radius,movement)
			pixel+=step;next_x+=delta_x;next_y+=delta_y
		elif next_x<next_y:
			pixel.x+=step.x;next_x+=delta_x
		else:
			pixel.y+=step.y;next_y+=delta_y
		blocked=blocked or not _pixel_clear(pixel,radius,movement)
		if movement:
			var cell := Vector2i(floori(pixel.x/_cell_size),floori(pixel.y/_cell_size))
			if cell!=previous_cell and not _edge_allowed(previous_cell,cell):blocked=true
			previous_cell=cell
		if blocked:return maxf(0.0,fraction-.001/length)
	# A negative-direction endpoint on an integer boundary belongs to its
	# floor() pixel, not the pixel beyond the requested segment.
	var final_pixel := Vector2i(floori(finish.x),floori(finish.y))
	if not _pixel_clear(final_pixel,radius,movement):return maxf(0.0,1.0-.001/length)
	if movement and previous_cell!=_cell(finish) and not _edge_allowed(previous_cell,_cell(finish)):return maxf(0.0,1.0-.001/length)
	return 1.0

func raycast_endpoint(start: Vector2, finish: Vector2, radius: float = 0.0) -> Vector2:
	return start.lerp(finish,_trace_fraction(start,finish,radius,radius>0))

func ray_end(start: Vector2, finish: Vector2, radius: float = 0.0) -> Vector2:
	return raycast_endpoint(start,finish,radius)

func visibility_fan(origin: Vector2, heading: Vector2, half_angle: float, distance: float, rays: int = 60) -> PackedVector2Array:
	var polygon := PackedVector2Array([origin])
	var forward := heading.normalized() if heading.length_squared()>.0001 else Vector2.RIGHT
	for index in range(maxi(2,rays)+1):
		var angle := lerpf(-half_angle,half_angle,float(index)/maxi(2,rays))
		polygon.append(raycast_endpoint(origin,origin+forward.rotated(angle)*distance))
	return polygon

func nearest_walkable(point: Vector2, radius: float = DEFAULT_RADIUS) -> Vector2:
	if is_walkable(point,radius):return point
	var id := _nearest_cell(point,radius)
	return _cell_center(id) if id>=0 else Vector2.INF

func _nearest_cell(point: Vector2, radius: float, as_destination: bool = false) -> int:
	if not point.is_finite():return -1
	var base := _cell(point.clamp(Vector2.ZERO,bounds.end-Vector2.ONE))
	var base_id := _cell_id(base)
	var needs_connection := is_walkable(point,radius)
	if _cell_walkable(base_id,radius) and _endpoint_cell_clear(point,base_id,radius,as_destination,needs_connection):return base_id
	var best := -1
	var distance := INF
	for ring in range(maxi(_width,_height)):
		for y in range(maxi(0,base.y-ring),mini(_height-1,base.y+ring)+1):
			if _layered and floori(float(y)/512)!=layer_at(point):continue
			for x in range(maxi(0,base.x-ring),mini(_width-1,base.x+ring)+1):
				if ring>0 and x>base.x-ring and x<base.x+ring and y>base.y-ring and y<base.y+ring:continue
				var id := y*_width+x
				if not _cell_walkable(id,radius):continue
				if not _endpoint_cell_clear(point,id,radius,as_destination,needs_connection):continue
				var candidate := point.distance_squared_to(_cell_center(id))
				if candidate<distance:distance=candidate;best=id
		if best>=0 and pow(maxf(0,(ring-1)*_cell_size),2)>distance:break
	return best

func _endpoint_cell_clear(point: Vector2, id: int, radius: float, as_destination: bool, required: bool) -> bool:
	if not required:return true # Off-floor click projection, not a movement leg.
	var center := _cell_center(id)
	return not segment_blocked(center,point,radius) if as_destination else not segment_blocked(point,center,radius)

func _graph_for(radius: float) -> PortalGraph:
	var key := ceili(maxf(DEFAULT_RADIUS,radius)*4)
	if _graphs.has(key):return _graphs[key]
	var graph := PortalGraph.new()
	graph.region_ids=_region_ids; graph.positions=_positions; graph.region_count=_regions.size()
	graph.factors_by_side=_region_pair_factors
	graph.layered=_layered
	graph.set_side("")
	graph.reserve_space(int(data.get("statistics",{}).get("walk_cells",16000)))
	var effective := key*.25
	for id in range(_width*_height):
		if _cell_walkable(id,effective):graph.add_point(id,_positions[id])
	for id in graph.get_point_ids():
		var cell := Vector2i(id%_width,floori(float(id)/_width))
		for bit in range(8):
			if (_edges[id] & (1<<bit))==0:continue
			var other := _cell_id(cell+DIRECTIONS[bit])
			if graph.has_point(other) and ((_centre_navigation and effective<=_nav_agent_radius) or not segment_blocked(_positions[id],_positions[other],effective)):
				graph.connect_points(id,other,false)
	for traversal_key in _traversals:
		var row: Dictionary=_traversals[traversal_key]
		var first := int(row["from"])
		var last := int(row["to"])
		if graph.has_point(first) and graph.has_point(last):
			graph.connect_points(first,last,false)
			var from := Vector2(_positions[first].x,fposmod(_positions[first].y,1024.0))
			var to := Vector2(_positions[last].x,fposmod(_positions[last].y,1024.0))
			graph.traversal_costs[traversal_key]=from.distance_to(to)+float(row["seconds"])*70.0
	_graphs[key]=graph
	return graph

func find_path(start: Vector2, finish: Vector2, radius: float = DEFAULT_RADIUS, side: String = "") -> Array[Vector2]:
	var origin := nearest_walkable(start,radius)
	var target := nearest_walkable(finish,radius)
	if not origin.is_finite() or not target.is_finite():return []
	var first := _nearest_cell(origin,radius)
	var last := _nearest_cell(target,radius,true)
	if first<0 or last<0:return []
	var key := str(first)+":"+str(last)+":"+str(ceili(radius*4))+":"+side.to_lower()
	var cached: Dictionary=_paths.get(key,{})
	if cached.is_empty():
		var graph := _graph_for(radius)
		graph.set_side(side.to_lower())
		var ids := graph.get_id_path(first,last)
		var raw: Array[Vector2]=[]
		var biased := false
		for index in range(1,ids.size()):
			raw.append(_cell_center(ids[index]))
			if graph.pair_factors[int(_region_ids[ids[index-1]])*_regions.size()+int(_region_ids[ids[index]])]<1:biased=true
		if ids.size()==1:raw.append(_cell_center(last))
		cached={"path":_simplify(_cell_center(first),raw,radius),"biased":biased}
		_cache_path(key,cached)
	if bool(cached["biased"]):path_bias_uses+=1
	var result: Array[Vector2]=[]
	result.assign(cached["path"])
	if result.is_empty():return result
	if origin.distance_squared_to(_cell_center(first))>.01 and segment_blocked(origin,result[0],radius):result.push_front(_cell_center(first))
	if result[-1].distance_squared_to(target)>.00000001:result.append(target)
	return result

func _cache_path(key: String, path: Dictionary) -> void:
	# One eviction preserves other warmed routes instead of clearing all 256.
	if _paths.has(key):
		_paths[key]=path
		return
	if _paths.size()>=MAX_PATH_CACHE:_paths.erase(_path_fifo.pop_front())
	_paths[key]=path
	_path_fifo.append(key)

func _simplify(start: Vector2, path: Array[Vector2], radius: float) -> Array[Vector2]:
	var result: Array[Vector2]=[]
	var point := start
	var index := 0
	while index<path.size():
		var furthest := index
		for next in range(path.size()-1,index,-1):
			if not segment_blocked(point,path[next],radius):furthest=next;break
		result.append(path[furthest]);point=path[furthest];index=furthest+1
	return result

func constrain_motion(start: Vector2, finish: Vector2, radius: float = DEFAULT_RADIUS) -> Vector2:
	var origin := start if is_walkable(start,radius) else nearest_walkable(start,radius)
	if not origin.is_finite():return start
	if not segment_blocked(origin,finish,radius):return finish
	var fraction := _trace_fraction(origin,finish,radius,true)
	var result := origin.lerp(finish,fraction)
	# Vector2 uses single precision: an exact boundary fraction may round to
	# its blocked side. Keep the returned complete displacement legal too.
	if segment_blocked(origin,result,radius):
		var low := 0.0
		var high := fraction
		for iteration in range(16):
			var middle := (low+high)*.5
			if segment_blocked(origin,origin.lerp(finish,middle),radius):high=middle
			else:low=middle
		result=origin.lerp(finish,low)
	var horizontal := Vector2(finish.x,result.y)
	if not segment_blocked(result,horizontal,radius) and not segment_blocked(origin,horizontal,radius):result=horizontal
	var vertical := Vector2(result.x,finish.y)
	if not segment_blocked(result,vertical,radius) and not segment_blocked(origin,vertical,radius):result=vertical
	return result

func _region_name(id: int) -> String:
	if id<0 or id>=_region_ids.size() or _region_ids[id]>=_regions.size():return ""
	return str(_regions[_region_ids[id]])

func region_at(point: Vector2) -> String:
	var id := _cell_id(_cell(point))
	var region := _region_name(id)
	if region.is_empty():region=_region_name(_nearest_cell(point,DEFAULT_RADIUS))
	return region

func positions_for_region(region: String) -> Array[Vector2]:
	var result: Array[Vector2]=[]
	result.assign(_region_points.get(region,[]))
	return result

func nearest_waypoint_id(point: Vector2) -> String:
	var closest := ""
	var distance := INF
	for id in waypoint_positions:
		var target: Vector2=waypoint_positions[id]
		var candidate := point.distance_squared_to(target)
		if candidate<distance and not segment_blocked(point,target):distance=candidate;closest=str(id)
	return closest

func apply_knowledge(source: Dictionary) -> void:
	knowledge=source.duplicate(true)
	_route_factors.clear();_graphs.clear();_paths.clear();_path_fifo.clear();_region_pair_factors.clear()
	path_bias_uses=0;watch_bias_uses=0;watch_fallback_uses=0
	var samples: Dictionary={}
	for row in knowledge.get("transitions",[]):
		var key := str(row.get("from_region",""))+"|"+str(row.get("side","")).to_lower()+"|"+str(row.get("to_region",""))
		samples[key]=float(samples.get(key,0))+float(row.get("samples",0))
	for region in knowledge.get("regions",{}):
		var preferences: Dictionary=knowledge["regions"][region].get("route_preferences",{})
		for side in preferences:
			for row in preferences[side]:
				var key := str(region)+"|"+str(side).to_lower()+"|"+str(row.get("region",""))
				samples[key]=float(samples.get(key,0))+float(row.get("routes",0))
	for region in _regions:
		for side in ["t","ct"]:
			var maximum := 1.0
			for neighbor in _regions:maximum=maxf(maximum,float(samples.get(str(region)+"|"+side+"|"+str(neighbor),0)))
			for neighbor in _regions:
				var key: String = str(region)+"|"+str(side)+"|"+str(neighbor)
				var count := float(samples.get(key,0))
				if count>0 and region!=neighbor:_route_factors[key]=1.0-.18*clampf(count/maximum,0,1)
	# Float64 retains the previous Dictionary float exactly, including ties.
	# AStar callbacks now perform only packed-array indexing and vector distance.
	var unweighted := PackedFloat64Array()
	unweighted.resize(_regions.size()*_regions.size());unweighted.fill(1.0)
	_region_pair_factors[""]=unweighted
	for side in ["t","ct"]:
		var factors := unweighted.duplicate()
		for from_index in range(_regions.size()):
			for to_index in range(_regions.size()):
				factors[from_index*_regions.size()+to_index]=route_cost_factor(str(_regions[from_index]),str(_regions[to_index]),side)
		_region_pair_factors[side]=factors

func set_knowledge(source: Dictionary) -> void:
	apply_knowledge(source)

func route_cost_factor(from_region: String, to_region: String, side: String = "") -> float:
	return float(_route_factors.get(from_region+"|"+side.to_lower()+"|"+to_region,1.0))

func knowledge_usage() -> Dictionary:
	var mapped := 0
	for region in _regions:
		if knowledge.get("regions",{}).has(region):mapped+=1
	return {"source_regions":mapped,"mapped_waypoints":waypoint_positions.size(),"transitions":knowledge.get("transitions",[]).size(),"path_bias_uses":path_bias_uses,"watch_bias_uses":watch_bias_uses,"watch_fallback_uses":watch_fallback_uses,"geometry":"actual_NAV_projected_2D","cached_paths":_paths.size()}

func preferred_watch(point: Vector2, side: String, _role: String = "rifle") -> Vector2:
	var region := region_at(point)
	var preferences: Array=knowledge.get("regions",{}).get(region,{}).get("watch_preferences",{}).get(side.to_lower(),[])
	for preference in preferences:
		for candidate in positions_for_region(str(preference.get("region",""))):
			if point.distance_to(candidate)>12 and not segment_blocked(point,candidate):watch_bias_uses+=1;return candidate
	var anchor: Dictionary={}
	var closest := 96.0*96.0
	for row in _watch_anchors:
		if row["region"]!=region or row["side"]!=side.to_lower():continue
		var position := vec(row["position"])
		var distance := point.distance_squared_to(position)
		if distance<closest:closest=distance;anchor=row
	if not anchor.is_empty():
		var target := raycast_endpoint(point,point+vec(anchor["direction"])*180)
		if target.distance_to(point)>8:watch_bias_uses+=1;return target
	# A region behind a wall is watched at its reachable visible entrance.
	for preference in preferences.slice(0,2):
		for candidate in positions_for_region(str(preference.get("region",""))):
			var route := find_path(point,candidate,DEFAULT_RADIUS,side)
			if not route.is_empty() and point.distance_to(route[0])>8 and not segment_blocked(point,route[0]):watch_bias_uses+=1;watch_fallback_uses+=1;return route[0]
	var fallback := point
	var distance := 0.0
	for angle in range(0,360,45):
		var target := raycast_endpoint(point,point+Vector2.RIGHT.rotated(deg_to_rad(angle))*120)
		if target.distance_squared_to(point)>distance:distance=target.distance_squared_to(point);fallback=target
	return fallback

func validation_report(radius: float = DEFAULT_RADIUS) -> Dictionary:
	var invalid_spawns: Array[String]=[]
	var invalid_targets: Array[String]=[]
	for side in data.get("spawns",{}):
		for index in range(data["spawns"][side].size()):
			if not is_walkable(vec(data["spawns"][side][index]),radius):invalid_spawns.append(str(side)+":"+str(index))
	for name in data.get("tactical_targets",{}):
		if not is_walkable(vec(data["tactical_targets"][name]),radius):invalid_targets.append(str(name))
	return {"invalid_spawns":invalid_spawns,"invalid_targets":invalid_targets,"walk_cells":data.get("statistics",{}).get("walk_cells",0),"source_nav_areas":data.get("statistics",{}).get("source_nav_areas",0),"directed_portals":true,"floor_overlap_approximation":not _layered,"layer_identity_preserved":_layered,"traversal_links":_traversals.size(),"navigation_space":"NAV_agent_centres" if _centre_navigation else "eroded_NAV_footprint","nominal_agent_radius":_nav_agent_radius,"cell_size":_cell_size}

func layer_at(point: Vector2) -> int:
	return clampi(floori(point.y/1024.0),0,1) if _layered else 0

func traversal_between(start: Vector2, finish: Vector2) -> Dictionary:
	if _traversals.is_empty():return {}
	var first := _cell_id(_cell(start))
	var last := _cell_id(_cell(finish))
	if first<0 or last<0:return {}
	# The actor must reach the source gate, not activate from a nearby room.
	if start.distance_to(_cell_center(first))>.06 or finish.distance_to(_cell_center(last))>.06:return {}
	return _traversals.get(str(first)+":"+str(last),{}).duplicate(true)

func traversal_near(point: Vector2, direction: Vector2, ladder_only: bool = false) -> Dictionary:
	var closest := 8.0
	var result: Dictionary={}
	for row in _traversals.values():
		if ladder_only and row["kind"]!="ladder":continue
		var start := _cell_center(int(row["from"]))
		var finish := _cell_center(int(row["to"]))
		var distance := point.distance_to(start)
		if distance>=closest or segment_blocked(point,start,DEFAULT_RADIUS):continue
		var offset := Vector2(finish.x-start.x,fposmod(finish.y,1024.0)-fposmod(start.y,1024.0))
		if offset.length_squared()>1 and offset.normalized().dot(direction.normalized())<.1:continue
		closest=distance;result=row.duplicate(true)
		result["start"]=start;result["finish"]=finish
	return result

func traversal_markers(layer: int, all_kinds: bool = false) -> Array:
	var result: Array=[]
	var occupied: Array[Vector2]=[]
	for row in _traversals.values():
		var start := _cell_center(int(row["from"]))
		var finish := _cell_center(int(row["to"]))
		if layer_at(start)!=layer:continue
		if not all_kinds and layer_at(start)==layer_at(finish) and row["kind"]!="ladder":continue
		if occupied.any(func(point):return Vector2(point).distance_to(start)<64.0):continue
		occupied.append(start)
		var direction := " ↑" if layer_at(finish)<layer_at(start) else " ↓" if layer_at(finish)>layer_at(start) else ""
		result.append({"position":start,"kind":str(row["kind"])+direction})
	return result
