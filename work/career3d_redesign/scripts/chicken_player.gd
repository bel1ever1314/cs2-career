extends CharacterBody3D
## Keyboard intent -> physical velocity -> visual gait. No gameplay state here.
signal recovered
signal carry_state_changed(kind: String, state: String)
const Appearance = preload("res://scripts/appearance_customization.gd")
var camera_yaw := 0.0
var enabled := true
var locked := false
var test_mode := false
var test_direction := Vector3.ZERO
var test_run := false
var visual: Node3D
var left_foot: Node3D
var right_foot: Node3D
var left_wing: Node3D
var right_wing: Node3D
var phase := 0.0
var seat_pose := false
var home := Vector3(-.75,.23,5.45)
var shape_node: CollisionShape3D
var walk_speed := 2.65
var run_speed := 4.1
var step_height := 0.0
var foot_origins: Array[Vector3] = []
var gait_weight := 0.0
## The imported model has wing pivots, not a skeleton. A future rig adapter can
## replace _pose_carry_wings and grip transforms without changing this API.
var carried_item := ""
var carry_state := "idle"
var carry_blend := 0.0
var item_use := false
var use_blend := 0.0
var pending_item := ""
var carry_catalog: Dictionary = {}
var carry_root: Node3D
var item_nodes: Dictionary = {}
var left_grip: Node3D
var right_grip: Node3D
var seat_blend := 0.0
## While seated the visual rises onto the chair cushion and slides toward the
## desk, so the round body rests on the seat instead of passing through it.
## seat_lift = cushion top above the actor origin minus the body's 0.16 m base.
var seat_lift := 0.0
var seat_forward := 0.0
var upper_body_action := ""
var chicken_model: Node3D
var appearance: Dictionary = {}
var saved_appearance_signature := ""
## Secondary motion on the imported pivots: head bob, breathing, blinking and
## look-around. Purely visual; collision, gait timing and carry poses unchanged.
var head_pivot: Node3D
var player_kit: Node3D
var head_kit: Node3D
var body_pivot: Node3D
var head_origin := Vector3.ZERO
var head_rest := Vector3.ZERO
var body_scale := Vector3.ONE
var eyes: Array[Node3D] = []
var eye_scale: Array[Vector3] = []
var life_time := 0.0
var look_timer := 2.0
var look_target := Vector2.ZERO
var look_current := Vector2.ZERO
var blink_timer := 3.0
var blink_left := 0.0
var last_heading := 0.0
var turn_lean := 0.0
var bounce := 0.0
var previous_gait := 0.0

func _ready() -> void:
	collision_layer = 2
	collision_mask = 1
	floor_snap_length = .22
	safe_margin = .003
	var capsule := CapsuleShape3D.new()
	capsule.radius = .29
	capsule.height = 1.24
	shape_node = CollisionShape3D.new()
	shape_node.shape = capsule
	shape_node.position.y = .62
	add_child(shape_node)
	visual = Node3D.new()
	visual.name = "VisualPivot"
	add_child(visual)
	var model := (load("res://assets/player_chicken.glb") as PackedScene).instantiate() as Node3D
	chicken_model = model
	model.scale = Vector3.ONE*.62
	model.position.y = -.071 # feet, not the old display plinth, touch the floor
	visual.add_child(model)
	var stand := model.find_child("DisplayStand",true,false) as Node3D
	if stand: stand.queue_free()
	var kit := model.find_child("PlayerKit",true,false) as Node3D
	if kit: kit.visible = true
	for node in model.find_children("*", "MeshInstance3D", true, false):
		var name_text := str(node.name).replace("_"," ")
		if name_text == "Cream belly bib": node.visible = false
	left_foot = model.find_child("FootLeftPivot",true,false) as Node3D
	right_foot = model.find_child("FootRightPivot",true,false) as Node3D
	left_wing = model.find_child("WingLeftPivot",true,false) as Node3D
	right_wing = model.find_child("WingRightPivot",true,false) as Node3D
	if left_foot and right_foot:foot_origins=[left_foot.position,right_foot.position]
	head_pivot = model.find_child("HeadPivot",true,false) as Node3D
	body_pivot = model.find_child("BodyPivot",true,false) as Node3D
	if head_pivot: head_origin = head_pivot.position; head_rest = head_pivot.rotation
	# The headset was modelled beside the head, not under it. Move it onto the
	# head so look-around and head bobbing carry it along.
	player_kit = model.find_child("PlayerKit",true,false) as Node3D
	if head_pivot and player_kit:
		head_kit = Node3D.new(); head_kit.name = "HeadKit"; head_pivot.add_child(head_kit)
		for node in player_kit.find_children("*","MeshInstance3D",true,false):
			var part := str(node.name).to_lower()
			if part.begins_with("headphone") or part.begins_with("headset") or part.begins_with("microphone"):
				node.reparent(head_kit,true)
	if body_pivot: body_scale = body_pivot.scale
	for eye_name in ["Eye L","Eye R","Eye glint","Eye glint_001"]:
		var eye := model.find_child(eye_name,true,false) as Node3D
		if eye: eyes.append(eye); eye_scale.append(eye.scale)
	life_time = randf()*10.0
	blink_timer = randf_range(1.5,4.0)
	look_timer = randf_range(1.0,3.0)
	_prepare_carried_items()
	if _is_personal_avatar():
		add_to_group("career_personal_avatar")
		CareerBridge.changed.connect(_sync_appearance)
		_sync_appearance()

func _is_personal_avatar() -> bool:
	# NPC identity is assigned after super._ready(), so an empty npc_id is not
	# a reliable distinction. Presence of the subclass property is stable.
	for property in get_property_list():
		if str(property["name"]) == "npc_id": return false
	return true

func _sync_appearance() -> void:
	var avatar: Variant = CareerBridge.context.get("avatar", {})
	var raw: Variant = avatar.get("appearance", {}) if avatar is Dictionary else {}
	var saved := Appearance.normalize(raw if raw is Dictionary else {})
	var signature := JSON.stringify([CareerBridge.context.get("player", {}).get("id", ""), saved])
	# A calendar/news refresh must not erase the unsaved live preview. Only a
	# changed saved avatar or a different career identity replaces it.
	if signature == saved_appearance_signature: return
	saved_appearance_signature = signature
	apply_appearance(saved)

func apply_appearance(values: Dictionary) -> void:
	appearance = Appearance.normalize(values)
	if is_instance_valid(chicken_model): Appearance.apply_model(chicken_model, appearance)

func _physics_process(delta: float) -> void:
	if locked:
		velocity = Vector3.ZERO
		_animate(delta,0.0)
		return
	var direction := Vector3.ZERO
	var running := false
	if enabled:
		if test_mode:
			direction = test_direction.limit_length(1)
			running = test_run
		else:
			var axes := Input.get_vector("club_left","club_right","club_up","club_down")
			direction = Vector3(axes.x,0,axes.y).rotated(Vector3.UP,camera_yaw)
			running = Input.is_action_pressed("club_run")
	var speed := run_speed if running else walk_speed
	velocity.x = move_toward(velocity.x,direction.x*speed,18.0*delta)
	velocity.z = move_toward(velocity.z,direction.z*speed,18.0*delta)
	if not is_on_floor(): velocity.y -= 20.0*delta
	else: velocity.y = -.25
	_step_up(delta)
	move_and_slide()
	var actual := Vector2(get_real_velocity().x,get_real_velocity().z).length()
	if direction.length_squared()>.01:
		var target := atan2(direction.x,direction.z) # imported chicken faces +Z
		visual.rotation.y = lerp_angle(visual.rotation.y,target,1-exp(-14.0*delta))
	_animate(delta,actual)
	if global_position.y < -3:
		global_position = home
		reset_physics_interpolation()
		velocity = Vector3.ZERO
		recovered.emit()

func _animate(delta: float,speed: float) -> void:
	# Foot placement follows distance, not a fixed pendulum timer. The planted
	# part is longer than the lifted return; stopping blends to a neutral pose.
	gait_weight=move_toward(gait_weight,clampf(speed/walk_speed,0,1),delta*7)
	phase+=speed*delta*TAU/1.25
	seat_blend=move_toward(seat_blend,1.0 if seat_pose else 0.0,delta*5)
	var upper_still:=carry_state!="idle" or seat_pose
	# A small hop on every step (two per cycle), a waddle, a forward lean that
	# grows when trotting, and a lean into turns.
	var trot := clampf((speed-walk_speed)/maxf(.1,run_speed-walk_speed),0,1)
	var hop := absf(sin(phase))*(.028+.020*trot)*gait_weight
	visual.position.y=lerpf(visual.position.y,hop if not upper_still else seat_lift*seat_blend,1-exp(-18*delta))
	var facing:=Vector3(sin(visual.rotation.y),0,cos(visual.rotation.y))*seat_forward*seat_blend
	visual.position.x=lerpf(visual.position.x,facing.x,1-exp(-18*delta));visual.position.z=lerpf(visual.position.z,facing.z,1-exp(-18*delta))
	visual.rotation.z=lerpf(visual.rotation.z,(sin(phase)*.045*gait_weight+turn_lean) if not upper_still else 0.0,1-exp(-12*delta))
	visual.rotation.x=lerpf(visual.rotation.x,(.05+.09*trot)*gait_weight if not upper_still else .015*seat_blend,1-exp(-10*delta))
	if foot_origins.size()==2:
		for i in range(2):
			var foot: Node3D=left_foot if i==0 else right_foot
			var cycle: float=fposmod(phase/TAU+i*.5,1)
			var height:=0.0
			var forward:=0.0
			if cycle<.62:forward=lerpf(.24,-.24,cycle/.62)
			else:
				var swing: float=(cycle-.62)/.38
				forward=lerpf(-.24,.24,smoothstep(0,1,swing))
				height=sin(swing*PI)*.10
			foot.position=foot_origins[i]+Vector3(0,height,forward)*gait_weight
			# Seated: shins swing forward over the cushion edge.
			foot.rotation.x=lerpf(-forward*.45*gait_weight,-1.05 if seat_lift>.05 else -.65,seat_blend)
	_secondary_motion(delta,speed,upper_still)
	var running_weight := clampf((speed-walk_speed)/maxf(.1,run_speed-walk_speed),0,1)
	# Wings swing with the stride and open a little when trotting.
	var left_pose:=Vector3(-sin(phase)*(.14+.12*running_weight)*gait_weight,0,-.10*running_weight*gait_weight)
	var right_pose:=Vector3(sin(phase)*(.14+.12*running_weight)*gait_weight,0,.10*running_weight*gait_weight)
	if upper_body_action=="typing":
		left_pose=Vector3(-.65+.035*sin(phase*2),0,.10)
		right_pose=Vector3(-.65+.035*sin(phase*2+1.8),0,-.10)
	elif upper_body_action=="trophy_lift":
		# Both wings up around a cup held over the head, with a small pump.
		var lift:=sin(life_time*3.4)*.09
		left_pose=Vector3(-2.2+lift,0,.24);right_pose=Vector3(-2.2+lift,0,-.24)
	elif upper_body_action=="clap":
		var clap:=absf(sin(life_time*8.5))
		left_pose=Vector3(-.95,0,.38-clap*.3);right_pose=Vector3(-.95,0,-.38+clap*.3)
	if left_wing:left_wing.rotation=left_pose
	if right_wing:right_wing.rotation=right_pose
	_animate_carried_item(delta,left_pose,right_pose)

func _secondary_motion(delta: float,speed: float,upper_still: bool) -> void:
	life_time += delta
	var idle := clampf(1.0-gait_weight,0,1)
	# Turn lean from how fast the facing changes (only while walking).
	var heading := visual.rotation.y
	var turn_rate := wrapf(heading-last_heading,-PI,PI)/maxf(delta,.001)
	last_heading = heading
	turn_lean = lerpf(turn_lean,clampf(-turn_rate*.035,-.16,.16)*gait_weight,1-exp(-8*delta))
	# Start/stop squash: compress when the gait weight changes quickly.
	var gait_change := (gait_weight-previous_gait)/maxf(delta,.001)
	previous_gait = gait_weight
	bounce = lerpf(bounce,clampf(absf(gait_change)*.03,0,.06),1-exp(-12*delta))
	if body_pivot:
		var breathe := sin(life_time*2.3)*.016*idle
		var step_squash := absf(cos(phase))*.035*gait_weight
		var squash := breathe-step_squash-bounce
		body_pivot.scale = body_scale*Vector3(1.0-squash*.5,1.0+squash,1.0-squash*.5)
	if is_instance_valid(head_kit) and is_instance_valid(player_kit): head_kit.visible = player_kit.visible
	if head_pivot:
		# Look around now and then while standing; the body never turns, so a
		# seated or menu-facing pose keeps its exact direction.
		look_timer -= delta
		if look_timer <= 0:
			look_timer = randf_range(2.2,5.5)
			look_target = Vector2(randf_range(-.55,.55),randf_range(-.10,.16)) if randf() < .7 else Vector2.ZERO
		var target := look_target*idle if not upper_still or seat_pose else Vector2.ZERO
		look_current = look_current.lerp(target,1-exp(-3.5*delta))
		var peck := sin(phase*2.0)*.05*gait_weight
		head_pivot.rotation = head_rest+Vector3(look_current.y+peck*.6,look_current.x,0)
		head_pivot.position = head_origin+Vector3(0,sin(life_time*2.3+.6)*.006*idle,peck*.35)
	# Blink: quick vertical squash of the eyes and their glints.
	blink_timer -= delta
	if blink_timer <= 0:
		blink_left = .13
		blink_timer = randf_range(2.4,5.2) if randf() > .2 else .25
	if blink_left > 0: blink_left = maxf(0,blink_left-delta)
	var lid := 1.0-sin(clampf(blink_left/.13,0,1)*PI)*.9
	for index in range(eyes.size()):
		if is_instance_valid(eyes[index]): eyes[index].scale = eye_scale[index]*Vector3(1,lid,1)

func _prepare_carried_items() -> void:
	var source=JSON.parse_string(FileAccess.get_file_as_string("res://data/carried_items.json"))
	assert(source is Dictionary and source.get("schema_version")==1,"Invalid carried item data")
	carry_catalog=source["items"]
	carry_root=Node3D.new();carry_root.name="CarriedItems";visual.add_child(carry_root)
	if left_wing:
		left_grip=Node3D.new();left_grip.name="LeftGrip";left_grip.position=Vector3(0,-.49,.18);left_wing.add_child(left_grip)
	if right_wing:
		right_grip=Node3D.new();right_grip.name="RightGrip";right_grip.position=Vector3(0,-.49,.18);right_wing.add_child(right_grip)
	for kind in carry_catalog:
		var holder:=Node3D.new();holder.name=str(kind).capitalize();carry_root.add_child(holder)
		holder.visible=false;item_nodes[kind]=holder
		var groups: Dictionary={}
		for definition in carry_catalog[kind].get("groups",[]):
			var pivot:=Node3D.new();pivot.name=str(definition["id"])
			pivot.position=_item_vec(definition.get("position",[0,0,0]));pivot.rotation=_item_vec(definition.get("rotation",[0,0,0]))
			holder.add_child(pivot);groups[str(definition["id"])]=pivot
		for part in carry_catalog[kind]["parts"]:
			var mesh:=MeshInstance3D.new();mesh.name=str(part["id"])
			var dimensions: Array=part["size"]
			if part.get("shape","box")=="cylinder":
				var cylinder:=CylinderMesh.new();cylinder.top_radius=float(dimensions[0]);cylinder.bottom_radius=float(dimensions[0])*.94;cylinder.height=float(dimensions[1]);mesh.mesh=cylinder
			else:
				var box:=BoxMesh.new();box.size=_item_vec(dimensions);mesh.mesh=box
			mesh.position=_item_vec(part.get("position",[0,0,0]))
			var mat:=StandardMaterial3D.new();mat.albedo_color=Color(str(part["color"]));mat.roughness=.8
			mesh.material_override=mat
			var parent: Node=groups.get(str(part.get("parent","")),holder)
			parent.add_child(mesh)

func _item_vec(values: Array) -> Vector3:
	return Vector3(float(values[0]),float(values[1]),float(values[2]))

func set_carried_item(kind: String) -> void:
	if not kind.is_empty() and not carry_catalog.has(kind):return
	if kind==pending_item and carry_state!="idle":return
	pending_item=kind
	if kind==carried_item and not kind.is_empty():
		_set_carry_state("taking" if carry_blend<1.0 else ("using" if item_use else "holding"))
	elif not carried_item.is_empty():_set_carry_state("stowing")
	elif not kind.is_empty():_take_pending_item()

func set_item_use(active: bool) -> void:
	item_use=active
	if carry_state in ["holding","using"]:_set_carry_state("using" if active else "holding")

func _set_carry_state(next: String) -> void:
	if carry_state==next:return
	carry_state=next;carry_state_changed.emit(carried_item,carry_state)

func _take_pending_item() -> void:
	carried_item=pending_item;carry_blend=0.0;use_blend=0.0
	_update_item_attachment(carry_catalog[carried_item])
	(item_nodes[carried_item] as Node3D).visible=true
	_set_carry_state("taking")

func _animate_carried_item(delta: float,left_pose: Vector3,right_pose: Vector3) -> void:
	if carried_item.is_empty():return
	carry_blend=move_toward(carry_blend,0.0 if carry_state=="stowing" else 1.0,delta*4.5)
	use_blend=move_toward(use_blend,1.0 if item_use and carry_state!="stowing" else 0.0,delta*5)
	if carry_state=="taking" and carry_blend>=1:_set_carry_state("using" if item_use else "holding")
	if carry_state=="stowing" and carry_blend<=0:
		(item_nodes[carried_item] as Node3D).visible=false
		carried_item="";use_blend=0.0;_set_carry_state("idle")
		if not pending_item.is_empty():_take_pending_item()
		return
	var definition: Dictionary=carry_catalog[carried_item]
	_pose_carry_wings(definition,left_pose,right_pose)
	_update_item_attachment(definition)

func _pose_carry_wings(definition: Dictionary,left_pose: Vector3,right_pose: Vector3) -> void:
	var left_target:=_item_vec(definition["left_wing"]).lerp(_item_vec(definition["left_use"]),use_blend)
	var right_target:=_item_vec(definition["right_wing"]).lerp(_item_vec(definition["right_use"]),use_blend)
	if left_wing:left_wing.rotation=left_pose.lerp(left_target,smoothstep(0,1,carry_blend))
	if right_wing:right_wing.rotation=right_pose.lerp(right_target,smoothstep(0,1,carry_blend))

func _update_item_attachment(definition: Dictionary) -> void:
	if not left_grip or not right_grip:return
	var grip:=right_grip.global_position
	if definition.get("grip","both")=="both":
		# One wing receives the notebook first; the second supports it as both
		# grips converge. It never appears at the actor's origin for a frame.
		var middle:=left_grip.global_position.lerp(right_grip.global_position,.5)
		grip=grip.lerp(middle,smoothstep(0,1,carry_blend))
	var held: Node3D=item_nodes[carried_item]
	held.global_position=grip
	held.rotation=_item_vec(definition["rotation"]).lerp(_item_vec(definition["use_rotation"]),use_blend)
	for group in definition.get("groups",[]):
		var pivot:=held.find_child(str(group["id"]),true,false) as Node3D
		if pivot:pivot.rotation=_item_vec(group.get("rotation",[0,0,0])).lerp(_item_vec(group.get("use_rotation",group.get("rotation",[0,0,0]))),use_blend)

func clear_presentation() -> void:
	seat_pose=false;upper_body_action="";item_use=false;pending_item=""
	for held in item_nodes.values():(held as Node3D).visible=false
	carried_item="";carry_blend=0.0;use_blend=0.0;_set_carry_state("idle")

func _step_up(delta: float) -> void:
	if step_height<=0 or not is_on_floor():return
	var motion:=Vector3(velocity.x,0,velocity.z)*delta
	if motion.length()<.001:return
	var collision:=KinematicCollision3D.new()
	if not test_move(global_transform,motion,collision):return
	if collision.get_normal().y>.3:return
	# Test body clearance and landing; never step onto an unverified height.
	if test_move(global_transform,Vector3.UP*step_height):return
	var candidate:=global_transform;candidate.origin.y+=step_height
	if test_move(candidate,motion):return
	candidate.origin+=motion
	var floor_hit:=KinematicCollision3D.new()
	if test_move(candidate,Vector3.DOWN*(step_height+.08),floor_hit) and floor_hit.get_normal().y>.7:
		var landing: float=candidate.origin.y+floor_hit.get_travel().y
		if landing>global_position.y+.015 and landing-global_position.y<=step_height+.01:
			global_position.y=landing+.004

func face_toward(target: Vector3) -> void:
	var d := target-global_position
	if Vector2(d.x,d.z).length()>.01: visual.rotation.y = atan2(d.x,d.z)
