extends "res://scripts/chicken_player.gd"
## Physical locomotion and presentation only. Schedules/choices live in ClubLife.
signal arrived
var definition: Dictionary={}
var npc_id: String=""
var state: String="doing"
var action: String="reading"
var activity_label: String=""
var site_id: String=""
var schedule_index:=0
var remaining:=0.0
var destination:=Vector3.ZERO
var approach:=Vector3.ZERO
var route: Array[Vector3]=[]
var route_index:=0
var actor_time:=0.0
var talking:=false
var previous_state: String=""
var talk_action: String=""
var talk_yaw:=0.0
var bond:=0
var topics: Dictionary={}
var encourage_at: float=-1000
var stopped_for:=0.0
var travelled:=0.0
var finished_jobs:=0
var job_counts: Dictionary={}
var head: Node3D
var head_base:=Vector3.ZERO
var nameplate: Label3D
var manager
var last_position:=Vector3.ZERO
var sidestep:=Vector3.ZERO
var sidestep_time:=0.0
var template_id: String=""
var last_arrival_at:=0.0
var progress_anchor:=Vector3.ZERO
var progress_time:=0.0

func _ready() -> void:
	super._ready()
	npc_id=str(definition["id"])
	template_id=str(definition.get("template_id",npc_id))
	test_mode=true;walk_speed=1.6;run_speed=1.6;collision_layer=4;collision_mask=7
	(shape_node.shape as CapsuleShape3D).radius=.24
	visual.scale=Vector3.ONE*.93
	for child in get_children():
		if child is GeometryInstance3D:child.visible=false
	head=visual.find_child("HeadPivot",true,false) as Node3D
	if head:head_base=head.rotation
	for mesh in visual.find_children("*","MeshInstance3D",true,false):
		if str(mesh.name).replace("_"," ")=="Sleeveless team jersey":
			var mat:=StandardMaterial3D.new();mat.albedo_color=Color(str(definition["color"]));mat.roughness=.85
			mesh.material_override=mat
	# ClubLife keeps the identity label as metadata. Its old visibility updates
	# cannot expose a world-space name: the owning parent stays hidden.
	var identity:=Node3D.new();identity.name="IdentityMetadata";identity.visible=false;add_child(identity)
	nameplate=Label3D.new();nameplate.text=str(definition["name"])+" · "+str(definition["role"]);identity.add_child(nameplate)
	if npc_id=="chef":
		var hat=_prop("hat",Vector3(0,1.5,0),Vector3(.5,.20,.40),Color("fff1db"));hat.visible=true
	last_position=position
	progress_anchor=position

func bind_identity(row: Dictionary,template: Dictionary) -> void:
	# Metadata refresh must not restart the physical schedule or conversation.
	npc_id=str(row["id"]);definition["id"]=npc_id
	definition["name"]=str(row.get("name",npc_id))
	var actual_role: String=str(row.get("role","rifle"))
	definition["career_role"]=actual_role
	var labels: Dictionary={"igl":"指挥","awp":"主狙","awper":"主狙","entry":"突破手","lurker":"自由人","lurk":"自由人","rifle":"步枪手","support":"辅助","anchor":"守点"}
	definition["role"]=str(labels.get(actual_role.to_lower(),actual_role))
	definition["training"]=template["training"].duplicate()
	definition["encourage"]=template["encourage"].duplicate()
	nameplate.text=definition["name"]+" · "+definition["role"]

func _prop(id: String,p: Vector3,size: Vector3,color: Color) -> Node3D:
	var mesh:=MeshInstance3D.new();mesh.name=id;mesh.position=p
	if id=="cup" or id=="hat":
		var primitive:=CylinderMesh.new();primitive.top_radius=size.x*.5;primitive.bottom_radius=size.x*.47;primitive.height=size.y;mesh.mesh=primitive
	else:
		var primitive:=BoxMesh.new();primitive.size=size;mesh.mesh=primitive
	var mat:=StandardMaterial3D.new();mat.albedo_color=color;mesh.material_override=mat;visual.add_child(mesh);mesh.visible=false
	return mesh

func _physics_process(delta: float) -> void:
	actor_time+=delta
	if talking or state=="doing" or state=="waiting":
		locked=true;test_direction=Vector3.ZERO
	else:
		locked=false
		while route_index<route.size() and Vector2(position.x-route[route_index].x,position.z-route[route_index].z).length()<.12:route_index+=1
		if route_index>=route.size():
			test_direction=Vector3.ZERO;velocity=Vector3.ZERO;arrived.emit()
		else:
			var direction:=route[route_index]-position;direction.y=0
			test_direction=manager.steer(self,direction.normalized(),delta)
	var before:=position
	super._physics_process(delta)
	var moved:=Vector2(position.x-before.x,position.z-before.z).length()
	travelled+=moved
	if state=="walking" and not talking:
		stopped_for=stopped_for+delta if moved<.003 else 0.0
		progress_time+=delta
	else:stopped_for=0
	last_position=position

func _animate(delta: float,speed: float) -> void:
	super._animate(delta,speed)
	var doing:=state=="doing" and not talking
	if head:head.rotation=head_base+Vector3(sin(actor_time*1.8)*.025,0,0)
	if state=="walking" and not talking:return
	visual.rotation.x=lerpf(visual.rotation.x,0,delta*5)
	if carry_state=="idle":visual.position.y=sin(actor_time*1.5)*.006
	# The carry controller is the sole writer for both wings while an item is
	# taking/held/used/stowing. Talking keeps the same object in the hands.
	if carry_state!="idle":
		if head and action in ["reading","review"]:head.rotation.x=head_base.x+.12
		return
	if talking:
		if right_wing:right_wing.rotation.z=-.35-.12*sin(actor_time*4)
		if head:head.rotation.x=head_base.x+.04*sin(actor_time*3)
	elif doing:
		if right_wing:right_wing.rotation.z=0
		match action:
			"typing":
				if left_wing:left_wing.rotation.x=-.65+.13*sin(actor_time*11)
				if right_wing:right_wing.rotation.x=-.65+.10*sin(actor_time*11+1.8)
			"cooking","cleaning":
				if right_wing:right_wing.rotation.x=-.7+.25*sin(actor_time*3.8)
			"stretching":
				if left_wing:left_wing.rotation.z=.5+.3*sin(actor_time*1.5)
				if right_wing:right_wing.rotation.z=-.5-.3*sin(actor_time*1.5)

func start_route(points: Array[Vector3],target: Vector3) -> void:
	route=points;route_index=0;destination=target;state="walking";locked=false;seat_pose=false;stopped_for=0
	set_item_use(false);set_carried_item("");upper_body_action=""
	progress_anchor=position;progress_time=0;sidestep_time=0
	if left_wing:left_wing.rotation.z=0
	if right_wing:right_wing.rotation.z=0

func start_job(id: String,site: Dictionary,duration: float) -> void:
	site_id=id;approach=position;remaining=duration;state="doing";locked=true;velocity=Vector3.ZERO
	action=str(site["action"]);activity_label=str(site["label"])
	var held: String="notebook" if action in ["reading","review"] else ("cup" if action in ["drinking","eating"] else "")
	if template_id=="analyst" and action in ["reading","review"]:held="laptop"
	set_carried_item(held);set_item_use(not held.is_empty())
	seat_pose=site.has("seat")
	if seat_pose:
		position=Vector3(site["seat"][0],site["seat"][1],site["seat"][2]);reset_physics_interpolation()
	face_toward(Vector3(site["look"][0],site["look"][1],site["look"][2]))
	job_counts[id]=int(job_counts.get(id,0))+1
	last_arrival_at=manager.clock

func leave_seat() -> void:
	if seat_pose:position=approach;reset_physics_interpolation()
	seat_pose=false;locked=false

func begin_talk(target: Vector3) -> void:
	previous_state=state;talk_action=action if state=="doing" else state;talk_yaw=visual.rotation.y
	talking=true;velocity=Vector3.ZERO;face_toward(target)

func end_talk() -> void:
	talking=false;state=previous_state;visual.rotation.y=talk_yaw;velocity=Vector3.ZERO
	if right_wing:right_wing.rotation.z=0
	if left_wing:left_wing.rotation.z=0
