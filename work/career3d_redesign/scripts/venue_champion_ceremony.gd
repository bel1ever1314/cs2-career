extends CanvasLayer
## Display-only five-person victory cutscene. Official results decide eligibility.
## The temporary viewport never moves the real visitor, teammates or saved career.
signal finished
signal lift_started
const UI = preload("res://scripts/computer_ui.gd")
const Competitor = preload("res://scripts/venue_competitor.gd")
const Roster = preload("res://scripts/venue_match_roster.gd")
const DURATION := 8.0
const LIFT_START := 1.8
const LIFT_END := 3.25
var evidence: Dictionary = {}
var elapsed := 0.0
var active := false
var raised := false
var actors: Array[Node3D] = []
var cup: Node3D
var viewport: SubViewport
var camera: Camera3D
var confetti: MultiMeshInstance3D
var overlay: Control
var continue_button: Button
var phase_label: Label
var finished_count := 0
var visuals_ready := false

static func plan(award: Dictionary, participation: Dictionary) -> Dictionary:
	if award.get("kind", "") != "event_awards" or award.get("source", "") != "completed_event.awards" or not bool(award.get("participated", false)): return {}
	var own := str(award.get("own_team", ""))
	var human := str(award.get("human_id", ""))
	var event_id := str(award.get("event_id", ""))
	if own.is_empty() or human.is_empty() or event_id.is_empty() or str(award.get("champion", "")) != own: return {}
	if not bool(participation.get("personal", false)) or participation.get("destination", "") not in ["lan", "major"]: return {}
	if str(participation.get("stage", "")) != "GF" or str(participation.get("event_id", "")) != event_id: return {}
	var snapshot: Dictionary = participation.get("result", {})
	if not bool(snapshot.get("played", false)) or str(snapshot.get("winner", "")) != own or snapshot.get("maps", []).is_empty(): return {}
	if str(snapshot.get("player_id", "")) != human or str(snapshot.get("player_team", "")) != own: return {}
	var frozen: Dictionary = participation.get("roster", {})
	if str(frozen.get("own_team", "")) != own or str(frozen.get("human_id", "")) != human or str(frozen.get("match_id", "")) != str(snapshot.get("match_id", snapshot.get("id", ""))): return {}
	var rows: Array = frozen.get("own", [])
	if rows.size() != 5: return {}
	var ids: Dictionary = {}
	var human_index := -1
	for index in range(rows.size()):
		if not rows[index] is Dictionary: return {}
		var id := Roster.identity(rows[index])
		if id.is_empty() or ids.has(id) or str(rows[index].get("name", "")).strip_edges().is_empty(): return {}
		ids[id] = true
		if id == human: human_index = index
	if human_index < 0: return {}
	var order: Array = rows.duplicate(true)
	var player: Dictionary = order.pop_at(human_index)
	order.insert(2, player)
	return {"id":str(award.get("id", "")), "event_id":event_id, "event_name":str(award.get("event_name", "赛事冠军")),
		"team":own, "human_id":human, "players":order, "destination":participation.destination,
		"match_id":str(frozen.match_id), "appearance":participation.get("appearance", {}).duplicate(true)}

func _ready() -> void:
	layer = 36
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_process(false)

func start(value: Dictionary) -> bool:
	if active or value.get("players", []).size() != 5: return false
	evidence = value.duplicate(true)
	elapsed = 0.0
	raised = false
	active = true
	_build()
	visuals_ready = true
	_process(0.0)
	set_process(true)
	return true

func _build() -> void:
	overlay = Control.new()
	overlay.name = "ChampionshipTrophyLift"
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(overlay)
	var screen := SubViewportContainer.new()
	screen.name = "ChampionStageViewport"
	screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	screen.stretch = true
	screen.mouse_filter = Control.MOUSE_FILTER_IGNORE
	overlay.add_child(screen)
	viewport = SubViewport.new()
	viewport.name = "VictoryWorld"
	viewport.own_world_3d = true
	viewport.size = Vector2i(1280, 720)
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	screen.add_child(viewport)
	var world := Node3D.new()
	world.name = "ChampionshipStage"
	viewport.add_child(world)
	var environment := WorldEnvironment.new()
	var ambience := Environment.new()
	ambience.background_mode = Environment.BG_COLOR
	ambience.background_color = Color("07131e")
	ambience.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	ambience.ambient_light_color = Color("b5c8d2")
	ambience.ambient_light_energy = .75
	ambience.tonemap_mode = Environment.TONE_MAPPER_ACES
	environment.environment = ambience
	world.add_child(environment)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-35, -25, 0)
	light.light_color = Color("ffe4ba")
	light.light_energy = 1.5
	world.add_child(light)
	var backlight := OmniLight3D.new()
	backlight.position = Vector3(0, 3.3, -1.3)
	backlight.light_color = Color("eabd61")
	backlight.light_energy = 2.0
	backlight.omni_range = 9.0
	world.add_child(backlight)
	_box(world, "VictoryPodium", Vector3(0, -.10, 0), Vector3(8.0, .20, 3.4), Color("1d3143"))
	_box(world, "GoldenPodiumEdge", Vector3(0, -.025, 1.72), Vector3(8.0, .05, .025), Color("efcf78"), true)
	_box(world, "DarkStageBackdrop", Vector3(0, 2.1, -1.9), Vector3(12.0, 4.4, .16), Color("101c2a"))
	for x in [-4.3, 4.3]:
		_box(world, "StageLightColumn", Vector3(x, 1.65, -1.78), Vector3(.07, 3.3, .03), Color("e3b866"), true)
	_sign(world, str(evidence.event_name), Vector3(0, 3.05, -1.78), 46, Color("e7c77d"))
	_sign(world, str(evidence.team), Vector3(0, 2.42, -1.78), 68, Color("f5eddb"))
	_sign(world, "CHAMPIONS", Vector3(0, 1.91, -1.78), 30, Color("a8c9cd"))
	for index in range(5):
		var row: Dictionary = evidence.players[index]
		var actor = Competitor.new()
		actor.name = "Champion_" + str(index)
		actor.position = Vector3((index - 2) * 1.3, 0, .85)
		actor.locked = true
		actor.test_mode = true
		world.add_child(actor)
		actor.set_physics_process(false)
		actor.setup_identity(row, str(evidence.team), Color("355d72"))
		if index == 2 and not evidence.appearance.is_empty(): actor.apply_appearance(evidence.appearance)
		actor.face_toward(actor.position + Vector3(0, 0, 1))
		actors.append(actor)
		_sign(world, str(row.get("name", "")) + (" · 你" if index == 2 else ""), Vector3((index - 2) * 1.3, .16, 1.3), 24, Color("f3d588") if index == 2 else Color("d4dfde"))
	cup = _cup(world)
	cup.position = Vector3(0, 1.13, .33)
	camera = Camera3D.new()
	camera.name = "ChampionCamera"
	camera.current = true
	camera.fov = 48
	camera.position = Vector3(0, 2.7, 8.3)
	world.add_child(camera)
	camera.look_at(Vector3(0, 1.45, 0), Vector3.UP)
	confetti = MultiMeshInstance3D.new()
	confetti.name = "GoldenConfetti"
	var fragments := MultiMesh.new()
	fragments.transform_format = MultiMesh.TRANSFORM_3D
	fragments.use_colors = true
	var paper := BoxMesh.new()
	paper.size = Vector3(.045, .07, .008)
	fragments.mesh = paper
	fragments.instance_count = 88
	for index in range(fragments.instance_count):
		fragments.set_instance_color(index, Color("f3cc70") if index % 3 else Color("e8e4cd"))
	confetti.multimesh = fragments
	var material := StandardMaterial3D.new()
	material.vertex_color_use_as_albedo = true
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	confetti.material_override = material
	confetti.visible = false
	world.add_child(confetti)
	var heading := Label.new()
	heading.name = "ChampionCelebrationHeading"
	heading.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	heading.offset_top = 22
	heading.offset_bottom = 68
	heading.text = "我们夺冠了！"
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	heading.add_theme_font_override("font", UI.Base.font())
	heading.add_theme_font_size_override("font_size", 30)
	heading.add_theme_color_override("font_color", Color("f4dfae"))
	heading.mouse_filter = Control.MOUSE_FILTER_IGNORE
	overlay.add_child(heading)
	var footer := VBoxContainer.new()
	footer.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	footer.offset_top = -104
	footer.offset_bottom = -18
	footer.alignment = BoxContainer.ALIGNMENT_CENTER
	overlay.add_child(footer)
	phase_label = UI.label(footer, "和队友一起走向奖杯", 16, Color("eee7d5"))
	phase_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	continue_button = UI.button(footer, "查看赛事荣誉", finish)
	continue_button.name = "ChampionCeremonyContinue"
	continue_button.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	continue_button.custom_minimum_size.x = 220
	continue_button.disabled = true
	UI.primary(continue_button)

func _box(parent: Node3D, id: String, at: Vector3, dimensions: Vector3, color: Color, glow: bool = false) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	mesh.name = id
	var box := BoxMesh.new()
	box.size = dimensions
	mesh.mesh = box
	mesh.position = at
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = .52
	if glow:
		material.emission_enabled = true
		material.emission = color
		material.emission_energy_multiplier = .65
	mesh.material_override = material
	parent.add_child(mesh)
	return mesh

func _sign(parent: Node3D, text: String, at: Vector3, font_size: int, color: Color) -> void:
	var label := Label3D.new()
	label.text = text
	label.name = "ChampionStageName"
	label.position = at
	label.font = UI.Base.font()
	label.font_size = font_size
	label.pixel_size = .007
	label.modulate = color
	label.outline_size = 6
	parent.add_child(label)

func _cup(parent: Node3D) -> Node3D:
	var holder := Node3D.new()
	holder.name = "ChampionCup"
	parent.add_child(holder)
	var gold := StandardMaterial3D.new()
	gold.albedo_color = Color("e6c15b")
	gold.metallic = .82
	gold.roughness = .24
	_box(holder, "TrophyBase", Vector3(0, -.16, 0), Vector3(.30, .08, .24), Color("17263a"))
	for definition in [["TrophyStem", .038, .038, .24, -.005], ["TrophyBowl", .21, .092, .23, .19]]:
		var mesh := MeshInstance3D.new()
		mesh.name = str(definition[0])
		var shape := CylinderMesh.new()
		shape.top_radius = float(definition[1])
		shape.bottom_radius = float(definition[2])
		shape.height = float(definition[3])
		shape.radial_segments = 24
		mesh.mesh = shape
		mesh.position.y = float(definition[4])
		mesh.material_override = gold
		holder.add_child(mesh)
	for side in [-1.0, 1.0]:
		var mesh := MeshInstance3D.new()
		mesh.name = "TrophyHandleLeft" if side < 0 else "TrophyHandleRight"
		var ring := TorusMesh.new()
		ring.inner_radius = .085
		ring.outer_radius = .12
		mesh.mesh = ring
		mesh.rotation.x = PI * .5
		mesh.position = Vector3(side * .21, .20, 0)
		mesh.material_override = gold
		holder.add_child(mesh)
	return holder

func _process(delta: float) -> void:
	if not active or not visuals_ready: return
	elapsed += delta
	var advance := smoothstep(0.0, 1.5, elapsed)
	var lift := smoothstep(LIFT_START, LIFT_END, elapsed)
	for index in range(actors.size()):
		var actor = actors[index]
		actor.position.z = lerpf(.85, 0.0, advance)
		actor._animate(minf(delta, .1), .55 if elapsed < 1.5 else 0.0)
		if index == 2:
			if actor.left_wing: actor.left_wing.rotation = Vector3(lerpf(-.68, -2.7, lift), 0, lerpf(.1, .28, lift))
			if actor.right_wing: actor.right_wing.rotation = Vector3(lerpf(-.68, -2.7, lift), 0, lerpf(-.1, -.28, lift))
		elif elapsed >= LIFT_START:
			var cheer := .13 * sin(elapsed * 3.8 + index)
			if actor.left_wing: actor.left_wing.rotation = Vector3((-1.85 + cheer) * lift, 0, .35 * lift)
			if actor.right_wing: actor.right_wing.rotation = Vector3((-1.85 - cheer) * lift, 0, -.35 * lift)
			actor.visual.position.y = absf(sin(elapsed * 3.2 + index)) * .045 * lift
	# Wings are short on this mascot. Anchor the cup to its actual two grips,
	# not to an imagined human arm height that leaves it floating above the bird.
	var lifter = actors[2]
	if is_instance_valid(lifter.left_grip) and is_instance_valid(lifter.right_grip):
		cup.global_position = lifter.left_grip.global_position.lerp(lifter.right_grip.global_position, .5) + Vector3(0, .15, .18)
	if elapsed >= LIFT_START and not raised:
		raised = true
		phase_label.text = str(evidence.team) + " · 冠军属于我们"
		lift_started.emit()
	confetti.visible = elapsed >= LIFT_END
	if confetti.visible:
		for index in range(confetti.multimesh.instance_count):
			var time := elapsed - LIFT_END + index * .11
			var at := Vector3(sin(index * 2.7) * 3.6 + sin(time * 1.4) * .15, 4.2 - fposmod(time * .8, 4.5), .45 + cos(index * 1.8) * 1.9)
			confetti.multimesh.set_instance_transform(index, Transform3D(Basis.from_euler(Vector3(time, time * .7, index + time)), at))
	continue_button.disabled = elapsed < LIFT_END + .35
	if elapsed >= DURATION: finish()

func finish() -> void:
	if not active: return
	active = false
	set_process(false)
	finished_count += 1
	finished.emit()

func diagnostic_snapshot() -> Dictionary:
	var names: Array[String] = []
	for actor in actors: names.append(str(actor.display_name))
	return {"active":active, "event_id":evidence.get("event_id", ""), "team":evidence.get("team", ""),
		"actors":actors.size(), "player_id":evidence.get("human_id", ""), "names":names,
		"lift_started":raised, "trophy_height":cup.position.y if is_instance_valid(cup) else 0.0, "elapsed":elapsed,
		"finished_count":finished_count, "changes_career":false, "changes_venue_actors":false}
