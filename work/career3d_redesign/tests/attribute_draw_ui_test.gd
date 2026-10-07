extends Node
## Native saved-team-draw fixtures. No HTTP writes or existing-save access.
const Fixture = preload("res://tests/team_draw_fixture.gd")
const PATH := "/api/3d/start/draw"
var checks := 0
var failures: Array[String] = []
var session: Dictionary = {}
var original_context := ""

func _ready() -> void:
	call_deferred("run")

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("ATTRIBUTE_DRAW_UI_CHECK ", "PASS " if value else "FAIL ", label)

func settle(count: int = 3) -> void:
	for _index in range(count): await get_tree().process_frame

func named(node_name: String) -> Control:
	return Computer.content.find_child(node_name, true, false) as Control

func busy(value: bool, post: bool = false) -> void:
	CareerBridge.active_post = post
	CareerBridge.busy = value
	CareerBridge.busy_changed.emit(value)

func request(action: String) -> Dictionary:
	CareerBridge.queued_command.clear()
	busy(true)
	if action in ["open", "roll"]: (named("CareerTeamDrawRoll") as Button).pressed.emit()
	else: Computer.career_start.attribute_draw.send(action)
	var queued := CareerBridge.queued_command.duplicate(true)
	CareerBridge.queued_command.clear()
	busy(false)
	return queued.get("body", {})

func receive(draw: Dictionary = {}) -> void:
	var response := {"ok":true, "attribute_draw":session.duplicate(true)}
	if not draw.is_empty(): response["draw"] = draw.duplicate(true)
	Computer._finished(PATH, response)

func capture(name: String, viewport: Viewport = null) -> void:
	if DisplayServer.get_name() == "headless": return
	var directory := ""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--capture-dir="): directory = argument.trim_prefix("--capture-dir=")
	if directory.is_empty(): return
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(directory)
	var target := viewport if viewport != null else get_viewport()
	check(target.get_texture().get_image().save_png(directory.path_join(name + ".png")) == OK, "native screenshot " + name)

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(2); return
	var fixture: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/start_options_fixture.json"))
	for era in fixture: fixture[era] = Fixture.upgrade_options(fixture[era])
	CareerBridge.context = {"date":"2026-10-02", "player":{"name":"已有选手", "id":"existing"}, "team":{"name":"已有战队"}, "calendar":{"revision":42}, "avatar":{"appearance":{}}, "inbox":[], "stories":[], "money":12345}
	var media: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/media.json"))
	var manifest_path := str(media.get("team_manifest", ""))
	if FileAccess.file_exists(manifest_path):
		var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
		var paths := {}
		for team in manifest.get("team_backgrounds", {}): paths[team] = manifest.team_backgrounds[team].get("path", "")
		CareerBridge.context["media"] = {"team_backgrounds":paths}
	CareerBridge.connected = true
	CareerBridge.endpoint = ""
	CareerBridge.clock_held = true
	original_context = JSON.stringify(CareerBridge.context)
	get_window().content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	get_window().content_scale_size = Vector2i(1280, 720)
	get_window().size = Vector2i(1280, 720)
	await settle()
	Computer.open_app("start", "bedroom")
	var start = Computer.career_start
	start.begin_new()
	start.options = fixture["2026"].duplicate(true)
	start.options_by_era = fixture.duplicate(true)
	start.draft.name = "TeamDraw UI"
	start.draft.org = "Fixture Club"
	var draw_ui = start.attribute_draw
	draw_ui.loaded["2026"] = true
	Computer._rebuild()
	await settle()
	check(named("CareerDrawDifficulty") == null and not start.draft.has("difficulty"), "difficulty choices removed from creation and payload")
	check(named("AppearanceEditor") == null and named("CareerStartCreate") == null, "selection page does not render appearance or direct creation")
	check((named("CareerStartNext") as Button).disabled, "incomplete attributes block next step")
	var open_body := request("open")
	check(open_body.action == "open" and not open_body.has("difficulty"), "open intent has no difficulty")
	session = Fixture.empty_session()
	# Read fixtures directly; the open-to-first-roll convenience is verified below.
	draw_ui.pending_body.clear()
	receive()
	await settle()
	var first_team: Dictionary = fixture["2026"].teams[0]
	var roll_body := request("roll")
	check(roll_body.action == "roll" and not roll_body.has("axis") and roll_body.draft_id == session.draft_id, "roll draws one team without axis")
	var first_draw := Fixture.draw(session, first_team)
	receive(first_draw)
	await settle()
	check(draw_ui.candidates.is_empty() and named("CareerTeamAbilities") == null and draw_ui.current_draw().is_empty(), "rolling outcome remains hidden in background until reveal")
	check(draw_ui.current().pending_draw_id == first_draw.draw_id and not draw_ui.unrevealed_draw_id.is_empty(), "outcome remains durably committed while presentation hides it")
	check((named("CareerTeamDrawRoll") as Button).disabled, "pending team must supply one attribute before next draw")
	check(is_instance_valid(draw_ui.reel) and draw_ui.reel.result.name == first_team.name and draw_ui.reel.result.value == "1500", "team animation uses committed VRS team result")
	await capture("team_draw_reel", draw_ui.popup.get_viewport())
	draw_ui.reel.skip()
	draw_ui.popup.hide()
	await settle()
	check(draw_ui.candidates.size() == 35 and draw_ui.unrevealed_draw_id.is_empty(), "reveal exposes five players and seven real ability slots")
	check(str(named("CareerCurrent_opening").text).contains("—") and not draw_ui.candidates[16].button.text.contains("↑"), "unfilled current value is empty, not a fictional zero baseline")
	await capture("team_draw_pending")
	Computer.scroll.scroll_vertical = 250
	await settle()
	var before_scroll := Computer.scroll.scroll_vertical
	var candidate: Dictionary = draw_ui.candidates[16]
	var button: Button = candidate.button
	var before_id := button.get_instance_id()
	button.pressed.emit()
	await settle()
	check(button.get_instance_id() == before_id and Computer.scroll.scroll_vertical == before_scroll, "clicking value keeps same controls and exact scrollbar position")
	check(CareerBridge.queued_command.is_empty() and draw_ui.pending_path.is_empty(), "value click only previews and does not consume the draw")
	check(str(named("CareerCurrent_opening").text).contains("—"), "preview never changes committed current column")
	check(not (named("CareerTeamDrawCommit") as Button).disabled and draw_ui.commit_button.text.contains(candidate.choice.source_player), "chosen value provides explicit commit feedback")
	busy(true)
	draw_ui.commit()
	var select_body: Dictionary = CareerBridge.queued_command.get("body", {}).duplicate(true)
	CareerBridge.queued_command.clear()
	busy(false)
	check(select_body.action == "select" and select_body.draw_id == first_draw.draw_id and select_body.player_id == candidate.choice.player_id and select_body.axis == candidate.choice.axis, "commit references current draw one player and one axis")
	check(draw_ui.commit_button.disabled, "double click while saving cannot duplicate selection")
	Fixture.choose(session, first_draw, candidate.choice.axis, 1)
	receive()
	await settle()
	check(button.get_instance_id() == before_id and Computer.scroll.scroll_vertical == before_scroll, "saved selection updates in place without scrolling to top")
	check(draw_ui.current().axes[3].selected_value == 72 and draw_ui.history.text.contains(first_team.name), "collected ability and history show committed source")
	check(str(named("CareerCurrent_opening").text).contains("72"), "left column displays committed value next to ability")
	for index in range(5):
		check(draw_ui.candidates[15 + index].button.text.contains("↑") == (index > 1), "only strictly higher candidates receive an arrow " + str(index))
	check(draw_ui.candidates[17].button.tooltip_text.contains("+2"), "hover explains the exact improvement")
	check(not draw_ui.roll_button.disabled and draw_ui.commit_button.disabled, "one committed value unlocks next draw and seals previous team")
	check((named("CareerStartNext") as Button).disabled, "one ability is insufficient for appearance")
	await capture("team_draw_selection")
	# Budget guard: when only empty abilities are allowed, a filled axis is locked.
	var second_body := request("roll")
	var second_draw := Fixture.draw(session, first_team, 2)
	session.selectable_axes = ["utility"]
	receive(second_draw)
	await settle()
	draw_ui.reel.skip(); draw_ui.popup.hide()
	check(draw_ui.candidates[0].button.disabled and not draw_ui.candidates[30].button.disabled, "server selectable axes enforce budget without blocking valid empty axis")
	check(second_body.draft_revision == 2, "subsequent roll uses saved revision")
	# Restore a complete saved draft and exercise next/back without losing choices.
	session = Fixture.completed()
	draw_ui.sessions["2026"] = session.duplicate(true)
	Computer._rebuild()
	await settle()
	check(not (named("CareerStartNext") as Button).disabled, "seven completed abilities unlock explicit next step")
	(named("CareerStartNext") as Button).pressed.emit()
	await settle()
	check(start.page == "appearance" and named("AppearanceEditor") != null and named("CareerTeamAbilities") == null, "only next step opens appearance editor")
	check(named("CareerStartCreate") != null, "creation is available only after appearance step")
	start.avatar.set_value("body_color", "aabbcc")
	(named("CareerStartBackToSelection") as Button).pressed.emit()
	await settle()
	check(start.page == "create" and draw_ui.complete() and start.avatar.values().body_color == "aabbcc", "back preserves collected abilities and appearance draft")
	check(start.draft.name == "TeamDraw UI" and start.draft.org == "Fixture Club", "wizard transitions preserve identity draft")
	await real_schema_checks(draw_ui, start)
	check(JSON.stringify(CareerBridge.context) == original_context, "all team selection fixtures leave existing career projection untouched")
	Computer.close_computer()
	if is_instance_valid(draw_ui.popup): draw_ui.popup.queue_free()
	print("ATTRIBUTE_DRAW_UI_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)

func real_schema_checks(draw_ui: RefCounted, start: RefCounted) -> void:
	var path := ""
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--backend-fixture="): path = argument.trim_prefix("--backend-fixture=")
	if path.is_empty(): return
	var source: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	var scenarios: Array = []
	var raw: Variant = source.get("sessions", {})
	if raw is Dictionary:
		for key in raw: scenarios.append({"name":key, "session":raw[key]})
	else: scenarios = raw
	for scenario in scenarios:
		var real_session: Dictionary = scenario.session
		start.draft.era = str(real_session.era)
		draw_ui.sessions[str(real_session.era)] = real_session.duplicate(true)
		draw_ui.loaded[str(real_session.era)] = true
		start.page = "create"
		Computer._rebuild()
		await settle()
		check(not draw_ui.has_pending_draw() if real_session.pending_draw_id == null else draw_ui.has_pending_draw(), "real backend null pending state: " + str(scenario.name))
		check(draw_ui.complete() == bool(real_session.complete), "real backend completion accepted: " + str(scenario.name))
		for axis in real_session.axes:
			if axis.selected_player_id == null:
				check(str(draw_ui.axis_labels[str(axis.id)].text).contains("—"), "real backend null axis renders unfilled: " + str(scenario.name) + "/" + str(axis.id))
		if real_session.complete:
			check(not (named("CareerStartNext") as Button).disabled, "real backend complete null session opens appearance gate")
