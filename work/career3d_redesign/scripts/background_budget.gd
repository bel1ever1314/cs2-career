extends Node
## The career window must not render a second 3D game behind CS2. Keep the
## bridge/autoloads alive for launch, result import, shutdown and reconnect.
const BACKGROUND_FPS := 10
var background := false
var foreground_fps := 0
var foreground_render := true
var parked_scene: Node
var parked_mode := Node.PROCESS_MODE_INHERIT
var elapsed := 0.0

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_process(not Engine.is_editor_hint() and DisplayServer.get_name() != "headless" and not "--no-service" in OS.get_cmdline_user_args())

func _process(delta: float) -> void:
	elapsed += delta
	if elapsed < .2: return
	elapsed = 0.0
	set_background(not get_window().has_focus())
	if background:
		# Scene changes/entrance transitions may still need to finish while a
		# launch is pending. Don't freeze a transition's awaited animation.
		if Travel.busy: _restore_scene()
		else: _park_scene()

func set_background(value: bool) -> void:
	if value == background: return
	background = value
	if value:
		foreground_fps = Engine.max_fps
		foreground_render = RenderingServer.render_loop_enabled
		Engine.max_fps = mini(foreground_fps, BACKGROUND_FPS) if foreground_fps > 0 else BACKGROUND_FPS
		RenderingServer.render_loop_enabled = false
		if not Travel.busy: _park_scene()
		# Pause immediately rather than allowing a nearly-expired map deadline
		# to run before the next low-rate UI update.
		if is_instance_valid(Computer.match_center): Computer.match_center.pace.pause(false)
	else:
		_restore_scene()
		Engine.max_fps = foreground_fps
		RenderingServer.render_loop_enabled = foreground_render

func _park_scene() -> void:
	var current := get_tree().current_scene
	if current == parked_scene: return
	_restore_scene()
	if not is_instance_valid(current): return
	parked_scene = current
	parked_mode = current.process_mode
	current.process_mode = Node.PROCESS_MODE_DISABLED

func _restore_scene() -> void:
	if is_instance_valid(parked_scene): parked_scene.process_mode = parked_mode
	parked_scene = null

func _exit_tree() -> void:
	if background:
		_restore_scene()
		Engine.max_fps = foreground_fps
		RenderingServer.render_loop_enabled = foreground_render
