extends Node
const Player = preload("res://scripts/chicken_player.gd")
## Data-driven local interactions. The signals are the future career adapter;
## this prototype only changes session-local values, never saves or rewards.
signal action_started(id: String,kind: String)
signal action_completed(id: String,effects: Dictionary)
signal action_cancelled(id: String)
signal message(text: String)
signal stats_changed
var items: Array[Dictionary] = []
var current: Dictionary = {}
var active: Dictionary = {}
var elapsed := 0.0
var values := {"energy":65,"focus":55,"mood":70}
var cooldowns: Dictionary = {}
var player: Player
var saved_position := Vector3.ZERO
var completed: Dictionary = {}
var cooldown_clock := 0.0
var retained_device: Dictionary = {}

func configure(actor: Player) -> void:
	player = actor
	var source = JSON.parse_string(FileAccess.get_file_as_string("res://data/interactions.json"))
	assert(source is Dictionary and source.get("schema_version")==1,"Invalid interaction data")
	var ids := {}
	var carried=JSON.parse_string(FileAccess.get_file_as_string("res://data/carried_items.json"))
	var overrides: Dictionary=carried.get("world_interactions",{})
	for raw in source["items"]:
		if raw.get("id")=="teammate":continue # replaced by the moving NPC, no phantom talk spot
		assert(not ids.has(raw["id"]),"Duplicate interaction ID")
		ids[raw["id"]] = true
		assert(raw["anchor"].size()==3 and float(raw["range"])>0)
		var item: Dictionary=raw.duplicate(true)
		if overrides.has(str(item["id"])):item.merge(overrides[str(item["id"])],true)
		items.append(item)

func vec(a: Array) -> Vector3:
	return Vector3(float(a[0]),float(a[1]),float(a[2]))

func available(item: Dictionary) -> bool:
	if item.is_empty():return false
	var anchor := vec(item["anchor"])
	var origin := player.global_position + Vector3(0,.65,0)
	if Vector2(origin.x-anchor.x,origin.z-anchor.z).length()>float(item["range"]): return false
	# The approach anchor is outside the object. Walls and other furniture
	# block the reach ray, so E cannot operate the next room through a wall.
	var target := Vector3(anchor.x,origin.y,anchor.z)
	var query := PhysicsRayQueryParameters3D.create(origin,target,1)
	query.exclude = [player.get_rid()]
	var space:=player.get_world_3d().direct_space_state
	if not space.intersect_ray(query).is_empty():return false
	if str(item.get("id",""))=="computer" and item.has("seat"):
		var probe:=PhysicsShapeQueryParameters3D.new();var sphere:=SphereShape3D.new();sphere.radius=.33
		probe.shape=sphere;probe.transform.origin=vec(item["seat"])+Vector3(0,.6,0);probe.collision_mask=4
		if not space.intersect_shape(probe,1).is_empty():return false
	return true

func nearest() -> Dictionary:
	var best: Dictionary = {}
	var score := INF
	for item in items:
		if not available(item): continue
		var a := vec(item["anchor"])
		var distance := Vector2(a.x-player.position.x,a.z-player.position.z).length()
		if distance<score: score=distance; best=item
	return best

func reachable(id: String) -> Dictionary:
	for item in items:
		if str(item["id"])==id and available(item): return item
	return {}

func request() -> bool:
	if not active.is_empty(): return false
	current = nearest()
	if current.is_empty(): return false
	return start(current)

func start(item: Dictionary) -> bool:
	if not active.is_empty() or not retained_device.is_empty() or not available(item): return false
	var id := str(item["id"])
	if float(cooldowns.get(id,0))>cooldown_clock:
		message.emit("刚刚做过了，过几秒再来吧。")
		return false
	if float(item["seconds"])<=0:
		message.emit(str(item["text"]))
		action_completed.emit(id,{})
		return true
	active = item
	elapsed = 0
	saved_position = player.global_position
	player.locked = true
	player.velocity = Vector3.ZERO
	player.face_toward(vec(item["look"]))
	if item.has("seat"):
		# Only the short seating transition is snapped; normal locomotion
		# always uses move_and_slide. Exit restores the verified approach spot.
		player.global_position = vec(item["seat"])
		player.reset_physics_interpolation()
		player.seat_pose = true
		player.face_toward(vec(item["seat_look"]))
	action_started.emit(id,str(item["kind"]))
	return true

func _physics_process(delta: float) -> void:
	cooldown_clock += delta
	if player==null: return
	if active.is_empty():
		current = nearest()
		return
	elapsed += delta
	if elapsed>=float(active["seconds"]): finish()

func finish() -> void:
	if active.is_empty(): return
	var done := active
	if str(done["id"])=="computer":
		# The screen owns the rest of this seated session. Finishing the short
		# approach must not stand the actor up while its menu remains open.
		retained_device=done;active={};elapsed=0
	else:_restore()
	for key in done["effects"]:
		if values.has(key): values[key] = clampi(int(values[key])+int(done["effects"][key]),0,100)
	cooldowns[done["id"]] = cooldown_clock+float(done.get("cooldown",5))
	completed[done["id"]] = int(completed.get(done["id"],0))+1
	stats_changed.emit()
	message.emit(str(done["text"]))
	action_completed.emit(str(done["id"]),done["effects"])

func cancel() -> void:
	if active.is_empty() and retained_device.is_empty(): return
	var id := str(active.get("id",retained_device.get("id","")))
	_restore()
	message.emit("已停止，未结算这次交互。")
	action_cancelled.emit(id)

func _restore() -> void:
	if active.has("seat") or retained_device.has("seat"):
		player.global_position = saved_position
		player.reset_physics_interpolation()
	player.seat_pose = false
	player.locked = false
	player.velocity = Vector3.ZERO
	active = {}
	retained_device = {}
	elapsed = 0

func release_device() -> void:
	if not retained_device.is_empty():_restore()

func _exit_tree() -> void:
	if is_instance_valid(player):
		_restore();player.clear_presentation()

func progress() -> float:
	return 0.0 if active.is_empty() else clampf(elapsed/float(active["seconds"]),0,1)
