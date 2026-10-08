extends SceneTree
## Isolated scene/input checks; --no-service keeps career saves untouched.
var checks := 0
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("run")

func check(ok: bool, caption: String) -> void:
	checks += 1
	if not ok: failures.append(caption)
	print("ENVIRONMENT_UI ","PASS " if ok else "FAIL ",caption)

func frames(count: int = 3) -> void:
	for index in range(count): await physics_frame

func capture(name_value: String) -> void:
	if not "--capture-environment" in OS.get_cmdline_user_args(): return
	await process_frame
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://temp"))
	root.get_texture().get_image().save_png("res://temp/" + name_value + ".png")

func run() -> void:
	check("--no-service" in OS.get_cmdline_user_args(),"test never starts service")
	var bridge := root.get_node("CareerBridge")
	bridge.set_process(false)
	var initial_locale := root.get_node("Locale")
	initial_locale.language="zh-CN"; TranslationServer.set_locale("zh_CN"); initial_locale.changed.emit()
	var context: Dictionary = bridge.context.duplicate(true)
	context["environment"] = {"blocked":"","home":{"balance":10000,"owned":["plant","bookshelf","wall_sage","floor_oak"],"placed":[],"wallpaper":"sage","floor":"oak",
		"fixed":[[-2,-.8,1.84,2.85],[-.65,-1.94,.65,.65],[1.4,-2.01,2.5,.98],[1.35,-.94,.7,.68],[1.72,.83,1.03,.96],[2.59,2.14,.83,.72],[.05,1.06,1.24,1.24]],
		"anchors":[[-1.45,1.35],[-1.5,1.1],[.4,-1.2],[2.1,2.2]],
		"catalog":[{"id":"plant","name":"绿植","name_en":"Potted plant","kind":"furniture","price":350,"footprint":[.45,.45],"solid":true,"color":"7b9d70"},
		{"id":"bookshelf","name":"小书架","name_en":"Bookshelf","kind":"furniture","price":900,"footprint":[.8,.35],"solid":true,"color":"caa078"},
		{"id":"wall_sage","name":"鼠尾草绿墙面","name_en":"Sage walls","kind":"wallpaper","price":400,"style":"sage"}]}}
	bridge.context = context
	# The empty lounge no longer carries the coffee table/beanbag/cabinet solids.
	context.environment.home.fixed = context.environment.home.fixed.slice(0,4)
	change_scene_to_file("res://bedroom.tscn")
	await scene_changed
	await frames(5)
	var room := current_scene
	var decor = room.decoration
	check(decor!=null,"bedroom has decoration editor")
	check(room.get_node_or_null("CoffeeTable")==null and room.get_node_or_null("Beanbag")==null and room.get_node_or_null("EntryCabinet")==null,"removed default lounge has no invisible colliders")
	var optional := 0
	for mesh in room.model.find_children("*","MeshInstance3D",true,false):
		var label := str(mesh.name).replace("_"," ").to_lower()
		if "coffee table" in label or "beanbag" in label or "entry cabinet" in label or "rug" in label:
			optional += 1
			check(not mesh.visible,"optional authored mesh hidden: " + label)
	check(optional>5,"real furnished model was inspected")
	var original_camera := Vector3(room.yaw,room.pitch,room.zoom)
	var original_position: Vector3 = room.player.position
	decor.present(); await frames()
	check(decor.visible and bridge.phone_open and room.player.locked,"editor locks movement and clock")
	check(not room.get_node("WorldHud").visible,"world device shortcuts cannot bypass unsaved decoration prompt")
	check(room.player.carried_item=="","decoration does not make player hold phone")
	check(room.camera.h_offset!=0,"room moves beside catalogue while decorating")
	decor._use(decor._item("plant"))
	decor.set_process(false)
	decor.pending.x=2.75; decor.pending.z=-.5
	check(decor._local_valid(decor.pending),"free floor accepts purchased furniture")
	decor._rotate(); check(int(decor.pending.rotation)==90,"rotation advances 90 degrees")
	decor._color("d8acac"); check(decor.pending.color=="d8acac","furniture color selectable")
	var blocked: Dictionary = decor.pending.duplicate(true)
	blocked.x=-2;blocked.z=-.75
	check(not decor._local_valid(blocked),"bed footprint rejects furniture")
	blocked.x=2;blocked.z=2.25
	check(not decor._local_valid(blocked),"door approach rejects furniture")
	decor.ghost.visible=true
	var click := InputEventMouseButton.new()
	click.button_index=MOUSE_BUTTON_LEFT;click.pressed=true
	decor._place_pending(); await frames()
	check(decor.draft.size()==1 and decor.dirty,"floor click adds draft without saving")
	var furniture := room.get_node("HomeDecorBuilding")
	check(furniture.get_child_count()>0,"draft places real 3D furniture")
	check(bridge.context.environment.home.placed.is_empty(),"preview never changes persisted projection")
	var first: Dictionary = decor.draft[0].duplicate(true)
	decor._move(first)
	decor.pending.x=2.5;decor.pending.z=-.5
	decor.ghost.visible=true;decor._place_pending()
	check(decor.draft.size()==1 and decor.draft[0].x==2.5,"move updates same furniture instance")
	decor._select_at(Vector3(2.5,.12,-.5))
	check(decor.pending.id==first.id,"clicking placed furniture selects it without another purchase")
	check(not room.get_node("HomeDecorBuilding").get_child(0).visible,"moving item hides original mesh until placed or cancelled")
	decor._cancel_move()
	check(room.get_node("HomeDecorBuilding").get_child(0).visible,"cancel restores original mesh")
	decor._close_requested()
	check(decor.visible and decor.closing_prompt,"dirty close asks before discarding")
	await frames()
	await capture("home-decoration-zh")
	var viewport_before := root.size
	for resolution in [Vector2i(960,540),Vector2i(1920,1080)]:
		root.size=resolution
		await frames()
		check(root.get_visible_rect().encloses(decor.panel.get_global_rect()),"decoration panel fits " + str(resolution))
		check(decor.panel.get_global_rect().encloses(decor.save_button.get_global_rect()),"save remains visible " + str(resolution))
		var front: Vector2 = room.camera.unproject_position(Vector3(0,.12,1.8))
		check(root.get_visible_rect().has_point(front) and not decor.panel.get_global_rect().has_point(front),"free floor remains clickable " + str(resolution))
		await capture("home-decoration-" + str(resolution.x))
	root.size=viewport_before
	await frames()
	decor.close(); await frames()
	check(not decor.visible and not bridge.phone_open and not room.player.locked,"closing restores controls")
	check(room.player.position.is_equal_approx(original_position),"editor does not move player")
	check(Vector3(room.yaw,room.pitch,room.zoom).is_equal_approx(original_camera),"closing restores camera")
	check(room.get_node("HomeDecorBuilding").get_child_count()==0,"discard restores saved room")
	# Save freezes every input path, and refreshes must preserve an unsaved draft.
	decor.present()
	decor._use(decor._item("plant")); decor.pending.x=0; decor.pending.z=1
	check(decor._local_valid(decor.pending),"former coffee-table position is now available")
	decor._place_pending()
	var staged: Array = decor.draft.duplicate(true)
	bridge.changed.emit()
	check(decor.draft==staged and decor.dirty,"context refresh keeps unsaved room draft")
	var writes: Array = []
	decor.command_sender = func(path, body): writes.append({"path":path,"body":body.duplicate(true)}); return true
	decor._move(decor.draft[0]); decor._save()
	check(writes.is_empty() and not decor.pending.is_empty(),"save cannot silently discard pending move")
	decor._cancel_move(); decor._save()
	decor._remove(str(staged[0].id)); decor._move(staged[0]); decor._clear_room(); decor._save(); decor._use(decor._item("bookshelf"))
	check(writes.size()==1 and decor.draft==staged and decor.pending.is_empty(),"in-flight save freezes remove, move, clear and duplicate save")
	check(decor.save_button.disabled,"save button stays disabled during request")
	bridge.context.environment.home.placed=staged.duplicate(true)
	bridge.changed.emit()
	decor._finished(writes[0].path,{"ok":true,"reason":"fixture saved"})
	check(not decor.dirty and decor.baseline==staged,"acknowledged layout becomes saved baseline")
	# Do not strand a character inside furniture placed at their old position.
	room.player.position=Vector3(0,.12,1)
	decor.close(); await frames()
	check(Vector2(room.player.position.x,room.player.position.z).length()>0.0 and room.player.position.distance_to(Vector3(0,.12,1))>.3,"closing editor clears newly occupied player position")
	decor.present(); decor._clear_room()
	check(decor.draft.is_empty() and decor.dirty and "plant" in decor.home.owned,"pack away keeps furniture in inventory")
	decor.close(); await frames()
	check(room.get_node("HomeDecorBuilding").get_child_count()==1,"discard pack-away restores saved item")
	bridge.context.environment.home.placed=[]; bridge.changed.emit()
	decor.present()
	bridge.context.environment.blocked="请先结束当前比赛，再装修或升级设施。"
	bridge.changed.emit()
	var escape := InputEventKey.new(); escape.pressed=true; escape.physical_keycode=KEY_ESCAPE
	decor._unhandled_input(escape)
	check(not decor.visible and not bridge.phone_open,"blocked decoration can still be closed with Escape")
	bridge.context.environment.blocked=""
	var locale := root.get_node("Locale")
	locale.language = "en"; TranslationServer.set_locale("en"); locale.changed.emit()
	decor.present(); await frames()
	check(decor.content.get_child_count()>1,"English furniture catalogue renders")
	await capture("home-decoration-en")
	decor.close()
	locale.language = "zh-CN"; TranslationServer.set_locale("zh_CN"); locale.changed.emit()
	context["operations"] = {"loan":{"active":false,"cap":0,"rate":.03},"wages":[],"log":[],"unsigned":false,"player_only":true}
	context["finance"] = {"club":{"balance":900000,"next_net":-9500,"lines":[]},"pocket":{"balance":10000,"next_net":1500,"lines":[]}}
	context.environment["club"] = {"team_id":"a","tier":"standard","tier_name":"普通俱乐部","tier_name_en":"Standard club","balance":900000,"facilities":{"training":1,"meeting":1,"kitchen":1,"lounge":1},
		"next_tier":{"id":"elite","name":"豪门俱乐部","name_en":"Elite club","price":650000},"upgrades":[]}
	for item in [["training","训练室",18000],["meeting","战术会议室",12000],["kitchen","厨房",8000],["lounge","休息区",10000]]:
		context.environment.club.upgrades.append({"id":item[0],"name":item[1],"level":1,"current":{"name":"基础设施"},"next":{"name":"升级设施","price":item[2]}})
	bridge.context = context.duplicate(true)
	var computer := root.get_node("Computer")
	computer.open_app("operations","bedroom")
	await process_frame
	check(computer.content.find_child("ClubFacilities",true,false)!=null,"computer exposes facility management")
	check(computer.content.find_children("FacilityUpgrade_*","Button",true,false).size()==4,"four distinct facility upgrade controls")
	computer.business._ask_facility("facility",{"team_id":"a","facility":"training","level":2,"price":18000},"双屏训练区")
	await process_frame
	check(computer.content.find_child("ConfirmFacilityUpgrade",true,false)!=null,"purchase shows explicit club account confirmation")
	check(int(bridge.context.environment.club.balance)==900000,"preview and confirmation do not debit wallet")
	computer.scroll.ensure_control_visible(computer.content.find_child("ConfirmFacilityUpgrade",true,false))
	await frames()
	await capture("club-facilities-zh")
	computer.business._cancel_facility(); await process_frame
	check(computer.business.pending_facility.is_empty(),"cancel clears purchase without write")
	computer.close_computer(); await frames()
	check(not bridge.phone_open and not room.player.locked,"computer returns to bedroom movement")
	print("ENVIRONMENT_UI_RESULT checks=",checks," failures=",JSON.stringify(failures))
	quit(0 if failures.is_empty() else 1)
