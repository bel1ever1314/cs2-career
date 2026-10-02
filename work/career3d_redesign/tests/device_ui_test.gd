extends Node
## Native layout and modal ownership tests. --no-service uses an explicit UI fixture only.
var failures: Array[String] = []
var checks := 0
var modal_calls: Array = []

func _ready() -> void:
	call_deferred("run")

func set_device_open(opened: bool, kind: String) -> void:
	modal_calls.append({"opened":opened, "kind":kind})

func before_phone() -> void:
	pass

func before_computer() -> void:
	pass

func check(value: bool, label: String) -> void:
	checks += 1
	if not value:
		failures.append(label)
	print("DEVICE_UI_CHECK ", "PASS " if value else "FAIL ", label)

func settle() -> void:
	await get_tree().process_frame
	await get_tree().process_frame

func visible_buttons(node: Node) -> Array[Button]:
	var result: Array[Button] = []
	for child in node.get_children():
		if child is Button and child.is_visible_in_tree():
			result.append(child)
		result.append_array(visible_buttons(child))
	return result

func fit(device: Node, label: String) -> void:
	var viewport_rect := get_viewport().get_visible_rect()
	var rect: Rect2 = device.panel.get_global_rect()
	check(viewport_rect.encloses(rect), label + " physical shell inside viewport")
	check(device.content.get_combined_minimum_size().x <= device.scroll.size.x + 1, label + " no horizontal overflow")
	check(device.scroll.size.y >= device.panel.size.y * 0.4, label + " usable body height")
	# Home intentionally has no top title toolbar in the approved phone design.
	if device.title.is_visible_in_tree():
		check((device.title.get_parent() as Control).size.y <= 64, label + " visible toolbar stays single line")
	if device.name == "Phone":
		var navigation = device.panel.find_child("PhoneNavigation", true, false)
		check(navigation != null and navigation.is_visible_in_tree() and navigation.size.y <= 64, label + " bottom navigation stays visible and compact")
	check((device.clock.get_parent() as Control).size.y <= 50, label + " status bar stays single line")
	for button in visible_buttons(device.screen):
		check(button.focus_mode == Control.FOCUS_ALL, label + " keyboard focus: " + button.text.left(22))
		check(button.size.x >= 32, label + " visible button width: " + button.text.left(22))
		check(button.get_theme_color("font_focus_color") == button.get_theme_color("font_color"), label + " focus preserves text contrast: " + button.text.left(22))

func run() -> void:
	get_viewport().size = Vector2i(1280, 720)
	var offline: bool = "--no-service" in OS.get_cmdline_user_args()
	if offline:
		# Test data is confined to this test process and never sent to the career service.
		CareerBridge.context = {
			"date":"2026-03-04", "player":{"id":"fixture-own", "name":"布局测试选手", "role":"rifle", "ability":78},
			"team":{"id":"fixture-team", "name":"布局测试战队", "rank":10, "region":"EU", "roster":[{"id":"fixture-own", "name":"布局测试选手", "role":"rifle", "ability":78}, {"id":"fixture-mate", "name":"很长的队友姓名 Layout Teammate", "role":"awp", "ability":80}]},
			"inbox":[{"id":"fixture-mail", "title":"赛事邀请 · 布局测试", "kind":"invite", "status":"open", "date":"2026-03-04", "evname":"测试邀请", "dates":"2026-03-10", "body":"这段长邮件用于验证窄屏换行和按钮布局。"}, {"id":"fixture-long-mail", "title":"非常长的赛事邀请标题 Thunderpick World Championship Regional Qualifier 布局验证", "kind":"invite", "status":"read", "date":"2026-03-03", "evname":"长标题验证", "body":"只在测试进程中显示的布局验证文本。"}],
			"stories":[], "recent_matches":[], "calendar_events":[{"id":"fixture-event", "date":"2026-03-10", "name":"赛事日程布局测试", "registered":false}],
			"contacts":[{"id":"coach:fixture-team", "name":"教练", "topic":"coach", "greeting":"今天按自己的节奏来。", "messages":[], "preview":"今天按自己的节奏来。", "replies":[{"id":"practice", "label":"我想练一会儿"}]}, {"id":"fixture-mate", "name":"很长的队友姓名 Layout Teammate", "topic":"teammate", "messages":[], "preview":"有空一起练一会儿？", "replies":[]}],
			"teams":[], "news":{"rows":[{"id":"fixture-report", "title":"很长的赛事荣誉报道 · Major MVP、EVP 与五位置最佳阵容", "date":"2026-03-04", "category":"awards"}], "total":1, "pages":1}, "money":1000,
			"finance":{"club":{"balance":220000, "next_net":-9500, "lines":[{"label":"工资", "amount":-9500}]}, "pocket":{"balance":35000, "next_net":1500, "lines":[{"label":"合同工资", "amount":1500}]}},
			"operations":{"loan":{"active":false, "cap":50000, "rate":0.03}, "wages":[], "log":[], "unsigned":false, "player_only":false, "upgrade_supported":false},
			"transfers":{"club_allowed":true, "club_money":220000, "roster":[{"player_id":"fixture-mate", "name":"很长的可替换成员姓名 Layout Teammate", "role":"awp"}], "players":[{"player_id":"fixture-recruit", "name":"很长的可购买选手姓名 Layout Transfer Target", "role":"rifle", "ability":81, "age":20, "normal_fee":10000, "normal_chance":0.6, "negotiation_fee":1000, "guaranteed_fee":20000, "blocked":""}]},
			"player_transfers":{"offers":[], "teams":[], "last_attempt":null, "pending":null},
			"ladder":{"revision":1, "lobby":null, "player":{"elo":1200, "wins":2, "losses":1}, "history":[], "maps":["dust2", "mirage"]},
			"scrims":{"opponents":[{"id":"fixture-opponent", "name":"训练赛布局测试对手"}], "scheduled":[], "history":[]}
		}
		CareerBridge.connected = true
	else:
		var deadline := Time.get_ticks_msec() + 45000
		while (CareerBridge.connecting or CareerBridge.busy) and Time.get_ticks_msec() < deadline:
			await get_tree().process_frame
		check(CareerBridge.connected, "real career service connected")
	CareerBridge.clock_held = true
	Phone.present()
	await settle()
	check(Phone.active_page == "home", "today compatibility maps to home")
	check(Phone.APPS.size() == 6 and Phone.nav_buttons.size() == 6, "six phone apps")
	check(get_viewport().gui_get_focus_owner() == null, "opening phone does not paint a preselected app")
	var tab := InputEventKey.new()
	tab.physical_keycode = KEY_TAB
	tab.pressed = true
	Phone._input(tab)
	check(get_viewport().gui_get_focus_owner() == Phone.nav_buttons["mail"], "Tab starts native keyboard navigation")
	get_viewport().gui_release_focus()
	await settle()
	fit(Phone, "phone home at 1280x720")
	for item in preload("res://tests/phone_reference_checks.gd").new().evaluate(Phone):
		check(item["ok"], item["label"])
	check(Phone.content.size.y <= Phone.scroll.size.y + 1, "home content fits without scrolling")
	var child_id := Phone.content.get_child(0).get_instance_id()
	await get_tree().create_timer(0.12).timeout
	check(Phone.content.get_child(0).get_instance_id() == child_id, "clock tick does not rebuild phone")
	# App labels belong to the same action as the icon, not a decorative dead area.
	for app in Phone.APPS:
		Phone.present("home")
		await settle()
		var caption: Label = null
		for label in Phone.content.find_children("*", "Label", true, false):
			if str(label.get_meta("app_caption", "")) == str(app["id"]):
				caption = label
				break
		check(caption != null, "app caption remains separate and identifiable: " + str(app["name"]))
		if caption:
			var tap := InputEventMouseButton.new()
			tap.button_index = MOUSE_BUTTON_LEFT
			tap.pressed = true
			caption.gui_input.emit(tap)
			check(Phone.active_page == str(app["id"]), "app name is clickable: " + str(app["name"]))
	for app in Phone.APPS:
		Phone.present(str(app["id"]))
		await settle()
		fit(Phone, "phone " + str(app["id"]))
	Phone.present("mail")
	await settle()
	var mail_rows := Phone.content.find_children("MailRow_*", "Button", true, false)
	check(mail_rows.size() == CareerBridge.context.get("inbox", []).size(), "every real mail has a row, not a decorative card")
	for row in mail_rows:
		check(row.get_theme_stylebox("normal").bg_color.a == 0, "mail row has the reference's transparent surface")
		for word in row.find_children("*", "Label", true, false):
			check(row.get_global_rect().grow(1).encloses(word.get_global_rect()), "mail text stays inside its row: " + str(word.text).left(22))
	Phone.present("calendar")
	var saved_date: String = Phone.selected_date
	Phone._home()
	Phone._route("calendar")
	await settle()
	check(Phone.selected_date == saved_date, "calendar selection survives home navigation")
	Phone.present("mail")
	var inbox: Array = CareerBridge.context.get("inbox", [])
	if not inbox.is_empty():
		Phone._open_mail(str(inbox[0].get("id", "")))
		await settle()
		fit(Phone, "phone mail detail")
		Phone._back()
		check(Phone.active_page == "home" and Phone.screen.visible, "mail detail back returns to phone home")
	Phone.present("chat")
	var contacts := Phone._contacts()
	var contact_id := str(contacts[0].get("id", "")) if not contacts.is_empty() else ""
	Phone._open_chat(contact_id)
	check(not contact_id.is_empty() and Phone.title.text == str(contacts[0].get("name", "")), "chat uses projected stable contact identity")
	Phone._home()
	Phone._route("chat")
	check(Phone.selected_contact == contact_id, "chat return retains contact")
	if offline:
		var narrative := "队友认真回了一句谢谢。你们收好外设，坐下来聊了一会儿。".repeat(14)
		CareerBridge.context["contacts"][1]["messages"] = [{"id":"fixture-birthday-narrative", "date":"2026-03-04", "sender":"narrator", "name":"生日后的回应", "text":narrative}, {"id":"fixture-birthday-reply", "date":"2026-03-04", "sender":"contact", "name":"很长的队友姓名 Layout Teammate", "text":"谢谢，你还记得。"}]
		Phone._finished("/api/3d/story", {"ok":true, "social_contact_id":"fixture-mate", "social_focus_message_id":"fixture-birthday-narrative"})
		await settle()
		check(Phone.active_page == "chat" and Phone.selected_contact == "fixture-mate", "birthday choice automatically shows the related person's response")
		var bodies := Phone.content.find_children("SocialMessageBody", "Label", true, false)
		check(bodies.size() == 2 and bodies[0].text == narrative and bodies[0].max_lines_visible == -1 and bodies[0].size.y > 200, "full birthday narrative wraps with readable height and no clipping")
		check(Phone.content.find_children("*", "ScrollContainer", true, false).is_empty(), "birthday narrative uses the full phone scroll without a tiny nested pane")
		fit(Phone, "birthday conversation")
	Phone._back()
	check(Phone.active_page == "home" and Phone.screen.visible and not Phone.back_button.disabled, "app back shows home with an enabled back control")
	Phone._back()
	check(not Phone.screen.visible and not CareerBridge.phone_open, "back on phone home puts the phone down")
	Phone.present("news")
	await settle()
	fit(Phone, "phone news list")
	Phone.news_article = {"title":"Major 冠军报道 · 一段足够长的标题确认换行", "date":"2026-03-04", "category":"top20", "text":"已保存的新闻全文，不在读页面时重新生成。\n\n另一段长文用来检查手机窄屏。", "rows":[{"rank":1, "player":"fixture-star", "feature":{"title":"年度人物专栏", "sections":[{"heading":"这一年的位置", "text":"这段专栏来自已经保存的最终榜。"}]}}]}
	Phone._rebuild()
	await settle()
	fit(Phone, "phone full article and Top20 feature")
	Phone._back()
	check(Phone.active_page == "home" and Phone.screen.visible, "article back returns to phone home")
	var late_path := "/api/3d/player?id=ui-late-response"
	var late_result := {"ok":true, "detail":{"name":"晚到的选手资料", "player_id":"ui-late-response", "role":"rifle"}}
	# Represent an already accepted GET; no network request or business command is sent.
	Phone.pending_detail_path = late_path
	Phone.pending_detail_intent = Phone.detail_intent_serial
	Phone.pending_detail_open = false
	Phone.close_phone()
	Phone._finished(late_path, late_result)
	check(not Phone.screen.visible and not CareerBridge.phone_open, "late GET does not reopen a closed phone")
	check(Phone.selected_player.get("player_id") == "ui-late-response", "late GET caches detail after close")
	Phone.pending_detail_path = late_path
	Phone.pending_detail_intent = Phone.detail_intent_serial
	Phone.pending_detail_open = true
	Phone._finished(late_path, late_result)
	check(Phone.screen.visible and Phone.active_page == "player", "explicit hidden compatibility intent opens detail")
	Phone.pending_detail_path = late_path
	Phone.pending_detail_intent = Phone.detail_intent_serial
	Phone.pending_detail_open = false
	Phone.close_phone()
	Phone.present("home")
	Phone._finished(late_path, late_result)
	check(Phone.screen.visible and Phone.active_page == "home", "cancelled GET does not redirect a newly opened phone")
	var computer := get_node_or_null("/root/Computer")
	check(computer != null, "Computer autoload registered")
	if computer:
		computer.present("bedroom")
		await settle()
		check(not Phone.screen.visible and computer.screen.visible and CareerBridge.phone_open, "computer exclusively owns modal")
		fit(computer, "bedroom desktop at 1280x720")
		check(computer.APPS.size() == 9, "nine desktop apps include finance transfers and news")
		for page in ["operations", "transfers", "news"]:
			computer._navigate(page)
			await settle()
			fit(computer, "new computer application " + page)
		computer._navigate("operations")
		await settle()
		var amount = computer.content.find_child("ComputerCashAmount_borrow", true, false)
		if amount:
			amount.text = "-1"
			computer.business._cash_command("borrow", amount)
			check(not CareerBridge.busy and not computer.notice.is_empty(), "negative cash never sends a command")
		computer._navigate("transfers")
		var transfer_rows: Array = CareerBridge.context.get("transfers", {}).get("players", [])
		if offline and not transfer_rows.is_empty():
			computer.business._ask_purchase(transfer_rows[0], "guaranteed")
			await settle()
			fit(computer, "transfer confirmation")
			check(not computer.business.pending_purchase.is_empty() and not CareerBridge.busy, "purchase first shows confirmation without spending")
			computer.business._dismiss_confirmation()
		computer._navigate("scrim")
		await settle()
		check(computer.action_buttons.is_empty(), "bedroom scrim has no executable booking action")
		computer.present("club")
		computer._navigate("scrim")
		await settle()
		fit(computer, "club scrim at 1280x720")
		computer._navigate("events")
		await settle()
		fit(computer, "computer events at 1280x720")
		var ladder_report := {"id":"ui-ladder-report", "mode":"rank", "teams":["蓝队", "橙队"], "map":{"map":"dust2", "score":"13-11", "players":{}}, "human_id":"fixture-own"}
		var scrim_report := {"id":"ui-scrim-report", "teams":["本队", "训练对手"], "map":{"map":"mirage", "score":"13-9", "players":{}}, "human_id":"fixture-own"}
		computer._navigate("ladder")
		computer._open_report(ladder_report)
		computer._desktop()
		computer._navigate("scrim")
		await settle()
		check(computer.report.is_empty(), "ladder report does not replace scrim booking")
		check(not computer.action_buttons.is_empty(), "scrim booking remains reachable after ladder report")
		computer._open_report(scrim_report)
		computer._desktop()
		computer._navigate("ladder")
		check(computer.report.get("id") == "ui-ladder-report", "scrim report does not replace ladder report")
		computer._navigate("scrim")
		check(computer.report.get("id") == "ui-scrim-report", "return to scrim restores its own report")
		computer._back()
		computer._navigate("ladder")
		computer._navigate("scrim")
		check(computer.report.is_empty(), "closing scrim report keeps scrim booking state")
		computer._finished("/api/3d/ladder/simulate", {"ok":true, "result":ladder_report})
		check(computer.report.is_empty() and computer.page_reports.get("ladder", {}).get("id") == "ui-ladder-report", "late ladder result is cached only in ladder")
		Phone.present("home")
		Phone.pending_detail_path = late_path
		Phone.pending_detail_intent = Phone.detail_intent_serial
		Phone.pending_detail_open = false
		computer.present("club")
		Phone._finished(late_path, late_result)
		check(computer.screen.visible and not Phone.screen.visible, "late phone GET does not replace an opened computer")
		Phone.present()
		check(Phone.screen.visible and not computer.screen.visible and CareerBridge.phone_open, "phone exclusively owns modal")
		computer.present("club")
		await settle()
		var key := InputEventKey.new()
		key.physical_keycode = KEY_P
		key.pressed = true
		Phone._input(key)
		computer._input(key)
		check(not Phone.screen.visible and not computer.screen.visible and not CareerBridge.phone_open, "P consumes one event without reopening phone")
		await settle()
		computer.present("club")
		key.physical_keycode = KEY_E
		computer._input(key)
		check(not computer.screen.visible and not CareerBridge.phone_open, "E leaves computer")
		check(modal_calls[-1] == {"opened":false, "kind":"computer"}, "computer releases seated world session with correct kind")
	Phone.close_phone()
	print("DEVICE_UI_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	if offline:
		get_tree().quit(0 if failures.is_empty() else 1)
	else:
		CareerBridge.quit()
