extends Node
const Board = preload("res://scripts/club_notice_board.gd")
const Display = preload("res://scripts/club_trophy_display.gd")
const Club = preload("res://scripts/club_play.gd")
const Player = preload("res://scripts/chicken_player.gd")
const Interactions = preload("res://scripts/club_interactions.gd")
var checks := 0
var failures: Array[String] = []
var board: Board
var club: Club

func _ready() -> void:
	if not "--no-service" in OS.get_cmdline_user_args():
		get_tree().quit(1)
		return
	call_deferred("run")

func check(ok: bool, description: String) -> void:
	checks += 1
	if not ok: failures.append(description)
	print("CLUB_HONOURS_CHECK ", "PASS " if ok else "FAIL ", description)

func before_phone() -> void:
	board.close_board(false)

func set_device_open(opened: bool, kind: String) -> void:
	club.set_device_open(opened, kind)

func all_text(node: Node) -> String:
	var result := str(node.text) + "\n" if node is Label else ""
	for child in node.get_children(): result += all_text(child)
	return result

func key(code: int) -> void:
	var event := InputEventKey.new()
	event.physical_keycode = code; event.keycode = code; event.pressed = true
	Input.parse_input_event(event); Input.flush_buffered_events()

func title(id: String, team: String, historical: bool) -> Dictionary:
	return {"id":id, "event":"Event " + id, "short":"Cup " + id, "team":team,
		"year":2025, "date":"2025-03-01", "historical":historical, "player_earned":not historical}

func run() -> void:
	CareerBridge.set_process(false)
	CareerBridge.connected = true
	club = Club.new()
	club.player = Player.new()
	club.interactions = Interactions.new()
	club.interactions.player = club.player
	# Do not put the avatar in the scene: these tests need no imported GLB or save.
	board = Board.new()
	add_child(board)
	club.club_board = board
	CareerBridge.context = {"team":{"name":"Vitality"}, "date":"2026-06-18", "media":{},
		"nextmatch":{"event":"Test Open", "date":"2026-06-18", "opponent":"Spirit",
			"attendance":{"display_name":"线下赛场", "instruction":"到门口选择「线下赛场」，前往选手席入座。"}},
		"club_trophies":{"team":"Vitality", "rows":[title("Major", "Vitality", true), title("Open", "Vitality", false)],
			"personal_rows":[title("OldClub", "Spirit", false)]}}
	club._action_completed("reception", {})
	await get_tree().process_frame
	check(board.is_open() and board.page == "reception", "front desk opens the world reception panel")
	check(not Phone.screen.visible and not Computer.screen.visible, "front desk opens neither phone nor computer")
	check(CareerBridge.phone_open and club.player.locked and club.device_kind == "club_board", "reception owns modal movement and clock lock")
	check(club.player.pending_item.is_empty() and not club.player.item_use, "reception does not pull a phone into player's hand")
	var text := all_text(board.content)
	check("Spirit" in text and "线下赛场" in text and "到门口选择" in text, "reception names opponent and explains venue attendance")
	if "--capture-club-board" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://temp"))
		get_viewport().get_texture().get_image().save_png("res://temp/club_reception_panel.png")
	key(KEY_E)
	check(not board.is_open() and not CareerBridge.phone_open and not club.player.locked, "E closes reception and releases movement")
	check(not Phone.screen.visible, "closing world panel does not also open phone")
	await get_tree().process_frame
	club._action_completed("trophy", {})
	text = all_text(board.content)
	check(board.page == "trophy" and "Event Major" in text and "Event Open" in text, "cabinet panel lists historical and newly won club championships")
	check("加盟前的俱乐部冠军" in text and "我的冠军" in text and "Event OldClub" in text, "transferred player's personal titles remain separate from club history")
	var before := board.content.get_child(0)
	board.refresh()
	check(before == board.content.get_child(0), "unchanged context does not rebuild the panel every frame")
	Phone.present()
	check(not board.is_open() and Phone.screen.visible and CareerBridge.phone_open and club.player.locked, "opening phone from board transfers ownership without unlocking movement")
	Phone.close_phone()
	check(not CareerBridge.phone_open and not club.player.locked, "closing the replacement phone releases world ownership")
	await get_tree().process_frame
	board.present("trophy")
	key(KEY_P)
	check(not board.is_open() and not Phone.screen.visible and not CareerBridge.phone_open, "P dismisses cabinet without key leaking into the phone")
	await get_tree().process_frame
	CareerBridge.context["nextmatch"] = null
	board.present("reception")
	check("没有待进行" in all_text(board.content), "reception accepts null schedule")
	board.close_board()
	var model := Node3D.new()
	add_child(model)
	for name_text in ["Trophy_foot", "Trophy_cup_2", "Honours_label", "Trophy_cabinet_shelf"]:
		var mesh := MeshInstance3D.new(); mesh.name = name_text; model.add_child(mesh)
	var display := Display.new()
	add_child(display)
	display.setup(model)
	display.refresh(CareerBridge.context)
	check(not model.get_node("Trophy_foot").visible and not model.get_node("Trophy_cup_2").visible and model.get_node("Trophy_cabinet_shelf").visible, "replace placeholder cups without hiding the cabinet shelves")
	check(display.trophy_nodes.size() == 2 and display.title.text.contains("Vitality"), "actual shelf renders one cup per club championship")
	check(display.trophy_nodes[0].get_meta("honour")["id"] == "Major", "visible cup retains precise event identity")
	var first := display.trophy_nodes[0]
	display.refresh(CareerBridge.context)
	check(first == display.trophy_nodes[0], "unchanged honours do not respawn 3D trophies")
	var many: Array = []
	for index in range(9): many.append(title(str(index), "Vitality", false))
	CareerBridge.context["club_trophies"]["rows"] = many
	display.refresh(CareerBridge.context)
	check(display.trophy_nodes.size() == 6 and display.title.text.contains("9 座"), "six shelf slots show total count without losing full honours list")
	check(display.trophy_nodes[0].position.y == display.trophy_nodes[1].position.y and display.trophy_nodes[2].position.y > display.trophy_nodes[1].position.y, "shelf cups occupy three distinct rows")
	CareerBridge.context["team"]["name"] = "NewClub"
	CareerBridge.context["club_trophies"] = {"team":"NewClub", "rows":[], "personal_rows":[title("OldClub", "Spirit", false)]}
	display.refresh(CareerBridge.context)
	check(display.trophy_nodes.is_empty() and display.title.text.contains("NewClub"), "transfer refreshes club shelf without copying former club's trophies")
	board.present("trophy")
	check("Event OldClub" in all_text(board.content), "transfer preserves own titles in personal section")
	board.close_board()
	club.player.free()
	club.interactions.free()
	club.free()
	print("CLUB_HONOURS_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
