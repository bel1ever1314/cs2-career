extends Node
## Run the copied E-drive project with --no-service. No service, saves or CS2.
const Roster=preload("res://scripts/venue_match_roster.gd")
const Cue=preload("res://scripts/arena_competitive_cue.gd")
var failures: Array[String]=[]
var checks:=0
var commands: Array[String]=[]
var scene

func _ready() -> void:
	if get_parent()!=Travel:
		var runner=get_script().new();Travel.add_child(runner)
	else:call_deferred("run")

func check(value: bool, label: String) -> void:
	checks+=1
	if not value:failures.append(label)
	print("VENUE_FLOW ","PASS " if value else "FAIL ",label)

func frames(count: int) -> void:
	for i in range(count):
		if is_instance_valid(scene):scene.focused=true;scene.paused=false
		await get_tree().physics_frame

func venue(destination: String) -> Dictionary:
	var a: Array=[];var b: Array=[]
	for i in range(5):
		a.append({"id":"own_"+str(i),"player_id":"own_"+str(i),"name":"Ally "+str(i),"team":"Own","role":"rifle"})
		b.append({"id":"opp_"+str(i),"player_id":"opp_"+str(i),"name":"Opponent "+str(i),"team":"Other","role":"rifle"})
	return {"destination":destination,"travel_allowed":true,"should_walk":true,"identity_source":"frozen_match_rosters","team_a":"Own","team_b":"Other","own_team":"Own","human_id":"own_0","players_a":a,"players_b":b,"event_name":"Isolated Fixture Event","name":"Original career stage"}

func arrive(destination: String, id: String) -> bool:
	var source:=venue(destination)
	source["match_id"]=id
	var frozen:=JSON.stringify(source)
	CareerBridge.context={"player":{"id":"own_0","name":"Ally 0","role":"rifle"},"team":{"name":"Own","roster":source["players_a"].duplicate(true)},"nextmatch":{"id":id,"event":"Isolated Fixture Event","date":"2026-10-02","opponent":"Other","best_of":3,"due":true},"match_preflight":{"match_id":id,"phase":"ready","due":true,"venue":source.duplicate(true),"can_launch":true,"connection":{"can_launch":true},"veto":{"complete":true}}}
	Computer.match_center.show_real=true;Computer.match_center.pending_match_id=id
	check(Travel.go_match(source,id),"accept physical "+destination+" match visit")
	source["players_a"][0]["name"]="MUTATED OUTSIDE"
	var until:=Time.get_ticks_msec()+30000
	while Travel.busy and Time.get_ticks_msec()<until:await get_tree().process_frame
	scene=get_tree().current_scene;scene.testing=true;scene.player.test_mode=true;scene.focused=true
	if destination=="major":scene.finish_intro()
	await frames(12)
	check(not Travel.busy and scene.scene_file_path==Travel.SCENES[destination],"in-process arrival "+destination)
	check(JSON.stringify(Travel.match_visit["venue"])==frozen,"venue roster snapshot deep copy")
	Computer.match_center.command_sender=func(path: String,_body: Dictionary):commands.append(path);return false
	return not Travel.busy

func walk(point: Vector3) -> bool:
	for i in range(1800):
		var direction: Vector3=point-scene.player.position;direction.y=0
		if direction.length()<.18:
			scene.player.test_direction=Vector3.ZERO;await frames(10);return true
		scene.player.test_direction=direction.normalized();await frames(1)
	scene.player.test_direction=Vector3.ZERO
	check(false,"walk obstructed "+str(point)+" at "+str(scene.player.position))
	return false

func capture(label: String, eye: Vector3=Vector3.ZERO, focus: Vector3=Vector3.ZERO) -> void:
	if "--venue-flow-capture" not in OS.get_cmdline_user_args():return
	var owned: bool=scene.camera_owned
	if eye!=Vector3.ZERO:
		scene.camera_owned=true;scene.camera.position=eye;scene.camera.look_at(focus,Vector3.UP)
	await get_tree().process_frame;await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png("res://renders/"+label+".png")
	scene.camera_owned=owned
	await frames(3)

func run() -> void:
	CareerBridge.connected=false;CareerBridge.set_process(false);CareerBridge.sound_muted=true
	var online:=venue("lan");online["travel_allowed"]=false
	check(not Travel.go_match(online,"online"),"online/unknown projection cannot request physical travel")
	check(not Travel.is_match_seated(venue("lan"),"any"),"false hand-off never grants seat permission")
	var sample:=venue("major");var original:=JSON.stringify(sample)
	var valid:=Roster.plan({"match_id":"frozen","venue":sample})
	check(valid.size()>0 and Roster.identity(valid["own"][2])=="own_0","stable human ID reserves exactly centre seat")
	check(JSON.stringify(sample)==original,"presentation ordering leaves donor roster untouched")
	sample["players_b"][0]["player_id"]="own_0"
	check(Roster.plan({"venue":sample}).is_empty(),"duplicate identity rejected without invented peers")
	sample["players_b"][0]["player_id"]=null
	check(Roster.plan({"venue":sample}).is_empty(),"null ID never becomes a fabricated string identity")
	if not await arrive("lan","lan-fixture"):finish();return
	check(scene.peers.size()==9,"small LAN has nine real frozen peers")
	check(not Travel.is_match_seated(venue("lan"),"lan-fixture"),"standing user cannot launch")
	Computer.match_center.command("launch",{"match_id":"lan-fixture","side":"ct"})
	check(commands.is_empty(),"actual UI launch handler blocks standing user without sending command")
	await walk(Vector3(0,0,3.2));var approach: Vector3=scene.player.position
	await capture("lan_nine_peers",Vector3(5.8,2.4,4.9),Vector3(0,1.1,0))
	scene.interact();await frames(65)
	check(Computer.screen.visible and Computer.location=="lan" and Computer.active_page=="career_match","small LAN E opens current match computer")
	check(Computer.match_center.pending_match_id=="lan-fixture" and Computer.match_center.current_preflight().get("match_id","")=="lan-fixture","current match/preflight survives physical scene hand-off")
	check(Travel.is_match_seated(venue("lan"),"lan-fixture"),"own LAN seat grants matching physical gate")
	check(not Travel.is_match_seated(venue("lan"),"another-match"),"another match never reuses seated gate")
	Computer.close_computer();await frames(35)
	check(not scene.device_seated and scene.player.position.distance_to(approach)<.05,"computer close restores LAN approach")
	check(not Travel.is_match_seated(venue("lan"),"lan-fixture"),"standing back up releases launch gate")
	if not await arrive("major","major-fixture"):finish();return
	check(scene.peers.size()==9 and scene.allies.size()==4 and scene.diagnostic_snapshot()["seated_peers"]==5,"major starts with four walking teammates and five seated opponents")
	check(not Travel.menu_open,"competition arrival keeps door menu out of team walkout")
	check(scene.atmosphere.entrance_bpm==136.0 and scene.atmosphere.competitive,"competition gets distinct original 136 BPM cue")
	var ids: Dictionary={}
	for actor in scene.peers:ids[actor.npc_id]=true
	check(ids.size()==9 and not ids.has("own_0"),"nine distinct IDs and player's seat genuinely empty")
	await capture("major_team_holding",Vector3(0,2.8,57.0),Vector3(0,1.2,53.5))
	for point in [Vector3(0,0,35),Vector3(0,0,16),Vector3(0,0,2.5),Vector3(2.1,0,2.5),Vector3(2.1,0,-7.8),Vector3(8,0,-7.8),Vector3(8,0,-12.5),Vector3(9,0,-18.48),Vector3(-5.96,0,-18.48)]:
		if not await walk(point):break
	for i in range(4500):
		if scene.competition_phase=="ready":break
		await frames(1)
	check(scene.competition_phase=="ready" and scene.diagnostic_snapshot()["seated_peers"]==9,"four teammates physically use aisle/ramp and take their seats")
	if scene.competition_phase!="ready":
		for entry in scene.allies:
			print("ALLY_DEBUG ",entry["actor"].position," step=",entry["step"]," colliders=",entry["actor"].get_slide_collision_count())
			for i in range(entry["actor"].get_slide_collision_count()):print("ALLY_COLLISION ",entry["actor"].get_slide_collision(i).get_collider().name)
	check(scene._at_player_seat(),"user walks continuously to rear empty seat")
	check(scene.atmosphere.entrance_count==1 and scene.atmosphere.portal_landed,"team walkout/portal cue occurs once")
	await capture("major_nine_peers",Vector3(0,4.4,-22.0),Vector3(0,2.5,-16.0))
	check(not Travel.go_match(venue("major"),"major-fixture"),"same scene and match cannot restart entrance")
	var standing: Vector3=scene.player.position
	scene.interact();await frames(65)
	check(Computer.screen.visible and Computer.location=="major" and Computer.active_page=="career_match","large venue own E seat opens major match computer")
	check(Travel.is_match_seated(venue("major"),"major-fixture"),"major launch gate requires completed walk and seat")
	Computer.close_computer();await frames(35)
	check(not scene.device_seated and not scene.camera_owned and scene.player.position.distance_to(standing)<.05,"major close releases seated camera and restores aisle")
	check(commands.is_empty(),"travel, walking, seating and close send no backend/CS2 command")
	var stream:=Cue.stream();var peak:=0.0;var build_energy:=0.0;var drop_energy:=0.0
	for i in range(stream.data.size()/2):
		var sample_value:=float(stream.data.decode_s16(i*2))/32767.0;peak=maxf(peak,absf(sample_value))
		var t:=float(i)/Cue.RATE
		if t>=1.0 and t<3.0:build_energy+=sample_value*sample_value
		if t>=4.0 and t<6.0:drop_energy+=sample_value*sample_value
	check(stream.get_length()>16.0 and stream.get_length()<17.0 and peak<.84,"original PCM cue bounded duration/peak")
	check(drop_energy>build_energy*1.4,"original cue clearly intensifies at competitive drop")
	ResourceSaver.save(stream,"res://temp/original_competitive_cue.tres")
	stream.save_to_wav("res://temp/original_competitive_cue.wav")
	var awards: Dictionary={"ready":true,"finalized":true,"year":2025,"human_id":"human","source":"season.top20","top3":[{"rank":1,"name":"Actual One","player_id":"one"},{"rank":2,"name":"Actual Two","player_id":"two"},{"rank":3,"name":"Actual Three","player_id":"three"}],"top20":[]}
	for i in range(20):awards["top20"].append({"rank":i+1,"name":"Archived "+str(i+1),"player_id":"archived_"+str(i+1)})
	check(Travel.go_awards(awards),"normal mode can reach finalized annual ceremony")
	awards["top3"][0]["name"]="MUTATED OUTSIDE"
	while Travel.busy:await get_tree().process_frame
	scene=get_tree().current_scene;scene.testing=true;scene.player.test_mode=true
	check(scene.finalized and not scene.preview and scene.top20_rows.size()==20 and "Actual One" in scene.ranking_board.text,"ceremony freezes actual annual top3 and full Top20")
	await capture("awards_actual_top20",Vector3(-5.8,2.0,3.0),Vector3(-9.6,2.5,3.0))
	check(not Travel.go_awards({"ready":true,"finalized":false}),"live ranking cannot masquerade as annual ceremony")
	finish()

func finish() -> void:
	var report: Dictionary={"checks":checks,"failures":failures,"commands":commands,"no_service":not CareerBridge.connected,"cs2_launches":0}
	var file:=FileAccess.open("res://temp/venue_match_flow.json",FileAccess.WRITE);file.store_string(JSON.stringify(report,"  "))
	print("VENUE_FLOW_RESULT ",JSON.stringify(report));get_tree().quit(0 if failures.is_empty() else 1)
