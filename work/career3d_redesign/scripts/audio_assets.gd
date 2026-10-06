extends RefCounted
## Shared loading for the original music/ambience files in assets/audio.
## Files are plain Ogg Vorbis read at runtime (same as the arena entrance), so
## the packaged game does not depend on Godot's import cache. Missing files
## return null and callers keep their synthesized fallbacks.
const DIR := "res://assets/audio/"
static var _cache: Dictionary = {}
static var _cues: Dictionary = {}

static func stream(file: String, loop: bool = false) -> AudioStream:
	var key := file + ("#loop" if loop else "")
	if _cache.has(key): return _cache[key]
	var result: AudioStream = null
	var path := DIR + file
	if FileAccess.file_exists(path):
		var ogg := AudioStreamOggVorbis.load_from_file(path)
		if ogg != null:
			ogg.loop = loop
			result = ogg
	_cache[key] = result
	return result

static func cue(id: String) -> Dictionary:
	if _cues.has(id): return _cues[id]
	var path := DIR + id + "_cue.json"
	var data: Dictionary = {}
	if FileAccess.file_exists(path):
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
		if parsed is Dictionary and int(parsed.get("schema_version", 0)) == 1: data = parsed
	_cues[id] = data
	return data

## Music and crowd stems that must stay sample-aligned, each with its own level.
static func synchronized(files: Array) -> AudioStreamSynchronized:
	var streams: Array[AudioStream] = []
	for file in files:
		var item := stream(str(file))
		if item == null: return null
		streams.append(item)
	var result := AudioStreamSynchronized.new()
	result.stream_count = streams.size()
	for i in range(streams.size()):
		result.set_sync_stream(i, streams[i])
		result.set_sync_stream_volume(i, 0.0)
	return result

static func db(linear: float) -> float:
	return linear_to_db(linear) if linear > 0.0001 else -80.0

## Overall loudness after the player's sound settings (0 when muted). Looked up
## at runtime so standalone test scripts without autoloads still compile.
static func master() -> float:
	var tree := Engine.get_main_loop() as SceneTree
	var bridge: Node = tree.root.get_node_or_null("CareerBridge") if tree != null else null
	if bridge == null: return 0.7
	return 0.0 if bool(bridge.get("sound_muted")) else clampf(float(bridge.get("sound_volume")), 0.0, 1.0)

static func device_open() -> bool:
	var tree := Engine.get_main_loop() as SceneTree
	var bridge: Node = tree.root.get_node_or_null("CareerBridge") if tree != null else null
	return bridge != null and bool(bridge.get("phone_open"))
