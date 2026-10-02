extends SceneTree
## Natural full match from an isolated backend's frozen career session.
const Catalog = preload("res://scripts/map_catalog.gd")
const Sim = preload("res://scripts/match_sim.gd")

func _initialize() -> void:
	call_deferred("run")

func serializable(value):
	if value is Vector2: return [value.x, value.y]
	if value is Dictionary:
		var result: Dictionary = {}
		for key in value: result[key] = serializable(value[key])
		return result
	if value is Array:
		var result: Array = []
		for item in value: result.append(serializable(item))
		return result
	return value

func run() -> void:
	var session_file := ""
	var report_file := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--session-file="): session_file = arg.trim_prefix("--session-file=")
		if arg.begins_with("--report-file="): report_file = arg.trim_prefix("--report-file=")
	if not (report_file.begins_with("D:/") or report_file.begins_with("E:/")):
		push_error("Exporter requires an explicit isolated D:/ or E:/ output")
		quit(1)
		return
	var session = JSON.parse_string(FileAccess.get_file_as_string(session_file))
	if not session is Dictionary:
		push_error("Missing frozen career session")
		quit(1)
		return
	var sim = Sim.new()
	if not sim.configure(Catalog.load_map(str(session.map)), session.rosters, int(session.seed), {}, true):
		push_error("Frozen career map/rosters failed to configure")
		quit(1)
		return
	var started := Time.get_ticks_msec()
	for tick in range(40000):
		sim.step(0.25)
		sim.pop_events()
		if sim._phase == "finished": break
	var report: Dictionary = sim.report()
	if report.get("finished") != true or report.get("winner") not in ["ct", "t"]:
		push_error("Natural career RTS map did not finish decisively")
		quit(1)
		return
	var file := FileAccess.open(report_file, FileAccess.WRITE)
	if file == null:
		push_error("Cannot write isolated natural-match report")
		quit(1)
		return
	file.store_string(JSON.stringify(serializable(report)))
	file.close()
	print("CAREER_RTS_ACTUAL_REPORT ", JSON.stringify({"map":report.map, "score":report.score, "rounds":report.round_history.size(), "elapsed_ms":Time.get_ticks_msec() - started, "report_file":report_file}))
	quit(0)
