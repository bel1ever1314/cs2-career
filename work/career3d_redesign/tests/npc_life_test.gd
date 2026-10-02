extends Node
var app
var failures: Array[String]=[]
var checks:=0
func check(ok: bool,label: String) -> void:
	checks+=1
	if not ok:failures.append(label)
	print("NPC_CHECK ","PASS " if ok else "FAIL ",label)
func frames(n: int) -> void:
	for i in range(n):await get_tree().physics_frame
func avoids(points: Array,start: Vector3,body: Vector3,radius: float) -> bool:
	var previous:=start
	for point in points:
		var closest: Vector3=Geometry3D.get_closest_point_to_segment(body,previous,point)
		if Vector2(closest.x-body.x,closest.z-body.z).length()<radius:return false
		previous=point
	return true
func run(application) -> void:
	app=application
	await frames(10)
	var life=app.life
	var context: Dictionary={"player":{"id":"human"},"team":{"id":"fixture-club","roster":[
		{"id":"human","name":"真人","role":"igl","you":true},
		{"id":"fixture-awp","name":"测试主狙","role":"awp","ability":88},
		{"id":"fixture-entry","name":"测试突破","role":"entry","ability":84},
		{"id":"fixture-lurk","name":"测试自由人","role":"lurker","ability":82},
		{"id":"fixture-rifle","name":"测试步枪","role":"rifle","ability":85},
		{"id":"fixture-awp","name":"重复项","role":"awp"}]}}
	life.bind_career(context)
	await frames(2)
	check(life.roster.size()==8,"four actual teammates and four staff")
	var identities: Dictionary={};var coach
	for npc in life.roster:
		check(not identities.has(npc.npc_id) and npc.npc_id!="human","unique identity excludes human: "+npc.npc_id)
		identities[npc.npc_id]=npc
		if npc.template_id=="coach":coach=npc
	check(identities["fixture-awp"].nameplate.text=="测试主狙 · 主狙","actual name and role on nameplate")
	check(identities["fixture-awp"].definition["training"]==life.data["role_templates"]["awp"]["training"],"role-specific dialogue template")
	var before_binding: Dictionary=life.snapshot()
	var before_route: Array=identities["fixture-awp"].route.duplicate()
	life.bind_career(context)
	check(before_binding==life.snapshot() and before_route==identities["fixture-awp"].route,"same context preserves schedule and route")
	life.bind_career({"player":null,"team":null})
	check(before_binding==life.snapshot(),"missing player identity does not alter the displayed roster")
	var reordered: Dictionary=context.duplicate(true);reordered["team"]["roster"].reverse()
	life.bind_career(reordered)
	check(identities["fixture-awp"] in life.roster and before_route==identities["fixture-awp"].route,"reordered roster keeps the same NPC object")
	check(context["team"]["roster"][1]["name"]=="测试主狙","binding does not mutate career context")
	check(life.invalid_sites.is_empty(),"all stations have a reachable approach")
	var bypass_start: Vector3=life.navigation.world(life.navigation.nearest(Vector3(-9,.223,6.5)))
	var bypass_end: Vector3=life.navigation.world(life.navigation.nearest(Vector3(-5.75,.223,6.5)))
	var obstacle: Vector3=bypass_start.lerp(bypass_end,.5)
	var bypass: Array=life.navigation.path(bypass_start,bypass_end,[{"position":obstacle,"radius":.60}])
	check(not bypass.is_empty() and avoids(bypass,bypass_start,obstacle,.48),"dynamic path walks around a stationary person")
	check(not life.navigation.path(bypass_start,bypass_end).is_empty(),"temporary people do not corrupt the navigation grid")
	check(life.navigation.path(bypass_start,bypass_end,[{"position":bypass_end,"radius":.60}]).is_empty(),"occupied destination cannot count as arrival elsewhere")
	for npc in life.roster:
		var schedule: Array=npc.definition["schedule"]
		for i in range(schedule.size()):
			var a: Vector3=life.data["sites"][schedule[i][0]]["target"]
			var b: Vector3=life.data["sites"][schedule[(i+1)%schedule.size()][0]]["target"]
			check(not life.navigation.path(a,b).is_empty(),npc.npc_id+" path "+schedule[i][0]+" -> "+schedule[(i+1)%schedule.size()][0])
	app.player.position=coach.position+Vector3(0,0,1.0);app.player.reset_physics_interpolation()
	await frames(4)
	check(life.begin(coach),"nearby E-equivalent conversation")
	var remaining: float=coach.remaining
	var location: Vector3=coach.position
	var other_remaining: float=life.roster[1].remaining
	await frames(90)
	check(absf(coach.remaining-remaining)<.001 and coach.position.distance_to(location)<.01,"speaking NPC pauses current job")
	check(life.roster[1].remaining<other_remaining,"others keep doing their work")
	life.choose("training");var first: String=life.line
	life.choose("training");check(first!=life.line,"role dialogue rotates without immediate repeat")
	life.choose("encourage");var bond: int=coach.bond
	life.choose("encourage");check(coach.bond==bond,"repeated encouragement cannot farm relationship")
	life.choose("leave");await frames(4)
	check(not coach.talking and not app.player.locked and coach.remaining<remaining,"conversation resumes same job")
	life._next(coach)
	check(coach.state=="walking" and life.begin(coach),"conversation can pause an NPC on a route")
	var walking_route: Array=coach.route.duplicate();var walking_index: int=coach.route_index
	var walking_position: Vector3=coach.position
	await frames(30)
	check(coach.position.distance_to(walking_position)<.01 and coach.route==walking_route and coach.route_index==walking_index,"conversation preserves walking route and progress")
	life.close()
	check(coach.state=="walking" and not coach.talking and coach.route==walking_route,"leaving conversation resumes the original route")
	# A close NPC on the opposite side of the lounge partition is not audible
	# through E interaction. This is an isolated geometry negative case.
	var saved_position: Vector3=coach.position
	coach.position=Vector3(-4.85,.23,6.5);app.player.position=Vector3(-3.95,.23,6.5)
	await frames(2)
	check(not life.can_talk(coach),"no conversation through wall")
	coach.position=saved_position;coach.reset_physics_interpolation()
	app.player.position=Vector3(-.75,.23,6.65);app.player.reset_physics_interpolation()
	await frames(60*240)
	var actors: Dictionary={}
	for npc in life.roster:
		actors[npc.npc_id]={"distance":npc.travelled,"jobs":npc.finished_jobs,"state":npc.state,"site":npc.site_id,"position":str(npc.position),"stopped_for":npc.stopped_for,"visits":npc.job_counts}
		check(npc.travelled>2,npc.npc_id+" walks between activities")
		check(npc.finished_jobs>=2,npc.npc_id+" completes multiple jobs")
		check(npc.job_counts.size()>=2,npc.npc_id+" actually reaches different work sites")
		var arrivals: int=0
		for count in npc.job_counts.values():arrivals+=int(count)
		check(arrivals>=4 and life.clock-npc.last_arrival_at<100,npc.npc_id+" keeps reaching work sites instead of circling")
		check(npc.position.y>0,npc.npc_id+" stays on scene")
		check(npc.stopped_for<3.1,npc.npc_id+" bounded obstruction recovery")
	var saved: Dictionary=life.snapshot()
	check(saved["npcs"]["coach"]["bond"]==bond,"relationship included in scene-transfer snapshot")
	var changed: Dictionary=context.duplicate(true)
	changed["team"]["id"]="fixture-next-club"
	changed["team"]["roster"][4]={"id":"fixture-new","name":"新队友","role":"igl"}
	changed["team"]["roster"].pop_back()
	life.bind_career(changed);await frames(2)
	var changed_ids: Array[String]=[]
	for npc in life.roster:changed_ids.append(npc.npc_id)
	check(life.roster.size()==8 and "fixture-new" in changed_ids and not "fixture-rifle" in changed_ids,"team change refreshes actual teammates without duplicates")
	check(coach in life.roster and coach.bond==bond,"staff survive team changes")
	life.bind_career({"player":{"id":"human"},"team":null});await frames(2)
	check(life.roster.size()==4 and coach in life.roster,"unsigned context retains only staff")
	life.bind_career(context);await frames(2)
	var regrown: Dictionary={}
	for npc in life.roster:
		check(not regrown.has(npc.npc_id),"regrown roster identity stays unique: "+npc.npc_id)
		regrown[npc.npc_id]=true
	check(life.roster.size()==8,"joining a team recreates four teammates")
	life.restore(saved)
	check(life.snapshot()["npcs"]["coach"]["bond"]==bond and life.roster.size()==8,"scene snapshot restores bound roster and staff relationship")
	var result: Dictionary={"checks":checks,"failures":failures,"actors":actors,"path_queries":life.navigation.queries,"replans":life.replans,"waits":life.waits}
	var f:=FileAccess.open("res://temp/npc_test_report.json",FileAccess.WRITE);f.store_string(JSON.stringify(result,"  "))
	print("NPC_RESULT ",JSON.stringify(result))
	get_tree().quit(0 if failures.is_empty() else 1)
