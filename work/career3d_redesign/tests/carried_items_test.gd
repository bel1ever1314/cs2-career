extends Node
## Focused assertions for visible attachments and real device seating. This
## suite uses the actual scene/controller, not a replacement movement model.
var app
var failures: Array[String]=[]
var checks:=0
var transitions: Array[String]=[]

func check(ok: bool,label: String) -> void:
	checks+=1
	if not ok:failures.append(label)
	print("CARRY_CHECK ","PASS " if ok else "FAIL ",label)

func frames(count: int) -> void:
	for _i in range(count):await get_tree().physics_frame

func item(id: String) -> Dictionary:
	for candidate in app.interactions.items:
		if str(candidate["id"])==id:return candidate
	return {}

func run(application) -> void:
	app=application
	await frames(10)
	var actor=app.player
	app.life.enabled=false;app.life.held=true
	check(actor.is_on_floor(),"real controller starts on the floor")
	for child in actor.get_children():
		check(not child is GeometryInstance3D and not child is Label3D,"no player ring or world-space name")
	for npc in app.life.roster:
		check(not npc.nameplate.is_visible_in_tree(),"NPC identity is not floating: "+npc.npc_id)
	actor.carry_state_changed.connect(func(_kind,state):transitions.append(state))
	actor.set_carried_item("notebook");actor.set_item_use(true)
	check(actor.carry_state=="taking","notebook starts with a taking transition")
	await frames(24)
	check(actor.carried_item=="notebook" and actor.carry_state=="using","notebook settles into use")
	var book: Node3D=actor.item_nodes["notebook"]
	var grip_mid: Vector3=actor.left_grip.global_position.lerp(actor.right_grip.global_position,.5)
	check(book.visible and book.global_position.distance_to(grip_mid)<.001,"paper notebook is attached to both wing grips")
	check(book.find_child("PaperPages",true,false)!=null and book.find_child("ClothCover",true,false)!=null,"notebook has physical pages and cloth cover")
	var left_rotation: Vector3=actor.left_wing.rotation
	var right_rotation: Vector3=actor.right_wing.rotation
	var before: Vector3=actor.position
	actor.test_direction=Vector3(0,0,1)
	await frames(24)
	check(actor.position.distance_to(before)>.25 and actor.get_real_velocity().length()>.5,"carrying still uses physical walking")
	check(actor.left_wing.rotation.distance_to(left_rotation)<.002 and actor.right_wing.rotation.distance_to(right_rotation)<.002,"walking does not swing the held upper body")
	check(absf(actor.visual.rotation.z)<.002,"carrying removes torso sway")
	actor.test_direction=Vector3.ZERO
	actor.set_item_use(false);actor.set_carried_item("")
	check(actor.carry_state=="stowing","notebook has a stowing transition")
	await frames(24)
	check(actor.carry_state=="idle" and not book.visible,"stowing ends with a hidden notebook")
	app.set_device_open(true,"phone")
	await frames(24)
	var phone: Node3D=actor.item_nodes["phone"]
	check(actor.carried_item=="phone" and actor.carry_state=="using","phone device requests the phone pose")
	check(phone.global_position.distance_to(actor.right_grip.global_position)<.001,"phone rests in the right wing grip")
	app.set_device_open(false,"phone")
	await frames(24)
	check(not actor.locked and actor.carry_state=="idle","closing phone restores walking and stows it")
	actor.set_carried_item("laptop");actor.set_item_use(true)
	await frames(24)
	var laptop: Node3D=actor.item_nodes["laptop"]
	var hinge:=laptop.find_child("LidHinge",true,false) as Node3D
	grip_mid=actor.left_grip.global_position.lerp(actor.right_grip.global_position,.5)
	check(actor.carried_item=="laptop" and laptop.global_position.distance_to(grip_mid)<.001,"laptop base is supported by both wing grips")
	check(hinge and absf(hinge.rotation.x-.15)<.002,"using laptop opens its physical screen hinge")
	actor.set_item_use(false)
	await frames(18)
	check(hinge and absf(hinge.rotation.x+1.50)<.002,"stopping laptop use folds the screen closed")
	actor.set_carried_item("")
	await frames(24)
	actor.position=Vector3(11.55,.23,8.6);actor.reset_physics_interpolation()
	await frames(3)
	check(app.world_target().is_empty() and not app.prompt_panel.visible and app.prompt_label.text.is_empty(),"no reachable target means no E prompt")
	var board:=item("whiteboard")
	actor.position=app.interactions.vec(board["anchor"]);actor.position.y=.23;actor.reset_physics_interpolation()
	await frames(3)
	check(app.interactions.start(board),"whiteboard offers a physical notebook interaction")
	await frames(24)
	check(actor.carried_item=="notebook" and book.visible,"whiteboard visibly holds the paper notebook")
	app.interactions.cancel()
	await frames(24)
	check(actor.carry_state=="idle" and not actor.locked,"E-equivalent cancel stows the notebook")
	var reader=app.life.roster[0]
	reader.start_job("carry_fixture",{"action":"review","label":"复盘","look":[0,1.2,-8]},3)
	await frames(24)
	check(reader.carried_item=="notebook" and reader.carry_state=="using","NPC review uses the same notebook controller")
	var reader_rotation: Vector3=reader.left_wing.rotation
	await frames(12)
	check(reader.left_wing.rotation.distance_to(reader_rotation)<.002,"NPC activity pose does not overwrite carried wing pose")
	var computer:=item("computer")
	var saved_npcs: Dictionary={}
	for npc in app.life.roster:
		saved_npcs[npc.npc_id]=npc.position;npc.position=Vector3(9,.23,8);npc.collision_layer=0
	actor.position=app.interactions.vec(computer["anchor"]);actor.position.y=.23;actor.reset_physics_interpolation()
	await frames(3)
	check(app.interactions.available(computer),"computer approach is reachable from the real chair side")
	var occupied=app.life.roster[0]
	occupied.position=app.interactions.vec(computer["seat"]);occupied.collision_layer=4
	await frames(2)
	check(not app.interactions.available(computer),"an occupied computer seat cannot be used")
	occupied.position=Vector3(9,.23,8);occupied.collision_layer=0
	await frames(2)
	var approach: Vector3=actor.position
	check(app.interactions.start(computer),"computer starts its short seating transition")
	await frames(60)
	check(app.device_kind=="computer" and CareerBridge.phone_open,"computer opens its own device screen")
	check(actor.seat_pose and actor.locked and not app.interactions.retained_device.is_empty(),"computer menu retains the seated actor after interaction completes")
	var seated: Vector3=actor.position
	var seat_yaw: float=actor.visual.rotation.y
	await frames(20)
	check(actor.position.distance_to(seated)<.001 and absf(actor.visual.rotation.y-seat_yaw)<.001,"menu keeps the seat position and screen-facing direction")
	check(actor.carried_item!="phone","computer interaction does not summon a phone")
	Computer.close_computer()
	await frames(24)
	check(not CareerBridge.phone_open and not actor.locked and not actor.seat_pose,"closing computer stands up and resumes movement")
	check(actor.position.distance_to(approach)<.04 and app.interactions.retained_device.is_empty(),"closing computer restores the verified approach point")
	check("taking" in transitions and "using" in transitions and "stowing" in transitions and "idle" in transitions,"carry state transitions are observable")
	print("CARRY_TEST_RESULT ",JSON.stringify({"checks":checks,"failures":failures,"transitions":transitions}))
	get_tree().quit(0 if failures.is_empty() else 1)
