extends Node
## Run with the test-only ladder_bridge_fixture autoload and --no-service.
const MAPS := ["dust2", "mirage", "inferno", "nuke", "ancient", "anubis", "train"]
var checks := 0
var failures: Array[String] = []
var transport
var capture := false

func _ready() -> void:
	call_deferred("run")

func before_computer() -> void: pass
func before_phone() -> void: pass
func set_device_open(_opened: bool, _kind: String) -> void: pass

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)
	print("CUSTOM_UI_CHECK ", "PASS " if ok else "FAIL ", label)

func settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame

func pid(index: int) -> String:
	return "custom-ui-%d" % index

func rows() -> Array:
	var out: Array = []
	for index in range(12):
		out.append({"player_id":pid(index), "name":"测试选手 %d" % index, "club":"独立测试队", "role":"awp", "ability":75 + index, "elo":1500 + index})
	return out

func ctx(room = null, shared = null, revision: int = 4) -> Dictionary:
	return {"date":"2026-10-01", "player":{"id":"unchanged-career-player", "name":"原生涯角色"},
		"custom":{"revision":revision, "lobby":room, "shared_lobby":shared, "history":[], "maps":MAPS.duplicate()},
		"ladder":{"revision":revision, "lobby":room if room != null else shared, "rank_human_id":"unchanged-career-player", "player":{"elo":1500}, "history":[], "maps":MAPS.duplicate()},
		"inbox":[], "calendar_events":[]}

func room(phase: String = "ready") -> Dictionary:
	var roster := {}
	var a: Array = []; var b: Array = []
	for index in range(10):
		var player: Dictionary = rows()[index].duplicate(true)
		player["role"] = ["awp", "entry", "lurk", "igl", "rifle"][index % 5]
		roster[pid(index)] = player
		if index < 5: a.append(pid(index))
		else: b.append(pid(index))
	return {"id":"custom-isolated-room", "mode":"custom", "phase":phase, "a":a, "b":b, "selection":a+b,
		"roster":roster, "human_id":"", "map":"dust2", "ct":"a", "role_assignment_version":1, "picks":[], "bans":[]}

func catalog() -> Dictionary:
	return {"ok":true, "revision":4, "rows":rows().slice(0, 8), "page":1, "page_size":8, "total":12, "pages":2, "search":"", "maps":MAPS.duplicate()}

func show(context: Dictionary, connection: Dictionary = {}) -> void:
	Computer.custom_room.reset()
	Computer.report.clear(); Computer.page_reports.clear()
	transport.fixture_reset(context)
	Computer.custom_room.catalog = catalog()
	Computer.custom_room.catalog_path = Computer.custom_room._catalog_query()
	Computer.custom_room.status = connection.duplicate(true)
	Computer.present("club")
	Computer._navigate("custom", false)
	await settle()

func named(name_text: String):
	return Computer.content.find_child(name_text, true, false)

func button(name_text: String) -> Button:
	return named(name_text) as Button

func labels() -> String:
	var text: PackedStringArray = []
	for label in Computer.content.find_children("*", "Label", true, false): text.append(label.text)
	return "\n".join(text)

func pool_buttons(prefix: String) -> Array:
	var out: Array = []
	for control in Computer.content.find_children("*", "Button", true, false):
		if str(control.name).begins_with(prefix): out.append(control)
	return out

func visible_pool() -> int:
	var count := 0
	for control in pool_buttons("CustomAddA_"):
		var overlap: Rect2 = Computer.scroll.get_global_rect().intersection(control.get_global_rect())
		if overlap.size.y >= 22 and overlap.size.x >= control.size.x * .5: count += 1
	return count

func capture_page(filename: String) -> void:
	if not capture: return
	await settle()
	await RenderingServer.frame_post_draw
	var output := ProjectSettings.globalize_path("res://tests-output")
	DirAccess.make_dir_recursive_absolute(output)
	check(get_viewport().get_texture().get_image().save_png(output.path_join(filename)) == OK, "capture " + filename)

func run() -> void:
	transport = get_node("/root/CareerBridge")
	if not transport.has_method("fixture_reset") or not "--no-service" in OS.get_cmdline_user_args():
		push_error("Custom UI requires test bridge and --no-service")
		get_tree().quit(2); return
	capture = "--custom-capture" in OS.get_cmdline_user_args()
	Computer.set_process(false); Phone.set_process(false)
	get_window().content_scale_size = Vector2i(1280, 720)
	get_window().size = Vector2i(1280, 720)
	await show(ctx())
	Computer._navigate("battle", false)
	await settle()
	check(button("ComputerOpenCustom") != null and button("ComputerOpenRTS") != null, "battle center has explicit custom and RTS entries")
	button("ComputerOpenCustom").pressed.emit()
	await settle()
	check(Computer.active_page == "custom", "battle entry opens independent custom page")
	check(pool_buttons("CustomAddA_").size() == 8 and visible_pool() > 0, "1280x720 search page includes eight rows and readable first-fold add buttons")
	check(button("CustomCreate").disabled, "incomplete ten-player roster cannot create room")
	check(named("CustomControl").get_item_metadata(0) == "", "default observer is explicit empty human id for ten bots")
	await capture_page("custom_roster_1280.png")
	var before: String = JSON.stringify(CareerBridge.context)
	button("CustomAddA_" + pid(0)).pressed.emit()
	button("CustomAddB_" + pid(1)).pressed.emit()
	Computer.custom_room.add_player("b", pid(0))
	check(Computer.custom_room.a == [pid(0)] and Computer.custom_room.b == [pid(1)], "same stable player cannot appear twice or on both teams")
	check(JSON.stringify(CareerBridge.context) == before and transport.fixture_calls.is_empty(), "roster selections remain local draft and never mutate career or room")
	Computer.custom_room._set_human(pid(0))
	Computer.custom_room.remove_player("a", pid(0))
	check(Computer.custom_room.human_id.is_empty(), "removing controlled player safely returns to observer mode")
	Computer.custom_room.add_player("a", pid(0))
	button("CustomRecommend").pressed.emit()
	check(transport.fixture_calls[-1]["path"] == "/api/3d/custom/recommend", "recommend calls custom-only endpoint")
	check(button("CustomRecommend").disabled and not named("CustomSearch").editable and named("CustomMap").disabled, "pending write locks local mutable selectors and roster actions")
	var recommended: Array = []
	for index in range(10): recommended.append(pid(index))
	transport.fixture_complete({}, {"ok":true, "players":recommended, "rows":rows().slice(0, 10)})
	await settle()
	check(Computer.custom_room.a.size() == 5 and Computer.custom_room.b.size() == 5, "recommendation fills both teams to exactly five")
	check(Computer.custom_room.a[0] == pid(0) and Computer.custom_room.b[0] == pid(1), "recommendation preserves previously chosen side and stable ids")
	var chosen: Array = Computer.custom_room.a + Computer.custom_room.b
	var unique := {}; for id in chosen: unique[id] = true
	check(unique.size() == 10 and not button("CustomCreate").disabled, "recommended roster is unique and unlocks create")
	button("CustomCreate").pressed.emit()
	var request: Dictionary = transport.fixture_calls[-1]
	check(request["path"] == "/api/3d/custom/create" and request["body"]["players"] == chosen, "create sends ordered A-five then B-five stable ids")
	check(request["body"]["revision"] == 4 and request["body"]["human_id"] == "" and request["body"]["map"] == "dust2" and request["body"]["ct"] == "a", "create uses shared revision map ct and observer schema")
	var ready_room := room()
	transport.fixture_complete(ctx(ready_room, {"id":ready_room.id, "mode":"custom", "phase":"ready"}, 5))
	Computer.custom_room.received("/api/3d/custom/status", {"ok":true, "status":"idle", "can_launch":true, "process_known":true, "cs2_running":false})
	await settle()
	check(not button("CustomLaunch").disabled and not button("CustomSimulate").disabled and button("CustomConfigure").disabled, "ready unchanged room can launch or simulate without redundant configure")
	check(labels().contains("主狙") and labels().contains("突破") and labels().contains("自由人") and labels().contains("指挥") and labels().contains("步枪手"), "saved room uses backend five-position assignment instead of duplicate catalog roles")
	check(not button("CustomRTS").disabled, "ready saved Dust2 roster enables RTS instruction entry")
	await capture_page("custom_ready_1280.png")
	Computer.custom_room._set_map("mirage"); Computer.custom_room._set_ct("b"); Computer.custom_room._set_human(pid(2))
	check(button("CustomLaunch").disabled and button("CustomSimulate").disabled and button("CustomRTS").disabled, "unsaved map or controller blocks launch simulate and RTS until configured")
	button("CustomConfigure").pressed.emit()
	request = transport.fixture_calls[-1]
	check(request["body"].get("lobby_id") == ready_room.id and request["body"].get("map") == "mirage" and request["body"].get("ct") == "b" and request["body"].get("human_id") == pid(2), "configure uses bound room and current map side controlled stable id")
	ready_room["map"] = "mirage"; ready_room["ct"] = "b"; ready_room["human_id"] = pid(2)
	transport.fixture_complete(ctx(ready_room, {"id":ready_room.id, "mode":"custom", "phase":"ready"}, 6))
	await settle()
	check(not Computer.custom_room.dirty and CareerBridge.context.player.id == "unchanged-career-player" and CareerBridge.context.ladder.rank_human_id == "unchanged-career-player", "custom controller change never changes career or ranked identity")
	check(named("CustomRemove_" + pid(0)) == null and pool_buttons("CustomAddA_").is_empty(), "existing saved room roster is immutable until ending room")
	var launching := room("starting")
	await show(ctx(launching), {"ok":true, "status":"failed", "can_retry":true, "can_collect":true, "process_known":true, "cs2_running":false, "reason":"隔离模拟启动失败"})
	check(button("CustomRetry") != null and button("CustomCollect") != null and button("CustomCancel") != null, "failed pending startup offers retry collect and explicit end room")
	check(named("CustomMap").disabled and named("CustomControl").disabled, "pending real-result room cannot edit roster map or controller")
	var pending_widget: int = button("CustomRetry").get_instance_id()
	Computer.custom_room.received("/api/3d/custom/status", Computer.custom_room.status.duplicate(true))
	await settle()
	check(button("CustomRetry").get_instance_id() == pending_widget, "unchanged custom status poll does not repaint pending action widgets")
	await capture_page("custom_pending_1280.png")
	button("CustomCollect").pressed.emit()
	check(transport.fixture_calls[-1]["path"] == "/api/3d/custom/collect" and transport.fixture_calls[-1]["body"].get("lobby_id") == launching.id, "collect is bound to original custom room and endpoint")
	transport.fixture_complete({}, {"ok":false, "msg":"隔离检查：战绩暂未回传。"})
	await settle()
	check(Computer.custom_room.pending_action.is_empty() and labels().contains("暂未回传") and not button("CustomCollect").disabled, "failed collection has feedback and restores explicit manual retry")
	button("CustomRetry").pressed.emit()
	check(transport.fixture_calls[-1]["path"] == "/api/3d/custom/launch" and transport.fixture_calls[-1]["body"].get("lobby_id") == launching.id, "retry binds original custom launch room without creating another")
	transport.fixture_complete({}, {"ok":false, "msg":"隔离检查：请求超时", "outcome_unknown":true})
	await settle()
	check(Computer.custom_room.uncertain and labels().contains("不会自动重试"), "uncertain write completion clears pending and shows reconciliation feedback")
	var sent: int = transport.fixture_calls.size()
	Computer.custom_room.process(20)
	Computer.custom_room.command("launch")
	check(transport.fixture_calls.size() == sent, "unknown launch never auto-replays or accepts another write before status reconciliation")
	Computer.custom_room.received("/api/3d/custom/status", {"ok":true, "status":"failed", "can_retry":true, "can_collect":true, "process_known":false, "cs2_running":null})
	await settle()
	check(not Computer.custom_room.uncertain and button("CustomCancel") == null, "status reconciliation restores manual retry while unknown process prevents cancel")
	Computer.custom_room.received("/api/3d/custom/status", {"ok":true, "can_collect":true, "process_known":true, "cs2_running":true})
	await settle()
	check(button("CustomCancel") == null, "running CS2 game cannot cancel active custom room")
	Computer.custom_room.received("/api/3d/custom/status", {"ok":true, "can_collect":true, "process_known":true, "cs2_running":false})
	await settle()
	button("CustomCancel").pressed.emit(); await settle()
	check(button("CustomCancelConfirm") != null and transport.fixture_calls.size() == sent, "ending room requires explicit confirmation before any write")
	button("CustomCancelConfirm").pressed.emit()
	check(transport.fixture_calls[-1]["path"] == "/api/3d/custom/cancel" and transport.fixture_calls[-1]["body"].get("lobby_id") == launching.id, "confirmed cancel binds original room")
	transport.fixture_complete(ctx(null, null, 7))
	await settle()
	check(Computer.custom_room.a.is_empty() and Computer.custom_room.b.is_empty() and button("CustomCreate").disabled, "successful cancel resets to a clean draft without old members")
	await show(ctx(null, {"id":"rank-lock", "mode":"rank", "phase":"draft"}))
	check(button("CustomForeignRoom") != null and button("CustomCreate") == null, "unfinished ranked room clearly blocks custom creation")
	check(not Computer.custom_room.command("create") and transport.fixture_calls.is_empty(), "foreign rank lock cannot be bypassed through custom create helper")
	await show(ctx(room()))
	Computer._navigate("ladder", false); await settle()
	check(labels().contains("共享房间") and Computer.content.find_children("LadderDraft_*", "Button", true, false).is_empty(), "custom room is never relabeled or manually controlled through ladder page")
	await show(ctx())
	var field: LineEdit = named("CustomSearch")
	field.grab_focus(); await settle()
	for keycode in [KEY_E, KEY_P]:
		var key := InputEventKey.new(); key.keycode = keycode; key.physical_keycode = keycode; key.unicode = 101 if keycode == KEY_E else 112; key.pressed = true
		get_viewport().push_input(key)
		var release := key.duplicate(); release.pressed = false; get_viewport().push_input(release)
	await settle()
	check(Computer.screen.visible and field.text == "ep" and Computer.custom_room.search_draft == "ep", "native E P typing stays in search without closing workstation")
	field.text = "选手 & EP"; field.text_changed.emit(field.text)
	Computer.custom_room.search_players()
	Computer.custom_room.process(0)
	check(transport.fixture_reads[-1]["path"].contains("search=" + "选手 & EP".uri_encode()) and transport.fixture_reads[-1]["path"].contains("page=1"), "catalog search sends encoded query and resets to first page")
	var result := catalog(); result["rows"] = rows().slice(8, 12); result["search"] = "选手 & EP"
	Computer.custom_room.received(Computer.custom_room.catalog_path, result)
	await settle()
	check(button("CustomAddA_" + pid(8)) != null and button("CustomAddA_" + pid(0)) == null, "search result renders actual response stable ids")
	button("CustomNextPage").pressed.emit(); Computer.custom_room.process(0)
	check(transport.fixture_reads[-1]["path"].contains("page=2"), "catalog next page has independent server pagination")
	Computer.custom_room.catalog.clear(); Computer.custom_room.fetch_catalog()
	Computer.custom_room.process(0); await settle()
	var reads_before: int = transport.fixture_reads.size()
	Computer.custom_room.process(10); await settle()
	check(Computer.custom_room.catalog_failed and button("CustomRetryCatalog") != null, "failed empty catalog has an explicit retry action")
	check(transport.fixture_reads.size() == reads_before, "failed directory never creates an automatic read retry loop")
	button("CustomRetryCatalog").pressed.emit()
	check(Computer.custom_room.request_catalog and not Computer.custom_room.catalog_failed, "catalog manual retry schedules one new read")
	await show(ctx(room()), {"ok":true, "can_launch":true})
	button("CustomSimulate").pressed.emit()
	check(transport.fixture_calls[-1]["path"] == "/api/3d/custom/simulate" and transport.fixture_calls[-1]["body"].get("lobby_id") == "custom-isolated-room", "simulation uses custom endpoint and bound room without CS2 startup")
	var report := {"id":"custom-isolated-room", "mode":"custom", "source":"simulated", "date":"2026-10-01", "human_id":"", "changes":{}, "map":{"map":"dust2", "score":"13 : 8", "winner":"A 队", "players":{"A 队":[], "B 队":[]}}}
	var finished := room("finished"); finished["result"] = report
	transport.fixture_complete(ctx(finished, null, 8), {"ok":true, "reason":"模拟已完成，不计天梯积分。", "result":report})
	await settle()
	check(not Computer.report.is_empty() and labels().contains("13 : 8") and not labels().contains("你的天梯积分"), "simulation report opens scores without claiming career or Elo settlement")
	Computer._back(); await settle()
	button("CustomNewDraft").pressed.emit(); await settle()
	check(button("CustomCreate") != null and Computer.custom_room.a.is_empty() and Computer.custom_room.b.is_empty(), "finished shared room supports selecting a fresh ten-player draft")
	var calls_before: int = transport.fixture_calls.size()
	Computer.rts_render = func(parent: Node):
		var label := Label.new(); label.name = "RTSFixtureCallback"; parent.add_child(label)
	Computer._navigate("rts", false); await settle()
	check(named("RTSFixtureCallback") != null and transport.fixture_calls.size() == calls_before, "RTS navigation invokes supplied readonly renderer without career command")
	Computer.rts_render = Callable()
	check(CareerBridge.endpoint.is_empty() and not CareerBridge.owns_service, "custom tests never start backend CS2 or save writer")
	Computer.close_computer()
	print("CUSTOM_UI_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
