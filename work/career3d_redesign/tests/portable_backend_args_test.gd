extends Node
## Run headless with res://tests/portable_backend_args_test.tscn -- --no-service.
## The production static helpers only construct paths/arguments; no child is launched.
const Bridge = preload("res://scripts/career_bridge.gd")
var checks := 0
var failures: Array[String] = []

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("PORTABLE_BACKEND_CHECK ", "PASS " if value else "FAIL ", label)

func _ready() -> void:
	call_deferred("run")

func run() -> void:
	var moved := "Q:/Moved Tester/CS2 Career 3D/game"
	var ready := moved.path_join("runtime/service-321.json")
	check(Bridge.local_path("../backend/CareerBackend.exe", moved) == "Q:/Moved Tester/CS2 Career 3D/backend/CareerBackend.exe", "backend resolves beside a relocated game folder")
	check(Bridge.local_path("res://runtime/career", moved) == moved.path_join("runtime/career"), "resource notation resolves to the local package folder")
	check(Bridge.local_path("R:/Separate Career/demo", moved) == "R:/Separate Career/demo", "explicit separate demo directory remains absolute")
	var packaged := Bridge.service_launch({"backend_exe":"../backend/CareerBackend.exe", "repo_root":"", "python":"", "data_dir":"runtime/career"}, ready, 321, moved)
	check(packaged.get("executable", "") == "Q:/Moved Tester/CS2 Career 3D/backend/CareerBackend.exe", "packaged backend does not require source or a Python installation")
	var expected := PackedStringArray(["--data-dir", moved.path_join("runtime/career"), "--port", "127.0.0.1:0", "--ready-file", ready, "--parent-pid", "321", "--media-config", moved.path_join("data/media.json")])
	check(packaged.get("args", PackedStringArray()) == expected, "backend receives isolated data, loopback port, handshake, owner and local media")
	var source := Bridge.service_launch({"python":"../Python/python.exe", "repo_root":"../source", "data_dir":"runtime/career"}, ready, 321, moved)
	check(source.get("executable", "") == "Q:/Moved Tester/CS2 Career 3D/Python/python.exe", "source fallback resolves a relative interpreter")
	var source_args: PackedStringArray = source.get("args", PackedStringArray())
	check(source_args.size() == expected.size() + 2 and source_args[0] == "-B" and source_args[1] == "Q:/Moved Tester/CS2 Career 3D/source/tools/career3d_service.py", "source fallback disables bytecode and resolves the backend script")
	check(source_args.slice(2) == expected, "source fallback preserves the same service contract")
	for command in ["python", "python.exe"]:
		var on_path := Bridge.service_launch({"python":command, "repo_root":"../..", "data_dir":"runtime/career"}, ready, 321, moved)
		check(on_path.get("executable", "") == command, "bare interpreter uses PATH: " + command)
	var absolute := Bridge.service_launch({"python":"S:/Python/python.exe", "repo_root":"S:/Source", "data_dir":"R:/Separate Career/demo"}, ready, 321, moved)
	var absolute_args: PackedStringArray = absolute.get("args", PackedStringArray())
	check(absolute.get("executable", "") == "S:/Python/python.exe" and absolute_args[1] == "S:/Source/tools/career3d_service.py" and absolute_args[3] == "R:/Separate Career/demo", "existing absolute source configuration remains compatible")
	check(Bridge.service_launch({"python":"", "repo_root":""}, ready, 321, moved).has("error"), "missing launch configuration reports a clear error")
	print("PORTABLE_BACKEND_RESULT ", JSON.stringify({"checks":checks, "failures":failures, "processes_launched":0}))
	get_tree().quit(0 if failures.is_empty() else 1)
