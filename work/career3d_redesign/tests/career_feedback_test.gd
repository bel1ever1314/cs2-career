extends Node
## Read-only presentation fixtures. No service, save or actual CS2 is started.
var checks := 0
var failures: Array[String] = []
var sent: Array = []

func _ready() -> void:
	call_deferred("run")

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("FEEDBACK_CHECK ", "PASS " if value else "FAIL ", label)

func command(path: String, payload: Dictionary) -> bool:
	sent.append({"path":path, "body":payload.duplicate(true)})
	return true

func settle() -> void:
	for _index in range(4): await get_tree().process_frame

func capture(name: String) -> void:
	if DisplayServer.get_name() == "headless": return
	var directory := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture-dir="): directory = arg.trim_prefix("--capture-dir=")
	if directory.is_empty(): return
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(directory)
	check(get_viewport().get_texture().get_image().save_png(directory.path_join(name + ".png")) == OK, "native screenshot " + name)

func champion_layout(feed, viewport_size: Vector2i, champion: String, title: String, capture_name: String = "") -> void:
	get_window().content_scale_size = viewport_size
	get_window().size = viewport_size
	await settle()
	var fixture := {"id":"layout-" + str(checks), "kind":"event_awards", "title":title, "date":"2026-10-02", "champion":champion, "quick":true}
	var original := JSON.stringify(fixture)
	feed.present(fixture)
	if is_instance_valid(feed.flight): feed.flight.kill()
	feed.sheet.rotation = 0
	feed.sheet.modulate.a = 1
	feed._layout()
	await settle()
	var name_label := feed.body.find_child("HonoursChampionName", true, false) as Label
	var heading := feed.body.find_child("HonoursChampionHeading", true, false) as Label
	var headline := feed.body.find_child("HonoursHeadline", true, false) as Label
	var prefix := str(viewport_size) + " " + champion.left(20)
	check(name_label != null and heading != null and headline != null, prefix + " stable champion text nodes")
	if name_label != null and heading != null and headline != null:
		check(name_label.get_line_count() == 1 and heading.get_line_count() == 1, prefix + " champion and heading stay horizontal")
		check(name_label.size.x >= feed.body.size.x - 1 and name_label.size.x > 160, prefix + " champion receives complete text column")
		check(name_label.tooltip_text == champion and name_label.text == champion, prefix + " full long team name retained for tooltip")
		check(headline.size.x >= feed.body.size.x - 1 and headline.get_line_count() < maxi(2, title.length() / 2), prefix + " event headline wraps across full sheet width")
		if headline.get_theme_font("font").get_string_size(title, HORIZONTAL_ALIGNMENT_LEFT, -1, 28).x > headline.size.x:
			check(title.find(" · ") < 0 or headline.text.contains("\n"), prefix + " long title wraps at a meaningful subtitle boundary")
		check(feed.sheet.size.x <= viewport_size.x * .86 + 1 and feed.sheet.position.x >= 0, prefix + " no horizontal newspaper overflow")
	check(JSON.stringify(fixture) == original, prefix + " layout leaves award evidence unchanged")
	if not capture_name.is_empty(): await capture(capture_name)
	feed._release()
	await settle()

func run() -> void:
	check("--no-service" in OS.get_cmdline_user_args(), "no-service test flag")
	CareerBridge.sound_muted = true
	CareerBridge.context = {"player":{"id":"human"}, "calendar":{"revision":22}, "stories":[], "feedback":{"items":[]}}
	CareerBridge.connected = true
	CareerBridge.clock_held = true
	get_window().content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	var media: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/media.json"))
	var manifest_path := str(media.get("team_manifest", ""))
	if FileAccess.file_exists(manifest_path):
		var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
		var paths := {}
		for team in manifest.get("team_backgrounds", {}): paths[team] = manifest.team_backgrounds[team].get("path", "")
		CareerBridge.context["media"] = {"team_backgrounds":paths}
	var feed = CareerBridge.feedback
	feed.set_process(false)
	feed.command_sender = command
	var snapshot := {"id":"awards-event-1", "kind":"event_awards", "title":"冠军及个人荣誉", "event_name":"Fixture LAN", "date":"2026-06-21", "quick":true, "own_team":"Team A", "champion":"Team A", "human_id":"human", "mvp":{"player":"Player A", "team":"Team A", "player_id":"human"}, "evp":[{"player":"Player B", "team":"Team B"}], "five":[{"player":"Player A", "team":"Team A"}, {"player":"Player B", "team":"Team B"}, {"player":"Player C", "team":"Team A"}, {"player":"Player D", "team":"Team B"}, {"player":"Player E", "team":"Team A"}]}
	var original := JSON.stringify(snapshot)
	CareerBridge.context.feedback.items = [snapshot]
	feed.ingest(); feed.ingest()
	check(feed.queue.size() == 1, "polling identical frozen feed does not enqueue duplicates")
	feed._process(0)
	await settle()
	check(CareerBridge.feedback_active and not feed.entry.is_empty() and feed.sheet.visible, "championship newspaper opens and locks world input")
	check(feed.last_sound == "champion", "own event championship uses celebration sting")
	check(feed.body.find_children("HonoursPlayerName", "Label", true, false).size() == 7, "MVP EVP and all five best lineup players are presented")
	check(feed.actions.size() == 1, "quick honours require no ceremony trip")
	check(JSON.stringify(snapshot) == original, "presentation never changes frozen match or awards")
	feed.acknowledge(); feed.acknowledge()
	check(sent.size() == 1 and sent[0].body.ids == [snapshot.id] and sent[0].body.revision == 22, "one explicit acknowledgement with stable id and revision")
	feed._finished("/api/3d/feedback/ack", {"ok":false, "reason":"fixture failure"})
	check(not feed.entry.is_empty() and not feed.actions[0].disabled, "failed acknowledgement retains newspaper and allows retry")
	feed.acknowledge()
	feed._finished("/api/3d/feedback/ack", {"ok":true})
	await settle()
	check(not CareerBridge.feedback_active and feed.entry.is_empty(), "acknowledgement releases modal without selecting unrelated story")
	check(feed.map_result("match-1-map-0", true), "map victory emits a sound")
	check(not feed.map_result("match-1-map-0", false) and feed.last_sound == "win", "same map result replay cannot emit contradictory or duplicate sound")
	check(feed.map_result("match-1-map-1", false) and feed.last_sound == "loss", "map defeat has distinct feedback")
	var waves: Array = []
	for kind in ["win", "loss", "champion", "honours"]:
		var sound = feed.make_sound(kind)
		waves.append(sound.data.size())
		check(sound.format == AudioStreamWAV.FORMAT_16_BITS and sound.mix_rate == 22050 and sound.data.size() > 0, "valid original cached audio " + kind)
	check(waves[2] > waves[0], "championship sting lasts longer than map feedback")
	CareerBridge.context.stories = [{"id":"decision", "choices":[{"id":"yes"}]}]
	check(not feed.can_present(), "business story choice is not stolen by awards presentation")
	CareerBridge.context.stories = []
	var top := {"id":"top20-2026", "kind":"top20", "title":"2026 年度Top20", "quick":false, "rows":[{"rank":1, "player":"Player A", "team":"Team A"}, {"rank":2, "player":"Player B", "team":"Team B"}, {"rank":3, "player":"Player C", "team":"Team A"}], "ceremony":{"ready":true,"finalized":true,"year":2026}}
	feed.present(top)
	await settle()
	check(feed.actions.size() == 2 and feed.actions[0].text.contains("颁奖现场"), "normal Top20 offers formal ceremony along with readable feedback")
	check(feed.body.find_children("HonoursPlayerName", "Label", true, false).size() == 3, "Top20 displays frozen names and ranks")
	if DisplayServer.get_name() != "headless":
		await get_tree().create_timer(.7).timeout
		await capture("honours-top20")
	feed._release()
	await settle()
	for viewport_size in [Vector2i(1920,1080), Vector2i(1280,720), Vector2i(1024,768), Vector2i(640,480), Vector2i(390,844), Vector2i(320,568)]:
		await champion_layout(feed, viewport_size, "FlyQuest", "赛事冠军 · IEM 世界锦标赛", "honours-champion-%dx%d" % [viewport_size.x, viewport_size.y])
	await champion_layout(feed, Vector2i(1024,768), "International Counter-Strike Championship Academy", "2026 国际反恐精英世界锦标赛 · 欧洲赛区年度总决赛冠军与个人荣誉", "honours-champion-long-1024")
	await champion_layout(feed, Vector2i(390,844), "国际反恐精英职业俱乐部联合竞技青训队", "2026 国际反恐精英世界锦标赛 · 欧洲赛区年度总决赛冠军与个人荣誉", "honours-champion-long-390")
	await champion_layout(feed, Vector2i(320,568), "International Counter-Strike Championship Academy", "2026 国际反恐精英世界锦标赛 · 欧洲赛区年度总决赛冠军与个人荣誉")
	Computer.close_computer()
	print("FEEDBACK_RESULT ", JSON.stringify({"checks":checks,"failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
