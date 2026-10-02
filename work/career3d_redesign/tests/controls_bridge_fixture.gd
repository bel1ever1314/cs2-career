extends Node
## Controls rendering fixture; no backend, career folder or game is connected.
var busy := false
var connected := true
var phone_open := false
var context := {"calendar":{"revision":3}}
var requests: Array = []

func _send(path: String, body: Dictionary, post: bool = true) -> bool:
	requests.append({"path":path, "body":body.duplicate(true), "post":post})
	return true
