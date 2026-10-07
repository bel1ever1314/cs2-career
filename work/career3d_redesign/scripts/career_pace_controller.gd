extends RefCounted
## Ephemeral playback state shared by both devices. Never restored from a save.
## The owner sends one command at a time; taking a deadline consumes it first.
const WAIT_SECONDS := 4.0
var running := false
var phase := "paused"
var remaining := WAIT_SECONDS
var target := ""
var reservation := ""
var reservation_target := ""
var in_flight := false
var next_mode := "simulate"

func pause() -> void:
	running = false
	remaining = WAIT_SECONDS
	if phase != "playing": phase = "paused"

func resume() -> void:
	running = true
	remaining = WAIT_SECONDS
	if phase == "paused": phase = "idle"

func arm(kind: String, key: String) -> void:
	phase = kind
	target = key
	remaining = WAIT_SECONDS

func reserve(mode: String, key: String) -> void:
	reservation = mode
	reservation_target = key
	# Cancel the simulation deadline immediately, including on its last frame.
	remaining = WAIT_SECONDS

func clear_reservation() -> void:
	reservation = ""
	reservation_target = ""

func take(key: String, mode: String = "") -> String:
	if in_flight or key != target: return ""
	in_flight = true
	var chosen := mode
	if chosen.is_empty(): chosen = reservation if reservation_target == key else "simulate"
	clear_reservation()
	phase = "dispatching"
	return chosen

func tick(delta: float, allowed: bool) -> bool:
	if not running or in_flight or not allowed or phase not in ["prepare", "waiting"]: return false
	remaining = maxf(0, remaining - delta)
	return remaining <= 0

func completed(series_finished: bool, next_key: String) -> void:
	in_flight = false
	if series_finished or reservation_target != next_key: clear_reservation()
	arm("waiting", next_key)

func reset() -> void:
	running = false
	phase = "paused"
	target = ""
	in_flight = false
	next_mode = "simulate"
	clear_reservation()
