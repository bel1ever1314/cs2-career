extends RefCounted
## Versioned resource catalog. An unavailable map is never substituted by Dust2.
const CATALOG_PATH := "res://data/map_catalog.json"
const SCHEMA_VERSION := 2

static func catalog() -> Dictionary:
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(CATALOG_PATH))
	return parsed if parsed is Dictionary else {}

static func entry(map_id: String) -> Dictionary:
	return catalog().get("maps", {}).get(map_id, {}).duplicate(true)

static func available_maps() -> Array[String]:
	var result: Array[String] = []
	var rows: Dictionary = catalog().get("maps", {})
	for map_id in rows:
		if rows[map_id].get("status", "") == "playable":
			result.append(str(map_id))
	return result

static func load_map(map_id: String) -> Dictionary:
	var row := entry(map_id)
	if row.get("status", "") != "playable": return {}
	var path := str(row.get("data_file", ""))
	if path.is_empty() or not FileAccess.file_exists(path): return {}
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not parsed is Dictionary or parsed.get("map", "") != map_id: return {}
	var geometry: Dictionary = parsed.get("geometry", {})
	for key in ["grid_file", "collision_mask", "clearance_mask", "sight_mask"]:
		if not FileAccess.file_exists(str(geometry.get(key, ""))) and not ResourceLoader.exists(str(geometry.get(key, ""))): return {}
	var knowledge_file := str(row.get("knowledge_file", ""))
	if not knowledge_file.is_empty() and FileAccess.file_exists(knowledge_file):
		var knowledge = JSON.parse_string(FileAccess.get_file_as_string(knowledge_file))
		if knowledge is Dictionary: parsed["botlab_knowledge"] = knowledge
	parsed["catalog_schema_version"] = SCHEMA_VERSION
	return parsed
