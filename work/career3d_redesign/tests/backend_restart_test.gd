extends Node
## An opt-in integration test. All saves and the owned Python process belong
## to the caller-created temporary fixture, never the playable installation.
var failures: Array[String] = []
var checks := 0
var owned_pids: Array[int] = []
var recovered_request := false

func confirmed(path: String, result: Dictionary) -> void:
	if path == "/api/fixture/spend" and result.get("ok", false) and result.get("result_summary", false):
		recovered_request = true

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("RESTART_CHECK ", "PASS " if value else "FAIL ", label)

func _ready() -> void:
	call_deferred("run")

func wait_until(predicate: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000)
	while not predicate.call() and Time.get_ticks_msec() < deadline:
		await get_tree().process_frame
	return predicate.call()

func run() -> void:
	var args: Dictionary = {}
	for arg in OS.get_cmdline_user_args():
		if arg.contains("="):
			args[arg.get_slice("=", 0)] = arg.substr(arg.find("=") + 1)
	var fixture := str(args.get("--fixture-root", ""))
	if fixture.is_empty() or not FileAccess.file_exists(fixture.path_join("restart-test.marker")):
		check(false, "caller must supply a marked temporary fixture")
		finish(); return
	CareerBridge.settings = {"repo_root":fixture, "python":args["--python"],
		"data_dir":fixture.path_join("career"), "import_cs2_config":false}
	CareerBridge.ready_file = fixture.path_join("ready.json")
	var launch := CareerBridge.service_launch(CareerBridge.settings, CareerBridge.ready_file, OS.get_process_id())
	CareerBridge.process_id = OS.create_process(launch.executable, launch.args, false)
	CareerBridge.owns_service = CareerBridge.process_id > 0
	owned_pids.append(CareerBridge.process_id)
	CareerBridge.connecting = true
	CareerBridge.startup_started = Time.get_ticks_msec()
	CareerBridge.phone_open = true # no autonomous date advancement during fixture
	CareerBridge.set_process(true)
	if not await wait_until(func(): return CareerBridge.connected, 40):
		check(false, "initial real backend connects")
		finish(); return
	check(true, "initial real backend connects")
	var previous_pid: int = CareerBridge.process_id
	var previous_token: String = CareerBridge.token
	var previous_day: String = str(CareerBridge.context.get("date", ""))
	check(not previous_day.is_empty(), "initial saved career is projected")
	check(OS.kill(previous_pid) == OK, "kill only the test-owned backend")
	await wait_until(func(): return not OS.is_process_running(previous_pid), 5)
	CareerBridge.refresh()
	var recovered := await wait_until(func(): return CareerBridge.connected and CareerBridge.process_id != previous_pid, 45)
	owned_pids.append(CareerBridge.process_id)
	check(recovered, "frontend respawns and reconnects after abrupt process death")
	check(CareerBridge.token != previous_token, "new handshake replaces stale authentication token")
	check(str(CareerBridge.context.get("date", "")) == previous_day, "reconnect preserves saved progress")
	check(not CareerBridge.active_post and CareerBridge.queued_command.is_empty(), "reconnect does not replay a write")
	if recovered:
		CareerBridge.command_finished.connect(confirmed)
		var before_money := int(CareerBridge.context.get("money", 0))
		previous_pid = CareerBridge.process_id
		previous_token = CareerBridge.token
		var marker := FileAccess.open(fixture.path_join("fault-armed.marker"), FileAccess.WRITE)
		marker.store_string("one post-commit interruption")
		marker.close()
		check(CareerBridge.command("/api/fixture/spend", {"request_id":"committed-fixture-001"}), "send one fixture command")
		var reported := await wait_until(func(): return CareerBridge.reconnecting and not CareerBridge.unknown_command.is_empty(), 20)
		check(reported, "coded commit error triggers recovery without a transport failure")
		check(CareerBridge.unknown_command.get("request_id") == "committed-fixture-001", "recovery retains original command identity")
		var confirmed_save := await wait_until(func(): return recovered_request, 45)
		owned_pids.append(CareerBridge.process_id)
		check(confirmed_save, "restart rolls forward and receipt confirms committed operation")
		check(CareerBridge.process_id != previous_pid and CareerBridge.token != previous_token, "recovery uses a new owned process and handshake")
		check(int(CareerBridge.context.get("money", 0)) == before_money + 37, "committed operation applies exactly once")
		check(CareerBridge.unknown_command.is_empty() and CareerBridge.queued_command.is_empty(), "recovery clears lookup without replaying writes")
		check(FileAccess.file_exists(fixture.path_join("fault-consumed.marker")), "real file replacement failure was injected")
	finish()

func finish() -> void:
	# The service's parent watchdog is also active; cleanup is limited to PIDs
	# created by this test, including the frontend-owned replacement.
	CareerBridge.set_process(false)
	for pid in owned_pids:
		if pid > 0 and OS.is_process_running(pid): OS.kill(pid)
	print("RESTART_RESULT checks=", checks, " failures=", failures)
	get_tree().quit(0 if failures.is_empty() else 1)
