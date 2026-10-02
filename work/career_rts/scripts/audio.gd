extends Node
## Small, self-contained synthesized cues. Never consumes the match RNG.
## Gunfire is deliberately quiet and bounded so ten bots do not become noise.

const SAMPLE_RATE := 22050
const VOICE_LIMIT := 8
const SHOT_INTERVAL_MS := 32

var muted: bool = false:
	set(value):
		muted = value
		if muted:
			for voice in _voices:
				voice.stop()

var _voices: Array[AudioStreamPlayer] = []
var _sounds: Dictionary = {}
var _last_shot_ms: int = -SHOT_INTERVAL_MS
var _next_voice: int = 0
var events_played: int = 0


func _ready() -> void:
	_build_sounds()
	for index in range(VOICE_LIMIT):
		var voice := AudioStreamPlayer.new()
		voice.name = "CueVoice%d" % index
		voice.volume_db = -21.0
		add_child(voice)
		_voices.append(voice)


func toggle() -> bool:
	muted = not muted
	return muted


func play_event(kind: String, event: Dictionary = {}) -> bool:
	if muted or _voices.is_empty():
		return false
	var sound_kind := kind
	if kind == "gunfire":
		sound_kind = "shot"
	elif kind == "reload_complete":
		sound_kind = "reload_finish"
	elif kind == "round_live":
		sound_kind = "round_start"
	if not _sounds.has(sound_kind):
		return false
	if sound_kind == "shot":
		var now := Time.get_ticks_msec()
		if now - _last_shot_ms < SHOT_INTERVAL_MS:
			return false
		_last_shot_ms = now
	var voice: AudioStreamPlayer = null
	for candidate in _voices:
		if not candidate.playing:
			voice = candidate
			break
	if voice == null:
		# Do not interrupt a round cue for dense automatic fire.
		if sound_kind == "shot":
			return false
		voice = _voices[_next_voice]
		_next_voice = (_next_voice + 1) % VOICE_LIMIT
		voice.stop()
	voice.stream = _sounds[sound_kind]
	voice.pitch_scale = 0.78 if sound_kind == "shot" and str(event.get("weapon", "")) == "awp" else 1.0
	voice.volume_db = -23.0 if sound_kind in ["shot", "reload", "reload_finish"] else -20.0
	voice.play()
	events_played += 1
	return true


func _build_sounds() -> void:
	var durations := {"shot": 0.12, "reload": 0.25, "reload_finish": 0.10,
		"round_start": 0.33, "round_end": 0.42, "bomb_planted": 0.42,
		"bomb_defused": 0.40, "bomb_exploded": 0.35}
	for kind: String in durations:
		_sounds[kind] = _synthesize(kind, float(durations[kind]))


func _synthesize(kind: String, duration: float) -> AudioStreamWAV:
	var count := int(ceil(duration * SAMPLE_RATE))
	var pcm := PackedByteArray()
	pcm.resize(count * 2)
	var rng := RandomNumberGenerator.new()
	rng.seed = 9173 + absi(kind.hash())
	var filtered_noise := 0.0
	for index in range(count):
		var time := float(index) / SAMPLE_RATE
		filtered_noise = lerpf(filtered_noise, rng.randf_range(-1.0, 1.0), 0.58)
		var sample := 0.0
		match kind:
			"shot":
				sample = filtered_noise * exp(-time * 57.0) * 0.85
				sample += sin(TAU * 150.0 * time) * exp(-time * 34.0) * 0.35
			"reload", "reload_finish":
				var click_time := time
				if kind == "reload" and time >= 0.145:
					click_time -= 0.145
				sample = (filtered_noise * 0.70 + sin(TAU * 720.0 * time) * 0.30) * exp(-click_time * 100.0)
			"round_start":
				sample = _tone(time, 0.01, 0.12, 520.0) + _tone(time, 0.16, 0.14, 780.0)
			"round_end":
				sample = _tone(time, 0.01, 0.17, 660.0) + _tone(time, 0.22, 0.17, 440.0)
			"bomb_planted":
				sample = _tone(time, 0.02, 0.075, 900.0) + _tone(time, 0.16, 0.075, 900.0) + _tone(time, 0.30, 0.075, 900.0)
			"bomb_defused":
				sample = _tone(time, 0.01, 0.14, 620.0) + _tone(time, 0.18, 0.18, 930.0)
			"bomb_exploded":
				sample = (filtered_noise * 0.70 + sin(TAU * 65.0 * time) * 0.30) * exp(-time * 12.0)
		# A tiny fade removes PCM boundary clicks without lengthening the cue.
		var fade := minf(1.0, time * 1200.0) * minf(1.0, (duration - time) * 250.0)
		pcm.encode_s16(index * 2, int(clampf(sample * fade, -1.0, 1.0) * 20000.0))
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = SAMPLE_RATE
	stream.stereo = false
	stream.data = pcm
	return stream


func _tone(time: float, start: float, duration: float, frequency: float) -> float:
	var local := time - start
	if local < 0.0 or local >= duration:
		return 0.0
	return sin(TAU * frequency * local) * sin(PI * local / duration) * 0.55
