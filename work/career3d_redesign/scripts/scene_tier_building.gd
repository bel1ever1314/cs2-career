extends Node3D
## Versioned native geometry. The common playing/NPC anchors are never moved.
## Each exported tier scene builds its own shell, annex, furniture and audience.
const ChickenCrowd = preload("res://scripts/arena_chicken_crowd.gd")
const ChickenMesh = preload("res://scripts/chicken_mesh.gd")
const CATALOG := "res://data/scene_tiers.json"
@export var kind := "club"
@export var tier := "academy"
@export var capacity := 0
var facilities: Dictionary = {}
@export var include_stations := true
var core_variant := ""
@export var auto_cutaway := true
var roof_height := 0.0
var roof_group: Node3D
var upper_wall_group: Node3D
var enclosure_closed := false
var built := false
var materials: Dictionary = {}
var footprint := Rect2(-12.3,-8.9,24.6,18.5)
var audience_count := 0
var station_count := 0
var collision_count := 0
var door_clearance := Rect2(11.8,-1.35,1.2,2.7)

func _ready() -> void:
	if not built: build()
	set_process(kind == "venue")

func _process(_delta: float) -> void:
	if not auto_cutaway or not is_instance_valid(roof_group): return
	var camera := get_viewport().get_camera_3d()
	if camera: set_cutaway(camera.global_position.y > global_position.y+roof_height+.5)

func set_cutaway(value: bool) -> void:
	if is_instance_valid(roof_group): roof_group.visible = not value
	if is_instance_valid(upper_wall_group): upper_wall_group.visible = not value

func build() -> void:
	if built: return
	built = true
	var catalog: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
	assert(int(catalog.get("schema_version",0)) == 1)
	if kind == "club": _club(catalog.club.get(tier,catalog.club.academy))
	else: _venue(catalog.venues.get(str(capacity),catalog.venues["0"]))
	set_meta("layout", diagnostics())

func diagnostics() -> Dictionary:
	return {"version":1,"kind":kind,"tier":tier,"capacity":capacity,"core_variant":core_variant,"audience":audience_count,
		"stations":station_count,"colliders":collision_count,"footprint":[footprint.position.x,footprint.position.y,footprint.size.x,footprint.size.y],
		"core_anchors_preserved":true,"enclosure_closed":enclosure_closed,"roof_height":roof_height,
		"annex_door":[door_clearance.position.x,door_clearance.position.y,door_clearance.size.x,door_clearance.size.y]}

func _mat(color: Color, glow: float = 0.0) -> StandardMaterial3D:
	var key := color.to_html()+":"+str(glow)
	if materials.has(key): return materials[key]
	var result := StandardMaterial3D.new(); result.albedo_color = color; result.roughness = .82
	if glow > 0:
		result.emission_enabled = true; result.emission = color; result.emission_energy_multiplier = glow
	materials[key] = result
	return result

func _mesh(parent: Node3D, id: String, shape: Mesh, at: Vector3, color: Color, glow: float = 0.0) -> MeshInstance3D:
	var result := MeshInstance3D.new(); result.name = id; result.mesh = shape; result.position = at
	result.material_override = _mat(color,glow); parent.add_child(result)
	return result

func _box(parent: Node3D, id: String, at: Vector3, size: Vector3, color: Color, solid: bool = false, glow: float = 0.0) -> MeshInstance3D:
	var shape := BoxMesh.new(); shape.size = size
	var result := _mesh(parent,id,shape,at,color,glow)
	if solid: _solid(parent,id,at,size)
	return result

func _solid(parent: Node3D, id: String, at: Vector3, size: Vector3) -> void:
	var body := StaticBody3D.new(); body.name = id+"Solid"; body.position = at
	body.collision_layer = 1; body.collision_mask = 2
	var shape := BoxShape3D.new(); shape.size = size
	var collision := CollisionShape3D.new(); collision.shape = shape; body.add_child(collision); parent.add_child(body)
	collision_count += 1

func _cylinder(parent: Node3D, id: String, at: Vector3, radius: float, height: float, color: Color) -> MeshInstance3D:
	var shape := CylinderMesh.new(); shape.top_radius = radius; shape.bottom_radius = radius
	shape.height = height; shape.radial_segments = 12
	return _mesh(parent,id,shape,at,color)

func _orb(parent: Node3D, id: String, at: Vector3, size: Vector3, color: Color) -> MeshInstance3D:
	var shape := SphereMesh.new(); shape.radius = .5; shape.height = 1.0; shape.radial_segments = 12; shape.rings = 6
	var result := _mesh(parent,id,shape,at,color); result.scale = size
	return result

func _rounded(parent: Node3D, id: String, at: Vector3, size: Vector3, color: Color, radius: float = .10, solid: bool = false) -> void:
	var r := minf(radius,minf(size.x,size.z)*.45)
	_box(parent,id+"Centre",at,Vector3(size.x-r*2,size.y,size.z),color)
	_box(parent,id+"Cross",at,Vector3(size.x,size.y,size.z-r*2),color)
	for x in [-1.0,1.0]:
		for z in [-1.0,1.0]: _cylinder(parent,id+"Corner",at+Vector3(x*(size.x*.5-r),0,z*(size.z*.5-r)),r,size.y,color)
	if solid: _solid(parent,id,at,size)

func _label(parent: Node3D, id: String, text: String, at: Vector3, size: float = .008, angle: float = 0.0) -> Label3D:
	var result := Label3D.new(); result.name = id; result.text = text; result.position = at
	result.set_meta("source_text",text)
	result.font_size = 42; result.pixel_size = size; result.rotation.y = angle
	result.modulate = Color("f6e9c9"); result.outline_modulate = Color("314b44"); result.outline_size = 4
	parent.add_child(result); return result

func _room(parent: Node3D, id: String, center: Vector2, width: float, depth: float, wall: Color, open_west: bool = false, floor_y: float = .22) -> void:
	var y := floor_y
	var offset := floor_y-.22
	_rounded(parent,id+"Floor",Vector3(center.x,y-.12,center.y),Vector3(width,.24,depth),Color("b8946d"),.16,true)
	# Cutaway walls retain a real footprint, with low front/side walls for the
	# inherited overhead camera. Tall rear panels give the room its own volume.
	_rounded(parent,id+"BackWall",Vector3(center.x,1.65+offset,center.y-depth*.5),Vector3(width,2.85,.20),wall,.08,true)
	_rounded(parent,id+"FrontWall",Vector3(center.x,.71+offset,center.y+depth*.5),Vector3(width,.98,.20),wall,.08,true)
	_rounded(parent,id+"EastWall",Vector3(center.x+width*.5,.85+offset,center.y),Vector3(.20,1.26,depth),wall,.08,true)
	if not open_west: _rounded(parent,id+"WestWall",Vector3(center.x-width*.5,.85+offset,center.y),Vector3(.20,1.26,depth),wall,.08,true)
	for x in [center.x-width*.5+.2,center.x+width*.5-.2]:
		_cylinder(parent,id+"TimberColumn",Vector3(x,1.42+offset,center.y-depth*.5+.2),.15,2.4,Color("7d604a"))
	_rounded(parent,id+"RoofBeam",Vector3(center.x,2.83+offset,center.y-depth*.5+.20),Vector3(width,.20,.25),Color("7d604a"),.09)
	for i in range(int(width/1.5)):
		_box(parent,id+"OakPlank",Vector3(center.x-width*.5+.65+i*1.5,.227+offset,center.y),Vector3(.013,.006,depth-.4),Color("957452"))

func _club(config: Dictionary) -> void:
	var wall := Color(str(config.get("shell_color","e4d5b9")))
	var accent := Color(str(config.get("accent","799989")))
	var height := 1.25 if tier == "academy" else 1.65 if tier == "standard" else 2.1
	# Three visibly different entrance structures; the door and approach stay.
	for x in [-2.2,2.2]:
		_cylinder(self,"EntranceRoundColumn",Vector3(x,.22+height*.5,8.8),.16,height,Color("967558"))
	_rounded(self,"EntranceCanopy",Vector3(0,.22+height,8.8),Vector3(4.8,.22,.8 if tier=="academy" else 1.5),accent,.18)
	if tier != "academy":
		for side in [-1.0,1.0]:
			_rounded(self,"EntranceBench",Vector3(side*3.7,.56,8.72),Vector3(1.35,.24,.40),Color("b7966f"),.13)
	if tier == "elite":
		for side in [-1.0,1.0]:
			make_furniture(self,"plant",Vector3(side*4.9,.22,8.65),Color("739e81"),false)
		_rounded(self,"EliteEntranceInlay",Vector3(0,.234,7.7),Vector3(3.2,.012,.8),Color("d4b578"),.16)
	# Facility upgrades add actual distinct objects rather than a colour tint.
	var training := clampi(int(facilities.get("training",1)),1,3)
	var meeting := clampi(int(facilities.get("meeting",1)),1,3)
	var kitchen := clampi(int(facilities.get("kitchen",1)),1,3)
	var lounge := clampi(int(facilities.get("lounge",1)),1,3)
	for i in range(training-1):
		_rounded(self,"TrainingAnalysisDisplay",Vector3(-9.6+i*3.1,2.12,-8.57),Vector3(2.35,1.20,.10),Color("365b55"),.08)
		for line in range(3): _box(self,"DisplayGraph",Vector3(-10.3+i*3.1+line*.38,2.0+line*.14,-8.5),Vector3(.19,.14+line*.16,.015),Color("e3cf95"))
	if meeting > 1:
		_rounded(self,"TacticalWallDisplay",Vector3(2.50,2.32,-8.54),Vector3(1.15,.88,.10),accent,.07)
	if kitchen > 1:
		_rounded(self,"KitchenRecipeBoard",Vector3(9.2,2.26,-8.52),Vector3(1.45,.84,.10),Color("ead6af"),.10)
	if kitchen > 2:
		for x in [7.8,8.3,8.8]: _cylinder(self,"KitchenSpiceCanister",Vector3(x,1.96,-8.40),.12,.23,Color("a57859"))
	if lounge > 1: _rounded(self,"LoungeAcousticArch",Vector3(-10.8,1.45,8.78),Vector3(1.6,2.35,.10),accent,.12)
	var width := float(config.get("annex_width",0)); var depth := float(config.get("annex_depth",0))
	if width == 0: return
	var cx := 12.22+width*.5
	footprint = Rect2(-12.3,-8.9,24.52+width,18.5)
	_room(self,"ReviewAnnex",Vector2(cx,0),width,depth,wall,true)
	# Existing east boundary is replaced only at this 2.7m wide connecting door.
	for sign_value in [-1.0,1.0]:
		var segment := (depth-2.7)*.5
		_box(self,"AnnexWestWall",Vector3(12.22,.9,sign_value*(1.35+segment*.5)),Vector3(.20,1.36,segment),wall,true)
	_rounded(self,"AnnexDoorLintel",Vector3(12.22,2.6,0),Vector3(.28,.22,2.95),accent,.10)
	for z in [-1.43,1.43]: _cylinder(self,"AnnexDoorPost",Vector3(12.22,1.4,z),.12,2.36,Color("967558"))
	_rounded(self,"AnnexWelcomeRug",Vector3(13.55,.235,0),Vector3(2.2,.01,2.05),accent,.22)
	if tier == "standard":
		_meeting(self,Vector3(cx,.22,-2.5),meeting,accent)
		make_furniture(self,"bookshelf",Vector3(cx+1.7,.22,-depth*.5+.55),Color("987355"))
		make_furniture(self,"plant",Vector3(cx+2.3,.22,depth*.5-.65),Color("71977c"))
		_label(self,"ReviewAnnexTitle","REVIEW",Vector3(cx,2.4,-depth*.5+.12),.010)
	else:
		# A central aisle divides two larger usable rooms. Nothing crosses its
		# z=-1.35..1.35 approach, or the original NPC/interaction paths.
		_meeting(self,Vector3(cx-.35,.22,-3.85),meeting,accent)
		make_furniture(self,"bookshelf",Vector3(13.2,.22,-5.85),Color("967355"))
		make_furniture(self,"trophy_table",Vector3(cx+3.4,.22,-5.9),Color("c3a66d"))
		make_furniture(self,"sofa",Vector3(cx+.1,.22,4.25),Color("789586"))
		make_furniture(self,"sofa",Vector3(cx+3.65,.22,4.25),Color("789586"))
		make_furniture(self,"lamp",Vector3(cx+4.4,.22,6.10),Color("d5bd8c"))
		for x in [13.6,18.1,22.4]: make_furniture(self,"plant",Vector3(x,.22,6.4),Color("749780"))
		_rounded(self,"RecoveryMat",Vector3(14.0,.235,3.7),Vector3(1.6,.014,2.55),Color("c9b08b"),.16)
		for z in [-1.45,1.45]:
			for x in [13.6,17.6,21.6]: _rounded(self,"AnnexRoomScreen",Vector3(x,1.18,z),Vector3(1.3,1.6,.16),accent,.08,true)
		_label(self,"MeetingSuiteTitle","REVIEW & ANALYSIS",Vector3(cx,2.45,-6.86),.010)
		_label(self,"RecoverySuiteTitle","RECOVERY LOUNGE",Vector3(cx,1.80,6.87),.009,PI)

func _meeting(parent: Node3D, at: Vector3, level: int, accent: Color) -> void:
	_rounded(parent,"ReviewTable",at+Vector3(0,.74,0),Vector3(2.5,.18,1.25),Color("a98260"),.22,true)
	for side in [-1.0,1.0]:
		for x in [-.78,.78]:
			_rounded(parent,"ReviewStool",at+Vector3(x,.39,side*1.03),Vector3(.57,.30,.57),accent,.16,true)
	for i in range(level):
		_rounded(parent,"ReviewTablet",at+Vector3(-.7+i*.7,.852,0),Vector3(.43,.035,.28),Color("31534e"),.04)
	make_furniture(parent,"rug",at+Vector3(0,.006,0),accent,false)

func make_furniture(parent: Node3D, item: String, at: Vector3, color: Color, solid: bool = true) -> Node3D:
	var object := Node3D.new(); object.name = "Furniture_"+item; object.position = at; object.set_meta("item",item); parent.add_child(object)
	var oak := Color("9f7958")
	match item:
		"plant":
			_cylinder(object,"ClayPot",Vector3(0,.21,0),.24,.42,Color("c7976e"))
			for i in range(5):
				var angle := i*TAU/5; _orb(object,"RoundLeaf",Vector3(cos(angle)*.19,.62+i*.075,sin(angle)*.19),Vector3(.35,.46,.32),color)
			if solid: _solid(object,"Plant",Vector3(0,.35,0),Vector3(.54,.70,.54))
		"bookshelf":
			_rounded(object,"ShelfFrame",Vector3(0,.86,0),Vector3(1.28,1.72,.38),oak,.07)
			_box(object,"ShelfBacking",Vector3(0,.87,.17),Vector3(1.10,1.57,.05),Color("76563e"))
			for row in range(3):
				_box(object,"Shelf",Vector3(0,.18+row*.53,-.035),Vector3(1.15,.055,.39),Color("c6a57f"))
				for book in range(7): _box(object,"Book",Vector3(-.46+book*.15,.38+row*.53,-.09),Vector3(.10,.32+.035*(book%3),.21),color.lightened(float(book%3)*.1))
			if solid: _solid(object,"Shelf",Vector3(0,.86,0),Vector3(1.28,1.72,.40))
		"lamp":
			_cylinder(object,"LampFoot",Vector3(0,.04,0),.28,.08,oak)
			_cylinder(object,"LampStem",Vector3(0,.78,0),.035,1.48,Color("ad885f"))
			var shade := _cylinder(object,"FabricShade",Vector3(0,1.58,0),.33,.38,color)
			(shade.mesh as CylinderMesh).top_radius = .22
			var light := OmniLight3D.new(); light.position = Vector3(0,1.5,0); light.light_color = Color("ffdeb0")
			light.light_energy = .18; light.omni_range = 3.2; object.add_child(light)
			if solid: _solid(object,"Lamp",Vector3(0,.3,0),Vector3(.48,.6,.48))
		"rug": _rounded(object,"WovenRug",Vector3(0,.006,0),Vector3(3.4,.012,2.75),color,.22)
		"sofa":
			_rounded(object,"SofaBase",Vector3(0,.3,0),Vector3(2.0,.48,.86),color,.16)
			_rounded(object,"SofaBack",Vector3(0,.64,-.34),Vector3(2.0,.63,.23),color.darkened(.1),.1)
			for side in [-1.0,1.0]:
				_rounded(object,"SofaArm",Vector3(side*.91,.52,0),Vector3(.24,.36,.88),color.darkened(.06),.1)
				_rounded(object,"SofaCushion",Vector3(side*.40,.57,.04),Vector3(.70,.12,.63),color.lightened(.13),.10)
			if solid: _solid(object,"Sofa",Vector3(0,.45,0),Vector3(2.0,.90,.90))
		"trophy_table":
			_rounded(object,"TrophyTable",Vector3(0,.72,0),Vector3(1.0,.16,.62),oak,.11)
			for x in [-.35,.35]: _cylinder(object,"TableLeg",Vector3(x,.33,0),.07,.66,oak)
			_cylinder(object,"TrophyBase",Vector3(0,.84,0),.18,.09,Color("3d5147"))
			_cylinder(object,"TrophyStem",Vector3(0,1.02,0),.042,.3,color)
			var cup := _cylinder(object,"TrophyCup",Vector3(0,1.23,0),.18,.22,color); (cup.mesh as CylinderMesh).bottom_radius = .09
			if solid: _solid(object,"Table",Vector3(0,.43,0),Vector3(1.0,.86,.62))
	return object

func _venue(config: Dictionary) -> void:
	var width := float(config.width); var depth := float(config.depth)
	# An arena visit keeps its authored raised stage at z=-14.5 and its long
	# entrance tunnel even for a local 100-seat event. A studio LAN retains
	# the separate floor-level ten-station layout. Never put small-room walls
	# across the existing arena approach or stage stairs.
	var large := capacity >= 1000 or core_variant == "major"
	var core_bowl := core_variant == "major" and capacity >= 1000
	var grand := capacity >= 10000
	if core_variant == "major":
		width = maxf(width,40.0); depth = maxf(depth,67.0)
	var stage_z := -14.5 if large else 0.0
	var stage_y := 1.68 if large else .04
	var base_y := .44 if large else 0.0
	footprint = Rect2(-width*.5,-depth*.5,width,depth)
	var cream := Color("e6d5b7"); var green := Color("5a7d74"); var oak := Color("ae8963")
	if not large:
		_room(self,"StudioShell",Vector2.ZERO,width,depth,cream,false,0.0)
		# Replace the cutaway room's front strip with a real centre doorway.
		# The existing LAN entrance anchor remains reachable through this gap.
		for child in get_children():
			if str(child.name).begins_with("StudioShellFrontWall"):
				if child is StaticBody3D:
					remove_child(child); child.free(); collision_count -= 1
				elif child is Node3D: child.visible = false
		for side in [-1.0,1.0]:
			var front_segment := (width-2.4)*.5
			_rounded(self,"StudioEntryLowWall",Vector3(side*(1.2+front_segment*.5),.49,depth*.5),Vector3(front_segment,.98,.20),cream,.08,true)
		# The rear of a small room has a complete rounded proscenium. The
		# ten-station studio has acoustic walls and no audience at all.
		_rounded(self,"StudioBackDisplay",Vector3(0,2.45,-depth*.5+.20),Vector3(9.0,1.6,.18),green,.16)
		_rounded(self,"StudioHangingSign",Vector3(0,3.00,-3.41),Vector3(6.1,.65,.10),green,.10)
		_label(self,"StudioTitle","CAREER STUDIO" if capacity==0 else "LOCAL LAN",Vector3(0,3.00,-3.34),.011)
		for x in [-5.6,5.6]: _cylinder(self,"StageCanopySupport",Vector3(x,1.75,-3.8),.16,3.5,oak)
		_rounded(self,"StageCanopy",Vector3(0,3.48,-3.8),Vector3(11.5,.22,.74),green,.19)
		if capacity>0:
			# Side galleries leave the original ten-PC room and centre entrance
			# entirely clear. Audience positions have no per-spectator physics.
			for side in [-1.0,1.0]:
				for row in range(int(config.rows)):
					var z := -4.6+row*float(config.spacing_z)
					_box(self,"SmallGalleryStep",Vector3(side*10.5,.08+row*.16,z),Vector3(7.8,.16+row*.32,1.19),oak)
		else:
			for x in [-5.7,5.7]:
				make_furniture(self,"plant",Vector3(x,.22,4.9),Color("7c9e80"),false)
				_rounded(self,"StudioEquipmentCubby",Vector3(x,.74,-4.9),Vector3(.64,1.04,.67),oak,.10)
	else:
		# Different independent building volumes: single-bank hall versus a
		# much wider multi-terrace arena, curved colonnade and suspended rig.
		_box(self,"ArenaPresentationPlinth",Vector3(0,.1,0),Vector3(width,.28,depth),Color("d0b38a"))
		_box(self,"ArenaPublicFloor",Vector3(0,base_y-.07,2),Vector3(width-1,.14,depth-3),Color("96775a"),include_stations)
		if core_variant != "major":
			# Standalone tiers own a complete stage backdrop. In the live Major,
			# its original LED/media and ten PCs remain the sole stage core.
			_rounded(self,"ArenaStageRearWall",Vector3(0,4.0,-22.3),Vector3(35,6.0,.32),green,.14)
			_rounded(self,"ArenaLED",Vector3(0,4.5,-22.0),Vector3(22,4.2,.16),Color("304f48"),.1)
			_label(self,"ArenaHeadline","CAREER GRAND ARENA" if grand else "CAREER HALL",Vector3(0,4.8,-21.88),.053)
		for side in [-1.0,1.0]:
			# The live Major keeps its own grounded seating bowl instead.
			if not core_bowl:
				var band_width := float(config.columns)*float(config.spacing_x)+1.2
				var inner := 7.0 if grand else 6.3
				for row in range(int(config.rows)):
					var y := base_y+row*float(config.rise)
					var z := -6.0+row*float(config.spacing_z)
					# Each riser is solid down to the floor: a real stand, not
					# thin slabs hanging in the air.
					var height := maxf(.26,y-base_y+.02)
					_box(self,"TerraceBank",Vector3(side*(inner+band_width*.5),y-height*.5,z),Vector3(band_width,height,float(config.spacing_z)),Color("b5a080") if row%5==0 else oak,core_variant=="major")
					if row%5==4: _rounded(self,"TerraceRail",Vector3(side*(inner+band_width*.5),y+.35,z+.4),Vector3(band_width,.08,.08),green,.035)
				var top := base_y+(int(config.rows)-1)*float(config.rise)
				# Back of the stand: solid to the floor, topped by a waist-high
				# rail behind the last row (not a tall blank wall).
				var back_h := top-base_y+1.05
				var back_z := -6.0+int(config.rows)*float(config.spacing_z)-.3
				_box(self,"TerraceBackWall",Vector3(side*(inner+band_width*.5),base_y+back_h*.5,back_z),Vector3(band_width,back_h,.24),cream,core_variant=="major")
				_rounded(self,"TerraceBackRail",Vector3(side*(inner+band_width*.5),base_y+back_h+.04,back_z),Vector3(band_width+.1,.08,.32),green,.035)
			var x: float = side*(width*.5-1.1)
			for i in range(11 if grand else 7):
				var z := -depth*.5+.8+i*(depth-1.6)/(10.0 if grand else 6.0)
				_cylinder(self,"ArenaColonnade",Vector3(x,8.2 if grand else 5.2,z),.45,16.0 if grand else 10.0,cream)
			_rounded(self,"RoofRingBeam",Vector3(x,16.3 if grand else 10.3,0),Vector3(1.2,.68,depth-1),green,.3)
		if grand:
			for x in [-28.0,0.0,28.0]:
				_box(self,"SuspendedTruss",Vector3(x,16.0,4),Vector3(.32,.34,65),Color("b9a078"))
				for z in [-9.0,5.0,20.0]: _orb(self,"ArenaPendant",Vector3(x,15.7,z),Vector3(.8,.3,.8),Color("f8d79e"))
		# The inherited approach tunnel x=-3..3,z=18..58 remains open.
		for side in [-1.0,1.0]:
			_rounded(self,"ArenaGalleryPortal",Vector3(side*4.3,3.5,18),Vector3(1.2,6.2,1.2),cream,.3)
		_rounded(self,"ArenaPortalBeam",Vector3(0,6.5,18),Vector3(9.8,.65,1.2),green,.28)
	if include_stations: _stations(stage_z,stage_y,large)
	if capacity>0 and not core_bowl: _audience(config,base_y,large)
	_venue_enclosure(width,depth,large,grand)

func _beam(parent: Node3D, id: String, a: Vector3, b: Vector3, thickness: float, color: Color) -> void:
	var beam := _box(parent,id,(a+b)*.5,Vector3(thickness,thickness,a.distance_to(b)),color)
	beam.basis = Basis.looking_at(b-a,Vector3.RIGHT if absf((b-a).normalized().dot(Vector3.UP))>.98 else Vector3.UP)

func _venue_enclosure(width: float, depth: float, large: bool, grand: bool) -> void:
	# Roof and upper walls are complete physical geometry, not a sky backdrop.
	# Only the review/overhead camera hides their visual group. Their collision
	# stays in place; the original centre entrance keeps a 6m opening.
	roof_height = (25.0 if grand else 12.5) if large else 4.35
	if core_variant == "major": roof_height = maxf(roof_height,29.5)
	var wall := Color("d9d5bf"); var timber := Color("806850"); var green := Color("54766c")
	roof_group = Node3D.new(); roof_group.name = "TierRoofCutaway"; add_child(roof_group)
	upper_wall_group = Node3D.new(); upper_wall_group.name = "TierUpperWallsCutaway"; add_child(upper_wall_group)
	var lower_y := 1.3 if large else 1.15
	var front_z := depth*.5
	var door_width := 6.0 if large else 2.4
	var upper_height := roof_height-lower_y
	for side in [-1.0,1.0]:
		_rounded(upper_wall_group,"ClosedVenueSideWall",Vector3(side*width*.5,lower_y+upper_height*.5,0),Vector3(.42,upper_height,depth),wall,.18)
		_solid(self,"ClosedVenueSideWall",Vector3(side*width*.5,lower_y+upper_height*.5,0),Vector3(.42,upper_height,depth))
		_rounded(self,"VenueWallWainscot",Vector3(side*(width*.5-.23),.75,0),Vector3(.18,1.5,depth),green,.08)
		var segment := (width-door_width)*.5
		var x: float = side*(door_width*.5+segment*.5)
		_rounded(upper_wall_group,"VenueEntryFacade",Vector3(x,lower_y+upper_height*.5,front_z),Vector3(segment,upper_height,.42),wall,.18)
		_solid(self,"VenueEntryFacade",Vector3(x,lower_y+upper_height*.5,front_z),Vector3(segment,upper_height,.42))
	_rounded(upper_wall_group,"ClosedVenueRearWall",Vector3(0,lower_y+upper_height*.5,-depth*.5),Vector3(width,upper_height,.42),wall,.18)
	_solid(self,"ClosedVenueRearWall",Vector3(0,lower_y+upper_height*.5,-depth*.5),Vector3(width,upper_height,.42))
	var portal_height := 6.5 if large else 3.0
	_box(upper_wall_group,"VenueEntryAbovePortal",Vector3(0,(roof_height+portal_height)*.5,front_z),Vector3(door_width,roof_height-portal_height,.42),wall)
	_solid(self,"VenueEntryAbovePortal",Vector3(0,(roof_height+portal_height)*.5,front_z),Vector3(door_width,roof_height-portal_height,.42))
	# Shallow pitched panels make a closed two-sided roof with a visible warm
	# underside. The slight crown clears both suspended rig and old stage arch.
	var crown := 2.5 if large else .45
	for sign_value in [-1.0,1.0]:
		var gable := PrismMesh.new(); gable.size = Vector3(width,crown,.42)
		var mesh := _mesh(upper_wall_group,"ClosedVenueRoofGable",gable,Vector3(0,roof_height+crown*.5,sign_value*depth*.5),wall)
		var body := StaticBody3D.new(); body.name = "ClosedVenueGableSolid"; body.position = mesh.position
		var collision := CollisionShape3D.new(); collision.shape = gable.create_convex_shape()
		body.add_child(collision); add_child(body); collision_count += 1
	for side in [-1.0,1.0]:
		var span := Vector3(width*.5,crown,0).length()
		var panel := _box(roof_group,"ClosedVenueRoof",Vector3(side*width*.25,roof_height+crown*.5,0),Vector3(span,.24,depth+.6),Color("bcc9b4"))
		panel.rotation.z = -side*atan2(crown,width*.5)
		var body := StaticBody3D.new(); body.name = "ClosedVenueRoofSolid"; body.position = panel.position; body.rotation = panel.rotation
		var shape := BoxShape3D.new(); shape.size = (panel.mesh as BoxMesh).size
		var collision := CollisionShape3D.new(); collision.shape = shape; body.add_child(collision); add_child(body); collision_count += 1
	var count := 13 if grand else 8 if large else 4
	for index in range(count):
		var z := -depth*.5+.5+index*(depth-1)/float(count-1)
		var left := Vector3(-width*.5,roof_height-.22,z); var peak := Vector3(0,roof_height+crown-.22,z); var right := Vector3(width*.5,roof_height-.22,z)
		_beam(roof_group,"VenueTimberRafter",left,peak,.32 if large else .14,timber)
		_beam(roof_group,"VenueTimberRafter",peak,right,.32 if large else .14,timber)
		if large:
			_box(roof_group,"RoofTrussChord",Vector3(0,roof_height-.85,z),Vector3(width,.25,.25),green)
			for x in range(-4,5):
				var px := x*width/10.0
				var py := roof_height+crown*(1-absf(px)/(width*.5))-.22
				_beam(roof_group,"RoofTrussWeb",Vector3(px,roof_height-.85,z),Vector3(px,py,z),.18,timber)
		else: _box(roof_group,"StudioCeilingStrip",Vector3(0,roof_height-.30,z),Vector3(width*.7,.055,.12),Color("f6e4bb"),false,.45)
	# An unmistakable building-front portal, with no foot/column in the route.
	for side in [-1.0,1.0]:
		_rounded(self,"EntryFacadeColumn",Vector3(side*(door_width*.5+.55),portal_height*.5,front_z+.32),Vector3(.65,portal_height,.85),green,.22)
	_rounded(self,"EntryFacadeLintel",Vector3(0,portal_height,front_z+.32),Vector3(door_width+1.75,.65,1.1),green,.22)
	if large:
		_rounded(upper_wall_group,"ArenaFrontFascia",Vector3(0,8.1,front_z+.25),Vector3(width,.45,.28),green,.13)
		_rounded(upper_wall_group,"ArenaWelcomeSign",Vector3(0,10.8,front_z+.30),Vector3(18,2.2,.24),green,.14)
		_label(upper_wall_group,"ArenaFrontTitle","GRAND ARENA" if grand else "CAREER HALL",Vector3(0,10.9,front_z+.45),.025)
	if large:
		# The stage has a dedicated transverse rig, separate from the full roof.
		for side in [-1.0,1.0]:
			_cylinder(self,"StageRigRoundPillar",Vector3(side*17,6.5,-20),.24,13.0,green)
		_box(self,"StageUpperTruss",Vector3(0,13.0,-20),Vector3(34,.25,.25),green)
		_box(self,"StageLowerTruss",Vector3(0,12.0,-20),Vector3(34,.25,.25),green)
		for x in range(-16,17,2):
			_beam(self,"StageTrussDiagonal",Vector3(x,12,-20),Vector3(x+1.6,13,-20),.11,timber)
			_orb(self,"WarmStageRigLamp",Vector3(x,11.7,-20),Vector3(.32,.18,.32),Color("ead5aa"))
	else:
		for z in [-2.5,2.5]:
			var light := OmniLight3D.new(); light.position = Vector3(0,3.6,z); light.light_color = Color("ffecd0")
			light.light_energy = .65; light.omni_range = width*.55; add_child(light)
	enclosure_closed = true

func _stations(stage_z: float, stage_y: float, large: bool) -> void:
	for side in [-1.0,1.0]:
		var desk_z: float = stage_z+side*1.08
		_rounded(self,"TeamCompetitionDesk",Vector3(0,stage_y+.97,desk_z),Vector3(10.9,.16,.94),Color("9b7758"),.14)
		for leg_x in [-4.8,0.0,4.8]: _cylinder(self,"CompetitionDeskLeg",Vector3(leg_x,stage_y+.45,desk_z),.09,.9,Color("806548"))
		for i in range(5):
			var x := -4.2+i*2.1
			_rounded(self,"CompetitionScreen",Vector3(x,stage_y+1.45,stage_z+side*.95),Vector3(1.1,.67,.08),Color("244c46"),.04)
			_box(self,"MonitorFoot",Vector3(x,stage_y+1.12,stage_z+side*.95),Vector3(.06,.25,.06),Color("556d60"))
			_rounded(self,"MonitorBase",Vector3(x,stage_y+1.07,stage_z+side*.95),Vector3(.36,.03,.24),Color("556d60"),.03)
			_rounded(self,"Keyboard",Vector3(x,stage_y+1.076,stage_z+side*1.3),Vector3(.60,.04,.22),Color("d7c7aa"),.035)
			_rounded(self,"MousePad",Vector3(x+.45,stage_y+1.066,stage_z+side*1.3),Vector3(.28,.025,.29),Color("547c68"),.025)
			_rounded(self,"CompetitionChair",Vector3(x,stage_y+.47,stage_z+side*2.33),Vector3(.70,.20,.66),Color("688e7b"),.16)
			_rounded(self,"CompetitionBackrest",Vector3(x,stage_y+.78,stage_z+side*2.62),Vector3(.70,.70,.12),Color("547468"),.04)
			_cylinder(self,"ChairStem",Vector3(x,stage_y+.25,stage_z+side*2.33),.06,.45,Color("695f4d"))
			_rounded(self,"ChairFoot",Vector3(x,stage_y+.06,stage_z+side*2.33),Vector3(.70,.10,.59),Color("695f4d"),.07)
			station_count += 1
	if large: _box(self,"PlayerStage",Vector3(0,stage_y-.15,stage_z),Vector3(32,.30,12),Color("9b7954"),true)

func _audience(config: Dictionary, floor_y: float, large: bool) -> void:
	var transforms: Array[Transform3D] = []
	var scale_value := float(config.seat_scale)
	for side in [-1.0,1.0]:
		for row in range(int(config.rows)):
			for column in range(int(config.columns)):
				var x: float = side*((7.6 if capacity>=10000 else 6.9) + column*float(config.spacing_x)) if large else side*(7.4+column*float(config.spacing_x))
				var z := -6.0+row*float(config.spacing_z) if large else -4.6+row*float(config.spacing_z)
				var y := floor_y+row*float(config.rise) if large else .16+row*float(config.rise)
				var origin := Vector3(x,y,z)
				var direction := Vector3(0,0,-15.0 if large else 0.0)-Vector3(x,0,z)
				var rotation_y := atan2(direction.x,direction.z)
				transforms.append(Transform3D(Basis(Vector3.UP,rotation_y).scaled(Vector3.ONE*scale_value),origin))
	audience_count = transforms.size()
	assert(audience_count == capacity)
	# One shared seated spectator (same design as the near crowd), a low-detail
	# version so ten thousand stay one cheap batch; seat and legs included.
	var surface := SurfaceTool.new(); surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	ChickenMesh._box(surface,Vector3(0,ChickenMesh.BODY_BOTTOM-.04,-.03),Vector3(.52,.08,.48),Color("5d776d"))
	ChickenMesh._box(surface,Vector3(0,ChickenMesh.BODY_BOTTOM+.23,-.33),Vector3(.52,.50,.06),Color("5d776d"))
	ChickenMesh.add_seated_chicken(surface,Vector3.ZERO,0,true)
	ChickenMesh.legs(surface,Vector3.ZERO,0.0)
	var shape := surface.commit()
	var instances := MultiMesh.new(); instances.transform_format = MultiMesh.TRANSFORM_3D; instances.use_custom_data = true; instances.use_colors = true
	instances.mesh = shape; instances.instance_count = transforms.size()
	for i in range(transforms.size()):
		instances.set_instance_transform(i,transforms[i]); instances.set_instance_custom_data(i,ChickenMesh.tint(i)); instances.set_instance_color(i,Color.WHITE)
	var batch := MultiMeshInstance3D.new(); batch.name = "TierSeatedChickenAudience"; batch.multimesh = instances; batch.material_override = ChickenMesh.material()
	batch.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF; add_child(batch)
