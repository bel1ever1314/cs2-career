extends Node
## One looping ambience bed (crowd, room tone) that follows the player's sound
## settings and eases between levels. Phones, computers and the pause menu
## duck it instead of cutting it, so a venue never goes dead silent.
const Audio = preload("res://scripts/audio_assets.gd")
var player: AudioStreamPlayer
var level := 1.0          # requested level 0..1 (set by the venue)
var gain := 1.0           # fixed trim for this bed
var duck_when_device := 0.45
var paused := false
var current := 0.0

func setup(file: String, trim: float = 1.0, start_level: float = 1.0) -> bool:
	name = "Ambience_" + file.get_basename()
	gain = trim; level = start_level
	player = AudioStreamPlayer.new(); player.name = "Player"
	player.stream = Audio.stream(file, true)
	player.volume_db = -80.0
	add_child(player)
	if player.stream == null: return false
	# Start at a random point so two visits do not sound identical.
	player.play(randf() * maxf(0.0, player.stream.get_length() - 1.0))
	return true

func set_level(value: float) -> void:
	level = clampf(value, 0.0, 1.5)

func _process(delta: float) -> void:
	if player == null or player.stream == null: return
	var duck := duck_when_device if Audio.device_open() else 1.0
	if paused: duck = minf(duck, 0.4)
	var target := Audio.master() * gain * level * duck
	current = lerpf(current, target, 1.0 - exp(-2.5 * delta))
	player.volume_db = Audio.db(current)

func diagnostic() -> Dictionary:
	return {"file": name, "playing": player != null and player.playing, "level": level, "volume_db": player.volume_db if player else -80.0}
