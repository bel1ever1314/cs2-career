extends Node
## Everyday music selection, venue ambience assets, settings persistence and the
## Major opener's synchronized stems / hold-and-drop timing. Runs headless
## (dummy audio driver still advances playback).
const Audio = preload("res://scripts/audio_assets.gd")
const Director = preload("res://scripts/music_director.gd")
const Atmosphere = preload("res://scripts/arena_atmosphere.gd")
var failures: Array[String] = []
var checks := 0

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("AUDIO_CHECK ", "PASS " if value else "FAIL ", label)

func _ready() -> void:
	call_deferred("run")

func frames(count: int) -> void:
	for i in range(count): await get_tree().process_frame

func seconds(value: float) -> void:
	await get_tree().create_timer(value).timeout

func run() -> void:
	# Track choice: club day/night, home night; home day stays quiet; venues none.
	check(Director.track_for("res://play.tscn", 600.0) == "club_day", "club daytime plays the afternoon track")
	check(Director.track_for("res://play.tscn", 1200.0) == "club_night", "club evening plays the night track")
	check(Director.track_for("res://play.tscn", 200.0) == "club_night", "after midnight counts as night")
	check(Director.track_for("res://bedroom.tscn", 1300.0) == "home_night", "home at night plays the window track")
	check(Director.track_for("res://bedroom.tscn", 600.0) == "", "home daytime has no track yet")
	for venue in ["res://major_walk.tscn", "res://lan.tscn", "res://awards.tscn"]:
		check(Director.track_for(venue, 600.0) == "", "venue owns its sound: " + venue)
	for id in Director.TRACKS:
		var stream := Audio.stream(Director.TRACKS[id], true) as AudioStreamOggVorbis
		check(stream != null and stream.loop and stream.get_length() > 50.0, "music file loads as a loop: " + id)
	for file in ["crowd_arena_murmur.ogg", "crowd_arena_active.ogg", "crowd_lan_room.ogg", "crowd_awards_hall.ogg"]:
		var bed := Audio.stream(file, true) as AudioStreamOggVorbis
		check(bed != null and bed.loop and bed.get_length() >= 29.0, "ambience bed loads as a loop: " + file)

	# Ducking and settings persistence (scratch file, never the player's).
	var music: Node = get_node("/root/Music")
	CareerBridge.phone_open = true
	check(is_equal_approx(music._duck_target(), 0.5), "phone/computer ducks music")
	CareerBridge.feedback_active = true
	check(is_equal_approx(music._duck_target(), 0.25), "presentations duck music further")
	CareerBridge.phone_open = false; CareerBridge.feedback_active = false
	var saved := [music.settings_path, music.music_volume, CareerBridge.sound_volume, CareerBridge.sound_muted]
	music.settings_path = "user://audio_settings_test.cfg"
	music.music_volume = 0.35; CareerBridge.sound_volume = 0.55; CareerBridge.sound_muted = true
	music.save_settings()
	music.music_volume = 1.0; CareerBridge.sound_volume = 1.0; CareerBridge.sound_muted = false
	music.load_settings()
	check(is_equal_approx(music.music_volume, 0.35) and is_equal_approx(CareerBridge.sound_volume, 0.55) and CareerBridge.sound_muted, "music, sound and mute persist")
	DirAccess.remove_absolute(ProjectSettings.globalize_path("user://audio_settings_test.cfg"))
	music.settings_path = saved[0]; music.music_volume = saved[1]; CareerBridge.sound_volume = saved[2]; CareerBridge.sound_muted = saved[3]
	music._start("club_day")
	await frames(10)
	var decks: Array = music.decks
	check(decks[music.active].playing and music.deck_track[music.active] == "club_day" and music.deck_target[music.active] == 1.0, "a started track fades in on its own deck")
	music._start("club_night")
	await frames(5)
	check(music.deck_target[1 - music.active] == 0.0 and music.deck_target[music.active] == 1.0, "switching crossfades the previous deck out")

	# Opener cue file agrees with the beat grid.
	var cue := Audio.cue("major_final")
	var beat := float(cue.get("beat_seconds", 0.0))
	check(not cue.is_empty() and beat > 0.0, "final opener cue loads")
	check(float(cue["hold_start"]) < float(cue["hold_end"]) and float(cue["hold_end"]) < float(cue["gate"]) and float(cue["gate"]) < float(cue["drop"]) and float(cue["drop"]) < float(cue["final"]) and float(cue["final"]) < float(cue["length"]), "cue timings are ordered")
	for key in ["hold_start", "hold_end", "gate", "drop", "final"]:
		var beats := float(cue[key]) / beat
		check(absf(beats - roundf(beats)) < 0.001, "cue point on the beat grid: " + key)

	# Ordinary doorway visits must use the new track too, without a match roster.
	var visit_sun := DirectionalLight3D.new(); add_child(visit_sun)
	var visit: Node3D = Atmosphere.new(); add_child(visit)
	visit.setup(Environment.new(), visit_sun)
	var visit_track: AudioStreamPlayer = visit.audio_layers["entrance"]
	check(not visit.competitive and visit.uses_cue() and visit.entrance_bpm == 128.0, "free visit selects the final opener without a match roster")
	check(visit_track.stream is AudioStreamSynchronized and visit_track.stream.get_length() > 40.0, "free visit loads the full new music and crowd stems")
	visit.update_visitor(Vector3(0, .5, 56.8), .016)
	check(visit.entrance_count == 0, "lobby waits until entering the tunnel")
	visit.set_paused(true)
	visit.update_visitor(Vector3(0, .5, 45), .016)
	check(visit.entrance_count == 0, "paused visit does not start music")
	visit.set_paused(false)
	visit.update_visitor(Vector3(0, .5, 45), .016, false)
	check(visit.entrance_count == 0, "scene transition does not start free-visit music")
	visit.update_visitor(Vector3(0, .5, 45), .016)
	await frames(3)
	check(visit.entrance_count == 1 and visit_track.playing and not visit.portal_landed, "walking into the tunnel starts the new build once")
	visit.update_visitor(Vector3(0, .5, 16), .016)
	await frames(3)
	check(visit.portal_landed and visit_track.get_playback_position() >= float(cue["gate"]) - .05, "free visit lands the new drop at the bowl entrance")
	for z in [35, 56.8, 45, 16]: visit.update_visitor(Vector3(0, .5, z), .016)
	check(visit.entrance_count == 1, "walking back and forth does not restart the music")
	visit.settle_competition()
	await seconds(.9)
	check(not visit_track.playing, "seating stops the entrance music")
	visit.queue_free(); visit_sun.queue_free(); await frames(2)

	# Missing assets must never revive a retired entrance track.
	var cached_crowd: Variant = Audio._cache.get("major_final_crowd.ogg")
	var cached_music: Variant = Audio._cache.get("major_final_music.ogg")
	Audio._cache["major_final_crowd.ogg"] = null
	for music_missing in [false, true]:
		if music_missing: Audio._cache["major_final_music.ogg"] = null
		var sun := DirectionalLight3D.new(); add_child(sun)
		var arena: Node3D = Atmosphere.new(); add_child(arena)
		arena.setup(Environment.new(), sun)
		var entrance: AudioStreamPlayer = arena.audio_layers["entrance"]
		if music_missing:
			arena.update_visitor(Vector3(0, .5, 16), .016)
			check(entrance.stream == null and arena.entrance_count == 0 and arena.diagnostic_snapshot()["entrance_duration"] == 0.0, "missing new music keeps ambience only, never the retired music")
		else:
			check(entrance.stream == cached_music and arena.uses_cue(), "missing crowd keeps the same new music and light timing")
		arena.queue_free(); sun.queue_free(); await frames(2)
	Audio._cache["major_final_crowd.ogg"] = cached_crowd
	Audio._cache["major_final_music.ogg"] = cached_music

	# Atmosphere: synchronized stems, capacity scaling, hold loop and portal drop.
	for capacity in [10000, 1000]:
		var env := Environment.new(); var sun := DirectionalLight3D.new(); add_child(sun)
		var arena: Node3D = Atmosphere.new(); add_child(arena)
		arena.setup(env, sun, {"competitive": true, "capacity": capacity})
		var entrance: AudioStreamPlayer = arena.audio_layers["entrance"]
		var synced := entrance.stream as AudioStreamSynchronized
		check(arena.uses_cue() and synced != null and synced.stream_count == 2, "opener music and crowd are synchronized stems (%d seats)" % capacity)
		check(absf(synced.get_sync_stream_volume(1) - Audio.db(arena.crowd_stem_gain)) < 0.01, "crowd stem level follows capacity (%d seats)" % capacity)
		check(arena.audio_layers.has("crowd_active") and not arena.audio_layers.has("cheer"), "arena uses rendered crowd beds, not the synthesized cheer")
		if capacity == 10000:
			check(arena.synthesised_frames < 100000, "arena no longer synthesizes its crowd at load")
			arena.start_entrance()
			await frames(3)
			entrance.seek(float(cue["hold_end"]) - 0.01)
			await seconds(0.12)
			arena.update_visitor(Vector3(0, .5, 45), 0.016)
			check(arena.hold_loops >= 1 and entrance.get_playback_position() < float(cue["hold_end"]), "far from the tunnel mouth the build bar repeats")
			entrance.seek(float(cue["hold_end"]) - 0.01)
			var loops: int = arena.hold_loops
			await seconds(0.12)
			arena.update_visitor(Vector3(0, .5, 20), 0.016)
			check(arena.hold_loops == loops, "near the tunnel mouth the build runs on into the drop")
			entrance.seek(5.0)
			await frames(3)
			arena.portal_impact()
			await frames(3)
			var at: float = entrance.get_playback_position()
			check(at >= float(cue["gate"]) - 0.05 and at < float(cue["drop"]) + 0.3, "crossing the portal jumps to the silent beat before the drop")
			var flash: Dictionary = arena.beat_state(float(cue["drop"]) + 0.01)
			var gate: Dictionary = arena.beat_state((float(cue["gate"]) + float(cue["drop"])) * 0.5)
			check(float(flash["pulse"]) > 0.9 and float(gate["pulse"]) == 0.0, "lights hold on the silent beat and hit on the drop")
		else:
			check(arena.crowd_stem_gain < 1.0 and arena.ambience_gain < 1.0, "a thousand-seat event sounds smaller than the full bowl")
		arena.queue_free(); sun.queue_free()
		await frames(2)
	for competitive in [false, true]:
		var sun := DirectionalLight3D.new(); add_child(sun)
		var arena: Node3D = Atmosphere.new(); add_child(arena)
		arena.setup(Environment.new(), sun, {"competitive":competitive,"capacity":100})
		arena.start_entrance(); arena.update_visitor(Vector3(0,.5,16), .016)
		check(not arena.entrance_enabled and not arena.uses_cue() and arena.audio_layers["entrance"].stream == null and arena.entrance_count == 0, "small arena has no entrance music (competitive=%s)" % competitive)
		check(arena.audio_layers["crowd"].playing and not arena.audio_layers.has("cheer"), "small arena keeps only its scaled ambience")
		arena.queue_free(); sun.queue_free(); await frames(2)

	print("AUDIO_RESULT checks=", checks, " failures=", failures.size())
	for item in failures: print("AUDIO_FAILURE ", item)
	get_tree().quit(0 if failures.is_empty() else 1)
