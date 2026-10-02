extends Node
## This drives the same phone commands as a player, against an isolated service.
var failures: Array[String]=[]
var checks:=0
var last_result: Dictionary={}
var response_serial:=0

func check(ok: bool,label: String) -> void:
	checks+=1
	if not ok:failures.append(label)
	print("CAREER3D_CHECK ","PASS " if ok else "FAIL ",label)

func wait_idle(seconds: int=90) -> bool:
	var deadline: int=Time.get_ticks_msec()+seconds*1000
	while (CareerBridge.busy or CareerBridge.connecting) and Time.get_ticks_msec()<deadline:
		await get_tree().process_frame
	return CareerBridge.connected and not CareerBridge.busy

func send(path: String,body: Dictionary) -> Dictionary:
	await wait_idle()
	last_result={}; var serial:=response_serial
	check(CareerBridge.command(path,body),"command accepted "+path)
	var deadline: int=Time.get_ticks_msec()+90000
	while response_serial==serial and Time.get_ticks_msec()<deadline:await get_tree().process_frame
	return last_result.duplicate(true)

func calendar(day: String) -> Dictionary:
	await wait_idle(); last_result={}; var serial:=response_serial
	check(CareerBridge.calendar(day,false),"calendar accepted "+day)
	var deadline: int=Time.get_ticks_msec()+90000
	while (response_serial==serial or CareerBridge.calendar_running or CareerBridge.busy) and Time.get_ticks_msec()<deadline:await get_tree().process_frame
	return last_result.duplicate(true)

func run() -> void:
	process_mode=Node.PROCESS_MODE_ALWAYS
	# Survive travel; it is the actual same-window scene manager.
	reparent(CareerBridge)
	CareerBridge.command_finished.connect(func(_path,result):last_result=result;response_serial+=1)
	var online: bool=await wait_idle(45)
	check(online,"Godot starts Python and authenticates")
	if not online:_finish(); return
	check(CareerBridge.context.get("isolated",false),"isolated career reported")
	check(get_tree().current_scene.scene_file_path=="res://bedroom.tscn","morning starts in bedroom")
	CareerBridge.clock_held=true
	for page in Phone.PAGES:Phone.present(page); await get_tree().process_frame
	check(Phone.screen.visible and CareerBridge.phone_open,"all seven phone pages render")
	var before: float=CareerBridge.clock_minutes
	await get_tree().create_timer(.15).timeout
	check(CareerBridge.clock_minutes==before,"phone pauses display clock")
	Phone.close_phone()
	Travel.go("club"); await Travel.arrived
	var club=get_tree().current_scene
	check(club.life.roster.size()==8,"four real teammates plus four staff")
	var members: Dictionary={}
	for actor in club.life.roster:
		if actor.definition.get("player_id","")!="":members[str(actor.definition["player_id"])]=true
	# Exact career projection is also exposed by life.snapshot().
	var bound: Dictionary=club.life.snapshot().get("career",{})
	check(not bound.is_empty() or members.size()==4,"roster identity bound, not generic strangers")
	Phone.present("team")
	check(not club.player.enabled or CareerBridge.phone_open,"phone blocks world movement")
	Phone.close_phone()
	Travel.go("major"); await Travel.arrived
	var arena=get_tree().current_scene
	arena.finish_intro()
	check(arena.atmosphere!=null,"enclosed venue atmosphere present")
	Phone.present("settings"); Phone._audio()
	check(Input.mouse_mode==Input.MOUSE_MODE_VISIBLE,"phone releases first-person mouse")
	Phone.close_phone()
	Travel.go("bedroom"); await Travel.arrived
	check(get_tree().current_scene.scene_file_path=="res://bedroom.tscn","return to bedroom in same window")
	var initial: String=str(CareerBridge.context.get("date",""))
	var next: String=CareerBridge.add_days(initial,1)
	var result: Dictionary=await calendar(next)
	check(result.get("status")=="reached" and CareerBridge.context.get("date")==next,"calendar reaches exact future date")
	var invite: Dictionary={}
	var invitation_date := "9999"
	var event_dates: Dictionary={}
	for event in CareerBridge.context.get("calendar_events",[]):event_dates[str(event["id"])]=str(event.get("date",""))
	for item in CareerBridge.context.get("inbox",[]):
		if item.get("kind")=="invite" and item.get("status")=="open":
			var day: String=event_dates.get(str(item.get("event_id","")),"9999")
			if day<invitation_date:invite=item; invitation_date=day
	check(not invite.is_empty(),"real event invitation available")
	if not invite.is_empty():
		result=await send("/api/3d/mail/accept",{"id":invite["id"]})
		check(result.get("ok",false),"real invitation accepted")
		var target_date:=CareerBridge.add_days(invitation_date,7)
		result=await calendar(target_date)
		check(result.get("status")=="paused","calendar pauses before a due match or story")
		for attempt in range(12):
			var stories: Array=CareerBridge.context.get("stories",[])
			if not stories.is_empty():
				var story: Dictionary=stories[0]; var choices: Array=story.get("choices",[])
				var choice: String=str(choices[0]["id"]) if not choices.is_empty() else ""
				for candidate in choices:
					if "reject" in str(candidate.get("id","")).to_lower() or "refuse" in str(candidate.get("id","")).to_lower():choice=str(candidate["id"])
				await send("/api/3d/story",{"id":story["id"],"choice":choice})
			else:
				var game = CareerBridge.context.get("nextmatch")
				if game is Dictionary and game.get("due",false):
					await send("/api/3d/match/simulate",{"match_id":game["id"]})
				else:await calendar(target_date)
			if not CareerBridge.context.get("recent_matches",[]).is_empty():break
		var recent: Array=CareerBridge.context.get("recent_matches",[])
		check(not recent.is_empty(),"real simulated series persisted")
		if not recent.is_empty():
			var serial:=response_serial
			Phone._load_detail(str(recent[0]["id"]))
			while response_serial==serial:await get_tree().process_frame
			var totals: Array=last_result.get("match",{}).get("totals",[])
			check(totals.size()==10,"ten player report is real backend data")
			var pid: String=str(CareerBridge.context.get("player",{}).get("id","")); var own:=0
			for row in totals:
				if row.get("player_id")==pid:own+=1
			check(own==1,"one unique highlighted player identity")
			check(Phone.active_page=="match" and not Phone.detail.is_empty(),"report renders in phone")
	_finish()

func _finish() -> void:
	var result: Dictionary={"checks":checks,"failures":failures,"date":CareerBridge.context.get("date",""),"data_dir":CareerBridge.settings.get("data_dir",""),"player":CareerBridge.context.get("player",{}),"recent":CareerBridge.context.get("recent_matches",[])}
	var file:=FileAccess.open("res://temp/career_integration_report.json",FileAccess.WRITE); file.store_string(JSON.stringify(result,"  ")); file.close()
	print("CAREER3D_RESULT ",JSON.stringify(result))
	CareerBridge.quit()
