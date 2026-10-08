extends Node
## Awards ceremony cues: orchestral files replace the synthesized placeholders,
## the synthesized versions remain as fallback, and cut rolls fade instead of clicking.
const Ceremony = preload("res://scripts/ceremony_audio.gd")
var failures: Array[String] = []
var checks := 0

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("CEREMONY_AUDIO ", "PASS " if value else "FAIL ", label)

func _ready() -> void:
	call_deferred("run")

func run() -> void:
	var minimum := {"drumroll":2.5, "drumroll_long":3.6, "hit":1.8, "fanfare":5.0, "applause":3.5, "tick":0.3, "honours":2.5, "champion":3.5}
	for kind in minimum:
		var stream := Ceremony.sound(kind)
		check(stream is AudioStreamOggVorbis, kind + " uses the rendered orchestral file")
		check(stream != null and stream.get_length() >= float(minimum[kind]), kind + " is long enough for its ceremony step")
		check(stream is AudioStreamOggVorbis and not (stream as AudioStreamOggVorbis).loop, kind + " plays once")
	check(Ceremony.sound("unknown") is AudioStreamWAV, "unknown kinds fall back to the synthesized click")
	check(Ceremony.stream("fanfare") is AudioStreamWAV, "synthesized fallback still available")
	# The Top20 / title popup opens with the rendered honours or champion sting.
	var Feedback = load("res://scripts/career_feedback.gd")
	var feed = Feedback.new()
	add_child(feed)
	CareerBridge.sound_muted = false
	CareerBridge.sound_volume = 0.8
	for kind in ["honours", "champion"]:
		feed.play_sound(kind)
		check(feed.audio_cache.get(kind) is AudioStreamOggVorbis, kind + " popup sting uses the orchestral file")
	feed.play_sound("win")
	check(feed.audio_cache.get("win") is AudioStreamWAV, "map result stings stay short and synthesized")
	feed.queue_free()
	CareerBridge.sound_volume = 0.8
	Ceremony.play(self, "drumroll", -6.0)
	var player := get_node_or_null("CeremonyAudio_drumroll") as AudioStreamPlayer
	check(player != null and player.playing and player.stream is AudioStreamOggVorbis, "roll plays the file")
	Ceremony.stop(self, "drumroll")
	check(player.playing, "stopping fades rather than cutting instantly")
	await get_tree().create_timer(Ceremony.STOP_FADE + 0.15).timeout
	check(not player.playing, "roll is silent after the fade")
	Ceremony.play(self, "drumroll", -6.0)
	check(player.playing and player.volume_db > -20.0, "replaying after a fade restores the level")
	Ceremony.stop(self, "drumroll")
	print("CEREMONY_AUDIO_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
