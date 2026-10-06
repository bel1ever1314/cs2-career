extends Node
## All career decisions belong to the Python service. This object holds a read
## projection and a demonstration clock, never a second Career or save writer.
signal changed
signal status_changed
signal busy_changed(value: bool)
signal command_finished(path: String, result: Dictionary)
signal wake_requested
signal growth_changed
const Feedback = preload("res://scripts/career_feedback.gd")
const SleepTransition = preload("res://scripts/sleep_transition.gd")
const Fmt = preload("res://scripts/ui_format.gd")
var feedback: CanvasLayer
var sleep_transition: CanvasLayer
var sleeping := false
var feedback_active := false
## Shared, unsaved allocation draft. The Python career remains the sole writer.
var growth_draft: Dictionary = {}
var context: Dictionary = {}
var connected := false
var busy := false
var phone_open := false
var connecting := true
var message := "正在载入独立生涯……"
var clock_minutes := 480.0
var clock_held := false
var sound_volume := .7
var sound_muted := false
var pending_target := ""
var request: HTTPRequest
var endpoint := ""
var token := ""
var process_id := -1
var owns_service := false
var ready_file := ""
var runtime_dir := ""
var settings: Dictionary = {}
var startup_time := 0.0
var startup_started := 0
var startup_poll := 0.0
var refresh_time := 0.0
var clock_boundary := false
var active_path := ""
var active_body: Dictionary = {}
var active_post := false
var queued_command: Dictionary = {}
var calendar_running := false
var closing := false
var exiting := false
var closing_startup := false

static func project_root() -> String:
	# Loose projects use their own folder; exported games use the EXE folder.
	if OS.has_feature("standalone") or OS.has_feature("template"):
		return OS.get_executable_path().get_base_dir().simplify_path()
	return ProjectSettings.globalize_path("res://").simplify_path()

static func local_path(value: String, root: String = "") -> String:
	if value.begins_with("user://"):
		return ProjectSettings.globalize_path(value)
	if value.is_absolute_path() and not value.begins_with("res://"):
		return value.simplify_path()
	var base := project_root() if root.is_empty() else root
	return base.path_join(value.trim_prefix("res://")).simplify_path()

static func service_launch(config: Dictionary, handshake: String, owner_pid: int, root: String = "") -> Dictionary:
	# This only builds arguments. Tests can inspect a relocated package without
	# spawning a service, importing Python modules or touching a saved career.
	var common := PackedStringArray([
		"--data-dir", local_path(str(config.get("data_dir", "runtime/career")), root),
		"--port", "127.0.0.1:0", "--ready-file", local_path(handshake, root),
		"--parent-pid", str(owner_pid), "--media-config", local_path("data/media.json", root)])
	var backend := str(config.get("backend_exe", "")).strip_edges()
	if not backend.is_empty():
		return {"executable":local_path(backend, root), "args":common}
	var python := str(config.get("python", "")).strip_edges()
	var repo := str(config.get("repo_root", "")).strip_edges()
	if python.is_empty() or repo.is_empty():
		return {"error":"请检查 data/career_link.json 中的后台程序，或 Python 和源码路径。"}
	var args := PackedStringArray(["-B", local_path(repo, root).path_join("tools/career3d_service.py")])
	args.append_array(common)
	# A bare command such as python/python.exe belongs to PATH; interpreter
	# file paths still resolve relative to the moved project like other files.
	var interpreter := local_path(python, root) if python.is_absolute_path() or python.contains("/") or python.contains("\\") else python
	return {"executable":interpreter, "args":args}

func _ready() -> void:
	# Importing resources and checking scripts must not create a playable save.
	if Engine.is_editor_hint() or "--check-only" in OS.get_cmdline_args():
		connecting = false
		set_process(false)
		return
	feedback = Feedback.new()
	feedback.name = "CareerFeedback"
	add_child(feedback)
	sleep_transition = SleepTransition.new()
	add_child(sleep_transition)
	get_tree().auto_accept_quit = false
	request = HTTPRequest.new(); request.timeout = 90; request.use_threads = true
	add_child(request); request.request_completed.connect(_response)
	for flag in ["--no-service", "--test", "--npc-test", "--arena-test", "--travel-test", "--arena-capture", "--npc-capture"]:
		if flag in OS.get_cmdline_user_args():
			connecting=false; message="独立场景检查"; set_process(false); return
	settings = JSON.parse_string(FileAccess.get_file_as_string("res://data/career_link.json"))
	clock_minutes=float(settings.get("start_hour",8))*60
	startup_started=Time.get_ticks_msec()
	runtime_dir = local_path("runtime")
	DirAccess.make_dir_recursive_absolute(runtime_dir)
	ready_file = runtime_dir.path_join("service-%d.json" % OS.get_process_id())
	var external_service := false
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--service-ready="):
			ready_file=arg.trim_prefix("--service-ready=")
			external_service=true
		if arg.begins_with("--demo-data="):
			settings["data_dir"]=arg.trim_prefix("--demo-data=")
	if not external_service:
		var launch := service_launch(settings, ready_file, OS.get_process_id())
		if launch.has("error"):
			_fail(str(launch["error"]))
		else:
			process_id=OS.create_process(str(launch["executable"]),launch["args"],false); owns_service=process_id>0
			if not owns_service:_fail("生涯后台未能启动，请检查 data/career_link.json 中的后台程序路径。")
	set_process(true)

func _process(delta: float) -> void:
	if closing_startup:return
	if connecting:
		startup_time+=delta; startup_poll-=delta
		if startup_poll<=0:
			startup_poll=.25
			if FileAccess.file_exists(ready_file):
				var row = JSON.parse_string(FileAccess.get_file_as_string(ready_file))
				if row is Dictionary and row.get("ready",false) and row.get("host")=="127.0.0.1":
					endpoint="http://127.0.0.1:%d" % int(row["port"]); token=str(row["token"])
					connecting=false; refresh(); return
		if Time.get_ticks_msec()-startup_started>35000:_fail("后台没有就绪。可能另一个样板窗口仍开着，请关闭它后重新打开。")
		return
	if not connected or closing or exiting:return
	refresh_time+=delta
	if refresh_time>20 and not busy and not sleeping:refresh_time=0; refresh()
	var scene=get_tree().current_scene
	var at_club: bool=scene!=null and scene.scene_file_path in ["res://play.tscn","res://bedroom.tscn"]
	var real_match_pending := _has_pending_match()
	if at_club and not bool(context.get("start", {}).get("creation_required", false)) and not real_match_pending and not phone_open and not clock_held and not busy and not Travel.busy and context.get("stories",[]).is_empty():
		clock_minutes+=delta/maxf(.2,float(settings.get("real_seconds_per_game_minute",1.0)))
		if clock_minutes>=1440 and not clock_boundary:
			clock_minutes=1439; clock_boundary=true
			calendar(add_days(str(context.get("date","")),1),false)

func _has_pending_match() -> bool:
	if context.get("rts", {}).get("pending", false): return true
	if bool(context.get("training_pending", false)) or context.get("match_preflight", {}).get("session_pending", false):
		return true
	for page in ["ladder", "custom"]:
		var lobby = context.get(page, {}).get("lobby")
		if lobby is Dictionary and lobby.get("phase", "") in ["starting", "launched", "rts"]:
			return true
	return false

func _fail(text: String) -> void:
	connecting=false; connected=false; message=text; status_changed.emit()

func refresh() -> void:
	if endpoint.is_empty() or busy:return
	_send("/api/3d/context",{},false)

func _send(path: String,body: Dictionary,post: bool=true) -> bool:
	if busy or endpoint.is_empty():return false
	active_path=path; active_body=body.duplicate(true); active_post=post; busy=true; busy_changed.emit(true)
	# The first explicit install downloads official runtime components.
	request.timeout = 600 if path == "/api/3d/setup/install" else 90
	var headers:=PackedStringArray(["X-Career-Token: "+token,"Content-Type: application/json"])
	var error:=request.request(endpoint+path,headers,HTTPClient.METHOD_POST if post else HTTPClient.METHOD_GET,JSON.stringify(body) if post else "")
	if error!=OK:
		busy=false; busy_changed.emit(false); _fail("本地请求没有发出："+str(error)); return false
	return true

func command(path: String,body: Dictionary={}) -> bool:
	if sleeping:
		message = "正在睡觉，醒来后再操作。"
		status_changed.emit()
		return false
	if not connected or closing:
		message = "操作未发出：本地后台尚未连接。"
		status_changed.emit()
		return false
	if busy:
		# A read-only background poll must not eat a player's click. Keep one
		# explicit command, without retrying writes or changing its revision.
		if not active_post and queued_command.is_empty():
			queued_command = {"path":path, "body":body.duplicate(true)}
			message = "操作已收到，当前同步结束后执行……"
			status_changed.emit()
			return true
		message = "上一项操作正在处理，请稍等。"
		status_changed.emit()
		return false
	return _send(path,body)

func _flush_queued() -> void:
	if busy or queued_command.is_empty(): return
	var queued := queued_command.duplicate(true)
	queued_command.clear()
	if not command(str(queued.path), queued.body):
		command_finished.emit(str(queued.path), {"ok":false, "msg":message, "not_sent":true})

func _response(result: int,code: int,_headers: PackedStringArray,body: PackedByteArray) -> void:
	var path:=active_path; var sent:=active_body.duplicate(true)
	busy=false; busy_changed.emit(false)
	var parsed := JSON.new()
	var out: Variant = null
	if result == HTTPRequest.RESULT_SUCCESS and parsed.parse(body.get_string_from_utf8()) == OK:
		out = parsed.data
		# Display projections: integral JSON numbers become ints ("#1", not "#1.0").
		# Tactics/RTS payloads keep their exact parsed form for round-trips.
		if out is Dictionary and not (path.contains("/tactics") or path.contains("/rts")):
			out = Fmt.normalize(out)
	if result!=HTTPRequest.RESULT_SUCCESS or not out is Dictionary:
		var discarded := queued_command.duplicate(true)
		queued_command.clear()
		connected=false; clock_held=true; calendar_running=false
		message="后台连接中断，当前场景仍可查看。请重新打开样板以恢复已保存生涯。"
		if sleeping: sleep_transition.complete({"ok":false, "msg":message})
		status_changed.emit()
		# The active write may already have been saved. Never retry it here;
		# just release local pending forms and ask for a fresh saved-state read.
		command_finished.emit(path, {"ok":false, "msg":message, "transport_failure":true, "outcome_unknown":active_post})
		if not discarded.is_empty():
			command_finished.emit(str(discarded.path), {"ok":false, "msg":"操作未执行：后台同步中断。请重新打开样板后再试。", "not_sent":true})
		if closing:_exit_now()
		return
	var loaded: bool = path == "/api/3d/saves/load" and out.get("ok", false) and out.get("loaded", false)
	Locale.register_projection(out)
	if loaded: _reset_for_loaded_career()
	# Even a rejected command can carry a valid, newly queued career story.
	if out.has("context"): _apply_context(out["context"])
	elif path=="/api/3d/context" and out.get("ok",false): _apply_context(out)
	if loaded and is_instance_valid(feedback): feedback.ingest()
	message=str(out.get("reason",out.get("msg","")))
	if code>=400:message=str(out.get("msg",message))
	status_changed.emit(); command_finished.emit(path,out)
	if loaded: call_deferred("_return_from_loaded_career")
	if not queued_command.is_empty(): call_deferred("_flush_queued")
	if path=="/api/3d/shutdown":
		_exit_now()
		return
	if closing:
		call_deferred("quit")
		return
	if path=="/api/3d/calendar":
		_finish_calendar(out, sent)
	if closing:call_deferred("quit")

func _finish_calendar(out: Dictionary, sent: Dictionary) -> void:
	var status := str(out.get("status", "error"))
	if status == "progress" and calendar_running and out.get("ok", false):
		call_deferred("_calendar_step")
		return
	calendar_running = false
	# A match gate stops simulation, not waking up on the actual match day.
	# Earlier stories still pause normally and never claim the target was reached.
	var match_morning := bool(out.get("ok", false)) and status == "paused" and str(out.get("reason_code", "")) == "player_match" and bool(context.get("nextmatch", {}).get("due", false)) and str(out.get("actualdate", "")) == str(context.get("date", ""))
	if (status == "reached" or match_morning) and sent.get("display_hour", 8) == 8:
		clock_minutes = 480
		clock_held = false
		clock_boundary = false
		if sent.get("wake", false): wake_requested.emit()
	elif status == "paused":
		clock_held = true
	if sleeping:
		var presentation := out.duplicate(true)
		presentation["wake_at_match"] = match_morning and bool(sent.get("wake", false))
		sleep_transition.complete(presentation)

func _reset_for_loaded_career() -> void:
	queued_command.clear()
	calendar_running = false
	pending_target = ""
	clock_boundary = false
	clock_minutes = 480
	clock_held = false
	growth_draft.clear()
	if is_instance_valid(feedback): feedback.reset_for_loaded_career()
	Phone.close_phone()
	Computer.close_computer()
	Phone.reset_career_views()
	Computer.reset_career_views()
	Computer.career_start = Computer.CareerStart.new()
	Computer.career_start.attach(Computer)
	Travel.match_visit.clear()
	Travel.awards_visit.clear()
	Travel.club_session.clear()
	growth_changed.emit()

func _return_from_loaded_career() -> void:
	if not closing and get_tree().current_scene != null: Travel.go("bedroom", false)

func _apply_context(value: Dictionary) -> void:
	Fmt.normalize(value)
	var old_date: String=str(context.get("date",""))
	var old_personal: Dictionary = context.get("personal", {})
	var new_personal: Dictionary = value.get("personal", {})
	var growth_changed_on_server: bool = not old_personal.is_empty() and (
		old_personal.get("attributes", {}) != new_personal.get("attributes", {})
		or old_personal.get("attr_points", 0) != new_personal.get("attr_points", 0)
		or context.get("player", {}).get("id", "") != value.get("player", {}).get("id", "")
		or old_personal.get("growth_allowed", false) != new_personal.get("growth_allowed", false))
	var differs: bool=JSON.stringify(context)!=JSON.stringify(value)
	context=value; connected=true
	if growth_changed_on_server:
		growth_draft.clear()
		growth_changed.emit()
	if old_date!=str(context.get("date","")):
		clock_minutes=float(context.get("clock",{}).get("hour",8))*60; clock_boundary=false; clock_held=false
	if differs:changed.emit()

func growth_remaining() -> int:
	var spent := 0
	for amount in growth_draft.values():
		spent += int(amount)
	return maxi(0, int(context.get("personal", {}).get("attr_points", context.get("attr_points", 0))) - spent)

func present_map_result(key: String, won: bool) -> void:
	if is_instance_valid(feedback): feedback.map_result(key, won)

func growth_adjust(axis: String, amount: int) -> bool:
	var personal: Dictionary = context.get("personal", {})
	var attributes: Dictionary = personal.get("attributes", {})
	if (busy and active_post) or not connected or not personal.get("growth_allowed", false) or not attributes.has(axis) or amount not in [-1, 1]:
		return false
	if typeof(attributes[axis]) not in [TYPE_INT, TYPE_FLOAT]:
		return false
	var current := int(growth_draft.get(axis, 0))
	if amount == 1 and (growth_remaining() < 1 or float(attributes[axis]) + current >= 100):
		return false
	if amount == -1 and current < 1:
		return false
	if current + amount == 0:
		growth_draft.erase(axis)
	else:
		growth_draft[axis] = current + amount
	growth_changed.emit()
	return true

func growth_clear() -> void:
	if growth_draft.is_empty():
		return
	growth_draft.clear()
	growth_changed.emit()

func growth_commit() -> bool:
	if growth_draft.is_empty() or not context.get("personal", {}).get("growth_allowed", false):
		return false
	return command("/api/3d/attr", {"allocations":growth_draft.duplicate(), "revision":int(context.get("calendar", {}).get("revision", 0))})

func calendar(target: String,wake: bool=true) -> bool:
	if wake and is_instance_valid(sleep_transition): return sleep_transition.begin(target)
	return _begin_calendar(target, wake)

func _begin_calendar(target: String,wake: bool=true) -> bool:
	if busy or not connected:return false
	pending_target=target; calendar_running=true; set_meta("calendar_wake",wake)
	return _calendar_step()

func _calendar_step() -> bool:
	if closing:
		_calendar_not_sent()
		return false
	var body: Dictionary={"target_date":pending_target,"revision":int(context.get("calendar",{}).get("revision",0)),"request_id":"godot-%d-%d" % [OS.get_process_id(),Time.get_ticks_usec()],"display_hour":8,"wake":bool(get_meta("calendar_wake",false))}
	var accepted := _send("/api/3d/calendar",body)
	if not accepted: _calendar_not_sent()
	return accepted

func _calendar_not_sent() -> void:
	calendar_running = false
	clock_held = true
	if sleeping: sleep_transition.complete({"ok":false, "msg":"日历请求没有发出，时间已暂停。"})

func add_days(day: String,count: int) -> String:
	if day.is_empty():return ""
	return Time.get_date_string_from_unix_time(int(Time.get_unix_time_from_datetime_string(day+"T00:00:00"))+count*86400)

func clock_text() -> String:
	return "%s  %02d:%02d" % [str(context.get("date","载入中")),floori(clock_minutes/60),int(clock_minutes)%60]

func quit() -> void:
	if exiting:return
	closing=true; calendar_running=false; clock_held=true
	message="正在保存并关闭生涯……"; status_changed.emit()
	if busy:return
	if owns_service and not endpoint.is_empty():
		_send("/api/3d/shutdown",{})
		return
	if owns_service and endpoint.is_empty() and not closing_startup:
		closing_startup=true
		_close_startup()
		return
	_exit_now()

func _close_startup() -> void:
	var deadline: int=Time.get_ticks_msec()+5000
	while OS.is_process_running(process_id) and Time.get_ticks_msec()<deadline:
		if FileAccess.file_exists(ready_file):
			var row = JSON.parse_string(FileAccess.get_file_as_string(ready_file))
			if row is Dictionary and row.get("ready",false) and row.get("host")=="127.0.0.1":
				endpoint="http://127.0.0.1:%d" % int(row["port"]); token=str(row["token"])
				_send("/api/3d/shutdown",{})
				return
		await get_tree().create_timer(.1).timeout
	# The child has a read-only parent handle; exiting the owner gracefully
	# shuts it down even if initialization hasn't yet published a handshake.
	get_tree().quit()

func _exit_now() -> void:
	if exiting:return
	exiting=true
	# Shutdown acknowledges the request before the server's final save/cleanup.
	# Give this owned child time to finish rather than leaving it locked behind.
	if owns_service and process_id>0:
		var deadline: int=Time.get_ticks_msec()+12000
		while OS.is_process_running(process_id) and Time.get_ticks_msec()<deadline:
			await get_tree().create_timer(.1).timeout
	get_tree().quit()

func _notification(what: int) -> void:
	if what==NOTIFICATION_WM_CLOSE_REQUEST:quit()
