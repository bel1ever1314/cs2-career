extends Node
## Run with CareerBridge autoloaded from tests/controls_bridge_fixture.gd.
const Controls = preload("res://scripts/computer_controls.gd")
const UI = preload("res://scripts/computer_ui.gd")
var content: VBoxContainer
var active_page := "management"
var profile_tab := "overview"
var notice := ""
var helper = Controls.new()
var commands: Array = []
var navigation := ""
var checks := 0
var failures: Array[String] = []

func _ready() -> void:
	if not CareerBridge.get_script().resource_path.ends_with("controls_bridge_fixture.gd"):
		push_error("Controls UI fixture needs tests/controls_bridge_fixture.gd as CareerBridge; do not use the real backend.")
		get_tree().quit(1)
		return
	content = VBoxContainer.new()
	add_child(content)
	helper.attach(self)
	call_deferred("run")

func check(ok: bool, text: String) -> void:
	checks += 1
	if not ok: failures.append(text)
	print("CONTROLS_UI_CHECK ", "PASS " if ok else "FAIL ", text)

func _label(parent: Node, value: String, size: int = 14, color: Color = UI.INK) -> Label:
	return UI.label(parent, value, size, color)

func _button(parent: Node, value: String, callback: Callable, _write: bool = true) -> Button:
	return UI.button(parent, value, callback)

func _device_command(path: String, body: Dictionary) -> void:
	commands.append({"path":path, "body":body.duplicate(true)})

func _navigate(page: String) -> void:
	navigation = page

func _open_phone(page: String) -> void:
	navigation = "phone:" + page

func _load_detail(kind: String, key: String) -> void:
	navigation = kind + ":" + key

func _tabs(parent: Node, options: Array, _selected: String, callback: Callable) -> void:
	for option in options: _button(parent, option["label"], callback.bind(option["id"]), false)

func _rebuild() -> void:
	UI.clear(content)
	helper.render(active_page)

func page(name: String, data: Dictionary) -> void:
	active_page = name
	helper.cache[helper._path(name)] = {"revision":3, "page":name, "data":data}
	_rebuild()

func find_button(caption: String, node: Node = content) -> Button:
	for child in node.get_children():
		if child is Button and child.text == caption: return child
		var found := find_button(caption, child)
		if found: return found
	return null

func run() -> void:
	var roster: Array = []
	for index in range(5):
		roster.append({"player_id":"p%d" % index, "name":"Player%d" % index,
			"role":["rifle", "awp", "igl", "entry", "lurk"][index], "ability":70, "age":19})
	var management := {"team":"Fixture Academy", "roster":roster, "roles":["rifle", "awp", "igl", "entry", "lurk"], "roles_allowed":true,
		"role_labels":{}, "contract_allowed":true, "offers":[{"id":"offer1", "title":"合同", "team":"Fixture Team", "status":"open", "body":"fixture contract"}], "pending":{}, "history":[]}
	page("management", management)
	var role = content.find_child("RosterRole_p0", true, false)
	check(role != null, "roster exposes per-player role controls")
	role.select(1)
	role.item_selected.emit(1)
	check(helper.role_draft["Player0"] == "awp" and helper.role_draft["Player1"] == "rifle", "selecting occupied AWP swaps original jobs")
	content.find_child("RosterSave", true, false).pressed.emit()
	check(commands[-1]["path"] == "/api/3d/controls/roles" and commands[-1]["body"]["roles"]["Player0"] == "awp", "save submits current role draft and a request identifier")
	check(commands[-1]["body"].has("request_id"), "write commands carry idempotence identifiers")
	find_button("查看加盟选择").pressed.emit()
	check(commands[-1]["path"].ends_with("contract/accept") and commands[-1]["body"]["id"] == "offer1", "contract opens original decision through explicit offer ID")
	management["roles_allowed"] = false
	management["contract_allowed"] = false
	page("management", management)
	check(content.find_child("RosterSave", true, false).disabled and find_button("查看加盟选择").disabled, "backend pending-match gates disable roster and contract actions")

	page("assistance", {"levels":["major", "qual"], "invites":{"major":"manual"}, "points":"off", "axes":["firepower"], "axis_labels":{"firepower":"枪法"}, "allowed":true})
	var invite = content.find_child("InviteRule_major", true, false)
	invite.select(2)
	invite.item_selected.emit(2)
	content.find_child("SaveInviteRules", true, false).pressed.emit()
	check(commands[-1]["body"]["invites"]["major"] == "decline", "invite settings retain edited level rule until save")
	var points = content.find_child("AutoPointDirection", true, false)
	points.select(2)
	points.item_selected.emit(2)
	content.find_child("SavePointDirection", true, false).pressed.emit()
	check(commands[-1]["body"]["points"] == "firepower", "training direction submits original axis identifier")
	CareerBridge.busy = true
	_rebuild()
	check(not content.find_child("SavePointDirection", true, false).disabled, "helper preserves semantic eligibility while owner applies transient request lock")
	CareerBridge.busy = false

	page("training", {"date":"2026-03-04", "pending":false, "launch_allowed":true, "config":{"ready":true},
		"opponents":[{"id":"opponent1", "name":"Opponent"}], "maps":["dust2", "mirage"], "personal":{"attr_points":2}, "growth_window":{}})
	var map_choice = content.find_child("TrainingMap", true, false)
	map_choice.select(1)
	map_choice.item_selected.emit(1)
	content.find_child("TrainingLaunch", true, false).pressed.emit()
	check(commands[-1]["path"].ends_with("training/launch") and commands[-1]["body"]["map"] == "mirage", "real training submits currently selected map and opponent")
	find_button("手动分配属性点").pressed.emit()
	check(navigation == "profile" and profile_tab == "growth", "manual growth opens existing shared profile controls")
	page("training", {"pending":true, "session":{"map":"mirage", "nonce":"fixture-training-nonce"}, "personal":{}, "growth_window":{}})
	find_button("核验并结算训练").pressed.emit()
	check(commands[-1]["path"].ends_with("training/finish"), "pending original training exposes verification action")
	var old_commands := commands.size()
	find_button("取消待核验训练").pressed.emit()
	check(commands.size() == old_commands and find_button("确认取消核验") != null, "training cancellation first shows explicit confirmation")
	find_button("确认取消核验").pressed.emit()
	check(commands[-1]["body"]["confirmed"] == true and commands[-1]["body"]["nonce"] == "fixture-training-nonce", "cancellation identifies current session and carries explicit confirmation")

	page("rankings", {"rows":[{"rank":1, "player":"RankPlayer", "team":"Team", "rating":1.2, "maps":25, "score":2.5}], "years":[2026], "year":2026, "pages":1, "total":1})
	find_button("RankPlayer · Team").pressed.emit()
	check(navigation == "player:RankPlayer", "Top20 names open existing player statistics detail")
	helper.ranking_search = "Team"
	helper._search_rankings()
	await get_tree().process_frame
	check(CareerBridge.requests[-1]["path"].contains("search=Team") and not CareerBridge.requests[-1]["post"], "rankings fetch bounded filtered read projection")
	helper.pending_path = ""
	page("workshop", {"root":"E:/isolated/extensions", "ready":0, "packs":[{"name":"Broken Pack", "version":"1", "id":"broken", "status":"rejected", "kinds":["incidents"], "errors":["fixture validation error"]}]})
	content.find_child("ReloadWorkshop", true, false).pressed.emit()
	check(commands[-1]["path"].ends_with("workshop/reload"), "workshop exposes original JSON registry reload")
	check(helper.render("unowned_page") == false, "helper leaves other desktop pages to owner")
	helper.received("/api/3d/controls/workshop/reload", {"ok":false, "msg":"Fixture rejection"})
	check(notice == "Fixture rejection", "rejected control commands surface original backend reason")
	print(JSON.stringify({"ok":failures.is_empty(), "checks":checks, "failures":failures, "real_backend_connected":false}))
	get_tree().quit(0 if failures.is_empty() else 1)
