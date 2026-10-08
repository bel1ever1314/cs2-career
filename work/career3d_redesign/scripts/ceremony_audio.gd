extends RefCounted
## Ceremony sounds: snare/timpani roll that builds, the reveal hit, a brass
## fanfare, applause and a soft tick. The orchestral recordings in
## assets/audio (rendered by tools/audio/ceremony.py) are used when present;
## the synthesized versions below stay as a fallback when a file is missing.
## Volume follows the game's sound setting.
const RATE := 22050
const Assets = preload("res://scripts/audio_assets.gd")
const FILES := {"drumroll":"ceremony_roll.ogg", "drumroll_long":"ceremony_roll_long.ogg", "hit":"ceremony_hit.ogg",
	"fanfare":"ceremony_fanfare.ogg", "applause":"ceremony_applause.ogg", "tick":"ceremony_tick.ogg",
	"honours":"ceremony_honours.ogg", "champion":"ceremony_champion.ogg"}
const STOP_FADE := 0.12
static var _cache: Dictionary = {}

## The sound actually played: the rendered file, else the synthesized fallback.
static func sound(kind: String) -> AudioStream:
	if FILES.has(kind):
		var file := Assets.stream(str(FILES[kind]))
		if file != null: return file
	return stream(kind)

## Synthesized fallback when a rendered file is missing.
static func stream(kind: String) -> AudioStreamWAV:
	if _cache.has(kind): return _cache[kind]
	var samples: PackedFloat32Array
	match kind:
		"drumroll": samples = _drumroll(2.6)
		"drumroll_long": samples = _drumroll(3.6)
		"hit": samples = _hit()
		"fanfare": samples = _fanfare()
		"applause": samples = _applause(3.2)
		"tick": samples = _tick()
		_: samples = _tick()
	var bytes := PackedByteArray()
	bytes.resize(samples.size() * 2)
	for i in range(samples.size()):
		bytes.encode_s16(i * 2, int(clampf(samples[i], -1.0, 1.0) * 32767.0))
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = RATE
	wav.data = bytes
	_cache[kind] = wav
	return wav

## Plays a ceremony sound on a reusable player owned by `owner`.
static func play(owner: Node, kind: String, gain_db: float = 0.0) -> void:
	if CareerBridge.sound_muted or CareerBridge.sound_volume <= 0.0: return
	var player := owner.get_node_or_null("CeremonyAudio_" + kind) as AudioStreamPlayer
	if player == null:
		player = AudioStreamPlayer.new(); player.name = "CeremonyAudio_" + kind
		owner.add_child(player)
	if player.has_meta("fade"):
		var old: Tween = player.get_meta("fade")
		if old and old.is_valid(): old.kill()
		player.remove_meta("fade")
	player.stream = sound(kind)
	player.volume_db = linear_to_db(clampf(CareerBridge.sound_volume, 0.001, 1.0)) - 4.0 + gain_db
	player.play()

## Stops with a short fade so a cut roll does not click.
static func stop(owner: Node, kind: String) -> void:
	var player := owner.get_node_or_null("CeremonyAudio_" + kind) as AudioStreamPlayer
	if player == null or not player.playing: return
	if not player.is_inside_tree():
		player.stop(); return
	var fade := player.create_tween()
	fade.tween_property(player, "volume_db", -60.0, STOP_FADE)
	fade.tween_callback(player.stop)
	player.set_meta("fade", fade)

static func _noise(rng: RandomNumberGenerator) -> float:
	return rng.randf() * 2.0 - 1.0

static func _drumroll(seconds: float) -> PackedFloat32Array:
	var out := PackedFloat32Array(); out.resize(int(RATE * seconds))
	var rng := RandomNumberGenerator.new(); rng.seed = 7
	var low := 0.0
	for i in range(out.size()):
		var t := float(i) / RATE
		var progress := t / seconds
		# Strokes speed up from 14 to 30 per second and swell in volume.
		var rate := lerpf(14.0, 30.0, progress)
		var stroke := fmod(t * rate, 1.0)
		var env := exp(-stroke * 9.0)
		var n := _noise(rng)
		low = lerpf(low, n, 0.25)
		var snare := (n - low) * 0.8 + sin(TAU * 190.0 * t) * 0.25 * exp(-stroke * 18.0)
		var swell := lerpf(0.25, 0.85, progress * progress)
		out[i] = snare * env * swell * 0.55
	return out

static func _hit() -> PackedFloat32Array:
	var seconds := 2.2
	var out := PackedFloat32Array(); out.resize(int(RATE * seconds))
	var rng := RandomNumberGenerator.new(); rng.seed = 11
	var hp := 0.0
	for i in range(out.size()):
		var t := float(i) / RATE
		var n := _noise(rng)
		hp = lerpf(hp, n, 0.08)
		var crash := (n - hp) * exp(-t * 2.2) * 0.45
		var boom := sin(TAU * (58.0 + 40.0 * exp(-t * 12.0)) * t) * exp(-t * 5.0) * 0.7
		out[i] = crash + boom
	return out

static func _fanfare() -> PackedFloat32Array:
	var seconds := 2.6
	var out := PackedFloat32Array(); out.resize(int(RATE * seconds))
	# Short-short-long brass figure, then a held major chord.
	var steps := [[0.0, 0.16, [523.25, 659.25]], [0.18, 0.16, [523.25, 659.25]], [0.36, 0.5, [587.33, 739.99]], [0.9, 1.7, [523.25, 659.25, 783.99, 1046.5]]]
	for i in range(out.size()):
		var t := float(i) / RATE
		var value := 0.0
		for step in steps:
			var start: float = step[0]; var length: float = step[1]
			if t < start or t > start + length + 0.25: continue
			var local := t - start
			var env := minf(1.0, local * 40.0) * (1.0 if local < length else exp(-(local - length) * 14.0))
			for hz in step[2]:
				var f: float = hz
				var vib := 1.0 + 0.004 * sin(TAU * 5.5 * t)
				# Saw-ish brass: a few harmonics with falling weights.
				for h in range(1, 6):
					value += sin(TAU * f * h * vib * t) * (0.16 / h) * env
		out[i] = value * 0.34
	return out

static func _applause(seconds: float) -> PackedFloat32Array:
	var out := PackedFloat32Array(); out.resize(int(RATE * seconds))
	var rng := RandomNumberGenerator.new(); rng.seed = 23
	var claps: Array = []
	for c in range(int(seconds * 55)):
		claps.append([rng.randf() * seconds, rng.randf_range(0.4, 1.0)])
	var band := 0.0
	for i in range(out.size()):
		var t := float(i) / RATE
		var n := _noise(rng)
		band = lerpf(band, n, 0.35)
		var bed := (n - band) * 0.05
		out[i] = bed * minf(1.0, t * 3.0) * minf(1.0, (seconds - t) * 1.5)
	for clap in claps:
		var at := int(float(clap[0]) * RATE)
		for k in range(min(500, out.size() - at)):
			out[at + k] += _noise(rng) * exp(-float(k) / 60.0) * 0.22 * float(clap[1])
	return out

static func _tick() -> PackedFloat32Array:
	var out := PackedFloat32Array(); out.resize(int(RATE * 0.12))
	for i in range(out.size()):
		var t := float(i) / RATE
		out[i] = sin(TAU * 1320.0 * t) * exp(-t * 60.0) * 0.4
	return out
