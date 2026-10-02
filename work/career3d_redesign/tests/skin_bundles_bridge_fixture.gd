extends "res://scripts/career_bridge.gd"
## Captures native UI requests in memory; never launches a service or game.
var requests: Array = []

func _ready() -> void:
	connecting = false
	connected = true
	clock_held = true
	set_process(false)

func _send(path: String, body: Dictionary, post: bool = true) -> bool:
	requests.append({"path":path, "body":body.duplicate(true), "post":post})
	return true
