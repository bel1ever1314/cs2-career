extends Node
const Budget = preload("res://scripts/background_budget.gd")
var failures: Array[String] = []
var draws := 0

func check(value: bool, message: String) -> void:
	print("BUDGET_CHECK ", "PASS " if value else "FAIL ", message)
	if not value: failures.append(message)

func _ready() -> void:
	call_deferred("run")

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(1); return
	var old_fps := Engine.max_fps
	Engine.max_fps = 120
	var governor := Budget.new()
	CareerBridge.add_child(governor)
	var old_mode := process_mode
	RenderingServer.frame_post_draw.connect(func(): draws += 1)
	await get_tree().create_timer(.5).timeout
	var foreground_draws := draws
	Computer.match_center.pace.flow.resume()
	governor.set_background(true)
	check(Engine.max_fps == 10 and not RenderingServer.render_loop_enabled, "background stops rendering and limits idle loop")
	check(process_mode == Node.PROCESS_MODE_DISABLED, "3D scene animations and node physics are parked")
	check(CareerBridge.can_process() and governor.can_process(), "service bridge and governor remain alive")
	check(not Computer.match_center.pace.flow.running, "background cannot auto-advance a map")
	await get_tree().create_timer(.2).timeout
	draws = 0
	await get_tree().create_timer(.5).timeout
	check(draws == 0, "no background draw submissions")
	governor.set_background(false)
	check(Engine.max_fps == 120 and RenderingServer.render_loop_enabled and process_mode == old_mode, "foreground restores exact previous settings")
	await get_tree().create_timer(.5).timeout
	if DisplayServer.get_name() != "headless": check(draws > 0 and foreground_draws > 0, "GPU drawing resumes after background idle")
	Engine.max_fps = 5
	governor.set_background(true)
	check(Engine.max_fps == 5, "do not raise an existing stricter frame cap")
	governor.set_background(false)
	governor.free()
	Engine.max_fps = old_fps
	print("BACKGROUND_BUDGET_RESULT failures=", failures.size(), " foreground_draws=", foreground_draws)
	get_tree().quit(0 if failures.is_empty() else 1)
