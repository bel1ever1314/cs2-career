extends SceneTree
## Memory-only fixture: no backend, game, save or user preference write.
var failures: Array[String] = []
var checks := 0
var locale
var phone
var computer
var bridge
var cjk := RegEx.new()

func _initialize() -> void:
	call_deferred("run")

func check(value: bool, caption: String) -> void:
	checks += 1
	if not value: failures.append(caption)

func audit(node: Node, page: String) -> void:
	if node is Control and not node.is_visible_in_tree(): return
	if node is Label or node is Button:
		var source := str(node.text)
		var displayed := str(node.tr(source))
		if cjk.search(displayed) and not locale._identity_names.has(displayed):
			failures.append(page + ": " + displayed)
	if node is OptionButton:
		for index in range(node.item_count):
			var displayed := str(node.tr(node.get_item_text(index)))
			if displayed != "简体中文" and cjk.search(displayed) and not locale._identity_names.has(displayed): failures.append(page + " option: " + displayed)
	if node is LineEdit:
		var hint := str(node.tr(node.placeholder_text))
		if cjk.search(hint): failures.append(page + " placeholder: " + hint)
	for child in node.get_children(): audit(child, page)

func run() -> void:
	check("--no-service" in OS.get_cmdline_user_args(), "isolated UI fixture")
	root.size = Vector2i(1440, 1000)
	locale = root.get_node("Locale")
	phone = root.get_node("Phone")
	computer = root.get_node("Computer")
	bridge = root.get_node("CareerBridge")
	bridge.set_process(false); phone.set_process(false); computer.set_process(false)
	cjk.compile("[\\x{3400}-\\x{9fff}]")
	var fixture := {"date":"2026-03-04", "calendar":{"revision":18},
		"player":{"id":"p1", "name":"Fixture player", "role":"rifle", "ability":78, "age":22},
		"team":{"id":"t1", "name":"Fixture team", "rank":10, "region":"EU", "roster":[]},
		"inbox":[], "stories":[], "contacts":[], "calendar_events":[], "recent_matches":[],
		"money":10000, "attr_points":0, "mode":"normal", "season":{"year":2026,"era":"2026","phase":"choice","choice_required":true},
		"profile":{"stats":{},"position_views":[]}, "teams":[],
		"settings":{"difficulty":"Medium", "skins_inventory_mode":"career", "real_skins":false,"steam_id":""},
		"operations":{"loan":{"active":false,"cap":50000,"rate":0.03},"wages":[],"log":[],"unsigned":false,"player_only":false},
		"finance":{"club":{"balance":220000,"next_net":-9500,"lines":[]},"pocket":{"balance":10000,"next_net":1500,"lines":[]}},
		"transfers":{"club_allowed":true,"players":[],"roster":[],"club_money":220000},
		"player_transfers":{"offers":[],"teams":[],"last_attempt":null,"pending":null},
		"scrims":{"opponents":[],"scheduled":[],"history":[]},"custom":{"lobby":null,"maps":["de_dust2"]},
		"ladder":{"player":{"elo":1200,"wins":2,"losses":1},"maps":["de_dust2"],"lobby":null,"history":[]},
		"news":{"rows":[],"total":0,"pages":1},"quick":{"year":2026,"mode":"normal","phase":"choice","can_choose":true,"choice_required":true},
		"start":{"can_continue":true},"avatar":{"appearance":{}},"rts":{"maps":[],"pending":false},
		"environment":{"blocked":"","club":{"tier":"academy","tier_name":"青训俱乐部","tier_name_en":"Academy club","balance":100000,"upgrades":[]},"home":{"balance":10000,"owned":[],"placed":[],"catalog":[]}}}
	fixture.inbox = [{"id":"fixture-mail", "kind":"invite", "status":"open", "date":"2026-03-04", "evname":"Fixture event",
		"title":"测试邀请标题", "title_en":"Fixture invitation", "body":"测试邀请正文", "body_en":"Fixture invitation body."}]
	fixture.stories = [{"id":"fixture-story", "title":"测试剧情标题", "title_en":"Fixture story", "text":"测试剧情正文", "text_en":"Fixture story body.",
		"choices":[{"id":"continue", "label":"测试剧情选择", "label_en":"Fixture story choice"}]}]
	fixture.contacts = [{"id":"fixture-coach", "name":"Fixture coach", "preview":"测试聊天预览", "preview_en":"Fixture chat preview",
		"messages":[{"id":"fixture-message", "name":"Fixture coach", "sender":"coach", "date":"2026-03-04", "text":"测试聊天正文", "text_en":"Fixture chat body."}],
		"replies":[{"id":"fixture-reply", "label":"测试回复选项", "label_en":"Fixture reply"}]}]
	fixture.nextmatch = {"id":"fixture-match", "event":"Fixture event", "date":"2026-03-06", "opponent":"Fixture opponent", "best_of":3, "due":false,
		"attendance":{"display_name":"小型赛场", "instruction":"比赛日到了，到俱乐部训练室的比赛电脑准备。"}}
	var article := {"id":"fixture-news", "title":"测试新闻标题", "title_en":"Fixture news", "text":"测试新闻正文", "text_en":"Fixture news body.",
		"date":"2026-03-04", "category":"awards", "mvp":{"player":"Fixture player", "team":"Fixture team", "role":"rifle", "rating":1.25},
		"five":[{"player":"Fixture player", "team":"Fixture team", "role":"rifle", "rating":1.25}]}
	fixture.news = {"rows":[article], "total":1, "page":1, "pages":1}
	bridge.context = fixture.duplicate(true); bridge.connected = true; bridge.clock_held = true
	locale.register_projection(bridge.context)
	var before := JSON.stringify(bridge.context)
	var old_language: String = locale.language
	locale.set_language("en", false)
	await process_frame
	for page in ["home","mail","chat","calendar","profile","match","quick","settings","stories","news"]:
		phone.present(page)
		await process_frame
		audit(phone.screen, "phone " + page)
	phone.present("mail"); phone.selected_mail = "fixture-mail"; phone._rebuild()
	await process_frame
	audit(phone.screen, "phone mail detail")
	phone.present("chat"); phone.selected_contact = "fixture-coach"; phone._rebuild()
	await process_frame
	audit(phone.screen, "phone chat detail")
	phone.present("news"); phone.news_article = article; phone._rebuild()
	await process_frame
	audit(phone.screen, "phone news detail")
	phone.close_phone()
	computer.present("club")
	for page in ["desktop","battle","career_match","quick","rts","scrim","events","market","operations","transfers","news","profile","mail","calendar","management","training","assistance","rankings","workshop","appearance","saves","settings"]:
		computer._navigate(page, false)
		await process_frame
		audit(computer.screen, "computer " + page)
	computer._navigate("mail", false); computer.selected_mail = fixture.inbox[0]; computer._rebuild()
	await process_frame
	audit(computer.screen, "computer mail detail")
	computer._navigate("news", false); computer.news.article = article; computer._rebuild()
	await process_frame
	audit(computer.screen, "computer news detail")
	check(JSON.stringify(bridge.context) == before, "language and page visits preserve context")
	check(bridge.endpoint.is_empty() and not bridge.owns_service, "no service or CS2 launched")
	locale.set_language("zh-CN", false)
	check(locale.text("布置房间") == "布置房间", "Chinese restored")
	locale.set_language(old_language, false)
	print("LOCALE_UI_RESULT checks=", checks, " failures=", JSON.stringify(failures))
	quit(0 if failures.is_empty() else 1)
