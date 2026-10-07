extends Node
## Everyday background music (autoload "Music").
##
## Picks a track from the current scene and the in-game clock, crossfades on
## changes, ducks under phones/computers/presentations, and rests between
## plays so loops do not wear thin. Venues own their own sound, so the music
## fades out there. Also owns persistence of the player's sound settings.
const Audio = preload("res://scripts/audio_assets.gd")
const SETTINGS_PATH := "user://audio_settings.cfg"
const TRACKS := {
	"club_day": "music_club_day.ogg",
	"club_night": "music_club_night.ogg",
	"home_night": "music_home_night.ogg",
}
const ZONES := {"res://play.tscn": "club", "res://bedroom.tscn": "home"}
const DAY_START := 360.0    # 06:00
const NIGHT_START := 1140.0 # 19:00
const FADE_SECONDS := 2.0
const PLAYS_BEFORE_REST := 2
const REST_RANGE := Vector2(20.0, 40.0)
const BASE_TRIM := 0.62     # music sits under footsteps, UI and voices

var music_volume := 0.7
var settings_path := SETTINGS_PATH  # tests point this at a scratch file
var decks: Array[AudioStreamPlayer] = []
var deck_track: Array[String] = ["", ""]
var deck_gain: Array[float] = [0.0, 0.0]
var deck_target: Array[float] = [0.0, 0.0]
var active := 0
var track := ""
var plays := 0
var last_position := 0.0
var resting := 0.0
var duck := 1.0
var evaluate_in := 0.0
var rng := RandomNumberGenerator.new()

func _ready() -> void:
	rng.randomize()
	load_settings()
	for i in range(2):
		var deck := AudioStreamPlayer.new(); deck.name = "Deck%d" % i; deck.volume_db = -80.0
		add_child(deck); decks.append(deck)

func load_settings() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(settings_path) != OK: return
	CareerBridge.sound_volume = clampf(float(cfg.get_value("audio", "sound_volume", CareerBridge.sound_volume)), 0.0, 1.0)
	CareerBridge.sound_muted = bool(cfg.get_value("audio", "sound_muted", CareerBridge.sound_muted))
	music_volume = clampf(float(cfg.get_value("audio", "music_volume", music_volume)), 0.0, 1.0)

func save_settings() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("audio", "sound_volume", CareerBridge.sound_volume)
	cfg.set_value("audio", "sound_muted", CareerBridge.sound_muted)
	cfg.set_value("audio", "music_volume", music_volume)
	cfg.save(settings_path)

func set_music_volume(value: float) -> void:
	music_volume = clampf(value, 0.0, 1.0)

func stop_scene_music() -> void:
	# Quiet destinations must not inherit the previous room's crossfade tail.
	# This is scene-local playback state, not a change to saved sound settings.
	track = ""; resting = 0.0; plays = 0; last_position = 0.0
	for i in range(decks.size()):
		decks[i].stop(); decks[i].volume_db = -80.0
		deck_track[i] = ""; deck_gain[i] = 0.0; deck_target[i] = 0.0

static func is_night(minutes: float) -> bool:
	return minutes < DAY_START or minutes >= NIGHT_START

## Track for a scene at a time of day; "" where the scene owns its own sound
## (venues) or no track is chosen yet (home in daytime).
static func track_for(scene_path: String, minutes: float) -> String:
	var zone: String = ZONES.get(scene_path, "")
	if zone.is_empty(): return ""
	var id := zone + ("_night" if is_night(minutes) else "_day")
	return id if TRACKS.has(id) else ""

func desired_track() -> String:
	var scene := get_tree().current_scene
	return "" if scene == null else track_for(scene.scene_file_path, CareerBridge.clock_minutes)

func _duck_target() -> float:
	if CareerBridge.feedback_active: return 0.25
	if CareerBridge.sleeping: return 0.3
	if CareerBridge.phone_open: return 0.5
	return 1.0

func _start(id: String) -> void:
	var stream := Audio.stream(TRACKS[id], true)
	if stream == null: return
	deck_target[active] = 0.0
	active = 1 - active
	var deck := decks[active]
	deck.stream = stream
	deck.play(0.0)
	deck_track[active] = id
	deck_gain[active] = 0.0; deck_target[active] = 1.0
	plays = 0; last_position = 0.0

func _process(delta: float) -> void:
	evaluate_in -= delta
	if evaluate_in <= 0.0:
		evaluate_in = 0.5
		var wanted := desired_track()
		if wanted != track and not Travel.busy:
			track = wanted; resting = 0.0
			if track.is_empty():
				deck_target[0] = 0.0; deck_target[1] = 0.0
			else:
				_start(track)
	var deck := decks[active]
	if not track.is_empty():
		if resting > 0.0:
			resting -= delta
			if resting <= 0.0: _start(track)
		elif deck_track[active] == track and deck.playing:
			var position := deck.get_playback_position()
			if position + 1.0 < last_position:
				plays += 1
				if plays >= PLAYS_BEFORE_REST:
					deck_target[active] = 0.0
					resting = rng.randf_range(REST_RANGE.x, REST_RANGE.y)
			last_position = position
	duck = lerpf(duck, _duck_target(), 1.0 - exp(-3.0 * delta))
	var level := Audio.master() * music_volume * BASE_TRIM * duck
	for i in range(2):
		deck_gain[i] = move_toward(deck_gain[i], deck_target[i], delta / FADE_SECONDS)
		decks[i].volume_db = Audio.db(level * deck_gain[i])
		if deck_gain[i] <= 0.0 and deck_target[i] <= 0.0 and decks[i].playing:
			decks[i].stop(); deck_track[i] = ""

func diagnostic() -> Dictionary:
	return {"track": track, "active": active, "deck_tracks": deck_track.duplicate(), "gains": deck_gain.duplicate(),
		"plays": plays, "resting": resting, "duck": duck, "music_volume": music_volume,
		"playing": decks[active].playing if decks.size() > active else false}
