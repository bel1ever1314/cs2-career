extends SceneTree
## Seeded complete autonomous games; real raw round/player reconciliation.
const Catalog = preload("res://scripts/map_catalog.gd")
const Sim = preload("res://scripts/match_sim.gd")
var failures: Array[String] = []
var checks := 0
var results: Array[Dictionary] = []

func _initialize() -> void: call_deferred("_run")

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label); push_error(label)

func serializable(value):
	if value is Vector2: return [value.x, value.y]
	if value is Dictionary:
		var row: Dictionary = {}
		for key in value: row[key] = serializable(value[key])
		return row
	if value is Array:
		var row: Array = []
		for item in value: row.append(serializable(item))
		return row
	return value

func _run() -> void:
	var rosters: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/rosters.json"))
	rosters["human_id"] = ""
	var maps: Array[String] = Catalog.available_maps()
	var overtime := false
	var directory := "E:/CS2CareerTools/RTSMultiMapQA-" + str(Time.get_unix_time_from_system()).replace(".", "-")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--map="): maps = [arg.trim_prefix("--map=")]
		elif arg == "--overtime": overtime = true
		elif arg.begins_with("--output-dir="): directory = arg.trim_prefix("--output-dir=")
	if not directory.is_absolute_path() or directory.left(3).to_upper() not in ["D:/", "E:/"]:
		push_error("Use an explicit isolated D/E report directory."); quit(2); return
	for map_id in maps:
		if FileAccess.file_exists(directory.path_join(map_id + "-20261002.json")):
			push_error("Existing reports are preserved. Choose a new output directory."); quit(2); return
	for map_id in maps:
		var started := Time.get_ticks_msec()
		var sim = Sim.new()
		check(sim.configure(Catalog.load_map(map_id), rosters, 20261002, {}, overtime), map_id + " natural match setup")
		var counts: Dictionary = {}
		for tick in range(50000 if overtime else 20000):
			sim.step(.25)
			for event in sim.pop_events(): counts[event["type"]] = int(counts.get(event["type"], 0)) + 1
			if sim._phase == "finished": break
		check(sim._phase == "finished", map_id + " natural game completes")
		var report: Dictionary = sim.report()
		check(report["round_history"].size() == int(report["score"]["ct"] + report["score"]["t"]), map_id + " round count reconciles score")
		var totals: Dictionary = {}
		var scores := {"ct": 0, "t": 0}
		for round_data in report["round_history"]:
			scores[round_data["winner"]] += 1
			check(round_data["players"].size() == 10, map_id + " round has ten raw player records")
			for row in round_data["players"]:
				var id: String = row["id"]
				if not totals.has(id): totals[id] = {"k": 0, "d": 0, "a": 0, "damage": 0, "opening_kills": 0, "opening_deaths": 0, "kast_rounds": 0, "survived_rounds": 0}
				for key in ["k", "d", "a", "damage", "opening_kills", "opening_deaths"]: totals[id][key] += int(row[key])
				totals[id]["kast_rounds"] += 1 if row["kast"] else 0
				totals[id]["survived_rounds"] += 1 if row["survived"] else 0
		for row in report["players"]:
			for key in totals[row["id"]]: check(int(row[key]) == int(totals[row["id"]][key]), map_id + row["id"] + key + " final/raw round totals reconcile")
		check(scores == report["score"], map_id + " raw winners reconcile score")
		check(int(counts.get("shot", 0)) > 0 and int(counts.get("kill", 0)) > 0, map_id + " natural combat occurred")
		DirAccess.make_dir_recursive_absolute(directory)
		var file := FileAccess.open(directory + "/" + map_id + "-20261002.json", FileAccess.WRITE)
		if file != null: file.store_string(JSON.stringify(serializable(report)))
		if overtime: check(report["winner"] != "draw", map_id + " MR3 returns a decisive result")
		var result := {"map": map_id, "score": report["score"], "rounds": report["round_history"].size(), "events": counts, "elapsed_ms": Time.get_ticks_msec() - started}
		results.append(result)
		print("MULTIMAP_MATCH " + JSON.stringify(result))
	print("MULTIMAP_MATCH_RESULT " + JSON.stringify({"checks": checks, "failures": failures, "maps": results}))
	quit(0 if failures.is_empty() else 1)
