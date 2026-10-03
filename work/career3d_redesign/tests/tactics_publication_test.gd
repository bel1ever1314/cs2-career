extends Node

var checks := 0
var failures: Array[String] = []
var requests: Array[Dictionary] = []
var clipboard := ""

func _ready() -> void:
	call_deferred("run")

func check(condition: bool, label: String) -> void:
	checks += 1
	if not condition: failures.append(label)
	print("TACTICS_PUBLICATION_CHECK ", "PASS " if condition else "FAIL ", label)

func tactic(ident: String) -> Dictionary:
	var value := {"id":ident, "name":"战术 " + ident, "side":"t", "slots":[]}
	for number in range(1, 6): value.slots.append({"slot":number, "steps":[]})
	return value

func publication(pending: bool, can_sync: bool, ids: Array, reason: String) -> Dictionary:
	return {"status":"pending" if pending else "synced", "pending":pending, "can_sync":can_sync,
		"synced":not pending, "prepared_map":"de_dust2", "published_ids":ids, "reason":reason}

func send_command(path: String, body: Dictionary) -> bool:
	requests.append({"path":path, "body":body.duplicate(true)})
	return true

func run() -> void:
	check("--no-service" in OS.get_cmdline_user_args(), "fixture explicitly forbids a backend service")
	if not failures.is_empty(): get_tree().quit(1); return
	CareerBridge.set_process(false)
	CareerBridge.connected = true
	CareerBridge.clock_held = true
	CareerBridge.context = {"date":"2026-10-03", "calendar":{"revision":7}, "player":{"id":"fixture", "name":"Fixture"}, "inbox":[], "calendar_events":[]}
	Locale.language = "zh-CN"
	TranslationServer.set_locale("zh_CN")
	var editor = Computer.tactics
	editor.command_sender = send_command
	editor.clipboard_writer = func(value: String) -> bool: clipboard = value; return true
	editor.clipboard_reader = func() -> String: return clipboard
	editor.libraries = {"de_dust2":{"ok":true, "map":"de_dust2", "schema_version":1, "tactics":[tactic("d_1")],
		"map_meta":{"pos_x":0, "pos_y":1000, "scale":1, "width":1000, "height":1000, "image_path":"res://tactics-radar.png"},
		"available_maps":[{"map":"de_dust2", "name":"Dust II"}],
		"publication":{"status":"no_session", "pending":true, "can_sync":false, "published_ids":[], "reason":"下次开局自动同步。"}}}
	Computer.present("club")
	Computer._navigate("tactics", false)
	for frame in range(4): await get_tree().process_frame
	check(editor.controls.TacticsSync.disabled, "no prepared current session disables publication")
	editor.set_draft(tactic("d_1"))
	editor.library().publication = publication(true, true, ["old"], "保存库与本场快照不同；请同步。")
	editor.refresh_library_controls()
	editor.refresh()
	check(not editor.controls.TacticsSync.disabled and "old" in editor.controls.publication.text, "pending publication shows existing IDs and enables sync")
	editor.controls.TacticsCopyCommand.pressed.emit()
	check(clipboard == "play d_1" and requests.is_empty(), "copy retains exact command without deploying anything")
	check("快照不同" in editor.notice, "copy feedback never promises a pending tactic is available in game")
	editor.draft.name = "保留未保存草稿"
	editor.changed()
	var draft_before: Dictionary = editor.draft.duplicate(true)
	editor.controls.TacticsSync.pressed.emit()
	check(requests.size() == 1 and requests[0].path == "/api/3d/tactics/sync", "sync submits the explicit publication endpoint")
	check(requests[0].body == {"revision":7, "map":"de_dust2"}, "sync submits no nonce, path, match reset or draft payload")
	check(editor.pending_action == "sync" and editor.controls.TacticsSync.disabled, "sync waits for its own response and blocks double submission")
	editor.finished("/api/3d/tactics/sync", {"ok":true, "replayed":true, "map":"de_dust2", "reason":"战术库已同步当前对局，不需重新准备比赛。",
		"publication":publication(false, true, ["d_1"], "战术库已同步当前对局，不需重新准备比赛。")})
	check(editor.draft == draft_before and editor.dirty, "publication response preserves the unsaved editor draft")
	check("d_1" in editor.controls.publication.text and editor.controls.TacticsSync.disabled, "verified published ID replaces stale list without implying execution")
	check(editor.pending_action.is_empty() and Computer.action_feedback.current_kind == "success", "verified sync owns its success feedback")
	editor.library().publication = publication(true, false, ["old"], "CS2 正在运行，本场快照未改动；退出后点击同步。")
	editor.refresh_library_controls(); editor.refresh()
	check(editor.controls.TacticsSync.disabled and not editor.controls.TacticsSave.disabled, "running game blocks publication but not independent library save")
	editor.controls.TacticsSave.pressed.emit()
	check(requests[-1].path == "/api/3d/tactics/save", "saving during a game retains the existing save contract")
	editor.finished("/api/3d/tactics/save", {"ok":true, "map":"de_dust2", "tactic":draft_before,
		"tactics":[draft_before], "library_message":"战术已保存到独立库。", "reason":"CS2 正在运行，本场快照未改动；退出后点击同步。",
		"publication":publication(true, false, ["old"], "CS2 正在运行，本场快照未改动；退出后点击同步。")})
	check(not editor.dirty and "已保存" in editor.notice and "退出后" in editor.notice, "save acknowledgement distinguishes saved data from deferred publication")
	var protected: Dictionary = editor.library().duplicate(true)
	editor.finished("/api/3d/tactics/sync", {"ok":true, "map":"de_dust2", "publication":publication(false, true, ["foreign"], "stale")})
	check(editor.library() == protected, "unsolicited stale sync response cannot overwrite publication state")
	editor.library().publication = publication(true, true, ["old"], "可同步。")
	editor.refresh_library_controls(); editor.refresh()
	editor.controls.TacticsSync.pressed.emit()
	editor.finished("/api/3d/tactics/sync", {"ok":true, "map":"de_dust2", "reason":"CS2 刚启动，未同步。",
		"publication":publication(true, false, ["old"], "CS2 刚启动，未同步。")})
	check(Computer.action_feedback.current_kind == "error" and "未同步" in editor.notice, "deferred or failed explicit sync never reports publication success")
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service and CareerBridge.runtime_dir.is_empty(), "test never opens live save or backend")
	print("TACTICS_PUBLICATION_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
