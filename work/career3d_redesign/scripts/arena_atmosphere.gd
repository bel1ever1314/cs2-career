extends Node3D
## Closed sports bowl: dark audience, bright stage, readable access routes.
## A single doorway cue unfolds on the original music's 112 BPM grid.

const SAMPLE_RATE := 12000
const TAU_F := PI * 2.0
const ENTRANCE_BPM := 112.0
const ENTRANCE_BEAT := 60.0 / ENTRANCE_BPM
const ENTRANCE_PHRASE_SECONDS := ENTRANCE_BEAT * 32.0
const CompetitiveCue = preload("res://scripts/arena_competitive_cue.gd")
var competitive := false
var entrance_bpm := ENTRANCE_BPM
var portal_landed := false
var entrance_duck := 1.0
var master_volume := 0.7
var muted := false
var showtime := false
var paused := false
var exposure_mix := 0.0
var interior_mix := 0.0
var entrance_triggered := false
var entrance_count := 0
var roof_mesh: MeshInstance3D
var upper_walls: MeshInstance3D
var venue_environment: Environment
var venue_sun: DirectionalLight3D
var passage_lights: Array[OmniLight3D] = []
var bowl_lights: Array[OmniLight3D] = []
var stage_lights: Array[SpotLight3D] = []
var face_lights: Array[SpotLight3D] = []
var entrance_accents: Array[SpotLight3D] = []
var screen_material: ShaderMaterial
var stage_subtitle: Label3D
var entrance_elapsed := 0.0
var entrance_envelope := 0.0
var beat_envelope := 0.0
var audio_source := "original local soundscape"
var screen_count := 0
var audio_layers: Dictionary = {}
var layer_gains: Dictionary = {}
var config: Dictionary = {}
var shell_segments := 0
var synthesised_frames := 0

func setup(environment: Environment, daylight: DirectionalLight3D, options: Dictionary = {}) -> void:
	name = "ArenaAtmosphere"
	config = options
	competitive = bool(options.get("competitive", false))
	entrance_bpm = CompetitiveCue.BPM if competitive else ENTRANCE_BPM
	venue_environment = environment
	venue_sun = daylight
	master_volume = clampf(float(options.get("master_volume", 0.7)), 0.0, 1.0)
	muted = bool(options.get("muted", false))
	_build_enclosure()
	_build_lighting()
	_build_stage_media()
	_build_audio()
	update_visitor(Vector3(0, 0.56, 56.8), 1.0, false)

func _material(color: String, emission: String = "", energy: float = 0.0) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(color)
	material.roughness = 0.87
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	if not emission.is_empty():
		material.emission_enabled = true
		material.emission = Color(emission)
		material.emission_energy_multiplier = energy
	return material

func _triangle(surface: SurfaceTool, a: Vector3, b: Vector3, c: Vector3) -> void:
	surface.add_vertex(a)
	surface.add_vertex(b)
	surface.add_vertex(c)

func _quad(surface: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3) -> void:
	_triangle(surface, a, b, c)
	_triangle(surface, a, c, d)

func _surface(name_text: String, surface: SurfaceTool, material: Material, solid: bool = false) -> MeshInstance3D:
	surface.generate_normals()
	var instance := MeshInstance3D.new()
	instance.name = name_text
	instance.mesh = surface.commit()
	instance.material_override = material
	add_child(instance)
	if solid:
		var body := StaticBody3D.new()
		body.name = name_text + "Collision"
		body.collision_layer = 1
		body.collision_mask = 2
		var shape := CollisionShape3D.new()
		shape.shape = instance.mesh.create_trimesh_shape()
		(shape.shape as ConcavePolygonShape3D).backface_collision = true
		body.add_child(shape)
		add_child(body)
	return instance

func _box(name_text: String, at: Vector3, size: Vector3, material: Material) -> MeshInstance3D:
	var instance := MeshInstance3D.new()
	instance.name = name_text
	var cube := BoxMesh.new()
	cube.size = size
	instance.mesh = cube
	instance.material_override = material
	instance.position = at
	add_child(instance)
	return instance

func _beam(name_text: String, a: Vector3, b: Vector3, width: float, material: Material) -> void:
	var instance := _box(name_text, (a + b) * 0.5, Vector3(width, width, a.distance_to(b)), material)
	var direction := (b - a).normalized()
	instance.look_at(b, Vector3.RIGHT if absf(direction.dot(Vector3.UP)) > 0.98 else Vector3.UP)

func _build_enclosure() -> void:
	# The existing 104 m-wide horseshoe bowl ends at 13.3 m; people remain
	# human-scale. A 25.6 m eave and 29 m crown clear its 22 m stage arch.
	var ring := PackedVector3Array([Vector3(-52.0, 0, -34.0), Vector3(52.0, 0, -34.0)])
	var divisions := 48
	for i in range(divisions + 1):
		var angle := PI * float(i) / divisions
		ring.append(Vector3(52.0 * cos(angle), 0, -3.0 + 52.0 * sin(angle)))
	shell_segments = ring.size()
	var roof := SurfaceTool.new()
	var walls := SurfaceTool.new()
	var lower := SurfaceTool.new()
	roof.begin(Mesh.PRIMITIVE_TRIANGLES)
	walls.begin(Mesh.PRIMITIVE_TRIANGLES)
	lower.begin(Mesh.PRIMITIVE_TRIANGLES)
	var crown := Vector3(0, 29.0, 3.0)
	for i in range(ring.size()):
		var a := ring[i]
		var b := ring[(i + 1) % ring.size()]
		var a_top := a + Vector3.UP * 25.6
		var b_top := b + Vector3.UP * 25.6
		var a_inner := Vector3(a.x * 0.48, 28.4, lerpf(3.0, a.z, 0.48))
		var b_inner := Vector3(b.x * 0.48, 28.4, lerpf(3.0, b.z, 0.48))
		_quad(roof, a_top, b_top, b_inner, a_inner)
		_triangle(roof, a_inner, b_inner, crown)
		_quad(walls, a + Vector3.UP * 13.4, b + Vector3.UP * 13.4, b_top, a_top)
		# One central 6.8 m portal meets the existing 5.7 m tunnel. It is an
		# opening in the real collision mesh, never a walk-through wall.
		var portal := absf(a.x) < 3.6 and absf(b.x) < 3.6 and minf(a.z, b.z) > 48.0
		var base_height := 5.1 if portal else 0.3
		_quad(lower, a + Vector3.UP * base_height, b + Vector3.UP * base_height,
			b + Vector3.UP * 13.4, a + Vector3.UP * 13.4)
	roof_mesh = _surface("ClosedArenaRoof", roof, _material("121820"), true)
	upper_walls = _surface("UpperAcousticWalls", walls, _material("17212b"))
	_surface("ArenaPerimeterWalls", lower, _material("1c2a35"), true)
	var timber := _material("615b4e")
	var steel := _material("536273")
	for x in [-42.0, -28.0, -14.0, 0.0, 14.0, 28.0, 42.0]:
		var front := -3.0 + sqrt(52.0 * 52.0 - x * x)
		var top := 28.3 - absf(x) * 0.047
		_beam("RoofStructuralRib", Vector3(x, 25.3, -33.8), Vector3(x, top, 4.0), 0.38, steel)
		_beam("RoofStructuralRib", Vector3(x, top, 4.0), Vector3(x, 25.3, front - 0.2), 0.38, steel)
	for side in [-1.0, 1.0]:
		for z in [-26.0, -14.0, -2.0, 10.0, 22.0]:
			_box("UpperWallTimberFin", Vector3(side * 51.65, 19.0, z), Vector3(0.24, 10.5, 0.35), timber)
	_box("FoyerCanopy", Vector3(0, 7.0, 53.0), Vector3(72.0, 0.4, 12.2), _material("788b89"))
	for side in [-1.0, 1.0]:
		_box("FoyerRoofColumn", Vector3(side * 34.8, 3.7, 53.0), Vector3(0.45, 6.6, 0.45), steel)
	var ribbon := _material("142a36", "6386a2", 0.35)
	for side in [-1.0, 1.0]:
		_beam("InteriorEaveRibbon", Vector3(side * 51.35, 14.6, -31.8), Vector3(side * 51.35, 14.6, -2.0), 0.16, ribbon)
	# A restrained suspended rig reads as a sports venue, with an uncluttered
	# sightline from the public tunnel to the trophy and competition screen.
	for z in [-17.0, -6.0]:
		_beam("OverheadLightingTruss", Vector3(-24, 23.5, z), Vector3(24, 23.5, z), 0.35, steel)
		for x in [-21.0, -7.0, 7.0, 21.0]:
			_beam("TrussSuspension", Vector3(x, 23.5, z), Vector3(x, 27.5, z), 0.055, timber)
	print("ARENA_ENCLOSURE segments=", shell_segments, " eave=25.6m crown=29m")

func _build_lighting() -> void:
	for z in [47.0, 38.0, 29.0, 20.0]:
		var light := OmniLight3D.new()
		light.name = "PassageWarmLight"
		light.position = Vector3(0, 3.5, z)
		light.light_color = Color("ffe4bd")
		light.light_energy = 0.95
		light.omni_range = 9.0
		add_child(light)
		passage_lights.append(light)
	for at in [Vector3(-24, 17, 8), Vector3(24, 17, 8), Vector3(0, 20, 30), Vector3(0, 5.2, 54)]:
		var light := OmniLight3D.new()
		light.name = "ArenaSoftHouseLight"
		light.position = at
		light.light_color = Color("a5bbd1") if at.z < 50 else Color("ffe4bc")
		light.light_energy = 0.43 if at.z < 50 else 1.3
		light.omni_range = 30.0 if at.z < 50 else 17.0
		add_child(light)
		bowl_lights.append(light)
	for x in [-18.0, -6.0, 6.0, 18.0]:
		var light := SpotLight3D.new()
		light.name = "StageFocusSpot"
		light.position = Vector3(x, 22.8, -6.0)
		add_child(light)
		light.look_at(Vector3(x * 0.55, 1.8, -17.0), Vector3.UP)
		light.light_color = Color("e2ecff") if x < 0 else Color("fff0d0")
		light.light_energy = 7.8
		light.spot_range = 38.0
		light.spot_angle = 26.0
		light.spot_attenuation = 0.7
		light.shadow_enabled = absf(x) < 10.0
		stage_lights.append(light)
	var trophy := SpotLight3D.new()
	trophy.name = "TrophyFocusSpot"
	trophy.position = Vector3(0, 18, 9)
	add_child(trophy)
	trophy.look_at(Vector3(0, 1, 0), Vector3.UP)
	trophy.light_color = Color("ffe7b6")
	trophy.light_energy = 6.1
	trophy.spot_angle = 20.0
	trophy.spot_range = 28.0
	stage_lights.append(trophy)
	# Front keys arrive from above camera eye level so seated competitors'
	# faces remain readable under the roof, with no blinding floor flood.
	for x in [-12.0, 12.0]:
		var key := SpotLight3D.new()
		key.name = "CompetitorFaceKey"
		key.position = Vector3(x, 6.5, -4.5)
		key.light_color = Color("ffe9ce")
		key.light_energy = 3.8
		key.spot_range = 25.0
		key.spot_angle = 39.0
		key.spot_attenuation = 0.5
		add_child(key)
		key.look_at(Vector3(x * 0.45, 2.7, -16.0), Vector3.UP)
		face_lights.append(key)
	# Blue/gold accent heads have broad soft cones and one slow sweep during
	# the doorway cue. They never oscillate/flash in everyday free walking.
	for x in [-19.0, -10.0, 10.0, 19.0]:
		var accent := SpotLight3D.new()
		accent.name = "EntranceAccentHead"
		accent.position = Vector3(x, 17.0, -20.0)
		accent.light_color = Color("70a8dd") if x < 0.0 else Color("e8c483")
		accent.light_energy = 1.2
		accent.spot_range = 39.0
		accent.spot_angle = 15.0
		accent.spot_attenuation = 0.5
		add_child(accent)
		accent.look_at(Vector3(x * 0.35, 0.9, -4.0), Vector3.UP)
		entrance_accents.append(accent)
	# Low guide strips and small public aisle pools are steady at all times.
	var guide := _material("456579", "89b9d2", 0.55)
	for side in [-1.0, 1.0]:
		_beam("RunwayEdgeGuide", Vector3(side * 1.66, 0.60, -7.4), Vector3(side * 1.66, 0.60, 0.8), 0.045, guide)
		for z in [12.0, 3.0, -6.0]:
			var aisle := OmniLight3D.new()
			aisle.name = "SteadyAislePool"
			aisle.position = Vector3(side * 15.0, 2.7, z)
			aisle.light_color = Color("a4b9d1")
			aisle.light_energy = 0.45
			aisle.omni_range = 7.0
			add_child(aisle)

func _build_stage_media() -> void:
	var shader := Shader.new()
	shader.code = """shader_type spatial;
render_mode unshaded, cull_disabled;
uniform float arrival = 0.0;
uniform float pulse = 0.0;
uniform float progress = 0.0;
void fragment() {
	vec2 uv = UV;
	float center = 1.0 - smoothstep(0.05, 0.68, abs(uv.x - 0.5));
	float border = 1.0 - smoothstep(0.008, 0.025, min(min(uv.x, 1.0-uv.x), min(uv.y, 1.0-uv.y)));
	float arc = exp(-abs(length((uv - vec2(0.5, 0.53)) * vec2(1.0, 1.7)) - (0.26 + progress * 0.08)) * 72.0);
	float band = exp(-abs(uv.y - 0.80) * 90.0);
	vec3 navy = vec3(0.013, 0.029, 0.059);
	vec3 blue = vec3(0.085, 0.20, 0.34) * center * (0.35 + arrival * 0.46);
	vec3 gold = vec3(0.76, 0.49, 0.19) * (border * 0.28 + arc * (0.07 + arrival * 0.16) + band * pulse * 0.20);
	ALBEDO = navy + blue + gold;
	EMISSION = ALBEDO * 0.65;
}
"""
	screen_material = ShaderMaterial.new()
	screen_material.shader = shader
	for spec in [[Vector3(0, 9.4, -23.612), Vector2(23.65, 10.0)],
		[Vector3(-20, 7.5, -20.718), Vector2(5.5, 8.6)],
		[Vector3(20, 7.5, -20.718), Vector2(5.5, 8.6)]]:
		var screen := MeshInstance3D.new()
		screen.name = "EntranceShowScreen"
		var panel := QuadMesh.new()
		panel.size = spec[1]
		screen.mesh = panel
		screen.position = spec[0]
		screen.material_override = screen_material
		add_child(screen)
		screen_count += 1
	var title := Label3D.new()
	title.name = "MajorScreenTitle"
	title.text = "职业赛" if competitive else "MAJOR"
	title.position = Vector3(0, 10.1, -23.57)
	title.font_size = 144
	title.pixel_size = 0.025
	title.modulate = Color("f0dfb6")
	title.outline_size = 0
	add_child(title)
	var subtitle := Label3D.new()
	stage_subtitle = subtitle
	subtitle.text = "入场"
	subtitle.position = Vector3(0, 6.65, -23.57)
	subtitle.font_size = 88
	subtitle.pixel_size = 0.016
	subtitle.modulate = Color("b8c7da")
	subtitle.outline_size = 0
	add_child(subtitle)

func beat_state(at_time: float) -> Dictionary:
	var cue_beat := 60.0 / entrance_bpm
	var phrase_seconds := cue_beat * 32.0
	var beats := maxf(at_time, 0.0) / cue_beat + 0.00001
	var beat_index := int(floor(beats))
	var phase := fposmod(beats, 1.0)
	# 180 ms cosine attack/release, a modest 15% accent. This is a soft bump
	# on a stable base, not an on/off strobe; no loops follow the final chord.
	var bump := (1.0 + cos(PI * minf(1.0, phase / 0.36))) * 0.5
	var phrase := smoothstep(0.0, cue_beat * 4.0, at_time) * (1.0 - smoothstep(phrase_seconds + 0.8, phrase_seconds + 3.0, at_time))
	return {"beat": beat_index, "phase": phase, "pulse": bump * phrase,
		"phrase": phrase, "progress": clampf(at_time / phrase_seconds, 0.0, 1.0)}

func _update_stage(delta: float) -> void:
	var entrance: AudioStreamPlayer = audio_layers.get("entrance")
	if entrance_triggered and not paused and entrance.playing:
		entrance_elapsed = entrance.get_playback_position()
	var cue := beat_state(entrance_elapsed) if entrance_triggered and entrance.playing else {"phrase": 0.0, "pulse": 0.0, "progress": 1.0}
	entrance_envelope = lerpf(entrance_envelope, float(cue["phrase"]), 1.0 - exp(-3.5 * delta))
	beat_envelope = lerpf(beat_envelope, float(cue["pulse"]), 1.0 - exp(-16.0 * delta))
	for light in stage_lights:
		light.light_energy = (8.2 if showtime else 7.4) * (1.0 + beat_envelope * 0.10)
	for light in face_lights:
		light.light_energy = 4.0
	for light in bowl_lights:
		light.light_energy = 1.3 if light.position.z > 50.0 else (0.30 if showtime else 0.43)
	for i in range(entrance_accents.size()):
		var light := entrance_accents[i]
		light.light_energy = 1.2 + entrance_envelope * (2.0 + beat_envelope * 0.45)
		var side := signf(light.position.x)
		var target_x := lerpf(side * 3.0, side * 15.0, float(cue["progress"]))
		light.look_at(Vector3(target_x, 0.9, -4.0), Vector3.UP)
	if screen_material:
		screen_material.set_shader_parameter("arrival", entrance_envelope)
		screen_material.set_shader_parameter("pulse", beat_envelope)
		screen_material.set_shader_parameter("progress", cue["progress"])

func _pcm_stream(kind: String, seconds: float, looped: bool) -> AudioStreamWAV:
	var frames := int(seconds * SAMPLE_RATE)
	var bytes := PackedByteArray()
	bytes.resize(frames * 2)
	var random := RandomNumberGenerator.new()
	random.seed = 290941 + kind.hash()
	var filtered := 0.0
	var slow := 0.0
	var notes := [62, 65, 69, 70, 69, 65, 69, 72, 77, 76, 74, 72]
	for i in range(frames):
		var t := float(i) / SAMPLE_RATE
		var noise := random.randf_range(-1.0, 1.0)
		filtered = lerpf(filtered, noise, 0.18)
		slow = lerpf(slow, noise, 0.026)
		var sample := 0.0
		match kind:
			"passage":
				sample = slow * 0.13 + sin(TAU_F * 70.0 * t) * 0.008
			"crowd":
				var swell := 0.56 + 0.18 * sin(TAU_F * t / seconds) + 0.12 * sin(TAU_F * 3.0 * t / seconds)
				sample = (filtered * 0.2 + slow * 0.32) * swell
				# Subtle random applause accents rather than identifiable speech.
				var clap := fmod(t, 0.71)
				if clap < 0.028:
					sample += noise * 0.09 * exp(-clap * 105.0)
			"entrance":
				# Portable emergency cue follows the same original orchestral
				# harmony/grid; normal builds use the authored GM stereo render.
				var beat := ENTRANCE_BEAT
				var step := int(t / beat)
				var phase := fmod(t, beat)
				var bar := int(step / 4) % 4
				var roots := [50, 46, 41, 48]
				var root: int = roots[bar]
				var root_hz := 440.0 * pow(2.0, (root - 69.0) / 12.0)
				var ostinato := [0, 7, 3 if bar < 2 else 4, 7]
				var string_note: int = root + 12 + int(ostinato[int(t / (beat * 0.5)) % 4])
				var string_hz := 440.0 * pow(2.0, (string_note - 69.0) / 12.0)
				var string_phase := fmod(t, beat * 0.5)
				var strings := (sin(TAU_F * string_hz * t) + 0.25 * sin(TAU_F * string_hz * 2.0 * t)) * minf(1.0, string_phase / 0.035) * exp(-string_phase * 5.0)
				var horn_hz := 440.0 * pow(2.0, (float(notes[int(step / 2) % notes.size()]) - 69.0) / 12.0)
				var horn := (sin(TAU_F * horn_hz * t) + 0.4 * sin(TAU_F * horn_hz * 2.0 * t) + 0.12 * sin(TAU_F * horn_hz * 3.0 * t)) * (0.65 + 0.35 * sin(PI * phase / beat))
				var bass := sin(TAU_F * root_hz * 0.5 * t) * 0.15
				var drum := sin(TAU_F * (46.0 * phase + 0.7 * (1.0 - exp(-phase * 25.0)))) * exp(-phase * 13.0) * 0.3 if step % 2 == 0 else filtered * exp(-phase * 28.0) * 0.22
				var fade := minf(1.0, t / 0.08) * minf(1.0, (seconds - t) / 1.7)
				sample = (strings * 0.09 + horn * 0.105 + bass + drum) * fade
			"cheer":
				var attack := minf(1.0, t / 0.65)
				var decay := minf(1.0, (seconds - t) / 2.0)
				var voices := sin(TAU_F * 178.0 * t + 1.8 * sin(7.0 * t)) + 0.6 * sin(TAU_F * 231.0 * t + sin(5.5 * t))
				sample = (filtered * 0.20 + slow * 0.18 + voices * 0.025) * attack * decay
		bytes.encode_s16(i * 2, int(clampf(sample, -0.85, 0.85) * 32767.0))
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = SAMPLE_RATE
	stream.stereo = false
	stream.data = bytes
	if looped:
		stream.loop_mode = AudioStreamWAV.LOOP_FORWARD
		stream.loop_begin = 0
		stream.loop_end = frames
	synthesised_frames += frames
	return stream

func _build_audio() -> void:
	for spec in [["passage", 6.0, true], ["crowd", 8.0, true], ["entrance", 20.44, false], ["cheer", 6.0, false]]:
		var layer := AudioStreamPlayer.new()
		var key: String = spec[0]
		layer.name = "OriginalArena_" + key
		if key == "entrance" and competitive:
			layer.stream = CompetitiveCue.stream()
			audio_source = "original 136 BPM competitive sting: percussion, driven bass, riser and impacts; no external recordings"
		elif key == "entrance" and FileAccess.file_exists("res://assets/audio/arena_entrance.ogg"):
			layer.stream = AudioStreamOggVorbis.load_from_file("res://assets/audio/arena_entrance.ogg")
			audio_source = "original 112 BPM GM orchestral arrangement: drums, timpani, strings, horns, trombones"
		if layer.stream == null:
			layer.stream = _pcm_stream(key, float(spec[1]), bool(spec[2]))
			if key == "entrance":
				audio_source = "original layered synthesis fallback; render compose_arena_entrance.py for orchestral instruments"
		layer.volume_db = -80.0
		add_child(layer)
		audio_layers[key] = layer
		layer_gains[key] = 0.0
		if bool(spec[2]):
			layer.play()
	print("ARENA_AUDIO source=", audio_source, " layers=", audio_layers.size(), " local_soundscape_frames=", synthesised_frames)

func set_master_volume(value: float) -> void:
	master_volume = clampf(value, 0.0, 1.0)
	_apply_audio_levels()

func set_muted(value: bool) -> void:
	muted = value
	_apply_audio_levels()

func set_showtime(value: bool) -> void:
	showtime = value

func start_entrance() -> void:
	if entrance_triggered or paused: return
	entrance_triggered = true; entrance_count += 1
	(audio_layers["entrance"] as AudioStreamPlayer).play()

func portal_impact() -> void:
	if portal_landed: return
	portal_landed = true
	start_entrance()
	var layer: AudioStreamPlayer = audio_layers["entrance"]
	if competitive and layer.get_playback_position() < CompetitiveCue.BEAT * 8.0:
		layer.play(CompetitiveCue.BEAT * 8.0)
	(audio_layers["cheer"] as AudioStreamPlayer).play()

func settle_competition() -> void:
	# Do not keep a walk-in track looping behind the seated match controls.
	var layer: AudioStreamPlayer = audio_layers["entrance"]
	if stage_subtitle: stage_subtitle.text="赛前准备"
	var tween := create_tween(); tween.tween_property(self,"entrance_duck",0.0,.8)
	tween.finished.connect(func(): layer.stop())

func set_paused(value: bool) -> void:
	paused = value
	for key in ["entrance", "cheer"]:
		if audio_layers.has(key):
			(audio_layers[key] as AudioStreamPlayer).stream_paused = value
	_apply_audio_levels()

func _apply_audio_levels() -> void:
	var gain := 0.0 if muted else master_volume * (0.38 if paused else 1.0)
	for key in audio_layers:
		var level := gain * float(layer_gains.get(key, 0.0))
		var layer: AudioStreamPlayer = audio_layers[key]
		layer.volume_db = linear_to_db(level) if level > 0.0001 else -80.0

func update_visitor(at: Vector3, delta: float, allow_entrance: bool = true) -> void:
	var inside_target := 1.0 - smoothstep(16.0, 23.0, at.z)
	interior_mix = lerpf(interior_mix, inside_target, 1.0 - exp(-3.0 * delta))
	var in_passage := at.z < 50.7 and at.z > 18.0 and absf(at.x) < 3.1
	var target := 0.0 if in_passage else (1.0 if at.z < 18.0 else 0.55)
	exposure_mix = lerpf(exposure_mix, target, 1.0 - exp(-3.2 * delta))
	venue_environment.background_color = Color("08121d")
	venue_environment.ambient_light_color = Color("8b9fba")
	venue_environment.ambient_light_energy = lerpf(0.065, 0.19 if not showtime else 0.15, exposure_mix)
	venue_sun.light_energy = 0.025
	layer_gains["passage"] = lerpf(0.60, 0.055, interior_mix)
	layer_gains["crowd"] = lerpf(0.055, 0.48, interior_mix)
	layer_gains["entrance"] = 0.90 * entrance_duck
	layer_gains["cheer"] = lerpf(0.03, 0.54, interior_mix)
	if allow_entrance and not paused and at.z < 18.0 and not entrance_triggered:
		start_entrance(); portal_impact()
	_update_stage(delta)
	_apply_audio_levels()

func diagnostic_snapshot() -> Dictionary:
	var volumes: Dictionary = {}
	for key in audio_layers:
		var layer: AudioStreamPlayer = audio_layers[key]
		volumes[key] = {"playing": layer.playing, "volume_db": layer.volume_db, "gain": layer_gains.get(key, 0.0)}
	var entrance: AudioStreamPlayer = audio_layers["entrance"]
	return {"closed_roof": is_instance_valid(roof_mesh), "upper_walls": is_instance_valid(upper_walls),
		"shell_segments": shell_segments, "roof_eave_m": 25.6, "roof_crown_m": 29.0,
		"interior_mix": interior_mix, "exposure_mix": exposure_mix,
		"ambient_energy": venue_environment.ambient_light_energy, "showtime": showtime,
		"master_volume": master_volume, "muted": muted, "paused": paused,
		"entrance_count": entrance_count, "audio_source": audio_source,
		"audio_layers": volumes, "synthesised_frames": synthesised_frames,
		"stage_spots": stage_lights.size(), "face_keys": face_lights.size(), "house_lights": bowl_lights.size(),
		"entrance_bpm": entrance_bpm, "competitive":competitive, "portal_landed":portal_landed, "entrance_elapsed": entrance_elapsed,
		"entrance_duration": entrance.stream.get_length(),
		"entrance_envelope": entrance_envelope, "beat_envelope": beat_envelope,
		"screens": screen_count, "screen_mode": "original entrance graphic", "strobe": false,
		"daily_lighting": "steady stage, dim bowl, continuous guide lights"}
