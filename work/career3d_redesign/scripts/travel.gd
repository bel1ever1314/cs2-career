extends Node
## In-process scene hand-off. Never opens another executable or reads Career.
signal arrived(destination: String)
const TravelMenu = preload("res://scripts/travel_menu.gd")
const MatchGuidance = preload("res://scripts/world_match_guidance.gd")
var busy := false
var menu_open := false
var menu: TravelMenu
var menu_scene: Node
var door_scene: Node
var door_inside := false
var door_dismissed := false
var club_session: Dictionary = {}
var returning := false
var curtain: ColorRect
var title: Label
var overlay: CanvasLayer
var match_visit: Dictionary = {}
var awards_visit: Dictionary = {}
var match_guidance_hud: CanvasLayer
const SCENES := {"club":"res://play.tscn","major":"res://major_walk.tscn","bedroom":"res://bedroom.tscn","lan":"res://lan.tscn","awards":"res://awards.tscn"}

func _ready() -> void:
	menu = TravelMenu.new(); add_child(menu)
	menu.confirmed.connect(_confirm_menu); menu.cancelled.connect(dismiss_for_visit)
	menu.resolve_requested.connect(_resolve_door_request)
	overlay=CanvasLayer.new();overlay.layer=100;add_child(overlay)
	curtain=ColorRect.new();curtain.color=Color("101c23")
	curtain.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	curtain.mouse_filter=Control.MOUSE_FILTER_IGNORE;overlay.add_child(curtain)
	title=Label.new();title.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	title.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;title.vertical_alignment=VERTICAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size",29);curtain.add_child(title)
	curtain.modulate.a=0;curtain.visible=false
	match_guidance_hud = MatchGuidance.new(); add_child(match_guidance_hud)
	CareerBridge.changed.connect(_career_changed)
	_career_changed()

func match_guidance() -> Dictionary:
	var game := current_game()
	var value: Variant = game.get("attendance", {})
	var attendance: Dictionary = value if value is Dictionary else {}
	if attendance.is_empty():
		value = CareerBridge.context.get("match_preflight", {})
		var preflight: Dictionary = value if value is Dictionary else {}
		if str(preflight.get("match_id", "")) == str(game.get("id", "")):
			value = preflight.get("attendance", {})
			attendance = value if value is Dictionary else {}
	if attendance.is_empty() or str(attendance.get("match_id", "")) != str(game.get("id", "")): return {}
	return attendance.duplicate(true)

func current_game() -> Dictionary:
	# The service returns JSON null when there is no next scheduled match.
	var value: Variant = CareerBridge.context.get("nextmatch")
	return value if value is Dictionary else {}

func match_visit_current(destination: String = "") -> bool:
	var game := current_game()
	var id := str(match_visit.get("match_id", ""))
	if id.is_empty() or id != str(game.get("id", "")): return false
	if not destination.is_empty() and destination != str(match_visit.get("destination", "")): return false
	var attendance := match_guidance()
	if not attendance.is_empty():
		return bool(attendance.get("is_today", false)) and str(attendance.get("phase", "")) in ["today", "in_progress"]
	var today := str(CareerBridge.context.get("date", ""))
	return bool(game.get("due", false)) and (today.is_empty() or today == str(game.get("date", "")))

func preview_match_hint(destination: String) -> String:
	var attendance := match_guidance()
	if attendance.is_empty() or not bool(attendance.get("planned", false)): return ""
	var venue := str(attendance.get("display_name", attendance.get("venue_name", "比赛场馆")))
	if destination != str(attendance.get("destination", "")):
		return "本场比赛在「%s」 · %s · 可从门口选择前往" % [venue, attendance.get("date", "")]
	if bool(attendance.get("is_today", false)):
		return "今日对阵 %s · 到门口选择「%s」，准备本场比赛" % [attendance.get("opponent", ""), venue]
	return "%s 对阵 %s · 今天可以先看看场馆，比赛日再来入座" % [attendance.get("date", ""), attendance.get("opponent", "")]

func _career_changed() -> void:
	if not match_visit.is_empty() and not match_visit_current(): match_visit.clear()
	if is_instance_valid(match_guidance_hud): match_guidance_hud.refresh()
	if menu_open and is_instance_valid(menu_scene):
		for destination in SCENES:
			if menu_scene.scene_file_path == SCENES[destination]:
				var chosen := menu.destinations[menu.selected] if not menu.destinations.is_empty() else ""
				menu.present(destination)
				if chosen in menu.destinations: menu.select_index(menu.destinations.find(chosen))
				break

func open_menu(current_destination: String) -> bool:
	if busy or menu_open or CareerBridge.phone_open or not SCENES.has(current_destination): return false
	var scene := get_tree().current_scene
	if scene == null or scene.scene_file_path != SCENES[current_destination]: return false
	menu_scene = scene
	menu_open = true
	menu.present(current_destination)
	return true

# Scenes report physical door reach independently from their nearest object/NPC.
# Device/help/conversation ownership hides the prompt without dismissing a visit.
func update_door(current_destination: String, near_door: bool, allowed: bool = true) -> void:
	var scene := get_tree().current_scene
	if scene == null or not SCENES.has(current_destination) or scene.scene_file_path != SCENES[current_destination]: return
	if not is_instance_valid(door_scene) or door_scene != scene:
		close_menu(); door_scene = scene; door_inside = false; door_dismissed = false
	if not near_door:
		door_inside = false; door_dismissed = false; close_menu(); return
	door_inside = true
	if not allowed or busy or CareerBridge.phone_open:
		close_menu(); return
	if not door_dismissed and not menu_open: open_menu(current_destination)

func dismiss_for_visit() -> void:
	door_dismissed = true
	close_menu()

func close_menu() -> void:
	if not menu_open: return
	menu.dismiss()
	menu_open = false
	menu_scene = null

func _confirm_menu(destination: String) -> void:
	if not menu_open or busy or menu.request_pending: return
	var attendance := match_guidance()
	var today := bool(attendance.get("is_today", false)) and bool(attendance.get("due", false))
	var can_arrive := bool(attendance.get("can_travel", false)) or bool(attendance.get("can_return", false))
	if (bool(attendance.get("planned", false)) or today) and can_arrive and destination == str(attendance.get("destination", "")):
		if Computer.match_center.request_pending:
			menu.set_notice("上一项操作正在处理，请稍等。")
			return
		menu.set_notice("正在核对本场比赛、阵容与地图……", true)
		Computer.match_center.travel_real(str(attendance.get("match_id", "")))
		return
	go(destination)

func finish_door_request(text: String, events: bool = false) -> void:
	if not menu.request_pending: return
	menu.set_notice(text if not text.is_empty() else "场馆准备未完成，请查看比赛准备。", false, events)

func _resolve_door_request(events: bool) -> void:
	dismiss_for_visit()
	if events and not CareerBridge.context.get("stories", []).is_empty():
		Phone.present("stories")
	else:
		var scene := get_tree().current_scene
		var place := "bedroom"
		for destination in ["bedroom", "club", "lan", "major"]:
			if scene != null and scene.scene_file_path == SCENES[destination]:
				place = destination
				break
		Computer.open_app("career_match", place)

func can_visit_match(venue: Dictionary, match_id: String) -> bool:
	var destination := str(venue.get("destination", venue.get("kind", "")))
	if match_id.is_empty() or destination not in ["major", "lan"] or not bool(venue.get("travel_allowed", false)): return false
	if str(venue.get("identity_source",""))!="frozen_match_rosters": return false
	if not str(venue.get("match_id",match_id)).is_empty() and str(venue.get("match_id",match_id)) != match_id: return false
	var game := current_game()
	if match_id != str(game.get("id", "")) or not bool(game.get("due", false)): return false
	var attendance := match_guidance()
	if not attendance.is_empty():
		if not bool(attendance.get("is_today", false)): return false
		if not bool(attendance.get("can_travel", false)):
			if not bool(attendance.get("can_return", false)) or str(attendance.get("phase", "")) != "in_progress": return false
			var value: Variant = CareerBridge.context.get("match_preflight", {})
			var preflight: Dictionary = value if value is Dictionary else {}
			value = preflight.get("venue", {})
			var frozen: Dictionary = value if value is Dictionary else {}
			if str(preflight.get("match_id", "")) != match_id or str(frozen.get("identity_source", "")) != "frozen_match_rosters": return false
			for field in ["players_a", "players_b", "human_id", "own_team", "destination"]:
				if venue.get(field) != frozen.get(field): return false
	var today := str(CareerBridge.context.get("date", ""))
	if not today.is_empty() and today != str(game.get("date", "")): return false
	return true

func go_match(venue: Dictionary, match_id: String) -> bool:
	# This is a presentation hand-off, never permission to launch an executable.
	if busy or not can_visit_match(venue, match_id): return false
	var destination := str(venue.get("destination", venue.get("kind", "")))
	var scene := get_tree().current_scene
	if scene != null and scene.scene_file_path == SCENES[destination] and str(match_visit.get("match_id", "")) == match_id:
		Computer.close_computer()
		menu.set_notice("返回本场席位 · 到你的空位按 E 入座")
		return true
	match_visit = {"match_id":match_id, "destination":destination, "venue":venue.duplicate(true)}
	go(destination)
	return true

func is_match_seated(venue: Dictionary, match_id: String) -> bool:
	var destination := str(venue.get("destination", venue.get("kind", "")))
	if busy or match_id.is_empty() or str(match_visit.get("match_id", "")) != match_id: return false
	if str(match_visit.get("destination", "")) != destination or not SCENES.has(destination): return false
	if not match_visit_current(destination): return false
	var scene := get_tree().current_scene
	return scene != null and scene.scene_file_path == SCENES[destination] and scene.has_method("match_seated") and bool(scene.match_seated(match_id))

func go_awards(awards: Dictionary) -> bool:
	if busy or not bool(awards.get("ready", false)) or not bool(awards.get("finalized", false)) or awards.get("year")==null: return false
	var rows: Variant=awards.get("top3",[])
	if not rows is Array or rows.size()!=3: return false
	var ranks: Dictionary={}
	for row in rows:
		if not row is Dictionary: return false
		var rank:=int(row.get("rank",0))
		if rank not in [1,2,3] or ranks.has(rank) or str(row.get("name",row.get("player",""))).strip_edges().is_empty(): return false
		ranks[rank]=true
	awards_visit = awards.duplicate(true)
	go("awards")
	return true

func go(destination: String, preserve_session: bool = true) -> void:
	if busy or not SCENES.has(destination):return
	menu.set_notice("")
	close_menu()
	busy=true
	if destination != str(match_visit.get("destination", "")): match_visit.clear()
	if destination != "awards": awards_visit.clear()
	var old_scene:=get_tree().current_scene
	if preserve_session:
		if old_scene.has_method("save_session"): old_scene.save_session()
	else:
		club_session.clear()
		returning = false
	Phone.close_phone()
	Computer.close_computer()
	var previous_mode: int=old_scene.process_mode
	old_scene.process_mode=Node.PROCESS_MODE_DISABLED
	Input.mouse_mode=Input.MOUSE_MODE_VISIBLE
	curtain.visible=true;curtain.mouse_filter=Control.MOUSE_FILTER_STOP
	title.text={"major":"前往场馆","club":"回到俱乐部","bedroom":"%s  08:00" % CareerBridge.context.get("date",""),"lan":"前往线下赛场","awards":"前往年度颁奖礼"}[destination]
	var fade:=create_tween();fade.tween_property(curtain,"modulate:a",1.0,.45)
	await fade.finished
	# Hidden/minimized GUI windows may stop drawing. The fade has completed;
	# keep its opaque curtain and yield one frame without depending on redraw.
	await get_tree().process_frame
	var path: String=SCENES[destination]
	var result:=ResourceLoader.load_threaded_request(path)
	if result==OK:
		while ResourceLoader.load_threaded_get_status(path)==ResourceLoader.THREAD_LOAD_IN_PROGRESS:
			await get_tree().process_frame
	var packed: PackedScene=ResourceLoader.load_threaded_get(path) if result==OK else null
	if packed==null:
		push_error("Scene could not load: "+path)
		title.text="场景未能载入，正在返回"
		old_scene.process_mode=previous_mode
	else:
		returning=destination=="club"
		get_tree().change_scene_to_packed(packed)
		await get_tree().scene_changed
	var reveal:=create_tween();reveal.tween_property(curtain,"modulate:a",0.0,.6)
	await reveal.finished
	curtain.visible=false;curtain.mouse_filter=Control.MOUSE_FILTER_IGNORE
	busy=false
	if packed:arrived.emit(destination)
