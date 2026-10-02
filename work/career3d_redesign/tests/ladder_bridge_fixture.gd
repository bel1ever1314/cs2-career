extends "res://scripts/career_bridge.gd"
## A test-only transport. Real bridge signals/projection are inherited; no
## Python process, HTTP request, game process, or save writer is started.
var fixture_calls: Array[Dictionary] = []
var fixture_reads: Array[Dictionary] = []
var fixture_reject_next := false

func _ready() -> void:
	connecting = false
	connected = true
	endpoint = ""
	message = "天梯 UI 隔离检查"
	set_process(false)

func _send(path: String, body: Dictionary, post: bool = true) -> bool:
	if post: return command(path, body)
	fixture_reads.append({"path":path, "body":body.duplicate(true)})
	return false

func command(path: String, body: Dictionary = {}) -> bool:
	if fixture_reject_next:
		fixture_reject_next = false
		message = "隔离测试：操作未发出。"
		status_changed.emit()
		return false
	if busy or not connected: return false
	fixture_calls.append({"path":path, "body":body.duplicate(true)})
	active_path = path
	active_body = body.duplicate(true)
	active_post = true
	busy = true
	busy_changed.emit(true)
	return true

func fixture_complete(next_context: Dictionary = {}, result: Dictionary = {"ok":true}) -> void:
	var path := active_path
	busy = false
	busy_changed.emit(false)
	if not next_context.is_empty(): _apply_context(next_context.duplicate(true))
	command_finished.emit(path, result.duplicate(true))

func fixture_reset(value: Dictionary) -> void:
	busy = false
	connected = true
	active_path = ""
	active_body.clear()
	queued_command.clear()
	fixture_calls.clear()
	fixture_reads.clear()
	fixture_reject_next = false
	_apply_context(value.duplicate(true))
	busy_changed.emit(false)
