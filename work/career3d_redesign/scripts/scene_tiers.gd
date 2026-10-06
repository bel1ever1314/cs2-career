extends RefCounted
## Presentation adapter only. Backend projections own tier, upgrades and decor.
const Building = preload("res://scripts/scene_tier_building.gd")
const DATA := "res://data/scene_tiers.json"
const CLUB_ROOT := "ClubTierBuilding"
const VENUE_ROOT := "VenueTierBuilding"
const HOME_ROOT := "HomeDecorBuilding"
static var translate: Callable
static var _catalog: Dictionary = {}

static func catalog() -> Dictionary:
	# Camera focus calls this every frame; immutable versioned data loads once.
	if _catalog.is_empty():
		_catalog = JSON.parse_string(FileAccess.get_file_as_string(DATA))
		assert(int(_catalog.get("schema_version",0)) == 1)
	return _catalog

static func _replace(parent: Node3D, name_value: String) -> void:
	var previous := parent.get_node_or_null(NodePath(name_value))
	if previous:
		parent.remove_child(previous); previous.queue_free()

static func _remember_visibility(node: Node3D, value: bool) -> void:
	if not node.has_meta("tier_original_visibility"): node.set_meta("tier_original_visibility",node.visible)
	node.visible = value

static func _restore_visibility(model: Node3D) -> void:
	if not is_instance_valid(model): return
	for node in model.find_children("*","Node3D",true,false):
		if node.has_meta("tier_original_visibility"): node.visible = bool(node.get_meta("tier_original_visibility"))

static func _east_door(parent: Node3D, model: Node3D, building: Node3D, active: bool) -> void:
	for boundary in parent.get_children():
		if not boundary is StaticBody3D: continue
		var text := str(boundary.name).replace("_"," ").to_lower()
		if str(boundary.name)!="Solid_east_boundary" and "right external wall" not in text: continue
		if not boundary.has_meta("tier_original_layer"): boundary.set_meta("tier_original_layer",boundary.collision_layer)
		boundary.collision_layer = 0 if active else int(boundary.get_meta("tier_original_layer"))
	if not active: return
	for node in model.find_children("*","MeshInstance3D",true,false):
		var text := str(node.name).replace("_"," ").to_lower()
		if "external wall" not in text and "rear wall" not in text: continue
		var bounds: AABB = node.global_transform*node.get_aabb()
		if bounds.get_center().x > 11.8: _remember_visibility(node,false)
	# Preserve all of the old east boundary except the annex door opening.
	for row in [[-8.9,-1.35],[1.35,9.48]]:
		var z := (float(row[0])+float(row[1]))*.5
		building._box(building,"CoreEastWall",Vector3(12.29,1.32,z),Vector3(.20,2.20,float(row[1])-float(row[0])),Color("e4d5b9"),true)

static func apply_club(parent: Node3D, model: Node3D, requested_tier: String, facilities: Dictionary = {}) -> Node3D:
	var tier := requested_tier if requested_tier in ["academy","standard","elite"] else "academy"
	var fingerprint := JSON.stringify([tier,facilities])
	var existing := parent.get_node_or_null(CLUB_ROOT) as Node3D
	if existing and str(existing.get_meta("fingerprint","")) == fingerprint:
		_relabel(existing); return existing
	_restore_visibility(model)
	_replace(parent,CLUB_ROOT)
	var scene_path := str(catalog().club[tier].scene)
	var building := (load(scene_path) as PackedScene).instantiate() as Node3D
	building.name = CLUB_ROOT; building.facilities = facilities.duplicate(true); building.build()
	building.set_meta("fingerprint",fingerprint); parent.add_child(building)
	_east_door(parent,model,building,tier != "academy")
	# A read/load can shrink a previous annex. Never strand the player outside
	# the current floor, or keep them inside a newly constructed wall/desk.
	var player: Node3D = _player(parent)
	if player and player.position.x > 11.8:
		var safe: bool = building.footprint.has_point(Vector2(player.position.x,player.position.z))
		if not safe or _inside_solid(building,player.position):
			player.position = Vector3(-.75,.23,5.45); player.reset_physics_interpolation()
			player.set("velocity",Vector3.ZERO)
	_relabel(building)
	return building

static func _player(parent: Node) -> Node3D:
	for property in parent.get_property_list():
		if str(property.name) == "player": return parent.get("player") as Node3D
	return null

static func _inside_solid(building: Node3D, position: Vector3) -> bool:
	for body in building.find_children("*","StaticBody3D",true,false):
		if body.collision_layer == 0: continue
		for child in body.get_children():
			if child is CollisionShape3D and child.shape is BoxShape3D:
				var center: Vector3 = body.global_position
				var size: Vector3 = child.shape.size
				if center.y+size.y*.5 <= position.y+.10: continue
				if center.y-size.y*.5 > position.y+1.55: continue
				var rect := Rect2(center.x-size.x*.5-.28,center.z-size.z*.5-.28,size.x+.56,size.z+.56)
				if rect.has_point(Vector2(position.x,position.z)): return true
	return false

static func club_view(tier: String) -> Dictionary:
	var info: Dictionary = catalog().club.get(tier,catalog().club.academy)
	return {"size":float(info.overview_size),"focus":Vector3(float(info.overview_focus_x),.8,0)}

static func club_room(at: Vector3, tier: String) -> String:
	if at.x < 12.0 or tier == "academy": return ""
	if tier == "standard": return "复盘附楼"
	return "分析与会议中心" if at.z < -1.35 else "恢复休息室" if at.z > 1.35 else "附楼走廊"

static func apply_venue(parent: Node3D, model: Node3D, requested_capacity: int, venue_kind: String = "major") -> Node3D:
	var capacity := requested_capacity if requested_capacity in [0,100,1000,10000] else (10000 if venue_kind=="major" else 0)
	var existing := parent.get_node_or_null(VENUE_ROOT) as Node3D
	if existing and int(existing.get_meta("capacity",-1)) == capacity and str(existing.get_meta("venue_kind","")) == venue_kind:
		_relabel(existing); return existing
	_replace(parent,VENUE_ROOT)
	var building := (load(str(catalog().venues[str(capacity)].scene)) as PackedScene).instantiate() as Node3D
	building.name = VENUE_ROOT; building.include_stations = false; building.core_variant = venue_kind
	building.build(); building.set_meta("capacity",capacity); building.set_meta("venue_kind",venue_kind)
	parent.add_child(building)
	if venue_kind == "lan": _lan_shell(parent,building,capacity)
	elif is_instance_valid(model): _major_shell(parent,model,capacity)
	_relabel(building); return building

static func _lan_shell(parent: Node3D, building: Node3D, capacity: int) -> void:
	# Ten PCs, the centre door, both desk aisles and their collision footprints
	# stay exactly as authored in lan_venue.json. Only the shell is replaced.
	# Old deck/access meshes also end exactly at y=0. The native wood floor
	# replaces that visible surface; retaining either causes dark/bright
	# depth fighting as TAA or a tiny camera turn changes the winning pixel.
	var outer_names := ["Floor","StageDeck","StageAccess","BackWall","EntryWall","ClosedCeiling","SideWall","BackDisplay"]
	for node in parent.get_children():
		if node == building: continue
		var text := str(node.get_meta("venue_authored_id",node.name))
		if node is MeshInstance3D:
			for prefix in outer_names:
				if text.begins_with(prefix): _remember_visibility(node,false); break
		if node is StaticBody3D and (text=="SideWall" or text.begins_with("SideWallCollision")):
			if not node.has_meta("tier_original_layer"): node.set_meta("tier_original_layer",node.collision_layer)
			node.collision_layer = 0 if capacity>0 else int(node.get_meta("tier_original_layer"))
	if capacity>0:
		# Side audience access uses the empty +/-6.6m passages, not player desks.
		for side in [-1.0,1.0]:
			for z in [-5.2,5.2]: building._box(building,"CoreSideWall",Vector3(side*6.6,1.3,z),Vector3(.18,2.6,2.5),Color("e6d5b7"),true)

static func _major_shell(parent: Node3D, model: Node3D, capacity: int = 10000) -> void:
	# The original stage, all competing stations, stairs and entrance tunnel
	# are the stable match core. Competition stations (monitors, keyboards,
	# mice, seats) belong to the core too.
	# Large events keep the arena's own seating bowl: its terraces are solid
	# down to the floor, carry the real stairs/colliders and the seated crowd.
	# A 1,000-seat event uses the lower two tiers; a 100-seat event uses the
	# building tier's small grounded stands instead.
	var bowl_tiers := 3 if capacity >= 10000 else (2 if capacity >= 1000 else 0)
	var retain := ["event floor","rear stage platform","performance floor","stage oak border","champions runway","centre aisle","foyer floor","walk tunnel","public stair","team competition desk","team desk front","team desk","stage ","wing ","main led","trophy","backstage","gate","concession","tree planter",
		"keyboard","mouse","monitor","seat cushion","seat pedestal","seat rounded back","desk support","desk front illuminated","booth team number","studio backdrop","rig "]
	if bowl_tiers > 0:
		retain.append_array(["bowl dark floor","plaza and arena floor","circulation ring","terrace","section number"])
	for node in model.find_children("*","MeshInstance3D",true,false):
		var text := str(node.name).replace("_"," ").to_lower()
		var keep := false
		for token in retain:
			if token in text: keep = true; break
		var tier := _bowl_tier(text)
		if tier > 0 and tier > bowl_tiers: keep = false
		if text.begins_with("crowd"): keep = false
		if bowl_tiers == 0 and "public stair" in text: keep = false
		if not keep:
			_remember_visibility(node,false)
			# Hidden structural surfaces must not stay walkable as invisible steps.
			if tier > 0 or "public stair" in text:
				var body := parent.get_node_or_null(NodePath("Surface_"+str(node.name))) as CollisionObject3D
				if body:
					if not body.has_meta("tier_original_layer"): body.set_meta("tier_original_layer",body.collision_layer)
					body.collision_layer = 0
	# The floor crowd's two block colliders leave with the crowd: no
	# invisible walls on an empty floor.
	for side in ["-1","1"]:
		var block := parent.get_node_or_null("Solid_FloorAudience"+side) as CollisionObject3D
		if block:
			if not block.has_meta("tier_original_layer"): block.set_meta("tier_original_layer",block.collision_layer)
			block.collision_layer = int(block.get_meta("tier_original_layer")) if bowl_tiers > 0 else 0
	var audience := parent.get_node_or_null("SeatedChickenAudience") as Node3D
	if audience:
		audience.visible = bowl_tiers > 0
		audience.process_mode = Node.PROCESS_MODE_INHERIT if bowl_tiers > 0 else Node.PROCESS_MODE_DISABLED
		# Upper-tier spectators leave with their tier (tier 2 tops out at 8.4 m).
		if bowl_tiers == 2 and audience.has_method("limit_height"): audience.limit_height(8.9)

static func _bowl_tier(text: String) -> int:
	if not text.begins_with("tier "): return 0
	var parts := text.split(" ")
	return int(parts[1]) if parts.size() > 1 and parts[1].is_valid_int() else 0

static func apply_home(parent: Node3D, model: Node3D, home: Dictionary) -> Node3D:
	var footprints := {}
	for item in home.get("catalog",[]):
		if item is Dictionary and item.get("kind","")=="furniture": footprints[str(item.id)] = item.get("footprint",[])
	var fingerprint := JSON.stringify([home.get("placed",[]),home.get("wallpaper","sage"),home.get("floor","oak"),footprints])
	var existing := parent.get_node_or_null(HOME_ROOT) as Node3D
	if existing and str(existing.get_meta("fingerprint","")) == fingerprint: return existing
	_replace(parent,HOME_ROOT)
	var building := Building.new(); building.name = HOME_ROOT; building.built = true
	building.set_meta("fingerprint",fingerprint); parent.add_child(building)
	for row in home.get("placed",[]):
		if not row is Dictionary: continue
		var item := str(row.get("item",""))
		if item not in ["plant","bookshelf","lamp","rug","sofa","trophy_table"]: continue
		var color := Color.from_string(str(row.get("color","779c87")),Color("779c87"))
		var object := building.make_furniture(building,item,Vector3(float(row.get("x",0)),.105,float(row.get("z",0))),color,item!="rug")
		# Backend placement validation and the real walking collider must share
		# the same footprint. Scaling is home-only; club furniture stays full-size.
		var native_sizes := {"plant":Vector2(.54,.54),"bookshelf":Vector2(1.28,.40),"lamp":Vector2(.48,.48),"rug":Vector2(3.4,2.75),"sofa":Vector2(2.0,.90),"trophy_table":Vector2(1.0,.62)}
		var defaults := {"plant":[.45,.45],"bookshelf":[.8,.35],"lamp":[.35,.35],"rug":[1.25,1.25],"sofa":[1.1,.55],"trophy_table":[.65,.4]}
		var target: Array = footprints.get(item,defaults[item])
		if target.size()==2:
			var native_size: Vector2 = native_sizes[item]
			var stretch := Vector3(float(target[0])/native_size.x,1.0,float(target[1])/native_size.y)
			for child in object.get_children():
				if not child is Node3D: continue
				child.position *= stretch
				if child is MeshInstance3D: child.scale *= stretch
				elif child is StaticBody3D:
					for collider in child.get_children():
						if collider is CollisionShape3D and collider.shape is BoxShape3D: collider.shape.size *= stretch
			object.set_meta("footprint",target.duplicate())
		object.rotation.y = deg_to_rad(float(row.get("rotation",0))); object.set_meta("placement_id",str(row.get("id","")))
	var walls := {"sage":"b5c1a2","cream":"e7dec7","sky":"b4cbd0","peach":"e0b8a5"}
	var floors := {"oak":"bd986d","walnut":"826448","stone":"b8b5a6"}
	if model:
		for node in model.find_children("*","MeshInstance3D",true,false):
			var text := str(node.name).replace("_"," ").to_lower()
			var color_text := ""
			if "wall" in text and "art" not in text and "clock" not in text: color_text = str(walls.get(home.get("wallpaper","sage"),walls.sage))
			elif "floor" in text or "plank" in text: color_text = str(floors.get(home.get("floor","oak"),floors.oak))
			if not color_text.is_empty(): node.material_override = building._mat(Color(color_text))
	return building

static func _relabel(root: Node) -> void:
	for node in root.find_children("*","Label3D",true,false):
		var source := str(node.get_meta("source_text",node.text))
		node.text = str(translate.call(source)) if translate.is_valid() else source
